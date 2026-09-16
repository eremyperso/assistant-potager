"""
utils/meteo.py — Météo quotidienne pour l'assistant potager
------------------------------------------------------------
Source : Open-Meteo (gratuit, sans clé API)
         https://open-meteo.com/

Fonctionnement :
  - Appel API Open-Meteo avec les coordonnées GPS configurées
  - Récupère température matin (8h) + après-midi (14h), précipitations,
    probabilité de pluie/orage, vent, code météo WMO
  - Traduit le code WMO en label lisible orienté potager
  - Enregistre automatiquement en base comme action 'observation'

Déclenchement :
  - Automatique à 05h00 chaque matin via JobQueue Telegram (bot.py)
  - Manuel via commande /meteo depuis Telegram

Zéro token Groq consommé — traitement 100% local.
"""

import logging
import time
import requests
from datetime import datetime, date, timezone as tz
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from sqlalchemy.orm import Session

log = logging.getLogger("potager")

# ── Coordonnées GPS du potager ────────────────────────────────────────────────
METEO_LATITUDE  = 48.96082453509178
METEO_LONGITUDE = 2.2038296967715305
METEO_TIMEZONE  = "Europe/Paris"

# ── URL Open-Meteo ─────────────────────────────────────────────────────────────
OPEN_METEO_URL         = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# ── Horizons de prévision ─────────────────────────────────────────────────────
# [US-182] Choix produit aligné sur la règle R3 du moteur de confiance (US-178,
# « aucun gel annoncé sur 14 jours ») ; Open-Meteo en accepte jusqu'à 16.
# Seul endroit où l'horizon est déclaré : `forecast_days` en découle.
METEO_HORIZON_PREVISION_JOURS = 14
# [US-075 / CA2] Horizon court du widget (`previsions`), inchangé par US-182.
METEO_HORIZON_WIDGET_JOURS    = 5
# [US-182 / CA7] Arrondi des coordonnées dans les journaux (~1 km) : assez pour
# diagnostiquer, pas assez pour retrouver l'adresse d'un jardinier.
METEO_DECIMALES_JOURNAL       = 2

# ── Codes météo WMO → label potager ───────────────────────────────────────────
# https://open-meteo.com/en/docs#weathervariables
WMO_CODES = {
    0:  ("☀️", "Ciel dégagé"),
    1:  ("🌤️", "Principalement dégagé"),
    2:  ("⛅", "Partiellement nuageux"),
    3:  ("☁️", "Couvert"),
    45: ("🌫️", "Brouillard"),
    48: ("🌫️", "Brouillard givrant"),
    51: ("🌦️", "Bruine légère"),
    53: ("🌦️", "Bruine modérée"),
    55: ("🌦️", "Bruine dense"),
    61: ("🌧️", "Pluie légère"),
    63: ("🌧️", "Pluie modérée"),
    65: ("🌧️", "Pluie forte"),
    71: ("🌨️", "Neige légère"),
    73: ("🌨️", "Neige modérée"),
    75: ("🌨️", "Neige forte"),
    77: ("🌨️", "Grains de neige"),
    80: ("🌦️", "Averses légères"),
    81: ("🌦️", "Averses modérées"),
    82: ("🌦️", "Averses violentes"),
    85: ("🌨️", "Averses de neige"),
    86: ("🌨️", "Averses de neige fortes"),
    95: ("⛈️", "Orage"),
    96: ("⛈️", "Orage avec grêle"),
    99: ("⛈️", "Orage violent avec grêle"),
}

def _wmo_label(code: int) -> tuple[str, str]:
    """Retourne (emoji, description) pour un code WMO."""
    return WMO_CODES.get(code, ("🌡️", f"Code météo {code}"))


def _conseil_potager(wmo_code: int, temp_matin: float, temp_aprem: float,
                     precipitations: float, vent_kmh: float) -> str:
    """
    Génère un conseil potager court en fonction des conditions météo.
    Logique locale — zéro token Groq.
    """
    conseils = []

    # Gel
    if temp_matin <= 0:
        conseils.append("⚠️ Risque de gel — protéger les plantations sensibles")
    elif temp_matin <= 3:
        conseils.append("🌡️ Température basse — surveiller les jeunes plants")

    # Canicule
    if temp_aprem >= 35:
        conseils.append("🌡️ Canicule — arrosage en soirée indispensable")
    elif temp_aprem >= 28:
        conseils.append("☀️ Chaleur — arrosage en soirée recommandé")

    # Pluie / orage
    if wmo_code in (95, 96, 99):
        conseils.append("⛈️ Orage prévu — pas d'arrosage ni de traitement")
    elif precipitations >= 10:
        conseils.append("🌧️ Pluie abondante — arrosage inutile")
    elif precipitations >= 3:
        conseils.append("🌦️ Pluie légère — arrosage probablement inutile")
    elif precipitations == 0 and temp_aprem >= 22:
        conseils.append("💧 Pas de pluie prévue — penser à arroser en soirée")

    # Vent
    if vent_kmh >= 50:
        conseils.append("💨 Vent fort — vérifier tuteurs et protections")
    elif vent_kmh >= 30:
        conseils.append("💨 Vent modéré — éviter les traitements foliaires")

    # Brouillard
    if wmo_code in (45, 48):
        conseils.append("🌫️ Brouillard — risque de maladies fongiques à surveiller")

    # Bon temps pour traitement
    if (wmo_code in (0, 1, 2) and precipitations == 0
            and vent_kmh < 20 and 10 <= temp_aprem <= 28):
        conseils.append("✅ Conditions idéales pour traitements foliaires")

    return " · ".join(conseils) if conseils else "🌿 Conditions normales"


def jour_local(timezone: str = METEO_TIMEZONE, maintenant: datetime | None = None) -> date:
    """
    [US-182] Date du jour dans le fuseau du potager — c'est elle, et non la date
    du serveur, qui borne une journée de prévision (le serveur peut tourner en UTC).

    `maintenant` doit être conscient du fuseau ; un fuseau inconnu retombe sur la
    date du serveur, en le journalisant.
    """
    instant = maintenant or datetime.now(tz.utc)
    try:
        return instant.astimezone(ZoneInfo(timezone)).date()
    except ZoneInfoNotFoundError:
        log.warning(f"⚠️  MÉTÉO FUSEAU    : fuseau inconnu '{timezone}', date du serveur utilisée")
        return instant.date()


def _parametres_prevision(latitudes: float | str, longitudes: float | str, timezone: str) -> dict:
    """Paramètres Open-Meteo communs à la lecture simple et à la lecture groupée
    (coordonnées séparées par des virgules pour la seconde)."""
    return {
        "latitude"            : latitudes,
        "longitude"           : longitudes,
        "timezone"            : timezone,
        # aujourd'hui + METEO_HORIZON_PREVISION_JOURS jours (US-182 / CA1)
        "forecast_days"       : METEO_HORIZON_PREVISION_JOURS + 1,
        # Instantané courant — température ressentie, humidité, vent (US-075 / CA3)
        "current"              : [
            "temperature_2m",
            "apparent_temperature",
            "relative_humidity_2m",
            "wind_speed_10m",
            "weather_code",
        ],
        # Données horaires
        "hourly"              : [
            "temperature_2m",
            "precipitation_probability",
            "precipitation",
            "windspeed_10m",
            "weathercode",
        ],
        # Données journalières
        "daily"               : [
            "weathercode",
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "precipitation_probability_max",
            "windspeed_10m_max",
            "sunrise",
            "sunset",
        ],
        "wind_speed_unit"     : "kmh",
        "precipitation_unit"  : "mm",
    }


def _localisation_journal(localisations: list[tuple[float, float]]) -> str:
    """[US-182 / CA7] Localisations arrondies pour les journaux : `48.96,2.20;43.30,5.38`."""
    d = METEO_DECIMALES_JOURNAL
    return ";".join(f"{lat:.{d}f},{lon:.{d}f}" for lat, lon in localisations)


def _journaliser_appel(
    localisations: list[tuple[float, float]],
    timezone: str,
    issue: str,
    debut: float,
    motif: str = "",
) -> None:
    """
    [US-182 / CA7] Une ligne par appel Open-Meteo — localisation arrondie, jour,
    issue, durée. Un échec est journalisé en erreur avec son motif : aucun appel
    ne disparaît dans un `except` muet.
    """
    duree_ms = int((time.perf_counter() - debut) * 1000)
    gabarit = "MÉTÉO APPEL      │ loc=%s │ jour=%s │ issue=%-14s │ %d ms │ %s"
    arguments = (
        _localisation_journal(localisations), jour_local(timezone).isoformat(),
        issue, duree_ms, motif or "-",
    )
    if issue == "succes":
        log.info("🌤️  " + gabarit, *arguments)
    elif issue == "succes_partiel":
        log.warning("⚠️  " + gabarit, *arguments)
    else:
        log.error("❌ " + gabarit, *arguments)


def _analyser_prevision(raw: dict) -> dict:
    """
    Transforme une réponse Open-Meteo (une localisation) en dict météo potager.
    Lève KeyError/IndexError/TypeError si la réponse est malformée.
    """
    daily   = raw["daily"]
    hourly  = raw["hourly"]
    current = raw.get("current") or {}
    times   = hourly["time"]  # liste de "2026-03-25T00:00", "...T01:00"...

    # Extraire la valeur horaire pour une heure cible (ex: 8 → 08:00)
    def hourly_val(key: str, hour: int):
        prefix = f"T{hour:02d}:00"
        for i, t in enumerate(times):
            if t.endswith(prefix):
                return hourly[key][i]
        return None

    wmo_code      = daily["weathercode"][0]
    temp_min      = daily["temperature_2m_min"][0]
    temp_max      = daily["temperature_2m_max"][0]
    precipitations= daily["precipitation_sum"][0] or 0.0
    proba_pluie   = daily["precipitation_probability_max"][0] or 0
    vent_max      = daily["windspeed_10m_max"][0] or 0.0
    lever_soleil  = daily["sunrise"][0]
    coucher_soleil= daily["sunset"][0]

    # Températures horaires pour le résumé potager
    temp_matin    = hourly_val("temperature_2m", 8)  or temp_min
    temp_aprem    = hourly_val("temperature_2m", 14) or temp_max
    proba_matin   = hourly_val("precipitation_probability", 8)  or 0
    proba_aprem   = hourly_val("precipitation_probability", 14) or 0

    emoji, label  = _wmo_label(wmo_code)
    conseil       = _conseil_potager(wmo_code, temp_matin, temp_aprem,
                                     precipitations, vent_max)

    def _round_or_none(v):
        return round(v, 1) if v is not None else None

    # [US-075 / CA2] Prévision des jours suivants (jour 0 = aujourd'hui, déjà
    # couvert ci-dessus) — jusqu'à 5 jours, selon ce que renvoie Open-Meteo.
    # [US-182 / CA1] Même lecture étendue à l'horizon de prévision complet, avec
    # l'horizon de chaque jour pour qu'un consommateur puisse en pondérer la fiabilité.
    previsions = []
    previsions_etendues = []
    for i in range(1, min(METEO_HORIZON_PREVISION_JOURS + 1, len(daily["time"]))):
        p_code = daily["weathercode"][i]
        p_emoji, p_label = _wmo_label(p_code)
        jour = {
            "date"     : daily["time"][i],
            "wmo_code" : p_code,
            "emoji"    : p_emoji,
            "label"    : p_label,
            "temp_max" : _round_or_none(daily["temperature_2m_max"][i]),
            "temp_min" : _round_or_none(daily["temperature_2m_min"][i]),
        }
        if i <= METEO_HORIZON_WIDGET_JOURS:
            previsions.append(dict(jour))
        previsions_etendues.append({**jour, "horizon_jours": i})

    return {
        "wmo_code"        : wmo_code,
        "emoji"           : emoji,
        "label"           : label,
        "temp_min"        : round(temp_min, 1),
        "temp_max"        : round(temp_max, 1),
        "temp_matin"      : round(temp_matin, 1),
        "temp_aprem"      : round(temp_aprem, 1),
        "precipitations"  : round(precipitations, 1),
        "proba_pluie"     : proba_pluie,
        "proba_matin"     : proba_matin,
        "proba_aprem"     : proba_aprem,
        "vent_max_kmh"    : round(vent_max, 1),
        "lever_soleil"    : lever_soleil[-5:],   # "HH:MM"
        "coucher_soleil"  : coucher_soleil[-5:], # "HH:MM"
        "conseil"         : conseil,
        "date"            : date.today().isoformat(),
        # [US-075 / CA2, CA3] Ajouts — absents de la version d'origine, sans
        # impact sur les consommateurs existants (bot, /meteo/history).
        "previsions"      : previsions,
        "temp_actuelle"   : _round_or_none(current.get("temperature_2m")),
        "ressenti"        : _round_or_none(current.get("apparent_temperature")),
        "humidite"        : current.get("relative_humidity_2m"),
        "vent_actuel_kmh" : _round_or_none(current.get("wind_speed_10m")),
        # [US-182 / CA1] Ajout — les 14 jours suivant aujourd'hui.
        "previsions_etendues": previsions_etendues,
    }


def fetch_meteo(
    lat: float = METEO_LATITUDE,
    lon: float = METEO_LONGITUDE,
    timezone: str = METEO_TIMEZONE,
) -> dict | None:
    """
    Interroge l'API Open-Meteo et retourne un dict avec les données météo
    pertinentes pour le potager.

    [US-075] `lat`/`lon`/`timezone` optionnels — repli sur les coordonnées du
    bot par défaut (comportement inchangé pour le job 5h et /meteo Telegram),
    même pattern que `fetch_meteo_history()`. Permet à `GET /meteo` d'interroger
    la localisation réelle d'un potager (US-074).

    Le dict retourné gagne des ajouts par rapport à la version d'origine, sans
    retirer ni renommer aucune clé existante (non-régression bot, US-075/CA5) :
    - `previsions` : jusqu'à 5 jours suivants (`date`, `wmo_code`, `emoji`,
      `label`, `temp_max`, `temp_min`)
    - `temp_actuelle`/`ressenti`/`humidite`/`vent_actuel_kmh` : instantané
      courant Open-Meteo, absents (`None`) si l'API ne les fournit pas.
    - [US-182] `previsions_etendues` : les `METEO_HORIZON_PREVISION_JOURS` jours
      suivants, mêmes champs que `previsions` plus `horizon_jours` (1 = demain).

    Sans cache : le job 5h et /meteo Telegram l'appellent directement. Les
    lectures en cache passent par `app.services.previsions_meteo` (US-182).

    Retourne None en cas d'erreur réseau.
    """
    params = _parametres_prevision(lat, lon, timezone)
    localisations = [(lat, lon)]
    debut = time.perf_counter()

    try:
        resp = requests.get(OPEN_METEO_URL, params=params, timeout=10)
        resp.raise_for_status()
        raw = resp.json()
    except requests.RequestException as e:
        _journaliser_appel(localisations, timezone, "echec_reseau", debut, str(e))
        return None

    try:
        meteo = _analyser_prevision(raw)
    except (KeyError, IndexError, TypeError) as e:
        _journaliser_appel(localisations, timezone, "echec_format", debut, repr(e))
        return None

    _journaliser_appel(localisations, timezone, "succes", debut)
    return meteo


def fetch_meteo_groupe(
    localisations: list[tuple[float, float]],
    timezone: str = METEO_TIMEZONE,
) -> list[dict | None] | None:
    """
    [US-182 / CA4] Prévision de plusieurs localisations en UN appel Open-Meteo
    (coordonnées séparées par des virgules ; la réponse est une liste dans
    l'ordre des coordonnées).

    Retourne une liste alignée sur `localisations` — `None` pour une localisation
    dont la réponse est malformée — ou `None` si l'appel lui-même échoue.
    """
    if not localisations:
        return []

    def _coordonnees(valeurs: list[float]) -> float | str:
        # Une seule localisation : même paramètre numérique que `fetch_meteo`.
        return valeurs[0] if len(valeurs) == 1 else ",".join(str(v) for v in valeurs)

    params = _parametres_prevision(
        _coordonnees([lat for lat, _ in localisations]),
        _coordonnees([lon for _, lon in localisations]),
        timezone,
    )
    debut = time.perf_counter()

    try:
        resp = requests.get(OPEN_METEO_URL, params=params, timeout=10)
        resp.raise_for_status()
        raw = resp.json()
    except requests.RequestException as e:
        _journaliser_appel(localisations, timezone, "echec_reseau", debut, str(e))
        return None

    # Open-Meteo rend un objet (et non une liste) pour une seule localisation.
    reponses = raw if isinstance(raw, list) else [raw]
    if len(reponses) != len(localisations):
        _journaliser_appel(
            localisations, timezone, "echec_format", debut,
            f"{len(reponses)} réponses pour {len(localisations)} localisations",
        )
        return None

    resultats: list[dict | None] = []
    for (lat, lon), reponse in zip(localisations, reponses):
        try:
            resultats.append(_analyser_prevision(reponse))
        except (KeyError, IndexError, TypeError) as e:
            _journaliser_appel([(lat, lon)], timezone, "echec_format", debut, repr(e))
            resultats.append(None)

    issue = "succes" if all(r is not None for r in resultats) else "succes_partiel"
    _journaliser_appel(localisations, timezone, issue, debut)
    return resultats


def format_meteo_commentaire(m: dict) -> str:
    """
    Formate les données météo en une ligne de commentaire pour la base.
    Stocké dans le champ `commentaire` de l'événement observation.

    Exemple :
    ☀️ Ensoleillé · Min 8°C / Max 22°C · Matin 12°C / AM 21°C ·
    Pluie 0mm (5%) · Vent 18km/h · Lever 07:12 · ✅ Conditions idéales
    """
    return (
        f"{m['emoji']} {m['label']} · "
        f"Min {m['temp_min']}°C / Max {m['temp_max']}°C · "
        f"Matin {m['temp_matin']}°C / AM {m['temp_aprem']}°C · "
        f"Pluie {m['precipitations']}mm ({m['proba_pluie']}%) · "
        f"Vent {m['vent_max_kmh']}km/h · "
        f"☀ {m['lever_soleil']}→{m['coucher_soleil']} · "
        f"{m['conseil']}"
    )


def fetch_meteo_history(
    lat: float = METEO_LATITUDE,
    lon: float = METEO_LONGITUDE,
    days: int = 30,
    timezone: str = METEO_TIMEZONE,
) -> list[dict] | None:
    """
    Interroge Open-Meteo Archive pour l'historique météo journalier.

    Args:
        lat      : latitude GPS (défaut : potager configuré)
        lon      : longitude GPS (défaut : potager configuré)
        days     : nombre de jours d'historique (7–365)
        timezone : fuseau IANA (défaut : Europe/Paris)

    Retourne une liste de dicts triés par date croissante :
        [{ date, temp_max, temp_min, precipitations, wmo_code, emoji, label }, ...]
    Retourne None en cas d'erreur réseau ou de parsing.
    """
    from datetime import timedelta

    today      = date.today()
    end_date   = today - timedelta(days=1)          # archive n'a pas les données du jour
    start_date = end_date - timedelta(days=days - 1)

    params = {
        "latitude"  : lat,
        "longitude" : lon,
        "start_date": start_date.isoformat(),
        "end_date"  : end_date.isoformat(),
        "daily"     : [
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "weathercode",
        ],
        "timezone"  : timezone,
    }

    try:
        resp = requests.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=10)
        resp.raise_for_status()
        raw = resp.json()
    except requests.RequestException as e:
        log.error(f"❌ MÉTÉO HISTORIQUE  : {e}")
        return None

    try:
        daily  = raw["daily"]
        times  = daily["time"]
        result = []
        for i, t in enumerate(times):
            wmo         = daily["weathercode"][i]
            emoji, label = _wmo_label(wmo)
            result.append({
                "date"          : t,
                "temp_max"      : daily["temperature_2m_max"][i],
                "temp_min"      : daily["temperature_2m_min"][i],
                "precipitations": daily["precipitation_sum"][i] or 0.0,
                "wmo_code"      : wmo,
                "emoji"         : emoji,
                "label"         : label,
            })
        log.info(f"🌤️  MÉTÉO HISTORIQUE : {len(result)} jours ({start_date} → {end_date})")
        return result
    except (KeyError, IndexError, TypeError) as e:
        log.error(f"❌ MÉTÉO HISTORIQUE PARSE : {e}")
        return None


def save_meteo_observation(db: Session) -> dict | None:
    """
    Récupère la météo du jour et l'enregistre en base comme observation.
    Évite les doublons : si une observation météo existe déjà pour aujourd'hui,
    ne crée pas de doublon.

    Retourne le dict météo si succès, None sinon.
    """
    from database.models import Evenement
    from utils.date_utils import parse_date

    # ── Anti-doublon : vérifier si observation météo déjà présente aujourd'hui
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_end   = datetime.combine(date.today(), datetime.max.time())

    existing = (
        db.query(Evenement)
        .filter(
            Evenement.type_action   == "observation",
            Evenement.texte_original == "[AUTO-METEO]",
            Evenement.date.between(today_start, today_end),
        )
        .first()
    )
    if existing:
        log.info(f"⏭️  MÉTÉO DOUBLON   : observation déjà présente pour aujourd'hui (id={existing.id})")
        return None

    # ── Appel API
    meteo = fetch_meteo()
    if not meteo:
        return None

    commentaire = format_meteo_commentaire(meteo)

    # ── Enregistrement en base
    event = Evenement(
        type_action    = "observation",
        culture        = None,
        variete        = None,
        quantite       = None,
        unite          = None,
        rang           = None,
        duree          = None,
        traitement     = None,
        commentaire    = commentaire,
        texte_original = "[AUTO-METEO]",
        date           = parse_date(meteo["date"]),
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    log.info(f"🌤️  MÉTÉO SAUVÉE    : id={event.id} | {commentaire[:80]}...")
    return meteo

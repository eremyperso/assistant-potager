"""
app/services/previsions_meteo.py — Prévisions à 14 jours, en cache par localisation [US-182]
============================================================================================
Le moteur de confiance (US-178) lit la météo bien plus souvent que le widget :
une lecture groupée par ouverture de l'écran Plan, une par question au bot.
Interroger Open-Meteo à chaque fois ferait de la charge et de la latence le
problème. Ce module est le seul point de lecture EN CACHE des prévisions ; le
job météo de 5 h et `/meteo` Telegram continuent d'appeler `fetch_meteo()`
directement, sans cache (inchangés).

Ce qui est délibérément écrit ici, et pourquoi :

- **[CA2] Clé `(latitude, longitude, fuseau, jour)`.** Les coordonnées sont
  arrondies à `DECIMALES_CLE` (~110 m, bien en deçà de la maille Open-Meteo) :
  deux potagers au même endroit partagent l'entrée, quel que soit le membre.
  Le fuseau fait partie de la clé parce qu'il découpe les journées de
  prévision — une prévision calée sur Paris n'est pas celle de Montréal. Le jour
  est celui du fuseau du potager (`jour_local`), pas celui du serveur.

- **[CA3] Une seule durée de validité, `DUREE_VALIDITE_CACHE`.** Une heure :
  le même appel alimente la température actuelle du widget (US-076), qu'une
  validité à la journée figerait sur la première lecture du matin (arbitrage
  produit du 16/09/2026). Une entrée expirée est rafraîchie à la lecture
  suivante ; aucun job ne le fait. Un changement de jour change la clé : la
  prévision d'hier n'est jamais servie pour aujourd'hui.

- **[CA5] Rien d'inventé.** Open-Meteo indisponible : on rend l'entrée du jour
  si elle existe — expirée, marquée `SOURCE_CACHE_EXPIRE` et avec son âge —,
  sinon `STATUT_INDISPONIBLE` sans aucune donnée. Chaque lecture porte l'âge de
  sa donnée ; c'est au consommateur de décider ce qu'il en fait.

- **[CA6] Sans localisation, pas d'appel.** `STATUT_LOCALISATION_MANQUANTE`
  est distinct de `STATUT_INDISPONIBLE` : l'un invite à localiser le potager,
  l'autre dit que le service météo ne répond pas.

- **[CA4] Lecture groupée en un appel.** Les localisations absentes du cache
  (ou expirées) sont demandées ensemble, en un seul appel Open-Meteo.

⚖️ Le cache vit dans la mémoire du processus (v1) : il ne survit pas à un
redémarrage et n'est pas partagé entre l'API et le bot. Le passer dans Redis
relève du plan multi-tenant, pas de cette US.
"""
import copy
import logging
import threading
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Optional

from database.models import Potager
from utils.meteo import METEO_TIMEZONE, fetch_meteo_groupe, jour_local

log = logging.getLogger("potager")

# ── Réglages (déclarés ici seulement) ─────────────────────────────────────────
DUREE_VALIDITE_CACHE = timedelta(hours=1)   # [CA3] seule déclaration de la validité
DECIMALES_CLE        = 3                    # [CA2] ~110 m

# ── Issues d'une lecture ──────────────────────────────────────────────────────
STATUT_DISPONIBLE             = "disponible"
STATUT_INDISPONIBLE           = "indisponible"
STATUT_LOCALISATION_MANQUANTE = "localisation_manquante"

SOURCE_OPEN_METEO   = "open_meteo"     # appel réseau effectué pour cette lecture
SOURCE_CACHE        = "cache"          # entrée valide, aucun appel
SOURCE_CACHE_EXPIRE = "cache_expire"   # Open-Meteo en échec : entrée expirée du jour


@dataclass(frozen=True)
class LecturePrevision:
    """Résultat d'une lecture de prévision : la météo, sa provenance et son âge."""
    statut: str
    meteo: Optional[dict] = None             # dict de `utils.meteo.fetch_meteo`
    source: Optional[str] = None             # SOURCE_* si disponible
    recuperee_le: Optional[datetime] = None  # instant de l'appel Open-Meteo (UTC)
    age_secondes: Optional[int] = None

    @property
    def disponible(self) -> bool:
        return self.statut == STATUT_DISPONIBLE


@dataclass(frozen=True)
class _Entree:
    meteo: dict
    recuperee_le: datetime


_CACHE: dict[tuple[float, float, str, date], _Entree] = {}
_VERROU = threading.Lock()


def cle_localisation(latitude: float, longitude: float) -> tuple[float, float]:
    """[CA2] Localisation arrondie qui sert de clé de cache et de coordonnées d'appel."""
    return (round(latitude, DECIMALES_CLE), round(longitude, DECIMALES_CLE))


def vider_cache() -> None:
    """Vide le cache (tests, diagnostic)."""
    with _VERROU:
        _CACHE.clear()


def _lecture(entree: _Entree, source: str, maintenant: datetime) -> LecturePrevision:
    # Copie profonde : un consommateur qui modifie sa météo ne corrompt pas le cache.
    return LecturePrevision(
        statut=STATUT_DISPONIBLE,
        meteo=copy.deepcopy(entree.meteo),
        source=source,
        recuperee_le=entree.recuperee_le,
        age_secondes=max(0, int((maintenant - entree.recuperee_le).total_seconds())),
    )


def lire_previsions_groupees(
    localisations: Iterable[tuple[Optional[float], Optional[float]]],
    fuseau: str = METEO_TIMEZONE,
    maintenant: Optional[datetime] = None,
) -> list[LecturePrevision]:
    """
    [CA4] Lit la prévision de plusieurs localisations en un appel de service.

    Retourne une lecture par localisation, dans l'ordre reçu. Une localisation
    incomplète (`None`) rend `STATUT_LOCALISATION_MANQUANTE` sans appel. Les
    localisations en cache valide ne déclenchent aucun appel ; les autres sont
    demandées ensemble, en UN appel Open-Meteo.

    `maintenant` (conscient du fuseau) sert aux tests ; par défaut l'heure UTC.
    """
    maintenant = maintenant or datetime.now(timezone.utc)
    jour = jour_local(fuseau, maintenant)
    localisations = list(localisations)

    cles: list[Optional[tuple[float, float]]] = [
        cle_localisation(lat, lon) if lat is not None and lon is not None else None
        for lat, lon in localisations
    ]

    with _VERROU:
        entrees = {
            cle: _CACHE.get((*cle, fuseau, jour))
            for cle in cles if cle is not None
        }
    a_rafraichir = [
        cle for cle, entree in entrees.items()
        if entree is None or maintenant - entree.recuperee_le >= DUREE_VALIDITE_CACHE
    ]
    rafraichies: set[tuple[float, float]] = set()

    if a_rafraichir:
        # Appel réseau hors verrou : une lecture lente ne bloque pas les autres.
        meteos = fetch_meteo_groupe(a_rafraichir, fuseau)
        with _VERROU:
            # Les entrées des jours passés ne serviront plus jamais : purgées ici.
            for cle_perimee in [c for c in _CACHE if c[3] != jour]:
                del _CACHE[cle_perimee]
            for cle, meteo in zip(a_rafraichir, meteos or [None] * len(a_rafraichir)):
                if meteo is None:
                    continue
                entree = _Entree(meteo=meteo, recuperee_le=maintenant)
                _CACHE[(*cle, fuseau, jour)] = entree
                entrees[cle] = entree
                rafraichies.add(cle)

    lectures: list[LecturePrevision] = []
    for cle in cles:
        if cle is None:
            lectures.append(LecturePrevision(statut=STATUT_LOCALISATION_MANQUANTE))
            continue
        entree = entrees[cle]
        if cle in rafraichies:
            lectures.append(_lecture(entree, SOURCE_OPEN_METEO, maintenant))
        elif cle not in a_rafraichir:
            log.debug("🌤️  MÉTÉO CACHE      │ loc=%.2f,%.2f │ jour=%s │ issue=cache", *cle, jour)
            lectures.append(_lecture(entree, SOURCE_CACHE, maintenant))
        elif entree is not None:
            lecture = _lecture(entree, SOURCE_CACHE_EXPIRE, maintenant)
            log.warning(
                "⚠️  MÉTÉO CACHE      │ loc=%.2f,%.2f │ jour=%s │ issue=cache_expire │ age=%ds",
                *cle, jour, lecture.age_secondes,
            )
            lectures.append(lecture)
        else:
            log.warning("⚠️  MÉTÉO CACHE      │ loc=%.2f,%.2f │ jour=%s │ issue=indisponible", *cle, jour)
            lectures.append(LecturePrevision(statut=STATUT_INDISPONIBLE))
    return lectures


def lire_previsions(
    latitude: Optional[float],
    longitude: Optional[float],
    fuseau: str = METEO_TIMEZONE,
    maintenant: Optional[datetime] = None,
) -> LecturePrevision:
    """[CA1, CA2, CA5, CA6] Lecture en cache de la prévision d'une localisation."""
    return lire_previsions_groupees([(latitude, longitude)], fuseau, maintenant)[0]


def lire_prevision_potager(
    potager: Optional[Potager],
    maintenant: Optional[datetime] = None,
) -> LecturePrevision:
    """[CA1, CA6] Prévision d'un potager, sur sa localisation (US-074)."""
    if potager is None:
        return LecturePrevision(statut=STATUT_LOCALISATION_MANQUANTE)
    return lire_previsions(potager.latitude, potager.longitude, maintenant=maintenant)


def lire_previsions_potagers(
    potagers: Iterable[Potager],
    maintenant: Optional[datetime] = None,
) -> dict[int, LecturePrevision]:
    """[CA4] Prévisions de plusieurs potagers en un appel de service, par `potager.id`."""
    potagers = list(potagers)
    lectures = lire_previsions_groupees(
        [(p.latitude, p.longitude) for p in potagers], maintenant=maintenant,
    )
    return {p.id: lecture for p, lecture in zip(potagers, lectures)}

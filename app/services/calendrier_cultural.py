"""
app/services/calendrier_cultural.py — Référentiel de calendrier cultural [US-068]
--------------------------------------------------------------------------------
Quand semer, dans combien de temps la culture lèvera, quand récolter : une
DONNÉE DE RÉFÉRENCE, lue sans aucun appel à un modèle de langage, et corrigeable
depuis le bot. Ce module ne crée aucun écran et ne modifie aucun calcul existant
— ses consommatrices sont US-070 (recalage sur les événements réels), l'écran
Plan (US-060) et la vue Cultures du Lot E.

Le modèle — celui des calendriers de semis, pas celui de la maquette
--------------------------------------------------------------------
    culture_config ── itinéraire cultural (« standard », « culture d'hiver »…)
                        ├── fenêtres, PAR ZONE climatique
                        │     semis en pépinière · semis en pleine terre · plantation · récolte
                        └── durées, COMMUNES à toutes les zones
                              semis → levée · semis → première récolte
                              semis → repiquage (itinéraire pépinière seulement)
                              plantation → première récolte [US-177]
                                           (itinéraire qui se plante seulement)

    potager ── zone climatique : choisie > déduite de la localisation > défaut

Trois décisions, et où elles vivent
-----------------------------------
1. **La zone se déduit à la lecture, elle ne se stocke pas (CA7, CA8).**
   `Potager.zone_climatique` ne porte que le CHOIX du jardinier. Sans choix, la
   zone est déduite de la localisation par `zone_depuis_localisation` — une
   seule règle, pas une seconde écrite en SQL dans une migration — puis retombe
   sur `CALENDRIER_ZONE_DEFAUT`. `zone_effective` dit toujours laquelle des
   trois origines a parlé : un jardinier doit savoir si « méditerranéen » est
   son choix ou une supposition.
2. **Une correction est locale au potager (CA11).** La première correction
   copie l'itinéraire partagé en un itinéraire personnalisé (`potager_id` non
   nul), qui le REMPLACE ensuite pour ce potager seulement. L'import n'écrit que
   du partagé : il ne peut donc, par construction, jamais écraser une valeur
   saisie par un jardinier (CA9).
3. **Rien n'est inventé (CA13).** Pas de fenêtre de repli empruntée à une zone
   voisine, pas de durée moyenne : une fenêtre absente n'est pas affichée, une
   durée absente se lit « — ». Une fourchette reste une fourchette (CA4).

Ce qui n'entre PAS ici
----------------------
L'écartement (CA5) : `culture_config.espacement` et `surface_m2` font foi. Les
attributs de conduite (US-161) et les relations (US-162, US-163) non plus.
"""
from __future__ import annotations

import logging
import re
import statistics
from dataclasses import dataclass, field
from typing import Iterable, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session
from unidecode import unidecode

from app.services import referentiel_sources as svc_sources
from app.services.context import TenantContext
from app.services.permissions import require_potager_non_archive, require_role
from database.models import (
    CultureConfig,
    DureeCulturale,
    FenetreCulturale,
    ItineraireCultural,
    Potager,
    ReferentielSource,
)
from utils.culture_resolve import normaliser_culture

log = logging.getLogger("potager")


class ValeurCalendrierInvalideError(ValueError):
    """Valeur refusée — rien n'est écrit. Le message est lu par le jardinier."""


class CultureInconnueError(LookupError):
    """La culture n'a aucune fiche `culture_config` : le calendrier enrichit une
    culture déjà dictée, il n'en crée aucune (même invariant qu'US-161/CA7)."""


# ── [CA6] Zones climatiques ──────────────────────────────────────────────────
#: Valeurs stockées, sans accent — comme `Potager.etat`. Les libellés accentués
#: ne vivent qu'à l'affichage.
ZONES_CLIMATIQUES: tuple[str, ...] = ("oceanique", "continental", "mediterraneen", "montagnard")

LIBELLES_ZONES: dict[str, str] = {
    "oceanique": "océanique",
    "continental": "continental",
    "mediterraneen": "méditerranéen",
    "montagnard": "montagnard",
}

#: Ce que la saisie tolère — le jardinier tape « méditerranée » ou « montagne ».
_ALIAS_ZONES: dict[str, str] = {
    "oceanique": "oceanique", "ocean": "oceanique", "atlantique": "oceanique",
    "continental": "continental", "continentale": "continental",
    "mediterraneen": "mediterraneen", "mediterraneenne": "mediterraneen",
    "mediterranee": "mediterraneen",
    "montagnard": "montagnard", "montagnarde": "montagnard", "montagne": "montagnard",
}

#: [CA7] Les trois origines possibles de la zone lue par un potager.
ORIGINE_ZONE_JARDINIER = "jardinier"
ORIGINE_ZONE_LOCALISATION = "localisation"
ORIGINE_ZONE_DEFAUT = "defaut"

_ZONE_DEFAUT_SECOURS = "oceanique"

# ── [CA2] Phases des fenêtres ────────────────────────────────────────────────
PHASE_SEMIS_PEPINIERE = "semis_pepiniere"
PHASE_SEMIS_PLEINE_TERRE = "semis_pleine_terre"
#: [CA17, amendement du 15/09/2026] Mise en place DÉFINITIVE d'un plant — issu
#: de la pépinière, acheté, ou organe de multiplication (caïeu, tubercule…).
#: Fenêtre autonome : elle n'est jamais déduite du semis en pépinière et du
#: délai de repiquage (CA18), et ne fait pas d'un itinéraire un itinéraire
#: « pépinière » (CA19, `_a_pepiniere`).
PHASE_PLANTATION = "plantation"
PHASE_RECOLTE = "recolte"

#: Dans l'ordre où un calendrier se lit — l'ordre du geste (CA20).
PHASES: tuple[str, ...] = (
    PHASE_SEMIS_PEPINIERE, PHASE_SEMIS_PLEINE_TERRE, PHASE_PLANTATION, PHASE_RECOLTE,
)

LIBELLES_PHASES: dict[str, str] = {
    PHASE_SEMIS_PEPINIERE: "Semis en pépinière",
    PHASE_SEMIS_PLEINE_TERRE: "Semis en pleine terre",
    PHASE_PLANTATION: "Plantation",
    PHASE_RECOLTE: "Récolte",
}

#: ⚠️ « plantation » est AUSSI un alias de la durée `repiquage` (`_ALIAS_ETAPES`) :
#: les deux tables ne sont jamais consultées ensemble — `fenetre` et `duree` sont
#: deux sous-commandes. L'alias d'étape est GARDÉ (CA29) : au bot, la
#: sous-commande tranche ; à la dictée, c'est la nature de la valeur — des mois
#: pour la fenêtre, des jours pour la durée (`interpreteur_commandes`).
#: « terre » seul n'est volontairement PAS un alias : « pomme de terre » se
#: lirait alors comme une culture suivie d'une phase.
_ALIAS_PHASES: dict[str, str] = {
    "pepiniere": PHASE_SEMIS_PEPINIERE, "semis_pepiniere": PHASE_SEMIS_PEPINIERE,
    "godet": PHASE_SEMIS_PEPINIERE, "abri": PHASE_SEMIS_PEPINIERE,
    "pleine_terre": PHASE_SEMIS_PLEINE_TERRE, "semis_pleine_terre": PHASE_SEMIS_PLEINE_TERRE,
    "pleineterre": PHASE_SEMIS_PLEINE_TERRE, "place": PHASE_SEMIS_PLEINE_TERRE,
    "plantation": PHASE_PLANTATION, "plantations": PHASE_PLANTATION,
    "recolte": PHASE_RECOLTE, "recoltes": PHASE_RECOLTE,
}

# ── [CA3] Étapes des durées ──────────────────────────────────────────────────
ETAPE_LEVEE = "levee"
ETAPE_RECOLTE = "recolte"
ETAPE_REPIQUAGE = "repiquage"
#: [US-177 / CA1] Quatrième étape : mise en place d'un PLANT → première récolte.
#: Les trois autres comptent depuis le semis ; celle-ci depuis la plantation, et
#: c'est toute sa raison d'être — un plant acheté en jardinerie n'a pas de semis,
#: donc pas d'origine, donc aucune récolte attendue (US-070 / CA11). Elle n'est
#: JAMAIS obtenue en retranchant `repiquage` à `recolte` (CA2) : ces deux durées
#: ne sont pas comptées sur la même convention, et leur différence serait un
#: chiffre que personne n'a mesuré.
ETAPE_PLANTATION_RECOLTE = "plantation_recolte"

ETAPES: tuple[str, ...] = (
    ETAPE_LEVEE, ETAPE_RECOLTE, ETAPE_REPIQUAGE, ETAPE_PLANTATION_RECOLTE,
)

LIBELLES_ETAPES: dict[str, str] = {
    ETAPE_LEVEE: "Semis → levée",
    ETAPE_RECOLTE: "Semis → première récolte",
    ETAPE_REPIQUAGE: "Semis → repiquage",
    ETAPE_PLANTATION_RECOLTE: "Plantation → première récolte",
}

#: ⚠️ « plantation » seul reste l'alias de `repiquage` (semis → plantation en
#: place) : c'est le mot qu'un jardinier emploie pour « dans combien de temps
#: est-ce que je plante ». L'étape d'US-177 exige les DEUX bornes — la
#: désambiguïsation est portée par le libellé saisi, jamais par un défaut.
_ALIAS_ETAPES: dict[str, str] = {
    "levee": ETAPE_LEVEE, "germination": ETAPE_LEVEE,
    "recolte": ETAPE_RECOLTE, "maturite": ETAPE_RECOLTE,
    "repiquage": ETAPE_REPIQUAGE, "plantation": ETAPE_REPIQUAGE,
    "plantation_recolte": ETAPE_PLANTATION_RECOLTE,
    "plantation_premiere_recolte": ETAPE_PLANTATION_RECOLTE,
    "plantation_maturite": ETAPE_PLANTATION_RECOLTE,
    "plant_recolte": ETAPE_PLANTATION_RECOLTE,
}

#: [CA1] Nom de l'itinéraire implicite — celui d'une culture sans itinéraire
#: nommé, et celui que vise une correction qui n'en nomme aucun.
ITINERAIRE_PAR_DEFAUT = "standard"

#: [CA4] Bornes de vraisemblance d'une durée. Elles écartent la faute de frappe
#: (« 9000 » jours), pas l'absence de source : l'ail d'automne dépasse 250 jours.
DUREE_MIN_JOURS = 1
DUREE_MAX_JOURS = 730
LONGUEUR_MAX_MENTION = 60

#: [CA13] Ce qu'affiche une durée absente — un tiret, jamais une estimation.
TIRET = "—"

#: Mots qui effacent une fenêtre ou une durée au bot.
_MOTS_EFFACEMENT = frozenset({"aucune", "aucun", "rien", "vide", "effacer", "-", TIRET})

MOIS: tuple[str, ...] = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)

_ALIAS_MOIS: dict[str, int] = {}
for _numero, _nom in enumerate(MOIS, start=1):
    _ALIAS_MOIS[unidecode(_nom)] = _numero
    _ALIAS_MOIS[str(_numero)] = _numero
    _ALIAS_MOIS[f"{_numero:02d}"] = _numero
#: Abréviations usuelles. « jui » est volontairement absent : juin ou juillet,
#: une abréviation ambiguë se refuse plutôt qu'elle ne se devine.
_ALIAS_MOIS.update({
    "janv": 1, "jan": 1, "fev": 2, "fevr": 2, "avr": 4, "juil": 7, "juill": 7,
    "aou": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
})


# ═════════════════════════════════════════════════════════════════════════════
# Normalisation — casse, accents et séparateurs indifférents (CA12)
# ═════════════════════════════════════════════════════════════════════════════
def _cle(texte: str) -> str:
    """Casse, accents, apostrophes typographiques et espaces multiples indifférents."""
    brut = unidecode((texte or "").replace("’", "'")).strip().lower()
    return " ".join(brut.split())


def normaliser_itineraire(nom: Optional[str]) -> str:
    """Clé de comparaison d'un nom d'itinéraire — « Culture d’Hiver » = « culture d'hiver »."""
    return _cle(nom or ITINERAIRE_PAR_DEFAUT) or ITINERAIRE_PAR_DEFAUT


def _resoudre(valeur: str, alias: dict[str, str], libelle: str, admis: Iterable[str]) -> str:
    cle = _cle(valeur).replace(" ", "_").replace("-", "_")
    trouve = alias.get(cle) or alias.get(cle.replace("_", ""))
    if trouve is None:
        raise ValeurCalendrierInvalideError(
            f"« {valeur} » n'est pas {libelle} connu(e). Valeurs possibles : {', '.join(admis)}."
        )
    return trouve


def normaliser_zone(valeur: str) -> str:
    """[CA6] Valeur canonique d'une zone climatique, ou refus."""
    return _resoudre(valeur, _ALIAS_ZONES, "une zone climatique", LIBELLES_ZONES.values())


def normaliser_phase(valeur: str) -> str:
    """[CA2] Phase canonique d'une fenêtre, ou refus."""
    return _resoudre(
        valeur, _ALIAS_PHASES, "une phase", ("pepiniere", "pleine_terre", "plantation", "recolte")
    )


def normaliser_etape(valeur: str) -> str:
    """[CA3] Étape canonique d'une durée, ou refus."""
    return _resoudre(valeur, _ALIAS_ETAPES, "une étape", ETAPES)


def est_phase(valeur: str) -> bool:
    try:
        normaliser_phase(valeur)
    except ValeurCalendrierInvalideError:
        return False
    return True


def est_etape(valeur: str) -> bool:
    try:
        normaliser_etape(valeur)
    except ValeurCalendrierInvalideError:
        return False
    return True


# ═════════════════════════════════════════════════════════════════════════════
# Zone climatique d'un potager (CA6, CA7, CA8)
# ═════════════════════════════════════════════════════════════════════════════
def zone_par_defaut() -> str:
    """[CA8] Zone lue par un potager sans choix ni localisation exploitable."""
    from app.config import CALENDRIER_ZONE_DEFAUT

    zone = _ALIAS_ZONES.get(_cle(CALENDRIER_ZONE_DEFAUT))
    if zone is None:
        log.warning(
            "[US-068] CALENDRIER_ZONE_DEFAUT=%r hors vocabulaire — repli sur %s",
            CALENDRIER_ZONE_DEFAUT, _ZONE_DEFAUT_SECOURS,
        )
        return _ZONE_DEFAUT_SECOURS
    return zone


def zone_depuis_localisation(latitude: Optional[float], longitude: Optional[float]) -> Optional[str]:
    """
    [CA7] Pré-positionne une zone à partir des coordonnées d'un potager.

    Une règle volontairement GROSSIÈRE et déclarée comme telle : elle donne un
    point de départ, le jardinier corrige — c'est lui qui connaît son
    microclimat, et un fond de vallée n'a pas le calendrier du plateau voisin.

    - hors de la France métropolitaine (Corse comprise) → None : aucune
      supposition, le potager lit la zone par défaut ;
    - arc méditerranéen et Corse : sud du 44,3ᵉ parallèle, à l'est du méridien
      2,8° E (Roussillon, Languedoc, Provence, Côte d'Azur) ;
    - quart nord-est : au nord du 45ᵉ parallèle, à l'est du méridien 4,5° E
      (Rhône-Alpes du nord, Bourgogne, Franche-Comté, Lorraine, Alsace) ;
    - océanique partout ailleurs.

    `montagnard` n'est JAMAIS déduit : il dépend de l'altitude, que les
    coordonnées seules ne donnent pas. Le déduire de la longitude placerait
    Grenoble et Chamonix dans la même case — mieux vaut ne rien supposer et
    laisser le jardinier le choisir.
    """
    if latitude is None or longitude is None:
        return None
    if not (41.0 <= latitude <= 51.5 and -5.5 <= longitude <= 10.0):
        return None
    if latitude < 44.3 and longitude >= 2.8:
        return "mediterraneen"
    if latitude >= 45.0 and longitude >= 4.5:
        return "continental"
    return "oceanique"


def zone_effective(potager: Optional[Potager]) -> tuple[str, str]:
    """
    [CA7, CA8] La zone qu'un potager lit, et d'où elle vient.

    Retourne (zone, origine) — origine ∈ {jardinier, localisation, defaut}. Ne
    lève jamais : un potager sans zone reste pleinement fonctionnel (CA8).
    """
    if potager is not None:
        choisie = _ALIAS_ZONES.get(_cle(potager.zone_climatique or ""))
        if choisie is not None:
            return choisie, ORIGINE_ZONE_JARDINIER
        deduite = zone_depuis_localisation(potager.latitude, potager.longitude)
        if deduite is not None:
            return deduite, ORIGINE_ZONE_LOCALISATION
    return zone_par_defaut(), ORIGINE_ZONE_DEFAUT


def zone_du_potager(db: Session, potager_id: Optional[int]) -> tuple[str, str]:
    """[CA8] `zone_effective` à partir d'un identifiant — potager absent compris."""
    potager = (
        db.query(Potager).filter(Potager.id == potager_id).first()
        if potager_id is not None else None
    )
    return zone_effective(potager)


def definir_zone(
    db: Session, ctx: TenantContext, valeur: Optional[str]
) -> tuple[tuple[str, str], tuple[str, str]]:
    """
    [CA7] Le jardinier choisit la zone de son potager — ou rend la main à la
    localisation avec une valeur vide (`None`, « auto »).

    Réservé au propriétaire : c'est un réglage du lieu, au même titre que sa
    localisation (US-074/CA4). Refusé sur un potager archivé (US-083).

    Retourne ((zone, origine) avant, (zone, origine) après).
    """
    canonique: Optional[str] = None
    if valeur is not None and _cle(valeur) not in ("", "auto", "automatique"):
        canonique = normaliser_zone(valeur)

    require_role(ctx, "owner", "changer la zone climatique du potager")
    require_potager_non_archive(db, ctx, "changer la zone climatique du potager")

    potager = db.query(Potager).filter(Potager.id == ctx.potager_id).first()
    if potager is None:
        raise LookupError(ctx.potager_id)
    avant = zone_effective(potager)
    potager.zone_climatique = canonique
    db.commit()
    apres = zone_effective(potager)
    log.info(
        "[US-068] Zone climatique : potager_id=%s %s (%s) → %s (%s) par user_id=%s",
        ctx.potager_id, avant[0], avant[1], apres[0], apres[1], ctx.user_id,
    )
    return avant, apres


def libelle_zone(zone: str, origine: Optional[str] = None) -> str:
    """Libellé affichable d'une zone, avec son origine quand elle n'est pas choisie."""
    libelle = LIBELLES_ZONES.get(zone, zone)
    if origine == ORIGINE_ZONE_LOCALISATION:
        return f"{libelle} (déduite de la localisation)"
    if origine == ORIGINE_ZONE_DEFAUT:
        return f"{libelle} (zone par défaut)"
    return libelle


# ═════════════════════════════════════════════════════════════════════════════
# Fenêtres (CA2) et durées (CA3, CA4) : lecture et écriture des valeurs
# ═════════════════════════════════════════════════════════════════════════════
def _mois(jeton: str) -> int:
    numero = _ALIAS_MOIS.get(_cle(jeton).rstrip("."))
    if numero is None:
        raise ValeurCalendrierInvalideError(
            f"« {jeton} » n'est pas un mois (janvier…décembre, ou 1…12)."
        )
    return numero


def parser_fenetre(valeur) -> Optional[tuple[int, int]]:
    """
    [CA2] « mars-mai », « mars à mai », « novembre → février », « juin », [3, 5]
    → (mois_debut, mois_fin). « aucune » → None (fenêtre vide).

    Une fenêtre peut chevaucher la fin d'année : (11, 2) est légitime.
    """
    if valeur is None:
        return None
    if isinstance(valeur, (list, tuple)):
        if len(valeur) != 2:
            raise ValeurCalendrierInvalideError("Une fenêtre se donne par deux mois : début et fin.")
        return _mois(str(valeur[0])), _mois(str(valeur[1]))
    texte = _cle(str(valeur))
    if not texte or texte in _MOTS_EFFACEMENT:
        return None
    # L'espace sépare aussi : c'est la forme que produit une phrase dictée
    # (« février avril »), les deux mois y arrivant en deux arguments.
    morceaux = [m for m in re.split(r"\s*(?:->|→|-|/|\ba\b|\bau\b|\bjusqu'?a\b)\s*|\s+", texte) if m]
    if len(morceaux) == 1:
        mois = _mois(morceaux[0])
        return mois, mois
    if len(morceaux) != 2:
        raise ValeurCalendrierInvalideError(
            f"« {valeur} » : une fenêtre s'écrit « mars-mai » (ou « aucune » pour la vider)."
        )
    return _mois(morceaux[0]), _mois(morceaux[1])


def mois_couverts(mois_debut: int, mois_fin: int) -> list[int]:
    """Mois d'une fenêtre, bornes incluses, fin d'année chevauchée comprise."""
    if mois_debut <= mois_fin:
        return list(range(mois_debut, mois_fin + 1))
    return list(range(mois_debut, 13)) + list(range(1, mois_fin + 1))


def formater_fenetre(mois_debut: Optional[int], mois_fin: Optional[int]) -> str:
    """« mars → mai », « juin », ou « aucune » pour une fenêtre vide."""
    if mois_debut is None or mois_fin is None:
        return "aucune"
    if mois_debut == mois_fin:
        return MOIS[mois_debut - 1]
    return f"{MOIS[mois_debut - 1]} → {MOIS[mois_fin - 1]}"


def parser_duree(valeur) -> Optional[tuple[Optional[int], Optional[int], Optional[str]]]:
    """
    [CA4] « 10 », « 70-90 », « 70 à 90 jours », [70, 90] → (70, 90, None) ;
    « vivace » → (None, None, "vivace") ; « aucune », None → None (effacement).

    Refuse une fourchette inversée ou hors du vraisemblable : `ValeurCalendrierInvalideError`.
    """
    if valeur is None:
        return None
    if isinstance(valeur, bool):
        raise ValeurCalendrierInvalideError("Une durée attend un nombre de jours.")
    if isinstance(valeur, (int, float)):
        bornes = [int(valeur)]
    elif isinstance(valeur, (list, tuple)):
        bornes = [int(v) for v in valeur]
    else:
        texte = _cle(str(valeur))
        if not texte or texte in _MOTS_EFFACEMENT:
            return None
        nombres = re.findall(r"\d+", texte)
        reste = re.sub(r"\d+|jours?|j\b|environ|[-→>/]|\ba\b|\bau\b|\s", "", texte)
        if not nombres:
            mention = str(valeur).strip()
            # « trois semaines » n'est pas une mention : c'est une durée mal
            # écrite, qu'accepter en texte rendrait illisible pour US-070.
            if re.search(r"\b(?:jours?|semaines?|mois|ans?|annees?)\b", texte):
                raise ValeurCalendrierInvalideError(
                    f"« {valeur} » : une durée s'écrit en nombre de jours (« 21 », « 14-21 »)."
                )
            if len(mention) > LONGUEUR_MAX_MENTION:
                raise ValeurCalendrierInvalideError(
                    f"Mention trop longue ({len(mention)} caractères, {LONGUEUR_MAX_MENTION} au plus)."
                )
            return None, None, mention
        if reste or len(nombres) > 2:
            raise ValeurCalendrierInvalideError(
                f"« {valeur} » : une durée s'écrit « 10 », « 70-90 », ou une mention comme « vivace »."
            )
        bornes = [int(n) for n in nombres]

    if len(bornes) not in (1, 2):
        raise ValeurCalendrierInvalideError("Une durée est un nombre de jours ou une fourchette.")
    jours_min, jours_max = bornes[0], bornes[-1]
    if jours_min > jours_max:
        raise ValeurCalendrierInvalideError(
            f"Fourchette inversée : {jours_min} à {jours_max} jours."
        )
    if jours_min < DUREE_MIN_JOURS or jours_max > DUREE_MAX_JOURS:
        raise ValeurCalendrierInvalideError(
            f"Durée hors du vraisemblable (entre {DUREE_MIN_JOURS} et {DUREE_MAX_JOURS} jours)."
        )
    return jours_min, jours_max, None


def formater_duree(
    jours_min: Optional[int], jours_max: Optional[int], mention: Optional[str] = None
) -> str:
    """
    [CA4, CA13] « 70 à 90 jours », « 10 jours », « vivace », ou « — ».

    Jamais une date : une durée conseillée est un ordre de grandeur, et
    l'afficher comme « récolte le 16 juillet » serait promettre ce que la
    plante ne tiendra pas.
    """
    if mention:
        return mention
    if jours_min is None:
        return TIRET
    if jours_max is None or jours_max == jours_min:
        return f"{jours_min} jour{'s' if jours_min > 1 else ''}"
    return f"{jours_min} à {jours_max} jours"


# ═════════════════════════════════════════════════════════════════════════════
# Lecture (CA1, CA2, CA3, CA6, CA8, CA12, CA13)
# ═════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class FenetreLue:
    phase: str
    libelle: str
    mois_debut: int
    mois_fin: int
    affichage: str
    attribution: Optional[str]

    @property
    def mois(self) -> list[int]:
        return mois_couverts(self.mois_debut, self.mois_fin)


@dataclass(frozen=True)
class DureeLue:
    etape: str
    libelle: str
    jours_min: Optional[int]
    jours_max: Optional[int]
    mention: Optional[str]
    affichage: str
    attribution: Optional[str]

    @property
    def renseignee(self) -> bool:
        return self.jours_min is not None or bool(self.mention)


@dataclass(frozen=True)
class ItineraireLu:
    nom: str
    #: [CA11] Calendrier propre à ce potager (une correction y a eu lieu).
    personnalise: bool
    #: [CA1] Itinéraire par défaut, sans aucune ligne en base.
    implicite: bool
    #: [CA2] Fenêtres RENSEIGNÉES pour la zone lue, dans l'ordre des phases.
    fenetres: list[FenetreLue]
    #: [CA3] Levée et récolte toujours présentes (« — » si absentes) ; repiquage
    #: seulement pour un itinéraire passant par la pépinière.
    durees: list[DureeLue]
    #: Zones pour lesquelles au moins une fenêtre existe — pour dire au
    #: jardinier « renseigné pour une autre zone » sans rien lui emprunter.
    zones_renseignees: list[str]

    def fenetre(self, phase: str) -> Optional[FenetreLue]:
        return next((f for f in self.fenetres if f.phase == phase), None)

    def duree(self, etape: str) -> Optional[DureeLue]:
        return next((d for d in self.durees if d.etape == etape), None)

    def frise(self) -> dict[int, list[str]]:
        """[CA13] Mois 1..12 → phases conseillées. Un mois vide reste vide :
        c'est la frise neutre, jamais une période inventée."""
        frise: dict[int, list[str]] = {m: [] for m in range(1, 13)}
        for fenetre in self.fenetres:
            for mois in fenetre.mois:
                frise[mois].append(fenetre.phase)
        return frise


@dataclass(frozen=True)
class Calendrier:
    culture: str
    #: False : aucune fiche `culture_config` — la culture reste utilisable
    #: partout, le calendrier est simplement vide (CA13, CA14).
    culture_connue: bool
    zone: str
    zone_origine: str
    itineraires: list[ItineraireLu] = field(default_factory=list)

    @property
    def renseigne(self) -> bool:
        """Au moins une fenêtre pour la zone lue, ou au moins une durée."""
        return any(
            it.fenetres or any(d.renseignee for d in it.durees)
            for it in self.itineraires
        )

    @property
    def attributions(self) -> list[str]:
        vues: list[str] = []
        for it in self.itineraires:
            for valeur in (*it.fenetres, *it.durees):
                if valeur.attribution and valeur.attribution not in vues:
                    vues.append(valeur.attribution)
        return vues


def fiches_visibles(db: Session, culture: str, potager_id: Optional[int]) -> list[CultureConfig]:
    """[CA12] Fiches `culture_config` de cette culture visibles du potager —
    partagées, ou personnalisées pour lui ; jamais celles d'un autre potager."""
    cible = normaliser_culture(culture)
    requete = db.query(CultureConfig)
    if potager_id is not None:
        requete = requete.filter(
            or_(CultureConfig.potager_id.is_(None), CultureConfig.potager_id == potager_id)
        )
    else:
        requete = requete.filter(CultureConfig.potager_id.is_(None))
    toutes = requete.all()
    fiches = [c for c in toutes if normaliser_culture(c.nom) == cible]
    if not fiches:
        # « les tomates » dicté : le pluriel régulier se ramène au singulier,
        # mot par mot — un rapprochement ÉCRIT, pas une ressemblance devinée.
        singulier = " ".join(re.sub(r"(?<=[a-z])[sx]$", "", mot) for mot in cible.split())
        fiches = [c for c in toutes if normaliser_culture(c.nom) == singulier]
    # Partagée d'abord : c'est à elle qu'un itinéraire personnalisé se rattache.
    return sorted(fiches, key=lambda c: (c.potager_id is not None, c.id))


def itineraires_visibles(
    db: Session, fiches: list[CultureConfig], potager_id: Optional[int]
) -> dict[str, ItineraireCultural]:
    """
    [CA11] Itinéraires lus par un potager, par nom normalisé : le personnalisé
    REMPLACE le partagé de même nom, pour ce potager seulement.
    """
    if not fiches:
        return {}
    requete = db.query(ItineraireCultural).filter(
        ItineraireCultural.culture_id.in_([f.id for f in fiches])
    )
    if potager_id is not None:
        requete = requete.filter(
            or_(ItineraireCultural.potager_id.is_(None), ItineraireCultural.potager_id == potager_id)
        )
    else:
        requete = requete.filter(ItineraireCultural.potager_id.is_(None))
    retenus: dict[str, ItineraireCultural] = {}
    for itineraire in requete.order_by(ItineraireCultural.id).all():
        deja = retenus.get(itineraire.nom_normalise)
        if deja is None or (deja.potager_id is None and itineraire.potager_id is not None):
            retenus[itineraire.nom_normalise] = itineraire
    return retenus


def _attributions(db: Session, source_ids: Iterable[Optional[int]]) -> dict[int, str]:
    ids = {i for i in source_ids if i is not None}
    if not ids:
        return {}
    return {
        s.id: (svc_sources.attribution_affichee(db, s.code) or s.attribution)
        for s in db.query(ReferentielSource).filter(ReferentielSource.id.in_(ids)).all()
    }


def _passe_par_pepiniere(fenetres: list[FenetreCulturale], durees: list[DureeCulturale]) -> bool:
    """[CA3] Un itinéraire passe par la pépinière s'il a une fenêtre de semis en
    pépinière (dans une zone quelconque) ou une durée de repiquage renseignée."""
    return any(f.phase == PHASE_SEMIS_PEPINIERE for f in fenetres) or any(
        d.etape == ETAPE_REPIQUAGE and (d.jours_min is not None or d.mention) for d in durees
    )


def _se_plante(fenetres: list[FenetreCulturale], durees: list[DureeCulturale]) -> bool:
    """
    [US-177 / CA3] Un itinéraire se plante s'il a une fenêtre de plantation (dans
    une zone quelconque) ou une durée plantation → récolte renseignée.

    Symétrique de `_passe_par_pepiniere`, et indépendante d'elle : l'ail et la
    fraise se plantent sans jamais passer par la pépinière, la laitue semée en
    place ne se plante pas — l'étape ne leur est donc pas proposée du tout,
    plutôt que proposée vide.
    """
    return any(f.phase == PHASE_PLANTATION for f in fenetres) or any(
        d.etape == ETAPE_PLANTATION_RECOLTE and (d.jours_min is not None or d.mention)
        for d in durees
    )


def _ordre_itineraire(nom_normalise: str) -> tuple[int, str]:
    return (0 if nom_normalise == ITINERAIRE_PAR_DEFAUT else 1, nom_normalise)


def lire_calendrier(db: Session, culture: str, potager_id: Optional[int]) -> Calendrier:
    """
    [CA1-CA4, CA6, CA8, CA12, CA13] Calendrier d'une culture tel que le lit un
    potager — zéro jeton, zéro écriture, ne lève jamais pour une donnée absente.

    - la zone est celle du potager, ou la zone par défaut (CA8) ;
    - un itinéraire personnalisé remplace le partagé de même nom (CA11) ;
    - seules les fenêtres RENSEIGNÉES pour cette zone sont restituées : aucune
      n'est empruntée à une autre zone (CA13) ;
    - une culture sans itinéraire en porte un implicite, « standard », vide (CA1).
    """
    zone, origine = zone_du_potager(db, potager_id)
    fiches = fiches_visibles(db, culture, potager_id)
    if not fiches:
        return Calendrier(culture=culture, culture_connue=False, zone=zone, zone_origine=origine)

    retenus = itineraires_visibles(db, fiches, potager_id)
    ids = [it.id for it in retenus.values()]
    fenetres_par_it: dict[int, list[FenetreCulturale]] = {i: [] for i in ids}
    durees_par_it: dict[int, list[DureeCulturale]] = {i: [] for i in ids}
    if ids:
        for f in db.query(FenetreCulturale).filter(FenetreCulturale.itineraire_id.in_(ids)).all():
            fenetres_par_it[f.itineraire_id].append(f)
        for d in db.query(DureeCulturale).filter(DureeCulturale.itineraire_id.in_(ids)).all():
            durees_par_it[d.itineraire_id].append(d)
    attributions = _attributions(
        db,
        [f.source_id for lst in fenetres_par_it.values() for f in lst]
        + [d.source_id for lst in durees_par_it.values() for d in lst],
    )

    lus: list[ItineraireLu] = []
    for nom_normalise in sorted(retenus, key=_ordre_itineraire):
        it = retenus[nom_normalise]
        fenetres = fenetres_par_it[it.id]
        durees = {d.etape: d for d in durees_par_it[it.id]}
        fenetres_zone = {f.phase: f for f in fenetres if f.zone_climatique == zone}
        etapes = [ETAPE_LEVEE, ETAPE_RECOLTE]
        if _passe_par_pepiniere(fenetres, list(durees.values())):
            etapes.append(ETAPE_REPIQUAGE)
        # [US-177 / CA3, CA6] Servie seulement pour ce qui se plante — omise,
        # jamais affichée vide, pour une culture semée en place.
        if _se_plante(fenetres, list(durees.values())):
            etapes.append(ETAPE_PLANTATION_RECOLTE)
        lus.append(ItineraireLu(
            nom=it.nom,
            personnalise=it.potager_id is not None,
            implicite=False,
            fenetres=[
                FenetreLue(
                    phase=phase,
                    libelle=LIBELLES_PHASES[phase],
                    mois_debut=fenetres_zone[phase].mois_debut,
                    mois_fin=fenetres_zone[phase].mois_fin,
                    affichage=formater_fenetre(fenetres_zone[phase].mois_debut, fenetres_zone[phase].mois_fin),
                    attribution=attributions.get(fenetres_zone[phase].source_id),
                )
                for phase in PHASES if phase in fenetres_zone
            ],
            durees=[
                DureeLue(
                    etape=etape,
                    libelle=LIBELLES_ETAPES[etape],
                    jours_min=durees[etape].jours_min if etape in durees else None,
                    jours_max=durees[etape].jours_max if etape in durees else None,
                    mention=durees[etape].mention if etape in durees else None,
                    affichage=(
                        formater_duree(durees[etape].jours_min, durees[etape].jours_max, durees[etape].mention)
                        if etape in durees else TIRET
                    ),
                    attribution=attributions.get(durees[etape].source_id) if etape in durees else None,
                )
                for etape in etapes
            ],
            zones_renseignees=[z for z in ZONES_CLIMATIQUES if any(f.zone_climatique == z for f in fenetres)],
        ))

    if not lus:
        lus.append(_itineraire_implicite())
    return Calendrier(
        culture=culture, culture_connue=True, zone=zone, zone_origine=origine, itineraires=lus,
    )


def _itineraire_implicite() -> ItineraireLu:
    """[CA1, CA13] L'itinéraire par défaut d'une culture sans référentiel : frise
    neutre, durées en tiret — aucune saisie exigée du jardinier."""
    return ItineraireLu(
        nom=ITINERAIRE_PAR_DEFAUT,
        personnalise=False,
        implicite=True,
        fenetres=[],
        durees=[
            DureeLue(etape, LIBELLES_ETAPES[etape], None, None, None, TIRET, None)
            for etape in (ETAPE_LEVEE, ETAPE_RECOLTE)
        ],
        zones_renseignees=[],
    )


def calendrier_en_dict(calendrier: Calendrier) -> dict:
    """Forme sérialisable — celle que servent l'API et que liront US-060/US-070."""
    return {
        "culture": calendrier.culture,
        "culture_connue": calendrier.culture_connue,
        "zone_climatique": calendrier.zone,
        "zone_climatique_origine": calendrier.zone_origine,
        "renseigne": calendrier.renseigne,
        "itineraires": [
            {
                "nom": it.nom,
                "personnalise": it.personnalise,
                "implicite": it.implicite,
                "fenetres": [
                    {"phase": f.phase, "mois_debut": f.mois_debut, "mois_fin": f.mois_fin,
                     "mois": f.mois, "affichage": f.affichage}
                    for f in it.fenetres
                ],
                # [CA4] jours_min/jours_max, jamais une date calculée.
                "durees": [
                    {"etape": d.etape, "jours_min": d.jours_min, "jours_max": d.jours_max,
                     "mention": d.mention, "affichage": d.affichage}
                    for d in it.durees
                ],
                "frise": {str(m): phases for m, phases in it.frise().items()},
                "zones_renseignees": it.zones_renseignees,
            }
            for it in calendrier.itineraires
        ],
        "attributions": calendrier.attributions,
    }


def calendriers_du_plan(db: Session, cultures: Iterable[str], potager_id: Optional[int]) -> dict:
    """
    [US-176 / CA1-CA9, CA11] Calendrier conseillé de TOUTES les cultures d'un
    écran Plan, en une seule lecture groupée — jamais une requête par tuile.

    Pour chaque culture, une seule frise : celle de l'itinéraire par défaut du
    référentiel (« standard » en tête, cf. `_ordre_itineraire`), jamais une
    fusion de plusieurs itinéraires (CA5). La durée servie est celle de l'étape
    `recolte` — semis → première récolte — dans sa forme de lecture, tiret
    compris (CA4). La plantation est servie comme toute phase du référentiel
    (US-068 / CA20, amendement du 15/09/2026) — LUE, jamais reconstituée ici
    depuis le semis en pépinière et le délai de repiquage (CA3 amendé).

    Zone, origine et attributions sont rendues UNE fois pour l'ensemble (CA8,
    CA9) ; les attributions ne portent que sur les valeurs réellement affichées.
    La clé de `cultures` est le nom tel que demandé : l'écran le retrouve sans
    renormaliser.
    """
    zone, origine = zone_du_potager(db, potager_id)
    attributions: list[str] = []
    resultat: dict[str, dict] = {}
    for nom in dict.fromkeys(c for c in cultures if c and c.strip()):
        calendrier = lire_calendrier(db, nom, potager_id)
        it = calendrier.itineraires[0] if calendrier.itineraires else None
        if it is None:
            resultat[nom] = {
                "culture_connue": calendrier.culture_connue, "renseigne": False,
                "itineraire": None, "itineraire_standard": True,
                "mois": {phase: [] for phase in PHASES}, "duree_recolte": TIRET,
            }
            continue
        duree = it.duree(ETAPE_RECOLTE)
        for valeur in (*it.fenetres, duree):
            if valeur is not None and valeur.attribution and valeur.attribution not in attributions:
                attributions.append(valeur.attribution)
        resultat[nom] = {
            "culture_connue": calendrier.culture_connue,
            "renseigne": bool(it.fenetres) or bool(duree and duree.renseignee),
            "itineraire": it.nom,
            "itineraire_standard": normaliser_itineraire(it.nom) == ITINERAIRE_PAR_DEFAUT,
            # Mois 1..12 par phase, fenêtre à cheval sur l'année comprise.
            "mois": {phase: (it.fenetre(phase).mois if it.fenetre(phase) else []) for phase in PHASES},
            "duree_recolte": duree.affichage if duree else TIRET,
        }
    log.info("[US-176] Calendriers du plan : potager_id=%s zone=%s (%s) cultures=%d",
             potager_id, zone, origine, len(resultat))
    return {
        "zone_climatique": zone,
        "zone_climatique_origine": origine,
        "zone_libelle": libelle_zone(zone, origine),
        "attributions": attributions,
        "cultures": resultat,
    }


# ═════════════════════════════════════════════════════════════════════════════
# Correction depuis le bot — locale au potager (CA10, CA11)
# ═════════════════════════════════════════════════════════════════════════════
def separer_culture_itineraire(
    db: Session, jetons: list[str], potager_id: Optional[int]
) -> tuple[str, str]:
    """
    Sépare « chou-fleur culture d'hiver » en (« chou-fleur », « culture d'hiver »).

    La culture est le PLUS LONG préfixe de jetons qui désigne une fiche connue
    (« petit pois » avant « petit ») ; le reste nomme l'itinéraire, ou
    « standard » s'il est vide. Sans aucune fiche reconnue, tous les jetons
    forment la culture — la correction échouera ensuite sur culture inconnue,
    avec le nom tel que tapé.
    """
    for longueur in range(len(jetons), 0, -1):
        candidat = " ".join(jetons[:longueur])
        if fiches_visibles(db, candidat, potager_id):
            reste = " ".join(jetons[longueur:]).strip()
            return candidat, reste or ITINERAIRE_PAR_DEFAUT
    return " ".join(jetons), ITINERAIRE_PAR_DEFAUT


def _itineraire_personnalise(
    db: Session, potager_id: int, culture: str, nom_itineraire: str
) -> ItineraireCultural:
    """
    [CA11] L'itinéraire personnalisé du potager, créé à la première correction.

    S'il existe un itinéraire partagé de même nom, il est COPIÉ — fenêtres de
    toutes les zones et durées, chacune avec son origine d'import : le potager
    part du référentiel et n'en modifie que ce qu'il corrige. Sinon, un
    itinéraire vide naît, d'origine `saisie_manuelle`.
    """
    fiches = fiches_visibles(db, culture, potager_id)
    if not fiches:
        raise CultureInconnueError(culture)
    cle = normaliser_itineraire(nom_itineraire)
    ids = [f.id for f in fiches]

    local = (
        db.query(ItineraireCultural)
        .filter(
            ItineraireCultural.culture_id.in_(ids),
            ItineraireCultural.nom_normalise == cle,
            ItineraireCultural.potager_id == potager_id,
        )
        .first()
    )
    if local is not None:
        return local

    origine = svc_sources.garantir_source(db, svc_sources.SOURCE_SAISIE_MANUELLE).id
    partage = (
        db.query(ItineraireCultural)
        .filter(
            ItineraireCultural.culture_id.in_(ids),
            ItineraireCultural.nom_normalise == cle,
            ItineraireCultural.potager_id.is_(None),
        )
        .first()
    )
    local = ItineraireCultural(
        culture_id=partage.culture_id if partage is not None else fiches[0].id,
        nom=partage.nom if partage is not None else (nom_itineraire.strip() or ITINERAIRE_PAR_DEFAUT),
        nom_normalise=cle,
        potager_id=potager_id,
        source_id=origine,
    )
    db.add(local)
    db.flush()
    if partage is not None:
        for f in db.query(FenetreCulturale).filter(FenetreCulturale.itineraire_id == partage.id).all():
            db.add(FenetreCulturale(
                itineraire_id=local.id, zone_climatique=f.zone_climatique, phase=f.phase,
                mois_debut=f.mois_debut, mois_fin=f.mois_fin, potager_id=potager_id,
                source_id=f.source_id,
            ))
        for d in db.query(DureeCulturale).filter(DureeCulturale.itineraire_id == partage.id).all():
            db.add(DureeCulturale(
                itineraire_id=local.id, etape=d.etape, jours_min=d.jours_min,
                jours_max=d.jours_max, mention=d.mention, potager_id=potager_id,
                source_id=d.source_id,
            ))
        db.flush()
    log.info(
        "[US-068] Calendrier personnalisé créé : '%s' / '%s' potager_id=%s (%s)",
        culture, local.nom, potager_id, "copie du partagé" if partage is not None else "vide",
    )
    return local


def _verifier_ecriture(db: Session, ctx: TenantContext, action: str) -> None:
    require_role(ctx, "editor", action)
    require_potager_non_archive(db, ctx, action)


def corriger_fenetre(
    db: Session,
    ctx: TenantContext,
    culture: str,
    phase: str,
    valeur,
    itineraire: str = ITINERAIRE_PAR_DEFAUT,
) -> tuple[str, str, str]:
    """
    [CA10, CA11] Corrige une fenêtre, pour la zone du potager et pour lui seul.

    La valeur est validée AVANT toute écriture : une saisie refusée ne touche à
    rien. « aucune » vide la fenêtre — dans le calendrier personnalisé, cela
    vaut « pas de fenêtre ici », sans retomber sur celle du partagé.

    Retourne (zone lue, affichage avant, affichage après).
    """
    phase = normaliser_phase(phase)
    bornes = parser_fenetre(valeur)
    _verifier_ecriture(db, ctx, "corriger le calendrier d'une culture")

    zone, _ = zone_du_potager(db, ctx.potager_id)
    avant = lire_calendrier(db, culture, ctx.potager_id)
    if not avant.culture_connue:
        raise CultureInconnueError(culture)
    cle = normaliser_itineraire(itineraire)
    it_avant = next((it for it in avant.itineraires if normaliser_itineraire(it.nom) == cle and not it.implicite), None)
    fenetre_avant = it_avant.fenetre(phase) if it_avant is not None else None
    affichage_avant = fenetre_avant.affichage if fenetre_avant is not None else "aucune"

    local = _itineraire_personnalise(db, ctx.potager_id, culture, itineraire)
    ligne = (
        db.query(FenetreCulturale)
        .filter(
            FenetreCulturale.itineraire_id == local.id,
            FenetreCulturale.zone_climatique == zone,
            FenetreCulturale.phase == phase,
        )
        .first()
    )
    if bornes is None:
        if ligne is not None:
            db.delete(ligne)
    else:
        origine = svc_sources.garantir_source(db, svc_sources.SOURCE_SAISIE_MANUELLE).id
        if ligne is None:
            ligne = FenetreCulturale(
                itineraire_id=local.id, zone_climatique=zone, phase=phase,
                potager_id=ctx.potager_id, mois_debut=bornes[0], mois_fin=bornes[1],
                source_id=origine,
            )
            db.add(ligne)
        else:
            ligne.mois_debut, ligne.mois_fin = bornes
            ligne.source_id = origine
    db.commit()

    affichage_apres = formater_fenetre(*bornes) if bornes else "aucune"
    log.info(
        "[US-068] Fenêtre corrigée : '%s' / '%s' %s zone=%s : %s → %s (potager_id=%s)",
        culture, local.nom, phase, zone, affichage_avant, affichage_apres, ctx.potager_id,
    )
    return zone, affichage_avant, affichage_apres


def corriger_duree(
    db: Session,
    ctx: TenantContext,
    culture: str,
    etape: str,
    valeur,
    itineraire: str = ITINERAIRE_PAR_DEFAUT,
) -> tuple[str, str]:
    """
    [CA3, CA4, CA10, CA11] Corrige une durée — commune à toutes les zones, mais
    propre au potager.

    [CA3] Le repiquage est refusé sur un itinéraire qui a des fenêtres et aucune
    en pépinière : une culture semée en place ne se repique pas. [US-177 / CA3]
    Même refus, sur la fenêtre de plantation, pour `plantation_recolte`.

    Retourne (affichage avant, affichage après).
    """
    etape = normaliser_etape(etape)
    valeurs = parser_duree(valeur)
    _verifier_ecriture(db, ctx, "corriger le calendrier d'une culture")

    avant = lire_calendrier(db, culture, ctx.potager_id)
    if not avant.culture_connue:
        raise CultureInconnueError(culture)
    cle = normaliser_itineraire(itineraire)
    it_avant = next((it for it in avant.itineraires if normaliser_itineraire(it.nom) == cle and not it.implicite), None)
    duree_avant = it_avant.duree(etape) if it_avant is not None else None
    affichage_avant = duree_avant.affichage if duree_avant is not None else TIRET

    local = _itineraire_personnalise(db, ctx.potager_id, culture, itineraire)
    if etape in (ETAPE_REPIQUAGE, ETAPE_PLANTATION_RECOLTE) and valeurs is not None:
        fenetres = db.query(FenetreCulturale).filter(FenetreCulturale.itineraire_id == local.id).all()
        # [US-177 / CA3] Même garde que le repiquage, sur l'autre phase : une
        # culture semée en place ne se plante pas, et un itinéraire SANS aucune
        # fenêtre ne préjuge de rien — le jardinier saisit ce qu'il connaît.
        phase_requise, message = (
            (PHASE_SEMIS_PEPINIERE,
             "Cet itinéraire ne passe pas par la pépinière : il n'a pas de délai de "
             "repiquage. Renseignez d'abord une fenêtre de semis en pépinière.")
            if etape == ETAPE_REPIQUAGE else
            (PHASE_PLANTATION,
             "Cet itinéraire ne se plante pas : il n'a pas de délai entre la plantation "
             "et la récolte. Renseignez d'abord une fenêtre de plantation.")
        )
        if fenetres and not any(f.phase == phase_requise for f in fenetres):
            db.rollback()
            raise ValeurCalendrierInvalideError(message)

    ligne = (
        db.query(DureeCulturale)
        .filter(DureeCulturale.itineraire_id == local.id, DureeCulturale.etape == etape)
        .first()
    )
    if valeurs is None:
        if ligne is not None:
            db.delete(ligne)
    else:
        origine = svc_sources.garantir_source(db, svc_sources.SOURCE_SAISIE_MANUELLE).id
        if ligne is None:
            ligne = DureeCulturale(itineraire_id=local.id, etape=etape, potager_id=ctx.potager_id)
            db.add(ligne)
        ligne.jours_min, ligne.jours_max, ligne.mention = valeurs
        ligne.source_id = origine
    db.commit()

    affichage_apres = formater_duree(*valeurs) if valeurs else TIRET
    log.info(
        "[US-068] Durée corrigée : '%s' / '%s' %s : %s → %s (potager_id=%s)",
        culture, local.nom, etape, affichage_avant, affichage_apres, ctx.potager_id,
    )
    return affichage_avant, affichage_apres


# ═════════════════════════════════════════════════════════════════════════════
# Écriture du PARTAGÉ — réservée à l'import du référentiel (CA9)
# ═════════════════════════════════════════════════════════════════════════════
def itineraire_partage(
    db: Session, fiche: CultureConfig, nom: str, source_id: Optional[int]
) -> tuple[ItineraireCultural, bool]:
    """Itinéraire PARTAGÉ d'une fiche, créé s'il manque. Retourne (itinéraire, créé)."""
    cle = normaliser_itineraire(nom)
    existant = (
        db.query(ItineraireCultural)
        .filter(
            ItineraireCultural.culture_id == fiche.id,
            ItineraireCultural.nom_normalise == cle,
            ItineraireCultural.potager_id.is_(None),
        )
        .first()
    )
    if existant is not None:
        return existant, False
    itineraire = ItineraireCultural(
        culture_id=fiche.id, nom=(nom or ITINERAIRE_PAR_DEFAUT).strip(),
        nom_normalise=cle, potager_id=None, source_id=source_id,
    )
    db.add(itineraire)
    db.flush()
    return itineraire, True


def mediane_arrondie(valeurs: list[int]) -> int:
    """Médiane arrondie à l'entier — utilitaire d'agrégation des adaptateurs."""
    return int(round(statistics.median(valeurs)))

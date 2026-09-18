"""
app/services/confiance_semis.py — Moteur de confiance semis / plantation [US-178]
=================================================================================
« Est-ce raisonnable de semer ça, ici, maintenant ? » Le référentiel (US-068) dit
QUAND on peut semer, la projection (US-070) QUAND on récoltera ; aucun des deux ne
répond à celle-là. Ce module rend, pour `(culture, action, date, parcelle)`, un
niveau de **1 à 3 étoiles**, un score 0-100 et la liste des MOTIFS qui l'ont fait
monter ou descendre.

Trois principes, et ils se lisent dans le code :

1. **Déterministe [CA2].** Cinq règles pondérées, aucune passerelle LLM importée
   ici. Même entrée, même sortie, zéro jeton.
2. **Motivé [CA1, CA6].** Chaque règle rend ses points OBTENUS, ses points MAXIMUM
   et un libellé en clair. Un consommateur affiche « pourquoi deux étoiles » sans
   rien recalculer.
3. **Muet plutôt que menteur [CA5].** Une règle dont la donnée manque rapporte 0 et
   se marque `indetermine` — jamais une valeur par défaut, jamais un silence. Une
   culture sans fenêtre pour la zone n'a **pas de score du tout** : un tiret.

⚖️ Ce module CALCULE et EXPOSE ; il n'affiche rien et n'écrit rien [CA11]. Ses
consommateurs sont US-179 (bot) et US-180 (écran Plan).

⚠️ Les pondérations, les seuils d'étoiles et les valeurs climatiques déclarées
ci-dessous sont des **décisions produit corrigeables**, pas des faits mesurés —
elles vivent toutes dans le bloc « Barème » qui suit, et nulle part ailleurs [CA3].
"""
from __future__ import annotations

import calendar
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.services import calendrier_cultural as cal
from app.services import previsions_meteo as svc_previsions
from database.models import CultureConfig, Parcelle, Potager
from utils.meteo import METEO_HORIZON_PREVISION_JOURS

log = logging.getLogger("potager")


# ═════════════════════════════════════════════════════════════════════════════
# Actions et phases (CA4, CA8)
# ═════════════════════════════════════════════════════════════════════════════
ACTION_SEMIS_PEPINIERE = "semis_pepiniere"
ACTION_SEMIS_PLEINE_TERRE = "semis_pleine_terre"
ACTION_PLANTATION = "plantation"
#: Un semis dont la filière n'est pas dite — TRANCHÉ par la parcelle (CA8),
#: jamais deviné ailleurs.
ACTION_SEMIS = "semis"

ACTIONS: tuple[str, ...] = (
    ACTION_SEMIS_PEPINIERE, ACTION_SEMIS_PLEINE_TERRE, ACTION_PLANTATION, ACTION_SEMIS,
)

LIBELLES_ACTIONS: dict[str, str] = {
    ACTION_SEMIS_PEPINIERE: "semis en pépinière",
    ACTION_SEMIS_PLEINE_TERRE: "semis en pleine terre",
    ACTION_PLANTATION: "plantation",
    ACTION_SEMIS: "semis",
}

_ALIAS_ACTIONS: dict[str, str] = {
    "semis_pepiniere": ACTION_SEMIS_PEPINIERE, "pepiniere": ACTION_SEMIS_PEPINIERE,
    "semis pepiniere": ACTION_SEMIS_PEPINIERE, "semis en pepiniere": ACTION_SEMIS_PEPINIERE,
    "godet": ACTION_SEMIS_PEPINIERE, "godets": ACTION_SEMIS_PEPINIERE,
    "semis_pleine_terre": ACTION_SEMIS_PLEINE_TERRE, "pleine_terre": ACTION_SEMIS_PLEINE_TERRE,
    "pleine terre": ACTION_SEMIS_PLEINE_TERRE, "semis pleine terre": ACTION_SEMIS_PLEINE_TERRE,
    "semis en pleine terre": ACTION_SEMIS_PLEINE_TERRE, "en place": ACTION_SEMIS_PLEINE_TERRE,
    "plantation": ACTION_PLANTATION, "planter": ACTION_PLANTATION, "plante": ACTION_PLANTATION,
    "repiquage": ACTION_PLANTATION, "repiquer": ACTION_PLANTATION,
    "semis": ACTION_SEMIS, "semer": ACTION_SEMIS, "seme": ACTION_SEMIS,
}

#: [CA4] L'action détermine la phase lue — et une seule. Une phase absente pour la
#: zone ne se remplace JAMAIS par celle d'une autre phase ni d'une autre zone.
PHASE_PAR_ACTION: dict[str, str] = {
    ACTION_SEMIS_PEPINIERE: cal.PHASE_SEMIS_PEPINIERE,
    ACTION_SEMIS_PLEINE_TERRE: cal.PHASE_SEMIS_PLEINE_TERRE,
    ACTION_PLANTATION: cal.PHASE_PLANTATION,
}

#: Une action en pleine terre expose la plante au gel et aux nuits fraîches ;
#: un semis en pépinière est à l'abri (R2, R3, R4 acquises d'office).
ACTIONS_PLEINE_TERRE: frozenset[str] = frozenset({ACTION_SEMIS_PLEINE_TERRE, ACTION_PLANTATION})


class ActionInvalideError(ValueError):
    """Action inconnue du moteur de confiance."""


def normaliser_action(valeur: Optional[str]) -> str:
    """Ramène « semer », « en pépinière », « plantation »… à une action connue."""
    if valeur is None or not str(valeur).strip():
        return ACTION_SEMIS
    cle = cal._cle(str(valeur)).replace("_", " ").strip()
    resolue = _ALIAS_ACTIONS.get(cle) or _ALIAS_ACTIONS.get(cle.replace(" ", "_"))
    if resolue is None:
        raise ActionInvalideError(
            f"Action inconnue : « {valeur} » (attendu : semis en pépinière, "
            f"semis en pleine terre ou plantation)"
        )
    return resolue


# ═════════════════════════════════════════════════════════════════════════════
# Barème — SEUL endroit où vivent règles, pondérations, seuils et valeurs
# déclarées [CA3]. Toute correction de la grille se fait ici.
# ═════════════════════════════════════════════════════════════════════════════
R1_FENETRE = "R1"
R2_DERNIERE_GELEE = "R2"
R3_GEL_ANNONCE = "R3"
R4_NUITS_DOUCES = "R4"
R5_SAISON_RESTANTE = "R5"

#: Points MAXIMUM de chaque règle — leur somme fait 100.
POINTS_MAX: dict[str, int] = {
    R1_FENETRE: 40,
    R2_DERNIERE_GELEE: 20,
    R3_GEL_ANNONCE: 20,
    R4_NUITS_DOUCES: 10,
    R5_SAISON_RESTANTE: 10,
}

LIBELLES_REGLES: dict[str, str] = {
    R1_FENETRE: "Fenêtre conseillée",
    R2_DERNIERE_GELEE: "Dernière gelée moyenne",
    R3_GEL_ANNONCE: "Gel annoncé",
    R4_NUITS_DOUCES: "Nuits douces",
    R5_SAISON_RESTANTE: "Saison restante",
}

#: Barèmes partiels (une règle peut rapporter moins que son maximum).
POINTS_R1_MOIS_ADJACENT = 20
POINTS_R2_GELEE_TOUT_JUSTE = 10

SCORE_MAXIMUM = sum(POINTS_MAX.values())            # 100
SEUIL_TROIS_ETOILES = 75
SEUIL_DEUX_ETOILES = 45

#: [US-178] Dernière gelée moyenne par zone climatique, en « JJ-MM ».
#: DÉCISION PRODUIT **validée par un humain le 17/09/2026** (plan d'épic 8, § 12),
#: reportée ici telle quelle : même patron que `adaptateur_wind_river.ZONE_USDA_PAR_ZONE`
#: — une constante, un seul endroit, corrigeable en diff git. Aucune de ces dates
#: n'est une mesure ; elles bornent R2, et elles seules.
DERNIERE_GELEE_MOYENNE_PAR_ZONE: dict[str, str] = {
    "mediterraneen": "15-03",
    "oceanique": "05-04",
    "continental": "25-04",
    "montagnard": "10-05",
}

#: 🧪 Marge après la dernière gelée moyenne au-delà de laquelle R2 est pleine.
MARGE_DERNIERE_GELEE_JOURS = 7

#: 🧪 Seuil de « nuits douces » de R4, en °C (hypothèse de départ : 8 °C).
SEUIL_NUITS_DOUCES_C = 8.0

#: 🧪 Fenêtre de nuits observée par R4, en jours suivant la date demandée.
FENETRE_NUITS_DOUCES_JOURS = 7

#: 🧪 Au-dessus de ce seuil de `culture_config.rusticite_min_c`, la culture est
#: tenue pour GÉLIVE (hypothèse : gélive si `rusticite_min_c > -2`).
SEUIL_GELIVITE_C = -2.0

#: Température à partir de laquelle une nuit annoncée compte comme un gel.
SEUIL_GEL_C = 0.0


# ═════════════════════════════════════════════════════════════════════════════
# Résultat (CA1, CA6)
# ═════════════════════════════════════════════════════════════════════════════
ETAT_GAGNE = "gagne"
ETAT_PERDU = "perdu"
ETAT_INDETERMINE = "indetermine"

TIRET = cal.TIRET

_JOURS_SEMAINE: tuple[str, ...] = (
    "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche",
)

MOTIF_SANS_CALENDRIER = "Aucun calendrier pour cette culture dans ta zone"
MOTIF_LOCALISER = "Météo indisponible : localise ton potager pour la prendre en compte"
MOTIF_METEO_INDISPONIBLE = "Météo indisponible"
MOTIF_PLAFOND_SANS_METEO = (
    "Sans météo, la troisième étoile est hors d'atteinte : {maximum} points possibles sur 100"
)


@dataclass(frozen=True)
class Motif:
    """[CA1, CA6] Une règle, son verdict, ses points et sa raison en clair."""
    regle: str
    libelle_regle: str
    etat: str                 # ETAT_GAGNE | ETAT_PERDU | ETAT_INDETERMINE
    libelle: str
    points: int
    points_max: int

    @property
    def indetermine(self) -> bool:
        return self.etat == ETAT_INDETERMINE


@dataclass(frozen=True)
class Confiance:
    """Confiance d'une action sur une culture à une date — sans score si R1 est muette."""
    culture: str
    culture_connue: bool
    action: str
    date_cible: date
    zone: str
    itineraire: Optional[str]
    #: 1, 2 ou 3 — `None` quand aucune fenêtre n'existe pour cette phase (CA4).
    etoiles: Optional[int]
    #: Score interne 0-100 — `None` en même temps que `etoiles`.
    score: Optional[int]
    motifs: list[Motif]
    #: [CA5] Plafond réellement atteignable : 100 moins les règles indéterminées.
    score_max_atteignable: int
    #: Ce que le jardinier doit savoir en plus du score (plafond météo, pépinière).
    avertissements: list[str]
    #: Première récolte attendue si l'action a lieu à cette date — une FOURCHETTE,
    #: jamais une date sèche. Calculée ici pour qu'US-179 n'ait rien à recalculer
    #: (gabarit de réponse du bot, § 5) ; `None` si la durée est inconnue.
    recolte_min: Optional[date] = None
    recolte_max: Optional[date] = None

    @property
    def sans_score(self) -> bool:
        return self.etoiles is None

    @property
    def affichage(self) -> str:
        return TIRET if self.etoiles is None else "★" * self.etoiles


def etoiles_depuis_score(score: int) -> int:
    """[CA3] Seuls seuils d'étoiles du projet : ≥ 75 → ★★★, ≥ 45 → ★★, sinon ★."""
    if score >= SEUIL_TROIS_ETOILES:
        return 3
    if score >= SEUIL_DEUX_ETOILES:
        return 2
    return 1


# ═════════════════════════════════════════════════════════════════════════════
# Lectures de contexte
# ═════════════════════════════════════════════════════════════════════════════
def _parcelle(db: Session, potager_id: Optional[int], parcelle_id: Optional[int]) -> Optional[Parcelle]:
    """Parcelle du potager courant — jamais celle d'un autre potager (US-042)."""
    if parcelle_id is None:
        return None
    parcelle = db.get(Parcelle, parcelle_id)
    if parcelle is None or (potager_id is not None and parcelle.potager_id != potager_id):
        return None
    return parcelle


def _action_effective(action: str, parcelle: Optional[Parcelle]) -> tuple[str, list[str]]:
    """
    [CA8] Une parcelle déclarée pépinière IMPOSE le semis en pépinière quand la
    filière n'est pas dite ; une plantation qu'on y demande n'est pas corrigée en
    douce — elle porte un avertissement explicite.
    """
    avertissements: list[str] = []
    en_pepiniere = bool(parcelle is not None and parcelle.est_pepiniere)
    if action == ACTION_SEMIS:
        if en_pepiniere:
            return ACTION_SEMIS_PEPINIERE, [
                "Parcelle déclarée pépinière : semis en pépinière"
            ]
        return ACTION_SEMIS_PLEINE_TERRE, avertissements
    if en_pepiniere and action in ACTIONS_PLEINE_TERRE:
        avertissements.append(
            f"Parcelle déclarée pépinière : une {LIBELLES_ACTIONS[action]} n'y a pas sa place"
        )
    # ⚠️ Une parcelle ORDINAIRE n'est pas un indice de pleine terre (US-069) :
    # un semis en pépinière qu'on y demande s'évalue comme demandé, sans réserve.
    return action, avertissements


def _itineraire_retenu(
    calendrier: cal.Calendrier, itineraire: Optional[str]
) -> Optional[cal.ItineraireLu]:
    """
    [CA7] L'itinéraire demandé, sinon celui par défaut du référentiel (le premier,
    « standard » en tête — US-176 / CA5). [CA3] Un itinéraire personnalisé remplace
    déjà le partagé de même nom dans `lire_calendrier` : la correction locale prime
    sans second mécanisme.
    """
    if not calendrier.itineraires:
        return None
    if itineraire and str(itineraire).strip():
        vise = cal.normaliser_itineraire(itineraire)
        return next(
            (it for it in calendrier.itineraires if cal.normaliser_itineraire(it.nom) == vise),
            None,
        )
    return calendrier.itineraires[0]


def _rusticite(fiches: list[CultureConfig]) -> Optional[float]:
    """Rusticité lue sur la fiche du potager si elle en porte une, sinon la partagée."""
    for fiche in reversed(fiches):          # personnalisées en fin de liste
        if fiche.rusticite_min_c is not None:
            return float(fiche.rusticite_min_c)
    return None


def _jours_prevus(lecture: svc_previsions.LecturePrevision) -> list[tuple[date, Optional[float]]]:
    """Prévisions étendues (US-182) ramenées à `(jour, température minimale)`."""
    if not lecture.disponible or not lecture.meteo:
        return []
    jours: list[tuple[date, Optional[float]]] = []
    for jour in lecture.meteo.get("previsions_etendues") or []:
        try:
            jours.append((date.fromisoformat(jour["date"]), jour.get("temp_min")))
        except (KeyError, TypeError, ValueError):
            continue
    return jours


def _libelle_jour(jour: date) -> str:
    """« jeudi 19 » — le jour que le jardinier reconnaîtra dans sa semaine."""
    return f"{_JOURS_SEMAINE[jour.weekday()]} {jour.day}"


def date_derniere_gelee(zone: str, annee: int) -> Optional[date]:
    """[CA3] Dernière gelée moyenne de la zone, datée dans `annee` — seule lecture
    de la table validée le 17/09/2026."""
    valeur = DERNIERE_GELEE_MOYENNE_PAR_ZONE.get(zone)
    if valeur is None:
        return None
    jour, mois = (int(part) for part in valeur.split("-"))
    return date(annee, mois, jour)


def _fin_de_mois(annee: int, mois: int) -> date:
    return date(annee, mois, calendar.monthrange(annee, mois)[1])


def prochaine_saison_de_recolte(
    fenetre: cal.FenetreLue, depuis: date
) -> tuple[date, date]:
    """
    La prochaine occurrence de la fenêtre de récolte qui ne soit pas déjà finie
    à `depuis` — bornes incluses.

    ⚠️ Une fenêtre est un couple de MOIS, sans année : « juillet → août » n'est
    pas une période, c'est un motif qui se répète. Le calendrier en porte deux
    formes, et les confondre est l'erreur à ne pas refaire :

    * `mois_debut <= mois_fin` — « juillet → août », dans l'année civile ;
    * `mois_debut >  mois_fin` — « novembre → février », qui ENJAMBE le 31/12
      et dont la fin appartient donc à l'année suivant le début.

    L'occurrence rendue est la première dont la FIN tombe à `depuis` ou après :
    c'est la seule saison sur laquelle un semis fait ce jour-là peut encore
    tomber.

    ⚠️ Le balayage commence à l'année PRÉCÉDENTE, et ce n'est pas une précaution
    gratuite : une fenêtre qui enjambe le 31/12 est encore ouverte en janvier
    alors qu'elle a commencé l'année d'avant. Partir de l'année de `depuis`
    ferait sauter par-dessus la saison en cours — « je peux semer de la mâche
    le 15 janvier ? » se verrait comparé à la saison de novembre SUIVANT.
    """
    for decalage in (-1, 0, 1):
        annee_debut = depuis.year + decalage
        debut = date(annee_debut, fenetre.mois_debut, 1)
        annee_fin = annee_debut + (1 if fenetre.mois_debut > fenetre.mois_fin else 0)
        fin = _fin_de_mois(annee_fin, fenetre.mois_fin)
        if fin >= depuis:
            return debut, fin
    # Inatteignable : le décalage d'un an suffit toujours à dépasser `depuis`.
    raise AssertionError("fenêtre de récolte sans occurrence à venir")  # pragma: no cover


# ═════════════════════════════════════════════════════════════════════════════
# Les cinq règles — chacune rend UN motif, points compris
# ═════════════════════════════════════════════════════════════════════════════
def _motif(regle: str, etat: str, libelle: str, points: int) -> Motif:
    return Motif(
        regle=regle, libelle_regle=LIBELLES_REGLES[regle], etat=etat,
        libelle=libelle, points=points, points_max=POINTS_MAX[regle],
    )


def _regle_fenetre(fenetre: Optional[cal.FenetreLue], date_cible: date) -> Motif:
    """R1 — la date tombe-t-elle dans la fenêtre conseillée de la zone ?"""
    if fenetre is None:
        return _motif(R1_FENETRE, ETAT_INDETERMINE, MOTIF_SANS_CALENDRIER, 0)
    mois = fenetre.mois
    if date_cible.month in mois:
        return _motif(R1_FENETRE, ETAT_GAGNE, "Dans la fenêtre conseillée pour ta zone",
                      POINTS_MAX[R1_FENETRE])
    avant = fenetre.mois_debut - 1 or 12
    apres = fenetre.mois_fin % 12 + 1
    if date_cible.month == avant:
        return _motif(R1_FENETRE, ETAT_GAGNE, "Un mois avant la fenêtre conseillée",
                      POINTS_R1_MOIS_ADJACENT)
    if date_cible.month == apres:
        return _motif(R1_FENETRE, ETAT_GAGNE, "Un mois après la fenêtre conseillée",
                      POINTS_R1_MOIS_ADJACENT)
    return _motif(R1_FENETRE, ETAT_PERDU,
                  f"Hors fenêtre conseillée ({fenetre.affichage} pour ta zone)", 0)


def _regle_derniere_gelee(
    action: str, zone: str, rusticite: Optional[float], date_cible: date
) -> Motif:
    """R2 — climatologie de la ZONE : la dernière gelée moyenne est-elle passée ?"""
    plein = POINTS_MAX[R2_DERNIERE_GELEE]
    if action not in ACTIONS_PLEINE_TERRE:
        return _motif(R2_DERNIERE_GELEE, ETAT_GAGNE,
                      "Semis en pépinière : gelée sans objet", plein)
    if rusticite is None:
        return _motif(R2_DERNIERE_GELEE, ETAT_INDETERMINE,
                      "Sensibilité au gel inconnue pour cette culture", 0)
    if rusticite <= SEUIL_GELIVITE_C:
        return _motif(R2_DERNIERE_GELEE, ETAT_GAGNE,
                      "Culture rustique : les gelées de ta zone ne la menacent pas", plein)
    gelee = date_derniere_gelee(zone, date_cible.year)
    if gelee is None:
        return _motif(R2_DERNIERE_GELEE, ETAT_INDETERMINE,
                      "Dernière gelée moyenne inconnue pour ta zone", 0)
    ecart = (date_cible - gelee).days
    if ecart >= MARGE_DERNIERE_GELEE_JOURS:
        return _motif(R2_DERNIERE_GELEE, ETAT_GAGNE, "Dernière gelée moyenne passée", plein)
    if ecart >= 0:
        return _motif(R2_DERNIERE_GELEE, ETAT_GAGNE,
                      "Dernière gelée moyenne tout juste passée", POINTS_R2_GELEE_TOUT_JUSTE)
    return _motif(R2_DERNIERE_GELEE, ETAT_PERDU,
                  "Trop tôt : gelées encore possibles dans ta zone", 0)


def _regle_gel_annonce(
    action: str, lecture: svc_previsions.LecturePrevision, date_cible: date
) -> Motif:
    """R3 — météo de la QUINZAINE : un gel est-il annoncé ? (distincte de R2)"""
    plein = POINTS_MAX[R3_GEL_ANNONCE]
    if action not in ACTIONS_PLEINE_TERRE:
        return _motif(R3_GEL_ANNONCE, ETAT_GAGNE, "Semis en pépinière : gel annoncé sans objet", plein)
    if lecture.statut == svc_previsions.STATUT_LOCALISATION_MANQUANTE:
        return _motif(R3_GEL_ANNONCE, ETAT_INDETERMINE, MOTIF_LOCALISER, 0)
    jours = [(j, t) for j, t in _jours_prevus(lecture) if j >= date_cible]
    if not jours:
        if not lecture.disponible:
            return _motif(R3_GEL_ANNONCE, ETAT_INDETERMINE, MOTIF_METEO_INDISPONIBLE, 0)
        return _motif(R3_GEL_ANNONCE, ETAT_INDETERMINE,
                      "Date au-delà de l'horizon de prévision", 0)
    gel = next((j for j, t in jours if t is not None and t <= SEUIL_GEL_C), None)
    if gel is not None:
        return _motif(R3_GEL_ANNONCE, ETAT_PERDU, f"Gel annoncé le {_libelle_jour(gel)}", 0)
    return _motif(R3_GEL_ANNONCE, ETAT_GAGNE, f"Aucun gel annoncé sur {METEO_HORIZON_PREVISION_JOURS} jours", plein)


def _regle_nuits_douces(
    action: str, lecture: svc_previsions.LecturePrevision, date_cible: date
) -> Motif:
    """R4 — les nuits de la semaine qui suit sont-elles assez douces pour lever ?"""
    plein = POINTS_MAX[R4_NUITS_DOUCES]
    if action not in ACTIONS_PLEINE_TERRE:
        return _motif(R4_NUITS_DOUCES, ETAT_GAGNE,
                      "Semis en pépinière : nuits sans objet", plein)
    if lecture.statut == svc_previsions.STATUT_LOCALISATION_MANQUANTE:
        return _motif(R4_NUITS_DOUCES, ETAT_INDETERMINE, MOTIF_METEO_INDISPONIBLE, 0)
    fin = date_cible + timedelta(days=FENETRE_NUITS_DOUCES_JOURS)
    temperatures = [t for j, t in _jours_prevus(lecture) if date_cible <= j <= fin and t is not None]
    if not temperatures:
        if not lecture.disponible:
            return _motif(R4_NUITS_DOUCES, ETAT_INDETERMINE, MOTIF_METEO_INDISPONIBLE, 0)
        return _motif(R4_NUITS_DOUCES, ETAT_INDETERMINE,
                      "Date au-delà de l'horizon de prévision", 0)
    moyenne = sum(temperatures) / len(temperatures)
    if moyenne >= SEUIL_NUITS_DOUCES_C:
        return _motif(R4_NUITS_DOUCES, ETAT_GAGNE,
                      "Nuits douces annoncées", plein)
    return _motif(R4_NUITS_DOUCES, ETAT_PERDU,
                  "Nuits fraîches : levée lente probable", 0)


def _etape_recolte(action: str) -> str:
    """[US-177 / CA8] `plantation_recolte` pour une plantation, `recolte` pour un
    semis — jamais l'une pour l'autre, et la règle tient à un seul endroit."""
    return cal.ETAPE_PLANTATION_RECOLTE if action == ACTION_PLANTATION else cal.ETAPE_RECOLTE


def recolte_attendue(
    itineraire: cal.ItineraireLu, action: str, date_cible: date
) -> tuple[Optional[date], Optional[date]]:
    """
    Fourchette de première récolte si l'action a lieu à `date_cible` — bornes
    incluses, `(None, None)` si la durée n'est pas chiffrée. Jamais une date
    sèche : c'est ce que R5 compare, et ce que le bot d'US-179 affichera.
    """
    duree = itineraire.duree(_etape_recolte(action))
    if duree is None or duree.jours_max is None:
        return (None, None)
    jours_min = duree.jours_min if duree.jours_min is not None else duree.jours_max
    return (date_cible + timedelta(days=jours_min),
            date_cible + timedelta(days=duree.jours_max))


def _regle_saison_restante(
    itineraire: cal.ItineraireLu, action: str, date_cible: date
) -> Motif:
    """
    R5 — la première récolte attendue tomberait-elle PENDANT la saison de récolte
    conseillée ? La durée lue dépend de l'action : `plantation_recolte` pour une
    plantation (US-177), `recolte` pour un semis — jamais l'une pour l'autre
    (US-177 / CA8).

    ⚠️ La règle teste une APPARTENANCE à l'intervalle, jamais la seule
    antériorité de sa borne de fin. C'est le correctif du 18/09/2026, et le motif
    en vaut d'être rappelé : comparer à la seule fin obligeait, quand ce mois
    était déjà passé, à reporter la saison d'un an — et ce report offrait onze
    mois de marge à qui était le plus en retard. Un semis de haricot le
    19 septembre gagnait ainsi la règle en zone océanique (récolte juillet →
    août, reportée à l'an prochain) là où il la perdait en zone montagnarde
    (récolte août → octobre, encore ouverte) : plus la culture était hors saison,
    plus elle marquait de points. Constaté sur deux potagers réels.

    Le report, lui, reste indispensable : un ail semé en octobre se récolte bien
    dans la fenêtre « mars → mai » de l'année SUIVANTE. Il vit désormais dans
    `prochaine_saison_de_recolte`, qui rend l'intervalle entier.
    """
    plein = POINTS_MAX[R5_SAISON_RESTANTE]
    etape = _etape_recolte(action)
    _, attendue = recolte_attendue(itineraire, action, date_cible)
    if attendue is None:
        return _motif(R5_SAISON_RESTANTE, ETAT_INDETERMINE,
                      f"Durée {cal.LIBELLES_ETAPES[etape].lower()} inconnue", 0)
    fenetre = itineraire.fenetre(cal.PHASE_RECOLTE)
    if fenetre is None:
        return _motif(R5_SAISON_RESTANTE, ETAT_INDETERMINE,
                      "Saison de récolte inconnue pour ta zone", 0)
    debut_saison, fin_saison = prochaine_saison_de_recolte(fenetre, date_cible)
    if debut_saison <= attendue <= fin_saison:
        return _motif(R5_SAISON_RESTANTE, ETAT_GAGNE,
                      "La récolte tomberait dans la saison conseillée", plein)
    if attendue > fin_saison:
        return _motif(R5_SAISON_RESTANTE, ETAT_PERDU,
                      "Récolte attendue après la fin de saison conseillée", 0)
    # La récolte arriverait AVANT l'ouverture de la saison : ce n'est pas un
    # semis tardif, c'est une saison de récolte déjà passée pour cette année.
    return _motif(R5_SAISON_RESTANTE, ETAT_PERDU,
                  f"Saison de récolte déjà passée : la prochaine ouvre en "
                  f"{cal.MOIS[fenetre.mois_debut - 1]}", 0)


# ═════════════════════════════════════════════════════════════════════════════
# Évaluation (CA1, CA2, CA5, CA6)
# ═════════════════════════════════════════════════════════════════════════════
def _sans_score(
    culture: str, culture_connue: bool, action: str, date_cible: date, zone: str,
    itineraire: Optional[str], avertissements: list[str],
) -> Confiance:
    """[CA4] Pas de fenêtre pour cette phase dans cette zone : pas de score, un tiret."""
    return Confiance(
        culture=culture, culture_connue=culture_connue, action=action, date_cible=date_cible,
        zone=zone, itineraire=itineraire, etoiles=None, score=None,
        motifs=[_motif(R1_FENETRE, ETAT_INDETERMINE, MOTIF_SANS_CALENDRIER, 0)],
        score_max_atteignable=0, avertissements=avertissements,
    )


def evaluer(
    db: Session,
    culture: str,
    action: Optional[str],
    date_cible: date,
    potager_id: Optional[int],
    parcelle_id: Optional[int] = None,
    itineraire: Optional[str] = None,
    lecture_meteo: Optional[svc_previsions.LecturePrevision] = None,
) -> Confiance:
    """
    [CA1-CA8] Confiance d'une action sur une culture, à une date, pour un potager.

    Lecture seule, sans appel LLM (CA2) et sans écriture (CA11). `lecture_meteo`
    est la prévision déjà lue par l'appelant — c'est ce qui permet à la lecture
    groupée de n'en faire qu'une pour tout l'écran Plan (CA9, CA10).
    """
    action_demandee = normaliser_action(action)
    parcelle = _parcelle(db, potager_id, parcelle_id)
    action_retenue, avertissements = _action_effective(action_demandee, parcelle)

    calendrier = cal.lire_calendrier(db, culture, potager_id)
    itineraire_lu = _itineraire_retenu(calendrier, itineraire)
    if itineraire_lu is None:
        return _sans_score(culture, calendrier.culture_connue, action_retenue, date_cible,
                           calendrier.zone, itineraire, avertissements)

    fenetre = itineraire_lu.fenetre(PHASE_PAR_ACTION[action_retenue])
    if fenetre is None:
        return _sans_score(culture, calendrier.culture_connue, action_retenue, date_cible,
                           calendrier.zone, itineraire_lu.nom, avertissements)

    if lecture_meteo is None:
        lecture_meteo = _lire_meteo(db, potager_id)
    rusticite = _rusticite(cal.fiches_visibles(db, culture, potager_id))

    motifs = [
        _regle_fenetre(fenetre, date_cible),
        _regle_derniere_gelee(action_retenue, calendrier.zone, rusticite, date_cible),
        _regle_gel_annonce(action_retenue, lecture_meteo, date_cible),
        _regle_nuits_douces(action_retenue, lecture_meteo, date_cible),
        _regle_saison_restante(itineraire_lu, action_retenue, date_cible),
    ]

    score = sum(m.points for m in motifs)
    # [CA5] Une règle indéterminée ne se compense pas : elle ABAISSE le plafond,
    # et le jardinier l'apprend au lieu de subir une étoile manquante.
    maximum = SCORE_MAXIMUM - sum(m.points_max for m in motifs if m.indetermine)
    if maximum < SEUIL_TROIS_ETOILES:
        avertissements.append(MOTIF_PLAFOND_SANS_METEO.format(maximum=maximum))

    recolte_min, recolte_max = recolte_attendue(itineraire_lu, action_retenue, date_cible)
    confiance = Confiance(
        culture=culture, culture_connue=calendrier.culture_connue, action=action_retenue,
        date_cible=date_cible, zone=calendrier.zone, itineraire=itineraire_lu.nom,
        etoiles=etoiles_depuis_score(score), score=score, motifs=motifs,
        score_max_atteignable=maximum, avertissements=avertissements,
        recolte_min=recolte_min, recolte_max=recolte_max,
    )
    log.info(
        "[US-178] Confiance %s / %s le %s : %d/100 (%s) — potager=%s zone=%s",
        culture, action_retenue, date_cible, score, confiance.affichage,
        potager_id, calendrier.zone,
    )
    return confiance


def _lire_meteo(db: Session, potager_id: Optional[int]) -> svc_previsions.LecturePrevision:
    """[CA10] Prévisions lues par le CACHE d'US-182 — jamais un appel réseau direct."""
    potager = db.get(Potager, potager_id) if potager_id is not None else None
    return svc_previsions.lire_prevision_potager(potager)


def evaluer_cultures(
    db: Session,
    cultures: Iterable[str],
    action: Optional[str],
    date_cible: date,
    potager_id: Optional[int],
    parcelle_id: Optional[int] = None,
    itineraire: Optional[str] = None,
) -> dict[str, Confiance]:
    """
    [CA9, CA10] Confiance de PLUSIEURS cultures à une même date, en une seule
    lecture météo — le besoin de l'écran Plan (US-180), qui n'a droit qu'à une
    requête. La clé est le nom tel que demandé.
    """
    lecture = _lire_meteo(db, potager_id)
    return {
        nom: evaluer(db, nom, action, date_cible, potager_id, parcelle_id, itineraire, lecture)
        for nom in dict.fromkeys(c for c in cultures if c and c.strip())
    }


def confiance_en_dict(confiance: Confiance) -> dict:
    """Forme sérialisable — celle que servent l'API (CA9) et que lira le bot (US-179)."""
    return {
        "culture": confiance.culture,
        "culture_connue": confiance.culture_connue,
        "action": confiance.action,
        "action_libelle": LIBELLES_ACTIONS[confiance.action],
        "date": confiance.date_cible.isoformat(),
        "zone_climatique": confiance.zone,
        "itineraire": confiance.itineraire,
        "etoiles": confiance.etoiles,
        "affichage": confiance.affichage,
        "score": confiance.score,
        "score_max_atteignable": confiance.score_max_atteignable,
        # [CA6] Le détail par règle : de quoi afficher « pourquoi deux étoiles ».
        "motifs": [
            {"regle": m.regle, "regle_libelle": m.libelle_regle, "etat": m.etat,
             "libelle": m.libelle, "points": m.points, "points_max": m.points_max}
            for m in confiance.motifs
        ],
        "avertissements": confiance.avertissements,
        # Une FOURCHETTE ou rien — le bot (US-179) l'affiche sans rien recalculer.
        "recolte_attendue": {
            "min": confiance.recolte_min.isoformat() if confiance.recolte_min else None,
            "max": confiance.recolte_max.isoformat() if confiance.recolte_max else None,
        },
    }


# ═════════════════════════════════════════════════════════════════════════════
# Lecture de l'écran Plan [US-180]
# ═════════════════════════════════════════════════════════════════════════════
#: [US-180 / CA1] Les gestes qu'une tuile peut porter. La récolte n'en est pas
#: un : on ne décide pas de récolter, on récolte quand c'est prêt.
ACTIONS_DE_TUILE: tuple[str, ...] = (
    ACTION_SEMIS_PEPINIERE, ACTION_SEMIS_PLEINE_TERRE, ACTION_PLANTATION,
)


@dataclass(frozen=True)
class ConfiancesCulture:
    """[US-180 / CA1, CA3] Ce qu'une tuile de l'écran Plan peut proposer à une date.

    Trois états, et trois seulement — la tuile n'en invente pas un quatrième :

    - `candidates` non vide → la ligne de confiance, sur la mieux placée ;
    - `candidates` vide et `a_calendrier` → rien à semer ni à planter ce mois-ci ;
    - `a_calendrier` faux → aucune fenêtre pour la zone (dégradé d'US-176 / CA6).
    """
    culture: str
    culture_connue: bool
    #: Au moins une phase de SEMIS ou de PLANTATION a une fenêtre pour la zone.
    #: La récolte n'y compte pas : elle ne se décide pas depuis la tuile.
    a_calendrier: bool
    #: [CA1] Actions en fenêtre ou à un mois, du meilleur score au moins bon.
    #: L'égalité n'est PAS tranchée ici : la règle de priorité des phases vit
    #: avec la frise qui la sert déjà (US-176 / CA3bis, `lib/calendrier.js`).
    candidates: list[Confiance]
    #: [US-183 / CA4] TOUTES les actions dont la phase a une fenêtre pour la
    #: zone, dans l'ordre du geste — le sélecteur de la fiche calendrier. Même
    #: évaluation que `candidates`, donc la tuile et la fiche ne peuvent pas
    #: afficher deux niveaux différents pour la même culture au même instant.
    actions: list[Confiance]


def confiances_de_culture(
    db: Session,
    culture: str,
    date_cible: date,
    potager_id: Optional[int],
    lecture_meteo: Optional[svc_previsions.LecturePrevision] = None,
) -> ConfiancesCulture:
    """
    [US-180 / CA1, CA3] Les actions PERTINENTES pour cette culture à cette date.

    « Pertinente » n'a pas de second mécanisme : c'est exactement R1 gagnée —
    la date tombe dans la fenêtre conseillée de la zone, ou à un mois d'elle.
    Le barème d'US-178 reste donc le seul juge de l'approche (US-178 / CA3).

    Aucune parcelle n'est passée : l'écran Plan lit une culture, pas un geste sur
    une planche. Les trois actions sont demandées NOMMÉMENT, donc aucune n'est
    tranchée en douce par `est_pepiniere` (US-178 / CA8).
    """
    evaluations = [
        evaluer(db, culture, action, date_cible, potager_id, lecture_meteo=lecture_meteo)
        for action in ACTIONS_DE_TUILE
    ]
    candidates = [
        c for c in evaluations
        if not c.sans_score
        and any(m.regle == R1_FENETRE and m.etat == ETAT_GAGNE for m in c.motifs)
    ]
    candidates.sort(key=lambda c: -(c.score or 0))
    return ConfiancesCulture(
        culture=culture,
        culture_connue=any(c.culture_connue for c in evaluations),
        a_calendrier=any(not c.sans_score for c in evaluations),
        candidates=candidates,
        actions=[c for c in evaluations if not c.sans_score],
    )


def confiances_du_plan(
    db: Session,
    cultures: Iterable[str],
    date_cible: date,
    potager_id: Optional[int],
) -> dict[str, ConfiancesCulture]:
    """
    [US-180 / CA6] Toutes les tuiles de l'écran Plan en UNE lecture : une seule
    prévision météo pour l'écran entier (US-178 / CA9, CA10), jamais une requête
    par tuile ni par action.
    """
    lecture = _lire_meteo(db, potager_id)
    return {
        nom: confiances_de_culture(db, nom, date_cible, potager_id, lecture)
        for nom in dict.fromkeys(c for c in cultures if c and c.strip())
    }


def confiances_culture_en_dict(confiances: ConfiancesCulture) -> dict:
    """Forme servie à l'écran Plan — les trois états d'une tuile, sans repli."""
    return {
        "culture": confiances.culture,
        "culture_connue": confiances.culture_connue,
        "a_calendrier": confiances.a_calendrier,
        "candidates": [confiance_en_dict(c) for c in confiances.candidates],
        "actions": [confiance_en_dict(c) for c in confiances.actions],
    }

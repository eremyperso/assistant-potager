"""
app/services/compagnon/veilleur.py — Ce qui mérite un message : les détecteurs [US-266]
======================================================================================
Le veilleur DÉTECTE, il ne rédige pas (R7) : ce module n'importe ni `llm`, ni l'agent,
et un test d'AST le vérifie (CA6). L'agent rédigera un signal plus tard (US-267), comme
il répond à une phrase ; ici, aucun message n'est envoyé.

Chaque détecteur est une fonction PURE (CA1) : il reçoit l'état du potager
(`EtatPotager`, lu en base par `veilleur_passage`) et rend des `Signal`
`(theme, cle_unique, priorite, expire_le, donnees)`. Ni base, ni réseau, ni horloge :
`etat.maintenant` est la seule heure qu'il connaisse. On le teste donc sans fixture.

`cle_unique` décrit le FAIT, pas le passage (CA3) : « gel:2026-10-28:parcelle-12 ».
Deux passages qui voient le même fait rendent la même clé, et la table n'en garde
qu'un (`signaux.enregistrer`).

Les seuils propres à une culture viennent du référentiel (CA8) : rusticité
(`culture_config.rusticite_min_c`), durées (`DureeCulturale`), fenêtres
(`FenetreCulturale`). Sans la donnée, pas de signal : aucun seuil n'est inventé pour
une culture qui n'en a pas. Les seuils qui ne dépendent d'aucune culture (canicule,
fortes pluies, chaleur) sont déclarés une fois, ci-dessous.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Callable, Iterable, Optional

from unidecode import unidecode

from app.services.alerte_recolte import SEUIL_ALERTE, alerte_recolte

log = logging.getLogger("potager")

# ═════════════════════════════════════════════════════════════════════════════
# Vocabulaire — le même que la table `signaux` (CHECK de migration_v65)
# ═════════════════════════════════════════════════════════════════════════════
THEME_METEO = "meteo"
THEME_SUIVIS = "suivis"
THEME_ECHEANCES = "echeances"
THEME_SUGGESTIONS = "suggestions"
THEME_RAPPELS = "rappels"
THEME_RESUME = "resume"
THEMES: tuple[str, ...] = (
    THEME_METEO, THEME_SUIVIS, THEME_ECHEANCES, THEME_SUGGESTIONS, THEME_RAPPELS, THEME_RESUME,
)

PRIORITE_IMMEDIATE = "immediat"
PRIORITE_NORMALE = "normal"
PRIORITE_RESUME = "resume"
PRIORITES: tuple[str, ...] = (PRIORITE_IMMEDIATE, PRIORITE_NORMALE, PRIORITE_RESUME)

#: Codes d'action suggérée de `echeances_lots` qui font une échéance de lot.
ACTION_REPIQUER = "repiquer"
ACTION_METTRE_EN_TERRE = "mettre_en_terre"

# ═════════════════════════════════════════════════════════════════════════════
# Seuils hors référentiel — UN bloc, corrigeable en un diff
# ═════════════════════════════════════════════════════════════════════════════
#: Jours de prévision regardés pour le gel, la canicule et les fortes pluies
#: (0 = aujourd'hui). Au-delà, la prévision est trop incertaine pour prévenir.
HORIZON_METEO_JOURS = 3
#: Une alerte du jour même ou du lendemain part tout de suite ; au-delà, elle attend.
HORIZON_IMMEDIAT_JOURS = 1
#: 🧪 Température maximale à partir de laquelle une journée est une canicule pour le potager.
SEUIL_CANICULE_C = 32.0
#: 🧪 Cumul de pluie du jour qui fait de fortes pluies (mm).
SEUIL_FORTES_PLUIES_MM = 20.0
#: 🧪 Sécheresse : jours chauds annoncés d'affilée, dès aujourd'hui…
JOURS_CHAUDS_SECHERESSE = 3
#: 🧪 … au-dessus de cette température maximale…
SEUIL_CHALEUR_C = 28.0
#: 🧪 … sans pluie utile (cumul du jour sous ce seuil, en mm)…
SEUIL_PLUIE_UTILE_MM = 2.0
#: 🧪 … et aucun arrosage noté depuis ce nombre de jours.
JOURS_SANS_ARROSAGE = 5
#: Un signal d'échéance ou de suivi reste pertinent une semaine s'il n'a pas de date.
DUREE_PERTINENCE = timedelta(days=7)
#: Le bilan de la semaine couvre les 7 derniers jours.
JOURS_BILAN = 7
#: Les fenêtres de semis citées dans un signal, au plus.
NB_FENETRES_MAX = 12

#: Les gestes qui ne disent rien au bilan : la météo enregistrée par le job de 5 h.
TEXTE_METEO_AUTO = "[AUTO-METEO]"


# ═════════════════════════════════════════════════════════════════════════════
# Ce qu'un détecteur reçoit, et ce qu'il rend (CA1)
# ═════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Signal:
    """Un fait qui mérite peut-être un message. `donnees` ne contient que des valeurs JSON."""

    theme: str
    cle_unique: str
    priorite: str
    expire_le: datetime
    donnees: dict = field(default_factory=dict)


@dataclass(frozen=True)
class CultureEnPlace:
    """Une culture en terre (ou semée en place), telle que `/plan` la montre."""

    culture: str
    nb_plants: float
    age_jours: int
    parcelle_id: Optional[int] = None
    parcelle_nom: Optional[str] = None
    variete: Optional[str] = None
    unite: Optional[str] = None
    type_organe: Optional[str] = None
    date_plantation: Optional[date] = None
    est_semis: bool = False
    #: Référentiel (`culture_config.rusticite_min_c`) ; None = inconnue, pas de signal de gel.
    rusticite_min_c: Optional[float] = None
    abri: Optional[str] = None


@dataclass(frozen=True)
class JourPrevu:
    """Une journée de prévision Open-Meteo."""

    jour: date
    temp_min: Optional[float] = None
    temp_max: Optional[float] = None
    precipitations: Optional[float] = None


@dataclass(frozen=True)
class LotPepiniere:
    """Un lot de semis, avec l'action que `echeances_lots` lui suggère."""

    lot_id: str
    culture: str
    numero: Optional[int] = None
    variete: Optional[str] = None
    date_semis: Optional[date] = None
    #: Code d'action suggérée (`echeances_lots.ACTION_*`), ou None.
    action: Optional[str] = None
    #: Fourchette de l'échéance de l'action, quand elle en a une.
    echeance_du: Optional[date] = None
    echeance_au: Optional[date] = None
    levee_notee: bool = False
    #: Graines semées qui n'ont encore donné ni levée ni godet.
    graines_en_attente: int = 0
    #: `DureeCulturale` de la levée (jours, borne haute) ; None = inconnue.
    duree_levee_max_jours: Optional[int] = None


@dataclass(frozen=True)
class FenetreSemis:
    """Une fenêtre de semis du calendrier cultural, pour la zone du potager."""

    culture: str
    phase: str
    mois_debut: int
    mois_fin: int
    deja_cultivee: bool = False


@dataclass(frozen=True)
class GesteDuJournal:
    """Un geste du journal récent du potager."""

    jour: date
    type_action: Optional[str]
    culture: Optional[str] = None
    quantite: Optional[float] = None
    unite: Optional[str] = None
    texte_original: Optional[str] = None


@dataclass(frozen=True)
class RappelProgramme:
    """[US-268] Un rappel confirmé par le jardinier, encore à venir ou tout juste échu."""

    rappel_id: int
    objet: str
    echeance_le: datetime
    cible_type: Optional[str] = None
    cible_id: Optional[int] = None


@dataclass(frozen=True)
class EtatPotager:
    """Tout ce que les détecteurs savent d'un potager, à un instant donné."""

    potager_id: int
    #: Heure locale du potager (Europe/Paris), sans fuseau.
    maintenant: datetime
    cultures: tuple[CultureEnPlace, ...] = ()
    previsions: tuple[JourPrevu, ...] = ()
    lots: tuple[LotPepiniere, ...] = ()
    fenetres_semis: tuple[FenetreSemis, ...] = ()
    #: Les gestes des deux dernières semaines au moins.
    journal: tuple[GesteDuJournal, ...] = ()
    #: [US-268] Les rappels programmés dont l'heure est venue.
    rappels: tuple[RappelProgramme, ...] = ()

    @property
    def aujourd_hui(self) -> date:
        return self.maintenant.date()


Detecteur = Callable[[EtatPotager], list[Signal]]


# ═════════════════════════════════════════════════════════════════════════════
# Outils communs
# ═════════════════════════════════════════════════════════════════════════════
def _slug(texte: Optional[str]) -> str:
    """« Pomme de terre » → « pomme-de-terre » : une clé lisible, stable, sans accent."""
    brut = unidecode((texte or "").strip().lower())
    mots = "".join(c if c.isalnum() else " " for c in brut).split()
    return "-".join(mots) or "inconnue"


def _cle_parcelle(culture: CultureEnPlace) -> str:
    return f"parcelle-{culture.parcelle_id}" if culture.parcelle_id is not None else "sans-parcelle"


def _fin_du_jour(jour: date) -> datetime:
    return datetime.combine(jour, time(23, 59))


def _priorite_meteo(etat: EtatPotager, jour: date) -> str:
    """Le jour même ou le lendemain : tout de suite ; plus loin, rien ne presse."""
    if (jour - etat.aujourd_hui).days <= HORIZON_IMMEDIAT_JOURS:
        return PRIORITE_IMMEDIATE
    return PRIORITE_NORMALE


def _jours_regardes(etat: EtatPotager) -> list[JourPrevu]:
    """Les jours de prévision de l'horizon météo, d'aujourd'hui à J+3, dans l'ordre."""
    fin = etat.aujourd_hui + timedelta(days=HORIZON_METEO_JOURS)
    return sorted(
        (j for j in etat.previsions if etat.aujourd_hui <= j.jour <= fin), key=lambda j: j.jour,
    )


def _par_parcelle(cultures: Iterable[CultureEnPlace]) -> dict[str, list[CultureEnPlace]]:
    groupes: dict[str, list[CultureEnPlace]] = {}
    for culture in cultures:
        groupes.setdefault(_cle_parcelle(culture), []).append(culture)
    return groupes


def _culture_en_donnees(culture: CultureEnPlace, **plus) -> dict:
    return {
        "culture": culture.culture, "variete": culture.variete,
        "nb_plants": culture.nb_plants, "unite": culture.unite or "plants", **plus,
    }


def _lieu(cultures: list[CultureEnPlace]) -> dict:
    premiere = cultures[0]
    return {"parcelle_id": premiere.parcelle_id, "parcelle": premiere.parcelle_nom, "abri": premiere.abri}


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — Les détecteurs
# ═════════════════════════════════════════════════════════════════════════════
def detecter_gel_canicule(etat: EtatPotager) -> list[Signal]:
    """Gel ou canicule annoncés × cultures en place. Un signal par jour et par parcelle.

    Gel : la minimale annoncée passe SOUS la rusticité de la culture (référentiel). Une
    culture sans rusticité connue n'est jamais exposée « par défaut ».
    Canicule : la maximale annoncée atteint `SEUIL_CANICULE_C`, pour toute culture en place.
    """
    signaux: list[Signal] = []
    if not etat.cultures:
        return signaux
    groupes = _par_parcelle(etat.cultures)
    for jour in _jours_regardes(etat):
        for cle_parcelle, cultures in groupes.items():
            if jour.temp_min is not None:
                exposees = [
                    c for c in cultures
                    if c.rusticite_min_c is not None and jour.temp_min < c.rusticite_min_c
                ]
                if exposees:
                    signaux.append(Signal(
                        theme=THEME_METEO,
                        cle_unique=f"gel:{jour.jour.isoformat()}:{cle_parcelle}",
                        priorite=_priorite_meteo(etat, jour.jour),
                        # Le gel est un fait de l'aube : passé la matinée, il est trop tard.
                        expire_le=datetime.combine(jour.jour, time(10, 0)),
                        donnees={
                            "jour": jour.jour.isoformat(), "temp_min": jour.temp_min, **_lieu(exposees),
                            "cultures": [_culture_en_donnees(c, seuil_c=c.rusticite_min_c) for c in exposees],
                        },
                    ))
            if jour.temp_max is not None and jour.temp_max >= SEUIL_CANICULE_C:
                signaux.append(Signal(
                    theme=THEME_METEO,
                    cle_unique=f"canicule:{jour.jour.isoformat()}:{cle_parcelle}",
                    priorite=_priorite_meteo(etat, jour.jour),
                    expire_le=datetime.combine(jour.jour, time(20, 0)),
                    donnees={
                        "jour": jour.jour.isoformat(), "temp_max": jour.temp_max,
                        "seuil_c": SEUIL_CANICULE_C, **_lieu(cultures),
                        "cultures": [_culture_en_donnees(c) for c in cultures],
                    },
                ))
    return signaux


def _dernier_arrosage(etat: EtatPotager) -> Optional[date]:
    jours = [g.jour for g in etat.journal if g.type_action == "arrosage"]
    return max(jours) if jours else None


def detecter_pluie_secheresse(etat: EtatPotager) -> list[Signal]:
    """Fortes pluies annoncées (météo) ; ou chaleur sèche sans arrosage noté (suivis).

    Sécheresse : `JOURS_CHAUDS_SECHERESSE` jours d'affilée, dès aujourd'hui, au-dessus de
    `SEUIL_CHALEUR_C` et sans pluie utile, alors qu'aucun arrosage n'est noté depuis
    `JOURS_SANS_ARROSAGE` jours et que des cultures sont en place. Un cumul de pluie
    inconnu ne vaut jamais « sec ». La clé suit le dernier arrosage : un arrosage noté
    clôt le fait, la sécheresse suivante est un autre fait.
    """
    signaux: list[Signal] = []
    for jour in _jours_regardes(etat):
        if jour.precipitations is not None and jour.precipitations >= SEUIL_FORTES_PLUIES_MM:
            signaux.append(Signal(
                theme=THEME_METEO,
                cle_unique=f"pluie:{jour.jour.isoformat()}",
                priorite=_priorite_meteo(etat, jour.jour),
                expire_le=_fin_du_jour(jour.jour),
                donnees={
                    "jour": jour.jour.isoformat(), "precipitations_mm": jour.precipitations,
                    "seuil_mm": SEUIL_FORTES_PLUIES_MM,
                },
            ))

    if not etat.cultures:
        return signaux
    a_venir = {j.jour: j for j in etat.previsions}
    serie = [a_venir.get(etat.aujourd_hui + timedelta(days=i)) for i in range(JOURS_CHAUDS_SECHERESSE)]
    chaud_et_sec = all(
        j is not None and j.temp_max is not None and j.temp_max >= SEUIL_CHALEUR_C
        and j.precipitations is not None and j.precipitations < SEUIL_PLUIE_UTILE_MM
        for j in serie
    )
    if not chaud_et_sec:
        return signaux
    dernier = _dernier_arrosage(etat)
    if dernier is not None and (etat.aujourd_hui - dernier).days < JOURS_SANS_ARROSAGE:
        return signaux
    if dernier is not None:
        cle = f"secheresse:arrosage-du:{dernier.isoformat()}"
    else:
        annee, semaine, _ = etat.aujourd_hui.isocalendar()
        cle = f"secheresse:aucun-arrosage:{annee}-S{semaine:02d}"
    signaux.append(Signal(
        theme=THEME_SUIVIS,
        cle_unique=cle,
        priorite=PRIORITE_NORMALE,
        expire_le=_fin_du_jour(etat.aujourd_hui + timedelta(days=JOURS_CHAUDS_SECHERESSE - 1)),
        donnees={
            "dernier_arrosage": dernier.isoformat() if dernier else None,
            "jours_sans_arrosage_min": JOURS_SANS_ARROSAGE,
            "jours": [
                {"jour": j.jour.isoformat(), "temp_max": j.temp_max, "precipitations_mm": j.precipitations}
                for j in serie
            ],
            "cultures": sorted({c.culture for c in etat.cultures}),
        },
    ))
    return signaux


def _cle_lot(lot: LotPepiniere) -> str:
    return f"lot-{lot.numero}" if lot.numero is not None else f"lot-{_slug(lot.lot_id)}"


def _donnees_lot(lot: LotPepiniere, **plus) -> dict:
    return {
        "lot_id": lot.lot_id, "numero": lot.numero, "culture": lot.culture, "variete": lot.variete,
        "date_semis": lot.date_semis.isoformat() if lot.date_semis else None, **plus,
    }


def detecter_echeances_lots(etat: EtatPotager) -> list[Signal]:
    """Un lot de pépinière à repiquer ou à mettre en terre (fourchette ouverte ou dépassée).

    L'action est celle que `echeances_lots` suggère déjà (sans modèle) ; le détecteur ne
    recalcule rien. Un signal par lot et par action : le repiquage, puis la mise en terre.
    """
    signaux: list[Signal] = []
    for lot in etat.lots:
        if lot.action not in (ACTION_REPIQUER, ACTION_METTRE_EN_TERRE):
            continue
        if lot.echeance_au is not None and lot.echeance_au >= etat.aujourd_hui:
            expire = _fin_du_jour(lot.echeance_au)
        else:
            expire = etat.maintenant + DUREE_PERTINENCE
        signaux.append(Signal(
            theme=THEME_ECHEANCES,
            cle_unique=f"{lot.action}:{_cle_lot(lot)}",
            priorite=PRIORITE_NORMALE,
            expire_le=expire,
            donnees=_donnees_lot(
                lot, action=lot.action,
                du=lot.echeance_du.isoformat() if lot.echeance_du else None,
                au=lot.echeance_au.isoformat() if lot.echeance_au else None,
                en_retard=lot.echeance_au is not None and lot.echeance_au < etat.aujourd_hui,
            ),
        ))
    return signaux


def detecter_recolte_imminente(etat: EtatPotager) -> list[Signal]:
    """Une culture plantée dont l'âge dépasse le seuil de son organe (`alerte_recolte`).

    La même règle que le « ⚠️ récolte imminente » de `/plan` (CA4) : un semis en place
    n'en relève pas, comme au bot.
    """
    signaux: list[Signal] = []
    for culture in etat.cultures:
        if culture.est_semis or not alerte_recolte(culture.type_organe, culture.age_jours):
            continue
        depuis = culture.date_plantation.isoformat() if culture.date_plantation else "inconnue"
        signaux.append(Signal(
            theme=THEME_ECHEANCES,
            cle_unique=f"recolte:{_cle_parcelle(culture)}:{_slug(culture.culture)}:{depuis}",
            priorite=PRIORITE_NORMALE,
            expire_le=etat.maintenant + DUREE_PERTINENCE,
            donnees=_culture_en_donnees(
                culture, parcelle_id=culture.parcelle_id, parcelle=culture.parcelle_nom,
                type_organe=culture.type_organe, age_jours=culture.age_jours,
                seuil_jours=SEUIL_ALERTE[culture.type_organe],
                date_plantation=culture.date_plantation.isoformat() if culture.date_plantation else None,
            ),
        ))
    return signaux


def detecter_levee_non_notee(etat: EtatPotager) -> list[Signal]:
    """Un semis plus vieux que sa durée de levée (`DureeCulturale`), sans levée notée.

    Sans durée de levée connue, ou sans date de semis, pas de signal ; un lot dont toutes
    les graines sont déjà parties en godet n'attend plus de levée.
    """
    signaux: list[Signal] = []
    for lot in etat.lots:
        if lot.levee_notee or lot.graines_en_attente <= 0:
            continue
        if lot.date_semis is None or lot.duree_levee_max_jours is None:
            continue
        attendue_le = lot.date_semis + timedelta(days=lot.duree_levee_max_jours)
        if etat.aujourd_hui <= attendue_le:
            continue
        signaux.append(Signal(
            theme=THEME_SUIVIS,
            cle_unique=f"levee:{_cle_lot(lot)}",
            priorite=PRIORITE_NORMALE,
            expire_le=etat.maintenant + DUREE_PERTINENCE,
            donnees=_donnees_lot(
                lot, graines_en_attente=lot.graines_en_attente,
                duree_levee_max_jours=lot.duree_levee_max_jours,
                levee_attendue_le=attendue_le.isoformat(),
                jours_depuis_semis=(etat.aujourd_hui - lot.date_semis).days,
            ),
        ))
    return signaux


def detecter_rappels_echus(etat: EtatPotager) -> list[Signal]:
    """[US-268 / CA4] Un rappel confirmé dont l'heure est venue : un signal « rappels », immédiat.

    Le rappel ne vieillit pas en silence : le signal reste pertinent 3 jours après l'échéance
    (plage de silence du jardinier, message groupé). Une clé par rappel : jamais deux messages.
    """
    return [
        Signal(
            theme=THEME_RAPPELS,
            cle_unique=f"rappel:{rappel.rappel_id}",
            priorite=PRIORITE_IMMEDIATE,
            expire_le=max(etat.maintenant, rappel.echeance_le) + timedelta(days=3),
            donnees={
                "objet": rappel.objet, "echeance_le": rappel.echeance_le.date().isoformat(),
                "rappel_id": rappel.rappel_id,
                **({"cible_type": rappel.cible_type, "cible_id": rappel.cible_id} if rappel.cible_type else {}),
            },
        )
        for rappel in etat.rappels if rappel.echeance_le <= etat.maintenant
    ]


def _fin_du_mois(jour: date) -> date:
    suivant = date(jour.year + (jour.month == 12), jour.month % 12 + 1, 1)
    return suivant - timedelta(days=1)


def detecter_fenetres_semis(etat: EtatPotager) -> list[Signal]:
    """Les fenêtres de semis (`FenetreCulturale`, zone du potager) qui s'ouvrent ce mois-ci.

    Un seul signal par mois, qui les cite toutes : les cultures déjà cultivées dans ce
    potager d'abord, puis les autres, `NB_FENETRES_MAX` au plus.
    """
    mois = etat.aujourd_hui.month
    ouvertes = [f for f in etat.fenetres_semis if f.mois_debut == mois]
    if not ouvertes:
        return []
    vues: set[tuple[str, str]] = set()
    cultures: list[dict] = []
    for fenetre in sorted(ouvertes, key=lambda f: (not f.deja_cultivee, f.culture, f.phase)):
        if (fenetre.culture, fenetre.phase) in vues:
            continue
        vues.add((fenetre.culture, fenetre.phase))
        cultures.append({
            "culture": fenetre.culture, "phase": fenetre.phase,
            "mois_debut": fenetre.mois_debut, "mois_fin": fenetre.mois_fin,
            "deja_cultivee": fenetre.deja_cultivee,
        })
    return [Signal(
        theme=THEME_SUGGESTIONS,
        cle_unique=f"semis:{etat.aujourd_hui.year:04d}-{mois:02d}",
        priorite=PRIORITE_RESUME,
        expire_le=_fin_du_jour(_fin_du_mois(etat.aujourd_hui)),
        donnees={
            "mois": f"{etat.aujourd_hui.year:04d}-{mois:02d}",
            "cultures": cultures[:NB_FENETRES_MAX],
            "total": len(cultures),
        },
    )]


def detecter_bilan_semaine(etat: EtatPotager) -> list[Signal]:
    """Le bilan des 7 derniers jours : gestes par type, récoltes par culture.

    Planifié le dimanche à 18 h (`job_bilan_semaine`). Une semaine sans aucun geste ne
    fait pas de bilan : rien n'est inventé pour remplir un message.
    """
    debut = etat.aujourd_hui - timedelta(days=JOURS_BILAN - 1)
    gestes = [
        g for g in etat.journal
        if debut <= g.jour <= etat.aujourd_hui and g.type_action and g.texte_original != TEXTE_METEO_AUTO
    ]
    if not gestes:
        return []
    par_type: dict[str, int] = {}
    recoltes: dict[tuple[str, str], float] = {}
    for geste in gestes:
        par_type[geste.type_action] = par_type.get(geste.type_action, 0) + 1
        if geste.type_action == "recolte" and geste.culture:
            cle = (geste.culture, geste.unite or "")
            recoltes[cle] = recoltes.get(cle, 0.0) + (geste.quantite or 0.0)
    annee, semaine, _ = etat.aujourd_hui.isocalendar()
    return [Signal(
        theme=THEME_RESUME,
        cle_unique=f"bilan:{annee}-S{semaine:02d}",
        priorite=PRIORITE_RESUME,
        expire_le=etat.maintenant + timedelta(days=1),
        donnees={
            "du": debut.isoformat(), "au": etat.aujourd_hui.isoformat(),
            "nb_gestes": len(gestes),
            "par_type": dict(sorted(par_type.items())),
            "recoltes": [
                {"culture": culture, "quantite": round(quantite, 2), "unite": unite or None}
                for (culture, unite), quantite in sorted(recoltes.items())
            ],
        },
    )]


# ═════════════════════════════════════════════════════════════════════════════
# Les passages
# ═════════════════════════════════════════════════════════════════════════════
#: Le passage horaire (CA5). Le bilan a son propre rendez-vous, le dimanche à 18 h.
DETECTEURS_HORAIRES: tuple[Detecteur, ...] = (
    detecter_gel_canicule,
    detecter_pluie_secheresse,
    detecter_echeances_lots,
    detecter_recolte_imminente,
    detecter_levee_non_notee,
    detecter_rappels_echus,
    detecter_fenetres_semis,
)
DETECTEURS_HEBDOMADAIRES: tuple[Detecteur, ...] = (detecter_bilan_semaine,)


def detecter(etat: EtatPotager, detecteurs: Iterable[Detecteur] = DETECTEURS_HORAIRES) -> list[Signal]:
    """Passe les détecteurs sur l'état d'un potager ; une clé n'est rendue qu'une fois.

    Un détecteur qui échoue est journalisé et sauté : il ne prive pas les autres.
    """
    signaux: list[Signal] = []
    cles: set[str] = set()
    for detecteur in detecteurs:
        try:
            trouves = detecteur(etat)
        except Exception:  # noqa: BLE001 — un détecteur en panne ne fait pas taire les autres
            log.exception("[US-266] Détecteur %s en échec (potager %s)", detecteur.__name__, etat.potager_id)
            continue
        for signal in trouves:
            if signal.cle_unique not in cles:
                cles.add(signal.cle_unique)
                signaux.append(signal)
    return signaux

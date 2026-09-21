"""
app/services/recalage_calendrier.py — Calendrier recalé sur les événements réels [US-070]
---------------------------------------------------------------------------------------
Devant une parcelle où la culture est déjà en place, la période CONSEILLÉE
(US-068, US-176) ne répond plus à rien : le jardinier a semé, il sait quand. Ce
module répond à la seule question qui reste — *où en est cette culture, et
quand est-ce que je la récolte* — en partant de la date RÉELLE du semis et des
durées du référentiel.

Il LIT et PROJETTE, rien d'autre (CA13) : aucun événement écrit, aucun stock ni
statistique recalculé. Il ne sert que l'écran Plan (`GET /plan/calendriers`).

Six décisions, et où elles vivent
---------------------------------
1. **Le SEMIS d'abord, la plantation à défaut (CA1, CA11 ; US-177 / CA7, CA8).**
   Le semis de la parcelle, ou celui d'où découle une plantation par le chaînage
   existant (`plantation.source_evenement_ids` → mise en godet →
   `origine_graines_id`, US-029 / US-065). À défaut seulement — plant acheté en
   jardinerie, ail, fraise — la plantation devient l'origine, avec la durée
   plantation → première récolte du référentiel (US-177). Sans cette durée, rien
   n'est projeté : la tuile garde la frise conseillée, plantation comprise.
   L'ordre est écrit dans `ancrer_serie`, et nulle part ailleurs.
2. **Le contexte de semis n'est pas deviné (CA11).** Un semis sans contexte
   (US-069) n'est pas recalé. Seule exception, et ce n'est pas une supposition :
   un semis chaîné à une mise en godet EST un semis de pépinière — la même
   preuve que la reprise de `migration_v47`.
3. **Une durée absente ne s'emprunte pas (CA11).** Sans durée semis → première
   récolte chiffrée (absente, ou mention « vivace »), pas de recalage : la tuile
   reste sur la frise conseillée et la durée restante en tiret.
4. **La plantation réelle fait foi (CA4).** Plantée hors de la fourchette du
   délai de repiquage, la récolte attendue se décale d'autant — mesuré au bord
   de fourchette le plus proche, jamais au milieu.
5. **Les séries ne se fusionnent pas (CA10).** Chaque semis est une série ; la
   projection porte sur la plus ancienne encore en place. Une récolte est
   rattachée à la plus ancienne série ouverte à sa date ; pour une culture
   végétative, elle la CLÔT (récolte terminale, CA6).
6. **Une fourchette reste une fourchette (CA3).** Dates attendues et jours
   restants sont rendus en (début, fin) ; aucune date unique n'est calculée.

Quatre états mensuels, lus par la frise (CA7) : semis (dans sa filière),
plantation, en croissance — de la levée à la première récolte attendue — et
récolte. Un mois sans aucun reste neutre.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date as _date, datetime, timedelta
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.services import calendrier_cultural as svc_calendrier
from app.services import contexte_semis as svc_contexte
from database.models import Evenement, Parcelle
from utils.culture_resolve import normaliser_culture

log = logging.getLogger("potager")

# ── Vocabulaire ──────────────────────────────────────────────────────────────
ACTION_SEMIS = "semis"
ACTION_GODET = "mise_en_godet"
ACTION_PLANTATION = "plantation"
ACTION_RECOLTE = "recolte"

ORGANE_VEGETATIF = "végétatif"

#: [CA10] Une série plus ancienne que ce délai n'est plus « en place » : le
#: calendrier est annuel, une culture pluriannuelle porte une mention (« vivace »)
#: et n'est de toute façon pas projetée.
HORIZON_SERIE_JOURS = 365

#: Récolte attendue encore à venir à la date de référence.
ETAT_A_VENIR = "a_venir"
#: Date de référence DANS la fourchette de première récolte attendue.
ETAT_RECOLTE_ATTENDUE = "recolte_attendue"
#: [CA12] Fourchette dépassée sans récolte constatée — dit, jamais masqué.
ETAT_RECOLTE_DEPASSEE = "recolte_depassee"
#: [CA5] Au moins une récolte réelle : le réel remplace l'attendu.
ETAT_EN_RECOLTE = "en_recolte"
#: [CA11] Aucun recalage possible — la tuile garde la frise conseillée.
ETAT_SANS_RECALAGE = "sans_recalage"

MOTIF_REFERENTIEL_ABSENT = "referentiel_absent"
#: [US-177 / CA7] Plantation sans semis connu ET sans durée plantation → récolte
#: au référentiel : rien n'est projeté, rien n'est emprunté.
MOTIF_PLANTATION_SANS_SEMIS = "plantation_sans_semis"
MOTIF_CONTEXTE_INCONNU = "contexte_inconnu"
MOTIF_DUREE_RECOLTE_ABSENTE = "duree_recolte_absente"

#: [US-177 / CA8] D'où part la projection d'une série. Le semis prime toujours.
ORIGINE_SEMIS = "semis"
ORIGINE_PLANTATION = "plantation"

#: [US-194 / CA1] La PHASE DU MOMENT d'une ligne en place — le dernier geste
#: connu, jamais une supposition. À ne pas confondre avec `ETAT_*` ci-dessus :
#: l'état dit où en est la RÉCOLTE ATTENDUE et disparaît sans référentiel, la
#: phase dit ce que le jardinier voit dans sa parcelle et existe toujours.
PHASE_SEMEE = "semee"
PHASE_EN_PLACE = "en_place"
PHASE_EN_RECOLTE = "en_recolte"
PHASES: tuple[str, ...] = (PHASE_SEMEE, PHASE_EN_PLACE, PHASE_EN_RECOLTE)

#: [US-194 / CA5] D'où vient `phase_depuis` — une levée ATTENDUE ne se présente
#: jamais comme constatée, c'est ce champ qui le dit à l'affichage.
DEPUIS_RECOLTE = "recolte"
DEPUIS_PLANTATION = "plantation"
DEPUIS_LEVEE_ATTENDUE = "levee_attendue"
DEPUIS_SEMIS = "semis"

#: Clés de `mois` — les phases du référentiel, plus l'état « en croissance ».
ETAT_CROISSANCE = "croissance"
CLES_MOIS: tuple[str, ...] = (
    svc_calendrier.PHASE_SEMIS_PEPINIERE,
    svc_calendrier.PHASE_SEMIS_PLEINE_TERRE,
    svc_calendrier.PHASE_PLANTATION,
    ETAT_CROISSANCE,
    svc_calendrier.PHASE_RECOLTE,
)


# ── Modèle de lecture ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Geste:
    """Un événement réel, réduit à ce que la projection lit."""
    id: int
    action: str
    jour: _date
    parcelle_id: Optional[int]
    culture: str
    variete: str = ""
    contexte_semis: Optional[str] = None
    origine_graines_id: Optional[int] = None
    source_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class Serie:
    """[CA1, CA10] Une série de culture dans une parcelle : son origine réelle."""
    semis: Optional[Geste]
    plantation: Optional[Geste]
    #: Filière du semis : dite (US-069), ou pépinière prouvée par le chaînage.
    contexte: Optional[str]

    @property
    def origine(self) -> Geste:
        return self.semis or self.plantation  # type: ignore[return-value]


@dataclass(frozen=True)
class Projection:
    parcelle_id: int
    culture: str
    variete: str
    etat: str
    motif: Optional[str] = None
    origine: Optional[Geste] = None
    contexte: Optional[str] = None
    plantation_reelle: Optional[_date] = None
    decalage_plantation_jours: Optional[int] = None
    levee_attendue: Optional[tuple[_date, _date]] = None
    recolte_attendue: Optional[tuple[_date, _date]] = None
    recolte_reelle: Optional[tuple[_date, _date]] = None
    jours_restants: Optional[tuple[int, int]] = None
    retard_jours: Optional[int] = None
    series_suivantes: int = 0
    prochaine_plage_semis: Optional[dict] = None
    mois: Optional[dict[str, list[int]]] = None

    def en_dict(self) -> dict:
        """Forme servie par l'API — des dates ISO, jamais une date unique (CA3)."""
        def plage(valeurs, cles=("debut", "fin")):
            return dict(zip(cles, (v.isoformat() for v in valeurs))) if valeurs else None

        return {
            "parcelle_id": self.parcelle_id,
            "culture": self.culture,
            "variete": self.variete,
            "etat": self.etat,
            "motif": self.motif,
            "origine": (
                {"action": self.origine.action, "date": self.origine.jour.isoformat(),
                 "contexte": self.contexte}
                if self.origine else None
            ),
            "plantation_reelle": self.plantation_reelle.isoformat() if self.plantation_reelle else None,
            "decalage_plantation_jours": self.decalage_plantation_jours,
            "levee_attendue": plage(self.levee_attendue),
            "recolte_attendue": plage(self.recolte_attendue),
            "recolte_reelle": plage(self.recolte_reelle, ("premiere", "derniere")),
            "jours_restants": (
                {"min": self.jours_restants[0], "max": self.jours_restants[1]}
                if self.jours_restants else None
            ),
            "retard_jours": self.retard_jours,
            "series_suivantes": self.series_suivantes,
            "prochaine_plage_semis": self.prochaine_plage_semis,
            "mois": self.mois,
        }


# ── Outils de dates ──────────────────────────────────────────────────────────
def _mois_entre(debut: _date, fin: _date) -> list[int]:
    """Mois 1..12 couverts de `debut` à `fin` inclus, dans l'ordre, au plus douze."""
    if fin < debut:
        return []
    mois: list[int] = []
    annee, m = debut.year, debut.month
    while (annee, m) <= (fin.year, fin.month) and len(mois) < 12:
        if m not in mois:
            mois.append(m)
        annee, m = (annee + 1, 1) if m == 12 else (annee, m + 1)
    return mois


def _fin_de_mois(annee: int, mois: int) -> _date:
    suivant = _date(annee + 1, 1, 1) if mois == 12 else _date(annee, mois + 1, 1)
    return suivant - timedelta(days=1)


def _fin_de_fenetre(depart: _date, fenetre) -> Optional[_date]:
    """[CA6] Dernier jour de la fenêtre conseillée qui CONTIENT `depart`, ou None
    si `depart` tombe hors fenêtre — une récolte hors saison ne s'étire pas sur
    une fenêtre qui ne la concerne pas."""
    if fenetre is None or depart.month not in fenetre.mois:
        return None
    annee, m = depart.year, depart.month
    while m != fenetre.mois_fin:
        annee, m = (annee + 1, 1) if m == 12 else (annee, m + 1)
    return _fin_de_mois(annee, m)


def _jours(duree) -> Optional[tuple[int, int]]:
    """Fourchette chiffrée d'une durée lue ; None pour une durée absente ou une mention."""
    if duree is None or duree.jours_min is None:
        return None
    return duree.jours_min, duree.jours_max if duree.jours_max is not None else duree.jours_min


# ── Ancrage : d'où part la projection (CA1, CA11 ; US-177 / CA7, CA8) ────────
@dataclass(frozen=True)
class Ancrage:
    """Le point de départ d'une projection et la durée qui s'y rapporte."""
    mode: str
    depart: _date
    duree_recolte: tuple[int, int]


def ancrer_serie(serie: Serie, itineraire) -> tuple[Optional[Ancrage], Optional[str]]:
    """
    [US-070 / CA1, CA11 ; US-177 / CA7, CA8] D'où part la projection d'une série,
    ou le motif qui l'empêche. **Seul endroit où cette règle est écrite.**

    L'ordre est la règle, et il ne se discute pas : le SEMIS d'abord, avec sa
    durée semis → première récolte. C'est l'origine la plus informative — elle
    seule donne une levée, et elle porte le décalage de plantation réelle (CA4).
    La plantation ne sert qu'en son ABSENCE, avec la durée d'US-177, et pour un
    plant acheté c'est la seule origine qui existe.

    Un semis présent dont la durée manque n'emprunte PAS celle de la plantation :
    les deux ne comptent pas depuis le même geste, et les mélanger produirait une
    date que le référentiel n'a jamais dite. Le mode dégradé est préféré.
    """
    if serie.semis is not None:
        if serie.contexte not in svc_contexte.CONTEXTES:
            return None, MOTIF_CONTEXTE_INCONNU
        duree = _jours(itineraire.duree(svc_calendrier.ETAPE_RECOLTE))
        if duree is None:
            return None, MOTIF_DUREE_RECOLTE_ABSENTE
        return Ancrage(ORIGINE_SEMIS, serie.semis.jour, duree), None

    if serie.plantation is not None:
        duree = _jours(itineraire.duree(svc_calendrier.ETAPE_PLANTATION_RECOLTE))
        if duree is not None:
            return Ancrage(ORIGINE_PLANTATION, serie.plantation.jour, duree), None
    return None, MOTIF_PLANTATION_SANS_SEMIS


# ── Séries (CA1, CA10) ───────────────────────────────────────────────────────
def construire_series(
    origines: list[Geste], index: dict[int, Geste]
) -> list[Serie]:
    """
    [CA1] Séries d'une tuile, de la plus ancienne à la plus récente.

    `origines` : semis et plantations de la tuile (même parcelle, culture,
    variété). `index` : tous les gestes par id, pour remonter le chaînage.
    Un semis déjà rattaché à une plantation de la tuile n'ouvre pas une seconde
    série ; plusieurs plantations d'un même semis n'en font qu'une.
    """
    series: dict[object, Serie] = {}
    for plantation in sorted((g for g in origines if g.action == ACTION_PLANTATION), key=lambda g: g.jour):
        semis = semis_chaine(plantation, index)
        cle = ("semis", semis.id) if semis else ("plantation", plantation.id)
        if cle in series:
            continue
        contexte = (semis.contexte_semis or svc_contexte.CONTEXTE_PEPINIERE) if semis else None
        series[cle] = Serie(semis=semis, plantation=plantation, contexte=contexte)
    for semis in (g for g in origines if g.action == ACTION_SEMIS):
        cle = ("semis", semis.id)
        if cle not in series:
            series[cle] = Serie(semis=semis, plantation=None, contexte=semis.contexte_semis)
    return sorted(series.values(), key=lambda s: (s.origine.jour, s.origine.id))


def semis_chaine(plantation: Geste, index: dict[int, Geste]) -> Optional[Geste]:
    """[CA1] Semis d'où découle une plantation : plantation → godet(s) → semis.
    Plusieurs lots : le plus ancien semis. Aucun rapprochement par culture ou par
    date — seulement le chaînage enregistré."""
    trouves = []
    for source_id in plantation.source_ids:
        godet = index.get(source_id)
        if godet is None:
            continue
        if godet.action == ACTION_SEMIS:
            trouves.append(godet)
            continue
        semis = index.get(godet.origine_graines_id) if godet.origine_graines_id else None
        if semis is not None and semis.action == ACTION_SEMIS:
            trouves.append(semis)
    return min(trouves, key=lambda g: (g.jour, g.id)) if trouves else None


def rattacher_recoltes(
    series: list[Serie], recoltes: list[Geste], organe: Optional[str]
) -> tuple[list[list[Geste]], list[bool]]:
    """
    [CA5, CA6, CA10] Récoltes de chaque série et série close ou non.

    Chaque récolte va à la plus ancienne série OUVERTE dont l'origine la
    précède. Pour une culture végétative, la récolte est terminale : elle clôt
    sa série, et la suivante est projetée. Une récolte reproductrice s'étale et
    ne clôt rien.
    """
    par_serie: list[list[Geste]] = [[] for _ in series]
    close = [False] * len(series)
    for recolte in sorted(recoltes, key=lambda g: (g.jour, g.id)):
        for i, serie in enumerate(series):
            if not close[i] and serie.origine.jour <= recolte.jour:
                par_serie[i].append(recolte)
                if organe == ORGANE_VEGETATIF:
                    close[i] = True
                break
    return par_serie, close


# ── Projection (CA2-CA9, CA11, CA12) ─────────────────────────────────────────
def prochaine_plage_semis(itineraire, contexte: Optional[str], date_ref: _date) -> Optional[dict]:
    """[CA9] Ce qui reste de la fenêtre de semis de la filière à la date de
    référence — de quoi échelonner une deuxième série. None si la fenêtre est
    terminée, inconnue, ou si la filière ne l'est pas."""
    phase = svc_contexte.phase_du_contexte(contexte)
    fenetre = itineraire.fenetre(phase) if (itineraire is not None and phase) else None
    if fenetre is None:
        return None
    mois_ref = date_ref.month
    if mois_ref in fenetre.mois:
        debut = mois_ref
    elif fenetre.mois_debut <= fenetre.mois_fin and mois_ref < fenetre.mois_debut:
        debut = fenetre.mois_debut
    else:
        return None
    return {
        "phase": phase,
        "libelle": svc_calendrier.LIBELLES_PHASES[phase],
        "mois_debut": debut,
        "mois_fin": fenetre.mois_fin,
        "affichage": svc_calendrier.formater_fenetre(debut, fenetre.mois_fin),
    }


def projeter_serie(
    *,
    parcelle_id: int,
    culture: str,
    variete: str,
    serie: Serie,
    recoltes: list[Geste],
    itineraire,
    organe: Optional[str],
    date_ref: _date,
    series_suivantes: int = 0,
) -> Projection:
    """
    [CA2-CA9, CA11, CA12] Projection d'UNE série à la date de référence.

    `itineraire` est l'`ItineraireLu` affiché par la tuile (US-176 / CA5), ou None
    sans référentiel. Ne lève jamais : ce qui manque se dit par un état.
    """
    commun = dict(parcelle_id=parcelle_id, culture=culture, variete=variete,
                  origine=serie.origine, contexte=serie.contexte,
                  plantation_reelle=serie.plantation.jour if serie.plantation else None,
                  series_suivantes=series_suivantes)

    def sans_recalage(motif: str) -> Projection:
        return Projection(
            etat=ETAT_SANS_RECALAGE, motif=motif,
            prochaine_plage_semis=prochaine_plage_semis(itineraire, serie.contexte, date_ref),
            **commun,
        )

    if itineraire is None or itineraire.implicite:
        return sans_recalage(MOTIF_REFERENTIEL_ABSENT)
    ancrage, motif = ancrer_serie(serie, itineraire)
    if ancrage is None:
        return sans_recalage(motif)  # type: ignore[arg-type]

    base, duree_recolte = ancrage.depart, ancrage.duree_recolte
    depuis_plantation = ancrage.mode == ORIGINE_PLANTATION

    # [CA4] Plantation réelle hors du délai de repiquage conseillé : décalage.
    # Sans objet quand la plantation EST l'origine (US-177) : il n'y a alors
    # aucun semis dont elle pourrait s'écarter.
    decalage = 0
    repiquage = None if depuis_plantation else _jours(itineraire.duree(svc_calendrier.ETAPE_REPIQUAGE))
    if serie.plantation is not None and repiquage is not None:
        au_plus_tot = base + timedelta(days=repiquage[0])
        au_plus_tard = base + timedelta(days=repiquage[1])
        if serie.plantation.jour > au_plus_tard:
            decalage = (serie.plantation.jour - au_plus_tard).days
        elif serie.plantation.jour < au_plus_tot:
            decalage = (serie.plantation.jour - au_plus_tot).days

    # La levée se compte depuis le SEMIS : un plant mis en place a déjà levé, et
    # lui appliquer ce délai annoncerait une germination qui a eu lieu ailleurs.
    duree_levee = None if depuis_plantation else _jours(itineraire.duree(svc_calendrier.ETAPE_LEVEE))
    levee = (
        (base + timedelta(days=duree_levee[0]), base + timedelta(days=duree_levee[1]))
        if duree_levee else None
    )
    attendue = (
        base + timedelta(days=duree_recolte[0] + decalage),
        base + timedelta(days=duree_recolte[1] + decalage),
    )
    reelle = (recoltes[0].jour, recoltes[-1].jour) if recoltes else None

    # [CA3, CA5, CA12] État à la date de référence.
    jours_restants = retard = None
    if reelle:
        etat = ETAT_EN_RECOLTE
    elif date_ref < attendue[0]:
        etat = ETAT_A_VENIR
        jours_restants = ((attendue[0] - date_ref).days, (attendue[1] - date_ref).days)
    elif date_ref <= attendue[1]:
        etat = ETAT_RECOLTE_ATTENDUE
        jours_restants = (0, (attendue[1] - date_ref).days)
    else:
        etat = ETAT_RECOLTE_DEPASSEE
        retard = (date_ref - attendue[1]).days

    # [CA5, CA6] Période de récolte : réelle dès qu'elle existe ; terminale pour
    # une culture végétative, étalée jusqu'à la fin de la fenêtre conseillée pour
    # une reproductrice.
    debut_recolte, fin_recolte = reelle if reelle else attendue
    if organe != ORGANE_VEGETATIF:
        fin_fenetre = _fin_de_fenetre(debut_recolte, itineraire.fenetre(svc_calendrier.PHASE_RECOLTE))
        if fin_fenetre and fin_fenetre > fin_recolte:
            fin_recolte = fin_fenetre

    # [CA7] Quatre états mensuels, « en croissance » sans chevauchement.
    phase_semis = svc_contexte.phase_du_contexte(serie.contexte)
    mois: dict[str, list[int]] = {cle: [] for cle in CLES_MOIS}
    if phase_semis is not None:
        mois[phase_semis] = [base.month]
    if serie.plantation is not None:
        mois[svc_calendrier.PHASE_PLANTATION] = [serie.plantation.jour.month]
    mois[svc_calendrier.PHASE_RECOLTE] = _mois_entre(debut_recolte, fin_recolte)
    debut_croissance = levee[0] if levee else base + timedelta(days=1)
    pris = {m for cle, valeurs in mois.items() for m in valeurs}
    mois[ETAT_CROISSANCE] = [
        m for m in _mois_entre(debut_croissance, debut_recolte - timedelta(days=1)) if m not in pris
    ]

    return Projection(
        etat=etat,
        decalage_plantation_jours=decalage if serie.plantation is not None and repiquage else None,
        levee_attendue=levee,
        recolte_attendue=attendue,
        recolte_reelle=reelle,
        jours_restants=jours_restants,
        retard_jours=retard,
        prochaine_plage_semis=prochaine_plage_semis(itineraire, serie.contexte, date_ref),
        mois=mois,
        **commun,
    )


@dataclass(frozen=True)
class SerieRetenue:
    """[CA10 ; US-194 / CA1] La série d'une tuile qui porte sa lecture, ses
    récoltes rattachées et le compte des autres — jamais une moyenne."""
    serie: Serie
    recoltes: list[Geste]
    series_suivantes: int
    nb_series: int


def serie_retenue(
    origines: list[Geste], recoltes: list[Geste], index: dict[int, Geste],
    organe: Optional[str], date_ref: _date,
) -> Optional[SerieRetenue]:
    """
    [CA10 ; US-194 / CA1, CA3] La plus ancienne série encore OUVERTE d'une tuile,
    ou la dernière si toutes sont closes (culture végétative entièrement
    récoltée). **Seul endroit où cette sélection est écrite** : la projection
    (US-070) et la phase du moment (US-194) lisent donc la même série.
    """
    horizon = date_ref - timedelta(days=HORIZON_SERIE_JOURS)
    series = [s for s in construire_series(origines, index) if s.origine.jour >= horizon]
    if not series:
        return None
    par_serie, close = rattacher_recoltes(series, recoltes, organe)
    ouvertes = [i for i, c in enumerate(close) if not c]
    retenue = ouvertes[0] if ouvertes else len(series) - 1
    return SerieRetenue(
        serie=series[retenue],
        recoltes=par_serie[retenue],
        series_suivantes=sum(1 for i in ouvertes if i > retenue),
        nb_series=len(series),
    )


def projeter_tuile(
    *,
    parcelle_id: int,
    culture: str,
    variete: str,
    origines: list[Geste],
    recoltes: list[Geste],
    index: dict[int, Geste],
    itineraire,
    organe: Optional[str],
    date_ref: _date,
) -> Optional[Projection]:
    """[CA10] Projection d'une tuile : la plus ancienne série encore en place,
    les suivantes comptées — jamais une moyenne. None sans aucune série."""
    retenue = serie_retenue(origines, recoltes, index, organe, date_ref)
    if retenue is None:
        return None
    return projeter_serie(
        parcelle_id=parcelle_id, culture=culture, variete=variete,
        serie=retenue.serie, recoltes=retenue.recoltes, itineraire=itineraire,
        organe=organe, date_ref=date_ref, series_suivantes=retenue.series_suivantes,
    )


# ── Phase du moment (US-194) ─────────────────────────────────────────────────
@dataclass(frozen=True)
class PhaseDuMoment:
    """[US-194 / CA1, CA5] Ce que le jardinier voit dans sa parcelle à la date de
    référence : un mot, la date depuis laquelle il vaut, et d'où vient cette date."""
    phase: str
    depuis: _date
    nature: str
    nb_series: int = 1

    def en_dict(self) -> dict:
        return {
            "phase": self.phase,
            "phase_depuis": self.depuis.isoformat(),
            "phase_depuis_nature": self.nature,
            "nb_series": self.nb_series,
        }


def phase_de_serie(
    serie: Serie, recoltes: list[Geste], itineraire, date_ref: _date,
) -> tuple[str, _date, str]:
    """
    [US-194 / CA1, CA2, CA5] La phase du moment d'UNE série et sa date de début.
    **Seul endroit où cette règle est écrite** — aucun autre fichier, front
    compris, ne recalcule une phase.

    L'ordre EST la règle :
    1. une récolte rattachée → **en récolte**, depuis la première (le réel prime) ;
    2. une plantation → **en place**, depuis elle : le plant a levé ailleurs, et
       lui appliquer un délai de levée annoncerait une germination déjà passée ;
    3. un semis dont la levée attendue est atteinte → **en place**, depuis le
       DÉBUT de la fourchette — une date attendue, que `nature` dit attendue ;
    4. sinon → **semée**, depuis le semis. Un semis dont le référentiel ne donne
       aucun délai de levée y reste jusqu'à sa première récolte : c'est le dernier
       geste CONNU, pas une supposition (⚖️ arbitrage d'US-194).

    Ne lève jamais et rend toujours une phase, même sans référentiel (CA2).
    """
    if recoltes:
        return PHASE_EN_RECOLTE, recoltes[0].jour, DEPUIS_RECOLTE
    if serie.semis is None:
        return PHASE_EN_PLACE, serie.plantation.jour, DEPUIS_PLANTATION  # type: ignore[union-attr]
    if serie.plantation is not None:
        return PHASE_EN_PLACE, serie.plantation.jour, DEPUIS_PLANTATION

    duree_levee = (
        _jours(itineraire.duree(svc_calendrier.ETAPE_LEVEE))
        if itineraire is not None and not itineraire.implicite else None
    )
    if duree_levee is not None:
        levee_debut = serie.semis.jour + timedelta(days=duree_levee[0])
        if date_ref >= levee_debut:
            return PHASE_EN_PLACE, levee_debut, DEPUIS_LEVEE_ATTENDUE
    return PHASE_SEMEE, serie.semis.jour, DEPUIS_SEMIS


def phase_de_tuile(
    *,
    origines: list[Geste],
    recoltes: list[Geste],
    index: dict[int, Geste],
    itineraire,
    organe: Optional[str],
    date_ref: _date,
) -> Optional[PhaseDuMoment]:
    """[US-194 / CA1, CA3] Phase du moment d'une tuile — celle de la série
    retenue, avec le nombre de séries à côté. None sans aucune série."""
    retenue = serie_retenue(origines, recoltes, index, organe, date_ref)
    if retenue is None:
        return None
    phase, depuis, nature = phase_de_serie(
        retenue.serie, retenue.recoltes, itineraire, date_ref
    )
    return PhaseDuMoment(phase=phase, depuis=depuis, nature=nature, nb_series=retenue.nb_series)


# ── Lecture en base ──────────────────────────────────────────────────────────
def _variete(valeur: Optional[str]) -> str:
    return (valeur or "").strip().lower()


def _geste(evenement: Evenement) -> Optional[Geste]:
    if evenement.date is None or not evenement.culture:
        return None
    jour = evenement.date.date() if isinstance(evenement.date, datetime) else evenement.date
    source_ids = tuple(
        int(i) for i in (evenement.source_evenement_ids or "").split(";") if i.strip().isdigit()
    )
    return Geste(
        id=evenement.id,
        action=evenement.type_action,
        jour=jour,
        parcelle_id=evenement.parcelle_id,
        culture=normaliser_culture(evenement.culture),
        variete=_variete(evenement.variete),
        contexte_semis=getattr(evenement, "contexte_semis", None),
        origine_graines_id=evenement.origine_graines_id,
        source_ids=source_ids,
    )


@dataclass(frozen=True)
class TuileLue:
    """[US-194 / CA1] Une tuile du Plan (parcelle × culture × variété) et tout ce
    dont sa lecture a besoin. `culture` / `variete` sont normalisées — ce sont les
    clés ; `nom_culture` / `nom_variete` sont ce qui a été dicté, pour l'affichage."""
    parcelle_id: int
    culture: str
    variete: str
    nom_culture: str
    nom_variete: str
    origines: list[Geste]
    recoltes: list[Geste]
    itineraire: object
    organe: Optional[str]


def lire_tuiles(
    db: Session, cultures: Iterable[str], potager_id: Optional[int], date_ref: _date
) -> tuple[list[TuileLue], dict[int, Geste]]:
    """
    [CA1, CA5, CA8 ; US-194 / CA1, CA7] Les tuiles des cultures demandées et
    l'index de tous les gestes, en UNE lecture des événements.

    **Seul endroit où le plan est lu en base** : la projection (US-070) et la
    phase du moment (US-194) en partent toutes les deux, donc d'exactement les
    mêmes séries — deux règles ne peuvent pas diverger sur les mêmes tuiles.

    Les événements postérieurs à `date_ref` sont ignorés (US-030) : reculer la
    date de référence replace toute la lecture à cette date (CA8).
    """
    demandees = {normaliser_culture(c) for c in cultures if c and c.strip()}
    if not demandees:
        return [], {}

    plancher = datetime.combine(date_ref - timedelta(days=2 * HORIZON_SERIE_JOURS), datetime.min.time())
    plafond = datetime.combine(date_ref, datetime.max.time())
    requete = (
        db.query(Evenement)
        .filter(Evenement.type_action.in_([ACTION_SEMIS, ACTION_GODET, ACTION_PLANTATION, ACTION_RECOLTE]))
        .filter(Evenement.date.isnot(None), Evenement.date >= plancher, Evenement.date <= plafond)
    )
    if potager_id is not None:
        requete = requete.filter(Evenement.potager_id == potager_id)
    bruts = {e.id: e for e in requete.all()}
    gestes = [g for g in (_geste(e) for e in bruts.values()) if g is not None]
    index = {g.id: g for g in gestes}

    # Tuiles : une origine rattachée à une parcelle, clé comme l'occupation du Plan.
    tuiles: dict[tuple[int, str, str], list[Geste]] = {}
    noms: dict[tuple[int, str, str], tuple[str, str]] = {}
    # Un semis de pépinière dont une plantation découle a quitté sa parcelle
    # d'origine : il n'y ouvre pas une série de plus.
    semis_plantes = {
        s.id for s in (semis_chaine(g, index) for g in gestes if g.action == ACTION_PLANTATION) if s
    }
    for g in gestes:
        if g.action == ACTION_SEMIS and g.id in semis_plantes:
            continue
        if g.culture in demandees and g.parcelle_id is not None and g.action in (ACTION_SEMIS, ACTION_PLANTATION):
            cle = (g.parcelle_id, g.culture, g.variete)
            tuiles.setdefault(cle, []).append(g)
            noms.setdefault(cle, (bruts[g.id].culture, bruts[g.id].variete or ""))

    # [CA5] Récoltes : celles de la parcelle ; une récolte sans parcelle ne va à
    # une tuile que si la culture n'est en place que dans UNE parcelle.
    parcelles_par_culture: dict[str, set[int]] = {}
    for parcelle_id, culture, _v in tuiles:
        parcelles_par_culture.setdefault(culture, set()).add(parcelle_id)
    recoltes = [g for g in gestes if g.action == ACTION_RECOLTE and g.culture in demandees]

    calendriers: dict[str, object] = {}
    organes: dict[str, Optional[str]] = {}
    lues: list[TuileLue] = []
    for (parcelle_id, culture, variete), origines in tuiles.items():
        if culture not in calendriers:
            lu = svc_calendrier.lire_calendrier(db, culture, potager_id)
            calendriers[culture] = lu.itineraires[0] if lu.itineraires else None
            fiches = svc_calendrier.fiches_visibles(db, culture, potager_id)
            organes[culture] = fiches[0].type_organe_recolte if fiches else None
        seules = parcelles_par_culture.get(culture, set()) == {parcelle_id}
        recoltes_tuile = [
            r for r in recoltes
            if r.culture == culture
            and (r.parcelle_id == parcelle_id or (r.parcelle_id is None and seules))
            and (r.variete in ("", variete))
        ]
        lues.append(TuileLue(
            parcelle_id=parcelle_id, culture=culture, variete=variete,
            nom_culture=noms[(parcelle_id, culture, variete)][0],
            nom_variete=noms[(parcelle_id, culture, variete)][1],
            origines=origines, recoltes=recoltes_tuile,
            itineraire=calendriers[culture], organe=organes[culture],
        ))
    return lues, index


def projections_du_plan(
    db: Session, cultures: Iterable[str], potager_id: Optional[int], date_ref: _date
) -> list[dict]:
    """
    [CA1-CA12] Projection de chaque tuile (parcelle × culture × variété) des
    cultures demandées, à la date de référence.
    """
    lues, index = lire_tuiles(db, cultures, potager_id, date_ref)
    resultat: list[dict] = []
    for tuile in lues:
        projection = projeter_tuile(
            parcelle_id=tuile.parcelle_id, culture=tuile.nom_culture,
            variete=tuile.nom_variete, origines=tuile.origines,
            recoltes=tuile.recoltes, index=index, itineraire=tuile.itineraire,
            organe=tuile.organe, date_ref=date_ref,
        )
        if projection is not None:
            resultat.append(projection.en_dict())

    # [US-183 / CA8] La fiche calendrier s'ouvre aussi depuis Stocks, qui n'a pas
    # la liste des parcelles : chaque série porte le nom de la sienne. Une lecture
    # pour toutes les tuiles, jamais une par série.
    ids = {p["parcelle_id"] for p in resultat}
    noms_parcelles = (
        dict(db.query(Parcelle.id, Parcelle.nom).filter(Parcelle.id.in_(ids)).all()) if ids else {}
    )
    for p in resultat:
        p["parcelle_nom"] = noms_parcelles.get(p["parcelle_id"])

    log.info(
        "[US-070] Recalage du plan : potager_id=%s date_ref=%s tuiles=%d recalees=%d",
        potager_id, date_ref.isoformat(), len(resultat),
        sum(1 for p in resultat if p["etat"] != ETAT_SANS_RECALAGE),
    )
    return resultat


def phases_du_plan(
    db: Session, cultures: Iterable[str], potager_id: Optional[int], date_ref: _date
) -> dict[tuple[int, str, str], dict]:
    """
    [US-194 / CA1, CA4, CA6, CA7, CA8] Phase du moment de chaque ligne en place,
    indexée par `(parcelle_id, culture normalisée, variété normalisée)` — la clé
    que l'écran Plan reconstitue pour ses lignes d'occupation.

    Lecture seule, exactement la même que `projections_du_plan` : aucune
    écriture, aucun stock, aucune projection ni confiance touchés (CA8).

    [CA4] Un semis en PÉPINIÈRE n'est pas une culture en place : il n'a pas de
    phase. Même exclusion que `calcul_occupation_parcelles` — une série née d'un
    semis, sans plantation, dans une parcelle `est_pepiniere`, est écartée. Une
    PLANTATION dans une parcelle de pépinière, elle, reste en place, comme dans
    l'occupation.
    """
    lues, index = lire_tuiles(db, cultures, potager_id, date_ref)
    if not lues:
        return {}

    ids = {t.parcelle_id for t in lues}
    pepinieres = {
        pid for pid, est in
        db.query(Parcelle.id, Parcelle.est_pepiniere).filter(Parcelle.id.in_(ids)).all()
        if est
    }

    resultat: dict[tuple[int, str, str], dict] = {}
    for tuile in lues:
        retenue = serie_retenue(
            tuile.origines, tuile.recoltes, index, tuile.organe, date_ref
        )
        if retenue is None:
            continue
        # [CA4] L'exclusion porte sur l'ORIGINE de la série, pas sur la phase :
        # un semis de pépinière levé reste un semis de pépinière, il n'est pas
        # pour autant une culture en place.
        if tuile.parcelle_id in pepinieres and retenue.serie.plantation is None:
            continue
        phase, depuis, nature = phase_de_serie(
            retenue.serie, retenue.recoltes, tuile.itineraire, date_ref
        )
        resultat[(tuile.parcelle_id, tuile.culture, tuile.variete)] = PhaseDuMoment(
            phase=phase, depuis=depuis, nature=nature, nb_series=retenue.nb_series,
        ).en_dict()

    log.info(
        "[US-194] Phases du plan : potager_id=%s date_ref=%s lignes=%d",
        potager_id, date_ref.isoformat(), len(resultat),
    )
    return resultat

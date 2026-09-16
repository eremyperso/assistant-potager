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
1. **L'origine est un SEMIS, jamais une plantation (CA1, CA11).** Le semis de la
   parcelle, ou celui d'où découle une plantation par le chaînage existant
   (`plantation.source_evenement_ids` → mise en godet → `origine_graines_id`,
   US-029 / US-065). Une plantation sans semis retrouvé (plant acheté, ail)
   n'est PAS projetée : le référentiel n'a aucune durée plantation → récolte
   (US-177). La tuile garde alors la frise conseillée, plantation comprise.
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
from database.models import Evenement
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
MOTIF_PLANTATION_SANS_SEMIS = "plantation_sans_semis"
MOTIF_CONTEXTE_INCONNU = "contexte_inconnu"
MOTIF_DUREE_RECOLTE_ABSENTE = "duree_recolte_absente"

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
    if serie.semis is None:
        return sans_recalage(MOTIF_PLANTATION_SANS_SEMIS)
    if serie.contexte not in svc_contexte.CONTEXTES:
        return sans_recalage(MOTIF_CONTEXTE_INCONNU)
    duree_recolte = _jours(itineraire.duree(svc_calendrier.ETAPE_RECOLTE))
    if duree_recolte is None:
        return sans_recalage(MOTIF_DUREE_RECOLTE_ABSENTE)

    base = serie.semis.jour

    # [CA4] Plantation réelle hors du délai de repiquage conseillé : décalage.
    decalage = 0
    repiquage = _jours(itineraire.duree(svc_calendrier.ETAPE_REPIQUAGE))
    if serie.plantation is not None and repiquage is not None:
        au_plus_tot = base + timedelta(days=repiquage[0])
        au_plus_tard = base + timedelta(days=repiquage[1])
        if serie.plantation.jour > au_plus_tard:
            decalage = (serie.plantation.jour - au_plus_tard).days
        elif serie.plantation.jour < au_plus_tot:
            decalage = (serie.plantation.jour - au_plus_tot).days

    duree_levee = _jours(itineraire.duree(svc_calendrier.ETAPE_LEVEE))
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
    horizon = date_ref - timedelta(days=HORIZON_SERIE_JOURS)
    series = [s for s in construire_series(origines, index) if s.origine.jour >= horizon]
    if not series:
        return None
    par_serie, close = rattacher_recoltes(series, recoltes, organe)
    ouvertes = [i for i, c in enumerate(close) if not c]
    # Toutes closes (culture végétative entièrement récoltée) : la dernière.
    retenue = ouvertes[0] if ouvertes else len(series) - 1
    suivantes = sum(1 for i in ouvertes if i > retenue)
    return projeter_serie(
        parcelle_id=parcelle_id, culture=culture, variete=variete,
        serie=series[retenue], recoltes=par_serie[retenue], itineraire=itineraire,
        organe=organe, date_ref=date_ref, series_suivantes=suivantes,
    )


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


def projections_du_plan(
    db: Session, cultures: Iterable[str], potager_id: Optional[int], date_ref: _date
) -> list[dict]:
    """
    [CA1-CA12] Projection de chaque tuile (parcelle × culture × variété) des
    cultures demandées, à la date de référence — en une lecture des événements.

    Les événements postérieurs à `date_ref` sont ignorés (US-030) : reculer la
    date de référence replace toute la projection à cette date (CA8).
    """
    demandees = {normaliser_culture(c) for c in cultures if c and c.strip()}
    if not demandees:
        return []

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
    resultat: list[dict] = []
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
        projection = projeter_tuile(
            parcelle_id=parcelle_id, culture=noms[(parcelle_id, culture, variete)][0],
            variete=noms[(parcelle_id, culture, variete)][1],
            origines=origines, recoltes=recoltes_tuile, index=index,
            itineraire=calendriers[culture], organe=organes[culture], date_ref=date_ref,
        )
        if projection is not None:
            resultat.append(projection.en_dict())

    log.info(
        "[US-070] Recalage du plan : potager_id=%s date_ref=%s tuiles=%d recalees=%d",
        potager_id, date_ref.isoformat(), len(resultat),
        sum(1 for p in resultat if p["etat"] != ETAT_SANS_RECALAGE),
    )
    return resultat

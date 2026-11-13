"""
[US-320] Étapes d'une culture en place, prévues puis validées.

Une culture en place ne dit plus seulement sa « phase » (US-194, trois valeurs) :
elle suit une **séquence d'étapes**, chacune **prévue** (d'après son calendrier
recalé, US-070 / US-183) ou **validée** (un geste confirmé du jardinier).

Séquences (arbitrage P3 du 12/11/2026 — « En croissance » et « En fleur » ne sont
pas retenues : aucun geste ne les porte) :

* semis direct en pleine terre : Semé → Levé → En récolte → Terminé ;
* plant (pépinière ou achat)   : Planté → En récolte → Terminé.

Ce que valide chaque étape — toujours un geste, jamais l'horloge (E3) :

* Semé    : le semis ;                 * Planté : la plantation ;
* Levé    : une levée rattachée au semis (US-212, étendue au semis direct) ;
* En récolte : la première récolte rattachée à la série ;
* Terminé : une **fin de culture** (« culture terminée », « arraché »), ou une
  ligne **soldée** — récoltée jusqu'au dernier pied (végétatif) ou perdue en
  totalité — qui n'est plus dans l'occupation du Plan.

Une étape prévue dont la date est atteinte devient « à confirmer » ; « Pas encore »
la repousse de trois jours par un rappel (US-266) dont la cible est l'étape de la
série — aucune table nouvelle. Une culture soldée sans fin de culture est « à
libérer » : la fin de culture la libère.

**Seul endroit où ces règles sont écrites** : l'API et l'écran ne font que lire
(E9). La phase d'US-194 reste servie telle quelle à côté (CA10).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date as _date, datetime, timedelta
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.services import calendrier_cultural as svc_calendrier
from app.services import recalage_calendrier as svc_recalage
from app.services.context import TenantContext
from database.models import ActionMenee, Evenement, Parcelle, Rappel
from utils.culture_resolve import normaliser_culture

log = logging.getLogger("potager")

# ── Vocabulaire ──────────────────────────────────────────────────────────────
ETAPE_SEMEE = "semee"
ETAPE_LEVEE = "levee"
ETAPE_PLANTEE = "plantee"
ETAPE_EN_RECOLTE = "en_recolte"
ETAPE_TERMINEE = "terminee"
ETAPES: tuple[str, ...] = (ETAPE_SEMEE, ETAPE_LEVEE, ETAPE_PLANTEE, ETAPE_EN_RECOLTE, ETAPE_TERMINEE)

LIBELLES: dict[str, str] = {
    ETAPE_SEMEE: "Semé",
    ETAPE_LEVEE: "Levé",
    ETAPE_PLANTEE: "Planté",
    ETAPE_EN_RECOLTE: "En récolte",
    ETAPE_TERMINEE: "Terminé",
}

SEQUENCE_SEMIS_DIRECT: tuple[str, ...] = (ETAPE_SEMEE, ETAPE_LEVEE, ETAPE_EN_RECOLTE, ETAPE_TERMINEE)
SEQUENCE_PLANT: tuple[str, ...] = (ETAPE_PLANTEE, ETAPE_EN_RECOLTE, ETAPE_TERMINEE)

STATUT_PREVUE = "prevue"
STATUT_VALIDEE = "validee"
#: Une étape passée que personne n'a notée (une levée jamais dite avant la récolte).
STATUT_NON_NOTEE = "non_notee"

SOURCE_JARDINIER = "jardinier"
SOURCE_COMPAGNON = "compagnon"
SOURCE_CALENDRIER = "calendrier"

#: [E7] « Pas encore » repousse le rappel de trois jours.
REPORT_JOURS = 3
#: Préfixe de `Rappel.cible_type` d'un report d'étape ; `cible_id` = la série (son geste d'origine).
CIBLE_ETAPE = "etape_"
#: [E8] Une ligne soldée depuis plus longtemps est tenue pour libérée : sans cette
#: borne, toutes les cultures récoltées de l'année passée seraient « à libérer »
#: le jour de la livraison.
JOURS_A_LIBERER_MAX = 60


class EtapeError(Exception):
    """[US-320] Un report d'étape impossible : série inconnue ou étape hors séquence."""


# ── Modèle de lecture ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Etape:
    code: str
    statut: str
    date: Optional[_date] = None
    source: Optional[str] = None

    def en_dict(self) -> dict:
        return {
            "code": self.code,
            "libelle": LIBELLES[self.code],
            "statut": self.statut,
            "date": self.date.isoformat() if self.date else None,
            "source": self.source,
        }


@dataclass(frozen=True)
class EtapesCulture:
    """[CA1] L'étape courante d'une culture et toute sa séquence."""
    serie_id: int
    etapes: tuple[Etape, ...]
    courante: Etape
    a_confirmer: bool = False
    a_liberer: bool = False
    rappel_le: Optional[_date] = None

    def en_dict(self) -> dict:
        return {
            "serie_id": self.serie_id,
            "etape": self.courante.code,
            "etape_libelle": LIBELLES[self.courante.code],
            "etape_statut": self.courante.statut,
            "etape_date": self.courante.date.isoformat() if self.courante.date else None,
            "etape_source": self.courante.source,
            "a_confirmer": self.a_confirmer,
            "a_liberer": self.a_liberer,
            "rappel_le": self.rappel_le.isoformat() if self.rappel_le else None,
            "etapes": [e.en_dict() for e in self.etapes],
        }


def sequence(serie: svc_recalage.Serie) -> tuple[str, ...]:
    """[CA2] Un plant (pépinière ou achat) ne passe ni par Semé ni par Levé."""
    return SEQUENCE_PLANT if serie.plantation is not None else SEQUENCE_SEMIS_DIRECT


def _source(geste_id: int, sources: dict[int, str]) -> str:
    return sources.get(geste_id, SOURCE_JARDINIER)


def etapes_de_serie(
    *,
    serie: svc_recalage.Serie,
    recoltes: list[svc_recalage.Geste],
    suivis: Iterable[svc_recalage.Geste] = (),
    soldee_le: Optional[_date] = None,
    itineraire=None,
    recolte_attendue: Optional[tuple[_date, _date]] = None,
    reports: Optional[dict[str, _date]] = None,
    sources: Optional[dict[int, str]] = None,
    date_ref: _date,
) -> EtapesCulture:
    """
    [E1-E8] Les étapes d'UNE série à la date de référence. Fonction pure.

    `suivis` : levées, pertes et fins de culture de la tuile ; `soldee_le` : la date
    à laquelle la ligne a quitté l'occupation sans fin de culture (None si elle est
    en place) ; `reports` : étape → jour jusqu'auquel « Pas encore » la tait.
    """
    sources = sources or {}
    reports = reports or {}
    codes = sequence(serie)
    origine = serie.origine
    debut = origine.jour

    # ── Validées : un geste, jamais l'horloge ────────────────────────────────
    validees: dict[str, Etape] = {}
    if serie.plantation is not None:
        validees[ETAPE_PLANTEE] = Etape(
            ETAPE_PLANTEE, STATUT_VALIDEE, serie.plantation.jour, _source(serie.plantation.id, sources))
    else:
        validees[ETAPE_SEMEE] = Etape(
            ETAPE_SEMEE, STATUT_VALIDEE, serie.semis.jour, _source(serie.semis.id, sources))  # type: ignore[union-attr]
        levees = sorted(
            (g for g in suivis if g.action == svc_recalage.ACTION_LEVEE and g.jour >= debut),
            key=lambda g: (g.jour, g.id),
        )
        if levees:
            validees[ETAPE_LEVEE] = Etape(ETAPE_LEVEE, STATUT_VALIDEE, levees[0].jour, _source(levees[0].id, sources))
    if recoltes:
        premiere = min(recoltes, key=lambda g: (g.jour, g.id))
        validees[ETAPE_EN_RECOLTE] = Etape(
            ETAPE_EN_RECOLTE, STATUT_VALIDEE, premiere.jour, _source(premiere.id, sources))
    fins = sorted(
        (g for g in suivis if g.action == svc_recalage.ACTION_FIN_CULTURE and g.jour >= debut),
        key=lambda g: (g.jour, g.id),
    )
    a_liberer = False
    if fins:
        validees[ETAPE_TERMINEE] = Etape(ETAPE_TERMINEE, STATUT_VALIDEE, fins[0].jour, _source(fins[0].id, sources))
    elif soldee_le is not None:
        # [E5, E8] Récoltée jusqu'au dernier pied, ou tout perdu : terminée, à libérer.
        validees[ETAPE_TERMINEE] = Etape(ETAPE_TERMINEE, STATUT_VALIDEE, soldee_le, SOURCE_JARDINIER)
        a_liberer = (date_ref - soldee_le).days <= JOURS_A_LIBERER_MAX

    # ── Prévues : le calendrier recalé, faute de quoi rien (E2) ──────────────
    prevues: dict[str, _date] = {}
    if serie.plantation is None and itineraire is not None and not getattr(itineraire, "implicite", True):
        duree = svc_recalage._jours(itineraire.duree(svc_calendrier.ETAPE_LEVEE))
        if duree is not None:
            prevues[ETAPE_LEVEE] = debut + timedelta(days=duree[0])
    if recolte_attendue is not None:
        prevues[ETAPE_EN_RECOLTE] = recolte_attendue[0]
        prevues[ETAPE_TERMINEE] = recolte_attendue[1]

    # ── Séquence : passées, courante, à venir ────────────────────────────────
    derniere = max(i for i, c in enumerate(codes) if c in validees)
    etapes: list[Etape] = []
    for i, code in enumerate(codes):
        if code in validees:
            etapes.append(validees[code])
        elif i < derniere:
            etapes.append(Etape(code, STATUT_NON_NOTEE))
        else:
            jour = prevues.get(code)
            etapes.append(Etape(code, STATUT_PREVUE, jour, SOURCE_CALENDRIER if jour else None))

    courante = etapes[derniere]
    a_confirmer = False
    rappel_le: Optional[_date] = None
    if derniere + 1 < len(codes):
        suivante = etapes[derniere + 1]
        if suivante.date is not None and suivante.date <= date_ref:
            report = reports.get(suivante.code)
            if report is not None and report > date_ref:
                rappel_le = report   # [E7] « Pas encore » : on se tait jusque-là
            else:
                courante = suivante  # [E3] prévue et atteinte : à confirmer, jamais validée seule
                a_confirmer = True

    return EtapesCulture(
        serie_id=origine.id, etapes=tuple(etapes), courante=courante,
        a_confirmer=a_confirmer, a_liberer=a_liberer, rappel_le=rappel_le,
    )


# ── Lecture en base ──────────────────────────────────────────────────────────
def _sources(db: Session, ids: set[int]) -> dict[int, str]:
    """Un geste passé par le compagnon (US-261 : il est devenu une action menée) a pour
    source le compagnon ; les autres (journal, données antérieures) le jardinier."""
    if not ids:
        return {}
    lignes = (
        db.query(ActionMenee.cible_id)
        .filter(ActionMenee.cible_type == "evenement", ActionMenee.cible_id.in_(ids))
        .all()
    )
    return {cid: SOURCE_COMPAGNON for (cid,) in lignes}


def _reports(db: Session, potager_id: Optional[int], ids: set[int]) -> dict[int, dict[str, _date]]:
    """[E7] Série → étape → jour jusqu'auquel elle est tue (le report le plus lointain)."""
    if not ids:
        return {}
    q = db.query(Rappel.cible_type, Rappel.cible_id, Rappel.echeance_le).filter(
        Rappel.cible_type.like(f"{CIBLE_ETAPE}%"), Rappel.cible_id.in_(ids), Rappel.etat != "annule",
    )
    if potager_id is not None:
        q = q.filter(Rappel.potager_id == potager_id)
    resultat: dict[int, dict[str, _date]] = {}
    for cible_type, cible_id, echeance in q.all():
        code = cible_type[len(CIBLE_ETAPE):]
        jour = echeance.date() if isinstance(echeance, datetime) else echeance
        actuel = resultat.setdefault(cible_id, {}).get(code)
        if actuel is None or jour > actuel:
            resultat[cible_id][code] = jour
    return resultat


def _cultures_recentes(db: Session, potager_id: Optional[int], date_ref: _date) -> set[str]:
    """Les cultures semées ou plantées dans l'horizon des séries — y compris celles que
    l'occupation ne montre plus, pour trouver ce qui est « à libérer »."""
    plancher = datetime.combine(date_ref - timedelta(days=svc_recalage.HORIZON_SERIE_JOURS), datetime.min.time())
    plafond = datetime.combine(date_ref, datetime.max.time())
    q = (
        db.query(Evenement.culture).distinct()
        .filter(Evenement.type_action.in_((svc_recalage.ACTION_SEMIS, svc_recalage.ACTION_PLANTATION)))
        .filter(Evenement.date >= plancher, Evenement.date <= plafond, Evenement.culture.isnot(None))
    )
    if potager_id is not None:
        q = q.filter(Evenement.potager_id == potager_id)
    return {c for (c,) in q.all() if c}


def cle_ligne(parcelle_id: int, culture: str, variete: Optional[str]) -> tuple[int, str, str]:
    """La clé (parcelle, culture, variété) normalisée, celle de `phases_du_plan` (US-194)."""
    return (parcelle_id, normaliser_culture(culture or ""), (variete or "").strip().lower())


def etapes_du_plan(
    db: Session,
    potager_id: Optional[int],
    date_ref: _date,
    en_place: set[tuple[int, str, str]],
) -> tuple[dict[tuple[int, str, str], dict], list[dict]]:
    """
    [CA1, CA4, CA8, E9] Les étapes de chaque ligne en place (indexées par `cle_ligne`)
    et la liste des cultures **à libérer** — soldées sans fin de culture.

    `en_place` : les clés des lignes de l'occupation du Plan. Lecture seule, la même
    que celle de la phase (`recalage_calendrier.lire_tuiles`).
    """
    lues, index = svc_recalage.lire_tuiles(
        db, _cultures_recentes(db, potager_id, date_ref), potager_id, date_ref,
    )
    if not lues:
        return {}, []
    ids_parcelles = {t.parcelle_id for t in lues}
    parcelles = {
        pid: (nom, bool(est))
        for pid, nom, est in db.query(Parcelle.id, Parcelle.nom, Parcelle.est_pepiniere)
        .filter(Parcelle.id.in_(ids_parcelles)).all()
    }
    ids_gestes = {g.id for t in lues for g in (*t.origines, *t.recoltes, *t.suivis)}
    sources = _sources(db, ids_gestes)
    reports = _reports(db, potager_id, {g.id for t in lues for g in t.origines})

    par_ligne: dict[tuple[int, str, str], dict] = {}
    a_liberer: list[dict] = []
    for tuile in lues:
        # Une ligne replantée après une fin de culture : seule la nouvelle série compte.
        fins_tuile = [g.jour for g in tuile.suivis if g.action == svc_recalage.ACTION_FIN_CULTURE]
        origines = tuile.origines
        if fins_tuile:
            apres = [o for o in origines if o.jour > max(fins_tuile)]
            origines = apres or origines
        retenue = svc_recalage.serie_retenue(origines, tuile.recoltes, index, tuile.organe, date_ref)
        if retenue is None:
            continue
        nom_parcelle, est_pepiniere = parcelles.get(tuile.parcelle_id, (None, False))
        # [US-194 / CA4] Un semis de pépinière n'est pas une culture en place.
        if est_pepiniere and retenue.serie.plantation is None:
            continue
        cle = (tuile.parcelle_id, tuile.culture, tuile.variete)
        dans_le_plan = cle in en_place
        origine = retenue.serie.origine
        suivis = [g for g in tuile.suivis if g.jour >= origine.jour]
        fin = any(g.action == svc_recalage.ACTION_FIN_CULTURE for g in suivis)
        if not dans_le_plan and not fin and retenue.series_suivantes == 0:
            # Soldée : la dernière récolte ou perte de la série dit quand.
            mouvements = [g.jour for g in (*retenue.recoltes, *suivis) if g.action != svc_recalage.ACTION_LEVEE]
            soldee_le: Optional[_date] = max(mouvements) if mouvements else None
            if soldee_le is None:
                continue   # jamais en place (ligne non localisée, pépinière) : rien à dire
        else:
            soldee_le = None
        if not dans_le_plan and not fin and soldee_le is None:
            continue
        projection = svc_recalage.projeter_serie(
            parcelle_id=tuile.parcelle_id, culture=tuile.nom_culture, variete=tuile.nom_variete,
            serie=retenue.serie, recoltes=retenue.recoltes, itineraire=tuile.itineraire,
            organe=tuile.organe, date_ref=date_ref,
        )
        etapes = etapes_de_serie(
            serie=retenue.serie, recoltes=retenue.recoltes, suivis=suivis, soldee_le=soldee_le,
            itineraire=tuile.itineraire, recolte_attendue=projection.recolte_attendue,
            reports=reports.get(origine.id), sources=sources, date_ref=date_ref,
        )
        if dans_le_plan:
            par_ligne[cle] = etapes.en_dict()
        elif etapes.a_liberer:
            a_liberer.append({
                "parcelle_id": tuile.parcelle_id,
                "parcelle_nom": nom_parcelle,
                "culture": tuile.nom_culture,
                "variete": tuile.nom_variete or None,
                **etapes.en_dict(),
            })
    log.info(
        "[US-320] Étapes du plan : potager_id=%s date_ref=%s lignes=%d a_confirmer=%d a_liberer=%d",
        potager_id, date_ref.isoformat(), len(par_ligne),
        sum(1 for e in par_ligne.values() if e["a_confirmer"]), len(a_liberer),
    )
    return par_ligne, a_liberer


# ── Écriture : « Pas encore » ────────────────────────────────────────────────
def reporter_etape(
    db: Session, ctx: TenantContext, serie_id: int, etape: str, aujourd_hui: Optional[_date] = None,
) -> Rappel:
    """
    [E7 / CA9] « Pas encore » : l'étape à confirmer se tait trois jours. Aucune étape
    n'est écrite ; un rappel (US-266) est programmé pour ce jour-là, sur l'étape de la
    série — le compagnon relancera le jardinier. Lève `EtapeError`.
    """
    from app.services.compagnon import rappels as svc_rappels
    from app.services.permissions import require_role

    require_role(ctx, "editor", "reporter une étape")
    if etape not in ETAPES:
        raise EtapeError(f"Étape inconnue : « {etape} ».")
    origine = (
        db.query(Evenement)
        .filter(Evenement.id == serie_id, Evenement.potager_id == ctx.potager_id)
        .filter(Evenement.type_action.in_((svc_recalage.ACTION_SEMIS, svc_recalage.ACTION_PLANTATION)))
        .first()
    )
    if origine is None:
        raise EtapeError("Cette culture n'existe plus dans le potager.")
    if origine.type_action == svc_recalage.ACTION_PLANTATION and etape in (ETAPE_SEMEE, ETAPE_LEVEE):
        raise EtapeError(f"Une culture plantée ne passe pas par l'étape « {LIBELLES[etape]} ».")
    jour = (aujourd_hui or _date.today()) + timedelta(days=REPORT_JOURS)
    lieu = ""
    if origine.parcelle_id:
        parcelle = db.get(Parcelle, origine.parcelle_id)
        lieu = f" ({parcelle.nom})" if parcelle is not None else ""
    objet = f"Vérifier : {LIBELLES[etape].lower()} — {origine.culture}{lieu}"
    cible_type = f"{CIBLE_ETAPE}{etape}"
    deja = (
        db.query(Rappel)
        .filter(Rappel.potager_id == ctx.potager_id, Rappel.cible_type == cible_type,
                Rappel.cible_id == origine.id, Rappel.etat == svc_rappels.ETAT_PROGRAMME)
        .first()
    )
    if deja is not None:
        # Un « Pas encore » redit : le même rappel, repoussé — jamais deux rappels.
        deja.echeance_le = datetime.combine(jour, datetime.min.time()).replace(hour=svc_rappels.HEURE_RAPPEL)
        db.commit()
        log.info("[US-320] « Pas encore » : %s de la série %s repoussée au %s", etape, serie_id, jour.isoformat())
        return deja
    rappel = svc_rappels.programmer(db, ctx, objet, jour, cible_type=cible_type, cible_id=origine.id)
    log.info("[US-320] « Pas encore » : %s de la série %s reportée au %s", etape, serie_id, jour.isoformat())
    return rappel

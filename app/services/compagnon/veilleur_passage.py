"""
app/services/compagnon/veilleur_passage.py — Le passage du veilleur, potager par potager [US-266]
================================================================================================
Le planificateur du bot (`app/bot/veilleur_jobs.py`) appelle `passer` toutes les
heures, et le dimanche à 18 h pour le bilan (CA5). Un passage :

1. liste les potagers actifs, sans potager armé (la table `potagers` n'a pas de RLS) ;
2. lit leurs prévisions en UN appel de service (`previsions_meteo`, cache d'une heure) ;
3. pour CHAQUE potager, sous son propre `tenant_scope` et dans sa propre session,
   lit son état (`lire_etat`), passe les détecteurs purs (`veilleur.detecter`), et
   écrit les signaux nouveaux (`signaux.enregistrer`).

Aucune lecture ne franchit la frontière d'un potager : la session est ouverte DANS le
`tenant_scope` du potager (RLS en production), et chaque requête filtre en plus
explicitement sur son `potager_id` (SQLite, tests). Un potager en échec est journalisé
et sauté ; il ne prive pas les suivants.

Comme `veilleur.py`, ce module ne parle jamais au modèle (R7, test d'AST).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable, Iterable, Optional, TypeVar

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.services import calendrier_cultural as cal
from app.services import echeances_lots as svc_echeances
from app.services import previsions_meteo as svc_previsions
from app.services.compagnon import rappels as svc_rappels
from app.services.compagnon import signaux as svc_signaux
from app.services.compagnon import veilleur
from app.services.context import TenantContext
from database.db import SessionLocal, tenant_scope
from database.models import CultureConfig, Evenement, FenetreCulturale, ItineraireCultural, Potager
from utils.culture_resolve import normaliser_culture
from utils.parcelles import calcul_occupation_parcelles, get_all_parcelles
from utils.stock import calcul_lots_pepiniere, graines_restantes

log = logging.getLogger("potager")

FUSEAU = svc_signaux.FUSEAU

#: Profondeur du journal lu : le bilan (7 jours) et l'arrosage (5 jours) y tiennent.
JOURS_DE_JOURNAL = 14

#: Les phases de semis dont l'ouverture fait une suggestion.
PHASES_SEMIS: tuple[str, ...] = (cal.PHASE_SEMIS_PEPINIERE, cal.PHASE_SEMIS_PLEINE_TERRE)

T = TypeVar("T")


@dataclass(frozen=True)
class PotagerVeille:
    """Ce que le passage garde d'un potager hors de toute session."""

    id: int
    latitude: Optional[float]
    longitude: Optional[float]


def maintenant_local() -> datetime:
    """L'heure du potager (Europe/Paris), sans fuseau — celle des prévisions et des signaux."""
    return datetime.now(FUSEAU).replace(tzinfo=None)


def potagers_a_veiller() -> list[PotagerVeille]:
    """Les potagers actifs : un potager archivé ou supprimé ne reçoit plus d'initiative."""
    with tenant_scope(None):
        db = SessionLocal()
        try:
            lignes = (
                db.query(Potager.id, Potager.latitude, Potager.longitude)
                .filter(Potager.etat == "actif", Potager.supprime_le.is_(None))
                .order_by(Potager.id)
                .all()
            )
        finally:
            db.close()
    return [PotagerVeille(id=i, latitude=lat, longitude=lon) for i, lat, lon in lignes]


# ═════════════════════════════════════════════════════════════════════════════
# Lecture de l'état d'un potager
# ═════════════════════════════════════════════════════════════════════════════
def _jour(valeur) -> Optional[date]:
    if valeur is None:
        return None
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, date):
        return valeur
    try:
        return date.fromisoformat(str(valeur)[:10])
    except ValueError:
        return None


def _flottant(valeur) -> Optional[float]:
    try:
        return float(valeur) if valeur is not None else None
    except (TypeError, ValueError):
        return None


def jours_prevus(lecture: Optional[svc_previsions.LecturePrevision]) -> tuple[veilleur.JourPrevu, ...]:
    """Aujourd'hui et les jours suivants d'une prévision ; rien si elle est indisponible."""
    if lecture is None or not lecture.disponible or not lecture.meteo:
        return ()
    meteo = lecture.meteo
    jours: list[veilleur.JourPrevu] = []
    aujourd_hui = _jour(meteo.get("date"))
    if aujourd_hui is not None:
        jours.append(veilleur.JourPrevu(
            jour=aujourd_hui, temp_min=_flottant(meteo.get("temp_min")),
            temp_max=_flottant(meteo.get("temp_max")), precipitations=_flottant(meteo.get("precipitations")),
        ))
    for prevu in meteo.get("previsions_etendues") or []:
        jour = _jour(prevu.get("date"))
        if jour is None:
            continue
        jours.append(veilleur.JourPrevu(
            jour=jour, temp_min=_flottant(prevu.get("temp_min")),
            temp_max=_flottant(prevu.get("temp_max")), precipitations=_flottant(prevu.get("precipitations")),
        ))
    return tuple(jours)


def _cle_culture(nom: Optional[str]) -> str:
    cle = normaliser_culture(nom or "")
    return cle[:-1] if len(cle) > 3 and cle.endswith("s") else cle


def _rusticites(db: Session, potager_id: int) -> dict[str, float]:
    """Rusticité par culture : la fiche du potager l'emporte sur le référentiel commun."""
    lignes = (
        db.query(CultureConfig.nom, CultureConfig.potager_id, CultureConfig.rusticite_min_c)
        .filter(or_(CultureConfig.potager_id.is_(None), CultureConfig.potager_id == potager_id))
        .filter(CultureConfig.rusticite_min_c.isnot(None))
        .all()
    )
    rusticites: dict[str, float] = {}
    for nom, proprietaire, valeur in sorted(lignes, key=lambda l: l[1] is not None):
        rusticites[_cle_culture(nom)] = float(valeur)
    return rusticites


def cultures_en_place(db: Session, potager_id: int) -> tuple[veilleur.CultureEnPlace, ...]:
    """Les cultures de `/plan` (même calcul), avec leur parcelle et leur rusticité."""
    occupation = calcul_occupation_parcelles(db, None, potager_id=potager_id)
    parcelles = {p.nom.strip().lower(): p for p in get_all_parcelles(db, potager_id=potager_id)}
    rusticites = _rusticites(db, potager_id)
    cultures: list[veilleur.CultureEnPlace] = []
    for nom_parcelle, lignes in occupation.items():
        parcelle = parcelles.get(nom_parcelle.strip().lower()) if nom_parcelle else None
        for ligne in lignes:
            cultures.append(veilleur.CultureEnPlace(
                culture=ligne["culture"], variete=ligne.get("variete"),
                nb_plants=float(ligne.get("nb_plants") or 0), unite=ligne.get("unite"),
                age_jours=int(ligne.get("age_jours") or 0), type_organe=ligne.get("type_organe"),
                date_plantation=_jour(ligne.get("date_plantation")),
                est_semis=ligne.get("type_action") == "semis",
                parcelle_id=parcelle.id if parcelle else None,
                parcelle_nom=parcelle.nom if parcelle else nom_parcelle,
                abri=parcelle.abri if parcelle else None,
                rusticite_min_c=rusticites.get(_cle_culture(ligne["culture"])),
            ))
    return tuple(cultures)


def _duree_levee_max(db: Session, culture: str, potager_id: int, cache: dict) -> Optional[int]:
    """Borne haute de la levée (`DureeCulturale`), lue une fois par culture ; None si inconnue."""
    cle = _cle_culture(culture)
    if cle not in cache:
        duree = None
        try:
            calendrier = cal.lire_calendrier(db, culture, potager_id)
            itineraire = calendrier.itineraires[0] if calendrier.itineraires else None
            lue = itineraire.duree(cal.ETAPE_LEVEE) if itineraire else None
            if lue is not None and lue.jours_min is not None:
                duree = lue.jours_max if lue.jours_max is not None else lue.jours_min
        except LookupError:
            duree = None
        cache[cle] = duree
    return cache[cle]


def _fourchette_de_l_action(echeances: dict, action: Optional[str]) -> tuple[Optional[date], Optional[date]]:
    if action == veilleur.ACTION_REPIQUER:
        bloc = echeances.get("repiquage") or {}
    elif action == veilleur.ACTION_METTRE_EN_TERRE:
        bloc = echeances.get("mise_en_terre") or {}
        if not bloc.get("du"):
            bloc = echeances.get("sortie_prevue") or {}
    else:
        return None, None
    return _jour(bloc.get("du")), _jour(bloc.get("au"))


def lots_de_pepiniere(db: Session, ctx: TenantContext, ref: date) -> tuple[veilleur.LotPepiniere, ...]:
    """Les lots de la Pépinière, l'action que `echeances_lots` leur suggère et leur levée."""
    lots = calcul_lots_pepiniere(db, None, potager_id=ctx.potager_id)
    if not lots:
        return ()
    actions = svc_echeances.echeances_et_actions(db, ctx, lots, ref)
    cache: dict = {}
    sortie: list[veilleur.LotPepiniere] = []
    for lot in lots:
        calcul = actions.get(lot["lot_id"]) or {}
        action = (calcul.get("action_suggeree") or {}).get("code")
        du, au = _fourchette_de_l_action(calcul.get("echeances") or {}, action)
        culture = lot.get("culture") or ""
        sortie.append(veilleur.LotPepiniere(
            lot_id=str(lot["lot_id"]), numero=lot.get("numero_lot"), culture=culture,
            variete=lot.get("variete"), date_semis=_jour(lot.get("date_semis")),
            action=action, echeance_du=du, echeance_au=au,
            levee_notee=lot.get("nb_leves") is not None,
            graines_en_attente=int(graines_restantes(lot) or 0),
            duree_levee_max_jours=_duree_levee_max(db, culture, ctx.potager_id, cache) if culture else None,
        ))
    return tuple(sortie)


def fenetres_de_semis(db: Session, potager_id: int) -> tuple[veilleur.FenetreSemis, ...]:
    """Les fenêtres de semis de la zone du potager (référentiel commun et fiches du potager)."""
    zone, _ = cal.zone_du_potager(db, potager_id)
    lignes = (
        db.query(CultureConfig.nom, FenetreCulturale.phase, FenetreCulturale.mois_debut, FenetreCulturale.mois_fin)
        .join(ItineraireCultural, ItineraireCultural.culture_id == CultureConfig.id)
        .join(FenetreCulturale, FenetreCulturale.itineraire_id == ItineraireCultural.id)
        .filter(FenetreCulturale.phase.in_(PHASES_SEMIS))
        .filter(FenetreCulturale.zone_climatique == zone)
        .filter(
            or_(CultureConfig.potager_id.is_(None), CultureConfig.potager_id == potager_id),
            or_(ItineraireCultural.potager_id.is_(None), ItineraireCultural.potager_id == potager_id),
        )
        .all()
    )
    cultivees = {
        _cle_culture(nom) for (nom,) in db.query(Evenement.culture).filter(
            Evenement.potager_id == potager_id, Evenement.culture.isnot(None),
        ).distinct()
    }
    return tuple(
        veilleur.FenetreSemis(
            culture=nom, phase=phase, mois_debut=debut, mois_fin=fin,
            deja_cultivee=_cle_culture(nom) in cultivees,
        )
        for nom, phase, debut, fin in lignes if debut and fin
    )


def journal_recent(db: Session, potager_id: int, depuis: date) -> tuple[veilleur.GesteDuJournal, ...]:
    """Les gestes du potager depuis `depuis`, hors météo enregistrée automatiquement."""
    lignes = (
        db.query(Evenement.date, Evenement.type_action, Evenement.culture, Evenement.quantite, Evenement.unite)
        .filter(Evenement.potager_id == potager_id, Evenement.date >= datetime.combine(depuis, datetime.min.time()))
        .filter(or_(Evenement.texte_original.is_(None), Evenement.texte_original != veilleur.TEXTE_METEO_AUTO))
        .order_by(Evenement.date)
        .all()
    )
    return tuple(
        veilleur.GesteDuJournal(jour=_jour(quand), type_action=action, culture=culture, quantite=quantite, unite=unite)
        for quand, action, culture, quantite, unite in lignes if quand is not None
    )


def _sans_casser(db: Session, quoi: str, potager_id: int, lire: Callable[[], T], defaut: T) -> T:
    """Une lecture en échec prive les détecteurs de ses données, pas des autres."""
    try:
        return lire()
    except Exception:  # noqa: BLE001
        db.rollback()   # PostgreSQL : une transaction en erreur refuse toute requête suivante
        log.exception("[US-266] Veilleur : lecture « %s » en échec (potager %s)", quoi, potager_id)
        return defaut


def lire_etat(
    db: Session, potager: PotagerVeille, maintenant: datetime,
    lecture_meteo: Optional[svc_previsions.LecturePrevision] = None,
) -> veilleur.EtatPotager:
    """L'état d'UN potager, lu dans une session ouverte sous son `tenant_scope`."""
    pid = potager.id
    ctx = TenantContext(user_id=None, potager_id=pid)
    ref = maintenant.date()
    return veilleur.EtatPotager(
        potager_id=pid,
        maintenant=maintenant,
        cultures=_sans_casser(db, "cultures", pid, lambda: cultures_en_place(db, pid), ()),
        previsions=jours_prevus(lecture_meteo),
        lots=_sans_casser(db, "lots", pid, lambda: lots_de_pepiniere(db, ctx, ref), ()),
        fenetres_semis=_sans_casser(db, "fenêtres", pid, lambda: fenetres_de_semis(db, pid), ()),
        journal=_sans_casser(
            db, "journal", pid, lambda: journal_recent(db, pid, ref - timedelta(days=JOURS_DE_JOURNAL)), (),
        ),
        rappels=_sans_casser(db, "rappels", pid, lambda: rappels_echus(db, pid, maintenant), ()),
    )


def rappels_echus(db: Session, potager_id: int, maintenant: datetime) -> tuple[veilleur.RappelProgramme, ...]:
    """[US-268 / CA4] Les rappels confirmés dont l'heure est venue."""
    return tuple(
        veilleur.RappelProgramme(
            rappel_id=r.id, objet=r.objet, echeance_le=r.echeance_le,
            cible_type=r.cible_type, cible_id=r.cible_id,
        )
        for r in svc_rappels.echus(db, potager_id, maintenant)
    )


def _clore_les_rappels(potager_id: int, etat: veilleur.EtatPotager) -> None:
    """Un rappel dont le signal est en base passe à « échu » : il a parlé, il ne reparlera pas."""
    if not etat.rappels:
        return
    with tenant_scope(potager_id):
        db = SessionLocal()
        try:
            svc_rappels.marquer_echus(db, potager_id, [r.rappel_id for r in etat.rappels])
        finally:
            db.close()


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — Le passage, potager par potager
# ═════════════════════════════════════════════════════════════════════════════
def passer(
    detecteurs: Iterable[veilleur.Detecteur] = veilleur.DETECTEURS_HORAIRES,
    maintenant: Optional[datetime] = None,
    avec_meteo: bool = True,
) -> dict[int, list[str]]:
    """Un passage du veilleur ; rend, par potager, les clés des signaux créés.

    Rien n'est envoyé (US-266) : les signaux sont en base et dans les journaux.
    """
    detecteurs = tuple(detecteurs)
    maintenant = maintenant or maintenant_local()
    potagers = potagers_a_veiller()
    lectures: dict[int, svc_previsions.LecturePrevision] = {}
    if avec_meteo and potagers:
        try:
            lectures = svc_previsions.lire_previsions_potagers(potagers)
        except Exception:  # noqa: BLE001 — sans météo, les autres détecteurs passent quand même
            log.exception("[US-266] Veilleur : prévisions indisponibles")
    resultats: dict[int, list[str]] = {}
    for potager in potagers:
        try:
            with tenant_scope(potager.id):
                db = SessionLocal()
                try:
                    etat = lire_etat(db, potager, maintenant, lectures.get(potager.id))
                finally:
                    db.close()
            signaux = veilleur.detecter(etat, detecteurs)
            resultats[potager.id] = svc_signaux.enregistrer(potager.id, signaux, maintenant)
            if veilleur.detecter_rappels_echus in detecteurs:
                _clore_les_rappels(potager.id, etat)
        except Exception:  # noqa: BLE001 — un potager en échec ne prive pas les suivants
            log.exception("[US-266] Veilleur : passage en échec pour le potager %s", potager.id)
    log.info(
        "[US-266] 👁️  VEILLEUR : %s potager(s) veillé(s), %s signal(aux) nouveau(x) (%s)",
        len(potagers), sum(len(c) for c in resultats.values()),
        ", ".join(d.__name__.removeprefix("detecter_") for d in detecteurs),
    )
    return resultats

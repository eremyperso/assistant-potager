"""
app/services/compagnon/rappels.py — Les rappels de suivi du compagnon [US-268]
------------------------------------------------------------------------------
« Je te fais signe le 3 novembre ? » : après un semis, le compagnon propose de revenir
vérifier la levée. Ce module porte tout ce qui n'est pas Telegram :

  - **La date vient du référentiel** (CA1) : `DureeCulturale` de l'étape, borne haute,
    ajoutée à la date du geste. Aucune durée n'est produite par un modèle ; sans durée
    connue, pas de proposition.
  - **Un rappel est une écriture** (CA2, R9) : `proposer_pour_evenement` et
    `resoudre_date` ne font que LIRE ; seul `programmer` écrit, appelé par le clic
    « Oui, rappelle-moi » ou par la confirmation d'une phrase.
  - **Le rappel libre** (CA3) : « rappelle-moi de tailler les tomates samedi » ; la date est
    résolue par `utils.date_utils` (grammaire d'US-094, mode futur), jamais par le modèle.
  - **L'échéance** (CA4) : le veilleur (`veilleur.detecter_rappels_echus`) en tire un signal
    du thème « rappels », distribué par les règles d'US-267.
  - **Thème coupé** (CA6) : un jardinier qui a coupé « rappels » ne reçoit aucune proposition.

La table `rappels` est celle d'US-266 (migration v65) : aucune migration ici.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from unidecode import unidecode

from app import config
from app.services import calendrier_cultural as cal
from app.services.compagnon import distributeur as regles
from app.services.compagnon import proactivite
from app.services.compagnon.signaux import RAPPEL_PROGRAMME
from app.services.context import TenantContext
from database.models import Evenement, Rappel

log = logging.getLogger("potager")

ETAT_PROGRAMME = RAPPEL_PROGRAMME
ETAT_ECHU = "echu"
ETAT_ANNULE = "annule"

#: L'heure à laquelle un rappel « du jour » est dû (heure locale du potager).
HEURE_RAPPEL = 9
OBJET_LONGUEUR_MAX = 200
#: Un rappel libre se programme dans l'année qui vient, pas plus : au-delà c'est une erreur de date.
HORIZON_MAX_JOURS = 366
#: Au plus ce nombre de rappels en attente par potager : un agenda, pas un journal.
RAPPELS_MAX = 30

CIBLE_EVENEMENT = "evenement"

#: Action de geste → (étape du calendrier qui donne le délai, formule de l'objet).
#: Seul le semis a une durée au référentiel : une reprise de repiquage n'en a pas, et on ne l'invente pas.
ACTIONS_A_RAPPEL: dict[str, tuple[str, str]] = {
    "semis": (cal.ETAPE_LEVEE, "voir où en est la levée des {culture}"),
}

ERREUR_OBJET_VIDE = "Je n'ai rien à te rappeler : dis-moi de quoi, par exemple « rappelle-moi de tailler les tomates samedi »."
ERREUR_OBJET_LONG = f"Ce rappel est trop long : {OBJET_LONGUEUR_MAX} caractères au plus."
ERREUR_DATE = (
    "Je n'ai pas compris pour quand. Dis-le-moi avec un jour (« samedi », « demain », « dans 3 jours », « le 12 novembre »)."
)
ERREUR_PASSE = "Cette date est déjà passée : donne-moi un jour à venir."
ERREUR_LOIN = "C'est trop loin : je programme des rappels dans l'année qui vient."
ERREUR_PLEIN = f"Tu as déjà {RAPPELS_MAX} rappels en attente. Annule-en un avec /rappels avant d'en ajouter."
ERREUR_INCONNU = "Ce rappel n'existe plus."


class RappelError(ValueError):
    """Un rappel refusé : le message est dit tel quel au jardinier."""


@dataclass(frozen=True)
class PropositionRappel:
    """Ce que le compagnon propose : rien n'est écrit tant que le jardinier n'a pas dit oui."""

    objet: str
    echeance: date
    cible_type: Optional[str] = None
    cible_id: Optional[int] = None


# ═════════════════════════════════════════════════════════════════════════════
# CA1, CA6 — La proposition après un geste
# ═════════════════════════════════════════════════════════════════════════════
def actif() -> bool:
    """Le distributeur envoie les messages (`COMPAGNON_PROACTIF=oui`) : sans lui, un rappel ne partirait jamais,
    et le compagnon ne le propose donc pas."""
    return bool(config.COMPAGNON_PROACTIF)


def theme_coupe(db: Session, ctx: TenantContext) -> bool:
    """[CA6] Le jardinier a coupé le thème « rappels » : aucune proposition, aucun rappel libre proposé."""
    return proactivite.lire(db, ctx).mode("rappels") == regles.MODE_COUPE


def _jours_du_referentiel(db: Session, culture: str, potager_id: int, etape: str) -> Optional[int]:
    """Borne haute de la durée de l'étape (`DureeCulturale`) ; None si le référentiel n'en sait rien."""
    try:
        calendrier = cal.lire_calendrier(db, culture, potager_id)
    except LookupError:
        return None
    itineraire = calendrier.itineraires[0] if calendrier.itineraires else None
    lue = itineraire.duree(etape) if itineraire else None
    if lue is None or lue.jours_min is None:
        return None
    return lue.jours_max if lue.jours_max is not None else lue.jours_min


def existe_pour(db: Session, ctx: TenantContext, cible_type: str, cible_id: int) -> bool:
    """Un rappel en attente existe déjà pour cette cible (un double clic ne double pas le rappel)."""
    return db.query(Rappel.id).filter(
        Rappel.potager_id == ctx.potager_id, Rappel.cible_type == cible_type,
        Rappel.cible_id == cible_id, Rappel.etat == ETAT_PROGRAMME,
    ).first() is not None


def proposer_pour_evenement(
    db: Session, ctx: TenantContext, evenement_id: int, aujourd_hui: Optional[date] = None,
) -> Optional[PropositionRappel]:
    """[CA1] Le rappel que mérite un geste enregistré, ou None. Ne lève jamais, n'écrit rien.

    La date est celle du geste augmentée de la durée du référentiel ; une échéance déjà passée
    (semis daté d'il y a trois semaines) ne donne pas de rappel.
    """
    aujourd_hui = aujourd_hui or date.today()
    try:
        evenement = db.query(Evenement).filter(
            Evenement.id == evenement_id, Evenement.potager_id == ctx.potager_id,
        ).first()
        if not actif() or evenement is None or not evenement.culture:
            return None
        regle = ACTIONS_A_RAPPEL.get((evenement.type_action or "").lower())
        if regle is None:
            return None
        if theme_coupe(db, ctx) or existe_pour(db, ctx, CIBLE_EVENEMENT, evenement.id):
            return None
        etape, formule = regle
        jours = _jours_du_referentiel(db, evenement.culture, ctx.potager_id, etape)
        if jours is None:
            return None
        depart = evenement.date.date() if evenement.date else aujourd_hui
        echeance = depart + timedelta(days=jours)
        if echeance <= aujourd_hui:
            return None
        return PropositionRappel(
            objet=formule.format(culture=evenement.culture), echeance=echeance,
            cible_type=CIBLE_EVENEMENT, cible_id=evenement.id,
        )
    except Exception:  # noqa: BLE001 — une proposition est un confort, jamais un échec de saisie
        log.exception("[US-268] Proposition de rappel impossible (événement %s)", evenement_id)
        db.rollback()
        return None


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — La date d'un rappel libre
# ═════════════════════════════════════════════════════════════════════════════
def resoudre_date(texte: str, aujourd_hui: Optional[date] = None) -> date:
    """[CA3] « samedi », « demain », « dans 3 jours », « le 12 novembre » → une date à venir.

    La grammaire est celle d'US-094 en lecture d'avenir. Lève `RappelError` si la phrase ne donne
    pas de date, si elle est passée ou trop lointaine : le code ne devine jamais.
    """
    from utils.date_utils import ANCRAGE_RESOLU, resoudre_ancrage_temporel

    aujourd_hui = aujourd_hui or date.today()
    ancrage = resoudre_ancrage_temporel(texte or "", aujourd_hui=aujourd_hui, futur=True)
    if ancrage.statut != ANCRAGE_RESOLU or not ancrage.date_iso:
        raise RappelError(ERREUR_DATE)
    return _jour_a_venir(date.fromisoformat(ancrage.date_iso), aujourd_hui)


_ISO = re.compile(r"\A\d{4}-\d{2}-\d{2}\Z")
#: Ce qui reste accroché à l'objet une fois la date retirée : « … tomates pour samedi » → « … tomates ».
_PARTICULES_FINALES = frozenset({"le", "la", "pour", "a", "vers", "avant", "d", "de", "du", "ce", "cette", "au"})
#: Une expression de date tient en quatre mots au plus (« dans une semaine », « le 12 novembre »).
_MOTS_DE_DATE_MAX = 4


def _cle(texte: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", unidecode(texte or "").lower()).split())


def objet_et_jour(morceaux: list[str], aujourd_hui: Optional[date] = None) -> tuple[str, date]:
    """[CA3] Sépare « tailler les tomates » de « samedi » dans ce que la commande reçoit.

    Les arguments arrivent soit tels que l'interpréteur les range (objet, puis date ISO ou dite), soit
    mot à mot d'une commande tapée : la date est le plus court suffixe que la grammaire d'US-094 date
    en entier. Lève `RappelError` quand il n'y a ni objet ni date.
    """
    aujourd_hui = aujourd_hui or date.today()
    morceaux = [m.strip() for m in morceaux if m and m.strip()]
    if len(morceaux) >= 2 and _ISO.match(morceaux[-1]):
        try:
            jour = date.fromisoformat(morceaux[-1])
        except ValueError:
            raise RappelError(ERREUR_DATE) from None
        return _objet_valide(" ".join(morceaux[:-1])), _jour_a_venir(jour, aujourd_hui)
    # Les arguments de l'interpréteur arrivent déjà découpés (un morceau peut avoir des espaces) :
    # la date est alors le dernier morceau, en entier.
    if len(morceaux) >= 2 and any(" " in m for m in morceaux):
        return _objet_valide(" ".join(morceaux[:-1])), resoudre_date(morceaux[-1], aujourd_hui)
    mots = morceaux
    for n in range(1, min(_MOTS_DE_DATE_MAX, len(mots) - 1) + 1):
        suffixe = " ".join(mots[-n:])
        if _expression_entiere(suffixe, aujourd_hui):
            objet = mots[:-n]
            while objet and _cle(objet[-1]) in _PARTICULES_FINALES:
                objet.pop()
            return _objet_valide(" ".join(objet)), resoudre_date(suffixe, aujourd_hui)
    if not mots:
        raise RappelError(ERREUR_OBJET_VIDE)
    raise RappelError(ERREUR_DATE)


def _expression_entiere(texte: str, aujourd_hui: date) -> bool:
    from utils.date_utils import ANCRAGE_RESOLU, resoudre_ancrage_temporel

    ancrage = resoudre_ancrage_temporel(texte, aujourd_hui=aujourd_hui, futur=True)
    return ancrage.statut == ANCRAGE_RESOLU and _cle(ancrage.expression or "") == _cle(texte)


def _objet_valide(objet: str) -> str:
    objet = " ".join((objet or "").split()).strip(" :,.!")
    for amorce in ("de ", "d'", "d’", "que ", "qu'", "qu’"):
        if objet.lower().startswith(amorce):
            objet = objet[len(amorce):].strip()
    if not objet:
        raise RappelError(ERREUR_OBJET_VIDE)
    return objet


def _jour_a_venir(jour: date, aujourd_hui: date) -> date:
    if jour < aujourd_hui:
        raise RappelError(ERREUR_PASSE)
    if jour > aujourd_hui + timedelta(days=HORIZON_MAX_JOURS):
        raise RappelError(ERREUR_LOIN)
    return jour


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — L'écriture, après confirmation seulement
# ═════════════════════════════════════════════════════════════════════════════
def programmer(
    db: Session, ctx: TenantContext, objet: str, jour: date,
    cible_type: Optional[str] = None, cible_id: Optional[int] = None,
    proposition_id: Optional[int] = None,
) -> Rappel:
    """[CA2] Crée le rappel. À n'appeler qu'après le clic « Oui, rappelle-moi » ou une phrase confirmée.

    Idempotent sur la cible : un rappel en attente pour le même geste n'est pas recréé.
    """
    objet = " ".join((objet or "").split()).strip(" :,.!")
    if not objet:
        raise RappelError(ERREUR_OBJET_VIDE)
    if len(objet) > OBJET_LONGUEUR_MAX:
        raise RappelError(ERREUR_OBJET_LONG)
    if cible_type and cible_id is not None:
        deja = db.query(Rappel).filter(
            Rappel.potager_id == ctx.potager_id, Rappel.cible_type == cible_type,
            Rappel.cible_id == cible_id, Rappel.etat == ETAT_PROGRAMME,
        ).first()
        if deja is not None:
            return deja
    en_attente = db.query(Rappel.id).filter(
        Rappel.potager_id == ctx.potager_id, Rappel.etat == ETAT_PROGRAMME,
    ).count()
    if en_attente >= RAPPELS_MAX:
        raise RappelError(ERREUR_PLEIN)
    rappel = Rappel(
        user_id=ctx.user_id, potager_id=ctx.potager_id, objet=objet,
        echeance_le=datetime.combine(jour, time(HEURE_RAPPEL)),
        cible_type=cible_type, cible_id=cible_id, etat=ETAT_PROGRAMME, proposition_id=proposition_id,
    )
    db.add(rappel)
    db.commit()
    log.info("[US-268] ⏰ Rappel programmé : %r le %s (potager %s)", objet, jour.isoformat(), ctx.potager_id)
    return rappel


def lister(db: Session, ctx: TenantContext) -> list[Rappel]:
    """[CA5] Les rappels à venir du potager, du plus proche au plus lointain."""
    return (db.query(Rappel)
            .filter(Rappel.potager_id == ctx.potager_id, Rappel.etat == ETAT_PROGRAMME)
            .order_by(Rappel.echeance_le, Rappel.id).all())


def annuler(db: Session, ctx: TenantContext, rappel_id: int) -> Rappel:
    """[CA5] Annule un rappel encore à venir ; un rappel échu ou déjà annulé n'est plus à annuler."""
    rappel = db.query(Rappel).filter(
        Rappel.id == rappel_id, Rappel.potager_id == ctx.potager_id, Rappel.etat == ETAT_PROGRAMME,
    ).first()
    if rappel is None:
        raise RappelError(ERREUR_INCONNU)
    rappel.etat = ETAT_ANNULE
    db.commit()
    log.info("[US-268] Rappel %s annulé (potager %s)", rappel_id, ctx.potager_id)
    return rappel


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — L'échéance, pour le veilleur
# ═════════════════════════════════════════════════════════════════════════════
def echus(db: Session, potager_id: int, maintenant: datetime) -> list[Rappel]:
    """Les rappels programmés dont l'heure est venue (`maintenant` : heure locale du potager)."""
    return (db.query(Rappel)
            .filter(Rappel.potager_id == potager_id, Rappel.etat == ETAT_PROGRAMME,
                    Rappel.echeance_le <= maintenant)
            .order_by(Rappel.echeance_le, Rappel.id).all())


def marquer_echus(db: Session, potager_id: int, ids: list[int]) -> int:
    """Passe les rappels signalés à « échu » : ils quittent `/rappels` et ne sont plus annulables."""
    if not ids:
        return 0
    nombre = (db.query(Rappel)
              .filter(Rappel.potager_id == potager_id, Rappel.id.in_(ids), Rappel.etat == ETAT_PROGRAMME)
              .update({Rappel.etat: ETAT_ECHU}, synchronize_session=False))
    db.commit()
    return nombre


def libelle_jour(jour: date) -> str:
    """« 3 novembre » : le jour dit au jardinier."""
    mois = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre",
            "octobre", "novembre", "décembre")
    return f"{jour.day} {mois[jour.month - 1]}"

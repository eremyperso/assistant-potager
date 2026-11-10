"""
app/services/voix/preferences.py — réglages vocaux du jardinier [US-300 / CA1, CA2, CA3, CA7]
=============================================================================================
Préférence de la PERSONNE (table `preferences_voix`, sans RLS) : le service ne lit et
n'écrit que la ligne du jardinier du contexte. Une lecture sans ligne rend les défauts
et n'écrit rien.
"""
import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app import config
from app.services.context import TenantContext
from app.services.voix.catalogue import VoixInconnueDuCatalogue, lire_catalogue
from database.models import PreferencesVoix

log = logging.getLogger("potager")


@dataclass(frozen=True)
class Preferences:
    mode_vocal: bool
    voix_id: str                    # la voix EFFECTIVE (celle qui sera lue)
    voix_choisie: Optional[str]     # ce que le jardinier a enregistré (None = défaut)
    lecture_auto: bool

    def public(self) -> dict:
        return {"mode_vocal": self.mode_vocal, "voix_id": self.voix_id,
                "lecture_auto": self.lecture_auto}


def _ligne(db: Session, ctx: TenantContext) -> Optional[PreferencesVoix]:
    return db.query(PreferencesVoix).filter(PreferencesVoix.user_id == ctx.user_id).first()


def voix_effective(choisie: Optional[str]) -> str:
    """[CA7] La voix choisie si le catalogue la propose encore, sinon `VOIX_PAR_DEFAUT` —
    sans erreur. Une voix retirée par Mistral ne casse pas la lecture."""
    if choisie and lire_catalogue().trouver(choisie) is not None:
        return choisie
    return config.VOIX_PAR_DEFAUT


def lire(db: Session, ctx: TenantContext) -> Preferences:
    """[CA2] Les réglages du jardinier ; les défauts s'il n'en a jamais enregistré."""
    ligne = _ligne(db, ctx)
    if ligne is None:
        return Preferences(False, voix_effective(None), None, True)
    return Preferences(bool(ligne.mode_vocal), voix_effective(ligne.voix_id),
                       ligne.voix_id, bool(ligne.lecture_auto))


_ABSENT = object()


def enregistrer(db: Session, ctx: TenantContext, *, mode_vocal=_ABSENT, voix_id=_ABSENT,
                lecture_auto=_ABSENT) -> Preferences:
    """[CA3] Enregistre les réglages fournis (les autres restent). `voix_id=None` remet la
    voix par défaut. Une voix absente du catalogue lève `VoixInconnueDuCatalogue`
    (la route répond 422 avec la liste valide). [CA7] Une voix devenue inconnue, déjà
    enregistrée, est corrigée ici (remise à NULL) si le jardinier n'en choisit pas une autre."""
    catalogue = lire_catalogue()
    if voix_id is not _ABSENT and voix_id is not None and catalogue.trouver(voix_id) is None:
        raise VoixInconnueDuCatalogue(voix_id, catalogue.ids())

    ligne = _ligne(db, ctx)
    if ligne is None:
        ligne = PreferencesVoix(user_id=ctx.user_id, mode_vocal=False, voix_id=None, lecture_auto=True)
        db.add(ligne)
    if mode_vocal is not _ABSENT:
        ligne.mode_vocal = bool(mode_vocal)
    if lecture_auto is not _ABSENT:
        ligne.lecture_auto = bool(lecture_auto)
    if voix_id is not _ABSENT:
        ligne.voix_id = voix_id
    elif ligne.voix_id and catalogue.trouver(ligne.voix_id) is None:
        log.info("🔊 VOIX │ préférence corrigée : voix retirée du catalogue │ user=%s", ctx.user_id)
        ligne.voix_id = None
    db.commit()
    return lire(db, ctx)

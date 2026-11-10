"""
app/services/voix/lecture.py — lire à voix haute une réponse du compagnon [US-304 / CA1, CA8, CA9]
==================================================================================================
Ce que fait `POST /compagnon/voix/lecture/{echange_id}` : le résumé parlé de l'échange (US-303),
dit dans la voix du jardinier (US-300), rendu en MP3.

La lecture se fait PAR IDENTIFIANT D'ÉCHANGE : aucun texte venu de la PWA n'est synthétisé
(étude §5.1). Le texte dit est toujours celui que le serveur a calculé pour CET échange, de CE
jardinier, dans CE potager.

Contrôles, dans l'ordre et avant toute dépense :
1. le mode vocal du jardinier (403) ;
2. l'échange existe dans son compte et son potager (404) ;
3. le plafond `VOIX_PLAFOND_LECTURES_JOUR` (429), compté dans `conso_tokens` (type `voix`,
   issue `ok`), comme celui des dictées : aucune table de plus.

Le MP3 n'est jamais écrit en base ni sur disque : la PWA le garde en mémoire le temps de la
session (CA6).
"""
import logging
from datetime import date

from sqlalchemy.orm import Session

from app import config
from app.services.compagnon import conversations as svc_conversations
from app.services.context import TenantContext
from app.services.voix import oral, preferences
from app.services.voix.synthese import synthetiser
from database.models import ConsoTokens
from llm.passerelle import ISSUE_OK, TYPE_VOIX

log = logging.getLogger("potager")

MESSAGE_MODE_VOCAL_ETEINT = "Le mode vocal est éteint : activez-le dans « Mon compagnon »."
MESSAGE_PLAFOND_ATTEINT = "Limite de lectures du jour atteinte."
MESSAGE_LECTURE_INDISPONIBLE = "Lecture indisponible pour le moment"
MESSAGE_ECHANGE_INTROUVABLE = "Échange introuvable"


class LectureRefuseeError(Exception):
    """Une lecture refusée avant la synthèse ; `statut` = réponse HTTP, `code` = motif pour la PWA."""

    statut = 400
    code = "lecture_refusee"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ModeVocalEteintError(LectureRefuseeError):
    statut, code = 403, "mode_vocal_eteint"


class EchangeIntrouvableError(LectureRefuseeError):
    statut, code = 404, "echange_introuvable"


class PlafondLecturesAtteintError(LectureRefuseeError):
    statut, code = 429, "plafond_lectures"


class RienALireError(LectureRefuseeError):
    """Le résumé parlé est vide (réponse faite d'émojis ou de liens seulement)."""

    statut, code = 422, "rien_a_lire"


def lectures_du_jour(db: Session, ctx: TenantContext) -> int:
    """[CA9] Synthèses réussies du jardinier aujourd'hui, tous potagers confondus
    (lues dans la mesure de la passerelle, `conso_tokens`, type `voix`)."""
    return db.query(ConsoTokens).filter(
        ConsoTokens.user_id == ctx.user_id,
        ConsoTokens.appel_type == TYPE_VOIX,
        ConsoTokens.issue == ISSUE_OK,
        ConsoTokens.date == date.today(),
    ).count()


def lire_echange(db: Session, ctx: TenantContext, echange_id: int) -> bytes:
    """[CA1] Le MP3 du résumé parlé de l'échange, dans la voix du jardinier.

    Lève `LectureRefuseeError` (403, 404, 422, 429), `LLMIndisponibleError` ou
    `VoixInconnueError` (la PWA dit « Lecture indisponible pour le moment » — CA8).
    """
    reglages = preferences.lire(db, ctx)
    if not reglages.mode_vocal:
        raise ModeVocalEteintError(MESSAGE_MODE_VOCAL_ETEINT)
    if svc_conversations.lire(ctx, echange_id) is None:
        raise EchangeIntrouvableError(MESSAGE_ECHANGE_INTROUVABLE)
    if lectures_du_jour(db, ctx) >= config.VOIX_PLAFOND_LECTURES_JOUR:
        log.info("🔊 VOIX │ plafond de lectures atteint │ user=%s │ %d/jour",
                 ctx.user_id, config.VOIX_PLAFOND_LECTURES_JOUR)
        raise PlafondLecturesAtteintError(MESSAGE_PLAFOND_ATTEINT)

    try:
        resume = oral.texte_oral(ctx, echange_id)
    except oral.EchangeIntrouvableError:
        raise EchangeIntrouvableError(MESSAGE_ECHANGE_INTROUVABLE)
    try:
        reponse = synthetiser(ctx, resume.texte, reglages.voix_id)
    except ValueError:
        log.info("🔊 VOIX │ lecture : rien à dire │ échange=%s", echange_id)
        raise RienALireError(MESSAGE_LECTURE_INDISPONIBLE)
    log.info("🔊 VOIX │ lecture │ échange=%s │ voix=%s │ %d octets",
             echange_id, reglages.voix_id, len(reponse.audio))
    return reponse.audio

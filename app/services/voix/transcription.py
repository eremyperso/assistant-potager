"""
app/services/voix/transcription.py — dictée envoyée au compagnon [US-302 / CA5, CA7, CA12]
==========================================================================================
Ce que vérifie `POST /compagnon/voix/transcrire` avant et après l'appel à Voxtral :
le mode vocal du jardinier (403), le poids et la durée du fichier (413), le nombre de
dictées du jour (429), puis la longueur du texte rendu (1 000 caractères au plus, comme
une phrase tapée).

Le texte rendu n'est PAS envoyé au compagnon ici : la PWA l'envoie elle-même par
`/compagnon/messages`, le chemin d'une phrase tapée (D4). Une dictée ne crée donc
jamais de geste sans la carte de confirmation (US-274).
"""
import logging
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app import config
from app.services.context import TenantContext
from app.services.voix import preferences
from app.services.voix.dictee import dicter
from database.models import ConsoTokens
from llm.passerelle import ISSUE_OK, TYPE_DICTEE

log = logging.getLogger("potager")

# [CA7] La même borne qu'une phrase tapée (`LONGUEUR_MAX` du panneau, `/compagnon/messages`).
LONGUEUR_MAX_TEXTE = 1000
# Une dictée arrêtée pile à la durée maximale arrive avec quelques dixièmes de plus.
TOLERANCE_DUREE_S = 2.0

MESSAGE_MODE_VOCAL_ETEINT = "Le mode vocal est éteint : activez-le dans « Mon compagnon »."
MESSAGE_DICTEE_TROP_LONGUE = "Dictée trop longue : {duree} s au plus."
MESSAGE_DICTEE_TROP_LOURDE = "Fichier de dictée trop lourd."
MESSAGE_PLAFOND_ATTEINT = "Limite de dictées du jour atteinte."
MESSAGE_TEXTE_TROP_LONG = "Message trop long, découpez-le."
MESSAGE_DICTEE_INDISPONIBLE = "La dictée est indisponible pour le moment, écrivez votre message."


class DicteeRefuseeError(Exception):
    """Une dictée refusée avant ou après la transcription ; `statut` = réponse HTTP,
    `code` = motif lisible par la PWA."""

    statut = 400
    code = "dictee_refusee"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ModeVocalEteintError(DicteeRefuseeError):
    statut, code = 403, "mode_vocal_eteint"


class DicteeTropLongueError(DicteeRefuseeError):
    statut, code = 413, "dictee_trop_longue"


class PlafondDicteesAtteintError(DicteeRefuseeError):
    statut, code = 429, "plafond_dictees"


class TexteDicteTropLongError(DicteeRefuseeError):
    statut, code = 422, "message_trop_long"


def taille_max_octets() -> int:
    return config.VOIX_DICTEE_TAILLE_MAX_KO * 1024


def dictees_du_jour(db: Session, ctx: TenantContext) -> int:
    """[CA12] Dictées réussies du jardinier aujourd'hui, tous potagers confondus
    (lues dans la mesure de la passerelle, `conso_tokens`, sans table de plus)."""
    return db.query(ConsoTokens).filter(
        ConsoTokens.user_id == ctx.user_id,
        ConsoTokens.appel_type == TYPE_DICTEE,
        ConsoTokens.issue == ISSUE_OK,
        ConsoTokens.date == date.today(),
    ).count()


def verifier_avant_transcription(db: Session, ctx: TenantContext, taille: int,
                                 duree_s: Optional[float]) -> None:
    """[CA5, CA12] Refuse une dictée qui ne doit pas partir chez Voxtral (rien n'est facturé)."""
    if not preferences.lire(db, ctx).mode_vocal:
        raise ModeVocalEteintError(MESSAGE_MODE_VOCAL_ETEINT)
    if taille > taille_max_octets():
        raise DicteeTropLongueError(MESSAGE_DICTEE_TROP_LOURDE)
    if duree_s is not None and duree_s > config.VOIX_DICTEE_DUREE_MAX_S + TOLERANCE_DUREE_S:
        raise DicteeTropLongueError(MESSAGE_DICTEE_TROP_LONGUE.format(duree=config.VOIX_DICTEE_DUREE_MAX_S))
    if dictees_du_jour(db, ctx) >= config.VOIX_PLAFOND_DICTEES_JOUR:
        log.info("🎙️  VOIX │ plafond de dictées atteint │ user=%s │ %d/jour",
                 ctx.user_id, config.VOIX_PLAFOND_DICTEES_JOUR)
        raise PlafondDicteesAtteintError(MESSAGE_PLAFOND_ATTEINT)


def transcrire(
    db: Session,
    ctx: TenantContext,
    contenu: bytes,
    nom_fichier: str,
    type_mime: Optional[str] = None,
    duree_s: Optional[float] = None,
) -> str:
    """[CA5] Fichier de la PWA → texte à envoyer au compagnon.

    Rend une chaîne vide si rien n'a été entendu (la PWA le dit, rien n'est envoyé — CA7).
    Lève `DicteeRefuseeError` (403, 413, 422, 429), `ValueError` (fichier vide),
    `LLMIndisponibleError` ou `FormatAudioNonConvertibleError` (la dictée est indisponible).
    """
    verifier_avant_transcription(db, ctx, len(contenu), duree_s)
    texte = dicter(ctx, contenu, nom_fichier, type_mime, duree_s).texte.strip()
    if len(texte) > LONGUEUR_MAX_TEXTE:
        log.info("🎙️  VOIX │ dictée refusée : %d caractères > %d", len(texte), LONGUEUR_MAX_TEXTE)
        raise TexteDicteTropLongError(MESSAGE_TEXTE_TROP_LONG)
    if not texte:
        log.info("🎙️  VOIX │ dictée vide : rien entendu │ user=%s", ctx.user_id)
    return texte

"""
app/services/voix/synthese.py — voix du compagnon [US-299 / CA2, CA5]
=====================================================================
Texte → MP3 par la passerelle (type `voix`, Voxtral). Le texte est nettoyé avant
l'envoi : Markdown, émojis et liens ne se disent pas, et chaque caractère envoyé
est facturé.
"""
import logging
from typing import Optional

from app import config
from app.services.context import TenantContext
from app.services.voix.nettoyage import nettoyer_pour_voix
from llm import passerelle
from llm.passerelle import ReponseVoix, VoixInconnueError

log = logging.getLogger("potager")

# Marie (Voxtral 3, français) par défaut ; réglable par `VOIX_PAR_DEFAUT` (US-300 / CA2).
VOIX_PAR_DEFAUT = config.VOIX_PAR_DEFAUT


def synthetiser(
    ctx: TenantContext,
    texte: str,
    voix_id: Optional[str] = None,
) -> ReponseVoix:
    """Dit `texte` avec la voix `voix_id` (défaut : `VOIX_PAR_DEFAUT`), en MP3.

    Lève `ValueError` si rien ne reste à dire après nettoyage, `VoixInconnueError`
    si la voix est refusée, `LLMIndisponibleError` si le fournisseur ne répond pas.
    """
    a_dire = nettoyer_pour_voix(texte)
    if not a_dire:
        raise ValueError("rien à dire après nettoyage du texte")
    voix = voix_id or config.VOIX_PAR_DEFAUT
    try:
        reponse = passerelle.synthetiser(ctx=ctx, texte=a_dire, voix_id=voix, format_audio="mp3")
    except VoixInconnueError:
        if voix == config.VOIX_PAR_DEFAUT:
            raise
        # [US-300 / CA7] Voix choisie puis retirée par Mistral : la voix par défaut, sans erreur.
        log.warning("⚠️  VOIX │ voix %s inconnue de Mistral → voix par défaut", voix)
        reponse = passerelle.synthetiser(
            ctx=ctx, texte=a_dire, voix_id=config.VOIX_PAR_DEFAUT, format_audio="mp3")
    log.info("🔊 VOIX │ réponse synthétisée │ potager=%s │ %d caractères │ %d octets",
             ctx.potager_id, reponse.nb_caracteres, len(reponse.audio))
    return reponse

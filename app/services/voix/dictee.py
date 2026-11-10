"""
app/services/voix/dictee.py — dictée de la PWA [US-299 / CA1, CA6, CA7]
=======================================================================
Audio enregistré par la PWA → texte, par la passerelle (type `dictee`, Voxtral).
L'audio reste en mémoire ; seule une conversion FFmpeg passe par un fichier
temporaire, supprimé aussitôt (voir `conversion.py`).
"""
import logging
from typing import Optional

from app.services.context import TenantContext
from app.services.voix.conversion import preparer_dictee
from llm import passerelle
from llm.passerelle import ReponseDictee

log = logging.getLogger("potager")


def dicter(
    ctx: TenantContext,
    contenu: bytes,
    nom_fichier: str,
    type_mime: Optional[str] = None,
    duree_s: Optional[float] = None,
) -> ReponseDictee:
    """Transcrit une dictée en français.

    `duree_s` : durée mesurée par la PWA, comptée si le fournisseur ne la rend pas.
    Lève `ValueError` (audio vide), `FormatAudioNonConvertibleError` (conversion
    impossible) ou `LLMIndisponibleError` (fournisseur) — jamais une exception brute.
    """
    if not contenu:
        raise ValueError("dictée vide : aucun audio reçu")
    audio, nom_envoye = preparer_dictee(contenu, nom_fichier, type_mime)
    reponse = passerelle.dicter(
        ctx=ctx, contenu=audio, nom_fichier=nom_envoye, langue="fr", duree_s=duree_s,
    )
    log.info("🎙️  VOIX │ dictée transcrite │ potager=%s │ %d s │ %d caractères",
             ctx.potager_id, reponse.duree_audio_s, len(reponse.texte))
    return reponse

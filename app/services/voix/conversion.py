"""
app/services/voix/conversion.py — conversion FFmpeg d'une dictée [US-299 / CA6, CA7]
====================================================================================
L'essai US-298 a vu `webm` (Chrome, Edge, Android) et `ogg` (Firefox) acceptés tels
quels par Voxtral ; `mp4` (Safari) n'y a pas été essayé. Un format listé dans
`VOIX_FORMATS_A_CONVERTIR` part en WAV mono 16 kHz (format documenté par Mistral).

Les fichiers de travail vivent dans un dossier temporaire supprimé à la sortie,
succès comme échec : l'audio du jardinier ne reste jamais sur le serveur (CA7).
"""
import logging
import os
import shutil
import subprocess
import tempfile
from typing import Optional

from app import config

log = logging.getLogger("potager")

FORMAT_CONVERTI = "wav"
DELAI_FFMPEG_S = 30

# Type MIME rendu par `MediaRecorder` → extension lue par le fournisseur.
_EXTENSION_PAR_MIME = {
    "audio/webm": "webm",
    "audio/ogg":  "ogg",
    "audio/mp4":  "mp4",
    "audio/x-m4a": "m4a",
    "audio/aac":  "aac",
    "audio/mpeg": "mp3",
    "audio/wav":  "wav",
    "audio/x-wav": "wav",
    "audio/flac": "flac",
}


class FormatAudioNonConvertibleError(Exception):
    """[CA6] Le format de la dictée doit être converti, et ne peut pas l'être
    (FFmpeg absent du serveur, ou en échec). Porte le format en cause."""

    def __init__(self, format_audio: str, motif: str) -> None:
        self.format_audio = format_audio
        super().__init__(f"dictée au format « {format_audio} » non convertible : {motif}")


def extension_audio(nom_fichier: str, type_mime: Optional[str] = None) -> str:
    """Extension du fichier audio, en minuscules ; à défaut, déduite du type MIME
    (`audio/webm;codecs=opus` → `webm`). Chaîne vide si rien ne la dit."""
    _, ext = os.path.splitext(nom_fichier or "")
    if ext:
        return ext.lstrip(".").lower()
    if type_mime:
        return _EXTENSION_PAR_MIME.get(type_mime.split(";")[0].strip().lower(), "")
    return ""


def doit_convertir(format_audio: str) -> bool:
    """Le format figure-t-il parmi ceux que Mistral refuse (configuration) ?"""
    return format_audio.lower() in config.VOIX_FORMATS_A_CONVERTIR


def ffmpeg_disponible() -> bool:
    """FFmpeg est-il dans le PATH du serveur ?"""
    return shutil.which("ffmpeg") is not None


def convertir_en_wav(contenu: bytes, format_audio: str) -> bytes:
    """Convertit une dictée en WAV mono 16 kHz. Lève `FormatAudioNonConvertibleError`
    si FFmpeg manque ou échoue ; le dossier de travail est supprimé dans tous les cas."""
    if not ffmpeg_disponible():
        log.warning("⚠️  VOIX │ FFmpeg absent : dictée %s non convertible", format_audio)
        raise FormatAudioNonConvertibleError(format_audio, "FFmpeg n'est pas installé sur le serveur")

    dossier = tempfile.mkdtemp(prefix="potager_voix_")
    try:
        source = os.path.join(dossier, f"dictee.{format_audio or 'audio'}")
        cible = os.path.join(dossier, f"dictee.{FORMAT_CONVERTI}")
        with open(source, "wb") as f:
            f.write(contenu)
        try:
            resultat = subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", source,
                 "-ar", "16000", "-ac", "1", cible],
                capture_output=True, timeout=DELAI_FFMPEG_S, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            raise FormatAudioNonConvertibleError(
                format_audio, f"FFmpeg en échec ({type(e).__name__})") from e
        if resultat.returncode != 0 or not os.path.exists(cible):
            raise FormatAudioNonConvertibleError(
                format_audio, f"FFmpeg en échec (code {resultat.returncode})")
        with open(cible, "rb") as f:
            converti = f.read()
        log.info("🎙️  VOIX │ dictée %s convertie en %s (%d → %d octets)",
                 format_audio, FORMAT_CONVERTI, len(contenu), len(converti))
        return converti
    finally:
        shutil.rmtree(dossier, ignore_errors=True)


def preparer_dictee(contenu: bytes, nom_fichier: str,
                    type_mime: Optional[str] = None) -> tuple[bytes, str]:
    """Audio et nom de fichier à envoyer au fournisseur : tels quels, ou convertis
    en WAV si le format est listé dans `VOIX_FORMATS_A_CONVERTIR`."""
    format_audio = extension_audio(nom_fichier, type_mime)
    nom_envoye = nom_fichier if os.path.splitext(nom_fichier or "")[1] else \
        f"dictee.{format_audio or 'webm'}"
    if not doit_convertir(format_audio):
        return contenu, nom_envoye
    return convertir_en_wav(contenu, format_audio), f"dictee.{FORMAT_CONVERTI}"

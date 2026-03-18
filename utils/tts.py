"""
utils/tts.py — Synthèse vocale via gTTS
----------------------------------------
Convertit un texte en message vocal Telegram (.ogg/opus).

Dépendances :
    pip install gtts
    + ffmpeg installé et accessible dans le PATH
      Windows : winget install ffmpeg
      ou https://www.gyan.dev/ffmpeg/builds/ → ffmpeg-release-essentials.zip

Utilisation :
    from utils.tts import send_voice_reply
    await send_voice_reply(update, "Votre texte à dicter")
"""

import os
import re
import logging
import tempfile
import subprocess
from gtts import gTTS

log = logging.getLogger("potager")

# ── Activer / désactiver la synthèse vocale ────────────────────────────────────
# Passez à False pour désactiver sans toucher au code appelant
TTS_ENABLED = True

# ── Longueur max du texte lu à voix haute ─────────────────────────────────────
# Au-delà, seule une version raccourcie est lue (évite les messages de 2 minutes)
TTS_MAX_CHARS = 400


def _strip_markdown(texte: str) -> str:
    """
    Supprime les balises Markdown pour une lecture vocale propre.
    * gras *, _ italique _, `code`, # titres, liens [x](y)...
    """
    # Titres
    texte = re.sub(r"#+\s*", "", texte)
    # Gras / italique / code inline
    texte = re.sub(r"[*_`]{1,3}", "", texte)
    # Liens Markdown [texte](url) → texte
    texte = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", texte)
    # Émojis (gTTS les lit bizarrement, on les retire)
    texte = re.sub(
        r"[\U0001F300-\U0001FFFF\U00002702-\U000027B0\U0000FE0F\U00002000-\U00002BFF]+",
        " ", texte
    )
    # Espaces multiples / retours à la ligne → espace simple
    texte = re.sub(r"\s+", " ", texte).strip()
    return texte


def _truncate_for_tts(texte: str) -> str:
    """
    Si le texte dépasse TTS_MAX_CHARS, le tronque proprement à la dernière
    phrase complète pour ne pas couper en milieu de mot.
    """
    if len(texte) <= TTS_MAX_CHARS:
        return texte
    tronque = texte[:TTS_MAX_CHARS]
    # Couper à la dernière phrase (. ! ?)
    dernier_point = max(
        tronque.rfind("."),
        tronque.rfind("!"),
        tronque.rfind("?"),
    )
    if dernier_point > TTS_MAX_CHARS // 2:
        tronque = tronque[:dernier_point + 1]
    return tronque + " …"


def _mp3_to_ogg(mp3_path: str) -> str | None:
    """
    Convertit un fichier MP3 en OGG/Opus via ffmpeg.
    Retourne le chemin du fichier .ogg, ou None si ffmpeg indisponible.
    """
    ogg_path = mp3_path.replace(".mp3", ".ogg")
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y",          # écraser sans confirmation
                "-i", mp3_path,
                "-c:a", "libopus",       # codec Opus (requis par Telegram voice note)
                "-b:a", "32k",           # bitrate léger (voix)
                ogg_path
            ],
            capture_output=True,
            timeout=15,
        )
        if result.returncode != 0:
            log.warning(f"⚠️ TTS ffmpeg erreur : {result.stderr.decode()[:200]}")
            return None
        return ogg_path
    except FileNotFoundError:
        log.warning("⚠️ TTS ffmpeg introuvable — installez ffmpeg et ajoutez-le au PATH Windows")
        return None
    except subprocess.TimeoutExpired:
        log.warning("⚠️ TTS ffmpeg timeout")
        return None


async def send_voice_reply(update, texte: str) -> bool:
    """
    Génère un message vocal à partir du texte et l'envoie via Telegram reply_voice().

    Paramètres :
        update  — objet Update Telegram
        texte   — texte brut ou Markdown à synthétiser

    Retourne True si le vocal a été envoyé, False sinon (erreur silencieuse).
    L'appelant peut continuer normalement même si le TTS échoue.
    """
    if not TTS_ENABLED:
        return False

    # Nettoyage du texte
    texte_clean = _strip_markdown(texte)
    texte_clean = _truncate_for_tts(texte_clean)

    if not texte_clean:
        return False

    mp3_path = None
    ogg_path = None

    try:
        # ── Génération MP3 via gTTS ────────────────────────────────────────────
        tts = gTTS(text=texte_clean, lang="fr", slow=False)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            mp3_path = tmp.name
        tts.save(mp3_path)
        log.info(f"🔊 TTS GÉNÉRÉ      : {len(texte_clean)} chars → {mp3_path}")

        # ── Conversion OGG/Opus pour Telegram voice note ──────────────────────
        ogg_path = _mp3_to_ogg(mp3_path)

        if ogg_path:
            # Envoi comme note vocale (bulle micro dans Telegram)
            with open(ogg_path, "rb") as audio:
                await update.message.reply_voice(voice=audio)
            log.info("🔊 TTS ENVOYÉ      : voice note OGG/Opus")
        else:
            # Fallback : envoi comme fichier audio MP3 si ffmpeg absent
            with open(mp3_path, "rb") as audio:
                await update.message.reply_audio(
                    audio=audio,
                    title="Réponse assistant",
                    filename="reponse.mp3"
                )
            log.info("🔊 TTS ENVOYÉ      : fallback audio MP3 (ffmpeg absent)")

        return True

    except Exception as e:
        log.error(f"❌ TTS ERREUR       : {e}")
        return False

    finally:
        # Nettoyage fichiers temporaires
        for path in [mp3_path, ogg_path]:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except Exception:
                    pass

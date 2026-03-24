"""
utils/tts.py — Synthèse vocale via gTTS avec activation dynamique
------------------------------------------------------------------
Convertit un texte en message vocal Telegram (.ogg/opus).

Activation/désactivation depuis Telegram :
    /tts      → affiche l'état actuel
    /tts_on   → active les réponses vocales
    /tts_off  → désactive les réponses vocales

L'état est persisté dans utils/.tts_state.json → survit au redémarrage.

Dépendances :
    pip install gtts
    + ffmpeg installé et accessible dans le PATH
      Windows : winget install ffmpeg
      ou https://www.gyan.dev/ffmpeg/builds/ → ffmpeg-release-essentials.zip

Utilisation :
    from utils.tts import send_voice_reply, set_tts_enabled, is_tts_enabled
    await send_voice_reply(update, "Votre texte à dicter")
"""

import os
import re
import json
import logging
import tempfile
import subprocess
from gtts import gTTS

log = logging.getLogger("potager")

# ── Fichier d'état persistant ──────────────────────────────────────────────────
_TTS_STATE_FILE = os.path.join(os.path.dirname(__file__), ".tts_state.json")

def _load_tts_state() -> bool:
    """Charge la préférence TTS depuis le fichier d'état (défaut : False)."""
    try:
        with open(_TTS_STATE_FILE) as f:
            return json.load(f).get("enabled", False)
    except (FileNotFoundError, json.JSONDecodeError):
        return False  # désactivé par défaut au 1er lancement

def _save_tts_state(enabled: bool):
    """Persiste la préférence TTS dans un fichier JSON local."""
    try:
        with open(_TTS_STATE_FILE, "w") as f:
            json.dump({"enabled": enabled}, f)
    except Exception as e:
        log.error(f"❌ TTS STATE SAVE  : impossible d'écrire l'état → {e}")

def set_tts_enabled(enabled: bool):
    """Active ou désactive le TTS globalement (persiste au redémarrage)."""
    _save_tts_state(enabled)
    log.info(f"{'🔊' if enabled else '🔇'} TTS STATE        : {'activé' if enabled else 'désactivé'}")

def is_tts_enabled() -> bool:
    """Retourne l'état TTS courant (lu depuis le fichier de persistance)."""
    return _load_tts_state()


# ── Longueur max du texte lu à voix haute ─────────────────────────────────────
# Au-delà, seule une version raccourcie est lue (évite les messages de 2 minutes)
TTS_MAX_CHARS = 400


def _strip_markdown(texte: str) -> str:
    """
    Supprime les balises Markdown pour une lecture vocale propre.
    * gras *, _ italique _, `code`, # titres, liens [x](y)...
    """
    texte = re.sub(r"#+\s*", "", texte)
    texte = re.sub(r"[*_`]{1,3}", "", texte)
    texte = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", texte)
    texte = re.sub(
        r"[\U0001F300-\U0001FFFF\U00002702-\U000027B0\U0000FE0F\U00002000-\U00002BFF]+",
        " ", texte
    )
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
                "ffmpeg", "-y",
                "-i", mp3_path,
                "-c:a", "libopus",
                "-b:a", "32k",
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
    Ne fait rien si le TTS est désactivé (commande /tts_off).

    Paramètres :
        update  — objet Update Telegram
        texte   — texte brut ou Markdown à synthétiser

    Retourne True si le vocal a été envoyé, False sinon (erreur silencieuse).
    """
    if not is_tts_enabled():
        return False

    texte_clean = _strip_markdown(texte)
    texte_clean = _truncate_for_tts(texte_clean)

    if not texte_clean:
        return False

    mp3_path = None
    ogg_path = None

    try:
        tts = gTTS(text=texte_clean, lang="fr", slow=False)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            mp3_path = tmp.name
        tts.save(mp3_path)
        log.info(f"🔊 TTS GÉNÉRÉ      : {len(texte_clean)} chars → {mp3_path}")

        ogg_path = _mp3_to_ogg(mp3_path)

        if ogg_path:
            with open(ogg_path, "rb") as audio:
                await update.message.reply_voice(voice=audio)
            log.info("🔊 TTS ENVOYÉ      : voice note OGG/Opus")
        else:
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
        for path in [mp3_path, ogg_path]:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except Exception:
                    pass

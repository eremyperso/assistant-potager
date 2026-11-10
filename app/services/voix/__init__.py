"""
app/services/voix — compagnon vocal de la PWA [US-299]
======================================================
Seul point d'entrée des routes vocales à venir (US-302 dictée, US-304 lecture) :
une route n'appelle jamais `llm.passerelle` directement pour la voix.

* `dicter()` — audio enregistré par la PWA → texte (type d'appel `dictee`) ;
  conversion FFmpeg préalable des formats listés dans `VOIX_FORMATS_A_CONVERTIR`.
* `synthetiser()` — texte → MP3 (type d'appel `voix`), après nettoyage du texte
  (Markdown, émojis, liens), repris de `utils/tts.py` sans le modifier.

Erreurs à rattraper par l'appelant, toutes avec repli « écrivez votre message » :
* `LLMIndisponibleError` — clé Mistral absente, délai, 5xx, 429 ;
* `VoixInconnueError` — la voix demandée n'existe pas (revenir à `VOIX_PAR_DEFAUT`) ;
* `FormatAudioNonConvertibleError` — format à convertir, FFmpeg absent ou en échec.

L'audio n'est jamais écrit en base ; un fichier temporaire de conversion est
supprimé après l'appel, erreur comprise (CA7). Le bot Telegram n'utilise pas ce
service : il garde Groq Whisper (`transcription`) et gTTS (`utils/tts.py`).
"""
from llm.passerelle import (
    LLMIndisponibleError,
    ReponseDictee,
    ReponseVoix,
    VoixInconnueError,
)
from app.services.voix.conversion import FormatAudioNonConvertibleError
from app.services.voix.dictee import dicter
from app.services.voix.nettoyage import nettoyer_pour_voix
from app.services.voix import catalogue, preferences
from app.services.voix.synthese import VOIX_PAR_DEFAUT, synthetiser

# [CA4] Phrase que la PWA dira quand la voix ne répond pas : le texte reste possible.
MESSAGE_VOIX_INDISPONIBLE = "La voix est indisponible, écrivez votre message."

__all__ = [
    "FormatAudioNonConvertibleError",
    "LLMIndisponibleError",
    "MESSAGE_VOIX_INDISPONIBLE",
    "ReponseDictee",
    "ReponseVoix",
    "VOIX_PAR_DEFAUT",
    "VoixInconnueError",
    "catalogue",
    "dicter",
    "nettoyer_pour_voix",
    "preferences",
    "synthetiser",
]

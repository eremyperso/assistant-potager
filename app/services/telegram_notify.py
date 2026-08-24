"""
app/services/telegram_notify.py — Notifications Telegram sortantes déclenchées
depuis le web [US-083 / CA9]
--------------------------------------------------------------------------------
`main.py` (endpoints FastAPI synchrones) n'a pas de session Telegram active
contrairement à `bot.py`, qui possède son propre process de polling/webhook.
Plutôt que d'y importer une instance `python-telegram-bot` (asynchrone, donc
malaisée à piloter depuis du code synchrone), l'envoi passe par un simple
appel HTTP à l'API Bot Telegram — même principe que les autres appels sortants
synchrones du projet (`requests`, cf. `tools/jira_tracker.py`, `utils/meteo.py`).

Best-effort : l'absence de compte Telegram lié ou une panne de l'API Telegram
ne doivent JAMAIS faire échouer l'action déclenchante (archivage, désarchivage
d'un potager...) — tout échec est journalisé, jamais levé.
"""
import logging

import requests

from config import TELEGRAM_BOT_TOKEN

log = logging.getLogger("potager")

_API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def envoyer_message(chat_id: int, texte: str) -> bool:
    """Envoie un message Telegram best-effort à `chat_id`.

    Retourne `True` si l'API Telegram a accepté l'envoi, `False` sinon —
    ne lève jamais d'exception (réseau indisponible, chat_id invalide,
    utilisateur ayant bloqué le bot...)."""
    try:
        response = requests.post(f"{_API_BASE}/sendMessage", json={"chat_id": chat_id, "text": texte}, timeout=10)
        response.raise_for_status()
        return True
    except requests.RequestException as err:
        log.warning("[telegram_notify] Échec d'envoi à chat_id=%s : %s", chat_id, err)
        return False


# [US-091] Identifiant public du bot (sans @), déduit du token via l'API
# Telegram (getMe) plutôt qu'une variable d'environnement séparée à maintenir
# à la main pour chaque environnement (dev/prod) en plus de TELEGRAM_BOT_TOKEN
# — élimine tout risque de désynchronisation entre le token réellement utilisé
# et le nom affiché dans le deep-link d'activation (cf. incident constaté en
# dev : un TELEGRAM_BOT_USERNAME configuré à la main ne correspondait pas au
# bot du token courant). Mis en cache après le premier succès pour le process.
_username_bot_cache: str | None = None


def obtenir_username_bot() -> str:
    """[US-091] Identifiant public du bot (sans @) pour construire le deep-link
    `https://t.me/<bot>?start=<code>` côté frontend (exposé via GET /auth/me).

    Best-effort comme `envoyer_message` : ne lève jamais, retourne `""` en cas
    d'échec (réseau indisponible, token invalide) — le frontend retombe alors
    sur le seul code manuel, sans bouton ni QR. Un échec n'est pas mis en
    cache : le prochain appel retente (auto-guérison après une panne Telegram
    transitoire, sans nécessiter de redémarrage du process)."""
    global _username_bot_cache
    if _username_bot_cache:
        return _username_bot_cache
    try:
        response = requests.get(f"{_API_BASE}/getMe", timeout=5)
        response.raise_for_status()
        username = response.json()["result"]["username"]
        _username_bot_cache = username
        return username
    except (requests.RequestException, KeyError, ValueError) as err:
        log.warning("[telegram_notify] Échec de résolution du nom du bot (getMe) : %s", err)
        return ""

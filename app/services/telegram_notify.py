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

_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"


def envoyer_message(chat_id: int, texte: str) -> bool:
    """Envoie un message Telegram best-effort à `chat_id`.

    Retourne `True` si l'API Telegram a accepté l'envoi, `False` sinon —
    ne lève jamais d'exception (réseau indisponible, chat_id invalide,
    utilisateur ayant bloqué le bot...)."""
    try:
        response = requests.post(_API_URL, json={"chat_id": chat_id, "text": texte}, timeout=10)
        response.raise_for_status()
        return True
    except requests.RequestException as err:
        log.warning("[telegram_notify] Échec d'envoi à chat_id=%s : %s", chat_id, err)
        return False

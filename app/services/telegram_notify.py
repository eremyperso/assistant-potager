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
from typing import Optional

import requests

from app.config import TELEGRAM_BOT_TOKEN

log = logging.getLogger("potager")

_API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def envoyer_message(chat_id: int, texte: str) -> bool:
    """Envoie un message Telegram best-effort à `chat_id`.

    Retourne `True` si l'API Telegram a accepté l'envoi, `False` sinon —
    ne lève jamais d'exception (réseau indisponible, chat_id invalide,
    utilisateur ayant bloqué le bot...)."""
    return envoyer(chat_id, texte) is not None


# ── [US-224 / CA5] Un envoi sortant qui sait poster un CLAVIER ───────────────
# Jusqu'ici, l'envoi sortant ne savait poster que du texte brut. C'est suffisant
# pour annoncer un archivage (US-083) ou l'arrivée d'un membre (US-085), qui
# n'appellent aucune réponse. Ça ne l'est pas pour inviter à traiter une file :
# sans clavier, toute invitation dégénère en « envoyez /gestes pour les
# traiter », et perd l'essentiel de son intérêt. Constaté à l'envoi d'un message
# de test sur l'environnement de dev le 21/09/2026.
#
# Le clavier est passé en STRUCTURE (une liste de rangées de `(libellé, donnée)`)
# plutôt qu'en JSON déjà formé : l'appelant est un service métier, il n'a pas à
# connaître la forme d'un `inline_keyboard` de l'API Bot.
Bouton = tuple  # (libellé: str, callback_data: str)


def _clavier(boutons: Optional[list[list["Bouton"]]]) -> Optional[dict]:
    if not boutons:
        return None
    return {
        "inline_keyboard": [
            [{"text": libelle, "callback_data": donnee} for libelle, donnee in rangee]
            for rangee in boutons
        ]
    }


def envoyer(
    chat_id: int,
    texte: str,
    boutons: Optional[list[list["Bouton"]]] = None,
    parse_mode: Optional[str] = None,
) -> Optional[int]:
    """[US-224 / CA5] Envoie un message, avec clavier éventuel, et rend son id.

    L'identifiant est ce qui permet à la relance suivante de REMPLACER
    celle-ci plutôt que d'empiler des bulles identiques (CA20). `None` en cas
    d'échec — best-effort, comme `envoyer_message` : un envoi perdu l'est sans
    bruit, mais il est journalisé, et le CA18 s'appuie sur ce retour pour
    savoir que l'information doit passer aussi par l'application.
    """
    charge: dict = {"chat_id": chat_id, "text": texte}
    clavier = _clavier(boutons)
    if clavier:
        charge["reply_markup"] = clavier
    if parse_mode:
        charge["parse_mode"] = parse_mode
    try:
        response = requests.post(f"{_API_BASE}/sendMessage", json=charge, timeout=10)
        response.raise_for_status()
        return response.json()["result"]["message_id"]
    except (requests.RequestException, KeyError, ValueError) as err:
        log.warning("[telegram_notify] Échec d'envoi à chat_id=%s : %s", chat_id, err)
        return None


def editer_message(
    chat_id: int,
    message_id: int,
    texte: str,
    boutons: Optional[list[list["Bouton"]]] = None,
    parse_mode: Optional[str] = None,
) -> bool:
    """[US-224 / CA20] Remplace un message déjà posté — la relance ne s'empile pas.

    `False` quand l'édition est refusée : message supprimé par le jardinier,
    contenu identique, message trop ancien. L'appelant repart alors d'un envoi
    neuf, et c'est pour ça que ce retour n'est pas ignoré.
    """
    charge: dict = {"chat_id": chat_id, "message_id": message_id, "text": texte}
    clavier = _clavier(boutons)
    if clavier:
        charge["reply_markup"] = clavier
    if parse_mode:
        charge["parse_mode"] = parse_mode
    try:
        response = requests.post(f"{_API_BASE}/editMessageText", json=charge, timeout=10)
        response.raise_for_status()
        return True
    except requests.RequestException as err:
        log.info(
            "[telegram_notify] Édition impossible (chat_id=%s, message_id=%s) : %s",
            chat_id, message_id, err,
        )
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

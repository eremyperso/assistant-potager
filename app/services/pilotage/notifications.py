"""
app/services/pilotage/notifications.py — Joindre l'administrateur par Telegram et par e-mail [US-316, US-317]
==============================================================================================================
Une seule porte d'envoi pour les alertes, les retours à la normale, le résumé quotidien et le bilan
hebdomadaire. L'administrateur est joint par :
- **Telegram** : le compte lié à `ADMIN_EMAIL` (`users.telegram_chat_id`), sinon `ADMIN_TELEGRAM_ID` ;
- **e-mail** : `ADMIN_EMAIL`, par l'envoi Brevo de `app/services/email.py`.

Les deux canaux sont indépendants [US-316 / CA9] : l'échec de l'un est journalisé, jamais levé, et
n'empêche pas l'autre. Aucun envoi ne porte de contenu de jardinier : les appelants ne passent que des
mesures (la garde de test le vérifie sur les messages produits).
"""
from __future__ import annotations

import html
import logging
import re
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app import config
from app.services import email as svc_email
from app.services import telegram_notify
from database.models import User

log = logging.getLogger("potager")

CANAL_TELEGRAM = "telegram"
CANAL_EMAIL = "email"

_URL = re.compile(r"(https?://\S+)")


def identifiant_telegram_admin(db: Session) -> Optional[int]:
    """Le `chat_id` Telegram de l'administrateur : celui du compte lié à `ADMIN_EMAIL`, à défaut
    `ADMIN_TELEGRAM_ID`. `None` si aucun des deux n'est utilisable."""
    adresse = (config.ADMIN_EMAIL or "").strip().lower()
    if adresse:
        for compte in db.query(User).filter(User.telegram_chat_id.isnot(None)).all():
            if (compte.email or "").strip().lower() == adresse:
                return int(compte.telegram_chat_id)
    brut = (config.ADMIN_TELEGRAM_ID or "").strip()
    if brut:
        try:
            return int(brut)
        except ValueError:
            log.warning("[US-316] ADMIN_TELEGRAM_ID n'est pas un entier : ignoré")
    return None


def canaux_configures(db: Session) -> set[str]:
    """Les canaux qui ont un destinataire : un canal sans destinataire n'est jamais « en échec »,
    il n'existe pas."""
    canaux: set[str] = set()
    if identifiant_telegram_admin(db) is not None:
        canaux.add(CANAL_TELEGRAM)
    if (config.ADMIN_EMAIL or "").strip():
        canaux.add(CANAL_EMAIL)
    return canaux


def _html(texte: str) -> str:
    """Le texte brut d'un message en HTML : un paragraphe par ligne, liens cliquables, tout échappé."""
    lignes = []
    for ligne in texte.split("\n"):
        echappee = html.escape(ligne)
        echappee = _URL.sub(r'<a href="\1">\1</a>', echappee)
        lignes.append(f"<p>{echappee}</p>" if echappee.strip() else "")
    return "".join(lignes)


def envoyer_telegram(db: Session, texte: str) -> bool:
    """Envoie `texte` à l'administrateur par Telegram. `False` sans destinataire ou en cas d'échec."""
    chat_id = identifiant_telegram_admin(db)
    if chat_id is None:
        log.warning("[US-316] Telegram : aucun identifiant d'administrateur (compte lié à ADMIN_EMAIL ou ADMIN_TELEGRAM_ID)")
        return False
    try:
        return bool(telegram_notify.envoyer_message(chat_id, texte))
    except Exception as e:  # noqa: BLE001 — un canal en échec ne lève jamais
        log.error("[US-316] Telegram : échec d'envoi à l'administrateur : %s", e)
        return False


def envoyer_email(sujet: str, texte: str) -> bool:
    """Envoie `texte` à `ADMIN_EMAIL` par Brevo. `False` sans adresse ou en cas d'échec."""
    adresse = (config.ADMIN_EMAIL or "").strip()
    if not adresse:
        log.warning("[US-316] e-mail : ADMIN_EMAIL absent")
        return False
    try:
        return bool(svc_email.envoyer_email(adresse, sujet, _html(texte)))
    except Exception as e:  # noqa: BLE001 — idem
        log.error("[US-316] e-mail : échec d'envoi à l'administrateur : %s", e)
        return False


def diffuser(db: Session, sujet: str, texte: str, canaux: Iterable[str]) -> set[str]:
    """Envoie `texte` sur chacun des `canaux` demandés ; rend l'ensemble de ceux qui ont réussi.

    Le sujet ne sert qu'à l'e-mail. Un canal inconnu est ignoré."""
    reussis: set[str] = set()
    for canal in sorted(set(canaux)):
        if canal == CANAL_TELEGRAM and envoyer_telegram(db, texte):
            reussis.add(canal)
        elif canal == CANAL_EMAIL and envoyer_email(sujet, texte):
            reussis.add(canal)
    return reussis

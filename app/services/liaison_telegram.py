"""
app/services/liaison_telegram.py — Liaison chat Telegram ⇄ compte web [US-045]
--------------------------------------------------------------------------------
Génère un code à usage unique côté web (compte authentifié) et le valide côté
Telegram pour rattacher `users.telegram_chat_id` au compte correspondant.

⚠️ Comme app/services/auth.py, ce module ne prend pas TenantContext en premier
paramètre : `creer_code_liaison` s'exécute avec un user_id déjà authentifié
(HTTP), et `lier_chat_id`/`resoudre_user_id_pour_chat` s'exécutent AVANT
qu'un TenantContext Telegram n'existe — c'est justement leur rôle de le rendre
possible.
"""
import secrets
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from database.models import LiaisonTelegram, User

# Alphabet sans caractères ambigus (pas de 0/O, 1/I/l) — code lisible à l'oral/écrit
_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
_LONGUEUR_CODE = 6
_TTL_MINUTES = 10


class CodeInvalideError(Exception):
    """[CA2] Code inconnu (jamais généré, ou faute de frappe)."""


class CodeExpireError(Exception):
    """[CA3] Code généré il y a plus de 10 minutes."""


class CodeDejaUtiliseError(Exception):
    """[CA4] Code déjà consommé par une liaison précédente."""


class ChatDejaLieError(Exception):
    """[CA5] Ce chat_id est déjà lié à un autre compte."""


def _generer_code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(_LONGUEUR_CODE))


def creer_code_liaison(db: Session, user_id: int) -> LiaisonTelegram:
    """[CA1] Génère un code à usage unique (TTL 10 min) pour `user_id`."""
    maintenant = datetime.utcnow()
    code = _generer_code()
    while db.query(LiaisonTelegram).filter(LiaisonTelegram.code == code).first() is not None:
        code = _generer_code()

    liaison = LiaisonTelegram(
        code=code,
        user_id=user_id,
        expire_le=maintenant + timedelta(minutes=_TTL_MINUTES),
    )
    db.add(liaison)
    db.commit()
    db.refresh(liaison)
    return liaison


def lier_chat_id(db: Session, code: str, chat_id: int) -> User:
    """[CA2-CA5] Valide un code et rattache `chat_id` au compte correspondant."""
    liaison = db.query(LiaisonTelegram).filter(LiaisonTelegram.code == code.strip().upper()).first()
    if liaison is None:
        raise CodeInvalideError("Code de liaison inconnu")

    if liaison.utilise_le is not None:
        raise CodeDejaUtiliseError("Ce code a déjà été utilisé")

    if datetime.utcnow() > liaison.expire_le:
        raise CodeExpireError("Ce code a expiré")

    autre = db.query(User).filter(
        User.telegram_chat_id == chat_id, User.id != liaison.user_id
    ).first()
    if autre is not None:
        raise ChatDejaLieError("Ce chat est déjà lié à un autre compte")

    user = db.query(User).filter(User.id == liaison.user_id).first()
    user.telegram_chat_id = chat_id
    liaison.utilise_le = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return user


def resoudre_user_id_pour_chat(db: Session, chat_id: int) -> Optional[int]:
    """[CA8] Résout le user_id lié à ce chat_id, ou None si le chat n'est pas lié."""
    user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
    return user.id if user else None


def ressemble_a_un_code(texte: str) -> bool:
    """[CA2] Détecte un message texte brut susceptible d'être un code de liaison
    (envoyé sans le préfixe `/lier`) — longueur exacte + alphabet autorisé."""
    candidat = texte.strip().upper()
    return len(candidat) == _LONGUEUR_CODE and all(c in _ALPHABET for c in candidat)

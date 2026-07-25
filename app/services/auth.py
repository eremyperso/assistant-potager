"""
app/services/auth.py — Authentification web par e-mail / mot de passe [US-044]
--------------------------------------------------------------------------------
Hachage des mots de passe (passlib/bcrypt), émission et vérification des JWT
(access + refresh) via python-jose, inscription et connexion des utilisateurs.

⚠️ Ce module ne prend pas TenantContext en premier paramètre (contrairement
aux autres services d'app/services/) : il s'exécute AVANT qu'un contexte
utilisateur n'existe — c'est justement lui qui le produit.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from config import JWT_SECRET, JWT_ALGORITHM, JWT_ACCESS_TTL_MIN, JWT_REFRESH_TTL_DAYS
from database.models import User

_pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

_TOKEN_TYPE_ACCESS = "access"
_TOKEN_TYPE_REFRESH = "refresh"


class EmailDejaUtiliseError(Exception):
    """[CA7] E-mail déjà inscrit — levée sur /auth/register."""


class IdentifiantsInvalidesError(Exception):
    """[CA2] E-mail inconnu ou mot de passe incorrect — levée sur /auth/login."""


class TokenExpireError(Exception):
    """[CA5] Token JWT syntaxiquement valide mais expiré."""


class TokenInvalideError(Exception):
    """[CA5] Token JWT absent, malformé, signature invalide, ou mauvais type."""


def hash_password(mot_de_passe: str) -> str:
    """Hache un mot de passe en clair — jamais stocké ni loggé tel quel [CA1]."""
    return _pwd_context.hash(mot_de_passe)


def verifier_mot_de_passe(mot_de_passe: str, mot_de_passe_hash: str) -> bool:
    """Vérifie un mot de passe en clair contre son hash."""
    return _pwd_context.verify(mot_de_passe, mot_de_passe_hash)


def _creer_token(user_id: int, type_token: str, duree: timedelta) -> str:
    maintenant = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": type_token,
        "iat": maintenant,
        "exp": maintenant + duree,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def creer_access_token(user_id: int) -> str:
    """[CA2] Access token, durée de vie courte (15 min par défaut)."""
    return _creer_token(user_id, _TOKEN_TYPE_ACCESS, timedelta(minutes=JWT_ACCESS_TTL_MIN))


def creer_refresh_token(user_id: int) -> str:
    """[CA2] Refresh token, durée de vie longue (30 jours par défaut)."""
    return _creer_token(user_id, _TOKEN_TYPE_REFRESH, timedelta(days=JWT_REFRESH_TTL_DAYS))


def _decoder_token(token: str, type_attendu: str) -> dict:
    """Décode un JWT et vérifie son type — lève TokenExpireError/TokenInvalideError [CA5]."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise TokenExpireError("Token expiré")
    except JWTError:
        raise TokenInvalideError("Token invalide")

    if payload.get("type") != type_attendu:
        raise TokenInvalideError(f"Type de token invalide (attendu: {type_attendu})")
    return payload


def decoder_access_token(token: str) -> dict:
    """[CA4/CA5] Décode un access token — utilisé par la dépendance get_current_user."""
    return _decoder_token(token, _TOKEN_TYPE_ACCESS)


def decoder_refresh_token(token: str) -> dict:
    """[CA3] Décode un refresh token — utilisé par /auth/refresh."""
    return _decoder_token(token, _TOKEN_TYPE_REFRESH)


def inscrire_utilisateur(db: Session, email: str, mot_de_passe: str) -> User:
    """[CA1/CA7] Crée un compte — lève EmailDejaUtiliseError si l'e-mail existe déjà."""
    email_normalise = email.strip().lower()
    existant = db.query(User).filter(User.email == email_normalise).first()
    if existant is not None:
        raise EmailDejaUtiliseError("Cet e-mail est déjà utilisé")

    user = User(email=email_normalise, mot_de_passe_hash=hash_password(mot_de_passe))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authentifier_utilisateur(db: Session, email: str, mot_de_passe: str) -> User:
    """[CA2] Vérifie les identifiants — lève IdentifiantsInvalidesError sinon."""
    email_normalise = email.strip().lower()
    user = db.query(User).filter(User.email == email_normalise).first()
    if user is None or not user.mot_de_passe_hash:
        raise IdentifiantsInvalidesError("E-mail ou mot de passe incorrect")
    if not verifier_mot_de_passe(mot_de_passe, user.mot_de_passe_hash):
        raise IdentifiantsInvalidesError("E-mail ou mot de passe incorrect")
    return user


def obtenir_utilisateur_par_id(db: Session, user_id: int) -> Optional[User]:
    """[CA4] Résout l'utilisateur à partir du `sub` d'un access token décodé."""
    return db.query(User).filter(User.id == user_id).first()

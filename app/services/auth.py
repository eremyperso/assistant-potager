"""
app/services/auth.py — Authentification web par e-mail / mot de passe [US-044]
--------------------------------------------------------------------------------
Hachage des mots de passe (passlib/bcrypt), émission et vérification des JWT
(access + refresh) via python-jose, inscription et connexion des utilisateurs.

⚠️ Ce module ne prend pas TenantContext en premier paramètre (contrairement
aux autres services d'app/services/) : il s'exécute AVANT qu'un contexte
utilisateur n'existe — c'est justement lui qui le produit.
"""
import hashlib
import secrets
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

# [CA9] Durée de validité du token de vérification d'e-mail
_VERIFICATION_TOKEN_TTL = timedelta(hours=24)


class EmailDejaUtiliseError(Exception):
    """[CA7] E-mail déjà inscrit — levée sur /auth/register."""


class IdentifiantsInvalidesError(Exception):
    """[CA2] E-mail inconnu ou mot de passe incorrect — levée sur /auth/login."""


class TokenExpireError(Exception):
    """[CA5] Token JWT syntaxiquement valide mais expiré."""


class TokenInvalideError(Exception):
    """[CA5] Token JWT absent, malformé, signature invalide, ou mauvais type."""


class EmailNonVerifieError(Exception):
    """[CA11] Identifiants corrects mais e-mail pas encore vérifié — levée sur /auth/login."""


class TokenVerificationInvalideError(Exception):
    """[CA10] Token de vérification d'e-mail inconnu, déjà utilisé ou malformé."""


class TokenVerificationExpireError(Exception):
    """[CA10] Token de vérification d'e-mail expiré (> 24h)."""


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
    """[CA2] Vérifie les identifiants — lève IdentifiantsInvalidesError sinon.
    [CA11] Lève EmailNonVerifieError si l'e-mail n'a pas encore été vérifié
    (vérifié après le mot de passe : un mauvais mot de passe reste un 401,
    jamais un indice sur l'état de vérification du compte)."""
    email_normalise = email.strip().lower()
    user = db.query(User).filter(User.email == email_normalise).first()
    if user is None or not user.mot_de_passe_hash:
        raise IdentifiantsInvalidesError("E-mail ou mot de passe incorrect")
    if not verifier_mot_de_passe(mot_de_passe, user.mot_de_passe_hash):
        raise IdentifiantsInvalidesError("E-mail ou mot de passe incorrect")
    if not user.email_verifie:
        raise EmailNonVerifieError("E-mail non vérifié")
    return user


def obtenir_utilisateur_par_id(db: Session, user_id: int) -> Optional[User]:
    """[CA4] Résout l'utilisateur à partir du `sub` d'un access token décodé."""
    return db.query(User).filter(User.id == user_id).first()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def demarrer_verification_email(db: Session, user: User) -> str:
    """[CA9] Génère un token de vérification aléatoire (24h), stocke uniquement
    son hash et renvoie la valeur brute — à transmettre exclusivement dans
    l'e-mail envoyé (app/services/email.py), jamais loggée ni renvoyée en HTTP."""
    token_brut = secrets.token_urlsafe(32)
    user.verification_token_hash = _hash_token(token_brut)
    user.verification_token_expire_le = datetime.utcnow() + _VERIFICATION_TOKEN_TTL
    user.verification_token_utilise_le = None
    db.commit()
    return token_brut


def verifier_email(db: Session, token: str) -> User:
    """[CA10] Valide un token de vérification et marque le compte comme vérifié.
    Usage unique (verification_token_utilise_le) : un rejeu du même token
    retombe sur TokenVerificationInvalideError, jamais une seconde validation
    silencieuse."""
    token_hash = _hash_token(token)
    user = db.query(User).filter(User.verification_token_hash == token_hash).first()
    if user is None or user.verification_token_utilise_le is not None:
        raise TokenVerificationInvalideError("Lien de vérification invalide")

    if user.verification_token_expire_le is None or datetime.utcnow() > user.verification_token_expire_le:
        raise TokenVerificationExpireError("Lien de vérification expiré")

    user.email_verifie = True
    user.verification_token_utilise_le = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return user


def renvoyer_verification_email(db: Session, email: str) -> Optional[str]:
    """[CA12] Régénère un token si un compte existe pour cet e-mail et n'est
    pas encore vérifié. Renvoie None sinon (compte inconnu ou déjà vérifié) —
    l'appelant doit renvoyer la même réponse générique dans tous les cas
    (anti-énumération, cohérent avec CA7)."""
    email_normalise = email.strip().lower()
    user = db.query(User).filter(User.email == email_normalise).first()
    if user is None or user.email_verifie:
        return None
    return demarrer_verification_email(db, user)

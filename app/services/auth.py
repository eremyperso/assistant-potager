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
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config import JWT_SECRET, JWT_ALGORITHM, JWT_ACCESS_TTL_MIN, JWT_REFRESH_TTL_DAYS
from database.models import User

log = logging.getLogger("potager")

_pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

_TOKEN_TYPE_ACCESS = "access"
_TOKEN_TYPE_REFRESH = "refresh"

# [CA9] Durée de validité du token de vérification d'e-mail
_VERIFICATION_TOKEN_TTL = timedelta(hours=24)

# [US-057 / CA1] Durée de validité du token de réinitialisation de mot de passe
_RESET_MDP_TOKEN_TTL = timedelta(hours=1)


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


class TokenResetMdpInvalideError(Exception):
    """[US-057 / CA4] Token de réinitialisation inconnu, déjà utilisé ou malformé."""


class TokenResetMdpExpireError(Exception):
    """[US-057 / CA4] Token de réinitialisation expiré (> 1h)."""


class RattachementNonVerifieError(Exception):
    """[US-090 / CA13] Un compte existe déjà pour cette adresse, mais Google
    n'atteste pas sa vérification (`email_verified = false`) — le rattachement
    automatique est refusé."""


class EmailGoogleAbsentError(Exception):
    """[US-090] L'id_token Google ne porte aucune adresse e-mail : impossible
    d'identifier ou de créer un compte."""


class FederationImpossibleError(Exception):
    """[US-090] Collision concurrente sur `google_sub` ou `email` — la création
    du compte fédéré n'a pas abouti."""


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


def inscrire_utilisateur(db: Session, email: str, mot_de_passe: str, nom: Optional[str] = None) -> User:
    """[CA1/CA7] Crée un compte — lève EmailDejaUtiliseError si l'e-mail existe déjà.
    [US-056 / CA3] `nom` optionnel, simplement stocké tel quel (colonne déjà
    existante, alimentée par le formulaire d'inscription refondu)."""
    email_normalise = email.strip().lower()
    existant = db.query(User).filter(User.email == email_normalise).first()
    if existant is not None:
        raise EmailDejaUtiliseError("Cet e-mail est déjà utilisé")

    nom_normalise = nom.strip() if nom and nom.strip() else None
    user = User(email=email_normalise, mot_de_passe_hash=hash_password(mot_de_passe), nom=nom_normalise)
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


# ── Fédération d'identité Google [US-090] ──────────────────────────────────────

# Nature de l'événement de connexion fédérée — journalisée et exploitée par
# l'endpoint de callback, jamais stockée sur l'utilisateur (CA15).
FEDERATION_CONNEXION = "connexion"
FEDERATION_RATTACHEMENT = "rattachement"
FEDERATION_CREATION = "creation"
FEDERATION_CREATION_NON_VERIFIEE = "creation_non_verifiee"


@dataclass(frozen=True)
class ResultatFederation:
    """Compte résolu + nature de l'événement, pour que l'appelant sache s'il doit
    émettre des jetons (CA11/CA12) ou déclencher la vérification Brevo (CA13)."""
    user: User
    evenement: str


def connecter_ou_creer_via_google(
    db: Session,
    sub: str,
    email: Optional[str],
    email_verifie: bool,
    nom: Optional[str] = None,
) -> ResultatFederation:
    """[US-090 / CA11, CA12, CA13, CA14] Résout le compte correspondant à une
    identité Google déjà validée (cf. `app/services/oauth_google.py`).

    Trois chemins, dans cet ordre :

    1. `google_sub` déjà connu → connexion d'un compte déjà fédéré.
    2. E-mail déjà utilisé par un compte local :
       - Google atteste la vérification → rattachement automatique et silencieux
         (CA12), l'utilisateur retrouve ses potagers, aucun doublon, et son mot
         de passe continue de fonctionner (CA15 : deux méthodes coexistent).
       - Google ne l'atteste pas → refus (CA13), pour ne pas offrir la prise de
         contrôle d'un compte à qui contrôle un annuaire Workspace mal réglé.
    3. Aucun compte → création, `mot_de_passe_hash` à NULL, `email_verifie`
       recopié de l'attestation Google (CA11/CA13).

    La création écrit le compte **et** son `google_sub` dans le même INSERT : un
    compte créé sans son `sub` serait inconnectable au coup suivant tout en
    réservant définitivement l'adresse e-mail."""
    sub = (sub or "").strip()
    if not sub:
        raise FederationImpossibleError("Identité Google sans sub")

    user = db.query(User).filter(User.google_sub == sub).first()
    if user is not None:
        # [CA14] Compte déjà fédéré : le `sub` prime sur l'e-mail, qui peut avoir
        # changé côté Google depuis la première connexion.
        log.info("[US-090] Connexion fédérée — user_id=%s fournisseur=google", user.id)
        return ResultatFederation(user=user, evenement=FEDERATION_CONNEXION)

    email_normalise = (email or "").strip().lower()
    if not email_normalise:
        raise EmailGoogleAbsentError("Identité Google sans adresse e-mail")

    existant = db.query(User).filter(User.email == email_normalise).first()
    if existant is not None:
        if not email_verifie:
            log.info(
                "[US-090] Rattachement refusé (e-mail non attesté) — user_id=%s fournisseur=google",
                existant.id,
            )
            raise RattachementNonVerifieError("E-mail Google non attesté vérifié")

        existant.google_sub = sub
        # L'attestation Google vaut vérification : un compte local resté non
        # vérifié devient vérifié, sans repasser par Brevo.
        existant.email_verifie = True
        if not existant.nom and nom:
            existant.nom = nom.strip()
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            log.warning("[US-090] Rattachement en conflit — fournisseur=google")
            raise FederationImpossibleError("Rattachement impossible")
        db.refresh(existant)
        log.info("[US-090] Rattachement automatique — user_id=%s fournisseur=google", existant.id)
        return ResultatFederation(user=existant, evenement=FEDERATION_RATTACHEMENT)

    user = User(
        email=email_normalise,
        nom=(nom.strip() if nom and nom.strip() else None),
        mot_de_passe_hash=None,          # [CA11] compte sans mot de passe
        email_verifie=bool(email_verifie),
        google_sub=sub,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Deux connexions simultanées pour la même identité : la seconde
        # retombe sur le compte créé par la première plutôt que d'échouer.
        db.rollback()
        deja_cree = db.query(User).filter(User.google_sub == sub).first()
        if deja_cree is not None:
            log.info("[US-090] Connexion fédérée (création concurrente) — user_id=%s fournisseur=google", deja_cree.id)
            return ResultatFederation(user=deja_cree, evenement=FEDERATION_CONNEXION)
        log.warning("[US-090] Création fédérée en conflit — fournisseur=google")
        raise FederationImpossibleError("Création du compte fédéré impossible")

    db.refresh(user)
    evenement = FEDERATION_CREATION if user.email_verifie else FEDERATION_CREATION_NON_VERIFIEE
    log.info("[US-090] Création de compte fédéré — user_id=%s fournisseur=google", user.id)
    return ResultatFederation(user=user, evenement=evenement)


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

    Idempotent une fois le compte vérifié : revisiter le même lien renvoie un
    succès plutôt qu'une erreur. Nécessaire en pratique — de nombreux clients
    mail et scanners anti-virus (Brevo lui-même via son tracking de clics,
    Outlook Safe Links, etc.) déclenchent une requête GET automatique sur le
    lien avant même que l'utilisateur ne clique, ce qui consommait le token à
    son insu et lui affichait ensuite « lien invalide » alors que son compte
    était déjà vérifié. Seul un token qui ne correspond à AUCUN compte reste
    rejeté — impossible de vérifier un compte tiers avec un token volé qui ne
    lui appartient pas."""
    token_hash = _hash_token(token)
    user = db.query(User).filter(User.verification_token_hash == token_hash).first()
    if user is None:
        raise TokenVerificationInvalideError("Lien de vérification invalide")

    if user.email_verifie:
        return user

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


def demander_reset_mot_de_passe(db: Session, email: str) -> Optional[tuple[str, bool]]:
    """[US-057 / CA1] Génère un token de réinitialisation (1h) si un compte web
    existe pour cet e-mail. Renvoie None sinon (compte inconnu ou Telegram-only)
    — l'appelant renvoie la même réponse générique dans tous les cas
    (anti-énumération, même principe que CA12/CA7).

    [US-090 / CA17] Un compte créé via Google n'a pas de mot de passe : il est
    désormais éligible lui aussi, mais pour en **définir** un premier plutôt que
    d'en remplacer un. Le booléen renvoyé (`definition_initiale`) permet à
    l'appelant d'adapter l'e-mail — orienter vers la connexion Google ou vers la
    définition d'un mot de passe — au lieu de laisser croire que le compte
    n'existe pas. La preuve de possession de l'adresse reste la même : le lien
    n'arrive que dans la boîte du titulaire."""
    email_normalise = email.strip().lower()
    user = db.query(User).filter(User.email == email_normalise).first()
    if user is None:
        return None
    if not user.mot_de_passe_hash and not user.google_sub:
        # Compte Telegram-only : rien à réinitialiser ni à définir ici.
        return None

    token_brut = secrets.token_urlsafe(32)
    user.reset_mdp_token_hash = _hash_token(token_brut)
    user.reset_mdp_token_expire_le = datetime.utcnow() + _RESET_MDP_TOKEN_TTL
    user.reset_mdp_token_utilise_le = None
    db.commit()
    return token_brut, not user.mot_de_passe_hash


def reinitialiser_mot_de_passe(db: Session, token: str, nouveau_mot_de_passe: str) -> User:
    """[US-057 / CA3, CA4] Valide un token de réinitialisation et remplace le
    mot de passe. Usage unique (reset_mdp_token_utilise_le), même pattern que
    verifier_email — un rejeu du même token retombe sur TokenResetMdpInvalideError."""
    token_hash = _hash_token(token)
    user = db.query(User).filter(User.reset_mdp_token_hash == token_hash).first()
    if user is None or user.reset_mdp_token_utilise_le is not None:
        raise TokenResetMdpInvalideError("Lien de réinitialisation invalide")

    if user.reset_mdp_token_expire_le is None or datetime.utcnow() > user.reset_mdp_token_expire_le:
        raise TokenResetMdpExpireError("Lien de réinitialisation expiré")

    user.mot_de_passe_hash = hash_password(nouveau_mot_de_passe)
    user.reset_mdp_token_utilise_le = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return user

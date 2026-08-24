"""
app/services/oauth_google.py — Fédération d'identité Google OpenID Connect [US-090]
--------------------------------------------------------------------------------
Flux **Authorization Code + PKCE** (CA5) : le navigateur ne voit jamais le
`client_secret`, l'échange du code contre les jetons se fait exclusivement ici,
côté serveur. Les flux implicites sont exclus.

Ce module ne connaît ni la base de données ni les jetons applicatifs : il
produit un `ProfilGoogle` vérifié (sub, e-mail, attestation de vérification,
nom) que `app/services/auth.py` transforme en compte, et que `main.py` convertit
en jetons US-044. Aucun jeton Google n'est persisté, aucun *offline access*
n'est demandé (CA10).

⚠️ [CA19] Aucun secret ne transite par les logs : ni code d'autorisation, ni
`id_token`, ni `client_secret`, ni `code_verifier` — même en DEBUG. Les erreurs
sont loguées par leur nature (statut HTTP, type d'exception), jamais par leur
contenu.
"""
import base64
import hashlib
import logging
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx
from jose import JWTError, jwt

import config
from config import JWT_ALGORITHM, JWT_SECRET

log = logging.getLogger("potager")

# Points d'entrée Google — figés plutôt que redécouverts à chaque connexion via
# le document de discovery : ces URL sont stables depuis des années et un appel
# réseau de moins sur le chemin de connexion.
AUTORISATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
JWKS_URI = "https://www.googleapis.com/oauth2/v3/certs"

# [CA10] Scopes strictement limités — aucune donnée au-delà de l'identité.
SCOPES = "openid email profile"

# Les deux valeurs d'`iss` que Google émet indifféremment.
_ISSUERS = ("https://accounts.google.com", "accounts.google.com")

_TIMEOUT_SECONDES = 10.0
_ETAT_TTL = timedelta(minutes=10)
_ETAT_TYPE = "oauth_google_etat"
_JWKS_TTL_DEFAUT = 3600  # secondes, si Google n'envoie pas de Cache-Control

# Les identifiants sont recopiés en constantes de module : cela permet aux tests
# de les surcharger (`monkeypatch.setattr(oauth_google, "GOOGLE_CLIENT_ID", …)`)
# sans toucher à l'environnement réel ni recharger `config`.
GOOGLE_CLIENT_ID = config.GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET = config.GOOGLE_CLIENT_SECRET
GOOGLE_REDIRECT_URIS = list(config.GOOGLE_REDIRECT_URIS)


class OAuthGoogleError(Exception):
    """Erreur générique du flux Google — jamais présentée telle quelle (CA3)."""


class OAuthNonConfigureError(OAuthGoogleError):
    """[CA4] GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET absents de l'environnement."""


class RedirectUriNonAutoriseeError(OAuthGoogleError):
    """[CA8] `redirect_uri` hors de la liste blanche de configuration."""


class EtatOAuthInvalideError(OAuthGoogleError):
    """[CA6] `state` absent, expiré, altéré ou ne correspondant pas au cookie."""


class EchangeCodeError(OAuthGoogleError):
    """[CA3] Google a refusé l'échange du code, ou l'appel réseau a échoué."""


class IdTokenInvalideError(OAuthGoogleError):
    """[CA7] Signature, `iss`, `aud`, `exp` ou `nonce` de l'id_token refusés."""


@dataclass(frozen=True)
class DemandeAutorisation:
    """Tout ce qu'il faut pour lancer une connexion et la vérifier au retour."""
    url: str
    state: str
    nonce: str
    code_verifier: str
    redirect_uri: str


@dataclass(frozen=True)
class ProfilGoogle:
    """Identité vérifiée extraite d'un id_token Google validé (CA7)."""
    sub: str
    email: Optional[str]
    email_verifie: bool
    nom: Optional[str]


def est_configure() -> bool:
    """[CA4] Le connecteur Google est-il exploitable dans cet environnement ?

    Faux → le bouton n'est pas affiché côté PWA (masqué, pas en erreur) et les
    endpoints répondent 404 : dev local et tests tournent sans compte Google."""
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_REDIRECT_URIS)


def redirect_uri_par_defaut() -> str:
    """Première URI de la liste blanche — celle de l'environnement courant."""
    if not GOOGLE_REDIRECT_URIS:
        raise OAuthNonConfigureError("Aucune redirect_uri configurée")
    return GOOGLE_REDIRECT_URIS[0]


def valider_redirect_uri(redirect_uri: str) -> str:
    """[CA8] N'accepte qu'une URI issue de la liste blanche d'environnement.

    Comparaison stricte, à l'octet près : ni normalisation, ni préfixe, ni
    joker — c'est précisément ce qui empêche une redirection ouverte."""
    if redirect_uri not in GOOGLE_REDIRECT_URIS:
        log.warning("[US-090] redirect_uri rejetée (hors liste blanche)")
        raise RedirectUriNonAutoriseeError("redirect_uri non autorisée")
    return redirect_uri


def _code_challenge(code_verifier: str) -> str:
    """[CA5] Challenge PKCE S256 — base64url du SHA-256, sans padding."""
    empreinte = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(empreinte).rstrip(b"=").decode("ascii")


def preparer_autorisation(redirect_uri: Optional[str] = None) -> DemandeAutorisation:
    """[CA5, CA6] Construit l'URL d'autorisation Google et les secrets à vérifier
    au retour : `state` anti-CSRF, `nonce` anti-rejeu, `code_verifier` PKCE.

    Aucun `access_type=offline` et aucun scope au-delà d'`openid email profile`
    (CA10) : l'application n'a besoin que de l'identité, une seule fois."""
    if not est_configure():
        raise OAuthNonConfigureError("Connexion Google non configurée")

    uri = valider_redirect_uri(redirect_uri) if redirect_uri else redirect_uri_par_defaut()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)

    parametres = {
        "client_id": GOOGLE_CLIENT_ID,
        "response_type": "code",
        "scope": SCOPES,
        "redirect_uri": uri,
        "state": state,
        "nonce": nonce,
        "code_challenge": _code_challenge(code_verifier),
        "code_challenge_method": "S256",
        # Laisse l'utilisateur choisir son compte plutôt que de réutiliser
        # silencieusement la session Google déjà ouverte dans le navigateur.
        "prompt": "select_account",
    }
    return DemandeAutorisation(
        url=f"{AUTORISATION_ENDPOINT}?{urlencode(parametres)}",
        state=state,
        nonce=nonce,
        code_verifier=code_verifier,
        redirect_uri=uri,
    )


def signer_etat(demande: DemandeAutorisation) -> str:
    """[CA6] Sérialise `state` / `nonce` / `code_verifier` dans un jeton signé,
    destiné à un cookie `HttpOnly` + `SameSite=Lax` — jamais au `localStorage`,
    qui est lisible par tout script de la page.

    Signature HMAC avec le secret applicatif : le navigateur transporte la
    valeur sans pouvoir la forger ni la modifier. TTL 10 min, aligné sur la
    durée de vie réelle d'un aller-retour de consentement."""
    maintenant = datetime.now(timezone.utc)
    payload = {
        "typ": _ETAT_TYPE,
        "state": demande.state,
        "nonce": demande.nonce,
        "code_verifier": demande.code_verifier,
        "redirect_uri": demande.redirect_uri,
        "iat": maintenant,
        "exp": maintenant + _ETAT_TTL,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def lire_etat(cookie: Optional[str], state_recu: Optional[str]) -> dict:
    """[CA6] Relit le cookie d'état et vérifie qu'il correspond bien au `state`
    renvoyé par Google — anti-CSRF. Toute anomalie (cookie absent, expiré,
    signature invalide, `state` différent) donne la même erreur, sans détail
    exploitable."""
    if not cookie:
        raise EtatOAuthInvalideError("Cookie d'état absent")
    try:
        payload = jwt.decode(cookie, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise EtatOAuthInvalideError("Cookie d'état invalide ou expiré")

    if payload.get("typ") != _ETAT_TYPE:
        raise EtatOAuthInvalideError("Cookie d'état de type inattendu")
    if not state_recu or not secrets.compare_digest(str(payload.get("state", "")), state_recu):
        raise EtatOAuthInvalideError("State ne correspondant pas au cookie d'état")
    return payload


# ── Clés publiques JWKS ────────────────────────────────────────────────────────
# Mises en cache en respectant le `Cache-Control` de Google : ses clés tournent
# environ deux fois par jour, les retélécharger à chaque connexion ajouterait un
# aller-retour réseau inutile sur le chemin critique.
_jwks_cache: dict = {"cles": None, "expire_le": 0.0}


def _duree_cache(entete_cache_control: Optional[str]) -> int:
    """Extrait `max-age` d'un en-tête Cache-Control, sinon la valeur par défaut."""
    if not entete_cache_control:
        return _JWKS_TTL_DEFAUT
    for directive in entete_cache_control.split(","):
        directive = directive.strip().lower()
        if directive.startswith("max-age="):
            try:
                return max(int(directive.split("=", 1)[1]), 0)
            except ValueError:
                break
    return _JWKS_TTL_DEFAUT


def _telecharger_jwks() -> list[dict]:
    try:
        reponse = httpx.get(JWKS_URI, timeout=_TIMEOUT_SECONDES)
        reponse.raise_for_status()
    except httpx.HTTPError as exc:
        log.error("[US-090] Clés publiques Google inaccessibles (%s)", type(exc).__name__)
        raise IdTokenInvalideError("Clés publiques Google inaccessibles")

    cles = reponse.json().get("keys", [])
    _jwks_cache["cles"] = cles
    _jwks_cache["expire_le"] = time.time() + _duree_cache(reponse.headers.get("cache-control"))
    return cles


def _cle_pour(kid: Optional[str], forcer: bool = False) -> dict:
    """Renvoie la clé JWKS correspondant au `kid` de l'id_token.

    Un `kid` inconnu déclenche un unique rechargement (rotation de clés côté
    Google entre deux connexions), jamais une boucle."""
    cles = _jwks_cache["cles"]
    if forcer or not cles or time.time() >= _jwks_cache["expire_le"]:
        cles = _telecharger_jwks()

    for cle in cles:
        if cle.get("kid") == kid:
            return cle

    if not forcer:
        return _cle_pour(kid, forcer=True)
    raise IdTokenInvalideError("Clé de signature Google inconnue")


def valider_id_token(id_token: str, nonce: str) -> ProfilGoogle:
    """[CA7] Valide l'id_token **côté serveur** : signature via les clés publiques
    JWKS de Google, `iss`, `aud`, `exp`, puis `nonce`. Une simple lecture non
    vérifiée du JWT ne satisfait pas ce critère et n'a pas lieu ici.

    L'algorithme accepté est celui déclaré par la clé JWKS (source de confiance),
    jamais celui annoncé dans l'en-tête du jeton — c'est ce qui ferme les
    attaques par confusion d'algorithme (`alg: none`, HS256 signé avec la clé
    publique)."""
    try:
        entete = jwt.get_unverified_header(id_token)
    except JWTError:
        raise IdTokenInvalideError("id_token malformé")

    cle = _cle_pour(entete.get("kid"))
    algorithme = cle.get("alg") or "RS256"

    try:
        claims = jwt.decode(
            id_token,
            cle,
            algorithms=[algorithme],
            audience=GOOGLE_CLIENT_ID,
            # `iss` vérifié juste après, Google en émettant deux variantes ;
            # `at_hash` non vérifiable ici, l'access_token Google n'étant jamais
            # conservé (CA10).
            options={"verify_iss": False, "verify_at_hash": False},
        )
    except JWTError:
        raise IdTokenInvalideError("id_token refusé (signature, audience ou expiration)")

    if claims.get("iss") not in _ISSUERS:
        raise IdTokenInvalideError("Émetteur de l'id_token inattendu")
    if not nonce or not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise IdTokenInvalideError("Nonce absent ou ne correspondant pas à la demande")

    sub = str(claims.get("sub") or "").strip()
    if not sub:
        raise IdTokenInvalideError("id_token sans identifiant de compte (sub)")

    email = (claims.get("email") or "").strip().lower() or None
    nom = (claims.get("name") or "").strip() or None
    return ProfilGoogle(
        sub=sub,
        email=email,
        email_verifie=bool(claims.get("email_verified")),
        nom=nom,
    )


def echanger_code_contre_jetons(code: str, code_verifier: str, redirect_uri: str) -> dict:
    """[CA5] Échange le code d'autorisation contre les jetons, côté serveur.

    Le `client_secret` ne quitte jamais ce processus. Aucune donnée de la
    requête ni de la réponse n'est loguée (CA19) : en cas d'échec, seul le
    statut HTTP ou le type d'exception l'est."""
    if not est_configure():
        raise OAuthNonConfigureError("Connexion Google non configurée")

    donnees = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }
    try:
        reponse = httpx.post(TOKEN_ENDPOINT, data=donnees, timeout=_TIMEOUT_SECONDES)
    except httpx.HTTPError as exc:
        log.error("[US-090] Échange du code impossible (%s)", type(exc).__name__)
        raise EchangeCodeError("Échange du code impossible")

    if reponse.status_code != 200:
        # Cas typiques : consentement révoqué depuis le compte Google, code
        # déjà consommé, code expiré (10 min).
        log.warning("[US-090] Échange du code refusé par Google (HTTP %s)", reponse.status_code)
        raise EchangeCodeError("Échange du code refusé par Google")

    try:
        jetons = reponse.json()
    except ValueError:
        raise EchangeCodeError("Réponse Google illisible")

    if not jetons.get("id_token"):
        raise EchangeCodeError("Réponse Google sans id_token")
    return jetons


def recuperer_profil(code: str, code_verifier: str, redirect_uri: str, nonce: str) -> ProfilGoogle:
    """Enchaîne échange du code (CA5) puis validation de l'id_token (CA7).

    Les jetons Google sont utilisés le temps de cet appel puis abandonnés :
    rien n'est persisté (CA10)."""
    jetons = echanger_code_contre_jetons(code, code_verifier, redirect_uri)
    return valider_id_token(jetons["id_token"], nonce)

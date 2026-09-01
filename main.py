"""
main.py — Assistant Potager v2 (moteur Groq, gratuit)
─────────────────────────────────────────────────────
Endpoints :
  GET  /health      → vérifier que l'API tourne
  POST /parse       → dicter une commande vocale (JSON)
  POST /voice       → blob audio MediaRecorder → Whisper → intent → JSON (PWA iPhone)
  POST /ask         → poser une question analytique
  GET  /stats       → stats JSON instantanées (sans LLM)
  GET  /historique  → derniers événements avec filtres

Authentification [US-044] :
  POST /auth/register            → créer un compte (e-mail + mot de passe)
  POST /auth/login                → connexion → access token (15 min) + refresh token (30 j)
  POST /auth/refresh               → nouvel access token à partir d'un refresh token valide
  GET  /auth/verify-email          → valide le lien de vérification reçu par e-mail (CA9/CA10)
  POST /auth/resend-verification   → renvoie un e-mail de vérification (CA12)

Connexion Google — OpenID Connect [US-090] :
  GET  /auth/oauth/providers          → connecteurs réellement disponibles ici (CA4)
  GET  /auth/oauth/google/start       → redirige vers Google (Authorization Code + PKCE)
  GET  /auth/oauth/google/callback    → retour Google → jetons applicatifs US-044
Tous les endpoints métier ci-dessus exigent désormais un access token valide
(en-tête `Authorization: Bearer <token>`), sauf /health. La connexion est
refusée (403 EMAIL_NOT_VERIFIED) tant que l'e-mail du compte n'est pas
vérifié (CA11) — sauf pour les comptes créés avant cette fonctionnalité,
réputés vérifiés (migration_v24.sql).

Onboarding self-service [US-048] :
  POST   /potagers                              → créer un potager (owner + potager actif)
  GET    /potagers/{id}                          → détail d'un potager, réservé à ses membres [US-082]
  PATCH  /potagers/{id}                          → modifier nom/ville/localisation (owner) [US-074]
  POST   /parcelles                              → créer une parcelle (editor min.) [US-058]
  POST   /potagers/{id}/invitations              → inviter un membre par code (owner)
  POST   /invitations/{code}/accepter            → accepter une invitation
  GET    /potagers/{id}/membres                  → lister les membres d'un potager
  DELETE /potagers/{id}/membres/{membre_user_id} → retirer un membre (owner)
  POST   /potagers/{id}/archiver                 → archiver un potager, lecture seule (owner) [US-083]
  POST   /potagers/{id}/desarchiver              → désarchiver un potager (owner) [US-083]
  GET    /potagers/{id}/impact-suppression       → décompte réel avant suppression (owner) [US-084]
  DELETE /potagers/{id}                          → supprimer un potager archivé, délai de grâce 30 j (owner) [US-084]
  GET    /potagers/corbeille                     → potagers supprimés restaurables (owner) [US-084]
  POST   /potagers/{id}/restaurer                → restaurer un potager supprimé (owner) [US-084]

Météo personnalisée [US-075] :
  GET /meteo → météo du jour + prévision 5 jours, sur la localisation du potager actif

Observabilité de la cascade de réponses + retour du jardinier [US-097] :
  POST /routage/{routage_log_id}/retour  → avis 👍/👎 sur une réponse de savoir/raisonnement
  GET  /admin/routage/metriques          → métriques de routage (réservé à ADMIN_EMAIL)
  GET  /admin/routage/retours-negatifs   → questions les plus souvent jugées mauvaises (réservé)
"""
import json
import logging
import os
import re
import tempfile
import uuid
from datetime import date
from typing import Optional
from urllib.parse import urlencode
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# ── Version [US-008] ────────────────────────────────────────────────────────────
def _lire_version() -> str:
    try:
        _base = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(_base, "VERSION"), encoding="utf-8") as _f:
            return _f.read().strip()
    except OSError:
        return "inconnue"

_APP_VERSION = _lire_version()

from database.db import Base, engine, SessionLocal, tenant_scope, current_potager_id
import utils.stock as _stock_mod
from utils.observations import build_observations_index
from llm.groq_client import parse_commande, transcribe_audio, classify_intent_pwa
# [US-092] Mode dégradé : une indisponibilité du fournisseur de modèles est
# convertie en 503 explicite portant le message de repli, jamais en erreur brute.
from llm.passerelle import LLMIndisponibleError, MESSAGE_REPLI_IA
from llm.rag import add_to_rag
from database.models import User, Potager
from app.services.context import default_context, TenantContext, DEFAULT_POTAGER_ID
from app.services import auth as svc_auth
from app.services import email as svc_email
from app.services import liaison_telegram as svc_liaison_telegram
from app.services import telegram_notify as svc_telegram_notify  # [US-091]
from app.services import oauth_google as svc_oauth_google  # [US-090]
from app.services import potager_actif as svc_potager_actif
from app.services import potagers as svc_potagers
from app.services import evenements as svc_evenements
from app.services.permissions import require_role, PermissionInsuffisanteError, PotagerArchiveError  # [US-047, US-083]
from app.services import stats as svc_stats
from app.services import plan as svc_plan
from app.services import questions as svc_questions
from app.services import parcelles as svc_parcelles
from app.services import stock as svc_stock  # [US-065]
from app.services import familles as svc_familles  # [US-067]
from utils.culture_resolve import normaliser_culture
from app.services import retours as svc_retours  # [US-097]
from app.services import metriques_routage as svc_metriques_routage  # [US-097]
from config import FRONTEND_URL, ADMIN_EMAIL  # [US-090, US-097]

log = logging.getLogger("potager")


# ── [US-090 / CA19] Masquage des secrets OAuth dans les logs d'accès ───────────
# Le code d'autorisation Google transite en clair dans la query string du
# callback : sans ce filtre, le logger d'accès d'uvicorn l'écrirait tel quel
# dans les journaux du serveur. Le filtre s'applique à la source (le logger
# `uvicorn.access`) plutôt qu'au format de log, pour couvrir aussi les
# éventuelles traces d'exception qui reprennent l'URL.
class _FiltreSecretsOAuth(logging.Filter):
    """Remplace la valeur des paramètres sensibles par `[masqué]` dans les logs."""

    _MOTIF = re.compile(r"\b(code|id_token|code_verifier|client_secret)=[^&\s\"']+")

    def _masquer(self, texte: str) -> str:
        return self._MOTIF.sub(r"\1=[masqué]", texte)

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._masquer(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(
                self._masquer(arg) if isinstance(arg, str) else arg for arg in record.args
            )
        return True


logging.getLogger("uvicorn.access").addFilter(_FiltreSecretsOAuth())

# ── Initialisation ─────────────────────────────────────────────────────────────
app = FastAPI(title="Assistant Potager 🌿", version=_APP_VERSION)
Base.metadata.create_all(bind=engine)   # crée la table si elle n'existe pas

# ── Rate limiting [US-044 / CA8] — protège /auth/login et /auth/register ──────
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


def _cle_rate_limit_par_compte(request: Request) -> str:
    """[US-091 / CA17] Clé de débit par compte plutôt que par IP — un même
    utilisateur ne doit pas pouvoir contourner la limite en changeant de
    réseau, et plusieurs comptes derrière la même IP (box familiale, réseau
    partagé) ne doivent pas se limiter mutuellement, alors que le deep-link
    multiplie les appels à cet endpoint.

    Décode directement le Bearer token plutôt que de dépendre de
    `get_current_user` (les dépendances FastAPI ne sont pas résolues avant que
    slowapi n'évalue la clé) — retombe sur l'IP si l'en-tête est absent ou
    invalide, la dépendance de la route rejettera alors la requête avec le bon
    code d'erreur ; la limite par IP reste un filet de sécurité dans ce cas."""
    entete = request.headers.get("authorization", "")
    if entete.lower().startswith("bearer "):
        try:
            payload = svc_auth.decoder_access_token(entete[7:].strip())
            return f"user:{payload['sub']}"
        except (svc_auth.TokenExpireError, svc_auth.TokenInvalideError):
            pass
    return get_remote_address(request)

# ── CORS — autorise le frontend Netlify + dev local ────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",        # dev React local
        "http://localhost:5173",        # dev Vite local
        "https://*.netlify.app",        # frontend Netlify (prod)
    ],
    allow_methods=["GET", "POST", "DELETE", "PATCH"],  # DELETE [US-048] membres, PATCH [US-074] modifier_potager
    allow_headers=["Authorization", "Content-Type"],
)


# [US-043] Arme app.potager_id (défense en profondeur RLS) pour toute la durée
# de traitement de chaque requête HTTP. [US-044] Le potager_id reste celui de
# default_context() (DEFAULT_POTAGER_ID) tant que US-046 (potager actif choisi
# par l'utilisateur authentifié) n'est pas livrée — seul user_id/role varient
# désormais avec get_current_user_ctx() ci-dessous.
@app.middleware("http")
async def _tenant_context_middleware(request, call_next):
    with tenant_scope(default_context().potager_id):
        return await call_next(request)


# ── Authentification [US-044] ──────────────────────────────────────────────────
_security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
) -> User:
    """[CA4/CA5] Dépendance FastAPI : exige un access token JWT valide, renvoie
    l'utilisateur authentifié — SANS résoudre de potager (identité seule).

    Renvoie 401 avec un `code` distinct selon le cas (absent / invalide /
    expiré) pour permettre au front de déclencher un refresh automatique
    uniquement sur `token_expired`. Utilisée pour les endpoints qui n'ont pas
    besoin de scope potager (ex. génération de code de liaison Telegram,
    listing des potagers — un utilisateur peut agir sur ces endpoints avant
    même d'appartenir à un potager).
    """
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "token_missing", "message": "Authentification requise"},
        )
    try:
        payload = svc_auth.decoder_access_token(credentials.credentials)
    except svc_auth.TokenExpireError:
        raise HTTPException(
            status_code=401,
            detail={"code": "token_expired", "message": "Session expirée, veuillez la rafraîchir"},
        )
    except svc_auth.TokenInvalideError:
        raise HTTPException(
            status_code=401,
            detail={"code": "token_invalid", "message": "Token invalide"},
        )

    db = SessionLocal()
    try:
        user = svc_auth.obtenir_utilisateur_par_id(db, int(payload["sub"]))
        if user is None:
            raise HTTPException(
                status_code=401,
                detail={"code": "token_invalid", "message": "Utilisateur introuvable"},
            )
        return user
    finally:
        db.close()


def get_current_user_ctx(user: User = Depends(get_current_user)) -> TenantContext:
    """[US-046 / CA6] Dépendance FastAPI : identité + potager actif réel — pour
    tous les endpoints métier qui lisent/écrivent des données scopées par
    potager. Renvoie 409 explicite si l'utilisateur n'appartient à aucun
    potager (CA5) — plus de DEFAULT_POTAGER_ID en dur."""
    db = SessionLocal()
    try:
        try:
            tenant_ctx = svc_potager_actif.resoudre_tenant_context(db, user.id)
            # [US-043] Réarme le GUC RLS avec le vrai potager (le middleware
            # l'avait initialisé sur default_context().potager_id avant que
            # cette dépendance ne s'exécute).
            current_potager_id.set(tenant_ctx.potager_id)
            return tenant_ctx
        except svc_potager_actif.AucunPotagerError:
            raise HTTPException(
                status_code=409,
                detail={"code": "no_potager", "message": "Aucun potager associé à ce compte"},
            )
    finally:
        db.close()


def require_admin_user(user: User = Depends(get_current_user)) -> User:
    """[US-097 / CA7] Dépendance FastAPI : réserve un endpoint au compte
    administrateur de la plateforme (`ADMIN_EMAIL`, variable d'environnement).
    `ADMIN_EMAIL` absent/vide → 403 systématique, jamais de repli implicite."""
    if not ADMIN_EMAIL or (user.email or "").strip().lower() != ADMIN_EMAIL.strip().lower():
        raise HTTPException(status_code=403, detail="Réservé à l'administrateur de la plateforme")
    return user


def ctx_pour_potager_consulte(db, ctx: TenantContext, potager_id: Optional[int]) -> TenantContext:
    """[US-083 / CA7] `potager_id` optionnel permet de consulter un autre
    potager que l'actif (typiquement un potager archivé, en lecture seule) —
    vérifie l'accès de l'utilisateur et renvoie un TenantContext ciblant ce
    potager. Sans `potager_id`, renvoie `ctx` (potager actif) inchangé.

    [Test] `isinstance` plutôt que `is None` : les tests qui appellent les
    fonctions d'endpoint directement (hors résolution FastAPI, cf.
    `test_us039_observations_frontend.py`) laissent `potager_id` à sa valeur
    par défaut `Query(default=None)` quand il n'est pas explicitement passé —
    jamais résolue en `None` puisque `Depends`/`Query` ne s'exécutent pas."""
    if not isinstance(potager_id, int):
        return ctx
    potager_detail = svc_potager_actif.obtenir_potager(db, ctx.user_id, potager_id)
    if potager_detail is None:
        raise HTTPException(status_code=403, detail="Vous n'êtes pas membre de ce potager")
    return TenantContext(user_id=ctx.user_id, potager_id=potager_id, role=potager_detail.get("role"))


class RegisterRequest(BaseModel):
    email: str
    mot_de_passe: str
    nom: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    mot_de_passe: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ResendVerificationRequest(BaseModel):
    email: str


class MotDePasseOublieRequest(BaseModel):
    email: str


class ReinitialiserMotDePasseRequest(BaseModel):
    token: str
    nouveau_mot_de_passe: str


@app.post("/auth/register", status_code=201)
@limiter.limit("5/minute")
def auth_register(request: Request, req: RegisterRequest):
    """[CA1/CA7] Inscription par e-mail + mot de passe. Mot de passe haché (bcrypt),
    jamais stocké ni loggé en clair. 409 si l'e-mail est déjà utilisé."""
    if not req.email or "@" not in req.email:
        raise HTTPException(status_code=400, detail="E-mail invalide")
    if not req.mot_de_passe or len(req.mot_de_passe) < 8:
        raise HTTPException(status_code=400, detail="Mot de passe trop court (8 caractères minimum)")

    db = SessionLocal()
    try:
        user = svc_auth.inscrire_utilisateur(db, req.email, req.mot_de_passe, req.nom)
        # [CA9] Envoi de l'e-mail de vérification — un échec d'envoi (réseau,
        # API Brevo indisponible) est loggé côté service mais ne fait pas
        # échouer l'inscription (l'utilisateur peut redemander via
        # /auth/resend-verification).
        token = svc_auth.demarrer_verification_email(db, user)
        svc_email.envoyer_email_verification(user.email, token)
        return {"id": user.id, "email": user.email}
    except svc_auth.EmailDejaUtiliseError:
        db.rollback()
        # [CA7] Message générique — ne confirme pas explicitement que le compte existe
        raise HTTPException(status_code=409, detail="Inscription impossible avec ces informations")
    finally:
        db.close()


@app.post("/auth/login")
@limiter.limit("10/minute")
def auth_login(request: Request, req: LoginRequest):
    """[CA2] Connexion — renvoie un access token (15 min) et un refresh token (30 j).
    [CA11] 403 EMAIL_NOT_VERIFIED si l'e-mail du compte n'est pas encore vérifié."""
    db = SessionLocal()
    try:
        user = svc_auth.authentifier_utilisateur(db, req.email, req.mot_de_passe)
    except svc_auth.IdentifiantsInvalidesError:
        raise HTTPException(status_code=401, detail="E-mail ou mot de passe incorrect")
    except svc_auth.EmailNonVerifieError:
        raise HTTPException(
            status_code=403,
            detail={"code": "EMAIL_NOT_VERIFIED", "message": "Vérifiez votre e-mail avant de vous connecter"},
        )
    finally:
        db.close()

    return {
        "access_token": svc_auth.creer_access_token(user.id),
        "refresh_token": svc_auth.creer_refresh_token(user.id),
        "token_type": "bearer",
    }


@app.post("/auth/refresh")
def auth_refresh(req: RefreshRequest):
    """[CA3] Nouvel access token à partir d'un refresh token valide, sans redemander le mot de passe."""
    try:
        payload = svc_auth.decoder_refresh_token(req.refresh_token)
    except svc_auth.TokenExpireError:
        raise HTTPException(status_code=401, detail={"code": "token_expired", "message": "Refresh token expiré"})
    except svc_auth.TokenInvalideError:
        raise HTTPException(status_code=401, detail={"code": "token_invalid", "message": "Refresh token invalide"})

    return {
        "access_token": svc_auth.creer_access_token(int(payload["sub"])),
        "token_type": "bearer",
    }


@app.get("/auth/verify-email")
def auth_verify_email(token: str):
    """[CA10] Valide le lien de vérification reçu par e-mail (clic direct, GET).
    Usage unique : un rejeu du même token renvoie la même erreur qu'un token
    invalide, sans distinction exploitable."""
    db = SessionLocal()
    try:
        svc_auth.verifier_email(db, token)
        return {"message": "E-mail vérifié avec succès"}
    except svc_auth.TokenVerificationInvalideError:
        raise HTTPException(
            status_code=400,
            detail={"code": "TOKEN_INVALID", "message": "Lien de vérification invalide"},
        )
    except svc_auth.TokenVerificationExpireError:
        raise HTTPException(
            status_code=400,
            detail={"code": "TOKEN_EXPIRED", "message": "Lien de vérification expiré, demandez-en un nouveau"},
        )
    finally:
        db.close()


@app.post("/auth/resend-verification")
@limiter.limit("5/minute")
def auth_resend_verification(request: Request, req: ResendVerificationRequest):
    """[CA12] Renvoie un e-mail de vérification si le compte existe et n'est
    pas encore vérifié. Réponse générique identique dans tous les cas
    (compte inconnu, déjà vérifié, ou renvoi effectif) — anti-énumération,
    cohérent avec CA7."""
    db = SessionLocal()
    try:
        token = svc_auth.renvoyer_verification_email(db, req.email)
        if token:
            svc_email.envoyer_email_verification(req.email, token)
    finally:
        db.close()
    return {"message": "Si un compte existe pour cet e-mail, un lien de vérification a été envoyé"}


@app.post("/auth/mot-de-passe-oublie")
@limiter.limit("5/minute")
def auth_mot_de_passe_oublie(request: Request, req: MotDePasseOublieRequest):
    """[US-057 / CA1] Envoie un e-mail de réinitialisation si le compte existe
    et a un mot de passe défini. Réponse générique identique dans tous les cas
    (compte inconnu, Telegram-only, ou envoi effectif) — anti-énumération,
    même principe que /auth/resend-verification (CA12)."""
    db = SessionLocal()
    try:
        # [US-090 / CA17] Un compte créé via Google est éligible lui aussi —
        # l'e-mail envoyé l'oriente alors vers « Continuer avec Google » ou vers
        # la définition d'un premier mot de passe.
        resultat = svc_auth.demander_reset_mot_de_passe(db, req.email)
        if resultat:
            token, definition_initiale = resultat
            svc_email.envoyer_email_reset_mdp(req.email, token, definition_initiale=definition_initiale)
    finally:
        db.close()
    return {"message": "Si un compte existe pour cet e-mail, un lien de réinitialisation a été envoyé"}


@app.post("/auth/reinitialiser-mot-de-passe")
@limiter.limit("10/minute")
def auth_reinitialiser_mot_de_passe(request: Request, req: ReinitialiserMotDePasseRequest):
    """[US-057 / CA3, CA4] Valide le token reçu par e-mail et remplace le mot
    de passe. Usage unique : un rejeu du même token renvoie la même erreur
    qu'un token invalide, sans distinction exploitable."""
    if not req.nouveau_mot_de_passe or len(req.nouveau_mot_de_passe) < 8:
        raise HTTPException(status_code=400, detail="Mot de passe trop court (8 caractères minimum)")

    db = SessionLocal()
    try:
        svc_auth.reinitialiser_mot_de_passe(db, req.token, req.nouveau_mot_de_passe)
        return {"message": "Mot de passe mis à jour"}
    except svc_auth.TokenResetMdpInvalideError:
        raise HTTPException(
            status_code=400,
            detail={"code": "TOKEN_INVALID", "message": "Lien de réinitialisation invalide"},
        )
    except svc_auth.TokenResetMdpExpireError:
        raise HTTPException(
            status_code=400,
            detail={"code": "TOKEN_EXPIRED", "message": "Lien de réinitialisation expiré, demandez-en un nouveau"},
        )
    finally:
        db.close()


# ── Connexion Google — OpenID Connect [US-090] ────────────────────────────────
# Cookie d'état signé (state + nonce + code_verifier), `HttpOnly` + `SameSite=Lax`
# et cantonné au chemin du flux : jamais de `localStorage` (CA6). `Lax` suffit —
# le retour de Google est une navigation GET de premier niveau, le seul cas où
# un cookie `Lax` est bien transmis depuis un site tiers.
_COOKIE_OAUTH_GOOGLE = "potager_oauth_google"
_CHEMIN_COOKIE_OAUTH = "/auth/oauth/google"


def _retour_pwa(**fragment: str) -> RedirectResponse:
    """Renvoie l'utilisateur sur la PWA, résultat de la fédération dans le
    fragment d'URL.

    Le fragment (`#…`) plutôt que la query string : il n'est jamais transmis au
    serveur, n'apparaît donc ni dans les logs d'accès ni dans l'en-tête
    `Referer` (CA19). L'URL de destination vient de la configuration, jamais
    d'un paramètre de la requête — aucune redirection ouverte possible.
    Le cookie d'état est détruit dans tous les cas : succès comme échec."""
    url = f"{FRONTEND_URL.rstrip('/')}/auth/callback#{urlencode(fragment)}"
    reponse = RedirectResponse(url, status_code=302)
    reponse.delete_cookie(_COOKIE_OAUTH_GOOGLE, path=_CHEMIN_COOKIE_OAUTH)
    return reponse


@app.get("/auth/oauth/providers")
def auth_oauth_providers():
    """[CA4] Connecteurs réellement utilisables dans cet environnement.

    La PWA masque purement et simplement le bouton Google quand il vaut `false`
    — pas de bouton en erreur, pas de « bientôt disponible » : sans identifiants
    Google configurés, le connecteur n'existe pas pour l'utilisateur."""
    return {"google": svc_oauth_google.est_configure()}


@app.get("/auth/oauth/google/start")
@limiter.limit("10/minute")
def auth_oauth_google_start(request: Request):
    """[CA5, CA6] Démarre le flux Authorization Code + PKCE et redirige vers
    l'écran de consentement Google.

    Rien de sensible n'est confié au navigateur : `code_verifier`, `state` et
    `nonce` partent dans un cookie signé `HttpOnly`, seul le `code_challenge`
    (leur empreinte) circule dans l'URL."""
    if not svc_oauth_google.est_configure():
        raise HTTPException(status_code=404, detail="Connexion Google non disponible")

    demande = svc_oauth_google.preparer_autorisation()
    reponse = RedirectResponse(demande.url, status_code=302)
    reponse.set_cookie(
        key=_COOKIE_OAUTH_GOOGLE,
        value=svc_oauth_google.signer_etat(demande),
        max_age=600,
        httponly=True,
        samesite="lax",
        # `Secure` dès que le flux est en HTTPS — laissé à False en dev local
        # sur http://localhost, où le navigateur refuserait le cookie sinon.
        secure=demande.redirect_uri.startswith("https://"),
        path=_CHEMIN_COOKIE_OAUTH,
    )
    log.info("[US-090] Demande d'autorisation émise — fournisseur=google")
    return reponse


@app.get("/auth/oauth/google/callback")
def auth_oauth_google_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    """[CA3, CA5, CA7, CA10-CA14] Retour de Google : vérifie l'état, échange le
    code côté serveur, valide l'id_token, puis résout ou crée le compte et émet
    les jetons **applicatifs** US-044 (access 15 min + refresh 30 j).

    Aucun jeton Google n'est conservé. Tous les chemins d'échec ramènent
    l'utilisateur sur l'écran de connexion avec un code de message
    compréhensible (CA3) — jamais de page blanche ni de trace technique."""
    if error:
        # Consentement refusé, fenêtre fermée, accès révoqué côté compte Google.
        log.info("[US-090] Autorisation non accordée (%s) — fournisseur=google", error)
        return _retour_pwa(erreur="acces_refuse")

    try:
        etat = svc_oauth_google.lire_etat(request.cookies.get(_COOKIE_OAUTH_GOOGLE), state)
    except svc_oauth_google.EtatOAuthInvalideError:
        log.warning("[US-090] État de connexion invalide — fournisseur=google")
        return _retour_pwa(erreur="etat_invalide")

    if not code:
        return _retour_pwa(erreur="echec_google")

    try:
        profil = svc_oauth_google.recuperer_profil(
            code=code,
            code_verifier=etat["code_verifier"],
            redirect_uri=etat["redirect_uri"],
            nonce=etat["nonce"],
        )
    except svc_oauth_google.OAuthGoogleError:
        return _retour_pwa(erreur="echec_google")

    db = SessionLocal()
    try:
        try:
            resultat = svc_auth.connecter_ou_creer_via_google(
                db,
                sub=profil.sub,
                email=profil.email,
                email_verifie=profil.email_verifie,
                nom=profil.nom,
            )
        except svc_auth.RattachementNonVerifieError:
            # [CA13] Compte existant + e-mail non attesté : pas de rattachement
            # automatique, l'utilisateur passe par son mot de passe.
            return _retour_pwa(erreur="email_non_verifie")
        except (svc_auth.EmailGoogleAbsentError, svc_auth.FederationImpossibleError):
            return _retour_pwa(erreur="echec_google")

        if resultat.evenement == svc_auth.FEDERATION_CREATION_NON_VERIFIEE:
            # [CA13] Création avec un e-mail non attesté : le compte reste non
            # vérifié et repasse par le parcours Brevo d'US-044.
            token = svc_auth.demarrer_verification_email(db, resultat.user)
            svc_email.envoyer_email_verification(resultat.user.email, token)
            return _retour_pwa(info="verification_requise")

        return _retour_pwa(
            access_token=svc_auth.creer_access_token(resultat.user.id),
            refresh_token=svc_auth.creer_refresh_token(resultat.user.id),
            evenement=resultat.evenement,
        )
    finally:
        db.close()


@app.get("/auth/me")
def auth_me(user: User = Depends(get_current_user)):
    """[US-055 / CA1] Identité du compte connecté + état de la liaison Telegram,
    pour le menu Compte de la PWA (nom, e-mail, « relié / à faire »).

    Lecture seule sur des colonnes existantes — aucune règle métier nouvelle.
    Identité seule (pas de potager requis, même dépendance que
    /auth/lien/generer-code) : le menu Compte doit rester consultable par un
    compte qui n'appartient encore à aucun potager (cf. US-046 / CA5).
    Le rôle n'est volontairement pas renvoyé ici : il dépend du potager actif
    et vient déjà de GET /potagers.
    """
    return {
        "id": user.id,
        "email": user.email,
        "nom": user.nom,
        # Booléen plutôt que le chat_id lui-même : le front n'a besoin que de
        # l'état, et l'identifiant Telegram n'a pas à circuler côté navigateur.
        "telegram_lie": user.telegram_chat_id is not None,
        # [US-091] Identifiant public du bot, déduit du token via l'API
        # Telegram (getMe, mis en cache) — jamais une variable d'environnement
        # séparée à maintenir en double par environnement, cf.
        # app/services/telegram_notify.py::obtenir_username_bot. Vide en cas
        # d'échec : le front retombe alors sur le seul code manuel, sans
        # bouton ni QR.
        "bot_username": svc_telegram_notify.obtenir_username_bot(),
    }


@app.post("/auth/lien/generer-code")
@limiter.limit("5/hour", key_func=_cle_rate_limit_par_compte)
def auth_generer_code_liaison(request: Request, user: User = Depends(get_current_user)):
    """[US-045 / CA1 ; US-091 / CA17] Génère un code à usage unique (TTL 10 min)
    pour lier ce compte web à un chat Telegram via la commande /lier du bot (ou
    le deep-link /start). Identité seule (pas de potager requis) : on doit
    pouvoir lier son Telegram avant même d'appartenir à un potager.

    Limité à 5 générations/heure/compte (CA17) : le deep-link et le QR de
    l'écran d'activation en multiplient les appels par rapport à la simple
    modale existante."""
    db = SessionLocal()
    try:
        liaison = svc_liaison_telegram.creer_code_liaison(db, user.id)
        # [Fix] expire_le est un datetime naïf en UTC (datetime.utcnow()) — sans
        # suffixe "Z", le navigateur interprète l'ISO string comme une heure
        # locale et décale le compte à rebours de l'offset du fuseau client.
        return {"code": liaison.code, "expire_le": liaison.expire_le.isoformat() + "Z"}
    finally:
        db.close()


@app.post("/auth/lien/delier")
def auth_delier(user: User = Depends(get_current_user)):
    """[US-050 / CA1] Dissocie le chat Telegram actuellement lié à ce compte.
    Identité seule (pas de potager requis, CA5) — même dépendance que
    /auth/lien/generer-code, jamais get_current_user_ctx pour cette action."""
    db = SessionLocal()
    try:
        svc_liaison_telegram.delier_chat_id(db, user.id)
        return {"success": True}
    finally:
        db.close()


@app.get("/potagers")
def lister_potagers(etat: str = "actif", user: User = Depends(get_current_user)):
    """[US-046 / CA2, CA5] Liste les potagers de l'utilisateur connecté, potager
    actif marqué. Identité seule : une liste vide est une réponse valide (CA5),
    pas une erreur — c'est au frontend de proposer la création/adhésion.

    [US-080 / CA5] `etat` filtre le cycle de vie : `actif` (défaut),
    `archive` ou `tous`. Un potager supprimé n'apparaît dans aucun cas."""
    db = SessionLocal()
    try:
        try:
            potagers = svc_potager_actif.lister_potagers_utilisateur(db, user.id, etat)
        except svc_potager_actif.FiltreEtatInvalideError as e:
            raise HTTPException(status_code=400, detail=str(e))
        potager_actif_id = None
        if potagers:
            try:
                potager_actif_id = svc_potager_actif.resoudre_tenant_context(db, user.id).potager_id
            except svc_potager_actif.AucunPotagerError:
                pass
        # [US-054 / CA1] Compteurs affichés dans le sélecteur de potager —
        # deux requêtes groupées, indépendantes du nombre de potagers.
        ids = [p.id for p in potagers]
        nb_parcelles = svc_potager_actif.compter_parcelles_par_potager(db, ids)
        nb_membres = svc_potager_actif.compter_membres_par_potager(db, ids)
        return {
            "potagers": [
                {
                    "id": p.id,
                    "nom": p.nom,
                    "actif": p.id == potager_actif_id,
                    # [US-080 / CA5] État du cycle de vie ('actif' | 'archive'),
                    # à ne pas confondre avec `actif` ci-dessus qui désigne le
                    # potager actuellement sélectionné par l'utilisateur.
                    "etat": p.etat,
                    # [US-048] rôle exposé pour que le frontend affiche la gestion
                    # des membres (inviter/retirer) uniquement aux owners.
                    "role": svc_potager_actif.role_utilisateur(db, user.id, p.id),
                    "nb_parcelles": nb_parcelles.get(p.id, 0),
                    "nb_membres": nb_membres.get(p.id, 0),
                    # [US-074 / CA5, CA6] Pré-remplissage du formulaire « Modifier le
                    # potager » — jamais de valeur par défaut inventée, `None` tel quel
                    # tant que la localisation n'a pas été renseignée.
                    "ville": p.ville,
                    "latitude": p.latitude,
                    "longitude": p.longitude,
                }
                for p in potagers
            ],
        }
    finally:
        db.close()


@app.get("/potagers/corbeille")
def lister_corbeille_potagers(user: User = Depends(get_current_user)):
    """[US-084 / CA6] Potagers supprimés restaurables — point d'accès dédié du
    droit au remords, réservé à leur owner.

    ⚠️ Déclarée AVANT `/potagers/{potager_id}` : FastAPI résout les routes dans
    l'ordre de déclaration, l'ordre inverse ferait tomber « corbeille » dans le
    paramètre entier `potager_id` (422). Un potager supprimé n'apparaît nulle
    part ailleurs (US-080 / CA7), y compris avec `etat=tous`."""
    db = SessionLocal()
    try:
        return {
            "potagers": [
                {
                    "id": p["id"],
                    "nom": p["nom"],
                    "etat": p["etat"],
                    "supprime_le": p["supprime_le"].isoformat() + "Z" if p["supprime_le"] else None,
                    "purge_prevue_le": p["purge_prevue_le"].isoformat() + "Z" if p["purge_prevue_le"] else None,
                }
                for p in svc_potagers.lister_potagers_supprimes(db, user.id)
            ],
            "delai_grace_jours": svc_potagers.DELAI_GRACE_JOURS,
        }
    finally:
        db.close()


@app.get("/potagers/{potager_id}")
def detail_potager(potager_id: int, user: User = Depends(get_current_user)):
    """[US-082 / CA2, CA6, CA7, CA8] Détail d'un potager pour l'écran Paramètres
    — réservé à ses membres, quel que soit leur rôle (CA6 : le frontend adapte
    l'affichage aux droits, cette lecture reste ouverte à tout membre). Un
    potager inexistant, supprimé ou dont l'appelant n'est pas membre reçoit le
    même refus générique, sans révéler laquelle de ces situations s'applique
    (même principe que GET /potagers/{id}/membres)."""
    db = SessionLocal()
    try:
        detail = svc_potager_actif.obtenir_potager(db, user.id, potager_id)
        if detail is None:
            raise HTTPException(status_code=403, detail="Vous n'êtes pas membre de ce potager")
        return detail
    finally:
        db.close()


@app.post("/potagers/{potager_id}/activer")
def activer_potager(potager_id: int, user: User = Depends(get_current_user)):
    """[US-046 / CA2, CA3, CA4] Change le potager actif de l'utilisateur connecté."""
    db = SessionLocal()
    try:
        try:
            nouveau_ctx = svc_potager_actif.definir_potager_actif(db, user.id, potager_id)
        except svc_potager_actif.PotagerNonMembreError:
            raise HTTPException(status_code=403, detail="Vous n'êtes pas membre de ce potager")
        except svc_potager_actif.PotagerInactifError as e:
            # [US-080 / CA6] 409 et non 403 : les droits sont là, c'est l'état du
            # potager qui bloque — le désarchivage (US-083) lève l'obstacle.
            raise HTTPException(status_code=409, detail=str(e))
        return {"potager_id": nouveau_ctx.potager_id, "role": nouveau_ctx.role}
    finally:
        db.close()


class CreerPotagerRequest(BaseModel):
    nom: str
    ville: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    # [US-081 / CA3, CA4] Bascule sur le potager créé. `True` par défaut :
    # l'onboarding (US-058) n'envoie pas ce champ et ne doit rien changer.
    activer: bool = True


class ModifierPotagerRequest(BaseModel):
    nom: Optional[str] = None
    ville: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class InviterMembreRequest(BaseModel):
    role_propose: str
    email_invite: Optional[str] = None


@app.post("/potagers", status_code=201)
def creer_potager(req: CreerPotagerRequest, user: User = Depends(get_current_user)):
    """[US-048 / CA1, CA2] Crée un potager — l'utilisateur en devient owner et
    ce potager devient son potager actif. Identité seule (pas de potager requis
    au préalable, CA7). [US-074 / CA3] `ville` est optionnelle, choisie via le
    module de recherche de ville unifié.

    [US-081 / CA3, CA4, CA7] Sert aussi la création d'un potager **additionnel**
    depuis la PWA : `activer=false` crée le potager sans quitter le potager
    courant. Un nom déjà porté par un autre potager de l'utilisateur reste
    autorisé (l'avertissement est purement informatif, côté interface)."""
    if not req.nom or not req.nom.strip():
        raise HTTPException(status_code=400, detail="Nom de potager requis")
    db = SessionLocal()
    try:
        potager = svc_potagers.creer_potager(
            db, user.id, req.nom.strip(), req.ville, req.latitude, req.longitude, activer=req.activer,
        )
        utilisateur = db.query(User).filter(User.id == user.id).first()
        return {
            "id": potager.id,
            "nom": potager.nom,
            "ville": potager.ville,
            "etat": potager.etat,  # [US-080] toujours 'actif' à la création
            # Bascule réellement effectuée : `activer=false` reste sans effet
            # pour un utilisateur qui n'avait encore aucun potager actif.
            "actif": utilisateur.potager_actif_id == potager.id,
        }
    finally:
        db.close()


class CreerParcelleRequest(BaseModel):
    nom: str
    exposition: Optional[str] = None
    superficie_m2: Optional[float] = None
    est_pepiniere: bool = False
    type_sol: Optional[str] = None


@app.post("/parcelles", status_code=201)
def creer_parcelle(req: CreerParcelleRequest, ctx: TenantContext = Depends(get_current_user_ctx)):
    """[US-058 / CA3, CA5] Première porte d'entrée HTTP pour créer une parcelle —
    jusqu'ici réservée au bot Telegram (`utils/parcelles.create_parcelle`, commande
    `/parcelle ajouter`). Utilisée par l'assistant de création du premier potager
    juste après POST /potagers (le potager créé est déjà le potager actif à ce
    moment, cf. `svc_potagers.creer_potager`)."""
    if not req.nom or not req.nom.strip():
        raise HTTPException(status_code=400, detail="Nom de parcelle requis")
    db = SessionLocal()
    try:
        try:
            parcelle = svc_parcelles.creer_parcelle(
                db, ctx, req.nom.strip(),
                exposition=req.exposition, superficie_m2=req.superficie_m2,
                est_pepiniere=req.est_pepiniere, type_sol=req.type_sol,
            )
        except PermissionInsuffisanteError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
        return {
            "id": parcelle.id, "nom": parcelle.nom, "exposition": parcelle.exposition,
            "superficie_m2": parcelle.superficie_m2, "est_pepiniere": parcelle.est_pepiniere,
            "type_sol": parcelle.type_sol,
        }
    finally:
        db.close()


@app.patch("/potagers/{potager_id}")
def modifier_potager(potager_id: int, req: ModifierPotagerRequest, user: User = Depends(get_current_user)):
    """[US-074 / CA4] Un owner corrige nom/ville/latitude/longitude d'un potager
    déjà créé — seul moyen de localiser un potager existant qui n'a jamais eu
    de localisation. Vise le potager de l'URL, pas nécessairement le potager
    actif de l'appelant (même principe que POST /potagers/{id}/invitations)."""
    if req.nom is not None and not req.nom.strip():
        raise HTTPException(status_code=400, detail="Nom de potager requis")
    db = SessionLocal()
    try:
        try:
            potager = svc_potagers.modifier_potager(
                db, user.id, potager_id,
                nom=req.nom.strip() if req.nom is not None else None,
                ville=req.ville, latitude=req.latitude, longitude=req.longitude,
            )
        except PermissionInsuffisanteError as e:
            raise HTTPException(status_code=403, detail=str(e))
        return {
            "id": potager.id, "nom": potager.nom, "ville": potager.ville,
            "latitude": potager.latitude, "longitude": potager.longitude,
        }
    finally:
        db.close()


@app.post("/potagers/{potager_id}/invitations", status_code=201)
def creer_invitation(potager_id: int, req: InviterMembreRequest, user: User = Depends(get_current_user)):
    """[US-048 / CA3] Un owner invite un membre par code, avec un rôle proposé
    (editor|lecteur). Vise le potager de l'URL, pas nécessairement le potager
    actif de l'appelant."""
    db = SessionLocal()
    try:
        try:
            invitation = svc_potagers.creer_invitation(
                db, user.id, potager_id, req.role_propose, req.email_invite,
            )
        except PermissionInsuffisanteError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except svc_potagers.RoleInvalideError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {
            "code": invitation.code,
            "role_propose": invitation.role_propose,
            "expire_le": invitation.expire_le.isoformat() + "Z",
        }
    finally:
        db.close()


@app.post("/invitations/{code}/accepter")
def accepter_invitation(code: str, user: User = Depends(get_current_user)):
    """[US-048 / CA4, CA8] Accepte une invitation — insère le membre dans
    potager_membres avec le rôle proposé. Identité seule (l'utilisateur peut
    n'avoir encore aucun potager, CA7)."""
    db = SessionLocal()
    try:
        try:
            membre = svc_potagers.accepter_invitation(db, user.id, code)
        except svc_potagers.InvitationInvalideError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except svc_potagers.InvitationExpireeError as e:
            raise HTTPException(status_code=410, detail=str(e))
        except svc_potagers.InvitationDejaUtiliseeError as e:
            raise HTTPException(status_code=409, detail=str(e))
        except svc_potagers.DejaMembreError as e:
            raise HTTPException(status_code=409, detail=str(e))
        return {"potager_id": membre.potager_id, "role": membre.role}
    finally:
        db.close()


@app.get("/potagers/{potager_id}/membres")
def lister_membres_potager(potager_id: int, user: User = Depends(get_current_user)):
    """[US-048] Liste les membres d'un potager — réservé à ses membres."""
    db = SessionLocal()
    try:
        role = svc_potager_actif.role_utilisateur(db, user.id, potager_id)
        if role is None:
            raise HTTPException(status_code=403, detail="Vous n'êtes pas membre de ce potager")
        return {"membres": svc_potagers.lister_membres(db, potager_id)}
    finally:
        db.close()


@app.delete("/potagers/{potager_id}/membres/{membre_user_id}")
def retirer_membre_potager(potager_id: int, membre_user_id: int, user: User = Depends(get_current_user)):
    """[US-048 / CA5, CA6] Un owner retire un membre — celui-ci perd l'accès
    immédiatement (potager actif invalidé s'il pointait vers ce potager)."""
    db = SessionLocal()
    try:
        try:
            svc_potagers.retirer_membre(db, user.id, potager_id, membre_user_id)
        except PermissionInsuffisanteError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except svc_potagers.MembreInconnuError as e:
            raise HTTPException(status_code=404, detail=str(e))
        return {"success": True}
    finally:
        db.close()


def _potager_lifecycle_response(potager: Potager) -> dict:
    """[US-083, US-084] Forme unique des réponses de cycle de vie — un seul
    contrat pour archiver/désarchiver/supprimer/restaurer, chaque champ à
    `None` quand l'état courant ne le concerne pas."""
    purge_prevue_le = svc_potagers.date_purge_prevue(potager)
    return {
        "id": potager.id,
        "etat": potager.etat,
        "archive_le": potager.archive_le.isoformat() + "Z" if potager.archive_le else None,
        # [US-084 / CA2, CA7] Date de suppression logique et date effective de purge.
        "supprime_le": potager.supprime_le.isoformat() + "Z" if potager.supprime_le else None,
        "purge_prevue_le": purge_prevue_le.isoformat() + "Z" if purge_prevue_le else None,
    }


@app.post("/potagers/{potager_id}/archiver")
def archiver_potager(potager_id: int, user: User = Depends(get_current_user)):
    """[US-083 / CA1, CA2, CA5, CA9] Archive un potager — owner uniquement.
    Passe en lecture seule (CA4) ; invalide le potager actif des membres qui
    pointaient dessus (CA5) ; notifie les autres membres liés à Telegram (CA9)."""
    db = SessionLocal()
    try:
        try:
            potager = svc_potagers.archiver_potager(db, user.id, potager_id)
        except PermissionInsuffisanteError as e:
            raise HTTPException(status_code=403, detail=str(e))
        return _potager_lifecycle_response(potager)
    finally:
        db.close()


@app.post("/potagers/{potager_id}/desarchiver")
def desarchiver_potager(potager_id: int, user: User = Depends(get_current_user)):
    """[US-083 / CA2, CA8, CA9] Désarchive un potager — owner uniquement.
    Rend l'écriture immédiatement possible, sans rebasculer le potager actif
    de qui que ce soit (CA8) ; notifie les autres membres liés à Telegram (CA9)."""
    db = SessionLocal()
    try:
        try:
            potager = svc_potagers.desarchiver_potager(db, user.id, potager_id)
        except PermissionInsuffisanteError as e:
            raise HTTPException(status_code=403, detail=str(e))
        return _potager_lifecycle_response(potager)
    finally:
        db.close()

class SupprimerPotagerRequest(BaseModel):
    # [US-084 / CA4] Re-saisie du mot de passe du compte web (US-044) — la
    # confirmation ne peut pas être un simple clic sur une action irréversible.
    mot_de_passe: str


@app.get("/potagers/{potager_id}/impact-suppression")
def impact_suppression_potager(potager_id: int, user: User = Depends(get_current_user)):
    """[US-084 / CA3, CA10] Décompte réel de ce que la suppression fera perdre —
    alimente l'écran de confirmation, owner uniquement (un editor/lecteur n'a
    même pas à connaître ce décompte, l'action lui étant interdite)."""
    db = SessionLocal()
    try:
        try:
            return svc_potagers.compter_impact_suppression(db, user.id, potager_id)
        except PermissionInsuffisanteError as e:
            raise HTTPException(status_code=403, detail=str(e))
    finally:
        db.close()


@app.delete("/potagers/{potager_id}")
def supprimer_potager(
    potager_id: int, req: SupprimerPotagerRequest, user: User = Depends(get_current_user)
):
    """[US-084 / CA1, CA2, CA4, CA5, CA10] Supprime un potager ARCHIVÉ — owner
    uniquement. Suppression logique : le potager disparaît immédiatement pour
    tous les membres (CA5), ses données ne sont effacées qu'au terme du délai
    de grâce (CA7), pendant lequel il reste restaurable (CA6).

    409 (et non 403) sur un potager non archivé : les droits sont là, c'est
    l'état qui bloque — même convention que POST /potagers/{id}/activer face à
    un potager archivé (US-080 / CA6)."""
    db = SessionLocal()
    try:
        try:
            potager = svc_potagers.supprimer_potager(db, user.id, potager_id, req.mot_de_passe)
        except PermissionInsuffisanteError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except svc_potagers.PotagerNonArchiveError as e:
            raise HTTPException(status_code=409, detail=str(e))
        except svc_potagers.MotDePasseInvalideError as e:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "mot_de_passe_invalide",
                    "message": str(e),
                    "tentatives_restantes": e.tentatives_restantes,
                },
            )
        except svc_potagers.TropDEchecsMotDePasseError as e:
            # [CA4] L'opération est abandonnée, pas seulement refusée : le
            # frontend referme la confirmation au lieu de proposer un 4e essai.
            raise HTTPException(
                status_code=403,
                detail={"code": "trop_d_echecs", "message": str(e)},
            )
        return _potager_lifecycle_response(potager)
    finally:
        db.close()


@app.post("/potagers/{potager_id}/restaurer")
def restaurer_potager(potager_id: int, user: User = Depends(get_current_user)):
    """[US-084 / CA6] Droit au remords — restaure un potager supprimé encore
    dans son délai de grâce. Il revient à l'état `archive`, jamais `actif`."""
    db = SessionLocal()
    try:
        try:
            potager = svc_potagers.restaurer_potager(db, user.id, potager_id)
        except PermissionInsuffisanteError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except svc_potagers.PotagerNonSupprimeError as e:
            raise HTTPException(status_code=409, detail=str(e))
        return _potager_lifecycle_response(potager)
    finally:
        db.close()


# ── Sessions conversationnelles (in-memory, multi-tours) ──────────────────────
# { session_id: [{"role": "user"|"assistant", "content": str}, ...] }
_sessions: dict[str, list[dict]] = {}
_SESSION_MAX_TURNS = 5  # garder les 5 derniers échanges

# ── Mapping MIME type → extension fichier audio ────────────────────────────────
_MIME_EXT: dict[str, str] = {
    "audio/mp4"  : ".mp4",
    "audio/m4a"  : ".m4a",
    "audio/webm" : ".webm",
    "audio/ogg"  : ".ogg",
    "audio/wav"  : ".wav",
    "audio/mpeg" : ".mp3",
    "audio/aac"  : ".aac",
}

# ── Frontend React (prioritaire) ou PWA fallback ──────────────────────────────
_DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "dist")
_STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

if os.path.isdir(_DIST):
    # Dashboard React buildé — servi en priorité
    _DIST_ASSETS = os.path.join(_DIST, "assets")
    if os.path.isdir(_DIST_ASSETS):
        app.mount("/assets", StaticFiles(directory=_DIST_ASSETS), name="assets")

    @app.get("/", include_in_schema=False)
    def serve_frontend():
        """Sert le dashboard React (frontend/dist/index.html)."""
        return FileResponse(os.path.join(_DIST, "index.html"))

elif os.path.isdir(_STATIC):
    # Fallback : ancienne PWA si le dist React n'est pas buildé
    app.mount("/static", StaticFiles(directory=_STATIC), name="static")

    @app.get("/", include_in_schema=False)
    def serve_pwa():
        return FileResponse(os.path.join(_STATIC, "index.html"))


# ── Modèle de requête ──────────────────────────────────────────────────────────
class TexteRequest(BaseModel):
    texte: str


class RetourRequest(BaseModel):
    avis: str  # 'positif' | 'negatif'


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/health")
def health():
    """Vérification que le serveur est opérationnel."""
    db = SessionLocal()
    nb = svc_evenements.compter_evenements(db, default_context())
    db.close()
    return {
        "status"          : "ok",
        "version"         : _APP_VERSION,
        "moteur_llm"      : "Groq (gratuit)",
        "date"            : str(date.today()),
        "evenements_total": nb
    }


@app.get("/cultures")
def get_cultures(ctx: TenantContext = Depends(get_current_user_ctx)):
    """
    Retourne la liste des cultures configurées avec leur type d'organe récolté.
    Utile pour l'interface PWA et la validation des saisies.
    """
    db = SessionLocal()
    try:
        cultures = svc_parcelles.lister_cultures_config(db, ctx)
        result = [
            {
                "nom": c.nom,
                "type_organe_recolte": c.type_organe_recolte,
                "description_agronomique": c.description_agronomique
            }
            for c in cultures
        ]
        return {"cultures": result, "total": len(result)}
    finally:
        db.close()


@app.post("/parse")
def parse(req: TexteRequest, ctx: TenantContext = Depends(get_current_user_ctx)):
    """
    Reçoit une phrase dictée → parse via Groq → sauvegarde en base.
    Gère les phrases multiples (ex: tomates ET courgettes → 2 événements).
    La date réelle (hier, lundi...) est stockée correctement.
    """
    if not req.texte or len(req.texte.strip()) < 3:
        raise HTTPException(status_code=400, detail="Texte trop court")

    # [US-047 CA1, CA4] Garde de rôle AVANT tout appel de parsing LLM.
    try:
        require_role(ctx, "editor", "enregistrer d'action")
    except PermissionInsuffisanteError as e:
        raise HTTPException(status_code=403, detail=str(e))

    # ── 1. Parsing LLM → liste d'événements ──────────────────────────────────
    try:
        items = parse_commande(req.texte, ctx=ctx)   # toujours une liste
    except LLMIndisponibleError:
        # [US-092 / CA8, CA9] Repli déclaré : rien n'est enregistré, et le client
        # reçoit le message d'indisponibilité, jamais la trace technique du 429.
        raise HTTPException(status_code=503, detail=MESSAGE_REPLI_IA)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=502, detail=f"JSON invalide retourné par le modèle : {e}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erreur d'appel au modèle : {e}")

    # ── 2. Sauvegarde PostgreSQL ──────────────────────────────────────────────
    db = SessionLocal()
    saved = []
    try:
        for parsed in items:
            event = svc_evenements.creer_evenement_depuis_parse(db, ctx, parsed, req.texte)
            add_to_rag(event.id, parsed)
            saved.append({"event_id": event.id, "parsed": parsed})

        return {
            "success"        : True,
            "nb_evenements"  : len(saved),
            "evenements"     : saved,
            "event_id"       : saved[0]["event_id"] if saved else None,
            "parsed"         : saved[0]["parsed"]   if saved else None,
            "texte_original" : req.texte,
        }
    except svc_evenements.EvenementInvalideError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionInsuffisanteError as e:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(e))
    except PotagerArchiveError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur base de données : {e}")
    finally:
        db.close()


@app.post("/voice")
async def voice(
    audio: UploadFile = File(...),
    session_id: str   = Form(default=""),
    ctx: TenantContext = Depends(get_current_user_ctx),
):
    """
    [PWA iPhone] Reçoit un blob audio MediaRecorder →
      1. Groq Whisper → texte transcrit
      2. classify_intent_pwa() → ACTION | INTERROGER
      3. parse_commande() ou repondre_question()
      4. Retourne { reponse, intent, texte, recap, session_id }
    """
    # 1. Écrire le blob audio dans un fichier temporaire
    ct  = (audio.content_type or "audio/webm").split(";")[0].strip()
    ext = _MIME_EXT.get(ct, ".webm")

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp_path = tmp.name
        tmp.write(await audio.read())

    # 2. Transcription Whisper
    try:
        texte = transcribe_audio(tmp_path, ext, ctx=ctx)
    except LLMIndisponibleError:
        # [US-092 / CA4, CA9] Le quota de transcription est distinct de celui du
        # chat : c'est celui qui saturera le premier en usage vocal.
        raise HTTPException(status_code=503, detail=MESSAGE_REPLI_IA)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erreur Whisper : {e}")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    if not texte:
        return {
            "reponse"    : "Je n'ai pas compris. Parlez plus distinctement et réessayez.",
            "intent"     : "ERREUR",
            "texte"      : "",
            "recap"      : None,
            "session_id" : session_id or str(uuid.uuid4()),
        }

    # 3. Session
    if not session_id:
        session_id = str(uuid.uuid4())
    history = _sessions.get(session_id, [])

    # 4. Classification de l'intention
    try:
        intent = classify_intent_pwa(texte, ctx=ctx)
    except LLMIndisponibleError:
        raise HTTPException(status_code=503, detail=MESSAGE_REPLI_IA)

    # 5a. INTERROGER — question analytique sur l'historique
    if intent == "INTERROGER":
        try:
            reponse = svc_questions.repondre_question(ctx, texte)
        except LLMIndisponibleError:
            raise HTTPException(status_code=503, detail=MESSAGE_REPLI_IA)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Erreur agent SQL : {e}")

        result = {
            "reponse"    : reponse,
            "intent"     : "INTERROGER",
            "texte"      : texte,
            "recap"      : None,
            "session_id" : session_id,
        }

    # 5b. ACTION — enregistrement d'un événement potager
    else:
        # [US-047 CA1, CA4] Garde de rôle AVANT tout appel de parsing LLM.
        try:
            require_role(ctx, "editor", "enregistrer d'action")
        except PermissionInsuffisanteError as e:
            raise HTTPException(status_code=403, detail=str(e))

        try:
            items = parse_commande(texte, ctx=ctx)
        except LLMIndisponibleError:
            raise HTTPException(status_code=503, detail=MESSAGE_REPLI_IA)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=502, detail=f"JSON invalide retourné par le modèle : {e}")
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Erreur parsing : {e}")

        db = SessionLocal()
        saved_parsed: list[dict] = []
        try:
            for parsed in items:
                event = svc_evenements.creer_evenement_depuis_parse(db, ctx, parsed, texte)
                add_to_rag(event.id, parsed)
                saved_parsed.append(parsed)
        except svc_evenements.EvenementInvalideError as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(e))
        except PermissionInsuffisanteError as e:
            db.rollback()
            raise HTTPException(status_code=403, detail=str(e))
        except PotagerArchiveError as e:
            db.rollback()
            raise HTTPException(status_code=409, detail=str(e))
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Erreur base : {e}")
        finally:
            db.close()

        recap = saved_parsed[0] if saved_parsed else None

        # Réponse vocale synthétique
        if recap:
            parts = [
                recap.get("action"),
                (recap.get("culture") or "") + (f" {recap['variete']}" if recap.get("variete") else ""),
                f"{recap['quantite']} {recap.get('unite', '')}".strip() if recap.get("quantite") is not None else None,
                f"parcelle {recap['parcelle']}" if recap.get("parcelle") else None,
            ]
            resume = ", ".join(p for p in parts if p)
            reponse = f"C'est noté ! J'ai enregistré : {resume}."
            if len(saved_parsed) > 1:
                reponse = f"C'est noté ! J'ai enregistré {len(saved_parsed)} actions."
        else:
            reponse = "Action enregistrée."

        result = {
            "reponse"       : reponse,
            "intent"        : "ACTION",
            "texte"         : texte,
            "recap"         : recap,
            "session_id"    : session_id,
            "nb_evenements" : len(saved_parsed),
        }

    # 6. Mettre à jour la session (historique multi-tours)
    history.append({"role": "user",      "content": texte})
    history.append({"role": "assistant", "content": result["reponse"]})
    _sessions[session_id] = history[-(  _SESSION_MAX_TURNS * 2):]

    return result


@app.post("/ask")
def ask(req: TexteRequest, ctx: TenantContext = Depends(get_current_user_ctx)):
    """
    Répond en langage naturel à une question sur l'historique du potager.
    Exemples : 'Combien de kg de tomates ?', 'Historique traitements courgettes'
    """
    try:
        reponse = svc_questions.repondre_question(ctx, req.texte)
    except LLMIndisponibleError:
        # [US-092 / CA9, CA10] /stats, /plan, la météo et la consultation web
        # restent fonctionnels : seule l'analyse en langage naturel est dégradée.
        raise HTTPException(status_code=503, detail=MESSAGE_REPLI_IA)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erreur agent SQL : {e}")

    return {"reponse": reponse}


@app.post("/routage/{routage_log_id}/retour")
def deposer_retour_routage(
    routage_log_id: int,
    req: RetourRequest,
    ctx: TenantContext = Depends(get_current_user_ctx),
):
    """[US-097 / CA9-CA11] Dépose un avis 👍/👎 sur une réponse de savoir ou de
    raisonnement, rattaché à son entrée de journal. Facultatif, ne bloque
    rien : un doublon (avis déjà donné) renvoie 409, pas une erreur bloquante
    pour l'appelant. Point d'accroche pour un futur contrôle web (CA9) — aucune
    vue Q&A n'existe encore côté PWA pour l'exposer directement."""
    db = SessionLocal()
    try:
        try:
            svc_retours.enregistrer_retour(db, ctx.potager_id, routage_log_id, req.avis)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except svc_retours.RoutageLogIntrouvableError:
            raise HTTPException(status_code=404, detail="Réponse introuvable pour ce potager")
        except svc_retours.RetourDejaEnregistreError:
            raise HTTPException(status_code=409, detail="Un avis a déjà été enregistré pour cette réponse")
    finally:
        db.close()
    return {"ok": True}


@app.get("/admin/routage/metriques")
def admin_routage_metriques(_admin: User = Depends(require_admin_user)):
    """[US-097 / CA5-CA8] Métriques de routage — lecture seule, réservée à
    l'administrateur de la plateforme. Aucun calcul ici n'appelle un modèle
    (CA8) ; aucun tableau de bord graphique n'est construit (CA7)."""
    db = SessionLocal()
    try:
        return {
            "par_etage": svc_metriques_routage.resume_par_etage(db),
            "jetons_moyens_par_question": svc_metriques_routage.jetons_moyens_par_question(db),
            "taux_remontee_cascade": svc_metriques_routage.taux_remontee_cascade(db),
            # [US-096 / CA6] Indicateur principal des gabarits sur agrégats SQL.
            "taux_donnees_sans_modele": svc_metriques_routage.taux_donnees_sans_modele(db),
            "taux_service_cache": svc_metriques_routage.taux_service_cache(db),
            # [US-095 / CA12] Cache de RÉPONSES (étage 0bis) — à ne pas
            # confondre avec `taux_service_cache` ci-dessus, qui mesure le
            # cache en mémoire des classifications. Publié avec son écart à
            # l'hypothèse de 40 %, jamais renormalisé.
            "taux_service_cache_reponses": svc_metriques_routage.taux_service_cache_reponses(db),
            "part_parseur_deterministe": svc_metriques_routage.part_parseur_deterministe(db),
            "comparaison_hypotheses": svc_metriques_routage.comparaison_hypotheses(db),
        }
    finally:
        db.close()


@app.get("/admin/routage/retours-negatifs")
def admin_routage_retours_negatifs(
    limite: int = Query(default=20, ge=1, le=200),
    _admin: User = Depends(require_admin_user),
):
    """[US-097 / CA12] Questions les plus souvent jugées mauvaises — alimente
    le corpus de routage (US-093/CA9) et la liste des lacunes de la base de
    connaissance."""
    db = SessionLocal()
    try:
        return {"questions": svc_metriques_routage.top_questions_mal_notees(db, limite=limite)}
    finally:
        db.close()


@app.get("/stats")
def stats(
    date_ref: date = Query(default=None),
    potager_id: int = Query(default=None),
    ctx: TenantContext = Depends(get_current_user_ctx)
):
    """[US-002/CA4] Statistiques JSON avec stock agronomique différencié.
    [US-030] date_ref optionnel (YYYY-MM-DD) : reconstitue l'état à une date passée.
    [US-083 / CA7] potager_id optionnel : consulte un potager archivé (non-actif)."""
    db = SessionLocal()
    try:
        use_ctx = ctx_pour_potager_consulte(db, ctx, potager_id)

        result = svc_stats.calculer_stats(db, use_ctx, date_ref)
        date_ref_effective = result.date_ref_effective
        total = result.total_evenements
        stocks = result.stocks
        godets = result.godets
        traitements = result.traitements
        cultures_avec_godet = result.cultures_avec_godet

        # [US-026 / semis pleine terre] Semis directement associés à une parcelle
        semis_data = result.semis
        cultures_semis_pt = {c.lower() for c, s in semis_data.items() if s.get("parcelles_pleine_terre")}
        semis_pleine_terre = [
            {
                "culture":    c,
                "total_seme": int(s["total_seme"]),
                "unite":      s["unite"],
                "type_organe": s["type_organe"],
                "parcelles":  s["parcelles_pleine_terre"],
            }
            for c, s in semis_data.items()
            if s.get("parcelles_pleine_terre")
        ]

        # [US-039 / CA2, CA6] Indicateur d'observations agrégées par culture (Stocks)
        obs_index = build_observations_index(db)

        stock_enrichi = _stock_mod.format_stock_stats_json(stocks)
        for entry in stock_enrichi:
            nom = (entry.get("culture") or "").lower()
            if nom in cultures_avec_godet:
                entry["origine"] = "pépinière"
            elif nom in cultures_semis_pt:
                entry["origine"] = "semis_pleine_terre"
            else:
                entry["origine"] = "pied_acheté"
            nb_obs = len(obs_index["stocks"].get(nom, []))
            entry["has_observations"] = nb_obs > 0
            entry["nb_observations"]  = nb_obs

        return {
            "date_ref_effective" : date_ref_effective.isoformat(),
            "total_evenements"   : total,
            "stock_par_culture"  : stock_enrichi,
            "godets"             : [
                {
                    "culture":           v["culture"],
                    "variete":           v["variete"],
                    "nb_plants_godets":  v["nb_plants_godets"],
                    "nb_graines_semees": v["nb_graines_semees"],
                    "nb_vendus":         v.get("nb_vendus", 0),
                    "nb_pertes_godet":   v.get("nb_pertes_godet", 0),
                    "stock_residuel_godet": v["stock_residuel_godet"],
                    "taux_reussite":     v["taux_reussite"],
                }
                for v in godets.values()
            ],
            "semis_pleine_terre" : semis_pleine_terre,
            "traitements"        : [{"produit": t or "?", "nb_applications": n} for t, n in traitements],
        }
    finally:
        db.close()


@app.get("/stats/varietes")
def get_stats_varietes(
    date_ref: date = Query(default=None),
    potager_id: int = Query(default=None),
    ctx: TenantContext = Depends(get_current_user_ctx),
):
    """[US-072] Détail par variété, toutes cultures et tous états confondus (potager /
    semis / pépinière), avec leurs parcelles d'origine réelles — alimente l'écran Stocks
    transverse (US-073). Nouvelle agrégation en lecture seule : ne modifie ni /stats ni
    /godets (CA8), aucune migration BDD (CA9).
    [US-030] date_ref optionnel (YYYY-MM-DD) : reconstitue l'état à une date passée.
    [US-083 / CA7] potager_id optionnel : consulte un potager archivé (non-actif)."""
    today = date.today()
    dr = min(date_ref, today) if date_ref else None
    date_ref_effective = dr or today
    db = SessionLocal()
    try:
        use_ctx = ctx_pour_potager_consulte(db, ctx, potager_id)
        varietes = svc_stock.calcul_stock_varietes(db, use_ctx, date_ref=dr)
        # [US-073 CA15] Observations agrégées par culture, même index que /stats —
        # pas de granularité variété côté observations (US-039), le badge remonte
        # donc sur chaque ligne d'une même culture.
        obs_index = build_observations_index(db)
        # [US-067 / CA5, CA6] Famille botanique par culture, relue à chaque appel
        # (pas de copie mémorisée) — None si non renseignée, l'écran Stocks
        # applique son propre repli "Autres" (CA3), comme avant cette US.
        familles = svc_familles.familles_par_culture(db, use_ctx)
        for entry in varietes:
            nom = (entry.get("culture") or "").lower()
            nb_obs = len(obs_index["stocks"].get(nom, []))
            entry["has_observations"] = nb_obs > 0
            entry["nb_observations"]  = nb_obs
            entry["famille"] = familles.get(normaliser_culture(entry.get("culture") or ""), None)
        return {
            "varietes":           varietes,
            "total":              len(varietes),
            "date_ref_effective": date_ref_effective.isoformat(),
        }
    finally:
        db.close()


@app.get("/stats/rendement")
def get_rendement(
    annee: int = Query(default=None),
    date_ref: date = Query(default=None),
    potager_id: int = Query(default=None),
    ctx: TenantContext = Depends(get_current_user_ctx),
):
    """[US_Stats_rendement_timeline] Timeline mensuelle des récoltes par culture.
    [US-030] date_ref optionnel (YYYY-MM-DD) : plafonne la borne haute à cette date.
    [US-083 / CA7] potager_id optionnel : consulte un potager archivé (non-actif)."""
    from utils.stock import calcul_rendement_mensuel
    today = date.today()
    annee_eff = annee or today.year
    dr = min(date_ref, today) if date_ref else None
    db = SessionLocal()
    try:
        use_ctx = ctx_pour_potager_consulte(db, ctx, potager_id)
        data = calcul_rendement_mensuel(db, annee_eff, dr, potager_id=use_ctx.potager_id)
        return {"annee": annee_eff, **data}
    finally:
        db.close()


@app.get("/stats/activite")
def get_activite(
    annee: int = Query(default=None),
    date_ref: date = Query(default=None),
    potager_id: int = Query(default=None),
    ctx: TenantContext = Depends(get_current_user_ctx),
):
    """[US_Stats_activite_potager] Heatmap d'activité quotidienne (nb événements/jour).
    [US-030] date_ref optionnel (YYYY-MM-DD) : plafonne la borne haute à cette date.
    [US-083 / CA7] potager_id optionnel : consulte un potager archivé (non-actif)."""
    from utils.stock import calcul_activite_quotidienne
    today = date.today()
    annee_eff = annee or today.year
    dr = min(date_ref, today) if date_ref else None
    db = SessionLocal()
    try:
        use_ctx = ctx_pour_potager_consulte(db, ctx, potager_id)
        jours = calcul_activite_quotidienne(db, annee_eff, dr, potager_id=use_ctx.potager_id)
        return {
            "annee":         annee_eff,
            "jours":         jours,
            "total_actions": sum(jours.values()),
            "jours_actifs":  len(jours),
        }
    finally:
        db.close()


@app.get("/plan")
def get_plan(
    date_ref: date = Query(default=None),
    potager_id: int = Query(default=None),
    ctx: TenantContext = Depends(get_current_user_ctx)
):
    """
    [US-024] Plan d'occupation des parcelles pour le dashboard frontend.
    [US-030] date_ref optionnel (YYYY-MM-DD) : reconstitue l'état à une date passée.
    [US-083 / CA7] potager_id optionnel : consulte un potager archivé (non-actif).

    Retourne la liste des parcelles actives avec leurs cultures en cours.
    Les parcelles sans culture sont incluses avec cultures=[].
    """
    today = date.today()
    dr = min(date_ref, today) if date_ref else None
    date_ref_effective = dr or today
    db = SessionLocal()
    try:
        use_ctx = ctx_pour_potager_consulte(db, ctx, potager_id)

        parcelles     = svc_plan.get_parcelles(db, use_ctx)
        occupation    = svc_plan.get_occupation(db, use_ctx, dr)

        # Index surface_m2 par nom de culture (insensible à la casse)
        surface_par_culture = svc_plan.surface_par_culture(db, use_ctx)

        # [US-067 / CA5, CA6, CA8] Famille botanique par culture — remplace la
        # table figée frontend/src/lib/familles.js (supprimée), relue à chaque
        # appel. None si non renseignée : Plan.jsx affiche "—", pas "Autres"
        # (une tuile de culture seule n'a pas besoin d'un groupe fourre-tout).
        familles_par_culture = svc_familles.familles_par_culture(db, use_ctx)

        # [US-039 / CA1, CA5] Indicateur d'observations par parcelle / ligne de culture
        obs_index = build_observations_index(db)

        result = []
        for p in parcelles:
            cultures_raw = occupation.get(p.nom, [])
            cultures = [
                {
                    "culture":    c.get("culture", ""),
                    "variete":    c.get("variete"),
                    # [US-037 / CA10] Une surface m² est fractionnable (ex: 1.5 m²) —
                    # ne jamais tronquer en int comme pour un nombre de plants/graines.
                    "nb_plants":  (c.get("nb_plants") or 0) if c.get("unite") == "m²" else int(c.get("nb_plants") or 0),
                    "unite":      c.get("unite") or "plants",
                    "type_organe": c.get("type_organe") or "végétatif",
                    "surface_m2_par_plant": surface_par_culture.get(
                        (c.get("culture") or "").lower(), None
                    ),
                    "famille": familles_par_culture.get(
                        normaliser_culture(c.get("culture") or ""), None
                    ),
                    "nb_observations": (
                        len(obs_index["culture_row"].get((p.id, c["culture"].lower(), c["variete"]), []))
                        if c.get("variete") and c.get("culture") else 0
                    ),
                }
                for c in cultures_raw
            ]
            for c in cultures:
                c["has_observations"] = c["nb_observations"] > 0

            # [US-037 / CA10] Calcul occupation réel : une culture semée en m² occupe
            # directement cette surface (aucune conversion via une empreinte au pied) ;
            # les autres unités (graines, pieds, plants) restent multipliées par
            # surface_m2_par_plant comme avant.
            occupation_pct = None
            if p.superficie_m2:
                surface_utilisee = sum(
                    c["nb_plants"] if c["unite"] == "m²"
                    else c["nb_plants"] * c["surface_m2_par_plant"]
                    for c in cultures
                    if c["unite"] == "m²" or c["surface_m2_par_plant"]
                )
                if surface_utilisee > 0:
                    occupation_pct = min(100, round(surface_utilisee / p.superficie_m2 * 100))

            nb_obs_parcelle = len(obs_index["parcelle"].get(p.id, []))
            result.append({
                "id":            p.id,
                "nom":           p.nom,
                "exposition":    p.exposition,
                "superficie_m2": p.superficie_m2,
                "cultures":      cultures,
                "occupation_pct": occupation_pct,
                "has_observations": nb_obs_parcelle > 0,
                "nb_observations":  nb_obs_parcelle,
            })

        return {"parcelles": result, "total": len(result), "date_ref_effective": date_ref_effective.isoformat()}
    finally:
        db.close()


@app.get("/observations")
def get_observations(
    parcelle_id: int = Query(default=None),
    culture: str = Query(default=None),
    variete: str = Query(default=None),
    ctx: TenantContext = Depends(get_current_user_ctx),
):
    """
    [US-039 / CA3] Détail des observations pour un point d'accès du dashboard :
      - parcelle_id + culture + variete → ligne de culture précise (Plan)
      - parcelle_id seul                → carte parcelle (Plan)
      - culture seule                   → agrégat culture (Stocks)
    """
    db = SessionLocal()
    try:
        index = build_observations_index(db)
        if parcelle_id is not None and culture and variete:
            items = index["culture_row"].get((parcelle_id, culture.lower(), variete), [])
        elif parcelle_id is not None:
            items = index["parcelle"].get(parcelle_id, [])
        elif culture:
            items = index["stocks"].get(culture.lower(), [])
        else:
            items = []
        return {"items": items}
    finally:
        db.close()


@app.get("/godets")
def get_godets(
    date_ref: date = Query(default=None),
    potager_id: int = Query(default=None),
    ctx: TenantContext = Depends(get_current_user_ctx),
):
    """
    [US-026] État de la pépinière : godets en attente de plantation + cultures tout plantées.
    [US-030] date_ref optionnel (YYYY-MM-DD) : reconstitue l'état à une date passée.
    [US-083 / CA7] potager_id optionnel : consulte un potager archivé (non-actif).

    Utilise calcul_godets() pour un stock agrégé par (culture, variété) avec déduction
    des plantations. Retourne deux listes :
    - en_attente  : cultures avec stock_residuel_godet > 0
    - tout_plante : cultures entièrement plantées (stock = 0), listées dans l'encart "Tout planté"
    """
    from utils.stock import calcul_godets
    today = date.today()
    dr = min(date_ref, today) if date_ref else None
    date_ref_effective = dr or today
    db = SessionLocal()
    try:
        use_ctx = ctx_pour_potager_consulte(db, ctx, potager_id)
        tous = calcul_godets(db, include_epuises=True, date_ref=dr, potager_id=use_ctx.potager_id)
        en_attente  = [v for v in tous.values() if v["stock_residuel_godet"] > 0 or v.get("graines_en_germination", 0) > 0]
        tout_plante = [v for v in tous.values() if v["stock_residuel_godet"] == 0 and not v.get("graines_en_germination")]
        return {
            "en_attente": en_attente,
            "tout_plante": tout_plante,
            "total": len(en_attente),
            "date_ref_effective": date_ref_effective.isoformat(),
        }
    finally:
        db.close()



@app.get("/pepiniere/lots")
def get_pepiniere_lots(
    date_ref: date = Query(default=None),
    potager_id: int = Query(default=None),
    ctx: TenantContext = Depends(get_current_user_ctx),
):
    """
    [US-065 / CA1, CA7] État de la pépinière LOT DE SEMIS PAR LOT DE SEMIS.

    Un lot = un événement de semis en pépinière, identifié par sa date ; les mises
    en godet sans semis rattaché forment un lot distinct (`sans_semis_rattache`).
    Chaque lot porte son propre avancement (`taux_germination`), son état de
    germination à trois valeurs (`etat_germination` : en_cours / close /
    indeterminee) et le signalement d'une éventuelle incohérence de saisie
    (`incoherence_saisie`).

    Cette lecture **s'ajoute** à `GET /godets` (agrégée par culture + variété), qui
    conserve exactement son contrat actuel — écrans Stocks, Statistiques et bot
    inchangés (CA5).

    [US-030] date_ref optionnel (YYYY-MM-DD) : reconstitue l'état à une date passée.
    [US-083 / CA7] potager_id optionnel : consulte un potager archivé (non-actif).
    """
    today = date.today()
    dr = min(date_ref, today) if date_ref else None
    date_ref_effective = dr or today
    db = SessionLocal()
    try:
        use_ctx = ctx_pour_potager_consulte(db, ctx, potager_id)
        lots = svc_stock.calcul_lots_pepiniere(db, use_ctx, date_ref=dr)
        # [US-067 / CA5, CA6, CA8] Famille botanique par culture — remplace la
        # table figée frontend/src/lib/familles.js (supprimée) qui alimentait le
        # regroupement de cet écran (US-061). Relue à chaque appel : une
        # correction de famille depuis le bot (CA4) se reflète au rechargement
        # suivant, sans copie mémorisée nulle part.
        familles = svc_familles.familles_par_culture(db, use_ctx)
        return {
            "lots": [
                {
                    **lot,
                    "date_semis": str(lot["date_semis"])[:10] if lot["date_semis"] else None,
                    "date_derniere_mise_en_godet": (
                        str(lot["date_derniere_mise_en_godet"])[:10]
                        if lot["date_derniere_mise_en_godet"] else None
                    ),
                    "famille": familles.get(normaliser_culture(lot.get("culture") or ""), None),
                }
                for lot in lots
            ],
            "total": len(lots),
            "date_ref_effective": date_ref_effective.isoformat(),
        }
    finally:
        db.close()


@app.get("/godets/detail")
def get_godet_detail(
    culture: str = Query(...),
    variete: str = Query(default=None),
    semis_id: int = Query(default=None, description="[US-065 CA6] Cible le lot issu de ce semis"),
    sans_semis_rattache: bool = Query(default=False, description="[US-065 CA6] Cible le lot des godets sans semis parent"),
    ctx: TenantContext = Depends(get_current_user_ctx),
):
    """
    [US-029] Cycle de vie complet semis → godets → plantations pour une (culture, variété).
    Utilisé par le panneau de détail de la pépinière frontend.

    [US-065 / CA6] `semis_id` (ou `sans_semis_rattache`) restreint le détail à un lot
    précis. Sans ces paramètres, le comportement historique agrégé est conservé.
    """
    db = SessionLocal()
    try:
        cycle = svc_evenements.cycle_vie_culture(
            db, ctx, culture, variete,
            semis_id=semis_id, sans_semis_rattache=sans_semis_rattache,
        )
        semis_events        = cycle["semis"]
        godet_events        = cycle["godets"]
        linked_plantations  = cycle["plantations"]
        vendu_events        = cycle["ventes"]
        perte_events        = cycle["pertes_godet"]
        taux                = cycle["taux_germination"]

        return {
            "culture": culture,
            "variete": variete,
            # [US-065 CA6] Rappel du lot ciblé, pour que le panneau de détail sache
            # ce qu'il affiche (lot précis vs agrégat culture + variété).
            "semis_id": semis_id,
            "sans_semis_rattache": sans_semis_rattache,
            "semis": [
                {
                    "id":        s.id,
                    "date":      str(s.date)[:10],
                    "nb_graines": int(s.quantite or 0),
                    "unite":     s.unite or "graines",
                    "parcelle":  s.parcelle_rel.nom if s.parcelle_rel else None,
                }
                for s in semis_events
            ],
            "godets": [
                {
                    "id":              g.id,
                    "date":            str(g.date)[:10],
                    "nb_plants":       int(g.nb_plants_godets or 0),
                    "nb_graines_lot":  int(g.nb_graines_semees) if g.nb_graines_semees else None,
                    "origine_semis_id": g.origine_graines_id,
                }
                for g in godet_events
            ],
            "plantations": [
                {
                    "id":              p.id,
                    "date":            str(p.date)[:10],
                    "quantite":        int(p.quantite or 0),
                    "parcelle":        p.parcelle_rel.nom if p.parcelle_rel else None,
                    "source_godet_ids": p.source_evenement_ids.split(";") if p.source_evenement_ids else [],
                }
                for p in linked_plantations
            ],
            "ventes": [
                {
                    "id":       v.id,
                    "date":     str(v.date)[:10],
                    "quantite": int(v.quantite or 0),
                }
                for v in vendu_events
            ],
            "pertes_godet": [
                {
                    "id":       p.id,
                    "date":     str(p.date)[:10],
                    "quantite": int(p.quantite or 0),
                }
                for p in perte_events
            ],
            "taux_germination": taux,
        }
    finally:
        db.close()


@app.get("/meteo")
def meteo_potager(ctx: TenantContext = Depends(get_current_user_ctx)):
    """
    [US-075 / CA3, CA4] Météo du jour + prévision 5 jours, calculées sur la
    localisation réelle du potager actif (`Potager.ville`/`latitude`/`longitude`,
    US-074) — pas les coordonnées globales du bot Telegram.

    Si le potager actif n'a pas encore de localisation renseignée, retourne
    `localisation_manquante: true` plutôt qu'un repli silencieux sur une météo
    qui ne correspondrait à aucun lieu réel du potager (CA4).
    """
    from utils.meteo import fetch_meteo, METEO_TIMEZONE

    db = SessionLocal()
    try:
        potager = db.query(Potager).filter(Potager.id == ctx.potager_id).first()
        if potager is None or potager.latitude is None or potager.longitude is None:
            return {"localisation_manquante": True}

        meteo = fetch_meteo(lat=potager.latitude, lon=potager.longitude, timezone=METEO_TIMEZONE)
        if meteo is None:
            raise HTTPException(status_code=502, detail="Impossible de récupérer les données Open-Meteo")

        return {
            "localisation_manquante": False,
            "ville": potager.ville,
            **meteo,
        }
    finally:
        db.close()


@app.get("/meteo/history")
def meteo_history(
    days    : int   = Query(default=30, ge=7, le=365, description="Nombre de jours d'historique"),
    lat     : float = Query(default=None, description="Latitude GPS (défaut : potager configuré)"),
    lon     : float = Query(default=None, description="Longitude GPS (défaut : potager configuré)"),
    timezone: str   = Query(default=None, description="Fuseau IANA (défaut : Europe/Paris)"),
    ctx: TenantContext = Depends(get_current_user_ctx),
):
    """
    Historique météo journalier (températures min/max + précipitations) depuis Open-Meteo Archive.
    Gratuit, sans authentification, zéro token Groq.

    Paramètres optionnels lat/lon permettent d'interroger n'importe quel potager.
    Retourne : { jours: [...], meta: { lat, lon, timezone, days, start_date, end_date } }
    """
    from utils.meteo import fetch_meteo_history, METEO_LATITUDE, METEO_LONGITUDE, METEO_TIMEZONE

    eff_lat = lat      if lat      is not None else METEO_LATITUDE
    eff_lon = lon      if lon      is not None else METEO_LONGITUDE
    eff_tz  = timezone if timezone is not None else METEO_TIMEZONE

    jours = fetch_meteo_history(lat=eff_lat, lon=eff_lon, days=days, timezone=eff_tz)

    if jours is None:
        raise HTTPException(status_code=502, detail="Impossible de récupérer les données Open-Meteo Archive")

    return {
        "jours": jours,
        "meta": {
            "lat"       : eff_lat,
            "lon"       : eff_lon,
            "timezone"  : eff_tz,
            "days"      : days,
            "start_date": jours[0]["date"]  if jours else None,
            "end_date"  : jours[-1]["date"] if jours else None,
        },
    }


@app.get("/historique")
def historique(
    limit     : int  = Query(default=20, le=100),
    offset    : int  = Query(default=0, ge=0),
    action    : str  = Query(default=None),
    culture   : str  = Query(default=None),
    parcelle  : str  = Query(default=None),
    from_date : str  = Query(default=None, alias="from"),
    to_date   : str  = Query(default=None, alias="to"),
    date_ref  : date = Query(default=None),
    potager_id: int = Query(default=None),
    ctx: TenantContext = Depends(get_current_user_ctx),
):
    """
    [US-027] Retourne les événements paginés avec filtres optionnels.
    [US-030] date_ref optionnel (YYYY-MM-DD) : borne haute, prioritaire sur to_date.
    [US-083 / CA7] potager_id optionnel : consulte un potager archivé (non-actif).
    Ex: /historique?culture=tomate&action=recolte&from=2026-05-01&to=2026-05-31&offset=20
    Retourne : { total: int, evenements: [...], date_ref_effective: str }
    """
    today = date.today()
    dr = min(date_ref, today) if date_ref else None
    date_ref_effective = dr or today
    # date_ref prend priorité sur to_date
    effective_to = dr.isoformat() if dr else to_date
    db = SessionLocal()
    try:
        use_ctx = ctx_pour_potager_consulte(db, ctx, potager_id)

        total, events = svc_evenements.lister_evenements(
            db, use_ctx,
            limit=limit, offset=offset, action=action, culture=culture,
            parcelle=parcelle, from_date=from_date, to_date=effective_to,
        )
        return {
            "total": total,
            "date_ref_effective": date_ref_effective.isoformat(),
            "evenements": [
                {
                    "id"         : e.id,
                    "date"       : str(e.date)[:10] if e.date else None,
                    "type_action": e.type_action,
                    "culture"    : e.culture,
                    "variete"    : e.variete,
                    "quantite"   : e.quantite,
                    "unite"      : e.unite,
                    # [US-063] Une mise en godet ne renseigne pas `quantite` : son
                    # compte réel vit dans `nb_plants_godets`. Sans ce champ, le
                    # journal affichait ces événements sans aucune quantité.
                    "nb_plants_godets": e.nb_plants_godets,
                    "parcelle"   : e.parcelle,
                    "traitement" : e.traitement,
                }
                for e in events
            ],
        }
    finally:
        db.close()


# ── Repli SPA — sert index.html pour les routes front sans backend (US-044) ────
# Enregistrée en dernier : toute route API définie plus haut (health, auth/*,
# stats, historique...) est essayée en premier par Starlette (ordre
# d'enregistrement) ; seuls les chemins non reconnus (ex. /verifier-email,
# ouvert depuis le lien de vérification e-mail) retombent ici.
if os.path.isdir(_DIST):
    @app.get("/{chemin_complet:path}", include_in_schema=False)
    def serve_frontend_spa_fallback(chemin_complet: str):
        return FileResponse(os.path.join(_DIST, "index.html"))
elif os.path.isdir(_STATIC):
    @app.get("/{chemin_complet:path}", include_in_schema=False)
    def serve_pwa_spa_fallback(chemin_complet: str):
        return FileResponse(os.path.join(_STATIC, "index.html"))

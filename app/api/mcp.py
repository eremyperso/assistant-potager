"""
app/api/mcp.py — Routes du canal MCP [US-290]
=============================================

  GET  /.well-known/oauth-protected-resource[/mcp]   métadonnées de la ressource (RFC 9728)
  GET  /.well-known/oauth-authorization-server       métadonnées du serveur d'autorisation (RFC 8414)
  POST /oauth/register                               enregistrement dynamique d'un client (RFC 7591)
  GET  /oauth/authorize                              → page de consentement de la PWA (/connecteur-ia)
  GET  /oauth/demande                                (PWA) ce que la page de consentement affiche
  POST /oauth/consentement                           (PWA) la réponse du jardinier → URL de retour
  POST /oauth/token                                  code + PKCE, ou rafraîchissement (rotation)
  POST /oauth/revoke                                 révocation par le client (RFC 7009)
  POST /mcp                                          le serveur MCP (JSON-RPC, sans état)
  GET  /mcp/connexions                               (PWA) les connecteurs du jardinier
  DELETE /mcp/connexions/{id}                        (PWA) révoquer un connecteur (CA8)
  POST /mcp/jetons-personnels                        (PWA) créer un jeton personnel (CA9)

Les routes de la PWA exigent la session JWT du jardinier ; `/mcp` exige un jeton du
connecteur. Aucune logique ici : tout passe par `app/services/mcp/`.
"""
from __future__ import annotations

import base64
import binascii
import html
import json
import logging
from typing import Callable, Optional
import hashlib
from urllib.parse import unquote, urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.config import FRONTEND_URL
from app.services.mcp import autorisation as svc_autorisation
from app.services.mcp import connexions as svc_connexions
from app.services.mcp import serveur as svc_serveur
from database.db import SessionLocal
from database.models import User

log = logging.getLogger("potager")

#: Chemins appelés par des clients MCP tiers, parfois depuis un navigateur (MCP
#: Inspector) : ils reçoivent un CORS ouvert, sans cookie (jetons Bearer seulement).
PREFIXES_CORS_OUVERT = ("/.well-known/oauth-", "/oauth/register", "/oauth/token", "/oauth/revoke")
CHEMINS_CORS_OUVERT = ("/mcp",)
_ENTETES_CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization, Content-Type, Mcp-Session-Id, MCP-Protocol-Version, Last-Event-ID",
    "Access-Control-Expose-Headers": "WWW-Authenticate, Mcp-Session-Id, MCP-Protocol-Version",
    "Access-Control-Max-Age": "600",
}
_SANS_CACHE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


def chemin_cors_ouvert(chemin: str) -> bool:
    return chemin in CHEMINS_CORS_OUVERT or chemin.startswith(PREFIXES_CORS_OUVERT)


async def middleware_cors_mcp(request: Request, call_next):
    """CORS ouvert sur les seuls chemins du canal MCP ; le reste garde le CORS de la PWA."""
    if not chemin_cors_ouvert(request.url.path):
        return await call_next(request)
    if request.method == "OPTIONS":
        return Response(status_code=204, headers=_ENTETES_CORS)
    reponse = await call_next(request)
    for cle, valeur in _ENTETES_CORS.items():
        reponse.headers[cle] = valeur
    return reponse


def cle_debit_jeton(request: Request) -> str:
    """Filet anti-rafale de /mcp par JETON (jamais par IP : les assistants partagent les leurs)."""
    entete = request.headers.get("authorization", "")
    jeton = entete[7:].strip() if entete.lower().startswith("bearer ") else ""
    return "mcp:" + hashlib.sha256(jeton.encode("utf-8")).hexdigest()[:24]


def _url_metadonnees_ressource() -> str:
    return f"{svc_autorisation.emetteur()}/.well-known/oauth-protected-resource/mcp"


def _non_authentifie(description: Optional[str] = None) -> JSONResponse:
    """[CA1] Sans jeton valide : une invitation à s'authentifier, jamais de données."""
    entete = f'Bearer resource_metadata="{_url_metadonnees_ressource()}"'
    if description:
        # Un en-tête HTTP reste en ASCII : le libellé accentué ne va que dans le corps.
        entete += ', error="invalid_token", error_description="token expired, revoked or unknown"'
    return JSONResponse(
        status_code=401,
        content={"error": "invalid_token" if description else "unauthorized",
                 "error_description": description or "Connecte ce connecteur à ton compte Assistant Potager."},
        headers={"WWW-Authenticate": entete},
    )


def _erreur_oauth(erreur: svc_autorisation.ErreurOAuth) -> JSONResponse:
    entetes = dict(_SANS_CACHE)
    if erreur.statut == 401:
        entetes["WWW-Authenticate"] = "Basic"
    return JSONResponse(status_code=erreur.statut, content=erreur.corps(), headers=entetes)


def _page_erreur(message: str) -> HTMLResponse:
    """Erreur de `/oauth/authorize` qui ne peut pas repartir chez le client (retour non vérifié)."""
    corps = (
        "<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Connexion impossible — Assistant Potager</title></head>"
        "<body style='font-family:system-ui,sans-serif;max-width:32rem;margin:3rem auto;padding:0 1rem'>"
        "<h1 style='font-size:1.25rem'>Connexion impossible</h1>"
        f"<p>{html.escape(message)}</p>"
        "<p>Relance la connexion depuis ton assistant.</p></body></html>"
    )
    return HTMLResponse(status_code=400, content=corps)


def _identifiants_client(request: Request, formulaire: dict) -> tuple[Optional[str], Optional[str]]:
    """client_id / client_secret : en-tête Basic (client_secret_basic) ou formulaire."""
    entete = request.headers.get("authorization", "")
    if entete.lower().startswith("basic "):
        try:
            decode = base64.b64decode(entete[6:].strip()).decode("utf-8")
            client_id, _, secret = decode.partition(":")
            return unquote(client_id), unquote(secret)
        except (binascii.Error, UnicodeDecodeError):
            raise svc_autorisation.ErreurOAuth("invalid_client", "En-tête Basic illisible", statut=401)
    return formulaire.get("client_id"), formulaire.get("client_secret")


class ConsentementRequest(BaseModel):
    demande: str
    accepte: bool
    ecriture: bool = False
    potager_ids: list[int] = []


class AssistantsExternesRequest(BaseModel):
    interdit: bool


class JetonPersonnelRequest(BaseModel):
    libelle: str
    ecriture: bool = False
    potager_ids: list[int]
    duree_jours: Optional[int] = None


def creer_routeur(get_current_user: Callable[..., User], limiter) -> APIRouter:
    """Le routeur du canal MCP. `get_current_user` (session JWT de la PWA) et `limiter`
    (slowapi) viennent de `app.api.main`, qui l'inclut avant le repli SPA."""
    routeur = APIRouter()

    # ── Métadonnées ───────────────────────────────────────────────────────────
    @routeur.get("/.well-known/oauth-protected-resource", include_in_schema=False)
    @routeur.get("/.well-known/oauth-protected-resource/mcp", include_in_schema=False)
    def metadonnees_ressource():
        return svc_autorisation.metadonnees_ressource_protegee()

    @routeur.get("/.well-known/oauth-authorization-server", include_in_schema=False)
    @routeur.get("/.well-known/oauth-authorization-server/mcp", include_in_schema=False)
    def metadonnees_serveur():
        return svc_autorisation.metadonnees_serveur_autorisation()

    # ── Enregistrement dynamique ──────────────────────────────────────────────
    # Les clients d'un même éditeur (Claude, ChatGPT) partagent leurs adresses IP : les
    # plafonds par IP restent larges ; le vrai plafond est celui du connecteur (CA6).
    @routeur.post("/oauth/register", status_code=201, include_in_schema=False)
    @limiter.limit("30/minute")
    async def oauth_register(request: Request):
        try:
            donnees = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            return _erreur_oauth(svc_autorisation.ErreurOAuth("invalid_client_metadata", "Corps JSON attendu"))

        def _enregistrer():
            db = SessionLocal()
            try:
                return svc_autorisation.enregistrer_client(db, donnees)
            finally:
                db.close()

        try:
            reponse = await run_in_threadpool(_enregistrer)
        except svc_autorisation.ErreurOAuth as erreur:
            return _erreur_oauth(erreur)
        return JSONResponse(status_code=201, content=reponse, headers=_SANS_CACHE)

    # ── Autorisation → consentement dans la PWA ───────────────────────────────
    @routeur.get("/oauth/authorize", include_in_schema=False)
    def oauth_authorize(request: Request):
        params = dict(request.query_params)
        db = SessionLocal()
        try:
            demande = svc_autorisation.valider_demande(db, params)
        except svc_autorisation.ErreurDemandeAvecRetour as erreur:
            return RedirectResponse(erreur.redirection, status_code=302)
        except svc_autorisation.ErreurDemandeSansRetour as erreur:
            log.warning("[US-290] /oauth/authorize refusé : %s", erreur.description)
            return _page_erreur(erreur.description)
        finally:
            db.close()
        return RedirectResponse(f"{FRONTEND_URL}/connecteur-ia?{urlencode({'demande': demande})}", status_code=302)

    @routeur.get("/oauth/demande", include_in_schema=False)
    def oauth_demande(demande: str, user: User = Depends(get_current_user)):
        db = SessionLocal()
        try:
            return svc_autorisation.decrire_demande(db, user.id, demande)
        except svc_autorisation.ConsentementInvalideError as erreur:
            raise HTTPException(status_code=400, detail=str(erreur))
        finally:
            db.close()

    @routeur.post("/oauth/consentement", include_in_schema=False)
    def oauth_consentement(req: ConsentementRequest, user: User = Depends(get_current_user)):
        db = SessionLocal()
        try:
            url = svc_autorisation.consentir(
                db, user.id, req.demande, req.accepte, ecriture=req.ecriture, potager_ids=req.potager_ids,
            )
            return {"redirection": url}
        except svc_autorisation.ConsentementInvalideError as erreur:
            raise HTTPException(status_code=400, detail=str(erreur))
        finally:
            db.close()

    # ── Jeton et révocation ───────────────────────────────────────────────────
    @routeur.post("/oauth/token", include_in_schema=False)
    @limiter.limit("300/minute")
    async def oauth_token(request: Request):
        formulaire = dict(await request.form())

        def _jeton():
            db = SessionLocal()
            try:
                client_id, secret = _identifiants_client(request, formulaire)
                client = svc_autorisation.authentifier_client(db, client_id, secret)
                octroi = formulaire.get("grant_type")
                if octroi == "authorization_code":
                    return svc_autorisation.echanger_code(
                        db, client, formulaire.get("code"), formulaire.get("redirect_uri"),
                        formulaire.get("code_verifier"),
                    )
                if octroi == "refresh_token":
                    return svc_autorisation.rafraichir(db, client, formulaire.get("refresh_token"))
                raise svc_autorisation.ErreurOAuth("unsupported_grant_type", f"grant_type non pris en charge : {octroi}")
            finally:
                db.close()

        try:
            reponse = await run_in_threadpool(_jeton)
        except svc_autorisation.ErreurOAuth as erreur:
            log.info("[US-290] /oauth/token refusé : %s", erreur.code)
            return _erreur_oauth(erreur)
        return JSONResponse(content=reponse, headers=_SANS_CACHE)

    @routeur.post("/oauth/revoke", include_in_schema=False)
    async def oauth_revoke(request: Request):
        formulaire = dict(await request.form())

        def _revoquer():
            db = SessionLocal()
            try:
                client_id, secret = _identifiants_client(request, formulaire)
                client = svc_autorisation.authentifier_client(db, client_id, secret)
                svc_autorisation.revoquer_jeton(db, client, formulaire.get("token"))
            finally:
                db.close()

        try:
            await run_in_threadpool(_revoquer)
        except svc_autorisation.ErreurOAuth as erreur:
            return _erreur_oauth(erreur)
        return Response(status_code=200, headers=_SANS_CACHE)

    # ── Le serveur MCP ────────────────────────────────────────────────────────
    @routeur.post("/mcp", include_in_schema=False)
    @limiter.limit("240/minute", key_func=cle_debit_jeton)
    async def mcp(request: Request):
        entete = request.headers.get("authorization", "")
        jeton = entete[7:].strip() if entete.lower().startswith("bearer ") else None
        if not jeton:
            return _non_authentifie()
        brut = await request.body()

        def _traiter():
            db = SessionLocal()
            try:
                connexion = svc_autorisation.resoudre_jeton(db, jeton)
                if connexion is None:
                    return None, False
                try:
                    corps = json.loads(brut or b"null")
                except (json.JSONDecodeError, UnicodeDecodeError):
                    return {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "JSON illisible"}}, True
                return svc_serveur.traiter(db, connexion, corps), True
            finally:
                db.close()

        reponse, authentifie = await run_in_threadpool(_traiter)
        if not authentifie:
            return _non_authentifie("Jeton expiré, révoqué ou inconnu")
        if reponse is None:
            return Response(status_code=202)
        return JSONResponse(content=reponse)

    @routeur.api_route("/mcp", methods=["GET", "DELETE"], include_in_schema=False)
    def mcp_sans_flux():
        """Mode sans état : pas de flux SSE ouvert par le client, pas de session à clore."""
        return Response(status_code=405, headers={"Allow": "POST"})

    # ── Connecteurs du jardinier (PWA) ────────────────────────────────────────
    @routeur.get("/mcp/connexions")
    def lister_connexions_mcp(user: User = Depends(get_current_user)):
        db = SessionLocal()
        try:
            return {"connexions": svc_connexions.lister(db, user.id), "url_connecteur": svc_autorisation.url_ressource()}
        finally:
            db.close()

    @routeur.delete("/mcp/connexions/{autorisation_id}")
    def revoquer_connexion_mcp(autorisation_id: int, user: User = Depends(get_current_user)):
        db = SessionLocal()
        try:
            if not svc_autorisation.revoquer_connexion(db, user.id, autorisation_id):
                raise HTTPException(status_code=404, detail="Connecteur introuvable")
            return {"revoque": True}
        finally:
            db.close()

    @routeur.get("/mcp/connexions/{autorisation_id}/activite")
    def activite_connexion_mcp(autorisation_id: int, user: User = Depends(get_current_user)):
        """[US-294 / CA3] Les 100 derniers appels d'une connexion : date, outil, potager, résultat."""
        db = SessionLocal()
        try:
            appels = svc_connexions.activite(db, user.id, autorisation_id)
            if appels is None:
                raise HTTPException(status_code=404, detail="Connecteur introuvable")
            return {"appels": appels}
        finally:
            db.close()

    @routeur.patch("/potagers/{potager_id}/assistants-externes")
    def interdire_assistants_externes(
        potager_id: int, req: AssistantsExternesRequest, user: User = Depends(get_current_user),
    ):
        """[US-294 / CA6] Le propriétaire interdit (ou rouvre) les assistants externes pour ce potager."""
        db = SessionLocal()
        try:
            return svc_connexions.interdire_assistants(db, user.id, potager_id, req.interdit)
        except svc_connexions.PasProprietaireError as erreur:
            raise HTTPException(status_code=403, detail=str(erreur))
        except LookupError as erreur:
            raise HTTPException(status_code=404, detail=str(erreur))
        finally:
            db.close()

    @routeur.post("/mcp/jetons-personnels", status_code=201)
    def creer_jeton_personnel_mcp(req: JetonPersonnelRequest, user: User = Depends(get_current_user)):
        db = SessionLocal()
        try:
            autorisation, jeton = svc_autorisation.creer_jeton_personnel(
                db, user.id, req.libelle, req.ecriture, req.potager_ids, req.duree_jours,
            )
            return {
                "jeton": jeton,
                "connexion": svc_autorisation.decrire_autorisation(db, autorisation),
                "url_connecteur": svc_autorisation.url_ressource(),
            }
        except svc_autorisation.ConsentementInvalideError as erreur:
            raise HTTPException(status_code=400, detail=str(erreur))
        finally:
            db.close()

    return routeur

"""
tests/test_us290_serveur_mcp.py — Connecter son assistant IA à son potager [US-290]
===================================================================================
Serveur d'autorisation OAuth 2.1 (PKCE) + serveur MCP sans état sur /mcp.
Couverture CA1 → CA9 et le scénario Gherkin ; CA10 (Claude réel + MCP Inspector)
se vérifie à la main sur une URL publique.

Aucun appel réseau : l'API est jouée par TestClient sur une base SQLite partagée.
Un outil d'écriture FACTICE est enregistré par les tests qui en ont besoin (US-292
apportera les vrais) : il compte ses exécutions et note le contexte qu'il a reçu.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import config
from app.services import auth as svc_auth
from app.services.compagnon.actions_menees import CANAL_MCP, canal_courant
from app.services.mcp import autorisation as svc_autorisation
from app.services.mcp import serveur as svc_serveur
from database.db import Base, current_potager_id
from database.models import (
    McpAppel, McpAutorisation, McpClient, McpCodeAutorisation, McpJeton, Potager, PotagerMembre, User,
)

RACINE = Path(__file__).resolve().parents[1]
RETOUR = "https://claude.ai/api/mcp/auth_callback"
SECRET_LIBRE = "note-tres-personnelle-ne-pas-journaliser"


def LECTURES_REGISTRE() -> set[str]:
    """Les outils de lecture enregistrés (US-290 : `lister_potagers` ; US-291 en ajoute dix)."""
    return {nom for nom, outil in svc_serveur.REGISTRE.items() if not outil.ecriture}


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def fabrique():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(bind=engine, autocommit=False, autoflush=False)
    engine.dispose()


@pytest.fixture
def client(fabrique, monkeypatch):
    from app.api import main
    from app.api import mcp as api_mcp

    monkeypatch.setattr(main, "SessionLocal", fabrique)
    monkeypatch.setattr(api_mcp, "SessionLocal", fabrique)
    monkeypatch.setattr(config, "MCP_URL_PUBLIQUE", "https://potager.test")
    monkeypatch.setattr(api_mcp, "FRONTEND_URL", "https://potager.test")
    main.limiter.reset()
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def jardin(fabrique):
    """Une jardinière propriétaire de « Les Mésanges » et lectrice de « Le Verger »."""
    with fabrique() as db:
        camille = User(email="camille@test.fr", nom="Camille", email_verifie=True)
        autre = User(email="autre@test.fr", nom="Autre", email_verifie=True)
        db.add_all([camille, autre])
        db.flush()
        mesanges = Potager(nom="Les Mésanges", proprietaire_id=camille.id, etat="actif")
        verger = Potager(nom="Le Verger", proprietaire_id=autre.id, etat="actif")
        etranger = Potager(nom="Chez Autre", proprietaire_id=autre.id, etat="actif")
        db.add_all([mesanges, verger, etranger])
        db.flush()
        db.add_all([
            PotagerMembre(user_id=camille.id, potager_id=mesanges.id, role="owner"),
            PotagerMembre(user_id=camille.id, potager_id=verger.id, role="lecteur"),
            PotagerMembre(user_id=autre.id, potager_id=verger.id, role="owner"),
            PotagerMembre(user_id=autre.id, potager_id=etranger.id, role="owner"),
        ])
        camille.potager_actif_id = mesanges.id
        db.commit()
        return {
            "user_id": camille.id, "autre_id": autre.id,
            "mesanges": mesanges.id, "verger": verger.id, "etranger": etranger.id,
        }


@pytest.fixture
def outil_ecriture():
    """Un outil d'écriture factice, retiré du registre en fin de test."""
    appels: list[dict] = []

    def executer(db, appel):
        appels.append({
            "potager_id": appel.ctx.potager_id, "role": appel.ctx.role,
            "guc": current_potager_id.get(), "canal": canal_courant.get(),
        })
        return {"propose": True}

    svc_serveur.enregistrer_outil(svc_serveur.Outil(
        nom="proposer_test", titre="Proposer (test)", description="Écriture factice.",
        executer=executer, ecriture=True, idempotent=False,
        proprietes={"note": {"type": "string"}},
    ))
    yield appels
    svc_serveur.REGISTRE.pop("proposer_test", None)


def _pwa(user_id: int) -> dict:
    return {"Authorization": f"Bearer {svc_auth.creer_access_token(user_id)}"}


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def _enregistrer(client, **extra) -> dict:
    corps = {"client_name": "Claude", "redirect_uris": [RETOUR], "token_endpoint_auth_method": "none"}
    corps.update(extra)
    reponse = client.post("/oauth/register", json=corps)
    assert reponse.status_code == 201, reponse.text
    return reponse.json()


def _autoriser(client, client_id: str, challenge: str, scope: str = "potager.lecture", state: str = "xyz"):
    return client.get("/oauth/authorize", params={
        "response_type": "code", "client_id": client_id, "redirect_uri": RETOUR,
        "code_challenge": challenge, "code_challenge_method": "S256", "state": state, "scope": scope,
        "resource": "https://potager.test/mcp",
    }, follow_redirects=False)


def _demande(reponse) -> str:
    assert reponse.status_code == 302, reponse.text
    url = urlsplit(reponse.headers["location"])
    assert url.path == "/connecteur-ia"
    return parse_qs(url.query)["demande"][0]


def _connecter(client, jardin, *, ecriture=False, potagers=None, enregistrement=None) -> dict:
    """Le parcours complet : enregistrement, autorisation, consentement, jeton."""
    enregistrement = enregistrement or _enregistrer(client)
    verifier, challenge = _pkce()
    demande = _demande(_autoriser(client, enregistrement["client_id"], challenge))
    consentement = client.post("/oauth/consentement", headers=_pwa(jardin["user_id"]), json={
        "demande": demande, "accepte": True, "ecriture": ecriture,
        "potager_ids": potagers if potagers is not None else [jardin["mesanges"]],
    })
    assert consentement.status_code == 200, consentement.text
    retour = parse_qs(urlsplit(consentement.json()["redirection"]).query)
    jetons = client.post("/oauth/token", data={
        "grant_type": "authorization_code", "code": retour["code"][0], "redirect_uri": RETOUR,
        "client_id": enregistrement["client_id"], "code_verifier": verifier,
    })
    assert jetons.status_code == 200, jetons.text
    return {**jetons.json(), "client_id": enregistrement["client_id"]}


def _rpc(client, jeton: str, methode: str, params: dict | None = None, ident: int = 1):
    corps = {"jsonrpc": "2.0", "id": ident, "method": methode}
    if params is not None:
        corps["params"] = params
    return client.post("/mcp", json=corps, headers={"Authorization": f"Bearer {jeton}"})


def _appeler(client, jeton: str, outil: str, arguments: dict | None = None) -> dict:
    reponse = _rpc(client, jeton, "tools/call", {"name": outil, "arguments": arguments or {}})
    assert reponse.status_code == 200, reponse.text
    return reponse.json()["result"]


def _noms_outils(client, jeton: str) -> set[str]:
    return {o["name"] for o in _rpc(client, jeton, "tools/list").json()["result"]["tools"]}


def _journal(fabrique) -> list[McpAppel]:
    with fabrique() as db:
        lignes = db.query(McpAppel).order_by(McpAppel.id).all()
        db.expunge_all()
        return lignes


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — Une URL unique, et sans jeton : une invitation à s'authentifier
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1UrlEtInvitation:

    def test_us290_mcp_sans_jeton_invite_a_s_authentifier(self, client):
        reponse = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert reponse.status_code == 401
        entete = reponse.headers["www-authenticate"]
        assert entete.startswith("Bearer ")
        assert 'resource_metadata="https://potager.test/.well-known/oauth-protected-resource/mcp"' in entete
        assert "result" not in reponse.json()

    def test_us290_mcp_jeton_inconnu_rend_401_sans_donnees(self, client):
        reponse = _rpc(client, "mcpa_inconnu", "tools/list")
        assert reponse.status_code == 401
        assert 'error="invalid_token"' in reponse.headers["www-authenticate"]
        assert "result" not in reponse.json()

    def test_us290_metadonnees_de_la_ressource(self, client):
        for chemin in ("/.well-known/oauth-protected-resource", "/.well-known/oauth-protected-resource/mcp"):
            meta = client.get(chemin).json()
            assert meta["resource"] == "https://potager.test/mcp"
            assert meta["authorization_servers"] == ["https://potager.test"]

    def test_us290_metadonnees_du_serveur_d_autorisation(self, client):
        meta = client.get("/.well-known/oauth-authorization-server").json()
        assert meta["issuer"] == "https://potager.test"
        assert meta["code_challenge_methods_supported"] == ["S256"]
        assert meta["registration_endpoint"] == "https://potager.test/oauth/register"
        assert "authorization_code" in meta["grant_types_supported"]

    def test_us290_get_mcp_n_ouvre_pas_de_flux(self, client):
        reponse = client.get("/mcp")
        assert reponse.status_code == 405 and reponse.headers["allow"] == "POST"

    def test_us290_cors_ouvert_sur_le_seul_canal_mcp(self, client):
        preflight = client.options("/oauth/token", headers={
            "Origin": "http://localhost:6274", "Access-Control-Request-Method": "POST",
        })
        assert preflight.status_code == 204
        assert preflight.headers["access-control-allow-origin"] == "*"
        reponse = client.post("/mcp", json={})
        assert "WWW-Authenticate" in reponse.headers["access-control-expose-headers"]

    def test_us290_initialize_rend_le_protocole_et_les_capacites(self, client, jardin):
        jeton = _connecter(client, jardin)["access_token"]
        resultat = _rpc(client, jeton, "initialize", {
            "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "Claude", "version": "1"},
        }).json()["result"]
        assert resultat["protocolVersion"] == "2025-06-18"
        assert resultat["capabilities"] == {  # [US-295] + ressources et prompts
            "tools": {"listChanged": False},
            "resources": {"listChanged": False, "subscribe": False},
            "prompts": {"listChanged": False},
        }
        assert resultat["serverInfo"]["name"] == "assistant-potager"
        assert "inventer" in resultat["instructions"]

    def test_us290_version_inconnue_rend_la_plus_recente(self, client, jardin):
        jeton = _connecter(client, jardin)["access_token"]
        resultat = _rpc(client, jeton, "initialize", {"protocolVersion": "1999-01-01"}).json()["result"]
        assert resultat["protocolVersion"] == svc_serveur.VERSIONS_PROTOCOLE[0]

    def test_us290_notification_rend_202_sans_corps(self, client, jardin):
        jeton = _connecter(client, jardin)["access_token"]
        reponse = client.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                              headers={"Authorization": f"Bearer {jeton}"})
        assert reponse.status_code == 202 and reponse.content == b""

    def test_us290_json_illisible_et_methode_inconnue(self, client, jardin):
        jeton = _connecter(client, jardin)["access_token"]
        entetes = {"Authorization": f"Bearer {jeton}", "Content-Type": "application/json"}
        assert client.post("/mcp", content=b"{pas du json", headers=entetes).json()["error"]["code"] == -32700
        assert _rpc(client, jeton, "sampling/createMessage").json()["error"]["code"] == -32601
        assert _rpc(client, jeton, "ping").json()["result"] == {}
        assert len(_rpc(client, jeton, "prompts/list").json()["result"]["prompts"]) == 4  # [US-295]

    def test_us290_lot_de_messages(self, client, jardin):
        jeton = _connecter(client, jardin)["access_token"]
        reponse = client.post("/mcp", headers={"Authorization": f"Bearer {jeton}"}, json=[
            {"jsonrpc": "2.0", "id": 1, "method": "ping"},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ])
        assert [r["id"] for r in reponse.json()] == [1, 2]


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — OAuth 2.1 + PKCE, consentement nommant l'assistant, la portée, les potagers
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2OAuth:

    def test_us290_enregistrement_dynamique_client_public(self, client):
        reponse = _enregistrer(client)
        assert reponse["client_id"].startswith("mcp_")
        assert reponse["token_endpoint_auth_method"] == "none"
        assert "client_secret" not in reponse

    def test_us290_enregistrement_refuse_un_retour_http_distant(self, client):
        reponse = client.post("/oauth/register", json={"client_name": "X", "redirect_uris": ["http://evil.example/cb"]})
        assert reponse.status_code == 400 and reponse.json()["error"] == "invalid_redirect_uri"

    def test_us290_enregistrement_accepte_la_boucle_locale(self, client):
        reponse = _enregistrer(client, redirect_uris=["http://localhost:6274/oauth/callback"])
        assert reponse["redirect_uris"] == ["http://localhost:6274/oauth/callback"]

    def test_us290_authorize_renvoie_vers_la_page_de_consentement(self, client):
        enregistrement = _enregistrer(client)
        _verifier, challenge = _pkce()
        demande = _demande(_autoriser(client, enregistrement["client_id"], challenge))
        assert demande.count(".") == 2  # une demande signée (JWT), aucune table d'attente

    def test_us290_authorize_client_inconnu_ne_redirige_jamais(self, client):
        _v, challenge = _pkce()
        reponse = _autoriser(client, "mcp_inconnu", challenge)
        assert reponse.status_code == 400 and "location" not in reponse.headers
        assert "Connexion impossible" in reponse.text

    def test_us290_authorize_retour_non_enregistre_ne_redirige_jamais(self, client):
        enregistrement = _enregistrer(client)
        _v, challenge = _pkce()
        reponse = client.get("/oauth/authorize", params={
            "response_type": "code", "client_id": enregistrement["client_id"],
            "redirect_uri": "https://evil.example/cb", "code_challenge": challenge, "code_challenge_method": "S256",
        }, follow_redirects=False)
        assert reponse.status_code == 400 and "location" not in reponse.headers

    def test_us290_authorize_sans_pkce_repart_en_erreur_chez_le_client(self, client):
        enregistrement = _enregistrer(client)
        reponse = client.get("/oauth/authorize", params={
            "response_type": "code", "client_id": enregistrement["client_id"], "redirect_uri": RETOUR, "state": "s1",
        }, follow_redirects=False)
        assert reponse.status_code == 302
        retour = parse_qs(urlsplit(reponse.headers["location"]).query)
        assert retour["error"] == ["invalid_request"] and retour["state"] == ["s1"]

    def test_us290_authorize_pkce_plain_refuse(self, client):
        enregistrement = _enregistrer(client)
        reponse = client.get("/oauth/authorize", params={
            "response_type": "code", "client_id": enregistrement["client_id"], "redirect_uri": RETOUR,
            "code_challenge": "a" * 43, "code_challenge_method": "plain",
        }, follow_redirects=False)
        assert parse_qs(urlsplit(reponse.headers["location"]).query)["error"] == ["invalid_request"]

    def test_us290_authorize_ressource_etrangere_refusee(self, client):
        enregistrement = _enregistrer(client)
        _v, challenge = _pkce()
        reponse = client.get("/oauth/authorize", params={
            "response_type": "code", "client_id": enregistrement["client_id"], "redirect_uri": RETOUR,
            "code_challenge": challenge, "code_challenge_method": "S256", "resource": "https://autre.example/mcp",
        }, follow_redirects=False)
        assert parse_qs(urlsplit(reponse.headers["location"]).query)["error"] == ["invalid_target"]

    def test_us290_page_de_consentement_nomme_assistant_portee_et_potagers(self, client, jardin):
        enregistrement = _enregistrer(client)
        _v, challenge = _pkce()
        demande = _demande(_autoriser(client, enregistrement["client_id"], challenge, scope="potager.lecture potager.ecriture"))
        infos = client.get("/oauth/demande", params={"demande": demande}, headers=_pwa(jardin["user_id"])).json()
        assert infos["client"] == {"nom": "Claude", "retour": "claude.ai"}
        assert infos["ecriture_demandee"] is True
        noms = {p["nom"]: p for p in infos["potagers"]}
        assert set(noms) == {"Les Mésanges", "Le Verger"}  # jamais le potager d'un autre
        assert noms["Les Mésanges"]["actif"] is True and noms["Le Verger"]["role"] == "lecteur"

    def test_us290_consentement_exige_la_session_du_jardinier(self, client):
        enregistrement = _enregistrer(client)
        _v, challenge = _pkce()
        demande = _demande(_autoriser(client, enregistrement["client_id"], challenge))
        assert client.get("/oauth/demande", params={"demande": demande}).status_code == 401
        assert client.post("/oauth/consentement", json={"demande": demande, "accepte": True}).status_code == 401

    def test_us290_lecture_seule_par_defaut(self, client, jardin, fabrique):
        jetons = _connecter(client, jardin)
        assert jetons["scope"] == "potager.lecture"
        with fabrique() as db:
            assert db.query(McpAutorisation).one().portee == "lecture"

    def test_us290_refus_renvoie_access_denied(self, client, jardin):
        enregistrement = _enregistrer(client)
        _v, challenge = _pkce()
        demande = _demande(_autoriser(client, enregistrement["client_id"], challenge, state="etat-42"))
        url = client.post("/oauth/consentement", headers=_pwa(jardin["user_id"]),
                          json={"demande": demande, "accepte": False}).json()["redirection"]
        retour = parse_qs(urlsplit(url).query)
        assert url.startswith(RETOUR) and retour["error"] == ["access_denied"] and retour["state"] == ["etat-42"]

    def test_us290_consentement_sans_potager_refuse(self, client, jardin):
        enregistrement = _enregistrer(client)
        _v, challenge = _pkce()
        demande = _demande(_autoriser(client, enregistrement["client_id"], challenge))
        reponse = client.post("/oauth/consentement", headers=_pwa(jardin["user_id"]),
                              json={"demande": demande, "accepte": True, "potager_ids": []})
        assert reponse.status_code == 400

    def test_us290_consentement_sur_le_potager_d_un_autre_refuse(self, client, jardin):
        enregistrement = _enregistrer(client)
        _v, challenge = _pkce()
        demande = _demande(_autoriser(client, enregistrement["client_id"], challenge))
        reponse = client.post("/oauth/consentement", headers=_pwa(jardin["user_id"]),
                              json={"demande": demande, "accepte": True, "potager_ids": [jardin["etranger"]]})
        assert reponse.status_code == 400

    def test_us290_demande_falsifiee_refusee(self, client, jardin):
        reponse = client.get("/oauth/demande", params={"demande": "a.b.c"}, headers=_pwa(jardin["user_id"]))
        assert reponse.status_code == 400

    def test_us290_code_rendu_avec_state_et_emetteur(self, client, jardin):
        enregistrement = _enregistrer(client)
        _v, challenge = _pkce()
        demande = _demande(_autoriser(client, enregistrement["client_id"], challenge, state="s-9"))
        url = client.post("/oauth/consentement", headers=_pwa(jardin["user_id"]), json={
            "demande": demande, "accepte": True, "potager_ids": [jardin["mesanges"]],
        }).json()["redirection"]
        retour = parse_qs(urlsplit(url).query)
        assert retour["code"][0].startswith("mcpc_") and retour["state"] == ["s-9"]
        assert retour["iss"] == ["https://potager.test"]

    def test_us290_mauvais_verificateur_pkce_refuse(self, client, jardin):
        enregistrement = _enregistrer(client)
        _v, challenge = _pkce()
        demande = _demande(_autoriser(client, enregistrement["client_id"], challenge))
        url = client.post("/oauth/consentement", headers=_pwa(jardin["user_id"]), json={
            "demande": demande, "accepte": True, "potager_ids": [jardin["mesanges"]],
        }).json()["redirection"]
        code = parse_qs(urlsplit(url).query)["code"][0]
        reponse = client.post("/oauth/token", data={
            "grant_type": "authorization_code", "code": code, "redirect_uri": RETOUR,
            "client_id": enregistrement["client_id"], "code_verifier": secrets.token_urlsafe(48),
        })
        assert reponse.status_code == 400 and reponse.json()["error"] == "invalid_grant"

    def test_us290_code_rejoue_revoque_la_connexion(self, client, jardin, fabrique):
        enregistrement = _enregistrer(client)
        verifier, challenge = _pkce()
        demande = _demande(_autoriser(client, enregistrement["client_id"], challenge))
        url = client.post("/oauth/consentement", headers=_pwa(jardin["user_id"]), json={
            "demande": demande, "accepte": True, "potager_ids": [jardin["mesanges"]],
        }).json()["redirection"]
        code = parse_qs(urlsplit(url).query)["code"][0]
        donnees = {"grant_type": "authorization_code", "code": code, "redirect_uri": RETOUR,
                   "client_id": enregistrement["client_id"], "code_verifier": verifier}
        premier = client.post("/oauth/token", data=donnees).json()
        assert client.post("/oauth/token", data=donnees).json()["error"] == "invalid_grant"
        assert _rpc(client, premier["access_token"], "tools/list").status_code == 401

    def test_us290_code_expire_refuse(self, client, jardin, fabrique):
        enregistrement = _enregistrer(client)
        verifier, challenge = _pkce()
        demande = _demande(_autoriser(client, enregistrement["client_id"], challenge))
        url = client.post("/oauth/consentement", headers=_pwa(jardin["user_id"]), json={
            "demande": demande, "accepte": True, "potager_ids": [jardin["mesanges"]],
        }).json()["redirection"]
        with fabrique() as db:
            db.query(McpCodeAutorisation).update({McpCodeAutorisation.expire_le: svc_autorisation._maintenant() - timedelta(seconds=1)})
            db.commit()
        reponse = client.post("/oauth/token", data={
            "grant_type": "authorization_code", "code": parse_qs(urlsplit(url).query)["code"][0],
            "redirect_uri": RETOUR, "client_id": enregistrement["client_id"], "code_verifier": verifier,
        })
        assert reponse.json()["error"] == "invalid_grant"

    def test_us290_code_d_un_autre_client_refuse(self, client, jardin):
        a = _enregistrer(client)
        b = _enregistrer(client, client_name="Intrus")
        verifier, challenge = _pkce()
        demande = _demande(_autoriser(client, a["client_id"], challenge))
        url = client.post("/oauth/consentement", headers=_pwa(jardin["user_id"]), json={
            "demande": demande, "accepte": True, "potager_ids": [jardin["mesanges"]],
        }).json()["redirection"]
        reponse = client.post("/oauth/token", data={
            "grant_type": "authorization_code", "code": parse_qs(urlsplit(url).query)["code"][0],
            "redirect_uri": RETOUR, "client_id": b["client_id"], "code_verifier": verifier,
        })
        assert reponse.json()["error"] == "invalid_grant"

    def test_us290_rafraichissement_avec_rotation(self, client, jardin):
        jetons = _connecter(client, jardin)
        nouveaux = client.post("/oauth/token", data={
            "grant_type": "refresh_token", "refresh_token": jetons["refresh_token"], "client_id": jetons["client_id"],
        }).json()
        assert nouveaux["access_token"] != jetons["access_token"]
        assert nouveaux["refresh_token"] != jetons["refresh_token"]
        assert _rpc(client, nouveaux["access_token"], "tools/list").status_code == 200

    def test_us290_rafraichissement_rejoue_revoque_tout(self, client, jardin):
        jetons = _connecter(client, jardin)
        donnees = {"grant_type": "refresh_token", "refresh_token": jetons["refresh_token"], "client_id": jetons["client_id"]}
        nouveaux = client.post("/oauth/token", data=donnees).json()
        assert client.post("/oauth/token", data=donnees).json()["error"] == "invalid_grant"
        assert _rpc(client, nouveaux["access_token"], "tools/list").status_code == 401

    def test_us290_grant_type_inconnu(self, client, jardin):
        enregistrement = _enregistrer(client)
        reponse = client.post("/oauth/token", data={"grant_type": "password", "client_id": enregistrement["client_id"]})
        assert reponse.json()["error"] == "unsupported_grant_type"

    def test_us290_client_confidentiel_par_basic(self, client, jardin):
        enregistrement = _enregistrer(client, token_endpoint_auth_method="client_secret_basic")
        assert enregistrement["client_secret"].startswith("mcps_")
        verifier, challenge = _pkce()
        demande = _demande(_autoriser(client, enregistrement["client_id"], challenge))
        url = client.post("/oauth/consentement", headers=_pwa(jardin["user_id"]), json={
            "demande": demande, "accepte": True, "potager_ids": [jardin["mesanges"]],
        }).json()["redirection"]
        code = parse_qs(urlsplit(url).query)["code"][0]
        donnees = {"grant_type": "authorization_code", "code": code, "redirect_uri": RETOUR, "code_verifier": verifier}
        sans_secret = client.post("/oauth/token", data={**donnees, "client_id": enregistrement["client_id"]})
        assert sans_secret.status_code == 401 and sans_secret.json()["error"] == "invalid_client"
        basic = base64.b64encode(f"{enregistrement['client_id']}:{enregistrement['client_secret']}".encode()).decode()
        reponse = client.post("/oauth/token", data=donnees, headers={"Authorization": f"Basic {basic}"})
        assert reponse.status_code == 200 and reponse.headers["cache-control"] == "no-store"

    def test_us290_secrets_jamais_stockes_en_clair(self, client, jardin, fabrique):
        jetons = _connecter(client, jardin)
        with fabrique() as db:
            empreintes = {j.empreinte for j in db.query(McpJeton).all()}
        assert jetons["access_token"] not in empreintes
        assert hashlib.sha256(jetons["access_token"].encode()).hexdigest() in empreintes


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — La page de consentement avertit que les données partent chez l'éditeur
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3Avertissement:

    def test_us290_page_de_consentement_avertit_de_la_sortie_des_donnees(self):
        source = (RACINE / "frontend/src/views/ConsentementConnecteur.jsx").read_text(encoding="utf-8")
        assert "politique de confidentialité" in source
        assert "Anthropic, OpenAI, Mistral" in source
        assert "Nous ne pouvons ni l’effacer ni le contrôler" in source

    def test_us290_case_lecture_cochee_et_figee_ecriture_a_cocher(self):
        source = (RACINE / "frontend/src/views/ConsentementConnecteur.jsx").read_text(encoding="utf-8")
        assert 'id="portee-lecture"\n                  checked\n                  disabled' in source
        assert "useState(false)" in source  # l'écriture part décochée


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — Contexte locataire à chaque appel ; potager hors consentement refusé
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4ContexteLocataire:

    def test_us290_lister_potagers_ne_rend_que_les_potagers_consentis(self, client, jardin):
        jeton = _connecter(client, jardin)["access_token"]
        resultat = _appeler(client, jeton, "lister_potagers")
        assert resultat["isError"] is False
        potagers = resultat["structuredContent"]["potagers"]
        assert [p["nom"] for p in potagers] == ["Les Mésanges"]
        assert potagers[0]["role"] == "propriétaire" and potagers[0]["actif"] is True

    def test_us290_contexte_arme_rls_et_canal_mcp(self, client, jardin, outil_ecriture):
        jeton = _connecter(client, jardin, ecriture=True)["access_token"]
        _appeler(client, jeton, "proposer_test", {"potager": "les mesanges"})
        assert outil_ecriture == [{
            "potager_id": jardin["mesanges"], "role": "owner", "guc": jardin["mesanges"], "canal": CANAL_MCP,
        }]

    def test_us290_potager_hors_consentement_refuse(self, client, jardin, outil_ecriture):
        jeton = _connecter(client, jardin, ecriture=True)["access_token"]
        resultat = _appeler(client, jeton, "proposer_test", {"potager": "Le Verger"})
        assert resultat["isError"] is True and "pas couvert par ce connecteur" in resultat["content"][0]["text"]
        assert outil_ecriture == []

    def test_us290_potager_d_un_autre_jardinier_refuse(self, client, jardin, outil_ecriture):
        jeton = _connecter(client, jardin, ecriture=True)["access_token"]
        resultat = _appeler(client, jeton, "proposer_test", {"potager": jardin["etranger"]})
        assert resultat["isError"] is True and "introuvable" in resultat["content"][0]["text"]
        assert outil_ecriture == []

    def test_us290_membre_retire_perd_l_acces(self, client, jardin, fabrique, outil_ecriture):
        jeton = _connecter(client, jardin, ecriture=True)["access_token"]
        with fabrique() as db:
            db.query(PotagerMembre).filter(PotagerMembre.user_id == jardin["user_id"],
                                           PotagerMembre.potager_id == jardin["mesanges"]).delete()
            db.commit()
        resultat = _appeler(client, jeton, "proposer_test")
        assert resultat["isError"] is True and outil_ecriture == []

    def test_us290_plusieurs_potagers_sans_actif_consenti_demande_lequel(self, client, jardin, fabrique, outil_ecriture):
        jeton = _connecter(client, jardin, ecriture=True, potagers=[jardin["mesanges"], jardin["verger"]])["access_token"]
        with fabrique() as db:
            db.query(User).filter(User.id == jardin["user_id"]).update({User.potager_actif_id: None})
            db.commit()
        resultat = _appeler(client, jeton, "proposer_test")
        assert resultat["isError"] is True and "Précise le potager" in resultat["content"][0]["text"]

    def test_us290_sans_potager_nomme_le_potager_actif(self, client, jardin, outil_ecriture):
        jeton = _connecter(client, jardin, ecriture=True, potagers=[jardin["mesanges"], jardin["verger"]])["access_token"]
        _appeler(client, jeton, "proposer_test")
        assert outil_ecriture[0]["potager_id"] == jardin["mesanges"]

    def test_us290_potager_archive_inaccessible(self, client, jardin, fabrique, outil_ecriture):
        jeton = _connecter(client, jardin, ecriture=True)["access_token"]
        with fabrique() as db:
            db.query(Potager).filter(Potager.id == jardin["mesanges"]).update({Potager.etat: "archive"})
            db.commit()
        resultat = _appeler(client, jeton, "proposer_test")
        assert resultat["isError"] is True and outil_ecriture == []


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — Outils selon la portée et le rôle ; écriture forcée refusée
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5PorteeEtRole:

    def test_us290_portee_lecture_liste_la_lecture_seule(self, client, jardin, outil_ecriture):
        jeton = _connecter(client, jardin)["access_token"]
        assert _noms_outils(client, jeton) == LECTURES_REGISTRE()

    def test_us290_annotations_lecture_seule(self, client, jardin):
        jeton = _connecter(client, jardin)["access_token"]
        outil = _rpc(client, jeton, "tools/list").json()["result"]["tools"][0]
        assert outil["annotations"]["readOnlyHint"] is True and outil["annotations"]["destructiveHint"] is False
        assert outil["inputSchema"]["type"] == "object"

    def test_us290_portee_ecriture_et_editeur_liste_l_ecriture(self, client, jardin, outil_ecriture):
        jeton = _connecter(client, jardin, ecriture=True)["access_token"]
        assert _noms_outils(client, jeton) == set(svc_serveur.REGISTRE)  # lectures + écritures (US-292) + factice

    def test_us290_portee_ecriture_mais_lecteur_partout_lecture_seule(self, client, jardin, outil_ecriture):
        jeton = _connecter(client, jardin, ecriture=True, potagers=[jardin["verger"]])["access_token"]
        assert _noms_outils(client, jeton) == LECTURES_REGISTRE()

    def test_us290_ecriture_forcee_sur_portee_lecture_refusee(self, client, jardin, outil_ecriture):
        jeton = _connecter(client, jardin)["access_token"]
        resultat = _appeler(client, jeton, "proposer_test", {"note": "x"})
        assert resultat["isError"] is True
        assert resultat["content"][0]["text"] == "Écriture non autorisée pour ce connecteur"
        assert outil_ecriture == []

    def test_us290_ecriture_forcee_par_un_lecteur_refusee(self, client, jardin, outil_ecriture):
        jeton = _connecter(client, jardin, ecriture=True, potagers=[jardin["mesanges"], jardin["verger"]])["access_token"]
        resultat = _appeler(client, jeton, "proposer_test", {"potager": "Le Verger"})
        assert resultat["content"][0]["text"] == "Tu es lecteur sur ce potager"
        assert outil_ecriture == []

    def test_us290_outil_inconnu_erreur_protocole(self, client, jardin):
        jeton = _connecter(client, jardin)["access_token"]
        reponse = _rpc(client, jeton, "tools/call", {"name": "supprimer_parcelle", "arguments": {}}).json()
        assert reponse["error"]["code"] == -32602

    def test_us290_argument_inconnu_refuse(self, client, jardin):
        jeton = _connecter(client, jardin)["access_token"]
        resultat = _appeler(client, jeton, "lister_potagers", {"sql": "drop"})
        assert resultat["isError"] is True and "Argument inconnu" in resultat["content"][0]["text"]

    def test_us290_aucun_outil_destructeur_enregistrable(self):
        with pytest.raises(ValueError):
            svc_serveur.enregistrer_outil(svc_serveur.Outil(
                nom="supprimer_x", titre="x", description="x", executer=lambda db, a: None,
                ecriture=True, destructeur=True,
            ))
        assert "supprimer_x" not in svc_serveur.REGISTRE

    def test_us290_erreur_interne_masquee_et_journalisee(self, client, jardin, fabrique):
        def casse(db, appel):
            raise RuntimeError("boum")
        svc_serveur.enregistrer_outil(svc_serveur.Outil(nom="casse_test", titre="x", description="x", executer=casse))
        try:
            jeton = _connecter(client, jardin)["access_token"]
            resultat = _appeler(client, jeton, "casse_test")
        finally:
            svc_serveur.REGISTRE.pop("casse_test", None)
        assert resultat["isError"] is True and "boum" not in resultat["content"][0]["text"]
        assert _journal(fabrique)[-1].resultat == "erreur"


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — Plafond d'appels par minute et par jour, par connecteur
# ═════════════════════════════════════════════════════════════════════════════
class TestCA6Quotas:

    def test_us290_plafond_minute_rien_n_est_execute(self, client, jardin, outil_ecriture, monkeypatch, fabrique):
        monkeypatch.setattr(config, "MCP_QUOTA_MINUTE", 2)
        jeton = _connecter(client, jardin, ecriture=True)["access_token"]
        _appeler(client, jeton, "proposer_test")
        _appeler(client, jeton, "proposer_test")
        resultat = _appeler(client, jeton, "proposer_test")
        assert resultat["isError"] is True and "Trop d'appels" in resultat["content"][0]["text"]
        assert len(outil_ecriture) == 2
        assert _journal(fabrique)[-1].motif == "quota"

    def test_us290_plafond_jour(self, client, jardin, monkeypatch):
        monkeypatch.setattr(config, "MCP_QUOTA_JOUR", 1)
        jeton = _connecter(client, jardin)["access_token"]
        assert _appeler(client, jeton, "lister_potagers")["isError"] is False
        assert "Plafond quotidien" in _appeler(client, jeton, "lister_potagers")["content"][0]["text"]

    def test_us290_plafond_propre_a_chaque_connecteur(self, client, jardin, monkeypatch):
        monkeypatch.setattr(config, "MCP_QUOTA_MINUTE", 1)
        premier = _connecter(client, jardin)["access_token"]
        second = _connecter(client, jardin)["access_token"]
        _appeler(client, premier, "lister_potagers")
        assert _appeler(client, premier, "lister_potagers")["isError"] is True
        assert _appeler(client, second, "lister_potagers")["isError"] is False

    def test_us290_refus_de_quota_ne_prolonge_pas_le_blocage(self, client, jardin, monkeypatch, fabrique):
        monkeypatch.setattr(config, "MCP_QUOTA_MINUTE", 1)
        jeton = _connecter(client, jardin)["access_token"]
        _appeler(client, jeton, "lister_potagers")
        for _ in range(3):
            _appeler(client, jeton, "lister_potagers")
        with fabrique() as db:  # la minute passe
            db.query(McpAppel).update({McpAppel.horodatage: svc_autorisation._maintenant() - timedelta(minutes=2)})
            db.commit()
        assert _appeler(client, jeton, "lister_potagers")["isError"] is False


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — Journal de chaque appel, sans le contenu des textes libres
# ═════════════════════════════════════════════════════════════════════════════
class TestCA7Journal:

    def test_us290_appel_journalise(self, client, jardin, fabrique):
        jeton = _connecter(client, jardin)["access_token"]
        _appeler(client, jeton, "lister_potagers")
        ligne = _journal(fabrique)[-1]
        assert (ligne.client, ligne.outil, ligne.resultat, ligne.user_id) == ("Claude", "lister_potagers", "ok", jardin["user_id"])
        assert ligne.horodatage is not None and ligne.duree_ms >= 0

    def test_us290_refus_journalise_avec_potager(self, client, jardin, fabrique, outil_ecriture):
        jeton = _connecter(client, jardin, ecriture=True, potagers=[jardin["mesanges"], jardin["verger"]])["access_token"]
        _appeler(client, jeton, "proposer_test", {"potager": "Le Verger"})
        ligne = _journal(fabrique)[-1]
        assert (ligne.resultat, ligne.motif, ligne.potager_id) == ("refus", "role", jardin["verger"])

    def test_us290_journal_sans_texte_libre(self, client, jardin, fabrique, outil_ecriture):
        jeton = _connecter(client, jardin, ecriture=True)["access_token"]
        _appeler(client, jeton, "proposer_test", {"note": SECRET_LIBRE})
        for ligne in _journal(fabrique):
            valeurs = [str(getattr(ligne, c.name)) for c in McpAppel.__table__.columns]
            assert not any(SECRET_LIBRE in v for v in valeurs)

    def test_us290_dernier_appel_retenu_sur_la_connexion(self, client, jardin, fabrique):
        jeton = _connecter(client, jardin)["access_token"]
        _appeler(client, jeton, "lister_potagers")
        with fabrique() as db:
            assert db.query(McpAutorisation).one().dernier_appel_le is not None


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — Révocation ou compte supprimé : accès coupé à l'appel suivant
# ═════════════════════════════════════════════════════════════════════════════
class TestCA8Revocation:

    def test_us290_revocation_depuis_la_pwa(self, client, jardin):
        jeton = _connecter(client, jardin)["access_token"]
        connexions = client.get("/mcp/connexions", headers=_pwa(jardin["user_id"])).json()
        assert connexions["url_connecteur"] == "https://potager.test/mcp"
        identifiant = connexions["connexions"][0]["id"]
        assert client.delete(f"/mcp/connexions/{identifiant}", headers=_pwa(jardin["user_id"])).json() == {"revoque": True}
        assert _rpc(client, jeton, "tools/list").status_code == 401
        liste = client.get("/mcp/connexions", headers=_pwa(jardin["user_id"])).json()["connexions"]
        assert liste[0]["revoque_le"] is not None

    def test_us290_on_ne_revoque_pas_le_connecteur_d_un_autre(self, client, jardin):
        _connecter(client, jardin)
        identifiant = client.get("/mcp/connexions", headers=_pwa(jardin["user_id"])).json()["connexions"][0]["id"]
        assert client.delete(f"/mcp/connexions/{identifiant}", headers=_pwa(jardin["autre_id"])).status_code == 404

    def test_us290_revocation_par_le_client_rfc7009(self, client, jardin):
        jetons = _connecter(client, jardin)
        reponse = client.post("/oauth/revoke", data={"token": jetons["refresh_token"], "client_id": jetons["client_id"]})
        assert reponse.status_code == 200
        assert _rpc(client, jetons["access_token"], "tools/list").status_code == 401

    def test_us290_revocation_d_un_jeton_d_acces_seul(self, client, jardin):
        jetons = _connecter(client, jardin)
        client.post("/oauth/revoke", data={"token": jetons["access_token"], "client_id": jetons["client_id"]})
        assert _rpc(client, jetons["access_token"], "tools/list").status_code == 401
        nouveaux = client.post("/oauth/token", data={
            "grant_type": "refresh_token", "refresh_token": jetons["refresh_token"], "client_id": jetons["client_id"],
        })
        assert nouveaux.status_code == 200

    def test_us290_compte_supprime_coupe_l_acces(self, client, jardin, fabrique):
        jeton = _connecter(client, jardin)["access_token"]
        with fabrique() as db:  # SQLite n'applique pas le CASCADE : seule la ligne du compte part
            db.query(PotagerMembre).filter(PotagerMembre.user_id == jardin["user_id"]).delete()
            db.query(Potager).filter(Potager.proprietaire_id == jardin["user_id"]).update({Potager.proprietaire_id: jardin["autre_id"]})
            db.query(User).filter(User.id == jardin["user_id"]).delete()
            db.commit()
        assert _rpc(client, jeton, "tools/list").status_code == 401

    def test_us290_jeton_d_acces_expire(self, client, jardin, fabrique):
        jeton = _connecter(client, jardin)["access_token"]
        with fabrique() as db:
            db.query(McpJeton).update({McpJeton.expire_le: svc_autorisation._maintenant() - timedelta(seconds=1)})
            db.commit()
        assert _rpc(client, jeton, "tools/list").status_code == 401

    def test_us290_jeton_de_rafraichissement_n_ouvre_pas_mcp(self, client, jardin):
        jetons = _connecter(client, jardin)
        assert _rpc(client, jetons["refresh_token"], "tools/list").status_code == 401


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — Jeton personnel pour les clients de développement
# ═════════════════════════════════════════════════════════════════════════════
class TestCA9JetonPersonnel:

    def _creer(self, client, jardin, **extra) -> dict:
        corps = {"libelle": "Claude Code", "potager_ids": [jardin["mesanges"]]}
        corps.update(extra)
        reponse = client.post("/mcp/jetons-personnels", headers=_pwa(jardin["user_id"]), json=corps)
        assert reponse.status_code == 201, reponse.text
        return reponse.json()

    def test_us290_jeton_personnel_ouvre_le_serveur(self, client, jardin):
        cree = self._creer(client, jardin)
        assert cree["jeton"].startswith("mcpp_")
        assert cree["connexion"]["type"] == "personnel" and cree["connexion"]["portee"] == "lecture"
        assert cree["connexion"]["expire_le"] is not None
        assert _appeler(client, cree["jeton"], "lister_potagers")["isError"] is False

    def test_us290_jeton_personnel_meme_portee(self, client, jardin, outil_ecriture):
        cree = self._creer(client, jardin)
        assert _appeler(client, cree["jeton"], "proposer_test")["content"][0]["text"] == "Écriture non autorisée pour ce connecteur"
        ecrivain = self._creer(client, jardin, ecriture=True)
        assert _appeler(client, ecrivain["jeton"], "proposer_test")["isError"] is False

    def test_us290_jeton_personnel_revocable(self, client, jardin):
        cree = self._creer(client, jardin)
        client.delete(f"/mcp/connexions/{cree['connexion']['id']}", headers=_pwa(jardin["user_id"]))
        assert _rpc(client, cree["jeton"], "tools/list").status_code == 401

    def test_us290_jeton_personnel_exige_un_potager_a_soi(self, client, jardin):
        reponse = client.post("/mcp/jetons-personnels", headers=_pwa(jardin["user_id"]),
                              json={"libelle": "x", "potager_ids": [jardin["etranger"]]})
        assert reponse.status_code == 400

    def test_us290_jeton_personnel_duree_bornee(self, client, jardin):
        reponse = client.post("/mcp/jetons-personnels", headers=_pwa(jardin["user_id"]),
                              json={"libelle": "x", "potager_ids": [jardin["mesanges"]], "duree_jours": 1000})
        assert reponse.status_code == 400

    def test_us290_jeton_personnel_exige_la_session(self, client, jardin):
        reponse = client.post("/mcp/jetons-personnels", json={"libelle": "x", "potager_ids": [jardin["mesanges"]]})
        assert reponse.status_code == 401


# ═════════════════════════════════════════════════════════════════════════════
# Gherkin
# ═════════════════════════════════════════════════════════════════════════════
def test_us290_gherkin_lecture_seule_sur_les_mesanges(client, jardin, fabrique, outil_ecriture):
    """Given un jardinier owner des « Mésanges » ; When il connecte Claude en laissant la
    seule portée « Lecture » ; Then Claude ne liste que la lecture, une écriture forcée est
    refusée avec le bon message, et l'appel figure au journal avec « refus »."""
    jeton = _connecter(client, jardin, potagers=[jardin["mesanges"]])["access_token"]

    outils = _rpc(client, jeton, "tools/list").json()["result"]["tools"]
    assert all(o["annotations"]["readOnlyHint"] for o in outils)

    resultat = _appeler(client, jeton, "proposer_test", {"potager": "Les Mésanges"})
    assert resultat["isError"] is True
    assert resultat["content"][0]["text"] == "Écriture non autorisée pour ce connecteur"
    assert outil_ecriture == []

    ligne = _journal(fabrique)[-1]
    assert (ligne.outil, ligne.resultat, ligne.client) == ("proposer_test", "refus", "Claude")


# ═════════════════════════════════════════════════════════════════════════════
# Structure
# ═════════════════════════════════════════════════════════════════════════════
def test_us290_migration_v69_cree_les_cinq_tables_et_son_rollback():
    migration = (RACINE / "migrations/migration_v69.sql").read_text(encoding="utf-8")
    rollback = (RACINE / "migrations/rollback_v69.sql").read_text(encoding="utf-8")
    for table in ("mcp_clients", "mcp_autorisations", "mcp_jetons", "mcp_codes_autorisation", "mcp_appels"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in migration
        assert f"DROP TABLE IF EXISTS {table}" in rollback
    for modele in (McpClient, McpAutorisation, McpJeton, McpCodeAutorisation, McpAppel):
        assert modele.__tablename__ in migration


def test_us290_aucun_appel_modele_sur_le_canal_mcp():
    """Principe 4 de l'étude : pas de LLM chez nous sur ce canal."""
    for fichier in ("app/services/mcp/serveur.py", "app/services/mcp/outils.py", "app/services/mcp/autorisation.py", "app/api/mcp.py"):
        source = (RACINE / fichier).read_text(encoding="utf-8")
        assert "passerelle" not in source and "groq" not in source.lower()

"""
tests/test_us055_menu_compte.py — [US-055] Menu Compte unifié
------------------------------------------------------------------
Couvre le seul volet backend de l'US : l'endpoint `GET /auth/me`, qui alimente
l'en-tête du menu Compte (identité) et l'état affiché à côté de « Relier
Telegram » (relié / à faire) — CA1.

Le reste de l'US est un regroupement d'UI existante (CA2 à CA6) : il relève de
la validation visuelle du QA-tester, pas d'un test pytest.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import auth as svc_auth
from database.db import Base
from database.models import Potager, PotagerMembre


@pytest.fixture
def _auth_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def app_client(_auth_engine, monkeypatch):
    import main
    TestSessionLocal = sessionmaker(bind=_auth_engine)
    monkeypatch.setattr(main, "SessionLocal", TestSessionLocal)
    main.app.state.limiter.reset()
    with TestClient(main.app) as c:
        yield c


def _compte(engine, email="jardinier@example.com", **champs):
    """Crée un compte web vérifié et renvoie (user_id, access_token)."""
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        user = svc_auth.inscrire_utilisateur(db, email, "motdepasse123")
        for cle, valeur in champs.items():
            setattr(user, cle, valeur)
        db.commit()
        return user.id, svc_auth.creer_access_token(user.id)
    finally:
        db.close()


def _entetes(token):
    return {"Authorization": f"Bearer {token}"}


# ── CA1 — Identité exposée au menu Compte ──────────────────────────────────

def test_us055_ca1_endpoint_protege_par_auth(app_client):
    """Sans access token, aucune identité ne doit fuiter."""
    resp = app_client.get("/auth/me")
    assert resp.status_code == 401


def test_us055_ca1_renvoie_identite_du_compte_connecte(app_client, _auth_engine):
    user_id, token = _compte(_auth_engine, nom="Jean Dupont")

    resp = app_client.get("/auth/me", headers=_entetes(token))

    assert resp.status_code == 200
    corps = resp.json()
    assert corps["id"] == user_id
    assert corps["email"] == "jardinier@example.com"
    assert corps["nom"] == "Jean Dupont"


def test_us055_ca1_nom_absent_renvoye_a_null(app_client, _auth_engine):
    """Le nom est facultatif (compte créé sans) — le front retombe alors sur la
    partie locale de l'e-mail, il ne doit pas recevoir d'erreur."""
    _, token = _compte(_auth_engine)

    corps = app_client.get("/auth/me", headers=_entetes(token)).json()

    assert corps["nom"] is None
    assert corps["email"] == "jardinier@example.com"


# ── CA1 — État de la liaison Telegram (« relié / à faire ») ─────────────────

def test_us055_ca1_telegram_lie_vrai_quand_un_chat_est_associe(app_client, _auth_engine):
    _, token = _compte(_auth_engine, telegram_chat_id=555)

    corps = app_client.get("/auth/me", headers=_entetes(token)).json()

    assert corps["telegram_lie"] is True


def test_us055_ca1_telegram_lie_faux_sans_chat_associe(app_client, _auth_engine):
    _, token = _compte(_auth_engine)

    corps = app_client.get("/auth/me", headers=_entetes(token)).json()

    assert corps["telegram_lie"] is False


def test_us055_ca1_chat_id_telegram_jamais_expose(app_client, _auth_engine):
    """Seul l'état booléen est utile au menu : l'identifiant Telegram lui-même
    n'a pas à circuler côté navigateur."""
    _, token = _compte(_auth_engine, telegram_chat_id=555)

    corps = app_client.get("/auth/me", headers=_entetes(token)).json()

    assert "telegram_chat_id" not in corps
    assert 555 not in corps.values()


def test_us055_ca1_aucun_secret_dans_la_reponse(app_client, _auth_engine):
    """Non-régression sécurité : ni hash de mot de passe, ni token de
    vérification d'e-mail ne doivent transiter par cet endpoint."""
    _, token = _compte(_auth_engine)

    corps = app_client.get("/auth/me", headers=_entetes(token)).json()

    assert set(corps) == {"id", "email", "nom", "telegram_lie"}


# ── CA1 — Identité seule : le menu Compte s'affiche sans potager ────────────

def test_us055_ca1_fonctionne_sans_aucun_potager(app_client, _auth_engine):
    """Le menu Compte (déconnexion, liaison Telegram) doit rester utilisable par
    un compte qui n'appartient encore à aucun potager — jamais le 409
    'no_potager' de get_current_user_ctx (cf. US-046 / CA5)."""
    _, token = _compte(_auth_engine, email="sanspotager@example.com")

    resp = app_client.get("/auth/me", headers=_entetes(token))

    assert resp.status_code == 200
    assert resp.json()["email"] == "sanspotager@example.com"


def test_us055_ca1_identite_isolee_entre_comptes(app_client, _auth_engine):
    """Deux comptes membres du même potager reçoivent chacun leur propre
    identité — non-régression multi-tenant."""
    SessionLocal = sessionmaker(bind=_auth_engine)
    proprietaire_id, token_proprietaire = _compte(_auth_engine, email="owner@example.com", nom="Alice")
    invite_id, token_invite = _compte(_auth_engine, email="invite@example.com", nom="Bob")

    db = SessionLocal()
    potager = Potager(nom="Jardin partagé", proprietaire_id=proprietaire_id)
    db.add(potager)
    db.commit()
    db.add(PotagerMembre(user_id=proprietaire_id, potager_id=potager.id, role="owner"))
    db.add(PotagerMembre(user_id=invite_id, potager_id=potager.id, role="editor"))
    db.commit()
    db.close()

    corps_proprietaire = app_client.get("/auth/me", headers=_entetes(token_proprietaire)).json()
    corps_invite = app_client.get("/auth/me", headers=_entetes(token_invite)).json()

    assert corps_proprietaire["nom"] == "Alice"
    assert corps_invite["nom"] == "Bob"
    assert corps_proprietaire["id"] != corps_invite["id"]

"""
tests/test_us044_authentification_jwt.py — [US-044] Authentification web JWT
-------------------------------------------------------------------------------
Couvre les critères d'acceptance CA1 à CA8 : inscription, connexion, refresh,
garde sur les endpoints métier, distinction token expiré/absent, secret via
env, anti-énumération sur /auth/register, rate-limit basique.
"""
import time
from datetime import timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import config
from app.services import auth as svc_auth
from database.db import Base
from database.models import User, Potager, PotagerMembre


@pytest.fixture
def _auth_engine():
    """Moteur SQLite partagé entre threads — le TestClient exécute les endpoints
    dans un thread différent de celui du test (StaticPool + check_same_thread=False)."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def test_db(_auth_engine):
    """Session DB de test — remplace la fixture globale pour partager le même moteur que le TestClient."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_auth_engine)
    db = SessionLocal()
    yield db
    db.rollback()
    db.close()


@pytest.fixture
def app_client(_auth_engine, monkeypatch):
    """TestClient FastAPI branché sur le moteur SQLite de test (pas de mock)."""
    import main

    TestSessionLocal = sessionmaker(bind=_auth_engine)
    monkeypatch.setattr(main, "SessionLocal", TestSessionLocal)
    main.app.state.limiter.reset()
    with TestClient(main.app) as c:
        yield c


def _creer_utilisateur(test_db, email="jardinier@example.com", mot_de_passe="motdepasse123"):
    user = svc_auth.inscrire_utilisateur(test_db, email, mot_de_passe)
    return user


# ── CA1 — Inscription ──────────────────────────────────────────────────────

def test_us044_ca1_inscription_reussie_hache_le_mot_de_passe(app_client, test_db):
    resp = app_client.post("/auth/register", json={
        "email": "jardinier@example.com",
        "mot_de_passe": "motdepasse123",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "jardinier@example.com"

    user = test_db.query(User).filter(User.email == "jardinier@example.com").first()
    assert user is not None
    assert user.mot_de_passe_hash is not None
    assert user.mot_de_passe_hash != "motdepasse123"  # jamais en clair


def test_us044_ca1_mot_de_passe_trop_court_rejete(app_client):
    resp = app_client.post("/auth/register", json={
        "email": "jardinier@example.com",
        "mot_de_passe": "court",
    })
    assert resp.status_code == 400


def test_us044_ca1_email_invalide_rejete(app_client):
    resp = app_client.post("/auth/register", json={
        "email": "pas-un-email",
        "mot_de_passe": "motdepasse123",
    })
    assert resp.status_code == 400


# ── CA2 — Connexion ─────────────────────────────────────────────────────────

def test_us044_ca2_connexion_reussie_renvoie_access_et_refresh_token(app_client, test_db):
    _creer_utilisateur(test_db)

    resp = app_client.post("/auth/login", json={
        "email": "jardinier@example.com",
        "mot_de_passe": "motdepasse123",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]

    payload_access = jwt.decode(body["access_token"], config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
    assert payload_access["type"] == "access"
    payload_refresh = jwt.decode(body["refresh_token"], config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
    assert payload_refresh["type"] == "refresh"


def test_us044_ca2_connexion_mauvais_mot_de_passe_rejetee(app_client, test_db):
    _creer_utilisateur(test_db)

    resp = app_client.post("/auth/login", json={
        "email": "jardinier@example.com",
        "mot_de_passe": "mauvais",
    })
    assert resp.status_code == 401


def test_us044_ca2_connexion_email_inconnu_rejetee(app_client):
    resp = app_client.post("/auth/login", json={
        "email": "inconnu@example.com",
        "mot_de_passe": "motdepasse123",
    })
    assert resp.status_code == 401


# ── CA3 — Refresh ───────────────────────────────────────────────────────────

def test_us044_ca3_refresh_valide_renvoie_nouvel_access_token(app_client, test_db):
    user = _creer_utilisateur(test_db)
    refresh_token = svc_auth.creer_refresh_token(user.id)

    resp = app_client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    payload = jwt.decode(body["access_token"], config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
    assert payload["type"] == "access"
    assert payload["sub"] == str(user.id)


def test_us044_ca3_refresh_avec_un_access_token_rejete(app_client, test_db):
    """Un access token n'est pas un refresh token valide — types distincts."""
    user = _creer_utilisateur(test_db)
    access_token = svc_auth.creer_access_token(user.id)

    resp = app_client.post("/auth/refresh", json={"refresh_token": access_token})
    assert resp.status_code == 401


# ── CA4 — Garde sur les endpoints métier ───────────────────────────────────

@pytest.mark.parametrize("path", [
    "/cultures", "/stats", "/historique", "/plan", "/godets",
])
def test_us044_ca4_acces_refuse_sans_token(app_client, path):
    resp = app_client.get(path)
    assert resp.status_code == 401


def test_us044_ca4_acces_autorise_avec_token_valide(app_client, test_db):
    user = _creer_utilisateur(test_db)
    # [US-046] /cultures résout désormais un potager réel — l'utilisateur doit en être membre.
    potager = Potager(nom="Potager test", proprietaire_id=user.id)
    test_db.add(potager)
    test_db.commit()
    test_db.add(PotagerMembre(user_id=user.id, potager_id=potager.id, role="owner"))
    test_db.commit()
    access_token = svc_auth.creer_access_token(user.id)

    resp = app_client.get("/cultures", headers={"Authorization": f"Bearer {access_token}"})
    assert resp.status_code == 200


def test_us044_ca4_health_reste_public(app_client):
    resp = app_client.get("/health")
    assert resp.status_code == 200


# ── CA5 — Distinction token expiré / absent / invalide ─────────────────────

def test_us044_ca5_token_absent_renvoie_code_token_missing(app_client):
    resp = app_client.get("/historique")
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "token_missing"


def test_us044_ca5_token_invalide_renvoie_code_token_invalid(app_client):
    resp = app_client.get("/historique", headers={"Authorization": "Bearer ceci-nest-pas-un-jwt"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "token_invalid"


def test_us044_ca5_token_expire_renvoie_code_token_expired(app_client, test_db):
    user = _creer_utilisateur(test_db)
    # Token déjà expiré (durée négative)
    expired_token = svc_auth._creer_token(user.id, "access", timedelta(seconds=-1))

    resp = app_client.get("/historique", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "token_expired"


# ── CA6 — Secret JWT lu depuis l'environnement ──────────────────────────────

def test_us044_ca6_secret_jwt_vient_de_lenvironnement(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "un-secret-different-pour-le-test")
    import importlib
    import config as config_module
    importlib.reload(config_module)
    try:
        assert config_module.JWT_SECRET == "un-secret-different-pour-le-test"
    finally:
        importlib.reload(config_module)  # restaure le secret de test global


# ── CA7 — Double inscription refusée sans énumération exploitable ─────────

def test_us044_ca7_double_inscription_refusee_409(app_client, test_db):
    _creer_utilisateur(test_db)

    resp = app_client.post("/auth/register", json={
        "email": "jardinier@example.com",
        "mot_de_passe": "autremotdepasse1",
    })
    assert resp.status_code == 409
    # Message générique, ne confirme pas explicitement l'existence du compte
    assert "existe" not in resp.json()["detail"].lower()


# ── CA8 — Rate limiting sur /auth/login et /auth/register ─────────────────

def test_us044_ca8_rate_limit_login_bloque_apres_n_tentatives(app_client, test_db):
    _creer_utilisateur(test_db)

    statuses = []
    for _ in range(15):
        resp = app_client.post("/auth/login", json={
            "email": "jardinier@example.com",
            "mot_de_passe": "mauvais",
        })
        statuses.append(resp.status_code)

    assert 429 in statuses


def test_us044_ca8_rate_limit_register_bloque_apres_n_tentatives(app_client):
    statuses = []
    for i in range(10):
        resp = app_client.post("/auth/register", json={
            "email": f"user{i}@example.com",
            "mot_de_passe": "motdepasse123",
        })
        statuses.append(resp.status_code)

    assert 429 in statuses

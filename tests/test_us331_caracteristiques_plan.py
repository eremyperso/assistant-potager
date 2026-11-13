"""
tests/test_us331_caracteristiques_plan.py — [US-331] Lire et modifier les caractéristiques
d'une parcelle dans le plan.

Côté serveur, l'US tient en deux points : le champ « Pépinière » (Non / Froide / Chaude) écrit
les deux colonnes de façon cohérente (CA6), et le « Type » de la parcelle est la forme du plan
(P7), liste fermée servie par le domaine.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import auth as svc_auth
from app.services import parcelles as svc_parcelles
from app.services import potagers as svc_potagers
from database.db import Base
from database.models import Parcelle
from utils.parcelles import create_parcelle


@pytest.fixture
def _engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def client(_engine, monkeypatch):
    from app.api import main
    monkeypatch.setattr(main, "SessionLocal", sessionmaker(bind=_engine))
    main.app.state.limiter.reset()
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def db(_engine):
    session = sessionmaker(bind=_engine)()
    yield session
    session.close()


def _planche(db):
    user = svc_auth.inscrire_utilisateur(db, "jardinier@example.com", "motdepasse123")
    potager = svc_potagers.creer_potager(db, user.id, "Potager de test")
    parcelle = create_parcelle(db, "planche_centrale", superficie_m2=12.0, potager_id=potager.id)
    return user, parcelle


def _patch(client, user, parcelle, corps):
    return client.patch(
        f"/parcelles/{parcelle.id}", json=corps,
        headers={"Authorization": f"Bearer {svc_auth.creer_access_token(user.id)}"},
    )


def test_ca6_froide_ecrit_la_pepiniere_et_son_type(client, db):
    user, parcelle = _planche(db)
    r = _patch(client, user, parcelle, {"est_pepiniere": True, "type_pepiniere": "froide"})
    assert r.status_code == 200
    assert (r.json()["est_pepiniere"], r.json()["type_pepiniere"]) == (True, "froide")
    db.expire_all()
    relue = db.get(Parcelle, parcelle.id)
    assert (relue.est_pepiniere, relue.type_pepiniere) == (True, "froide")


def test_ca6_non_retire_la_pepiniere_et_son_type(client, db):
    user, parcelle = _planche(db)
    _patch(client, user, parcelle, {"est_pepiniere": True, "type_pepiniere": "chaude"})
    r = _patch(client, user, parcelle, {"est_pepiniere": False})
    assert (r.json()["est_pepiniere"], r.json()["type_pepiniere"]) == (False, None)


def test_ca6_un_type_avec_non_est_ignore_plutot_que_contradictoire(client, db):
    user, parcelle = _planche(db)
    r = _patch(client, user, parcelle, {"est_pepiniere": False, "type_pepiniere": "chaude"})
    assert r.status_code == 200
    assert (r.json()["est_pepiniere"], r.json()["type_pepiniere"]) == (False, None)


def test_ca6_un_type_hors_vocabulaire_est_refuse(client, db):
    user, parcelle = _planche(db)
    r = _patch(client, user, parcelle, {"est_pepiniere": True, "type_pepiniere": "tiede"})
    assert r.status_code == 400


def test_p7_le_type_est_la_forme_du_plan(client, db):
    user, parcelle = _planche(db)
    r = _patch(client, user, parcelle, {"forme": "bac"})
    assert r.status_code == 200
    assert r.json()["geometrie"]["forme"] == "bac"


def test_p7_la_liste_des_types_vient_du_domaine():
    options = svc_parcelles.vocabulaires_fiche()["forme"]["options"]
    assert [o["valeur"] for o in options] == ["planche", "bac", "butte", "serre"]

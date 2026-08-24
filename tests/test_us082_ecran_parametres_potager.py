"""
tests/test_us082_ecran_parametres_potager.py — [US-082] Écran « Paramètres du
potager » — volet backend
------------------------------------------------------------------------------
Couvre CA7 (nouvel endpoint `GET /potagers/{id}`, réservé aux membres, refus
générique sans révéler l'existence du potager) et CA2/CA6/CA8 (champs exposés,
lecture ouverte à tout rôle, potager archivé toujours consultable).

CA1, CA3, CA4, CA5 (composition de l'écran, réutilisation du design system et
de GestionMembres, container queries) sont portés par le composant frontend
`ParametresPotager.jsx` — pas de logique serveur à couvrir ici.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import auth as svc_auth
from app.services import potager_actif as svc_potager_actif
from app.services import potagers as svc_potagers
from database.db import Base
from database.models import PotagerMembre, User


def _creer_user(db, email="jardinier@example.com", **kwargs):
    user = User(email=email, mot_de_passe_hash="x", **kwargs)
    db.add(user)
    db.commit()
    return user


# ── CA7 — Service `obtenir_potager` ─────────────────────────────────────────

def test_ca7_owner_obtient_le_detail_complet(test_db):
    owner = _creer_user(test_db)
    potager = svc_potagers.creer_potager(
        test_db, owner.id, "Jardin de Vitry", ville="Vitry-sur-Seine", latitude=48.787, longitude=2.393,
    )

    detail = svc_potager_actif.obtenir_potager(test_db, owner.id, potager.id)

    assert detail == {
        "id": potager.id,
        "nom": "Jardin de Vitry",
        "ville": "Vitry-sur-Seine",
        "latitude": pytest.approx(48.787),
        "longitude": pytest.approx(2.393),
        "etat": "actif",
        "role": "owner",
        "nb_parcelles": 0,
        "nb_membres": 1,
    }


def test_ca6_un_editor_obtient_aussi_le_detail(test_db):
    """[CA6] La lecture reste ouverte à tout membre, quel que soit son rôle."""
    owner = _creer_user(test_db, email="owner@example.com")
    editeur = _creer_user(test_db, email="editor@example.com")
    potager = svc_potagers.creer_potager(test_db, owner.id, "Jardin partagé")
    test_db.add(PotagerMembre(user_id=editeur.id, potager_id=potager.id, role="editor"))
    test_db.commit()

    detail = svc_potager_actif.obtenir_potager(test_db, editeur.id, potager.id)

    assert detail is not None
    assert detail["role"] == "editor"
    assert detail["nb_membres"] == 2


def test_ca7_non_membre_ne_recoit_rien(test_db):
    owner = _creer_user(test_db, email="owner@example.com")
    inconnu = _creer_user(test_db, email="inconnu@example.com")
    potager = svc_potagers.creer_potager(test_db, owner.id, "Jardin privé")

    assert svc_potager_actif.obtenir_potager(test_db, inconnu.id, potager.id) is None


def test_ca7_potager_inexistant_ne_recoit_rien(test_db):
    user = _creer_user(test_db)
    assert svc_potager_actif.obtenir_potager(test_db, user.id, 999_999) is None


def test_ca7_potager_supprime_traite_comme_inexistant_meme_pour_le_owner(test_db):
    """[CA7] Un potager `supprime` (US-084) reste invisible en toutes circonstances
    — même règle que `lister_potagers_utilisateur` (US-080)."""
    owner = _creer_user(test_db)
    potager = svc_potagers.creer_potager(test_db, owner.id, "Jardin voué à disparaître")
    potager.etat = svc_potager_actif.ETAT_SUPPRIME
    test_db.commit()

    assert svc_potager_actif.obtenir_potager(test_db, owner.id, potager.id) is None


def test_ca8_potager_archive_reste_consultable(test_db):
    owner = _creer_user(test_db)
    potager = svc_potagers.creer_potager(test_db, owner.id, "Jardin d'hiver")
    potager.etat = svc_potager_actif.ETAT_ARCHIVE
    test_db.commit()

    detail = svc_potager_actif.obtenir_potager(test_db, owner.id, potager.id)

    assert detail is not None
    assert detail["etat"] == "archive"


# ── CA7 — Endpoint web `GET /potagers/{id}` ─────────────────────────────────

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


def _creer_compte_web(db, email="jardinier@example.com", mot_de_passe="motdepasse123"):
    return svc_auth.inscrire_utilisateur(db, email, mot_de_passe)


def _auth_header(user_id):
    return {"Authorization": f"Bearer {svc_auth.creer_access_token(user_id)}"}


def test_get_potager_membre_recoit_le_detail(app_client, _auth_engine):
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    user = _creer_compte_web(db)
    headers = _auth_header(user.id)
    db.close()

    resp = app_client.post(
        "/potagers",
        json={"nom": "Jardin Vitry", "ville": "Vitry-sur-Seine", "latitude": 48.787, "longitude": 2.393},
        headers=headers,
    )
    potager_id = resp.json()["id"]

    resp = app_client.get(f"/potagers/{potager_id}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["nom"] == "Jardin Vitry"
    assert body["ville"] == "Vitry-sur-Seine"
    assert body["etat"] == "actif"
    assert body["role"] == "owner"
    assert body["nb_parcelles"] == 0
    assert body["nb_membres"] == 1


def test_ca7_get_potager_non_membre_recoit_un_refus_generique(app_client, _auth_engine):
    """[CA7] Ni 404 ni message distinctif : le non-membre n'apprend rien de plus
    qu'un simple refus, comme GET /potagers/{id}/membres."""
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    owner = _creer_compte_web(db, email="owner@example.com")
    inconnu = _creer_compte_web(db, email="inconnu@example.com")
    headers_owner = _auth_header(owner.id)
    headers_inconnu = _auth_header(inconnu.id)
    db.close()

    resp = app_client.post("/potagers", json={"nom": "Jardin privé"}, headers=headers_owner)
    potager_id = resp.json()["id"]

    resp = app_client.get(f"/potagers/{potager_id}", headers=headers_inconnu)
    assert resp.status_code == 403


def test_ca7_get_potager_inexistant_recoit_le_meme_refus(app_client, _auth_engine):
    """[CA7] Même statut/message qu'un potager existant dont on n'est pas membre
    — un potager inexistant ne se distingue pas d'un accès refusé."""
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    owner = _creer_compte_web(db, email="owner@example.com")
    inconnu = _creer_compte_web(db, email="inconnu@example.com")
    headers_owner = _auth_header(owner.id)
    headers_inconnu = _auth_header(inconnu.id)
    db.close()

    resp_potager = app_client.post("/potagers", json={"nom": "Jardin"}, headers=headers_owner)
    potager_id = resp_potager.json()["id"]

    resp_inexistant = app_client.get("/potagers/999999", headers=headers_inconnu)
    resp_non_membre = app_client.get(f"/potagers/{potager_id}", headers=headers_inconnu)

    assert resp_inexistant.status_code == 403
    assert resp_inexistant.json()["detail"] == resp_non_membre.json()["detail"]


def test_get_potager_sans_authentification_refuse(app_client):
    resp = app_client.get("/potagers/1")
    assert resp.status_code in (401, 403)

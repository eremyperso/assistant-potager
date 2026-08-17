"""
tests/test_us074_localisation_potager.py — [US-074] Localiser un potager via une
recherche de ville unifiée
------------------------------------------------------------------------------------
Couvre CA2 (colonne `Potager.ville`), CA3 (`POST /potagers` accepte `ville`),
CA4 (`PATCH /potagers/{id}`, réservé au owner), CA5 (pré-remplissage via
`GET /potagers`) et CA6 (jamais de valeur inventée pour un potager non
localisé). CA1 et CA7 (module de recherche, messages d'échec) sont portés par
le composant frontend `VilleSearch` — pas de logique serveur à couvrir ici.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import auth as svc_auth
from app.services import potagers as svc_potagers
from app.services.permissions import PermissionInsuffisanteError
from database.db import Base
from database.models import PotagerMembre, User


def _creer_user(db, email="jardinier@example.com", **kwargs):
    user = User(email=email, mot_de_passe_hash="x", **kwargs)
    db.add(user)
    db.commit()
    return user


# ── CA2, CA3 — Création avec localisation ───────────────────────────────────

def test_ca2_ca3_creer_potager_stocke_la_ville(test_db):
    user = _creer_user(test_db)

    potager = svc_potagers.creer_potager(
        test_db, user.id, "Jardin Vitry", ville="Vitry-sur-Seine", latitude=48.787, longitude=2.393,
    )

    assert potager.ville == "Vitry-sur-Seine"
    assert potager.latitude == 48.787
    assert potager.longitude == 2.393


def test_ca6_creer_potager_sans_localisation_ne_stocke_rien_par_defaut(test_db):
    """[CA6] Aucune valeur inventée : ville/latitude/longitude restent `None`."""
    user = _creer_user(test_db)

    potager = svc_potagers.creer_potager(test_db, user.id, "Jardin sans ville")

    assert potager.ville is None
    assert potager.latitude is None
    assert potager.longitude is None


# ── CA4 — Modification d'un potager existant ────────────────────────────────

def test_ca4_owner_peut_localiser_un_potager_existant(test_db):
    """Scénario Gherkin : localiser un potager existant, sans localisation."""
    owner = _creer_user(test_db)
    potager = svc_potagers.creer_potager(test_db, owner.id, "Jardin ancien")
    assert potager.ville is None

    resultat = svc_potagers.modifier_potager(
        test_db, owner.id, potager.id, ville="Lyon", latitude=45.764, longitude=4.836,
    )

    assert resultat.ville == "Lyon"
    assert resultat.latitude == 45.764
    assert resultat.longitude == 4.836
    assert resultat.nom == "Jardin ancien"  # non modifié


def test_ca4_modification_partielle_ne_touche_pas_les_champs_omis(test_db):
    owner = _creer_user(test_db)
    potager = svc_potagers.creer_potager(
        test_db, owner.id, "Jardin Nord", ville="Lille", latitude=50.629, longitude=3.057,
    )

    svc_potagers.modifier_potager(test_db, owner.id, potager.id, nom="Jardin Nord (renommé)")

    test_db.refresh(potager)
    assert potager.nom == "Jardin Nord (renommé)"
    assert potager.ville == "Lille"
    assert potager.latitude == 50.629
    assert potager.longitude == 3.057


def test_ca4_non_owner_ne_peut_pas_modifier(test_db):
    """Scénario Gherkin : un membre non-owner ne peut pas modifier la localisation."""
    owner = _creer_user(test_db, email="owner@example.com")
    editeur = _creer_user(test_db, email="editor@example.com")
    potager = svc_potagers.creer_potager(test_db, owner.id, "Jardin partagé")
    test_db.add(PotagerMembre(user_id=editeur.id, potager_id=potager.id, role="editor"))
    test_db.commit()

    with pytest.raises(PermissionInsuffisanteError):
        svc_potagers.modifier_potager(test_db, editeur.id, potager.id, ville="Lyon")


def test_ca4_utilisateur_hors_potager_ne_peut_pas_modifier(test_db):
    owner = _creer_user(test_db, email="owner@example.com")
    inconnu = _creer_user(test_db, email="inconnu@example.com")
    potager = svc_potagers.creer_potager(test_db, owner.id, "Jardin privé")

    with pytest.raises(PermissionInsuffisanteError):
        svc_potagers.modifier_potager(test_db, inconnu.id, potager.id, ville="Lyon")


# ── Endpoints web ────────────────────────────────────────────────────────────

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


def test_post_potagers_avec_ville(app_client, _auth_engine):
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
    assert resp.status_code == 201
    assert resp.json()["ville"] == "Vitry-sur-Seine"

    resp = app_client.get("/potagers", headers=headers)
    potager = resp.json()["potagers"][0]
    assert potager["ville"] == "Vitry-sur-Seine"
    assert potager["latitude"] == pytest.approx(48.787)
    assert potager["longitude"] == pytest.approx(2.393)


def test_ca6_get_potagers_sans_localisation_renvoie_null(app_client, _auth_engine):
    """[CA6] Jamais de "0, 0" par défaut — les champs restent `null`."""
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    user = _creer_compte_web(db)
    headers = _auth_header(user.id)
    db.close()

    app_client.post("/potagers", json={"nom": "Jardin sans ville"}, headers=headers)

    resp = app_client.get("/potagers", headers=headers)
    potager = resp.json()["potagers"][0]
    assert potager["ville"] is None
    assert potager["latitude"] is None
    assert potager["longitude"] is None


def test_ca4_patch_potagers_owner_localise_le_potager(app_client, _auth_engine):
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    user = _creer_compte_web(db)
    headers = _auth_header(user.id)
    db.close()

    resp = app_client.post("/potagers", json={"nom": "Jardin ancien"}, headers=headers)
    potager_id = resp.json()["id"]

    resp = app_client.patch(
        f"/potagers/{potager_id}",
        json={"ville": "Marseille", "latitude": 43.296, "longitude": 5.37},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ville"] == "Marseille"
    assert body["latitude"] == pytest.approx(43.296)
    assert body["longitude"] == pytest.approx(5.37)
    assert body["nom"] == "Jardin ancien"


def test_ca4_patch_potagers_403_si_non_owner(app_client, _auth_engine):
    """Scénario Gherkin : un membre non-owner ne peut pas modifier la localisation."""
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    owner = _creer_compte_web(db, email="owner@example.com")
    editeur = _creer_compte_web(db, email="editor@example.com")
    owner_headers = _auth_header(owner.id)
    editeur_headers = _auth_header(editeur.id)
    db.close()

    resp = app_client.post("/potagers", json={"nom": "Jardin partagé"}, headers=owner_headers)
    potager_id = resp.json()["id"]
    code = app_client.post(
        f"/potagers/{potager_id}/invitations", json={"role_propose": "editor"}, headers=owner_headers,
    ).json()["code"]
    app_client.post(f"/invitations/{code}/accepter", headers=editeur_headers)

    resp = app_client.patch(f"/potagers/{potager_id}", json={"ville": "Lyon"}, headers=editeur_headers)
    assert resp.status_code == 403


def test_patch_potagers_nom_vide_refuse(app_client, _auth_engine):
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    user = _creer_compte_web(db)
    headers = _auth_header(user.id)
    db.close()

    resp = app_client.post("/potagers", json={"nom": "Jardin"}, headers=headers)
    potager_id = resp.json()["id"]

    resp = app_client.patch(f"/potagers/{potager_id}", json={"nom": "   "}, headers=headers)
    assert resp.status_code == 400

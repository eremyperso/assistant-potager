"""
tests/test_us058_onboarding_premier_potager.py — [US-058] Assistant de création
du premier potager (4 étapes)
------------------------------------------------------------------------------------
L'assistant lui-même (`frontend/src/views/Onboarding.jsx`) est un parcours
purement visuel/local (CA1-CA4, CA6) : aucune donnée n'est envoyée avant la
validation finale du récapitulatif. Ce fichier couvre donc la persistance
réelle côté serveur (CA5) :
- `Parcelle.type_sol` (migration_v28), colonne informative seule ;
- `utils.parcelles.create_parcelle` étendue (est_pepiniere/type_sol dès la
  création) ;
- le nouvel endpoint `POST /parcelles` (première porte d'entrée HTTP pour la
  création de parcelle, jusqu'ici réservée au bot Telegram).

CA2 (rejoindre un potager existant par code) réutilise `accepter_invitation`
sans changement — déjà couvert par `test_us048_invitations_onboarding.py`.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import auth as svc_auth
from app.services import parcelles as svc_parcelles
from app.services import potagers as svc_potagers
from app.services.context import TenantContext
from app.services.permissions import PermissionInsuffisanteError
from database.db import Base
from database.models import Parcelle, PotagerMembre, User
from utils.parcelles import create_parcelle


def _creer_user(db, email="jardinier@example.com", **kwargs):
    user = User(email=email, mot_de_passe_hash="x", **kwargs)
    db.add(user)
    db.commit()
    return user


# ── CA3 — Parcelle.type_sol / création avec nature d'espace + sol ──────────────

def test_ca3_create_parcelle_stocke_est_pepiniere_et_type_sol(test_db):
    parcelle = create_parcelle(
        test_db, "Planche du fond",
        exposition="Ouest", superficie_m2=12.5,
        est_pepiniere=True, type_sol="Argileux",
    )

    assert parcelle.exposition == "Ouest"
    assert parcelle.superficie_m2 == 12.5
    assert parcelle.est_pepiniere is True
    assert parcelle.type_sol == "Argileux"


def test_ca3_create_parcelle_sans_type_sol_ni_pepiniere_garde_les_defauts(test_db):
    """[CA3] Champs informatifs facultatifs — comportement historique inchangé
    pour les appelants (bot.py) qui ne les passent pas."""
    parcelle = create_parcelle(test_db, "Planche historique")

    assert parcelle.est_pepiniere is False
    assert parcelle.type_sol is None


def test_type_sol_n_est_pas_exploite_par_le_calcul_de_stock(test_db):
    """[§5.8] Colonne purement informative — n'affecte ni est_pepiniere (déjà
    testé) ni aucune autre colonne de calcul."""
    parcelle = create_parcelle(test_db, "Planche argileuse", type_sol="Argileux")
    test_db.refresh(parcelle)

    # Seule la colonne type_sol porte l'information — le reste du modèle
    # (utilisé par utils.stock) est inchangé.
    assert isinstance(parcelle, Parcelle)
    assert parcelle.type_sol == "Argileux"
    assert parcelle.actif is True


# ── CA5 — app/services/parcelles.creer_parcelle (garde de rôle) ────────────────

def test_ca5_creer_parcelle_service_cree_avec_potager_id_du_contexte(test_db):
    owner = _creer_user(test_db)
    potager = svc_potagers.creer_potager(test_db, owner.id, "Potager de test")
    ctx = TenantContext(user_id=owner.id, potager_id=potager.id, role="owner")

    parcelle = svc_parcelles.creer_parcelle(
        test_db, ctx, "Planche du fond",
        exposition="Est", superficie_m2=8.0, est_pepiniere=False, type_sol="Limoneux",
    )

    assert parcelle.potager_id == potager.id
    assert parcelle.type_sol == "Limoneux"


def test_ca5_creer_parcelle_refuse_role_lecteur(test_db):
    """[Défense en profondeur] Un rôle lecteur ne peut pas créer de parcelle —
    hors du parcours normal de l'assistant (l'utilisateur y est toujours owner
    juste après avoir créé son potager), mais la garde reste testée."""
    owner = _creer_user(test_db, email="owner@example.com")
    lecteur = _creer_user(test_db, email="lecteur@example.com")
    potager = svc_potagers.creer_potager(test_db, owner.id, "Potager partagé")
    test_db.add(PotagerMembre(user_id=lecteur.id, potager_id=potager.id, role="lecteur"))
    test_db.commit()
    ctx = TenantContext(user_id=lecteur.id, potager_id=potager.id, role="lecteur")

    with pytest.raises(PermissionInsuffisanteError):
        svc_parcelles.creer_parcelle(test_db, ctx, "Planche interdite")


def test_ca5_creer_parcelle_doublon_leve_valueerror(test_db):
    owner = _creer_user(test_db)
    potager = svc_potagers.creer_potager(test_db, owner.id, "Potager de test")
    ctx = TenantContext(user_id=owner.id, potager_id=potager.id, role="owner")
    svc_parcelles.creer_parcelle(test_db, ctx, "Planche du fond")

    with pytest.raises(ValueError):
        svc_parcelles.creer_parcelle(test_db, ctx, "Planche du fond")


# ── Endpoints web — POST /potagers puis POST /parcelles ────────────────────────

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


def test_scenario_parcours_complet_potager_et_parcelle_persistes_ensemble(app_client, _auth_engine):
    """Scénario Gherkin « Parcours complet » : POST /potagers (avec localisation)
    puis POST /parcelles créent le potager (actif, owner) et sa première parcelle
    en une seule validation finale (CA5)."""
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    user = _creer_compte_web(db)
    headers = _auth_header(user.id)
    db.close()

    resp = app_client.post(
        "/potagers",
        json={"nom": "Potager de Rémy", "ville": "Argenteuil", "latitude": 48.95, "longitude": 2.25},
        headers=headers,
    )
    assert resp.status_code == 201
    potager_id = resp.json()["id"]

    resp = app_client.post(
        "/parcelles",
        json={
            "nom": "Planche du fond", "exposition": "Ouest", "superficie_m2": 12.5,
            "est_pepiniere": True, "type_sol": "Argileux",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["nom"] == "Planche du fond"
    assert body["exposition"] == "Ouest"
    assert body["superficie_m2"] == pytest.approx(12.5)
    assert body["est_pepiniere"] is True
    assert body["type_sol"] == "Argileux"

    # Le potager fraîchement créé est bien le potager actif (CA5) : la parcelle
    # a donc été rattachée sans avoir à le préciser explicitement.
    resp = app_client.get("/potagers", headers=headers)
    potager = resp.json()["potagers"][0]
    assert potager["id"] == potager_id
    assert potager["actif"] is True
    assert potager["role"] == "owner"
    assert potager["nb_parcelles"] == 1


def test_scenario_parcours_minimal_potager_sans_parcelle(app_client, _auth_engine):
    """Scénario Gherkin « Parcours minimal » : seul le nom du potager est fourni,
    aucun appel à POST /parcelles — le potager existe sans aucune parcelle."""
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    user = _creer_compte_web(db)
    headers = _auth_header(user.id)
    db.close()

    resp = app_client.post("/potagers", json={"nom": "Potager minimal"}, headers=headers)
    assert resp.status_code == 201

    resp = app_client.get("/potagers", headers=headers)
    potager = resp.json()["potagers"][0]
    assert potager["nom"] == "Potager minimal"
    assert potager["nb_parcelles"] == 0


def test_post_parcelles_nom_vide_refuse(app_client, _auth_engine):
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    user = _creer_compte_web(db)
    headers = _auth_header(user.id)
    db.close()

    app_client.post("/potagers", json={"nom": "Potager"}, headers=headers)

    resp = app_client.post("/parcelles", json={"nom": "   "}, headers=headers)
    assert resp.status_code == 400


def test_post_parcelles_doublon_409(app_client, _auth_engine):
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    user = _creer_compte_web(db)
    headers = _auth_header(user.id)
    db.close()

    app_client.post("/potagers", json={"nom": "Potager"}, headers=headers)
    app_client.post("/parcelles", json={"nom": "Planche du fond"}, headers=headers)

    resp = app_client.post("/parcelles", json={"nom": "Planche du fond"}, headers=headers)
    assert resp.status_code == 409


def test_post_parcelles_sans_potager_actif_renvoie_409_no_potager(app_client, _auth_engine):
    """Défense en profondeur : sans potager (n'arrive jamais dans le parcours de
    l'assistant, où POST /potagers précède toujours POST /parcelles), l'endpoint
    échoue explicitement plutôt que de créer une parcelle orpheline."""
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    user = _creer_compte_web(db)
    headers = _auth_header(user.id)
    db.close()

    resp = app_client.post("/parcelles", json={"nom": "Planche du fond"}, headers=headers)
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "no_potager"

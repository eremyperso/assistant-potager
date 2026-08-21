"""
tests/test_us081_creer_potager_additionnel.py — [US-081] Créer un potager
additionnel depuis la PWA
--------------------------------------------------------------------------------
Volet serveur de l'US : CA4 (`creer_potager` accepte un paramètre d'activation,
création atomique, owner, état `actif`), CA5 (comportement après création avec
et sans bascule, vu de l'API) et CA7 (nom vide refusé, nom en double autorisé).

CA1, CA2, CA3, CA6, CA8 et le CA type portent sur l'interface : ils sont
verrouillés mécaniquement par `frontend/src/lib/us081_creer_potager.test.js`
(`npm test`) et validés visuellement par le QA.
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
from database.models import Potager, PotagerMembre, User


def _creer_user(db, email="jardinier@example.com", **kwargs):
    user = User(email=email, mot_de_passe_hash="x", **kwargs)
    db.add(user)
    db.commit()
    return user


# ── CA4 — Paramètre d'activation, création atomique ───────────────────────

def test_us081_ca4_creation_bascule_par_defaut(test_db):
    """[CA4] Valeur par défaut inchangée : l'onboarding US-058 ne bouge pas."""
    user = _creer_user(test_db)
    user_id = user.id

    potager = svc_potagers.creer_potager(test_db, user_id, "Jardin de Vitry")

    recharge = test_db.query(User).filter(User.id == user_id).first()
    assert recharge.potager_actif_id == potager.id


def test_us081_ca4_creation_sans_bascule_laisse_le_potager_courant(test_db):
    """Scénario Gherkin « Créer un potager sans basculer dessus »."""
    user = _creer_user(test_db)
    user_id = user.id
    principal = svc_potagers.creer_potager(test_db, user_id, "Jardin principal")

    nouveau = svc_potagers.creer_potager(
        test_db, user_id, "Jardin de mes parents", activer=False
    )

    recharge = test_db.query(User).filter(User.id == user_id).first()
    assert recharge.potager_actif_id == principal.id
    assert nouveau.id != principal.id


def test_us081_ca4_createur_toujours_owner_et_potager_actif(test_db):
    """[CA4] Quelle que soit la bascule : owner, état `actif` (US-080), et
    création atomique — le potager existe complet ou pas du tout."""
    user = _creer_user(test_db)
    svc_potagers.creer_potager(test_db, user.id, "Jardin principal")

    nouveau = svc_potagers.creer_potager(test_db, user.id, "Jardin de Bretagne", activer=False)

    assert nouveau.etat == "actif"
    assert nouveau.archive_le is None and nouveau.supprime_le is None
    membre = (
        test_db.query(PotagerMembre)
        .filter(PotagerMembre.potager_id == nouveau.id, PotagerMembre.user_id == user.id)
        .first()
    )
    assert membre is not None and membre.role == "owner"


def test_us081_ca4_premier_potager_devient_actif_meme_sans_bascule(test_db):
    """Edge case : `activer=False` sur un compte sans aucun potager le laisserait
    coincé sur l'onboarding (409 « aucun potager », US-046 / CA5)."""
    user = _creer_user(test_db)
    user_id = user.id

    potager = svc_potagers.creer_potager(test_db, user_id, "Premier jardin", activer=False)

    recharge = test_db.query(User).filter(User.id == user_id).first()
    assert recharge.potager_actif_id == potager.id


def test_us081_ca5_le_nouveau_potager_apparait_dans_la_liste(test_db):
    """[CA5] Sans bascule, le potager créé est bien présent au prochain affichage."""
    user = _creer_user(test_db)
    svc_potagers.creer_potager(test_db, user.id, "Jardin principal")
    nouveau = svc_potagers.creer_potager(test_db, user.id, "Jardin de Bretagne", activer=False)

    ids = [p.id for p in svc_potager_actif.lister_potagers_utilisateur(test_db, user.id)]

    assert nouveau.id in ids


def test_us081_creation_sans_localisation_ne_stocke_rien(test_db):
    """Scénario Gherkin « Création sans localisation » : aucune valeur inventée."""
    user = _creer_user(test_db)

    potager = svc_potagers.creer_potager(test_db, user.id, "Jardin sans ville", activer=False)

    assert potager.ville is None
    assert potager.latitude is None
    assert potager.longitude is None


# ── CA7 — Nom en double autorisé côté serveur ─────────────────────────────

def test_us081_ca7_nom_identique_autorise(test_db):
    """[CA7] Deux jardins peuvent légitimement porter le même nom : le serveur
    ne bloque pas, l'avertissement est purement informatif (côté interface)."""
    user = _creer_user(test_db)
    premier = svc_potagers.creer_potager(test_db, user.id, "Jardin")

    second = svc_potagers.creer_potager(test_db, user.id, "Jardin", activer=False)

    assert second.id != premier.id
    assert test_db.query(Potager).filter(Potager.nom == "Jardin").count() == 2


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


def _compte_avec_potager(engine, nom="Jardin de Vitry"):
    db = sessionmaker(bind=engine)()
    user = svc_auth.inscrire_utilisateur(db, "jardinier@example.com", "motdepasse123")
    potager = svc_potagers.creer_potager(db, user.id, nom)
    ids = (user.id, potager.id)
    db.close()
    return ids


def _auth_header(user_id):
    return {"Authorization": f"Bearer {svc_auth.creer_access_token(user_id)}"}


def test_us081_ca4_post_potagers_avec_bascule(app_client, _auth_engine):
    """Scénario Gherkin « Créer un second potager et basculer dessus »."""
    user_id, principal_id = _compte_avec_potager(_auth_engine)

    resp = app_client.post(
        "/potagers",
        json={"nom": "Jardin de Bretagne", "ville": "Quimper",
              "latitude": 47.996, "longitude": -4.098, "activer": True},
        headers=_auth_header(user_id),
    )

    assert resp.status_code == 201
    corps = resp.json()
    assert corps["actif"] is True
    assert corps["etat"] == "actif"
    assert corps["ville"] == "Quimper"

    potagers = app_client.get("/potagers", headers=_auth_header(user_id)).json()["potagers"]
    actif = next(p for p in potagers if p["actif"])
    assert actif["id"] == corps["id"] and actif["role"] == "owner"


def test_us081_ca3_ca5_post_potagers_sans_bascule(app_client, _auth_engine):
    """[CA3, CA5] Case décochée : le potager actif de l'utilisateur ne bouge pas,
    mais le nouveau potager apparaît bien dans la liste."""
    user_id, principal_id = _compte_avec_potager(_auth_engine)

    resp = app_client.post(
        "/potagers",
        json={"nom": "Jardin de mes parents", "activer": False},
        headers=_auth_header(user_id),
    )

    assert resp.status_code == 201
    assert resp.json()["actif"] is False

    potagers = app_client.get("/potagers", headers=_auth_header(user_id)).json()["potagers"]
    assert next(p for p in potagers if p["actif"])["id"] == principal_id
    assert resp.json()["id"] in [p["id"] for p in potagers]


def test_us081_ca4_post_potagers_sans_champ_activer_bascule(app_client, _auth_engine):
    """[CA4] Non-régression US-058 : l'assistant d'onboarding n'envoie pas
    `activer` et doit continuer à basculer."""
    user_id, principal_id = _compte_avec_potager(_auth_engine)

    resp = app_client.post(
        "/potagers", json={"nom": "Jardin sans champ activer"}, headers=_auth_header(user_id)
    )

    assert resp.status_code == 201
    assert resp.json()["actif"] is True


@pytest.mark.parametrize("nom", ["", "   ", "\t\n"])
def test_us081_ca7_post_potagers_nom_vide_refuse(app_client, _auth_engine, nom):
    """Scénario Gherkin « Nom vide refusé » — garde serveur, en plus du client."""
    user_id, principal_id = _compte_avec_potager(_auth_engine)

    resp = app_client.post("/potagers", json={"nom": nom}, headers=_auth_header(user_id))

    assert resp.status_code == 400
    potagers = app_client.get("/potagers", headers=_auth_header(user_id)).json()["potagers"]
    assert len(potagers) == 1  # rien n'a été créé


def test_us081_ca7_post_potagers_nom_en_double_accepte(app_client, _auth_engine):
    user_id, _ = _compte_avec_potager(_auth_engine, nom="Jardin")

    resp = app_client.post(
        "/potagers", json={"nom": "Jardin", "activer": False}, headers=_auth_header(user_id)
    )

    assert resp.status_code == 201
    potagers = app_client.get("/potagers", headers=_auth_header(user_id)).json()["potagers"]
    assert [p["nom"] for p in potagers] == ["Jardin", "Jardin"]

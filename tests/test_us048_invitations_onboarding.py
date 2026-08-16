"""
tests/test_us048_invitations_onboarding.py — [US-048] Invitations & onboarding self-service
--------------------------------------------------------------------------------------------
Couvre CA1 à CA8 : création de potager (owner + potager actif), invitation par
code TTL (garde de rôle owner), acceptation (succès / code invalide / expiré /
déjà utilisé / déjà membre), retrait d'un membre et invalidation immédiate de
son potager actif (CA6), le tout au niveau service (app/services/potagers.py)
et au niveau endpoint FastAPI (self-service de bout en bout, CA7).
"""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import auth as svc_auth
from app.services import potagers as svc_potagers
from app.services.permissions import PermissionInsuffisanteError
from database.db import Base
from database.models import Invitation, Potager, PotagerMembre, User


def _creer_user(db, email="jardinier@example.com", **kwargs):
    user = User(email=email, mot_de_passe_hash="x", **kwargs)
    db.add(user)
    db.commit()
    return user


def _creer_potager(db, nom, proprietaire_id, membre_id=None, role="owner"):
    potager = Potager(nom=nom, proprietaire_id=proprietaire_id)
    db.add(potager)
    db.commit()
    db.add(PotagerMembre(user_id=membre_id or proprietaire_id, potager_id=potager.id, role=role))
    db.commit()
    return potager


# ── CA1, CA2 — Création d'un potager ────────────────────────────────────────

def test_us048_ca1_creer_potager_devient_owner_et_potager_actif(test_db):
    user = _creer_user(test_db)

    potager = svc_potagers.creer_potager(test_db, user.id, "Jardin Nord", latitude=48.8, longitude=2.3)

    membre = (
        test_db.query(PotagerMembre)
        .filter(PotagerMembre.user_id == user.id, PotagerMembre.potager_id == potager.id)
        .first()
    )
    assert membre is not None
    assert membre.role == "owner"

    test_db.refresh(user)
    assert user.potager_actif_id == potager.id


def test_us048_ca2_creer_potager_stocke_la_localisation(test_db):
    user = _creer_user(test_db)

    potager = svc_potagers.creer_potager(test_db, user.id, "Jardin Sud", latitude=43.6, longitude=1.4)

    assert potager.latitude == 43.6
    assert potager.longitude == 1.4


# ── CA3 — Invitation par un owner ───────────────────────────────────────────

def test_us048_ca3_owner_peut_inviter_avec_role_propose(test_db):
    owner = _creer_user(test_db)
    potager = _creer_potager(test_db, "Jardin", owner.id)

    invitation = svc_potagers.creer_invitation(test_db, owner.id, potager.id, "editor")

    assert 6 <= len(invitation.code) <= 8
    assert invitation.code.isalnum()
    assert invitation.potager_id == potager.id
    assert invitation.role_propose == "editor"
    assert invitation.utilisee_le is None
    delta = invitation.expire_le - invitation.cree_le
    assert timedelta(days=6) < delta <= timedelta(days=7, seconds=5)


def test_us048_ca3_non_owner_ne_peut_pas_inviter(test_db):
    owner = _creer_user(test_db, email="owner@example.com")
    editeur = _creer_user(test_db, email="editor@example.com")
    potager = _creer_potager(test_db, "Jardin", owner.id, membre_id=editeur.id, role="editor")

    with pytest.raises(PermissionInsuffisanteError):
        svc_potagers.creer_invitation(test_db, editeur.id, potager.id, "lecteur")


def test_us048_ca3_role_propose_invalide_refuse(test_db):
    owner = _creer_user(test_db)
    potager = _creer_potager(test_db, "Jardin", owner.id)

    with pytest.raises(svc_potagers.RoleInvalideError):
        svc_potagers.creer_invitation(test_db, owner.id, potager.id, "owner")


# ── CA4 — Acceptation d'une invitation ──────────────────────────────────────

def test_us048_ca4_acceptation_ajoute_le_membre_avec_le_role_propose(test_db):
    owner = _creer_user(test_db, email="owner@example.com")
    potager = _creer_potager(test_db, "Jardin", owner.id)
    invitation = svc_potagers.creer_invitation(test_db, owner.id, potager.id, "editor")
    invite = _creer_user(test_db, email="invite@example.com")

    membre = svc_potagers.accepter_invitation(test_db, invite.id, invitation.code)

    assert membre.user_id == invite.id
    assert membre.potager_id == potager.id
    assert membre.role == "editor"
    test_db.refresh(invitation)
    assert invitation.utilisee_le is not None
    test_db.refresh(invite)
    assert invite.potager_actif_id == potager.id  # aucun potager avant → sélection auto


def test_us048_ca4_acceptation_ne_change_pas_le_potager_actif_existant(test_db):
    owner = _creer_user(test_db, email="owner@example.com")
    potager = _creer_potager(test_db, "Jardin", owner.id)
    invitation = svc_potagers.creer_invitation(test_db, owner.id, potager.id, "lecteur")
    invite = _creer_user(test_db, email="invite@example.com")
    autre_potager = _creer_potager(test_db, "Autre jardin", invite.id)
    invite.potager_actif_id = autre_potager.id
    test_db.commit()

    svc_potagers.accepter_invitation(test_db, invite.id, invitation.code)

    test_db.refresh(invite)
    assert invite.potager_actif_id == autre_potager.id


def test_us048_deja_membre_refuse(test_db):
    owner = _creer_user(test_db, email="owner@example.com")
    potager = _creer_potager(test_db, "Jardin", owner.id)
    invite = _creer_user(test_db, email="invite@example.com")
    test_db.add(PotagerMembre(user_id=invite.id, potager_id=potager.id, role="lecteur"))
    test_db.commit()
    invitation = svc_potagers.creer_invitation(test_db, owner.id, potager.id, "editor")

    with pytest.raises(svc_potagers.DejaMembreError):
        svc_potagers.accepter_invitation(test_db, invite.id, invitation.code)


# ── CA8 — Invitation invalide / expirée / déjà utilisée ─────────────────────

def test_us048_ca8_code_inconnu_refuse(test_db):
    invite = _creer_user(test_db)
    with pytest.raises(svc_potagers.InvitationInvalideError):
        svc_potagers.accepter_invitation(test_db, invite.id, "INCONNU1")


def test_us048_ca8_invitation_expiree_refusee(test_db):
    owner = _creer_user(test_db, email="owner@example.com")
    potager = _creer_potager(test_db, "Jardin", owner.id)
    invitation = Invitation(
        code="ABCD1234", potager_id=potager.id, invite_par_id=owner.id, role_propose="editor",
        expire_le=datetime.utcnow() - timedelta(minutes=1),
    )
    test_db.add(invitation)
    test_db.commit()
    invite = _creer_user(test_db, email="invite@example.com")

    with pytest.raises(svc_potagers.InvitationExpireeError):
        svc_potagers.accepter_invitation(test_db, invite.id, "ABCD1234")


def test_us048_ca8_invitation_deja_utilisee_refusee(test_db):
    owner = _creer_user(test_db, email="owner@example.com")
    potager = _creer_potager(test_db, "Jardin", owner.id)
    invitation = Invitation(
        code="ABCD1234", potager_id=potager.id, invite_par_id=owner.id, role_propose="editor",
        expire_le=datetime.utcnow() + timedelta(days=1),
        utilisee_le=datetime.utcnow(),
    )
    test_db.add(invitation)
    test_db.commit()
    invite = _creer_user(test_db, email="invite@example.com")

    with pytest.raises(svc_potagers.InvitationDejaUtiliseeError):
        svc_potagers.accepter_invitation(test_db, invite.id, "ABCD1234")


# ── CA5, CA6 — Retrait d'un membre et invalidation immédiate ───────────────

def test_us048_ca5_owner_peut_retirer_un_membre(test_db):
    owner = _creer_user(test_db, email="owner@example.com")
    editeur = _creer_user(test_db, email="editor@example.com")
    potager = _creer_potager(test_db, "Jardin", owner.id)
    test_db.add(PotagerMembre(user_id=editeur.id, potager_id=potager.id, role="editor"))
    test_db.commit()

    svc_potagers.retirer_membre(test_db, owner.id, potager.id, editeur.id)

    membre = (
        test_db.query(PotagerMembre)
        .filter(PotagerMembre.user_id == editeur.id, PotagerMembre.potager_id == potager.id)
        .first()
    )
    assert membre is None


def test_us048_ca6_retrait_invalide_le_potager_actif_du_membre(test_db):
    owner = _creer_user(test_db, email="owner@example.com")
    editeur = _creer_user(test_db, email="editor@example.com")
    potager = _creer_potager(test_db, "Jardin", owner.id)
    test_db.add(PotagerMembre(user_id=editeur.id, potager_id=potager.id, role="editor"))
    editeur.potager_actif_id = potager.id
    test_db.commit()

    svc_potagers.retirer_membre(test_db, owner.id, potager.id, editeur.id)

    test_db.refresh(editeur)
    assert editeur.potager_actif_id is None


def test_us048_ca5_non_owner_ne_peut_pas_retirer(test_db):
    owner = _creer_user(test_db, email="owner@example.com")
    editeur = _creer_user(test_db, email="editor@example.com")
    autre = _creer_user(test_db, email="autre@example.com")
    potager = _creer_potager(test_db, "Jardin", owner.id, membre_id=editeur.id, role="editor")
    test_db.add(PotagerMembre(user_id=autre.id, potager_id=potager.id, role="editor"))
    test_db.commit()

    with pytest.raises(PermissionInsuffisanteError):
        svc_potagers.retirer_membre(test_db, editeur.id, potager.id, autre.id)


def test_us048_retrait_membre_inconnu_refuse(test_db):
    owner = _creer_user(test_db, email="owner@example.com")
    autre = _creer_user(test_db, email="autre@example.com")
    potager = _creer_potager(test_db, "Jardin", owner.id)

    with pytest.raises(svc_potagers.MembreInconnuError):
        svc_potagers.retirer_membre(test_db, owner.id, potager.id, autre.id)


# ── Endpoints web — parcours self-service (CA7) ─────────────────────────────

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


def test_us048_post_potagers_cree_owner_et_potager_actif(app_client, _auth_engine):
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    user = _creer_compte_web(db)
    headers = _auth_header(user.id)
    db.close()

    resp = app_client.post("/potagers", json={"nom": "Jardin Nord"}, headers=headers)
    assert resp.status_code == 201
    potager_id = resp.json()["id"]

    resp = app_client.get("/potagers", headers=headers)
    body = resp.json()
    assert len(body["potagers"]) == 1
    assert body["potagers"][0]["id"] == potager_id
    assert body["potagers"][0]["actif"] is True
    assert body["potagers"][0]["role"] == "owner"


def test_us048_parcours_complet_invitation_puis_acceptation(app_client, _auth_engine):
    """[CA7] Inscription → création de potager → invitation → acceptation, sans
    aucune intervention manuelle en base."""
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    owner = _creer_compte_web(db, email="owner@example.com")
    owner_headers = _auth_header(owner.id)
    db.close()

    resp = app_client.post("/potagers", json={"nom": "Jardin partagé"}, headers=owner_headers)
    potager_id = resp.json()["id"]

    resp = app_client.post(
        f"/potagers/{potager_id}/invitations",
        json={"role_propose": "editor"},
        headers=owner_headers,
    )
    assert resp.status_code == 201
    code = resp.json()["code"]

    db = SessionLocal()
    invite = _creer_compte_web(db, email="invite@example.com")
    invite_headers = _auth_header(invite.id)
    db.close()

    resp = app_client.post(f"/invitations/{code}/accepter", headers=invite_headers)
    assert resp.status_code == 200
    assert resp.json() == {"potager_id": potager_id, "role": "editor"}

    resp = app_client.get("/potagers", headers=invite_headers)
    assert resp.json()["potagers"][0]["actif"] is True


def test_us048_creer_invitation_403_si_non_owner(app_client, _auth_engine):
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    owner = _creer_compte_web(db, email="owner@example.com")
    editeur = _creer_compte_web(db, email="editor@example.com")
    potager = _creer_potager(db, "Jardin", owner.id, membre_id=editeur.id, role="editor")
    editeur_headers = _auth_header(editeur.id)
    potager_id = potager.id
    db.close()

    resp = app_client.post(
        f"/potagers/{potager_id}/invitations",
        json={"role_propose": "lecteur"},
        headers=editeur_headers,
    )
    assert resp.status_code == 403


def test_us048_accepter_invitation_404_si_code_invalide(app_client, _auth_engine):
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    user = _creer_compte_web(db)
    headers = _auth_header(user.id)
    db.close()

    resp = app_client.post("/invitations/INCONNU1/accepter", headers=headers)
    assert resp.status_code == 404


def test_us048_delete_membre_403_si_non_owner(app_client, _auth_engine):
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    owner = _creer_compte_web(db, email="owner@example.com")
    editeur = _creer_compte_web(db, email="editor@example.com")
    autre = _creer_compte_web(db, email="autre@example.com")
    potager = _creer_potager(db, "Jardin", owner.id, membre_id=editeur.id, role="editor")
    db.add(PotagerMembre(user_id=autre.id, potager_id=potager.id, role="editor"))
    db.commit()
    editeur_headers = _auth_header(editeur.id)
    potager_id, autre_id = potager.id, autre.id
    db.close()

    resp = app_client.delete(f"/potagers/{potager_id}/membres/{autre_id}", headers=editeur_headers)
    assert resp.status_code == 403


def test_us048_ca6_membre_retire_perd_immediatement_acces(app_client, _auth_engine):
    """[CA6] Après retrait, toute requête ultérieure du membre retiré sur ce
    potager échoue (409 'aucun potager') — même mécanique que CA5 de US-046."""
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    owner = _creer_compte_web(db, email="owner@example.com")
    editeur = _creer_compte_web(db, email="editor@example.com")
    potager = _creer_potager(db, "Jardin", owner.id)
    db.add(PotagerMembre(user_id=editeur.id, potager_id=potager.id, role="editor"))
    editeur.potager_actif_id = potager.id
    db.commit()
    owner_headers = _auth_header(owner.id)
    editeur_headers = _auth_header(editeur.id)
    potager_id, editeur_id = potager.id, editeur.id
    db.close()

    resp = app_client.delete(f"/potagers/{potager_id}/membres/{editeur_id}", headers=owner_headers)
    assert resp.status_code == 200

    resp = app_client.get("/cultures", headers=editeur_headers)
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "no_potager"


def test_us048_get_membres_403_si_non_membre(app_client, _auth_engine):
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    owner = _creer_compte_web(db, email="owner@example.com")
    autre = _creer_compte_web(db, email="autre@example.com")
    potager = _creer_potager(db, "Jardin", owner.id)
    autre_headers = _auth_header(autre.id)
    potager_id = potager.id
    db.close()

    resp = app_client.get(f"/potagers/{potager_id}/membres", headers=autre_headers)
    assert resp.status_code == 403


def test_us048_get_membres_liste_pour_un_membre(app_client, _auth_engine):
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    owner = _creer_compte_web(db, email="owner@example.com")
    potager = _creer_potager(db, "Jardin", owner.id)
    owner_headers = _auth_header(owner.id)
    potager_id = potager.id
    db.close()

    resp = app_client.get(f"/potagers/{potager_id}/membres", headers=owner_headers)
    assert resp.status_code == 200
    membres = resp.json()["membres"]
    assert len(membres) == 1
    assert membres[0]["role"] == "owner"

"""
tests/test_us083_archiver_desarchiver_potager.py — [US-083] Archiver et
désarchiver un potager
--------------------------------------------------------------------------------
Couvre CA1 (endpoints owner-only), CA2 (etat/archive_le), CA4 (garde d'écriture
« couche services », partagée bot/API), CA5 (invalidation du potager actif des
membres concernés) et CA9 (notification Telegram best-effort des autres
membres). CA6/CA7/CA8 (masquage, bandeau, désarchivage sans bascule) sont
couverts pour leur volet backend (CA8 : aucune bascule automatique) — le rendu
(badges, bandeau, bascule d'affichage) relève de la validation visuelle QA.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import auth as svc_auth
from app.services import evenements as svc_evenements
from app.services import potager_actif as svc_potager_actif
from app.services import potagers as svc_potagers
from app.services.context import TenantContext
from app.services.permissions import PermissionInsuffisanteError, PotagerArchiveError
from database.db import Base
from database.models import PotagerMembre, User


def _creer_user(db, email="jardinier@example.com", **kwargs):
    user = User(email=email, mot_de_passe_hash="x", **kwargs)
    db.add(user)
    db.commit()
    return user


# ── CA1, CA2 — Archiver ──────────────────────────────────────────────────────

def test_ca1_ca2_owner_archive_le_potager(test_db):
    owner = _creer_user(test_db)
    potager = svc_potagers.creer_potager(test_db, owner.id, "Ancien jardin")
    assert potager.etat == "actif"
    assert potager.archive_le is None

    resultat = svc_potagers.archiver_potager(test_db, owner.id, potager.id)

    assert resultat.etat == "archive"
    assert resultat.archive_le is not None


def test_ca1_non_owner_ne_peut_pas_archiver(test_db):
    owner = _creer_user(test_db, email="owner@example.com")
    editeur = _creer_user(test_db, email="editor@example.com")
    potager = svc_potagers.creer_potager(test_db, owner.id, "Jardin partagé")
    test_db.add(PotagerMembre(user_id=editeur.id, potager_id=potager.id, role="editor"))
    test_db.commit()

    with pytest.raises(PermissionInsuffisanteError):
        svc_potagers.archiver_potager(test_db, editeur.id, potager.id)


# ── CA2, CA8 — Désarchiver ───────────────────────────────────────────────────

def test_ca2_desarchiver_repasse_a_actif_et_efface_archive_le(test_db):
    owner = _creer_user(test_db)
    potager = svc_potagers.creer_potager(test_db, owner.id, "Jardin d'hiver")
    svc_potagers.archiver_potager(test_db, owner.id, potager.id)

    resultat = svc_potagers.desarchiver_potager(test_db, owner.id, potager.id)

    assert resultat.etat == "actif"
    assert resultat.archive_le is None


def test_ca8_desarchivage_ne_rebascule_le_potager_actif_de_personne(test_db):
    owner = _creer_user(test_db)
    potager_archive = svc_potagers.creer_potager(test_db, owner.id, "Ancien jardin")  # actif (premier potager)
    potager_courant = svc_potagers.creer_potager(test_db, owner.id, "Jardin courant", activer=False)
    test_db.refresh(owner)
    assert owner.potager_actif_id == potager_archive.id  # actif avant archivage

    svc_potagers.archiver_potager(test_db, owner.id, potager_archive.id)
    test_db.refresh(owner)
    assert owner.potager_actif_id is None  # [CA5] invalidé par l'archivage

    # [CA5] La bascule automatique n'a lieu qu'à l'accès suivant (resoudre_tenant_context,
    # US-046/CA1) — un seul potager actif restant → sélection silencieuse persistée.
    svc_potager_actif.resoudre_tenant_context(test_db, owner.id)
    test_db.refresh(owner)
    assert owner.potager_actif_id == potager_courant.id

    svc_potagers.desarchiver_potager(test_db, owner.id, potager_archive.id)

    test_db.refresh(owner)
    assert owner.potager_actif_id == potager_courant.id  # [CA8] inchangé


def test_ca1_non_owner_ne_peut_pas_desarchiver(test_db):
    owner = _creer_user(test_db, email="owner@example.com")
    lecteur = _creer_user(test_db, email="lecteur@example.com")
    potager = svc_potagers.creer_potager(test_db, owner.id, "Jardin partagé")
    test_db.add(PotagerMembre(user_id=lecteur.id, potager_id=potager.id, role="lecteur"))
    test_db.commit()
    svc_potagers.archiver_potager(test_db, owner.id, potager.id)

    with pytest.raises(PermissionInsuffisanteError):
        svc_potagers.desarchiver_potager(test_db, lecteur.id, potager.id)


# ── CA5 — Invalidation du potager actif des membres concernés ──────────────

def test_ca5_invalide_le_potager_actif_de_chaque_membre_concerne(test_db):
    """Scénario Gherkin « Archiver un potager après un déménagement »."""
    owner = _creer_user(test_db, email="owner@example.com")
    membre = _creer_user(test_db, email="membre@example.com")
    ancien = svc_potagers.creer_potager(test_db, owner.id, "Ancien jardin")
    nouveau = svc_potagers.creer_potager(test_db, owner.id, "Nouveau jardin", activer=False)
    test_db.add(PotagerMembre(user_id=membre.id, potager_id=ancien.id, role="editor"))
    test_db.commit()

    svc_potagers.archiver_potager(test_db, owner.id, ancien.id)

    test_db.refresh(owner)
    test_db.refresh(membre)
    assert owner.potager_actif_id is None  # invalidé par l'archivage
    # [CA5] Membre sans autre potager → invalidé, retombe sur NULL (onboarding).
    assert membre.potager_actif_id is None

    # [CA5] La bascule automatique n'a lieu qu'à l'accès suivant : owner n'a
    # plus qu'un potager actif restant → sélection silencieuse persistée
    # (mécanisme déjà en place, resoudre_tenant_context / US-046 CA1).
    ctx = svc_potager_actif.resoudre_tenant_context(test_db, owner.id)
    assert ctx.potager_id == nouveau.id
    test_db.refresh(owner)
    assert owner.potager_actif_id == nouveau.id


def test_ca5_membre_dont_ce_nest_pas_le_potager_actif_nest_pas_touche(test_db):
    owner = _creer_user(test_db, email="owner@example.com")
    membre = _creer_user(test_db, email="membre@example.com")
    potager = svc_potagers.creer_potager(test_db, owner.id, "Jardin partagé")
    autre_potager = svc_potagers.creer_potager(test_db, membre.id, "Jardin du membre")
    test_db.add(PotagerMembre(user_id=membre.id, potager_id=potager.id, role="editor"))
    test_db.commit()

    svc_potagers.archiver_potager(test_db, owner.id, potager.id)

    test_db.refresh(membre)
    assert membre.potager_actif_id == autre_potager.id  # jamais touché


def test_ca3_archivage_du_dernier_potager_laisse_lowner_sans_potager_actif(test_db):
    """Scénario Gherkin « Archivage du dernier potager »."""
    owner = _creer_user(test_db)
    potager = svc_potagers.creer_potager(test_db, owner.id, "Seul jardin")

    svc_potagers.archiver_potager(test_db, owner.id, potager.id)

    test_db.refresh(owner)
    assert owner.potager_actif_id is None
    with pytest.raises(svc_potager_actif.AucunPotagerError):
        svc_potager_actif.resoudre_tenant_context(test_db, owner.id)


# ── CA9 — Notification Telegram best-effort ─────────────────────────────────

def test_ca9_notifie_les_autres_membres_lies_a_telegram(test_db, monkeypatch):
    owner = _creer_user(test_db, email="owner@example.com", nom="Emmanuel")
    lie = _creer_user(test_db, email="lie@example.com", telegram_chat_id=555)
    non_lie = _creer_user(test_db, email="nonlie@example.com")
    potager = svc_potagers.creer_potager(test_db, owner.id, "Jardin de tous")
    test_db.add(PotagerMembre(user_id=lie.id, potager_id=potager.id, role="editor"))
    test_db.add(PotagerMembre(user_id=non_lie.id, potager_id=potager.id, role="lecteur"))
    test_db.commit()

    appels = []
    monkeypatch.setattr(
        "app.services.telegram_notify.envoyer_message",
        lambda chat_id, texte: appels.append((chat_id, texte)) or True,
    )

    svc_potagers.archiver_potager(test_db, owner.id, potager.id)

    assert len(appels) == 1
    chat_id, texte = appels[0]
    assert chat_id == 555
    assert "Emmanuel" in texte
    assert "Jardin de tous" in texte


def test_ca9_absence_de_liaison_ne_fait_jamais_echouer_larchivage(test_db, monkeypatch):
    """[CA9 note fonctionnelle] Aucun membre lié à Telegram — l'archivage réussit
    normalement, `envoyer_message` n'est simplement jamais appelé."""
    owner = _creer_user(test_db)
    potager = svc_potagers.creer_potager(test_db, owner.id, "Jardin solo")

    def _echec(*a, **kw):
        raise AssertionError("envoyer_message ne doit pas être appelé sans membre lié")

    monkeypatch.setattr("app.services.telegram_notify.envoyer_message", _echec)

    resultat = svc_potagers.archiver_potager(test_db, owner.id, potager.id)
    assert resultat.etat == "archive"


# ── CA4 — Garde d'écriture, couche services ─────────────────────────────────

def test_ca4_ecriture_refusee_sur_un_potager_archive(test_db):
    """Scénario Gherkin « Écriture refusée sur un potager archivé ».

    [CA4] Testé directement au niveau service (TenantContext construit à la
    main plutôt que résolu via `resoudre_tenant_context`) : côté web comme
    côté bot, la résolution normale du contexte (US-046) exclut déjà les
    potagers archivés et invalide (CA5) le pointeur `potager_actif_id` dès
    l'archivage — un appelant standard ne peut donc jamais obtenir de `ctx`
    pointant sur un potager archivé. Ce garde est la défense en profondeur
    de la couche services elle-même (CA4 : « refusée dans la couche services »),
    pas un chemin atteignable en pratique depuis un endpoint HTTP normal."""
    owner = _creer_user(test_db)
    potager = svc_potagers.creer_potager(test_db, owner.id, "Jardin archivé")
    svc_potagers.archiver_potager(test_db, owner.id, potager.id)
    ctx = TenantContext(user_id=owner.id, potager_id=potager.id, role="owner")

    with pytest.raises(PotagerArchiveError):
        svc_evenements.creer_evenement_observation(
            test_db, ctx, {"constat": "Tout va bien"}, "tout va bien", "Observation",
        )


def test_ca4_ecriture_autorisee_sur_un_potager_actif(test_db):
    """Non-régression : le garde ne bloque rien sur un potager non archivé."""
    owner = _creer_user(test_db)
    potager = svc_potagers.creer_potager(test_db, owner.id, "Jardin actif")
    ctx = TenantContext(user_id=owner.id, potager_id=potager.id, role="owner")

    event = svc_evenements.creer_evenement_observation(
        test_db, ctx, {"constat": "Tout va bien"}, "tout va bien", "Observation",
    )
    assert event.id is not None


def test_ca4_lecture_reste_autorisee_sur_un_potager_archive(test_db):
    """[CA4] « la lecture reste autorisée » — dernier_evenement (lecture pure)
    ne passe par aucune garde de rôle ni d'archivage."""
    owner = _creer_user(test_db)
    potager = svc_potagers.creer_potager(test_db, owner.id, "Jardin actif")
    ctx = TenantContext(user_id=owner.id, potager_id=potager.id, role="owner")
    svc_evenements.creer_evenement_observation(
        test_db, ctx, {"constat": "Tout va bien"}, "tout va bien", "Observation",
    )
    svc_potagers.archiver_potager(test_db, owner.id, potager.id)

    # La lecture ne lève jamais PotagerArchiveError.
    dernier = svc_evenements.dernier_evenement(test_db, ctx)
    assert dernier is not None


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
    monkeypatch.setattr("app.services.telegram_notify.envoyer_message", lambda *a, **kw: True)
    main.app.state.limiter.reset()
    with TestClient(main.app) as c:
        yield c


def _creer_compte_web(db, email="jardinier@example.com", mot_de_passe="motdepasse123"):
    return svc_auth.inscrire_utilisateur(db, email, mot_de_passe)


def _auth_header(user_id):
    return {"Authorization": f"Bearer {svc_auth.creer_access_token(user_id)}"}


def test_endpoint_archiver_puis_desarchiver(app_client, _auth_engine):
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    user = _creer_compte_web(db)
    headers = _auth_header(user.id)
    db.close()

    resp = app_client.post("/potagers", json={"nom": "Jardin à archiver"}, headers=headers)
    potager_id = resp.json()["id"]

    resp = app_client.post(f"/potagers/{potager_id}/archiver", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["etat"] == "archive"
    assert resp.json()["archive_le"] is not None

    resp = app_client.post(f"/potagers/{potager_id}/desarchiver", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["etat"] == "actif"
    assert resp.json()["archive_le"] is None


def test_endpoint_archiver_refuse_non_owner(app_client, _auth_engine):
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    owner = _creer_compte_web(db, email="owner@example.com")
    editeur = _creer_compte_web(db, email="editor@example.com")
    headers_owner = _auth_header(owner.id)
    headers_editeur = _auth_header(editeur.id)
    db.close()

    resp = app_client.post("/potagers", json={"nom": "Jardin partagé"}, headers=headers_owner)
    potager_id = resp.json()["id"]

    db = SessionLocal()
    db.add(PotagerMembre(user_id=editeur.id, potager_id=potager_id, role="editor"))
    db.commit()
    db.close()

    resp = app_client.post(f"/potagers/{potager_id}/archiver", headers=headers_editeur)
    assert resp.status_code == 403


def test_ca6_potager_archive_absent_du_filtre_par_defaut(app_client, _auth_engine):
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    user = _creer_compte_web(db)
    headers = _auth_header(user.id)
    db.close()

    resp = app_client.post("/potagers", json={"nom": "Jardin à archiver"}, headers=headers)
    potager_id = resp.json()["id"]
    app_client.post(f"/potagers/{potager_id}/archiver", headers=headers)

    resp_defaut = app_client.get("/potagers", headers=headers)
    assert all(p["id"] != potager_id for p in resp_defaut.json()["potagers"])

    resp_tous = app_client.get("/potagers?etat=tous", headers=headers)
    archive = next(p for p in resp_tous.json()["potagers"] if p["id"] == potager_id)
    assert archive["etat"] == "archive"

"""
tests/test_us086_quitter_potager.py — [US-086] Quitter un potager dont on est membre
--------------------------------------------------------------------------------
Couvre CA1 (endpoint `POST /potagers/{id}/quitter`, identité seule), CA2 (refus au
dernier owner, garde d'US-085 réutilisée), CA3 (owner non unique), CA4 (potager actif
invalidé, bascule ou aucun potager), CA5 (aucune donnée métier effacée), CA7 (owners
liés à Telegram informés) et CA8 (accès coupé dès la requête suivante — test
d'isolation). CA6 (zone sensible, confirmation) relève du frontend :
`frontend/src/lib/us086_quitter_potager.test.js`.
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
from app.services.permissions import PermissionInsuffisanteError
from database.db import Base
from database.models import Evenement, Parcelle, PotagerMembre, User


def _creer_user(db, email="jardinier@example.com", **kwargs):
    user = User(email=email, mot_de_passe_hash="x", **kwargs)
    db.add(user)
    db.commit()
    return user


def _ajouter_membre(db, potager_id, user, role):
    db.add(PotagerMembre(user_id=user.id, potager_id=potager_id, role=role))
    db.commit()


def _role(db, potager_id, user_id):
    return svc_potager_actif.role_utilisateur(db, user_id, potager_id)


@pytest.fixture
def association(test_db):
    """« Jardin des Lilas » : un owner, une éditrice, une lectrice — et le potager
    personnel de l'éditrice (dont elle est owner)."""
    owner = _creer_user(test_db, email="owner@example.com", nom="Emmanuel")
    editrice = _creer_user(test_db, email="edith@example.com", nom="Edith")
    lectrice = _creer_user(test_db, email="lea@example.com", nom="Léa")
    lilas = svc_potagers.creer_potager(test_db, owner.id, "Jardin des Lilas")
    _ajouter_membre(test_db, lilas.id, editrice, "editor")
    _ajouter_membre(test_db, lilas.id, lectrice, "lecteur")
    perso = svc_potagers.creer_potager(test_db, editrice.id, "Potager d'Edith", activer=False)
    return {"owner": owner, "editrice": editrice, "lectrice": lectrice, "lilas": lilas, "perso": perso}


# ── CA1, CA4, CA5 — Quitter un jardin partagé ───────────────────────────────

def test_ca1_un_membre_quitte_un_potager_dont_il_n_est_pas_owner(test_db, association):
    """Scénario Gherkin « Quitter un jardin partagé »."""
    editrice = association["editrice"]
    lilas_id = association["lilas"].id
    editrice.potager_actif_id = lilas_id
    test_db.commit()

    svc_potagers.quitter_potager(test_db, editrice.id, lilas_id)

    assert _role(test_db, lilas_id, editrice.id) is None
    # Son potager actif est son potager personnel (bascule reprise à l'accès suivant).
    ctx = svc_potager_actif.resoudre_tenant_context(test_db, editrice.id)
    assert ctx.potager_id == association["perso"].id
    assert ctx.role == "owner"


def test_ca1_un_lecteur_peut_aussi_quitter(test_db, association):
    svc_potagers.quitter_potager(test_db, association["lectrice"].id, association["lilas"].id)
    assert _role(test_db, association["lilas"].id, association["lectrice"].id) is None


def test_ca1_le_depart_ne_demande_aucune_permission_particuliere(test_db, association):
    """Un lecteur, le rôle le plus faible, peut partir sans qu'aucun `require_role` ne l'en empêche."""
    svc_potagers.quitter_potager(test_db, association["lectrice"].id, association["lilas"].id)
    membres = svc_potagers.lister_membres(test_db, association["lilas"].id)
    assert {m["email"] for m in membres} == {"owner@example.com", "edith@example.com"}


def test_ca1_un_non_membre_ne_peut_pas_quitter(test_db, association):
    intrus = _creer_user(test_db, email="intrus@example.com")

    with pytest.raises(svc_potager_actif.PotagerNonMembreError):
        svc_potagers.quitter_potager(test_db, intrus.id, association["lilas"].id)


def test_ca5_les_evenements_parcelles_et_photos_du_partant_restent_au_potager(test_db, association):
    """Quitter n'efface aucune donnée métier : le potager appartient au collectif."""
    editrice = association["editrice"]
    lilas_id = association["lilas"].id
    ctx = TenantContext(user_id=editrice.id, potager_id=lilas_id, role="editor")
    evenement = svc_evenements.creer_evenement_observation(
        test_db, ctx, {"constat": "Pucerons sur les fèves"}, "pucerons", "Observation",
    )
    test_db.add(Parcelle(nom="Planche A", nom_normalise="planchea", potager_id=lilas_id))
    test_db.commit()
    avant = (
        test_db.query(Evenement).filter(Evenement.potager_id == lilas_id).count(),
        test_db.query(Parcelle).filter(Parcelle.potager_id == lilas_id).count(),
    )

    svc_potagers.quitter_potager(test_db, editrice.id, lilas_id)

    apres = (
        test_db.query(Evenement).filter(Evenement.potager_id == lilas_id).count(),
        test_db.query(Parcelle).filter(Parcelle.potager_id == lilas_id).count(),
    )
    assert apres == avant == (1, 1)
    # Les événements passés restent visibles pour les autres membres.
    ctx_owner = TenantContext(user_id=association["owner"].id, potager_id=lilas_id, role="owner")
    assert svc_evenements.dernier_evenement(test_db, ctx_owner).id == evenement.id


# ── CA2 — Le dernier owner ne peut pas quitter ──────────────────────────────

def test_ca2_le_dernier_owner_ne_peut_pas_quitter(test_db, association):
    """Scénario Gherkin « Le dernier owner ne peut pas quitter »."""
    lilas_id = association["lilas"].id

    with pytest.raises(svc_potagers.DernierOwnerError) as exc:
        svc_potagers.quitter_potager(test_db, association["owner"].id, lilas_id)

    message = str(exc.value)
    assert "Désigne d'abord un autre propriétaire" in message  # US-085
    assert "archive puis supprime le potager" in message  # US-083 / US-084
    assert _role(test_db, lilas_id, association["owner"].id) == "owner"


def test_ca2_un_owner_seul_de_son_potager_personnel_ne_peut_pas_le_quitter(test_db, association):
    with pytest.raises(svc_potagers.DernierOwnerError):
        svc_potagers.quitter_potager(test_db, association["editrice"].id, association["perso"].id)


def test_ca2_la_garde_est_celle_d_us085_une_seule_regle_pour_les_trois_chemins(test_db, association, monkeypatch):
    """« Trois chemins, une seule règle » : le départ appelle la même garde que le
    changement de rôle et le retrait de membre."""
    appels = []
    monkeypatch.setattr(
        svc_potagers, "_garantir_un_owner_restant",
        lambda db, potager, membre, action, *a, **kw: appels.append((membre, action)),
    )

    svc_potagers.quitter_potager(test_db, association["owner"].id, association["lilas"].id)

    assert appels == [(association["owner"].id, "le quitter")]


def test_le_depart_et_le_retrait_partagent_la_meme_suppression_d_appartenance(test_db, association, monkeypatch):
    """Factorisation : ni `retirer_membre` ni `quitter_potager` ne dupliquent la
    suppression d'appartenance et l'invalidation du potager actif."""
    appels = []
    original = svc_potagers._supprimer_appartenance

    def _espion(db, potager_id, membre_user_id, *args, **kwargs):
        appels.append(membre_user_id)
        return original(db, potager_id, membre_user_id, *args, **kwargs)

    monkeypatch.setattr(svc_potagers, "_supprimer_appartenance", _espion)

    svc_potagers.quitter_potager(test_db, association["lectrice"].id, association["lilas"].id)
    svc_potagers.retirer_membre(test_db, association["owner"].id, association["lilas"].id, association["editrice"].id)

    assert appels == [association["lectrice"].id, association["editrice"].id]


# ── CA3 — Un owner non unique quitte comme n'importe quel membre ────────────

def test_ca3_un_owner_non_unique_peut_quitter(test_db, association):
    lilas_id = association["lilas"].id
    svc_potagers.modifier_role_membre(test_db, association["owner"].id, lilas_id, association["editrice"].id, "owner")

    svc_potagers.quitter_potager(test_db, association["owner"].id, lilas_id)

    assert _role(test_db, lilas_id, association["owner"].id) is None
    assert _role(test_db, lilas_id, association["editrice"].id) == "owner"


def test_ca3_passer_la_main_puis_partir_le_parcours_complet(test_db, association):
    """US-085 puis US-086 : l'owner désigne un successeur, se rétrograde, puis quitte."""
    lilas_id = association["lilas"].id
    svc_potagers.modifier_role_membre(test_db, association["owner"].id, lilas_id, association["editrice"].id, "owner")
    svc_potagers.modifier_role_membre(test_db, association["owner"].id, lilas_id, association["owner"].id, "editor")

    svc_potagers.quitter_potager(test_db, association["owner"].id, lilas_id)

    assert _role(test_db, lilas_id, association["owner"].id) is None
    assert _role(test_db, lilas_id, association["editrice"].id) == "owner"


def test_ca3_deux_owners_qui_partent_l_un_apres_l_autre_jamais_orphelin(test_db, association):
    lilas_id = association["lilas"].id
    svc_potagers.modifier_role_membre(test_db, association["owner"].id, lilas_id, association["editrice"].id, "owner")

    svc_potagers.quitter_potager(test_db, association["owner"].id, lilas_id)
    with pytest.raises(svc_potagers.DernierOwnerError):
        svc_potagers.quitter_potager(test_db, association["editrice"].id, lilas_id)

    assert _role(test_db, lilas_id, association["editrice"].id) == "owner"


# ── CA4 — Potager actif invalidé, bascule ou aucun potager ──────────────────

def test_ca4_quitter_son_dernier_potager_laisse_sans_potager_actif(test_db, association):
    """Scénario Gherkin « Quitter son potager actif et son dernier potager »."""
    lectrice = association["lectrice"]
    lilas_id = association["lilas"].id
    lectrice.potager_actif_id = lilas_id
    test_db.commit()

    svc_potagers.quitter_potager(test_db, lectrice.id, lilas_id)

    test_db.refresh(lectrice)
    assert lectrice.potager_actif_id is None
    # Parcours d'adhésion/création : l'API répond « aucun potager » (409 no_potager).
    with pytest.raises(svc_potager_actif.AucunPotagerError):
        svc_potager_actif.resoudre_tenant_context(test_db, lectrice.id)


def test_ca4_quitter_un_potager_qui_n_est_pas_l_actif_ne_change_pas_l_actif(test_db, association):
    editrice = association["editrice"]
    editrice.potager_actif_id = association["perso"].id
    test_db.commit()

    svc_potagers.quitter_potager(test_db, editrice.id, association["lilas"].id)

    test_db.refresh(editrice)
    assert editrice.potager_actif_id == association["perso"].id


# ── CA7 — Les owners liés à Telegram sont informés ──────────────────────────

def test_ca7_les_owners_lies_a_telegram_sont_informes_du_depart(test_db, association, monkeypatch):
    lilas_id = association["lilas"].id
    svc_potagers.modifier_role_membre(test_db, association["owner"].id, lilas_id, association["lectrice"].id, "owner")
    association["owner"].telegram_chat_id = 111
    association["lectrice"].telegram_chat_id = 222  # second owner
    association["editrice"].telegram_chat_id = 333  # simple éditrice : hors diffusion
    test_db.commit()
    appels = []
    monkeypatch.setattr(
        "app.services.telegram_notify.envoyer_message",
        lambda chat_id, texte: appels.append((chat_id, texte)) or True,
    )

    svc_potagers.quitter_potager(test_db, association["editrice"].id, lilas_id)

    assert sorted(chat_id for chat_id, _ in appels) == [111, 222]
    texte = appels[0][1]
    assert "Edith" in texte and "a quitté" in texte and "Jardin des Lilas" in texte


def test_ca7_un_owner_qui_part_n_est_pas_notifie_lui_meme_mais_l_autre_owner_l_est(test_db, association, monkeypatch):
    lilas_id = association["lilas"].id
    svc_potagers.modifier_role_membre(test_db, association["owner"].id, lilas_id, association["editrice"].id, "owner")
    association["owner"].telegram_chat_id = 111
    association["editrice"].telegram_chat_id = 333
    test_db.commit()
    destinataires = []
    monkeypatch.setattr(
        "app.services.telegram_notify.envoyer_message",
        lambda chat_id, texte: destinataires.append(chat_id) or True,
    )

    svc_potagers.quitter_potager(test_db, association["owner"].id, lilas_id)

    assert destinataires == [333]


def test_ca7_aucun_owner_lie_aucun_envoi_et_le_depart_reussit(test_db, association, monkeypatch):
    def _echec(*a, **kw):
        raise AssertionError("envoyer_message ne doit pas être appelé sans owner lié à Telegram")

    monkeypatch.setattr("app.services.telegram_notify.envoyer_message", _echec)

    svc_potagers.quitter_potager(test_db, association["lectrice"].id, association["lilas"].id)

    assert _role(test_db, association["lilas"].id, association["lectrice"].id) is None


def test_ca7_une_panne_telegram_ne_fait_pas_echouer_le_depart(test_db, association, monkeypatch):
    association["owner"].telegram_chat_id = 111
    test_db.commit()
    monkeypatch.setattr("app.services.telegram_notify.envoyer_message", lambda *a, **kw: False)

    svc_potagers.quitter_potager(test_db, association["lectrice"].id, association["lilas"].id)

    assert _role(test_db, association["lilas"].id, association["lectrice"].id) is None


def test_ca7_un_depart_refuse_ne_notifie_personne(test_db, association, monkeypatch):
    association["editrice"].telegram_chat_id = 333
    test_db.commit()
    appels = []
    monkeypatch.setattr("app.services.telegram_notify.envoyer_message", lambda *a: appels.append(a) or True)

    with pytest.raises(svc_potagers.DernierOwnerError):
        svc_potagers.quitter_potager(test_db, association["owner"].id, association["lilas"].id)

    assert appels == []


def test_non_regression_les_notifications_de_cycle_de_vie_atteignent_toujours_tous_les_membres(
    test_db, association, monkeypatch
):
    """`_notifier_cycle_vie` gagne un filtre de rôles ; sans filtre (archivage, US-083),
    tous les autres membres liés à Telegram restent notifiés."""
    for user, chat in ((association["editrice"], 1), (association["lectrice"], 2)):
        user.telegram_chat_id = chat
        test_db.commit()
    destinataires = []
    monkeypatch.setattr(
        "app.services.telegram_notify.envoyer_message",
        lambda chat_id, texte: destinataires.append(chat_id) or True,
    )

    svc_potagers.archiver_potager(test_db, association["owner"].id, association["lilas"].id)

    assert sorted(destinataires) == [1, 2]


# ── CA8 — Accès coupé immédiatement (test d'isolation) ──────────────────────

def test_ca8_apres_le_depart_l_ancien_membre_n_a_plus_aucun_droit_sur_le_potager(test_db, association):
    """Scénario Gherkin « Accès coupé immédiatement »."""
    lectrice = association["lectrice"]
    lilas_id = association["lilas"].id
    svc_potagers.quitter_potager(test_db, lectrice.id, lilas_id)

    assert _role(test_db, lilas_id, lectrice.id) is None
    assert svc_potager_actif.obtenir_potager(test_db, lectrice.id, lilas_id) is None
    assert svc_potager_actif.lister_potagers_utilisateur(test_db, lectrice.id) == []
    with pytest.raises(svc_potager_actif.PotagerNonMembreError):
        svc_potager_actif.definir_potager_actif(test_db, lectrice.id, lilas_id)
    # Un contexte reconstruit pour ce potager ne porte plus aucun rôle : toute écriture,
    # y compris celle d'un simple événement, est refusée.
    ctx = TenantContext(user_id=lectrice.id, potager_id=lilas_id, role=_role(test_db, lilas_id, lectrice.id))
    with pytest.raises(PermissionInsuffisanteError):
        svc_evenements.creer_evenement_observation(test_db, ctx, {"constat": "x"}, "x", "Observation")


def test_ca8_un_editor_parti_ne_peut_plus_ecrire_dans_le_potager_quitte(test_db, association):
    editrice = association["editrice"]
    lilas_id = association["lilas"].id
    svc_potagers.quitter_potager(test_db, editrice.id, lilas_id)

    ctx = TenantContext(user_id=editrice.id, potager_id=lilas_id, role=_role(test_db, lilas_id, editrice.id))
    with pytest.raises(PermissionInsuffisanteError):
        svc_evenements.creer_evenement_observation(test_db, ctx, {"constat": "x"}, "x", "Observation")


def test_ca8_le_potager_quitte_ne_sert_plus_de_contexte_a_l_ancien_membre(test_db, association):
    """Côté bot comme API, le contexte se résout depuis `potager_membres` : le potager
    quitté n'y figure plus, même s'il était encore pointé par `potager_actif_id`."""
    editrice = association["editrice"]
    editrice.potager_actif_id = association["lilas"].id
    test_db.commit()

    svc_potagers.quitter_potager(test_db, editrice.id, association["lilas"].id)

    ctx = svc_potager_actif.resoudre_tenant_context(test_db, editrice.id)
    assert ctx.potager_id != association["lilas"].id


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
    from app.api import main
    TestSessionLocal = sessionmaker(bind=_auth_engine)
    monkeypatch.setattr(main, "SessionLocal", TestSessionLocal)
    monkeypatch.setattr("app.services.telegram_notify.envoyer_message", lambda *a, **kw: True)
    main.app.state.limiter.reset()
    with TestClient(main.app) as c:
        yield c


def _auth_header(user_id):
    return {"Authorization": f"Bearer {svc_auth.creer_access_token(user_id)}"}


@pytest.fixture
def api_association(app_client, _auth_engine):
    """« Jardin des Lilas » créé par l'API : `owner` (créateur), `editeur` et `lecteur`."""
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    ids = {
        nom: svc_auth.inscrire_utilisateur(db, f"{nom}@example.com", "motdepasse123").id
        for nom in ("owner", "editeur", "lecteur")
    }
    db.close()
    headers = {nom: _auth_header(uid) for nom, uid in ids.items()}
    potager_id = app_client.post("/potagers", json={"nom": "Jardin des Lilas"}, headers=headers["owner"]).json()["id"]
    db = SessionLocal()
    db.add(PotagerMembre(user_id=ids["editeur"], potager_id=potager_id, role="editor"))
    db.add(PotagerMembre(user_id=ids["lecteur"], potager_id=potager_id, role="lecteur"))
    db.commit()
    db.close()
    return {"potager_id": potager_id, "ids": ids, "headers": headers}


def test_endpoint_ca1_un_editor_quitte_le_potager(app_client, api_association):
    resp = app_client.post(
        f"/potagers/{api_association['potager_id']}/quitter", headers=api_association["headers"]["editeur"],
    )

    assert resp.status_code == 200
    assert resp.json() == {"success": True}
    liste = app_client.get(
        f"/potagers/{api_association['potager_id']}/membres", headers=api_association["headers"]["owner"],
    ).json()["membres"]
    assert api_association["ids"]["editeur"] not in {m["user_id"] for m in liste}


def test_endpoint_ca2_le_dernier_owner_ne_peut_pas_quitter_409(app_client, api_association):
    resp = app_client.post(
        f"/potagers/{api_association['potager_id']}/quitter", headers=api_association["headers"]["owner"],
    )

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "Désigne d'abord un autre propriétaire" in detail
    assert "archive puis supprime le potager" in detail


def test_endpoint_ca3_apres_promotion_le_createur_peut_quitter(app_client, api_association):
    base = f"/potagers/{api_association['potager_id']}"
    app_client.patch(
        f"{base}/membres/{api_association['ids']['editeur']}", json={"role": "owner"},
        headers=api_association["headers"]["owner"],
    )

    resp = app_client.post(f"{base}/quitter", headers=api_association["headers"]["owner"])

    assert resp.status_code == 200


def test_endpoint_un_non_membre_recoit_403(app_client, api_association, _auth_engine):
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    intrus = svc_auth.inscrire_utilisateur(db, "intrus@example.com", "motdepasse123")
    entete = _auth_header(intrus.id)
    db.close()

    resp = app_client.post(f"/potagers/{api_association['potager_id']}/quitter", headers=entete)

    assert resp.status_code == 403


def test_endpoint_exige_une_authentification(app_client, api_association):
    resp = app_client.post(f"/potagers/{api_association['potager_id']}/quitter")
    assert resp.status_code in (401, 403)


def test_endpoint_ca8_apres_le_depart_toute_requete_scopee_sur_le_potager_est_refusee(app_client, api_association):
    """Test d'isolation (cf. US-042/US-043) : l'ancien membre n'accède plus à rien."""
    base = f"/potagers/{api_association['potager_id']}"
    entete = api_association["headers"]["editeur"]
    # Un potager personnel : le contexte reste résolu après le départ, seul le potager quitté est refusé.
    assert app_client.post("/potagers", json={"nom": "Potager perso"}, headers=entete).status_code == 201
    assert app_client.get(base, headers=entete).status_code == 200  # membre : accès normal

    assert app_client.post(f"{base}/quitter", headers=entete).status_code == 200

    assert app_client.get(base, headers=entete).status_code == 403
    assert app_client.get(f"{base}/membres", headers=entete).status_code == 403
    assert app_client.post(f"{base}/activer", headers=entete).status_code == 403
    assert app_client.get(f"/plan?potager_id={api_association['potager_id']}", headers=entete).status_code == 403
    assert app_client.post(f"{base}/invitations", json={"role_propose": "lecteur"}, headers=entete).status_code == 403


def test_endpoint_ca4_le_dernier_potager_quitte_mene_au_parcours_sans_potager(app_client, api_association):
    """L'API répond 409 `no_potager` — signal que le frontend traduit en parcours
    d'adhésion/création, sans écran d'erreur."""
    entete = api_association["headers"]["lecteur"]
    assert app_client.get("/cultures", headers=entete).status_code == 200  # potager actif résolu

    app_client.post(f"/potagers/{api_association['potager_id']}/quitter", headers=entete)

    resp = app_client.get("/cultures", headers=entete)
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "no_potager"
    assert app_client.get("/potagers", headers=entete).json()["potagers"] == []


def test_endpoint_ca4_les_autres_membres_gardent_leur_acces(app_client, api_association):
    base = f"/potagers/{api_association['potager_id']}"
    app_client.post(f"{base}/quitter", headers=api_association["headers"]["editeur"])

    assert app_client.get(base, headers=api_association["headers"]["lecteur"]).status_code == 200
    assert app_client.get(base, headers=api_association["headers"]["owner"]).status_code == 200

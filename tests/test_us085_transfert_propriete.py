"""
tests/test_us085_transfert_propriete.py — [US-085] Changer le rôle d'un membre et
transférer la propriété d'un potager
--------------------------------------------------------------------------------
Couvre CA1 (endpoint owner-only, trois rôles), CA2 (promotion → plusieurs owners),
CA3 (auto-rétrogradation sous condition), CA4 (garde « dernier owner », unique et
partagée avec `retirer_membre`), CA5 (editor/lecteur ne changent aucun rôle),
CA6 (effet immédiat) et CA8 (notification Telegram best-effort du membre concerné).
CA7 (confirmation de promotion) et CA9 (emplacement dans « Paramètres du potager »)
relèvent du frontend : `frontend/src/lib/us085_roles_membres.test.js`.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Query, sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import auth as svc_auth
from app.services import evenements as svc_evenements
from app.services import potager_actif as svc_potager_actif
from app.services import potagers as svc_potagers
from app.services.permissions import PermissionInsuffisanteError
from database.db import Base
from database.models import Potager, PotagerMembre, User


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


def _nb_owners(db, potager_id):
    return db.query(PotagerMembre).filter(
        PotagerMembre.potager_id == potager_id, PotagerMembre.role == "owner"
    ).count()


@pytest.fixture
def jardin(test_db):
    """Un potager partagé : un owner, un editor, un lecteur."""
    owner = _creer_user(test_db, email="owner@example.com", nom="Emmanuel")
    editeur = _creer_user(test_db, email="editor@example.com", nom="Edith")
    lecteur = _creer_user(test_db, email="lecteur@example.com", nom="Léo")
    potager = svc_potagers.creer_potager(test_db, owner.id, "Jardin des Lilas")
    _ajouter_membre(test_db, potager.id, editeur, "editor")
    _ajouter_membre(test_db, potager.id, lecteur, "lecteur")
    return {"owner": owner, "editeur": editeur, "lecteur": lecteur, "potager": potager}


# ── CA2 — Promouvoir un membre propriétaire ─────────────────────────────────

def test_ca2_promouvoir_un_membre_donne_plusieurs_owners(test_db, jardin):
    """Scénario Gherkin « Promouvoir un membre propriétaire »."""
    potager_id = jardin["potager"].id

    membre = svc_potagers.modifier_role_membre(
        test_db, jardin["owner"].id, potager_id, jardin["editeur"].id, "owner",
    )

    assert membre.role == "owner"
    assert _nb_owners(test_db, potager_id) == 2


def test_ca2_le_membre_promu_dispose_des_droits_d_owner(test_db, jardin):
    potager_id = jardin["potager"].id
    svc_potagers.modifier_role_membre(test_db, jardin["owner"].id, potager_id, jardin["editeur"].id, "owner")

    # Gérer les membres : inviter…
    invitation = svc_potagers.creer_invitation(test_db, jardin["editeur"].id, potager_id, "lecteur")
    assert invitation.code
    # …et archiver le potager.
    potager = svc_potagers.archiver_potager(test_db, jardin["editeur"].id, potager_id)
    assert potager.etat == "archive"


def test_ca2_un_lecteur_peut_etre_promu_directement_owner(test_db, jardin):
    svc_potagers.modifier_role_membre(
        test_db, jardin["owner"].id, jardin["potager"].id, jardin["lecteur"].id, "owner",
    )
    assert _role(test_db, jardin["potager"].id, jardin["lecteur"].id) == "owner"


# ── CA3 — Se rétrograder, sous condition ────────────────────────────────────

def test_ca3_un_owner_peut_se_retrograder_s_il_en_reste_un_autre(test_db, jardin):
    """Scénario Gherkin « Passer la main puis se retirer du pouvoir »."""
    potager_id = jardin["potager"].id
    svc_potagers.modifier_role_membre(test_db, jardin["owner"].id, potager_id, jardin["editeur"].id, "owner")

    membre = svc_potagers.modifier_role_membre(
        test_db, jardin["owner"].id, potager_id, jardin["owner"].id, "editor",
    )

    assert membre.role == "editor"
    assert _nb_owners(test_db, potager_id) == 1
    assert _role(test_db, potager_id, jardin["editeur"].id) == "owner"


def test_ca3_se_retrograder_en_lecteur_est_aussi_possible(test_db, jardin):
    potager_id = jardin["potager"].id
    svc_potagers.modifier_role_membre(test_db, jardin["owner"].id, potager_id, jardin["editeur"].id, "owner")

    svc_potagers.modifier_role_membre(test_db, jardin["owner"].id, potager_id, jardin["owner"].id, "lecteur")

    assert _role(test_db, potager_id, jardin["owner"].id) == "lecteur"


def test_ca3_le_dernier_owner_ne_peut_pas_se_retrograder(test_db, jardin):
    """Scénario Gherkin « Le dernier owner ne peut pas se rétrograder »."""
    potager_id = jardin["potager"].id

    with pytest.raises(svc_potagers.DernierOwnerError) as exc:
        svc_potagers.modifier_role_membre(test_db, jardin["owner"].id, potager_id, jardin["owner"].id, "editor")

    # Le message indique la marche à suivre : désigner d'abord un autre propriétaire.
    message = str(exc.value)
    assert "propriétaire" in message
    assert "Désigne d'abord un autre propriétaire" in message
    assert _role(test_db, potager_id, jardin["owner"].id) == "owner"


def test_ca3_deux_owners_qui_se_retrogradent_l_un_apres_l_autre_jamais_orphelin(test_db, jardin):
    """La course de deux rétrogradations simultanées, rejouée en séquence : la
    seconde voit le résultat de la première et se voit refuser."""
    potager_id = jardin["potager"].id
    svc_potagers.modifier_role_membre(test_db, jardin["owner"].id, potager_id, jardin["editeur"].id, "owner")

    svc_potagers.modifier_role_membre(test_db, jardin["owner"].id, potager_id, jardin["owner"].id, "editor")
    with pytest.raises(svc_potagers.DernierOwnerError):
        svc_potagers.modifier_role_membre(test_db, jardin["editeur"].id, potager_id, jardin["editeur"].id, "editor")

    assert _nb_owners(test_db, potager_id) == 1


# ── CA4 — Garde « dernier owner » : unique, partagée avec retirer_membre ────

def test_ca4_un_owner_peut_en_retrograder_un_autre_tant_qu_il_reste_un_owner(test_db, jardin):
    potager_id = jardin["potager"].id
    svc_potagers.modifier_role_membre(test_db, jardin["owner"].id, potager_id, jardin["editeur"].id, "owner")

    svc_potagers.modifier_role_membre(test_db, jardin["owner"].id, potager_id, jardin["editeur"].id, "lecteur")

    assert _role(test_db, potager_id, jardin["editeur"].id) == "lecteur"
    assert _nb_owners(test_db, potager_id) == 1


def test_ca4_non_regression_le_dernier_owner_ne_peut_pas_se_retirer(test_db, jardin):
    potager_id = jardin["potager"].id

    with pytest.raises(svc_potagers.DernierOwnerError):
        svc_potagers.retirer_membre(test_db, jardin["owner"].id, potager_id, jardin["owner"].id)

    assert _role(test_db, potager_id, jardin["owner"].id) == "owner"


def test_ca4_non_regression_retirer_un_membre_ordinaire_fonctionne_toujours(test_db, jardin):
    potager_id = jardin["potager"].id

    svc_potagers.retirer_membre(test_db, jardin["owner"].id, potager_id, jardin["lecteur"].id)

    assert _role(test_db, potager_id, jardin["lecteur"].id) is None


def test_ca4_non_regression_retrait_invalide_toujours_le_potager_actif(test_db, jardin):
    potager_id = jardin["potager"].id
    jardin["editeur"].potager_actif_id = potager_id
    test_db.commit()

    svc_potagers.retirer_membre(test_db, jardin["owner"].id, potager_id, jardin["editeur"].id)

    test_db.refresh(jardin["editeur"])
    assert jardin["editeur"].potager_actif_id is None


def test_ca4_non_regression_retirer_un_utilisateur_non_membre_leve_membre_inconnu(test_db, jardin):
    etranger = _creer_user(test_db, email="etranger@example.com")

    with pytest.raises(svc_potagers.MembreInconnuError):
        svc_potagers.retirer_membre(test_db, jardin["owner"].id, jardin["potager"].id, etranger.id)


def test_ca4_non_regression_un_editor_ne_peut_toujours_pas_retirer_un_membre(test_db, jardin):
    with pytest.raises(PermissionInsuffisanteError):
        svc_potagers.retirer_membre(test_db, jardin["editeur"].id, jardin["potager"].id, jardin["lecteur"].id)


def test_ca4_un_owner_peut_retirer_un_autre_owner_s_il_en_reste_un(test_db, jardin):
    potager_id = jardin["potager"].id
    svc_potagers.modifier_role_membre(test_db, jardin["owner"].id, potager_id, jardin["editeur"].id, "owner")

    svc_potagers.retirer_membre(test_db, jardin["owner"].id, potager_id, jardin["editeur"].id)

    assert _nb_owners(test_db, potager_id) == 1


def test_ca4_une_seule_regle_pour_changer_un_role_et_retirer_un_membre(test_db, jardin, monkeypatch):
    """« Trois chemins, une seule règle » : les deux chemins existants appellent la
    même fonction de garde (le troisième, le départ volontaire, est couvert par US-086)."""
    potager_id = jardin["potager"].id
    svc_potagers.modifier_role_membre(test_db, jardin["owner"].id, potager_id, jardin["editeur"].id, "owner")
    appels = []
    monkeypatch.setattr(
        svc_potagers, "_garantir_un_owner_restant",
        lambda db, potager, membre, action, *a, **kw: appels.append(action),
    )

    # Chemin 1 : rétrograder un owner.
    svc_potagers.modifier_role_membre(test_db, jardin["owner"].id, potager_id, jardin["editeur"].id, "lecteur")
    # Chemin 2 : retirer un owner (ici lui-même — la garde, neutralisée, laisse faire).
    svc_potagers.retirer_membre(test_db, jardin["owner"].id, potager_id, jardin["owner"].id)

    assert len(appels) == 2


def test_ca4_la_garde_pose_un_verrou_sur_les_owners_dans_la_transaction(test_db, jardin, monkeypatch):
    """Course entre deux rétrogradations : la garde relit les owners sous
    `SELECT … FOR UPDATE` (ignoré par SQLite, décisif sous PostgreSQL)."""
    potager_id = jardin["potager"].id
    svc_potagers.modifier_role_membre(test_db, jardin["owner"].id, potager_id, jardin["editeur"].id, "owner")
    verrous = []
    original = Query.with_for_update

    def _espion(self, *args, **kwargs):
        verrous.append(True)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Query, "with_for_update", _espion)

    svc_potagers.modifier_role_membre(test_db, jardin["owner"].id, potager_id, jardin["owner"].id, "editor")

    assert verrous


def test_ca4_la_garde_ne_bloque_jamais_un_membre_qui_n_est_pas_owner(test_db, jardin):
    """Un potager sans owner (donnée héritée) ne doit pas bloquer la sortie d'un simple membre."""
    potager_id = jardin["potager"].id
    test_db.query(PotagerMembre).filter(
        PotagerMembre.potager_id == potager_id, PotagerMembre.role == "owner"
    ).update({"role": "editor"})
    test_db.commit()

    svc_potagers._garantir_un_owner_restant(test_db, potager_id, jardin["lecteur"].id, "quitter")  # ne lève pas


# ── CA5 — Un editor ou un lecteur ne change aucun rôle ──────────────────────

def test_ca5_un_editor_ne_peut_pas_se_promouvoir_owner(test_db, jardin):
    """Scénario Gherkin « Un editor ne peut pas changer de rôle »."""
    potager_id = jardin["potager"].id

    with pytest.raises(PermissionInsuffisanteError):
        svc_potagers.modifier_role_membre(test_db, jardin["editeur"].id, potager_id, jardin["editeur"].id, "owner")

    assert _role(test_db, potager_id, jardin["editeur"].id) == "editor"


def test_ca5_un_editor_ne_peut_pas_modifier_le_role_d_un_autre(test_db, jardin):
    with pytest.raises(PermissionInsuffisanteError):
        svc_potagers.modifier_role_membre(
            test_db, jardin["editeur"].id, jardin["potager"].id, jardin["lecteur"].id, "editor",
        )


def test_ca5_un_lecteur_ne_peut_modifier_aucun_role_y_compris_le_sien(test_db, jardin):
    potager_id = jardin["potager"].id

    with pytest.raises(PermissionInsuffisanteError):
        svc_potagers.modifier_role_membre(test_db, jardin["lecteur"].id, potager_id, jardin["lecteur"].id, "editor")

    assert _role(test_db, potager_id, jardin["lecteur"].id) == "lecteur"


def test_ca5_un_non_membre_ne_peut_rien_modifier(test_db, jardin):
    intrus = _creer_user(test_db, email="intrus@example.com")

    with pytest.raises(PermissionInsuffisanteError):
        svc_potagers.modifier_role_membre(
            test_db, intrus.id, jardin["potager"].id, jardin["lecteur"].id, "owner",
        )


# ── CA1 — Rôles acceptés, membre inconnu, idempotence ───────────────────────

@pytest.mark.parametrize("role", ["owner", "editor", "lecteur"])
def test_ca1_les_trois_roles_sont_acceptes(test_db, jardin, role):
    svc_potagers.modifier_role_membre(
        test_db, jardin["owner"].id, jardin["potager"].id, jardin["editeur"].id, role,
    )
    assert _role(test_db, jardin["potager"].id, jardin["editeur"].id) == role


@pytest.mark.parametrize("role", ["admin", "", "OWNER", "proprietaire"])
def test_ca1_un_role_inconnu_est_refuse(test_db, jardin, role):
    with pytest.raises(svc_potagers.RoleInvalideError):
        svc_potagers.modifier_role_membre(
            test_db, jardin["owner"].id, jardin["potager"].id, jardin["editeur"].id, role,
        )
    assert _role(test_db, jardin["potager"].id, jardin["editeur"].id) == "editor"


def test_ca1_un_membre_inconnu_du_potager_est_refuse(test_db, jardin):
    etranger = _creer_user(test_db, email="etranger@example.com")

    with pytest.raises(svc_potagers.MembreInconnuError):
        svc_potagers.modifier_role_membre(
            test_db, jardin["owner"].id, jardin["potager"].id, etranger.id, "editor",
        )


def test_ca1_demander_le_role_actuel_est_sans_effet_et_sans_notification(test_db, jardin, monkeypatch):
    jardin["editeur"].telegram_chat_id = 777
    test_db.commit()
    appels = []
    monkeypatch.setattr("app.services.telegram_notify.envoyer_message", lambda *a: appels.append(a) or True)

    membre = svc_potagers.modifier_role_membre(
        test_db, jardin["owner"].id, jardin["potager"].id, jardin["editeur"].id, "editor",
    )

    assert membre.role == "editor"
    assert appels == []


def test_l_action_vise_le_potager_de_l_url_pas_le_potager_actif(test_db, jardin):
    """Comme `retirer_membre`, l'action vise le potager de l'URL, pas le potager actif."""
    autre = svc_potagers.creer_potager(test_db, jardin["owner"].id, "Autre jardin")  # devient potager actif
    test_db.refresh(jardin["owner"])
    assert jardin["owner"].potager_actif_id == autre.id

    svc_potagers.modifier_role_membre(
        test_db, jardin["owner"].id, jardin["potager"].id, jardin["editeur"].id, "owner",
    )

    assert _role(test_db, jardin["potager"].id, jardin["editeur"].id) == "owner"


# ── Source de vérité des droits : potager_membres.role, pas proprietaire_id ─

def test_proprietaire_id_reste_le_createur_d_origine(test_db, jardin):
    potager_id = jardin["potager"].id
    svc_potagers.modifier_role_membre(test_db, jardin["owner"].id, potager_id, jardin["editeur"].id, "owner")
    svc_potagers.modifier_role_membre(test_db, jardin["owner"].id, potager_id, jardin["owner"].id, "lecteur")

    potager = test_db.query(Potager).filter(Potager.id == potager_id).first()
    assert potager.proprietaire_id == jardin["owner"].id  # le créateur d'origine, inchangé
    # …mais ses droits suivent `potager_membres.role`, pas cette colonne :
    with pytest.raises(PermissionInsuffisanteError):
        svc_potagers.archiver_potager(test_db, jardin["owner"].id, potager_id)
    assert svc_potagers.archiver_potager(test_db, jardin["editeur"].id, potager_id).etat == "archive"


# ── CA6 — Effet immédiat, sans reconnexion ──────────────────────────────────

def test_ca6_un_lecteur_passe_editor_peut_ecrire_des_sa_requete_suivante(test_db, jardin):
    """Scénario Gherkin « Corriger un rôle mal attribué »."""
    potager_id = jardin["potager"].id
    ctx_avant = svc_potager_actif.resoudre_tenant_context(test_db, jardin["lecteur"].id)
    assert ctx_avant.role == "lecteur"
    with pytest.raises(PermissionInsuffisanteError):
        svc_evenements.creer_evenement_observation(
            test_db, ctx_avant, {"constat": "Tout va bien"}, "tout va bien", "Observation",
        )

    svc_potagers.modifier_role_membre(test_db, jardin["owner"].id, potager_id, jardin["lecteur"].id, "editor")

    ctx_apres = svc_potager_actif.resoudre_tenant_context(test_db, jardin["lecteur"].id)
    assert ctx_apres.role == "editor"
    evenement = svc_evenements.creer_evenement_observation(
        test_db, ctx_apres, {"constat": "Tout va bien"}, "tout va bien", "Observation",
    )
    assert evenement.id is not None


def test_ca6_un_owner_retrograde_perd_ses_droits_des_la_requete_suivante(test_db, jardin):
    potager_id = jardin["potager"].id
    svc_potagers.modifier_role_membre(test_db, jardin["owner"].id, potager_id, jardin["editeur"].id, "owner")
    svc_potagers.modifier_role_membre(test_db, jardin["editeur"].id, potager_id, jardin["owner"].id, "editor")

    ctx = svc_potager_actif.resoudre_tenant_context(test_db, jardin["owner"].id)
    assert ctx.role == "editor"
    with pytest.raises(PermissionInsuffisanteError):
        svc_potagers.creer_invitation(test_db, jardin["owner"].id, potager_id, "lecteur")


# ── CA8 — Notification Telegram du membre concerné ──────────────────────────

def test_ca8_le_membre_lie_a_telegram_est_informe_de_son_nouveau_role(test_db, jardin, monkeypatch):
    jardin["lecteur"].telegram_chat_id = 4242
    test_db.commit()
    appels = []
    monkeypatch.setattr(
        "app.services.telegram_notify.envoyer_message",
        lambda chat_id, texte: appels.append((chat_id, texte)) or True,
    )

    svc_potagers.modifier_role_membre(
        test_db, jardin["owner"].id, jardin["potager"].id, jardin["lecteur"].id, "editor",
    )

    assert len(appels) == 1
    chat_id, texte = appels[0]
    assert chat_id == 4242
    assert "Emmanuel" in texte and "Jardin des Lilas" in texte
    assert "éditeur" in texte  # le nouveau rôle, en français
    assert "événements" in texte  # ce qu'il peut désormais faire


def test_ca8_la_promotion_owner_dit_ce_que_le_role_permet(test_db, jardin, monkeypatch):
    jardin["editeur"].telegram_chat_id = 4243
    test_db.commit()
    appels = []
    monkeypatch.setattr(
        "app.services.telegram_notify.envoyer_message",
        lambda chat_id, texte: appels.append(texte) or True,
    )

    svc_potagers.modifier_role_membre(
        test_db, jardin["owner"].id, jardin["potager"].id, jardin["editeur"].id, "owner",
    )

    assert "propriétaire" in appels[0]
    assert "archiver" in appels[0] and "membres" in appels[0]


def test_ca8_seul_le_membre_concerne_est_notifie(test_db, jardin, monkeypatch):
    jardin["editeur"].telegram_chat_id = 1
    jardin["lecteur"].telegram_chat_id = 2
    test_db.commit()
    destinataires = []
    monkeypatch.setattr(
        "app.services.telegram_notify.envoyer_message",
        lambda chat_id, texte: destinataires.append(chat_id) or True,
    )

    svc_potagers.modifier_role_membre(
        test_db, jardin["owner"].id, jardin["potager"].id, jardin["lecteur"].id, "editor",
    )

    assert destinataires == [2]


def test_ca8_membre_sans_compte_telegram_lie_aucun_envoi_et_le_changement_reussit(test_db, jardin, monkeypatch):
    def _echec(*a, **kw):
        raise AssertionError("envoyer_message ne doit pas être appelé sans compte Telegram lié")

    monkeypatch.setattr("app.services.telegram_notify.envoyer_message", _echec)

    membre = svc_potagers.modifier_role_membre(
        test_db, jardin["owner"].id, jardin["potager"].id, jardin["lecteur"].id, "editor",
    )
    assert membre.role == "editor"


def test_ca8_une_panne_telegram_ne_fait_pas_echouer_le_changement_de_role(test_db, jardin, monkeypatch):
    jardin["lecteur"].telegram_chat_id = 9
    test_db.commit()
    monkeypatch.setattr("app.services.telegram_notify.envoyer_message", lambda *a, **kw: False)

    membre = svc_potagers.modifier_role_membre(
        test_db, jardin["owner"].id, jardin["potager"].id, jardin["lecteur"].id, "editor",
    )
    assert membre.role == "editor"


def test_ca8_un_refus_ne_notifie_personne(test_db, jardin, monkeypatch):
    jardin["editeur"].telegram_chat_id = 5
    test_db.commit()
    appels = []
    monkeypatch.setattr("app.services.telegram_notify.envoyer_message", lambda *a: appels.append(a) or True)

    with pytest.raises(svc_potagers.DernierOwnerError):
        svc_potagers.modifier_role_membre(
            test_db, jardin["owner"].id, jardin["potager"].id, jardin["owner"].id, "editor",
        )
    assert appels == []


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
def api_jardin(app_client, _auth_engine):
    """Potager créé par l'API : `owner` (créateur), `editeur` et `lecteur` membres."""
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    owner = svc_auth.inscrire_utilisateur(db, "owner@example.com", "motdepasse123")
    editeur = svc_auth.inscrire_utilisateur(db, "editor@example.com", "motdepasse123")
    lecteur = svc_auth.inscrire_utilisateur(db, "lecteur@example.com", "motdepasse123")
    ids = {"owner": owner.id, "editeur": editeur.id, "lecteur": lecteur.id}
    db.close()

    headers = {nom: _auth_header(uid) for nom, uid in ids.items()}
    potager_id = app_client.post("/potagers", json={"nom": "Jardin partagé"}, headers=headers["owner"]).json()["id"]
    db = SessionLocal()
    db.add(PotagerMembre(user_id=ids["editeur"], potager_id=potager_id, role="editor"))
    db.add(PotagerMembre(user_id=ids["lecteur"], potager_id=potager_id, role="lecteur"))
    db.commit()
    db.close()
    return {"potager_id": potager_id, "ids": ids, "headers": headers}


def _url(api_jardin, nom):
    return f"/potagers/{api_jardin['potager_id']}/membres/{api_jardin['ids'][nom]}"


def test_endpoint_l_owner_change_le_role_d_un_membre(app_client, api_jardin):
    resp = app_client.patch(_url(api_jardin, "editeur"), json={"role": "owner"}, headers=api_jardin["headers"]["owner"])

    assert resp.status_code == 200
    assert resp.json() == {"user_id": api_jardin["ids"]["editeur"], "role": "owner"}
    liste = app_client.get(
        f"/potagers/{api_jardin['potager_id']}/membres", headers=api_jardin["headers"]["owner"],
    ).json()["membres"]
    assert {m["user_id"]: m["role"] for m in liste}[api_jardin["ids"]["editeur"]] == "owner"


def test_endpoint_ca6_le_membre_promu_gere_les_membres_des_la_requete_suivante(app_client, api_jardin):
    invitation = lambda: app_client.post(  # noqa: E731
        f"/potagers/{api_jardin['potager_id']}/invitations",
        json={"role_propose": "lecteur"}, headers=api_jardin["headers"]["editeur"],
    )
    assert invitation().status_code == 403  # editor : pas le droit d'inviter

    app_client.patch(_url(api_jardin, "editeur"), json={"role": "owner"}, headers=api_jardin["headers"]["owner"])

    assert invitation().status_code == 201  # même jeton, nouveau rôle, sans reconnexion


def test_endpoint_ca5_un_editor_ne_peut_pas_se_promouvoir_owner(app_client, api_jardin):
    resp = app_client.patch(_url(api_jardin, "editeur"), json={"role": "owner"}, headers=api_jardin["headers"]["editeur"])

    assert resp.status_code == 403
    liste = app_client.get(
        f"/potagers/{api_jardin['potager_id']}/membres", headers=api_jardin["headers"]["owner"],
    ).json()["membres"]
    assert {m["user_id"]: m["role"] for m in liste}[api_jardin["ids"]["editeur"]] == "editor"


def test_endpoint_ca3_le_dernier_owner_ne_peut_pas_se_retrograder_409(app_client, api_jardin):
    resp = app_client.patch(_url(api_jardin, "owner"), json={"role": "editor"}, headers=api_jardin["headers"]["owner"])

    assert resp.status_code == 409
    assert "Désigne d'abord un autre propriétaire" in resp.json()["detail"]


def test_endpoint_ca3_apres_promotion_le_createur_peut_se_retrograder(app_client, api_jardin):
    app_client.patch(_url(api_jardin, "editeur"), json={"role": "owner"}, headers=api_jardin["headers"]["owner"])

    resp = app_client.patch(_url(api_jardin, "owner"), json={"role": "editor"}, headers=api_jardin["headers"]["owner"])

    assert resp.status_code == 200
    assert resp.json()["role"] == "editor"


def test_endpoint_ca4_delete_du_dernier_owner_refuse_409(app_client, api_jardin):
    resp = app_client.delete(_url(api_jardin, "owner"), headers=api_jardin["headers"]["owner"])

    assert resp.status_code == 409
    assert "propriétaire" in resp.json()["detail"]


def test_endpoint_ca4_delete_d_un_membre_ordinaire_fonctionne_toujours(app_client, api_jardin):
    resp = app_client.delete(_url(api_jardin, "lecteur"), headers=api_jardin["headers"]["owner"])

    assert resp.status_code == 200
    assert resp.json() == {"success": True}


def test_endpoint_ca4_delete_d_un_non_membre_404_et_par_un_editor_403(app_client, api_jardin):
    inconnu = app_client.delete(
        f"/potagers/{api_jardin['potager_id']}/membres/99999", headers=api_jardin["headers"]["owner"],
    )
    assert inconnu.status_code == 404

    interdit = app_client.delete(_url(api_jardin, "lecteur"), headers=api_jardin["headers"]["editeur"])
    assert interdit.status_code == 403


def test_endpoint_role_inconnu_400(app_client, api_jardin):
    resp = app_client.patch(_url(api_jardin, "editeur"), json={"role": "admin"}, headers=api_jardin["headers"]["owner"])
    assert resp.status_code == 400


def test_endpoint_membre_inconnu_404(app_client, api_jardin):
    resp = app_client.patch(
        f"/potagers/{api_jardin['potager_id']}/membres/99999", json={"role": "editor"},
        headers=api_jardin["headers"]["owner"],
    )
    assert resp.status_code == 404


def test_endpoint_corps_sans_role_422(app_client, api_jardin):
    resp = app_client.patch(_url(api_jardin, "editeur"), json={}, headers=api_jardin["headers"]["owner"])
    assert resp.status_code == 422


def test_endpoint_exige_une_authentification(app_client, api_jardin):
    resp = app_client.patch(_url(api_jardin, "editeur"), json={"role": "owner"})
    assert resp.status_code in (401, 403)

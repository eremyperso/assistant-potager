"""
tests/test_us047_roles_permissions.py — [US-047] Contrôle des actions par rôle
-------------------------------------------------------------------------------
Couvre CA1 à CA7 : matrice de permissions centralisée (app/services/permissions.py),
garde en défense en profondeur dans app/services/evenements.py, garde précoce
(avant tout appel de parsing LLM) dans bot.py et main.py, message de refus
cohérent bot/PWA, et journalisation sans exception non gérée.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.context import TenantContext, current_context, set_current_context, default_context
from app.services import evenements as svc_evenements
from app.services import auth as svc_auth
from app.services import potager_actif as svc_potager_actif
from app.services.permissions import require_role, PermissionInsuffisanteError, NIVEAUX_ROLE
from database.db import Base
from database.models import Evenement, Parcelle, Potager, PotagerMembre


CTX_LECTEUR = TenantContext(user_id=1, potager_id=1, role="lecteur")
CTX_EDITOR  = TenantContext(user_id=2, potager_id=1, role="editor")
CTX_OWNER   = TenantContext(user_id=3, potager_id=1, role="owner")


# ── require_role() — matrice de permissions unique (CA1, CA2, CA3, CA6) ───────

def test_require_role_lecteur_refuse_niveau_editor():
    with pytest.raises(PermissionInsuffisanteError):
        require_role(CTX_LECTEUR, "editor", "enregistrer d'action")


def test_require_role_editor_autorise_niveau_editor():
    require_role(CTX_EDITOR, "editor", "enregistrer d'action")  # ne lève pas


def test_require_role_owner_autorise_niveau_editor():
    """[CA3] Owner a tous les droits de l'editor."""
    require_role(CTX_OWNER, "editor", "enregistrer d'action")  # ne lève pas


def test_require_role_editor_refuse_niveau_owner():
    """[CA2] Editor ne peut pas gérer les membres/paramètres (réservé owner)."""
    with pytest.raises(PermissionInsuffisanteError):
        require_role(CTX_EDITOR, "owner", "gérer les membres")


def test_require_role_role_absent_refuse():
    ctx_sans_role = TenantContext(user_id=4, potager_id=1, role=None)
    with pytest.raises(PermissionInsuffisanteError):
        require_role(ctx_sans_role, "editor", "enregistrer d'action")


def test_require_role_message_refus_explicite_et_coherent():
    """[CA5] Message identique bot/PWA — un seul gabarit."""
    with pytest.raises(PermissionInsuffisanteError) as exc_info:
        require_role(CTX_LECTEUR, "editor", "enregistrer d'action")
    assert str(exc_info.value) == "Tu es lecteur sur ce potager, tu ne peux pas enregistrer d'action."


def test_require_role_journalise_le_refus_sans_lever_autre_exception(caplog):
    """[CA7] Refus journalisé (log structuré), et seule PermissionInsuffisanteError
    est levée — pas d'exception non gérée côté appelant."""
    import logging
    with caplog.at_level(logging.WARNING, logger="potager"):
        with pytest.raises(PermissionInsuffisanteError):
            require_role(CTX_LECTEUR, "editor", "enregistrer d'action")
    assert any("Permission refusée" in r.message for r in caplog.records)


def test_niveaux_role_ordre_croissant():
    assert NIVEAUX_ROLE["lecteur"] < NIVEAUX_ROLE["editor"] < NIVEAUX_ROLE["owner"]


# ── Défense en profondeur — app/services/evenements.py (CA1, CA6) ─────────────

def test_ca1_creer_evenement_depuis_parse_refuse_lecteur(test_db):
    parsed = {"action": "recolte", "culture": "tomate", "quantite": 1, "unite": "kg"}
    with pytest.raises(PermissionInsuffisanteError):
        svc_evenements.creer_evenement_depuis_parse(test_db, CTX_LECTEUR, parsed, "texte")
    assert test_db.query(Evenement).count() == 0


def test_ca1_creer_evenement_ligne_refuse_lecteur(test_db):
    parsed = {"action": "arrosage", "culture": None, "quantite": None, "unite": None}
    with pytest.raises(PermissionInsuffisanteError):
        svc_evenements.creer_evenement_ligne(test_db, CTX_LECTEUR, parsed, "texte")
    assert test_db.query(Evenement).count() == 0


def test_ca1_creer_evenement_godet_refuse_lecteur(test_db):
    parsed = {"action": "mise_en_godet", "culture": "tomate", "nb_graines_semees": 5, "nb_plants_godets": 3}
    with pytest.raises(PermissionInsuffisanteError):
        svc_evenements.creer_evenement_godet(test_db, CTX_LECTEUR, parsed, "texte")
    assert test_db.query(Evenement).count() == 0


def test_ca1_creer_evenement_observation_refuse_lecteur(test_db):
    fields = {"constat": "feuilles jaunes", "culture": None}
    with pytest.raises(PermissionInsuffisanteError):
        svc_evenements.creer_evenement_observation(test_db, CTX_LECTEUR, fields, "texte", "Note")
    assert test_db.query(Evenement).count() == 0


def test_ca1_creer_evenement_perte_refuse_lecteur(test_db):
    item = {"action": "perte", "culture": "tomate", "quantite": 1}
    with pytest.raises(PermissionInsuffisanteError):
        svc_evenements.creer_evenement_perte(test_db, CTX_LECTEUR, item, "texte")
    assert test_db.query(Evenement).count() == 0


def test_ca1_corriger_evenement_refuse_lecteur(test_db):
    event = Evenement(type_action="recolte", culture="tomate", quantite=1, unite="kg", potager_id=1)
    test_db.add(event)
    test_db.commit()

    with pytest.raises(PermissionInsuffisanteError):
        svc_evenements.corriger_evenement(test_db, CTX_LECTEUR, event.id, {"quantite": 2}, " | corr")

    test_db.refresh(event)
    assert event.quantite == 1  # inchangé


def test_ca1_supprimer_evenement_refuse_lecteur(test_db):
    event = Evenement(type_action="recolte", culture="tomate", quantite=1, unite="kg", potager_id=1)
    test_db.add(event)
    test_db.commit()
    event_id = event.id

    with pytest.raises(PermissionInsuffisanteError):
        svc_evenements.supprimer_evenement(test_db, CTX_LECTEUR, event_id)

    assert test_db.query(Evenement).filter(Evenement.id == event_id).first() is not None


def test_editor_peut_enregistrer_un_evenement(test_db):
    """[CA2] Editor autorisé à saisir."""
    parsed = {"action": "arrosage", "culture": None, "quantite": None, "unite": None}
    event = svc_evenements.creer_evenement_ligne(test_db, CTX_EDITOR, parsed, "texte")
    assert event.id is not None


# ── CA2 — Lecture autorisée pour un lecteur (pas de garde sur les fonctions
#          de consultation) ────────────────────────────────────────────────

def test_ca2_lecteur_peut_consulter_historique(test_db):
    event = Evenement(type_action="arrosage", potager_id=1)
    test_db.add(event)
    test_db.commit()

    evenements = svc_evenements.evenements_recents(test_db, CTX_LECTEUR)
    assert len(evenements) == 1


# ── CA4 — bot.py : garde AVANT tout appel de parsing LLM ──────────────────────

@pytest.mark.asyncio
async def test_ca4_bot_parse_and_save_bloque_lecteur_sans_appel_llm(test_db):
    import bot as bot_module

    update = MagicMock()
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    update.callback_query = None

    set_current_context(CTX_LECTEUR)
    try:
        with (
            patch("bot.parse_commande") as mock_parse_commande,
            patch("bot.SessionLocal", return_value=test_db),
        ):
            await bot_module._parse_and_save(update, "j'ai récolté 2 kg de tomates")
    finally:
        set_current_context(default_context())

    mock_parse_commande.assert_not_called()  # [CA4] aucun appel LLM
    assert test_db.query(Evenement).count() == 0  # [rien n'est enregistré]
    update.message.reply_text.assert_awaited_once()
    texte_envoye = update.message.reply_text.call_args[0][0]
    assert "lecteur" in texte_envoye.lower()  # [CA5] message explicite


@pytest.mark.asyncio
async def test_ca4_bot_corr_start_bloque_lecteur(test_db):
    """Un lecteur ne peut pas entrer dans le flux /corriger (bloque aussi, en
    amont, l'appel Groq de _corr_apply)."""
    import bot as bot_module

    update = MagicMock()
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    tg_ctx = MagicMock()
    tg_ctx.user_data = {}

    set_current_context(CTX_LECTEUR)
    try:
        with patch("bot.SessionLocal", return_value=test_db):
            await bot_module._corr_start(update, tg_ctx)
    finally:
        set_current_context(default_context())

    update.message.reply_text.assert_awaited_once()
    assert "lecteur" in update.message.reply_text.call_args[0][0].lower()
    assert tg_ctx.user_data.get("mode") != "corr_search"


@pytest.mark.asyncio
async def test_editor_bot_parse_and_save_nest_pas_bloque_par_le_garde(test_db):
    """[CA2] Editor autorisé à saisir : le garde de rôle ne l'arrête pas — le
    pipeline de parsing/confirmation se poursuit normalement (comportement
    hors permissions, non ré-testé ici)."""
    import bot as bot_module

    update = MagicMock()
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    update.callback_query = None

    items = [{"action": "arrosage", "culture": None, "variete": None, "quantite": None, "unite": None, "parcelle": None}]

    set_current_context(CTX_EDITOR)
    try:
        with (
            patch("bot.parse_commande", return_value=items),
            patch("bot._normalize_items", return_value=items),
            patch("bot.SessionLocal", return_value=test_db),
        ):
            await bot_module._parse_and_save(update, "j'ai arrosé")
    finally:
        set_current_context(default_context())

    # Le garde n'a pas intercepté l'appel : aucun message de refus envoyé.
    for call in update.message.reply_text.call_args_list:
        assert "tu ne peux pas" not in call.args[0].lower()


# ── CA4 — main.py : POST /parse bloqué avant l'appel de parsing LLM ───────────

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


def _creer_potager_avec_role(db, nom, proprietaire_id, membre_id, role):
    potager = Potager(nom=nom, proprietaire_id=proprietaire_id)
    db.add(potager)
    db.commit()
    db.add(PotagerMembre(user_id=membre_id, potager_id=potager.id, role=role))
    db.commit()
    return potager


def test_ca4_post_parse_403_pour_lecteur_sans_appel_llm(app_client, _auth_engine):
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    proprietaire = _creer_compte_web(db, email="owner@example.com")
    lecteur = _creer_compte_web(db, email="lecteur@example.com")
    _creer_potager_avec_role(db, "Jardin partagé", proprietaire.id, lecteur.id, "lecteur")
    access_token = svc_auth.creer_access_token(lecteur.id)
    db.close()

    with patch("main.parse_commande") as mock_parse_commande:
        resp = app_client.post(
            "/parse",
            json={"texte": "j'ai récolté 2 kg de tomates"},
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert resp.status_code == 403
    assert "lecteur" in resp.json()["detail"].lower()
    mock_parse_commande.assert_not_called()  # [CA4]


def test_editor_post_parse_enregistre_normalement(app_client, _auth_engine):
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    proprietaire = _creer_compte_web(db, email="owner2@example.com")
    editor = _creer_compte_web(db, email="editor2@example.com")
    _creer_potager_avec_role(db, "Jardin partagé 2", proprietaire.id, editor.id, "editor")
    access_token = svc_auth.creer_access_token(editor.id)
    db.close()

    items = [{"action": "arrosage", "culture": None, "variete": None, "quantite": None, "unite": None}]
    with patch("main.parse_commande", return_value=items):
        resp = app_client.post(
            "/parse",
            json={"texte": "j'ai arrosé"},
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert resp.status_code == 200
    assert resp.json()["success"] is True

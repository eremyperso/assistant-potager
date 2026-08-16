"""
tests/test_us046_potager_actif.py — [US-046] Sélection et changement de potager actif
-------------------------------------------------------------------------------------
Couvre CA1 à CA6 : sélection automatique silencieuse (potager unique), listing,
changement explicite persistant, garde web/bot bloquant sur "aucun potager",
et résolution du TenantContext (contextvar) sans valeur en dur.
"""
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import auth as svc_auth
from app.services import potager_actif as svc_potager_actif
from app.services.context import current_context, set_current_context, default_context, TenantContext
from database.db import Base
from database.models import User, Potager, PotagerMembre
from bot import cmd_potager, _potager_select_cb, _verifier_liaison_ou_onboarding


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


# ── CA1 — Sélection automatique silencieuse (un seul potager) ─────────────

def test_us046_ca1_un_seul_potager_selectionne_et_persiste_automatiquement(test_db):
    user = _creer_user(test_db)
    potager = _creer_potager(test_db, "Jardin unique", user.id)

    ctx = svc_potager_actif.resoudre_tenant_context(test_db, user.id)

    assert ctx.potager_id == potager.id
    assert ctx.role == "owner"
    test_db.refresh(user)
    assert user.potager_actif_id == potager.id  # persisté silencieusement


# ── CA5 — Aucun potager ─────────────────────────────────────────────────────

def test_us046_ca5_aucun_potager_leve_erreur(test_db):
    user = _creer_user(test_db)
    with pytest.raises(svc_potager_actif.AucunPotagerError):
        svc_potager_actif.resoudre_tenant_context(test_db, user.id)


# ── CA2 — Listing des potagers ──────────────────────────────────────────────

def test_us046_ca2_lister_potagers_utilisateur(test_db):
    user = _creer_user(test_db)
    p1 = _creer_potager(test_db, "Jardin Nord", user.id)
    p2 = _creer_potager(test_db, "Jardin Sud", user.id)

    potagers = svc_potager_actif.lister_potagers_utilisateur(test_db, user.id)

    assert [p.id for p in potagers] == [p1.id, p2.id]


def test_us046_plusieurs_potagers_sans_choix_defaut_transitoire_non_persiste(test_db):
    """Plusieurs potagers, aucun choix encore fait → potager par défaut utilisé
    pour CETTE résolution mais PAS persisté (CA2 attend un choix explicite)."""
    user = _creer_user(test_db)
    p1 = _creer_potager(test_db, "Jardin Nord", user.id)
    _creer_potager(test_db, "Jardin Sud", user.id)

    ctx = svc_potager_actif.resoudre_tenant_context(test_db, user.id)

    assert ctx.potager_id == p1.id
    test_db.refresh(user)
    assert user.potager_actif_id is None  # non persisté


# ── CA2, CA3, CA4 — Changement explicite, immédiat et persistant ──────────

def test_us046_ca2_ca3_ca4_definir_potager_actif_change_et_persiste(test_db):
    user = _creer_user(test_db)
    _creer_potager(test_db, "Jardin Nord", user.id)
    p2 = _creer_potager(test_db, "Jardin Sud", user.id)

    ctx = svc_potager_actif.definir_potager_actif(test_db, user.id, p2.id)

    assert ctx.potager_id == p2.id
    test_db.refresh(user)
    assert user.potager_actif_id == p2.id  # [CA4] persistant

    # [CA3] Une résolution suivante reflète immédiatement le nouveau choix
    ctx2 = svc_potager_actif.resoudre_tenant_context(test_db, user.id)
    assert ctx2.potager_id == p2.id


def test_us046_definir_potager_actif_non_membre_leve_erreur(test_db):
    proprietaire = _creer_user(test_db, email="a@example.com")
    autre = _creer_user(test_db, email="b@example.com")
    potager = _creer_potager(test_db, "Jardin privé", proprietaire.id)

    with pytest.raises(svc_potager_actif.PotagerNonMembreError):
        svc_potager_actif.definir_potager_actif(test_db, autre.id, potager.id)


def test_us046_potager_actif_deja_defini_est_reutilise(test_db):
    user = _creer_user(test_db)
    p1 = _creer_potager(test_db, "Jardin Nord", user.id)
    p2 = _creer_potager(test_db, "Jardin Sud", user.id)
    svc_potager_actif.definir_potager_actif(test_db, user.id, p2.id)

    ctx = svc_potager_actif.resoudre_tenant_context(test_db, user.id)
    assert ctx.potager_id == p2.id
    assert ctx.potager_id != p1.id


# ── CA6 — current_context()/set_current_context() (contextvar) ────────────

def test_us046_ca6_current_context_retombe_sur_default_si_rien_arme():
    assert current_context() == default_context()


def test_us046_ca6_current_context_reflete_le_contexte_arme():
    ctx = TenantContext(user_id=7, potager_id=42, role="editor")
    set_current_context(ctx)
    try:
        assert current_context() == ctx
    finally:
        set_current_context(default_context())  # reset pour ne pas polluer les autres tests


# ── CA5/CA6 (bot) — Garde bloquant si aucun potager ────────────────────────

def _mock_update_texte(texte, chat_id=555):
    update = MagicMock()
    update.effective_chat.id = chat_id
    update.message.text = texte
    update.message.reply_text = AsyncMock()
    return update


@pytest.mark.asyncio
async def test_us046_ca5_bot_bloque_chat_lie_sans_potager(test_db):
    user = _creer_user(test_db, telegram_chat_id=555)  # lié mais AUCUN potager

    update = _mock_update_texte("récolté 2 kg de tomates")
    tg_ctx = MagicMock()
    tg_ctx.user_data = {}

    with patch('bot.SessionLocal', return_value=test_db):
        resultat = await _verifier_liaison_ou_onboarding(update, tg_ctx)

    assert resultat is False
    update.message.reply_text.assert_awaited_once()
    assert "potager" in update.message.reply_text.call_args[0][0].lower()


# ── CA2 (bot) — /potager liste + callback de sélection ─────────────────────

@pytest.mark.asyncio
async def test_us046_cmd_potager_liste_les_potagers_avec_actif_marque(test_db):
    user = _creer_user(test_db, telegram_chat_id=777)
    _creer_potager(test_db, "Jardin Nord", user.id)
    _creer_potager(test_db, "Jardin Sud", user.id)

    update = MagicMock()
    update.message.reply_text = AsyncMock()
    tg_ctx = MagicMock()
    tg_ctx.user_data = {"tenant_user_id": user.id}

    with patch('bot.SessionLocal', return_value=test_db):
        await cmd_potager(update, tg_ctx)

    update.message.reply_text.assert_awaited_once()
    kwargs = update.message.reply_text.call_args[1]
    boutons = kwargs["reply_markup"].inline_keyboard
    assert len(boutons) == 2
    assert boutons[0][0].callback_data.startswith("potager_select_")


@pytest.mark.asyncio
async def test_us046_potager_select_cb_change_et_persiste(test_db):
    user = _creer_user(test_db, telegram_chat_id=888)
    user_id = user.id
    _creer_potager(test_db, "Jardin Nord", user.id)
    p2 = _creer_potager(test_db, "Jardin Sud", user.id)
    p2_id = p2.id

    update = MagicMock()
    update.callback_query.data = f"potager_select_{p2_id}"
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    tg_ctx = MagicMock()
    tg_ctx.user_data = {"tenant_user_id": user_id}

    with patch('bot.SessionLocal', return_value=test_db):
        await _potager_select_cb(update, tg_ctx)

    update.callback_query.edit_message_text.assert_awaited_once()
    assert "Jardin Sud" in update.callback_query.edit_message_text.call_args[0][0]
    recharge = test_db.query(User).filter(User.id == user_id).first()
    assert recharge.potager_actif_id == p2_id


@pytest.mark.asyncio
async def test_us046_potager_select_cb_refuse_si_non_membre(test_db):
    proprietaire = _creer_user(test_db, email="a@example.com")
    autre = _creer_user(test_db, email="b@example.com", telegram_chat_id=999)
    potager = _creer_potager(test_db, "Jardin privé", proprietaire.id)

    update = MagicMock()
    update.callback_query.data = f"potager_select_{potager.id}"
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    tg_ctx = MagicMock()
    tg_ctx.user_data = {"tenant_user_id": autre.id}

    with patch('bot.SessionLocal', return_value=test_db):
        await _potager_select_cb(update, tg_ctx)

    assert "pas membre" in update.callback_query.edit_message_text.call_args[0][0]


# ── Endpoints web /potagers ──────────────────────────────────────────────

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


def test_us046_get_potagers_liste_vide_si_aucun_potager(app_client, _auth_engine):
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    user = _creer_compte_web(db)
    access_token = svc_auth.creer_access_token(user.id)
    db.close()

    resp = app_client.get("/potagers", headers={"Authorization": f"Bearer {access_token}"})
    assert resp.status_code == 200  # [CA5] liste vide, pas une erreur
    assert resp.json() == {"potagers": []}


def test_us046_get_potagers_marque_le_potager_actif(app_client, _auth_engine):
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    user = _creer_compte_web(db)
    _creer_potager(db, "Jardin unique", user.id)
    access_token = svc_auth.creer_access_token(user.id)
    db.close()

    resp = app_client.get("/potagers", headers={"Authorization": f"Bearer {access_token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["potagers"]) == 1
    assert body["potagers"][0]["actif"] is True


def test_us046_post_activer_potager_change_le_potager(app_client, _auth_engine):
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    user = _creer_compte_web(db)
    _creer_potager(db, "Jardin Nord", user.id)
    p2 = _creer_potager(db, "Jardin Sud", user.id)
    p2_id = p2.id
    access_token = svc_auth.creer_access_token(user.id)
    db.close()

    resp = app_client.post(f"/potagers/{p2_id}/activer", headers={"Authorization": f"Bearer {access_token}"})
    assert resp.status_code == 200
    assert resp.json()["potager_id"] == p2_id


def test_us046_post_activer_potager_403_si_non_membre(app_client, _auth_engine):
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    proprietaire = _creer_compte_web(db, email="a@example.com")
    autre = _creer_compte_web(db, email="b@example.com")
    potager = _creer_potager(db, "Jardin privé", proprietaire.id)
    potager_id = potager.id
    access_token = svc_auth.creer_access_token(autre.id)
    db.close()

    resp = app_client.post(f"/potagers/{potager_id}/activer", headers={"Authorization": f"Bearer {access_token}"})
    assert resp.status_code == 403


def test_us046_ca5_endpoint_metier_409_si_aucun_potager(app_client, _auth_engine):
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    user = _creer_compte_web(db)  # aucun potager
    access_token = svc_auth.creer_access_token(user.id)
    db.close()

    resp = app_client.get("/cultures", headers={"Authorization": f"Bearer {access_token}"})
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "no_potager"


def test_us046_auth_generer_code_ne_necessite_pas_de_potager(app_client, _auth_engine):
    """[Fix architecture] /auth/lien/generer-code ne dépend que de l'identité —
    un utilisateur doit pouvoir lier son Telegram avant même d'avoir un potager."""
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    user = _creer_compte_web(db)  # aucun potager
    access_token = svc_auth.creer_access_token(user.id)
    db.close()

    resp = app_client.post("/auth/lien/generer-code", headers={"Authorization": f"Bearer {access_token}"})
    assert resp.status_code == 200

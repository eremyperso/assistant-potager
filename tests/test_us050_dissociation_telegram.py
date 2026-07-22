"""
tests/test_us050_dissociation_telegram.py — [US-050] Dissocier un chat Telegram d'un compte
----------------------------------------------------------------------------------------------
Couvre CA1 à CA7 : service delier_chat_id (symétrique de lier_chat_id), endpoint PWA
POST /auth/lien/delier (identité seule, sans potager requis), commande bot /delier
avec confirmation, indépendance vis-à-vis du rôle/potager (CA5), non-régression
sur le garde de liaison standard (US-045) pour le chat une fois dissocié.
"""
import logging
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import auth as svc_auth
from app.services import liaison_telegram as svc_liaison
from database.db import Base
from database.models import User
from bot import cmd_delier, _delier_confirm, handle_text, _COMMANDES_SANS_GARDE_LIAISON


def _creer_user(db, email="jardinier@example.com", **kwargs):
    user = User(email=email, mot_de_passe_hash="x", **kwargs)
    db.add(user)
    db.commit()
    return user


# ── Service — delier_chat_id (CA3, CA6, CA7) ────────────────────────────────

def test_ca3_ca6_delier_chat_id_dissocie_sans_toucher_au_reste(test_db):
    user = _creer_user(test_db, telegram_chat_id=555, potager_actif_id=None)
    user_id = user.id

    resultat = svc_liaison.delier_chat_id(test_db, user_id)

    assert resultat.telegram_chat_id is None
    test_db.refresh(user)
    assert user.telegram_chat_id is None
    assert user.email == "jardinier@example.com"  # [CA6] identité inchangée


def test_ca7_delier_chat_id_journalise(test_db, caplog):
    user = _creer_user(test_db, telegram_chat_id=555)
    with caplog.at_level(logging.INFO, logger="potager"):
        svc_liaison.delier_chat_id(test_db, user.id)
    assert any("Dissociation Telegram" in r.message for r in caplog.records)


def test_ca4_relier_apres_dissociation(test_db):
    """[Scénario Gherkin] Un chat dissocié peut immédiatement être relié via un
    nouveau code — au même compte ou à un autre."""
    user = _creer_user(test_db, telegram_chat_id=555)
    svc_liaison.delier_chat_id(test_db, user.id)

    liaison = svc_liaison.creer_code_liaison(test_db, user.id)
    relie = svc_liaison.lier_chat_id(test_db, liaison.code, 555)
    assert relie.telegram_chat_id == 555


# ── CA5 — Indépendance du rôle/potager ──────────────────────────────────────

def test_ca5_delier_chat_id_fonctionne_sans_aucun_potager(test_db):
    """Un utilisateur qui n'appartient à AUCUN potager doit pouvoir dissocier —
    l'action ne dépend jamais de TenantContext/require_role."""
    user = _creer_user(test_db, telegram_chat_id=555)  # aucun Potager/PotagerMembre créé
    resultat = svc_liaison.delier_chat_id(test_db, user.id)
    assert resultat.telegram_chat_id is None


# ── Bot — cmd_delier (CA2) ───────────────────────────────────────────────────

def _mock_update(chat_id=42424242, texte=""):
    update = MagicMock()
    update.effective_chat.id = chat_id
    update.message.text = texte
    update.message.reply_text = AsyncMock()
    return update


@pytest.mark.asyncio
async def test_cmd_delier_chat_non_lie_affiche_onboarding(test_db):
    update = _mock_update(chat_id=999)
    tg_ctx = MagicMock()
    tg_ctx.user_data = {}

    with patch('bot.SessionLocal', return_value=test_db):
        await cmd_delier(update, tg_ctx)

    update.message.reply_text.assert_awaited_once()
    assert "lier" in update.message.reply_text.call_args[0][0].lower()
    assert tg_ctx.user_data.get('mode') != 'delier_confirm'


@pytest.mark.asyncio
async def test_cmd_delier_chat_lie_propose_confirmation(test_db):
    user = _creer_user(test_db, telegram_chat_id=777)
    update = _mock_update(chat_id=777)
    tg_ctx = MagicMock()
    tg_ctx.user_data = {}

    with patch('bot.SessionLocal', return_value=test_db):
        await cmd_delier(update, tg_ctx)

    assert tg_ctx.user_data['mode'] == 'delier_confirm'
    assert tg_ctx.user_data['delier_user_id'] == user.id
    update.message.reply_text.assert_awaited_once()
    assert "reply_markup" in update.message.reply_text.call_args[1]
    # Le chat n'est pas encore dissocié tant que non confirmé
    recharge = test_db.query(User).filter(User.id == user.id).first()
    assert recharge.telegram_chat_id == 777


# ── Bot — _delier_confirm (CA2, CA3) ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_delier_confirm_oui_dissocie(test_db):
    user = _creer_user(test_db, telegram_chat_id=777)
    update = _mock_update(chat_id=777, texte="✅ Oui, délier")
    tg_ctx = MagicMock()
    tg_ctx.user_data = {'mode': 'delier_confirm', 'delier_user_id': user.id}

    with patch('bot.SessionLocal', return_value=test_db):
        await _delier_confirm(update, tg_ctx, "✅ Oui, délier")

    recharge = test_db.query(User).filter(User.id == user.id).first()
    assert recharge.telegram_chat_id is None
    assert tg_ctx.user_data['mode'] is None
    assert 'delier_user_id' not in tg_ctx.user_data
    update.message.reply_text.assert_awaited_once()
    assert "dissocié" in update.message.reply_text.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_delier_confirm_non_annule(test_db):
    user = _creer_user(test_db, telegram_chat_id=777)
    update = _mock_update(chat_id=777, texte="❌ Non, annuler")
    tg_ctx = MagicMock()
    tg_ctx.user_data = {'mode': 'delier_confirm', 'delier_user_id': user.id}

    with patch('bot.SessionLocal', return_value=test_db):
        await _delier_confirm(update, tg_ctx, "❌ Non, annuler")

    test_db.refresh(user)
    assert user.telegram_chat_id == 777  # [Scénario Gherkin] rien n'est modifié
    assert tg_ctx.user_data['mode'] is None
    update.message.reply_text.assert_awaited_once()
    assert "annulée" in update.message.reply_text.call_args[0][0].lower()


# ── CA5 — handle_text court-circuite le garde standard pour la confirmation ──

@pytest.mark.asyncio
async def test_ca5_handle_text_confirmation_ne_passe_pas_par_le_garde_potager(test_db):
    """Un utilisateur SANS potager, en pleine confirmation de dissociation, ne doit
    jamais recevoir le message 'aucun potager' — la confirmation est interceptée
    avant _verifier_liaison_ou_onboarding (qui exige un potager actif)."""
    user = _creer_user(test_db, telegram_chat_id=777)  # aucun potager
    update = _mock_update(chat_id=777, texte="oui")
    tg_ctx = MagicMock()
    tg_ctx.user_data = {'mode': 'delier_confirm', 'delier_user_id': user.id}

    with patch('bot.SessionLocal', return_value=test_db):
        await handle_text(update, tg_ctx)

    recharge = test_db.query(User).filter(User.id == user.id).first()
    assert recharge.telegram_chat_id is None  # la dissociation a bien eu lieu
    texte_envoye = update.message.reply_text.call_args[0][0]
    assert "potager" not in texte_envoye.lower()


# ── CA9 (non-régression US-045) — /delier reste hors garde de liaison standard ──

def test_delier_hors_garde_liaison_standard():
    assert "delier" in _COMMANDES_SANS_GARDE_LIAISON


# ── Endpoint web POST /auth/lien/delier (CA1) ────────────────────────────────

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


def test_ca1_endpoint_delier_protege_par_auth(app_client):
    resp = app_client.post("/auth/lien/delier")
    assert resp.status_code == 401


def test_ca1_endpoint_delier_dissocie(app_client, _auth_engine):
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    user = svc_auth.inscrire_utilisateur(db, "jardinier@example.com", "motdepasse123")
    user.telegram_chat_id = 555
    db.commit()
    access_token = svc_auth.creer_access_token(user.id)
    db.close()

    resp = app_client.post("/auth/lien/delier", headers={"Authorization": f"Bearer {access_token}"})
    assert resp.status_code == 200
    assert resp.json() == {"success": True}

    db = SessionLocal()
    refresh = db.query(User).filter(User.id == user.id).first()
    assert refresh.telegram_chat_id is None
    db.close()


def test_ca5_endpoint_delier_fonctionne_sans_potager(app_client, _auth_engine):
    """[CA5] Identité seule — aucun potager créé pour ce compte, l'endpoint ne
    doit jamais renvoyer l'erreur 409 'no_potager' réservée à get_current_user_ctx."""
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    user = svc_auth.inscrire_utilisateur(db, "sanspotager@example.com", "motdepasse123")
    user.telegram_chat_id = 321
    db.commit()
    access_token = svc_auth.creer_access_token(user.id)
    db.close()

    resp = app_client.post("/auth/lien/delier", headers={"Authorization": f"Bearer {access_token}"})
    assert resp.status_code == 200

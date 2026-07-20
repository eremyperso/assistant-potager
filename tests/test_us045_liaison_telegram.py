"""
tests/test_us045_liaison_telegram.py — [US-045] Liaison chat Telegram ⇄ compte web
-------------------------------------------------------------------------------------
Couvre CA1 à CA9 : génération de code (service + endpoint), validation (succès,
expiré, déjà utilisé, chat déjà lié), garde priorité 0 dans handle_voice/handle_text
ET sur toutes les commandes slash métier (aucun appel Groq/lecture de données sur
chat non lié), commande /lier, détection de code brut, non-régression start/help/lier.
"""
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import auth as svc_auth
from app.services import liaison_telegram as svc_liaison
from database.db import Base
from database.models import LiaisonTelegram, User
from bot import (
    cmd_lier, handle_voice, handle_text, _verifier_liaison_ou_onboarding,
    _construire_application, _COMMANDES_SANS_GARDE_LIAISON,
)


# ── CA1 — Génération de code ────────────────────────────────────────────────

def test_us045_ca1_creer_code_liaison_format_et_ttl(test_db):
    user = User(email="jardinier@example.com", mot_de_passe_hash="x")
    test_db.add(user)
    test_db.commit()

    liaison = svc_liaison.creer_code_liaison(test_db, user.id)

    assert 6 <= len(liaison.code) <= 8
    assert liaison.code.isalnum()
    assert liaison.user_id == user.id
    assert liaison.utilise_le is None
    delta = liaison.expire_le - liaison.cree_le
    assert timedelta(minutes=9) < delta <= timedelta(minutes=10, seconds=5)


# ── CA2 — Liaison réussie ────────────────────────────────────────────────────

def test_us045_ca2_lier_chat_id_reussi(test_db):
    user = User(email="jardinier@example.com", mot_de_passe_hash="x")
    test_db.add(user)
    test_db.commit()
    liaison = svc_liaison.creer_code_liaison(test_db, user.id)

    resultat = svc_liaison.lier_chat_id(test_db, liaison.code, 987654321)

    assert resultat.id == user.id
    assert resultat.telegram_chat_id == 987654321
    test_db.refresh(liaison)
    assert liaison.utilise_le is not None


# ── CA3 — Code expiré ───────────────────────────────────────────────────────

def test_us045_ca3_code_expire_refuse(test_db):
    user = User(email="jardinier@example.com", mot_de_passe_hash="x")
    test_db.add(user)
    test_db.commit()
    liaison = LiaisonTelegram(code="ABC234", user_id=user.id, expire_le=datetime.utcnow() - timedelta(minutes=1))
    test_db.add(liaison)
    test_db.commit()

    with pytest.raises(svc_liaison.CodeExpireError):
        svc_liaison.lier_chat_id(test_db, "ABC234", 111)


# ── CA4 — Code déjà utilisé ─────────────────────────────────────────────────

def test_us045_ca4_code_deja_utilise_refuse(test_db):
    user = User(email="jardinier@example.com", mot_de_passe_hash="x")
    test_db.add(user)
    test_db.commit()
    liaison = LiaisonTelegram(
        code="ABC234", user_id=user.id,
        expire_le=datetime.utcnow() + timedelta(minutes=5),
        utilise_le=datetime.utcnow(),
    )
    test_db.add(liaison)
    test_db.commit()

    with pytest.raises(svc_liaison.CodeDejaUtiliseError):
        svc_liaison.lier_chat_id(test_db, "ABC234", 111)


def test_us045_ca2_code_invalide_refuse(test_db):
    with pytest.raises(svc_liaison.CodeInvalideError):
        svc_liaison.lier_chat_id(test_db, "INEXISTANT", 111)


# ── CA5 — Chat déjà lié à un autre compte ──────────────────────────────────

def test_us045_ca5_chat_deja_lie_a_un_autre_compte_refuse(test_db):
    proprietaire = User(email="a@example.com", mot_de_passe_hash="x", telegram_chat_id=555)
    autre = User(email="b@example.com", mot_de_passe_hash="x")
    test_db.add_all([proprietaire, autre])
    test_db.commit()
    liaison = svc_liaison.creer_code_liaison(test_db, autre.id)

    with pytest.raises(svc_liaison.ChatDejaLieError):
        svc_liaison.lier_chat_id(test_db, liaison.code, 555)


# ── CA1 (endpoint web) — POST /auth/lien/generer-code ──────────────────────

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


def test_us045_ca1_endpoint_generer_code_protege_par_auth(app_client):
    resp = app_client.post("/auth/lien/generer-code")
    assert resp.status_code == 401


def test_us045_ca1_endpoint_generer_code_retourne_code(app_client, _auth_engine):
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    user = svc_auth.inscrire_utilisateur(db, "jardinier@example.com", "motdepasse123")
    access_token = svc_auth.creer_access_token(user.id)
    db.close()

    resp = app_client.post("/auth/lien/generer-code", headers={"Authorization": f"Bearer {access_token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert 6 <= len(body["code"]) <= 8
    assert "expire_le" in body


# ── CA6/CA7 — Garde priorité 0 : chat non lié, aucun appel Groq ────────────

def _mock_update_texte(texte, chat_id=42424242):
    update = MagicMock()
    update.effective_chat.id = chat_id
    update.message.text = texte
    update.message.reply_text = AsyncMock()
    return update


@pytest.mark.asyncio
async def test_us045_ca6_handle_text_chat_non_lie_bloque_avant_groq(test_db):
    update = _mock_update_texte("récolté 2 kg de tomates")
    tg_ctx = MagicMock()
    tg_ctx.user_data = {}

    with patch('bot.SessionLocal', return_value=test_db), \
         patch('bot.parse_message') as mock_parse:
        await handle_text(update, tg_ctx)

    mock_parse.assert_not_called()
    update.message.reply_text.assert_awaited_once()
    assert "relié" in update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_us045_ca6_handle_voice_chat_non_lie_bloque_avant_whisper(test_db):
    update = MagicMock()
    update.effective_chat.id = 42424242
    update.message.reply_text = AsyncMock()
    update.message.voice.get_file = AsyncMock()
    tg_ctx = MagicMock()
    tg_ctx.user_data = {}

    with patch('bot.SessionLocal', return_value=test_db), \
         patch('bot.groq_client') as mock_groq:
        await handle_voice(update, tg_ctx)

    update.message.voice.get_file.assert_not_called()
    mock_groq.audio.transcriptions.create.assert_not_called()
    update.message.reply_text.assert_awaited_once()
    assert "relié" in update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_us045_ca8_chat_lie_expose_user_id_dans_user_data(test_db):
    user = User(email="jardinier@example.com", mot_de_passe_hash="x", telegram_chat_id=42424242)
    test_db.add(user)
    test_db.commit()

    update = _mock_update_texte("récolté 2 kg de tomates")
    tg_ctx = MagicMock()
    tg_ctx.user_data = {}

    with patch('bot.SessionLocal', return_value=test_db):
        resultat = await _verifier_liaison_ou_onboarding(update, tg_ctx)

    assert resultat is True
    assert tg_ctx.user_data['tenant_user_id'] == user.id


# ── CA2 (bis) — Code brut envoyé en texte libre (sans /lier) ───────────────

@pytest.mark.asyncio
async def test_us045_ca2_code_brut_en_texte_libre_lie_le_chat(test_db):
    user = User(email="jardinier@example.com", mot_de_passe_hash="x")
    test_db.add(user)
    test_db.commit()
    liaison = svc_liaison.creer_code_liaison(test_db, user.id)

    update = _mock_update_texte(liaison.code, chat_id=13579)
    tg_ctx = MagicMock()
    tg_ctx.user_data = {}

    with patch('bot.SessionLocal', return_value=test_db):
        resultat = await _verifier_liaison_ou_onboarding(update, tg_ctx, liaison.code)

    assert resultat is True
    # La session test_db a été fermée (db.close()) par la garde comme en
    # production — on revérifie via une requête fraîche plutôt qu'un refresh.
    recharge = test_db.query(User).filter(User.id == user.id).first()
    assert recharge.telegram_chat_id == 13579
    update.message.reply_text.assert_awaited_once()
    assert "succès" in update.message.reply_text.call_args[0][0]


# ── /lier — commande explicite ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_us045_cmd_lier_sans_argument_affiche_usage(test_db):
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    tg_ctx = MagicMock()
    tg_ctx.args = []

    await cmd_lier(update, tg_ctx)

    update.message.reply_text.assert_awaited_once()
    assert "Usage" in update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_us045_cmd_lier_code_valide_lie_le_chat(test_db):
    user = User(email="jardinier@example.com", mot_de_passe_hash="x")
    test_db.add(user)
    test_db.commit()
    liaison = svc_liaison.creer_code_liaison(test_db, user.id)

    update = MagicMock()
    update.effective_chat.id = 2468
    update.message.reply_text = AsyncMock()
    tg_ctx = MagicMock()
    tg_ctx.args = [liaison.code]
    tg_ctx.user_data = {}

    with patch('bot.SessionLocal', return_value=test_db):
        await cmd_lier(update, tg_ctx)

    recharge = test_db.query(User).filter(User.id == user.id).first()
    assert recharge.telegram_chat_id == 2468
    assert "succès" in update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_us045_cmd_lier_code_expire_message_explicite(test_db):
    user = User(email="jardinier@example.com", mot_de_passe_hash="x")
    test_db.add(user)
    test_db.commit()
    liaison = LiaisonTelegram(code="EXPIRE1", user_id=user.id, expire_le=datetime.utcnow() - timedelta(minutes=1))
    test_db.add(liaison)
    test_db.commit()

    update = MagicMock()
    update.effective_chat.id = 999
    update.message.reply_text = AsyncMock()
    tg_ctx = MagicMock()
    tg_ctx.args = ["EXPIRE1"]

    with patch('bot.SessionLocal', return_value=test_db):
        await cmd_lier(update, tg_ctx)

    assert "expiré" in update.message.reply_text.call_args[0][0]


# ── CA6/CA7 (révisé) — Garde centralisé sur TOUTES les commandes slash métier ──
# Test par introspection (recommandé par le backlog) plutôt que par une liste
# figée : toute commande future non exemptée est automatiquement couverte par
# construction (_enregistrer_commande), ce test vérifie que ce mécanisme est
# bien en place pour l'ensemble des commandes réellement enregistrées.

def test_us045_ca6_ca7_toutes_les_commandes_metier_sont_gardees_sauf_onboarding():
    app = _construire_application()

    commandes_gardees = set()
    commandes_exemptees = set()

    for handlers in app.handlers.values():
        for h in handlers:
            if h.__class__.__name__ != "CommandHandler":
                continue
            for nom in h.commands:
                if getattr(h.callback, "_garde_liaison", False):
                    commandes_gardees.add(nom)
                else:
                    commandes_exemptees.add(nom)

    # [CA9] Exactement les commandes d'onboarding sont exemptées, rien de plus
    assert commandes_exemptees == _COMMANDES_SANS_GARDE_LIAISON

    # [CA6/CA7] Toute commande métier connue à ce jour est bien gardée
    commandes_metier_attendues = {
        "version", "stats", "historique", "ask", "corriger", "note",
        "tts", "tts_on", "tts_off", "meteo", "plan", "parcelle", "parcelles", "vendre",
    }
    assert commandes_metier_attendues <= commandes_gardees


@pytest.mark.asyncio
async def test_us045_ca6_commande_metier_bloquee_pour_chat_non_lie(test_db):
    """[CA6 révisé] /parcelle lister depuis un chat non lié → onboarding, pas de données."""
    from bot import cmd_parcelle

    update = MagicMock()
    update.effective_chat.id = 13131313
    update.message.reply_text = AsyncMock()
    tg_ctx = MagicMock()
    tg_ctx.args = ["lister"]

    with patch('bot.SessionLocal', return_value=test_db):
        await _avec_garde_liaison_test_helper(cmd_parcelle, update, tg_ctx)

    update.message.reply_text.assert_awaited_once()
    assert "relié" in update.message.reply_text.call_args[0][0]


async def _avec_garde_liaison_test_helper(handler, update, ctx):
    """Reproduit exactement le comportement de _avec_garde_liaison() pour tester
    un handler individuel sans reconstruire toute l'Application."""
    from bot import _avec_garde_liaison
    return await _avec_garde_liaison(handler)(update, ctx)


@pytest.mark.asyncio
async def test_us045_ca9_start_help_lier_accessibles_sans_liaison(test_db):
    """[CA9] Non-régression : /start, /help, /lier restent utilisables sans liaison."""
    from bot import cmd_start, cmd_help, _avec_garde_liaison

    for nom, handler in (("start", cmd_start), ("help", cmd_help), ("lier", cmd_lier)):
        assert nom in _COMMANDES_SANS_GARDE_LIAISON
        # Ces handlers ne sont jamais enveloppés par _avec_garde_liaison lors de
        # l'enregistrement réel (cf. test d'introspection ci-dessus) — ici on
        # vérifie juste qu'ils ne portent pas le marqueur de garde.
        assert not getattr(handler, "_garde_liaison", False)

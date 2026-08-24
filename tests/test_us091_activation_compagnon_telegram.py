"""
tests/test_us091_activation_compagnon_telegram.py — [US-091] Activer son
compagnon de terrain Telegram en un seul geste
--------------------------------------------------------------------------------
Couvre CA8 à CA13 (deep-link `/start <code>` côté bot — mêmes refus que /lier,
accueil contextualisé, tolérance à l'absence de potager, canal de push ouvert),
CA12 (non-régression + correctif : `/start` sans payload lit désormais le vrai
potager actif au lieu du potager #1 par défaut), CA17 (limitation de débit par
compte sur /auth/lien/generer-code) et CA18 (journalisation d'audit sans fuite
du code). CA1-CA7, CA14-CA16, CA19 sont visuels/éditoriaux — cf. rapport QA.
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
from app.services import telegram_notify as svc_telegram_notify
from database.db import Base
from database.models import LiaisonTelegram, User, Potager, PotagerMembre
from bot import cmd_start


# ── Fixtures partagées (bot.py — SQLite en mémoire, même moteur que conftest) ──

def _mock_update(chat_id=42424242, first_name="Rémy"):
    update = MagicMock()
    update.effective_chat.id = chat_id
    update.effective_user.first_name = first_name
    update.message.reply_text = AsyncMock()
    return update


def _donner_potager(db, user, nom="Potager test"):
    potager = Potager(nom=nom, proprietaire_id=user.id)
    db.add(potager)
    db.commit()
    db.add(PotagerMembre(user_id=user.id, potager_id=potager.id, role="owner"))
    db.commit()
    return potager


def _tg_ctx(args=None):
    ctx = MagicMock()
    ctx.args = args or []
    ctx.user_data = {}
    return ctx


# ── CA8 — /start <code> applique exactement les refus de /lier ─────────────

@pytest.mark.asyncio
async def test_us091_ca8_start_code_invalide_refuse(test_db):
    update = _mock_update()
    with patch('bot.SessionLocal', return_value=test_db):
        await cmd_start(update, _tg_ctx(["INEXISTANT"]))

    update.message.reply_text.assert_awaited_once()
    assert "invalide" in update.message.reply_text.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_us091_ca8_start_code_expire_refuse(test_db):
    user = User(email="jardinier@example.com", mot_de_passe_hash="x")
    test_db.add(user)
    test_db.commit()
    liaison = LiaisonTelegram(code="ABC234", user_id=user.id, expire_le=datetime.utcnow() - timedelta(minutes=1))
    test_db.add(liaison)
    test_db.commit()

    update = _mock_update()
    with patch('bot.SessionLocal', return_value=test_db):
        await cmd_start(update, _tg_ctx(["ABC234"]))

    assert "expiré" in update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_us091_ca8_start_code_deja_utilise_refuse(test_db):
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

    update = _mock_update()
    with patch('bot.SessionLocal', return_value=test_db):
        await cmd_start(update, _tg_ctx(["ABC234"]))

    assert "déjà été utilisé" in update.message.reply_text.call_args[0][0]


# ── CA9 — Chat déjà lié à un autre compte : refus + renvoi vers déliaison ──

@pytest.mark.asyncio
async def test_us091_ca9_chat_deja_lie_renvoie_vers_delier_pwa(test_db):
    proprietaire = User(email="a@example.com", mot_de_passe_hash="x", telegram_chat_id=555)
    autre = User(email="b@example.com", mot_de_passe_hash="x")
    test_db.add_all([proprietaire, autre])
    test_db.commit()
    liaison = svc_liaison.creer_code_liaison(test_db, autre.id)

    update = _mock_update(chat_id=555)
    with patch('bot.SessionLocal', return_value=test_db):
        await cmd_start(update, _tg_ctx([liaison.code]))

    message = update.message.reply_text.call_args[0][0]
    assert "déjà lié à un autre compte" in message
    assert "Déliez" in message and "application web" in message
    # Aucune seconde liaison : le chat 555 reste sur le compte propriétaire.
    recharge = test_db.query(User).filter(User.id == proprietaire.id).first()
    assert recharge.telegram_chat_id == 555


# ── CA10 — Accueil contextualisé (prénom + potager) après liaison réussie ──

@pytest.mark.asyncio
async def test_us091_ca10_liaison_reussie_message_contextualise(test_db):
    user = User(email="jardinier@example.com", mot_de_passe_hash="x")
    test_db.add(user)
    test_db.commit()
    _donner_potager(test_db, user, nom="Jardin de Vitry")
    liaison = svc_liaison.creer_code_liaison(test_db, user.id)
    user_id = user.id  # capturé avant que le handler ne ferme la session (db.close())

    update = _mock_update(chat_id=2468, first_name="Camille")
    with patch('bot.SessionLocal', return_value=test_db):
        await cmd_start(update, _tg_ctx([liaison.code]))

    message = update.message.reply_text.call_args[0][0]
    assert "Camille" in message
    assert "Jardin de Vitry" in message
    assert "activé" in message.lower()

    recharge = test_db.query(User).filter(User.id == user_id).first()
    assert recharge.telegram_chat_id == 2468


# ── CA11 — Liaison réussie même sans potager, aucun blocage ────────────────

@pytest.mark.asyncio
async def test_us091_ca11_liaison_reussie_sans_potager_aucun_blocage(test_db):
    user = User(email="sanspotager@example.com", mot_de_passe_hash="x")
    test_db.add(user)
    test_db.commit()
    liaison = svc_liaison.creer_code_liaison(test_db, user.id)

    update = _mock_update(chat_id=13131313)
    with patch('bot.SessionLocal', return_value=test_db):
        await cmd_start(update, _tg_ctx([liaison.code]))

    message = update.message.reply_text.call_args[0][0]
    assert "activé" in message.lower()
    assert "aucun potager" in message.lower() or "membre d'aucun potager" in message.lower()

    recharge = test_db.query(User).filter(User.id == user.id).first()
    assert recharge.telegram_chat_id == 13131313  # la liaison a bien eu lieu


# ── CA12 — /start sans payload ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_us091_ca12_start_sans_payload_chat_non_lie_onboarding(test_db):
    update = _mock_update(chat_id=99999999)
    with patch('bot.SessionLocal', return_value=test_db):
        await cmd_start(update, _tg_ctx())

    message = update.message.reply_text.call_args[0][0]
    assert "n'est pas encore reli" in message
    assert "lien d'activation" in message  # [CA12] geste enrichi, non-régression /lier conservée
    assert "/lier" in message


@pytest.mark.asyncio
async def test_us091_ca12_start_sans_payload_chat_lie_utilise_le_vrai_potager(test_db):
    """[Correctif] Avant US-091, /start sans payload lisait toujours le potager
    #1 par défaut (default_context()), quel que soit le chat appelant — un
    utilisateur lié à un AUTRE potager voyait les stats du potager #1. On force
    ici un potager #1 « leurre » avec des événements, pour prouver que le
    compteur affiché est bien celui du potager réellement actif de l'appelant."""
    from database.models import Evenement

    # Potager-leurre id=1 (premier créé) — n'appartient PAS à notre utilisateur.
    autre_proprio = User(email="autre@example.com", mot_de_passe_hash="x")
    test_db.add(autre_proprio)
    test_db.commit()
    potager_leurre = Potager(nom="Potager leurre", proprietaire_id=autre_proprio.id)
    test_db.add(potager_leurre)
    test_db.commit()
    assert potager_leurre.id == 1
    for _ in range(3):
        test_db.add(Evenement(type_action="recolte", potager_id=potager_leurre.id, date=datetime.utcnow()))
    test_db.commit()

    # Notre utilisateur, lié, avec son propre potager (id != 1) sans événement.
    user = User(email="jardinier@example.com", mot_de_passe_hash="x", telegram_chat_id=2222)
    test_db.add(user)
    test_db.commit()
    _donner_potager(test_db, user, nom="Mon potager")

    update = _mock_update(chat_id=2222)
    with patch('bot.SessionLocal', return_value=test_db):
        await cmd_start(update, _tg_ctx())

    message = update.message.reply_text.call_args[0][0]
    assert "0 événements" in message  # pas les 3 événements du potager-leurre #1


# ── CA13 — Le canal de push est ouvert immédiatement après la liaison ──────

@pytest.mark.asyncio
async def test_us091_ca13_envoi_proactif_apres_liaison_aboutit(test_db):
    user = User(email="jardinier@example.com", mot_de_passe_hash="x")
    test_db.add(user)
    test_db.commit()
    _donner_potager(test_db, user)
    liaison = svc_liaison.creer_code_liaison(test_db, user.id)

    update = _mock_update(chat_id=778899)
    with patch('bot.SessionLocal', return_value=test_db):
        await cmd_start(update, _tg_ctx([liaison.code]))

    with patch('app.services.telegram_notify.requests.post') as mock_post:
        mock_post.return_value = MagicMock(raise_for_status=lambda: None)
        ok = svc_telegram_notify.envoyer_message(778899, "Rappel arrosage 🌱")

    assert ok is True
    mock_post.assert_called_once()
    assert mock_post.call_args.kwargs["json"]["chat_id"] == 778899


# ── Config — bot_username déduit du token via getMe (jamais une variable ───
# séparée à resynchroniser à la main par environnement, cf. incident constaté
# en dev : un TELEGRAM_BOT_USERNAME configuré manuellement ne correspondait
# plus au bot du token réellement chargé) ──────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_cache_username_bot():
    """Le cache est un global de module — isole chaque test du précédent."""
    svc_telegram_notify._username_bot_cache = None
    yield
    svc_telegram_notify._username_bot_cache = None


def test_us091_obtenir_username_bot_succes_et_mis_en_cache():
    with patch('app.services.telegram_notify.requests.get') as mock_get:
        mock_get.return_value = MagicMock(
            raise_for_status=lambda: None,
            json=lambda: {"ok": True, "result": {"username": "mon_bot"}},
        )
        assert svc_telegram_notify.obtenir_username_bot() == "mon_bot"
        assert svc_telegram_notify.obtenir_username_bot() == "mon_bot"

    mock_get.assert_called_once()  # 2e appel servi depuis le cache, pas de 2e requête


def test_us091_obtenir_username_bot_echec_reseau_retourne_vide_et_ne_bloque_pas():
    import requests as requests_module

    with patch('app.services.telegram_notify.requests.get', side_effect=requests_module.RequestException("panne")):
        assert svc_telegram_notify.obtenir_username_bot() == ""


def test_us091_obtenir_username_bot_echec_non_mis_en_cache_reessaie():
    """Un échec transitoire ne doit pas condamner tout le process : le prochain
    appel retente au lieu de rester bloqué sur '' pour toujours."""
    import requests as requests_module

    with patch('app.services.telegram_notify.requests.get', side_effect=requests_module.RequestException("panne")):
        assert svc_telegram_notify.obtenir_username_bot() == ""

    with patch('app.services.telegram_notify.requests.get') as mock_get:
        mock_get.return_value = MagicMock(
            raise_for_status=lambda: None,
            json=lambda: {"ok": True, "result": {"username": "mon_bot"}},
        )
        assert svc_telegram_notify.obtenir_username_bot() == "mon_bot"


# ── CA18 — Journalisation d'audit, sans jamais loguer le code ──────────────

def test_us091_ca18_liaison_reussie_journalisee_sans_le_code(test_db, caplog):
    user = User(email="jardinier@example.com", mot_de_passe_hash="x")
    test_db.add(user)
    test_db.commit()
    liaison = svc_liaison.creer_code_liaison(test_db, user.id)

    with caplog.at_level("INFO", logger="potager"):
        svc_liaison.lier_chat_id(test_db, liaison.code, 4242)

    messages = [r.getMessage() for r in caplog.records]
    audit = [m for m in messages if "Liaison Telegram réussie" in m]
    assert len(audit) == 1
    assert str(user.id) in audit[0]
    assert "4242" in audit[0]
    assert liaison.code not in audit[0]


# ── CA17 — Limitation de débit sur /auth/lien/generer-code (5/heure/compte) ─

@pytest.fixture
def _rate_limit_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def rl_db(_rate_limit_engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_rate_limit_engine)
    db = SessionLocal()
    yield db
    db.rollback()
    db.close()


@pytest.fixture
def rl_client(_rate_limit_engine, monkeypatch):
    import main
    TestSessionLocal = sessionmaker(bind=_rate_limit_engine)
    monkeypatch.setattr(main, "SessionLocal", TestSessionLocal)
    main.app.state.limiter.reset()
    with TestClient(main.app) as c:
        yield c


def test_us091_ca17_rate_limit_generer_code_bloque_apres_5_par_compte(rl_client, rl_db):
    user = User(email="jardinier@example.com", mot_de_passe_hash="x")
    rl_db.add(user)
    rl_db.commit()
    token = svc_auth.creer_access_token(user.id)
    headers = {"Authorization": f"Bearer {token}"}

    statuses = [rl_client.post("/auth/lien/generer-code", headers=headers).status_code for _ in range(6)]

    assert statuses[:5] == [200] * 5
    assert statuses[5] == 429


def test_us091_ca17_codes_deja_generes_restent_utilisables_apres_blocage(rl_client, rl_db):
    """La limite bloque les NOUVELLES générations, pas les codes déjà émis."""
    user = User(email="jardinier@example.com", mot_de_passe_hash="x")
    rl_db.add(user)
    rl_db.commit()
    token = svc_auth.creer_access_token(user.id)
    headers = {"Authorization": f"Bearer {token}"}

    premier_code = rl_client.post("/auth/lien/generer-code", headers=headers).json()["code"]
    for _ in range(5):
        rl_client.post("/auth/lien/generer-code", headers=headers)

    resultat = svc_liaison.lier_chat_id(rl_db, premier_code, 321321)
    assert resultat.id == user.id


def test_us091_ca17_rate_limit_est_par_compte_pas_par_ip(rl_client, rl_db):
    """Deux comptes derrière la même IP (TestClient) ne se limitent pas l'un l'autre."""
    a = User(email="a@example.com", mot_de_passe_hash="x")
    b = User(email="b@example.com", mot_de_passe_hash="x")
    rl_db.add_all([a, b])
    rl_db.commit()
    token_a = svc_auth.creer_access_token(a.id)
    token_b = svc_auth.creer_access_token(b.id)

    for _ in range(5):
        rl_client.post("/auth/lien/generer-code", headers={"Authorization": f"Bearer {token_a}"})

    resp_b = rl_client.post("/auth/lien/generer-code", headers={"Authorization": f"Bearer {token_b}"})
    assert resp_b.status_code == 200

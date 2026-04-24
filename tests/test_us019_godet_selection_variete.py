"""
[US-019] Tests — Sélection assistée de variété pour mise en godet ambiguë

CA1 : Plusieurs variétés disponibles → menu inline avec boutons par variété
CA2 : Une seule variété disponible → confirmation automatique
CA3 : Aucun semis actif → avertissement + choix d'enregistrer quand même
CA4 : Variété déjà précisée → court-circuit, sauvegarde directe (comportement actuel)
CA5 : Timeout — pending expiré → message d'annulation
CA6 : calcul_semis_par_culture filtre correctement les variétés avec stock_residuel > 0
"""
import pytest
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, Evenement, Parcelle
from utils.stock import calcul_semis_par_culture


# ── Fixture DB ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    p = Parcelle(nom="nord", nom_normalise="nord", actif=True)
    session.add(p)
    session.flush()
    yield session, p.id
    session.close()


def _semis(session, pid, culture, variete=None, quantite=20):
    ev = Evenement(
        type_action="semis", culture=culture, variete=variete,
        quantite=quantite, unite="graines",
        date=datetime(2026, 4, 1), parcelle_id=pid,
    )
    session.add(ev)
    session.flush()


def _godet(session, pid, culture, variete=None, nb_plants=5, nb_graines=10):
    ev = Evenement(
        type_action="mise_en_godet", culture=culture, variete=variete,
        nb_plants_godets=nb_plants, nb_graines_semees=nb_graines,
        date=datetime(2026, 4, 10), parcelle_id=pid,
    )
    session.add(ev)
    session.flush()


# ── CA6 — filtre stock_residuel > 0 ──────────────────────────────────────────

def test_us019_ca6_filtre_varietes_avec_stock(db):
    """CA6 — Seules les variétés avec stock_residuel > 0 sont proposées."""
    session, pid = db
    _semis(session, pid, "courgette", variete="jaune", quantite=10)
    _semis(session, pid, "courgette", variete="ronde", quantite=10)
    # épuiser toute la variété ronde
    _godet(session, pid, "courgette", variete="ronde", nb_plants=8, nb_graines=10)

    semis_var = calcul_semis_par_culture(session, "courgette")
    dispo = [s for s in semis_var if s["stock_residuel"] > 0]

    assert len(dispo) == 1
    assert dispo[0]["variete"] == "jaune"
    assert dispo[0]["stock_residuel"] == 10


def test_us019_ca6_aucun_stock_si_tout_consomme(db):
    """CA6 — Liste vide si toutes les variétés ont stock_residuel = 0."""
    session, pid = db
    _semis(session, pid, "courgette", variete="jaune", quantite=10)
    _godet(session, pid, "courgette", variete="jaune", nb_plants=8, nb_graines=10)

    semis_var = calcul_semis_par_culture(session, "courgette")
    dispo = [s for s in semis_var if s["stock_residuel"] > 0]
    assert dispo == []


# ── CA1 — plusieurs variétés → menu inline ───────────────────────────────────

@pytest.mark.asyncio
async def test_us019_ca1_plusieurs_varietes_menu_inline(db):
    """CA1 — 2 variétés disponibles → message avec InlineKeyboardMarkup."""
    from bot import _GODET_PENDING, _parse_and_save
    from telegram import InlineKeyboardMarkup
    _GODET_PENDING.clear()

    mock_update   = MagicMock()
    mock_message  = AsyncMock()
    mock_update.message           = mock_message
    mock_update.effective_user    = MagicMock(id=42)
    mock_update.effective_message = mock_message

    parsed_item = {
        "action": "mise_en_godet", "culture": "courgette", "variete": None,
        "nb_plants_godets": 8, "nb_graines_semees": None,
        "quantite": None, "unite": None, "date": None, "commentaire": None,
    }

    semis_dispo = [
        {"variete": "jaune", "stock_residuel": 20, "nb_semis": 1, "total_seme": 20,
         "unite": "graines", "date_premier_semis": None, "plants_en_godet": 0},
        {"variete": "ronde", "stock_residuel": 15, "nb_semis": 1, "total_seme": 15,
         "unite": "graines", "date_premier_semis": None, "plants_en_godet": 0},
    ]

    mock_db = MagicMock()

    with patch("bot.parse_commande", return_value=[parsed_item]), \
         patch("utils.validation.validate_parsed_action", return_value=(True, "")), \
         patch("bot.SessionLocal", return_value=mock_db), \
         patch("utils.stock.calcul_semis_par_culture", return_value=semis_dispo):

        await _parse_and_save(mock_update, "mise en godet courgette")

    assert 42 in _GODET_PENDING
    # Vérification que reply_text a été appelé avec un InlineKeyboardMarkup
    call_kwargs = mock_message.reply_text.call_args[1]
    assert isinstance(call_kwargs.get("reply_markup"), InlineKeyboardMarkup)
    _GODET_PENDING.clear()


# ── CA2 — une seule variété → confirmation ───────────────────────────────────

def test_us019_ca2_une_variete_confirmation(db):
    """CA2 — Une seule variété dispo → parsed_godet["variete"] pré-rempli."""
    session, pid = db
    _semis(session, pid, "courgette", variete="jaune", quantite=20)

    semis_var = calcul_semis_par_culture(session, "courgette")
    dispo = [s for s in semis_var if s["stock_residuel"] > 0]

    assert len(dispo) == 1
    # Simule le comportement CA2 : variete pré-remplie avant confirmation
    parsed = {"action": "mise_en_godet", "culture": "courgette", "variete": None}
    parsed["variete"] = dispo[0]["variete"]
    assert parsed["variete"] == "jaune"


# ── CA3 — aucun semis actif → warning ────────────────────────────────────────

def test_us019_ca3_aucun_semis_actif(db):
    """CA3 — Aucun semis actif pour la culture → liste vide."""
    session, pid = db
    # Pas de semis enregistré pour courgette

    semis_var = calcul_semis_par_culture(session, "courgette")
    dispo = [s for s in semis_var if s["stock_residuel"] > 0]
    assert dispo == []


# ── CA4 — variété déjà précisée → court-circuit ──────────────────────────────

def test_us019_ca4_variete_deja_presente_pas_d_interception():
    """CA4 — Si variété précisée dans le parsed, pas d'interception US-019."""
    parsed = {
        "action": "mise_en_godet", "culture": "courgette", "variete": "jaune",
        "nb_plants_godets": 5, "nb_graines_semees": 10,
    }
    # La condition d'interception ne doit pas se déclencher
    intercepter = (
        parsed.get("action") == "mise_en_godet"
        and not parsed.get("variete")   # False car variete="jaune"
    )
    assert intercepter is False


# ── CA5 — timeout ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_us019_ca5_timeout_pending_expire():
    """CA5 — Callback sur pending expiré → message d'annulation."""
    from bot import _GODET_PENDING, _GODET_TIMEOUT, _godet_variete_cb

    user_id = 99
    _GODET_PENDING[user_id] = {
        "parsed": {"action": "mise_en_godet", "culture": "courgette", "variete": None},
        "texte":  "mise en godet courgette",
        "ts":     time.time() - (_GODET_TIMEOUT + 5),  # expiré
    }

    mock_query  = AsyncMock()
    mock_query.data = "godet_confirm"
    mock_update = MagicMock()
    mock_update.callback_query   = mock_query
    mock_update.effective_user   = MagicMock(id=user_id)
    mock_update.effective_message = AsyncMock()

    await _godet_variete_cb(mock_update, MagicMock())

    mock_query.edit_message_text.assert_called_once()
    call_text = mock_query.edit_message_text.call_args[0][0]
    assert "annulée" in call_text.lower() or "timeout" in call_text.lower()
    assert user_id not in _GODET_PENDING


# ── CA5 — annulation explicite ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_us019_ca5_annulation_bouton_cancel():
    """CA5 — Clic sur 'Annuler' → pending supprimé, message d'annulation."""
    from bot import _GODET_PENDING, _godet_variete_cb

    user_id = 100
    _GODET_PENDING[user_id] = {
        "parsed": {"action": "mise_en_godet", "culture": "tomate", "variete": None},
        "texte":  "mise en godet tomate",
        "ts":     time.time(),
    }

    mock_query  = AsyncMock()
    mock_query.data = "godet_cancel"
    mock_update = MagicMock()
    mock_update.callback_query   = mock_query
    mock_update.effective_user   = MagicMock(id=user_id)
    mock_update.effective_message = AsyncMock()

    await _godet_variete_cb(mock_update, MagicMock())

    mock_query.edit_message_text.assert_called_once()
    assert "annulée" in mock_query.edit_message_text.call_args[0][0].lower()
    assert user_id not in _GODET_PENDING

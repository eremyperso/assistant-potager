"""
[US-021] Tests — Confirmation avant enregistrement d'une action en base

CA1  : Résumé + boutons Confirmer/Annuler affichés après parsing d'une action
CA2  : Bouton Confirmer → enregistrement effectif en base
CA3  : Bouton Annuler → aucun enregistrement, message "Action annulée."
CA4  : Timeout expiré (> 60 s) → message d'expiration, aucun enregistrement
CA5  : Pending absent (double-clic) → message d'expiration
CA6  : Intents interrogation/stats/historique → pas de confirmation (exécution directe)
CA7  : _build_action_summary — rendu correct pour 1 et N actions
CA8  : Parcelle absente + parcelles actives → menu inline affiché avant confirmation
CA9  : Sélection parcelle via menu → résumé mis à jour + boutons Confirmer/Annuler
CA10 : Sélection "Sans parcelle" → parcelle=None dans items
CA11 : Aucune parcelle active en base → confirmation directe sans menu
CA12 : TTL de 1 min s'applique pendant la sélection de parcelle
"""
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

import bot as bot_module
from bot import (
    _build_action_summary,
    _ACTION_PENDING,
    _ACTION_TIMEOUT,
    _action_confirm_cb,
)


# ── Helpers ──────────────────────────────────────────────────────────────────────

def _make_update(user_id: int = 42, text: str = ""):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    update.effective_message = update.message
    return update


def _make_callback_update(user_id: int = 42, data: str = "action_confirm"):
    update = MagicMock()
    update.effective_user.id = user_id
    update.callback_query = AsyncMock()
    update.callback_query.data = data
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.effective_message = AsyncMock()
    update.effective_message.reply_text = AsyncMock()
    return update


def _ctx():
    return MagicMock()


# ── CA7 — _build_action_summary ───────────────────────────────────────────────

def test_us021_ca7_summary_un_item():
    """CA7 — Résumé lisible pour un seul item."""
    items = [{"action": "semis", "culture": "courgette", "variete": "jaune",
              "quantite": 20, "unite": "graines", "date": "2026-04-15", "parcelle": "serre"}]
    summary = _build_action_summary(items)
    assert "Je vais enregistrer" in summary
    assert "semis" in summary
    assert "courgette" in summary
    assert "jaune" in summary
    assert "20 graines" in summary
    assert "serre" in summary
    assert "C'est correct ?" in summary


def test_us021_ca7_summary_plusieurs_items():
    """CA7 — Résumé lisible pour plusieurs items."""
    items = [
        {"action": "semis",     "culture": "tomate",    "quantite": 10, "unite": "graines"},
        {"action": "plantation","culture": "courgette", "quantite": 3,  "unite": "plants"},
    ]
    summary = _build_action_summary(items)
    assert "2 actions" in summary
    assert "semis" in summary
    assert "plantation" in summary
    assert "C'est correct ?" in summary


def test_us021_ca7_summary_sans_quantite():
    """CA7 — Résumé sans quantité ni variété (action minimale)."""
    items = [{"action": "arrosage", "culture": "tomate"}]
    summary = _build_action_summary(items)
    assert "arrosage" in summary
    assert "tomate" in summary


# ── CA1 — Affichage résumé + boutons après parsing ───────────────────────────

@pytest.mark.asyncio
async def test_us021_ca1_affiche_confirmation_apres_parsing():
    """CA1 — _parse_and_save affiche le résumé et les boutons sans sauvegarder."""
    update = _make_update(user_id=1)
    parsed_item = {"action": "recolte", "culture": "tomate", "quantite": 2, "unite": "kg"}

    with (
        patch("bot.parse_commande", return_value=[parsed_item]),
        patch("utils.validation.validate_parsed_action", return_value=(True, "")),
        patch("bot._normalize_items", return_value=[parsed_item]),
    ):
        _ACTION_PENDING.pop(1, None)
        await bot_module._parse_and_save(update, "récolté 2 kg de tomates")

    # Doit afficher le résumé avec les boutons
    assert update.message.reply_text.called
    call_kwargs = update.message.reply_text.call_args
    text_sent = call_kwargs[0][0] if call_kwargs[0] else call_kwargs[1].get("text", "")
    assert "Je vais enregistrer" in text_sent or "recolte" in text_sent.lower() or "récolte" in text_sent.lower()

    # Doit stocker dans _ACTION_PENDING
    assert 1 in _ACTION_PENDING
    assert _ACTION_PENDING[1]["items"] == [parsed_item]
    _ACTION_PENDING.pop(1, None)


# ── CA2 — Confirmation → enregistrement effectif ────────────────────────────

@pytest.mark.asyncio
async def test_us021_ca2_confirmation_enregistre():
    """CA2 — Bouton Confirmer déclenche _do_save_items."""
    user_id = 2
    items = [{"action": "recolte", "culture": "tomate", "quantite": 2, "unite": "kg"}]
    _ACTION_PENDING[user_id] = {"items": items, "texte": "récolté 2 kg", "ts": time.time()}

    update = _make_callback_update(user_id=user_id, data="action_confirm")

    with patch("bot._do_save_items", new_callable=AsyncMock) as mock_save:
        await _action_confirm_cb(update, _ctx())

    mock_save.assert_awaited_once()
    args = mock_save.call_args[0]
    assert args[1] == items
    assert user_id not in _ACTION_PENDING


# ── CA3 — Annulation → aucun enregistrement ──────────────────────────────────

@pytest.mark.asyncio
async def test_us021_ca3_annulation_pas_enregistrement():
    """CA3 — Bouton Annuler → aucune sauvegarde, message d'annulation."""
    user_id = 3
    items = [{"action": "semis", "culture": "courgette"}]
    _ACTION_PENDING[user_id] = {"items": items, "texte": "semis courgette", "ts": time.time()}

    update = _make_callback_update(user_id=user_id, data="action_cancel")

    with patch("bot._do_save_items", new_callable=AsyncMock) as mock_save:
        await _action_confirm_cb(update, _ctx())

    mock_save.assert_not_awaited()
    update.callback_query.edit_message_text.assert_awaited_once()
    msg = update.callback_query.edit_message_text.call_args[0][0]
    assert "annulée" in msg.lower()
    assert user_id not in _ACTION_PENDING


# ── CA4 — Timeout expiré → message d'expiration ──────────────────────────────

@pytest.mark.asyncio
async def test_us021_ca4_timeout_expire():
    """CA4 — Pending plus vieux que 60 s → message d'expiration, pas de sauvegarde."""
    user_id = 4
    items = [{"action": "semis", "culture": "laitue"}]
    _ACTION_PENDING[user_id] = {
        "items": items, "texte": "semis laitue",
        "ts": time.time() - (_ACTION_TIMEOUT + 5),  # expiré
    }

    update = _make_callback_update(user_id=user_id, data="action_confirm")

    with patch("bot._do_save_items", new_callable=AsyncMock) as mock_save:
        await _action_confirm_cb(update, _ctx())

    mock_save.assert_not_awaited()
    update.callback_query.edit_message_text.assert_awaited_once()
    msg = update.callback_query.edit_message_text.call_args[0][0]
    assert "expir" in msg.lower() or "annul" in msg.lower()
    assert user_id not in _ACTION_PENDING


# ── CA5 — Pending absent (double-clic ou session perdue) ─────────────────────

@pytest.mark.asyncio
async def test_us021_ca5_pending_absent():
    """CA5 — Aucun pending pour cet utilisateur → message d'expiration."""
    user_id = 5
    _ACTION_PENDING.pop(user_id, None)

    update = _make_callback_update(user_id=user_id, data="action_confirm")

    with patch("bot._do_save_items", new_callable=AsyncMock) as mock_save:
        await _action_confirm_cb(update, _ctx())

    mock_save.assert_not_awaited()
    update.callback_query.edit_message_text.assert_awaited_once()
    msg = update.callback_query.edit_message_text.call_args[0][0]
    assert "expir" in msg.lower()


# ── CA6 — Questions ne déclenchent pas la confirmation ───────────────────────

@pytest.mark.asyncio
async def test_us021_ca6_question_pas_de_confirmation():
    """CA6 — Intent INTERROGER → _ask_question appelée, _ACTION_PENDING non modifié."""
    user_id = 6
    update = _make_update(user_id=user_id)

    # action=None déclenche reroutage vers _ask_question (US-011)
    parsed_question = {"action": None, "culture": None, "quantite": None}

    with (
        patch("bot.parse_commande", return_value=[parsed_question]),
        patch("bot._normalize_items", return_value=[parsed_question]),
        patch("utils.validation.validate_parsed_action", return_value=(False, "action None manquante — reroutage question")),
        patch("bot._ask_question", new_callable=AsyncMock) as mock_ask,
    ):
        _ACTION_PENDING.pop(user_id, None)
        await bot_module._parse_and_save(update, "combien de tomates ai-je récoltées ?")

    mock_ask.assert_awaited_once()
    assert user_id not in _ACTION_PENDING


# ── CA8 — Parcelle absente + parcelles actives → menu inline ─────────────────

@pytest.mark.asyncio
async def test_us021_ca8_menu_parcelle_affiche():
    """CA8 — Pas de parcelle détectée et parcelles actives → menu inline."""
    user_id = 8
    parsed_item = {"action": "plantation", "culture": "tomate", "quantite": 10, "unite": "plants"}

    fake_parcelle = MagicMock()
    fake_parcelle.nom = "zone-tomates"

    with (
        patch("bot.parse_commande", return_value=[parsed_item]),
        patch("utils.validation.validate_parsed_action", return_value=(True, "")),
        patch("bot._normalize_items", return_value=[parsed_item]),
        patch("bot.get_all_parcelles", return_value=[fake_parcelle]),
        patch("bot.SessionLocal"),
    ):
        _ACTION_PENDING.pop(user_id, None)
        update = _make_update(user_id=user_id)
        await bot_module._parse_and_save(update, "plantation 10 plants de tomate")

    # Le menu doit être affiché (reply_text appelé)
    assert update.message.reply_text.called
    call_kwargs = update.message.reply_text.call_args
    text_sent = call_kwargs[0][0] if call_kwargs[0] else call_kwargs[1].get("text", "")
    assert "Quelle parcelle" in text_sent or "parcelle" in text_sent.lower()

    # _parcelle_demandee doit être True dans pending
    assert user_id in _ACTION_PENDING
    assert _ACTION_PENDING[user_id]["items"][0].get("_parcelle_demandee") is True
    _ACTION_PENDING.pop(user_id, None)


# ── CA9 — Sélection parcelle → résumé + boutons Confirmer/Annuler ────────────

@pytest.mark.asyncio
async def test_us021_ca9_selection_parcelle_affiche_confirmation():
    """CA9 — Sélection parcelle via callback → items mis à jour + boutons Confirmer/Annuler."""
    user_id = 9
    items = [{"action": "plantation", "culture": "tomate", "quantite": 10,
              "unite": "plants", "_parcelle_demandee": True}]
    _ACTION_PENDING[user_id] = {"items": items, "texte": "plantation tomate", "ts": time.time()}

    update = _make_callback_update(user_id=user_id, data="action_parcelle:zone-tomates")

    with patch("bot._do_save_items", new_callable=AsyncMock) as mock_save:
        await _action_confirm_cb(update, _ctx())

    # Pas de sauvegarde à cette étape
    mock_save.assert_not_awaited()

    # Parcelle mise à jour dans items
    assert _ACTION_PENDING[user_id]["items"][0]["parcelle"] == "zone-tomates"
    assert "_parcelle_demandee" not in _ACTION_PENDING[user_id]["items"][0]

    # Boutons Confirmer/Annuler affichés
    update.callback_query.edit_message_text.assert_awaited_once()
    edit_kwargs = update.callback_query.edit_message_text.call_args
    markup = edit_kwargs[1].get("reply_markup") or (edit_kwargs[0][1] if len(edit_kwargs[0]) > 1 else None)
    assert markup is not None  # InlineKeyboardMarkup présent
    _ACTION_PENDING.pop(user_id, None)


# ── CA10 — "Sans parcelle" → parcelle=None dans items ───────────────────────

@pytest.mark.asyncio
async def test_us021_ca10_sans_parcelle():
    """CA10 — Choix 'Sans parcelle' → items[0]['parcelle'] = None."""
    user_id = 10
    items = [{"action": "arrosage", "culture": "tomate", "_parcelle_demandee": True}]
    _ACTION_PENDING[user_id] = {"items": items, "texte": "arrosage tomate", "ts": time.time()}

    update = _make_callback_update(user_id=user_id, data="action_parcelle_none")

    with patch("bot._do_save_items", new_callable=AsyncMock) as mock_save:
        await _action_confirm_cb(update, _ctx())

    mock_save.assert_not_awaited()
    assert _ACTION_PENDING[user_id]["items"][0]["parcelle"] is None
    assert "_parcelle_demandee" not in _ACTION_PENDING[user_id]["items"][0]
    update.callback_query.edit_message_text.assert_awaited_once()
    _ACTION_PENDING.pop(user_id, None)


# ── CA11 — Aucune parcelle active → confirmation directe sans menu ───────────

@pytest.mark.asyncio
async def test_us021_ca11_aucune_parcelle_active():
    """CA11 — Aucune parcelle active en base → confirmation directe (sans menu)."""
    user_id = 11
    parsed_item = {"action": "semis", "culture": "laitue", "quantite": 5, "unite": "graines"}

    with (
        patch("bot.parse_commande", return_value=[parsed_item]),
        patch("utils.validation.validate_parsed_action", return_value=(True, "")),
        patch("bot._normalize_items", return_value=[parsed_item]),
        patch("bot.get_all_parcelles", return_value=[]),  # aucune parcelle active
        patch("bot.SessionLocal"),
    ):
        _ACTION_PENDING.pop(user_id, None)
        update = _make_update(user_id=user_id)
        await bot_module._parse_and_save(update, "semis 5 graines laitue")

    # Doit afficher la confirmation directement (pas de "Quelle parcelle")
    assert update.message.reply_text.called
    call_kwargs = update.message.reply_text.call_args
    text_sent = call_kwargs[0][0] if call_kwargs[0] else call_kwargs[1].get("text", "")
    assert "Quelle parcelle" not in text_sent

    # Pending sans _parcelle_demandee
    assert user_id in _ACTION_PENDING
    assert _ACTION_PENDING[user_id]["items"][0].get("_parcelle_demandee") is not True
    _ACTION_PENDING.pop(user_id, None)


# ── CA12 — TTL s'applique pendant la sélection de parcelle ──────────────────

@pytest.mark.asyncio
async def test_us021_ca12_ttl_pendant_selection_parcelle():
    """CA12 — Pending expiré lors de la sélection de parcelle → message d'expiration."""
    user_id = 12
    items = [{"action": "semis", "culture": "radis", "_parcelle_demandee": True}]
    _ACTION_PENDING[user_id] = {
        "items": items, "texte": "semis radis",
        "ts": time.time() - (_ACTION_TIMEOUT + 5),  # expiré
    }

    update = _make_callback_update(user_id=user_id, data="action_parcelle:zone-nord")

    with patch("bot._do_save_items", new_callable=AsyncMock) as mock_save:
        await _action_confirm_cb(update, _ctx())

    mock_save.assert_not_awaited()
    update.callback_query.edit_message_text.assert_awaited_once()
    msg = update.callback_query.edit_message_text.call_args[0][0]
    assert "expir" in msg.lower() or "annul" in msg.lower()
    assert user_id not in _ACTION_PENDING

"""
[US-038] Tests — Saisie guidée de notes/observations par catégorie

CA1 : /note affiche un menu inline avec les 4 catégories
CA2 : Message texte détecté comme demande de note → même menu
CA3 : Sélection catégorie → question guidée adaptée posée
CA4 : Réponse libre → extraction Groq des champs pertinents
CA5 : Récapitulatif avant enregistrement avec boutons Confirmer/Annuler
CA6 : Confirmation → Evenement créé avec type_action="observation" et champs attendus
CA7 : Aucune colonne ajoutée — réutilisation stricte du modèle Evenement existant
CA9 : Annulation à tout moment (bouton ou mot-clé) → aucun enregistrement
"""
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import bot as bot_module
from bot import (
    _note_start,
    _note_category_selected,
    _note_details_received,
    _note_confirm_cb,
    _build_note_summary,
    _NOTE_PENDING,
    _NOTE_TIMEOUT,
)
from utils.notes import NOTE_CATEGORIES, is_note_request, match_note_category
from database.models import Evenement, Parcelle


# ── Helpers ──────────────────────────────────────────────────────────────────────

def _make_update(user_id: int = 42):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    update.effective_message = update.message
    return update


def _make_callback_update(user_id: int = 42, data: str = "note_confirm"):
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
    ctx = MagicMock()
    ctx.user_data = {}
    return ctx


# ── utils/notes.py — détection et matching ───────────────────────────────────

def test_us038_is_note_request_detecte_phrases_typiques():
    assert is_note_request("je veux noter une observation sur mes tomates")
    assert is_note_request("je veux noter que le sol est sec")
    assert is_note_request("Ajouter une note")
    assert not is_note_request("j'ai récolté 2 kg de tomates")
    assert not is_note_request("combien de tomates ai-je récolté ?")


def test_us038_match_note_category_variantes():
    assert match_note_category("🔍 Observation") == "observation"
    assert match_note_category("observation") == "observation"
    assert match_note_category("🐛 Maladie / ravageur") == "maladie"
    assert match_note_category("maladie") == "maladie"
    assert match_note_category("ravageur") == "maladie"
    assert match_note_category("💧 Arrosage (remarque)") == "arrosage"
    assert match_note_category("🌿 Paillage") == "paillage"
    assert match_note_category("paillage") == "paillage"
    assert match_note_category("n'importe quoi") is None


# ── CA1/CA2 — Démarrage du flux (menu de catégories) ─────────────────────────

@pytest.mark.asyncio
async def test_us038_ca1_note_start_affiche_menu_categories():
    update = _make_update(user_id=1)
    ctx = _ctx()

    await _note_start(update, ctx)

    assert update.message.reply_text.called
    assert ctx.user_data['mode'] == 'note_category'
    call_args = update.message.reply_text.call_args
    reply_markup = call_args[1].get("reply_markup")
    assert reply_markup is not None


# ── CA3 — Sélection de catégorie → question guidée ────────────────────────────

@pytest.mark.asyncio
async def test_us038_ca3_categorie_valide_pose_question_guidee():
    update = _make_update(user_id=2)
    ctx = _ctx()
    ctx.user_data['mode'] = 'note_category'

    await _note_category_selected(update, ctx, "🐛 Maladie / ravageur")

    assert ctx.user_data['note_category'] == 'maladie'
    assert ctx.user_data['mode'] == 'note_details'
    question_sent = update.message.reply_text.call_args[0][0]
    assert question_sent == NOTE_CATEGORIES["maladie"]["question"]


@pytest.mark.asyncio
async def test_us038_ca3_categorie_invalide_reprompt():
    update = _make_update(user_id=3)
    ctx = _ctx()
    ctx.user_data['mode'] = 'note_category'

    await _note_category_selected(update, ctx, "n'importe quoi")

    assert 'note_category' not in ctx.user_data
    assert ctx.user_data['mode'] == 'note_category'  # reste en attente de sélection
    msg = update.message.reply_text.call_args[0][0]
    assert "non reconnue" in msg.lower()


@pytest.mark.asyncio
async def test_us038_ca9_annulation_pendant_selection_categorie():
    update = _make_update(user_id=4)
    ctx = _ctx()
    ctx.user_data['mode'] = 'note_category'

    await _note_category_selected(update, ctx, "❌ Annuler")

    assert ctx.user_data.get('mode') is None
    msg = update.message.reply_text.call_args[0][0]
    assert "annulée" in msg.lower()


# ── CA4/CA5 — Extraction Groq + récapitulatif ────────────────────────────────

@pytest.mark.asyncio
async def test_us038_ca4_ca5_extraction_et_recapitulatif():
    user_id = 5
    update = _make_update(user_id=user_id)
    ctx = _ctx()
    ctx.user_data['mode'] = 'note_details'
    ctx.user_data['note_category'] = 'maladie'

    fields = {
        "culture": "tomate", "variete": None, "parcelle": "Nord",
        "constat": "mildiou sur les feuilles du bas", "traitement": "purin d'ortie",
        "duree_minutes": None, "date": None,
    }
    _NOTE_PENDING.pop(user_id, None)

    with patch("bot.extract_note_fields", return_value=fields) as mock_extract:
        await _note_details_received(
            update, ctx,
            "tomates parcelle Nord, mildiou sur les feuilles du bas, j'ai traité au purin d'ortie",
        )

    mock_extract.assert_called_once()
    assert mock_extract.call_args[0][0] == 'maladie'

    # mode nettoyé (interaction suivante = callback inline)
    assert ctx.user_data.get('mode') is None
    assert 'note_category' not in ctx.user_data

    # pending stocké pour la confirmation
    assert user_id in _NOTE_PENDING
    assert _NOTE_PENDING[user_id]["categorie"] == 'maladie'
    assert _NOTE_PENDING[user_id]["fields"] == fields

    # récapitulatif envoyé avec boutons inline
    call_args = update.message.reply_text.call_args
    recap_text = call_args[0][0]
    assert "mildiou sur les feuilles du bas" in recap_text
    assert "purin d'ortie" in recap_text
    assert call_args[1].get("reply_markup") is not None

    _NOTE_PENDING.pop(user_id, None)


@pytest.mark.asyncio
async def test_us038_ca9_annulation_pendant_saisie_details():
    update = _make_update(user_id=6)
    ctx = _ctx()
    ctx.user_data['mode'] = 'note_details'
    ctx.user_data['note_category'] = 'observation'

    with patch("bot.extract_note_fields") as mock_extract:
        await _note_details_received(update, ctx, "annuler")

    mock_extract.assert_not_called()
    assert ctx.user_data.get('mode') is None
    msg = update.message.reply_text.call_args[0][0]
    assert "annulée" in msg.lower()


def test_us038_build_note_summary_contient_categorie_et_constat():
    fields = {"culture": "courgette", "variete": None, "parcelle": None,
              "constat": "sol sec", "traitement": None, "duree_minutes": None, "date": None}
    summary = _build_note_summary("arrosage", fields)
    assert "Arrosage" in summary
    assert "sol sec" in summary
    assert "courgette" in summary
    assert "C'est correct ?" in summary


# ── CA6/CA7 — Confirmation → Evenement enregistré (modèle inchangé) ──────────

@pytest.mark.asyncio
async def test_us038_ca6_ca7_confirmation_enregistre_evenement(test_db):
    user_id = 7
    fields = {
        "culture": "tomate", "variete": None, "parcelle": None,
        "constat": "mildiou sur les feuilles du bas", "traitement": "purin d'ortie",
        "duree_minutes": None, "date": None,
    }
    _NOTE_PENDING[user_id] = {
        "categorie": "maladie", "fields": fields,
        "texte": "tomates mildiou, traité au purin d'ortie", "ts": time.time(),
    }

    update = _make_callback_update(user_id=user_id, data="note_confirm")

    with patch("bot.SessionLocal", return_value=test_db):
        await _note_confirm_cb(update, _ctx())

    assert user_id not in _NOTE_PENDING

    event = test_db.query(Evenement).order_by(Evenement.id.desc()).first()
    assert event is not None
    assert event.type_action == "observation"
    assert event.culture == "tomate"
    assert event.traitement == "purin d'ortie"
    assert event.commentaire == "[Maladie / ravageur] mildiou sur les feuilles du bas"
    assert event.texte_original == "tomates mildiou, traité au purin d'ortie"
    assert event.date is not None


@pytest.mark.asyncio
async def test_us038_ca6_resolution_parcelle(test_db):
    """CA6 — Une parcelle existante mentionnée dans la note est résolue et liée."""
    parcelle = Parcelle(nom="Nord", nom_normalise="nord", actif=True)
    test_db.add(parcelle)
    test_db.commit()
    parcelle_id = parcelle.id

    user_id = 8
    fields = {
        "culture": None, "variete": None, "parcelle": "Nord",
        "constat": "sol sec", "traitement": None, "duree_minutes": 15, "date": None,
    }
    _NOTE_PENDING[user_id] = {
        "categorie": "arrosage", "fields": fields,
        "texte": "sol sec parcelle Nord", "ts": time.time(),
    }

    update = _make_callback_update(user_id=user_id, data="note_confirm")

    with patch("bot.SessionLocal", return_value=test_db):
        await _note_confirm_cb(update, _ctx())

    event = test_db.query(Evenement).order_by(Evenement.id.desc()).first()
    assert event.parcelle_id == parcelle_id
    assert event.duree == 15


# ── CA9 — Annulation via callback ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_us038_ca9_annulation_callback_pas_enregistrement():
    user_id = 9
    fields = {"culture": None, "variete": None, "parcelle": None,
              "constat": "test", "traitement": None, "duree_minutes": None, "date": None}
    _NOTE_PENDING[user_id] = {"categorie": "observation", "fields": fields, "texte": "test", "ts": time.time()}

    update = _make_callback_update(user_id=user_id, data="note_cancel")

    with patch("bot._save_note_event", new_callable=AsyncMock) as mock_save:
        await _note_confirm_cb(update, _ctx())

    mock_save.assert_not_awaited()
    assert user_id not in _NOTE_PENDING
    update.callback_query.edit_message_text.assert_awaited_once()
    msg = update.callback_query.edit_message_text.call_args[0][0]
    assert "annulée" in msg.lower()


# ── CA9 — Timeout expiré ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_us038_timeout_expire_pas_enregistrement():
    user_id = 10
    fields = {"culture": None, "variete": None, "parcelle": None,
              "constat": "test", "traitement": None, "duree_minutes": None, "date": None}
    _NOTE_PENDING[user_id] = {
        "categorie": "observation", "fields": fields, "texte": "test",
        "ts": time.time() - (_NOTE_TIMEOUT + 5),
    }

    update = _make_callback_update(user_id=user_id, data="note_confirm")

    with patch("bot._save_note_event", new_callable=AsyncMock) as mock_save:
        await _note_confirm_cb(update, _ctx())

    mock_save.assert_not_awaited()
    assert user_id not in _NOTE_PENDING
    msg = update.callback_query.edit_message_text.call_args[0][0]
    assert "expir" in msg.lower()


@pytest.mark.asyncio
async def test_us038_pending_absent_message_expiration():
    user_id = 11
    _NOTE_PENDING.pop(user_id, None)

    update = _make_callback_update(user_id=user_id, data="note_confirm")

    with patch("bot._save_note_event", new_callable=AsyncMock) as mock_save:
        await _note_confirm_cb(update, _ctx())

    mock_save.assert_not_awaited()
    msg = update.callback_query.edit_message_text.call_args[0][0]
    assert "expir" in msg.lower()

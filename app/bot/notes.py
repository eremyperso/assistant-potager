"""Notes et observations libres [US-038].

Module extrait de l'ancien bot.py monolithique (découpage 2026-09).
"""
import time
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from database.db import SessionLocal
from llm.groq_client import extract_note_fields
from llm.passerelle import LLMIndisponibleError, MESSAGE_REPLI_IA
from utils.notes import NOTE_CATEGORIES, match_note_category
from utils.culture_resolve import resolve_culture, resolve_variete
from app.services.context import current_context
from app.services import evenements as svc_evenements
from .noyau import AFTER_RECORD_KEYBOARD, MENU_KEYBOARD, log
from .etat import _NOTE_PENDING, _NOTE_TIMEOUT


# ── [US-038] SAISIE GUIDÉE DE NOTES/OBSERVATIONS ────────────────────────────────
_NOTE_CATEGORY_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton(NOTE_CATEGORIES["observation"]["label"]), KeyboardButton(NOTE_CATEGORIES["maladie"]["label"])],
        [KeyboardButton(NOTE_CATEGORIES["arrosage"]["label"]),    KeyboardButton(NOTE_CATEGORIES["paillage"]["label"])],
        [KeyboardButton("❌ Annuler")],
    ],
    resize_keyboard=True,
)


_NOTE_CANCEL_KEYWORDS = {"❌ annuler", "annuler"}


def _note_reset(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    ctx.user_data.pop('mode', None)
    ctx.user_data.pop('note_category', None)


async def _note_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """[US-038 / CA1, CA2] Démarre le flux guidé : affiche le menu de catégories."""
    _note_reset(ctx)
    ctx.user_data['mode'] = 'note_category'
    await update.effective_message.reply_text(
        "📝 *Nouvelle note*\n\nQuelle catégorie souhaites-tu noter ?",
        parse_mode="Markdown",
        reply_markup=_NOTE_CATEGORY_KEYBOARD,
    )


async def _note_category_selected(update: Update, ctx: ContextTypes.DEFAULT_TYPE, texte: str) -> None:
    """[US-038 / CA3] Étape 2 — la catégorie est choisie, on pose la question guidée."""
    if texte.strip().lower() in _NOTE_CANCEL_KEYWORDS:
        _note_reset(ctx)
        await update.effective_message.reply_text("↩️ Note annulée.", reply_markup=MENU_KEYBOARD)
        return

    categorie = match_note_category(texte)
    if categorie is None:
        await update.effective_message.reply_text(
            "❓ Catégorie non reconnue. Choisis un des boutons ci-dessous :",
            reply_markup=_NOTE_CATEGORY_KEYBOARD,
        )
        return

    ctx.user_data['note_category'] = categorie
    ctx.user_data['mode'] = 'note_details'
    log.info(f"[US-038] Catégorie sélectionnée : {categorie}")
    await update.effective_message.reply_text(
        NOTE_CATEGORIES[categorie]["question"],
        reply_markup=ReplyKeyboardMarkup([["❌ Annuler"]], resize_keyboard=True),
    )


def _build_note_summary(categorie: str, fields: dict) -> str:
    label = NOTE_CATEGORIES[categorie]["label"]
    lines = [f"{label}\n"]
    if fields.get("culture"):
        lines.append(f"🥬 Culture : *{fields['culture']}*")
    if fields.get("variete"):
        lines.append(f"🏷 Variété : *{fields['variete']}*")
    if fields.get("parcelle"):
        lines.append(f"📍 Parcelle : *{fields['parcelle']}*")
    lines.append(f"📝 Constat : *{fields['constat']}*")
    if fields.get("traitement"):
        lines.append(f"🧪 Traitement / matériau : *{fields['traitement']}*")
    if fields.get("duree_minutes"):
        lines.append(f"⏱ Durée constatée : *{fields['duree_minutes']} min*")
    lines.append("\nC'est correct ?")
    return "\n".join(lines)


async def _note_details_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE, texte: str) -> None:
    """[US-038 / CA4, CA5] Étape 3 — extraction Groq des champs + récapitulatif."""
    import time

    if texte.strip().lower() in _NOTE_CANCEL_KEYWORDS:
        _note_reset(ctx)
        await update.effective_message.reply_text("↩️ Note annulée.", reply_markup=MENU_KEYBOARD)
        return

    categorie = ctx.user_data.get('note_category')
    if categorie is None:
        # État incohérent (ex: redémarrage du bot en plein flux) → on repart proprement
        await _note_start(update, ctx)
        return

    try:
        fields = extract_note_fields(categorie, texte, ctx=current_context())
    except LLMIndisponibleError:
        # [US-092 / CA9] Repli déclaré : la note n'est pas perdue mais elle n'est
        # pas structurée non plus — on garde le flux ouvert et on le dit.
        log.warning("⏳ NOTE            : IA indisponible, extraction des champs impossible")
        await update.effective_message.reply_text(
            f"⏳ {MESSAGE_REPLI_IA}.\n\n"
            "Ta note n'a pas été enregistrée — retente dans quelques minutes.",
            reply_markup=MENU_KEYBOARD,
        )
        _note_reset(ctx)
        return

    # [feedback] Résout culture/variete vers les valeurs canoniques déjà en base
    # (Groq peut renvoyer "haricot"/"nain" alors que la BDD a "haricot"/"vert nain Contender")
    if fields.get("culture"):
        db = SessionLocal()
        try:
            culture_resolue = resolve_culture(db, current_context().potager_id, fields["culture"])
            if culture_resolue != fields["culture"]:
                log.info(f"[US-038] Culture résolue : '{fields['culture']}' → '{culture_resolue}'")
            fields["culture"] = culture_resolue
            if fields.get("variete"):
                variete_resolue = resolve_variete(db, current_context().potager_id, culture_resolue, fields["variete"])
                if variete_resolue != fields["variete"]:
                    log.info(f"[US-038] Variété résolue : '{fields['variete']}' → '{variete_resolue}'")
                fields["variete"] = variete_resolue
        finally:
            db.close()

    _note_reset(ctx)

    user_id = update.effective_user.id
    _NOTE_PENDING[user_id] = {
        "categorie": categorie,
        "fields": fields,
        "texte": texte,
        "ts": time.time(),
    }

    summary = _build_note_summary(categorie, fields)
    buttons = [[
        InlineKeyboardButton("✅ Confirmer", callback_data="note_confirm"),
        InlineKeyboardButton("❌ Annuler",   callback_data="note_cancel"),
    ]]
    await update.effective_message.reply_text(
        summary, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons)
    )


async def _save_note_event(update: Update, pending: dict) -> None:
    """[US-038 / CA6, CA7] Sauvegarde l'Evenement observation — aucune colonne ajoutée."""
    categorie = pending["categorie"]
    fields    = pending["fields"]
    label     = NOTE_CATEGORIES[categorie]["label"].split(" ", 1)[-1]  # retire l'emoji

    db = SessionLocal()
    try:
        event = svc_evenements.creer_evenement_observation(db, current_context(), fields, pending["texte"], label)
    except Exception as e:
        db.rollback()
        await update.effective_message.reply_text(f"❌ Erreur base de données : {e}")
        return
    finally:
        db.close()

    await update.effective_message.reply_text(
        f"✅ *Note enregistrée* — {NOTE_CATEGORIES[categorie]['label']}",
        parse_mode="Markdown",
    )
    await update.effective_message.reply_text(
        "_Que voulez-vous faire ensuite ?_",
        parse_mode="Markdown",
        reply_markup=AFTER_RECORD_KEYBOARD,
    )


async def _note_confirm_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """[US-038 / CA5, CA9] Callback inline — confirmation ou annulation de la note."""
    import time
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    data    = query.data

    if data == "note_cancel":
        _NOTE_PENDING.pop(user_id, None)
        log.info(f"[US-038] Note annulée — user_id={user_id}")
        await query.edit_message_text("❌ Note annulée.", reply_markup=None)
        return

    pending = _NOTE_PENDING.get(user_id)
    if pending is None:
        await query.edit_message_text("⏱ Note expirée. Veuillez recommencer avec /note.")
        return

    if time.time() - pending["ts"] > _NOTE_TIMEOUT:
        _NOTE_PENDING.pop(user_id, None)
        await query.edit_message_text(f"⏱ *Confirmation expirée ({_NOTE_TIMEOUT} s), note annulée.*", parse_mode="Markdown")
        return

    _NOTE_PENDING.pop(user_id, None)
    await query.edit_message_text("⏳ Enregistrement en cours...", reply_markup=None)
    await _save_note_event(update, pending)

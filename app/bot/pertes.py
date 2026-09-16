"""Pertes et ventes de plants : choix de variété et enregistrement.

Module extrait de l'ancien bot.py monolithique (découpage 2026-09).
"""
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from database.db import SessionLocal
from utils.tts import send_voice_reply
from app.services.context import current_context
from app.services import evenements as svc_evenements
from .noyau import AFTER_RECORD_KEYBOARD, _md, log
from .etat import (
    _PERTE_PENDING,
    _PERTE_TIMEOUT,
    _VENDU_PENDING,
    _VENDU_TIMEOUT,
)
from .enregistrement import _build_recap, _build_recap_tts


async def _vendu_variete_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback inline — sélection de variété godet pour une vente ambiguë."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    pending = _VENDU_PENDING.pop(user_id, None)

    if pending is None:
        await query.edit_message_text("⏱ Action expirée. Veuillez re-saisir votre vente.")
        return

    import time as _time_mod
    if _time_mod.time() - pending["ts"] > _VENDU_TIMEOUT:
        await query.edit_message_text("⏱ *Action annulée* (timeout 60 s). Veuillez re-saisir.", parse_mode="Markdown")
        return

    data = query.data  # vendu_var:{variete} | vendu_cancel

    if data == "vendu_cancel":
        await query.edit_message_text("❌ Vente annulée.", reply_markup=None)
        return

    if data.startswith("vendu_var:"):
        variete = data[len("vendu_var:"):]
        variete = variete if variete != "__none__" else None
        item    = pending["item"]
        texte   = pending["texte"]
        item["variete"] = variete
        log.info("[vendu_cb] Variété '%s' sélectionnée pour '%s' — user_id=%s", variete, item.get("culture"), user_id)
        await query.edit_message_text(
            f"✅ Variété *{variete or 'non précisée'}* sélectionnée.",
            parse_mode="Markdown",
            reply_markup=None,
        )
        # _parse_and_save utilise update.message (None dans un callback) → utiliser _save_perte_item
        # qui utilise update.effective_message, compatible callback ET message
        await _save_perte_item(update, item, texte)


async def _save_perte_item(update: Update, item: dict, texte: str) -> None:
    """
    Sauvegarde directe d'un item perte ou perte_godet depuis un callback inline.

    N'utilise PAS _parse_and_save (qui nécessite update.message).
    Utilise update.effective_message qui fonctionne dans les contextes callback ET message.
    """
    db = SessionLocal()
    try:
        event = svc_evenements.creer_evenement_perte(db, current_context(), item, texte)
    except svc_evenements.EvenementInvalideError as e:
        db.rollback()
        log.warning(f"❌ PERTE INVALIDE : {e} | texte={texte!r}")
        await update.effective_message.reply_text(f"❌ {e}")
        return
    except Exception as e:
        db.rollback()
        await update.effective_message.reply_text(f"❌ Erreur base de données : {e}")
        return
    finally:
        db.close()

    recap = _build_recap(item, event.id)
    await update.effective_message.reply_text(recap, parse_mode="Markdown", reply_markup=AFTER_RECORD_KEYBOARD)
    await send_voice_reply(update, _build_recap_tts(item))


# ── [vendu/perte_godet] CALLBACK DISAMBIGUATION PERTE ────────────────────────────

def _stock_variete_jardin(v: dict) -> int:
    """Calcule le stock actif d'une variété au jardin."""
    from utils.stock import stock_actif_variete
    return stock_actif_variete(v)


def _variete_reelle(v: dict) -> str | None:
    """[fix bug EN PLACE non déduit] `calcul_stock_par_variete()` substitue déjà
    `variete=None` par le libellé humain LABEL_VARIETE_NON_PRECISEE pour l'affichage.
    Ramène ce libellé à None avant toute réutilisation comme donnée (callback_data,
    pré-remplissage d'un item) — sinon le libellé littéral finit stocké tel quel dans
    Evenement.variete au lieu de NULL, et devient invisible à l'agrégation des pertes."""
    from utils.stock import LABEL_VARIETE_NON_PRECISEE
    variete = v.get("variete")
    return None if not variete or variete == LABEL_VARIETE_NON_PRECISEE else variete


async def _handle_perte_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Flux disambiguation perte en 2 étapes :
      Étape 1 : potager ou pépinière ? (toujours en premier)
      Étape 2 : quelle variété ? (uniquement si plusieurs variétés actives dans ce contexte)

    Callbacks :
      perte_source:jardin     → sélection contexte jardin
      perte_source:pepiniere  → sélection contexte pépinière
      perte_var_j:{variete}   → variété jardin choisie → save perte
      perte_var_p:{variete}   → variété pépinière choisie → save perte_godet
      perte_cancel            → annulation
    """
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    pending = _PERTE_PENDING.get(user_id)

    if pending is None:
        await query.edit_message_text("⏱ Action expirée. Veuillez re-saisir.")
        return

    import time as _time
    if _time.time() - pending["ts"] > _PERTE_TIMEOUT:
        _PERTE_PENDING.pop(user_id, None)
        await query.edit_message_text("⏱ *Action expirée* (timeout). Veuillez re-saisir.", parse_mode="Markdown")
        return

    data    = query.data
    item    = pending["item"]
    texte   = pending["texte"]
    culture = item.get("culture", "")
    qte     = item.get("quantite", "?")

    if data == "perte_cancel":
        _PERTE_PENDING.pop(user_id, None)
        await query.edit_message_text("❌ Annulé.", reply_markup=None)
        return

    # ── ÉTAPE 1 : contexte choisi → maintenant sélection variété ────────────

    if data == "perte_source:jardin":
        jardin_varietes = [v for v in pending.get("jardin_varietes", []) if _stock_variete_jardin(v) > 0]

        if len(jardin_varietes) == 0:
            # Aucune variété active au jardin → enregistrer sans variété
            _PERTE_PENDING.pop(user_id, None)
            item["action"] = "perte"
            await query.edit_message_text("🌿 Enregistrement perte au potager...", reply_markup=None)
            await _save_perte_item(update, item, texte)

        elif len(jardin_varietes) == 1:
            _PERTE_PENDING.pop(user_id, None)
            item["action"]  = "perte"
            item["variete"] = _variete_reelle(jardin_varietes[0])
            var_lbl = item["variete"] or "non précisée"
            await query.edit_message_text(f"🌿 *{culture} {var_lbl}* — enregistrement...", parse_mode="Markdown", reply_markup=None)
            await _save_perte_item(update, item, texte)

        else:
            # Plusieurs variétés actives au jardin → demander laquelle
            buttons = []
            for v in jardin_varietes:
                var   = v["variete"] or "non précisée"
                stock = _stock_variete_jardin(v)
                cb    = _variete_reelle(v) or "__none__"
                buttons.append([InlineKeyboardButton(f"🌿 {var} ({stock} plants actifs)", callback_data=f"perte_var_j:{cb}")])
            buttons.append([InlineKeyboardButton("❌ Annuler", callback_data="perte_cancel")])
            await query.edit_message_text(
                f"🌿 Quelle variété de *{_md(culture)}* au potager ?",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        return

    if data == "perte_source:pepiniere":
        godets_actifs = pending.get("godets", [])

        if len(godets_actifs) == 0:
            _PERTE_PENDING.pop(user_id, None)
            item["action"] = "perte_godet"
            item.pop("parcelle", None)
            await query.edit_message_text("🪴 Enregistrement perte pépinière...", reply_markup=None)
            await _save_perte_item(update, item, texte)

        elif len(godets_actifs) == 1:
            _PERTE_PENDING.pop(user_id, None)
            item["action"]  = "perte_godet"
            item["variete"] = godets_actifs[0]["variete"]
            item.pop("parcelle", None)
            var_lbl = item["variete"] or "non précisée"
            await query.edit_message_text(f"🪴 *{culture} {var_lbl}* — enregistrement...", parse_mode="Markdown", reply_markup=None)
            await _save_perte_item(update, item, texte)

        else:
            # Plusieurs variétés en godet → demander laquelle
            buttons = []
            for g in godets_actifs:
                var = g["variete"] or "non précisée"
                cb  = g["variete"] if g["variete"] else "__none__"
                buttons.append([InlineKeyboardButton(f"🪴 {var} ({g['stock_residuel_godet']} en godet)", callback_data=f"perte_var_p:{cb}")])
            buttons.append([InlineKeyboardButton("❌ Annuler", callback_data="perte_cancel")])
            await query.edit_message_text(
                f"🪴 Quelle variété de *{_md(culture)}* en pépinière ?",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        return

    # ── ÉTAPE 2 : variété choisie ────────────────────────────────────────────

    if data.startswith("perte_var_j:"):
        _PERTE_PENDING.pop(user_id, None)
        variete         = data[len("perte_var_j:"):]
        variete         = variete if variete != "__none__" else None
        item["action"]  = "perte"
        item["variete"] = variete
        var_lbl         = variete or "non précisée"
        log.info(f"[perte] Jardin variété={var_lbl}")
        await query.edit_message_text(f"🌿 *{culture} {var_lbl}* — enregistrement perte potager...", parse_mode="Markdown", reply_markup=None)
        await _save_perte_item(update, item, texte)
        return

    if data.startswith("perte_var_p:"):
        _PERTE_PENDING.pop(user_id, None)
        variete         = data[len("perte_var_p:"):]
        variete         = variete if variete != "__none__" else None
        item["action"]  = "perte_godet"
        item["variete"] = variete
        item.pop("parcelle", None)
        var_lbl         = variete or "non précisée"
        log.info(f"[perte] Pépinière variété={var_lbl}")
        await query.edit_message_text(f"🪴 *{culture} {var_lbl}* — enregistrement perte pépinière...", parse_mode="Markdown", reply_markup=None)
        await _save_perte_item(update, item, texte)
        return

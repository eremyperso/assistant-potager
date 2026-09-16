"""Mise en godet : choix du lot, rattachement aux graines, enregistrement.

Module extrait de l'ancien bot.py monolithique (découpage 2026-09).
"""
import time
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from database.db import SessionLocal
from utils.tts import send_voice_reply
from app.services.context import current_context
from app.services import evenements as svc_evenements
from app.services import stock as svc_stock
from .noyau import AFTER_RECORD_KEYBOARD, log
from .etat import (
    _GODET_GRAINES_PENDING,
    _GODET_GRAINES_TIMEOUT,
    _GODET_LOT_PENDING,
    _GODET_LOT_TIMEOUT,
    _GODET_PENDING,
    _GODET_TIMEOUT,
)
from .enregistrement import _build_recap, _build_recap_tts


def _lot_pressenti_pour_godet(parsed: dict) -> "dict | None":
    """
    [US-066 / CA1, CA4] Lot de semis auquel cette mise en godet va se rattacher,
    tel que `creer_evenement_godet` le résoudra : lot explicitement désigné, sinon
    unique candidat capable. Retourne None dès que le rattachement est incertain
    (aucun candidat, ou plusieurs) — il n'y a alors aucun reste précis à annoncer,
    donc aucune question à poser.
    """
    graines_requises = int(parsed.get("nb_graines_semees") or parsed.get("nb_plants_godets") or 0)
    db = SessionLocal()
    try:
        semis_id = parsed.get("origine_graines_id")
        if semis_id is not None:
            return svc_stock.lot_pepiniere_par_semis(db, current_context(), int(semis_id))
        candidats = svc_stock.lots_candidats_mise_en_godet(
            db, current_context(), parsed.get("culture") or "", parsed.get("variete"),
            graines_requises=graines_requises,
        )
        return candidats[0] if len(candidats) == 1 else None
    finally:
        db.close()


async def _demander_graines_godet_si_manquant(update: Update, parsed: dict, texte: str) -> bool:
    """
    [US-066 / CA1, CA2, CA4] Réclame le « sur N graines » d'une mise en godet quand
    il manque et qu'un lot de semis rattachable a encore des graines non soldées.

    Sans cette information, le lot reste en germination « indéterminée » à vie
    (US-065 / CA3) : le système ne peut pas savoir que ses graines sont soldées,
    donc son avancement n'atteint jamais 100 %. Le jardinier est le seul à la
    connaître, et seulement au moment du repiquage — d'où la question immédiate.

    Retourne True si la question a été posée (l'appelant s'arrête là).
    """
    # [CA4] Déjà fourni dans la dictée, déjà demandé, ou rien à rapporter à un lot
    if parsed.get("nb_graines_semees") or parsed.get("_graines_demandees"):
        return False
    if not parsed.get("nb_plants_godets"):
        return False

    lot = _lot_pressenti_pour_godet(parsed)
    # [CA4] Aucun semis rattachable, ou lot déjà entièrement soldé → pas de question
    if not lot or lot.get("graines_en_germination", 0) <= 0:
        return False

    import time as _time_gr
    user_id = update.effective_user.id
    _GODET_GRAINES_PENDING[user_id] = {
        "parsed": parsed, "texte": texte, "ts": _time_gr.time(), "lot": lot,
    }

    # [CA3] Une action explicite pour passer outre — jamais de valeur inventée
    buttons = [[
        InlineKeyboardButton("🤷 Je ne sais pas", callback_data="godetgraines_skip"),
        InlineKeyboardButton("❌ Annuler",        callback_data="godetgraines_cancel"),
    ]]

    # [CA2] Contexte utile : culture, variété et reste réel du lot concerné
    label = f"{lot['culture']} *{lot['variete']}*" if lot.get("variete") else f"*{lot['culture']}*"
    date_lot = _fmt_date_lot(lot.get("date_semis"))
    await update.effective_message.reply_text(
        f"🌾 Sur combien de graines avez-vous repiqué ces "
        f"*{parsed['nb_plants_godets']}* plants de {label} ?\n\n"
        f"_Lot semé le {date_lot} : il reste {lot['graines_en_germination']} "
        f"graine(s) non soldée(s)._",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    log.info(
        "[US-066] Nombre de graines réclamé pour le lot #%s (%d restantes) — user_id=%s",
        lot["semis_id"], lot["graines_en_germination"], user_id,
    )
    return True


async def _godet_graines_reponse(update: Update, texte_reponse: str) -> None:
    """
    [US-066 / CA5] Traite la réponse chiffrée du jardinier. Toute valeur incohérente
    est signalée et redemandée, jamais enregistrée : moins de graines que de plants
    (taux > 100 % impossible), ou plus que le lot n'en a encore.
    """
    import re as _re_gr
    import time as _time_gr

    user_id = update.effective_user.id
    pending = _GODET_GRAINES_PENDING.pop(user_id, None)
    if pending is None:
        return

    if _time_gr.time() - pending["ts"] > _GODET_GRAINES_TIMEOUT:
        await update.effective_message.reply_text(
            "⏱ *Action annulée* (délai dépassé). Veuillez re-saisir votre mise en godet.",
            parse_mode="Markdown",
        )
        return

    parsed = pending["parsed"]
    lot    = pending["lot"]
    nb_plants = int(parsed.get("nb_plants_godets") or 0)

    async def _redemander(message: str) -> None:
        """Remet en attente sans consommer la question — CA5."""
        _GODET_GRAINES_PENDING[user_id] = pending
        await update.effective_message.reply_text(message, parse_mode="Markdown")

    match = _re_gr.search(r"(\d+)", texte_reponse or "")
    if not match:
        await _redemander("❌ Nombre non reconnu. Indiquez un nombre de graines (ex: _10_).")
        return

    nb_graines = int(match.group(1))

    if nb_graines < nb_plants:
        await _redemander(
            f"❌ Impossible : *{nb_plants}* plants ne peuvent pas venir de "
            f"*{nb_graines}* graines. Indiquez au moins {nb_plants}."
        )
        return

    restantes = lot["graines_en_germination"]
    if nb_graines > restantes:
        await _redemander(
            f"❌ Ce lot n'a plus que *{restantes}* graine(s) en germination : "
            f"*{nb_graines}* est impossible. Corrigez la valeur, ou choisissez "
            f"« Je ne sais pas » pour enregistrer sans."
        )
        return

    parsed["nb_graines_semees"] = nb_graines
    parsed["_graines_demandees"] = True
    log.info("[US-066] Nombre de graines saisi : %d — user_id=%s", nb_graines, user_id)
    await _save_godet_item(update, parsed, pending["texte"])


async def _godet_graines_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """[US-066 / CA3] Callback inline — passer outre ou annuler."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    pending = _GODET_GRAINES_PENDING.pop(user_id, None)
    if pending is None:
        await query.edit_message_text("⏱ Action expirée. Veuillez re-saisir votre mise en godet.")
        return

    if query.data == "godetgraines_cancel":
        await query.edit_message_text("❌ Mise en godet annulée.", reply_markup=None)
        return

    # [CA3] Enregistrement sans nombre de graines — le lot restera en germination
    # « indéterminée » (US-065 / CA3), ce que le message annonce sans détour.
    parsed = pending["parsed"]
    parsed["_graines_demandees"] = True
    log.info("[US-066 CA3] Nombre de graines non renseigné (choix explicite) — user_id=%s", user_id)
    await query.edit_message_text(
        "✅ Enregistrement *sans* nombre de graines.\n"
        "_L'avancement de ce lot restera indéterminé._",
        parse_mode="Markdown",
        reply_markup=None,
    )
    await _save_godet_item(update, parsed, pending["texte"])


def _fmt_date_lot(dt) -> str:
    """Libellé court et lisible d'une date de semis pour les boutons de choix de lot."""
    return dt.strftime("%d/%m/%Y") if dt else "date inconnue"


async def _demander_lot_godet_si_ambigu(update: Update, parsed: dict, texte: str) -> bool:
    """
    [fix rattachement lot godet] Demande sur quel lot de semis porte le repiquage
    lorsque plusieurs lots de la culture ont encore des graines en germination.

    Sans ce choix, `creer_evenement_godet` ne pouvait rattacher le godet que s'il
    existait un unique semis pour la culture : deux semis échelonnés laissaient
    `origine_graines_id` à NULL, et aucun des deux lots n'avançait dans la pépinière
    (US-065). Le jardinier est le seul à savoir de quel lot vient le repiquage —
    aucune heuristique ne peut le deviner, d'où la question explicite.

    Retourne True si la question a été posée (l'appelant doit s'arrêter là),
    False s'il peut poursuivre l'enregistrement immédiatement.
    """
    # Choix déjà fait (lot désigné ou refus explicite) → ne jamais redemander
    if parsed.get("_lot_choisi") or parsed.get("origine_graines_id") is not None:
        return False

    # [fix garde-fou graines du lot] Ne proposer que des lots capables d'absorber ce
    # repiquage : un lot trop petit serait refusé à l'écriture, l'afficher au menu
    # ne ferait que promettre un choix impossible.
    graines_requises = int(parsed.get("nb_graines_semees") or parsed.get("nb_plants_godets") or 0)

    db = SessionLocal()
    try:
        candidats = svc_stock.lots_candidats_mise_en_godet(
            db, current_context(), parsed.get("culture") or "", parsed.get("variete"),
            graines_requises=graines_requises,
        )
    finally:
        db.close()

    if len(candidats) < 2:
        # 0 candidat  → le service tranche (rattachement impossible : refus ou
        #               godet sans parent selon qu'il existe des lots ou non) ;
        # 1 candidat  → déduction automatique, aucune question à poser.
        return False

    import time as _time_lot
    user_id = update.effective_user.id
    _GODET_LOT_PENDING[user_id] = {
        "parsed": parsed,
        "texte":  texte,
        "ts":     _time_lot.time(),
        "labels": {lot["semis_id"]: _fmt_date_lot(lot["date_semis"]) for lot in candidats},
    }

    buttons = [
        [InlineKeyboardButton(
            f"{_fmt_date_lot(lot['date_semis'])} — {lot['graines_en_germination']} graines restantes",
            callback_data=f"godetlot:{lot['semis_id']}",
        )]
        for lot in candidats
    ]
    # Pas d'échappatoire « je ne sais pas » : elle produirait un godet sans parent
    # alors que des lots existent et peuvent le porter — exactement le trou que
    # `AucunLotDisponibleError` ferme côté service. Choisir, ou annuler.
    buttons.append([InlineKeyboardButton("❌ Annuler", callback_data="godetlot_cancel")])

    culture = parsed.get("culture") or "cette culture"
    variete = parsed.get("variete")
    label   = f"{culture} *{variete}*" if variete else f"*{culture}* (sans variété)"
    await update.effective_message.reply_text(
        f"🌱 Plusieurs semis de {label} ont encore des graines en germination.\n\n"
        "Sur quel lot ce repiquage a-t-il été fait ?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    log.info(
        "[fix rattachement lot godet] %d lots candidats proposés pour '%s' — user_id=%s",
        len(candidats), parsed.get("culture"), user_id,
    )
    return True


async def _save_godet_item(update: Update, parsed: dict, texte: str) -> None:
    """Sauvegarde un item mise_en_godet et affiche le récapitulatif."""
    # [fix rattachement lot godet] Point de passage obligé des chemins de saisie
    # godet (US-019 et confirmation directe) : le lot parent se choisit ici.
    if await _demander_lot_godet_si_ambigu(update, parsed, texte):
        return

    # [US-066] Puis, le lot étant connu, le nombre de graines qu'il solde. L'ordre
    # compte : CA2 exige d'annoncer le reste du lot concerné, ce qui suppose de
    # savoir de quel lot il s'agit.
    if await _demander_graines_godet_si_manquant(update, parsed, texte):
        return

    db = SessionLocal()
    try:
        event = svc_evenements.creer_evenement_godet(db, current_context(), parsed, texte)
    except svc_evenements.EvenementInvalideError as e:
        db.rollback()
        log.warning(f"❌ MISE EN GODET INVALIDE : {e} | texte={texte!r}")
        await update.effective_message.reply_text(f"❌ {e}")
        return
    except Exception as e:
        db.rollback()
        await update.effective_message.reply_text(f"❌ Erreur base de données : {e}")
        return
    finally:
        db.close()

    recap = _build_recap(parsed, event.id)
    await update.effective_message.reply_text(recap, parse_mode="Markdown", reply_markup=AFTER_RECORD_KEYBOARD)
    await send_voice_reply(update, _build_recap_tts(parsed))


async def _godet_variete_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """[US-019] Callback inline — sélection de variété pour une mise en godet ambiguë."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    pending = _GODET_PENDING.pop(user_id, None)

    if pending is None:
        await query.edit_message_text("⏱ Action expirée. Veuillez re-saisir votre mise en godet.")
        return

    import time
    if time.time() - pending["ts"] > _GODET_TIMEOUT:
        await query.edit_message_text("⏱ *Action annulée* (timeout 60 s). Veuillez re-saisir.", parse_mode="Markdown")
        return

    data = query.data  # godet_var:{variete} | godet_confirm | godet_cancel | godet_force

    if data == "godet_cancel":
        await query.edit_message_text("❌ Mise en godet annulée.", reply_markup=None)
        return

    parsed = pending["parsed"]
    texte  = pending["texte"]

    if data.startswith("godet_var:"):
        variete = data[len("godet_var:"):]
        parsed["variete"] = variete if variete != "__none__" else None
    elif data in ("godet_confirm", "godet_force"):
        pass  # variété déjà dans parsed (CA2) ou aucune (CA3)

    await query.edit_message_text(
        f"✅ Variété confirmée : *{parsed.get('variete') or 'non précisée'}*",
        parse_mode="Markdown",
        reply_markup=None,
    )
    await _save_godet_item(update, parsed, texte)


async def _godet_lot_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """[fix rattachement lot godet] Callback inline — choix du lot de semis parent
    d'une mise en godet, quand plusieurs lots sont encore en germination."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    pending = _GODET_LOT_PENDING.pop(user_id, None)

    if pending is None:
        await query.edit_message_text("⏱ Action expirée. Veuillez re-saisir votre mise en godet.")
        return

    import time
    if time.time() - pending["ts"] > _GODET_LOT_TIMEOUT:
        await query.edit_message_text("⏱ *Action annulée* (timeout 2 min). Veuillez re-saisir.", parse_mode="Markdown")
        return

    data = query.data  # godetlot:{semis_id} | godetlot_cancel

    if data == "godetlot_cancel":
        await query.edit_message_text("❌ Mise en godet annulée.", reply_markup=None)
        return

    parsed = pending["parsed"]
    texte  = pending["texte"]

    semis_id = int(data[len("godetlot:"):])
    parsed["origine_graines_id"] = semis_id
    # Marqueur de décision : empêche _save_godet_item de reposer la question.
    parsed["_lot_choisi"] = True
    log.info("[fix rattachement lot godet] Lot id=%s choisi — user_id=%s", semis_id, user_id)
    await query.edit_message_text(
        f"✅ Lot de semis du *{pending['labels'].get(semis_id, semis_id)}* sélectionné.",
        parse_mode="Markdown",
        reply_markup=None,
    )

    await _save_godet_item(update, parsed, texte)

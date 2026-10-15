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
from app.services import lots_pepiniere as svc_lots  # [US-209]
from .noyau import AFTER_RECORD_KEYBOARD, log
from .etat import (
    _DEPLACEMENT_LOT_PENDING,
    _DEPLACEMENT_LOT_TIMEOUT,
    _GODET_GRAINES_PENDING,
    _QUANTITE_PENDING,
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
        f"_Lot {_etiquette_lot(lot)} : il reste {lot['graines_en_germination']} "
        f"graine(s) non soldée(s)._",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    log.info(
        "[US-066] Nombre de graines réclamé pour le lot #%s (%d restantes) — user_id=%s",
        lot["semis_id"], lot["graines_en_germination"], user_id,
    )
    return True


async def _godet_graines_reponse(update: Update, texte_reponse: str, ctx=None) -> None:
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
    await _save_godet_item(update, parsed, pending["texte"], ctx)


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
    await _save_godet_item(update, parsed, pending["texte"], ctx)


def _fmt_date_lot(dt) -> str:
    """Libellé court et lisible d'une date de semis pour les boutons de choix de lot."""
    return dt.strftime("%d/%m/%Y") if dt else "date inconnue"


def _etiquette_lot(lot: dict) -> str:
    """[US-209] « n° 4 · 21/09/2026 » : le numéro écrit sur l'étiquette, puis la date,
    seule façon de distinguer deux lots de la même variété sur les boutons de choix."""
    date_lot = _fmt_date_lot(lot.get("date_semis"))
    return f"n° {lot['numero_lot']} · {date_lot}" if lot.get("numero_lot") is not None else date_lot


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
        "labels": {lot["semis_id"]: _etiquette_lot(lot) for lot in candidats},
    }

    buttons = [
        [InlineKeyboardButton(
            f"{_etiquette_lot(lot)} — {lot['graines_en_germination']} graines restantes",
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


async def _save_godet_item(update: Update, parsed: dict, texte: str, ctx=None) -> None:
    """Sauvegarde un item mise_en_godet et affiche le récapitulatif.

    [US-224] Un geste venu de la file porte `_geste_file` : il quitte la file
    APRÈS l'écriture réussie, comme au récapitulatif d'US-021, jamais avant.
    """
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

    geste_file = parsed.get("_geste_file")
    if geste_file:
        from app.services import file_gestes as svc_file
        from .enregistrement import _GesteDeLaFile
        from .file_gestes import proposer_suivant
        svc_file.confirmer(_GesteDeLaFile(geste_file))
        if ctx is not None:
            await proposer_suivant(update, ctx, geste_file["user_id"])


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
    await _save_godet_item(update, parsed, texte, ctx)


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
        f"✅ Lot de semis *{pending['labels'].get(semis_id, semis_id)}* sélectionné.",
        parse_mode="Markdown",
        reply_markup=None,
    )

    await _save_godet_item(update, parsed, texte, ctx)


# ──────────────────────────────────────────────────────────────────────────────
# [US-224] La porte unique de la quantité de pépinière
# ──────────────────────────────────────────────────────────────────────────────
# Mise en godet, perte de godet, vente, mise en terre d'un lot : le NOMBRE de plants
# est ce qui fait bouger le stock (`int(qte or 0)` dans `calcul_lots_pepiniere`). Un
# événement écrit sans lui ne décrémente rien et laisse son lot « indéterminé » —
# constaté le 14/10/2026 (mise en godet #593, perte de godet #596). Chaque chemin
# qui y mène — dictée, voix, geste de la file — passe donc ICI avant le
# récapitulatif, et la question propose ce que la base sait déjà du lot.
_VERBE_QUANTITE = {
    "mise_en_godet": "repiqués en godet",
    "perte_godet": "perdus",
    "perte": "perdus",
    "vendu": "vendus",
    "plantation": "mis en terre",
}
_MOTS_PEPINIERE_PERTE = ("pepiniere", "pépinière", "godet", "semis")


def _quantite_pepiniere_manquante(item: dict, texte: str = "") -> bool:
    """[US-224] L'item est-il un geste de pépinière dont le nombre de plants manque ?

    `perte` (sans « godet ») n'est concernée que si la phrase dit la pépinière ou cite
    un lot — au potager, la question existante (US-021 / CA9) fait déjà foi. Une
    plantation n'est interrogée ici que quand elle cite son lot : sans lot, le
    CA9 générique la demande, sans proposition de stock à faire.
    """
    from utils.actions import normalize_action
    action = normalize_action(item.get("action"))
    if action == "mise_en_godet":
        return not item.get("nb_plants_godets") and not item.get("_plants_demandes")
    if action not in ("perte_godet", "perte", "vendu", "plantation") or item.get("quantite"):
        return False
    lot_cite = bool(item.get("numero_lot_cite")) or item.get("origine_graines_id") is not None
    if not (item.get("culture") or lot_cite):
        return False                       # la culture est demandée avant, plus loin
    if action in ("perte_godet", "vendu"):
        return True
    if action == "plantation":
        return lot_cite
    from unidecode import unidecode
    texte_n = unidecode((texte or "").lower())
    return lot_cite or any(m in texte_n for m in _MOTS_PEPINIERE_PERTE)


def _lot_pressenti_pour_sortie(parsed: dict) -> "dict | None":
    """[US-224] Le lot d'où des godets vont sortir (perte, vente, mise en terre) : le lot
    cité, sinon l'unique lot de la culture (et variété dite) qui a encore des godets.
    None dès que c'est incertain — aucun stock précis à annoncer, donc aucune
    proposition à faire.
    """
    db = SessionLocal()
    try:
        semis_id = parsed.get("origine_graines_id")
        if semis_id is not None:
            return svc_stock.lot_pepiniere_par_semis(db, current_context(), int(semis_id))
        culture = (parsed.get("culture") or "").lower()
        if not culture:
            return None
        variete = (parsed.get("variete") or "").lower() or None
        candidats = [
            lot for lot in svc_stock.calcul_lots_pepiniere(db, current_context())
            if not lot.get("sans_semis_rattache")
            and (lot.get("culture") or "").lower() == culture
            and (variete is None or (lot.get("variete") or "").lower() == variete)
            and (lot.get("stock_residuel_godet") or 0) > 0
        ]
        return candidats[0] if len(candidats) == 1 else None
    finally:
        db.close()


async def _poser_question_quantite_pepiniere(
    update: Update, items: list, texte: str, geste_file, message,
) -> None:
    """[US-224] Pose « combien de plants ? » avec, quand le lot est connu, ce qui reste
    en base — « Tout le lot : N » —, plutôt que de le révéler après la réponse.

    « Je ne sais pas » n'est offert qu'à la mise en godet (enregistrement sans nombre,
    explicite et signalé). Une perte ou une vente sans nombre ne ferait bouger aucun
    stock : le nombre y est obligatoire, « Annuler » seul permet d'en sortir.

    La réponse arrive par `_godet_plants_cb` (bouton) ou par le texte
    (`messages._repondre_quantite_en_attente`) ; dans les deux cas le geste reprend
    `_parse_and_save` avec son `geste_file`.
    """
    from utils.actions import normalize_action
    import time as _time_q

    item = items[0]
    action = normalize_action(item.get("action"))
    est_godet = action == "mise_en_godet"
    user_id = update.effective_user.id
    de_la_file = geste_file is not None

    lot = _lot_pressenti_pour_godet(item) if est_godet else _lot_pressenti_pour_sortie(item)
    cle = "graines_en_germination" if est_godet else "stock_residuel_godet"
    reste = int(lot.get(cle) or 0) if lot else 0

    attente = {
        "items": items, "texte": texte, "ts": _time_q.time(), "geste_file": geste_file,
        # Marqueur : seul un clavier de CETTE question peut y répondre
        # (`_godet_plants_cb`), jamais celui d'une autre quantité.
        "godet_plants": True,
    }
    boutons = []
    if lot and reste > 0:
        attente["lot_propose"] = {"semis_id": lot["semis_id"], "reste": reste}
        boutons.append([InlineKeyboardButton(f"✅ Tout le lot : {reste}", callback_data="godetplants_all")])
    if est_godet:
        boutons.append([InlineKeyboardButton("🤷 Je ne sais pas", callback_data="godetplants_skip")])
    boutons.append([InlineKeyboardButton(
        "❌ Laisser dans ma file" if de_la_file else "❌ Annuler", callback_data="godetplants_cancel",
    )])

    verbe = _VERBE_QUANTITE.get(action, "concernés")
    lot_cite = item.get("numero_lot_cite")
    de_lot = f" du lot n° {lot_cite}" if lot_cite else ""
    if lot and reste > 0:
        nature = "graine(s) non soldée(s)" if est_godet else "plant(s) en godet"
        question = (
            f"🪴 Combien de plants avez-vous {verbe} ?\n\n"
            f"_Lot {_etiquette_lot(lot)} : il reste {reste} {nature}._\n"
            "Appuyez sur « Tout le lot », ou tapez un autre nombre."
        )
    else:
        question = f"🪴 Combien de plants{de_lot} avez-vous {verbe} ? (ex: 3)\n"
        if not est_godet:
            question += "_Le nombre est nécessaire pour mettre le stock à jour._"

    _QUANTITE_PENDING[user_id] = attente
    log.info("[US-224] Nombre de plants manquant pour '%s' — user_id=%s", action, user_id)
    await message.reply_text(
        question, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(boutons),
    )


async def _godet_plants_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """[US-224] « Tout le lot » : le nombre de plants d'une mise en godet de la file,
    lu en base (les graines non soldées du lot) plutôt que redicté.

    Le lot est alors entièrement soldé : plants et graines valent le reste du lot,
    ce qui rend inutile la question « sur combien de graines ? ». Taper un autre
    nombre garde le parcours habituel (réponse texte, puis question des graines).
    """
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    pending = _QUANTITE_PENDING.get(user_id)
    items = (pending or {}).get("items") or [{}]
    # Un clavier périmé ne doit jamais répondre à une AUTRE question de quantité.
    est_la_question = bool(pending) and bool(
        pending.get("godet_plants") or pending.get("lot_propose")
    )
    if not est_la_question:
        await query.edit_message_text(
            "⏱ Ce choix n'est plus actif. Redonnez votre mise en godet, ou /gestes "
            "pour rouvrir vos gestes en attente."
        )
        return
    _QUANTITE_PENDING.pop(user_id, None)
    de_la_file = pending.get("geste_file") is not None

    if query.data == "godetplants_cancel":
        await query.edit_message_text(
            "👌 Le geste reste dans votre file — reprenez-le avec /gestes."
            if de_la_file else "❌ Mise en godet annulée.",
            reply_markup=None,
        )
        return

    if query.data == "godetplants_skip" and items[0].get("action") != "mise_en_godet":
        # Jamais offert pour une perte ou une vente : le nombre y est obligatoire.
        _QUANTITE_PENDING[user_id] = pending
        await query.answer("Le nombre de plants est nécessaire.", show_alert=False)
        return

    if query.data == "godetplants_skip":
        # Choix explicite, comme « Je ne sais pas » d'US-066 : le godet est écrit sans
        # nombre, et on dit ce que ça coûte au lieu de le laisser se produire en silence.
        items[0]["_plants_demandes"] = True
        log.info("[US-224] Nombre de plants non renseigné (choix explicite) — user_id=%s", user_id)
        await query.edit_message_text(
            "✅ Enregistrement *sans* nombre de plants.\n"
            "_Aucun plant n'entrera en stock et l'avancement du lot restera indéterminé._",
            parse_mode="Markdown", reply_markup=None,
        )
        from .saisie import _parse_and_save   # import tardif : saisie importe ce module
        await _parse_and_save(
            update, pending["texte"], pre_parsed_items=items, geste_file=pending.get("geste_file"),
        )
        return

    lot = pending.get("lot_propose")
    if not lot:
        await query.edit_message_text("⏱ Ce choix n'est plus actif. Redonnez votre mise en godet.")
        return
    item = items[0]
    if item.get("action") == "mise_en_godet":
        item["nb_plants_godets"] = lot["reste"]
        item["nb_graines_semees"] = lot["reste"]   # lot soldé : rien à redemander (US-066)
    else:
        # Perte, vente, mise en terre : le nombre de plants est la quantité de l'acte.
        item["quantite"] = lot["reste"]
        item["unite"] = "plants"
    item["origine_graines_id"] = lot["semis_id"]
    log.info(
        "[US-224] Tout le lot proposé : %d plants, lot id=%s — user_id=%s",
        lot["reste"], lot["semis_id"], user_id,
    )
    await query.edit_message_text(
        f"✅ *{lot['reste']}* plants — tout le lot.", parse_mode="Markdown",
        reply_markup=None,
    )

    from .saisie import _parse_and_save   # import tardif : saisie importe ce module
    await _parse_and_save(
        update, pending["texte"], pre_parsed_items=items, geste_file=pending.get("geste_file"),
    )


# ──────────────────────────────────────────────────────────────────────────────
# [US-211] Déplacer un lot d'une pépinière à l'autre
# ──────────────────────────────────────────────────────────────────────────────
async def _preparer_deplacement(update: Update, parsed: dict, texte: str, geste_file=None) -> bool:
    """[US-211 / CA3, CA4] Désigne le lot d'un déplacement et contrôle sa destination
    AVANT le récapitulatif : rien n'est confirmé qui serait refusé à l'écriture.

    Retourne True si le flux s'arrête ici (refus dit au jardinier, ou question posée
    sur le lot — l'appelant ne doit plus rien faire), False si le geste est prêt :
    `parsed` porte alors le lot (`origine_graines_id`, `_lot_numero`) et la destination
    canonique, et le récapitulatif peut suivre.
    """
    message = update.effective_message
    db = SessionLocal()
    candidats: list[dict] = []
    try:
        try:
            svc_evenements.resoudre_lot_deplacement(db, current_context(), parsed)
            return False
        except svc_evenements.LotIndetermineError:
            # Plusieurs lots en cours pour cette culture : le jardinier est le seul à
            # savoir lequel il déplace (modèle d'US-019). Seuls les lots issus d'un
            # semis sont proposés : ce sont les seuls que le bouton peut désigner.
            candidats = [
                lot for lot in svc_evenements.lots_deplacables(
                    db, current_context(), parsed.get("culture") or "", parsed.get("variete"),
                )
                if lot.get("semis_id") is not None
            ]
        except svc_evenements.EvenementInvalideError as e:
            log.info("[US-211] Déplacement refusé : %s | texte=%r", e, texte)
            await message.reply_text(f"❌ {e}")
            return True
    finally:
        db.close()

    if len(candidats) < 2:
        await message.reply_text(
            "❌ Plusieurs lots correspondent : citez le numéro du lot à déplacer (« le lot 119 »)."
        )
        return True

    import time as _time_dep
    user_id = update.effective_user.id
    _DEPLACEMENT_LOT_PENDING[user_id] = {
        "parsed": parsed,
        "texte": texte,
        "ts": _time_dep.time(),
        "geste_file": geste_file,
        "labels": {lot["semis_id"]: _etiquette_lot(lot) for lot in candidats},
    }
    buttons = [
        [InlineKeyboardButton(
            f"{_etiquette_lot(lot)} — {lot.get('stock_residuel_godet', 0)} godets",
            callback_data=f"deplot:{lot['semis_id']}",
        )]
        for lot in candidats
    ]
    buttons.append([InlineKeyboardButton("❌ Annuler", callback_data="deplot_cancel")])
    culture = parsed.get("culture") or "cette culture"
    variete = parsed.get("variete")
    label = f"{culture} *{variete}*" if variete else f"*{culture}*"
    await message.reply_text(
        f"🚚 Plusieurs lots de {label} sont en pépinière.\n\nQuel lot déplacez-vous ?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    log.info("[US-211] %d lots candidats proposés pour '%s' — user_id=%s", len(candidats), culture, user_id)
    return True


async def _deplacement_lot_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """[US-211 / CA3] Callback inline — choix du lot à déplacer quand plusieurs lots de
    la culture sont en pépinière. Le geste reprend ensuite son parcours normal :
    récapitulatif, confirmation, écriture."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    pending = _DEPLACEMENT_LOT_PENDING.pop(user_id, None)
    if pending is None:
        await query.edit_message_text("⏱ Action expirée. Veuillez redire votre déplacement.")
        return

    import time
    if time.time() - pending["ts"] > _DEPLACEMENT_LOT_TIMEOUT:
        await query.edit_message_text("⏱ *Action annulée* (timeout 2 min). Veuillez redire.", parse_mode="Markdown")
        return

    data = query.data  # deplot:{semis_id} | deplot_cancel
    if data == "deplot_cancel":
        await query.edit_message_text("❌ Déplacement annulé.", reply_markup=None)
        return

    parsed = pending["parsed"]
    semis_id = int(data[len("deplot:"):])
    parsed["origine_graines_id"] = semis_id
    log.info("[US-211] Lot de semis id=%s choisi pour le déplacement — user_id=%s", semis_id, user_id)
    await query.edit_message_text(
        f"✅ Lot *{pending['labels'].get(semis_id, semis_id)}* sélectionné.",
        parse_mode="Markdown",
        reply_markup=None,
    )

    from .saisie import _parse_and_save   # import tardif : saisie importe ce module
    await _parse_and_save(
        update, pending["texte"], pre_parsed_items=[parsed], geste_file=pending.get("geste_file"),
    )


# ──────────────────────────────────────────────────────────────────────────────
# [US-209 / CA7] Commande /lot <numéro> — un lot de pépinière, zéro jeton
# ──────────────────────────────────────────────────────────────────────────────
async def cmd_lot(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /lot — la liste des lots (les 15 plus récents), /lot tomate pour filtrer.
    /lot 128 — culture, variété, date de semis, emplacement, graines semées, plants
    obtenus et restants. Aucun appel au modèle, aucun effet de bord ; le numéro est
    cherché dans le potager courant seulement (un lot d'un autre potager n'existe pas).
    """
    brut = " ".join(ctx.args or []).strip().lstrip("#")
    if not brut.isdigit():
        # [US-209] Sans numéro : la liste des lots, filtrée par culture si on en cite une.
        db = SessionLocal()
        try:
            lots = svc_stock.calcul_lots_pepiniere(db, current_context())
        finally:
            db.close()
        log.info("[US-209] /lot — liste (%s)", brut or "toutes cultures")
        await update.message.reply_text(
            svc_lots.formater_liste_lots_telegram(lots, brut or None), parse_mode="Markdown",
        )
        return
    numero = int(brut)
    db = SessionLocal()
    try:
        lot = svc_stock.lot_pepiniere_par_numero(db, current_context(), numero)
    finally:
        db.close()
    if lot is None:
        await update.message.reply_text(f"Aucun lot n° {numero} dans ce potager.")
        return
    log.info("[US-209 / CA7] /lot %s consulté", numero)
    await update.message.reply_text(svc_lots.formater_lot_telegram(lot), parse_mode="Markdown")

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
from utils.stock import graines_restantes   # [US-212]
from app.services import lots_pepiniere as svc_lots  # [US-209]
from .noyau import AFTER_RECORD_KEYBOARD, _md, log
from .etat import (
    _DEPLACEMENT_LOT_PENDING,
    _DEPLACEMENT_LOT_TIMEOUT,
    _LEVEE_LOT_PENDING,
    _LEVEE_LOT_TIMEOUT,
    _LEVEE_TERMINEE_PENDING,
    _LEVEE_TERMINEE_TIMEOUT,
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
    if not lot or graines_restantes(lot) <= 0:   # [US-212] capacité de repiquage
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
        f"_Lot {_etiquette_lot(lot)} : il reste {graines_restantes(lot)} "
        f"graine(s) non soldée(s)._",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    log.info(
        "[US-066] Nombre de graines réclamé pour le lot #%s (%d restantes) — user_id=%s",
        lot["semis_id"], graines_restantes(lot), user_id,
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

    restantes = graines_restantes(lot)
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
            f"{_etiquette_lot(lot)} — {graines_restantes(lot)} graines restantes",
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
    reste = (graines_restantes(lot) if est_godet else int(lot.get("stock_residuel_godet") or 0)) if lot else 0

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
        except svc_evenements.OrigineAmbigueError as e:
            # [US-241 / CA3] Lot réparti, origine non dite : le jardinier choisit.
            return await _demander_origine_godets(update, parsed, texte, geste_file, e)
        except svc_evenements.DestinationManquanteError as e:
            # [US-241 / CA12] « Ranger dans… » : déposé sans destination, on la demande.
            return await _demander_destination(update, parsed, texte, geste_file, e)
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
        "question": "lot",
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


#: [US-241] Valeur de bouton pour l'origine « emplacement non renseigné » (US-210 / CA5).
_SANS_EMPLACEMENT = "x"


def _nom_origine(entree: dict) -> str:
    return entree.get("nom") or "Emplacement non renseigné"


def _valeur_origine(entree: dict) -> str:
    pid = entree.get("parcelle_id")
    return str(pid) if pid is not None else _SANS_EMPLACEMENT


async def _demander_origine_godets(
    update: Update, parsed: dict, texte: str, geste_file, erreur: "svc_evenements.OrigineAmbigueError",
) -> bool:
    """[US-241 / CA3, CA9] Un lot réparti entre plusieurs pépinières, et un geste qui ne dit
    pas d'où viennent les godets : une question, un bouton par pépinière avec son nombre de
    godets (« Serre (10) »). Aucune origine n'est choisie à la place du jardinier (A41).
    Sert au déplacement chiffré comme à la plantation, la perte et la vente."""
    import time as _time_orig
    user_id = update.effective_user.id
    origines = list(erreur.origines)
    _DEPLACEMENT_LOT_PENDING[user_id] = {
        "question": "origine",
        "parsed": parsed,
        "texte": texte,
        "ts": _time_orig.time(),
        "geste_file": geste_file,
        "labels": {_valeur_origine(o): _nom_origine(o) for o in origines},
    }
    buttons = [
        [InlineKeyboardButton(f"{_nom_origine(o)} ({o['godets']})", callback_data=f"deplorig:{_valeur_origine(o)}")]
        for o in origines
    ]
    buttons.append([InlineKeyboardButton("❌ Annuler", callback_data="deplot_cancel")])
    await update.effective_message.reply_text(
        f"📍 {erreur}",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    log.info(
        "[US-241 / CA3] Origine demandée (%s, %d pépinières) — user_id=%s",
        parsed.get("action"), len(origines), user_id,
    )
    return True


async def _demander_destination(
    update: Update, parsed: dict, texte: str, geste_file, erreur: "svc_evenements.DestinationManquanteError",
) -> bool:
    """[US-241 / CA12] Déplacement déposé sans destination (« Ranger dans… », « Déplacer »
    de la fiche du lot) : les pépinières du potager par boutons, hors l'origine."""
    message = update.effective_message
    if not erreur.pepinieres:
        await message.reply_text(
            "❌ Aucune autre pépinière dans ce potager : déclarez-en une (« le châssis est une "
            "pépinière froide ») pour y ranger ce lot."
        )
        return True
    import time as _time_dest
    user_id = update.effective_user.id
    _DEPLACEMENT_LOT_PENDING[user_id] = {
        "question": "destination",
        "parsed": parsed,
        "texte": texte,
        "ts": _time_dest.time(),
        "geste_file": geste_file,
        "labels": {str(p["id"]): p["nom"] for p in erreur.pepinieres},
    }
    buttons = [
        [InlineKeyboardButton(p["nom"], callback_data=f"depldest:{p['id']}")]
        for p in erreur.pepinieres
    ]
    buttons.append([InlineKeyboardButton("❌ Annuler", callback_data="deplot_cancel")])
    quoi = f"{int(parsed['quantite'])} godets du lot" if parsed.get("quantite") else "le lot"
    numero = parsed.get("_lot_numero")
    suffixe = f" {numero}" if numero is not None else ""
    await message.reply_text(
        f"🚚 Où rangez-vous {quoi}{suffixe} ?",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    log.info("[US-241 / CA12] Destination demandée (%d pépinières) — user_id=%s", len(erreur.pepinieres), user_id)
    return True


async def _preparer_origine_sortie(update: Update, parsed: dict, texte: str, geste_file=None) -> bool:
    """[US-241 / CA9] Plantation, perte ou vente qui puise dans un lot réparti sans dire
    d'où : l'origine est demandée par boutons AVANT le récapitulatif. Retourne True si une
    question est posée (l'appelant s'arrête), False sinon."""
    db = SessionLocal()
    erreur = None
    try:
        svc_evenements.controler_origine_sortie(db, current_context(), parsed)
    except svc_evenements.OrigineAmbigueError as e:
        erreur = e
    finally:
        db.close()
    if erreur is None:
        return False
    return await _demander_origine_godets(update, parsed, texte, geste_file, erreur)


async def _deplacement_lot_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """[US-211 / CA3] Callback inline — choix du lot à déplacer quand plusieurs lots de
    la culture sont en pépinière. [US-241] Aussi : choix de l'origine des godets d'un lot
    réparti (`deplorig:`), et de la destination d'un déplacement déposé sans elle
    (`depldest:`). Le geste reprend ensuite son parcours normal : récapitulatif,
    confirmation, écriture."""
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

    data = query.data  # deplot:{semis_id} | deplorig:{parcelle|x} | depldest:{parcelle} | deplot_cancel
    if data == "deplot_cancel":
        await query.edit_message_text(
            "👌 Le geste reste dans votre file — reprenez-le avec /gestes."
            if pending.get("geste_file") is not None else "❌ Geste annulé.",
            reply_markup=None,
        )
        return

    parsed = pending["parsed"]
    question = pending.get("question", "lot")
    prefixe = {"lot": "deplot:", "origine": "deplorig:", "destination": "depldest:"}[question]
    if not data.startswith(prefixe):
        # Un clavier périmé ne répond jamais à une AUTRE question.
        await query.edit_message_text("⏱ Ce choix n'est plus actif. Veuillez redire votre geste.")
        return
    valeur = data[len(prefixe):]
    if question == "origine":
        parsed["parcelle_origine_id"] = None if valeur == _SANS_EMPLACEMENT else int(valeur)
        log.info("[US-241 / CA3] Origine %s choisie — user_id=%s", valeur, user_id)
        await query.edit_message_text(
            f"✅ Depuis *{pending['labels'].get(valeur, valeur)}*.", parse_mode="Markdown", reply_markup=None,
        )
    elif question == "destination":
        parsed["parcelle"] = pending["labels"].get(valeur)
        log.info("[US-241 / CA12] Destination %s choisie — user_id=%s", valeur, user_id)
        await query.edit_message_text(
            f"✅ Vers *{pending['labels'].get(valeur, valeur)}*.", parse_mode="Markdown", reply_markup=None,
        )
    else:
        semis_id = int(valeur)
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
# [US-212] Noter la levée d'un lot de semis
# ──────────────────────────────────────────────────────────────────────────────
async def _preparer_levee(update: Update, parsed: dict, texte: str, geste_file=None) -> bool:
    """[US-212 / CA2, CA3, CA4] Désigne le lot d'une levée AVANT le récapitulatif.

    Même parcours que le déplacement (`_preparer_deplacement`) et même règle de
    désignation (`svc_evenements.designer_lot`) : le numéro cité, sinon la culture quand
    un seul lot en cours correspond, sinon un choix par boutons (numéro et date de semis).

    Retourne True si le flux s'arrête ici (refus dit, question posée, choix demandé),
    False si le geste est prêt : `parsed` porte alors le lot et ses alertes
    (`_alertes_levee`, jamais corrigées en silence) et le récapitulatif peut suivre.

    [CA11] La PWA ne dépose que le GESTE (le lot) : le nombre de levés, puis « la levée
    est-elle terminée ? », sont demandés ICI, précisément, avec ce que la base sait du lot.
    Une phrase dictée avec son nombre (« levée du lot 128 : 40 ») ne pose aucune des deux :
    sans « terminée », la levée est en cours.
    """
    message = update.effective_message
    db = SessionLocal()
    candidats: list[dict] = []
    hors_pepiniere = False
    try:
        try:
            lot = svc_evenements.resoudre_lot_levee(db, current_context(), parsed)
            if parsed.get("quantite") is None:
                await _poser_question_levee(update, parsed, texte, geste_file, lot)
                return True
            if parsed.get("_levee_a_preciser") and not parsed.get("_levee_terminee_repondue"):
                await _poser_question_levee_terminee(update, parsed, texte, geste_file, lot)
                return True
            return False
        except svc_evenements.LotIndetermineError:
            candidats = [
                lot for lot in svc_evenements.lots_deplacables(
                    db, current_context(), parsed.get("culture") or "", parsed.get("variete"),
                )
                if lot.get("semis_id") is not None
            ]
        except svc_evenements.LeveeHorsPepiniereError as e:
            log.info("[US-212 / CA4] Levée hors pépinière : %s | texte=%r", e, texte)
            hors_pepiniere = True
        except svc_evenements.EvenementInvalideError as e:
            log.info("[US-212] Levée refusée : %s | texte=%r", e, texte)
            await message.reply_text(f"❌ {e}")
            return True
    finally:
        db.close()

    user_id = update.effective_user.id
    if hors_pepiniere:
        # « les carottes ont levé » : un semis en pleine terre n'a pas de lot. Ce n'est pas
        # une levée de lot — on le dit, et on propose de la noter en observation.
        culture = parsed.get("culture") or "cette culture"
        _LEVEE_LOT_PENDING[user_id] = {
            "parsed": parsed, "texte": texte, "ts": time.time(), "geste_file": geste_file,
        }
        await message.reply_text(
            f"🌱 La levée se note sur un *lot de pépinière* — je n'en trouve aucun pour *{culture}*. "
            "S'il s'agit d'un semis en pleine terre, je peux le noter en observation.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📝 Noter en observation", callback_data="levlot_obs"),
                InlineKeyboardButton("❌ Non merci", callback_data="levlot_cancel"),
            ]]),
        )
        return True

    if len(candidats) < 2:
        await message.reply_text(
            "❌ Plusieurs lots correspondent : citez le numéro du lot (« levée du lot 128 : 40 »)."
        )
        return True

    _LEVEE_LOT_PENDING[user_id] = {
        "parsed": parsed, "texte": texte, "ts": time.time(), "geste_file": geste_file,
        "labels": {lot["semis_id"]: _etiquette_lot(lot) for lot in candidats},
    }
    buttons = [
        [InlineKeyboardButton(
            f"{_etiquette_lot(lot)} — {lot.get('graines_semees', 0)} graines semées",
            callback_data=f"levlot:{lot['semis_id']}",
        )]
        for lot in candidats
    ]
    buttons.append([InlineKeyboardButton("❌ Annuler", callback_data="levlot_cancel")])
    culture = parsed.get("culture") or "cette culture"
    variete = parsed.get("variete")
    label = f"{culture} *{variete}*" if variete else f"*{culture}*"
    await message.reply_text(
        f"🌱 Plusieurs lots de {label} sont en pépinière.\n\nSur quel lot comptez-vous la levée ?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    log.info("[US-212] %d lots candidats proposés pour '%s' — user_id=%s", len(candidats), culture, user_id)
    return True


def _nom_du_lot_levee(lot: dict) -> str:
    """« Chou frisé » : la culture et la variété du lot, pour les questions du bot."""
    nom = (lot.get("culture") or "").capitalize()
    if lot.get("variete"):
        nom += f" {lot['variete']}"
    return _md(nom)


async def _poser_question_levee(update: Update, parsed: dict, texte: str, geste_file, lot: dict) -> None:
    """[US-212 / CA11] « Combien de plants ont levé ? » — avec le lot, ses graines semées et
    son dernier comptage, plutôt que de les révéler après la réponse.

    La réponse arrive par le texte (`messages._repondre_quantite_en_attente`) : un nombre,
    zéro compris (« rien n'a encore levé »). Le geste reprend ensuite `_parse_and_save`
    avec son `geste_file`, et `_preparer_levee` pose la question suivante.
    """
    user_id = update.effective_user.id
    parsed["_levee_a_preciser"] = True
    _QUANTITE_PENDING[user_id] = {
        "items": [parsed], "texte": texte, "ts": time.time(), "geste_file": geste_file, "levee": True,
    }
    numero = lot.get("numero_lot")
    cible = f"le lot n° {numero}" if numero is not None else "ce lot"
    # [US-212 / CA11] Un lot déjà en partie repiqué : ses plants repiqués ont forcément levé.
    # On ne demande que ce qui a levé parmi les graines RESTANTES, et le total (repiqués +
    # réponse) est déduit à la réponse — le comptage reste un total du lot.
    repiques = int(lot.get("plants_obtenus") or 0)
    restantes = graines_restantes(lot)
    if repiques > 0 and restantes > 0:
        parsed["_leves_deja_repiques"] = repiques
        lignes = [f"🌱 Combien de plants ont levé parmi les {restantes} graines restantes du {cible[3:]} ?\n"]
    else:
        lignes = [f"🌱 Combien de plants ont levé dans {cible} ?\n"]
    detail = f"_{_nom_du_lot_levee(lot)} · semé le {_fmt_date_lot(lot.get('date_semis'))}"
    if lot.get("graines_semees"):
        detail += f" · {lot['graines_semees']} graines semées"
    if "_leves_deja_repiques" in parsed:
        detail += f", dont {repiques} déjà repiqué{'s' if repiques > 1 else ''} en godet"
    lignes.append(detail + "._")
    if lot.get("nb_leves") is not None:
        jour = str(lot["date_derniere_levee"])[:10] if lot.get("date_derniere_levee") else None
        quand = f" le {jour[8:10]}/{jour[5:7]}" if jour else ""
        lignes.append(f"_Dernier comptage : {lot['nb_leves']} levés{quand} — le nouveau le remplace._")
    lignes.append("\nTapez le nombre de plants levés (0 si rien n'a encore levé).")
    await update.effective_message.reply_text(
        "\n".join(lignes), parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(
            "❌ Laisser dans ma file" if geste_file is not None else "❌ Annuler", callback_data="levdet_cancel",
        )]]),
    )
    log.info("[US-212 / CA11] Nombre de levés demandé pour le lot %s — user_id=%s", numero, user_id)


async def _poser_question_levee_terminee(update: Update, parsed: dict, texte: str, geste_file, lot: dict) -> None:
    """[US-212 / CA7, CA11] « La levée est-elle terminée ? » — dit ce que « oui » solde AVANT
    de demander : les graines non levées, et la germination du lot qui se clôt."""
    user_id = update.effective_user.id
    _LEVEE_TERMINEE_PENDING[user_id] = {
        "items": [parsed], "texte": texte, "ts": time.time(), "geste_file": geste_file,
    }
    numero = lot.get("numero_lot")
    cible = f"du lot n° {numero}" if numero is not None else "du lot"
    leves = int(float(parsed.get("quantite") or 0))
    graines = int(lot.get("graines_semees") or 0)
    lignes = [f"✅ La levée {cible} est-elle terminée ?\n"]
    if graines > 0:
        lignes.append(f"_{leves} levés sur {graines} graines semées ({round(leves / graines * 100)} %)._")
    soldees = max(0, graines - leves)
    oui = "la germination du lot est close"
    if soldees == 1:
        oui += " et la graine non levée est soldée"
    elif soldees > 1:
        oui += f" et les {soldees} graines non levées sont soldées"
    lignes.append(f"• *Terminée* : {oui}.")
    lignes.append("• *Pas encore* : le lot reste « en cours », vous pourrez recompter.")
    await update.effective_message.reply_text(
        "\n".join(lignes), parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Oui, terminée", callback_data="levdet_oui"),
             InlineKeyboardButton("⏳ Pas encore", callback_data="levdet_non")],
            [InlineKeyboardButton(
                "❌ Laisser dans ma file" if geste_file is not None else "❌ Annuler", callback_data="levdet_cancel",
            )],
        ]),
    )
    log.info("[US-212 / CA7] « Levée terminée ? » demandé pour le lot %s — user_id=%s", numero, user_id)


async def _levee_detail_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """[US-212 / CA11] Boutons des questions de la levée : « Oui, terminée » / « Pas encore » /
    annuler. Le geste reprend ensuite son parcours normal : récapitulatif, confirmation,
    écriture."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    data = query.data  # levdet_oui | levdet_non | levdet_cancel

    if data == "levdet_cancel":
        question = _QUANTITE_PENDING.get(user_id)
        nombre = question if question and question.get("levee") else None
        if nombre is not None:
            _QUANTITE_PENDING.pop(user_id, None)
        terminee = _LEVEE_TERMINEE_PENDING.pop(user_id, None)
        geste_file = (terminee or nombre or {}).get("geste_file")
        await query.edit_message_text(
            "👌 Le geste reste dans votre file — /gestes le rouvre." if geste_file is not None else "❌ Levée annulée.",
            reply_markup=None,
        )
        return

    pending = _LEVEE_TERMINEE_PENDING.pop(user_id, None)
    if pending is None:
        await query.edit_message_text("⏱ Action expirée. Veuillez redire la levée.")
        return
    if time.time() - pending["ts"] > _LEVEE_TERMINEE_TIMEOUT:
        await query.edit_message_text("⏱ *Action annulée* (timeout 3 min). Veuillez redire.", parse_mode="Markdown")
        return

    parsed = pending["items"][0]
    terminee = data == "levdet_oui"
    if terminee:
        parsed["levee_terminee"] = True
    parsed["_levee_terminee_repondue"] = True
    log.info("[US-212 / CA7] Levée terminée=%s — user_id=%s", terminee, user_id)
    await query.edit_message_text(
        "✅ Levée *terminée*." if terminee else "⏳ Levée *pas encore terminée*.",
        parse_mode="Markdown", reply_markup=None,
    )

    from .saisie import _parse_and_save   # import tardif : saisie importe ce module
    await _parse_and_save(
        update, pending["texte"], pre_parsed_items=pending["items"], geste_file=pending.get("geste_file"),
    )


async def _levee_lot_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """[US-212 / CA2, CA4] Callback inline — choix du lot d'une levée, ou observation d'un
    semis en pleine terre. Le geste reprend ensuite son parcours normal : récapitulatif,
    confirmation, écriture."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    pending = _LEVEE_LOT_PENDING.pop(user_id, None)
    if pending is None:
        await query.edit_message_text("⏱ Action expirée. Veuillez redire la levée.")
        return
    if time.time() - pending["ts"] > _LEVEE_LOT_TIMEOUT:
        await query.edit_message_text("⏱ *Action annulée* (timeout 2 min). Veuillez redire.", parse_mode="Markdown")
        return

    data = query.data  # levlot:{semis_id} | levlot_obs | levlot_cancel
    if data == "levlot_cancel":
        await query.edit_message_text("❌ Levée annulée.", reply_markup=None)
        return

    parsed = pending["parsed"]
    if data == "levlot_obs":
        await _noter_levee_en_observation(query, parsed, pending["texte"])
        return

    semis_id = int(data[len("levlot:"):])
    parsed["origine_graines_id"] = semis_id
    log.info("[US-212] Lot de semis id=%s choisi pour la levée — user_id=%s", semis_id, user_id)
    await query.edit_message_text(
        f"✅ Lot *{pending['labels'].get(semis_id, semis_id)}* sélectionné.",
        parse_mode="Markdown",
        reply_markup=None,
    )

    from .saisie import _parse_and_save   # import tardif : saisie importe ce module
    await _parse_and_save(
        update, pending["texte"], pre_parsed_items=[parsed], geste_file=pending.get("geste_file"),
    )


async def _noter_levee_en_observation(query, parsed: dict, texte: str) -> None:
    """[US-212 / CA4] Le semis est en pleine terre : la phrase du jardinier est gardée
    telle quelle en observation (US-038), sans appel au modèle ni stock touché."""
    champs = {
        "culture": parsed.get("culture"),
        "variete": parsed.get("variete"),
        "constat": (texte or "").strip(),
        "date": parsed.get("date"),
    }
    db = SessionLocal()
    try:
        svc_evenements.creer_evenement_observation(db, current_context(), champs, texte, "Levée")
    except svc_evenements.EvenementInvalideError as e:
        db.rollback()
        await query.edit_message_text(f"❌ {e}", reply_markup=None)
        return
    finally:
        db.close()
    await query.edit_message_text(
        "✅ *Observation enregistrée* — levée d'un semis en pleine terre.",
        parse_mode="Markdown", reply_markup=None,
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

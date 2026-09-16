"""Cœur de la saisie dictée : _parse_and_save et les rappels qui y reviennent.

Module extrait de l'ancien bot.py monolithique (découpage 2026-09).
"""
import json
import time
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from database.db import SessionLocal
from utils.actions import normalize_action
from utils.parcelles import create_parcelle, get_all_parcelles, resolve_parcelle
from llm.parseur_deterministe import ORIGINE_LLM
from llm.passerelle import LLMIndisponibleError, MESSAGE_REPLI_IA
from utils.culture_resolve import resolve_culture, resolve_variete
from app.services.context import current_context
from app.services import parcelles as svc_parcelles
from app.services.permissions import require_role, PermissionInsuffisanteError
from .noyau import MENU_KEYBOARD, _md, log
from .etat import (
    _ACTIONS_SOURCE,
    _ACTION_PENDING,
    _GODET_PENDING,
    _PERTE_PENDING,
    _QUANTITE_PENDING,
    _RECOLTE_PENDING,
    _RECOLTE_PIECES_PENDING,
    _RECOLTE_TIMEOUT,
    _SEMIS_CULTURE_PENDING,
    _SEMIS_CULTURE_TIMEOUT,
    _VENDU_PENDING,
)
from .normalisation import _normalize_items, _parser_items
from .enregistrement import (
    _boutons_confirmation,
    _build_action_summary,
    _get_parcelles_avec_culture,
    _preparer_contexte_semis,
)
from .godets import _demander_graines_godet_si_manquant, _demander_lot_godet_si_ambigu
from .pertes import _save_perte_item, _stock_variete_jardin, _variete_reelle
from .interpretation import _UpdateCommande, _message_de
from .questions import _ask_question


# ── [CA19] Créer la parcelle manquante dans la foulée du geste ────────────────
# Le seul point où deux flux se rejoignent. La phrase d'origine est CONSERVÉE
# pour être rejouée après création, jamais reconstruite : le jardinier n'a pas à
# la redire, et le geste enregistré reste exactement celui qu'il a dicté.
_CREATION_PARCELLE_PENDING: dict[int, dict] = {}


async def _proposer_creation_parcelle_du_geste(
    update: Update, items: list, texte: str, msg=None
) -> bool:
    """Propose de créer la parcelle citée par un geste quand elle n'existe pas.

    Retourne True si la proposition a été faite (le geste est alors en attente).
    Refuser laisse le flux de désambiguïsation actuel se dérouler à l'identique
    (CA19), et aucune parcelle n'est créée sans cette confirmation explicite
    (CA20) — la règle d'US-094 n'est pas assouplie, elle est outillée.
    """
    if len(items) != 1:
        return False
    nom_parcelle = (items[0].get("parcelle") or "").strip()
    if not nom_parcelle:
        return False

    db = SessionLocal()
    try:
        if resolve_parcelle(db, nom_parcelle, potager_id=current_context().potager_id) is not None:
            return False
    finally:
        db.close()

    user_id = update.effective_user.id
    _CREATION_PARCELLE_PENDING[user_id] = {
        "items": items, "texte": texte, "nom": nom_parcelle, "ts": time.time(),
    }
    resume = _build_action_summary(items).splitlines()[0] if items else ""
    boutons = [[
        InlineKeyboardButton("✅ Créer et enregistrer", callback_data="interpparc:ok"),
        InlineKeyboardButton("❌ Non", callback_data="interpparc:non"),
    ]]
    texte_msg = (
        f"📍 La parcelle *{_md(nom_parcelle.upper())}* n'existe pas.\n"
        f"La créer et enregistrer ce geste ?\n\n_{_md(resume)}_"
    )
    log.info("[US-172 CA19] Parcelle inconnue citée par un geste : %r", nom_parcelle)
    if msg is not None:
        await msg.edit_text(texte_msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(boutons))
    else:
        await _message_de(update).reply_text(
            texte_msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(boutons)
        )
    return True


async def _creation_parcelle_geste_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """[CA19, CA20] Callback de la création de parcelle proposée par un geste."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    pending = _CREATION_PARCELLE_PENDING.pop(user_id, None)
    if pending is None:
        await query.edit_message_text("⏱ Demande expirée. Redites votre geste.", reply_markup=None)
        return

    items, texte, nom = pending["items"], pending["texte"], pending["nom"]

    if query.data == "interpparc:non":
        # Le geste continue sans la parcelle inconnue : le flux de
        # désambiguïsation existant reprend, à l'identique.
        for item in items:
            item.pop("parcelle", None)
        log.info("[US-172 CA19] Création refusée — désambiguïsation habituelle")
        await query.edit_message_text("↩️ Parcelle non créée.", reply_markup=None)
        await _parse_and_save(_UpdateCommande(update), texte, pre_parsed_items=items)
        return

    db = SessionLocal()
    try:
        nouvelle = create_parcelle(db, nom, potager_id=current_context().potager_id)
        log.info("[US-172 CA19] Parcelle créée dans la foulée du geste : %r", nouvelle.nom)
    except ValueError as e:
        await query.edit_message_text(f"❌ {e}", reply_markup=None)
        return
    finally:
        db.close()

    await query.edit_message_text(
        f"✅ Parcelle *{_md(nouvelle.nom.upper())}* créée.", parse_mode="Markdown", reply_markup=None
    )
    # La phrase d'origine est rejouée telle quelle : le jardinier n'a rien à
    # redire, et le geste part au flux de validation habituel (US-021).
    await _parse_and_save(_UpdateCommande(update), texte, pre_parsed_items=items)


async def _recolte_variete_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback inline — sélection de variété pour une récolte ambiguë."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    pending = _RECOLTE_PENDING.pop(user_id, None)

    if pending is None:
        await query.edit_message_text("⏱ Action expirée. Veuillez re-saisir votre récolte.")
        return

    import time as _time_mod
    if _time_mod.time() - pending["ts"] > _RECOLTE_TIMEOUT:
        await query.edit_message_text("⏱ *Action annulée* (timeout 60 s). Veuillez re-saisir.", parse_mode="Markdown")
        return

    data = query.data  # recolte_var:{variete} | recolte_cancel

    if data == "recolte_cancel":
        await query.edit_message_text("❌ Récolte annulée.", reply_markup=None)
        return

    if data.startswith("recolte_var:"):
        variete = data[len("recolte_var:"):]
        item    = pending["item"]
        texte   = pending["texte"]
        item["variete"] = variete
        log.info("[recolte_cb] Variété '%s' sélectionnée pour '%s' — user_id=%s", variete, item.get("culture"), user_id)

        await query.edit_message_text(
            f"✅ Variété *{variete}* sélectionnée.",
            parse_mode="Markdown",
            reply_markup=None,
        )
        # Relancer le flux de confirmation avec la variété renseignée
        await _parse_and_save(update, texte, pre_parsed_items=[item])


async def _semis_organe_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """[US-037 CA7] Callback inline — végétatif/reproducteur pour une culture inconnue lors d'un semis."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    data    = query.data  # semis_organe:végétatif | semis_organe:reproducteur | semis_organe_cancel

    if data == "semis_organe_cancel":
        _SEMIS_CULTURE_PENDING.pop(user_id, None)
        log.info(f"[US-037 CA7] Semis annulé (culture inconnue) — user_id={user_id}")
        await query.edit_message_text("❌ Semis annulé.", reply_markup=None)
        return

    pending = _SEMIS_CULTURE_PENDING.pop(user_id, None)
    if pending is None:
        await query.edit_message_text("⏱ Action expirée. Veuillez re-saisir votre semis.")
        return

    import time as _time_mod
    if _time_mod.time() - pending["ts"] > _SEMIS_CULTURE_TIMEOUT:
        await query.edit_message_text(f"⏱ *Confirmation expirée ({_SEMIS_CULTURE_TIMEOUT} s), semis annulé.*", parse_mode="Markdown")
        return

    type_organe = data[len("semis_organe:"):]
    items       = pending["items"]
    culture     = (items[0].get("culture") or "").strip()

    db = SessionLocal()
    try:
        tenant_ctx = current_context()
        cfg = svc_parcelles.get_culture_config(db, tenant_ctx, culture)
        if cfg is None:
            svc_parcelles.creer_culture_config(db, tenant_ctx, culture, type_organe)
            log.info(f"[US-037 CA7] CultureConfig créée : '{culture}' → {type_organe}")
    finally:
        db.close()

    await query.edit_message_text(
        f"✅ *{culture.capitalize()}* enregistrée comme culture *{type_organe}*.",
        parse_mode="Markdown",
        reply_markup=None,
    )
    await _parse_and_save(update, pending["texte"], pre_parsed_items=items)


# ── PARSING + SAUVEGARDE ────────────────────────────────────────────────────────
async def _parse_and_save(update: Update, texte: str, msg=None, pre_parsed_items=None):
    """Parse le texte → liste d'événements → PostgreSQL → récapitulatif.

    pre_parsed_items : items déjà extraits par parse_message() (single-pass).
    Si None, appel de secours à parse_commande() (bulk, multi-lignes, fallback).
    """
    # Gestion des callback queries : update.message peut être None
    message = update.message or (update.callback_query.message if update.callback_query else None)

    # [US-047 CA1, CA4] Garde de rôle AVANT tout appel de parsing LLM (parse_commande
    # ci-dessous) — un lecteur qui dicte une action n'y déclenche aucun appel Groq.
    try:
        require_role(current_context(), "editor", "enregistrer d'action")
    except PermissionInsuffisanteError as e:
        if msg: await msg.edit_text(f"⛔ {e}")
        else:   await message.reply_text(f"⛔ {e}")
        return

    try:
        if pre_parsed_items is not None:
            items = pre_parsed_items   # déjà parsé — pas de 2e appel LLM
        else:
            items = _parser_items(texte)
    except LLMIndisponibleError:
        # [US-092 / CA9] Aucun repli utile : sans parsing, rien à enregistrer.
        # On le dit explicitement plutôt que d'inventer un événement.
        log.warning("⏳ PARSING         : IA indisponible, action non enregistrée")
        txt = (
            f"⏳ {MESSAGE_REPLI_IA}.\n\n"
            "Ton action n'a pas été enregistrée — redis-la dans quelques minutes."
        )
        if msg: await msg.edit_text(txt)
        else:   await message.reply_text(txt)
        return
    except Exception as e:
        log.error(f"❌ ERREUR PARSING  : {e}")
        txt = f"❌ Erreur parsing : {e}\n\nEssayez de reformuler votre action."
        if msg: await msg.edit_text(txt)
        else:   await message.reply_text(txt)
        return

    # [US-094 / CA10] Un item déjà parsé porte son origine ; celui qui n'en a
    # pas vient du modèle (pre_parsed_items de parse_message, flux en attente).
    for _item in items:
        if isinstance(_item, dict):
            _item.setdefault("origine_parsing", ORIGINE_LLM)

    log.info(f"🤖 PARSING        : {json.dumps(items, ensure_ascii=False)}")
    items = _normalize_items(items, texte)
    if len(items) > 1:
        log.info(f"📦 ITEMS NORMALISÉS: {len(items)} événements à sauvegarder")

    # [US-011 bis] Retire toute culture hallucinée (absente du texte source) avant validation
    from utils.validation import strip_culture_hallucinee
    for i, item in enumerate(items):
        culture_avant = item.get("culture")
        items[i] = strip_culture_hallucinee(item, texte)
        if culture_avant and items[i].get("culture") is None:
            log.warning(f"⚠️ CULTURE HALLUCINÉE : '{culture_avant}' absente du texte → retirée | texte={texte!r}")

    # [fix doublons orthographiques] Résout culture/variété vers les valeurs canoniques
    # déjà en base (ex: "creme"/"cerise" dictés → variété déjà connue), pour ce pipeline
    # de dictée directe. Jusqu'ici cette canonisation n'existait que dans le flux "notes"
    # (_note_details_received) — le flux normal enregistrait la variété brute telle
    # quelle, fragmentant silencieusement les variétés en base au moindre écart d'orthographe.
    if any(item.get("culture") for item in items):
        db_resolve = SessionLocal()
        try:
            for item in items:
                if not item.get("culture"):
                    continue
                culture_resolue = resolve_culture(db_resolve, current_context().potager_id, item["culture"])
                if culture_resolue != item["culture"]:
                    log.info(f"[resolve] Culture '{item['culture']}' → '{culture_resolue}'")
                item["culture"] = culture_resolue
                if item.get("variete"):
                    variete_resolue = resolve_variete(db_resolve, current_context().potager_id, culture_resolue, item["variete"])
                    if variete_resolue != item["variete"]:
                        log.info(f"[resolve] Variété '{item['variete']}' → '{variete_resolue}'")
                    item["variete"] = variete_resolue
        finally:
            db_resolve.close()

    # [US-011] Validation post-parsing — filtre les hallucinations Groq en Python pur
    from utils.validation import validate_parsed_action
    validated = []
    action_none_detected = False
    for item in items:
        is_valid, reason = validate_parsed_action(item, texte)
        if not is_valid:
            log.warning(f"❌ VALIDATION US011: {reason} | item={json.dumps(item, ensure_ascii=False)}")
            if "manquante" in reason or "None" in reason:
                action_none_detected = True
        else:
            validated.append(item)
    items = validated

    if not items:
        if action_none_detected:
            # Groq a parsé une question comme action → reroutage vers le flux interrogation
            log.info(f"❓ REROUTAGE US011 : action=None détectée → _ask_question('{texte}')")
            await _ask_question(update, texte)
        else:
            await message.reply_text("❌ Aucune action détectée.")
        return

    # Cas JSON sans action ni culture → phrase non reconnue comme action potager
    first = items[0] if items else {}
    if not (first.get("action") or first.get("culture") or first.get("quantite")):
        log.warning("⚠️  JSON SANS ACTION NI CULTURE : phrase non reconnue, pas de sauvegarde")
        await message.reply_text(
            "🤔 Je n'ai pas compris cette action.\n\n"
            "• Pour enregistrer : _\"Récolté 2 kg de tomates hier\"_\n"
            "• Pour interroger  : _\"Combien de tomates ai-je récolté ?\"_",
            parse_mode="Markdown",
            reply_markup=MENU_KEYBOARD
        )
        return

    # Cas ambiguïté rang/quantité détectée par Groq
    if len(items) == 1 and items[0].get("action") == "AMBIGUE":
        hint = items[0].get("commentaire", "précisez le nombre de plants par rang et le nombre de rangs")
        await message.reply_text(
            "🤔 *Précision nécessaire*\n\n"
            "Je n'ai pas bien compris la quantité et les rangs.\n\n"
            "Reformulez en précisant :\n"
            f"_{hint}_\n\n"
            "Exemple : _planter 10 choux-fleurs par rang sur 3 rangs parcelle nord_",
            parse_mode="Markdown",
            reply_markup=MENU_KEYBOARD
        )
        return

    # [US-049] Garde-fou "culture jamais plantée" — appelle la validation centrale
    # unique (app/services/evenements.py::valider_evenement), qui reste de toute
    # façon l'autorité finale au moment de l'écriture (défense en profondeur) ;
    # l'appel ici n'est qu'un raccourci UX pour bloquer AVANT d'afficher un
    # récapitulatif de confirmation voué à échouer. Contrôle appliqué à CHAQUE item,
    # pas seulement au premier — c'est l'ancienne restriction `len(items) == 1` qui
    # avait laissé passer une culture hallucinée quand Groq segmente une phrase
    # multi-culture ("cueilli 2 kilos de cerise, tomates, nord") en plusieurs items
    # dans la même réponse JSON.
    from app.services.evenements import valider_evenement as _valider_evenement, CultureInconnueError
    db_chk = SessionLocal()
    try:
        for _item_chk in items:
            if not _item_chk.get("culture"):
                continue
            try:
                _valider_evenement(
                    db_chk, current_context(),
                    action=_item_chk.get("action"), culture=_item_chk["culture"],
                    variete=_item_chk.get("variete"), parcelle=None,
                )
            except CultureInconnueError as e:
                log.warning(f"❌ CULTURE JAMAIS PLANTÉE : '{_item_chk['culture']}' — action bloquée | texte={texte!r}")
                err = (
                    f"❌ {e}\n\n"
                    f"Vérifiez le nom, ou enregistrez d'abord un semis/plantation de *{_item_chk['culture']}*."
                )
                if msg: await msg.edit_text(err, parse_mode="Markdown")
                else:   await message.reply_text(err, parse_mode="Markdown", reply_markup=MENU_KEYBOARD)
                return
    finally:
        db_chk.close()

    # [US-037 / CA7] Semis d'une culture inconnue de CultureConfig — demander
    # à l'utilisateur si elle est végétative ou reproductive avant d'enregistrer.
    if (
        len(items) == 1
        and normalize_action(items[0].get("action")) == "semis"
        and items[0].get("culture")
    ):
        culture_semis_ca7 = items[0]["culture"].strip()
        from utils.stock import get_type_organe as _get_type_organe_ca7
        db_tmp = SessionLocal()
        try:
            type_organe_connu = _get_type_organe_ca7(db_tmp, culture_semis_ca7)
        finally:
            db_tmp.close()

        if type_organe_connu is None:
            import time as _time_ca7
            user_id = update.effective_user.id
            _SEMIS_CULTURE_PENDING[user_id] = {"items": items, "texte": texte, "ts": _time_ca7.time()}
            buttons = [
                [InlineKeyboardButton("🌱 Végétative (récolte = plante entière)", callback_data="semis_organe:végétatif")],
                [InlineKeyboardButton("🔁 Reproductive (récoltes multiples)", callback_data="semis_organe:reproducteur")],
                [InlineKeyboardButton("❌ Annuler", callback_data="semis_organe_cancel")],
            ]
            await message.reply_text(
                f"🤔 *{culture_semis_ca7.capitalize()}* est une culture inconnue.\n\n"
                "Est-elle *végétative* (on récolte la plante entière, ex: carotte, salade) "
                "ou *reproductive* (on cueille plusieurs fois, ex: tomate, haricot) ?",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            log.info(
                "[US-037 CA7] Culture '%s' inconnue de CultureConfig — clarification demandée user_id=%s",
                culture_semis_ca7, user_id,
            )
            return

    # [US-019 / CA1-CA3] Interception mise_en_godet sans variété — sélection assistée
    import time as _time
    if (
        len(items) == 1
        and normalize_action(items[0].get("action")) == "mise_en_godet"
        and not items[0].get("variete")
    ):
        parsed_godet = items[0]
        culture      = parsed_godet.get("culture", "")
        user_id      = update.effective_user.id

        from utils.stock import calcul_semis_par_culture
        db_tmp = SessionLocal()
        try:
            semis_var = [
                s for s in calcul_semis_par_culture(db_tmp, culture, potager_id=current_context().potager_id)
                if s["stock_residuel"] > 0
            ]
        finally:
            db_tmp.close()

        _GODET_PENDING[user_id] = {"parsed": parsed_godet, "texte": texte, "ts": _time.time()}

        if len(semis_var) > 1:
            # CA1 — plusieurs variétés disponibles → menu inline
            buttons = []
            for s in semis_var:
                var_label = s["variete"] or "non précisée"
                cb_key    = s["variete"] if s["variete"] else "__none__"
                buttons.append([InlineKeyboardButton(
                    f"{var_label} ({s['stock_residuel']} restantes)",
                    callback_data=f"godet_var:{cb_key}"
                )])
            buttons.append([InlineKeyboardButton("❌ Annuler", callback_data="godet_cancel")])
            await message.reply_text(
                f"🪴 Pour quelle variété de *{culture}* ?",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        elif len(semis_var) == 1:
            # CA2 — une seule variété → confirmation automatique
            s   = semis_var[0]
            var = s["variete"] or "non précisée"
            parsed_godet["variete"] = s["variete"]
            buttons = [
                [InlineKeyboardButton("✅ Confirmer", callback_data="godet_confirm"),
                 InlineKeyboardButton("❌ Annuler",   callback_data="godet_cancel")]
            ]
            await message.reply_text(
                f"🪴 Je suppose la variété *{var}* (seule en pépinière, {s['stock_residuel']} restantes). Confirmer ?",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        else:
            # CA3 — aucun semis actif pour cette culture
            buttons = [
                [InlineKeyboardButton("✅ Enregistrer quand même", callback_data="godet_force"),
                 InlineKeyboardButton("❌ Annuler",                callback_data="godet_cancel")]
            ]
            await message.reply_text(
                f"⚠️ Aucun semis de *{culture}* en pépinière. Voulez-vous quand même enregistrer cette mise en godet ?",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        return  # attente callback — pas de sauvegarde immédiate

    # [fix rattachement lot godet] Mise en godet dont la variété est DÉJÀ connue :
    # le bloc US-019 ci-dessus ne s'est pas déclenché, mais le lot parent peut
    # rester ambigu (plusieurs semis échelonnés encore en germination).
    if (
        len(items) == 1
        and normalize_action(items[0].get("action")) == "mise_en_godet"
        and await _demander_lot_godet_si_ambigu(update, items[0], texte)
    ):
        return  # attente callback — pas de sauvegarde immédiate

    # [US-066] Même chemin : réclamer le « sur N graines » manquant avant d'écrire.
    if (
        len(items) == 1
        and normalize_action(items[0].get("action")) == "mise_en_godet"
        and await _demander_graines_godet_si_manquant(update, items[0], texte)
    ):
        return  # attente réponse — pas de sauvegarde immédiate

    # ── Disambiguation récolte — variété + parcelle ──────────────────────────────
    if (
        len(items) == 1
        and normalize_action(items[0].get("action")) == "recolte"
        and items[0].get("culture")
        and not items[0].get("variete")
    ):
        item_r  = items[0]
        culture = item_r["culture"]
        user_id = update.effective_user.id

        from utils.stock import calcul_stock_par_variete
        db_tmp = SessionLocal()
        try:
            varietes_stock = [
                v for v in calcul_stock_par_variete(db_tmp, culture, potager_id=current_context().potager_id)
                if (v["plants_plantes"] - v["plants_perdus"]) > 0
                and v["variete"] != "Variété non précisée"
            ]
        finally:
            db_tmp.close()

        if len(varietes_stock) > 1:
            # Plusieurs variétés en stock → menu inline
            _RECOLTE_PENDING[user_id] = {"item": item_r, "texte": texte, "ts": _time.time()}
            buttons = [
                [InlineKeyboardButton(
                    f"🌿 {v['variete']} ({int(v['plants_plantes'] - v['plants_perdus'])} plants)",
                    callback_data=f"recolte_var:{v['variete']}"
                )]
                for v in varietes_stock
            ]
            buttons.append([InlineKeyboardButton("❌ Annuler", callback_data="recolte_cancel")])
            await message.reply_text(
                f"🥬 *{culture.capitalize()}* — Quelle variété récoltez-vous ?",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            log.info("[recolte] %d variétés pour '%s' — menu inline user_id=%s", len(varietes_stock), culture, user_id)
            return

        elif len(varietes_stock) == 1:
            # Une seule variété → auto-remplir silencieusement
            item_r["variete"] = varietes_stock[0]["variete"]
            log.info("[recolte] Variété '%s' auto-déduite pour '%s'", item_r["variete"], culture)
            # pas de return → continue vers la confirmation normale

    # ── [US-036 CA10] Récolte végétative pesée sans nombre de pieds — clarification ──
    if (
        len(items) == 1
        and normalize_action(items[0].get("action")) == "recolte"
        and items[0].get("culture")
        and (items[0].get("unite") or "").lower() in {"kg", "g", "mg"}
    ):
        culture_p = items[0]["culture"]
        from utils.stock import get_type_organe
        db_tmp = SessionLocal()
        try:
            type_organe_p = get_type_organe(db_tmp, culture_p)
        finally:
            db_tmp.close()

        if type_organe_p == "végétatif":
            user_id = update.effective_user.id
            _RECOLTE_PIECES_PENDING[user_id] = {"items": items, "texte": texte, "ts": _time.time()}
            log.info("[US-036 CA10] Poids sans nb de pieds pour '%s' (végétatif) — user_id=%s", culture_p, user_id)
            await message.reply_text(
                f"🌿 Combien de pieds de *{culture_p}* avez-vous récoltés au total ? "
                "_(le poids sera conservé séparément pour le rendement)_",
                parse_mode="Markdown",
            )
            return

    # ── Disambiguation vendu — variété godet ─────────────────────────────────────
    if (
        len(items) == 1
        and normalize_action(items[0].get("action")) == "vendu"
        and items[0].get("culture")
        and not items[0].get("variete")
    ):
        item_v  = items[0]
        culture = item_v["culture"]
        user_id = update.effective_user.id

        from utils.stock import calcul_godets_par_culture as _cgpc_v
        db_tmp = SessionLocal()
        try:
            godets_dispo = _cgpc_v(db_tmp, culture, potager_id=current_context().potager_id)
        finally:
            db_tmp.close()

        if len(godets_dispo) > 1:
            # Plusieurs variétés en godet → menu inline
            _VENDU_PENDING[user_id] = {"item": item_v, "texte": texte, "ts": _time.time()}
            buttons = [
                [InlineKeyboardButton(
                    f"🪴 {g['variete'] or 'non précisée'} ({g['stock_residuel_godet']} en godet)",
                    callback_data=f"vendu_var:{g['variete'] if g['variete'] else '__none__'}",
                )]
                for g in godets_dispo
            ]
            buttons.append([InlineKeyboardButton("❌ Annuler", callback_data="vendu_cancel")])
            await message.reply_text(
                f"🪴 *{culture.capitalize()}* — Quelle variété vendez-vous ?",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            log.info("[vendu] %d variétés godet pour '%s' — menu inline user_id=%s", len(godets_dispo), culture, user_id)
            return

        elif len(godets_dispo) == 1:
            # Une seule variété → auto-remplir silencieusement
            item_v["variete"] = godets_dispo[0]["variete"]
            log.info("[vendu] Variété '%s' auto-déduite depuis godet pour '%s'", item_v["variete"], culture)
            # pas de return → continue vers la confirmation

    # ── [vendu/perte_godet] Disambiguation perte — intelligence contextuelle ──────
    if (
        len(items) == 1
        and normalize_action(items[0].get("action")) == "perte"
        and items[0].get("culture")
    ):
        item    = items[0]
        culture = item.get("culture", "")
        variete = item.get("variete")

        # ── 1. Détection du contexte dans le texte brut ─────────────────────
        from unidecode import unidecode as _ud
        texte_n = _ud(texte.lower())
        _MOTS_JARDIN    = {"potager", "jardin", "pleine terre", "en terre", "sol"}
        _MOTS_PEPINIERE = {"pepiniere", "godet", "en godet", "semis"}
        ctx_jardin    = any(m in texte_n for m in _MOTS_JARDIN)
        ctx_pepiniere = any(m in texte_n for m in _MOTS_PEPINIERE)

        # ── 2. Nettoyage : si Groq a mis un mot-clé de contexte dans variete ─
        if variete:
            v_n = _ud(variete.lower())
            if any(m in v_n for m in _MOTS_JARDIN | _MOTS_PEPINIERE):
                if any(m in v_n for m in _MOTS_PEPINIERE): ctx_pepiniere = True
                if any(m in v_n for m in _MOTS_JARDIN):    ctx_jardin    = True
                variete         = None
                item["variete"] = None

        # ── 3. Chargement des stocks disponibles ────────────────────────────
        from utils.stock import calcul_godets_par_culture as _cgpc, calcul_stock_par_variete as _csv
        from utils.parcelles import levenshtein_distance as _lev
        db_perte = SessionLocal()
        try:
            godets_dispo    = _cgpc(db_perte, culture, potager_id=current_context().potager_id)
            varietes_jardin = _csv(db_perte, culture, potager_id=current_context().potager_id)
        finally:
            db_perte.close()

        jardin_actif  = [v for v in varietes_jardin if _stock_variete_jardin(v) > 0]

        # ── 4. Fuzzy match variété sur les candidats disponibles ─────────────
        def _fuzzy_variete(needle: str, candidates: list[str]) -> str | None:
            """Retourne le candidat le plus proche (Levenshtein ≤ 2), ou None."""
            needle_n = _ud(needle.lower())
            best, best_d = None, 99
            for c in candidates:
                if not c: continue
                d = _lev(needle_n, _ud(c.lower()))
                if d < best_d:
                    best, best_d = c, d
            return best if best_d <= 2 else None

        var_jardin_matched    = None
        var_pepiniere_matched = None
        if variete:
            var_jardin_matched    = _fuzzy_variete(variete, [v.get("variete") or "" for v in jardin_actif])
            var_pepiniere_matched = _fuzzy_variete(variete, [g.get("variete") or "" for g in godets_dispo])

        # ── 5. Décision : contexte connu → court-circuit des menus ──────────
        ctx_connu = ctx_jardin or ctx_pepiniere

        if ctx_jardin and not ctx_pepiniere:
            # Contexte jardin clair
            item["action"] = "perte"
            if var_jardin_matched:
                # Variété reconnue (fuzzy) → sauvegarder directement
                item["variete"] = var_jardin_matched
                log.info(f"[perte-auto] Jardin, variété fuzzy '{variete}'→'{var_jardin_matched}'")
                await _save_perte_item(update, item, texte)
                return
            elif len(jardin_actif) == 1:
                item["variete"] = _variete_reelle(jardin_actif[0])
                log.info(f"[perte-auto] Jardin, variété unique '{item['variete']}'")
                await _save_perte_item(update, item, texte)
                return
            elif len(jardin_actif) > 1:
                # Afficher sélection variété jardin directement (sans question source)
                import time as _time
                _PERTE_PENDING[update.effective_user.id] = {
                    "item": item, "texte": texte,
                    "godets": godets_dispo, "jardin_varietes": varietes_jardin,
                    "ts": _time.time(),
                }
                buttons = []
                for v in jardin_actif:
                    var   = v["variete"] or "non précisée"
                    stock = _stock_variete_jardin(v)
                    cb    = _variete_reelle(v) or "__none__"
                    buttons.append([InlineKeyboardButton(f"🌿 {var} ({stock} plants actifs)", callback_data=f"perte_var_j:{cb}")])
                buttons.append([InlineKeyboardButton("❌ Annuler", callback_data="perte_cancel")])
                await message.reply_text(
                    f"🌿 Quelle variété de *{_md(culture)}* au potager ?",
                    parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons),
                )
                return
            # Aucune variété active au jardin → sauvegarder sans variété
            log.info(f"[perte-auto] Jardin, aucune variété active → save sans variété")
            await _save_perte_item(update, item, texte)
            return

        if ctx_pepiniere and not ctx_jardin:
            # Contexte pépinière clair
            item["action"] = "perte_godet"
            item.pop("parcelle", None)
            if var_pepiniere_matched:
                item["variete"] = var_pepiniere_matched
                log.info(f"[perte-auto] Pépinière, variété fuzzy '{variete}'→'{var_pepiniere_matched}'")
                await _save_perte_item(update, item, texte)
                return
            elif len(godets_dispo) == 1:
                item["variete"] = godets_dispo[0]["variete"]
                log.info(f"[perte-auto] Pépinière, variété unique '{item['variete']}'")
                await _save_perte_item(update, item, texte)
                return
            elif len(godets_dispo) > 1:
                import time as _time
                _PERTE_PENDING[update.effective_user.id] = {
                    "item": item, "texte": texte,
                    "godets": godets_dispo, "jardin_varietes": varietes_jardin,
                    "ts": _time.time(),
                }
                buttons = []
                for g in godets_dispo:
                    var = g["variete"] or "non précisée"
                    cb  = g["variete"] if g["variete"] else "__none__"
                    buttons.append([InlineKeyboardButton(f"🪴 {var} ({g['stock_residuel_godet']} en godet)", callback_data=f"perte_var_p:{cb}")])
                buttons.append([InlineKeyboardButton("❌ Annuler", callback_data="perte_cancel")])
                await message.reply_text(
                    f"🪴 Quelle variété de *{_md(culture)}* en pépinière ?",
                    parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons),
                )
                return
            # Aucun godet → sauvegarder sans variété
            log.info(f"[perte-auto] Pépinière, aucune variété en godet → save sans variété")
            await _save_perte_item(update, item, texte)
            return

        # ── 6. Contexte non connu : menu source si godet en stock ───────────
        import time as _time
        godets_pertinents = godets_dispo
        if godets_pertinents:
            user_id = update.effective_user.id
            _PERTE_PENDING[user_id] = {
                "item":           item,
                "texte":          texte,
                "godets":         godets_pertinents,
                "jardin_varietes": varietes_jardin,
                "ts":             _time.time(),
            }
            culture_md    = _md(culture)
            qte           = item.get("quantite", "?")
            nb_godets     = len(godets_pertinents)
            nb_jardin     = len(jardin_actif)
            lbl_jardin    = f"🌿 Au potager ({nb_jardin} variété{'s' if nb_jardin > 1 else ''} active{'s' if nb_jardin > 1 else ''})" if nb_jardin > 1 else "🌿 Au potager"
            lbl_pepiniere = f"🪴 Pépinière ({nb_godets} variété{'s' if nb_godets > 1 else ''} en godet)" if nb_godets > 1 else f"🪴 Pépinière ({godets_pertinents[0]['stock_residuel_godet']} en godet)"
            buttons = [
                [InlineKeyboardButton(lbl_jardin,    callback_data="perte_source:jardin")],
                [InlineKeyboardButton(lbl_pepiniere, callback_data="perte_source:pepiniere")],
                [InlineKeyboardButton("❌ Annuler",   callback_data="perte_cancel")],
            ]
            var_lbl = f" *{variete}*" if variete else ""
            await message.reply_text(
                f"🤔 Perte de *{qte} {culture_md}*{var_lbl} — au potager ou en pépinière ?",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            return  # attente callback

        # ── 7. Aucun godet, aucun contexte → disambiguation variété jardin ───
        # (même logique que récolte : auto-remplir si unique, menu si plusieurs)
        if not godets_pertinents and jardin_actif and not variete:
            if len(jardin_actif) == 1:
                item["variete"] = _variete_reelle(jardin_actif[0])
                log.info("[perte-auto] Aucun godet, variété unique jardin '%s' → auto-remplie", item["variete"])
                # pas de return → continue vers la confirmation
            else:
                # Plusieurs variétés au jardin → menu inline
                _PERTE_PENDING[update.effective_user.id] = {
                    "item": item, "texte": texte,
                    "godets": [], "jardin_varietes": varietes_jardin,
                    "ts": _time.time(),
                }
                buttons_var = [
                    [InlineKeyboardButton(
                        f"🌿 {v['variete'] or 'non précisée'} ({_stock_variete_jardin(v)} plants actifs)",
                        callback_data=f"perte_var_j:{_variete_reelle(v) or '__none__'}",
                    )]
                    for v in jardin_actif
                ]
                buttons_var.append([InlineKeyboardButton("❌ Annuler", callback_data="perte_cancel")])
                await message.reply_text(
                    f"🌿 Quelle variété de *{_md(culture)}* avez-vous perdu ?",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(buttons_var),
                )
                log.info("[perte] %d variétés jardin pour '%s', aucun godet — menu inline user_id=%s",
                         len(jardin_actif), culture, update.effective_user.id)
                return

    # [US-021] Confirmation avant enregistrement
    import time as _time
    user_id = update.effective_user.id
    _ACTION_PENDING[user_id] = {"items": items, "texte": texte, "ts": _time.time()}

    # Actions pépinière → jamais de parcelle (godets non localisés dans une parcelle)
    # [fix bug id=351] mise_en_godet ajouté — un godet n'est jamais rattaché à une
    # parcelle, cette liste doit rester alignée avec `parcelle_id=None` forcé par
    # creer_evenement_godet (sinon CA8 propose une parcelle réelle, ex. "serre",
    # qui finit par être assignée à un événement qui ne devrait jamais en avoir).
    _ACTIONS_PEPINIERE = {"vendu", "perte_godet", "mise_en_godet"}

    # [US-172 / CA19, CA20] Le geste cite une parcelle qui n'existe pas ?
    # Jusqu'ici, le jardinier devait quitter sa phrase, taper une commande de
    # création, puis la redicter. On la lui propose ici, avant toute
    # désambiguïsation — et la phrase d'origine est conservée pour être rejouée
    # telle quelle, jamais reconstruite. Refuser laisse le flux ci-dessous se
    # dérouler à l'identique.
    if await _proposer_creation_parcelle_du_geste(update, items, texte, msg):
        return

    # [US-049] Incohérence culture/variété ↔ parcelle citée — appelle la validation
    # centrale (app/services/evenements.py::valider_evenement) au lieu de recalculer
    # le prédicat ici, pour ne jamais diverger de la règle réellement appliquée à
    # l'écriture. Si invalide, la parcelle citée n'est PAS retenue telle quelle —
    # elle est retirée pour que le bloc CA8 ci-dessous la redétermine (auto-
    # assignation ou menu, cas item unique), exactement comme si l'utilisateur
    # n'avait rien précisé. Contrôle appliqué à CHAQUE item (CA3 US-049 : aucune
    # règle ne doit dépendre du nombre d'items traités dans le même appel).
    from app.services.evenements import valider_evenement as _valider_evenement2, ParcelleIncoherenteError
    db_tmp = SessionLocal()
    try:
        for _item_coh in items:
            if not (_item_coh.get("parcelle") and _item_coh.get("culture")):
                continue
            if (_item_coh.get("type_action") or _item_coh.get("action") or "") in _ACTIONS_SOURCE:
                continue
            culture      = _item_coh["culture"]
            variete      = _item_coh.get("variete") or None
            nom_parcelle = _item_coh["parcelle"]
            parcelle_resolue = resolve_parcelle(db_tmp, nom_parcelle, potager_id=current_context().potager_id)
            if parcelle_resolue is None:
                continue   # parcelle inconnue : gérée séparément au moment de l'écriture
            try:
                _valider_evenement2(
                    db_tmp, current_context(),
                    action=_item_coh.get("action"), culture=culture,
                    variete=variete, parcelle=parcelle_resolue,
                )
            except ParcelleIncoherenteError as e:
                autres = []
                if variete:
                    # La variété n'est pas connue sur CETTE parcelle : indiquer où
                    # elle a été plantée si elle existe ailleurs, pour aider au choix.
                    parcelles_culture_seule = _get_parcelles_avec_culture(db_tmp, culture, None)
                    autres = sorted({
                        p.nom for p in parcelles_culture_seule if p.id != parcelle_resolue.id
                    })
                suffixe = f" (trouvé sur : {', '.join(autres)})" if autres else ""
                label = f"{e.culture} {e.variete}" if e.variete else e.culture
                _item_coh["_avertissement_coherence"] = (
                    f"⚠️ Aucune trace de *{label}* sur *{e.parcelle_nom}*{suffixe}."
                )
                log.warning("[coherence-check] %s — parcelle retirée, redétection via CA8", str(e))
                del _item_coh["parcelle"]
    finally:
        db_tmp.close()

    # [CA8/CA11] Parcelle absente sur action simple → sélection intelligente
    if len(items) == 1 and not items[0].get("parcelle"):
        action_type = items[0].get("type_action") or items[0].get("action") or ""
        culture     = items[0].get("culture") or ""
        variete     = items[0].get("variete") or None

        if action_type not in _ACTIONS_PEPINIERE:
            db_tmp = SessionLocal()
            try:
                if action_type not in _ACTIONS_SOURCE and culture:
                    # Actions sur culture déjà en place → chercher les parcelles où elle a été plantée
                    parcelles_culture = _get_parcelles_avec_culture(db_tmp, culture, variete)
                else:
                    parcelles_culture = []

                if parcelles_culture and len(parcelles_culture) == 1:
                    # Une seule parcelle connue → auto-assignation silencieuse
                    items[0]["parcelle"] = parcelles_culture[0].nom
                    log.info(f"[US-021] Parcelle auto-détectée : {parcelles_culture[0].nom!r} pour {culture!r}")

                elif parcelles_culture:
                    # Plusieurs parcelles avec cette culture → proposer uniquement celles-là
                    items[0]["_parcelle_demandee"] = True
                    summary = _build_action_summary(items)
                    buttons = [
                        [InlineKeyboardButton(f"📍 {p.nom}", callback_data=f"action_parcelle:{p.nom}")]
                        for p in parcelles_culture
                    ]
                    buttons.append([InlineKeyboardButton("📍 Sans parcelle", callback_data="action_parcelle_none")])
                    log.info(f"[US-021 CA8] {len(parcelles_culture)} parcelles pour {culture!r} — user_id={user_id}")
                    await message.reply_text(
                        summary + f"\n\n*Dans quelle parcelle ?* _(parcelles avec {culture})_",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup(buttons),
                    )
                    return

                else:
                    # Aucune plantation connue ou action source → liste complète
                    parcelles_actives = get_all_parcelles(db_tmp, potager_id=current_context().potager_id)
                    if parcelles_actives:
                        items[0]["_parcelle_demandee"] = True
                        summary = _build_action_summary(items)
                        buttons = [
                            [InlineKeyboardButton(f"📍 {p.nom}", callback_data=f"action_parcelle:{p.nom}")]
                            for p in parcelles_actives
                        ]
                        buttons.append([InlineKeyboardButton("📍 Sans parcelle", callback_data="action_parcelle_none")])
                        log.info(f"[US-021 CA8] Sélection parcelle (liste complète) — user_id={user_id}")
                        await message.reply_text(
                            summary + "\n\n*Quelle parcelle ?*",
                            parse_mode="Markdown",
                            reply_markup=InlineKeyboardMarkup(buttons),
                        )
                        return
            finally:
                db_tmp.close()

    # [US-021 CA9] Quantité manquante pour actions clés → demander avant confirmation
    if (
        len(items) == 1
        and normalize_action(items[0].get("action")) in ["recolte", "semis", "plantation"]
        and not items[0].get("quantite")
    ):
        user_id = update.effective_user.id
        _QUANTITE_PENDING[user_id] = {"items": items, "texte": texte, "ts": _time.time()}
        log.info(f"[US-021 CA9] Quantité manquante pour '{items[0].get('action')}' — user_id={user_id}")
        await message.reply_text(
            "Quelle quantité ? (ex: 2 kg, 15 plants, 1 sachet...)"
        )
        return

    # Parcelle déjà renseignée ou aucune parcelle active → confirmation directe
    # [US-069 / CA2, CA3] Contexte des semis : dit, proposé, ou laissé vide.
    _preparer_contexte_semis(items, texte)
    summary = _build_action_summary(items)
    log.info(f"[US-021] Confirmation demandée — user_id={user_id}, {len(items)} item(s)")
    await message.reply_text(
        summary,
        parse_mode="Markdown",
        reply_markup=_boutons_confirmation(items),
    )


# ══════════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════
# [vendu/perte_godet] Commande /vendre
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_vendre(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /vendre [culture] [variete] [quantite] — Enregistre une vente de plants de pépinière.

    Exemple : /vendre tomate cerise 5
    """
    if not ctx.args or len(ctx.args) < 2:
        await update.message.reply_text(
            "🪴 *Vente de plants pépinière*\n\n"
            "Usage : `/vendre [culture] [variété] [quantité]`\n"
            "Exemple : `/vendre tomate cerise 5`\n\n"
            "Ou dictez naturellement : _\"vendu 5 tomates cerise\"_",
            parse_mode="Markdown",
        )
        return

    # Parse des arguments
    args = ctx.args
    try:
        quantite = int(args[-1])
        if len(args) >= 3:
            culture = args[0].lower()
            variete = " ".join(args[1:-1])
        else:
            culture = args[0].lower()
            variete = None
    except ValueError:
        culture  = args[0].lower()
        variete  = " ".join(args[1:]) if len(args) > 1 else None
        quantite = None

    texte_synth = f"vendu {quantite or ''} {culture}{' ' + variete if variete else ''}".strip()
    item = {
        "action":   "vendu",
        "culture":  culture,
        "variete":  variete,
        "quantite": quantite,
        "unite":    "plants",
    }
    await _parse_and_save(update, texte_synth, pre_parsed_items=[item])

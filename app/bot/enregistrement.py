"""Récapitulatif, confirmation et écriture des événements (_do_save_items).

Module extrait de l'ancien bot.py monolithique (découpage 2026-09).
"""
import time
from typing import Optional

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from database.db import SessionLocal
from utils.actions import normalize_action
from utils.parcelles import resolve_parcelle
from llm.passerelle import LLMIndisponibleError, MESSAGE_REPLI_IA
from utils.tts import send_voice_reply
from app.services.context import current_context
from app.services import evenements as svc_evenements
from app.services import parcelles as svc_parcelles
from app.services import avertissements_plantation as svc_avertissements
from app.services import contexte_semis as svc_contexte_semis
from app.services.permissions import require_role, PermissionInsuffisanteError
from datetime import date
from .noyau import (
    AFTER_RECORD_KEYBOARD,
    MENU_KEYBOARD,
    _md,
    log,
)
from .etat import _ACTION_PENDING, _ACTION_TIMEOUT
from .normalisation import _normalize_items, _parser_items


# ── PARSING MULTI-LIGNES ─────────────────────────────────────────────────────────
async def _parse_multi(update, lignes: list, msg=None):
    """Traite chaque ligne séparément → chaque événement a son propre texte_original et sa propre date."""
    # [US-047 CA1, CA4] Garde de rôle AVANT tout appel de parsing LLM (parse_commande
    # par ligne ci-dessous).
    try:
        require_role(current_context(), "editor", "enregistrer d'action")
    except PermissionInsuffisanteError as e:
        txt = f"⛔ {e}"
        if msg: await msg.edit_text(txt)
        else:   await update.message.reply_text(txt)
        return

    log.info(f"📋 MULTI-LIGNES    : {len(lignes)} phrases à traiter séparément")
    total_saved = []
    avertissements: list[str] = []  # [US-167]

    for i, ligne in enumerate(lignes, 1):
        log.info(f"  [{i}/{len(lignes)}] Traitement : {ligne}")
        try:
            items = _parser_items(ligne)
            items = _normalize_items(items, ligne)
            from utils.validation import strip_culture_hallucinee
            for j, item in enumerate(items):
                culture_avant = item.get("culture")
                items[j] = strip_culture_hallucinee(item, ligne)
                if culture_avant and items[j].get("culture") is None:
                    log.warning(f"  [{i}] ⚠️ CULTURE HALLUCINÉE : '{culture_avant}' absente du texte → retirée | ligne={ligne!r}")
        except LLMIndisponibleError:
            # [US-092 / CA9] Inutile de tenter les lignes suivantes : le
            # fournisseur est saturé, chacune consommerait une nouvelle
            # tentative pour le même échec. On arrête et on le dit.
            log.warning(f"  [{i}] ⏳ IA indisponible → arrêt du traitement multi-lignes")
            txt = (
                f"⏳ {MESSAGE_REPLI_IA}.\n\n"
                f"{len(total_saved)} action(s) enregistrée(s) avant l'interruption — "
                "redis les suivantes dans quelques minutes."
            )
            if msg: await msg.edit_text(txt)
            else:   await update.message.reply_text(txt)
            return
        except Exception as e:
            log.error(f"  [{i}] Erreur parsing : {e}")
            continue

        first = items[0] if items else {}
        if not (first.get("action") or first.get("culture") or first.get("quantite")):
            log.warning(f"  [{i}] JSON sans action ni culture — ignoré : {ligne}")
            continue

        db = SessionLocal()
        try:
            # [US-167] Évalué AVANT l'écriture ci-dessous, sur l'historique de
            # cette ligne — sinon l'événement qu'on est en train de créer se
            # compterait comme son propre antécédent de rotation.
            avertissements.extend(_evaluer_avertissements_avant_ecriture(db, current_context(), items))

            for parsed in items:
                event = svc_evenements.creer_evenement_ligne(db, current_context(), parsed, ligne)
                log.info(f"  💾 DB SAVE : id={event.id} | action={event.type_action} | culture={event.culture} | parcelle_id={event.parcelle_id} | date={event.date}")
                total_saved.append((parsed, event.id))
        except Exception as e:
            db.rollback()
            log.error(f"  [{i}] Erreur DB : {e}")
        finally:
            db.close()

    # Récapitulatif global
    if not total_saved:
        if msg: await msg.edit_text("❌ Aucune action reconnue.")
        return

    lines_out = [f"✅ *{len(total_saved)} action(s) enregistrée(s)*\n"]
    for parsed, eid in total_saved:
        cult  = parsed.get("culture") or "—"
        act   = parsed.get("action")  or "?"
        d     = parsed.get("date")    or "aujourd'hui"
        lines_out.append(f"• #{eid} *{act}* — {cult} _{d}_")

    recap = "\n".join(lines_out)
    if msg:   await msg.edit_text(recap, parse_mode="Markdown")
    else:     await update.message.reply_text(recap, parse_mode="Markdown")

    # [US-167 / CA1-CA3] Avertissement de rotation/association (calculé plus
    # haut, avant l'écriture) — après la confirmation d'enregistrement
    # ci-dessus, jamais à sa place.
    if avertissements:
        await update.message.reply_text("\n".join(avertissements))

    await update.message.reply_text(
        "_Que voulez-vous faire ensuite ?_",
        parse_mode="Markdown",
        reply_markup=AFTER_RECORD_KEYBOARD
    )
    refreshed = SessionLocal()
    try:
        nb = svc_evenements.compter_evenements(refreshed, current_context())
        # pas de reply ici, juste log
        log.info(f"📦 TOTAL BASE     : {nb} événements")
    finally:
        refreshed.close()


    # [US-037] La condition de "localisation" d'une culture (_cond_localisation_culture)
    # vit désormais dans app/services/evenements.py, seul module qui construit encore
    # des requêtes sur Evenement/Parcelle pour cette logique.


def _get_parcelles_avec_culture(db, culture: str, variete: str | None) -> list:
    """Retourne les parcelles distinctes où cette culture a été plantée ou semée en pleine terre."""
    return svc_parcelles.parcelles_avec_culture(db, current_context(), culture, variete)


def _ligne_contexte_semis(p: dict) -> "str | None":
    """[US-069 / CA2, CA3] Ligne « Filière » du récapitulatif d'un semis : le
    contexte dit, ou celui qui est PROPOSÉ (et pourquoi), ou « non précisée »."""
    if normalize_action(p.get("action")) != svc_contexte_semis.ACTION_SEMIS:
        return None
    if p.get("contexte_semis"):
        return f"🧭 Filière : *{svc_contexte_semis.libelle_contexte(p['contexte_semis'])}*"
    if p.get("_contexte_propose"):
        motif = p.get("_contexte_motif")
        suffixe = f" _(proposée : {_md(motif)})_" if motif else " _(proposée)_"
        return f"🧭 Filière : *{svc_contexte_semis.libelle_contexte(p['_contexte_propose'])}*{suffixe}"
    return "🧭 Filière : _non précisée_"


def _preparer_contexte_semis(items: list[dict], texte: str) -> None:
    """[US-069 / CA2, CA3] Contexte des semis d'une saisie, AVANT confirmation.

    - dit dans la phrase (ou lu par la grammaire) → retenu tel quel ;
    - sinon, pour une saisie d'UN seul geste, une proposition est calculée
      (`_contexte_propose`), que le bouton « Confirmer » adopte en un geste ;
    - sinon rien : le semis s'enregistrera sans contexte.
    Aucune question n'est posée ici — pas d'interrogatoire sur une dictée
    multi-gestes (point de vigilance de l'US), et une proposition impossible ne
    bloque rien (CA9). Rejouable : ne touche jamais un contexte déjà tranché.
    """
    semis = [i for i in items if normalize_action(i.get("action")) == svc_contexte_semis.ACTION_SEMIS]
    if not semis:
        return
    dit = svc_contexte_semis.detecter_contexte(texte)
    db = SessionLocal()
    try:
        for item in semis:
            if item.get("contexte_semis"):
                item.pop("_contexte_propose", None)
                item.pop("_contexte_motif", None)
                continue
            if dit:
                item["contexte_semis"] = dit
                item.pop("_contexte_propose", None)
                item.pop("_contexte_motif", None)
                continue
            item.pop("contexte_semis", None)
            proposition = None
            if len(items) == 1:
                parcelle = (
                    resolve_parcelle(db, item["parcelle"], potager_id=current_context().potager_id)
                    if item.get("parcelle") else None
                )
                proposition = svc_contexte_semis.proposer_contexte(
                    db, item.get("culture"), current_context().potager_id, parcelle
                )
            if proposition is None:
                item.pop("_contexte_propose", None)
                item.pop("_contexte_motif", None)
            else:
                item["_contexte_propose"] = proposition.contexte
                item["_contexte_motif"] = proposition.motif
                log.info("[US-069 / CA3] Contexte proposé : %s (%s)", proposition.contexte, proposition.motif)
    finally:
        db.close()


def _boutons_confirmation(items: list[dict], geste_file: Optional[dict] = None) -> InlineKeyboardMarkup:
    """[US-021] Confirmer / Annuler — et [US-069 / CA3] pour un semis unique sans
    contexte dit, une seconde rangée qui corrige la proposition ET enregistre,
    dans le même geste. « Confirmer » adopte la proposition affichée.

    [US-224 / CA7] Un geste venu de la file offre TROIS issues nommées sans
    ambiguïté — *Confirmer* (enregistre et retire de la file), *Plus tard*
    (repose le geste dans la file, et le dit), *Abandonner ce geste* (le retire
    définitivement, et le dit). Le libellé « Annuler » disparaît de ce flux : il
    ne permettait pas de distinguer « j'annule la confirmation » de « j'annule
    le geste », et c'est cette confusion qui faisait perdre des gestes préparés.
    """
    if geste_file:
        rangees = [
            [InlineKeyboardButton("✅ Confirmer", callback_data="action_confirm")],
        ]
        # [US-224 / CA25] Un geste confirmé trois jours après son dépôt porte la
        # date de son DÉPÔT : c'est le jour où le jardinier était au potager. Le
        # récapitulatif l'affiche (ligne « 📅 Date ») et permet de la corriger —
        # d'un bouton, parce qu'un geste rattrapé de la veille se corrige d'un
        # doigt, pas en redictant la phrase. Le bouton n'apparaît que s'il
        # change quelque chose.
        if len(items) == 1 and items[0].get("date") != date.today().isoformat():
            rangees.append([InlineKeyboardButton(
                "📅 Plutôt aujourd'hui", callback_data="action_dater_aujourdhui",
            )])
        rangees.append([
            InlineKeyboardButton("⏳ Plus tard", callback_data="action_plus_tard"),
            InlineKeyboardButton("🗑 Abandonner ce geste", callback_data="action_abandonner"),
        ])
    else:
        rangees = [[
            InlineKeyboardButton("✅ Confirmer", callback_data="action_confirm"),
            InlineKeyboardButton("❌ Annuler",   callback_data="action_cancel"),
        ]]
    if len(items) == 1:
        item = items[0]
        if (
            normalize_action(item.get("action")) == svc_contexte_semis.ACTION_SEMIS
            and not item.get("contexte_semis")
        ):
            propose = item.get("_contexte_propose")
            if propose == svc_contexte_semis.CONTEXTE_PEPINIERE:
                rangees.append([
                    InlineKeyboardButton("🌿 Plutôt en pleine terre", callback_data="action_contexte:pleine_terre"),
                    InlineKeyboardButton("❔ Sans préciser", callback_data="action_contexte:aucun"),
                ])
            elif propose == svc_contexte_semis.CONTEXTE_PLEINE_TERRE:
                rangees.append([
                    InlineKeyboardButton("🪴 Plutôt en pépinière", callback_data="action_contexte:pepiniere"),
                    InlineKeyboardButton("❔ Sans préciser", callback_data="action_contexte:aucun"),
                ])
            else:
                rangees.append([
                    InlineKeyboardButton("🪴 En pépinière", callback_data="action_contexte:pepiniere"),
                    InlineKeyboardButton("🌿 En pleine terre", callback_data="action_contexte:pleine_terre"),
                ])
    return InlineKeyboardMarkup(rangees)


def _build_action_summary(items: list[dict]) -> str:
    """Construit le résumé lisible d'une ou plusieurs actions avant confirmation."""
    if len(items) == 1:
        p = items[0]
        lines = ["📝 *Je vais enregistrer :*\n"]
        action = p.get("action") or "action"
        lines.append(f"🌱 Action : *{action}*")
        if p.get("culture"):   lines.append(f"🥬 Culture : *{p['culture']}*")
        if p.get("variete"):   lines.append(f"🏷 Variété : *{p['variete']}*")
        if p.get("quantite") is not None:
            qte   = p["quantite"]
            unite = p.get("unite") or ""
            rang  = p.get("rang")
            if rang:
                lines.append(f"⚖️ Quantité : *{int(qte)} {unite}/rang × {rang} rangs*")
            else:
                lines.append(f"⚖️ Quantité : *{qte} {unite}*".strip())
        if p.get("parcelle"):
            lines.append(f"📍 Parcelle : *{p['parcelle']}*")
        elif p.get("_parcelle_demandee") is not True:
            lines.append("📍 Parcelle : ❓ non détectée")
        if p.get("date"):      lines.append(f"📅 Date : *{p['date']}*")
        ligne_contexte = _ligne_contexte_semis(p)
        if ligne_contexte:     lines.append(ligne_contexte)
        if p.get("commentaire"): lines.append(f"📝 Note : *{p['commentaire']}*")
        if p.get("_avertissement_coherence"):
            lines.append(f"\n{p['_avertissement_coherence']}")
        lines.append("\nC'est correct ?")
        return "\n".join(lines)
    else:
        lines = [f"📝 *Je vais enregistrer {len(items)} actions :*\n"]
        avertissements = []
        for i, p in enumerate(items, 1):
            action  = p.get("action") or "action"
            culture = p.get("culture") or "?"
            qte_str = f" — {p['quantite']} {p.get('unite') or ''}".strip() if p.get("quantite") is not None else ""
            lines.append(f"{i}. *{action}* {culture}{qte_str}")
            if p.get("_avertissement_coherence"):
                avertissements.append(f"{i}. {p['_avertissement_coherence']}")
        if avertissements:
            lines.append("")
            lines.extend(avertissements)
        lines.append("\nC'est correct ?")
        return "\n".join(lines)


def _evaluer_avertissements_avant_ecriture(db, tenant_ctx, items: list[dict]) -> list[str]:
    """[US-167 / CA1, CA10] Avertissements de rotation/association pour les
    items plantation/semis d'un lot — évalués AVANT toute écriture, sur
    l'historique tel qu'il était avant cette sauvegarde. Appeler ceci APRÈS
    avoir écrit les événements ferait apparaître l'événement tout juste créé
    comme son propre antécédent dans la requête de `rotation.evaluer_rotation`
    (faux conflit auto-référentiel — bug constaté en production le 02/09/2026 :
    une plantation de tomate sur une parcelle sans aucun autre antécédent se
    voyait citée comme « déjà présente cette année », elle-même). Le message
    reste affiché après la confirmation d'enregistrement chez l'appelant —
    seul le calcul est avancé plus tôt, l'ordre d'affichage ne change pas."""
    messages: list[str] = []
    for parsed in items:
        if normalize_action(parsed.get("action")) not in svc_avertissements.ACTIONS_DECLENCHANT_AVERTISSEMENT:
            continue
        nom_parcelle = parsed.get("parcelle")
        if not nom_parcelle:
            continue
        parcelle = resolve_parcelle(db, nom_parcelle, potager_id=tenant_ctx.potager_id)
        if parcelle is None:
            continue
        messages.extend(
            svc_avertissements.evaluer_avertissements_plantation(
                db, tenant_ctx, parcelle.id, parsed.get("culture")
            )
        )
    return messages


async def _do_save_items(update: Update, items: list[dict], texte: str, msg=None) -> None:
    """[US-021] Sauvegarde effective en base après confirmation utilisateur."""
    db = SessionLocal()
    saved_items = []
    try:
        # [US-167] Évalué AVANT toute écriture ci-dessous — voir la docstring
        # de `_evaluer_avertissements_avant_ecriture` pour la raison (sinon
        # l'événement qu'on est en train de créer se compte comme son propre
        # antécédent de rotation).
        avertissements = _evaluer_avertissements_avant_ecriture(db, current_context(), items)

        for parsed in items:
            # [US-049] La résolution reste ici (nécessaire pour construire l'Evenement
            # avec le bon parcelle_id), mais le BLOCAGE si la parcelle ne résout à rien
            # est désormais décidé uniquement par la validation centrale à l'intérieur
            # de creer_evenement_confirme (valider_evenement) — plus de duplication de
            # la règle "parcelle inconnue" à cet endroit.
            nom_parcelle = parsed.get("parcelle")
            parcelle_obj = resolve_parcelle(db, nom_parcelle, potager_id=current_context().potager_id) if nom_parcelle else None

            try:
                # [fix bug id=351] mise_en_godet doit toujours passer par
                # creer_evenement_godet (parcelle_id forcé à None + auto-link au
                # semis d'origine), jamais par creer_evenement_confirme — même
                # quand la variété est déjà connue (seul cas jusqu'ici routé vers
                # la fonction dédiée, via l'interception _GODET_PENDING plus haut).
                if normalize_action(parsed.get("action")) == "mise_en_godet":
                    event = svc_evenements.creer_evenement_godet(db, current_context(), parsed, texte)
                else:
                    event = svc_evenements.creer_evenement_confirme(db, current_context(), parsed, texte, parcelle_obj)
            except svc_evenements.ParcelleInconnueError as e:
                db.rollback()
                log.warning(f"⚠️ PARCELLE INCONNUE : {nom_parcelle!r} — sauvegarde bloquée")
                err_msg = f"❌ {e}\n\nCréez-la d'abord avec : `/parcelle ajouter {nom_parcelle}`"
                if msg:  await msg.edit_text(err_msg, parse_mode="Markdown")
                else:    await update.effective_message.reply_text(err_msg, parse_mode="Markdown", reply_markup=MENU_KEYBOARD)
                return
            except svc_evenements.EvenementInvalideError as e:
                # [US-049] Filet de sécurité final — la validation centrale a rejeté
                # l'événement au moment même de l'écriture. Les contrôles amont dans
                # _parse_and_save couvrent déjà l'UX normale ; ce cas ne devrait se
                # produire que si l'état du potager a changé entre la confirmation et
                # l'écriture, ou via un chemin qui aurait échappé aux contrôles amont.
                db.rollback()
                log.warning(f"❌ ÉVÉNEMENT INVALIDE (écriture) : {e} | texte={texte!r}")
                err_msg = f"❌ {e}"
                if msg:  await msg.edit_text(err_msg, parse_mode="Markdown")
                else:    await update.effective_message.reply_text(err_msg, parse_mode="Markdown", reply_markup=MENU_KEYBOARD)
                return
            # [US-069] Le récapitulatif affiche le contexte RÉELLEMENT enregistré.
            parsed["contexte_semis"] = event.contexte_semis
            saved_items.append((parsed, event.id))
    except Exception as e:
        db.rollback()
        await update.effective_message.reply_text(f"❌ Erreur base de données : {e}")
        return
    finally:
        db.close()

    if len(saved_items) == 1:
        parsed, event_id = saved_items[0]
        recap = _build_recap(parsed, event_id)
        if msg:  await msg.edit_text(recap, parse_mode="Markdown")
        else:    await update.effective_message.reply_text(recap, parse_mode="Markdown")
    else:
        lines_out = [f"✅ *{len(saved_items)} actions enregistrées !*\n"]
        for parsed, event_id in saved_items:
            cult  = parsed.get("culture") or "?"
            qte   = str(parsed["quantite"]) + " " + (parsed.get("unite") or "") if parsed.get("quantite") else ""
            d     = parsed.get("date") or str(date.today())
            lines_out.append(f"• *{cult}* {qte} — _{d}_ ✔")
        recap_multi = "\n".join(lines_out)
        if msg:  await msg.edit_text(recap_multi, parse_mode="Markdown")
        else:    await update.effective_message.reply_text(recap_multi, parse_mode="Markdown")

    # [US-167 / CA1-CA3] Avertissement de rotation/association (calculé plus haut,
    # avant l'écriture) — TOUJOURS affiché après la confirmation ci-dessus,
    # jamais à sa place. Un simple message, pas une question : aucun état
    # conversationnel n'est ouvert ici.
    if avertissements:
        await update.effective_message.reply_text("\n".join(avertissements))

    await update.effective_message.reply_text(
        "_Que voulez-vous faire ensuite ?_",
        parse_mode="Markdown",
        reply_markup=AFTER_RECORD_KEYBOARD,
    )

    if len(saved_items) == 1:
        parsed, _ = saved_items[0]
        await send_voice_reply(update, _build_recap_tts(parsed))


async def _action_confirm_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """[US-021] Callback inline — sélection parcelle, confirmation ou annulation.

    [US-224 / CA7, CA8] Quand le récapitulatif est le niveau 2 d'un geste de la
    file, trois issues le remplacent — *Confirmer*, *Plus tard*, *Abandonner ce
    geste* — et une seule d'entre elles, avec l'abandon, retire le geste de la
    file. Un délai de confirmation dépassé, lui, ne le retire PAS : c'était la
    troisième façon de perdre un geste préparé sous US-196, et elle disparaît
    ici.
    """
    import time
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    data    = query.data

    # Annulation valide à toutes les étapes
    if data == "action_cancel":
        _ACTION_PENDING.pop(user_id, None)
        log.info(f"[US-021] Action annulée — user_id={user_id}")
        await query.edit_message_text("❌ Action annulée.", reply_markup=None)
        return

    pending = _ACTION_PENDING.get(user_id)  # ne pas pop avant confirmation finale

    # [US-224 / CA7, CA8] « Plus tard » et « Abandonner ce geste » : deux
    # issues, deux phrases distinctes, et le geste sait laquelle lui a été
    # appliquée. Traitées AVANT le contrôle de délai : reposer un geste reste
    # possible même si le récapitulatif a vieilli à l'écran.
    if data in ("action_plus_tard", "action_abandonner"):
        _ACTION_PENDING.pop(user_id, None)
        await _issue_geste_file(update, ctx, pending, data)
        return

    if pending is None:
        await query.edit_message_text("⏱ Action expirée. Veuillez re-saisir votre commande.")
        return

    if time.time() - pending["ts"] > _ACTION_TIMEOUT:
        _ACTION_PENDING.pop(user_id, None)
        if pending.get("geste_file"):
            # [US-224 / CA8] Le geste est TOUJOURS là : dépasser le délai de
            # confirmation n'est pas l'abandonner.
            await query.edit_message_text(
                f"⏱ *Confirmation expirée ({_ACTION_TIMEOUT} s).*\n\n"
                "Ce geste est toujours en attente dans votre file — /gestes le rouvre.",
                parse_mode="Markdown",
            )
        else:
            await query.edit_message_text("⏱ *Confirmation expirée (60 s), action annulée.*", parse_mode="Markdown")
        return

    # [CA9/CA10] Sélection de parcelle
    if data.startswith("action_parcelle:") or data == "action_parcelle_none":
        parcelle_nom = None if data == "action_parcelle_none" else data[len("action_parcelle:"):]
        for item in pending["items"]:
            item["parcelle"] = parcelle_nom
            item.pop("_parcelle_demandee", None)
        log.info(f"[US-021 CA9] Parcelle sélectionnée : {parcelle_nom!r} — user_id={user_id}")
        # [US-069 / CA3] Une parcelle pépinière est un indice : proposition recalculée.
        _preparer_contexte_semis(pending["items"], pending["texte"])
        summary = _build_action_summary(pending["items"])
        await query.edit_message_text(
            summary, parse_mode="Markdown",
            reply_markup=_boutons_confirmation(pending["items"], pending.get("geste_file")),
        )
        return

    # [US-224 / CA25] La date du dépôt corrigée d'un bouton — et le récapitulatif
    # se réaffiche plutôt que d'enregistrer : corriger n'est pas confirmer.
    if data == "action_dater_aujourdhui":
        for item in pending["items"]:
            item["date"] = date.today().isoformat()
        log.info("[US-224 / CA25] Date du geste ramenée au jour — user_id=%s", user_id)
        await query.edit_message_text(
            _build_action_summary(pending["items"]), parse_mode="Markdown",
            reply_markup=_boutons_confirmation(pending["items"], pending.get("geste_file")),
        )
        return

    # [US-069 / CA3] Contexte choisi au clavier : corrige la proposition ET
    # enregistre — un seul geste. « aucun » enregistre sans contexte (clé
    # présente et vide : la phrase n'est pas relue derrière ce choix).
    if data.startswith("action_contexte:"):
        choix = data[len("action_contexte:"):]
        contexte = None if choix == "aucun" else svc_contexte_semis.normaliser_contexte(choix)
        for item in pending["items"]:
            if normalize_action(item.get("action")) == svc_contexte_semis.ACTION_SEMIS:
                item["contexte_semis"] = contexte
                item.pop("_contexte_propose", None)
                item.pop("_contexte_motif", None)
        log.info(f"[US-069 / CA3] Contexte choisi : {contexte!r} — user_id={user_id}")
    else:
        # « Confirmer » adopte la proposition affichée, et elle seule.
        for item in pending["items"]:
            if item.get("_contexte_propose") and not item.get("contexte_semis"):
                item["contexte_semis"] = item.pop("_contexte_propose")
                item.pop("_contexte_motif", None)
                log.info(f"[US-069 / CA3] Proposition confirmée : {item['contexte_semis']} — user_id={user_id}")

    # action_confirm → sauvegarde effective
    _ACTION_PENDING.pop(user_id, None)
    await query.edit_message_text("⏳ Enregistrement en cours...", reply_markup=None)
    log.info(f"[US-021] Confirmation reçue — user_id={user_id}, {len(pending['items'])} item(s)")
    await _do_save_items(update, pending["items"], pending["texte"])

    # [US-224 / CA7, CA9] Le geste ne quitte la file qu'APRÈS l'écriture, jamais
    # avant : un enregistrement qui échoue doit laisser le geste en attente
    # plutôt que le faire disparaître sans trace. La confirmation faite, le
    # compagnon annonce ce qui reste et propose le suivant.
    geste_file = pending.get("geste_file")
    if geste_file:
        from app.services import file_gestes as svc_file
        from .file_gestes import proposer_suivant
        svc_file.confirmer(_GesteDeLaFile(geste_file))
        await proposer_suivant(update, ctx, geste_file["user_id"])


class _GesteDeLaFile:
    """[US-224] Le minimum dont `file_gestes` a besoin pour sortir un geste.

    L'état de confirmation (`_ACTION_PENDING`) ne garde qu'un dictionnaire —
    jamais un objet SQLAlchemy, dont la session serait refermée depuis
    longtemps au moment où le jardinier appuie. Ce porteur rend les deux seuls
    attributs que `confirmer` / `abandonner` lisent.
    """

    def __init__(self, geste_file: dict):
        self.id = geste_file["id"]
        self.potager_id = geste_file["potager_id"]


async def _issue_geste_file(
    update: Update, ctx: ContextTypes.DEFAULT_TYPE, pending: Optional[dict], data: str,
) -> None:
    """[US-224 / CA7, CA8] « Plus tard » repose le geste ; « Abandonner » le retire.

    Les deux le DISENT : c'est toute la raison d'avoir séparé ces deux libellés
    de l'« Annuler » d'US-196, qui ne permettait pas de savoir lequel des deux
    venait de se produire.
    """
    from app.services import file_gestes as svc_file
    from .file_gestes import proposer_suivant, reposer_pour_la_session

    query = update.callback_query
    geste_file = (pending or {}).get("geste_file")
    if not geste_file:
        # Un clavier de file survivant à un redémarrage du bot : l'état mémoire
        # est perdu, la file ne l'est pas — c'est justement ce qu'elle apporte.
        await query.edit_message_text(
            "⏱ Ce récapitulatif n'est plus actif, mais vos gestes sont toujours "
            "en attente — /gestes les rouvre."
        )
        return

    if data == "action_abandonner":
        svc_file.abandonner(_GesteDeLaFile(geste_file))
        log.info("[US-224 / CA7] Geste abandonné depuis le récapitulatif : id=%s", geste_file["id"])
        await query.edit_message_text(
            "🗑 *Geste abandonné* — il a été retiré de votre file, et rien n'a été "
            "enregistré.",
            parse_mode="Markdown",
        )
    else:
        reposer_pour_la_session(ctx, geste_file["id"])
        log.info("[US-224 / CA8] Geste reposé dans la file : id=%s", geste_file["id"])
        await query.edit_message_text(
            "⏳ *Geste remis en attente* — il reste dans votre file, /gestes le rouvre.",
            parse_mode="Markdown",
        )
    await proposer_suivant(update, ctx, geste_file["user_id"])


def _build_recap_tts(p: dict) -> str:
    """
    Version vocale du récapitulatif — phrase naturelle sans Markdown ni émoji.
    Ex : "Récolte enregistrée. 3 kg de tomates cerise, parcelle nord, le 2026-03-11."
    """
    parties = []
    action = p.get("action") or "action"
    parties.append(f"{action.capitalize()} enregistrée.")

    if p.get("culture"):
        qte    = p.get("quantite")
        unite  = p.get("unite") or ""
        cult   = p.get("culture")
        variete = p.get("variete")
        label  = f"{cult} {variete}".strip() if variete else cult
        if qte:
            rang = p.get("rang")
            if rang:
                total = int(qte) * int(rang)
                parties.append(f"{total} {unite} de {label} sur {rang} rangs.")
            else:
                parties.append(f"{qte} {unite} de {label}.".strip())
        else:
            parties.append(f"Culture : {label}.")

    if p.get("parcelle"):
        parties.append(f"Parcelle {p['parcelle']}.")
    if p.get("duree_minutes"):
        parties.append(f"Durée : {p['duree_minutes']} minutes.")
    if p.get("traitement"):
        parties.append(f"Traitement : {p['traitement']}.")
    if p.get("date"):
        parties.append(f"Date : {p['date']}.")
    if p.get("commentaire"):
        parties.append(p["commentaire"])

    return " ".join(parties)


def _build_recap(p: dict, event_id: int) -> str:
    """Construit le message de récapitulatif."""
    lines = ["✅ *C'est noté !* _(ID #%d)_\n" % event_id]

    # Cas spécial mise_en_godet : repiquage de plantules barquette → godet [US-016]
    action_norm = normalize_action(p.get("action")) or p.get("action") or ""
    if action_norm == "mise_en_godet":
        nb_g = p.get("nb_graines_semees")   # graines d'origine dans la barquette (optionnel)
        nb_p = p.get("nb_plants_godets")    # plants repiqués en godet (champ principal)
        taux_str = ""
        if nb_g and nb_p:
            taux = round(nb_p / nb_g * 100)
            taux_str = f" → *{taux}% de réussite*"
        lines.append("🪴 Action : *mise en godet* (repiquage plantules → godet)")
        if p.get("culture"):      lines.append(f"🥬 Culture : *{p['culture']}*")
        if p.get("variete"):      lines.append(f"🏷 Variété : *{p['variete']}*")
        if nb_p:                  lines.append(f"🌱 Plants repiqués en godet : *{nb_p}*{taux_str}")
        if nb_g:                  lines.append(f"🌾 Graines en barquette d'origine : *{nb_g}*")
        if p.get("parcelle"):     lines.append(f"📍 Parcelle : *{p['parcelle']}*")
        if p.get("date"):         lines.append(f"📅 Date : *{p['date']}*")
        if p.get("commentaire"):  lines.append(f"📝 Note : *{p['commentaire']}*")
        lines.append("\n_Que voulez-vous faire ensuite ?_")
        return "\n".join(lines)

    # Calcul quantité totale si rang présent
    qte_str  = None
    if p.get("quantite") is not None:
        qte_val = p["quantite"]
        unite   = p.get("unite") or ""
        rang    = p.get("rang")
        if rang:
            total   = int(qte_val) * int(rang)
            qte_str = f"{int(qte_val)} {unite}/rang × {rang} rangs = *{total} {unite} total*"
        else:
            qte_str = f"{qte_val} {unite}".strip()

    fields = [
        ("🌱 Action",      p.get("action")),
        ("🥬 Culture",     p.get("culture")),
        ("🏷 Variété",     p.get("variete")),
        ("⚖️ Quantité",   qte_str),
        ("📍 Parcelle",    p.get("parcelle")),
        ("🌾 Rangs",       str(p["rang"]) + " rangs" if p.get("rang") else None),
        ("⏱ Durée",       str(p["duree_minutes"]) + " min" if p.get("duree_minutes") else None),
        ("💊 Traitement",  p.get("traitement")),
        ("📅 Date",        p.get("date")),
        # [US-069] Filière du semis, seulement si elle est connue.
        ("🧭 Filière",     svc_contexte_semis.libelle_contexte(p["contexte_semis"]) if p.get("contexte_semis") else None),
        ("📝 Note",        p.get("commentaire")),
    ]

    for label, val in fields:
        if val:
            lines.append(f"{label} : *{val}*")

    lines.append("\n_Que voulez-vous faire ensuite ?_")
    return "\n".join(lines)

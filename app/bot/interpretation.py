"""Commandes dictées par une phrase [US-172] : proposition, complétion, exécution.

Module extrait de l'ancien bot.py monolithique (découpage 2026-09).
"""
import time
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler, ContextTypes
from database.db import SessionLocal
from utils.parcelles import normalize_parcelle_name, find_doublon, resolve_parcelle
from app.services.context import current_context
from app.services import menu_commandes as svc_menu_commandes
from app.services import interpreteur_commandes as svc_interpreteur
from .noyau import _md, log


# ══════════════════════════════════════════════════════════════════════════════
# [US-172] Piloter le bot par une phrase — proposition, complétion, exécution
# ══════════════════════════════════════════════════════════════════════════════
# La reconnaissance vit dans `app/services/interpreteur_commandes.py` ; ce qui
# suit est le seul code Telegram qu'elle exige : proposer, compléter, exécuter.
#
# Point de conception central (CA9) : l'exécution ne réimplémente RIEN. Elle
# retrouve le handler réellement enregistré par introspection de
# `ctx.application`, pose les arguments dans `ctx.args` et l'appelle. Une
# commande dictée traverse donc exactement le même chemin qu'une commande
# tapée — même service, mêmes contrôles de rôle, mêmes messages, mêmes claviers
# contextuels, et le même garde de liaison (CA14), puisque c'est le handler
# ENVELOPPÉ par `_avec_garde_liaison` que l'introspection retrouve.
#
# Aucune table de correspondance nom → fonction n'est tenue ici : elle
# divergerait au premier renommage, et la divergence se paierait en commande
# dictée qui n'exécute rien.

_INTERP_PENDING: dict[int, dict] = {}


# Une proposition non tranchée expire : elle porte des arguments lus dans une
# phrase, et les rejouer un quart d'heure plus tard sur un potager dont on a
# changé entre-temps n'aurait aucun sens.
_INTERP_TIMEOUT = 300  # secondes


_INTERP_MODE_COMPLETION = "interp_completion"


class _UpdateCommande:
    """Vue d'un `Update` qui expose toujours `.message`.

    Les handlers de commande écrivent via `update.message.reply_text` : appelés
    depuis un callback de bouton, où `update.message` vaut None, ils
    échoueraient. Cette vue substitue le message porteur du clavier et délègue
    tout le reste à l'Update d'origine (`effective_user`, `effective_message`,
    `callback_query`…), pour que le handler ne voie aucune différence.
    """

    def __init__(self, update: Update):
        self._update = update
        self.message = update.message or (
            update.callback_query.message if update.callback_query else None
        )

    def __getattr__(self, nom):
        return getattr(self._update, nom)


def _handler_de_commande(ctx: ContextTypes.DEFAULT_TYPE, nom: str):
    """Le handler réellement enregistré pour `/nom`, par introspection (CA6, CA9).

    Même procédé que `_noms_commandes_enregistrees` pour le menu d'US-171 : on
    lit les `CommandHandler` de l'Application plutôt qu'une liste recopiée. Ce
    qui est retourné est le callback ENVELOPPÉ, garde de liaison compris.
    """
    application = getattr(ctx, "application", None)
    for groupe in (getattr(application, "handlers", None) or {}).values():
        for handler in groupe:
            if isinstance(handler, CommandHandler) and nom in handler.commands:
                return handler.callback
    return None


def _resoudre_noms_parcelle(commande):
    """[CA12] Une commande ne s'exécute jamais sur un nom approché.

    `resolve_parcelle` rapproche « planche nord-est » de « Planche Nord »
    (Levenshtein ≤ 2, puis sous-chaîne). C'est le bon comportement pour
    rattacher un geste à une parcelle — et le mauvais pour en supprimer une :
    une suppression exécutée sur la mauvaise parcelle coûte davantage que cent
    phrases non comprises.

    L'exigence est donc l'égalité EXACTE après la normalisation habituelle du
    projet (casse, accents, espaces, tirets — `normalize_parcelle_name`, jamais
    une seconde règle). À défaut, le nom voisin est proposé au jardinier, et la
    valeur dictée est retirée de la commande pour qu'aucun chemin ne puisse
    l'exécuter telle quelle.
    """
    a_verifier = [
        argument for argument in commande.forme.arguments
        if argument.type == svc_menu_commandes.TYPE_PARCELLE
        and commande.valeurs.get(argument.nom)
    ]
    if not a_verifier:
        return commande

    db = SessionLocal()
    try:
        potager_id = current_context().potager_id
        for argument in a_verifier:
            nom_dicte = commande.valeurs[argument.nom]
            exact, _ = find_doublon(db, normalize_parcelle_name(nom_dicte), potager_id=potager_id)
            if exact is not None and exact.actif:
                continue
            voisine = resolve_parcelle(db, nom_dicte, potager_id=potager_id)
            candidats = (voisine.nom,) if voisine is not None else ()
            log.info(
                "[US-172 CA12] Parcelle %r inexacte → %s",
                nom_dicte,
                f"candidat proposé : {voisine.nom!r}" if voisine else "aucun voisin",
            )
            return commande.avec_candidats(argument.nom, candidats)
        return commande
    finally:
        db.close()


def _message_de(update: Update):
    return update.message or (update.callback_query.message if update.callback_query else None)


async def _interp_proposer(update: Update, ctx: ContextTypes.DEFAULT_TYPE, commande, msg=None) -> None:
    """Point d'entrée unique d'une commande interprétée : rien ne s'exécute ici.

    Trois issues possibles, dans cet ordre — le doute d'abord, l'incomplétude
    ensuite, la validation en dernier :
      * un nom de parcelle inexact → les voisins sont proposés (CA12) ;
      * un argument obligatoire absent → il est demandé (CA13) ;
      * sinon → récapitulatif et confirmation explicite (CA10, CA11).
    """
    commande = _resoudre_noms_parcelle(commande)
    user_id = update.effective_user.id
    log_id = svc_interpreteur.persister_journal(
        current_context(), commande, svc_interpreteur.ISSUE_PROPOSEE
    )
    svc_interpreteur.journaliser(commande, svc_interpreteur.ISSUE_PROPOSEE)
    _INTERP_PENDING[user_id] = {
        "commande": commande, "attend": None, "log_id": log_id, "ts": time.time(),
    }
    await _interp_etape_suivante(update, ctx, msg=msg)


async def _interp_etape_suivante(update: Update, ctx: ContextTypes.DEFAULT_TYPE, msg=None) -> None:
    """Affiche l'étape courante de la proposition en attente."""
    user_id = update.effective_user.id
    pending = _INTERP_PENDING.get(user_id)
    if pending is None:
        return
    commande = pending["commande"]
    message = _message_de(update)

    async def _repondre(texte: str, boutons) -> None:
        clavier = InlineKeyboardMarkup(boutons) if boutons else None
        if msg is not None:
            await msg.edit_text(texte, parse_mode="Markdown", reply_markup=clavier)
        else:
            await message.reply_text(texte, parse_mode="Markdown", reply_markup=clavier)

    # ── [CA12] Le nom dicté n'existe pas exactement ──────────────────────────
    if commande.candidats or commande.argument_candidat is not None:
        pending["attend"] = commande.argument_candidat
        boutons = [
            [InlineKeyboardButton(f"📍 {nom}", callback_data=f"interp:cand:{rang}")]
            for rang, nom in enumerate(commande.candidats)
        ]
        boutons.append([InlineKeyboardButton("❌ Annuler", callback_data="interp:non")])
        if commande.candidats:
            texte = (
                f"❓ Aucune parcelle ne porte exactement ce nom.\n"
                f"Vouliez-vous dire *{_md(commande.candidats[0].upper())}* ?"
            )
        else:
            texte = "❓ Aucune parcelle ne porte ce nom, ni un nom voisin."
        await _repondre(texte, boutons)
        return

    # ── [CA13] Un argument manquant se complète, il n'échoue pas ─────────────
    if commande.manquants:
        argument = commande.manquants[0]
        pending["attend"] = argument.nom
        ctx.user_data['mode'] = _INTERP_MODE_COMPLETION
        if argument.vocabulaire:
            # Une valeur de vocabulaire fermé se choisit, elle ne se devine
            # jamais à partir d'un synonyme approchant.
            boutons = [
                [InlineKeyboardButton(valeur, callback_data=f"interp:val:{rang}")]
                for rang, valeur in enumerate(argument.vocabulaire)
            ]
        else:
            boutons = []
        boutons.append([InlineKeyboardButton("❌ Annuler", callback_data="interp:non")])
        await _repondre(f"*{commande.forme.libelle}*\n\n{argument.question}", boutons)
        return

    # ── [CA10] Une commande de CONSULTATION s'exécute directement ────────────
    # Elle n'écrit rien : lui demander « voulez-vous vraiment afficher le
    # plan ? » doublerait chaque lecture sans rien protéger. La moitié
    # PÉDAGOGIQUE du CA10 est en revanche servie dans les deux cas — la commande
    # équivalente est rappelée, et c'est ainsi que le jardinier apprend la
    # syntaxe sans avoir eu à l'apprendre.
    if not commande.forme.confirmation:
        _INTERP_PENDING.pop(user_id, None)
        ctx.user_data['mode'] = None
        svc_interpreteur.persister_journal(
            current_context(), commande,
            svc_interpreteur.ISSUE_CONFIRMEE, pending.get("log_id"),
        )
        svc_interpreteur.journaliser(commande, svc_interpreteur.ISSUE_CONFIRMEE)
        await _repondre(f"↪️ `{commande.commande_equivalente()}`", None)
        await _interp_executer(update, ctx, commande)
        return

    # ── [CA10, CA11] Rien de ce qui ÉCRIT ne s'exécute à l'aveugle ───────────
    pending["attend"] = None
    ctx.user_data['mode'] = None
    entete = "🗑 " if commande.forme.destructrice else "➕ "
    boutons = [[
        InlineKeyboardButton("✅ Confirmer", callback_data="interp:ok"),
        InlineKeyboardButton("❌ Annuler", callback_data="interp:non"),
    ]]
    await _repondre(entete + svc_interpreteur.recapitulatif(commande), boutons)


async def _interp_executer(update: Update, ctx: ContextTypes.DEFAULT_TYPE, commande) -> None:
    """[CA9, CA14] Exécute la commande via le handler réellement enregistré."""
    handler = _handler_de_commande(ctx, commande.commande)
    message = _message_de(update)
    if handler is None:
        log.error("[US-172] /%s introuvable parmi les CommandHandler", commande.commande)
        await message.reply_text(
            f"❌ La commande /{commande.commande} n'est pas disponible.",
        )
        return
    log.info(
        "[US-172] Exécution de la commande interprétée : %s",
        commande.commande_equivalente(),
    )
    ctx.args = list(commande.args)
    await handler(_UpdateCommande(update), ctx)


async def _interp_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback inline — confirmation, refus, choix d'une valeur ou d'un nom voisin."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    pending = _INTERP_PENDING.get(user_id)

    if query.data == "interp:non":
        _INTERP_PENDING.pop(user_id, None)
        ctx.user_data['mode'] = None
        if pending is not None:
            svc_interpreteur.persister_journal(
                current_context(), pending["commande"],
                svc_interpreteur.ISSUE_REFUSEE, pending.get("log_id"),
            )
            svc_interpreteur.journaliser(pending["commande"], svc_interpreteur.ISSUE_REFUSEE)
        await query.edit_message_text("❌ Annulé — rien n'a été fait.", reply_markup=None)
        return

    if pending is None:
        await query.edit_message_text("⏱ Demande expirée. Redites-la.", reply_markup=None)
        return
    if time.time() - pending["ts"] > _INTERP_TIMEOUT:
        _INTERP_PENDING.pop(user_id, None)
        ctx.user_data['mode'] = None
        svc_interpreteur.persister_journal(
            current_context(), pending["commande"],
            svc_interpreteur.ISSUE_ABANDONNEE, pending.get("log_id"),
        )
        await query.edit_message_text("⏱ Demande expirée, rien n'a été fait.", reply_markup=None)
        return

    commande = pending["commande"]

    # ── Choix d'un nom voisin proposé (CA12) ─────────────────────────────────
    if query.data.startswith("interp:cand:"):
        try:
            choisi = commande.candidats[int(query.data.rsplit(":", 1)[1])]
        except (ValueError, IndexError):
            await query.edit_message_text("❌ Données invalides.", reply_markup=None)
            return
        pending["commande"] = commande.avec(**{commande.argument_candidat: choisi})
        await _interp_etape_suivante(update, ctx, msg=query.message)
        return

    # ── Choix d'une valeur de vocabulaire fermé (CA13) ───────────────────────
    if query.data.startswith("interp:val:"):
        argument = next(
            (a for a in commande.manquants if a.nom == pending.get("attend")), None
        )
        if argument is None:
            await query.edit_message_text("❌ Données invalides.", reply_markup=None)
            return
        try:
            valeur = argument.vocabulaire[int(query.data.rsplit(":", 1)[1])]
        except (ValueError, IndexError):
            await query.edit_message_text("❌ Données invalides.", reply_markup=None)
            return
        pending["commande"] = commande.avec(**{argument.nom: valeur})
        await _interp_etape_suivante(update, ctx, msg=query.message)
        return

    # ── Confirmation (CA10) ──────────────────────────────────────────────────
    if query.data == "interp:ok":
        _INTERP_PENDING.pop(user_id, None)
        ctx.user_data['mode'] = None
        svc_interpreteur.persister_journal(
            current_context(), commande,
            svc_interpreteur.ISSUE_CONFIRMEE, pending.get("log_id"),
        )
        svc_interpreteur.journaliser(commande, svc_interpreteur.ISSUE_CONFIRMEE)
        await query.edit_message_text(
            f"⏳ `{commande.commande_equivalente()}`", parse_mode="Markdown", reply_markup=None
        )
        await _interp_executer(update, ctx, commande)


async def _interp_completion_texte(update: Update, ctx: ContextTypes.DEFAULT_TYPE, texte: str) -> None:
    """[CA13] Réponse tapée à un argument demandé.

    Un argument de vocabulaire fermé n'accepte QUE l'une de ses valeurs : la
    saisie est comparée à la normalisation près, jamais rapprochée d'un
    synonyme. Le jardinier qui écrit « ça se marie bien » se voit reproposer les
    boutons plutôt que voir « favorable » écrit à sa place.
    """
    user_id = update.effective_user.id
    pending = _INTERP_PENDING.get(user_id)
    if pending is None or not pending.get("attend"):
        ctx.user_data['mode'] = None
        return
    commande = pending["commande"]
    argument = next((a for a in commande.manquants if a.nom == pending["attend"]), None)
    if argument is None:
        ctx.user_data['mode'] = None
        return

    valeur = (texte or "").strip()
    if argument.vocabulaire:
        normalise, _ = svc_interpreteur.normaliser(valeur)
        correspondance = next(
            (v for v in argument.vocabulaire if svc_interpreteur.normaliser(v)[0] == normalise),
            None,
        )
        if correspondance is None:
            await update.message.reply_text(
                f"❓ Valeur attendue parmi : *{'* · *'.join(argument.vocabulaire)}*",
                parse_mode="Markdown",
            )
            return
        valeur = correspondance

    pending["commande"] = commande.avec(**{argument.nom: valeur})
    await _interp_etape_suivante(update, ctx)


async def _traiter_commande_interpretee(
    update: Update, ctx: ContextTypes.DEFAULT_TYPE, resultat, msg=None
) -> bool:
    """Aiguille un résultat d'interprétation. Retourne True s'il a été pris en charge.

    [CA12] Une ambiguïté — plusieurs commandes reconnues dans la même phrase —
    n'exécute pas la plus probable : elle demande laquelle.
    """
    if resultat is None:
        return False

    message = _message_de(update)
    if isinstance(resultat, svc_interpreteur.Ambiguite):
        lignes = ["❓ *Plusieurs commandes possibles* — laquelle ?", ""]
        for candidat in resultat.candidats:
            lignes.append(f"• {candidat.forme.libelle} : `{candidat.commande_equivalente()}`")
        lignes.append("")
        lignes.append("_Reformulez, ou tapez directement la commande voulue._")
        texte = "\n".join(lignes)
        log.info(
            "[US-172 CA12] Ambiguïté (%s) → précision demandée",
            ", ".join(c.commande for c in resultat.candidats),
        )
        if msg is not None:
            await msg.edit_text(texte, parse_mode="Markdown")
        else:
            await message.reply_text(texte, parse_mode="Markdown")
        return True

    await _interp_proposer(update, ctx, resultat, msg=msg)
    return True

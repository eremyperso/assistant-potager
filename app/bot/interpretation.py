"""Commandes dictées par une phrase [US-172] : proposition, complétion, exécution.

Module extrait de l'ancien bot.py monolithique (découpage 2026-09).
"""
import secrets
import time
from typing import Optional
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler, ContextTypes
from database.db import SessionLocal
from utils.parcelles import normalize_parcelle_name, find_doublon, resolve_parcelle
from app.services.context import current_context
from app.services import menu_commandes as svc_menu_commandes
from app.services import interpreteur_commandes as svc_interpreteur
from app.services.agent import contexte_court as svc_contexte_court
from app.services import liaison_telegram as svc_liaison_telegram
from app.services import potager_actif as svc_potager_actif
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

# [US-234] Une proposition est liée à ses boutons par un identifiant court
# (`interp:ok:<id>`) et au potager où elle a été faite. Sans cela, « Confirmer »
# sous un ANCIEN message validait la proposition la plus récente — la seule que
# `_INTERP_PENDING` ait gardée — et une commande confirmée après un `/potager`
# s'exécutait dans le nouveau potager. Chaque entrée porte donc :
#   "id"         identifiant de la proposition, repris par TOUS ses boutons
#   "potager_id" potager actif au moment où elle a été faite


# Une proposition non tranchée expire : elle porte des arguments lus dans une
# phrase, et les rejouer un quart d'heure plus tard sur un potager dont on a
# changé entre-temps n'aurait aucun sens.
_INTERP_TIMEOUT = 300  # secondes


_INTERP_MODE_COMPLETION = "interp_completion"

_MSG_DEMANDE_EXPIREE = "⏱ Demande expirée, rien n'a été fait."
_MSG_POTAGER_CHANGE = (
    "⚠️ Le potager actif a changé depuis cette demande, rien n'a été fait. "
    "Redites-la dans le potager voulu."
)
_MSG_POTAGER_INCONNU = (
    "⚠️ Impossible de vérifier le potager actif, rien n'a été fait. Redites la demande."
)


def _nouvel_id_proposition(precedent: Optional[str] = None) -> str:
    """[US-234 CA1] Identifiant court d'une proposition (tient dans `callback_data`).

    Jamais égal à celui de la proposition qu'il remplace : deux demandes
    successives ne partagent ainsi aucun bouton, même par une rencontre fortuite.
    """
    while True:
        identifiant = secrets.token_hex(3)
        if identifiant != precedent:
            return identifiant


def _decoder_callback(data: str) -> tuple[str, Optional[str], Optional[str]]:
    """[US-234 CA1] `interp:<action>[:<rang>]:<id>` → (action, rang, identifiant).

    `cand` et `val` portent un rang entre l'action et l'identifiant. Un bouton
    sans identifiant — un message envoyé avant US-234 — donne `identifiant=None`
    et sera refusé comme périmé : on ne devine pas à quelle proposition il répond.
    """
    morceaux = (data or "").split(":")
    action = morceaux[1] if len(morceaux) > 1 else ""
    if action in ("cand", "val"):
        rang = morceaux[2] if len(morceaux) > 2 else None
        identifiant = morceaux[3] if len(morceaux) > 3 else None
    else:
        rang = None
        identifiant = morceaux[2] if len(morceaux) > 2 else None
    return action, rang, identifiant or None


def _contexte_au_clic(update: Update):
    """[US-234 CA3, US-237] `TenantContext` du jardinier À L'INSTANT du clic, ou None.

    `current_context()` ne convient pas ici : un callback ne passe pas par le
    garde de liaison, il lit donc le contexte par défaut. Le potager actif se
    relit en base, par le chat, comme le garde le fait pour un message.
    """
    db = None
    try:
        db = SessionLocal()
        user_id = svc_liaison_telegram.resoudre_user_id_pour_chat(db, update.effective_chat.id)
        if user_id is None:
            return None
        return svc_potager_actif.resoudre_tenant_context(db, user_id)
    except Exception:  # noqa: BLE001 — impossible de vérifier : le doute vaut refus
        log.exception("[US-234 CA3] Potager actif illisible au moment du clic")
        return None
    finally:
        if db is not None:
            db.close()


def _potager_actif_au_clic(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> Optional[int]:
    """[US-234 CA3] Potager actif du jardinier À L'INSTANT du clic, ou None."""
    contexte = _contexte_au_clic(update)
    return contexte.potager_id if contexte is not None else None


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


def _abandonner_precedente(user_id: int) -> Optional[dict]:
    """[US-234 CA7] Une nouvelle demande écrase la précédente : celle-ci n'aura
    jamais de suite, son journal le dit au lieu de rester « proposée ».
    Rend la proposition remplacée, ou None."""
    ancienne = _INTERP_PENDING.get(user_id)
    if ancienne is not None:
        svc_interpreteur.persister_journal(
            current_context(), ancienne["commande"],
            svc_interpreteur.ISSUE_ABANDONNEE, ancienne.get("log_id"),
        )
        svc_interpreteur.journaliser(ancienne["commande"], svc_interpreteur.ISSUE_ABANDONNEE)
        log.info("[US-234] Proposition %s remplacée par une nouvelle demande", ancienne.get("id"))
    return ancienne


def _ecartes_apres(ancienne: Optional[dict], nouvelle) -> tuple[str, ...]:
    """[US-238 / CA2] Les noms voisins que le jardinier a laissés de côté.

    Quand une nouvelle proposition de la MÊME commande remplace une proposition
    qui offrait des noms voisins, ces noms n'ont pas été retenus : « non,
    l'autre » ne doit pas les reproposer. Une autre commande repart de zéro.
    """
    if ancienne is None:
        return ()
    precedente = ancienne["commande"]
    if (
        not isinstance(precedente, svc_interpreteur.CommandeInterpretee)
        or not isinstance(nouvelle, svc_interpreteur.CommandeInterpretee)
        or precedente.forme.cle != nouvelle.forme.cle
        or not precedente.candidats
    ):
        return ()
    return tuple(ancienne.get("ecartes", ())) + tuple(precedente.candidats)


def contexte_court_de(update: Update):
    """[US-238 / CA1, CA5, CA6] Le contexte court du jardinier qui écrit, ou None.

    La proposition en attente est celle de CE jardinier (`_INTERP_PENDING` est
    rangé par `user_id`) ; le service la refuse si elle est expirée (CA5) ou
    faite dans un autre potager (CA6). None : la phrase est une demande nouvelle.
    """
    pending = _INTERP_PENDING.get(update.effective_user.id)
    if pending is None:
        return None
    return svc_contexte_court.construire(
        current_context(), pending["commande"], pending["ts"], pending.get("potager_id"),
        ecartes=tuple(pending.get("ecartes", ())), delai=_INTERP_TIMEOUT,
    )


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
    ancienne = _abandonner_precedente(user_id)

    log_id = svc_interpreteur.persister_journal(
        current_context(), commande, svc_interpreteur.ISSUE_PROPOSEE
    )
    svc_interpreteur.journaliser(commande, svc_interpreteur.ISSUE_PROPOSEE)
    _INTERP_PENDING[user_id] = {
        "commande": commande, "attend": None, "log_id": log_id, "ts": time.time(),
        "id": _nouvel_id_proposition(ancienne.get("id") if ancienne else None),
        "potager_id": current_context().potager_id,
        "ecartes": _ecartes_apres(ancienne, commande),
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
    # [US-234 CA1] Repris par tous les boutons de cette étape. `_interp_proposer`
    # l'a déjà posé ; l'attribuer ici garantit seulement qu'aucun bouton n'est
    # jamais affiché sans identifiant, d'où qu'ait été construite la proposition.
    ident = pending.setdefault("id", _nouvel_id_proposition())

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
            [InlineKeyboardButton(f"📍 {nom}", callback_data=f"interp:cand:{rang}:{ident}")]
            for rang, nom in enumerate(commande.candidats)
        ]
        boutons.append([InlineKeyboardButton("❌ Annuler", callback_data=f"interp:non:{ident}")])
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
                [InlineKeyboardButton(valeur, callback_data=f"interp:val:{rang}:{ident}")]
                for rang, valeur in enumerate(argument.vocabulaire)
            ]
        else:
            boutons = []
        boutons.append([InlineKeyboardButton("❌ Annuler", callback_data=f"interp:non:{ident}")])
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
        InlineKeyboardButton("✅ Confirmer", callback_data=f"interp:ok:{ident}"),
        InlineKeyboardButton("❌ Annuler", callback_data=f"interp:non:{ident}"),
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
    action, rang, identifiant = _decoder_callback(query.data)

    # ── [US-234 CA2] Un bouton ne parle que de SA proposition ────────────────
    # Ni confirmer, ni annuler, ni choisir : un bouton sous un ancien message
    # n'agit jamais sur la proposition en cours, qui reste telle quelle. La
    # proposition qu'il visait a déjà été journalisée « abandonnée » le jour
    # où elle a été remplacée (CA7).
    if pending is None or identifiant is None or identifiant != pending.get("id"):
        log.info(
            "[US-234 CA2] Bouton %r périmé (proposition en cours : %s) → rien d'exécuté",
            query.data, pending.get("id") if pending else None,
        )
        await query.edit_message_text(_MSG_DEMANDE_EXPIREE, reply_markup=None)
        return

    if action == "non":
        _INTERP_PENDING.pop(user_id, None)
        ctx.user_data['mode'] = None
        svc_interpreteur.persister_journal(
            current_context(), pending["commande"],
            svc_interpreteur.ISSUE_REFUSEE, pending.get("log_id"),
        )
        svc_interpreteur.journaliser(pending["commande"], svc_interpreteur.ISSUE_REFUSEE)
        await query.edit_message_text("❌ Annulé — rien n'a été fait.", reply_markup=None)
        return

    if time.time() - pending["ts"] > _INTERP_TIMEOUT:
        _INTERP_PENDING.pop(user_id, None)
        ctx.user_data['mode'] = None
        svc_interpreteur.persister_journal(
            current_context(), pending["commande"],
            svc_interpreteur.ISSUE_ABANDONNEE, pending.get("log_id"),
        )
        await query.edit_message_text(_MSG_DEMANDE_EXPIREE, reply_markup=None)
        return

    # ── [US-234 CA3] La commande s'exécute dans le potager où elle a été dite ─
    # Le garde de liaison, lui, résoudrait le potager ACTUEL : après un
    # `/potager`, « supprime la parcelle nord » viserait une parcelle du
    # nouveau potager. Placé avant tout choix (nom voisin, valeur), pour qu'une
    # proposition périmée ne se construise pas plus avant.
    potager_clic = _potager_actif_au_clic(update, ctx)
    if potager_clic is None or potager_clic != pending.get("potager_id"):
        log.info(
            "[US-234 CA3] Potager de la proposition %s : %s, potager actif au clic : %s → rien d'exécuté",
            pending["id"], pending.get("potager_id"), potager_clic,
        )
        _INTERP_PENDING.pop(user_id, None)
        ctx.user_data['mode'] = None
        svc_interpreteur.persister_journal(
            current_context(), pending["commande"],
            svc_interpreteur.ISSUE_ABANDONNEE, pending.get("log_id"),
        )
        svc_interpreteur.journaliser(pending["commande"], svc_interpreteur.ISSUE_ABANDONNEE)
        await query.edit_message_text(
            _MSG_POTAGER_INCONNU if potager_clic is None else _MSG_POTAGER_CHANGE,
            reply_markup=None,
        )
        return

    commande = pending["commande"]

    # ── [US-237] Un plan n'a qu'une paire de boutons : tout confirmer, annuler ─
    if isinstance(commande, svc_interpreteur.Plan):
        if action != "ok":
            await query.edit_message_text("❌ Données invalides.", reply_markup=None)
            return
        _INTERP_PENDING.pop(user_id, None)
        ctx.user_data['mode'] = None
        svc_interpreteur.persister_journal(
            current_context(), commande,
            svc_interpreteur.ISSUE_CONFIRMEE, pending.get("log_id"),
        )
        svc_interpreteur.journaliser(commande, svc_interpreteur.ISSUE_CONFIRMEE)
        await _plan_executer(update, commande, query)
        return

    # ── Choix d'un nom voisin proposé (CA12) ─────────────────────────────────
    if action == "cand":
        try:
            choisi = commande.candidats[int(rang)]
        except (TypeError, ValueError, IndexError):
            await query.edit_message_text("❌ Données invalides.", reply_markup=None)
            return
        pending["commande"] = commande.avec(**{commande.argument_candidat: choisi})
        await _interp_etape_suivante(update, ctx, msg=query.message)
        return

    # ── Choix d'une valeur de vocabulaire fermé (CA13) ───────────────────────
    if action == "val":
        argument = next(
            (a for a in commande.manquants if a.nom == pending.get("attend")), None
        )
        if argument is None:
            await query.edit_message_text("❌ Données invalides.", reply_markup=None)
            return
        try:
            valeur = argument.vocabulaire[int(rang)]
        except (TypeError, ValueError, IndexError):
            await query.edit_message_text("❌ Données invalides.", reply_markup=None)
            return
        pending["commande"] = commande.avec(**{argument.nom: valeur})
        await _interp_etape_suivante(update, ctx, msg=query.message)
        return

    # ── Confirmation (CA10) ──────────────────────────────────────────────────
    # [US-234 CA4, CA5] La proposition est retirée AVANT l'exécution : un double
    # appui trouve `_INTERP_PENDING` vide et tombe sur CA2. Ce qui s'exécute est
    # `commande`, celle qui a été affichée — la phrase n'est jamais réinterprétée.
    if action == "ok":
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


# ══════════════════════════════════════════════════════════════════════════════
# [US-237] Plusieurs commandes en une phrase — un plan, une confirmation
# ══════════════════════════════════════════════════════════════════════════════
# Un plan ne passe PAS par les handlers : ils répondent un message et rendent
# None, on ne saurait pas si l'étape 1 a réussi avant de lancer l'étape 2. Ses
# étapes passent par les exécuteurs de service (`app.services.agent.executeurs`),
# qui appellent le même service que les handlers et rendent un résultat.

async def _plan_proposer(update: Update, ctx: ContextTypes.DEFAULT_TYPE, plan, msg=None) -> None:
    """[CA5] Les étapes numérotées et UNE paire « Tout confirmer » / « Annuler »,
    liée à sa proposition et à son potager (US-234). Rien ne s'exécute ici."""
    user_id = update.effective_user.id
    ancienne = _abandonner_precedente(user_id)
    log_id = svc_interpreteur.persister_journal(current_context(), plan, svc_interpreteur.ISSUE_PROPOSEE)
    svc_interpreteur.journaliser(plan, svc_interpreteur.ISSUE_PROPOSEE)
    ident = _nouvel_id_proposition(ancienne.get("id") if ancienne else None)
    _INTERP_PENDING[user_id] = {
        "commande": plan, "attend": None, "log_id": log_id, "ts": time.time(),
        "id": ident, "potager_id": current_context().potager_id,
    }
    ctx.user_data['mode'] = None
    clavier = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Tout confirmer", callback_data=f"interp:ok:{ident}"),
        InlineKeyboardButton("❌ Annuler", callback_data=f"interp:non:{ident}"),
    ]])
    texte = "📋 " + svc_interpreteur.recapitulatif_plan(plan)
    if msg is not None:
        await msg.edit_text(texte, parse_mode="Markdown", reply_markup=clavier)
    else:
        await _message_de(update).reply_text(texte, parse_mode="Markdown", reply_markup=clavier)


async def _plan_executer(update: Update, plan, query) -> None:
    """[CA6, CA7] Exécute les étapes dans l'ordre, dans le potager vérifié au
    clic, et remplace le récapitulatif par le compte rendu ✅ ❌ ⏭."""
    from app.services.agent import executeurs as svc_executeurs
    from app.services.context import set_current_context

    contexte = _contexte_au_clic(update)
    if contexte is None:
        await query.edit_message_text(_MSG_POTAGER_INCONNU, reply_markup=None)
        return
    set_current_context(contexte)
    resultats = svc_executeurs.executer_plan(plan, contexte)
    # Texte brut : les raisons viennent du service, elles ne sont pas du Markdown.
    await query.edit_message_text(svc_executeurs.compte_rendu(plan, resultats), reply_markup=None)


def texte_aiguillage(aiguillage) -> Optional[str]:
    """[US-236 / CA4, CA5] Ce que le bot répond à une précision ou à une demande
    hors catalogue ; None pour une question ou un geste, que le flux suit."""
    # Le texte du modèle est échappé : un `_` ou un `*` qu'il écrirait casserait
    # le Markdown du message entier.
    dit = _md((aiguillage.message or "").replace("*", "").replace("`", "")).strip()
    if aiguillage.vers == svc_interpreteur.VERS_PRECISION:
        return f"❓ {dit}\n\n_Rien n'a été fait. Redis ta demande en précisant._"
    if aiguillage.vers == svc_interpreteur.VERS_HORS_PERIMETRE:
        raison = f" ({dit})" if dit else ""
        return (
            f"🤷 Je ne sais pas encore faire ça{raison}.\n\n"
            "_Ta demande est notée pour les prochaines évolutions._"
        )
    if aiguillage.vers == svc_interpreteur.VERS_NON_COMPRIS:
        # [INC-018] Une demande d'agir que ni l'agent ni l'ancien repli n'ont traitée : on le
        # dit, au lieu de laisser le routeur répondre à côté (la liste des lots en pépinière).
        return (
            "🙏 Je n'ai pas réussi à traiter cette demande : je ne l'ai pas comprise, "
            "ou le service est momentanément indisponible.\n\n"
            "_Rien n'a été fait._ Réessaie dans un instant, ou passe par la commande : "
            f"`{(aiguillage.message or '/menu').replace('`', '')}`."
        )
    return None


async def _suivre_aiguillage(message, aiguillage, msg=None) -> bool:
    """[US-236] Une précision ou un hors-périmètre reçoit sa réponse ici, et rien
    n'est proposé ni exécuté (CA4). Une question ou un geste rend False : le flux
    appelant les envoie à la cascade ou au parseur, sans reclasser (CA2, CA3)."""
    texte = texte_aiguillage(aiguillage)
    if texte is None:
        return False
    log.info("[US-236] Aiguillage %s → %s", aiguillage.vers, aiguillage.message or "-")
    if msg is not None:
        await msg.edit_text(texte, parse_mode="Markdown")
    else:
        await message.reply_text(texte, parse_mode="Markdown")
    return True


async def _traiter_commande_interpretee(
    update: Update, ctx: ContextTypes.DEFAULT_TYPE, resultat, msg=None
) -> bool:
    """Aiguille un résultat d'interprétation. Retourne True s'il a été pris en charge.

    [CA12] Une ambiguïté — plusieurs commandes reconnues dans la même phrase —
    n'exécute pas la plus probable : elle demande laquelle.
    """
    if resultat is None:
        return False

    # [US-238 / CA1] Chaque phrase interprétée devient un échange, que l'agent
    # lira si la prochaine phrase corrige ou prolonge celle-ci.
    svc_contexte_court.noter_resultat(current_context(), resultat)
    message = _message_de(update)
    if isinstance(resultat, svc_interpreteur.Aiguillage):
        return await _suivre_aiguillage(message, resultat, msg=msg)
    if isinstance(resultat, svc_interpreteur.Plan):
        await _plan_proposer(update, ctx, resultat, msg=msg)
        return True
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

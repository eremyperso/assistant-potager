"""Commandes /rappel et /rappels [US-268] — les rappels de suivi du compagnon.

Ce module ne décide rien : les dates, les durées et les écritures sont dans
`app/services/compagnon/rappels`. Il porte :

1. **Proposer** après un geste (CA1) : « Je te fais signe le 3 novembre ? »
   `[Oui, rappelle-moi] [Pas la peine]`. Le bouton « Oui » est la confirmation (R9) : rien n'est
   écrit avant. Les boutons ne portent que l'identifiant du geste (`rap:o:<id>`), la proposition
   est recalculée au clic — aucun état à garder.
2. **Programmer** avec `/rappel programmer <objet> <jour>` : c'est ce que la CONFIRMATION d'une
   phrase (« rappelle-moi de tailler les tomates samedi ») exécute (CA2, CA3).
3. **Lister et annuler** avec `/rappels` (CA5).

Aucun appel au modèle : tout est gabarit et boutons.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.services.compagnon import rappels as svc_rappels
from app.services.context import current_context
from database.db import SessionLocal

from .noyau import log

PREFIXE_CALLBACK = "rap"

TEXTE_AUCUN = "Tu n'as aucun rappel à venir. Dis-moi par exemple « rappelle-moi de tailler les tomates samedi »."
TEXTE_AIDE = "Les rappels : /rappels pour les voir, /rappel programmer <ce dont te souvenir> <quand> pour en ajouter un."
TEXTE_SANS_ENVOI = (
    "\n\n⚠️ Les messages spontanés sont coupés sur cette installation : ce rappel est noté, "
    "mais je ne pourrai te le dire que quand ils seront rétablis."
)
TEXTE_PAS_LA_PEINE = "D'accord, je ne te rappellerai rien."
TEXTE_PERIME = "Ce rappel n'a plus lieu d'être (date passée, ou rappels coupés dans tes réglages) : je ne le programme pas."
TEXTE_DEJA = "C'est déjà programmé."


def _message(update: Update):
    return update.message or (update.callback_query.message if update.callback_query else None)


def texte_proposition(proposition: svc_rappels.PropositionRappel) -> str:
    return f"⏰ Je te fais signe le {svc_rappels.libelle_jour(proposition.echeance)} pour {proposition.objet} ?"


def _clavier_proposition(evenement_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Oui, rappelle-moi", callback_data=f"{PREFIXE_CALLBACK}:o:{evenement_id}"),
        InlineKeyboardButton("Pas la peine", callback_data=f"{PREFIXE_CALLBACK}:n:{evenement_id}"),
    ]])


async def proposer_rappel(update: Update, saved_items: list) -> None:
    """[CA1, CA6] Après des gestes enregistrés, au plus UNE proposition : celle du premier geste qui s'y prête.

    Ne lève jamais : une proposition est un confort, jamais un échec de saisie.
    """
    message = _message(update)
    if message is None or not saved_items or not svc_rappels.actif():
        return
    try:
        contexte = current_context()
        db = SessionLocal()
        try:
            for _, evenement_id in saved_items:
                proposition = svc_rappels.proposer_pour_evenement(db, contexte, evenement_id)
                if proposition is not None:
                    break
        finally:
            db.close()
        if proposition is None:
            return
        await message.reply_text(texte_proposition(proposition), reply_markup=_clavier_proposition(evenement_id))
        log.info("[US-268] Rappel proposé pour l'événement %s (%s)", evenement_id, proposition.echeance.isoformat())
    except Exception:  # noqa: BLE001
        log.exception("[US-268] Proposition de rappel en échec")


def texte_liste(rappels) -> str:
    lignes = ["Voici tes rappels à venir :"]
    lignes.extend(f"• {svc_rappels.libelle_jour(r.echeance_le.date())} — {r.objet}" for r in rappels)
    return "\n".join(lignes)


def _clavier_liste(rappels) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(
        f"Annuler : {r.objet}"[:48], callback_data=f"{PREFIXE_CALLBACK}:a:{r.id}")] for r in rappels])


async def _lister(update: Update) -> None:
    db = SessionLocal()
    try:
        rappels = svc_rappels.lister(db, current_context())
        texte = texte_liste(rappels) if rappels else TEXTE_AUCUN
        clavier = _clavier_liste(rappels) if rappels else None
    finally:
        db.close()
    await _message(update).reply_text(texte, reply_markup=clavier)


async def cmd_rappel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/rappel — `programmer <objet> <jour>` écrit (après confirmation, R9) ; sans argument, la liste."""
    args = list(getattr(ctx, "args", None) or [])
    action = args[0].lower() if args else ""
    if action == "programmer":
        db = SessionLocal()
        try:
            objet, jour = svc_rappels.objet_et_jour(args[1:])
            rappel = svc_rappels.programmer(db, current_context(), objet, jour)
            texte = f"⏰ C'est noté : je te fais signe le {svc_rappels.libelle_jour(jour)} — {rappel.objet}."
            if not svc_rappels.actif():
                texte += TEXTE_SANS_ENVOI
        except svc_rappels.RappelError as e:
            texte = f"🙏 {e}"
        finally:
            db.close()
        await _message(update).reply_text(texte)
        return
    if action and action not in ("lister", "voir"):
        await _message(update).reply_text(TEXTE_AIDE)
        return
    await _lister(update)


async def cmd_rappels(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/rappels — les rappels à venir, avec un bouton d'annulation chacun (CA5)."""
    await _lister(update)


async def _rappel_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Boutons : `o` accepte la proposition d'un geste, `n` la refuse, `a` annule un rappel de la liste."""
    query = update.callback_query
    await query.answer()
    morceaux = (query.data or "").split(":")
    if len(morceaux) < 3 or not morceaux[2].isdigit():
        return
    action, cible = morceaux[1], int(morceaux[2])
    contexte = current_context()
    db = SessionLocal()
    try:
        if action == "n":
            await query.edit_message_text(TEXTE_PAS_LA_PEINE, reply_markup=None)
        elif action == "o":
            if svc_rappels.existe_pour(db, contexte, svc_rappels.CIBLE_EVENEMENT, cible):
                await query.edit_message_text(TEXTE_DEJA, reply_markup=None)
                return
            proposition = svc_rappels.proposer_pour_evenement(db, contexte, cible)
            if proposition is None:
                await query.edit_message_text(TEXTE_PERIME, reply_markup=None)
                return
            svc_rappels.programmer(
                db, contexte, proposition.objet, proposition.echeance,
                cible_type=proposition.cible_type, cible_id=proposition.cible_id,
            )
            await query.edit_message_text(
                f"⏰ C'est noté : je te fais signe le {svc_rappels.libelle_jour(proposition.echeance)}.",
                reply_markup=None,
            )
        elif action == "a":
            rappel = svc_rappels.annuler(db, contexte, cible)
            restants = svc_rappels.lister(db, contexte)
            texte = f"C'est annulé : {rappel.objet}."
            await query.edit_message_text(
                texte + ("\n\n" + texte_liste(restants) if restants else ""),
                reply_markup=_clavier_liste(restants) if restants else None,
            )
    except svc_rappels.RappelError as e:
        await query.edit_message_text(f"🙏 {e}", reply_markup=None)
    finally:
        db.close()

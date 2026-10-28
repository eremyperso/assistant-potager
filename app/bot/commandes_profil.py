"""Commande /profil [US-258] — comment le compagnon appelle le jardinier et sur quel ton.

Ce module ne décide rien : le prénom est validé et rangé par
`app/services/profil_echange`. Il porte trois gestes, tous du côté de Telegram :

1. **Accueillir** au premier échange avec le compagnon : proposer le prénom
   (jamais le supposer) et les trois registres, par boutons (CA1, CA3).
2. **Proposer** un changement de prénom dit en phrase (« appelle-moi Rico ») :
   une proposition à confirmer, pas une écriture d'office (CA6, R9).
3. **Montrer et régler** avec `/profil` (CA3).

Aucun appel au modèle : tout est gabarit et boutons.
"""
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.services import profil_echange as svc_profil
from app.services.context import current_context
from database.db import SessionLocal

from .noyau import log

#: Clé de `ctx.user_data` : le prénom en attente de confirmation.
_CLE_PRENOM_EN_ATTENTE = "profil_prenom_propose"

_APPELLE_MOI = re.compile(r"^\s*appell?e[zs]?[\s-]+moi\s+(?P<prenom>.+?)\s*[.!]*\s*$", re.IGNORECASE)

TEXTE_CHANGER_PRENOM = "Dis-moi : « appelle-moi <prénom> », et je te propose de le retenir."


def _boutons_registres() -> list[list[InlineKeyboardButton]]:
    return [[InlineKeyboardButton(svc_profil.LIBELLES_REGISTRE[r], callback_data=f"profil:r:{r}")
             for r in svc_profil.REGISTRES]]


def _clavier_profil() -> InlineKeyboardMarkup:
    lignes = _boutons_registres()
    lignes.append([InlineKeyboardButton("Changer de prénom", callback_data="profil:autre")])
    return InlineKeyboardMarkup(lignes)


def texte_profil(profil: "svc_profil.Profil | None") -> str:
    """Ce que le compagnon sait, dit au jardinier."""
    profil = profil or svc_profil.Profil()
    prenom = f"Je t'appelle {profil.prenom}." if profil.prenom else "Je ne connais pas encore ton prénom."
    return (f"{prenom}\nOn se parle sur le ton : {svc_profil.LIBELLES_REGISTRE[profil.registre].lower()}.\n"
            "Le ton change ma façon de dire les choses, jamais ce que je te dis.")


def _message(update: Update):
    return update.message or (update.callback_query.message if update.callback_query else None)


def _lire(ctx_tenant):
    db = SessionLocal()
    try:
        return svc_profil.lire(db, ctx_tenant)
    finally:
        db.close()


async def proposer_prenom(update: Update, ctx: ContextTypes.DEFAULT_TYPE, saisie: str) -> None:
    """[CA2, CA6] Valide la saisie, puis PROPOSE de la retenir (Confirmer / Annuler)."""
    prenom, erreur = svc_profil.valider_prenom(saisie)
    if erreur:
        await _message(update).reply_text(erreur)
        return
    ctx.user_data[_CLE_PRENOM_EN_ATTENTE] = prenom
    clavier = InlineKeyboardMarkup([[InlineKeyboardButton(f"Oui, {prenom}", callback_data="profil:ok"),
                                     InlineKeyboardButton("Non", callback_data="profil:non")]])
    await _message(update).reply_text(f"Je t'appellerai {prenom}. C'est bon ?", reply_markup=clavier)


async def phrase_de_profil(update: Update, ctx: ContextTypes.DEFAULT_TYPE, texte: str) -> bool:
    """[CA6] « appelle-moi Rico » → une proposition. True si la phrase était de ce genre."""
    trouve = _APPELLE_MOI.match(texte or "")
    if not trouve:
        return False
    log.info("[US-258] Phrase de profil : proposition de prénom")
    await proposer_prenom(update, ctx, trouve.group("prenom"))
    return True


async def accueil_premier_contact(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """[CA1, CA3] Au premier échange : demander comment appeler le jardinier, en proposant
    le prénom Telegram, puis les registres. Une seule fois par (jardinier, potager)."""
    contexte = current_context()
    db = SessionLocal()
    try:
        if not svc_profil.est_premier_contact(db, contexte):
            return
        svc_profil.marquer_accueilli(db, contexte)
    finally:
        db.close()
    lignes = []
    propose = svc_profil.prenom_propose(getattr(update.effective_user, "first_name", None))
    if propose:
        ctx.user_data[_CLE_PRENOM_EN_ATTENTE] = propose
        lignes.append([InlineKeyboardButton(propose, callback_data="profil:ok"),
                       InlineKeyboardButton("Autre prénom", callback_data="profil:autre")])
        question = f"Au fait, comment dois-je t'appeler ? {propose} ?"
    else:
        lignes.append([InlineKeyboardButton("Dire mon prénom", callback_data="profil:autre")])
        question = "Au fait, comment dois-je t'appeler ?"
    lignes.extend(_boutons_registres())
    log.info("[US-258] Premier contact : prénom et registre demandés")
    await _message(update).reply_text(
        question + "\nEt sur quel ton : sobre, comme un voisin, ou gouailleur ? "
        "Tu pourras changer avec /profil.",
        reply_markup=InlineKeyboardMarkup(lignes))


async def cmd_profil(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/profil — voir et régler le prénom et le registre ; `/profil prenom Rico` propose un prénom."""
    args = list(getattr(ctx, "args", None) or [])
    if args and args[0].lower() in ("prenom", "prénom") and len(args) > 1:
        await proposer_prenom(update, ctx, " ".join(args[1:]))
        return
    await _message(update).reply_text(texte_profil(_lire(current_context())), reply_markup=_clavier_profil())


async def _profil_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Boutons du profil : registre choisi, prénom confirmé ou refusé, prénom à dire."""
    query = update.callback_query
    await query.answer()
    action = query.data.split(":", 1)[1]
    contexte = current_context()
    if action == "autre":
        await query.message.reply_text(TEXTE_CHANGER_PRENOM)
        return
    if action == "non":
        ctx.user_data.pop(_CLE_PRENOM_EN_ATTENTE, None)
        await query.edit_message_text("D'accord, je ne change rien.")
        return
    db = SessionLocal()
    try:
        if action == "ok":
            prenom = ctx.user_data.pop(_CLE_PRENOM_EN_ATTENTE, None)
            profil, erreur = svc_profil.definir_prenom(db, contexte, prenom or "")
            texte = erreur or f"C'est noté, {profil.prenom}."
        elif action.startswith("r:"):
            profil = svc_profil.definir_registre(db, contexte, action[2:])
            texte = (f"Ton choisi : {svc_profil.LIBELLES_REGISTRE[profil.registre].lower()}."
                     if profil else "Je ne connais pas ce ton.")
        else:
            return
    finally:
        db.close()
    await query.message.reply_text(texte)

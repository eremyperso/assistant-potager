"""Commande /profil [US-258] — comment le compagnon appelle le jardinier et sur quel ton.

Ce module ne décide rien : le prénom est validé et rangé par
`app/services/profil_echange`. Il porte trois gestes, tous du côté de Telegram :

1. **Accueillir** au premier échange avec le compagnon : proposer le prénom
   (jamais le supposer) et les trois registres, par boutons (CA1, CA3).
2. **Proposer** un changement de prénom dit en phrase (« appelle-moi Rico ») :
   une proposition à confirmer, pas une écriture d'office (CA6, R9).
3. **Montrer et régler** avec `/profil` (CA3).

[US-267 / CA9] Le profil, partie 3 : les messages spontanés. `/profil` → « 🔔 Messages
spontanés » montre le mode de chaque thème (un bouton le fait tourner : tout de suite →
point du matin → jamais), la plage de silence et l'heure du point du matin. Une phrase
(« arrête de me parler de la météo », « silence de 22 h à 7 h ») est PROPOSÉE, puis
confirmée, comme « appelle-moi X ».

Aucun appel au modèle : tout est gabarit et boutons.
"""
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.services import profil_echange as svc_profil
from app.services.compagnon import distributeur as svc_distributeur
from app.services.compagnon import proactivite as svc_proactivite
from app.services.compagnon import veilleur_passage as svc_veilleur_passage
from app.services.context import current_context
from database.db import SessionLocal

from .noyau import log

#: Clé de `ctx.user_data` : le prénom en attente de confirmation.
_CLE_PRENOM_EN_ATTENTE = "profil_prenom_propose"
#: [US-267 / CA9] Le réglage des messages spontanés proposé par une phrase, en attente.
_CLE_REGLAGE_EN_ATTENTE = "profil_proactivite_propose"

TEXTE_CHANGER_SILENCE = ("Dis-moi par exemple : « silence de 22 h à 7 h », ou « pas de silence », "
                         "et je te propose de le retenir.")
TEXTE_CHANGER_MATIN = "Dis-moi par exemple : « point du matin à 7 h », et je te propose de le retenir."

_APPELLE_MOI = re.compile(r"^\s*appell?e[zs]?[\s-]+moi\s+(?P<prenom>.+?)\s*[.!]*\s*$", re.IGNORECASE)

TEXTE_CHANGER_PRENOM = "Dis-moi : « appelle-moi <prénom> », et je te propose de le retenir."


def _boutons_registres() -> list[list[InlineKeyboardButton]]:
    return [[InlineKeyboardButton(svc_profil.LIBELLES_REGISTRE[r], callback_data=f"profil:r:{r}")
             for r in svc_profil.REGISTRES]]


def _clavier_profil() -> InlineKeyboardMarkup:
    lignes = _boutons_registres()
    lignes.append([InlineKeyboardButton("Changer de prénom", callback_data="profil:autre")])
    lignes.append([InlineKeyboardButton("🔔 Messages spontanés", callback_data="profil:proactif")])
    return InlineKeyboardMarkup(lignes)


def texte_profil(profil: "svc_profil.Profil | None") -> str:
    """Ce que le compagnon sait, dit au jardinier."""
    profil = profil or svc_profil.Profil()
    prenom = f"Je t'appelle {profil.prenom}." if profil.prenom else "Je ne connais pas encore ton prénom."
    return (f"{prenom}\nOn se parle sur le ton : {svc_profil.LIBELLES_REGISTRE[profil.registre].lower()}.\n"
            "Le ton change ma façon de dire les choses, jamais ce que je te dis.\n"
            "Ce que je t'écris de moi-même (gel, levées, échéances…) se règle sous « Messages spontanés ».")


# ── [US-267 / CA9] Les messages spontanés ────────────────────────────────────
def _clavier_proactivite(reglages) -> InlineKeyboardMarkup:
    """Un bouton par thème, qui fait tourner son mode ; puis le silence et le point du matin."""
    lignes = [
        [InlineKeyboardButton(
            f"{svc_distributeur.LIBELLES_THEME[theme].capitalize()[:32]} : "
            f"{svc_distributeur.LIBELLES_MODE[reglages.mode(theme)]}",
            callback_data=f"profil:pt:{theme}")]
        for theme in svc_distributeur.THEMES_REGLABLES
    ]
    lignes.append([InlineKeyboardButton("🌙 Plage de silence", callback_data="profil:silence"),
                   InlineKeyboardButton("☀️ Point du matin", callback_data="profil:matin")])
    return InlineKeyboardMarkup(lignes)


def _reglages(contexte):
    db = SessionLocal()
    try:
        return svc_proactivite.lire(db, contexte)
    finally:
        db.close()


async def afficher_proactivite(update: Update, contexte=None) -> None:
    """[CA9] Les réglages des messages spontanés, avec leurs boutons."""
    reglages = _reglages(contexte or current_context())
    await _message(update).reply_text(svc_proactivite.texte_reglages(reglages),
                                      reply_markup=_clavier_proactivite(reglages))


async def proposer_reglage(update: Update, ctx: ContextTypes.DEFAULT_TYPE, changement) -> None:
    """[CA9, R9] Une phrase de réglage devient une proposition : rien n'est écrit sans « Oui »."""
    ctx.user_data[_CLE_REGLAGE_EN_ATTENTE] = changement.en_donnees()
    clavier = InlineKeyboardMarkup([[InlineKeyboardButton("Oui", callback_data="profil:pok"),
                                     InlineKeyboardButton("Non", callback_data="profil:non")]])
    await _message(update).reply_text(svc_proactivite.texte_changement(changement), reply_markup=clavier)


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
    """[CA6] « appelle-moi Rico » → une proposition. True si la phrase était de ce genre.

    [US-267 / CA9] « arrête de me parler de la météo », « silence de 22 h à 7 h » aussi."""
    trouve = _APPELLE_MOI.match(texte or "")
    if trouve:
        log.info("[US-258] Phrase de profil : proposition de prénom")
        await proposer_prenom(update, ctx, trouve.group("prenom"))
        return True
    changement = svc_proactivite.lire_phrase(texte)
    if changement is None:
        return False
    log.info("[US-267 / CA9] Phrase de réglage des messages spontanés : %s", changement.en_donnees())
    await proposer_reglage(update, ctx, changement)
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
        ctx.user_data.pop(_CLE_REGLAGE_EN_ATTENTE, None)
        await query.edit_message_text("D'accord, je ne change rien.")
        return
    # [US-267 / CA9] Les messages spontanés.
    if action == "proactif":
        await afficher_proactivite(update, contexte)
        return
    if action == "silence":
        await query.message.reply_text(TEXTE_CHANGER_SILENCE)
        return
    if action == "matin":
        await query.message.reply_text(TEXTE_CHANGER_MATIN)
        return
    if action == "pok" or action.startswith("pt:"):
        await _regler_proactivite(query, ctx, contexte, action)
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


async def _regler_proactivite(query, ctx: ContextTypes.DEFAULT_TYPE, contexte, action: str) -> None:
    """[CA9] Le bouton d'un thème (le clic vaut confirmation) ou le « Oui » d'une phrase proposée."""
    if action == "pok":
        donnees = ctx.user_data.pop(_CLE_REGLAGE_EN_ATTENTE, None)
        if not donnees:
            await query.edit_message_text("⏱ Cette proposition n'est plus d'actualité. Redis-moi ce que tu veux régler.")
            return
        changement = svc_proactivite.Changement.depuis_donnees(donnees)
    else:
        theme = action.split(":", 1)[1]
        if theme not in svc_distributeur.MODES_PAR_DEFAUT:
            return
        changement = svc_proactivite.Changement(
            svc_proactivite.REGLAGE_MODE, theme=theme,
            mode=svc_proactivite.mode_suivant(_reglages(contexte).mode(theme)))
    db = SessionLocal()
    try:
        reglages = svc_proactivite.appliquer(db, contexte, changement, svc_veilleur_passage.maintenant_local())
    finally:
        db.close()
    if reglages is None:
        await query.message.reply_text("Je n'ai pas pu retenir ce réglage.")
        return
    if action == "pok":
        await query.edit_message_text("C'est noté.")
        await query.message.reply_text(svc_proactivite.texte_reglages(reglages),
                                       reply_markup=_clavier_proactivite(reglages))
    else:
        await query.edit_message_text(svc_proactivite.texte_reglages(reglages),
                                      reply_markup=_clavier_proactivite(reglages))

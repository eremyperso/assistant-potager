"""Commande /carnet [US-265] — ce que le compagnon retient de ce que le jardinier lui dit.

Ce module ne décide rien : les faits sont validés et rangés par
`app/services/carnet_compagnon`. Il porte :

1. **Montrer** le carnet avec `/carnet` : faits, niveau, objectifs, et les boutons
   [Modifier] [Oublier un point] [Tout oublier] (CA3).
2. **Écrire** avec `/carnet retenir <fait>` : c'est ce que la CONFIRMATION d'une
   proposition de l'agent exécute (R9). Le modèle ne l'appelle jamais lui-même.
3. **Proposer le niveau** déduit de l'activité (CA5) et **régler les objectifs de
   saison** avec `/carnet objectif <texte>`.

Aucun appel au modèle : tout est gabarit et boutons.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.services import carnet_compagnon as svc_carnet
from app.services.compagnon import conversations as svc_conversations
from app.services.context import current_context
from database.db import SessionLocal

from .noyau import log

#: Clé de `ctx.user_data` : le fait dont le jardinier va dire le nouveau texte.
_CLE_FAIT_A_MODIFIER = "carnet_fait_a_modifier"

TEXTE_VIDE = (
    "Mon carnet est vide pour l'instant. Dis-moi une habitude, par exemple « j'arrose le soir », "
    "et je te propose de la retenir."
)
TEXTE_DEMANDE_MODIFICATION = "Dis-moi la nouvelle version de ce point, en une phrase."
TEXTE_AIDE = (
    "Le carnet : /carnet pour le voir, /carnet retenir <fait> pour y noter une chose, "
    "/carnet objectif <texte> pour un objectif de saison."
)


def texte_carnet(carnet: svc_carnet.Carnet) -> str:
    """Ce que le compagnon sait, dit au jardinier."""
    if carnet.vide:
        return TEXTE_VIDE
    lignes = ["Voici ce que je sais de toi et de ton potager :"]
    if carnet.niveau:
        lignes.append(f"• niveau : {svc_carnet.LIBELLES_NIVEAU[carnet.niveau].lower()} ;")
    lignes.extend(f"• objectif : {objectif} ;" for objectif in carnet.objectifs)
    lignes.extend(f"• {fait.texte} ;" for fait in carnet.faits)
    return "\n".join(lignes)


def _clavier(carnet: svc_carnet.Carnet, niveau_propose: "str | None") -> "InlineKeyboardMarkup | None":
    lignes = []
    if niveau_propose:
        lignes.append([InlineKeyboardButton(
            f"Je me dirais {svc_carnet.LIBELLES_NIVEAU[niveau_propose].lower()}", callback_data=f"carnet:niv:{niveau_propose}"),
            InlineKeyboardButton("Pas maintenant", callback_data="carnet:niv:non")])
    if carnet.faits:
        lignes.append([InlineKeyboardButton("Modifier", callback_data="carnet:mod"),
                       InlineKeyboardButton("Oublier un point", callback_data="carnet:oub")])
    if not carnet.vide:
        lignes.append([InlineKeyboardButton("Tout oublier", callback_data="carnet:tout")])
    return InlineKeyboardMarkup(lignes) if lignes else None


def _message(update: Update):
    return update.message or (update.callback_query.message if update.callback_query else None)


def _lire():
    """(carnet, niveau à proposer) du jardinier courant."""
    contexte = current_context()
    db = SessionLocal()
    try:
        return svc_carnet.lire(db, contexte), svc_carnet.niveau_a_proposer(db, contexte)
    finally:
        db.close()


async def _montrer(update: Update) -> None:
    carnet, propose = _lire()
    texte = texte_carnet(carnet)
    if propose:
        texte += ("\n\nD'après ce que tu notes ici, je te vois plutôt "
                  f"{svc_carnet.LIBELLES_NIVEAU[propose].lower()}. C'est juste ?")
    await _message(update).reply_text(texte, reply_markup=_clavier(carnet, propose))


def _origine() -> "str | None":
    """La phrase du jardinier qui a fait naître le fait : le dernier échange de la conversation."""
    try:
        echanges = svc_conversations.recents(current_context())
        return echanges[-1].texte if echanges else None
    except Exception:  # noqa: BLE001 — l'origine est un plus, jamais une condition
        return None


async def cmd_carnet(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/carnet — voir le carnet ; `retenir <fait>` écrit (après confirmation) ; `objectif <texte>` règle un objectif."""
    args = list(getattr(ctx, "args", None) or [])
    action = args[0].lower() if args else ""
    reste = " ".join(args[1:]).strip()
    contexte = current_context()
    if action == "retenir":
        genre = args[1].lower() if len(args) > 2 and args[1].lower() in ("habitude", "objectif") else ""
        if genre:
            reste = " ".join(args[2:]).strip()
        db = SessionLocal()
        try:
            if genre == "objectif":
                actuels = list(svc_carnet.lire(db, contexte).objectifs)
                svc_carnet.definir_objectifs(db, contexte, [*actuels, reste])
                texte = f"🎯 Objectif de saison noté : {reste}"
            else:
                fait = svc_carnet.retenir(db, contexte, reste, origine=_origine())
                texte = f"📓 C'est noté dans mon carnet : {fait.texte}"
        except svc_carnet.CarnetError as e:
            texte = f"🙏 {e}"
        finally:
            db.close()
        await _message(update).reply_text(texte)
        return
    if action in ("objectif", "objectifs"):
        db = SessionLocal()
        try:
            actuels = list(svc_carnet.lire(db, contexte).objectifs)
            svc_carnet.definir_objectifs(db, contexte, [*actuels, reste] if reste else actuels)
            texte = "🎯 Objectif noté." if reste else "Dis-moi l'objectif : /carnet objectif <texte>."
        except svc_carnet.CarnetError as e:
            texte = f"🙏 {e}"
        finally:
            db.close()
        await _message(update).reply_text(texte)
        return
    if action and action not in ("lister", "voir"):
        await _message(update).reply_text(TEXTE_AIDE)
        return
    await _montrer(update)


async def phrase_de_carnet(update: Update, ctx: ContextTypes.DEFAULT_TYPE, texte: str) -> bool:
    """Le jardinier dit la nouvelle version d'un point qu'il a choisi de modifier → True si la phrase l'était."""
    fait_id = ctx.user_data.pop(_CLE_FAIT_A_MODIFIER, None) if isinstance(getattr(ctx, "user_data", None), dict) else None
    if fait_id is None:
        return False
    db = SessionLocal()
    try:
        fait = svc_carnet.modifier(db, current_context(), fait_id, texte)
        reponse = f"📓 C'est corrigé : {fait.texte}"
    except svc_carnet.CarnetError as e:
        reponse = f"🙏 {e}"
    finally:
        db.close()
    log.info("[US-265] Fait modifié par phrase")
    await _message(update).reply_text(reponse)
    return True


def _choix(faits, prefixe: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(f.texte[:48], callback_data=f"carnet:{prefixe}:{f.id}")]
                                 for f in faits])


async def _carnet_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Boutons du carnet : modifier, oublier un point, tout oublier, niveau proposé."""
    query = update.callback_query
    await query.answer()
    morceaux = query.data.split(":")
    action = morceaux[1] if len(morceaux) > 1 else ""
    contexte = current_context()
    db = SessionLocal()
    try:
        if action in ("mod", "oub"):
            faits = svc_carnet.lister(db, contexte)
            if not faits:
                await query.message.reply_text(TEXTE_VIDE)
                return
            question = "Lequel veux-tu modifier ?" if action == "mod" else "Lequel dois-je oublier ?"
            await query.message.reply_text(question, reply_markup=_choix(faits, "m" if action == "mod" else "o"))
            return
        if action == "m" and len(morceaux) > 2:
            ctx.user_data[_CLE_FAIT_A_MODIFIER] = int(morceaux[2])
            await query.message.reply_text(TEXTE_DEMANDE_MODIFICATION)
            return
        if action == "o" and len(morceaux) > 2:
            try:
                svc_carnet.oublier(db, contexte, int(morceaux[2]))
                texte = "C'est oublié."
            except svc_carnet.CarnetError as e:
                texte = f"🙏 {e}"
            await query.message.reply_text(texte)
            return
        if action == "tout":
            if len(morceaux) > 2 and morceaux[2] == "ok":
                nombre = svc_carnet.tout_oublier(db, contexte)
                await query.edit_message_text(f"Carnet vidé : j'ai tout oublié ({nombre} point(s)).")
            elif len(morceaux) > 2:
                await query.edit_message_text("D'accord, je garde tout.")
            else:
                await query.message.reply_text(
                    "Tout oublier ? Faits, objectifs et niveau seront effacés.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("Oui, tout oublier", callback_data="carnet:tout:ok"),
                        InlineKeyboardButton("Non", callback_data="carnet:tout:non")]]))
            return
        if action == "niv" and len(morceaux) > 2:
            if morceaux[2] in svc_carnet.NIVEAUX:
                svc_carnet.definir_niveau(db, contexte, morceaux[2])
                await query.message.reply_text(
                    f"C'est noté : {svc_carnet.LIBELLES_NIVEAU[morceaux[2]].lower()}.")
            else:
                await query.message.reply_text("D'accord, je ne change rien.")
    except svc_carnet.CarnetError as e:
        await query.message.reply_text(f"🙏 {e}")
    finally:
        db.close()

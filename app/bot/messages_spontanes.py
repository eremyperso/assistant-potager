"""Les messages spontanés du compagnon dans Telegram [US-267].

Le distributeur (`app/services/compagnon/distribution.py`) fait partir ce que le veilleur a
détecté. Ce module ne fait que le planifier, et recevoir ce qui en revient :

* `job_distributeur` — le passage, toutes les quinze minutes, hors de la boucle du bot ;
  seul le planificateur du bot distribue (CA11) ;
* `_spontane_cb` — un bouton d'un message spontané : la phrase de geste qu'il porte part au
  flux des gestes, qui montre un récapitulatif à confirmer. Rien n'est écrit au clic (R8) ;
* `reprendre_reponse` — la réponse écrite ou dictée à un message spontané : la réaction
  est notée (CA5), et la phrase est lue avec le signal d'origine (CA8).
"""
import asyncio

from telegram import Update
from telegram.ext import ContextTypes

from app.services.compagnon import distribution as svc_distribution
from app.services.compagnon import propositions as svc_propositions
from app.services.compagnon import reponse_signal as svc_reponse
from app.services.context import current_context

from .noyau import log

MSG_PERIME = "⏱ Ce message n'est plus d'actualité."
MSG_RIEN = "👌 D'accord, je n'enregistre rien."


async def job_distributeur(context: ContextTypes.DEFAULT_TYPE) -> None:
    """[CA11] Le passage du distributeur : silence, point du matin, demi-heure de regroupement.
    Il lit la base, appelle le modèle et Telegram de façon bloquante : hors de la boucle."""
    try:
        await asyncio.to_thread(svc_distribution.passer)
    except Exception as e:  # noqa: BLE001 — un job de fond ne tue jamais le bot
        log.error("❌ JOB DISTRIBUTEUR : %s", e)


async def _spontane_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """[CA7] Un bouton d'un message spontané ouvre une PROPOSITION, jamais une écriture."""
    query = update.callback_query
    await query.answer()
    lu = svc_reponse.lire_callback(query.data or "")
    contexte = current_context()
    if lu is None or contexte.user_id is None:
        return
    potager_id, envoi_id, code = lu
    if potager_id != contexte.potager_id:
        # F5 : le geste s'enregistrerait dans le potager actif, pas dans celui du message.
        nom = svc_propositions.potager_a_nommer(contexte.user_id, potager_id) or "un autre potager"
        await query.message.reply_text(
            f"Ce message concerne {nom}. Passe sur ce potager avec /potager, puis appuie de nouveau.")
        return
    if code == svc_reponse.CODE_REGLAGES:
        from .commandes_profil import afficher_proactivite

        await afficher_proactivite(update, contexte)
        return
    signal = svc_distribution.signal_du_bouton(potager_id, contexte.user_id, envoi_id)
    if signal is None:
        await query.message.reply_text(MSG_PERIME)
        return
    phrase = svc_reponse.phrase_du_geste(signal, code)
    if phrase is None:
        await query.message.reply_text(MSG_RIEN)
        return
    log.info("[US-267 / CA7] Bouton « %s » du message spontané → %r (récapitulatif à confirmer)", code, phrase)
    from .saisie import _parse_and_save

    await _parse_and_save(update, phrase)


def reprendre_reponse(update: Update, texte: str) -> str:
    """[CA5, CA8] La phrase du jardinier, lue avec le message spontané auquel elle répond.

    Sans message spontané en cours, elle est rendue telle quelle. Sinon la réaction est
    notée, et une réponse courte que le code sait lire (« oui environ 20 sur 24 ») devient
    la phrase de geste complète (« levée du lot 14 : 20 »), qui suit le chemin ordinaire
    jusqu'au récapitulatif à confirmer. Le reste passe tel quel, et l'agent trouve le
    message spontané dans son contexte (`contexte_court_de`).
    """
    contexte = current_context()
    cite = getattr(getattr(getattr(update, "message", None), "reply_to_message", None), "message_id", None)
    en_cours = svc_distribution.message_en_contexte(
        contexte.potager_id, contexte.user_id, telegram_message_id=cite if isinstance(cite, int) else None)
    if en_cours is None:
        return texte
    svc_distribution.noter_reaction(contexte.potager_id, contexte.user_id, en_cours.message_id)
    phrase = svc_reponse.reformuler(en_cours.signaux, texte)
    if phrase is None:
        return texte
    log.info("[US-267 / CA8] Réponse au message spontané %s : %r → %r", en_cours.message_id, texte, phrase)
    return phrase

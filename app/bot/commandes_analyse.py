"""Commande /approfondir [US-273] — l'analyse approfondie du potager, en lecture seule.

Ce module ne décide rien : la boucle de lecture est `app/services/agent/analyse.py`, appelée par
l'orchestrateur commun (le bouton « Approfondir » de la PWA passe par le même chemin). Il porte :

1. **Demander** la question quand elle manque (aide d'usage, aucun appel au modèle) ;
2. **Lancer** l'analyse hors de la boucle d'événements (plusieurs appels au modèle de suite) ;
3. **Dire** le résultat, découpé sous la limite de Telegram.

Aucune écriture : ni proposition, ni bouton de confirmation. Les pistes d'action de l'analyse sont du
texte ; agir passe par le dialogue ordinaire (R2).
"""
import asyncio

from telegram import Update
from telegram.ext import ContextTypes

from app.services.compagnon import orchestrateur as svc_orchestrateur
from app.services.context import current_context
from llm.passerelle import LLMIndisponibleError, MESSAGE_REPLI_IA

from .noyau import _decouper_en_blocs, log

TEXTE_USAGE = (
    "🔬 *Analyse approfondie :*\n\n"
    "Dis-moi ce que tu veux comprendre, je croise tes récoltes, la météo et tes parcelles. "
    "Je ne modifie rien.\n\n"
    "Ex : `/approfondir pourquoi mes tomates ont peu donné ?`"
)
TEXTE_EN_COURS = "🔬 Je regarde ton potager en détail, ça prend un moment…"


async def cmd_approfondir(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/approfondir <question> — une synthèse qui croise plusieurs lectures, sans rien écrire."""
    question = " ".join(ctx.args).strip() if ctx.args else ""
    if not question:
        await update.message.reply_text(TEXTE_USAGE, parse_mode="Markdown")
        return
    log.info("🔬 APPROFONDIR    : %s", question[:120])
    attente = await update.message.reply_text(TEXTE_EN_COURS)
    contexte = current_context()
    try:
        resultat = await asyncio.to_thread(svc_orchestrateur.analyser_le_potager, contexte, question)
    except LLMIndisponibleError:
        await attente.edit_text(f"⏳ {MESSAGE_REPLI_IA}.")
        return
    blocs = _decouper_en_blocs(f"🔬 {resultat.texte}")
    # Texte brut : la synthèse est écrite par un modèle, un `_` ou un `*` isolé ferait échouer le Markdown.
    await attente.edit_text(blocs[0])
    for bloc in blocs[1:]:
        await update.message.reply_text(bloc)

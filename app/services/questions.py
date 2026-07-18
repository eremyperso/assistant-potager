"""
app/services/questions.py — Mode /ask [US-041 / CA7, US-042 / CA3, CA7]
-----------------------------------------------------------------------
Point d'entrée unique pour répondre à une question analytique, via le SQL
agent [US-012] : extract_intent_query_mesuree() (~100 tokens Groq) puis
query_agent_answer() (zéro Groq pour la réponse elle-même — l'agent SQL
répond en Python pur, scopé par potager_id + fenêtre 12 mois / 100 événements
max, voir llm/sql_agent.py). Auparavant dupliqué : bot.py utilisait déjà
cette approche (_ask_question), tandis que main.py (/ask, /voice-INTERROGER)
chargeait tout l'historique en JSON et l'envoyait au LLM (~5000 tokens/appel).
Cette US unifie les deux sur l'approche SQL agent, la moins coûteuse et la
seule scopable proprement par potager.

[US-042 / CA7] Le nombre de tokens Groq réellement consommés par l'appel est
loggué à chaque appel — cible : < 1500 tokens/appel (contre ~5000 avant).
"""
import logging

from app.services.context import TenantContext
from llm.groq_client import extract_intent_query_mesuree
from llm.sql_agent import query_agent_answer

log = logging.getLogger("potager")


def repondre_question(ctx: TenantContext, question: str) -> str:
    """Répond à une question analytique en langage naturel sur l'historique du potager,
    scopée au potager courant (ctx.potager_id). Gère elle-même sa session DB (via
    query_agent_answer) — pas de `db` en paramètre, conformément à la signature
    définie par l'US (US-041 / CA7)."""
    intent, tokens = extract_intent_query_mesuree(question)
    reponse = query_agent_answer(question, intent, potager_id=ctx.potager_id)
    log.info(
        "[US-042 CA7] repondre_question potager_id=%s tokens_groq=%d (cible <1500)",
        ctx.potager_id, tokens,
    )
    return reponse

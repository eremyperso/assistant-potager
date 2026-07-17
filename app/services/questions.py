"""
app/services/questions.py — Mode /ask [US-041 / CA7]
-----------------------------------------------------------------------
Point d'entrée unique pour répondre à une question analytique, via le SQL
agent [US-012] : extract_intent_query() (~100 tokens Groq) puis
query_agent_answer() (zéro Groq pour la réponse elle-même — l'agent SQL
répond en Python pur). Auparavant dupliqué : bot.py utilisait déjà cette
approche (_ask_question), tandis que main.py (/ask, /voice-INTERROGER)
chargeait tout l'historique en JSON et l'envoyait au LLM (~5000 tokens/appel).
Cette US unifie les deux sur l'approche SQL agent, la moins coûteuse et la
seule déjà scopable proprement par potager (US-042).
"""
from app.services.context import TenantContext
from llm.groq_client import extract_intent_query
from llm.sql_agent import query_agent_answer


def repondre_question(ctx: TenantContext, question: str) -> str:
    """Répond à une question analytique en langage naturel sur l'historique du potager.
    Gère elle-même sa session DB (via query_agent_answer) — pas de `db` en paramètre,
    conformément à la signature définie par l'US (US-041 / CA7)."""
    intent = extract_intent_query(question)
    return query_agent_answer(question, intent)

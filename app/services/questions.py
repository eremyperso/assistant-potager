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

[US-096] Ordre de l'étage 1, désormais en deux temps : le catalogue de réponses
chiffrées (`app/services/reponses_chiffrees.py`) est consulté EN PREMIER et
répond par gabarit à coût nul ; l'agent SQL historique, qui coûte encore une
extraction d'intention (~100 jetons), ne sert plus que les formulations qu'aucune
famille du catalogue ne reconnaît. Le routeur (US-093) n'a pas à le savoir : il
appelle toujours `repondre_question_avec_confiance()`, dont le contrat est
inchangé — c'est ce qui permet d'étendre le catalogue sans y toucher.
"""
import logging

from app.services import reponses_chiffrees
from app.services.context import TenantContext
from llm.groq_client import extract_intent_query_mesuree
from llm.sql_agent import query_agent_answer, query_agent_answer_avec_confiance

log = logging.getLogger("potager")


def repondre_question(ctx: TenantContext, question: str) -> str:
    """Répond à une question analytique en langage naturel sur l'historique du potager,
    scopée au potager courant (ctx.potager_id). Gère elle-même sa session DB (via
    query_agent_answer) — pas de `db` en paramètre, conformément à la signature
    définie par l'US (US-041 / CA7)."""
    texte, _ = repondre_question_avec_confiance(ctx, question)
    return texte


def repondre_question_avec_confiance(ctx: TenantContext, question: str) -> tuple[str, bool]:
    """[US-093 / CA6] Variante de `repondre_question()` qui signale en plus si
    l'étage data a produit une réponse exploitable. Utilisée par le routeur pour
    décider d'une remontée de cascade vers l'étage suivant sans avoir à
    réinterpréter le texte produit."""
    # [US-096 / CA1] Étage 1, premier passage : les familles de questions
    # chiffrées du catalogue (`app/services/reponses_chiffrees.py`) sont servies
    # par un gabarit, AVANT toute extraction d'intention — donc avant le seul
    # appel modèle qui subsistait sur ce chemin. Une famille reconnue mais sans
    # donnée (`present=False`) rend la main à la cascade (CA8) sans avoir rien
    # dépensé pour le constater, tout en portant une phrase honnête (CA7) qui
    # sert de réponse si aucun étage supérieur ne fait mieux.
    chiffree = reponses_chiffrees.repondre_chiffre(ctx, question)
    if chiffree is not None:
        log.info(
            "[US-096 CA1] repondre_question potager_id=%s famille=%s tokens_groq=0 donnee=%s",
            ctx.potager_id, chiffree.famille, "oui" if chiffree.present else "aucune",
        )
        return chiffree.texte, chiffree.present

    # [US-092 / CA2] Le contexte tenant est transmis explicitement à la
    # passerelle : c'est lui qui rend l'appel imputable au bon potager.
    intent, tokens = extract_intent_query_mesuree(question, ctx=ctx)
    reponse, confiant = query_agent_answer_avec_confiance(question, intent, potager_id=ctx.potager_id)
    log.info(
        "[US-042 CA7] repondre_question potager_id=%s tokens_groq=%d (cible <1500)",
        ctx.potager_id, tokens,
    )
    return reponse, confiant

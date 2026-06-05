"""
[US-012] sql_agent.py — Agent SQL pour répondre aux questions sans hallucinations Groq.

Stratégie :
  1. Recevoir l'intent extrait (action, culture, date_from)
  2. Construire et exécuter une requête SQLAlchemy (zéro Groq)
  3. Formater la réponse en texte simple
"""

from sqlalchemy import func
from database.db import SessionLocal
from database.models import Evenement


class QueryAgent:
    """Agent SQL pour questions analytiques — zéro appel LLM."""

    def __init__(self, db):
        self.db = db

    def answer(self, question: str, intent: dict) -> str:
        """
        Répond à une question sans appel Groq.

        Args:
            question: Question utilisateur (pour le fallback message)
            intent: {"action": ..., "culture": ..., "date_from": ...}
        Returns:
            Réponse texte prête à afficher
        """
        action = intent.get("action")
        culture = intent.get("culture")

        if culture and action:
            return self._answer_quantity(action, culture)

        if culture and not action:
            return self._answer_history_culture(culture)

        if action and not culture:
            return self._answer_action_stats(action)

        return "Je n'ai pas compris la question. Formulez autrement."

    def _answer_quantity(self, action: str, culture: str) -> str:
        """Répond à : "Combien de [culture] [action] ?"."""
        rows = self.db.query(
            Evenement.unite,
            func.sum(Evenement.quantite).label("total"),
        ).filter(
            Evenement.type_action == action,
            Evenement.culture == culture,
        ).group_by(Evenement.unite).all()

        if not rows or all(r.total is None for r in rows):
            return f"Aucune donnée enregistrée pour {culture} / {action}."

        parts = []
        for unite, total in rows:
            if total is not None:
                unite_str = f" {unite}" if unite else ""
                parts.append(f"{total:g}{unite_str}")
        total_str = " + ".join(parts)
        return f"Total {culture} {action} : {total_str}"

    def _answer_history_culture(self, culture: str) -> str:
        """Répond à : "Historique de [culture]"."""
        events = (
            self.db.query(Evenement)
            .filter(Evenement.culture == culture)
            .order_by(Evenement.date.desc())
            .limit(5)
            .all()
        )
        if not events:
            return f"Aucun événement enregistré pour {culture}."

        lines = [f"Historique {culture} (5 derniers) :"]
        for e in events:
            date_str = e.date.strftime("%d/%m/%Y") if e.date else "?"
            lines.append(f"  • {e.type_action} ({date_str})")
        return "\n".join(lines)

    def _answer_action_stats(self, action: str) -> str:
        """Répond à : "Stats [action]"."""
        rows = (
            self.db.query(
                Evenement.culture,
                Evenement.unite,
                func.count(Evenement.id).label("nb"),
                func.sum(Evenement.quantite).label("total"),
            )
            .filter(Evenement.type_action == action)
            .group_by(Evenement.culture, Evenement.unite)
            .order_by(func.sum(Evenement.quantite).desc())
            .limit(10)
            .all()
        )
        if not rows:
            return f"Aucun événement de type {action} enregistré."

        # Regroupe les lignes par culture (une culture peut avoir plusieurs unités)
        from collections import defaultdict
        par_culture: dict[str, list[str]] = defaultdict(list)
        for culture, unite, nb, total in rows:
            if total:
                unite_str = f" {unite}" if unite else ""
                par_culture[culture or "?"].append(f"{total:g}{unite_str}")
            else:
                par_culture[culture or "?"].append(f"{nb} fois")

        lines = [f"Top cultures — {action} :"]
        for culture, parts in par_culture.items():
            lines.append(f"  • {culture} : {' + '.join(parts)}")
        return "\n".join(lines)


def query_agent_answer(question: str, intent: dict) -> str:
    """
    [US-012] Point d'entrée public — répond via SQL agent, zéro Groq.

    Args:
        question: Question utilisateur
        intent: Dict {action, culture, date_from} issu de extract_intent_query()
    Returns:
        Réponse texte
    """
    db = SessionLocal()
    try:
        return QueryAgent(db).answer(question, intent)
    finally:
        db.close()

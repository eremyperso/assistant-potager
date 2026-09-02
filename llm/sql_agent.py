"""
[US-012] sql_agent.py — Agent SQL pour répondre aux questions sans hallucinations Groq.

Stratégie :
  1. Recevoir l'intent extrait (action, culture, date_from)
  2. Construire et exécuter une requête SQLAlchemy (zéro Groq)
  3. Formater la réponse en texte simple

[US-042 / CA3] Scope par potager_id (isolation inter-potagers) + fenêtre
temporelle par défaut de 12 mois — bornes appliquées à chaque requête.
`potager_id=None` (défaut) préserve le comportement historique non scopé
pour les tests unitaires directs de ce module ; les appelants applicatifs
(app/services/questions.py) passent toujours potager_id=ctx.potager_id.
"""

import logging
import re
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import func
from unidecode import unidecode

from database.db import SessionLocal
from database.models import Evenement
from utils.actions import ACTION_MAP

log = logging.getLogger("potager")

# ─── Fenêtre temporelle / limite par défaut [US-042 / CA3, CA7] ───────────────
WINDOW_DAYS = 365      # 12 mois glissants
EVENT_LIMIT = 100      # nombre maximum d'événements considérés par question

# ─── Conversion d'unités ───────────────────────────────────────────────────────

_WEIGHT_TO_G: dict[str, float] = {
    "g": 1, "gr": 1, "gramme": 1, "grammes": 1,
    "kg": 1000, "kilo": 1000, "kilos": 1000,
}
_VOLUME_TO_ML: dict[str, float] = {
    "ml": 1, "cl": 10, "dl": 100,
    "l": 1000, "litre": 1000, "litres": 1000,
}


_NON_ALPHANUM = re.compile(r"[^a-z0-9]+")


def _action_citee(question: str, action: str) -> bool:
    """Le geste retenu par l'extraction d'intention est-il vraiment cité dans la
    question ?

    L'extraction choisit dans un vocabulaire **fermé** (`INTENT_PROMPT`) : une
    question qui ne relève d'aucun de ces gestes en ressort quand même avec un
    geste. « quelles sont mes parcelles contenant des familles de solanacées ? »
    en est revenue avec `action="observation"` le 02/09/2026, et l'agent a servi
    un « Top cultures — observation » — un classement parfaitement exact, hors
    sujet, et assez assuré (`confiant=True`) pour que la cascade d'US-093 ne
    remonte pas d'un étage. Une réponse fausse d'apparence juste, donc, là où
    « je n'ai pas compris » aurait laissé l'étage suivant répondre. Même cause
    le même jour pour « sur quelles parcelles je trouve des tomates ? », servie
    en « Historique observation de tomate » : le geste inventé, cette fois
    appliqué à la bonne culture.

    Le contrôle ne s'applique qu'aux chemins où le geste dicte la FORME de la
    réponse (classement de cultures, historique d'un geste). Là où il désigne
    seulement QUEL chiffre est demandé — « Total fraise ? » → le total récolté,
    sans qu'aucun synonyme de « récolte » n'apparaisse — l'inférence du modèle
    est légitime et reste retenue.

    Le contrôle réutilise les synonymes de `utils/actions.ACTION_MAP` — le
    référentiel des gestes, jamais une seconde liste — et ne coûte qu'une
    comparaison de chaînes. Les synonymes de moins de quatre lettres sont
    ignorés, comme dans `reponses_chiffrees._detecter_action`, pour la même
    raison : ils matchent n'importe quoi.
    """
    normalisee = _NON_ALPHANUM.sub(" ", unidecode((question or "").strip().lower()))
    for synonyme in ACTION_MAP.get(action, ()):
        normalise = _NON_ALPHANUM.sub(" ", unidecode(synonyme.strip().lower())).strip()
        if len(normalise) >= 4 and re.search(rf"\b{re.escape(normalise)}", normalisee):
            return True
    return False


def _fmt_poids(g: float) -> str:
    return f"{g / 1000:g} kg" if g >= 1000 else f"{g:g} g"


def _fmt_volume(ml: float) -> str:
    return f"{ml / 1000:g} L" if ml >= 1000 else f"{ml:g} ml"


def _aggregate(pairs: list[tuple[str | None, float]]) -> str:
    """Convertit et agrège des (unite, quantite), retourne une chaîne formatée."""
    weight_g = 0.0
    volume_ml = 0.0
    other: dict[str, float] = defaultdict(float)

    for unite, total in pairs:
        if total is None:
            continue
        u = (unite or "").strip().lower()
        if u in _WEIGHT_TO_G:
            weight_g += total * _WEIGHT_TO_G[u]
        elif u in _VOLUME_TO_ML:
            volume_ml += total * _VOLUME_TO_ML[u]
        else:
            other[unite or ""] += total

    parts = []
    if weight_g:
        parts.append(_fmt_poids(weight_g))
    if volume_ml:
        parts.append(_fmt_volume(volume_ml))
    for unite, total in other.items():
        parts.append(f"{total:g} {unite}".strip())
    return " + ".join(parts) if parts else "0"


class QueryAgent:
    """Agent SQL pour questions analytiques — zéro appel LLM.
    [US-042] potager_id=None (défaut) = non scopé (tests unitaires directs)."""

    def __init__(self, db, potager_id: Optional[int] = None):
        self.db = db
        self.potager_id = potager_id

    def _scoped(self, q):
        """[US-042 / CA3] Applique le scope tenant + la fenêtre temporelle 12 mois
        par défaut à une requête portant sur Evenement."""
        if self.potager_id is not None:
            q = q.filter(Evenement.potager_id == self.potager_id)
        cutoff = date.today() - timedelta(days=WINDOW_DAYS)
        q = q.filter(Evenement.date >= cutoff)
        return q

    def answer(self, question: str, intent: dict) -> str:
        """
        Répond à une question sans appel Groq.

        Args:
            question: Question utilisateur (pour le fallback message)
            intent: {"action": ..., "culture": ..., "date_from": ..., "query_type": ...}
        Returns:
            Réponse texte prête à afficher
        """
        texte, _ = self.answer_avec_confiance(question, intent)
        return texte

    def answer_avec_confiance(self, question: str, intent: dict) -> tuple[str, bool]:
        """
        [US-093 / CA6] Variante explicite de `answer()` : signale en plus si la
        réponse est exploitable (`confiant=True`) ou si l'étage n'a rien trouvé
        (`confiant=False`). Le signal est produit ICI, au point exact où on sait
        déjà qu'aucune ligne n'a été trouvée — jamais reconstitué à distance par
        un appelant qui devrait sinon deviner en inspectant le texte produit.

        Args:
            question: Question utilisateur (pour le fallback message)
            intent: {"action": ..., "culture": ..., "date_from": ..., "query_type": ...}
        Returns:
            (réponse texte, confiant)
        """
        action     = intent.get("action")
        culture    = intent.get("culture")
        query_type = intent.get("query_type", "quantite")

        # Le geste est-il seulement dans la question ? La réponse ne commande
        # PAS les mêmes chemins (`_action_citee`) :
        #
        #   • là où le geste dicte à lui seul la FORME de la réponse — un
        #     classement de cultures, la liste des occurrences d'un geste — un
        #     geste inventé produit une réponse hors sujet et sûre d'elle ;
        #   • là où il ne fait que désigner QUEL chiffre est demandé (« Total
        #     fraise ? » → le total récolté), l'inférence du modèle est
        #     légitime et ne cite aucun synonyme. L'écarter casserait des
        #     questions qui marchent.
        geste_cite = bool(action) and _action_citee(question, action)
        if action and not geste_cite:
            log.info(
                "🚫 AGENT SQL       │ geste '%s' absent de la question : ni classement ni historique de geste │ '%s'",
                action, (question or "")[:60],
            )

        if culture and action:
            if query_type == "date":
                return self._answer_date(action, culture)
            if query_type == "historique":
                # « sur quelles parcelles je trouve des tomates ? » arrivait ici
                # avec `action="observation"` et rendait « Historique
                # observation de tomate » (02/09/2026). Sans geste cité, on
                # liste l'historique de la culture, sans lui prêter un geste.
                return self._answer_history_culture(culture, action if geste_cite else None)
            return self._answer_quantity(action, culture)

        if culture and not action:
            return self._answer_history_culture(culture)

        if action and not culture:
            # Un classement « top cultures » sur un geste que personne n'a
            # nommé n'est pas une réponse : il vaut mieux rendre la main.
            if not geste_cite:
                return "Je n'ai pas compris la question. Formulez autrement.", False
            return self._answer_action_stats(action)

        return "Je n'ai pas compris la question. Formulez autrement.", False

    def _answer_quantity(self, action: str, culture: str) -> tuple[str, bool]:
        """Répond à : "Combien de [culture] [action] ?"."""
        q = self._scoped(
            self.db.query(
                Evenement.unite,
                func.sum(Evenement.quantite).label("total"),
            ).filter(
                Evenement.type_action == action,
                Evenement.culture == culture,
            )
        )
        rows = q.group_by(Evenement.unite).all()

        if not rows or all(r.total is None for r in rows):
            return f"Aucune donnée enregistrée pour {culture} / {action}.", False

        total_str = _aggregate([(r.unite, r.total) for r in rows])
        return f"Total {culture} {action} : {total_str}", True

    def _answer_date(self, action: str, culture: str) -> tuple[str, bool]:
        """Répond à : "À quelle date ai-je [action] de [culture] ?"."""
        q = self._scoped(
            self.db.query(Evenement).filter(
                Evenement.type_action == action,
                Evenement.culture == culture,
            )
        )
        events = q.order_by(Evenement.date.desc()).limit(5).all()
        if not events:
            return f"Aucune {action} de {culture} enregistrée.", False

        if len(events) == 1:
            e = events[0]
            date_str = e.date.strftime("%d/%m/%Y") if e.date else "?"
            variete_str = f" ({e.variete})" if e.variete else ""
            qte_str = f" — {e.quantite:g} {e.unite or ''}".rstrip() if e.quantite else ""
            return f"{action.capitalize()} de {culture}{variete_str} : le {date_str}{qte_str}", True

        lines = [f"{action.capitalize()} de {culture} ({len(events)} entrées) :"]
        for e in events:
            date_str = e.date.strftime("%d/%m/%Y") if e.date else "?"
            variete_str = f" {e.variete}" if e.variete else ""
            qte_str = f" — {e.quantite:g} {e.unite or ''}".rstrip() if e.quantite else ""
            lines.append(f"  • {date_str}{variete_str}{qte_str}")
        return "\n".join(lines), True

    def _answer_history_culture(self, culture: str, action: str | None = None) -> tuple[str, bool]:
        """Répond à : "Historique de [culture]" ou "Mes [action] de [culture]"."""
        q = self._scoped(self.db.query(Evenement).filter(Evenement.culture == culture))
        if action:
            q = q.filter(Evenement.type_action == action)
        events = q.order_by(Evenement.date.desc()).limit(5).all()

        if not events:
            label = f"{action} de {culture}" if action else culture
            return f"Aucun événement enregistré pour {label}.", False

        label = f"{action} de {culture}" if action else culture
        lines = [f"Historique {label} (5 derniers) :"]
        for e in events:
            date_str = e.date.strftime("%d/%m/%Y") if e.date else "?"
            variete_str = f" {e.variete}" if e.variete else ""
            qte_str = f" — {e.quantite:g} {e.unite or ''}".rstrip() if e.quantite else ""
            lines.append(f"  • {date_str}{variete_str} {e.type_action}{qte_str}")
        return "\n".join(lines), True

    def _answer_action_stats(self, action: str) -> tuple[str, bool]:
        """Répond à : "Stats [action]"."""
        q = self._scoped(
            self.db.query(
                Evenement.culture,
                Evenement.unite,
                func.count(Evenement.id).label("nb"),
                func.sum(Evenement.quantite).label("total"),
            ).filter(Evenement.type_action == action)
        )
        rows = (
            q.group_by(Evenement.culture, Evenement.unite)
            .order_by(func.sum(Evenement.quantite).desc())
            .limit(10)
            .all()
        )
        if not rows:
            return f"Aucun événement de type {action} enregistré.", False

        # Regroupe par culture, agrège les unités avec conversion
        pairs_by_culture: dict[str, list[tuple]] = defaultdict(list)
        nb_by_culture: dict[str, int] = defaultdict(int)
        for culture, unite, nb, total in rows:
            key = culture or "?"
            pairs_by_culture[key].append((unite, total))
            nb_by_culture[key] += nb

        lines = [f"Top cultures — {action} :"]
        for culture, pairs in pairs_by_culture.items():
            has_qty = any(total for _, total in pairs)
            qte_str = _aggregate(pairs) if has_qty else f"{nb_by_culture[culture]} fois"
            lines.append(f"  • {culture} : {qte_str}")
        return "\n".join(lines), True


def query_agent_answer(question: str, intent: dict, potager_id: Optional[int] = None) -> str:
    """
    [US-012 / US-042] Point d'entrée public — répond via SQL agent, zéro Groq.

    Args:
        question: Question utilisateur
        intent: Dict {action, culture, date_from} issu de extract_intent_query()
        potager_id: [US-042] tenant courant — None (défaut) = non scopé (tests directs) ;
            les appelants applicatifs passent toujours potager_id=ctx.potager_id.
    Returns:
        Réponse texte
    """
    texte, _ = query_agent_answer_avec_confiance(question, intent, potager_id=potager_id)
    return texte


def query_agent_answer_avec_confiance(
    question: str, intent: dict, potager_id: Optional[int] = None
) -> tuple[str, bool]:
    """[US-093 / CA6] Variante de `query_agent_answer()` qui signale en plus si
    l'étage data a trouvé quelque chose d'exploitable — utilisée par le routeur
    pour décider d'une remontée de cascade sans interpréter le texte produit."""
    db = SessionLocal()
    try:
        return QueryAgent(db, potager_id=potager_id).answer_avec_confiance(question, intent)
    finally:
        db.close()

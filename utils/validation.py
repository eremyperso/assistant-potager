"""
[US-011] validation.py — Validation post-parsing pour bloquer les hallucinations Groq.

Règles appliquées en Python pur (zéro appel Groq) :
  1. Action doit être dans la whitelist canonique
  2. Observation → culture + date obligatoires
  3. Texte source avec 3+ marqueurs de question → rejet
  4. Quantité et rang doivent être numériques si présents
"""

ACTIONS_VALIDES = {
    "semis", "plantation", "repiquage", "arrosage", "desherbage",
    "paillage", "fertilisation", "traitement", "taille", "tuteurage",
    "recolte", "perte", "observation", "mise_en_godet",
}

QUESTION_MARKERS = {
    "combien", "quand", "quel", "quelle", "quels", "quelles",
    "afficher", "montrer", "voir", "liste", "consulter", "historique",
    "date", "derniere", "dernier", "depuis", "nombre", "total",
}


def _count_question_markers(texte: str) -> int:
    words = texte.lower().split()
    return sum(1 for w in words if w.rstrip("?.,!") in QUESTION_MARKERS)


def validate_parsed_action(parsed: dict, texte_original: str) -> tuple[bool, str]:
    """
    [US-011] Valide qu'un JSON parsé par Groq représente réellement une action.

    Retourne (is_valid, raison).
    """
    action = parsed.get("action")
    culture = parsed.get("culture")
    quantite = parsed.get("quantite")
    date = parsed.get("date")

    # Règle 1 — action dans la whitelist (si fournie)
    if action and action.lower() not in ACTIONS_VALIDES:
        return False, f"Action inconnue ou hallucination Groq : '{action}'"

    # Règle 2 — observation exige culture + date
    if action and action.lower() == "observation":
        if not culture or not date:
            return False, "Observation sans culture ou date → hallucination Groq"

    # Règle 3 — texte qui ressemble à une question
    if _count_question_markers(texte_original) >= 3:
        return False, f"Texte ressemble à une question ({_count_question_markers(texte_original)} marqueurs)"

    # Règle 4 — quantité numérique
    if quantite is not None:
        try:
            float(quantite)
        except (ValueError, TypeError):
            return False, f"Quantité non numérique : '{quantite}'"

    rang = parsed.get("rang")
    if rang is not None:
        try:
            int(rang)
        except (ValueError, TypeError):
            return False, f"Rang non numérique : '{rang}'"

    return True, "Validation OK"

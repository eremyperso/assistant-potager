"""
utils/notes.py — Helpers de détection et catégorisation pour le flux NOTE (US-038)

Saisie guidée de notes/observations : l'utilisateur choisit une catégorie
(observation, maladie, arrosage, paillage), l'assistant pose une question
guidée adaptée, puis Groq extrait les champs pertinents de la réponse libre.
Tout est enregistré comme un Evenement type_action="observation" — aucune
colonne supplémentaire n'est nécessaire.
"""
import re

# [US-038] Catégories de notes proposées au premier tour de menu.
# La clé est utilisée comme préfixe dans le champ commentaire de l'Evenement.
NOTE_CATEGORIES: dict[str, dict[str, str]] = {
    "observation": {
        "label": "🔍 Observation",
        "question": (
            "Décris ton observation (parcelle et culture concernées si besoin) :"
        ),
    },
    "maladie": {
        "label": "🐛 Maladie / ravageur",
        "question": (
            "Décris le problème sanitaire observé : culture/parcelle concernée, "
            "symptôme constaté, et le traitement appliqué ou envisagé si tu en as un."
        ),
    },
    "arrosage": {
        "label": "💧 Arrosage (remarque)",
        "question": (
            "Décris ton constat lié à l'arrosage : parcelle concernée, état du sol "
            "(sec/détrempé...), durée constatée si pertinent."
        ),
    },
    "paillage": {
        "label": "🌿 Paillage",
        "question": (
            "Décris ton constat ou action de paillage : parcelle/culture concernée, "
            "matériau utilisé si pertinent."
        ),
    },
}

# Mots-clés déclencheurs du flux NOTE (message vocal/texte libre)
_NOTE_KEYWORDS = (
    "je veux noter", "je voudrais noter", "noter une observation",
    "noter un truc", "ajouter une note", "prendre une note",
    "faire une observation", "noter que", "à noter",
)


def is_note_request(texte: str) -> bool:
    """[US-038 / CA2] Retourne True si la phrase déclenche le flux guidé de note."""
    t = texte.lower().strip()
    return any(kw in t for kw in _NOTE_KEYWORDS)


# Réponses au menu de catégories → clé canonique NOTE_CATEGORIES.
# Tolère l'emoji, la casse, les accents et le pluriel/variantes courantes.
_CATEGORY_ALIASES: dict[str, str] = {
    "observation": "observation",
    "maladie": "maladie",
    "maladie / ravageur": "maladie",
    "ravageur": "maladie",
    "arrosage": "arrosage",
    "arrosage (remarque)": "arrosage",
    "paillage": "paillage",
}


def match_note_category(texte: str) -> str | None:
    """[US-038 / CA3] Identifie la catégorie choisie depuis le texte du bouton ou une réponse libre."""
    t = texte.lower().strip()
    t = re.sub(r"[^\w\sàâçéèêëîïôûùüÿæœ/()]", "", t).strip()

    if t in _CATEGORY_ALIASES:
        return _CATEGORY_ALIASES[t]

    for alias, key in _CATEGORY_ALIASES.items():
        if alias in t:
            return key
    return None

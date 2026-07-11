"""
[US-011] validation.py — Validation post-parsing pour bloquer les hallucinations Groq.

Règles appliquées en Python pur (zéro appel Groq) :
  1. Action doit être dans la whitelist canonique
  2. Observation → culture + date obligatoires
  3. Texte source avec 3+ marqueurs de question → rejet
  4. Quantité et rang doivent être numériques si présents
  5. Culture extraite mais absente du texte source → retirée (hallucination Groq)
"""
import re
from unidecode import unidecode

ACTIONS_VALIDES = {
    "semis", "plantation", "repiquage", "arrosage", "desherbage",
    "paillage", "fertilisation", "traitement", "taille", "tuteurage",
    "recolte", "perte", "observation", "mise_en_godet",
    "vendu", "perte_godet",   # actions pépinière
}

QUESTION_MARKERS = {
    "combien", "quand", "quel", "quelle", "quels", "quelles",
    "affiche", "afficher", "montre", "montrer", "voir", "liste", "consulter", "historique",
    "detail", "détail", "date", "derniere", "dernier", "depuis", "nombre", "total",
}


def _count_question_markers(texte: str) -> int:
    words = texte.lower().split()
    return sum(1 for w in words if w.rstrip("?.,!") in QUESTION_MARKERS)


def _normalise_mot(mot: str) -> str:
    """Minuscule + sans accent, pour une comparaison texte robuste."""
    return unidecode(mot).lower().strip()


def culture_grounded_dans_texte(culture: str, texte_original: str) -> bool:
    """
    [US-011 bis] Vrai si `culture` apparaît comme un MOT du texte_original
    (insensible à la casse, aux accents, et au pluriel simple en 's'/'es').

    Comparaison mot-à-mot (pas une sous-chaîne brute) pour éviter les faux
    positifs — ex : "ail" est une sous-chaîne de "paillage" mais n'y est pas
    mentionné comme culture.

    Sert à détecter une culture inventée par Groq alors qu'aucun légume/plante
    n'est mentionné dans le message dicté/tapé par l'utilisateur.
    """
    if not culture:
        return True  # rien à vérifier

    culture_norm = _normalise_mot(str(culture))
    # Variantes plurielles/singulières simples (français) pour ne pas rater
    # une culture citée au pluriel dans le texte alors que Groq l'a renvoyée
    # au singulier (ou l'inverse).
    candidats = {culture_norm, culture_norm + "s", culture_norm + "es"}
    if culture_norm.endswith("es"):
        candidats.add(culture_norm[:-2])
    elif culture_norm.endswith("s"):
        candidats.add(culture_norm[:-1])

    mots_texte = {_normalise_mot(m) for m in re.findall(r"[^\W\d_]+", texte_original, flags=re.UNICODE)}

    return any(c and c in mots_texte for c in candidats)


def strip_culture_hallucinee(parsed: dict, texte_original: str) -> dict:
    """
    [US-011 bis] Retire `culture` (et `variete`) d'un item parsé si la culture
    n'apparaît nulle part dans le texte source — évite d'enregistrer une culture
    inventée par Groq (ex : "paillage parcelle X" → culture="ail" halluciné).

    Ne bloque jamais l'action entière : seule la culture non fondée est retirée.
    """
    culture = parsed.get("culture")
    if culture and not culture_grounded_dans_texte(culture, texte_original):
        parsed = dict(parsed)
        parsed["culture"] = None
        parsed["variete"] = None
        return parsed
    return parsed


def validate_parsed_action(parsed: dict, texte_original: str) -> tuple[bool, str]:
    """
    [US-011] Valide qu'un JSON parsé par Groq représente réellement une action.

    Retourne (is_valid, raison).
    """
    action = parsed.get("action")
    culture = parsed.get("culture")
    quantite = parsed.get("quantite")
    date = parsed.get("date")

    # Règle 0 — action obligatoire (None = Groq a parsé une question/hallucination)
    if not action:
        return False, "Action manquante (None) — Groq a parsé une interrogation comme une action"

    # Règle 1 — action dans la whitelist
    if action.lower() not in ACTIONS_VALIDES:
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

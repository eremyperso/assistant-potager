"""
[US-011] Tests — Validation post-parsing pour bloquer les hallucinations Groq.

Couvre les 6 critères d'acceptance + edge cases.
Zéro appel réseau — validation en Python pur.
"""

import pytest
from utils.validation import validate_parsed_action


# ─────────────────────────────────────────────────────────────────────────────
# CA1 — Action hors whitelist → rejetée
# ─────────────────────────────────────────────────────────────────────────────

def test_us011_ca1_action_inconnue_rejetee():
    """CA1 : action hors whitelist canonique est rejetée."""
    valid, reason = validate_parsed_action(
        {"action": "supergrossissage", "culture": "tomate"},
        "Récolté 2 kg de tomates"
    )
    assert valid is False
    assert "inconnue" in reason.lower() or "hallucination" in reason.lower()


def test_us011_ca1_action_valide_acceptee():
    """CA1 inverse : action de la whitelist est acceptée."""
    valid, _ = validate_parsed_action(
        {"action": "recolte", "culture": "tomate", "quantite": 2},
        "Récolté 2 kg de tomates"
    )
    assert valid is True


# ─────────────────────────────────────────────────────────────────────────────
# CA2 — Observation sans culture ou date → rejetée
# ─────────────────────────────────────────────────────────────────────────────

def test_us011_ca2_observation_sans_date_rejetee():
    """CA2 : observation sans date est rejetée."""
    valid, reason = validate_parsed_action(
        {"action": "observation", "culture": "tomate", "date": None},
        "J'ai observé les tomates"
    )
    assert valid is False
    assert "observation" in reason.lower()


def test_us011_ca2_observation_sans_culture_rejetee():
    """CA2 : observation sans culture est rejetée."""
    valid, reason = validate_parsed_action(
        {"action": "observation", "culture": None, "date": "2026-04-20"},
        "Observation dans le jardin"
    )
    assert valid is False
    assert "observation" in reason.lower()


def test_us011_ca2_observation_complete_acceptee():
    """CA2 inverse : observation avec culture + date passe la validation."""
    valid, _ = validate_parsed_action(
        {"action": "observation", "culture": "tomate", "date": "2026-04-20"},
        "Observé les tomates aujourd'hui"
    )
    assert valid is True


# ─────────────────────────────────────────────────────────────────────────────
# CA3 — Texte avec 3+ marqueurs de question → rejeté
# ─────────────────────────────────────────────────────────────────────────────

def test_us011_ca3_texte_question_rejete():
    """CA3 : texte avec 3+ marqueurs de question est rejeté."""
    valid, reason = validate_parsed_action(
        {"action": "recolte", "culture": "tomate"},
        "Combien de tomates quand afficher liste ?"
    )
    assert valid is False
    assert "question" in reason.lower() or "marqueur" in reason.lower()


def test_us011_ca3_texte_action_accepte():
    """CA3 inverse : texte d'action sans marqueurs de question passe."""
    valid, _ = validate_parsed_action(
        {"action": "semis", "culture": "carotte"},
        "Semé des carottes hier dans la parcelle nord"
    )
    assert valid is True


# ─────────────────────────────────────────────────────────────────────────────
# CA4 — Quantité non numérique → rejetée
# ─────────────────────────────────────────────────────────────────────────────

def test_us011_ca4_quantite_non_numerique_rejetee():
    """CA4 : quantité non numérique est rejetée."""
    valid, reason = validate_parsed_action(
        {"action": "recolte", "culture": "tomate", "quantite": "beaucoup"},
        "Récolté beaucoup de tomates"
    )
    assert valid is False
    assert "quantit" in reason.lower()


def test_us011_ca4_quantite_numerique_acceptee():
    """CA4 inverse : quantité numérique (int ou float) passe."""
    valid, _ = validate_parsed_action(
        {"action": "recolte", "culture": "tomate", "quantite": 2.5},
        "Récolté 2.5 kg de tomates"
    )
    assert valid is True


def test_us011_ca4_rang_non_numerique_rejete():
    """CA4 : rang non numérique est rejeté."""
    valid, reason = validate_parsed_action(
        {"action": "plantation", "culture": "poivron", "rang": "trois"},
        "Planté des poivrons sur trois rangs"
    )
    assert valid is False
    assert "rang" in reason.lower()


# ─────────────────────────────────────────────────────────────────────────────
# CA5 — Rejet → WARNING (vérifié via retour de la fonction)
# ─────────────────────────────────────────────────────────────────────────────

def test_us011_ca5_rejet_retourne_raison():
    """CA5 : tout rejet retourne une raison non vide (loggable en WARNING)."""
    valid, reason = validate_parsed_action(
        {"action": "inventee", "culture": "tomate"},
        "test"
    )
    assert valid is False
    assert reason and len(reason) > 0


# ─────────────────────────────────────────────────────────────────────────────
# CA6 — Actions valides passent sans modification
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("action", [
    "semis", "plantation", "repiquage", "arrosage", "desherbage",
    "paillage", "fertilisation", "traitement", "taille", "tuteurage",
    "recolte", "perte", "mise_en_godet",
])
def test_us011_ca6_toutes_actions_canoniques_acceptees(action):
    """CA6 : toutes les actions canoniques de la whitelist passent."""
    valid, reason = validate_parsed_action(
        {"action": action, "culture": "tomate"},
        f"Action {action} sur les tomates"
    )
    assert valid is True, f"Action '{action}' rejetée à tort : {reason}"


# ─────────────────────────────────────────────────────────────────────────────
# Edge cases
# ─────────────────────────────────────────────────────────────────────────────

def test_us011_edge_sans_action_bloque():
    """Règle 0 : action=None → rejet immédiat (Groq a parsé une interrogation comme action)."""
    valid, reason = validate_parsed_action({}, "affiche le détail sur la culture courgette")
    assert valid is False
    assert "None" in reason or "manquante" in reason


def test_us011_edge_quantite_none_acceptee():
    """Edge : quantite=None ne déclenche pas de rejet."""
    valid, _ = validate_parsed_action(
        {"action": "arrosage", "culture": "courgette", "quantite": None},
        "Arrosé les courgettes"
    )
    assert valid is True


def test_us011_edge_action_casse_insensible():
    """Edge : la casse de l'action n'importe pas (RECOLTE == recolte)."""
    valid, _ = validate_parsed_action(
        {"action": "RECOLTE", "culture": "tomate"},
        "Récolté des tomates"
    )
    assert valid is True

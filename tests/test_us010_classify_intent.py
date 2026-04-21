"""
[US-010] Tests — Améliorer la classification d'intention pour distinguer questions et actions.

Couvre les 6 critères d'acceptance + edge cases + erreur API Groq.
Tous les appels Groq sont mockés (pas de réseau).
"""

import pytest
from unittest.mock import patch, MagicMock


# ─────────────────────────────────────────────────────────────────────────────
# Fixture : mock d'un appel Groq retournant un intent donné
# ─────────────────────────────────────────────────────────────────────────────

def _mock_groq_response(intent: str):
    """Retourne un mock Groq simulant la réponse intent."""
    mock_choice = MagicMock()
    mock_choice.message.content = intent
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    return mock_resp


def _classify(texte: str, groq_returns: str) -> str:
    """Appelle classify_intent() avec Groq mocké."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_groq_response(groq_returns)
    with patch("groq.Groq", return_value=mock_client):
        from bot import classify_intent
        return classify_intent(texte)


# ─────────────────────────────────────────────────────────────────────────────
# CA1 — "Combien de tomates ai-je récolté ?" → INTERROGER
# ─────────────────────────────────────────────────────────────────────────────

def test_us010_ca1_question_combien_classifie_interroger():
    """CA1 : question avec 'combien' est classifiée INTERROGER."""
    result = _classify("Combien de tomates ai-je récolté ?", "INTERROGER")
    assert result == "INTERROGER"


# ─────────────────────────────────────────────────────────────────────────────
# CA2 — "Afficher les récoltes de carotte" → INTERROGER
# ─────────────────────────────────────────────────────────────────────────────

def test_us010_ca2_afficher_classifie_interroger():
    """CA2 : message avec 'afficher' est classifié INTERROGER."""
    result = _classify("Afficher les récoltes de carotte", "INTERROGER")
    assert result == "INTERROGER"


# ─────────────────────────────────────────────────────────────────────────────
# CA3 — "Quand ai-je planté mes courgettes ?" → INTERROGER
# ─────────────────────────────────────────────────────────────────────────────

def test_us010_ca3_question_quand_classifie_interroger():
    """CA3 : question avec 'quand' est classifiée INTERROGER."""
    result = _classify("Quand ai-je planté mes courgettes ?", "INTERROGER")
    assert result == "INTERROGER"


# ─────────────────────────────────────────────────────────────────────────────
# CA4 — "J'ai récolté 2 kg de tomates" → ACTION
# ─────────────────────────────────────────────────────────────────────────────

def test_us010_ca4_action_recolte_classifie_action():
    """CA4 : action déclarative au passé reste classifiée ACTION."""
    result = _classify("J'ai récolté 2 kg de tomates", "ACTION")
    assert result == "ACTION"


# ─────────────────────────────────────────────────────────────────────────────
# CA5 — "Semé des carottes hier" → ACTION
# ─────────────────────────────────────────────────────────────────────────────

def test_us010_ca5_action_semis_classifie_action():
    """CA5 : action passée sans point d'interrogation reste classifiée ACTION."""
    result = _classify("Semé des carottes hier", "ACTION")
    assert result == "ACTION"


# ─────────────────────────────────────────────────────────────────────────────
# CA6 — message avec "?" ET mot-clé interrogatif → jamais ACTION
# ─────────────────────────────────────────────────────────────────────────────

def test_us010_ca6_point_interrogation_plus_motcle_jamais_action():
    """CA6 : message avec '?' + mot-clé interrogatif n'est jamais classifié ACTION."""
    result = _classify("Quel est le total de mes semis ?", "INTERROGER")
    assert result != "ACTION"
    assert result == "INTERROGER"


# ─────────────────────────────────────────────────────────────────────────────
# Edge cases
# ─────────────────────────────────────────────────────────────────────────────

def test_us010_edge_montrer_classifie_interroger():
    """Edge : 'montrer' déclenche INTERROGER."""
    result = _classify("Montrer mes semis de radis", "INTERROGER")
    assert result == "INTERROGER"


def test_us010_edge_voir_classifie_interroger():
    """Edge : 'voir' déclenche INTERROGER."""
    result = _classify("Voir les dernières récoltes", "INTERROGER")
    assert result == "INTERROGER"


def test_us010_edge_liste_classifie_interroger():
    """Edge : 'liste' déclenche INTERROGER."""
    result = _classify("Liste des plantations de mai", "INTERROGER")
    assert result == "INTERROGER"


def test_us010_edge_action_verbe_passe_sans_question():
    """Edge : verbe d'action au passé sans '?' → ACTION."""
    result = _classify("Arrosé les courgettes 30 minutes", "ACTION")
    assert result == "ACTION"


def test_us010_edge_plan_classifie_plan():
    """Edge : demande de plan → PLAN (non ACTION, non INTERROGER)."""
    result = _classify("Plan du potager", "PLAN")
    assert result == "PLAN"


def test_us010_edge_stats_classifie_stats():
    """Edge : 'stats' → STATS (non ACTION)."""
    result = _classify("stats", "STATS")
    assert result == "STATS"


# ─────────────────────────────────────────────────────────────────────────────
# Cas d'erreur — API Groq indisponible → fallback ACTION
# ─────────────────────────────────────────────────────────────────────────────

def test_us010_erreur_groq_fallback_action():
    """Erreur API Groq → fallback sécurisé sur ACTION."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("Groq timeout")
    with patch("groq.Groq", return_value=mock_client):
        from bot import classify_intent
        result = classify_intent("Combien de tomates ?")
    assert result == "ACTION"  # fallback défini dans classify_intent()


# ─────────────────────────────────────────────────────────────────────────────
# Cas d'erreur — Intent inconnu retourné → fallback ACTION
# ─────────────────────────────────────────────────────────────────────────────

def test_us010_intent_inconnu_fallback_action():
    """Intent non reconnu dans INTENTS → fallback ACTION."""
    result = _classify("blabla incomprehensible", "INCONNU_XYZ")
    assert result == "ACTION"

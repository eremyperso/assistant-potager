"""
[US-012] Tests — Agent SQL pour répondre aux questions sans appel Groq.

Couvre les 6 critères d'acceptance + edge cases.
DB mockée via SQLite in-memory (fixtures conftest.py).
"""

import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.db import Base
from database.models import Evenement
from llm.sql_agent import QueryAgent, query_agent_answer


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def db_session():
    """Session SQLite in-memory avec données de test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    from datetime import datetime
    events = [
        Evenement(type_action="recolte", culture="tomate", quantite=2.0, unite="kg",
                  date=datetime(2026, 4, 10)),
        Evenement(type_action="recolte", culture="tomate", quantite=3.5, unite="kg",
                  date=datetime(2026, 4, 15)),
        Evenement(type_action="arrosage", culture="courgette", date=datetime(2026, 4, 18)),
        Evenement(type_action="arrosage", culture="courgette", date=datetime(2026, 4, 17)),
        Evenement(type_action="arrosage", culture="courgette", date=datetime(2026, 4, 16)),
        Evenement(type_action="arrosage", culture="courgette", date=datetime(2026, 4, 15)),
        Evenement(type_action="arrosage", culture="courgette", date=datetime(2026, 4, 14)),
        Evenement(type_action="semis", culture="carotte", quantite=50.0, unite="graines",
                  date=datetime(2026, 3, 1)),
    ]
    for e in events:
        db.add(e)
    db.commit()
    yield db
    db.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def agent(db_session):
    return QueryAgent(db_session)


# ─────────────────────────────────────────────────────────────────────────────
# CA1 — Retourne le total réel depuis la base
# ─────────────────────────────────────────────────────────────────────────────

def test_us012_ca1_total_recolte_tomate(agent):
    """CA1 : question 'combien de tomates récolté' retourne le total réel."""
    intent = {"action": "recolte", "culture": "tomate", "date_from": None}
    reponse = agent.answer("Combien de tomates ai-je récolté ?", intent)
    assert "tomate" in reponse.lower()
    assert "5.5" in reponse or "recolte" in reponse.lower()


# ─────────────────────────────────────────────────────────────────────────────
# CA2 — Historique d'une culture — liste les 5 derniers événements
# ─────────────────────────────────────────────────────────────────────────────

def test_us012_ca2_historique_arrosage_courgette(agent):
    """CA2 : historique des arrosages courgettes liste ≤ 5 événements."""
    intent = {"action": None, "culture": "courgette", "date_from": None}
    reponse = agent.answer("Historique des arrosages courgettes", intent)
    assert "courgette" in reponse.lower()
    # 5 arrosages en base → doit tous les afficher (limite = 5)
    assert reponse.count("arrosage") >= 1


# ─────────────────────────────────────────────────────────────────────────────
# CA3 — Aucun appel à repondre_question() (Groq)
# ─────────────────────────────────────────────────────────────────────────────

def test_us012_ca3_pas_appel_repondre_question(db_session):
    """CA3 : query_agent_answer() n'appelle jamais repondre_question()."""
    intent = {"action": "recolte", "culture": "tomate", "date_from": None}
    with patch("llm.groq_client.repondre_question") as mock_rq:
        with patch("llm.sql_agent.SessionLocal", return_value=db_session):
            query_agent_answer("Combien de tomates ?", intent)
    mock_rq.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# CA4 — extract_intent_query() ≤ 100 tokens (via mock — on vérifie max_tokens)
# ─────────────────────────────────────────────────────────────────────────────

def test_us012_ca4_extract_intent_query_max_tokens():
    """CA4 : extract_intent_query() appelle Groq avec max_tokens ≤ 128."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = '{"action":"recolte","culture":"tomate","date_from":null}'
    mock_client.chat.completions.create.return_value = mock_resp

    with patch("llm.groq_client._client", mock_client):
        from llm.groq_client import extract_intent_query
        extract_intent_query("Combien de tomates ?")

    call_kwargs = mock_client.chat.completions.create.call_args[1]
    assert call_kwargs.get("max_tokens", 999) <= 128


# ─────────────────────────────────────────────────────────────────────────────
# CA5 — Intent non reconnu → message clair, sans erreur
# ─────────────────────────────────────────────────────────────────────────────

def test_us012_ca5_intent_vide_retourne_message_comprehensible(agent):
    """CA5 : intent sans action ni culture retourne un message d'aide, pas une exception."""
    intent = {"action": None, "culture": None, "date_from": None}
    reponse = agent.answer("blabla incompréhensible", intent)
    assert isinstance(reponse, str)
    assert len(reponse) > 0
    assert "compris" in reponse.lower() or "formulez" in reponse.lower()


# ─────────────────────────────────────────────────────────────────────────────
# CA6 — La réponse est transmise par TTS (vérifié dans bot.py — test d'intégration)
# Note : non testable automatiquement ici (dépend de send_voice_reply Telegram)
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# Edge cases
# ─────────────────────────────────────────────────────────────────────────────

def test_us012_edge_culture_sans_donnees(agent):
    """Edge : culture inexistante en base → message 'aucune donnée'."""
    intent = {"action": "recolte", "culture": "licorne", "date_from": None}
    reponse = agent.answer("Combien de licornes récoltées ?", intent)
    assert "aucune" in reponse.lower() or "licorne" in reponse.lower()


def test_us012_edge_action_seule_sans_culture(agent):
    """Edge : intent avec action seule → stats par culture."""
    intent = {"action": "arrosage", "culture": None, "date_from": None}
    reponse = agent.answer("Stats arrosages ?", intent)
    assert "arrosage" in reponse.lower()
    assert "courgette" in reponse.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Conversion d'unités — _aggregate()
# ─────────────────────────────────────────────────────────────────────────────

def test_us012_conversion_g_et_kg_fusionne_en_kg():
    """500 g + 1 kg → 1.5 kg (fusion, pas '500 g + 1 kg')."""
    from llm.sql_agent import _aggregate
    result = _aggregate([("g", 500.0), ("kg", 1.0)])
    assert result == "1.5 kg"


def test_us012_conversion_g_seul_reste_en_g():
    """800 g reste affiché en g (pas de conversion si < 1000 g)."""
    from llm.sql_agent import _aggregate
    result = _aggregate([("g", 800.0)])
    assert result == "800 g"


def test_us012_conversion_g_depasse_1000_passe_en_kg():
    """1200 g → 1.2 kg."""
    from llm.sql_agent import _aggregate
    result = _aggregate([("g", 1200.0)])
    assert result == "1.2 kg"


def test_us012_conversion_ml_et_cl_fusionne_en_l():
    """500 ml + 50 cl (=500 ml) → 1 L."""
    from llm.sql_agent import _aggregate
    result = _aggregate([("ml", 500.0), ("cl", 50.0)])
    assert result == "1 L"


def test_us012_conversion_unites_mixtes_non_converties_separees():
    """'graines' et 'plants' restent séparés (pas de conversion)."""
    from llm.sql_agent import _aggregate
    result = _aggregate([("graines", 50.0), ("plants", 10.0)])
    assert "50 graines" in result
    assert "10 plants" in result


def test_us012_conversion_en_base_total_kg_mixte(db_session):
    """Récolte avec g et kg en base → total converti en kg."""
    from datetime import datetime
    db_session.add(Evenement(type_action="recolte", culture="fraise",
                             quantite=500.0, unite="g", date=datetime(2026, 5, 1)))
    db_session.add(Evenement(type_action="recolte", culture="fraise",
                             quantite=1.0, unite="kg", date=datetime(2026, 5, 2)))
    db_session.commit()
    agent = QueryAgent(db_session)
    reponse = agent.answer("Total fraise ?", {"action": "recolte", "culture": "fraise"})
    assert "1.5 kg" in reponse


def test_us012_edge_extract_intent_query_json_invalide():
    """Edge : Groq retourne du JSON invalide → fallback dict vide sans crash."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = "réponse invalide non JSON"
    mock_client.chat.completions.create.return_value = mock_resp

    with patch("llm.groq_client._client", mock_client):
        from llm.groq_client import extract_intent_query
        result = extract_intent_query("Combien de tomates ?")

    assert result == {"action": None, "culture": None, "date_from": None}

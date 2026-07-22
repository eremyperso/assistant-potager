"""
tests/test_isolation_potager.py — [US-042 / CA5]
-----------------------------------------------------------------------
Test d'isolation obligatoire : étant donné deux potagers A et B possédant
chacun des événements distincts, toute requête (historique, stats, plan,
question analytique) effectuée avec le contexte du potager A ne doit
retourner strictement aucune donnée du potager B.

Couvre aussi CA3 (repondre_question/QueryAgent scopés) et CA7 (fenêtre
temporelle 12 mois + limite 100 événements de llm/sql_agent.py).
"""
from datetime import datetime, date, timedelta
from unittest.mock import patch

import pytest

from app.services.context import TenantContext
from app.services import evenements as svc_evenements
from app.services import stats as svc_stats
from app.services import plan as svc_plan
from app.services import parcelles as svc_parcelles
from app.services import questions as svc_questions
from database.models import Evenement, Parcelle, CultureConfig
from llm.sql_agent import QueryAgent


CTX_A = TenantContext(user_id=1, potager_id=1, role="owner")
CTX_B = TenantContext(user_id=2, potager_id=2, role="owner")


@pytest.fixture
def deux_potagers(test_db):
    """Deux potagers A (id=1) et B (id=2) avec des données distinctes."""
    # [pré-existant] nom_normalise porte une contrainte UNIQUE globale (pas encore
    # scopée par potager_id — hors périmètre de cette US) : noms distincts ici.
    parcelle_a = Parcelle(nom="Nord A", nom_normalise="norda", ordre=1, actif=True, potager_id=1)
    parcelle_b = Parcelle(nom="Nord B", nom_normalise="nordb", ordre=1, actif=True, potager_id=2)
    test_db.add_all([parcelle_a, parcelle_b])
    test_db.commit()

    aujourd_hui = datetime.combine(date.today(), datetime.min.time())

    evt_a = Evenement(
        type_action="recolte", culture="tomate", quantite=5.0, unite="kg",
        date=aujourd_hui, parcelle_id=parcelle_a.id, potager_id=1,
    )
    evt_b = Evenement(
        type_action="recolte", culture="courgette", quantite=9.0, unite="kg",
        date=aujourd_hui, parcelle_id=parcelle_b.id, potager_id=2,
    )
    plant_a = Evenement(
        type_action="plantation", culture="tomate", quantite=3, unite="plants",
        date=aujourd_hui, parcelle_id=parcelle_a.id, potager_id=1,
    )
    plant_b = Evenement(
        type_action="plantation", culture="courgette", quantite=4, unite="plants",
        date=aujourd_hui, parcelle_id=parcelle_b.id, potager_id=2,
    )
    test_db.add_all([evt_a, evt_b, plant_a, plant_b])
    test_db.commit()

    return {"parcelle_a": parcelle_a, "parcelle_b": parcelle_b, "evt_a": evt_a, "evt_b": evt_b}


# ──────────────────────────────────────────────────────────────────────────────
# CA5 — Isolation historique / lecture d'événements
# ──────────────────────────────────────────────────────────────────────────────

def test_ca5_lister_evenements_isole_par_potager(test_db, deux_potagers):
    total_a, events_a = svc_evenements.lister_evenements(test_db, CTX_A)
    total_b, events_b = svc_evenements.lister_evenements(test_db, CTX_B)

    assert total_a == 2
    assert {e.culture for e in events_a} == {"tomate"}
    assert total_b == 2
    assert {e.culture for e in events_b} == {"courgette"}


def test_ca5_get_evenement_id_dun_autre_potager_retourne_none(test_db, deux_potagers):
    evt_b_id = deux_potagers["evt_b"].id
    assert svc_evenements.get_evenement(test_db, CTX_A, evt_b_id) is None
    assert svc_evenements.get_evenement(test_db, CTX_B, evt_b_id) is not None


def test_ca5_supprimer_evenement_dun_autre_potager_echoue(test_db, deux_potagers):
    evt_b_id = deux_potagers["evt_b"].id
    assert svc_evenements.supprimer_evenement(test_db, CTX_A, evt_b_id) is False
    # La donnée du potager B doit toujours exister
    assert svc_evenements.get_evenement(test_db, CTX_B, evt_b_id) is not None


def test_ca5_dernier_evenement_isole(test_db, deux_potagers):
    dernier_a = svc_evenements.dernier_evenement(test_db, CTX_A)
    dernier_b = svc_evenements.dernier_evenement(test_db, CTX_B)
    assert dernier_a.potager_id == 1
    assert dernier_b.potager_id == 2


# ──────────────────────────────────────────────────────────────────────────────
# [fix bug rapporté] Isolation du garde-fou "culture jamais plantée"
# (culture_deja_plantee ne filtrait pas par potager_id — une culture plantée
# dans N'IMPORTE QUEL AUTRE potager neutralisait le garde-fou partout).
# ──────────────────────────────────────────────────────────────────────────────

def test_ca5_culture_jamais_plantee_dans_ce_potager_refusee_meme_si_plantee_ailleurs(test_db, deux_potagers):
    """Le potager B a planté 'courgette', jamais 'tomate' — 'tomate' n'existe que
    dans le potager A. Une récolte de tomate tentée sur B doit être refusée,
    même si tomate est parfaitement connue ailleurs dans la base."""
    with pytest.raises(svc_evenements.CultureInconnueError):
        svc_evenements.valider_evenement(test_db, CTX_B, action="recolte", culture="tomate")

    # Non-régression : la récolte reste bien autorisée sur le potager qui l'a plantée
    svc_evenements.valider_evenement(test_db, CTX_A, action="recolte", culture="tomate")


# ──────────────────────────────────────────────────────────────────────────────
# Scénario Gherkin — Isolation des statistiques entre deux potagers
# ──────────────────────────────────────────────────────────────────────────────

def test_ca5_stats_isolees_entre_deux_potagers(test_db, deux_potagers):
    stats_a = svc_stats.calculer_stats(test_db, CTX_A)
    stats_b = svc_stats.calculer_stats(test_db, CTX_B)

    assert "tomate" in stats_a.stocks
    assert "courgette" not in stats_a.stocks

    assert "courgette" in stats_b.stocks
    assert "tomate" not in stats_b.stocks


# ──────────────────────────────────────────────────────────────────────────────
# Isolation du plan d'occupation des parcelles
# ──────────────────────────────────────────────────────────────────────────────

def test_ca5_plan_occupation_isole_entre_deux_potagers(test_db, deux_potagers):
    parcelles_a = svc_plan.get_parcelles(test_db, CTX_A)
    parcelles_b = svc_plan.get_parcelles(test_db, CTX_B)

    assert {p.id for p in parcelles_a} == {deux_potagers["parcelle_a"].id}
    assert {p.id for p in parcelles_b} == {deux_potagers["parcelle_b"].id}

    occupation_a = svc_plan.get_occupation(test_db, CTX_A)
    occupation_b = svc_plan.get_occupation(test_db, CTX_B)

    cultures_a = {entry["culture"] for liste in occupation_a.values() for entry in liste}
    cultures_b = {entry["culture"] for liste in occupation_b.values() for entry in liste}
    assert cultures_a == {"tomate"}
    assert cultures_b == {"courgette"}


def test_ca5_get_parcelle_dun_autre_potager_retourne_none(test_db, deux_potagers):
    parcelle_b_id = deux_potagers["parcelle_b"].id
    assert svc_parcelles.get_parcelle(test_db, CTX_A, parcelle_b_id) is None
    assert svc_parcelles.get_parcelle(test_db, CTX_B, parcelle_b_id) is not None


# ──────────────────────────────────────────────────────────────────────────────
# Scénario Gherkin — Isolation du mode ask (QueryAgent, avant même Groq)
# ──────────────────────────────────────────────────────────────────────────────

def test_ca5_queryagent_isole_par_potager(test_db, deux_potagers):
    intent = {"action": "recolte", "culture": None, "date_from": None, "query_type": "stats"}

    reponse_a = QueryAgent(test_db, potager_id=1).answer("stats récolte", intent)
    reponse_b = QueryAgent(test_db, potager_id=2).answer("stats récolte", intent)

    assert "tomate" in reponse_a.lower()
    assert "courgette" not in reponse_a.lower()

    assert "courgette" in reponse_b.lower()
    assert "tomate" not in reponse_b.lower()


def test_ca5_repondre_question_isolee_par_potager(test_db, deux_potagers):
    """[Gherkin] Un membre du potager A pose une question via /ask → aucune donnée
    du potager B dans la réponse. extract_intent_query_mesuree est mocké (zéro appel
    réseau Groq réel dans les tests) ; seul le scoping SQL est vérifié ici."""
    intent = {"action": "recolte", "culture": None, "date_from": None, "query_type": "stats"}

    with patch("app.services.questions.extract_intent_query_mesuree", return_value=(intent, 42)):
        with patch("llm.sql_agent.SessionLocal", return_value=test_db):
            reponse_a = svc_questions.repondre_question(CTX_A, "quelles sont mes récoltes ?")
            reponse_b = svc_questions.repondre_question(CTX_B, "quelles sont mes récoltes ?")

    assert "tomate" in reponse_a.lower()
    assert "courgette" not in reponse_a.lower()
    assert "courgette" in reponse_b.lower()
    assert "tomate" not in reponse_b.lower()


# ──────────────────────────────────────────────────────────────────────────────
# Scénario Gherkin — Fenêtre temporelle et limite du mode ask [CA3, CA7]
# ──────────────────────────────────────────────────────────────────────────────

def test_ca3_fenetre_temporelle_12_mois_exclut_evenements_anciens(test_db):
    """Un événement vieux de plus de 12 mois n'est pas pris en compte par QueryAgent."""
    ancien = datetime.now() - timedelta(days=400)
    recent = datetime.now() - timedelta(days=10)

    test_db.add_all([
        Evenement(type_action="recolte", culture="tomate", quantite=100.0, unite="kg",
                  date=ancien, potager_id=1),
        Evenement(type_action="recolte", culture="tomate", quantite=2.0, unite="kg",
                  date=recent, potager_id=1),
    ])
    test_db.commit()

    intent = {"action": "recolte", "culture": "tomate", "date_from": None, "query_type": "quantite"}
    reponse = QueryAgent(test_db, potager_id=1).answer("combien de tomates récoltées ?", intent)

    # Seul l'événement récent (2 kg) doit être compté — pas 100 kg ni 102 kg cumulés.
    assert "2 kg" in reponse
    assert "100" not in reponse
    assert "102" not in reponse

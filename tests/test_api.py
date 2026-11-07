import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.db import Base, SessionLocal
from database.models import Evenement, CultureConfig
from app.api.main import app, get_current_user_ctx
from app.services.context import default_context


@pytest.fixture
def client(test_db):
    """Client de test FastAPI avec DB mockée."""
    # Ajouter des données de test
    test_db.add(CultureConfig(nom="tomate", type_organe_recolte="reproducteur", description_agronomique="Fruit"))
    test_db.add(CultureConfig(nom="salade", type_organe_recolte="végétatif", description_agronomique="Feuille"))
    test_db.commit()

    def override_get_db():
        return test_db

    app.dependency_overrides[get_current_user_ctx] = default_context
    with patch('llm.rag.add_to_rag', MagicMock()), \
         patch('app.api.main.SessionLocal', return_value=test_db):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.pop(get_current_user_ctx, None)


class TestAPI:
    """Tests pour les endpoints API."""

    def test_get_cultures(self, client, test_db):
        """Test GET /cultures retourne la liste des cultures configurées."""
        response = client.get("/cultures")
        assert response.status_code == 200
        data = response.json()
        assert "cultures" in data
        assert data["total"] >= 2
        assert any(c["nom"] == "tomate" and c["type_organe_recolte"] == "reproducteur" for c in data["cultures"])
        assert any(c["nom"] == "salade" and c["type_organe_recolte"] == "végétatif" for c in data["cultures"])

    def test_creation_evenement_herite_type_organe_recolte(self, client, test_db):
        """[US-274] Le service d'enregistrement (autrefois derrière POST /parse) hérite le type_organe_recolte de culture_config."""
        from app.services import evenements as svc_evenements

        svc_evenements.creer_evenement_depuis_parse(
            test_db, default_context(),
            {"action": "plantation", "culture": "tomate", "quantite": 5, "unite": "plants"},
            "J'ai planté 5 tomates",
        )
        event = test_db.query(Evenement).filter(Evenement.culture == "tomate").first()
        assert event is not None
        assert event.type_organe_recolte == "reproducteur"

    def test_creation_evenement_culture_inconnue_sans_type(self, client, test_db):
        """[US-274] Une culture inconnue de culture_config ne reçoit pas de type_organe_recolte."""
        from app.services import evenements as svc_evenements

        svc_evenements.creer_evenement_depuis_parse(
            test_db, default_context(),
            {"action": "plantation", "culture": "inconnue", "quantite": 3, "unite": "plants"},
            "J'ai planté 3 inconnues",
        )
        event = test_db.query(Evenement).filter(Evenement.culture == "inconnue").first()
        assert event is not None
        assert event.type_organe_recolte is None

    def test_health_endpoint(self, client):
        """Test GET /health fonctionne."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
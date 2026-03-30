import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.db import Base, SessionLocal
from database.models import Evenement, CultureConfig
from main import app


@pytest.fixture
def client(test_db):
    """Client de test FastAPI avec DB mockée."""
    # Ajouter des données de test
    test_db.add(CultureConfig(nom="tomate", type_organe_recolte="reproducteur", description_agronomique="Fruit"))
    test_db.add(CultureConfig(nom="salade", type_organe_recolte="végétatif", description_agronomique="Feuille"))
    test_db.commit()
    
    def override_get_db():
        return test_db
    
    with patch('llm.rag.add_to_rag', MagicMock()), \
         patch('main.SessionLocal', return_value=test_db):
        with TestClient(app) as c:
            yield c


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

    @patch('main.parse_commande')
    @patch('llm.rag.add_to_rag')
    def test_parse_inherits_type_organe_recolte(self, mock_rag, mock_parse, client, test_db):
        """Test que POST /parse hérite automatiquement le type_organe_recolte depuis culture_config."""
        # Mock du parsing Groq
        mock_parse.return_value = [{
            "action": "plantation",
            "culture": "tomate",
            "quantite": 5,
            "unite": "plants"
        }]
        
        response = client.post("/parse", json={"texte": "J'ai planté 5 tomates"})
        assert response.status_code == 200
        
        # Vérifier que l'événement a été créé avec le bon type
        event = test_db.query(Evenement).filter(Evenement.culture == "tomate").first()
        assert event is not None
        assert event.type_organe_recolte == "reproducteur"

    @patch('main.parse_commande')
    @patch('llm.rag.add_to_rag')
    def test_parse_unknown_culture_no_type(self, mock_rag, mock_parse, client, test_db):
        """Test que POST /parse ne définit pas type_organe_recolte pour culture inconnue."""
        mock_parse.return_value = [{
            "action": "plantation",
            "culture": "inconnue",
            "quantite": 3,
            "unite": "plants"
        }]
        
        response = client.post("/parse", json={"texte": "J'ai planté 3 inconnues"})
        assert response.status_code == 200
        
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
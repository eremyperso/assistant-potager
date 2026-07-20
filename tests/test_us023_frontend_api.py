"""
[US-023] Tests — Contrat API FastAPI consommé par le frontend dashboard.

Stratégie : mock des fonctions utilitaires (importées dans le corps des endpoints)
et de SessionLocal via patch ciblé sur main.py.
"""
import pytest
from unittest.mock import MagicMock, patch, call
from fastapi.testclient import TestClient

MOCK_STOCK = [{"culture": "tomate", "nb_plants": 6, "type_organe": "reproducteur"}]
MOCK_GODETS_DICT = {}  # vide → pas de godets en attente


def _db():
    """Session DB minimale pour les endpoints qui font des requêtes directes."""
    db = MagicMock()
    db.query.return_value.count.return_value = 42
    db.query.return_value.filter.return_value.count.return_value = 0
    db.query.return_value.filter.return_value.first.return_value = (0, 0)  # arrosages (nb, duree)
    db.query.return_value.filter.return_value.all.return_value = []
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    db.query.return_value.order_by.return_value.all.return_value = []
    db.query.return_value.all.return_value = []
    db.query.return_value.group_by.return_value.all.return_value = []
    db.query.return_value.filter.return_value.group_by.return_value.all.return_value = []
    return db


@pytest.fixture
def app_client():
    from main import app, get_current_user_ctx
    from app.services.context import default_context
    app.dependency_overrides[get_current_user_ctx] = default_context
    with (
        patch("main.SessionLocal", return_value=_db()),
        patch("utils.stock.calcul_stock_cultures",   return_value=MOCK_STOCK),
        patch("utils.stock.format_stock_stats_json", return_value=MOCK_STOCK),
        patch("utils.stock.calcul_godets",           return_value=MOCK_GODETS_DICT),
    ):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.pop(get_current_user_ctx, None)


# ─── CA1 : /health → 200 avec status, version, date ─────────────────────────

def test_us023_ca1_health_retourne_200(app_client):
    """CA1 — GET /health retourne status=ok, version, date."""
    resp = app_client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "date" in body


# ─── CA2 : /stats → 4 clés attendues par le frontend ────────────────────────

def test_us023_ca2_stats_retourne_structure_complete(app_client):
    """CA2 — GET /stats retourne total_evenements, stock_par_culture, godets, semis_pleine_terre."""
    resp = app_client.get("/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert "total_evenements"   in body
    assert "stock_par_culture"  in body
    assert "godets"             in body
    assert "semis_pleine_terre" in body
    assert isinstance(body["stock_par_culture"],  list)
    assert isinstance(body["godets"],             list)
    assert isinstance(body["semis_pleine_terre"], list)


# ─── CA3 : /godets → format US-026 (en_attente + tout_plante + total) ────────

def test_us023_ca3_godets_retourne_dict(app_client):
    """CA3 — GET /godets retourne en_attente, tout_plante et total [US-026]."""
    resp = app_client.get("/godets")
    assert resp.status_code == 200
    body = resp.json()
    assert "en_attente"  in body
    assert "tout_plante" in body
    assert "total"       in body
    assert isinstance(body["en_attente"], list)
    assert isinstance(body["tout_plante"], list)


# ─── CA4 : /historique → accepte ?limit et ?culture ─────────────────────────

def test_us023_ca4_historique_retourne_200(app_client):
    """CA4 — GET /historique?limit=20 retourne 200."""
    assert app_client.get("/historique?limit=20").status_code == 200


def test_us023_ca4_historique_filtre_culture(app_client):
    """CA4 — GET /historique?culture=tomate retourne 200."""
    assert app_client.get("/historique?culture=tomate&limit=5").status_code == 200


# ─── CA5 : /cultures → liste pour le sélecteur Stats ────────────────────────

def test_us023_ca5_cultures_retourne_liste(app_client):
    """CA5 — GET /cultures retourne {cultures: [...], total: int}."""
    resp = app_client.get("/cultures")
    assert resp.status_code == 200
    body = resp.json()
    assert "cultures" in body
    assert isinstance(body["cultures"], list)
    assert "total" in body


# ─── CA6 : CORS → Origin Vite dev acceptée ───────────────────────────────────

def test_us023_ca6_cors_origin_dev_accepte(app_client):
    """CA6 — CORS autorise http://localhost:3000 (dev Vite)."""
    resp = app_client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert resp.status_code == 200
    assert "access-control-allow-origin" in resp.headers


# ─── Edge : route inconnue → 404 ─────────────────────────────────────────────

def test_us023_edge_route_inconnue_404(app_client):
    """Edge — Route inexistante retourne 404 sans crash."""
    assert app_client.get("/inexistant").status_code == 404

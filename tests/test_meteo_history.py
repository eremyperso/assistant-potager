"""
tests/test_meteo_history.py — Tests unitaires pour fetch_meteo_history()
et le endpoint GET /meteo/history.
"""
import pytest
import requests as req_module
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from utils.meteo import fetch_meteo_history, METEO_LATITUDE, METEO_LONGITUDE, METEO_TIMEZONE

# ── Fixture : réponse Open-Meteo simulée ─────────────────────────────────────

MOCK_ARCHIVE_RESPONSE = {
    "daily": {
        "time"               : ["2026-06-01", "2026-06-02", "2026-06-03"],
        "temperature_2m_max" : [24.3, 20.0, 19.6],
        "temperature_2m_min" : [12.8, 14.1, 12.5],
        "precipitation_sum"  : [0.0, 18.5, 1.6],
        "weathercode"        : [3, 63, 53],
    }
}


def _mock_response(data: dict) -> MagicMock:
    m = MagicMock()
    m.json.return_value = data
    m.raise_for_status.return_value = None
    return m


# ── Tests fetch_meteo_history ─────────────────────────────────────────────────

def test_fetch_meteo_history_retourne_liste():
    """Résultat est une liste non vide."""
    with patch("utils.meteo.requests.get", return_value=_mock_response(MOCK_ARCHIVE_RESPONSE)):
        result = fetch_meteo_history(days=3)
    assert isinstance(result, list)
    assert len(result) == 3


def test_fetch_meteo_history_structure_jour():
    """Chaque jour contient tous les champs attendus."""
    with patch("utils.meteo.requests.get", return_value=_mock_response(MOCK_ARCHIVE_RESPONSE)):
        result = fetch_meteo_history(days=3)
    jour = result[0]
    assert jour["date"]           == "2026-06-01"
    assert jour["temp_max"]       == 24.3
    assert jour["temp_min"]       == 12.8
    assert jour["precipitations"] == 0.0
    assert jour["wmo_code"]       == 3
    assert "emoji" in jour
    assert "label" in jour


def test_fetch_meteo_history_wmo_traduit():
    """Le code WMO 63 est traduit en pluie modérée."""
    with patch("utils.meteo.requests.get", return_value=_mock_response(MOCK_ARCHIVE_RESPONSE)):
        result = fetch_meteo_history(days=3)
    jour_pluie = result[1]  # weathercode=63
    assert jour_pluie["emoji"] == "🌧️"
    assert "Pluie modérée" in jour_pluie["label"]


def test_fetch_meteo_history_coordonnees_defaut():
    """Sans arguments, utilise les coordonnées du potager configuré."""
    with patch("utils.meteo.requests.get", return_value=_mock_response(MOCK_ARCHIVE_RESPONSE)) as mock_get:
        fetch_meteo_history()
    params = mock_get.call_args[1]["params"]
    assert params["latitude"]  == METEO_LATITUDE
    assert params["longitude"] == METEO_LONGITUDE
    assert params["timezone"]  == METEO_TIMEZONE


def test_fetch_meteo_history_coordonnees_custom():
    """Les coordonnées personnalisées sont transmises à l'API."""
    with patch("utils.meteo.requests.get", return_value=_mock_response(MOCK_ARCHIVE_RESPONSE)) as mock_get:
        fetch_meteo_history(lat=43.296, lon=5.381, days=3, timezone="Europe/Paris")
    params = mock_get.call_args[1]["params"]
    assert params["latitude"]  == 43.296
    assert params["longitude"] == 5.381


def test_fetch_meteo_history_plage_dates():
    """start_date et end_date couvrent bien `days` jours."""
    from datetime import date, timedelta
    with patch("utils.meteo.requests.get", return_value=_mock_response(MOCK_ARCHIVE_RESPONSE)) as mock_get:
        fetch_meteo_history(days=30)
    params    = mock_get.call_args[1]["params"]
    start     = date.fromisoformat(params["start_date"])
    end       = date.fromisoformat(params["end_date"])
    assert (end - start).days == 29          # 30 jours inclusifs → écart de 29
    assert end == date.today() - timedelta(days=1)


def test_fetch_meteo_history_erreur_reseau():
    """Retourne None si l'API est inaccessible."""
    with patch("utils.meteo.requests.get", side_effect=req_module.RequestException("timeout")):
        result = fetch_meteo_history(days=3)
    assert result is None


def test_fetch_meteo_history_reponse_malformee():
    """Retourne None si la réponse ne contient pas la clé 'daily'."""
    with patch("utils.meteo.requests.get", return_value=_mock_response({"error": True})):
        result = fetch_meteo_history(days=3)
    assert result is None


# ── Tests endpoint /meteo/history ────────────────────────────────────────────

@pytest.fixture
def client():
    from main import app
    return TestClient(app)


def test_endpoint_meteo_history_ok(client):
    """Le endpoint retourne 200 avec la structure attendue."""
    with patch("utils.meteo.requests.get", return_value=_mock_response(MOCK_ARCHIVE_RESPONSE)):
        resp = client.get("/meteo/history?days=30")
    assert resp.status_code == 200
    data = resp.json()
    assert "jours" in data
    assert "meta"  in data
    assert len(data["jours"]) == 3
    assert data["meta"]["days"] == 30


def test_endpoint_meteo_history_coordonnees_custom(client):
    """Le endpoint transmet lat/lon à fetch_meteo_history."""
    with patch("utils.meteo.requests.get", return_value=_mock_response(MOCK_ARCHIVE_RESPONSE)) as mock_get:
        resp = client.get("/meteo/history?days=30&lat=43.296&lon=5.381")
    assert resp.status_code == 200
    params = mock_get.call_args[1]["params"]
    assert params["latitude"]  == pytest.approx(43.296)
    assert params["longitude"] == pytest.approx(5.381)


def test_endpoint_meteo_history_erreur_amont(client):
    """Retourne 502 si Open-Meteo est inaccessible."""
    with patch("utils.meteo.requests.get", side_effect=req_module.RequestException("down")):
        resp = client.get("/meteo/history?days=30")
    assert resp.status_code == 502


def test_endpoint_meteo_history_days_hors_bornes(client):
    """days < 7 ou > 365 → 422 validation error."""
    resp = client.get("/meteo/history?days=3")   # < ge=7
    assert resp.status_code == 422

    with patch("utils.meteo.requests.get", return_value=_mock_response(MOCK_ARCHIVE_RESPONSE)):
        resp2 = client.get("/meteo/history?days=400")  # > le=365
    assert resp2.status_code == 422

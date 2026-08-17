"""
tests/test_us075_meteo_web.py — [US-075] Météo web personnalisée sur la
localisation réelle du potager
------------------------------------------------------------------------------
Couvre CA1 (fetch_meteo généralisée lat/lon/timezone), CA2 (prévision 5
jours), CA3/CA4 (GET /meteo, avec/sans localisation) et CA5 (non-régression :
le bot Telegram appelle toujours fetch_meteo() sans argument et obtient
exactement les mêmes clés qu'avant cette US).
"""
import pytest
import requests as req_module
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import auth as svc_auth
from app.services import potagers as svc_potagers
from database.db import Base
from utils.meteo import fetch_meteo, format_meteo_commentaire, METEO_LATITUDE, METEO_LONGITUDE, METEO_TIMEZONE

# ── Fixture : réponse Open-Meteo forecast simulée (6 jours) ─────────────────

_HOURLY_TIMES = [f"2026-06-01T{h:02d}:00" for h in range(24)]

MOCK_FORECAST_RESPONSE = {
    "current": {
        "temperature_2m": 18.4,
        "apparent_temperature": 17.1,
        "relative_humidity_2m": 62,
        "wind_speed_10m": 12.3,
        "weather_code": 2,
    },
    "hourly": {
        "time"                     : _HOURLY_TIMES,
        "temperature_2m"           : [10.0 + h * 0.3 for h in range(24)],
        "precipitation_probability": [5] * 24,
        "precipitation"            : [0.0] * 24,
        "windspeed_10m"            : [10.0] * 24,
        "weathercode"              : [2] * 24,
    },
    "daily": {
        "time"                          : ["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04", "2026-06-05", "2026-06-06"],
        "weathercode"                   : [2, 61, 3, 0, 1, 80],
        "temperature_2m_max"            : [22.0, 19.5, 20.1, 24.0, 23.2, 21.0],
        "temperature_2m_min"            : [12.0, 13.1, 11.5, 12.8, 13.0, 12.2],
        "precipitation_sum"             : [0.0, 4.2, 0.0, 0.0, 0.0, 1.1],
        "precipitation_probability_max" : [10, 60, 20, 5, 15, 40],
        "windspeed_10m_max"             : [15.0, 22.0, 18.0, 10.0, 12.0, 25.0],
        "sunrise"                       : [f"2026-06-0{i}T05:5{9 - i}" for i in range(1, 7)],
        "sunset"                        : [f"2026-06-0{i}T21:3{i}" for i in range(1, 7)],
    },
}


def _mock_response(data: dict) -> MagicMock:
    m = MagicMock()
    m.json.return_value = data
    m.raise_for_status.return_value = None
    return m


# ── CA1 — Paramètres lat/lon/timezone ───────────────────────────────────────

def test_ca1_fetch_meteo_coordonnees_defaut():
    """Sans arguments, utilise les coordonnées globales du bot (non-régression)."""
    with patch("utils.meteo.requests.get", return_value=_mock_response(MOCK_FORECAST_RESPONSE)) as mock_get:
        fetch_meteo()
    params = mock_get.call_args[1]["params"]
    assert params["latitude"]  == METEO_LATITUDE
    assert params["longitude"] == METEO_LONGITUDE
    assert params["timezone"]  == METEO_TIMEZONE


def test_ca1_fetch_meteo_coordonnees_custom():
    with patch("utils.meteo.requests.get", return_value=_mock_response(MOCK_FORECAST_RESPONSE)) as mock_get:
        fetch_meteo(lat=43.296, lon=5.381, timezone="Europe/Paris")
    params = mock_get.call_args[1]["params"]
    assert params["latitude"]  == 43.296
    assert params["longitude"] == 5.381


# ── CA2 — Prévision 5 jours ──────────────────────────────────────────────────

def test_ca2_fetch_meteo_previsions_cinq_jours():
    with patch("utils.meteo.requests.get", return_value=_mock_response(MOCK_FORECAST_RESPONSE)):
        result = fetch_meteo()
    assert len(result["previsions"]) == 5
    premier = result["previsions"][0]
    assert premier["date"] == "2026-06-02"
    assert premier["wmo_code"] == 61
    assert premier["temp_max"] == 19.5
    assert premier["temp_min"] == 13.1
    assert "Pluie" in premier["label"]


def test_fetch_meteo_instantane_courant():
    with patch("utils.meteo.requests.get", return_value=_mock_response(MOCK_FORECAST_RESPONSE)):
        result = fetch_meteo()
    assert result["temp_actuelle"]   == 18.4
    assert result["ressenti"]        == 17.1
    assert result["humidite"]        == 62
    assert result["vent_actuel_kmh"] == 12.3


def test_fetch_meteo_current_absent_ne_leve_pas():
    """Une réponse Open-Meteo dégradée sans bloc `current` ne casse pas l'appel."""
    reponse_sans_current = {k: v for k, v in MOCK_FORECAST_RESPONSE.items() if k != "current"}
    with patch("utils.meteo.requests.get", return_value=_mock_response(reponse_sans_current)):
        result = fetch_meteo()
    assert result is not None
    assert result["temp_actuelle"] is None
    assert result["humidite"] is None


# ── CA5 — Non-régression bot Telegram ───────────────────────────────────────

def test_ca5_fetch_meteo_conserve_toutes_les_cles_dorigine():
    cles_dorigine = {
        "wmo_code", "emoji", "label", "temp_min", "temp_max", "temp_matin", "temp_aprem",
        "precipitations", "proba_pluie", "proba_matin", "proba_aprem", "vent_max_kmh",
        "lever_soleil", "coucher_soleil", "conseil", "date",
    }
    with patch("utils.meteo.requests.get", return_value=_mock_response(MOCK_FORECAST_RESPONSE)):
        result = fetch_meteo()
    assert cles_dorigine.issubset(result.keys())
    # format_meteo_commentaire (utilisé par le bot) ne lit que les clés d'origine
    commentaire = format_meteo_commentaire(result)
    assert isinstance(commentaire, str) and commentaire


def test_ca5_fetch_meteo_appel_sans_argument_reste_valide():
    """Le job 5h / la commande /meteo appellent fetch_meteo() sans argument."""
    with patch("utils.meteo.requests.get", return_value=_mock_response(MOCK_FORECAST_RESPONSE)):
        result = fetch_meteo()
    assert result["temp_matin"] == pytest.approx(12.4)
    assert result["temp_aprem"] == pytest.approx(14.2)


def test_fetch_meteo_erreur_reseau():
    with patch("utils.meteo.requests.get", side_effect=req_module.RequestException("timeout")):
        result = fetch_meteo()
    assert result is None


# ── CA3, CA4 — Endpoint GET /meteo ───────────────────────────────────────────

@pytest.fixture
def _auth_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def app_client(_auth_engine, monkeypatch):
    import main
    TestSessionLocal = sessionmaker(bind=_auth_engine)
    monkeypatch.setattr(main, "SessionLocal", TestSessionLocal)
    main.app.state.limiter.reset()
    with TestClient(main.app) as c:
        yield c


def _creer_compte_avec_potager(SessionLocal, ville=None, latitude=None, longitude=None):
    db = SessionLocal()
    user = svc_auth.inscrire_utilisateur(db, "jardinier@example.com", "motdepasse123")
    potager = svc_potagers.creer_potager(db, user.id, "Jardin", ville=ville, latitude=latitude, longitude=longitude)
    headers = {"Authorization": f"Bearer {svc_auth.creer_access_token(user.id)}"}
    db.close()
    return headers, potager.id


def test_ca4_meteo_potager_sans_localisation(app_client, _auth_engine):
    """Scénario Gherkin : potager sans localisation → localisation_manquante=true."""
    SessionLocal = sessionmaker(bind=_auth_engine)
    headers, _ = _creer_compte_avec_potager(SessionLocal)

    # L'API Open-Meteo ne doit jamais être appelée pour un potager non localisé.
    with patch("utils.meteo.requests.get", side_effect=AssertionError("ne doit pas être appelé")):
        resp = app_client.get("/meteo", headers=headers)

    assert resp.status_code == 200
    assert resp.json() == {"localisation_manquante": True}


def test_ca3_meteo_potager_localise(app_client, _auth_engine):
    """Scénario Gherkin : météo d'un potager localisé."""
    SessionLocal = sessionmaker(bind=_auth_engine)
    headers, _ = _creer_compte_avec_potager(
        SessionLocal, ville="Vitry-sur-Seine", latitude=48.787, longitude=2.393,
    )

    with patch("utils.meteo.requests.get", return_value=_mock_response(MOCK_FORECAST_RESPONSE)) as mock_get:
        resp = app_client.get("/meteo", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["localisation_manquante"] is False
    assert body["ville"] == "Vitry-sur-Seine"
    assert len(body["previsions"]) == 5

    params = mock_get.call_args[1]["params"]
    assert params["latitude"]  == pytest.approx(48.787)
    assert params["longitude"] == pytest.approx(2.393)


def test_meteo_potager_erreur_amont(app_client, _auth_engine):
    SessionLocal = sessionmaker(bind=_auth_engine)
    headers, _ = _creer_compte_avec_potager(SessionLocal, ville="Lyon", latitude=45.764, longitude=4.836)

    with patch("utils.meteo.requests.get", side_effect=req_module.RequestException("down")):
        resp = app_client.get("/meteo", headers=headers)

    assert resp.status_code == 502

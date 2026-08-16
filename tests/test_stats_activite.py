"""
tests/test_stats_activite.py
------------------------------
[US_Stats_activite_potager] Heatmap d'activité quotidienne.

Couvre :
  - calcul_activite_quotidienne() : agrégation par jour, filtrage par année, date_ref
  - GET /stats/activite           : structure JSON, paramètres annee/date_ref
"""
from __future__ import annotations

import pytest
from datetime import date, datetime
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from database.db import Base
from database.models import Evenement
from utils.stock import calcul_activite_quotidienne


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


def _ev(db, type_action, date_, culture="tomate"):
    e = Evenement(type_action=type_action, culture=culture, quantite=1, unite="plants", date=date_)
    db.add(e)
    db.flush()
    return e


@pytest.fixture
def client():
    from main import app, get_current_user_ctx
    from app.services.context import default_context
    app.dependency_overrides[get_current_user_ctx] = default_context
    with patch("main.SessionLocal", return_value=MagicMock()):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.pop(get_current_user_ctx, None)


# ── calcul_activite_quotidienne ─────────────────────────────────────────────

def test_activite_agrege_par_jour(db_session):
    """Plusieurs événements le même jour sont comptés ensemble."""
    _ev(db_session, "plantation", datetime(2026, 3, 10, 9, 0))
    _ev(db_session, "arrosage",   datetime(2026, 3, 10, 18, 0))
    _ev(db_session, "recolte",    datetime(2026, 3, 11, 8, 0))
    result = calcul_activite_quotidienne(db_session, 2026)
    assert result["2026-03-10"] == 2
    assert result["2026-03-11"] == 1


def test_activite_filtre_par_annee(db_session):
    """Les événements hors de l'année demandée sont exclus."""
    _ev(db_session, "plantation", datetime(2025, 12, 31, 9, 0))
    _ev(db_session, "plantation", datetime(2026, 1, 1, 9, 0))
    result = calcul_activite_quotidienne(db_session, 2026)
    assert "2025-12-31" not in result
    assert result["2026-01-01"] == 1


def test_activite_sans_evenements(db_session):
    """Aucun événement → dict vide, pas d'erreur."""
    assert calcul_activite_quotidienne(db_session, 2026) == {}


def test_activite_date_ref_plafonne_la_borne(db_session):
    """[US-030] date_ref plafonne la borne haute — événements après sont exclus."""
    _ev(db_session, "plantation", datetime(2026, 3, 10, 9, 0))
    _ev(db_session, "plantation", datetime(2026, 3, 20, 9, 0))
    result = calcul_activite_quotidienne(db_session, 2026, date_ref=date(2026, 3, 15))
    assert "2026-03-10" in result
    assert "2026-03-20" not in result


# ── Endpoint GET /stats/activite ────────────────────────────────────────────

def test_endpoint_activite_structure(client):
    with patch("utils.stock.calcul_activite_quotidienne", return_value={"2026-03-10": 2}):
        resp = client.get("/stats/activite?annee=2026")
    assert resp.status_code == 200
    data = resp.json()
    assert "annee" in data
    assert "jours" in data
    assert "total_actions" in data
    assert "jours_actifs" in data
    assert data["annee"] == 2026
    assert data["total_actions"] == 2
    assert data["jours_actifs"] == 1


def test_endpoint_activite_annee_par_defaut(client):
    """Sans paramètre annee, utilise l'année courante."""
    with patch("utils.stock.calcul_activite_quotidienne", return_value={}):
        resp = client.get("/stats/activite")
    assert resp.status_code == 200
    assert resp.json()["annee"] == date.today().year

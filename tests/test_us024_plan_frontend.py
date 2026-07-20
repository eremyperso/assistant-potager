"""
[US-024] Tests — Endpoint GET /plan pour le dashboard frontend.

Vérifie : structure de réponse, parcelles libres incluses, cultures listées,
occupation_pct calculé, gestion erreur.
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from database.models import Parcelle


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _parcelle(nom, exposition=None, superficie=None):
    p = MagicMock(spec=Parcelle)
    p.nom          = nom
    p.exposition   = exposition
    p.superficie_m2 = superficie
    p.actif        = True
    return p


MOCK_PARCELLES = [
    _parcelle("Centrale", exposition="Plein soleil", superficie=4.0),
    _parcelle("Mi-ombre"),
]

MOCK_OCCUPATION = {
    "Centrale": [
        {"culture": "tomate", "variete": "Cœur de bœuf", "nb_plants": 6.0,
         "type_organe": "reproducteur", "unite": "plants"},
        {"culture": "basilic", "variete": None, "nb_plants": 4.0,
         "type_organe": "végétatif", "unite": "pieds"},
    ],
    # Mi-ombre absente → libre
}


@pytest.fixture
def client():
    from main import app, get_current_user_ctx
    from app.services.context import default_context
    app.dependency_overrides[get_current_user_ctx] = default_context
    with (
        patch("main.SessionLocal",              return_value=MagicMock()),
        patch("utils.parcelles.get_all_parcelles",          return_value=MOCK_PARCELLES),
        patch("utils.parcelles.calcul_occupation_parcelles", return_value=MOCK_OCCUPATION),
    ):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.pop(get_current_user_ctx, None)


# ── CA1 : /plan retourne 200 + clés parcelles/total ──────────────────────────

def test_us024_ca1_plan_retourne_structure(client):
    """CA1 — GET /plan retourne {parcelles: [...], total: int}."""
    resp = client.get("/plan")
    assert resp.status_code == 200
    body = resp.json()
    assert "parcelles" in body
    assert "total" in body
    assert body["total"] == 2


# ── CA2 : chaque parcelle liste ses cultures ──────────────────────────────────

def test_us024_ca2_cultures_listees(client):
    """CA2 — Centrale a 2 cultures avec culture, variete, nb_plants, type_organe."""
    body = client.get("/plan").json()
    centrale = next(p for p in body["parcelles"] if p["nom"] == "Centrale")
    assert len(centrale["cultures"]) == 2
    c0 = centrale["cultures"][0]
    assert "culture"    in c0
    assert "variete"    in c0
    assert "nb_plants"  in c0
    assert "type_organe" in c0


# ── CA3 : badge type_organe présent ──────────────────────────────────────────

def test_us024_ca3_type_organe_present(client):
    """CA3 — type_organe retourné pour chaque culture (végétatif/reproducteur)."""
    body = client.get("/plan").json()
    centrale = next(p for p in body["parcelles"] if p["nom"] == "Centrale")
    types = {c["type_organe"] for c in centrale["cultures"]}
    assert "reproducteur" in types
    assert "végétatif"    in types


# ── CA4 : parcelle libre incluse avec cultures=[] ─────────────────────────────

def test_us024_ca4_parcelle_libre_incluse(client):
    """CA4 — Mi-ombre (sans culture) est retournée avec cultures=[]."""
    body = client.get("/plan").json()
    miombre = next((p for p in body["parcelles"] if p["nom"] == "Mi-ombre"), None)
    assert miombre is not None
    assert miombre["cultures"] == []


# ── CA5 : occupation_pct calculé si superficie connue ────────────────────────

def test_us024_ca5_occupation_pct_calcule(client):
    """CA5 — occupation_pct est un entier entre 0 et 100 si superficie_m2 connue."""
    body = client.get("/plan").json()
    centrale = next(p for p in body["parcelles"] if p["nom"] == "Centrale")
    assert centrale["occupation_pct"] is not None
    assert 0 <= centrale["occupation_pct"] <= 100


def test_us024_ca5_occupation_pct_null_sans_superficie(client):
    """CA5 — occupation_pct est None si superficie_m2 non renseignée."""
    body = client.get("/plan").json()
    miombre = next(p for p in body["parcelles"] if p["nom"] == "Mi-ombre")
    assert miombre["occupation_pct"] is None


# ── CA6 : état vide — aucune parcelle ────────────────────────────────────────

def test_us024_ca6_aucune_parcelle(client):
    """CA6 — Aucune parcelle → parcelles=[], total=0, pas d'erreur."""
    from main import app
    with (
        patch("main.SessionLocal",              return_value=MagicMock()),
        patch("utils.parcelles.get_all_parcelles",          return_value=[]),
        patch("utils.parcelles.calcul_occupation_parcelles", return_value={}),
    ):
        with TestClient(app) as c:
            body = c.get("/plan").json()
    assert body["parcelles"] == []
    assert body["total"] == 0


# ── Edge : exposition et superficie inclus dans la réponse ───────────────────

def test_us024_edge_meta_parcelle(client):
    """Edge — exposition et superficie_m2 retournés dans la réponse."""
    body = client.get("/plan").json()
    centrale = next(p for p in body["parcelles"] if p["nom"] == "Centrale")
    assert centrale["exposition"]   == "Plein soleil"
    assert centrale["superficie_m2"] == 4.0

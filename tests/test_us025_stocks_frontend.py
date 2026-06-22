"""
[US-025] Tests — Endpoint GET /stats pour la vue Stocks cultures frontend.

Vérifie : structure de réponse, séparation végétatif/reproducteur, champs par culture,
données graphe, état vide, erreur API.

Note : CA5 (filtre texte client) et CA3 (rendu graphe) sont validés côté frontend
uniquement — non testables automatiquement en pytest.
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from utils.stock import StockCulture


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _stock(culture, type_organe, plantes=10, perdus=0, recoltes=0.0, unite="plants"):
    """Crée un StockCulture mocké.

    [US-036] `recoltes` alimente le pool "pièces" (recoltes_total, stock)
    pour le végétatif, ou le pool "poids" (rendement_total) pour le
    reproducteur — jamais les deux à la fois, conformément au garde-fou CA6.
    """
    s = MagicMock(spec=StockCulture)
    s.culture        = culture
    s.type_organe    = type_organe
    s.plants_plantes = plantes
    s.plants_perdus  = perdus
    s.unite          = unite
    s.is_reproducteur = type_organe == "reproducteur"
    if type_organe == "reproducteur":
        s.stock_plants      = plantes - perdus
        s.recoltes_total    = 0.0
        s.unite_recolte     = "plants"
        s.nb_recoltes       = 0
        s.rendement_total   = recoltes
        s.unite_rendement   = "kg"
        s.nb_recoltes_poids = 2 if recoltes else 0
    else:
        s.stock_plants      = plantes - perdus - recoltes
        s.recoltes_total    = recoltes
        s.unite_recolte     = "plants"
        s.nb_recoltes       = 2 if recoltes else 0
        s.rendement_total   = 0.0
        s.unite_rendement   = ""
        s.nb_recoltes_poids = 0
    return s


MOCK_STOCKS = {
    "salade": _stock("salade", "végétatif", plantes=25, perdus=2),
    "tomate": _stock("tomate", "reproducteur", plantes=14, recoltes=1.2),
}


@pytest.fixture
def client():
    from main import app
    with (
        patch("main.SessionLocal",                  return_value=MagicMock()),
        patch("utils.stock.calcul_stock_cultures",  return_value=MOCK_STOCKS),
        patch("utils.stock.calcul_godets",          return_value={}),
        patch("main.Evenement",                     new_callable=MagicMock),
    ):
        with TestClient(app) as c:
            yield c


@pytest.fixture
def client_vide():
    from main import app
    with (
        patch("main.SessionLocal",                  return_value=MagicMock()),
        patch("utils.stock.calcul_stock_cultures",  return_value={}),
        patch("utils.stock.calcul_godets",          return_value={}),
        patch("main.Evenement",                     new_callable=MagicMock),
    ):
        with TestClient(app) as c:
            yield c


# ── CA1 : /stats retourne stock_par_culture avec végétatif ET reproducteur ───

def test_us025_ca1_stats_retourne_deux_types():
    """CA1 — /stats retourne des cultures végétatives et reproductrices."""
    from utils.stock import format_stock_stats_json
    result = format_stock_stats_json(MOCK_STOCKS)
    types = {e["type_organe"] for e in result}
    assert "végétatif"    in types
    assert "reproducteur" in types


# ── CA2 : champs requis présents par culture ──────────────────────────────────

def test_us025_ca2_champs_par_culture():
    """CA2 — Chaque culture expose culture, stock_plants, plants_perdus, type_organe, unite."""
    from utils.stock import format_stock_stats_json
    result = format_stock_stats_json(MOCK_STOCKS)
    for entry in result:
        assert "culture"      in entry
        assert "stock_plants" in entry
        assert "plants_perdus" in entry
        assert "type_organe"  in entry
        assert "unite"        in entry


def test_us025_ca2_reproducteur_a_rendement():
    """CA2 — Culture reproductrice expose rendement_total, unite_rendement, nb_recoltes."""
    from utils.stock import format_stock_stats_json
    result = format_stock_stats_json(MOCK_STOCKS)
    tomate = next(e for e in result if e["culture"] == "tomate")
    assert "rendement_total"  in tomate
    assert "unite_rendement"  in tomate
    assert "nb_recoltes"      in tomate


def test_us025_ca2_vegetatif_sans_rendement():
    """CA2 — Culture végétative n'expose pas de champ rendement_total."""
    from utils.stock import format_stock_stats_json
    result = format_stock_stats_json(MOCK_STOCKS)
    salade = next(e for e in result if e["culture"] == "salade")
    assert "rendement_total" not in salade


# ── CA3 : données graphe — plants_plantes et plants_perdus présents ───────────

def test_us025_ca3_donnees_graphe():
    """CA3 — plants_plantes et plants_perdus disponibles pour construire le graphe."""
    from utils.stock import format_stock_stats_json
    result = format_stock_stats_json(MOCK_STOCKS)
    for entry in result:
        assert "plants_plantes" in entry
        assert "plants_perdus"  in entry
        assert entry["plants_plantes"] >= 0
        assert entry["plants_perdus"]  >= 0


# ── CA6 : état vide ───────────────────────────────────────────────────────────

def test_us025_ca6_vide_liste_vide():
    """CA6 — Aucun stock → stock_par_culture=[]."""
    from utils.stock import format_stock_stats_json
    result = format_stock_stats_json({})
    assert result == []


def test_us025_ca6_api_retourne_200_si_vide():
    """CA6 — GET /stats retourne 200 même si aucune culture."""
    from main import app
    with (
        patch("main.SessionLocal",                  return_value=MagicMock()),
        patch("utils.stock.calcul_stock_cultures",  return_value={}),
        patch("utils.stock.calcul_godets",          return_value={}),
        patch("main.Evenement",                     new_callable=MagicMock),
    ):
        with TestClient(app) as c:
            resp = c.get("/stats")
    assert resp.status_code == 200
    assert resp.json()["stock_par_culture"] == []


# ── Pertes reflétées dans stock_plants ────────────────────────────────────────

def test_us025_pertes_deduites_stock():
    """CA2 — Pertes réduisent stock_plants pour les cultures végétatives."""
    from utils.stock import format_stock_stats_json
    salade_reel = StockCulture(
        culture="salade", unite="plants", type_organe="végétatif",
        plants_plantes=25, plants_perdus=2,
    )
    result = format_stock_stats_json({"salade": salade_reel})
    salade = result[0]
    assert salade["stock_plants"] == 23
    assert salade["plants_perdus"] == 2

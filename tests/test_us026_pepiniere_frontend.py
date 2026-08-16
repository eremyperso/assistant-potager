"""
tests/test_us026_pepiniere_frontend.py
---------------------------------------
[US-026] Vue pépinière — godets en attente de plantation

Couvre :
- CA1 : métriques résumé (total, taux_reussite exposés pour calcul frontend)
- CA2 : liste compacte par variété avec champs attendus (culture, variete, nb_plants_godets…)
- CA3 : taux_reussite + stock_residuel_godet exposés pour Progress + grand chiffre
- CA4 : cultures tout plantées absentes de en_attente
- CA5 : cultures tout plantées présentes dans tout_plante
- CA6 : réponse vide quand aucune mise_en_godet

Stratégie : mock de calcul_godets() — évite le problème de thread SQLite avec TestClient.
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from main import app, get_current_user_ctx
from app.services.context import default_context

# ── Mock data ─────────────────────────────────────────────────────────────────

# Deux variétés : courgette en attente + tomate tout plantée
_GODETS_ATTENTE = {
    "courgette (Gold Rush)": {
        "culture":              "courgette",
        "variete":              "Gold Rush",
        "nb_godets":            1,
        "nb_graines_semees":    12,
        "nb_plants_godets":     10,
        "nb_plantes":           5,
        "stock_residuel_godet": 5,
        "taux_reussite":        83,
    }
}

_GODETS_EPUISES = {
    "tomate (cerise)": {
        "culture":              "tomate",
        "variete":              "cerise",
        "nb_godets":            1,
        "nb_graines_semees":    10,
        "nb_plants_godets":     8,
        "nb_plantes":           8,
        "stock_residuel_godet": 0,
        "taux_reussite":        80,
    }
}

_GODETS_TOUS = {**_GODETS_ATTENTE, **_GODETS_EPUISES}
_GODETS_VIDES = {}


def _db():
    return MagicMock()


# ── Fixture client ─────────────────────────────────────────────────────────────

@pytest.fixture
def client_avec_godets():
    """Client avec courgette en attente + tomate tout plantée."""
    app.dependency_overrides[get_current_user_ctx] = default_context
    with (
        patch("main.SessionLocal", return_value=_db()),
        patch("utils.stock.calcul_godets", return_value=_GODETS_TOUS),
    ):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.pop(get_current_user_ctx, None)


@pytest.fixture
def client_vide():
    """Client sans aucun godet."""
    app.dependency_overrides[get_current_user_ctx] = default_context
    with (
        patch("main.SessionLocal", return_value=_db()),
        patch("utils.stock.calcul_godets", return_value=_GODETS_VIDES),
    ):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.pop(get_current_user_ctx, None)


# ──────────────────────────────────────────────────────────────────────────────
# CA6 — Pépinière vide
# ──────────────────────────────────────────────────────────────────────────────

class TestCA6PepiniereVide:
    def test_reponse_vide_sans_godet(self, client_vide) -> None:
        """CA6 — Aucun godet → en_attente=[], tout_plante=[], total=0."""
        resp = client_vide.get("/godets")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["en_attente"] == []
        assert data["tout_plante"] == []


# ──────────────────────────────────────────────────────────────────────────────
# CA2 + CA3 — Champs de la liste en_attente
# ──────────────────────────────────────────────────────────────────────────────

class TestCA2CA3ListeEnAttente:
    def test_champs_requis_presents(self, client_avec_godets) -> None:
        """CA2 — Chaque entrée en_attente contient les champs UI attendus."""
        data = client_avec_godets.get("/godets").json()
        assert data["total"] == 1
        g = data["en_attente"][0]
        assert g["culture"] == "courgette"
        assert g["variete"] == "Gold Rush"
        assert "nb_plants_godets"     in g   # CA2 : nb repiqués
        assert "nb_plantes"           in g   # CA2 : nb plantés
        assert "stock_residuel_godet" in g   # CA3 : Progress bar
        assert "taux_reussite"        in g   # CA3 : grand chiffre coloré

    def test_stock_residuel_correct(self, client_avec_godets) -> None:
        """CA3 — stock_residuel_godet = nb_plants_godets − nb_plantes."""
        g = client_avec_godets.get("/godets").json()["en_attente"][0]
        assert g["stock_residuel_godet"] == 5   # 10 godets − 5 plantés

    def test_taux_reussite_present(self, client_avec_godets) -> None:
        """CA3 — taux_reussite exposé pour grand chiffre coloré frontend."""
        g = client_avec_godets.get("/godets").json()["en_attente"][0]
        assert g["taux_reussite"] == 83


# ──────────────────────────────────────────────────────────────────────────────
# CA4 — Cultures tout plantées absentes de en_attente
# ──────────────────────────────────────────────────────────────────────────────

class TestCA4ToutPlanteAbsentEnAttente:
    def test_culture_epuisee_absente_en_attente(self, client_avec_godets) -> None:
        """CA4 — Tomate (stock=0) absente de en_attente."""
        cultures = [g["culture"] for g in client_avec_godets.get("/godets").json()["en_attente"]]
        assert "tomate" not in cultures


# ──────────────────────────────────────────────────────────────────────────────
# CA5 — Encart "Tout planté"
# ──────────────────────────────────────────────────────────────────────────────

class TestCA5ToutPlante:
    def test_culture_epuisee_dans_tout_plante(self, client_avec_godets) -> None:
        """CA5 — Tomate (stock=0) apparaît dans tout_plante."""
        tout_plante = client_avec_godets.get("/godets").json()["tout_plante"]
        assert any(c["culture"] == "tomate" for c in tout_plante)

    def test_culture_en_attente_absente_tout_plante(self, client_avec_godets) -> None:
        """CA5 — Courgette (stock>0) absente de tout_plante."""
        tout_plante = client_avec_godets.get("/godets").json()["tout_plante"]
        assert not any(c["culture"] == "courgette" for c in tout_plante)

    def test_tout_plante_contient_variete(self, client_avec_godets) -> None:
        """CA5 — tout_plante expose variete pour l'affichage de l'encart."""
        tout_plante = client_avec_godets.get("/godets").json()["tout_plante"]
        tomate = next(c for c in tout_plante if c["culture"] == "tomate")
        assert tomate["variete"] == "cerise"


# ──────────────────────────────────────────────────────────────────────────────
# CA1 — Structure de réponse globale
# ──────────────────────────────────────────────────────────────────────────────

class TestCA1Structure:
    def test_total_reflète_en_attente_seulement(self, client_avec_godets) -> None:
        """CA1 — total = nombre de variétés en attente (stock > 0 uniquement)."""
        assert client_avec_godets.get("/godets").json()["total"] == 1

    def test_structure_reponse(self, client_avec_godets) -> None:
        """CA1 — réponse contient en_attente, tout_plante, total."""
        data = client_avec_godets.get("/godets").json()
        assert "en_attente"  in data
        assert "tout_plante" in data
        assert "total"       in data

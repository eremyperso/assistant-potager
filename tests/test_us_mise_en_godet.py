"""
tests/test_us_mise_en_godet.py
-------------------------------
Tests US "Enregistrer une mise en godet avec taux de réussite germination"

CA1 : `mise_en_godet` est reconnu dans ACTION_MAP (utils/actions.py)
CA2 : Evenement a bien les colonnes `nb_graines_semees` et `nb_plants_godets`
CA3 : Le taux de réussite = nb_plants_godets / nb_graines_semees × 100 est correct
CA4 : L'action mise_en_godet ne modifie PAS le stock actif
CA5 : Le prompt LLM contient `mise_en_godet` ET les champs `nb_graines_semees` / `nb_plants_godets`
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import inspect as sa_inspect

from utils.actions import ACTION_MAP, normalize_action
from database.models import Evenement
from llm.groq_client import PARSE_PROMPT
from bot import _build_recap


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def parsed_mise_en_godet() -> dict:
    """Payload parsé typique pour une mise en godet (24 plants / 30 graines)."""
    return {
        "action": "mise_en_godet",
        "culture": "tomate",
        "variete": "cerise",
        "nb_graines_semees": 30,
        "nb_plants_godets": 24,
        "quantite": None,
        "unite": None,
        "parcelle": None,
        "date": None,
        "commentaire": None,
    }


@pytest.fixture
def mock_db_empty():
    """Session SQLAlchemy mockée sans aucun événement enregistré."""
    db = MagicMock()
    db.query.return_value.filter.return_value.filter.return_value.all.return_value = []
    return db


# ──────────────────────────────────────────────────────────────────────────────
# CA1 — ACTION_MAP reconnaît mise_en_godet et ses synonymes
# ──────────────────────────────────────────────────────────────────────────────

class TestCA1ActionMap:
    def test_ca1_mise_en_godet_present_in_action_map(self) -> None:
        """CA1 — La clé 'mise_en_godet' existe bien dans ACTION_MAP."""
        assert "mise_en_godet" in ACTION_MAP

    def test_ca1_synonyme_mis_en_godet_normalise(self) -> None:
        """CA1 — Le synonyme 'mis en godet' est normalisé vers 'mise_en_godet'."""
        # Happy path : synonyme tel que dicté vocalement
        result = normalize_action("mis en godet")
        assert result == "mise_en_godet"

    def test_ca1_synonyme_godets_normalise(self) -> None:
        """CA1 — Le synonyme 'godets' est normalisé vers 'mise_en_godet'."""
        result = normalize_action("godets")
        assert result == "mise_en_godet"

    def test_ca1_canonical_direct_normalise(self) -> None:
        """CA1 — La chaîne canonique 'mise_en_godet' est normalisée correctement."""
        # Le LLM retourne directement l'action canonique
        result = normalize_action("mise_en_godet")
        assert result == "mise_en_godet"

    def test_ca1_action_map_a_au_moins_un_synonyme(self) -> None:
        """CA1 — mise_en_godet possède au moins un synonyme dans ACTION_MAP."""
        assert len(ACTION_MAP["mise_en_godet"]) >= 1


# ──────────────────────────────────────────────────────────────────────────────
# CA2 — Evenement possède les colonnes nb_graines_semees et nb_plants_godets
# ──────────────────────────────────────────────────────────────────────────────

class TestCA2ModelColumns:
    def test_ca2_colonne_nb_graines_semees_existe(self) -> None:
        """CA2 — La colonne nb_graines_semees est déclarée sur Evenement."""
        colonnes = {c.key for c in Evenement.__table__.columns}
        assert "nb_graines_semees" in colonnes

    def test_ca2_colonne_nb_plants_godets_existe(self) -> None:
        """CA2 — La colonne nb_plants_godets est déclarée sur Evenement."""
        colonnes = {c.key for c in Evenement.__table__.columns}
        assert "nb_plants_godets" in colonnes

    def test_ca2_colonnes_nullable(self) -> None:
        """CA2 — Les deux colonnes sont nullable (optionnelles pour les autres actions)."""
        table = Evenement.__table__
        assert table.c["nb_graines_semees"].nullable is True
        assert table.c["nb_plants_godets"].nullable is True

    def test_ca2_evenement_instanciable_avec_champs_godets(self) -> None:
        """CA2 — Evenement peut être instancié avec nb_graines_semees et nb_plants_godets."""
        ev = Evenement(
            type_action="mise_en_godet",
            culture="tomate",
            nb_graines_semees=30,
            nb_plants_godets=24,
        )
        assert ev.nb_graines_semees == 30
        assert ev.nb_plants_godets == 24

    def test_ca2_evenement_champs_godets_none_par_defaut(self) -> None:
        """CA2 — Sans valeur, les champs graines/plants sont None."""
        ev = Evenement(type_action="arrosage", culture="courgette")
        assert ev.nb_graines_semees is None
        assert ev.nb_plants_godets is None


# ──────────────────────────────────────────────────────────────────────────────
# CA3 — Taux de réussite : nb_plants_godets / nb_graines_semees × 100
# ──────────────────────────────────────────────────────────────────────────────

class TestCA3TauxReussite:
    def test_ca3_taux_80_pct_gherkin(self, parsed_mise_en_godet: dict) -> None:
        """CA3 — Scénario Gherkin : 24 plants / 30 graines → 80%."""
        recap = _build_recap(parsed_mise_en_godet, event_id=42)
        assert "80%" in recap

    def test_ca3_taux_100_pct(self) -> None:
        """CA3 — 10 plants / 10 graines → 100%."""
        payload = {
            "action": "mise_en_godet",
            "culture": "poivron",
            "nb_graines_semees": 10,
            "nb_plants_godets": 10,
        }
        recap = _build_recap(payload, event_id=1)
        assert "100%" in recap

    def test_ca3_taux_arrondi(self) -> None:
        """CA3 — 2 plants / 3 graines → arrondi à 67%."""
        payload = {
            "action": "mise_en_godet",
            "culture": "aubergine",
            "nb_graines_semees": 3,
            "nb_plants_godets": 2,
        }
        recap = _build_recap(payload, event_id=2)
        assert "67%" in recap

    def test_ca3_taux_absent_si_graines_manquantes(self) -> None:
        """CA3 — Edge case : nb_graines_semees absent → pas de taux affiché."""
        payload = {
            "action": "mise_en_godet",
            "culture": "tomate",
            "nb_graines_semees": None,
            "nb_plants_godets": 24,
        }
        recap = _build_recap(payload, event_id=3)
        # Sans graines, impossible de calculer → pas de "% de réussite"
        assert "% de réussite" not in recap

    def test_ca3_taux_absent_si_plants_manquants(self) -> None:
        """CA3 — Edge case : nb_plants_godets absent → pas de taux affiché."""
        payload = {
            "action": "mise_en_godet",
            "culture": "tomate",
            "nb_graines_semees": 30,
            "nb_plants_godets": None,
        }
        recap = _build_recap(payload, event_id=4)
        assert "% de réussite" not in recap

    def test_ca3_recap_mentionne_pepiniere_hors_stock(self, parsed_mise_en_godet: dict) -> None:
        """CA3 — Le récap indique la mise en godet comme repiquage de plantules [US-016]."""
        recap = _build_recap(parsed_mise_en_godet, event_id=5)
        assert "repiquage" in recap.lower() or "godet" in recap.lower()


# ──────────────────────────────────────────────────────────────────────────────
# CA4 — mise_en_godet n'incrémente pas le stock actif
# ──────────────────────────────────────────────────────────────────────────────

class TestCA4StockExclu:
    def test_ca4_mise_en_godet_absente_du_stock(self, test_db) -> None:
        """CA4 — Un événement mise_en_godet ne figure pas dans calcul_stock_cultures."""
        from utils.stock import calcul_stock_cultures

        ev = Evenement(
            type_action="mise_en_godet",
            culture="tomate",
            variete="cerise",
            nb_graines_semees=30,
            nb_plants_godets=24,
            quantite=None,
            unite="plants",
        )
        test_db.add(ev)
        test_db.commit()

        stock = calcul_stock_cultures(test_db)
        # La mise_en_godet ne doit pas contribuer au stock des plantations
        assert "tomate" not in stock

    def test_ca4_plantation_incrementee_stock(self, test_db) -> None:
        """CA4 — Contrôle : une plantation incrémente bien le stock (comportement attendu)."""
        from utils.stock import calcul_stock_cultures

        ev = Evenement(
            type_action="plantation",
            culture="courgette",
            quantite=5.0,
            unite="plants",
            rang=1,
        )
        test_db.add(ev)
        test_db.commit()

        stock = calcul_stock_cultures(test_db)
        assert "courgette" in stock
        assert stock["courgette"].plants_plantes == 5.0

    def test_ca4_mise_en_godet_et_plantation_meme_culture(self, test_db) -> None:
        """CA4 — mise_en_godet ne s'additionne pas au stock si la même culture a une plantation."""
        from utils.stock import calcul_stock_cultures

        test_db.add(Evenement(
            type_action="plantation",
            culture="tomate",
            quantite=10.0,
            unite="plants",
            rang=1,
        ))
        test_db.add(Evenement(
            type_action="mise_en_godet",
            culture="tomate",
            nb_graines_semees=30,
            nb_plants_godets=24,
        ))
        test_db.commit()

        stock = calcul_stock_cultures(test_db)
        # Seule la plantation doit compter (10 plants, pas 34)
        assert stock["tomate"].plants_plantes == 10.0

    def test_ca4_filtre_plantation_uniquement(self) -> None:
        """CA4 — Vérifie dans le code source que calcul_stock_cultures filtre sur 'plantation'."""
        import inspect
        from utils import stock as stock_module
        source = inspect.getsource(stock_module.calcul_stock_cultures)
        assert '"plantation"' in source or "'plantation'" in source


# ──────────────────────────────────────────────────────────────────────────────
# CA5 — PARSE_PROMPT contient mise_en_godet ET les champs nb_*
# ──────────────────────────────────────────────────────────────────────────────

class TestCA5PromptLLM:
    def test_ca5_prompt_contient_mise_en_godet_dans_liste_actions(self) -> None:
        """CA5 — PARSE_PROMPT liste 'mise_en_godet' parmi les actions possibles."""
        assert "mise_en_godet" in PARSE_PROMPT

    def test_ca5_prompt_contient_champ_nb_graines_semees(self) -> None:
        """CA5 — PARSE_PROMPT définit le champ nb_graines_semees dans le schéma JSON."""
        assert "nb_graines_semees" in PARSE_PROMPT

    def test_ca5_prompt_contient_champ_nb_plants_godets(self) -> None:
        """CA5 — PARSE_PROMPT définit le champ nb_plants_godets dans le schéma JSON."""
        assert "nb_plants_godets" in PARSE_PROMPT

    def test_ca5_prompt_contient_exemple_gherkin(self) -> None:
        """CA5 — PARSE_PROMPT inclut un exemple concret de mise_en_godet avec nb_graines/plants."""
        assert "nb_graines_semees" in PARSE_PROMPT
        assert "nb_plants_godets" in PARSE_PROMPT
        # L'exemple Gherkin doit montrer action=mise_en_godet
        assert '"action":"mise_en_godet"' in PARSE_PROMPT.replace(" ", "").replace("\n", "")

    def test_ca5_prompt_format_valide(self) -> None:
        """CA5 — PARSE_PROMPT peut être formaté sans erreur avec des valeurs de dates fictives."""
        formatted = PARSE_PROMPT.format(
            date_context="Aujourd'hui le 2026-04-08.",
            today_iso="2026-04-08",
            yesterday="2026-04-07",
            day_before="2026-04-06",
        )
        assert "mise_en_godet" in formatted
        assert "nb_graines_semees" in formatted
        assert "nb_plants_godets" in formatted


# ──────────────────────────────────────────────────────────────────────────────
# CA6 — POST /parse sauvegarde nb_graines_semees et nb_plants_godets
# ──────────────────────────────────────────────────────────────────────────────

class TestCA6MainParseSaveGodetFields:
    def test_ca6_post_parse_sauvegarde_champs_godet(self, test_db) -> None:
        """CA6 — POST /parse crée un Evenement avec nb_graines_semees et nb_plants_godets."""
        from fastapi.testclient import TestClient
        from unittest.mock import patch
        from main import app

        parsed_mock = [{
            "action": "mise_en_godet",
            "culture": "tomate",
            "variete": "cerise",
            "nb_graines_semees": 30,
            "nb_plants_godets": 24,
            "quantite": None,
            "unite": None,
            "parcelle": None,
            "date": None,
            "commentaire": None,
        }]
        with patch("main.parse_commande", return_value=parsed_mock), \
             patch("main.add_to_rag"), \
             patch("main.SessionLocal", return_value=test_db):
            client = TestClient(app)
            resp = client.post("/parse", json={"texte": "mis en godet 24 tomates cerise sur 30 graines"})

        assert resp.status_code == 200
        ev = test_db.query(Evenement).filter(Evenement.type_action == "mise_en_godet").first()
        assert ev is not None
        assert ev.nb_graines_semees == 30
        assert ev.nb_plants_godets == 24


# ──────────────────────────────────────────────────────────────────────────────
# CA7 — GET /godets retourne les godets sans plantation postérieure
# ──────────────────────────────────────────────────────────────────────────────

class TestCA7GetGodets:
    def test_ca7_godets_en_attente_retournes(self, test_db) -> None:
        """CA7 — GET /godets retourne un godet sans plantation postérieure."""
        from fastapi.testclient import TestClient
        from unittest.mock import patch
        from main import app

        test_db.add(Evenement(
            type_action="mise_en_godet",
            culture="tomate",
            variete="cerise",
            nb_graines_semees=30,
            nb_plants_godets=24,
        ))
        test_db.commit()

        with patch("main.SessionLocal", return_value=test_db):
            client = TestClient(app)
            resp = client.get("/godets")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["godets_en_attente"][0]["culture"] == "tomate"
        assert data["godets_en_attente"][0]["nb_plants_godets"] == 24

    def test_ca7_godets_vide_si_aucun(self, test_db) -> None:
        """CA7 — GET /godets retourne une liste vide si aucun godet enregistré."""
        from fastapi.testclient import TestClient
        from unittest.mock import patch
        from main import app

        with patch("main.SessionLocal", return_value=test_db):
            client = TestClient(app)
            resp = client.get("/godets")

        assert resp.status_code == 200
        assert resp.json()["total"] == 0


# ──────────────────────────────────────────────────────────────────────────────
# CA8 — GET /godets exclut les godets avec plantation postérieure
# ──────────────────────────────────────────────────────────────────────────────

class TestCA8GetGodetsExclusion:
    def test_ca8_godet_exclu_si_plantation_posterieure(self, test_db) -> None:
        """CA8 — GET /godets n'inclut pas un godet déjà planté en parcelle."""
        from fastapi.testclient import TestClient
        from unittest.mock import patch
        from datetime import datetime
        from main import app

        test_db.add(Evenement(
            type_action="mise_en_godet",
            culture="poivron",
            nb_plants_godets=15,
            date=datetime(2026, 3, 10),
        ))
        test_db.add(Evenement(
            type_action="plantation",
            culture="poivron",
            quantite=15.0,
            unite="plants",
            rang=1,
            date=datetime(2026, 4, 1),
        ))
        test_db.commit()

        with patch("main.SessionLocal", return_value=test_db):
            client = TestClient(app)
            resp = client.get("/godets")

        assert resp.status_code == 200
        assert resp.json()["total"] == 0


# ──────────────────────────────────────────────────────────────────────────────
# CA9 — calcul_godets() retourne le taux de réussite correct
# ──────────────────────────────────────────────────────────────────────────────

class TestCA9CalcGodets:
    def test_ca9_taux_reussite_calcule(self, test_db) -> None:
        """CA9 — calcul_godets() retourne 80% pour 24 plants sur 30 graines."""
        from utils.stock import calcul_godets

        test_db.add(Evenement(
            type_action="mise_en_godet",
            culture="tomate",
            variete="cerise",
            nb_graines_semees=30,
            nb_plants_godets=24,
        ))
        test_db.commit()

        godets = calcul_godets(test_db)
        assert "tomate (cerise)" in godets
        assert godets["tomate (cerise)"]["taux_reussite"] == 80

    def test_ca9_taux_none_si_graines_absentes(self, test_db) -> None:
        """CA9 — taux_reussite est None si nb_graines_semees est absent."""
        from utils.stock import calcul_godets

        test_db.add(Evenement(
            type_action="mise_en_godet",
            culture="poivron",
            nb_plants_godets=10,
            nb_graines_semees=None,
        ))
        test_db.commit()

        godets = calcul_godets(test_db)
        assert "poivron" in godets
        assert godets["poivron"]["taux_reussite"] is None


# ──────────────────────────────────────────────────────────────────────────────
# CA10 — calcul_semis() retourne graines_en_godet enrichi
# ──────────────────────────────────────────────────────────────────────────────

class TestCA10CalcSemisEnriched:
    def test_ca10_graines_en_godet_present(self, test_db) -> None:
        """CA10 — calcul_semis() retourne plants_en_godet (nb_plants_godets) [US-017]."""
        from utils.stock import calcul_semis

        test_db.add(Evenement(
            type_action="semis",
            culture="tomate",
            quantite=50.0,
            unite="graines",
        ))
        test_db.add(Evenement(
            type_action="mise_en_godet",
            culture="tomate",
            nb_graines_semees=30,
            nb_plants_godets=24,
        ))
        test_db.commit()

        semis = calcul_semis(test_db)
        assert "tomate" in semis
        # [US-017] On déduit nb_plants_godets (24), pas nb_graines_semees (30)
        assert semis["tomate"]["plants_en_godet"] == 24
        assert semis["tomate"]["stock_residuel"] == max(0, 50 - 24)  # 26

    def test_ca10_graines_en_godet_zero_si_aucun_godet(self, test_db) -> None:
        """CA10 — graines_en_godet vaut 0 si aucune mise_en_godet pour cette culture."""
        from utils.stock import calcul_semis

        test_db.add(Evenement(
            type_action="semis",
            culture="carotte",
            quantite=100.0,
            unite="graines",
        ))
        test_db.commit()

        semis = calcul_semis(test_db)
        assert "carotte" in semis
        assert semis["carotte"]["plants_en_godet"] == 0  # [US-017] nouvelle clé

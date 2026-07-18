"""
tests/test_us036_rendement_poids_vegetatif.py — Tests US-036
--------------------------------------------------------------
Couverture :
  - CA1/CA2 : non testables automatiquement (jugement du LLM Groq sur la
    formulation) — couverts par la règle + exemple ajoutés à PARSE_PROMPT,
    validés manuellement. CA3 (plomberie de sauvegarde multi-items) est
    testée ci-dessous via _do_save_items.
  - CA3/CA4 : double entrée récolte (pièces + poids) — déduction de stock
    par les pièces uniquement, rendement alimenté par le poids uniquement
  - CA5     : rendement cumulé exposé pour le végétatif (comme reproducteur)
  - CA6     : garde-fou — aucune double déduction (poids n'affecte pas le stock)
  - CA7     : /stats par variété (calcul_stock_par_variete) sépare les 2 pools
  - CA8     : le graphique Rendements (calcul_rendement_mensuel) inclut
    désormais les cultures végétatives pesées
  - CA9     : un seul événement (pièces) ne génère aucun rendement (no régression)
  - CA10    : poids dicté sans nombre de pieds (végétatif) → clarification
    demandée, puis combinaison en 2 items après réponse utilisateur
  - Régression constatée en production (US-036) : utils/parcelles.py avait sa
    propre agrégation des récoltes, indépendante de utils/stock.py, qui
    additionnait quantite sans filtrer par unité — une récolte pesée (g/kg)
    se cumulait avec la récolte en pièces et faisait disparaître la culture
    de /plan (nb_plants retombait à 0). Couvert ci-dessous.
"""
import time
import pytest
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.db import Base
from database.models import Evenement, CultureConfig, Parcelle
from utils.stock import (
    calcul_stock_cultures,
    calcul_stock_par_variete,
    calcul_rendement_mensuel,
    format_stock_stats_json,
    format_stock_ligne_telegram,
    format_variete_bloc_telegram,
)
from utils.parcelles import calcul_occupation_parcelles


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def engine():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture
def db(engine):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


def _seed_betterave(db):
    db.add(CultureConfig(nom="betterave", type_organe_recolte="végétatif", description_agronomique="Racine"))
    db.commit()


# ══════════════════════════════════════════════════════════════════════════════
# CA3 / CA4 / CA6 — calcul_stock_cultures : double entrée pièces + poids
# ══════════════════════════════════════════════════════════════════════════════

class TestDoubleEntreeStockCultures:

    def test_ca3_ca4_pieces_deduisent_stock_poids_alimente_rendement(self, db):
        """[CA3/CA4] 2 pieds + 250g sur la même culture : stock=-2, rendement=+250g."""
        _seed_betterave(db)
        db.add(Evenement(type_action="plantation", culture="betterave", quantite=20, rang=1, unite="plants", date=date(2026, 3, 1)))
        db.add(Evenement(type_action="recolte",    culture="betterave", quantite=2,   unite="plants", date=date(2026, 6, 1)))
        db.add(Evenement(type_action="recolte",    culture="betterave", quantite=250, unite="g",      date=date(2026, 6, 1)))
        db.commit()

        s = calcul_stock_cultures(db)["betterave"]
        assert s.type_organe == "végétatif"
        # Stock = 20 plantés - 2 récoltés (pièces) = 18, le poids n'intervient pas
        assert s.stock_plants == 18
        assert s.recoltes_total == 2.0
        assert s.rendement_total == 250.0  # reste en "g" sous le seuil de 1000
        assert s.unite_rendement == "g"

    def test_ca6_garde_fou_poids_ne_double_deduit_pas_stock(self, db):
        """[CA6] Un poids élevé ne doit jamais réduire le stock de plants au-delà des pièces."""
        _seed_betterave(db)
        db.add(Evenement(type_action="plantation", culture="betterave", quantite=10, rang=1, unite="plants", date=date(2026, 3, 1)))
        db.add(Evenement(type_action="recolte",    culture="betterave", quantite=1,    unite="plants", date=date(2026, 6, 1)))
        db.add(Evenement(type_action="recolte",    culture="betterave", quantite=5000, unite="g",      date=date(2026, 6, 1)))
        db.commit()

        s = calcul_stock_cultures(db)["betterave"]
        # Si le poids était comptabilisé dans la déduction, stock serait négatif/0 à tort
        assert s.stock_plants == 9
        assert s.rendement_total == 5.0

    def test_ca9_seul_nombre_de_pieds_aucun_rendement(self, db):
        """[CA9] Pas de poids dicté → comportement identique à avant, pas de rendement."""
        _seed_betterave(db)
        db.add(Evenement(type_action="plantation", culture="betterave", quantite=10, rang=1, unite="plants", date=date(2026, 3, 1)))
        db.add(Evenement(type_action="recolte",    culture="betterave", quantite=3, unite="plants", date=date(2026, 6, 1)))
        db.commit()

        s = calcul_stock_cultures(db)["betterave"]
        assert s.stock_plants == 7
        assert s.rendement_total == 0.0
        assert s.nb_recoltes_poids == 0


# ══════════════════════════════════════════════════════════════════════════════
# CA5 — Exposition JSON /stats + Telegram
# ══════════════════════════════════════════════════════════════════════════════

class TestExpositionRendementVegetatif:

    def test_ca5_json_expose_rendement_si_pese(self, db):
        """[CA5] format_stock_stats_json expose rendement_total pour le végétatif pesé."""
        _seed_betterave(db)
        db.add(Evenement(type_action="plantation", culture="betterave", quantite=20, rang=1, unite="plants", date=date(2026, 3, 1)))
        db.add(Evenement(type_action="recolte",    culture="betterave", quantite=2,   unite="plants", date=date(2026, 6, 1)))
        db.add(Evenement(type_action="recolte",    culture="betterave", quantite=250, unite="g",      date=date(2026, 6, 1)))
        db.commit()

        stocks = calcul_stock_cultures(db)
        entry = next(e for e in format_stock_stats_json(stocks) if e["culture"] == "betterave")
        assert entry["rendement_total"] == 250.0
        assert entry["unite_rendement"] == "g"

    def test_ca7_json_pas_de_rendement_si_non_pese(self, db):
        """[CA7] Pas de régression : végétatif sans poids n'expose pas rendement_total."""
        _seed_betterave(db)
        db.add(Evenement(type_action="plantation", culture="betterave", quantite=20, rang=1, unite="plants", date=date(2026, 3, 1)))
        db.add(Evenement(type_action="recolte",    culture="betterave", quantite=2, unite="plants", date=date(2026, 6, 1)))
        db.commit()

        stocks = calcul_stock_cultures(db)
        entry = next(e for e in format_stock_stats_json(stocks) if e["culture"] == "betterave")
        assert "rendement_total" not in entry

    def test_ca5_telegram_ligne_affiche_rendement(self, db):
        """[CA5] format_stock_ligne_telegram affiche le rendement en plus du stock pièces."""
        _seed_betterave(db)
        db.add(Evenement(type_action="plantation", culture="betterave", quantite=20, rang=1, unite="plants", date=date(2026, 3, 1)))
        db.add(Evenement(type_action="recolte",    culture="betterave", quantite=2,   unite="plants", date=date(2026, 6, 1)))
        db.add(Evenement(type_action="recolte",    culture="betterave", quantite=250, unite="g",      date=date(2026, 6, 1)))
        db.commit()

        s = calcul_stock_cultures(db)["betterave"]
        ligne = format_stock_ligne_telegram(s)
        assert "18" in ligne
        assert "récolté 2" in ligne
        assert "250.0 g" in ligne


# ══════════════════════════════════════════════════════════════════════════════
# CA7 — Détail par variété (calcul_stock_par_variete)
# ══════════════════════════════════════════════════════════════════════════════

class TestDetailParVarieteVegetatif:

    def test_ca7_pools_separes_par_variete(self, db):
        """[CA7] calcul_stock_par_variete sépare pièces et poids par variété."""
        _seed_betterave(db)
        db.add(Evenement(type_action="plantation", culture="betterave", variete="rouge", quantite=15, rang=1, unite="plants", date=date(2026, 3, 1)))
        db.add(Evenement(type_action="recolte",    culture="betterave", variete="rouge", quantite=2,   unite="plants", date=date(2026, 6, 1)))
        db.add(Evenement(type_action="recolte",    culture="betterave", variete="rouge", quantite=250, unite="g",      date=date(2026, 6, 1)))
        db.commit()

        result = calcul_stock_par_variete(db, "betterave")
        assert len(result) == 1
        v = result[0]
        assert v["variete"] == "rouge"
        assert v["recoltes_total"] == 2.0
        assert v["rendement_total"] == 250.0
        assert v["unite_rendement"] == "g"

    def test_ca7_format_telegram_variete_affiche_rendement(self, db):
        """[CA7] format_variete_bloc_telegram affiche aussi le rendement pour le végétatif."""
        _seed_betterave(db)
        db.add(Evenement(type_action="plantation", culture="betterave", variete="rouge", quantite=15, rang=1, unite="plants", date=date(2026, 3, 1)))
        db.add(Evenement(type_action="recolte",    culture="betterave", variete="rouge", quantite=2,   unite="plants", date=date(2026, 6, 1)))
        db.add(Evenement(type_action="recolte",    culture="betterave", variete="rouge", quantite=250, unite="g",      date=date(2026, 6, 1)))
        db.commit()

        v = calcul_stock_par_variete(db, "betterave")[0]
        bloc = format_variete_bloc_telegram(v)
        assert "250.0 g" in bloc


# ══════════════════════════════════════════════════════════════════════════════
# CA8 — Graphique Rendements (calcul_rendement_mensuel)
# ══════════════════════════════════════════════════════════════════════════════

class TestRendementMensuelVegetatif:

    def test_ca8_culture_vegetative_pesee_incluse(self, db):
        """[CA8] Une culture végétative pesée apparaît dans le graphique Rendements."""
        _seed_betterave(db)
        db.add(Evenement(type_action="recolte", culture="betterave", quantite=2,   unite="plants", date=datetime(2026, 6, 1)))
        db.add(Evenement(type_action="recolte", culture="betterave", quantite=250, unite="g",      date=datetime(2026, 6, 1)))
        db.commit()

        data = calcul_rendement_mensuel(db, 2026)
        cultures = {c["culture"]: c for c in data["cultures"]}
        assert "betterave" in cultures
        assert cultures["betterave"]["total"] == 0.25
        # La récolte en pièces (unité "plants") n'est jamais incluse dans ce graphique
        assert cultures["betterave"]["mensuel"] == {"6": 0.25}


# ══════════════════════════════════════════════════════════════════════════════
# CA3 — Plomberie de sauvegarde : 2 items récolte → 2 Evenement distincts
# ══════════════════════════════════════════════════════════════════════════════

class TestSauvegardeDoubleEvenement:

    @pytest.mark.asyncio
    async def test_ca3_deux_items_recolte_creent_deux_evenements(self):
        """[CA3] _do_save_items crée un Evenement par item (pièces + poids), sans fusion."""
        import bot as bot_module

        update = MagicMock()
        update.effective_message = AsyncMock()
        update.effective_message.reply_text = AsyncMock()

        items = [
            {"action": "recolte", "culture": "betterave", "quantite": 2, "unite": "plants"},
            {"action": "recolte", "culture": "betterave", "quantite": 250, "unite": "g"},
        ]

        fake_db = MagicMock()
        fake_db.refresh = MagicMock()

        with patch("bot.SessionLocal", return_value=fake_db):
            await bot_module._do_save_items(update, items, "récolté 2 betteraves 250g")

        # Un Evenement ajouté par item, donc 2 appels à db.add()
        assert fake_db.add.call_count == 2
        evenements_ajoutes = [call.args[0] for call in fake_db.add.call_args_list]
        quantites = sorted(e.quantite for e in evenements_ajoutes)
        unites    = sorted(e.unite for e in evenements_ajoutes)
        assert quantites == [2.0, 250.0]
        assert unites == ["g", "plants"]


# ══════════════════════════════════════════════════════════════════════════════
# CA10 — Récolte végétative pesée sans nombre de pieds → clarification
# ══════════════════════════════════════════════════════════════════════════════

class TestClarificationPiecesManquantes:

    @pytest.mark.asyncio
    async def test_ca10_poids_seul_vegetatif_demande_clarification(self):
        """[CA10] Poids seul sur une culture végétative → demande le nombre de pieds, pas de sauvegarde."""
        import bot as bot_module
        from bot import _RECOLTE_PIECES_PENDING

        user_id = 100
        update = MagicMock()
        update.effective_user.id = user_id
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock()
        update.callback_query = None

        parsed_item = {"action": "recolte", "culture": "betterave", "quantite": 250, "unite": "g"}

        with (
            patch("bot.parse_commande", return_value=[parsed_item]),
            patch("bot._normalize_items", return_value=[parsed_item]),
            patch("utils.validation.validate_parsed_action", return_value=(True, "")),
            patch("utils.stock.get_type_organe", return_value="végétatif"),
            patch("utils.culture_resolve.culture_deja_plantee", return_value=True),
            patch("bot.SessionLocal"),
        ):
            _RECOLTE_PIECES_PENDING.pop(user_id, None)
            await bot_module._parse_and_save(update, "récolté 250g de betterave")

        assert update.message.reply_text.called
        texte_envoye = update.message.reply_text.call_args[0][0]
        assert "pieds" in texte_envoye.lower()

        assert user_id in _RECOLTE_PIECES_PENDING
        assert _RECOLTE_PIECES_PENDING[user_id]["items"] == [parsed_item]
        _RECOLTE_PIECES_PENDING.pop(user_id, None)

    @pytest.mark.asyncio
    async def test_ca10_poids_seul_reproducteur_pas_de_clarification(self):
        """[CA10] Poids seul sur une culture reproductrice → comportement normal, pas de clarification."""
        import bot as bot_module
        from bot import _RECOLTE_PIECES_PENDING

        user_id = 101
        update = MagicMock()
        update.effective_user.id = user_id
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock()
        update.callback_query = None

        parsed_item = {"action": "recolte", "culture": "tomate", "quantite": 2, "unite": "kg"}

        with (
            patch("bot.parse_commande", return_value=[parsed_item]),
            patch("bot._normalize_items", return_value=[parsed_item]),
            patch("utils.validation.validate_parsed_action", return_value=(True, "")),
            patch("utils.stock.get_type_organe", return_value="reproducteur"),
            patch("bot.SessionLocal"),
            patch("bot.get_all_parcelles", return_value=[]),
        ):
            _RECOLTE_PIECES_PENDING.pop(user_id, None)
            await bot_module._parse_and_save(update, "récolté 2 kg de tomates")

        # Pas de clarification déclenchée pour le reproducteur
        assert user_id not in _RECOLTE_PIECES_PENDING
        from bot import _ACTION_PENDING
        _ACTION_PENDING.pop(user_id, None)

    @pytest.mark.asyncio
    async def test_ca10_reponse_nombre_pieds_combine_les_deux_items(self):
        """[CA10] La réponse au nombre de pieds reconstruit un item pièces et relance le parsing."""
        import bot as bot_module
        from bot import _RECOLTE_PIECES_PENDING

        user_id = 102
        poids_item = {"action": "recolte", "culture": "betterave", "quantite": 250, "unite": "g"}
        _RECOLTE_PIECES_PENDING[user_id] = {
            "items": [poids_item], "texte": "récolté 250g de betterave", "ts": time.time(),
        }

        update = MagicMock()
        update.effective_user.id = user_id
        update.message = MagicMock()
        update.message.text = "2"
        update.message.reply_text = AsyncMock()

        with patch("bot._parse_and_save", new_callable=AsyncMock) as mock_parse_save:
            await bot_module.handle_text(update, MagicMock())

        assert user_id not in _RECOLTE_PIECES_PENDING
        mock_parse_save.assert_awaited_once()
        _, items_passed = mock_parse_save.call_args[0][0], mock_parse_save.call_args[1].get("pre_parsed_items")
        assert len(items_passed) == 2
        pieces = next(i for i in items_passed if i["unite"] == "plants")
        poids  = next(i for i in items_passed if i["unite"] == "g")
        assert pieces["quantite"] == "2"
        assert poids["quantite"] == 250


# ══════════════════════════════════════════════════════════════════════════════
# Régression /plan — la récolte pesée ne doit pas faire disparaître la culture
# ══════════════════════════════════════════════════════════════════════════════

class TestOccupationParcellesNonRegression:

    def test_recolte_pesee_vegetatif_naffecte_pas_occupation_parcelle(self, db):
        """[US-036 non-regression] Une récolte pesée ne doit pas réduire nb_plants
        sur /plan — seule la récolte en pièces compte pour l'occupation."""
        _seed_betterave(db)
        p = Parcelle(nom="PLACE_MILIEU_A", nom_normalise="placemilieua", actif=True)
        db.add(p); db.commit()
        db.add(Evenement(
            type_action="plantation", culture="betterave", variete="rouge",
            quantite=50, rang=1, unite="plants", parcelle_id=p.id, date=date(2026, 4, 5),
        ))
        db.add(Evenement(type_action="recolte", culture="betterave", quantite=2,   unite="plants", date=date(2026, 6, 22)))
        db.add(Evenement(type_action="recolte", culture="betterave", quantite=250, unite="g",      date=date(2026, 6, 22)))
        db.commit()

        occupation = calcul_occupation_parcelles(db)
        cultures = occupation.get("PLACE_MILIEU_A", [])
        betterave = next((c for c in cultures if c["culture"] == "betterave"), None)

        assert betterave is not None, "la betterave a disparu du plan (régression du bug poids/pièces)"
        assert betterave["nb_plants"] == 48  # 50 plantés - 2 récoltés (pièces), le poids n'intervient pas

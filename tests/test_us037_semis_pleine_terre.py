"""
tests/test_us037_semis_pleine_terre.py
---------------------------------------
[US-037] Enregistrer un semis en pleine terre avec type de culture et unité adaptée.

Couvre :
- CA1/CA2/CA6 : normalisation d'unité semis (graines | pieds | m²), zéro conversion
- CA3        : résolution automatique de type_organe_recolte via CultureConfig
- CA4        : stock végétatif alimenté par un semis pleine terre
- CA5        : stock reproducteur pleine terre — récolte n'affecte pas le stock de pieds
- CA7        : culture inconnue de CultureConfig → clarification avant sauvegarde
- CA8        : champs de l'événement semis
- CA9        : affichage /stats (Telegram + JSON) avec l'unité d'origine
- CA10       : occupation de parcelle — un semis m² n'est pas multiplié par une empreinte au pied
- Régression : /déplacer (US-007) doit retrouver une culture semée uniquement en pleine
  terre (sans événement 'plantation'), sinon "Aucune plantation trouvée" bloque à tort
  l'utilisateur (bug remonté après mise en prod de l'US-037)
"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from database.models import Evenement, Parcelle, CultureConfig
from utils.stock import (
    calcul_stock_cultures,
    calcul_stock_par_variete,
    calcul_semis,
    format_stock_ligne_telegram,
    format_stock_stats_json,
    get_type_organe,
    _fmt_qte_unite,
)
from app.services.evenements import _normalize_unite_semis, _UNITES_SEMIS_CANONIQUES
from bot import _do_save_items


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def db_with_parcelle_et_cultures(test_db):
    """BD avec une parcelle 'nord' et deux CultureConfig (végétatif / reproducteur)."""
    db = test_db
    db.add(Parcelle(nom="Nord", nom_normalise="nord", ordre=1, actif=True))
    db.add(CultureConfig(nom="carotte", type_organe_recolte="végétatif"))
    db.add(CultureConfig(nom="haricot", type_organe_recolte="reproducteur"))
    db.commit()
    return db


def _mock_update():
    update = MagicMock()
    update.effective_message.reply_text = AsyncMock()
    update.effective_user.id = 42
    return update


# ──────────────────────────────────────────────────────────────────────────────
# CA1 / CA2 / CA6 — normalisation d'unité semis (graines | pieds | m²)
# ──────────────────────────────────────────────────────────────────────────────

class TestNormalisationUnite:

    @pytest.mark.parametrize("brute", ["m2", "m²", "M2", "mètre carré", "metre carre", " m2 "])
    def test_ca1_ca2_unites_surface_normalisees_vers_m2(self, brute):
        """CA1/CA2 : toute variante de saisie 'm2' est normalisée en 'm²', jamais convertie."""
        assert _normalize_unite_semis(brute) == "m²"

    @pytest.mark.parametrize("brute", ["pied", "pieds", "plant", "plants", "PIEDS"])
    def test_ca1_unites_pieds_normalisees(self, brute):
        assert _normalize_unite_semis(brute) == "pieds"

    @pytest.mark.parametrize("brute", ["graine", "graines", "GRAINES"])
    def test_ca1_unites_graines_normalisees(self, brute):
        assert _normalize_unite_semis(brute) == "graines"

    @pytest.mark.parametrize("brute", [None, "", "pots", "barquette", "kg"])
    def test_ca6_unite_totalement_inconnue_defaut_graines(self, brute):
        """Seule une unité vraiment inconnue retombe sur 'graines' par défaut."""
        assert _normalize_unite_semis(brute) == "graines"

    def test_toutes_les_cles_canoniques_couvrent_les_3_unites(self):
        assert set(_UNITES_SEMIS_CANONIQUES.values()) == {"graines", "pieds", "m²"}


class TestSauvegardeUniteM2:

    @pytest.mark.asyncio
    @patch("bot.send_voice_reply", new_callable=AsyncMock)
    async def test_ca2_quantite_m2_conservee_sans_conversion(self, mock_voice, db_with_parcelle_et_cultures):
        """[CA2 / reproduction bug id=274-275] Un semis '2 m2' ne doit PLUS perdre sa quantité
        ni se voir forcer l'unité 'graines'."""
        db = db_with_parcelle_et_cultures
        item = {"action": "semis", "culture": "haricot", "quantite": 2, "unite": "m2", "parcelle": "nord"}
        with patch("bot.SessionLocal", return_value=db):
            await _do_save_items(_mock_update(), [item], "j'ai semé 2 m2 de haricot vert")

        ev = db.query(Evenement).filter_by(type_action="semis", culture="haricot").first()
        assert ev is not None
        assert ev.quantite == 2
        assert ev.unite == "m²"

    @pytest.mark.asyncio
    @patch("bot.send_voice_reply", new_callable=AsyncMock)
    async def test_ca3_type_organe_resolu_a_la_sauvegarde(self, mock_voice, db_with_parcelle_et_cultures):
        """[CA3 / reproduction bug id=274-275] type_organe_recolte doit être renseigné dès
        la sauvegarde, pas laissé NULL alors que la culture est connue."""
        db = db_with_parcelle_et_cultures
        item = {"action": "semis", "culture": "haricot", "quantite": 2, "unite": "m²", "parcelle": "nord"}
        with patch("bot.SessionLocal", return_value=db):
            await _do_save_items(_mock_update(), [item], "semis haricot")

        ev = db.query(Evenement).filter_by(type_action="semis", culture="haricot").first()
        assert ev.type_organe_recolte == "reproducteur"

    @pytest.mark.asyncio
    @patch("bot.send_voice_reply", new_callable=AsyncMock)
    async def test_ca3_culture_inconnue_type_organe_reste_none(self, mock_voice, db_with_parcelle_et_cultures):
        """Sans CultureConfig existante, _do_save_items n'invente pas de type_organe (CA7 gère ce cas en amont)."""
        db = db_with_parcelle_et_cultures
        item = {"action": "semis", "culture": "mache", "quantite": 1, "unite": "m²", "parcelle": "nord"}
        with patch("bot.SessionLocal", return_value=db):
            await _do_save_items(_mock_update(), [item], "semis mache")

        ev = db.query(Evenement).filter_by(type_action="semis", culture="mache").first()
        assert ev.type_organe_recolte is None


# ──────────────────────────────────────────────────────────────────────────────
# CA4 — Stock végétatif alimenté par un semis pleine terre
# ──────────────────────────────────────────────────────────────────────────────

class TestStockVegetatifSemisPleineTerre:

    def test_ca4_semis_graines_alimente_le_stock(self, db_with_parcelle_et_cultures):
        db = db_with_parcelle_et_cultures
        nord = db.query(Parcelle).filter_by(nom_normalise="nord").first()
        db.add(Evenement(
            type_action="semis", culture="carotte", quantite=80, unite="graines",
            parcelle_id=nord.id, date=datetime.now(),
        ))
        db.commit()

        stocks = calcul_stock_cultures(db)
        assert "carotte" in stocks
        assert stocks["carotte"].stock_plants == 80
        assert stocks["carotte"].unite == "graines"
        assert stocks["carotte"].type_organe == "végétatif"

    def test_ca4_recolte_terminale_decremente_le_stock_vegetatif(self, db_with_parcelle_et_cultures):
        db = db_with_parcelle_et_cultures
        nord = db.query(Parcelle).filter_by(nom_normalise="nord").first()
        db.add(Evenement(
            type_action="semis", culture="carotte", quantite=80, unite="graines",
            parcelle_id=nord.id, date=datetime.now() - timedelta(days=10),
        ))
        db.add(Evenement(
            type_action="recolte", culture="carotte", quantite=30, unite="plants",
            date=datetime.now(),
        ))
        db.commit()

        stocks = calcul_stock_cultures(db)
        assert stocks["carotte"].stock_plants == 50

    def test_ca4_semis_nursery_sans_parcelle_nest_pas_compte(self, db_with_parcelle_et_cultures):
        """Un semis SANS parcelle_id (barquette pépinière) ne doit pas fausser le stock potager."""
        db = db_with_parcelle_et_cultures
        db.add(Evenement(
            type_action="semis", culture="carotte", quantite=200, unite="graines",
            parcelle_id=None, date=datetime.now(),
        ))
        db.commit()

        stocks = calcul_stock_cultures(db)
        assert "carotte" not in stocks


# ──────────────────────────────────────────────────────────────────────────────
# CA5 — Stock reproducteur pleine terre (pieds actifs + rendement indépendant)
# ──────────────────────────────────────────────────────────────────────────────

class TestStockReproducteurSemisPleineTerre:

    def test_ca5_semis_m2_alimente_le_stock_pieds_actifs(self, db_with_parcelle_et_cultures):
        db = db_with_parcelle_et_cultures
        nord = db.query(Parcelle).filter_by(nom_normalise="nord").first()
        db.add(Evenement(
            type_action="semis", culture="haricot", quantite=2, unite="m²",
            parcelle_id=nord.id, date=datetime.now(),
        ))
        db.commit()

        stocks = calcul_stock_cultures(db)
        assert stocks["haricot"].stock_plants == 2
        assert stocks["haricot"].unite == "m²"
        assert stocks["haricot"].is_reproducteur

    def test_ca5_recolte_ne_decremente_pas_le_stock_pieds(self, db_with_parcelle_et_cultures):
        """[Gherkin Cas 3] Une récolte de 800g ne doit pas réduire le stock de 2 m² de pieds."""
        db = db_with_parcelle_et_cultures
        nord = db.query(Parcelle).filter_by(nom_normalise="nord").first()
        db.add(Evenement(
            type_action="semis", culture="haricot", quantite=2, unite="m²",
            parcelle_id=nord.id, date=datetime.now() - timedelta(days=20),
        ))
        db.add(Evenement(
            type_action="recolte", culture="haricot", quantite=0.8, unite="kg",
            date=datetime.now(),
        ))
        db.commit()

        stocks = calcul_stock_cultures(db)
        haricot = stocks["haricot"]
        assert haricot.stock_plants == 2                # inchangé
        # 800g < 1000g → _best_unite conserve l'unité 'g' (comportement existant, pas US-037)
        assert haricot.rendement_total == pytest.approx(800.0)
        assert haricot.unite_rendement == "g"

    def test_ca5_perte_decremente_le_stock_pieds(self, db_with_parcelle_et_cultures):
        db = db_with_parcelle_et_cultures
        nord = db.query(Parcelle).filter_by(nom_normalise="nord").first()
        db.add(Evenement(
            type_action="semis", culture="haricot", quantite=2, unite="m²",
            parcelle_id=nord.id, date=datetime.now() - timedelta(days=20),
        ))
        db.add(Evenement(type_action="perte", culture="haricot", quantite=0.5, date=datetime.now()))
        db.commit()

        stocks = calcul_stock_cultures(db)
        assert stocks["haricot"].stock_plants == 1.5


# ──────────────────────────────────────────────────────────────────────────────
# CA5 (détail variété) — calcul_stock_par_variete doit aussi inclure les semis pleine terre
# ──────────────────────────────────────────────────────────────────────────────

class TestStockParVarieteSemisPleineTerre:

    def test_ca9_stock_par_variete_inclut_semis_pleine_terre(self, db_with_parcelle_et_cultures):
        db = db_with_parcelle_et_cultures
        nord = db.query(Parcelle).filter_by(nom_normalise="nord").first()
        db.add(Evenement(
            type_action="semis", culture="haricot", variete="vert nain", quantite=2, unite="m²",
            parcelle_id=nord.id, date=datetime.now(),
        ))
        db.commit()

        result = calcul_stock_par_variete(db, "haricot")
        assert len(result) == 1
        assert result[0]["variete"] == "vert nain"
        assert result[0]["plants_plantes"] == 2
        assert result[0]["unite_plant"] == "m²"

    def test_culture_uniquement_semee_sans_plantation_nest_plus_ignoree(self, db_with_parcelle_et_cultures):
        """Avant US-037, une culture sans événement 'plantation' retournait toujours []."""
        db = db_with_parcelle_et_cultures
        nord = db.query(Parcelle).filter_by(nom_normalise="nord").first()
        db.add(Evenement(
            type_action="semis", culture="carotte", quantite=50, unite="graines",
            parcelle_id=nord.id, date=datetime.now(),
        ))
        db.commit()

        assert calcul_stock_par_variete(db, "carotte") != []


# ──────────────────────────────────────────────────────────────────────────────
# CA7 — Culture inconnue de CultureConfig → clarification avant sauvegarde
# ──────────────────────────────────────────────────────────────────────────────

class TestClarificationCultureInconnue:

    @pytest.mark.asyncio
    async def test_ca7_semis_culture_inconnue_declenche_le_menu_et_ne_sauvegarde_pas(self, db_with_parcelle_et_cultures):
        from bot import _parse_and_save, _SEMIS_CULTURE_PENDING

        db = db_with_parcelle_et_cultures
        item = {"action": "semis", "culture": "mache", "quantite": 1, "unite": "m²", "parcelle": "nord"}

        update = MagicMock()
        update.message.reply_text = AsyncMock()
        update.callback_query = None
        update.effective_user.id = 99

        with patch("bot.SessionLocal", return_value=db):
            await _parse_and_save(update, "semé 1 m² de mâche", pre_parsed_items=[item])

        # Aucun événement enregistré : la sauvegarde est suspendue
        assert db.query(Evenement).filter_by(type_action="semis", culture="mache").first() is None
        # Un menu de clarification a bien été proposé
        update.message.reply_text.assert_awaited_once()
        assert 99 in _SEMIS_CULTURE_PENDING
        assert "végétative" in update.message.reply_text.call_args.args[0].lower() or \
               "reproductive" in update.message.reply_text.call_args.args[0].lower()
        _SEMIS_CULTURE_PENDING.pop(99, None)

    @pytest.mark.asyncio
    async def test_ca7_reponse_utilisateur_cree_cultureconfig_et_relance_la_sauvegarde(self, db_with_parcelle_et_cultures):
        from bot import _semis_organe_cb, _SEMIS_CULTURE_PENDING
        import time

        db = db_with_parcelle_et_cultures
        item = {"action": "semis", "culture": "mache", "quantite": 1, "unite": "m²", "parcelle": "nord"}
        _SEMIS_CULTURE_PENDING[7] = {"items": [item], "texte": "semé 1 m² de mâche", "ts": time.time()}

        update = MagicMock()
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        update.callback_query.data = "semis_organe:végétatif"
        update.effective_user.id = 7

        with patch("bot.SessionLocal", return_value=db), \
             patch("bot._parse_and_save", new_callable=AsyncMock) as mock_save, \
             patch("bot.send_voice_reply", new_callable=AsyncMock):
            await _semis_organe_cb(update, MagicMock())

        cfg = db.query(CultureConfig).filter_by(nom="mache").first()
        assert cfg is not None
        assert cfg.type_organe_recolte == "végétatif"
        mock_save.assert_awaited_once()
        assert 7 not in _SEMIS_CULTURE_PENDING

    @pytest.mark.asyncio
    async def test_ca7_annulation_ne_cree_pas_de_cultureconfig(self, db_with_parcelle_et_cultures):
        from bot import _semis_organe_cb, _SEMIS_CULTURE_PENDING
        import time

        db = db_with_parcelle_et_cultures
        item = {"action": "semis", "culture": "mache", "quantite": 1, "unite": "m²"}
        _SEMIS_CULTURE_PENDING[8] = {"items": [item], "texte": "semé 1 m² de mâche", "ts": time.time()}

        update = MagicMock()
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        update.callback_query.data = "semis_organe_cancel"
        update.effective_user.id = 8

        with patch("bot.SessionLocal", return_value=db):
            await _semis_organe_cb(update, MagicMock())

        assert db.query(CultureConfig).filter_by(nom="mache").first() is None
        assert 8 not in _SEMIS_CULTURE_PENDING


# ──────────────────────────────────────────────────────────────────────────────
# CA9 — Affichage /stats (Telegram + JSON) avec l'unité d'origine
# ──────────────────────────────────────────────────────────────────────────────

class TestAffichageStats:

    def test_ca9_fmt_qte_unite_arrondit_m2_sans_troncature(self):
        assert _fmt_qte_unite(1.5, "m²") == 1.5
        assert _fmt_qte_unite(2.0, "m²") == 2.0
        assert _fmt_qte_unite(3.0, "plants") == 3
        assert isinstance(_fmt_qte_unite(3.0, "plants"), int)

    def test_ca9_ligne_telegram_reproducteur_m2(self, db_with_parcelle_et_cultures):
        db = db_with_parcelle_et_cultures
        nord = db.query(Parcelle).filter_by(nom_normalise="nord").first()
        db.add(Evenement(type_action="semis", culture="haricot", quantite=2, unite="m²",
                          parcelle_id=nord.id, date=datetime.now() - timedelta(days=10)))
        db.add(Evenement(type_action="recolte", culture="haricot", quantite=1.4, unite="kg",
                          date=datetime.now()))
        db.commit()

        stocks = calcul_stock_cultures(db)
        ligne = format_stock_ligne_telegram(stocks["haricot"])
        assert "2 m² actifs" in ligne
        assert "1.4 kg" in ligne

    def test_ca9_json_stats_conserve_unite_m2(self, db_with_parcelle_et_cultures):
        db = db_with_parcelle_et_cultures
        nord = db.query(Parcelle).filter_by(nom_normalise="nord").first()
        db.add(Evenement(type_action="semis", culture="haricot", quantite=2, unite="m²",
                          parcelle_id=nord.id, date=datetime.now()))
        db.commit()

        stocks = calcul_stock_cultures(db)
        data = format_stock_stats_json(stocks)
        haricot_entry = next(e for e in data if e["culture"] == "haricot")
        assert haricot_entry["unite"] == "m²"
        assert haricot_entry["stock_plants"] == 2


# ──────────────────────────────────────────────────────────────────────────────
# CA10 — Occupation de parcelle : m² n'est jamais multiplié par une empreinte au pied
# ──────────────────────────────────────────────────────────────────────────────

class TestOccupationParcelleCA10:
    """[CA10] Appelle directement main.get_plan() (fonction sync, pas de TestClient/thread
    anyio) pour éviter le piège SQLite ':memory:' + SingletonThreadPool où chaque thread
    obtient une base vide — limitation d'environnement de test déjà présente sur ce projet
    (cf. tests/test_api.py, qui échoue pour la même raison, indépendamment de l'US-037)."""

    @pytest.fixture
    def db_plan(self, db_with_parcelle_et_cultures):
        db = db_with_parcelle_et_cultures
        nord = db.query(Parcelle).filter_by(nom_normalise="nord").first()
        nord.superficie_m2 = 10.0
        # Empreinte au pied de la carotte (utilisée pour les semis en graines/pieds)
        cfg = db.query(CultureConfig).filter_by(nom="carotte").first()
        cfg.surface_m2 = 0.03
        db.commit()
        return db

    def test_ca10_semis_m2_occupation_directe(self, db_plan):
        import main
        nord = db_plan.query(Parcelle).filter_by(nom_normalise="nord").first()
        db_plan.add(Evenement(type_action="semis", culture="haricot", quantite=2, unite="m²",
                               parcelle_id=nord.id, date=datetime.now()))
        db_plan.commit()

        with patch("main.SessionLocal", return_value=db_plan):
            data = main.get_plan(date_ref=None)

        parcelle_nord = next(p for p in data["parcelles"] if p["nom"] == "Nord")
        # 2 m² / 10 m² = 20% — PAS 2 × empreinte au pied
        assert parcelle_nord["occupation_pct"] == 20

    def test_ca10_semis_graines_reste_multiplie_par_empreinte_au_pied(self, db_plan):
        """Non-régression : les unités graines/pieds continuent d'utiliser l'empreinte au pied."""
        import main
        nord = db_plan.query(Parcelle).filter_by(nom_normalise="nord").first()
        db_plan.add(Evenement(type_action="semis", culture="carotte", quantite=100, unite="graines",
                               parcelle_id=nord.id, date=datetime.now()))
        db_plan.commit()

        with patch("main.SessionLocal", return_value=db_plan):
            data = main.get_plan(date_ref=None)

        parcelle_nord = next(p for p in data["parcelles"] if p["nom"] == "Nord")
        # 100 graines × 0.03 m²/pied = 3 m² → 3/10 = 30%
        assert parcelle_nord["occupation_pct"] == 30


# ──────────────────────────────────────────────────────────────────────────────
# Régression — /déplacer (US-007) doit retrouver une culture semée en pleine terre
# ──────────────────────────────────────────────────────────────────────────────

class TestDeplacerCultureSemeePleineTerre:
    """Bug remonté en prod : une culture semée uniquement en pleine terre (haricot, sans
    jamais passer par un événement 'plantation') était invisible pour /déplacer, qui ne
    filtrait que sur type_action == 'plantation'."""

    @pytest.mark.asyncio
    async def test_depl_start_trouve_une_culture_semee_pleine_terre(self, db_with_parcelle_et_cultures):
        from bot import _depl_start

        db = db_with_parcelle_et_cultures
        nord = db.query(Parcelle).filter_by(nom_normalise="nord").first()
        db.add(Evenement(type_action="semis", culture="haricot", quantite=2, unite="m²",
                          parcelle_id=nord.id, date=datetime.now()))
        db.commit()

        update = MagicMock()
        update.message.reply_text = AsyncMock()
        ctx = MagicMock()
        ctx.user_data = {}

        with patch("bot.SessionLocal", return_value=db):
            await _depl_start(update, ctx, "haricot")

        # Ne doit PAS afficher le message d'échec "aucune plantation trouvée"
        texte = update.message.reply_text.call_args.args[0]
        assert "aucune" not in texte.lower()
        assert ctx.user_data.get("mode") == "depl_parcelle_select"

    def test_get_parcelles_avec_culture_trouve_semis_pleine_terre(self, db_with_parcelle_et_cultures):
        from bot import _get_parcelles_avec_culture

        db = db_with_parcelle_et_cultures
        nord = db.query(Parcelle).filter_by(nom_normalise="nord").first()
        db.add(Evenement(type_action="semis", culture="haricot", quantite=2, unite="m²",
                          parcelle_id=nord.id, date=datetime.now()))
        db.commit()

        parcelles = _get_parcelles_avec_culture(db, "haricot", None)
        assert len(parcelles) == 1
        assert parcelles[0].nom_normalise == "nord"

    def test_semis_pepiniere_sans_parcelle_non_localise(self, db_with_parcelle_et_cultures):
        """Un semis pépinière (parcelle_id=None) n'est jamais une 'localisation' déplaçable."""
        from bot import _get_parcelles_avec_culture

        db = db_with_parcelle_et_cultures
        db.add(Evenement(type_action="semis", culture="haricot", quantite=50, unite="graines",
                          parcelle_id=None, date=datetime.now()))
        db.commit()

        assert _get_parcelles_avec_culture(db, "haricot", None) == []


# ──────────────────────────────────────────────────────────────────────────────
# Régression — [CA2] ne jamais additionner des unités incompatibles pour une culture
# ──────────────────────────────────────────────────────────────────────────────

class TestPasDeMelangeUnitesIncompatibles:
    """Bug remonté en prod : un semis historique en 'graines' (id=2075, 100 graines) et un
    nouveau semis en 'm²' (id=276, 2 m²) pour la même culture 'haricot' se sommaient en
    '102 m²' — un artefact sans aucun sens physique. Plus jamais d'addition brute entre
    unités différentes pour une même culture."""

    def test_stock_cultures_ne_mixe_pas_graines_et_m2(self, db_with_parcelle_et_cultures):
        db = db_with_parcelle_et_cultures
        nord = db.query(Parcelle).filter_by(nom_normalise="nord").first()
        # Semis historique en graines (godet/pépinière classique, avant US-037)
        db.add(Evenement(type_action="semis", culture="haricot", variete="vert nain", quantite=100,
                          unite="graines", parcelle_id=nord.id, date=datetime.now() - timedelta(days=80)))
        # Nouveau semis pleine terre en m² (US-037)
        db.add(Evenement(type_action="semis", culture="haricot", variete="beurre", quantite=2,
                          unite="m²", parcelle_id=nord.id, date=datetime.now()))
        db.commit()

        stocks = calcul_stock_cultures(db)
        haricot = stocks["haricot"]
        # L'unité dominante (le plus grand total, ici 100 > 2) est conservée seule
        assert haricot.stock_plants == 100
        assert haricot.unite == "graines"
        # En aucun cas 102 (100 + 2 additionnés à tort entre unités incompatibles)
        assert haricot.stock_plants != 102

    def test_stock_par_variete_ne_mixe_pas_les_unites(self, db_with_parcelle_et_cultures):
        """Deux variétés différentes ont chacune leur propre unité — pas d'interférence."""
        db = db_with_parcelle_et_cultures
        nord = db.query(Parcelle).filter_by(nom_normalise="nord").first()
        db.add(Evenement(type_action="semis", culture="haricot", variete="vert nain", quantite=100,
                          unite="graines", parcelle_id=nord.id, date=datetime.now() - timedelta(days=80)))
        db.add(Evenement(type_action="semis", culture="haricot", variete="beurre", quantite=2,
                          unite="m²", parcelle_id=nord.id, date=datetime.now()))
        db.commit()

        result = calcul_stock_par_variete(db, "haricot")
        by_variete = {r["variete"]: r for r in result}
        assert by_variete["vert nain"]["plants_plantes"] == 100
        assert by_variete["vert nain"]["unite_plant"] == "graines"
        assert by_variete["beurre"]["plants_plantes"] == 2
        assert by_variete["beurre"]["unite_plant"] == "m²"

    def test_calcul_semis_ne_mixe_pas_les_unites(self, db_with_parcelle_et_cultures):
        from utils.stock import calcul_semis

        db = db_with_parcelle_et_cultures
        nord = db.query(Parcelle).filter_by(nom_normalise="nord").first()
        db.add(Evenement(type_action="semis", culture="haricot", quantite=100,
                          unite="graines", parcelle_id=nord.id, date=datetime.now() - timedelta(days=80)))
        db.add(Evenement(type_action="semis", culture="haricot", quantite=2,
                          unite="m²", parcelle_id=nord.id, date=datetime.now()))
        db.commit()

        semis = calcul_semis(db)
        assert semis["haricot"]["total_seme"] == 100
        assert semis["haricot"]["unite"] == "graines"
        assert semis["haricot"]["total_seme"] != 102


# ──────────────────────────────────────────────────────────────────────────────
# [migration_v15] Parcelle pépinière (est_pepiniere=True) — un semis qui y est
# rattaché ne doit jamais polluer le stock "pleine terre", même consommé en
# godet puis planté ailleurs. Bug remonté : 75 graines de tomate semées en
# pépinière (parcelle "serre" réelle) écrasaient les 22 plants réellement
# plantés, car _resoudre_unite_dominante gardait l'unité au plus gros total
# brut (75 > 22) sans savoir que ces graines étaient déjà consommées.
# ──────────────────────────────────────────────────────────────────────────────

class TestParcellePepiniereExclueDuStockPleineTerre:

    @pytest.fixture
    def db_avec_serre(self, db_with_parcelle_et_cultures):
        db = db_with_parcelle_et_cultures
        db.add(Parcelle(nom="Serre", nom_normalise="serre", ordre=2, actif=True, est_pepiniere=True))
        db.add(CultureConfig(nom="tomate", type_organe_recolte="reproducteur"))
        db.commit()
        return db

    def test_semis_pepiniere_nalimente_pas_le_stock_pleine_terre(self, db_avec_serre):
        db = db_avec_serre
        serre = db.query(Parcelle).filter_by(nom_normalise="serre").first()
        centre = db.query(Parcelle).filter_by(nom_normalise="nord").first()

        # 75 graines semées en pépinière (parcelle réelle "serre", flag pépinière)
        db.add(Evenement(
            type_action="semis", culture="tomate", quantite=75, unite="graines",
            parcelle_id=serre.id, date=datetime.now() - timedelta(days=60),
        ))
        # Mise en godet : les 75 graines sont consommées
        db.add(Evenement(
            type_action="mise_en_godet", culture="tomate",
            nb_graines_semees=75, nb_plants_godets=38,
            date=datetime.now() - timedelta(days=45),
        ))
        # 22 plants réellement transplantés en pleine terre
        db.add(Evenement(
            type_action="plantation", culture="tomate", quantite=22, unite="plants",
            parcelle_id=centre.id, date=datetime.now() - timedelta(days=20),
        ))
        db.commit()

        stocks = calcul_stock_cultures(db)
        tomate = stocks["tomate"]
        # Le stock "au potager" reflète les vraies plantations, pas les graines
        # déjà transformées en godet.
        assert tomate.stock_plants == 22
        assert tomate.unite == "plants"

        semis = calcul_semis(db)
        # La tomate ne doit plus apparaître comme "semée en pleine terre"
        assert semis["tomate"]["parcelles_pleine_terre"] == []

    def test_semis_parcelle_ordinaire_reste_pleine_terre(self, db_avec_serre):
        """Non-régression : une parcelle normale (est_pepiniere=False) continue de
        compter comme pleine terre, comme avant migration_v15."""
        db = db_avec_serre
        nord = db.query(Parcelle).filter_by(nom_normalise="nord").first()
        db.add(Evenement(
            type_action="semis", culture="haricot", quantite=2, unite="m²",
            parcelle_id=nord.id, date=datetime.now(),
        ))
        db.commit()

        stocks = calcul_stock_cultures(db)
        assert stocks["haricot"].stock_plants == 2
        assert stocks["haricot"].unite == "m²"

        semis = calcul_semis(db)
        assert semis["haricot"]["parcelles_pleine_terre"] == ["Nord"]

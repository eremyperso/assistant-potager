"""
tests/test_resolve_parcelle.py — Tests unitaires pour resolve_parcelle
-----------------------------------------------------------------------
Vérifie que la résolution de nom de parcelle (LLM → FK BDD) fonctionne
correctement dans tous les cas : exact, proche, introuvable, vide.
Couvre aussi la validation dans le flux de correction (_corr_apply).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from database.models import Parcelle, Evenement
from utils.parcelles import resolve_parcelle


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def db_avec_parcelles(test_db):
    """Insère Nord, Sud, Est dans la DB de test."""
    test_db.add(Parcelle(nom="Nord", nom_normalise="nord", ordre=1, actif=True))
    test_db.add(Parcelle(nom="Sud",  nom_normalise="sud",  ordre=2, actif=True))
    test_db.add(Parcelle(nom="Est",  nom_normalise="est",  ordre=3, actif=True))
    test_db.commit()
    return test_db


# ──────────────────────────────────────────────────────────────────────────────
# Tests de resolve_parcelle (utils/parcelles.py)
# ──────────────────────────────────────────────────────────────────────────────

class TestResolveParcelle:
    """Tests unitaires de la fonction resolve_parcelle."""

    def test_resolution_exacte(self, db_avec_parcelles):
        """Un nom exact (casse insensible) retourne la parcelle correspondante."""
        result = resolve_parcelle(db_avec_parcelles, "Nord")
        assert result is not None
        assert result.nom == "Nord"

    def test_resolution_exacte_majuscule(self, db_avec_parcelles):
        """Nom tout en majuscules → résolution correcte."""
        result = resolve_parcelle(db_avec_parcelles, "NORD")
        assert result is not None
        assert result.nom_normalise == "nord"

    def test_resolution_proche_levenshtein(self, db_avec_parcelles):
        """Nom avec 1 faute → résolution par correspondance approchée."""
        result = resolve_parcelle(db_avec_parcelles, "Nrd")   # distance 1
        assert result is not None
        assert result.nom == "Nord"

    def test_aucune_correspondance(self, db_avec_parcelles):
        """Parcelle inconnue (aucune variante proche) → retourne None."""
        # "Serre" est loin de nord/sud/est (distance > 2) → aucune résolution
        result = resolve_parcelle(db_avec_parcelles, "Serre")
        assert result is None

    def test_nom_vide(self, db_avec_parcelles):
        """Nom vide → retourne None sans erreur."""
        assert resolve_parcelle(db_avec_parcelles, "") is None

    def test_nom_none(self, db_avec_parcelles):
        """None passé → retourne None sans erreur."""
        assert resolve_parcelle(db_avec_parcelles, None) is None

    def test_nom_espaces(self, db_avec_parcelles):
        """Nom avec espaces seuls → retourne None sans erreur."""
        assert resolve_parcelle(db_avec_parcelles, "   ") is None

    def test_resolution_sous_chaine_simple(self, test_db):
        """[bug tomate cerise] 'centrale' doit résoudre vers 'planche-centrale'."""
        test_db.add(Parcelle(nom="Planche-Centrale", nom_normalise="planchecentrale", ordre=1, actif=True))
        test_db.add(Parcelle(nom="Planche-Ombre",    nom_normalise="plancheombre",    ordre=2, actif=True))
        test_db.commit()

        result = resolve_parcelle(test_db, "centrale")
        assert result is not None
        assert result.nom == "Planche-Centrale"

    def test_resolution_sous_chaine_ambigue_retient_le_plus_specifique(self, test_db):
        """Si plusieurs parcelles matchent par sous-chaîne (aucune exacte/proche par
        Levenshtein), retient celle dont la longueur normalisée est la plus proche
        du nom fourni — pas la première trouvée dans l'ordre SQL."""
        test_db.add(Parcelle(nom="Jardin-Nord",       nom_normalise="jardinnord",       ordre=1, actif=True))
        test_db.add(Parcelle(nom="Jardin-Nord-Ouest", nom_normalise="jardinnordouest",  ordre=2, actif=True))
        test_db.commit()

        # "jardinnordouestbas" contient les deux nom_normalise en sous-chaîne, mais
        # est plus proche en longueur de "jardinnordouest" (+3) que de "jardinnord" (+8)
        result = resolve_parcelle(test_db, "jardin nord ouest bas")
        assert result is not None
        assert result.nom == "Jardin-Nord-Ouest"


# ──────────────────────────────────────────────────────────────────────────────
# Tests d'intégration bot.py — _do_save_items avec parcelle inconnue
#
# [US-021] La validation "parcelle inconnue" a migré de _parse_and_save (qui ne
# fait plus que construire le récapitulatif de confirmation) vers _do_save_items,
# appelée après que l'utilisateur ait tapé "✅ Confirmer". Ces tests ciblaient
# encore _parse_and_save et étaient cassés depuis ce refactor — ils testaient
# donc une garde-fou qui n'était en réalité plus jamais exercée par eux.
# ──────────────────────────────────────────────────────────────────────────────

class TestDoSaveItemsParcelleBloquee:
    """Vérifie que _do_save_items bloque si la parcelle est introuvable."""

    @pytest.mark.asyncio
    async def test_parcelle_inconnue_bloque_sauvegarde(self, test_db):
        """Si la parcelle extraite par Groq n'existe pas, aucun événement n'est créé."""
        update_mock = MagicMock()
        update_mock.effective_message = AsyncMock()
        update_mock.effective_message.reply_text = AsyncMock()

        parsed_item = {
            "action": "plantation",
            "culture": "courgette",
            "quantite": 10,
            "unite": "plants",
            "parcelle": "Ouest",  # parcelle inexistante
            "date": None,
        }

        with patch("bot.SessionLocal", return_value=test_db), \
             patch("bot.resolve_parcelle", return_value=None):

            from bot import _do_save_items
            await _do_save_items(update_mock, [parsed_item], "planter 10 courgettes parcelle Ouest")

        # Vérifie que le message d'erreur a été envoyé
        update_mock.effective_message.reply_text.assert_called_once()
        call_args = update_mock.effective_message.reply_text.call_args
        assert "Ouest" in call_args[0][0]
        assert "n'existe pas" in call_args[0][0]

        # Vérifie qu'aucun événement n'a été persisté
        assert test_db.query(Evenement).count() == 0

    @pytest.mark.asyncio
    async def test_parcelle_connue_sauvegarde_avec_fk(self, test_db):
        """Si la parcelle est résolue, l'événement est créé avec parcelle_id renseigné."""
        parcelle_nord = Parcelle(nom="Nord", nom_normalise="nord", ordre=1, actif=True)
        test_db.add(parcelle_nord)
        test_db.commit()
        nord_id = parcelle_nord.id

        update_mock = MagicMock()
        update_mock.effective_message = AsyncMock()
        update_mock.effective_message.reply_text = AsyncMock()

        parsed_item = {
            "action": "plantation",
            "culture": "tomate",
            "quantite": 5,
            "unite": "plants",
            "parcelle": "Nord",
            "date": None,
        }

        with patch("bot.SessionLocal", return_value=test_db), \
             patch("bot.resolve_parcelle", return_value=parcelle_nord), \
             patch("bot.send_voice_reply", new_callable=AsyncMock):

            from bot import _do_save_items
            await _do_save_items(update_mock, [parsed_item], "planter 5 tomates parcelle Nord")

        # L'événement doit avoir été persisté avec la FK vers Nord
        saved = test_db.query(Evenement).filter(Evenement.culture == "tomate").one()
        assert saved.parcelle_id == nord_id


# ──────────────────────────────────────────────────────────────────────────────
# Tests flux de correction — _corr_apply avec parcelle inconnue
# ──────────────────────────────────────────────────────────────────────────────

class TestCorrApplyParcelleValidation:
    """Vérifie que _corr_apply bloque une correction vers une parcelle inconnue."""

    @pytest.mark.asyncio
    async def test_correction_parcelle_inconnue_bloque(self):
        """Si la correction demande une parcelle inconnue, _corr_apply renvoie une erreur."""
        update_mock = MagicMock()
        update_mock.message.reply_text = AsyncMock()

        ctx_mock = MagicMock()
        ctx_mock.user_data = {
            'mode': 'corr_apply',
            'corr_event_id': 10,
        }

        event_mock = MagicMock()
        event_mock.type_action = "plantation"
        event_mock.culture = "poivron"
        event_mock.variete = None
        event_mock.quantite = 10.0
        event_mock.unite = "plants"
        event_mock.parcelle = None
        event_mock.rang = None
        event_mock.duree = None
        event_mock.traitement = None
        event_mock.commentaire = None
        event_mock.date = None
        event_mock.potager_id = 1  # [US-042] doit correspondre à default_context().potager_id

        # Simuler la réponse Groq → correction parcelle inconnue
        groq_resp = MagicMock()
        groq_resp.choices[0].message.content = '{"parcelle": "bretagne"}'

        with patch("bot.SessionLocal") as mock_session_cls, \
             patch("bot.resolve_parcelle", return_value=None) as mock_resolve, \
             patch("groq.Groq") as mock_groq_cls, \
             patch("bot.MENU_KEYBOARD", None):

            mock_db = MagicMock()
            mock_db.get.return_value = event_mock
            mock_session_cls.return_value = mock_db

            mock_groq_instance = MagicMock()
            mock_groq_instance.chat.completions.create.return_value = groq_resp
            mock_groq_cls.return_value = mock_groq_instance

            from bot import _corr_apply
            await _corr_apply(update_mock, ctx_mock, "plantation sur parcelle bretagne")

        # resolve_parcelle doit avoir été appelée
        mock_resolve.assert_called_once()
        # Le mode NE doit PAS être passé en corr_confirm
        assert ctx_mock.user_data.get('mode') != 'corr_confirm'

    @pytest.mark.asyncio
    async def test_correction_parcelle_connue_normalise_et_continue(self):
        """Si la parcelle est résolue, son nom canonique remplace la valeur brute."""
        update_mock = MagicMock()
        update_mock.message.reply_text = AsyncMock()

        ctx_mock = MagicMock()
        ctx_mock.user_data = {
            'mode': 'corr_apply',
            'corr_event_id': 10,
        }

        event_mock = MagicMock()
        event_mock.type_action = "plantation"
        event_mock.culture = "poivron"
        event_mock.variete = None
        event_mock.quantite = 10.0
        event_mock.unite = "plants"
        event_mock.parcelle = None
        event_mock.rang = None
        event_mock.duree = None
        event_mock.traitement = None
        event_mock.commentaire = None
        event_mock.date = None
        event_mock.potager_id = 1  # [US-042] doit correspondre à default_context().potager_id

        parcelle_nord = MagicMock()
        parcelle_nord.nom = "Nord"
        parcelle_nord.id = 1

        groq_resp = MagicMock()
        groq_resp.choices[0].message.content = '{"parcelle": "NORD"}'

        with patch("bot.SessionLocal") as mock_session_cls, \
             patch("bot.resolve_parcelle", return_value=parcelle_nord), \
             patch("groq.Groq") as mock_groq_cls, \
             patch("bot.MENU_KEYBOARD", None):

            mock_db = MagicMock()
            mock_db.get.return_value = event_mock
            mock_session_cls.return_value = mock_db

            mock_groq_instance = MagicMock()
            mock_groq_instance.chat.completions.create.return_value = groq_resp
            mock_groq_cls.return_value = mock_groq_instance

            from bot import _corr_apply
            await _corr_apply(update_mock, ctx_mock, "plantation sur parcelle nord")

        # Le mode doit être passé en corr_confirm
        assert ctx_mock.user_data.get('mode') == 'corr_confirm'
        # La correction doit contenir le nom canonique et l'id FK
        pending = ctx_mock.user_data.get('corr_pending', {})
        assert pending.get('parcelle') == "Nord"
        assert pending.get('_parcelle_id') == 1


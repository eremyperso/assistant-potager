"""
tests/test_us069_contexte_semis.py — Semis en pépinière ou en pleine terre [US-069]
==================================================================================

Couvre les dix critères d'acceptance et les six scénarios Gherkin :

- CA1  le contexte ne vit que sur un semis
- CA2  reconnu quand il est dit — grammaire déterministe comme chemin modèle
- CA3  proposé quand il ne l'est pas, confirmé ou corrigé en un geste ;
       indéterminable → enregistré sans contexte
- CA4  corrigeable après coup, sans modèle quand la phrase ne dit que lui
- CA5  reprise des semis existants : la requête DE LA MIGRATION est exécutée
- CA6  trois totaux séparés par culture et par saison
- CA7  le contexte choisit la fenêtre conseillée du référentiel (US-068)
- CA8  aucune régression sur le stock
- CA9  l'absence de contexte ne bloque rien
- CA10 ce fichier

Aucun appel réseau : la passerelle modèle est interceptée là où un chemin
pourrait la solliciter, et les tests du CA4 vérifient qu'elle ne l'est PAS.
Les fenêtres de calendrier écrites ici sont des VALEURS DE TEST.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

import bot as bot_module
from app.services import calendrier_cultural as cal
from app.services import contexte_semis as cs
from app.services import evenements as svc_evenements
from app.services.context import TenantContext
from database.models import CultureConfig, Evenement, Parcelle, Potager, User
from llm.parseur_deterministe import ORIGINE_DETERMINISTE, parser_saisie
from utils.stock import calcul_stock_cultures

RACINE = Path(__file__).resolve().parent.parent
MIGRATION = RACINE / "migrations" / "migration_v47.sql"
CTX = TenantContext(user_id=1, potager_id=1, role="owner")
CTX_B = TenantContext(user_id=2, potager_id=2, role="owner")


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def db(test_db):
    test_db.add_all([User(id=1, email="a@potager.test"), User(id=2, email="b@potager.test")])
    test_db.flush()
    test_db.add_all([
        Potager(id=1, nom="Jardin A", proprietaire_id=1),
        Potager(id=2, nom="Jardin B", proprietaire_id=2),
    ])
    for nom, organe in (("tomate", "reproducteur"), ("carotte", "végétatif"),
                        ("courgette", "reproducteur"), ("radis", "végétatif")):
        test_db.add(CultureConfig(nom=nom, type_organe_recolte=organe))
    test_db.add_all([
        Parcelle(id=1, nom="nord", nom_normalise="nord", potager_id=1),
        Parcelle(id=2, nom="serre", nom_normalise="serre", potager_id=1, est_pepiniere=True),
    ])
    test_db.commit()
    return test_db


@pytest.fixture
def session_bot(test_engine):
    """Le bot ouvre et FERME ses sessions : il lui faut une fabrique, pas `test_db`."""
    return sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def _semis(db, culture, contexte=None, parcelle_id=None, quand=datetime(2026, 4, 12),
           quantite=10.0, unite="graines", potager_id=1):
    ev = Evenement(type_action="semis", culture=culture, quantite=quantite, unite=unite,
                   parcelle_id=parcelle_id, date=quand, contexte_semis=contexte, potager_id=potager_id)
    db.add(ev)
    db.commit()
    return ev


def _calendrier(db, culture, phase, valeur="mars-mai"):
    """Fenêtre de TEST dans la zone par défaut du potager 1."""
    cal.corriger_fenetre(db, CTX, culture, phase, valeur)


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — seul un semis porte un contexte
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1:

    def test_us069_ca1_colonne_nullable_sur_evenements(self, test_engine):
        from sqlalchemy import inspect
        colonnes = {c["name"]: c for c in inspect(test_engine).get_columns("evenements")}
        assert "contexte_semis" in colonnes
        assert colonnes["contexte_semis"]["nullable"] is True

    @pytest.mark.parametrize("action", ["plantation", "recolte", "mise_en_godet", "arrosage"])
    def test_us069_ca1_aucun_autre_geste_n_en_porte(self, action):
        assert cs.contexte_pour_action(action, "pepiniere") is None
        assert cs.contexte_depuis_saisie({"action": action}, "planté en pleine terre") is None

    def test_us069_ca1_plantation_dictee_en_pleine_terre_sans_contexte(self, db):
        ev = svc_evenements.creer_evenement_confirme(
            db, CTX, {"action": "plantation", "culture": "tomate", "quantite": 3, "unite": "plants"},
            "planté 3 tomates en pleine terre", db.get(Parcelle, 1),
        )
        assert ev.contexte_semis is None

    def test_us069_ca1_migration_pose_la_contrainte_semis_seul(self):
        sql = MIGRATION.read_text(encoding="utf-8")
        assert "CHECK (contexte_semis IS NULL OR type_action = 'semis')" in sql
        assert "ADD COLUMN IF NOT EXISTS contexte_semis" in sql
        assert (RACINE / "migrations" / "rollback_v47.sql").exists()

    def test_us069_ca1_valeur_illisible_refusee(self):
        with pytest.raises(ValueError):
            cs.normaliser_contexte("sur le balcon")
        assert cs.normaliser_contexte("Pleine terre") == cs.CONTEXTE_PLEINE_TERRE
        assert cs.normaliser_contexte("godets") == cs.CONTEXTE_PEPINIERE
        assert cs.normaliser_contexte("aucun") is None


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — reconnu quand il est dit
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2:

    @pytest.mark.parametrize("phrase,attendu", [
        ("semé 50 graines de tomate cerise en pépinière", "pepiniere"),
        ("semé des carottes rang 3 en pleine terre", "pleine_terre"),
        ("semis de radis en place", "pleine_terre"),
        ("semis direct de haricots", "pleine_terre"),
        ("semé 20 graines de poivron en godets", "pepiniere"),
        ("semé des tomates dans des barquettes", "pepiniere"),
        ("semé des tomates hors sol", "pepiniere"),
        ("semé des radis", None),
        ("semé des tomates sous abri", None),                 # une serre peut être en pleine terre
        ("semé en godets puis en pleine terre", None),       # ne tranche pas
    ])
    def test_us069_ca2_detection(self, phrase, attendu):
        assert cs.detecter_contexte(phrase) == attendu

    def test_us069_ca2_scenario_dicte_explicitement_en_pepiniere(self, db):
        """Gherkin — « semé 50 graines de tomate cerise en pépinière »."""
        texte = "semé 50 graines de tomate cerise en pépinière"
        ev = svc_evenements.creer_evenement_confirme(
            db, CTX, {"action": "semis", "culture": "tomate", "variete": "cerise",
                      "quantite": 50, "unite": "graines"}, texte, None,
        )
        assert ev.contexte_semis == cs.CONTEXTE_PEPINIERE
        # … et il n'alimente pas le stock de culture en place (CA8).
        assert "tomate" not in calcul_stock_cultures(db, potager_id=1)

    def test_us069_ca2_deux_contextes_distincts(self, db):
        a = svc_evenements.creer_evenement_confirme(
            db, CTX, {"action": "semis", "culture": "tomate", "quantite": 50, "unite": "graines"},
            "semé 50 graines de tomate cerise en pépinière", None)
        b = svc_evenements.creer_evenement_confirme(
            db, CTX, {"action": "semis", "culture": "carotte", "quantite": 3, "unite": "graines", "rang": 3},
            "semé des carottes rang 3 en pleine terre", db.get(Parcelle, 1))
        assert (a.contexte_semis, b.contexte_semis) == ("pepiniere", "pleine_terre")

    def test_us069_ca2_grammaire_deterministe_lit_le_contexte_sans_modele(self, db):
        with patch("llm.passerelle.appeler_chat") as appel:
            resultat = parser_saisie("semé 50 graines de tomate en pépinière", CTX, db=db,
                                     aujourd_hui=date(2026, 4, 12))
        appel.assert_not_called()
        assert resultat.items, resultat.raison
        item = resultat.items[0]
        assert item["origine_parsing"] == ORIGINE_DETERMINISTE
        assert (item["action"], item["culture"], item["quantite"]) == ("semis", "tomate", 50)
        assert item["contexte_semis"] == cs.CONTEXTE_PEPINIERE

    def test_us069_ca2_grammaire_sans_contexte_ne_pose_pas_la_cle(self, db):
        resultat = parser_saisie("semé 30 graines de radis", CTX, db=db, aujourd_hui=date(2026, 4, 12))
        assert resultat.items
        assert "contexte_semis" not in resultat.items[0]

    def test_us069_ca2_chemin_api_depuis_parse(self, db):
        ev = svc_evenements.creer_evenement_depuis_parse(
            db, CTX, {"action": "semis", "culture": "radis", "quantite": 30, "unite": "graines"},
            "semé 30 graines de radis en place")
        assert ev.contexte_semis == cs.CONTEXTE_PLEINE_TERRE

    def test_us069_ca2_chemin_multiligne(self, db):
        ev = svc_evenements.creer_evenement_ligne(
            db, CTX, {"action": "semis", "culture": "tomate", "quantite": 12, "unite": "graines"},
            "semé 12 tomates en godets")
        assert ev.contexte_semis == cs.CONTEXTE_PEPINIERE


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — proposé, confirmé ou corrigé en un geste
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3Proposition:

    def test_us069_ca3_referentiel_pleine_terre_seule(self, db):
        _calendrier(db, "carotte", "pleine_terre")
        proposition = cs.proposer_contexte(db, "carotte", 1)
        assert proposition.contexte == cs.CONTEXTE_PLEINE_TERRE
        assert "calendrier" in proposition.motif

    def test_us069_ca3_referentiel_pepiniere_seule(self, db):
        _calendrier(db, "tomate", "pepiniere", "février-avril")
        assert cs.proposer_contexte(db, "tomate", 1).contexte == cs.CONTEXTE_PEPINIERE

    def test_us069_ca3_duree_de_repiquage_vaut_pepiniere(self, db):
        cal.corriger_duree(db, CTX, "tomate", "repiquage", "42-56")
        assert cs.proposer_contexte(db, "tomate", 1).contexte == cs.CONTEXTE_PEPINIERE

    def test_us069_ca3_deux_fenetres_ne_tranchent_pas(self, db):
        _calendrier(db, "courgette", "pepiniere", "avril")
        _calendrier(db, "courgette", "pleine_terre", "mai-juin")
        assert cs.proposer_contexte(db, "courgette", 1) is None

    def test_us069_ca3_une_fenetre_de_plantation_n_est_pas_un_indice_de_pepiniere(self, db):
        """[US-068 / CA19, amendement du 15/09/2026] Un plant acheté se plante sans
        avoir été semé chez soi : la plantation ne départage pas les deux filières."""
        _calendrier(db, "carotte", "pleine_terre", "mai-juin")
        _calendrier(db, "carotte", "plantation", "mai")
        assert cs.proposer_contexte(db, "carotte", 1).contexte == cs.CONTEXTE_PLEINE_TERRE
        _calendrier(db, "radis", "plantation", "mai")
        assert cs.proposer_contexte(db, "radis", 1) is None

    def test_us069_ca3_sans_referentiel_rien_n_est_propose(self, db):
        assert cs.proposer_contexte(db, "radis", 1) is None
        assert cs.proposer_contexte(db, "culture-inconnue", 1) is None
        assert cs.proposer_contexte(db, None, 1) is None

    def test_us069_ca3_parcelle_pepiniere_prime(self, db):
        _calendrier(db, "carotte", "pleine_terre")
        proposition = cs.proposer_contexte(db, "carotte", 1, db.get(Parcelle, 2))
        assert proposition.contexte == cs.CONTEXTE_PEPINIERE
        assert "serre" in proposition.motif

    def test_us069_ca3_parcelle_ordinaire_n_est_pas_un_indice(self, db):
        """Point de vigilance : rattaché à une parcelle ≠ « en pleine terre »."""
        assert cs.proposer_contexte(db, "radis", 1, db.get(Parcelle, 1)) is None

    def test_us069_ca3_proposition_isolee_au_potager(self, db):
        _calendrier(db, "carotte", "pleine_terre")    # correction LOCALE au potager 1
        assert cs.proposer_contexte(db, "carotte", 2) is None

    def test_us069_ca3_proposition_non_confirmee_jamais_enregistree(self, db):
        """Une proposition restée dans `_contexte_propose` n'est pas un contexte."""
        ev = svc_evenements.creer_evenement_confirme(
            db, CTX, {"action": "semis", "culture": "carotte", "quantite": 3, "unite": "graines",
                      "_contexte_propose": "pleine_terre"}, "semé 3 graines de carotte", None)
        assert ev.contexte_semis is None

    def test_us069_ca3_referentiel_en_erreur_ne_bloque_rien(self, db):
        with patch.object(cal, "lire_calendrier", side_effect=RuntimeError("boom")):
            assert cs.proposer_contexte(db, "carotte", 1) is None


def _update_callback(data: str, user_id: int = 69):
    update = MagicMock()
    update.effective_user.id = user_id
    update.callback_query = AsyncMock()
    update.callback_query.data = data
    update.effective_message = AsyncMock()
    return update


class TestCA3Bot:

    def test_us069_ca3_scenario_carotte_proposee_en_pleine_terre(self, db, session_bot):
        """Gherkin — « semé des carottes rang 3 », le référentiel sème la carotte en
        pleine terre : le récapitulatif la propose, en un seul geste."""
        _calendrier(db, "carotte", "pleine_terre")
        items = [{"action": "semis", "culture": "carotte", "quantite": 3, "unite": "graines"}]
        with patch.object(bot_module, "SessionLocal", session_bot), \
             patch.object(bot_module, "current_context", return_value=CTX):
            bot_module._preparer_contexte_semis(items, "semé des carottes rang 3")
        assert items[0]["_contexte_propose"] == cs.CONTEXTE_PLEINE_TERRE
        assert "contexte_semis" not in items[0]

        resume = bot_module._build_action_summary(items)
        assert "Filière : *pleine terre*" in resume and "proposée" in resume
        rangees = bot_module._boutons_confirmation(items).inline_keyboard
        assert [b.callback_data for b in rangees[0]] == ["action_confirm", "action_cancel"]
        assert [b.callback_data for b in rangees[1]] == ["action_contexte:pepiniere", "action_contexte:aucun"]

    def test_us069_ca3_contexte_dit_aucune_seconde_rangee(self, session_bot, db):
        items = [{"action": "semis", "culture": "tomate", "quantite": 50}]
        with patch.object(bot_module, "SessionLocal", session_bot), \
             patch.object(bot_module, "current_context", return_value=CTX):
            bot_module._preparer_contexte_semis(items, "semé 50 graines de tomate en pépinière")
        assert items[0]["contexte_semis"] == cs.CONTEXTE_PEPINIERE
        assert len(bot_module._boutons_confirmation(items).inline_keyboard) == 1
        assert "Filière : *pépinière*" in bot_module._build_action_summary(items)

    def test_us069_ca3_indeterminable_deux_boutons_facultatifs(self, db, session_bot):
        items = [{"action": "semis", "culture": "radis", "quantite": 30}]
        with patch.object(bot_module, "SessionLocal", session_bot), \
             patch.object(bot_module, "current_context", return_value=CTX):
            bot_module._preparer_contexte_semis(items, "semé 30 radis")
        assert "_contexte_propose" not in items[0]
        assert "non précisée" in bot_module._build_action_summary(items)
        rangees = bot_module._boutons_confirmation(items).inline_keyboard
        assert [b.callback_data for b in rangees[1]] == ["action_contexte:pepiniere", "action_contexte:pleine_terre"]

    def test_us069_ca3_pas_d_interrogatoire_sur_une_dictee_multi_gestes(self, db, session_bot):
        _calendrier(db, "carotte", "pleine_terre")
        items = [{"action": "semis", "culture": "carotte"}, {"action": "arrosage", "culture": "tomate"}]
        with patch.object(bot_module, "SessionLocal", session_bot), \
             patch.object(bot_module, "current_context", return_value=CTX):
            bot_module._preparer_contexte_semis(items, "semé des carottes et arrosé les tomates")
        assert "_contexte_propose" not in items[0]
        assert len(bot_module._boutons_confirmation(items).inline_keyboard) == 1

    def test_us069_ca3_hors_semis_rien_ne_change(self):
        items = [{"action": "recolte", "culture": "tomate", "quantite": 2}]
        bot_module._preparer_contexte_semis(items, "récolté 2 kg de tomates")
        assert "Filière" not in bot_module._build_action_summary(items)
        assert len(bot_module._boutons_confirmation(items).inline_keyboard) == 1

    @pytest.mark.asyncio
    async def test_us069_ca3_confirmer_adopte_la_proposition(self):
        items = [{"action": "semis", "culture": "carotte", "_contexte_propose": "pleine_terre",
                  "_contexte_motif": "calendrier"}]
        bot_module._ACTION_PENDING[69] = {"items": items, "texte": "semé des carottes", "ts": __import__("time").time()}
        with patch.object(bot_module, "_do_save_items", new=AsyncMock()) as sauver:
            await bot_module._action_confirm_cb(_update_callback("action_confirm"), MagicMock())
        enregistres = sauver.call_args[0][1]
        assert enregistres[0]["contexte_semis"] == cs.CONTEXTE_PLEINE_TERRE
        assert "_contexte_propose" not in enregistres[0]
        assert 69 not in bot_module._ACTION_PENDING

    @pytest.mark.asyncio
    async def test_us069_ca3_corriger_en_un_geste_enregistre(self):
        items = [{"action": "semis", "culture": "carotte", "_contexte_propose": "pleine_terre"}]
        bot_module._ACTION_PENDING[69] = {"items": items, "texte": "semé des carottes", "ts": __import__("time").time()}
        with patch.object(bot_module, "_do_save_items", new=AsyncMock()) as sauver:
            await bot_module._action_confirm_cb(_update_callback("action_contexte:pepiniere"), MagicMock())
        sauver.assert_awaited_once()
        assert sauver.call_args[0][1][0]["contexte_semis"] == cs.CONTEXTE_PEPINIERE

    @pytest.mark.asyncio
    async def test_us069_ca3_sans_preciser_enregistre_sans_contexte(self, db):
        """Gherkin — semis laissé sans contexte : la phrase n'est pas relue derrière le choix."""
        items = [{"action": "semis", "culture": "carotte", "_contexte_propose": "pleine_terre"}]
        bot_module._ACTION_PENDING[69] = {"items": items, "texte": "semé des carottes", "ts": __import__("time").time()}
        with patch.object(bot_module, "_do_save_items", new=AsyncMock()) as sauver:
            await bot_module._action_confirm_cb(_update_callback("action_contexte:aucun"), MagicMock())
        item = sauver.call_args[0][1][0]
        assert "contexte_semis" in item and item["contexte_semis"] is None
        ev = svc_evenements.creer_evenement_confirme(db, CTX, dict(item, quantite=3), "semé en place 3 carottes", None)
        assert ev.contexte_semis is None

    @pytest.mark.asyncio
    async def test_us069_ca3_parse_and_save_affiche_la_proposition(self, db, session_bot):
        """Chemin complet de la confirmation : la seconde rangée est bien envoyée."""
        _calendrier(db, "carotte", "pleine_terre")
        update = MagicMock()
        update.effective_user.id = 70
        update.message = AsyncMock()
        update.callback_query = None
        item = {"action": "semis", "culture": "carotte", "quantite": 3, "unite": "graines", "parcelle": "nord"}
        with patch.object(bot_module, "SessionLocal", session_bot), \
             patch.object(bot_module, "current_context", return_value=CTX), \
             patch("app.services.context.current_context", return_value=CTX), \
             patch.object(bot_module, "_normalize_items", side_effect=lambda items, t: items), \
             patch("utils.validation.strip_culture_hallucinee", side_effect=lambda it, t: it), \
             patch.object(bot_module, "_proposer_creation_parcelle_du_geste", new=AsyncMock(return_value=False)):
            await bot_module._parse_and_save(update, "semé 3 graines de carotte parcelle nord",
                                             pre_parsed_items=[item])
        texte, kwargs = update.message.reply_text.call_args[0][0], update.message.reply_text.call_args[1]
        assert "Filière : *pleine terre*" in texte
        rangees = kwargs["reply_markup"].inline_keyboard
        assert rangees[1][0].callback_data == "action_contexte:pepiniere"
        bot_module._ACTION_PENDING.pop(70, None)


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — corrigeable après coup
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4:

    @pytest.mark.parametrize("phrase,attendu", [
        ("non, c'était en pépinière", "pepiniere"),
        ("plutôt en godets", "pepiniere"),
        ("en pleine terre, pas en pépinière", "pleine_terre"),
        ("en pépinière et non en pleine terre", "pepiniere"),
        ("c'était 30 graines en pépinière", None),     # corrige aussi une quantité
        ("c'était 3 kg", None),
    ])
    def test_us069_ca4_correction_qui_ne_dit_que_le_contexte(self, phrase, attendu):
        assert cs.correction_contexte_seule(phrase) == attendu

    def test_us069_ca4_service_corrige_le_contexte(self, db):
        ev = _semis(db, "tomate")
        corrige = svc_evenements.corriger_evenement(db, CTX, ev.id, {"contexte_semis": "pepiniere"}, " | [CORR]")
        assert corrige.contexte_semis == cs.CONTEXTE_PEPINIERE
        corrige = svc_evenements.corriger_evenement(db, CTX, ev.id, {"contexte_semis": None}, " | [CORR]")
        assert corrige.contexte_semis is None

    def test_us069_ca4_valeur_illisible_rien_n_est_ecrit(self, db):
        ev = _semis(db, "tomate", contexte="pleine_terre")
        with pytest.raises(ValueError):
            svc_evenements.corriger_evenement(db, CTX, ev.id, {"contexte_semis": "au balcon", "quantite": 99}, "x")
        db.expire_all()
        relu = db.get(Evenement, ev.id)
        assert (relu.contexte_semis, relu.quantite) == ("pleine_terre", 10.0)

    def test_us069_ca4_semis_corrige_en_plantation_perd_son_contexte(self, db):
        ev = _semis(db, "tomate", contexte="pepiniere", parcelle_id=1)
        corrige = svc_evenements.corriger_evenement(db, CTX, ev.id, {"action": "plantation"}, "x")
        assert corrige.contexte_semis is None

    def test_us069_ca4_contexte_refuse_sur_un_autre_geste(self, db):
        ev = Evenement(type_action="plantation", culture="tomate", parcelle_id=1, potager_id=1,
                       date=datetime(2026, 5, 1), quantite=2)
        db.add(ev)
        db.commit()
        with pytest.raises(ValueError):
            svc_evenements.corriger_evenement(db, CTX, ev.id, {"contexte_semis": "pepiniere"}, "x")

    def test_us069_ca4_correction_isolee_au_potager(self, db):
        ev = _semis(db, "tomate")
        assert svc_evenements.corriger_evenement(db, CTX_B, ev.id, {"contexte_semis": "pepiniere"}, "x") is None

    @pytest.mark.asyncio
    async def test_us069_ca4_bot_correction_sans_modele(self, db, session_bot):
        ev = _semis(db, "tomate")
        update = MagicMock()
        update.message = AsyncMock()
        msg_attente = AsyncMock()
        update.message.reply_text = AsyncMock(return_value=msg_attente)
        ctx = MagicMock()
        ctx.user_data = {"corr_event_id": ev.id, "mode": "corr_apply"}
        with patch.object(bot_module, "SessionLocal", session_bot), \
             patch.object(bot_module, "current_context", return_value=CTX), \
             patch.object(bot_module.passerelle, "appeler_chat") as appel:
            await bot_module._corr_apply(update, ctx, "non, c'était en pépinière")
        appel.assert_not_called()
        assert ctx.user_data["corr_pending"] == {"contexte_semis": "pepiniere"}
        resume = msg_attente.edit_text.call_args[0][0]
        assert "Filière" in resume and "sans contexte" in resume and "pépinière" in resume

        ctx.user_data["mode"] = "corr_confirm"
        with patch.object(bot_module, "SessionLocal", session_bot), \
             patch.object(bot_module, "current_context", return_value=CTX):
            await bot_module._corr_confirm(update, ctx, "✅ Confirmer")
        db.expire_all()
        relu = db.get(Evenement, ev.id)
        assert relu.contexte_semis == cs.CONTEXTE_PEPINIERE
        assert "filière" in relu.texte_original

    @pytest.mark.asyncio
    async def test_us069_ca4_bot_correction_mixte_ajoute_le_contexte_au_modele(self, db, session_bot):
        ev = _semis(db, "tomate")
        update = MagicMock()
        update.message = AsyncMock()
        msg_attente = AsyncMock()
        update.message.reply_text = AsyncMock(return_value=msg_attente)
        ctx = MagicMock()
        ctx.user_data = {"corr_event_id": ev.id, "mode": "corr_apply"}
        reponse = MagicMock(texte='{"quantite": 30, "parcelle": "pepiniere"}')
        with patch.object(bot_module, "SessionLocal", session_bot), \
             patch.object(bot_module, "current_context", return_value=CTX), \
             patch.object(bot_module.passerelle, "appeler_chat", return_value=reponse):
            await bot_module._corr_apply(update, ctx, "c'était 30 graines en pépinière")
        # « pépinière » lu comme une parcelle inexistante : retiré, le contexte reste.
        assert ctx.user_data["corr_pending"] == {"quantite": 30, "contexte_semis": "pepiniere"}

    @pytest.mark.asyncio
    async def test_us069_ca4_hors_semis_le_modele_garde_la_main(self, db, session_bot):
        ev = Evenement(type_action="recolte", culture="tomate", potager_id=1, date=datetime(2026, 7, 1), quantite=2)
        db.add(ev)
        db.commit()
        update = MagicMock()
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock(return_value=AsyncMock())
        ctx = MagicMock()
        ctx.user_data = {"corr_event_id": ev.id, "mode": "corr_apply"}
        with patch.object(bot_module, "SessionLocal", session_bot), \
             patch.object(bot_module, "current_context", return_value=CTX), \
             patch.object(bot_module.passerelle, "appeler_chat", return_value=MagicMock(texte='{"quantite": 3}')) as appel:
            await bot_module._corr_apply(update, ctx, "en pleine terre")
        appel.assert_called_once()
        assert "contexte_semis" not in ctx.user_data["corr_pending"]

    def test_us069_ca4_fmt_event_affiche_la_filiere(self, db):
        ev = _semis(db, "tomate", contexte="pepiniere")
        assert bot_module._fmt_event(ev).endswith("· pépinière")
        assert "·" not in bot_module._fmt_event(_semis(db, "radis"))


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — reprise des semis existants : la requête de la migration, telle quelle
# ═════════════════════════════════════════════════════════════════════════════
def _requete_reprise() -> str:
    sql = MIGRATION.read_text(encoding="utf-8")
    m = re.search(r"-- -- REPRISE:DEBUT --(.*?)-- -- REPRISE:FIN --", sql, re.S)
    assert m, "marqueurs REPRISE absents de migration_v47.sql"
    return m.group(1).strip().rstrip(";")


class TestCA5:

    def _godet(self, db, semis_id):
        db.add(Evenement(type_action="mise_en_godet", culture="tomate", nb_plants_godets=8,
                         origine_graines_id=semis_id, potager_id=1, date=datetime(2026, 4, 30)))
        db.commit()

    def test_us069_ca5_scenario_semis_chaine_devient_pepiniere(self, db):
        semis = _semis(db, "tomate")
        self._godet(db, semis.id)
        db.execute(text(_requete_reprise()))
        db.commit()
        db.expire_all()
        assert db.get(Evenement, semis.id).contexte_semis == cs.CONTEXTE_PEPINIERE

    def test_us069_ca5_scenario_sans_godet_reste_sans_contexte(self, db):
        courgette = _semis(db, "courgette", parcelle_id=1)
        db.execute(text(_requete_reprise()))
        db.commit()
        db.expire_all()
        assert db.get(Evenement, courgette.id).contexte_semis is None
        assert db.query(Evenement).filter(Evenement.contexte_semis == "pleine_terre").count() == 0

    def test_us069_ca5_rejouable_et_n_ecrase_pas_une_correction(self, db):
        corrige = _semis(db, "tomate", contexte="pleine_terre")
        self._godet(db, corrige.id)
        for _ in range(2):
            db.execute(text(_requete_reprise()))
            db.commit()
        db.expire_all()
        assert db.get(Evenement, corrige.id).contexte_semis == "pleine_terre"

    def test_us069_ca5_reprise_ne_touche_que_des_semis(self, db):
        plantation = Evenement(type_action="plantation", culture="tomate", potager_id=1, date=datetime(2026, 5, 2))
        db.add(plantation)
        db.commit()
        self._godet(db, plantation.id)
        db.execute(text(_requete_reprise()))
        db.commit()
        db.expire_all()
        assert db.get(Evenement, plantation.id).contexte_semis is None


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — trois totaux séparés
# ═════════════════════════════════════════════════════════════════════════════
class TestCA6:

    def test_us069_ca6_scenario_trois_totaux_par_culture(self, db):
        _semis(db, "tomate", "pepiniere")
        _semis(db, "tomate", "pepiniere", quantite=5)
        _semis(db, "tomate", "pleine_terre")
        _semis(db, "tomate", None)
        _semis(db, "radis", "pleine_terre", quantite=1, unite="m²")
        lignes = {l.culture: l for l in cs.semis_par_contexte(db, 1)}
        tomate = lignes["tomate"]
        assert (tomate.pepiniere, tomate.pleine_terre, tomate.sans_contexte) == (2, 1, 1)
        assert tomate.quantites["pepiniere"] == {"graines": 15.0}
        assert lignes["radis"].quantites["pleine_terre"] == {"m²": 1.0}

    def test_us069_ca6_par_saison(self, db):
        _semis(db, "tomate", "pepiniere", quand=datetime(2025, 3, 1))
        _semis(db, "tomate", "pleine_terre", quand=datetime(2026, 5, 1))
        lignes = cs.semis_par_contexte(db, 1)
        assert [(l.saison, l.pepiniere, l.pleine_terre) for l in lignes] == [(2026, 0, 1), (2025, 1, 0)]
        assert [l.saison for l in cs.semis_par_contexte(db, 1, saison=2025)] == [2025]

    def test_us069_ca6_date_ref_et_isolation(self, db):
        _semis(db, "tomate", "pepiniere", quand=datetime(2026, 6, 1))
        _semis(db, "tomate", "pepiniere", potager_id=2)
        assert cs.semis_par_contexte(db, 1, date_ref=date(2026, 5, 1)) == []
        assert cs.semis_par_contexte(db, 1)[0].pepiniere == 1

    def test_us069_ca6_formatage_bot_sans_contexte_explicite(self, db):
        _semis(db, "tomate", "pepiniere")
        _semis(db, "tomate", None)
        _semis(db, "carotte", "pleine_terre")
        bloc = "\n".join(cs.formater_semis_par_contexte_telegram(cs.semis_par_contexte(db, 1), 2026))
        assert "saison 2026" in bloc
        assert "tomate : 🪴 1 en pépinière · 🌿 0 en pleine terre · ❔ 1 sans contexte" in bloc
        assert "carotte : 🪴 0 en pépinière · 🌿 1 en pleine terre" in bloc
        assert cs.formater_semis_par_contexte_telegram([], 2026) == []

    @pytest.mark.asyncio
    async def test_us069_ca6_cmd_stats_affiche_le_bloc(self, db, session_bot):
        _semis(db, "tomate", "pepiniere", quand=datetime(2026, 4, 1))
        update = MagicMock()
        update.effective_message = AsyncMock()
        ctx = MagicMock()
        ctx.args = ["2026-09-01"]
        with patch.object(bot_module, "SessionLocal", session_bot), \
             patch.object(bot_module, "current_context", return_value=CTX), \
             patch.object(bot_module, "_send_chunked", new=AsyncMock()) as envoi, \
             patch.object(bot_module, "send_voice_reply", new=AsyncMock()):
            await bot_module.cmd_stats(update, ctx)
        texte = envoi.call_args[0][1]
        assert "Semis par filière — saison 2026" in texte
        assert "tomate : 🪴 1 en pépinière" in texte


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — le contexte choisit la fenêtre conseillée
# ═════════════════════════════════════════════════════════════════════════════
class TestCA7:

    def test_us069_ca7_phases(self):
        assert cs.phase_du_contexte("pepiniere") == cal.PHASE_SEMIS_PEPINIERE
        assert cs.phase_du_contexte("pleine_terre") == cal.PHASE_SEMIS_PLEINE_TERRE
        assert cs.phase_du_contexte(None) is None

    def test_us069_ca7_fenetre_du_contexte(self, db):
        _calendrier(db, "courgette", "pepiniere", "avril")
        _calendrier(db, "courgette", "pleine_terre", "mai-juin")
        en_godet = _semis(db, "courgette", "pepiniere")
        en_place = _semis(db, "courgette", "pleine_terre")
        assert (cs.fenetre_conseillee(db, en_godet).mois_debut,) == (4,)
        assert (cs.fenetre_conseillee(db, en_place).mois_debut, cs.fenetre_conseillee(db, en_place).mois_fin) == (5, 6)

    def test_us069_ca7_sans_contexte_mode_degrade(self, db):
        _calendrier(db, "courgette", "pleine_terre", "mai-juin")
        assert cs.fenetre_conseillee(db, _semis(db, "courgette", None)) is None

    def test_us069_ca7_rien_n_est_emprunte_a_l_autre_filiere(self, db):
        _calendrier(db, "courgette", "pleine_terre", "mai-juin")
        assert cs.fenetre_conseillee(db, _semis(db, "courgette", "pepiniere")) is None


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — aucune régression sur le stock
# ═════════════════════════════════════════════════════════════════════════════
class TestCA8:

    def _instantane(self, stocks):
        return {c: (s.stock_plants if hasattr(s, "stock_plants") else None, repr(s)) for c, s in stocks.items()}

    def test_us069_ca8_le_contexte_ne_change_pas_le_stock(self, db):
        _semis(db, "radis", "pleine_terre", parcelle_id=1, quantite=40)
        _semis(db, "tomate", "pepiniere", parcelle_id=2, quantite=30)
        _semis(db, "carotte", None, parcelle_id=1, quantite=20)
        _semis(db, "courgette", "pleine_terre", parcelle_id=None, quantite=6)  # contexte ≠ parcelle
        avec = self._instantane(calcul_stock_cultures(db, potager_id=1))

        db.query(Evenement).update({Evenement.contexte_semis: None})
        db.commit()
        sans = self._instantane(calcul_stock_cultures(db, potager_id=1))
        assert avec == sans

    def test_us069_ca8_pepiniere_hors_stock_pleine_terre_au_stock(self, db):
        _semis(db, "tomate", "pepiniere", parcelle_id=2)
        _semis(db, "radis", "pleine_terre", parcelle_id=1)
        stocks = calcul_stock_cultures(db, potager_id=1)
        assert "radis" in stocks
        assert "tomate" not in stocks

    def test_us069_ca8_chainage_godet_inchange(self, db):
        semis = _semis(db, "tomate", "pepiniere", quantite=20)
        godet = svc_evenements.creer_evenement_godet(
            db, CTX, {"action": "mise_en_godet", "culture": "tomate", "nb_plants_godets": 8}, "mis 8 tomates en godet")
        assert godet.origine_graines_id == semis.id
        assert godet.contexte_semis is None


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — l'absence de contexte ne bloque rien
# ═════════════════════════════════════════════════════════════════════════════
class TestCA9:

    def test_us069_ca9_scenario_semis_sans_contexte_enregistre(self, db):
        ev = svc_evenements.creer_evenement_confirme(
            db, CTX, {"action": "semis", "culture": "radis", "quantite": 30, "unite": "graines"},
            "semé 30 graines de radis", None)
        assert ev.id and ev.contexte_semis is None
        assert cs.semis_par_contexte(db, 1)[0].sans_contexte == 1
        assert cs.fenetre_conseillee(db, ev) is None
        assert "· " not in bot_module._fmt_event(ev)

    def test_us069_ca9_api_stats_expose_les_trois_totaux(self, monkeypatch):
        import main
        from fastapi.testclient import TestClient
        from sqlalchemy import create_engine
        from sqlalchemy.pool import StaticPool
        from database.db import Base

        moteur = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                               poolclass=StaticPool)
        Base.metadata.create_all(bind=moteur)
        session = sessionmaker(bind=moteur)()
        _semis(session, "tomate", "pepiniere")
        _semis(session, "tomate", None)
        session.close()
        monkeypatch.setattr(main, "SessionLocal", sessionmaker(bind=moteur))
        main.app.dependency_overrides[main.get_current_user_ctx] = lambda: CTX
        try:
            with patch.object(main, "ctx_pour_potager_consulte", side_effect=lambda d, c, p: c):
                reponse = TestClient(main.app).get("/stats?date_ref=2026-09-01")
        finally:
            main.app.dependency_overrides.pop(main.get_current_user_ctx, None)
            moteur.dispose()
        assert reponse.status_code == 200
        corps = reponse.json()
        assert corps["semis_par_contexte"] == [{
            "saison": 2026, "culture": "tomate", "pepiniere": 1, "pleine_terre": 0,
            "sans_contexte": 1, "total": 2,
            "quantites": {"pepiniere": {"graines": 10.0}, "sans_contexte": {"graines": 10.0}},
        }]
        assert "semis_pleine_terre" in corps and "stock_par_culture" in corps

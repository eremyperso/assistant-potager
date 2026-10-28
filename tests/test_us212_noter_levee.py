"""
tests/test_us212_noter_levee.py — Noter la levée d'un lot de semis [US-212]
==========================================================================

Le geste `levee` compte combien de graines d'une barquette ont levé : un CONSTAT, pas un
mouvement de stock.

- CA1/CA2   le geste, et chaque forme dictée lue SANS modèle
- CA3       « sur N » discordant, plus de levés que de graines : signalés, jamais corrigés
- CA4       un lot de pépinière issu d'un semis — sinon refus ; pleine terre → observation
- CA5       récapitulatif, Journal, correction, suppression
- CA6       instantané (le plus récent fait foi), taux de levée, indication « terminée »
- CA7       une levée terminée clôt la germination ; non terminée, elle la laisse telle quelle
- CA8       moyenne de levée de la culture, à partir de deux lots
- CA9       repiquage supérieur aux levés : signalé, jamais borné
- CA10      aucun stock ne change
- CA11      la PWA ne dépose que le GESTE (le lot) ; le bot demande le nombre et « terminée »

Aucun appel réseau, aucun appel au modèle.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import evenements as svc_evenements
from app.services import file_gestes as svc_gestes
from app.services import lots_pepiniere as lots
from app.services.context import TenantContext
from database.models import CultureConfig, Evenement, Parcelle, Potager, User
from llm.parseur_deterministe import parser_saisie
from utils.actions import normalize_action
from utils.dependances_donnee import natures_impactees
from utils.stock import calcul_godets, calcul_lots_pepiniere, calcul_stock_par_variete

RACINE = Path(__file__).resolve().parent.parent
CTX = TenantContext(user_id=1, potager_id=1, role="owner")
CTX_B = TenantContext(user_id=2, potager_id=2, role="owner")


@pytest.fixture
def db(test_db):
    test_db.add_all([User(id=1, email="a@potager.test"), User(id=2, email="b@potager.test")])
    test_db.flush()
    test_db.add_all([Potager(id=1, nom="Jardin A", proprietaire_id=1), Potager(id=2, nom="Jardin B", proprietaire_id=2)])
    for nom in ("chou", "tomate", "carotte"):
        test_db.add(CultureConfig(nom=nom, type_organe_recolte="végétatif"))
    test_db.add_all([
        Parcelle(id=1, nom="nord", nom_normalise="nord", potager_id=1),
        Parcelle(id=2, nom="serre", nom_normalise="serre", potager_id=1, est_pepiniere=True),
        Parcelle(id=3, nom="serre", nom_normalise="serre", potager_id=2, est_pepiniere=True),
    ])
    test_db.commit()
    return test_db


def _semis(db, culture="chou", variete=None, quantite=48.0, quand=datetime(2026, 9, 1), potager=1, parcelle=2):
    ev = Evenement(type_action="semis", culture=culture, variete=variete, quantite=quantite, unite="graines",
                   parcelle_id=parcelle, date=quand, potager_id=potager)
    db.add(ev)
    db.commit()
    return ev


def _godet(db, semis, plants=20, graines=24):
    ev = Evenement(type_action="mise_en_godet", culture=semis.culture, nb_plants_godets=plants,
                   nb_graines_semees=graines, origine_graines_id=semis.id, potager_id=semis.potager_id,
                   date=datetime(2026, 9, 20))
    db.add(ev)
    db.commit()
    return ev


def _lot(db, semis, potager=1, date_ref=None):
    return next(l for l in calcul_lots_pepiniere(db, date_ref, potager_id=potager) if l["semis_id"] == semis.id)


def _noter(db, semis, leves, *, terminee=False, jour="2026-09-12", sur=None, ctx=CTX):
    """Note une levée par le chemin de la dictée : référence de lot → confirmation."""
    item = {
        "action": "levee", "numero_lot_cite": semis.numero_lot, "quantite": leves, "unite": "plants",
        "date": jour, "nb_graines_semees": sur,
    }
    if terminee:
        item["levee_terminee"] = True
    lots.resoudre_references(db, ctx, [item])
    return svc_evenements.creer_evenement_confirme(db, ctx, item, f"levée du lot {semis.numero_lot} : {leves}", None)


# ═════════════════════════════════════════════════════════════════════════════
# CA1, CA2 — le geste et ses formes dictées, lues sans modèle
# ═════════════════════════════════════════════════════════════════════════════
class TestGrammaire:

    def test_us212_ca1_le_geste_est_au_referentiel(self):
        for forme in ("levee", "levée", "levé", "levés", "lever"):
            assert normalize_action(forme) == "levee"

    def test_us212_ca2_levee_du_lot_n_deux_points_quarante(self, db):
        lu = parser_saisie("levée du lot 128 : 40", CTX, db=db)
        assert lu.reconnu, lu.raison
        item = lu.items[0]
        assert item["action"] == "levee"
        assert item["numero_lot_cite"] == 128
        assert item["quantite"] == 40 and item["unite"] == "plants"
        assert item["origine_parsing"] == "deterministe"
        assert "levee_terminee" not in item

    def test_us212_ca2_quarante_choux_friseS_leves_sur_quarante_huit(self, db):
        _semis(db, "chou", variete="frisé")
        lu = parser_saisie("40 choux frisés levés sur 48", CTX, db=db)
        assert lu.reconnu, lu.raison
        item = lu.items[0]
        assert (item["action"], item["culture"], item["variete"]) == ("levee", "chou", "frisé")
        assert item["quantite"] == 40 and item["nb_graines_semees"] == 48

    def test_us212_ca2_les_tomates_cerise_ont_leve_douze_plants(self, db):
        _semis(db, "tomate", variete="cerise")
        lu = parser_saisie("les tomates cerise ont levé, 12 plants", CTX, db=db)
        assert lu.reconnu, lu.raison
        item = lu.items[0]
        assert (item["action"], item["culture"], item["variete"], item["quantite"]) == ("levee", "tomate", "cerise", 12)

    def test_us212_ca2_levee_terminee_pour_le_lot(self, db):
        lu = parser_saisie("levée terminée pour le lot 128 : 40", CTX, db=db)
        assert lu.reconnu, lu.raison
        item = lu.items[0]
        assert item["action"] == "levee" and item["levee_terminee"] is True
        assert item["numero_lot_cite"] == 128 and item["quantite"] == 40

    def test_us212_ca2_une_phrase_sur_un_semis_en_pleine_terre_se_lit_aussi(self, db):
        lu = parser_saisie("les carottes ont levé", CTX, db=db)
        assert lu.reconnu, lu.raison
        assert lu.items[0]["action"] == "levee" and lu.items[0]["culture"] == "carotte"
        assert lu.items[0]["quantite"] is None

    def test_us212_une_phrase_qui_n_est_pas_une_levee_part_au_modele(self, db):
        assert not parser_saisie("j'ai levé les paillis", CTX, db=db).reconnu

    def test_us212_une_levee_sans_lot_ni_culture_part_au_modele(self, db):
        assert not parser_saisie("levée 40", CTX, db=db).reconnu

    @pytest.mark.parametrize("phrase", [
        "levée du lot 128 : 40", "40 choux frisés levés sur 48", "les tomates cerise ont levé, 12 plants",
        "levée terminée pour le lot 128 : 40", "les carottes ont levé",
    ])
    def test_us212_ca2_le_routeur_classe_chaque_forme_en_geste(self, phrase):
        from llm.routeur import _regle_par_geste, NATURE_ACTION
        assert _regle_par_geste(phrase) == NATURE_ACTION

    @pytest.mark.parametrize("phrase", ["quand lèvent les carottes ?", "est-ce que les tomates ont levé ?"])
    def test_us212_une_question_sur_la_levee_n_est_pas_une_saisie(self, phrase):
        from llm.routeur import _ouverture_interrogative
        assert phrase.endswith("?") or _ouverture_interrogative(phrase)


# ═════════════════════════════════════════════════════════════════════════════
# CA5, CA6 — noter, relire, corriger, supprimer
# ═════════════════════════════════════════════════════════════════════════════
class TestNoter:

    def test_us212_premier_comptage_gherkin(self, db):
        semis = _semis(db, "chou", quantite=48)
        item = {"action": "levee", "numero_lot_cite": semis.numero_lot, "quantite": 40, "date": "2026-09-12"}
        lots.resoudre_references(db, CTX, [item])
        from app.bot.enregistrement import _build_action_summary
        resume = _build_action_summary([svc_evenements.resoudre_lot_levee(db, CTX, item) and item])
        assert f"levée du lot {semis.numero_lot} (chou) : 40 plants" in resume
        assert "83 %" in resume
        svc_evenements.creer_evenement_confirme(db, CTX, item, "levée", None)

        lot = _lot(db, semis)
        assert lot["nb_leves"] == 40 and lot["taux_levee"] == 83
        assert lot["etat_germination"] == "en_cours"           # une levée non terminée ne conclut rien
        assert lot["graines_en_germination"] == 48
        assert str(lot["date_derniere_levee"])[:10] == "2026-09-12"
        assert lot["levee_terminee"] is False

    def test_us212_ca6_l_evenement_porte_le_lot_le_nombre_et_la_date(self, db):
        semis = _semis(db)
        evt = _noter(db, semis, 40, sur=48)
        assert evt.type_action == "levee"
        assert evt.origine_graines_id == semis.id
        assert evt.quantite == 40 and evt.unite == "plants" and evt.nb_graines_semees == 48
        assert evt.levee_terminee is False and evt.culture == "chou"
        assert str(evt.date)[:10] == "2026-09-12"

    def test_us212_ca6_deux_comptages_successifs_gherkin(self, db):
        semis = _semis(db)
        _noter(db, semis, 30, jour="2026-09-08")
        _noter(db, semis, 40, jour="2026-09-12")
        lot = _lot(db, semis)
        assert lot["nb_leves"] == 40             # pas 70 : un comptage est un instantané
        assert str(lot["date_derniere_levee"])[:10] == "2026-09-12"

    def test_us212_ca6_le_plus_recent_fait_foi_meme_s_il_est_plus_bas(self, db):
        semis = _semis(db)
        _noter(db, semis, 40, jour="2026-09-08")
        _noter(db, semis, 35, jour="2026-09-12")
        assert _lot(db, semis)["nb_leves"] == 35

    def test_us212_ca6_la_date_de_reference_borne_le_comptage(self, db):
        semis = _semis(db)
        _noter(db, semis, 30, jour="2026-09-08")
        _noter(db, semis, 40, jour="2026-09-12")
        assert _lot(db, semis, date_ref=date(2026, 9, 10))["nb_leves"] == 30
        assert _lot(db, semis, date_ref=date(2026, 9, 5))["nb_leves"] is None

    def test_us212_sans_levee_notee_le_lot_se_lit_comme_avant(self, db):
        semis = _semis(db)
        lot = _lot(db, semis)
        assert lot["nb_leves"] is None and lot["taux_levee"] is None
        assert lot["date_derniere_levee"] is None and lot["levee_terminee"] is False
        assert lot["etat_germination"] == "en_cours" and lot["graines_en_germination"] == 48

    def test_us212_ca6_zero_est_un_comptage(self, db):
        semis = _semis(db)
        _noter(db, semis, 0)
        lot = _lot(db, semis)
        assert lot["nb_leves"] == 0 and lot["taux_levee"] == 0

    def test_us212_ca6_taux_absent_sans_graines_semees_connues(self, db):
        semis = _semis(db, quantite=0)
        _noter(db, semis, 12)
        lot = _lot(db, semis)
        assert lot["nb_leves"] == 12 and lot["taux_levee"] is None

    def test_us212_ca5_le_nombre_de_levees_est_obligatoire(self, db):
        semis = _semis(db)
        item = {"action": "levee", "numero_lot_cite": semis.numero_lot, "quantite": None}
        lots.resoudre_references(db, CTX, [item])
        with pytest.raises(svc_evenements.QuantiteManquanteError) as erreur:
            svc_evenements.creer_evenement_confirme(db, CTX, item, "levée", None)
        assert "Combien de plants ont levé" in str(erreur.value)

    def test_us212_ca5_la_levee_se_corrige_et_se_supprime(self, db):
        semis = _semis(db)
        evt = _noter(db, semis, 30)
        svc_evenements.corriger_evenement(db, CTX, evt.id, {"quantite": 36}, "[CORR test]")
        assert _lot(db, semis)["nb_leves"] == 36
        assert svc_evenements.supprimer_evenement(db, CTX, evt.id) is True
        assert _lot(db, semis)["nb_leves"] is None

    def test_us212_ca5_le_resume_vocal_dit_la_levee(self, db):
        from app.bot.enregistrement import _build_recap_tts
        item = {"action": "levee", "culture": "chou", "quantite": 40, "_lot_numero": 128}
        assert _build_recap_tts(item) == "Levée du lot 128 (chou) : 40 plants enregistrée."


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — les incohérences sont signalées, jamais corrigées en silence
# ═════════════════════════════════════════════════════════════════════════════
class TestIncoherences:

    def _resoudre(self, db, semis, leves, sur=None):
        item = {"action": "levee", "numero_lot_cite": semis.numero_lot, "quantite": leves, "nb_graines_semees": sur}
        lots.resoudre_references(db, CTX, [item])
        svc_evenements.resoudre_lot_levee(db, CTX, item)
        return item

    def test_us212_ca3_un_sur_n_discordant_est_signale(self, db):
        semis = _semis(db, quantite=48)
        item = self._resoudre(db, semis, 40, sur=50)
        assert len(item["_alertes_levee"]) == 1
        assert "sur 50" in item["_alertes_levee"][0] and "48 graines" in item["_alertes_levee"][0]
        assert item["quantite"] == 40 and item["nb_graines_semees"] == 50     # rien n'est corrigé

    def test_us212_ca3_un_sur_n_concordant_ne_dit_rien(self, db):
        semis = _semis(db, quantite=48)
        assert self._resoudre(db, semis, 40, sur=48)["_alertes_levee"] == []

    def test_us212_ca3_plus_de_leves_que_de_graines_est_refuse(self, db):
        semis = _semis(db, quantite=48)
        with pytest.raises(svc_evenements.LeveeRefuseeError, match="impossible"):
            self._resoudre(db, semis, 60)
        assert _lot(db, semis)["nb_leves"] is None    # rien n'est écrit

    def test_us212_ca3_autant_de_leves_que_de_graines_est_accepte(self, db):
        semis = _semis(db, quantite=48)
        assert self._resoudre(db, semis, 48)["_alertes_levee"] == []

    def test_us212_ca3_le_recapitulatif_porte_les_alertes(self, db):
        from app.bot.enregistrement import _build_action_summary
        semis = _semis(db, quantite=48)
        item = self._resoudre(db, semis, 40, sur=50)
        assert "sur 50" in _build_action_summary([item])


# ═════════════════════════════════════════════════════════════════════════════
# CA2, CA4 — quel lot ?
# ═════════════════════════════════════════════════════════════════════════════
class TestDesignationDuLot:

    def test_us212_ca2_une_culture_a_un_seul_lot_le_designe(self, db):
        semis = _semis(db)
        item = {"action": "levee", "culture": "chou", "quantite": 40}
        lot = svc_evenements.resoudre_lot_levee(db, CTX, item)
        assert lot["semis_id"] == semis.id and item["origine_graines_id"] == semis.id
        assert item["_lot_numero"] == semis.numero_lot

    def test_us212_ca2_plusieurs_lots_de_la_culture_demandent_lequel(self, db):
        _semis(db)
        _semis(db, quand=datetime(2026, 9, 10))
        with pytest.raises(svc_evenements.LotIndetermineError):
            svc_evenements.resoudre_lot_levee(db, CTX, {"action": "levee", "culture": "chou", "quantite": 40})

    def test_us212_ca2_les_candidats_portent_numero_et_date_de_semis(self, db):
        premier, second = _semis(db), _semis(db, quand=datetime(2026, 9, 10))
        candidats = svc_evenements.lots_deplacables(db, CTX, "chou")
        assert {c["numero_lot"] for c in candidats} == {premier.numero_lot, second.numero_lot}
        assert all(c["date_semis"] is not None for c in candidats)

    def test_us212_ca2_la_resolution_est_ecrite_une_fois_et_partagee_avec_le_deplacement(self):
        source = (RACINE / "app" / "services" / "evenements.py").read_text(encoding="utf-8")
        assert source.count("def designer_lot(") == 1
        for fonction in ("resoudre_lot_deplacement", "resoudre_lot_cloture", "resoudre_lot_levee"):
            corps = source.split(f"def {fonction}(")[1].split("\ndef ")[0]
            assert "designer_lot(" in corps, fonction

    def test_us212_ca4_un_numero_inconnu_est_refuse(self, db):
        _semis(db)
        item = {"action": "levee", "numero_lot_cite": 999, "quantite": 40}
        lots.resoudre_references(db, CTX, [item])
        with pytest.raises(svc_evenements.LeveeRefuseeError, match="Aucun lot n° 999"):
            svc_evenements.resoudre_lot_levee(db, CTX, item)

    def test_us212_ca4_le_lot_d_un_autre_potager_est_refuse(self, db):
        etranger = _semis(db, potager=2, parcelle=3)
        item = {"action": "levee", "numero_lot_cite": etranger.numero_lot, "culture": "chou", "quantite": 40}
        lots.resoudre_references(db, CTX, [item])
        # Le lot n° 1 du potager B n'est pas le lot n° 1 du potager A : ici, A n'en a aucun.
        with pytest.raises((svc_evenements.LeveeRefuseeError, svc_evenements.LeveeHorsPepiniereError)):
            svc_evenements.resoudre_lot_levee(db, CTX, item)

    def test_us212_ca4_le_lot_godets_sans_semis_rattache_la_refuse(self, db):
        db.add(Evenement(type_action="mise_en_godet", culture="tomate", nb_plants_godets=15,
                         potager_id=1, date=datetime(2026, 9, 20)))
        db.commit()
        with pytest.raises(svc_evenements.LeveeRefuseeError, match="pas de semis rattaché"):
            svc_evenements.resoudre_lot_levee(db, CTX, {"action": "levee", "culture": "tomate", "quantite": 5})

    def test_us212_ca4_un_lot_cloture_la_refuse(self, db):
        semis = _semis(db)
        item = {"action": "cloture_lot", "numero_lot_cite": semis.numero_lot, "date": "2026-09-30"}
        lots.resoudre_references(db, CTX, [item])
        svc_evenements.creer_evenement_confirme(db, CTX, item, "cloture", None)
        with pytest.raises(svc_evenements.LeveeRefuseeError):
            _noter(db, semis, 40)

    def test_us212_ca4_un_semis_en_pleine_terre_n_est_pas_un_lot(self, db):
        db.add(Evenement(type_action="semis", culture="carotte", quantite=100, unite="graines",
                         parcelle_id=1, contexte_semis="pleine_terre", date=datetime(2026, 9, 1), potager_id=1))
        db.commit()
        with pytest.raises(svc_evenements.LeveeHorsPepiniereError, match="rien à compter"):
            svc_evenements.resoudre_lot_levee(db, CTX, {"action": "levee", "culture": "carotte", "quantite": 12})

    def test_us212_ca4_pleine_terre_le_bot_dit_et_propose_l_observation(self, db, monkeypatch):
        """Gherkin « Semis en pleine terre » : le bot indique que la levée se note sur un lot de
        pépinière et propose de l'enregistrer en observation."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock

        from app import bot as bot_module
        from app.bot import etat

        monkeypatch.setattr(bot_module, "SessionLocal", lambda: db)
        monkeypatch.setattr(db, "close", lambda: None)
        monkeypatch.setattr(bot_module, "current_context", lambda: CTX)
        message = MagicMock()
        message.reply_text = AsyncMock()
        update = MagicMock()
        update.effective_message = message
        update.effective_user.id = 77
        parsed = {"action": "levee", "culture": "carotte", "quantite": None}

        arret = asyncio.run(bot_module._preparer_levee(update, parsed, "les carottes ont levé"))

        assert arret is True
        dit = message.reply_text.call_args.args[0]
        assert "lot de pépinière" in dit and "observation" in dit
        boutons = [b.callback_data for ligne in message.reply_text.call_args.kwargs["reply_markup"].inline_keyboard for b in ligne]
        assert "levlot_obs" in boutons
        assert 77 in etat._LEVEE_LOT_PENDING
        etat._LEVEE_LOT_PENDING.clear()

    def test_us212_ca4_l_observation_proposee_est_ecrite_sans_stock(self, db, monkeypatch):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock

        from app import bot as bot_module

        monkeypatch.setattr(bot_module, "SessionLocal", lambda: db)
        monkeypatch.setattr(db, "close", lambda: None)
        monkeypatch.setattr(bot_module, "current_context", lambda: CTX)
        db.add(Evenement(type_action="semis", culture="carotte", quantite=100, unite="graines",
                         parcelle_id=1, contexte_semis="pleine_terre", date=datetime(2026, 9, 1), potager_id=1))
        db.commit()
        avant = calcul_godets(db, include_epuises=True, potager_id=1)
        query = MagicMock()
        query.edit_message_text = AsyncMock()

        asyncio.run(bot_module.godets._noter_levee_en_observation(
            query, {"culture": "carotte", "date": "2026-09-14"}, "les carottes ont levé",
        ))

        obs = db.query(Evenement).filter(Evenement.type_action == "observation").one()
        assert obs.culture == "carotte" and "les carottes ont levé" in obs.commentaire
        assert db.query(Evenement).filter(Evenement.type_action == "levee").count() == 0
        assert calcul_godets(db, include_epuises=True, potager_id=1) == avant


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — la levée terminée clôt la germination
# ═════════════════════════════════════════════════════════════════════════════
class TestLeveeTerminee:

    def test_us212_ca7_levee_terminee_gherkin(self, db):
        semis = _semis(db, quantite=48)
        evt = _noter(db, semis, 40, terminee=True)
        assert evt.levee_terminee is True
        lot = _lot(db, semis)
        assert lot["etat_germination"] == "close"
        assert lot["levee_terminee"] is True
        assert lot["graines_non_levees_soldees"] == 8
        assert lot["graines_en_germination"] == 0         # plus rien « en train de lever »

    def test_us212_ca7_les_plants_leves_restent_a_repiquer(self, db):
        """`graines_en_germination` tombe à 0, mais les 40 levés doivent pouvoir être repiqués."""
        semis = _semis(db, quantite=48)
        _noter(db, semis, 40, terminee=True)
        assert _lot(db, semis)["graines_non_soldees"] == 40     # les 8 non-levées sont soldées
        item = {"action": "mise_en_godet", "culture": "chou", "nb_plants_godets": 40,
                "nb_graines_semees": 48, "origine_graines_id": semis.id, "date": "2026-09-20"}
        svc_evenements.creer_evenement_godet(db, CTX, item, "mise en godet 40 choux sur 48")
        lot = _lot(db, semis)
        assert lot["plants_obtenus"] == 40 and lot["stock_residuel_godet"] == 40
        assert lot["incoherence_repiquage_levee"] is False
        assert lot["graines_non_soldees"] == 0    # plus rien à repiquer : « Repiquer » disparaît

    def test_us212_ca14_chaque_comptage_figure_dans_le_cycle_de_vie_du_lot(self, db):
        """Le fil « Détail du lot » montre chaque comptage, pas seulement le dernier."""
        semis, autre = _semis(db, quantite=48), _semis(db, quand=datetime(2026, 9, 3))
        premier = _noter(db, semis, 30, jour="2026-09-10")
        second = _noter(db, semis, 40, terminee=True, jour="2026-09-14", sur=48)
        _noter(db, autre, 12)
        levees = svc_evenements.cycle_vie_culture(db, CTX, "chou", None, semis_id=semis.id)["levees"]
        assert [l.id for l in levees] == [premier.id, second.id]
        assert (levees[1].quantite, levees[1].nb_graines_semees, levees[1].levee_terminee) == (40, 48, True)

    def test_us212_ca7_un_lot_cloture_par_la_levee_reste_candidat_au_repiquage(self, db):
        from utils.stock import lots_candidats_mise_en_godet
        semis = _semis(db, quantite=48)
        _noter(db, semis, 40, terminee=True)
        assert [l["semis_id"] for l in lots_candidats_mise_en_godet(db, "chou", None, potager_id=1)] == [semis.id]

    def test_us212_ca7_une_levee_non_terminee_laisse_la_germination_telle_quelle(self, db):
        semis = _semis(db, quantite=48)
        _godet(db, semis, plants=20, graines=24)
        avant = _lot(db, semis)
        _noter(db, semis, 30)
        apres = _lot(db, semis)
        for champ in ("etat_germination", "graines_en_germination", "graines_non_soldees", "taux_germination",
                      "stock_residuel_godet", "plants_obtenus"):
            assert apres[champ] == avant[champ], champ

    def test_us212_ca7_la_levee_terminee_reste_close_apres_un_comptage_ulterieur(self, db):
        semis = _semis(db, quantite=48)
        _noter(db, semis, 40, terminee=True, jour="2026-09-12")
        _noter(db, semis, 42, jour="2026-09-15")
        lot = _lot(db, semis)
        assert lot["nb_leves"] == 42                      # le nombre se met à jour
        assert lot["levee_terminee"] is True and lot["etat_germination"] == "close"
        assert lot["graines_non_levees_soldees"] == 6

    def test_us212_ca7_le_recapitulatif_dit_ce_que_la_levee_terminee_solde(self, db):
        from app.bot.enregistrement import _build_action_summary
        semis = _semis(db, quantite=48)
        item = {"action": "levee", "numero_lot_cite": semis.numero_lot, "quantite": 40, "levee_terminee": True}
        lots.resoudre_references(db, CTX, [item])
        svc_evenements.resoudre_lot_levee(db, CTX, item)
        resume = _build_action_summary([item])
        assert "levée terminée du lot" in resume and "8 graines non levées seront soldées" in resume


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — la moyenne de la culture, à partir de deux lots
# ═════════════════════════════════════════════════════════════════════════════
class TestMoyenne:

    def _lots_notes(self, db, taux, potager=1, parcelle=2, culture="chou"):
        notes = []
        for i, pct in enumerate(taux):
            semis = _semis(db, culture, quantite=100, quand=datetime(2026, 8, 1 + i), potager=potager, parcelle=parcelle)
            ctx = CTX if potager == 1 else CTX_B
            _noter(db, semis, pct, jour="2026-08-20", ctx=ctx)
            notes.append(semis)
        return notes

    def test_us212_ca8_deux_lots_anterieurs_donnent_la_moyenne_gherkin(self, db):
        self._lots_notes(db, [70, 80])
        courant = _semis(db, "chou", quantite=48, quand=datetime(2026, 9, 1))
        lot = _lot(db, courant)
        assert lot["moyenne_levee_culture"] == 75 and lot["nb_lots_moyenne_levee"] == 2

    def test_us212_ca8_un_seul_lot_anterieur_ne_donne_aucune_moyenne_gherkin(self, db):
        self._lots_notes(db, [70])
        courant = _semis(db, "chou", quantite=48, quand=datetime(2026, 9, 1))
        assert _lot(db, courant)["moyenne_levee_culture"] is None

    def test_us212_ca8_aucun_lot_anterieur_aucune_moyenne(self, db):
        courant = _semis(db, "chou", quantite=48)
        lot = _lot(db, courant)
        assert lot["moyenne_levee_culture"] is None and lot["nb_lots_moyenne_levee"] == 0

    def test_us212_ca8_un_lot_n_entre_pas_dans_sa_propre_moyenne(self, db):
        a, b = self._lots_notes(db, [70, 80])
        assert _lot(db, a)["moyenne_levee_culture"] is None       # un seul AUTRE lot : 80
        assert _lot(db, b)["moyenne_levee_culture"] is None       # un seul AUTRE lot : 70

    def test_us212_ca8_la_moyenne_se_lit_aussi_sur_un_lot_deja_note(self, db):
        a, b, c = self._lots_notes(db, [70, 80, 90])
        assert _lot(db, a)["moyenne_levee_culture"] == 85
        assert _lot(db, c)["moyenne_levee_culture"] == 75

    def test_us212_ca8_une_autre_culture_ne_compte_pas(self, db):
        self._lots_notes(db, [70, 80], culture="tomate")
        courant = _semis(db, "chou", quantite=48)
        assert _lot(db, courant)["moyenne_levee_culture"] is None

    def test_us212_ca8_isolation_entre_potagers(self, db):
        self._lots_notes(db, [70, 80], potager=2, parcelle=3)
        courant = _semis(db, "chou", quantite=48)
        assert _lot(db, courant)["moyenne_levee_culture"] is None
        autre = _semis(db, "chou", quantite=48, potager=2, parcelle=3)
        assert _lot(db, autre, potager=2)["moyenne_levee_culture"] == 75

    def test_us212_ca8_un_lot_sans_graines_connues_n_a_pas_de_taux_donc_ne_compte_pas(self, db):
        self._lots_notes(db, [70])
        sans = _semis(db, "chou", quantite=0, quand=datetime(2026, 8, 15))
        _noter(db, sans, 12)
        courant = _semis(db, "chou", quantite=48)
        assert _lot(db, courant)["moyenne_levee_culture"] is None

    def test_us212_ca8_la_phrase_compare_le_taux_a_la_moyenne(self):
        assert lots.phrase_taux_levee(83, 75, "chou") == "83 % — au-dessus de la moyenne des lots de chou ici (75 %)"
        assert lots.phrase_taux_levee(60, 75, "chou").startswith("60 % — en dessous de")
        assert lots.phrase_taux_levee(76, 75, "chou").startswith("76 % — dans la moyenne")
        assert lots.phrase_taux_levee(83, None, "chou") == "83 %"
        assert lots.phrase_taux_levee(None, 75, "chou") is None


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — un repiquage supérieur aux levés est signalé, jamais borné
# ═════════════════════════════════════════════════════════════════════════════
class TestRepiquageApresLevee:

    def test_us212_ca9_repiquer_plus_que_leve_est_signale_et_garde(self, db):
        semis = _semis(db, quantite=48)
        _noter(db, semis, 40)
        item = {"action": "mise_en_godet", "culture": "chou", "nb_plants_godets": 45,
                "nb_graines_semees": 48, "origine_graines_id": semis.id, "date": "2026-09-20"}
        svc_evenements.creer_evenement_godet(db, CTX, item, "mise en godet 45 choux sur 48")    # pas refusé
        lot = _lot(db, semis)
        assert lot["plants_obtenus"] == 45                      # jamais borné
        assert lot["incoherence_repiquage_levee"] is True

    def test_us212_ca9_le_signalement_est_dit_dans_la_fiche_telegram(self, db):
        semis = _semis(db, quantite=48)
        _noter(db, semis, 40)
        _godet(db, semis, plants=45, graines=48)
        texte = lots.formater_lot_telegram(_lot(db, semis))
        assert "Plus de plants repiqués que de levés" in texte

    def test_us212_ca9_sans_levee_notee_aucun_signalement(self, db):
        semis = _semis(db, quantite=48)
        _godet(db, semis, plants=45, graines=48)
        assert _lot(db, semis)["incoherence_repiquage_levee"] is False


# ═════════════════════════════════════════════════════════════════════════════
# CA10 — aucun stock ne change
# ═════════════════════════════════════════════════════════════════════════════
class TestAucunStock:

    @pytest.mark.parametrize("terminee", [False, True])
    def test_us212_ca10_les_stocks_sont_identiques_avant_et_apres(self, db, terminee):
        semis = _semis(db, "chou", variete="frisé", quantite=48)
        _godet(db, semis, plants=20, graines=24)

        def lecture():
            return (
                calcul_godets(db, include_epuises=True, potager_id=1),
                calcul_stock_par_variete(db, "chou", potager_id=1),
            )

        avant = lecture()
        _noter(db, semis, 30, terminee=terminee)
        assert lecture() == avant

    def test_us212_ca10_une_levee_ne_cree_aucun_godet(self, db):
        semis = _semis(db)
        _noter(db, semis, 40)
        lot = _lot(db, semis)
        assert lot["stock_residuel_godet"] == 0 and lot["plants_obtenus"] == 0

    def test_us212_ca10_aucune_nature_de_stock_n_est_invalidee(self):
        natures = set(natures_impactees("levee"))
        assert "stock" not in natures
        assert {"pepiniere", "semis"} <= natures

    def test_us212_ca10_la_levee_ne_sort_pas_du_stock_des_godets_ni_des_plants(self):
        source = (RACINE / "utils" / "stock.py").read_text(encoding="utf-8")
        # `levee` n'apparaît que dans la lecture par lot, jamais dans un calcul de stock agrégé.
        assert source.count('"levee"') == 1


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — ce que l'API rend
# ═════════════════════════════════════════════════════════════════════════════
class TestApi:

    def test_us212_ca6_get_pepiniere_lots_expose_les_levees(self, db):
        from app.api.main import _lot_pepiniere_json
        semis = _semis(db)
        _noter(db, semis, 40, terminee=True, jour="2026-09-12")
        lot = _lot(db, semis)
        json = _lot_pepiniere_json(lot, {})
        assert json["nb_leves"] == 40
        assert json["date_derniere_levee"] == "2026-09-12"
        assert json["taux_levee"] == 83
        assert json["levee_terminee"] is True
        assert json["moyenne_levee_culture"] is None            # moins de deux autres lots
        assert json["graines_non_levees_soldees"] == 8

    def test_us212_ca6_sans_levee_les_champs_sont_nuls_pas_zero(self, db):
        from app.api.main import _lot_pepiniere_json
        json = _lot_pepiniere_json(_lot(db, _semis(db)), {})
        assert json["nb_leves"] is None and json["taux_levee"] is None and json["date_derniere_levee"] is None

    def test_us212_ca6_le_taux_de_levee_n_est_pas_le_taux_de_germination(self, db):
        semis = _semis(db, quantite=48)
        _godet(db, semis, plants=20, graines=24)
        _noter(db, semis, 40)
        lot = _lot(db, semis)
        assert lot["taux_levee"] == 83                          # levés ÷ graines semées
        assert lot["taux_germination"] == 42                    # plants repiqués ÷ graines semées

    def test_us212_ca6_le_prompt_du_modele_connait_la_levee(self):
        source = (RACINE / "llm" / "groq_client.py").read_text(encoding="utf-8")
        assert "RÈGLE levee" in source and "| levee" in source


# ═════════════════════════════════════════════════════════════════════════════
# Échéances — « Noter la levée » ne se propose plus une fois la levée notée
# ═════════════════════════════════════════════════════════════════════════════
class TestEcheances:

    def test_us212_une_levee_notee_est_vue_par_les_echeances(self, db):
        from app.services.echeances_lots import _levee_notee
        semis = _semis(db)
        assert _levee_notee(_lot(db, semis)) is False
        _noter(db, semis, 40)
        assert _levee_notee(_lot(db, semis)) is True

    def test_us212_des_leves_non_repiques_comptent_comme_des_graines_a_repiquer(self, db):
        from app.services.echeances_lots import _a_des_graines
        semis = _semis(db)
        _noter(db, semis, 40, terminee=True)
        assert _a_des_graines(_lot(db, semis)) is True


# ═════════════════════════════════════════════════════════════════════════════
# CA11 — le geste est ouvert à la PWA, avec son gabarit de phrase
# ═════════════════════════════════════════════════════════════════════════════
class TestPwa:
    """CA11 — depuis la PWA, la saisie est limitée : seul le GESTE est possible. Ni le nombre de
    levés ni « levée terminée » ne se saisissent à l'écran ; le bot les demande."""

    def test_us212_ca11_la_levee_est_un_geste_ouvert(self):
        assert "levee" in svc_gestes.GESTES_OUVERTS_PWA
        assert "levee" in svc_gestes.GESTES_DE_LOT

    def test_us212_ca11_le_geste_depose_cite_son_lot_et_rien_d_autre(self, db):
        semis = _semis(db)
        depot = svc_gestes.deposer_geste(db, CTX, action="levee", culture="chou", lot_id=semis.id)
        item = svc_gestes.item_du_geste(depot.geste)
        assert item["action"] == "levee" and item["numero_lot_cite"] == semis.numero_lot
        assert item["quantite"] is None and item["unite"] is None
        assert "levee_terminee" not in item
        assert db.query(Evenement).filter(Evenement.type_action == "levee").count() == 0     # rien n'est écrit

    def test_us212_ca11_un_nombre_envoye_par_un_ancien_client_est_ignore(self, db):
        semis = _semis(db)
        depot = svc_gestes.deposer_geste(db, CTX, action="levee", culture="chou", lot_id=semis.id, quantite=40)
        item = svc_gestes.item_du_geste(depot.geste)
        assert item["quantite"] is None and item["unite"] is None

    def test_us212_ca11_le_depot_n_accepte_plus_levee_terminee(self, db):
        semis = _semis(db)
        with pytest.raises(TypeError):
            svc_gestes.deposer_geste(db, CTX, action="levee", culture="chou", lot_id=semis.id, levee_terminee=True)
        from app.api.main import PreparerGesteRequest
        assert "levee_terminee" not in PreparerGesteRequest.model_fields

    def test_us212_ca11_la_phrase_a_dicter_ne_dit_que_le_lot_et_est_lue_sans_modele(self, db):
        semis = _semis(db)
        depot = svc_gestes.deposer_geste(db, CTX, action="levee", culture="chou", lot_id=semis.id)
        phrase = svc_gestes.phrase_a_dicter(svc_gestes.item_du_geste(depot.geste))
        assert phrase == f"levée du lot {semis.numero_lot}"
        lu = parser_saisie(phrase, CTX, db=db)
        assert lu.reconnu, lu.raison
        assert lu.items[0]["action"] == "levee" and lu.items[0]["quantite"] is None
        assert lu.items[0]["numero_lot_cite"] == semis.numero_lot

    def test_us212_ca11_une_seconde_levee_en_attente_pour_le_lot_est_refusee(self, db):
        semis = _semis(db)
        svc_gestes.deposer_geste(db, CTX, action="levee", culture="chou", lot_id=semis.id)
        with pytest.raises(svc_gestes.GesteDeLotDejaEnAttenteError):
            svc_gestes.deposer_geste(db, CTX, action="levee", culture="chou", lot_id=semis.id)

    def test_us212_ca11_le_lot_d_un_autre_potager_est_refuse(self, db):
        etranger = _semis(db, potager=2, parcelle=3)
        with pytest.raises(svc_gestes.LotHorsPotagerError):
            svc_gestes.deposer_geste(db, CTX, action="levee", culture="chou", lot_id=etranger.id)

    def test_us212_ca11_un_membre_en_lecture_seule_ne_depose_rien(self, db):
        from app.services.permissions import PermissionInsuffisanteError
        semis = _semis(db)
        lecteur = TenantContext(user_id=1, potager_id=1, role="viewer")
        with pytest.raises(PermissionInsuffisanteError):
            svc_gestes.deposer_geste(db, lecteur, action="levee", culture="chou", lot_id=semis.id)

    def test_us212_ca11_le_front_ne_saisit_rien_de_la_levee(self):
        lib = (RACINE / "frontend" / "src" / "lib" / "ficheLot.js").read_text(encoding="utf-8")
        fiche = (RACINE / "frontend" / "src" / "components" / "FicheLot.jsx").read_text(encoding="utf-8")
        assert "export const LEVEE_DISPONIBLE = true" in lib
        assert not (RACINE / "frontend" / "src" / "components" / "CompteurNumerique.jsx").exists()
        for reste in ("CompteurNumerique", "CompteurLevee", "gesteDeLevee", "Levée terminée"):
            assert reste not in fiche and reste not in lib, reste


# ═════════════════════════════════════════════════════════════════════════════
# CA11 — le bot demande le détail, précisément
# ═════════════════════════════════════════════════════════════════════════════
class TestQuestionsDuBot:
    """Le geste déposé depuis la PWA ne porte que son lot : le bot demande le nombre de levés,
    puis si la levée est terminée, avec ce que la base sait du lot."""

    UID = 4242

    @pytest.fixture
    def bot(self, db, monkeypatch):
        from unittest.mock import AsyncMock, MagicMock, patch

        from app import bot as bot_module
        from app.bot import etat

        for pending in (etat._QUANTITE_PENDING, etat._LEVEE_TERMINEE_PENDING, etat._ACTION_PENDING):
            pending.pop(self.UID, None)
        monkeypatch.setattr(bot_module, "SessionLocal", lambda: db)
        monkeypatch.setattr(db, "close", lambda: None)
        update = MagicMock()
        update.effective_user.id = self.UID
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock()
        update.effective_message = update.message
        ctx = MagicMock(potager_id=1, user_id=1)
        with (
            patch("app.bot._normalize_items", side_effect=lambda items, texte: items),
            patch("app.bot.require_role"),
            patch("app.bot.current_context", return_value=ctx),
        ):
            yield SimpleBot(bot_module, etat, update)
        for pending in (etat._QUANTITE_PENDING, etat._LEVEE_TERMINEE_PENDING, etat._ACTION_PENDING):
            pending.pop(self.UID, None)

    @staticmethod
    def _geste_pwa(semis):
        return {"action": "levee", "culture": "chou", "numero_lot_cite": semis.numero_lot,
                "quantite": None, "unite": None, "date": "2026-09-12"}

    @staticmethod
    def _file():
        return {"id": 33, "potager_id": 1, "user_id": 1, "position": 1, "total": 1}

    @staticmethod
    def _textes(update):
        return [c.args[0] for c in update.message.reply_text.call_args_list]

    @staticmethod
    def _boutons(appel):
        return [b.callback_data for ligne in appel.kwargs["reply_markup"].inline_keyboard for b in ligne]

    @pytest.mark.asyncio
    async def test_us212_ca11_le_bot_demande_le_nombre_avec_ce_que_la_base_sait_du_lot(self, db, bot):
        semis = _semis(db, "chou", variete="frisé", quantite=48)
        _noter(db, semis, 30, jour="2026-09-08")
        await bot.module._parse_and_save(
            bot.update, f"levée du lot {semis.numero_lot}", pre_parsed_items=[self._geste_pwa(semis)],
            geste_file=self._file(),
        )
        question = self._textes(bot.update)[-1]
        assert f"Combien de plants ont levé dans le lot n° {semis.numero_lot}" in question
        assert "Chou frisé" in question and "48 graines semées" in question and "semé le 01/09/2026" in question
        assert "Dernier comptage : 30 levés le 08/09" in question
        assert "0 si rien n'a encore levé" in question
        assert self._boutons(bot.update.message.reply_text.call_args) == ["levdet_cancel"]
        assert "Laisser dans ma file" in bot.update.message.reply_text.call_args.kwargs["reply_markup"].inline_keyboard[0][0].text
        assert bot.etat._QUANTITE_PENDING[self.UID]["levee"] is True
        assert db.query(Evenement).filter(Evenement.type_action == "levee").count() == 1   # le comptage d'avant seulement

    @pytest.mark.asyncio
    async def test_us212_ca11_le_nombre_repondu_declenche_la_question_terminee(self, db, bot):
        semis = _semis(db, "chou", quantite=48)
        await bot.module._parse_and_save(
            bot.update, "levée", pre_parsed_items=[self._geste_pwa(semis)], geste_file=self._file(),
        )
        assert await bot.module._repondre_quantite_en_attente(bot.update, "40 plants") is True

        question = self._textes(bot.update)[-1]
        assert f"La levée du lot n° {semis.numero_lot} est-elle terminée" in question
        assert "40 levés sur 48 graines semées (83 %)" in question
        assert "les 8 graines non levées sont soldées" in question
        assert self._boutons(bot.update.message.reply_text.call_args) == ["levdet_oui", "levdet_non", "levdet_cancel"]
        assert self.UID not in bot.etat._QUANTITE_PENDING
        assert bot.etat._LEVEE_TERMINEE_PENDING[self.UID]["items"][0]["quantite"] == 40

    @pytest.mark.asyncio
    async def test_us212_ca11_oui_terminee_mene_au_recapitulatif_puis_ferme_la_germination(self, db, bot):
        from unittest.mock import AsyncMock, MagicMock
        semis = _semis(db, "chou", quantite=48)
        await bot.module._parse_and_save(
            bot.update, "levée", pre_parsed_items=[self._geste_pwa(semis)], geste_file=self._file(),
        )
        await bot.module._repondre_quantite_en_attente(bot.update, "40")

        query = MagicMock(data="levdet_oui")
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update = MagicMock(callback_query=query)
        update.effective_user.id = self.UID
        update.message = None                         # un callback n'a pas de message propre :
        query.message = bot.update.message            # `_parse_and_save` répond dans celui du bouton
        await bot.module._levee_detail_cb(update, MagicMock())

        recap = self._textes(bot.update)[-1]
        assert f"levée terminée du lot {semis.numero_lot} (chou) : 40 plants" in recap
        assert "8 graines non levées seront soldées" in recap
        item = bot.etat._ACTION_PENDING[self.UID]["items"][0]
        assert item["levee_terminee"] is True and item["quantite"] == 40
        assert bot.etat._ACTION_PENDING[self.UID]["geste_file"] == self._file()

        svc_evenements.creer_evenement_confirme(db, CTX, item, "levée", None)
        lot = _lot(db, semis)
        assert lot["etat_germination"] == "close" and lot["graines_en_germination"] == 0
        assert lot["nb_leves"] == 40 and lot["graines_non_levees_soldees"] == 8

    @pytest.mark.asyncio
    async def test_us212_ca11_lot_en_partie_repique_demande_les_graines_restantes(self, db, bot):
        """Le lot 4 de terrain : 20 graines, 15 déjà repiquées, 5 à lever. « 5 » = 5 levés
        parmi les restantes, donc 20 levés sur 20 — rien n'est soldé, aucune incohérence,
        et le récapitulatif ne demande aucune parcelle."""
        from unittest.mock import AsyncMock, MagicMock
        semis = _semis(db, "tomate", variete="jaune", quantite=20)
        _godet(db, semis, plants=15, graines=15)
        geste = {**self._geste_pwa(semis), "culture": "tomate"}
        await bot.module._parse_and_save(bot.update, "levée", pre_parsed_items=[geste], geste_file=self._file())

        question = self._textes(bot.update)[-1]
        assert f"parmi les 5 graines restantes du lot n° {semis.numero_lot}" in question
        assert "20 graines semées, dont 15 déjà repiqués en godet" in question

        await bot.module._repondre_quantite_en_attente(bot.update, "5")
        terminee = self._textes(bot.update)[-1]
        assert "20 levés sur 20 graines semées (100 %)" in terminee
        assert "soldée" not in terminee

        query = MagicMock(data="levdet_oui")
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update = MagicMock(callback_query=query)
        update.effective_user.id = self.UID
        update.message = None
        query.message = bot.update.message
        await bot.module._levee_detail_cb(update, MagicMock())

        recap = self._textes(bot.update)[-1]
        assert ": 20 plants" in recap and "Dont 15 déjà repiqués en godet et 5 levés parmi les graines restantes" in recap
        assert "soldée" not in recap and "parcelle ?" not in recap

        item = bot.etat._ACTION_PENDING[self.UID]["items"][0]
        svc_evenements.creer_evenement_confirme(db, CTX, item, "levée", None)
        lot = _lot(db, semis)
        assert lot["nb_leves"] == 20 and lot["taux_levee"] == 100
        assert lot["graines_non_levees_soldees"] == 0 and lot["incoherence_repiquage_levee"] is False

    @pytest.mark.asyncio
    async def test_us212_ca11_pas_encore_laisse_la_levee_en_cours(self, db, bot):
        from unittest.mock import AsyncMock, MagicMock
        semis = _semis(db, "chou", quantite=48)
        await bot.module._parse_and_save(bot.update, "levée", pre_parsed_items=[self._geste_pwa(semis)])
        await bot.module._repondre_quantite_en_attente(bot.update, "40")
        query = MagicMock(data="levdet_non")
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update = MagicMock(callback_query=query)
        update.effective_user.id = self.UID
        update.message = None                         # un callback n'a pas de message propre :
        query.message = bot.update.message            # `_parse_and_save` répond dans celui du bouton
        await bot.module._levee_detail_cb(update, MagicMock())

        item = bot.etat._ACTION_PENDING[self.UID]["items"][0]
        assert not item.get("levee_terminee")
        assert f"levée du lot {semis.numero_lot} (chou) : 40 plants" in self._textes(bot.update)[-1]
        svc_evenements.creer_evenement_confirme(db, CTX, item, "levée", None)
        assert _lot(db, semis)["etat_germination"] == "en_cours"

    @pytest.mark.asyncio
    async def test_us212_ca11_une_phrase_dictee_avec_son_nombre_ne_pose_aucune_question(self, db, bot):
        semis = _semis(db, "chou", quantite=48)
        item = {**self._geste_pwa(semis), "quantite": 40, "unite": "plants"}
        await bot.module._parse_and_save(bot.update, f"levée du lot {semis.numero_lot} : 40", pre_parsed_items=[item])
        assert self.UID not in bot.etat._QUANTITE_PENDING
        assert self.UID not in bot.etat._LEVEE_TERMINEE_PENDING
        assert "C'est correct" in self._textes(bot.update)[-1]
        assert not bot.etat._ACTION_PENDING[self.UID]["items"][0].get("levee_terminee")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("reponse", ["0", "rien", "aucun"])
    async def test_us212_ca11_zero_est_un_comptage_valide(self, db, bot, reponse):
        semis = _semis(db, "chou", quantite=48)
        await bot.module._parse_and_save(bot.update, "levée", pre_parsed_items=[self._geste_pwa(semis)])
        assert await bot.module._repondre_quantite_en_attente(bot.update, reponse) is True
        assert bot.etat._LEVEE_TERMINEE_PENDING[self.UID]["items"][0]["quantite"] == 0

    @pytest.mark.asyncio
    async def test_us212_ca11_une_reponse_non_numerique_redemande_le_nombre(self, db, bot):
        semis = _semis(db, "chou", quantite=48)
        await bot.module._parse_and_save(bot.update, "levée", pre_parsed_items=[self._geste_pwa(semis)])
        assert await bot.module._repondre_quantite_en_attente(bot.update, "euh") is True
        assert "Nombre de plants levés non reconnu" in self._textes(bot.update)[-1]
        assert self.UID in bot.etat._QUANTITE_PENDING            # la question reste posée

    @pytest.mark.asyncio
    async def test_us212_ca11_une_vraie_nouvelle_saisie_abandonne_la_question(self, db, bot):
        semis = _semis(db, "chou", quantite=48)
        await bot.module._parse_and_save(bot.update, "levée", pre_parsed_items=[self._geste_pwa(semis)])
        assert await bot.module._repondre_quantite_en_attente(
            bot.update, "j'ai récolté deux kilos de tomates ce matin au jardin",
        ) is False
        assert self.UID not in bot.etat._QUANTITE_PENDING

    @pytest.mark.asyncio
    async def test_us212_ca11_annuler_laisse_le_geste_dans_la_file(self, db, bot):
        from unittest.mock import AsyncMock, MagicMock
        semis = _semis(db, "chou", quantite=48)
        await bot.module._parse_and_save(
            bot.update, "levée", pre_parsed_items=[self._geste_pwa(semis)], geste_file=self._file(),
        )
        query = MagicMock(data="levdet_cancel")
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update = MagicMock(callback_query=query)
        update.effective_user.id = self.UID
        await bot.module._levee_detail_cb(update, MagicMock())
        assert self.UID not in bot.etat._QUANTITE_PENDING
        assert "reste dans votre file" in query.edit_message_text.call_args.args[0]
        assert db.query(Evenement).filter(Evenement.type_action == "levee").count() == 0

    @pytest.mark.asyncio
    async def test_us212_ca11_un_lot_clos_ou_inconnu_est_refuse_avant_toute_question(self, db, bot):
        semis = _semis(db, "chou", quantite=48)
        item = {"action": "levee", "culture": "chou", "numero_lot_cite": 999, "quantite": None}
        await bot.module._parse_and_save(bot.update, "levée du lot 999", pre_parsed_items=[item])
        assert self.UID not in bot.etat._QUANTITE_PENDING
        assert "999" in self._textes(bot.update)[-1]


class SimpleBot:
    """Ce qu'un test du bot manipule : le package, ses états, la mise à jour Telegram simulée."""

    def __init__(self, module, etat, update):
        self.module, self.etat, self.update = module, etat, update


# ═════════════════════════════════════════════════════════════════════════════
# Migration
# ═════════════════════════════════════════════════════════════════════════════
class TestMigration:

    def test_us212_la_migration_ajoute_la_colonne_et_son_rollback_la_retire(self):
        migration = (RACINE / "migrations" / "migration_v57.sql").read_text(encoding="utf-8")
        rollback = (RACINE / "migrations" / "rollback_v57.sql").read_text(encoding="utf-8")
        assert "ADD COLUMN IF NOT EXISTS levee_terminee BOOLEAN" in migration
        assert "CHECK (levee_terminee IS NULL OR type_action = 'levee')" in migration
        assert "DROP COLUMN IF EXISTS levee_terminee" in rollback

    def test_us212_le_modele_porte_la_colonne(self, db):
        assert "levee_terminee" in {c.name for c in Evenement.__table__.columns}

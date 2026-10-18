"""
tests/test_us216_fiche_lot.py — La fiche d'un lot et ses gestes [US-216]
=======================================================================

La fiche elle-même est un composant React : ses règles d'affichage (gestes selon
l'état du lot, quantités proposées, taux et comparaison) sont dans
`frontend/src/lib/ficheLot.js`, testées par `npm test`. Ce fichier tient le
CÔTÉ SERVEUR de l'US :

- CA2   `GET /pepiniere/lots/{numero}` rend les échéances et l'action suggérée
- CA8   les gestes de la fiche (repiquer, perte, clôture) sont ouverts à la PWA
- CA9   chacun cite son lot et dit ses quantités, sans rien écrire au dépôt
- clôture : le geste `cloture_lot` solde le lot entier — godets ET graines —,
  définitivement, et sort du stock agrégé
- CA12  un membre en lecture seule ne dépose rien
- CA17  la fiche du corpus décrit la fiche du lot

Aucun appel réseau, aucun appel au modèle.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services import echeances_lots as svc_echeances
from app.services import evenements as svc_evenements
from app.services import file_gestes as svc_gestes
from app.services import lots_pepiniere as lots
from app.services.context import TenantContext
from app.services.permissions import PermissionInsuffisanteError
from database.models import CultureConfig, Evenement, Parcelle, Potager, User
from llm.parseur_deterministe import parser_saisie
from utils.actions import normalize_action
from utils.dependances_donnee import natures_impactees
from utils.stock import calcul_godets, calcul_lots_pepiniere

RACINE = Path(__file__).resolve().parent.parent
CTX = TenantContext(user_id=1, potager_id=1, role="owner")
CTX_LECTEUR = TenantContext(user_id=1, potager_id=1, role="viewer")


@pytest.fixture
def db(test_db):
    test_db.add(User(id=1, email="a@potager.test"))
    test_db.flush()
    test_db.add(Potager(id=1, nom="Jardin A", proprietaire_id=1))
    for nom in ("chou", "tomate"):
        test_db.add(CultureConfig(nom=nom, type_organe_recolte="végétatif"))
    test_db.add_all([
        Parcelle(id=1, nom="nord", nom_normalise="nord", potager_id=1),
        Parcelle(id=2, nom="serre", nom_normalise="serre", potager_id=1, est_pepiniere=True),
    ])
    test_db.commit()
    return test_db


def _semis(db, culture="chou", quantite=48.0, quand=datetime(2026, 4, 1)):
    ev = Evenement(type_action="semis", culture=culture, quantite=quantite, unite="graines",
                   parcelle_id=2, date=quand, potager_id=1)
    db.add(ev)
    db.commit()
    return ev


def _godet(db, semis, plants=20, graines=24):
    ev = Evenement(type_action="mise_en_godet", culture=semis.culture, nb_plants_godets=plants,
                   nb_graines_semees=graines, origine_graines_id=semis.id, potager_id=1,
                   date=datetime(2026, 4, 20))
    db.add(ev)
    db.commit()
    return ev


def _lot(db, semis):
    return next(l for l in calcul_lots_pepiniere(db, None, potager_id=1) if l["semis_id"] == semis.id)


def _cloturer(db, numero):
    item = {"action": "cloture_lot", "numero_lot_cite": numero, "date": "2026-05-10"}
    lots.resoudre_references(db, CTX, [item])
    return svc_evenements.creer_evenement_confirme(db, CTX, item, f"cloture lot {numero}", None)


# ═════════════════════════════════════════════════════════════════════════════
# La clôture solde le lot entier
# ═════════════════════════════════════════════════════════════════════════════
class TestCloture:

    def test_us216_cloture_solde_les_godets_et_les_graines(self, db):
        semis = _semis(db)
        _godet(db, semis, plants=20, graines=24)    # 24 graines soldées, 20 plants, 24 à lever
        avant = _lot(db, semis)
        assert (avant["stock_residuel_godet"], avant["graines_en_germination"]) == (20, 24)

        _cloturer(db, semis.numero_lot)

        apres = _lot(db, semis)
        assert apres["stock_residuel_godet"] == 0
        assert apres["graines_en_germination"] == 0
        assert apres["cloture"] is True
        assert apres["etat_germination"] == "close"

    def test_us216_cloture_garde_l_historique_du_lot(self, db):
        semis = _semis(db)
        _godet(db, semis, plants=20, graines=24)
        _cloturer(db, semis.numero_lot)
        lot = _lot(db, semis)
        # Rien de ce qui s'est passé n'est réécrit : seul le reste est soldé.
        assert lot["plants_obtenus"] == 20 and lot["graines_semees"] == 48
        assert lot["nb_plantes"] == 0 and lot["nb_pertes_godet"] == 0
        assert str(lot["date_cloture"])[:10] == "2026-05-10"

    def test_us216_cloture_fige_les_nombres_dans_l_evenement(self, db):
        semis = _semis(db)
        _godet(db, semis, plants=20, graines=24)
        evt = _cloturer(db, semis.numero_lot)
        assert evt.type_action == "cloture_lot"
        assert evt.origine_graines_id == semis.id
        assert evt.quantite == 20 and evt.nb_graines_semees == 24

    def test_us216_cloture_sort_les_godets_du_stock_agrege(self, db):
        semis = _semis(db)
        _godet(db, semis, plants=20, graines=24)
        assert calcul_godets(db, potager_id=1)["chou"]["stock_residuel_godet"] == 20
        _cloturer(db, semis.numero_lot)
        agrege = calcul_godets(db, include_epuises=True, potager_id=1)["chou"]
        assert agrege["stock_residuel_godet"] == 0

    def test_us216_cloture_d_un_semis_sans_godet_solde_les_graines(self, db):
        semis = _semis(db)
        assert calcul_godets(db, potager_id=1)["chou"]["graines_en_germination"] == 48
        _cloturer(db, semis.numero_lot)
        assert _lot(db, semis)["graines_en_germination"] == 0
        assert "chou" not in calcul_godets(db, potager_id=1)

    def test_us216_un_lot_clos_n_est_plus_dormant_ni_a_traiter(self, db):
        semis = _semis(db, quand=datetime(2026, 1, 2))
        _godet(db, semis)
        _cloturer(db, semis.numero_lot)
        suite = svc_echeances.echeances_d_un_lot(db, CTX, _lot(db, semis), date(2026, 9, 1))
        assert suite["action_suggeree"] is None
        assert suite["echeances"]["dormance"]["est_dormant"] is False

    def test_us216_lot_deja_clos_est_refuse(self, db):
        semis = _semis(db)
        _cloturer(db, semis.numero_lot)
        item = {"action": "cloture_lot", "numero_lot_cite": semis.numero_lot}
        lots.resoudre_references(db, CTX, [item])
        with pytest.raises(svc_evenements.ClotureRefuseeError):
            svc_evenements.creer_evenement_confirme(db, CTX, item, "cloture lot", None)

    def test_us216_lot_inconnu_est_refuse_sans_rien_ecrire(self, db):
        item = {"action": "cloture_lot", "numero_lot_cite": 999}
        lots.resoudre_references(db, CTX, [item])
        assert "Aucun lot n° 999" in item["_alerte_lot"]
        with pytest.raises(svc_evenements.ClotureRefuseeError):
            svc_evenements.creer_evenement_confirme(db, CTX, item, "cloture lot 999", None)
        assert db.query(Evenement).filter(Evenement.type_action == "cloture_lot").count() == 0

    def test_us216_le_recapitulatif_connait_les_nombres_soldes(self, db):
        semis = _semis(db)
        _godet(db, semis, plants=20, graines=24)
        item = {"action": "cloture_lot", "numero_lot_cite": semis.numero_lot}
        lots.resoudre_references(db, CTX, [item])
        assert item["_lot_cloture"] == {"godets": 20, "graines": 24}

    def test_us216_la_cloture_figure_dans_le_cycle_de_vie_du_lot(self, db):
        semis = _semis(db)
        _godet(db, semis, plants=20, graines=24)
        evt = _cloturer(db, semis.numero_lot)
        cycle = svc_evenements.cycle_vie_culture(db, CTX, "chou", None, semis_id=semis.id)
        assert [c.id for c in cycle["clotures"]] == [evt.id]
        assert (cycle["clotures"][0].quantite, cycle["clotures"][0].nb_graines_semees) == (20, 24)

    def test_us216_la_cloture_d_un_lot_ne_remonte_pas_dans_un_autre(self, db):
        clos, ouvert = _semis(db), _semis(db, quand=datetime(2026, 4, 5))
        _cloturer(db, clos.numero_lot)
        cycle = svc_evenements.cycle_vie_culture(db, CTX, "chou", None, semis_id=ouvert.id)
        assert cycle["clotures"] == []

    def test_us216_le_vocabulaire_et_les_natures(self):
        assert normalize_action("cloture_lot") == "cloture_lot"
        assert normalize_action("clôturer le lot 128") == "cloture_lot"
        assert {"pepiniere", "stock", "semis", "journal"} <= set(natures_impactees("cloture_lot"))


# ═════════════════════════════════════════════════════════════════════════════
# CA8, CA9, CA12 — les gestes de la fiche passent par la file
# ═════════════════════════════════════════════════════════════════════════════
class TestGestesDeLaFiche:

    def test_us216_ca8_les_trois_gestes_sont_ouverts(self):
        for geste in ("mise_en_godet", "perte_godet", "cloture_lot", "plantation", "deplacement"):
            assert geste in svc_gestes.GESTES_OUVERTS_PWA

    def test_us216_ca9_repiquer_cite_le_lot_et_compte_des_plants(self, db):
        semis = _semis(db)
        depot = svc_gestes.deposer_geste(
            db, CTX, action="mise_en_godet", culture="chou", lot_id=semis.id, quantite=30,
        )
        item = svc_gestes.item_du_geste(depot.geste)
        assert item["numero_lot_cite"] == semis.numero_lot
        assert item["nb_plants_godets"] == 30 and item["quantite"] is None
        assert db.query(Evenement).filter(Evenement.type_action == "mise_en_godet").count() == 0

    def test_us216_ca9_la_phrase_a_dicter_est_lue_sans_modele(self, db):
        semis = _semis(db)
        depot = svc_gestes.deposer_geste(
            db, CTX, action="mise_en_godet", culture="chou", lot_id=semis.id, quantite=30,
        )
        phrase = svc_gestes.phrase_a_dicter(svc_gestes.item_du_geste(depot.geste))
        assert phrase == f"mise en godet 30 plants du lot {semis.numero_lot}"
        lu = parser_saisie(phrase, CTX, db=db)
        assert lu.items and lu.items[0]["action"] == "mise_en_godet"
        assert lu.items[0]["numero_lot_cite"] == semis.numero_lot

    def test_us216_ca9_la_phrase_de_cloture_est_lue_sans_modele(self, db):
        semis = _semis(db)
        depot = svc_gestes.deposer_geste(db, CTX, action="cloture_lot", culture="chou", lot_id=semis.id)
        item = svc_gestes.item_du_geste(depot.geste)
        assert item["quantite"] is None          # ce que la clôture solde est relu à la confirmation
        phrase = svc_gestes.phrase_a_dicter(item)
        assert phrase == f"cloture du lot {semis.numero_lot}"
        lu = parser_saisie(phrase, CTX, db=db)
        assert lu.items and lu.items[0]["action"] == "cloture_lot"

    def test_us216_ca9_la_perte_propose_la_quantite_connue(self, db):
        semis = _semis(db)
        _godet(db, semis)   # [INC-014] une perte suppose des godets dans le lot
        depot = svc_gestes.deposer_geste(
            db, CTX, action="perte_godet", culture="chou", lot_id=semis.id, quantite=5,
        )
        item = svc_gestes.item_du_geste(depot.geste)
        assert (item["quantite"], item["unite"]) == (5, "plants")
        assert item["numero_lot_cite"] == semis.numero_lot

    def test_us216_ca12_un_lecteur_ne_depose_rien(self, db):
        semis = _semis(db)
        with pytest.raises(PermissionInsuffisanteError):
            svc_gestes.deposer_geste(db, CTX_LECTEUR, action="cloture_lot", culture="chou", lot_id=semis.id)


class TestCasLimites:

    def test_us216_un_lot_d_un_autre_potager_est_refuse(self, db):
        db.add_all([User(id=2, email="b@potager.test")])
        db.flush()
        db.add(Potager(id=2, nom="Jardin B", proprietaire_id=2))
        db.commit()
        etranger = Evenement(type_action="semis", culture="chou", quantite=10, unite="graines",
                             date=datetime(2026, 4, 1), potager_id=2)
        db.add(etranger)
        db.commit()
        with pytest.raises(svc_gestes.LotHorsPotagerError):
            svc_gestes.deposer_geste(db, CTX, action="cloture_lot", culture="chou", lot_id=etranger.id)

    def test_us216_cloture_d_un_lot_sans_semis_rattache_par_culture(self, db):
        godet = Evenement(type_action="mise_en_godet", culture="tomate", nb_plants_godets=15,
                          potager_id=1, date=datetime(2026, 4, 20))
        db.add(godet)
        db.commit()
        item = {"action": "cloture_lot", "culture": "tomate", "date": "2026-05-10"}
        evt = svc_evenements.creer_evenement_confirme(db, CTX, item, "cloture des tomates", None)
        assert evt.quantite == 15 and evt.origine_graines_id is None
        lot = next(l for l in calcul_lots_pepiniere(db, None, potager_id=1) if l["sans_semis_rattache"])
        assert lot["cloture"] is True and lot["stock_residuel_godet"] == 0

    def test_us216_plusieurs_lots_de_la_culture_sans_numero_demande_lequel(self, db):
        _godet(db, _semis(db))
        _godet(db, _semis(db, quand=datetime(2026, 5, 1)))
        item = {"action": "cloture_lot", "culture": "chou"}
        with pytest.raises(svc_evenements.LotIndetermineError):
            svc_evenements.creer_evenement_confirme(db, CTX, item, "cloture chou", None)

    def test_us216_la_liste_porte_les_pepinieres_du_potager(self, db):
        assert lots.pepinieres_du_potager(db, CTX) == [
            {"id": 2, "nom": "serre", "superficie_m2": None, "type_pepiniere": None}]


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — une seule lecture ouvre la fiche
# ═════════════════════════════════════════════════════════════════════════════
class TestLectureParNumero:

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.api.main import app, get_current_user_ctx
        app.dependency_overrides[get_current_user_ctx] = lambda: CTX
        with patch("app.api.main.SessionLocal", return_value=MagicMock()):
            yield TestClient(app)
        app.dependency_overrides.clear()

    _LOT = {
        "lot_id": "semis-7", "semis_id": 7, "numero_lot": 128, "culture": "chou", "variete": None,
        "date_semis": datetime(2026, 9, 1), "date_derniere_mise_en_godet": None, "parcelle": "serre",
        "sans_semis_rattache": False, "cloture": False, "date_cloture": None,
    }

    def test_us216_ca2_la_lecture_par_numero_porte_echeances_et_action(self, client):
        suite = {
            "echeances": {"repiquage": {"etat": "en_retard", "retard_jours": 6}, "raisons": []},
            "action_suggeree": {"code": "repiquer", "libelle": "Repiquer en godet"},
        }
        with (
            patch("app.services.stock.lot_pepiniere_par_numero", return_value=dict(self._LOT)),
            patch("app.services.echeances_lots.echeances_d_un_lot", return_value=suite) as calcul,
        ):
            corps = client.get("/pepiniere/lots/128").json()
        assert corps["action_suggeree"]["code"] == "repiquer"
        assert corps["echeances"]["repiquage"]["retard_jours"] == 6
        assert corps["date_cloture"] is None
        assert calcul.call_count == 1


# ═════════════════════════════════════════════════════════════════════════════
# CA2, CA11 — la fiche reste atteignable de bout en bout (régression du 14/10/2026 :
# « Détail du lot » coupé par le bas de la fenêtre quand le panneau défilait)
# ═════════════════════════════════════════════════════════════════════════════
class TestPanneauAtteignable:

    def _source(self):
        return (RACINE / "frontend" / "src" / "views" / "Pepiniere.jsx").read_text(encoding="utf-8")

    def test_us216_le_panneau_est_borne_par_la_zone_qui_defile(self):
        source = self._source()
        assert "useHauteurZone(" in source
        assert "maxHeight: hauteurZone - 32" in source

    def test_us216_le_panneau_part_du_haut_de_l_ecran_avec_les_filtres_a_gauche(self):
        source = self._source()
        # La colonne de gauche porte les filtres ; le panneau est son voisin dans le même grid.
        assert source.index("[grid-template-columns:minmax(0,1fr)_420px]") < source.rindex("{filtres}")


# ═════════════════════════════════════════════════════════════════════════════
# CA17 — le corpus
# ═════════════════════════════════════════════════════════════════════════════
def test_us216_ca17_la_fiche_du_corpus_decrit_la_fiche_du_lot():
    fiche = (RACINE / "data" / "connaissance" / "doc_app" / "pepiniere-par-lot.md").read_text(encoding="utf-8")
    assert "fiche du lot" in fiche.lower()
    assert "clôtur" in fiche.lower()

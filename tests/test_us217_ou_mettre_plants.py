"""
[US-217] Proposer où mettre en terre les plants d'un lot.

Les suggestions sont une lecture du Plan (US-198, places d'US-227) faite UNE fois
par lecture de la pépinière : parcelles non pépinières avec un rang libre,
exposition comparée à celle de la culture, ordre concordance → rangs libres →
ordre des parcelles, parcelles sans nombre de rangs à la fin.

Le geste pré-rempli (« Mettre en terre ici ») est couvert côté front par
`frontend/src/lib/ficheLot.test.js`.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from app.services import confiance_semis as conf
from app.services import echeances_lots as ech
from app.services import previsions_meteo as svc_previsions
from app.services.context import TenantContext
from database.models import CultureConfig, Evenement, Parcelle, Potager, User
from utils.stock import calcul_lots_pepiniere

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
LE_19_SEPT = date(2026, 9, 19)


@pytest.fixture(autouse=True)
def _meteo_sans_reseau(monkeypatch):
    """Aucune prévision réelle, comme dans les tests d'US-214."""
    monkeypatch.setattr(conf, "_lire_meteo", lambda db, potager_id: svc_previsions.LecturePrevision(
        statut=svc_previsions.STATUT_LOCALISATION_MANQUANTE))


@pytest.fixture
def db(test_db):
    """Le décor du Gherkin : planche-nord au soleil, planche-ombre, planche-est sans rangs."""
    test_db.add(User(id=1, email="a@potager.test"))
    test_db.flush()
    test_db.add(Potager(id=1, nom="Jardin", proprietaire_id=1, zone_climatique="oceanique"))
    test_db.flush()
    test_db.add_all([
        Parcelle(id=1, nom="planche-ombre", nom_normalise="plancheombre", potager_id=1,
                 nb_rangs=2, ensoleillement="mi-ombre", ordre=1),
        Parcelle(id=2, nom="planche-nord", nom_normalise="planchenord", potager_id=1,
                 nb_rangs=2, ensoleillement="plein soleil", ordre=2),
        Parcelle(id=3, nom="planche-est", nom_normalise="plancheest", potager_id=1,
                 ensoleillement="plein soleil", ordre=3),
        Parcelle(id=4, nom="pleine", nom_normalise="pleine", potager_id=1,
                 nb_rangs=1, ensoleillement="plein soleil", ordre=4),
        Parcelle(id=5, nom="Serre", nom_normalise="serre", potager_id=1,
                 est_pepiniere=True, type_pepiniere="chaude", nb_rangs=3, ordre=5),
    ])
    test_db.add(CultureConfig(nom="chou", type_organe_recolte="feuille", exposition="plein soleil"))
    test_db.add(Evenement(
        type_action="plantation", culture="salade", quantite=10, unite="plants",
        parcelle_id=4, date=datetime(2026, 9, 10), potager_id=1,
    ))
    test_db.commit()
    return test_db


def _lot_de_godets(db, culture="chou", plants=40, numero=128):
    semis = Evenement(
        type_action="semis", culture=culture, quantite=48, unite="graines",
        date=datetime(2026, 8, 1), parcelle_id=5, potager_id=1, numero_lot=numero,
    )
    db.add(semis)
    db.commit()
    if plants:
        db.add(Evenement(
            type_action="mise_en_godet", culture=culture, nb_plants_godets=plants,
            nb_graines_semees=plants, origine_graines_id=semis.id, parcelle_id=5,
            date=datetime(2026, 8, 20), potager_id=1,
        ))
        db.commit()
    return semis


def _lire(db, ref=LE_19_SEPT):
    lots = calcul_lots_pepiniere(db, ref, potager_id=1)
    return ech.lire_echeances(db, CTX, lots, ref)


def _ou_mettre(db, semis, ref=LE_19_SEPT):
    return _lire(db, ref)["par_lot"][f"semis-{semis.id}"]["ou_mettre"]


class TestSuggestions:
    def test_us217_gherkin_deux_planches_ordre_et_exposition(self, db):
        """[CA1, CA2, CA3] planche-nord concordante d'abord, puis planche-ombre qui diffère."""
        om = _ou_mettre(db, _lot_de_godets(db))
        noms = [s["parcelle"] for s in om["suggestions"]]
        assert noms == ["planche-nord", "planche-ombre", "planche-est"]
        nord, ombre, est = om["suggestions"]
        assert nord["rangs_libres"] == 2 and nord["numeros_rangs_libres"] == [1, 2]
        assert nord["exposition"]["comparaison"] == ech.EXPO_CONCORDE
        assert ombre["exposition"]["comparaison"] == ech.EXPO_DIFFERE
        assert ombre["exposition"]["libelle"] == "mi-ombre, pour une culture de plein soleil"
        # [CA4] Ni longueur ni espacement : la section le dit, une fois.
        assert om["plants_non_calcules"] == ech.MENTION_PLANTS_NON_CALCULES
        assert nord["places_libres"] is None

    def test_us217_ca1_exclut_pepinieres_et_parcelles_pleines(self, db):
        om = _ou_mettre(db, _lot_de_godets(db))
        noms = {s["parcelle"] for s in om["suggestions"]}
        assert "Serre" not in noms and "pleine" not in noms

    def test_us217_ca3_sans_nombre_de_rangs_apres_et_inconnu(self, db):
        est = _ou_mettre(db, _lot_de_godets(db))["suggestions"][-1]
        assert est["parcelle"] == "planche-est"
        assert est["rangs_libres"] is None

    def test_us217_ca3_a_exposition_egale_le_plus_de_rangs_libres_d_abord(self, db):
        db.get(Parcelle, 1).ensoleillement = "plein soleil"
        db.get(Parcelle, 1).nb_rangs = 1
        db.commit()
        noms = [s["parcelle"] for s in _ou_mettre(db, _lot_de_godets(db))["suggestions"]]
        assert noms[:2] == ["planche-nord", "planche-ombre"]

    @pytest.mark.parametrize("parcelle, culture, attendu", [
        ("plein soleil", "plein soleil", ech.EXPO_CONCORDE),
        ("Mi ombre", "plein soleil", ech.EXPO_DIFFERE),
        (None, "plein soleil", ech.EXPO_NON_COMPARABLE),
        ("sud-est", "plein soleil", ech.EXPO_NON_COMPARABLE),
        ("ombre", None, ech.EXPO_NON_COMPARABLE),
    ])
    def test_us217_ca2_trois_issues_de_la_comparaison(self, parcelle, culture, attendu):
        assert ech.comparer_exposition(parcelle, culture)["comparaison"] == attendu

    def test_us217_ca2_culture_sans_exposition_non_comparable(self, db):
        om = _ou_mettre(db, _lot_de_godets(db, culture="navet"))
        assert {s["exposition"]["comparaison"] for s in om["suggestions"]} == {ech.EXPO_NON_COMPARABLE}

    def test_us217_lot_sans_godet_aucune_suggestion(self, db):
        assert _ou_mettre(db, _lot_de_godets(db, plants=0)) is None

    def test_us217_date_de_reference_passee(self, db):
        """Avant la plantation du 10/09, la parcelle « pleine » avait son rang libre."""
        om = _ou_mettre(db, _lot_de_godets(db), ref=date(2026, 9, 5))
        assert "pleine" in {s["parcelle"] for s in om["suggestions"]}

    def test_us217_ca8_aucun_rang_libre(self, db):
        for pid in (1, 2):
            db.get(Parcelle, pid).nb_rangs = 0
        db.commit()
        om = _ou_mettre(db, _lot_de_godets(db))
        assert om["aucun_rang_libre"] is True
        assert [s["parcelle"] for s in om["suggestions"]] == ["planche-est"]

    def test_us217_ca7_rang_non_prerempli_sans_position(self, db):
        """US-203 non livrée : la numérotation d'installation n'est pas une position."""
        assert all(s["premier_rang_libre"] is None for s in _ou_mettre(db, _lot_de_godets(db))["suggestions"])

    def test_us217_places_quand_longueur_et_espacement_connus(self, db):
        """[Encart US-227] La suggestion se dit en places, par la règle de la Vue plan."""
        db.get(Parcelle, 2).longueur_m = 4.0
        db.query(CultureConfig).filter_by(nom="chou").one().espacement = "40 × 50 cm"
        db.commit()
        om = _ou_mettre(db, _lot_de_godets(db))
        nord = next(s for s in om["suggestions"] if s["parcelle"] == "planche-nord")
        assert nord["places_par_rang"] == 10 and nord["places_libres"] == 20
        assert om["plants_non_calcules"] is None

    def test_us217_ca5_lecture_sans_ecriture(self, db):
        avant = db.query(Evenement).count()
        _ou_mettre(db, _lot_de_godets(db))
        assert db.query(Evenement).count() == avant + 2   # les deux du décor du lot


class TestBudget:
    def test_us217_ca1_plan_lu_une_fois_pour_tous_les_lots(self, db, monkeypatch):
        appels = []
        vrai = ech._lire_le_plan
        monkeypatch.setattr(ech, "_lire_le_plan", lambda *a, **k: appels.append(1) or vrai(*a, **k))
        _lot_de_godets(db, numero=128)
        _lot_de_godets(db, culture="poireau", numero=129)
        lecture = _lire(db)
        assert len(appels) == 1
        assert all(v["ou_mettre"] for v in lecture["par_lot"].values())

    def test_us217_ca10_aujourdhui_lit_les_memes_rangs_libres(self, db):
        _lot_de_godets(db)
        lecture = _lire(db)
        rangs = {r["parcelle"]: r["rangs_libres"] for r in lecture["resume"]["prets_pour_le_plan"]["rangs_libres_par_parcelle"]}
        om = next(iter(lecture["par_lot"].values()))["ou_mettre"]
        for s in om["suggestions"]:
            assert rangs[s["parcelle"]] == s["rangs_libres"]

    def test_us217_ca6_fiche_par_numero_porte_ou_mettre(self, db):
        semis = _lot_de_godets(db)
        lot = next(l for l in calcul_lots_pepiniere(db, LE_19_SEPT, potager_id=1) if l["lot_id"] == f"semis-{semis.id}")
        assert ech.echeances_d_un_lot(db, CTX, lot, LE_19_SEPT)["ou_mettre"]["suggestions"]


@pytest.mark.parametrize("parcelle, attendu", [
    ("Nord", "ensoleillement de la parcelle non renseigné"),
    (None, "ensoleillement de la parcelle non renseigné"),
])
def test_us217_ca2_libelle_orientation_ou_absence_non_comparable(parcelle, attendu):
    """[US-239 / CA8] Une orientation n'est jamais traduite en ensoleillement."""
    assert ech.comparer_exposition(parcelle, "plein soleil")["libelle"] == attendu

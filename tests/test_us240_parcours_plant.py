"""
tests/test_us240_parcours_plant.py — Le parcours du plant [US-240]
==================================================================

`GET /pepiniere/lots` gagne un bloc `parcours` : une étiquette par (lot, stade,
emplacement), rangée dans sa colonne, les lignes de pépinière, les compteurs, les
dormants hors kanban, et « à semer » limité aux graines dont on dispose.

- CA1        le bloc s'ajoute, rien n'est retiré
- CA2-CA4    les étiquettes et leurs fragments
- CA5        la table des colonnes (P9)
- CA6        chaque état, le seuil de 15 jours
- CA7        graines restantes d'un lot en partie repiqué : aucune échéance (A33)
- CA8        sans donnée, pas d'échéance
- CA9        ordre d'urgence dans une case
- CA10       toutes les pépinières, vides comprises ; « Sans emplacement »
- CA11       compteurs
- CA12       dormants hors kanban
- CA13-CA15  à semer : bornes de fenêtre, jours restants, variétés en stock
- CA16-CA18  une lecture du stock, lecture seule, isolation
- CA20-CA21  documentation

Les durées écrites ici sont des VALEURS DE TEST : elles n'engagent aucune agronomie.
Lu au lundi 19 octobre 2026, comme le wireframe « C · Le parcours du plant — v2 ».
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import calendrier_cultural as cal
from app.services import confiance_semis as conf
from app.services import echeances_lots as ech
from app.services import previsions_meteo as svc_previsions
from app.services import stock as svc_stock
from app.services.context import TenantContext
from database.db import Base
from database.models import (
    CultureConfig, DureeCulturale, Evenement, FenetreCulturale, ItineraireCultural,
    Parcelle, Potager, ReferentielSource, User,
)
from utils.stock import calcul_lots_pepiniere

RACINE = Path(__file__).resolve().parent.parent
CTX = TenantContext(user_id=1, potager_id=1, role="owner")
CTX_B = TenantContext(user_id=2, potager_id=2, role="owner")

LE_19_OCT = date(2026, 10, 19)
SERRE, CHASSIS, VERANDA = 2, 3, 4


# ═════════════════════════════════════════════════════════════════════════════
# Décor
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def db(test_db):
    """Deux potagers ; une planche, une serre chaude, un châssis froid, une véranda sans type."""
    test_db.add_all([User(id=1, email="a@potager.test"), User(id=2, email="b@potager.test")])
    test_db.flush()
    test_db.add_all([
        Potager(id=1, nom="Jardin A", proprietaire_id=1, zone_climatique="oceanique"),
        Potager(id=2, nom="Jardin B", proprietaire_id=2, zone_climatique="oceanique"),
    ])
    test_db.flush()
    test_db.add_all([
        Parcelle(id=1, nom="Planche nord", nom_normalise="planchenord", potager_id=1, nb_rangs=4),
        Parcelle(id=SERRE, nom="Serre", nom_normalise="serre", potager_id=1,
                 est_pepiniere=True, type_pepiniere="chaude", superficie_m2=2.5),
        Parcelle(id=CHASSIS, nom="Châssis froid", nom_normalise="chassisfroid", potager_id=1,
                 est_pepiniere=True, type_pepiniere="froide"),
        Parcelle(id=VERANDA, nom="Véranda", nom_normalise="veranda", potager_id=1, est_pepiniere=True),
        Parcelle(id=5, nom="Serre B", nom_normalise="serreb", potager_id=2,
                 est_pepiniere=True, type_pepiniere="chaude"),
    ])
    test_db.add(ReferentielSource(
        id=1, code="test", libelle="Test", licence="CC0",
        attribution="Valeurs de test", partageable=True, importee=True,
    ))
    test_db.commit()
    return test_db


@pytest.fixture(autouse=True)
def _meteo_sans_reseau(monkeypatch):
    """Aucune prévision réelle : la lecture météo est rendue « indisponible »."""
    monkeypatch.setattr(
        conf, "_lire_meteo",
        lambda db, potager_id: svc_previsions.LecturePrevision(
            statut=svc_previsions.STATUT_LOCALISATION_MANQUANTE),
    )


def _referentiel(db, nom, *, godet=None, terre=None, fenetre=None):
    """Une culture, son itinéraire, ses délais (jours_min, jours_max) et sa fenêtre de semis
    en pépinière (mois_debut, mois_fin)."""
    fiche = CultureConfig(nom=nom, type_organe_recolte="fruit")
    db.add(fiche)
    db.flush()
    it = ItineraireCultural(culture_id=fiche.id, nom="standard", nom_normalise="standard", source_id=1)
    db.add(it)
    db.flush()
    if fenetre:
        db.add(FenetreCulturale(
            itineraire_id=it.id, zone_climatique="oceanique", phase=cal.PHASE_SEMIS_PEPINIERE,
            mois_debut=fenetre[0], mois_fin=fenetre[1], source_id=1,
        ))
    for etape, bornes in ((cal.ETAPE_SEMIS_GODET, godet), (cal.ETAPE_REPIQUAGE, terre)):
        if bornes:
            db.add(DureeCulturale(itineraire_id=it.id, etape=etape, jours_min=bornes[0],
                                  jours_max=bornes[1], source_id=1))
    db.commit()


def _dt(jour: date) -> datetime:
    return datetime(jour.year, jour.month, jour.day)


def _semis(db, culture, jour, *, graines=48, parcelle_id=SERRE, numero=None, variete=None, potager_id=1):
    e = Evenement(type_action="semis", culture=culture, variete=variete, quantite=graines,
                  unite="graines", date=_dt(jour), parcelle_id=parcelle_id,
                  potager_id=potager_id, numero_lot=numero)
    db.add(e)
    db.commit()
    return e


def _godets(db, semis, jour, plants, *, parcelle_id=SERRE):
    e = Evenement(type_action="mise_en_godet", culture=semis.culture, nb_plants_godets=plants,
                  nb_graines_semees=plants, origine_graines_id=semis.id, parcelle_id=parcelle_id,
                  date=_dt(jour), potager_id=semis.potager_id)
    db.add(e)
    db.commit()
    return e


def _levee(db, semis, jour, leves, *, terminee=False):
    db.add(Evenement(type_action="levee", culture=semis.culture, origine_graines_id=semis.id,
                     quantite=leves, unite="plants", levee_terminee=terminee,
                     date=_dt(jour), potager_id=semis.potager_id))
    db.commit()


def _deplacer(db, semis, jour, parcelle_id):
    db.add(Evenement(type_action="deplacement", culture=semis.culture, origine_graines_id=semis.id,
                     parcelle_id=parcelle_id, date=_dt(jour), potager_id=semis.potager_id))
    db.commit()


def _planter(db, culture, variete, plants, *, potager_id=1):
    """Une culture en cours au potager : de quoi la voir à l'écran Stocks."""
    db.add(Evenement(type_action="plantation", culture=culture, variete=variete, quantite=plants,
                     unite="plants", parcelle_id=1, date=datetime(2026, 9, 1), potager_id=potager_id))
    db.commit()


def _parcours(db, ref=LE_19_OCT, ctx=CTX):
    lots = calcul_lots_pepiniere(db, ref, potager_id=ctx.potager_id)
    return ech.lire_echeances(db, ctx, lots, ref)["parcours"]


def _du_lot(parcours, semis):
    """Les étiquettes d'un lot, dans l'ordre de ses fragments (la liste, elle, suit l'urgence)."""
    return sorted(
        (e for e in parcours["etiquettes"] if e["lot"]["id"] == f"semis-{semis.id}"),
        key=lambda e: e["fragment"]["rang"],
    )


def _seule(parcours, semis):
    etiquettes = _du_lot(parcours, semis)
    assert len(etiquettes) == 1, etiquettes
    return etiquettes[0]


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — la décision produit est figée
# ═════════════════════════════════════════════════════════════════════════════
def test_us240_ca6_seuil_sortir_bientot_fige():
    """Un changement involontaire du seuil casse ce test, pas la Pépinière."""
    assert ech.SEUIL_SORTIR_BIENTOT_JOURS == 15
    assert ech.STADES == ("levee", "godet", "endurcissement", "pret")


# ═════════════════════════════════════════════════════════════════════════════
# CA2-CA4, CA7 — étiquettes et fragments
# ═════════════════════════════════════════════════════════════════════════════
class TestEtiquettes:

    def test_us240_gherkin_lot_coupe_par_le_stade(self, db):
        """Lot 23 : 16 graines, 12 repiquées, 4 non soldées → deux étiquettes, levée d'abord."""
        _referentiel(db, "tomate cerise", godet=(10, 12), terre=(42, 51))
        s = _semis(db, "tomate cerise", date(2026, 9, 15), graines=16, numero=23)
        _godets(db, s, date(2026, 9, 27), 12)
        levee, godet = _du_lot(_parcours(db), s)
        assert (levee["stade"], levee["fragment"]) == ("levee", {"rang": 1, "total": 2})
        assert levee["quantites"]["graines"] == 4
        assert (godet["stade"], godet["fragment"]) == ("godet", {"rang": 2, "total": 2})
        assert godet["quantites"]["godets"] == 12

    def test_us240_ca7_graines_restantes_sans_echeance_de_repiquage(self, db):
        """[A33] Les 4 graines restantes n'attendent plus de repiquage : ni jours, ni retard."""
        _referentiel(db, "tomate cerise", godet=(10, 12), terre=(42, 51))
        s = _semis(db, "tomate cerise", date(2026, 9, 15), graines=16, numero=23)
        _godets(db, s, date(2026, 9, 27), 12)
        levee = _du_lot(_parcours(db), s)[0]
        assert levee["etat"] == "levee_en_cours"
        assert levee["echeance"]["jours"] is None and levee["echeance"]["en_retard"] is False
        assert levee["echeance"]["du"] is None and levee["echeance"]["raison"] is None
        assert levee["soldable_par_levee_terminee"] is True
        assert levee["mention"] == "12 déjà en godet"

    def test_us240_cas_reel_levee_notee_apres_un_repiquage_partiel(self, db):
        """Lot 1 : 50 graines, 40 levées puis 40 repiquées (« 40 plants », sans « sur N »),
        puis 45 levées au total : deux étiquettes, dont 10 graines restantes avec 5 levées."""
        _referentiel(db, "chou")
        s = _semis(db, "chou", date(2026, 2, 15), graines=50, numero=1)
        _levee(db, s, date(2026, 3, 19), 40)
        db.add(Evenement(type_action="mise_en_godet", culture="chou", nb_plants_godets=40,
                         nb_graines_semees=40, origine_graines_id=s.id, parcelle_id=None,
                         date=datetime(2026, 3, 25), potager_id=1))
        db.commit()
        _levee(db, s, date(2026, 10, 19), 45)
        levee, godet = _du_lot(_parcours(db), s)
        assert levee["fragment"] == {"rang": 1, "total": 2} and godet["fragment"] == {"rang": 2, "total": 2}
        assert (levee["stade"], levee["etat"]) == ("levee", "levee_en_cours")
        assert levee["quantites"]["graines"] == 10 and levee["quantites"]["leves"] == 5
        assert levee["mention"] == "40 déjà en godet" and levee["echeance"]["jours"] is None
        assert godet["quantites"]["godets"] == 40 and godet["emplacement_id"] == SERRE

    def test_us240_ca2_lot_non_coupe_un_seul_fragment(self, db):
        _referentiel(db, "chou", godet=(10, 12))
        s = _semis(db, "chou", date(2026, 10, 15))
        e = _seule(_parcours(db), s)
        assert e["fragment"] == {"rang": 1, "total": 1}

    def test_us240_ca4_identite_et_quantites(self, db):
        _referentiel(db, "chou frisé", godet=(10, 12))
        s = _semis(db, "chou frisé", date(2026, 10, 1), graines=24, numero=28, variete="Vert du Nord")
        _levee(db, s, date(2026, 10, 9), 18)
        e = _seule(_parcours(db), s)
        assert e["lot"] == {"id": f"semis-{s.id}", "numero": 28, "culture": "chou frisé",
                            "variete": "Vert du Nord", "date_semis": "2026-10-01"}
        assert e["quantites"] == {"graines": 24, "leves": 18, "godets": None, "unite": "graines"}
        assert e["emplacement_id"] == SERRE
        assert e["id"] == f"semis-{s.id}:levee:{SERRE}"

    def test_us240_ca2_levee_terminee_solde_les_non_levees(self, db):
        """Levée terminée à 10 sur 16, 10 repiqués : il ne reste rien en levée."""
        _referentiel(db, "chou", godet=(10, 12), terre=(60, 70))
        s = _semis(db, "chou", date(2026, 9, 20), graines=16)
        _levee(db, s, date(2026, 9, 28), 10, terminee=True)
        _godets(db, s, date(2026, 10, 2), 10)
        assert [e["stade"] for e in _du_lot(_parcours(db), s)] == ["godet"]

    def test_us240_ca2_levee_terminee_les_leves_restent_a_repiquer(self, db):
        """Levée terminée à 18 sur 24, rien repiqué : l'étiquette « en levée » reste."""
        _referentiel(db, "chou", godet=(10, 12))
        s = _semis(db, "chou", date(2026, 10, 1), graines=24)
        _levee(db, s, date(2026, 10, 9), 18, terminee=True)
        e = _seule(_parcours(db), s)
        assert e["stade"] == "levee" and e["quantites"]["graines"] == 18

    def test_us240_ca2_semis_sans_quantite_est_en_levee_sans_nombre(self, db):
        _referentiel(db, "chou", godet=(10, 12))
        s = _semis(db, "chou", date(2026, 10, 15), graines=None)
        e = _seule(_parcours(db), s)
        assert e["stade"] == "levee" and e["quantites"]["graines"] is None

    def test_us240_ca2_lot_epuise_n_a_aucune_etiquette(self, db):
        _referentiel(db, "laitue", godet=(10, 12), terre=(30, 40))
        s = _semis(db, "laitue", date(2026, 8, 1), graines=6)
        g = _godets(db, s, date(2026, 8, 12), 6)
        db.add(Evenement(type_action="plantation", culture="laitue", quantite=6, unite="plants",
                         source_evenement_ids=str(g.id), parcelle_id=1,
                         date=datetime(2026, 9, 20), potager_id=1))
        db.commit()
        assert _du_lot(_parcours(db), s) == []

    def test_us240_ca2_lot_sans_semis_rattache(self, db):
        """Des godets sans semis : une étiquette de godets, « durée ? », date de semis inconnue."""
        _referentiel(db, "tomate", terre=(42, 51))
        db.add(Evenement(type_action="mise_en_godet", culture="tomate", nb_plants_godets=8,
                         parcelle_id=SERRE, date=datetime(2026, 9, 15), potager_id=1))
        db.commit()
        etiquettes = _parcours(db)["etiquettes"]
        assert len(etiquettes) == 1
        e = etiquettes[0]
        assert (e["stade"], e["etat"]) == ("godet", "duree_inconnue")
        assert e["echeance"]["raison"] == "date de semis inconnue"
        assert e["lot"]["date_semis"] is None

    def test_us240_ca3_graines_a_la_parcelle_du_semis_godets_a_l_emplacement_courant(self, db):
        """Semé en serre, repiqué au châssis : chaque fragment sur sa ligne."""
        _referentiel(db, "chou", godet=(10, 12), terre=(60, 70))
        s = _semis(db, "chou", date(2026, 9, 20), graines=16)
        _godets(db, s, date(2026, 10, 2), 10, parcelle_id=CHASSIS)
        levee, godet = _du_lot(_parcours(db), s)
        assert levee["emplacement_id"] == SERRE
        assert godet["emplacement_id"] == CHASSIS

    def test_us240_ca4_mention_deplaces_le(self, db):
        _referentiel(db, "poivron", terre=(101, 111))
        s = _semis(db, "poivron", date(2026, 8, 1), graines=6, numero=21)
        _godets(db, s, date(2026, 9, 1), 6)
        _deplacer(db, s, date(2026, 10, 1), CHASSIS)
        e = _seule(_parcours(db), s)
        assert e["emplacement_id"] == CHASSIS
        assert e["mention"] == "déplacés le 1er oct."


# ═════════════════════════════════════════════════════════════════════════════
# CA5, CA6, CA8 — table des colonnes et états
# ═════════════════════════════════════════════════════════════════════════════
class TestColonnesEtEtats:

    def test_us240_levee_repiquer_retard(self, db):
        """Chou frisé #28 : semé 1er oct., repiquage prévu 11–13 oct. → +6 j."""
        _referentiel(db, "chou frisé", godet=(10, 12))
        s = _semis(db, "chou frisé", date(2026, 10, 1), graines=24, numero=28)
        e = _seule(_parcours(db), s)
        assert (e["stade"], e["etat"]) == ("levee", "repiquer_retard")
        assert e["echeance"]["jours"] == 6 and e["echeance"]["en_retard"] is True
        assert (e["echeance"]["du"], e["echeance"]["au"]) == ("2026-10-11", "2026-10-13")
        assert e["echeance"]["debut_regle"] == "2026-10-01"

    def test_us240_levee_a_repiquer(self, db):
        _referentiel(db, "chou", godet=(10, 12))
        s = _semis(db, "chou", date(2026, 10, 8))
        e = _seule(_parcours(db), s)
        assert (e["stade"], e["etat"], e["echeance"]["jours"]) == ("levee", "a_repiquer", 0)

    def test_us240_levee_en_cours(self, db):
        _referentiel(db, "chou", godet=(10, 12))
        s = _semis(db, "chou", date(2026, 10, 15))
        e = _seule(_parcours(db), s)
        assert (e["stade"], e["etat"], e["echeance"]["jours"]) == ("levee", "levee_en_cours", 6)

    def test_us240_ca8_levee_duree_inconnue(self, db):
        """Carotte sans délai semis → godet : pas d'échéance, la raison est rendue."""
        _referentiel(db, "carotte")
        s = _semis(db, "carotte", date(2026, 9, 14), parcelle_id=CHASSIS)
        e = _seule(_parcours(db), s)
        assert (e["stade"], e["etat"]) == ("levee", "duree_inconnue")
        assert e["echeance"]["jours"] is None and e["echeance"]["du"] is None
        assert e["echeance"]["raison"] == "délai semis → godet non renseigné pour la culture « carotte »"

    def test_us240_godet_en_cours(self, db):
        _referentiel(db, "chou", terre=(60, 70))
        s = _semis(db, "chou", date(2026, 10, 1), graines=10)
        _godets(db, s, date(2026, 10, 12), 10)
        e = _seule(_parcours(db), s)
        assert (e["stade"], e["etat"], e["echeance"]["jours"]) == ("godet", "en_cours", 42)

    def test_us240_godet_sortir_bientot(self, db):
        """Tomate cerise : mise en terre 27 oct.–5 nov. → « Sortir bientôt », 8 j."""
        _referentiel(db, "tomate cerise", terre=(42, 51))
        s = _semis(db, "tomate cerise", date(2026, 9, 15), graines=12)
        _godets(db, s, date(2026, 9, 27), 12)
        e = _seule(_parcours(db), s)
        assert (e["stade"], e["etat"], e["echeance"]["jours"]) == ("godet", "sortir_bientot", 8)
        assert (e["echeance"]["du"], e["echeance"]["au"]) == ("2026-10-27", "2026-11-05")

    def test_us240_godet_le_seuil_de_15_jours_est_inclus(self, db):
        _referentiel(db, "chou", terre=(30, 40))
        s = _semis(db, "chou", date(2026, 10, 4), graines=10)   # terre dès le 3 nov. : 15 j
        _godets(db, s, date(2026, 10, 12), 10)
        assert _seule(_parcours(db), s)["etat"] == "sortir_bientot"

    def test_us240_ca8_godet_duree_inconnue(self, db):
        _referentiel(db, "tomate", godet=(10, 12))
        s = _semis(db, "tomate", date(2026, 9, 15), graines=8)
        _godets(db, s, date(2026, 9, 27), 8)
        e = _seule(_parcours(db), s)
        assert (e["stade"], e["etat"]) == ("godet", "duree_inconnue")
        assert e["echeance"]["raison"] == "délai avant plantation non renseigné pour la culture « tomate »"
        assert e["echeance"]["du"] is None

    def test_us240_endurcissement_compte_a_rebours(self, db):
        """Poireau #24 : terre dès le 23 oct., en serre chaude → J3 sur 7."""
        _referentiel(db, "poireau", terre=(83, 90))
        s = _semis(db, "poireau", date(2026, 8, 1), graines=30, numero=24)
        _godets(db, s, date(2026, 8, 20), 30)
        e = _seule(_parcours(db), s)
        assert (e["stade"], e["etat"]) == ("endurcissement", "endurcir")
        assert e["echeance"]["endurcissement"] == {"jour": 3, "sur": 7}
        assert e["echeance"]["jours"] == 4
        assert e["echeance"]["debut_regle"] == "2026-10-16"

    def test_us240_endurcissement_pepiniere_de_type_inconnu(self, db):
        _referentiel(db, "poireau", terre=(83, 90))
        s = _semis(db, "poireau", date(2026, 8, 1), graines=30, parcelle_id=VERANDA)
        _godets(db, s, date(2026, 8, 20), 30, parcelle_id=VERANDA)
        assert _seule(_parcours(db), s)["etat"] == "endurcir"

    def test_us240_gherkin_godet_en_pepiniere_froide(self, db):
        """[A35] Lot 21 au châssis froid, mise en terre 10–20 nov. → s'endurcit sur place."""
        _referentiel(db, "poivron", terre=(101, 111))
        s = _semis(db, "poivron", date(2026, 8, 1), graines=6, numero=21, parcelle_id=CHASSIS)
        _godets(db, s, date(2026, 9, 1), 6, parcelle_id=CHASSIS)
        e = _seule(_parcours(db), s)
        assert (e["stade"], e["etat"]) == ("endurcissement", "endurcit_sur_place")
        assert e["echeance"]["endurcissement"] is None   # pas de compte à rebours
        assert e["echeance"]["jours"] == 22
        assert e["emplacement_id"] == CHASSIS

    def test_us240_froide_deplace_recemment_compte_depuis_le_deplacement(self, db):
        _referentiel(db, "poivron", terre=(101, 111))
        s = _semis(db, "poivron", date(2026, 8, 1), graines=6)
        _godets(db, s, date(2026, 9, 1), 6)
        _deplacer(db, s, date(2026, 10, 16), CHASSIS)
        e = _seule(_parcours(db), s)
        assert (e["stade"], e["etat"]) == ("endurcissement", "endurcir")
        assert e["echeance"]["endurcissement"] == {"jour": 3, "sur": 7}

    def test_us240_pret_a_sortir(self, db):
        _referentiel(db, "laitue", terre=(75, 85))
        s = _semis(db, "laitue", date(2026, 8, 1), graines=20)
        _godets(db, s, date(2026, 8, 15), 20)
        e = _seule(_parcours(db), s)
        assert (e["stade"], e["etat"], e["echeance"]["jours"]) == ("pret", "a_sortir", 0)

    def test_us240_gherkin_pret_a_sortir_en_retard(self, db):
        """Lot 30 : laitue, 20 godets en serre, mise en terre 1er–10 oct. → 9 j de retard."""
        _referentiel(db, "laitue", terre=(61, 70))
        s = _semis(db, "laitue", date(2026, 8, 1), graines=20, numero=30)
        _godets(db, s, date(2026, 9, 1), 20)      # moins de 60 j : pas dormant
        p = _parcours(db)
        e = _seule(p, s)
        assert (e["stade"], e["etat"]) == ("pret", "sortir_retard")
        assert e["echeance"]["jours"] == 9 and e["echeance"]["en_retard"] is True
        assert p["compteurs"]["a_sortir"] == {"total": 1, "retard": True}

    def test_us240_pret_quel_que_soit_le_type_de_pepiniere(self, db):
        _referentiel(db, "laitue", terre=(61, 70))
        s = _semis(db, "laitue", date(2026, 8, 1), graines=20, parcelle_id=CHASSIS)
        _godets(db, s, date(2026, 9, 1), 20, parcelle_id=CHASSIS)
        assert _seule(_parcours(db), s)["stade"] == "pret"

    def test_us240_date_de_reference_passee(self, db):
        """Au 1er octobre, la laitue d'août n'est pas encore prête : « en godet »."""
        _referentiel(db, "laitue", terre=(75, 85))
        s = _semis(db, "laitue", date(2026, 8, 1), graines=20)
        _godets(db, s, date(2026, 8, 15), 20)
        e = _seule(_parcours(db, ref=date(2026, 10, 1)), s)
        assert (e["stade"], e["etat"], e["echeance"]["jours"]) == ("godet", "sortir_bientot", 14)


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — ordre d'urgence
# ═════════════════════════════════════════════════════════════════════════════
def test_us240_ca9_ordre_d_urgence_dans_une_case(db):
    """En levée, en serre : retard de 6 j, retard de 2 j, échéance dans 6 j, sans échéance."""
    _referentiel(db, "chou", godet=(10, 12))
    _referentiel(db, "carotte")
    sans = _semis(db, "carotte", date(2026, 10, 1), numero=1)
    proche = _semis(db, "chou", date(2026, 10, 15), numero=2)
    petit = _semis(db, "chou", date(2026, 10, 5), numero=3)
    grand = _semis(db, "chou", date(2026, 10, 1), numero=4)
    ordre = [e["lot"]["numero"] for e in _parcours(db)["etiquettes"]
             if e["stade"] == "levee" and e["emplacement_id"] == SERRE]
    assert ordre == [grand.numero_lot, petit.numero_lot, proche.numero_lot, sans.numero_lot]


# ═════════════════════════════════════════════════════════════════════════════
# CA10 — lignes du kanban
# ═════════════════════════════════════════════════════════════════════════════
class TestLignes:

    def test_us240_gherkin_pepiniere_vide_listee(self, db):
        _referentiel(db, "chou", godet=(10, 12))
        _semis(db, "chou", date(2026, 10, 15))
        lignes = {l["nom"]: l for l in _parcours(db)["pepinieres"]}
        assert list(lignes) == ["Serre", "Châssis froid", "Véranda"]
        assert lignes["Châssis froid"]["nb_etiquettes"] == 0
        assert lignes["Châssis froid"]["type_pepiniere"] == "froide"
        assert lignes["Véranda"]["type_pepiniere"] is None
        assert lignes["Serre"]["superficie_m2"] == 2.5

    def test_us240_ca10_compte_lots_etiquettes_alertes(self, db):
        _referentiel(db, "tomate cerise", godet=(10, 12), terre=(42, 51))
        _referentiel(db, "chou frisé", godet=(10, 12))
        s = _semis(db, "tomate cerise", date(2026, 9, 15), graines=16)
        _godets(db, s, date(2026, 9, 27), 12)
        _semis(db, "chou frisé", date(2026, 10, 1))
        serre = _parcours(db)["pepinieres"][0]
        assert (serre["nb_lots"], serre["nb_etiquettes"], serre["nb_alertes"]) == (2, 3, 1)

    def test_us240_ca10_prochaine_sortie(self, db):
        """« Rien à sortir aujourd'hui. Prochain : Poireau #24, le 23 oct. »"""
        _referentiel(db, "poireau", terre=(83, 90))
        s = _semis(db, "poireau", date(2026, 8, 1), graines=30, numero=24)
        _godets(db, s, date(2026, 8, 20), 30)
        serre = _parcours(db)["pepinieres"][0]
        assert serre["prochaine_sortie"] == {"lot_numero": 24, "culture": "poireau", "du": "2026-10-23"}

    def test_us240_ca10_lot_sans_emplacement(self, db):
        _referentiel(db, "tomate", godet=(10, 12))
        s = _semis(db, "tomate", date(2026, 10, 15), parcelle_id=None)
        p = _parcours(db)
        assert _seule(p, s)["emplacement_id"] is None
        assert p["sans_emplacement"]["nb_etiquettes"] == 1

    def test_us240_ca10_sans_emplacement_absent_quand_vide(self, db):
        _referentiel(db, "chou", godet=(10, 12))
        _semis(db, "chou", date(2026, 10, 15))
        assert _parcours(db)["sans_emplacement"] is None


# ═════════════════════════════════════════════════════════════════════════════
# CA11 — compteurs
# ═════════════════════════════════════════════════════════════════════════════
class TestCompteurs:

    def test_us240_ca11_a_repiquer_compte_les_etiquettes_et_le_retard(self, db):
        _referentiel(db, "chou", godet=(10, 12))
        _semis(db, "chou", date(2026, 10, 1))    # en retard
        _semis(db, "chou", date(2026, 10, 8))    # à repiquer
        _semis(db, "chou", date(2026, 10, 15))   # à venir : non compté
        assert _parcours(db)["compteurs"]["a_repiquer"] == {"total": 2, "retard": True}

    def test_us240_ca11_a_repiquer_sans_retard(self, db):
        _referentiel(db, "chou", godet=(10, 12))
        _semis(db, "chou", date(2026, 10, 8))
        assert _parcours(db)["compteurs"]["a_repiquer"] == {"total": 1, "retard": False}

    def test_us240_ca11_a_sortir_compte_bientot_et_atteinte(self, db):
        _referentiel(db, "tomate cerise", terre=(42, 51))
        _referentiel(db, "laitue", terre=(75, 85))
        for culture, jour in (("tomate cerise", date(2026, 9, 15)), ("laitue", date(2026, 8, 1))):
            _godets(db, _semis(db, culture, jour, graines=10), date(2026, 9, 27), 10)
        assert _parcours(db)["compteurs"]["a_sortir"] == {"total": 2, "retard": False}

    def test_us240_ca11_endurcit_compte_le_compte_a_rebours_et_le_froid(self, db):
        _referentiel(db, "poireau", terre=(83, 90))
        _referentiel(db, "poivron", terre=(101, 111))
        _godets(db, _semis(db, "poireau", date(2026, 8, 1), graines=30), date(2026, 8, 20), 30)
        _godets(db, _semis(db, "poivron", date(2026, 8, 1), graines=6, parcelle_id=CHASSIS),
                date(2026, 9, 1), 6, parcelle_id=CHASSIS)
        assert _parcours(db)["compteurs"]["endurcit"] == {"total": 2, "retard": False}

    def test_us240_ca11_les_compteurs_comptent_des_etiquettes(self, db):
        """Un lot coupé compte deux étiquettes, pas un lot (A31)."""
        _referentiel(db, "tomate cerise", godet=(10, 12), terre=(42, 51))
        s = _semis(db, "tomate cerise", date(2026, 9, 15), graines=16)
        _godets(db, s, date(2026, 9, 27), 12)
        p = _parcours(db)
        assert len(p["etiquettes"]) == 2
        assert p["compteurs"]["a_sortir"]["total"] == 1      # le fragment de godets seul
        assert p["compteurs"]["a_repiquer"]["total"] == 0    # A33 : les graines restantes n'attendent rien

    def test_us240_ca11_a_semer_et_dormants_comptent_cultures_et_lots(self, db):
        _referentiel(db, "laitue d'hiver", fenetre=(9, 10))
        _planter(db, "laitue d'hiver", "Merveille d'hiver", 4)
        _referentiel(db, "tomate")
        _semis(db, "tomate", date(2026, 4, 1), graines=5)
        c = _parcours(db)["compteurs"]
        assert c["a_semer"] == {"total": 1, "retard": False}
        assert c["dormants"] == {"total": 1, "retard": False}


# ═════════════════════════════════════════════════════════════════════════════
# CA12 — dormants hors kanban
# ═════════════════════════════════════════════════════════════════════════════
class TestDormants:

    def test_us240_gherkin_un_lot_dormant(self, db):
        """Lot 7 : 5 graines non levées, rien depuis 201 jours → tiroir, aucune étiquette."""
        _referentiel(db, "tomate")
        s = _semis(db, "tomate", date(2026, 4, 1), graines=5, numero=7, variete="cœur de bœuf")
        p = _parcours(db)
        assert _du_lot(p, s) == []
        (d,) = p["dormants"]
        assert d["lot"]["numero"] == 7 and d["lot"]["date_semis"] == "2026-04-01"
        assert d["jours_sans_geste"] == 201
        assert d["reste"] == {"graines": 5, "godets": None, "unite": "graines"}
        assert d["a_des_godets"] is False

    def test_us240_ca12_dormant_avec_godets(self, db):
        """[A37] Un dormant qui a des godets se signale : « Mettre en terre » reste possible."""
        _referentiel(db, "basilic", terre=(30, 40))
        s = _semis(db, "basilic", date(2026, 5, 1), graines=6)
        _godets(db, s, date(2026, 5, 20), 6)
        (d,) = _parcours(db)["dormants"]
        assert d["a_des_godets"] is True and d["reste"]["godets"] == 6

    def test_us240_ca12_du_plus_ancien_geste_au_plus_recent(self, db):
        _referentiel(db, "tomate")
        recent = _semis(db, "tomate", date(2026, 7, 1), graines=5, numero=8)
        ancien = _semis(db, "tomate", date(2026, 3, 20), graines=5, numero=3)
        assert [d["lot"]["numero"] for d in _parcours(db)["dormants"]] == [
            ancien.numero_lot, recent.numero_lot]


# ═════════════════════════════════════════════════════════════════════════════
# CA13-CA15 — le bon moment pour semer
# ═════════════════════════════════════════════════════════════════════════════
class TestASemer:

    def test_us240_gherkin_a_semer_limite_aux_graines_dont_on_dispose(self, db):
        _referentiel(db, "laitue d'hiver", fenetre=(9, 10))
        _referentiel(db, "mache", fenetre=(9, 10))
        _planter(db, "laitue d'hiver", "Merveille d'hiver", 4)
        p = _parcours(db)
        (laitue,) = p["a_semer"]
        assert laitue["culture"] == "laitue d'hiver"
        assert laitue["varietes_en_stock"] == ["Merveille d'hiver"]
        assert laitue["jours_restants"] == 12
        assert p["a_semer_sans_graines"] == [{"culture": "mache"}]
        assert p["source_stock_graines"] == "cultures_en_cours"

    def test_us240_ca13_fenetre_bornes_et_part_ecoulee(self, db):
        _referentiel(db, "laitue d'hiver", fenetre=(9, 10))
        _planter(db, "laitue d'hiver", "Merveille d'hiver", 4)
        (laitue,) = _parcours(db)["a_semer"]
        assert (laitue["du"], laitue["au"]) == ("2026-09-01", "2026-10-31")
        assert laitue["periode"] == "1er sept.–31 oct."
        assert laitue["part_ecoulee"] == 0.8
        assert laitue["fenetre"] == "septembre → octobre"   # le champ d'US-214, inchangé

    def test_us240_ca15_variete_a_zero_n_est_pas_en_stock(self, db):
        _referentiel(db, "laitue d'hiver", fenetre=(9, 10))
        _planter(db, "laitue d'hiver", "Merveille d'hiver", 4)
        db.add(Evenement(type_action="perte", culture="laitue d'hiver", variete="Merveille d'hiver",
                         quantite=4, unite="plants", parcelle_id=1,
                         date=datetime(2026, 10, 1), potager_id=1))
        db.commit()
        p = _parcours(db)
        assert p["a_semer"] == []
        assert p["a_semer_sans_graines"] == [{"culture": "laitue d'hiver"}]

    def test_us240_ca15_varietes_sans_doublon_variete_non_precisee_tue(self, db):
        _referentiel(db, "feve", fenetre=(10, 11))
        _planter(db, "feve", "Aguadulce", 4)
        _planter(db, "feve", "Aguadulce", 2)
        _planter(db, "feve", None, 3)
        (feve,) = _parcours(db)["a_semer"]
        assert feve["varietes_en_stock"] == ["Aguadulce"]

    def test_us240_ca14_aucune_culture_dans_sa_fenetre(self, db):
        _referentiel(db, "laitue", fenetre=(3, 5))
        p = _parcours(db)
        assert p["a_semer"] == [] and p["a_semer_sans_graines"] == []

    def test_us240_ca13_un_lot_en_cours_ecarte_la_culture(self, db):
        _referentiel(db, "laitue d'hiver", godet=(10, 12), fenetre=(9, 10))
        _planter(db, "laitue d'hiver", "Merveille d'hiver", 4)
        _semis(db, "laitue d'hiver", date(2026, 10, 15))
        p = _parcours(db)
        assert p["a_semer"] == [] and p["a_semer_sans_graines"] == []

    @pytest.mark.parametrize("ref, attendu", [
        (date(2026, 10, 31), {"jours_restants": 0, "part_ecoulee": 1.0}),
        (date(2026, 9, 1), {"jours_restants": 60, "part_ecoulee": 0.02}),
    ])
    def test_us240_ca13_jours_restants_en_fin_de_mois(self, ref, attendu):
        bornes = ech._bornes_fenetre(9, 10, ref)
        assert {k: bornes[k] for k in attendu} == attendu

    def test_us240_ca13_fevrier_bissextile(self):
        assert ech._bornes_fenetre(1, 2, date(2028, 2, 10))["au"] == "2028-02-29"

    @pytest.mark.parametrize("ref, du, au, restants", [
        (date(2026, 11, 20), "2026-11-01", "2027-02-28", 100),   # partie d'automne
        (date(2027, 1, 15), "2026-11-01", "2027-02-28", 44),     # partie d'hiver
    ])
    def test_us240_ca13_fenetre_a_cheval_sur_l_annee(self, ref, du, au, restants):
        bornes = ech._bornes_fenetre(11, 2, ref)
        assert (bornes["du"], bornes["au"], bornes["jours_restants"]) == (du, au, restants)


# ═════════════════════════════════════════════════════════════════════════════
# CA16-CA18 — une lecture, lecture seule, isolation
# ═════════════════════════════════════════════════════════════════════════════
class TestContraintes:

    def test_us240_ca16_une_seule_lecture_du_stock(self, db, monkeypatch):
        for nom in ("laitue d'hiver", "mache", "epinard"):
            _referentiel(db, nom, fenetre=(9, 10))
        appels = []
        lire = svc_stock.calcul_stock_varietes
        monkeypatch.setattr(svc_stock, "calcul_stock_varietes",
                            lambda *a, **k: appels.append(1) or lire(*a, **k))
        _parcours(db)
        assert len(appels) == 1

    def test_us240_ca16_aucune_lecture_du_stock_sans_culture_candidate(self, db, monkeypatch):
        _referentiel(db, "chou", godet=(10, 12))
        _semis(db, "chou", date(2026, 10, 1))
        monkeypatch.setattr(svc_stock, "calcul_stock_varietes",
                            lambda *a, **k: pytest.fail("stock lu sans candidate"))
        _parcours(db)

    def test_us240_ca16_les_pepinieres_passees_ne_sont_pas_relues(self, db, monkeypatch):
        monkeypatch.setattr(ech, "_pepinieres_du_potager", lambda *a: pytest.fail("relu"))
        lots = calcul_lots_pepiniere(db, LE_19_OCT, potager_id=1)
        p = ech.lire_echeances(db, CTX, lots, LE_19_OCT, pepinieres=[{"id": SERRE, "nom": "Serre"}])
        assert [l["nom"] for l in p["parcours"]["pepinieres"]] == ["Serre"]

    def test_us240_ca17_lecture_seule(self, db):
        _referentiel(db, "laitue d'hiver", fenetre=(9, 10))
        _planter(db, "laitue d'hiver", "Merveille d'hiver", 4)
        _referentiel(db, "tomate")
        _semis(db, "tomate", date(2026, 4, 1), graines=5)
        avant = db.query(Evenement).count()
        stocks_avant = svc_stock.calcul_stock_varietes(db, CTX, LE_19_OCT)
        _parcours(db)
        db.expire_all()
        assert db.query(Evenement).count() == avant
        assert svc_stock.calcul_stock_varietes(db, CTX, LE_19_OCT) == stocks_avant
        assert not db.new and not db.dirty and not db.deleted

    def test_us240_ca18_isolation_lots_et_pepinieres(self, db):
        _referentiel(db, "chou", godet=(10, 12))
        a = _semis(db, "chou", date(2026, 10, 1), potager_id=1)
        b = _semis(db, "chou", date(2026, 10, 1), potager_id=2, parcelle_id=5)
        pa, pb = _parcours(db, ctx=CTX), _parcours(db, ctx=CTX_B)
        assert {e["lot"]["id"] for e in pa["etiquettes"]} == {f"semis-{a.id}"}
        assert {e["lot"]["id"] for e in pb["etiquettes"]} == {f"semis-{b.id}"}
        assert [l["nom"] for l in pb["pepinieres"]] == ["Serre B"]

    def test_us240_ca18_isolation_du_stock_de_graines(self, db):
        """Les graines du potager B ne rendent pas la laitue « à semer » chez A."""
        _referentiel(db, "laitue d'hiver", fenetre=(9, 10))
        _planter(db, "laitue d'hiver", "Merveille d'hiver", 4, potager_id=2)
        p = _parcours(db, ctx=CTX)
        assert p["a_semer"] == []
        assert p["a_semer_sans_graines"] == [{"culture": "laitue d'hiver"}]


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — l'API ajoute, sans rien retirer
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def _moteur_api():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def client_api(_moteur_api, monkeypatch):
    from app.api import main

    monkeypatch.setattr(main, "SessionLocal", sessionmaker(bind=_moteur_api))
    main.app.state.limiter.reset()
    with TestClient(main.app) as client:
        yield client


def _jardin(client, moteur):
    """Un compte, son potager, une serre et un lot de chou en retard de repiquage."""
    from app.services import auth as svc_auth

    session = sessionmaker(bind=moteur)()
    user = svc_auth.inscrire_utilisateur(session, "jardinier@example.com", "motdepasse123")
    entete = {"Authorization": f"Bearer {svc_auth.creer_access_token(user.id)}"}
    client.post("/potagers", json={"nom": "Jardin"}, headers=entete)
    potager = session.query(Potager).filter(Potager.proprietaire_id == user.id).first()
    potager.zone_climatique = "oceanique"
    session.add(ReferentielSource(id=1, code="test", libelle="Test", licence="CC0",
                                  attribution="Valeurs de test", partageable=True, importee=True))
    serre = Parcelle(nom="Serre", nom_normalise="serre", potager_id=potager.id,
                     est_pepiniere=True, type_pepiniere="chaude")
    fiche = CultureConfig(nom="chou", type_organe_recolte="fruit")
    session.add_all([serre, fiche])
    session.flush()
    it = ItineraireCultural(culture_id=fiche.id, nom="standard", nom_normalise="standard", source_id=1)
    session.add(it)
    session.flush()
    session.add(DureeCulturale(itineraire_id=it.id, etape=cal.ETAPE_SEMIS_GODET,
                               jours_min=10, jours_max=12, source_id=1))
    session.add(Evenement(type_action="semis", culture="chou", quantite=48, unite="graines",
                          parcelle_id=serre.id, date=datetime(2026, 10, 1),
                          potager_id=potager.id, numero_lot=128))
    session.commit()
    session.close()
    return entete


def test_us240_ca1_l_api_porte_le_parcours(client_api, _moteur_api):
    entete = _jardin(client_api, _moteur_api)
    corps = client_api.get("/pepiniere/lots", params={"date_ref": "2026-10-19"}, headers=entete).json()
    parcours = corps["parcours"]
    assert set(parcours) == {
        "stades", "pepinieres", "sans_emplacement", "etiquettes", "compteurs",
        "a_semer", "a_semer_sans_graines", "source_stock_graines", "dormants",
        "calendrier_semis",   # [US-218] ajouté par la maquette HF
    }
    (etiquette,) = parcours["etiquettes"]
    assert etiquette["lot"]["numero"] == 128 and etiquette["etat"] == "repiquer_retard"
    assert [p["nom"] for p in parcours["pepinieres"]] == ["Serre"]


def test_us240_ca1_aucun_champ_existant_retire(client_api, _moteur_api):
    entete = _jardin(client_api, _moteur_api)
    corps = client_api.get("/pepiniere/lots", params={"date_ref": "2026-10-19"}, headers=entete).json()
    assert {"lots", "total", "date_ref_effective", "resume", "pepinieres"} <= set(corps)
    lot = corps["lots"][0]
    assert {"echeances", "action_suggeree", "rang_urgence", "ou_mettre"} <= set(lot)
    assert set(corps["resume"]) == {"a_repiquer", "a_endurcir", "prets_pour_le_plan", "a_semer"}


# ═════════════════════════════════════════════════════════════════════════════
# CA20, CA21 — documentation
# ═════════════════════════════════════════════════════════════════════════════
def test_us240_ca20_fiche_de_domaine():
    texte = (RACINE / "docs" / "domaines" / "pepiniere.md").read_text(encoding="utf-8")
    assert "US-240" in texte
    for attendu in ("En levée", "En godet", "Endurcissement", "Prêt à sortir", "15 jours",
                    "A33", "A34", "A35", "sortir_bientot", "endurcit_sur_place", "fragment"):
        assert attendu in texte, attendu


def test_us240_ca21_corpus_jardinier():
    texte = (RACINE / "data" / "connaissance" / "doc_app" / "pepiniere-par-lot.md").read_text(encoding="utf-8")
    for attendu in ("deux étiquettes", "plus d'échéance", "cultures en cours"):
        assert attendu in texte.lower(), attendu

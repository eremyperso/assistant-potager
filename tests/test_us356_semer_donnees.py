"""
tests/test_us356_semer_donnees.py — Les données de l'onglet « Semer » [US-356 / CA7]
====================================================================================

`GET /pepiniere/lots` → `parcours` gagne deux champs EN LECTURE, sans migration ni route nouvelle :

- `a_semer_ecartees`      les cultures à la fenêtre ouverte et pourquoi elles ne sont pas proposées :
                          `lot_en_cours` (avec le n° du lot) ; `graines_epuisees` quand le stock de
                          graines du potager est connu et nul. Un motif non calculable n'est pas dit.
- `prochaines_ouvertures` plusieurs prochaines ouvertures de fenêtre (à partir de `_calendrier_semis`),
                          pas seulement la première.

Aucune fenêtre n'est recalculée côté écran (RT6) : tout vient d'ici.
Les durées écrites ici sont des VALEURS DE TEST : elles n'engagent aucune agronomie.
Lu au lundi 19 octobre 2026, comme les tests d'US-240.
"""
from __future__ import annotations

from datetime import date, datetime

from app.services import echeances_lots as ech
from tests.test_us240_parcours_plant import (  # noqa: F401 — fixtures et décor partagés
    CTX, CTX_B, LE_19_OCT, _meteo_sans_reseau, _parcours, _planter, _referentiel, _semis, db,
)
from database.models import Evenement


def test_us356_ca7_un_lot_en_cours_ecarte_la_culture_avec_son_numero(db):
    """Gherkin 2 : la laitue (#59) est écartée, « Un lot est déjà en cours (#59) »."""
    _referentiel(db, "laitue d'hiver", godet=(10, 12), fenetre=(9, 10))
    _planter(db, "laitue d'hiver", "Reine de mai", 4)
    _semis(db, "laitue d'hiver", date(2026, 10, 15), numero=59)
    p = _parcours(db)
    assert p["a_semer"] == [] and p["a_semer_sans_graines"] == []
    (ecartee,) = p["a_semer_ecartees"]
    assert ecartee == {
        "culture": "laitue d'hiver", "fenetre": "septembre → octobre",
        "motif": ech.MOTIF_LOT_EN_COURS, "lot_numero": 59,
    }


def test_us356_ca7_le_numero_cite_est_celui_du_lot_en_cours_le_plus_recent(db):
    _referentiel(db, "laitue d'hiver", godet=(10, 12), fenetre=(9, 10))
    _semis(db, "laitue d'hiver", date(2026, 10, 1), numero=41)
    _semis(db, "laitue d'hiver", date(2026, 10, 15), numero=59)
    (ecartee,) = _parcours(db)["a_semer_ecartees"]
    assert ecartee["lot_numero"] == 59


def test_us356_ca7_graines_epuisees_seulement_quand_le_stock_est_connu_et_nul(db):
    """Le stock de laitue est connu (planté puis perdu : 0) → épuisé. La mâche n'a aucune ligne : rien n'est dit."""
    _referentiel(db, "laitue d'hiver", fenetre=(9, 10))
    _referentiel(db, "mache", fenetre=(9, 10))
    _planter(db, "laitue d'hiver", "Merveille d'hiver", 4)
    db.add(Evenement(type_action="perte", culture="laitue d'hiver", variete="Merveille d'hiver",
                     quantite=4, unite="plants", parcelle_id=1, date=datetime(2026, 10, 1), potager_id=1))
    db.commit()
    p = _parcours(db)
    assert {c["culture"] for c in p["a_semer_sans_graines"]} == {"laitue d'hiver", "mache"}
    assert p["a_semer_ecartees"] == [{
        "culture": "laitue d'hiver", "fenetre": "septembre → octobre",
        "motif": ech.MOTIF_GRAINES_EPUISEES, "lot_numero": None,
    }]


def test_us356_ca7_une_culture_proposee_n_est_pas_ecartee(db):
    _referentiel(db, "feve", fenetre=(10, 11))
    _planter(db, "feve", "Aguadulce", 4)
    p = _parcours(db)
    assert [c["culture"] for c in p["a_semer"]] == ["feve"]
    assert p["a_semer_ecartees"] == []


def test_us356_ca7_fenetre_fermee_rien_a_ecarter(db):
    _referentiel(db, "laitue", godet=(10, 12), fenetre=(3, 5))
    _semis(db, "laitue", date(2026, 10, 15), numero=7)
    assert _parcours(db)["a_semer_ecartees"] == []


def test_us356_ca7_plusieurs_prochaines_ouvertures_dans_l_ordre(db):
    """Le lundi 19 oct. : le poireau s'ouvre en novembre, le petit pois en décembre, la tomate en février."""
    _referentiel(db, "poireau", fenetre=(11, 12))
    _referentiel(db, "petit pois", fenetre=(12, 2))
    _referentiel(db, "tomate", fenetre=(2, 4))
    p = _parcours(db)
    assert [(o["culture"], o["date"]) for o in p["prochaines_ouvertures"]] == [
        ("poireau", "2026-11-01"), ("petit pois", "2026-12-01"), ("tomate", "2027-02-01"),
    ]
    assert [o["jours"] for o in p["prochaines_ouvertures"]] == [13, 43, 105]


def test_us356_ca7_les_ouvertures_sont_bornees(db):
    for i in range(ech.NB_PROCHAINES_OUVERTURES + 5):
        _referentiel(db, f"culture {i:02d}", fenetre=(11, 12))
    assert len(_parcours(db)["prochaines_ouvertures"]) == ech.NB_PROCHAINES_OUVERTURES


def test_us356_ca7_les_prochaines_ouvertures_sont_la_aussi_quand_une_culture_est_a_semer(db):
    """Le champ est lu en permanence : `calendrier_semis` (US-218), lui, reste réservé au « rien à semer »."""
    _referentiel(db, "feve", fenetre=(10, 11))
    _referentiel(db, "poireau", fenetre=(11, 12))
    _planter(db, "feve", "Aguadulce", 4)
    p = _parcours(db)
    assert p["a_semer"] and p["calendrier_semis"] is None
    assert [o["culture"] for o in p["prochaines_ouvertures"]] == ["poireau"]


def test_us356_ca7_lecture_seule_et_isolee(db):
    """Un autre potager ne voit ni le lot ni les ouvertures du premier ; rien n'est écrit."""
    _referentiel(db, "laitue d'hiver", godet=(10, 12), fenetre=(9, 10))
    _semis(db, "laitue d'hiver", date(2026, 10, 15), numero=59)
    avant = db.query(Evenement).count()
    assert _parcours(db)["a_semer_ecartees"]
    assert _parcours(db, ctx=CTX_B)["a_semer_ecartees"] == []
    assert db.query(Evenement).count() == avant


def test_us356_ca7_aucun_champ_existant_retire(db):
    _referentiel(db, "feve", fenetre=(10, 11))
    _planter(db, "feve", "Aguadulce", 4)
    p = _parcours(db)
    for cle in ("stades", "pepinieres", "sans_emplacement", "etiquettes", "compteurs", "a_semer",
                "a_semer_sans_graines", "source_stock_graines", "dormants", "calendrier_semis"):
        assert cle in p

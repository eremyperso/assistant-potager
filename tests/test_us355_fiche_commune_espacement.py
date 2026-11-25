"""
[US-355 / CA3] La fiche culture rend l'espacement de la culture, tel que la fiche de
culture le porte : l'onglet Référence de la fiche commune le dit sans le recalculer.
Lecture seule : aucune migration, aucune route nouvelle.
"""
from datetime import date

import pytest

from app.services import fiche_culture as svc_fiche
from database.models import CultureConfig, Potager, User

DATE_REF = date(2026, 11, 25)


@pytest.fixture
def db(test_db):
    test_db.add(User(id=1, email="a@potager.test"))
    test_db.flush()
    test_db.add(Potager(id=1, nom="Jardin A", proprietaire_id=1, zone_climatique="oceanique"))
    test_db.commit()
    return test_db


def _culture(db, nom, espacement=None):
    db.add(CultureConfig(nom=nom, type_organe_recolte="végétatif", potager_id=None, espacement=espacement))
    db.commit()


def test_la_fiche_rend_l_espacement_de_la_culture(db):
    _culture(db, "chou de bruxelles", espacement="60 cm entre plants, 60 cm entre rangs")
    fiche = svc_fiche.composer_fiche_pwa(db, "chou de bruxelles", 1, DATE_REF)
    assert fiche.espacement == "60 cm entre plants, 60 cm entre rangs"
    assert svc_fiche.fiche_pwa_en_dict(fiche)["espacement"] == "60 cm entre plants, 60 cm entre rangs"


def test_un_espacement_vide_ou_absent_reste_non_renseigne(db):
    _culture(db, "poireau", espacement="   ")
    _culture(db, "ail", espacement=None)
    assert svc_fiche.composer_fiche_pwa(db, "poireau", 1, DATE_REF).espacement is None
    assert svc_fiche.fiche_pwa_en_dict(svc_fiche.composer_fiche_pwa(db, "ail", 1, DATE_REF))["espacement"] is None


def test_une_culture_hors_referentiel_n_a_pas_d_espacement(db):
    fiche = svc_fiche.composer_fiche_pwa(db, "kiwano", 1, DATE_REF)
    assert fiche.fiche_absente is True
    assert fiche.espacement is None

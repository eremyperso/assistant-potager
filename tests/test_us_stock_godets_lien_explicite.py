"""
Décision PO du 07/10/2026, précisée (cas du poireau, version 3.145) : une plantation sans
variété ne sort des godets que si elle CITE ses godets (`source_evenement_ids`). Sans lien,
elle reste un évènement à part. Et un lot qui a des godets plantés ET des graines encore en
germination montre deux lignes distinctes dans Stocks, pas des « godets à replanter » fantômes.
"""
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, Evenement, Parcelle
from utils.stock import calcul_godets, calcul_godets_par_culture, calcul_stock_varietes


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    serre = Parcelle(nom="serre", nom_normalise="serre", actif=True, est_pepiniere=True)
    planche = Parcelle(nom="planche", nom_normalise="planche", actif=True)
    session.add_all([serre, planche])
    session.flush()
    yield session, serre.id, planche.id
    session.close()


def _semis(s, serre, culture, qte, variete=None):
    ev = Evenement(type_action="semis", culture=culture, variete=variete, quantite=qte,
                   unite="graines", date=datetime(2026, 8, 15), parcelle_id=serre)
    s.add(ev)
    s.flush()
    return ev.id


def _godet(s, serre, culture, nb, semis_id=None, variete=None, jour=14):
    ev = Evenement(type_action="mise_en_godet", culture=culture, variete=variete,
                   nb_plants_godets=nb, nb_graines_semees=nb, date=datetime(2026, 10, jour),
                   parcelle_id=serre, origine_graines_id=semis_id)
    s.add(ev)
    s.flush()
    return ev.id


def _plantation(s, planche, culture, qte, sources=None, variete=None, jour=16):
    ev = Evenement(type_action="plantation", culture=culture, variete=variete, quantite=qte,
                   unite="plants", date=datetime(2026, 10, jour), parcelle_id=planche,
                   source_evenement_ids=sources)
    s.add(ev)
    s.flush()
    return ev.id


def test_plantation_sans_variete_liee_au_godet_est_deduite(db):
    """Le poireau : 50 + 30 godets, deux plantations qui citent leurs godets → 0 restant."""
    s, serre, planche = db
    sem = _semis(s, serre, "poireau", 100)
    g1 = _godet(s, serre, "poireau", 50, sem, jour=14)
    g2 = _godet(s, serre, "poireau", 30, sem, jour=17)
    _plantation(s, planche, "poireau", 50, sources=str(g1), jour=16)
    _plantation(s, planche, "poireau", 30, sources=str(g2), jour=17)

    godets = calcul_godets(s, include_epuises=True)
    assert godets["poireau"]["nb_plantes"] == 80
    assert godets["poireau"]["stock_residuel_godet"] == 0
    assert calcul_godets_par_culture(s, "poireau") == []


def test_plantation_sans_variete_sans_lien_reste_un_evenement_a_part(db):
    """La règle du 07/10 tient : sans lien explicite, rien n'est deviné."""
    s, serre, planche = db
    _godet(s, serre, "cornichon", 6)
    _plantation(s, planche, "cornichon", 4)
    g = calcul_godets_par_culture(s, "cornichon")[0]
    assert g["nb_plantes"] == 0
    assert g["stock_residuel_godet"] == 6


def test_lien_explicite_plafonne_au_contenu_du_godet(db):
    """Une plantation qui cite un godet de 10 pour 12 plants n'en retire que 10 ; le reliquat
    ne se rabat pas sur un godet sans variété (aucune supposition)."""
    s, serre, planche = db
    g1 = _godet(s, serre, "poireau", 10)
    _plantation(s, planche, "poireau", 12, sources=str(g1))
    assert calcul_godets(s, include_epuises=True)["poireau"]["nb_plantes"] == 10


def test_lien_explicite_vers_un_godet_de_variete_retire_a_cette_variete(db):
    """Plantation sans variété citant un godet « jaune » : la déduction va à « jaune »."""
    s, serre, planche = db
    g1 = _godet(s, serre, "courgette", 8, variete="jaune")
    _plantation(s, planche, "courgette", 3, sources=str(g1))
    g = calcul_godets_par_culture(s, "courgette")[0]
    assert g["variete"] == "jaune" and g["nb_plantes"] == 3 and g["stock_residuel_godet"] == 5


def test_stocks_poireau_godets_plantes_et_graines_en_germination(db):
    """100 graines, 80 repiqués et plantés : plus de ligne « godets », 20 graines en pépinière."""
    s, serre, planche = db
    sem = _semis(s, serre, "poireau", 100)
    g1 = _godet(s, serre, "poireau", 50, sem, jour=14)
    g2 = _godet(s, serre, "poireau", 30, sem, jour=17)
    _plantation(s, planche, "poireau", 50, sources=str(g1), jour=16)
    _plantation(s, planche, "poireau", 30, sources=str(g2), jour=17)

    pep = [v for v in calcul_stock_varietes(s) if v["culture"] == "poireau" and v["etat"] == "pep"]
    assert len(pep) == 1
    assert pep[0]["unite"] == "graines" and pep[0]["stock_actuel"] == 20


def test_stocks_lot_avec_godets_restants_et_graines_deux_lignes(db):
    """Godets restants ET graines non levées : une ligne par unité."""
    s, serre, planche = db
    sem = _semis(s, serre, "chou", 100)
    g1 = _godet(s, serre, "chou", 60, sem)
    _plantation(s, planche, "chou", 10, sources=str(g1))

    pep = sorted(
        (v for v in calcul_stock_varietes(s) if v["culture"] == "chou" and v["etat"] == "pep"),
        key=lambda v: v["unite"],
    )
    assert [(v["unite"], v["stock_actuel"]) for v in pep] == [("graines", 40), ("plants", 50)]

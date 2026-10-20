"""
[US-242] Chaque mise en terre (avec sa parcelle), vente et perte en godet imputée à un lot
garde sa date : `sorties_datees` de `GET /pepiniere/lots`, lue par le journal du lot.
"""
from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.main import _lot_pepiniere_json
from database.db import Base
from database.models import Evenement, Parcelle
from utils.stock import calcul_lots_pepiniere

POTAGER_ID = 1


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add_all([
        Parcelle(id=1, nom="SERRE", nom_normalise="serre", potager_id=POTAGER_ID, est_pepiniere=True),
        Parcelle(id=2, nom="planche_centrale", nom_normalise="planchecentrale", potager_id=POTAGER_ID),
    ])
    session.commit()
    yield session
    session.close()


def _ev(db, type_action, jour, quantite, **kw):
    e = Evenement(type_action=type_action, culture="tomate", variete="coeur de boeuf",
                  quantite=float(quantite), date=datetime(2026, *jour), potager_id=POTAGER_ID, **kw)
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def _lot_de_la_maquette(db):
    semis = _ev(db, "semis", (3, 15), 10, unite="graines", parcelle_id=1)
    godet = _ev(db, "mise_en_godet", (6, 1), 10, nb_plants_godets=10, unite="plants", origine_graines_id=semis.id)
    return semis, godet


def test_us242_la_plantation_garde_sa_date_et_sa_parcelle(db) -> None:
    """Le cas du lot n° 1 : « lundi 15 juin, 10 plants sur planche_centrale »."""
    semis, godet = _lot_de_la_maquette(db)
    plantation = _ev(db, "plantation", (6, 15), 10, unite="plants", parcelle_id=2,
                     source_evenement_ids=str(godet.id))
    (lot,) = calcul_lots_pepiniere(db, potager_id=POTAGER_ID)
    assert lot["nb_plantes"] == 10
    assert len(lot["sorties_datees"]) == 1
    s = lot["sorties_datees"][0]
    assert (s["nature"], s["quantite"], s["parcelle"], s["id"]) == ("plantation", 10, "planche_centrale", plantation.id)
    assert str(s["date"])[:10] == "2026-06-15"


def test_us242_plantation_repartie_sur_deux_lots(db) -> None:
    """Une plantation qui dépasse un lot se répartit : chaque lot garde SA part, à la même date."""
    s1 = _ev(db, "semis", (3, 1), 5, unite="graines", parcelle_id=1)
    s2 = _ev(db, "semis", (3, 10), 5, unite="graines", parcelle_id=1)
    g1 = _ev(db, "mise_en_godet", (4, 1), 5, nb_plants_godets=5, unite="plants", origine_graines_id=s1.id)
    g2 = _ev(db, "mise_en_godet", (4, 2), 5, nb_plants_godets=5, unite="plants", origine_graines_id=s2.id)
    _ev(db, "plantation", (6, 15), 8, unite="plants", parcelle_id=2, source_evenement_ids=f"{g1.id};{g2.id}")
    lots = {l["semis_id"]: l for l in calcul_lots_pepiniere(db, potager_id=POTAGER_ID)}
    assert [x["quantite"] for x in lots[s1.id]["sorties_datees"]] == [5]
    assert [x["quantite"] for x in lots[s2.id]["sorties_datees"]] == [3]


def test_us242_ventes_et_pertes_sont_datees(db) -> None:
    semis, godet = _lot_de_la_maquette(db)
    _ev(db, "vendu", (6, 20), 2, unite="plants", origine_graines_id=semis.id)
    _ev(db, "perte_godet", (6, 22), 1, unite="plants", origine_graines_id=semis.id)
    (lot,) = calcul_lots_pepiniere(db, potager_id=POTAGER_ID)
    assert [(x["nature"], x["quantite"], str(x["date"])[:10]) for x in lot["sorties_datees"]] == [
        ("vente", 2, "2026-06-20"), ("perte", 1, "2026-06-22"),
    ]
    assert all(x["parcelle"] is None for x in lot["sorties_datees"])


def test_us242_lot_sans_sortie_a_une_liste_vide(db) -> None:
    _ev(db, "semis", (3, 15), 10, unite="graines", parcelle_id=1)
    (lot,) = calcul_lots_pepiniere(db, potager_id=POTAGER_ID)
    assert lot["sorties_datees"] == []


def test_us242_l_api_rend_les_dates_en_iso_court(db) -> None:
    semis, godet = _lot_de_la_maquette(db)
    _ev(db, "plantation", (6, 15), 4, unite="plants", parcelle_id=2, source_evenement_ids=str(godet.id))
    (lot,) = calcul_lots_pepiniere(db, potager_id=POTAGER_ID)
    rendu = _lot_pepiniere_json(lot, {})
    assert rendu["sorties_datees"][0]["date"] == "2026-06-15"
    assert rendu["sorties_datees"][0]["parcelle"] == "planche_centrale"


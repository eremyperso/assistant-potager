"""
tests/test_inc013_perte_godet_par_lot.py
[INC-013] Une perte ou une vente de godet n'apparaît que dans le cycle de vie du lot
qu'elle impute (`origine_graines_id`), jamais dans celui des autres lots de la même
culture/variété.
"""
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.services import evenements as svc_evenements
from app.services.context import TenantContext
from database.db import Base
from database.models import Evenement

POTAGER_ID = 1


@pytest.fixture
def db():
    """Session SQLite en mémoire, tables recréées à chaque test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def ctx():
    return TenantContext(user_id=1, potager_id=POTAGER_ID, role="owner")


def _evt(db, action, jour, origine=None, quantite=None, unite=None):
    e = Evenement(
        type_action=action, culture="chou", variete="frisé", quantite=quantite,
        unite=unite, origine_graines_id=origine, date=datetime(2026, 9, jour),
        potager_id=POTAGER_ID,
    )
    db.add(e)
    db.commit()
    return e


@pytest.fixture
def deux_lots(db):
    lot_5 = _evt(db, "semis", 1, quantite=100, unite="graines")
    lot_7 = _evt(db, "semis", 2, quantite=100, unite="graines")
    perte_7 = _evt(db, "perte_godet", 15, origine=lot_7.id, quantite=10, unite="plants")
    perte_5 = _evt(db, "perte_godet", 16, origine=lot_5.id, quantite=3, unite="plants")
    vente_7 = _evt(db, "vendu", 17, origine=lot_7.id, quantite=5, unite="plants")
    return lot_5, lot_7, perte_5, perte_7, vente_7


def test_inc013_perte_absente_du_cycle_des_autres_lots(db, ctx, deux_lots) -> None:
    """La perte du lot 7 n'apparaît pas dans le cycle de vie du lot 5."""
    lot_5, lot_7, perte_5, perte_7, _ = deux_lots

    cycle_5 = svc_evenements.cycle_vie_culture(db, ctx, "chou", "frisé", semis_id=lot_5.id)
    cycle_7 = svc_evenements.cycle_vie_culture(db, ctx, "chou", "frisé", semis_id=lot_7.id)

    assert [p.id for p in cycle_5["pertes_godet"]] == [perte_5.id]
    assert [p.id for p in cycle_7["pertes_godet"]] == [perte_7.id]


def test_inc013_vente_rattachee_au_seul_lot_cite(db, ctx, deux_lots) -> None:
    lot_5, lot_7, _, _, vente_7 = deux_lots

    assert svc_evenements.cycle_vie_culture(db, ctx, "chou", "frisé", semis_id=lot_5.id)["ventes"] == []
    ventes_7 = svc_evenements.cycle_vie_culture(db, ctx, "chou", "frisé", semis_id=lot_7.id)["ventes"]
    assert [v.id for v in ventes_7] == [vente_7.id]


def test_inc013_lecture_agregee_inchangee(db, ctx, deux_lots) -> None:
    """Sans lot demandé, culture + variété agrégés : toutes les pertes remontent."""
    _, _, perte_5, perte_7, _ = deux_lots

    cycle = svc_evenements.cycle_vie_culture(db, ctx, "chou", "frisé")

    assert {p.id for p in cycle["pertes_godet"]} == {perte_5.id, perte_7.id}


def test_inc013_lot_sans_semis_ne_prend_que_les_pertes_orphelines(db, ctx, deux_lots) -> None:
    orpheline = _evt(db, "perte_godet", 20, origine=None, quantite=2, unite="plants")

    cycle = svc_evenements.cycle_vie_culture(db, ctx, "chou", "frisé", sans_semis_rattache=True)

    assert [p.id for p in cycle["pertes_godet"]] == [orpheline.id]

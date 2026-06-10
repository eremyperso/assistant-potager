"""
tests/test_us030_date_reference.py
-----------------------------------
[US-030] Paramètre date de référence sur les endpoints et commandes Telegram.

Couvre :
  CA1-CA9  : filtrage temporel dans calcul_stock_cultures, calcul_godets,
              calcul_occupation_parcelles
  CA10-CA14: parsing date Telegram (_parse_date_arg, _looks_like_date)
  CA15     : stock à date antérieure, future, jour exact
  CA16     : régression sans paramètre date_ref
"""
from __future__ import annotations

import pytest
from datetime import date, timedelta, datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.db import Base
from database.models import Evenement, CultureConfig, Parcelle
from utils.stock import (
    calcul_stock_cultures,
    calcul_godets,
    calcul_godets_par_culture,
    calcul_semis,
    _cutoff_dt,
)
from utils.parcelles import calcul_occupation_parcelles


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


def _ev(db, type_action, culture, quantite=1, unite="plants", date_=None, variete=None,
        nb_plants_godets=None, parcelle_id=None, rang=None):
    """Helper : crée et flush un événement."""
    if date_ is None:
        date_ = datetime.now()
    elif isinstance(date_, date) and not isinstance(date_, datetime):
        date_ = datetime(date_.year, date_.month, date_.day)
    e = Evenement(
        type_action=type_action,
        culture=culture,
        variete=variete,
        quantite=quantite,
        unite=unite,
        date=date_,
        nb_plants_godets=nb_plants_godets,
        parcelle_id=parcelle_id,
        rang=rang or 1,
    )
    db.add(e)
    db.flush()
    return e


# ── Helpers _cutoff_dt ────────────────────────────────────────────────────────

def test_us030_cutoff_dt_none():
    """[US-030] _cutoff_dt(None) retourne None — pas de filtre."""
    assert _cutoff_dt(None) is None


def test_us030_cutoff_dt_date():
    """[US-030] _cutoff_dt retourne 23:59:59 du jour donné."""
    d = date(2025, 5, 1)
    result = _cutoff_dt(d)
    assert result == datetime(2025, 5, 1, 23, 59, 59)


# ── calcul_stock_cultures avec date_ref ───────────────────────────────────────

def test_us030_ca15_stock_date_anterieure(db_session):
    """[US-030 / CA15] Stock à date antérieure exclut les plantations futures."""
    past   = date.today() - timedelta(days=10)
    future = date.today() + timedelta(days=10)

    _ev(db_session, "plantation", "tomate", quantite=10, date_=past)
    _ev(db_session, "plantation", "tomate", quantite=5,  date_=future)
    db_session.commit()

    stocks_past = calcul_stock_cultures(db_session, past)
    stocks_all  = calcul_stock_cultures(db_session)

    assert stocks_past["tomate"].plants_plantes == 10.0
    assert stocks_all["tomate"].plants_plantes  == 15.0


def test_us030_ca15_stock_date_exacte_inclusion(db_session):
    """[US-030 / CA15] Un événement dont la date == date_ref est inclus (borne inclusive)."""
    ref = date(2025, 5, 1)
    _ev(db_session, "plantation", "courgette", quantite=4, date_=ref)
    db_session.commit()

    stocks = calcul_stock_cultures(db_session, ref)
    assert "courgette" in stocks
    assert stocks["courgette"].plants_plantes == 4.0


def test_us030_ca15_stock_date_future_retourne_tout(db_session):
    """[US-030 / CA5/CA15] date_ref future → comportement identique à aujourd'hui."""
    today  = date.today()
    future = today + timedelta(days=365)

    _ev(db_session, "plantation", "salade", quantite=6, date_=today)
    db_session.commit()

    stocks_future = calcul_stock_cultures(db_session, future)
    stocks_none   = calcul_stock_cultures(db_session)

    # Les deux doivent inclure les événements d'aujourd'hui
    assert "salade" in stocks_future
    assert "salade" in stocks_none


def test_us030_ca16_regression_sans_date_ref(db_session):
    """[US-030 / CA16] Sans date_ref → comportement identique à l'existant (régression)."""
    _ev(db_session, "plantation", "radis", quantite=20)
    _ev(db_session, "perte",      "radis", quantite=5)
    db_session.commit()

    stocks = calcul_stock_cultures(db_session)
    assert "radis" in stocks
    assert stocks["radis"].stock_plants == 15.0


def test_us030_pertes_filtrees_par_date(db_session):
    """[US-030] Les pertes postérieures à date_ref ne sont pas déduites."""
    ref  = date.today() - timedelta(days=5)
    past = date.today() - timedelta(days=10)

    _ev(db_session, "plantation", "laitue", quantite=10, date_=past)
    _ev(db_session, "perte",      "laitue", quantite=3,  date_=date.today())  # après ref
    db_session.commit()

    stocks_ref = calcul_stock_cultures(db_session, ref)
    stocks_now = calcul_stock_cultures(db_session)

    assert stocks_ref["laitue"].stock_plants == 10.0   # perte pas encore survenue
    assert stocks_now["laitue"].stock_plants == 7.0    # perte déduite


# ── calcul_godets avec date_ref ───────────────────────────────────────────────

def test_us030_godets_date_anterieure(db_session):
    """[US-030 / CA3/CA8] calcul_godets exclut les mises en godet futures."""
    past   = date.today() - timedelta(days=10)
    future = date.today() + timedelta(days=5)

    _ev(db_session, "mise_en_godet", "tomate", nb_plants_godets=8,  date_=past)
    _ev(db_session, "mise_en_godet", "tomate", nb_plants_godets=4,  date_=future)
    db_session.commit()

    godets_past = calcul_godets(db_session, date_ref=past)
    godets_all  = calcul_godets(db_session)

    key = "tomate"
    assert godets_past[key]["nb_plants_godets"] == 8
    assert godets_all[key]["nb_plants_godets"]  == 12


def test_us030_godets_plantation_posterieure_ignoree(db_session):
    """[US-030] Une plantation postérieure à date_ref ne déduit pas le stock godet."""
    ref   = date.today() - timedelta(days=5)
    past  = date.today() - timedelta(days=10)
    today = date.today()

    _ev(db_session, "mise_en_godet", "poivron", nb_plants_godets=6, date_=past)
    _ev(db_session, "plantation",    "poivron", quantite=6,          date_=today)
    db_session.commit()

    godets_ref = calcul_godets(db_session, include_epuises=True, date_ref=ref)
    godets_now = calcul_godets(db_session, include_epuises=True)

    # Au ref : plantation pas encore comptée → stock = 6
    assert godets_ref["poivron"]["stock_residuel_godet"] == 6
    # Maintenant : tout planté → stock = 0
    assert godets_now["poivron"]["stock_residuel_godet"] == 0


# ── calcul_semis avec date_ref ────────────────────────────────────────────────

def test_us030_semis_filtre_par_date(db_session):
    """[US-030 / CA7] calcul_semis filtre les semis postérieurs à date_ref."""
    ref    = date.today() - timedelta(days=5)
    past   = date.today() - timedelta(days=20)
    future = date.today()

    _ev(db_session, "semis", "basilic", quantite=30, date_=past)
    _ev(db_session, "semis", "basilic", quantite=20, date_=future)
    db_session.commit()

    semis_ref = calcul_semis(db_session, ref)
    semis_all = calcul_semis(db_session)

    assert semis_ref["basilic"]["total_seme"] == 30
    assert semis_all["basilic"]["total_seme"] == 50


# ── calcul_occupation_parcelles avec date_ref ─────────────────────────────────

def test_us030_occupation_exclut_plantations_futures(db_session):
    """[US-030 / CA1] calcul_occupation_parcelles exclut les plantations futures."""
    past   = date.today() - timedelta(days=30)
    future = date.today() + timedelta(days=10)
    ref    = date.today() - timedelta(days=5)

    _ev(db_session, "plantation", "carotte", quantite=15, date_=past)
    _ev(db_session, "plantation", "carotte", quantite=10, date_=future)
    db_session.commit()

    occ_ref = calcul_occupation_parcelles(db_session, ref)
    occ_all = calcul_occupation_parcelles(db_session)

    # Récupère toutes les cultures "carotte" toutes parcelles confondues
    all_entries_ref = [e for entries in occ_ref.values() for e in entries if e["culture"] == "carotte"]
    all_entries_all = [e for entries in occ_all.values() for e in entries if e["culture"] == "carotte"]

    total_ref = sum(e["nb_plants"] for e in all_entries_ref)
    total_all = sum(e["nb_plants"] for e in all_entries_all)

    assert total_ref == pytest.approx(15.0, abs=1)
    assert total_all == pytest.approx(25.0, abs=1)


# ── Parsing date Telegram ─────────────────────────────────────────────────────

def test_us030_ca10_parse_date_iso():
    """[US-030 / CA10] _parse_date_arg reconnaît le format YYYY-MM-DD."""
    from bot import _parse_date_arg
    assert _parse_date_arg("2025-05-01") == date(2025, 5, 1)


def test_us030_ca10_parse_date_fr():
    """[US-030 / CA10] _parse_date_arg reconnaît le format JJ/MM/AAAA."""
    from bot import _parse_date_arg
    assert _parse_date_arg("01/05/2025") == date(2025, 5, 1)


def test_us030_ca10_parse_date_invalide():
    """[US-030 / CA10/CA14] _parse_date_arg retourne None pour une date invalide."""
    from bot import _parse_date_arg
    assert _parse_date_arg("32/13/2025") is None
    assert _parse_date_arg("not-a-date") is None
    assert _parse_date_arg("tomate") is None


def test_us030_ca10_parse_date_future_capee():
    """[US-030 / CA5] Date future → capée à aujourd'hui."""
    from bot import _parse_date_arg
    future = (date.today() + timedelta(days=365)).isoformat()
    result = _parse_date_arg(future)
    assert result == date.today()


def test_us030_ca14_looks_like_date():
    """[US-030 / CA14] _looks_like_date détecte les fausses dates."""
    from bot import _looks_like_date
    assert _looks_like_date("32/13/2025") is True   # ressemble à date FR mais invalide
    assert _looks_like_date("2025-13-01") is True   # ressemble à date ISO mais invalide
    assert _looks_like_date("tomate")     is False
    assert _looks_like_date("nord")       is False


def test_us030_ca16_parse_date_none_si_absent():
    """[US-030 / CA16] Pas d'arg date → date_ref reste None (comportement par défaut)."""
    from bot import _parse_date_arg
    assert _parse_date_arg("") is None

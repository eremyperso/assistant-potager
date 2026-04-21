"""
[US-014] Tests — Correction affichage semis dans /stats et /stats [culture]

CA1 : /stats global — semis n'affiche plus les récoltes des plantations
CA2 : /stats global — semis sans quantité ne crashe pas
CA3 : /stats [culture] — semis rattachés au bloc de leur variété
CA4 : /stats [culture] — semis sans variété correspondante listés séparément
CA5 : /stats [culture] — culture avec uniquement des semis (pas de plantation)
CA6 : non-régression — récoltes restent dans section Plantations
CA7 : non-régression — culture sans semis inchangée
"""
import pytest
from datetime import datetime, date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, Evenement, Parcelle, CultureConfig
from utils.stock import calcul_semis, calcul_semis_par_culture, calcul_stock_cultures, calcul_stock_par_variete


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    # Parcelle minimale
    p = Parcelle(nom="nord", nom_normalise="nord", actif=True)
    session.add(p)
    session.flush()
    yield session, p.id
    session.close()


def _ev(db_session, parcelle_id, type_action, culture, variete=None,
        quantite=None, unite=None, date_ev=None):
    ev = Evenement(
        type_action=type_action,
        culture=culture,
        variete=variete,
        quantite=quantite,
        unite=unite,
        date=date_ev or datetime(2026, 4, 1),
        parcelle_id=parcelle_id,
    )
    db_session.add(ev)
    db_session.flush()
    return ev


# ─────────────────────────────────────────────────────────────────────────────
# CA1 — /stats global : pas de récoltes dans la section Semis
# ─────────────────────────────────────────────────────────────────────────────

def test_us014_ca1_semis_sans_recoltes(db):
    """calcul_semis() ne retourne plus de données de récolte."""
    session, pid = db
    _ev(session, pid, "plantation", "courgette", quantite=15, unite="plants")
    _ev(session, pid, "recolte",    "courgette", quantite=10, unite="kg")
    _ev(session, pid, "semis",      "courgette", quantite=20, unite="graines")

    result = calcul_semis(session)

    assert "courgette" in result
    s = result["courgette"]
    assert s["nb_semis"] == 1
    assert s["total_seme"] == 20.0
    # Plus de clés récolte
    assert "nb_recoltes"   not in s
    assert "total_recolte" not in s
    assert "unite_recolte" not in s


def test_us014_ca1_semis_ne_doublonne_pas_recoltes(db):
    """Vérification que les récoltes n'apparaissent que dans calcul_stock_cultures."""
    session, pid = db
    _ev(session, pid, "plantation", "tomate", quantite=10, unite="plants")
    _ev(session, pid, "recolte",    "tomate", quantite=5,  unite="kg")
    _ev(session, pid, "semis",      "tomate", quantite=30, unite="graines")

    semis  = calcul_semis(session)
    stocks = calcul_stock_cultures(session)

    # Récoltes dans stocks (plantations), pas dans semis
    assert stocks["tomate"].nb_recoltes == 1
    assert stocks["tomate"].recoltes_total > 0
    assert "nb_recoltes" not in semis["tomate"]


# ─────────────────────────────────────────────────────────────────────────────
# CA2 — /stats global : semis sans quantité ne crashe pas
# ─────────────────────────────────────────────────────────────────────────────

def test_us014_ca2_semis_sans_quantite(db):
    """Un semis avec quantite=None ne crashe pas."""
    session, pid = db
    _ev(session, pid, "semis", "persil", quantite=None, unite=None)

    result = calcul_semis(session)

    assert "persil" in result
    assert result["persil"]["nb_semis"] == 1
    assert result["persil"]["total_seme"] is None or result["persil"]["total_seme"] == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# CA3 — /stats [culture] : semis rattachés au bloc de leur variété
# ─────────────────────────────────────────────────────────────────────────────

def test_us014_ca3_semis_par_culture_variete_connue(db):
    """calcul_semis_par_culture retourne le semis variété jaune pour courgette."""
    session, pid = db
    _ev(session, pid, "plantation", "courgette", variete="jaune",
        quantite=10, unite="plants", date_ev=datetime(2026, 4, 11))
    _ev(session, pid, "semis",      "courgette", variete="jaune",
        quantite=20, unite="graines", date_ev=datetime(2026, 4, 20))

    result = calcul_semis_par_culture(session, "courgette")

    assert len(result) == 1
    s = result[0]
    assert s["variete"] == "jaune"
    assert s["nb_semis"] == 1
    assert s["total_seme"] == 20.0
    assert s["unite"] == "graines"
    assert s["date_premier_semis"] == datetime(2026, 4, 20)


def test_us014_ca3_plusieurs_semis_meme_variete(db):
    """Deux semis de la même variété sont agrégés."""
    session, pid = db
    _ev(session, pid, "semis", "courgette", variete="jaune",
        quantite=10, unite="graines", date_ev=datetime(2026, 3, 1))
    _ev(session, pid, "semis", "courgette", variete="jaune",
        quantite=15, unite="graines", date_ev=datetime(2026, 4, 1))

    result = calcul_semis_par_culture(session, "courgette")

    assert len(result) == 1
    assert result[0]["nb_semis"] == 2
    assert result[0]["total_seme"] == 25.0
    # Date la plus ancienne
    assert result[0]["date_premier_semis"] == datetime(2026, 3, 1)


def test_us014_ca3_semis_insensible_casse_culture(db):
    """La recherche par culture est insensible à la casse."""
    session, pid = db
    _ev(session, pid, "semis", "Courgette", variete=None, quantite=20, unite="graines")

    result = calcul_semis_par_culture(session, "courgette")
    assert len(result) == 1


# ─────────────────────────────────────────────────────────────────────────────
# CA4 — semis sans variété plantée correspondante
# ─────────────────────────────────────────────────────────────────────────────

def test_us014_ca4_semis_variete_sans_plantation(db):
    """Un semis d'une variété non plantée est bien retourné."""
    session, pid = db
    # Plantation variété None
    _ev(session, pid, "plantation", "courgette", variete=None, quantite=10, unite="plants")
    # Semis variété "verte" sans plantation correspondante
    _ev(session, pid, "semis", "courgette", variete="verte", quantite=5, unite="graines")

    result = calcul_semis_par_culture(session, "courgette")
    varietes = [r["variete"] for r in result]

    assert "verte" in varietes


def test_us014_ca4_semis_sans_variete(db):
    """Un semis sans variété (None) est retourné."""
    session, pid = db
    _ev(session, pid, "semis", "carotte", variete=None, quantite=100, unite="graines")

    result = calcul_semis_par_culture(session, "carotte")
    assert len(result) == 1
    assert result[0]["variete"] is None


# ─────────────────────────────────────────────────────────────────────────────
# CA5 — culture avec uniquement des semis (pas de plantation)
# ─────────────────────────────────────────────────────────────────────────────

def test_us014_ca5_culture_semis_seuls(db):
    """calcul_semis_par_culture retourne des données même sans plantation."""
    session, pid = db
    _ev(session, pid, "semis", "basilic", variete=None, quantite=50, unite="graines")

    result = calcul_semis_par_culture(session, "basilic")
    assert len(result) == 1
    assert result[0]["total_seme"] == 50.0


def test_us014_ca5_calcul_stock_par_variete_culture_semis_seuls(db):
    """calcul_stock_par_variete retourne [] pour culture sans plantation (comportement existant)."""
    session, pid = db
    _ev(session, pid, "semis", "basilic", variete=None, quantite=50, unite="graines")

    result = calcul_stock_par_variete(session, "basilic")
    # La fonction existante retourne [] sans plantation — c'est attendu
    # Le routing cmd_stats gère ce cas avec calcul_semis_par_culture
    assert result == []


# ─────────────────────────────────────────────────────────────────────────────
# CA6 — non-régression : récoltes dans la section Plantations
# ─────────────────────────────────────────────────────────────────────────────

def test_us014_ca6_recoltes_dans_stocks_plantations(db):
    """Les récoltes restent correctement dans calcul_stock_cultures."""
    session, pid = db
    _ev(session, pid, "plantation", "tomate", quantite=10, unite="plants")
    _ev(session, pid, "recolte",    "tomate", quantite=3,  unite="kg")
    _ev(session, pid, "recolte",    "tomate", quantite=2,  unite="kg")

    stocks = calcul_stock_cultures(session)
    assert "tomate" in stocks
    assert stocks["tomate"].nb_recoltes == 2
    assert stocks["tomate"].recoltes_total == pytest.approx(5.0)


def test_us014_ca6_semis_sans_impact_sur_stock_plantations(db):
    """Ajouter un semis ne change pas le stock des plantations."""
    session, pid = db
    _ev(session, pid, "plantation", "courgette", quantite=10, unite="plants")
    stocks_avant = calcul_stock_cultures(session)

    _ev(session, pid, "semis", "courgette", quantite=20, unite="graines")
    stocks_apres = calcul_stock_cultures(session)

    assert stocks_avant["courgette"].stock_plants == stocks_apres["courgette"].stock_plants


# ─────────────────────────────────────────────────────────────────────────────
# CA7 — non-régression : culture sans semis inchangée
# ─────────────────────────────────────────────────────────────────────────────

def test_us014_ca7_culture_sans_semis_absente_de_calcul_semis(db):
    """Une culture sans semis n'apparaît pas dans calcul_semis."""
    session, pid = db
    _ev(session, pid, "plantation", "salade", quantite=30, unite="plants")
    _ev(session, pid, "recolte",    "salade", quantite=7,  unite="plants")

    result = calcul_semis(session)
    assert "salade" not in result


def test_us014_ca7_calcul_stock_par_variete_sans_semis_inchange(db):
    """calcul_stock_par_variete sans semis retourne les mêmes données qu'avant."""
    session, pid = db
    _ev(session, pid, "plantation", "salade", quantite=30, unite="plants")
    _ev(session, pid, "perte",      "salade", quantite=2,  unite="plants")

    varietes = calcul_stock_par_variete(session, "salade")
    semis    = calcul_semis_par_culture(session, "salade")

    assert len(varietes) == 1
    assert varietes[0]["plants_plantes"] == 30
    assert varietes[0]["plants_perdus"]  == 2
    assert semis == []


def test_us014_ca7_plusieurs_cultures_isolation(db):
    """Les semis d'une culture n'affectent pas les stats d'une autre."""
    session, pid = db
    _ev(session, pid, "plantation", "tomate",   quantite=10, unite="plants")
    _ev(session, pid, "plantation", "courgette",quantite=5,  unite="plants")
    _ev(session, pid, "semis",      "courgette",quantite=20, unite="graines")

    semis = calcul_semis(session)
    assert "courgette" in semis
    assert "tomate" not in semis

    stocks = calcul_stock_cultures(session)
    assert stocks["tomate"].stock_plants == 10
    assert stocks["courgette"].stock_plants == 5

"""
tests/test_us029_chainagecomplet.py
[US-029] Chaînage complet du cycle de vie semis → godet → plantation

Couverture :
  CA1  — colonne source_evenement_ids présente sur le modèle
  CA5  — _find_plantation_sources : variété unique héritée du godet
  CA7  — _find_plantation_sources : multi-lots → IDs séparés par ";"
  CA8  — _find_plantation_sources : allocation FIFO (lot le plus ancien d'abord)
  CA9  — calcul_godets_par_culture : déduction correcte via variété héritée
  CA10 — calcul_godets_par_culture : CA6 et CA6-reverse ne s'annulent plus
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.db import Base
from database.models import Evenement
from utils.stock import _find_plantation_sources, calcul_godets_par_culture


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    """Session SQLite en mémoire, tables recréées à chaque test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


def _godet(db, culture, variete, nb_plants, date_offset=0):
    """Crée un événement mise_en_godet et le retourne."""
    e = Evenement(
        type_action      = "mise_en_godet",
        culture          = culture,
        variete          = variete,
        nb_plants_godets = nb_plants,
        quantite         = float(nb_plants),
        unite            = "plants",
        date             = datetime(2026, 4, 1) + timedelta(days=date_offset),
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def _plantation(db, culture, variete, quantite, source_ids=None):
    """Crée un événement plantation et le retourne."""
    e = Evenement(
        type_action          = "plantation",
        culture              = culture,
        variete              = variete,
        quantite             = float(quantite),
        unite                = "plants",
        source_evenement_ids = source_ids,
        date                 = datetime(2026, 5, 1),
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


# ── CA1 : colonne source_evenement_ids présente ───────────────────────────────

def test_us029_ca1_colonne_source_evenement_ids_presente(db):
    """CA1 — La colonne source_evenement_ids est bien présente sur le modèle Evenement."""
    e = Evenement(type_action="plantation", culture="tomate")
    db.add(e)
    db.commit()
    db.refresh(e)
    assert hasattr(e, "source_evenement_ids")
    assert e.source_evenement_ids is None


# ── CA5 : héritage variété unique ─────────────────────────────────────────────

def test_us029_ca5_variete_heritee_godet_unique(db):
    """CA5 — Une seule variété en godet → variété héritée automatiquement."""
    g = _godet(db, "butternut", "récolte de 2025", 20)

    variete_resolue, source_ids = _find_plantation_sources(db, "butternut", None, 10.0)

    assert variete_resolue == "récolte de 2025"
    assert source_ids == str(g.id)


def test_us029_ca5_variete_deja_precisee_conservee(db):
    """CA5 — Si la variété est déjà précisée, elle est conservée et le godet est identifié."""
    g = _godet(db, "tomate", "cerise", 15)

    variete_resolue, source_ids = _find_plantation_sources(db, "tomate", "cerise", 5.0)

    assert variete_resolue == "cerise"
    assert source_ids == str(g.id)


def test_us029_ca5_sans_godet_retourne_none(db):
    """CA5 — Aucun godet actif → retourne (None, None)."""
    variete_resolue, source_ids = _find_plantation_sources(db, "courge", None, 5.0)
    assert variete_resolue is None
    assert source_ids is None


def test_us029_ca5_plusieurs_varietes_retourne_none(db):
    """CA5 — Plusieurs variétés en godet → ambigu → (None, None) pour déclencher menu."""
    _godet(db, "tomate", "cerise", 10)
    _godet(db, "tomate", "cœur de bœuf", 8)

    variete_resolue, source_ids = _find_plantation_sources(db, "tomate", None, 5.0)

    assert variete_resolue is None
    assert source_ids is None


# ── CA7 : multi-lots → IDs séparés par ";" ────────────────────────────────────

def test_us029_ca7_multi_lots_source_ids_semicolon(db):
    """CA7 — Plantation consomme 2 lots → source_evenement_ids contient les 2 IDs."""
    g1 = _godet(db, "butternut", "récolte de 2025", 3, date_offset=0)   # ancien
    g2 = _godet(db, "butternut", "récolte de 2025", 10, date_offset=10)  # récent

    variete_resolue, source_ids = _find_plantation_sources(db, "butternut", "récolte de 2025", 8.0)

    assert variete_resolue == "récolte de 2025"
    assert source_ids is not None
    ids = source_ids.split(";")
    assert str(g1.id) in ids  # lot le plus ancien consommé en premier
    assert str(g2.id) in ids


# ── CA8 : FIFO (lot le plus ancien d'abord) ──────────────────────────────────

def test_us029_ca8_fifo_lot_ancien_dabord(db):
    """CA8 — FIFO : le plus ancien godet est consommé en premier."""
    g_ancien = _godet(db, "courge", "musqué de Provence", 5, date_offset=0)
    g_recent = _godet(db, "courge", "musqué de Provence", 10, date_offset=30)

    # Plantation de 5 exactement → seul le lot ancien doit être référencé
    variete_resolue, source_ids = _find_plantation_sources(db, "courge", "musqué de Provence", 5.0)

    assert source_ids is not None
    ids = source_ids.split(";")
    assert str(g_ancien.id) in ids
    assert str(g_recent.id) not in ids


def test_us029_ca8_fifo_lot_ancien_epuise_prend_suivant(db):
    """CA8 — Lot ancien épuisé par une plantation précédente → prend le lot suivant."""
    g1 = _godet(db, "courge", "musqué de Provence", 3, date_offset=0)
    g2 = _godet(db, "courge", "musqué de Provence", 10, date_offset=10)

    # Premiere plantation consomme tout g1
    _plantation(db, "courge", "musqué de Provence", 3.0, source_ids=str(g1.id))

    # Deuxième plantation → g1 vide, doit pointer vers g2
    variete_resolue, source_ids = _find_plantation_sources(db, "courge", "musqué de Provence", 5.0)

    assert source_ids is not None
    ids = source_ids.split(";")
    assert str(g1.id) not in ids   # épuisé
    assert str(g2.id) in ids


# ── CA9/CA10 : calcul_godets_par_culture sans conflit CA6/CA6-reverse ─────────

def test_us029_ca10_ca6_et_reverse_ne_s_annulent_plus(db):
    """CA10 — Un godet sans variété ET une plantation sans variété ne doivent plus se bloquer mutuellement."""
    # Godet AVEC variété et godet SANS variété pour la même culture
    g_avec = _godet(db, "courge", "musqué de Provence", 18)
    _godet(db, "courge", None, 5)

    # Plantation sans variété (ancienne, non liée)
    _plantation(db, "courge", None, 10.0)

    godets = calcul_godets_par_culture(db, "courge")

    # Le godet avec variété doit avoir son stock réduit de 10
    musque = next((g for g in godets if g["variete"] == "musqué de Provence"), None)
    assert musque is not None
    assert musque["stock_residuel_godet"] == 8   # 18 - 10 déduits via CA6


def test_us029_ca9_plantation_avec_variete_heritee_deduit_godet(db):
    """CA9 — Plantation avec variété héritée du godet → stock godet correctement déduit."""
    g = _godet(db, "butternut", "récolte de 2025", 20)
    _plantation(db, "butternut", "récolte de 2025", 10.0, source_ids=str(g.id))

    godets = calcul_godets_par_culture(db, "butternut")

    butter = next((g for g in godets if g["variete"] == "récolte de 2025"), None)
    assert butter is not None
    assert butter["stock_residuel_godet"] == 10  # 20 - 10


def test_us029_ca9_stock_zero_exclu_de_la_liste(db):
    """CA9/CA4 — Godet entièrement planté → n'apparaît plus dans la liste (stock=0)."""
    g = _godet(db, "butternut", "récolte de 2025", 10)
    _plantation(db, "butternut", "récolte de 2025", 10.0, source_ids=str(g.id))

    godets = calcul_godets_par_culture(db, "butternut")

    assert len(godets) == 0  # tout planté, exclu


def test_us029_retrocompatibilite_sans_source_ids(db):
    """Rétrocompatibilité — Plantations sans source_evenement_ids : calcul heuristique CA6."""
    _godet(db, "courgette", "jaune", 10)
    _plantation(db, "courgette", None, 4.0)  # ancienne saisie sans lien ni variété

    godets = calcul_godets_par_culture(db, "courgette")

    courgette = next((g for g in godets if g["variete"] == "jaune"), None)
    assert courgette is not None
    assert courgette["stock_residuel_godet"] == 6  # CA6 attribue les 4 plants

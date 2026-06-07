"""
[US-022] Tests — Déduction du stock de godets lors d'une plantation en pleine terre

CA1 : plantation déduites du stock godet pour la variété correspondante
CA2 : calcul_godets_par_culture() retourne stock_residuel_godet correct
CA3 : affichage /stats <culture> — stock résiduel dans section Pépinière
CA4 : variété entièrement plantée → absente de la liste retournée
CA5 : déduction strictement par (culture, variété) — pas de confusion inter-variétés
CA6 : plantation sans variété rattachée à la variété unique si une seule en godet
CA7 : scénario exact — mise_en_godet 10 + plantation 4 → stock résiduel 6
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, Evenement, Parcelle
from utils.stock import calcul_godets_par_culture


# ── Fixture DB ───────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    p = Parcelle(nom="sud", nom_normalise="sud", actif=True)
    session.add(p)
    session.flush()
    yield session, p.id
    session.close()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _godet(session, pid, culture, variete=None, nb_plants=10, nb_graines=12):
    ev = Evenement(
        type_action="mise_en_godet", culture=culture, variete=variete,
        nb_plants_godets=nb_plants, nb_graines_semees=nb_graines,
        date=datetime(2026, 4, 10), parcelle_id=pid,
    )
    session.add(ev)
    session.flush()


def _plantation(session, pid, culture, variete=None, quantite=4):
    ev = Evenement(
        type_action="plantation", culture=culture, variete=variete,
        quantite=quantite, unite="plants",
        date=datetime(2026, 4, 20), parcelle_id=pid,
    )
    session.add(ev)
    session.flush()


# ── CA7 — Scénario exact de l'US ─────────────────────────────────────────────

def test_us022_ca7_scenario_exact_stock_residuel_6(db):
    """CA7 — mise_en_godet 10 plants jaune + plantation 4 plants jaune → stock résiduel = 6."""
    session, pid = db
    _godet(session, pid, "courgette", "jaune", nb_plants=10, nb_graines=12)
    _plantation(session, pid, "courgette", "jaune", quantite=4)

    result = calcul_godets_par_culture(session, "courgette")

    assert len(result) == 1
    g = result[0]
    assert g["variete"] == "jaune"
    assert g["nb_plants_godets"] == 10
    assert g["nb_plantes"] == 4
    assert g["stock_residuel_godet"] == 6


# ── CA1 — Plantation déduite par variété ─────────────────────────────────────

def test_us022_ca1_deduction_plantation_correcte(db):
    """CA1 — Le stock godet est bien décrémenté du nombre de plants plantés."""
    session, pid = db
    _godet(session, pid, "tomate", "cerise", nb_plants=8)
    _plantation(session, pid, "tomate", "cerise", quantite=3)

    result = calcul_godets_par_culture(session, "tomate")

    assert len(result) == 1
    assert result[0]["stock_residuel_godet"] == 5
    assert result[0]["nb_plantes"] == 3


# ── CA2 — Champs nb_plantes et stock_residuel_godet présents ─────────────────

def test_us022_ca2_champs_retournes(db):
    """CA2 — calcul_godets_par_culture() retourne nb_plantes et stock_residuel_godet."""
    session, pid = db
    _godet(session, pid, "poivron", "rouge", nb_plants=6)
    _plantation(session, pid, "poivron", "rouge", quantite=2)

    result = calcul_godets_par_culture(session, "poivron")

    assert len(result) == 1
    g = result[0]
    assert "nb_plantes" in g
    assert "stock_residuel_godet" in g
    assert g["nb_plants_godets"] == 6
    assert g["nb_plantes"] == 2
    assert g["stock_residuel_godet"] == 4


# ── CA2 — Sans plantation, nb_plantes = 0 et stock = nb_plants_godets ────────

def test_us022_ca2_sans_plantation_stock_intact(db):
    """CA2 — Sans plantation, le stock résiduel est égal au total repiqué."""
    session, pid = db
    _godet(session, pid, "poivron", "vert", nb_plants=5)

    result = calcul_godets_par_culture(session, "poivron")

    assert len(result) == 1
    g = result[0]
    assert g["nb_plantes"] == 0
    assert g["stock_residuel_godet"] == 5


# ── CA4 — Variété entièrement plantée absente de la liste ────────────────────

def test_us022_ca4_variete_entierement_plantee_absente(db):
    """CA4 — Quand tous les godets sont plantés, la variété disparaît de la liste."""
    session, pid = db
    _godet(session, pid, "aubergine", "violette", nb_plants=5)
    _plantation(session, pid, "aubergine", "violette", quantite=5)

    result = calcul_godets_par_culture(session, "aubergine")

    assert result == []


def test_us022_ca4_liste_vide_si_toutes_varietes_plantees(db):
    """CA4 — Section Pépinière vide si toutes les variétés ont stock résiduel = 0."""
    session, pid = db
    _godet(session, pid, "laitue", "batavia", nb_plants=4)
    _godet(session, pid, "laitue", "romaine", nb_plants=3)
    _plantation(session, pid, "laitue", "batavia", quantite=4)
    _plantation(session, pid, "laitue", "romaine", quantite=3)

    result = calcul_godets_par_culture(session, "laitue")

    assert result == []


# ── CA5 — Déduction strictement par (culture, variété) ───────────────────────

def test_us022_ca5_deduction_par_variete_isolation(db):
    """CA5 — Une plantation de variété jaune ne déduit pas du stock de variété verte."""
    session, pid = db
    _godet(session, pid, "courgette", "jaune", nb_plants=10)
    _godet(session, pid, "courgette", "verte", nb_plants=8)
    _plantation(session, pid, "courgette", "jaune", quantite=5)

    result = calcul_godets_par_culture(session, "courgette")
    par_var = {g["variete"]: g for g in result}

    assert par_var["jaune"]["stock_residuel_godet"] == 5
    assert par_var["verte"]["stock_residuel_godet"] == 8   # inchangé


def test_us022_ca5_pas_de_confusion_inter_cultures(db):
    """CA5 — Une plantation de tomate ne modifie pas le stock godet de poivron."""
    session, pid = db
    _godet(session, pid, "poivron", "jaune", nb_plants=6)
    _plantation(session, pid, "tomate", "cerise", quantite=3)  # autre culture

    result = calcul_godets_par_culture(session, "poivron")

    assert len(result) == 1
    assert result[0]["stock_residuel_godet"] == 6


# ── CA6 — Plantation sans variété → rattachement variété unique ──────────────

def test_us022_ca6_plantation_sans_variete_rattachee_variete_unique(db):
    """CA6 — Plantation sans variété rattachée à la seule variété en godet."""
    session, pid = db
    _godet(session, pid, "melon", "charentais", nb_plants=8)
    _plantation(session, pid, "melon", variete=None, quantite=3)  # sans variété

    result = calcul_godets_par_culture(session, "melon")

    assert len(result) == 1
    assert result[0]["variete"] == "charentais"
    assert result[0]["nb_plantes"] == 3
    assert result[0]["stock_residuel_godet"] == 5


def test_us022_ca6_plantation_sans_variete_ignoree_si_plusieurs_varietes(db):
    """CA6 — Plantation sans variété ignorée si plusieurs variétés en godet (log WARNING)."""
    session, pid = db
    _godet(session, pid, "potiron", "blanc", nb_plants=5)
    _godet(session, pid, "potiron", "orange", nb_plants=4)
    _plantation(session, pid, "potiron", variete=None, quantite=2)  # ambiguë

    result = calcul_godets_par_culture(session, "potiron")

    par_var = {g["variete"]: g for g in result}
    # Aucun stock ne doit être déduit (plantation ignorée)
    assert par_var["blanc"]["stock_residuel_godet"] == 5
    assert par_var["orange"]["stock_residuel_godet"] == 4


# ── CA6 — Godet ET plantation sans variété → match direct (régression cornichon) ──

def test_us022_ca6_godet_et_plantation_sans_variete(db):
    """CA6 — Quand godet et plantation ont variete=None, la déduction doit être appliquée.

    Régression : avant le fix, les plantations sans variété étaient ignorées
    quand le godet était aussi sans variété (varietes_avec_godet vide → else → WARNING).
    """
    session, pid = db
    _godet(session, pid, "cornichon", variete=None, nb_plants=10, nb_graines=30)
    _plantation(session, pid, "cornichon", variete=None, quantite=6)

    result = calcul_godets_par_culture(session, "cornichon")

    assert len(result) == 1
    g = result[0]
    assert g["variete"] is None
    assert g["nb_plants_godets"] == 10
    assert g["nb_plantes"] == 6
    assert g["stock_residuel_godet"] == 4


def test_us022_ca6_godet_et_plantation_sans_variete_entierement_plante(db):
    """CA6 — Godet et plantation sans variété, stock = 0 → absent de la liste (CA4)."""
    session, pid = db
    _godet(session, pid, "cornichon", variete=None, nb_plants=6, nb_graines=18)
    _plantation(session, pid, "cornichon", variete=None, quantite=6)

    result = calcul_godets_par_culture(session, "cornichon")

    assert result == []


# ── Stocke jamais négatif ─────────────────────────────────────────────────────

def test_us022_stock_residuel_jamais_negatif(db):
    """Stock résiduel ne peut pas être négatif même si plantation > godets."""
    session, pid = db
    _godet(session, pid, "haricot", "vert", nb_plants=3)
    _plantation(session, pid, "haricot", "vert", quantite=10)  # plus que le stock

    result = calcul_godets_par_culture(session, "haricot")

    # stock = max(0, 3-10) = 0 → variété absente (filtrée par CA4)
    assert result == []


# ── CA6-reverse — Godet sans variété + plantation avec variété ────────────────

def test_us022_ca6_reverse_godet_sans_variete_plantation_avec_variete(db):
    """CA6-reverse — Godet sans variété + plantation avec variété unique → stock correct.

    Cas réel cornichon :
      mise_en_godet(variete=None, 10 plants)
      plantation(variete='petit Paris', 8 plants)
      → stock résiduel = 2 (pas 10)
    """
    from utils.stock import calcul_godets
    session, pid = db
    _godet(session, pid, "cornichon", variete=None, nb_plants=10, nb_graines=30)
    _plantation(session, pid, "cornichon", variete="petit Paris", quantite=8)

    # calcul_godets_par_culture
    result = calcul_godets_par_culture(session, "cornichon")
    assert len(result) == 1
    g = result[0]
    assert g["variete"] is None
    assert g["nb_plants_godets"] == 10
    assert g["nb_plantes"] == 8         # plantation 'petit Paris' rattachée
    assert g["stock_residuel_godet"] == 2

    # calcul_godets (cohérence)
    godets = calcul_godets(session, include_epuises=False)
    assert len(godets) == 1
    v = list(godets.values())[0]
    assert v["nb_plantes"] == 8
    assert v["stock_residuel_godet"] == 2


def test_us022_ca6_reverse_pas_rattachement_si_plusieurs_varietes(db):
    """CA6-reverse — Pas de rattachement si plusieurs variétés en plantation (ambiguïté)."""
    session, pid = db
    _godet(session, pid, "tomate", variete=None, nb_plants=10, nb_graines=15)
    _plantation(session, pid, "tomate", variete="cerise", quantite=3)
    _plantation(session, pid, "tomate", variete="cœur de bœuf", quantite=4)

    # Deux variétés en plantation → impossible de rattacher → stock reste = 10
    result = calcul_godets_par_culture(session, "tomate")
    assert len(result) == 1
    assert result[0]["stock_residuel_godet"] == 10

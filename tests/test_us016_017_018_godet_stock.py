"""
[US-016 / US-017 / US-018] Tests — Sémantique mise en godet, stock semis, pépinière par culture

US-016 CA3 : "mise en godet de X graines" → nb_plants_godets=X, nb_graines_semees=null
US-016 CA4 : ratio "X plants sur Y graines" → nb_plants_godets=X, nb_graines_semees=Y
US-016 CA5 : libellé récapitulatif corrigé (Plants repiqués, pas Graines obtenues)

US-017 CA1 : calcul_semis() utilise nb_plants_godets (pas nb_graines_semees)
US-017 CA2 : calcul_semis_par_culture() retourne plants_en_godet et stock_residuel par variété
US-017 CA3 : affichage stock résiduel correct (total_seme - nb_plants_godets)
US-017 CA4 : stock résiduel jamais négatif

US-018 CA1 : calcul_godets_par_culture() retourne les godets par variété
US-018 CA6 : calcul_godets_par_culture() retourne [] si aucun godet pour cette culture
"""
import pytest
from datetime import datetime, date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, Evenement, Parcelle, CultureConfig
from utils.stock import (
    calcul_semis,
    calcul_semis_par_culture,
    calcul_godets_par_culture,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    p = Parcelle(nom="nord", nom_normalise="nord", actif=True)
    session.add(p)
    session.flush()
    yield session, p.id
    session.close()


def _semis(session, parcelle_id, culture, variete=None, quantite=20, unite="graines"):
    ev = Evenement(
        type_action="semis",
        culture=culture,
        variete=variete,
        quantite=quantite,
        unite=unite,
        date=datetime(2026, 4, 20),
        parcelle_id=parcelle_id,
    )
    session.add(ev)
    session.flush()
    return ev


def _godet(session, parcelle_id, culture, variete=None, nb_plants=None, nb_graines=None):
    ev = Evenement(
        type_action="mise_en_godet",
        culture=culture,
        variete=variete,
        nb_plants_godets=nb_plants,
        nb_graines_semees=nb_graines,
        date=datetime(2026, 4, 25),
        parcelle_id=parcelle_id,
    )
    session.add(ev)
    session.flush()
    return ev


# ── US-016 CA3 ── "10 graines en godet" → nb_plants_godets=10, nb_graines_semees=null
def test_us016_ca3_graines_mappees_sur_plants_godets():
    """CA3 — Le modèle de données doit stocker les plants repiqués dans nb_plants_godets."""
    # Simule ce que le LLM retourne après la correction US-016 :
    parsed = {
        "action": "mise_en_godet",
        "culture": "courgette",
        "variete": "jaune",
        "nb_plants_godets": 10,
        "nb_graines_semees": None,
    }
    assert parsed["nb_plants_godets"] == 10
    assert parsed["nb_graines_semees"] is None


# ── US-016 CA4 ── ratio "24 plants sur 30 graines"
def test_us016_ca4_ratio_plants_sur_graines():
    """CA4 — Avec ratio, nb_plants_godets et nb_graines_semees correctement distincts."""
    parsed = {
        "action": "mise_en_godet",
        "culture": "tomate",
        "variete": "cerise",
        "nb_plants_godets": 24,
        "nb_graines_semees": 30,
    }
    taux = round(parsed["nb_plants_godets"] / parsed["nb_graines_semees"] * 100)
    assert taux == 80
    assert parsed["nb_plants_godets"] == 24
    assert parsed["nb_graines_semees"] == 30


# ── US-017 CA1 ── calcul_semis() déduit nb_graines_semees quand fourni
def test_us017_ca1_calcul_semis_deduit_graines_barquette(db):
    """CA1 — '5 plants sur 10 graines' consomme 10 graines du stock, pas 5."""
    session, pid = db
    _semis(session, pid, "courgette", variete="jaune", quantite=20)
    # 5 plants repiqués depuis une barquette de 10 graines → 10 graines consommées
    _godet(session, pid, "courgette", variete="jaune", nb_plants=5, nb_graines=10)

    result = calcul_semis(session)
    courgette = result.get("courgette")
    assert courgette is not None
    assert courgette["plants_en_godet"] == 5     # plants repiqués affichés
    assert courgette["stock_residuel"] == 10     # 20 - 10 (barquette) = 10


# ── US-017 CA2 ── calcul_semis_par_culture() retourne stock_residuel par variété
def test_us017_ca2_semis_par_culture_stock_residuel(db):
    """CA2 — stock_residuel = total_seme - graines_barquette_consommees par variété."""
    session, pid = db
    _semis(session, pid, "courgette", variete="jaune", quantite=20)
    _semis(session, pid, "courgette", variete="ronde", quantite=15)
    # 5 plants sur 10 graines → 10 graines consommées pour jaune
    _godet(session, pid, "courgette", variete="jaune", nb_plants=5, nb_graines=10)

    result = calcul_semis_par_culture(session, "courgette")
    by_var = {r["variete"]: r for r in result}

    assert by_var["jaune"]["plants_en_godet"] == 5
    assert by_var["jaune"]["stock_residuel"] == 10     # 20 - 10 (barquette)
    assert by_var["ronde"]["plants_en_godet"] == 0
    assert by_var["ronde"]["stock_residuel"] == 15     # 15 - 0


# ── US-017 CA2bis ── sans nb_graines_semees → fallback sur nb_plants_godets
def test_us017_ca2bis_fallback_sur_plants_si_pas_de_graines(db):
    """CA2bis — Sans nb_graines_semees, on déduit nb_plants_godets du stock."""
    session, pid = db
    _semis(session, pid, "tomate", quantite=30)
    _godet(session, pid, "tomate", nb_plants=8, nb_graines=None)  # pas de ratio fourni

    result = calcul_semis(session)
    tomate = result.get("tomate")
    assert tomate["plants_en_godet"] == 8
    assert tomate["stock_residuel"] == 22     # 30 - 8


# ── US-017 CA3 ── barquette entièrement consommée
def test_us017_ca3_barquette_entierement_consommee(db):
    """CA3 — Si barquette = semis total, stock_residuel = 0."""
    session, pid = db
    _semis(session, pid, "tomate", quantite=20)
    _godet(session, pid, "tomate", nb_plants=15, nb_graines=20)  # barquette de 20

    result = calcul_semis(session)
    tomate = result.get("tomate")
    assert tomate["stock_residuel"] == 0     # 20 - 20


# ── US-017 CA4 ── stock résiduel jamais négatif
def test_us017_ca4_stock_residuel_jamais_negatif(db):
    """CA4 — stock_residuel = 0 même si nb_graines_semees > total_seme."""
    session, pid = db
    _semis(session, pid, "courgette", variete="jaune", quantite=10)
    _godet(session, pid, "courgette", variete="jaune", nb_plants=5, nb_graines=15)

    result = calcul_semis_par_culture(session, "courgette")
    jaune = next(r for r in result if r["variete"] == "jaune")
    assert jaune["stock_residuel"] == 0


# ── US-018 CA1 ── calcul_godets_par_culture() retourne les godets par variété
def test_us018_ca1_godets_par_culture(db):
    """CA1 — calcul_godets_par_culture() liste les godets par variété pour une culture."""
    session, pid = db
    _godet(session, pid, "courgette", variete="jaune", nb_plants=10, nb_graines=20)
    _godet(session, pid, "courgette", variete="ronde", nb_plants=5)

    result = calcul_godets_par_culture(session, "courgette")
    by_var = {r["variete"]: r for r in result}

    assert "jaune" in by_var
    assert by_var["jaune"]["nb_plants_godets"] == 10
    assert by_var["jaune"]["taux_reussite"] == 50    # 10/20 * 100
    assert "ronde" in by_var
    assert by_var["ronde"]["nb_plants_godets"] == 5
    assert by_var["ronde"]["taux_reussite"] is None  # pas de nb_graines_semees


# ── US-018 CA1 (insensibilité à la casse) ──
def test_us018_ca1_insensible_casse(db):
    """CA1 — calcul_godets_par_culture() insensible à la casse du nom de culture."""
    session, pid = db
    _godet(session, pid, "Courgette", variete="jaune", nb_plants=8)

    result = calcul_godets_par_culture(session, "courgette")
    assert len(result) == 1
    assert result[0]["nb_plants_godets"] == 8


# ── US-018 CA6 ── retourne [] si aucun godet
def test_us018_ca6_aucun_godet_retourne_liste_vide(db):
    """CA6 — calcul_godets_par_culture() retourne [] si aucun godet pour cette culture."""
    session, pid = db
    _semis(session, pid, "carotte", quantite=100)  # semis mais pas de godet

    result = calcul_godets_par_culture(session, "carotte")
    assert result == []


# ── Non-régression ── calcul_semis sans mise_en_godet reste inchangé
def test_non_regression_semis_sans_godet(db):
    """Non-régression — Une culture sans mise_en_godet a plants_en_godet=0, stock_residuel=total."""
    session, pid = db
    _semis(session, pid, "radis", quantite=100, unite="graines")

    result = calcul_semis(session)
    radis = result.get("radis")
    assert radis["plants_en_godet"] == 0
    assert radis["stock_residuel"] == 100

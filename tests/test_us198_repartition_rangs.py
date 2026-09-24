"""
tests/test_us198_repartition_rangs.py — Répartition des cultures en rangs [US-198]

Critères couverts :
- CA1  un seul module de service, en lecture seule, qui réutilise l'occupation
- CA2  GET /plan : champs de rang par culture, `disposition` par parcelle
- CA3  GET /plan : bloc de totaux, sans mêler une parcelle sans dénominateur
- CA4  tout est calculé à la date de référence (US-030)
- CA5  une seule lecture : aucune requête par parcelle ni par ligne
- CA6  aucun calcul existant ne change (stock, occupation_pct, occupation servie)
- CA9  R1 à R9 : rangs, quantité par rang, modes, numérotation, libres,
       dépassement, pépinière, non localisé, date passée
"""
from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from app.services.repartition_rangs import (
    MODE_POQUET,
    MODE_RANG,
    MODE_SURFACE,
    NUMEROTATION_ORDRE_INSTALLATION,
    cle_ligne,
    mode_implantation,
    repartition_du_plan,
)
from database.models import CultureConfig, Evenement, Parcelle, Potager, User
from utils.parcelles import calcul_occupation_parcelles, get_all_parcelles

DATE_REF = date(2026, 7, 1)


# ══════════════════════════════════════════════════════════════════════════════
# Fixtures — un potager réel, lu comme le fait GET /plan
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def db(test_db):
    test_db.add(User(id=1, email="a@potager.test"))
    test_db.flush()
    test_db.add(Potager(id=1, nom="Jardin", proprietaire_id=1))
    test_db.flush()
    test_db.add_all([
        CultureConfig(nom="tomate", type_organe_recolte="reproducteur"),
        CultureConfig(nom="poireau", type_organe_recolte="végétatif"),
        CultureConfig(nom="carotte", type_organe_recolte="végétatif"),
        CultureConfig(nom="courgette", type_organe_recolte="reproducteur"),
        CultureConfig(nom="radis", type_organe_recolte="végétatif"),
        CultureConfig(nom="laitue", type_organe_recolte="végétatif"),
        CultureConfig(nom="basilic", type_organe_recolte="végétatif"),
    ])
    test_db.add_all([
        Parcelle(id=1, nom="planche centrale", nom_normalise="planchecentrale",
                 potager_id=1, ordre=1, nb_rangs=5, superficie_m2=6.0),
        Parcelle(id=2, nom="planche est", nom_normalise="plancheest",
                 potager_id=1, ordre=2, nb_rangs=None, superficie_m2=4.0),
        Parcelle(id=3, nom="butte", nom_normalise="butte",
                 potager_id=1, ordre=3, nb_rangs=1),
        Parcelle(id=4, nom="serre", nom_normalise="serre",
                 potager_id=1, ordre=4, nb_rangs=2, est_pepiniere=True),
    ])
    test_db.commit()
    return test_db


def _geste(db, **champs) -> None:
    champs.setdefault("potager_id", 1)
    champs.setdefault("unite", "plants")
    db.add(Evenement(**champs))
    db.commit()


def _repartir(db, date_ref: date = DATE_REF) -> dict:
    """Le chemin exact de GET /plan : occupation d'abord, répartition ensuite."""
    parcelles = get_all_parcelles(db, potager_id=1)
    occupation = calcul_occupation_parcelles(db, date_ref, potager_id=1)
    return repartition_du_plan(db, parcelles, occupation, potager_id=1, date_ref=date_ref)


def test_us198_ca17_plantations_existantes_completent_puis_ouvrent(db) -> None:
    parcelle = db.get(Parcelle, 1)
    parcelle.longueur_m = 4
    for jour, quantite in ((1, 4), (2, 12)):
        _geste(db, type_action="plantation", culture="laitue", quantite=quantite,
               parcelle_id=1, date=datetime(2026, 6, jour))
    occupation = calcul_occupation_parcelles(db, DATE_REF, potager_id=1)
    resultat = repartition_du_plan(
        db, get_all_parcelles(db, potager_id=1), occupation, potager_id=1,
        date_ref=DATE_REF, attributs_culture={"laitue": {"espacement_rang_cm": 30}},
    )
    disposition = resultat["dispositions"][parcelle.nom]
    occupes = [rang for rang in disposition["rangs"] if not rang["libre"]]
    assert [rang["quantite_par_rang"] for rang in occupes] == [13, 3]
    assert [rang["places_restantes"] for rang in occupes] == [0, 10]
    assert disposition["rangs_libres"] == 3


def _repartir_mesure(db, date_ref=DATE_REF, espacement=30):
    return repartition_du_plan(
        db, get_all_parcelles(db, potager_id=1),
        calcul_occupation_parcelles(db, date_ref, potager_id=1), potager_id=1,
        date_ref=date_ref,
        attributs_culture={"laitue": {"espacement_rang_cm": espacement}},
    )


@pytest.mark.parametrize("initial,ajout,declares,attendus,exces", [
    (4, 5, 5, [9], 0),
    (4, 9, 5, [13], 0),
    (4, 12, 5, [13, 3], 0),
    (4, 30, 5, [13, 13, 8], 0),
    (4, 12, 1, [16], 3),
    (4, 30, 2, [13, 21], 8),
    (0, 30, 5, [13, 13, 4], 0),
    (0, 26, 5, [13, 13], 0),
    (0, 40, 2, [13, 27], 14),
])
def test_us198_ca10_a_ca14_affectation_progressive(db, initial, ajout, declares, attendus, exces):
    parcelle = db.get(Parcelle, 1)
    parcelle.longueur_m = 4
    parcelle.nb_rangs = declares
    if initial:
        _geste(db, type_action="plantation", culture="laitue", quantite=initial,
               parcelle_id=1, date=datetime(2026, 6, 1))
    _geste(db, type_action="plantation", culture="laitue", quantite=ajout,
           parcelle_id=1, date=datetime(2026, 6, 2))
    resultat = _repartir_mesure(db)
    disposition = resultat["dispositions"][parcelle.nom]
    occupes = [rang for rang in disposition["rangs"] if not rang["libre"]]
    assert [rang["quantite_par_rang"] for rang in occupes] == attendus
    assert sum(rang["quantite_par_rang"] for rang in occupes) == initial + ajout
    assert sum(rang["depassement_places"] for rang in occupes) == exces
    assert disposition["rangs_occupes"] == len(attendus)
    assert disposition["rangs_libres"] == declares - len(attendus)
    assert disposition["depassement"] == 0
    assert resultat == _repartir_mesure(db)


def test_us198_ca11_complete_deux_rangs_explicitement_declares(db):
    db.get(Parcelle, 1).longueur_m = 4
    for jour, quantite, rang in ((1, 10, 1), (2, 8, 1), (3, 7, None)):
        _geste(db, type_action="plantation", culture="laitue", quantite=quantite,
               rang=rang, parcelle_id=1, date=datetime(2026, 6, jour))
    disposition = _repartir_mesure(db)["dispositions"]["planche centrale"]
    assert [rang["quantite_par_rang"] for rang in disposition["rangs"] if not rang["libre"]] == [13, 12]
    assert disposition["rangs_libres"] == 3


def test_us198_ca14_declaration_explicite_ne_se_repartit_pas(db):
    db.get(Parcelle, 1).longueur_m = 4
    _geste(db, type_action="plantation", culture="laitue", quantite=16,
           rang=2, parcelle_id=1, date=datetime(2026, 6, 1))
    disposition = _repartir_mesure(db)["dispositions"]["planche centrale"]
    assert [rang["quantite_par_rang"] for rang in disposition["rangs"] if not rang["libre"]] == [16, 16]
    assert [rang["depassement_places"] for rang in disposition["rangs"] if not rang["libre"]] == [3, 3]


@pytest.mark.parametrize("variete,unite,type_action", [
    ("batavia", "plants", "plantation"),
    (None, "plants", "plantation"),
    ("romaine", "pieds", "plantation"),
    ("romaine", "plants", "semis"),
])
def test_us198_ca10_ne_melange_pas_les_lignes(db, variete, unite, type_action):
    db.get(Parcelle, 1).longueur_m = 4
    _geste(db, type_action="plantation", culture="laitue", variete="romaine",
           quantite=4, parcelle_id=1, date=datetime(2026, 6, 1))
    _geste(db, type_action=type_action, culture="laitue", variete=variete,
           unite=unite, quantite=5, parcelle_id=1, date=datetime(2026, 6, 2))
    disposition = _repartir_mesure(db)["dispositions"]["planche centrale"]
    assert [rang["quantite_par_rang"] for rang in disposition["rangs"] if not rang["libre"]] == [4, 5]


def test_us198_ca12_preserve_les_autres_cultures_dans_l_ordre_des_gestes(db):
    parcelle = db.get(Parcelle, 1)
    parcelle.longueur_m = 4
    parcelle.nb_rangs = 3
    for jour, culture, quantite in ((1, "laitue", 4), (2, "tomate", 3), (3, "laitue", 30)):
        _geste(db, type_action="plantation", culture=culture, quantite=quantite,
               parcelle_id=1, date=datetime(2026, 6, jour))
    resultat = _repartir_mesure(db)
    rangs = resultat["dispositions"][parcelle.nom]["rangs"]
    assert [(rang["culture"], rang["quantite_par_rang"]) for rang in rangs] == [
        ("laitue", 13), ("tomate", 3), ("laitue", 21),
    ]
    assert resultat["lignes"][_cle(parcelle.nom, "laitue")]["numeros_rangs"] == [1, 3]
    assert rangs[-1]["depassement_places"] == 8


def test_us198_ca19_nouvelle_culture_parcelle_pleine(db):
    parcelle = db.get(Parcelle, 1)
    parcelle.longueur_m = 4
    parcelle.nb_rangs = 1
    for jour, culture, quantite in ((1, "tomate", 4), (2, "laitue", 16)):
        _geste(db, type_action="plantation", culture=culture, quantite=quantite,
               parcelle_id=1, date=datetime(2026, 6, jour))
    disposition = _repartir_mesure(db)["dispositions"][parcelle.nom]
    assert disposition["depassement"] == 1
    assert disposition["rangs_libres"] == 0
    assert disposition["rangs"][1]["culture"] == "laitue"
    assert disposition["rangs"][1]["quantite_par_rang"] == 16
    assert disposition["rangs"][1]["depassement_places"] == 3


def test_us198_ca18_recalcule_sans_modifier_les_evenements(db):
    parcelle = db.get(Parcelle, 1)
    parcelle.longueur_m = 4
    _geste(db, type_action="plantation", culture="laitue", quantite=16,
           parcelle_id=1, date=datetime(2026, 6, 1))
    avant = [(geste.id, geste.quantite, geste.rang) for geste in db.query(Evenement).all()]
    for longueur, espacement, attendu in ((4, 30, [13, 3]), (3, 30, [10, 6]), (3, 15, [16])):
        parcelle.longueur_m = longueur
        db.commit()
        disposition = _repartir_mesure(db, espacement=espacement)["dispositions"][parcelle.nom]
        assert [rang["quantite_par_rang"] for rang in disposition["rangs"] if not rang["libre"]] == attendu
    assert [(geste.id, geste.quantite, geste.rang) for geste in db.query(Evenement).all()] == avant


@pytest.mark.parametrize("longueur,declares,espacement,unite,type_action,parcelle_id", [
    (None, 5, 30, "plants", "plantation", 1),
    (4, None, 30, "plants", "plantation", 1),
    (4, 5, None, "plants", "plantation", 1),
    (4, 5, 30, "graines", "semis", 1),
    (4, 5, 30, "m²", "plantation", 1),
    (4, 5, 30, "plants", "plantation", 4),
])
def test_us198_ca10_repli_et_perimetre_inchanges(db, longueur, declares, espacement, unite, type_action, parcelle_id):
    parcelle = db.get(Parcelle, parcelle_id)
    parcelle.longueur_m = longueur
    parcelle.nb_rangs = declares
    _geste(db, type_action=type_action, culture="laitue", quantite=30,
           unite=unite, parcelle_id=parcelle_id, date=datetime(2026, 6, 1))
    disposition = _repartir_mesure(db, espacement=espacement)["dispositions"][parcelle.nom]
    assert disposition["rangs_occupes"] == 1
    assert disposition["rangs"][0]["quantite_par_rang"] == 30


def test_us198_ca17_date_reference_avant_ajout(db):
    db.get(Parcelle, 1).longueur_m = 4
    for jour, quantite in ((1, 4), (20, 12)):
        _geste(db, type_action="plantation", culture="laitue", quantite=quantite,
               parcelle_id=1, date=datetime(2026, 6, jour))
    disposition = _repartir_mesure(db, date_ref=date(2026, 6, 10))["dispositions"]["planche centrale"]
    assert disposition["rangs_occupes"] == 1
    assert disposition["rangs"][0]["quantite_par_rang"] == 4


def test_us198_ca15_api_expose_les_quantites_de_chaque_rang(db):
    from app.api.main import get_plan
    from app.services.context import TenantContext

    db.get(Parcelle, 1).longueur_m = 4
    db.query(CultureConfig).filter(CultureConfig.nom == "laitue").one().espacement = "30 à 30 cm"
    _geste(db, type_action="plantation", culture="laitue", quantite=16,
           parcelle_id=1, date=datetime(2026, 6, 1))
    with patch("app.api.main.SessionLocal", return_value=db):
        reponse = get_plan(date_ref=DATE_REF, potager_id=None,
                           ctx=TenantContext(user_id=1, potager_id=1, role="owner"))
    parcelle = next(parcelle for parcelle in reponse["parcelles"] if parcelle["id"] == 1)
    assert parcelle["cultures"][0]["nb_plants"] == 16
    assert parcelle["cultures"][0]["numeros_rangs"] == [1, 2]
    assert [rang["quantite_par_rang"] for rang in parcelle["disposition"]["rangs"] if not rang["libre"]] == [13, 3]


def test_us198_ca10_affectation_isolee_par_potager(db):
    db.get(Parcelle, 1).longueur_m = 4
    db.add(Potager(id=2, nom="Autre jardin", proprietaire_id=1))
    db.flush()
    db.add(Parcelle(id=5, nom="planche centrale", nom_normalise="planchecentrale",
                    potager_id=2, nb_rangs=5, longueur_m=4))
    _geste(db, type_action="plantation", culture="laitue", quantite=40,
           parcelle_id=5, potager_id=2, date=datetime(2026, 6, 1))
    _geste(db, type_action="plantation", culture="laitue", quantite=16,
           parcelle_id=1, date=datetime(2026, 6, 2))
    disposition = _repartir_mesure(db)["dispositions"]["planche centrale"]
    assert [rang["quantite_par_rang"] for rang in disposition["rangs"] if not rang["libre"]] == [13, 3]


def test_us198_recolte_partielle_conserve_la_regle_actuelle(db):
    db.get(Parcelle, 1).longueur_m = 4
    _geste(db, type_action="plantation", culture="laitue", quantite=30,
           parcelle_id=1, date=datetime(2026, 6, 1))
    _geste(db, type_action="recolte", culture="laitue", quantite=14,
           parcelle_id=1, date=datetime(2026, 6, 2))
    disposition = _repartir_mesure(db)["dispositions"]["planche centrale"]
    assert disposition["rangs_occupes"] == 1
    assert disposition["rangs"][0]["quantite_par_rang"] == 16


def _cle(parcelle: str, culture: str, variete: str = "", unite: str = "plants",
         semis: bool = False) -> tuple:
    entree = {"culture": culture, "variete": variete, "unite": unite}
    if semis:
        entree["type_action"] = "semis"
    return cle_ligne(parcelle, entree)


# ══════════════════════════════════════════════════════════════════════════════
# R4 — Le mode d'implantation se déduit de la seule unité
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("unite,attendu", [
    ("plants", MODE_RANG),
    ("graines", MODE_RANG),
    ("pieds", MODE_RANG),
    (None, MODE_RANG),
    ("m²", MODE_SURFACE),
    ("m2", MODE_SURFACE),
    ("poquets", MODE_POQUET),
    ("Poquet", MODE_POQUET),
])
def test_us198_r4_mode_deduit_de_l_unite(unite, attendu) -> None:
    """R4 — m² → surface, poquet → poquet, toute autre unité → rang."""
    assert mode_implantation(unite) == attendu


# ══════════════════════════════════════════════════════════════════════════════
# Scénario Gherkin 1 — Deux lignes, rangs libres (R2, R3, R5, R6)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def db_deux_lignes(db):
    _geste(db, type_action="plantation", culture="tomate", variete="noire de Crimée",
           quantite=8.0, rang=1, parcelle_id=1, date=datetime(2026, 6, 1))
    # « planté 6 poireaux sur 2 rangs » — 12 plants, 2 rangs.
    _geste(db, type_action="plantation", culture="poireau", quantite=6.0, rang=2,
           parcelle_id=1, date=datetime(2026, 6, 10))
    return db


def test_us198_ca9_une_ligne_sur_un_rang(db_deux_lignes) -> None:
    """R2, R5 — La ligne la plus anciennement installée prend le rang 1."""
    lignes = _repartir(db_deux_lignes)["lignes"]
    tomate = lignes[_cle("planche centrale", "tomate", "noire de Crimée")]
    assert tomate["rangs"] == 1
    assert tomate["numeros_rangs"] == [1]
    assert tomate["quantite_par_rang"] == 8
    assert tomate["date_installation"] == date(2026, 6, 1)


def test_us198_ca9_plantation_sur_trois_rangs(db_deux_lignes) -> None:
    """R2, R3 — « sur 2 rangs » occupe 2 rangs, chacun portant 6 des 12 plants."""
    lignes = _repartir(db_deux_lignes)["lignes"]
    poireau = lignes[_cle("planche centrale", "poireau")]
    assert poireau["rangs"] == 2
    assert poireau["numeros_rangs"] == [2, 3]
    assert poireau["quantite_par_rang"] == 6


def test_us198_ca9_numerotation_et_rangs_libres(db_deux_lignes) -> None:
    """R5, R6 — Rangs numérotés dans l'ordre d'installation, les libres suivent."""
    disposition = _repartir(db_deux_lignes)["dispositions"]["planche centrale"]
    assert disposition["rangs_declares"] == 5
    assert disposition["rangs_occupes"] == 3
    assert disposition["rangs_libres"] == 2
    assert disposition["depassement"] == 0
    assert disposition["mode_numerotation"] == NUMEROTATION_ORDRE_INSTALLATION
    assert [(r["numero"], r["culture"], r["libre"]) for r in disposition["rangs"]] == [
        (1, "tomate", False),
        (2, "poireau", False),
        (3, "poireau", False),
        (4, None, True),
        (5, None, True),
    ]


def test_us198_ca9_deux_installations_de_la_meme_ligne(db_deux_lignes) -> None:
    """R2 — Une même ligne née de deux installations somme leurs rangs."""
    _geste(db_deux_lignes, type_action="plantation", culture="poireau", quantite=4.0,
           rang=1, parcelle_id=1, date=datetime(2026, 6, 20))
    poireau = _repartir(db_deux_lignes)["lignes"][_cle("planche centrale", "poireau")]
    assert poireau["rangs"] == 3
    # 12 + 4 plants sur 3 rangs.
    assert poireau["quantite_par_rang"] == 5


def test_us198_r2_des_gestes_muets_n_inventent_aucun_rang(db) -> None:
    """R2 — Plusieurs installations qui ne disent « sur N rangs » ni l'une ni
    l'autre : la ligne occupe UN rang, pas un par geste.

    Retour de terrain (23/09/2026) : quatre semis de tomate du même jour
    occupaient quatre rangs d'une planche qui n'en déclare que sept, et le plan
    affichait « 10 rangs occupés pour 7 déclarés ». Le nombre de gestes
    d'installation n'est pas un nombre de rangs — seul le multiplicateur dicté
    l'est.
    """
    for quantite in (10.0, 20.0, 30.0, 10.0):
        _geste(db, type_action="semis", culture="tomate", quantite=quantite,
               unite="graines", parcelle_id=1, date=datetime(2026, 6, 1))
    ligne = _repartir(db)["lignes"][
        _cle("planche centrale", "tomate", unite="graines", semis=True)
    ]
    assert ligne["rangs"] == 1
    assert ligne["quantite_par_rang"] == 70


def test_us198_r2_un_seul_geste_dicte_suffit_a_donner_le_compte(db) -> None:
    """R2 — Un geste muet à côté d'un geste qui dit « sur 2 rangs » : seuls les
    multiplicateurs réellement dictés sont sommés."""
    # « planté 6 poireaux sur 2 rangs » = 12 pieds, puis 6 pieds sans rang dit.
    _geste(db, type_action="plantation", culture="poireau", quantite=6.0,
           rang=2, parcelle_id=1, date=datetime(2026, 6, 1))
    _geste(db, type_action="plantation", culture="poireau", quantite=6.0,
           parcelle_id=1, date=datetime(2026, 6, 2))
    ligne = _repartir(db)["lignes"][_cle("planche centrale", "poireau")]
    assert ligne["rangs"] == 2
    # 12 + 6 pieds sur les 2 rangs dits.
    assert ligne["quantite_par_rang"] == 9


# ══════════════════════════════════════════════════════════════════════════════
# R3, R4 — Quantité par rang en m² (scénario « Semis en surface »)
# ══════════════════════════════════════════════════════════════════════════════

def test_us198_ca9_quantite_par_rang_en_m2(db) -> None:
    """R3, R4 — 2 m² de carottes : mode surface, 2 m² sur son rang."""
    _geste(db, type_action="semis", culture="carotte", quantite=2.0, unite="m²",
           parcelle_id=1, date=datetime(2026, 6, 1))
    ligne = _repartir(db)["lignes"][
        _cle("planche centrale", "carotte", unite="m²", semis=True)
    ]
    assert ligne["mode_implantation"] == MODE_SURFACE
    assert ligne["rangs"] == 1
    assert ligne["quantite_par_rang"] == 2.0


def test_us198_r3_quantite_par_rang_jamais_zero(db) -> None:
    """R3 — Une ligne non vide porte au moins 1 par rang, jamais 0."""
    _geste(db, type_action="plantation", culture="poireau", quantite=1.0, rang=4,
           parcelle_id=1, date=datetime(2026, 6, 1))
    ligne = _repartir(db)["lignes"][_cle("planche centrale", "poireau")]
    assert ligne["rangs"] == 4
    assert ligne["quantite_par_rang"] == 1


# ══════════════════════════════════════════════════════════════════════════════
# R6, R7 — Sans nombre de rangs déclaré ; dépassement
# ══════════════════════════════════════════════════════════════════════════════

def test_us198_ca9_parcelle_sans_nombre_de_rangs(db) -> None:
    """R6 — Sans nombre déclaré : rangs libres inconnus (None), jamais zéro."""
    _geste(db, type_action="plantation", culture="courgette", quantite=3.0, rang=1,
           parcelle_id=2, date=datetime(2026, 6, 1))
    resultat = _repartir(db)
    assert resultat["lignes"][_cle("planche est", "courgette")]["numeros_rangs"] == [1]
    disposition = resultat["dispositions"]["planche est"]
    assert disposition["rangs_declares"] is None
    assert disposition["rangs_libres"] is None
    assert disposition["rangs_occupes"] == 1
    assert disposition["depassement"] == 0


def test_us198_ca9_depassement_aucune_culture_masquee(db) -> None:
    """R7 — Plus de lignes que de rangs : tout reste, la parcelle porte l'écart."""
    _geste(db, type_action="semis", culture="radis", quantite=30.0, unite="graines",
           parcelle_id=3, date=datetime(2026, 6, 1))
    _geste(db, type_action="semis", culture="laitue", quantite=20.0, unite="graines",
           parcelle_id=3, date=datetime(2026, 6, 2))
    resultat = _repartir(db)
    lignes_butte = [c for c in resultat["lignes"] if c[0] == "butte"]
    assert len(lignes_butte) == 2
    disposition = resultat["dispositions"]["butte"]
    assert disposition["rangs_occupes"] == 2
    assert disposition["depassement"] == 1
    assert disposition["rangs_libres"] == 0


# ══════════════════════════════════════════════════════════════════════════════
# R8 — Parcelle pépinière : des lots, pas des lignes de semis
# ══════════════════════════════════════════════════════════════════════════════

def test_us198_ca9_pepiniere_porte_ses_lots_en_cours(db) -> None:
    """R8 — La serre ne porte aucune ligne de semis mais dit ses lots en cours."""
    for jour in (1, 5, 9):
        _geste(db, type_action="semis", culture="tomate", quantite=20.0,
               unite="graines", parcelle_id=4, date=datetime(2026, 6, jour))
    resultat = _repartir(db)
    assert [c for c in resultat["lignes"] if c[0] == "serre"] == []
    assert resultat["dispositions"]["serre"]["nb_lots_en_cours"] == 3
    # Une parcelle ordinaire ne parle jamais de lots.
    assert resultat["dispositions"]["planche centrale"]["nb_lots_en_cours"] is None


def test_us198_ca9_plantation_en_pepiniere_reste_une_ligne(db) -> None:
    """R8 — Une plantation faite dans une pépinière reste une ligne comme ailleurs."""
    _geste(db, type_action="plantation", culture="basilic", quantite=4.0, rang=2,
           parcelle_id=4, date=datetime(2026, 6, 1))
    resultat = _repartir(db)
    ligne = resultat["lignes"][_cle("serre", "basilic")]
    assert ligne["rangs"] == 2
    assert resultat["dispositions"]["serre"]["rangs_occupes"] == 2


# ══════════════════════════════════════════════════════════════════════════════
# R9 — Les cultures non localisées : un bloc à part
# ══════════════════════════════════════════════════════════════════════════════

def test_us198_ca9_non_localise_sans_rang_ni_numerotation(db) -> None:
    """R9 — Une culture sans parcelle n'occupe aucun rang et n'est pas numérotée."""
    _geste(db, type_action="plantation", culture="basilic", quantite=3.0, rang=1,
           parcelle_id=None, date=datetime(2026, 6, 1))
    ligne = _repartir(db)["lignes"][_cle(None, "basilic")]
    assert ligne["rangs"] is None
    assert ligne["numeros_rangs"] == []
    assert ligne["quantite_par_rang"] is None
    assert ligne["mode_implantation"] == MODE_RANG


# ══════════════════════════════════════════════════════════════════════════════
# CA4 — Tout est calculé à la date de référence
# ══════════════════════════════════════════════════════════════════════════════

def test_us198_ca4_installation_posterieure_n_occupe_pas_de_rang(db_deux_lignes) -> None:
    """CA4 — À une date antérieure aux poireaux, ils n'occupent encore aucun rang."""
    resultat = _repartir(db_deux_lignes, date_ref=date(2026, 6, 5))
    assert _cle("planche centrale", "poireau") not in resultat["lignes"]
    disposition = resultat["dispositions"]["planche centrale"]
    assert disposition["rangs_occupes"] == 1
    assert disposition["rangs_libres"] == 4


def test_us198_ca4_rangs_d_une_installation_posterieure_ignores(db_deux_lignes) -> None:
    """CA4 — Un rang ajouté après la date de référence n'est pas compté."""
    _geste(db_deux_lignes, type_action="plantation", culture="tomate",
           variete="noire de Crimée", quantite=2.0, rang=3, parcelle_id=1,
           date=datetime(2026, 8, 1))
    tomate = _repartir(db_deux_lignes)["lignes"][
        _cle("planche centrale", "tomate", "noire de Crimée")
    ]
    assert tomate["rangs"] == 1


# ══════════════════════════════════════════════════════════════════════════════
# CA3 — Totaux
# ══════════════════════════════════════════════════════════════════════════════

def test_us198_ca3_totaux_ne_melent_pas_une_parcelle_sans_denominateur(db_deux_lignes) -> None:
    """CA3 — Une parcelle sans nombre de rangs n'entre pas dans le pourcentage."""
    _geste(db_deux_lignes, type_action="plantation", culture="courgette", quantite=3.0,
           rang=1, parcelle_id=2, date=datetime(2026, 6, 1))
    totaux = _repartir(db_deux_lignes)["totaux"]
    # planche centrale (5) + butte (1) ; la serre est une pépinière, la planche
    # est n'a pas de dénominateur.
    assert totaux["rangs_declares"] == 6
    assert totaux["rangs_occupes"] == 3
    assert totaux["parcelles_sans_nb_rangs"] == 1
    assert totaux["superficie_totale_m2"] == 10.0
    assert totaux["occupation_rangs_pct"] == 50


def test_us198_ca3_rangs_libres_par_parcelle_dans_l_ordre(db_deux_lignes) -> None:
    """CA3 — Les rangs libres sont listés dans l'ordre d'affichage des parcelles."""
    totaux = _repartir(db_deux_lignes)["totaux"]
    assert [(e["parcelle"], e["rangs_libres"]) for e in totaux["rangs_libres_par_parcelle"]] == [
        ("planche centrale", 2),
        ("planche est", None),
        ("butte", 1),
        ("serre", 2),
    ]


# ══════════════════════════════════════════════════════════════════════════════
# CA1, CA5, CA6 — Lecture seule, une seule lecture, aucun calcul changé
# ══════════════════════════════════════════════════════════════════════════════

def test_us198_ca1_ca6_l_occupation_n_est_ni_recalculee_ni_modifiee(db_deux_lignes) -> None:
    """CA1, CA6 — L'occupation reçue ressort intacte, sans être recalculée."""
    parcelles = get_all_parcelles(db_deux_lignes, potager_id=1)
    occupation = calcul_occupation_parcelles(db_deux_lignes, DATE_REF, potager_id=1)
    avant = {k: [dict(e) for e in v] for k, v in occupation.items()}
    with patch("utils.parcelles.calcul_occupation_parcelles") as recalcul:
        repartition_du_plan(db_deux_lignes, parcelles, occupation,
                            potager_id=1, date_ref=DATE_REF)
    recalcul.assert_not_called()
    assert {k: [dict(e) for e in v] for k, v in occupation.items()} == avant


def test_us198_ca6_le_stock_ne_change_pas(db_deux_lignes) -> None:
    """CA6 — Le stock est identique avant et après la répartition."""
    from utils.stock import calcul_stock_cultures
    avant = {c: s.stock_plants for c, s in
             calcul_stock_cultures(db_deux_lignes, DATE_REF, potager_id=1).items()}
    _repartir(db_deux_lignes)
    apres = {c: s.stock_plants for c, s in
             calcul_stock_cultures(db_deux_lignes, DATE_REF, potager_id=1).items()}
    assert apres == avant


def test_us198_ca5_le_nombre_de_lectures_ne_depend_pas_de_la_taille_du_plan(db_deux_lignes) -> None:
    """CA5 — Ni une requête par parcelle, ni une requête par ligne : le nombre de
    lectures est le même sur un plan de deux lignes et sur un plan trois fois
    plus fourni."""
    def _lectures(db) -> int:
        parcelles = get_all_parcelles(db, potager_id=1)
        occupation = calcul_occupation_parcelles(db, DATE_REF, potager_id=1)
        compteur = {"n": 0}
        vraie_query = db.query

        def _compter(*args, **kwargs):
            compteur["n"] += 1
            return vraie_query(*args, **kwargs)

        with patch.object(db, "query", side_effect=_compter):
            repartition_du_plan(db, parcelles, occupation,
                                potager_id=1, date_ref=DATE_REF)
        return compteur["n"]

    petit = _lectures(db_deux_lignes)
    db_deux_lignes.add(Parcelle(id=5, nom="planche ouest", nom_normalise="plancheouest",
                                potager_id=1, ordre=5, nb_rangs=4))
    db_deux_lignes.commit()
    for culture, jour in (("radis", 1), ("laitue", 2), ("carotte", 3)):
        _geste(db_deux_lignes, type_action="plantation", culture=culture, quantite=5.0,
               rang=1, parcelle_id=5, date=datetime(2026, 6, jour))
    assert _lectures(db_deux_lignes) == petit


# ══════════════════════════════════════════════════════════════════════════════
# CA2, CA3 — Ce que GET /plan sert réellement
# ══════════════════════════════════════════════════════════════════════════════

def _parcelle_mock(nom: str, *, id_: int, nb_rangs=None, ordre=0, pepiniere=False,
                   superficie=None):
    p = MagicMock(spec=Parcelle)
    p.id = id_
    p.nom = nom
    p.exposition = None
    p.superficie_m2 = superficie
    p.abri = None
    p.paillage = None
    p.nb_rangs = nb_rangs
    p.longueur_m = None  # [US-225] non renseignée
    p.ordre = ordre
    p.est_pepiniere = pepiniere
    p.actif = True
    return p


@pytest.fixture
def client_plan():
    from app.api.main import app, get_current_user_ctx
    from app.services.context import default_context

    parcelles = [
        _parcelle_mock("Centrale", id_=1, nb_rangs=5, ordre=1, superficie=6.0),
        _parcelle_mock("Serre", id_=2, nb_rangs=2, ordre=2, pepiniere=True),
        _parcelle_mock("Jamais mesuree", id_=3, ordre=3),
    ]
    occupation = {
        "Centrale": [
            {"culture": "tomate", "variete": "noire de Crimée", "nb_plants": 8.0,
             "type_organe": "reproducteur", "unite": "plants",
             "date_plantation": datetime(2026, 6, 1)},
            {"culture": "poireau", "variete": "", "nb_plants": 12.0,
             "type_organe": "végétatif", "unite": "plants",
             "date_plantation": datetime(2026, 6, 10)},
        ],
    }
    rangs = {
        cle_ligne("Centrale", occupation["Centrale"][0]): 1,
        cle_ligne("Centrale", occupation["Centrale"][1]): 2,
    }
    app.dependency_overrides[get_current_user_ctx] = default_context
    with (
        patch("app.api.main.SessionLocal", return_value=MagicMock()),
        patch("utils.parcelles.get_all_parcelles", return_value=parcelles),
        patch("utils.parcelles.calcul_occupation_parcelles", return_value=occupation),
        patch("app.services.repartition_rangs._rangs_declares_a_installation",
              return_value=rangs),
        patch("app.services.repartition_rangs._lots_en_cours_par_parcelle",
              return_value={"Serre": 3}),
    ):
        from fastapi.testclient import TestClient
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.pop(get_current_user_ctx, None)


def test_us198_ca2_chaque_culture_porte_ses_rangs(client_plan) -> None:
    """CA2 — mode, rangs, quantité par rang, date d'installation, numéros."""
    parcelles = {p["nom"]: p for p in client_plan.get("/plan").json()["parcelles"]}
    cultures = {c["culture"]: c for c in parcelles["Centrale"]["cultures"]}
    assert cultures["tomate"]["mode_implantation"] == MODE_RANG
    assert cultures["tomate"]["rangs"] == 1
    assert cultures["tomate"]["quantite_par_rang"] == 8
    assert cultures["tomate"]["date_installation"] == "2026-06-01"
    assert cultures["tomate"]["numeros_rangs"] == [1]
    assert cultures["poireau"]["numeros_rangs"] == [2, 3]
    assert cultures["poireau"]["quantite_par_rang"] == 6


def test_us198_ca2_chaque_parcelle_porte_sa_disposition(client_plan) -> None:
    """CA2 — La disposition dit les rangs déclarés, occupés, libres et l'écart."""
    parcelles = {p["nom"]: p for p in client_plan.get("/plan").json()["parcelles"]}
    disposition = parcelles["Centrale"]["disposition"]
    assert disposition["rangs_declares"] == 5
    assert disposition["rangs_occupes"] == 3
    assert disposition["rangs_libres"] == 2
    assert disposition["depassement"] == 0
    assert disposition["mode_numerotation"] == NUMEROTATION_ORDRE_INSTALLATION
    assert len(disposition["rangs"]) == 5
    assert parcelles["Serre"]["disposition"]["nb_lots_en_cours"] == 3
    assert parcelles["Jamais mesuree"]["disposition"]["rangs_libres"] is None


def test_us198_ca2_aucun_champ_existant_retire(client_plan) -> None:
    """CA2, CA6 — Les champs servis jusqu'ici le sont toujours, à l'identique."""
    corps = client_plan.get("/plan").json()
    parcelle = corps["parcelles"][0]
    for champ in ("id", "nom", "exposition", "superficie_m2", "abri", "paillage",
                  "nb_rangs", "ordre", "est_pepiniere", "cultures", "occupation_pct",
                  "has_observations", "nb_observations"):
        assert champ in parcelle
    for champ in ("culture", "variete", "nb_plants", "unite", "type_organe",
                  "surface_m2_par_plant", "famille", "phase", "nb_series"):
        assert champ in parcelle["cultures"][0]
    assert corps["total"] == 3
    assert "date_ref_effective" in corps


def test_us198_ca3_totaux_servis_par_le_plan(client_plan) -> None:
    """CA3 — Le bloc de totaux accompagne la liste des parcelles."""
    totaux = client_plan.get("/plan").json()["totaux"]
    assert totaux["superficie_totale_m2"] == 6.0
    assert totaux["rangs_declares"] == 5       # la Serre est une pépinière
    assert totaux["rangs_occupes"] == 3
    assert totaux["parcelles_sans_nb_rangs"] == 1
    assert [e["parcelle"] for e in totaux["rangs_libres_par_parcelle"]] == [
        "Centrale", "Serre", "Jamais mesuree",
    ]

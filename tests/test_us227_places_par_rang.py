"""
tests/test_us227_places_par_rang.py — Places d'un rang et ce qu'il en reste [US-227]

Critères couverts :
- CA1   R10 à R17 dans le module de répartition existant, en lecture seule
- CA2   GET /plan : champs de places par rang, part semée d'un semis en ligne,
        longueur et capacité d'exemple d'un rang libre
- CA3   GET /plan : longueur, largeur déduite, `parcelles_sans_longueur`
- CA4   aucun total de places, aucun pourcentage de remplissage
- CA5   tout est calculé à la date de référence (US-030)
- CA6   aucune lecture supplémentaire : le compte de requêtes ne bouge pas
- CA7   aucun calcul existant ne change (champs d'US-198, occupation, stock)
- CA10  plants, graines, poquets, longueur absente, espacement absent, surface,
        dépassement, semis en ligne partiel / complet / débordant, rang libre
        avec et sans culture de référence, totaux, date passée, pépinière
"""
from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from app.services.context import TenantContext
from app.services.plan import attributs_par_culture
from app.services.repartition_rangs import cle_ligne, repartition_du_plan
from database.models import CultureConfig, Evenement, Parcelle, Potager, User
from utils.parcelles import calcul_occupation_parcelles, get_all_parcelles

DATE_REF = date(2026, 7, 1)
CTX = TenantContext(user_id=1, potager_id=1, role="owner")


# ══════════════════════════════════════════════════════════════════════════════
# Fixtures — un potager mesuré (US-225) et un référentiel espacé (US-226)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def db(test_db):
    test_db.add(User(id=1, email="a@potager.test"))
    test_db.flush()
    test_db.add(Potager(id=1, nom="Jardin", proprietaire_id=1))
    test_db.flush()
    test_db.add_all([
        # `surface_m2` = A × B ÷ 10000, pour que le contrôle d'US-226 / CA3 soit muet.
        CultureConfig(nom="tomate", type_organe_recolte="reproducteur",
                      espacement="50 x 60 cm", surface_m2=0.30),
        CultureConfig(nom="courge", type_organe_recolte="reproducteur",
                      espacement="150 x 200 cm", surface_m2=3.0),
        CultureConfig(nom="carotte", type_organe_recolte="végétatif",
                      espacement="5 x 25 cm", surface_m2=0.0125),
        CultureConfig(nom="radis", type_organe_recolte="végétatif",
                      espacement="4 x 20 cm", surface_m2=0.008),
        # [R11] Sans espacement dans le référentiel : aucune place, jamais une moyenne.
        CultureConfig(nom="laitue", type_organe_recolte="végétatif"),
        CultureConfig(nom="courgette", type_organe_recolte="reproducteur"),
    ])
    test_db.add_all([
        Parcelle(id=1, nom="planche centrale", nom_normalise="planchecentrale",
                 potager_id=1, ordre=1, nb_rangs=5, superficie_m2=6.0, longueur_m=12.0),
        # [R11] Jamais mesurée : aucun rang chiffré, quelles que soient ses cultures.
        Parcelle(id=2, nom="planche est", nom_normalise="plancheest",
                 potager_id=1, ordre=2, nb_rangs=3, superficie_m2=4.0, longueur_m=None),
        Parcelle(id=3, nom="planche ombre", nom_normalise="plancheombre",
                 potager_id=1, ordre=3, nb_rangs=2, superficie_m2=4.5, longueur_m=9.0),
        Parcelle(id=4, nom="serre", nom_normalise="serre", potager_id=1, ordre=4,
                 nb_rangs=2, est_pepiniere=True, longueur_m=6.0),
    ])
    test_db.commit()
    return test_db


def _geste(db, **champs) -> None:
    champs.setdefault("potager_id", 1)
    champs.setdefault("unite", "plants")
    db.add(Evenement(**champs))
    db.commit()


def _repartir(db, date_ref: date = DATE_REF) -> dict:
    """Le chemin exact de GET /plan : occupation, attributs de fiche, répartition."""
    parcelles = get_all_parcelles(db, potager_id=1)
    occupation = calcul_occupation_parcelles(db, date_ref, potager_id=1)
    return repartition_du_plan(
        db, parcelles, occupation, potager_id=1, date_ref=date_ref,
        attributs_culture=attributs_par_culture(db, CTX),
    )


def _rangs(repartition: dict, parcelle: str) -> list[dict]:
    return repartition["dispositions"][parcelle]["rangs"]


def _rang(repartition: dict, parcelle: str, numero: int) -> dict:
    return next(r for r in _rangs(repartition, parcelle) if r["numero"] == numero)


# ══════════════════════════════════════════════════════════════════════════════
# R10, R12, R13 — Les places d'un rang, et ce qui les prend
# ══════════════════════════════════════════════════════════════════════════════

def test_us227_r10_places_d_un_rang_de_tomates(db) -> None:
    """Gherkin 1 — 12 m à 50 cm : 24 places, 9 prises, 15 restantes."""
    _geste(db, type_action="plantation", culture="tomate", quantite=9.0, rang=1,
           parcelle_id=1, date=datetime(2026, 6, 1))
    rang = _rang(_repartir(db), "planche centrale", 1)
    assert rang["espacement_rang_cm"] == 50
    assert rang["places"] == 24
    assert rang["places_prises"] == 9
    assert rang["places_restantes"] == 15
    assert rang["depassement_places"] == 0


def test_us227_places_salade_espacement_notation_a(db) -> None:
    """[US-227] Quatre salades sur 4 m avec « 30 à 30 cm » : neuf places restent."""
    db.add(CultureConfig(nom="salade", type_organe_recolte="végétatif",
                         espacement="30 à 30 cm", surface_m2=0.09))
    db.query(Parcelle).filter(Parcelle.id == 1).update({"longueur_m": 4.0})
    db.commit()
    _geste(db, type_action="plantation", culture="salade", quantite=4.0, rang=1,
           parcelle_id=1, date=datetime(2026, 6, 1))
    repartition = _repartir(db)
    rang = _rang(repartition, "planche centrale", 1)
    assert rang["espacement_rang_cm"] == 30
    assert rang["places"] == 13
    assert rang["places_prises"] == 4
    assert rang["places_restantes"] == 9
    assert rang["depassement_places"] == 0
    assert _rang(repartition, "planche centrale", 2)["capacite_exemple"] == {
        "nombre": 13, "culture": "salade",
    }


def test_us227_r10_places_au_minimum_une(db) -> None:
    """R10 — Une courge à 150 cm sur 1 m de planche : une place, jamais zéro."""
    db.query(Parcelle).filter(Parcelle.id == 1).update({"longueur_m": 1.0})
    db.commit()
    _geste(db, type_action="plantation", culture="courge", quantite=1.0, rang=1,
           parcelle_id=1, date=datetime(2026, 6, 1))
    assert _rang(_repartir(db), "planche centrale", 1)["places"] == 1


def test_us227_r12_des_graines_prennent_des_places(db) -> None:
    """R12 — Les graines comptent comme des individus posés sur le rang."""
    _geste(db, type_action="semis", culture="radis", quantite=40.0, rang=1,
           unite="graines", parcelle_id=1, date=datetime(2026, 6, 1))
    rang = _rang(_repartir(db), "planche centrale", 1)
    assert rang["places"] == 300          # 12 m ÷ 4 cm
    assert rang["places_prises"] == 40
    assert rang["places_restantes"] == 260


def test_us227_r12_un_poquet_occupe_une_place(db) -> None:
    """R12 — Un poquet prend UNE place, quel que soit le nombre de graines dedans."""
    _geste(db, type_action="semis", culture="courge", quantite=5.0, rang=1,
           unite="poquets", parcelle_id=1, date=datetime(2026, 6, 1))
    rang = _rang(_repartir(db), "planche centrale", 1)
    assert rang["places"] == 8            # 12 m ÷ 150 cm
    assert rang["places_prises"] == 5
    assert rang["places_restantes"] == 3


def test_us227_r10_les_rangs_d_une_meme_ligne_portent_la_meme_capacite(db) -> None:
    """R10 — La longueur est celle de la PARCELLE : tous ses rangs ont les mêmes places."""
    # « planté 12 tomates sur 3 rangs » — 36 plants au total, 12 par rang (US-198 / R3).
    _geste(db, type_action="plantation", culture="tomate", quantite=12.0, rang=3,
           parcelle_id=1, date=datetime(2026, 6, 1))
    rangs = [r for r in _rangs(_repartir(db), "planche centrale") if not r["libre"]]
    assert len(rangs) == 3
    assert {r["places"] for r in rangs} == {24}
    assert {r["places_prises"] for r in rangs} == {12}
    assert {r["places_restantes"] for r in rangs} == {12}


# ══════════════════════════════════════════════════════════════════════════════
# R11 — Les trois cas, et seulement les trois, où un rang n'a pas de places
# ══════════════════════════════════════════════════════════════════════════════

def test_us227_r11_parcelle_sans_longueur(db) -> None:
    """Gherkin 3 — Aucune longueur : aucun rang chiffré dans toute la parcelle."""
    _geste(db, type_action="plantation", culture="courgette", quantite=3.0, rang=1,
           parcelle_id=2, date=datetime(2026, 6, 1))
    rang = _rang(_repartir(db), "planche est", 1)
    assert rang["places"] is None
    assert rang["places_prises"] is None
    assert rang["places_restantes"] is None
    assert rang["depassement_places"] is None


def test_us227_r11_culture_sans_espacement(db) -> None:
    """Gherkin 4 — La laitue n'a pas d'espacement : aucune place, aucune moyenne."""
    _geste(db, type_action="plantation", culture="laitue", quantite=20.0, rang=1,
           parcelle_id=1, date=datetime(2026, 6, 1))
    rang = _rang(_repartir(db), "planche centrale", 1)
    assert rang["espacement_rang_cm"] is None
    assert rang["places"] is None
    assert rang["places_prises"] is None


def test_us227_r11_implantation_en_surface(db) -> None:
    """R11 — Un semis en m² n'occupe pas des places : il occupe une surface."""
    _geste(db, type_action="semis", culture="carotte", quantite=2.0, rang=1,
           unite="m2", parcelle_id=1, date=datetime(2026, 6, 1))
    rang = _rang(_repartir(db), "planche centrale", 1)
    assert rang["places"] is None
    assert rang["places_restantes"] is None


def test_us227_r12_une_unite_qui_ne_pose_pas_d_individus_ne_prend_pas_de_place(db) -> None:
    """R12 — Des grammes ne sont pas des pieds : la capacité reste connue, pas ce qui l'occupe."""
    _geste(db, type_action="semis", culture="carotte", quantite=30.0, rang=1,
           unite="g", parcelle_id=1, date=datetime(2026, 6, 1))
    rang = _rang(_repartir(db), "planche centrale", 1)
    assert rang["places"] == 240
    assert rang["places_prises"] is None
    assert rang["places_restantes"] is None


# ══════════════════════════════════════════════════════════════════════════════
# R14 — Le rang surchargé : un signalement, jamais une correction
# ══════════════════════════════════════════════════════════════════════════════

def test_us227_r14_rang_surcharge(db) -> None:
    """Gherkin 2 — 9 m à 40 cm, 26 pieds : 22 places, 0 restante, 4 de dépassement."""
    db.add(CultureConfig(nom="tomate coeur de boeuf", type_organe_recolte="reproducteur",
                         espacement="40 x 50 cm", surface_m2=0.20))
    db.commit()
    _geste(db, type_action="plantation", culture="tomate coeur de boeuf", quantite=26.0,
           rang=1, parcelle_id=3, date=datetime(2026, 6, 1))
    repartition = _repartir(db)
    rang = _rang(repartition, "planche ombre", 1)
    assert rang["places"] == 22
    assert rang["places_prises"] == 22
    assert rang["places_restantes"] == 0
    assert rang["depassement_places"] == 4
    # La quantité déclarée par le jardinier fait foi — rien n'est corrigé.
    cle = cle_ligne("planche ombre", {"culture": "tomate coeur de boeuf", "unite": "plants"})
    assert repartition["lignes"][cle]["quantite_par_rang"] == 26.0


def test_us227_r14_depassement_de_rang_et_de_parcelle_sont_distincts(db) -> None:
    """R14 vs US-198 / R7 — Trop de pieds sur un rang n'est pas trop de rangs occupés."""
    _geste(db, type_action="plantation", culture="tomate", quantite=40.0, rang=1,
           parcelle_id=1, date=datetime(2026, 6, 1))
    repartition = _repartir(db)
    assert _rang(repartition, "planche centrale", 1)["depassement_places"] == 16
    # La parcelle, elle, n'a qu'un rang occupé sur cinq déclarés.
    assert repartition["dispositions"]["planche centrale"]["depassement"] == 0


# ══════════════════════════════════════════════════════════════════════════════
# R15 — Le semis en ligne se mesure en mètres, pas en places
# ══════════════════════════════════════════════════════════════════════════════

def test_us227_r15_semis_en_ligne_partiel(db) -> None:
    """Gherkin 5 — 3 m de carottes sur 9 m : un tiers semé, 6 m restants, aucune place."""
    _geste(db, type_action="semis", culture="carotte", quantite=3.0, rang=1,
           unite="ml", parcelle_id=3, date=datetime(2026, 6, 1))
    rang = _rang(_repartir(db), "planche ombre", 1)
    assert rang["part_semee"] == pytest.approx(0.33, abs=0.01)
    assert rang["metres_restants"] == 6.0
    assert rang["depassement_metres"] == 0.0
    assert rang["places"] is None
    assert rang["places_prises"] is None


def test_us227_r15_semis_en_ligne_complet(db) -> None:
    """R15 — Un rang semé de bout en bout : part semée 1, rien qui reste."""
    _geste(db, type_action="semis", culture="carotte", quantite=9.0, rang=1,
           unite="ml", parcelle_id=3, date=datetime(2026, 6, 1))
    rang = _rang(_repartir(db), "planche ombre", 1)
    assert rang["part_semee"] == 1.0
    assert rang["metres_restants"] == 0.0
    assert rang["depassement_metres"] == 0.0


def test_us227_r15_semis_en_ligne_debordant(db) -> None:
    """R15 — Plus long que le rang : part plafonnée à 1, dépassement EN MÈTRES."""
    _geste(db, type_action="semis", culture="carotte", quantite=12.0, rang=1,
           unite="ml", parcelle_id=3, date=datetime(2026, 6, 1))
    rang = _rang(_repartir(db), "planche ombre", 1)
    assert rang["part_semee"] == 1.0
    assert rang["metres_restants"] == 0.0
    assert rang["depassement_metres"] == 3.0
    assert rang["depassement_places"] is None


def test_us227_r15_semis_en_ligne_sans_longueur(db) -> None:
    """R15 — Sans longueur de planche, une part semée n'a pas de sens : None."""
    _geste(db, type_action="semis", culture="carotte", quantite=3.0, rang=1,
           unite="ml", parcelle_id=2, date=datetime(2026, 6, 1))
    rang = _rang(_repartir(db), "planche est", 1)
    assert rang["part_semee"] is None
    assert rang["metres_restants"] is None


# ══════════════════════════════════════════════════════════════════════════════
# R16 — Le rang libre porte sa longueur, pas des places
# ══════════════════════════════════════════════════════════════════════════════

def test_us227_r16_rang_libre_avec_capacite_d_exemple(db) -> None:
    """Gherkin 6 — Rang libre : sa longueur, et 24 tomates en exemple, nommées."""
    _geste(db, type_action="plantation", culture="tomate", quantite=9.0, rang=1,
           parcelle_id=1, date=datetime(2026, 6, 1))
    rang = _rang(_repartir(db), "planche centrale", 5)
    assert rang["libre"] is True
    assert rang["longueur_m"] == 12.0
    assert rang["capacite_exemple"] == {"nombre": 24, "culture": "tomate"}
    assert "places" not in rang
    assert "places_restantes" not in rang


def test_us227_r16_rang_libre_sans_culture_de_reference(db) -> None:
    """R16 — Aucune culture d'espacement connu dans la parcelle : la longueur seule."""
    _geste(db, type_action="plantation", culture="laitue", quantite=6.0, rang=1,
           parcelle_id=1, date=datetime(2026, 6, 1))
    rang = _rang(_repartir(db), "planche centrale", 5)
    assert rang["longueur_m"] == 12.0
    assert rang["capacite_exemple"] is None


def test_us227_r16_rang_libre_d_une_parcelle_sans_longueur(db) -> None:
    """R16 — Sans longueur, un rang libre ne porte ni longueur ni exemple."""
    rang = _rang(_repartir(db), "planche est", 1)
    assert rang["libre"] is True
    assert rang["longueur_m"] is None
    assert rang["capacite_exemple"] is None


def test_us227_r16_l_exemple_vient_d_une_culture_reellement_presente(db) -> None:
    """R16 / A26 — L'exemple est pris sur la première culture installée, jamais un défaut."""
    _geste(db, type_action="semis", culture="courge", quantite=2.0, rang=1,
           unite="poquets", parcelle_id=1, date=datetime(2026, 6, 1))
    _geste(db, type_action="plantation", culture="tomate", quantite=4.0, rang=1,
           parcelle_id=1, date=datetime(2026, 6, 20))
    rang = _rang(_repartir(db), "planche centrale", 5)
    assert rang["capacite_exemple"] == {"nombre": 8, "culture": "courge"}


# ══════════════════════════════════════════════════════════════════════════════
# R8, R17, CA4 — Pépinière, totaux, et ce qui n'existera jamais
# ══════════════════════════════════════════════════════════════════════════════

def test_us227_r8_une_pepiniere_n_a_pas_de_places(db) -> None:
    """CA10 — Une pépinière abrite des lots, pas des rangs au cordeau : aucune place."""
    _geste(db, type_action="semis", culture="tomate", quantite=30.0, rang=1,
           unite="graines", parcelle_id=4, date=datetime(2026, 6, 1))
    _geste(db, type_action="plantation", culture="tomate", quantite=6.0, rang=1,
           parcelle_id=4, date=datetime(2026, 6, 2))
    rangs = _rangs(_repartir(db), "serre")
    assert all(r.get("places") is None for r in rangs)
    assert all(r.get("capacite_exemple") is None for r in rangs if r["libre"])
    # Le semis de pépinière n'est toujours pas une ligne du plan (US-198 / R8).
    assert [r["numero"] for r in rangs if not r["libre"]] == [1]


def test_us227_r17_totaux_comptent_les_parcelles_sans_longueur(db) -> None:
    """R17 — Le bloc de totaux gagne le nombre de parcelles sans longueur."""
    assert _repartir(db)["totaux"]["parcelles_sans_longueur"] == 1


def test_us227_ca4_aucun_total_de_places_ni_pourcentage_de_remplissage(db) -> None:
    """CA4 / RT13 — Une place est une capacité de rang, jamais un second taux."""
    _geste(db, type_action="plantation", culture="tomate", quantite=9.0, rang=1,
           parcelle_id=1, date=datetime(2026, 6, 1))
    totaux = _repartir(db)["totaux"]
    assert [c for c in totaux if "place" in c] == []
    assert [c for c in totaux if "remplissage" in c] == []


def test_us227_ca4_aucune_parcelle_ne_porte_de_total_de_places(db) -> None:
    """CA4 — Ni par parcelle : la disposition n'agrège aucune place."""
    _geste(db, type_action="plantation", culture="tomate", quantite=9.0, rang=1,
           parcelle_id=1, date=datetime(2026, 6, 1))
    disposition = _repartir(db)["dispositions"]["planche centrale"]
    assert [c for c in disposition if "place" in c] == []


# ══════════════════════════════════════════════════════════════════════════════
# CA5, CA6, CA7 — Date de référence, coût de lecture, non-régression
# ══════════════════════════════════════════════════════════════════════════════

def test_us227_ca5_a_une_date_passee_les_places_suivent_l_occupation(db) -> None:
    """CA5 — Une plantation postérieure à la date de référence ne prend aucune place."""
    _geste(db, type_action="plantation", culture="tomate", quantite=9.0, rang=1,
           parcelle_id=1, date=datetime(2026, 6, 1))
    _geste(db, type_action="plantation", culture="courge", quantite=4.0, rang=1,
           parcelle_id=1, date=datetime(2026, 8, 15))
    rangs = [r for r in _rangs(_repartir(db, DATE_REF), "planche centrale") if not r["libre"]]
    assert len(rangs) == 1
    assert rangs[0]["culture"] == "tomate"
    assert rangs[0]["places_prises"] == 9


def test_us227_ca6_aucune_lecture_supplementaire(db) -> None:
    """CA6 — Le calcul se greffe sur la lecture d'US-198 : même compte de requêtes,
    et indépendant de la taille du plan."""
    def _lectures(attributs) -> int:
        parcelles = get_all_parcelles(db, potager_id=1)
        occupation = calcul_occupation_parcelles(db, DATE_REF, potager_id=1)
        compteur = {"n": 0}
        vraie_query = db.query

        def _compter(*args, **kwargs):
            compteur["n"] += 1
            return vraie_query(*args, **kwargs)

        with patch.object(db, "query", side_effect=_compter):
            repartition_du_plan(db, parcelles, occupation, potager_id=1,
                                date_ref=DATE_REF, attributs_culture=attributs)
        return compteur["n"]

    _geste(db, type_action="plantation", culture="tomate", quantite=9.0, rang=1,
           parcelle_id=1, date=datetime(2026, 6, 1))
    attributs = attributs_par_culture(db, CTX)
    sans_places = _lectures(None)
    assert _lectures(attributs) == sans_places

    for culture, jour in (("radis", 2), ("laitue", 3), ("carotte", 4)):
        _geste(db, type_action="plantation", culture=culture, quantite=5.0, rang=1,
               parcelle_id=3, date=datetime(2026, 6, jour))
    assert _lectures(attributs) == sans_places


def test_us227_ca1_ca7_l_occupation_n_est_ni_recalculee_ni_modifiee(db) -> None:
    """CA1, CA7 — Lecture seule : l'occupation passée en entrée ressort intacte."""
    _geste(db, type_action="plantation", culture="tomate", quantite=9.0, rang=1,
           parcelle_id=1, date=datetime(2026, 6, 1))
    occupation = calcul_occupation_parcelles(db, DATE_REF, potager_id=1)
    avant = {k: [dict(e) for e in v] for k, v in occupation.items()}
    repartition_du_plan(db, get_all_parcelles(db, potager_id=1), occupation,
                        potager_id=1, date_ref=DATE_REF,
                        attributs_culture=attributs_par_culture(db, CTX))
    assert {k: [dict(e) for e in v] for k, v in occupation.items()} == avant


def test_us227_ca7_les_champs_d_us198_ne_changent_pas(db) -> None:
    """CA7 — Mêmes rangs, mêmes quantités, mêmes totaux avec et sans les places."""
    _geste(db, type_action="plantation", culture="tomate", quantite=9.0, rang=2,
           parcelle_id=1, date=datetime(2026, 6, 1))
    parcelles = get_all_parcelles(db, potager_id=1)
    occupation = calcul_occupation_parcelles(db, DATE_REF, potager_id=1)
    commun = dict(potager_id=1, date_ref=DATE_REF)
    sans = repartition_du_plan(db, parcelles, occupation, **commun)
    avec = repartition_du_plan(db, parcelles, occupation,
                               attributs_culture=attributs_par_culture(db, CTX), **commun)

    assert avec["lignes"] == sans["lignes"]
    conserves = ("numero", "libre", "culture", "variete", "unite")
    for nom, disposition in avec["dispositions"].items():
        temoin = sans["dispositions"][nom]
        assert {c: v for c, v in disposition.items() if c != "rangs"} == \
               {c: v for c, v in temoin.items() if c != "rangs"}
        for rang, rang_temoin in zip(disposition["rangs"], temoin["rangs"]):
            assert {c: rang[c] for c in conserves} == {c: rang_temoin[c] for c in conserves}
    assert {c: v for c, v in avec["totaux"].items() if c != "parcelles_sans_longueur"} == \
           {c: v for c, v in sans["totaux"].items() if c != "parcelles_sans_longueur"}


# ══════════════════════════════════════════════════════════════════════════════
# CA2, CA3 — Ce que GET /plan sert réellement
# ══════════════════════════════════════════════════════════════════════════════

def _parcelle_mock(nom: str, *, id_: int, nb_rangs=None, ordre=0, pepiniere=False,
                   superficie=None, longueur=None):
    p = MagicMock(spec=Parcelle)
    p.id = id_
    p.nom = nom
    p.exposition = None
    p.superficie_m2 = superficie
    p.abri = None
    p.paillage = None
    p.nb_rangs = nb_rangs
    p.longueur_m = longueur
    p.ordre = ordre
    p.est_pepiniere = pepiniere
    p.actif = True
    return p


@pytest.fixture
def client_plan():
    from app.api.main import app, get_current_user_ctx
    from app.services.context import default_context

    parcelles = [
        _parcelle_mock("Centrale", id_=1, nb_rangs=3, ordre=1, superficie=6.0, longueur=12.0),
        _parcelle_mock("Jamais mesuree", id_=2, nb_rangs=2, ordre=2, superficie=4.0),
    ]
    occupation = {
        "Centrale": [
            {"culture": "tomate", "variete": "noire de Crimée", "nb_plants": 9.0,
             "type_organe": "reproducteur", "unite": "plants",
             "date_plantation": datetime(2026, 6, 1)},
            {"culture": "carotte", "variete": "", "nb_plants": 3.0,
             "type_organe": "végétatif", "unite": "ml", "type_action": "semis",
             "date_plantation": datetime(2026, 6, 10)},
        ],
        "Jamais mesuree": [
            {"culture": "courgette", "variete": "", "nb_plants": 3.0,
             "type_organe": "reproducteur", "unite": "plants",
             "date_plantation": datetime(2026, 6, 5)},
        ],
    }
    fiches = [
        MagicMock(nom="tomate", surface_m2=0.30, espacement="50 x 60 cm", potager_id=None),
        MagicMock(nom="carotte", surface_m2=0.0125, espacement="5 x 25 cm", potager_id=None),
        MagicMock(nom="courgette", surface_m2=1.0, espacement=None, potager_id=None),
    ]
    rangs = {
        cle_ligne("Centrale", occupation["Centrale"][0]): 1,
        cle_ligne("Centrale", occupation["Centrale"][1]): 1,
        cle_ligne("Jamais mesuree", occupation["Jamais mesuree"][0]): 1,
    }
    app.dependency_overrides[get_current_user_ctx] = default_context
    with (
        patch("app.api.main.SessionLocal", return_value=MagicMock()),
        patch("utils.parcelles.get_all_parcelles", return_value=parcelles),
        patch("utils.parcelles.calcul_occupation_parcelles", return_value=occupation),
        patch("app.services.plan.lister_cultures_config", return_value=fiches),
        patch("app.services.repartition_rangs._rangs_declares_a_installation",
              return_value=rangs),
        patch("app.services.repartition_rangs._lots_en_cours_par_parcelle",
              return_value={}),
    ):
        from fastapi.testclient import TestClient
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.pop(get_current_user_ctx, None)


def test_us227_ca2_chaque_rang_occupe_porte_ses_places(client_plan) -> None:
    """CA2 — Places, prises, restantes, dépassement et espacement, par rang."""
    parcelles = {p["nom"]: p for p in client_plan.get("/plan").json()["parcelles"]}
    rang = parcelles["Centrale"]["disposition"]["rangs"][0]
    assert rang["culture"] == "tomate"
    assert rang["espacement_rang_cm"] == 50
    assert rang["places"] == 24
    assert rang["places_prises"] == 9
    assert rang["places_restantes"] == 15
    assert rang["depassement_places"] == 0


def test_us227_ca2_un_semis_en_ligne_porte_sa_part_semee(client_plan) -> None:
    """CA2 — Un semis en `ml` porte part semée et mètres restants, pas des places."""
    parcelles = {p["nom"]: p for p in client_plan.get("/plan").json()["parcelles"]}
    rang = parcelles["Centrale"]["disposition"]["rangs"][1]
    assert rang["culture"] == "carotte"
    assert rang["places"] is None
    assert rang["part_semee"] == pytest.approx(0.25)
    assert rang["metres_restants"] == 9.0


def test_us227_ca2_un_rang_libre_porte_sa_longueur_et_son_exemple(client_plan) -> None:
    """CA2 — Le rang libre servi par l'API : longueur et capacité d'exemple nommée."""
    parcelles = {p["nom"]: p for p in client_plan.get("/plan").json()["parcelles"]}
    libre = parcelles["Centrale"]["disposition"]["rangs"][2]
    assert libre["libre"] is True
    assert libre["longueur_m"] == 12.0
    assert libre["capacite_exemple"] == {"nombre": 24, "culture": "tomate"}


def test_us227_ca2_une_parcelle_sans_longueur_n_a_aucun_rang_chiffre(client_plan) -> None:
    """CA2 / R11 — Aucun rang chiffré, quelles que soient ses cultures."""
    parcelles = {p["nom"]: p for p in client_plan.get("/plan").json()["parcelles"]}
    for rang in parcelles["Jamais mesuree"]["disposition"]["rangs"]:
        assert rang.get("places") is None
        assert rang.get("capacite_exemple") is None


def test_us227_ca3_chaque_parcelle_porte_longueur_et_largeur_deduite(client_plan) -> None:
    """CA3 — La longueur déclarée (US-225) et la largeur qui s'en déduit."""
    parcelles = {p["nom"]: p for p in client_plan.get("/plan").json()["parcelles"]}
    centrale = parcelles["Centrale"]
    assert centrale["longueur_m"] == 12.0
    assert centrale["largeur_m"] == 0.5
    assert centrale["largeur_deduite"] is True
    assert centrale["largeur_incoherente"] is False
    assert parcelles["Jamais mesuree"]["longueur_m"] is None
    assert parcelles["Jamais mesuree"]["largeur_m"] is None


def test_us227_ca3_les_totaux_comptent_les_parcelles_sans_longueur(client_plan) -> None:
    """CA3 — `parcelles_sans_longueur` servi par GET /plan."""
    assert client_plan.get("/plan").json()["totaux"]["parcelles_sans_longueur"] == 1


def test_us227_ca4_la_reponse_n_expose_aucun_total_de_places(client_plan) -> None:
    """CA4 — Sur la forme même de la réponse : aucun total, aucun pourcentage."""
    corps = client_plan.get("/plan").json()
    assert [c for c in corps["totaux"] if "place" in c] == []
    for parcelle in corps["parcelles"]:
        assert [c for c in parcelle if "place" in c or "remplissage" in c] == []
        assert [c for c in parcelle["disposition"] if "place" in c] == []


def test_us227_ca7_aucun_champ_existant_retire(client_plan) -> None:
    """CA7 — Les champs d'US-198 et d'US-024 sont tous encore là, inchangés."""
    parcelles = {p["nom"]: p for p in client_plan.get("/plan").json()["parcelles"]}
    centrale = parcelles["Centrale"]
    # 9 × 0,30 m² + 3 × 0,0125 m² sur 6 m² — le calcul d'US-037 est intact.
    assert centrale["occupation_pct"] == 46
    disposition = centrale["disposition"]
    assert disposition["rangs_declares"] == 3
    assert disposition["rangs_occupes"] == 2
    assert disposition["rangs_libres"] == 1
    culture = centrale["cultures"][0]
    assert culture["rangs"] == 1
    assert culture["quantite_par_rang"] == 9.0
    assert culture["espacement_rang_cm"] == 50

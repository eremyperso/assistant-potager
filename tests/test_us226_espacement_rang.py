"""
tests/test_us226_espacement_rang.py — Espacement sur le rang d'une culture [US-226]

Critères couverts :
- CA1  toutes les formes de la chaîne `A × B cm` ; c'est A qui est retenu
- CA2  valeur unique lue comme l'espacement sur le rang ; illisible = « non renseigné »
- CA3  contrôle de cohérence par surface_m2, journalisé une fois par lecture
- CA4  GET /plan expose espacement_rang_cm ; aucun affichage existant ne change
- CA5  aucune lecture supplémentaire : branchée sur la lecture déjà faite
- CA6  une fiche personnalisée au potager prime sur la fiche globale
- CA7  la variété n'a pas d'espacement propre
- CA8  tools/controler_espacements.py liste les cultures en usage sans espacement
- CA9  fiches de domaine et de corpus mises à jour
- CA10 (transverse) : les valeurs réelles de la migration v13 rejouées une à une
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services import plan as svc_plan
from app.services.context import TenantContext
from app.services.espacement_rang import (
    ESPACEMENT_MAX_CM,
    ESPACEMENT_MIN_CM,
    _lire,
    espacement_rang_cm,
)
from database.models import CultureConfig, Potager, User

RACINE = Path(__file__).resolve().parent.parent
CTX = TenantContext(user_id=1, potager_id=1, role="owner")


@pytest.fixture
def db(test_db):
    test_db.add(User(id=1, email="a@potager.test"))
    test_db.flush()
    test_db.add(Potager(id=1, nom="Jardin", proprietaire_id=1))
    test_db.flush()
    test_db.add_all([
        CultureConfig(id=1, nom="potimarron", type_organe_recolte="reproducteur",
                      espacement="110 × 135 cm", surface_m2=1.485),
        CultureConfig(id=2, nom="tomate", type_organe_recolte="reproducteur",
                      espacement="50 cm", surface_m2=None),
        CultureConfig(id=3, nom="laitue", type_organe_recolte="végétatif",
                      espacement=None, surface_m2=0.09),
    ])
    test_db.commit()
    return test_db


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — Toutes les formes de la chaîne, et c'est A qui est retenu
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize(
    "chaine, attendu",
    [
        ("110 × 135 cm", 110),
        ("110 x 135 cm", 110),
        ("110×135", 110),
        ("110x135cm", 110),
        ("110 - 135 cm", 135 and 110),
        ("110-135", 110),
        ("  110  ×  135  CM  ", 110),
        ("110 * 135 cm", 110),
        ("30,5 × 40 cm", 31),     # virgule décimale, arrondie à l'entier
        ("30.5 x 40 cm", 31),
        ("40 × 60 centimètres", 40),
        ("30 à 30 cm", 30),
        ("40 à 60 cm", 40),
        ("110 a 135 cm", 110),
        ("  30,5  À  40  CM  ", 31),
        ("30.5 à 40 centimètres", 31),
    ],
)
def test_us226_ca1_lecture_de_la_chaine(chaine: str, attendu: int) -> None:
    """CA1 — `A × B cm` sous toutes ses formes : A est l'espacement SUR LE RANG."""
    assert espacement_rang_cm(chaine) == attendu


def test_us226_ca1_le_second_nombre_n_est_jamais_retenu() -> None:
    """CA1 — B est l'écart ENTRE rangs : il ne sert qu'au contrôle, jamais de valeur."""
    assert espacement_rang_cm("110 × 135 cm") != 135


@pytest.mark.parametrize(
    "chaine, attendu",
    [
        ("30 à 30 cm", (30.0, 30.0)),
        ("50 à 60 cm", (50.0, 60.0)),
        ("110 à 135 cm", (110.0, 135.0)),
        ("30,5 a 40 cm", (30.5, 40.0)),
        ("30\u00a0à\u00a030 cm", (30.0, 30.0)),
    ],
)
def test_us226_lecture_deux_distances_notation_a(chaine, attendu) -> None:
    """[US-226] La notation du référentiel conserve les deux distances."""
    assert _lire(chaine) == attendu


def test_us226_notation_a_controle_aussi_la_surface(caplog) -> None:
    """[US-226] Le second nombre sert toujours au contrôle de cohérence."""
    with caplog.at_level(logging.WARNING, logger="potager"):
        assert espacement_rang_cm("50 à 60 cm", surface_m2=0.3) == 50
        assert not caplog.records
        assert espacement_rang_cm("50 à 60 cm", surface_m2=0.1) == 50
    assert len(caplog.records) == 1


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — Valeur unique, et ce qui n'est pas lisible
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("chaine, attendu", [("50 cm", 50), ("50", 50), ("  50  ", 50)])
def test_us226_ca2_valeur_unique(chaine: str, attendu: int) -> None:
    """CA2 — Une seule valeur est l'espacement sur le rang."""
    assert espacement_rang_cm(chaine) == attendu


@pytest.mark.parametrize(
    "chaine",
    [
        None, "", "   ", "cm", "large", "espacement moyen", "serré",
        "0 cm",                 # zéro n'est pas un espacement
        "0,5 cm",               # arrondi à 0 : hors bornes
        "401 cm", "1000 × 2000 cm",
        "-50 cm",               # un espacement ne se compte pas à l'envers
        "environ 40 cm",        # la convention n'est pas respectée : on ne devine pas
        "entre 40 et 60 cm", "40 a cm", "a 60 cm", "40abc60 cm",
        "0 à 30 cm", "401 à 500 cm",
    ],
)
def test_us226_ca2_illisible_donne_non_renseigne(chaine) -> None:
    """CA2 — Vide, non numérique ou hors bornes : « non renseigné », jamais zéro."""
    assert espacement_rang_cm(chaine) is None


def test_us226_ca2_bornes() -> None:
    """CA2 — Les bornes sont 1 à 400 cm, incluses."""
    assert (ESPACEMENT_MIN_CM, ESPACEMENT_MAX_CM) == (1, 400)
    assert espacement_rang_cm("1 cm") == 1
    assert espacement_rang_cm("400 cm") == 400


def test_us226_ca2_aucune_valeur_de_repli_depuis_la_surface() -> None:
    """CA2 — Une surface au sol seule ne donne AUCUN espacement sur le rang."""
    assert espacement_rang_cm(None, surface_m2=1.485, culture="potimarron") is None


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — Contrôle de cohérence par la surface au sol
# ═════════════════════════════════════════════════════════════════════════════

def test_us226_ca3_coherent_ne_journalise_rien(caplog) -> None:
    """CA3 — 110 × 135 ÷ 10000 = 1,485 m² : la fiche dit vrai, rien à signaler."""
    with caplog.at_level(logging.WARNING, logger="potager"):
        assert espacement_rang_cm("110 × 135 cm", surface_m2=1.485, culture="potimarron") == 110
    assert "espacement incohérent" not in caplog.text


def test_us226_ca3_incoherent_journalise_mais_retient(caplog) -> None:
    """CA3 — Gherkin : « 150 × 200 cm » contre 0,5 m² — retenu, et signalé."""
    with caplog.at_level(logging.WARNING, logger="potager"):
        valeur = espacement_rang_cm("150 × 200 cm", surface_m2=0.5, culture="courge")
    assert valeur == 150                      # la valeur est retenue quand même
    assert "espacement incohérent" in caplog.text
    assert "courge" in caplog.text


def test_us226_ca3_tolerance_de_dix_pour_cent(caplog) -> None:
    """CA3 — 10 % d'écart passent ; au-delà, l'anomalie est journalisée."""
    with caplog.at_level(logging.WARNING, logger="potager"):
        # 100 × 120 ÷ 10000 = 1,200 m² — la fiche annonce 1,25 (4 % d'écart)
        espacement_rang_cm("100 × 120 cm", surface_m2=1.25, culture="patisson")
    assert "espacement incohérent" not in caplog.text


def test_us226_ca3_une_seule_ligne_par_culture_et_par_lecture(caplog) -> None:
    """CA3 — Une anomalie de référentiel ne s'écrit qu'une fois par lecture."""
    journal: set = set()
    with caplog.at_level(logging.WARNING, logger="potager"):
        for _ in range(5):
            espacement_rang_cm("150 × 200 cm", surface_m2=0.5,
                               culture="courge", journal=journal)
    assert caplog.text.count("espacement incohérent") == 1


def test_us226_ca3_une_surface_absente_ne_declenche_aucun_controle(caplog) -> None:
    """CA3 — Sans surface, il n'y a rien à comparer : ni alerte, ni refus."""
    with caplog.at_level(logging.WARNING, logger="potager"):
        assert espacement_rang_cm("150 × 200 cm", surface_m2=None, culture="courge") == 150
    assert "espacement incohérent" not in caplog.text


# ═════════════════════════════════════════════════════════════════════════════
# CA10 — Les valeurs réelles de la migration v13, rejouées une à une
# ═════════════════════════════════════════════════════════════════════════════

def _entrees_de_la_v13() -> list[tuple[str, str, float]]:
    """Lit `migrations/migration_v13.sql` plutôt que de recopier ses valeurs.

    Recopier aurait fait diverger le test du référentiel à la première
    correction : c'est la migration qui fait foi, ici comme ailleurs.
    """
    sql = (RACINE / "migrations" / "migration_v13.sql").read_text(encoding="utf-8")
    motif = re.compile(
        r"'([^']+)'\s*,\s*'[^']*'\s*,\s*'((?:\d[^']*?))'\s*,\s*([\d.]+)"
    )
    return [(m.group(1), m.group(2), float(m.group(3))) for m in motif.finditer(sql)]


def test_us226_ca10_le_corpus_de_la_v13_est_bien_lu() -> None:
    """CA10 — Chaque entrée de la v13 : A lisible, et `A × B ÷ 10000` = surface."""
    entrees = _entrees_de_la_v13()
    assert len(entrees) >= 4, "corpus v13 tronqué — la vérification ne vaudrait plus rien"
    for culture, chaine, surface in entrees:
        valeur = espacement_rang_cm(chaine, surface_m2=surface, culture=culture)
        assert valeur is not None, f"{culture} : espacement illisible ({chaine!r})"
        assert ESPACEMENT_MIN_CM <= valeur <= ESPACEMENT_MAX_CM, culture


def test_us226_ca10_la_convention_a_inferieur_ou_egal_a_b() -> None:
    """CA10 — La convention `A ≤ B` tient sur toutes les entrées de la v13."""
    from app.services.espacement_rang import _lire

    for culture, chaine, _surface in _entrees_de_la_v13():
        sur_le_rang, entre_rangs = _lire(chaine)
        if entre_rangs is not None:
            assert sur_le_rang <= entre_rangs, f"{culture} : convention A ≤ B violée"


# ═════════════════════════════════════════════════════════════════════════════
# CA5 / CA6 / CA7 — La lecture unique, la fiche personnalisée, la variété
# ═════════════════════════════════════════════════════════════════════════════

def test_us226_ca5_une_seule_lecture_de_culture_config(db) -> None:
    """CA5 — La dérivation ne coûte aucune requête : elle se greffe sur la lecture."""
    appels = {"n": 0}
    vraie = svc_plan.lister_cultures_config

    def _compter(session, ctx):
        appels["n"] += 1
        return vraie(session, ctx)

    with patch.object(svc_plan, "lister_cultures_config", _compter):
        index = svc_plan.attributs_par_culture(db, CTX)
    assert appels["n"] == 1
    # Surface ET espacement rendus par cette unique lecture.
    assert index["potimarron"]["espacement_rang_cm"] == 110
    assert index["potimarron"]["surface_m2"] == 1.485


def test_us226_ca5_le_nombre_de_lectures_ne_depend_pas_du_nombre_de_cultures(db) -> None:
    """CA5 — Jamais une requête par culture : dix fiches se lisent comme trois."""
    for n in range(10):
        db.add(CultureConfig(id=100 + n, nom=f"culture {n}",
                             type_organe_recolte="végétatif", espacement="40 × 60 cm"))
    db.commit()

    appels = {"n": 0}
    vraie = svc_plan.lister_cultures_config

    def _compter(session, ctx):
        appels["n"] += 1
        return vraie(session, ctx)

    with patch.object(svc_plan, "lister_cultures_config", _compter):
        index = svc_plan.attributs_par_culture(db, CTX)
    assert appels["n"] == 1
    assert len(index) == 13


@pytest.mark.parametrize("globale_d_abord", [True, False])
def test_us226_ca6_la_fiche_personnalisee_prime(db, globale_d_abord: bool) -> None:
    """CA6 — Gherkin : le potager a personnalisé la tomate — c'est SA fiche qui parle.

    Les deux fiches sont servies directement à `attributs_par_culture` : le
    modèle SQLAlchemy déclare `culture_config.nom` unique, ce que la base de
    production ne fait pas (migration v5 : un simple index), et deux fiches de
    même nom ne peuvent donc pas coexister dans la base SQLite des tests. C'est
    bien l'arbitrage entre les deux qui est vérifié ici, dans les deux ordres de
    lecture possibles — l'ordre ne doit jamais décider à la place de la règle.
    """
    globale = CultureConfig(nom="tomate", type_organe_recolte="reproducteur",
                            espacement="50 × 70 cm", potager_id=None)
    propre = CultureConfig(nom="tomate", type_organe_recolte="reproducteur",
                           espacement="40 × 60 cm", potager_id=1)
    fiches = [globale, propre] if globale_d_abord else [propre, globale]
    with patch.object(svc_plan, "lister_cultures_config", return_value=fiches):
        index = svc_plan.attributs_par_culture(db, CTX)
    assert index["tomate"]["espacement_rang_cm"] == 40
    assert index["tomate"]["personnalisee"] is True


def test_us226_ca6_la_fiche_globale_sert_quand_rien_n_est_personnalise(db) -> None:
    """CA6 — Sans personnalisation, la fiche partagée reste celle qu'on lit."""
    index = svc_plan.attributs_par_culture(db, CTX)
    assert index["tomate"]["espacement_rang_cm"] == 50
    assert index["tomate"]["personnalisee"] is False


def test_us226_ca7_la_variete_partage_l_espacement_de_sa_culture(db) -> None:
    """CA7 — L'index est tenu par CULTURE : aucune variété n'y a d'entrée propre.

    Une tomate cerise et une tomate cœur de bœuf lisent donc le même espacement,
    sauf si la variété existe comme fiche culture à part entière — ce que le
    modèle permet déjà, et que ce test montre plutôt qu'il ne l'invente.
    """
    index = svc_plan.attributs_par_culture(db, CTX)
    assert "tomate cerise" not in index
    db.add(CultureConfig(id=60, nom="tomate cerise", type_organe_recolte="reproducteur",
                         espacement="30 × 50 cm"))
    db.commit()
    index = svc_plan.attributs_par_culture(db, CTX)
    assert index["tomate cerise"]["espacement_rang_cm"] == 30
    assert index["tomate"]["espacement_rang_cm"] == 50


def test_us226_ca4_la_chaine_d_origine_reste_exposee(db) -> None:
    """CA4 — La chaîne du référentiel est toujours là : aucun affichage ne change."""
    index = svc_plan.attributs_par_culture(db, CTX)
    assert index["potimarron"]["espacement"] == "110 × 135 cm"
    # L'index historique par surface rend exactement ce qu'il rendait.
    assert svc_plan.surface_par_culture(db, CTX)["potimarron"] == 1.485
    assert svc_plan.surface_par_culture(db, CTX)["tomate"] == 0.0


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — GET /plan
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def client_plan():
    from app.api.main import app, get_current_user_ctx
    from app.services.context import default_context
    from database.models import Parcelle

    parcelle = MagicMock(spec=Parcelle)
    parcelle.id = 1
    parcelle.nom = "Centrale"
    parcelle.exposition = None
    parcelle.superficie_m2 = 12.0
    parcelle.abri = None
    parcelle.paillage = None
    parcelle.nb_rangs = 4
    parcelle.longueur_m = 12.0
    parcelle.ordre = 1
    parcelle.est_pepiniere = False
    parcelle.actif = True

    occupation = {
        "Centrale": [
            {"culture": "potimarron", "variete": "", "nb_plants": 3.0,
             "type_organe": "reproducteur", "unite": "plants"},
            {"culture": "laitue", "variete": "", "nb_plants": 12.0,
             "type_organe": "végétatif", "unite": "plants"},
        ],
    }
    attributs = {
        "potimarron": {"surface_m2": 1.485, "espacement": "110 × 135 cm",
                       "espacement_rang_cm": 110, "personnalisee": False},
        "laitue": {"surface_m2": 0.09, "espacement": None,
                   "espacement_rang_cm": None, "personnalisee": False},
    }
    app.dependency_overrides[get_current_user_ctx] = default_context
    with (
        patch("app.api.main.SessionLocal", return_value=MagicMock()),
        patch("utils.parcelles.get_all_parcelles", return_value=[parcelle]),
        patch("utils.parcelles.calcul_occupation_parcelles", return_value=occupation),
        patch("app.services.plan.attributs_par_culture", return_value=attributs),
    ):
        from fastapi.testclient import TestClient
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.pop(get_current_user_ctx, None)


def test_us226_ca4_plan_expose_l_espacement_derive(client_plan) -> None:
    """CA4 — Chaque ligne de culture porte espacement_rang_cm, nullable."""
    cultures = client_plan.get("/plan").json()["parcelles"][0]["cultures"]
    par_nom = {c["culture"]: c for c in cultures}
    assert par_nom["potimarron"]["espacement_rang_cm"] == 110
    # Référentiel muet : « non renseigné », et l'écran le dira (RT2).
    assert par_nom["laitue"]["espacement_rang_cm"] is None


def test_us226_ca4_aucun_champ_existant_retire(client_plan) -> None:
    """CA4 — Aucun affichage existant ne change : la surface au pied est intacte."""
    culture = client_plan.get("/plan").json()["parcelles"][0]["cultures"][0]
    for champ in ("culture", "variete", "nb_plants", "unite", "type_organe",
                  "surface_m2_par_plant", "famille", "nb_observations",
                  "mode_implantation", "rangs", "quantite_par_rang"):
        assert champ in culture
    assert culture["surface_m2_par_plant"] == 1.485


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — L'outil de contrôle
# ═════════════════════════════════════════════════════════════════════════════

def test_us226_ca8_l_outil_ne_liste_que_les_cultures_en_usage(db) -> None:
    """CA8 — Le rapport porte sur ce qui pousse, pas sur les 300 fiches du catalogue."""
    from datetime import datetime

    from database.models import Evenement
    from tools import controler_espacements as outil

    db.add_all([
        Evenement(id=1, culture="laitue", type_action="plantation",
                  date=datetime(2026, 4, 1), potager_id=1),
        Evenement(id=2, culture="potimarron", type_action="plantation",
                  date=datetime(2026, 4, 1), potager_id=1),
    ])
    db.commit()

    manquantes, incoherentes, lisibles = outil.analyser(db, potager_id=1)
    noms_manquants = {c for c, _brut, _sans in manquantes}
    assert "laitue" in noms_manquants          # aucune chaîne d'espacement
    assert "potimarron" in {c for c, _b, _v in lisibles}
    # La tomate a une fiche mais n'a jamais été dictée : elle n'est pas du rapport.
    assert "tomate" not in noms_manquants
    assert "tomate" not in {c for c, _b, _v in lisibles}


def test_us226_ca8_l_outil_ne_modifie_rien() -> None:
    """CA8 — Un rapport, pas une migration : aucune écriture dans le module."""
    source = (RACINE / "tools" / "controler_espacements.py").read_text(encoding="utf-8")
    for interdit in (".commit(", ".add(", ".delete(", "UPDATE ", "INSERT "):
        assert interdit not in source, f"l'outil de contrôle écrit : {interdit!r}"


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — La documentation livrée dans la même livraison
# ═════════════════════════════════════════════════════════════════════════════

def test_us226_ca9_fiche_de_domaine_a_jour() -> None:
    """CA9 — plan-et-rangs.md porte la section « D'où vient l'espacement sur le rang »."""
    fiche = (RACINE / "docs" / "domaines" / "plan-et-rangs.md").read_text(encoding="utf-8")
    assert "## D'où vient l'espacement sur le rang" in fiche
    assert "A ≤ B" in fiche                         # la convention
    assert "controler_espacements.py" in fiche      # où porter l'effort
    assert "attributs_par_culture" in fiche         # la lecture unique


def test_us226_ca9_fiche_de_corpus_a_jour() -> None:
    """CA9 — La fiche jardinier dit pourquoi certains rangs n'affichent pas de places."""
    fiche = (RACINE / "data" / "connaissance" / "doc_app" / "parcelles-et-plan.md").read_text(
        encoding="utf-8"
    )
    assert "places non calculées" in fiche
    assert "110 × 135 cm" in fiche
    # Aucune moyenne, aucun emprunt : c'est la promesse tenue au jardinier.
    assert "Aucune moyenne" in fiche

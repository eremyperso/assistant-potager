"""
tests/test_us229_fiche_parcelle_caracteristiques.py — Carte « Caractéristiques »
de la fiche parcelle [US-229]

Cette US est une US de **lecture** : elle ne livre ni champ nouveau, ni
migration, ni écriture. Ce qui se vérifie côté serveur est donc étroit, et c'est
précisément ce qui fait sa valeur :

- CA1  la carte se nourrit de la réponse DÉJÀ chargée par l'onglet Parcelles
       (`GET /plan`) : les deux champs qui lui manquaient — `type_sol` (US-058)
       et `actif` (US-009) — y sont ajoutés, aucun endpoint n'est créé
- CA2  la largeur est déduite par `utils.parcelles.largeur_deduite` et par elle
       seule : aucune division n'est réécrite côté frontend
- CA3  AUCUNE migration n'est livrée : chaque champ affiché se lit sur une
       colonne existante de `parcelles`, ou sur la largeur déduite
- CA9  aucun mode édition n'est livré : le web n'écrit toujours pas ces champs

Le rendu (C1 à C11, CA4 à CA8, CA10) se vérifie dans
`frontend/src/lib/planParcelles.test.js` et sur `/plan-parcelles`.
"""
from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from database.models import Parcelle

RACINE = Path(__file__).resolve().parent.parent
LIB = RACINE / "frontend" / "src" / "lib" / "planParcelles.js"
VUE = RACINE / "frontend" / "src" / "views" / "Plan.jsx"

#: [CA3] Les champs de la carte (C2) et la colonne de `parcelles` qui les porte.
#: La largeur est la seule exception : elle ne se stocke pas, elle se déduit.
CHAMPS_ET_COLONNES = {
    "nom": "nom",
    "superficie": "superficie_m2",
    "longueur": "longueur_m",
    "nb_rangs": "nb_rangs",
    "exposition": "exposition",
    "type_sol": "type_sol",
    "abri": "abri",
    "paillage": "paillage",
    "pepiniere": "est_pepiniere",
    "statut": "actif",
}


def _parcelle_mock(nom, *, superficie=None, longueur=None, type_sol=None,
                   actif=True, pepiniere=False, ordre=0):
    p = MagicMock(spec=Parcelle)
    p.id = abs(hash(nom)) % 1000
    p.nom = nom
    p.exposition = "sud"
    p.superficie_m2 = superficie
    p.abri = None
    p.paillage = None
    p.nb_rangs = None
    p.longueur_m = longueur
    p.type_sol = type_sol
    p.ordre = ordre
    p.est_pepiniere = pepiniere
    p.actif = actif
    return p


@pytest.fixture
def client_plan():
    from app.api.main import app, get_current_user_ctx
    from app.services.context import default_context

    parcelles = [
        _parcelle_mock("Centrale", superficie=69.0, longueur=12.0,
                       type_sol="Limoneux", ordre=1),
        _parcelle_mock("Sans rien", ordre=2),
    ]
    app.dependency_overrides[get_current_user_ctx] = default_context
    with (
        patch("app.api.main.SessionLocal", return_value=MagicMock()),
        patch("utils.parcelles.get_all_parcelles", return_value=parcelles),
        patch("utils.parcelles.calcul_occupation_parcelles", return_value={}),
    ):
        from fastapi.testclient import TestClient
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.pop(get_current_user_ctx, None)


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — La carte se sert de la réponse déjà chargée, pas d'une lecture de plus
# ═════════════════════════════════════════════════════════════════════════════

def test_us229_ca1_plan_expose_tous_les_champs_de_la_carte(client_plan) -> None:
    """CA1 — Les onze champs de C2 se lisent dans la réponse de `GET /plan`."""
    par_nom = {p["nom"]: p for p in client_plan.get("/plan").json()["parcelles"]}
    centrale = par_nom["Centrale"]
    for champ in ("nom", "superficie_m2", "longueur_m", "largeur_m", "nb_rangs",
                  "exposition", "type_sol", "abri", "paillage", "est_pepiniere",
                  "actif"):
        assert champ in centrale, f"{champ} absent de GET /plan"


def test_us229_ca1_type_sol_et_statut_servis_tels_quels(client_plan) -> None:
    """CA1 — Le type de sol (US-058) et le statut (US-009) sont servis, non devinés."""
    par_nom = {p["nom"]: p for p in client_plan.get("/plan").json()["parcelles"]}
    assert par_nom["Centrale"]["type_sol"] == "Limoneux"
    assert par_nom["Centrale"]["actif"] is True
    # « Non renseigné » se sert tel quel : jamais remplacé par une valeur de repli.
    assert par_nom["Sans rien"]["type_sol"] is None


def test_us229_ca1_aucun_endpoint_de_fiche_parcelle(client_plan) -> None:
    """CA1 — Aucun appel supplémentaire n'est introduit pour la carte."""
    from app.api.main import app

    chemins = {route.path for route in app.routes}
    assert "/parcelles/{parcelle_id}/caracteristiques" not in chemins
    assert "/plan/parcelle/{parcelle_id}" not in chemins


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — La largeur se déduit à UN seul endroit
# ═════════════════════════════════════════════════════════════════════════════

def test_us229_ca2_largeur_deduite_par_le_serveur(client_plan) -> None:
    """CA2 — La carte relit la largeur du serveur ; elle ne la recalcule pas."""
    from utils.parcelles import largeur_deduite

    par_nom = {p["nom"]: p for p in client_plan.get("/plan").json()["parcelles"]}
    attendue, _ = largeur_deduite(69.0, 12.0)
    assert par_nom["Centrale"]["largeur_m"] == attendue
    assert par_nom["Centrale"]["largeur_deduite"] is True


def test_us229_ca2_aucune_division_dans_la_carte() -> None:
    """CA2 — Aucune division de superficie par longueur côté frontend."""
    source = LIB.read_text(encoding="utf-8")
    assert re.search(r"superficie_m2\s*/", source) is None
    assert re.search(r"/\s*.{0,20}longueur_m", source) is None


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — Aucune migration, aucune colonne nouvelle
# ═════════════════════════════════════════════════════════════════════════════

def test_us229_ca3_chaque_champ_affiche_est_une_colonne_existante() -> None:
    """CA3 — Les dix champs stockés de C2 existent déjà sur `parcelles`."""
    colonnes = set(Parcelle.__table__.columns.keys())
    for champ, colonne in CHAMPS_ET_COLONNES.items():
        assert colonne in colonnes, f"{champ} n'a pas de colonne {colonne}"


def test_us229_ca3_la_largeur_n_est_pas_une_colonne() -> None:
    """CA3 — La largeur reste DÉDUITE : elle n'a jamais été stockée (US-225)."""
    assert "largeur_m" not in Parcelle.__table__.columns.keys()


def test_us229_ca3_aucune_migration_livree() -> None:
    """CA3 — La dernière migration du dépôt reste celle d'avant l'US."""
    migrations = sorted(
        int(m.stem.split("_v")[1])
        for m in (RACINE / "migrations").glob("migration_v*.sql")
    )
    assert migrations[-1] == 53, (
        "US-229 ne livre aucune migration : les champs de la carte existent tous."
    )


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — Aucune édition n'est livrée par cette US
# ═════════════════════════════════════════════════════════════════════════════

def test_us229_ca9_leve_par_us230_le_bouton_modifier_agit() -> None:
    """CA9 — **levé par US-230**, livrée le 24/09/2026.

    Le CA disait : tant qu'US-230 n'est pas livrée, « Modifier » est rendu
    désactivé et hors tabulation, et la carte n'appelle aucune écriture. Elle
    l'est. Ce qui reste à tenir n'est donc plus l'absence d'édition, mais son
    contraire — et le fait que le bouton ne soit plus une promesse vide.
    """
    vue = VUE.read_text(encoding="utf-8")
    bloc = vue[vue.index("function CarteCaracteristiques"):]
    bloc = bloc[: bloc.index("// ── Panneau de détail")]
    # La promesse d'US-229 est tenue : plus de bouton mort, plus de « bientôt ».
    assert "arrive bientôt" not in bloc
    assert "tabIndex={-1}" not in bloc
    # Et c'est bien la MÊME carte qui bascule (US-230 / E1).
    assert "api.modifierParcelle" in bloc
    assert "Enregistrer" in bloc and "Annuler" in bloc


def test_us229_ca9_le_bouton_reste_absent_en_lecture_seule() -> None:
    """[US-230 / E10] Ce qu'US-229 garantissait — aucune écriture possible —
    reste vrai pour un membre en lecture seule : le bouton n'est pas grisé, il
    n'est pas rendu."""
    vue = VUE.read_text(encoding="utf-8")
    bloc = vue[vue.index("function CarteCaracteristiques"):]
    bloc = bloc[: bloc.index("// ── Panneau de détail")]
    assert "!lectureSeule &&" in bloc

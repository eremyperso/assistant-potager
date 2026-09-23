"""
tests/test_us200_vue_plan.py — La Vue plan [US-200]

L'US est frontend : l'essentiel de sa couverture est dans
`frontend/src/lib/planVue.test.js` (`npm test`, CA2) et dans la page de contrôle
visuel `/vue-plan` (CA11). Ne restent ici que les deux volets vérifiables en
Python :

- CA1  la vue lit `GET /plan` et RIEN d'autre — donc les cultures non localisées
       (V17), jusqu'ici absentes de la réponse, doivent y figurer ;
- garde-fous de structure : le sous-onglet n'est plus un écran d'attente, la lib
  de rendu ne connaît pas React, et la vue ne fait qu'un seul appel d'API.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from database.models import Parcelle

RACINE = Path(__file__).resolve().parent.parent
FRONT = RACINE / "frontend" / "src"


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _parcelle(nom, superficie=None, nb_rangs=None):
    p = MagicMock(spec=Parcelle)
    p.id = abs(hash(nom)) % 1000
    p.nom = nom
    p.exposition = None
    p.superficie_m2 = superficie
    p.abri = None
    p.paillage = None
    p.nb_rangs = nb_rangs
    p.longueur_m = None  # [US-225] non renseignée
    p.ordre = 0
    p.est_pepiniere = False
    p.actif = True
    return p


MOCK_PARCELLES = [_parcelle("planche-centrale", superficie=12.0, nb_rangs=5)]

# [V17] Une culture en place dont la parcelle n'a jamais été dite : clé `None`
# de l'occupation, exactement comme `calcul_occupation_parcelles` la rend.
MOCK_OCCUPATION = {
    "planche-centrale": [
        {"culture": "tomate", "variete": "noire de Crimée", "nb_plants": 8.0,
         "type_organe": "reproducteur", "unite": "plants"},
    ],
    None: [
        {"culture": "tomate", "variete": "green zebra", "nb_plants": 4.0,
         "type_organe": "reproducteur", "unite": "plants"},
        {"culture": "carotte", "variete": None, "nb_plants": 2.0,
         "type_organe": "végétatif", "unite": "m²"},
    ],
}


@pytest.fixture
def client():
    from app.api.main import app, get_current_user_ctx
    from app.services.context import default_context

    app.dependency_overrides[get_current_user_ctx] = default_context
    with (
        patch("app.api.main.SessionLocal", return_value=MagicMock()),
        patch("utils.parcelles.get_all_parcelles", return_value=MOCK_PARCELLES),
        patch("utils.parcelles.calcul_occupation_parcelles", return_value=MOCK_OCCUPATION),
    ):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.pop(get_current_user_ctx, None)


# ══════════════════════════════════════════════════════════════════════════════
# CA1 — tout ce que la vue dessine tient dans UNE lecture de GET /plan
# ══════════════════════════════════════════════════════════════════════════════

def test_us200_ca1_plan_sert_les_cultures_non_localisees(client):
    """[CA1 / V17] Les cultures sans parcelle sont servies par GET /plan."""
    body = client.get("/plan").json()
    assert "non_localisees" in body
    cultures = {c["culture"] for c in body["non_localisees"]}
    assert cultures == {"tomate", "carotte"}


def test_us200_ca1_non_localisee_porte_son_mode_dimplantation(client):
    """[V4] Chaque culture non localisée porte le mode déduit de son unité."""
    body = client.get("/plan").json()
    par_culture = {c["culture"]: c for c in body["non_localisees"]}
    assert par_culture["tomate"]["mode_implantation"] == "rang"
    assert par_culture["carotte"]["mode_implantation"] == "surface"


def test_us200_ca1_une_surface_non_localisee_nest_jamais_tronquee(client):
    """[US-037 / CA10] Une quantité en m² est fractionnable, pas un entier."""
    body = client.get("/plan").json()
    carotte = next(c for c in body["non_localisees"] if c["culture"] == "carotte")
    assert carotte["unite"] == "m²"
    assert carotte["nb_plants"] == 2.0


def test_us200_ca1_le_bloc_est_toujours_present_meme_vide():
    """[CA1] `non_localisees` est toujours là : la vue n'a jamais à le deviner."""
    from app.api.main import app, get_current_user_ctx
    from app.services.context import default_context

    app.dependency_overrides[get_current_user_ctx] = default_context
    with (
        patch("app.api.main.SessionLocal", return_value=MagicMock()),
        patch("utils.parcelles.get_all_parcelles", return_value=MOCK_PARCELLES),
        patch("utils.parcelles.calcul_occupation_parcelles",
              return_value={"planche-centrale": []}),
    ):
        with TestClient(app) as c:
            body = c.get("/plan").json()
    app.dependency_overrides.pop(get_current_user_ctx, None)
    assert body["non_localisees"] == []


def test_us200_ca6_les_parcelles_restent_inchangees(client):
    """[US-198 / CA6] Le bloc ajouté ne touche à rien de ce qui était déjà servi."""
    body = client.get("/plan").json()
    parcelle = body["parcelles"][0]
    assert parcelle["nom"] == "planche-centrale"
    assert parcelle["nb_rangs"] == 5
    assert parcelle["disposition"]["rangs_declares"] == 5
    # La culture non localisée n'entre dans AUCUNE parcelle.
    assert [c["culture"] for c in parcelle["cultures"]] == ["tomate"]


# ══════════════════════════════════════════════════════════════════════════════
# Garde-fous de structure
# ══════════════════════════════════════════════════════════════════════════════

def test_us200_le_sous_onglet_nest_plus_un_ecran_dattente():
    """[CA1] « Vue plan » monte la vue réelle, plus le Placeholder d'US-053."""
    app_jsx = (FRONT / "App.jsx").read_text(encoding="utf-8")
    assert "'plan-vue': (props) => <PlanVue {...props} />" in app_jsx
    assert "Vue plan à l'échelle" not in app_jsx


def test_us200_ca2_la_lib_de_rendu_ne_connait_pas_react():
    """[CA2] Les règles de rendu sont vérifiables sans monter de composant."""
    lib = (FRONT / "lib" / "planVue.js").read_text(encoding="utf-8")
    imports = [l for l in lib.splitlines() if l.startswith("import ")]
    assert imports and all("react" not in l.lower() for l in imports)
    assert (FRONT / "lib" / "planVue.test.js").exists()


def test_us200_ca1_la_vue_ne_fait_quun_seul_appel_dapi():
    """[CA1] Une seule lecture : `api.plan`, et aucune autre."""
    vue = (FRONT / "views" / "PlanVue.jsx").read_text(encoding="utf-8")
    appels = [mot for mot in vue.split() if mot.startswith("api.")]
    assert appels == ["api.plan(dateRef,"]


def test_us200_ca5_deux_colonnes_par_container_query_jamais_trois():
    """[CA5 / A1] Container queries, jamais de breakpoint d'écran, jamais 3 colonnes.

    [US-228 / CA5, arbitrage A23] Le seuil passe de 720 à 1000 px : une carte
    porte désormais une piste de places, il lui faut plus de largeur. La règle
    elle-même ne bouge pas — container query, deux colonnes, jamais trois.
    """
    vue = (FRONT / "views" / "PlanVue.jsx").read_text(encoding="utf-8")
    assert "@[1000px]/plan:grid-cols-2" in vue
    assert "grid-cols-3" not in vue
    assert "md:grid-cols" not in vue and "lg:grid-cols" not in vue


def test_us200_ca11_la_page_de_controle_visuel_est_routee():
    """[CA11] `/vue-plan` rejoue la vue sur des réponses simulées, en lazy()."""
    main_jsx = (FRONT / "main.jsx").read_text(encoding="utf-8")
    assert "'/vue-plan': () => import('./views/_PlanVuePreview.jsx')" in main_jsx
    assert (FRONT / "views" / "_PlanVuePreview.jsx").exists()

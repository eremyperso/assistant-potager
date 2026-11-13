"""
tests/test_us228_piste_des_places.py — Le rang dessiné en piste de places [US-228]

L'US est entièrement frontale : le CALCUL de rendu est vérifié par
`frontend/src/lib/planVue.test.js` (`npm test`, sans React, CA2). Ce qui se
vérifie ici est ce qu'un test JavaScript ne peut pas voir — que les RÈGLES
structurantes du dépôt tiennent toujours :

- CA2  aucune règle métier recalculée côté front ; la lib ne connaît pas React
- CA3  les emoji de culture reprennent la maquette, sans équivalence en plants
- CA4  la piste est un composant du design system, à palette et taille paramétrées
- CA5  container queries, jamais de breakpoint d'écran, jamais trois colonnes
- CA7  aucune donnée de places n'est inventée : elles viennent toutes de GET /plan
- CA12 la page de contrôle visuel couvre les cas que l'US énumère
"""
from __future__ import annotations

import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
FRONT = RACINE / "frontend" / "src"
LIB = FRONT / "lib" / "planVue.js"
PISTE = FRONT / "components" / "ui" / "PisteDesPlaces.jsx"
RANG = FRONT / "components" / "ui" / "RangPlan.jsx"
VUE = FRONT / "views" / "PlanVue.jsx"
PREVIEW = FRONT / "views" / "_PlanVuePreview.jsx"


def _lire(chemin: Path) -> str:
    return chemin.read_text(encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════════
# CA2 — Le calcul de rendu vit dans la lib, sans React et sans agronomie
# ══════════════════════════════════════════════════════════════════════════════

def test_us228_ca2_la_piste_se_calcule_dans_la_lib_sans_react() -> None:
    """CA2 — Fentes, regroupement, plancher et libellés sont vérifiables sans composant."""
    lib = _lire(LIB)
    for fonction in ("pisteDuRang", "resteDuRang", "sousLibelleRang",
                     "sousLibelleLibre", "dimensionsTexte"):
        assert f"export function {fonction}" in lib, fonction
    imports = [l for l in lib.splitlines() if l.startswith("import ")]
    assert imports and all("react" not in l.lower() for l in imports)
    assert "[P1, P5]" in _lire(FRONT / "lib" / "planVue.test.js")


def test_us228_ca2_ca7_aucune_place_n_est_recalculee_cote_front() -> None:
    """CA2, CA7 — Les places viennent de `GET /plan` (US-227) : le front ne les
    redérive jamais d'une longueur et d'un espacement."""
    lib = _lire(LIB)
    # La formule d'US-227 / R10 n'a aucune raison d'exister ici.
    assert "longueur_m * 100" not in lib
    assert not re.search(r"espacement[^\n]*/\s*100", lib)
    assert "Math.floor(" not in lib.split("// ── La piste des places")[1].split("// ── Rangs")[0]


# ══════════════════════════════════════════════════════════════════════════════
# CA3, CA4 — Design system : pictogrammes isolés, piste paramétrable
# ══════════════════════════════════════════════════════════════════════════════

def test_us228_les_phases_partagent_les_icones_de_la_maquette() -> None:
    """Les graines, la pousse et le panier se retrouvent dans la légende et les rangs."""
    phases = _lire(FRONT / "components" / "ui" / "PastillePhase.jsx")
    assert phases.count("<IconePhase phase={p.cle}") == 2
    for phase in ("PHASE_SEMEE", "PHASE_EN_PLACE", "PHASE_EN_RECOLTE"):
        assert f"phase === {phase}" in phases


def test_us228_ca4_la_piste_est_un_composant_du_design_system() -> None:
    """CA4 — `PisteDesPlaces`, exporté par le point d'entrée unique, palette et
    taille en paramètre, pour qu'US-222 et l'onglet Rotation le reprennent."""
    index = _lire(FRONT / "components" / "ui" / "index.js")
    assert "PisteDesPlaces" in index
    piste = _lire(PISTE)
    assert "palette = palettePhases()" in piste
    assert "taille = 'normale'" in piste
    assert "aria-hidden" in piste


def test_us228_ca4_le_trait_d_us200_devient_le_mode_degrade() -> None:
    """CA4, P6 — `TraitRang` n'est pas supprimé : il est le mode dégradé de la piste."""
    assert (FRONT / "components" / "ui" / "TraitRang.jsx").exists()
    assert "TraitRang" in _lire(PISTE)


# ══════════════════════════════════════════════════════════════════════════════
# CA5, CA6 — Container queries, jamais de breakpoint d'écran
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
# CA12 — La page de contrôle visuel couvre les cas de l'US
# ══════════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════════
# [US-327 / CA6] Les places quittent le plan
# ══════════════════════════════════════════════════════════════════════════════
# Le rang dessiné en piste de places (`RangPlan`, `CartePlanParcelle`, la Vue plan
# d'US-200 et sa page de contrôle) a quitté l'écran Plan : la maquette « Plan -
# Pistes » le juge inexploitable en consultation. Les places se lisent dans le suivi
# d'une culture (US-322, bloc S3) ; la piste et le trait restent au design system.

def test_us228_us327_la_carte_et_le_rang_de_la_vue_plan_sont_retires() -> None:
    """[US-327 / CA6] Ni carte ni rang de l'ancienne Vue plan ; la piste reste."""
    for retire in (RANG, VUE, PREVIEW, FRONT / "components" / "ui" / "CartePlanParcelle.jsx"):
        assert not retire.exists(), retire
    index = _lire(FRONT / "components" / "ui" / "index.js")
    assert "export { PisteDesPlaces, IconeCote }" in index
    assert "export { TraitRang }" in index


def test_us228_us327_les_places_passent_dans_le_suivi() -> None:
    """[US-327 / CA6, US-322 / S3] La ligne de place du suivi : pieds, mètres, espacement."""
    lib = _lire(FRONT / "lib" / "suiviCulture.js")
    assert "export function lignePlace" in lib
    assert "⚠ +" in lib

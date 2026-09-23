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

def test_us228_ca3_les_symboles_de_culture_sont_proportionnels() -> None:
    """CA3 — Sept symboles de culture sans équivalence en plants."""
    piste = _lire(PISTE)
    assert "function Repere" in piste
    assert "data-repere={plein ? 'plein' : 'creux'}" in piste
    assert "symboleDeCulture(culture, variete)" in piste
    assert "<MarqueLibre taille={taille}" in piste
    assert "<PictoCulture culture={rang.culture} variete={rang.variete}" in _lire(RANG)
    assert "MAX_FENTES = 7" in _lire(LIB)
    assert "piedsParFente" not in _lire(LIB)
    assert "7 symboles = rang plein (en proportion)" in _lire(VUE)


def test_us228_p15_la_phase_reste_ecrite_sur_chaque_rang() -> None:
    """P15 — Le composant de phase écrit son mot, même sur mobile."""
    rang = _lire(RANG)
    assert "<PastillePhase ligne={rang}" in rang
    assert "<PucePhase" not in rang


def test_us228_les_phases_partagent_les_icones_de_la_maquette() -> None:
    """Les graines, la pousse et le panier se retrouvent dans la légende et les rangs."""
    phases = _lire(FRONT / "components" / "ui" / "PastillePhase.jsx")
    assert phases.count("<IconePhase phase={p.cle}") == 2
    for phase in ("PHASE_SEMEE", "PHASE_EN_PLACE", "PHASE_EN_RECOLTE"):
        assert f"phase === {phase}" in phases


def test_us228_le_rang_libre_ne_propose_pas_de_lien_ajouter() -> None:
    """Un rang libre n'affiche aucune invitation d'ajout non implémentée."""
    assert "ajouter une culture" not in _lire(RANG).lower()


def test_us228_les_rangs_partagent_les_colonnes_et_les_libelles_sont_concis() -> None:
    """Les pistes restent alignées et le rappel de plantation n'est pas affiché."""
    rang = _lire(RANG)
    assert "minmax(0,1fr)_80px_104px]" in rang
    assert "reste.prefixe === 'reste' ? 'libre'" in rang
    assert "reste.prefixe !== 'reste'" in rang
    assert "rang.total" not in rang
    assert 'className="whitespace-nowrap">{rang.sousLibelle?.quantite}' in rang


def test_us228_p11_les_indicateurs_absents_sont_signales() -> None:
    """P11 — Quatre icônes identifiées, texte accessible et rouge si absent."""
    carte = _lire(FRONT / "components" / "ui" / "CartePlanParcelle.jsx")
    assert "carte.indicateurs.map" in carte
    assert "data-indicateur={indicateur.cle}" in carte
    assert "title={indicateur.titre}" in carte
    assert "indicateur.alerte ? 'text-red" in carte
    for type_indicateur in ("surface", "longueur", "largeur", "rangs"):
        assert f"type === '{type_indicateur}'" in carte


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

def test_us228_ca5_deux_colonnes_a_1000px_de_conteneur() -> None:
    """CA5 / A23 — Le seuil de la maquette gelée remplace les 720 px d'A1."""
    vue = _lire(VUE)
    assert "@[1000px]/plan:grid-cols-2" in vue
    assert "@[720px]/plan" not in vue
    assert "grid-cols-3" not in vue
    assert "md:grid-cols" not in vue and "lg:grid-cols" not in vue


def test_us228_ca6_la_ligne_se_replie_sous_560px_de_carte() -> None:
    """CA6 — Trois zones empilées sous 560 px de largeur de CARTE, 44 px de cible."""
    rang = _lire(RANG)
    assert "@[560px]/carte:grid-cols-" in rang
    assert "min-h-[44px]" in rang
    assert "md:" not in rang and "lg:" not in rang


# ══════════════════════════════════════════════════════════════════════════════
# CA12 — La page de contrôle visuel couvre les cas de l'US
# ══════════════════════════════════════════════════════════════════════════════

def test_us228_ca12_la_page_de_controle_couvre_les_cas_enumeres() -> None:
    """CA12 — Piste normale, grande capacité, surcharge, semis en ligne, rang libre,
    parcelle sans longueur et largeur incohérente s'y voient d'un coup d'œil."""
    preview = _lire(PREVIEW)
    assert "largeur_incoherente" in preview
    assert "capacite_exemple" in preview
    assert "part_semee" in preview
    assert "'ml'" in preview
    assert "parcelles_sans_longueur" in preview
    # Un rang plus chargé que ses places, et un rang à plus de seize places.
    assert "26, 'plants'" in preview
    assert "60, 'graines'" in preview

"""
[US-242] L'onglet « Lots » de la Pépinière en journal de saison.

Les règles (statut, gestes datés, fenêtre, positions, bilan) vivent dans
`frontend/src/lib/lotsJournal.js` et sont couvertes par `lotsJournal.test.js`
(`npm test`, CA11) ; ce fichier vérifie la structure de l'écran et la lancer
quand Node est disponible. Le rendu se valide sur `/pepiniere-lots` (CA10).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
SRC = RACINE / "frontend" / "src"


def _lire(chemin: str) -> str:
    return (SRC / chemin).read_text(encoding="utf-8")


def test_us242_ca11_la_lib_est_testee_par_npm_test() -> None:
    """CA11 — la lib et son fichier de test existent, au format `node:test`."""
    lib = _lire("lib/lotsJournal.js")
    for fonction in ("statutLot", "gestesDates", "fenetre", "frise", "bilanDesLots", "journalDuLot"):
        assert f"export function {fonction}" in lib, fonction
    assert "from 'node:test'" in _lire("lib/lotsJournal.test.js")


@pytest.mark.skipif(shutil.which("node") is None, reason="Node absent")
def test_us242_ca11_les_regles_de_la_lib_passent() -> None:
    """CA11 — les tests de la lib passent (statut, gestes datés, fenêtre, bilan)."""
    r = subprocess.run(
        ["node", "--test", "src/lib/lotsJournal.test.js"],
        cwd=RACINE / "frontend", capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]


def test_us242_ca1_le_filtre_ouvre_sur_tous() -> None:
    """CA1 — quatre filtres, « Tous » à l'ouverture (état d'écran)."""
    lib = _lire("lib/lotsJournal.js")
    for libelle in ("En cours", "À régler", "Terminés", "Tous"):
        assert f"libelle: '{libelle}'" in lib, libelle
    assert "filtreLots: 'tous'" in _lire("views/Pepiniere.jsx")


def test_us242_l_onglet_lots_rend_le_journal() -> None:
    """La vue Pépinière rend `OngletLots` sur l'onglet Lots ; l'ancienne grille de cartes a disparu."""
    vue = _lire("views/Pepiniere.jsx")
    assert "<OngletLots" in vue
    for ancien in ("function LotCard", "function Reperes", "GroupHead", "const TRIS"):
        assert ancien not in vue, ancien


def test_us242_ca7_la_fiche_n_a_aucun_bouton_de_geste() -> None:
    """CA7 — registre sans geste : aucun `BoutonGeste`, un lien « Agir dans Ma pépinière »."""
    onglet = _lire("components/OngletLots.jsx")
    assert "BoutonGeste" not in onglet
    assert "Agir dans Ma pépinière" in onglet
    vue = _lire("views/Pepiniere.jsx")
    assert "setEtat({ onglet: 'parcours' })" in vue


def test_us242_ca6_ligne_cliquable_au_clavier_et_fiche_depliee() -> None:
    """CA6 — ligne clavier + `aria-expanded`, fiche dépliée au large, plein écran à l'étroit."""
    onglet = _lire("components/OngletLots.jsx")
    assert 'role="button" tabIndex={0} aria-expanded={estOuvert}' in onglet
    assert "e.key === 'Enter' || e.key === ' '" in onglet
    assert "<FicheDepliee" in onglet and "<FichePleinEcran" in onglet


def test_us242_ca8_aller_au_lot_remet_tous_et_deplie() -> None:
    """CA8 — « Aller au lot n° » remet le filtre sur Tous et déplie le lot ; inconnu, il le dit."""
    onglet = _lire("components/OngletLots.jsx")
    assert "setEtat({ filtreLots: 'tous', q: '', lotDeplie: cible.lot_id })" in onglet
    assert "messageLotInconnu(numero)" in onglet


def test_us242_ca10_composants_en_container_queries() -> None:
    """CA10 — la mise en page des blocs suit leur conteneur, pas l'écran."""
    onglet = _lire("components/OngletLots.jsx")
    for conteneur in ("@container/journal", "@container/bilan", "@container/fichej", "@container/barre-lots"):
        assert conteneur in onglet, conteneur
    assert " md:" not in onglet and " lg:" not in onglet


def test_us242_ca10_page_de_controle_visuel() -> None:
    """CA10 — la page de contrôle `/pepiniere-lots` monte le vrai écran."""
    assert "'/pepiniere-lots'" in _lire("main.jsx")
    assert "<Pepiniere" in _lire("views/_PepiniereLotsPreview.jsx")


def test_us242_corpus_decrit_le_journal_de_saison() -> None:
    """US-099 / CA9 — la fiche du corpus décrit l'onglet tel qu'il est."""
    fiche = (RACINE / "data" / "connaissance" / "doc_app" / "pepiniere-par-lot.md").read_text(encoding="utf-8")
    assert "## Relire sa saison dans l'onglet Lots" in fiche
    assert "les cartes par lot, groupées par famille" not in fiche

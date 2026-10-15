"""[US-215] L'onglet « Aujourd'hui » de la Pépinière.

Le rendu et ses règles de mise en forme sont couverts par `npm test`
(`frontend/src/lib/pepiniere.aujourdhui.test.js`, CA15). Ce fichier tient ce que
pytest peut garantir : la donnée servie à la pastille (CA2), les garde-fous du
front (aucune écriture, aucune redirection vers Telegram, onglet Lots intact) et
le corpus (CA17).
"""
from pathlib import Path

import pytest

from app.services import lots_pepiniere
from app.services.context import TenantContext
from database.models import Parcelle, Potager, User

RACINE = Path(__file__).resolve().parents[1]
SRC = RACINE / "frontend" / "src"
CTX = TenantContext(user_id=1, potager_id=1, role="owner")


@pytest.fixture
def db(test_db):
    test_db.add_all([User(id=1, email="a@potager.test"), User(id=2, email="b@potager.test")])
    test_db.flush()
    test_db.add_all([Potager(id=1, nom="A", proprietaire_id=1), Potager(id=2, nom="B", proprietaire_id=2)])
    test_db.flush()
    test_db.add_all([
        Parcelle(id=1, nom="nord", nom_normalise="nord", potager_id=1),
        Parcelle(id=2, nom="serre", nom_normalise="serre", potager_id=1, est_pepiniere=True,
                 superficie_m2=2.5, type_pepiniere="chaude"),
        Parcelle(id=3, nom="chassis", nom_normalise="chassis", potager_id=2, est_pepiniere=True),
    ])
    test_db.commit()
    return test_db


def _lire(chemin: str) -> str:
    return (SRC / chemin).read_text(encoding="utf-8")


# ── CA2 — la pastille d'une pépinière unique ─────────────────────────────────

def test_us215_ca2_pepinieres_portent_superficie_et_type(db) -> None:
    """CA2 — superficie et type copiés pour la pastille, potager consulté seulement."""
    assert lots_pepiniere.pepinieres_du_potager(db, CTX) == [
        {"id": 2, "nom": "serre", "superficie_m2": 2.5, "type_pepiniere": "chaude"},
    ]


def test_us215_ca2_type_absent_rendu_vide(db) -> None:
    """CA2 / RT2 — un type non renseigné reste vide, jamais supposé."""
    serre = db.get(Parcelle, 2)
    serre.type_pepiniere = None
    serre.superficie_m2 = None
    db.commit()
    p = lots_pepiniere.pepinieres_du_potager(db, CTX)[0]
    assert p["type_pepiniere"] is None and p["superficie_m2"] is None


# ── CA1, CA7 bis, CA11 — garde-fous du front ────────────────────────────────

def test_us215_ca1_onglet_lots_intact() -> None:
    """CA1 — l'onglet Lots garde ses cartes, groupes par famille et numéro de lot."""
    vue = _lire("views/Pepiniere.jsx")
    for repere in ("function LotCard", "GroupHead", "libelleNumeroLot(lot)", "emplacementLot(lot)",
                   "<OngletAujourdhui", "ongletsPepiniere"):
        assert repere in vue, repere


def test_us215_ca7bis_aucune_redirection_vers_telegram() -> None:
    """CA7 bis — l'onglet dépose par BoutonGeste, sans lien Telegram ni ouverture de fenêtre."""
    onglet = _lire("components/OngletAujourdhui.jsx")
    assert "BoutonGeste" in onglet
    for interdit in ("t.me", "window.open", "location.href", "lien_profond", "api.preparerGeste"):
        assert interdit not in onglet, interdit
    bouton = _lire("components/BoutonGeste.jsx")
    assert "notifier(notificationDepot(" in bouton
    assert "window.open" not in bouton


def test_us215_ca11_lecture_seule_sans_bouton() -> None:
    """CA11 — les boutons de geste passent par BoutonGeste, qui ne rend rien en lecture seule."""
    bouton = _lire("components/BoutonGeste.jsx")
    assert "if (!peutEnregistrer(potagerActif?.role)) return null" in bouton


def test_us215_ca14_bouton_nomme_son_lot() -> None:
    """CA14 — le nom accessible du bouton nomme le lot."""
    assert "aria-label={ariaLabel}" in _lire("components/BoutonGeste.jsx")
    assert "ariaLabel={bouton.ariaLabel}" in _lire("components/OngletAujourdhui.jsx")


def test_us215_ca12_container_queries_sans_breakpoint() -> None:
    """CA12 — container queries pour le composant, aucun breakpoint d'écran."""
    onglet = _lire("components/OngletAujourdhui.jsx")
    assert "@container/liste" in onglet and "@container/bandeau" in onglet
    for bp in (" sm:", " md:", " lg:", " xl:"):
        assert bp not in onglet, bp


def test_us215_ca16_page_de_controle_branchee() -> None:
    """CA16 — la page de contrôle visuel est routée."""
    assert "'/pepiniere-aujourdhui'" in _lire("main.jsx")
    page = _lire("views/_PepiniereAujourdhuiPreview.jsx")
    for etat in ("nominal", "une_pepiniere", "vide", "lecture_seule", "echec"):
        assert etat in page


# ── CA17 — corpus ───────────────────────────────────────────────────────────

def test_us215_ca17_corpus_decrit_l_onglet() -> None:
    """CA17 — la fiche jardinier décrit l'onglet et ses quatre réponses, sans Telegram ouvert."""
    fiche = (RACINE / "data" / "connaissance" / "doc_app" / "pepiniere-par-lot.md").read_text(encoding="utf-8")
    for mot in ("onglet **Aujourd'hui**", "À repiquer", "À endurcir", "Prêts pour le plan",
                "À semer", "onglet **Lots**", "sans quitter l'application ni ouvrir Telegram"):
        assert mot in fiche, mot
    assert "puis ouvre votre compagnon Telegram" not in fiche

"""[US-218] L'onglet « Ma pépinière » — le parcours du plant.

Le rangement des étiquettes, leurs libellés, le grand chiffre, la règle, les
fragments liés, l'onglet de stade par défaut et le choix des gestes sont couverts
par `npm test` (`frontend/src/lib/parcours.test.js`, CA26). Ce fichier tient ce que
pytest peut garantir :

- côté serveur, la fourchette de sortie de chaque lot (`echeances.sortie_prevue`,
  conservée du premier travail, A39) et le calendrier de la bande quand rien n'est
  à semer (`parcours.calendrier_semis`, maquette HF) ;
- côté front, les garde-fous : deux onglets, onglets retirés supprimés, une seule
  lecture des lots, gestes déposés sans redirection, lecture seule, container
  queries, page de contrôle (CA27), corpus (CA30).

Les durées écrites ici sont des VALEURS DE TEST : elles n'engagent aucune agronomie.
"""
from datetime import date
from pathlib import Path

import pytest

from app.services import calendrier_cultural as cal
from app.services import echeances_lots as ech

RACINE = Path(__file__).resolve().parents[1]
SRC = RACINE / "frontend" / "src"
LE_19_SEPT = date(2026, 9, 19)
LE_19_OCT = date(2026, 10, 19)


def _duree(etape: str, mini: int, maxi: int) -> cal.DureeLue:
    return cal.DureeLue(etape=etape, libelle=etape, jours_min=mini, jours_max=maxi,
                        mention=None, affichage=f"{mini}-{maxi} j", attribution=None)


DELAIS = ech._Delais(
    godet=_duree(cal.ETAPE_SEMIS_GODET, 10, 12),
    mise_en_terre=_duree(cal.ETAPE_REPIQUAGE, 40, 50),
)
SANS_DELAIS = ech._Delais(godet=None, mise_en_terre=None)


def _lot(**plus) -> dict:
    lot = {
        "lot_id": "semis-128", "numero_lot": 128, "culture": "chou", "variete": "frisé",
        "date_semis": "2026-09-01", "graines_semees": 48, "graines_soldees": 0,
        "graines_en_germination": 48, "nb_mises_en_godet": 0, "stock_residuel_godet": 0,
        "plants_obtenus": 0, "sans_semis_rattache": False, "date_dernier_geste": "2026-09-01",
        "emplacement": {"nom": "Serre", "type_pepiniere": "chaude", "origine": "semis"},
    }
    lot.update(plus)
    return lot


def _lire(chemin: str) -> str:
    return (SRC / chemin).read_text(encoding="utf-8")


# ── A39 — `sortie_prevue`, la fin de la règle des étiquettes (P18) ──────────

def test_us218_sortie_prevue_champ_ajoute_sans_rien_retirer() -> None:
    """A39 — `sortie_prevue` s'ajoute : aucune clé d'US-214 ne disparaît."""
    e = ech._echeances_du_lot(_lot(), DELAIS, LE_19_SEPT)["echeances"]
    for cle in ("date_reference", "repiquage", "mise_en_terre", "endurcissement", "dormance", "raisons"):
        assert cle in e, cle


def test_us218_sortie_prevue_lot_en_graines() -> None:
    """A39 — un lot sans godet a sa fourchette de sortie, alors que `mise_en_terre` reste vide."""
    e = ech._echeances_du_lot(_lot(), DELAIS, LE_19_SEPT)["echeances"]
    assert e["mise_en_terre"]["etat"] is None
    assert e["sortie_prevue"] == {"du": "2026-10-11", "au": "2026-10-21", "raison": None}


def test_us218_sortie_prevue_lot_en_godets_egale_mise_en_terre() -> None:
    """A39 — en godets, `sortie_prevue` et `mise_en_terre` disent la même fourchette."""
    lot = _lot(nb_mises_en_godet=1, stock_residuel_godet=40, graines_en_germination=0, graines_soldees=48)
    e = ech._echeances_du_lot(lot, DELAIS, LE_19_SEPT)["echeances"]
    assert (e["sortie_prevue"]["du"], e["sortie_prevue"]["au"]) == (e["mise_en_terre"]["du"], e["mise_en_terre"]["au"])


def test_us218_sortie_prevue_sans_delai_motivee() -> None:
    """RT2 — sans délai avant plantation, aucune date inventée : la raison est dite."""
    e = ech._echeances_du_lot(_lot(), SANS_DELAIS, LE_19_SEPT)["echeances"]
    assert e["sortie_prevue"]["du"] is None and e["sortie_prevue"]["au"] is None
    assert "délai avant plantation non renseigné" in e["sortie_prevue"]["raison"]


def test_us218_sortie_prevue_sans_semis_rattache() -> None:
    """A39 — des godets sans semis rattaché n'ont pas de sortie calculable."""
    lot = _lot(sans_semis_rattache=True, date_semis=None, nb_mises_en_godet=1, stock_residuel_godet=12)
    e = ech._echeances_du_lot(lot, DELAIS, LE_19_SEPT)["echeances"]
    assert e["sortie_prevue"] == {"du": None, "au": None, "raison": "date de semis inconnue"}


# ── Maquette HF — le calendrier de la bande quand rien n'est à semer ────────

FENETRES = [
    ("tomate", 2, 4), ("poireau", 2, 5), ("melon", 3, 4), ("mâche", 8, 10), ("chou d'hiver", 11, 2),
]


@pytest.fixture
def fenetres(monkeypatch):
    monkeypatch.setattr(ech, "_fenetres_semis_pepiniere", lambda db, pid: ("oceanique", FENETRES))


def test_us218_calendrier_six_mois_a_partir_de_la_reference(fenetres) -> None:
    """HF — six mois, le mois de référence en tête, chacun avec son délai."""
    c = ech._calendrier_semis(None, 1, LE_19_OCT)
    assert [m["mois"] for m in c["mois"]] == ["2026-10", "2026-11", "2026-12", "2027-01", "2027-02", "2027-03"]
    assert [m["dans_jours"] for m in c["mois"]] == [0, 13, 43, 74, 105, 133]
    assert c["mois"][0]["s_ouvrent"] == []   # le mois en cours : les tuiles le disent


def test_us218_calendrier_ouvertures_et_encore_ouvertes(fenetres) -> None:
    """HF — un mois cite les cultures qui s'y ouvrent, puis compte celles déjà citées encore ouvertes."""
    c = ech._calendrier_semis(None, 1, LE_19_OCT)
    par_mois = {m["mois"]: m for m in c["mois"]}
    assert par_mois["2026-11"]["s_ouvrent"] == ["chou d'hiver"]
    assert par_mois["2027-02"]["s_ouvrent"] == ["poireau", "tomate"]
    assert par_mois["2027-02"]["encore_ouvertes"] == 1      # chou d'hiver, jusqu'en février
    assert par_mois["2027-03"]["s_ouvrent"] == ["melon"]
    assert par_mois["2027-03"]["encore_ouvertes"] == 2      # poireau et tomate


def test_us218_calendrier_prochaine_ouverture(fenetres) -> None:
    """HF — la prochaine ouverture : le 1er du premier mois où une fenêtre s'ouvre (RT2)."""
    c = ech._calendrier_semis(None, 1, LE_19_OCT)
    assert c["prochaine_ouverture"] == {"date": "2026-11-01", "jours": 13}
    assert c["zone"] == cal.LIBELLES_ZONES.get("oceanique", "oceanique")


def test_us218_calendrier_sans_aucune_fenetre(monkeypatch) -> None:
    """RT2 — sans fenêtre au référentiel, pas d'ouverture inventée."""
    monkeypatch.setattr(ech, "_fenetres_semis_pepiniere", lambda db, pid: ("oceanique", []))
    c = ech._calendrier_semis(None, 1, LE_19_OCT)
    assert c["prochaine_ouverture"] is None
    assert all(not m["s_ouvrent"] for m in c["mois"])


def test_us218_calendrier_seulement_quand_rien_n_est_a_semer() -> None:
    """HF / CA7 — le bloc ne lit le calendrier que si rien n'est à semer ni replié."""
    source = (RACINE / "app" / "services" / "echeances_lots.py").read_text(encoding="utf-8")
    assert "_calendrier_semis(db, ctx.potager_id, ref) if not (a_semer_stock or sans_graines) else None" in source


# ── CA1, CA29 — deux onglets, les onglets retirés supprimés ─────────────────

def test_us218_ca1_deux_onglets_parcours_par_defaut() -> None:
    """CA1 — la vue ouvre le parcours par défaut ; « Lots » est le journal de saison (US-242)."""
    vue = _lire("views/Pepiniere.jsx")
    assert "onglet: 'parcours'" in vue
    assert "<OngletParcours" in vue and "ONGLETS_PEPINIERE" in vue
    assert "<OngletLots" in vue and "libelleNumeroLot(lot)" in vue


@pytest.mark.parametrize("chemin", [
    "components/OngletAujourdhui.jsx", "views/_PepiniereAujourdhuiPreview.jsx",
    "lib/pepiniere.aujourdhui.test.js", "components/OngletCalendrier.jsx",
    "lib/calendrierPepiniere.js", "views/_PepiniereCalendrierPreview.jsx",
])
def test_us218_ca29_code_des_onglets_retires_supprime(chemin: str) -> None:
    """CA29 — le code et les pages de contrôle des onglets retirés n'existent plus."""
    assert not (SRC / chemin).exists(), chemin


def test_us218_ca29_aucune_reference_aux_onglets_retires() -> None:
    """CA29 — plus aucune importation des onglets retirés."""
    for chemin in ("views/Pepiniere.jsx", "main.jsx", "lib/pepiniere.js"):
        texte = _lire(chemin)
        for retire in ("OngletAujourdhui", "OngletCalendrier", "calendrierPepiniere", "ongletsPepiniere"):
            assert retire not in texte, (chemin, retire)


# ── CA14, CA23, CA25 — gestes, lecture seule, une seule lecture ─────────────

def test_us218_ca25_une_seule_lecture() -> None:
    """CA25 — l'onglet ne lit rien lui-même : tout vient de `GET /pepiniere/lots`."""
    onglet = _lire("components/OngletParcours.jsx")
    assert "api." not in onglet
    assert "calendriersPlan" not in _lire("views/Pepiniere.jsx")


def test_us218_ca14_gestes_deposes_sans_redirection() -> None:
    """CA14 — les gestes passent par BoutonGeste : dépôt dans la file, notification, pas de Telegram."""
    onglet = _lire("components/OngletParcours.jsx")
    assert "BoutonGeste" in onglet and "gestesEtiquette(" in onglet
    for interdit in ("t.me", "window.open", "location.href", "preparerGeste"):
        assert interdit not in onglet, interdit


def test_us218_ca14_une_seule_regle_de_gestes() -> None:
    """CA14 / CA26 — le choix des gestes réutilise celui de la fiche du lot, sans le dupliquer."""
    lib = _lire("lib/parcours.js")
    assert "gestesDuLot" in lib
    assert "const GESTE_DE_SUGGESTION" not in lib


def test_us218_ca23_lecture_seule_sans_bouton() -> None:
    """CA23 — en lecture seule, aucun geste : BoutonGeste se tait, l'onglet aussi."""
    assert "if (!peutEnregistrer(potagerActif?.role)) return null" in _lire("components/BoutonGeste.jsx")
    onglet = _lire("components/OngletParcours.jsx")
    assert "const ecriture = peutEnregistrer(potagerActif?.role)" in onglet
    assert "if (!ecriture || !gestes.length) return null" in onglet


# ── CA22, CA24 — container queries, tableau sémantique ──────────────────────

def test_us218_ca22_container_queries_sans_breakpoint() -> None:
    """CA22 — container queries pour le composant, aucun breakpoint d'écran."""
    onglet = _lire("components/OngletParcours.jsx")
    assert "@container/parcours" in onglet and "@[48rem]/parcours:hidden" in onglet
    for bp in (" sm:", " md:", " lg:", " xl:"):
        assert bp not in onglet, bp


def test_us218_ca24_tableau_semantique() -> None:
    """CA24 — un tableau : lignes = pépinières, colonnes = stades ; étiquettes focalisables et nommées."""
    onglet = _lire("components/OngletParcours.jsx")
    for repere in ("<table", '<th scope="row"', '<th key={c.cle} scope="col"', "tabIndex={0}",
                   "aria-label={nomAccessible(etiquette)}", 'role="tablist"'):
        assert repere in onglet, repere


def test_us218_monthstrip_non_modifie() -> None:
    """Notes — `MonthStrip` n'est pas touché par l'onglet."""
    for chemin in ("components/OngletParcours.jsx", "lib/parcours.js"):
        assert "MonthStrip" not in _lire(chemin)


# ── CA26, CA27 — lib testée, page de contrôle ───────────────────────────────

def test_us218_ca26_lib_sans_react_couverte() -> None:
    """CA26 — la lib n'importe pas React et a ses tests `npm test`."""
    assert "react" not in _lire("lib/parcours.js").lower()
    assert (SRC / "lib" / "parcours.test.js").exists()


def test_us218_ca27_page_de_controle_branchee() -> None:
    """CA27 — la page de contrôle visuel est routée et rejoue les états demandés."""
    assert "'/pepiniere-parcours'" in _lire("main.jsx")
    page = _lire("views/_PepiniereParcoursPreview.jsx")
    for etat in ("nominal", "hf", "une_pepiniere", "pepiniere_vide", "aucun_lot", "sans_semer",
                 "lecture_seule", "chargement", "echec"):
        assert f"'{etat}'" in page, etat
    # Retard, « Durée ? », pépinière froide, lot coupé, étiquette sans emplacement.
    for cas in ("repiquer_retard", "duree_inconnue", "endurcit_sur_place", "1, 2)", "'godet', null, 'en_cours'"):
        assert cas in page, cas


# ── CA30 — corpus et documentation ──────────────────────────────────────────

def test_us218_ca30_corpus_decrit_le_parcours() -> None:
    """CA30 — la fiche jardinier décrit l'onglet et ne parle plus des onglets retirés."""
    fiche = (RACINE / "data" / "connaissance" / "doc_app" / "pepiniere-par-lot.md").read_text(encoding="utf-8")
    for mot in ("onglet **Ma pépinière**", "En levée", "En godet", "Endurcissement", "Prêt à sortir",
                "Le bon moment pour semer", "lots dormants", "1/2", "onglet **Lots**"):
        assert mot in fiche, mot
    for retire in ("onglet **Aujourd'hui**", "onglet **Calendrier**", "onglet **Emplacements**"):
        assert retire not in fiche, retire


@pytest.mark.parametrize("fichier", ["docs/domaines/pepiniere.md", "docs/domaines/README.md"])
def test_us218_fiche_de_domaine_a_jour(fichier: str) -> None:
    """La fiche de domaine et sa table nomment l'onglet."""
    texte = (RACINE / fichier).read_text(encoding="utf-8")
    assert "OngletParcours" in texte
    assert "OngletCalendrier" not in texte and "OngletAujourdhui" not in texte


# ── Maquette HF, option B — la fiche en bandeau sous la rangée ──────────────

def test_us218_ca20_fiche_en_bandeau_sous_la_rangee() -> None:
    """CA20 / HF option B — au large, la fiche s'ouvre dans une ligne du tableau, sous la rangée."""
    onglet = _lire("components/OngletParcours.jsx")
    assert "<FicheLotBandeau" in onglet and "cleLigneDe(ouvert.etiquette) === l.cle" in onglet
    assert "colSpan={STADES.length + 1}" in onglet
    vue = _lire("views/Pepiniere.jsx")
    assert "const LARGEUR_BANDEAU = 768" in vue
    assert "etiquetteOuverte(data?.parcours, fiche.lot_id, etiquetteChoisie)" in vue
    # [US-242] Sur « Lots », la fiche se déplie sous la ligne : la fenêtre ne sert qu'au parcours.
    assert "const enFenetre = fiche != null && !enBandeau && onglet === 'parcours'" in vue


def test_us218_ca20_bandeau_reutilise_les_regles_de_la_fiche() -> None:
    """CA14 / US-216 CA15 — le bandeau tire ses gestes de `gestesDuLot`, sans règle à lui."""
    fiche = _lire("components/FicheLot.jsx")
    debut = fiche.index("export function FicheLotBandeau")
    bandeau = fiche[debut:]
    assert "gestesDuLot(lot, { nbPepinieres })" in bandeau
    assert "peutEnregistrer(potagerActif?.role)" in bandeau
    assert "<BoutonGeste" in bandeau and "api." not in bandeau

"""
tests/test_us348_fiches_cultures_courantes.py
[US-348] Rédiger et ingérer les fiches agronomiques des cultures courantes manquantes

Comme pour US-140, le livrable est du CONTENU : ces tests lisent les fiches RÉELLES
de `data/connaissance/agronomie/`, jamais un corpus de laboratoire. Les refus
éditoriaux (CA3 : ni dose, ni produit, ni chiffre) sont ceux de
`tools/controler_corpus_agronomie.py`, qui est l'outil de relecture du déploiement.
"""
import json
import re
from pathlib import Path

import pytest

from app.services import connaissance
from app.services.context import TenantContext
from database.models import CultureConfig, KnowledgeChunk, Potager, User
from tools import controler_corpus_agronomie as controle
from tools import ingerer_connaissance as ing

RACINE = Path(__file__).resolve().parents[1]
CORPUS = RACINE / "data" / "connaissance" / "agronomie"
JEU = RACINE / "tests" / "corpus" / "jeu_evaluation_compagnon.json"
CTX = TenantContext(user_id=1, potager_id=1, role="owner")

#: slug du fichier → nom exact de `culture_config`, type d'organe (tableau de l'US)
CULTURES: dict[str, tuple[str, str]] = {
    "salade": ("salade", "végétatif"),
    "mache": ("mâche", "végétatif"),
    "radis": ("radis", "végétatif"),
    "epinard": ("épinard", "végétatif"),
    "poireau": ("poireau", "végétatif"),
    "oignon": ("oignon", "végétatif"),
    "betterave": ("betterave", "végétatif"),
    "pomme-de-terre": ("pomme de terre", "végétatif"),
    "petit-pois": ("petit pois", "reproducteur"),
    "fraise": ("fraise", "reproducteur"),
}
REPRODUCTRICES = [slug for slug, (_, organe) in CULTURES.items() if organe == "reproducteur"]


@pytest.fixture
def base(test_db):
    test_db.add(User(id=1, email="a@potager.test"))
    test_db.flush()
    test_db.add(Potager(id=1, nom="Jardin A", proprietaire_id=1))
    anciennes = ("tomate", "haricot", "courgette", "chou", "carotte", "concombre", "cornichon", "poivron", "ail", "blette")
    for nom, organe in [*CULTURES.values(), *[(n, "reproducteur") for n in anciennes]]:
        test_db.add(CultureConfig(nom=nom, type_organe_recolte=organe, potager_id=None))
    test_db.commit()
    return test_db


@pytest.fixture
def corpus(base):
    rapport = ing.Rapport()
    for chemin in sorted(CORPUS.rglob("*.md")):
        if chemin.name.upper() != "README.MD":
            ing.ingerer_fichier(base, chemin, RACINE, rapport)
    assert not rapport.erreurs, rapport.erreurs
    return base


def _fiche(slug: str, theme: str):
    return controle.lire_fiche(CORPUS / f"{slug}-{theme}.md")


# ── CA1 ──────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("slug", CULTURES)
def test_ca1_chaque_culture_a_sa_fiche_de_conduite_et_de_problemes(slug):
    for theme in ("conduite-recolte", "problemes"):
        fiche = _fiche(slug, theme)
        assert fiche.entete["culture"] == CULTURES[slug][0]
        assert fiche.theme == theme and fiche.culture == slug
        assert len(fiche.sections) >= 4


def test_ca1_le_controle_lit_le_theme_comme_un_suffixe():
    """Une culture à tirets ne perd pas la moitié de son nom."""
    assert controle._decouper_nom("pomme-de-terre-problemes") == ("pomme-de-terre", "problemes")
    assert controle._decouper_nom("petit-pois-conduite-recolte") == ("petit-pois", "conduite-recolte")
    assert controle._decouper_nom("tomate-problemes") == ("tomate", "problemes")


def test_ca1_les_fiches_sont_rattachees_a_leur_culture_en_base(corpus):
    for slug, (nom, _) in CULTURES.items():
        culture_id = corpus.query(CultureConfig.id).filter(CultureConfig.nom == nom).scalar()
        fragments = (corpus.query(KnowledgeChunk)
                     .filter(KnowledgeChunk.reference.like(f"%agronomie/{slug}-%")).all())
        assert fragments, f"aucun fragment pour {slug}"
        assert {f.culture_id for f in fragments} == {culture_id}, slug


# ── CA2 ──────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("slug", CULTURES)
def test_ca2_la_conduite_s_ouvre_sur_le_cycle_de_vie(slug):
    premiere = _fiche(slug, "conduite-recolte").sections[0]
    assert premiere.metadonnees["intention"] == "cycle"
    texte = premiere.contenu.lower()
    assert "récolte" in texte
    assert "plant" in texte or "sème" in texte


@pytest.mark.parametrize("slug", REPRODUCTRICES)
def test_ca2_une_culture_reproductive_dit_que_la_recolte_est_repetee(slug):
    assert "récolte répétée" in _fiche(slug, "conduite-recolte").sections[0].contenu.lower()


def test_ca2_pomme_de_terre_et_petit_pois_ne_passent_pas_par_un_godet():
    assert "pas de godet" in _fiche("pomme-de-terre", "conduite-recolte").sections[0].contenu
    assert "sans godet" in _fiche("petit-pois", "conduite-recolte").sections[0].contenu


# ── CA3 ──────────────────────────────────────────────────────────────────────
def test_ca3_aucune_dose_aucun_produit_et_les_sources_sont_citees():
    rapport, fiches = controle.controler(CORPUS, tuple(CULTURES))
    assert rapport.conforme, rapport.refus
    for slug in CULTURES:
        for theme in ("conduite-recolte", "problemes"):
            brut = (CORPUS / f"{slug}-{theme}.md").read_text(encoding="utf-8")
            assert "## Sources et licence" in brut
            assert "Ephytia" in brut and "propriétaire" in brut


# ── CA4 ──────────────────────────────────────────────────────────────────────
QUESTIONS = {
    "poireau": "quand butter mes poireaux ?",
    "salade": "mes salades montent en graine",
    "mache": "ma mâche ne lève pas",
    "radis": "mes radis sont creux",
    "epinard": "mes épinards montent en graine",
    "oignon": "comment faire sécher mes oignons ?",
    "betterave": "mes betteraves restent petites",
    "pomme-de-terre": "mes pommes de terre ont du mildiou",
    "petit-pois": "comment cueillir mes petits pois ?",
    "fraise": "mes fraises pourrissent avec de la moisissure grise",
}


@pytest.mark.parametrize("slug,question", QUESTIONS.items())
def test_ca4_la_recherche_rattachee_a_la_culture_ne_rend_que_cette_culture(corpus, slug, question):
    """Gherkin : « aucun passage d'une autre culture n'est montré »."""
    contexte = connaissance.rechercher(corpus, CTX, question, domaine="jardinage", limite=5)
    assert contexte.references, f"« {question} » ne retrouve rien"
    autres = [r for r in contexte.references if f"agronomie/{slug}-" not in r]
    assert not autres, f"« {question} » rend aussi {autres}"
    assert contexte.passages[0].source == "Assistant Potager — rédaction interne"


# ── CA5 ──────────────────────────────────────────────────────────────────────
def test_ca5_la_carte_de_couverture_dit_ce_que_le_dossier_contient():
    lisez_moi = (CORPUS / "README.md").read_text(encoding="utf-8")
    carte = lisez_moi.split("### Carte de couverture", 1)[1].split("\n\n", 2)[1]
    lignes = [ligne for ligne in carte.splitlines() if ligne.startswith("| ") and "✅" in ligne]
    cultures_carte = {ligne.split("|")[1].strip() for ligne in lignes}
    attendues = {fiche.entete["culture"] for fiche in
                 (controle.lire_fiche(c) for c in CORPUS.glob("*.md") if c.name != "README.md")}
    assert cultures_carte == attendues
    for slug in CULTURES:
        assert f"`{slug}-problemes.md`" in lisez_moi and f"`{slug}-conduite-recolte.md`" in lisez_moi


# ── CA6 ──────────────────────────────────────────────────────────────────────
def test_ca6_les_cas_culture_sans_fiche_ne_portent_que_des_cultures_sans_fiche():
    couvertes = {nom for nom, _ in CULTURES.values()} | {
        f.entete["culture"] for f in (controle.lire_fiche(c) for c in CORPUS.glob("*.md") if c.name != "README.md")}
    jeu = json.loads(JEU.read_text(encoding="utf-8"))
    for besoin in jeu["besoins"]:
        if besoin["attendus"].get("couverture_absente"):
            cultures = {besoin["fiche"].get("culture")} | {
                (f.get("fiche") or {}).get("culture") for f in besoin["formulations"]}
            assert not (cultures & couvertes), (besoin["id"], cultures & couvertes)
        for f in besoin["formulations"]:
            if f.get("couverture_absente"):
                assert (f.get("fiche") or {}).get("culture") not in couvertes
    texte = JEU.read_text(encoding="utf-8")
    assert not re.search(r"n'a pas de fiche \(salade\)", texte)

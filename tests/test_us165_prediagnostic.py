"""
tests/test_us165_prediagnostic.py
[US-165] Proposer un pré-diagnostic déterministe à partir des symptômes décrits

Couverture des critères d'acceptance CA1 → CA15.

Ce que ce fichier vérifie STRUCTURELLEMENT plutôt que par une consigne :
- **CA7 (aucune prescription)** — l'absence de colonne où stocker un dosage ou un
  produit, contrôlée sur le modèle lui-même. Une consigne de rédaction se perd ;
  une colonne qui n'existe pas ne se remplit jamais.
- **CA9 (aucun appel modèle)** — réseau coupé ET passerelle LLM sous surveillance
  pendant le pré-diagnostic, comme US-162 le fait pour son propre « zéro jeton ».
  L'absence d'import de client Groq est vérifiée en plus, pas à la place.
- **CA4 (« cela peut évoquer », jamais « c'est »)** — les textes réellement
  produits sont passés au crible des tournures affirmatives, sur tout le corpus.

La mesure du CA11/CA12 est ici et non seulement dans `tools/mesurer_prediagnostic.py` :
elle porte sur le référentiel RÉELLEMENT versionné (les trois manifestes du
dépôt), et c'est ce qui la rend opposable. Elle tourne sur le repli SQLite —
la mesure qui décide de l'activation en production (CA13) doit être rejouée
contre PostgreSQL, ce que l'outil rappelle dans son propre rapport.
"""
import csv
import json
import socket
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services import bioagresseurs as svc_bio
from app.services import catalogue_sql
from app.services import connaissance
from app.services import import_referentiel as svc_import
from app.services import prediagnostic as svc_pre
from app.services import referentiel_sources as svc_sources
from app.services import reponses_chiffrees as rc
from app.services.context import TenantContext
from database.models import CultureConfig, Symptome, SymptomeBioagresseur

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
AUTRE_POTAGER = 2

RACINE = Path(__file__).resolve().parent.parent
CORPUS = RACINE / "tests" / "corpus" / "us165_prediagnostic.csv"

#: Les trois manifestes du dépôt, DANS L'ORDRE DES DÉPENDANCES — identiques à
#: `tools.mesurer_prediagnostic.MANIFESTES_PAR_DEFAUT`. Les rejouer ici fait
#: porter la mesure sur le référentiel réellement livré, pas sur un jeu d'essai
#: taillé pour réussir.
MANIFESTES = (
    "data/referentiel/eppo/bioagresseurs_eppo.json",
    "data/referentiel/bioagresseurs_redaction_interne_complet.json",
    "data/referentiel/symptomes_redaction_interne.json",
)

#: `blette` et `laitue` sont les libellés d'une source, pas des cultures de
#: `culture_config` (qui porte `bette` et `salade` — migration_v5/v6). Ne pas les
#: créer ici est ce qui rend le test fidèle : l'import doit les compter « en
#: attente de revue humaine » (US-162 / CA9), exactement comme en production.
LIBELLES_ABSENTS_DU_REFERENTIEL = {"blette", "laitue"}

TAUX_RAPPEL_CIBLE = 0.80


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def db(test_db):
    svc_sources.semer_sources_socle(test_db)
    return test_db


def _seed_culture(db, nom, potager_id=None):
    fiche = CultureConfig(nom=nom, type_organe_recolte="vegetatif", potager_id=potager_id)
    db.add(fiche)
    db.commit()
    return fiche


def _charger_corpus() -> list[dict]:
    with CORPUS.open(encoding="utf-8", newline="") as fichier:
        return [l for l in csv.DictReader(fichier) if (l.get("description") or "").strip()]


@pytest.fixture(scope="module")
def corpus() -> list[dict]:
    return _charger_corpus()


@pytest.fixture
def referentiel(db):
    """Le référentiel RÉEL du dépôt, importé dans la base de test.

    Coûteux (trois manifestes, ~600 lignes écrites) mais indispensable : mesurer
    le rappel sur un jeu d'essai écrit pour l'occasion ne dirait rien de ce que
    le jardinier recevra.
    """
    noms = set()
    for chemin in MANIFESTES:
        manifeste = json.loads((RACINE / chemin).read_text(encoding="utf-8"))
        for arete in manifeste.get("cultures_bioagresseurs") or []:
            noms.add(arete["culture"])
    noms -= LIBELLES_ABSENTS_DU_REFERENTIEL
    noms |= {ligne["culture"] for ligne in _charger_corpus()}
    for nom in sorted(noms):
        db.add(CultureConfig(nom=nom, type_organe_recolte="vegetatif"))
    db.commit()

    for chemin in MANIFESTES:
        svc_import.importer_fichier(db, RACINE / chemin)
    return db


@pytest.fixture
def symptome_taches(db):
    """Un symptôme minimal et ses deux pistes, pour les tests unitaires."""
    _seed_culture(db, "tomate")
    _seed_culture(db, "carotte")
    for nom, categorie in (
        ("mildiou de la tomate", "champignon"),
        ("alternariose", "champignon"),
        ("mildiou de la carotte", "champignon"),
    ):
        svc_bio.enregistrer_bioagresseur(db, nom, categorie)
    svc_bio.rattacher(db, "tomate", "mildiou de la tomate", "courant")
    svc_bio.rattacher(db, "tomate", "alternariose", "occasionnel")
    svc_bio.rattacher(db, "carotte", "mildiou de la carotte", "courant")

    svc_pre.enregistrer_symptome(
        db,
        "des taches brunes sur les feuilles",
        svc_pre.ORGANE_FEUILLE,
        synonymes="taches marron ; feuillage brûlé ; taches après la pluie",
    )
    svc_pre.rattacher(db, "des taches brunes sur les feuilles", "mildiou de la tomate", 0.9)
    svc_pre.rattacher(db, "des taches brunes sur les feuilles", "alternariose", 0.5)
    svc_pre.rattacher(db, "des taches brunes sur les feuilles", "mildiou de la carotte", 0.9)
    return db


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — Libellé, organe atteint, et surtout des SYNONYMES en langage courant
# ═════════════════════════════════════════════════════════════════════════════
def test_us165_ca1_un_symptome_porte_libelle_organe_et_synonymes(db):
    symptome, cree = svc_pre.enregistrer_symptome(
        db, "Un dépôt blanc poudreux", svc_pre.ORGANE_FEUILLE,
        synonymes="poudre blanche ; oïdium ; feuilles farineuses",
    )
    assert cree
    assert symptome.libelle == "Un dépôt blanc poudreux"
    assert symptome.libelle_normalise == "un depot blanc poudreux"
    assert symptome.organe == svc_pre.ORGANE_FEUILLE
    assert "poudre blanche" in symptome.synonymes
    # Le vecteur est maintenu À L'ÉCRITURE : un symptôme inséré sans lui serait
    # en base et introuvable.
    assert symptome.recherche_fts


def test_us165_ca1_les_synonymes_font_trouver_le_symptome(db):
    """LE critère de l'US : « poudre blanche » doit retrouver un symptôme dont
    le libellé ne contient ni « poudre » ni « blanche » en ces termes."""
    svc_pre.enregistrer_symptome(
        db, "un revêtement pulvérulent clair sur le limbe", svc_pre.ORGANE_FEUILLE,
        synonymes="poudre blanche ; oïdium ; feuilles farineuses ; blanc sur le feuillage",
    )
    trouves = svc_pre.rechercher_symptomes(db, "mes courgettes ont de la poudre blanche")
    assert trouves and trouves[0].score >= svc_pre.PREDIAGNOSTIC_SEUIL_SYMPTOME


def test_us165_ca1_organe_hors_vocabulaire_refuse(db):
    with pytest.raises(svc_pre.ValeurSymptomeInvalideError):
        svc_pre.enregistrer_symptome(db, "des taches", "pédoncule")


def test_us165_ca1_libelle_vide_refuse(db):
    with pytest.raises(svc_pre.ValeurSymptomeInvalideError):
        svc_pre.enregistrer_symptome(db, "   ", svc_pre.ORGANE_FEUILLE)


def test_us165_ca1_un_symptome_n_appartient_a_aucune_culture():
    """Décision de conception centrale : c'est le CROISEMENT qui décide de la
    piste, pas le symptôme. Une colonne `culture_id` ici rendrait la
    désambiguïsation du CA14 structurellement impossible."""
    colonnes = {c.name for c in Symptome.__table__.columns}
    assert not any("culture" in nom for nom in colonnes)


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — La relation est PONDÉRÉE, et le poids ne se montre jamais
# ═════════════════════════════════════════════════════════════════════════════
def test_us165_ca2_le_poids_est_stocke(symptome_taches):
    arete = (
        symptome_taches.query(SymptomeBioagresseur)
        .join(Symptome, SymptomeBioagresseur.symptome_id == Symptome.id)
        .first()
    )
    assert 0 < arete.poids <= 1


@pytest.mark.parametrize("poids", [0, -0.1, 1.5, "beaucoup"])
def test_us165_ca2_poids_hors_bornes_refuse(symptome_taches, poids):
    with pytest.raises(svc_pre.ValeurSymptomeInvalideError):
        svc_pre.rattacher(
            symptome_taches, "des taches brunes sur les feuilles",
            "mildiou de la tomate", poids,
        )


def test_us165_ca2_le_poids_ne_sort_jamais_du_service(symptome_taches):
    """« jamais un pourcentage affiché comme tel au jardinier » — la garantie
    n'est pas une consigne de rendu : `Piste` ne porte aucun champ de poids, donc
    aucun appelant ne peut en afficher un."""
    resultat = svc_pre.prediagnostic(
        symptome_taches, "mes tomates ont des taches marron sur les feuilles", "tomate",
    )
    assert resultat.pistes
    for piste in resultat.pistes:
        assert not hasattr(piste, "poids")
        assert not hasattr(piste, "plausibilite")


def test_us165_ca2_aucun_pourcentage_dans_le_texte_servi(symptome_taches, monkeypatch):
    monkeypatch.setattr(rc, "SessionLocal", lambda: symptome_taches)
    reponse = rc.repondre_chiffre(
        CTX, "mes tomates ont des taches marron sur les feuilles", db=symptome_taches,
    )
    assert reponse is not None
    assert "%" not in reponse.texte


def test_us165_ca2_le_poids_ordonne_les_pistes(symptome_taches):
    resultat = svc_pre.prediagnostic(
        symptome_taches, "mes tomates ont des taches marron sur les feuilles", "tomate",
    )
    noms = [p.bioagresseur for p in resultat.pistes]
    assert noms.index("mildiou de la tomate") < noms.index("alternariose")


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — Le croisement avec les bioagresseurs de CETTE culture
# ═════════════════════════════════════════════════════════════════════════════
def test_us165_ca3_un_mildiou_d_une_autre_culture_n_est_pas_propose(symptome_taches):
    """Le scénario Gherkin « Croisement avec la culture », mot pour mot."""
    resultat = svc_pre.prediagnostic(
        symptome_taches, "des taches marron sur les feuilles de mes carottes", "carotte",
    )
    noms = [p.bioagresseur for p in resultat.pistes]
    assert "mildiou de la carotte" in noms
    assert "mildiou de la tomate" not in noms
    assert "alternariose" not in noms


def test_us165_ca3_culture_hors_referentiel(symptome_taches):
    """Scénario Gherkin « Culture hors périmètre »."""
    resultat = svc_pre.prediagnostic(
        symptome_taches, "des taches marron sur les feuilles", "quinoa",
    )
    assert resultat.issue == svc_pre.ISSUE_CULTURE_SANS_FICHE
    assert resultat.pistes == ()


def test_us165_ca3_culture_connue_sans_aucun_bioagresseur_rattache(symptome_taches):
    """Symptôme reconnu, culture connue, aucun croisement — une TROISIÈME
    ignorance, distincte des deux autres. Les confondre trompe le jardinier."""
    _seed_culture(symptome_taches, "topinambour")
    resultat = svc_pre.prediagnostic(
        symptome_taches, "des taches marron sur les feuilles", "topinambour",
    )
    assert resultat.issue == svc_pre.ISSUE_AUCUN_CROISEMENT
    assert resultat.symptome  # le symptôme, lui, a bien été reconnu
    assert resultat.pistes == ()


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — « cela peut évoquer », jamais « c'est » (critère bloquant)
# ═════════════════════════════════════════════════════════════════════════════
#: Tournures qui feraient d'une piste un diagnostic. Testées sur les textes
#: RÉELLEMENT produits, jamais sur les gabarits seuls : c'est l'assemblage qui
#: parvient au jardinier.
TOURNURES_AFFIRMATIVES = (
    " c'est ", " ce sont ", "il s'agit", "tu as ", "vous avez ",
    "diagnostic", "à coup sûr", "certainement", "sans aucun doute",
)


def test_us165_ca4_la_formule_est_dans_le_texte_servi(symptome_taches, monkeypatch):
    monkeypatch.setattr(rc, "SessionLocal", lambda: symptome_taches)
    reponse = rc.repondre_chiffre(
        CTX, "mes tomates ont des taches marron sur les feuilles", db=symptome_taches,
    )
    assert svc_pre.FORMULE_EVOCATION in reponse.texte


def test_us165_ca4_aucune_tournure_affirmative_sur_tout_le_corpus(referentiel, corpus, monkeypatch):
    monkeypatch.setattr(rc, "SessionLocal", lambda: referentiel)
    fautes = []
    for entree in corpus:
        reponse = rc.repondre_chiffre(CTX, entree["description"], db=referentiel)
        if reponse is None:
            continue
        minuscule = f" {reponse.texte.lower()} "
        for tournure in TOURNURES_AFFIRMATIVES:
            if tournure in minuscule:
                fautes.append((entree["numero"], tournure))
    assert not fautes, f"tournures affirmatives servies : {fautes}"


def test_us165_ca4_la_formule_n_est_ecrite_qu_a_un_endroit():
    """La prudence ne peut pas être une intention de rédaction répartie : elle
    vit dans `FORMULE_EVOCATION`, et les gabarits la CONCATÈNENT."""
    source = (RACINE / "app" / "services" / "reponses_chiffrees.py").read_text(encoding="utf-8")
    assert source.count(f'"{svc_pre.FORMULE_EVOCATION}"') == 0
    assert source.count("svc_prediagnostic.FORMULE_EVOCATION") >= 2


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — Deux à trois hypothèses, jamais une seule qui se lise comme une conclusion
# ═════════════════════════════════════════════════════════════════════════════
def test_us165_ca5_au_plus_trois_pistes(referentiel, corpus):
    for entree in corpus:
        resultat = svc_pre.prediagnostic(
            referentiel, entree["description"], entree["culture"],
        )
        assert len(resultat.pistes) <= svc_pre.PREDIAGNOSTIC_MAX_PISTES


def test_us165_ca5_une_piste_unique_est_dite_comme_telle(symptome_taches, monkeypatch):
    """L'US exige deux à trois hypothèses. Quand le croisement n'en produit
    qu'une, on ne fabrique pas la seconde : on DIT que la piste est seule, pour
    qu'elle ne se lise pas comme une conclusion."""
    monkeypatch.setattr(rc, "SessionLocal", lambda: symptome_taches)
    resultat = svc_pre.prediagnostic(
        symptome_taches, "des taches marron sur les feuilles de mes carottes", "carotte",
    )
    assert resultat.issue == svc_pre.ISSUE_PISTE_UNIQUE
    reponse = rc.repondre_chiffre(
        CTX, "des taches marron sur les feuilles de mes carottes", db=symptome_taches,
    )
    assert svc_pre.MESSAGE_PISTE_UNIQUE in reponse.texte
    assert "ne la lis pas comme une conclusion" in reponse.texte


def test_us165_ca5_plusieurs_pistes_sont_ordonnees_sans_chiffre(symptome_taches, monkeypatch):
    monkeypatch.setattr(rc, "SessionLocal", lambda: symptome_taches)
    reponse = rc.repondre_chiffre(
        CTX, "mes tomates ont des taches marron sur les feuilles", db=symptome_taches,
    )
    lignes = [l for l in reponse.texte.split("\n") if l.strip().startswith("•")]
    assert len(lignes) >= 2
    assert not any(car.isdigit() for ligne in lignes for car in ligne)


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — Chaque piste renvoie à sa source, et la réserve suit le contenu non relu
# ═════════════════════════════════════════════════════════════════════════════
def test_us165_ca6_la_source_est_citee(symptome_taches, monkeypatch):
    monkeypatch.setattr(rc, "SessionLocal", lambda: symptome_taches)
    reponse = rc.repondre_chiffre(
        CTX, "mes tomates ont des taches marron sur les feuilles", db=symptome_taches,
    )
    assert "D'après" in reponse.texte


def test_us165_ca6_une_piste_indicative_porte_la_reserve(symptome_taches, monkeypatch):
    monkeypatch.setattr(rc, "SessionLocal", lambda: symptome_taches)
    reponse = rc.repondre_chiffre(
        CTX, "mes tomates ont des taches marron sur les feuilles", db=symptome_taches,
    )
    # La réserve est celle d'US-140/CA8, mot pour mot — jamais une variante.
    assert connaissance.RESERVE_INDICATIF in reponse.texte


def test_us165_ca6_une_piste_verifiee_ne_porte_aucune_reserve(symptome_taches):
    for nom in ("mildiou de la tomate", "alternariose"):
        svc_pre.rattacher(
            symptome_taches, "des taches brunes sur les feuilles", nom, 0.9,
            niveau_confiance=svc_pre.NIVEAU_VERIFIE,
        )
    resultat = svc_pre.prediagnostic(
        symptome_taches, "mes tomates ont des taches marron sur les feuilles", "tomate",
    )
    assert resultat.reserve == ""


def test_us165_ca6_niveau_de_confiance_hors_vocabulaire_refuse(symptome_taches):
    with pytest.raises(svc_pre.ValeurSymptomeInvalideError):
        svc_pre.rattacher(
            symptome_taches, "des taches brunes sur les feuilles",
            "mildiou de la tomate", 0.9, niveau_confiance="probable",
        )


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — Aucun dosage, aucune recommandation de produit
# ═════════════════════════════════════════════════════════════════════════════
def test_us165_ca7_aucune_colonne_de_prescription():
    """La garantie est STRUCTURELLE : il n'existe aucune colonne où stocker un
    dosage ou un produit, donc rien à restituer. Même contrôle que
    migration_v43 pour les tables d'US-162."""
    interdits = ("dose", "produit", "traitement", "posologie", "dilution")
    for table in (Symptome.__table__, SymptomeBioagresseur.__table__):
        for colonne in table.columns:
            assert not any(mot in colonne.name.lower() for mot in interdits), colonne.name


def test_us165_ca7_aucun_vocabulaire_de_traitement_dans_les_reponses(referentiel, corpus, monkeypatch):
    monkeypatch.setattr(rc, "SessionLocal", lambda: referentiel)
    interdits = ("bouillie bordelaise", "cuivre", "pulvéris", " dose ", "ml/l", "g/l",
                 "insecticide", "fongicide", "traiter avec")
    fautes = []
    for entree in corpus:
        reponse = rc.repondre_chiffre(CTX, entree["description"], db=referentiel)
        if reponse is None:
            continue
        minuscule = f" {reponse.texte.lower()} "
        fautes += [(entree["numero"], mot) for mot in interdits if mot in minuscule]
    assert not fautes, f"vocabulaire de traitement servi : {fautes}"


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — Un symptôme non reconnu produit un refus, jamais une piste forcée
# ═════════════════════════════════════════════════════════════════════════════
def test_us165_ca8_symptome_inconnu(symptome_taches):
    """Scénario Gherkin « Symptôme non reconnu »."""
    resultat = svc_pre.prediagnostic(
        symptome_taches, "mes tomates chantent la nuit quand il pleut", "tomate",
    )
    assert resultat.issue == svc_pre.ISSUE_SYMPTOME_INCONNU
    assert resultat.pistes == ()
    assert resultat.symptome is None


def test_us165_ca8_le_refus_est_explicite_et_ne_propose_rien(symptome_taches, monkeypatch):
    monkeypatch.setattr(rc, "SessionLocal", lambda: symptome_taches)
    reponse = rc.repondre_chiffre(
        CTX, "mes tomates ont des trous carrés fluorescents", db=symptome_taches,
    )
    assert reponse is not None
    assert svc_pre.MESSAGE_SYMPTOME_INCONNU == reponse.texte
    assert "•" not in reponse.texte


def test_us165_ca8_les_trois_ignorances_ont_trois_messages_distincts():
    messages = {
        svc_pre.MESSAGE_SYMPTOME_INCONNU,
        svc_pre.MESSAGE_CULTURE_SANS_FICHE,
        svc_pre.MESSAGE_AUCUN_CROISEMENT,
    }
    assert len(messages) == 3
    # Aucune des trois ne doit se lire comme une absence de RISQUE.
    for message in (svc_pre.MESSAGE_CULTURE_SANS_FICHE, svc_pre.MESSAGE_AUCUN_CROISEMENT):
        assert "absence de risque" in message


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — Déterministe et sans appel au modèle
# ═════════════════════════════════════════════════════════════════════════════
def test_us165_ca9_le_module_n_importe_aucun_client_llm():
    """Contrôle sur les seules lignes d'IMPORT, et non sur le fichier entier :
    la docstring du module NOMME ce qu'il n'importe pas, et un test qui balaierait
    tout le texte échouerait sur sa propre documentation."""
    source = (RACINE / "app" / "services" / "prediagnostic.py").read_text(encoding="utf-8")
    imports = [
        ligne for ligne in source.splitlines()
        if ligne.startswith("import ") or ligne.startswith("from ")
    ]
    for ligne in imports:
        for interdit in ("groq", "llm", "httpx", "openai", "requests"):
            assert interdit not in ligne, ligne


def test_us165_ca9_aucun_appel_reseau_ni_passerelle(symptome_taches):
    """Scénario Gherkin « Pré-diagnostic sans jeton ». Réseau coupé ET passerelle
    surveillée : l'absence d'import ne prouve pas l'absence d'appel."""
    def _refuser(*args, **kwargs):
        raise AssertionError("appel réseau pendant un pré-diagnostic")

    with patch.object(socket.socket, "connect", _refuser), \
         patch("llm.passerelle.appeler_chat") as appel:
        resultat = svc_pre.prediagnostic(
            symptome_taches, "mes tomates ont des taches marron sur les feuilles", "tomate",
        )
    assert resultat.pistes
    appel.assert_not_called()


def test_us165_ca9_le_resultat_est_deterministe(symptome_taches):
    premier = svc_pre.prediagnostic(
        symptome_taches, "mes tomates ont des taches marron sur les feuilles", "tomate",
    )
    for _ in range(3):
        suivant = svc_pre.prediagnostic(
            symptome_taches, "mes tomates ont des taches marron sur les feuilles", "tomate",
        )
        assert [p.bioagresseur for p in suivant.pistes] == [p.bioagresseur for p in premier.pistes]
        assert suivant.score == premier.score


# ═════════════════════════════════════════════════════════════════════════════
# CA10 — Rattaché à l'action canonique `observation`, aucun type ajouté
# ═════════════════════════════════════════════════════════════════════════════
def test_us165_ca10_aucun_type_d_action_ajoute():
    from utils.actions import ACTION_MAP

    assert "observation" in ACTION_MAP
    assert "prediagnostic" not in ACTION_MAP
    assert "symptome" not in ACTION_MAP


def test_us165_ca10_une_saisie_d_observation_n_est_pas_detournee(symptome_taches, monkeypatch):
    """« j'ai observé des taches marron sur mes tomates » RAPPORTE un fait : le
    catalogue doit rendre la main pour que l'évènement s'enregistre."""
    monkeypatch.setattr(rc, "SessionLocal", lambda: symptome_taches)
    assert rc.reconnait_famille(
        CTX, "j'ai observé des taches marron sur mes tomates", db=symptome_taches,
    ) != "prediagnostic_symptome"


# ═════════════════════════════════════════════════════════════════════════════
# CA11 / CA12 — La mesure, sur les DEUX assiettes séparément
# ═════════════════════════════════════════════════════════════════════════════
def test_us165_ca11_le_corpus_porte_bien_19_v1_et_25_hors(corpus):
    assert len(corpus) == 44
    assert sum(1 for l in corpus if l["perimetre"] == "v1") == 19
    assert sum(1 for l in corpus if l["perimetre"] != "v1") == 25


def test_us165_ca11_le_corpus_couvre_les_dix_cultures_du_perimetre(corpus):
    attendues = {
        "tomate", "haricot", "courgette", "chou", "carotte",
        "concombre", "cornichon", "poivron", "ail", "bette",
    }
    assert {l["culture"] for l in corpus if l["perimetre"] == "v1"} == attendues


def test_us165_ca11_rappel_sur_le_perimetre_v1(referentiel, corpus):
    """« La bonne piste figure dans les trois premiers résultats dans au moins
    80 % des cas de l'assiette v1. »"""
    v1 = [l for l in corpus if l["perimetre"] == "v1"]
    manques = []
    for entree in v1:
        resultat = svc_pre.prediagnostic(referentiel, entree["description"], entree["culture"])
        noms = [svc_pre.normaliser_libelle(p.bioagresseur) for p in resultat.pistes]
        if svc_pre.normaliser_libelle(entree["piste_attendue"]) not in noms:
            manques.append((entree["numero"], entree["piste_attendue"], noms))
    taux = (len(v1) - len(manques)) / len(v1)
    assert taux >= TAUX_RAPPEL_CIBLE, f"rappel {taux:.0%} — manques : {manques}"


def test_us165_ca12_honnetete_sur_les_25_entrees_hors_perimetre(referentiel, corpus):
    """Assiette DISTINCTE, question DIFFÉRENTE : non pas « la bonne piste
    sort-elle », mais « l'application refuse-t-elle plutôt que de forcer ». Les
    confondre plafonnerait la mesure du CA11 pour une raison de découpage."""
    hors = [l for l in corpus if l["perimetre"] != "v1"]
    forcees = []
    for entree in hors:
        resultat = svc_pre.prediagnostic(referentiel, entree["description"], entree["culture"])
        if not resultat.pistes:
            continue  # refus explicite : honnête par construction
        noms = [svc_pre.normaliser_libelle(p.bioagresseur) for p in resultat.pistes]
        attendue = svc_pre.normaliser_libelle(entree["piste_attendue"])
        if not attendue or attendue not in noms:
            forcees.append((entree["numero"], entree["piste_attendue"], noms))
    assert not forcees, f"pistes forcées faute de mieux : {forcees}"


def test_us165_ca12_les_deux_assiettes_ne_sont_jamais_confondues():
    """Le corpus DÉCLARE son périmètre ligne à ligne : c'est ce qui rend
    impossible de mesurer les deux ensemble par inadvertance."""
    with CORPUS.open(encoding="utf-8", newline="") as fichier:
        colonnes = csv.DictReader(fichier).fieldnames
    assert "perimetre" in colonnes


# ═════════════════════════════════════════════════════════════════════════════
# CA14 — La désambiguïsation : un symptôme, trois cultures, trois pistes
# ═════════════════════════════════════════════════════════════════════════════
DESCRIPTION_ROUILLE = "des traits orange qui partent en poussière quand je frotte les feuilles"


@pytest.mark.parametrize("culture,attendue", [
    ("ail", "rouille des alliacées"),
    ("poireau", "rouille des alliacées"),
    ("haricot", "rouille du haricot"),
    ("asperge", "rouille de l'asperge"),
])
def test_us165_ca14_desambiguisation_par_la_culture(referentiel, culture, attendue):
    """Le cas volontaire du corpus (#38 poireau / #44 ail), élargi aux deux
    autres rouilles du référentiel. C'est le croisement — et lui seul — qui
    désambiguïse : le symptôme, lui, est le même."""
    resultat = svc_pre.prediagnostic(referentiel, DESCRIPTION_ROUILLE, culture)
    noms = [p.bioagresseur for p in resultat.pistes]
    assert attendue in noms, noms


def test_us165_ca14_les_rouilles_des_autres_cultures_ne_fuient_pas(referentiel):
    resultat = svc_pre.prediagnostic(referentiel, DESCRIPTION_ROUILLE, "ail")
    noms = [p.bioagresseur for p in resultat.pistes]
    assert "rouille du haricot" not in noms
    assert "rouille de l'asperge" not in noms


# ═════════════════════════════════════════════════════════════════════════════
# Isolation par potager — le pattern d'US-162/CA3, réappliqué
# ═════════════════════════════════════════════════════════════════════════════
def test_us165_un_symptome_local_ne_fuit_pas_vers_un_autre_potager(db):
    svc_pre.enregistrer_symptome(
        db, "mes tuteurs sifflent au vent", svc_pre.ORGANE_TIGE,
        synonymes="sifflement ; bruit au vent", potager_id=CTX.potager_id,
    )
    assert svc_pre.get_symptome(db, "mes tuteurs sifflent au vent", potager_id=CTX.potager_id)
    assert svc_pre.get_symptome(db, "mes tuteurs sifflent au vent", potager_id=AUTRE_POTAGER) is None
    assert not svc_pre.rechercher_symptomes(db, "des tuteurs qui sifflent", potager_id=AUTRE_POTAGER)


def test_us165_une_saisie_locale_n_est_jamais_promue_au_partage(db):
    symptome, _ = svc_pre.enregistrer_symptome(
        db, "des feuilles violettes", svc_pre.ORGANE_FEUILLE, potager_id=CTX.potager_id,
    )
    assert symptome.potager_id == CTX.potager_id
    assert svc_pre.get_symptome(db, "des feuilles violettes", potager_id=None) is None


def test_us165_la_garde_du_catalogue_couvre_les_deux_tables():
    """[US-096 / CA11] Les deux tables portent un `potager_id` : une lecture sans
    filtre doit être refusée À L'EXÉCUTION, pas signalée en revue de code."""
    assert "symptome" in catalogue_sql.TABLES_TENANT
    assert "symptome_bioagresseur" in catalogue_sql.TABLES_TENANT


# ═════════════════════════════════════════════════════════════════════════════
# Import — idempotence et non-écrasement de la saisie humaine
# ═════════════════════════════════════════════════════════════════════════════
def _manifeste(**blocs):
    base = {"source": {"code": svc_sources.SOURCE_REDACTION_INTERNE}}
    base.update(blocs)
    return base


def test_us165_import_idempotent(db):
    manifeste = _manifeste(symptomes=[{
        "libelle": "des feuilles grises", "organe": "feuille",
        "synonymes": "gris ; terne",
    }])
    premier = svc_import.importer(db, manifeste)
    second = svc_import.importer(db, manifeste)
    assert premier.symptomes_crees == ["des feuilles grises"]
    assert second.symptomes_crees == []
    assert second.symptomes_ecrits == []


def test_us165_import_ne_fabrique_ni_symptome_ni_bioagresseur(db):
    resultat = svc_import.importer(db, _manifeste(symptomes_bioagresseurs=[{
        "symptome": "un symptôme jamais déclaré",
        "bioagresseur": "un bioagresseur jamais déclaré",
        "poids": 0.8,
    }]))
    assert resultat.suspicions_ignorees == ["un symptôme jamais déclaré → un bioagresseur jamais déclaré"]
    assert db.query(Symptome).count() == 0


def test_us165_import_preserve_la_saisie_humaine(db):
    svc_pre.enregistrer_symptome(
        db, "des feuilles grises", svc_pre.ORGANE_FEUILLE, synonymes="observé chez moi",
    )
    resultat = svc_import.importer(db, {
        "source": {
            "code": svc_sources.SOURCE_WIND_RIVER,
            "libelle": "Wind River Greens",
            "licence": svc_sources.LICENCE_CC_BY,
            "attribution": "Wind River Greens (CC BY 4.0)",
        },
        "symptomes": [{
            "libelle": "des feuilles grises", "organe": "tige", "synonymes": "autre chose",
        }],
    })
    assert resultat.symptomes_preserves == ["des feuilles grises"]
    symptome = svc_pre.get_symptome(db, "des feuilles grises")
    assert symptome.organe == svc_pre.ORGANE_FEUILLE
    assert symptome.synonymes == "observé chez moi"


def test_us165_le_manifeste_du_depot_est_coherent():
    """Une identité déclarée sans aucune arête de culture ne serait jamais
    proposée : elle serait du poids mort, et le manifeste doit le dire."""
    manifeste = json.loads(
        (RACINE / "data" / "referentiel" / "symptomes_redaction_interne.json").read_text(encoding="utf-8")
    )
    declarees = {b["nom_commun_fr"] for b in manifeste["bioagresseurs"]}
    rattachees = {a["bioagresseur"] for a in manifeste["cultures_bioagresseurs"]}
    assert not declarees - rattachees

    libelles = [s["libelle"] for s in manifeste["symptomes"]]
    assert len(libelles) == len(set(libelles))
    for entree in manifeste["symptomes_bioagresseurs"]:
        assert entree["symptome"] in libelles
        assert 0 < entree["poids"] <= 1

"""
tests/test_us140_corpus_agronomique.py
[US-140] Constituer un socle agronomique sur les cultures réellement suivies

Couverture des critères d'acceptance CA1 → CA14 et des dix scénarios Gherkin.

Trois partis pris expliquent la forme de ce fichier, et ils sont les mêmes
qu'en US-099 — pour la même raison : le livrable est du CONTENU.

- **Ces tests lisent les fiches réelles de `data/connaissance/agronomie/`**,
  jamais un corpus de laboratoire. Un test qui ingérerait ses propres fixtures
  passerait au vert avec un corpus de production faux, ce qui est exactement le
  risque que l'US nomme : « une fiche agronomique fausse est plus nuisible
  qu'une fiche absente ».

- **Les refus éditoriaux (CA7, CA7bis, CA9, CA10, CA13) sont délégués à
  `tools/controler_corpus_agronomie.py`.** L'US répète six fois « une fiche qui
  contient ceci est refusée à la relecture » ; une relecture humaine tient cette
  promesse le jour de la livraison, pas six mois plus tard. Les tests vérifient
  ici que l'outil de relecture existe, qu'il refuse ce qu'il doit refuser, et
  que le corpus réel passe.

- **Le CA11 est mesuré, pas affirmé.** Le corpus de questions
  (`tests/corpus/us140_questions_diagnostic.csv`) reprend mot pour mot les
  dix-neuf entrées du périmètre v1 de `docs/CORPUS_QUESTIONS_DIAGNOSTIC_CA11.md`,
  écrites le 25/08/2026 — donc AVANT les fiches. C'est ce qui empêche la mesure
  d'être auto-réalisatrice, contrainte explicite des notes techniques de l'US.

⚠️ Ces tests tournent sur SQLite (`tests/conftest.py`), donc sur le repli de
`app/services/connaissance.py`. Ils protègent la RÉDACTION contre les
régressions ; le classement qui conditionne l'activation en production se
remesure contre PostgreSQL :

    python tools/mesurer_corpus_savoir.py \\
        --corpus tests/corpus/us140_questions_diagnostic.csv \\
        --racine data/connaissance/agronomie --detail
"""
import csv
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services import cache_questions as cq
from app.services import connaissance
from app.services import referentiel_sources
from app.services import reponses_chiffrees as rc
from app.services.context import TenantContext
from database.models import CultureConfig, KnowledgeChunk, KnowledgeDocument, Potager, RoutageLog, User
from llm import routeur
from tools import controler_corpus_agronomie as controle
from tools import ingerer_connaissance as ing

RACINE = Path(__file__).resolve().parents[1]
CORPUS = RACINE / "data" / "connaissance" / "agronomie"
QUESTIONS = RACINE / "tests" / "corpus" / "us140_questions_diagnostic.csv"
LISEZ_MOI = CORPUS / "README.md"
PREFIXE = "data/connaissance/agronomie/"

CTX = TenantContext(user_id=1, potager_id=1, role="owner")

# [CA1] Le périmètre nominatif de l'US, mesuré le 25/08/2026 et repris tel quel
# par `docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md` §3.1. Écrit ici plutôt que
# déduit du dossier : c'est la LISTE DE L'US qui fait foi, et un fichier renommé
# doit casser ce test au lieu de passer inaperçu.
PERIMETRE: tuple[str, ...] = (
    "tomate", "haricot", "courgette", "chou", "carotte",
    "concombre", "cornichon", "poivron", "ail", "blette",
)

# La blette est la seule culture du périmètre dont le libellé du jardinier n'est
# pas celui du référentiel : `culture_config` porte « bette » (semé par
# migration_v6), et les fiches s'y rattachent sous ce nom. Le mot du jardinier,
# lui, est porté par la ligne « On parle aussi de » de chaque section — c'est
# elle, et non l'en-tête, qui décide de ce que la recherche retrouve.
LIBELLE_REFERENTIEL = {"blette": "bette"}

# [CA11] Cible de l'US : la bonne fiche dans les trois premiers résultats.
RANG_CIBLE = 3
TAUX_CIBLE = 0.80


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture(autouse=True)
def _cache_classification_propre():
    routeur.vider_cache()
    yield
    routeur.vider_cache()


@pytest.fixture
def base(test_db):
    """Un potager et les cultures du référentiel — le décor minimal.

    Les cultures sont GLOBALES (`potager_id` nul), comme en production : une
    fiche partagée ne peut se rattacher qu'à une culture partagée.
    """
    test_db.add(User(id=1, email="a@potager.test"))
    test_db.flush()
    test_db.add(Potager(id=1, nom="Jardin A", proprietaire_id=1))
    for culture in PERIMETRE:
        test_db.add(CultureConfig(
            nom=LIBELLE_REFERENTIEL.get(culture, culture),
            type_organe_recolte="reproducteur",
            potager_id=None,
        ))
    test_db.commit()
    return test_db


def _ingerer(db, racine: Path = CORPUS) -> ing.Rapport:
    rapport = ing.Rapport()
    for chemin in sorted(racine.rglob("*.md")):
        if chemin.name.upper() == "README.MD":
            continue
        ing.ingerer_fichier(db, chemin, RACINE, rapport)
    return rapport


@pytest.fixture
def corpus(base):
    """Le corpus RÉEL du dépôt, ingéré comme l'outil le ferait."""
    rapport = _ingerer(base)
    assert not rapport.erreurs, rapport.erreurs
    return base, rapport


@pytest.fixture
def fiches():
    """Les fiches lues depuis le dépôt — la source, pas l'index."""
    return [controle.lire_fiche(chemin) for chemin in sorted(CORPUS.glob("*.md"))
            if chemin.name.upper() != "README.MD"]


@pytest.fixture
def sans_appel_modele():
    """[CA14] Fait échouer le test si un modèle est appelé sur ce chemin."""
    with patch("llm.passerelle.appeler_chat", side_effect=AssertionError(
        "Un appel au modèle a eu lieu là où l'US en exige zéro"
    )):
        yield


def _questions_attendues() -> list[tuple[str, str]]:
    with QUESTIONS.open(encoding="utf-8", newline="") as fichier:
        return [
            (ligne["question"].strip(), PREFIXE + ligne["fragment_attendu"].strip())
            for ligne in csv.DictReader(fichier)
            if ligne["question"].strip() and ligne["fragment_attendu"].strip()
        ]


def _rang(db, question: str, attendu: str) -> "int | None":
    contexte = connaissance.rechercher(db, CTX, question, limite=10)
    references = list(contexte.references)
    return references.index(attendu) + 1 if attendu in references else None


def _ecrire_fiche(dossier: Path, nom: str, entete: str, corps: str) -> Path:
    chemin = dossier / nom
    chemin.write_text(f"---\n{entete}\n---\n\n{corps}\n", encoding="utf-8")
    return chemin


_ENTETE_VALIDE = (
    'titre: "Fiche d\'essai"\n'
    'famille: "agronomie"\n'
    'source: "Assistant Potager — rédaction interne"\n'
    'niveau_confiance: "a-valider"\n'
    'culture: "tomate"'
)
_CORPS_VALIDE = (
    "## Une question de jardinier posée en toutes lettres\n\n"
    "**Intention :** diagnostic\n"
    "**Organes concernés :** feuille\n"
    "**On parle aussi de :** un alias ; un deuxième alias ; un troisième alias\n\n"
    "Un texte assez long pour porter une idée répondable telle quelle, sans "
    "dépendre de ce qui le précède ni de ce qui le suit dans la fiche."
)


# ═════════════════════════════════════════════════════════════════════════════
# CA1 / CA5 — le périmètre et ce que chaque culture doit posséder
# ═════════════════════════════════════════════════════════════════════════════
def test_us140_ca1_les_dix_cultures_du_perimetre_ont_leurs_fiches():
    """CA1 — les dix cultures nommées par l'US, ni plus ni moins."""
    presentes = controle.cultures_du_perimetre(CORPUS)
    assert set(presentes) == set(PERIMETRE), (
        f"périmètre du dépôt {sorted(presentes)} ≠ périmètre de l'US {sorted(PERIMETRE)}"
    )


def test_us140_ca5_chaque_culture_porte_ses_problemes_et_ses_gestes():
    """CA5 — « maladies et ravageurs courants avec leurs symptômes, ET gestes
    courants d'entretien et de récolte ». Une culture qui n'aurait que ses
    problèmes serait un assistant qui sait dire ce qui va mal, pas quoi faire."""
    rapport, _ = controle.controler(CORPUS, PERIMETRE)
    manquants = [ligne for ligne in rapport.refus if "CA1/CA5" in ligne]
    assert not manquants, manquants


def test_us140_ca5_chaque_culture_est_reellement_interrogeable(corpus, sans_appel_modele):
    """CA5 — une fiche présente mais introuvable ne couvre rien. Chaque culture
    est donc vérifiée par une question de symptôme, pas par un nom de fichier."""
    db, _ = corpus
    interrogations = {
        "tomate": "mes tomates ont le cul noir",
        "courgette": "les feuilles de mes courgettes ont de la poudre blanche",
        "haricot": "mes haricots ne lèvent pas les graines sont molles",
        "chou": "mes choux sont mangés il ne reste que les nervures",
        "carotte": "mes carottes sont fourchues",
        "concombre": "mes concombres sont amers",
        "cornichon": "mes cornichons deviennent amers et jaunissent sur pied",
        "poivron": "mes poivrons perdent toutes leurs fleurs",
        "ail": "mes feuilles d'ail ont des traits orange",
        "blette": "mes feuilles de blettes sont cloquées avec des galeries",
    }
    for culture, question in interrogations.items():
        contexte = connaissance.rechercher(db, CTX, question, limite=3)
        origines = {ref.split("#", 1)[0].rsplit("/", 1)[-1].split("-", 1)[0]
                    for ref in contexte.references}
        assert culture in origines, f"« {question} » ne retrouve aucune fiche {culture} ({origines})"


# ═════════════════════════════════════════════════════════════════════════════
# CA2 / CA3 — la licence est un préalable bloquant, pas une métadonnée
# ═════════════════════════════════════════════════════════════════════════════
def test_us140_ca3_chaque_fiche_porte_sa_source_et_sa_licence(fiches):
    """CA3 — « chaque document porte sa source et sa licence »."""
    for fiche in fiches:
        assert fiche.entete.get("source"), f"{fiche.chemin.name} sans source affichable"
        assert fiche.entete.get("licence"), f"{fiche.chemin.name} sans licence"


def test_us140_ca2_aucune_licence_hors_du_socle_dans_le_corpus(fiches):
    """CA2 — le socle est fermé : CC0, Licence Ouverte, CC BY, EPPO, propriétaire.
    Toute autre licence, CC-BY-SA en tête, est hors corpus."""
    for fiche in fiches:
        assert fiche.entete["licence"] in referentiel_sources.LICENCES_SOCLE, fiche.chemin.name


def test_us140_ca3_un_contenu_sans_licence_etablie_est_refuse(base, tmp_path):
    """Gherkin « Contenu sans licence établie refusé » — l'ingestion refuse, et
    AUCUN fragment n'est créé. Le contrôle porte sur la base, pas sur l'exception :
    une exception levée après une écriture partielle laisserait du contenu."""
    chemin = _ecrire_fiche(tmp_path, "sans-licence.md", _ENTETE_VALIDE, _CORPS_VALIDE)
    with pytest.raises(ing.DocumentInvalide, match="licence non établie"):
        ing.ingerer_fichier(base, chemin, tmp_path, ing.Rapport())
    assert base.query(KnowledgeChunk).count() == 0
    assert base.query(KnowledgeDocument).count() == 0


def test_us140_ca3_une_source_cc_by_sa_est_refusee_malgre_une_licence_connue(base, tmp_path):
    """Gherkin « Source CC-BY-SA refusée malgré une licence connue » — la licence
    est parfaitement établie, elle est simplement hors du socle. C'est le cas
    qu'un contrôle « la clé est-elle renseignée ? » laisserait passer, et c'est
    précisément celui qui contaminerait le corpus."""
    entete = _ENTETE_VALIDE + '\nlicence: "CC-BY-SA-4.0"'
    chemin = _ecrire_fiche(tmp_path, "cc-by-sa.md", entete, _CORPS_VALIDE)
    with pytest.raises(ing.DocumentInvalide, match="hors socle"):
        ing.ingerer_fichier(base, chemin, tmp_path, ing.Rapport())
    assert base.query(KnowledgeChunk).count() == 0
    assert base.query(KnowledgeDocument).count() == 0


def test_us140_ca3_le_socle_de_licences_n_est_pas_redefini_ici():
    """CA3 — « aucun second mécanisme ». Le contrôle d'ingestion s'appuie sur le
    registre d'US-166, celui-là même qu'oppose déjà l'import du référentiel
    structuré. Deux listes finiraient par diverger, et la permissive gagnerait."""
    source = Path(ing.__file__).read_text(encoding="utf-8")
    assert "referentiel_sources.LICENCES_SOCLE" in source
    assert "CC-BY-SA" not in source, "le socle ne s'énumère pas dans l'outil d'ingestion"


def test_us140_ca3_une_licence_du_socle_passe(base, tmp_path):
    """CA3 — le contrôle refuse ce qui doit l'être et laisse passer le reste :
    une règle qui refuse tout n'est pas un contrôle, c'est une panne."""
    entete = _ENTETE_VALIDE + '\nlicence: "proprietaire"'
    chemin = _ecrire_fiche(tmp_path, "propre.md", entete, _CORPS_VALIDE)
    ing.ingerer_fichier(base, chemin, tmp_path, ing.Rapport())
    assert base.query(KnowledgeDocument).count() == 1


def test_us140_ca3_la_licence_reste_facultative_pour_les_autres_familles(base, tmp_path):
    """CA3 — l'exigence porte sur `agronomie`, qui reprend un savoir qui n'est
    pas le nôtre. `doc_app` (US-099) décrit notre propre application : lui
    imposer une licence obligerait à recréditer treize fiches sans tiers à
    créditer, et rendrait la règle décorative."""
    entete = _ENTETE_VALIDE.replace('famille: "agronomie"', 'famille: "doc_app"')
    chemin = _ecrire_fiche(tmp_path, "doc-app.md", entete, _CORPS_VALIDE)
    ing.ingerer_fichier(base, chemin, tmp_path, ing.Rapport())
    assert base.query(KnowledgeDocument).count() == 1


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — l'attribution est affichée avec la réponse
# ═════════════════════════════════════════════════════════════════════════════
def test_us140_ca4_la_source_affichee_est_celle_du_registre(fiches):
    """CA4 — « lorsqu'une licence impose l'attribution, celle-ci est conservée ».
    La chaîne affichée n'est donc pas rédigée fiche par fiche : c'est celle du
    registre des sources, seul endroit où une licence à attribution obligatoire
    (CC BY 4.0, EPPO) déclare la mention exacte qu'elle exige."""
    attendues = {entree["attribution"] for entree in referentiel_sources.SOURCES_SOCLE}
    for fiche in fiches:
        assert fiche.entete["source"] in attendues, (
            f"{fiche.chemin.name} affiche « {fiche.entete['source'] } », "
            f"absent du registre des sources"
        )


def test_us140_ca4_l_attribution_accompagne_la_reponse_servie(corpus, sans_appel_modele):
    """Gherkin « Attribution affichée » — la mention part AVEC le texte, dans le
    même message. Une attribution consignée au dépôt et absente de la réponse ne
    remplirait aucune obligation de licence."""
    db, _ = corpus
    contexte = connaissance.rechercher(db, CTX, "mes tomates ont le cul noir")
    assert contexte.passages, "la question la plus prévisible du corpus doit trouver quelque chose"
    assert contexte.sources == ("Assistant Potager — rédaction interne",)
    assert connaissance.restituer(contexte).endswith(
        "_Source : Assistant Potager — rédaction interne_"
    )


def test_us140_ca4_l_attribution_suit_aussi_une_reponse_reecrite(corpus, monkeypatch):
    """CA4 — une réponse RÉDIGÉE à partir du corpus en est une œuvre dérivée : la
    mention doit l'accompagner elle aussi. C'est le chemin normal des fiches
    d'agronomie, qui sont `a-valider` et descendent donc toujours à l'étage 3."""
    db, _ = corpus
    _armer_cascade(db, monkeypatch)
    with patch("llm.passerelle.appeler_chat", return_value=_reponse_modele()):
        reponse = routeur.repondre_avec_cascade(CTX, "pourquoi mes tomates ont le cul noir ?")
    assert "_D'après : Assistant Potager — rédaction interne_" in reponse.texte


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — les mots du jardinier, dans la section
# ═════════════════════════════════════════════════════════════════════════════
def test_us140_ca6_chaque_section_porte_les_mots_du_jardinier(fiches):
    """CA6 — « chaque fiche liste explicitement les mots du jardinier à côté du
    terme technique ». C'est LA mesure qui permet à la recherche plein texte de
    fonctionner sans moteur vectoriel : un lemme absent de l'index est un
    rapprochement impossible, quelle que soit la qualité du texte."""
    fautes = []
    for fiche in fiches:
        for section in fiche.sections:
            alias = controle.decouper_alias(
                section.metadonnees.get("on parle aussi de", "")
            )
            if len(alias) < controle.ALIAS_MINIMUM:
                fautes.append(f"{fiche.chemin.name} · « {section.intitule} » : {len(alias)} alias")
    assert not fautes, fautes


def test_us140_ca6_les_alias_ne_sont_jamais_affiches(corpus):
    """CA6 — un alias doit peser à l'index et ne jamais s'afficher. Sans cette
    séparation, le message envoyé au jardinier s'ouvrirait sur la ligne
    « On parle aussi de : cul noir ; nécrose apicale ; … » avant la réponse."""
    db, _ = corpus
    for reference, contenu in db.query(KnowledgeChunk.reference, KnowledgeChunk.contenu).all():
        assert "On parle aussi de" not in contenu, reference
        assert "Organes concernés" not in contenu, reference
        assert "**Intention" not in contenu, reference


def test_us140_ca6_le_mot_populaire_retrouve_le_terme_technique(corpus, sans_appel_modele):
    """CA6 / Gherkin « Diagnostic à partir des mots du jardinier » et « Symptôme
    décrit en langage courant » — les deux scénarios de l'US, vérifiés sur le
    vocabulaire courant seul, sans jamais employer le nom de la maladie."""
    db, _ = corpus
    attendus = {
        "pourquoi mes tomates ont le cul noir": "tomate-problemes.md",
        "mes feuilles de courgette deviennent jaunes et poudreuses": "courgette-problemes.md",
        "il y a du blanc comme de la farine sur mes concombres": "concombre-problemes.md",
        "mes carottes font deux jambes": "carotte-problemes.md",
    }
    for question, fichier in attendus.items():
        contexte = connaissance.rechercher(db, CTX, question, limite=RANG_CIBLE)
        origines = [ref.split("#", 1)[0].rsplit("/", 1)[-1] for ref in contexte.references]
        assert fichier in origines, f"« {question} » → {origines}"


# ═════════════════════════════════════════════════════════════════════════════
# CA7 / CA7bis / CA10 / CA13 — ce qu'une fiche ne contient jamais
# ═════════════════════════════════════════════════════════════════════════════
def test_us140_le_corpus_reel_passe_la_relecture():
    """CA7, CA7bis, CA9, CA10, CA13 — le contrôle complet sur le corpus livré.
    Un seul test pour tous ces critères, parce qu'un seul outil les porte : les
    tests qui suivent vérifient que cet outil refuse bien ce qu'il doit."""
    rapport, _ = controle.controler(CORPUS, PERIMETRE)
    assert rapport.conforme, rapport.refus
    assert rapport.fiches == len(PERIMETRE) * len(controle.THEMES_REQUIS_PAR_CULTURE)


@pytest.mark.parametrize("phrase,critere", [
    ("Semer les graines à deux centimètres de profondeur dans un sol ressuyé.", "CA7"),
    ("Compter trois semaines entre le semis et la mise en godet du plant.", "CA7"),
    ("Récolter en juillet, quand le feuillage a séché sur pied au jardin.", "CA7"),
    ("Espacer les pieds de quarante cm sur le rang pour aérer le feuillage.", "CA7/CA13a"),
])
def test_us140_ca7_une_fiche_qui_chiffre_est_refusee(tmp_path, phrase, critere):
    """Gherkin « Aucune date dans les fiches » et « Fiche générée portant un
    chiffre non sourcé » — dates, fenêtres et durées appartiennent au référentiel
    calendrier (US-068), les valeurs chiffrées au référentiel structuré (US-161).
    Dupliquées ici, elles créeraient une seconde vérité, fausse pour la moitié
    des jardiniers puisqu'elle ignore la zone climatique."""
    corps = _CORPS_VALIDE + " " + phrase
    _ecrire_fiche(tmp_path, "tomate-problemes.md",
                  _ENTETE_VALIDE + '\nlicence: "proprietaire"', corps)
    rapport, _ = controle.controler(tmp_path)
    assert any(critere in ligne for ligne in rapport.refus), rapport.refus


@pytest.mark.parametrize("phrase", [
    "Une association de cultures avec le basilic éloigne certains ravageurs.",
    "Respecter une rotation avant de replacer une solanacée sur la planche.",
    "Le délai de retour tient compte de la famille botanique de la culture.",
])
def test_us140_ca7bis_une_fiche_qui_enonce_une_relation_est_refusee(tmp_path, phrase):
    """Gherkin « Aucune association ni rotation dans les fiches » — ce sont des
    arêtes entre cultures, portées par `association_culture` et le calcul de
    rotation (US-163). Écrites dans une fiche, elles deviennent une vérité
    invisible du calcul, impossible à croiser avec l'historique d'une parcelle
    et incapable de déclencher l'avertissement d'US-167."""
    corps = _CORPS_VALIDE + " " + phrase
    _ecrire_fiche(tmp_path, "tomate-problemes.md",
                  _ENTETE_VALIDE + '\nlicence: "proprietaire"', corps)
    rapport, _ = controle.controler(tmp_path)
    assert any("CA7bis" in ligne for ligne in rapport.refus), rapport.refus


def test_us140_ca7bis_expliquer_un_mecanisme_reste_autorise(tmp_path):
    """CA7bis — « une fiche peut en revanche expliquer un mécanisme ». Un contrôle
    qui refuserait aussi l'explication viderait les fiches de ce qui en fait
    l'intérêt, et serait contourné dès la deuxième rédaction."""
    corps = _CORPS_VALIDE + (
        " Les solanacées prélèvent fortement les mêmes éléments du sol et y "
        "laissent des parasites qui leur sont propres, ce qui appauvrit la "
        "planche pour elles seules."
    )
    _ecrire_fiche(tmp_path, "tomate-problemes.md",
                  _ENTETE_VALIDE + '\nlicence: "proprietaire"', corps)
    rapport, _ = controle.controler(tmp_path)
    assert not [ligne for ligne in rapport.refus if "CA7bis" in ligne], rapport.refus


@pytest.mark.parametrize("phrase", [
    "Pulvériser une bouillie bordelaise sur le feuillage dès les premiers signes.",
    "Diluer le produit avant de traiter les pieds atteints du rang.",
    "Un fongicide de contact protège le feuillage encore sain de la parcelle.",
])
def test_us140_ca10_une_fiche_qui_prescrit_un_produit_est_refusee(tmp_path, phrase):
    """CA10 — « aucune fiche ne donne de dosage ni de recommandation d'emploi
    d'un produit phytosanitaire ; l'assistant n'est pas un conseiller en
    traitement ». C'est une limite de responsabilité, pas une préférence."""
    corps = _CORPS_VALIDE + " " + phrase
    _ecrire_fiche(tmp_path, "tomate-problemes.md",
                  _ENTETE_VALIDE + '\nlicence: "proprietaire"', corps)
    rapport, _ = controle.controler(tmp_path)
    assert any("CA10" in ligne for ligne in rapport.refus), rapport.refus


def test_us140_ca10_le_modele_recoit_la_meme_interdiction():
    """CA10 — le corpus est propre, mais l'étage 3 RÉDIGE. Une consigne absente
    du prompt laisserait le modèle prescrire ce que les fiches se refusent à
    écrire, et le jardinier ne verrait pas la différence."""
    assert "dose" in routeur._PROMPT_FIXE_RAISONNEMENT
    assert "conseiller en traitement" in routeur._PROMPT_FIXE_RAISONNEMENT


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — le niveau de confiance, et la réserve qu'il impose
# ═════════════════════════════════════════════════════════════════════════════
def test_us140_ca8_le_niveau_de_confiance_est_renseigne_par_fiche(corpus):
    """CA8 / CA13 (b) — `a-valider` par défaut, sans exception, tant qu'une
    personne qui jardine n'a pas relu la fiche phrase par phrase. En base, cet
    état éditorial se replie sur `indicatif`, qui pilote un comportement : le
    passage ne peut plus être servi mot pour mot."""
    db, _ = corpus
    documents = db.query(KnowledgeDocument).all()
    assert documents, "le corpus ne doit pas être vide"
    for document in documents:
        assert document.famille == connaissance.FAMILLE_AGRONOMIE, document.reference
        assert document.niveau_confiance == connaissance.NIVEAU_INDICATIF, document.reference
        assert document.potager_id is None, document.reference


def test_us140_ca8_un_contenu_indicatif_n_est_jamais_servi_mot_pour_mot(corpus):
    """CA8 — servir tel quel un contenu que le corpus déclare lui-même incertain
    ferait passer pour établi ce qui ne l'est pas. La recherche le refuse par
    construction, quel que soit son score."""
    db, _ = corpus
    contexte = connaissance.rechercher(db, CTX, "mes tomates ont le cul noir")
    assert contexte.passages
    assert not contexte.suffisant
    assert contexte.issue == connaissance.ISSUE_TRANSMIS


def test_us140_ca8_une_reponse_indicative_porte_une_reserve_explicite(corpus, monkeypatch):
    """Gherkin « Fiche générée non relue » — la réponse est servie AVEC la réserve
    due à un contenu `indicatif`. Sans elle, le niveau de confiance restait un
    engagement interne dont rien ne parvenait au jardinier."""
    db, _ = corpus
    _armer_cascade(db, monkeypatch)
    with patch("llm.passerelle.appeler_chat", return_value=_reponse_modele()):
        reponse = routeur.repondre_avec_cascade(CTX, "pourquoi mes tomates ont le cul noir ?")
    assert connaissance.RESERVE_INDICATIF in reponse.texte
    ligne = db.query(RoutageLog).order_by(RoutageLog.id.desc()).first()
    assert ligne.issue_savoir == connaissance.ISSUE_TRANSMIS


def test_us140_ca8_une_fiche_relue_ne_porte_aucune_reserve():
    """CA8 — la réserve signale une EXCEPTION. Affichée partout, elle deviendrait
    un ornement que plus personne ne lit, et le jour où elle compte vraiment,
    elle ne se verrait plus."""
    passage = connaissance.Passage(
        reference="x#00", titre_document="T", intitule="I", contenu="C",
        source="S", niveau_confiance=connaissance.NIVEAU_VERIFIE, score=0.9,
    )
    verifie = connaissance.ContexteConnaissance(question="q", passages=(passage,))
    assert connaissance.reserve_a_afficher(verifie) == ""

    indicatif = connaissance.ContexteConnaissance(
        question="q",
        passages=(connaissance.Passage(
            reference="x#00", titre_document="T", intitule="I", contenu="C",
            source="S", niveau_confiance=connaissance.NIVEAU_INDICATIF, score=0.9,
        ),),
    )
    assert connaissance.reserve_a_afficher(indicatif) == connaissance.RESERVE_INDICATIF


def test_us140_ca8_la_reserve_se_lit_sans_legende():
    """CA8 — « une réserve EXPLICITE ». Le message part aussi en synthèse vocale :
    un pictogramme ou une abréviation n'y survivrait pas."""
    assert len(connaissance.RESERVE_INDICATIF.split()) >= 12
    assert "vérifi" in connaissance.RESERVE_INDICATIF or "relue" in connaissance.RESERVE_INDICATIF


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — la prudence du conseil
# ═════════════════════════════════════════════════════════════════════════════
def test_us140_ca9_chaque_section_de_diagnostic_propose_au_lieu_d_affirmer(fiches):
    """Gherkin « Prudence du conseil » — « l'excès d'eau est plus probable qu'une
    carence » et non « tes courgettes ont trop d'eau ». La prudence est lexicale
    et se contrôle : une section de diagnostic sans aucune tournure d'hypothèse
    affirme, quoi qu'ait voulu dire son auteur."""
    fautes = []
    for fiche in (f for f in fiches if f.theme == "problemes"):
        for section in fiche.sections:
            aplati = controle._aplatir(f"{section.intitule} {section.contenu}")
            if not any(m in aplati for m in controle.MARQUEURS_PRUDENCE):
                fautes.append(f"{fiche.chemin.name} · « {section.intitule} »")
    assert not fautes, fautes


def test_us140_ca9_une_section_de_diagnostic_affirmative_est_refusee(tmp_path):
    """CA9 — le contrôle refuse bien ce qu'il annonce refuser."""
    corps = (
        "## Mes tomates ont le cul noir\n\n"
        "**Intention :** diagnostic\n"
        "**Organes concernés :** fruit\n"
        "**On parle aussi de :** cul noir ; nécrose apicale ; tache sous le fruit\n\n"
        "Le cul noir de la tomate vient d'un manque de calcium dans le sol. "
        "Un apport de calcium règle définitivement le problème sur tous les pieds."
    )
    _ecrire_fiche(tmp_path, "tomate-problemes.md",
                  _ENTETE_VALIDE + '\nlicence: "proprietaire"', corps)
    rapport, _ = controle.controler(tmp_path)
    assert any("CA9" in ligne for ligne in rapport.refus), rapport.refus


def test_us140_ca9_le_modele_recoit_la_consigne_d_ordonner_ses_hypotheses():
    """CA9 — les fiches d'agronomie sont `indicatif`, donc TOUTE réponse
    d'agronomie est rédigée par l'étage 3. La prudence du corpus ne vaut donc
    rien si le prompt, lui, autorise l'affirmation."""
    prompt = routeur._PROMPT_FIXE_RAISONNEMENT
    assert "ordre de probabilité" in prompt
    assert "jamais une cause comme certaine" in prompt


# ═════════════════════════════════════════════════════════════════════════════
# CA11 / CA12 — la mesure
# ═════════════════════════════════════════════════════════════════════════════
def test_us140_ca11_le_corpus_de_questions_est_suffisant():
    """CA11 — « un corpus d'au moins 30 questions de diagnostic formulées avec
    les mots d'un jardinier »."""
    questions = _questions_attendues()
    assert len(questions) >= 30, f"{len(questions)} questions, 30 exigées"
    assert len({q for q, _ in questions}) == len(questions), "questions dupliquées"


def test_us140_ca11_le_corpus_reprend_les_questions_ecrites_avant_les_fiches():
    """CA11 — « le corpus doit être constitué AVANT la rédaction des fiches :
    rédiger d'abord puis construire le test à partir des fiches produirait une
    mesure auto-réalisatrice ». Les dix-neuf entrées du périmètre v1 de
    `docs/CORPUS_QUESTIONS_DIAGNOSTIC_CA11.md` (25/08/2026) doivent donc se
    retrouver mot pour mot dans le CSV de mesure."""
    posees = {q for q, _ in _questions_attendues()}
    anterieures = [
        "mes tomates ont le cul noir",
        "les feuilles de mes courgettes ont de la poudre blanche",
        "mes choux sont mangés, il ne reste que les nervures",
        "mes concombres sont amers, immangeables",
        "mes carottes sont fourchues, elles font deux ou trois jambes",
        "les feuilles de mes tomates s'enroulent en cuillère vers le haut",
        "mes feuilles de blettes sont cloquées avec des galeries claires dedans",
        "mes poivrons sous la serre perdent toutes leurs fleurs sans faire de fruit",
        "mes haricots ne lèvent pas, j'ai gratté les graines sont molles et pourries",
        "mes carottes ont mal levé, il y a des trous dans le rang",
    ]
    absentes = [q for q in anterieures if q not in posees]
    assert not absentes, f"questions du corpus du 25/08/2026 non reprises : {absentes}"


def test_us140_ca11_tous_les_fragments_attendus_existent(corpus):
    """CA11 — une attente qui ne désigne aucun fragment mesurerait le vide. Ce
    test tombe aussi quand une section est renommée sans que le corpus suive."""
    db, _ = corpus
    indexes = {reference for (reference,) in db.query(KnowledgeChunk.reference).all()}
    inconnus = sorted({attendu for _, attendu in _questions_attendues()} - indexes)
    assert not inconnus, f"fragments attendus introuvables : {inconnus}"


def test_us140_ca11_la_bonne_fiche_sort_dans_les_trois_premiers(corpus):
    """CA11 — la cible de l'US : au moins 80 % des questions placent la bonne
    fiche dans les trois premiers résultats. Le seuil est un seuil, pas une
    perfection : quelques questions restent hors cible et ce sont elles, listées
    ici, qui disent quoi enrichir (CA12)."""
    db, _ = corpus
    resultats = [(q, _rang(db, q, attendu)) for q, attendu in _questions_attendues()]
    dans_cible = [q for q, rang in resultats if rang is not None and rang <= RANG_CIBLE]
    taux = len(dans_cible) / len(resultats)
    hors_cible = [f"« {q} » → {'absent' if r is None else f'rang {r}'}"
                  for q, r in resultats if r is None or r > RANG_CIBLE]
    assert taux >= TAUX_CIBLE, (
        f"{len(dans_cible)}/{len(resultats)} ({taux:.0%}) dans le top {RANG_CIBLE}, "
        f"cible {TAUX_CIBLE:.0%}\n" + "\n".join(hors_cible)
    )


def test_us140_ca12_la_mesure_est_consignee_et_datee():
    """CA12 — « le résultat de cette mesure est ce qui décidera, plus tard, de
    l'activation ou non de la recherche sémantique ». Une mesure qui n'est
    consignée nulle part ne peut rien décider : elle est reperdue au premier
    changement de corpus."""
    texte = LISEZ_MOI.read_text(encoding="utf-8")
    assert "CA11" in texte and "CA12" in texte
    assert re.search(r"\d+\s*/\s*\d+", texte), "aucun résultat chiffré consigné"
    assert "recherche sémantique" in texte or "vectoriel" in texte


def test_us140_ca12_une_question_hors_perimetre_ne_force_aucune_reponse(corpus, sans_appel_modele):
    """CA12 — les vingt-cinq entrées HORS périmètre v1 du corpus du 25/08/2026
    sont un test d'honnêteté, pas de rappel : sur une culture qu'aucune fiche ne
    couvre, l'étage doit rendre une issue vide plutôt qu'une fiche voisine
    forcée. Une réponse sur la courgette à une question sur le melon serait
    pire qu'un silence."""
    db, _ = corpus
    contexte = connaissance.rechercher(db, CTX, "mes melons n'ont aucun goût")
    origines = {ref.split("#", 1)[0].rsplit("/", 1)[-1].split("-", 1)[0]
                for ref in contexte.references}
    assert not contexte.suffisant, "aucune fiche melon n'existe : rien ne doit être servi tel quel"
    assert "melon" not in origines


# ═════════════════════════════════════════════════════════════════════════════
# CA13 — le plan imposé, et les quatre garde-fous de la rédaction assistée
# ═════════════════════════════════════════════════════════════════════════════
def test_us140_ca13c_le_plan_est_impose_et_identique_pour_toutes(fiches):
    """CA13 (c) — « plan de fiche imposé et identique pour toutes, faute de quoi
    le découpage en fragments d'US-098 devient irrégulier ». Le thème est porté
    par le nom de fichier : le plan se lit sur le dossier, sans ouvrir une fiche."""
    for fiche in fiches:
        assert fiche.theme in controle.THEMES_IMPOSES, fiche.chemin.name
        for section in fiche.sections:
            assert section.intitule, f"{fiche.chemin.name} : texte hors section"
            for cle in controle.METADONNEES_DE_SECTION:
                assert controle._aplatir(cle) in section.metadonnees, (
                    f"{fiche.chemin.name} · « {section.intitule} » sans `{cle}`"
                )


def test_us140_ca13c_une_fiche_hors_plan_est_refusee(tmp_path):
    """CA13 (c) — un thème inventé ou une section sans ses métadonnées casse
    l'homogénéité du découpage, et le contrôle le dit."""
    _ecrire_fiche(tmp_path, "tomate-calendrier.md",
                  _ENTETE_VALIDE + '\nlicence: "proprietaire"', _CORPS_VALIDE)
    rapport, _ = controle.controler(tmp_path)
    assert any("CA13c" in ligne for ligne in rapport.refus), rapport.refus


def test_us140_ca13d_la_mention_de_source_est_visible_cote_utilisateur(corpus):
    """CA13 (d) — « mention de source visible côté utilisateur, cohérente avec le
    CA4 ». Le contrôle porte sur ce que la restitution PRODUIT, pas sur ce que
    l'en-tête déclare."""
    db, _ = corpus
    contexte = connaissance.rechercher(db, CTX, "mes carottes sont fourchues")
    assert contexte.passages
    assert "_Source : " in connaissance.restituer(contexte)


def test_us140_ca14_la_redaction_ne_touche_jamais_le_chemin_de_reponse(base, sans_appel_modele):
    """CA14 — « la génération se fait hors du chemin de réponse au jardinier et
    hors du quota qui le sert ». L'ingestion et la relecture sont des outils hors
    ligne : aucun appel modèle, ni pendant l'un, ni pendant l'autre."""
    rapport = _ingerer(base)
    assert not rapport.erreurs, rapport.erreurs
    controle.controler(CORPUS, PERIMETRE)


def test_us140_ca14_les_outils_de_corpus_n_appellent_aucun_modele():
    """CA14 — un appel modèle ajouté un jour dans l'un de ces outils replacerait
    la rédaction sur le quota qui sert le jardinier, sans que rien ne le signale.
    Le contrôle porte donc sur le code, pas seulement sur une exécution."""
    for module in (ing, controle):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "passerelle" not in source, f"{module.__name__} touche à la passerelle LLM"
        assert "groq" not in source.lower(), f"{module.__name__} touche au fournisseur"


# ═════════════════════════════════════════════════════════════════════════════
# Ingestion — même mécanisme que le corpus de fonctionnement, aucun second
# ═════════════════════════════════════════════════════════════════════════════
def test_us140_le_corpus_s_ingere_sans_erreur_ni_defaut_de_decoupage(corpus):
    """Notes techniques de l'US : « les fiches suivent le même format d'en-tête et
    le même outil d'ingestion que le corpus de fonctionnement — aucun second
    mécanisme ». `--strict` compris : aucun fragment ne dépend du précédent."""
    _, rapport = corpus
    assert not rapport.erreurs, rapport.erreurs
    assert not rapport.avertissements, rapport.avertissements
    assert rapport.crees == len(list(CORPUS.glob("*.md"))) - 1  # le README n'est pas du contenu
    assert rapport.fragments > 0


def test_us140_reingerer_un_corpus_inchange_n_ecrit_rien(corpus):
    """Idempotence — c'est elle qui autorise à rejouer l'ingestion à chaque
    déploiement, comme une migration."""
    db, premier = corpus
    second = _ingerer(db)
    assert second.inchanges == premier.crees
    assert second.crees == 0 and second.mis_a_jour == 0 and second.fragments == 0


@pytest.mark.parametrize("chemin", [
    ".github/workflows/deploy.yml",
    ".github/workflows/deploy-dev.yml",
    "deploy.sh",
    "update_dev.ps1",
])
def test_us140_la_relecture_est_executee_au_deploiement(chemin):
    """CA7, CA10, CA13 — une règle de relecture qui ne s'exécute pas au
    déploiement n'est pas une règle, c'est un souhait. Les QUATRE chemins de
    déploiement sont vérifiés, pas seulement le script historique : le
    déploiement réel passe par les workflows GitHub."""
    contenu = (RACINE / chemin).read_text(encoding="utf-8")
    assert "tools/controler_corpus_agronomie.py" in contenu, (
        f"{chemin} n'exécute pas la relecture du corpus agronomique"
    )


@pytest.mark.parametrize("chemin", [
    ".github/workflows/deploy.yml",
    ".github/workflows/deploy-dev.yml",
])
def test_us140_la_relecture_precede_l_ingestion(chemin):
    """L'ordre n'est pas indifférent : ingérer d'abord puis contrôler ferait
    entrer à l'index une fiche que la relecture refuse, et l'index resterait
    faux jusqu'au déploiement suivant."""
    contenu = (RACINE / chemin).read_text(encoding="utf-8")
    assert (contenu.index("controler_corpus_agronomie.py")
            < contenu.index("ingerer_connaissance.py"))


# ═════════════════════════════════════════════════════════════════════════════
# Tenue dans le temps — la table de relecture, comme en US-099 / CA9
# ═════════════════════════════════════════════════════════════════════════════
def test_us140_chaque_fiche_figure_dans_la_table_de_relecture(fiches):
    """Règle projet (CLAUDE.md, posée par US-099 / CA9) : une évolution qui rend
    une fiche fausse impose sa mise à jour dans la même livraison. Ce point n'est
    tenable que si l'on sait quelle fiche relire — c'est la table du README, et
    une fiche qui n'y figure pas ne sera jamais relue."""
    table = LISEZ_MOI.read_text(encoding="utf-8")
    manquantes = [f.chemin.name for f in fiches if f"`{f.chemin.name}`" not in table]
    assert not manquantes, f"fiches absentes de la table de relecture : {manquantes}"


def test_us140_la_table_de_relecture_ne_cite_aucune_fiche_disparue(fiches):
    """L'écart inverse : une ligne de table qui survit à sa fiche envoie relire
    un fichier qui n'existe plus."""
    table = LISEZ_MOI.read_text(encoding="utf-8")
    presentes = {f.chemin.name for f in fiches}
    citees = set(re.findall(r"`([\w-]+\.md)`", table)) - {"README.md"}
    assert citees <= presentes, f"fiches citées mais absentes : {citees - presentes}"


# ═════════════════════════════════════════════════════════════════════════════
# La commande elle-même — c'est elle que le déploiement exécute
# ═════════════════════════════════════════════════════════════════════════════
def test_us140_la_commande_de_relecture_rend_zero_sur_le_corpus_livre(capsys):
    """Le déploiement n'appelle pas `controler()`, il appelle `main()`. Un
    rapport qui planterait à l'affichage — la console Windows est en cp1252 et
    le rapport porte des emojis — ferait échouer un déploiement sur un corpus
    pourtant valide."""
    assert controle.main([]) == 0
    sortie = capsys.readouterr().out
    assert "20" in sortie and "10" in sortie


def test_us140_la_commande_rend_un_code_d_erreur_sur_une_fiche_refusee(tmp_path, capsys):
    """Un contrôle qui signale sans échouer laisse passer ce qu'il vient de
    refuser : c'est le code de retour, et lui seul, qui arrête le déploiement."""
    _ecrire_fiche(tmp_path, "tomate-problemes.md",
                  _ENTETE_VALIDE + '\nlicence: "CC-BY-SA-4.0"', _CORPS_VALIDE)
    assert controle.main(["--racine", str(tmp_path), "--detail"]) == 1
    assert "refus à la relecture" in capsys.readouterr().out


def test_us140_la_commande_signale_une_racine_introuvable(tmp_path, capsys):
    """Un dossier absent ne doit pas se lire comme « corpus conforme » : le code
    de retour distingue le refus (1) de l'erreur d'exécution (2)."""
    assert controle.main(["--racine", str(tmp_path / "nulle-part")]) == 2
    assert "introuvable" in capsys.readouterr().out


# ═════════════════════════════════════════════════════════════════════════════
# Outillage partagé
# ═════════════════════════════════════════════════════════════════════════════
def _reponse_modele(texte: str = "Une réponse rédigée à partir du corpus."):
    """La réponse normalisée que rend la passerelle — mesure comprise.

    Un objet factice sans `tokens_total` passerait le test et masquerait que la
    cascade compte les jetons de chaque étage : mieux vaut le vrai type.
    """
    from llm import passerelle
    return passerelle.ReponseLLM(
        texte=texte, modele="mock", appel_type=passerelle.TYPE_QUESTION,
        tokens_in=5, tokens_out=5,
    )


def _armer_cascade(db, monkeypatch):
    monkeypatch.setattr(routeur, "SessionLocal", lambda: db)
    monkeypatch.setattr(cq, "SessionLocal", lambda: db)
    monkeypatch.setattr(rc, "SessionLocal", lambda: db)

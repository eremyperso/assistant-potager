"""
tests/test_us099_corpus_fonctionnement.py
[US-099] Apprendre à l'assistant à expliquer sa propre application

Couverture des critères d'acceptance CA1 → CA12 et des cinq scénarios Gherkin.

Trois partis pris expliquent la forme de ce fichier :

- **Ces tests portent sur du CONTENU, pas sur du code.** Le livrable d'US-099
  est un corpus éditorial ; les tests le traitent donc comme du code — ils
  lisent les fiches réelles de `data/connaissance/doc_app/`, pas des fixtures
  écrites pour l'occasion. Un test qui ingérerait un corpus de laboratoire
  passerait au vert avec un corpus de production faux.

- **Le CA9 (« tenue dans le temps ») est le plus important et le moins
  spontané.** Il ne se vérifie pas sur un comportement : il se vérifie sur une
  trace. `data/connaissance/doc_app/README.md` porte la table « ce qui rend une
  fiche fausse », et le test échoue dès qu'une fiche n'y figure pas — c'est ce
  qui empêche le corpus de devenir, en quelques mois, un mensonge documenté.

- **Le CA11 est mesuré, pas affirmé.** Le corpus de questions est un fichier
  versionné (`tests/corpus/us099_questions_fonctionnement.csv`) et le test
  vérifie le rang réel de chaque réponse attendue, comme le fait
  `tools/mesurer_corpus_savoir.py` hors des tests.

⚠️ Ces tests tournent sur SQLite (`tests/conftest.py`), donc sur le repli de
`app/services/connaissance.py`. Ils protègent la RÉDACTION contre les
régressions ; le classement réel en production se remesure contre PostgreSQL
avec `python tools/mesurer_corpus_savoir.py --corpus
tests/corpus/us099_questions_fonctionnement.csv --racine data/connaissance/doc_app`.
"""
import csv
import re
from pathlib import Path
from unittest.mock import patch

import pytest

import bot
from app.services import cache_questions as cq
from app.services import connaissance
from app.services import metriques_routage as svc_metriques
from app.services import reponses_chiffrees as rc
from app.services.context import TenantContext
from database.models import CultureConfig, KnowledgeChunk, KnowledgeDocument, Potager, RoutageLog, User
from llm import routeur
from tools import controler_aide_corpus as controle
from tools import ingerer_connaissance as ing

RACINE = Path(__file__).resolve().parents[1]
CORPUS = RACINE / "data" / "connaissance" / "doc_app"
QUESTIONS = RACINE / "tests" / "corpus" / "us099_questions_fonctionnement.csv"
LISEZ_MOI = CORPUS / "README.md"
PREFIXE = "data/connaissance/doc_app/"

CTX = TenantContext(user_id=1, potager_id=1, role="owner")

# [CA1] Les dix sujets que l'US exige, et la fiche qui les porte. Écrit ici
# plutôt que déduit du dossier : c'est la LISTE DE L'US qui fait foi, et un
# renommage de fichier doit casser ce test, pas passer inaperçu.
SUJETS_ATTENDUS: dict[str, str] = {
    "le calcul du stock": "stock-plants-calcul.md",
    "la mise en godet": "semis-godet-plantation.md",
    "le chaînage semis → godet → plantation": "semis-godet-plantation.md",
    "cultures végétatives et reproductrices": "recoltes-et-pertes.md",
    "la pépinière par lot": "pepiniere-par-lot.md",
    "les parcelles et le plan d'occupation": "parcelles-et-plan.md",
    "la lecture du journal": "journal-et-corrections.md",
    "le cycle de vie d'un potager": "potager-cycle-de-vie.md",
    "le partage et les rôles": "potager-partage-et-roles.md",
    "l'activation du compagnon Telegram": "compagnon-telegram.md",
}

# [CA3] Ce qui n'a rien à faire dans un texte servi au jardinier. Volontairement
# des IDENTIFIANTS techniques et non des mots français : « parcelle » et
# « journal » sont le vocabulaire du jardinier, `culture_config` ne l'est pas.
MOTIFS_INTERDITS: dict[str, "re.Pattern[str]"] = {
    "numéro d'US": re.compile(r"\bUS-\d"),
    "identifiant technique": re.compile(r"\b[a-z]+_[a-z_]+\b"),
    "nom de fichier": re.compile(r"\.(py|sql|md|json)\b"),
    "requête SQL": re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE)\b"),
    "adresse e-mail": re.compile(r"[\w.+-]+@[\w-]+\.[a-z]{2,}"),
}


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
    """Un potager et une culture globale — le décor minimal d'une recherche."""
    test_db.add(User(id=1, email="a@potager.test"))
    test_db.flush()
    test_db.add(Potager(id=1, nom="Jardin A", proprietaire_id=1))
    test_db.add(CultureConfig(nom="tomate", type_organe_recolte="reproducteur", potager_id=None))
    test_db.commit()
    return test_db


def _ingerer(db) -> ing.Rapport:
    rapport = ing.Rapport()
    for chemin in sorted(CORPUS.rglob("*.md")):
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
    lues, erreurs = controle.lire_fiches(CORPUS)
    assert not erreurs, erreurs
    return lues


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


@pytest.fixture
def sans_appel_modele():
    """[CA8] Fait échouer le test si un modèle est appelé sur un chemin de savoir."""
    with patch("llm.passerelle.appeler_chat", side_effect=AssertionError(
        "Un appel au modèle a eu lieu sur l'étage du savoir, qui doit coûter zéro jeton"
    )):
        yield


# ═════════════════════════════════════════════════════════════════════════════
# CA1 / CA2 — le contenu couvre les sujets, et il répond à des questions
# ═════════════════════════════════════════════════════════════════════════════
def test_us099_ca1_les_dix_sujets_exiges_ont_leur_fiche():
    """CA1 — les dix sujets énumérés par l'US existent dans le dépôt."""
    presentes = {chemin.name for chemin in CORPUS.glob("*.md")}
    for sujet, fichier in SUJETS_ATTENDUS.items():
        assert fichier in presentes, f"sujet non couvert : {sujet} (fiche {fichier} absente)"


def test_us099_ca1_chaque_sujet_est_reellement_interrogeable(corpus, sans_appel_modele):
    """CA1 — une fiche présente mais introuvable ne couvre rien. Chaque sujet
    est donc vérifié par une question, pas par la présence d'un fichier."""
    db, _ = corpus
    interrogations = {
        "stock-plants-calcul.md": "comment est calculé mon stock ?",
        "semis-godet-plantation.md": "est-ce que planter mes godets les retire de la pepiniere ?",
        "recoltes-et-pertes.md": "pourquoi mon stock de tomate ne baisse pas quand je recolte ?",
        "pepiniere-par-lot.md": "c'est quoi un lot de semis ?",
        "parcelles-et-plan.md": "a quoi sert une parcelle ?",
        "journal-et-corrections.md": "comment corriger une saisie mal comprise ?",
        "potager-cycle-de-vie.md": "a quoi sert l'archivage d'un potager ?",
        "potager-partage-et-roles.md": "comment inviter quelqu'un a rejoindre mon jardin ?",
        "compagnon-telegram.md": "comment activer le compagnon de terrain ?",
    }
    for fichier, question in interrogations.items():
        contexte = connaissance.rechercher(db, CTX, question, limite=3)
        origines = {ref.split("#", 1)[0].rsplit("/", 1)[-1] for ref in contexte.references}
        assert fichier in origines, f"« {question} » ne retrouve pas {fichier} (trouvé : {origines})"


def test_us099_ca2_chaque_fragment_repond_a_une_question_posable(corpus):
    """CA2 — « chaque fiche répond à des questions réellement posables », et non
    à une arborescence de fonctionnalités. Le contrôle : tout fragment indexé
    est la réponse attendue d'au moins une question du corpus de mesure. Un
    fragment que personne n'a su formuler en question est un fragment écrit
    depuis le plan de l'application, pas depuis le jardinier."""
    db, _ = corpus
    indexes = {reference for (reference,) in db.query(KnowledgeChunk.reference).all()}
    interroges = {attendu for _, attendu in _questions_attendues()}
    orphelins = sorted(r.rsplit("/", 1)[-1] for r in indexes - interroges)
    assert not orphelins, f"fragments sans question correspondante : {orphelins}"


def test_us099_ca2_chaque_section_porte_une_question_pas_une_etiquette(corpus):
    """CA2 — l'intitulé d'une section est la question déguisée : « Comment le
    stock est calculé » en est une, « Stock » n'en est pas une."""
    db, _ = corpus
    for intitule, in db.query(KnowledgeChunk.intitule).all():
        assert intitule, "un fragment sans intitulé est un fragment sans question"
        assert len(intitule.split()) >= 4, f"intitulé trop court pour être une question : {intitule!r}"


# ═════════════════════════════════════════════════════════════════════════════
# CA3 / CA4 / CA5 / CA6 — la matière servie
# ═════════════════════════════════════════════════════════════════════════════
def test_us099_ca3_aucun_vocabulaire_technique_dans_le_texte_servi(corpus):
    """CA3 — ni nom de table, ni nom de fonction, ni numéro d'US : le texte
    part TEL QUEL dans un message au jardinier, source comprise."""
    db, _ = corpus
    lignes = db.query(
        KnowledgeChunk.reference, KnowledgeChunk.titre_document,
        KnowledgeChunk.intitule, KnowledgeChunk.contenu,
    ).all()
    sources = {source for (source,) in db.query(KnowledgeDocument.source).all()}
    fautes: list[str] = []
    for reference, titre, intitule, contenu in lignes:
        texte = " ".join(filter(None, (titre, intitule, contenu)))
        for libelle, motif in MOTIFS_INTERDITS.items():
            for occurrence in motif.findall(texte):
                fautes.append(f"{reference.rsplit('/', 1)[-1]} · {libelle} : {occurrence}")
    for source in sources:
        for libelle, motif in MOTIFS_INTERDITS.items():
            if motif.search(source):
                fautes.append(f"source affichée « {source} » · {libelle}")
    assert not fautes, fautes


def test_us099_ca4_ce_qui_consomme_un_pied_est_dit_explicitement(corpus, sans_appel_modele):
    """CA4 — « une réponse fausse à cet endroit fait douter de tout le stock ».
    Les deux cas sont écrits, et chacun se retrouve par la question qui le pose."""
    db, _ = corpus

    continue_ = connaissance.rechercher(db, CTX, "pourquoi mon stock de tomate ne baisse pas quand je recolte ?")
    assert continue_.suffisant, "la question la plus prévisible doit être servie telle quelle"
    assert "reproductrice" in connaissance.restituer(continue_).lower()

    destructive = connaissance.rechercher(db, CTX, "quelles cultures perdent un pied a chaque recolte ?")
    assert "vegetative" in _sans_accent(connaissance.restituer(destructive))


def _sans_accent(texte: str) -> str:
    from unidecode import unidecode
    return unidecode(texte).lower()


def test_us099_ca5_famille_partage_et_niveau_de_confiance(corpus):
    """CA5 — famille `doc_app`, `potager_id` nul (savoir partagé), niveau
    `verifie` : c'est ce triplet qui autorise à servir le texte mot pour mot."""
    db, _ = corpus
    documents = db.query(KnowledgeDocument).all()
    assert documents, "le corpus ne doit pas être vide"
    for document in documents:
        assert document.famille == connaissance.FAMILLE_DOC_APP, document.reference
        assert document.potager_id is None, document.reference
        assert document.niveau_confiance == connaissance.NIVEAU_VERIFIE, document.reference
    for fragment in db.query(KnowledgeChunk).all():
        assert fragment.potager_id is None, fragment.reference


def test_us099_ca6_aucune_donnee_personnelle_ni_potager_reel(fiches, corpus):
    """CA6 — aucune adresse, aucun numéro, aucun exemple tiré d'un potager réel.
    Un `potager_id` dans un en-tête suffirait à faire d'une fiche partagée un
    fragment privé : il est refusé ici, pas seulement à l'ingestion."""
    db, _ = corpus
    for fiche in fiches:
        entete, _corps = ing.lire_entete(fiche.chemin.read_text(encoding="utf-8"))
        assert not entete.get("potager_id"), f"{fiche.chemin.name} porte un potager_id"
    telephone = re.compile(r"\b0[1-9](?:[ .-]?\d{2}){4}\b")
    for reference, contenu in db.query(KnowledgeChunk.reference, KnowledgeChunk.contenu).all():
        assert not telephone.search(contenu), reference
        assert "@" not in contenu, reference


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — le sommaire et la forme longue ne divergent pas
# ═════════════════════════════════════════════════════════════════════════════
def test_us099_ca7_chaque_domaine_de_l_aide_possede_une_fiche(fiches):
    """CA7 — le contrôle automatisé exigé par l'US. Il échoue en intégration
    continue dès qu'un domaine annoncé par `/help` n'a plus de fiche."""
    rapport = controle.controler(bot._HELP_DOMAINES, fiches)
    assert not rapport.manquants, (
        f"domaines annoncés par /help sans aucune fiche : {rapport.manquants}"
    )
    assert rapport.conforme


def test_us099_ca7_aucune_fiche_ne_se_reclame_d_un_domaine_inconnu(fiches):
    """CA7 — l'écart symétrique : une fiche qui déclare un domaine que `/help`
    ne connaît pas est presque toujours une faute de frappe dans l'en-tête."""
    rapport = controle.controler(bot._HELP_DOMAINES, fiches)
    assert not rapport.orphelins, f"domaines déclarés hors de /help : {rapport.orphelins}"


def test_us099_ca7_le_sommaire_derive_des_domaines_et_ne_les_recopie_pas():
    """CA7 — `/help` affiche exactement les domaines contrôlés. Une liste
    recopiée à la main divergerait, et le contrôle porterait alors sur une
    liste que le jardinier ne voit pas."""
    assert bot._HELP_MOTS_CLES == " · ".join(bot._HELP_DOMAINES)
    for domaine in bot._HELP_DOMAINES:
        assert domaine in bot._HELP_CONTEXTUEL, f"/help {domaine} n'affiche aucune aide"


def test_us099_ca7_aucune_aide_contextuelle_n_echappe_au_controle():
    """CA7 — un domaine d'aide ajouté sans entrer dans `_HELP_DOMAINES`
    resterait invisible du contrôle de couverture : il serait annoncé au
    jardinier sans qu'aucune fiche ne lui soit jamais réclamée."""
    couverts = {id(bot._HELP_CONTEXTUEL[d]) for d in bot._HELP_DOMAINES}
    for mot_cle, texte in bot._HELP_CONTEXTUEL.items():
        assert id(texte) in couverts, (
            f"l'aide « {mot_cle} » n'est rattachée à aucun domaine de _HELP_DOMAINES"
        )


def test_us099_ca7_le_corpus_ne_recopie_pas_le_texte_de_l_aide(corpus):
    """CA7 — « le sommaire renvoie vers un contenu, il ne le duplique pas ».
    Une fiche qui recopierait les lignes de commande de `/help` en ferait une
    seconde version, condamnée à diverger."""
    db, _ = corpus
    for reference, contenu in db.query(KnowledgeChunk.reference, KnowledgeChunk.contenu).all():
        assert "→ /" not in contenu, f"{reference} recopie la syntaxe de /help"
        assert not re.search(r"^\s*/\w+", contenu, re.MULTILINE), (
            f"{reference} énumère des commandes au lieu d'expliquer"
        )


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — servi par l'étage du savoir, sans appel au modèle, avec la source
# ═════════════════════════════════════════════════════════════════════════════
def _armer_cascade(db, monkeypatch):
    monkeypatch.setattr(routeur, "SessionLocal", lambda: db)
    monkeypatch.setattr(cq, "SessionLocal", lambda: db)
    monkeypatch.setattr(rc, "SessionLocal", lambda: db)


def test_us099_ca8_une_question_de_fonctionnement_est_servie_a_cout_nul(corpus, monkeypatch):
    """CA8 — traitée par l'étage du savoir, sans appel au modèle, source citée."""
    db, _ = corpus
    _armer_cascade(db, monkeypatch)

    with patch("llm.passerelle.appeler_chat", side_effect=AssertionError("zéro jeton attendu")):
        reponse = routeur.repondre_avec_cascade(CTX, "a quoi sert l'archivage d'un potager ?")

    assert reponse.etage_resolveur == routeur.ETAGE_SAVOIR
    assert "lecture seule" in reponse.texte
    assert "_Source : " in reponse.texte
    ligne = db.query(RoutageLog).order_by(RoutageLog.id.desc()).first()
    assert ligne.issue_savoir == connaissance.ISSUE_SERVI
    assert ligne.tokens_consommes == 0


def test_us099_ca8_une_question_de_mecanisme_n_est_pas_prise_pour_une_donnee(corpus):
    """CA8 — « comment est calculé mon stock ? » demande une RÈGLE ; « quel est
    mon stock ? » demande un chiffre. Les deux phrases partagent leurs mots,
    pas leur intention : sans cette distinction, la première recevait un
    agrégat en guise d'explication, sans que le corpus soit consulté."""
    assert routeur.classer_demande(
        "comment est calculé mon stock de tomates ?", CTX
    ).nature == routeur.NATURE_QUESTION_SAVOIR
    assert routeur.classer_demande(
        "a quoi sert l'archivage d'un potager ?", CTX
    ).nature == routeur.NATURE_QUESTION_SAVOIR
    # …et la question de donnée reste une question de donnée.
    assert routeur.classer_demande(
        "combien de tomates ai-je récoltées ?", CTX
    ).nature == routeur.NATURE_QUESTION_DATA


def test_us099_ca8_la_source_citee_est_lisible_par_un_jardinier(corpus, sans_appel_modele):
    """CA8 — la source est AFFICHÉE : elle doit se lire, pas se décoder."""
    db, _ = corpus
    contexte = connaissance.rechercher(db, CTX, "a quoi sert une parcelle ?")
    assert contexte.sources == ("Guide de l'Assistant Potager",)
    assert connaissance.restituer(contexte).endswith("_Source : Guide de l'Assistant Potager_")


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — tenue dans le temps
# ═════════════════════════════════════════════════════════════════════════════
def test_us099_ca9_chaque_fiche_declare_ce_qui_la_rendrait_fausse(fiches):
    """CA9 — « une évolution qui rend une fiche fausse impose sa mise à jour
    dans la même livraison ». Ce point n'est tenable que si l'on sait, en
    touchant un calcul, quelle fiche relire : c'est la table de relecture du
    README, et une fiche qui n'y figure pas ne sera jamais relue."""
    table = LISEZ_MOI.read_text(encoding="utf-8")
    manquantes = [f.chemin.name for f in fiches if f"`{f.chemin.name}`" not in table]
    assert not manquantes, (
        f"fiches absentes de la table de relecture de {LISEZ_MOI.name} : {manquantes}"
    )


def test_us099_ca9_la_table_de_relecture_ne_cite_aucune_fiche_disparue(fiches):
    """CA9 — l'écart inverse : une ligne de table qui survit à sa fiche envoie
    relire un fichier qui n'existe plus."""
    table = LISEZ_MOI.read_text(encoding="utf-8")
    presentes = {f.chemin.name for f in fiches}
    citees = set(re.findall(r"`([\w-]+\.md)`", table)) - {"README.md"}
    assert citees <= presentes, f"fiches citées mais absentes du dossier : {citees - presentes}"


# ═════════════════════════════════════════════════════════════════════════════
# CA10 — ingéré comme une migration, et rejouable
# ═════════════════════════════════════════════════════════════════════════════
def test_us099_ca10_le_corpus_s_ingere_sans_erreur_ni_defaut_de_decoupage(corpus):
    """CA10 — l'ingestion d'US-098 accepte le corpus, `--strict` compris : aucun
    fragment ne dépend de celui qui le précède."""
    _, rapport = corpus
    assert not rapport.erreurs, rapport.erreurs
    assert not rapport.avertissements, rapport.avertissements
    assert rapport.crees == len(list(CORPUS.glob("*.md"))) - 1  # le README n'est pas du contenu
    assert rapport.fragments > 0


def test_us099_ca10_reingerer_un_corpus_inchange_n_ecrit_rien(corpus):
    """CA10 — « idempotente et sans effet si le contenu n'a pas changé » : c'est
    ce qui autorise à la rejouer à chaque déploiement, comme une migration."""
    db, premier = corpus
    second = _ingerer(db)
    assert second.inchanges == premier.crees
    assert second.crees == 0 and second.mis_a_jour == 0 and second.fragments == 0


@pytest.mark.parametrize("chemin", [
    ".github/workflows/deploy.yml",       # prod — le chemin réellement emprunté
    ".github/workflows/deploy-dev.yml",   # dev  — idem
    "deploy.sh",                          # script historique, gardé cohérent
    "update_dev.ps1",                     # poste de développement
])
def test_us099_ca10_l_ingestion_fait_partie_du_deploiement(chemin):
    """CA10 — « son ingestion est intégrée au déploiement au même titre qu'une
    migration ». Une fiche corrigée dans le dépôt mais jamais réingérée reste
    fausse en production, ce que le CA9 interdit.

    Les QUATRE chemins de déploiement sont vérifiés, pas seulement `deploy.sh` :
    le déploiement réel passe par les workflows GitHub, et n'y contrôler que le
    script historique reviendrait à valider un chemin que personne n'emprunte."""
    contenu = (RACINE / chemin).read_text(encoding="utf-8")
    assert "tools/controler_aide_corpus.py" in contenu, f"{chemin} n'exécute pas le contrôle CA7"
    assert "tools/ingerer_connaissance.py" in contenu, f"{chemin} n'ingère pas le corpus"


@pytest.mark.parametrize("chemin", [
    ".github/workflows/deploy.yml",
    ".github/workflows/deploy-dev.yml",
])
def test_us099_ca10_l_ingestion_suit_les_migrations_et_precede_le_redemarrage(chemin):
    """CA10 — l'ordre n'est pas indifférent : ingérer avant d'avoir appliqué les
    migrations écrirait dans des tables absentes, et ingérer après le
    redémarrage servirait l'ancien corpus jusqu'au déploiement suivant."""
    contenu = (RACINE / chemin).read_text(encoding="utf-8")
    migrations = contenu.index("name: Apply SQL migrations")
    ingestion = contenu.index("name: Ingest knowledge corpus")
    redemarrage = contenu.index("name: Restart systemd services")
    assert migrations < ingestion < redemarrage


@pytest.mark.parametrize("chemin", [
    ".github/workflows/deploy.yml",
    ".github/workflows/deploy-dev.yml",
    "deploy.sh",
    "update_dev.ps1",
])
def test_us099_ca10_une_fiche_supprimee_quitte_l_index(chemin):
    """CA9/CA10 — supprimer une fiche du dépôt est la façon de RETIRER un
    contenu devenu faux. Sans `--elaguer`, elle resterait indexée et continuerait
    d'être servie, indéfiniment et sans que rien ne le signale."""
    contenu = (RACINE / chemin).read_text(encoding="utf-8")
    assert "--elaguer" in contenu, f"{chemin} n'élague pas les fiches disparues"


# ═════════════════════════════════════════════════════════════════════════════
# CA11 — mesure du classement
# ═════════════════════════════════════════════════════════════════════════════
def test_us099_ca11_le_corpus_de_questions_est_suffisant():
    """CA11 — « un jeu d'au moins 20 questions de fonctionnement »."""
    questions = _questions_attendues()
    assert len(questions) >= 20, f"{len(questions)} questions, 20 exigées"
    assert len({q for q, _ in questions}) == len(questions), "questions dupliquées"


def test_us099_ca11_tous_les_fragments_attendus_existent(corpus):
    """CA11 — une attente qui ne désigne aucun fragment mesurerait le vide.
    Ce test tombe aussi quand une section est renommée sans que le corpus de
    mesure suive."""
    db, _ = corpus
    indexes = {reference for (reference,) in db.query(KnowledgeChunk.reference).all()}
    inconnus = sorted({attendu for _, attendu in _questions_attendues()} - indexes)
    assert not inconnus, f"fragments attendus introuvables : {inconnus}"


def test_us099_ca11_la_bonne_fiche_sort_dans_les_trois_premiers(corpus):
    """CA11 — la cible de l'US, vérifiée question par question."""
    db, _ = corpus
    echecs = []
    for question, attendu in _questions_attendues():
        rang = _rang(db, question, attendu)
        if rang is None or rang > 3:
            echecs.append(f"« {question} » → {'absent' if rang is None else f'rang {rang}'}")
    assert not echecs, "\n".join(echecs)


# ═════════════════════════════════════════════════════════════════════════════
# CA12 — ce que le corpus ne sait pas dire alimente la liste de rédaction
# ═════════════════════════════════════════════════════════════════════════════
def test_us099_ca12_une_question_sans_fiche_est_une_issue_vide(corpus, sans_appel_modele):
    """CA12 — une question de fonctionnement hors corpus ne trouve rien, et le
    dit. C'est cette issue, et non un silence, qui alimente la rédaction."""
    db, _ = corpus
    contexte = connaissance.rechercher(db, CTX, "c'est quoi le calendrier lunaire ?")
    assert contexte.issue == connaissance.ISSUE_VIDE
    assert contexte.passages == ()


def test_us099_ca12_les_questions_sans_reponse_forment_la_liste_de_redaction(base):
    """CA12 — « elles constituent la liste de rédaction de la version
    suivante » : la journalisation d'US-097 les remonte telles quelles."""
    base.add_all([
        RoutageLog(potager_id=1, question_normalisee="cest quoi le calendrier lunaire",
                   nature=routeur.NATURE_QUESTION_SAVOIR, origine_classification="regle",
                   etage_resolveur=routeur.ETAGE_RAISONNEMENT, cascade_remontee=False,
                   score_savoir=0.0, issue_savoir=connaissance.ISSUE_VIDE),
        RoutageLog(potager_id=1, question_normalisee="cest quoi le calendrier lunaire",
                   nature=routeur.NATURE_QUESTION_SAVOIR, origine_classification="regle",
                   etage_resolveur=routeur.ETAGE_RAISONNEMENT, cascade_remontee=False,
                   score_savoir=0.0, issue_savoir=connaissance.ISSUE_VIDE),
    ])
    base.commit()

    lacunes = svc_metriques.questions_sans_savoir(base)
    assert lacunes[0]["question_normalisee"] == "cest quoi le calendrier lunaire"
    assert lacunes[0]["nb"] == 2


# ═════════════════════════════════════════════════════════════════════════════
# Les scénarios Gherkin de l'US
# ═════════════════════════════════════════════════════════════════════════════
def test_us099_gherkin_l_assistant_explique_le_calcul_du_stock(corpus, monkeypatch):
    """Gherkin 1 — « la réponse explique la règle avec ses mots, elle cite la
    fiche dont elle est issue, et aucun appel au modèle n'a lieu »."""
    db, _ = corpus
    _armer_cascade(db, monkeypatch)

    with patch("llm.passerelle.appeler_chat", side_effect=AssertionError("zéro jeton attendu")):
        reponse = routeur.repondre_avec_cascade(CTX, "comment est calculé mon stock de tomates ?")

    assert reponse.etage_resolveur == routeur.ETAGE_SAVOIR
    assert "se déduit des gestes enregistrés" in reponse.texte
    assert "_Source : Guide de l'Assistant Potager_" in reponse.texte


def test_us099_gherkin_la_notion_de_culture_reproductrice_est_expliquee(corpus, monkeypatch):
    """Gherkin 2 — le jardinier ne comprend pas pourquoi ses haricots ne
    diminuent pas après récolte ; la réponse explique la différence entre
    culture végétative et culture reproductrice."""
    db, _ = corpus
    _armer_cascade(db, monkeypatch)

    with patch("llm.passerelle.appeler_chat", side_effect=AssertionError("zéro jeton attendu")):
        reponse = routeur.repondre_avec_cascade(
            CTX, "pourquoi mes haricots ne diminuent pas quand je les récolte ?")

    assert reponse.etage_resolveur == routeur.ETAGE_SAVOIR
    assert "reproductrices" in reponse.texte
    assert "haricot" in reponse.texte


def test_us099_gherkin_sommaire_et_corpus_alignes(fiches):
    """Gherkin 3 — « chaque domaine du sommaire possède au moins une fiche »."""
    rapport = controle.controler(controle.domaines_de_l_aide(), fiches)
    assert rapport.conforme
    assert all(rapport.couverture.values())


def test_us099_gherkin_une_fiche_perdue_fait_echouer_le_controle(fiches):
    """Gherkin 4 — le pendant du précédent : le contrôle DOIT tomber quand une
    fiche disparaît. Sans cette vérification, on ne saurait pas si le contrôle
    passe parce que tout va bien ou parce qu'il ne contrôle rien."""
    survivantes = [f for f in fiches if "stock" not in f.domaines]
    rapport = controle.controler(bot._HELP_DOMAINES, survivantes)
    assert rapport.manquants == ("stock",)
    assert not rapport.conforme


def test_us099_gherkin_question_sans_fiche_remontee_pour_redaction(corpus, monkeypatch):
    """Gherkin 5 — une question de fonctionnement qui ne trouve aucun fragment
    figure dans la liste de rédaction consultée par l'administrateur."""
    db, _ = corpus
    _armer_cascade(db, monkeypatch)

    from llm.passerelle import ReponseLLM
    from llm import passerelle
    reponse_modele = ReponseLLM(texte="Je ne sais pas encore répondre à cela.", modele="mock",
                                appel_type=passerelle.TYPE_QUESTION, tokens_in=5, tokens_out=5)
    with patch("llm.passerelle.appeler_chat", return_value=reponse_modele):
        routeur.repondre_avec_cascade(CTX, "c'est quoi le calendrier lunaire ?")

    ligne = db.query(RoutageLog).order_by(RoutageLog.id.desc()).first()
    assert ligne.issue_savoir == connaissance.ISSUE_VIDE
    lacunes = svc_metriques.questions_sans_savoir(db)
    assert any("calendrier lunaire" in l["question_normalisee"] for l in lacunes)


# ═════════════════════════════════════════════════════════════════════════════
# Le contrôle en ligne de commande — celui que joue le déploiement
# ═════════════════════════════════════════════════════════════════════════════
def _fiche_minimale(dossier: Path, nom: str, domaines: "str | None") -> Path:
    entete = ["---", "titre: Fiche d'essai", "famille: doc_app",
              "source: Guide de l'Assistant Potager", "niveau_confiance: verifie"]
    if domaines is not None:
        entete.append(f"domaines_aide: {domaines}")
    entete.append("---")
    chemin = dossier / nom
    chemin.write_text(
        "\n".join(entete) + "\n\n## Une section qui répond à une question\n\n"
        "Un texte assez long pour porter une idée répondable telle quelle, "
        "sans dépendre de ce qui précède ni de ce qui suit.\n",
        encoding="utf-8",
    )
    return chemin


def test_us099_ca7_l_outil_valide_le_corpus_reel_du_depot(capsys):
    """CA7 — l'outil que joue le déploiement rend 0 sur le corpus livré."""
    assert controle.main([]) == 0
    assert "Chaque domaine annoncé par /help est couvert" in capsys.readouterr().out


def test_us099_ca7_l_outil_detaille_la_couverture_domaine_par_domaine(capsys):
    """CA7 — le rapport nomme la fiche retenue : un contrôle qui dit seulement
    « conforme » n'aide pas à écrire la fiche manquante le jour où il tombe."""
    assert controle.main(["--detail"]) == 0
    sortie = capsys.readouterr().out
    for domaine in bot._HELP_DOMAINES:
        assert domaine in sortie


def test_us099_ca7_l_outil_echoue_sur_un_domaine_sans_fiche(tmp_path, capsys):
    """CA7 — « échouer en intégration continue si un domaine n'est plus
    couvert » : le code de retour, pas seulement un message."""
    _fiche_minimale(tmp_path, "fiche-partielle.md", "stock")
    assert controle.main(["--racine", str(tmp_path)]) == 1
    sortie = capsys.readouterr().out
    assert "sans aucune fiche" in sortie
    assert "parcelle" in sortie


def test_us099_ca7_une_fiche_illisible_est_une_erreur_pas_un_silence(tmp_path, capsys):
    """CA7 — un en-tête cassé ne doit pas se traduire en « domaine non
    couvert » sans qu'on sache pourquoi : la cause est nommée."""
    (tmp_path / "cassee.md").write_text("Pas d'en-tête du tout.\n", encoding="utf-8")
    fiches, erreurs = controle.lire_fiches(tmp_path)
    assert fiches == [] and len(erreurs) == 1 and "en-tête absent" in erreurs[0]
    assert controle.main(["--racine", str(tmp_path)]) == 1
    assert "illisible" in capsys.readouterr().out


def test_us099_ca7_une_racine_absente_est_signalee(tmp_path, capsys):
    """CA7 — un dossier introuvable rend un code distinct de l'échec de
    couverture : se tromper de chemin n'est pas la même erreur que livrer un
    corpus incomplet."""
    assert controle.main(["--racine", str(tmp_path / "nulle-part")]) == 2
    assert "introuvable" in capsys.readouterr().out


def test_us099_ca7_le_domaine_orphelin_avertit_sans_bloquer(tmp_path, capsys):
    """CA7 — une fiche qui se réclame d'un domaine inconnu de `/help` est
    signalée, jamais bloquante : c'est une coquille d'en-tête, pas une promesse
    non tenue au jardinier."""
    for domaine in bot._HELP_DOMAINES:
        _fiche_minimale(tmp_path, f"fiche-{domaine}.md", domaine)
    _fiche_minimale(tmp_path, "fiche-inventee.md", "verger")
    assert controle.main(["--racine", str(tmp_path)]) == 0
    assert "absent(s) de /help" in capsys.readouterr().out


def test_us099_ca7_les_domaines_se_lisent_quel_que_soit_le_separateur():
    """CA7 — `culture ; fiche` et `culture, fiche` déclarent la même chose ;
    la casse et les accents ne changent rien, comme dans `/help`."""
    assert controle.decouper_domaines("culture ; fiche") == ("culture", "fiche")
    assert controle.decouper_domaines("culture, fiche") == ("culture", "fiche")
    assert controle.decouper_domaines("Récolte") == ("recolte",)
    assert controle.decouper_domaines("stock ; stock") == ("stock",)
    assert controle.decouper_domaines(None) == ()
    assert controle.decouper_domaines("") == ()

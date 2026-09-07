"""
tests/test_us098_socle_connaissance.py
[US-098] Doter l'assistant d'une base de connaissance interrogeable en plein texte

Couverture des critères d'acceptance CA1 → CA14, amendement du 25/08/2026 inclus
(CA2 en référence de culture, CA2bis).

Trois partis pris expliquent la forme de ce fichier :

- **Le « zéro appel modèle » du CA8 se démontre, il ne s'affirme pas.** Un
  double fait échouer le test dès que `llm.passerelle.appeler_chat` est
  sollicité sur un chemin de savoir. C'est le même dispositif que
  `tests/test_us095_cache_questions.py`, et pour la même raison.

- **Le CA5 est vérifié STATIQUEMENT en plus de dynamiquement.** « Il n'existe
  aucun chemin de code capable d'interroger la table sans ce filtre » est une
  affirmation sur le dépôt entier, pas sur un appel : un test qui n'exercerait
  que `rechercher()` ne dirait rien du module qui, demain, écrirait sa propre
  requête. Le test lit donc les sources.

- **Le CA9 a le statut du test d'isolation des événements (US-042).** La
  question du potager B est écrite pour matcher EXACTEMENT le fragment privé
  du potager A, mot pour mot — un test qui poserait une question quelconque ne
  prouverait rien.

⚠️ Ces tests tournent sur SQLite (`tests/conftest.py`), donc sur le repli de
`app/services/connaissance.py` et non sur la recherche plein texte française de
PostgreSQL. Ils protègent la MÉCANIQUE contre les régressions ; la mesure du
CA13 qui conditionne l'activation en production doit être rejouée sur
PostgreSQL via `python tools/mesurer_corpus_savoir.py`, ce que le CA13 ci-dessous
rappelle explicitement.
"""
import csv
import re
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services import cache_questions as cq
from app.services import connaissance
from app.services import metriques_routage as svc_metriques
from app.services import potagers as svc_potagers
from app.services import reponses_chiffrees as rc
from app.services.context import TenantContext
from database.models import (
    CultureConfig, KnowledgeChunk, KnowledgeDocument, Potager, QuestionCache,
    RoutageLog, User,
)
from llm import passerelle, routeur
from llm.passerelle import ReponseLLM
from tools import ingerer_connaissance as ing

RACINE = Path(__file__).resolve().parents[1]
CORPUS_DOCUMENTS = RACINE / "tests" / "corpus" / "us098_connaissance"
CORPUS_QUESTIONS = RACINE / "tests" / "corpus" / "us098_questions_savoir.csv"

CTX_A = TenantContext(user_id=1, potager_id=1, role="owner")
CTX_B = TenantContext(user_id=2, potager_id=2, role="owner")


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
    """Deux potagers et deux cultures globales — le décor minimal de l'isolation."""
    test_db.add_all([
        User(id=1, email="a@potager.test"),
        User(id=2, email="b@potager.test"),
    ])
    test_db.flush()
    test_db.add_all([
        Potager(id=1, nom="Jardin A", proprietaire_id=1),
        Potager(id=2, nom="Jardin B", proprietaire_id=2),
    ])
    test_db.add_all([
        CultureConfig(nom="tomate", type_organe_recolte="reproducteur", potager_id=None),
        CultureConfig(nom="courgette", type_organe_recolte="reproducteur", potager_id=None),
    ])
    test_db.commit()
    return test_db


def _document(db, reference, titre, *, famille=connaissance.FAMILLE_AGRONOMIE,
              source="Test", niveau=connaissance.NIVEAU_VERIFIE, potager_id=None,
              empreinte="e1"):
    document, _ = connaissance.enregistrer_document(
        db, reference=reference, titre=titre, famille=famille, source=source,
        niveau_confiance=niveau, empreinte=empreinte, potager_id=potager_id,
    )
    return document


def _fragment(reference, contenu, *, ordre=0, intitule=None, culture_id=None, type_=None):
    return connaissance.FragmentAIngerer(
        reference=reference, ordre=ordre, intitule=intitule, contenu=contenu,
        culture_id=culture_id, type=type_,
    )


@pytest.fixture
def corpus_ingere(base):
    """Le corpus de mesure, ingéré tel que l'outil le produirait."""
    rapport = ing.Rapport()
    for chemin in sorted(CORPUS_DOCUMENTS.rglob("*.md")):
        if chemin.name.upper() == "README.MD":
            continue
        ing.ingerer_fichier(base, chemin, RACINE, rapport)
    assert not rapport.erreurs, rapport.erreurs
    return base, rapport


@pytest.fixture
def sans_appel_modele():
    """[CA8] Fait échouer le test si un modèle est appelé sur un chemin de savoir."""
    with patch("llm.passerelle.appeler_chat", side_effect=AssertionError(
        "Un appel au modèle a eu lieu sur l'étage du savoir, qui doit coûter zéro jeton"
    )):
        yield


def _reponse_modele(texte: str) -> ReponseLLM:
    return ReponseLLM(texte=texte, modele="mock", appel_type=passerelle.TYPE_QUESTION,
                      tokens_in=10, tokens_out=20)


# ═════════════════════════════════════════════════════════════════════════════
# CA1 / CA2 / CA3 — structure
# ═════════════════════════════════════════════════════════════════════════════
def test_us098_ca1_document_porte_les_colonnes_annoncees():
    """CA1 — potager_id, titre, famille, source, niveau_confiance et les deux dates."""
    colonnes = set(KnowledgeDocument.__table__.columns.keys())
    assert {"potager_id", "titre", "famille", "source", "niveau_confiance",
            "cree_le", "mis_a_jour_le"} <= colonnes
    assert KnowledgeDocument.__table__.c.potager_id.nullable, \
        "potager_id nullable : NULL = savoir global partagé"


def test_us098_ca1_familles_et_niveaux_sont_le_vocabulaire_annonce():
    """CA1 — les trois familles et les deux niveaux de confiance, pas d'autres."""
    assert connaissance.FAMILLES == {"agronomie", "doc_app", "memoire_potager"}
    assert connaissance.NIVEAUX_CONFIANCE == {"verifie", "indicatif"}
    with pytest.raises(ValueError):
        connaissance.valider_entete("botanique", "verifie")
    with pytest.raises(ValueError):
        connaissance.valider_entete("agronomie", "certain")


def test_us098_ca2_fragment_porte_les_colonnes_annoncees():
    """CA2 — document, potager_id dénormalisé, contenu, culture, type, saison,
    vecteur plein texte et colonne d'embedding."""
    table = KnowledgeChunk.__table__
    colonnes = set(table.columns.keys())
    assert {"document_id", "potager_id", "contenu", "culture_id", "type",
            "saison", "recherche_fts", "embedding"} <= colonnes
    assert table.c.embedding.nullable
    assert table.c.culture_id.nullable, "un fragment doc_app ne se rattache à aucune culture"


def test_us098_ca2_la_culture_est_une_reference_pas_un_libelle():
    """CA2 amendé — `culture_id` est une clé étrangère vers culture_config, et
    aucune colonne texte `culture` ne subsiste sur le fragment."""
    table = KnowledgeChunk.__table__
    assert "culture" not in table.columns.keys(), \
        "un libellé texte rejouerait l'erreur corrigée par migration_v12"
    cibles = {fk.column.table.name for fk in table.c.culture_id.foreign_keys}
    assert cibles == {"culture_config"}


def test_us098_ca2_embedding_est_cree_mais_jamais_utilise():
    """CA2 — la colonne d'embedding est créée, nullable et INUTILISÉE : aucune
    lecture ni écriture nulle part dans le code applicatif."""
    sources = list((RACINE / "app").rglob("*.py")) + list((RACINE / "llm").rglob("*.py")) \
        + list((RACINE / "tools").rglob("*.py"))
    for fichier in sources:
        texte = fichier.read_text(encoding="utf-8")
        for ligne in texte.splitlines():
            depouillee = ligne.strip()
            if depouillee.startswith("#") or "embedding" not in depouillee:
                continue
            assert "Column(" in depouillee, \
                f"{fichier.name} manipule `embedding`, qui doit rester inutilisée : {depouillee}"


def test_us098_ca3_une_seule_fiche_tomate_sert_tous_les_jardins(base, sans_appel_modele):
    """CA3 — un document global (potager_id NULL) est retrouvé par les deux potagers."""
    document = _document(base, "global/tomate.md", "La tomate")
    connaissance.remplacer_fragments(base, document, [
        _fragment("global/tomate.md#00", "La tomate se conduit sur un seul pied par godet."),
    ])
    base.commit()

    for ctx in (CTX_A, CTX_B):
        contexte = connaissance.rechercher(base, ctx, "comment conduire la tomate ?")
        assert [p.reference for p in contexte.passages] == ["global/tomate.md#00"]


def test_us098_ca3_fragment_herite_du_potager_de_son_document(base):
    """CA2/CA3 — `potager_id` du fragment est dénormalisé DEPUIS le document,
    jamais saisi à part : les deux ne peuvent pas diverger."""
    document = _document(base, "prive/a.md", "Mémoire du jardin A", potager_id=1)
    connaissance.remplacer_fragments(base, document, [_fragment("prive/a.md#00", "Contenu privé.")])
    base.commit()
    fragment = base.query(KnowledgeChunk).one()
    assert fragment.potager_id == 1


# ═════════════════════════════════════════════════════════════════════════════
# CA2bis — renommer une culture n'orpheline aucun fragment
# ═════════════════════════════════════════════════════════════════════════════
def test_us098_ca2bis_renommer_une_culture_n_orpheline_aucun_fragment(base, sans_appel_modele):
    """CA2bis — le jardinier renomme « courgette » en « courgette verte » : les
    fragments suivent, et une recherche sur le nouveau nom les retrouve.

    Aucune commande `/culture renommer` n'existe à ce jour : le renommage est
    donc simulé là où toute commande future écrira — sur `culture_config.nom`.
    C'est précisément ce qui rend l'invariant vérifiable AVANT que la commande
    n'existe, et non après coup."""
    courgette = base.query(CultureConfig).filter(CultureConfig.nom == "courgette").one()
    document = _document(base, "agro/courgette.md", "La courgette")
    connaissance.remplacer_fragments(base, document, [
        _fragment("agro/courgette.md#00",
                  "Un feutrage blanc poudreux sur les feuilles signale l'oidium.",
                  culture_id=courgette.id),
    ])
    base.commit()

    courgette.nom = "courgette verte"
    base.commit()

    fragment = base.query(KnowledgeChunk).one()
    assert fragment.culture_id == courgette.id, "le fragment reste rattaché à la culture renommée"

    # La résolution passe par le référentiel : le NOUVEAU nom la trouve…
    assert connaissance.resoudre_culture(base, CTX_A, "mes courgettes vertes ont un feutrage blanc") \
        == courgette.id
    contexte = connaissance.rechercher(base, CTX_A, "feutrage blanc sur mes courgettes vertes")
    assert [p.reference for p in contexte.passages] == ["agro/courgette.md#00"]


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — recherche plein texte française, index adapté
# ═════════════════════════════════════════════════════════════════════════════
def test_us098_ca4_le_dictionnaire_francais_est_explicite_partout():
    """CA4 — la configuration est la MÊME dans la migration et dans le code.

    Elle sert à l'écriture du vecteur comme à l'interrogation : deux valeurs
    différentes ne dégraderaient pas la recherche, elles la rendraient muette.
    """
    assert connaissance.CONFIG_FTS == "french_sans_accent"
    migration = (RACINE / "migrations" / "migration_v42.sql").read_text(encoding="utf-8")
    assert "CREATE TEXT SEARCH CONFIGURATION french_sans_accent (COPY = french)" in migration, \
        "la migration doit CRÉER la configuration que le code nomme"
    assert "WITH unaccent, french_stem" in migration, \
        "l'ordre compte : unaccent replie l'accent, french_stem lemmatise ensuite"
    assert "pg_ts_config WHERE cfgname = 'french_sans_accent'" in migration, \
        "la migration doit VÉRIFIER que la configuration existe après exécution"
    assert "USING GIN (recherche_fts)" in migration
    rollback = (RACINE / "migrations" / "rollback_v42.sql").read_text(encoding="utf-8")
    assert "DROP TEXT SEARCH CONFIGURATION IF EXISTS french_sans_accent" in rollback, \
        "le rollback doit emporter la configuration créée à l'aller"


def test_us098_ca4_l_accent_ne_change_pas_le_lexeme():
    """CA4 — « recolter » et « récolter » doivent être le MÊME lexème.

    Défaut constaté en production le 04/09/2026 : sous la configuration
    `french` seule, PostgreSQL lemmatise sans retirer les accents, et
    `to_tsvector('french', 'récolter recolter')` rend `'recolt':2 'récolt':1` —
    deux lexèmes sans rapport. Le jardinier qui tapait « quand recolter mes
    carottes ? » recevait une réponse sur les carottes fourchues, là où la même
    question accentuée trouvait la bonne section. Sur un clavier mobile, taper
    sans accent est la norme, pas l'exception.

    Ce test verrouille le contrat côté repli SQLite (`unidecode`) ; côté
    PostgreSQL c'est `unaccent` dans `french_sans_accent` qui le tient, et la
    migration v42 le vérifie par une requête. Les deux moteurs divergeaient
    silencieusement sur ce point — toute mesure locale en était optimiste.
    """
    for accentue, nu in (("récolter", "recolter"), ("éclaircir", "eclaircir"),
                         ("oïdium", "oidium"), ("flétrit", "fletrit")):
        assert connaissance.lexemes(accentue) == connaissance.lexemes(nu), \
            f"{accentue!r} et {nu!r} ne produisent pas le même lexème"


def test_us098_ca4_le_vecteur_est_maintenu_a_l_ecriture(base):
    """CA4 (note technique) — le vecteur est calculé À L'ÉCRITURE du fragment,
    donc il est déjà renseigné avant toute recherche."""
    document = _document(base, "agro/mildiou.md", "Le mildiou de la tomate")
    connaissance.remplacer_fragments(base, document, [
        _fragment("agro/mildiou.md#00", "Des taches huileuses brunes apparaissent sur les feuilles."),
    ])
    base.commit()
    fragment = base.query(KnowledgeChunk).one()
    assert fragment.recherche_fts, "aucun vecteur écrit : le fragment serait introuvable"
    # Le titre du document est indexé au même titre que le contenu (poids 'A').
    assert "mildiou" in fragment.recherche_fts


def test_us098_ca4_la_recherche_reste_sous_le_seuil_de_perception(corpus_ingere):
    """CA4 — les temps de réponse sont MESURÉS. Le seuil vaut pour ce moteur ;
    la mesure de production est celle de `tools/mesurer_corpus_savoir.py`."""
    db, _ = corpus_ingere
    import time
    durees = []
    for question, _ in _questions_corpus():
        debut = time.perf_counter()
        connaissance.rechercher(db, CTX_A, question)
        durees.append((time.perf_counter() - debut) * 1000)
    durees.sort()
    p95 = durees[max(0, int(len(durees) * 0.95) - 1)]
    assert p95 < 150, f"p95 = {p95:.1f} ms"


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — le filtre d'isolation est porté par la recherche, à un seul endroit
# ═════════════════════════════════════════════════════════════════════════════
def test_us098_ca5_aucun_autre_module_n_interroge_la_table():
    """CA5 — vérification STATIQUE : `app/services/connaissance.py` est le seul
    module du dépôt à construire une requête sur `knowledge_chunks`.

    Sans ce test, l'affirmation « aucun chemin de code ne peut oublier le
    filtre » ne serait vraie que des chemins existants."""
    motif = re.compile(r"query\(\s*KnowledgeChunk|from\s+knowledge_chunks", re.IGNORECASE)
    autorises = {
        RACINE / "app" / "services" / "connaissance.py",   # le seul point de lecture
        RACINE / "database" / "models.py",                 # la déclaration du modèle
    }
    fautifs = []
    for dossier in ("app", "llm", "utils", "tools"):
        for fichier in (RACINE / dossier).rglob("*.py"):
            if fichier in autorises or "__pycache__" in fichier.parts:
                continue
            if motif.search(fichier.read_text(encoding="utf-8")):
                fautifs.append(str(fichier.relative_to(RACINE)))
    for fichier in (RACINE / "main.py", RACINE / "bot.py"):
        if motif.search(fichier.read_text(encoding="utf-8")):
            fautifs.append(fichier.name)
    assert not fautifs, f"requête directe sur knowledge_chunks hors du service : {fautifs}"


def test_us098_ca5_le_filtre_est_pose_meme_sans_metadonnee(base):
    """CA5 — le filtre est inconditionnel : il figure dans le SQL émis quelle
    que soit la question."""
    requete = connaissance._requete_base(base, CTX_A)
    sql = str(requete.statement).lower()
    assert "potager_id is null" in sql
    assert "potager_id = " in sql


def test_us098_ca5_sans_potager_courant_la_recherche_est_refusee(base):
    """CA5 — pas de repli silencieux sur un potager par défaut : sans tenant,
    une recherche n'est pas isolable, donc elle n'a pas lieu."""
    with pytest.raises(ValueError):
        connaissance.rechercher(base, TenantContext(user_id=1, potager_id=None), "mildiou")


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — les métadonnées restreignent, mais ne vident jamais
# ═════════════════════════════════════════════════════════════════════════════
def test_us098_ca6_la_culture_detectee_restreint_la_recherche(base, sans_appel_modele):
    """CA6 — deux fiches « taches sur les feuilles », une par culture : la
    culture citée dans la question tranche."""
    tomate = base.query(CultureConfig).filter(CultureConfig.nom == "tomate").one()
    courgette = base.query(CultureConfig).filter(CultureConfig.nom == "courgette").one()
    doc = _document(base, "agro/taches.md", "Taches sur les feuilles")
    connaissance.remplacer_fragments(base, doc, [
        _fragment("agro/taches.md#00", "Des taches brunes sur les feuilles annoncent le mildiou.",
                  ordre=0, culture_id=tomate.id),
        _fragment("agro/taches.md#01", "Des taches blanches sur les feuilles annoncent l'oidium.",
                  ordre=1, culture_id=courgette.id),
    ])
    base.commit()

    contexte = connaissance.rechercher(base, CTX_A, "des taches sur les feuilles de courgette")
    assert [p.reference for p in contexte.passages] == ["agro/taches.md#01"]
    assert contexte.metadonnees_appliquees.get("culture_id") == str(courgette.id)


def test_us098_ca6_une_metadonnee_absente_est_ignoree(base, sans_appel_modele):
    """CA6 — sans culture ni type détectés, la recherche porte sur tout le socle."""
    doc = _document(base, "agro/paillage.md", "Le paillage")
    connaissance.remplacer_fragments(base, doc, [
        _fragment("agro/paillage.md#00", "Le paillage garde le sol frais et limite l'évaporation."),
    ])
    base.commit()
    contexte = connaissance.rechercher(base, CTX_A, "a quoi sert le paillage ?")
    assert contexte.passages
    assert contexte.metadonnees_appliquees == {}


def test_us098_ca6_une_restriction_qui_viderait_le_resultat_est_relachee(base, sans_appel_modele):
    """CA6 — « jamais un filtre qui vide le résultat » : la culture citée n'est
    portée par aucun fragment, la recherche est rejouée sans elle plutôt que de
    rendre la main vide."""
    doc = _document(base, "agro/arrosage.md", "Arroser au potager")
    connaissance.remplacer_fragments(base, doc, [
        # Aucune culture rattachée : la restriction par culture le viderait.
        _fragment("agro/arrosage.md#00", "Arroser tôt le matin limite fortement l'évaporation."),
    ])
    base.commit()

    contexte = connaissance.rechercher(base, CTX_A, "quand arroser mes tomates ?")
    assert [p.reference for p in contexte.passages] == ["agro/arrosage.md#00"]
    assert contexte.metadonnees_appliquees == {}, "la restriction a été relâchée, elle n'est pas revendiquée"


def test_us098_ca6_le_type_de_question_est_deterministe():
    """CA6 — la détection du type est du vocabulaire, pas un appel modèle, et
    elle rend `None` plutôt que de deviner."""
    assert connaissance.detecter_type("mes feuilles ont des taches de mildiou") == "maladie"
    assert connaissance.detecter_type("à quelle profondeur semer ?") == "semis"
    assert connaissance.detecter_type("quel délai de retour pour les solanacées ?") == "rotation"
    assert connaissance.detecter_type("bonjour") is None


# ═════════════════════════════════════════════════════════════════════════════
# CA7 / CA8 — deux issues, un contexte, jamais une réponse rédigée
# ═════════════════════════════════════════════════════════════════════════════
def test_us098_ca8_la_recherche_retourne_un_contexte_pas_une_reponse(base, sans_appel_modele):
    """CA8 — passages, sources et score ; aucun champ de réponse rédigée, et
    aucun appel au modèle sur ce chemin."""
    doc = _document(base, "agro/culnoir.md", "Le cul noir de la tomate", source="Rédaction interne")
    connaissance.remplacer_fragments(base, doc, [
        _fragment("agro/culnoir.md#00",
                  "Le cul noir est une tache noire sous le fruit, due à un manque de calcium."),
    ])
    base.commit()

    contexte = connaissance.rechercher(base, CTX_A, "pourquoi mes tomates ont le cul noir ?")
    assert contexte.passages and contexte.sources == ("Rédaction interne",)
    assert 0.0 <= contexte.confiance <= 1.0
    assert not hasattr(contexte, "reponse")
    assert not hasattr(contexte, "texte")


def test_us098_ca7_confiance_elevee_sert_la_reponse_a_cout_nul(base, sans_appel_modele):
    """CA7 — première issue : le passage vérifié est servi tel quel, zéro jeton."""
    doc = _document(base, "agro/culnoir.md", "Le cul noir de la tomate", source="Rédaction interne")
    connaissance.remplacer_fragments(base, doc, [
        _fragment("agro/culnoir.md#00",
                  "Le cul noir est une tache noire sous le fruit, due à un manque de calcium."),
    ])
    base.commit()

    contexte = connaissance.rechercher(base, CTX_A, "le cul noir de la tomate")
    assert contexte.suffisant and contexte.issue == connaissance.ISSUE_SERVI
    texte = connaissance.restituer(contexte)
    assert "manque de calcium" in texte and "Rédaction interne" in texte


def test_us098_ca7_un_passage_indicatif_n_est_jamais_servi_tel_quel(base, sans_appel_modele):
    """CA7 — un corpus qui se déclare incertain ne doit pas être présenté comme
    établi : le passage descend en contexte, il n'est pas servi."""
    doc = _document(base, "agro/consoude.md", "Le purin de consoude",
                    niveau=connaissance.NIVEAU_INDICATIF)
    connaissance.remplacer_fragments(base, doc, [
        _fragment("agro/consoude.md#00", "Le purin de consoude apporte de la potasse aux tomates."),
    ])
    base.commit()

    contexte = connaissance.rechercher(base, CTX_A, "à quoi sert le purin de consoude ?")
    assert contexte.passages, "le passage est bien trouvé"
    assert not contexte.suffisant
    assert contexte.issue == connaissance.ISSUE_TRANSMIS


def test_us098_ca7_confiance_faible_transmet_le_contexte(base, sans_appel_modele):
    """CA7 — seconde issue : le contexte descend vers l'étage supérieur, formaté
    en passages étiquetés — jamais en réponse."""
    doc = _document(base, "agro/limaces.md", "Les limaces", niveau=connaissance.NIVEAU_INDICATIF)
    connaissance.remplacer_fragments(base, doc, [
        _fragment("agro/limaces.md#00", "Les limaces mangent la nuit et laissent du mucus.",
                  intitule="Reconnaître les dégâts"),
    ])
    base.commit()

    contexte = connaissance.rechercher(base, CTX_A, "qu'est-ce qui mange mes salades la nuit ?")
    transmis = connaissance.contexte_pour_raisonnement(contexte)
    assert "Les limaces — Reconnaître les dégâts" in transmis
    assert "mucus" in transmis


def test_us098_ca7_une_reponse_reecrite_garde_son_attribution(base, monkeypatch):
    """CA7 — l'attribution suit le contenu, y compris quand le modèle l'a
    RÉÉCRIT.

    Sur le chemin `servi`, `restituer()` ajoute « _Source : … _ ». Sur le
    chemin `transmis`, la même matière partait sans aucune mention : le
    jardinier ne pouvait plus savoir que la réponse venait du corpus. Ce n'est
    pas qu'une commodité de lecture — `referentiel_source` porte des licences à
    attribution obligatoire à l'affichage (CC BY 4.0), qui couvrent aussi les
    œuvres dérivées, et une réponse rédigée à partir du texte en est une.
    """
    document = _document(base, "agro/cul-noir.md", "Le cul noir de la tomate",
                         source="Rédaction interne",
                         niveau=connaissance.NIVEAU_INDICATIF)
    connaissance.remplacer_fragments(base, document, [
        _fragment("agro/cul-noir.md#00", intitule="Le cul noir",
                  contenu="Le cul noir vient d'un apport en calcium irrégulier "
                          "pendant que le fruit grossit, souvent faute d'un "
                          "arrosage régulier."),
    ])
    base.commit()
    for module in (routeur, cq, rc):
        monkeypatch.setattr(module, "SessionLocal", lambda: base)
    monkeypatch.setattr(passerelle, "appeler_chat",
                        lambda *a, **k: _reponse_modele("Arrose plus régulièrement."))

    reponse = routeur.repondre_avec_cascade(
        CTX_A, "pourquoi mes tomates ont le cul noir ?")

    assert reponse.etage_resolveur == routeur.ETAGE_RAISONNEMENT
    assert "Arrose plus régulièrement." in reponse.texte
    assert "_D'après : Rédaction interne_" in reponse.texte, \
        "une réponse rédigée à partir du corpus doit dire de quoi elle dérive"


def test_us098_ca7_une_reponse_sans_corpus_n_invente_aucune_attribution(base, monkeypatch):
    """CA7, revers — quand la recherche ne trouve rien, la réponse ne doit
    porter AUCUNE attribution : elle ne dérive d'aucune fiche."""
    for module in (routeur, cq, rc):
        monkeypatch.setattr(module, "SessionLocal", lambda: base)
    monkeypatch.setattr(passerelle, "appeler_chat",
                        lambda *a, **k: _reponse_modele("Un pommier se taille en hiver."))
    reponse = routeur.repondre_avec_cascade(CTX_A, "comment tailler un pommier ?")
    assert "D'après" not in reponse.texte and "Source" not in reponse.texte


def test_us098_ca7_une_recherche_vide_est_une_issue_legitime(base, sans_appel_modele):
    """CA7/CA14 — base vide : aucune exception, une issue `vide` et un score nul."""
    contexte = connaissance.rechercher(base, CTX_A, "comment tailler un pommier ?")
    assert contexte.passages == () and contexte.confiance == 0.0
    assert contexte.issue == connaissance.ISSUE_VIDE


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — isolation, invariant du même rang que celui des événements (US-042)
# ═════════════════════════════════════════════════════════════════════════════
def test_us098_ca9_un_fragment_prive_du_potager_a_est_invisible_du_potager_b(base, sans_appel_modele):
    """CA9 — la question du potager B reprend MOT POUR MOT le fragment privé du
    potager A. Elle ne doit rien retourner."""
    doc_prive = _document(base, "prive/a.md", "Mémoire du jardin A", potager_id=1,
                          famille=connaissance.FAMILLE_MEMOIRE_POTAGER)
    connaissance.remplacer_fragments(base, doc_prive, [
        _fragment("prive/a.md#00",
                  "La planche nord du jardin A subit une remontée d'argile après chaque orage."),
    ])
    base.commit()

    question = "remontée d'argile sur la planche nord après chaque orage"

    contexte_a = connaissance.rechercher(base, CTX_A, question)
    assert [p.reference for p in contexte_a.passages] == ["prive/a.md#00"]
    assert contexte_a.passages[0].prive is True

    contexte_b = connaissance.rechercher(base, CTX_B, question)
    assert contexte_b.passages == (), "fuite inter-potagers sur la base de connaissance"
    assert contexte_b.issue == connaissance.ISSUE_VIDE


def test_us098_ca9_un_savoir_prive_ne_devient_jamais_une_reponse_partagee(base):
    """CA9 — corollaire côté cache : une réponse dérivée d'un passage privé
    n'est jamais mémorisée en savoir partagé (`potager_id NULL`)."""
    doc_prive = _document(base, "prive/a.md", "Mémoire du jardin A", potager_id=1,
                          famille=connaissance.FAMILLE_MEMOIRE_POTAGER)
    connaissance.remplacer_fragments(base, doc_prive, [
        _fragment("prive/a.md#00", "La planche nord subit une remontée d'argile après un orage."),
    ])
    base.commit()

    contexte = connaissance.rechercher(base, CTX_A, "remontée d'argile planche nord")
    assert contexte.passages and not contexte.contexte_partageable

    routeur._memoriser_reponse(
        CTX_A, "remontée d'argile planche nord",
        routeur.DecisionRoutage(nature=routeur.NATURE_QUESTION_SAVOIR,
                                origine=routeur.ORIGINE_REGLE, confiance=1.0),
        routeur.ETAGE_SAVOIR, None, "Ta planche nord remonte de l'argile.", contexte,
    )
    assert base.query(QuestionCache).count() == 0


# ═════════════════════════════════════════════════════════════════════════════
# CA10 / CA11 / CA12 — ingestion
# ═════════════════════════════════════════════════════════════════════════════
def test_us098_ca10_reingerer_un_document_inchange_ne_cree_aucun_doublon(base, tmp_path):
    """CA10 — l'outil est idempotent : au second passage, rien n'est écrit."""
    fiche = tmp_path / "tomate.md"
    fiche.write_text(_fiche_exemple(), encoding="utf-8")

    premier = ing.Rapport()
    ing.ingerer_fichier(base, fiche, tmp_path, premier)
    assert (premier.crees, premier.fragments) == (1, 2)
    apres_premier = base.query(KnowledgeChunk).count()

    second = ing.Rapport()
    ing.ingerer_fichier(base, fiche, tmp_path, second)
    assert (second.crees, second.mis_a_jour, second.inchanges) == (0, 0, 1)
    assert base.query(KnowledgeChunk).count() == apres_premier
    assert base.query(KnowledgeDocument).count() == 1


def test_us098_ca11_un_document_corrige_remplace_ses_fragments(base, tmp_path):
    """CA11 — réingérer un document MODIFIÉ remplace ses fragments."""
    fiche = tmp_path / "tomate.md"
    fiche.write_text(_fiche_exemple(), encoding="utf-8")
    ing.ingerer_fichier(base, fiche, tmp_path, ing.Rapport())
    avant = {c.reference for c in base.query(KnowledgeChunk).all()}

    fiche.write_text(_fiche_exemple(corrigee=True), encoding="utf-8")
    rapport = ing.Rapport()
    ing.ingerer_fichier(base, fiche, tmp_path, rapport)

    apres = {c.reference for c in base.query(KnowledgeChunk).all()}
    assert rapport.mis_a_jour == 1
    assert apres != avant, "les anciens fragments doivent avoir été remplacés"
    contenus = " ".join(c.contenu for c in base.query(KnowledgeChunk).all())
    assert "arrosage régulier" in contenus


def test_us098_ca11_une_reference_longue_est_memorisable(base):
    """CA11 — `questions_cache.fragment_id` doit pouvoir contenir ce que
    `knowledge_chunks.reference` produit.

    `migration_v36` avait dimensionné la colonne à VARCHAR(120) alors qu'aucun
    fragment n'existait encore. Une référence est un chemin de dépôt suivi d'un
    numéro d'ordre et d'un intitulé de section : sur le premier corpus
    agronomique réel, 19 des 96 fragments dépassaient cette borne. La
    mémorisation échouait alors sur un DataError PostgreSQL — rattrapé et
    journalisé, donc invisible du jardinier, mais la question repayait un appel
    modèle complet à chaque fois qu'elle était reposée (constaté le 04/09/2026).

    Le test s'exécute sous SQLite, qui n'applique pas les bornes de VARCHAR :
    il ne peut donc pas reproduire le DataError. Ce qu'il verrouille est ce qui
    l'a causé — la référence produite dépasse la borne d'origine, et le modèle
    ne la borne plus.
    """
    from database.models import QuestionCache

    reference = (
        "tests/corpus/corpus_agronomie_24_fiches/haricot-recolte-conservation.md"
        "#00-reconnaitre-une-gousse-tendre-prete-a-etre-cueillie"
    )
    assert len(reference) > 120, "l'exemple doit dépasser la borne d'origine"
    assert QuestionCache.__table__.c.fragment_id.type.length is None, \
        "fragment_id ne doit plus être borné : il reporte une reference sans borne"

    entree = cq.memoriser_figee(
        base, CTX_A, "quand cueillir les haricots verts ?",
        "Une gousse tendre se casse net entre les doigts.",
        source_etage=cq.SOURCE_RAG, fragment_id=reference,
    )
    base.commit()
    assert entree is not None and entree.fragment_id == reference
    assert cq.invalider_par_fragment(base, reference) == 1


def test_us098_ca11_la_reponse_figee_derivee_est_invalidee(base, tmp_path):
    """CA11 — une réponse figée issue d'un fragment disparu tombe à la
    réingestion. Corriger une fiche ne doit pas laisser vivre une réponse
    erronée."""
    fiche = tmp_path / "tomate.md"
    fiche.write_text(_fiche_exemple(), encoding="utf-8")
    ing.ingerer_fichier(base, fiche, tmp_path, ing.Rapport())
    reference_fragment = (
        base.query(KnowledgeChunk.reference).order_by(KnowledgeChunk.ordre).first()[0]
    )

    entree = cq.memoriser_figee(
        base, CTX_A, "pourquoi mes tomates ont le cul noir ?",
        "Le cul noir vient d'un manque de calcium.",
        source_etage=cq.SOURCE_RAG, fragment_id=reference_fragment,
    )
    assert entree is not None and base.query(QuestionCache).count() == 1

    fiche.write_text(_fiche_exemple(corrigee=True), encoding="utf-8")
    rapport = ing.Rapport()
    ing.ingerer_fichier(base, fiche, tmp_path, rapport)

    assert rapport.invalidations == 1
    assert base.query(QuestionCache).count() == 0


def test_us098_ca12_le_titre_du_document_est_conserve_sur_chaque_fragment(base, tmp_path):
    """CA12 — « contexte du titre du document conservé » : chaque fragment le
    porte, et le titre est indexé avec le contenu."""
    fiche = tmp_path / "tomate.md"
    fiche.write_text(_fiche_exemple(), encoding="utf-8")
    ing.ingerer_fichier(base, fiche, tmp_path, ing.Rapport())
    for fragment in base.query(KnowledgeChunk).all():
        assert fragment.titre_document == "Le cul noir de la tomate"
        assert "tomat" in fragment.recherche_fts


def test_us098_ca12_un_fragment_non_autonome_est_signale(base, tmp_path):
    """CA12 — « un fragment qui n'a de sens qu'avec le précédent est un défaut
    de découpage » : l'outil le signale AVANT de l'indexer."""
    fiche = tmp_path / "defaut.md"
    fiche.write_text(
        "---\ntitre: Fiche mal découpée\nfamille: agronomie\n"
        "source: Test\nniveau_confiance: verifie\n---\n\n"
        "## Première idée\n\n"
        "Le paillage garde le sol frais et limite fortement l'évaporation en été, "
        "ce qui lisse les à-coups d'humidité.\n\n"
        "## Suite\n\n"
        "Il faut alors pailler le pied, sinon rien de tout cela ne fonctionne "
        "correctement sur la durée d'une saison entière.\n",
        encoding="utf-8",
    )
    rapport = ing.Rapport()
    ing.ingerer_fichier(base, fiche, tmp_path, rapport)
    assert len(rapport.avertissements) == 1
    assert "dépend du fragment précédent" in rapport.avertissements[0]


def test_us098_ca12_un_fragment_trop_court_est_signale():
    """CA12 — un titre orphelin ou une phrase de liaison ne porte pas une idée."""
    defaut = ing.controler_autonomie(ing.Section(intitule="Bref", contenu="Voir plus haut."))
    assert defaut is not None and "trop court" in defaut


def test_us098_ingestion_refuse_une_culture_absente_du_referentiel(base, tmp_path):
    """CA2 — un libellé de culture inconnu est refusé, jamais replié en NULL
    silencieux : le fragment perdrait sa métadonnée sans que rien ne le dise."""
    fiche = tmp_path / "inconnue.md"
    fiche.write_text(
        "---\ntitre: Fiche inconnue\nfamille: agronomie\nsource: Test\n"
        "niveau_confiance: verifie\nculture: topinambour\n---\n\n"
        "## Une idée\n\nUn contenu suffisamment long pour passer le contrôle "
        "d'autonomie du découpage sans être signalé.\n",
        encoding="utf-8",
    )
    with pytest.raises(ing.DocumentInvalide, match="topinambour"):
        ing.ingerer_fichier(base, fiche, tmp_path, ing.Rapport())


def test_us098_ingestion_refuse_un_entete_incomplet(base, tmp_path):
    """Edge case — un fichier sans en-tête n'est pas deviné, il est refusé."""
    fiche = tmp_path / "sans_entete.md"
    fiche.write_text("## Une section\n\nDu contenu sans en-tête du tout.\n", encoding="utf-8")
    with pytest.raises(ing.DocumentInvalide, match="en-tête absent"):
        ing.ingerer_fichier(base, fiche, tmp_path, ing.Rapport())


# ═════════════════════════════════════════════════════════════════════════════
# Format de fiche du corpus agronomique — ce que l'ingestion doit savoir lire
# -----------------------------------------------------------------------------
# Les fiches réelles portent, en plus de l'en-tête minimal, des conventions
# d'écriture destinées au relecteur humain : guillemets, blocs en liste, titre
# H1, métadonnées de section, section de licence en pied. Aucune n'est du
# contenu de réponse. Toutes se sont révélées sur un corpus mesuré, et chacune
# de ces conventions a un test parce que chacune a produit un vrai défaut :
# fiche refusée, fragment vide servi comme faisant autorité, ou métadonnée
# envoyée telle quelle au jardinier.
# ═════════════════════════════════════════════════════════════════════════════
def _fiche_v2(niveau: str = "a-valider") -> str:
    """Une fiche au format du corpus agronomique, avec toutes ses conventions."""
    return (
        "---\n"
        'titre: "Problèmes observables de tomate"\n'
        'famille: "agronomie"\n'
        'source: "Rédaction interne"\n'
        f'niveau_confiance: "{niveau}"\n'
        'culture: "tomate"\n'
        'theme: "problemes"\n'
        "index_terms:\n"
        '  - "cul noir"\n'
        # Terme présent au niveau du DOCUMENT et dans AUCUNE section : c'est lui
        # qui rend le test de non-indexation discriminant.
        '  - "chlorose ferrique"\n'
        "sources:\n"
        '  - organisme: "USDA National Agricultural Library"\n'
        '    licence: "Domaine public"\n'
        "---\n\n"
        "# Problèmes observables de tomate\n\n"
        "## Une zone sombre apparaît sous le fruit\n\n"
        "**Intention :** diagnostic\n"
        "**Organes concernés :** fruit\n"
        "**On parle aussi de :** cul noir ; nécrose apicale ; manque de calcium\n\n"
        "**Attention :** un fruit atteint ne guérit jamais.\n\n"
        "Une zone brune puis noire, sèche et creusée sous le fruit vient d'une "
        "alimentation en eau irrégulière pendant la croissance, même lorsque le "
        "sol contient assez de calcium.\n\n"
        "## Sources et licence\n\n"
        "- U.S. Department of Agriculture, National Agricultural Library, contenu "
        "gouvernemental américain généralement dans le domaine public.\n"
        "- Texte de cette fiche rédigé de zéro, sans reproduction textuelle.\n"
    )


def _ingerer_v2(db, tmp_path, niveau: str = "a-valider"):
    fiche = tmp_path / "tomate-problemes.md"
    fiche.write_text(_fiche_v2(niveau), encoding="utf-8")
    rapport = ing.Rapport()
    ing.ingerer_fichier(db, fiche, tmp_path, rapport)
    db.commit()
    return rapport


def test_us098_format_entete_tolere_les_guillemets():
    """Une valeur entre guillemets est une convention d'écriture, pas un sens
    différent — la refuser rejetait la totalité d'un corpus par ailleurs sain."""
    entete, _ = ing.lire_entete('---\nfamille: "agronomie"\ntitre: \'Le cul noir\'\n---\n\n#\n')
    assert entete["famille"] == "agronomie"
    assert entete["titre"] == "Le cul noir"


def test_us098_format_une_apostrophe_interne_traverse_intacte():
    """Edge case du dépouillement : on retire une PAIRE de guillemets, jamais
    une apostrophe française isolée."""
    entete, _ = ing.lire_entete("---\ntitre: L'été au potager\n---\n\n#\n")
    assert entete["titre"] == "L'été au potager"


def test_us098_format_un_bloc_en_liste_ne_produit_aucune_cle_parasite():
    """`sources:` et `index_terms:` sont des listes destinées au relecteur. Le
    schéma n'a qu'un champ `source` SCALAIRE — celui affiché au jardinier. Lues
    ligne à ligne, ces listes faisaient échouer la fiche entière."""
    entete, _ = ing.lire_entete(
        "---\n"
        'source: "Rédaction interne"\n'
        "index_terms:\n  - \"cul noir\"\n  - \"nécrose apicale\"\n"
        "sources:\n  - organisme: \"USDA\"\n    licence: \"Domaine public\"\n"
        "---\n\n#\n"
    )
    assert entete["source"] == "Rédaction interne"
    assert "organisme" not in entete and "licence" not in entete
    assert entete["index_terms"] == "" and entete["sources"] == ""


def test_us098_format_le_h1_de_tete_ne_produit_pas_de_fragment(base, tmp_path):
    """Le `# H1` recopie `titre:`. Indexé, il produisait un fragment de
    préambule qui sortait en TÊTE sur le seul nom de la culture, à 1.000 de
    confiance, sans rien répondre."""
    _ingerer_v2(base, tmp_path)
    fragments = base.query(KnowledgeChunk).all()
    assert all(f.intitule is not None for f in fragments), \
        "un fragment de préambule subsiste — le H1 de tête a été indexé"


def test_us098_format_la_section_de_licence_n_est_pas_indexee(base, tmp_path):
    """« Sources et licence » est identique d'une fiche à l'autre et ne répond
    à aucune question de jardinier. Indexée, elle remontait à 0.919 de
    confiance sur toute question portant les mots « source » ou « licence »."""
    _ingerer_v2(base, tmp_path)
    intitules = [f.intitule for f in base.query(KnowledgeChunk).all()]
    assert intitules == ["Une zone sombre apparaît sous le fruit"]


def test_us098_format_les_alias_indexent_sans_jamais_s_afficher(base, tmp_path):
    """LE test du format : « On parle aussi de » doit peser à l'index et rester
    invisible.

    La recherche est LEXICALE — un lemme absent de l'index est un rapprochement
    impossible, quelle que soit la qualité du texte. Mais ces alias vivent dans
    le corps de la section : sans extraction, le message Telegram s'ouvrait sur
    `**Intention :** diagnostic / **Organes concernés :** fruit / **On parle
    aussi de :** cul noir ; …` avant d'en venir à la réponse.
    """
    _ingerer_v2(base, tmp_path)
    ctx = TenantContext(user_id=1, potager_id=1, role="owner")

    # Retrouvé par un alias que le texte de la section ne contient pas.
    contexte = connaissance.rechercher(base, ctx, "mes tomates ont le cul noir")
    assert contexte.passages, "l'alias « cul noir » n'a pas été indexé"
    assert contexte.passages[0].intitule == "Une zone sombre apparaît sous le fruit"

    servi = connaissance.restituer(contexte)
    for interdit in ("On parle aussi de", "Organes concernés", "Intention :",
                     "nécrose apicale", "index_terms"):
        assert interdit not in servi, f"{interdit!r} a fui vers le jardinier"
    assert "alimentation en eau irrégulière" in servi


def test_us098_format_une_cle_hors_vocabulaire_reste_du_contenu(base, tmp_path):
    """On ne retire que ce qu'on sait nommer : `**Attention :**` est de la
    rédaction, pas de la métadonnée, et doit rester dans le texte servi."""
    _ingerer_v2(base, tmp_path)
    fragment = base.query(KnowledgeChunk).one()
    assert "**Attention :** un fruit atteint ne guérit jamais." in fragment.contenu


def test_us098_format_intention_est_retiree_du_texte_sans_etre_indexee():
    """`intention` repère la rédaction (« diagnostic », « comprendre la
    cause ») : personne ne tape ces mots, les indexer n'ajoute que du bruit.
    Elle quitte donc le contenu SANS rejoindre l'index."""
    propre, termes = ing.extraire_indexation(
        "**Intention :** diagnostic\n"
        "**Organes concernés :** fruit\n"
        "**On parle aussi de :** cul noir ; nécrose apicale\n\n"
        "Le texte de la réponse.\n"
    )
    assert propre == "Le texte de la réponse."
    assert "diagnostic" not in termes
    assert "cul noir" in termes and "fruit" in termes


def test_us098_format_index_terms_du_document_n_est_pas_indexe(base, tmp_path):
    """Décision MESURÉE, pas de principe : `index_terms` au niveau du document
    pèse identiquement sur TOUTES les sections de la fiche, donc il dilue
    exactement ce que les alias de section discriminent — 17/19 en tête sans
    lui, 15/19 avec, sur 19 questions réelles du corpus CA11 et 24 fiches.

    Il garde toute sa valeur d'index de relecture DANS le fichier, qui reste la
    source. Le test mord sur « chlorose ferrique », terme présent au niveau du
    document et dans aucune section.
    """
    _ingerer_v2(base, tmp_path)
    fragment = base.query(KnowledgeChunk).one()
    for lexeme in connaissance.lexemes("chlorose ferrique"):
        assert lexeme not in (fragment.recherche_fts or ""), \
            "un terme d'index de document est remonté dans le vecteur de recherche"

    ctx = TenantContext(user_id=1, potager_id=1, role="owner")
    assert not connaissance.rechercher(base, ctx, "chlorose ferrique").passages


def test_us098_format_niveau_a_valider_se_comporte_comme_indicatif(base, tmp_path):
    """`niveau_confiance` pilote un comportement binaire : servir mot pour mot,
    ou descendre en contexte vers l'étage de raisonnement. Une fiche non encore
    relue phrase par phrase se comporte comme `indicatif` — l'intention
    éditoriale reste portée par le fichier, qui est la source."""
    _ingerer_v2(base, tmp_path, niveau="a-valider")
    document = base.query(KnowledgeDocument).one()
    assert document.niveau_confiance == connaissance.NIVEAU_INDICATIF

    ctx = TenantContext(user_id=1, potager_id=1, role="owner")
    contexte = connaissance.rechercher(base, ctx, "mes tomates ont le cul noir")
    assert contexte.passages and not contexte.suffisant, \
        "une fiche non relue ne doit jamais être servie mot pour mot"


def test_us098_format_une_fiche_v2_s_ingere_sans_avertissement(base, tmp_path):
    """Bout en bout : le format réel du corpus passe `--strict` sans retouche."""
    rapport = _ingerer_v2(base, tmp_path)
    assert rapport.erreurs == []
    assert rapport.avertissements == []
    assert rapport.fragments == 1


def test_us098_suppression_d_un_document_invalide_ses_fragments(base, tmp_path):
    """CA11 (variante) — un document retiré du dépôt emporte ses fragments et
    les réponses qui en dérivaient."""
    fiche = tmp_path / "tomate.md"
    fiche.write_text(_fiche_exemple(), encoding="utf-8")
    ing.ingerer_fichier(base, fiche, tmp_path, ing.Rapport())
    reference = ing.reference_document(fiche, tmp_path)

    supprimes, retirees = connaissance.supprimer_document(base, reference)
    base.commit()
    assert supprimes == 2 and len(retirees) == 2
    assert base.query(KnowledgeChunk).count() == 0


# ═════════════════════════════════════════════════════════════════════════════
# CA13 — qualité mesurée
# ═════════════════════════════════════════════════════════════════════════════
def _questions_corpus() -> list[tuple[str, str]]:
    prefixe = CORPUS_DOCUMENTS.relative_to(RACINE).as_posix()
    with CORPUS_QUESTIONS.open(encoding="utf-8", newline="") as fichier:
        return [
            (ligne["question"].strip(), f"{prefixe}/{ligne['fragment_attendu'].strip()}")
            for ligne in csv.DictReader(fichier)
            if ligne.get("question") and ligne.get("fragment_attendu")
        ]


def test_us098_ca13_le_corpus_compte_au_moins_trente_questions():
    """CA13 — « au moins 30 questions de savoir avec le fragment attendu »."""
    questions = _questions_corpus()
    assert len(questions) >= 30
    assert len({q for q, _ in questions}) == len(questions), "questions dupliquées"


def test_us098_ca13_le_bon_fragment_sort_dans_les_trois_premiers(corpus_ingere):
    """CA13 — cible : le bon fragment dans le top 3.

    ⚠️ Cette exécution mesure le REPLI SQLite, pas la recherche plein texte
    française de PostgreSQL. Elle protège la mécanique contre les régressions ;
    la mesure qui conditionne l'ACTIVATION en production est celle de
    `python tools/mesurer_corpus_savoir.py` contre la base de production, et le
    seuil de confiance devra y être réétalonné (`RAG_SEUIL_CONFIANCE`).
    """
    db, _ = corpus_ingere
    questions = _questions_corpus()
    dans_cible = 0
    manques = []
    for question, attendu in questions:
        contexte = connaissance.rechercher(db, CTX_A, question, limite=3)
        if attendu in contexte.references:
            dans_cible += 1
        else:
            manques.append(question)
    taux = dans_cible / len(questions)
    assert taux >= 0.80, f"top-3 = {taux:.0%} ; hors cible : {manques}"


def test_us098_ca13_tous_les_fragments_attendus_existent(corpus_ingere):
    """CA13 — un corpus qui viserait des fragments inexistants mesurerait le
    vide. Les 42 références attendues doivent toutes être en base."""
    db, _ = corpus_ingere
    presentes = {reference for (reference,) in db.query(KnowledgeChunk.reference).all()}
    attendus = {attendu for _, attendu in _questions_corpus()}
    assert attendus <= presentes, f"références inexistantes : {sorted(attendus - presentes)}"


# ═════════════════════════════════════════════════════════════════════════════
# CA14 — journalisation de la recherche
# ═════════════════════════════════════════════════════════════════════════════
def test_us098_ca14_routage_logs_porte_le_score_et_l_issue(base, monkeypatch):
    """CA14 — chaque recherche laisse son score et son issue dans `routage_logs`."""
    doc = _document(base, "agro/culnoir.md", "Le cul noir de la tomate")
    connaissance.remplacer_fragments(base, doc, [
        _fragment("agro/culnoir.md#00",
                  "Le cul noir est une tache noire sous le fruit, due à un manque de calcium."),
    ])
    base.commit()
    monkeypatch.setattr(routeur, "SessionLocal", lambda: base)
    monkeypatch.setattr(cq, "SessionLocal", lambda: base)
    monkeypatch.setattr(rc, "SessionLocal", lambda: base)

    with patch("llm.passerelle.appeler_chat", side_effect=AssertionError("zéro jeton attendu")):
        reponse = routeur.repondre_avec_cascade(CTX_A, "pourquoi mes tomates ont le cul noir ?")

    assert reponse.etage_resolveur == routeur.ETAGE_SAVOIR
    ligne = base.query(RoutageLog).order_by(RoutageLog.id.desc()).first()
    assert ligne.issue_savoir == connaissance.ISSUE_SERVI
    assert ligne.score_savoir is not None and ligne.score_savoir > 0
    assert ligne.tokens_consommes == 0


def test_us098_ca14_les_questions_sans_reponse_sont_listables(base):
    """CA14 — « identifier les questions qui ne trouvent rien : ce sont elles
    qui définissent le contenu à écrire ensuite »."""
    base.add_all([
        RoutageLog(potager_id=1, question_normalisee="comment tailler un pommier",
                   nature=routeur.NATURE_QUESTION_SAVOIR, origine_classification="regle",
                   etage_resolveur=routeur.ETAGE_RAISONNEMENT, cascade_remontee=False,
                   score_savoir=0.0, issue_savoir=connaissance.ISSUE_VIDE),
        RoutageLog(potager_id=1, question_normalisee="comment tailler un pommier",
                   nature=routeur.NATURE_QUESTION_SAVOIR, origine_classification="regle",
                   etage_resolveur=routeur.ETAGE_RAISONNEMENT, cascade_remontee=False,
                   score_savoir=0.0, issue_savoir=connaissance.ISSUE_VIDE),
        RoutageLog(potager_id=1, question_normalisee="le cul noir de la tomate",
                   nature=routeur.NATURE_QUESTION_SAVOIR, origine_classification="regle",
                   etage_resolveur=routeur.ETAGE_SAVOIR, cascade_remontee=False,
                   score_savoir=0.9, issue_savoir=connaissance.ISSUE_SERVI),
    ])
    base.commit()

    resume = svc_metriques.resume_savoir(base)
    assert resume["total_recherches"] == 3
    assert resume["par_issue"][connaissance.ISSUE_VIDE]["nb"] == 2
    assert resume["par_issue"][connaissance.ISSUE_SERVI]["nb"] == 1

    lacunes = svc_metriques.questions_sans_savoir(base)
    assert lacunes[0] == {"question_normalisee": "comment tailler un pommier",
                          "issue": connaissance.ISSUE_VIDE, "nb": 2}


# ═════════════════════════════════════════════════════════════════════════════
# Cascade complète — les scénarios Gherkin de l'US
# ═════════════════════════════════════════════════════════════════════════════
def test_us098_gherkin_question_de_savoir_repondue_sans_ia(base, monkeypatch):
    """Gherkin 1 — « les passages pertinents sont retrouvés … et aucun appel au
    modèle n'a lieu »."""
    doc = _document(base, "agro/culnoir.md", "Le cul noir de la tomate")
    connaissance.remplacer_fragments(base, doc, [
        _fragment("agro/culnoir.md#00",
                  "Le cul noir est une tache noire sous le fruit, due à un manque de calcium."),
    ])
    base.commit()
    monkeypatch.setattr(routeur, "SessionLocal", lambda: base)
    monkeypatch.setattr(cq, "SessionLocal", lambda: base)
    monkeypatch.setattr(rc, "SessionLocal", lambda: base)

    with patch("llm.passerelle.appeler_chat", side_effect=AssertionError("zéro jeton attendu")):
        reponse = routeur.repondre_avec_cascade(CTX_A, "pourquoi mes tomates ont le cul noir ?")
    assert "manque de calcium" in reponse.texte


def test_us098_gherkin_confiance_faible_transmise_a_l_etage_superieur(base, monkeypatch):
    """Gherkin 3 — « le contexte est transmis à l'étage de raisonnement, et la
    question n'est pas déclarée sans réponse »."""
    doc = _document(base, "agro/limaces.md", "Les limaces",
                    niveau=connaissance.NIVEAU_INDICATIF)
    connaissance.remplacer_fragments(base, doc, [
        _fragment("agro/limaces.md#00", "Les limaces mangent la nuit et laissent du mucus."),
    ])
    base.commit()
    monkeypatch.setattr(routeur, "SessionLocal", lambda: base)
    monkeypatch.setattr(cq, "SessionLocal", lambda: base)
    monkeypatch.setattr(rc, "SessionLocal", lambda: base)

    with patch("llm.passerelle.appeler_chat",
               return_value=_reponse_modele("Ce sont probablement des limaces.")) as modele:
        reponse = routeur.repondre_avec_cascade(
            CTX_A, "pourquoi mes salades sont mangees la nuit ?")

    assert reponse.etage_resolveur == routeur.ETAGE_RAISONNEMENT
    assert reponse.texte, "la question n'est jamais déclarée sans réponse"
    message = modele.call_args.kwargs["message_utilisateur"]
    assert "Passages de la base de connaissance" in message and "mucus" in message
    ligne = base.query(RoutageLog).order_by(RoutageLog.id.desc()).first()
    assert ligne.issue_savoir == connaissance.ISSUE_TRANSMIS
    assert ligne.cascade_remontee is True


def test_us098_base_vide_la_cascade_se_comporte_comme_avant(base, monkeypatch):
    """Non-régression — socle vide (état à la livraison) : la cascade retombe
    sur le raisonnement, sans erreur et sans remontée revendiquée."""
    monkeypatch.setattr(routeur, "SessionLocal", lambda: base)
    monkeypatch.setattr(cq, "SessionLocal", lambda: base)
    monkeypatch.setattr(rc, "SessionLocal", lambda: base)

    with patch("llm.passerelle.appeler_chat",
               return_value=_reponse_modele("Il faut tailler en hiver.")):
        reponse = routeur.repondre_avec_cascade(CTX_A, "pourquoi mes pommiers ne donnent rien ?")

    assert reponse.etage_resolveur == routeur.ETAGE_RAISONNEMENT
    ligne = base.query(RoutageLog).order_by(RoutageLog.id.desc()).first()
    assert ligne.issue_savoir == connaissance.ISSUE_VIDE
    assert ligne.cascade_remontee is False


def test_us098_socle_indisponible_ne_coute_jamais_une_reponse(base, monkeypatch):
    """Cas d'erreur — une panne de la recherche (migration non jouée, base
    inaccessible) ne doit jamais empêcher de répondre."""
    monkeypatch.setattr(routeur, "SessionLocal", lambda: base)
    monkeypatch.setattr(cq, "SessionLocal", lambda: base)
    monkeypatch.setattr(rc, "SessionLocal", lambda: base)
    monkeypatch.setattr(connaissance, "rechercher",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("table absente")))

    with patch("llm.passerelle.appeler_chat", return_value=_reponse_modele("Réponse de repli.")):
        reponse = routeur.repondre_avec_cascade(CTX_A, "pourquoi mes courgettes jaunissent ?")
    assert reponse.texte == "Réponse de repli."


def test_us098_rag_inactif_court_circuite_l_etage(base, monkeypatch):
    """L'interrupteur `RAG_ACTIF` coupe l'étage sans redéploiement."""
    monkeypatch.setattr(routeur, "RAG_ACTIF", False)
    monkeypatch.setattr(connaissance, "rechercher",
                        lambda *a, **k: pytest.fail("l'étage devait être court-circuité"))
    assert routeur._consulter_savoir(CTX_A, "le cul noir de la tomate") is None


# ═════════════════════════════════════════════════════════════════════════════
# Purge potager (US-084) — la connaissance privée part avec le potager
# ═════════════════════════════════════════════════════════════════════════════
def test_us098_purge_potager_emporte_la_connaissance_privee(base):
    """La connaissance PRIVÉE d'un potager purgé disparaît ; le savoir global,
    qui n'appartient à personne, reste."""
    prive = _document(base, "prive/a.md", "Mémoire du jardin A", potager_id=1,
                      famille=connaissance.FAMILLE_MEMOIRE_POTAGER)
    connaissance.remplacer_fragments(base, prive, [_fragment("prive/a.md#00", "Note privée.")])
    global_ = _document(base, "global/tomate.md", "La tomate")
    connaissance.remplacer_fragments(base, global_, [_fragment("global/tomate.md#00", "Note globale.")])
    base.commit()

    potager = base.get(Potager, 1)
    potager.etat = "supprime"
    potager.supprime_le = datetime.utcnow() - timedelta(days=40)
    base.commit()

    resultat = svc_potagers.purger_potager(base, 1)
    assert resultat["volumes"]["knowledge_chunks"] == 1
    restants = {c.reference for c in base.query(KnowledgeChunk).all()}
    assert restants == {"global/tomate.md#00"}


# ═════════════════════════════════════════════════════════════════════════════
# Fixture de contenu
# ═════════════════════════════════════════════════════════════════════════════
def _fiche_exemple(corrigee: bool = False) -> str:
    """Une fiche à deux sections. `corrigee=True` renomme la seconde section :
    son fragment change donc de référence, ce qui est exactement le cas que le
    CA11 doit traiter."""
    seconde = "Corriger le cul noir" if corrigee else "Éviter le cul noir"
    detail = ("Un arrosage régulier et un paillage lissent l'humidité du sol, "
              "et les fruits suivants reviennent sains en une à deux semaines."
              if corrigee else
              "Un paillage au pied limite l'évaporation et régularise l'humidité "
              "du sol entre deux arrosages successifs.")
    return (
        "---\n"
        "titre: Le cul noir de la tomate\n"
        "famille: agronomie\n"
        "source: Test\n"
        "niveau_confiance: verifie\n"
        "culture: tomate\n"
        "type: maladie\n"
        "---\n\n"
        "## Ce qu'est le cul noir\n\n"
        "Le cul noir est une tache brune puis noire sous le fruit de la tomate, "
        "causée par un manque de calcium au moment où le fruit grossit.\n\n"
        f"## {seconde}\n\n"
        f"{detail}\n"
    )

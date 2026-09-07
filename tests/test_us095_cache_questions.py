"""
tests/test_us095_cache_questions.py
[US-095] Servir les questions récurrentes depuis un cache qui ne ment jamais

Couverture des critères d'acceptance CA1 → CA13.

Deux invariants structurent tout ce fichier, et expliquent la forme des tests :

- **Aucun appel modèle n'est toléré sur le chemin du cache.** La passerelle
  (`llm.passerelle.appeler_chat`) est remplacée par un double qui fait échouer
  le test s'il est appelé, sauf dans les rares tests qui simulent
  explicitement un étage de raisonnement. C'est la seule façon de *démontrer*
  le « zéro jeton » plutôt que de l'affirmer.

- **La justesse se prouve par la séquence, pas par l'état.** Le test central
  (CA6) rejoue le scénario réel de bout en bout : question, réponse servie,
  évènement contradictoire enregistré par la couche services, même question
  reposée. C'est le seul test qui prouve que le cache ne survit pas à ce qui
  le contredit.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services import cache_questions as cq
from app.services import evenements as svc_evenements
from app.services import metriques_routage as svc_metriques
from app.services import potagers as svc_potagers
from app.services import reponses_chiffrees as rc
from app.services.context import TenantContext
from database.models import CultureConfig, Evenement, Parcelle, QuestionCache, RoutageLog
from llm import passerelle, routeur
from llm.passerelle import LLMIndisponibleError, ReponseLLM
from utils.dependances_donnee import (
    NATURE_JOURNAL,
    NATURE_RECOLTE,
    NATURE_STOCK,
    NATURES_TOUTES,
    natures_impactees,
)

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
CTX_VOISIN = TenantContext(user_id=2, potager_id=2, role="owner")

ANNEE = datetime.now().year

RACINE = Path(__file__).resolve().parents[1]


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture(autouse=True)
def _cache_classification_propre():
    """Le cache de CLASSIFICATION du routeur est en mémoire du processus : sans
    ce nettoyage, une décision d'un test fuiterait dans le suivant."""
    routeur.vider_cache()
    yield
    routeur.vider_cache()


@pytest.fixture
def potager(test_db):
    """Un potager minimal mais réaliste : une culture reproductrice pesée
    (tomate), une culture végétative (carotte), une parcelle nommée et une
    variété — ces deux derniers servent de témoins de fuite au CA8."""
    test_db.add_all([
        CultureConfig(nom="tomate", type_organe_recolte="reproducteur", potager_id=None),
        CultureConfig(nom="carotte", type_organe_recolte="végétatif", potager_id=None),
    ])
    nord = Parcelle(nom="planche-nord", nom_normalise="planchenord", potager_id=1,
                    actif=True, est_pepiniere=False)
    test_db.add(nord)
    test_db.commit()

    test_db.add_all([
        Evenement(date=datetime(ANNEE, 5, 1), type_action="plantation", culture="tomate",
                  variete="Marmande", quantite=6, unite="plants", potager_id=1,
                  parcelle_id=nord.id),
        Evenement(date=datetime(ANNEE, 7, 3), type_action="recolte", culture="tomate",
                  quantite=2, unite="kg", potager_id=1),
        Evenement(date=datetime(ANNEE, 5, 10), type_action="plantation", culture="carotte",
                  quantite=40, unite="plants", potager_id=1, parcelle_id=nord.id),
    ])
    test_db.commit()
    return test_db


@pytest.fixture
def cascade(potager, monkeypatch):
    """Fait pointer les trois `SessionLocal` du chemin de cascade vers la
    session de test : celui du cache (étage 0bis), celui des gabarits (étage
    des données) et celui du routeur (journal + mémorisation)."""
    monkeypatch.setattr(cq, "SessionLocal", lambda: potager)
    monkeypatch.setattr(rc, "SessionLocal", lambda: potager)
    monkeypatch.setattr(routeur, "SessionLocal", lambda: potager)
    return potager


@pytest.fixture
def sans_appel_modele():
    """Arme le double qui fait échouer le test si un modèle est appelé."""
    with patch("llm.passerelle.appeler_chat", side_effect=AssertionError(
        "Un appel au modèle a eu lieu sur un chemin qui doit coûter zéro jeton"
    )):
        yield


def _reponse_modele(texte: str) -> ReponseLLM:
    return ReponseLLM(
        texte=texte, modele="mock", appel_type=passerelle.TYPE_QUESTION,
        tokens_in=10, tokens_out=20,
    )


def _memoriser_stock_tomate(db) -> QuestionCache:
    """Mémorise l'entrée de référence utilisée par la plupart des tests :
    « mon stock de tomates ? », famille `stock_courant`."""
    chiffree = rc.repondre_chiffre(CTX, "mon stock de tomates ?", db=db)
    assert chiffree is not None and chiffree.present
    entree = cq.memoriser_template_sql(db, CTX, "mon stock de tomates ?", chiffree.aiguillage)
    assert entree is not None
    return entree


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — Structure de la table
# ═════════════════════════════════════════════════════════════════════════════
def test_us095_ca1_la_table_porte_les_colonnes_annoncees():
    """CA1 — les colonnes nommées par l'US existent, sous ces noms-là."""
    colonnes = set(QuestionCache.__table__.columns.keys())
    assert {
        "potager_id", "motif_normalise", "type_reponse", "template",
        "reponse_figee", "source_etage", "valide_jusqu_au", "cree_le",
    } <= colonnes


def test_us095_ca1_potager_id_nullable_pour_le_savoir_partageable():
    """CA1 — `potager_id` nul = savoir général partageable entre tous les
    potagers. Une colonne NOT NULL rendrait ce cas impossible à exprimer."""
    assert QuestionCache.__table__.columns["potager_id"].nullable is True


def test_us095_ca1_deux_types_de_reponse_et_pas_un_de_plus(potager):
    """CA1 — `template_sql` et `figee`, jamais confondus : une entrée
    paramétrée ne porte pas de texte, une entrée figée ne porte pas
    d'aiguillage."""
    parametree = _memoriser_stock_tomate(potager)
    assert parametree.type_reponse == cq.TYPE_TEMPLATE_SQL
    assert parametree.reponse_figee is None
    assert parametree.template is not None

    figee = cq.memoriser_figee(
        potager, CTX, "à quelle profondeur semer les carottes ?",
        "Sème les carottes à environ 1 cm de profondeur, en ligne.",
    )
    assert figee.type_reponse == cq.TYPE_FIGEE
    assert figee.template is None
    assert figee.reponse_figee


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — Le motif est la normalisation du routeur, jamais une variante
# ═════════════════════════════════════════════════════════════════════════════
def test_us095_ca2_motif_produit_par_la_fonction_du_routeur(potager):
    """CA2 — le motif stocké est exactement `routeur.normaliser_question()`."""
    question = "Mon Stock de TOMATES ?!"
    chiffree = rc.repondre_chiffre(CTX, question, db=potager)
    entree = cq.memoriser_template_sql(potager, CTX, question, chiffree.aiguillage)
    assert entree.motif_normalise == routeur.normaliser_question(question)
    assert entree.motif_normalise == "mon stock de tomates"


def test_us095_ca2_variantes_de_ponctuation_partagent_le_meme_motif(potager, sans_appel_modele):
    """CA2 — dictée vocale et frappe au pouce produisent la même question à la
    ponctuation près : elles doivent retomber sur la même entrée, sinon le
    cache ne servirait jamais deux fois."""
    _memoriser_stock_tomate(potager)
    servie = cq.servir(CTX, "Mon stock de tomates ?!", db=potager)
    assert servie is not None
    assert servie.type_reponse == cq.TYPE_TEMPLATE_SQL


def test_us095_ca2_trois_formulations_une_seule_entree(potager, sans_appel_modele):
    """CA2 — LE test du constat de production du 29/08/2026 : trois façons de
    poser la même question avaient créé trois entrées en 29 secondes et servi
    zéro réponse. Elles doivent désormais partager une entrée unique, et les
    deux reformulations suivantes doivent être servies depuis le cache.

    Le potager de test cultive du concombre pour reproduire fidèlement le cas.
    """
    potager.add_all([
        CultureConfig(nom="concombre", type_organe_recolte="reproducteur", potager_id=None),
        Evenement(date=datetime(ANNEE, 5, 5), type_action="plantation", culture="concombre",
                  quantite=3, unite="plants", potager_id=1),
        Evenement(date=datetime(ANNEE, 7, 10), type_action="recolte", culture="concombre",
                  quantite=1.5, unite="kg", potager_id=1),
    ])
    potager.commit()

    formulations = [
        "quel est ma production de concombre",
        "ma production de concombre",
        "production de concombre",
    ]
    servies = 0
    for question in formulations:
        depuis_cache = cq.servir(CTX, question, db=potager)
        if depuis_cache is not None:
            servies += 1
            continue
        chiffree = rc.repondre_chiffre(CTX, question, db=potager)
        assert chiffree is not None and chiffree.present
        cq.memoriser_template_sql(potager, CTX, question, chiffree.aiguillage)

    assert potager.query(QuestionCache).count() == 1, "une seule entrée pour une seule question"
    assert servies == 2, "les deux reformulations sont servies depuis le cache"
    entree = potager.query(QuestionCache).one()
    assert entree.cle_aiguillage == "rendement_saison|concombre|"
    # La formulation qui a créé l'entrée reste lisible, comme trace d'audit.
    assert entree.motif_normalise == "quel est ma production de concombre"


def test_us095_ca2_la_cle_est_l_aiguillage_pas_la_phrase(potager):
    """CA2 — l'identité d'une question est son aiguillage. Deux cultures
    différentes restent deux entrées ; deux phrases pour une même culture n'en
    font qu'une."""
    assert rc.cle_aiguillage(
        {"famille": "rendement_saison", "culture": "Concombre", "parcelle": None}
    ) == "rendement_saison|concombre|"
    assert rc.cle_aiguillage(
        {"famille": "rendement_saison", "culture": "tomate", "parcelle": None}
    ) != rc.cle_aiguillage(
        {"famille": "rendement_saison", "culture": "concombre", "parcelle": None}
    )


def test_us095_ca2_periode_differente_meme_entree_reponses_differentes(potager, sans_appel_modele):
    """CA2/CA3 — ce qui rend la clé par aiguillage SÛRE : la période n'y entre
    pas parce qu'elle est redérivée de la phrase vivante. Deux questions de
    même aiguillage mais de mois différents partagent l'entrée et reçoivent
    chacune leur réponse exacte."""
    potager.add_all([
        Evenement(date=datetime(ANNEE, 7, 5), type_action="recolte", culture="tomate",
                  quantite=4, unite="kg", potager_id=1),
        Evenement(date=datetime(ANNEE, 8, 5), type_action="recolte", culture="tomate",
                  quantite=9, unite="kg", potager_id=1),
    ])
    potager.commit()

    juillet = "combien de tomates ai-je récolté en juillet ?"
    aout = "combien de tomates ai-je récolté en août ?"
    chiffree = rc.repondre_chiffre(CTX, juillet, db=potager)
    cq.memoriser_template_sql(potager, CTX, juillet, chiffree.aiguillage)

    servie_juillet = cq.servir(CTX, juillet, db=potager)
    servie_aout = cq.servir(CTX, aout, db=potager)

    assert potager.query(QuestionCache).count() == 1
    assert servie_juillet is not None and servie_aout is not None
    # Le libellé de période vient de la question NORMALISÉE (« aout »), pas de
    # sa forme accentuée : c'est le comportement du gabarit US-096, inchangé.
    assert "juillet" in servie_juillet.texte and "6 kg" in servie_juillet.texte
    assert "aout" in servie_aout.texte and "9 kg" in servie_aout.texte


def test_us095_ca2_action_differente_meme_entree_reponses_differentes(potager, sans_appel_modele):
    """CA2/CA3 — même démonstration pour le type d'action, lui aussi redérivé
    de la phrase : « quand ai-je planté » et « quand ai-je récolté » partagent
    l'aiguillage `derniere_occurrence|tomate|` sans se confondre."""
    question_plantation = "quand ai-je planté les tomates ?"
    chiffree = rc.repondre_chiffre(CTX, question_plantation, db=potager)
    cq.memoriser_template_sql(potager, CTX, question_plantation, chiffree.aiguillage)

    servie_plantation = cq.servir(CTX, question_plantation, db=potager)
    servie_recolte = cq.servir(CTX, "quand ai-je récolté les tomates ?", db=potager)

    assert potager.query(QuestionCache).count() == 1
    assert "plantation" in servie_plantation.texte.lower()
    assert "récolte" in servie_recolte.texte.lower()


def test_us095_ca2_l_espace_des_cles_est_borne(potager, sans_appel_modele):
    """CA2/CA11 — la propriété qui règle le risque d'explosion : quel que soit
    le nombre de formulations posées, le nombre de lignes ne dépasse pas le
    nombre d'aiguillages distincts. Ici deux (stock tomate, stock carotte),
    pour huit formulations."""
    formulations = [
        "mon stock de tomates", "mon stock de tomates ?", "stock de tomates",
        "il me reste combien de tomates", "il me reste combien de tomates ?",
        "mon stock de carottes", "stock de carottes", "il me reste combien de carottes",
    ]
    for question in formulations:
        if cq.servir(CTX, question, db=potager) is not None:
            continue
        chiffree = rc.repondre_chiffre(CTX, question, db=potager)
        if chiffree is not None and chiffree.present:
            cq.memoriser_template_sql(potager, CTX, question, chiffree.aiguillage)

    cles = {e.cle_aiguillage for e in potager.query(QuestionCache).all()}
    assert cles == {"stock_courant|tomate|", "stock_courant|carotte|"}
    assert potager.query(QuestionCache).count() == 2


def test_us095_ca2_une_seule_implementation_de_la_normalisation():
    """CA2 — « la même normalisation que le routeur, jamais une variante » :
    le module de cache n'en redéfinit pas une, il importe celle du routeur."""
    assert cq.normaliser_question is routeur.normaliser_question


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — Une réponse paramétrée ne stocke que la structure et l'aiguillage
# ═════════════════════════════════════════════════════════════════════════════
def test_us095_ca3_entree_parametree_ne_contient_aucun_chiffre_de_reponse(potager):
    """CA3 — le chiffre servi au jardinier n'apparaît nulle part dans l'entrée.
    C'est ce qui rend la classe entière des réponses périmées impossible : il
    n'y a rien de périssable à stocker."""
    chiffree = rc.repondre_chiffre(CTX, "mon stock de tomates ?", db=potager)
    entree = cq.memoriser_template_sql(potager, CTX, "mon stock de tomates ?", chiffree.aiguillage)

    aiguillage = json.loads(entree.template)
    assert aiguillage["famille"] == "stock_courant"
    assert set(aiguillage) == {"famille", "culture", "parcelle", "dependances"}
    # Aucune valeur numérique, ni dans l'aiguillage ni ailleurs sur la ligne.
    assert not any(caractere.isdigit() for caractere in entree.template)
    assert entree.reponse_figee is None


def test_us095_ca3_les_valeurs_sont_recalculees_a_chaque_service(potager, sans_appel_modele):
    """CA3 — le cœur du dispositif, isolé de l'invalidation : une écriture qui
    contourne complètement la couche services (donc n'invalide RIEN) doit
    quand même se refléter dans la réponse servie, parce que celle-ci est
    recalculée et non mémorisée."""
    _memoriser_stock_tomate(potager)
    avant = cq.servir(CTX, "mon stock de tomates ?", db=potager).texte

    # Écriture directe en base : aucun service, aucune invalidation.
    potager.add(Evenement(date=datetime(ANNEE, 7, 20), type_action="plantation",
                          culture="tomate", quantite=10, unite="plants", potager_id=1))
    potager.commit()

    apres = cq.servir(CTX, "mon stock de tomates ?", db=potager).texte
    assert potager.query(QuestionCache).count() == 1, "l'entrée est bien toujours là"
    assert apres != avant, "la réponse servie doit refléter la base actuelle"
    assert "16" in apres


def test_us095_ca3_periode_redérivee_et_non_memorisee(potager):
    """CA3 — la période n'est PAS mémorisée : une fenêtre résolue en décembre
    (« cette saison ») servirait encore les chiffres de l'an passé en janvier.
    Elle est redérivée de la phrase à chaque service."""
    chiffree = rc.repondre_chiffre(CTX, "combien de tomates ai-je récolté cette saison ?", db=potager)
    assert chiffree is not None
    assert "periode" not in chiffree.aiguillage
    assert "annee" not in json.dumps(chiffree.aiguillage)


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — Chaque entrée porte ses dépendances
# ═════════════════════════════════════════════════════════════════════════════
def test_us095_ca4_entree_porte_culture_et_natures(potager):
    """CA4 — culture concernée et natures de donnée, sur la ligne elle-même."""
    entree = _memoriser_stock_tomate(potager)
    assert entree.culture == "tomate"
    for nature in (NATURE_STOCK, NATURE_RECOLTE):
        assert f"|{nature}|" in entree.natures


def test_us095_ca4_chaque_famille_du_catalogue_declare_ses_dependances():
    """CA4 — garde-fou : une famille ajoutée sans dépendances serait une
    famille dont les réponses survivraient à l'évènement qui les contredit.
    Le champ est obligatoire ; ce test vérifie qu'aucune n'est vide ni
    fantaisiste."""
    for famille in rc.FAMILLES:
        assert famille.dependances, f"famille '{famille.nom}' sans dépendance déclarée"
        assert set(famille.dependances) <= NATURES_TOUTES, famille.nom


def test_us095_ca4_toute_ecriture_impacte_au_moins_le_journal():
    """CA4 — même un arrosage périme « quand ai-je arrosé pour la dernière
    fois ? ». Aucune action ne peut donc n'impacter aucune nature."""
    for action in ("recolte", "arrosage", "semis", "observation", "geste-inconnu", None):
        assert NATURE_JOURNAL in natures_impactees(action)


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — Toute écriture invalide immédiatement les entrées dépendantes
# ═════════════════════════════════════════════════════════════════════════════
def test_us095_ca5_recolte_invalide_les_entrees_de_stock_de_la_culture(potager):
    """CA5 — enregistrer une récolte de tomates rend caduque toute réponse
    mémorisée portant sur le stock ou les récoltes de tomates."""
    _memoriser_stock_tomate(potager)
    assert potager.query(QuestionCache).count() == 1

    svc_evenements.creer_evenement_depuis_parse(
        potager, CTX,
        {"action": "recolte", "culture": "tomate", "quantite": 5, "unite": "kg"},
        "récolté 5 kg de tomates",
    )
    assert potager.query(QuestionCache).count() == 0


def test_us095_ca5_entree_sans_culture_invalidee_par_tout_evenement(potager):
    """CA5 — une réponse globale (stock de tout le potager) dérive de
    l'ensemble : n'importe quelle culture la périme."""
    chiffree = rc.repondre_chiffre(CTX, "quel est mon stock ?", db=potager)
    entree = cq.memoriser_template_sql(potager, CTX, "quel est mon stock ?", chiffree.aiguillage)
    assert entree.culture is None

    svc_evenements.creer_evenement_depuis_parse(
        potager, CTX,
        {"action": "recolte", "culture": "carotte", "quantite": 3, "unite": "plants"},
        "récolté 3 carottes",
    )
    assert potager.query(QuestionCache).count() == 0


def test_us095_ca5_une_autre_culture_ne_perime_pas_l_entree(potager):
    """CA5 — invalider large ne veut pas dire invalider tout : une récolte de
    carottes ne périme pas une réponse portant sur les tomates. Sans cette
    limite, le cache serait vidé à chaque saisie et ne servirait jamais."""
    _memoriser_stock_tomate(potager)
    svc_evenements.creer_evenement_depuis_parse(
        potager, CTX,
        {"action": "recolte", "culture": "carotte", "quantite": 3, "unite": "plants"},
        "récolté 3 carottes",
    )
    assert potager.query(QuestionCache).count() == 1


def test_us095_ca5_un_arrosage_perime_le_journal_mais_pas_le_stock(potager):
    """CA5 — la granularité par nature de donnée : un arrosage ne déplace aucun
    stock, il ne périme que « quand ai-je arrosé ? »."""
    _memoriser_stock_tomate(potager)
    chiffree = rc.repondre_chiffre(CTX, "quand ai-je planté les tomates ?", db=potager)
    cq.memoriser_template_sql(potager, CTX, "quand ai-je planté les tomates ?", chiffree.aiguillage)
    assert potager.query(QuestionCache).count() == 2

    svc_evenements.creer_evenement_depuis_parse(
        potager, CTX, {"action": "arrosage", "culture": "tomate"}, "arrosé les tomates",
    )
    restantes = potager.query(QuestionCache).all()
    assert [e.motif_normalise for e in restantes] == ["mon stock de tomates"]


def test_us095_ca5_invalidation_branchee_en_un_seul_endroit():
    """CA5 / note technique — l'invalidation vit dans la couche services
    d'écriture et nulle part ailleurs. Dupliquée dans le bot et dans l'API,
    elle divergerait au premier chemin d'écriture ajouté, et l'oubli ne se
    verrait pas : il se paierait en réponse fausse."""
    appelants = []
    for chemin in list(RACINE.glob("*.py")) + list((RACINE / "app").rglob("*.py")) \
            + list((RACINE / "llm").rglob("*.py")) + list((RACINE / "utils").rglob("*.py")):
        contenu = chemin.read_text(encoding="utf-8")
        if "invalider_pour_evenement(" in contenu:
            appelants.append(chemin.name)
    assert sorted(appelants) == ["cache_questions.py", "evenements.py"], appelants


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — Le test central : la séquence complète
# ═════════════════════════════════════════════════════════════════════════════
def test_us095_ca6_le_cache_ne_survit_pas_a_l_evenement_qui_le_contredit(cascade, sans_appel_modele):
    """CA6 — scénario Gherkin « Le cache ne survit pas à un événement qui le
    contredit », joué de bout en bout par la cascade réelle :

      1. le jardinier demande son stock de tomates → réponse servie, mémorisée
      2. il enregistre « récolté 5 kg de tomates » par la couche services
      3. il repose exactement la même question

    La seconde réponse doit refléter le nouvel état, et ne jamais reprendre la
    valeur précédente. Aucun appel modèle sur tout le parcours.
    """
    question = "mon stock de tomates ?"

    premiere = routeur.repondre_avec_cascade(CTX, question)
    assert premiere.etage_resolveur == routeur.ETAGE_DONNEE
    assert cascade.query(QuestionCache).count() == 1, "la réponse a bien été mémorisée"

    # La question reposée telle quelle est servie par l'étage 0bis.
    depuis_cache = routeur.repondre_avec_cascade(CTX, question)
    assert depuis_cache.etage_resolveur == routeur.ETAGE_CACHE
    assert depuis_cache.texte == premiere.texte

    # 2. L'évènement contradictoire, par le chemin d'écriture réel.
    svc_evenements.creer_evenement_depuis_parse(
        cascade, CTX,
        {"action": "recolte", "culture": "tomate", "quantite": 5, "unite": "kg"},
        "récolté 5 kg de tomates",
    )
    assert cascade.query(QuestionCache).count() == 0, "CA5 : l'entrée a été supprimée"

    # 3. Même question : la réponse repart de l'état réel.
    seconde = routeur.repondre_avec_cascade(CTX, question)
    assert seconde.etage_resolveur == routeur.ETAGE_DONNEE
    assert "7 kg" in seconde.texte
    assert seconde.texte != premiere.texte


def test_us095_ca6_question_recurrente_servie_sans_aucun_appel_modele(cascade, sans_appel_modele):
    """CA6 / scénario Gherkin « Question récurrente servie instantanément » —
    la réponse est produite depuis le motif mémorisé, et aucun appel au modèle
    n'a lieu (le double armé par la fixture le prouve)."""
    question = "mon stock de tomates ?"
    routeur.repondre_avec_cascade(CTX, question)

    resultat = routeur.repondre_avec_cascade(CTX, question)

    assert resultat.etage_resolveur == routeur.ETAGE_CACHE
    ligne = cascade.query(RoutageLog).order_by(RoutageLog.id.desc()).first()
    assert ligne.etage_resolveur == routeur.ETAGE_CACHE
    assert ligne.tokens_consommes == 0


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — Correction et suppression invalident au même titre qu'une création
# ═════════════════════════════════════════════════════════════════════════════
def test_us095_ca7_correction_d_evenement_invalide(potager):
    """CA7 / scénario Gherkin « Correction d'événement prise en compte »."""
    evenement = svc_evenements.creer_evenement_depuis_parse(
        potager, CTX,
        {"action": "recolte", "culture": "tomate", "quantite": 5, "unite": "kg"},
        "récolté 5 kg de tomates",
    )
    _memoriser_stock_tomate(potager)
    assert potager.query(QuestionCache).count() == 1

    svc_evenements.corriger_evenement(
        potager, CTX, evenement.id, {"quantite": 3}, " | [CORR] 5 → 3",
    )
    assert potager.query(QuestionCache).count() == 0


def test_us095_ca7_suppression_d_evenement_invalide(potager):
    """CA7 — la suppression est le chemin le plus facile à oublier : l'entrée
    est lue AVANT la disparition de la ligne dont elle dérive."""
    evenement = svc_evenements.creer_evenement_depuis_parse(
        potager, CTX,
        {"action": "recolte", "culture": "tomate", "quantite": 5, "unite": "kg"},
        "récolté 5 kg de tomates",
    )
    _memoriser_stock_tomate(potager)

    assert svc_evenements.supprimer_evenement(potager, CTX, evenement.id) is True
    assert potager.query(QuestionCache).count() == 0


def test_us095_ca7_correction_de_culture_invalide_les_deux_cultures(potager):
    """CA7 — corriger « récolte de tomates » en « récolte de carottes » périme
    les réponses des DEUX cultures. N'invalider que la nouvelle laisserait le
    stock de tomates figé sur une récolte qui n'existe plus."""
    evenement = svc_evenements.creer_evenement_depuis_parse(
        potager, CTX,
        {"action": "recolte", "culture": "tomate", "quantite": 5, "unite": "kg"},
        "récolté 5 kg de tomates",
    )
    _memoriser_stock_tomate(potager)
    chiffree = rc.repondre_chiffre(CTX, "il me reste combien de carottes ?", db=potager)
    cq.memoriser_template_sql(potager, CTX, "il me reste combien de carottes ?", chiffree.aiguillage)
    assert potager.query(QuestionCache).count() == 2

    svc_evenements.corriger_evenement(
        potager, CTX, evenement.id,
        {"culture": "carotte", "unite": "plants"}, " | [CORR] tomate → carotte",
    )
    assert potager.query(QuestionCache).count() == 0


# ═════════════════════════════════════════════════════════════════════════════
# CA8 / CA9 — Isolation
# ═════════════════════════════════════════════════════════════════════════════
def test_us095_ca8_savoir_general_partage_entre_potagers(potager):
    """CA8 / scénario Gherkin « Savoir général partagé entre potagers » — une
    réponse figée est mémorisée sans potager, donc servie à tous."""
    texte = "Sème les carottes à environ 1 cm de profondeur, en ligne, puis tasse légèrement."
    entree = cq.memoriser_figee(potager, CTX, "à quelle profondeur semer les carottes ?", texte)
    assert entree.potager_id is None

    servie = cq.servir(CTX_VOISIN, "à quelle profondeur semer les carottes ?", db=potager)
    assert servie is not None
    assert servie.texte == texte
    assert servie.partagee is True


def test_us095_ca8_une_reponse_de_savoir_est_memorisee_puis_partagee(cascade):
    """CA8 — bout en bout : une question de connaissance générale posée par le
    potager 1 est mémorisée sans potager, et le potager 2 la reçoit sans
    qu'aucun modèle ne soit rappelé."""
    question = "à quelle profondeur semer les carottes ?"
    texte = "Sème-les à environ 1 cm, en ligne, puis tasse légèrement."

    with patch("llm.passerelle.appeler_chat", return_value=_reponse_modele(texte)) as modele:
        premiere = routeur.repondre_avec_cascade(CTX, question)
    assert premiere.texte == texte
    assert modele.called

    entree = cascade.query(QuestionCache).one()
    assert entree.type_reponse == cq.TYPE_FIGEE
    assert entree.potager_id is None

    with patch("llm.passerelle.appeler_chat", side_effect=AssertionError(
        "le savoir mémorisé doit être servi sans rappeler le modèle"
    )):
        chez_le_voisin = routeur.repondre_avec_cascade(CTX_VOISIN, question)
    assert chez_le_voisin.texte == texte
    assert chez_le_voisin.etage_resolveur == routeur.ETAGE_CACHE


def test_us095_ca8_refus_si_le_texte_cite_une_parcelle_du_potager(potager):
    """CA8 — le contrôle à l'écriture : une réponse qui nomme « planche-nord »
    n'est pas du savoir général, c'est une donnée du potager 1. La mémoriser
    en partagé serait la fuite la plus discrète et la plus durable."""
    assert cq.memoriser_figee(
        potager, CTX, "comment protéger mes semis du froid ?",
        "Pose un voile sur la planche-nord dès que la température descend.",
    ) is None
    assert potager.query(QuestionCache).count() == 0


def test_us095_ca8_refus_si_le_texte_cite_une_variete_du_potager(potager):
    """CA8 — une variété cultivée dans le potager est un nom propre, pas du
    savoir général."""
    assert cq.memoriser_figee(
        potager, CTX, "quelle variété résiste au mildiou ?",
        "La Marmande est réputée sensible, préfère une variété résistante.",
    ) is None


def test_us095_ca8_refus_si_le_modele_avoue_ne_pas_savoir(potager):
    """CA8 / note technique — cas réel du 29/08/2026 : l'appel avait RÉUSSI,
    mais le modèle répondait « je n'ai pas accès aux données météorologiques
    historiques ». Cette non-réponse avait été mémorisée en savoir général,
    donc partagée à TOUS les potagers pendant 90 jours.

    La garde du mode dégradé (429) ne couvrait pas ce cas : elle repose sur une
    exception levée, or ici rien n'a échoué."""
    assert cq.memoriser_figee(
        potager, CTX, "quel temps faisait-il en avril ?",
        "Je n'ai pas accès aux données météorologiques historiques en temps réel, "
        "donc je ne peux pas vous indiquer le temps qu'il a fait.",
    ) is None
    assert potager.query(QuestionCache).count() == 0


@pytest.mark.parametrize("texte", [
    "Je ne peux pas répondre à cette question.",
    "Je ne dispose pas de cette information.",
    "En tant qu'assistant, je n'ai pas de données sur ce point.",
])
def test_us095_ca8_les_formes_de_non_reponse_sont_reconnues(texte):
    """CA8 — le modèle décline de plusieurs façons ; toutes valent refus."""
    assert cq.est_non_reponse(texte) is True


def test_us095_ca8_un_vrai_savoir_n_est_pas_pris_pour_une_non_reponse():
    """CA8 — la garde ne doit pas être si large qu'elle refuse le savoir réel :
    une réponse agronomique normale passe."""
    assert cq.est_non_reponse(
        "Sème les carottes à environ 1 cm de profondeur, en ligne."
    ) is False


def test_us095_ca10_une_question_datee_n_est_pas_du_savoir_general(potager):
    """CA10 — une réponse figée doit être vraie indépendamment du moment.
    « quelle météo le 10/04 dernier » ne sera jamais reposée à l'identique, et
    signifierait autre chose l'an prochain : rien à mémoriser en partagé."""
    assert cq.memoriser_figee(
        potager, CTX, "quelle météo le 10/04 dernier ?", "Il a fait beau et sec.",
    ) is None
    assert cq.memoriser_figee(
        potager, CTX, "qu'ai-je fait hier au jardin ?", "Tu as taillé et arrosé.",
    ) is None
    # …tandis qu'une question intemporelle reste mémorisable.
    assert cq.memoriser_figee(
        potager, CTX, "à quelle profondeur semer les carottes ?", "Environ un centimètre.",
    ) is not None


def test_us095_ca4_une_reponse_figee_ne_declare_aucune_nature(potager):
    """CA4 — une réponse figée ne dérive d'AUCUN potager : elle ne doit
    déclarer aucune nature de donnée. Replier ce cas sur `journal` déclarerait
    une dépendance qui n'existe pas, et ferait tenir l'isolation du CA10 par le
    seul filtre `potager_id`."""
    assert cq._encoder_natures([]) == ""
    entree = cq.memoriser_figee(
        potager, CTX, "quand semer les carottes ?", "De mars à juillet selon les variétés.",
    )
    assert entree.natures == ""


def test_us095_ca8_un_nom_de_culture_n_est_pas_un_temoin_de_fuite(potager):
    """CA8 — le contrôle ne doit pas être si large qu'il interdise le savoir
    agronomique : « carotte » appartient au savoir général autant qu'au
    potager. Seuls les noms propres (parcelle, variété) sont des témoins."""
    entree = cq.memoriser_figee(
        potager, CTX, "quand semer les carottes ?",
        "Les carottes se sèment de mars à juillet selon les variétés.",
    )
    assert entree is not None


def test_us095_ca8_le_temoin_doit_apparaitre_comme_un_mot_entier(potager):
    """CA8 — un témoin ne se cherche pas au milieu d'un mot.

    Constaté le 04/09/2026 : le contrôle testait `temoin in texte`, donc la
    variété « verte » se reconnaissait dans « une racine ou*verte* », « serre »
    dans « plantules *serre*es », « autre » dans « d'*autre*s insectes ». Aucune
    de ces phrases ne cite quoi que ce soit du potager, et 23 fragments sur 96
    du corpus agronomique tombaient sous ce couperet — donc autant de réponses
    qu'on ne pouvait jamais mémoriser, repayées au modèle à chaque fois.
    """
    for phrase in (
        "Une racine ouverte se conserve moins bien.",
        "Des plantules serrees se concurrencent pour la lumiere.",
        "D'autres insectes peuvent laisser des blessures voisines.",
    ):
        assert not cq.contient_donnee_potager(potager, CTX.potager_id, phrase), \
            f"faux positif sur un mot courant : {phrase!r}"


def test_us095_ca8_un_vrai_nom_reste_detecte_meme_au_pluriel(potager):
    """CA8 — la borne de mot ne doit pas ouvrir une porte : le nom propre reste
    reconnu, y compris accordé au pluriel."""
    assert cq.contient_donnee_potager(
        potager, CTX.potager_id, "Pose un voile sur la planche-nord ce soir.")
    assert cq.contient_donnee_potager(
        potager, CTX.potager_id, "Les Marmandes de cette annee ont bien donne.")


def test_us095_ca8_une_valeur_generique_n_est_pas_un_temoin(potager):
    """CA8 — `evenements.variete` est un champ LIBRE : il reçoit « Gariguette »
    comme « autre », « blanc » ou « variété non précisée ». Les secondes sont
    des mots français ordinaires — les retenir comme témoins ne protège rien et
    interdit de mémoriser le savoir le plus banal.

    Le critère reste celui de la docstring : un témoin est un nom que SEUL ce
    potager emploie.
    """
    for generique in ("autre", "blanc", "verte", "cerise", "variete non precisee",
                      "recolte de 2025", "annee 2024"):
        assert not cq._est_temoin_exploitable(generique), \
            f"{generique!r} ne devrait pas servir de témoin de fuite"
    for propre in ("gariguette", "marmande", "coeur de boeuf", "planche-nord",
                   "noire de crimee"):
        assert cq._est_temoin_exploitable(propre), \
            f"{propre!r} est un nom propre du potager, il doit rester un témoin"


def test_us095_ca8_une_reponse_agronomique_banale_est_memorisable(potager):
    """CA8, bout en bout — c'est le défaut tel qu'il se voyait en production :
    une réponse générale sur le tuteurage était refusée à la mémorisation, donc
    la même question repayait un appel modèle à chaque fois."""
    entree = cq.memoriser_figee(
        potager, CTX, "comment tuteurer mes haricots grimpants ?",
        "Installe un support avant que les tiges ne s'allongent : les jeunes "
        "pousses s'y enroulent d'elles-memes. Des plantules serrees se "
        "concurrencent, et une tige ouverte cicatrise mal.",
    )
    assert entree is not None, "une reponse agronomique generale doit etre memorisable"


def test_us095_ca9_aucune_fuite_entre_potagers(potager, sans_appel_modele):
    """CA9 / scénario Gherkin « Aucune fuite entre potagers » — une réponse
    mémorisée pour le potager A n'est jamais servie au potager B, même à motif
    strictement identique."""
    _memoriser_stock_tomate(potager)
    assert cq.servir(CTX, "mon stock de tomates ?", db=potager) is not None
    assert cq.servir(CTX_VOISIN, "mon stock de tomates ?", db=potager) is None


def test_us095_ca9_une_entree_parametree_partagee_ne_serait_jamais_servie(potager, sans_appel_modele):
    """CA9 — défense en profondeur : même si une entrée paramétrée se
    retrouvait avec `potager_id` nul (donnée corrompue, migration ratée), elle
    ne serait pas servie — elle recalculerait sur les données d'un potager
    pour un autre."""
    potager.add(QuestionCache(
        potager_id=None, motif_normalise="mon stock de tomates",
        type_reponse=cq.TYPE_TEMPLATE_SQL,
        template=json.dumps({"famille": "stock_courant", "culture": "tomate",
                             "parcelle": None, "dependances": ["stock"]}),
        source_etage=cq.SOURCE_SQL, natures="|stock|",
    ))
    potager.commit()
    assert cq.servir(CTX_VOISIN, "mon stock de tomates ?", db=potager) is None


def test_us095_ca8_le_cache_part_avec_le_potager_purge(potager):
    """CA8 — la purge physique d'un potager (US-084 / CA7) emporte ses entrées
    de cache : elles nomment ses cultures et ses parcelles."""
    from database.models import Potager, User

    proprietaire = User(id=1, email="jardinier@example.test")
    potager.add(proprietaire)
    potager.commit()
    potager.add(Potager(id=1, nom="Mon potager", proprietaire_id=proprietaire.id))
    potager.commit()
    _memoriser_stock_tomate(potager)
    assert svc_potagers.purger_potager(potager, 1)["volumes"]["questions_cache"] == 1


# ═════════════════════════════════════════════════════════════════════════════
# CA10 — Durée de vie et lien au fragment de connaissance
# ═════════════════════════════════════════════════════════════════════════════
def test_us095_ca10_une_reponse_figee_porte_90_jours_de_validite(potager):
    """CA10 — durée de validité par défaut d'une réponse figée."""
    entree = cq.memoriser_figee(potager, CTX, "quand semer les carottes ?", "De mars à juillet.")
    reste = entree.valide_jusqu_au - datetime.utcnow()
    assert timedelta(days=89) < reste <= timedelta(days=cq.TTL_FIGEE_JOURS)


def test_us095_ca10_fiche_corrigee_invalide_les_reponses_qui_en_derivent(potager):
    """CA10 / scénario Gherkin « Fiche de connaissance corrigée » — corriger
    une fiche agronomique ne doit pas laisser vivre des mois une réponse
    erronée. Le lien est une simple référence stockée, pas un mécanisme
    d'événements (note technique de l'US)."""
    cq.memoriser_figee(
        potager, CTX, "à quelle profondeur semer les carottes ?",
        "Environ 1 cm.", source_etage=cq.SOURCE_RAG, fragment_id="fiche-carotte-v1",
    )
    cq.memoriser_figee(
        potager, CTX, "quand semer les carottes ?",
        "De mars à juillet.", source_etage=cq.SOURCE_RAG, fragment_id="fiche-carotte-v2",
    )

    assert cq.invalider_par_fragment(potager, "fiche-carotte-v1") == 1
    restantes = potager.query(QuestionCache).all()
    assert [e.fragment_id for e in restantes] == ["fiche-carotte-v2"]


def test_us095_ca10_un_evenement_ne_touche_jamais_le_savoir_general(potager):
    """CA10 — une réponse figée ne dérive d'aucun potager : aucun évènement ne
    peut la contredire, donc aucune écriture ne la supprime. Seuls sa durée de
    vie et son fragment d'origine la font tomber."""
    entree = cq.memoriser_figee(potager, CTX, "quand semer les carottes ?", "De mars à juillet.")
    # La raison PREMIÈRE : l'entrée ne déclare aucune dépendance de donnée.
    # Sans cette assertion, le test tiendrait par le seul filtre `potager_id`
    # de l'invalidation, et passerait encore si l'entrée déclarait à tort
    # dériver du journal.
    assert entree.natures == ""

    svc_evenements.creer_evenement_depuis_parse(
        potager, CTX,
        {"action": "recolte", "culture": "carotte", "quantite": 3, "unite": "plants"},
        "récolté 3 carottes",
    )
    assert potager.query(QuestionCache).count() == 1


# ═════════════════════════════════════════════════════════════════════════════
# CA11 — Durée de vie : écartées à la lecture, nettoyées au fil de l'eau
# ═════════════════════════════════════════════════════════════════════════════
def test_us095_ca11_une_entree_perimee_n_est_pas_servie(potager, sans_appel_modele):
    """CA11 — écartée à la lecture, avant même d'être nettoyée."""
    entree = _memoriser_stock_tomate(potager)
    entree.valide_jusqu_au = datetime.utcnow() - timedelta(days=1)
    potager.commit()
    assert cq.servir(CTX, "mon stock de tomates ?", db=potager) is None


def test_us095_ca11_les_perimees_sont_nettoyees_a_l_ecriture_suivante(potager):
    """CA11 — nettoyage au fil de l'eau, à l'occasion d'une écriture : aucun
    job planifié n'est ajouté pour cela."""
    perimee = _memoriser_stock_tomate(potager)
    perimee.valide_jusqu_au = datetime.utcnow() - timedelta(days=1)
    potager.commit()

    chiffree = rc.repondre_chiffre(CTX, "il me reste combien de carottes ?", db=potager)
    cq.memoriser_template_sql(potager, CTX, "il me reste combien de carottes ?", chiffree.aiguillage)

    motifs = {e.motif_normalise for e in potager.query(QuestionCache).all()}
    assert motifs == {"il me reste combien de carottes"}


def test_us095_ca11_aucun_job_planifie_ajoute():
    """CA11 — « aucun nouveau job planifié n'est ajouté pour cela » : le cache
    n'apparaît nulle part dans la planification du bot."""
    bot_source = (RACINE / "bot.py").read_text(encoding="utf-8")
    assert "cache_questions" not in bot_source


def test_us095_borne_haute_par_potager(potager, monkeypatch):
    """Note technique — une saisie erratique ne doit pas faire croître la table
    indéfiniment : au-delà de la borne, les plus anciennes cèdent la place."""
    monkeypatch.setattr(cq, "MAX_ENTREES_PAR_POTAGER", 3)
    chiffree = rc.repondre_chiffre(CTX, "mon stock de tomates ?", db=potager)
    for indice in range(6):
        cq.memoriser_template_sql(
            potager, CTX, f"mon stock de tomates numero {indice} ?", chiffree.aiguillage,
        )
    assert potager.query(QuestionCache).count() <= 3


# ═════════════════════════════════════════════════════════════════════════════
# CA12 — Mesure du taux de service
# ═════════════════════════════════════════════════════════════════════════════
def _log_routage(db, etage: str, origine: str = routeur.ORIGINE_REGLE) -> None:
    db.add(RoutageLog(
        potager_id=1, question_normalisee="mon stock de tomates",
        nature=routeur.NATURE_QUESTION_DATA, origine_classification=origine,
        etage_resolveur=etage, cascade_remontee=False, confiance=1.0,
        latence_ms=1, tokens_consommes=0, cree_le=datetime.utcnow(),
    ))
    db.commit()


def test_us095_ca12_le_taux_de_service_est_mesure_et_expose(test_db):
    """CA12 — le taux de service depuis le cache est mesuré, et confronté à
    l'hypothèse de ~40 % : elle est vérifiée par la mesure, jamais affirmée."""
    for _ in range(4):
        _log_routage(test_db, routeur.ETAGE_CACHE, routeur.ORIGINE_CACHE)
    for _ in range(6):
        _log_routage(test_db, routeur.ETAGE_DONNEE)

    mesure = svc_metriques.taux_service_cache_reponses(test_db)
    assert mesure["taux"] == pytest.approx(0.4)
    assert mesure["nb_servies"] == 4
    assert mesure["hypothese"] == 0.40
    assert mesure["ecart"] == pytest.approx(0.0)


def test_us095_ca12_aucune_question_mesuree_n_est_pas_zero_pour_cent(test_db):
    """CA12 — « rien à rapporter » et « 0 % servi » sont deux choses
    différentes : la première itération après déploiement ne doit pas se lire
    comme un échec de l'hypothèse."""
    assert svc_metriques.taux_service_cache_reponses(test_db)["taux"] is None


def test_us095_ca12_les_deux_caches_se_mesurent_separement(test_db):
    """CA12 — le cache de RÉPONSES (étage 0bis) et le cache de CLASSIFICATION
    en mémoire du routeur sont deux objets distincts. Confondre leurs mesures
    ferait croire l'un efficace parce que l'autre l'est."""
    _log_routage(test_db, routeur.ETAGE_CACHE, routeur.ORIGINE_CACHE)
    _log_routage(test_db, routeur.ETAGE_RAISONNEMENT, routeur.ORIGINE_CACHE)
    _log_routage(test_db, routeur.ETAGE_DONNEE, routeur.ORIGINE_REGLE)

    assert svc_metriques.taux_service_cache_reponses(test_db)["nb_servies"] == 1
    # Une seule classification servie par le cache mémoire (la réponse servie
    # par l'étage 0bis n'en est pas une).
    assert svc_metriques.taux_service_cache(test_db) == pytest.approx(1 / 3)


# ═════════════════════════════════════════════════════════════════════════════
# CA13 — Indiscernable d'une réponse fraîche
# ═════════════════════════════════════════════════════════════════════════════
def test_us095_ca13_la_reponse_servie_ne_mentionne_jamais_le_cache(cascade, sans_appel_modele):
    """CA13 — aucune mention « réponse en cache » : seul le journal en garde
    trace. Le texte servi est mot pour mot celui d'une réponse fraîche."""
    question = "mon stock de tomates ?"
    fraiche = routeur.repondre_avec_cascade(CTX, question)
    depuis_cache = routeur.repondre_avec_cascade(CTX, question)

    assert depuis_cache.texte == fraiche.texte
    for marqueur in ("cache", "mémoris", "memoris", "déjà répondu"):
        assert marqueur not in depuis_cache.texte.lower()


# ═════════════════════════════════════════════════════════════════════════════
# Ce qui ne doit JAMAIS être mémorisé
# ═════════════════════════════════════════════════════════════════════════════
def test_us095_une_reponse_hybride_n_est_jamais_memorisee(cascade):
    """Une réponse hybride mêle par définition raisonnement et données du
    potager : ni rejouable (aucune famille), ni partageable (elle porte des
    chiffres du potager). Elle n'est donc mémorisée sous aucune des deux
    formes."""
    question = "mes tomates jaunissent alors que j'ai beaucoup arrosé, qu'en penses-tu ?"
    with patch("llm.passerelle.appeler_chat", return_value=_reponse_modele("Sans doute un excès d'eau.")):
        routeur.repondre_avec_cascade(CTX, question)
    assert cascade.query(QuestionCache).count() == 0


def test_us095_le_mode_degrade_n_est_jamais_memorise(cascade):
    """Note technique — une réponse produite en mode dégradé (429) serait
    mémorisée comme une non-réponse, puis servie comme une réponse. Une
    cascade interrompue ne mémorise rien."""
    question = "pourquoi mes tomates ont-elles le cul noir ?"
    with patch("llm.passerelle.appeler_chat", side_effect=LLMIndisponibleError("quota dépassé")):
        with pytest.raises(LLMIndisponibleError):
            routeur.repondre_avec_cascade(CTX, question)
    assert cascade.query(QuestionCache).count() == 0


def test_us095_une_absence_de_donnee_n_est_jamais_memorisee(cascade):
    """Une famille reconnue mais sans donnée (`present=False`) rend la main à
    la cascade : mémoriser sa phrase d'absence reviendrait à figer un « je n'ai
    rien » que le premier enregistrement démentirait."""
    question = "combien de physalis ai-je récolté cette saison ?"
    with patch("llm.passerelle.appeler_chat", return_value=_reponse_modele("Aucune récolte connue.")):
        routeur.repondre_avec_cascade(CTX, question)
    assert cascade.query(QuestionCache).count() == 0


def test_us095_une_panne_du_cache_ne_casse_jamais_la_reponse(cascade):
    """L'étage 0bis est une accélération, jamais un point de défaillance : une
    lecture impossible rend la main à la cascade telle qu'elle existait avant
    cette US."""
    with patch.object(cq, "_entree_parametree", side_effect=RuntimeError("base indisponible")):
        resultat = routeur.repondre_avec_cascade(CTX, "mon stock de tomates ?")
    assert resultat.etage_resolveur == routeur.ETAGE_DONNEE
    assert "tomate" in resultat.texte.lower()

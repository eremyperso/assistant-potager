"""
tests/test_us096_reponses_chiffrees_gabarits.py
[US-096] Répondre aux questions chiffrées par des gabarits sur agrégats SQL

Couverture des critères d'acceptance CA1 → CA12. Aucun appel réseau : la
passerelle LLM (`llm.passerelle.appeler_chat`) et l'extraction d'intention
(`llm.groq_client.extract_intent_query_mesuree`) sont remplacées par des doubles
qui **échouent le test s'ils sont appelés** — c'est la seule façon de prouver le
CA1 (« sans aucun appel au modèle ») plutôt que de l'affirmer.

Le jeu de données reproduit exactement le modèle de domaine que l'US impose de
distinguer : une culture reproductrice (haricot, courgette — le pied reste en
place, la cueillette ne diminue rien) et une culture végétative (carotte — la
récolte consomme le pied).
"""
from datetime import datetime
from unittest.mock import patch

import pytest

from app.services import catalogue_sql, questions as svc_questions
from app.services import reponses_chiffrees as rc
from app.services.catalogue_sql import (
    DelaiRequeteDepasseError,
    EcritureInterditeError,
    RequeteHorsCatalogueError,
    RequeteNonIsoleeError,
)
from app.services.context import TenantContext
from database.models import CultureConfig, Evenement, Parcelle
from utils import stock as _stock

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
CTX_VOISIN = TenantContext(user_id=2, potager_id=2, role="owner")

ANNEE = datetime.now().year


def _evenement(**champs) -> Evenement:
    return Evenement(**champs)


@pytest.fixture
def potager(test_db):
    """Un potager complet : une reproductrice pesée, une reproductrice en pieds,
    une végétative, une parcelle occupée et un lot de pépinière."""
    test_db.add_all([
        CultureConfig(nom="courgette", type_organe_recolte="reproducteur", potager_id=None),
        CultureConfig(nom="haricot", type_organe_recolte="reproducteur", potager_id=None),
        CultureConfig(nom="carotte", type_organe_recolte="végétatif", potager_id=None),
        CultureConfig(nom="fraise", type_organe_recolte="reproducteur", potager_id=None),
    ])
    nord = Parcelle(nom="NORD", nom_normalise="nord", potager_id=1, actif=True, est_pepiniere=False)
    test_db.add(nord)
    test_db.commit()

    test_db.add_all([
        # Courgette : 4 pieds plantés, 2 récoltes pesées (2,5 kg + 1200 g = 3,7 kg)
        _evenement(date=datetime(ANNEE, 5, 1), type_action="plantation", culture="courgette",
                   quantite=4, unite="plants", potager_id=1, parcelle_id=nord.id),
        _evenement(date=datetime(ANNEE, 7, 3), type_action="recolte", culture="courgette",
                   quantite=2.5, unite="kg", potager_id=1),
        _evenement(date=datetime(ANNEE, 7, 20), type_action="recolte", culture="courgette",
                   quantite=1200, unite="g", potager_id=1),
        # Haricot : 30 pieds en place, 3 cueillettes (scénario Gherkin)
        _evenement(date=datetime(ANNEE, 5, 2), type_action="plantation", culture="haricot",
                   quantite=30, unite="plants", potager_id=1, parcelle_id=nord.id),
        _evenement(date=datetime(ANNEE, 7, 1), type_action="recolte", culture="haricot",
                   quantite=800, unite="g", potager_id=1),
        _evenement(date=datetime(ANNEE, 7, 8), type_action="recolte", culture="haricot",
                   quantite=600, unite="g", potager_id=1),
        _evenement(date=datetime(ANNEE, 7, 15), type_action="recolte", culture="haricot",
                   quantite=500, unite="g", potager_id=1),
        # Carotte végétative : 40 plantées, 12 récoltées en pièces
        # Semis en pépinière (pas de parcelle) : un semis pleine terre ferait
        # cohabiter graines et plants sur la même culture, conflit d'unité que
        # US-037/CA2 tranche en excluant l'une des deux — hors sujet ici.
        _evenement(date=datetime(ANNEE, 4, 12), type_action="semis", culture="carotte",
                   quantite=100, unite="graines", potager_id=1),
        _evenement(date=datetime(ANNEE, 5, 10), type_action="plantation", culture="carotte",
                   quantite=40, unite="plants", potager_id=1, parcelle_id=nord.id),
        _evenement(date=datetime(ANNEE, 8, 1), type_action="recolte", culture="carotte",
                   quantite=12, unite="plants", potager_id=1),
        # Pépinière : un lot de semis sans parcelle, encore en germination
        _evenement(date=datetime(ANNEE, 3, 4), type_action="semis", culture="fraise",
                   quantite=50, unite="graines", nb_graines_semees=50, potager_id=1),
    ])
    test_db.commit()
    return test_db


@pytest.fixture(autouse=True)
def _aucun_appel_modele():
    """[CA1] Tout appel modèle pendant ces tests est un échec, pas un détail."""
    with patch("llm.passerelle.appeler_chat", side_effect=AssertionError(
        "CA1 violé : un appel au modèle a eu lieu pour une question chiffrée"
    )):
        yield


@pytest.fixture
def session_applicative(potager, monkeypatch):
    """Fait pointer `SessionLocal` du service vers la session de test, pour les
    tests qui passent par le chemin applicatif réel (`repondre_question`)."""
    monkeypatch.setattr(rc, "SessionLocal", lambda: potager)
    return potager


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — Le catalogue des familles, servi sans aucun appel au modèle
# ═════════════════════════════════════════════════════════════════════════════
FAMILLES_ATTENDUES = {
    "total_recolte", "derniere_occurrence", "stock_courant", "pieds_actifs",
    "rendement_saison", "pepiniere", "occupation_parcelle",
    # [Chantier 3 / US-170] Nombre de godets produits — distinct du rendement
    # récolté, que le motif `\bproduit\b` de rendement_saison confondait avec lui.
    "godets_produits",
    # Variantes « toutes cultures » des deux familles qui se posent aussi sans
    # culture nommée — ajoutées après les essais en conditions réelles du
    # 26/08/2026, où « quel est le rendement de la saison ? » et « quel est mon
    # stock ? » partaient au modèle faute d'être reconnues.
    "rendement_global", "stock_global",
    # Ajoutée après les essais du 26/08/2026 : « j'ai combien de parcelle
    # vide ? » est une question chiffrée qui partait au modèle pour recevoir
    # une réponse inventée.
    "parcelles_libres",
    # Ajoutée après l'essai du 02/09/2026 : « quelles parcelles contiennent des
    # solanacées ? » repartait à l'agent SQL, qui servait un « Top cultures »
    # hors sujet — couverte par tests/test_parcelles_par_famille_botanique.py.
    "parcelles_par_famille",
    # Même essai, symétrique : « sur quelles parcelles je trouve des
    # tomates ? » recevait un « Historique observation de tomate ».
    "parcelles_par_culture",
}


def test_us096_catalogue_couvre_les_familles_du_ca1():
    """CA1 — les familles annoncées existent, ni plus ni moins."""
    assert {famille.nom for famille in rc.FAMILLES} == FAMILLES_ATTENDUES


@pytest.mark.parametrize("question,famille", [
    ("combien de courgettes récoltées cet été ?", "total_recolte"),
    ("quand ai-je semé les carottes ?", "derniere_occurrence"),
    ("il me reste combien de carottes ?", "stock_courant"),
    ("combien de pieds de haricot ?", "pieds_actifs"),
    ("où en sont mes haricots ?", "rendement_saison"),
    ("qu'est-ce qu'il y a en pépinière ?", "pepiniere"),
    ("qu'est-ce qu'il y a dans la parcelle NORD ?", "occupation_parcelle"),
])
def test_us096_ca1_chaque_famille_repond_sans_modele(potager, question, famille):
    """CA1 — chaque famille est aiguillée et servie ; le double d'appel modèle
    est armé par la fixture autouse : un seul appel ferait échouer le test."""
    reponse = rc.repondre_chiffre(CTX, question, db=potager)
    assert reponse is not None, f"aucune famille reconnue pour « {question} »"
    assert reponse.famille == famille
    assert reponse.present is True


def test_us096_ca1_question_hors_catalogue_rend_la_main(potager):
    """CA1 — une question de savoir ne relève d'aucune famille : l'étage passe
    son tour (None) au lieu de forcer une réponse chiffrée sans objet."""
    assert rc.repondre_chiffre(CTX, "pourquoi mes tomates ont le cul noir ?", db=potager) is None


def test_us096_ca1_extraction_intention_court_circuitee(session_applicative):
    """CA1 — sur le chemin applicatif réel, l'extraction d'intention (seul appel
    modèle restant de l'étage data) n'a plus lieu pour une question chiffrée."""
    with patch(
        "app.services.questions.extract_intent_query_mesuree",
        side_effect=AssertionError("CA1 violé : extraction d'intention appelée"),
    ):
        texte, confiant = svc_questions.repondre_question_avec_confiance(
            CTX, "combien de courgettes récoltées cet été ?"
        )
    assert confiant is True
    assert "3.7 kg" in texte


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — La réponse est produite par le gabarit, pas par le modèle
# ═════════════════════════════════════════════════════════════════════════════
def test_us096_ca2_reponse_conforme_au_gabarit(potager):
    """CA2 — la phrase servie est le gabarit de la famille, trous remplis."""
    reponse = rc.repondre_chiffre(CTX, "combien de courgettes récoltées cet été ?", db=potager)
    assert reponse.texte == "Tu as récolté 3.7 kg de courgette cet été (2 récoltes)."


def test_us096_ca2_aucun_trou_laisse_dans_les_gabarits(potager):
    """CA2 — un trou non rempli est un défaut visible du jardinier : aucune
    réponse servie ne doit contenir d'accolade résiduelle."""
    questions = [
        "combien de courgettes récoltées cet été ?", "quand ai-je semé les carottes ?",
        "il me reste combien de carottes ?", "combien de pieds de haricot ?",
        "où en sont mes haricots ?", "qu'est-ce qu'il y a en pépinière ?",
        "qu'est-ce qu'il y a dans la parcelle NORD ?",
    ]
    for question in questions:
        reponse = rc.repondre_chiffre(CTX, question, db=potager)
        assert "{" not in reponse.texte and "}" not in reponse.texte, question


def test_us096_ca2_gabarits_remplis_sans_format():
    """CA2 — `_remplir` substitue littéralement : une accolade parasite dans une
    valeur ne casse rien, là où `.format()` lèverait (invariant projet prompts)."""
    assert rc._remplir("bonjour {qui}", {"qui": "{monde}"}) == "bonjour {monde}"


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — Le type d'organe de récolte commande la phrase
# ═════════════════════════════════════════════════════════════════════════════
def test_us096_ca3_reproducteur_distingue_rendement_et_pieds(potager):
    """CA3 + Gherkin — 30 pieds de haricots et trois cueillettes : la réponse
    donne le rendement cumulé ET, séparément, les pieds toujours en place."""
    reponse = rc.repondre_chiffre(CTX, "où en sont mes haricots ?", db=potager)
    assert "1.9 kg" in reponse.texte          # 800 + 600 + 500 g
    assert "30 plants" in reponse.texte
    assert "toujours en place" in reponse.texte


def test_us096_ca3_cueillette_jamais_presentee_comme_une_diminution(potager):
    """CA3 — « il me reste combien de courgettes ? » sur une reproductrice ne
    doit jamais annoncer un stock qui diminue à chaque cueillette."""
    reponse = rc.repondre_chiffre(CTX, "il me reste combien de courgettes ?", db=potager)
    assert "4 plants toujours en place" in reponse.texte
    assert "la cueillette ne les diminue pas" in reponse.texte
    assert "Il te reste" not in reponse.texte


def test_us096_ca3_vegetatif_voit_bien_son_stock_diminuer(potager):
    """CA3 — sur une végétative, la récolte consomme le pied : 40 − 12 = 28."""
    reponse = rc.repondre_chiffre(CTX, "il me reste combien de carottes ?", db=potager)
    assert reponse.texte.startswith("Il te reste 28 plants de carotte")
    assert "récolté 12" in reponse.texte


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — Un seul chiffre pour une même réalité, bot et web confondus
# ═════════════════════════════════════════════════════════════════════════════
def test_us096_ca4_meme_chiffre_que_l_api_web(potager):
    """CA4 — le rendement du gabarit est exactement celui que /stats sérialise
    pour la PWA : même fonction de service, même arrondi."""
    stocks = _stock.calcul_stock_cultures(potager, potager_id=1)
    json_web = {entree["culture"]: entree for entree in _stock.format_stock_stats_json(stocks)}
    rendement_web = round(json_web["courgette"]["rendement_total"], 2)

    reponse = rc.repondre_chiffre(CTX, "combien de courgettes récoltées cet été ?", db=potager)
    assert f"{rendement_web:g} kg" in reponse.texte


def test_us096_ca4_meme_stock_que_stats_telegram(potager):
    """CA4 — le nombre de pieds actifs est celui de la ligne /stats Telegram."""
    stocks = _stock.calcul_stock_cultures(potager, potager_id=1)
    ligne_telegram = _stock.format_stock_ligne_telegram(stocks["carotte"])

    reponse = rc.repondre_chiffre(CTX, "il me reste combien de carottes ?", db=potager)
    assert "28 plants" in ligne_telegram and "28 plants" in reponse.texte


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — Ce qui est transmis au modèle : un résumé chiffré, jamais des lignes
# ═════════════════════════════════════════════════════════════════════════════
def test_us096_ca5_resume_compact_et_sans_ligne_brute(potager):
    """CA5 — le résumé transmissible reste très en deçà de 1 000 jetons et ne
    contient aucune ligne d'événement brute (ni id, ni texte dicté)."""
    for question in ("où en sont mes haricots ?", "qu'est-ce qu'il y a dans la parcelle NORD ?"):
        reponse = rc.repondre_chiffre(CTX, question, db=potager)
        assert len(reponse.resume) < 1500      # ~1 000 jetons, très largement
        assert "texte_original" not in reponse.resume
        assert "Evenement" not in reponse.resume


def test_us096_ca5_seul_le_resume_agrege_descend_a_l_etage_suivant(session_applicative):
    """CA5 — sur une question hybride, l'étage de raisonnement ne reçoit que le
    résumé déjà agrégé produit par le gabarit."""
    from llm import routeur

    routeur.vider_cache()
    contextes: list[str] = []

    def _faux_raisonnement(ctx, question, contexte_donnees=""):
        contextes.append(contexte_donnees)
        return "réponse de raisonnement"

    with patch.object(routeur, "_repondre_raisonnement", side_effect=_faux_raisonnement), \
         patch.object(routeur, "_persister_routage_log", return_value=None):
        routeur.repondre_avec_cascade(CTX, "où en sont mes haricots, à ton avis ?")

    assert contextes and "1.9 kg" in contextes[0]
    assert "texte_original" not in contextes[0]


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — Le taux de questions de données servies sans modèle est mesuré
# ═════════════════════════════════════════════════════════════════════════════
def test_us096_ca6_taux_donnees_sans_modele_publie(test_db):
    """CA6 — l'indicateur principal de succès de l'US est calculable sur
    `routage_logs`, sans colonne nouvelle : une cascade à 0 jeton est une
    question de données servie sans modèle."""
    from app.services import metriques_routage
    from database.models import RoutageLog
    from llm.routeur import ETAGE_DONNEE, ETAGE_RAISONNEMENT

    test_db.add_all([
        RoutageLog(potager_id=1, question_normalisee="q1", nature="QUESTION_DATA",
                   origine_classification="regle", etage_resolveur=ETAGE_DONNEE,
                   cascade_remontee=False, confiance=1.0, latence_ms=5, tokens_consommes=0),
        RoutageLog(potager_id=1, question_normalisee="q2", nature="QUESTION_DATA",
                   origine_classification="regle", etage_resolveur=ETAGE_DONNEE,
                   cascade_remontee=False, confiance=1.0, latence_ms=8, tokens_consommes=0),
        RoutageLog(potager_id=1, question_normalisee="q3", nature="QUESTION_DATA",
                   origine_classification="regle", etage_resolveur=ETAGE_DONNEE,
                   cascade_remontee=False, confiance=1.0, latence_ms=900, tokens_consommes=140),
        RoutageLog(potager_id=1, question_normalisee="q4", nature="QUESTION_SAVOIR",
                   origine_classification="regle", etage_resolveur=ETAGE_RAISONNEMENT,
                   cascade_remontee=False, confiance=1.0, latence_ms=1200, tokens_consommes=800),
    ])
    test_db.commit()

    assert metriques_routage.taux_donnees_sans_modele(test_db) == pytest.approx(2 / 3)


def test_us096_ca6_aucune_question_de_donnee_ne_vaut_pas_zero(test_db):
    """CA6 — rien à rapporter (None) n'est pas « 0 % sans modèle » : la même
    honnêteté que le CA7 s'applique aux métriques."""
    from app.services import metriques_routage

    assert metriques_routage.taux_donnees_sans_modele(test_db) is None


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — Un résultat vide n'est jamais présenté comme un zéro
# ═════════════════════════════════════════════════════════════════════════════
def test_us096_ca7_absence_de_donnee_dite_honnetement(potager):
    """CA7 + Gherkin — aucune récolte de fraises : la réponse le dit, et
    n'annonce pas un total de zéro."""
    reponse = rc.repondre_chiffre(CTX, "combien de fraises ai-je récolté cette année ?", db=potager)
    assert reponse.present is False
    assert reponse.texte == "Je n'ai aucune récolte de fraise enregistrée cette année."
    assert "0" not in reponse.texte


def test_us096_ca7_absence_portee_par_le_type_de_retour(potager):
    """CA7 — la distinction vit dans le type de retour de l'agrégation, pas
    seulement dans la phrase : `present` est faux, la valeur agrégée est nulle."""
    agregat = catalogue_sql.executer(
        "total_recolte", potager, CTX, culture="fraise", periode=rc.Periode(),
    )
    assert agregat["present"] is False
    assert agregat["poids_g"] == 0.0 and agregat["nb"] == 0


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — Un résultat vide rend la main à l'étage suivant
# ═════════════════════════════════════════════════════════════════════════════
def test_us096_ca8_resultat_vide_rend_la_main(session_applicative):
    """CA8 — `confiant=False` est le signal de remontée de cascade d'US-093,
    produit ici sans qu'aucun appel modèle n'ait été payé pour le constater."""
    with patch(
        "app.services.questions.extract_intent_query_mesuree",
        side_effect=AssertionError("CA8 violé : appel modèle pour constater un vide"),
    ):
        texte, confiant = svc_questions.repondre_question_avec_confiance(
            CTX, "combien de fraises ai-je récolté cette année ?"
        )
    assert confiant is False
    assert "aucune récolte" in texte


def test_us096_ca8_cascade_remonte_effectivement():
    """CA8 — vue de la cascade complète : l'étage donnée passe la main une fois,
    et c'est l'étage de raisonnement qui produit la réponse finale.

    [US-170 / CA18 — révision de CA6/CA7] `repondre_question_detaille` est mocké
    pour renvoyer `chiffree=None` : c'est désormais le SEUL signal de remontée
    (aucune famille du catalogue n'a matché — culture inconnue du potager, par
    exemple). Avant US-170, ce test portait sur « combien de fraises ai-je
    récolté cette année ? » contre le potager réel — une culture semée mais
    jamais récoltée, donc une famille qui MATCHE avec `present=False` : la
    remontée y était précisément le bug corrigé par le chantier 2 (« Je n'ai
    aucune récolte de fraise enregistrée » est une réponse exacte, pas un
    échec — voir `tests/test_us170_routage_questions.py` pour ce cas précis,
    servi directement sans remontée)."""
    from llm import routeur

    routeur.vider_cache()
    with patch.object(routeur, "_repondre_raisonnement", return_value="réponse d'expert"), \
         patch.object(routeur, "_persister_routage_log", return_value=None), \
         patch(
             "app.services.questions.repondre_question_detaille",
             return_value=("Aucune donnée enregistrée pour physalis / recolte.", False, None),
         ) as mock_data:
        resultat = routeur.repondre_avec_cascade(
            CTX, "combien de physalis ai-je récolté cette année ?"
        )
    mock_data.assert_called_once()  # [CA7] un seul saut, jamais répété
    assert resultat.texte == "réponse d'expert"
    assert resultat.etage_resolveur == routeur.ETAGE_RAISONNEMENT


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — Aucune requête SQL librement composée n'est exécutable
# ═════════════════════════════════════════════════════════════════════════════
def test_us096_ca9_agregation_hors_catalogue_refusee(potager):
    """CA9 — un nom d'agrégation qui n'est pas au catalogue est refusé, quelle
    que soit son origine."""
    with pytest.raises(RequeteHorsCatalogueError):
        catalogue_sql.executer("SELECT * FROM evenements", potager, CTX)


def test_us096_ca9_toutes_les_familles_pointent_vers_le_catalogue():
    """CA9 + Gherkin — seule une requête du catalogue prédéfini est exécutable :
    aucune famille ne peut désigner une agrégation qui n'y figure pas."""
    noms = set(catalogue_sql.noms_catalogue())
    assert {famille.agregation for famille in rc.FAMILLES} <= noms


def test_us096_ca9_aucun_sql_textuel_dans_les_agregations():
    """CA9 — le module d'agrégation ne construit aucune requête textuelle : tout
    passe par des requêtes ORM paramétrées."""
    import inspect

    source = inspect.getsource(rc)
    assert "text(" not in source
    assert "execute(" not in source


# ═════════════════════════════════════════════════════════════════════════════
# CA10 — Lecture seule et délai maximal
# ═════════════════════════════════════════════════════════════════════════════
def test_us096_ca10_ecriture_refusee_pendant_une_agregation(potager):
    """CA10 — l'accès utilisé pour ces agrégations est en lecture seule."""
    from sqlalchemy import text as _text

    with pytest.raises(EcritureInterditeError):
        with catalogue_sql.garde_lecture_seule(potager):
            potager.execute(_text("DELETE FROM evenements WHERE potager_id = 1"))


def test_us096_ca10_delai_maximal_impose(potager):
    """CA10 — un délai maximal est imposé à chaque requête ; budget nul =
    interruption dès la première instruction."""
    with pytest.raises(DelaiRequeteDepasseError):
        with catalogue_sql.garde_lecture_seule(potager, budget_ms=-1):
            potager.query(Evenement).filter(Evenement.potager_id == 1).all()


def test_us096_ca10_garde_retiree_apres_usage(potager):
    """CA10 — le contrôle ne pèse que sur les agrégations : une écriture
    ordinaire reste possible après coup."""
    with catalogue_sql.garde_lecture_seule(potager):
        potager.query(Evenement).filter(Evenement.potager_id == 1).count()
    potager.add(_evenement(date=datetime(ANNEE, 8, 2), type_action="arrosage",
                           culture="carotte", potager_id=1))
    potager.commit()


# ═════════════════════════════════════════════════════════════════════════════
# CA11 — Le filtre potager_id est appliqué par construction
# ═════════════════════════════════════════════════════════════════════════════
def test_us096_ca11_requete_sans_filtre_refusee_a_l_execution(potager):
    """CA11 — une agrégation du catalogue qui ne porte pas `potager_id` est
    refusée à l'exécution, pas seulement signalée en revue de code."""

    def _agregation_fautive(db, ctx):
        return db.query(Evenement).all()

    catalogue_sql._CATALOGUE["_test_sans_filtre"] = _agregation_fautive
    try:
        with pytest.raises(RequeteNonIsoleeError):
            catalogue_sql.executer("_test_sans_filtre", potager, CTX)
    finally:
        catalogue_sql._CATALOGUE.pop("_test_sans_filtre", None)


def test_us096_ca11_absence_de_potager_courant_refusee(potager):
    """CA11 — sans tenant courant, l'agrégation est refusée avant la base."""
    sans_potager = TenantContext(user_id=1, potager_id=None, role="owner")
    with pytest.raises(RequeteNonIsoleeError):
        catalogue_sql.executer("pepiniere", potager, sans_potager)


# ═════════════════════════════════════════════════════════════════════════════
# CA12 — Test d'isolation dédié : sortir du potager courant est impossible
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def potager_voisin(potager):
    """Un second potager, avec des chiffres volontairement remarquables."""
    autre = Parcelle(nom="SUD", nom_normalise="sud", potager_id=2, actif=True, est_pepiniere=False)
    potager.add(autre)
    potager.commit()
    potager.add_all([
        _evenement(date=datetime(ANNEE, 5, 1), type_action="plantation", culture="courgette",
                   quantite=999, unite="plants", potager_id=2, parcelle_id=autre.id),
        _evenement(date=datetime(ANNEE, 7, 4), type_action="recolte", culture="courgette",
                   quantite=777, unite="kg", potager_id=2),
    ])
    potager.commit()
    return potager


@pytest.mark.parametrize("question", [
    "et dans les autres jardins, ça donne quoi ?",
    "compare avec le potager de Marc",
    "combien de courgettes récoltées cet été dans tous les potagers ?",
    "il me reste combien de courgettes chez les autres ?",
    "qu'est-ce qu'il y a dans la parcelle SUD ?",
])
def test_us096_ca12_aucune_donnee_d_un_autre_potager(potager_voisin, question):
    """CA12 + Gherkin — questions formulées pour sortir du potager courant :
    aucune n'obtient une seule donnée du potager voisin."""
    reponse = rc.repondre_chiffre(CTX, question, db=potager_voisin)
    texte = "" if reponse is None else reponse.texte
    assert "999" not in texte
    assert "777" not in texte
    assert "SUD" not in texte


def test_us096_ca12_chaque_potager_voit_ses_propres_chiffres(potager_voisin):
    """CA12 — l'isolation n'est pas un blocage : le potager voisin, lui, obtient
    bien SES chiffres pour la même question."""
    question = "combien de courgettes récoltées cet été ?"
    chez_moi = rc.repondre_chiffre(CTX, question, db=potager_voisin)
    chez_voisin = rc.repondre_chiffre(CTX_VOISIN, question, db=potager_voisin)
    assert "3.7 kg" in chez_moi.texte
    assert "777 kg" in chez_voisin.texte


# ═════════════════════════════════════════════════════════════════════════════
# Cas limites — extraction déterministe des paramètres
# ═════════════════════════════════════════════════════════════════════════════
def test_us096_periode_absente_ne_restreint_rien(potager):
    """Une question sans repère temporel porte sur tout l'historique, et le dit."""
    reponse = rc.repondre_chiffre(CTX, "combien de courgettes ai-je récolté ?", db=potager)
    assert "au total" in reponse.texte


def test_us096_periode_hors_recolte_repond_vide_sans_zero(potager):
    """Une période sans récolte n'invente pas un zéro (CA7 appliqué à la période)."""
    reponse = rc.repondre_chiffre(CTX, "combien de courgettes récoltées en janvier ?", db=potager)
    assert reponse.present is False
    assert "en janvier" in reponse.texte


def test_us096_question_vide_ou_muette_ne_leve_pas(potager):
    """Une entrée vide ne doit provoquer ni exception, ni réponse fabriquée."""
    assert rc.repondre_chiffre(CTX, "", db=potager) is None
    assert rc.repondre_chiffre(CTX, "   ", db=potager) is None


def test_us096_famille_reconnue_sans_culture_nest_pas_servie(potager):
    """Une famille reconnue dont la culture manque n'est pas servie
    approximativement : la cascade reprend la main."""
    assert rc.repondre_chiffre(CTX, "il me reste combien de trucs ?", db=potager) is None


def test_us096_erreur_d_agregation_ne_casse_pas_la_cascade(potager, monkeypatch):
    """Robustesse — l'étage 1 accélère la cascade, il ne l'interrompt jamais."""
    def _explose(*args, **kwargs):
        raise RuntimeError("base indisponible")

    monkeypatch.setattr(rc, "_extraire_parametres", _explose)
    assert rc.repondre_chiffre(CTX, "combien de courgettes récoltées ?", db=potager) is None


def test_us096_valeurs_markdown_echappees(potager):
    """Invariant projet — une valeur venue de la base est échappée avant d'entrer
    dans une sortie Markdown du bot."""
    potager.add(CultureConfig(nom="mais_doux", type_organe_recolte="végétatif", potager_id=None))
    potager.add(_evenement(date=datetime(ANNEE, 5, 3), type_action="plantation",
                           culture="mais_doux", quantite=6, unite="plants", potager_id=1))
    potager.commit()
    reponse = rc.repondre_chiffre(CTX, "il me reste combien de mais_doux ?", db=potager)
    assert "mais\\_doux" in reponse.texte


# ═════════════════════════════════════════════════════════════════════════════
# Détection de période — déterministe, sans interprétation hasardeuse
# ═════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("question,libelle,annee_attendue", [
    ("combien de courgettes récoltées en 2024 ?", "en 2024", 2024),
    ("combien de courgettes récoltées l'an dernier ?", "l'an dernier", ANNEE - 1),
    ("combien de courgettes récoltées ce printemps ?", "ce printemps", ANNEE),
    ("combien de courgettes récoltées cet automne ?", "cet automne", ANNEE),
    ("combien de courgettes récoltées cet hiver ?", "cet hiver", ANNEE),
    ("combien de courgettes récoltées ce mois-ci ?", "ce mois-ci", ANNEE),
    ("combien de courgettes récoltées en juillet ?", "en juillet", ANNEE),
    ("combien de courgettes récoltées cette année ?", "cette année", ANNEE),
])
def test_us096_periodes_reconnues(question, libelle, annee_attendue):
    """La fenêtre annoncée dans la réponse est celle qui a été interrogée —
    un libellé faux serait un chiffre juste sur la mauvaise période."""
    from datetime import date

    periode = rc._detecter_periode(rc._normaliser(question), date(ANNEE, 8, 26))
    assert periode.libelle == libelle
    assert periode.annee == annee_attendue
    assert periode.debut is not None and periode.fin is not None


def test_us096_periode_non_reconnue_ne_devine_rien():
    """Une formulation temporelle inconnue ne restreint rien plutôt que de
    risquer un chiffre juste sur une période devinée."""
    from datetime import date

    periode = rc._detecter_periode(rc._normaliser("combien la saison passee ?"), date(ANNEE, 8, 26))
    assert periode.debut is None and periode.fin is None and periode.libelle == "au total"


def test_us096_refus_de_garde_rend_la_main_sans_erreur(potager, monkeypatch):
    """Un refus de garde-fou n'est jamais présenté au jardinier : il est
    journalisé et la question poursuit la cascade."""
    def _refuser(*args, **kwargs):
        raise RequeteNonIsoleeError("filtre absent")

    monkeypatch.setattr(catalogue_sql, "executer", _refuser)
    assert rc.repondre_chiffre(CTX, "il me reste combien de carottes ?", db=potager) is None


# ═════════════════════════════════════════════════════════════════════════════
# Essais en conditions réelles du 26/08/2026 — non-régression
# -----------------------------------------------------------------------------
# Trois défauts qu'aucun test ne voyait, tous invisibles en session partagée :
# le refus de garde sur la pépinière (chargement paresseux d'une parcelle), les
# deux familles « toutes cultures » manquantes, et l'aiguillage payant de ces
# questions par le routeur.
# ═════════════════════════════════════════════════════════════════════════════
def test_us096_pepiniere_en_session_fraiche(potager, test_engine):
    """Régression — un semis rattaché à une parcelle pépinière déclenchait un
    chargement paresseux `SELECT … FROM parcelles WHERE id = ?` sans filtre de
    potager, que le garde refusait : la pépinière ne répondait jamais en
    production, alors que le test passait grâce à la table d'identité de la
    session déjà peuplée par la fixture."""
    from sqlalchemy.orm import sessionmaker

    serre = Parcelle(nom="Serre", nom_normalise="serre", potager_id=1,
                     actif=True, est_pepiniere=True)
    potager.add(serre)
    potager.commit()
    potager.add(_evenement(date=datetime(ANNEE, 3, 4), type_action="semis", culture="haricot",
                           quantite=40, unite="graines", nb_graines_semees=40,
                           potager_id=1, parcelle_id=serre.id))
    potager.commit()

    session_neuve = sessionmaker(bind=test_engine)()
    try:
        reponse = rc.repondre_chiffre(CTX, "qu'est-ce qu'il y a en pépinière ?", db=session_neuve)
    finally:
        session_neuve.close()

    assert reponse is not None and reponse.present is True
    assert "haricot" in reponse.texte and "Serre" not in reponse.texte


def test_us096_rendement_de_la_saison_sans_culture(potager):
    """Régression — « quel est le rendement de la saison ? » ne nomme aucune
    culture : la famille par culture ne pouvait pas la servir, et la question
    partait au modèle."""
    reponse = rc.repondre_chiffre(CTX, "quel est le rendement de la saison ?", db=potager)
    assert reponse is not None and reponse.famille == "rendement_global"
    assert "cette saison" in reponse.texte
    assert "5.6 kg" in reponse.texte          # 3,7 kg courgette + 1,9 kg haricot


def test_us096_stock_global_sans_culture(potager):
    """Régression — « quel est mon stock ? » porte sur tout le potager."""
    reponse = rc.repondre_chiffre(CTX, "quel est mon stock ?", db=potager)
    assert reponse is not None and reponse.famille == "stock_global"
    # [CA3] Chaque ligne dit l'état juste selon le type d'organe.
    assert "28 plants restants" in reponse.texte      # carotte, végétative
    assert "30 plants en place" in reponse.texte      # haricot, reproductrice


def test_us096_famille_par_culture_prioritaire_sur_la_variante_globale(potager):
    """Une question qui nomme une culture reste servie par la famille précise,
    jamais par la variante « toutes cultures »."""
    reponse = rc.repondre_chiffre(CTX, "quel est le rendement de mes haricots ?", db=potager)
    assert reponse.famille == "rendement_saison"


@pytest.mark.parametrize("question", [
    "qu'est-ce qu'il y a en pépinière ?",
    "quel est le rendement de la saison ?",
    "quel est mon stock ?",
    "combien de pieds de haricot ?",
    "où en sont mes haricots ?",
    "qu'est-ce qu'il y a dans la parcelle NORD ?",
])
def test_us096_ca6_aiguillage_gratuit_des_questions_chiffrees(question):
    """CA6 — ces questions doivent être aiguillées par une RÈGLE : une
    classification payée par le modèle, suivie d'un étage hybride payant,
    annulerait le gain que cette US mesure."""
    from llm import routeur

    assert routeur._regle_par_mots_cles(question) == routeur.NATURE_QUESTION_DATA


def test_us096_derniere_occurrence_sans_culture_dit_juste(potager):
    """Régression — sans culture nommée, l'absence ne doit pas se dire
    « aucun arrosage de cette culture »."""
    reponse = rc.repondre_chiffre(CTX, "quand ai-je arrosé ?", db=potager)
    assert reponse.texte == "Je n'ai aucun arrosage enregistré."


# ═════════════════════════════════════════════════════════════════════════════
# Résolution de parcelle — le jardinier ne dit jamais le nom exact
# -----------------------------------------------------------------------------
# Constaté sur la base de dev le 26/08/2026 : les parcelles s'appellent
# « test-planche-nord », le jardinier demande « la parcelle nord ». Chercher le
# nom complet dans la phrase ne trouvait rien, et toutes les questions de
# parcelle partaient au modèle.
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def parcelles_nommees(potager):
    """Des noms composés, comme en base réelle."""
    for nom in ("test-planche-nord", "test-planche-sud", "test-potager-centre"):
        potager.add(Parcelle(
            nom=nom,
            nom_normalise=nom.replace("-", ""),
            potager_id=1, actif=True, est_pepiniere=False,
        ))
    potager.commit()
    return potager


@pytest.mark.parametrize("question,attendu", [
    # « nord » désigne exactement la parcelle NORD de la fixture : la
    # correspondance exacte l'emporte sur la sous-chaîne de test-planche-nord.
    ("qu'est ce qu'il y a dans la parcelle nord ?", "NORD"),
    ("qu'est-ce qu'il y a dans la planche sud ?", "test-planche-sud"),
    ("qu'est-ce qu'il y a dans la parcelle test-planche-nord ?", "test-planche-nord"),
    ("qu'y a t il sur la parcelle centre ?", "test-potager-centre"),
])
def test_us096_parcelle_resolue_par_designateur(parcelles_nommees, question, attendu):
    """Le mot qui suit « parcelle » / « planche » est résolu vers le nom réel,
    par le même triptyque que `utils/parcelles.resolve_parcelle`."""
    params = rc._extraire_parametres(parcelles_nommees, CTX, question)
    assert params.parcelle == attendu


def test_us096_parcelle_ambigue_nest_jamais_devinee(parcelles_nommees):
    """« la parcelle test » désigne trois parcelles : aucune n'est choisie au
    hasard. Une réponse exacte sur la mauvaise parcelle serait pire qu'une
    non-réponse."""
    params = rc._extraire_parametres(parcelles_nommees, CTX, "qu'est ce qu'il y a dans la parcelle test ?")
    assert params.parcelle is None
    assert rc.repondre_chiffre(CTX, "qu'est ce qu'il y a dans la parcelle test ?", db=parcelles_nommees) is None


def test_us096_parcelle_inconnue_rend_la_main(parcelles_nommees):
    """Une parcelle qui n'existe pas ne produit pas de réponse fabriquée."""
    params = rc._extraire_parametres(parcelles_nommees, CTX, "qu'est ce qu'il y a dans la parcelle ouest ?")
    assert params.parcelle is None


# ═════════════════════════════════════════════════════════════════════════════
# Parcelles libres
# ═════════════════════════════════════════════════════════════════════════════
def test_us096_parcelles_libres_listees(parcelles_nommees):
    """Les parcelles sans culture en place sont comptées et nommées ; NORD, qui
    porte des cultures, n'y figure pas."""
    reponse = rc.repondre_chiffre(CTX, "j'ai combien de parcelle vide ?", db=parcelles_nommees)
    assert reponse is not None and reponse.famille == "parcelles_libres"
    assert "3 parcelle(s) libre(s) sur 4" in reponse.texte
    assert "test-planche-nord" in reponse.texte
    # NORD porte des cultures en place : elle n'est pas libre. Le test vise la
    # ligne de liste, pas le nom contenu dans « test-planche-nord ».
    assert "  • NORD" not in reponse.texte


def test_us096_aucune_parcelle_libre_est_une_reponse(potager):
    """CA7 — « aucune parcelle libre » est un chiffre, pas une absence de
    donnée : la cascade ne doit pas remonter pour aller inventer mieux."""
    reponse = rc.repondre_chiffre(CTX, "j'ai combien de parcelle vide ?", db=potager)
    assert reponse.present is True
    assert reponse.texte == "Aucune parcelle libre : tes 1 parcelles sont toutes occupées."


def test_us096_pepiniere_exclue_des_parcelles_libres(potager):
    """Une serre n'est pas une place libre pour la prochaine culture."""
    potager.add(Parcelle(nom="Serre", nom_normalise="serre", potager_id=1,
                         actif=True, est_pepiniere=True))
    potager.commit()
    agregat = catalogue_sql.executer("parcelles_libres", potager, CTX)
    assert agregat["total"] == 1          # NORD seule, la serre est hors compte


# ═════════════════════════════════════════════════════════════════════════════
# Unités incompatibles — le chiffre du web, mais son unité nommée
# ═════════════════════════════════════════════════════════════════════════════
def test_us096_unite_de_recolte_nommee(potager):
    """Quand le pool « pièces » n'a pas l'unité du stock (5 m² semés, 15 pieds
    récoltés — cas US-037/CA2), le gabarit nomme l'unité de la récolte. Le
    chiffre reste celui de /stats : c'est la lisibilité qu'on corrige, pas la
    valeur (CA4)."""
    potager.add_all([
        _evenement(date=datetime(ANNEE, 3, 1), type_action="plantation", culture="carotte",
                   quantite=5, unite="m²", potager_id=1),
    ])
    potager.commit()
    reponse = rc.repondre_chiffre(CTX, "il me reste combien de carottes ?", db=potager)
    assert "récolté 12 plants" in reponse.texte


# ═════════════════════════════════════════════════════════════════════════════
# Listes longues — ce que le jardinier voit vs ce qui descend au modèle
# -----------------------------------------------------------------------------
# Constaté le 26/08/2026 : la pépinière annonçait « 27 lot(s) » puis n'en
# listait que 8, sans le dire. L'en-tête et la liste se contredisaient, et le
# jardinier n'avait aucun moyen de savoir que 19 lots manquaient.
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def pepiniere_fournie(potager):
    """Trente lots de semis, comme en base réelle."""
    serre = Parcelle(nom="Serre", nom_normalise="serre", potager_id=1,
                     actif=True, est_pepiniere=True)
    potager.add(serre)
    potager.commit()
    for numero in range(30):
        potager.add(_evenement(
            date=datetime(ANNEE, 3, 1), type_action="semis", culture=f"culture{numero:02d}",
            quantite=20, unite="graines", nb_graines_semees=20,
            potager_id=1, parcelle_id=serre.id,
        ))
    potager.commit()
    return potager


def test_us096_liste_tronquee_annonce_ce_qui_manque(pepiniere_fournie):
    """Le nombre annoncé et la liste ne doivent jamais se contredire en
    silence : la troncature est dite, avec le reste chiffré."""
    reponse = rc.repondre_chiffre(CTX, "qu'est-ce qu'il y a en pépinière ?", db=pepiniere_fournie)
    lignes = reponse.texte.split("\n")

    import re

    annonces = int(re.search(r"(\d+) lot", lignes[0]).group(1))
    assert annonces > rc.MAX_LIGNES_AFFICHEES
    # Le reste annoncé complète exactement la liste affichée : en-tête et liste
    # se recoupent, au lieu de se contredire.
    reste = int(re.search(r"et (\d+) autre", lignes[-1]).group(1))
    assert reste == annonces - rc.MAX_LIGNES_AFFICHEES
    assert len(lignes) == 1 + rc.MAX_LIGNES_AFFICHEES + 1


def test_us096_liste_complete_nannonce_aucun_reste(potager):
    """À l'inverse, une liste complète ne doit pas suggérer qu'il en manque."""
    reponse = rc.repondre_chiffre(CTX, "qu'est-ce qu'il y a dans la parcelle NORD ?", db=potager)
    assert "… et" not in reponse.texte


def test_us096_message_telegram_sous_la_limite(pepiniere_fournie):
    """Le plafond d'affichage existe pour une seule raison : un message
    Telegram ne dépasse pas 4 096 caractères."""
    reponse = rc.repondre_chiffre(CTX, "qu'est-ce qu'il y a en pépinière ?", db=pepiniere_fournie)
    assert len(reponse.texte) < 4096


def test_us096_ca5_resume_plus_court_que_l_affichage(pepiniere_fournie):
    """CA5 — le résumé qui descend au modèle est plafonné bien plus bas que
    l'affichage : deux publics, deux plafonds. Le jardinier n'est pas amputé
    pour un budget de jetons qui ne le concerne pas."""
    reponse = rc.repondre_chiffre(CTX, "qu'est-ce qu'il y a en pépinière ?", db=pepiniere_fournie)

    assert len(reponse.resume) < len(reponse.texte)
    assert len(reponse.resume.split("\n")) <= rc.MAX_LIGNES_RESUME + 2
    assert len(reponse.resume) < 1500          # ~1 000 jetons, très largement


# ═════════════════════════════════════════════════════════════════════════════
# Formulations réelles — le catalogue reconnaît, le routeur ne devine plus
# -----------------------------------------------------------------------------
# Essais du 26/08/2026, deux échecs distincts pour une même cause de fond :
#   • « sur MA parcelle nord » : le routeur n'avait pas la préposition dans sa
#     liste → classification payée, puis raisonnement payé, alors que le
#     gabarit avait déjà répondu gratuitement.
#   • « u'est ce qu'il y a… » (le q manquant à la frappe) : le catalogue exigeait
#     la tournure exacte → l'agent SQL a servi un « Top cultures » hors sujet.
# Deux listes de motifs qui divergent : le routeur interroge désormais le
# catalogue, et le catalogue s'appuie sur la parcelle résolue, pas la grammaire.
# ═════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("question", [
    "qu'est ce qu'il y a sur ma parcelle nord ?",
    "u'est ce qu'il y a dans la parcelle nord ?",     # typo de frappe
    "qu'est ce que j'ai en parcelle nord ?",
    "ma parcelle nord",                                # dictée elliptique
    "contenu de la parcelle nord",
])
def test_us096_occupation_reconnue_quelle_que_soit_la_tournure(potager, question):
    """La question est identifiée par la parcelle résolue, pas par une tournure
    interrogative exacte — aucune liste littérale ne rattraperait toutes les
    formes que produisent la dictée et la frappe au pouce."""
    assert rc.reconnait_famille(CTX, question, db=potager) == "occupation_parcelle"


@pytest.mark.parametrize("question", [
    "pourquoi ma parcelle nord est envahie de limaces ?",
    "que dois-je planter sur ma parcelle NORD ?",
    "comment amender la parcelle NORD ?",
    "que faire de ma parcelle NORD à ton avis ?",
])
def test_us096_savoir_sur_une_parcelle_rend_la_main(potager, question):
    """Une famille large doit savoir se disqualifier : une question de savoir ou
    de conseil qui nomme une parcelle n'attend pas un inventaire de cultures."""
    assert rc.reconnait_famille(CTX, question, db=potager) is None


def test_us096_famille_precise_prioritaire_sur_occupation(potager):
    """« quand ai-je semé dans la parcelle NORD ? » nomme une parcelle, mais
    demande une date : la famille précise passe avant le filet."""
    assert rc.reconnait_famille(CTX, "quand ai-je semé dans la parcelle NORD ?",
                                db=potager) == "derniere_occurrence"


def test_us096_routeur_classe_par_le_catalogue_sans_modele(session_applicative):
    """Le routeur n'entretient plus sa propre liste de motifs pour les questions
    chiffrées : il demande au catalogue. Une formulation qu'aucun mot-clé ne
    prévoit est donc aiguillée par une RÈGLE, à zéro jeton."""
    from llm import routeur

    routeur.vider_cache()
    question = "qu'est ce qu'il y a sur ma parcelle NORD ?"
    assert routeur._regle_par_mots_cles(question) is None   # aucun mot-clé ne matche

    decision = routeur.classer_demande(question, CTX)
    assert decision.nature == routeur.NATURE_QUESTION_DATA
    assert decision.origine == routeur.ORIGINE_REGLE        # jamais l'appel modèle


def test_us096_reconnaissance_nexecute_aucune_agregation(potager, monkeypatch):
    """Reconnaître n'est pas répondre : la reconnaissance ne doit déclencher
    aucune agrégation — sans quoi le routeur paierait deux fois le calcul."""
    def _interdit(*args, **kwargs):
        raise AssertionError("une agrégation a été exécutée pendant la reconnaissance")

    monkeypatch.setattr(catalogue_sql, "executer", _interdit)
    assert rc.reconnait_famille(CTX, "qu'est-ce qu'il y a dans la parcelle NORD ?",
                                db=potager) == "occupation_parcelle"

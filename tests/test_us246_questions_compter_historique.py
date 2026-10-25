"""
tests/test_us246_questions_compter_historique.py
[US-246] Compter mes gestes et retrouver l'historique d'un type de geste

Potager de référence (`tools.couverture_gabarits`) complété, ici, de gestes datés
RELATIVEMENT à aujourd'hui : « ce mois-ci » ne doit pas dépendre du jour du test.
"""
import re
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app.services import reponses_chiffrees as rc
from app.services.context import TenantContext
from database.models import Evenement
from tools import couverture_gabarits as cg

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
CTX_VIDE = TenantContext(user_id=9, potager_id=9, role="owner")

AUJOURDHUI = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
IL_Y_A_40_JOURS = AUJOURDHUI - timedelta(days=40)


def _evt(**champs) -> Evenement:
    return Evenement(potager_id=1, **champs)


@pytest.fixture
def potager(test_db):
    cg.construire_potager_de_reference(test_db)
    test_db.add_all(
        # 4 arrosages de tomate aujourd'hui, 2 il y a 40 jours : seuls les 4 sont « de ce mois-ci ».
        [_evt(date=AUJOURDHUI, type_action="arrosage", culture="tomate") for _ in range(4)]
        + [_evt(date=IL_Y_A_40_JOURS, type_action="arrosage", culture="tomate") for _ in range(2)]
        + [_evt(date=AUJOURDHUI, type_action="arrosage", culture="haricot") for _ in range(3)]
        # Deux traitements au purin d'ortie.
        + [_evt(date=AUJOURDHUI - timedelta(days=jours), type_action="traitement", culture="tomate",
                traitement="purin d'ortie") for jours in (1, 3)]
        # Trois saisies de perte, 5 plants au total.
        + [_evt(date=AUJOURDHUI - timedelta(days=jours), type_action="perte", culture="carotte",
                quantite=quantite, unite="plants") for jours, quantite in ((1, 2), (2, 1), (4, 2))]
        # Treize arrosages de courgette : au-delà du plafond de l'historique.
        + [_evt(date=AUJOURDHUI - timedelta(days=jours), type_action="arrosage", culture="courgette")
           for jours in range(13)]
    )
    test_db.commit()
    with patch("llm.passerelle.appeler_chat", side_effect=AssertionError("appel modèle interdit")):
        yield test_db


def _repondre(potager, question, ctx=CTX):
    reponse = rc.repondre_chiffre(ctx, question, db=potager)
    assert reponse is not None, f"aucune famille pour : {question}"
    return reponse


def test_us246_ca1_le_nombre_d_arrosages_de_la_culture_sur_la_periode(potager):
    reponse = _repondre(potager, "combien de fois j'ai arrosé les tomates ce mois-ci")
    assert reponse.famille == "nombre_occurrences"
    assert reponse.texte == "4 arrosages de tomate ce mois-ci."


@pytest.mark.parametrize("question", [
    "combien d'arrosages ce mois-ci ?", "nombre d'arrosages ce mois-ci",
])
def test_us246_ca1_sans_culture_tous_les_arrosages_du_mois(potager, question):
    reponse = _repondre(potager, question)
    assert reponse.famille == "nombre_occurrences"
    assert re.fullmatch(r"\d+ arrosages ce mois-ci, toutes cultures confondues\.", reponse.texte), reponse.texte
    assert int(reponse.texte.split()[0]) >= 7, "au moins les 4 de tomate et les 3 de haricot"


def test_us246_ca1_la_periode_citee_restreint_le_compte(potager):
    reponse = _repondre(potager, "combien de fois j'ai arrosé les tomates avant-hier ?")
    assert reponse.texte == "Je n'ai aucun arrosage de tomate enregistré avant-hier."


def test_us246_ca2_sans_periode_c_est_la_saison_et_la_reponse_le_dit(potager):
    reponse = _repondre(potager, "combien de fois j'ai arrosé les haricots ?")
    assert reponse.texte == "3 arrosages de haricot cette saison."


def test_us246_ca3_les_traitements_avec_date_et_produit(potager):
    reponse = _repondre(potager, "quels traitements ai-je faits sur les tomates ?")
    assert reponse.famille == "historique_action"
    assert reponse.texte.startswith("2 traitements de tomate")
    assert "produit : purin d'ortie" in reponse.texte
    premiere, seconde = [ligne for ligne in reponse.texte.split("\n") if "•" in ligne]
    assert (AUJOURDHUI - timedelta(days=1)).strftime("%d/%m/%Y") in premiere, "la plus récente d'abord"
    assert (AUJOURDHUI - timedelta(days=3)).strftime("%d/%m/%Y") in seconde


def test_us246_ca3_la_liste_est_plafonnee_et_le_reste_annonce(potager):
    reponse = _repondre(potager, "quels arrosages j'ai faits sur les courgettes ?")
    assert reponse.famille == "historique_action"
    assert reponse.texte.startswith("13 arrosages de courgette")
    assert reponse.texte.count("•") == rc.LIMITE_HISTORIQUE_GESTE
    assert "et 3 autre(s)" in reponse.texte


def test_us246_ca4_une_perte_donne_aussi_le_total_de_pieds(potager):
    reponse = _repondre(potager, "combien de pertes de carottes ?")
    assert reponse.famille == "nombre_occurrences"
    assert reponse.texte.startswith("3 pertes de carotte cette saison.")
    assert "Au total : 5 plants perdu(s)." in reponse.texte


def test_us246_ca4_l_historique_des_pertes_donne_le_total(potager):
    texte = _repondre(potager, "quelles pertes j'ai eues sur les carottes ?").texte
    assert "2 plants" in texte and "Au total : 5 perdu(s)." in texte


def test_us246_ca5_les_gestes_du_referentiel_et_leurs_synonymes(potager):
    assert _repondre(potager, "combien de désherbages ce mois-ci ?").texte == (
        "Je n'ai aucun désherbage enregistré ce mois-ci, toutes cultures confondues.")
    assert _repondre(potager, "combien de pulvérisations sur les tomates ?").texte == (
        "2 traitements de tomate cette saison.")


def test_us246_ca6_zero_occurrence_est_une_reponse(potager):
    reponse = _repondre(potager, "combien d'arrosages de fraise ?")
    assert reponse.famille == "nombre_occurrences"
    assert reponse.texte == "Je n'ai aucun arrosage de fraise enregistré cette saison."
    assert reponse.present is True, "zéro est une réponse, pas une remontée vers le modèle"


def test_us246_ca6_un_historique_vide_est_une_reponse(potager):
    reponse = _repondre(potager, "quels traitements ai-je faits sur les haricots ?")
    assert "aucun traitement de haricot" in reponse.texte
    assert reponse.present is True


def test_us246_ca7_la_derniere_occurrence_reste_servie_comme_avant(potager):
    reponse = _repondre(potager, "quand ai-je arrosé les tomates pour la dernière fois ?")
    assert reponse.famille == "derniere_occurrence"


@pytest.mark.parametrize("question", [
    "comment arroser les tomates ?",
    "combien de fois faut-il arroser les tomates ?",
    "quelles variétés de tomate planter ?",
    "combien d'arrosages sur la parcelle nord ?",
])
def test_us246_une_question_de_savoir_ou_de_parcelle_n_est_pas_comptee(potager, question):
    reponse = rc.repondre_chiffre(CTX, question, db=potager)
    assert reponse is None or reponse.famille not in ("nombre_occurrences", "historique_action")


def test_us246_ca8_limite_au_potager_actif(potager):
    assert _repondre(potager, "combien d'arrosages de tomate ce mois-ci ?", CTX_VIDE).texte == (
        "Je n'ai aucun arrosage de tomate enregistré ce mois-ci."
    )


def test_us246_le_cache_rejoue_l_aiguillage_et_derive_la_periode_de_la_phrase(potager):
    reponse = _repondre(potager, "combien de fois j'ai arrosé les tomates ce mois-ci")
    rejouee = rc.servir_aiguillage(CTX, reponse.aiguillage, "combien de fois j'ai arrosé les tomates hier ?", db=potager)
    assert rejouee is not None
    assert rejouee.texte == "Je n'ai aucun arrosage de tomate enregistré hier."


def test_us246_ca8_les_questions_sont_au_corpus_et_bien_servies(potager):
    familles = ("nombre_occurrences", "historique_action")
    corpus = [ligne for ligne in cg.lire_corpus() if ligne["attendu"] in familles]
    assert len(corpus) >= 8
    assert all(r.issue == cg.BIEN for r in cg.rejouer(potager, CTX, corpus))


def test_us246_une_culture_inconnue_n_est_pas_comptee_toutes_cultures_confondues(potager):
    """« combien de physalis ai-je récolté » nomme une culture que le potager ne connaît pas :
    le motif s'ancre sur le nom du geste, il ne sert pas un total qui ne répond pas à la question."""
    reponse = rc.repondre_chiffre(CTX, "combien de physalis ai-je récolté cette saison ?", db=potager)
    assert reponse is None or reponse.famille != "nombre_occurrences"

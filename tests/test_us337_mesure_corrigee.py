"""[US-337] Corrections de la mesure après la relecture humaine du 26/11/2026 (SYNTHESE.md) : le juge voit les résultats
des outils, et le code relève les affirmations sans lecture, les dates fausses et le « semer ou planter ? » reposé."""
from datetime import date

import pytest

from tools.jeu_evaluation import controles, juge, jeu as j
from tools.jeu_evaluation.trace import AppelTrace, TraceCas, TraceTour

JOUR = date(2026, 11, 23)


def _noter(texte, appels=(), jardinier="qu'est-ce qu'il me reste ?"):
    trace = TraceCas("X", "m", 1, tours=[TraceTour(rang=1, jardinier=jardinier, texte=texte, appels=list(appels))])
    notes = controles.Notes()
    controles.controler_affirmations(trace, notes)
    controles.controler_dates(trace, notes, jour=JOUR)
    controles.controler_chiffres(trace, notes)
    controles.controler_intention(j.charger().filtrer(cas=["B05-F1"]).cas[0], trace, notes)
    return notes


@pytest.mark.parametrize("texte, appels", [
    ("Tu n'as rien en stock.", [AppelTrace("consulter_donnees", resultat='{"donnees": null, "disponible": false}')]),
    ("Aucun semis en pépinière ce mois-ci.", [AppelTrace("que_semer_ce_mois", resultat="{}")]),
    ("Pas de risque de gel annoncé.", [AppelTrace("meteo", resultat='{"disponible": false}')]),
    ("Les causes possibles : carence en azote.", []),
    ("Évite le fenouil près des tomates.", []),
    ("Gelées dimanche 26.", []),
])
def test_une_affirmation_sans_lecture_est_inventee(texte, appels):
    assert _noter(texte, appels).rien_d_invente is False


def test_une_temperature_negative_se_source_avec_son_signe():
    meteo = AppelTrace("voir_meteo", resultat='{"min": 2}')
    assert _noter("Il fera -2°C.", [meteo]).rien_d_invente is False
    assert _noter("Il fera -2°C.", [AppelTrace("voir_meteo", resultat='{"min": -2}')]).rien_d_invente is True


@pytest.mark.parametrize("texte, appels", [
    ("Tu n'as rien en stock.", [AppelTrace("voir_stock", resultat='{"total_varietes": 0}')]),
    ("Redis ta phrase avec la quantité (2 kg, 15 plants, 1 sachet…).", []),
    ("Jeudi 26, rien à signaler.", []),
])
def test_ce_qui_est_lu_ou_donne_en_exemple_n_est_pas_invente(texte, appels):
    assert _noter(texte, appels).rien_d_invente is True


def test_semer_ou_planter_apres_semer_est_une_question_reposee():
    question = "Tu veux semer ou planter tes radis ?"
    assert _noter(question, jardinier="c'est le moment de semer des radis ?").intention_gardee is False
    assert _noter(question, jardinier="c'est le moment pour les radis ?").intention_gardee is True


def test_le_juge_lit_le_resultat_de_chaque_outil():
    cas = j.charger().filtrer(cas=["B16-F1"]).cas[0]
    appel = AppelTrace("consulter_donnees", resultat='{"disponible": false}')
    trace = TraceCas(cas.id, "m", 1, tours=[TraceTour(rang=1, jardinier="stock ?", texte="rien", appels=[appel])])
    assert 'rendu : {"disponible": false}' in juge.transcrire(cas, trace, JOUR)

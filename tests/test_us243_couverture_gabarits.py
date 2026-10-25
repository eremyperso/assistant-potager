"""
tests/test_us243_couverture_gabarits.py
[US-243] Mesurer la couverture des gabarits sur les questions portant sur mes données

Le corpus `tests/corpus/us243_couverture_gabarits.csv` associe chaque question à
la famille de gabarit qui DOIT la servir (ou à « aucune » : savoir, calendrier,
hors périmètre). Le rejeu mesure le CHOIX de la famille — sans appel modèle et
sans PostgreSQL — et sépare trois issues : bien servie, non servie, mal servie.
"""
from unittest.mock import patch

import pytest

from app.services import reponses_chiffrees as rc
from app.services.context import TenantContext
from tools import couverture_gabarits as cg

CTX = TenantContext(user_id=1, potager_id=1, role="owner")

# [CA5] Taux minimal de questions bien servies parmi celles qui attendent une
# famille. Relevé à 1,00 par US-249 : toutes les questions « a_couvrir » sont servies.
# Jamais à baisser.
SEUIL_BIEN_SERVIES = 1.00


@pytest.fixture
def corpus():
    return cg.lire_corpus()


@pytest.fixture
def resultats(test_db, corpus):
    cg.construire_potager_de_reference(test_db)
    with patch("llm.passerelle.appeler_chat", side_effect=AssertionError("appel modèle interdit")):
        return cg.rejouer(test_db, CTX, corpus)


def test_us243_ca1_corpus_d_au_moins_60_questions_rattachees_a_une_famille(corpus):
    assert len(corpus) >= 60
    familles = {ligne["attendu"] for ligne in corpus} - {cg.AUCUNE}
    existantes = {famille.nom for famille in rc.FAMILLES}
    couvertes = {ligne["attendu"] for ligne in corpus if ligne["statut"] == cg.STATUT_COUVERT} - {cg.AUCUNE}
    assert couvertes <= existantes, f"famille inconnue au catalogue : {couvertes - existantes}"
    assert familles, "au moins une famille attendue"


def test_us243_ca2_le_corpus_porte_des_pieges_et_des_formulations_orales(corpus):
    pieges = [ligne for ligne in corpus if ligne["attendu"] == cg.AUCUNE]
    assert len(pieges) >= 8
    assert any("comment" in ligne["question"] for ligne in pieges), "question de savoir citant une parcelle"
    sans_ponctuation = [ligne for ligne in corpus if not ligne["question"].strip().endswith("?")]
    assert len(sans_ponctuation) >= 5, "dictée vocale : pas de point d'interrogation"
    assert any(ligne["question"] == "combien de parcelle ?" for ligne in corpus), "faute courante du relevé"


def test_us243_ca3_trois_taux_sont_calcules(resultats):
    t = cg.taux(resultats)
    assert set(t) == {cg.BIEN, cg.NON, cg.MAL}
    assert all(0.0 <= v <= 1.0 for v in t.values())
    assert t[cg.BIEN] + t[cg.NON] == pytest.approx(1.0)


def test_us243_ca4_aucune_question_n_est_servie_par_une_autre_famille(resultats):
    mal = [(r.question, r.attendu, r.obtenu) for r in resultats if r.issue == cg.MAL]
    assert not mal, f"questions mal servies : {mal}"


def test_us243_ca5_le_taux_de_questions_bien_servies_ne_recule_pas(resultats):
    assert cg.taux(resultats)[cg.BIEN] >= SEUIL_BIEN_SERVIES


def test_us243_ca5_les_questions_couvertes_sont_toutes_bien_servies(resultats):
    ratees = [r.question for r in resultats if r.statut == cg.STATUT_COUVERT and r.issue != cg.BIEN]
    assert not ratees, f"questions déclarées couvertes mais non servies : {ratees}"


def test_us243_ca5_une_regression_serait_detectee():
    """Le seuil mord : un catalogue qui ne sert plus rien tombe sous le seuil."""
    faux = [cg.Resultat("q", "stock_global", cg.STATUT_COUVERT, None, cg.NON)] * 5
    assert cg.taux(faux)[cg.BIEN] < SEUIL_BIEN_SERVIES


def test_us243_ca4_une_famille_inattendue_est_comptee_mal_servie():
    resultats = [cg.Resultat("q", "stock_global", cg.STATUT_COUVERT, "pepiniere", cg.MAL)]
    assert cg.taux(resultats)[cg.MAL] == 1.0


def test_us243_ca6_le_rejeu_ne_fait_aucun_appel_modele(test_db, corpus):
    cg.construire_potager_de_reference(test_db)
    with patch("llm.passerelle.appeler_chat", side_effect=AssertionError("appel modèle")) as modele:
        cg.rejouer(test_db, CTX, corpus)
    modele.assert_not_called()


def test_us243_ca7_une_commande_donne_les_taux_et_les_questions_non_servies(capsys, tmp_path):
    code = cg.main([])
    sortie = capsys.readouterr().out
    assert code == 0
    assert "bien servies" in sortie and "non servies" in sortie and "mal servies" in sortie
    assert "NON SERVIES" not in sortie  # US-249 : plus aucune question du corpus ne descend au modèle

    corpus = tmp_path / "corpus.csv"
    corpus.write_text(
        "question,attendu,statut\nquel est le cours de la tomate en bourse ?,prix,a_couvrir\n",
        encoding="utf-8",
    )
    cg.main(["--corpus", str(corpus)])
    assert "NON SERVIES" in capsys.readouterr().out

"""
tests/test_us245_questions_cultures_varietes.py
[US-245] Lister les cultures en place et les variétés d'une culture

Potager de référence : tomate (12 « Cœur de bœuf » + 6 sans variété), haricot
(30 pieds, cueillis deux fois), courgette (4), carotte entièrement récoltée,
fraise encore en pépinière.
"""
from unittest.mock import patch

import pytest

from app.services import reponses_chiffrees as rc
from app.services.context import TenantContext
from tools import couverture_gabarits as cg

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
CTX_VIDE = TenantContext(user_id=9, potager_id=9, role="owner")


@pytest.fixture
def potager(test_db):
    cg.construire_potager_de_reference(test_db)
    with patch("llm.passerelle.appeler_chat", side_effect=AssertionError("appel modèle interdit")):
        yield test_db


def _repondre(potager, question, ctx=CTX):
    reponse = rc.repondre_chiffre(ctx, question, db=potager)
    assert reponse is not None, f"aucune famille pour : {question}"
    return reponse


@pytest.mark.parametrize("question", [
    "quelles cultures j'ai en place ?", "qu'est-ce que je cultive en ce moment ?",
    "liste mes cultures", "quelles sont mes cultures",
])
def test_us245_ca1_les_cultures_en_place_avec_pieds_et_parcelles(potager, question):
    reponse = _repondre(potager, question)
    assert reponse.famille == "cultures_en_place"
    assert "Cultures en place (3)" in reponse.texte
    assert "tomate : 18 plants — NORD" in reponse.texte
    assert "haricot : 30 plants — NORD" in reponse.texte


def test_us245_ca2_la_pepiniere_est_presentee_a_part(potager):
    texte = _repondre(potager, "quelles cultures j'ai en place ?").texte
    avant, apres = texte.split("En pépinière")
    assert "fraise" not in avant and "fraise" in apres


def test_us245_ca3_vegetative_recoltee_absente_reproductrice_cueillie_presente(potager):
    texte = _repondre(potager, "quelles cultures j'ai en place ?").texte
    assert "carotte" not in texte, "culture végétative entièrement récoltée"
    assert "haricot" in texte, "la cueillette ne retire pas le pied"


def test_us245_ca4_les_varietes_avec_pieds_en_place(potager):
    reponse = _repondre(potager, "quelles variétés de tomate j'ai ?")
    assert reponse.famille == "varietes_culture"
    assert "2 variété(s) de tomate" in reponse.texte
    assert "Cœur de bœuf : 12 plants en place" in reponse.texte
    assert "Variété non précisée : 6 plants en place" in reponse.texte


def test_us245_ca5_le_nombre_de_varietes_distinctes(potager):
    reponse = _repondre(potager, "combien de variétés de tomates ?")
    assert reponse.famille == "varietes_culture"
    assert reponse.texte == "2 variété(s) de tomate."


def test_us245_ca6_aucune_culture_en_place_est_une_reponse(test_db):
    reponse = rc.repondre_chiffre(CTX_VIDE, "qu'est-ce que je cultive en ce moment ?", db=test_db)
    assert reponse is not None and reponse.famille == "cultures_en_place"
    assert reponse.texte == "Aucune culture en place pour l'instant."
    assert reponse.present is True


def test_us245_ca7_les_chiffres_sont_ceux_de_l_ecran_de_stock(potager):
    from utils import stock
    stocks = stock.calcul_stock_cultures(potager, potager_id=1)
    attendu = {c: s.stock_plants for c, s in stocks.items() if s.stock_plants > 0}
    texte = _repondre(potager, "quelles cultures j'ai en place ?").texte
    for culture, pieds in attendu.items():
        assert f"{culture} : {pieds:g} plants" in texte


@pytest.mark.parametrize("question", [
    "quelles variétés de tomate planter ?",
    "quelles variétés de tomate résistent au mildiou ?",
    "quelles variétés de tomate existent ?",
])
def test_us245_une_question_de_conseil_sur_les_varietes_n_est_pas_servie(potager, question):
    reponse = rc.repondre_chiffre(CTX, question, db=potager)
    assert reponse is None or reponse.famille != "varietes_culture"


def test_us245_ca8_limite_au_potager_actif_et_au_corpus(potager):
    assert "tomate" not in _repondre(potager, "liste mes cultures", CTX_VIDE).texte
    familles = ("cultures_en_place", "varietes_culture")
    corpus = [ligne for ligne in cg.lire_corpus() if ligne["attendu"] in familles]
    assert len(corpus) >= 8
    assert all(r.issue == cg.BIEN for r in cg.rejouer(potager, CTX, corpus))

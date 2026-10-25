"""
tests/test_us249_questions_potager_actif.py
[US-249] Dire quel est mon potager actif

Le jardinier (id 1) a accès à « Maison » (actif) et « Jardin partagé » ; « Potager du
voisin » appartient à un autre compte. Aucun appel modèle n'est toléré.
"""
from unittest.mock import patch

import pytest

from app.services import reponses_chiffrees as rc
from app.services.context import TenantContext
from database.models import Potager, PotagerMembre, User
from tools import couverture_gabarits as cg

CTX = TenantContext(user_id=1, potager_id=1, role="owner")


@pytest.fixture
def potager(test_db):
    cg.construire_potager_de_reference(test_db)
    with patch("llm.passerelle.appeler_chat", side_effect=AssertionError("appel modèle interdit")):
        yield test_db


def _repondre(db, question, ctx=CTX):
    reponse = rc.repondre_chiffre(ctx, question, db=db)
    assert reponse is not None, f"aucune famille pour : {question}"
    return reponse


@pytest.mark.parametrize("question", [
    "quel est mon potager actif ?",
    "sur quel potager je suis ?",
    "comment s'appelle mon potager ?",
    "quel est mon potager ?",
])
def test_us249_ca1_le_nom_du_potager_actif(potager, question):
    reponse = _repondre(potager, question)
    assert reponse.famille == "potager_actif"
    assert "« Maison »" in reponse.texte


def test_us249_ca2_plusieurs_potagers_les_cite_et_rappelle_la_commande(potager):
    texte = _repondre(potager, "quel est mon potager actif ?").texte
    assert "Jardin partagé" in texte and "/potager" in texte


def test_us249_ca2_un_seul_potager_ne_propose_pas_de_changer(test_db):
    test_db.add_all([User(id=1), Potager(id=1, nom="Maison", proprietaire_id=1)])
    test_db.flush()
    test_db.add(PotagerMembre(user_id=1, potager_id=1, role="owner"))
    test_db.commit()
    texte = _repondre(test_db, "quel est mon potager actif ?").texte
    assert "Maison" in texte and "/potager" not in texte


def test_us249_ca3_le_nombre_de_potagers_et_leurs_noms(potager):
    texte = _repondre(potager, "combien de potagers j'ai ?").texte
    assert "2 potager" in texte and "Maison (actif)" in texte and "Jardin partagé" in texte


def test_us249_ca4_jamais_le_potager_d_un_autre_compte(potager):
    for question in ("quel est mon potager actif ?", "combien de potagers j'ai ?"):
        assert "voisin" not in _repondre(potager, question).texte.lower()


def test_us249_ca4_un_potager_actif_dont_on_n_est_pas_membre_n_est_pas_cite(potager):
    intrus = TenantContext(user_id=1, potager_id=3, role="owner")
    reponse = _repondre(potager, "quel est mon potager actif ?", ctx=intrus)
    assert reponse.present is False
    assert "voisin" not in reponse.texte.lower()


def test_us249_ca5_une_question_de_conseil_n_est_pas_captee(potager):
    assert rc.repondre_chiffre(CTX, "comment créer un deuxième potager ?", db=potager) is None
    assert rc.repondre_chiffre(CTX, "quels conseils pour mon potager actif ?", db=potager) is None

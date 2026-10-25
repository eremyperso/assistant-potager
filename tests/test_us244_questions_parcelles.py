"""
tests/test_us244_questions_parcelles.py
[US-244] Répondre aux questions sur mes parcelles et leurs caractéristiques

Potager de référence (`tools.couverture_gabarits`) : NORD renseignée (sol argileux,
6 rangs, 12 m, exposition sud, plein soleil, paillée, des cultures), SUD vierge,
Serre pépinière chaude sous serre.
"""
from unittest.mock import patch

import pytest

from app.services import reponses_chiffrees as rc
from app.services.context import TenantContext
from database.models import Parcelle
from tools import couverture_gabarits as cg

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
CTX_AUTRE = TenantContext(user_id=2, potager_id=2, role="owner")


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
    "combien de parcelles ?", "affiche mes parcelles", "quelles sont mes parcelles ?",
])
def test_us244_ca1_nombre_et_liste_des_parcelles(potager, question):
    reponse = _repondre(potager, question)
    assert reponse.famille == "liste_parcelles"
    assert "3 parcelle(s)" in reponse.texte
    assert "Serre (pépinière)" in reponse.texte


def test_us244_ca2_les_pepinieres_avec_leur_type(potager):
    reponse = _repondre(potager, "quelles sont mes pépinières ?")
    assert reponse.famille == "parcelles_filtrees"
    assert "1 parcelle(s) en pépinière sur 3" in reponse.texte
    assert "Serre (pépinière chaude)" in reponse.texte
    assert "NORD" not in reponse.texte


@pytest.mark.parametrize("question,attendu", [
    ("quel est le type de sol de la parcelle NORD ?", "Argileux"),
    ("combien de rangs a la parcelle NORD ?", "6 rang(s)"),
    ("quelle est la longueur de la parcelle nord", "12 m"),
    ("quelle est l'exposition de la parcelle NORD ?", "sud"),
    ("quel ensoleillement pour la parcelle nord", "plein soleil"),
    ("la parcelle nord est-elle paillée ?", "paillée"),
    ("la serre est-elle une pépinière ?", "pépinière chaude"),
])
def test_us244_ca3_la_valeur_enregistree_et_elle_seule(potager, question, attendu):
    reponse = _repondre(potager, question)
    assert reponse.famille == "attributs_parcelle"
    assert attendu in reponse.texte
    assert "tomate" not in reponse.texte and "haricot" not in reponse.texte, "pas la liste des cultures"


def test_us244_ca3_une_seule_caracteristique_par_reponse(potager):
    texte = _repondre(potager, "combien de rangs a la parcelle NORD ?").texte
    assert "sol" not in texte.lower() and "Argileux" not in texte


def test_us244_ca4_une_caracteristique_absente_est_dite_avec_la_commande(potager):
    reponse = _repondre(potager, "quel sol a la parcelle sud")
    assert "non renseigné" in reponse.texte
    assert "/parcelle modifier SUD type_sol=" in reponse.texte
    assert reponse.present is True, "« non renseigné » est une réponse, pas une remontée"


def test_us244_ca4_aucune_valeur_par_defaut_inventee(potager):
    assert "non renseigné" in _repondre(potager, "la parcelle sud est-elle sous abri ?").texte
    assert "non renseigné" in _repondre(potager, "la parcelle sud est-elle paillée ?").texte


def test_us244_ca5_les_parcelles_qui_portent_la_caracteristique(potager):
    paillees = _repondre(potager, "quelles parcelles sont paillées ?")
    assert paillees.famille == "parcelles_filtrees"
    assert "1 parcelle(s) paillée(s) sur 3" in paillees.texte and "NORD" in paillees.texte
    assert "2 parcelle(s) sans cette information" in paillees.texte, "l'inconnu est compté à part"
    abritees = _repondre(potager, "quelles parcelles sont sous abri ?")
    assert "Serre" in abritees.texte and "NORD" not in abritees.texte.split("\n")[1]


def test_us244_ca5_aucune_parcelle_ne_porte_la_caracteristique_est_une_reponse(potager):
    reponse = _repondre(potager, "quelles parcelles sont à l'ombre ?")
    assert "Aucune parcelle à l'ombre sur tes 3 parcelles" in reponse.texte
    assert reponse.present is True


def test_us244_ca6_l_occupation_d_une_parcelle_liste_toujours_les_cultures(potager):
    reponse = _repondre(potager, "qu'y a-t-il sur la parcelle NORD ?")
    assert reponse.famille == "occupation_parcelle"
    assert "tomate" in reponse.texte


def test_us244_ca6_une_culture_nommee_n_est_pas_une_caracteristique_de_parcelle(potager):
    reponse = rc.repondre_chiffre(CTX, "combien de rangs de carottes sur la parcelle nord", db=potager)
    assert reponse is None or reponse.famille != "attributs_parcelle"


@pytest.mark.parametrize("question", [
    "comment amender le sol de la parcelle nord ?",
    "comment pailler la parcelle nord ?",
    "qu'est-ce que le paillage ?",
    "quelles plantes aiment l'ombre ?",
])
def test_us244_ca7_une_question_de_savoir_n_est_pas_servie(potager, question):
    reponse = rc.repondre_chiffre(CTX, question, db=potager)
    assert reponse is None or reponse.famille not in ("attributs_parcelle", "parcelles_filtrees")


def test_us244_ca8_limite_au_potager_actif(potager):
    potager.add(Parcelle(nom="AUTRE", nom_normalise="autre", potager_id=2, actif=True,
                         est_pepiniere=False, type_sol="Sableux"))
    potager.commit()
    assert "AUTRE" not in _repondre(potager, "affiche mes parcelles").texte
    assert "Sableux" in _repondre(potager, "quel est le type de sol de la parcelle autre ?", CTX_AUTRE).texte
    assert rc.repondre_chiffre(CTX, "quel est le type de sol de la parcelle autre ?", db=potager) is None


def test_us244_aiguillage_rejoue_sans_perdre_la_caracteristique_demandee(potager):
    """Le cache rejoue l'aiguillage : la caractéristique est redérivée de la phrase."""
    reponse = _repondre(potager, "combien de rangs a la parcelle NORD ?")
    rejouee = rc.servir_aiguillage(CTX, reponse.aiguillage, "quelle est l'exposition de la parcelle nord", db=potager)
    assert rejouee is not None and "sud" in rejouee.texte and "rang" not in rejouee.texte


def test_us244_ca9_les_questions_sont_au_corpus_et_bien_servies(potager):
    familles = ("liste_parcelles", "attributs_parcelle", "parcelles_filtrees")
    corpus = [ligne for ligne in cg.lire_corpus() if ligne["attendu"] in familles]
    assert len(corpus) >= 15
    assert all(r.issue == cg.BIEN for r in cg.rejouer(potager, CTX, corpus))

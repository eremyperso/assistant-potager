"""
tests/test_us247_questions_journal_periode.py
[US-247] Restituer ce que j'ai fait sur une période

Les gestes sont datés relativement à aujourd'hui, le jour du test ne doit pas
changer le résultat.
"""
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest

from app.services import reponses_chiffrees as rc
from app.services.context import TenantContext
from database.models import Evenement, Parcelle
from tools import couverture_gabarits as cg

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
CTX_VIDE = TenantContext(user_id=9, potager_id=9, role="owner")

AUJOURDHUI = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
HIER = AUJOURDHUI - timedelta(days=1)


@pytest.fixture
def potager(test_db):
    cg.construire_potager_de_reference(test_db)
    sud = test_db.query(Parcelle).filter_by(nom="SUD").one()
    test_db.add_all([
        Evenement(potager_id=1, date=HIER, type_action="arrosage", culture="tomate"),
        Evenement(potager_id=1, date=HIER, type_action="recolte", culture="courgette",
                  quantite=2, unite="kg", parcelle_id=sud.id),
    ])
    test_db.commit()
    with patch("llm.passerelle.appeler_chat", side_effect=AssertionError("appel modèle interdit")):
        yield test_db


def _repondre(potager, question, ctx=CTX):
    reponse = rc.repondre_chiffre(ctx, question, db=potager)
    assert reponse is not None, f"aucune famille pour : {question}"
    return reponse


@pytest.mark.parametrize("question", [
    "qu'est-ce que j'ai fait hier", "qu'ai-je fait hier ?", "qu'est ce que j'ai fait hier ?",
])
def test_us247_ca1_ca2_les_gestes_d_hier_avec_culture_quantite_et_parcelle(potager, question):
    reponse = _repondre(potager, question)
    assert reponse.famille == "journal_periode"
    assert "(2 geste(s))" in reponse.texte and "hier" in reponse.texte
    assert "arrosage de tomate" in reponse.texte
    assert "récolte de courgette — 2 kg — parcelle SUD" in reponse.texte


def test_us247_ca1_les_gestes_sont_regroupes_par_jour(potager):
    potager.add(Evenement(potager_id=1, date=AUJOURDHUI - timedelta(days=3), type_action="paillage", culture="tomate"))
    potager.commit()
    texte = _repondre(potager, "qu'est-ce que j'ai fait ces derniers jours ?").texte if False else \
        _repondre(potager, "qu'est-ce que j'ai fait ?").texte
    entetes = [ligne for ligne in texte.split("\n") if ligne.endswith(":") and ligne[:2].isdigit()]
    assert entetes == [f"{(AUJOURDHUI - timedelta(days=3)):%d/%m/%Y} :", f"{HIER:%d/%m/%Y} :"]
    assert texte.index("paillage") < texte.index("arrosage"), "du plus ancien au plus récent"


@pytest.mark.parametrize("question,libelle", [
    ("qu'est-ce que j'ai fait cette semaine ?", "cette semaine"),
    ("qu'ai-je fait la semaine dernière ?", "la semaine dernière"),
    ("qu'est-ce que j'ai fait aujourd'hui ?", "aujourd'hui"),
])
def test_us247_ca1_les_periodes_reconnues(potager, question, libelle):
    reponse = _repondre(potager, question)
    assert reponse.famille == "journal_periode"
    assert libelle in reponse.texte


def test_us247_ca1_cette_semaine_va_du_lundi_a_aujourd_hui():
    jeudi = date(2026, 10, 22)
    periode = rc._detecter_periode("qu ai je fait cette semaine", jeudi)
    assert (periode.debut, periode.fin) == (date(2026, 10, 19), jeudi)
    derniere = rc._detecter_periode("qu ai je fait la semaine derniere", jeudi)
    assert (derniere.debut, derniere.fin) == (date(2026, 10, 12), date(2026, 10, 18))


def test_us247_ca1_une_date_citee(potager):
    reponse = _repondre(potager, "qu'est-ce que j'ai fait le 4 mars ?")
    assert reponse.famille == "journal_periode"
    assert "le 4 mars" in reponse.texte and "semis de fraise" in reponse.texte


def test_us247_ca3_au_dela_du_plafond_la_reponse_resume_par_geste(potager):
    potager.add_all(
        [Evenement(potager_id=1, date=AUJOURDHUI, type_action="arrosage", culture="haricot") for _ in range(10)]
        + [Evenement(potager_id=1, date=AUJOURDHUI, type_action="desherbage", culture="haricot") for _ in range(4)]
    )
    potager.commit()
    texte = _repondre(potager, "qu'est-ce que j'ai fait ?").texte
    assert "•" not in texte, "plus de lignes au-delà du plafond"
    assert "11 arrosages, 4 désherbages, 1 récolte" in texte
    assert "historique de l'application" in texte


def test_us247_ca4_sans_periode_les_7_derniers_jours_et_la_reponse_le_dit(potager):
    reponse = _repondre(potager, "qu'est-ce que j'ai fait ?")
    assert "ces 7 derniers jours" in reponse.texte
    assert "arrosage de tomate" in reponse.texte


def test_us247_ca4_un_geste_plus_ancien_que_7_jours_n_est_pas_cite(potager):
    potager.add(Evenement(potager_id=1, date=AUJOURDHUI - timedelta(days=9), type_action="taille", culture="tomate"))
    potager.commit()
    assert "taille" not in _repondre(potager, "qu'est-ce que j'ai fait ?").texte


def test_us247_ca5_une_periode_sans_geste_est_une_reponse(potager):
    reponse = _repondre(potager, "qu'est-ce que j'ai fait le 2 janvier ?")
    assert reponse.texte == "Rien d'enregistré le 2 janvier."
    assert reponse.present is True


def test_us247_ca5_une_periode_sans_geste_hier(test_db):
    cg.construire_potager_de_reference(test_db)
    assert _repondre(test_db, "qu'ai-je fait hier ?").texte == "Rien d'enregistré hier."


def test_us247_une_culture_citee_filtre_le_journal(potager):
    texte = _repondre(potager, "qu'ai-je fait sur les tomates ?").texte
    assert "arrosage de tomate" in texte and "courgette" not in texte


def test_us247_ca6_le_rappel_de_note_reste_servi_par_les_notes(potager):
    assert _repondre(potager, "qu'avais-je noté sur les haricots ?").famille == "notes_culture"


@pytest.mark.parametrize("question", [
    "qu'est-ce que je dois faire cette semaine ?",
    "que faire au potager cette semaine ?",
    "comment savoir ce que j'ai fait ?",
])
def test_us247_une_question_de_conseil_n_est_pas_servie_par_le_journal(potager, question):
    reponse = rc.repondre_chiffre(CTX, question, db=potager)
    assert reponse is None or reponse.famille != "journal_periode"


def test_us247_ca7_limite_au_potager_actif(potager):
    assert _repondre(potager, "qu'ai-je fait hier ?", CTX_VIDE).texte == "Rien d'enregistré hier."


def test_us247_le_cache_redérive_la_periode_de_la_phrase(potager):
    reponse = _repondre(potager, "qu'ai-je fait hier ?")
    rejouee = rc.servir_aiguillage(CTX, reponse.aiguillage, "qu'ai-je fait aujourd'hui ?", db=potager)
    assert rejouee is not None and rejouee.texte == "Rien d'enregistré aujourd'hui."


def test_us247_ca7_les_questions_sont_au_corpus_et_bien_servies(potager):
    corpus = [ligne for ligne in cg.lire_corpus() if ligne["attendu"] == "journal_periode"]
    assert len(corpus) >= 5
    assert all(r.issue == cg.BIEN for r in cg.rejouer(potager, CTX, corpus))

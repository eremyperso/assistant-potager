"""
tests/test_us248_questions_classement_recoltes.py
[US-248] Classer mes récoltes et donner le total de la saison

Potager de référence (`tools.couverture_gabarits`) : haricot 1,4 kg, courgette 2,5 kg,
carotte 12 plants. Aucun appel modèle n'est toléré.
"""
from datetime import datetime
from unittest.mock import patch

import pytest

from app.services import reponses_chiffrees as rc
from app.services.context import TenantContext
from database.models import Evenement
from tools import couverture_gabarits as cg
from utils import stock as _stock

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
ANNEE = datetime.now().year


@pytest.fixture
def potager(test_db):
    cg.construire_potager_de_reference(test_db)
    with patch("llm.passerelle.appeler_chat", side_effect=AssertionError("appel modèle interdit")):
        yield test_db


def _repondre(db, question, ctx=CTX):
    reponse = rc.repondre_chiffre(ctx, question, db=db)
    assert reponse is not None, f"aucune famille pour : {question}"
    return reponse


def test_us248_ca1_le_classement_va_du_plus_au_moins_productif(potager):
    reponse = _repondre(potager, "quelle culture a le plus produit cette année ?")
    assert reponse.famille == "classement_recoltes"
    assert reponse.texte.index("courgette") < reponse.texte.index("haricot")
    assert "2.5 kg" in reponse.texte or "2,5 kg" in reponse.texte


@pytest.mark.parametrize("question", [
    "quelle est ma meilleure récolte ?",
    "quelle culture a le plus produit ?",
    "c'est quoi ma meilleure récolte ?",
])
def test_us248_ca1_les_formulations_du_classement_sont_reconnues(potager, question):
    assert _repondre(potager, question).famille == "classement_recoltes"


def test_us248_ca1_la_saison_en_cours_est_dite_par_defaut(potager):
    assert "cette saison" in _repondre(potager, "quelle est ma meilleure récolte ?").texte


def test_us248_ca2_le_total_toutes_cultures_confondues(potager):
    texte = _repondre(potager, "combien de kg ai-je récoltés cette année ?").texte
    assert "1.4 kg" not in texte and "1,4 kg" not in texte  # un total, pas un détail par culture
    assert "3.9 kg" in texte or "3,9 kg" in texte


def test_us248_ca3_les_pieces_sont_a_part_et_jamais_additionnees(potager):
    classement = _repondre(potager, "quelle culture a le plus produit ?").texte
    total = _repondre(potager, "combien de kg ai-je récoltés cette année ?").texte
    for texte in (classement, total):
        assert "À part" in texte
        assert "carotte" in texte and "12 plants" in texte
    assert "15.9" not in total and "15,9" not in total


def test_us248_ca3_des_bottes_gardent_leur_unite(potager):
    potager.add(Evenement(potager_id=1, date=datetime(ANNEE, 6, 1), type_action="recolte",
                          culture="radis", quantite=5, unite="bottes"))
    potager.commit()
    texte = _repondre(potager, "quelle est ma meilleure récolte ?").texte
    assert "radis" in texte and "5 bottes" in texte


def test_us248_ca4_les_cueillettes_d_une_reproductrice_se_cumulent(potager):
    # haricot : 800 g + 600 g du potager de référence = 1,4 kg, quel que soit le nombre de pieds (30).
    texte = _repondre(potager, "quelle culture a le plus produit ?").texte
    assert "1.4 kg" in texte or "1,4 kg" in texte


def test_us248_ca5_aucune_recolte_est_une_reponse(test_db):
    with patch("llm.passerelle.appeler_chat", side_effect=AssertionError("appel modèle interdit")):
        reponse = _repondre(test_db, "quelle culture a le plus produit ?")
    assert reponse.present is False
    assert "aucune récolte" in reponse.texte.lower()


def test_us248_ca5_des_pieces_seules_ne_disent_pas_aucune_recolte(test_db):
    test_db.add(Evenement(potager_id=1, date=datetime(ANNEE, 6, 1), type_action="recolte",
                          culture="radis", quantite=5, unite="bottes"))
    test_db.commit()
    texte = _repondre(test_db, "combien de kg ai-je récoltés cette année ?").texte
    assert "aucune récolte pesée" in texte and "5 bottes" in texte


def test_us248_ca6_le_total_est_celui_des_statistiques_du_web(potager):
    web = _stock.calcul_rendement_mensuel(potager, ANNEE, potager_id=1)
    agregat = rc.catalogue_sql.executer(
        "classement_recoltes", potager, CTX, periode=rc._periode_saison(rc.Periode()),
    )
    assert round(agregat["total_g"] / 1000, 2) == web["total_general_kg"]
    assert [(c, round(g / 1000, 2)) for c, g in agregat["cultures"]] == [
        (e["culture"], e["total"]) for e in web["cultures"]
    ]


def test_us248_ca7_limite_au_potager_actif(potager):
    potager.add(Evenement(potager_id=2, date=datetime(ANNEE, 6, 1), type_action="recolte",
                          culture="melon", quantite=40, unite="kg"))
    potager.commit()
    assert "melon" not in _repondre(potager, "quelle culture a le plus produit ?").texte


def test_us248_une_culture_nommee_reste_servie_par_les_familles_existantes(potager):
    assert _repondre(potager, "combien de kg de haricots récoltés cette année").famille == "total_recolte"

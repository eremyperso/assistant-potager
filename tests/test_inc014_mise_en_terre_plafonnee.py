"""
tests/test_inc014_mise_en_terre_plafonnee.py
[INC-014] La mise en terre d'un lot ne dépasse jamais ses plants disponibles : le dépôt
(PWA) tient compte du restant ET des gestes déjà en attente, et la confirmation (bot)
refuse un geste que le lot ne peut plus fournir.
"""
from datetime import datetime

import pytest

from app.services import file_gestes as svc
from app.services.context import TenantContext
from database.models import Evenement, Potager, PotagerMembre, User


@pytest.fixture
def db(test_db, monkeypatch):
    test_db.add(User(id=1, email="camille@potager.test"))
    test_db.flush()
    test_db.add(Potager(id=1, nom="Jardin A", proprietaire_id=1))
    test_db.flush()
    test_db.add(PotagerMembre(user_id=1, potager_id=1, role="owner"))
    test_db.commit()
    monkeypatch.setattr(svc, "SessionLocal", lambda: test_db)
    monkeypatch.setattr(test_db, "close", lambda: None)
    return test_db


@pytest.fixture
def ctx():
    return TenantContext(user_id=1, potager_id=1, role="owner")


@pytest.fixture
def lot(db):
    """Un lot de poireau : 50 graines semées, 50 plants en godet."""
    semis = Evenement(
        type_action="semis", culture="poireau", variete="bleu", quantite=50, unite="graines",
        date=datetime(2026, 8, 15), potager_id=1,
    )
    db.add(semis)
    db.commit()
    db.add(Evenement(
        type_action="mise_en_godet", culture="poireau", variete="bleu", nb_plants_godets=50,
        nb_graines_semees=50, origine_graines_id=semis.id, date=datetime(2026, 8, 30), potager_id=1,
    ))
    db.commit()
    return semis


def _planter(db, ctx, lot, quantite):
    return svc.deposer_geste(
        db, ctx, action="plantation", culture="poireau", variete="bleu",
        quantite=quantite, unite="plants", lot_id=lot.id,
    )


def test_inc014_restant_du_lot_lu_comme_la_pepiniere(db, lot):
    assert svc.plants_restants_du_lot(db, 1, lot.id) == 50


def test_inc014_second_depot_de_tout_le_lot_refuse(db, ctx, lot):
    """Le bug d'origine : cliquer deux fois « Mettre en terre » empilait 2 × 50."""
    _planter(db, ctx, lot, 50)
    with pytest.raises(svc.QuantiteSuperieureAuLotError) as e:
        _planter(db, ctx, lot, 50)
    assert e.value.disponibles == 0
    assert e.value.reserves == 50
    assert len(svc.lister_en_attente(db, 1)) == 1


def test_inc014_mises_en_terre_partielles_jusqu_a_epuisement(db, ctx, lot):
    """20 sur une parcelle, 30 sur une autre : le total tient dans le lot."""
    _planter(db, ctx, lot, 20)
    _planter(db, ctx, lot, 30)
    with pytest.raises(svc.QuantiteSuperieureAuLotError):
        _planter(db, ctx, lot, 1)
    assert len(svc.lister_en_attente(db, 1)) == 2


def test_inc014_quantite_superieure_au_disponible_refusee(db, ctx, lot):
    _planter(db, ctx, lot, 20)
    with pytest.raises(svc.QuantiteSuperieureAuLotError) as e:
        _planter(db, ctx, lot, 40)
    assert e.value.disponibles == 30
    assert "30" in str(e.value)


def test_inc014_geste_retire_de_la_file_libere_les_plants(db, ctx, lot):
    premier = _planter(db, ctx, lot, 50)
    svc.abandonner(premier.geste)
    db.commit()
    _planter(db, ctx, lot, 50)   # ne lève plus


def test_inc014_quantite_absente_non_plafonnee_si_le_lot_a_des_plants(db, ctx, lot):
    _planter(db, ctx, lot, None)


def test_inc014_confirmation_refuse_un_geste_que_le_lot_ne_peut_plus_fournir(db, ctx, lot):
    """Cinq gestes déjà en file avant le correctif : après le premier, les autres sont refusés."""
    premier = _planter(db, ctx, lot, 50).geste
    # Le premier est confirmé : la plantation est écrite, le lot est vidé.
    db.add(Evenement(
        type_action="plantation", culture="poireau", variete="bleu", quantite=50, unite="plants",
        source_evenement_ids=str(lot.id), date=datetime(2026, 9, 1), potager_id=1,
    ))
    db.commit()
    assert svc.plants_restants_du_lot(db, 1, lot.id) == 0
    # Un second geste arrivé avant le correctif (injecté tel quel dans la file).
    from database.models import GesteIntention
    from datetime import timedelta
    ancien = GesteIntention(
        code="ancien", user_id=1, potager_id=1, etat=svc.ETAT_EN_ATTENTE,
        geste={"action": "plantation", "culture": "poireau", "quantite": 50, "_lot_id": lot.id},
        cree_le=datetime.utcnow(), expire_le=datetime.utcnow() + timedelta(days=3),
    )
    db.add(ancien)
    db.commit()
    motif = svc.verifier_contexte(db, ancien, 1)
    assert motif and "plus aucun plant" in motif
    assert premier.id != ancien.id


# ── Les autres gestes de lot : perte, repiquage, déplacement, clôture ────────
def _geste(db, ctx, lot, action, quantite=None):
    return svc.deposer_geste(
        db, ctx, action=action, culture="poireau", variete="bleu",
        quantite=quantite, unite="plants" if quantite is not None else None, lot_id=lot.id,
    )


@pytest.mark.parametrize("action", ["perte_godet", "cloture_lot", "deplacement"])
def test_inc014_geste_sans_nombre_ne_s_empile_pas(db, ctx, lot, action):
    """« Déclarer une perte », « Clôturer », « Déplacer » : un seul à la fois par lot."""
    _geste(db, ctx, lot, action)
    with pytest.raises(svc.GesteDeLotDejaEnAttenteError):
        _geste(db, ctx, lot, action)
    assert len(svc.lister_en_attente(db, 1)) == 1


def test_inc014_gestes_de_types_differents_restent_possibles(db, ctx, lot):
    _geste(db, ctx, lot, "perte_godet")
    _geste(db, ctx, lot, "deplacement")
    assert len(svc.lister_en_attente(db, 1)) == 2


def test_inc014_perte_et_plantation_se_partagent_les_memes_godets(db, ctx, lot):
    _geste(db, ctx, lot, "perte_godet", 10)
    with pytest.raises(svc.QuantiteSuperieureAuLotError) as e:
        _planter(db, ctx, lot, 50)
    assert e.value.disponibles == 40
    _planter(db, ctx, lot, 40)


def test_inc014_perte_superieure_au_stock_refusee(db, ctx, lot):
    with pytest.raises(svc.QuantiteSuperieureAuLotError):
        _geste(db, ctx, lot, "perte_godet", 51)


def test_inc014_geste_sans_nombre_bloque_aussi_un_second_avec_nombre(db, ctx, lot):
    _geste(db, ctx, lot, "perte_godet")
    with pytest.raises(svc.GesteDeLotDejaEnAttenteError):
        _geste(db, ctx, lot, "perte_godet", 5)


def test_inc014_repiquage_plafonne_par_les_graines_en_germination(db, ctx):
    semis = Evenement(
        type_action="semis", culture="tomate", quantite=40, unite="graines",
        date=datetime(2026, 8, 1), potager_id=1,
    )
    db.add(semis)
    db.commit()
    svc.deposer_geste(db, ctx, action="mise_en_godet", culture="tomate", quantite=30, lot_id=semis.id)
    with pytest.raises(svc.QuantiteSuperieureAuLotError) as e:
        svc.deposer_geste(db, ctx, action="mise_en_godet", culture="tomate", quantite=30, lot_id=semis.id)
    assert e.value.disponibles == 10
    assert "graine" in str(e.value)


def test_inc014_confirmation_refuse_une_perte_que_le_lot_ne_peut_plus_fournir(db, ctx, lot):
    from datetime import timedelta
    from database.models import GesteIntention
    db.add(Evenement(
        type_action="perte_godet", culture="poireau", variete="bleu", quantite=50, unite="plants",
        origine_graines_id=lot.id, date=datetime(2026, 9, 1), potager_id=1,
    ))
    ancien = GesteIntention(
        code="ancienne-perte", user_id=1, potager_id=1, etat=svc.ETAT_EN_ATTENTE,
        geste={"action": "perte_godet", "culture": "poireau", "quantite": 10, "_lot_id": lot.id},
        cree_le=datetime.utcnow(), expire_le=datetime.utcnow() + timedelta(days=3),
    )
    db.add(ancien)
    db.commit()
    motif = svc.verifier_contexte(db, ancien, 1)
    assert motif and "plus aucun plant" in motif

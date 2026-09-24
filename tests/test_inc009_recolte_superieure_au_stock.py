"""
tests/test_inc009_recolte_superieure_au_stock.py — [INC-009] Le garde-fou de
quantité de `valider_evenement` (`StockInsuffisantError`) couvrait la perte
(jardin, godet) mais pas la récolte : une récolte destructive (culture
végétative, en pièces) pouvait dépasser le stock en place sans être refusée ni
même signalée. Reproduction exacte : « récolte de 50 salades » acceptée alors
que 23 plants seulement étaient en place.

Couvre :
- la récolte destructive (végétatif, en pièces) refusée au-delà du stock
- la même quantité acceptée dans la limite du stock
- la récolte reproductrice (tomate) non soumise au contrôle — le pied reste
- la récolte pesée (kg/g/mg) non soumise au contrôle — ce n'est pas un compte de pieds
- le filtrage par variété
- la correction d'un événement (`corriger_evenement`) soumise au même contrôle
- la non-régression du contrôle existant sur la perte (jardin, godet)
- le message d'erreur (verbe, stock annoncé)
"""
from datetime import datetime

import pytest

from app.services.context import TenantContext
from app.services import evenements as svc_evenements
from app.services.evenements import StockInsuffisantError
from database.models import CultureConfig, Evenement, Parcelle


@pytest.fixture
def ctx():
    return TenantContext(user_id=1, potager_id=1, role="owner")


@pytest.fixture
def db_salade(test_db):
    """[INC-009] Le jeu de test du déclarant : 23 plants de salade en place,
    aucune récolte ni perte préalable."""
    test_db.add(CultureConfig(nom="salade", type_organe_recolte="végétatif"))
    test_db.add(CultureConfig(nom="tomate", type_organe_recolte="reproducteur"))
    test_db.commit()
    test_db.add(Evenement(
        type_action="plantation", culture="salade", quantite=23, unite="plants",
        date=datetime(2026, 9, 1), potager_id=1,
    ))
    test_db.commit()
    return test_db


def _recolter(db, ctx, culture: str, quantite: float, unite: str = "plants", variete=None):
    parsed = {"action": "recolte", "culture": culture, "variete": variete,
              "quantite": quantite, "unite": unite}
    return svc_evenements.creer_evenement_confirme(db, ctx, parsed, "texte", None)


# ── Le scénario rapporté ──────────────────────────────────────────────────────

def test_inc009_recolte_superieure_au_stock_refusee(db_salade, ctx):
    """23 plants en place, récolte de 50 : refusée, rien n'est écrit."""
    with pytest.raises(StockInsuffisantError) as exc:
        _recolter(db_salade, ctx, "salade", 50)
    assert exc.value.stock_disponible == 23
    assert db_salade.query(Evenement).filter_by(type_action="recolte").count() == 0


def test_inc009_message_erreur_annonce_le_verbe_et_le_stock(db_salade, ctx):
    with pytest.raises(StockInsuffisantError) as exc:
        _recolter(db_salade, ctx, "salade", 50)
    message = str(exc.value)
    assert "Récolte de 50" in message
    assert "23 plant" in message


def test_inc009_recolte_dans_la_limite_du_stock_acceptee(db_salade, ctx):
    """23 en place, récolte de 20 : acceptée, l'événement est bien écrit."""
    event = _recolter(db_salade, ctx, "salade", 20)
    assert event.id is not None
    assert event.quantite == 20


def test_inc009_recolte_exactement_le_stock_acceptee(db_salade, ctx):
    """Limite : récolter exactement ce qu'il reste n'est pas un dépassement."""
    event = _recolter(db_salade, ctx, "salade", 23)
    assert event.id is not None


# ── Exclusions volontaires ────────────────────────────────────────────────────

def test_inc009_recolte_reproductrice_non_controlee(db_salade, ctx):
    """Une tomate laisse le pied en place après cueillette (US-036) : la récolte
    n'est jamais soumise à ce contrôle, quelle que soit la quantité plantée."""
    db_salade.add(Evenement(
        type_action="plantation", culture="tomate", quantite=2, unite="plants",
        date=datetime(2026, 9, 1), potager_id=1,
    ))
    db_salade.commit()
    event = _recolter(db_salade, ctx, "tomate", 500)
    assert event.id is not None


def test_inc009_recolte_pesee_non_controlee(db_salade, ctx):
    """Une récolte en kg n'est pas un décompte de pieds : jamais comparée au
    stock de plants, même très supérieure en apparence."""
    event = _recolter(db_salade, ctx, "salade", 500, unite="kg")
    assert event.id is not None


# ── Assiette du contrôle ──────────────────────────────────────────────────────

def test_inc009_filtre_par_variete(db_salade, ctx):
    """Deux variétés distinctes : la récolte d'une ne porte pas sur le stock
    de l'autre."""
    db_salade.add(Evenement(
        type_action="plantation", culture="salade", variete="batavia", quantite=10,
        unite="plants", date=datetime(2026, 9, 1), potager_id=1,
    ))
    db_salade.commit()
    with pytest.raises(StockInsuffisantError) as exc:
        _recolter(db_salade, ctx, "salade", 11, variete="batavia")
    assert exc.value.stock_disponible == 10
    # La ligne "romaine" (23 plants, sans variété précisée) n'est pas concernée.
    event = _recolter(db_salade, ctx, "salade", 10, variete="batavia")
    assert event.id is not None


# ── Correction d'un événement existant ───────────────────────────────────────

def test_inc009_correction_soumise_au_meme_controle(db_salade, ctx):
    """Corriger une récolte déjà enregistrée vers une quantité qui dépasse le
    stock disponible est refusé, comme une création."""
    event = _recolter(db_salade, ctx, "salade", 10)
    with pytest.raises(StockInsuffisantError):
        svc_evenements.corriger_evenement(db_salade, ctx, event.id, {"quantite": 999}, " | corr")


# ── Non-régression : la perte garde son propre contrôle et son propre message ──

def test_inc009_perte_refusee_avec_verbe_perte(db_salade, ctx):
    parsed = {"action": "perte", "culture": "salade", "variete": None,
              "quantite": 50, "unite": "plants"}
    with pytest.raises(StockInsuffisantError) as exc:
        svc_evenements.creer_evenement_confirme(db_salade, ctx, parsed, "texte", None)
    assert "Perte de 50" in str(exc.value)

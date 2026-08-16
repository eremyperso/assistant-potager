"""
tests/test_us041_couche_services.py
------------------------------------
[US-041] Couche services/ partagée bot ⇄ PWA avec contexte tenant.

Couvre :
- CA1/CA2 : TenantContext existe, default_context() renvoie le potager #1
- CA3     : app.services.evenements expose enregistrer/corriger/supprimer/lister
- CA8     : aucun db.query(Evenement|Parcelle|CultureConfig) direct dans bot.py / main.py
- Non-régression fonctionnelle sur les opérations de base (création, correction,
  suppression, historique paginé, stats agrégées) via la couche services.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.services.context import TenantContext, default_context
from app.services import evenements as svc_evenements
from app.services import stats as svc_stats
from database.models import Evenement, Parcelle, CultureConfig

ROOT = Path(__file__).resolve().parent.parent


# ──────────────────────────────────────────────────────────────────────────────
# CA1 / CA2 — TenantContext
# ──────────────────────────────────────────────────────────────────────────────

def test_ca1_tenant_context_existe():
    ctx = TenantContext(user_id=1, potager_id=1, role="owner")
    assert ctx.potager_id == 1
    assert ctx.user_id == 1
    assert ctx.role == "owner"


def test_ca2_default_context_pointe_potager_1():
    ctx = default_context()
    assert ctx.potager_id == 1
    assert ctx.user_id == 1


# ──────────────────────────────────────────────────────────────────────────────
# CA8 — Zéro accès direct db.query(Evenement|Parcelle|CultureConfig) hors services/
# ──────────────────────────────────────────────────────────────────────────────

_DIRECT_QUERY_RE = re.compile(r"\.query\(\s*(Evenement|Parcelle|CultureConfig)\b")
_DIRECT_GET_RE = re.compile(r"db\.get\(\s*(Evenement|Parcelle|CultureConfig)\b")


@pytest.mark.parametrize("filename", ["bot.py", "main.py"])
def test_ca8_aucun_db_query_direct_hors_services(filename):
    source = (ROOT / filename).read_text(encoding="utf-8")
    query_hits = _DIRECT_QUERY_RE.findall(source)
    get_hits = _DIRECT_GET_RE.findall(source)
    assert not query_hits, f"{filename} contient encore des db.query() directs : {query_hits}"
    assert not get_hits, f"{filename} contient encore des db.get() directs : {get_hits}"


def test_ca8_aucune_creation_directe_evenement_hors_services():
    for filename in ("bot.py", "main.py"):
        source = (ROOT / filename).read_text(encoding="utf-8")
        assert "Evenement(" not in source, f"{filename} construit encore un Evenement() directement"


# ──────────────────────────────────────────────────────────────────────────────
# CA3 — CRUD événements via la couche services (non-régression fonctionnelle)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def ctx():
    return default_context()


@pytest.fixture
def parcelle_nord(test_db, ctx):
    p = Parcelle(nom="Nord", nom_normalise="nord", ordre=1, actif=True, potager_id=ctx.potager_id)
    test_db.add(p)
    test_db.commit()
    return p


def test_ca3_enregistrer_evenement_resout_parcelle_et_herite_type_organe(test_db, ctx, parcelle_nord):
    test_db.add(CultureConfig(nom="tomate", type_organe_recolte="reproducteur"))
    # [US-049] "tomate" doit avoir un historique de plantation sur "nord" pour que
    # la récolte passe la validation centrale (culture jamais plantée + cohérence parcelle).
    test_db.add(Evenement(type_action="plantation", culture="tomate", quantite=2, unite="plants",
                           parcelle_id=parcelle_nord.id, potager_id=ctx.potager_id))
    test_db.commit()

    parsed = {"action": "recolte", "culture": "tomate", "quantite": 2, "unite": "kg", "parcelle": "nord"}
    event = svc_evenements.creer_evenement_depuis_parse(test_db, ctx, parsed, "j'ai récolté 2 kg de tomates")

    assert event.id is not None
    assert event.type_action == "recolte"
    assert event.parcelle_id == parcelle_nord.id
    assert event.type_organe_recolte == "reproducteur"


def test_ca3_lister_evenements_pagine_et_filtre(test_db, ctx, parcelle_nord):
    for i in range(3):
        test_db.add(Evenement(type_action="arrosage", culture=None, parcelle_id=parcelle_nord.id, potager_id=ctx.potager_id))
    test_db.add(Evenement(type_action="recolte", culture="tomate", parcelle_id=parcelle_nord.id, potager_id=ctx.potager_id))
    test_db.commit()

    total, events = svc_evenements.lister_evenements(test_db, ctx, limit=2, offset=0)
    assert total == 4
    assert len(events) == 2

    total_filtre, events_filtre = svc_evenements.lister_evenements(test_db, ctx, action="recolte")
    assert total_filtre == 1
    assert events_filtre[0].culture == "tomate"


def test_ca3_corriger_evenement_applique_les_champs_et_trace(test_db, ctx):
    # [US-049] "tomate" doit avoir un historique de plantation pour que la correction
    # (qui revalide l'événement dans son état final) passe la validation centrale.
    test_db.add(Evenement(type_action="plantation", culture="tomate", quantite=2, unite="plants", potager_id=ctx.potager_id))
    ev = Evenement(type_action="recolte", culture="tomate", quantite=2, unite="kg", potager_id=ctx.potager_id)
    test_db.add(ev)
    test_db.commit()

    updated = svc_evenements.corriger_evenement(
        test_db, ctx, ev.id, {"quantite": 3}, " | [CORR] quantite: 2 → 3"
    )
    assert updated.quantite == 3
    assert "[CORR]" in updated.texte_original


def test_ca3_supprimer_evenement(test_db, ctx):
    ev = Evenement(type_action="arrosage", potager_id=ctx.potager_id)
    test_db.add(ev)
    test_db.commit()
    ev_id = ev.id

    assert svc_evenements.supprimer_evenement(test_db, ctx, ev_id) is True
    assert svc_evenements.get_evenement(test_db, ctx, ev_id) is None
    assert svc_evenements.supprimer_evenement(test_db, ctx, ev_id) is False


# ──────────────────────────────────────────────────────────────────────────────
# CA4 — Stats agrégées calculées une seule fois (StatsResult)
# ──────────────────────────────────────────────────────────────────────────────

def test_ca4_calculer_stats_agrege_stock_et_traitements(test_db, ctx, parcelle_nord):
    test_db.add(CultureConfig(nom="tomate", type_organe_recolte="reproducteur"))
    test_db.add(Evenement(type_action="plantation", culture="tomate", quantite=3, unite="plants", parcelle_id=parcelle_nord.id, potager_id=ctx.potager_id))
    test_db.add(Evenement(type_action="traitement", traitement="purin d'ortie", potager_id=ctx.potager_id))
    test_db.commit()

    result = svc_stats.calculer_stats(test_db, ctx)
    assert result.total_evenements == 2
    assert "tomate" in result.stocks
    assert len(result.traitements) == 1

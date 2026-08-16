"""
[US-049] Tests — Validation centrale et non contournable avant toute écriture
d'un Evenement.

CA3 : aucune règle ne dépend du nombre d'items traités dans un même appel
CA4 : reproduction exacte du bug rapporté (phrase multi-culture segmentée par Groq)
CA5 : parcourt toutes les fonctions d'écriture de app/services/evenements.py et
      vérifie qu'aucune ne permet d'écrire une culture jamais plantée — liste
      explicite documentée (cf. notes techniques de l'US) : à compléter si une
      nouvelle fonction d'écriture est ajoutée, pour que l'oubli soit visible en
      revue de code plutôt que silencieux
CA6 : non-régression du comportement utilisateur déjà livré
CA7 : corriger_evenement et deplacer_evenements passent par la même validation
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.context import TenantContext
from app.services import evenements as svc_evenements
from app.services.evenements import CultureInconnueError, ParcelleIncoherenteError
from database.models import Evenement, Parcelle

CULTURE_INCONNUE = "mangue-jamais-plantee"


@pytest.fixture
def ctx():
    return TenantContext(user_id=1, potager_id=1, role="owner")


# ── CA4 — Bug rapporté : phrase multi-culture segmentée par Groq ────────────────

@pytest.mark.asyncio
async def test_ca4_bug_rapporte_phrase_multi_culture_segmentee(test_db):
    """
    "cueilli 2 kilos de cerise, tomates, nord" segmenté par Groq en deux items
    dans la même réponse JSON (culture="cerise" puis culture="tomate"), aucune
    des deux jamais plantée dans le potager → aucun des deux événements écrit.

    Reproduit exactement les logs terrain qui avaient révélé le contournement :
    id=337 (cerise) et id=338 (tomate) tous deux enregistrés sur parcelle=1001
    malgré le garde-fou "culture jamais plantée" déjà en place, parce que ce
    garde-fou était conditionné à len(items) == 1.
    """
    import bot as bot_module

    parcelle_nord = Parcelle(nom="test-planche-nord", nom_normalise="testplanchenord", ordre=1, actif=True)
    test_db.add(parcelle_nord)
    test_db.commit()

    items = [
        {"action": "recolte", "culture": "cerise", "variete": None, "quantite": 2, "unite": "kg", "parcelle": "nord"},
        {"action": "recolte", "culture": "tomate", "variete": None, "quantite": 2, "unite": "kg", "parcelle": "nord"},
    ]

    update = MagicMock()
    update.effective_user.id = 8063902186
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    update.effective_message = update.message

    with (
        patch("bot.parse_commande", return_value=items),
        patch("bot._normalize_items", return_value=items),
        patch("bot.SessionLocal", return_value=test_db),
    ):
        bot_module._ACTION_PENDING.pop(8063902186, None)
        await bot_module._parse_and_save(update, "cueilli 2 kilos de cerise, tomates, nord")

    # Aucun des deux événements ne doit avoir été écrit
    assert test_db.query(Evenement).count() == 0
    assert update.message.reply_text.called
    text_sent = update.message.reply_text.call_args[0][0]
    assert "cerise" in text_sent
    bot_module._ACTION_PENDING.pop(8063902186, None)


# ── CA5 — Toutes les fonctions d'écriture rejettent une culture inconnue ────────

def test_ca5_creer_evenement_depuis_parse_rejette_culture_inconnue(test_db, ctx):
    parsed = {"action": "recolte", "culture": CULTURE_INCONNUE, "quantite": 1, "unite": "kg"}
    with pytest.raises(CultureInconnueError):
        svc_evenements.creer_evenement_depuis_parse(test_db, ctx, parsed, "texte")
    assert test_db.query(Evenement).count() == 0


def test_ca5_creer_evenement_ligne_rejette_culture_inconnue(test_db, ctx):
    parsed = {"action": "recolte", "culture": CULTURE_INCONNUE, "quantite": 1, "unite": "kg"}
    with pytest.raises(CultureInconnueError):
        svc_evenements.creer_evenement_ligne(test_db, ctx, parsed, "texte")
    assert test_db.query(Evenement).count() == 0


def test_ca5_creer_evenement_confirme_rejette_culture_inconnue(test_db, ctx):
    parsed = {"action": "recolte", "culture": CULTURE_INCONNUE, "quantite": 1, "unite": "kg"}
    with pytest.raises(CultureInconnueError):
        svc_evenements.creer_evenement_confirme(test_db, ctx, parsed, "texte", None)
    assert test_db.query(Evenement).count() == 0


def test_ca5_creer_evenement_observation_rejette_culture_inconnue(test_db, ctx):
    fields = {
        "culture": CULTURE_INCONNUE, "variete": None, "parcelle": None,
        "constat": "test", "traitement": None, "duree_minutes": None, "date": None,
    }
    with pytest.raises(CultureInconnueError):
        svc_evenements.creer_evenement_observation(test_db, ctx, fields, "texte", "Test")
    assert test_db.query(Evenement).count() == 0


def test_ca5_creer_evenement_perte_rejette_culture_inconnue(test_db, ctx):
    item = {"action": "perte", "culture": CULTURE_INCONNUE, "quantite": 1, "unite": "plants"}
    with pytest.raises(CultureInconnueError):
        svc_evenements.creer_evenement_perte(test_db, ctx, item, "texte")
    assert test_db.query(Evenement).count() == 0


def test_ca5_corriger_evenement_rejette_culture_inconnue(test_db, ctx):
    """[CA7] Une correction qui ferait pointer un événement existant vers une
    culture jamais plantée doit être refusée, pas seulement les créations."""
    test_db.add(Evenement(type_action="plantation", culture="tomate", quantite=1,
                           unite="plants", potager_id=ctx.potager_id))
    ev = Evenement(type_action="recolte", culture="tomate", quantite=1, unite="kg",
                    potager_id=ctx.potager_id)
    test_db.add(ev)
    test_db.commit()

    with pytest.raises(CultureInconnueError):
        svc_evenements.corriger_evenement(test_db, ctx, ev.id, {"culture": CULTURE_INCONNUE}, " | corr")

    # L'événement original ne doit pas avoir été altéré par la tentative refusée
    test_db.refresh(ev)
    assert ev.culture == "tomate"


def test_ca5_creer_evenement_godet_action_source_jamais_bloquee(test_db, ctx):
    """mise_en_godet est une action source (introduit une nouvelle culture) —
    jamais bloquée, même sur une culture inédite dans le potager."""
    parsed = {"action": "mise_en_godet", "culture": CULTURE_INCONNUE, "quantite": 5, "unite": "graines"}
    event = svc_evenements.creer_evenement_godet(test_db, ctx, parsed, "texte")
    assert event.id is not None
    assert event.culture == CULTURE_INCONNUE


def test_ca5_deplacer_evenements_non_bloque_par_incoherence_parcelle(test_db, ctx):
    """[CA7] deplacer_evenements passe par la validation centrale mais NE DOIT PAS
    être bloquée par la règle d'incohérence culture/parcelle : c'est justement son
    rôle d'établir qu'une culture est désormais localisée sur une nouvelle parcelle."""
    p1 = Parcelle(nom="Ancienne", nom_normalise="ancienne", ordre=1, actif=True, potager_id=ctx.potager_id)
    p2 = Parcelle(nom="Nouvelle", nom_normalise="nouvelle", ordre=2, actif=True, potager_id=ctx.potager_id)
    test_db.add_all([p1, p2])
    test_db.commit()
    test_db.add(Evenement(type_action="plantation", culture="tomate", quantite=1, unite="plants",
                           parcelle_id=p1.id, potager_id=ctx.potager_id))
    test_db.commit()

    nb = svc_evenements.deplacer_evenements(test_db, ctx, "tomate", None, p2.id, "Nouvelle")
    assert nb == 1


# ── CA2/CA6 — Rules réellement appliquées + non-régression ──────────────────────

def test_ca2_incoherence_parcelle_leve_parcelle_incoherente_error(test_db, ctx):
    """Culture existante mais jamais sur CETTE parcelle précise → erreur distincte
    de CultureInconnueError, pour permettre à bot.py une correction assistée plutôt
    qu'un blocage sec (cf. CA6 : comportement déjà livré préservé)."""
    p_ombre    = Parcelle(nom="Ombre", nom_normalise="ombre", ordre=1, actif=True, potager_id=ctx.potager_id)
    p_centrale = Parcelle(nom="Centrale", nom_normalise="centrale", ordre=2, actif=True, potager_id=ctx.potager_id)
    test_db.add_all([p_ombre, p_centrale])
    test_db.commit()
    test_db.add(Evenement(type_action="plantation", culture="tomate", variete="cerise",
                           quantite=1, unite="plants", parcelle_id=p_ombre.id, potager_id=ctx.potager_id))
    test_db.commit()

    with pytest.raises(ParcelleIncoherenteError):
        svc_evenements.valider_evenement(
            test_db, ctx, action="recolte", culture="tomate", variete="cerise", parcelle=p_centrale,
        )


def test_ca6_action_source_jamais_bloquee_sur_nouvelle_culture(test_db, ctx):
    """Un semis sur une culture jamais vue reste possible — c'est l'action qui
    introduit la culture pour la première fois."""
    svc_evenements.valider_evenement(
        test_db, ctx, action="semis", culture=CULTURE_INCONNUE, variete=None, parcelle=None,
    )  # ne doit lever aucune exception

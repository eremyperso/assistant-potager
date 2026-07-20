"""
[fix bug id=351] Un item mise_en_godet dont Groq a renvoyé variete="gourmand" mais
culture=null tombait dans le flux générique de confirmation (_do_save_items →
creer_evenement_confirme) au lieu du chemin dédié (creer_evenement_godet), car
l'interception _GODET_PENDING (bot.py) ne se déclenche que si la variété est
absente. Résultat en production : événement enregistré avec culture=NULL et
parcelle_id=1005 ("serre", choisie via la sélection de parcelle CA8) alors qu'un
godet ne doit jamais être rattaché à une parcelle.

Trois correctifs couverts ici :
1. "mise_en_godet" ajouté à _ACTIONS_PEPINIERE (bot.py) — CA8 ne doit plus jamais
   proposer de parcelle pour cette action.
2. _do_save_items route désormais tout item mise_en_godet vers
   creer_evenement_godet, jamais vers creer_evenement_confirme.
3. valider_evenement rejette une action structurellement liée à une culture
   (semis, plantation, mise_en_godet, recolte, perte, perte_godet, vendu) fournie
   sans culture — CultureManquanteError — sans jamais l'exiger pour les actions
   "zone" (observation, paillage, arrosage...).
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.context import TenantContext
from app.services import evenements as svc_evenements
from app.services.evenements import CultureManquanteError
from database.models import Evenement, Parcelle


@pytest.fixture
def ctx():
    return TenantContext(user_id=1, potager_id=1, role="owner")


# ── Règle "culture obligatoire" ciblée ───────────────────────────────────────

@pytest.mark.parametrize("action", ["semis", "plantation", "mise_en_godet", "recolte", "perte", "perte_godet", "vendu"])
def test_culture_manquante_bloquee_pour_actions_liees_a_une_culture(test_db, ctx, action):
    with pytest.raises(CultureManquanteError):
        svc_evenements.valider_evenement(test_db, ctx, action=action, culture=None, variete=None, parcelle=None)


@pytest.mark.parametrize("action", ["observation", "paillage", "arrosage", "desherbage", "taille", "tuteurage", "fertilisation", "binage"])
def test_culture_optionnelle_preservee_pour_actions_zone(test_db, ctx, action):
    """Non-régression : ces actions restent utilisables sans culture (paillage
    d'une parcelle entière, note météo, désherbage général...)."""
    svc_evenements.valider_evenement(test_db, ctx, action=action, culture=None, variete=None, parcelle=None)  # ne lève rien


def test_creer_evenement_godet_rejette_culture_vide(test_db, ctx):
    """Reproduit le cas exact du bug id=351 : variete="gourmand" présente, culture
    vide — doit être rejeté au lieu d'écrire un godet fantôme."""
    parsed = {"culture": None, "variete": "gourmand", "nb_graines_semees": 3, "nb_plants_godets": 3}
    with pytest.raises(CultureManquanteError):
        svc_evenements.creer_evenement_godet(test_db, ctx, parsed, "mise en godet de 3 gourmand sur 3 graines")
    assert test_db.query(Evenement).count() == 0


# ── Routage : mise_en_godet ne doit jamais passer par creer_evenement_confirme ──

@pytest.mark.asyncio
async def test_mise_en_godet_avec_variete_route_vers_creer_evenement_godet(test_db, ctx):
    """[fix bug id=351] Même quand la variété est déjà connue (donc pas
    d'interception _GODET_PENDING en amont), _do_save_items doit sauvegarder via
    creer_evenement_godet — jamais via creer_evenement_confirme — pour garantir
    parcelle_id=None et le lien origine_graines_id, quel que soit le chemin qui a
    mené jusqu'à la confirmation."""
    import bot as bot_module

    serre = Parcelle(nom="serre", nom_normalise="serre", ordre=1, actif=True, est_pepiniere=True)
    test_db.add(serre)
    test_db.add(Evenement(type_action="semis", culture="pois", variete="gourmand",
                           quantite=3, unite="graines", parcelle_id=serre.id))
    test_db.commit()

    items = [{
        "action": "mise_en_godet", "culture": "pois", "variete": "gourmand",
        "nb_graines_semees": 3, "nb_plants_godets": 3,
        "parcelle": "serre",  # simule une résolution de parcelle qui n'aurait jamais dû être demandée
    }]

    update = MagicMock()
    update.effective_user.id = 999
    update.effective_message = AsyncMock()

    with patch("bot.SessionLocal", return_value=test_db):
        await bot_module._do_save_items(update, items, "mise en godet de 3 pois gourmand sur 3 graines")

    event = test_db.query(Evenement).filter(Evenement.type_action == "mise_en_godet").one()
    assert event.parcelle_id is None
    assert event.origine_graines_id is not None
    assert event.culture == "pois"


@pytest.mark.asyncio
async def test_mise_en_godet_culture_manquante_bloque_sans_ecriture(test_db, ctx):
    """Reproduit le bug id=351 de bout en bout via _do_save_items : culture=None,
    variete="gourmand" — aucun événement fantôme ne doit être écrit, l'utilisateur
    reçoit un message d'erreur explicite."""
    import bot as bot_module

    items = [{
        "action": "mise_en_godet", "culture": None, "variete": "gourmand",
        "nb_graines_semees": 3, "nb_plants_godets": 3,
    }]

    update = MagicMock()
    update.effective_user.id = 998
    update.effective_message = AsyncMock()

    with patch("bot.SessionLocal", return_value=test_db):
        await bot_module._do_save_items(update, items, "mise en godet de 3 gourmand sur 3 graines")

    assert test_db.query(Evenement).count() == 0
    assert update.effective_message.reply_text.called

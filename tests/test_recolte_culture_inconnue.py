"""
tests/test_recolte_culture_inconnue.py — Non-régression du bug rapporté :

  Il était possible d'enregistrer une récolte (ou toute action supposant une
  culture déjà en place — perte, arrosage...) pour une culture jamais semée,
  jamais plantée, jamais mise en godet dans le potager. Aucun garde-fou ne
  vérifiait l'existence de la culture elle-même (contrairement à la parcelle,
  qui était déjà bloquée si inconnue — cf. test_resolve_parcelle.py).

Comportement corrigé : _parse_and_save bloque avant confirmation (même
traitement que "parcelle inconnue") si la culture citée n'a jamais été
introduite dans le potager via un semis/plantation/mise en godet.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from database.models import Parcelle, Evenement


def _make_update(user_id: int = 1):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    update.effective_message = update.message
    return update


@pytest.fixture
def db_avec_tomate(test_db):
    centrale = Parcelle(nom="planche-centrale", nom_normalise="planchecentrale", ordre=1, actif=True)
    test_db.add(centrale)
    test_db.commit()
    test_db.add(Evenement(type_action="plantation", culture="tomate", variete="cerise",
                           quantite=2, unite="plants", parcelle_id=centrale.id))
    test_db.commit()
    return test_db


@pytest.mark.asyncio
async def test_recolte_culture_jamais_plantee_bloquee(db_avec_tomate):
    """[Bug rapporté] Récolte de 'mangue' — jamais semée/plantée — doit être bloquée."""
    update = _make_update()
    parsed_item = {
        "action": "recolte", "culture": "mangue",
        "quantite": 3, "unite": "kg",
    }

    import bot as bot_module
    with (
        patch("bot.parse_commande", return_value=[parsed_item]),
        patch("bot._normalize_items", return_value=[parsed_item]),
        patch("bot.SessionLocal", return_value=db_avec_tomate),
    ):
        bot_module._ACTION_PENDING.pop(1, None)
        await bot_module._parse_and_save(update, "j'ai récolté 3 kg de mangue")

    assert update.message.reply_text.called
    text_sent = update.message.reply_text.call_args[0][0]
    assert "mangue" in text_sent
    assert "Aucune trace de" in text_sent

    # Aucun événement ne doit avoir été créé (bloqué avant confirmation)
    assert db_avec_tomate.query(Evenement).filter(Evenement.culture == "mangue").count() == 0


@pytest.mark.asyncio
async def test_recolte_culture_connue_non_bloquee(db_avec_tomate):
    """Une récolte sur une culture réellement plantée n'est pas bloquée par ce garde-fou."""
    update = _make_update()
    parsed_item = {
        "action": "recolte", "culture": "tomate", "variete": "cerise",
        "quantite": 2, "unite": "kg", "parcelle": "centrale",
    }

    import bot as bot_module
    with (
        patch("bot.parse_commande", return_value=[parsed_item]),
        patch("bot._normalize_items", return_value=[parsed_item]),
        patch("bot.SessionLocal", return_value=db_avec_tomate),
    ):
        bot_module._ACTION_PENDING.pop(1, None)
        await bot_module._parse_and_save(update, "j'ai récolté 2 kg de tomates cerise, parcelle centrale")

    text_sent = update.message.reply_text.call_args[0][0]
    assert "Aucune trace de" not in text_sent
    bot_module._ACTION_PENDING.pop(1, None)


@pytest.mark.asyncio
async def test_semis_culture_nouvelle_pas_bloque(db_avec_tomate):
    """[non-régression] Un SEMIS (action source) sur une culture jamais vue avant
    doit rester possible — c'est justement l'action qui introduit une culture."""
    update = _make_update()
    parsed_item = {
        "action": "semis", "culture": "mangue",
        "quantite": 5, "unite": "graines",
    }

    import bot as bot_module
    with (
        patch("bot.parse_commande", return_value=[parsed_item]),
        patch("bot._normalize_items", return_value=[parsed_item]),
        patch("bot.SessionLocal", return_value=db_avec_tomate),
        patch("utils.stock.get_type_organe", return_value="reproducteur"),
    ):
        bot_module._ACTION_PENDING.pop(1, None)
        await bot_module._parse_and_save(update, "j'ai semé 5 graines de mangue")

    text_sent = update.message.reply_text.call_args[0][0]
    assert "Aucune trace de" not in text_sent
    bot_module._ACTION_PENDING.pop(1, None)

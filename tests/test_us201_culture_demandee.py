"""
[US-201 / I3] « Ajouter une culture » sur un rang libre : le compagnon demande la culture.

La Vue plan dépose un geste *Semer en place* ou *Planter* rattaché à la parcelle,
sans culture. Avant cette US, le compagnon sautait directement à « Quelle
quantité ? » puis proposait d'enregistrer un semis sans culture (constaté le
06/10/2026). Il doit demander la culture AVANT tout le reste.

- une file sans culture → « Quelle culture ? », rien n'est enregistré ;
- la réponse devient la culture et rejoint le texte du geste (garde US-011 bis) ;
- « annuler » laisse le geste dans la file ;
- une phrase dictée sans culture garde son comportement habituel ;
- un geste qui a sa culture n'est pas interrogé.
"""
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app import bot as bot_module
from app.bot import messages
from app.bot.etat import _ACTION_PENDING, _CULTURE_PENDING, _QUANTITE_PENDING

GESTE_FILE = {"id": 7, "potager_id": 1, "user_id": 1, "position": 1, "total": 1}


def _update(user_id: int = 901, texte: str = ""):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message = AsyncMock()
    update.message.text = texte
    update.message.reply_text = AsyncMock()
    update.effective_message = update.message
    return update


def _nettoyer(user_id: int) -> None:
    for table in (_CULTURE_PENDING, _QUANTITE_PENDING, _ACTION_PENDING):
        table.pop(user_id, None)


@pytest.mark.asyncio
@pytest.mark.parametrize("action,verbe", [("semis", "semer"), ("plantation", "planter")])
async def test_us201_un_geste_de_la_file_sans_culture_la_demande(action, verbe):
    """I3 — la culture est demandée avant la quantité, rien n'est confirmé."""
    uid = 901
    item = {"action": action, "culture": None, "parcelle": "planche-centrale"}
    _nettoyer(uid)
    update = _update(uid)
    try:
        with (
            patch("app.bot._normalize_items", side_effect=lambda items, texte: items),
            patch("app.bot.require_role"),
            patch("app.bot.current_context"),
        ):
            await bot_module._parse_and_save(
                update, f"{action} parcelle planche-centrale",
                pre_parsed_items=[item], geste_file=GESTE_FILE,
            )

        texte = update.message.reply_text.call_args[0][0]
        assert "Quelle culture" in texte and verbe in texte
        assert "quantité" not in texte.lower()
        assert uid in _CULTURE_PENDING
        assert _CULTURE_PENDING[uid]["geste_file"] == GESTE_FILE
        assert uid not in _ACTION_PENDING          # aucun récapitulatif, rien d'enregistrable
        assert uid not in _QUANTITE_PENDING        # la quantité viendra APRÈS la culture
    finally:
        _nettoyer(uid)


@pytest.mark.asyncio
async def test_us201_la_reponse_devient_la_culture_et_garde_le_geste(monkeypatch):
    """La culture rejoint l'item ET le texte (garde anti-hallucination), geste_file conservé."""
    uid = 902
    espion = AsyncMock()
    monkeypatch.setattr(messages, "_parse_and_save", espion)
    monkeypatch.setattr(messages, "_verifier_liaison_ou_onboarding", AsyncMock(return_value=True))
    _CULTURE_PENDING[uid] = {
        "items": [{"action": "semis", "culture": None, "parcelle": "planche-centrale"}],
        "texte": "semis en pleine terre parcelle planche-centrale",
        "ts": time.time(), "geste_file": GESTE_FILE,
    }
    update = _update(uid, "courgette")
    try:
        await messages.handle_text(update, SimpleNamespace(user_data={}))
    finally:
        _nettoyer(uid)

    espion.assert_awaited_once()
    args, kwargs = espion.await_args
    assert kwargs["pre_parsed_items"][0]["culture"] == "courgette"
    assert "courgette" in args[1]
    assert kwargs["geste_file"] == GESTE_FILE
    assert uid not in _CULTURE_PENDING


@pytest.mark.asyncio
async def test_us201_annuler_laisse_le_geste_dans_la_file(monkeypatch):
    uid = 903
    espion = AsyncMock()
    monkeypatch.setattr(messages, "_parse_and_save", espion)
    monkeypatch.setattr(messages, "_verifier_liaison_ou_onboarding", AsyncMock(return_value=True))
    _CULTURE_PENDING[uid] = {
        "items": [{"action": "semis", "culture": None}], "texte": "semis",
        "ts": time.time(), "geste_file": GESTE_FILE,
    }
    update = _update(uid, "Annuler")
    try:
        await messages.handle_text(update, SimpleNamespace(user_data={}))
    finally:
        _nettoyer(uid)

    espion.assert_not_awaited()
    assert "/gestes" in update.message.reply_text.call_args[0][0]
    assert uid not in _CULTURE_PENDING


@pytest.mark.asyncio
async def test_us201_une_phrase_dictee_sans_culture_garde_son_comportement():
    """Hors file (pas de geste_file) : aucune question de culture n'est ajoutée."""
    uid = 904
    item = {"action": "semis", "culture": None, "quantite": 5, "unite": "graines"}
    _nettoyer(uid)
    update = _update(uid)
    try:
        with (
            patch("app.bot._normalize_items", side_effect=lambda items, texte: items),
            patch("app.bot.require_role"),
            patch("app.bot.current_context"),
            patch("app.bot.get_all_parcelles", return_value=[]),
            patch("app.bot.SessionLocal"),
        ):
            await bot_module._parse_and_save(update, "semis 5 graines", pre_parsed_items=[item])
        assert uid not in _CULTURE_PENDING
    finally:
        _nettoyer(uid)


@pytest.mark.asyncio
async def test_us201_un_geste_avec_sa_culture_n_est_pas_interroge():
    uid = 905
    item = {"action": "plantation", "culture": "tomate", "quantite": 4, "unite": "plants"}
    _nettoyer(uid)
    update = _update(uid)
    try:
        with (
            patch("app.bot._normalize_items", side_effect=lambda items, texte: items),
            patch("app.bot.require_role"),
            patch("app.bot.current_context"),
            patch("app.bot.get_all_parcelles", return_value=[]),
            patch("app.bot.SessionLocal"),
        ):
            await bot_module._parse_and_save(
                update, "plantation de tomate", pre_parsed_items=[item], geste_file=GESTE_FILE,
            )
        assert uid not in _CULTURE_PENDING
    finally:
        _nettoyer(uid)


# ── /gestes ne doit pas planter sur un nom de parcelle avec « _ » ────────────
# Constaté le 06/10/2026 : « planche_centrale » ouvrait une mise en italique
# jamais refermée, et Telegram refusait la liste entière (BadRequest).

def test_us201_libelle_court_echappe_le_markdown_des_noms():
    from app.services import file_gestes as svc

    geste = SimpleNamespace(geste={
        "action": "plantation", "culture": "petit_pois", "parcelle": "planche_centrale",
        "date": "2026-10-06",
    })
    ligne = svc.libelle_court(geste)

    assert "planche\_centrale" in ligne and "petit\_pois" in ligne
    # Plus aucun « _ » nu : rien ne peut ouvrir une entité Markdown.
    assert "_" not in ligne.replace("\_", "")
    assert "(2026-10-06)" in ligne


def test_us201_echapper_markdown_neutralise_les_quatre_caracteres():
    from app.services import file_gestes as svc

    assert svc.echapper_markdown("a_b*c`d[e") == "a\_b\*c\`d\[e"
    assert svc.echapper_markdown("tomate") == "tomate"

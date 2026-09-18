"""
tests/test_meteo_telegram_potager.py — /meteo Telegram sur la localisation du potager actif

La commande /meteo datait d'avant le multi-tenant (US-043 / US-074) : elle
interrogeait les coordonnées globales du bot et rattachait l'observation au
potager #1. Elle suit désormais la règle de `GET /meteo` (US-075 / CA4).
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.context import TenantContext
from database.models import Evenement, Potager
from utils.meteo import (
    METEO_LATITUDE,
    LocalisationPotagerManquanteError,
    save_meteo_observation,
)
from tests.test_us182_previsions_meteo import _patch_open_meteo


def _potager(db, id_: int, lat=None, lon=None, ville=None) -> Potager:
    potager = Potager(id=id_, nom=f"P{id_}", ville=ville, latitude=lat, longitude=lon, proprietaire_id=1)
    db.add(potager)
    db.commit()
    return potager


def test_save_meteo_observation_utilise_la_localisation_du_potager(test_db) -> None:
    _potager(test_db, 2, lat=43.3, lon=5.4)
    with _patch_open_meteo() as mock_get:
        meteo = save_meteo_observation(test_db, potager_id=2)
    assert meteo is not None
    params = mock_get.call_args[1]["params"]
    assert (params["latitude"], params["longitude"]) == (43.3, 5.4)
    evenement = test_db.query(Evenement).filter(Evenement.texte_original == "[AUTO-METEO]").one()
    assert evenement.potager_id == 2


def test_save_meteo_observation_anti_doublon_par_potager(test_db) -> None:
    _potager(test_db, 1, lat=48.9, lon=2.2)
    _potager(test_db, 2, lat=43.3, lon=5.4)
    with _patch_open_meteo():
        assert save_meteo_observation(test_db, potager_id=1) is not None
        assert save_meteo_observation(test_db, potager_id=2) is not None
        assert save_meteo_observation(test_db, potager_id=2) is None
    assert test_db.query(Evenement).filter(Evenement.texte_original == "[AUTO-METEO]").count() == 2


def test_save_meteo_observation_sans_localisation_n_appelle_pas_open_meteo(test_db) -> None:
    _potager(test_db, 2)
    with _patch_open_meteo(side_effect=AssertionError("ne doit pas être appelé")):
        with pytest.raises(LocalisationPotagerManquanteError):
            save_meteo_observation(test_db, potager_id=2)
    assert test_db.query(Evenement).count() == 0


def test_save_meteo_observation_sans_potager_garde_les_coordonnees_du_bot(test_db) -> None:
    """Job 5 h : comportement d'origine inchangé."""
    with _patch_open_meteo() as mock_get:
        assert save_meteo_observation(test_db) is not None
    assert mock_get.call_args[1]["params"]["latitude"] == METEO_LATITUDE


def _update() -> MagicMock:
    update = MagicMock()
    update.message.reply_text = AsyncMock(return_value=MagicMock(edit_text=AsyncMock()))
    return update


@pytest.mark.asyncio
async def test_cmd_meteo_potager_actif_sans_localisation(test_db) -> None:
    from app.bot import meteo_jobs

    _potager(test_db, 2)
    update = _update()
    ctx = TenantContext(user_id=1, potager_id=2, role="owner")
    with patch.object(meteo_jobs, "SessionLocal", return_value=test_db), \
         patch.object(meteo_jobs, "current_context", return_value=ctx), \
         _patch_open_meteo(side_effect=AssertionError("ne doit pas être appelé")):
        await meteo_jobs.cmd_meteo(update, MagicMock())
    message = update.message.reply_text.return_value.edit_text.call_args[0][0]
    assert "localisation" in message


@pytest.mark.asyncio
async def test_cmd_meteo_interroge_le_potager_actif(test_db) -> None:
    from app.bot import meteo_jobs

    _potager(test_db, 2, lat=43.3, lon=5.4, ville="Marseille")
    update = _update()
    ctx = TenantContext(user_id=1, potager_id=2, role="owner")
    with patch.object(meteo_jobs, "SessionLocal", return_value=test_db), \
         patch.object(meteo_jobs, "current_context", return_value=ctx), \
         _patch_open_meteo() as mock_get:
        await meteo_jobs.cmd_meteo(update, MagicMock())
    assert mock_get.call_args[1]["params"]["latitude"] == 43.3
    message = update.message.reply_text.return_value.edit_text.call_args[0][0]
    assert "Météo enregistrée" in message
    assert "📍 Marseille (43.3000, 5.4000)" in message

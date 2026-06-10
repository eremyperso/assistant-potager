"""
Tests — Normalisation unité semis

Règle : si type_action='semis' et unite absente ou hors {"graine","graines","plant","plants"}
→ forcée à 'graines' dans _do_save_items.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, Evenement, Parcelle
from bot import _UNITES_SEMIS_VALIDES


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    p = Parcelle(nom="serre", nom_normalise="serre", actif=True)
    session.add(p)
    session.commit()
    yield session
    session.close()


def _mock_update():
    update = MagicMock()
    update.effective_message.reply_text = AsyncMock()
    update.effective_user.id = 42
    return update


# ── Tests unitaires sur la constante ─────────────────────────────────────────

def test_constante_unites_valides():
    """La constante contient exactement les 4 formes attendues."""
    assert _UNITES_SEMIS_VALIDES == frozenset({"graine", "graines", "plant", "plants"})


@pytest.mark.parametrize("unite", ["graine", "graines", "plant", "plants"])
def test_unites_valides_conservees(unite):
    """Les unités reconnues ne doivent pas être écrasées."""
    unite_brute = (unite or "").lower().strip()
    assert unite_brute in _UNITES_SEMIS_VALIDES


@pytest.mark.parametrize("unite", [None, "", "kg", "pots", "barquette", "bottes", "m2", "pied"])
def test_unites_invalides_normalisees(unite):
    """Toute unité hors liste → doit être forcée à 'graines'."""
    unite_brute = (unite or "").lower().strip()
    assert unite_brute not in _UNITES_SEMIS_VALIDES


# ── Tests d'intégration via _do_save_items ───────────────────────────────────

@pytest.mark.asyncio
@patch("bot.send_voice_reply", new_callable=AsyncMock)
async def test_semis_unite_none_sauvegarde_graines(mock_voice, db):
    """Semis sans unité → sauvegardé avec unite='graines'."""
    from bot import _do_save_items
    item = {"action": "semis", "culture": "tomate", "quantite": 20, "unite": None}
    with patch("bot.SessionLocal", return_value=db):
        await _do_save_items(_mock_update(), [item], "semis tomate 20")
    ev = db.query(Evenement).filter_by(type_action="semis").first()
    assert ev is not None
    assert ev.unite == "graines"


@pytest.mark.asyncio
@patch("bot.send_voice_reply", new_callable=AsyncMock)
async def test_semis_unite_pots_forcee_graines(mock_voice, db):
    """Semis avec unite='pots' → forcée à 'graines'."""
    from bot import _do_save_items
    item = {"action": "semis", "culture": "basilic", "quantite": 10, "unite": "pots"}
    with patch("bot.SessionLocal", return_value=db):
        await _do_save_items(_mock_update(), [item], "semis basilic 10 pots")
    ev = db.query(Evenement).filter_by(type_action="semis", culture="basilic").first()
    assert ev is not None
    assert ev.unite == "graines"


@pytest.mark.asyncio
@patch("bot.send_voice_reply", new_callable=AsyncMock)
async def test_semis_unite_graines_conservee(mock_voice, db):
    """Semis avec unite='graines' → conservée telle quelle."""
    from bot import _do_save_items
    item = {"action": "semis", "culture": "carotte", "quantite": 50, "unite": "graines"}
    with patch("bot.SessionLocal", return_value=db):
        await _do_save_items(_mock_update(), [item], "semis carotte 50 graines")
    ev = db.query(Evenement).filter_by(type_action="semis", culture="carotte").first()
    assert ev is not None
    assert ev.unite == "graines"


@pytest.mark.asyncio
@patch("bot.send_voice_reply", new_callable=AsyncMock)
async def test_plantation_unite_non_affectee(mock_voice, db):
    """La normalisation ne s'applique PAS aux autres actions (plantation)."""
    from bot import _do_save_items
    item = {"action": "plantation", "culture": "tomate", "quantite": 3, "unite": "pots"}
    with patch("bot.SessionLocal", return_value=db):
        await _do_save_items(_mock_update(), [item], "plantation tomate 3 pots")
    ev = db.query(Evenement).filter_by(type_action="plantation").first()
    assert ev is not None
    assert ev.unite == "pots"

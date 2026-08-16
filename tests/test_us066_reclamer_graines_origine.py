"""
tests/test_us066_reclamer_graines_origine.py
[US-066] Réclamer le nombre de graines d'origine lors d'une mise en godet

Couverture des critères d'acceptance :
  CA1 — la question est posée quand `nb_graines_semees` manque et qu'un lot
        rattachable a encore des graines non soldées
  CA2 — la question rappelle culture, variété et graines restantes du lot concerné
  CA3 — la réponse est facultative : « Je ne sais pas » enregistre sans valeur, et
        l'état de germination du lot reste « indéterminée » (US-065)
  CA4 — la question n'est pas posée : nombre déjà fourni, aucun semis rattachable,
        lot déjà entièrement soldé, ou rattachement ambigu
  CA5 — une réponse incohérente est signalée et redemandée, jamais enregistrée
  CA6 — le flux fonctionne en saisie texte comme en saisie vocale

Note QA : US-066 est une US d'interaction Telegram (labels `telegram`,
`enregistrement`). Aucun fichier de `frontend/` n'est touché — le volet de
validation visuelle 375/768/1280 px ne s'applique pas.
"""
import time
from datetime import datetime

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.db import Base
from database.models import Evenement
from app.services.context import TenantContext
from app.services import evenements as svc_evenements
from utils.stock import calcul_lots_pepiniere, ETAT_GERMINATION_INDETERMINEE

POTAGER_ID = 1


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def ctx():
    return TenantContext(user_id=1, potager_id=POTAGER_ID, role="owner")


@pytest.fixture(autouse=True)
def _pending_propre():
    """Aucun test ne doit hériter d'une question en attente d'un autre."""
    from bot import _GODET_GRAINES_PENDING
    _GODET_GRAINES_PENDING.clear()
    yield
    _GODET_GRAINES_PENDING.clear()


def _mock_update(user_id=42):
    """Update Telegram minimal, compatible contexte message ET callback."""
    update = MagicMock()
    message = AsyncMock()
    update.message = message
    update.effective_message = message
    update.effective_user = MagicMock(id=user_id)
    return update, message


def _parsed_godet(nb_plants=5, nb_graines=None, **extra):
    base = {
        "action": "mise_en_godet", "culture": "tomate", "variete": None,
        "nb_plants_godets": nb_plants, "nb_graines_semees": nb_graines,
        "quantite": float(nb_plants) if nb_plants is not None else None, "unite": "plants",
        "date": None, "commentaire": None,
    }
    base.update(extra)
    return base


_LOT_OUVERT = {
    "semis_id": 12, "culture": "tomate", "variete": None,
    "date_semis": datetime(2026, 3, 1), "graines_en_germination": 10,
}
_LOT_SOLDE = {**_LOT_OUVERT, "graines_en_germination": 0}


def _patch_lot(lot):
    """Force le lot pressenti — isole la question de la résolution du lot."""
    return patch("bot._lot_pressenti_pour_godet", return_value=lot)


# ── CA1 / CA2 — la question est posée, avec son contexte ────────────────────

@pytest.mark.asyncio
async def test_us066_ca1_question_posee_quand_graines_manquantes() -> None:
    """CA1 — « 5 tomates en godet » sans nombre de graines, lot ouvert → question."""
    # Arrange
    from bot import _GODET_GRAINES_PENDING, _demander_graines_godet_si_manquant
    update, message = _mock_update()
    parsed = _parsed_godet()

    # Act
    with _patch_lot(_LOT_OUVERT):
        pose = await _demander_graines_godet_si_manquant(update, parsed, "5 tomates en godet")

    # Assert
    assert pose is True
    assert 42 in _GODET_GRAINES_PENDING
    message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_us066_ca2_question_rappelle_le_contexte_du_lot() -> None:
    """CA2 — culture, variété et graines restantes, plutôt qu'une question à l'aveugle."""
    # Arrange
    from bot import _demander_graines_godet_si_manquant
    update, message = _mock_update()
    lot = {**_LOT_OUVERT, "variete": "Cœur de bœuf", "graines_en_germination": 7}

    # Act
    with _patch_lot(lot):
        await _demander_graines_godet_si_manquant(
            update, _parsed_godet(nb_plants=5, variete="Cœur de bœuf"), "texte"
        )

    # Assert
    texte_question = message.reply_text.call_args[0][0]
    assert "tomate" in texte_question
    assert "Cœur de bœuf" in texte_question
    assert "7 graine" in texte_question
    assert "5" in texte_question           # le nombre de plants repiqués
    assert "01/03/2026" in texte_question  # le lot concerné, daté


@pytest.mark.asyncio
async def test_us066_ca3_bouton_je_ne_sais_pas_present() -> None:
    """CA3 — la sortie explicite est offerte dès la question."""
    # Arrange
    from bot import _demander_graines_godet_si_manquant
    update, message = _mock_update()

    # Act
    with _patch_lot(_LOT_OUVERT):
        await _demander_graines_godet_si_manquant(update, _parsed_godet(), "texte")

    # Assert
    markup = message.reply_text.call_args[1]["reply_markup"]
    callbacks = [b.callback_data for ligne in markup.inline_keyboard for b in ligne]
    assert "godetgraines_skip" in callbacks
    assert "godetgraines_cancel" in callbacks


# ── CA4 — les cas où la question n'a pas lieu d'être ────────────────────────

@pytest.mark.asyncio
async def test_us066_ca4_pas_de_question_si_graines_deja_fournies() -> None:
    """CA4 — « 5 tomates en godet sur 6 graines » : rien à demander."""
    from bot import _demander_graines_godet_si_manquant
    update, message = _mock_update()

    with _patch_lot(_LOT_OUVERT):
        pose = await _demander_graines_godet_si_manquant(
            update, _parsed_godet(nb_graines=6), "5 tomates sur 6 graines"
        )

    assert pose is False
    message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_us066_ca4_pas_de_question_sans_semis_rattachable() -> None:
    """CA4 — aucune courgette semée en pépinière : aucun reste à annoncer."""
    from bot import _demander_graines_godet_si_manquant
    update, message = _mock_update()

    with _patch_lot(None):
        pose = await _demander_graines_godet_si_manquant(update, _parsed_godet(), "texte")

    assert pose is False
    message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_us066_ca4_pas_de_question_si_lot_entierement_solde() -> None:
    """CA4 — un lot sans graine restante n'a plus rien à solder."""
    from bot import _demander_graines_godet_si_manquant
    update, message = _mock_update()

    with _patch_lot(_LOT_SOLDE):
        pose = await _demander_graines_godet_si_manquant(update, _parsed_godet(), "texte")

    assert pose is False
    message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_us066_ca4_pas_de_question_deux_fois() -> None:
    """CA4 — anti-boucle : une fois traitée, la question n'est jamais reposée."""
    from bot import _demander_graines_godet_si_manquant
    update, message = _mock_update()

    with _patch_lot(_LOT_OUVERT):
        pose = await _demander_graines_godet_si_manquant(
            update, _parsed_godet(_graines_demandees=True), "texte"
        )

    assert pose is False
    message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_us066_ca4_pas_de_question_sans_plants_repiques() -> None:
    """Edge case — sans nombre de plants, il n'y a rien à rapporter à des graines."""
    from bot import _demander_graines_godet_si_manquant
    update, message = _mock_update()

    with _patch_lot(_LOT_OUVERT):
        pose = await _demander_graines_godet_si_manquant(update, _parsed_godet(nb_plants=None), "t")

    assert pose is False


def test_us066_ca4_lot_pressenti_none_si_ambigu() -> None:
    """CA4 — deux lots candidats : le rattachement est incertain, donc aucun reste
    précis à annoncer. La question du LOT est posée avant, pas celle-ci."""
    from bot import _lot_pressenti_pour_godet

    with (
        patch("bot.SessionLocal", return_value=MagicMock()),
        patch("app.services.stock.lots_candidats_mise_en_godet",
              return_value=[_LOT_OUVERT, {**_LOT_OUVERT, "semis_id": 13}]),
    ):
        assert _lot_pressenti_pour_godet(_parsed_godet()) is None


def test_us066_lot_pressenti_suit_le_lot_explicitement_choisi() -> None:
    """Le lot désigné au menu prime : c'est son reste qui sera annoncé."""
    from bot import _lot_pressenti_pour_godet

    with (
        patch("bot.SessionLocal", return_value=MagicMock()),
        patch("app.services.stock.lot_pepiniere_par_semis", return_value=_LOT_OUVERT) as mock_lot,
    ):
        lot = _lot_pressenti_pour_godet(_parsed_godet(origine_graines_id=12))

    assert lot == _LOT_OUVERT
    assert mock_lot.call_args[0][2] == 12


# ── CA5 — réponses incohérentes signalées et redemandées ────────────────────

@pytest.mark.asyncio
async def test_us066_ca5_moins_de_graines_que_de_plants_redemande() -> None:
    """CA5 — Gherkin « Réponse incohérente refusée » : 5 plants sur 3 graines."""
    # Arrange
    from bot import _GODET_GRAINES_PENDING, _godet_graines_reponse
    parsed = _parsed_godet(nb_plants=5)
    _GODET_GRAINES_PENDING[42] = {
        "parsed": parsed, "texte": "t", "ts": time.time(), "lot": _LOT_OUVERT,
    }
    update, message = _mock_update()

    # Act
    with patch("bot._save_godet_item", new=AsyncMock()) as mock_save:
        await _godet_graines_reponse(update, "3 graines")

    # Assert
    mock_save.assert_not_awaited()
    assert 42 in _GODET_GRAINES_PENDING          # remis en attente
    assert parsed.get("nb_graines_semees") is None  # rien d'enregistré
    assert "Impossible" in message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_us066_ca5_plus_de_graines_que_le_lot_redemande() -> None:
    """CA5 — cohérence avec le garde-fou de cumul : on ne solde pas 20 graines sur
    un lot qui n'en a plus que 10. Redemandé plutôt que refusé à l'écriture."""
    # Arrange
    from bot import _GODET_GRAINES_PENDING, _godet_graines_reponse
    parsed = _parsed_godet(nb_plants=5)
    _GODET_GRAINES_PENDING[42] = {
        "parsed": parsed, "texte": "t", "ts": time.time(), "lot": _LOT_OUVERT,
    }
    update, message = _mock_update()

    # Act
    with patch("bot._save_godet_item", new=AsyncMock()) as mock_save:
        await _godet_graines_reponse(update, "20")

    # Assert
    mock_save.assert_not_awaited()
    assert 42 in _GODET_GRAINES_PENDING
    assert "10" in message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_us066_ca5_reponse_non_numerique_redemande() -> None:
    """CA5 — une réponse sans chiffre ne consomme pas la question."""
    # Arrange
    from bot import _GODET_GRAINES_PENDING, _godet_graines_reponse
    _GODET_GRAINES_PENDING[42] = {
        "parsed": _parsed_godet(), "texte": "t", "ts": time.time(), "lot": _LOT_OUVERT,
    }
    update, message = _mock_update()

    # Act
    with patch("bot._save_godet_item", new=AsyncMock()) as mock_save:
        await _godet_graines_reponse(update, "aucune idée")

    # Assert
    mock_save.assert_not_awaited()
    assert 42 in _GODET_GRAINES_PENDING
    assert "non reconnu" in message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_us066_reponse_valide_est_enregistree() -> None:
    """Happy path — la valeur saisie alimente `nb_graines_semees` et l'écriture suit."""
    # Arrange
    from bot import _GODET_GRAINES_PENDING, _godet_graines_reponse
    parsed = _parsed_godet(nb_plants=5)
    _GODET_GRAINES_PENDING[42] = {
        "parsed": parsed, "texte": "5 tomates en godet", "ts": time.time(), "lot": _LOT_OUVERT,
    }
    update, _ = _mock_update()

    # Act
    with patch("bot._save_godet_item", new=AsyncMock()) as mock_save:
        await _godet_graines_reponse(update, "sur 8 graines")

    # Assert
    assert parsed["nb_graines_semees"] == 8
    assert parsed["_graines_demandees"] is True
    mock_save.assert_awaited_once()
    assert 42 not in _GODET_GRAINES_PENDING


@pytest.mark.asyncio
async def test_us066_borne_inclusive_egale_au_nombre_de_plants() -> None:
    """Un repiquage sans aucune perte (5 plants sur 5 graines) est légitime."""
    # Arrange
    from bot import _GODET_GRAINES_PENDING, _godet_graines_reponse
    parsed = _parsed_godet(nb_plants=5)
    _GODET_GRAINES_PENDING[42] = {
        "parsed": parsed, "texte": "t", "ts": time.time(), "lot": _LOT_OUVERT,
    }
    update, _ = _mock_update()

    # Act
    with patch("bot._save_godet_item", new=AsyncMock()):
        await _godet_graines_reponse(update, "5")

    # Assert
    assert parsed["nb_graines_semees"] == 5


@pytest.mark.asyncio
async def test_us066_reponse_expiree_n_enregistre_rien() -> None:
    """Cas d'erreur — délai dépassé : rien n'est écrit, le jardinier re-saisit."""
    # Arrange
    from bot import _GODET_GRAINES_PENDING, _GODET_GRAINES_TIMEOUT, _godet_graines_reponse
    _GODET_GRAINES_PENDING[42] = {
        "parsed": _parsed_godet(), "texte": "t",
        "ts": time.time() - _GODET_GRAINES_TIMEOUT - 1, "lot": _LOT_OUVERT,
    }
    update, _ = _mock_update()

    # Act
    with patch("bot._save_godet_item", new=AsyncMock()) as mock_save:
        await _godet_graines_reponse(update, "8")

    # Assert
    mock_save.assert_not_awaited()
    assert 42 not in _GODET_GRAINES_PENDING


# ── CA3 — passer outre ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_us066_ca3_je_ne_sais_pas_enregistre_sans_valeur() -> None:
    """CA3 — Gherkin « Le jardinier ne sait pas répondre » : aucune valeur inventée."""
    # Arrange
    from bot import _GODET_GRAINES_PENDING, _godet_graines_cb
    parsed = _parsed_godet()
    _GODET_GRAINES_PENDING[42] = {
        "parsed": parsed, "texte": "t", "ts": time.time(), "lot": _LOT_OUVERT,
    }
    update, _ = _mock_update()
    update.callback_query = AsyncMock()
    update.callback_query.data = "godetgraines_skip"

    # Act
    with patch("bot._save_godet_item", new=AsyncMock()) as mock_save:
        await _godet_graines_cb(update, MagicMock())

    # Assert
    assert parsed.get("nb_graines_semees") is None
    assert parsed["_graines_demandees"] is True
    mock_save.assert_awaited_once()


@pytest.mark.asyncio
async def test_us066_ca3_annulation_n_enregistre_rien() -> None:
    """Annuler abandonne la mise en godet entière."""
    # Arrange
    from bot import _GODET_GRAINES_PENDING, _godet_graines_cb
    _GODET_GRAINES_PENDING[42] = {
        "parsed": _parsed_godet(), "texte": "t", "ts": time.time(), "lot": _LOT_OUVERT,
    }
    update, _ = _mock_update()
    update.callback_query = AsyncMock()
    update.callback_query.data = "godetgraines_cancel"

    # Act
    with patch("bot._save_godet_item", new=AsyncMock()) as mock_save:
        await _godet_graines_cb(update, MagicMock())

    # Assert
    mock_save.assert_not_awaited()


def test_us066_ca3_etat_indetermine_conforme_a_us065(db, ctx) -> None:
    """CA3 — bout en bout : passer outre laisse bien le lot en germination
    « indéterminée », conformément à US-065 / CA3."""
    # Arrange
    semis = Evenement(
        type_action="semis", culture="tomate", quantite=10.0, unite="graines",
        date=datetime(2026, 3, 1), potager_id=POTAGER_ID,
    )
    db.add(semis)
    db.commit()
    db.refresh(semis)

    # Act — mise en godet sans nombre de graines, comme après un « Je ne sais pas »
    svc_evenements.creer_evenement_godet(
        db, ctx,
        {"action": "mise_en_godet", "culture": "tomate", "variete": None,
         "nb_plants_godets": 5, "nb_graines_semees": None, "quantite": 5.0,
         "unite": "plants", "date": None, "commentaire": None},
        "5 tomates en godet",
    )
    lot = calcul_lots_pepiniere(db, potager_id=POTAGER_ID)[0]

    # Assert
    assert lot["etat_germination"] == ETAT_GERMINATION_INDETERMINEE
    assert lot["graines_soldees"] == 5   # repli sur le nombre de plants


# ── CA6 — texte et voix ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_us066_ca6_reponse_interceptee_en_saisie_texte() -> None:
    """CA6 — la réponse texte est captée avant tout parsing Groq."""
    # Arrange
    from bot import _GODET_GRAINES_PENDING, handle_text
    _GODET_GRAINES_PENDING[42] = {
        "parsed": _parsed_godet(), "texte": "t", "ts": time.time(), "lot": _LOT_OUVERT,
    }
    update, _ = _mock_update()
    update.message.text = "8"

    # Act
    with (
        patch("bot._verifier_liaison_ou_onboarding", new=AsyncMock(return_value=True)),
        patch("bot._godet_graines_reponse", new=AsyncMock()) as mock_reponse,
        patch("bot.parse_commande") as mock_parse,
    ):
        await handle_text(update, MagicMock())

    # Assert
    mock_reponse.assert_awaited_once()
    mock_parse.assert_not_called()  # aucun appel LLM : c'est une réponse, pas une action


@pytest.mark.asyncio
async def test_us066_ca6_reponse_interceptee_en_saisie_vocale() -> None:
    """CA6 — même flux à la voix : la transcription est une réponse, pas une action.
    L'interception est branchée dans handle_voice, qui ne lisait aucun état en
    attente jusqu'ici."""
    # Arrange
    import bot as bot_mod
    from bot import _GODET_GRAINES_PENDING
    import inspect

    source_voice = inspect.getsource(bot_mod.handle_voice)

    # Assert — branchement présent et placé avant la classification d'intention
    assert "_GODET_GRAINES_PENDING" in source_voice
    assert source_voice.index("_GODET_GRAINES_PENDING") < source_voice.index("MODES_CORR")
    assert "_godet_graines_reponse" in source_voice


def test_us066_motifs_de_callback_disjoints() -> None:
    """Garde-fou de routage : `^godet_` (variété), `^godetlot` (lot) et
    `^godetgraines` (graines) ne se recouvrent jamais."""
    import re

    motifs = {
        "variete": re.compile(r"^godet_"),
        "lot":     re.compile(r"^godetlot"),
        "graines": re.compile(r"^godetgraines"),
    }
    attendus = {
        "godet_var:Cerise":     "variete",
        "godet_confirm":        "variete",
        "godetlot:374":         "lot",
        "godetlot_cancel":      "lot",
        "godetgraines_skip":    "graines",
        "godetgraines_cancel":  "graines",
    }
    for donnee, motif_attendu in attendus.items():
        matches = [nom for nom, motif in motifs.items() if motif.match(donnee)]
        assert matches == [motif_attendu], f"{donnee!r} routé vers {matches}"

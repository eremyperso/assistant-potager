"""
tests/test_perte_disambiguation.py
------------------------------------
Tests du flow de disambiguation perte (jardin vs pépinière).

Test critique : _handle_perte_callback DOIT sauvegarder l'événement en DB.
Le bug original : update.message = None dans un callback → plantait silencieusement.

Ces tests auraient détecté le bug immédiatement.

Couvre :
  CA1 : perte_source:jardin  → type_action="perte"       sauvegardé
  CA2 : perte_source:pepiniere → type_action="perte_godet" sauvegardé
  CA3 : perte_var_j:{variete} → perte jardin, bonne variété
  CA4 : perte_var_p:{variete} → perte_godet, bonne variété
  CA5 : perte_cancel          → rien sauvegardé
  CA6 : timeout               → rien sauvegardé, message expiration
  CA7 : pending absent        → message gracieux, pas de crash
  CA8 : update.message = None → pas de crash (bug regression test)
"""
import asyncio
import time
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, Evenement, Parcelle, CultureConfig


# ── Fixture DB in-memory ──────────────────────────────────────────────────────

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    p = Parcelle(nom="nord", nom_normalise="nord", actif=True)
    session.add(p)
    session.add(CultureConfig(nom="tomate", type_organe_recolte="reproducteur"))
    session.flush()
    yield session, p.id
    session.close()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_callback_update(user_id: int, data: str):
    """Update mocké pour callback inline — update.message = None (cas réel)."""
    update             = MagicMock()
    update.message     = None                   # ← simulation exacte d'un callback
    update.effective_user.id = user_id
    update.effective_message = MagicMock()
    update.effective_message.reply_text = AsyncMock()

    query              = MagicMock()
    query.answer       = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.data         = data
    update.callback_query = query
    return update


def _make_ctx():
    return MagicMock()


def _build_pending(item, session, ts=None):
    """Construit l'état _PERTE_PENDING en interrogeant la DB de test."""
    from utils.stock import calcul_godets_par_culture, calcul_stock_par_variete
    godets          = calcul_godets_par_culture(session, item.get("culture", ""))
    varietes_jardin = calcul_stock_par_variete(session, item.get("culture", ""))
    return {
        "item":           item,
        "texte":          f"perdu {item.get('quantite', 1)} {item.get('culture', '')}",
        "godets":         godets,
        "jardin_varietes": varietes_jardin,
        "ts":             ts if ts is not None else time.time(),
    }


def _run(coro):
    """Lance une coroutine de façon synchrone (compatible Python 3.10+)."""
    return asyncio.run(coro)


# ── CA1 : perte_source:jardin → perte sauvegardée ────────────────────────────

def test_ca1_perte_jardin_sauvegardee(db):
    """CA1 — perte_source:jardin → DB contient type_action='perte'."""
    session, pid = db
    session.add(Evenement(
        type_action="plantation", culture="tomate", variete="cerise",
        quantite=5, rang=1, unite="plants",
        parcelle_id=pid, date=datetime(2026, 5, 1),
    ))
    session.add(Evenement(
        type_action="mise_en_godet", culture="tomate", variete="cerise",
        nb_plants_godets=3, nb_graines_semees=5, date=datetime(2026, 4, 1),
    ))
    session.commit()

    user_id = 42
    item    = {"action": "perte", "culture": "tomate", "variete": "cerise", "quantite": 1}
    state   = _build_pending(item, session)
    update  = _make_callback_update(user_id, "perte_source:jardin")

    with patch("bot._PERTE_PENDING", {user_id: state}), \
         patch("bot.SessionLocal", return_value=session), \
         patch("bot.send_voice_reply", new_callable=AsyncMock):
        from bot import _handle_perte_callback
        _run(_handle_perte_callback(update, _make_ctx()))

    ev = session.query(Evenement).filter_by(type_action="perte").first()
    assert ev is not None, "Événement perte NON sauvegardé en base — bug update.message=None ?"
    assert ev.culture  == "tomate"
    assert ev.variete  == "cerise"
    assert ev.quantite == 1.0


# ── CA2 : perte_source:pepiniere → perte_godet sauvegardée ───────────────────

def test_ca2_perte_pepiniere_sauvegardee(db):
    """CA2 — perte_source:pepiniere → DB contient type_action='perte_godet'."""
    session, pid = db
    session.add(Evenement(
        type_action="mise_en_godet", culture="tomate", variete="cerise",
        nb_plants_godets=3, nb_graines_semees=5, date=datetime(2026, 4, 1),
    ))
    session.commit()

    user_id = 43
    item    = {"action": "perte", "culture": "tomate", "variete": "cerise", "quantite": 2}
    state   = _build_pending(item, session)
    update  = _make_callback_update(user_id, "perte_source:pepiniere")

    with patch("bot._PERTE_PENDING", {user_id: state}), \
         patch("bot.SessionLocal", return_value=session), \
         patch("bot.send_voice_reply", new_callable=AsyncMock):
        from bot import _handle_perte_callback
        _run(_handle_perte_callback(update, _make_ctx()))

    ev = session.query(Evenement).filter_by(type_action="perte_godet").first()
    assert ev is not None, "Événement perte_godet NON sauvegardé"
    assert ev.culture  == "tomate"
    assert ev.variete  == "cerise"
    assert ev.quantite == 2.0


# ── CA3 : perte_var_j:{variete} → perte jardin bonne variété ─────────────────

def test_ca3_perte_var_j_bonne_variete(db):
    """CA3 — perte_var_j:cerise → perte type_action='perte' variete='cerise'."""
    session, pid = db
    session.add(Evenement(
        type_action="plantation", culture="tomate", variete="cerise",
        quantite=5, rang=1, unite="plants",
        parcelle_id=pid, date=datetime(2026, 5, 1),
    ))
    session.add(Evenement(
        type_action="mise_en_godet", culture="tomate", variete="cerise",
        nb_plants_godets=3, nb_graines_semees=5, date=datetime(2026, 4, 1),
    ))
    session.commit()

    user_id = 44
    item    = {"action": "perte", "culture": "tomate", "variete": None, "quantite": 1}
    state   = _build_pending(item, session)
    update  = _make_callback_update(user_id, "perte_var_j:cerise")

    with patch("bot._PERTE_PENDING", {user_id: state}), \
         patch("bot.SessionLocal", return_value=session), \
         patch("bot.send_voice_reply", new_callable=AsyncMock):
        from bot import _handle_perte_callback
        _run(_handle_perte_callback(update, _make_ctx()))

    ev = session.query(Evenement).filter_by(type_action="perte").first()
    assert ev is not None
    assert ev.variete == "cerise"


# ── CA4 : perte_var_p:{variete} → perte_godet bonne variété ──────────────────

def test_ca4_perte_var_p_bonne_variete(db):
    """CA4 — perte_var_p:cerise → perte_godet variete='cerise'."""
    session, pid = db
    session.add(Evenement(
        type_action="mise_en_godet", culture="tomate", variete="cerise",
        nb_plants_godets=5, nb_graines_semees=8, date=datetime(2026, 4, 1),
    ))
    session.commit()

    user_id = 45
    item    = {"action": "perte", "culture": "tomate", "variete": None, "quantite": 1}
    state   = _build_pending(item, session)
    update  = _make_callback_update(user_id, "perte_var_p:cerise")

    with patch("bot._PERTE_PENDING", {user_id: state}), \
         patch("bot.SessionLocal", return_value=session), \
         patch("bot.send_voice_reply", new_callable=AsyncMock):
        from bot import _handle_perte_callback
        _run(_handle_perte_callback(update, _make_ctx()))

    ev = session.query(Evenement).filter_by(type_action="perte_godet").first()
    assert ev is not None
    assert ev.variete == "cerise"


# ── CA5 : perte_cancel → rien sauvegardé ─────────────────────────────────────

def test_ca5_cancel_rien_sauvegarde(db):
    """CA5 — perte_cancel → aucun événement, pending supprimé."""
    session, pid = db
    user_id = 46
    pending_dict = {user_id: {
        "item": {"action": "perte", "culture": "tomate", "quantite": 1},
        "texte": "perdu 1 tomate", "godets": [], "jardin_varietes": [],
        "ts": time.time(),
    }}
    update = _make_callback_update(user_id, "perte_cancel")

    with patch("bot._PERTE_PENDING", pending_dict):
        from bot import _handle_perte_callback
        _run(_handle_perte_callback(update, _make_ctx()))

    nb = session.query(Evenement).filter(
        Evenement.type_action.in_(["perte", "perte_godet"])
    ).count()
    assert nb == 0
    assert user_id not in pending_dict


# ── CA6 : timeout → rien sauvegardé ──────────────────────────────────────────

def test_ca6_timeout_rien_sauvegarde(db):
    """CA6 — pending expiré → rien sauvegardé."""
    session, pid = db
    user_id = 47
    pending_dict = {user_id: {
        "item": {"action": "perte", "culture": "tomate", "quantite": 1},
        "texte": "perdu 1 tomate", "godets": [], "jardin_varietes": [],
        "ts": time.time() - 9999,
    }}
    update = _make_callback_update(user_id, "perte_source:jardin")

    with patch("bot._PERTE_PENDING", pending_dict):
        from bot import _handle_perte_callback
        _run(_handle_perte_callback(update, _make_ctx()))

    nb = session.query(Evenement).filter(
        Evenement.type_action.in_(["perte", "perte_godet"])
    ).count()
    assert nb == 0
    msg = update.callback_query.edit_message_text.call_args[0][0]
    assert "expir" in msg.lower()


# ── CA7 : pending absent → pas de crash ──────────────────────────────────────

def test_ca7_pending_absent_pas_de_crash():
    """CA7 — _PERTE_PENDING vide → message gracieux, pas d'exception."""
    user_id = 48
    update  = _make_callback_update(user_id, "perte_source:jardin")

    with patch("bot._PERTE_PENDING", {}):
        from bot import _handle_perte_callback
        _run(_handle_perte_callback(update, _make_ctx()))

    update.callback_query.edit_message_text.assert_called_once()


# ── CA8 : update.message = None → pas de crash (regression) ─────────────────

def test_ca8_update_message_none_regression(db):
    """CA8 — Régression : update.message=None dans un callback ne crash pas."""
    session, pid = db
    session.add(Evenement(
        type_action="mise_en_godet", culture="tomate", variete="cerise",
        nb_plants_godets=3, nb_graines_semees=5, date=datetime(2026, 4, 1),
    ))
    session.commit()

    user_id = 49
    item    = {"action": "perte", "culture": "tomate", "variete": "cerise", "quantite": 1}
    state   = _build_pending(item, session)
    update  = _make_callback_update(user_id, "perte_source:pepiniere")

    assert update.message is None, "Ce test simule le cas réel : update.message doit être None"

    with patch("bot._PERTE_PENDING", {user_id: state}), \
         patch("bot.SessionLocal", return_value=session), \
         patch("bot.send_voice_reply", new_callable=AsyncMock):
        from bot import _handle_perte_callback
        _run(_handle_perte_callback(update, _make_ctx()))  # ne doit pas lever AttributeError

    # Et l'événement est bien sauvegardé malgré update.message = None
    ev = session.query(Evenement).filter_by(type_action="perte_godet").first()
    assert ev is not None, "Événement non sauvegardé quand update.message=None"


# ── Tests contexte intelligent (court-circuit) ───────────────────────────────

def _make_message_update(user_id: int, text: str):
    """Update mocké pour message texte (update.message n'est PAS None)."""
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_message = MagicMock()
    update.effective_message.reply_text = AsyncMock()
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    update.callback_query = None
    return update


def _setup_db_tomate(session, pid):
    """Crée une situation avec godets ET jardin pour tomate.

    [fix contrôle quantité perte] nb_plants_godets doit rester strictement
    supérieur à la quantité plantée : sinon stock_residuel_godet retombe à 0
    (tout a été repiqué), et le garde-fou de quantité rejette à raison toute
    perte en pépinière — ce test veut un stock godet réellement disponible.
    """
    session.add(Evenement(
        type_action="plantation", culture="tomate", variete="cerise",
        quantite=10.0, rang=1, unite="plants",
        parcelle_id=pid, date=datetime(2026, 5, 1),
    ))
    session.add(Evenement(
        type_action="mise_en_godet", culture="tomate", variete="cerise",
        nb_plants_godets=15, nb_graines_semees=20, date=datetime(2026, 4, 1),
    ))
    session.commit()


def test_cx1_contexte_pepiniere_dans_texte_sauvegarde_direct(db):
    """CX1 — 'pépinière' dans le texte → sauvegarde directe sans menu source."""
    session, pid = db
    _setup_db_tomate(session, pid)

    update = _make_message_update(999, "perte de 1 plant de tomate pépinière")
    item   = {"action": "perte", "culture": "tomate", "variete": None, "quantite": 1}

    with patch("bot.SessionLocal", return_value=session), \
         patch("bot.send_voice_reply", new_callable=AsyncMock), \
         patch("bot.AFTER_RECORD_KEYBOARD", MagicMock()):
        from bot import _parse_and_save
        _run(_parse_and_save(update, "perte de 1 plant de tomate pépinière", pre_parsed_items=[item]))

    ev = session.query(Evenement).filter_by(type_action="perte_godet").first()
    assert ev is not None, "Devrait être perte_godet sans menu car 'pépinière' dans texte"
    # Aucun menu ne doit avoir été affiché (pas de reply_text avec clavier inline)
    update.message.reply_text.assert_not_called()


def test_cx2_contexte_potager_dans_texte_sauvegarde_direct(db):
    """CX2 — 'au potager' dans le texte → sauvegarde directe sans menu source."""
    session, pid = db
    _setup_db_tomate(session, pid)

    update = _make_message_update(998, "perte de 1 plant de tomate au potager")
    item   = {"action": "perte", "culture": "tomate", "variete": None, "quantite": 1}

    with patch("bot.SessionLocal", return_value=session), \
         patch("bot.send_voice_reply", new_callable=AsyncMock), \
         patch("bot.AFTER_RECORD_KEYBOARD", MagicMock()):
        from bot import _parse_and_save
        _run(_parse_and_save(update, "perte de 1 plant de tomate au potager", pre_parsed_items=[item]))

    ev = session.query(Evenement).filter_by(type_action="perte").first()
    assert ev is not None, "Devrait être perte jardin sans menu car 'potager' dans texte"
    update.message.reply_text.assert_not_called()


def test_cx3_variete_fuzzy_match_typo(db):
    """CX3 — variété mal orthographiée → fuzzy match → sauvegarde avec variété correcte."""
    session, pid = db
    # 1 godet tomate cerise
    session.add(Evenement(
        type_action="mise_en_godet", culture="tomate", variete="cerise",
        nb_plants_godets=5, nb_graines_semees=8, date=datetime(2026, 4, 1),
    ))
    session.commit()

    update = _make_message_update(997, "perte de 1 tomate cerize pépinière")
    # Groq a mal orthographié "cerise" → "cerize"
    item = {"action": "perte", "culture": "tomate", "variete": "cerize", "quantite": 1}

    with patch("bot.SessionLocal", return_value=session), \
         patch("bot.send_voice_reply", new_callable=AsyncMock), \
         patch("bot.AFTER_RECORD_KEYBOARD", MagicMock()):
        from bot import _parse_and_save
        _run(_parse_and_save(update, "perte de 1 tomate cerize pépinière", pre_parsed_items=[item]))

    ev = session.query(Evenement).filter_by(type_action="perte_godet").first()
    assert ev is not None
    assert ev.variete == "cerise", f"Variété attendue 'cerise', obtenu '{ev.variete}'"


# ── Regression : perte sur variété "non précisée" (bug EN PLACE non déduit) ──
#
# `calcul_stock_par_variete()` substitue déjà variete=None par le libellé humain
# "Variété non précisée" dans son résultat. Ce libellé ne doit JAMAIS être réécrit
# tel quel dans Evenement.variete (sinon il ne matche plus la clé None utilisée
# par les plantations, et la perte devient invisible du calcul EN PLACE/PERDU).

def test_perte_auto_variete_unique_non_precisee_sauvegarde_none(db):
    """Une seule variété non précisée au jardin, aucun godet, aucun mot-clé de
    contexte dans le texte → auto-remplissage (bot.py section 7) doit sauvegarder
    variete=None, pas le libellé littéral 'Variété non précisée'."""
    session, pid = db
    session.add(Evenement(
        type_action="plantation", culture="tomate", variete=None,
        quantite=2.0, rang=1, unite="plants",
        parcelle_id=pid, date=datetime(2026, 5, 1),
    ))
    session.commit()

    user_id = 996
    update  = _make_message_update(user_id, "perte de 2 pieds de tomate")
    item    = {"action": "perte", "culture": "tomate", "variete": None, "quantite": 2}

    with patch("bot.SessionLocal", return_value=session), \
         patch("bot.send_voice_reply", new_callable=AsyncMock), \
         patch("bot.AFTER_RECORD_KEYBOARD", MagicMock()):
        from bot import _parse_and_save, _action_confirm_cb
        _run(_parse_and_save(update, "perte de 2 pieds de tomate", pre_parsed_items=[item]))

        # [US-021] Une seule parcelle plantée en tomate → auto-détectée, puis
        # confirmation demandée avant sauvegarde effective : on la valide ici.
        confirm_update = _make_callback_update(user_id, "action_confirm")
        _run(_action_confirm_cb(confirm_update, _make_ctx()))

    ev = session.query(Evenement).filter_by(type_action="perte").first()
    assert ev is not None
    assert ev.variete is None, (
        f"variete devrait être None, obtenu '{ev.variete}' — le libellé "
        "d'affichage a fuité dans les données stockées"
    )

    from utils.stock import calcul_stock_par_variete
    stock = calcul_stock_par_variete(session, "tomate")
    assert len(stock) == 1
    assert stock[0]["plants_perdus"] == 2.0
    assert stock[0]["plants_plantes"] - stock[0]["plants_perdus"] == 0.0


def test_perte_menu_jardin_variete_non_precisee_callback_sans_libelle(db):
    """Plusieurs variétés jardin dont une non précisée → le bouton correspondant
    doit utiliser le sentinel '__none__', jamais le libellé littéral, sinon un
    clic dessus réécrit le libellé en base (scénario exact du bug rapporté :
    5 variétés de tomate, menu inline, choix de la variété non précisée)."""
    session, pid = db
    session.add(Evenement(
        type_action="plantation", culture="tomate", variete=None,
        quantite=2.0, rang=1, unite="plants",
        parcelle_id=pid, date=datetime(2026, 5, 1),
    ))
    session.add(Evenement(
        type_action="plantation", culture="tomate", variete="cerise",
        quantite=3.0, rang=1, unite="plants",
        parcelle_id=pid, date=datetime(2026, 5, 1),
    ))
    session.commit()

    update = _make_message_update(995, "perte de 2 pieds de tomate")
    item   = {"action": "perte", "culture": "tomate", "variete": None, "quantite": 2}

    with patch("bot.SessionLocal", return_value=session), \
         patch("bot.send_voice_reply", new_callable=AsyncMock), \
         patch("bot.AFTER_RECORD_KEYBOARD", MagicMock()):
        from bot import _parse_and_save
        _run(_parse_and_save(update, "perte de 2 pieds de tomate", pre_parsed_items=[item]))

    update.message.reply_text.assert_called_once()
    _, kwargs = update.message.reply_text.call_args
    boutons = [b for row in kwargs["reply_markup"].inline_keyboard for b in row]
    callback_data = {b.callback_data for b in boutons}
    assert "perte_var_j:__none__" in callback_data
    assert not any("non précisée" in cb for cb in callback_data), (
        f"Le libellé d'affichage a fuité dans un callback_data : {callback_data}"
    )

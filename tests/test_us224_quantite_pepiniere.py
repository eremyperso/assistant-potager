"""
[US-224] Quantité obligatoire sur les opérations de pépinière.

Constaté le 14/10/2026 : une perte de godet déposée depuis la file (#596), des
mises en godet dictées (#588, #589, #593) étaient écrites SANS nombre de plants.
Aucun stock ne bougeait, le lot restait « indéterminé ».

- le service refuse la création sans quantité (règle 9) — jamais à la correction ;
- le plafond d'une sortie est celui du LOT cité, pas celui de la culture entière ;
- le bot pose la question avec ce que la base sait du lot (« Tout le lot : N ») ;
- un refus d'écriture laisse le geste dans la file ;
- la réponse (texte ou voix) n'avale pas une nouvelle saisie.
"""
import time
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import evenements as svc
from app.services.context import TenantContext
from database.models import Evenement


@pytest.fixture
def ctx():
    return TenantContext(user_id=1, potager_id=1, role="owner")


def _semis(db, ctx, culture="poireau", graines=100):
    ev = Evenement(
        type_action="semis", culture=culture, quantite=graines, unite="graines",
        potager_id=ctx.potager_id, date=datetime(2026, 8, 15),
    )
    db.add(ev)
    db.commit()
    return ev


def _godet(db, ctx, semis, plants, culture="poireau"):
    ev = Evenement(
        type_action="mise_en_godet", culture=culture, nb_plants_godets=plants,
        nb_graines_semees=plants, origine_graines_id=semis.id,
        potager_id=ctx.potager_id, date=datetime(2026, 9, 1),
    )
    db.add(ev)
    db.commit()
    return ev


# ══════════════════════════════════════════════════════════════════════════════
# Service — règle 9
# ══════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("action", ["perte_godet", "vendu"])
def test_service_refuse_la_creation_sans_quantite(test_db, ctx, action):
    semis = _semis(test_db, ctx)
    _godet(test_db, ctx, semis, 50)
    parsed = {"action": action, "culture": "poireau", "origine_graines_id": semis.id}

    with pytest.raises(svc.QuantiteManquanteError):
        svc.creer_evenement_confirme(test_db, ctx, parsed, "perte godet du lot 8", None)

    assert test_db.query(Evenement).filter(Evenement.type_action == action).count() == 0


def test_service_accepte_la_perte_avec_quantite_et_la_rattache_au_lot(test_db, ctx):
    semis = _semis(test_db, ctx)
    _godet(test_db, ctx, semis, 50)
    parsed = {"action": "perte_godet", "culture": "poireau", "quantite": 4, "unite": "plants",
              "origine_graines_id": semis.id}

    event = svc.creer_evenement_confirme(test_db, ctx, parsed, "perte godet 4 poireaux", None)

    assert event.quantite == 4
    assert event.origine_graines_id == semis.id


def test_service_refuse_une_quantite_nulle(test_db, ctx):
    semis = _semis(test_db, ctx)
    _godet(test_db, ctx, semis, 50)
    parsed = {"action": "perte_godet", "culture": "poireau", "quantite": 0, "origine_graines_id": semis.id}
    with pytest.raises(svc.QuantiteManquanteError):
        svc.creer_evenement_confirme(test_db, ctx, parsed, "perte godet 0", None)


def test_mise_en_godet_sans_plants_refusee_sauf_choix_explicite(test_db, ctx):
    semis = _semis(test_db, ctx)
    parsed = {"action": "mise_en_godet", "culture": "poireau", "origine_graines_id": semis.id}

    with pytest.raises(svc.QuantiteManquanteError):
        svc.creer_evenement_godet(test_db, ctx, dict(parsed), "mise en godet poireau")

    # « Je ne sais pas » : le bot pose `_plants_demandes`, le service l'accepte.
    parsed["_plants_demandes"] = True
    event = svc.creer_evenement_godet(test_db, ctx, parsed, "mise en godet poireau")
    assert event.nb_plants_godets is None


def test_deplacement_et_cloture_restent_sans_quantite(test_db, ctx):
    """Lot entier par construction : jamais soumis à la règle 9."""
    assert "deplacement" not in svc._ACTIONS_QUANTITE_OBLIGATOIRE
    assert "cloture_lot" not in svc._ACTIONS_QUANTITE_OBLIGATOIRE


def test_la_correction_d_un_ancien_evenement_sans_quantite_reste_possible(test_db, ctx):
    """La règle ne vaut qu'à la création : renommer la date d'un événement historique
    sans quantité ne doit pas être bloqué."""
    ancien = Evenement(
        type_action="perte_godet", culture="poireau", quantite=None, unite="plants",
        potager_id=ctx.potager_id, date=datetime(2026, 10, 14),
    )
    test_db.add(ancien)
    test_db.commit()

    # valider_evenement sans `a_la_creation` : aucune exception.
    svc.valider_evenement(
        test_db, ctx, action="perte_godet", culture="poireau", quantite=None, unite="plants",
    )


# ══════════════════════════════════════════════════════════════════════════════
# Service — plafond par lot
# ══════════════════════════════════════════════════════════════════════════════
def test_plafond_par_lot_et_non_par_culture(test_db, ctx):
    """Deux lots de poireau : 50 godets au lot A, 10 au lot B. Le stock agrégé (60)
    laisserait perdre 20 plants « du lot B » ; le plafond du lot cité, non."""
    lot_a = _semis(test_db, ctx, graines=100)
    lot_b = _semis(test_db, ctx, graines=20)
    _godet(test_db, ctx, lot_a, 50)
    _godet(test_db, ctx, lot_b, 10)
    parsed = {"action": "perte_godet", "culture": "poireau", "quantite": 20,
              "unite": "plants", "origine_graines_id": lot_b.id}

    with pytest.raises(svc.StockLotInsuffisantError) as exc:
        svc.creer_evenement_confirme(test_db, ctx, parsed, "perte godet 20 du lot B", None)

    assert "10" in str(exc.value)


# ══════════════════════════════════════════════════════════════════════════════
# Bot — la porte unique de la quantité
# ══════════════════════════════════════════════════════════════════════════════
def _update(uid):
    update = MagicMock()
    update.effective_user.id = uid
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    update.effective_message = update.message
    return update


@pytest.mark.parametrize("item,attendu", [
    ({"action": "perte_godet", "culture": "poireau"}, True),
    ({"action": "perte_godet", "culture": "poireau", "quantite": 3}, False),
    ({"action": "vendu", "culture": "chou"}, True),
    ({"action": "mise_en_godet", "culture": "chou"}, True),
    ({"action": "mise_en_godet", "culture": "chou", "nb_plants_godets": 30}, False),
    ({"action": "mise_en_godet", "culture": "chou", "_plants_demandes": True}, False),
    ({"action": "plantation", "culture": "chou"}, False),              # sans lot : CA9 générique
    ({"action": "plantation", "culture": "chou", "numero_lot_cite": 5}, True),
    ({"action": "deplacement", "culture": "chou", "origine_graines_id": 5}, False),
    ({"action": "cloture_lot", "culture": "chou", "origine_graines_id": 5}, False),
    ({"action": "recolte", "culture": "chou"}, False),
])
def test_quantite_pepiniere_manquante(item, attendu):
    from app.bot.godets import _quantite_pepiniere_manquante
    assert _quantite_pepiniere_manquante(item, "texte") is attendu


def test_perte_sans_contexte_pepiniere_garde_la_question_du_potager():
    from app.bot.godets import _quantite_pepiniere_manquante
    assert _quantite_pepiniere_manquante({"action": "perte", "culture": "tomate"}, "perdu des tomates") is False
    assert _quantite_pepiniere_manquante({"action": "perte", "culture": "tomate"}, "perdu des tomates en godet") is True


@pytest.mark.asyncio
async def test_perte_godet_de_la_file_demande_le_nombre_avec_le_stock_du_lot(monkeypatch):
    from app import bot as bot_module
    from app.bot import godets, saisie

    uid = 801
    saisie._QUANTITE_PENDING.pop(uid, None)
    lot = {"semis_id": 581, "numero_lot": 8, "date_semis": datetime(2026, 8, 15),
           "stock_residuel_godet": 50, "graines_en_germination": 0,
           "culture": "poireau", "variete": None}
    monkeypatch.setattr(godets, "_lot_pressenti_pour_sortie", lambda parsed: lot)
    update = _update(uid)
    geste_file = {"id": 34, "potager_id": 1, "user_id": uid, "position": 1, "total": 1}
    item = {"action": "perte_godet", "culture": "poireau", "unite": "plants", "quantite": None}

    try:
        with (
            patch("app.bot._normalize_items", side_effect=lambda items, texte: items),
            patch("app.bot.require_role"),
            patch("app.bot.current_context", return_value=SimpleNamespace(potager_id=1, user_id=uid)),
        ):
            await bot_module._parse_and_save(
                update, "perte godet de poireau", pre_parsed_items=[item], geste_file=geste_file,
            )

        attente = saisie._QUANTITE_PENDING[uid]
        assert attente["godet_plants"] is True
        assert attente["geste_file"] == geste_file
        assert attente["lot_propose"] == {"semis_id": 581, "reste": 50}
        boutons = update.message.reply_text.call_args.kwargs["reply_markup"].inline_keyboard
        assert [r[0].callback_data for r in boutons] == ["godetplants_all", "godetplants_cancel"]
        assert "il reste 50 plant(s) en godet" in update.message.reply_text.call_args[0][0]
    finally:
        saisie._QUANTITE_PENDING.pop(uid, None)


@pytest.mark.asyncio
async def test_perte_et_vente_n_offrent_pas_je_ne_sais_pas(monkeypatch):
    from app import bot as bot_module
    from app.bot import godets, saisie

    uid = 802
    saisie._QUANTITE_PENDING.pop(uid, None)
    monkeypatch.setattr(godets, "_lot_pressenti_pour_sortie", lambda parsed: None)
    update = _update(uid)
    item = {"action": "vendu", "culture": "chou", "quantite": None}
    try:
        with (
            patch("app.bot._normalize_items", side_effect=lambda items, texte: items),
            patch("app.bot.require_role"),
            patch("app.bot.current_context", return_value=SimpleNamespace(potager_id=1, user_id=uid)),
        ):
            await bot_module._parse_and_save(update, "vendu des choux", pre_parsed_items=[item])
        boutons = update.message.reply_text.call_args.kwargs["reply_markup"].inline_keyboard
        donnees = [r[0].callback_data for r in boutons]
        assert "godetplants_skip" not in donnees
        assert donnees == ["godetplants_cancel"]
    finally:
        saisie._QUANTITE_PENDING.pop(uid, None)


@pytest.mark.asyncio
async def test_tout_le_lot_pour_une_perte_pose_la_quantite_et_le_lot(monkeypatch):
    from app.bot import godets, saisie
    import app.bot.saisie as saisie_mod

    espion = AsyncMock()
    monkeypatch.setattr(saisie_mod, "_parse_and_save", espion)
    uid = 803
    saisie._QUANTITE_PENDING[uid] = {
        "items": [{"action": "perte_godet", "culture": "poireau"}],
        "texte": "perte godet de poireau", "ts": time.time(), "geste_file": None,
        "godet_plants": True, "lot_propose": {"semis_id": 581, "reste": 50},
    }
    query = MagicMock(data="godetplants_all")
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update = SimpleNamespace(callback_query=query, effective_user=SimpleNamespace(id=uid))
    try:
        await godets._godet_plants_cb(update, SimpleNamespace(user_data={}))
    finally:
        saisie._QUANTITE_PENDING.pop(uid, None)

    item = espion.await_args.kwargs["pre_parsed_items"][0]
    assert item["quantite"] == 50 and item["unite"] == "plants"
    assert item["origine_graines_id"] == 581
    assert "nb_plants_godets" not in item


# ══════════════════════════════════════════════════════════════════════════════
# Réponse texte / voix
# ══════════════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
@pytest.mark.parametrize("reponse,attendu", [("30", 30), ("30 plants", 30), ("environ 20", 20)])
async def test_reponse_numerique_pose_la_quantite_d_une_perte(monkeypatch, reponse, attendu):
    from app.bot import messages, saisie

    espion = AsyncMock()
    monkeypatch.setattr(messages, "_parse_and_save", espion)
    uid = 811
    saisie._QUANTITE_PENDING[uid] = {
        "items": [{"action": "perte_godet", "culture": "poireau"}],
        "texte": "perte godet", "ts": time.time(), "geste_file": None, "godet_plants": True,
    }
    update = SimpleNamespace(
        message=SimpleNamespace(text=reponse, reply_text=AsyncMock()),
        effective_user=SimpleNamespace(id=uid),
    )
    try:
        consomme = await messages._repondre_quantite_en_attente(update, reponse)
    finally:
        saisie._QUANTITE_PENDING.pop(uid, None)

    assert consomme is True
    item = espion.await_args.kwargs["pre_parsed_items"][0]
    assert item["quantite"] == attendu and item["unite"] == "plants"


@pytest.mark.asyncio
async def test_une_nouvelle_dictee_n_est_pas_avalee_comme_quantite(monkeypatch):
    """« récolté 2 kg de tomates » n'est pas la réponse « 2 plants »."""
    from app.bot import messages, saisie

    espion = AsyncMock()
    monkeypatch.setattr(messages, "_parse_and_save", espion)
    uid = 812
    saisie._QUANTITE_PENDING[uid] = {
        "items": [{"action": "perte_godet", "culture": "poireau"}],
        "texte": "perte godet", "ts": time.time(), "geste_file": None, "godet_plants": True,
    }
    update = SimpleNamespace(
        message=SimpleNamespace(text="j'ai récolté 2 kg de tomates", reply_text=AsyncMock()),
        effective_user=SimpleNamespace(id=uid),
    )
    try:
        consomme = await messages._repondre_quantite_en_attente(update, "j'ai récolté 2 kg de tomates")
        reste = uid in saisie._QUANTITE_PENDING
    finally:
        saisie._QUANTITE_PENDING.pop(uid, None)

    assert consomme is False
    assert reste is False                    # la question est abandonnée
    espion.assert_not_awaited()


@pytest.mark.asyncio
async def test_question_perimee_n_avale_pas_le_message(monkeypatch):
    from app.bot import messages, saisie

    uid = 813
    saisie._QUANTITE_PENDING[uid] = {
        "items": [{"action": "perte_godet", "culture": "poireau"}],
        "texte": "perte godet", "ts": time.time() - 10_000, "geste_file": None, "godet_plants": True,
    }
    update = SimpleNamespace(
        message=SimpleNamespace(text="5", reply_text=AsyncMock()),
        effective_user=SimpleNamespace(id=uid),
    )
    try:
        consomme = await messages._repondre_quantite_en_attente(update, "5")
    finally:
        saisie._QUANTITE_PENDING.pop(uid, None)
    assert consomme is False


@pytest.mark.asyncio
async def test_nombre_non_reconnu_redemande_sans_perdre_la_question():
    from app.bot import messages, saisie

    uid = 814
    saisie._QUANTITE_PENDING[uid] = {
        "items": [{"action": "perte_godet", "culture": "poireau"}],
        "texte": "perte godet", "ts": time.time(), "geste_file": None, "godet_plants": True,
    }
    reply = AsyncMock()
    update = SimpleNamespace(
        message=SimpleNamespace(text="beaucoup", reply_text=reply),
        effective_user=SimpleNamespace(id=uid),
    )
    try:
        consomme = await messages._repondre_quantite_en_attente(update, "beaucoup")
        reste = uid in saisie._QUANTITE_PENDING
    finally:
        saisie._QUANTITE_PENDING.pop(uid, None)
    assert consomme is True and reste is True
    assert "non reconnu" in reply.await_args.args[0]


# ══════════════════════════════════════════════════════════════════════════════
# File — un refus d'écriture ne retire pas le geste
# ══════════════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_refus_d_ecriture_laisse_le_geste_dans_la_file(monkeypatch):
    from app.bot import enregistrement
    from app.services import file_gestes as svc_file

    confirmes = []
    monkeypatch.setattr(svc_file, "confirmer", lambda g: confirmes.append(g.id))
    monkeypatch.setattr(enregistrement, "_do_save_items", AsyncMock(return_value=False))

    uid = 821
    geste_file = {"id": 40, "potager_id": 1, "user_id": uid, "position": 1, "total": 1}
    enregistrement._ACTION_PENDING[uid] = {
        "items": [{"action": "perte_godet", "culture": "poireau", "quantite": 99}],
        "texte": "perte godet 99", "ts": time.time(), "geste_file": geste_file,
    }
    query = MagicMock(data="action_confirm")
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(
        callback_query=query, effective_user=SimpleNamespace(id=uid), effective_message=message,
    )
    try:
        await enregistrement._action_confirm_cb(update, SimpleNamespace(user_data={}))
    finally:
        enregistrement._ACTION_PENDING.pop(uid, None)

    assert confirmes == []
    assert "reste dans votre file" in message.reply_text.await_args.args[0]


# ══════════════════════════════════════════════════════════════════════════════
# Audit de l'existant — lecture seule
# ══════════════════════════════════════════════════════════════════════════════
def test_audit_liste_les_evenements_sans_nombre_de_plants(test_db, ctx):
    semis = _semis(test_db, ctx)
    sans = [
        Evenement(type_action="perte_godet", culture="poireau", quantite=None, unite="plants",
                  origine_graines_id=semis.id, potager_id=1, date=datetime(2026, 10, 14)),
        Evenement(type_action="mise_en_godet", culture="poireau", nb_plants_godets=None,
                  origine_graines_id=semis.id, potager_id=1, date=datetime(2026, 10, 14)),
    ]
    avec = [
        Evenement(type_action="perte_godet", culture="poireau", quantite=3, unite="plants",
                  potager_id=1, date=datetime(2026, 10, 14)),
        Evenement(type_action="deplacement", culture="poireau", quantite=None,
                  origine_graines_id=semis.id, potager_id=1, date=datetime(2026, 10, 14)),
        Evenement(type_action="perte_godet", culture="poireau", quantite=None,
                  potager_id=2, date=datetime(2026, 10, 14)),         # un autre potager
    ]
    test_db.add_all(sans + avec)
    test_db.commit()

    trouves = svc.evenements_pepiniere_sans_quantite(test_db, ctx)

    assert {e.id for e in trouves} == {e.id for e in sans}
    assert test_db.query(Evenement).count() == 1 + len(sans) + len(avec)   # rien n'a été écrit

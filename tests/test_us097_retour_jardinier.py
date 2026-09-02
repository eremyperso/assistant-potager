"""
tests/test_us097_retour_jardinier.py
[US-097] Retour du jardinier sur une réponse de savoir/raisonnement

Couverture :
  CA9  : boutons 👍/👎 uniquement pour les réponses de savoir/raisonnement
  CA10 : le retour est rattaché à l'entrée de journal correspondante
  CA11 : facultatif, ne bloque rien, jamais redemandé (contrainte UNIQUE)
  CA12 : liste des questions les plus souvent jugées mauvaises
  CA13 : aucun 👎 ne déclenche de nouvel appel modèle
  CA3  : purge d'un potager → ses entrées de journal ET ses avis disparaissent
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services import potagers as svc_potagers
from app.services import retours as svc_retours
from app.services.context import TenantContext
from database.models import RoutageLog, RoutageRetour, User
from llm import routeur

CTX = TenantContext(user_id=1, potager_id=1, role="owner")


class _SessionPartagee:
    """Enrobe `test_db` en neutralisant `.close()` : le code applicatif ferme
    sa session en fin d'appel (une `SessionLocal()` par appel, en production),
    ce qui détacherait la session de test partagée entre plusieurs appels d'un
    même test si on la laissait faire."""

    def __init__(self, session):
        self._session = session

    def close(self):
        pass

    def __getattr__(self, nom):
        return getattr(self._session, nom)


def _log(db, potager_id=1, **kwargs):
    defaults = dict(
        potager_id=potager_id, question_normalisee="pourquoi mes tomates jaunissent",
        nature=routeur.NATURE_QUESTION_SAVOIR, origine_classification=routeur.ORIGINE_REGLE,
        etage_resolveur=routeur.ETAGE_RAISONNEMENT, cascade_remontee=False,
        confiance=1.0, latence_ms=100, tokens_consommes=50,
    )
    defaults.update(kwargs)
    ligne = RoutageLog(**defaults)
    db.add(ligne)
    db.commit()
    db.refresh(ligne)
    return ligne


# ─────────────────────────────────────────────────────────────────────────────
# CA9, CA10, CA11 — service app.services.retours
# ─────────────────────────────────────────────────────────────────────────────

def test_us097_ca9_enregistrer_retour_positif(test_db):
    ligne = _log(test_db)
    retour = svc_retours.enregistrer_retour(test_db, potager_id=1, routage_log_id=ligne.id, avis="positif")
    assert retour.avis == "positif"


def test_us097_ca10_retour_rattache_a_lentree_de_journal(test_db):
    """CA10 : relier un avis à l'étage, à la confiance et à l'origine qui ont
    produit la réponse — le rattachement se fait par routage_log_id."""
    ligne = _log(test_db, etage_resolveur=routeur.ETAGE_RAISONNEMENT, confiance=0.4)
    retour = svc_retours.enregistrer_retour(test_db, potager_id=1, routage_log_id=ligne.id, avis="negatif")

    assert retour.routage_log_id == ligne.id
    rattache = test_db.query(RoutageLog).filter(RoutageLog.id == retour.routage_log_id).one()
    assert rattache.etage_resolveur == routeur.ETAGE_RAISONNEMENT
    assert rattache.confiance == pytest.approx(0.4)


def test_us097_ca11_avis_deja_enregistre_leve_erreur(test_db):
    """CA11 : jamais redemandé pour la même réponse — contrainte UNIQUE réelle,
    pas seulement une convention côté interface."""
    ligne = _log(test_db)
    svc_retours.enregistrer_retour(test_db, potager_id=1, routage_log_id=ligne.id, avis="positif")

    with pytest.raises(svc_retours.RetourDejaEnregistreError):
        svc_retours.enregistrer_retour(test_db, potager_id=1, routage_log_id=ligne.id, avis="negatif")

    # Un seul avis subsiste, c'est bien le premier.
    assert test_db.query(RoutageRetour).filter(RoutageRetour.routage_log_id == ligne.id).count() == 1


def test_us097_isolation_inter_potagers_routage_log_introuvable(test_db):
    """Invariant projet : isolation inter-potagers — un avis ne peut pas être
    déposé sur l'entrée de journal d'un AUTRE potager."""
    ligne = _log(test_db, potager_id=1)

    with pytest.raises(svc_retours.RoutageLogIntrouvableError):
        svc_retours.enregistrer_retour(test_db, potager_id=2, routage_log_id=ligne.id, avis="positif")


def test_us097_avis_invalide_leve_valueerror(test_db):
    ligne = _log(test_db)
    with pytest.raises(ValueError):
        svc_retours.enregistrer_retour(test_db, potager_id=1, routage_log_id=ligne.id, avis="neutre")


# ─────────────────────────────────────────────────────────────────────────────
# CA9 — boutons proposés uniquement pour savoir/raisonnement (bot.py)
# ─────────────────────────────────────────────────────────────────────────────

def _make_update():
    update = MagicMock()
    update.effective_user.id = 42
    msg = MagicMock()
    msg.edit_text = AsyncMock()
    update.message = MagicMock()
    update.message.reply_text = AsyncMock(return_value=msg)
    return update, msg


def _boutons_retour_proposes(update) -> bool:
    for appel in update.message.reply_text.call_args_list:
        markup = appel.kwargs.get("reply_markup")
        if markup is not None and getattr(markup, "inline_keyboard", None):
            callbacks = [b.callback_data for ligne in markup.inline_keyboard for b in ligne]
            if any(cb.startswith("retour_routage:") for cb in callbacks):
                return True
    return False


@pytest.mark.asyncio
async def test_us097_ca9_boutons_proposes_pour_reponse_raisonnement():
    import bot

    update, _ = _make_update()
    resultat = routeur.ReponseCascade(texte="Réponse savante.", etage_resolveur=routeur.ETAGE_RAISONNEMENT, routage_log_id=7)

    with (
        patch("bot.current_context", return_value=CTX),
        patch("bot.routeur.repondre_avec_cascade", return_value=resultat),
        patch("bot.send_voice_reply", new=AsyncMock()),
    ):
        await bot._ask_question(update, "pourquoi mes tomates jaunissent ?")

    assert _boutons_retour_proposes(update)


@pytest.mark.asyncio
async def test_us097_ca9_pas_de_boutons_pour_reponse_donnee():
    import bot

    update, _ = _make_update()
    resultat = routeur.ReponseCascade(texte="4 kg de tomates.", etage_resolveur=routeur.ETAGE_DONNEE, routage_log_id=8)

    with (
        patch("bot.current_context", return_value=CTX),
        patch("bot.routeur.repondre_avec_cascade", return_value=resultat),
        patch("bot.send_voice_reply", new=AsyncMock()),
    ):
        await bot._ask_question(update, "combien de tomates ai-je récolté ?")

    assert not _boutons_retour_proposes(update)


@pytest.mark.asyncio
async def test_us097_pas_de_boutons_si_journal_non_ecrit():
    """routage_log_id absent (écriture du journal en échec) : rien à
    rattacher (CA10), donc pas de boutons proposés."""
    import bot

    update, _ = _make_update()
    resultat = routeur.ReponseCascade(texte="Réponse savante.", etage_resolveur=routeur.ETAGE_RAISONNEMENT, routage_log_id=None)

    with (
        patch("bot.current_context", return_value=CTX),
        patch("bot.routeur.repondre_avec_cascade", return_value=resultat),
        patch("bot.send_voice_reply", new=AsyncMock()),
    ):
        await bot._ask_question(update, "pourquoi mes tomates jaunissent ?")

    assert not _boutons_retour_proposes(update)


# ─────────────────────────────────────────────────────────────────────────────
# CA9, CA11, CA13 — callback Telegram _retour_routage_cb
# ─────────────────────────────────────────────────────────────────────────────

def _make_callback_update(data: str):
    update = MagicMock()
    update.effective_user.id = 42
    update.callback_query = AsyncMock()
    update.callback_query.data = data
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    return update


@pytest.mark.asyncio
async def test_us097_ca9_callback_avis_positif_enregistre(test_db):
    import bot

    ligne = _log(test_db)
    update = _make_callback_update(f"retour_routage:positif:{ligne.id}")

    with (
        patch("bot.SessionLocal", lambda: _SessionPartagee(test_db)),
        patch("bot.current_context", return_value=CTX),
    ):
        await bot._retour_routage_cb(update, MagicMock())

    update.callback_query.answer.assert_awaited_once()
    update.callback_query.edit_message_text.assert_awaited_once()
    assert test_db.query(RoutageRetour).filter(RoutageRetour.routage_log_id == ligne.id).one().avis == "positif"


@pytest.mark.asyncio
async def test_us097_ca13_callback_avis_negatif_naucun_appel_modele(test_db):
    """CA13 : un 👎 n'appelle jamais un modèle plus gros — pur point d'écriture."""
    import bot

    ligne = _log(test_db)
    update = _make_callback_update(f"retour_routage:negatif:{ligne.id}")

    with (
        patch("bot.SessionLocal", lambda: _SessionPartagee(test_db)),
        patch("bot.current_context", return_value=CTX),
        patch("llm.passerelle.appeler_chat") as mock_llm,
    ):
        await bot._retour_routage_cb(update, MagicMock())

    mock_llm.assert_not_called()
    assert test_db.query(RoutageRetour).filter(RoutageRetour.routage_log_id == ligne.id).one().avis == "negatif"


@pytest.mark.asyncio
async def test_us097_ca11_callback_double_clic_message_deja_enregistre(test_db):
    import bot

    ligne = _log(test_db)
    update1 = _make_callback_update(f"retour_routage:positif:{ligne.id}")
    update2 = _make_callback_update(f"retour_routage:positif:{ligne.id}")

    with patch("bot.SessionLocal", lambda: _SessionPartagee(test_db)), patch("bot.current_context", return_value=CTX):
        await bot._retour_routage_cb(update1, MagicMock())
        await bot._retour_routage_cb(update2, MagicMock())

    # [CA11] Un seul avis en base malgré le double clic.
    assert test_db.query(RoutageRetour).filter(RoutageRetour.routage_log_id == ligne.id).count() == 1
    texte_second_appel = update2.callback_query.edit_message_text.call_args[0][0]
    assert "déjà" in texte_second_appel.lower()


@pytest.mark.asyncio
async def test_us097_callback_donnees_invalides_ne_leve_pas():
    import bot

    update = _make_callback_update("retour_routage:pas_un_format_valide")
    await bot._retour_routage_cb(update, MagicMock())
    update.callback_query.edit_message_text.assert_awaited_once()


# ─────────────────────────────────────────────────────────────────────────────
# CA12 — liste des questions les plus souvent jugées mauvaises
# ─────────────────────────────────────────────────────────────────────────────

def test_us097_ca12_top_questions_mal_notees(test_db):
    from app.services import metriques_routage as svc_metriques

    l1 = _log(test_db, question_normalisee="pourquoi mes tomates jaunissent")
    l2 = _log(test_db, question_normalisee="pourquoi mes tomates jaunissent")
    l3 = _log(test_db, question_normalisee="comment planter des radis")
    svc_retours.enregistrer_retour(test_db, 1, l1.id, "negatif")
    svc_retours.enregistrer_retour(test_db, 1, l2.id, "negatif")
    svc_retours.enregistrer_retour(test_db, 1, l3.id, "positif")

    top = svc_metriques.top_questions_mal_notees(test_db)

    assert top[0]["question_normalisee"] == "pourquoi mes tomates jaunissent"
    assert top[0]["nb_avis_negatifs"] == 2
    assert all(q["question_normalisee"] != "comment planter des radis" for q in top)


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint web POST /routage/{id}/retour — appel direct de la fonction
# (TestClient + SQLite mémoire multi-thread est une limitation préexistante
# de ce projet, voir tests/test_us097_routage_logs.py::TestCA7AccesAdministrateur)
# ─────────────────────────────────────────────────────────────────────────────

class TestEndpointWebRetour:

    def test_us097_web_retour_positif_ok(self, test_db):
        import main
        ligne = _log(test_db)

        with patch("main.SessionLocal", return_value=_SessionPartagee(test_db)):
            reponse = main.deposer_retour_routage(
                ligne.id, main.RetourRequest(avis="positif"), ctx=CTX,
            )
        assert reponse == {"ok": True}

    def test_us097_web_retour_avis_invalide_400(self, test_db):
        import main
        ligne = _log(test_db)

        with patch("main.SessionLocal", return_value=_SessionPartagee(test_db)):
            with pytest.raises(HTTPException) as err:
                main.deposer_retour_routage(ligne.id, main.RetourRequest(avis="neutre"), ctx=CTX)
        assert err.value.status_code == 400

    def test_us097_web_retour_introuvable_404(self, test_db):
        import main

        with patch("main.SessionLocal", return_value=_SessionPartagee(test_db)):
            with pytest.raises(HTTPException) as err:
                main.deposer_retour_routage(999, main.RetourRequest(avis="positif"), ctx=CTX)
        assert err.value.status_code == 404

    def test_us097_web_retour_deja_enregistre_409(self, test_db):
        import main
        ligne = _log(test_db)

        with patch("main.SessionLocal", return_value=_SessionPartagee(test_db)):
            main.deposer_retour_routage(ligne.id, main.RetourRequest(avis="positif"), ctx=CTX)
            with pytest.raises(HTTPException) as err:
                main.deposer_retour_routage(ligne.id, main.RetourRequest(avis="negatif"), ctx=CTX)
        assert err.value.status_code == 409


# ─────────────────────────────────────────────────────────────────────────────
# CA3 — Suppression d'un potager : journal ET avis disparaissent avec lui
# ─────────────────────────────────────────────────────────────────────────────

def test_us097_ca3_purge_potager_efface_routage_logs_et_retours(test_db):
    """Scénario Gherkin « Suppression d'un potager »."""
    owner = User(email="owner@example.com", mot_de_passe_hash="x")
    test_db.add(owner)
    test_db.commit()
    potager = svc_potagers.creer_potager(test_db, owner.id, "Jardin condamné")

    ligne = _log(test_db, potager_id=potager.id)
    svc_retours.enregistrer_retour(test_db, potager.id, ligne.id, "negatif")

    resultat = svc_potagers.purger_potager(test_db, potager.id)

    assert resultat["volumes"]["routage_logs"] == 1
    assert resultat["volumes"]["routage_retours"] == 1
    assert test_db.query(RoutageLog).filter(RoutageLog.potager_id == potager.id).count() == 0
    assert test_db.query(RoutageRetour).filter(RoutageRetour.potager_id == potager.id).count() == 0

"""
tests/test_us286_agent_voit_messages_envoyes.py — Montrer à l'agent ce que le bot a envoyé de lui-même [US-286]
=============================================================================================================
Le 01/11/2026, la file de gestes (US-224) a purgé un geste et l'a annoncé ; vingt-cinq secondes plus
tard le jardinier écrit « vide le geste » et l'agent y lit « effacer le dernier geste du carnet ».

* **CA1** — l'invitation, la relance, l'avertissement et la purge de la file entrent dans la
  conversation (`echanges_conversation.signal`) et dans les échanges que reçoit l'agent ;
* **CA2** — l'agent lit la file (`lire(quoi="gestes_en_attente")`) et peut proposer d'abandonner un
  geste, confirmé au bouton ;
* **CA3** — « vide le geste » juste après une purge : rien en attente, aucune écriture ;
* **CA4** — « vide le geste » avec un geste en attente : un abandon proposé, jamais une annulation du carnet ;
* **CA5** — les outils d'US-272 ne changent pas ;
* **CA7** — aucun appel au modèle réel : la passerelle est simulée.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app import config
from app.bot import file_gestes as bot_file
from app.bot import interpretation as bot_interpretation
from app.services import file_gestes as svc
from app.services import interpreteur_commandes as interp
from app.services import relances_file as svc_relances
from app.services import telegram_notify as svc_notify
from app.services.agent import catalogue_outils, contexte_court, interpreteur_agent, lecture
from app.services.agent.catalogue_outils import OUTIL_ABANDONNER, OUTIL_ANNULER_ACTION, OUTIL_LIRE, OUTILS_DECISION
from app.services.compagnon import conversations, decisions, file_agent
from app.services.context import TenantContext
from database.models import (
    CultureConfig, EchangeConversation, Evenement, Parcelle, Potager, PotagerMembre, User,
)
from llm import passerelle
from llm.passerelle import AppelOutil, ReponseOutils

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
PARCELLES = ("Carré nord", "Serre")
ANNONCE_PURGE = "1 geste vidé : il n'avait pas été confirmé"


# ── Outillage ────────────────────────────────────────────────────────────────
@pytest.fixture
def db(test_db, monkeypatch):
    test_db.add_all([User(id=1, email="camille@potager.test"), User(id=2, email="dominique@potager.test")])
    test_db.flush()
    test_db.add_all([Potager(id=1, nom="Jardin A", proprietaire_id=1), Potager(id=2, nom="Jardin B", proprietaire_id=2)])
    test_db.flush()
    test_db.add_all([
        PotagerMembre(user_id=1, potager_id=1, role="owner"),
        PotagerMembre(user_id=2, potager_id=2, role="owner"),
        Parcelle(id=1, nom="carré nord", nom_normalise="carrenord", potager_id=1),
        CultureConfig(nom="tomate", type_organe_recolte="reproducteur", potager_id=None),
        CultureConfig(nom="epinard", type_organe_recolte="vegetatif", potager_id=None),
    ])
    test_db.commit()
    monkeypatch.setattr(svc, "SessionLocal", lambda: test_db)
    monkeypatch.setattr(test_db, "close", lambda: None)
    monkeypatch.setattr("database.db.SessionLocal", lambda: test_db)
    return test_db


@pytest.fixture
def envois(monkeypatch):
    envoyes: list[tuple] = []

    def _envoyer(chat_id, texte, boutons=None, parse_mode=None):
        envoyes.append((chat_id, texte, boutons))
        return 1000 + len(envoyes)

    monkeypatch.setattr(svc_notify, "envoyer", _envoyer)
    monkeypatch.setattr(svc_notify, "editer_message", lambda *a, **k: True)
    return SimpleNamespace(envoyes=envoyes)


@pytest.fixture
def modele():
    with patch.object(passerelle, "appeler_chat_outils") as faux:
        yield faux


@pytest.fixture
def agent(monkeypatch):
    monkeypatch.setattr(config, "AGENT_MODE", "actif")
    monkeypatch.setattr(interpreteur_agent, "noms_parcelles_du_potager", lambda ctx: PARCELLES)
    monkeypatch.setattr(interpreteur_agent, "voisin_en_base", lambda ctx: (lambda nom: None))


def _reponse(*appels: AppelOutil, texte: str = "") -> ReponseOutils:
    return ReponseOutils(
        texte=texte, modele="test", appel_type=passerelle.TYPE_AGENT,
        tokens_in=900, tokens_out=50, latence_ms=400, appels=appels, statut=passerelle.STATUT_OK,
    )


def _lier(db, chat_id: int = 555) -> None:
    db.query(User).filter(User.id == 1).first().telegram_chat_id = chat_id
    db.commit()


def _deposer(db, culture: str = "tomate", maintenant: datetime | None = None):
    return svc.deposer_geste(db, CTX, action="semis", culture=culture, maintenant=maintenant).geste


def _signaux() -> list[str]:
    from database.models import EchangeConversation as E

    with conversations._session(1) as session:
        return [e.signal for e in session.query(E).order_by(E.id).all()]


def _noms_offerts(modele) -> set[str]:
    return {outil["function"]["name"] for outil in modele.call_args.kwargs["outils"]}


def _purger_un_geste(db) -> None:
    depot = datetime.utcnow() - timedelta(days=3, minutes=1)
    _deposer(db, maintenant=depot)
    vides = [g for g in svc.gestes_perimes(db, datetime.utcnow()) if svc.perimer(g)]
    assert svc_relances.notifier_purge(db, 1, vides) is True


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — tout message envoyé par le bot de lui-même entre dans la conversation
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1MessagesEnvoyesDansLaConversation:

    def test_us286_ca1_la_purge_entre_dans_la_conversation(self, db, envois):
        _lier(db)
        _purger_un_geste(db)
        assert _signaux() == ["file:purge"]
        recents = conversations.recents(CTX)
        assert len(recents) == 1 and recents[0].texte == ""
        assert "a été vidé" in recents[0].resume and "tomate" in recents[0].resume
        assert "*" not in recents[0].resume, "le message est relu comme du texte, sans Markdown"

    def test_us286_ca1_l_avertissement_entre_dans_la_conversation(self, db, envois):
        _lier(db)
        depot = datetime(2026, 9, 21, 10, 0)
        _deposer(db, maintenant=depot)
        echeance = depot + timedelta(days=3) - timedelta(hours=2)
        assert svc_relances.avertir(db, 1, svc.gestes_a_avertir(db, echeance), maintenant=echeance) is True
        assert _signaux() == ["file:avertissement"]

    def test_us286_ca1_l_invitation_et_la_relance_entrent_dans_la_conversation(self, db, envois):
        _lier(db)
        depot = svc.deposer_geste(db, CTX, action="semis", culture="tomate")
        assert svc_relances.inviter_si_premier_depot(db, 1, depot) is True
        assert _signaux() == ["file:invitation"]

        ligne = svc_relances.reglage(db, 1)
        ligne.derniere_relance_le = None
        ligne.derniere_activite_le = None
        db.commit()
        creneau = datetime.utcnow().replace(hour=svc_relances.CRENEAUX_RELANCE[0], minute=0)
        assert svc_relances.relancer(db, 1, maintenant=creneau) is True
        assert _signaux() == ["file:invitation", "file:relance"]

    def test_us286_ca1_un_envoi_perdu_n_entre_pas_dans_la_conversation(self, db, monkeypatch):
        _lier(db)
        monkeypatch.setattr(svc_notify, "envoyer", lambda *a, **k: None)
        depot = datetime.utcnow() - timedelta(days=3, minutes=1)
        _deposer(db, maintenant=depot)
        vides = [g for g in svc.gestes_perimes(db, datetime.utcnow()) if svc.perimer(g)]
        assert svc_relances.notifier_purge(db, 1, vides) is False
        assert _signaux() == []

    def test_us286_ca1_une_memoire_illisible_ne_fait_pas_echouer_l_envoi(self, db, envois, monkeypatch):
        _lier(db)
        monkeypatch.setattr(conversations, "noter", MagicMock(side_effect=RuntimeError("base KO")))
        depot = datetime.utcnow() - timedelta(days=3, minutes=1)
        _deposer(db, maintenant=depot)
        vides = [g for g in svc.gestes_perimes(db, datetime.utcnow()) if svc.perimer(g)]
        assert svc_relances.notifier_purge(db, 1, vides) is True

    def test_us286_ca1_le_message_est_retenu_dans_le_potager_du_geste(self, db, envois):
        _lier(db)
        _purger_un_geste(db)
        assert conversations.recents(TenantContext(user_id=1, potager_id=2, role="owner")) == ()

    def test_us286_ca1_le_message_spontane_reste_note_avec_son_signal(self):
        """US-267 : déjà noté à l'envoi (distribution.py) — la chaîne `spontane:<id>` n'a pas bougé."""
        import inspect

        from app.services.compagnon import distribution

        assert 'signal=f"spontane:{message.id}"' in inspect.getsource(distribution._envoyer_message)


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — l'agent lit la file
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2LectureDeLaFile:

    def test_us286_ca2_la_lecture_existe_et_ne_compte_pas_dans_le_plafond(self):
        assert "gestes_en_attente" in catalogue_outils.LECTURES
        assert catalogue_outils.controler_parite_outils() == []

    def test_us286_ca2_lire_rend_les_gestes_qui_attendent(self, db):
        geste = _deposer(db)
        _deposer(db, culture="epinard")
        import json

        donnees = json.loads(lecture.lire({"quoi": "gestes_en_attente"}, CTX))["donnees"]
        assert len(donnees) == 2 and donnees[0]["id"] == geste.code
        assert donnees[0]["culture"] == "tomate" and "tomate" in donnees[0]["geste"]
        filtre = json.loads(lecture.lire({"quoi": "gestes_en_attente", "nom": "epinard"}, CTX))["donnees"]
        assert [g["culture"] for g in filtre] == ["epinard"]

    def test_us286_ca2_la_file_d_un_autre_compte_n_est_pas_lue(self, db):
        svc.deposer_geste(db, TenantContext(user_id=2, potager_id=2, role="owner"), action="semis", culture="tomate")
        import json

        assert json.loads(lecture.lire({"quoi": "gestes_en_attente"}, CTX))["donnees"] == []


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — « vide le geste » juste après une purge
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3ApresUnePurge:

    def test_us286_ca3_l_agent_voit_la_purge_et_repond_sans_rien_ecrire(self, db, envois, agent, modele):
        _lier(db)
        _purger_un_geste(db)
        court = contexte_court.construire(CTX, echanges=conversations.recents(CTX))
        assert court is not None and "vidé" in court.echanges[-1].resume

        reponse_finale = "Ce geste vient d'être retiré de ta file : il n'y a plus rien en attente."
        modele.side_effect = [
            _reponse(AppelOutil(OUTIL_LIRE, {"quoi": "gestes_en_attente"})),
            _reponse(texte=reponse_finale),
        ]
        resultat = interp.interpreter("vide le geste", CTX, contexte_court=court)

        assert getattr(resultat, "proposition", None) is None and resultat.decision is None
        assert "retiré" in resultat.texte and "rien" in resultat.texte
        # La file est vide : aucun outil d'abandon n'est offert, et rien n'a été écrit au carnet.
        assert OUTIL_ABANDONNER not in _noms_offerts(modele)
        assert db.query(Evenement).count() == 0

    def test_us286_ca3_sans_file_aucun_outil_d_abandon_n_est_offert(self, db, agent, modele):
        modele.return_value = _reponse(texte="Rien n'attend dans ta file.")
        interp.interpreter("vide le geste", CTX)
        assert OUTIL_ABANDONNER not in _noms_offerts(modele)


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — « vide le geste » avec un geste en attente
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4GesteEnAttente:

    def test_us286_ca4_l_abandon_du_geste_est_propose_pas_une_annulation_du_carnet(self, db, agent, modele):
        geste = _deposer(db)
        modele.return_value = _reponse(AppelOutil(OUTIL_ABANDONNER, {"id": geste.code}))
        resultat = interp.interpreter("vide le geste", CTX)

        assert resultat.decision == decisions.Decision("abandonner", geste.code)
        assert OUTIL_ABANDONNER in _noms_offerts(modele)
        assert db.query(Evenement).count() == 0
        # Le geste est toujours là : l'abandon se confirme au bouton.
        assert file_agent.existe(1, geste.code)

    def test_us286_ca4_confirmer_un_geste_de_la_file_d_un_mot_est_refuse(self, db, agent, modele):
        geste = _deposer(db)
        modele.return_value = _reponse(AppelOutil(catalogue_outils.OUTIL_CONFIRMER, {"id": geste.code}))
        resultat = interp.interpreter("oui", CTX)
        assert getattr(resultat, "decision", None) is None
        assert file_agent.existe(1, geste.code)

    def test_us286_ca4_un_code_inconnu_ou_d_un_autre_compte_ne_decide_rien(self, db, agent, modele):
        autre = svc.deposer_geste(db, TenantContext(user_id=2, potager_id=2, role="owner"),
                                  action="semis", culture="tomate").geste
        _deposer(db)
        modele.return_value = _reponse(AppelOutil(OUTIL_ABANDONNER, {"id": autre.code}))
        assert interp.interpreter("vide le geste", CTX).decision is None
        modele.return_value = _reponse(AppelOutil(OUTIL_ABANDONNER, {"id": "g-inconnu"}))
        assert interp.interpreter("vide le geste", CTX).decision is None
        assert file_agent.existe(2, autre.code)

    @pytest.mark.asyncio
    async def test_us286_ca4_le_bot_montre_une_carte_puis_le_bouton_abandonne(self, db):
        geste = _deposer(db)
        update, tg_ctx = MagicMock(), MagicMock(user_data={"tenant_user_id": 1})
        update.effective_message.reply_text = AsyncMock()
        with patch.object(bot_interpretation, "current_context", return_value=CTX):
            await bot_interpretation._interp_decider(update, tg_ctx, decisions.Decision("abandonner", geste.code))

        update.effective_message.reply_text.assert_awaited_once()
        boutons = update.effective_message.reply_text.await_args.kwargs["reply_markup"].inline_keyboard[0]
        assert [b.text for b in boutons] == ["🗑 Abandonner", "↩️ Le garder"]
        assert file_agent.existe(1, geste.code), "rien n'est abandonné avant le clic"

        clic = MagicMock()
        clic.effective_chat.id = 1
        clic.callback_query = AsyncMock()
        clic.callback_query.data = boutons[0].callback_data
        with patch.object(bot_file, "_user_id", return_value=1):
            await bot_file.file_cb(clic, tg_ctx)
        assert not file_agent.existe(1, geste.code)
        assert "Geste abandonné" in clic.callback_query.edit_message_text.await_args.args[0]
        assert db.query(Evenement).count() == 0

        # Un second clic ne refait rien.
        with patch.object(bot_file, "_user_id", return_value=1):
            await bot_file.file_cb(clic, tg_ctx)
        assert "n'attend plus" in clic.callback_query.edit_message_text.await_args.args[0]

    @pytest.mark.asyncio
    async def test_us286_ca4_le_bouton_garder_ne_retire_rien(self, db):
        geste = _deposer(db)
        clic = MagicMock()
        clic.callback_query = AsyncMock()
        clic.callback_query.data = "file:garder"
        with patch.object(bot_file, "_user_id", return_value=1):
            await bot_file.file_cb(clic, MagicMock(user_data={}))
        assert file_agent.existe(1, geste.code)

    @pytest.mark.asyncio
    async def test_us286_ca4_le_bouton_d_un_geste_d_un_autre_compte_ne_retire_rien(self, db):
        autre = svc.deposer_geste(db, TenantContext(user_id=2, potager_id=2, role="owner"),
                                  action="semis", culture="tomate").geste
        clic = MagicMock()
        clic.callback_query = AsyncMock()
        clic.callback_query.data = f"file:abandon:{autre.id}"
        with patch.object(bot_file, "_user_id", return_value=1):
            await bot_file.file_cb(clic, MagicMock(user_data={}))
        assert file_agent.existe(2, autre.code)


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — les cartes d'US-272 ne changent pas : une mémoire et une lecture, rien d'autre
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5Cartes:

    def test_us286_ca5_aucun_outil_n_est_ajoute(self):
        assert OUTILS_DECISION == ("confirmer_proposition", "abandonner_proposition")
        assert catalogue_outils.NB_OUTILS_MAX == 19
        assert len(catalogue_outils.outils()) + len(OUTILS_DECISION) + len(catalogue_outils.OUTILS_CORRECTION) \
            <= catalogue_outils.NB_OUTILS_MAX

    def test_us286_ca5_l_annulation_du_carnet_ne_vise_pas_un_geste_de_la_file(self):
        outil = next(o for o in catalogue_outils.outils_correction() if o.nom == OUTIL_ANNULER_ACTION) \
            if hasattr(catalogue_outils, "outils_correction") else None
        description = (outil.schema if outil else catalogue_outils._outils_correction()[1].schema)["function"]["description"]
        assert "gestes_en_attente" in description

    def test_us286_ca5_en_clair_retire_le_markdown(self):
        assert file_agent.en_clair("🗑 *2 gestes préparés ont été vidés* :\n• semis tomate — carré\\_nord") \
            == "🗑 2 gestes préparés ont été vidés :\n• semis tomate — carré_nord"

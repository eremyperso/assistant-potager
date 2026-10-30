"""
tests/test_us259_conversation_propositions.py — Conversation et propositions en base [US-259]
=============================================================================================
Le compagnon se souvient de ce qu'on vient de se dire et de ce qu'il a proposé,
même après un redémarrage du bot et quel que soit le canal.

Couverture CA1 → CA10 et les deux scénarios Gherkin. La base des propositions et
des échanges est la SQLite en mémoire de `conftest.memoire_compagnon`, vidée à
chaque test ; le test de concurrence (CA3) monte sa propre base sur fichier, la
seule où deux connexions écrivent vraiment en même temps. Aucun appel réseau :
Telegram est simulé par `MagicMock`/`AsyncMock`, le modèle par la passerelle patchée.
"""
from __future__ import annotations

import asyncio
import inspect
import pathlib
import re
import threading
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from telegram.ext import CommandHandler

from app.bot import interpretation as bot_interpretation
from app.bot import liaison as bot_liaison
from app.services import file_gestes as svc_file
from app.services import interpreteur_commandes as interp
from app.services import potager_actif as svc_potager_actif
from app.services.agent import contexte_court, interpreteur_agent
from app.services.agent.catalogue_outils import OUTIL_MODIFIER_PARCELLE
from app.services.compagnon import conversations
from app.services.compagnon import propositions as svc_propositions
from app.services.context import TenantContext
from database.db import Base
from database.models import EchangeConversation, Potager, PotagerMembre, Proposition, User
from llm import passerelle
from llm.passerelle import AppelOutil, ReponseOutils

RACINE = pathlib.Path(__file__).resolve().parent.parent
MIGRATION = RACINE / "migrations" / "migration_v61.sql"
ROLLBACK = RACINE / "migrations" / "rollback_v61.sql"

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
PHRASE = "passe la planche sud à 2 rangs"


def _commande(phrase: str = PHRASE, nom: str = "Planche Sud", rangs: int = 2) -> interp.CommandeInterpretee:
    return interp._construire_commande(
        interp.FORMES_PAR_CLE[("parcelle", "modifier")],
        {"nom": nom, "modification": f"rangs={rangs}"}, interp.ORIGINE_AGENT, 1.0, phrase,
    )


def _sur(user_id, potager_id):
    return TenantContext(user_id=user_id, potager_id=potager_id, role="owner")


def _ctx_tg(handler=None):
    ctx = MagicMock()
    ctx.user_data = {}
    ctx.args = []
    ctx.application.handlers = {0: [CommandHandler("parcelle", handler or AsyncMock())]}
    return ctx


def _update():
    update = MagicMock()
    update.effective_user.id = 42
    update.message = AsyncMock()
    update.callback_query = None
    return update


def _clic(data: str):
    update = MagicMock()
    update.effective_user.id = 42
    update.message = None
    update.callback_query = AsyncMock()
    update.callback_query.data = data
    update.callback_query.message = AsyncMock()
    return update


def _texte_du_clic(update) -> str:
    return "\n".join(str(a.args[0]) for a in update.callback_query.edit_message_text.await_args_list)


@pytest.fixture
def au_clic():
    """Le jardinier 1 clique ; il est membre du potager de la proposition, quel qu'il soit."""
    with patch.object(bot_interpretation, "_jardinier_au_clic", return_value=CTX.user_id), \
         patch.object(bot_interpretation, "_contexte_sur", side_effect=_sur) as contexte, \
         patch.object(interp, "persister_journal", return_value=5):
        yield contexte


@pytest.fixture
def en_potager(memoire_compagnon):
    """Session sur la base du compagnon, pour y poser des potagers et des membres."""
    db = memoire_compagnon()
    yield db
    db.rollback()
    for modele in (PotagerMembre, Potager, User):
        db.query(modele).delete()
    db.commit()
    db.close()


def _potager(db, potager_id: int, nom: str, membre: int = 1, etat: str = "actif", role: str = "owner"):
    if db.get(User, membre) is None:
        db.add(User(id=membre, email=f"j{membre}@example.org", mot_de_passe_hash="x"))
    db.add(Potager(id=potager_id, nom=nom, proprietaire_id=membre, etat=etat))
    db.add(PotagerMembre(user_id=membre, potager_id=potager_id, role=role))
    db.commit()


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — les 10 derniers échanges, par jardinier et par potager, 30 min glissantes
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1Echanges:

    def test_us259_ca1_un_echange_garde_ses_cinq_informations(self, memoire_compagnon):
        proposition = svc_propositions.proposer(CTX, _commande())
        conversations.noter(CTX, PHRASE, "proposition : /parcelle modifier Planche Sud rangs=2",
                            canal="telegram", outils=("modifier_parcelle",),
                            proposition_id=proposition.id, signal="gel")
        ligne = memoire_compagnon().query(EchangeConversation).one()
        assert (ligne.user_id, ligne.potager_id, ligne.canal) == (1, 1, "telegram")
        assert ligne.texte_jardinier == PHRASE
        assert ligne.texte_compagnon.startswith("proposition :")
        assert ligne.outils == ["modifier_parcelle"]
        assert ligne.proposition_id == proposition.id
        assert ligne.signal == "gel"

    def test_us259_ca1_dix_echanges_au_plus_du_plus_ancien_au_plus_recent(self):
        debut = datetime.utcnow() - timedelta(minutes=15)
        for rang in range(14):
            conversations.noter(CTX, f"p{rang}", "ok", canal="pwa", maintenant=debut + timedelta(minutes=rang))
        assert [e.texte for e in conversations.recents(CTX)] == [f"p{r}" for r in range(4, 14)]

    def test_us259_ca1_trente_minutes_glissantes(self):
        """Chaque échange repousse l'échéance ; un silence de plus de 30 min clôt la conversation."""
        t0 = datetime(2026, 10, 28, 9, 0)
        for minutes in (0, 25, 50):
            conversations.noter(CTX, f"à {minutes}", "ok", canal="telegram", maintenant=t0 + timedelta(minutes=minutes))
        # 50 minutes du premier au dernier, jamais plus de 25 entre deux : une seule conversation.
        assert len(conversations.recents(CTX, maintenant=t0 + timedelta(minutes=70))) == 3
        assert conversations.recents(CTX, maintenant=t0 + timedelta(minutes=81)) == ()

    def test_us259_ca1_un_silence_coupe_la_conversation(self):
        t0 = datetime(2026, 10, 28, 9, 0)
        conversations.noter(CTX, "hier soir", "ok", canal="telegram", maintenant=t0)
        conversations.noter(CTX, "ce matin", "ok", canal="telegram", maintenant=t0 + timedelta(minutes=40))
        textes = [e.texte for e in conversations.recents(CTX, maintenant=t0 + timedelta(minutes=41))]
        assert textes == ["ce matin"]

    def test_us259_ca1_par_jardinier_et_par_potager(self):
        conversations.noter(CTX, "le mien", "ok", canal="telegram")
        conversations.noter(_sur(2, 1), "celui d'un autre membre", "ok", canal="telegram")
        conversations.noter(_sur(1, 2), "dans mon autre potager", "ok", canal="pwa")
        assert [e.texte for e in conversations.recents(CTX)] == ["le mien"]

    def test_us259_ca1_commune_aux_canaux(self):
        """Ce qui est dit dans la PWA est lu par le compagnon Telegram, et inversement."""
        t0 = datetime.utcnow() - timedelta(minutes=2)
        conversations.noter(CTX, "dans la PWA", "ok", canal="pwa", maintenant=t0)
        conversations.noter(CTX, "dans Telegram", "ok", canal="telegram", maintenant=t0 + timedelta(minutes=1))
        assert [e.texte for e in conversations.recents(CTX)] == ["dans la PWA", "dans Telegram"]

    def test_us259_ca1_purge_a_trente_jours(self, en_potager):
        _potager(en_potager, 1, "Potager du bas")
        maintenant = datetime(2026, 10, 28, 12, 0)
        conversations.noter(CTX, "vieux", "ok", canal="telegram", maintenant=maintenant - timedelta(days=31))
        conversations.noter(CTX, "récent", "ok", canal="telegram", maintenant=maintenant - timedelta(days=29))
        assert conversations.purger(maintenant) == 1
        restants = [l.texte_jardinier for l in en_potager.query(EchangeConversation).all()]
        assert restants == ["récent"]

    def test_us259_ca1_les_propositions_de_conversation_partent_avec_les_echanges(self, memoire_compagnon):
        maintenant = datetime(2026, 10, 28, 12, 0)
        vieille = svc_propositions.proposer(CTX, _commande(), maintenant=maintenant - timedelta(days=31))
        recente = svc_propositions.proposer(_sur(1, 2), _commande(), maintenant=maintenant - timedelta(days=1))
        db = memoire_compagnon()
        db.add(Proposition(code="gvieux", user_id=1, potager_id=1, nature="geste", contenu={},
                           cree_le=maintenant - timedelta(days=40), expire_le=maintenant, etat="en_attente"))
        db.commit()
        assert svc_propositions.purger(maintenant) == 1
        restantes = {p.code for p in db.query(Proposition).all()}
        assert vieille.code not in restantes
        assert {recente.code, "gvieux"} <= restantes, "un geste de la file a sa propre rétention"

    def test_us259_ca1_la_purge_passe_chaque_potager_sous_son_propre_guc(self, en_potager):
        """RLS stricte : sans potager armé, rien ne s'efface — le balayage arme chacun."""
        _potager(en_potager, 1, "Bas")
        _potager(en_potager, 2, "Haut")
        armes: list = []
        reel = conversations.tenant_scope

        def _espion(potager_id):
            armes.append(potager_id)
            return reel(potager_id)

        with patch.object(conversations, "tenant_scope", side_effect=_espion):
            conversations.purger()
        assert armes == [None, 1, 2]

    def test_us259_ca1_une_memoire_en_panne_ne_casse_jamais_la_reponse(self):
        with patch.object(conversations, "SessionLocal", side_effect=RuntimeError("base indisponible")):
            conversations.noter(CTX, "phrase", "ok", canal="telegram")
            assert conversations.recents(CTX) == ()

    @pytest.mark.asyncio
    async def test_us259_ca1_le_bot_note_l_echange_avec_sa_proposition(self, memoire_compagnon):
        reponse = interp.ReponseAgent(texte="Je te propose 2 rangs.", proposition=_commande(),
                                      outils=("modifier_parcelle",), texte_origine=PHRASE)
        with patch.object(bot_interpretation, "current_context", return_value=CTX), \
             patch.object(bot_interpretation, "_resoudre_noms_parcelle", side_effect=lambda c: c), \
             patch.object(interp, "persister_journal", return_value=5):
            await bot_interpretation._traiter_commande_interpretee(_update(), _ctx_tg(), reponse)
        ligne = memoire_compagnon().query(EchangeConversation).one()
        en_cours = svc_propositions.en_attente(1, 1)
        assert ligne.canal == "telegram" and ligne.outils == ["modifier_parcelle"]
        assert ligne.proposition_id == en_cours.id
        assert ligne.texte_compagnon == "proposition : /parcelle modifier Planche Sud rangs=2"

    def test_us259_ca1_l_api_note_dans_la_meme_conversation(self):
        """`POST /voice` (la PWA) range son échange au même endroit que Telegram (canal pwa)."""
        from app.api import main as api

        source = inspect.getsource(api.voice)
        assert "svc_conversations.noter(" in source and "CANAL_PWA" in source


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — cinq états
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2Etats:

    def test_us259_ca2_les_cinq_etats(self):
        assert (svc_propositions.ETAT_EN_ATTENTE, *svc_propositions.ETATS_SORTIS) == (
            "en_attente", "confirmee", "abandonnee", "perimee", "remplacee")

    def test_us259_ca2_la_base_refuse_un_autre_etat(self):
        sql = MIGRATION.read_text(encoding="utf-8")
        assert "CHECK (etat IN ('en_attente', 'confirmee', 'abandonnee', 'perimee', 'remplacee'))" in sql
        contraintes = {c.name: str(c.sqltext) for c in Proposition.__table__.constraints if c.name}
        assert "remplacee" in contraintes["ck_propositions_etat"]

    def test_us259_ca2_une_nouvelle_proposition_remplace_l_ancienne(self):
        ancienne = svc_propositions.proposer(CTX, _commande())
        nouvelle = svc_propositions.proposer(CTX, _commande("non, 4 rangs", rangs=4))
        relue = svc_propositions.par_code(ancienne.code, 1)
        assert relue.etat == svc_propositions.ETAT_REMPLACEE
        assert svc_propositions.en_attente(1, 1).code == nouvelle.code != ancienne.code

    def test_us259_ca2_la_remplacante_est_notee(self, memoire_compagnon):
        ancienne = svc_propositions.proposer(CTX, _commande())
        nouvelle = svc_propositions.proposer(CTX, _commande("non, 4 rangs", rangs=4))
        ligne = memoire_compagnon().get(Proposition, ancienne.id)
        assert ligne.remplacee_par_id == nouvelle.id and ligne.traite_le is not None

    def test_us259_ca2_une_proposition_d_un_autre_potager_n_est_pas_remplacee(self):
        ailleurs = svc_propositions.proposer(_sur(1, 2), _commande())
        svc_propositions.proposer(CTX, _commande())
        assert svc_propositions.par_code(ailleurs.code, 1).en_attente

    def test_us259_ca2_un_geste_de_la_file_n_est_jamais_remplace(self, memoire_compagnon):
        db = memoire_compagnon()
        geste = Proposition(code="gabc", user_id=1, potager_id=1, nature="geste", contenu={"action": "semis"},
                            cree_le=datetime.utcnow(), expire_le=datetime.utcnow() + timedelta(days=3),
                            etat="en_attente", notifiee=True)
        db.add(geste)
        db.commit()
        svc_propositions.proposer(CTX, _commande())
        db.expire_all()
        assert db.get(Proposition, geste.id).etat == "en_attente"

    @pytest.mark.asyncio
    async def test_us259_ca2_annuler_abandonne(self, au_clic):
        proposition = svc_propositions.proposer(CTX, _commande())
        await bot_interpretation._interp_cb(_clic(f"interp:non:{proposition.code}"), _ctx_tg())
        assert svc_propositions.par_code(proposition.code, 1).etat == svc_propositions.ETAT_ABANDONNEE

    @pytest.mark.asyncio
    async def test_us259_ca2_confirmer_confirme(self, au_clic):
        proposition = svc_propositions.proposer(CTX, _commande())
        await bot_interpretation._interp_cb(_clic(f"interp:ok:{proposition.code}"), _ctx_tg())
        assert svc_propositions.par_code(proposition.code, 1).etat == svc_propositions.ETAT_CONFIRMEE


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — une consommation atomique
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3Atomicite:

    def test_us259_ca3_deux_confirmations_simultanees_n_en_font_qu_une(self, tmp_path):
        """Deux connexions, deux transactions, au même instant : une seule l'emporte."""
        moteur = create_engine(f"sqlite:///{tmp_path / 'concurrence.db'}", connect_args={"timeout": 30})
        Base.metadata.create_all(bind=moteur)
        fabrique = sessionmaker(bind=moteur)
        with fabrique() as db:
            ligne = Proposition(code="p1", user_id=1, potager_id=1, nature="commande", contenu={},
                                cree_le=datetime.utcnow(), expire_le=datetime.utcnow() + timedelta(minutes=30),
                                etat="en_attente")
            db.add(ligne)
            db.commit()
            ident = ligne.id

        depart = threading.Barrier(2)
        resultats: list[bool] = []

        def _confirmer():
            with fabrique() as db:
                depart.wait()
                resultats.append(svc_propositions.sortir(db, ident, svc_propositions.ETAT_CONFIRMEE))

        fils = [threading.Thread(target=_confirmer) for _ in range(2)]
        for fil in fils:
            fil.start()
        for fil in fils:
            fil.join()
        moteur.dispose()
        assert sorted(resultats) == [False, True]

    def test_us259_ca3_la_condition_est_dans_l_update(self):
        """Pas de lecture puis écriture : la condition `en_attente` est dans l'UPDATE lui-même."""
        source = inspect.getsource(svc_propositions.sortir)
        assert "Proposition.etat == ETAT_EN_ATTENTE" in source and ".update(" in source
        assert ".first()" not in source

    @pytest.mark.asyncio
    async def test_us259_ca3_deux_clics_concurrents_n_executent_qu_une_fois(self, au_clic):
        handler = AsyncMock()
        ctx = _ctx_tg(handler)
        proposition = svc_propositions.proposer(CTX, _commande())
        await asyncio.gather(
            bot_interpretation._interp_cb(_clic(f"interp:ok:{proposition.code}"), ctx),
            bot_interpretation._interp_cb(_clic(f"interp:ok:{proposition.code}"), ctx),
        )
        handler.assert_awaited_once()

    def test_us259_ca3_la_file_d_us224_passe_par_la_meme_sortie(self):
        """Un geste confirmé deux fois (portail et Telegram) ne sort qu'une fois."""
        source = inspect.getsource(svc_file._sortir)
        assert "svc_propositions.sortir(" in source

    def test_us259_ca3_une_proposition_qui_n_attend_plus_ne_se_met_pas_a_jour(self):
        proposition = svc_propositions.proposer(CTX, _commande())
        assert svc_propositions.consommer(proposition, svc_propositions.ETAT_CONFIRMEE)
        assert svc_propositions.mettre_a_jour(proposition, commande=_commande(rangs=9), attend=None) is None
        assert not svc_propositions.consommer(proposition, svc_propositions.ETAT_ABANDONNEE)

    def test_us259_ca3_un_etat_inconnu_est_refuse(self):
        with pytest.raises(ValueError):
            svc_propositions.sortir(MagicMock(), 1, "faite")


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — la proposition porte son potager, l'exécution l'arme
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4Potager:

    def test_us259_ca4_la_proposition_porte_son_potager(self):
        proposition = svc_propositions.proposer(_sur(1, 7), _commande())
        assert proposition.potager_id == 7
        assert svc_propositions.par_code(proposition.code, 1).potager_id == 7

    @pytest.mark.asyncio
    async def test_us259_ca4_confirmee_depuis_un_autre_potager_actif_elle_s_execute_dans_le_sien(self, au_clic):
        vu: list = []

        async def handler(update, ctx):
            vu.append(ctx.user_data.get(bot_liaison.CLE_POTAGER_IMPOSE))

        proposition = svc_propositions.proposer(_sur(1, 7), _commande())
        ctx = _ctx_tg(handler)
        # Le potager actif du canal est le 2 : il n'est même pas consulté.
        with patch.object(bot_interpretation, "current_context", return_value=_sur(1, 2)):
            await bot_interpretation._interp_cb(_clic(f"interp:ok:{proposition.code}"), ctx)
        au_clic.assert_called_once_with(1, 7)
        assert vu == [7]
        assert bot_liaison.CLE_POTAGER_IMPOSE not in ctx.user_data

    @pytest.mark.asyncio
    async def test_us259_ca4_le_garde_de_liaison_arme_le_potager_impose(self):
        update = _update()
        ctx = MagicMock(user_data={bot_liaison.CLE_POTAGER_IMPOSE: 7})
        impose = TenantContext(user_id=3, potager_id=7, role="editor")
        with patch.object(bot_liaison.svc_potager_actif, "contexte_sur_potager", return_value=impose) as cible, \
             patch.object(bot_liaison.svc_potager_actif, "resoudre_tenant_context") as actif, \
             patch.object(bot_liaison, "set_current_context") as armer:
            assert await bot_liaison._resoudre_et_armer_contexte(update, ctx, MagicMock(), 3)
        cible.assert_called_once()
        actif.assert_not_called()
        armer.assert_called_once_with(impose)
        assert bot_liaison.CLE_POTAGER_IMPOSE not in ctx.user_data, "il ne vaut que pour une exécution"

    @pytest.mark.asyncio
    async def test_us259_ca4_hors_d_acces_le_garde_refuse(self):
        update = _update()
        ctx = MagicMock(user_data={bot_liaison.CLE_POTAGER_IMPOSE: 7})
        with patch.object(bot_liaison.svc_potager_actif, "contexte_sur_potager", return_value=None):
            assert await bot_liaison._resoudre_et_armer_contexte(update, ctx, MagicMock(), 3) is False
        assert "plus accès" in update.message.reply_text.await_args.args[0]

    def test_us259_ca4_le_role_se_relit_sur_le_potager_de_la_proposition(self, en_potager):
        _potager(en_potager, 7, "Potager du haut", role="editor")
        _potager(en_potager, 8, "Archivé", etat="archive")
        assert svc_potager_actif.contexte_sur_potager(en_potager, 1, 7) == TenantContext(1, 7, "editor")
        assert svc_potager_actif.contexte_sur_potager(en_potager, 2, 7) is None, "pas membre"
        assert svc_potager_actif.contexte_sur_potager(en_potager, 1, 8) is None, "plus actif"

    def test_us259_ca4_la_carte_nomme_le_potager_quand_il_y_en_a_plusieurs(self, en_potager):
        _potager(en_potager, 1, "Potager du bas")
        assert svc_propositions.potager_a_nommer(1, 1) is None
        _potager(en_potager, 2, "Potager du haut")
        assert svc_propositions.potager_a_nommer(1, 2) == "Potager du haut"

    @pytest.mark.asyncio
    async def test_us259_ca4_le_recapitulatif_porte_le_nom_du_potager(self):
        update = _update()
        with patch.object(bot_interpretation, "current_context", return_value=CTX), \
             patch.object(bot_interpretation, "_resoudre_noms_parcelle", side_effect=lambda c: c), \
             patch.object(interp, "persister_journal", return_value=5), \
             patch.object(svc_propositions, "potager_a_nommer", return_value="Potager du haut"):
            await bot_interpretation._interp_proposer(update, _ctx_tg(), _commande())
        assert update.message.reply_text.await_args.args[0].startswith("🏡 _Potager du haut_")


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — 30 minutes en conversation, la durée de la file une fois notifiée
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5DureeDeVie:

    def test_us259_ca5_une_proposition_de_conversation_vit_trente_minutes(self):
        instant = datetime(2026, 10, 28, 10, 0)
        proposition = svc_propositions.proposer(CTX, _commande(), maintenant=instant)
        assert proposition.expire_le == instant + timedelta(minutes=30)
        assert svc_propositions.en_attente(1, 1, maintenant=instant + timedelta(minutes=29)) is not None
        assert svc_propositions.en_attente(1, 1, maintenant=instant + timedelta(minutes=31)) is None

    def test_us259_ca5_notifiee_elle_prend_la_duree_de_la_file(self, memoire_compagnon):
        instant = datetime(2026, 10, 28, 10, 0)
        proposition = svc_propositions.proposer(CTX, _commande(), maintenant=instant)
        assert svc_propositions.marquer_notifiee(proposition.id, 1)
        ligne = memoire_compagnon().get(Proposition, proposition.id)
        assert ligne.notifiee is True
        assert ligne.expire_le == instant + timedelta(days=svc_file.DUREE_VIE_JOURS)

    def test_us259_ca5_un_geste_de_la_file_est_notifie_trois_jours(self, test_db, monkeypatch):
        monkeypatch.setattr(svc_file, "SessionLocal", lambda: test_db)
        test_db.add(User(id=1, email="j@example.org", mot_de_passe_hash="x"))
        test_db.add(Potager(id=1, nom="Bas", proprietaire_id=1))
        test_db.add(PotagerMembre(user_id=1, potager_id=1, role="owner"))
        test_db.commit()
        instant = datetime(2026, 10, 28, 10, 0)
        depot = svc_file.deposer_geste(test_db, CTX, action="semis", culture="radis", maintenant=instant)
        assert depot.geste.notifiee is True and depot.geste.nature == "geste"
        assert depot.geste.expire_le == instant + timedelta(days=3)

    @pytest.mark.asyncio
    async def test_us259_ca5_un_clic_apres_trente_minutes_ne_fait_rien(self, au_clic, memoire_compagnon):
        handler = AsyncMock()
        instant = datetime.utcnow() - timedelta(minutes=31)
        proposition = svc_propositions.proposer(CTX, _commande(), maintenant=instant)
        clic = _clic(f"interp:ok:{proposition.code}")
        await bot_interpretation._interp_cb(clic, _ctx_tg(handler))
        handler.assert_not_awaited()
        assert "Demande expirée" in _texte_du_clic(clic)
        assert svc_propositions.par_code(proposition.code, 1).etat == svc_propositions.ETAT_PERIMEE

    def test_us259_ca5_l_avertissement_avant_purge_reste_celui_de_la_file(self):
        assert svc_file.DELAI_AVERTISSEMENT_HEURES == 4
        assert svc_file.DUREE_VIE_JOURS == svc_propositions.DUREE_NOTIFIEE_JOURS == 3


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — gestes_intentions devient une nature de proposition (+ Gherkin 2)
# ═════════════════════════════════════════════════════════════════════════════
def _reprise() -> str:
    sql = MIGRATION.read_text(encoding="utf-8")
    trouve = re.search(r"-- -- REPRISE:DEBUT --(.*?)-- -- REPRISE:FIN --", sql, re.S)
    assert trouve, "marqueurs REPRISE absents de migration_v61.sql"
    return trouve.group(1)


class TestCA6NatureGeste:

    def test_us259_gherkin_un_geste_en_attente_est_migre_tel_quel(self):
        """Given un geste en attente dans la file d'US-224 avant la migration
        When la migration est appliquée
        Then le geste apparaît comme proposition de nature « geste », toujours en attente."""
        moteur = create_engine("sqlite://")
        with moteur.begin() as cx:
            # La table telle que v60 l'a laissée, déjà renommée et augmentée par v61.
            cx.execute(text(
                "CREATE TABLE propositions (id INTEGER PRIMARY KEY, code TEXT, etat TEXT, "
                "nature TEXT NOT NULL DEFAULT 'geste', canal TEXT, notifiee BOOLEAN NOT NULL DEFAULT 0, "
                "expire_le TEXT)"))
            cx.execute(text(
                "INSERT INTO propositions (id, code, etat, expire_le) VALUES "
                "(1, 'gAttente', 'en_attente', '2026-10-30'), (2, 'gFait', 'confirme', '2026-10-30'), "
                "(3, 'gLaisse', 'abandonne', '2026-10-30'), (4, 'gVide', 'perime', '2026-10-30')"))
            for instruction in filter(str.strip, _reprise().split(";")):
                cx.execute(text(instruction))
            lignes = cx.execute(text("SELECT id, code, etat, nature, canal, notifiee, expire_le "
                                     "FROM propositions ORDER BY id")).all()
        assert lignes[0] == (1, "gAttente", "en_attente", "geste", "pwa", 1, "2026-10-30")
        assert [l.etat for l in lignes[1:]] == ["confirmee", "abandonnee", "perimee"]

    def test_us259_ca6_la_reprise_est_idempotente(self):
        moteur = create_engine("sqlite://")
        with moteur.begin() as cx:
            cx.execute(text("CREATE TABLE propositions (id INTEGER PRIMARY KEY, etat TEXT, nature TEXT "
                            "DEFAULT 'geste', canal TEXT, notifiee BOOLEAN DEFAULT 0)"))
            cx.execute(text("INSERT INTO propositions (id, etat) VALUES (1, 'confirme')"))
            for _ in range(2):
                for instruction in filter(str.strip, _reprise().split(";")):
                    cx.execute(text(instruction))
            assert cx.execute(text("SELECT etat, canal FROM propositions")).one() == ("confirmee", "pwa")

    def test_us259_ca6_la_table_est_renommee_pas_copiee(self):
        """Même ligne, même code, même lien `?start=` : la migration renomme, elle ne recopie pas."""
        sql = MIGRATION.read_text(encoding="utf-8")
        assert "ALTER TABLE gestes_intentions RENAME TO propositions" in sql
        assert "RENAME COLUMN geste TO contenu" in sql
        assert "INSERT INTO propositions" not in sql

    def test_us259_ca6_une_table_creee_par_create_all_ne_bloque_pas_le_renommage(self):
        """L'API et le bot font `create_all` au démarrage : relancés sur le nouveau modèle avant
        la migration, ils créent une table `propositions` vide. Elle est supprimée (vide
        seulement), la clé étrangère des échanges est remise, et la policy n'est renommée
        que sur la table renommée."""
        sql = MIGRATION.read_text(encoding="utf-8")
        garde = sql.index("IF EXISTS (SELECT 1 FROM propositions) THEN")
        assert garde < sql.index("DROP TABLE propositions CASCADE") < sql.index(
            "ALTER TABLE gestes_intentions RENAME TO propositions")
        assert "RAISE EXCEPTION" in sql[garde:sql.index("DROP TABLE propositions CASCADE")]
        assert "AND polrelid = to_regclass('public.propositions')" in sql
        assert "ADD CONSTRAINT echanges_conversation_proposition_id_fkey" in sql

    def test_us259_ca6_le_rollback_rend_la_file(self):
        sql = ROLLBACK.read_text(encoding="utf-8")
        assert "ALTER TABLE propositions RENAME TO gestes_intentions" in sql
        assert "DELETE FROM propositions WHERE nature <> 'geste'" in sql
        assert "DROP TABLE IF EXISTS echanges_conversation" in sql

    def _gestes(self, db):
        maintenant = datetime.utcnow()
        geste = Proposition(code="gfile", user_id=1, potager_id=1, nature="geste",
                            contenu={"action": "semis", "culture": "radis"}, cree_le=maintenant,
                            expire_le=maintenant + timedelta(days=3), etat="en_attente", notifiee=True)
        commande = Proposition(code="pconv", user_id=1, potager_id=1, nature="commande", contenu={},
                               cree_le=maintenant, expire_le=maintenant + timedelta(minutes=30),
                               etat="en_attente")
        db.add_all([geste, commande])
        db.commit()
        return geste, commande

    def test_us259_gherkin_sa_relance_part_comme_avant(self, test_db):
        """… And sa relance part comme avant : le compte est relancé pour CE geste seul."""
        geste, _ = self._gestes(test_db)
        assert svc_file.comptes_avec_file(test_db) == [1]
        assert [g.code for g in svc_file.lister_en_attente(test_db, 1)] == ["gfile"]
        assert svc_file.compter_en_attente(test_db, 1) == 1

    def test_us259_ca6_le_lien_start_retrouve_le_geste_et_lui_seul(self, test_db):
        geste, commande = self._gestes(test_db)
        assert svc_file.geste_par_code(test_db, "gfile", 1).id == geste.id
        with pytest.raises(svc_file.CodeIntrouvableError):
            svc_file.geste_par_code(test_db, "pconv", 1)

    def test_us259_ca6_une_commande_proposee_ne_perime_pas_comme_un_geste(self, test_db):
        _, commande = self._gestes(test_db)
        plus_tard = datetime.utcnow() + timedelta(days=5)
        assert [g.code for g in svc_file.gestes_perimes(test_db, plus_tard)] == ["gfile"]
        assert all(g.code != "pconv" for g in svc_file.gestes_a_avertir(test_db, plus_tard - timedelta(days=2)))

    def test_us259_ca6_le_contenu_d_un_geste_rejoue_comme_avant(self, test_db):
        geste, _ = self._gestes(test_db)
        assert svc_file.item_du_geste(geste) == {"action": "semis", "culture": "radis"}

    def test_us259_ca6_les_etats_de_la_file_sont_ceux_des_propositions(self):
        assert (svc_file.ETAT_CONFIRME, svc_file.ETAT_ABANDONNE, svc_file.ETAT_PERIME) == (
            "confirmee", "abandonnee", "perimee")

    def test_us259_ca6_la_pwa_lit_l_etat_au_feminin(self):
        source = (RACINE / "frontend" / "src" / "components" / "BandeauFile.jsx").read_text(encoding="utf-8")
        assert "geste.etat === 'perimee'" in source


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — les magasins en mémoire sont retirés
# ═════════════════════════════════════════════════════════════════════════════
class TestCA7PlusDeMemoireDeProcessus:

    def test_us259_ca7_plus_d_interp_pending(self):
        assert not hasattr(bot_interpretation, "_INTERP_PENDING")
        assert "_INTERP_PENDING" not in (RACINE / "app" / "bot" / "interpretation.py").read_text(encoding="utf-8")

    def test_us259_ca7_plus_de_sessions_dans_l_api(self):
        from app.api import main as api

        assert not hasattr(api, "_sessions")

    def test_us259_ca7_le_contexte_court_ne_garde_plus_rien(self):
        for nom in ("_ECHANGES", "noter", "echanges_de", "oublier_tout", "noter_resultat"):
            assert not hasattr(contexte_court, nom), nom

    def test_us259_ca7_le_contexte_vient_de_la_base(self):
        svc_propositions.proposer(CTX, _commande())
        conversations.noter(CTX, "bonjour", "réponse : Bonjour !", canal="pwa")
        with patch.object(bot_interpretation, "current_context", return_value=CTX):
            contexte = bot_interpretation.contexte_court_de(_update())
        assert contexte.commandes == ("/parcelle modifier Planche Sud rangs=2",)
        assert [e.texte for e in contexte.echanges] == ["bonjour"]


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — une proposition survit à un redémarrage (+ Gherkin 1)
# ═════════════════════════════════════════════════════════════════════════════
class TestCA8Redemarrage:

    @pytest.mark.asyncio
    async def test_us259_gherkin_confirmee_apres_un_redemarrage_elle_s_execute_une_fois(self, au_clic):
        """Given une proposition « planche Sud 2 rangs » en attente
        When le bot redémarre
        And le jardinier clique « Confirmer »
        Then elle est exécutée une seule fois."""
        # Avant le redémarrage : la proposition est montrée par le bot.
        update = _update()
        with patch.object(bot_interpretation, "current_context", return_value=CTX), \
             patch.object(bot_interpretation, "_resoudre_noms_parcelle", side_effect=lambda c: c):
            await bot_interpretation._interp_proposer(update, _ctx_tg(), _commande())
        code = svc_propositions.en_attente(1, 1).code

        # Le bot redémarre : un nouveau processus n'a ni `user_data`, ni rien en mémoire.
        handler = AsyncMock()
        apres = _ctx_tg(handler)
        await bot_interpretation._interp_cb(_clic(f"interp:ok:{code}"), apres)
        await bot_interpretation._interp_cb(_clic(f"interp:ok:{code}"), apres)

        handler.assert_awaited_once()
        assert apres.args == ["modifier", "Planche Sud", "rangs=2"]

    def test_us259_ca8_une_commande_se_relit_a_l_identique(self):
        commande = _commande().avec_candidats("nom", ("Planche Sud", "Serre"))
        proposition = svc_propositions.proposer(CTX, commande)
        assert svc_propositions.par_code(proposition.code, 1).commande == commande

    def test_us259_ca8_une_completion_se_relit_a_l_identique(self):
        commande = interp.reconnaitre_par_regles("note une association entre la carotte et l'aneth")
        proposition = svc_propositions.proposer(CTX, commande)
        svc_propositions.mettre_a_jour(proposition, commande=commande, attend="nature")
        relue = svc_propositions.en_attente(1, 1)
        assert relue.commande == commande and relue.attend == "nature"
        assert [a.nom for a in relue.commande.manquants] == ["nature", "preuve", "motif"]

    def test_us259_ca8_un_plan_se_relit_a_l_identique(self):
        plan = interp.Plan((_commande(), _commande(nom="Serre")), texte_origine=PHRASE, deja_faites=(1,))
        proposition = svc_propositions.proposer(CTX, plan)
        assert proposition.nature == svc_propositions.NATURE_PLAN
        assert svc_propositions.par_code(proposition.code, 1).commande == plan

    def test_us259_ca8_un_champ_disparu_du_catalogue_n_empeche_pas_la_relecture(self, memoire_compagnon):
        proposition = svc_propositions.proposer(CTX, _commande())
        db = memoire_compagnon()
        ligne = db.get(Proposition, proposition.id)
        contenu = dict(ligne.contenu)
        contenu["proposition"] = {**contenu["proposition"], "champ_retire": 1}
        ligne.contenu = contenu
        db.commit()
        assert svc_propositions.par_code(proposition.code, 1).commande == _commande()

    def test_us259_ca8_une_ligne_illisible_vaut_une_proposition_absente(self, memoire_compagnon):
        proposition = svc_propositions.proposer(CTX, _commande())
        db = memoire_compagnon()
        db.get(Proposition, proposition.id).contenu = {"proposition": {"n_importe": "quoi"}}
        db.commit()
        assert svc_propositions.en_attente(1, 1) is None


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — potager_id et RLS ; rien d'un autre potager n'est lu
# ═════════════════════════════════════════════════════════════════════════════
class TestCA9Isolement:

    def test_us259_ca9_les_deux_tables_portent_potager_id(self):
        for table in (Proposition.__table__, EchangeConversation.__table__):
            assert table.c.potager_id.nullable is False

    def test_us259_ca9_rls_des_echanges_stricte(self):
        sql = MIGRATION.read_text(encoding="utf-8")
        assert "ALTER TABLE echanges_conversation ENABLE ROW LEVEL SECURITY" in sql
        assert re.search(
            r"CREATE POLICY tenant_isolation_echanges_conversation ON echanges_conversation\s+"
            r"USING\s+\(potager_id = current_setting\('app.potager_id'\)::int\)\s+"
            r"WITH CHECK \(potager_id = current_setting\('app.potager_id'\)::int\)", sql)

    def test_us259_ca9_la_policy_des_propositions_suit_la_table(self):
        sql = MIGRATION.read_text(encoding="utf-8")
        assert "RENAME TO tenant_isolation_propositions" in sql

    def test_us259_ca9_la_proposition_d_un_autre_potager_n_est_pas_lue(self):
        svc_propositions.proposer(_sur(1, 2), _commande())
        assert svc_propositions.en_attente(1, 1) is None

    def test_us259_ca9_le_bouton_d_un_autre_jardinier_n_est_pas_lu(self):
        proposition = svc_propositions.proposer(_sur(2, 1), _commande())
        assert svc_propositions.par_code(proposition.code, 1) is None

    def test_us259_ca9_les_echanges_s_ecrivent_et_se_lisent_sous_leur_potager(self):
        armes: list = []
        reel = conversations.tenant_scope

        def _espion(potager_id):
            armes.append(potager_id)
            return reel(potager_id)

        with patch.object(conversations, "tenant_scope", side_effect=_espion):
            conversations.noter(_sur(1, 4), "x", "ok", canal="telegram")
            conversations.recents(_sur(1, 4))
        assert armes == [4, 4]

    def test_us259_ca9_une_proposition_s_ecrit_sous_SON_potager(self):
        proposition = svc_propositions.proposer(_sur(1, 6), _commande())
        armes: list = []
        reel = svc_propositions.tenant_scope

        def _espion(potager_id):
            armes.append(potager_id)
            return reel(potager_id)

        with patch.object(svc_propositions, "tenant_scope", side_effect=_espion):
            svc_propositions.mettre_a_jour(proposition, commande=proposition.commande, attend="nom")
            svc_propositions.consommer(proposition, svc_propositions.ETAT_CONFIRMEE)
        assert armes == [6, 6]


# ═════════════════════════════════════════════════════════════════════════════
# Les dix échanges transmis à l'agent, même sans proposition
# ═════════════════════════════════════════════════════════════════════════════
def _reponse(*appels: AppelOutil) -> ReponseOutils:
    return ReponseOutils(texte="", modele="test", appel_type=passerelle.TYPE_AGENT,
                         tokens_in=900, tokens_out=50, latence_ms=400, appels=appels,
                         statut=passerelle.STATUT_OK)


class TestConversationTransmiseALAgent:

    def _conversation(self) -> contexte_court.ContexteCourt:
        echange = contexte_court.Echange("passe la planche nord à 6 rangs",
                                         "proposition : /parcelle modifier Planche Nord rangs=6", 0.0)
        return contexte_court.construire(CTX, echanges=(echange,))

    def test_us259_sans_proposition_les_echanges_forment_un_contexte(self):
        contexte = self._conversation()
        assert contexte is not None and not contexte.en_attente
        assert "proposition_en_attente" not in contexte.donnees()
        assert "aucune proposition n'est en attente" in contexte.prompt()
        assert "CORRIGER" not in contexte.prompt()

    def test_us259_sans_echange_ni_proposition_rien_n_est_ajoute(self):
        assert contexte_court.construire(CTX) is None

    def test_us259_l_agent_lit_la_conversation_dans_la_partie_variable(self, monkeypatch):
        monkeypatch.setattr(interpreteur_agent, "noms_parcelles_du_potager", lambda ctx: ("Planche Nord",))
        monkeypatch.setattr(interpreteur_agent, "voisin_en_base", lambda ctx: (lambda nom: None))
        with patch.object(passerelle, "appeler_chat_outils", return_value=_reponse()) as modele:
            interpreteur_agent.proposer("et la serre ?", CTX, self._conversation())
        noyau = modele.call_args.kwargs
        assert noyau["message_utilisateur"] == "et la serre ?"
        assert "derniers_echanges" in noyau["prompt_variable"]

    def test_us259_sans_proposition_le_validateur_n_ancre_que_sur_la_phrase(self, monkeypatch):
        """Un nombre dit dans un échange passé n'est pas « dit » dans cette phrase : sans
        proposition en attente, rien n'est prolongé, et le validateur refuse ce 6."""
        monkeypatch.setattr(interpreteur_agent, "noms_parcelles_du_potager", lambda ctx: ("Planche Nord", "Serre"))
        monkeypatch.setattr(interpreteur_agent, "voisin_en_base", lambda ctx: (lambda nom: None))
        appel = AppelOutil(OUTIL_MODIFIER_PARCELLE, {"parcelle": "Serre", "nb_rangs": 6})
        with patch.object(passerelle, "appeler_chat_outils", return_value=_reponse(appel)):
            resultat = interpreteur_agent.proposer("et la serre aussi", CTX, self._conversation())
        assert resultat.proposition is None and resultat.refus

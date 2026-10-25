"""
tests/test_us236_aiguillage_agent.py — Aiguiller une phrase qui n'est pas une commande [US-236]
==============================================================================================
Question, geste, précision, hors périmètre : l'agent dit où va la phrase, le
bot le suit sans repasser par la classification par mots-clés.

Aucun appel réseau : la passerelle est simulée (`modele`), le bot est piloté
par des `MagicMock`/`AsyncMock`, la base est SQLite en mémoire.
"""
from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import sessionmaker

from app import config
from app.bot import interpretation as bot_interpretation
from app.bot import messages as bot_messages
from app.bot import questions as bot_questions
from app.services import interpreteur_commandes as interp
from app.services.agent import catalogue_outils, interpreteur_agent
from app.services.agent.catalogue_outils import OUTIL_MODIFIER_PARCELLE
from app.services.context import TenantContext
from database.models import RoutageLog
from llm import passerelle, routeur
from llm.passerelle import AppelOutil, ReponseOutils

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
PARCELLES = ("Serre extérieure", "Planche Nord", "Planche Sud", "Tunnel")
EXCEL = "Exporte-moi tout l'historique en Excel"
VAGUE = "Modifie ma serre"


def _reponse(*appels: AppelOutil, statut: str = passerelle.STATUT_OK) -> ReponseOutils:
    return ReponseOutils(
        texte="", modele="test", appel_type=passerelle.TYPE_AGENT,
        tokens_in=900, tokens_out=50, latence_ms=400, appels=appels, statut=statut,
    )


@pytest.fixture
def agent_actif(monkeypatch):
    monkeypatch.setattr(config, "AGENT_MODE", "actif")


@pytest.fixture
def parcelles_connues(monkeypatch):
    monkeypatch.setattr(interpreteur_agent, "noms_parcelles_du_potager", lambda ctx: PARCELLES)
    monkeypatch.setattr(interpreteur_agent, "voisin_en_base", lambda ctx: (lambda nom: None))


@pytest.fixture
def modele():
    with patch.object(passerelle, "appeler_chat_outils") as faux:
        yield faux


@pytest.fixture
def sans_journal(monkeypatch):
    """Le journal a ses propres tests : ailleurs, il n'écrit rien."""
    monkeypatch.setattr(interpreteur_agent, "persister_aiguillage", MagicMock())
    return interpreteur_agent.persister_aiguillage


@pytest.fixture
def session_de_test(test_db, test_engine, monkeypatch):
    fabrique = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    monkeypatch.setattr("database.db.SessionLocal", fabrique)
    return test_db


def _update(texte: str):
    update = MagicMock()
    update.effective_user.id = 4242
    update.message = AsyncMock()
    update.message.text = texte
    update.message.reply_text = AsyncMock()
    update.effective_message = update.message
    update.callback_query = None
    return update


async def _handle_text(texte: str, resultat):
    """Pilote `handle_text` jusqu'à l'étage de l'interpréteur, qui rend `resultat`."""
    update = _update(texte)
    tg_ctx = MagicMock()
    tg_ctx.user_data = {}
    with (
        patch.object(bot_messages, "_verifier_liaison_ou_onboarding", new=AsyncMock(return_value=True)),
        patch.object(bot_messages, "current_context", return_value=CTX),
        patch.object(bot_messages.svc_interpreteur, "interpreter", return_value=resultat),
        patch.object(bot_messages.routeur, "classer_demande") as classer,
        patch.object(bot_messages, "_ask_question", new=AsyncMock()) as ask,
        patch.object(bot_messages, "_parse_and_save", new=AsyncMock()) as parse,
        patch.object(bot_messages, "_corr_annuler_dernier", new=AsyncMock()),
        patch.object(bot_messages, "_corr_start", new=AsyncMock()),
    ):
        classer.return_value = routeur.DecisionRoutage(routeur.NATURE_ACTION, routeur.ORIGINE_REGLE, 1.0)
        await bot_messages.handle_text(update, tg_ctx)
    return update, classer, ask, parse


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — l'agent choisit toujours un outil
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1ToujoursUnOutil:

    def test_us236_ca1_appel_avec_tool_choice_required(self, agent_actif, modele, parcelles_connues):
        modele.return_value = _reponse(AppelOutil("hors_perimetre", {"raison": "export"}))
        interpreteur_agent.proposer(EXCEL, CTX)
        assert modele.call_args.kwargs.get("tool_choice", "required") == "required"

    def test_us236_ca1_les_quatre_outils_terminaux_sont_au_catalogue(self):
        noms = {o.nom for o in catalogue_outils.outils()}
        assert set(catalogue_outils.OUTILS_TERMINAUX) <= noms

    def test_us236_ca1_un_texte_libre_n_est_pas_une_reponse(self, agent_actif, modele, parcelles_connues):
        """Pas d'appel d'outil = agent indisponible : rien n'est montré du texte."""
        modele.return_value = _reponse()
        resultat = interpreteur_agent.proposer(EXCEL, CTX)
        assert resultat.disponible is False
        assert resultat.aiguillage is None and resultat.commande is None

    @pytest.mark.parametrize("outil,vers", [
        ("poser_question", interp.VERS_QUESTION),
        ("saisir_geste", interp.VERS_GESTE),
        ("demander_precision", interp.VERS_PRECISION),
        ("hors_perimetre", interp.VERS_HORS_PERIMETRE),
    ])
    def test_us236_ca1_chaque_outil_terminal_donne_son_aiguillage(self, outil, vers):
        aiguillage = interpreteur_agent.aiguillage_de(AppelOutil(outil, {}), "x")
        assert aiguillage.vers == vers

    def test_us236_ca1_un_outil_de_commande_n_est_pas_un_aiguillage(self):
        assert interpreteur_agent.aiguillage_de(AppelOutil(OUTIL_MODIFIER_PARCELLE, {}), "x") is None


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — une question va à la cascade avec sa nature, sans mots-clés
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2Question:

    def test_us236_ca2_poser_question_rend_un_aiguillage_avec_sa_nature(
        self, agent_actif, modele, parcelles_connues
    ):
        modele.return_value = _reponse(AppelOutil("poser_question", {"nature": "QUESTION_DATA"}))
        resultat = interp.interpreter("quelles sont mes pépinières ?", CTX)
        assert isinstance(resultat, interp.Aiguillage)
        assert resultat.vers == interp.VERS_QUESTION
        assert resultat.nature_question == routeur.NATURE_QUESTION_DATA

    def test_us236_ca2_nature_inconnue_laisse_la_cascade_classer(self):
        aiguillage = interpreteur_agent.aiguillage_de(
            AppelOutil("poser_question", {"nature": "ACTION"}), "x")
        assert aiguillage.vers == interp.VERS_QUESTION
        assert aiguillage.nature_question is None

    @pytest.mark.asyncio
    async def test_us236_ca2_le_bot_ne_reclasse_pas(self):
        aiguillage = interp.Aiguillage(vers=interp.VERS_QUESTION,
                                       nature_question=routeur.NATURE_QUESTION_SAVOIR)
        _, classer, ask, parse = await _handle_text("la serre est-elle une pépinière ?", aiguillage)
        classer.assert_not_called()
        ask.assert_awaited_once()
        assert ask.await_args.kwargs["nature"] == routeur.NATURE_QUESTION_SAVOIR
        parse.assert_not_called()

    @pytest.mark.asyncio
    async def test_us236_ca2_ask_question_transmet_la_decision(self):
        update = _update("q")
        update.message.reply_text = AsyncMock(return_value=AsyncMock())
        reponse = routeur.ReponseCascade(texte="ok", etage_resolveur=routeur.ETAGE_DONNEE,
                                         routage_log_id=None)
        with (
            patch.object(bot_questions, "current_context", return_value=CTX),
            patch.object(bot_questions.routeur, "repondre_avec_cascade", return_value=reponse) as cascade,
            patch.object(bot_questions, "send_voice_reply", new=AsyncMock()),
        ):
            await bot_questions._ask_question(update, "q", nature=routeur.NATURE_QUESTION_DATA)
        decision = cascade.call_args.kwargs["decision"]
        assert decision.nature == routeur.NATURE_QUESTION_DATA
        assert decision.origine == routeur.ORIGINE_AGENT

    def test_us236_ca2_la_cascade_ne_reclasse_pas_une_nature_donnee(self):
        decision = routeur.DecisionRoutage(routeur.NATURE_QUESTION_DATA, routeur.ORIGINE_AGENT, 1.0)
        with (
            patch("app.services.cache_questions.servir", return_value=None),
            patch.object(routeur, "classer_demande") as classer,
            patch("app.services.questions.repondre_question_detaille",
                  return_value=("3 pépinières", True, None)),
            patch.object(routeur, "_persister_routage_log", return_value=None),
        ):
            resultat = routeur.repondre_avec_cascade(CTX, "quelles sont mes pépinières", decision=decision)
        classer.assert_not_called()
        assert resultat.texte == "3 pépinières"


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — un geste va au parseur, inchangé
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3Geste:

    def test_us236_ca3_saisir_geste_rend_un_aiguillage(self, agent_actif, modele, parcelles_connues):
        modele.return_value = _reponse(AppelOutil("saisir_geste", {}))
        resultat = interp.interpreter("bon les radis c'est fait", CTX)
        assert resultat.vers == interp.VERS_GESTE

    @pytest.mark.asyncio
    async def test_us236_ca3_le_bot_va_droit_au_parseur(self):
        aiguillage = interp.Aiguillage(vers=interp.VERS_GESTE)
        _, classer, ask, parse = await _handle_text("bon les radis c'est fait", aiguillage)
        classer.assert_not_called()
        ask.assert_not_called()
        parse.assert_awaited_once()


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — précision : une question ciblée, rien n'est proposé
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4Precision:

    def test_us236_ca4_demander_precision_porte_la_question(
        self, agent_actif, modele, parcelles_connues, sans_journal
    ):
        modele.return_value = _reponse(AppelOutil(
            "demander_precision", {"question": "Que veux-tu modifier sur « Serre extérieure » ?"}))
        resultat = interp.interpreter(VAGUE, CTX)
        assert resultat.vers == interp.VERS_PRECISION
        assert "Serre extérieure" in resultat.message
        sans_journal.assert_called_once()

    def test_us236_ca4_precision_sans_texte_reste_une_precision(self):
        aiguillage = interpreteur_agent.aiguillage_de(AppelOutil("demander_precision", {"question": "  "}), "x")
        assert aiguillage.message == interpreteur_agent.PRECISION_PAR_DEFAUT

    def test_us236_ca4_designation_relative_n_est_pas_un_nom(self):
        """« près des tomates » n'est pas un nom : aucune règle ne complète par supposition."""
        assert interp.reconnaitre_par_regles("supprime la parcelle près des tomates") is None
        assert interp.reconnaitre_par_regles("supprime la parcelle à côté du puits") is None

    def test_us236_ca4_un_vrai_nom_reste_reconnu(self):
        resultat = interp.reconnaitre_par_regles("supprime la parcelle nord")
        assert resultat.commande_equivalente() == "/parcelle supprimer nord"

    @pytest.mark.asyncio
    async def test_us236_ca4_rien_n_est_propose(self):
        bot_interpretation._INTERP_PENDING.pop(4242, None)
        aiguillage = interp.Aiguillage(vers=interp.VERS_PRECISION,
                                       message="Que veux-tu modifier sur « Serre extérieure » ?")
        update, classer, ask, parse = await _handle_text(VAGUE, aiguillage)
        texte = update.message.reply_text.await_args.args[0]
        assert texte.startswith("❓ Que veux-tu modifier sur « Serre extérieure » ?")
        assert "Rien n'a été fait" in texte
        assert 4242 not in bot_interpretation._INTERP_PENDING
        assert update.message.reply_text.await_args.kwargs.get("reply_markup") is None
        classer.assert_not_called()
        ask.assert_not_called()
        parse.assert_not_called()

    def test_us236_ca4_le_texte_du_modele_est_echappe(self):
        texte = bot_interpretation.texte_aiguillage(
            interp.Aiguillage(vers=interp.VERS_PRECISION, message="quelle *planche_nord* ?"))
        assert "planche\\_nord" in texte and "*" not in texte.split("\n")[0]


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — hors catalogue : « je ne sais pas encore faire ça », journalisé
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5HorsPerimetre:

    def test_us236_ca5_hors_perimetre_porte_la_raison(
        self, agent_actif, modele, parcelles_connues, sans_journal
    ):
        modele.return_value = _reponse(AppelOutil("hors_perimetre", {"raison": "exporter vers Excel"}))
        resultat = interp.interpreter(EXCEL, CTX)
        assert resultat.vers == interp.VERS_HORS_PERIMETRE
        assert resultat.message == "exporter vers Excel"
        sans_journal.assert_called_once()

    @pytest.mark.asyncio
    async def test_us236_ca5_aucune_liste_n_est_affichee(self):
        aiguillage = interp.Aiguillage(vers=interp.VERS_HORS_PERIMETRE, message="exporter vers Excel")
        update, classer, ask, parse = await _handle_text(EXCEL, aiguillage)
        texte = update.message.reply_text.await_args.args[0]
        assert "Je ne sais pas encore faire ça (exporter vers Excel)" in texte
        classer.assert_not_called()
        ask.assert_not_called()
        parse.assert_not_called()

    def test_us236_ca5_journalise_comme_demande_de_fonctionnalite(
        self, agent_actif, modele, parcelles_connues, session_de_test
    ):
        modele.return_value = _reponse(AppelOutil("hors_perimetre", {"raison": "exporter vers Excel"}))
        interp.interpreter(EXCEL, CTX)
        ligne = session_de_test.query(RoutageLog).one()
        assert ligne.issue_interpretation == interp.ISSUE_HORS_PERIMETRE
        assert ligne.origine_classification == interp.ORIGINE_AGENT
        assert ligne.outils_agent == "hors_perimetre"
        assert "excel" in ligne.question_normalisee
        assert ligne.potager_id == CTX.potager_id

    def test_us236_ca4_ca5_precision_journalisee(
        self, agent_actif, modele, parcelles_connues, session_de_test
    ):
        modele.return_value = _reponse(AppelOutil("demander_precision", {"question": "Quoi ?"}))
        interp.interpreter(VAGUE, CTX)
        assert session_de_test.query(RoutageLog).one().issue_interpretation == interp.ISSUE_PRECISION

    def test_us236_ca5_question_et_geste_ne_sont_pas_journalises_ici(
        self, agent_actif, modele, parcelles_connues, sans_journal
    ):
        """La cascade et le parseur ont leur propre journal : pas de double ligne."""
        modele.return_value = _reponse(AppelOutil("poser_question", {"nature": "QUESTION_DATA"}))
        interp.interpreter("quelles sont mes pépinières ?", CTX)
        sans_journal.assert_not_called()

    def test_us236_ca5_journal_en_panne_ne_bloque_pas(
        self, agent_actif, modele, parcelles_connues, monkeypatch
    ):
        monkeypatch.setattr("database.db.SessionLocal", MagicMock(side_effect=RuntimeError("base")))
        modele.return_value = _reponse(AppelOutil("hors_perimetre", {"raison": "export"}))
        assert interp.interpreter(EXCEL, CTX).vers == interp.VERS_HORS_PERIMETRE


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — les paires piégeuses
# ═════════════════════════════════════════════════════════════════════════════
_MODELE_SIMULE = {
    "la serre extérieure est-elle une pépinière ?":
        AppelOutil("poser_question", {"nature": "QUESTION_DATA"}),
    "la serre extérieure n'est plus une pépinière":
        AppelOutil(OUTIL_MODIFIER_PARCELLE, {"parcelle": "Serre extérieure", "est_pepiniere": False}),
    "quelles sont mes pépinières ?":
        AppelOutil("poser_question", {"nature": "QUESTION_DATA"}),
}


class TestCA6PairesPiegeuses:

    @pytest.fixture
    def modele_par_phrase(self, modele):
        modele.side_effect = lambda **kw: _reponse(_MODELE_SIMULE[kw["message_utilisateur"]])
        return modele

    def test_us236_ca6_affirmation_commande(self, agent_actif, modele_par_phrase, parcelles_connues):
        resultat = interp.interpreter("la serre extérieure est une pépinière", CTX)
        assert isinstance(resultat, interp.CommandeInterpretee)
        assert resultat.commande_equivalente().endswith("pepiniere=oui")
        modele_par_phrase.assert_not_called()  # les règles suffisent

    def test_us236_ca6_interrogation_question(self, agent_actif, modele_par_phrase, parcelles_connues):
        resultat = interp.interpreter("la serre extérieure est-elle une pépinière ?", CTX)
        assert isinstance(resultat, interp.Aiguillage)
        assert resultat.vers == interp.VERS_QUESTION

    def test_us236_ca6_negation_commande(self, agent_actif, modele_par_phrase, parcelles_connues):
        resultat = interp.interpreter("la serre extérieure n'est plus une pépinière", CTX)
        assert isinstance(resultat, interp.CommandeInterpretee)
        assert resultat.commande_equivalente() == "/parcelle modifier Serre extérieure pepiniere=non"

    def test_us236_ca6_liste_question(self, agent_actif, modele_par_phrase, parcelles_connues):
        resultat = interp.interpreter("quelles sont mes pépinières ?", CTX)
        assert isinstance(resultat, interp.Aiguillage)
        assert resultat.nature_question == routeur.NATURE_QUESTION_DATA


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — une demande de procédure est captée avant l'agent
# ═════════════════════════════════════════════════════════════════════════════
class TestCA7Procedure:

    @pytest.mark.parametrize("phrase", [
        "comment supprimer une parcelle ?",
        "comment on fait pour passer une parcelle en pépinière",
    ])
    def test_us236_ca7_aucun_appel_au_modele(self, agent_actif, modele, phrase):
        assert interp.interpreter(phrase, CTX) is None
        modele.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — les mots-clés du routeur restent actifs hors prise en charge
# ═════════════════════════════════════════════════════════════════════════════
class TestCA8MotsClesActifs:

    @pytest.mark.asyncio
    async def test_us236_ca8_sans_aiguillage_le_routeur_classe(self):
        _, classer, _, _ = await _handle_text(EXCEL, None)
        classer.assert_called_once()

    @pytest.mark.parametrize("mode", ["off", "ombre"])
    def test_us236_ca8_hors_mode_actif_pas_d_aiguillage(self, monkeypatch, modele, mode):
        monkeypatch.setattr(config, "AGENT_MODE", mode)
        monkeypatch.setattr(interpreteur_agent, "lancer_en_arriere_plan", lambda f: None)
        with patch.object(interp, "_appeler_modele", return_value=None):
            assert interp.interpreter(EXCEL, CTX) is None

    def test_us236_ca8_modele_indisponible_pas_d_aiguillage(self, agent_actif, modele, parcelles_connues):
        modele.side_effect = RuntimeError("429")
        with patch.object(interp, "_appeler_modele", return_value=None):
            assert interp.interpreter(EXCEL, CTX) is None

    def test_us236_ca8_rejet_du_validateur_pas_d_aiguillage(self, agent_actif, modele, parcelles_connues):
        modele.return_value = _reponse(AppelOutil("outil_inexistant", {}))
        assert interp.interpreter(EXCEL, CTX) is None


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — l'ordre des étages
# ═════════════════════════════════════════════════════════════════════════════
class TestCA9OrdreDesEtages:

    def test_us236_ca9_ordre_dans_handle_text(self):
        """Gardes de conversation → règles → filtres → agent → routeur → cascade."""
        source = inspect.getsource(bot_messages.handle_text)
        reperes = [
            "_verifier_liaison_ou_onboarding(",           # garde de liaison
            "_interp_completion_texte(",                  # gardes de flux en cours
            "if mode == 'ask'",
            "reconnaitre_par_regles(",                    # règles
            "_is_requete_godets(",                        # filtres sans modèle
            "svc_interpreteur.interpreter(",              # agent (filtres de savoir/geste dedans)
            "svc_interpreteur.VERS_QUESTION",             # aiguillage suivi
            "routeur.classer_demande(",                   # routeur
            "_parse_and_save(",                           # parseur de gestes (le dernier appel)
        ]
        positions = [source.index(repere) for repere in reperes[:-1]] + [source.rindex(reperes[-1])]
        assert positions == sorted(positions)

    def test_us236_ca9_ordre_dans_interpreter(self):
        source = inspect.getsource(interp.interpreter)
        reperes = ["reconnaitre_par_regles(", "_est_demande_de_savoir(", "annonce_un_geste(",
                   "interpreteur_agent.proposer(", "_appeler_modele("]
        positions = [source.index(repere) for repere in reperes]
        assert positions == sorted(positions)

    def test_us236_ca9_ordre_dans_handle_voice(self):
        source = inspect.getsource(bot_messages.handle_voice)
        reperes = ["if mode == 'ask'", "svc_interpreteur.interpreter(",
                   "svc_interpreteur.VERS_QUESTION", "routeur.classer_par_regles(", "parse_message("]
        positions = [source.index(repere) for repere in reperes]
        assert positions == sorted(positions)

    def test_us236_ca9_un_geste_annonce_n_atteint_pas_l_agent(self, agent_actif, modele):
        assert interp.interpreter("j'ai récolté 3 kg de tomates hier", CTX) is None
        modele.assert_not_called()

    def test_us236_ca9_une_regle_passe_avant_l_agent(self, agent_actif, modele):
        assert interp.interpreter("la planche nord a 5 rangs", CTX).origine == interp.ORIGINE_REGLE
        modele.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# Gherkin — canal vocal, même comportement
# ═════════════════════════════════════════════════════════════════════════════
class TestCanalVocal:

    @pytest.mark.asyncio
    async def test_us236_vocal_hors_perimetre_edite_le_message_d_attente(self):
        msg = AsyncMock()
        aiguillage = interp.Aiguillage(vers=interp.VERS_HORS_PERIMETRE, message="exporter vers Excel")
        pris = await bot_interpretation._traiter_commande_interpretee(_update(EXCEL), MagicMock(),
                                                                      aiguillage, msg=msg)
        assert pris is True
        assert "Je ne sais pas encore faire ça" in msg.edit_text.await_args.args[0]

    @pytest.mark.asyncio
    async def test_us236_vocal_question_et_geste_rendent_la_main(self):
        for vers in (interp.VERS_QUESTION, interp.VERS_GESTE):
            pris = await bot_interpretation._traiter_commande_interpretee(
                _update("x"), MagicMock(), interp.Aiguillage(vers=vers))
            assert pris is False

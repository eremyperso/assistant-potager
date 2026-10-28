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


def _texte(texte: str) -> ReponseOutils:
    """[US-257] Le tour où le modèle répond en texte, sans outil : il clôt la boucle."""
    return ReponseOutils(texte=texte, modele="test", appel_type=passerelle.TYPE_AGENT)


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
    monkeypatch.setattr(interpreteur_agent, "persister_reponse", MagicMock())
    return interpreteur_agent.persister_reponse


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
# CA1 — [US-257] l'agent ne choisit plus toujours un outil : il peut répondre en texte.
# `tool_choice="required"`, `poser_question`, `demander_precision` et `hors_perimetre`
# sont remplacés (tests/test_us257_compagnon_repond_en_texte.py). Reste l'aiguillage
# vers le parseur de gestes.
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1ToujoursUnOutil:

    def test_us236_ca1_l_outil_terminal_qui_reste_est_au_catalogue(self):
        noms = {o.nom for o in catalogue_outils.outils()}
        assert set(catalogue_outils.OUTILS_TERMINAUX) == {"saisir_geste"} <= noms


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — une question va à la cascade, sans mots-clés
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2Question:

    def test_us257_une_question_va_a_la_cascade_sans_appel_au_modele(
        self, agent_actif, modele, parcelles_connues
    ):
        """[US-257] Plus de `poser_question` : la phrase interrogative va à la cascade, qui la classe."""
        resultat = interp.interpreter("quelles sont mes pépinières ?", CTX)
        assert isinstance(resultat, interp.Aiguillage)
        assert resultat.vers == interp.VERS_QUESTION and resultat.nature_question is None
        modele.assert_not_called()

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

    def test_us257_le_refus_du_validateur_devient_une_question_redigee(
        self, agent_actif, modele, parcelles_connues, sans_journal
    ):
        """[US-257] « Modifie ma serre » ne dit aucun champ : le validateur refuse, le modèle demande."""
        modele.side_effect = [
            _reponse(AppelOutil(OUTIL_MODIFIER_PARCELLE, {"parcelle": "Serre extérieure"}, id="m1")),
            _texte("Que veux-tu changer sur la Serre extérieure : ses rangs, son abri, son paillage ?"),
        ]
        resultat = interp.interpreter(VAGUE, CTX)
        assert isinstance(resultat, interp.ReponseAgent) and resultat.proposition is None
        assert "Serre extérieure" in resultat.texte
        sans_journal.assert_called_once()

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
        reponse = interp.ReponseAgent(texte="Que veux-tu changer sur la Serre extérieure ?",
                                      texte_origine=VAGUE)
        update, classer, ask, parse = await _handle_text(VAGUE, reponse)
        texte = update.message.reply_text.await_args.args[0]
        # [US-257 / CA6] Le texte de l'agent, sans le « Rien n'a été fait. Redis ta demande ».
        assert texte == "Que veux-tu changer sur la Serre extérieure ?"
        assert 4242 not in bot_interpretation._INTERP_PENDING
        assert update.message.reply_text.await_args.kwargs.get("reply_markup") is None
        classer.assert_not_called()
        ask.assert_not_called()
        parse.assert_not_called()

    def test_us257_le_texte_de_l_agent_est_echappe_devant_un_recapitulatif(self):
        texte = bot_interpretation.texte_de_l_agent("quelle *planche_nord* ?")
        assert texte == "quelle planche\\_nord ?"


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — hors catalogue : expliqué par l'agent, journalisé
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5HorsPerimetre:

    def _manque(self, modele):
        modele.side_effect = [
            _reponse(AppelOutil("manque_catalogue", {"demande": "exporter vers Excel"}, id="x1")),
            _texte("Je ne sais pas encore exporter vers Excel ; je peux te résumer ta saison."),
        ]

    def test_us257_manque_catalogue_porte_la_demande(
        self, agent_actif, modele, parcelles_connues, sans_journal
    ):
        self._manque(modele)
        resultat = interp.interpreter(EXCEL, CTX)
        assert resultat.manque_catalogue == "exporter vers Excel"
        assert resultat.texte.startswith("Je ne sais pas encore exporter vers Excel")
        sans_journal.assert_called_once()

    @pytest.mark.asyncio
    async def test_us236_ca5_aucune_liste_n_est_affichee(self):
        reponse = interp.ReponseAgent(texte="Je ne sais pas encore exporter vers Excel.",
                                      manque_catalogue="exporter vers Excel", texte_origine=EXCEL)
        update, classer, ask, parse = await _handle_text(EXCEL, reponse)
        assert update.message.reply_text.await_args.args[0] == "Je ne sais pas encore exporter vers Excel."
        classer.assert_not_called()
        ask.assert_not_called()
        parse.assert_not_called()

    def test_us236_ca5_journalise_comme_demande_de_fonctionnalite(
        self, agent_actif, modele, parcelles_connues, session_de_test
    ):
        self._manque(modele)
        interp.interpreter(EXCEL, CTX)
        ligne = session_de_test.query(RoutageLog).one()
        assert ligne.issue_interpretation == interp.ISSUE_HORS_PERIMETRE
        assert ligne.origine_classification == interp.ORIGINE_AGENT
        assert ligne.outils_agent == "manque_catalogue"
        assert "excel" in ligne.question_normalisee
        assert ligne.potager_id == CTX.potager_id

    def test_us236_ca4_ca5_precision_journalisee(
        self, agent_actif, modele, parcelles_connues, session_de_test
    ):
        modele.side_effect = [
            _reponse(AppelOutil(OUTIL_MODIFIER_PARCELLE, {"parcelle": "Serre extérieure"}, id="m1")),
            _texte("Que veux-tu changer ?"),
        ]
        interp.interpreter(VAGUE, CTX)
        assert session_de_test.query(RoutageLog).one().issue_interpretation == interp.ISSUE_PRECISION

    def test_us236_ca5_geste_et_conversation_ne_sont_pas_journalises_ici(
        self, agent_actif, modele, parcelles_connues, sans_journal
    ):
        """Le parseur a son propre journal ; un « merci » n'est pas une demande."""
        modele.return_value = _reponse(AppelOutil("saisir_geste", {}))
        interp.interpreter("bon les radis c'est fait", CTX)
        sans_journal.assert_not_called()

    def test_us236_ca5_journal_en_panne_ne_bloque_pas(
        self, agent_actif, modele, parcelles_connues, monkeypatch
    ):
        monkeypatch.setattr("database.db.SessionLocal", MagicMock(side_effect=RuntimeError("base")))
        self._manque(modele)
        assert interp.interpreter(EXCEL, CTX).manque_catalogue == "exporter vers Excel"


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — les paires piégeuses
# ═════════════════════════════════════════════════════════════════════════════
_MODELE_SIMULE = {
    "la serre extérieure n'est plus une pépinière":
        AppelOutil(OUTIL_MODIFIER_PARCELLE, {"parcelle": "Serre extérieure", "est_pepiniere": False}),
}


class TestCA6PairesPiegeuses:

    @pytest.fixture
    def modele_par_phrase(self, modele):
        # [US-257] Le modèle propose au premier tour, répond en texte après le verdict.
        modele.side_effect = lambda **kw: (
            _texte("Je te propose ceci.") if kw.get("historique")
            else _reponse(_MODELE_SIMULE[kw["message_utilisateur"]])
        )
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
        modele_par_phrase.assert_not_called()

    def test_us236_ca6_negation_commande(self, agent_actif, modele_par_phrase, parcelles_connues):
        resultat = interp.interpreter("la serre extérieure n'est plus une pépinière", CTX)
        assert isinstance(resultat.proposition, interp.CommandeInterpretee)
        assert resultat.proposition.commande_equivalente() == "/parcelle modifier Serre extérieure pepiniere=non"

    def test_us236_ca6_liste_question(self, agent_actif, modele_par_phrase, parcelles_connues):
        resultat = interp.interpreter("quelles sont mes pépinières ?", CTX)
        assert isinstance(resultat, interp.Aiguillage) and resultat.vers == interp.VERS_QUESTION
        modele_par_phrase.assert_not_called()


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
        reponse = interp.ReponseAgent(texte="Je ne sais pas encore exporter vers Excel.",
                                      manque_catalogue="exporter vers Excel", texte_origine=EXCEL)
        with patch.object(bot_interpretation, "current_context", return_value=CTX):
            pris = await bot_interpretation._traiter_commande_interpretee(_update(EXCEL), MagicMock(),
                                                                          reponse, msg=msg)
        assert pris is True
        assert msg.edit_text.await_args.args[0] == "Je ne sais pas encore exporter vers Excel."

    @pytest.mark.asyncio
    async def test_us236_vocal_question_et_geste_rendent_la_main(self):
        for vers in (interp.VERS_QUESTION, interp.VERS_GESTE):
            pris = await bot_interpretation._traiter_commande_interpretee(
                _update("x"), MagicMock(), interp.Aiguillage(vers=vers))
            assert pris is False

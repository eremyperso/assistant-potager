"""
tests/test_us284_question_en_attente.py — Répondre d'un mot à la question du compagnon [US-284]
==============================================================================================
« Supprime la planche » → « Laquelle : Planche Nord ou Planche Sud ? » → « la planche sud » :
la réponse courte est lue avec la question que le compagnon vient de poser, et donne la
proposition de supprimer Planche Sud. « oui » à une question qui offre une action donne la
carte, jamais un salut. Une demande nouvelle efface la question ; elle expire à 10 minutes.

Aucun appel réseau (CA6) : la passerelle est simulée (`modele`), la base est celle de la
fixture `memoire_compagnon`.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.bot import interpretation as bot_interpretation
from app.services import interpreteur_commandes as interp
from app.services.agent import contexte_court, interpreteur_agent
from app.services.agent.catalogue_outils import OUTILS_DECISION
from app.services.agent.contexte_court import Echange, QuestionEnAttente
from app.services.compagnon import conversations
from app.services.compagnon import propositions as svc_propositions
from app.services.context import TenantContext
from llm import passerelle
from llm.passerelle import AppelOutil, ReponseOutils

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
PARCELLES = ("Planche Nord", "Planche Sud", "Serre")
QUESTION_LAQUELLE = "Laquelle veux-tu supprimer : Planche Nord ou Planche Sud ?"


# ═════════════════════════════════════════════════════════════════════════════
# Outillage
# ═════════════════════════════════════════════════════════════════════════════
def _reponse(*appels: AppelOutil, texte: str = "") -> ReponseOutils:
    return ReponseOutils(
        texte=texte, modele="test", appel_type=passerelle.TYPE_AGENT,
        tokens_in=900, tokens_out=50, latence_ms=400, appels=appels, statut=passerelle.STATUT_OK,
    )


def _supprimer(nom: str) -> AppelOutil:
    return AppelOutil("supprimer_parcelle", {"nom": nom})


def _question(phrase: str = "Supprime la planche", question: str = QUESTION_LAQUELLE,
              choix: tuple[str, ...] = ("Planche Nord", "Planche Sud")) -> QuestionEnAttente:
    return QuestionEnAttente(phrase=phrase, question=question, choix=choix, ts=time.time())


def _contexte(question: QuestionEnAttente | None = None) -> contexte_court.ContexteCourt:
    echanges = (Echange("Supprime la planche", f"réponse : {QUESTION_LAQUELLE}", time.time()),)
    return contexte_court.construire(CTX, echanges=echanges, question=question or _question())


def _update():
    update = MagicMock()
    update.effective_user.id = 4242
    update.effective_chat.id = 4242
    update.message = AsyncMock()
    update.message.reply_to_message = None
    update.callback_query = None
    return update


def _contexte_du_bot():
    """Le contexte que le bot construit pour la phrase suivante, lu en base."""
    with patch.object(bot_interpretation, "current_context", return_value=CTX):
        return bot_interpretation.contexte_court_de(_update())


def _noter_question(il_y_a_min: float = 0.0, question: QuestionEnAttente | None = None) -> None:
    conversations.noter(
        CTX, "Supprime la planche", f"réponse : {QUESTION_LAQUELLE}", canal=svc_propositions.CANAL_TELEGRAM,
        question=(question or _question()).donnees(),
        maintenant=datetime.utcnow() - timedelta(minutes=il_y_a_min),
    )


@pytest.fixture
def modele():
    with patch.object(passerelle, "appeler_chat_outils") as faux:
        yield faux


@pytest.fixture
def parcelles_connues(monkeypatch):
    monkeypatch.setattr(interpreteur_agent, "noms_parcelles_du_potager", lambda ctx: PARCELLES)
    monkeypatch.setattr(interpreteur_agent, "voisin_en_base", lambda ctx: (lambda nom: None))


def _noms_offerts(appel) -> set[str]:
    return {outil["function"]["name"] for outil in appel.kwargs["outils"]}


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — la question est gardée quand l'agent finit par une question pour agir
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1QuestionGardee:

    def test_us284_ca1_une_demande_d_agir_finie_par_une_question_la_garde(self, modele, parcelles_connues):
        modele.return_value = _reponse(texte=QUESTION_LAQUELLE)
        resultat = interpreteur_agent.proposer("Supprime la planche", CTX, None)
        assert resultat.proposition is None
        question = resultat.question_en_attente
        assert question is not None
        assert question.phrase == "Supprime la planche"
        assert question.question == QUESTION_LAQUELLE
        assert question.choix == ("Planche Nord", "Planche Sud")

    def test_us284_ca1_une_ecriture_refusee_pour_une_valeur_manquante_la_garde(self, modele, parcelles_connues):
        # « ma planche » n'est pas une demande d'agir reconnue ; le refus du validateur l'est.
        modele.side_effect = [
            _reponse(AppelOutil("renommer_parcelle", {"ancien": "Planche Nord"})),
            _reponse(texte="Quel nouveau nom veux-tu lui donner ?"),
        ]
        resultat = interpreteur_agent.proposer("ma planche nord, un autre nom", CTX, None)
        assert resultat.question_en_attente is not None

    def test_us284_ca1_une_question_qui_offre_une_action_la_garde(self, modele, parcelles_connues):
        modele.return_value = _reponse(texte="La Serre a souffert du gel. Veux-tu que je note un traitement ?")
        resultat = interpreteur_agent.proposer("la serre a gelé cette nuit", CTX, None)
        assert resultat.question_en_attente is not None

    def test_us284_ca1_une_conversation_simple_n_en_garde_pas(self, modele, parcelles_connues):
        modele.return_value = _reponse(texte="Avec plaisir ! Comment va le potager ?")
        resultat = interpreteur_agent.proposer("merci", CTX, None)
        assert resultat.question_en_attente is None

    def test_us284_ca1_un_texte_sans_question_n_en_garde_pas(self, modele, parcelles_connues):
        modele.return_value = _reponse(texte="Je ne trouve pas cette parcelle.")
        resultat = interpreteur_agent.proposer("Supprime la planche", CTX, None)
        assert resultat.question_en_attente is None

    def test_us284_ca1_une_proposition_n_en_garde_pas(self, modele, parcelles_connues):
        modele.return_value = _reponse(_supprimer("Planche Sud"), texte="Tu confirmes ?")
        resultat = interpreteur_agent.proposer("Supprime la planche sud", CTX, None)
        assert resultat.proposition is not None
        assert resultat.question_en_attente is None

    def test_us284_ca1_la_question_passe_a_la_reponse_agent(self, modele, parcelles_connues, monkeypatch):
        monkeypatch.setattr(interp, "_mode_agent", lambda: interp.MODE_PRIORITAIRE)
        modele.return_value = _reponse(texte=QUESTION_LAQUELLE)
        resultat = interp.interpreter("Supprime la planche", CTX, contexte_court=None)
        assert isinstance(resultat, interp.ReponseAgent)
        assert resultat.question_en_attente is not None
        assert contexte_court.echange_de(resultat).question["choix"] == ["Planche Nord", "Planche Sud"]

    def test_us284_ca1_le_bot_la_range_en_base_avec_l_echange(self):
        reponse = interp.ReponseAgent(texte=QUESTION_LAQUELLE, texte_origine="Supprime la planche",
                                      question_en_attente=_question())
        with patch.object(bot_interpretation, "current_context", return_value=CTX):
            bot_interpretation._noter_echange(reponse)
        echanges = conversations.recents(CTX)
        assert echanges[-1].question == _question().donnees()
        assert contexte_court.question_de(echanges).choix == ("Planche Nord", "Planche Sud")


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — la réponse courte est lue avec la question
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2ReponseCourte:

    def test_us284_ca2_le_contexte_porte_la_question_et_sa_consigne(self):
        contexte = _contexte()
        donnees = contexte.donnees()["question_en_attente"]
        assert donnees == {"phrase_du_jardinier": "Supprime la planche", "ta_question": QUESTION_LAQUELLE,
                           "choix": ["Planche Nord", "Planche Sud"]}
        assert "question_en_attente" in contexte.prompt()
        assert "ne repose pas la question" in contexte.prompt()
        # Le prompt fixe, mesuré, n'est pas touché.
        assert "question_en_attente" not in interpreteur_agent.PROMPT_FIXE_PRIORITAIRE

    def test_us284_ca2_la_planche_sud_donne_la_suppression(self, modele, parcelles_connues):
        modele.return_value = _reponse(_supprimer("Planche Sud"))
        resultat = interpreteur_agent.proposer("la planche sud", CTX, _contexte())
        appel = modele.call_args
        # Le modèle reçoit la réponse SEULE ; la question est dans la partie variable.
        assert appel.kwargs["message_utilisateur"] == "la planche sud"
        assert "question_en_attente" in appel.kwargs["prompt_variable"]
        # La projection voit le verbe de destruction de la phrase d'origine (mode actif).
        assert "supprimer_parcelle" in _noms_offerts(appel)
        assert resultat.commande is not None
        assert resultat.commande.commande_equivalente() == "/parcelle supprimer Planche Sud"
        assert resultat.question_en_attente is None

    def test_us284_ca2_le_validateur_ancre_sur_phrase_d_origine_et_reponse(self, modele, parcelles_connues):
        modele.return_value = _reponse(_supprimer("Planche Sud"))
        resultat = interpreteur_agent.proposer("la planche sud", CTX, _contexte())
        assert resultat.commande.texte_origine == "Supprime la planche ; la planche sud"

    def test_us284_ca2_sans_question_la_reponse_courte_n_offre_pas_la_suppression(self, modele, parcelles_connues):
        modele.return_value = _reponse(texte="De quelle planche parles-tu ?")
        interpreteur_agent.proposer("la planche sud", CTX, None)
        assert "supprimer_parcelle" not in _noms_offerts(modele.call_args)

    def test_us284_ca2_une_seconde_question_garde_la_phrase_ancree(self, modele, parcelles_connues):
        modele.return_value = _reponse(texte="Planche Nord ou Planche Sud ?")
        resultat = interpreteur_agent.proposer("la planche", CTX, _contexte())
        assert resultat.question_en_attente.phrase == "Supprime la planche ; la planche"

    def test_us284_ca2_la_suppression_reste_au_bouton_seul(self):
        commande = interp._construire_commande(
            interp.FORMES_PAR_CLE[("parcelle", "supprimer")], {"nom": "Planche Sud"},
            interp.ORIGINE_AGENT, 1.0, "Supprime la planche ; la planche sud",
        )
        from app.services.compagnon import decisions
        assert decisions.est_destructrice(commande)

    def test_us284_ca2_le_bot_lit_la_question_en_base(self):
        _noter_question(il_y_a_min=2)
        contexte = _contexte_du_bot()
        assert contexte is not None and contexte.question is not None
        assert contexte.question.phrase == "Supprime la planche"


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — « oui » à une question qui offrait une action donne la carte
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3Oui:

    def _offre(self) -> contexte_court.ContexteCourt:
        return _contexte(_question(question="Veux-tu que je supprime la Planche Sud ?", choix=("Planche Sud",)))

    def test_us284_ca3_oui_donne_la_proposition(self, modele, parcelles_connues):
        modele.return_value = _reponse(_supprimer("Planche Sud"))
        resultat = interpreteur_agent.proposer("oui", CTX, self._offre())
        assert resultat.commande is not None and resultat.decision is None

    @pytest.mark.parametrize("accord", ["oui", "vas-y", "d'accord"])
    def test_us284_ca3_un_salut_est_relance_une_fois(self, modele, parcelles_connues, accord):
        modele.side_effect = [_reponse(texte="Salut, potager !"), _reponse(_supprimer("Planche Sud")),
                              _reponse(texte="")]
        resultat = interpreteur_agent.proposer(accord, CTX, self._offre())
        relance = modele.call_args_list[1].kwargs["historique"][-1]["content"]
        assert "répond à ta question" in relance and "Supprime la planche" in relance
        assert resultat.commande is not None

    def test_us284_ca3_oui_a_deux_choix_ne_designe_aucune_parcelle(self, modele, parcelles_connues):
        # « Laquelle : Planche Nord ou Planche Sud ? » → « oui » : le modèle qui devinerait est refusé.
        modele.return_value = _reponse(_supprimer("Planche Sud"))
        resultat = interpreteur_agent.proposer("oui", CTX, _contexte())
        assert resultat.commande is None
        assert "Planche Nord" in resultat.texte and "Planche Sud" in resultat.texte

    def test_us284_ca3_aucun_outil_de_decision_n_est_offert(self, modele, parcelles_connues):
        modele.return_value = _reponse(_supprimer("Planche Sud"))
        interpreteur_agent.proposer("oui", CTX, self._offre())
        assert not _noms_offerts(modele.call_args) & set(OUTILS_DECISION)

    def test_us284_ca3_la_question_prime_sur_la_derniere_proposition_traitee(self):
        traitee = contexte_court.Traitee(code="p1", etat="confirmee", resume="/parcelle ajouter Serre")
        contexte = contexte_court.construire(CTX, question=_question(), traitee=traitee)
        assert contexte.traitee is None and not contexte.decidable

    def test_us284_ca3_offre_une_action(self):
        assert contexte_court.offre_une_action("Veux-tu que je supprime la Planche Sud ?")
        assert contexte_court.offre_une_action("Si tu veux, je te le rappelle demain ?")
        assert not contexte_court.offre_une_action("Veux-tu que je supprime la Planche Sud.")
        assert not contexte_court.offre_une_action("Comment va le potager ?")


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — une demande nouvelle efface la question ; jamais d'écriture seule
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4Effacement:

    def test_us284_ca4_une_demande_nouvelle_efface_la_question(self, modele, parcelles_connues):
        modele.return_value = _reponse(AppelOutil("creer_parcelle", {"nom": "Planche Ouest"}))
        resultat = interpreteur_agent.proposer("crée la planche ouest", CTX, _contexte())
        appel = modele.call_args
        assert "question_en_attente" not in appel.kwargs["prompt_variable"]
        # Plus d'ancrage : la destruction d'origine ne déverrouille rien.
        assert "supprimer_parcelle" not in _noms_offerts(appel)
        if resultat.commande is not None:
            assert resultat.commande.texte_origine == "crée la planche ouest"

    def test_us284_ca4_une_question_du_jardinier_efface_la_question(self, modele, parcelles_connues):
        modele.return_value = _reponse(texte="Il fera beau.")
        interpreteur_agent.proposer("quel temps fera-t-il demain ?", CTX, _contexte())
        assert "question_en_attente" not in modele.call_args.kwargs["prompt_variable"]

    @pytest.mark.parametrize("refus", ["non", "laisse tomber", "Non merci."])
    def test_us284_ca4_un_refus_n_est_pas_relance(self, modele, parcelles_connues, refus):
        modele.return_value = _reponse(texte="D'accord, je ne touche à rien.")
        resultat = interpreteur_agent.proposer(refus, CTX, _contexte())
        assert modele.call_count == 1
        assert resultat.proposition is None and resultat.decision is None

    def test_us284_ca4_une_question_ne_fait_jamais_ecrire_seule(self, modele, parcelles_connues):
        # Le modèle s'obstine en texte : rien n'est proposé, rien n'est décidé.
        modele.return_value = _reponse(texte="Tu es sûr ?")
        resultat = interpreteur_agent.proposer("oui", CTX, _contexte())
        assert resultat.proposition is None and resultat.decision is None

    def test_us284_ca4_un_echange_plus_recent_consomme_la_question(self):
        _noter_question(il_y_a_min=3)
        conversations.noter(CTX, "merci", "réponse : Avec plaisir !", canal=svc_propositions.CANAL_TELEGRAM,
                            maintenant=datetime.utcnow() - timedelta(minutes=1))
        assert contexte_court.question_de(conversations.recents(CTX)) is None

    def test_us284_ca4_une_phrase_sans_echange_clot_la_question(self):
        _noter_question(il_y_a_min=1)
        incompris = interp.Aiguillage(vers=interp.VERS_NON_COMPRIS, texte_origine="blabla")
        with patch.object(bot_interpretation, "current_context", return_value=CTX):
            bot_interpretation._noter_echange(incompris)
        assert contexte_court.question_de(conversations.recents(CTX)) is None

    @pytest.mark.asyncio
    async def test_us284_ca4_une_phrase_partie_ailleurs_clot_la_question(self):
        _noter_question(il_y_a_min=1)
        with patch.object(bot_interpretation, "current_context", return_value=CTX):
            pris = await bot_interpretation._traiter_commande_interpretee(_update(), MagicMock(), None)
        assert pris is False
        assert contexte_court.question_de(conversations.recents(CTX)) is None

    def test_us284_ca4_clore_sans_base_ne_leve_pas(self, monkeypatch):
        monkeypatch.setattr(conversations, "SessionLocal", MagicMock(side_effect=RuntimeError("base")))
        conversations.clore_question(CTX)  # la mémoire ne casse jamais la réponse

    @pytest.mark.parametrize("phrase,refus", [
        ("non", True), ("Non merci.", True), ("laisse tomber", True), ("ni l'un ni l'autre", True),
        ("non, la sud", False), ("oui", False), ("la planche sud", False),
    ])
    def test_us284_ca4_refuse_la_question(self, phrase, refus):
        assert contexte_court.refuse_la_question(phrase) is refus


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — expiration, et la forme rangée
# ═════════════════════════════════════════════════════════════════════════════
class TestCA6Expiration:

    def test_us284_ca6_la_question_vit_dix_minutes(self):
        _noter_question(il_y_a_min=9)
        assert _contexte_du_bot().question is not None

    def test_us284_ca6_au_dela_elle_est_ignoree(self):
        _noter_question(il_y_a_min=11)
        contexte = _contexte_du_bot()
        assert contexte is not None and contexte.question is None  # la conversation, elle, dure 30 min

    def test_us284_ca6_question_de_sans_echange(self):
        assert contexte_court.question_de(()) is None

    def test_us284_ca6_une_forme_illisible_est_ignoree(self):
        echange = Echange("x", "y", time.time(), {"question": "sans phrase"})
        assert contexte_court.question_de((echange,)) is None

    def test_us284_ca6_aller_retour_de_la_forme_rangee(self):
        question = _question()
        relue = QuestionEnAttente.depuis(question.donnees(), question.ts)
        assert relue == question

    def test_us284_ca6_les_choix_dans_l_ordre_de_la_question(self):
        assert contexte_court.choix_nommes("La sud ou la nord ? Planche Sud ou Planche Nord ?", PARCELLES) == (
            "Planche Sud", "Planche Nord")
        assert contexte_court.choix_nommes("Laquelle ?", PARCELLES) == ()

    def test_us284_ca6_une_longue_phrase_est_tronquee_par_le_debut(self):
        question = contexte_court.nouvelle_question("a" * 400 + " fin", "Laquelle ?", PARCELLES)
        assert len(question.phrase) == contexte_court.LONGUEUR_QUESTION_MAX and question.phrase.endswith("fin")


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — le corpus de terrain porte les dialogues ; l'outil de mesure garde la question
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5Corpus:

    def test_us284_ca5_les_dialogues_question_reponse_sont_au_corpus(self):
        from tools import evaluer_dialogues as ed

        dialogues = {d.id: d for d in ed.charger_corpus(ed.CORPUS_TERRAIN)}
        assert {"TER-29", "TER-30", "TER-36", "TER-37"} <= set(dialogues)
        assert [t.jardinier for t in dialogues["TER-37"].tours if t.jardinier][-1] == "oui"
        assert dialogues["TER-36"].tours[1].attendu.parametres == {
            "ancien": "planche test", "nouveau": "planche des courges"}

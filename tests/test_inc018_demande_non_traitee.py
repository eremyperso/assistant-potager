"""
tests/test_inc018_demande_non_traitee.py — Une demande d'agir ne repart pas au routeur [INC-018]
================================================================================================
« Créez la planche Nord… » dictée, l'agent échoue (appel rejeté, panne, proposition refusée) :
la phrase retombait sur le routeur par mots-clés, qui répondait par la liste des lots en
pépinière avec une confiance de 1,00. Pour une phrase qui s'ouvre sur un verbe d'action, le
jardinier lit maintenant que la demande n'a pas été traitée, et la commande à taper.

Aucun appel réseau : la passerelle est simulée, le bot est piloté par des mocks.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app import config
from app.bot import interpretation as bot_interpretation
from app.bot import messages as bot_messages
from app.services import interpreteur_commandes as interp
from app.services.agent import contexte_court, interpreteur_agent
from app.services.context import TenantContext
from llm import passerelle, routeur
from llm.passerelle import AppelOutil, ReponseOutils

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
PARCELLES = ("Serre extérieure", "Planche Nord", "Planche Sud", "Tunnel")
INCIDENT = "Créez la planche Nord de 8 mètres de long avec 4 rangs et mets la serre en pépinière froide."


def _reponse(*appels: AppelOutil, statut: str = passerelle.STATUT_OK) -> ReponseOutils:
    return ReponseOutils(texte="", modele="test", appel_type=passerelle.TYPE_AGENT,
                         latence_ms=400, appels=appels, statut=statut)


@pytest.fixture
def parcelles_connues(monkeypatch):
    monkeypatch.setattr(interpreteur_agent, "noms_parcelles_du_potager", lambda ctx: PARCELLES)
    monkeypatch.setattr(interpreteur_agent, "voisin_en_base", lambda ctx: (lambda nom: None))


@pytest.fixture
def modele():
    with patch.object(passerelle, "appeler_chat_outils") as faux:
        yield faux


@pytest.fixture
def ancien_repli_muet():
    """L'ancien repli (modèle sous contrainte fermée) ne propose rien."""
    with patch.object(interp, "_appeler_modele", return_value=None) as faux:
        yield faux


def _mode(monkeypatch, valeur: str) -> None:
    monkeypatch.setattr(config, "AGENT_MODE", valeur)


# ═════════════════════════════════════════════════════════════════════════════
# Reconnaître une phrase qui demande d'agir
# ═════════════════════════════════════════════════════════════════════════════
class TestDemandeDAgir:

    @pytest.mark.parametrize("phrase,commande", [
        (INCIDENT, "/parcelle ajouter <nom>"),
        ("crée la planche Nord de 8 mètres", "/parcelle ajouter <nom>"),
        ("je veux créer une planche", "/parcelle ajouter <nom>"),
        ("Peux-tu créer la planche Est ?", "/parcelle ajouter <nom>"),
        ("supprime la planche", "/parcelle supprimer <nom>"),
        ("renomme la planche sud", "/parcelle renommer <ancien nom> <nouveau nom>"),
        ("S'il te plaît, mets la serre en pépinière", "/parcelle modifier <nom> <caractéristique>=<valeur>"),
        ("montre-moi le plan", "/menu"),
    ])
    def test_inc018_un_verbe_d_action_en_tete_demande_d_agir(self, phrase, commande):
        assert interp.demande_d_agir(interp.normaliser(phrase)[0]) == commande

    @pytest.mark.parametrize("phrase", [
        "devrais-je créer une planche ?",
        "mets-tu de l'engrais sur les tomates ?",
        "la planche nord a 5 rangs",
        "combien de rangs a la planche nord ?",
        "quand semer les carottes",
        "",
    ])
    def test_inc018_une_question_ou_une_declaration_n_est_pas_une_demande(self, phrase):
        assert interp.demande_d_agir(interp.normaliser(phrase)[0]) is None


# ═════════════════════════════════════════════════════════════════════════════
# L'interpréteur : l'échec d'une demande d'agir est dit, pas routé
# ═════════════════════════════════════════════════════════════════════════════
class TestInterpreteur:

    def test_inc018_l_incident_n_est_pas_une_regle(self):
        """La phrase de l'incident passe par l'agent : aucune règle de commande ne la prend."""
        assert interp.reconnaitre_par_regles(INCIDENT) is None

    @pytest.mark.parametrize("panne", [
        passerelle.QuotaLLMDepasseError("429"),
        passerelle.FournisseurLLMIndisponibleError("panne"),
    ])
    def test_inc018_agent_en_panne_la_demande_n_est_pas_routee(
        self, monkeypatch, modele, parcelles_connues, ancien_repli_muet, panne
    ):
        _mode(monkeypatch, "actif")
        modele.side_effect = panne
        resultat = interp.interpreter(INCIDENT, CTX)
        assert isinstance(resultat, interp.Aiguillage) and resultat.vers == interp.VERS_NON_COMPRIS
        assert resultat.message == "/parcelle ajouter <nom>"
        ancien_repli_muet.assert_called_once()  # l'ancien repli est tenté avant de renoncer

    def test_inc018_appel_rejete_par_le_serveur(self, monkeypatch, modele, parcelles_connues, ancien_repli_muet):
        _mode(monkeypatch, "actif")
        modele.return_value = _reponse(statut=passerelle.STATUT_APPEL_INVALIDE)
        resultat = interp.interpreter(INCIDENT, CTX)
        assert resultat.vers == interp.VERS_NON_COMPRIS

    def test_inc018_proposition_refusee_par_le_validateur(
        self, monkeypatch, modele, parcelles_connues, ancien_repli_muet
    ):
        """L'agent répond mais le validateur rejette (outil inconnu) : même message, pas de routeur."""
        _mode(monkeypatch, "actif")
        modele.return_value = _reponse(AppelOutil("exporter_excel", {}))
        # Sans nombre : la phrase de l'incident en porte, qui ouvrirait un tour de complément.
        resultat = interp.interpreter("Créez la planche Nord et mets la serre en pépinière froide.", CTX)
        assert isinstance(resultat, interp.Aiguillage) and resultat.vers == interp.VERS_NON_COMPRIS
        ancien_repli_muet.assert_not_called()

    def test_inc018_ancien_repli_sous_le_seuil(self, monkeypatch, modele, parcelles_connues):
        _mode(monkeypatch, "actif")
        modele.side_effect = passerelle.FournisseurLLMIndisponibleError("panne")
        faible = interp._construire_commande(
            interp.FORMES_PAR_CLE[("parcelle", "ajouter")], {"nom": "Nord"}, interp.ORIGINE_MODELE, 0.2, "x")
        with patch.object(interp, "_appeler_modele", return_value=faible):
            resultat = interp.interpreter(INCIDENT, CTX)
        assert resultat.vers == interp.VERS_NON_COMPRIS

    def test_inc018_l_ancien_repli_qui_propose_garde_la_main(self, monkeypatch, modele, parcelles_connues):
        _mode(monkeypatch, "actif")
        modele.side_effect = passerelle.FournisseurLLMIndisponibleError("panne")
        sure = interp._construire_commande(
            interp.FORMES_PAR_CLE[("parcelle", "ajouter")], {"nom": "Nord"}, interp.ORIGINE_MODELE, 0.95, "x")
        with patch.object(interp, "_appeler_modele", return_value=sure):
            resultat = interp.interpreter(INCIDENT, CTX)
        assert resultat.origine == interp.ORIGINE_MODELE

    def test_inc018_une_declaration_garde_son_chemin_habituel(
        self, monkeypatch, modele, parcelles_connues, ancien_repli_muet
    ):
        _mode(monkeypatch, "actif")
        modele.side_effect = passerelle.FournisseurLLMIndisponibleError("panne")
        assert interp.interpreter("la planche nord a maintenant 6 rangs", CTX) is None

    @pytest.mark.parametrize("mode", ["off", "ombre"])
    def test_inc018_hors_mode_actif_rien_ne_change(
        self, monkeypatch, modele, parcelles_connues, ancien_repli_muet, mode
    ):
        _mode(monkeypatch, mode)
        modele.side_effect = passerelle.FournisseurLLMIndisponibleError("panne")
        with patch.object(interpreteur_agent, "lancer_en_arriere_plan"):
            assert interp.interpreter(INCIDENT, CTX) is None

    def test_inc018_les_regles_restent_un_raccourci(self, monkeypatch, modele):
        """Une phrase qu'une règle reconnaît ne passe pas par l'agent, donc ne peut pas échouer avec lui."""
        _mode(monkeypatch, "actif")
        resultat = interp.interpreter("supprime la parcelle nord", CTX)
        assert resultat.commande_equivalente() == "/parcelle supprimer nord"
        modele.assert_not_called()

    def test_inc018_un_echec_n_entre_pas_dans_le_contexte_court(self):
        aiguillage = interp.Aiguillage(vers=interp.VERS_NON_COMPRIS, message="/menu", texte_origine="x")
        assert contexte_court.resume_de(aiguillage) is None


# ═════════════════════════════════════════════════════════════════════════════
# Le bot : le message, et jamais le routeur
# ═════════════════════════════════════════════════════════════════════════════
def _update(texte: str):
    update = MagicMock()
    update.effective_user.id = 4242
    update.message = AsyncMock()
    update.message.text = texte
    update.message.reply_text = AsyncMock()
    update.effective_message = update.message
    update.callback_query = None
    return update


class TestBot:

    @pytest.mark.asyncio
    async def test_inc018_le_jardinier_lit_un_message_explicite_pas_une_reponse_du_routeur(
        self, monkeypatch, modele, parcelles_connues, ancien_repli_muet
    ):
        _mode(monkeypatch, "actif")
        modele.return_value = _reponse(statut=passerelle.STATUT_APPEL_INVALIDE)
        update = _update(INCIDENT)
        tg_ctx = MagicMock()
        tg_ctx.user_data = {}
        with (
            patch.object(bot_messages, "_verifier_liaison_ou_onboarding", new=AsyncMock(return_value=True)),
            patch.object(bot_messages, "current_context", return_value=CTX),
            patch.object(bot_interpretation, "current_context", return_value=CTX),
            patch.object(bot_messages, "contexte_court_de", return_value=None),
            patch.object(bot_messages.routeur, "classer_demande") as classer,
            patch.object(bot_messages, "_ask_question", new=AsyncMock()) as ask,
            patch.object(bot_messages, "_parse_and_save", new=AsyncMock()) as parse,
        ):
            classer.return_value = routeur.DecisionRoutage(
                routeur.NATURE_QUESTION_DATA, routeur.ORIGINE_REGLE, 1.0)
            await bot_messages.handle_text(update, tg_ctx)
        classer.assert_not_called()
        ask.assert_not_called()
        parse.assert_not_called()
        texte = update.message.reply_text.await_args.args[0]
        assert "Je n'ai pas réussi à traiter cette demande" in texte
        assert "Rien n'a été fait" in texte
        assert "`/parcelle ajouter <nom>`" in texte

    def test_inc018_le_message_ne_promet_rien_et_nomme_la_commande(self):
        texte = bot_interpretation.texte_aiguillage(
            interp.Aiguillage(vers=interp.VERS_NON_COMPRIS, message="/parcelle supprimer <nom>"))
        assert texte.startswith("🙏") and "`/parcelle supprimer <nom>`" in texte

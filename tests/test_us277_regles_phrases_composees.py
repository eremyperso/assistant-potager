"""
tests/test_us277_regles_phrases_composees.py — Les règles ne lisent que les phrases simples [US-277]
===================================================================================================
Une règle reconnaît UNE commande et en prend les arguments par position. Sur une phrase
composée ou négative, elle déformait : « renomme la planche sud en planche des courges et
supprime la planche nord » renommait en « planche des courges et supprime la planche nord ».
Ces phrases vont à l'agent ; sans agent, le jardinier lit qu'elles n'ont pas été traitées.

Aucun appel réseau : la passerelle est simulée, le bot est piloté par des mocks.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app import config
from app.bot import interpretation as bot_interpretation
from app.bot import messages as bot_messages
from app.services import interpreteur_commandes as interp
from app.services.agent import interpreteur_agent
from app.services.context import TenantContext
from llm import passerelle
from llm.passerelle import AppelOutil, ReponseOutils

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
PARCELLES = ("Serre extérieure", "Planche Nord", "Planche Sud", "Planche sans nom", "Tunnel")
RENOMME_ET_SUPPRIME = "renomme la planche sud en planche des courges et supprime la planche nord"
PLUS_PAILLEE = "la planche sud n'est plus paillée"


def _reponse(*appels: AppelOutil, statut: str = passerelle.STATUT_OK) -> ReponseOutils:
    return ReponseOutils(texte="", modele="test", appel_type=passerelle.TYPE_AGENT,
                         latence_ms=400, appels=appels, statut=statut)


def _texte(texte: str) -> ReponseOutils:
    """[US-257] Le tour où le modèle répond en texte, sans outil : il clôt la boucle."""
    return ReponseOutils(texte=texte, modele="test", appel_type=passerelle.TYPE_AGENT, latence_ms=400)


def _pour_l_agent(phrase: str, ctx=None) -> bool:
    """La détection telle qu'`interpreter` l'appelle : avec la lecture des règles."""
    return interp.phrase_pour_l_agent(phrase, ctx, interp.reconnaitre_par_regles(phrase))


@pytest.fixture
def parcelles_connues(monkeypatch):
    monkeypatch.setattr(interpreteur_agent, "noms_parcelles_du_potager", lambda ctx: PARCELLES)
    monkeypatch.setattr(interpreteur_agent, "voisin_en_base", lambda ctx: (lambda nom: None))


@pytest.fixture
def modele():
    with patch.object(passerelle, "appeler_chat_outils") as faux:
        yield faux


@pytest.fixture
def ancien_repli():
    with patch.object(interp, "_appeler_modele", return_value=None) as faux:
        yield faux


def _mode(monkeypatch, valeur: str) -> None:
    monkeypatch.setattr(config, "AGENT_MODE", valeur)


# ═════════════════════════════════════════════════════════════════════════════
# La détection
# ═════════════════════════════════════════════════════════════════════════════
class TestDetection:

    @pytest.mark.parametrize("phrase", [
        RENOMME_ET_SUPPRIME,
        "supprime la planche nord et renomme la planche sud en planche des courges",
        "crée la parcelle Verger de 20 m² et mets-la à l'ombre",
        "passe la planche nord en plein soleil, puis montre-moi le plan",
    ])
    def test_us277_ca1_une_seconde_demande_va_a_l_agent(self, phrase):
        assert interp.reconnaitre_par_regles(phrase) is not None
        assert _pour_l_agent(phrase)

    def test_us277_ca1_une_seconde_parcelle_sans_verbe_va_a_l_agent(self):
        """« … et la planche centrale en pépinière chaude » : la seconde action ne répète pas le verbe."""
        assert _pour_l_agent("mets la serre en pépinière froide et la planche centrale en pépinière chaude")

    @pytest.mark.parametrize("phrase", [PLUS_PAILLEE, "le potager du fond n'est plus paillé"])
    def test_us277_ca2_une_negation_mal_lue_va_a_l_agent(self, phrase):
        lecture = interp.reconnaitre_par_regles(phrase)
        assert lecture.valeurs["modification"] == "paillage=oui"   # la négation a été perdue
        assert _pour_l_agent(phrase)

    @pytest.mark.parametrize("phrase,modification", [
        ("la parcelle 2 n'est pas paillée", "paillage=non"),
        ("la parcelle 2 est sans abri", "abri=aucun"),
    ])
    def test_us277_ca2_une_negation_bien_lue_reste_aux_regles(self, phrase, modification):
        assert interp.reconnaitre_par_regles(phrase).valeurs["modification"] == modification
        assert not _pour_l_agent(phrase)

    def test_us277_ca2_une_commande_qui_porte_la_negation_reste_aux_regles(self):
        """« sans culture » est le sens même de `/bioagresseur orphelins`."""
        assert not _pour_l_agent("je veux voir les bioagresseurs sans culture")

    @pytest.mark.parametrize("phrase", ["et la planche sud n'est plus paillée", "et le tunnel aussi",
                                        "puis la serre"])
    def test_us277_ca3_une_liaison_en_tete_va_a_l_agent(self, phrase):
        assert interp.phrase_pour_l_agent(phrase)

    def test_us277_ca3_puis_je_est_une_question_pas_une_liaison(self):
        assert not _pour_l_agent("puis-je semer la mâche dans dix jours ?")

    @pytest.mark.parametrize("phrase", [
        "renomme la planche sud en planche des courges",
        "supprime la parcelle nord",
        "mets la serre en pépinière froide",
        "crée la parcelle Est",
    ])
    def test_us277_ca4_une_phrase_simple_reste_aux_regles(self, phrase):
        assert interp.reconnaitre_par_regles(phrase) is not None
        assert not _pour_l_agent(phrase)

    def test_us277_ca5_un_nom_de_parcelle_ne_fait_pas_basculer_la_phrase(self, parcelles_connues):
        phrase = "renomme la planche sans nom en planche Est"
        assert _pour_l_agent(phrase)              # sans potager : « sans » passe pour un retrait
        assert not _pour_l_agent(phrase, CTX)     # « Planche sans nom » est une parcelle du potager


# ═════════════════════════════════════════════════════════════════════════════
# L'interpréteur
# ═════════════════════════════════════════════════════════════════════════════
class TestInterpreteur:

    def test_us277_ca1_l_agent_recoit_la_phrase_composee(self, monkeypatch, modele, parcelles_connues):
        _mode(monkeypatch, "actif")
        # [US-257] Le modèle propose, lit le verdict, puis répond en texte : deux appels.
        modele.side_effect = [
            _reponse(AppelOutil("renommer_parcelle", {"ancien": "Planche Sud", "nouveau": "planche des courges"})),
            _texte("Je te propose de renommer la Planche Sud."),
        ]
        resultat = interp.interpreter(RENOMME_ET_SUPPRIME, CTX)
        assert modele.call_count == 2
        assert resultat.proposition.valeurs.get("nouveau") != "planche des courges et supprime la planche nord"

    def test_us277_ca2_la_negation_va_a_l_agent_sans_passer_par_le_filtre_des_gestes(
        self, monkeypatch, modele, parcelles_connues
    ):
        """« paillée » est un mot de geste : la phrase n'est pas pour autant un geste, les règles y ont vu une commande."""
        _mode(monkeypatch, "actif")
        modele.side_effect = [
            _reponse(AppelOutil("modifier_parcelle", {"parcelle": "Planche Sud", "paillage": False})),
            _texte("Je te propose de retirer le paillage de la Planche Sud."),
        ]
        resultat = interp.interpreter(PLUS_PAILLEE, CTX)
        assert modele.call_count == 2
        assert isinstance(resultat.proposition, interp.CommandeInterpretee)
        assert "oui" not in resultat.proposition.valeurs.get("modification", "")

    def test_us277_ca4_une_phrase_simple_n_appelle_aucun_modele(self, monkeypatch, modele, parcelles_connues):
        _mode(monkeypatch, "actif")
        resultat = interp.interpreter("renomme la planche sud en planche des courges", CTX)
        modele.assert_not_called()
        assert resultat.valeurs == {"ancien": "planche sud", "nouveau": "planche des courges"}

    def test_us277_ca6_agent_indisponible_le_jardinier_lit_que_rien_n_est_fait(
        self, monkeypatch, modele, parcelles_connues, ancien_repli
    ):
        _mode(monkeypatch, "actif")
        modele.return_value = _reponse(statut=passerelle.STATUT_APPEL_INVALIDE)
        resultat = interp.interpreter(RENOMME_ET_SUPPRIME, CTX)
        assert isinstance(resultat, interp.Aiguillage) and resultat.vers == interp.VERS_NON_COMPRIS
        assert resultat.message == "/parcelle renommer <ancien> <nouveau>"
        ancien_repli.assert_not_called()   # il ne rendrait qu'UNE commande

    def test_us277_ca6_agent_desactive_rien_n_est_lu_de_travers(self, monkeypatch, modele, ancien_repli):
        _mode(monkeypatch, "off")
        resultat = interp.interpreter(PLUS_PAILLEE, CTX)
        assert isinstance(resultat, interp.Aiguillage) and resultat.vers == interp.VERS_NON_COMPRIS
        assert resultat.message == "/parcelle modifier <nom> <modification>"
        modele.assert_not_called()
        ancien_repli.assert_not_called()

    def test_us277_ca6_sans_modele_autorise_rien_n_est_lu_de_travers(self):
        resultat = interp.interpreter(RENOMME_ET_SUPPRIME, CTX, autoriser_modele=False)
        assert isinstance(resultat, interp.Aiguillage) and resultat.vers == interp.VERS_NON_COMPRIS

    def test_us277_ca6_une_ambiguite_ecartee_nomme_chaque_commande(self):
        candidats = (
            interp.reconnaitre_par_regles("renomme la planche sud en planche des courges"),
            interp.reconnaitre_par_regles("supprime la parcelle nord"),
        )
        syntaxe = interp._syntaxe(interp.Ambiguite(candidats=candidats))
        assert syntaxe == "/parcelle renommer <ancien> <nouveau> puis /parcelle supprimer <nom>"


# ═════════════════════════════════════════════════════════════════════════════
# Le bot
# ═════════════════════════════════════════════════════════════════════════════
def _update(texte: str):
    update = MagicMock()
    update.effective_user.id = 4277
    update.message = AsyncMock()
    update.message.text = texte
    update.message.reply_text = AsyncMock()
    update.effective_message = update.message
    update.callback_query = None
    return update


class TestBot:

    @pytest.mark.asyncio
    async def test_us277_le_raccourci_supprimer_n_annule_pas_la_derniere_saisie(
        self, monkeypatch, modele, ancien_repli
    ):
        """« supprime … et renomme … » commence par « supprime » : le raccourci « annuler ma
        dernière saisie » ne doit pas la prendre, même si la lecture des règles est écartée."""
        _mode(monkeypatch, "off")
        update = _update("supprime la planche nord et renomme la planche sud en planche des courges")
        tg_ctx = MagicMock()
        tg_ctx.user_data = {}
        with (
            patch.object(bot_messages, "_verifier_liaison_ou_onboarding", new=AsyncMock(return_value=True)),
            patch.object(bot_messages, "current_context", return_value=CTX),
            patch.object(bot_interpretation, "current_context", return_value=CTX),
            patch.object(bot_messages, "contexte_court_de", return_value=None),
            patch.object(bot_messages, "_corr_annuler_dernier", new=AsyncMock()) as annuler,
            patch.object(bot_messages, "_parse_and_save", new=AsyncMock()) as parse,
        ):
            await bot_messages.handle_text(update, tg_ctx)
        annuler.assert_not_awaited()
        parse.assert_not_awaited()
        texte = update.message.reply_text.await_args.args[0]
        assert "Rien n'a été fait" in texte
        assert "`/parcelle renommer <ancien> <nouveau>`" in texte

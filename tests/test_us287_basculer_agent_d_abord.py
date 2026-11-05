"""[US-287] Basculer le bot en agent d'abord sur Mistral Small 4.

CA3 — en mode `prioritaire`, aucun raccourci à mots-clés de `app/bot/messages.py` ne prend
une phrase libre avant l'agent ; chacun a son outil (« déplacer » reçoit `/deplacer`).
Les gardes de dialogue en cours et les textes exacts des boutons ne changent pas.
CA4 — sur quota ou panne de l'agent, les règles et les raccourcis d'aujourd'hui reprennent
la main, et le jardinier lit une réponse.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app import config
from app.bot import deplacement as bot_deplacement
from app.bot import interpretation as bot_interpretation
from app.bot import messages as bot_messages
from app.services import interpreteur_commandes as interp
from app.services import menu_commandes
from app.services.agent import catalogue_outils, interpreteur_agent, savoir
from app.services.agent.interpreteur_agent import ResultatAgent
from app.services.context import TenantContext
from llm import passerelle
from utils.deplacer import is_deplacer_request

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
PARCELLES = ("Planche Nord", "Planche Sud", "Tunnel")
RACINE = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def lectures_simulees(monkeypatch):
    monkeypatch.setattr(interpreteur_agent, "noms_parcelles_du_potager", lambda ctx: PARCELLES)
    monkeypatch.setattr(interpreteur_agent, "voisin_en_base", lambda ctx: (lambda nom: None))
    monkeypatch.setattr(interpreteur_agent, "persister_reponse", lambda *a, **k: None)
    monkeypatch.setattr(savoir, "precharger", lambda ctx, releves: "")


@pytest.fixture
def prioritaire(monkeypatch):
    monkeypatch.setattr(config, "AGENT_MODE", "prioritaire")


def _update(texte: str):
    update = MagicMock()
    update.effective_user.id = 28700
    update.message = AsyncMock()
    update.message.text = texte
    update.message.reply_text = AsyncMock()
    update.effective_message = update.message
    update.callback_query = None
    return update


class _Raccourcis:
    """Les cibles des raccourcis de `handle_text`, et ce qui suit l'interpréteur, simulés."""

    def __init__(self):
        self.annuler = AsyncMock()
        self.corriger = AsyncMock()
        self.godets = AsyncMock()
        self.deplacer = AsyncMock()
        self.note = AsyncMock()
        self.note_details = AsyncMock()
        self.ask = AsyncMock()
        self.parse = AsyncMock()

    def tous(self) -> list[AsyncMock]:
        return [self.annuler, self.corriger, self.godets, self.deplacer, self.note]


async def _envoyer(texte: str, user_data: dict | None = None,
                   traiter=None, pour_l_agent: bool = False) -> _Raccourcis:
    """`handle_text` sur `texte`, raccourcis et suite simulés ; `traiter` remplace
    `_traiter_commande_interpretee` (par défaut : rien n'est pris en charge)."""
    r = _Raccourcis()
    tg_ctx = MagicMock()
    tg_ctx.user_data = dict(user_data or {})
    traiter = traiter or AsyncMock(return_value=False)
    with (
        patch.object(bot_messages, "_verifier_liaison_ou_onboarding", new=AsyncMock(return_value=True)),
        patch.object(bot_messages, "current_context", return_value=CTX),
        patch.object(bot_interpretation, "current_context", return_value=CTX),
        patch.object(bot_messages, "contexte_court_de", return_value=None),
        patch.object(bot_messages, "reprendre_reponse", side_effect=lambda u, t: t),
        patch.object(bot_messages.svc_corrections, "pour_l_agent_plutot_que_le_raccourci",
                     return_value=pour_l_agent),
        patch.object(bot_messages, "_corr_annuler_dernier", new=r.annuler),
        patch.object(bot_messages, "_corr_start", new=r.corriger),
        patch.object(bot_messages, "_consulter_godets", new=r.godets),
        patch.object(bot_messages, "_depl_start", new=r.deplacer),
        patch.object(bot_messages, "_note_start", new=r.note),
        patch.object(bot_messages, "_note_details_received", new=r.note_details),
        patch.object(bot_messages, "_traiter_commande_interpretee", new=traiter),
        patch.object(bot_messages.routeur, "classer_demande") as classer,
        patch.object(bot_messages, "_ask_question", new=r.ask),
        patch.object(bot_messages, "_parse_and_save", new=r.parse),
    ):
        classer.return_value = MagicMock(nature=bot_messages.routeur.NATURE_ACTION)
        await bot_messages.handle_text(_update(texte), tg_ctx)
    return r


REPONSE = ResultatAgent(disponible=True, texte="Je m'en occupe.")

#: Une phrase par raccourci placé avant l'interpréteur, et le raccourci qui la prenait.
PHRASES_RACCOURCIS = [
    ("effacer mon carnet", "annuler"),
    ("annuler mon dernier arrosage", "annuler"),
    ("modifier ma dernière récolte", "corriger"),
    ("montre-moi mes godets", "godets"),
    ("déplacer mes tomates sur la planche nord", "deplacer"),
    ("je veux noter que les fèves ont des pucerons", "note"),
]


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — l'agent avant les raccourcis
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3AgentAvantLesRaccourcis:

    @pytest.mark.asyncio
    @pytest.mark.parametrize("texte,raccourci", PHRASES_RACCOURCIS)
    async def test_us287_ca3_en_prioritaire_la_phrase_libre_va_a_l_agent(self, prioritaire, texte, raccourci):
        with patch.object(interpreteur_agent, "proposer", return_value=REPONSE) as agent:
            r = await _envoyer(texte)
        agent.assert_called_once()
        assert agent.call_args.kwargs.get("prioritaire") is True
        for cible in r.tous():
            cible.assert_not_awaited()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("texte,raccourci", PHRASES_RACCOURCIS)
    async def test_us287_ca3_le_mode_actif_garde_ses_raccourcis(self, monkeypatch, texte, raccourci):
        monkeypatch.setattr(config, "AGENT_MODE", "actif")
        with patch.object(interpreteur_agent, "proposer", return_value=REPONSE) as agent:
            r = await _envoyer(texte)
        agent.assert_not_called()
        getattr(r, raccourci).assert_awaited_once()

    @pytest.mark.asyncio
    async def test_us287_gherkin_effacer_mon_carnet_va_a_l_agent(self, prioritaire):
        """Given prioritaire, When « effacer mon carnet », Then l'agent, pas « annuler la dernière saisie »."""
        traiter = AsyncMock(return_value=True)
        with patch.object(interpreteur_agent, "proposer", return_value=REPONSE):
            r = await _envoyer("effacer mon carnet", traiter=traiter)
        r.annuler.assert_not_awaited()
        resultat = traiter.await_args.args[2]
        assert isinstance(resultat, interp.ReponseAgent) and resultat.texte == "Je m'en occupe."

    @pytest.mark.asyncio
    async def test_us287_ca3_une_phrase_que_l_agent_laisse_ne_repart_pas_aux_mots_cles(self, prioritaire):
        """L'agent n'a rien proposé : la phrase suit la cascade habituelle, sans raccourci."""
        with patch.object(interpreteur_agent, "proposer", return_value=ResultatAgent(disponible=True)):
            r = await _envoyer("montre-moi mes godets")
        r.godets.assert_not_awaited()
        r.parse.assert_awaited_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bouton,raccourci", [("🗑 supprimer", "annuler"), ("✏️ corriger", "corriger"),
                                                  ("annuler", "annuler")])
    async def test_us287_ca3_le_texte_exact_d_un_bouton_reste_servi(self, prioritaire, bouton, raccourci):
        with patch.object(interpreteur_agent, "proposer") as agent:
            r = await _envoyer(bouton)
        agent.assert_not_called()
        getattr(r, raccourci).assert_awaited_once()

    @pytest.mark.asyncio
    async def test_us287_ca3_un_dialogue_en_cours_reste_avant_l_agent(self, prioritaire):
        with patch.object(interpreteur_agent, "proposer") as agent:
            r = await _envoyer("des pucerons sur les fèves", user_data={"mode": "note_details"})
        agent.assert_not_called()
        r.note_details.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_us287_ca3_le_profil_reste_avant_l_agent(self, prioritaire):
        with patch.object(interpreteur_agent, "proposer") as agent, \
             patch.object(bot_messages, "phrase_de_profil", new=AsyncMock(return_value=True)) as profil:
            await _envoyer("appelle-moi Rico")
        profil.assert_awaited_once()
        agent.assert_not_called()

    @pytest.mark.asyncio
    async def test_us287_ca3_le_carnet_en_modification_reste_avant_l_agent(self, prioritaire):
        with patch.object(interpreteur_agent, "proposer") as agent, \
             patch.object(bot_messages, "phrase_de_profil", new=AsyncMock(return_value=False)), \
             patch.object(bot_messages, "phrase_de_carnet", new=AsyncMock(return_value=True)) as carnet:
            await _envoyer("je préfère arroser le matin")
        carnet.assert_awaited_once()
        agent.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — « déplacer une culture » reçoit un outil
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3OutilDeplacer:

    def test_us287_ca3_afficher_propose_le_deplacement(self):
        outil = catalogue_outils.outils_par_nom()[catalogue_outils.OUTIL_CONSULTER]
        proprietes = outil.schema["function"]["parameters"]["properties"]
        assert "deplacer" in proprietes["commande"]["enum"]
        assert "culture" in proprietes  # le champ partagé avec /fiche et /vendre, pas un doublon

    def test_us287_ca3_la_forme_ouvre_un_parcours_sans_rien_ecrire(self):
        forme = interp.FORMES_PAR_CLE[("deplacer", None)]
        assert not forme.confirmation and not forme.destructrice
        assert "deplacer" in menu_commandes.ORDRE_METIER and "deplacer" in menu_commandes.DESCRIPTIONS

    @pytest.mark.parametrize("phrase,culture", [
        ("déplace mes tomates sur la planche nord", "tomates"),
        ("je veux déplacer mes carottes", "carottes"),
        ("changement de parcelle pour les poireaux", "poireaux"),
    ])
    def test_us287_ca3_la_regle_reconnait_le_deplacement(self, phrase, culture):
        resultat = interp.reconnaitre_par_regles(phrase)
        assert resultat.commande == "deplacer"
        assert resultat.valeurs.get("culture") == culture

    @pytest.mark.parametrize("phrase", [
        "déplacer le lot 5 au châssis froid",
        "déplace les godets de tomate sous le châssis",
        "déplacer les poireaux de la serre à la pépinière",
    ])
    def test_us287_ca3_un_lot_de_pepiniere_reste_un_geste(self, phrase):
        resultat = interp.reconnaitre_par_regles(phrase)
        assert resultat is None or resultat.commande != "deplacer"

    @pytest.mark.parametrize("phrase", ["associer tomate et basilic", "ajoute une nouvelle parcelle Est"])
    def test_us287_ca3_le_raccourci_etait_trop_large_pour_passer_avant_l_agent(self, phrase):
        """Pourquoi le raccourci ne pouvait pas rester gardé en mode `prioritaire`."""
        assert is_deplacer_request(phrase)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("args,culture", [(["tomates"], "tomates"), ([], None),
                                              (["pommes", "de", "terre"], "pommes de terre")])
    async def test_us287_ca3_la_commande_ouvre_le_parcours_guide(self, args, culture):
        tg_ctx = MagicMock()
        tg_ctx.args = args
        with patch.object(bot_deplacement, "_depl_start", new=AsyncMock()) as depart:
            await bot_deplacement.cmd_deplacer(_update("/deplacer"), tg_ctx)
        depart.assert_awaited_once()
        assert depart.await_args.args[2] == culture

    def test_us287_ca3_la_commande_est_enregistree(self):
        source = (RACINE / "app" / "bot" / "application.py").read_text(encoding="utf-8")
        assert '_enregistrer_commande(app, "deplacer",   cmd_deplacer)' in source


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — mode dégradé
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def modele():
    with patch.object(passerelle, "appeler_chat_outils") as faux:
        yield faux


@pytest.fixture
def ancien_repli_muet():
    with patch.object(interp, "_appeler_modele", return_value=None) as faux:
        yield faux


class TestCA4ModeDegrade:

    @pytest.mark.parametrize("panne", [
        passerelle.QuotaLLMDepasseError("429"),
        passerelle.FournisseurLLMIndisponibleError("panne"),
    ])
    def test_us287_gherkin_mistral_429_les_regles_proposent(self, prioritaire, modele, ancien_repli_muet, panne):
        """Given Mistral répond 429, When « crée la parcelle Est », Then « /parcelle ajouter Est »."""
        modele.side_effect = panne
        resultat = interp.interpreter("crée la parcelle Est", CTX)
        assert isinstance(resultat, interp.CommandeInterpretee)
        assert resultat.commande_equivalente() == "/parcelle ajouter Est"
        modele.assert_called_once()

    def test_us287_ca4_agent_d_abord_rend_la_cascade_quand_l_agent_tombe(self, prioritaire, modele):
        modele.side_effect = passerelle.QuotaLLMDepasseError("429")
        assert interp.agent_d_abord("crée la parcelle Est", CTX) is interp.CASCADE_HABITUELLE

    def test_us287_ca4_hors_prioritaire_l_agent_n_est_pas_consulte(self, monkeypatch, modele):
        monkeypatch.setattr(config, "AGENT_MODE", "actif")
        assert interp.agent_d_abord("crée la parcelle Est", CTX) is interp.CASCADE_HABITUELLE
        modele.assert_not_called()

    @pytest.mark.asyncio
    async def test_us287_ca4_les_raccourcis_reprennent_la_main(self, prioritaire, modele):
        modele.side_effect = passerelle.QuotaLLMDepasseError("429")
        r = await _envoyer("effacer mon carnet")
        r.annuler.assert_awaited_once()
        modele.assert_called_once()

    @pytest.mark.asyncio
    async def test_us287_ca4_le_jardinier_lit_la_proposition_des_regles(self, prioritaire, modele,
                                                                        ancien_repli_muet):
        """Le bot ne rappelle pas l'agent (un seul 429), et la commande des règles est montrée."""
        modele.side_effect = passerelle.QuotaLLMDepasseError("429")
        traiter = AsyncMock(return_value=True)
        r = await _envoyer("crée la parcelle Est", traiter=traiter)
        modele.assert_called_once()
        resultat = traiter.await_args.args[2]
        assert resultat.commande_equivalente() == "/parcelle ajouter Est"
        r.parse.assert_not_awaited()

    def test_us287_ca4_interpreter_sans_agent_d_abord_ne_le_rappelle_pas(self, prioritaire, modele,
                                                                        ancien_repli_muet):
        resultat = interp.interpreter("crée la parcelle Est", CTX, consulter_agent_d_abord=False)
        modele.assert_not_called()
        assert resultat.commande_equivalente() == "/parcelle ajouter Est"


# ═════════════════════════════════════════════════════════════════════════════
# CA2 / CA6 — réglages documentés
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2Reglages:

    def test_us287_ca2_env_example_donne_la_cible(self):
        exemple = (RACINE / ".env.example").read_text(encoding="utf-8")
        assert "GROQ_MODEL_AGENT=mistral/mistral-small-2603" in exemple
        assert "GROQ_MODEL_COMPAGNON_SIGNAL=mistral/mistral-small-2603" in exemple
        assert "AGENT_MODE=prioritaire" in exemple

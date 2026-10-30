"""
tests/test_us260_confirmer_par_phrase.py — Confirmer, corriger ou abandonner une proposition par une phrase [US-260]
====================================================================================================================
« Vas-y », « non 4 rangs », « laisse tomber » : le jardinier répond à une proposition sans
chercher le bouton. La confirmation par phrase passe UNIQUEMENT par l'outil
`confirmer_proposition(id)`, validé contre l'identifiant de la proposition en cours (B3).

Aucun appel réseau : la passerelle est simulée (`modele`), le bot est piloté par des
`MagicMock` / `AsyncMock`, la base est celle de la fixture `memoire_compagnon`.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app import config
from app.bot import interpretation as bot_interpretation
from app.services import interpreteur_commandes as interp
from app.services.agent import catalogue_outils, contexte_court, executeurs, interpreteur_agent
from app.services.agent.catalogue_outils import (
    OUTIL_ABANDONNER, OUTIL_CONFIRMER, OUTIL_MODIFIER_PARCELLE, OUTILS_DECISION,
)
from app.services.compagnon import decisions
from app.services.compagnon import propositions as svc_propositions
from app.services.context import TenantContext
from llm import passerelle
from llm.passerelle import AppelOutil, ReponseOutils

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
AUTRE_POTAGER = TenantContext(user_id=1, potager_id=2, role="owner")
PARCELLES = ("Planche Nord", "Planche Sud", "Serre")


# ═════════════════════════════════════════════════════════════════════════════
# Outillage
# ═════════════════════════════════════════════════════════════════════════════
def _reponse(*appels: AppelOutil, texte: str = "") -> ReponseOutils:
    return ReponseOutils(
        texte=texte, modele="test", appel_type=passerelle.TYPE_AGENT,
        tokens_in=900, tokens_out=50, latence_ms=400, appels=appels, statut=passerelle.STATUT_OK,
    )


def _confirmer(code: str) -> AppelOutil:
    return AppelOutil(OUTIL_CONFIRMER, {"id": code})


def _abandonner(code: str) -> AppelOutil:
    return AppelOutil(OUTIL_ABANDONNER, {"id": code})


def _rangs(parcelle: str, valeur: int) -> AppelOutil:
    return AppelOutil(OUTIL_MODIFIER_PARCELLE, {"parcelle": parcelle, "nb_rangs": valeur})


def _commande(texte: str = "passe la planche nord à 2 rangs", nom: str = "Planche Nord",
              modification: str = "rangs=2") -> interp.CommandeInterpretee:
    return interp._construire_commande(
        interp.FORMES_PAR_CLE[("parcelle", "modifier")],
        {"nom": nom, "modification": modification}, interp.ORIGINE_AGENT, 1.0, texte,
    )


def _suppression(nom: str = "Planche Nord") -> interp.CommandeInterpretee:
    return interp._construire_commande(
        interp.FORMES_PAR_CLE[("parcelle", "supprimer")],
        {"nom": nom}, interp.ORIGINE_AGENT, 1.0, f"supprime la parcelle {nom.lower()}",
    )


def _archivage() -> interp.CommandeInterpretee:
    return _commande("mets la planche nord hors service", modification="actif=non")


def _en_attente(commande, ctx: TenantContext = CTX, il_y_a_s: float = 0.0):
    """Une proposition en attente, rangée en base comme le bot la range."""
    return svc_propositions.proposer(
        ctx, commande, log_id=7, maintenant=datetime.utcnow() - timedelta(seconds=il_y_a_s),
    )


def _update(utilisateur: int = 4242):
    update = MagicMock()
    update.effective_user.id = utilisateur
    update.effective_chat.id = utilisateur
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    update.callback_query = None
    return update


def _contexte():
    """Le contexte que le bot construit pour la phrase suivante, lu en base."""
    with patch.object(bot_interpretation, "current_context", return_value=CTX):
        return bot_interpretation.contexte_court_de(_update())


@pytest.fixture
def modele():
    with patch.object(passerelle, "appeler_chat_outils") as faux:
        yield faux


@pytest.fixture
def parcelles_connues(monkeypatch):
    monkeypatch.setattr(interpreteur_agent, "noms_parcelles_du_potager", lambda ctx: PARCELLES)
    monkeypatch.setattr(interpreteur_agent, "voisin_en_base", lambda ctx: (lambda nom: None))


@pytest.fixture
def agent_actif(monkeypatch):
    monkeypatch.setattr(config, "AGENT_MODE", "actif")


def _noms_offerts(modele) -> set[str]:
    return {outil["function"]["name"] for outil in modele.call_args.kwargs["outils"]}


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — deux outils, validés contre l'identifiant de la proposition en attente
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1OutilsValides:

    def test_us260_ca1_les_deux_outils_existent_et_prennent_un_identifiant(self):
        outils = {o.nom: o for o in catalogue_outils.outils_decision()}
        assert set(outils) == {"confirmer_proposition", "abandonner_proposition"} == set(OUTILS_DECISION)
        for outil in outils.values():
            assert outil.decision and not outil.ecrit and not outil.terminal
            parametres = outil.schema["function"]["parameters"]
            assert list(parametres["properties"]) == ["id"] and parametres["required"] == ["id"]

    def test_us260_ca1_le_plafond_d_outils_compte_les_outils_de_decision(self):
        assert len(catalogue_outils.outils()) + len(OUTILS_DECISION) <= catalogue_outils.NB_OUTILS_MAX
        assert catalogue_outils.controler_parite_outils() == []

    def test_us260_ca1_ils_sont_offerts_seulement_quand_une_proposition_attend(self, modele, parcelles_connues):
        modele.return_value = _reponse(texte="Salut !")
        interpreteur_agent.proposer("bonjour", CTX, None)
        assert not _noms_offerts(modele) & set(OUTILS_DECISION)

        _en_attente(_commande())
        interpreteur_agent.proposer("vas-y", CTX, _contexte())
        assert set(OUTILS_DECISION) <= _noms_offerts(modele)

    def test_us260_ca1_le_contexte_donne_l_identifiant_et_la_consigne(self):
        proposition = _en_attente(_commande())
        contexte = _contexte()
        assert contexte.code == proposition.code
        assert contexte.donnees()["proposition_en_attente"]["id"] == proposition.code
        assert "confirmer_proposition" in contexte.prompt() and "abandonner_proposition" in contexte.prompt()
        # Le prompt fixe, mesuré par US-233 / US-235, n'est pas touché.
        assert "confirmer_proposition" not in interpreteur_agent.PROMPT_FIXE

    def test_us260_ca1_un_identifiant_qui_n_est_pas_celui_de_la_proposition_est_refuse(
            self, modele, parcelles_connues):
        proposition = _en_attente(_commande())
        modele.side_effect = [
            _reponse(_confirmer("pAUTRE0000000")),
            _reponse(_confirmer(proposition.code)),
        ]
        resultat = interpreteur_agent.proposer("vas-y", CTX, _contexte())
        # Le verdict du premier appel est lu par le modèle, qui reprend le bon identifiant.
        verdict = modele.call_args_list[1].kwargs["historique"][-1]["content"]
        assert "refusée" in verdict and "identifiant inconnu" in verdict
        assert resultat.decision == decisions.Decision("confirmer", proposition.code)

    def test_us260_ca1_une_decision_acceptee_clot_la_boucle_sans_rien_executer(self, modele, parcelles_connues):
        proposition = _en_attente(_commande())
        modele.return_value = _reponse(_confirmer(proposition.code))
        with patch.object(bot_interpretation, "_interp_executer", new=AsyncMock()) as executer:
            resultat = interpreteur_agent.proposer("vas-y", CTX, _contexte())
        assert resultat.decision == decisions.Decision("confirmer", proposition.code)
        assert resultat.commande is None and resultat.plan is None
        assert modele.call_count == 1
        executer.assert_not_called()
        # La proposition attend toujours : seul le bot la fait sortir de l'attente.
        assert svc_propositions.par_code(proposition.code, CTX.user_id).en_attente

    def test_us260_ca1_un_texte_seul_ne_confirme_rien(self, modele, parcelles_connues):
        _en_attente(_commande())
        modele.return_value = _reponse(texte="Parfait, je lance ça !")
        resultat = interpreteur_agent.proposer("vas-y", CTX, _contexte())
        assert resultat.decision is None

    def test_us260_ca1_abandonner_est_valide_de_la_meme_facon(self, modele, parcelles_connues):
        proposition = _en_attente(_commande())
        modele.return_value = _reponse(_abandonner(proposition.code))
        resultat = interpreteur_agent.proposer("laisse tomber", CTX, _contexte())
        assert resultat.decision == decisions.Decision("abandonner", proposition.code)

    def test_us260_ca1_une_decision_et_une_ecriture_dans_le_meme_message_ne_se_cumulent_pas(
            self, modele, parcelles_connues):
        proposition = _en_attente(_commande())
        modele.return_value = _reponse(_rangs("Planche Nord", 4), _confirmer(proposition.code))
        resultat = interpreteur_agent.proposer("non 4 rangs, vas-y", CTX, _contexte())
        assert resultat.decision is None  # la nouvelle proposition remplace l'ancienne, rien ne se confirme


# ═════════════════════════════════════════════════════════════════════════════
# CA1 (suite) — la confirmation par phrase exécute ce que le bouton exécute
# ═════════════════════════════════════════════════════════════════════════════
class TestExecutionParPhrase:

    @pytest.mark.asyncio
    async def test_us260_confirmer_fait_sortir_de_l_attente_puis_execute_une_fois(self):
        proposition = _en_attente(_commande())
        update, tg_ctx = _update(), MagicMock(user_data={})
        decision = decisions.Decision("confirmer", proposition.code)
        with (
            patch.object(bot_interpretation, "current_context", return_value=CTX),
            patch.object(bot_interpretation, "_contexte_sur", return_value=CTX),
            patch.object(interp, "persister_journal", return_value=8),
            patch.object(bot_interpretation, "_interp_executer", new=AsyncMock()) as executer,
        ):
            await bot_interpretation._interp_decider(update, tg_ctx, decision)
            await bot_interpretation._interp_decider(update, tg_ctx, decision)  # le « oui » répété
        assert executer.await_count == 1
        assert executer.await_args.args[2] == proposition.commande
        assert executer.await_args.kwargs["potager_id"] == CTX.potager_id
        relue = svc_propositions.par_code(proposition.code, CTX.user_id)
        assert relue.etat == svc_propositions.ETAT_CONFIRMEE and relue.traite_canal == "telegram"

    @pytest.mark.asyncio
    async def test_us260_abandonner_ne_fait_rien_et_le_dit(self):
        proposition = _en_attente(_commande())
        update, tg_ctx = _update(), MagicMock(user_data={})
        with (
            patch.object(bot_interpretation, "current_context", return_value=CTX),
            patch.object(interp, "persister_journal", return_value=8),
            patch.object(bot_interpretation, "_interp_executer", new=AsyncMock()) as executer,
        ):
            await bot_interpretation._interp_decider(
                update, tg_ctx, decisions.Decision("abandonner", proposition.code))
        executer.assert_not_called()
        assert update.message.reply_text.call_args.args[0] == decisions.TEXTE_ABANDONNEE
        assert svc_propositions.par_code(proposition.code, CTX.user_id).etat == svc_propositions.ETAT_ABANDONNEE

    @pytest.mark.asyncio
    async def test_us260_un_plan_se_confirme_par_phrase_comme_au_bouton(self):
        plan = interp.Plan((_commande(), _commande(nom="Planche Sud")), texte_origine="deux planches")
        proposition = _en_attente(plan)
        update, tg_ctx = _update(), MagicMock(user_data={})
        resultats = (executeurs.ResultatEtape("reussie", "ok"), executeurs.ResultatEtape("reussie", "ok"))
        with (
            patch.object(bot_interpretation, "current_context", return_value=CTX),
            patch.object(bot_interpretation, "_contexte_sur", return_value=CTX),
            patch.object(interp, "persister_journal", return_value=8),
            patch.object(executeurs, "executer_plan", return_value=resultats) as executer,
        ):
            await bot_interpretation._interp_decider(
                update, tg_ctx, decisions.Decision("confirmer", proposition.code))
        executer.assert_called_once()
        assert executer.call_args.args[0] == plan and executer.call_args.kwargs["proposition_id"] == proposition.id

    @pytest.mark.asyncio
    async def test_us260_la_base_fait_foi_une_proposition_d_un_autre_jardinier_ne_s_execute_pas(self):
        proposition = _en_attente(_commande(), TenantContext(user_id=2, potager_id=1, role="owner"))
        update, tg_ctx = _update(), MagicMock(user_data={})
        with (
            patch.object(bot_interpretation, "current_context", return_value=CTX),
            patch.object(bot_interpretation, "_interp_executer", new=AsyncMock()) as executer,
        ):
            await bot_interpretation._interp_decider(
                update, tg_ctx, decisions.Decision("confirmer", proposition.code))
        executer.assert_not_called()
        assert update.message.reply_text.call_args.args[0] == bot_interpretation._MSG_DEMANDE_EXPIREE


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — « non 4 rangs » : une nouvelle proposition, l'ancienne est remplacée
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2NonQuatreRangs:

    def test_us260_ca2_la_correction_est_une_ecriture_pas_une_confirmation(self, modele, parcelles_connues):
        _en_attente(_commande())
        modele.return_value = _reponse(_rangs("Planche Nord", 4))
        resultat = interpreteur_agent.proposer("non 4 rangs", CTX, _contexte())
        assert resultat.decision is None
        assert resultat.commande.valeurs["modification"] == "rangs=4"

    @pytest.mark.asyncio
    async def test_us260_ca2_gherkin_non_4_rangs_remplace_l_ancienne(self, modele, parcelles_connues):
        ancienne = _en_attente(_commande())
        modele.return_value = _reponse(_rangs("Planche Nord", 4))
        resultat = interpreteur_agent.proposer("non 4 rangs", CTX, _contexte())
        reponse = interp.ReponseAgent(texte="", proposition=resultat.commande, outils=resultat.outils)
        update, tg_ctx = _update(), MagicMock(user_data={})
        with (
            patch.object(bot_interpretation, "current_context", return_value=CTX),
            patch.object(interp, "persister_journal", return_value=8),
            patch.object(bot_interpretation, "_resoudre_noms_parcelle", side_effect=lambda c: c),
            patch.object(bot_interpretation, "_interp_executer", new=AsyncMock()) as executer,
        ):
            await bot_interpretation._traiter_commande_interpretee(update, tg_ctx, reponse)
        nouvelle = svc_propositions.en_attente(CTX.user_id, CTX.potager_id)
        assert nouvelle.code != ancienne.code and nouvelle.commande.valeurs["modification"] == "rangs=4"
        assert svc_propositions.par_code(ancienne.code, CTX.user_id).etat == svc_propositions.ETAT_REMPLACEE
        executer.assert_not_called()  # CA6 : aucun second geste sur une phrase de correction


# ═════════════════════════════════════════════════════════════════════════════
# CA2 (suite) — une décision ne reprend rien : si la phrase donne autre chose, elle CORRIGE
# Trouvé en recette sur le vrai modèle (Mistral Small 4) : « non 4 rangs » appelait
# `abandonner_proposition`, et rien dans le code ne regardait la phrase.
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2UneDecisionNeReprendRien:

    @staticmethod
    def _verdict_du_tour_suivant(modele) -> str:
        return modele.call_args_list[1].kwargs["historique"][-1]["content"]

    def test_us260_ca2_non_4_rangs_appele_en_abandon_est_renvoye_a_l_outil_de_commande(
            self, modele, parcelles_connues):
        proposition = _en_attente(_commande())
        modele.side_effect = [
            _reponse(_abandonner(proposition.code)),
            _reponse(_rangs("Planche Nord", 4)),
            _reponse(texte="Je te propose de passer la Planche Nord à 4 rangs : tu confirmes ?"),
        ]
        resultat = interpreteur_agent.proposer("non 4 rangs", CTX, _contexte())
        verdict = self._verdict_du_tour_suivant(modele)
        assert "refusée" in verdict and "« 4 »" in verdict and "outil de commande" in verdict
        assert resultat.decision is None
        assert resultat.commande.valeurs["modification"] == "rangs=4"
        assert svc_propositions.par_code(proposition.code, CTX.user_id).en_attente  # rien n'a été abandonné

    def test_us260_ca2_oui_4_rangs_peut_devenir_une_correction(self, modele, parcelles_connues):
        proposition = _en_attente(_commande())
        modele.side_effect = [
            _reponse(_confirmer(proposition.code)),
            _reponse(_rangs("Planche Nord", 4)),
            _reponse(texte="Je te propose de passer la Planche Nord à 4 rangs : tu confirmes ?"),
        ]
        resultat = interpreteur_agent.proposer("oui, 4 rangs", CTX, _contexte())
        assert resultat.decision is None
        assert resultat.commande.valeurs["modification"] == "rangs=4"

    def test_us260_ca2_oui_4_rangs_ne_confirme_jamais_l_ancienne_valeur(self, modele, parcelles_connues):
        """Le modèle y tient : le code répond, la proposition (2 rangs) n'est pas lancée sur un mot."""
        proposition = _en_attente(_commande())
        modele.return_value = _reponse(_confirmer(proposition.code))
        resultat = interpreteur_agent.proposer("oui, 4 rangs", CTX, _contexte())
        assert resultat.decision is None and resultat.bouton_seul
        assert "« 4 »" in resultat.texte and "pas d'un mot" in resultat.texte
        assert modele.call_count == 2  # écarté une fois, puis le code répond
        assert svc_propositions.par_code(proposition.code, CTX.user_id).en_attente

    def test_us260_ca2_si_le_modele_y_tient_l_abandon_passe(self, modele, parcelles_connues):
        """L'abandon ne fait rien : écarté une fois, il n'est jamais bloqué."""
        proposition = _en_attente(_commande())
        modele.return_value = _reponse(_abandonner(proposition.code))
        resultat = interpreteur_agent.proposer("laisse tomber, 4 rangs c'est trop", CTX, _contexte())
        assert resultat.decision == decisions.Decision("abandonner", proposition.code)
        assert modele.call_count == 2

    @pytest.mark.parametrize("phrase,dit", [
        ("non, quatre rangs", "« 4 »"),
        ("plutôt la planche sud", "« Planche Sud »"),
        ("non, plein soleil", "« plein soleil »"),
        ("non 4 rangs et plein soleil", "« 4 »"),
    ])
    def test_us260_ca2_un_nombre_en_lettres_une_parcelle_une_valeur_corrigent_aussi(
            self, phrase, dit, modele, parcelles_connues):
        proposition = _en_attente(_commande())
        modele.side_effect = [_reponse(_abandonner(proposition.code))] + [_reponse(texte="D'accord.")] * 3
        interpreteur_agent.proposer(phrase, CTX, _contexte())
        verdict = self._verdict_du_tour_suivant(modele)
        assert "refusée" in verdict and dit in verdict

    @pytest.mark.parametrize("phrase,decision", [
        ("non merci", "abandonner"), ("laisse tomber", "abandonner"), ("annule", "abandonner"),
        ("finalement non", "abandonner"), ("non, laisse tomber la planche nord", "abandonner"),
        ("oui", "confirmer"), ("vas-y", "confirmer"), ("c'est bon", "confirmer"),
        ("oui pour les 2 rangs", "confirmer"), ("oui, la planche nord", "confirmer"),
        ("ok vas-y pour la Planche Nord à 2 rangs", "confirmer"),
    ])
    def test_us260_ca2_une_reponse_qui_ne_dit_rien_de_plus_n_est_pas_ecartee(
            self, phrase, decision, modele, parcelles_connues):
        proposition = _en_attente(_commande())
        appel = _confirmer if decision == "confirmer" else _abandonner
        modele.return_value = _reponse(appel(proposition.code))
        resultat = interpreteur_agent.proposer(phrase, CTX, _contexte())
        assert resultat.decision == decisions.Decision(decision, proposition.code)
        assert modele.call_count == 1

    def test_us260_ca2_une_destruction_confirmee_avec_une_autre_parcelle_reste_au_bouton(
            self, modele, parcelles_connues):
        proposition = _en_attente(_suppression())
        modele.return_value = _reponse(_confirmer(proposition.code))
        resultat = interpreteur_agent.proposer("oui, la planche sud", CTX, _contexte())
        assert resultat.decision is None and resultat.bouton_seul
        assert resultat.texte == decisions.TEXTE_BOUTON_SEUL
        assert svc_propositions.par_code(proposition.code, CTX.user_id).en_attente

    def test_us260_ca2_apres_traitement_non_4_rangs_est_une_demande_nouvelle(self, modele, parcelles_connues):
        proposition = _en_attente(_commande())
        svc_propositions.consommer(proposition, svc_propositions.ETAT_CONFIRMEE, canal="telegram")
        modele.side_effect = [
            _reponse(_abandonner(proposition.code)),
            _reponse(_rangs("Planche Nord", 4)),
            _reponse(texte="Je te propose de passer la Planche Nord à 4 rangs : tu confirmes ?"),
        ]
        resultat = interpreteur_agent.proposer("non 4 rangs", CTX, _contexte())
        assert "refusée" in self._verdict_du_tour_suivant(modele)
        assert resultat.decision is None and resultat.commande.valeurs["modification"] == "rangs=4"

    def test_us260_ca2_la_consigne_et_les_outils_disent_qu_un_non_chiffre_corrige(self):
        _en_attente(_commande())
        assert "ni un abandon ni une confirmation" in _contexte().prompt()
        descriptions = {o.nom: o.schema["function"]["description"] for o in catalogue_outils.outils_decision()}
        assert "Pas pour une correction" in descriptions["abandonner_proposition"]
        assert "Pas quand la phrase change" in descriptions["confirmer_proposition"]


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — une commande destructrice ne se confirme qu'au bouton
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3DestructriceAuBoutonSeul:

    @pytest.mark.parametrize("commande", [_suppression(), _archivage()], ids=["suppression", "archivage"])
    def test_us260_ca3_une_destruction_est_reconnue(self, commande):
        assert decisions.est_destructrice(commande)

    def test_us260_ca3_un_plan_avec_une_etape_destructrice_l_est(self):
        assert decisions.est_destructrice(interp.Plan((_commande(), _archivage()), texte_origine="x"))
        assert not decisions.est_destructrice(interp.Plan((_commande(),), texte_origine="x"))

    @pytest.mark.parametrize("commande", [_suppression(), _archivage()], ids=["suppression", "archivage"])
    def test_us260_ca3_vas_y_sur_une_destruction_n_est_pas_une_confirmation(
            self, commande, modele, parcelles_connues):
        proposition = _en_attente(commande)
        modele.return_value = _reponse(_confirmer(proposition.code))
        resultat = interpreteur_agent.proposer("vas-y", CTX, _contexte())
        assert resultat.decision is None and resultat.bouton_seul
        assert resultat.texte == decisions.TEXTE_BOUTON_SEUL
        assert modele.call_count == 1  # le code répond, le modèle n'a rien à écrire
        assert svc_propositions.par_code(proposition.code, CTX.user_id).en_attente

    def test_us260_ca3_abandonner_une_destruction_reste_permis(self, modele, parcelles_connues):
        proposition = _en_attente(_suppression())
        modele.return_value = _reponse(_abandonner(proposition.code))
        resultat = interpreteur_agent.proposer("laisse tomber", CTX, _contexte())
        assert resultat.decision == decisions.Decision("abandonner", proposition.code)

    @pytest.mark.asyncio
    async def test_us260_ca3_gherkin_le_compagnon_invite_a_cliquer_et_remontre_la_carte(self):
        proposition = _en_attente(_suppression())
        reponse = interp.ReponseAgent(texte=decisions.TEXTE_BOUTON_SEUL, bouton_seul=True)
        update, tg_ctx = _update(), MagicMock(user_data={})
        with (
            patch.object(bot_interpretation, "current_context", return_value=CTX),
            patch.object(bot_interpretation, "_interp_executer", new=AsyncMock()) as executer,
        ):
            await bot_interpretation._repondre_agent(update, tg_ctx, reponse)
        executer.assert_not_called()
        envoi = update.message.reply_text.call_args
        assert "définitive" in envoi.args[0] and "Supprimer" in envoi.args[0]
        boutons = [b.callback_data for ligne in envoi.kwargs["reply_markup"].inline_keyboard for b in ligne]
        assert boutons == [f"interp:ok:{proposition.code}", f"interp:non:{proposition.code}"]
        assert svc_propositions.par_code(proposition.code, CTX.user_id).en_attente

    @pytest.mark.asyncio
    async def test_us260_ca3_meme_si_l_agent_se_trompait_la_base_refuse(self):
        """Défense en profondeur : la décision reçue par le bot est rejouée contre la base."""
        proposition = _en_attente(_suppression())
        update, tg_ctx = _update(), MagicMock(user_data={})
        with (
            patch.object(bot_interpretation, "current_context", return_value=CTX),
            patch.object(bot_interpretation, "_contexte_sur", return_value=CTX),
            patch.object(bot_interpretation, "_interp_executer", new=AsyncMock()) as executer,
        ):
            await bot_interpretation._interp_decider(
                update, tg_ctx, decisions.Decision("confirmer", proposition.code))
        executer.assert_not_called()
        assert svc_propositions.par_code(proposition.code, CTX.user_id).en_attente
        assert "définitive" in update.message.reply_text.call_args.args[0]


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — une phrase ambiguë n'exécute rien : le compagnon demande laquelle
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4Ambiguite:

    def test_us260_ca4_ok_sans_proposition_en_attente_ne_confirme_rien(self, modele, parcelles_connues):
        modele.return_value = _reponse(_confirmer("pFANTOME00000"))
        resultat = interpreteur_agent.proposer("ok", CTX, None)
        assert resultat.decision is None and not resultat.bouton_seul
        assert resultat.texte == decisions.TEXTE_RIEN_EN_ATTENTE
        assert modele.call_count == 1

    def test_us260_ca4_deux_propositions_candidates_on_demande_laquelle(self, modele, parcelles_connues):
        proposition = _en_attente(_commande())
        _en_attente(_commande(nom="Serre"), AUTRE_POTAGER)
        contexte = _contexte()
        assert len(contexte.ailleurs) == 1 and "Serre" in contexte.ailleurs[0]
        modele.return_value = _reponse(_confirmer(proposition.code))
        resultat = interpreteur_agent.proposer("oui", CTX, contexte)
        assert resultat.decision is None
        assert "Deux propositions" in resultat.texte and "Serre" in resultat.texte
        assert svc_propositions.par_code(proposition.code, CTX.user_id).en_attente

    def test_us260_ca4_une_proposition_seulement_dans_un_autre_potager_est_nommee(
            self, modele, parcelles_connues):
        _en_attente(_commande(nom="Serre"), AUTRE_POTAGER)
        contexte = _contexte()
        assert contexte is not None and contexte.decidable and not contexte.en_attente
        modele.return_value = _reponse(_confirmer("pQUELCONQUE000"))
        resultat = interpreteur_agent.proposer("vas-y", CTX, contexte)
        assert resultat.decision is None and "dans un autre" in resultat.texte

    def test_us260_ca4_une_proposition_qui_attend_une_precision_n_est_pas_confirmable(
            self, modele, parcelles_connues):
        incomplete = _commande("passe la planche nrod à 2 rangs", "planche nrod").avec_candidats(
            "nom", ("Planche Nord",))
        proposition = _en_attente(incomplete)
        modele.return_value = _reponse(_confirmer(proposition.code))
        resultat = interpreteur_agent.proposer("oui", CTX, _contexte())
        assert resultat.decision is None and resultat.texte == decisions.TEXTE_PAS_PRETE

    @pytest.mark.asyncio
    async def test_us260_ca4_la_reponse_du_code_part_en_texte_simple(self):
        update, tg_ctx = _update(), MagicMock(user_data={})
        reponse = interp.ReponseAgent(texte=decisions.TEXTE_RIEN_EN_ATTENTE)
        with patch.object(bot_interpretation, "current_context", return_value=CTX):
            await bot_interpretation._repondre_agent(update, tg_ctx, reponse)
        assert update.message.reply_text.call_args.args[0] == decisions.TEXTE_RIEN_EN_ATTENTE


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — une proposition déjà traitée : où et quand, sans seconde exécution
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5DejaTraitee:

    def test_us260_ca5_la_derniere_traitee_est_dans_le_contexte(self):
        proposition = _en_attente(_commande())
        svc_propositions.consommer(proposition, svc_propositions.ETAT_CONFIRMEE, canal="telegram")
        contexte = _contexte()
        assert not contexte.en_attente and contexte.decidable
        assert contexte.traitee.code == proposition.code and contexte.traitee.canal == "telegram"
        assert contexte.donnees()["derniere_proposition_traitee"]["etat"] == "confirmee"
        assert "déjà été traitée" in contexte.prompt()

    def test_us260_ca5_un_oui_tardif_vise_la_proposition_traitee(self, modele, parcelles_connues):
        proposition = _en_attente(_commande())
        svc_propositions.consommer(proposition, svc_propositions.ETAT_CONFIRMEE, canal="telegram")
        modele.return_value = _reponse(_confirmer(proposition.code))
        resultat = interpreteur_agent.proposer("oui", CTX, _contexte())
        assert resultat.decision == decisions.Decision("confirmer", proposition.code)

    @pytest.mark.asyncio
    async def test_us260_ca5_elle_repond_ou_et_quand_sans_rien_refaire(self):
        proposition = _en_attente(_commande())
        svc_propositions.consommer(proposition, svc_propositions.ETAT_CONFIRMEE, canal="telegram")
        update, tg_ctx = _update(), MagicMock(user_data={})
        with (
            patch.object(bot_interpretation, "current_context", return_value=CTX),
            patch.object(bot_interpretation, "_interp_executer", new=AsyncMock()) as executer,
            patch.object(executeurs, "executer_plan") as plan,
        ):
            await bot_interpretation._interp_decider(
                update, tg_ctx, decisions.Decision("confirmer", proposition.code))
        executer.assert_not_called()
        plan.assert_not_called()
        texte = update.message.reply_text.call_args.args[0]
        assert "déjà été confirmée" in texte and "Telegram" in texte and "à " in texte

    def test_us260_ca5_l_heure_dite_est_celle_de_paris(self):
        assert decisions.heure_locale(datetime(2026, 10, 28, 12, 32)) == "13:32"   # heure d'hiver
        assert decisions.heure_locale(datetime(2026, 7, 14, 12, 32)) == "14:32"    # heure d'été

    def test_us260_ca5_une_abandonnee_se_dit_aussi(self):
        texte = decisions.deja_traitee("abandonnee", datetime(2026, 10, 28, 12, 0), "pwa")
        assert "abandonnée" in texte and "dans l'application" in texte and "je ne refais rien" in texte

    @pytest.mark.asyncio
    async def test_us260_ca5_entre_la_lecture_et_la_decision_un_clic_a_deja_tout_fait(self):
        """Le contexte de l'agent datait d'avant le clic : la sortie atomique ne laisse passer qu'une exécution."""
        proposition = _en_attente(_commande())
        update, tg_ctx = _update(), MagicMock(user_data={})
        svc_propositions.consommer(proposition, svc_propositions.ETAT_CONFIRMEE, canal="telegram")  # le clic
        with (
            patch.object(bot_interpretation, "current_context", return_value=CTX),
            patch.object(bot_interpretation, "_interp_executer", new=AsyncMock()) as executer,
        ):
            await bot_interpretation._interp_decider(
                update, tg_ctx, decisions.Decision("confirmer", proposition.code))
        executer.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# Le chemin complet : interpreter() rend la décision au bot
# ═════════════════════════════════════════════════════════════════════════════
class TestDeBoutEnBout:

    def test_us260_interpreter_rend_une_reponse_portant_la_decision(
            self, agent_actif, modele, parcelles_connues):
        proposition = _en_attente(_commande())
        modele.return_value = _reponse(_confirmer(proposition.code))
        reponse = interp.interpreter("vas-y", CTX, contexte_court=_contexte())
        assert isinstance(reponse, interp.ReponseAgent)
        assert reponse.decision == decisions.Decision("confirmer", proposition.code)
        assert reponse.proposition is None

    def test_us260_interpreter_rend_l_invitation_a_cliquer(self, agent_actif, modele, parcelles_connues):
        proposition = _en_attente(_suppression())
        modele.return_value = _reponse(_confirmer(proposition.code))
        reponse = interp.interpreter("vas-y", CTX, contexte_court=_contexte())
        assert reponse.decision is None and reponse.bouton_seul
        assert reponse.texte == decisions.TEXTE_BOUTON_SEUL

    def test_us260_la_decision_devient_un_echange_de_la_conversation(self):
        decision = decisions.Decision("confirmer", "pXXXX")
        assert contexte_court.resume_de(interp.ReponseAgent(texte="", decision=decision)) == (
            "proposition confirmée par le jardinier")
        assert contexte_court.resume_de(
            interp.ReponseAgent(texte="", decision=decisions.Decision("abandonner", "pXXXX"))
        ) == "proposition abandonnée par le jardinier"


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — la mesure du lot 2, rejouée sans modèle : zéro confirmation d'une destruction,
# zéro second geste sur une phrase de correction
# ═════════════════════════════════════════════════════════════════════════════
PHRASES_D_ACCORD = ("vas-y", "oui", "ok", "c'est bon", "go", "fais-le", "d'accord", "oui vas-y")
PHRASES_DE_CORRECTION = (("non 4 rangs", 4), ("plutôt 3 rangs", 3), ("non, 5 rangs", 5), ("mets 4 rangs", 4))


class TestCA6MesureLot2:

    @pytest.mark.parametrize("phrase", PHRASES_D_ACCORD)
    @pytest.mark.parametrize("commande", [_suppression(), _archivage()], ids=["suppression", "archivage"])
    def test_us260_ca6_zero_confirmation_par_une_phrase_pour_une_destruction(
            self, phrase, commande, modele, parcelles_connues):
        proposition = _en_attente(commande)
        modele.return_value = _reponse(_confirmer(proposition.code))   # le pire modèle : il confirme toujours
        resultat = interpreteur_agent.proposer(phrase, CTX, _contexte())
        assert resultat.decision is None
        assert svc_propositions.par_code(proposition.code, CTX.user_id).en_attente

    @pytest.mark.asyncio
    @pytest.mark.parametrize("phrase,rangs", PHRASES_DE_CORRECTION)
    async def test_us260_ca6_zero_second_geste_sur_une_phrase_de_correction(
            self, phrase, rangs, modele, parcelles_connues):
        _en_attente(_commande())
        modele.return_value = _reponse(_rangs("Planche Nord", rangs))
        resultat = interpreteur_agent.proposer(phrase, CTX, _contexte())
        assert resultat.decision is None and resultat.commande is not None
        reponse = interp.ReponseAgent(texte="", proposition=resultat.commande)
        update, tg_ctx = _update(), MagicMock(user_data={})
        with (
            patch.object(bot_interpretation, "current_context", return_value=CTX),
            patch.object(interp, "persister_journal", return_value=8),
            patch.object(bot_interpretation, "_resoudre_noms_parcelle", side_effect=lambda c: c),
            patch.object(bot_interpretation, "_interp_executer", new=AsyncMock()) as executer,
            patch.object(executeurs, "executer_plan") as plan,
        ):
            await bot_interpretation._traiter_commande_interpretee(update, tg_ctx, reponse)
        executer.assert_not_called()
        plan.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — la fiche sur la confirmation est à jour
# ═════════════════════════════════════════════════════════════════════════════
class TestCA7Fiche:

    def test_us260_ca7_la_fiche_dit_comment_repondre_par_une_phrase(self):
        from pathlib import Path

        fiche = Path("data/connaissance/doc_app/compagnon-reponses-et-memoire.md").read_text(encoding="utf-8")
        for attendu in ("vas-y", "laisse tomber", "bouton"):
            assert attendu in fiche

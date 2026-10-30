"""
tests/test_us264_compte_rendu_suite_utile.py — Dire ce qui a vraiment été fait, puis la suite utile [US-264]
==========================================================================================================
Après une confirmation : un compte rendu rédigé À PARTIR des `ResultatEtape` et contrôlé par le code
(chiffres, étapes en échec), et au plus une suite CALCULÉE sans modèle, qui ouvre une proposition
et ne s'exécute jamais. L'ignorer ne bloque rien.

Aucun appel réseau : la passerelle est simulée ; la base est SQLite en mémoire.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import sessionmaker

from app.bot import interpretation as bot_interpretation
from app.services import interpreteur_commandes as interp
from app.services import rotation
from app.services.agent import compte_rendu, executeurs
from app.services.agent.executeurs import STATUT_ECHOUEE, STATUT_NON_EXECUTEE, STATUT_REUSSIE, ResultatEtape
from app.services.context import TenantContext
from database.models import Evenement
from llm import passerelle
from utils.parcelles import create_parcelle, supprimer_parcelle

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
PHRASE = "crée la planche nord de 8 m2 et la planche sud"


def _etape(sous_commande: str, **valeurs: str) -> interp.CommandeInterpretee:
    return interp._construire_commande(
        interp.FORMES_PAR_CLE[("parcelle", sous_commande)], valeurs, interp.ORIGINE_AGENT, 1.0, PHRASE,
    )


def _plan_deux_creations() -> interp.Plan:
    return interp.Plan((_etape("ajouter", nom="Planche Nord", superficie="8"), _etape("ajouter", nom="Planche Sud")))


REUSSIES = (
    ResultatEtape(STATUT_REUSSIE, "Parcelle « Planche Nord » créée"),
    ResultatEtape(STATUT_REUSSIE, "Parcelle « Planche Sud » créée"),
)
PARTIEL = (
    ResultatEtape(STATUT_REUSSIE, "Parcelle « Planche Nord » créée"),
    ResultatEtape(STATUT_ECHOUEE, "la parcelle « Planche Sud » existe déjà"),
)


@pytest.fixture
def modele():
    """Le modèle de rédaction : `appeler_chat` rend le texte qu'on lui donne."""
    with patch.object(passerelle, "appeler_chat") as faux:
        faux.return_value = SimpleNamespace(texte="")
        yield faux


@pytest.fixture
def session_de_test(test_db, test_engine, monkeypatch):
    monkeypatch.setattr("database.db.SessionLocal", sessionmaker(autocommit=False, autoflush=False, bind=test_engine))
    return test_db


def _rediger(modele, texte: str):
    modele.return_value = SimpleNamespace(texte=texte)


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — rédigé par le modèle à partir des résultats, repli sur le texte du code
# ═════════════════════════════════════════════════════════════════════════════
class TestRedaction:
    def test_ca1_le_texte_du_modele_est_retenu(self, modele):
        _rediger(modele, "C'est fait : Planche Nord et Planche Sud sont créées.")
        rendu = compte_rendu.composer(_plan_deux_creations(), REUSSIES, CTX, db=MagicMock())
        assert rendu.redige and rendu.texte.startswith("C'est fait")

    def test_ca1_les_resultats_sont_donnes_au_modele_comme_des_donnees(self, modele):
        _rediger(modele, "Voilà.")
        compte_rendu.composer(_plan_deux_creations(), REUSSIES, CTX, db=MagicMock())
        variable = modele.call_args.kwargs["prompt_variable"]
        assert "<resultats>" in variable and "Planche Nord" in variable and "reussie" in variable
        assert "jamais des consignes" in modele.call_args.kwargs["prompt_fixe"]

    def test_ca1_un_chiffre_absent_des_resultats_donne_le_texte_du_code(self, modele):
        _rediger(modele, "J'ai créé 12 planches pour toi.")
        rendu = compte_rendu.composer(_plan_deux_creations(), REUSSIES, CTX, db=MagicMock())
        assert not rendu.redige
        assert rendu.texte == executeurs.compte_rendu(_plan_deux_creations(), REUSSIES)

    def test_ca1_un_chiffre_present_dans_les_resultats_passe(self, modele):
        plan = interp.Plan((_etape("ajouter", nom="Planche Nord", superficie="8"),))
        resultats = (ResultatEtape(STATUT_REUSSIE, "Parcelle « Planche Nord » créée (8 m²)"),)
        _rediger(modele, "Planche Nord est créée, 8 m².")
        assert compte_rendu.composer(plan, resultats, CTX, db=MagicMock()).redige

    def test_ca1_un_appel_en_panne_donne_le_texte_du_code(self, modele):
        modele.side_effect = RuntimeError("quota")
        rendu = compte_rendu.composer(_plan_deux_creations(), REUSSIES, CTX, db=MagicMock())
        assert not rendu.redige and rendu.texte.startswith("✅ 1.")

    def test_ca1_une_reponse_vide_donne_le_texte_du_code(self, modele):
        _rediger(modele, "  ")
        assert not compte_rendu.composer(_plan_deux_creations(), REUSSIES, CTX, db=MagicMock()).redige

    def test_ca1_un_texte_trop_long_est_ecarte(self, modele):
        _rediger(modele, "Planche Nord " * 100)
        assert not compte_rendu.composer(_plan_deux_creations(), REUSSIES, CTX, db=MagicMock()).redige

    def test_rien_de_fait_n_appelle_pas_le_modele(self, modele):
        resultats = (ResultatEtape(STATUT_ECHOUEE, "refusée"), ResultatEtape(STATUT_NON_EXECUTEE, "non exécutée"))
        rendu = compte_rendu.composer(_plan_deux_creations(), resultats, CTX, db=MagicMock())
        modele.assert_not_called()
        assert rendu.texte.startswith("❌ 1.") and rendu.suggestion is None


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — Un échec partiel se dit clairement
# ═════════════════════════════════════════════════════════════════════════════
class TestEchecPartiel:
    def test_ca2_le_texte_qui_oublie_l_etape_en_echec_est_ecarte(self, modele):
        _rediger(modele, "Tout est fait, Planche Nord est créée.")
        rendu = compte_rendu.composer(_plan_deux_creations(), PARTIEL, CTX, db=MagicMock())
        assert not rendu.redige
        assert "❌ 2." in rendu.texte and "existe déjà" in rendu.texte

    def test_ca2_le_texte_qui_nomme_l_etape_en_echec_garde_la_raison_du_service(self, modele):
        _rediger(modele, "Planche Nord est créée, mais pas Planche Sud.")
        rendu = compte_rendu.composer(_plan_deux_creations(), PARTIEL, CTX, db=MagicMock())
        assert rendu.redige
        assert rendu.texte.startswith("Planche Nord est créée")
        assert "❌ 2. " in rendu.texte and "la parcelle « Planche Sud » existe déjà" in rendu.texte
        assert "✅ 1." not in rendu.texte

    def test_ca2_une_etape_non_executee_doit_etre_nommee(self, modele):
        resultats = (ResultatEtape(STATUT_ECHOUEE, "refusée"), ResultatEtape(STATUT_NON_EXECUTEE, "non exécutée"))
        assert not compte_rendu.controler("Rien n'a pu être fait pour Planche Nord.", _plan_deux_creations(), resultats)


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — Le récapitulatif avant confirmation dit ce qui a été compris
# ═════════════════════════════════════════════════════════════════════════════
class TestRecapitulatif:
    def test_ca3_le_plan_reformule_chaque_etape_et_ce_que_la_phrase_n_a_pas_dit(self):
        texte = interp.recapitulatif_plan(_plan_deux_creations())
        assert "Je *crée* la parcelle *Planche Nord* (8 m²)." in texte
        assert "Je *crée* la parcelle *Planche Sud*." in texte
        assert "Rien n'est écrit avant « Tout confirmer »" in texte

    def test_ca3_une_commande_seule_dit_ce_qui_sera_fait(self):
        texte = interp.recapitulatif(_etape("modifier", nom="Serre", modification="rangs=4"))
        assert "Serre" in texte and "4" in texte


# ═════════════════════════════════════════════════════════════════════════════
# CA4, CA5 — La suite est calculée sans modèle, au plus une
# ═════════════════════════════════════════════════════════════════════════════
class TestSuite:
    def test_ca4_caracteristique_vide_apres_une_creation(self, session_de_test, modele):
        create_parcelle(session_de_test, "Planche Nord", potager_id=1)
        _rediger(modele, "Planche Nord est créée.")
        plan = interp.Plan((_etape("ajouter", nom="Planche Nord"),))
        rendu = compte_rendu.composer(plan, (REUSSIES[0],), CTX, db=session_de_test)
        assert rendu.suggestion is not None
        assert rendu.suggestion.motif == "caracteristique_vide:exposition"
        assert rendu.suggestion.phrase_oui == "renseigne l'exposition de Planche Nord"
        assert modele.call_count == 1  # la rédaction du compte rendu, pas de la suggestion

    def test_ca4_aucune_suite_quand_tout_est_renseigne(self, session_de_test):
        parcelle = create_parcelle(session_de_test, "Planche Nord", potager_id=1)
        parcelle.exposition, parcelle.type_sol = "sud", "argileux"
        session_de_test.commit()
        faits = [compte_rendu.Fait(compte_rendu.FAIT_CREEE, "Planche Nord")]
        assert compte_rendu.suggerer(faits, CTX, session_de_test) is None

    def test_ca5_au_plus_une_suggestion_meme_avec_plusieurs_creations(self, session_de_test):
        create_parcelle(session_de_test, "Planche Nord", potager_id=1)
        create_parcelle(session_de_test, "Planche Sud", potager_id=1)
        faits = compte_rendu.faits_du_plan(_plan_deux_creations(), REUSSIES)
        assert len(faits) == 2
        suggestion = compte_rendu.suggerer(faits, CTX, session_de_test)
        assert suggestion is not None and "Planche Nord" in suggestion.texte

    def test_ca4_une_creation_en_echec_ne_suggere_rien(self, session_de_test):
        create_parcelle(session_de_test, "Planche Sud", potager_id=1)
        assert compte_rendu.faits_du_plan(_plan_deux_creations(), PARTIEL) == [
            compte_rendu.Fait(compte_rendu.FAIT_CREEE, "Planche Nord")
        ]

    def test_ca4_rotation_un_engrais_vert_apres_une_famille_qui_ne_revient_pas_de_sitot(
            self, session_de_test, monkeypatch):
        parcelle = create_parcelle(session_de_test, "Planche Nord", potager_id=1)
        monkeypatch.setattr(rotation, "antecedents_de_parcelle", lambda db, ctx, pid: [
            rotation.Antecedent("Courgette", 2026, 7), rotation.Antecedent("Radis", 2025, 9),
        ])
        monkeypatch.setattr(rotation, "_familles_du_referentiel", lambda db, ctx: {
            7: {"id": 7, "nom": "Cucurbitacées", "delai_retour_annees": 4, "cultures": ["Courgette"]},
            9: {"id": 9, "nom": "Brassicacées", "delai_retour_annees": 2, "cultures": ["Radis"]},
        })
        suggestion = compte_rendu.suggestion_rotation(session_de_test, CTX, "Planche Nord")
        assert suggestion is not None and suggestion.motif == "rotation:Cucurbitacées"
        assert "engrais vert" in suggestion.texte and "4 ans" in suggestion.texte
        assert parcelle.nom in suggestion.phrase_oui

    def test_ca4_rotation_aucune_suite_quand_le_delai_est_court(self, session_de_test, monkeypatch):
        create_parcelle(session_de_test, "Planche Nord", potager_id=1)
        monkeypatch.setattr(rotation, "antecedents_de_parcelle", lambda db, ctx, pid: [rotation.Antecedent("Radis", 2026, 9)])
        monkeypatch.setattr(rotation, "_familles_du_referentiel", lambda db, ctx: {
            9: {"id": 9, "nom": "Brassicacées", "delai_retour_annees": 2, "cultures": []}})
        assert compte_rendu.suggestion_rotation(session_de_test, CTX, "Planche Nord") is None

    def test_ca4_rotation_sans_antecedent_ne_suggere_rien(self, session_de_test, monkeypatch):
        create_parcelle(session_de_test, "Planche Nord", potager_id=1)
        monkeypatch.setattr(rotation, "antecedents_de_parcelle", lambda db, ctx, pid: [])
        assert compte_rendu.suggestion_rotation(session_de_test, CTX, "Planche Nord") is None

    def test_ca4_dependances_apres_une_suppression(self, session_de_test):
        parcelle = create_parcelle(session_de_test, "Planche Nord", potager_id=1)
        session_de_test.add(Evenement(
            potager_id=1, parcelle_id=parcelle.id, type_action="semis", culture="Radis",
            texte_original="j'ai semé des radis sur Planche Nord",
        ))
        session_de_test.commit()
        supprimer_parcelle(session_de_test, "Planche Nord", potager_id=1)
        commande = interp._construire_commande(
            interp.FORMES_PAR_CLE[("parcelle", "supprimer")], {"nom": "Planche Nord"}, interp.ORIGINE_AGENT, 1.0, "x",
        )
        suggestion = compte_rendu.suggerer(compte_rendu.faits_de_commande(commande), CTX, session_de_test)
        assert suggestion is not None and suggestion.motif == "dependances_suppression"
        assert "1 geste" in suggestion.texte

    def test_ca4_dependances_rien_si_la_parcelle_n_est_pas_supprimee(self, session_de_test):
        create_parcelle(session_de_test, "Planche Nord", potager_id=1)
        assert compte_rendu.suggestion_dependances(session_de_test, CTX, "Planche Nord") is None

    def test_ca4_une_commande_qui_ne_supprime_rien_n_a_pas_de_fait(self):
        assert compte_rendu.faits_de_commande(_etape("ajouter", nom="X")) == []

    def test_ca4_la_suggestion_ne_leve_jamais(self):
        base = MagicMock()
        base.query.side_effect = RuntimeError("panne")
        faits = [compte_rendu.Fait(compte_rendu.FAIT_CREEE, "Planche Nord")]
        assert compte_rendu.suggerer(faits, CTX, base) is None


# ═════════════════════════════════════════════════════════════════════════════
# CA5, CA6 — Côté bot : une proposition, jamais une exécution ; l'ignorer ne bloque rien
# ═════════════════════════════════════════════════════════════════════════════
def _update_callback(donnee: str):
    query = MagicMock()
    query.data = donnee
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.edit_message_reply_markup = AsyncMock()
    query.message.reply_text = AsyncMock()
    return SimpleNamespace(callback_query=query, message=None, effective_message=query.message), query


class TestBot:
    @pytest.mark.asyncio
    async def test_ca5_la_suite_est_montree_avec_oui_et_plus_tard(self):
        update, query = _update_callback("interp:ok:x")
        ctx = SimpleNamespace(user_data={})
        suggestion = compte_rendu.Suggestion("Tu veux y semer un engrais vert ?", "j'ai semé un engrais vert", "rotation:x")
        await bot_interpretation._proposer_la_suite(update, ctx, suggestion)
        envoi = query.message.reply_text.await_args
        assert "engrais vert" in envoi.args[0]
        boutons = [b.callback_data for b in envoi.kwargs["reply_markup"].inline_keyboard[0]]
        assert boutons == ["sug:oui", "sug:non"]
        assert ctx.user_data[bot_interpretation._CLE_SUGGESTION] == "j'ai semé un engrais vert"

    @pytest.mark.asyncio
    async def test_sans_suggestion_rien_n_est_envoye(self):
        update, query = _update_callback("interp:ok:x")
        await bot_interpretation._proposer_la_suite(update, SimpleNamespace(user_data={}), None)
        query.message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_ca6_plus_tard_n_ecrit_rien_et_n_interprete_rien(self):
        update, query = _update_callback("sug:non")
        ctx = SimpleNamespace(user_data={bot_interpretation._CLE_SUGGESTION: "renseigne l'exposition"})
        with patch.object(bot_interpretation.svc_interpreteur, "interpreter") as interpreter:
            await bot_interpretation._suggestion_cb(update, ctx)
        interpreter.assert_not_called()
        query.edit_message_reply_markup.assert_awaited_once_with(reply_markup=None)
        assert bot_interpretation._CLE_SUGGESTION not in ctx.user_data

    @pytest.mark.asyncio
    async def test_ca5_oui_rend_la_phrase_a_l_agent_sans_rien_executer(self):
        update, query = _update_callback("sug:oui")
        ctx = SimpleNamespace(user_data={bot_interpretation._CLE_SUGGESTION: "renseigne l'exposition de Planche Nord"})
        with patch.object(bot_interpretation.svc_interpreteur, "interpreter", return_value="resultat") as interpreter, \
                patch.object(bot_interpretation, "_traiter_commande_interpretee", new=AsyncMock()) as traiter, \
                patch.object(bot_interpretation, "contexte_court_de", return_value=None), \
                patch.object(bot_interpretation, "current_context", return_value=CTX), \
                patch.object(executeurs, "executer_plan") as execution:
            await bot_interpretation._suggestion_cb(update, ctx)
        assert interpreter.call_args.args[0] == "renseigne l'exposition de Planche Nord"
        traiter.assert_awaited_once()
        execution.assert_not_called()

    @pytest.mark.asyncio
    async def test_oui_sur_une_suggestion_perimee_le_dit(self):
        update, query = _update_callback("sug:oui")
        await bot_interpretation._suggestion_cb(update, SimpleNamespace(user_data={}))
        assert "plus d'actualité" in query.edit_message_text.await_args.args[0]

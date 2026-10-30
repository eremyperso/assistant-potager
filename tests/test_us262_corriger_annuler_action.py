"""
tests/test_us262_corriger_annuler_action.py — Corriger ou annuler par une phrase ce qui vient d'être fait [US-262]
==================================================================================================================
« En fait c'était 3 rangs », « annule le dernier semis » : la phrase vise une action menée
(US-261), jamais un nouveau geste. L'agent appelle `corriger_action` / `annuler_action`, le
code en fait une proposition avant → après, et l'exécution passe par `evenements`.

Aucun appel réseau : la passerelle est simulée. Les actions menées vivent dans la base de la
fixture `memoire_compagnon` ; les événements et les parcelles dans `test_db`.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import func
from sqlalchemy.orm import sessionmaker

from app import config
from app.bot import interpretation as bot_interpretation
from app.services import evenements as svc_evenements
from app.services import interpreteur_commandes as interp
from app.services import potagers as svc_potagers
from app.services.agent import catalogue_outils, interpreteur_agent
from app.services.compagnon import actions_menees, corrections, decisions
from app.services.context import TenantContext
from database.models import ActionMenee, Evenement, User
from llm import passerelle
from llm.passerelle import AppelOutil, ReponseOutils
from utils.parcelles import create_parcelle

PHRASE_SEMIS = "semis radis planche Sud 2 rangs"


# ═════════════════════════════════════════════════════════════════════════════
# Outillage
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def potager(test_db, test_engine, monkeypatch):
    """Un vrai potager, sa Planche Sud, et la lecture des gestes par `corrections` sur `test_db`."""
    utilisateur = User(email="jardinier262@example.com", mot_de_passe_hash="x")
    test_db.add(utilisateur)
    test_db.commit()
    lieu = svc_potagers.creer_potager(test_db, utilisateur.id, "Jardin")
    create_parcelle(test_db, "Planche Sud", potager_id=lieu.id)
    create_parcelle(test_db, "Planche Nord", potager_id=lieu.id)
    monkeypatch.setattr(corrections, "SessionLocal", sessionmaker(bind=test_engine, autoflush=False))
    return TenantContext(user_id=utilisateur.id, potager_id=lieu.id, role="owner")


@pytest.fixture
def modele():
    with patch.object(passerelle, "appeler_chat_outils") as faux:
        yield faux


@pytest.fixture
def parcelles_connues(monkeypatch):
    monkeypatch.setattr(interpreteur_agent, "noms_parcelles_du_potager", lambda ctx: ("Planche Sud", "Planche Nord"))
    monkeypatch.setattr(interpreteur_agent, "voisin_en_base", lambda ctx: (lambda nom: None))


@pytest.fixture
def agent_actif(monkeypatch):
    monkeypatch.setattr(config, "AGENT_MODE", "actif", raising=False)


def _geste(db, ctx: TenantContext, culture: str = "radis", rang=2, action: str = "semis",
           parcelle: str = "Planche Sud", il_y_a: timedelta = timedelta(0), **champs) -> Evenement:
    """Un geste au carnet, retenu comme action menée — comme après une confirmation."""
    from database.models import Parcelle

    lieu = db.query(Parcelle).filter(Parcelle.nom == parcelle, Parcelle.potager_id == ctx.potager_id).first()
    event = Evenement(
        type_action=action, culture=culture, rang=rang, parcelle_id=lieu.id if lieu else None,
        date=datetime(2026, 10, 29), potager_id=ctx.potager_id, texte_original=PHRASE_SEMIS, **champs,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    nom = lieu.nom if lieu else None
    actions_menees.noter(
        ctx, nature=actions_menees.NATURE_GESTE, resume=actions_menees.resume_evenement(event, nom),
        cible_type="evenement", cible_id=event.id, cible_nom=nom,
        apres=actions_menees.instantane_evenement(event, nom), maintenant=datetime.utcnow() - il_y_a,
    )
    return event


def _reponse(*appels: AppelOutil, texte: str = "") -> ReponseOutils:
    return ReponseOutils(
        texte=texte, modele="test", appel_type=passerelle.TYPE_AGENT, tokens_in=10, tokens_out=5,
        latence_ms=1, appels=tuple(appels), statut=passerelle.STATUT_OK,
    )


def _valider(outil: str, arguments: dict, phrase: str, ctx: TenantContext) -> corrections.VerdictCorrection:
    return corrections.valider(outil, arguments, phrase, ctx, ("Planche Sud", "Planche Nord"))


def _nb_gestes(db, ctx: TenantContext) -> int:
    return db.query(func.count(Evenement.id)).filter(Evenement.potager_id == ctx.potager_id).scalar()


def _actions(memoire) -> list[ActionMenee]:
    with memoire() as db:
        return db.query(ActionMenee).order_by(ActionMenee.id).all()


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — deux outils d'écriture, qui produisent une proposition avant → après
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1OutilsEtProposition:

    def test_us262_ca1_les_deux_outils_existent_et_ecrivent(self):
        outils = {o.nom: o for o in catalogue_outils.outils_correction()}
        assert set(outils) == {"corriger_action", "annuler_action"}
        assert all(o.ecrit and o.correction for o in outils.values())
        assert outils["annuler_action"].detruit and not outils["corriger_action"].detruit
        corriger = outils["corriger_action"].schema["function"]["parameters"]
        assert corriger["required"] == ["ref", "champs"]
        assert {"rang", "quantite", "culture", "parcelle"} <= set(corriger["properties"]["champs"]["properties"])
        assert outils["annuler_action"].schema["function"]["parameters"]["required"] == ["ref"]

    def test_us262_ca1_le_plafond_compte_les_outils_offerts_a_la_demande(self):
        assert catalogue_outils.controler_parite_outils() == []
        assert (len(catalogue_outils.outils()) + len(catalogue_outils.OUTILS_DECISION)
                + len(catalogue_outils.OUTILS_CORRECTION)) <= catalogue_outils.NB_OUTILS_MAX

    def test_us262_ca1_gherkin_trois_rangs_devient_une_proposition_avant_apres(self, test_db, potager):
        _geste(test_db, potager)
        verdict = _valider("corriger_action", {"ref": "A1", "champs": {"rang": 3}}, "en fait c'était 3 rangs", potager)
        commande = verdict.commande
        assert commande is not None and corrections.est_correction(commande)
        assert "Semis radis : 2 rangs → 3 rangs" in interp.recapitulatif(commande)
        assert "Semis radis : 2 rangs → 3 rangs" in commande.commande_equivalente()
        assert not decisions.est_destructrice(commande) and decisions.est_prete(commande)

    def test_us262_ca1_une_annulation_est_une_proposition_destructrice(self, test_db, potager):
        _geste(test_db, potager)
        commande = _valider("annuler_action", {"ref": "A1"}, "annule le dernier semis", potager).commande
        assert commande is not None and commande.sous_commande == corrections.SOUS_ANNULER
        assert decisions.est_destructrice(commande)   # ne se confirme qu'au bouton (US-260 / CA3)
        assert "retiré du carnet" in interp.recapitulatif(commande)

    def test_us262_ca1_la_proposition_survit_a_la_base(self, test_db, potager):
        """Rangée en base (US-259) puis relue : ce qui se confirme est ce qui a été montré."""
        from app.services.compagnon import propositions

        _geste(test_db, potager)
        commande = _valider("corriger_action", {"ref": "A1", "champs": {"rang": 3}}, "en fait 3 rangs", potager).commande
        relue = propositions.proposer(potager, commande)
        assert propositions.par_code(relue.code, potager.user_id).commande == commande

    @pytest.mark.parametrize("champs, raison", [
        ({"rang": 4}, "n'est pas dit"),               # un nombre que la phrase ne dit pas
        ({"rang": 2}, "rien ne change"),              # la valeur actuelle
        ({"parcelle": "Serre"}, "inconnue"),          # une parcelle qui n'existe pas
        ({"culture": None}, "aucun champ corrigé"),   # rien à corriger
    ])
    def test_us262_ca1_les_champs_sont_ancres_sur_la_phrase(self, test_db, potager, champs, raison):
        _geste(test_db, potager)
        verdict = _valider("corriger_action", {"ref": "A1", "champs": champs},
                           "en fait c'était 3 rangs, pas 2, sur la serre", potager)
        assert verdict.commande is None and raison in verdict.raison

    def test_us262_ca1_trois_en_lettres_et_une_autre_parcelle(self, test_db, potager):
        _geste(test_db, potager)
        verdict = _valider("corriger_action", {"ref": "A1", "champs": {"rang": 3, "parcelle": "Planche Nord"}},
                           "non, trois rangs et sur la planche nord", potager)
        lignes = corrections.lignes_avant_apres(verdict.commande)
        assert "Semis radis : 2 rangs → 3 rangs" in lignes
        assert "Semis radis — parcelle : Planche Sud → Planche Nord" in lignes


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — l'exécution passe par `evenements`, après confirmation seulement
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2Execution:

    def test_us262_ca2_rien_n_est_ecrit_avant_la_confirmation(self, test_db, potager):
        event = _geste(test_db, potager)
        _valider("corriger_action", {"ref": "A1", "champs": {"rang": 3}}, "en fait c'était 3 rangs", potager)
        test_db.refresh(event)
        assert event.rang == 2

    def test_us262_ca2_la_correction_passe_par_corriger_evenement(self, test_db, potager, memoire_compagnon):
        event = _geste(test_db, potager)
        commande = _valider("corriger_action", {"ref": "A1", "champs": {"rang": 3}},
                            "en fait c'était 3 rangs", potager).commande
        with patch.object(svc_evenements, "corriger_evenement", wraps=svc_evenements.corriger_evenement) as espion:
            texte = corrections.executer(test_db, potager, commande)
        espion.assert_called_once()
        assert espion.call_args.args[2] == event.id and espion.call_args.args[3] == {"rang": 3}
        test_db.refresh(event)
        assert event.rang == 3 and texte.startswith("✅ Corrigé")
        assert _nb_gestes(test_db, potager) == 1   # aucun second semis
        correction = _actions(memoire_compagnon)[-1]
        assert correction.resume.startswith("correction : ")
        assert (correction.avant["rang"], correction.apres["rang"]) == (2, 3)
        assert correction.cible_id == event.id

    def test_us262_ca2_l_annulation_passe_par_supprimer_evenement(self, test_db, potager, memoire_compagnon):
        event = _geste(test_db, potager)
        commande = _valider("annuler_action", {"ref": "A1"}, "annule le dernier semis", potager).commande
        with patch.object(svc_evenements, "supprimer_evenement", wraps=svc_evenements.supprimer_evenement) as espion:
            texte = corrections.executer(test_db, potager, commande)
        espion.assert_called_once()
        assert _nb_gestes(test_db, potager) == 0 and texte.startswith("🗑 Annulé")
        assert _actions(memoire_compagnon)[-1].resume.startswith("annulation : semis radis")
        # Le geste annulé n'est plus une candidate : on ne corrige pas ce qui n'existe plus.
        assert corrections.candidates(potager) == []
        assert event.id not in [c.evenement_id for c in corrections.candidates(potager)]

    def test_us262_ca2_un_geste_qui_a_change_entre_temps_n_est_pas_touche(self, test_db, potager):
        event = _geste(test_db, potager)
        commande = _valider("corriger_action", {"ref": "A1", "champs": {"rang": 3}}, "en fait 3 rangs", potager).commande
        event.rang = 5
        test_db.commit()
        assert "a changé" in corrections.executer(test_db, potager, commande)
        test_db.refresh(event)
        assert event.rang == 5

    def test_us262_ca2_un_geste_disparu_n_est_pas_recree(self, test_db, potager):
        event = _geste(test_db, potager)
        commande = _valider("annuler_action", {"ref": "A1"}, "annule le dernier semis", potager).commande
        test_db.delete(event)
        test_db.commit()
        assert corrections.executer(test_db, potager, commande) == corrections.TEXTE_DISPARU

    def test_us262_ca2_un_semis_qui_a_des_suites_ne_s_annule_pas_d_une_phrase(self, test_db, potager):
        semis = _geste(test_db, potager)
        test_db.add(Evenement(type_action="mise_en_godet", culture="radis", quantite=6, potager_id=potager.potager_id,
                              origine_graines_id=semis.id, date=datetime(2026, 10, 29)))
        test_db.commit()
        verdict = _valider("annuler_action", {"ref": "A1"}, "annule le semis de radis", potager)
        assert verdict.commande is None and "/corriger" in verdict.question

    def test_us262_ca2_parcelle_et_date_corrigees_par_le_service(self, test_db, potager):
        event = _geste(test_db, potager)
        commande = _valider("corriger_action",
                            {"ref": "A1", "champs": {"parcelle": "Planche Nord", "date": "2026-10-28"}},
                            "non, c'était hier sur la planche nord, le 28", potager).commande
        texte = corrections.executer(test_db, potager, commande)
        test_db.refresh(event)
        assert texte.startswith("✅ Corrigé")
        from database.models import Parcelle

        assert test_db.get(Parcelle, event.parcelle_id).nom == "Planche Nord"
        assert event.date.date().isoformat() == "2026-10-28"

    def test_us262_ca2_un_lecteur_ne_corrige_rien(self, test_db, potager):
        """❌ Le rôle se relit à l'exécution : un membre en lecture seule ne modifie pas le carnet."""
        event = _geste(test_db, potager)
        commande = _valider("corriger_action", {"ref": "A1", "champs": {"rang": 3}}, "en fait 3 rangs", potager).commande
        lecteur = TenantContext(user_id=potager.user_id, potager_id=potager.potager_id, role="lecteur")
        texte = corrections.executer(test_db, lecteur, commande)
        test_db.refresh(event)
        assert texte.startswith("❌") and event.rang == 2

    @pytest.mark.asyncio
    async def test_us262_ca2_le_bot_execute_par_le_service_sans_handler(self, test_db, potager):
        commande = SimpleNamespace(forme=corrections.FORME_CORRIGER, valeurs={})
        message = MagicMock(reply_text=AsyncMock())
        update = SimpleNamespace(message=message, callback_query=None)
        with patch.object(corrections, "executer", return_value="✅ Corrigé : x") as executer, \
                patch.object(bot_interpretation, "_handler_de_commande") as handler, \
                patch.object(bot_interpretation, "current_context", return_value=potager):
            await bot_interpretation._interp_executer(update, MagicMock(), commande, potager_id=potager.potager_id)
        executer.assert_called_once()
        handler.assert_not_called()
        message.reply_text.assert_awaited_once_with("✅ Corrigé : x")


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — 10 minutes après une action, l'agent passe avant le filtre « geste annoncé »
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3AvantLeFiltreGeste:

    @pytest.fixture
    def agent(self, monkeypatch):
        faux = MagicMock(return_value=interpreteur_agent.ResultatAgent(disponible=True, texte="ok"))
        monkeypatch.setattr(interpreteur_agent, "proposer", faux)
        monkeypatch.setattr(interpreteur_agent, "persister_reponse", lambda *a, **k: None)
        return faux

    def test_us262_ca3_une_correction_juste_apres_un_geste_va_a_l_agent(self, test_db, potager, agent_actif, agent):
        _geste(test_db, potager, il_y_a=timedelta(minutes=3))
        resultat = interp.interpreter("en fait j'ai semé 3 rangs", potager)
        agent.assert_called_once()
        assert isinstance(resultat, interp.ReponseAgent)

    def test_us262_ca3_apres_dix_minutes_le_filtre_reprend(self, test_db, potager, agent_actif, agent):
        _geste(test_db, potager, il_y_a=timedelta(minutes=20))
        assert interp.interpreter("en fait j'ai semé 3 rangs", potager) is None
        agent.assert_not_called()

    def test_us262_ca3_un_geste_nouveau_garde_le_filtre(self, test_db, potager, agent_actif, agent):
        _geste(test_db, potager, il_y_a=timedelta(minutes=1))
        assert interp.interpreter("j'ai semé des carottes planche nord", potager) is None
        agent.assert_not_called()

    def test_us262_ca3_annule_le_dernier_semis_n_est_jamais_un_semis(self, test_db, potager, agent_actif, agent):
        _geste(test_db, potager, il_y_a=timedelta(hours=3))
        interp.interpreter("annule le dernier semis", potager)
        agent.assert_called_once()

    def test_us262_ca3_modele_indisponible_aucune_proposition(self, test_db, potager, agent_actif, monkeypatch):
        """❌ Groq / Mistral en 429 : rien n'est proposé ni écrit ; la phrase suit son chemin (CA5 garde le carnet)."""
        monkeypatch.setattr(interpreteur_agent, "proposer",
                            lambda *a, **k: interpreteur_agent.ResultatAgent(disponible=False, motif="429"))
        monkeypatch.setattr(interp, "_appeler_modele", lambda *a, **k: None)
        _geste(test_db, potager, il_y_a=timedelta(minutes=1))
        resultat = interp.interpreter("en fait j'ai semé 3 rangs", potager)
        assert not isinstance(resultat, interp.ReponseAgent)
        assert _nb_gestes(test_db, potager) == 1

    def test_us262_ca3_sans_agent_actif_rien_ne_change(self, test_db, potager, monkeypatch, agent):
        monkeypatch.setattr(config, "AGENT_MODE", "off", raising=False)
        _geste(test_db, potager, il_y_a=timedelta(minutes=1))
        assert interp.interpreter("en fait j'ai semé 3 rangs", potager) is None

    def test_us262_ca3_le_raccourci_annuler_cede_a_l_agent(self, test_db, potager, agent_actif):
        assert not corrections.pour_l_agent_plutot_que_le_raccourci("annuler le dernier semis", potager)
        _geste(test_db, potager)
        assert corrections.pour_l_agent_plutot_que_le_raccourci("annuler le dernier semis", potager)
        assert not corrections.pour_l_agent_plutot_que_le_raccourci("annuler", potager)

    @pytest.mark.parametrize("phrase, attendu", [
        ("en fait c'était 3 rangs", True), ("non, des carottes", True), ("finalement c'est 3 rangs", True),
        ("annule le dernier semis", True), ("je me suis trompé, 4 rangs", True),
        ("j'ai semé des carottes", False), ("arrosé la planche nord", False),
    ])
    def test_us262_ca3_les_marques_de_correction(self, phrase, attendu):
        assert corrections.ressemble_a_une_correction(phrase) is attendu


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — deux actions candidates : le compagnon demande laquelle, en les nommant
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4Laquelle:

    def test_us262_ca4_deux_semis_sans_designation(self, test_db, potager):
        _geste(test_db, potager, culture="radis", il_y_a=timedelta(minutes=5))
        _geste(test_db, potager, culture="carottes", rang=4, parcelle="Planche Nord")
        verdict = _valider("annuler_action", {}, "annule le semis", potager)
        assert verdict.commande is None
        assert "Laquelle" in verdict.question
        assert "semis radis" in verdict.question and "semis carottes" in verdict.question

    def test_us262_ca4_le_dernier_designe_le_plus_recent(self, test_db, potager):
        _geste(test_db, potager, culture="radis", il_y_a=timedelta(minutes=5))
        carottes = _geste(test_db, potager, culture="carottes", rang=4, parcelle="Planche Nord")
        commande = _valider("annuler_action", {"ref": "A2"}, "annule le dernier semis", potager).commande
        assert commande.valeurs["evenement"] == str(carottes.id)

    def test_us262_ca4_la_culture_dite_l_emporte_sur_la_reference(self, test_db, potager):
        """« annule le semis de radis » ne retire jamais les carottes que le modèle aurait choisies."""
        _geste(test_db, potager, culture="radis", il_y_a=timedelta(minutes=5))
        _geste(test_db, potager, culture="carottes", rang=4, parcelle="Planche Nord")
        verdict = _valider("annuler_action", {"ref": "A1"}, "annule le semis de radis", potager)
        assert verdict.commande is None and "A2" in verdict.raison
        commande = _valider("annuler_action", {"ref": "A2"}, "annule le semis de radis", potager).commande
        assert "radis" in commande.valeurs["resume"]

    def test_us262_ca4_une_seule_candidate_se_passe_de_reference(self, test_db, potager):
        _geste(test_db, potager)
        _geste(test_db, potager, action="arrosage", culture=None, rang=None)
        commande = _valider("annuler_action", {}, "annule le semis", potager).commande
        assert "semis radis" in commande.valeurs["resume"]

    def test_us262_ca4_la_question_est_dite_par_le_code_dans_la_boucle(
            self, test_db, potager, modele, parcelles_connues):
        _geste(test_db, potager, culture="radis", il_y_a=timedelta(minutes=5))
        _geste(test_db, potager, culture="carottes", rang=4, parcelle="Planche Nord")
        modele.side_effect = [
            _reponse(AppelOutil("corriger_action", {"champs": {"rang": 3}})),
            _reponse(texte="C'est fait !"),
        ]
        resultat = interpreteur_agent.proposer("en fait c'était 3 rangs", potager, None)
        assert resultat.proposition is None
        assert "Laquelle veux-tu corriger" in resultat.texte
        assert "semis radis" in resultat.texte and "semis carottes" in resultat.texte
        assert modele.call_count == 1   # la question du code clôt la boucle

    def test_us262_ca4_un_geste_corrige_deux_fois_n_est_qu_une_candidate(self, test_db, potager):
        event = _geste(test_db, potager)
        svc_evenements.corriger_evenement(test_db, potager, event.id, {"rang": 3}, " [test]")
        (candidate,) = corrections.candidates(potager)
        assert candidate.ref == "A1" and candidate.valeurs["rang"] == 3


# ═════════════════════════════════════════════════════════════════════════════
# Recette du 29/10/2026 (Ministral 8B) — la dernière action est une modification de parcelle
# ═════════════════════════════════════════════════════════════════════════════
class TestRecetteParcelleModifiee:
    """« passe la planche principal à 7 rangs » → « non 6 rangs » → ✅ → « en fait c'était 8 rangs ».
    Avant correctif : la parcelle n'était pas corrigeable, le compagnon demandait laquelle entre
    deux arrosages et un semis compté en graines."""

    @pytest.fixture
    def recette(self, test_db, potager):
        from utils.parcelles import find_doublon, normalize_parcelle_name

        create_parcelle(test_db, "principal", potager_id=potager.potager_id)
        parcelle, _ = find_doublon(test_db, normalize_parcelle_name("principal"), potager_id=potager.potager_id)
        parcelle.nb_rangs = 6
        test_db.commit()
        _geste(test_db, potager, action="arrosage", culture=None, rang=None, parcelle="principal",
               il_y_a=timedelta(minutes=40))
        _geste(test_db, potager, culture="radis", rang=None, parcelle="principal", quantite=1, unite="graines",
               il_y_a=timedelta(minutes=30))
        _geste(test_db, potager, action="arrosage", culture=None, rang=None, parcelle="principal",
               il_y_a=timedelta(minutes=20))
        actions_menees.noter(
            potager, nature=actions_menees.NATURE_COMMANDE, resume="Modifier une parcelle : principal",
            cible_type="parcelle", cible_nom="principal",
            avant={"nom": "principal", "actif": True, "nb_rangs": 7},
            apres={"nom": "principal", "actif": True, "nb_rangs": 6},
        )
        return potager

    @pytest.mark.parametrize("ref", ["A1", None, "A3"])
    def test_us262_recette_huit_rangs_corrige_la_parcelle(self, recette, ref):
        verdict = corrections.valider("corriger_action", {"ref": ref, "champs": {"rang": 8}},
                                      "en fait c'était 8 rangs", recette, ("Planche Sud", "Planche Nord", "principal"))
        commande = verdict.commande
        assert commande is not None, verdict
        assert commande.commande_equivalente() == "/parcelle modifier principal rangs=8"
        recap = interp.recapitulatif(commande)
        assert recap.startswith("*Corriger* : principal") and "6 → 8" in recap

    def test_us262_recette_les_gestes_sans_rangs_ne_sont_pas_candidats(self, recette):
        liste = corrections.candidates(recette)
        assert [c.cible for c in liste] == ["parcelle", "evenement", "evenement", "evenement"]
        assert [c.ref for c in corrections.compatibles(liste, {"rang": 8})] == ["A1"]

    def test_us262_recette_dans_la_boucle_de_l_agent(self, recette, modele, monkeypatch):
        monkeypatch.setattr(interpreteur_agent, "noms_parcelles_du_potager", lambda ctx: ("principal",))
        monkeypatch.setattr(interpreteur_agent, "voisin_en_base", lambda ctx: (lambda nom: None))
        modele.side_effect = [
            _reponse(AppelOutil("corriger_action", {"ref": "A1", "champs": {"rang": 8}})),
            _reponse(texte="Je corrige la planche principal : 8 rangs."),
        ]
        resultat = interpreteur_agent.proposer("en fait c'était 8 rangs", recette, None)
        assert resultat.commande is not None
        assert resultat.commande.commande_equivalente() == "/parcelle modifier principal rangs=8"

    def test_us262_recette_une_modification_de_parcelle_ne_s_annule_pas_d_un_mot(self, recette):
        verdict = corrections.valider("annuler_action", {"ref": "A1"}, "annule ce que je viens de faire", recette)
        assert verdict.commande is None and "remets" in verdict.question

    def test_us262_recette_la_valeur_doit_etre_dite(self, recette):
        verdict = corrections.valider("corriger_action", {"ref": "A1", "champs": {"rang": 9}},
                                      "en fait c'était 8 rangs", recette, ("principal",))
        assert verdict.commande is None


class TestRecetteModeleSansAppel:
    """Recette du 29/10 (Ministral 8B) : « j'ai planté 5 plants de tomates » ✅, puis « oups, me suis
    trompé c'était 2 plants » → le modèle ÉCRIT « Proposition : /corriger — … Confirme-moi » sans
    appeler d'outil ; aucune carte, et « oui » ne confirmait rien."""

    PHRASE = "oups, me suis trompé c'était 2 plants"
    TEXTE_DU_MODELE = ("Proposition : /corriger — Plantation tomate : 5 plants → 2 plants sur la planche "
                       "principale. Confirme-moi si c'est bien celui-là !")

    @pytest.fixture
    def recette(self, test_db, potager):
        _geste(test_db, potager, culture="radis", rang=None, quantite=1, unite="graines",
               il_y_a=timedelta(minutes=30))
        _geste(test_db, potager, action="arrosage", culture=None, rang=None, quantite=10, unite="litres",
               il_y_a=timedelta(minutes=20))
        _geste(test_db, potager, action="plantation", culture="tomate", rang=None, quantite=5, unite="plants")
        return potager

    def test_us262_recette_le_texte_du_modele_est_une_proposition_decrite(self):
        assert interpreteur_agent.decrit_une_proposition(self.TEXTE_DU_MODELE)
        assert not interpreteur_agent.decrit_une_proposition("Tu veux que je te propose quelque chose ?")

    def test_us262_recette_l_unite_dite_designe_la_plantation(self, recette):
        commande = _valider("corriger_action", {"champs": {"quantite": 2}}, self.PHRASE, recette).commande
        assert "Plantation tomate : 5 plants → 2 plants" in corrections.lignes_avant_apres(commande)

    def test_us262_recette_relance_puis_filet_donnent_la_carte(self, recette, modele, parcelles_connues):
        modele.side_effect = [_reponse(texte=self.TEXTE_DU_MODELE), _reponse(texte=self.TEXTE_DU_MODELE)]
        resultat = interpreteur_agent.proposer(self.PHRASE, recette, None)
        # Une seule relance, qui dit quel outil appeler…
        assert modele.call_count == 2
        relance = modele.call_args_list[1].kwargs["historique"][-1]["content"]
        assert relance == interpreteur_agent.CORRECTION_SANS_APPEL_ACTION
        # … puis le code fait la proposition lui-même : une carte à boutons, pas une question en texte.
        assert corrections.est_correction(resultat.commande)
        assert "Plantation tomate : 5 plants → 2 plants" in resultat.commande.commande_equivalente()
        assert resultat.texte == corrections.TEXTE_FILET
        assert "filet_correction" in resultat.outils

    def test_us262_recette_un_modele_qui_se_reprend_n_a_pas_besoin_du_filet(self, recette, modele, parcelles_connues):
        modele.side_effect = [
            _reponse(texte=self.TEXTE_DU_MODELE),
            _reponse(AppelOutil("corriger_action", {"ref": "A1", "champs": {"quantite": 2}})),
            _reponse(texte="Je corrige ta plantation de tomates."),
        ]
        resultat = interpreteur_agent.proposer(self.PHRASE, recette, None)
        assert corrections.est_correction(resultat.commande) and "filet_correction" not in resultat.outils

    def test_us262_recette_la_carte_rend_oui_decidable(self, recette, modele, parcelles_connues):
        """La proposition rangée en base, « oui » trouve quelque chose à confirmer (US-260)."""
        from app.services.agent import contexte_court
        from app.services.compagnon import propositions

        modele.side_effect = [_reponse(texte=self.TEXTE_DU_MODELE)] * 2
        resultat = interpreteur_agent.proposer(self.PHRASE, recette, None)
        rangee = propositions.proposer(recette, resultat.commande)
        court = contexte_court.construire(recette, rangee.commande, ts=rangee.ts,
                                          potager_id=recette.potager_id, code=rangee.code)
        assert court.decidable and court.prete and not court.destructrice

    @pytest.mark.parametrize("phrase, attendu", [
        ("oups, me suis trompé c'était 2 plants", ("quantite", 2, "plants")),
        ("en fait huit rangs", ("rang", 8, "rangs")),
        ("c'était 2 plants pas 5 plants", ("quantite", 2, "plants")),
        ("en fait 3 rangs et 2 plants", None),     # deux valeurs : le filet ne choisit pas
        ("en fait c'était des carottes", None),    # pas de nombre : le modèle seul
    ])
    def test_us262_recette_valeur_dite(self, phrase, attendu):
        assert corrections.valeur_dite(phrase) == attendu


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — un geste sans culture n'est jamais enregistré d'office
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5SansCulture:

    def test_us262_ca5_un_semis_sans_culture_est_refuse_par_le_service(self, test_db, potager):
        with pytest.raises(svc_evenements.CultureManquanteError):
            svc_evenements.creer_evenement_ligne(
                test_db, potager, {"action": "semis", "rang": 3}, "en fait c'était 3 rangs",
            )
        test_db.rollback()
        assert _nb_gestes(test_db, potager) == 0

    def test_us262_ca5_une_correction_ne_vide_jamais_la_culture(self, test_db, potager):
        _geste(test_db, potager)
        verdict = _valider("corriger_action", {"ref": "A1", "champs": {"culture": ""}}, "en fait rien", potager)
        assert verdict.commande is None


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — 0 second geste créé sur une phrase de correction (boucle simulée)
# ═════════════════════════════════════════════════════════════════════════════
class TestCA6PasDeSecondGeste:

    def test_us262_ca6_gherkin_la_correction_n_est_pas_aiguillee_vers_le_parseur(
            self, test_db, potager, modele, parcelles_connues):
        _geste(test_db, potager, il_y_a=timedelta(minutes=2))
        modele.side_effect = [
            _reponse(AppelOutil("saisir_geste", {})),   # le modèle croit à un geste
            _reponse(AppelOutil("corriger_action", {"ref": "A1", "champs": {"rang": 3}})),
            _reponse(texte="Je corrige ton semis de radis : 3 rangs."),
        ]
        resultat = interpreteur_agent.proposer("en fait j'ai semé 3 rangs", potager, None)
        assert resultat.aiguillage is None
        assert corrections.est_correction(resultat.commande)
        assert "Semis radis : 2 rangs → 3 rangs" in resultat.commande.commande_equivalente()
        verdict = json.loads(modele.call_args_list[1].kwargs["historique"][-1]["content"])
        assert verdict["verdict"] == "refusée" and "corriger_action" in verdict["raison"]
        assert _nb_gestes(test_db, potager) == 1

    def test_us262_ca6_un_geste_nouveau_reste_un_geste(self, test_db, potager, modele, parcelles_connues):
        _geste(test_db, potager, il_y_a=timedelta(minutes=2))
        modele.side_effect = [_reponse(AppelOutil("saisir_geste", {}))]
        resultat = interpreteur_agent.proposer("j'ai aussi semé des carottes", potager, None)
        assert resultat.aiguillage is not None and resultat.aiguillage.vers == interp.VERS_GESTE

    def test_us262_ca6_les_outils_ne_sont_offerts_qu_avec_un_geste_corrigeable(
            self, test_db, potager, modele, parcelles_connues):
        modele.return_value = _reponse(texte="Bonjour !")
        interpreteur_agent.proposer("en fait c'était 3 rangs", potager, None)
        noms = [s["function"]["name"] for s in modele.call_args.kwargs["outils"]]
        assert "corriger_action" not in noms and "annuler_action" not in noms
        _geste(test_db, potager)
        interpreteur_agent.proposer("en fait c'était 3 rangs", potager, None)
        noms = [s["function"]["name"] for s in modele.call_args.kwargs["outils"]]
        assert "corriger_action" in noms and "annuler_action" not in noms
        assert interpreteur_agent.CONSIGNE_CORRECTION in modele.call_args.kwargs["prompt_variable"]
        interpreteur_agent.proposer("annule le dernier semis", potager, None)
        noms = [s["function"]["name"] for s in modele.call_args.kwargs["outils"]]
        assert "annuler_action" in noms
        assert len(noms) <= catalogue_outils.NB_OUTILS_MAX

    def test_us262_ca6_une_correction_ne_se_melange_pas_a_une_commande(
            self, test_db, potager, modele, parcelles_connues):
        _geste(test_db, potager)
        modele.side_effect = [
            _reponse(AppelOutil("corriger_action", {"ref": "A1", "champs": {"rang": 3}}),
                     AppelOutil("modifier_parcelle", {"parcelle": "Planche Sud", "nb_rangs": 3})),
            _reponse(texte="Je corrige ton semis."),
        ]
        resultat = interpreteur_agent.proposer("en fait c'était 3 rangs", potager, None)
        assert corrections.est_correction(resultat.commande)
        verdicts = [json.loads(m["content"]) for m in modele.call_args_list[1].kwargs["historique"] if m["role"] == "tool"]
        assert verdicts[1]["verdict"] == "refusée"


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — la fiche du corpus de fonctionnement dit comment corriger par une phrase
# ═════════════════════════════════════════════════════════════════════════════
class TestCA7Fiche:

    def test_us262_ca7_la_fiche_dit_la_correction_par_une_phrase(self):
        from pathlib import Path

        fiche = (Path(__file__).resolve().parent.parent
                 / "data/connaissance/doc_app/journal-et-corrections.md").read_text(encoding="utf-8")
        assert "en fait c'était 3 rangs" in fiche
        assert "annule le dernier semis" in fiche

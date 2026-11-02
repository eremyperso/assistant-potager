"""
tests/test_agent_prioritaire.py — L'agent d'abord, et la mesure qui le compare [mesure du 01/11/2026]
=====================================================================================================
`AGENT_MODE=prioritaire` envoie toute phrase libre à l'agent avant les règles, avec le
catalogue complet et les outils de savoir ; les règles ne servent plus qu'en mode dégradé.
`tools/evaluer_dialogues.py` le rejoue (`--mode prioritaire`), sur le corpus de terrain tiré
des traces du 28/10 au 01/11/2026, et compte deux couperets que ces traces ont montrés.
Sans modèle : la passerelle est simulée.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app import config
from app.services import interpreteur_commandes as interp
from app.services.agent import catalogue_outils, interpreteur_agent, savoir
from app.services.agent.interpreteur_agent import ResultatAgent
from app.services.context import TenantContext
from app.services.interpreteur_commandes import Aiguillage, CommandeInterpretee, ReponseAgent
from llm import passerelle
from llm.passerelle import AppelOutil, ReponseOutils
import tools.evaluer_dialogues as ed

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
PARCELLES = ("Planche Nord", "Planche Sud", "Tunnel")


def _reponse(*appels: AppelOutil, texte: str = "") -> ReponseOutils:
    return ReponseOutils(texte=texte, modele="test", appel_type=passerelle.TYPE_AGENT,
                         tokens_in=900, tokens_out=50, latence_ms=400, appels=appels)


@pytest.fixture
def prioritaire(monkeypatch):
    monkeypatch.setattr(config, "AGENT_MODE", "prioritaire")


@pytest.fixture(autouse=True)
def lectures_simulees(monkeypatch):
    monkeypatch.setattr(interpreteur_agent, "noms_parcelles_du_potager", lambda ctx: PARCELLES)
    monkeypatch.setattr(interpreteur_agent, "voisin_en_base", lambda ctx: (lambda nom: None))
    monkeypatch.setattr(interpreteur_agent, "persister_reponse", lambda *a, **k: None)
    monkeypatch.setattr(savoir, "precharger", lambda ctx, releves: "")


@pytest.fixture
def modele():
    with patch.object(passerelle, "appeler_chat_outils") as faux:
        yield faux


# ═════════════════════════════════════════════════════════════════════════════
# Le réglage
# ═════════════════════════════════════════════════════════════════════════════
class TestReglage:
    def test_prioritaire_est_un_mode_connu(self):
        assert "prioritaire" in config.AGENT_MODES

    def test_prioritaire_herite_de_ce_que_actif_ouvre(self, prioritaire):
        assert interp.agent_actif()

    def test_off_n_active_pas_l_agent(self, monkeypatch):
        monkeypatch.setattr(config, "AGENT_MODE", "off")
        assert not interp.agent_actif()


# ═════════════════════════════════════════════════════════════════════════════
# L'agent avant les règles
# ═════════════════════════════════════════════════════════════════════════════
class TestAgentDAbord:
    def test_une_phrase_que_les_regles_reconnaissent_va_d_abord_a_l_agent(self, prioritaire):
        assert interp.reconnaitre_par_regles("crée la parcelle Est") is not None
        with patch.object(interpreteur_agent, "proposer",
                          return_value=ResultatAgent(disponible=True, texte="Je te propose la parcelle Est.")) as agent:
            resultat = interp.interpreter("crée la parcelle Est", CTX)
        assert agent.call_args.kwargs.get("prioritaire") is True
        assert isinstance(resultat, ReponseAgent) and resultat.texte == "Je te propose la parcelle Est."

    def test_une_question_n_est_plus_aiguillee_vers_la_cascade(self, prioritaire):
        with patch.object(interpreteur_agent, "proposer",
                          return_value=ResultatAgent(disponible=True, texte="Ton dernier semis : radis.")):
            resultat = interp.interpreter("quel est mon dernier semis ?", CTX)
        assert isinstance(resultat, ReponseAgent)

    def test_un_geste_va_au_parseur_quand_l_agent_le_dit(self, prioritaire):
        aiguillage = Aiguillage(vers=interp.VERS_GESTE, texte_origine="j'ai arrosé la planche nord")
        with patch.object(interpreteur_agent, "proposer",
                          return_value=ResultatAgent(disponible=True, aiguillage=aiguillage)):
            resultat = interp.interpreter("j'ai arrosé la planche nord", CTX)
        assert isinstance(resultat, Aiguillage) and resultat.vers == interp.VERS_GESTE

    def test_agent_indisponible_mode_degrade_par_les_regles(self, prioritaire):
        with patch.object(interpreteur_agent, "proposer",
                          return_value=ResultatAgent(disponible=False, motif="QuotaLLMDepasseError")), \
             patch.object(interp, "_appeler_modele", lambda *a, **k: None):
            resultat = interp.interpreter("crée la parcelle Est", CTX)
        assert isinstance(resultat, CommandeInterpretee)

    def test_une_commande_tapee_ne_passe_pas_par_l_agent(self, prioritaire):
        with patch.object(interpreteur_agent, "proposer") as agent:
            interp.interpreter("/parcelle lister", CTX)
        agent.assert_not_called()

    def test_le_mode_actif_garde_les_regles_d_abord(self, monkeypatch):
        monkeypatch.setattr(config, "AGENT_MODE", "actif")
        with patch.object(interpreteur_agent, "proposer") as agent:
            resultat = interp.interpreter("crée la parcelle Est", CTX)
        agent.assert_not_called()
        assert isinstance(resultat, CommandeInterpretee)


# ═════════════════════════════════════════════════════════════════════════════
# Ce que voit le modèle
# ═════════════════════════════════════════════════════════════════════════════
class TestCeQueVoitLeModele:
    def test_catalogue_complet_et_savoir_meme_sur_une_question(self, modele):
        modele.return_value = _reponse(texte="Tu as deux planches.")
        interpreteur_agent.proposer("est-ce que je peux supprimer la planche sud ?", CTX, prioritaire=True)
        envoyes = {s["function"]["name"] for s in modele.call_args.kwargs["outils"]}
        attendus = {o.nom for o in catalogue_outils.outils_projetes(catalogue_outils.PROJECTION_COMPLETE)}
        assert attendus | set(catalogue_outils.OUTILS_SAVOIR) <= envoyes

    def test_le_prompt_est_celui_du_mode_prioritaire(self, modele):
        modele.return_value = _reponse(texte="Salut !")
        interpreteur_agent.proposer("bonjour", CTX, prioritaire=True)
        arguments = modele.call_args.kwargs
        assert arguments["prompt_fixe"] == interpreteur_agent.PROMPT_FIXE_PRIORITAIRE
        assert savoir.CONSIGNE_SAVOIR not in arguments["prompt_variable"]

    def test_le_mode_actif_garde_son_prompt_mesure(self, modele):
        modele.return_value = _reponse(texte="Salut !")
        interpreteur_agent.proposer("bonjour", CTX)
        assert modele.call_args.kwargs["prompt_fixe"] == interpreteur_agent.PROMPT_FIXE

    def test_le_prompt_prioritaire_interdit_la_confirmation_en_texte(self):
        assert "Ne demande jamais une confirmation en texte" in interpreteur_agent.PROMPT_FIXE_PRIORITAIRE
        assert "/ask" not in interpreteur_agent.PROMPT_FIXE_PRIORITAIRE


# ═════════════════════════════════════════════════════════════════════════════
# La mesure : couperets tirés des traces, notation, corpus de terrain
# ═════════════════════════════════════════════════════════════════════════════
ATTENDU_TEXTE = ed.Attendu(outils=("texte",), ecriture=False)


class TestCouperetsDuTerrain:
    @pytest.mark.parametrize("texte", [
        "Je vais effacer le dernier geste enregistré dans ton carnet. Est-ce que tu veux vraiment le supprimer ?",
        "Demain il pleut. Si tu veux que je te rappelle l'événement, dis-le-moi !",
        "Tu veux que je corrige ton semis de radis avec 8 graines ? Dis-moi si c'est bon pour toi !",
    ])
    def test_une_confirmation_demandee_sans_proposition_est_un_couperet(self, texte):
        resultat = ReponseAgent(texte=texte, texte_origine="vide le geste")
        assert "promesse_sans_proposition" in ed.couperets_au_jardinier(ATTENDU_TEXTE, resultat, ed.CHEMIN_AGENT)

    def test_la_meme_phrase_devant_une_carte_en_attente_n_en_est_pas_un(self):
        resultat = ReponseAgent(texte="Tu confirmes ?", texte_origine="vas-y")
        assert ed.couperets_au_jardinier(ATTENDU_TEXTE, resultat, ed.CHEMIN_AGENT, en_attente=object()) == ()

    @pytest.mark.parametrize("texte", [
        "Il n'y a plus de geste en attente.",
        # Échanges #66 et #111 : une offre d'en dire plus, pas une écriture promise.
        "Tu as fait 2 arrosages. Si tu veux que je te détaille autre chose, dis-le-moi !",
        "Avec plaisir, Emmanuel ! Tu veux que je t'aide à noter quelque chose au potager ?",
        # Mesure du 01/11 : la question de la consigne 11, comptée à tort avant correction.
        "Quelle parcelle veux-tu supprimer parmi Planche Nord, Planche Sud ou Planche Centrale ?",
    ])
    def test_une_reponse_qui_ne_promet_rien_passe(self, texte):
        resultat = ReponseAgent(texte=texte, texte_origine="merci")
        assert ed.couperets_au_jardinier(ATTENDU_TEXTE, resultat, ed.CHEMIN_AGENT) == ()

    def test_un_salut_en_plein_dialogue_est_un_couperet(self):
        resultat = ReponseAgent(texte="Salut Emmanuel ! Que veux-tu faire ?", texte_origine="oui")
        assert "salut_en_cours" in ed.couperets_au_jardinier(ATTENDU_TEXTE, resultat, ed.CHEMIN_AGENT, en_cours=True)
        assert ed.couperets_au_jardinier(ATTENDU_TEXTE, resultat, ed.CHEMIN_AGENT) == ()


class TestNotation:
    def test_les_lectures_du_savoir_ne_sont_pas_des_ecritures(self):
        assert not any(ed.est_ecriture(nom) for nom in catalogue_outils.OUTILS_SAVOIR)

    def test_une_lecture_non_nommee_ne_masque_pas_l_appel_juge(self):
        reponses = [_reponse(AppelOutil("consulter_donnees", {"question": "q"}),
                             AppelOutil("modifier_parcelle", {"parcelle": "Tunnel", "nb_rangs": 4}))]
        attendu = ed.Attendu(outils=("modifier_parcelle",))
        assert [a.nom for a in ed.appels_juges(reponses, attendu)] == ["modifier_parcelle"]

    def test_une_lecture_nommee_reste_jugee(self):
        reponses = [_reponse(AppelOutil("chercher_connaissance", {"question": "q"}))]
        attendu = ed.Attendu(outils=("chercher_connaissance", "texte"))
        assert [a.nom for a in ed.appels_juges(reponses, attendu)] == ["chercher_connaissance"]

    def test_abandonner_puis_reproposer_c_est_corriger(self):
        reponses = [_reponse(AppelOutil("abandonner_proposition", {"id": "P1"}),
                             AppelOutil("modifier_parcelle", {"parcelle": "principal", "nb_rangs": 4}))]
        attendu = ed.Attendu(outils=("modifier_parcelle",))
        assert [a.nom for a in ed.appels_juges(reponses, attendu)] == ["modifier_parcelle"]

    def test_abandonner_seul_reste_juge(self):
        reponses = [_reponse(AppelOutil("abandonner_proposition", {"id": "P1"}))]
        attendu = ed.Attendu(outils=("modifier_parcelle",))
        assert [a.nom for a in ed.appels_juges(reponses, attendu)] == ["abandonner_proposition"]


class TestCorpusDeTerrain:
    def test_le_corpus_se_charge_et_cite_ses_echanges(self):
        dialogues = ed.charger_corpus(ed.CORPUS_TERRAIN)
        assert len(dialogues) >= 30
        assert all(d.source.startswith("terrain") for d in dialogues)

    def test_les_outils_attendus_existent(self):
        connus = ({o.nom for o in catalogue_outils.outils()} | set(catalogue_outils.OUTILS_SAVOIR)
                  | set(catalogue_outils.OUTILS_DECISION) | set(catalogue_outils.OUTILS_CORRECTION)
                  | {ed.PSEUDO_TEXTE, ed.PSEUDO_AUCUNE_ECRITURE})
        for d in ed.charger_corpus(ed.CORPUS_TERRAIN):
            for t in d.tours:
                if t.appelle_le_modele:
                    assert ed._outils_nommes(t.attendu) <= connus, (d.id, t.attendu.outils)

    def test_le_plan_prioritaire_annonce_le_volume_sans_appel(self):
        sortie = ed.plan(ed.charger_corpus(ed.CORPUS_TERRAIN), list(ed.MODELES_PRIORITAIRE), ed.MODE_PRIORITAIRE, 33)
        assert "mode prioritaire" in sortie and "potager 33" in sortie and "jetons d'entrée" in sortie

    def test_les_modeles_du_01_11_ont_leur_tarif(self):
        assert set(ed.MODELES_PRIORITAIRE) <= set(ed.TARIFS_01_11_2026["modeles"])

    def test_dry_run_prioritaire_sans_appel(self, capsys):
        assert ed.main(["--mode", "prioritaire", "--corpus", str(ed.CORPUS_TERRAIN),
                        "--potager", "33", "--utilisateur", "2", "--dry-run"]) == 0
        assert "mode prioritaire" in capsys.readouterr().out

    def test_potager_sans_utilisateur_est_refuse(self):
        with pytest.raises(SystemExit):
            ed.main(["--potager", "33", "--dry-run"])

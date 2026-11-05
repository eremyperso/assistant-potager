"""
tests/test_us281_garde_fous_apres_modele.py — Les garde-fous APRÈS le modèle, dans le validateur [US-281]
=========================================================================================================
En mode `prioritaire`, le modèle voit tout le catalogue : à « est-ce que je peux supprimer la
planche sud sans perdre mon historique ? », il proposait une suppression (mesure du 01/11/2026).
Le validateur refuse désormais ce qu'une question ou une demande incomplète ne peut pas produire :
une écriture sur une question (CA1), une carte à laquelle manque une valeur indispensable (CA2),
une désactivation non dite (CA3), la recréation d'une parcelle active (CA4). Le verdict revient
au modèle ; le jardinier ne lit jamais « refusée » (CA6). Sans modèle : la passerelle est simulée.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app import config
from app.services import interpreteur_commandes as interp
from app.services.agent import interpreteur_agent, savoir
from app.services.agent.catalogue_outils import (
    OUTIL_CREER_PARCELLE,
    OUTIL_MODIFIER_PARCELLE,
    PROJECTION_COMPLETE,
)
from app.services.agent.interpreteur_agent import Propositions, _sans_refus
from app.services.agent.projection import est_une_question
from app.services.agent.validation import (
    RAISON_QUESTION,
    ContexteValidation,
    desactivation_dite,
    valider_appel,
    valider_plan,
)
from app.services.context import TenantContext
from app.services.interpreteur_commandes import CommandeInterpretee
from llm import passerelle
from llm.passerelle import AppelOutil, ReponseOutils

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
PARCELLES = ("Planche Nord", "Planche Sud", "Planche Test", "Tunnel", "Serre", "Est")

QUESTION_SUPPRESSION = "est-ce que je peux supprimer la planche sud sans perdre mon historique ?"
RENOMMAGE_POLI = "est-ce que tu peux renommer la parcelle tunnel en serre chaude ?"
QUATRE_CREATIONS = "crée les parcelles Ouest, Centre, Est et Fraisier"


def _appel(outil: str, ident: str = "a1", /, **arguments) -> AppelOutil:
    return AppelOutil(outil, arguments, id=ident)


def _outils(*appels: AppelOutil) -> ReponseOutils:
    return ReponseOutils(texte="", modele="test", appel_type=passerelle.TYPE_AGENT,
                         tokens_in=900, tokens_out=50, latence_ms=400, appels=appels)


def _texte(texte: str) -> ReponseOutils:
    return ReponseOutils(texte=texte, modele="test", appel_type=passerelle.TYPE_AGENT)


@pytest.fixture(autouse=True)
def lectures_simulees(monkeypatch):
    monkeypatch.setattr(interpreteur_agent, "noms_parcelles_du_potager", lambda ctx: PARCELLES)
    monkeypatch.setattr(interpreteur_agent, "voisin_en_base", lambda ctx: (lambda nom: None))
    monkeypatch.setattr(interpreteur_agent, "profil_du_jardinier", lambda ctx: None)
    monkeypatch.setattr(interpreteur_agent, "persister_reponse", lambda *a, **k: None)
    monkeypatch.setattr(interpreteur_agent.actions_menees, "recentes", lambda ctx: ())
    monkeypatch.setattr(savoir, "precharger", lambda ctx, releves: "")


@pytest.fixture
def modele():
    with patch.object(passerelle, "appeler_chat_outils") as faux:
        yield faux


def _proposer(modele, phrase: str, *tours: ReponseOutils, prioritaire: bool = True):
    modele.side_effect = list(tours)
    return interpreteur_agent.proposer(phrase, CTX, prioritaire=prioritaire)


def _verdicts_lus(modele) -> list[dict]:
    """Ce que le modèle a lu en réponse à ses appels, au dernier tour."""
    historique = modele.call_args_list[-1].kwargs.get("historique", [])
    return [json.loads(m["content"]) for m in historique if m["role"] == "tool"]


def _sans_carte(resultat) -> bool:
    return resultat.commande is None and resultat.plan is None


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — Une question ne produit aucune écriture
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1Question:

    @pytest.mark.parametrize("phrase, attendu", [
        (QUESTION_SUPPRESSION, True),
        ("comment je renomme une parcelle", True),
        ("les limaces ont bouffé mes salades", True),
        (RENOMMAGE_POLI, False),
        ("peux-tu renommer la planche sud en potager ?", False),
        ("supprime la planche test", False),
        ("renomme la planche sud", False),
    ])
    def test_us281_ca1_ce_qui_est_une_question(self, phrase, attendu):
        assert est_une_question(phrase) is attendu

    def test_us281_ca1_un_constat_qui_suit_une_proposition_n_en_est_pas_une(self):
        assert not est_une_question("les limaces", texte_en_contexte="crée la planche limaces ; les limaces")

    def test_us281_ca1_gherkin_suppression_proposee_sur_une_question(self, modele):
        """Gherkin : le modèle appelle supprimer_parcelle, le validateur refuse, le jardinier lit du texte."""
        reponse = "Oui : retire-la du potager plutôt que de la supprimer, son historique reste."
        resultat = _proposer(modele, QUESTION_SUPPRESSION,
                             _outils(_appel("supprimer_parcelle", nom="Planche Sud")), _texte(reponse))
        assert _sans_carte(resultat)
        assert resultat.texte == reponse
        assert _verdicts_lus(modele) == [{"verdict": "refusée", "raison": RAISON_QUESTION}]
        assert RAISON_QUESTION in resultat.refus

    def test_us281_ca1_modification_sur_un_constat_de_probleme(self, modele):
        resultat = _proposer(modele, "les limaces ont bouffé la planche nord",
                             _outils(_appel(OUTIL_MODIFIER_PARCELLE, parcelle="Planche Nord", abri="aucun")),
                             _texte("Pose des pièges à bière le soir."))
        assert _sans_carte(resultat)

    def test_us281_ca1_un_geste_sur_une_question_ne_va_pas_au_parseur(self, modele):
        resultat = _proposer(modele, "est-ce que j'ai bien semé les carottes ?",
                             _outils(_appel("saisir_geste")), _texte("Oui, le 12 octobre."))
        assert resultat.aiguillage is None and _sans_carte(resultat)
        assert _verdicts_lus(modele)[0]["raison"] == RAISON_QUESTION

    def test_us281_ca1_la_lecture_reste_permise_sur_une_question(self, modele):
        lire = _appel(interpreteur_agent.OUTIL_LIRE, quoi="parcelles", nom="")
        with patch.object(interpreteur_agent.lecture, "lire", return_value="Planche Sud : 3 rangs"):
            resultat = _proposer(modele, "combien de rangs a la planche sud ?",
                                 _outils(lire), _texte("Elle en a 3."))
        assert resultat.texte == "Elle en a 3." and not resultat.refus

    def test_us281_ca1_le_filet_ne_propose_rien_sur_un_constat(self, modele):
        resultat = _proposer(modele, "les limaces ont bouffé la planche nord, elle a 5 rangs",
                             _texte("Les limaces adorent l'humidité."))
        assert _sans_carte(resultat)

    def test_us281_ca8_renommage_poli_reste_propose(self, modele):
        resultat = _proposer(modele, RENOMMAGE_POLI,
                             _outils(_appel("renommer_parcelle", ancien="Tunnel", nouveau="Serre chaude")),
                             _texte("Je te propose de renommer le tunnel."))
        assert resultat.commande is not None
        assert resultat.commande.forme.sous_commande == "renommer"
        assert resultat.commande.valeurs == {"ancien": "Tunnel", "nouveau": "Serre chaude"}

    def test_us281_ca8_supprime_la_planche_test_reste_proposee_bouton_seul(self, modele):
        resultat = _proposer(modele, "supprime la planche test",
                             _outils(_appel("supprimer_parcelle", nom="Planche Test")),
                             _texte("Je te propose de supprimer la planche test."))
        assert resultat.commande is not None and resultat.commande.forme.destructrice
        assert resultat.commande.valeurs == {"nom": "Planche Test"}


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — Valeur indispensable manquante : une question, jamais une carte incomplète
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2ValeurManquante:

    @pytest.mark.parametrize("prioritaire", [True, False])
    def test_us281_ca2_gherkin_renommage_sans_nouveau_nom(self, modele, prioritaire):
        """Gherkin : « renomme la planche sud » → « En quoi veux-tu la renommer ? », aucune carte."""
        resultat = _proposer(modele, "renomme la planche sud",
                             _outils(_appel("renommer_parcelle", ancien="Planche Sud", nouveau="Planche Sud")),
                             _texte("En quoi veux-tu la renommer ?"), prioritaire=prioritaire)
        assert _sans_carte(resultat)
        assert resultat.texte == "En quoi veux-tu la renommer ?"
        verdict = _verdicts_lus(modele)[0]
        assert verdict["verdict"] == "refusée" and "il manque" in verdict["raison"]
        assert "nouveau nom" in verdict["raison"]

    def test_us281_ca2_modele_muet_la_question_du_code(self, modele):
        resultat = _proposer(modele, "renomme la planche sud",
                             _outils(_appel("renommer_parcelle", ancien="Planche Sud")), _texte(""))
        assert _sans_carte(resultat)
        assert resultat.texte == "En quoi veux-tu renommer « Planche Sud » ?"

    def test_us281_ca2_creation_sans_nom(self, modele):
        resultat = _proposer(modele, "crée une parcelle",
                             _outils(_appel(OUTIL_CREER_PARCELLE)), _texte("Quel nom lui donnes-tu ?"))
        assert _sans_carte(resultat)
        assert "il manque" in _verdicts_lus(modele)[0]["raison"]

    def test_us281_ca2_rappel_sans_objet(self, modele):
        resultat = _proposer(modele, "programme un rappel pour samedi",
                             _outils(_appel("programmer_rappel", date="samedi")),
                             _texte("De quoi veux-tu que je te fasse souvenir samedi ?"))
        assert _sans_carte(resultat)
        assert "il manque" in _verdicts_lus(modele)[0]["raison"]

    def test_us281_ca2_le_modele_complete_au_tour_suivant(self, modele):
        """Le refus n'est pas une impasse : l'appel corrigé est proposé."""
        resultat = _proposer(modele, "renomme la planche sud en potager",
                             _outils(_appel("renommer_parcelle", ancien="Planche Sud")),
                             _outils(_appel("renommer_parcelle", "a2", ancien="Planche Sud", nouveau="Potager")),
                             _texte("Je te propose de la renommer en Potager."))
        assert resultat.commande is not None and resultat.commande.valeurs["nouveau"] == "Potager"


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — Désactivation : seulement si la phrase la dit
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3Desactivation:

    @pytest.mark.parametrize("phrase, attendu", [
        ("enlève la serre", False),
        ("supprime la serre", False),
        ("désactive la serre", True),
        ("archive la planche nord", True),
        ("la serre ne sert plus", True),
        ("retire-la du potager", True),
        ("mets la serre hors service", True),
    ])
    def test_us281_ca3_ce_qui_dit_de_desactiver(self, phrase, attendu):
        assert desactivation_dite(phrase) is attendu

    @pytest.mark.parametrize("prioritaire", [True, False])
    def test_us281_ca3_enleve_la_serre_devient_une_question(self, modele, prioritaire):
        resultat = _proposer(modele, "enlève la serre",
                             _outils(_appel(OUTIL_MODIFIER_PARCELLE, parcelle="Serre", actif=False)),
                             _texte(""), prioritaire=prioritaire)
        assert _sans_carte(resultat)
        assert resultat.texte.startswith("Que veux-tu faire de « Serre »")
        assert "refus" not in resultat.texte

    def test_us281_ca3_desactive_la_serre_est_propose(self, modele):
        resultat = _proposer(modele, "désactive la serre",
                             _outils(_appel(OUTIL_MODIFIER_PARCELLE, parcelle="Serre", actif=False)),
                             _texte("Je te propose de la mettre hors service."))
        assert resultat.commande is not None
        assert "actif=non" in resultat.commande.commande_equivalente()

    def test_us281_ca3_retire_la_du_potager_est_propose(self):
        verdict = valider_appel(
            _appel(OUTIL_MODIFIER_PARCELLE, parcelle="Serre", actif=False),
            ContexteValidation(texte="la serre, retire-la du potager", noms_parcelles=PARCELLES),
        )
        assert verdict.commande is not None

    def test_us281_ca3_la_remise_en_service_n_est_pas_concernee(self):
        verdict = valider_appel(
            _appel(OUTIL_MODIFIER_PARCELLE, parcelle="Serre", actif=True),
            ContexteValidation(texte="remets la serre en service", noms_parcelles=PARCELLES),
        )
        assert verdict.commande is not None


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — Une parcelle active ne se recrée pas
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4ParcelleExistante:

    def _creations(self, *noms: str) -> tuple[AppelOutil, ...]:
        return tuple(_appel(OUTIL_CREER_PARCELLE, f"c{rang}", nom=nom) for rang, nom in enumerate(noms))

    def test_us281_ca4_creation_seule_refusee(self):
        verdict = valider_appel(_appel(OUTIL_CREER_PARCELLE, nom="est"),
                                ContexteValidation(texte="crée la parcelle est", noms_parcelles=PARCELLES))
        assert verdict.commande is None and verdict.precision.startswith("La parcelle « Est » existe déjà")

    def test_us281_ca4_plan_de_quatre_creations_refuse(self):
        verdict = valider_plan(self._creations("Ouest", "Centre", "Est", "Fraisier"),
                               ContexteValidation(texte=QUATRE_CREATIONS, noms_parcelles=PARCELLES))
        assert verdict.plan is None
        assert "« Est » existe déjà" in verdict.precision

    @pytest.mark.parametrize("prioritaire", [True, False])
    def test_us281_ca4_le_modele_lit_la_raison_et_propose_le_reste(self, modele, prioritaire):
        texte = "Est existe déjà : je te propose les trois autres."
        resultat = _proposer(modele, QUATRE_CREATIONS,
                             _outils(*self._creations("Ouest", "Centre", "Est", "Fraisier")),
                             _texte(texte), prioritaire=prioritaire)
        assert resultat.plan is not None
        assert [e.valeurs["nom"] for e in resultat.plan.etapes] == ["Ouest", "Centre", "Fraisier"]
        assert resultat.plan.deja_faites == ()
        refus = [v for v in _verdicts_lus(modele) if v["verdict"] == "refusée"]
        assert len(refus) == 1 and "« Est » existe déjà" in refus[0]["raison"]
        assert resultat.texte == texte

    def test_us281_ca4_correctif_du_28_10_creation_avec_caracteristiques_devient_modification(self):
        verdict = valider_plan(
            (_appel(OUTIL_CREER_PARCELLE, nom="Planche Nord", nb_rangs=5),),
            ContexteValidation(texte="ma planche nord a 5 rangs", noms_parcelles=PARCELLES),
        )
        assert verdict.plan is not None
        assert [e.commande_equivalente() for e in verdict.plan.etapes] == ["/parcelle modifier Planche Nord rangs=5"]

    def test_us281_ca4_une_parcelle_inactive_peut_etre_recreee(self):
        """Seules les parcelles ACTIVES sont dans `noms_parcelles` (noms_parcelles_du_potager)."""
        verdict = valider_appel(_appel(OUTIL_CREER_PARCELLE, nom="Fraisier"),
                                ContexteValidation(texte="crée la parcelle fraisier", noms_parcelles=PARCELLES))
        assert verdict.commande is not None


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — Les deux modes
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5Modes:

    def test_us281_ca5_en_actif_la_projection_reste_gardee(self, modele):
        resultat = _proposer(modele, QUESTION_SUPPRESSION,
                             _outils(_appel("supprimer_parcelle", nom="Planche Sud")),
                             _texte("Oui, retire-la du potager."), prioritaire=False)
        envoyes = {s["function"]["name"] for s in modele.call_args_list[0].kwargs["outils"]}
        assert "supprimer_parcelle" not in envoyes
        assert _sans_carte(resultat)
        assert _verdicts_lus(modele)[0]["raison"] == "outil indisponible pour cette phrase"

    def test_us281_ca5_le_validateur_garde_la_question_quel_que_soit_le_catalogue(self):
        """En `actif`, un catalogue complet (une question mal projetée) ne laisse rien passer non plus."""
        propositions = Propositions(
            ContexteValidation(texte=QUESTION_SUPPRESSION, noms_parcelles=PARCELLES),
            {"supprimer_parcelle"}, projection=PROJECTION_COMPLETE,
        )
        contenus = propositions.juger([_appel("supprimer_parcelle", nom="Planche Sud")], CTX)
        assert json.loads(contenus[0])["raison"] == RAISON_QUESTION
        assert propositions.proposition is None

    def test_us281_ca8_la_planche_nord_a_5_rangs_reste_aux_regles_en_actif(self, monkeypatch):
        monkeypatch.setattr(config, "AGENT_MODE", "actif")
        with patch.object(interpreteur_agent, "proposer") as agent:
            resultat = interp.interpreter("la planche nord a 5 rangs", CTX)
        agent.assert_not_called()
        assert isinstance(resultat, CommandeInterpretee)
        assert resultat.commande_equivalente().endswith("rangs=5")


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — Le refus revient au modèle, jamais au jardinier
# ═════════════════════════════════════════════════════════════════════════════
class TestCA6Verdict:

    def test_us281_ca6_le_mot_refusee_n_est_jamais_lu(self, modele):
        resultat = _proposer(modele, QUESTION_SUPPRESSION,
                             _outils(_appel("supprimer_parcelle", nom="Planche Sud")),
                             _texte("Ma proposition a été refusée. Oui, retire-la plutôt du potager."))
        assert resultat.texte == "Oui, retire-la plutôt du potager."

    def test_us281_ca6_la_raison_brute_recopiee_est_retiree(self):
        raison = "il manque une valeur indispensable — nouveau nom de la parcelle : pose la question"
        texte = _sans_refus("Il manque une valeur indispensable — nouveau nom. En quoi la renommer ?",
                            [raison], [])
        assert texte == "En quoi la renommer ?"

    def test_us281_ca6_une_raison_qui_est_une_question_peut_etre_reprise(self):
        question = "La parcelle « Est » existe déjà : je ne la recrée pas."
        assert _sans_refus(question, [question], [question]) == question

    def test_us281_ca6_sans_refus_le_texte_est_intact(self):
        assert _sans_refus("Les tomates refusent de mûrir ? C'est le froid.", [], []) == \
            "Les tomates refusent de mûrir ? C'est le froid."

    def test_us281_ca6_tout_retire_la_question_du_code_prend_le_relais(self, modele):
        resultat = _proposer(modele, "renomme la planche sud",
                             _outils(_appel("renommer_parcelle", ancien="Planche Sud")),
                             _texte("Appel refusé."))
        assert resultat.texte == "En quoi veux-tu renommer « Planche Sud » ?"

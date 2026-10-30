"""
tests/test_us257_compagnon_repond_en_texte.py — Le compagnon répond en texte [US-257]
====================================================================================
L'agent passe en boucle conversationnelle (`tool_choice="auto"`) : il répond en
texte, pose une vraie question quand il doute, dit ce qu'il ne sait pas faire,
lit le verdict du validateur et se corrige ; un contrôle déterministe retire
toute annonce d'action non exécutée.

Aucun appel réseau : la passerelle est simulée (`modele`), le bot est piloté
par des `MagicMock`/`AsyncMock`, la base est SQLite en mémoire. Ces tests
vérifient la boucle et ses garde-fous, pas la compréhension : celle-ci se mesure
sur le vrai modèle (`tools/evaluer_dialogues.py`, CA8).
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import sessionmaker

from app import config
from app.bot import interpretation as bot_interpretation
from app.services import interpreteur_commandes as interp
from app.services.agent import catalogue_outils, contexte_court, interpreteur_agent
from app.services.agent.validation import demandes_de_la_phrase, demandes_non_reprises
from app.services.context import TenantContext
from database.models import RoutageLog
from llm import passerelle
from llm.passerelle import AppelOutil, ReponseOutils

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
PARCELLES = ("Serre extérieure", "Planche Nord", "Planche Sud", "Tunnel")
INC018 = "crée la planche Est 8 m avec 4 rangs et mets la serre extérieure en pépinière froide"


def _reponse(*appels: AppelOutil, texte: str = "", statut: str = passerelle.STATUT_OK) -> ReponseOutils:
    return ReponseOutils(
        texte=texte, modele="test", appel_type=passerelle.TYPE_AGENT,
        tokens_in=900, tokens_out=50, latence_ms=400, appels=appels, statut=statut,
    )


def _texte(texte: str) -> ReponseOutils:
    return _reponse(texte=texte)


def _appel(outil: str, ident: str = "", **arguments) -> AppelOutil:
    return AppelOutil(outil, arguments, id=ident)


def _contenus_outils(appel_mock, rang: int) -> list[dict]:
    """Les messages `tool` reçus par le modèle au `rang`-ième appel (à partir de 0)."""
    historique = appel_mock.call_args_list[rang].kwargs.get("historique") or []
    return [json.loads(m["content"]) for m in historique if m["role"] == "tool"]


@pytest.fixture
def agent_actif(monkeypatch):
    monkeypatch.setattr(config, "AGENT_MODE", "actif")


@pytest.fixture
def parcelles_connues(monkeypatch):
    monkeypatch.setattr(interpreteur_agent, "noms_parcelles_du_potager", lambda ctx: PARCELLES)
    monkeypatch.setattr(interpreteur_agent, "voisin_en_base", lambda ctx: (lambda nom: None))
    monkeypatch.setattr(interp, "_noms_de_parcelle_masques", lambda normalise, ctx: normalise)


@pytest.fixture
def modele():
    with patch.object(passerelle, "appeler_chat_outils") as faux:
        yield faux


@pytest.fixture
def sans_journal(monkeypatch):
    journal = MagicMock()
    monkeypatch.setattr(interpreteur_agent, "persister_reponse", journal)
    return journal


@pytest.fixture
def session_de_test(test_db, test_engine, monkeypatch):
    fabrique = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    monkeypatch.setattr("database.db.SessionLocal", fabrique)
    return test_db


@pytest.fixture(autouse=True)
def _sans_accueil(monkeypatch):
    """[US-258] L'accueil du premier échange a ses propres tests (test_us258_profil_echange)."""
    monkeypatch.setattr(bot_interpretation, "accueil_premier_contact", AsyncMock())


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — une réponse en texte libre, sans outil
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1TexteLibre:

    def test_us257_ca1_l_agent_est_appele_en_tool_choice_auto(self, modele, parcelles_connues):
        modele.return_value = _texte("Avec plaisir, bonne journée au jardin !")
        interpreteur_agent.proposer("merci", CTX)
        assert modele.call_args.kwargs["tool_choice"] == "auto"

    @pytest.mark.parametrize("phrase", ["merci", "bonjour", "bonne journée"])
    def test_us257_ca1_une_phrase_simple_recoit_un_texte_sans_outil(
        self, agent_actif, modele, parcelles_connues, sans_journal, phrase,
    ):
        modele.return_value = _texte("Avec plaisir. Bonne journée au jardin !")
        resultat = interp.interpreter(phrase, CTX)
        assert isinstance(resultat, interp.ReponseAgent)
        assert resultat.texte == "Avec plaisir. Bonne journée au jardin !"
        assert resultat.proposition is None and resultat.outils == ()
        assert modele.call_count == 1

    def test_us257_ca1_une_conversation_simple_n_ecrit_rien_au_journal(
        self, session_de_test, modele, parcelles_connues,
    ):
        modele.return_value = _texte("Avec plaisir !")
        resultat = interpreteur_agent.proposer("merci", CTX)
        interpreteur_agent.persister_reponse(CTX, "merci", resultat)
        assert session_de_test.query(RoutageLog).count() == 0

    @pytest.mark.asyncio
    async def test_us257_ca1_le_bot_envoie_le_texte_tel_quel(self):
        update = MagicMock()
        update.effective_user.id = 7
        update.message.reply_text = AsyncMock()
        update.callback_query = None
        reponse = interp.ReponseAgent(texte="Avec plaisir_ !", texte_origine="merci")
        with patch.object(bot_interpretation, "current_context", return_value=CTX),                 patch.object(bot_interpretation, "accueil_premier_contact", new=AsyncMock()):  # [US-258]
            pris = await bot_interpretation._traiter_commande_interpretee(update, MagicMock(), reponse)
        assert pris is True
        update.message.reply_text.assert_awaited_once_with("Avec plaisir_ !")

    @pytest.mark.asyncio
    async def test_us257_ca1_en_vocal_le_message_d_attente_est_edite(self):
        update = MagicMock()
        update.callback_query = None
        attente = AsyncMock()
        reponse = interp.ReponseAgent(texte="Bonjour !", texte_origine="bonjour")
        with patch.object(bot_interpretation, "current_context", return_value=CTX),                 patch.object(bot_interpretation, "accueil_premier_contact", new=AsyncMock()):  # [US-258]
            await bot_interpretation._traiter_commande_interpretee(update, MagicMock(), reponse, msg=attente)
        attente.edit_text.assert_awaited_once_with("Bonjour !")


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — une vraie question ; les outils d'aiguillage cèdent la place au texte
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2VraieQuestion:

    def test_us257_ca2_les_outils_d_aiguillage_sont_retires(self):
        noms = {outil.nom for outil in catalogue_outils.outils()}
        assert not noms & {"poser_question", "demander_precision", "hors_perimetre"}
        assert catalogue_outils.OUTIL_MANQUE_CATALOGUE in noms
        assert catalogue_outils.OUTILS_TERMINAUX == ("saisir_geste",)

    def test_us257_ca2_manque_catalogue_est_dans_toutes_les_projections(self):
        for projection in catalogue_outils.PROJECTIONS:
            noms = {o.nom for o in catalogue_outils.outils_projetes(projection)}
            assert catalogue_outils.OUTIL_MANQUE_CATALOGUE in noms

    def test_us257_ca2_le_catalogue_reste_coherent(self):
        assert catalogue_outils.controler_parite_outils() == []

    def test_us257_ca2_le_prompt_ne_cite_plus_les_outils_retires(self):
        prompt = interpreteur_agent.PROMPT_FIXE
        assert "poser_question" not in prompt and "demander_precision" not in prompt
        assert "hors_perimetre" not in prompt and "manque_catalogue" in prompt
        assert "nomme les choix" in prompt

    def test_us257_ca2_une_question_redigee_est_rendue_telle_quelle(
        self, agent_actif, modele, parcelles_connues, sans_journal,
    ):
        modele.return_value = _texte("Tu as trois planches : Nord, Sud et Est. Laquelle veux-tu supprimer ?")
        resultat = interp.interpreter("supprime la planche", CTX)
        assert isinstance(resultat, interp.ReponseAgent)
        assert resultat.proposition is None
        assert "Laquelle" in resultat.texte

    def test_us257_ca2_supprime_la_planche_nomme_les_planches_existantes(
        self, agent_actif, modele, parcelles_connues, sans_journal,
    ):
        """Gherkin : le validateur refuse, le modèle lit les choix et les nomme."""
        modele.side_effect = [
            _reponse(_appel("supprimer_parcelle", "a1", nom="planche")),
            _texte("Laquelle veux-tu supprimer : la Planche Nord ou la Planche Sud ?"),
        ]
        resultat = interp.interpreter("supprime la planche", CTX)
        verdict = _contenus_outils(modele, 1)[0]
        assert verdict["verdict"] == "refusée"
        assert "Planche Nord" in verdict["raison"] and "Planche Sud" in verdict["raison"]
        assert resultat.proposition is None
        assert "Planche Nord" in resultat.texte and "Planche Sud" in resultat.texte

    def test_us257_ca2_sans_texte_la_question_du_validateur_est_posee(
        self, modele, parcelles_connues,
    ):
        modele.side_effect = [_reponse(_appel("supprimer_parcelle", "a1", nom="planche")), _texte("")]
        resultat = interpreteur_agent.proposer("supprime la planche", CTX)
        assert resultat.disponible and resultat.proposition is None
        assert "Planche Nord" in resultat.texte and "Planche Sud" in resultat.texte

    def test_us257_ca2_manque_catalogue_porte_la_demande_et_le_texte(
        self, agent_actif, modele, parcelles_connues, sans_journal,
    ):
        modele.side_effect = [
            _reponse(_appel("manque_catalogue", "a1", demande="export Excel")),
            _texte("Je ne sais pas encore exporter vers Excel. Je peux te résumer ta saison."),
        ]
        resultat = interp.interpreter("exporte-moi tout l'historique en Excel", CTX)
        assert resultat.manque_catalogue == "export Excel"
        assert "Excel" in resultat.texte and resultat.proposition is None
        assert _contenus_outils(modele, 1)[0]["effet"] == "aucun"

    def test_us257_ca2_manque_catalogue_est_journalise_comme_demande(
        self, session_de_test, modele, parcelles_connues,
    ):
        modele.side_effect = [
            _reponse(_appel("manque_catalogue", "a1", demande="rappel daté")),
            _texte("Je ne sais pas encore régler un rappel."),
        ]
        resultat = interpreteur_agent.proposer("règle un rappel demain à 8 heures", CTX)
        interpreteur_agent.persister_reponse(CTX, "règle un rappel demain à 8 heures", resultat)
        ligne = session_de_test.query(RoutageLog).one()
        assert ligne.issue_interpretation == interp.ISSUE_HORS_PERIMETRE
        assert ligne.outils_agent == "manque_catalogue"

    def test_us257_ca2_un_refus_sans_proposition_est_journalise_en_precision(
        self, session_de_test, modele, parcelles_connues,
    ):
        modele.side_effect = [_reponse(_appel("supprimer_parcelle", "a1", nom="planche")),
                              _texte("Laquelle ?")]
        resultat = interpreteur_agent.proposer("supprime la planche", CTX)
        interpreteur_agent.persister_reponse(CTX, "supprime la planche", resultat)
        assert session_de_test.query(RoutageLog).one().issue_interpretation == interp.ISSUE_PRECISION

    def test_us257_ca2_j_ai_note_ta_demande_est_vrai_apres_manque_catalogue(self, modele, parcelles_connues):
        modele.side_effect = [
            _reponse(_appel("manque_catalogue", "a1", demande="export Excel")),
            _texte("Je ne sais pas encore le faire ; j'ai noté ta demande pour la suite."),
        ]
        resultat = interpreteur_agent.proposer("exporte en Excel", CTX)
        assert "j'ai noté ta demande" in resultat.texte


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — le verdict revient au modèle, qui se corrige ; la boucle est bornée
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3VerdictRenvoye:

    def test_us257_ca3_une_proposition_valide_est_annoncee_proposee(self, modele, parcelles_connues):
        modele.side_effect = [
            _reponse(_appel("modifier_parcelle", "a1", parcelle="Tunnel", nb_rangs=4)),
            _texte("Je te propose de passer le Tunnel à 4 rangs."),
        ]
        resultat = interpreteur_agent.proposer("mets le tunnel à 4 rangs", CTX)
        verdict = _contenus_outils(modele, 1)[0]
        assert verdict["verdict"].startswith("proposée")
        assert verdict["commande"] == resultat.commande.commande_equivalente()
        assert verdict["commande"].startswith("/parcelle modifier Tunnel") and verdict["commande"].endswith("=4")
        assert resultat.texte == "Je te propose de passer le Tunnel à 4 rangs."

    def test_us257_ca3_un_refus_est_lu_puis_corrige(self, modele, parcelles_connues):
        """« 6 rangs » inventé : refusé, puis corrigé par le modèle dans la même boucle."""
        modele.side_effect = [
            _reponse(_appel("modifier_parcelle", "a1", parcelle="Tunnel", nb_rangs=6)),
            _reponse(_appel("modifier_parcelle", "a2", parcelle="Tunnel", nb_rangs=4)),
            _texte("Je te propose 4 rangs pour le Tunnel."),
        ]
        resultat = interpreteur_agent.proposer("mets le tunnel à 4 rangs", CTX)
        assert _contenus_outils(modele, 1)[0]["verdict"] == "refusée"
        assert resultat.commande.valeurs["modification"].endswith("=4")
        assert resultat.refus  # la trace du refus reste au journal

    def test_us257_ca3_un_appel_sur_la_meme_cible_complete_au_lieu_de_doubler(self, modele, parcelles_connues):
        modele.side_effect = [
            _reponse(_appel("modifier_parcelle", "a1", parcelle="Tunnel", nb_rangs=4)),
            _reponse(_appel("modifier_parcelle", "a2", parcelle="Tunnel", longueur_m=8)),
            _texte("Je te propose 4 rangs et 8 m pour le Tunnel."),
        ]
        resultat = interpreteur_agent.proposer("mets le tunnel à 4 rangs et 8 m de long", CTX)
        assert resultat.plan is None
        modifications = resultat.commande.valeurs["modification"].split()
        assert len(modifications) == 2 and {m[-2:] for m in modifications} == {"=4", "=8"}

    def test_us257_ca3_la_boucle_est_bornee_puis_redigee_sans_outil(self, monkeypatch, modele, parcelles_connues):
        monkeypatch.setattr(config, "AGENT_MAX_TOURS", 3)
        lecture = _reponse(_appel("lire", "l1", quoi="parcelles"))
        modele.side_effect = [lecture, lecture, lecture, _texte("Tes parcelles sont listées.")]
        with patch.object(interpreteur_agent.lecture, "lire", return_value='{"donnees": []}'):
            resultat = interpreteur_agent.proposer("parle-moi de mes parcelles", CTX)
        assert modele.call_count == 4
        assert [c.kwargs["tool_choice"] for c in modele.call_args_list] == ["auto", "auto", "auto", "none"]
        assert resultat.texte == "Tes parcelles sont listées."

    def test_us257_ca3_le_resultat_d_une_lecture_est_rendu_au_modele(self, modele, parcelles_connues):
        modele.side_effect = [_reponse(_appel("lire", "l1", quoi="parcelles")), _texte("Tu as 4 parcelles.")]
        with patch.object(interpreteur_agent.lecture, "lire", return_value='{"donnees": [{"nom": "Tunnel"}]}'):
            resultat = interpreteur_agent.proposer("combien j'ai de parcelles", CTX)
        assert _contenus_outils(modele, 1) == [{"donnees": [{"nom": "Tunnel"}]}]
        assert resultat.texte == "Tu as 4 parcelles."

    def test_us257_ca3_un_outil_hors_projection_est_refuse(self, modele, parcelles_connues):
        """« mets… » ne voit pas la suppression (US-276) : l'appel est refusé, rien n'est proposé."""
        modele.side_effect = [_reponse(_appel("supprimer_parcelle", "a1", nom="Tunnel")), _texte("D'accord.")]
        resultat = interpreteur_agent.proposer("mets le tunnel en jachère", CTX)
        assert _contenus_outils(modele, 1)[0]["raison"] == "outil indisponible pour cette phrase"
        assert resultat.proposition is None

    def test_us257_ca3_une_panne_au_premier_tour_rend_l_agent_indisponible(self, modele, parcelles_connues):
        modele.side_effect = passerelle.QuotaLLMDepasseError("quota")
        resultat = interpreteur_agent.proposer("crée la planche est", CTX)
        assert resultat.disponible is False

    def test_us257_ca3_une_panne_au_second_tour_garde_la_proposition(self, modele, parcelles_connues):
        modele.side_effect = [
            _reponse(_appel("creer_parcelle", "a1", nom="planche est")),
            passerelle.QuotaLLMDepasseError("quota"),
        ]
        resultat = interpreteur_agent.proposer("crée la planche est", CTX)
        assert resultat.disponible and resultat.texte == ""
        assert resultat.commande.commande_equivalente() == "/parcelle ajouter planche est"

    def test_us257_ca3_une_reponse_vide_sans_rien_a_proposer_rend_la_main(
        self, agent_actif, monkeypatch, modele, parcelles_connues, sans_journal,
    ):
        """Le modèle répond sans rien dire : jamais un message vide, jamais un autre modèle."""
        ancien_repli = MagicMock()
        monkeypatch.setattr(interp, "_appeler_modele", ancien_repli)
        modele.return_value = _texte("")
        assert interpreteur_agent.proposer("hmm", CTX).motif == interpreteur_agent.MOTIF_REPONSE_VIDE
        assert interp.interpreter("hmm", CTX) is None
        demande = interp.interpreter("crée la planche est", CTX)
        assert isinstance(demande, interp.Aiguillage) and demande.vers == interp.VERS_NON_COMPRIS
        ancien_repli.assert_not_called()

    def test_us257_ca3_un_geste_rapporte_va_au_parseur(self, modele, parcelles_connues):
        modele.return_value = _reponse(_appel("saisir_geste", "g1"))
        resultat = interpreteur_agent.proposer("j'ai semé des radis", CTX)
        assert resultat.aiguillage.vers == interp.VERS_GESTE
        assert modele.call_count == 1


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — toutes les actions de la phrase (US-250)
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4PlusieursActions:

    def test_us257_ca4_la_phrase_est_decoupee_en_demandes(self):
        assert demandes_de_la_phrase(INC018, PARCELLES) == [
            "cree la planche est 8 m avec 4 rangs",
            "et mets la serre exterieure en pepiniere froide",
        ]
        assert demandes_de_la_phrase("la planche nord n'a plus d'abri", PARCELLES) == [
            "la planche nord n a plus d abri",
        ]

    def test_us257_ca4_un_nom_de_parcelle_avec_et_ne_coupe_rien(self):
        assert len(demandes_de_la_phrase("mets le carré est et ouest en pépinière", ("Carré est et ouest",))) == 1

    def test_us257_ca4_seul_le_surplus_de_demandes_est_non_repris(self):
        creer, modifier = _appel("creer_parcelle"), _appel("modifier_parcelle")
        assert demandes_non_reprises(INC018, [creer], PARCELLES) == [
            "et mets la serre exterieure en pepiniere froide",
        ]
        assert demandes_non_reprises(INC018, [creer, modifier], PARCELLES) == []

    def test_us257_ca4_un_verbe_a_un_seul_outil_doit_etre_repris(self):
        """« supprime » sans appel de suppression : le mot d'action n'est pas repris."""
        phrase = "renomme la planche sud en planche des courges et supprime la planche nord"
        deux_renommages = [_appel("renommer_parcelle"), _appel("renommer_parcelle")]
        assert demandes_non_reprises(phrase, deux_renommages, PARCELLES) == ["et supprime la planche nord"]
        assert demandes_non_reprises(phrase, [_appel("renommer_parcelle"), _appel("supprimer_parcelle")],
                                     PARCELLES) == []
        assert demandes_non_reprises("crée la planche est", [], PARCELLES) == ["cree la planche est"]

    def test_us257_ca4_un_verbe_a_plusieurs_outils_ne_se_verifie_qu_au_compte(self):
        """« ajoute 2 rangs » modifie une parcelle : il n'exige pas `creer_parcelle`."""
        assert demandes_non_reprises("ajoute 2 rangs à la planche nord", [_appel("modifier_parcelle")],
                                     PARCELLES) == []

    def test_us257_ca4_une_demande_d_agir_sans_appel_redonne_un_tour(self, modele, parcelles_connues):
        modele.side_effect = [
            _texte("D'accord, dis-moi ses dimensions."),
            _reponse(_appel("creer_parcelle", "a1", nom="planche est")),
            _texte("Je te propose la planche Est."),
        ]
        resultat = interpreteur_agent.proposer("crée la planche est", CTX)
        relance = modele.call_args_list[1].kwargs["historique"][-1]
        assert relance["role"] == "user" and "« cree la planche est »" in relance["content"]
        assert resultat.commande.commande_equivalente() == "/parcelle ajouter planche est"

    def test_us257_ca4_une_phrase_sans_verbe_d_action_n_est_pas_relancee(self, modele, parcelles_connues):
        modele.return_value = _texte("Avec plaisir !")
        interpreteur_agent.proposer("merci beaucoup", CTX)
        assert modele.call_count == 1

    def test_us257_ca4_la_relance_sans_appel_n_est_donnee_qu_une_fois(self, modele, parcelles_connues):
        modele.return_value = _texte("Laquelle veux-tu supprimer : Nord ou Sud ?")
        resultat = interpreteur_agent.proposer("supprime la planche", CTX)
        assert modele.call_count == 2
        assert resultat.texte == "Laquelle veux-tu supprimer : Nord ou Sud ?"

    @staticmethod
    def _en_attente(texte: str = "passe le tunnel à 3 rangs"):
        commande = interp._construire_commande(
            interp.FORMES_PAR_CLE[("parcelle", "modifier")], {"nom": "Tunnel", "modification": "rangs=3"},
            interp.ORIGINE_AGENT, 1.0, texte)
        return contexte_court.construire(CTX, commande, 0.0, CTX.potager_id, maintenant=1.0)

    def test_us257_ca4_une_suite_qui_oublie_la_proposition_en_attente_redonne_un_tour(
        self, modele, parcelles_connues,
    ):
        """« et la planche sud aussi » ne doit pas remplacer la proposition par la seule suite."""
        modele.side_effect = [
            _reponse(_appel("modifier_parcelle", "a1", parcelle="Planche Sud", nb_rangs=3)),
            _reponse(_appel("modifier_parcelle", "a2", parcelle="Tunnel", nb_rangs=3)),
            _texte("Je te propose les deux."),
        ]
        resultat = interpreteur_agent.proposer("et la planche sud aussi", CTX, self._en_attente())
        signal = _contenus_outils(modele, 1)[0]["non_repris_dans_tes_appels"]
        assert signal[0].startswith("la proposition en attente") and "Tunnel" in signal[0]
        assert len(resultat.plan.etapes) == 2

    def test_us257_ca4_une_correction_chiffree_sans_appel_redonne_un_tour(self, modele, parcelles_connues):
        modele.side_effect = [
            _texte("La proposition reste en attente."),
            _reponse(_appel("modifier_parcelle", "a1", parcelle="Tunnel", nb_rangs=4)),
            _texte("Corrigé : 4 rangs."),
        ]
        resultat = interpreteur_agent.proposer("non 4 rangs", CTX, self._en_attente())
        assert modele.call_args_list[1].kwargs["historique"][-1]["role"] == "user"
        assert resultat.commande.valeurs["modification"].endswith("=4")

    def test_us257_ca4_une_correction_ne_signale_pas_le_nombre_qu_elle_remplace(self, modele, parcelles_connues):
        """« non 4 rangs » sur « … 3 rangs » : le 3 est remplacé, pas oublié."""
        commande = interp._construire_commande(
            interp.FORMES_PAR_CLE[("parcelle", "modifier")], {"nom": "Tunnel", "modification": "rangs=3"},
            interp.ORIGINE_AGENT, 1.0, "passe le tunnel à 3 rangs")
        court = contexte_court.construire(CTX, commande, 0.0, CTX.potager_id, maintenant=1.0)
        modele.side_effect = [_reponse(_appel("modifier_parcelle", "a1", parcelle="Tunnel", nb_rangs=4)),
                              _texte("Corrigé : 4 rangs.")]
        resultat = interpreteur_agent.proposer("non 4 rangs", CTX, court)
        assert "non_repris_dans_tes_appels" not in _contenus_outils(modele, 1)[0]
        assert resultat.commande.valeurs["modification"].endswith("=4")

    def test_us257_ca4_deux_actions_donnent_un_plan_complet(self, modele, parcelles_connues):
        """Gherkin : deux propositions présentées à confirmer, aucune annonce."""
        modele.side_effect = [
            _reponse(
                _appel("creer_parcelle", "a1", nom="planche Est", longueur_m=8, nb_rangs=4),
                _appel("modifier_parcelle", "a2", parcelle="Serre extérieure", type_pepiniere="froide"),
            ),
            _texte("Je te propose de créer la planche Est et de passer la Serre en pépinière froide."),
        ]
        resultat = interpreteur_agent.proposer(INC018, CTX)
        etapes = [e.commande_equivalente() for e in resultat.plan.etapes]
        assert etapes == [
            "/parcelle ajouter planche Est",
            "/parcelle modifier planche Est longueur=8 rangs=4",
            "/parcelle modifier Serre extérieure pepiniere=froide",
        ]
        assert not interpreteur_agent.annonce_une_action(resultat.texte)
        assert "non_repris_dans_tes_appels" not in _contenus_outils(modele, 1)[-1]

    def test_us257_ca4_une_action_oubliee_redonne_un_tour(self, modele, parcelles_connues):
        modele.side_effect = [
            _reponse(_appel("creer_parcelle", "a1", nom="planche Est", longueur_m=8, nb_rangs=4)),
            _reponse(_appel("modifier_parcelle", "a2", parcelle="Serre extérieure", type_pepiniere="froide")),
            _texte("Je te propose les deux."),
        ]
        resultat = interpreteur_agent.proposer(INC018, CTX)
        signal = _contenus_outils(modele, 1)[0]["non_repris_dans_tes_appels"]
        assert signal == ["et mets la serre exterieure en pepiniere froide"]
        assert len(resultat.plan.etapes) == 3  # création, ses caractéristiques, la serre

    def test_us257_ca4_un_nombre_oublie_redonne_un_tour(self, modele, parcelles_connues):
        modele.side_effect = [
            _reponse(_appel("creer_parcelle", "a1", nom="planche Est", longueur_m=8)),
            _texte("Je te propose la planche Est, 8 m."),
        ]
        interpreteur_agent.proposer("crée la planche Est 8 m avec 4 rangs", CTX)
        assert _contenus_outils(modele, 1)[0]["non_repris_dans_tes_appels"] == ["4"]

    def test_us257_ca4_le_signal_n_est_donne_qu_une_fois(self, modele, parcelles_connues):
        modele.side_effect = [
            _reponse(_appel("creer_parcelle", "a1", nom="planche Est")),
            _reponse(_appel("creer_parcelle", "a2", nom="planche Est")),
            _texte("Je te propose la planche Est."),
        ]
        interpreteur_agent.proposer(INC018, CTX)
        assert "non_repris_dans_tes_appels" in _contenus_outils(modele, 1)[0]
        assert "non_repris_dans_tes_appels" not in _contenus_outils(modele, 2)[-1]


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — aucune annonce d'une action non exécutée
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5Annonces:

    @pytest.mark.parametrize("texte", [
        "C'est fait !", "c'est fait, la planche existe", "J'ai noté ton semis.", "J'ai créé la planche Est.",
        "La planche Est a été créée.", "Voilà, c'est enregistré.", "C'est noté !", "J'ai bien supprimé la serre.",
        "Je viens de passer la serre en pépinière froide.", "La serre est bien modifiée.", "J’ai ajouté 4 rangs.",
    ])
    def test_us257_ca5_une_annonce_est_reconnue(self, texte):
        assert interpreteur_agent.annonce_une_action(texte)

    @pytest.mark.parametrize("texte", [
        "Je te propose de créer la planche Est, 8 m, 4 rangs.",
        "La planche sera créée quand tu auras confirmé.",
        "Tu veux que je crée la planche Est ?",
        "Avec plaisir, bonne journée !",
        "Laquelle veux-tu supprimer : Nord ou Sud ?",
        "Tu as semé des radis mardi sur la planche Sud.",
    ])
    def test_us257_ca5_une_proposition_n_est_pas_une_annonce(self, texte):
        assert not interpreteur_agent.annonce_une_action(texte)

    def test_us257_ca5_devant_une_proposition_le_recapitulatif_parle_seul(self, modele, parcelles_connues):
        modele.side_effect = [
            _reponse(_appel("creer_parcelle", "a1", nom="planche est")),
            _texte("C'est fait, la planche Est est créée !"),
        ]
        resultat = interpreteur_agent.proposer("crée la planche est", CTX)
        assert resultat.texte == ""
        assert resultat.commande.commande_equivalente() == "/parcelle ajouter planche est"

    def test_us257_ca5_sans_proposition_l_annonce_est_renvoyee_au_modele(self, modele, parcelles_connues):
        modele.side_effect = [_texte("C'est fait !"), _texte("Je n'ai rien fait : que veux-tu créer ?")]
        resultat = interpreteur_agent.proposer("fais-le", CTX)
        correction = modele.call_args_list[1].kwargs["historique"][-1]
        assert correction == {"role": "user", "content": interpreteur_agent.CORRECTION_ANNONCE}
        assert resultat.texte == "Je n'ai rien fait : que veux-tu créer ?"

    def test_us257_ca5_une_annonce_obstinee_est_remplacee_par_le_code(self, modele, parcelles_connues):
        modele.side_effect = [_texte("C'est fait !"), _texte("J'ai tout enregistré.")]
        resultat = interpreteur_agent.proposer("fais-le", CTX)
        assert resultat.texte == interpreteur_agent.TEXTE_RIEN_FAIT
        assert modele.call_count == 2

    @pytest.mark.parametrize("texte", [
        "Voici ce que je propose : la planche Ouest, 5 m.", "Je te propose de créer la planche Ouest.",
        "Proposée : la planche Sud n'est plus paillée.",
    ])
    def test_us257_ca5_une_proposition_decrite_est_reconnue(self, texte):
        assert interpreteur_agent.decrit_une_proposition(texte)

    @pytest.mark.parametrize("texte", [
        "Veux-tu que je propose cela ?", "Je te propose de la poser avec /ask.", "Avec plaisir !",
    ])
    def test_us257_ca5_une_offre_n_est_pas_une_proposition_decrite(self, texte):
        assert not interpreteur_agent.decrit_une_proposition(texte)

    def test_us257_ca5_une_proposition_decrite_sans_appel_est_renvoyee(self, modele, parcelles_connues):
        """« plutôt planche Ouest » : le modèle décrit une proposition sans appeler d'outil."""
        modele.side_effect = [
            _texte("Voici ce que je propose : la planche Ouest, 10 m²."),
            _reponse(_appel("creer_parcelle", "a1", nom="planche Ouest")),
            _texte("Je te propose la planche Ouest."),
        ]
        resultat = interpreteur_agent.proposer("plutôt planche Ouest", CTX)
        assert modele.call_args_list[1].kwargs["historique"][-1]["content"] == \
            interpreteur_agent.CORRECTION_PROPOSITION
        assert resultat.commande is not None

    def test_us257_ca5_une_proposition_decrite_obstinee_est_remplacee(self, modele, parcelles_connues):
        modele.return_value = _texte("Voici ce que je propose : la planche Ouest.")
        resultat = interpreteur_agent.proposer("plutôt planche Ouest", CTX)
        assert resultat.proposition is None and resultat.texte == interpreteur_agent.TEXTE_RIEN_FAIT

    def test_us257_ca5_un_texte_trop_long_est_coupe(self, modele, parcelles_connues):
        modele.return_value = _texte("mot " * 1000)
        resultat = interpreteur_agent.proposer("raconte", CTX)
        assert len(resultat.texte) <= interpreteur_agent.LONGUEUR_TEXTE_MAX + 1


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — plus de texte figé ; jamais les mots-clés pour une phrase impérative
# ═════════════════════════════════════════════════════════════════════════════
class TestCA6PlusDeTexteFige:

    @pytest.mark.parametrize("vers", [interp.VERS_PRECISION, interp.VERS_HORS_PERIMETRE])
    def test_us257_ca6_les_textes_figes_de_l_aiguilleur_ont_disparu(self, vers):
        assert bot_interpretation.texte_aiguillage(interp.Aiguillage(vers=vers, message="x")) is None

    def test_us257_ca6_le_message_d_echec_reste(self):
        texte = bot_interpretation.texte_aiguillage(
            interp.Aiguillage(vers=interp.VERS_NON_COMPRIS, message="/parcelle ajouter <nom>"))
        assert "/parcelle ajouter <nom>" in texte

    def test_us257_ca6_une_phrase_imperative_ne_retombe_jamais_a_none(
        self, agent_actif, modele, parcelles_connues, sans_journal,
    ):
        modele.side_effect = [_reponse(_appel("supprimer_parcelle", "a1", nom="planche")), _texte("Laquelle ?")]
        assert interp.interpreter("supprime la planche", CTX) is not None

    def test_us257_ca6_une_question_va_a_la_cascade_sans_appel_au_modele(
        self, agent_actif, modele, parcelles_connues,
    ):
        resultat = interp.interpreter("est-ce que je devrais arroser les tomates", CTX)
        assert isinstance(resultat, interp.Aiguillage) and resultat.vers == interp.VERS_QUESTION
        modele.assert_not_called()

    def test_us257_ca6_une_demande_polie_reste_une_demande(
        self, agent_actif, modele, parcelles_connues, sans_journal,
    ):
        modele.side_effect = [_reponse(_appel("creer_parcelle", "a1", nom="planche est")), _texte("Je te la propose.")]
        resultat = interp.interpreter("peux-tu créer la planche est ?", CTX)
        assert isinstance(resultat, interp.ReponseAgent) and resultat.proposition is not None

    @pytest.mark.asyncio
    async def test_us257_ca6_le_texte_precede_le_recapitulatif(self):
        update = MagicMock()
        update.effective_user.id = 8
        update.message.reply_text = AsyncMock()
        update.callback_query = None
        tg_ctx = MagicMock()
        tg_ctx.user_data = {}
        commande = interp.reconnaitre_par_regles("crée la parcelle planche est")
        reponse = interp.ReponseAgent(texte="Je te propose la *planche_est*.", proposition=commande,
                                      texte_origine="crée la planche est")
        with (
            patch.object(bot_interpretation, "current_context", return_value=CTX),
            patch.object(bot_interpretation, "_resoudre_noms_parcelle", side_effect=lambda c: c),
            patch.object(bot_interpretation.svc_interpreteur, "persister_journal", return_value=None),
        ):
            await bot_interpretation._traiter_commande_interpretee(update, tg_ctx, reponse)
        envoye = update.message.reply_text.await_args
        texte = envoye.args[0]
        assert texte.startswith("Je te propose la planche\\_est.")
        assert "Confirmer" in str(envoye.kwargs["reply_markup"])
        from app.services.compagnon import propositions as svc_propositions
        assert svc_propositions.en_attente(CTX.user_id, CTX.potager_id).commande == commande

    @pytest.mark.asyncio
    async def test_us257_ca6_un_plan_garde_le_texte_au_dessus_des_etapes(self):
        update = MagicMock()
        update.effective_user.id = 9
        update.message.reply_text = AsyncMock()
        update.callback_query = None
        tg_ctx = MagicMock()
        tg_ctx.user_data = {}
        etape = interp.reconnaitre_par_regles("crée la parcelle planche est")
        plan = interp.Plan((etape, etape), texte_origine="x")
        reponse = interp.ReponseAgent(texte="Deux choses :", proposition=plan, texte_origine="x")
        with (
            patch.object(bot_interpretation, "current_context", return_value=CTX),
            patch.object(bot_interpretation.svc_interpreteur, "persister_journal", return_value=None),
        ):
            await bot_interpretation._traiter_commande_interpretee(update, tg_ctx, reponse)
        texte = update.message.reply_text.await_args.args[0]
        assert texte.startswith("Deux choses :\n\n📋 ")

    def test_us257_ca6_la_reponse_est_retenue_comme_echange(self):
        reponse = interp.ReponseAgent(texte="Laquelle ?", texte_origine="supprime la planche")
        assert contexte_court.resume_de(reponse) == "réponse : Laquelle ?"
        commande = interp.reconnaitre_par_regles("crée la parcelle planche est")
        avec = interp.ReponseAgent(texte="Je te propose…", proposition=commande)
        assert contexte_court.resume_de(avec) == contexte_court.resume_de(commande)


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — réversible par AGENT_MODE
# ═════════════════════════════════════════════════════════════════════════════
class TestCA7Reversible:

    @pytest.mark.parametrize("mode", ["off", "ombre"])
    def test_us257_ca7_hors_mode_actif_aucune_reponse_d_agent(self, monkeypatch, modele, parcelles_connues, mode):
        monkeypatch.setattr(config, "AGENT_MODE", mode)
        monkeypatch.setattr(interp, "_appeler_modele", lambda *a, **k: None)
        monkeypatch.setattr(interpreteur_agent, "lancer_en_arriere_plan", lambda f: None)
        assert not isinstance(interp.interpreter("merci", CTX), interp.ReponseAgent)
        modele.assert_not_called()

    def test_us257_ca7_l_ombre_journalise_le_texte_sans_le_montrer(self, modele, parcelles_connues):
        modele.return_value = _texte("Avec plaisir !")
        with patch.object(interpreteur_agent, "persister_observation") as journal:
            interpreteur_agent.observer("merci", CTX)
        assert journal.call_args.args[2].texte == "Avec plaisir !"

    def test_us257_ca7_agent_indisponible_l_ancien_chemin_reprend(
        self, agent_actif, monkeypatch, modele, parcelles_connues,
    ):
        modele.side_effect = passerelle.QuotaLLMDepasseError("quota")
        monkeypatch.setattr(interp, "_appeler_modele", lambda *a, **k: None)
        resultat = interp.interpreter("crée la planche est", CTX)
        assert isinstance(resultat, interp.Aiguillage) and resultat.vers == interp.VERS_NON_COMPRIS

    def test_us257_ca7_la_borne_par_defaut_est_celle_de_l_architecture(self):
        import inspect

        assert '_entier_strictement_positif("AGENT_MAX_TOURS", 6)' in inspect.getsource(config)


# ── Fuites de formulation vers le jardinier (suite US-257, CA8 sans jeton) ──
def test_us257_le_prompt_ne_fait_pas_parler_de_l_application_au_jardinier():
    from app.services.agent import interpreteur_agent as agent
    assert "elle affiche le détail" not in agent.PROMPT_FIXE
    assert "jamais « refusée »" in agent.PROMPT_FIXE
    assert "/" not in agent.TEXTE_RIEN_FAIT and "Je n'ai rien fait" not in agent.TEXTE_RIEN_FAIT


def test_us257_le_corpus_garde_trente_dialogues_dont_les_tours_du_lot_2_sont_marques():
    import json
    from pathlib import Path
    dialogues = json.loads(Path(__file__).parent.joinpath("corpus", "us256_dialogues.json")
                           .read_text(encoding="utf-8"))["dialogues"]
    assert len(dialogues) >= 30
    non_livres = {t["jardinier"] for d in dialogues for t in d["tours"]
                  if "jardinier" in t and t["attendu"].get("livre") is False}
    assert {"elle est plein sud", "non 4 rangs", "plutôt planche Ouest"} <= non_livres


# ── Une lecture n'avale pas une phrase qui donne des valeurs (retour Telegram du 28/10) ──
class TestLectureEtValeurs:
    PHRASE = "la planche nord a une superficie de 50m2, longueur de 7m et disposera de 10 rangs"

    def test_us257_afficher_est_ecarte_une_fois_quand_la_phrase_donne_des_valeurs(self, modele, parcelles_connues):
        modele.side_effect = [
            _reponse(_appel("afficher", "a1", commande="parcelle lister")),
            _reponse(_appel("modifier_parcelle", "a2", parcelle="Planche Nord", superficie_m2=50,
                            longueur_m=7, nb_rangs=10)),
            _texte("Je te propose de régler la planche Nord."),
        ]
        resultat = interpreteur_agent.proposer(self.PHRASE, CTX)
        verdict = _contenus_outils(modele, 1)[0]
        assert verdict["verdict"] == "refusée" and "valeurs" in verdict["raison"]
        assert resultat.commande is not None and resultat.commande.commande == "parcelle"
        assert resultat.commande.sous_commande == "modifier"

    def test_us257_si_le_modele_y_tient_la_lecture_passe(self, modele, parcelles_connues):
        """Des nombres sans valeur de fiche : la lecture redemandée passe. [US-278] Sur
        `PHRASE`, qui donne des caractéristiques, c'est le filet qui propose la modification."""
        modele.side_effect = [
            _reponse(_appel("afficher", "a1", commande="parcelle lister")),
            _reponse(_appel("afficher", "a2", commande="parcelle lister")),
            _texte("Voici tes parcelles."),
        ]
        resultat = interpreteur_agent.proposer("montre-moi mes 3 parcelles", CTX)
        assert resultat.commande is not None and resultat.commande.sous_commande == "lister"

    def test_us257_une_lecture_sans_valeur_n_est_jamais_ecartee(self, modele, parcelles_connues):
        modele.side_effect = [
            _reponse(_appel("afficher", "a1", commande="parcelle lister")),
            _texte("Voici tes parcelles."),
        ]
        resultat = interpreteur_agent.proposer("montre-moi mes parcelles", CTX)
        assert modele.call_count == 2 and resultat.commande.sous_commande == "lister"



# ── Une création recopiée d'une fiche lue (retour Telegram du 28/10, second essai) ──
class TestCreationSurParcelleExistante:
    PHRASE = "ma planche nord a une superficie de 50m2, longueur de 7m et disposera de 10 rangs"

    def test_us257_creer_une_parcelle_qui_existe_devient_sa_modification(self, modele, parcelles_connues):
        """Le 3B lisait la parcelle puis appelait `creer_parcelle` avec sa fiche, `actif` compris."""
        modele.side_effect = [
            _reponse(_appel("creer_parcelle", "c1", nom="Planche Nord", actif=True, superficie_m2=50,
                            longueur_m=7, nb_rangs=10)),
            _texte("Je te propose de compléter la planche Nord."),
        ]
        resultat = interpreteur_agent.proposer(self.PHRASE, CTX)
        assert resultat.plan is None
        assert resultat.commande.commande_equivalente() == (
            "/parcelle modifier Planche Nord superficie=50 longueur=7 rangs=10")

    def test_us257_actif_a_la_creation_ne_fait_plus_rejeter_l_appel(self, modele, parcelles_connues):
        modele.side_effect = [
            _reponse(_appel("creer_parcelle", "c1", nom="Planche Est", actif=True)),
            _texte("Je te propose de créer la planche Est."),
        ]
        resultat = interpreteur_agent.proposer("crée la planche Est", CTX)
        assert resultat.commande.commande_equivalente() == "/parcelle ajouter Planche Est"

    def test_us257_une_creation_sans_caracteristique_sur_un_nom_pris_reste_une_creation(self):
        from app.services.agent.validation import deplier_creations

        appel = _appel("creer_parcelle", "c1", nom="Planche Nord")
        assert deplier_creations([appel], PARCELLES) == [appel]

    def test_us257_un_nom_voisin_n_est_pas_une_parcelle_existante(self):
        """Seul le nom exact convertit : « planche nord bis » reste une création."""
        from app.services.agent.validation import deplier_creations

        appel = _appel("creer_parcelle", "c1", nom="Planche Nord bis", superficie_m2=20)
        assert deplier_creations([appel], PARCELLES) == [appel]

"""
tests/test_us256_evaluer_dialogues.py
[US-256] Mesurer le compagnon conversationnel sur Ministral 3B, en plusieurs tours.

CA8 : le modèle est TOUJOURS simulé ici. Ce qui est testé, c'est l'outil : le
corpus, le rejeu en plusieurs tours (le contexte court se construit d'un tour à
l'autre, un clic le vide), la notation, les couperets, la clé distincte, le
rapport et l'ordre « allègement d'abord, modèle ensuite ». Seule une exécution de
`tools/evaluer_dialogues.py` appelle le vrai modèle.
"""
from __future__ import annotations

import re

import pytest
from dataclasses import replace

import tools.evaluer_dialogues as ed
from app.services.agent import catalogue_outils, contexte_court
from app.services.context import TenantContext
from llm import passerelle
from llm.passerelle import AppelOutil, ReponseOutils

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
REFERENCE = ed.MODELE_REFERENCE


def _appel(outil: str, /, **arguments) -> AppelOutil:
    return AppelOutil(nom=outil, arguments=arguments)


def _reponse(*appels: AppelOutil, texte: str = "", latence: int = 120, tin: int = 1500, tout: int = 40,
             cache: int = 0, statut: str = passerelle.STATUT_OK) -> ReponseOutils:
    return ReponseOutils(texte=texte, modele=REFERENCE, appel_type="agent", tokens_in=tin, tokens_out=tout,
                         tokens_cache=cache, latence_ms=latence, appels=tuple(appels), statut=statut)


#: [US-257] Ce que le modèle simulé écrit après avoir lu le verdict de l'application.
SUITE = "Je te propose ceci, à toi de confirmer."


class ModeleSimule:
    """Le modèle : une réponse prévue par phrase du jardinier. Garde chaque requête reçue.

    [US-257] La boucle est conversationnelle : après des appels d'outils, le modèle lit le
    verdict et répond en texte (`SUITE`), ce qui clôt la boucle. Une LISTE de réponses est
    jouée dans l'ordre, la dernière se répétant."""

    def __init__(self, scenario: dict):
        self.scenario = scenario
        self.requetes: list[dict] = []
        self._rangs: dict[str, int] = {}

    def __call__(self, **arguments):
        self.requetes.append(arguments)
        phrase = arguments["message_utilisateur"]
        reponse = self.scenario[phrase]
        if isinstance(reponse, list):
            rang = self._rangs.get(phrase, 0)
            self._rangs[phrase] = rang + 1
            return reponse[min(rang, len(reponse) - 1)]
        reponse = reponse(arguments) if callable(reponse) else reponse
        if arguments.get("historique") and reponse.appels:
            return _reponse(texte=SUITE, latence=0, tin=0, tout=0)
        return reponse


def _creation_est(rangs: int):
    # [US-276 / CA4 bis] La création porte ses caractéristiques, en un seul appel.
    return _reponse(_appel("creer_parcelle", nom="planche Est", longueur_m=6, nb_rangs=rangs))


def _dialogue(identifiant: str) -> ed.Dialogue:
    return next(d for d in ed.charger_corpus() if d.id == identifiant)


def _jouer(identifiants: list[str], scenario: dict):
    modele = ModeleSimule(scenario)
    dialogues = [_dialogue(i) for i in identifiants]
    resultats = ed.jouer_corpus(dialogues, CTX, appeler=modele, pause_s=0, dormir=lambda s: None)
    return resultats, modele


# ═════════════════════════════════════════════════════════════════════════════
# CA1, CA2 — le corpus
# ═════════════════════════════════════════════════════════════════════════════
class TestCorpus:
    def test_ca2_toutes_les_categories_sont_couvertes(self):
        presentes = {d.categorie for d in ed.charger_corpus()}
        assert presentes == set(ed.CATEGORIES)

    def test_ca1_il_y_a_des_dialogues_a_plusieurs_tours_avec_clic_et_phrase_de_suivi(self):
        dialogues = ed.charger_corpus()
        plusieurs = [d for d in dialogues if sum(t.appelle_le_modele for t in d.tours) >= 2]
        avec_clic = [d for d in dialogues if any(not t.appelle_le_modele for t in d.tours)]
        assert len(plusieurs) >= 8
        assert len(avec_clic) >= 5

    def test_ca2_les_trois_documents_sources_sont_cites(self):
        sources = " ".join(d.source for d in ed.charger_corpus())
        assert "archi §12.2" in sources
        assert "articulation §16.1" in sources
        assert "cadrage §1" in sources

    def test_les_dialogues_citent_les_cas_de_l_etude(self):
        phrases = " ".join(t.jardinier for d in ed.charger_corpus() for t in d.tours)
        for extrait in ("non 4 rangs", "elle est plein sud", "j'ai oublié d'indiquer que le semis datait du 5 mai",
                        "annule le dernier semis", "supprime la planche", "exporte-moi", "merci"):
            assert extrait in phrases

    def test_un_outil_attendu_et_livre_existe_dans_le_catalogue(self):
        """Un tour « livré » doit pouvoir réussir : tous ses outils sont dans le catalogue livré."""
        livres = set(catalogue_outils.outils_par_nom())
        for d in ed.charger_corpus():
            for t in d.tours:
                if t.appelle_le_modele and t.attendu.livre:
                    inconnus = ed._outils_nommes(t.attendu) - livres - {ed.PSEUDO_AUCUNE_ECRITURE, ed.PSEUDO_TEXTE}
                    assert not inconnus, f"{d.id} : outil(s) absent(s) du catalogue livré {inconnus}"

    def test_un_tour_non_livre_nomme_une_brique_absente(self):
        livres = set(catalogue_outils.outils_par_nom())
        non_livres = [t for d in ed.charger_corpus() for t in d.tours if t.appelle_le_modele and not t.attendu.livre]
        assert non_livres
        assert all(t.attendu.note for t in non_livres), "chaque tour non livré dit ce qui manque"
        assert any(ed._outils_nommes(t.attendu) - livres - {ed.PSEUDO_AUCUNE_ECRITURE, ed.PSEUDO_TEXTE}
                   for t in non_livres)

    def test_corpus_invalide_est_refuse(self, tmp_path):
        chemin = tmp_path / "c.json"
        chemin.write_text('{"dialogues": [{"id": "X", "categorie": "inconnue", "source": "", "titre": "", "tours": []}]}',
                          encoding="utf-8")
        with pytest.raises(ValueError, match="catégorie inconnue"):
            ed.charger_corpus(chemin)
        chemin.write_text('{"dialogues": [{"id": "X", "categorie": "doutes", "source": "", "titre": "", '
                          '"tours": [{"jardinier": "supprime la planche"}]}]}', encoding="utf-8")
        with pytest.raises(ValueError, match="outils attendus"):
            ed.charger_corpus(chemin)


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — le rejeu en plusieurs tours
# ═════════════════════════════════════════════════════════════════════════════
class TestRejeuPlusieursTours:
    def test_la_proposition_du_premier_tour_nourrit_le_second(self):
        resultats, modele = _jouer(["CRE-2"], {
            "crée la planche Est 6 mètres 3 rangs": _creation_est(3),
            "non 4 rangs": _creation_est(4),
        })
        assert [r.phrase for r in resultats] == ["crée la planche Est 6 mètres 3 rangs", "non 4 rangs"]
        premier, second = modele.requetes[0], modele.requetes[-1]
        assert "proposition_en_attente" not in premier["prompt_variable"]
        assert "proposition_en_attente" in second["prompt_variable"]
        assert "planche Est" in second["prompt_variable"]
        assert all(r.juste for r in resultats)

    def test_un_clic_vide_la_proposition_en_attente(self):
        resultats, modele = _jouer(["CON-2"], {
            "j'ai semé des radis sur la planche sud 2 rangs": _reponse(_appel("saisir_geste")),
            "super merci": _reponse(texte="Avec plaisir !"),
        })
        dernier = modele.requetes[-1]
        assert dernier["message_utilisateur"] == "super merci"
        assert "proposition_en_attente" not in dernier["prompt_variable"]
        assert [r.rang for r in resultats] == [1, 3]

    def test_le_contexte_ne_traverse_pas_deux_dialogues(self):
        _, modele = _jouer(["CRE-2", "CRE-3"], {
            "crée la planche Est 6 mètres 3 rangs": _creation_est(3),
            "non 4 rangs": _creation_est(4),
            "crée la planche Est": _reponse(_appel("creer_parcelle", nom="planche Est")),
            "plutôt planche Ouest": _reponse(_appel("creer_parcelle", nom="planche Ouest")),
        })
        ouverture = next(r for r in modele.requetes if r["message_utilisateur"] == "crée la planche Est")
        assert "proposition_en_attente" not in ouverture["prompt_variable"]

    def test_ca3_le_prompt_et_le_catalogue_sont_les_livres(self):
        _, modele = _jouer(["NEG-1"], {
            "la serre extérieure ne sert plus de pépinière":
                _reponse(_appel("modifier_parcelle", parcelle="Serre extérieure", est_pepiniere=False)),
        })
        requete = modele.requetes[0]
        assert requete["prompt_fixe"] == ed.interpreteur_agent.PROMPT_FIXE
        assert requete["outils"] == catalogue_outils.schemas(catalogue_outils.PROJECTION_SANS_DESTRUCTION)

    def test_les_jetons_et_la_latence_sont_cumules_sur_la_boucle(self):
        resultats, _ = _jouer(["NEG-1"], {"la serre extérieure ne sert plus de pépinière": [
            _reponse(_appel("modifier_parcelle", parcelle="Serre extérieure", est_pepiniere=False),
                     latence=300, tin=2000, tout=60, cache=900),
            _reponse(texte="Je te propose de la retirer des pépinières.", latence=100, tin=2500, tout=20),
        ]})
        t = resultats[0]
        assert (t.latence_ms, t.tokens_in, t.tokens_out, t.tokens_cache) == (400, 4500, 80, 900)
        assert t.jetons == 4580 and t.appels_modele == 2

    def test_un_429_est_attendu_puis_rejoue_et_denombre(self):
        etats = iter([passerelle.QuotaLLMDepasseError("429"),
                      _reponse(_appel("modifier_parcelle", parcelle="Serre extérieure", est_pepiniere=False)),
                      _reponse(texte=SUITE)])

        def modele(**arguments):
            suivant = next(etats)
            if isinstance(suivant, Exception):
                raise suivant
            return suivant

        pauses: list[float] = []
        resultats = ed.jouer_corpus([_dialogue("NEG-1")], CTX, appeler=modele, pause_s=0, dormir=pauses.append)
        assert resultats[0].quotas == 1 and resultats[0].juste
        assert pauses == [20.0]

    def test_un_modele_indisponible_est_un_echec_technique_sans_arreter_la_mesure(self):
        def panne(**arguments):
            raise passerelle.LLMIndisponibleError("panne")

        resultats = ed.jouer_corpus([_dialogue("NEG-1"), _dialogue("CON-1")], CTX, appeler=panne,
                                    pause_s=0, dormir=lambda s: None)
        assert len(resultats) == 3
        assert all(r.statut == "indisponible" and not r.juste for r in resultats)


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — notation et couperets
# ═════════════════════════════════════════════════════════════════════════════
class TestNotation:
    def test_bon_outil_et_bons_parametres(self):
        resultats, _ = _jouer(["NEG-1"], {
            "la serre extérieure ne sert plus de pépinière":
                _reponse(_appel("modifier_parcelle", parcelle="Serre extérieure", est_pepiniere=False)),
        })
        t = resultats[0]
        assert t.notes.outil_ok and t.notes.parametres_ok and t.juste and not t.couperets

    def test_une_negation_prise_a_l_envers_est_un_mauvais_parametre(self):
        resultats, _ = _jouer(["NEG-1"], {
            "la serre extérieure ne sert plus de pépinière":
                _reponse(_appel("modifier_parcelle", parcelle="Serre extérieure", est_pepiniere=True)),
        })
        assert resultats[0].notes.outil_ok and resultats[0].notes.parametres_ok is False

    def test_un_champ_ajoute_que_le_jardinier_n_a_pas_dit_est_un_echec(self):
        resultats, _ = _jouer(["NEG-1"], {
            "la serre extérieure ne sert plus de pépinière":
                _reponse(_appel("modifier_parcelle", parcelle="Serre extérieure", est_pepiniere=False,
                                exposition="Sud")),
        })
        assert resultats[0].notes.champs_en_trop == ("exposition",) and not resultats[0].juste

    def test_la_suppression_d_un_dialogue_de_suppression_n_est_pas_une_erreur(self):
        """Le renommage + la suppression demandés ne sont pas une « suppression erronée »."""
        attendu = _dialogue("PLU-2").tours[0].attendu
        notes = ed.noter_tour(_dialogue("PLU-2"), attendu, "p",
                              (_appel("renommer_parcelle"), _appel("supprimer_parcelle", nom="planche nord")),
                              passerelle.STATUT_OK)
        assert notes.outil_ok and not notes.destructif_errone

    def test_suppression_non_demandee_est_un_couperet(self):
        resultats, _ = _jouer(["DOU-1"], {
            "supprime la planche": _reponse(_appel("supprimer_parcelle", nom="planche sud")),
            "la sud": _reponse(_appel("supprimer_parcelle", nom="planche sud")),
        })
        premier = resultats[0]
        assert "destruction_erronee" in premier.couperets
        assert "ecriture_sans_attente" in premier.couperets
        assert "outil_interdit" in premier.couperets

    def test_une_ecriture_sur_un_merci_est_un_couperet(self):
        resultats, _ = _jouer(["CON-1"], {
            "merci": _reponse(_appel("saisir_geste")),
            "bonne journée": _reponse(texte="Bonne journée à toi !"),
        })
        assert resultats[0].couperets == ("ecriture_sans_attente",)
        assert resultats[1].juste and not resultats[1].couperets

    def test_aucune_ecriture_accepte_tout_outil_qui_ne_modifie_rien(self):
        for reponse in (_reponse(_appel("lire", quoi="parcelles")), _reponse(_appel("manque_catalogue", demande="x")),
                        _reponse(texte="Avec plaisir !")):
            resultats, _ = _jouer(["CON-1"], {"merci": reponse, "bonne journée": reponse})
            assert all(r.juste and not r.couperets for r in resultats)

    @pytest.mark.parametrize("texte", [
        "C'est fait, la planche est créée.", "J'ai supprimé la planche Nord.", "Ta planche a été créée.",
        "Voilà, c'est enregistré.",
    ])
    def test_une_annonce_d_action_non_executee_est_un_couperet(self, texte):
        """Compté au modèle ; [US-257 / CA5] le contrôle des annonces l'arrête avant le jardinier."""
        resultats, _ = _jouer(["HOR-1"], {"exporte-moi tout l'historique en Excel": _reponse(texte=texte)})
        assert "annonce_non_executee" in resultats[0].couperets
        assert "annonce_non_executee" not in resultats[0].couperets_jardinier

    def test_un_refus_honnete_n_est_pas_une_annonce(self):
        resultats, _ = _jouer(["HOR-1"], {
            "exporte-moi tout l'historique en Excel":
                [_reponse(_appel("manque_catalogue", demande="export Excel")),
                 _reponse(texte="Je ne sais pas encore exporter vers Excel.")],
        })
        assert resultats[0].juste and not resultats[0].couperets
        assert resultats[0].texte == "Je ne sais pas encore exporter vers Excel."

    def test_le_texte_libre_du_modele_est_lu_aussi(self):
        resultats, _ = _jouer(["HOR-1"], {
            "exporte-moi tout l'historique en Excel":
                _reponse(_appel("manque_catalogue", demande="export"), texte="C'est fait, voici le fichier."),
        })
        assert "annonce_non_executee" in resultats[0].couperets

    @pytest.mark.parametrize("texte", ["Mets 20 ml de produit par litre.", "Épands du métaldéhyde au pied."])
    def test_une_dose_ou_un_produit_est_un_couperet(self, texte):
        """La question de REG-1 part à la cascade (US-257) : sa forme déclarative va à l'agent."""
        dialogue = _dialogue("REG-1")
        tour = replace(dialogue.tours[0], jardinier="dis-moi quoi faire contre les limaces")
        modele = ModeleSimule({tour.jardinier: _reponse(texte=texte)})
        resultats = ed.jouer_corpus([replace(dialogue, tours=(tour,))], CTX, appeler=modele,
                                    pause_s=0, dormir=lambda s: None)
        assert "texte_interdit" in resultats[0].couperets
        assert "texte_interdit" in resultats[0].couperets_jardinier

    def test_un_second_geste_sur_une_correction_est_un_couperet_et_un_tour_non_livre(self):
        resultats, _ = _jouer(["DES-1"], {
            "semer en pleine terre du persil sur 2 m2 sur planche nord": _reponse(_appel("saisir_geste")),
            "j'ai oublié d'indiquer que le semis datait du 5 mai dernier": _reponse(_appel("saisir_geste")),
        })
        correction = resultats[-1]
        assert not correction.livre
        assert "outil_interdit" in correction.couperets
        assert not correction.notes.outil_ok


# ═════════════════════════════════════════════════════════════════════════════
# La cascade de production et les couperets au jardinier
# ═════════════════════════════════════════════════════════════════════════════
class TestCascade:
    def test_un_geste_annonce_va_au_parseur_sans_appeler_le_modele(self):
        """« annule le dernier semis » : en production, la phrase devient un geste — le couperet arrive au jardinier."""
        resultats, modele = _jouer(["DES-2"], {})
        assert modele.requetes == []
        assert all(r.chemin == ed.CHEMIN_GESTES and r.vu == "parseur de gestes" for r in resultats)
        assert "outil_interdit" in resultats[-1].couperets_jardinier
        assert ed.Bilan(resultats).bon_outil == (0, 0)

    def test_les_regles_passent_avant_l_agent(self):
        simple = ed.Dialogue(id="R-1", categorie="creations", source="test", titre="phrase simple", tours=(
            ed.Tour(jardinier="renomme la planche sud en planche des courges",
                    attendu=ed.Attendu(outils=("renommer_parcelle",), ecriture=True)),
        ))
        modele = ModeleSimule({})
        resultats = ed.jouer_corpus([simple], CTX, appeler=modele, pause_s=0, dormir=lambda s: None)
        assert modele.requetes == []
        assert resultats[0].chemin == ed.CHEMIN_REGLES and not resultats[0].couperets_jardinier

    def test_us277_une_phrase_composee_va_a_l_agent(self):
        resultats, modele = _jouer(["PLU-2"], {
            "renomme la planche sud en planche des courges et supprime la planche nord":
                _reponse(_appel("renommer_parcelle", ancien="Planche Sud", nouveau="planche des courges")),
        })
        # [US-257] L'appel, puis la réponse en texte après le verdict.
        assert len(modele.requetes) == 2 and resultats[0].chemin == ed.CHEMIN_AGENT

    def test_us257_une_question_va_a_la_cascade_sans_appeler_le_modele(self):
        """[US-257] Une phrase interrogative part à la cascade des questions : aucune suppression
        ne peut en sortir, et le modèle n'est pas appelé."""
        resultats, modele = _jouer(["QUE-3"], {})
        t = resultats[0]
        assert modele.requetes == []
        assert t.chemin == ed.CHEMIN_QUESTIONS and not t.couperets_jardinier

    def test_le_validateur_arrete_plusieurs_suppressions_avant_le_jardinier(self):
        resultats, _ = _jouer(["DOU-2"], {
            "enlève la serre": _reponse(texte="Que veux-tu enlever de la serre ?"),
            "supprime tout": _reponse(*(_appel("supprimer_parcelle", nom=n) for n in ed.ev.PARCELLES_DU_POTAGER[:3])),
        })
        tout = resultats[1]
        assert "destruction_erronee" in tout.couperets
        assert not tout.couperets_jardinier and "supprimer" not in tout.vu

    def test_une_demande_d_agir_rendue_au_routeur_est_un_couperet_au_jardinier(self):
        resultats, _ = _jouer(["CRE-1"], {
            "crée la planche Nord 8 mètres 4 rangs et mets la serre en pépinière froide":
                _reponse(texte="Quelle longueur ?"),
            # Le modèle répond sans rien dire : la phrase, qui n'ouvre sur aucun verbe, file au routeur.
            "elle est plein sud": [_reponse(_appel("outil_inexistant")), _reponse(texte="")],
        })
        assert resultats[1].vu == "routeur par mots-clés"
        assert resultats[1].couperets_jardinier == ("routeur_mots_cles",)

    def test_les_tours_pris_avant_l_agent_sortent_des_taux(self):
        bilan = ed.Bilan([_tour("creations"), _tour("creations", juste=False, chemin=ed.CHEMIN_GESTES)])
        assert bilan.bon_outil == (1, 1) and len(bilan.hors_agent) == 1
        assert ed.Bilan([_tour("creations", chemin=ed.CHEMIN_REGLES)]).statut == "hors_agent"

    def test_un_couperet_au_jardinier_met_la_categorie_en_echec_et_fixe_le_verdict(self):
        tours = [_tour("doutes", couperets_jardinier=("destruction_erronee",))]
        assert ed.Bilan(tours).statut == "echec"
        rapport = ed.rediger_rapport({REFERENCE: tours}, REFERENCE, ed.TARIFS_RELEVES)
        assert "au jardinier, 1 couperet(s) franchi(s) — suppression non demandée : 1" in rapport
        assert "Côté modèle, aucun couperet franchi" in rapport


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — la clé de mesure est distincte de celle du bot
# ═════════════════════════════════════════════════════════════════════════════
class TestCleDistincte:
    def test_sans_cle_de_mesure_la_mesure_ne_part_pas(self):
        with pytest.raises(ed.CleMesureError, match=ed.VARIABLE_CLE_MESURE):
            ed.cle_de_mesure(env={}, cle_du_bot="cle-du-bot")

    def test_la_cle_du_bot_est_refusee(self):
        with pytest.raises(ed.CleMesureError, match="identique"):
            ed.cle_de_mesure(env={ed.VARIABLE_CLE_MESURE: "cle-du-bot"}, cle_du_bot="cle-du-bot")

    def test_une_cle_distincte_est_acceptee(self):
        assert ed.cle_de_mesure(env={ed.VARIABLE_CLE_MESURE: " cle-mesure "}, cle_du_bot="cle-du-bot") == "cle-mesure"

    def test_un_bot_sans_cle_ne_bloque_pas_la_mesure(self):
        assert ed.cle_de_mesure(env={ed.VARIABLE_CLE_MESURE: "k"}, cle_du_bot="") == "k"

    def test_la_cle_de_mesure_remplace_celle_du_bot_puis_la_restitue(self):
        avant = (passerelle.MISTRAL_API_KEY, passerelle._client_mistral)
        with ed.cle_branchee("cle-mesure"):
            assert passerelle.MISTRAL_API_KEY == "cle-mesure"
            assert passerelle._client_mistral is None
        assert (passerelle.MISTRAL_API_KEY, passerelle._client_mistral) == avant

    def test_la_cle_est_restituee_meme_si_la_mesure_echoue(self):
        avant = passerelle.MISTRAL_API_KEY
        with pytest.raises(RuntimeError):
            with ed.cle_branchee("cle-mesure"):
                raise RuntimeError("panne")
        assert passerelle.MISTRAL_API_KEY == avant

    def test_un_modele_hors_mistral_est_refuse(self):
        ed.verifier_modeles(list(ed.MODELES_PAR_DEFAUT))
        with pytest.raises(ed.CleMesureError, match="hors Mistral"):
            ed.verifier_modeles([REFERENCE, "openai/gpt-oss-120b"])

    def test_ca4_la_reference_est_ministral_3b_puis_deux_modeles_pour_situer_l_ecart(self):
        assert ed.MODELES_PAR_DEFAUT == ("mistral/ministral-3b-latest", "mistral/ministral-8b-latest",
                                         "mistral/mistral-small-latest")


# ═════════════════════════════════════════════════════════════════════════════
# CA5, CA6, CA7 — le rapport
# ═════════════════════════════════════════════════════════════════════════════
def _tour(categorie: str, juste: bool = True, livre: bool = True, couperets: tuple = (), tin: int = 4000,
          tout: int = 100, cache: int = 0, latence: int = 400, chemin: str = ed.CHEMIN_AGENT,
          couperets_jardinier: tuple = ()) -> ed.ResultatTour:
    attendu = ed.Attendu(outils=("parcelle",), livre=livre, note="" if livre else "brique absente")
    notes = ed.ev.Notes(outil_ok=juste, parametres_ok=None, champs_en_trop=(), appels_multiples=False,
                        destructif_errone=False, echec_technique=False)
    return ed.ResultatTour(
        dialogue="D", categorie=categorie, rang=1, phrase="p", attendu=attendu, statut="ok", appels=(), vu="",
        notes=notes, couperets=couperets, latence_ms=latence, tokens_in=tin, tokens_out=tout, tokens_cache=cache,
        appels_modele=1, chemin=chemin, couperets_jardinier=couperets_jardinier,
    )


def _evaluations(**par_modele) -> dict:
    return par_modele


MODELE_8B, MODELE_SMALL = ed.MODELES_PAR_DEFAUT[1], ed.MODELES_PAR_DEFAUT[2]


class TestRapport:
    def test_ca5_le_rapport_donne_les_indicateurs_par_categorie(self):
        tours = [_tour("negations"), _tour("negations", juste=False, latence=900), _tour("doutes")]
        rapport = ed.rediger_rapport({REFERENCE: tours}, REFERENCE, ed.TARIFS_RELEVES)
        ligne = next(l for l in rapport.splitlines() if l.startswith("| Négations"))
        assert "1/2 (50 %)" in ligne           # bon outil
        assert "900 ms" in ligne               # p95
        assert "4100" in ligne                 # jetons par message
        assert "| Couperet |" in rapport and "## Tours à relire" in rapport

    def test_les_tours_non_livres_ne_comptent_pas_dans_les_taux(self):
        tours = [_tour("designation_action", juste=False, livre=False), _tour("designation_action", juste=False, livre=False)]
        rapport = ed.rediger_rapport({REFERENCE: tours}, REFERENCE, ed.TARIFS_RELEVES)
        ligne = next(l for l in rapport.splitlines() if l.startswith("| Désignation"))
        assert "| — |" in ligne and "cible non livrée" in ligne

    def test_ca6_l_allegement_est_propose_avant_le_modele(self):
        evaluations = _evaluations(**{
            REFERENCE: [_tour("plusieurs_actions", juste=False), _tour("plusieurs_actions")],
            MODELE_8B: [_tour("plusieurs_actions"), _tour("plusieurs_actions")],
        })
        rapport = ed.rediger_rapport(evaluations, REFERENCE, ed.TARIFS_RELEVES)
        section = rapport.split("### Plusieurs actions dans une phrase")[1].split("##")[0]
        assert section.index("Allègement d'abord") < section.index("Modèle ensuite")
        assert "Tour de complément" in section
        assert f"`{MODELE_8B}` tient la catégorie" in section

    def test_ca6_le_surcout_est_chiffre_aux_deux_volumes(self):
        evaluations = _evaluations(**{
            REFERENCE: [_tour("negations", juste=False, tin=4000, tout=100)],
            MODELE_SMALL: [_tour("negations", tin=4000, tout=100)],
        })
        rapport = ed.rediger_rapport(evaluations, REFERENCE, ed.TARIFS_RELEVES)
        # 50 msg/j : 1500 msg × (4000×0,15 + 100×0,60 − 4000×0,10 − 100×0,10) / 1e6 = +0,3825 → +0,38
        assert "+0.38 $/mois (régime stable, 50 messages/jour)" in rapport
        assert "+1.50 $/mois (mois de découverte, 200 messages/jour)" in rapport

    def test_ca6_aucun_modele_ne_corrige_est_dit_franchement(self):
        evaluations = _evaluations(**{
            REFERENCE: [_tour("negations", juste=False)], MODELE_8B: [_tour("negations", juste=False)],
        })
        rapport = ed.rediger_rapport(evaluations, REFERENCE, ed.TARIFS_RELEVES)
        assert "aucun des modèles comparés ne tient cette catégorie" in rapport

    def test_une_categorie_non_livree_renvoie_a_la_livraison_pas_au_modele(self):
        evaluations = _evaluations(**{REFERENCE: [_tour("designation_action", juste=False, livre=False)],
                                      MODELE_8B: [_tour("designation_action", livre=False)]})
        rapport = ed.rediger_rapport(evaluations, REFERENCE, ed.TARIFS_RELEVES)
        section = rapport.split("### Désignation d'une action (A1…A5)")[1].split("##")[0]
        assert "Préchargement des actions récentes" in section
        assert "sans objet tant que la brique n'existe pas" in section
        assert "Surcoût" not in section

    def test_un_couperet_met_la_categorie_en_echec_meme_a_100_pour_cent(self):
        bilan = ed.Bilan([_tour("doutes", couperets=("ecriture_sans_attente",)) for _ in range(3)])
        assert bilan.bon_outil == (3, 3) and bilan.statut == "echec"

    def test_toutes_les_categories_qui_tiennent_ne_demandent_aucun_allegement(self):
        rapport = ed.rediger_rapport({REFERENCE: [_tour("negations")]}, REFERENCE, ed.TARIFS_RELEVES)
        assert "aucun allègement ni changement de modèle" in rapport

    def test_chaque_categorie_a_un_allegement_du_cadrage(self):
        assert set(ed.ALLEGEMENTS) == set(ed.CATEGORIES)

    def test_ca7_la_grille_tarifaire_et_le_cache_sont_releves(self):
        evaluations = _evaluations(**{REFERENCE: [_tour("negations", cache=3000)], MODELE_8B: [_tour("negations")]})
        rapport = ed.rediger_rapport(evaluations, REFERENCE, ed.TARIFS_RELEVES)
        assert "Grille du 2026-10-27" in rapport
        assert "À confirmer" in rapport
        assert "cached input tokens reduce input cost by up to 90 %" in rapport
        assert "3000 (75 %)" in rapport          # part du prompt servie par le cache, mesurée
        assert "0 (0 %)" in rapport

    def test_une_grille_confirmee_remplace_le_releve(self, tmp_path):
        chemin = tmp_path / "t.json"
        chemin.write_text('{"date": "2026-11-02", "source": "console.mistral.ai", '
                          '"modeles": {"mistral/ministral-3b-latest": [0.04, 0.04]}}', encoding="utf-8")
        tarifs = ed.charger_tarifs(chemin)
        rapport = ed.rediger_rapport({REFERENCE: [_tour("negations")]}, REFERENCE, tarifs)
        assert "Grille du 2026-11-02" in rapport and "console.mistral.ai" in rapport
        assert "Confirmée." in rapport

    def test_un_tarif_inconnu_n_invente_aucun_cout(self):
        tarifs = {**ed.TARIFS_RELEVES, "modeles": {}}
        evaluations = _evaluations(**{REFERENCE: [_tour("negations", juste=False)], MODELE_8B: [_tour("negations")]})
        rapport = ed.rediger_rapport(evaluations, REFERENCE, tarifs)
        assert "tarif inconnu" in rapport

    def test_les_couperets_sont_comptes_par_modele(self):
        evaluations = _evaluations(**{
            REFERENCE: [_tour("doutes", couperets=("ecriture_sans_attente", "outil_interdit"))],
            MODELE_8B: [_tour("doutes")],
        })
        rapport = ed.rediger_rapport(evaluations, REFERENCE, ed.TARIFS_RELEVES)
        modele = rapport.split("## Couperets du modèle")[1]
        ligne = next(l for l in modele.splitlines() if l.startswith("| écriture proposée"))
        assert ligne.endswith("| 1 | 0 |")
        assert "2 couperet(s) franchi(s)" in rapport

    def test_le_rapport_ne_contient_aucune_cle(self):
        rapport = ed.rediger_rapport({REFERENCE: [_tour("negations")]}, REFERENCE, ed.TARIFS_RELEVES)
        assert not re.search(r"(sk-|[A-Za-z0-9]{32,})", rapport)


# ═════════════════════════════════════════════════════════════════════════════
# Le programme
# ═════════════════════════════════════════════════════════════════════════════
class TestProgramme:
    def test_dry_run_ne_fait_aucun_appel_et_dit_l_etat_de_la_cle(self, monkeypatch, capsys):
        monkeypatch.delenv(ed.VARIABLE_CLE_MESURE, raising=False)

        def interdit(**arguments):
            raise AssertionError("appel réseau pendant un dry-run")

        monkeypatch.setattr(passerelle, "appeler_chat_outils", interdit)
        assert ed.main(["--dry-run"]) == 0
        sortie = capsys.readouterr().out
        assert "Plan de la mesure" in sortie and "ministral-3b-latest" in sortie
        assert ed.VARIABLE_CLE_MESURE in sortie

    def test_sans_cle_la_mesure_sort_en_erreur_sans_appel(self, monkeypatch, capsys):
        monkeypatch.delenv(ed.VARIABLE_CLE_MESURE, raising=False)
        monkeypatch.setattr(passerelle, "appeler_chat_outils",
                            lambda **a: (_ for _ in ()).throw(AssertionError("appel réseau")))
        assert ed.main(["--sans-rapport"]) == 2
        assert ed.VARIABLE_CLE_MESURE in capsys.readouterr().err

    def test_la_cle_du_bot_arrete_la_mesure(self, monkeypatch, capsys):
        monkeypatch.setenv("MISTRAL_API_KEY", "meme-cle")
        monkeypatch.setenv(ed.VARIABLE_CLE_MESURE, "meme-cle")
        assert ed.main(["--sans-rapport"]) == 2
        assert "identique" in capsys.readouterr().err

    def test_le_filtre_de_categorie_et_la_limite_reduisent_le_plan(self, monkeypatch, capsys):
        monkeypatch.delenv(ed.VARIABLE_CLE_MESURE, raising=False)
        ed.main(["--dry-run", "--categorie", "doutes,negations", "--limite", "2"])
        assert "dialogues      : 2" in capsys.readouterr().out

    def test_une_categorie_inconnue_est_refusee(self):
        with pytest.raises(SystemExit):
            ed.main(["--dry-run", "--categorie", "inconnue"])

    def test_mesure_complete_simulee_ecrit_le_rapport_et_restitue_le_modele(self, monkeypatch, tmp_path):
        """Le programme de bout en bout, modèle simulé : rapport écrit, état de la passerelle restitué."""
        monkeypatch.setenv(ed.VARIABLE_CLE_MESURE, "cle-de-mesure-distincte")
        monkeypatch.setenv("MISTRAL_API_KEY", "cle-du-bot")
        monkeypatch.setattr(ed.time, "sleep", lambda s: None)
        monkeypatch.setattr(passerelle, "appeler_chat_outils",
                            lambda **a: _reponse(_appel("hors_perimetre", raison="Je ne sais pas encore.")))
        avant = (passerelle.GROQ_MODELE_PAR_TYPE[passerelle.TYPE_AGENT], passerelle.MISTRAL_API_KEY)
        chemin = tmp_path / "rapport.md"

        code = ed.main(["--modeles", REFERENCE, "--categorie", "hors_catalogue", "--pause", "0",
                        "--rapport", str(chemin)])

        assert code == 0
        assert (passerelle.GROQ_MODELE_PAR_TYPE[passerelle.TYPE_AGENT], passerelle.MISTRAL_API_KEY) == avant
        texte = chemin.read_text(encoding="utf-8")
        assert "US-256" in texte and "Hors catalogue" in texte
        assert "Clé de mesure distincte de celle du bot : oui" in texte
        assert "cle-de-mesure-distincte" not in texte

    def test_seul_le_chemin_de_la_passerelle_appelle_un_modele(self):
        """L'audit d'US-092 : aucun appel direct au SDK, tout passe par `llm.passerelle`."""
        source = open(ed.__file__, encoding="utf-8").read()
        assert not re.search(r"^\s*(import|from)\s+(groq|openai|mistralai)\b", source, re.MULTILINE)
        assert "chat.completions" not in source

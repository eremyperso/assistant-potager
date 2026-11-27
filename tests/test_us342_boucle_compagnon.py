"""
tests/test_us342_boucle_compagnon.py — La boucle du compagnon à capacités, derrière un interrupteur [US-342]
===========================================================================================================
Un bloc par critère d'acceptance (CA1 à CA7) et le scénario Gherkin.

Le modèle est TOUJOURS simulé ici : ces tests vérifient le code de la boucle (interrupteur, outils, étapes, texte,
cartes, garde-fous, type d'appel), jamais ce que Mistral Small 4 en fait. CA8 et CA8a se mesurent sur le jeu
d'évaluation (`tools/evaluer_compagnon.py --moteur capacites,boucle`), avec accord : rien ici ne les remplace.
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import sessionmaker

from app import config
from app.services import telegram_notify
from app.services.capacites import registre as svc_registre
from app.services.compagnon import boucle as svc_boucle
from app.services.compagnon import deux_canaux
from app.services.compagnon import echange_pwa as svc_echange
from app.services.compagnon import fil as svc_fil
from app.services.compagnon import orchestrateur as svc_orchestrateur
from app.services.compagnon import propositions as svc_propositions
from app.services.context import TenantContext
from database.models import CultureConfig, EchangeConversation, Evenement, Parcelle, Proposition
from llm import passerelle
from llm.passerelle import AppelOutil, ReponseOutils
from tests.test_us290_serveur_mcp import fabrique, jardin  # noqa: F401 — fixtures partagées
from tools.jeu_evaluation import moteurs

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
JOUR = date(2026, 11, 14)
MAINTENANT = datetime(2026, 11, 14, 9, 30)


def _reponse(*appels: AppelOutil, texte: str = "", statut: str = passerelle.STATUT_OK) -> ReponseOutils:
    return ReponseOutils(texte=texte, modele="mistral/mistral-small-2603", appel_type=passerelle.TYPE_COMPAGNON,
                         tokens_in=1000, tokens_out=50, tokens_cache=800, latence_ms=300, appels=tuple(appels),
                         statut=statut)


def _appel(nom: str, /, **arguments) -> AppelOutil:
    return AppelOutil(nom=nom, arguments=arguments, id=f"id_{nom}")


class ModeleScripte:
    """Un modèle simulé qui rend ses réponses dans l'ordre et garde chaque appel (historique figé)."""

    def __init__(self, *reponses):
        self.reponses = list(reponses)
        self.appels: list[dict] = []

    def __call__(self, **arguments):
        self.appels.append({**arguments, "historique": [dict(m) for m in arguments.get("historique") or []]})
        if not self.reponses:
            return _reponse(texte="(fin)")
        r = self.reponses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


class ExecuteurEspion:
    """Un exécuteur de capacités sans base : rend les données prévues et note les appels."""

    def __init__(self, donnees: dict | None = None):
        self.donnees = donnees or {}
        self.appels: list[tuple[str, dict]] = []

    def __call__(self, nom: str, arguments: dict) -> svc_boucle.ResultatOutil:
        self.appels.append((nom, arguments))
        d = self.donnees.get(nom, {"ok": True})
        return svc_boucle.ResultatOutil(json.dumps(d, ensure_ascii=False), donnees=d)


def _tour(modele, executer=None, fil=None, **options) -> svc_boucle.TourBoucle:
    return svc_boucle.jouer_tour(CTX, options.pop("phrase", "salut"), fil=fil or svc_fil.Fil(),
                                 executer=executer or ExecuteurEspion(), appeler=modele, jour=JOUR,
                                 maintenant=MAINTENANT, **options)


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — l'interrupteur : la PWA seulement, l'ancien moteur par défaut
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def boucle_espion(monkeypatch):
    appels: list[tuple] = []

    def repondre(ctx, texte, *, canal, contexte=None):
        appels.append((texte, canal, contexte))
        return svc_boucle.TourBoucle(phrase=texte, texte="réponse de la boucle")

    monkeypatch.setattr(svc_boucle, "repondre", repondre)
    return appels


def _distribuer(texte: str, canal: svc_orchestrateur.Canal):
    import asyncio

    return asyncio.run(svc_orchestrateur.distribuer(texte, CTX, canal))


def test_ca1_par_defaut_l_ancien_moteur_repond(monkeypatch, boucle_espion):
    assert config.COMPAGNON_MOTEUR == config.COMPAGNON_MOTEUR_ANCIEN  # .env.test ne le pose pas
    monkeypatch.setattr(svc_orchestrateur.svc_interpreteur, "interpreter", lambda *a, **k: None)
    distribution = _distribuer("j'aimerai planter des salades", svc_orchestrateur.Canal(nom="pwa"))
    assert boucle_espion == [] and distribution.moteur == "ancien"


def test_ca1_capacites_envoie_la_phrase_de_la_pwa_a_la_boucle(monkeypatch, boucle_espion):
    monkeypatch.setattr(config, "COMPAGNON_MOTEUR", config.COMPAGNON_MOTEUR_CAPACITES)
    distribution = _distribuer("j'aimerai planter des salades",
                               svc_orchestrateur.Canal(nom="pwa", journal={"culture": "salade"}))
    assert distribution.moteur == "capacites" and distribution.resultat.texte == "réponse de la boucle"
    assert boucle_espion == [("j'aimerai planter des salades", "pwa", {"culture": "salade"})]


def test_ca1_telegram_n_est_pas_touche(monkeypatch, boucle_espion):
    monkeypatch.setattr(config, "COMPAGNON_MOTEUR", config.COMPAGNON_MOTEUR_CAPACITES)
    monkeypatch.setattr(svc_orchestrateur.svc_interpreteur, "interpreter", lambda *a, **k: None)
    distribution = _distribuer("j'aimerai planter des salades", svc_orchestrateur.Canal(nom="telegram"))
    assert boucle_espion == [] and distribution.moteur == "ancien"
    assert not svc_orchestrateur.moteur_capacites("telegram") and svc_orchestrateur.moteur_capacites("pwa")


def test_ca1_une_valeur_inconnue_garde_l_ancien_moteur(monkeypatch):
    assert config.moteur_du_compagnon(" Capacites ") == "capacites"
    for brut in ("capacité", "oui", "", None, "nouveau"):
        assert config.moteur_du_compagnon(brut) == "ancien"
    monkeypatch.setenv("COMPAGNON_MOTEUR", "capacité")  # faute de frappe : signalée au démarrage
    monkeypatch.setattr(config, "_COMPAGNON_MOTEUR_BRUT", "capacité")
    assert any("COMPAGNON_MOTEUR" in l and "non retenu" in l for l in config.etat_configuration())


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — l'orchestrateur reste la porte ; gardes de dialogue et commandes tapées devant
# ═════════════════════════════════════════════════════════════════════════════
def test_ca2_la_garde_de_dialogue_du_canal_passe_avant_la_boucle(monkeypatch, boucle_espion):
    monkeypatch.setattr(config, "COMPAGNON_MOTEUR", config.COMPAGNON_MOTEUR_CAPACITES)
    distribution = _distribuer("arrête de me parler de la météo",
                               svc_orchestrateur.Canal(nom="pwa", dialogue=lambda t: True))
    assert distribution.pris_par_le_canal and distribution.garde == "dialogue" and boucle_espion == []


@pytest.mark.parametrize("texte", ["/plan", "  /calendrier salade"])
def test_ca2_une_commande_tapee_garde_son_chemin(monkeypatch, boucle_espion, texte):
    monkeypatch.setattr(config, "COMPAGNON_MOTEUR", config.COMPAGNON_MOTEUR_CAPACITES)
    monkeypatch.setattr(svc_orchestrateur.svc_interpreteur, "interpreter", lambda *a, **k: None)
    assert _distribuer(texte, svc_orchestrateur.Canal(nom="pwa")).moteur == "ancien" and boucle_espion == []


def test_ca2_le_texte_exact_d_un_bouton_garde_son_chemin(monkeypatch, boucle_espion):
    monkeypatch.setattr(config, "COMPAGNON_MOTEUR", config.COMPAGNON_MOTEUR_CAPACITES)
    monkeypatch.setattr(svc_orchestrateur.svc_interpreteur, "interpreter", lambda *a, **k: None)
    canal = svc_orchestrateur.Canal(nom="pwa", boutons_exacts=frozenset({"🗑️ supprimer"}))
    assert _distribuer("🗑️ Supprimer", canal).moteur == "ancien" and boucle_espion == []


def test_ca2_la_pwa_passe_par_l_orchestrateur(monkeypatch):
    """`echange_pwa` ne connaît pas la boucle : il présente ce que l'orchestrateur lui rend."""
    import inspect

    source = inspect.getsource(svc_echange)
    assert "svc_boucle" not in source and "boucle.repondre" not in source
    assert "svc_boucle.repondre" in inspect.getsource(svc_orchestrateur.distribuer)


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — les capacités du registre, et rien d'autre
# ═════════════════════════════════════════════════════════════════════════════
def test_ca3_le_modele_recoit_le_registre_moins_les_capacites_des_lots_suivants():
    import app.services.capacites  # noqa: F401

    attendus = sorted(n for n in svc_registre.REGISTRE if n not in svc_boucle.CAPACITES_ECARTEES)
    noms = [s["function"]["name"] for s in svc_boucle.schemas_des_outils()]
    assert noms == attendus
    for schema in svc_boucle.schemas_des_outils():
        capacite = svc_registre.REGISTRE[schema["function"]["name"]]
        assert schema["function"]["description"] == capacite.description
        assert schema["function"]["parameters"] == capacite.schema_entree()
    # Le seul chemin d'écriture de ce lot : proposer un geste (US-344 portera les autres).
    assert [n for n in noms if svc_registre.REGISTRE[n].ecriture] == ["proposer_geste"]
    assert {"situation_culture", "que_faire_maintenant", "voir_calendrier", "chercher_connaissance"} <= set(noms)


def test_ca3_aucun_outil_projete_depuis_les_commandes():
    from app.services.agent import catalogue_outils

    projetes = {s["function"]["name"] for s in catalogue_outils.schemas(catalogue_outils.PROJECTION_COMPLETE)}
    noms = set(svc_boucle.noms_des_outils())
    assert not (noms & projetes - set(svc_registre.REGISTRE))
    modele = ModeleScripte(_reponse(texte="Bonjour"))
    _tour(modele)
    assert [s["function"]["name"] for s in modele.appels[0]["outils"]] == list(svc_boucle.noms_des_outils())
    assert modele.appels[0]["tool_choice"] == "auto"


def test_ca3_une_capacite_ecartee_inventee_par_le_modele_n_est_pas_executee():
    espion = ExecuteurEspion()
    modele = ModeleScripte(_reponse(_appel("confirmer_proposition", proposition=12)), _reponse(texte="ok"))
    tour = _tour(modele, espion)
    assert espion.appels == [] and tour.appels[0].refus and "indisponible" in tour.appels[0].contenu


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — un nombre maximal d'étapes, un message clair, rien d'écrit
# ═════════════════════════════════════════════════════════════════════════════
def test_ca4_au_dela_des_etapes_un_message_clair_et_rien_en_attente():
    abandonnees: list = []
    espion = ExecuteurEspion({"proposer_geste": {"proposition": 77, "etat": "en_attente"}})
    modele = ModeleScripte(_reponse(_appel("proposer_geste", type="semis", culture="radis", quantite=2)),
                           *[_reponse(_appel("voir_plan")) for _ in range(10)])
    tour = _tour(modele, espion, abandonner=abandonnees.extend)
    assert tour.borne and tour.etapes == svc_boucle.ETAPES_MAX == 6
    assert tour.texte == svc_boucle.TEXTE_BORNE and "Rien n'a été noté" in tour.texte
    assert abandonnees == [77] and tour.propositions == []
    # La dernière étape n'exécute pas ses appels : 5 étapes exécutées (une proposition, quatre lectures).
    assert len(espion.appels) == 5
    # Le fil reste lisible : aucun appel d'outil sans résultat, et la réponse montrée termine le tour.
    assert tour.messages[-1] == {"role": "assistant", "content": svc_boucle.TEXTE_BORNE}
    appels = [tc["id"] for m in tour.messages for tc in (m.get("tool_calls") or [])]
    assert appels and len(appels) == len([m for m in tour.messages if m["role"] == "tool"])


def test_ca4_le_nombre_d_etapes_est_reglable():
    modele = ModeleScripte(*[_reponse(_appel("voir_plan")) for _ in range(5)])
    assert _tour(modele, etapes_max=2).etapes == 2
    assert config._entier_strictement_positif("INEXISTANTE_US342", 6) == 6


def test_ca4_un_modele_indisponible_abandonne_les_propositions_du_tour():
    abandonnees: list = []
    espion = ExecuteurEspion({"proposer_geste": {"proposition": 5}})
    modele = ModeleScripte(_reponse(_appel("proposer_geste", type="semis", culture="radis", quantite=2)),
                           passerelle.QuotaLLMDepasseError("429"))
    with pytest.raises(passerelle.LLMIndisponibleError):
        _tour(modele, espion, abandonner=abandonnees.extend)
    assert abandonnees == [5]


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — le texte du modèle ; le code n'ajoute que carte, source et lien
# ═════════════════════════════════════════════════════════════════════════════
def test_ca5_le_texte_montre_est_celui_du_modele():
    texte = "Pas maintenant : la prochaine fenêtre est en février.  "
    tour = _tour(ModeleScripte(_reponse(_appel("situation_culture", culture="salade")), _reponse(texte=texte)))
    assert tour.texte == texte.strip()


def test_ca5_la_source_et_le_lien_viennent_des_capacites():
    espion = ExecuteurEspion({
        "chercher_connaissance": {"passages": [{"source": "Fiche salade — conduite", "texte": "…"},
                                               {"source": "Fiche salade — conduite", "texte": "…"},
                                               {"source": "Guide de la pépinière", "texte": "…"}]},
        "ouvrir_dans_l_application": {"lien": "https://potager.test/plan?parcelle=Sud", "texte": "Ouvre…"},
    })
    modele = ModeleScripte(_reponse(_appel("chercher_connaissance", requete="arroser"),
                                    _appel("ouvrir_dans_l_application", ecran="plan")), _reponse(texte="Voilà."))
    tour = _tour(modele, espion)
    assert tour.sources == ["Fiche salade — conduite", "Guide de la pépinière"]
    assert tour.liens == [{"url": "https://potager.test/plan?parcelle=Sud", "libelle": "Ouvrir dans l'application"}]
    donnees = svc_echange._presenter_boucle(CTX, tour).en_donnees()
    assert donnees["texte"] == "Voilà." and donnees["sources"] == tour.sources and donnees["liens"] == tour.liens
    assert donnees["moteur"] == "capacites" and donnees["propositions"] == []


def test_ca5_une_reponse_de_l_ancien_moteur_ne_change_pas_de_forme():
    donnees = svc_echange.ReponseCompagnon(texte="Bonjour").en_donnees()
    assert "liens" not in donnees and "sources" not in donnees and "moteur" not in donnees


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — un prompt court et générique ; CA6b — une consultation n'attend jamais
# ═════════════════════════════════════════════════════════════════════════════
def test_ca6_le_prompt_est_court_generique_et_porte_les_regles():
    prompt = svc_boucle.PROMPT_FIXE
    lignes = prompt.strip().splitlines()
    assert 8 <= len(lignes) <= 16
    bas = prompt.lower()
    for regle in ("tu lis avant de répondre", "n'invente jamais une parcelle", "quantité",
                  "l'application montre une carte", "jamais de dose", "produit de traitement", "données du jardinier"):
        assert regle in bas, regle
    for scenario in ("salade", "tomate", "radis", "haricot", "planche", "novembre", "/calendrier", "b01"):
        assert scenario not in bas, scenario
    variable = svc_boucle.prompt_variable(JOUR, svc_fil.Fil())
    assert variable == "\nAujourd'hui : samedi 2026-11-14."


def test_ca6_le_prompt_ne_cite_aucune_formulation_renouvelable_du_jeu():
    from tools.jeu_evaluation import jeu as j

    jeu = j.charger()
    assert svc_boucle.PROMPT_FIXE in j.textes_des_prompts_livres()
    assert j.controler_renouvelables(jeu, [svc_boucle.PROMPT_FIXE]) == []


def test_ca6b_une_consultation_est_lue_et_montree_sans_proposition():
    espion = ExecuteurEspion({"voir_calendrier": {"culture": "salade", "fenetres": ["mars à septembre"]}})
    modele = ModeleScripte(_reponse(_appel("voir_calendrier", culture="salade")),
                           _reponse(texte="Calendrier de la salade : plantation de mars à septembre."))
    tour = _tour(modele, espion, phrase="/calendrier salade, tu peux me le montrer ?")
    assert tour.propositions == [] and "mars à septembre" in tour.texte
    assert svc_echange._presenter_boucle(CTX, tour).vers == svc_echange.VERS_REPONSE


def test_ca6b_une_consultation_n_est_pas_proposable_au_registre():
    from app.services.capacites import commandes

    assert "proposer_commande" in svc_boucle.CAPACITES_ECARTEES
    proposables = commandes.formes_proposables()
    assert proposables and all(f.confirmation for f in proposables)
    assert ("calendrier", None) not in {f.cle for f in proposables}


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — la passerelle, un type d'appel à part
# ═════════════════════════════════════════════════════════════════════════════
def test_ca7_chaque_appel_passe_par_la_passerelle_sous_le_type_compagnon():
    modele = ModeleScripte(_reponse(_appel("voir_plan")), _reponse(texte="ok"))
    _tour(modele)
    assert [a["appel_type"] for a in modele.appels] == [passerelle.TYPE_COMPAGNON] * 2
    assert passerelle.TYPE_COMPAGNON in passerelle.TYPES_APPEL
    assert passerelle.unite_pour(passerelle.TYPE_COMPAGNON) == passerelle.UNITE_JETON
    assert config.GROQ_MODELE_PAR_TYPE["compagnon"]


def test_ca7_la_boucle_appelle_la_vraie_passerelle_par_defaut(monkeypatch):
    vus: list = []

    def appeler_chat_outils(**arguments):
        vus.append(arguments["appel_type"])
        return _reponse(texte="ok")

    monkeypatch.setattr(passerelle, "appeler_chat_outils", appeler_chat_outils)
    svc_boucle.jouer_tour(CTX, "salut", fil=svc_fil.Fil(), executer=ExecuteurEspion(), jour=JOUR,
                          maintenant=MAINTENANT)
    assert vus == ["compagnon"]


# ═════════════════════════════════════════════════════════════════════════════
# De bout en bout dans la PWA : registre réel, proposition sur le canal PWA, carte, fil
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def pwa(fabrique, jardin, monkeypatch):  # noqa: F811
    for module in list(sys.modules.values()):
        nom = getattr(module, "__name__", "") or ""
        if (nom.startswith(("app.", "utils.", "llm.", "database."))
                and isinstance(getattr(module, "SessionLocal", None), sessionmaker)):
            monkeypatch.setattr(module, "SessionLocal", fabrique)
    monkeypatch.setattr(deux_canaux, "SYNCHRONE", True)
    monkeypatch.setattr(telegram_notify, "envoyer", lambda *a, **k: None)
    monkeypatch.setattr(telegram_notify, "editer_message", lambda *a, **k: True)
    monkeypatch.setattr(config, "COMPAGNON_MOTEUR", config.COMPAGNON_MOTEUR_CAPACITES)
    with fabrique() as db:
        db.add(Parcelle(nom="Planche sud", nom_normalise="planche sud", ordre=1, actif=True,
                        potager_id=jardin["mesanges"]))
        db.add(CultureConfig(nom="radis", type_organe_recolte="végétatif"))
        db.commit()
    return SimpleNamespace(fabrique=fabrique, ctx=TenantContext(user_id=jardin["user_id"],
                                                                potager_id=jardin["mesanges"], role="owner"))


def test_bout_en_bout_un_geste_dit_devient_une_carte_sur_le_canal_pwa(pwa, monkeypatch):
    modele = ModeleScripte(
        _reponse(_appel("voir_plan")),
        _reponse(_appel("proposer_geste", type="semis", culture="radis", quantite=2, unite="rangs",
                        parcelle="Planche sud")),
        _reponse(texte="Je te prépare ce semis de radis ; confirme-le sur la carte."))
    monkeypatch.setattr(passerelle, "appeler_chat_outils", modele)
    reponse = svc_echange.repondre(pwa.ctx, "j'ai semé 2 rangs de radis sur la planche sud")
    assert reponse.texte == "Je te prépare ce semis de radis ; confirme-le sur la carte."
    assert reponse.vers == svc_echange.VERS_GESTE and len(reponse.propositions) == 1
    carte = reponse.propositions[0]
    assert carte["confirmable"] and "radis" in carte["resume"]
    with pwa.fabrique() as db:
        ligne = db.get(Proposition, carte["id"])
        assert ligne.canal == svc_propositions.CANAL_PWA  # pas « mcp »
        assert "via MCP" not in json.dumps(ligne.contenu, ensure_ascii=False)
        assert db.query(Evenement).count() == 0  # rien n'est écrit avant le bouton
        echange = db.query(EchangeConversation).one()
        assert echange.canal == "pwa" and echange.proposition_id == carte["id"]
        assert echange.texte_compagnon == reponse.texte and echange.outils == ["voir_plan", "proposer_geste"]
        roles = [m["role"] for m in echange.messages]
        assert roles == ["user", "assistant", "tool", "assistant", "tool", "assistant"]
    assert reponse.echange_id == echange.id
    # La confirmation reste celle du bouton de la carte (US-270) : le geste s'écrit alors.
    resultat = svc_echange.confirmer(pwa.ctx, carte["id"])
    assert resultat.erreur is None
    with pwa.fabrique() as db:
        assert db.query(Evenement).count() == 1


def test_bout_en_bout_le_tour_suivant_relit_le_fil_et_l_etat_de_la_carte(pwa, monkeypatch):
    modele = ModeleScripte(
        _reponse(_appel("proposer_geste", type="semis", culture="radis", quantite=2, unite="rangs",
                        parcelle="Planche sud")),
        _reponse(texte="Confirme sur la carte."),
        _reponse(texte="C'est noté."))
    monkeypatch.setattr(passerelle, "appeler_chat_outils", modele)
    carte = svc_echange.repondre(pwa.ctx, "j'ai semé 2 rangs de radis sur la planche sud").propositions[0]
    svc_echange.confirmer(pwa.ctx, carte["id"])
    svc_echange.repondre(pwa.ctx, "merci")
    historique = modele.appels[-1]["historique"]
    assert historique[0]["content"].endswith("j'ai semé 2 rangs de radis sur la planche sud")
    assert any(m.get("tool_calls") for m in historique)  # les appels du tour 1, avec leurs arguments
    derniere = historique[-1]["content"]
    assert derniere.splitlines()[0].endswith("merci")
    assert f"carte n°{carte['id']}" in derniere and "Confirmé" in derniere


def test_bout_en_bout_un_lecteur_ne_propose_rien(pwa, monkeypatch):
    lecteur = TenantContext(user_id=pwa.ctx.user_id, potager_id=pwa.ctx.potager_id, role="lecteur")
    modele = ModeleScripte(_reponse(_appel("proposer_geste", type="semis", culture="radis", quantite=2)),
                           _reponse(texte="Tu es lecteur sur ce potager."))
    monkeypatch.setattr(passerelle, "appeler_chat_outils", modele)
    reponse = svc_echange.repondre(lecteur, "j'ai semé des radis")
    assert reponse.propositions == [] and svc_registre.REFUS_LECTEUR in modele.appels[1]["historique"][-1]["content"]


# ═════════════════════════════════════════════════════════════════════════════
# La mesure joue la boucle de production (moteur `boucle`)
# ═════════════════════════════════════════════════════════════════════════════
def test_mesure_le_moteur_boucle_joue_le_code_de_production(test_db):
    m = moteurs.ModeleSimule([_reponse(texte="Bonjour"), _reponse(texte="Re-bonjour")])
    moteur = moteurs.creer_moteur("boucle", CTX, simule=True, jour=JOUR, ouvrir_session=lambda: test_db)
    moteur._appeler = m
    assert isinstance(moteur, moteurs.MoteurBoucle) and moteur.mode_confirmation == "bouton"
    moteur.ouvrir(None)
    moteur.jouer(1, phrase="salut")
    moteur.jouer(2, phrase="ça va ?")
    premier, second = m.appels
    assert premier["prompt_fixe"] == svc_boucle.PROMPT_FIXE and premier["appel_type"] == passerelle.TYPE_COMPAGNON
    assert [s["function"]["name"] for s in premier["outils"]] == list(svc_boucle.noms_des_outils())
    assert [x["role"] for x in second["historique"]] == ["user", "assistant", "user"]


def test_mesure_le_clic_confirmer_est_dit_au_tour_suivant(test_db):
    m = moteurs.ModeleSimule([
        _reponse(_appel("proposer_geste", type="semis", culture="radis", quantite=2, date="2026-11-14")),
        _reponse(texte="Confirme sur la carte."), _reponse(texte="Noté.")])
    moteur = moteurs.MoteurBoucle(CTX, appeler=m, modele_simule=True, jour=JOUR, ouvrir_session=lambda: test_db)
    t1 = moteur.jouer(1, phrase="j'ai semé 2 rangs de radis")
    assert t1.proposition_en_attente and "[Proposition]" in t1.texte
    t2 = moteur.jouer(2, clic="Confirmer")
    assert t2.executions and t2.executions[0]["simule"]
    moteur.jouer(3, phrase="merci")
    assert "Confirmé" in m.appels[-1]["historique"][-1]["content"]


def test_mesure_le_moteur_boucle_refuse_une_ecriture_qu_il_ne_sait_pas_simuler(test_db):
    with pytest.raises(RuntimeError, match="ne sait pas jouer"):
        moteurs.RegistreMesure(CTX, jour=JOUR, noms=("voir_plan", "proposer_commande"))


# ═════════════════════════════════════════════════════════════════════════════
# Gherkin (modèle simulé : le comportement du vrai modèle se mesure, CA8a)
# ═════════════════════════════════════════════════════════════════════════════
def test_gherkin_salades_le_14_novembre(monkeypatch):
    """Given COMPAGNON_MOTEUR vaut « capacites » et nous sommes le 14 novembre / When « j'aimerai planter des
    salades » / Then la situation de la culture est lue avant de répondre, la réponse dit « pas maintenant » et la
    prochaine fenêtre, aucune commande voisine n'est proposée."""
    monkeypatch.setattr(config, "COMPAGNON_MOTEUR", config.COMPAGNON_MOTEUR_CAPACITES)
    espion = ExecuteurEspion({"situation_culture": {
        "culture": "salade", "verdict": "pas_ce_mois_ci",
        "texte": "Rien à semer ni planter ce mois-ci. Prochaine fenêtre : semer en pépinière février à mars."}})
    modele = ModeleScripte(
        _reponse(_appel("situation_culture", culture="salades")),
        _reponse(texte="Ce n'est pas le moment : la prochaine fenêtre est le semis en pépinière, de février à mars."))
    tour = _tour(modele, espion, phrase="j'aimerai planter des salades")
    assert espion.appels[0] == ("situation_culture", {"culture": "salades"})
    assert "pas le moment" in tour.texte and "février à mars" in tour.texte
    assert tour.propositions == [] and tour.liens == []
    assert not any(n.startswith("proposer_") or n in ("programmer_rappel",) for n, _ in espion.appels)

@pytest.mark.parametrize("phrase, messages, quantite, gardee", [
    ("semé haricots hier", [], 1, False),
    ("j'ai planté une tomate", [], 1, True),
    ("récolté 500 g de fraises", [], 0.5, True),
    ("planté 10 choux par rang sur 3 rangs", [], 30, True),
    ("oui", [{"role": "assistant", "content": "Je note 12 plants, ça te va ?"}], 12, True),
    ("planté le lot 2", [{"role": "tool", "content": '{"plants": 5}'}], 5, True),
    ("planté des tomates", [{"role": "user", "content": "[2026-11-14 10:00] salut\ncarte 7 confirmée"}], 7, False),
])
def test_une_quantite_non_dite_est_retiree_de_la_proposition(phrase, messages, quantite, gardee):
    arguments = {"type": "semis", "culture": "haricot", "quantite": quantite, "unite": "rangs"}
    retenus = svc_boucle._ancrer_la_quantite("proposer_geste", arguments, phrase, messages)
    assert ("quantite" in retenus) is gardee and ("unite" in retenus) is gardee

def test_les_noms_des_parcelles_sont_donnes_au_modele():
    variable = svc_boucle.prompt_variable(JOUR, svc_fil.Fil(), ("planche légumes", "serre"))
    assert variable == "\nAujourd'hui : samedi 2026-11-14.\nParcelles du potager : planche légumes, serre."

@pytest.mark.parametrize("phrase, messages, parcelle, gardee", [
    ("semé haricots hier", [], "planche légumes", False),
    ("planté sur la planche legume", [], "planche légumes", True),
    ("planté dans la serre", [], "Serre", True),
    ("planté des radis ce matin", [], "A", False),
    ("6 plants", [{"role": "user", "content": "[2026-11-14 10:00] planté sur la planche légumes"}], "planche légumes", True),
    ("oui", [{"role": "assistant", "content": "Je la mets sur la planche légumes ?"}], "planche légumes", True),
    ("planté des tomates", [{"role": "tool", "content": "Sur quelle parcelle ? planche légumes."}], "planche légumes", False),
])
def test_une_parcelle_non_dite_est_retiree_de_la_proposition(phrase, messages, parcelle, gardee):
    arguments = {"type": "plantation", "culture": "tomate", "parcelle": parcelle}
    retenus = svc_boucle._ancrer_la_parcelle("proposer_geste", arguments, phrase, messages)
    assert ("parcelle" in retenus) is gardee


def test_une_reponse_qui_annonce_une_carte_inexistante_est_corrigee():
    tour = svc_boucle.TourBoucle(phrase="x")
    tour.appels.append(svc_boucle.AppelBoucle("proposer_geste", {}, "{}", False, {}))
    assert svc_boucle._sans_carte_annoncee("Confirme dans l'application.", tour).endswith(svc_boucle.TEXTE_AUCUNE_CARTE)
    assert svc_boucle._sans_carte_annoncee("Sur quelle parcelle ?", tour) == "Sur quelle parcelle ?"
    tour.propositions.append(1)
    assert svc_boucle._sans_carte_annoncee("Confirme.", tour) == "Confirme."


def test_la_parcelle_retiree_est_dite_au_modele():
    sans = svc_boucle._dire_la_parcelle_retiree(svc_boucle.ResultatOutil("{}", donnees={}), "serre")
    assert "« serre » a été retirée" in sans.contenu and "sans_parcelle=true" in sans.contenu
    avec = svc_boucle._dire_la_parcelle_retiree(svc_boucle.ResultatOutil("{}", donnees={"proposition": 3}), "serre")
    assert "sans_parcelle" not in avec.contenu

@pytest.mark.parametrize("phrase, refusee", [
    ("je ne sais pas, à toi de voir", True), ("comme tu veux", True), ("oui", False),
    ("oui vas-y note-le", False), ("j'ai perdu 3 tomates", False),
])
def test_une_reponse_qui_ne_tranche_pas_ne_prepare_aucune_carte(phrase, refusee):
    tour = svc_boucle.TourBoucle(phrase=phrase)
    assert (svc_boucle._garde("proposer_geste", {}, tour) == svc_boucle.TEXTE_INDECIS) is refusee
    assert svc_boucle._garde("voir_plan", {}, tour) is None

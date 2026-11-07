"""
tests/test_us273_analyse_approfondie.py — Analyser le potager en profondeur, sans rien modifier [US-273]
======================================================================================================
Mode Extra (articulation §5.4) : une boucle de LECTURE seule, qui croise récoltes, météo, parcelles et
savoir, et rend une synthèse avec ses sources. Le bouton « Approfondir » de la PWA et `/approfondir`
du bot lancent la même analyse (`orchestrateur.analyser_le_potager`).

* CA1 — le bouton (mode `analyse` de `POST /compagnon/messages`) et la commande du bot ;
* CA2 — R2 : aucun outil d'écriture n'est atteignable, un appel d'écriture est refusé sans être exécuté ;
* CA3 — type d'appel `analyse`, bornes de tours et de jetons réglables, mention quand elles coupent ;
* CA4 — les chiffres cités sont ceux lus, les sources sont citées ;
* CA5 — l'analyse peut finir par des pistes, jamais par une action : rien n'est proposé ni écrit.

Aucun appel réseau : la passerelle, les lectures et la météo sont simulées.
"""
from __future__ import annotations

import ast
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app import config
from app.services.agent import catalogue_outils, lecture, savoir
from app.services.compagnon import analyse
from app.services.compagnon import echange_pwa as svc_echange
from app.services.compagnon import orchestrateur as svc_orchestrateur
from app.services.context import TenantContext, default_context
from database.models import Evenement, Proposition
from llm import passerelle
from llm.passerelle import AppelOutil, ReponseOutils

CTX = default_context()
QUESTION = "pourquoi mes tomates ont peu donné ?"
RECOLTES = json.dumps({"donnees": [{"culture": "tomate", "recolte_kg": 12, "plants": 8}]})
METEO = json.dumps({"lieu": "ton potager", "pluie_mm_total": 24})
SOURCE = "Mildiou de la tomate"


# ═════════════════════════════════════════════════════════════════════════════
# Outillage
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def modele():
    with patch.object(passerelle, "appeler_chat_outils") as faux:
        yield faux


@pytest.fixture(autouse=True)
def lectures_simulees(monkeypatch):
    """Rien ne touche la base, la météo ni le RAG : les lectures rendent des données fixes."""
    monkeypatch.setattr(savoir, "precharger", lambda ctx, releves: "")
    monkeypatch.setattr(lecture, "lire", lambda arguments, ctx: RECOLTES)

    def _executer(nom, arguments, ctx, releves):
        if nom == catalogue_outils.OUTIL_METEO:
            releves.ajouter(METEO, resume="24 mm de pluie en trois jours")
            return METEO
        if nom == catalogue_outils.OUTIL_CHERCHER_CONNAISSANCE:
            releves.ajouter("{}", resume="Le mildiou aime l'humidité.", source=SOURCE)
            return "{}"
        releves.ajouter(RECOLTES)
        return RECOLTES

    monkeypatch.setattr(savoir, "executer", _executer)
    monkeypatch.setattr(config, "ANALYSE_MAX_TOURS", 6, raising=False)
    monkeypatch.setattr(config, "ANALYSE_MAX_JETONS", 20000, raising=False)


def _reponse(texte: str = "", *appels: AppelOutil, tokens: int = 950) -> ReponseOutils:
    return ReponseOutils(
        texte=texte, modele="test", appel_type=passerelle.TYPE_ANALYSE, tokens_in=tokens - 50, tokens_out=50,
        latence_ms=100, appels=tuple(appels), statut=passerelle.STATUT_OK,
    )


def _appel(nom: str, ident: str = "a1", **arguments) -> AppelOutil:
    return AppelOutil(nom, arguments, id=ident)


def _lecture(ident: str = "a1") -> AppelOutil:
    return _appel("lire", ident, quoi="parcelles")


def _comptes(db) -> tuple[int, int]:
    return db.query(Evenement).count(), db.query(Proposition).count()


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — le bouton « Approfondir » et la commande du bot
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1Lancement:

    def test_ca1_le_mode_analyse_de_la_pwa_lance_l_analyse(self, modele):
        modele.side_effect = [
            _reponse("", _lecture(), _appel("meteo", "a2")),
            _reponse("Tu as récolté 12 kg sur 8 plants, d'après ton carnet."),
        ]
        reponse = svc_echange.repondre(CTX, QUESTION, mode="analyse")
        assert reponse.vers == svc_echange.VERS_ANALYSE
        assert "12 kg" in reponse.texte
        assert reponse.propositions == []
        donnees = reponse.en_donnees()
        assert donnees["vers"] == "analyse" and "sources" in donnees and "borne" in donnees

    def test_ca1_les_autres_reponses_ne_portent_pas_de_champ_d_analyse(self):
        donnees = svc_echange.ReponseCompagnon(texte="ok", vers=svc_echange.VERS_QUESTION).en_donnees()
        assert "sources" not in donnees and "borne" not in donnees

    def test_ca1_la_route_accepte_le_mode_analyse(self, modele):
        from fastapi.testclient import TestClient

        from app.api.main import app, get_current_user_ctx

        modele.side_effect = [_reponse("Synthèse de ta saison."), ]
        app.dependency_overrides[get_current_user_ctx] = default_context
        try:
            with TestClient(app) as client:
                ok = client.post("/compagnon/messages", json={"texte": QUESTION, "mode": "analyse"})
        finally:
            app.dependency_overrides.pop(get_current_user_ctx, None)
        assert ok.status_code == 200
        assert ok.json()["vers"] == "analyse" and "Synthèse de ta saison." in ok.json()["texte"]

    def test_ca1_une_question_vide_est_refusee(self):
        with pytest.raises(svc_echange.TexteVideError):
            svc_echange.repondre(CTX, "   ", mode="analyse")

    def test_ca1_le_bot_lance_l_analyse_par_approfondir(self):
        from app.bot import commandes_analyse

        attente = SimpleNamespace(edit_text=AsyncMock())
        message = SimpleNamespace(reply_text=AsyncMock(return_value=attente))
        update = SimpleNamespace(message=message)
        ctx = SimpleNamespace(args=["pourquoi", "mes", "tomates", "?"])
        resultat = analyse.ResultatAnalyse(texte="Synthèse. " + analyse.TEXTE_RIEN_MODIFIE)

        with patch.object(commandes_analyse, "current_context", return_value=CTX), \
             patch.object(svc_orchestrateur, "analyser_le_potager", return_value=resultat) as lancer:
            asyncio.run(commandes_analyse.cmd_approfondir(update, ctx))

        lancer.assert_called_once_with(CTX, "pourquoi mes tomates ?")
        assert "Synthèse." in attente.edit_text.call_args.args[0]

    def test_ca1_sans_question_le_bot_explique_l_usage_sans_appeler_le_modele(self):
        from app.bot import commandes_analyse

        message = SimpleNamespace(reply_text=AsyncMock())
        with patch.object(svc_orchestrateur, "analyser_le_potager") as lancer:
            asyncio.run(commandes_analyse.cmd_approfondir(SimpleNamespace(message=message), SimpleNamespace(args=[])))
        lancer.assert_not_called()
        assert "/approfondir" in message.reply_text.call_args.args[0]

    def test_ca1_le_bot_dit_la_panne_du_modele(self):
        from app.bot import commandes_analyse

        attente = SimpleNamespace(edit_text=AsyncMock())
        message = SimpleNamespace(reply_text=AsyncMock(return_value=attente))
        with patch.object(commandes_analyse, "current_context", return_value=CTX), \
             patch.object(svc_orchestrateur, "analyser_le_potager", side_effect=passerelle.LLMIndisponibleError("x")):
            asyncio.run(commandes_analyse.cmd_approfondir(
                SimpleNamespace(message=message), SimpleNamespace(args=["pourquoi"])))
        assert "⏳" in attente.edit_text.call_args.args[0]

    def test_ca1_la_commande_est_au_menu_a_l_aide_et_hors_de_l_interpreteur(self):
        from app.bot import aide
        from app.services import menu_commandes as menu

        assert "approfondir" in menu.DESCRIPTIONS and len(menu.DESCRIPTIONS["approfondir"]) <= menu.LONGUEUR_MAX_DESCRIPTION
        assert "approfondir" in menu.ORDRE_METIER
        assert "approfondir" in menu.COMMANDES_EXCLUES_INTERPRETEUR
        assert "analyse" in aide._HELP_DOMAINES and aide._HELP_CONTEXTUEL["approfondir"] is aide._HELP_CONTEXTUEL["analyse"]


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — R2 : une boucle de lecture, rien d'autre
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2LectureSeule:

    def test_ca2_la_boucle_n_expose_que_des_outils_de_lecture(self):
        assert set(analyse.noms_outils_analyse()) == set(catalogue_outils.OUTILS_DE_LECTURE)
        assert analyse.controler_lecture_seule() == []

    def test_ca2_aucun_outil_d_ecriture_du_catalogue_n_est_offert(self):
        offerts = set(analyse.noms_outils_analyse())
        for outil in catalogue_outils.outils():
            if outil.ecrit:
                assert outil.nom not in offerts, outil.nom
        for nom in (*catalogue_outils.OUTILS_DECISION, *catalogue_outils.OUTILS_CORRECTION,
                    *catalogue_outils.OUTILS_TERMINAUX):
            assert nom not in offerts

    def test_ca2_le_controle_denonce_un_outil_d_ecriture_ajoute_par_erreur(self):
        ecrivain = next(o for o in catalogue_outils.outils() if o.ecrit)
        with patch.object(analyse, "outils_analyse", return_value=[ecrivain.schema]):
            anomalies = analyse.controler_lecture_seule()
        assert any(ecrivain.nom in a for a in anomalies)

    def test_ca2_le_modele_appelle_un_outil_d_ecriture_il_est_refuse_et_rien_n_est_ecrit(self, modele, memoire_compagnon):
        with memoire_compagnon() as db:
            avant = _comptes(db)
        ecrivains = [o.nom for o in catalogue_outils.outils() if o.ecrit][:3] + ["saisir_geste", "confirmer_proposition"]
        modele.side_effect = [
            _reponse("", *[_appel(nom, f"e{i}") for i, nom in enumerate(ecrivains)], _lecture("l1")),
            _reponse("Tu as récolté 12 kg."),
        ]
        with patch.object(savoir, "executer", wraps=savoir.executer) as executer:
            resultat = analyse.analyser(QUESTION, CTX)

        assert set(resultat.refuses) == set(ecrivains)
        assert resultat.outils == ("lire",)
        # Aucun outil refusé n'a atteint un exécuteur.
        assert all(appel.args[0] in catalogue_outils.OUTILS_SAVOIR for appel in executer.call_args_list)
        # Le modèle a été informé du refus, pas de l'exécution.
        refus = [m for m in modele.call_args_list[1].kwargs["historique"]
                 if m.get("role") == "tool" and "lecture seule" in m["content"]]
        assert len(refus) == len(ecrivains)
        with memoire_compagnon() as db:
            assert _comptes(db) == avant

    def test_ca2_le_module_n_importe_aucun_chemin_d_ecriture(self):
        source = Path(analyse.__file__).read_text(encoding="utf-8")
        modules: set[str] = set()
        for noeud in ast.walk(ast.parse(source)):
            if isinstance(noeud, ast.ImportFrom):
                modules.add(noeud.module or "")
                modules.update(f"{noeud.module}.{a.name}" for a in noeud.names)
            elif isinstance(noeud, ast.Import):
                modules.update(a.name for a in noeud.names)
        interdits = ("evenements", "gestes", "executeurs", "propositions", "decisions", "corrections",
                     "gestes_conversation", "actions_menees", "database.models")
        for module in modules:
            assert not any(module.endswith(f".{nom}") or module == nom for nom in interdits), module

    def test_ca2_l_analyse_n_ecrit_ni_evenement_ni_proposition(self, modele, memoire_compagnon):
        modele.side_effect = [_reponse("", _lecture()), _reponse("Tu as récolté 12 kg. Piste : pailler.")]
        with memoire_compagnon() as db:
            avant = _comptes(db)
        svc_echange.repondre(CTX, QUESTION, mode="analyse")
        with memoire_compagnon() as db:
            assert _comptes(db) == avant

    def test_ca2_un_lecteur_peut_analyser(self, modele):
        modele.side_effect = [_reponse("Tu as récolté 12 kg.")]
        lecteur = TenantContext(user_id=CTX.user_id, potager_id=CTX.potager_id, role="reader")
        assert "12 kg" in svc_echange.repondre(lecteur, QUESTION, mode="analyse").texte


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — type d'appel, bornes, mention
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3Bornes:

    def test_ca3_le_type_d_appel_est_analyse_et_son_modele_se_regle(self, monkeypatch):
        assert passerelle.TYPE_ANALYSE == "analyse" and "analyse" in passerelle.TYPES_APPEL
        # Le dictionnaire que la passerelle lit (un autre test peut avoir rechargé `config`).
        assert passerelle.modele_pour("analyse")  # par défaut, le modèle de l'agent
        monkeypatch.setitem(passerelle.GROQ_MODELE_PAR_TYPE, "analyse", "mistral/gros-modele")
        assert passerelle.modele_pour("analyse") == "mistral/gros-modele"

    def test_ca3_chaque_appel_est_du_type_analyse(self, modele):
        modele.side_effect = [_reponse("", _lecture()), _reponse("Tu as récolté 12 kg.")]
        analyse.analyser(QUESTION, CTX)
        assert [c.kwargs["appel_type"] for c in modele.call_args_list] == ["analyse", "analyse"]

    def test_ca3_la_borne_de_tours_coupe_et_dit_la_mention(self, modele, monkeypatch):
        monkeypatch.setattr(config, "ANALYSE_MAX_TOURS", 2)
        modele.side_effect = [
            _reponse("", _lecture("a1")), _reponse("", _appel("meteo", "a2")),
            _reponse("Tu as récolté 12 kg, avec 24 mm de pluie."),   # la rédaction finale, sans outil
        ]
        resultat = analyse.analyser(QUESTION, CTX)
        assert resultat.borne == "tours" and resultat.tours == 2
        assert modele.call_count == 3 and modele.call_args_list[-1].kwargs["tool_choice"] == "none"
        assert "Analyse arrêtée" in resultat.texte and "2 tours" in resultat.texte
        assert "12 kg" in resultat.texte                       # elle rend ce qu'elle a

    def test_ca3_la_borne_de_jetons_coupe_et_dit_la_mention(self, modele, monkeypatch):
        monkeypatch.setattr(config, "ANALYSE_MAX_JETONS", 1000)
        modele.side_effect = [
            _reponse("", _lecture("a1"), tokens=1200),
            _reponse("Tu as récolté 12 kg."),                  # la rédaction finale
        ]
        resultat = analyse.analyser(QUESTION, CTX)
        assert resultat.borne == "jetons" and resultat.tours == 1
        assert modele.call_count == 2 and modele.call_args_list[-1].kwargs["tool_choice"] == "none"
        assert "Analyse arrêtée" in resultat.texte and "1000 jetons" in resultat.texte

    def test_ca3_une_analyse_qui_finit_a_temps_n_a_pas_de_mention(self, modele):
        modele.side_effect = [_reponse("", _lecture()), _reponse("Tu as récolté 12 kg.")]
        resultat = analyse.analyser(QUESTION, CTX)
        assert resultat.borne == "" and "Analyse arrêtée" not in resultat.texte

    def test_ca3_borne_atteinte_sans_texte_le_code_repond_avec_ce_qui_est_lu(self, modele, monkeypatch):
        monkeypatch.setattr(config, "ANALYSE_MAX_TOURS", 1)
        modele.side_effect = [_reponse("", _appel("meteo")), _reponse("")]
        resultat = analyse.analyser(QUESTION, CTX)
        assert "24 mm de pluie" in resultat.texte and "Analyse arrêtée" in resultat.texte

    def test_ca3_les_bornes_se_lisent_a_chaque_appel_et_ont_un_defaut(self):
        assert config.ANALYSE_MAX_TOURS >= 1 and config.ANALYSE_MAX_JETONS >= 1
        with patch.object(config, "ANALYSE_MAX_TOURS", 3), patch.object(config, "ANALYSE_MAX_JETONS", 500):
            assert analyse._bornes() == (3, 500)

    def test_ca3_une_panne_au_premier_tour_remonte_au_canal(self, modele):
        modele.side_effect = passerelle.LLMIndisponibleError("quota")
        with pytest.raises(passerelle.LLMIndisponibleError):
            analyse.analyser(QUESTION, CTX)

    def test_ca3_une_panne_en_cours_de_route_redige_avec_ce_qui_est_lu(self, modele):
        modele.side_effect = [_reponse("", _appel("meteo")), passerelle.LLMIndisponibleError("quota"),
                              passerelle.LLMIndisponibleError("quota")]
        resultat = analyse.analyser(QUESTION, CTX)
        assert "24 mm de pluie" in resultat.texte


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — les chiffres lus, les sources citées
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4ChiffresEtSources:

    def test_ca4_les_chiffres_lus_passent(self, modele):
        modele.side_effect = [_reponse("", _lecture(), _appel("meteo", "a2")),
                              _reponse("Récolte : 12 kg sur 8 plants, avec 24 mm de pluie.")]
        resultat = analyse.analyser(QUESTION, CTX)
        assert "12 kg sur 8 plants" in resultat.texte and modele.call_count == 2

    def test_ca4_un_chiffre_invente_est_renvoye_au_modele_une_fois(self, modele):
        modele.side_effect = [
            _reponse("", _lecture()),
            _reponse("Tu as perdu 40 % de ta récolte."),
            _reponse("Tu as récolté 12 kg sur 8 plants."),
        ]
        resultat = analyse.analyser(QUESTION, CTX)
        consigne = modele.call_args_list[2].kwargs["historique"][-1]
        assert consigne["role"] == "user" and "40" in consigne["content"]
        assert "40" not in resultat.texte and "12 kg" in resultat.texte

    def test_ca4_un_chiffre_toujours_invente_le_code_prend_la_main(self, modele):
        modele.side_effect = [
            _reponse("", _appel("meteo")),
            _reponse("Tu as perdu 40 % de ta récolte."),
            _reponse("Tu as perdu 40 % de ta récolte."),
        ]
        resultat = analyse.analyser(QUESTION, CTX)
        assert "40" not in resultat.texte and "24 mm de pluie" in resultat.texte

    def test_ca4_la_source_du_savoir_est_citee(self, modele):
        modele.side_effect = [
            _reponse("", _appel("chercher_connaissance", domaine="jardinage", question="mildiou")),
            _reponse("Le mildiou peut expliquer cette baisse."),
        ]
        resultat = analyse.analyser(QUESTION, CTX)
        assert SOURCE in resultat.texte and resultat.sources == (SOURCE,)

    def test_ca4_ni_dose_ni_produit(self, modele):
        modele.side_effect = [
            _reponse("", _appel("chercher_connaissance", domaine="jardinage", question="mildiou")),
            _reponse("Traite avec 20 g de bouillie bordelaise par litre."),
        ]
        resultat = analyse.analyser(QUESTION, CTX)
        assert "bouillie" not in resultat.texte and "20 g" not in resultat.texte

    def test_ca4_une_quantite_lue_n_est_pas_une_dose_mais_une_dose_inventee_l_est(self):
        releves = savoir.Releves()
        releves.ajouter(RECOLTES)
        assert not savoir.donne_une_dose_ou_un_produit("Tu as récolté 12 kg.", releves)
        assert savoir.donne_une_dose_ou_un_produit("Mets 20 g par litre.", releves)
        assert savoir.donne_une_dose_ou_un_produit("Du purin d'ortie.", releves)
        # Le dialogue garde sa règle d'avant : sans relevés, toute quantité reste suspecte.
        assert savoir.donne_une_dose_ou_un_produit("Tu as récolté 12 kg.")

    def test_ca4_le_prompt_exige_les_sources_et_les_chiffres_lus(self):
        assert "sources" in analyse.PROMPT_ANALYSE.lower() and "chiffres" in analyse.PROMPT_ANALYSE
        assert "dose" in analyse.PROMPT_ANALYSE


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — des pistes, jamais d'action
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5Pistes:

    TEXTE = "Tu as récolté 12 kg.\nPistes : pailler les pieds, espacer l'arrosage."

    def test_ca5_la_synthese_garde_ses_pistes_et_dit_que_rien_n_a_ete_modifie(self, modele):
        modele.side_effect = [_reponse("", _lecture()), _reponse(self.TEXTE)]
        resultat = analyse.analyser(QUESTION, CTX)
        assert "Pistes : pailler" in resultat.texte
        assert resultat.texte.endswith(analyse.TEXTE_RIEN_MODIFIE)
        assert "Rien n'a été modifié" in resultat.texte

    def test_ca5_les_pistes_ne_creent_aucune_proposition(self, modele, memoire_compagnon):
        modele.side_effect = [_reponse("", _lecture()), _reponse(self.TEXTE)]
        reponse = svc_echange.repondre(CTX, QUESTION, mode="analyse")
        assert reponse.propositions == []
        with memoire_compagnon() as db:
            assert db.query(Proposition).count() == 0 and db.query(Evenement).count() == 0

    def test_ca5_l_echange_rejoint_la_conversation(self, modele, memoire_compagnon):
        from database.models import EchangeConversation

        modele.side_effect = [_reponse("", _lecture()), _reponse(self.TEXTE)]
        svc_echange.repondre(CTX, QUESTION, mode="analyse")
        with memoire_compagnon() as db:
            assert db.query(EchangeConversation).count() == 1

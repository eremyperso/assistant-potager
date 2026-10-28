"""
tests/test_us233_passerelle_outils.py
[US-233] Ouvrir la passerelle aux appels d'outils et mesurer le modèle de l'agent.

Couverture des critères d'acceptance CA1 → CA8 et du scénario Gherkin. Aucun
appel réseau : le client du fournisseur est simulé. La mesure RÉELLE du modèle
(`tools/evaluer_agent.py`, quota Groq) n'est pas rejouée ici ; ce fichier
vérifie l'outil de mesure — échantillon, notation, critères, rapport — et que le
rapport livré existe et conclut.
"""
import importlib.util
import logging
import os
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import groq
import httpx
import pytest

from app.services.agent import catalogue_outils, interpreteur_agent
from app.services.context import TenantContext
from database.models import ConsoTokens
from llm import passerelle
from llm.passerelle import (
    AppelOutil,
    ContexteAppelManquantError,
    FournisseurLLMIndisponibleError,
    QuotaLLMDepasseError,
    ReponseOutils,
    STATUT_APPEL_INVALIDE,
    STATUT_OK,
    STATUT_SANS_OUTILS,
    TYPES_APPEL,
)
import tools.audit_appels_llm as audit
import tools.evaluer_agent as ev

RACINE = Path(__file__).resolve().parent.parent
CTX = TenantContext(user_id=7, potager_id=3, role="owner")
OUTILS = [{"type": "function", "function": {
    "name": "modifier_parcelle", "description": "x",
    "parameters": {"type": "object", "properties": {"parcelle": {"type": "string"}}},
}}]
URL = "https://api.groq.com/openai/v1/chat/completions"


# ═════════════════════════════════════════════════════════════════════════════
# Doubles du fournisseur
# ═════════════════════════════════════════════════════════════════════════════
def _reponse_outils(appels=(), contenu=None, tokens_in=1500, tokens_out=40, tokens_cache=0):
    """Réponse du SDK : `appels` = [(nom, arguments_json_ou_dict)]."""
    tool_calls = [
        SimpleNamespace(id=f"call_{i}", function=SimpleNamespace(name=nom, arguments=args))
        for i, (nom, args) in enumerate(appels)
    ]
    message = SimpleNamespace(content=contenu, tool_calls=tool_calls or None)
    usage = SimpleNamespace(
        prompt_tokens=tokens_in, completion_tokens=tokens_out,
        prompt_tokens_details=SimpleNamespace(cached_tokens=tokens_cache),
    )
    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)


def _erreur_400(message="bad request", code=None, imbrique=False):
    corps = {"message": message}
    if code:
        corps["code"] = code
    return groq.BadRequestError(
        message, response=httpx.Response(400, request=httpx.Request("POST", URL)),
        body={"error": corps} if imbrique else corps,
    )


def _erreur_429():
    reponse = httpx.Response(429, headers={"retry-after": "0"}, request=httpx.Request("POST", URL))
    return groq.RateLimitError("rate limit", response=reponse, body=None)


@pytest.fixture(autouse=True)
def _capacites_propres():
    passerelle.reinitialiser_capacites_outils()
    yield
    passerelle.reinitialiser_capacites_outils()


@pytest.fixture
def client():
    faux = MagicMock()
    faux.chat.completions.create.return_value = _reponse_outils(
        [("modifier_parcelle", '{"parcelle": "serre", "est_pepiniere": false}')]
    )
    with patch("llm.passerelle._client", faux), patch("llm.passerelle.time.sleep"):
        yield faux


@pytest.fixture
def conso_en_base(test_db):
    with patch("llm.passerelle.SessionLocal", lambda: test_db):
        yield test_db


def _appeler(**surcharges):
    parametres = dict(ctx=CTX, outils=OUTILS, prompt_fixe="consignes", message_utilisateur="phrase")
    parametres.update(surcharges)
    return passerelle.appeler_chat_outils(**parametres)


def _charger_config(env: dict):
    """Exécute `app/config.py` dans un module à part (sans toucher à `sys.modules`),
    avec exactement ces variables d'environnement. `None` retire la variable."""
    spec = importlib.util.spec_from_file_location("config_us233", RACINE / "app" / "config.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(os.environ, {k: v for k, v in env.items() if v is not None}), \
         patch("dotenv.load_dotenv"):          # le .env.dev ne doit pas écraser le cas testé
        for cle, valeur in env.items():
            if valeur is None:
                os.environ.pop(cle, None)
        spec.loader.exec_module(module)
    return module


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — un appel avec outils, par la passerelle, et rien d'autre
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1AppelAvecOutils:

    def test_us233_ca1_les_outils_et_le_tool_choice_partent_au_fournisseur(self, client):
        """[CA1] La liste d'outils et `tool_choice` sont transmis tels quels."""
        _appeler(tool_choice="required")
        envoye = client.chat.completions.create.call_args.kwargs
        assert envoye["tools"] == OUTILS
        assert envoye["tool_choice"] == "required"
        assert envoye["model"] == passerelle.modele_pour("agent")

    def test_us233_ca1_tool_choice_est_required_par_defaut(self, client):
        """[CA1] À cet étage le modèle choisit TOUJOURS un outil (architecture §3.3)."""
        _appeler()
        assert client.chat.completions.create.call_args.kwargs["tool_choice"] == "required"

    def test_us233_ca1_rend_le_texte_et_les_appels_d_outils(self, client):
        """[CA1] Le texte ET les appels, arguments décodés."""
        client.chat.completions.create.return_value = _reponse_outils(
            [("modifier_parcelle", '{"parcelle": "serre", "est_pepiniere": false}')],
            contenu="  je m'en occupe ",
        )
        reponse = _appeler()
        assert isinstance(reponse, ReponseOutils)
        assert reponse.ok and reponse.statut == STATUT_OK
        assert reponse.texte == "je m'en occupe"
        assert reponse.appels == (AppelOutil(
            nom="modifier_parcelle",
            arguments={"parcelle": "serre", "est_pepiniere": False},
            arguments_valides=True, id="call_0",
        ),)

    def test_us233_ca1_plusieurs_appels_sont_tous_rendus_dans_l_ordre(self, client):
        client.chat.completions.create.return_value = _reponse_outils(
            [("parcelle_ajouter", '{"nom": "carré"}'), ("modifier_parcelle", '{"parcelle": "carré"}')]
        )
        assert [a.nom for a in _appeler().appels] == ["parcelle_ajouter", "modifier_parcelle"]

    def test_us233_ca1_un_outil_sans_argument_est_valide(self, client):
        """[CA1] `saisir_geste()` n'a pas d'argument : ce n'est pas un appel illisible."""
        client.chat.completions.create.return_value = _reponse_outils([("saisir_geste", "")])
        appel = _appeler().appels[0]
        assert appel.arguments == {} and appel.arguments_valides

    @pytest.mark.parametrize("brut", ["{pas du json", "[1, 2]", '"texte"', 42])
    def test_us233_ca1_un_argument_illisible_est_signale_pas_ignore(self, client, brut):
        """[CA1] Jamais pris pour « aucun argument » : l'appelant doit pouvoir le distinguer."""
        client.chat.completions.create.return_value = _reponse_outils([("modifier_parcelle", brut)])
        appel = _appeler().appels[0]
        assert appel.arguments == {} and not appel.arguments_valides

    def test_us233_ca1_une_reponse_sans_appel_donne_une_liste_vide(self, client):
        client.chat.completions.create.return_value = _reponse_outils([], contenu="bonjour")
        reponse = _appeler()
        assert reponse.appels == () and reponse.texte == "bonjour"

    def test_us233_ca1_le_prompt_garde_la_partie_fixe_en_tete(self, client):
        """[CA1, CA6 d'US-092] Fixe d'abord, variable ensuite, phrase à part."""
        _appeler(prompt_fixe="FIXE|", prompt_variable="VARIABLE", message_utilisateur="phrase")
        messages = client.chat.completions.create.call_args.kwargs["messages"]
        assert messages == [
            {"role": "system", "content": "FIXE|VARIABLE"},
            {"role": "user", "content": "phrase"},
        ]

    def test_us233_ca1_le_niveau_de_raisonnement_suit_la_regle_des_autres_appels(self, client):
        """[CA1, CA3] `reasoning_effort` est envoyé comme pour `appeler_chat`, et
        omis pour qui ne l'accepte pas (famille compound, ou `reasoning=False`)."""
        with patch.object(passerelle, "GROQ_REASONING_EFFORT", "low"):
            _appeler()
            assert client.chat.completions.create.call_args.kwargs["reasoning_effort"] == "low"

            _appeler(reasoning=False)
            assert "reasoning_effort" not in client.chat.completions.create.call_args.kwargs

            with patch.dict(passerelle.GROQ_MODELE_PAR_TYPE, {"agent": "groq/compound-mini"}):
                _appeler()
            assert "reasoning_effort" not in client.chat.completions.create.call_args.kwargs

    def test_us233_ca1_sans_outil_l_appel_est_refuse_avant_le_reseau(self, client):
        with pytest.raises(ValueError):
            _appeler(outils=[])
        client.chat.completions.create.assert_not_called()

    def test_us233_ca1_l_appel_reste_imputable(self, client):
        """[CA1, CA2 d'US-092] Pas de contexte, pas d'appel."""
        with pytest.raises(ContexteAppelManquantError):
            _appeler(ctx=None)
        client.chat.completions.create.assert_not_called()

    def test_us233_ca1_l_audit_reste_vert_pour_le_nouvel_outil_et_la_passerelle(self):
        """[CA1] La passerelle reste le seul point de sortie : ni `llm/passerelle.py`
        ni `tools/evaluer_agent.py` ne sont signalés par l'audit — l'outil de
        mesure passe bien par elle.

        (Le test d'US-092 qui exige un audit totalement vide échoue pour une
        raison ANTÉRIEURE à cette US : `tools/mesurer_modeles_llm.py`.)"""
        fichiers_signales = {f for f, *_ in audit.auditer()}
        assert "tools/evaluer_agent.py" not in fichiers_signales
        assert "llm/passerelle.py" not in fichiers_signales
        assert "tools/evaluer_agent.py" in {
            c.relative_to(RACINE).as_posix() for c in audit._fichiers_a_auditer()
        }, "l'outil de mesure doit être DANS le périmètre de l'audit, sinon il ne prouve rien"


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — le type d'appel « agent » et son modèle propre
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2TypeAgent:

    def test_us233_ca2_le_type_agent_existe(self):
        assert passerelle.TYPE_AGENT == "agent" and "agent" in TYPES_APPEL

    def test_us233_ca2_groq_model_agent_regle_le_modele_de_l_agent(self):
        config = _charger_config({"GROQ_MODEL_AGENT": "modele-agent", "GROQ_MODEL_CLASSIFICATION": "petit"})
        assert config.GROQ_MODELE_PAR_TYPE["agent"] == "modele-agent"

    def test_us233_ca2_il_est_distinct_de_celui_de_la_classification(self):
        """[CA2] Changer l'un ne change pas l'autre."""
        config = _charger_config({"GROQ_MODEL_AGENT": "modele-agent", "GROQ_MODEL_CLASSIFICATION": "petit"})
        assert config.GROQ_MODELE_PAR_TYPE["classification"] == "petit"
        assert config.GROQ_MODELE_PAR_TYPE["agent"] != config.GROQ_MODELE_PAR_TYPE["classification"]

        seul = _charger_config({"GROQ_MODEL_AGENT": None, "GROQ_MODEL_CLASSIFICATION": "petit"})
        assert seul.GROQ_MODELE_PAR_TYPE["agent"] == seul.GROQ_MODEL, \
            "non renseigné, l'agent retombe sur GROQ_MODEL comme les autres types — pas sur la classification"

    def test_us233_ca2_l_appel_utilise_le_modele_de_l_agent(self, client):
        with patch.dict(passerelle.GROQ_MODELE_PAR_TYPE, {"agent": "modele-agent"}):
            reponse = _appeler()
        assert reponse.modele == "modele-agent"
        assert client.chat.completions.create.call_args.kwargs["model"] == "modele-agent"

    def test_us233_ca2_le_reglage_est_documente_dans_env_example(self):
        texte = (RACINE / ".env.example").read_text(encoding="utf-8")
        for variable in ("GROQ_MODEL_AGENT", "AGENT_MODE", "AGENT_MAX_TOURS"):
            assert variable in texte, f"{variable} n'est pas documenté dans .env.example"


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — journal, jetons (dont le cache), repli 429 : comme les autres types
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3MesureEtRepli:

    def test_us233_ca3_les_jetons_dont_le_cache_sont_comptes(self, client):
        client.chat.completions.create.return_value = _reponse_outils(
            [("saisir_geste", "")], tokens_in=1500, tokens_out=40, tokens_cache=1200,
        )
        reponse = _appeler()
        assert (reponse.tokens_in, reponse.tokens_out, reponse.tokens_cache) == (1500, 40, 1200)
        assert reponse.tokens_total == 1540 and reponse.latence_ms >= 0

    def test_us233_ca3_la_consommation_est_imputee_au_type_agent(self, client, conso_en_base):
        client.chat.completions.create.return_value = _reponse_outils(
            [("saisir_geste", "")], tokens_in=1500, tokens_out=40, tokens_cache=1200,
        )
        _appeler()
        ligne = conso_en_base.query(ConsoTokens).filter_by(appel_type="agent").one()
        assert (ligne.potager_id, ligne.tokens_in, ligne.tokens_out, ligne.tokens_cache, ligne.issue) \
            == (3, 1500, 40, 1200, "ok")

    def test_us233_ca3_le_journal_ne_porte_aucun_contenu(self, client, caplog):
        """[CA3, CA13 d'US-092] Métadonnées seulement : ni la phrase, ni le prompt."""
        caplog.set_level(logging.INFO, logger="potager")
        _appeler(prompt_fixe="CONSIGNE-SECRETE", message_utilisateur="PHRASE-DU-JARDINIER")
        journal = caplog.text
        assert "agent" in journal and "cache=" in journal
        assert "PHRASE-DU-JARDINIER" not in journal and "CONSIGNE-SECRETE" not in journal

    def test_us233_ca3_un_429_est_rejoue_une_fois_puis_converti(self, client, conso_en_base):
        """[CA3] Même politique que les autres types : une nouvelle tentative, puis
        le mode dégradé — et l'échec est compté."""
        client.chat.completions.create.side_effect = _erreur_429()
        with pytest.raises(QuotaLLMDepasseError):
            _appeler()
        assert client.chat.completions.create.call_count == 2
        assert conso_en_base.query(ConsoTokens).filter_by(appel_type="agent", issue="quota").count() == 1

    def test_us233_ca3_un_429_suivi_d_un_succes_aboutit(self, client):
        client.chat.completions.create.side_effect = [_erreur_429(), _reponse_outils([("saisir_geste", "")])]
        assert _appeler().appels[0].nom == "saisir_geste"

    def test_us233_ca3_une_panne_fournisseur_est_une_indisponibilite(self, client):
        erreur = groq.InternalServerError("upstream", response=httpx.Response(
            503, request=httpx.Request("POST", URL)), body=None)
        client.chat.completions.create.side_effect = erreur
        with pytest.raises(FournisseurLLMIndisponibleError):
            _appeler()

    def test_us233_ca3_un_autre_400_n_est_pas_avale(self, client):
        """[CA3] Seuls les deux 400 propres aux outils sont des statuts ; un modèle
        inconnu reste une erreur du fournisseur, qui suit le repli ordinaire."""
        client.chat.completions.create.side_effect = _erreur_400("The model `x` does not exist")
        with pytest.raises(FournisseurLLMIndisponibleError):
            _appeler()

    def test_us233_ca3_les_jetons_alimentent_l_accumulateur_de_cascade(self, client):
        jeton = passerelle.demarrer_mesure_cascade()
        _appeler()
        assert passerelle.cumul_mesure_cascade(jeton) == 1540


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — un modèle sans outils : détecté au premier appel, mémorisé, sans exception
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4ModeleSansOutils:

    @pytest.mark.parametrize("message", [
        "tool calling is not supported with this model",
        "This model does not support function calling",
        "Tools are unsupported for model x",
    ])
    def test_us233_ca4_detecte_au_premier_appel_sans_exception(self, client, message):
        client.chat.completions.create.side_effect = _erreur_400(message)
        reponse = _appeler()
        assert reponse.statut == STATUT_SANS_OUTILS and not reponse.ok
        assert reponse.appels == () and reponse.texte == ""

    def test_us233_ca4_le_detail_peut_etre_sous_la_cle_error(self, client):
        """Le SDK range parfois le détail sous `error`."""
        client.chat.completions.create.side_effect = _erreur_400(
            "tool calling is not supported", imbrique=True)
        assert _appeler().statut == STATUT_SANS_OUTILS

    def test_us233_ca4_le_resultat_est_memorise(self, client):
        """[CA4] Le second appel ne coûte plus un aller-retour."""
        client.chat.completions.create.side_effect = _erreur_400("tool calling is not supported")
        _appeler()
        seconde = _appeler()
        assert seconde.statut == STATUT_SANS_OUTILS
        assert client.chat.completions.create.call_count == 1

    def test_us233_ca4_la_memoire_est_par_modele(self, client):
        client.chat.completions.create.side_effect = [
            _erreur_400("tool calling is not supported"),
            _reponse_outils([("saisir_geste", "")]),
        ]
        with patch.dict(passerelle.GROQ_MODELE_PAR_TYPE, {"agent": "sans-outils"}):
            assert _appeler().statut == STATUT_SANS_OUTILS
        with patch.dict(passerelle.GROQ_MODELE_PAR_TYPE, {"agent": "avec-outils"}):
            assert _appeler().ok

    def test_us233_ca4_un_client_propre_a_un_potager_a_sa_propre_memoire(self, client):
        """[CA4] BYOK : la clé d'un potager n'hérite pas du refus de la plateforme."""
        client.chat.completions.create.side_effect = _erreur_400("tool calling is not supported")
        _appeler()
        byok = MagicMock()
        byok.chat.completions.create.return_value = _reponse_outils([("saisir_geste", "")])
        with patch("llm.passerelle._resoudre_client", return_value=byok):
            assert _appeler().ok
        byok.chat.completions.create.assert_called_once()

    def test_us233_ca4_la_memoire_peut_etre_oubliee(self, client):
        client.chat.completions.create.side_effect = [
            _erreur_400("tool calling is not supported"),
            _reponse_outils([("saisir_geste", "")]),
        ]
        _appeler()
        passerelle.reinitialiser_capacites_outils()
        assert _appeler().ok

    def test_us233_ca4_l_echec_est_journalise_et_compte(self, client, conso_en_base):
        client.chat.completions.create.side_effect = _erreur_400("tool calling is not supported")
        _appeler()
        ligne = conso_en_base.query(ConsoTokens).filter_by(appel_type="agent").one()
        assert ligne.issue == "erreur" and ligne.tokens_in == 0

    def test_us233_ca4_un_appel_malforme_est_un_statut_pas_une_panne(self, client):
        """[CA4] `tool_use_failed` : le modèle gère les outils mais a mal formé son appel."""
        client.chat.completions.create.side_effect = _erreur_400(
            "Failed to call a function", code="tool_use_failed")
        assert _appeler().statut == STATUT_APPEL_INVALIDE

    def test_inc018_la_generation_rejetee_est_journalisee_tronquee(self, client, caplog):
        """[INC-018] Le 400 `tool_use_failed` porte `failed_generation` : sans elle, un schéma
        trop strict ne se distingue pas d'un modèle qui comprend mal. Le statut ne change pas."""
        erreur = _erreur_400("Failed to call a function", code="tool_use_failed")
        erreur.body["failed_generation"] = '<function=parcelle_ajouter>{"superficie": null}' + "x" * 2000
        client.chat.completions.create.side_effect = erreur
        caplog.set_level(logging.WARNING, logger="potager")
        assert _appeler().statut == STATUT_APPEL_INVALIDE
        journal = [r for r in caplog.records
                   if r.levelno == logging.WARNING and "appel d'outil rejeté" in r.getMessage()]
        assert len(journal) == 1
        message = journal[0].getMessage()
        assert '<function=parcelle_ajouter>{"superficie": null}' in message
        assert len(message) < 900  # tronquée

    def test_inc018_generation_rejetee_imbriquee_ou_absente(self, client, caplog):
        caplog.set_level(logging.WARNING, logger="potager")
        erreur = _erreur_400("Failed to call a function", code="tool_use_failed", imbrique=True)
        erreur.body["error"]["failed_generation"] = "appel rejeté"
        client.chat.completions.create.side_effect = erreur
        assert _appeler().statut == STATUT_APPEL_INVALIDE
        assert "appel rejeté" in caplog.text

        caplog.clear()
        client.chat.completions.create.side_effect = _erreur_400(
            "Failed to call a function", code="tool_use_failed")
        assert _appeler().statut == STATUT_APPEL_INVALIDE
        assert "(absente)" in caplog.text

    def test_us233_ca4_un_appel_malforme_n_est_pas_memorise(self, client):
        """Un échec de génération n'est pas une incapacité : on réessaie au prochain appel."""
        client.chat.completions.create.side_effect = [
            _erreur_400("Failed to call a function", code="tool_use_failed"),
            _reponse_outils([("saisir_geste", "")]),
        ]
        assert _appeler().statut == STATUT_APPEL_INVALIDE
        assert _appeler().ok


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — AGENT_MODE et AGENT_MAX_TOURS
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5Configuration:

    def test_us233_ca5_valeurs_par_defaut(self):
        config = _charger_config({"AGENT_MODE": None, "AGENT_MAX_TOURS": None})
        # [US-257] La boucle conversationnelle : 6 tours (architecture §12.4).
        assert config.AGENT_MODE == "off" and config.AGENT_MAX_TOURS == 6

    @pytest.mark.parametrize("brut,attendu", [
        ("off", "off"), ("ombre", "ombre"), ("actif", "actif"),
        ("OMBRE", "ombre"), ("  actif ", "actif"),
    ])
    def test_us233_ca5_les_trois_modes(self, brut, attendu):
        assert _charger_config({"AGENT_MODE": brut}).AGENT_MODE == attendu

    @pytest.mark.parametrize("brut", ["", "oui", "true", "actifs", "1"])
    def test_us233_ca5_un_mode_inconnu_retombe_sur_off(self, brut):
        """Une faute de frappe ne doit jamais activer l'agent."""
        assert _charger_config({"AGENT_MODE": brut}).AGENT_MODE == "off"

    @pytest.mark.parametrize("brut,attendu", [("5", 5), ("1", 1), ("0", 6), ("-2", 6), ("abc", 6), ("", 6)])
    def test_us233_ca5_agent_max_tours(self, brut, attendu):
        assert _charger_config({"AGENT_MAX_TOURS": brut}).AGENT_MAX_TOURS == attendu

    def test_us233_ca5_sans_effet_tant_qu_aucun_agent_ne_les_lit(self):
        """[CA5] Aucun module applicatif ne lisait ces réglages en US-233.

        [US-235] L'agent est branché : un SEUL lecteur, l'interpréteur de
        commandes, qui choisit entre l'ancien repli et l'agent. Un second lecteur
        ferait deux endroits où le mode se décide.
        """
        lecteurs = []
        for dossier in ("app", "llm", "utils"):
            for chemin in (RACINE / dossier).rglob("*.py"):
                if chemin.name == "config.py":
                    continue
                if "AGENT_MODE" in chemin.read_text(encoding="utf-8-sig"):
                    lecteurs.append(chemin.relative_to(RACINE).as_posix())
        assert lecteurs == ["app/services/interpreteur_commandes.py"]


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — l'échantillon et le catalogue provisoire
# ═════════════════════════════════════════════════════════════════════════════
class TestCA6Echantillon:

    def test_us233_ca6_au_moins_trente_phrases(self):
        assert len(ev.charger_echantillon()) >= 30

    def test_us233_ca6_les_phrases_us172_sont_bien_dans_le_corpus_us172(self):
        """[CA6] « Du corpus US-172 » se vérifie : chaque ligne marquée `us172` en vient."""
        import csv
        with ev.CORPUS_US172.open(encoding="utf-8", newline="") as f:
            corpus = {ligne["phrase"].strip() for ligne in csv.DictReader(f)}
        reprises = [p for p in ev.charger_echantillon() if p.source == "us172"]
        assert len(reprises) >= 15
        assert [p.texte for p in reprises if p.texte not in corpus] == []

    def test_us233_ca6_l_enrichissement_est_la(self):
        """[CA6] Négations, paires déclaration / question, demandes ambiguës."""
        par_categorie = {}
        for p in ev.charger_echantillon():
            par_categorie.setdefault(p.categorie, []).append(p)
        assert len(par_categorie["negation"]) >= 6
        assert len(par_categorie["ambigu"]) >= 4
        paires = par_categorie["declaration_question"]
        # [US-257] Une question et une précision se disent en texte.
        assert {"modifier_parcelle", ev.PSEUDO_TEXTE} <= {o for p in paires for o in p.outils_attendus}
        assert all(p.outils_attendus == (ev.PSEUDO_TEXTE,) for p in par_categorie["ambigu"])

    def test_us233_ca6_le_catalogue_mesure_est_le_catalogue_livre(self):
        """[INC-018] La mesure ne garde pas sa copie : ce qu'elle note est ce qui est livré."""
        assert ev.NOMS_OUTILS == tuple(o["function"]["name"] for o in catalogue_outils.schemas())
        assert "modifier_parcelle" in ev.NOMS_OUTILS
        assert set(ev.OUTILS_TERMINAUX) <= set(ev.NOMS_OUTILS)

    def test_us233_ca6_est_pepiniere_est_un_booleen_dans_le_schema(self):
        """[CA6] C'est le typage qui doit porter la négation, sans règle."""
        outil = next(o for o in catalogue_outils.schemas() if o["function"]["name"] == "modifier_parcelle")
        assert outil["function"]["parameters"]["properties"]["est_pepiniere"]["type"] == ["boolean", "null"]

    def test_us233_ca6_chaque_attendu_existe_dans_le_catalogue(self):
        """Un attendu qui désigne un outil absent ou un paramètre inconnu rendrait
        la mesure fausse sans que rien ne le signale."""
        schemas = {o["function"]["name"]: o["function"]["parameters"]["properties"]
                   for o in catalogue_outils.schemas()}
        for p in ev.charger_echantillon():
            for outil in (n for attendu in p.outils_attendus for n in attendu.split("+")):
                assert outil in schemas or outil == ev.PSEUDO_TEXTE, f"{p.texte!r} attend l'outil inconnu {outil!r}"
            if p.parametres:
                inconnus = set(p.parametres) - set(schemas[p.outils_attendus[0]])
                assert not inconnus, f"{p.texte!r} attend des paramètres inconnus : {inconnus}"

    def test_us233_ca6_les_valeurs_attendues_respectent_les_listes_fermees(self):
        schemas = {o["function"]["name"]: o["function"]["parameters"]["properties"]
                   for o in catalogue_outils.schemas()}
        for p in ev.charger_echantillon():
            for cle, valeur in p.parametres.items():
                enum = schemas[p.outils_attendus[0]][cle].get("enum")
                if enum:
                    assert valeur in enum, f"{p.texte!r} : {cle}={valeur!r} hors de {enum}"

    def test_us233_ca6_le_prompt_ne_liste_pas_de_tournures(self):
        """Architecture §8 : le catalogue porte le sens, pas une liste de formulations."""
        # [INC-018] Le prompt LIVRÉ (12 consignes depuis la révision du 23/10/2026) : le plafond
        # porte sur les consignes, pas sur les lignes, et sur les exemples cités entre guillemets
        # — le catalogue porte le sens, aucune liste de formulations ne s'y ajoute.
        import re
        assert ev.PROMPT_FIXE is interpreteur_agent.PROMPT_FIXE
        assert len(re.findall(r"^\d+\. ", ev.PROMPT_FIXE, flags=re.M)) <= 12   # [US-257] toujours douze
        assert len(re.findall(r"«[^»]*»", ev.PROMPT_FIXE)) <= 3
        assert "n'est plus" not in ev.PROMPT_FIXE
        assert "Serre extérieure" not in ev.PROMPT_FIXE

    def test_us233_ca6_la_partie_variable_vient_apres_la_fixe_et_nomme_les_parcelles(self):
        variable = ev.prompt_variable()
        assert "Serre extérieure" in variable and "Date du jour" in variable
        assert "Serre extérieure" not in ev.PROMPT_FIXE


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — la notation et le rapport par catégorie
# ═════════════════════════════════════════════════════════════════════════════
def _phrase(texte="p", categorie="commande", outils=("modifier_parcelle",), parametres=None):
    return ev.Phrase(texte, categorie, tuple(outils), parametres or {}, "nouveau")


def _appel(nom, **arguments):
    return AppelOutil(nom=nom, arguments=arguments)


class TestCA7Notation:

    def test_us233_ca7_bon_outil_bons_parametres(self):
        phrase = _phrase(parametres={"parcelle": "serre extérieure", "est_pepiniere": False})
        notes = ev.noter(phrase, (_appel("modifier_parcelle", parcelle="Serre Extérieure", est_pepiniere=False),), STATUT_OK)
        assert notes.outil_ok and notes.parametres_ok and notes.reussite and not notes.champs_en_trop

    def test_us233_ca7_un_booleen_inverse_est_faux(self):
        """Le cas de départ : `true` au lieu de `false` ne se rattrape pas."""
        phrase = _phrase(parametres={"parcelle": "serre", "est_pepiniere": False})
        notes = ev.noter(phrase, (_appel("modifier_parcelle", parcelle="serre", est_pepiniere=True),), STATUT_OK)
        assert notes.outil_ok and notes.parametres_ok is False and not notes.reussite

    def test_us233_ca7_un_booleen_n_est_pas_un_nombre(self):
        phrase = _phrase(parametres={"nb_rangs": 1})
        assert ev.noter(phrase, (_appel("modifier_parcelle", nb_rangs=True),), STATUT_OK).parametres_ok is False

    def test_us233_ca7_un_nombre_se_compare_a_la_valeur(self):
        phrase = _phrase(parametres={"longueur_m": 12})
        assert ev.noter(phrase, (_appel("modifier_parcelle", longueur_m=12.0),), STATUT_OK).parametres_ok
        assert not ev.noter(phrase, (_appel("modifier_parcelle", longueur_m=21),), STATUT_OK).parametres_ok

    def test_us233_ca7_un_nom_de_parcelle_se_rattache_par_inclusion(self):
        """« serre » pour « Serre extérieure » : le rattachement est l'affaire du validateur."""
        phrase = _phrase(parametres={"parcelle": "serre"})
        assert ev.noter(phrase, (_appel("modifier_parcelle", parcelle="Serre extérieure"),), STATUT_OK).parametres_ok
        assert not ev.noter(phrase, (_appel("modifier_parcelle", parcelle="Planche Nord"),), STATUT_OK).parametres_ok

    def test_us233_ca7_un_nouveau_nom_se_compare_a_egalite(self):
        phrase = _phrase(outils=("parcelle_renommer",), parametres={"nouveau_nom": "planche des courges"})
        assert ev.noter(phrase, (_appel("parcelle_renommer", nouveau_nom="Planche des Courges"),), STATUT_OK).parametres_ok
        assert not ev.noter(phrase, (_appel("parcelle_renommer", nouveau_nom="courges"),), STATUT_OK).parametres_ok

    def test_us233_ca7_un_champ_ajoute_sans_etre_evoque_est_releve(self):
        """Le risque de la règle 9 du validateur : `type_pepiniere` ajouté de lui-même."""
        phrase = _phrase(categorie="ancrage_champ", parametres={"parcelle": "serre", "est_pepiniere": True})
        notes = ev.noter(phrase, (_appel("modifier_parcelle", parcelle="serre", est_pepiniere=True,
                                         type_pepiniere="chaude"),), STATUT_OK)
        assert notes.parametres_ok and notes.champs_en_trop == ("type_pepiniere",)
        assert not notes.reussite

    def test_us233_ca7_un_champ_vide_n_est_pas_un_champ_ajoute(self):
        phrase = _phrase(parametres={"parcelle": "serre"})
        notes = ev.noter(phrase, (_appel("modifier_parcelle", parcelle="serre", actif=None, exposition=""),), STATUT_OK)
        assert notes.champs_en_trop == ()

    def test_us233_ca7_le_mauvais_outil(self):
        notes = ev.noter(_phrase(), (_appel("poser_question", nature="DATA"),), STATUT_OK)
        assert not notes.outil_ok and not notes.reussite

    def test_us233_ca7_plusieurs_outils_acceptables(self):
        phrase = _phrase(outils=("poser_question", "saisir_geste"))
        assert ev.noter(phrase, (_appel("saisir_geste"),), STATUT_OK).outil_ok

    def test_us233_ca7_un_appel_destructeur_errone_est_releve_meme_en_second(self):
        """Le couperet : supprimer ce qu'on n'a pas demandé de supprimer."""
        notes = ev.noter(_phrase(), (_appel("modifier_parcelle"), _appel("supprimer_parcelle", parcelle="x")), STATUT_OK)
        assert notes.destructif_errone and notes.appels_multiples

    def test_us233_ca7_supprimer_quand_c_est_demande_n_est_pas_une_erreur(self):
        phrase = _phrase(outils=("supprimer_parcelle",), parametres={"parcelle": "planche sud"})
        notes = ev.noter(phrase, (_appel("supprimer_parcelle", parcelle="Planche Sud"),), STATUT_OK)
        assert not notes.destructif_errone and notes.reussite

    @pytest.mark.parametrize("statut", [STATUT_SANS_OUTILS, STATUT_APPEL_INVALIDE, "indisponible"])
    def test_us233_ca7_un_echec_technique_est_compte(self, statut):
        assert ev.noter(_phrase(), (), statut).echec_technique

    def test_us233_ca7_une_reponse_sans_appel_est_un_echec(self):
        assert ev.noter(_phrase(), (), STATUT_OK).echec_technique

    def test_us233_ca7_un_argument_illisible_est_un_echec(self):
        illisible = AppelOutil(nom="modifier_parcelle", arguments={}, arguments_valides=False)
        assert ev.noter(_phrase(), (illisible,), STATUT_OK).echec_technique

    def test_us233_ca7_lire_les_parametres_attendus(self):
        assert ev.lire_parametres("a=Serre|b=true|c=12|d=1.5|e=false") == {
            "a": "Serre", "b": True, "c": 12, "d": 1.5, "e": False}
        assert ev.lire_parametres("") == {}

    def test_us233_ca7_percentiles(self):
        assert ev.percentile([], 0.95) == 0.0
        assert ev.percentile(list(range(1, 101)), 0.95) == 95
        assert ev.percentile([40, 10, 30, 20], 0.5) == 20


def _resultats_de_demonstration() -> list:
    """Quatre phrases jouées par un faux modèle — dont celle du scénario Gherkin."""
    echantillon = [
        _phrase("Ma serre extérieure n'est plus une pépinière", "negation",
                parametres={"parcelle": "serre extérieure", "est_pepiniere": False}),
        _phrase("la planche nord a 5 rangs", "declaration_question", parametres={"parcelle": "planche nord", "nb_rangs": 5}),
        _phrase("combien de rangs a la planche nord ?", "declaration_question", ("poser_question",), {"nature": "DATA"}),
        _phrase("modifie ma serre", "ambigu", ("demander_precision",)),
    ]
    reponses = {
        "Ma serre extérieure n'est plus une pépinière": ReponseOutils(
            texte="", modele="m", appel_type="agent", tokens_in=1500, tokens_out=30, tokens_cache=1200,
            latence_ms=400, appels=(_appel("modifier_parcelle", parcelle="Serre extérieure", est_pepiniere=False),)),
        "la planche nord a 5 rangs": ReponseOutils(
            texte="", modele="m", appel_type="agent", tokens_in=1500, tokens_out=30, tokens_cache=1200,
            latence_ms=600, appels=(_appel("modifier_parcelle", parcelle="Planche Nord", nb_rangs=5),)),
        "combien de rangs a la planche nord ?": ReponseOutils(
            texte="", modele="m", appel_type="agent", tokens_in=1500, tokens_out=20, tokens_cache=0,
            latence_ms=500, appels=(_appel("modifier_parcelle", parcelle="Planche Nord"),)),   # ❌ confond avec une commande
        "modifie ma serre": ReponseOutils(
            texte="", modele="m", appel_type="agent", tokens_in=1500, tokens_out=25, tokens_cache=1200,
            latence_ms=700, appels=(_appel("demander_precision", question="Que veux-tu modifier ?"),)),
    }
    return ev.evaluer_modele("m", echantillon, lambda texte: reponses[texte], pause_s=0)


class TestCA7Rapport:

    def test_us233_ca7_agregats_par_categorie(self):
        agregats = ev.agreger(_resultats_de_demonstration())
        assert agregats["negation"].taux_reussite == 100
        assert agregats["declaration_question"].taux_reussite == 50     # la question prise pour une commande
        assert agregats["ambigu"].taux_outil == 100
        assert agregats["TOTAL"].n == 4

    def test_us233_ca7_latences_et_jetons(self):
        total = ev.agreger(_resultats_de_demonstration())["TOTAL"]
        assert (total.p50, total.p95) == (550, 700)
        assert total.jetons_par_phrase == (1500, 26.25)
        assert total.part_cache == pytest.approx(100 * 3600 / 6000)

    def test_us233_ca7_le_rapport_donne_les_chiffres_demandes(self):
        """[CA7] Par catégorie : bon outil, bons paramètres, précision demandée ;
        puis latence p50 / p95, jetons et part en cache."""
        agregats = ev.agreger(_resultats_de_demonstration())
        rapport = ev.rediger_rapport({"m": (agregats, ev.evaluer_criteres(agregats), _resultats_de_demonstration())})
        for attendu in ("Négations et retraits", "Paires déclaration / question", "Demandes ambiguës",
                        "Bon outil", "Bons paramètres", "p50", "p95", "Part servie par le cache",
                        "Jetons d'entrée / phrase"):
            assert attendu in rapport, f"le rapport ne contient pas « {attendu} »"
        assert "550 ms" in rapport and "700 ms" in rapport

    def test_us233_gherkin_le_rapport_indique_l_outil_et_la_valeur_de_la_phrase_de_reference(self):
        """[Gherkin] « Ma serre extérieure n'est plus une pépinière » → modifier_parcelle,
        est_pepiniere à false ; latence p95 et jetons ; un go ou un no-go."""
        resultats = _resultats_de_demonstration()
        agregats = ev.agreger(resultats)
        rapport = ev.rediger_rapport({"m": (agregats, ev.evaluer_criteres(agregats), resultats)})
        ligne = next(l for l in rapport.splitlines() if "Ma serre extérieure n'est plus une pépinière" in l)
        assert "modifier_parcelle" in ligne and '"est_pepiniere": false' in ligne and "✅" in ligne
        assert "p95" in rapport and "1500" in rapport
        assert "GO" in rapport

    def test_us233_ca7_les_cellules_du_tableau_restent_sur_une_ligne(self):
        resultats = _resultats_de_demonstration()
        resultats[0].phrase = _phrase("deux\nlignes", "negation")
        agregats = ev.agreger(resultats)
        rapport = ev.rediger_rapport({"m": (agregats, ev.evaluer_criteres(agregats), resultats)})
        assert "deux\nlignes" not in rapport


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — le go / no-go
# ═════════════════════════════════════════════════════════════════════════════
def _agregats_parfaits() -> dict:
    """Un modèle sans faute, rapide : tout est vert."""
    echantillon = ev.charger_echantillon()
    reponses = {}
    for p in echantillon:
        nom = p.outils_attendus[0]
        arguments = dict(p.parametres)
        if nom == "poser_question" and "nature" not in arguments:
            arguments["nature"] = "DATA"
        reponses[p.texte] = ReponseOutils(
            texte="", modele="m", appel_type="agent", tokens_in=1500, tokens_out=30,
            latence_ms=300, appels=(AppelOutil(nom=nom, arguments=arguments),))
    return ev.agreger(ev.evaluer_modele("m", echantillon, lambda t: reponses[t], pause_s=0))


class TestCA8GoNoGo:

    def test_us233_ca8_un_modele_parfait_est_go(self):
        criteres = ev.evaluer_criteres(_agregats_parfaits())
        assert [c.code for c in criteres if not c.ok] == []
        assert ev.verdict(criteres) == "GO"

    def test_us233_ca8_un_critere_critique_en_echec_fait_un_no_go(self):
        agregats = _agregats_parfaits()
        agregats["TOTAL"].latences = [9000] * 10
        criteres = ev.evaluer_criteres(agregats)
        assert next(c for c in criteres if c.code == "C7").ok is False
        assert ev.verdict(criteres) == "NO-GO"

    def test_us233_ca8_un_appel_destructeur_errone_fait_toujours_un_no_go(self):
        agregats = _agregats_parfaits()
        agregats["TOTAL"].destructifs_errones = 1
        assert ev.verdict(ev.evaluer_criteres(agregats)) == "NO-GO"

    def test_us233_ca8_un_critere_non_critique_en_echec_donne_des_reserves(self):
        agregats = _agregats_parfaits()
        agregats["ambigu"].reussites = 0
        criteres = ev.evaluer_criteres(agregats)
        assert next(c for c in criteres if c.code == "C8").ok is False
        assert ev.verdict(criteres) == "GO avec réserves"

    def test_us233_ca8_les_seuils_sont_ceux_qui_ont_ete_fixes_avant_la_mesure(self):
        """Les seuils ne bougent pas pour faire passer un modèle : ce test les fige."""
        attendus = {c.code: (c.attendu, c.critique) for c in ev.evaluer_criteres(_agregats_parfaits())}
        # [INC-018] C11 à C13 s'ajoutent (critères de sortie de l'étape 0) ; C1 à C10 ne bougent pas.
        assert attendus.pop("C11") == ("0", True) and attendus.pop("C12") == ("0", True)
        assert attendus.pop("C13") == ("≤ 5 %", False)
        assert attendus == {
            "C1": ("≥ 90 %", True), "C2": ("≥ 90 %", True), "C3": ("≥ 85 %", True),
            "C4": ("≥ 90 %", True), "C5": ("0", True), "C6": ("≤ 5 %", True),
            "C7": ("≤ 4 000 ms", True), "C8": ("≥ 75 %", False), "C9": ("≤ 10 %", False),
            "C10": ("≥ 85 %", False),
        }

    def test_us233_ca8_le_modele_retenu_est_le_plus_juste_puis_le_plus_rapide(self):
        bon = _agregats_parfaits()
        lent = _agregats_parfaits()
        lent["TOTAL"].latences = [3500] * 10                      # encore GO, mais plus lent
        mauvais = _agregats_parfaits()
        mauvais["TOTAL"].destructifs_errones = 1                  # NO-GO
        evaluations = {
            "lent": (lent, ev.evaluer_criteres(lent)),
            "mauvais": (mauvais, ev.evaluer_criteres(mauvais)),
            "bon": (bon, ev.evaluer_criteres(bon)),
        }
        assert ev.modele_retenu(evaluations) == "bon"

    def test_us233_ca8_aucun_modele_retenu_si_tous_sont_no_go(self):
        mauvais = _agregats_parfaits()
        mauvais["TOTAL"].destructifs_errones = 2
        assert ev.modele_retenu({"m": (mauvais, ev.evaluer_criteres(mauvais))}) is None

    def test_us233_ca8_le_rapport_conclut_par_un_go_ou_un_no_go_et_nomme_le_modele(self):
        resultats = _resultats_de_demonstration()
        agregats = ev.agreger(resultats)
        rapport = ev.rediger_rapport({"m": (agregats, ev.evaluer_criteres(agregats), resultats)})
        assert "## Verdict calculé" in rapport
        assert "Modèle retenu" in rapport and ("NO-GO" in rapport or "GO" in rapport)

    def test_us233_ca8_le_rapport_livre_existe_et_conclut(self):
        """[CA8] Le rapport est versé dans `docs/EPIC - AGENT INTERPRETEUR/`, avec le
        verdict calculé ET la lecture argumentée de l'analyste."""
        assert ev.RAPPORT.parent.name == "EPIC - AGENT INTERPRETEUR"
        assert ev.RAPPORT.exists(), "lancer `python tools/evaluer_agent.py` puis commenter le rapport"
        texte = ev.RAPPORT.read_text(encoding="utf-8")
        assert "## Verdict calculé" in texte
        assert "## Lecture et décision" in texte
        assert "p95" in texte and "Part servie par le cache" in texte


# ═════════════════════════════════════════════════════════════════════════════
# L'exécution de la mesure : quota, panne, plan à blanc
# ═════════════════════════════════════════════════════════════════════════════
class TestExecutionDeLaMesure:

    def test_us233_mesure_un_429_est_attendu_puis_rejoue_et_compte(self):
        attentes = []
        essais = iter([QuotaLLMDepasseError("429"), QuotaLLMDepasseError("429"),
                       ReponseOutils(texte="", modele="m", appel_type="agent", latence_ms=300,
                                     appels=(_appel("saisir_geste"),))])

        def appeler(_):
            suite = next(essais)
            if isinstance(suite, Exception):
                raise suite
            return suite

        resultat = ev.executer_phrase(_phrase(outils=("saisir_geste",)), appeler, dormir=attentes.append)
        assert resultat.quotas_429 == 2 and resultat.notes.reussite
        assert attentes == [20.0, 40.0], "l'attente s'allonge à chaque 429"

    def test_us233_mesure_un_quota_qui_ne_cede_pas_est_un_echec_technique(self):
        def appeler(_):
            raise QuotaLLMDepasseError("429")
        resultat = ev.executer_phrase(_phrase(), appeler, tentatives=2, dormir=lambda s: None)
        assert resultat.statut == "indisponible" and resultat.notes.echec_technique
        assert resultat.quotas_429 == 2

    def test_us233_mesure_une_panne_n_interrompt_pas_la_mesure(self):
        def appeler(_):
            raise FournisseurLLMIndisponibleError("panne")
        resultats = ev.evaluer_modele("m", [_phrase("a"), _phrase("b")], appeler, pause_s=0)
        assert [r.statut for r in resultats] == ["indisponible", "indisponible"]

    def test_us233_mesure_un_modele_sans_outils_est_note_pas_leve(self):
        reponse = ReponseOutils(texte="", modele="m", appel_type="agent", statut=STATUT_SANS_OUTILS)
        resultat = ev.executer_phrase(_phrase(), lambda _: reponse)
        assert resultat.statut == STATUT_SANS_OUTILS and resultat.notes.echec_technique

    def test_us233_mesure_le_plan_a_blanc_n_appelle_aucun_modele(self, capsys):
        with patch.object(passerelle, "appeler_chat_outils") as appel:
            assert ev.main(["--dry-run"]) == 0
        appel.assert_not_called()
        sortie = capsys.readouterr().out
        assert "Plan de la mesure" in sortie and "modifier_parcelle" in sortie

    def test_us233_mesure_sans_raisonnement_ne_vise_que_les_modeles_nommes(self):
        """Un modèle qui refuse `reasoning_effort` ferait mesurer un paramètre, pas le modèle."""
        reponse = ReponseOutils(texte="", modele="m", appel_type="agent",
                                appels=(_appel("saisir_geste"),))
        avant = dict(passerelle.GROQ_MODELE_PAR_TYPE)
        try:
            with patch.object(passerelle, "appeler_chat_outils", return_value=reponse) as appel:
                ev.main(["--modeles", "avec,sans", "--sans-raisonnement", "sans",
                         "--limite", "1", "--pause", "0", "--sans-rapport"])
        finally:
            passerelle.GROQ_MODELE_PAR_TYPE.clear()
            passerelle.GROQ_MODELE_PAR_TYPE.update(avant)
        assert [c.kwargs["reasoning"] for c in appel.call_args_list] == [True, False]

    def test_us233_mesure_l_outil_passe_par_la_passerelle_avec_le_catalogue(self):
        reponse = ReponseOutils(texte="", modele="m", appel_type="agent",
                                appels=(_appel("saisir_geste"),))
        with patch.object(passerelle, "appeler_chat_outils", return_value=reponse) as appel:
            ev.appeler_agent(CTX, "récolté 2 kg")
        envoye = appel.call_args.kwargs
        # [US-276] La mesure projette le catalogue comme le bot.
        assert envoye["outils"] == catalogue_outils.schemas(catalogue_outils.PROJECTION_SANS_DESTRUCTION)
        assert envoye["message_utilisateur"] == "récolté 2 kg"
        assert envoye["prompt_fixe"] == ev.PROMPT_FIXE and "Parcelles du potager" in envoye["prompt_variable"]


# ═════════════════════════════════════════════════════════════════════════════
# INC-018 — la mesure du prompt livré : séquences, appels rejetés, précisions inutiles
# ═════════════════════════════════════════════════════════════════════════════
class TestMesureINC018:

    def test_inc018_une_sequence_attendue_exige_chaque_outil(self):
        phrase = _phrase(outils=("creer_parcelle+modifier_parcelle",), categorie="deux_actions")
        deux = (_appel("creer_parcelle"), _appel("modifier_parcelle", parcelle="x"))
        assert ev.noter(phrase, deux, "ok").reussite
        assert not ev.noter(phrase, (_appel("creer_parcelle"),), "ok").outil_ok
        assert not ev.noter(phrase, (_appel("creer_parcelle"), _appel("creer_parcelle")), "ok").outil_ok

    def test_inc018_plusieurs_appels_attendus_ne_sont_pas_un_defaut(self):
        phrase = _phrase(outils=("modifier_parcelle+modifier_parcelle",))
        notes = ev.noter(phrase, (_appel("modifier_parcelle"), _appel("modifier_parcelle")), "ok")
        assert notes.appels_multiples is False and notes.reussite

    def test_inc018_un_appel_rejete_par_le_serveur_est_compte(self):
        notes = ev.noter(_phrase(), (), passerelle.STATUT_APPEL_INVALIDE)
        assert notes.appel_invalide and notes.echec_technique and not notes.reussite

    def test_inc018_une_precision_demandee_pour_rien_est_comptee(self):
        creation = _phrase(outils=("creer_parcelle",), parametres={})
        assert ev.noter(creation, (_appel("demander_precision", question="?"),), "ok").precision_inutile
        ambigu = _phrase(outils=("demander_precision",), categorie="ambigu")
        assert not ev.noter(ambigu, (_appel("demander_precision", question="?"),), "ok").precision_inutile

    def test_inc018_un_champ_deduit_du_nom_est_un_champ_invente(self):
        """« crée la planche Est » : l'exposition ne se déduit pas du nom."""
        phrase = _phrase(outils=("creer_parcelle",), parametres={"nom": "planche est"})
        appel = AppelOutil("creer_parcelle", {"nom": "Planche Est", "exposition": "Est", "superficie_m2": None})
        notes = ev.noter(phrase, (appel,), "ok")
        assert notes.champs_en_trop == ("exposition",) and not notes.reussite

    def test_inc018_les_criteres_de_sortie_sont_critiques(self):
        agregats = _agregats_parfaits()
        agregats["creation"] = ev.Agregat(n=3, reussites=3)
        assert next(c for c in ev.evaluer_criteres(agregats) if c.code == "C11").ok
        agregats["creation"].appels_invalides = 1
        criteres = ev.evaluer_criteres(agregats)
        assert next(c for c in criteres if c.code == "C11").ok is False
        assert ev.verdict(criteres) == "NO-GO"
        agregats["creation"].appels_invalides = 0
        agregats["TOTAL"].champs_en_trop = 1
        assert ev.verdict(ev.evaluer_criteres(agregats)) == "NO-GO"

    def test_inc018_le_corpus_couvre_les_phrases_de_l_incident(self):
        par_categorie = {}
        for p in ev.charger_echantillon():
            par_categorie.setdefault(p.categorie, []).append(p)
        for categorie in ev.CATEGORIES_CREATION + ("conseil_action", "doute"):
            assert par_categorie.get(categorie), categorie
        assert any("Planche Nord" in p.texte or "planche Nord" in p.texte for p in par_categorie["creation"])
        assert any("pépinière froide" in p.texte for p in par_categorie["deux_actions"])
        assert all(p.outils_attendus == (ev.PSEUDO_TEXTE,) for p in par_categorie["conseil_action"])  # [US-257]

    def test_inc018_la_mesure_rejoue_la_boucle_de_l_agent_livre(self):
        """`lire` ouvre un tour de plus (lecture fictive) ; la réponse rendue porte les appels
        utiles, la latence et les jetons cumulés — pas le seul premier tour."""
        tours = iter([
            ReponseOutils(texte="", modele="m", appel_type="agent", latence_ms=200, tokens_in=1000,
                          tokens_out=20, appels=(AppelOutil("lire", {"quoi": "parcelle", "nom": "Planche Nord"}),)),
            ReponseOutils(texte="", modele="m", appel_type="agent", latence_ms=150, tokens_in=1100,
                          tokens_out=30, appels=(_appel("poser_question", nature="QUESTION_DATA"),)),
        ])
        with patch.object(passerelle, "appeler_chat_outils", side_effect=lambda **kw: next(tours)) as appel:
            reponse = ev.appeler_agent(CTX, "combien de rangs a la planche nord ?")
        assert [a.nom for a in reponse.appels] == ["poser_question"]
        assert reponse.latence_ms == 350 and reponse.tokens_in == 2100 and reponse.tokens_out == 50
        assert "historique" not in appel.call_args_list[0].kwargs
        historique = appel.call_args_list[1].kwargs["historique"]
        assert historique[0]["tool_calls"][0]["function"]["name"] == "lire"
        assert "Planche Nord" in historique[1]["content"]

    def test_inc018_un_tour_sans_lecture_clot_la_boucle(self):
        reponse = ReponseOutils(texte="", modele="m", appel_type="agent",
                                appels=(_appel("modifier_parcelle", parcelle="x"),))
        with patch.object(passerelle, "appeler_chat_outils", return_value=reponse) as appel:
            rendue = ev.appeler_agent(CTX, "mets x en pépinière")
        assert appel.call_count == 1 and [a.nom for a in rendue.appels] == ["modifier_parcelle"]

    def test_inc018_la_boucle_est_bornee(self):
        lecture = ReponseOutils(texte="", modele="m", appel_type="agent",
                                appels=(_appel("lire", quoi="parcelles"),))
        with patch.object(passerelle, "appeler_chat_outils", return_value=lecture) as appel:
            rendue = ev.appeler_agent(CTX, "?")
        assert appel.call_count == interpreteur_agent._max_tours() and rendue.appels == ()

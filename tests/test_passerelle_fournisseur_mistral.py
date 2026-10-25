"""
tests/test_passerelle_fournisseur_mistral.py
Fournisseur Mistral dans la passerelle LLM : un modèle préfixé `mistral/` est
servi par l'API Mistral avec le même SDK, la même mesure et le même repli.

Aucun appel réseau : le client du fournisseur est simulé.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services.context import TenantContext
from llm import passerelle
from llm.passerelle import LLMIndisponibleError, TYPE_AGENT, TYPE_CLASSIFICATION

CTX = TenantContext(user_id=7, potager_id=3, role="owner")
OUTILS = [{"type": "function", "function": {
    "name": "parcelle_modifier", "description": "x",
    "parameters": {"type": "object", "properties": {"parcelle": {"type": "string"}}},
}}]
MODELE = "mistral/ministral-3b-latest"


def _reponse(appels=(), contenu=None):
    tool_calls = [
        SimpleNamespace(id=f"abc{i}defgh", function=SimpleNamespace(name=nom, arguments=args))
        for i, (nom, args) in enumerate(appels)
    ]
    message = SimpleNamespace(content=contenu, tool_calls=tool_calls or None)
    usage = SimpleNamespace(prompt_tokens=900, completion_tokens=30, prompt_tokens_details=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)


@pytest.fixture(autouse=True)
def _capacites_propres():
    passerelle.reinitialiser_capacites_outils()
    yield
    passerelle.reinitialiser_capacites_outils()


@pytest.fixture
def mistral():
    """Client Mistral simulé, Groq simulé à côté pour vérifier qu'il n'est pas touché."""
    faux_mistral, faux_groq = MagicMock(), MagicMock()
    faux_mistral.chat.completions.create.return_value = _reponse(
        [("parcelle_modifier", '{"parcelle": "serre"}')]
    )
    with patch.dict(passerelle.GROQ_MODELE_PAR_TYPE, {TYPE_AGENT: MODELE, TYPE_CLASSIFICATION: MODELE}), \
         patch("llm.passerelle.MISTRAL_API_KEY", "cle-de-test"), \
         patch("llm.passerelle._client_mistral", faux_mistral), \
         patch("llm.passerelle._client", faux_groq), \
         patch("llm.passerelle._enregistrer_conso"), \
         patch("llm.passerelle.time.sleep"):
        yield SimpleNamespace(mistral=faux_mistral, groq=faux_groq)


class TestRoutage:

    def test_le_chemin_du_sdk_groq_est_reecrit_vers_la_route_mistral(self):
        requete = httpx.Request("POST", "https://api.mistral.ai/openai/v1/chat/completions")
        passerelle._reecrire_chemin_mistral(requete)
        assert str(requete.url) == "https://api.mistral.ai/v1/chat/completions"

    def test_un_modele_mistral_part_chez_mistral_sans_son_prefixe(self, mistral):
        reponse = passerelle.appeler_chat_outils(
            ctx=CTX, outils=OUTILS, prompt_fixe="consignes", message_utilisateur="phrase",
        )
        mistral.groq.chat.completions.create.assert_not_called()
        kwargs = mistral.mistral.chat.completions.create.call_args.kwargs
        assert kwargs["model"] == "ministral-3b-latest"
        assert reponse.modele == MODELE, "la mesure garde le préfixe : elle dit qui a servi"
        assert reponse.appels[0].nom == "parcelle_modifier"

    def test_un_modele_groq_reste_chez_groq_inchange(self, mistral):
        mistral.groq.chat.completions.create.return_value = _reponse([("parcelle_modifier", "{}")])
        with patch.dict(passerelle.GROQ_MODELE_PAR_TYPE, {TYPE_AGENT: "openai/gpt-oss-120b"}):
            passerelle.appeler_chat_outils(
                ctx=CTX, outils=OUTILS, prompt_fixe="consignes", message_utilisateur="phrase",
            )
        mistral.mistral.chat.completions.create.assert_not_called()
        kwargs = mistral.groq.chat.completions.create.call_args.kwargs
        assert kwargs["model"] == "openai/gpt-oss-120b"
        assert kwargs["tool_choice"] == "required"


class TestEcartsApiMistral:

    def test_required_devient_any_et_pas_de_reasoning_effort(self, mistral):
        passerelle.appeler_chat_outils(
            ctx=CTX, outils=OUTILS, prompt_fixe="consignes", message_utilisateur="phrase",
        )
        kwargs = mistral.mistral.chat.completions.create.call_args.kwargs
        assert kwargs["tool_choice"] == "any"
        assert "reasoning_effort" not in kwargs

    def test_un_prompt_seul_n_est_pas_envoye_en_message_system_final(self, mistral):
        mistral.mistral.chat.completions.create.return_value = _reponse(contenu="semis")
        reponse = passerelle.appeler_chat(appel_type=TYPE_CLASSIFICATION, ctx=CTX, prompt_fixe="classe")
        messages = mistral.mistral.chat.completions.create.call_args.kwargs["messages"]
        assert messages[-1]["role"] == "user"
        assert reponse.texte == "semis"

    def test_un_tour_d_outils_sans_contenu_est_envoye_avec_un_contenu_vide(self, mistral):
        historique = [
            {"role": "assistant", "content": None, "tool_calls": [{"id": "abc0defgh", "type": "function",
             "function": {"name": "lire", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "abc0defgh", "content": "résultat"},
        ]
        passerelle.appeler_chat_outils(
            ctx=CTX, outils=OUTILS, prompt_fixe="consignes", message_utilisateur="phrase",
            historique=historique,
        )
        messages = mistral.mistral.chat.completions.create.call_args.kwargs["messages"]
        assert messages[2]["content"] == ""
        assert historique[0]["content"] is None, "l'historique de l'appelant n'est pas modifié"


class TestSansCle:

    def test_sans_cle_un_type_bascule_sur_mistral_est_indisponible(self, mistral):
        with patch("llm.passerelle.MISTRAL_API_KEY", ""), \
             patch("llm.passerelle._client_mistral", None):
            with pytest.raises(LLMIndisponibleError):
                passerelle.appeler_chat(appel_type=TYPE_CLASSIFICATION, ctx=CTX, prompt_fixe="classe")
        mistral.groq.chat.completions.create.assert_not_called()

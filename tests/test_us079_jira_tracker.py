"""
tests/test_us079_jira_tracker.py — Tests US-079 : Vérifier la création automatique
d'un ticket Jira depuis une US
-----------------------------------------------------------------------------
Couverture :
  - CA1 : le fichier backlog respecte le format ID/Titre attendu par le parseur ;
          un fichier mal formé lève une erreur explicite plutôt qu'un échec silencieux
  - CA2 : create-issue crée le ticket, force le statut "À faire", et reste
          idempotent (pas de doublon si l'US existe déjà) ; mode dégradé sans token
  - CA3 : le résumé et la description du ticket créé reprennent fidèlement
          le titre et la story de l'US source
  - CA4 : la clé Jira retournée par create_issue_from_backlog est exploitable
          (celle confirmée dans le chat par l'agent Suivi-US-Jira)
"""
from unittest.mock import MagicMock, patch

import pytest

from tools import jira_tracker as jt


def _mock_response(json_data=None, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    return resp


@pytest.fixture
def jira_env(monkeypatch):
    """Configuration Jira déterministe pour les tests (indépendante du vrai .env)."""
    monkeypatch.setenv("JIRA_HOST", "https://test.atlassian.net")
    monkeypatch.setenv("JIRA_EMAIL", "test@example.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "fake-token")
    monkeypatch.setenv("JIRA_PROJECT", "PIA")
    monkeypatch.setenv("JIRA_ISSUE_TYPE", "Story")
    monkeypatch.setenv("JIRA_ENABLED", "true")


def test_us079_parse_backlog_md_champs_complets():
    """CA1 — le fichier US-079 réel expose ID et Titre au format attendu par le parseur."""
    contenu = (
        "**ID :** US-079\n"
        "**Titre :** Vérifier la création automatique d'un ticket Jira depuis une US\n\n"
        "**Story :**\nEn tant que Product Owner ...\n"
    )
    champs = jt._parse_backlog_md(contenu)
    assert champs["id"] == "US-079"
    assert champs["titre"] == "Vérifier la création automatique d'un ticket Jira depuis une US"


def test_us079_create_issue_from_backlog_creation_nominale(jira_env, tmp_path):
    """CA2/CA3/CA4 — happy path : création d'une issue, résumé/description fidèles, statut À faire forcé."""
    md = tmp_path / "US-079_test.md"
    md.write_text(
        "**ID :** US-079\n**Titre :** Vérifier la création automatique d'un ticket Jira\n\n"
        "**Story :**\nEn tant que PO je veux valider le pipeline afin de le fiabiliser\n",
        encoding="utf-8",
    )

    with patch.object(jt, "requests") as mock_requests:
        mock_requests.get.side_effect = [
            _mock_response({"issues": []}),  # _resolve_issue_key : aucune issue existante
            _mock_response({"transitions": [{"to": {"name": "À faire"}, "id": "31"}]}),  # _get_transitions
        ]
        mock_requests.post.side_effect = [
            _mock_response({"key": "PIA-999"}, status_code=201),  # création de l'issue
            _mock_response({}),  # transition vers "À faire"
        ]

        cle = jt.create_issue_from_backlog(md)

    assert cle == "PIA-999"  # CA4 : clé exploitable

    creation_call = mock_requests.post.call_args_list[0]
    payload = creation_call.kwargs["json"]
    assert payload["fields"]["summary"] == "US-079 : Vérifier la création automatique d'un ticket Jira"
    description_text = payload["fields"]["description"]["content"][0]["content"][0]["text"]
    assert "En tant que PO je veux valider le pipeline" in description_text  # CA3

    transition_call = mock_requests.post.call_args_list[1]
    assert transition_call.args[0] == "https://test.atlassian.net/rest/api/3/issue/PIA-999/transitions"  # CA2


def test_us079_create_issue_from_backlog_idempotent(jira_env, tmp_path):
    """CA2 — une US déjà présente dans Jira n'est jamais recréée (comportement observé sur le backlog réel)."""
    md = tmp_path / "US-079_test.md"
    md.write_text("**ID :** US-079\n**Titre :** Titre test\n", encoding="utf-8")

    with patch.object(jt, "requests") as mock_requests:
        mock_requests.get.return_value = _mock_response(
            {"issues": [{"key": "PIA-70", "fields": {"summary": "US-079 : Vérifier..."}}]}
        )

        cle = jt.create_issue_from_backlog(md)

    assert cle == "PIA-70"
    mock_requests.post.assert_not_called()


def test_us079_create_issue_from_backlog_token_absent(tmp_path, monkeypatch):
    """CA2 — mode dégradé : sans JIRA_API_TOKEN, aucune exception, retourne None (l'outil ne bloque jamais)."""
    monkeypatch.setenv("JIRA_API_TOKEN", "")
    monkeypatch.setenv("JIRA_ENABLED", "true")
    md = tmp_path / "US-079_test.md"
    md.write_text("**ID :** US-079\n**Titre :** Titre test\n", encoding="utf-8")

    with patch.object(jt, "requests") as mock_requests:
        cle = jt.create_issue_from_backlog(md)

    assert cle is None
    mock_requests.get.assert_not_called()
    mock_requests.post.assert_not_called()


def test_us079_create_issue_from_backlog_fichier_mal_forme(tmp_path):
    """CA1 — un fichier backlog sans ID/Titre lisible lève une erreur explicite plutôt qu'un échec silencieux."""
    md = tmp_path / "US-079_invalide.md"
    md.write_text("Un contenu sans les champs attendus.", encoding="utf-8")

    with pytest.raises(jt.JiraTrackerError):
        jt.create_issue_from_backlog(md)

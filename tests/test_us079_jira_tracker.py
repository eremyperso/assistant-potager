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


# ── Extension incidents (Analyste-Incident.agent.md) ─────────────────────────
# Un incident réutilise exactement le pipeline US-079 : seul le préfixe INC-
# change le type d'issue créé (Bug au lieu de Story) et déclenche la pose de
# pièces jointes best-effort si le fichier référence des captures locales.

def test_incident_normaliser_us_preserve_prefixe_inc():
    """Le préfixe INC est préservé (contrairement à un numéro seul, toujours US par défaut)."""
    assert jt.normaliser_us("INC-4") == "INC-004"
    assert jt.normaliser_us("inc004") == "INC-004"
    assert jt.normaliser_us(66) == "US-066"  # comportement historique inchangé


def test_incident_parse_backlog_md_id_et_captures():
    """_parse_backlog_md reconnaît un ID INC- et le champ optionnel Captures."""
    contenu = (
        "**ID :** INC-001\n"
        "**Titre :** Erreur 500 sur /culture attributs tomate\n\n"
        "**Captures :** captures/inc-001-a.png, captures/inc-001-b.png\n"
    )
    champs = jt._parse_backlog_md(contenu)
    assert champs["id"] == "INC-001"
    assert champs["captures"] == "captures/inc-001-a.png, captures/inc-001-b.png"


def test_incident_create_issue_from_backlog_type_bug(jira_env, tmp_path, monkeypatch):
    """Un fichier INC-NNN crée une issue de type JIRA_ISSUE_TYPE_INCIDENT (Bug), pas Story."""
    monkeypatch.setenv("JIRA_ISSUE_TYPE_INCIDENT", "Bug")
    md = tmp_path / "INC-001_test.md"
    md.write_text(
        "**ID :** INC-001\n**Titre :** Erreur 500 sur /culture attributs tomate\n\n"
        "**Reproduction :**\nTaper /culture attributs tomate\n",
        encoding="utf-8",
    )

    with patch.object(jt, "requests") as mock_requests:
        mock_requests.get.side_effect = [
            _mock_response({"issues": []}),
            _mock_response({"transitions": [{"to": {"name": "À faire"}, "id": "31"}]}),
        ]
        mock_requests.post.side_effect = [
            _mock_response({"key": "PIA-1000"}, status_code=201),
            _mock_response({}),
        ]

        cle = jt.create_issue_from_backlog(md)

    assert cle == "PIA-1000"
    creation_call = mock_requests.post.call_args_list[0]
    payload = creation_call.kwargs["json"]
    assert payload["fields"]["issuetype"]["name"] == "Bug"
    assert payload["fields"]["summary"] == "INC-001 : Erreur 500 sur /culture attributs tomate"


def test_incident_create_issue_from_backlog_joint_capture_existante(jira_env, tmp_path):
    """Une capture référencée et présente sur le disque est jointe après création."""
    capture = tmp_path / "capture.png"
    capture.write_bytes(b"\x89PNG\r\n")
    md = tmp_path / "INC-002_test.md"
    md.write_text(
        f"**ID :** INC-002\n**Titre :** Défaut visuel\n\n**Captures :** {capture}\n",
        encoding="utf-8",
    )

    with patch.object(jt, "requests") as mock_requests:
        mock_requests.get.side_effect = [
            _mock_response({"issues": []}),
            _mock_response({"transitions": [{"to": {"name": "À faire"}, "id": "31"}]}),
        ]
        mock_requests.post.side_effect = [
            _mock_response({"key": "PIA-1001"}, status_code=201),
            _mock_response({}),
            _mock_response({}, status_code=200),
        ]

        cle = jt.create_issue_from_backlog(md)

    assert cle == "PIA-1001"
    attachment_call = mock_requests.post.call_args_list[2]
    assert attachment_call.args[0] == "https://test.atlassian.net/rest/api/3/issue/PIA-1001/attachments"
    assert attachment_call.kwargs["headers"] == {"X-Atlassian-Token": "no-check"}


def test_incident_create_issue_from_backlog_capture_introuvable_non_bloquant(jira_env, tmp_path):
    """Une capture référencée mais absente du disque est ignorée : le ticket est quand même créé."""
    md = tmp_path / "INC-003_test.md"
    md.write_text(
        "**ID :** INC-003\n**Titre :** Défaut visuel\n\n"
        "**Captures :** /chemin/inexistant/capture.png\n",
        encoding="utf-8",
    )

    with patch.object(jt, "requests") as mock_requests:
        mock_requests.get.side_effect = [
            _mock_response({"issues": []}),
            _mock_response({"transitions": [{"to": {"name": "À faire"}, "id": "31"}]}),
        ]
        mock_requests.post.side_effect = [
            _mock_response({"key": "PIA-1002"}, status_code=201),
            _mock_response({}),
        ]

        cle = jt.create_issue_from_backlog(md)

    assert cle == "PIA-1002"
    # Seuls création + transition ont été postés — aucune tentative de pièce jointe
    assert mock_requests.post.call_count == 2

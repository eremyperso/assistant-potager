"""
tests/test_us_tracker.py
[Suivi US] Mise à jour de l'état d'avancement d'une US sur le kanban GitHub

Couverture :
  - normalisation des identifiants d'US et des statuts
  - refus explicite de « Done » (colonne réservée au déploiement)
  - mode dégradé : jeton absent, US absente, colonne absente, API en échec
  - rapprochement US ↔ carte par préfixe de titre, avec pagination
  - mutation GraphQL réellement émise sur le chemin nominal

Tous les appels réseau sont mockés — aucun test ne touche GitHub.
"""
import logging

import pytest
import requests

from tools import us_tracker
from tools.us_tracker import (
    COLONNES,
    StatutNonPiloteError,
    UsTrackerError,
    normaliser_statut,
    normaliser_us,
    update_us_status,
)

PROJECT_ID = "PVT_test"
FIELD_ID = "PVTSSF_test"
OPTIONS = [
    {"id": "opt-todo", "name": "Todo"},
    {"id": "opt-wip", "name": "In Progress"},
    {"id": "opt-qa", "name": "In QA"},
    {"id": "opt-done", "name": "Done"},
]


@pytest.fixture
def env_github(monkeypatch):
    """Configuration complète — le chemin nominal."""
    monkeypatch.setenv("GITHUB_TOKEN", "jeton-de-test")
    monkeypatch.setenv("REPO_OWNER", "eremyperso")
    monkeypatch.setenv("REPO_NAME", "assistant-potager")
    monkeypatch.setenv("PROJECT_NUMBER", "1")


def _faux_graphql(items, options=None, appels=None):
    """Remplace `_graphql` : sert le projet, les items, puis encaisse la mutation."""
    def _impl(query, variables, token):
        if appels is not None:
            appels.append((query, variables))
        if "projectV2(number:" in query:
            return {"user": {"projectV2": {
                "id": PROJECT_ID,
                "field": {"id": FIELD_ID, "options": options if options is not None else OPTIONS},
            }}}
        if "items(first:" in query:
            return {"node": {"items": {
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "nodes": items,
            }}}
        return {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "item-1"}}}
    return _impl


def _item(item_id, titre):
    return {"id": item_id, "content": {"number": 1, "title": titre}}


# ── Normalisation ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("entree,attendu", [
    (66, "US-066"), ("66", "US-066"), ("US-66", "US-066"), ("us-066", "US-066"),
    ("US066", "US-066"), (" US-6 ", "US-006"), (151, "US-151"),
])
def test_normalise_les_identifiants_dus(entree, attendu) -> None:
    """La spec appelle `update_us_status(42, ...)`, les issues s'appellent
    « US-042 : … » — les deux écritures doivent converger."""
    assert normaliser_us(entree) == attendu


def test_identifiant_illisible_rejete() -> None:
    with pytest.raises(UsTrackerError):
        normaliser_us("pas-de-numero")


@pytest.mark.parametrize("entree,attendu", [
    ("a_faire", "a_faire"), ("à faire", "a_faire"), ("Todo", "a_faire"),
    ("en_cours", "en_cours"), ("en cours", "en_cours"), ("In Progress", "en_cours"),
    ("en_qa", "en_qa"), ("QA", "en_qa"), ("in qa", "en_qa"),
])
def test_normalise_les_statuts_et_leurs_variantes(entree, attendu) -> None:
    """Agents et humains n'écrivent pas le statut de la même façon."""
    assert normaliser_statut(entree) == attendu


def test_statut_inconnu_rejete() -> None:
    with pytest.raises(UsTrackerError):
        normaliser_statut("en_pause")


@pytest.mark.parametrize("statut", ["done", "Done", "réalisé", "realise", "terminé"])
def test_done_est_refuse_explicitement(statut) -> None:
    """La colonne finale est appliquée par le déploiement : la faire poser par un
    agent afficherait comme livrée une US qui ne l'est pas."""
    with pytest.raises(StatutNonPiloteError):
        normaliser_statut(statut)


def test_done_refuse_aussi_via_update_us_status(env_github) -> None:
    """Le refus vaut au point d'entrée public, pas seulement dans le helper."""
    with pytest.raises(StatutNonPiloteError):
        update_us_status(66, "done")


def test_les_trois_colonnes_pilotees_sont_celles_du_kanban() -> None:
    """Garde-fou de mapping : ces noms doivent correspondre exactement aux colonnes
    du projet GitHub, « Done » restant hors périmètre."""
    assert COLONNES == {
        "a_faire": "Todo",
        "en_cours": "In Progress",
        "en_qa": "In QA",
    }
    assert "Done" not in COLONNES.values()


# ── Chemin nominal ───────────────────────────────────────────────────────────

def test_met_a_jour_la_carte_de_lus(env_github, monkeypatch) -> None:
    """Happy path : la mutation est émise avec l'item et l'option attendus."""
    # Arrange
    appels = []
    monkeypatch.setattr(
        us_tracker, "_graphql",
        _faux_graphql([_item("item-42", "US-066 : Réclamer le nombre de graines")], appels=appels),
    )

    # Act
    ok = update_us_status("US-066", "en_qa")

    # Assert
    assert ok is True
    mutation = [(q, v) for q, v in appels if "updateProjectV2ItemFieldValue" in q]
    assert len(mutation) == 1
    _, variables = mutation[0]
    assert variables == {
        "projectId": PROJECT_ID, "itemId": "item-42",
        "fieldId": FIELD_ID, "optionId": "opt-qa",
    }


@pytest.mark.parametrize("statut,option_attendue", [
    ("a_faire", "opt-todo"), ("en_cours", "opt-wip"), ("en_qa", "opt-qa"),
])
def test_chaque_statut_vise_la_bonne_colonne(env_github, monkeypatch, statut, option_attendue) -> None:
    appels = []
    monkeypatch.setattr(
        us_tracker, "_graphql",
        _faux_graphql([_item("item-1", "US-066 : Titre")], appels=appels),
    )

    assert update_us_status(66, statut) is True
    _, variables = [(q, v) for q, v in appels if "updateProjectV2ItemFieldValue" in q][0]
    assert variables["optionId"] == option_attendue


def test_rapprochement_ancre_sur_le_prefixe_du_titre(env_github, monkeypatch) -> None:
    """`US-06` ne doit jamais être confondue avec `US-066` : le rapprochement est
    ancré sur le début du titre, pas sur une sous-chaîne."""
    appels = []
    monkeypatch.setattr(us_tracker, "_graphql", _faux_graphql([
        _item("item-mauvais", "US-066 : Une autre US"),
        _item("item-bon", "US-006 : Renommer une parcelle"),
    ], appels=appels))

    assert update_us_status(6, "en_cours") is True
    _, variables = [(q, v) for q, v in appels if "updateProjectV2ItemFieldValue" in q][0]
    assert variables["itemId"] == "item-bon"


def test_parcourt_toutes_les_pages_ditems(env_github, monkeypatch) -> None:
    """53 items aujourd'hui, plus demain : la carte cherchée peut être en 2e page."""
    pages = [
        {"pageInfo": {"hasNextPage": True, "endCursor": "curseur-1"},
         "nodes": [_item("item-a", "US-001 : Première")]},
        {"pageInfo": {"hasNextPage": False, "endCursor": None},
         "nodes": [_item("item-b", "US-066 : Cherchée")]},
    ]
    appels = []

    def _impl(query, variables, token):
        appels.append((query, variables))
        if "projectV2(number:" in query:
            return {"user": {"projectV2": {"id": PROJECT_ID,
                                           "field": {"id": FIELD_ID, "options": OPTIONS}}}}
        if "items(first:" in query:
            return {"node": {"items": pages[0 if variables.get("after") is None else 1]}}
        return {}

    monkeypatch.setattr(us_tracker, "_graphql", _impl)

    assert update_us_status(66, "en_cours") is True
    _, variables = [(q, v) for q, v in appels if "updateProjectV2ItemFieldValue" in q][0]
    assert variables["itemId"] == "item-b"


# ── Mode dégradé — le suivi ne bloque jamais ────────────────────────────────

def test_sans_jeton_logue_et_rend_la_main(monkeypatch, caplog) -> None:
    """Parti pris assumé : une panne de kanban n'interrompt pas une implémentation."""
    # Arrange
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    def _interdit(*args, **kwargs):
        raise AssertionError("aucun appel réseau ne doit être tenté sans jeton")

    monkeypatch.setattr(us_tracker, "_graphql", _interdit)

    # Act
    with caplog.at_level(logging.WARNING, logger="us_tracker"):
        ok = update_us_status(66, "en_cours")

    # Assert
    assert ok is False
    assert "GITHUB_TOKEN absent" in caplog.text
    assert "US-066" in caplog.text
    assert "In Progress" in caplog.text  # ce qui aurait été fait est tracé


def test_us_absente_du_projet_ne_leve_pas(env_github, monkeypatch, caplog) -> None:
    """Une US dont l'issue n'a jamais été créée : signalé, non bloquant."""
    monkeypatch.setattr(us_tracker, "_graphql", _faux_graphql([_item("x", "US-001 : Autre")]))

    with caplog.at_level(logging.WARNING, logger="us_tracker"):
        ok = update_us_status(999, "en_cours")

    assert ok is False
    assert "US-999" in caplog.text


def test_colonne_absente_ne_leve_pas(env_github, monkeypatch, caplog) -> None:
    """Le kanban a été remanié et « In QA » n'existe plus : signalé, non bloquant."""
    monkeypatch.setattr(
        us_tracker, "_graphql",
        _faux_graphql([_item("item-1", "US-066 : Titre")],
                      options=[{"id": "opt-todo", "name": "Todo"}]),
    )

    with caplog.at_level(logging.WARNING, logger="us_tracker"):
        ok = update_us_status(66, "en_qa")

    assert ok is False
    assert "In QA" in caplog.text


def test_api_en_echec_ne_leve_pas(env_github, monkeypatch, caplog) -> None:
    """Cas d'erreur réseau : GitHub indisponible ou jeton expiré."""
    def _boum(*args, **kwargs):
        raise requests.RequestException("503 Service Unavailable")

    monkeypatch.setattr(us_tracker, "_graphql", _boum)

    with caplog.at_level(logging.WARNING, logger="us_tracker"):
        ok = update_us_status(66, "en_cours")

    assert ok is False
    assert "mode dégradé" in caplog.text


# ── CLI ──────────────────────────────────────────────────────────────────────

def test_cli_retourne_0_meme_en_mode_degrade(monkeypatch) -> None:
    """L'Orchestrateur peut enchaîner sur le code retour : un suivi dégradé ne doit
    pas faire échouer l'étape qu'il observe."""
    monkeypatch.setattr(us_tracker, "update_us_status", lambda *a: False)
    assert us_tracker.main(["US-066", "en_cours"]) == 0


def test_cli_retourne_2_sur_appel_fautif(monkeypatch, capsys) -> None:
    """Un statut inconnu est une erreur de l'appelant, pas un aléa : code 2."""
    assert us_tracker.main(["US-066", "done"]) == 2
    assert "déploiement" in capsys.readouterr().err


def test_cli_sans_arguments_affiche_usage(capsys) -> None:
    assert us_tracker.main([]) == 2
    sortie = capsys.readouterr().err
    assert "Usage" in sortie
    assert "Done" in sortie  # l'exclusion est rappelée à l'usage

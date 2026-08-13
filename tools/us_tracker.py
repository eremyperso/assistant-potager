"""
tools/us_tracker.py — Suivi de l'état d'avancement des User Stories
--------------------------------------------------------------------
Met à jour la colonne d'une US sur le kanban GitHub (GitHub Projects v2) au fil
de son cycle de vie : PO → Developer → QA.

Trois transitions seulement sont pilotées ici :

    a_faire   → "Todo"         le PO a fini de rédiger l'US
    en_cours  → "In Progress"  le développement est en cours ou terminé
    en_qa     → "In QA"        la QA a validé l'US

La colonne finale ("Done") est **délibérément hors de portée de cet outil** :
elle est appliquée par le déploiement, pas par un agent. Toute tentative de la
positionner ici est refusée explicitement (voir `StatutNonPiloteError`).

Le lien entre une US et son élément de kanban passe par le **titre de l'issue**,
qui commence par l'identifiant (`US-066 : ...`) — convention déjà en place dans
ce dépôt (cf. `.github/workflows/create-issues-from-backlog.yml`).

Les colonnes sont résolues **par leur nom, à chaque appel** : renommer ou
réordonner les colonnes du projet GitHub ne demande aucune modification de code.

Mode dégradé
------------
Sans `GITHUB_TOKEN`, ou si l'API GitHub est indisponible, l'outil **logue ce
qu'il aurait fait et rend la main** sans lever d'exception. Le suivi d'avancement
est de l'observabilité : une panne de kanban ne doit jamais interrompre une
implémentation en cours. Même parti pris que `BREVO_API_KEY` dans
`app/services/email.py`.

Configuration (variables d'environnement)
-----------------------------------------
    GITHUB_TOKEN     jeton avec les scopes `project` et `repo` (obligatoire)
    REPO_OWNER       propriétaire du dépôt        (défaut : eremyperso)
    REPO_NAME        nom du dépôt                 (défaut : assistant-potager)
    PROJECT_NUMBER   numéro du projet GitHub      (défaut : 1)

Usage
-----
    # En ligne de commande (c'est ainsi que les agents l'invoquent)
    python tools/us_tracker.py US-066 en_cours

    # Depuis du code Python
    from tools.us_tracker import update_us_status
    update_us_status(66, "en_cours")
"""
from __future__ import annotations

import logging
import os
import re
import sys
from typing import Optional

import requests

log = logging.getLogger("us_tracker")

GITHUB_API_URL = "https://api.github.com/graphql"
TIMEOUT_S = 15

# ── Statuts pilotés ──────────────────────────────────────────────────────────
STATUT_A_FAIRE = "a_faire"
STATUT_EN_COURS = "en_cours"
STATUT_EN_QA = "en_qa"

#: Statut logique → nom EXACT de la colonne dans le projet GitHub.
COLONNES: dict[str, str] = {
    STATUT_A_FAIRE: "Todo",
    STATUT_EN_COURS: "In Progress",
    STATUT_EN_QA: "In QA",
}

#: Écritures tolérées en entrée — les agents et les humains n'écrivent pas tous
#: le statut de la même façon (accents, espaces, formulation de la spec d'origine).
_ALIAS_STATUTS: dict[str, str] = {
    "a_faire": STATUT_A_FAIRE, "a faire": STATUT_A_FAIRE, "à faire": STATUT_A_FAIRE,
    "afaire": STATUT_A_FAIRE, "todo": STATUT_A_FAIRE,
    "en_cours": STATUT_EN_COURS, "en cours": STATUT_EN_COURS,
    "encours": STATUT_EN_COURS, "in progress": STATUT_EN_COURS, "in_progress": STATUT_EN_COURS,
    "en_qa": STATUT_EN_QA, "en qa": STATUT_EN_QA, "qa": STATUT_EN_QA,
    "in qa": STATUT_EN_QA, "in_qa": STATUT_EN_QA,
}

#: Statuts refusés : la colonne finale relève du déploiement, jamais d'un agent.
_STATUTS_NON_PILOTES: set[str] = {
    "done", "realise", "réalisé", "realisé", "réalise", "termine", "terminé", "fini",
}


class UsTrackerError(Exception):
    """Erreur de configuration ou d'usage de l'outil de suivi."""


class StatutNonPiloteError(UsTrackerError):
    """Tentative de positionner une colonne que cet outil ne pilote pas.

    « Done » est appliqué par le déploiement : le faire poser par un agent
    donnerait une US affichée comme livrée alors qu'elle n'est pas déployée.
    Refus explicite plutôt que silencieux — l'appelant doit corriger son appel.
    """


def normaliser_us(us_number: "int | str") -> str:
    """
    Normalise un identifiant d'US vers la forme `US-066` utilisée dans les titres
    d'issues. Accepte `66`, `"66"`, `"US-66"`, `"us-066"`, `"US066"`.

    Le numéro est complété à trois chiffres, comme les issues déjà créées
    (`US-006`, `US-051`…).
    """
    brut = str(us_number).strip().upper()
    match = re.search(r"(\d+)", brut)
    if not match:
        raise UsTrackerError(f"Identifiant d'US illisible : {us_number!r}")
    return f"US-{int(match.group(1)):03d}"


def normaliser_statut(status: str) -> str:
    """Normalise un statut vers sa clé canonique, ou refuse s'il n'est pas piloté."""
    cle = (status or "").strip().lower().replace("-", "_")
    if cle in _STATUTS_NON_PILOTES or cle.replace("_", " ") in _STATUTS_NON_PILOTES:
        raise StatutNonPiloteError(
            f"Le statut « {status} » n'est pas piloté par le suivi des US : la colonne "
            f"finale est appliquée par le déploiement. Statuts acceptés : "
            f"{', '.join(sorted(COLONNES))}."
        )
    canonique = _ALIAS_STATUTS.get(cle) or _ALIAS_STATUTS.get(cle.replace("_", " "))
    if canonique is None:
        raise UsTrackerError(
            f"Statut inconnu : {status!r}. Attendu : {', '.join(sorted(COLONNES))}."
        )
    return canonique


# ── Accès GitHub ─────────────────────────────────────────────────────────────

def _config() -> dict:
    """Configuration lue à chaque appel (jamais figée à l'import, pour rester
    testable et suivre un changement d'environnement en cours de session)."""
    return {
        "token": os.environ.get("GITHUB_TOKEN", "").strip(),
        "owner": os.environ.get("REPO_OWNER", "eremyperso").strip(),
        "repo": os.environ.get("REPO_NAME", "assistant-potager").strip(),
        "project_number": int(os.environ.get("PROJECT_NUMBER", "1")),
    }


def _graphql(query: str, variables: dict, token: str) -> dict:
    """Exécute une requête GraphQL GitHub et retourne le bloc `data`."""
    reponse = requests.post(
        GITHUB_API_URL,
        json={"query": query, "variables": variables},
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        timeout=TIMEOUT_S,
    )
    reponse.raise_for_status()
    charge = reponse.json()
    if charge.get("errors"):
        raise UsTrackerError(f"GitHub GraphQL : {charge['errors']}")
    return charge.get("data") or {}


_Q_PROJET = """
query($owner: String!, $number: Int!) {
  user(login: $owner) {
    projectV2(number: $number) {
      id
      field(name: "Status") {
        ... on ProjectV2SingleSelectField {
          id
          options { id name }
        }
      }
    }
  }
}
"""

_Q_ITEMS = """
query($projectId: ID!, $after: String) {
  node(id: $projectId) {
    ... on ProjectV2 {
      items(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          content {
            ... on Issue { number title }
            ... on PullRequest { number title }
          }
        }
      }
    }
  }
}
"""

_M_MAJ_STATUT = """
mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
  updateProjectV2ItemFieldValue(input: {
    projectId: $projectId
    itemId: $itemId
    fieldId: $fieldId
    value: { singleSelectOptionId: $optionId }
  }) { projectV2Item { id } }
}
"""


def _resoudre_projet(cfg: dict) -> tuple[str, str, dict[str, str]]:
    """Retourne (project_id, status_field_id, {nom_colonne: option_id}).

    Les colonnes sont résolues par leur NOM : renommer une colonne côté GitHub
    n'impose aucune modification de ce fichier.
    """
    data = _graphql(
        _Q_PROJET,
        {"owner": cfg["owner"], "number": cfg["project_number"]},
        cfg["token"],
    )
    projet = ((data.get("user") or {}).get("projectV2")) or {}
    if not projet.get("id"):
        raise UsTrackerError(
            f"Projet #{cfg['project_number']} introuvable pour « {cfg['owner']} »."
        )
    champ = projet.get("field") or {}
    if not champ.get("id"):
        raise UsTrackerError("Le projet n'expose aucun champ « Status ».")
    options = {o["name"]: o["id"] for o in champ.get("options", [])}
    return projet["id"], champ["id"], options


def _trouver_item(project_id: str, identifiant_us: str, token: str) -> Optional[str]:
    """Identifiant de l'élément de kanban dont le titre porte cette US.

    Le rapprochement se fait sur le PRÉFIXE du titre (`US-066 : ...`) : chercher
    la sous-chaîne n'importe où confondrait `US-06` avec `US-066`.
    """
    after = None
    while True:
        data = _graphql(_Q_ITEMS, {"projectId": project_id, "after": after}, token)
        items = ((data.get("node") or {}).get("items")) or {}
        for noeud in items.get("nodes") or []:
            titre = ((noeud.get("content") or {}).get("title") or "").strip()
            if re.match(rf"^{re.escape(identifiant_us)}\b", titre, flags=re.IGNORECASE):
                return noeud["id"]
        page = items.get("pageInfo") or {}
        if not page.get("hasNextPage"):
            return None
        after = page.get("endCursor")


def update_us_status(us_number: "int | str", status: str) -> bool:
    """
    Met à jour la colonne d'une US sur le kanban GitHub.

    Retourne True si le kanban a bien été mis à jour, False si l'opération a été
    abandonnée en mode dégradé (jeton absent, US absente du projet, API
    indisponible). Ne lève JAMAIS pour une cause externe : le suivi ne doit pas
    interrompre le travail qu'il observe.

    Lève en revanche `StatutNonPiloteError` ou `UsTrackerError` sur une erreur
    d'appel (statut inconnu, identifiant illisible) — celle-là est un défaut de
    l'appelant, pas un aléa d'environnement, et doit être corrigée.
    """
    identifiant = normaliser_us(us_number)
    statut = normaliser_statut(status)          # lève si l'appel est fautif
    colonne = COLONNES[statut]

    cfg = _config()
    if not cfg["token"]:
        log.warning(
            "[us_tracker] GITHUB_TOKEN absent — %s aurait été déplacée vers « %s » "
            "(mode dégradé, aucune écriture)", identifiant, colonne,
        )
        return False

    try:
        project_id, field_id, options = _resoudre_projet(cfg)

        option_id = options.get(colonne)
        if option_id is None:
            log.warning(
                "[us_tracker] Colonne « %s » absente du projet (colonnes disponibles : %s) — "
                "%s non déplacée", colonne, ", ".join(sorted(options)) or "aucune", identifiant,
            )
            return False

        item_id = _trouver_item(project_id, identifiant, cfg["token"])
        if item_id is None:
            log.warning(
                "[us_tracker] %s absente du projet #%s — aucune carte à déplacer "
                "(l'issue a-t-elle été créée depuis le backlog ?)",
                identifiant, cfg["project_number"],
            )
            return False

        _graphql(
            _M_MAJ_STATUT,
            {"projectId": project_id, "itemId": item_id, "fieldId": field_id, "optionId": option_id},
            cfg["token"],
        )
    except (requests.RequestException, UsTrackerError) as err:
        log.warning(
            "[us_tracker] Échec de mise à jour de %s vers « %s » : %s "
            "(mode dégradé — le travail en cours n'est pas interrompu)",
            identifiant, colonne, err,
        )
        return False

    log.info("[us_tracker] %s → « %s »", identifiant, colonne)
    return True


def main(argv: Optional[list[str]] = None) -> int:
    """Point d'entrée CLI : `python tools/us_tracker.py US-066 en_cours`."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s │ %(message)s")
    args = list(argv if argv is not None else sys.argv[1:])

    if len(args) != 2:
        print(
            "Usage : python tools/us_tracker.py <US> <statut>\n"
            f"  <US>     : 66, US-066…\n"
            f"  <statut> : {', '.join(sorted(COLONNES))}\n"
            "\nLa colonne « Done » n'est pas pilotée ici : elle relève du déploiement.",
            file=sys.stderr,
        )
        return 2

    try:
        ok = update_us_status(args[0], args[1])
    except UsTrackerError as err:
        print(f"❌ {err}", file=sys.stderr)
        return 2

    # Le mode dégradé n'est pas un échec de commande : il ne doit pas faire
    # échouer une étape de l'Orchestrateur qui enchaînerait sur le code retour.
    return 0 if ok else 0


if __name__ == "__main__":
    raise SystemExit(main())

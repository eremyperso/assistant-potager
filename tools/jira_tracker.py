"""
tools/jira_tracker.py — Suivi de l'état d'avancement des User Stories sur Jira
-----────────────────────────────────────────────────────────────────────────

Met à jour l'état d'une US sur Jira au fil de son cycle de vie : PO → Developer → QA.

Trois transitions seulement sont pilotées ici (libellés par défaut = workflow
observé sur le projet PIA, surchageables via `JIRA_STATUS_*`) :

    a_faire   → "À faire"        le PO a fini de rédiger l'US
    en_cours  → "En cours"       le développement est en cours ou terminé
    en_qa     → "Revue en cours" la QA a validé l'US

La colonne finale ("Terminé") est **délibérément hors de portée de cet outil**.

Le lien entre une US et son issue Jira NE passe PAS par la clé Jira elle-même
(`PIA-47`, `SCRUM-12`…) — cette clé est attribuée par Jira à la création et n'a
aucun rapport avec la numérotation `US-066` utilisée dans `backlog/`. Le
rapprochement se fait, comme l'ancien système GitHub, sur le **préfixe du
résumé de l'issue** (`US-066 : Titre...`) : toute opération sur `US-066`
commence par une recherche JQL qui résout ce préfixe vers la clé Jira réelle.

Création d'issue depuis le backlog
-----------------------------------
`create_issue_from_backlog()` lit un fichier `backlog/US-NNN_*.md` rédigé par
Persona PO (format documenté dans `.github/agents/Personna PO.agent.md`) et crée
l'issue Jira correspondante — résumé préfixé `US-NNN : Titre`, description en
bloc de code (le markdown brut, tel quel). Idempotent : si une issue portant déjà
ce préfixe existe, elle n'est pas recréée, sa clé est simplement retournée.

Mode dégradé
------------
Sans `JIRA_API_TOKEN`, ou si l'API Jira est indisponible, l'outil **logue ce
qu'il aurait fait et rend la main** sans lever d'exception. Le suivi d'avancement
est de l'observabilité : une panne de kanban ne doit jamais interrompre une
implémentation en cours.

Configuration (variables d'environnement)
-----------------------------------------
    JIRA_HOST        URL de Jira Cloud (défaut : https://eremy.atlassian.net)
    JIRA_EMAIL       email pour l'authentification Basic (défaut : eremy.perso@gmail.com)
    JIRA_API_TOKEN   token API Jira (obligatoire)
    JIRA_PROJECT     clé du projet Jira (défaut : SCRUM)
    JIRA_ISSUE_TYPE  type d'issue créé par create-issue (défaut : Story)
    JIRA_ENABLED     active/désactive l'intégration (défaut : true si token présent)
    JIRA_STATUS_A_FAIRE   libellé Jira du statut "a_faire"   (défaut : À faire)
    JIRA_STATUS_EN_COURS  libellé Jira du statut "en_cours"  (défaut : En cours)
    JIRA_STATUS_EN_QA     libellé Jira du statut "en_qa"     (défaut : Revue en cours)

Usage
-----
    # En ligne de commande (c'est ainsi que les agents l'invoquent)
    python tools/jira_tracker.py US-066 en_cours

    # Créer le ticket Jira à partir du fichier rédigé par Persona PO
    python tools/jira_tracker.py create-issue backlog/US-066_titre-court.md

    # Lister les sprints actifs
    python tools/jira_tracker.py list-sprints

    # Lister les issues d'un sprint
    python tools/jira_tracker.py list-sprint <sprint_id>

    # Depuis du code Python
    from tools.jira_tracker import update_issue_status, create_issue_from_backlog
    update_issue_status("US-066", "en_cours")
    create_issue_from_backlog("backlog/US-066_titre-court.md")
"""
from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

# Charge le bon fichier .env selon APP_ENV (dev | prod) — même convention que
# config.py. Nécessaire ici : ce module est aussi invoqué en CLI directe
# (`python tools/jira_tracker.py ...`), qui ne passe jamais par config.py et ne
# voit donc aucune variable d'environnement sans ce chargement explicite.
load_dotenv(f".env.{os.environ.get('APP_ENV', 'dev')}", override=True)

log = logging.getLogger("jira_tracker")

# ── Statuts pilotés ──────────────────────────────────────────────────────────
STATUT_A_FAIRE = "a_faire"
STATUT_EN_COURS = "en_cours"
STATUT_EN_QA = "en_qa"

#: Statut logique → nom EXACT du statut dans Jira, défauts = workflow observé
#: sur le projet PIA. Surchargeable par projet via JIRA_STATUS_* (cf. _statuts_jira).
STATUTS_JIRA: dict[str, str] = {
    STATUT_A_FAIRE: "À faire",
    STATUT_EN_COURS: "En cours",
    STATUT_EN_QA: "Revue en cours",
}


def _statuts_jira() -> dict[str, str]:
    """Mapping statut logique → libellé Jira, avec surcharge par variable d'environnement.

    Les workflows Jira ne partagent pas tous les mêmes libellés (français,
    anglais, personnalisés) : les défauts collent au projet PIA observé, mais
    restent surchargeables sans toucher au code.
    """
    return {
        STATUT_A_FAIRE: os.environ.get("JIRA_STATUS_A_FAIRE", STATUTS_JIRA[STATUT_A_FAIRE]),
        STATUT_EN_COURS: os.environ.get("JIRA_STATUS_EN_COURS", STATUTS_JIRA[STATUT_EN_COURS]),
        STATUT_EN_QA: os.environ.get("JIRA_STATUS_EN_QA", STATUTS_JIRA[STATUT_EN_QA]),
    }

#: Écritures tolérées en entrée
_ALIAS_STATUTS: dict[str, str] = {
    "a_faire": STATUT_A_FAIRE, "a faire": STATUT_A_FAIRE, "à faire": STATUT_A_FAIRE,
    "afaire": STATUT_A_FAIRE, "todo": STATUT_A_FAIRE, "to do": STATUT_A_FAIRE,
    "en_cours": STATUT_EN_COURS, "en cours": STATUT_EN_COURS,
    "encours": STATUT_EN_COURS, "in progress": STATUT_EN_COURS, "in_progress": STATUT_EN_COURS,
    "en_qa": STATUT_EN_QA, "en qa": STATUT_EN_QA, "qa": STATUT_EN_QA,
    "in qa": STATUT_EN_QA, "in_qa": STATUT_EN_QA, "in review": STATUT_EN_QA,
    "en_review": STATUT_EN_QA,
}

#: Statuts refusés
_STATUTS_NON_PILOTES: set[str] = {
    "done", "realise", "réalisé", "realisé", "réalise", "termine", "terminé", "fini",
}


class JiraTrackerError(Exception):
    """Erreur de configuration ou d'usage de l'outil de suivi Jira."""


class StatutNonPiloteError(JiraTrackerError):
    """Tentative de positionner un statut que cet outil ne pilote pas."""


def normaliser_us(us_number: int | str) -> str:
    """
    Normalise un identifiant d'US vers la forme `US-066`.
    Accepte `66`, `"66"`, `"US-66"`, `"us-066"`, `"US066"`.
    """
    brut = str(us_number).strip().upper()
    match = re.search(r"(\d+)", brut)
    if not match:
        raise JiraTrackerError(f"Identifiant d'US illisible : {us_number!r}")
    return f"US-{int(match.group(1)):03d}"


def normaliser_statut(status: str) -> str:
    """Normalise un statut vers sa clé canonique, ou refuse s'il n'est pas piloté."""
    cle = (status or "").strip().lower().replace("-", "_")
    if cle in _STATUTS_NON_PILOTES or cle.replace("_", " ") in _STATUTS_NON_PILOTES:
        raise StatutNonPiloteError(
            f"Le statut « {status} » n'est pas piloté par le suivi des US : la colonne "
            f"finale est appliquée par le déploiement. Statuts acceptés : "
            f"{', '.join(sorted(STATUTS_JIRA))}."
        )
    canonique = _ALIAS_STATUTS.get(cle) or _ALIAS_STATUTS.get(cle.replace("_", " "))
    if canonique is None:
        raise JiraTrackerError(
            f"Statut inconnu : {status!r}. Attendu : {', '.join(sorted(STATUTS_JIRA))}."
        )
    return canonique


# ── Accès Jira REST API ──────────────────────────────────────────────────────

def _config() -> dict:
    """Configuration lue à chaque appel."""
    return {
        "host": os.environ.get("JIRA_HOST", "https://eremy.atlassian.net").rstrip("/"),
        "email": os.environ.get("JIRA_EMAIL", "eremy.perso@gmail.com"),
        "token": os.environ.get("JIRA_API_TOKEN", "").strip(),
        "project": os.environ.get("JIRA_PROJECT", "SCRUM"),
        "issue_type": os.environ.get("JIRA_ISSUE_TYPE", "Story"),
        "enabled": os.environ.get("JIRA_ENABLED", "true").lower() in ("true", "1", "yes"),
    }


def _resolve_issue_key(identifiant: str, cfg: dict) -> Optional[str]:
    """
    Résout un identifiant logique (`US-066`) vers la clé Jira réelle (`PIA-47`).

    Le rapprochement se fait sur le PRÉFIXE du résumé de l'issue — chercher la
    sous-chaîne n'importe où confondrait `US-06` avec `US-066`, exactement comme
    l'ancien `_trouver_item` du tracker GitHub.
    """
    url = f"{cfg['host']}/rest/api/3/search/jql"
    try:
        response = requests.get(
            url,
            params={
                "jql": f'project = "{cfg["project"]}" AND summary ~ "{identifiant}"',
                "maxResults": 50,
                "fields": "summary",
            },
            auth=HTTPBasicAuth(cfg["email"], cfg["token"]),
            timeout=15,
        )
        response.raise_for_status()
        for issue in response.json().get("issues", []):
            resume = (issue.get("fields", {}).get("summary") or "").strip()
            if re.match(rf"^{re.escape(identifiant)}\b", resume, flags=re.IGNORECASE):
                return issue["key"]
        return None
    except requests.RequestException as err:
        log.warning(f"[jira_tracker] Recherche de {identifiant} impossible : {err}")
        return None


def _get_transitions(issue_key: str, cfg: dict) -> dict[str, str]:
    """
    Récupère les transitions disponibles pour une issue.
    Retourne un dict {nom_statut: transition_id}.
    """
    url = f"{cfg['host']}/rest/api/3/issue/{issue_key}/transitions"
    try:
        response = requests.get(
            url,
            auth=HTTPBasicAuth(cfg["email"], cfg["token"]),
            timeout=15,
        )
        response.raise_for_status()
        transitions = response.json().get("transitions", [])
        return {t["to"]["name"]: t["id"] for t in transitions}
    except requests.RequestException as err:
        log.warning(f"[jira_tracker] Impossible de récupérer les transitions pour {issue_key}: {err}")
        return {}


def _transition_issue(issue_key: str, transition_id: str, cfg: dict) -> bool:
    """Effectue une transition sur une issue Jira."""
    url = f"{cfg['host']}/rest/api/3/issue/{issue_key}/transitions"
    try:
        response = requests.post(
            url,
            json={"transition": {"id": transition_id}},
            auth=HTTPBasicAuth(cfg["email"], cfg["token"]),
            timeout=15,
        )
        response.raise_for_status()
        return True
    except requests.RequestException as err:
        log.warning(f"[jira_tracker] Erreur lors de la transition de {issue_key}: {err}")
        return False


def update_issue_status(issue_key: str, status: str) -> bool:
    """
    Met à jour le statut d'une issue Jira.

    Retourne True si la mise à jour a fonctionné, False en mode dégradé
    (token absent, API indisponible). Ne lève JAMAIS pour une cause externe.

    Lève en revanche `StatutNonPiloteError` ou `JiraTrackerError` sur une
    erreur d'appel (statut inconnu, identifiant illisible).
    """
    # Normalise et valide les paramètres (lève si défaut d'appel)
    identifiant = normaliser_us(issue_key)
    statut = normaliser_statut(status)
    statut_jira = _statuts_jira()[statut]

    cfg = _config()

    # Mode dégradé si Jira désactivé
    if not cfg["enabled"]:
        log.warning(
            "[jira_tracker] JIRA désactivé (JIRA_ENABLED=false) — "
            "%s aurait été passée à « %s »", identifiant, statut_jira
        )
        return False

    # Mode dégradé si token absent
    if not cfg["token"]:
        log.warning(
            "[jira_tracker] JIRA_API_TOKEN absent — %s aurait été passée à « %s » "
            "(mode dégradé)", identifiant, statut_jira
        )
        return False

    try:
        # Résout l'identifiant logique (US-066) vers la vraie clé Jira (PIA-47)
        cle_jira = _resolve_issue_key(identifiant, cfg)
        if cle_jira is None:
            log.warning(
                "[jira_tracker] %s introuvable dans le projet %s — aucune issue "
                "à mettre à jour (a-t-elle été créée via `create-issue` ?)",
                identifiant, cfg["project"],
            )
            return False

        # Récupère les transitions disponibles
        transitions = _get_transitions(cle_jira, cfg)
        if not transitions:
            log.warning(
                "[jira_tracker] Aucune transition trouvée pour %s (%s)", identifiant, cle_jira
            )
            return False

        # Cherche la transition vers le statut cible
        transition_id = transitions.get(statut_jira)
        if transition_id is None:
            log.warning(
                "[jira_tracker] Statut « %s » indisponible pour %s (%s) "
                "(transitions disponibles : %s)", statut_jira, identifiant, cle_jira,
                ", ".join(sorted(transitions.keys()))
            )
            return False

        # Effectue la transition
        if not _transition_issue(cle_jira, transition_id, cfg):
            return False

        log.info("[jira_tracker] %s (%s) → « %s »", identifiant, cle_jira, statut_jira)
        return True

    except (requests.RequestException, JiraTrackerError) as err:
        log.warning(
            "[jira_tracker] Échec de mise à jour de %s vers « %s » : %s "
            "(mode dégradé)", identifiant, statut_jira, err
        )
        return False


# ── Création d'issue depuis un fichier backlog (Persona PO) ─────────────────

def _parse_backlog_md(content: str) -> dict:
    """Extrait ID, titre et épic d'un fichier `backlog/US-NNN_*.md`.

    Format documenté dans `.github/agents/Personna PO.agent.md` :
    `**ID :** US-XXX`, `**Titre :** ...`, `**Épic :** ...` (optionnel).
    """
    def _champ(pattern: str) -> Optional[str]:
        m = re.search(pattern, content, flags=re.IGNORECASE)
        return m.group(1).strip() if m else None

    return {
        "id": _champ(r"\*\*ID\s*:\*\*\s*(US-\d+)"),
        "titre": _champ(r"\*\*Titre\s*:\*\*\s*(.+)"),
        "epic": _champ(r"\*\*Épic\s*:\*\*\s*(.+)"),
    }


def _markdown_to_adf(text: str) -> dict:
    """Enveloppe le markdown brut dans un unique bloc de code ADF.

    Pas de conversion markdown → ADF riche : un bloc de code préserve le
    contenu exact (critères d'acceptance, Gherkin…) et reste lisible dans
    Jira, pour un coût d'implémentation minimal.
    """
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "codeBlock",
                "attrs": {"language": "markdown"},
                "content": [{"type": "text", "text": text}],
            }
        ],
    }


def _resolve_epic_key(epic_titre: str, cfg: dict) -> Optional[str]:
    """Cherche une issue de type Epic dont le résumé correspond à `epic_titre`.

    Best-effort : ne bloque jamais la création de l'US si l'épic est
    introuvable ou si le projet Jira ne supporte pas la liaison tentée.
    """
    url = f"{cfg['host']}/rest/api/3/search/jql"
    try:
        response = requests.get(
            url,
            params={
                "jql": f'project = "{cfg["project"]}" AND issuetype = Epic AND summary ~ "{epic_titre}"',
                "maxResults": 10,
                "fields": "summary",
            },
            auth=HTTPBasicAuth(cfg["email"], cfg["token"]),
            timeout=15,
        )
        response.raise_for_status()
        issues = response.json().get("issues", [])
        return issues[0]["key"] if issues else None
    except requests.RequestException as err:
        log.warning(f"[jira_tracker] Recherche de l'épic « {epic_titre} » impossible : {err}")
        return None


def create_issue_from_backlog(md_path: "str | Path") -> Optional[str]:
    """
    Crée l'issue Jira correspondant à un fichier `backlog/US-NNN_*.md`.

    Idempotent : si une issue dont le résumé commence par `US-NNN` existe déjà
    dans le projet, elle n'est PAS recréée — sa clé est retournée telle quelle.
    Le statut « À faire » est explicitement forcé après création (le statut de
    création par défaut dépend du workflow Jira du projet, pas garanti d'y
    correspondre) — sans échouer si l'issue s'y trouve déjà.

    Retourne la clé Jira (`PIA-47`) en cas de succès, `None` en mode dégradé
    (token absent, Jira désactivé, échec réseau) — ne lève jamais pour une
    cause externe. Lève `JiraTrackerError` si le fichier est illisible ou mal
    formé (ID ou Titre absent) : c'est un défaut de l'appelant, pas un aléa.
    """
    chemin = Path(md_path)
    try:
        contenu = chemin.read_text(encoding="utf-8")
    except OSError as err:
        raise JiraTrackerError(f"Impossible de lire {chemin} : {err}")

    champs = _parse_backlog_md(contenu)
    if not champs["id"] or not champs["titre"]:
        raise JiraTrackerError(
            f"{chemin} : champs « ID » et/ou « Titre » introuvables "
            "(format attendu : voir Personna PO.agent.md)"
        )

    identifiant = normaliser_us(champs["id"])
    resume = f"{identifiant} : {champs['titre']}"

    cfg = _config()
    if not cfg["enabled"] or not cfg["token"]:
        log.warning(
            "[jira_tracker] Jira désactivé ou token absent — %s aurait été créée "
            "sous « %s » (mode dégradé)", identifiant, resume,
        )
        return None

    # Idempotence : ne recrée pas une issue déjà présente pour ce préfixe
    existante = _resolve_issue_key(identifiant, cfg)
    if existante:
        log.info("[jira_tracker] %s déjà présente sous %s — création ignorée", identifiant, existante)
        return existante

    payload = {
        "fields": {
            "project": {"key": cfg["project"]},
            "summary": resume,
            "issuetype": {"name": cfg["issue_type"]},
            "description": _markdown_to_adf(contenu),
        }
    }

    if champs["epic"]:
        epic_key = _resolve_epic_key(champs["epic"], cfg)
        if epic_key:
            payload["fields"]["parent"] = {"key": epic_key}
        else:
            log.warning(
                "[jira_tracker] Épic « %s » introuvable — %s créée sans liaison "
                "d'épic (à lier manuellement dans Jira si besoin)",
                champs["epic"], identifiant,
            )

    try:
        response = requests.post(
            f"{cfg['host']}/rest/api/3/issue",
            json=payload,
            auth=HTTPBasicAuth(cfg["email"], cfg["token"]),
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as err:
        detail = getattr(err.response, "text", "") if err.response is not None else ""
        log.warning(
            "[jira_tracker] Échec de création de %s : %s %s (mode dégradé)",
            identifiant, err, detail,
        )
        return None

    cle = response.json()["key"]
    log.info("[jira_tracker] %s → créée sous %s (%s)", identifiant, cle, resume)

    # Force le statut « À faire » : le statut de création par défaut dépend du
    # workflow Jira du projet et n'est pas garanti d'y correspondre. Si la
    # transition n'apparaît pas dans les transitions disponibles, l'issue y
    # est déjà (cas le plus courant) — rien à faire, pas d'échec à signaler.
    statut_cible = _statuts_jira()[STATUT_A_FAIRE]
    transitions = _get_transitions(cle, cfg)
    transition_id = transitions.get(statut_cible)
    if transition_id:
        if _transition_issue(cle, transition_id, cfg):
            log.info("[jira_tracker] %s (%s) → « %s »", identifiant, cle, statut_cible)
        else:
            log.warning(
                "[jira_tracker] %s créée sous %s mais transition vers « %s » "
                "échouée — statut de création laissé tel quel",
                identifiant, cle, statut_cible,
            )

    return cle


def sync_backlog(backlog_dir: "str | Path" = "backlog") -> list[tuple[str, Optional[str], str]]:
    """
    Synchronise TOUT le dossier `backlog/` vers Jira : crée dans Jira chaque US
    qui n'y existe pas encore (statut `À faire`), sans jamais déclencher de
    développement — c'est le pendant « refinement » de `create_issue_from_backlog`,
    volontairement découplé de l'Orchestrateur.

    C'est la commande à lancer après une session de rédaction avec Persona PO
    (une ou plusieurs US) pour les faire apparaître dans Jira et pouvoir les
    organiser en sprint, avant de déclencher la moindre implémentation.

    Idempotent, comme `create_issue_from_backlog` : rejouable sans dupliquer les
    issues déjà créées lors d'un appel précédent.

    Retourne une liste de tuples `(nom_fichier, cle_jira_ou_None, message)` — un
    par fichier `backlog/*.md` examiné. `cle_jira` est `None` si le fichier a été
    ignoré (mal formé, pas une US) ou si Jira était en mode dégradé.
    """
    dossier = Path(backlog_dir)
    resultats: list[tuple[str, Optional[str], str]] = []
    for chemin in sorted(dossier.glob("*.md")):
        try:
            cle = create_issue_from_backlog(chemin)
        except JiraTrackerError as err:
            resultats.append((chemin.name, None, f"ignoré : {err}"))
            continue
        resultats.append((chemin.name, cle, "OK" if cle else "mode dégradé"))
    return resultats


def list_sprints(cfg: dict) -> list[dict]:
    """Liste les sprints du projet Jira."""
    # Les boards/sprints vivent sous l'API Agile (/rest/agile/1.0/...), pas sous
    # l'API plateforme (/rest/api/3/...) qui ne connaît pas /board — d'où le 404.
    url = f"{cfg['host']}/rest/agile/1.0/board"
    try:
        # Cherche d'abord le board du projet
        response = requests.get(
            url,
            params={"projectKeyOrId": cfg["project"]},
            auth=HTTPBasicAuth(cfg["email"], cfg["token"]),
            timeout=15,
        )
        response.raise_for_status()
        boards = response.json().get("values", [])
        if not boards:
            log.warning(f"Aucun board trouvé pour le projet {cfg['project']}")
            return []

        board_id = boards[0]["id"]

        # Récupère les sprints du board
        url = f"{cfg['host']}/rest/agile/1.0/board/{board_id}/sprint"
        response = requests.get(
            url,
            auth=HTTPBasicAuth(cfg["email"], cfg["token"]),
            timeout=15,
        )
        response.raise_for_status()
        return response.json().get("values", [])

    except requests.RequestException as err:
        log.error(f"Erreur récupération sprints: {err}")
        return []


def list_sprint_issues(sprint_id: str, cfg: dict) -> list[dict]:
    """Liste les issues d'un sprint."""
    url = f"{cfg['host']}/rest/api/3/search/jql"
    try:
        response = requests.get(
            url,
            params={
                "jql": f"sprint = {sprint_id} ORDER BY key DESC",
                "maxResults": 100,
                "fields": "summary,status",
            },
            auth=HTTPBasicAuth(cfg["email"], cfg["token"]),
            timeout=15,
        )
        response.raise_for_status()
        return response.json().get("issues", [])

    except requests.RequestException as err:
        log.error(f"Erreur récupération issues du sprint: {err}")
        return []


def main(argv: Optional[list[str]] = None) -> int:
    """Point d'entrée CLI."""
    # Force l'UTF-8 en sortie : certains shells Windows (Git Bash non
    # interactif, invite cmd.exe) retombent sur le codepage système (cp1252)
    # qui ne sait pas encoder les emojis utilisés ci-dessous (⏭, ✅…).
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    logging.basicConfig(level=logging.INFO, format="%(levelname)s │ %(message)s")
    args = list(argv if argv is not None else sys.argv[1:])

    if not args:
        print(
            "Usage : python tools/jira_tracker.py <commande>\n\n"
            "Commandes:\n"
            "  <issue_key> <statut>        Mettre à jour le statut d'une issue\n"
            "  create-issue <backlog.md>   Créer l'issue Jira depuis un fichier backlog\n"
            "  sync-backlog [dossier]      Créer dans Jira toutes les US du backlog pas encore créées\n"
            "  list-sprints                Lister les sprints actifs\n"
            "  list-sprint <sprint_id>     Lister les issues d'un sprint\n\n"
            f"Statuts acceptés : {', '.join(sorted(STATUTS_JIRA))}\n",
            file=sys.stderr,
        )
        return 2

    cfg = _config()

    if args[0] == "create-issue" and len(args) > 1:
        try:
            cle = create_issue_from_backlog(args[1])
        except JiraTrackerError as err:
            print(f"❌ {err}", file=sys.stderr)
            return 2
        if cle:
            print(f"✅ Issue créée/existante : {cle}")
        return 0

    if args[0] == "sync-backlog":
        dossier = args[1] if len(args) > 1 else "backlog"
        resultats = sync_backlog(dossier)
        if not resultats:
            print(f"Aucun fichier .md trouvé dans {dossier}/")
            return 0
        print(f"Synchronisation de {dossier}/ vers Jira ({len(resultats)} fichier(s) examiné(s)) :\n")
        for nom, cle, message in resultats:
            icone = "✅" if cle else "⏭ "
            print(f"  {icone} {nom} → {cle or message}")
        return 0

    # Commandes spéciales
    if args[0] == "list-sprints":
        sprints = list_sprints(cfg)
        if sprints:
            print(f"Sprints du projet {cfg['project']}:")
            for sprint in sprints:
                print(f"  • {sprint['id']}: {sprint['name']} ({sprint['state']})")
        else:
            print("Aucun sprint trouvé")
        return 0

    if args[0] == "list-sprint" and len(args) > 1:
        sprint_id = args[1]
        issues = list_sprint_issues(sprint_id, cfg)
        if issues:
            print(f"Issues du sprint {sprint_id}:")
            for issue in issues:
                status = issue.get("fields", {}).get("status", {}).get("name", "Unknown")
                summary = issue.get("fields", {}).get("summary", "No summary")
                print(f"  • {issue['key']}: {summary} [{status}]")
        else:
            print("Aucune issue trouvée")
        return 0

    # Mise à jour de statut
    if len(args) < 2:
        print(
            "Usage : python tools/jira_tracker.py <issue_key> <statut>\n"
            f"Statuts : {', '.join(sorted(STATUTS_JIRA))}",
            file=sys.stderr,
        )
        return 2

    try:
        ok = update_issue_status(args[0], args[1])
    except JiraTrackerError as err:
        print(f"❌ {err}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

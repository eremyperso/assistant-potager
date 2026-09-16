#!/usr/bin/env python3
"""Test de connexion à l'API Jira et listing des issues."""

import os
import sys

import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

load_dotenv(".env.dev")

# Configuration — lue depuis .env.dev pour rester alignée avec jira_tracker.py
# (un projet en dur ici avait dérivé du reste de la config par le passé)
JIRA_HOST = os.environ.get("JIRA_HOST", "https://eremy.atlassian.net").rstrip("/")
JIRA_EMAIL = os.environ.get("JIRA_EMAIL", "eremy.perso@gmail.com")
JIRA_PROJECT = os.environ.get("JIRA_PROJECT", "SCRUM")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN", "").strip() or input("Paste ton API token Jira ici: ").strip()

def test_connection():
    """Test la connexion à Jira."""
    print(f"\n🔍 Test de connexion à {JIRA_HOST}...")

    url = f"{JIRA_HOST}/rest/api/3/myself"

    try:
        response = requests.get(
            url,
            auth=HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN),
            timeout=5
        )

        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Connecté ! Utilisateur: {data.get('displayName')}")
            return True
        else:
            print(f"❌ Erreur {response.status_code}: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Erreur de connexion: {e}")
        return False

def list_issues():
    """Liste les issues du projet configuré (JIRA_PROJECT)."""
    print(f"\n📋 Récupération des issues du projet {JIRA_PROJECT}...")

    # /rest/api/3/search est supprimé côté Atlassian (HTTP 410) depuis leur
    # migration vers /rest/api/3/search/jql — pagination par nextPageToken,
    # plus de startAt. Voir https://developer.atlassian.com/changelog/#CHANGE-2046
    url = f"{JIRA_HOST}/rest/api/3/search/jql"
    params = {
        "jql": f"project = {JIRA_PROJECT} ORDER BY updated DESC",
        "maxResults": 10,
        "fields": "summary,status",
    }

    try:
        response = requests.get(
            url,
            params=params,
            auth=HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN),
            timeout=5
        )

        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            issues = data.get("issues", [])

            if issues:
                print(f"✅ {len(issues)} issue(s) trouvée(s):\n")
                for issue in issues:
                    key = issue.get("key")
                    summary = issue.get("fields", {}).get("summary")
                    status = issue.get("fields", {}).get("status", {}).get("name")
                    print(f"  • {key}: {summary} [{status}]")
            else:
                print("⚠️  Aucune issue trouvée pour ce projet")
            return True
        else:
            print(f"❌ Erreur {response.status_code}: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Erreur de requête: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Test de l'API Jira")
    print("=" * 60)

    if test_connection():
        list_issues()
    else:
        print("\n⚠️  Impossible de se connecter à Jira")
        sys.exit(1)

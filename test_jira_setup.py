#!/usr/bin/env python3
"""
Script de test de l'intégration Jira pour Claude Code.
Valide que la configuration est correcte avant d'utiliser les agents Jira.
"""

import sys
import os
from pathlib import Path

# Ajouter le répertoire racine au path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Valide que les imports fonctionnent."""
    print("📦 Vérification des imports...")
    try:
        from tools.jira_tracker import (
            update_issue_status, list_sprints, list_sprint_issues,
            normaliser_us, normaliser_statut
        )
        print("   ✅ Tous les imports fonctionnent")
        return True
    except ImportError as e:
        print(f"   ❌ Erreur d'import: {e}")
        return False


def test_normalization():
    """Valide les fonctions de normalisation."""
    print("\n🔤 Test des normalisations...")
    from tools.jira_tracker import normaliser_us, normaliser_statut

    tests = [
        ("66", "US-066"),
        ("US-66", "US-066"),
        ("us-066", "US-066"),
        ("US066", "US-066"),
    ]

    all_ok = True
    for input_val, expected in tests:
        result = normaliser_us(input_val)
        status = "✅" if result == expected else "❌"
        print(f"   {status} normaliser_us({input_val!r}) = {result!r} (attendu {expected!r})")
        if result != expected:
            all_ok = False

    statut_tests = [
        ("en_cours", "en_cours"),
        ("en cours", "en_cours"),
        ("In Progress", "en_cours"),
        ("a_faire", "a_faire"),
        ("en_qa", "en_qa"),
        ("in review", "en_qa"),
    ]

    for input_val, expected in statut_tests:
        result = normaliser_statut(input_val)
        status = "✅" if result == expected else "❌"
        print(f"   {status} normaliser_statut({input_val!r}) = {result!r} (attendu {expected!r})")
        if result != expected:
            all_ok = False

    return all_ok


def test_env_config():
    """Valide que les variables d'environnement sont configurées."""
    print("\n🔐 Vérification de la configuration...")

    from dotenv import load_dotenv
    load_dotenv(".env.dev")

    required = {
        "JIRA_HOST": "https://eremy.atlassian.net",
        "JIRA_EMAIL": "eremy.perso@gmail.com",
        "JIRA_PROJECT": "PIA",
    }

    optional = {
        "JIRA_API_TOKEN": "token API (absent = mode dégradé)",
        "JIRA_ENABLED": "true/false",
    }

    all_ok = True

    for var, default in required.items():
        value = os.getenv(var, default)
        if value == default and var != "JIRA_PROJECT":
            print(f"   ⚠️  {var} = {value!r} (valeur par défaut)")
        else:
            print(f"   ✅ {var} configuré")

    for var, desc in optional.items():
        value = os.getenv(var, "")
        if var == "JIRA_API_TOKEN":
            if value:
                print(f"   ✅ {var} configuré (token présent)")
            else:
                print(f"   ⚠️  {var} absent → mode dégradé activé ({desc})")
        else:
            print(f"   ℹ️  {var} = {os.getenv(var, 'true')!r}")

    return True


def test_cli():
    """Valide que la CLI fonctionne."""
    print("\n⚙️  Test de la CLI...")

    from tools.jira_tracker import main

    # Test sans arguments
    result = main([])
    if result == 2:
        print("   ✅ CLI affiche l'aide correctement")
    else:
        print(f"   ❌ Code de retour inattendu: {result}")
        return False

    # Test avec arguments invalides
    try:
        from tools.jira_tracker import normaliser_statut, JiraTrackerError
        normaliser_statut("invalid_status")
        print("   ❌ Devrait rejeter un statut invalide")
        return False
    except JiraTrackerError:
        print("   ✅ Rejette les statuts invalides correctement")

    return True


def main():
    """Lance tous les tests."""
    print("=" * 70)
    print("🧪 Tests de l'intégration Jira pour Claude Code")
    print("=" * 70)

    results = []

    results.append(("Imports", test_imports()))
    results.append(("Normalisation", test_normalization()))
    results.append(("Configuration", test_env_config()))
    results.append(("CLI", test_cli()))

    print("\n" + "=" * 70)
    print("📊 Résumé des tests")
    print("=" * 70)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} — {name}")

    all_passed = all(result for _, result in results)

    print("\n" + "=" * 70)
    if all_passed:
        print("✅ Tous les tests passent ! La configuration Jira est prête.")
        print("\nProchaines étapes:")
        print("  1. Complétez JIRA_API_TOKEN dans .env.dev")
        print("  2. Lancez: python test_jira_api.py")
        print("  3. Lancez un orchestrateur: @Orchestrateur-US-Jira US-066")
    else:
        print("❌ Certains tests ont échoué. Vérifiez la configuration.")
        sys.exit(1)
    print("=" * 70)


if __name__ == "__main__":
    main()

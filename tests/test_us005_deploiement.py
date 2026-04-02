"""
Tests US-005 : Déploiement automatisé sur serveur Scaleway
Vérifie la structure et la cohérence des artefacts de déploiement.
Ces tests s'exécutent localement sans connexion SSH.
"""
import os
import re
import stat
import pytest


DEPLOY_SH = os.path.join(os.path.dirname(__file__), "..", "deploy.sh")
WORKFLOW   = os.path.join(os.path.dirname(__file__), "..", ".github", "workflows", "deploy.yml")
SERVICE    = os.path.join(os.path.dirname(__file__), "..", "infra", "potager.service")


class TestDeploySh:
    """CA1 — deploy.sh existe et contient les étapes obligatoires."""

    def test_fichier_existe(self):
        assert os.path.isfile(DEPLOY_SH), "deploy.sh introuvable"

    def test_contient_rsync_ou_git_pull(self):
        content = open(DEPLOY_SH).read()
        assert "git pull" in content or "rsync" in content

    def test_contient_pip_install(self):
        """CA2 — les dépendances sont installées."""
        content = open(DEPLOY_SH).read()
        assert "pip install" in content

    def test_contient_migration_sql(self):
        """CA2 — les migrations SQL sont appliquées."""
        content = open(DEPLOY_SH).read()
        assert "migration" in content.lower()

    def test_contient_redemarrage_systemd(self):
        """CA3 — le service systemd est redémarré."""
        content = open(DEPLOY_SH).read()
        assert "systemctl restart" in content

    def test_aucun_token_hardcode(self):
        """CA4 — aucun secret dans deploy.sh."""
        content = open(DEPLOY_SH).read()
        assert "TOKEN" not in content or "TOKEN_PROD" not in content
        # Pas de token Telegram de la forme NNNNNNNNN:XXXXX
        tokens = re.findall(r"\d{8,10}:[A-Za-z0-9_-]{30,}", content)
        assert tokens == [], f"Token(s) hardcodé(s) trouvé(s) : {tokens}"

    def test_smoke_test_present(self):
        """CA5 — smoke test après déploiement."""
        content = open(DEPLOY_SH).read()
        assert "health" in content.lower() or "smoke" in content.lower()

    def test_secrets_charges_depuis_env_prod(self):
        """CA4 — les secrets viennent du fichier .env.prod sur le serveur."""
        content = open(DEPLOY_SH).read()
        assert ".env.prod" in content


class TestWorkflowGitHubActions:
    """CA1 — Le workflow GitHub Actions est valide (structure YAML)."""

    def test_fichier_existe(self):
        assert os.path.isfile(WORKFLOW), ".github/workflows/deploy.yml introuvable"

    def test_declenche_sur_push_main(self):
        content = open(WORKFLOW).read()
        assert "branches: [main]" in content or "branches:\n    - main" in content

    def test_secrets_via_github_secrets(self):
        """CA4 — les credentials passent par GitHub Secrets, pas en dur."""
        content = open(WORKFLOW).read()
        assert "secrets.SCALEWAY_SSH_PRIVATE_KEY" in content
        assert "secrets.SCALEWAY_HOST" in content
        # Pas de clé SSH ni password en dur
        assert "-----BEGIN" not in content

    def test_contient_smoke_test(self):
        """CA5 — smoke test présent dans le workflow."""
        content = open(WORKFLOW).read()
        assert "health" in content

    def test_contient_migration_sql(self):
        """CA2 — migrations SQL incluses dans le workflow."""
        content = open(WORKFLOW).read()
        assert "migration" in content.lower()


class TestSystemdService:
    """CA3 — Le fichier systemd configure le redémarrage automatique."""

    def test_fichier_existe(self):
        assert os.path.isfile(SERVICE), "infra/potager.service introuvable"

    def test_restart_on_failure(self):
        content = open(SERVICE).read()
        assert "Restart=on-failure" in content

    def test_environment_file_env_prod(self):
        """CA4 — les secrets sont chargés depuis EnvironmentFile=/opt/potager/.env.prod."""
        content = open(SERVICE).read()
        assert "EnvironmentFile" in content
        assert ".env.prod" in content

    def test_app_env_prod(self):
        """CA3 — APP_ENV est positionné à prod dans le service."""
        content = open(SERVICE).read()
        assert "APP_ENV=prod" in content

    def test_wanted_by_multi_user(self):
        """CA3 — le service démarre au boot."""
        content = open(SERVICE).read()
        assert "WantedBy=multi-user.target" in content

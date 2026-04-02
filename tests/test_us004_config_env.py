"""
Tests US-004 : Gestion des environnements dev et production
Vérifie que config.py charge le bon fichier .env selon APP_ENV.
"""
import importlib
import os
import sys
import pytest


def _reload_config(monkeypatch, env_name, env_vars):
    """Helper : positionne APP_ENV, injecte les vars, recharge config."""
    monkeypatch.setenv("APP_ENV", env_name)
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    # Forcer le rechargement du module config
    if "config" in sys.modules:
        monkeypatch.delitem(sys.modules, "config")
    import config
    return config


class TestConfigChargeEnvDev:
    """CA3 — config.py charge .env.dev quand APP_ENV=dev"""

    def test_token_dev_utilise(self, monkeypatch, tmp_path):
        """Le token TOKEN_DEV est chargé depuis .env.dev."""
        env_file = tmp_path / ".env.dev"
        env_file.write_text(
            "TELEGRAM_BOT_TOKEN=TOKEN_DEV_TEST\n"
            "GROQ_API_KEY=GROQ_DEV\n"
            "DATABASE_URL=postgresql://localhost/potager_dev\n"
        )
        monkeypatch.chdir(tmp_path)
        config = _reload_config(monkeypatch, "dev", {})
        assert config.TELEGRAM_BOT_TOKEN == "TOKEN_DEV_TEST"

    def test_bdd_locale_utilisee(self, monkeypatch, tmp_path):
        """La DATABASE_URL pointe vers PostgreSQL local en mode dev."""
        env_file = tmp_path / ".env.dev"
        env_file.write_text(
            "TELEGRAM_BOT_TOKEN=TOKEN_DEV_TEST\n"
            "GROQ_API_KEY=GROQ_DEV\n"
            "DATABASE_URL=postgresql://localhost/potager_dev\n"
        )
        monkeypatch.chdir(tmp_path)
        config = _reload_config(monkeypatch, "dev", {})
        assert "localhost" in config.DATABASE_URL


class TestConfigChargeEnvProd:
    """CA3 — config.py charge .env.prod quand APP_ENV=prod"""

    def test_token_prod_utilise(self, monkeypatch, tmp_path):
        """Le token TOKEN_PROD est chargé depuis .env.prod."""
        env_file = tmp_path / ".env.prod"
        env_file.write_text(
            "TELEGRAM_BOT_TOKEN=TOKEN_PROD_TEST\n"
            "GROQ_API_KEY=GROQ_PROD\n"
            "DATABASE_URL=postgresql://scaleway-host/potager\n"
        )
        monkeypatch.chdir(tmp_path)
        config = _reload_config(monkeypatch, "prod", {})
        assert config.TELEGRAM_BOT_TOKEN == "TOKEN_PROD_TEST"

    def test_bdd_scaleway_utilisee(self, monkeypatch, tmp_path):
        """La DATABASE_URL pointe vers Scaleway en mode prod."""
        env_file = tmp_path / ".env.prod"
        env_file.write_text(
            "TELEGRAM_BOT_TOKEN=TOKEN_PROD_TEST\n"
            "GROQ_API_KEY=GROQ_PROD\n"
            "DATABASE_URL=postgresql://scaleway-host/potager\n"
        )
        monkeypatch.chdir(tmp_path)
        config = _reload_config(monkeypatch, "prod", {})
        assert "scaleway-host" in config.DATABASE_URL


class TestConfigAucunSecretHardcode:
    """CA4 — Aucun token ou mot de passe hardcodé dans config.py"""

    def test_pas_de_token_hardcode(self):
        """config.py ne doit contenir aucun token Telegram réel."""
        with open("config.py", "r", encoding="utf-8") as f:
            source = f.read()
        # Un token Telegram réel est de la forme XXXXXXXXX:YYYYYYY
        import re
        tokens = re.findall(r"\d{8,10}:[A-Za-z0-9_-]{30,}", source)
        assert tokens == [], f"Token(s) Telegram hardcodé(s) trouvé(s) : {tokens}"

    def test_pas_de_cle_groq_hardcodee(self):
        """config.py ne doit contenir aucune clé GROQ réelle."""
        with open("config.py", "r", encoding="utf-8") as f:
            source = f.read()
        assert "gsk_" not in source, "Clé GROQ hardcodée trouvée dans config.py"

    def test_pas_de_mot_de_passe_bdd_hardcode(self):
        """config.py ne doit contenir aucun mot de passe PostgreSQL réel."""
        with open("config.py", "r", encoding="utf-8") as f:
            source = f.read()
        # Vérifie qu'aucune URL postgresql://user:password@ n'est présente
        import re
        urls = re.findall(r"postgresql://[^:]+:[^@]+@", source)
        assert urls == [], f"Credentials BDD hardcodés trouvés : {urls}"


class TestConfigErreurSiVarManquante:
    """CA4 — config.py lève une erreur si une variable obligatoire est absente"""

    def test_erreur_si_token_manquant(self, monkeypatch, tmp_path):
        """KeyError si TELEGRAM_BOT_TOKEN absent du fichier .env."""
        env_file = tmp_path / ".env.dev"
        env_file.write_text(
            "GROQ_API_KEY=GROQ_DEV\n"
            "DATABASE_URL=postgresql://localhost/potager_dev\n"
            # TELEGRAM_BOT_TOKEN intentionnellement absent
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        if "config" in sys.modules:
            monkeypatch.delitem(sys.modules, "config")
        with pytest.raises(KeyError):
            import config

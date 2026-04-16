"""
Tests US-008 : Commande /version dans le bot Telegram
Vérifie la lecture du fichier VERSION, du SHA git, et du endpoint /health.
"""
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _make_update(text="/version"):
    """Construit un faux objet Update Telegram pour les tests."""
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    return update


def _make_ctx():
    ctx = MagicMock()
    ctx.args = []
    return ctx


# ══════════════════════════════════════════════════════════════════════════════
# CA1 — Fichier VERSION existe et est lu correctement
# ══════════════════════════════════════════════════════════════════════════════

class TestCA1FichierVersion:
    def test_lire_version_retourne_contenu(self, tmp_path, monkeypatch):
        """_lire_version() retourne le contenu du fichier VERSION sans espace."""
        version_file = tmp_path / "VERSION"
        version_file.write_text("2.14.1\n")
        # Patch __file__ pour pointer vers tmp_path
        import bot
        with patch("os.path.dirname", return_value=str(tmp_path)):
            result = bot._lire_version()
        assert result == "2.14.1"

    def test_lire_version_absent_retourne_inconnue(self, tmp_path, monkeypatch):
        """_lire_version() retourne 'inconnue' si le fichier n'existe pas."""
        import bot
        with patch("os.path.dirname", return_value=str(tmp_path)):
            result = bot._lire_version()
        assert result == "inconnue"

    def test_lire_version_sans_newline(self, tmp_path):
        """_lire_version() strip les espaces et sauts de ligne."""
        version_file = tmp_path / "VERSION"
        version_file.write_text("  2.14.1  \n")
        import bot
        with patch("os.path.dirname", return_value=str(tmp_path)):
            result = bot._lire_version()
        assert result == "2.14.1"


# ══════════════════════════════════════════════════════════════════════════════
# CA2 & CA3 — Réponse nominale de /version
# ══════════════════════════════════════════════════════════════════════════════

class TestCA2CA3ReponseNominale:
    @pytest.mark.asyncio
    async def test_version_contient_version(self):
        """/version répond avec le numéro de version."""
        import bot
        update = _make_update()
        with patch.object(bot, "_APP_VERSION", "2.14.1"), \
             patch.object(bot, "_APP_GIT_SHA", "a1b2c3d"), \
             patch.dict(os.environ, {"APP_ENV": "prod"}):
            await bot.cmd_version(update, _make_ctx())

        texte = update.message.reply_text.call_args[0][0]
        assert "2.14.1" in texte

    @pytest.mark.asyncio
    async def test_version_contient_sha(self):
        """/version répond avec le SHA git."""
        import bot
        update = _make_update()
        with patch.object(bot, "_APP_VERSION", "2.14.1"), \
             patch.object(bot, "_APP_GIT_SHA", "a1b2c3d"), \
             patch.dict(os.environ, {"APP_ENV": "prod"}):
            await bot.cmd_version(update, _make_ctx())

        texte = update.message.reply_text.call_args[0][0]
        assert "a1b2c3d" in texte

    @pytest.mark.asyncio
    async def test_version_contient_env(self):
        """/version répond avec l'environnement APP_ENV."""
        import bot
        update = _make_update()
        with patch.object(bot, "_APP_VERSION", "2.14.1"), \
             patch.object(bot, "_APP_GIT_SHA", "a1b2c3d"), \
             patch.dict(os.environ, {"APP_ENV": "prod"}):
            await bot.cmd_version(update, _make_ctx())

        texte = update.message.reply_text.call_args[0][0]
        assert "prod" in texte

    @pytest.mark.asyncio
    async def test_version_utilise_markdown(self):
        """/version utilise parse_mode Markdown."""
        import bot
        update = _make_update()
        with patch.object(bot, "_APP_VERSION", "2.14.1"), \
             patch.object(bot, "_APP_GIT_SHA", "a1b2c3d"), \
             patch.dict(os.environ, {"APP_ENV": "dev"}):
            await bot.cmd_version(update, _make_ctx())

        kwargs = update.message.reply_text.call_args[1]
        assert kwargs.get("parse_mode") == "Markdown"


# ══════════════════════════════════════════════════════════════════════════════
# CA4 — Fichier VERSION absent : pas d'exception
# ══════════════════════════════════════════════════════════════════════════════

class TestCA4FichierAbsent:
    @pytest.mark.asyncio
    async def test_version_absente_repond_sans_exception(self):
        """/version répond 'inconnue' si VERSION est absent, sans lever d'exception."""
        import bot
        update = _make_update()
        with patch.object(bot, "_APP_VERSION", "inconnue"), \
             patch.object(bot, "_APP_GIT_SHA", "inconnu"), \
             patch.dict(os.environ, {"APP_ENV": "dev"}):
            await bot.cmd_version(update, _make_ctx())  # ne doit pas lever

        texte = update.message.reply_text.call_args[0][0]
        assert "inconnue" in texte


# ══════════════════════════════════════════════════════════════════════════════
# CA5 — Git indisponible : SHA affiché est "inconnu"
# ══════════════════════════════════════════════════════════════════════════════

class TestCA5GitIndisponible:
    def test_lire_git_sha_retourne_inconnu_si_git_absent(self):
        """_lire_git_sha() retourne 'inconnu' si git échoue."""
        import bot
        with patch("subprocess.run", side_effect=FileNotFoundError("git not found")):
            result = bot._lire_git_sha()
        assert result == "inconnu"

    def test_lire_git_sha_retourne_inconnu_si_pas_repo(self):
        """_lire_git_sha() retourne 'inconnu' si le répertoire n'est pas un dépôt git."""
        import subprocess
        import bot
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(128, "git")):
            result = bot._lire_git_sha()
        assert result == "inconnu"

    @pytest.mark.asyncio
    async def test_version_sha_inconnu_dans_reponse(self):
        """/version affiche 'inconnu' comme SHA quand git n'est pas disponible."""
        import bot
        update = _make_update()
        with patch.object(bot, "_APP_VERSION", "2.14.1"), \
             patch.object(bot, "_APP_GIT_SHA", "inconnu"), \
             patch.dict(os.environ, {"APP_ENV": "dev"}):
            await bot.cmd_version(update, _make_ctx())

        texte = update.message.reply_text.call_args[0][0]
        assert "inconnu" in texte
        assert "2.14.1" in texte


# ══════════════════════════════════════════════════════════════════════════════
# CA6 — /health de l'API lit la version depuis VERSION
# ══════════════════════════════════════════════════════════════════════════════

def _mock_session_local():
    """Retourne un faux SessionLocal dont .query().count() renvoie 0."""
    session = MagicMock()
    session.query.return_value.count.return_value = 0
    ctx_mgr = MagicMock()
    ctx_mgr.__enter__ = MagicMock(return_value=session)
    ctx_mgr.__exit__ = MagicMock(return_value=False)
    return session


class TestCA6HealthEndpoint:
    def test_health_version_lue_depuis_fichier(self):
        """GET /health retourne la version lue depuis VERSION, pas une valeur codée en dur."""
        from fastapi.testclient import TestClient
        import main
        fake_session = _mock_session_local()
        with patch.object(main, "_APP_VERSION", "2.14.1"), \
             patch("main.SessionLocal", return_value=fake_session):
            client = TestClient(main.app)
            response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "2.14.1"
        assert data["version"] != "2.0-groq"

    def test_health_retourne_status_ok(self):
        """GET /health retourne status: ok."""
        from fastapi.testclient import TestClient
        import main
        fake_session = _mock_session_local()
        with patch("main.SessionLocal", return_value=fake_session):
            client = TestClient(main.app)
            response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

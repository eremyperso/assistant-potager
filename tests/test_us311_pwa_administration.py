"""
tests/test_us311_pwa_administration.py — [US-311] La PWA d'administration « Pilotage ».

Le code de l'application (`admin/`) est testé par `npm test` (formats, périodes, filtres dans l'adresse,
client, service worker, manifeste). Ici : ce qui relève du dépôt et de l'API — le paquet, le montage sous
`/pilotage/`, la décision d'accès sur `/auth/me`, le déploiement et l'étanchéité avec le frontend.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import auth as svc_auth
from database.db import Base
from database.models import Potager, User

ROOT = Path(__file__).resolve().parent.parent
ADMIN = ROOT / "admin"
ADMIN_EMAIL = "admin@example.com"


def _lire(chemin: Path) -> str:
    return chemin.read_text(encoding="utf-8")


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — l'application vit dans admin/, partage la config Tailwind et les jetons
# ═════════════════════════════════════════════════════════════════════════════

class TestCA1Paquet:

    def test_us311_ca1_paquet_manifeste_icone_et_service_worker(self):
        paquet = json.loads(_lire(ADMIN / "package.json"))
        assert paquet["scripts"]["build"] == "vite build" and "test" in paquet["scripts"]
        assert {"react", "react-dom"} <= set(paquet["dependencies"])
        assert (ADMIN / "public" / "manifest.webmanifest").is_file()
        assert (ADMIN / "public" / "sw.js").is_file()
        assert (ADMIN / "public" / "icons" / "icon-512.png").is_file()

    def test_us311_ca1_la_config_tailwind_etend_celle_du_frontend(self):
        config = _lire(ADMIN / "tailwind.config.js")
        assert "../frontend/tailwind.config.js" in config
        assert "...base" in config
        assert "colors" not in config            # aucun jeton recopié

    def test_us311_ca1_les_jetons_viennent_de_la_feuille_du_frontend(self):
        css = _lire(ADMIN / "src" / "index.css")
        assert "../../frontend/src/index.css" in css
        assert "--brand:" not in css and "--bg:" not in css   # rien de recopié

    def test_us311_ca1_aucun_code_metier_du_jardinier_importe(self):
        for fichier in (ADMIN / "src").rglob("*.js*"):
            for importe in re.findall(r"from\s+['\"]([^'\"]+)['\"]", _lire(fichier)):
                assert "frontend" not in importe, f"{fichier.name} importe {importe}"

    def test_us311_ca1_le_dossier_a_son_claude_md(self):
        assert "/pilotage/" in _lire(ADMIN / "CLAUDE.md")


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — servie sous /pilotage/, portée limitée à ce chemin
# ═════════════════════════════════════════════════════════════════════════════

class TestCA2Chemin:

    def test_us311_ca2_la_base_de_vite_est_pilotage(self):
        assert "base: '/pilotage/'" in _lire(ADMIN / "vite.config.js")

    def test_us311_ca2_le_manifeste_est_limite_au_chemin(self):
        manifeste = json.loads(_lire(ADMIN / "public" / "manifest.webmanifest"))
        assert manifeste["scope"] == manifeste["start_url"] == "/pilotage/"
        assert manifeste["display"] == "standalone"

    def test_us311_ca2_l_api_monte_admin_dist_sous_pilotage(self):
        source = _lire(ROOT / "app" / "api" / "main.py")
        assert re.search(r'app\.mount\(\s*"/pilotage"\s*,\s*StaticFiles\(directory=_ADMIN_DIST', source)
        assert 'os.path.join(_RACINE, "admin", "dist")' in source

    def test_us311_ca2_pilotage_sans_barre_finale_redirige_et_n_ouvre_pas_l_application_des_jardiniers(self):
        """`/pilotage` (sans `/`) tombait sur le repli SPA des jardiniers : il doit rediriger."""
        source = _lire(ROOT / "app" / "api" / "main.py")
        assert re.search(r'@app\.get\("/pilotage", include_in_schema=False\)\s+def pilotage_sans_barre\(\):\s+return RedirectResponse\("/pilotage/"\)', source)
        # déclarée AVANT le repli SPA : Starlette essaie les routes dans l'ordre d'enregistrement
        assert source.index('@app.get("/pilotage"') < source.index('@app.get("/{chemin_complet:path}"')

    def test_us311_ca2_les_routes_du_jardinier_et_admin_ne_changent_pas(self):
        from app.api.main import app

        chemins = set(app.openapi()["paths"])
        for attendu in ("/admin/routage/metriques", "/admin/savoir/lacunes", "/auth/me", "/health"):
            assert attendu in chemins
        assert not any(c.startswith("/pilotage") for c in chemins)   # un montage statique, pas une route d'API

    def test_us311_ca2_la_coquille_est_servie_quand_elle_est_construite(self, tmp_path, monkeypatch):
        """Montage réel sur un `dist` factice : la page, ses ressources et le service worker sortent
        de /pilotage/, sans rien changer à la racine."""
        from fastapi import FastAPI
        from fastapi.staticfiles import StaticFiles

        (tmp_path / "index.html").write_text("<html>Pilotage</html>", encoding="utf-8")
        (tmp_path / "sw.js").write_text("// sw", encoding="utf-8")
        mini = FastAPI()
        mini.mount("/pilotage", StaticFiles(directory=tmp_path, html=True), name="pilotage")
        client = TestClient(mini)
        assert "Pilotage" in client.get("/pilotage/").text
        assert client.get("/pilotage/sw.js").status_code == 200
        assert client.get("/sw.js").status_code == 404


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — connexion existante ; seul ADMIN_EMAIL entre, avant toute donnée
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def api(monkeypatch):
    from app.api import main

    moteur = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=moteur)
    Session = sessionmaker(bind=moteur)
    with Session() as s:
        s.add_all([
            User(id=1, email=ADMIN_EMAIL, nom="Admin"),
            User(id=2, email="jardinier@example.com", nom="Jardinier"),
            Potager(id=1, nom="Potager", proprietaire_id=1),
        ])
        s.commit()
    monkeypatch.setattr(main, "SessionLocal", Session)
    monkeypatch.setattr(main, "ADMIN_EMAIL", ADMIN_EMAIL)
    main.app.state.limiter.reset()
    with TestClient(main.app) as client:
        yield client
    moteur.dispose()


def _jeton(user_id: int) -> dict:
    return {"Authorization": f"Bearer {svc_auth.creer_access_token(user_id)}"}


class TestCA3Acces:

    def test_us311_ca3_l_administrateur_est_reconnu_sur_auth_me(self, api):
        assert api.get("/auth/me", headers=_jeton(1)).json()["administrateur"] is True

    def test_us311_ca3_un_jardinier_ne_l_est_pas(self, api):
        corps = api.get("/auth/me", headers=_jeton(2)).json()
        assert corps["administrateur"] is False and corps["email"] == "jardinier@example.com"

    def test_us311_ca3_sans_admin_email_personne_n_est_administrateur(self, api, monkeypatch):
        from app.api import main

        monkeypatch.setattr(main, "ADMIN_EMAIL", "")
        assert api.get("/auth/me", headers=_jeton(1)).json()["administrateur"] is False

    def test_us311_ca3_la_decision_est_celle_de_require_admin_user(self, monkeypatch):
        from app.api import main

        monkeypatch.setattr(main, "ADMIN_EMAIL", "Admin@Example.com")
        assert main.est_administrateur(User(id=1, email="admin@example.com")) is True
        assert main.est_administrateur(User(id=2, email="autre@example.com")) is False
        assert main.est_administrateur(User(id=3, email=None)) is False

    def test_us311_ca3_sans_jeton_auth_me_reste_protege(self, api):
        assert api.get("/auth/me").status_code == 401

    def test_us311_ca3_le_client_decide_l_acces_avant_toute_requete_admin(self):
        """L'ordre est écrit dans l'application : `/auth/me` d'abord, les vues seulement si `ok`."""
        session = _lire(ADMIN / "src" / "hooks" / "useSession.js")
        assert "moi.administrateur ? 'ok' : 'reserve'" in session
        app = _lire(ADMIN / "src" / "App.jsx")
        assert app.index("EcranAccesReserve") < app.index("<Vue ")

    def test_us311_ca3_le_cors_accepte_le_serveur_de_dev_de_l_admin(self):
        assert "http://localhost:3001" in _lire(ROOT / "app" / "api" / "main.py")


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — le service worker ne met aucune réponse /admin/ en cache
# ═════════════════════════════════════════════════════════════════════════════

class TestCA7ServiceWorker:

    def test_us311_ca7_le_service_worker_exclut_admin_et_auth(self):
        sw = _lire(ADMIN / "public" / "sw.js")
        assert "(admin|auth)" in sw
        assert "ignorer" in sw

    def test_us311_ca7_aucune_donnee_d_admin_n_est_ecrite_dans_le_stockage(self):
        for fichier in (ADMIN / "src").rglob("*.js*"):
            if fichier.name.endswith(".test.js") or "fixtures" in fichier.parts:
                continue
            code = _lire(fichier)
            ecritures = re.findall(r"(?:localStorage|sessionStorage|stockage)\.setItem\(([^)]*)\)", code)
            for ecriture in ecritures:
                assert "donnees" not in ecriture and "synthese" not in ecriture, f"{fichier.name} : {ecriture}"


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — les déploiements dev et prod construisent et publient admin/
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("fichier,env,url", [
    ("deploy.yml", "prod", "https://potager.eremy.fr"),
    ("deploy-dev.yml", "dev", "https://dev.potager.eremy.fr"),
])
class TestCA8Deploiement:

    def test_us311_ca8_le_workflow_construit_admin(self, fichier, env, url):
        workflow = _lire(ROOT / ".github" / "workflows" / fichier)
        assert "cd admin" in workflow and "npm run build" in workflow
        assert f"VITE_API_URL={url}" in workflow

    def test_us311_ca8_le_workflow_publie_admin_dist(self, fichier, env, url):
        workflow = _lire(ROOT / ".github" / "workflows" / fichier)
        assert re.search(rf"rsync[^\n]*admin/dist/[^\n]*\\?\s*\n?[^\n]*/opt/potager-{env}/admin/dist/", workflow)

    def test_us311_ca8_admin_est_construit_apres_le_frontend(self, fichier, env, url):
        """Sa config Tailwind étend celle du frontend, dont `node_modules` vient d'être installé."""
        workflow = _lire(ROOT / ".github" / "workflows" / fichier)
        assert workflow.index("Build frontend React") < workflow.index("Build admin PWA")

    def test_us311_ca8_les_tests_de_l_admin_passent_avant_la_publication(self, fichier, env, url):
        workflow = _lire(ROOT / ".github" / "workflows" / fichier)
        assert workflow.index("npm test") < workflow.index("Deploy admin dist")


def test_us311_ca8_le_runbook_decrit_le_build_de_l_admin():
    runbook = _lire(ROOT / "docs" / "RUNBOOK" / "RUNBOOK_DEPLOIEMENT_PRODUCTION.md")
    assert "admin/dist" in runbook and "/pilotage/" in runbook


def test_us311_ca8_les_artefacts_de_build_ne_sont_pas_versionnes():
    ignore = _lire(ROOT / ".gitignore")
    assert "admin/node_modules/" in ignore and "admin/dist/" in ignore


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — le frontend du jardinier ne contient rien de l'administration
# ═════════════════════════════════════════════════════════════════════════════

class TestCA9Etancheite:

    def test_us311_ca9_aucun_module_du_frontend_n_importe_admin(self):
        for fichier in (ROOT / "frontend" / "src").rglob("*.js*"):
            for importe in re.findall(r"(?:from|import)\s*\(?\s*['\"]([^'\"]+)['\"]", _lire(fichier)):
                assert "admin/" not in importe and not importe.endswith("/admin"), f"{fichier} importe {importe}"
                assert "pilotage" not in importe.lower(), f"{fichier} importe {importe}"

    def test_us311_ca9_la_build_du_frontend_ne_voit_pas_admin(self):
        vite = _lire(ROOT / "frontend" / "vite.config.js")
        tailwind = _lire(ROOT / "frontend" / "tailwind.config.js")
        assert "admin" not in vite and "../admin" not in tailwind

    def test_us311_ca9_le_bundle_du_frontend_n_a_pas_de_service_worker_pilotage(self):
        dist = ROOT / "frontend" / "dist"
        if not dist.is_dir():
            pytest.skip("frontend/dist non construit")
        for fichier in (dist / "assets").glob("*.js"):
            assert "/pilotage/" not in fichier.read_text(encoding="utf-8", errors="ignore"), fichier.name

# ═════════════════════════════════════════════════════════════════════════════
# CA10 — conformité à la maquette d'US-318 (ce qui se vérifie sans navigateur)
# ═════════════════════════════════════════════════════════════════════════════

class TestCA10Maquette:
    """Le rendu à 375 / 768 / 1280 px se compare à l'écran (voir la validation visuelle) ; ici, les
    règles de la maquette qui s'écrivent dans le code."""

    def test_us311_ca10_un_seul_jeton_ajoute_a_l_identite(self):
        css = _lire(ADMIN / "src" / "index.css")
        valeurs = re.findall(r"--([a-z0-9-]+)\s*:\s*([^;]+);", css)
        nouvelles = {nom for nom, valeur in valeurs if not valeur.strip().startswith("var(")}
        assert nouvelles == {"brand-soft-strong"}

    def test_us311_ca10_les_series_sont_des_alias_des_teintes_de_l_application(self):
        css = _lire(ADMIN / "src" / "index.css")
        for serie, teinte in (("1", "blue"), ("2", "amber"), ("3", "god"), ("4", "violet"), ("5", "sem")):
            assert f"--serie-{serie}: var(--{teinte});" in css
        assert "--serie-autres: var(--txt3);" in css and "--serie-cache: var(--brand-soft-strong);" in css

    def test_us311_ca10_le_seuil_de_page_est_a_600_et_la_navigation_a_900(self):
        config = _lire(ADMIN / "tailwind.config.js")
        assert "tab: '600px'" in config
        assert "nav: '900px'" in _lire(ROOT / "frontend" / "tailwind.config.js")

    def test_us311_ca10_la_navigation_passe_du_bandeau_a_la_barre_basse_a_900_px(self):
        nav = _lire(ADMIN / "src" / "components" / "Navigation.jsx")
        assert "hidden gap-1 nav:flex" in nav          # bandeau : seulement dès 900 px
        assert "nav:hidden" in nav                    # barre basse : seulement en dessous
        assert "Potagers et jardiniers" in _lire(ADMIN / "src" / "lib" / "navigation.js")

    def test_us311_ca10_la_coquille_a_la_barre_d_outils_de_la_maquette(self):
        barre = _lire(ADMIN / "src" / "components" / "BarreOutils.jsx")
        for attendu in ("Période", "Filtres", "Provenance", "Canal", "Modèle", "Rafraîchir", "aria-pressed"):
            assert attendu in barre

    def test_us311_ca10_aucune_page_ne_defile_horizontalement_mais_defile_verticalement(self):
        css = _lire(ADMIN / "src" / "index.css")
        assert "overflow-x: clip" in css
        # `overflow-x: hidden` sur html et body bloquait la molette : la page ne défilait plus.
        regles = re.findall(r"([^{}]+)\{([^{}]*)\}", re.sub(r"/\*.*?\*/", "", css, flags=re.S))
        for selecteur, corps in regles:
            if re.search(r"(^|,)\s*(html|body)\s*(,|$)", selecteur.strip()):
                assert "overflow-x: hidden" not in corps and "overflow: hidden" not in corps, selecteur

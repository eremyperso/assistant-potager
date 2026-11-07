"""
tests/test_us274_retrait_ecritures_sans_confirmation.py — Retirer les chemins d'écriture sans confirmation [US-274]
==================================================================================================================
Règle R2 : il n'existe plus qu'UN chemin d'écriture, la proposition confirmée. Les anciens points d'API qui
écrivaient un geste dès la phrase reçue — `POST /parse`, `POST /voice` (branches ACTION et INTERROGER) — sont
retirés avec `classify_intent_pwa`, `transcribe_audio` et l'ancienne PWA `static/` qui en dépendait.

* CA1 — l'inventaire : aucun écran de `frontend/` ni de `static/` n'appelle ces points d'API ;
* CA2 — les points d'API et les fonctions mortes sont retirés ;
* CA3 — aucune route de l'API n'écrit un événement hors des exécuteurs de proposition ;
* CA4 — les fiches de `data/connaissance/doc_app/` ne citent plus ces chemins.

Gherkin : `POST /parse` répond 404.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.services.context import default_context

RACINE = Path(__file__).resolve().parent.parent
MAIN = RACINE / "app" / "api" / "main.py"
CHEMINS_RETIRES = ("/parse", "/voice")
APPEL_RETIRE = re.compile(r"""['"`]\s*(?:https?://[^'"`/]+)?(?:/api)?/(?:parse|voice)\b(?![-\w])""")


def _fichiers_d_ecran() -> list[Path]:
    """Tout ce qui s'affiche : le front React (sources et page d'entrée) et l'ancienne PWA, si elle existait encore."""
    ecrans: list[Path] = []
    for dossier, extensions in ((RACINE / "frontend" / "src", {".js", ".jsx", ".ts", ".tsx", ".html"}),
                                (RACINE / "static", {".js", ".html", ".json"})):
        if dossier.is_dir():
            ecrans += [p for p in dossier.rglob("*") if p.suffix in extensions and p.is_file()]
    ecrans.append(RACINE / "frontend" / "index.html")
    return [p for p in ecrans if p.is_file()]


@pytest.fixture
def client():
    from app.api.main import app, get_current_user_ctx

    app.dependency_overrides[get_current_user_ctx] = default_context
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_current_user_ctx, None)


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — l'inventaire des appelants
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1Inventaire:

    def test_ca1_aucun_ecran_n_appelle_parse_ni_voice(self):
        ecrans = _fichiers_d_ecran()
        assert ecrans, "l'inventaire ne lit rien : le test ne prouverait rien"
        appelants = [
            f"{p.relative_to(RACINE)}:{i}"
            for p in ecrans
            for i, ligne in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1)
            if APPEL_RETIRE.search(ligne)
        ]
        assert not appelants, f"écrans qui appellent encore un point d'API retiré : {appelants}"

    def test_ca1_l_ancienne_pwa_static_n_existe_plus(self):
        assert not (RACINE / "static").exists()

    def test_ca1_l_inventaire_sait_reconnaitre_un_appel(self):
        assert APPEL_RETIRE.search("const res = await fetch(API + '/voice', { method: 'POST' })")
        assert APPEL_RETIRE.search("post('/parse', { texte })")
        assert APPEL_RETIRE.search('fetch(`/parse`)')
        assert not APPEL_RETIRE.search("setTexte(parseur)") and not APPEL_RETIRE.search("'/voice-notes'")


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — retirés, avec ce qui n'a plus de raison d'être
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2Retrait:

    @pytest.mark.parametrize("chemin", CHEMINS_RETIRES)
    @pytest.mark.parametrize("methode", ["post", "put", "patch", "delete"])
    def test_ca2_les_chemins_retires_repondent_404(self, client, chemin, methode):
        """Gherkin : POST /parse → 404 (et non 405, qui laisserait croire que la route existe)."""
        assert getattr(client, methode)(chemin).status_code == 404

    @pytest.mark.parametrize("chemin", CHEMINS_RETIRES)
    def test_ca2_aucune_route_enregistree_pour_ces_chemins(self, chemin):
        from app.api.main import app

        enregistres = {getattr(r, "path", None) for r in app.routes}
        assert chemin not in enregistres
        assert chemin not in app.openapi()["paths"]

    def test_ca2_une_methode_non_permise_garde_son_405(self, client):
        assert client.delete("/health").status_code == 405

    def test_ca2_les_fonctions_devenues_mortes_sont_retirees(self):
        from llm import groq_client

        assert not hasattr(groq_client, "classify_intent_pwa")
        assert not hasattr(groq_client, "transcribe_audio")
        assert not hasattr(groq_client, "_PWA_CLASSIFY_PROMPT")

    def test_ca2_main_n_importe_plus_ce_qui_servait_a_ces_routes(self):
        source = MAIN.read_text(encoding="utf-8")
        for nom in ("classify_intent_pwa", "transcribe_audio", "parse_commande", "add_to_rag", "_MIME_EXT",
                    "UploadFile", "_STATIC"):
            assert nom not in source, nom

    def test_ca2_l_openapi_versionne_ne_decrit_plus_ces_chemins(self):
        chemin = RACINE / "docs" / "openapi.json"
        if not chemin.exists():
            pytest.skip("openapi.json non versionné")
        import json

        paths = json.loads(chemin.read_text(encoding="utf-8")).get("paths", {})
        assert not set(CHEMINS_RETIRES) & set(paths)


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — un seul chemin d'écriture : les exécuteurs de proposition
# ═════════════════════════════════════════════════════════════════════════════
def _ecrivains_d_evenements() -> set[str]:
    """Les fonctions de service qui écrivent un événement — DÉRIVÉES, jamais listées à la main :
    celles de `evenements.py` qui construisent un `Evenement(…)` ou en suppriment, et `enregistrer_gestes`."""
    arbre = ast.parse((RACINE / "app" / "services" / "evenements.py").read_text(encoding="utf-8"))
    noms: set[str] = {"enregistrer_gestes"}
    for fonction in (n for n in arbre.body if isinstance(n, ast.FunctionDef)):
        for noeud in ast.walk(fonction):
            if isinstance(noeud, ast.Call):
                f = noeud.func
                if isinstance(f, ast.Name) and f.id == "Evenement":
                    noms.add(fonction.name)
                if isinstance(f, ast.Attribute) and f.attr == "delete":
                    noms.add(fonction.name)
    return noms


class TestCA3UnSeulCheminDEcriture:

    def test_ca3_la_derivation_trouve_les_ecrivains_connus(self):
        ecrivains = _ecrivains_d_evenements()
        assert {"creer_evenement_depuis_parse", "creer_evenement_confirme", "corriger_evenement"} & ecrivains
        assert "supprimer_evenement" in ecrivains and "enregistrer_gestes" in ecrivains

    def test_ca3_aucune_route_n_ecrit_un_evenement(self):
        """Aucune fonction de route de `main.py` n'appelle un écrivain d'événements, ni ne construit un
        `Evenement`, ni ne supprime dans la table : l'écriture passe par `echange_pwa` (exécuteurs de
        proposition) et par les services qu'ils appellent."""
        ecrivains = _ecrivains_d_evenements()
        arbre = ast.parse(MAIN.read_text(encoding="utf-8"))
        fautes: list[str] = []
        for fonction in (n for n in arbre.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))):
            est_route = any(isinstance(d, ast.Call) and getattr(d.func, "attr", "") in
                            ("get", "post", "put", "patch", "delete", "api_route") for d in fonction.decorator_list)
            if not est_route:
                continue
            for noeud in ast.walk(fonction):
                if not isinstance(noeud, ast.Call):
                    continue
                f = noeud.func
                nom = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
                if nom in ecrivains or nom == "Evenement":
                    fautes.append(f"{fonction.name} → {nom}")
        assert not fautes, f"routes qui écrivent un événement sans passer par une proposition : {fautes}"

    def test_ca3_le_test_sait_denoncer_une_route_fautive(self, tmp_path, monkeypatch):
        """Le garde-fou n'est pas une formalité : une route qui appellerait `creer_evenement_depuis_parse` serait vue."""
        source = ('@app.post("/mauvaise")\n'
                  'def mauvaise(req):\n'
                  '    svc_evenements.creer_evenement_depuis_parse(db, ctx, {}, "x")\n')
        fautes = []
        ecrivains = _ecrivains_d_evenements()
        for fonction in (n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)):
            for noeud in ast.walk(fonction):
                if isinstance(noeud, ast.Call) and getattr(noeud.func, "attr", "") in ecrivains:
                    fautes.append(fonction.name)
        assert fautes == ["mauvaise"]

    def test_ca3_les_ecritures_de_la_pwa_passent_par_les_executeurs_de_proposition(self):
        """Ce qui reste : `echange_pwa.confirmer` / `_confirmer_commande`, derrière une proposition en base."""
        source = (RACINE / "app" / "services" / "compagnon" / "echange_pwa.py").read_text(encoding="utf-8")
        assert "def confirmer(" in source and "def _confirmer_commande(" in source


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — le corpus ne cite plus ces chemins
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4Corpus:

    def test_ca4_aucune_fiche_doc_app_ne_cite_les_chemins_retires(self):
        motif = re.compile(r"(?<![\w/])(?:POST\s+)?/(?:parse|voice)\b(?![-\w])")
        cites = []
        for fiche in (RACINE / "data" / "connaissance").rglob("*.md"):
            for i, ligne in enumerate(fiche.read_text(encoding="utf-8").splitlines(), 1):
                if motif.search(ligne) and "handle_voice" not in ligne:
                    cites.append(f"{fiche.relative_to(RACINE)}:{i}")
        assert not cites, f"fiches qui citent un chemin retiré : {cites}"

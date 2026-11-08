"""
tests/test_us295_guide_prompts_mcp.py — Guider le modèle et le jardinier sur le canal MCP [US-295]
===================================================================================================
Un bloc par critère d'acceptance (CA1 à CA7) et le scénario Gherkin. Les ressources et les prompts
sont lus par le vrai parcours MCP (jeton OAuth, POST /mcp). Le classement du corpus (CA5) est mesuré
par `test_us099_corpus_fonctionnement.py` ; ici on vérifie que les questions y sont.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

from app.services.mcp import guides as svc_guides
from database.models import Parcelle
from tests.test_us290_serveur_mcp import _connecter, _rpc, client, fabrique, jardin  # noqa: F401
from tests.test_us292_geste_assistant_ia import sessions  # noqa: F401

RACINE = Path(__file__).resolve().parent.parent
FICHE = RACINE / "data" / "connaissance" / "doc_app" / "assistants-ia-mcp.md"
README = RACINE / "data" / "connaissance" / "doc_app" / "README.md"
CORPUS = RACINE / "tests" / "corpus" / "us099_questions_fonctionnement.csv"
GUIDES = (RACINE / "data" / "connaissance" / "guide user" / "guide assistant.md",
          RACINE / "docs" / "MANUEL" / "guide assistant.md")
LIMITE_TELEGRAM = 4096
TITRE_CHAPITRE = "## 18.5 Votre potager dans votre assistant IA"


def _lire(client, jeton, uri):
    reponse = _rpc(client, jeton, "resources/read", {"uri": uri}).json()
    return reponse["result"]["contents"][0]["text"] if "result" in reponse else reponse["error"]


def _chapitre(chemin: Path) -> str:
    texte = chemin.read_text(encoding="utf-8")
    debut = texte.index(TITRE_CHAPITRE)
    return texte[debut:texte.index("\n## ", debut + 5)]


@pytest.fixture
def jeton(client, jardin, sessions):
    return _connecter(client, jardin)["access_token"]


@pytest.fixture
def mesanges(fabrique, jardin):
    with fabrique() as db:
        db.add_all([Parcelle(nom="Sud", nom_normalise="sud", potager_id=jardin["mesanges"], actif=True, nb_rangs=2),
                    Parcelle(nom="Nord", nom_normalise="nord", potager_id=jardin["mesanges"], actif=True)])
        db.commit()


# ── CA1 : le guide, pour le modèle ───────────────────────────────────────────
class TestCA1Guide:
    def test_us295_la_ressource_est_listee_et_lisible(self, client, jeton):
        noms = {r["name"] for r in _rpc(client, jeton, "resources/list").json()["result"]["resources"]}
        assert {"guide-du-potager", "resume-du-potager"} <= noms
        assert _lire(client, jeton, svc_guides.URI_GUIDE) == svc_guides.GUIDE_DU_POTAGER

    @pytest.mark.parametrize("attendu", [
        "semis", "mise_en_godet", "plantation", "recolte", "perte", "observation",   # le vocabulaire des gestes
        "Végétatif", "Reproducteur", "rendement cumulé",                              # végétatif / reproducteur
        "AAAA-MM-JJ",                                                                 # dates ISO
        "Ne jamais inventer", "demande",                                              # ne pas inventer une parcelle
        "récapitulatif", "confirmer_proposition",                                     # présenter avant de confirmer
        "dans l'application", "ouvrir_dans_l_application",                            # une destruction
        "chercher_connaissance", "cite la source",                                    # le jardinage
    ])
    def test_us295_le_guide_dit(self, attendu):
        assert attendu in svc_guides.GUIDE_DU_POTAGER

    def test_us295_les_outils_cites_existent(self):
        from app.services.mcp.serveur import REGISTRE

        cites = {o for o in re.findall(r"`([a-z_]+)`", svc_guides.GUIDE_DU_POTAGER) if "_" in o}
        assert {"confirmer_proposition", "chercher_connaissance", "ouvrir_dans_l_application"} <= cites
        for outil in cites - {"mise_en_godet"}:
            assert outil in REGISTRE, outil


# ── CA2 : le résumé, en une page ─────────────────────────────────────────────
class TestCA2Resume:
    def test_us295_parcelles_cultures_zone(self, client, jeton, mesanges):
        texte = _lire(client, jeton, svc_guides.URI_RESUME)
        assert "Les Mésanges" in texte and "Zone climatique" in texte
        assert "## Parcelles (2)" in texte and "Sud, 2 rang(s)" in texte and "- Nord" in texte
        assert "## Lots de pépinière en cours (0)" in texte and "Aucun lot en cours." in texte
        assert len(texte.splitlines()) < 40  # une page

    def test_us295_un_potager_nomme(self, client, jardin, sessions, mesanges):
        jeton = _connecter(client, jardin, potagers=[jardin["mesanges"], jardin["verger"]])["access_token"]
        assert "Le Verger" in _lire(client, jeton, f"{svc_guides.URI_RESUME}/Le Verger")
        assert "Les Mésanges" in _lire(client, jeton, f"{svc_guides.URI_RESUME}/{jardin['mesanges']}")

    def test_us295_un_potager_non_consenti_est_refuse(self, client, jeton):
        assert _lire(client, jeton, f"{svc_guides.URI_RESUME}/Le Verger")["code"] == -32002

    def test_us295_ressource_inconnue(self, client, jeton):
        assert _lire(client, jeton, "potager://secret")["code"] == -32002

    def test_us295_modele_de_ressource(self, client, jeton):
        modeles = _rpc(client, jeton, "resources/templates/list").json()["result"]["resourceTemplates"]
        assert modeles[0]["uriTemplate"].endswith("/{potager}")


class TestCA2Lignes:
    """Le résumé dit chaque culture et chaque lot sur une ligne, sans jamais planter sur un champ absent."""

    def test_us295_ligne_de_culture(self):
        assert svc_guides._ligne_culture({"culture": "tomate", "variete": "Cœur de bœuf", "nb_plants": 12.0,
                                          "unite": "plants"}) == "tomate (Cœur de bœuf) — 12 plants"
        assert svc_guides._ligne_culture({"culture": "fève", "nb_plants": "37"}) == "fève — 37"
        assert svc_guides._ligne_culture({}) == "?"

    def test_us295_ligne_de_lot(self):
        assert svc_guides._ligne_lot({"numero": 14, "culture": "tomate", "variete": "Roma",
                                      "action_suggeree": "à endurcir"}) == "lot 14 tomate (Roma) — à endurcir"
        assert svc_guides._ligne_lot({"lot": 3, "culture": "poireau", "action_suggeree": {"libelle": "à repiquer"}}) \
            == "lot 3 poireau — à repiquer"
        assert svc_guides._ligne_lot({}) == "lot ?"

    def test_us295_le_resume_liste_au_plus_quinze_lots(self, monkeypatch):
        from app.services.mcp import lectures

        lots = [{"numero": i, "culture": "tomate"} for i in range(20)]
        monkeypatch.setattr(svc_guides, "_voir", lambda f, db, c, ctx: (
            {"lots": lots} if f is lectures._voir_pepiniere else {"parcelles": [
                {"nom": "Sud", "nb_rangs": 3, "cultures": [{"culture": "fève", "nb_plants": 4, "unite": "plants"}]}]}))
        ctx = type("Ctx", (), {"user_id": 1, "potager_id": 1})()
        db = type("Db", (), {"get": lambda self, modele, ident: None})()
        monkeypatch.setattr(svc_guides.svc_potager_actif, "obtenir_potager", lambda *a: {"nom": "Test"})
        texte = svc_guides.resume_du_potager(db, None, ctx)
        assert "- Sud, 3 rang(s) : fève — 4 plants" in texte
        assert "## Lots de pépinière en cours (20)" in texte and "et 5 autre(s)" in texte
        assert texte.count("- lot ") == 15


# ── CA3 : quatre prompts ─────────────────────────────────────────────────────
class TestCA3Prompts:
    TITRES = ["Bilan de la semaine", "Que semer ce mois-ci ?", "Préparer ma sortie au jardin",
              "Bilan de saison d'une culture"]

    def test_us295_quatre_prompts(self, client, jeton):
        prompts = _rpc(client, jeton, "prompts/list").json()["result"]["prompts"]
        assert [p["title"] for p in prompts] == self.TITRES

    def test_us295_chaque_prompt_lit_les_outils_et_n_ecrit_rien(self, client, jeton):
        from app.services.mcp.serveur import REGISTRE

        for nom in [p["name"] for p in _rpc(client, jeton, "prompts/list").json()["result"]["prompts"]]:
            arguments = {"culture": "tomate"} if nom.startswith("bilan-de-saison") else {}
            texte = _rpc(client, jeton, "prompts/get", {"name": nom, "arguments": arguments}).json()["result"][
                "messages"][0]["content"]["text"]
            assert "N'enregistre rien" in texte or "Ne propose aucun" in texte, nom
            outils = re.findall(r"\b((?:voir|consulter|chercher)_[a-z_]+)\b", texte)
            assert outils, nom
            for outil in outils:
                assert outil in REGISTRE, (nom, outil)

    def test_us295_le_bilan_de_saison_prend_sa_culture(self, client, jeton):
        corps = _rpc(client, jeton, "prompts/get", {"name": "bilan-de-saison-d-une-culture", "arguments": {"culture": "fève"}})
        assert "« fève »" in corps.json()["result"]["messages"][0]["content"]["text"]
        manque = _rpc(client, jeton, "prompts/get", {"name": "bilan-de-saison-d-une-culture"}).json()
        assert manque["error"]["code"] == -32602

    def test_us295_prompt_inconnu(self, client, jeton):
        assert _rpc(client, jeton, "prompts/get", {"name": "n-importe-quoi"}).json()["error"]["code"] == -32602

    def test_us295_les_capacites_sont_annoncees(self, client, jeton):
        capacites = _rpc(client, jeton, "initialize", {"protocolVersion": "2025-06-18"}).json()["result"]["capabilities"]
        assert set(capacites) == {"tools", "resources", "prompts"}


# ── CA4 : la fiche de documentation ──────────────────────────────────────────
class TestCA4Fiche:
    def test_us295_la_fiche_dit_tout_ce_qu_il_faut(self):
        texte = FICHE.read_text(encoding="utf-8")
        for attendu in ("Claude", "ChatGPT", "Le Chat", "Connecteurs", "aucune destruction", "lien vers l'application",
                        "Aucune initiative", "Pas de photo", "qualité dépend", "partent chez l'éditeur", "Révoquer"):
            assert attendu in texte, attendu

    def test_us295_la_fiche_est_referencee_dans_le_readme(self):
        assert "assistants-ia-mcp.md" in README.read_text(encoding="utf-8")

    def test_us295_chaque_section_porte_une_ligne_on_parle_aussi_de(self):
        sections = re.split(r"^## ", FICHE.read_text(encoding="utf-8"), flags=re.M)[1:]
        assert len(sections) == 6 and all("**On parle aussi de :**" in s for s in sections)


# ── CA5 : le compagnon répond juste ──────────────────────────────────────────
class TestCA5Compagnon:
    def _questions(self):
        with CORPUS.open(encoding="utf-8", newline="") as f:
            return {ligne["question"]: ligne["fragment_attendu"] for ligne in csv.DictReader(f)}

    def test_us295_les_deux_questions_de_l_us_sont_au_corpus(self):
        questions = self._questions()
        assert questions["je peux utiliser Claude avec mon potager ?"].startswith("assistants-ia-mcp.md#")
        assert questions["pourquoi ChatGPT ne peut pas supprimer ma parcelle ?"].startswith("assistants-ia-mcp.md#")

    def test_us295_chaque_section_a_au_moins_une_question(self):
        cibles = {c.split("#", 1)[1].split("-")[0] for c in self._questions().values()
                  if c.startswith("assistants-ia-mcp.md#")}
        assert cibles == {"00", "01", "02", "03", "04", "05"}


# ── CA6 : le guide utilisateur ───────────────────────────────────────────────
class TestCA6GuideUtilisateur:
    @pytest.mark.parametrize("chemin", GUIDES, ids=["data", "docs"])
    def test_us295_le_chapitre_existe_sous_la_limite_telegram(self, chemin):
        assert 500 < len(_chapitre(chemin)) < LIMITE_TELEGRAM

    def test_us295_les_deux_copies_portent_le_meme_chapitre(self):
        assert _chapitre(GUIDES[0]) == _chapitre(GUIDES[1])


# ── Scénario Gherkin ─────────────────────────────────────────────────────────
def test_us295_gherkin(client, jeton, mesanges):
    """Le Chat connecté : « Préparer ma sortie au jardin » lit échéances et météo, sans rien enregistrer."""
    prompt = _rpc(client, jeton, "prompts/get", {"name": "preparer-ma-sortie-au-jardin"}).json()["result"]
    texte = prompt["messages"][0]["content"]["text"]
    assert "voir_echeances" in texte and "voir_meteo" in texte and "N'enregistre rien" in texte
    assert "liste priorisée" in texte
    # … et la fiche répond à « pourquoi Le Chat ne peut pas supprimer ma parcelle ? » : confirmation au bouton.
    fiche = FICHE.read_text(encoding="utf-8")
    assert "se **confirme au bouton**" in fiche and "Le Chat" in fiche

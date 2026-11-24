"""
tests/test_us338_registre_capacites.py — Le registre de capacités en couche neutre [US-338]
==========================================================================================
Le registre et ses capacités vivent dans `app/services/capacites/` ; le serveur MCP n'en est qu'un adaptateur.
Le compagnon de l'application peut lister et appeler les mêmes capacités pour un jardinier et un potager donnés,
sans jeton ni JSON-RPC (CA1) ; le contrat MCP est inchangé (CA2 : les tests d'US-290 à US-297 restent verts) ;
le serveur n'ajoute qu'authentification, quotas, portée et journal (CA3) ; un test de parité compare les deux
clients (CA4) ; la règle d'écriture d'une capacité est documentée (CA5) ; le compagnon actuel ne l'utilise pas (CA6).

Aucun appel réseau, aucun modèle : TestClient sur la base SQLite des tests d'US-290.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.services import potager_actif as svc_potager_actif
from app.services.capacites import registre
from app.services.compagnon.actions_menees import canal_courant
from app.services.mcp import serveur as svc_serveur
from database.db import current_potager_id
from database.models import McpAppel, Parcelle
from tests.test_us290_serveur_mcp import (  # noqa: F401 — fixtures et aides partagées
    _appeler, _connecter, _rpc, client, fabrique, jardin,
)

RACINE = Path(__file__).resolve().parents[1]
DOSSIER_EPIC = RACINE / "docs" / "EPIC 20 - COMPAGNON CLIENT DES CAPACITES"


def _ctx(fabrique, user_id: int, potager_id: int):
    with fabrique() as db:
        return svc_potager_actif.contexte_sur_potager(db, user_id, potager_id)


@pytest.fixture
def capacite_factice():
    """Une capacité d'écriture factice : elle note le potager du GUC et le canal qu'elle a vus."""
    vus: list[dict] = []

    def executer(db, appel):
        vus.append({"potager_id": appel.ctx.potager_id, "guc": current_potager_id.get(),
                    "canal": canal_courant.get(), "client": appel.appelant.client})
        return {"propose": True}

    registre.enregistrer_capacite(registre.Capacite(
        nom="proposer_factice_338", titre="Proposer (test)", description="Écriture factice.",
        executer=executer, ecriture=True, idempotent=False, proprietes={"note": {"type": "string"}},
    ))
    yield vus
    registre.REGISTRE.pop("proposer_factice_338", None)


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — Une couche indépendante du serveur MCP, appelable par le compagnon
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1CoucheNeutre:

    def test_us338_le_registre_ne_connait_ni_le_protocole_ni_le_jeton(self):
        for fichier in sorted((RACINE / "app/services/capacites").glob("*.py")):
            source = fichier.read_text(encoding="utf-8")
            assert not re.search(r"^\s*(from|import) app\.services\.mcp", source, re.MULTILINE), fichier.name
            assert not re.search(r"\b(McpAppel|McpJeton|verifier_quota|traiter_message|ErreurProtocole)\b", source), \
                fichier.name

    def test_us338_le_compagnon_liste_toutes_les_capacites(self):
        noms = {c.nom for c in registre.lister()}
        assert {"lister_potagers", "voir_plan", "voir_echeances", "proposer_geste", "confirmer_proposition",
                "proposer_commande"} <= noms
        assert {c.nom for c in registre.lister(ecriture=False)} == {c.nom for c in registre.lister() if not c.ecriture}

    def test_us338_le_compagnon_appelle_une_capacite_pour_un_potager(self, client, fabrique, jardin):
        ctx = _ctx(fabrique, jardin["user_id"], jardin["mesanges"])
        with fabrique() as db:
            donnees = registre.appeler(db, ctx, "lister_potagers")
        assert [p["nom"] for p in donnees["potagers"]] == ["Les Mésanges"]
        assert donnees["potagers"][0]["ecriture_possible"] is True

    def test_us338_l_appel_tourne_sous_le_potager_du_jardinier(self, fabrique, jardin, capacite_factice):
        ctx = _ctx(fabrique, jardin["user_id"], jardin["mesanges"])
        with fabrique() as db:
            assert registre.appeler(db, ctx, "proposer_factice_338", {"note": "x"}) == {"propose": True}
        assert capacite_factice == [{"potager_id": jardin["mesanges"], "guc": jardin["mesanges"],
                                     "canal": canal_courant.get(), "client": registre.CLIENT_COMPAGNON}]

    def test_us338_memes_gardes_que_le_mcp(self, fabrique, jardin, capacite_factice):
        mesanges = _ctx(fabrique, jardin["user_id"], jardin["mesanges"])
        verger = _ctx(fabrique, jardin["user_id"], jardin["verger"])  # lectrice
        with fabrique() as db:
            with pytest.raises(registre.RefusCapacite, match="inconnue"):
                registre.appeler(db, mesanges, "supprimer_tout")
            with pytest.raises(registre.RefusCapacite, match="Argument inconnu"):
                registre.appeler(db, mesanges, "proposer_factice_338", {"pirate": 1})
            with pytest.raises(registre.RefusCapacite, match=registre.REFUS_LECTEUR):
                registre.appeler(db, verger, "proposer_factice_338")
        assert capacite_factice == []

    def test_us338_arguments_qui_ne_sont_pas_un_objet(self, fabrique, jardin):
        ctx = _ctx(fabrique, jardin["user_id"], jardin["mesanges"])
        with fabrique() as db, pytest.raises(registre.RefusCapacite, match="objet JSON"):
            registre.appeler(db, ctx, "voir_plan", ["planche"])

    def test_us338_une_capacite_en_erreur_ne_valide_rien(self, fabrique, jardin):
        """❌ Une capacité qui lève : l'erreur remonte au compagnon, la transaction est annulée."""
        def casse(db, appel):
            db.add(Parcelle(nom="fantome", nom_normalise="fantome", potager_id=appel.ctx.potager_id))
            db.flush()
            raise RuntimeError("panne")

        registre.enregistrer_capacite(registre.Capacite(nom="casse_338", titre="x", description="x", executer=casse))
        try:
            ctx = _ctx(fabrique, jardin["user_id"], jardin["mesanges"])
            with fabrique() as db:
                with pytest.raises(RuntimeError, match="panne"):
                    registre.appeler(db, ctx, "casse_338")
                assert db.query(Parcelle).filter(Parcelle.nom == "fantome").count() == 0
        finally:
            registre.REGISTRE.pop("casse_338", None)

    def test_us338_aucune_capacite_destructrice(self):
        with pytest.raises(ValueError):
            registre.enregistrer_capacite(registre.Capacite(
                nom="supprimer_x_338", titre="x", description="x", executer=lambda db, a: None, destructeur=True))
        assert "supprimer_x_338" not in registre.REGISTRE


# ═════════════════════════════════════════════════════════════════════════════
# CA2 + Gherkin — Même réponse par les deux clients
# ═════════════════════════════════════════════════════════════════════════════
def test_us338_gherkin_claude_et_le_compagnon_lisent_le_meme_plan(client, fabrique, jardin):
    with fabrique() as db:
        db.add(Parcelle(nom="planche légumes", nom_normalise="planche legumes", potager_id=jardin["mesanges"],
                         superficie_m2=20))
        db.commit()
    jeton = _connecter(client, jardin)["access_token"]
    par_mcp = _appeler(client, jeton, "voir_plan")
    assert par_mcp.get("isError") is not True, par_mcp
    ctx = _ctx(fabrique, jardin["user_id"], jardin["mesanges"])
    with fabrique() as db:
        par_compagnon = registre.appeler(db, ctx, "voir_plan")
    assert par_compagnon == par_mcp["structuredContent"]
    assert "planche légumes" in str(par_compagnon)


def test_us338_le_compagnon_n_ecrit_rien_au_journal_mcp(client, fabrique, jardin):
    ctx = _ctx(fabrique, jardin["user_id"], jardin["mesanges"])
    with fabrique() as db:
        registre.appeler(db, ctx, "lister_potagers")
        assert db.query(McpAppel).count() == 0


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — Le serveur MCP n'est qu'un adaptateur
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3Adaptateur:

    def test_us338_un_seul_registre(self):
        assert svc_serveur.REGISTRE is registre.REGISTRE
        assert svc_serveur.Outil is registre.Capacite and svc_serveur.RefusOutil is registre.RefusCapacite

    def test_us338_les_anciens_modules_sont_les_memes(self):
        from app.services import capacites
        from app.services.mcp import commandes, ecritures, lectures

        assert lectures is capacites.lectures and ecritures is capacites.ecritures
        assert commandes is capacites.commandes

    def test_us338_le_serveur_ne_definit_plus_ni_capacite_ni_execution(self):
        source = (RACINE / "app/services/mcp/serveur.py").read_text(encoding="utf-8")
        assert "REGISTRE: dict" not in source and "class Outil" not in source
        assert "tenant_scope(" not in source and "outil.executer(" not in source
        for garde in ("verifier_quota", "REFUS_PORTEE", "resoudre_potager", "_journaliser"):
            assert garde in source, garde


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — Parité : les deux clients voient les mêmes capacités, avec les mêmes descriptions
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4Parite:

    @staticmethod
    def _vu_par_le_compagnon(ecriture: bool) -> dict:
        return {c.nom: (c.description, c.schema_entree()) for c in registre.lister(ecriture=ecriture)}

    @staticmethod
    def _vu_par_le_mcp(client, jeton: str) -> dict:
        outils = _rpc(client, jeton, "tools/list").json()["result"]["tools"]
        return {o["name"]: (o["description"], o["inputSchema"]) for o in outils}

    def test_us338_parite_en_ecriture(self, client, jardin):
        jeton = _connecter(client, jardin, ecriture=True)["access_token"]
        assert self._vu_par_le_mcp(client, jeton) == self._vu_par_le_compagnon(ecriture=True)

    def test_us338_parite_en_lecture(self, client, jardin):
        jeton = _connecter(client, jardin)["access_token"]
        assert self._vu_par_le_mcp(client, jeton) == self._vu_par_le_compagnon(ecriture=False)


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — La règle d'écriture d'une capacité est documentée
# ═════════════════════════════════════════════════════════════════════════════
def test_us338_regle_d_une_capacite_documentee():
    doc = (DOSSIER_EPIC / "07_REGLE_D_UNE_CAPACITE.md").read_text(encoding="utf-8")
    for regle in ("R1", "R2", "R3", "R4", "R5"):
        assert f"| {regle} |" in doc, regle
    assert "verdict" in doc and "avertissement_donnees" in doc
    assert "07_REGLE_D_UNE_CAPACITE.md" in (DOSSIER_EPIC / "README.md").read_text(encoding="utf-8")


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — Le compagnon actuel n'utilise pas encore le registre
# ═════════════════════════════════════════════════════════════════════════════
def test_us338_le_compagnon_actuel_n_appelle_pas_le_registre():
    # [US-342] Seule la boucle à capacités (derrière COMPAGNON_MOTEUR=capacites) est cliente du registre ;
    # l'ancien moteur (agent, bot, reste du compagnon) ne l'appelle toujours pas.
    boucle = RACINE / "app/services/compagnon/boucle.py"
    assert "services.capacites" in boucle.read_text(encoding="utf-8")
    for dossier in ("app/services/agent", "app/services/compagnon", "app/bot"):
        for fichier in (RACINE / dossier).rglob("*.py"):
            if fichier == boucle:
                continue
            assert "services.capacites" not in fichier.read_text(encoding="utf-8"), fichier
    assert "services.capacites" not in (RACINE / "app/services/interpreteur_commandes.py").read_text(encoding="utf-8")

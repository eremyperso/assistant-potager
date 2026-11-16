"""
tests/test_us306_provenance_appels.py — US-306 : marquer la provenance de chaque appel au modèle

`conso_tokens.provenance` : usage | mesure | test | fond | historique. Portée par un
contexte (`llm/contexte_appel.py`), lue par la passerelle à l'écriture, jamais passée
en paramètre par un appelant métier.

Aucun appel réseau : le client du fournisseur est simulé.
"""
from __future__ import annotations

import ast
import contextvars
import inspect
import pathlib
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.services.context import TenantContext
from database.models import ConsoTokens
from llm import contexte_appel, passerelle
from llm.contexte_appel import (
    PROVENANCE_FOND,
    PROVENANCE_HISTORIQUE,
    PROVENANCE_MESURE,
    PROVENANCE_TEST,
    PROVENANCE_USAGE,
    ProvenanceInvalideError,
)

RACINE = pathlib.Path(__file__).resolve().parent.parent
CTX_JARDINIER = TenantContext(user_id=7, potager_id=3, role="owner")
CTX_FOND = TenantContext(user_id=None, potager_id=3)


# ─────────────────────────────────────────────────────────────────────────────
# Outillage
# ─────────────────────────────────────────────────────────────────────────────
def _reponse(contenu: str = "ok", tokens_in: int = 100, tokens_out: int = 20):
    """Réponse chat réaliste mais NON factice (`SimpleNamespace`, pas `unittest.mock`)."""
    usage = SimpleNamespace(
        prompt_tokens=tokens_in, completion_tokens=tokens_out,
        prompt_tokens_details=SimpleNamespace(cached_tokens=0),
    )
    message = SimpleNamespace(content=contenu, tool_calls=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)


@pytest.fixture(autouse=True)
def _hors_mode_test(monkeypatch):
    """`conftest.py` pose APP_ENV=test sur SQLite : le mode test serait actif et
    écraserait « usage » / « fond ». Ces tests le désactivent, sauf là où ils le veulent."""
    monkeypatch.setattr(contexte_appel, "_en_mode_test", lambda: False)


@pytest.fixture(autouse=True)
def _modele_sans_reseau(monkeypatch):
    """Le modèle du type d'appel vient de `.env.{APP_ENV}` (Mistral en dev) : on le fixe
    sur un modèle Groq pour que le client simulé `llm.passerelle._client` serve toujours."""
    monkeypatch.setattr(passerelle, "modele_pour", lambda appel_type: "modele-de-test")


@pytest.fixture
def conso(test_db):
    """Redirige l'écriture de `conso_tokens` vers la base de test."""
    with patch("llm.passerelle.SessionLocal", lambda: test_db):
        yield test_db


@pytest.fixture
def client():
    faux = MagicMock()
    faux.chat.completions.create.return_value = _reponse()
    with patch("llm.passerelle._client", faux):
        yield faux


def _appel(ctx: TenantContext = CTX_JARDINIER, appel_type: str = passerelle.TYPE_QUESTION):
    return passerelle.appeler_chat(appel_type=appel_type, ctx=ctx, prompt_fixe="Tu es un assistant.")


def _provenances(db) -> list[str]:
    return [l.provenance for l in db.query(ConsoTokens).order_by(ConsoTokens.id).all()]


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — colonne, contrainte, migration, rollback, historique
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1Colonne:

    def test_us306_ca1_migration_et_rollback_existent(self):
        migration = (RACINE / "migrations" / "migration_v73.sql").read_text(encoding="utf-8")
        assert "ADD COLUMN IF NOT EXISTS provenance" in migration
        assert "NOT NULL DEFAULT 'historique'" in migration  # les lignes existantes → historique
        assert "usage" in migration and "mesure" in migration and "test" in migration and "fond" in migration
        rollback = (RACINE / "migrations" / "rollback_v73.sql").read_text(encoding="utf-8")
        assert "DROP COLUMN IF EXISTS provenance" in rollback

    def test_us306_ca1_colonne_non_nulle_et_defaut_historique(self, test_db):
        test_db.add(ConsoTokens(potager_id=1, date=__import__("datetime").date.today(),
                                appel_type="question", modele="m"))
        test_db.commit()
        assert test_db.query(ConsoTokens).one().provenance == PROVENANCE_HISTORIQUE

    def test_us306_ca1_contrainte_de_valeurs(self, test_db):
        test_db.add(ConsoTokens(potager_id=1, date=__import__("datetime").date.today(),
                                appel_type="question", modele="m", provenance="inconnue"))
        with pytest.raises(IntegrityError):
            test_db.commit()
        test_db.rollback()

    def test_us306_ca1_les_cinq_valeurs_sont_celles_de_la_contrainte(self):
        contrainte = next(c for c in ConsoTokens.__table__.constraints
                          if getattr(c, "name", "") == "ck_conso_tokens_provenance")
        for valeur in contexte_appel.PROVENANCES:
            assert f"'{valeur}'" in str(contrainte.sqltext)

    def test_us306_ca1_aucun_code_ne_peut_ecrire_historique(self):
        with pytest.raises(ProvenanceInvalideError):
            contexte_appel.fixer_provenance(PROVENANCE_HISTORIQUE)


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — portée par le contexte, lue par la passerelle, jamais en paramètre
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2Contexte:

    def test_us306_ca2_la_passerelle_lit_la_provenance_du_contexte(self, conso, client):
        with contexte_appel.provenance(PROVENANCE_MESURE):
            _appel()
        assert _provenances(conso) == [PROVENANCE_MESURE]

    def test_us306_ca2_le_contexte_est_restitue_en_sortie_de_bloc(self, conso, client):
        with contexte_appel.provenance(PROVENANCE_MESURE):
            pass
        assert contexte_appel.provenance_fixee() is None
        _appel()
        assert _provenances(conso) == [PROVENANCE_USAGE]

    def test_us306_ca2_valeur_invalide_refusee(self):
        with pytest.raises(ProvenanceInvalideError):
            contexte_appel.fixer_provenance("benchmark")

    @pytest.mark.parametrize("fonction", [
        passerelle.appeler_chat, passerelle.appeler_chat_outils, passerelle.transcrire,
        passerelle.dicter, passerelle.synthetiser,
    ])
    def test_us306_ca2_aucune_signature_ne_porte_la_provenance(self, fonction):
        assert "provenance" not in inspect.signature(fonction).parameters

    def test_us306_ca2_la_provenance_suit_la_tache_asyncio(self):
        """Deux traitements concurrents ne se voient pas : c'est une ContextVar."""
        import asyncio

        async def traitement(valeur: str) -> str:
            contexte_appel.fixer_provenance(valeur)
            await asyncio.sleep(0)
            return contexte_appel.provenance_fixee()

        async def les_deux():
            return await asyncio.gather(traitement(PROVENANCE_MESURE), traitement(PROVENANCE_TEST))

        assert asyncio.run(les_deux()) == [PROVENANCE_MESURE, PROVENANCE_TEST]
        assert contexte_appel.provenance_fixee() is None


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — défauts : bot / API = usage ; sans utilisateur = fond
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3Defauts:

    def test_us306_ca3_appel_d_un_jardinier_est_usage(self, conso, client):
        _appel(CTX_JARDINIER)
        assert _provenances(conso) == [PROVENANCE_USAGE]

    def test_us306_ca3_appel_sans_utilisateur_est_fond(self, conso, client):
        _appel(CTX_FOND)
        assert _provenances(conso) == [PROVENANCE_FOND]

    def test_us306_ca3_signal_du_compagnon_est_fond_meme_avec_un_utilisateur(self, conso, client):
        _appel(CTX_JARDINIER, appel_type=passerelle.TYPE_COMPAGNON_SIGNAL)
        assert _provenances(conso) == [PROVENANCE_FOND]

    def test_us306_ca3_un_echec_porte_aussi_la_provenance(self, conso):
        import groq
        import httpx
        requete = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
        erreur = groq.InternalServerError("panne", response=httpx.Response(503, request=requete), body=None)
        faux = MagicMock()
        faux.chat.completions.create.side_effect = erreur
        with patch("llm.passerelle._client", faux), patch("llm.passerelle.time.sleep"), \
                pytest.raises(passerelle.LLMIndisponibleError):
            with contexte_appel.provenance(PROVENANCE_MESURE):
                _appel()
        assert _provenances(conso) == [PROVENANCE_MESURE]


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — les outils de tools/ qui appellent un modèle écrivent « mesure »
# ═════════════════════════════════════════════════════════════════════════════
OUTILS_DE_MESURE = (
    "evaluer_agent", "evaluer_dialogues", "evaluer_interpreteur_agent",
    "mesurer_redaction_signaux", "mesurer_corpus_savoir", "rejeu_corpus",
)


def _fixe_mesure(chemin: pathlib.Path) -> bool:
    """Le `main()` de l'outil fixe la provenance « mesure »."""
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    principal = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    for noeud in ast.walk(principal):
        if not isinstance(noeud, ast.Call):
            continue
        nom = getattr(noeud.func, "attr", "")
        if nom == "demarrer_outil":  # [US-307] fixe « mesure », le canal « outil » et l'échange
            return True
        if nom == "fixer_provenance":
            return any(getattr(a, "attr", "") == "PROVENANCE_MESURE" for a in noeud.args)
    return False


class TestCA4Outils:

    @pytest.mark.parametrize("nom", OUTILS_DE_MESURE)
    def test_us306_ca4_l_outil_fixe_mesure_dans_main(self, nom):
        assert _fixe_mesure(RACINE / "tools" / f"{nom}.py"), f"tools/{nom}.py ne fixe pas « mesure »"

    def test_us306_ca4_la_liste_du_cadrage_est_couverte_par_l_audit(self):
        import tools.audit_appels_llm as audit
        detectes = {n[:-3] for n in audit.outils_appelant_un_modele()}
        assert set(OUTILS_DE_MESURE) <= detectes

    def test_us306_ca4_main_d_un_outil_pose_mesure_sans_fuite(self):
        """Exécute réellement le début de `main()` (--dry-run : aucun appel de modèle)."""
        from tools import rejeu_corpus

        def lancer():
            with patch("sys.argv", ["rejeu_corpus", "--corpus", "action", "--fichier", "inexistant.csv"]):
                try:
                    rejeu_corpus.main()
                except (SystemExit, Exception):  # noqa: BLE001 — seul l'effet sur le contexte compte
                    pass
            return contexte_appel.provenance_fixee()

        assert contextvars.copy_context().run(lancer) == PROVENANCE_MESURE
        assert contexte_appel.provenance_fixee() is None


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — harnais conversationnel et mode test = « test »
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5Test:

    def test_us306_ca5_mode_test_actif_ecrit_test(self, conso, client, monkeypatch):
        monkeypatch.setattr(contexte_appel, "_en_mode_test", lambda: True)
        _appel()
        assert _provenances(conso) == [PROVENANCE_TEST]

    def test_us306_ca5_une_provenance_explicite_l_emporte_sur_le_mode_test(self, conso, client, monkeypatch):
        monkeypatch.setattr(contexte_appel, "_en_mode_test", lambda: True)
        with contexte_appel.provenance(PROVENANCE_MESURE):
            _appel()
        assert _provenances(conso) == [PROVENANCE_MESURE]

    def test_us306_ca5_le_mode_test_se_lit_sur_mode_test_actif(self, monkeypatch):
        from app.services import mode_test
        monkeypatch.undo()  # retire le faux `_en_mode_test` de la fixture autouse
        monkeypatch.setattr(mode_test, "actif", lambda: True)
        assert contexte_appel._en_mode_test() is True
        monkeypatch.setattr(mode_test, "actif", lambda: False)
        assert contexte_appel._en_mode_test() is False

    def test_us306_ca5_le_harnais_fixe_test(self):
        import tests_conv.__main__ as cli

        def lancer():
            try:
                cli.main(["validate"])
            except SystemExit:
                pass
            return contexte_appel.provenance_fixee()

        assert contextvars.copy_context().run(lancer) == PROVENANCE_TEST


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — un modèle simulé n'écrit rien hors d'une base de session de test
# ═════════════════════════════════════════════════════════════════════════════
class TestCA6ModeleSimule:

    def test_us306_ca6_reponse_factice_hors_base_de_test_ecrit_zero_ligne(self, conso):
        factice = MagicMock()
        factice.chat.completions.create.return_value = MagicMock()  # réponse `unittest.mock`
        with patch("llm.passerelle._client", factice), \
                patch("llm.passerelle._base_de_session_de_test", return_value=False):
            _appel()
        assert conso.query(ConsoTokens).count() == 0

    def test_us306_ca6_meme_appel_sur_base_de_test_ecrit_la_ligne(self, conso):
        factice = MagicMock()
        factice.chat.completions.create.return_value = MagicMock()
        with patch("llm.passerelle._client", factice):  # `test_db` est SQLite : base de test
            _appel()
        assert conso.query(ConsoTokens).count() == 1

    def test_us306_ca6_simulation_declaree_par_un_outil(self, conso, client):
        with contexte_appel.modele_simule(), \
                patch("llm.passerelle._base_de_session_de_test", return_value=False):
            _appel()
        assert conso.query(ConsoTokens).count() == 0

    def test_us306_ca6_un_vrai_appel_hors_base_de_test_est_ecrit(self, conso, client):
        """Garde-fou inverse : le filtre ne doit pas avaler les appels réels."""
        with patch("llm.passerelle._base_de_session_de_test", return_value=False):
            _appel()  # réponse non factice
        assert conso.query(ConsoTokens).count() == 1

    def test_us306_ca6_le_drapeau_ne_fuit_pas_sur_l_appel_suivant(self, conso):
        factice = MagicMock()
        factice.chat.completions.create.return_value = MagicMock()
        with patch("llm.passerelle._client", factice), \
                patch("llm.passerelle._base_de_session_de_test", return_value=False):
            _appel()
        reel = MagicMock()
        reel.chat.completions.create.return_value = _reponse()
        with patch("llm.passerelle._client", reel), \
                patch("llm.passerelle._base_de_session_de_test", return_value=False):
            _appel()
        assert conso.query(ConsoTokens).count() == 1

    @pytest.mark.parametrize("url,attendu", [
        ("sqlite://", True), ("postgresql://u:p@h/potager_test", True),
        ("postgresql://u:p@h/potager", False), ("postgresql://u:p@h/potager_dev", False),
    ])
    def test_us306_ca6_definition_de_la_base_de_test(self, url, attendu):
        from app.services.mode_test import base_de_test
        assert base_de_test(url) is attendu


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — aucun point d'entrée de tools/ n'appelle un modèle sans fixer la provenance
# ═════════════════════════════════════════════════════════════════════════════
class TestCA7Audit:

    def test_us306_ca7_aucun_outil_n_appelle_un_modele_sans_provenance(self):
        import tools.audit_appels_llm as audit
        manquants = audit.outils_sans_provenance()
        assert manquants == [], f"outils sans provenance fixée : {manquants}"

    def test_us306_ca7_le_controle_detecte_un_oubli(self):
        """Sans ce test, l'audit pourrait devenir tautologique (motifs cassés)."""
        import tools.audit_appels_llm as audit
        sans = ast.parse("from llm import passerelle\ndef main():\n    passerelle.appeler_chat()\n")
        avec = ast.parse("from llm import contexte_appel\ndef main():\n"
                         "    contexte_appel.fixer_provenance(contexte_appel.PROVENANCE_MESURE)\n")
        assert audit._importe_le_modele(sans) and not audit._fixe_la_provenance(sans)
        assert audit._fixe_la_provenance(avec)

    def test_us306_ca7_la_liste_des_outils_n_est_pas_vide(self):
        import tools.audit_appels_llm as audit
        assert len(audit.outils_appelant_un_modele()) >= len(OUTILS_DE_MESURE)


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — rien ne change pour les indicateurs existants
# ═════════════════════════════════════════════════════════════════════════════
class TestCA8NonRegression:

    def test_us306_ca8_les_jetons_du_harnais_comptent_toutes_les_provenances(self, conso, client):
        """`tests_conv/harness/base.py::jetons` somme les jetons du potager, quelle que
        soit la provenance : le rapport d'un scénario ne change pas."""
        with contexte_appel.provenance(PROVENANCE_TEST):
            _appel()
        _appel()
        total = conso.query(ConsoTokens).filter(ConsoTokens.potager_id == 3).count()
        assert total == 2
        assert sum(l.tokens_in for l in conso.query(ConsoTokens).all()) == 200

"""
tests/test_us307_echange_canal_unite.py — US-307 : relier les appels d'un même échange,
avec canal, version et unité

`conso_tokens` gagne `echange_ref`, `canal`, `version_app`, `unite`. Tout vient du contexte
posé à l'entrée de l'interaction (`llm/contexte_appel.py`) ; la passerelle fixe l'unité d'après
le type d'appel, à un seul endroit. Aucun appel réseau : les clients sont simulés.
"""
from __future__ import annotations

import ast
import contextvars
import inspect
import pathlib
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.context import TenantContext
from database.models import ConsoTokens, EchangeConversation
from llm import contexte_appel, passerelle
from llm.contexte_appel import (
    CANAL_FOND, CANAL_INCONNU, CANAL_MCP, CANAL_OUTIL, CANAL_PWA, CANAL_TELEGRAM, CANAUX,
)

RACINE = pathlib.Path(__file__).resolve().parent.parent
CTX = TenantContext(user_id=7, potager_id=3, role="owner")
CTX_FOND = TenantContext(user_id=None, potager_id=3)


# ─────────────────────────────────────────────────────────────────────────────
# Outillage
# ─────────────────────────────────────────────────────────────────────────────
def _reponse(tokens_in: int = 100, tokens_out: int = 20):
    usage = SimpleNamespace(
        prompt_tokens=tokens_in, completion_tokens=tokens_out,
        prompt_tokens_details=SimpleNamespace(cached_tokens=0),
    )
    message = SimpleNamespace(content="ok", tool_calls=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)


@pytest.fixture(autouse=True)
def _isolation(monkeypatch):
    monkeypatch.setattr(contexte_appel, "_en_mode_test", lambda: False)
    monkeypatch.setattr(passerelle, "modele_pour", lambda appel_type: "modele-de-test")
    # Un test qui ouvre un échange ou un canal ne doit pas le laisser au suivant.
    jetons = [contexte_appel._echange_ref.set(None), contexte_appel.canal_courant.set(CANAL_INCONNU)]
    yield
    contexte_appel.canal_courant.reset(jetons[1])
    contexte_appel._echange_ref.reset(jetons[0])


@pytest.fixture
def conso(test_db):
    with patch("llm.passerelle.SessionLocal", lambda: test_db):
        yield test_db


@pytest.fixture
def fournisseur():
    """Chat, dictée et voix servis par un client simulé non factice dans ses réponses."""
    faux = MagicMock()
    faux.chat.completions.create.return_value = _reponse()
    faux.audio.transcriptions.create.return_value = SimpleNamespace(
        text="où en sont mes tomates ?", usage={"prompt_audio_seconds": 4.2})
    faux.audio.speech.create.return_value.read.return_value = b"ID3faux-mp3"
    with patch("llm.passerelle._client", faux):
        yield faux


def _lignes(db) -> list[ConsoTokens]:
    return db.query(ConsoTokens).order_by(ConsoTokens.id).all()


def _chat(ctx=CTX, appel_type=passerelle.TYPE_AGENT):
    return passerelle.appeler_chat(appel_type=appel_type, ctx=ctx, prompt_fixe="Tu es un assistant.")


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — colonnes, contraintes, migration, rollback
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1Colonnes:

    def test_us307_ca1_migration_et_rollback(self):
        migration = (RACINE / "migrations" / "migration_v74.sql").read_text(encoding="utf-8")
        for fragment in ("echange_ref", "canal", "version_app", "unite", "ix_conso_tokens_echange_ref",
                         "NOT NULL DEFAULT 'inconnu'", "NOT NULL DEFAULT 'jeton'"):
            assert fragment in migration
        rollback = (RACINE / "migrations" / "rollback_v74.sql").read_text(encoding="utf-8")
        for colonne in ("echange_ref", "canal", "version_app", "unite"):
            assert f"DROP COLUMN IF EXISTS {colonne}" in rollback

    def test_us307_ca1_valeurs_par_defaut_de_l_existant(self, test_db):
        test_db.add(ConsoTokens(potager_id=1, date=date.today(), appel_type="question", modele="m"))
        test_db.commit()
        ligne = test_db.query(ConsoTokens).one()
        assert (ligne.canal, ligne.unite) == ("inconnu", "jeton")
        assert ligne.echange_ref is None and ligne.version_app is None

    @pytest.mark.parametrize("colonne,valeur", [("canal", "satellite"), ("unite", "litre")])
    def test_us307_ca1_contraintes_de_valeurs(self, test_db, colonne, valeur):
        from sqlalchemy.exc import IntegrityError
        test_db.add(ConsoTokens(potager_id=1, date=date.today(), appel_type="question",
                                modele="m", **{colonne: valeur}))
        with pytest.raises(IntegrityError):
            test_db.commit()
        test_db.rollback()

    def test_us307_ca1_les_canaux_de_la_contrainte_sont_ceux_du_code(self):
        contrainte = next(c for c in ConsoTokens.__table__.constraints
                          if getattr(c, "name", "") == "ck_conso_tokens_canal")
        for canal in CANAUX:
            assert f"'{canal}'" in str(contrainte.sqltext)
        assert CANAUX == {"telegram", "pwa", "mcp", "fond", "outil", "inconnu"}

    def test_us307_ca1_echange_ref_est_indexe(self):
        assert ConsoTokens.__table__.c.echange_ref.index is True
        assert ConsoTokens.__table__.c.echange_ref.nullable is True


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — l'existant est rejoué (migration) : unité déduite du type d'appel
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2ExistantRejoue:

    def test_us307_ca2_la_migration_deduit_l_unite_du_type(self):
        migration = (RACINE / "migrations" / "migration_v74.sql").read_text(encoding="utf-8")
        assert "SET unite = 'seconde'   WHERE appel_type = 'dictee'" in migration
        assert "SET unite = 'caractere' WHERE appel_type = 'voix'" in migration

    def test_us307_ca2_la_regle_de_la_migration_est_celle_de_la_passerelle(self):
        assert passerelle.unite_pour("dictee") == "seconde"
        assert passerelle.unite_pour("voix") == "caractere"
        assert passerelle.unite_pour("agent") == "jeton"


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — un échange à l'entrée de chaque interaction, partagé par toutes ses lignes
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3Echange:

    def test_us307_ca3_les_lignes_d_un_meme_echange_le_partagent(self, conso, fournisseur):
        contexte_appel.ouvrir_echange()
        ref = contexte_appel.echange_courant()
        _chat(appel_type=passerelle.TYPE_CLASSIFICATION)
        _chat(appel_type=passerelle.TYPE_AGENT)
        assert [l.echange_ref for l in _lignes(conso)] == [ref, ref]
        assert contexte_appel.identifiant_valide(ref)

    def test_us307_ca3_deux_echanges_ne_se_melangent_pas(self, conso, fournisseur):
        contexte_appel.ouvrir_echange()
        premier = contexte_appel.echange_courant()
        _chat()
        contexte_appel.ouvrir_echange()
        _chat()
        refs = [l.echange_ref for l in _lignes(conso)]
        assert refs[0] == premier and refs[1] != premier

    def test_us307_ca3_scenario_pwa_dictee_agent_oral_voix(self, conso, fournisseur):
        """Le scénario Gherkin : dictée (seconde), agent, oral et voix (caractère) d'une même
        réponse portent le même echange_ref, canal pwa, version du fichier VERSION."""
        contexte_appel.canal_courant.set(CANAL_PWA)
        contexte_appel.ouvrir_echange()                     # requête de dictée
        passerelle.dicter(ctx=CTX, contenu=b"audio", nom_fichier="dictee.webm", duree_s=4.2)
        ref = contexte_appel.echange_courant()
        # Requête du message : l'échange de la dictée est repris.
        contexte_appel.ouvrir_echange()
        assert contexte_appel.reprendre_echange(ref)
        _chat(appel_type=passerelle.TYPE_AGENT)
        # Requête de lecture : l'échange persisté de la réponse porte la même référence.
        contexte_appel.ouvrir_echange()
        assert contexte_appel.reprendre_echange(ref)
        _chat(appel_type=passerelle.TYPE_ORAL)
        passerelle.synthetiser(ctx=CTX, texte="Vos tomates vont bien.", voix_id="v1")

        lignes = _lignes(conso)
        assert [l.appel_type for l in lignes] == ["dictee", "agent", "oral", "voix"]
        assert {l.echange_ref for l in lignes} == {ref}
        assert {l.canal for l in lignes} == {"pwa"}
        assert {l.version_app for l in lignes} == {passerelle.VERSION_APP}
        assert [l.unite for l in lignes] == ["seconde", "jeton", "jeton", "caractere"]

    def test_us307_ca3_un_identifiant_mal_forme_est_ignore(self):
        contexte_appel.ouvrir_echange()
        avant = contexte_appel.echange_courant()
        for mauvais in (None, "", "abc", "x" * 32, "A" * 32, "0" * 33, 12):
            assert contexte_appel.reprendre_echange(mauvais) is False
        assert contexte_appel.echange_courant() == avant

    def test_us307_ca3_les_points_d_entree_ouvrent_un_echange(self):
        sources = {
            "app/bot/application.py": "contexte_appel.ouvrir_echange()",
            "app/api/main.py": "contexte_appel.ouvrir_echange()",
            "app/services/mcp/serveur.py": "contexte_appel.ouvrir_echange()",
        }
        for fichier, motif in sources.items():
            assert motif in (RACINE / fichier).read_text(encoding="utf-8"), fichier

    def test_us307_ca3_le_middleware_de_l_api_ouvre_un_echange_par_requete(self):
        from fastapi.testclient import TestClient
        from app.api.main import app
        vus: list = []

        original = contexte_appel.ouvrir_echange

        def espion():
            jeton = original()
            vus.append(contexte_appel.echange_courant())
            return jeton

        with patch.object(contexte_appel, "ouvrir_echange", espion):
            client = TestClient(app)
            client.get("/version")
            client.get("/version")
        assert len(vus) >= 2 and len(set(vus)) == len(vus)
        assert all(contexte_appel.identifiant_valide(v) for v in vus)

    def test_us307_ca3_le_message_reprend_l_echange_de_la_dictee(self):
        """`POST /compagnon/messages` : l'`echange_ref` de la requête devient l'échange courant."""
        from app.api import main as api
        from app.api.main import MessageCompagnonRequest
        ref = contexte_appel.nouvel_identifiant_echange()
        vu = {}

        def repondre(ctx, texte, mode):
            vu["ref"] = contexte_appel.echange_courant()
            return SimpleNamespace(en_donnees=lambda: {"ok": True})

        with patch.object(api.svc_echange_pwa, "repondre", repondre):
            api.envoyer_message_compagnon(MessageCompagnonRequest(texte="bonjour", echange_ref=ref), CTX)
        assert vu["ref"] == ref

    def test_us307_ca3_la_dictee_rend_son_echange(self):
        source = (RACINE / "app" / "api" / "main.py").read_text(encoding="utf-8")
        assert '"echange_ref": contexte_appel.echange_courant()' in source


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — sans interaction : un identifiant propre à l'exécution
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4SansInteraction:

    def test_us307_ca4_appel_de_fond_porte_un_identifiant_propre(self, conso, fournisseur):
        _chat(CTX_FOND, passerelle.TYPE_COMPAGNON_SIGNAL)
        _chat(CTX_FOND, passerelle.TYPE_COMPAGNON_SIGNAL)
        premier, second = _lignes(conso)
        assert contexte_appel.identifiant_valide(premier.echange_ref)
        assert contexte_appel.identifiant_valide(second.echange_ref)
        assert premier.echange_ref != second.echange_ref
        assert (premier.canal, second.canal) == (CANAL_FOND, CANAL_FOND)

    def test_us307_ca4_un_outil_porte_un_identifiant_pour_toute_son_execution(self, conso, fournisseur):
        def lancer():
            contexte_appel.demarrer_outil()
            _chat()
            _chat()
            return contexte_appel.echange_courant()

        ref = contextvars.copy_context().run(lancer)
        lignes = _lignes(conso)
        assert {l.echange_ref for l in lignes} == {ref}
        assert {l.canal for l in lignes} == {CANAL_OUTIL}
        assert {l.provenance for l in lignes} == {"mesure"}

    def test_us307_ca4_main_d_un_outil_ouvre_canal_outil_et_echange(self):
        from tools import rejeu_corpus

        def lancer():
            with patch("sys.argv", ["rejeu_corpus", "--corpus", "action", "--fichier", "inexistant.csv"]):
                try:
                    rejeu_corpus.main()
                except (SystemExit, Exception):  # noqa: BLE001 — seul l'effet sur le contexte compte
                    pass
            return contexte_appel.canal_courant.get(), contexte_appel.echange_courant()

        canal, ref = contextvars.copy_context().run(lancer)
        assert canal == CANAL_OUTIL and contexte_appel.identifiant_valide(ref)

    def test_us307_ca4_canal_inconnu_hors_interaction_avec_utilisateur(self, conso, fournisseur):
        _chat(CTX)
        assert _lignes(conso)[0].canal == CANAL_INCONNU

    @pytest.mark.parametrize("canal", [CANAL_TELEGRAM, CANAL_PWA, CANAL_MCP])
    def test_us307_ca4_le_canal_du_point_d_entree_est_ecrit(self, conso, fournisseur, canal):
        contexte_appel.canal_courant.set(canal)
        _chat()
        assert _lignes(conso)[0].canal == canal

    def test_us307_ca4_le_canal_est_le_meme_objet_que_celui_des_actions_menees(self):
        """`actions_menees.canal_courant` (US-261) et celui de la passerelle ne font qu'un."""
        from app.services.compagnon import actions_menees
        assert actions_menees.canal_courant is contexte_appel.canal_courant
        assert actions_menees.CANAL_PWA == CANAL_PWA == "pwa"


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — version lue une fois au démarrage
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5Version:

    def test_us307_ca5_version_app_reprend_le_fichier_version(self):
        from app import config
        attendu = (RACINE / "VERSION").read_text(encoding="utf-8").strip()
        assert config.VERSION_APP == attendu and attendu

    def test_us307_ca5_la_ligne_porte_la_version_du_processus(self, conso, fournisseur):
        with patch("llm.passerelle.VERSION_APP", "9.9.9"):
            _chat()
        assert _lignes(conso)[0].version_app == "9.9.9"

    def test_us307_ca5_le_fichier_n_est_pas_relu_a_chaque_appel(self, conso, fournisseur):
        with patch("builtins.open", side_effect=AssertionError("VERSION relu à l'appel")):
            _chat()
        assert len(_lignes(conso)) == 1

    def test_us307_ca5_fichier_absent_donne_une_version_nulle(self):
        from app import config
        with patch("builtins.open", side_effect=OSError):
            assert config._lire_version_app() is None


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — l'unité est fixée par la passerelle, en un seul endroit
# ═════════════════════════════════════════════════════════════════════════════
class TestCA6Unite:

    def test_us307_ca6_tout_type_d_appel_declare_son_unite(self):
        """Un type ajouté à TYPES_APPEL sans unité déclarée fait échouer ce test."""
        manquants = passerelle.TYPES_APPEL - set(passerelle.UNITES_PAR_TYPE)
        assert not manquants, f"types d'appel sans unité : {sorted(manquants)}"
        assert set(passerelle.UNITES_PAR_TYPE) <= passerelle.TYPES_APPEL
        for unite in passerelle.UNITES_PAR_TYPE.values():
            assert unite in {"jeton", "seconde", "caractere"}

    def test_us307_ca6_seuls_dictee_et_voix_ne_comptent_pas_en_jetons(self):
        hors_jeton = {t: u for t, u in passerelle.UNITES_PAR_TYPE.items() if u != "jeton"}
        assert hors_jeton == {"dictee": "seconde", "voix": "caractere"}

    def test_us307_ca6_type_sans_unite_refuse(self):
        with pytest.raises(passerelle.ContexteAppelManquantError):
            passerelle.unite_pour("inventé")

    def test_us307_ca6_aucun_appelant_ne_passe_l_unite(self):
        for fonction in (passerelle.appeler_chat, passerelle.appeler_chat_outils, passerelle.transcrire,
                         passerelle.dicter, passerelle.synthetiser, passerelle._enregistrer_conso):
            parametres = inspect.signature(fonction).parameters
            assert not {"unite", "canal", "echange_ref", "version_app"} & set(parametres)

    def test_us307_ca6_une_seule_ecriture_de_la_colonne_unite(self):
        """L'unité ne s'écrit qu'à un endroit : `_enregistrer_conso`."""
        arbre = ast.parse((RACINE / "llm" / "passerelle.py").read_text(encoding="utf-8"))
        ecritures = [n for n in ast.walk(arbre) if isinstance(n, ast.keyword) and n.arg == "unite"]
        assert len(ecritures) == 1

    def test_us307_ca6_la_ligne_ecrite_porte_l_unite_du_type(self, conso, fournisseur):
        contexte_appel.ouvrir_echange()
        passerelle.dicter(ctx=CTX, contenu=b"a", nom_fichier="d.webm", duree_s=3)
        passerelle.synthetiser(ctx=CTX, texte="Bonjour", voix_id="v1")
        dictee, voix = _lignes(conso)
        assert (dictee.unite, dictee.tokens_in) == ("seconde", 5)   # 4,2 s arrondies au-dessus
        assert (voix.unite, voix.tokens_in) == ("caractere", 7)


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — l'échange persisté retrouve ses lignes de consommation
# ═════════════════════════════════════════════════════════════════════════════
class TestCA7EchangePersiste:

    def test_us307_ca7_l_echange_persiste_retient_sa_reference(self, conso, fournisseur, test_db):
        from app.services.compagnon import conversations
        contexte_appel.canal_courant.set(CANAL_PWA)
        contexte_appel.ouvrir_echange()
        ref = contexte_appel.echange_courant()
        _chat()
        conversations.noter(CTX, "où en sont mes tomates ?", "Elles vont bien.", canal="pwa")

        fabrique = conversations.SessionLocal
        db = fabrique()
        try:
            echange = db.query(EchangeConversation).one()
            assert echange.echange_ref == ref
        finally:
            db.close()
        retrouvees = test_db.query(ConsoTokens).filter(ConsoTokens.echange_ref == echange.echange_ref).all()
        assert [l.appel_type for l in retrouvees] == ["agent"]

    def test_us307_ca7_la_lecture_reprend_l_echange_de_la_reponse(self, conso, fournisseur):
        from app.services.compagnon import conversations
        from app.services.voix import oral
        contexte_appel.ouvrir_echange()
        ref = contexte_appel.echange_courant()
        conversations.noter(CTX, "bonjour", "Bonjour, que puis-je faire ?", canal="pwa")
        echange_id = conversations.dernier_id(CTX)

        contexte_appel.ouvrir_echange()           # la requête de lecture a son propre échange…
        assert contexte_appel.echange_courant() != ref
        with patch.object(oral, "resumer", lambda ctx, texte, carte=False: oral.ResumeOral("Bonjour.", "modele")):
            oral.texte_oral(CTX, echange_id)
        assert contexte_appel.echange_courant() == ref   # … puis reprend celui de la réponse

    def test_us307_ca7_pas_de_cle_etrangere(self):
        colonne = EchangeConversation.__table__.c.echange_ref
        assert not colonne.foreign_keys and colonne.nullable


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — aucune signature métier ne change : le contexte seul transporte les valeurs
# ═════════════════════════════════════════════════════════════════════════════
class TestCA8Contexte:

    def test_us307_ca8_services_et_passerelle_sans_nouveau_parametre(self):
        from app.services.compagnon import conversations, echange_pwa
        from app.services.voix import dictee, lecture, oral, synthese
        interdits = {"echange_ref", "version_app", "unite"}
        for module in (echange_pwa, dictee, lecture, oral, synthese):
            for nom, fonction in inspect.getmembers(module, inspect.isfunction):
                if fonction.__module__ != module.__name__:
                    continue
                assert not interdits & set(inspect.signature(fonction).parameters), f"{module.__name__}.{nom}"
        # `noter` garde `canal` (le canal de l'échange affiché), pas l'échange de la mesure.
        assert "echange_ref" not in inspect.signature(conversations.noter).parameters

    def test_us307_ca8_le_contexte_suit_la_tache_asyncio(self):
        import asyncio

        async def interaction() -> str:
            contexte_appel.ouvrir_echange()
            await asyncio.sleep(0)
            return contexte_appel.echange_courant()

        async def deux():
            return await asyncio.gather(interaction(), interaction())

        premier, second = asyncio.run(deux())
        assert premier != second
        assert contexte_appel.echange_courant() is None

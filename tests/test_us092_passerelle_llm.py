"""
[US-092] Tests — Faire transiter tout appel au LLM par une passerelle unique.

Un test (au moins) par critère d'acceptance CA1 → CA13, plus les edge cases et
les cas d'erreur : quota saturé, délai dépassé, panne fournisseur, appel non
imputable. Aucun appel réseau : le client de la passerelle est intercepté.

Le test structurant de l'US est `TestCA10ApplicationUtileSansIA` : avec le
fournisseur en 429 permanent, l'application doit rester utile — côté bot comme
côté API. Le LLM ne doit jamais être un point de défaillance unique fonctionnel.
"""
import json
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import groq
import httpx
import pytest
from fastapi.testclient import TestClient

from app.services.context import TenantContext
from llm import passerelle
from llm.passerelle import (
    ContexteAppelManquantError,
    DelaiLLMDepasseError,
    FournisseurLLMIndisponibleError,
    LLMIndisponibleError,
    MESSAGE_REPLI_IA,
    QuotaLLMDepasseError,
    TYPES_APPEL,
)

RACINE = Path(__file__).resolve().parent.parent

CTX = TenantContext(user_id=7, potager_id=3, role="owner")


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures — client du fournisseur simulé
# ─────────────────────────────────────────────────────────────────────────────

def _reponse_chat(contenu: str, tokens_in: int = 120, tokens_out: int = 30,
                  tokens_cache: int = 0):
    """Réponse chat du SDK, avec un objet `usage` réaliste."""
    usage = MagicMock()
    usage.prompt_tokens = tokens_in
    usage.completion_tokens = tokens_out
    usage.prompt_tokens_details.cached_tokens = tokens_cache

    message = MagicMock()
    message.content = contenu
    choix = MagicMock()
    choix.message = message

    reponse = MagicMock()
    reponse.choices = [choix]
    reponse.usage = usage
    return reponse


def _erreur_429(retry_after: str = "0"):
    requete = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    reponse = httpx.Response(
        429,
        headers={"retry-after": retry_after, "x-ratelimit-remaining-tokens": "0"},
        request=requete,
    )
    return groq.RateLimitError("rate limit exceeded", response=reponse, body=None)


def _erreur_500():
    requete = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    reponse = httpx.Response(503, request=requete)
    return groq.InternalServerError("upstream", response=reponse, body=None)


def _erreur_timeout():
    requete = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    return groq.APITimeoutError(request=requete)


@pytest.fixture
def client_ok():
    """Client du fournisseur qui répond normalement."""
    client = MagicMock()
    client.chat.completions.create.return_value = _reponse_chat('{"action":"recolte"}')
    client.audio.transcriptions.create.return_value = "deux kilos de tomates"
    with patch("llm.passerelle._client", client):
        yield client


@pytest.fixture
def client_429():
    """Fournisseur en 429 permanent — sur le chat comme sur la transcription."""
    client = MagicMock()
    client.chat.completions.create.side_effect = _erreur_429()
    client.audio.transcriptions.create.side_effect = _erreur_429()
    with patch("llm.passerelle._client", client), \
         patch("llm.passerelle.time.sleep"):   # pas d'attente réelle en test
        yield client


@pytest.fixture
def conso_en_base(test_db):
    """Redirige l'écriture de `conso_tokens` vers la base de test."""
    with patch("llm.passerelle.SessionLocal", lambda: test_db):
        yield test_db


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — Point de passage unique, attesté par un audit exécutable
# ═════════════════════════════════════════════════════════════════════════════

class TestCA1AuditPointDePassageUnique:

    def test_us092_ca1_aucun_appel_direct_hors_passerelle(self):
        """CA1 : l'audit du code applicatif ne relève aucun appel direct."""
        import tools.audit_appels_llm as audit

        infractions = audit.auditer()
        assert infractions == [], (
            "Appels directs au fournisseur hors passerelle :\n"
            + "\n".join(f"  {f}:{l} — {m}" for f, l, m, _ in infractions)
        )

    def test_us092_ca1_audit_detecte_bien_une_infraction(self):
        """CA1 : l'audit n'est pas vide de sens — il repère un appel direct.

        Sans ce test, l'audit pourrait devenir tautologique (motifs cassés,
        périmètre vide) et continuer à passer au vert indéfiniment.
        """
        import tools.audit_appels_llm as audit

        source = (
            "from groq import Groq\n"
            "client = Groq(api_key='x')\n"
            "resp = client.chat.completions.create(model='m', messages=[])\n"
            "tr = client.audio.transcriptions.create(file=f, model='w')\n"
        )
        libelles = {libelle for _, libelle, _ in audit._infractions_du_fichier(source)}
        assert libelles == {
            "import direct du SDK groq",
            "instanciation directe du client Groq",
            "appel direct chat.completions.create",
            "appel direct audio.transcriptions.create",
        }

    def test_us092_ca1_audit_couvre_les_gros_fichiers_appelants(self):
        """CA1 : bot.py et main.py — d'où venaient la moitié des appels directs —
        sont bien dans le périmètre analysé.

        Garde-fou concret : `bot.py` porte un BOM UTF-8 hérité. Lu en utf-8
        strict, il ne se parsait pas et sortait silencieusement de l'audit, qui
        restait vert en ignorant le plus gros fichier du projet.
        """
        import tools.audit_appels_llm as audit

        analyses = {c.name for c in audit._fichiers_a_auditer()}
        assert {"bot.py", "main.py", "groq_client.py"} <= analyses

        source_bot = (RACINE / "bot.py").read_text(encoding="utf-8-sig")
        anomalies = [lib for _, lib, _ in audit._infractions_du_fichier(source_bot)
                     if "non analysable" in lib]
        assert anomalies == [], f"bot.py n'est pas réellement analysé : {anomalies}"

    def test_us092_ca1_fichier_illisible_nest_pas_declare_conforme(self):
        """CA1 : un fichier que l'audit n'arrive pas à analyser est signalé,
        jamais compté comme conforme par défaut."""
        import tools.audit_appels_llm as audit

        libelles = [lib for _, lib, _ in audit._infractions_du_fichier("def (:\n")]
        assert libelles and "non analysable" in libelles[0]

    def test_us092_ca1_audit_ignore_les_mentions_en_commentaire(self):
        """CA1 : une mention de Groq en prose n'est pas un appel — sinon
        l'audit produirait des faux positifs et finirait ignoré."""
        import tools.audit_appels_llm as audit

        source = (
            '"""Le moteur historique était Groq (gratuit)."""\n'
            "# on n'appelle plus Groq (voir la passerelle)\n"
            "MOTEUR = 'Groq (gratuit)'\n"
        )
        assert audit._infractions_du_fichier(source) == []


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — Aucun appel anonyme
# ═════════════════════════════════════════════════════════════════════════════

class TestCA2AucunAppelAnonyme:

    def test_us092_ca2_appel_sans_contexte_echoue(self, client_ok):
        """CA2 : sans TenantContext, l'appel échoue explicitement."""
        with pytest.raises(ContexteAppelManquantError):
            passerelle.appeler_chat(
                appel_type=passerelle.TYPE_PARSING, ctx=None,
                prompt_fixe="consigne", message_utilisateur="bonjour",
            )
        client_ok.chat.completions.create.assert_not_called()

    def test_us092_ca2_appel_sans_potager_echoue(self, client_ok):
        """CA2 : un contexte sans potager_id n'est imputable à personne."""
        ctx_vide = TenantContext(user_id=1, potager_id=None)
        with pytest.raises(ContexteAppelManquantError):
            passerelle.appeler_chat(
                appel_type=passerelle.TYPE_PARSING, ctx=ctx_vide,
                prompt_fixe="consigne", message_utilisateur="bonjour",
            )
        client_ok.chat.completions.create.assert_not_called()

    def test_us092_ca2_type_appel_inconnu_refuse(self, client_ok):
        """CA2 : un type d'appel hors nomenclature est refusé avant le réseau."""
        with pytest.raises(ContexteAppelManquantError):
            passerelle.appeler_chat(
                appel_type="divination", ctx=CTX,
                prompt_fixe="consigne", message_utilisateur="bonjour",
            )
        client_ok.chat.completions.create.assert_not_called()

    def test_us092_ca2_les_cinq_types_sont_declares(self):
        """CA2 : la nomenclature couvre les cinq usages réels du produit."""
        assert TYPES_APPEL == {
            "classification", "parsing", "question", "synthese", "transcription",
        }

    def test_us092_ca2_erreur_de_contexte_nest_pas_une_indisponibilite(self):
        """CA2 : un appel non imputable est un défaut de code, pas un 429 —
        il ne doit jamais être capté par le repli utilisateur."""
        assert not issubclass(ContexteAppelManquantError, LLMIndisponibleError)


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — Modèle configurable par type
# ═════════════════════════════════════════════════════════════════════════════

class TestCA3ModeleParType:

    def test_us092_ca3_chaque_type_a_son_modele(self):
        """CA3 : chaque type d'appel résout un modèle."""
        for type_appel in TYPES_APPEL:
            assert passerelle.modele_pour(type_appel)

    def test_us092_ca3_changer_de_modele_est_une_configuration(self, client_ok):
        """CA3 : router la classification sur un petit modèle rapide ne demande
        aucun changement de code — seule la configuration bouge."""
        config = dict(passerelle.GROQ_MODELE_PAR_TYPE)
        config["classification"] = "petit-modele-rapide"

        with patch.dict(passerelle.GROQ_MODELE_PAR_TYPE, config, clear=True):
            reponse = passerelle.appeler_chat(
                appel_type=passerelle.TYPE_CLASSIFICATION, ctx=CTX,
                prompt_fixe="classe ce message", message_utilisateur="stats",
            )

        assert reponse.modele == "petit-modele-rapide"
        assert client_ok.chat.completions.create.call_args.kwargs["model"] == "petit-modele-rapide"

    def test_us092_ca3_consommation_imputee_au_modele_appele(self, conso_en_base, client_ok):
        """CA3 : la consommation est imputée au modèle réellement appelé —
        les quotas du fournisseur étant comptés par modèle."""
        from database.models import ConsoTokens

        config = dict(passerelle.GROQ_MODELE_PAR_TYPE)
        config["classification"] = "petit-modele-rapide"
        with patch.dict(passerelle.GROQ_MODELE_PAR_TYPE, config, clear=True):
            passerelle.appeler_chat(
                appel_type=passerelle.TYPE_CLASSIFICATION, ctx=CTX,
                prompt_fixe="classe ce message", message_utilisateur="stats",
            )

        ligne = conso_en_base.query(ConsoTokens).one()
        assert ligne.modele == "petit-modele-rapide"
        assert ligne.appel_type == "classification"


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — La transcription passe aussi par la passerelle
# ═════════════════════════════════════════════════════════════════════════════

class TestCA4TranscriptionDansLaPasserelle:

    def test_us092_ca4_transcription_typee_et_imputee(self, conso_en_base, tmp_path, client_ok):
        """CA4 : un vocal produit une ligne de consommation de type transcription."""
        from database.models import ConsoTokens

        fichier = tmp_path / "message.ogg"
        fichier.write_bytes(b"faux-audio")

        reponse = passerelle.transcrire(
            ctx=CTX, chemin_fichier=str(fichier), nom_fichier="message.ogg"
        )

        assert reponse.texte == "deux kilos de tomates"
        ligne = conso_en_base.query(ConsoTokens).one()
        assert ligne.appel_type == "transcription"
        assert ligne.potager_id == CTX.potager_id

    def test_us092_ca4_transcription_garde_son_propre_modele(self, tmp_path, client_ok):
        """CA4 : elle conserve son modèle (et donc son quota) propre — c'est
        celui qui saturera le premier en usage vocal."""
        from config import GROQ_WHISPER_MODEL

        fichier = tmp_path / "message.ogg"
        fichier.write_bytes(b"faux-audio")
        passerelle.transcrire(ctx=CTX, chemin_fichier=str(fichier))

        appel = client_ok.audio.transcriptions.create.call_args
        assert appel.kwargs["model"] == GROQ_WHISPER_MODEL
        assert appel.kwargs["model"] != passerelle.modele_pour(passerelle.TYPE_PARSING) \
            or GROQ_WHISPER_MODEL == passerelle.modele_pour(passerelle.TYPE_PARSING)

    def test_us092_ca4_transcription_sans_contexte_refusee(self, tmp_path, client_ok):
        """CA4 + CA2 : la transcription n'échappe pas à la règle d'imputation."""
        fichier = tmp_path / "message.ogg"
        fichier.write_bytes(b"faux-audio")
        with pytest.raises(ContexteAppelManquantError):
            passerelle.transcrire(ctx=None, chemin_fichier=str(fichier))


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — Mesure : la table conso_tokens
# ═════════════════════════════════════════════════════════════════════════════

class TestCA5MesureConsommation:

    def test_us092_ca5_ligne_de_consommation_complete(self, conso_en_base, client_ok):
        """CA5 : chaque appel alimente conso_tokens avec toutes ses colonnes."""
        from database.models import ConsoTokens

        passerelle.appeler_chat(
            appel_type=passerelle.TYPE_QUESTION, ctx=CTX,
            prompt_fixe="consigne", message_utilisateur="combien de tomates ?",
        )

        ligne = conso_en_base.query(ConsoTokens).one()
        assert ligne.potager_id == 3
        assert ligne.user_id == 7
        assert ligne.date is not None
        assert ligne.appel_type == "question"
        assert ligne.modele
        assert ligne.tokens_in == 120
        assert ligne.tokens_out == 30
        assert ligne.latence_ms >= 0
        assert ligne.issue == "ok"

    def test_us092_ca5_les_echecs_sont_mesures_aussi(self, conso_en_base, client_429):
        """CA5 : un 429 laisse une trace — sinon une saturation ressemblerait
        à une simple baisse d'usage."""
        from database.models import ConsoTokens

        with pytest.raises(QuotaLLMDepasseError):
            passerelle.appeler_chat(
                appel_type=passerelle.TYPE_PARSING, ctx=CTX,
                prompt_fixe="consigne", message_utilisateur="récolté 2 kg",
            )

        ligne = conso_en_base.query(ConsoTokens).one()
        assert ligne.issue == "quota"

    def test_us092_ca5_panne_de_mesure_ne_casse_pas_lappel(self, client_ok):
        """CA5 edge : la mesure est de l'observabilité — si la base refuse
        l'écriture, l'appel réussit quand même."""
        session_ko = MagicMock()
        session_ko.commit.side_effect = RuntimeError("base indisponible")

        with patch("llm.passerelle.SessionLocal", lambda: session_ko):
            reponse = passerelle.appeler_chat(
                appel_type=passerelle.TYPE_PARSING, ctx=CTX,
                prompt_fixe="consigne", message_utilisateur="récolté 2 kg",
            )
        assert reponse.texte == '{"action":"recolte"}'

    def test_us092_ca5_cette_us_ne_plafonne_pas(self, conso_en_base, client_ok):
        """CA5 : mesurer n'est pas plafonner — aucun appel n'est refusé au motif
        d'une consommation déjà enregistrée (le blocage relève de l'US quotas)."""
        for _ in range(5):
            passerelle.appeler_chat(
                appel_type=passerelle.TYPE_PARSING, ctx=CTX,
                prompt_fixe="consigne", message_utilisateur="récolté 2 kg",
            )
        assert client_ok.chat.completions.create.call_count == 5


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — Prompts assemblés partie fixe en tête
# ═════════════════════════════════════════════════════════════════════════════

class TestCA6PromptsCachables:

    def test_us092_ca6_partie_fixe_en_tete_variables_en_fin(self, client_ok):
        """CA6 : le préfixe stable ouvre le prompt, les variables le ferment."""
        passerelle.appeler_chat(
            appel_type=passerelle.TYPE_SYNTHESE, ctx=CTX,
            prompt_fixe="CONSIGNE STABLE",
            prompt_variable="\nHistorique : [1,2,3]",
            message_utilisateur="combien ?",
        )
        messages = client_ok.chat.completions.create.call_args.kwargs["messages"]
        assert messages[0]["content"].startswith("CONSIGNE STABLE")
        assert messages[0]["content"].endswith("Historique : [1,2,3]")
        assert messages[-1] == {"role": "user", "content": "combien ?"}

    def test_us092_ca6_jetons_de_cache_distingues(self, conso_en_base, client_ok):
        """CA6 : les jetons servis depuis le cache du fournisseur sont comptés
        à part dès qu'il les expose."""
        from database.models import ConsoTokens

        client_ok.chat.completions.create.return_value = _reponse_chat(
            "ok", tokens_in=900, tokens_out=20, tokens_cache=850
        )
        reponse = passerelle.appeler_chat(
            appel_type=passerelle.TYPE_PARSING, ctx=CTX,
            prompt_fixe="consigne", message_utilisateur="récolté 2 kg",
        )

        assert reponse.tokens_cache == 850
        assert conso_en_base.query(ConsoTokens).one().tokens_cache == 850

    def test_us092_ca6_absence_de_cache_ne_casse_rien(self, client_ok):
        """CA6 edge : un fournisseur qui n'expose pas le cache → 0, pas d'erreur."""
        usage = MagicMock()
        usage.prompt_tokens = 100
        usage.completion_tokens = 10
        usage.prompt_tokens_details = None
        reponse_sdk = _reponse_chat("ok")
        reponse_sdk.usage = usage
        client_ok.chat.completions.create.return_value = reponse_sdk

        reponse = passerelle.appeler_chat(
            appel_type=passerelle.TYPE_PARSING, ctx=CTX,
            prompt_fixe="consigne", message_utilisateur="récolté 2 kg",
        )
        assert reponse.tokens_cache == 0
        assert reponse.tokens_in == 100

    def test_us092_ca6_prompt_de_question_met_lhistorique_en_fin(self, client_ok):
        """CA6 : repondre_question() n'ouvre plus le prompt sur l'historique."""
        from llm.groq_client import repondre_question

        repondre_question("combien ?", '[{"culture":"tomate"}]', ctx=CTX)
        systeme = client_ok.chat.completions.create.call_args.kwargs["messages"][0]["content"]
        assert systeme.index("Historique potager") > systeme.index("REGLE ABSOLUE")


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — Ordre de grandeur de consommation mesuré et consigné
# ═════════════════════════════════════════════════════════════════════════════

class TestCA7ConsommationConsignee:

    def test_us092_ca7_chaque_appel_logue_ses_jetons(self, caplog, client_ok):
        """CA7 : l'impact en jetons est chiffré et loggé pour tout appel LLM."""
        with caplog.at_level(logging.INFO, logger="potager"):
            passerelle.appeler_chat(
                appel_type=passerelle.TYPE_PARSING, ctx=CTX,
                prompt_fixe="consigne", message_utilisateur="récolté 2 kg",
            )
        journal = caplog.text
        assert "in=120" in journal and "out=30" in journal
        assert "potager=3" in journal

    def test_us092_ca7_ordre_de_grandeur_consigne(self):
        """CA7 : le relevé avant / après est consigné dans le dépôt."""
        doc = RACINE / "docs" / "AUDIT_PASSERELLE_LLM_US092.md"
        assert doc.exists(), "le relevé de consommation avant/après doit être consigné"
        contenu = doc.read_text(encoding="utf-8")
        assert "avant" in contenu.lower() and "après" in contenu.lower()


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — Un 429 est intercepté et typé
# ═════════════════════════════════════════════════════════════════════════════

class TestCA8QuotaIntercepte:

    def test_us092_ca8_429_devient_exception_typee(self, client_429):
        """CA8 : le 429 ne remonte jamais brut."""
        with pytest.raises(QuotaLLMDepasseError) as exc:
            passerelle.appeler_chat(
                appel_type=passerelle.TYPE_PARSING, ctx=CTX,
                prompt_fixe="consigne", message_utilisateur="récolté 2 kg",
            )
        assert not isinstance(exc.value, groq.RateLimitError)
        assert exc.value.issue == "quota"

    def test_us092_ca8_trois_causes_restent_distinguables(self, client_ok):
        """CA8 : quota, délai et panne mènent au même repli mais restent
        distincts dans les journaux — sinon le diagnostic devient impossible."""
        cas = [
            (_erreur_429(), QuotaLLMDepasseError, "quota"),
            (_erreur_timeout(), DelaiLLMDepasseError, "delai"),
            (_erreur_500(), FournisseurLLMIndisponibleError, "erreur"),
        ]
        for erreur, attendu, issue in cas:
            client_ok.chat.completions.create.side_effect = erreur
            with patch("llm.passerelle.time.sleep"), pytest.raises(attendu) as exc:
                passerelle.appeler_chat(
                    appel_type=passerelle.TYPE_PARSING, ctx=CTX,
                    prompt_fixe="consigne", message_utilisateur="récolté 2 kg",
                )
            assert exc.value.issue == issue
            assert isinstance(exc.value, LLMIndisponibleError)


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — Chaque appelant déclare son repli
# ═════════════════════════════════════════════════════════════════════════════

class TestCA9ReplisDeclares:

    def test_us092_ca9_message_invariable(self):
        """CA9 : le message de repli est celui, mot pour mot, décidé par l'US."""
        assert MESSAGE_REPLI_IA == (
            "L'analyse avancée par IA est temporairement indisponible, "
            "réessaie dans quelques minutes"
        )

    @pytest.mark.asyncio
    async def test_us092_ca9_bot_ne_plante_pas_et_previent(self, client_429):
        """CA9 : côté bot, une dictée pendant une saturation reçoit le message
        de repli — jamais un silence, jamais une trace technique."""
        from bot import _parse_and_save

        update = MagicMock()
        update.message.reply_text = AsyncMock()
        update.callback_query = None

        with patch("bot.require_role"):
            await _parse_and_save(update, "récolté 2 kg de tomates")

        envoye = update.message.reply_text.await_args[0][0]
        assert MESSAGE_REPLI_IA in envoye
        assert "429" not in envoye and "RateLimit" not in envoye

    @pytest.mark.asyncio
    async def test_us092_ca9_bot_ninvente_aucun_evenement(self, client_429):
        """CA9 : jamais une réponse inventée — rien n'est enregistré en base."""
        from bot import _parse_and_save

        update = MagicMock()
        update.message.reply_text = AsyncMock()
        update.callback_query = None

        with patch("bot.require_role"), \
             patch("bot.SessionLocal") as session:
            await _parse_and_save(update, "récolté 2 kg de tomates")

        session.assert_not_called()

    def test_us092_ca9_api_repond_503_avec_le_message(self, api_client, client_429):
        """CA9 : côté API, l'indisponibilité est un 503 portant le message de
        repli, pas une 500 ni une trace de 429."""
        reponse = api_client.post("/ask", json={"texte": "combien de tomates ?"})
        assert reponse.status_code == 503
        assert reponse.json()["detail"] == MESSAGE_REPLI_IA

    def test_us092_ca9_repli_de_lecture_json_reste_distinct(self, client_ok):
        """CA9 edge : une réponse illisible garde son fallback conservatif —
        elle ne doit pas être confondue avec une indisponibilité."""
        from llm.groq_client import classify_intent_pwa

        client_ok.chat.completions.create.return_value = _reponse_chat("n'importe quoi")
        assert classify_intent_pwa("récolté 2 kg", ctx=CTX) == "ACTION"


# ═════════════════════════════════════════════════════════════════════════════
# CA10 — L'application reste utile sans IA (test structurant de l'US)
# ═════════════════════════════════════════════════════════════════════════════

MOCK_STOCK = [{"culture": "tomate", "nb_plants": 6, "type_organe": "reproducteur"}]


def _db_api():
    db = MagicMock()
    db.query.return_value.count.return_value = 42
    db.query.return_value.filter.return_value.count.return_value = 0
    db.query.return_value.filter.return_value.first.return_value = (0, 0)
    db.query.return_value.filter.return_value.all.return_value = []
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    db.query.return_value.order_by.return_value.all.return_value = []
    db.query.return_value.all.return_value = []
    db.query.return_value.group_by.return_value.all.return_value = []
    db.query.return_value.filter.return_value.group_by.return_value.all.return_value = []
    return db


@pytest.fixture
def api_client():
    """Client HTTP de l'API, authentifié sur le potager par défaut."""
    from main import app, get_current_user_ctx
    from app.services.context import default_context

    app.dependency_overrides[get_current_user_ctx] = default_context
    with (
        patch("main.SessionLocal", return_value=_db_api()),
        patch("utils.stock.calcul_stock_cultures", return_value=MOCK_STOCK),
        patch("utils.stock.format_stock_stats_json", return_value=MOCK_STOCK),
        patch("utils.stock.calcul_godets", return_value={}),
    ):
        with TestClient(app) as client:
            yield client
    app.dependency_overrides.pop(get_current_user_ctx, None)


class TestCA10ApplicationUtileSansIA:
    """Fournisseur en 429 permanent : ce qui ne dépend pas du LLM doit vivre."""

    @pytest.mark.parametrize("route", ["/health", "/stats", "/plan", "/historique", "/godets"])
    def test_us092_ca10_api_consultations_restent_fonctionnelles(
        self, api_client, client_429, route
    ):
        """CA10 : /stats, /plan, /historique, le stock et la consultation web
        répondent normalement pendant la saturation."""
        reponse = api_client.get(route)
        assert reponse.status_code == 200, f"{route} → {reponse.status_code}"

    def test_us092_ca10_api_meteo_reste_fonctionnelle(self, api_client, client_429):
        """CA10 : la météo (Open-Meteo, aucun LLM) reste servie."""
        db_meteo = MagicMock()
        db_meteo.query.return_value.filter.return_value.first.return_value = None
        with patch("main.SessionLocal", return_value=db_meteo):
            reponse = api_client.get("/meteo")
        assert reponse.status_code == 200
        client_429.chat.completions.create.assert_not_called()

    def test_us092_ca10_aucune_de_ces_routes_nappelle_le_modele(
        self, api_client, client_429
    ):
        """CA10 : et surtout, aucune d'elles n'a nécessité un appel au modèle —
        c'est ce qui garantit qu'elles resteront vraies demain."""
        for route in ("/health", "/stats", "/plan", "/historique", "/godets"):
            api_client.get(route)
        client_429.chat.completions.create.assert_not_called()
        client_429.audio.transcriptions.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_us092_ca10_bot_stats_reste_fonctionnel(self, client_429, test_db):
        """CA10 : côté bot, /stats répond sans toucher au modèle."""
        from bot import cmd_stats

        update = MagicMock()
        update.message.reply_text = AsyncMock()
        update.effective_message.reply_text = AsyncMock()

        with patch("bot.SessionLocal", return_value=test_db), \
             patch("bot.send_voice_reply", new_callable=AsyncMock):
            await cmd_stats(update, None)

        # /stats passe par l'envoi découpé (update.effective_message)
        update.effective_message.reply_text.assert_awaited()
        client_429.chat.completions.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_us092_ca10_bot_plan_reste_fonctionnel(self, client_429):
        """CA10 : côté bot, /plan répond sans toucher au modèle."""
        from bot import cmd_plan

        update = MagicMock()
        update.message.reply_text = AsyncMock()
        ctx = MagicMock()
        ctx.args = []
        ctx.user_data = {}

        with patch("bot.SessionLocal", return_value=MagicMock()), \
             patch("bot.calcul_occupation_parcelles", return_value={}), \
             patch("bot.get_all_parcelles", return_value=[]), \
             patch("bot.send_voice_reply", new_callable=AsyncMock):
            await cmd_plan(update, ctx)

        update.message.reply_text.assert_awaited()
        client_429.chat.completions.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_us092_ca10_bot_historique_reste_fonctionnel(self, client_429, test_db):
        """CA10 : côté bot, /historique répond sans toucher au modèle."""
        from bot import cmd_historique

        update = MagicMock()
        update.message.reply_text = AsyncMock()
        ctx = MagicMock()
        ctx.args = []
        ctx.user_data = {}

        with patch("bot.SessionLocal", return_value=test_db), \
             patch("bot.send_voice_reply", new_callable=AsyncMock):
            await cmd_historique(update, ctx)

        update.message.reply_text.assert_awaited()
        client_429.chat.completions.create.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# CA11 — En-têtes de limitation de débit lus et journalisés
# ═════════════════════════════════════════════════════════════════════════════

class TestCA11EntetesDeDebit:

    def test_us092_ca11_entetes_captures_au_niveau_transport(self):
        """CA11 : le hook lit les en-têtes x-ratelimit-* de la réponse HTTP."""
        passerelle._derniers_entetes_debit.clear()
        requete = httpx.Request("POST", "https://api.groq.com/x")
        reponse = httpx.Response(
            200,
            headers={
                "x-ratelimit-remaining-tokens": "1200",
                "x-ratelimit-limit-tokens": "6000",
                "content-type": "application/json",
            },
            request=requete,
        )
        passerelle._capturer_entetes_debit(reponse)

        entetes = passerelle.entetes_debit()
        assert entetes["x-ratelimit-remaining-tokens"] == "1200"
        assert entetes["x-ratelimit-limit-tokens"] == "6000"
        assert "content-type" not in entetes

    def test_us092_ca11_entetes_journalises_avec_lappel(self, caplog, client_ok):
        """CA11 : ils sont journalisés — c'est la matière qui permettra de
        freiner avant le 429 plutôt que de le subir."""
        passerelle._derniers_entetes_debit.clear()
        passerelle._derniers_entetes_debit["x-ratelimit-remaining-tokens"] = "42"

        with caplog.at_level(logging.INFO, logger="potager"):
            passerelle.appeler_chat(
                appel_type=passerelle.TYPE_PARSING, ctx=CTX,
                prompt_fixe="consigne", message_utilisateur="récolté 2 kg",
            )
        assert "x-ratelimit-remaining-tokens" in caplog.text

    def test_us092_ca11_hook_tolere_une_reponse_sans_entetes(self):
        """CA11 edge : un hook ne doit jamais casser l'appel qu'il observe."""
        passerelle._capturer_entetes_debit(MagicMock(headers=None))  # pas d'exception


# ═════════════════════════════════════════════════════════════════════════════
# CA12 — Une seule nouvelle tentative, temporisée par Retry-After
# ═════════════════════════════════════════════════════════════════════════════

class TestCA12NouvelleTentativeUnique:

    def test_us092_ca12_une_seule_nouvelle_tentative_sur_429(self, client_ok):
        """CA12 : 2 appels au maximum (l'original + une reprise), pas plus."""
        client_ok.chat.completions.create.side_effect = _erreur_429()
        with patch("llm.passerelle.time.sleep"), pytest.raises(QuotaLLMDepasseError):
            passerelle.appeler_chat(
                appel_type=passerelle.TYPE_PARSING, ctx=CTX,
                prompt_fixe="consigne", message_utilisateur="récolté 2 kg",
            )
        assert client_ok.chat.completions.create.call_count == 2

    def test_us092_ca12_reprise_reussie_sert_la_reponse(self, client_ok):
        """CA12 : si la reprise aboutit, l'utilisateur ne voit rien du 429."""
        client_ok.chat.completions.create.side_effect = [
            _erreur_429(), _reponse_chat('{"action":"recolte"}')
        ]
        with patch("llm.passerelle.time.sleep"):
            reponse = passerelle.appeler_chat(
                appel_type=passerelle.TYPE_PARSING, ctx=CTX,
                prompt_fixe="consigne", message_utilisateur="récolté 2 kg",
            )
        assert reponse.texte == '{"action":"recolte"}'

    def test_us092_ca12_temporisation_respecte_retry_after(self, client_ok):
        """CA12 : l'en-tête Retry-After pilote l'attente, dans la limite du
        plafond configuré (on n'endort pas un handler Telegram longtemps)."""
        client_ok.chat.completions.create.side_effect = _erreur_429(retry_after="1")
        with patch("llm.passerelle.time.sleep") as sommeil, \
             pytest.raises(QuotaLLMDepasseError):
            passerelle.appeler_chat(
                appel_type=passerelle.TYPE_PARSING, ctx=CTX,
                prompt_fixe="consigne", message_utilisateur="récolté 2 kg",
            )
        assert sommeil.call_args[0][0] == pytest.approx(1.0)

    def test_us092_ca12_retry_after_excessif_est_plafonne(self, client_ok):
        """CA12 : un Retry-After de 10 minutes ne fait pas patienter 10 minutes —
        on bascule en mode dégradé, ce qui rend la saturation visible."""
        client_ok.chat.completions.create.side_effect = _erreur_429(retry_after="600")
        with patch("llm.passerelle.time.sleep") as sommeil, \
             pytest.raises(QuotaLLMDepasseError):
            passerelle.appeler_chat(
                appel_type=passerelle.TYPE_PARSING, ctx=CTX,
                prompt_fixe="consigne", message_utilisateur="récolté 2 kg",
            )
        assert sommeil.call_args[0][0] <= passerelle.GROQ_RETRY_MAX_S

    def test_us092_ca12_5xx_est_rejoue_lui_aussi(self, client_ok):
        """CA12 : la reprise couvre les 5xx comme les 429."""
        client_ok.chat.completions.create.side_effect = _erreur_500()
        with patch("llm.passerelle.time.sleep"), \
             pytest.raises(FournisseurLLMIndisponibleError):
            passerelle.appeler_chat(
                appel_type=passerelle.TYPE_PARSING, ctx=CTX,
                prompt_fixe="consigne", message_utilisateur="récolté 2 kg",
            )
        assert client_ok.chat.completions.create.call_count == 2

    def test_us092_ca12_delai_depasse_nest_pas_rejoue(self, client_ok):
        """CA12 : un appel trop lent emprunte directement le chemin de repli —
        le rejouer doublerait l'attente déjà subie par le jardinier."""
        client_ok.chat.completions.create.side_effect = _erreur_timeout()
        with patch("llm.passerelle.time.sleep"), pytest.raises(DelaiLLMDepasseError):
            passerelle.appeler_chat(
                appel_type=passerelle.TYPE_PARSING, ctx=CTX,
                prompt_fixe="consigne", message_utilisateur="récolté 2 kg",
            )
        assert client_ok.chat.completions.create.call_count == 1

    def test_us092_ca12_delai_maximal_configure(self):
        """CA12 : un délai maximal par appel est bien configuré."""
        assert passerelle.GROQ_TIMEOUT_S > 0


# ═════════════════════════════════════════════════════════════════════════════
# CA13 — Étanchéité des journaux
# ═════════════════════════════════════════════════════════════════════════════

class TestCA13EtancheiteDesJournaux:

    def test_us092_ca13_ni_prompt_ni_texte_original_dans_les_journaux(
        self, caplog, client_ok
    ):
        """CA13 : les journaux de la passerelle portent des métadonnées de
        consommation, pas des contenus."""
        secret_utilisateur = "j-ai-recolte-des-tomates-dans-mon-jardin-secret"
        with caplog.at_level(logging.DEBUG, logger="potager"):
            passerelle.appeler_chat(
                appel_type=passerelle.TYPE_PARSING, ctx=CTX,
                prompt_fixe="CONSIGNE-CONFIDENTIELLE-DU-PROMPT",
                message_utilisateur=secret_utilisateur,
            )
        assert secret_utilisateur not in caplog.text
        assert "CONSIGNE-CONFIDENTIELLE-DU-PROMPT" not in caplog.text

    def test_us092_ca13_aucune_cle_dans_les_journaux(self, caplog, client_429):
        """CA13 : y compris sur le chemin d'erreur, aucune clé ne fuite."""
        from config import GROQ_API_KEY

        with caplog.at_level(logging.DEBUG, logger="potager"), \
             pytest.raises(QuotaLLMDepasseError):
            passerelle.appeler_chat(
                appel_type=passerelle.TYPE_PARSING, ctx=CTX,
                prompt_fixe="consigne", message_utilisateur="récolté 2 kg",
            )
        assert GROQ_API_KEY not in caplog.text
        assert "api_key" not in caplog.text.lower()

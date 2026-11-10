"""
tests/test_fournisseurs_compatibles.py — fournisseurs compatibles OpenAI déclarés dans l'env

Brancher un autre fournisseur que Groq ou Mistral (OpenAI, serveur de voix local…) est un
réglage du `.env` : `FOURNISSEURS_COMPATIBLES`, `FOURNISSEUR_<NOM>_BASE_URL`,
`FOURNISSEUR_<NOM>_API_KEY`, puis le préfixe `<nom>/` dans `GROQ_MODEL_<TYPE>`. Les voix
proposées hors Mistral se déclarent dans `VOIX_CATALOGUE`.

Aucun appel réseau : les requêtes passent par un `httpx.MockTransport`, ce qui vérifie
l'URL, l'en-tête d'authentification et le corps réellement envoyés.
"""
from __future__ import annotations

import json
import pathlib
from unittest.mock import patch

import httpx
import pytest

from app import config
from app.services.context import TenantContext
from app.services.voix import catalogue
from llm import passerelle
from llm.passerelle import LLMIndisponibleError, TYPE_DICTEE, TYPE_VOIX, VoixInconnueError

RACINE = pathlib.Path(__file__).resolve().parent.parent
CTX = TenantContext(user_id=7, potager_id=3, role="owner")
MP3 = b"ID3\x04\x00faux-mp3-oai"
DECLARES = {"oai": {"base_url": "https://api.exemple.test/v1", "api_key": "sk-test"}}


# ─────────────────────────────────────────────────────────────────────────────
# Outillage
# ─────────────────────────────────────────────────────────────────────────────
class Fournisseur:
    """Faux fournisseur OpenAI : note chaque requête et répond selon le chemin."""

    def __init__(self, statut_voix: int = 200, corps_erreur: dict | None = None):
        self.requetes: list[httpx.Request] = []
        self.statut_voix, self.corps_erreur = statut_voix, corps_erreur

    def __call__(self, requete: httpx.Request) -> httpx.Response:
        self.requetes.append(requete)
        if requete.url.path.endswith("/audio/speech"):
            if self.statut_voix != 200:
                return httpx.Response(self.statut_voix, json=self.corps_erreur or {})
            return httpx.Response(200, content=MP3, headers={"content-type": "audio/mpeg"})
        if requete.url.path.endswith("/audio/transcriptions"):
            return httpx.Response(200, json={"text": " Trois rangs de carottes. "})
        return httpx.Response(404, json={"error": "inconnu"})


@pytest.fixture
def fournisseur():
    """Un fournisseur `oai` déclaré, servi par le faux transport, et les deux types vocaux dessus."""
    faux = Fournisseur()
    class _ClientSimule(httpx.Client):   # sous-classe : le SDK vérifie isinstance(httpx.Client)
        def __init__(self, *args, **kwargs):
            super().__init__(*args, transport=httpx.MockTransport(faux), **kwargs)

    with patch.dict(passerelle.FOURNISSEURS_COMPATIBLES, DECLARES, clear=True), \
         patch.dict(passerelle._clients_compatibles, {}, clear=True), \
         patch.dict(passerelle.GROQ_MODELE_PAR_TYPE,
                    {TYPE_VOIX: "oai/gpt-4o-mini-tts", TYPE_DICTEE: "oai/gpt-4o-mini-transcribe"}), \
         patch("httpx.Client", _ClientSimule), \
         patch("llm.passerelle.time.sleep"):
        yield faux


@pytest.fixture
def conso_en_base(test_db):
    with patch("llm.passerelle.SessionLocal", lambda: test_db):
        yield test_db


def _lignes_conso(db):
    from database.models import ConsoTokens
    return db.query(ConsoTokens).order_by(ConsoTokens.id).all()


# ═════════════════════════════════════════════════════════════════════════════
# Lecture de la configuration
# ═════════════════════════════════════════════════════════════════════════════
class TestConfiguration:
    def test_fournisseur_declare_retenu_url_sans_barre_finale(self):
        retenus, ecartes = config.lire_fournisseurs_compatibles({
            "FOURNISSEURS_COMPATIBLES": " OAI , local ",
            "FOURNISSEUR_OAI_BASE_URL": "https://api.openai.com/v1/",
            "FOURNISSEUR_OAI_API_KEY": "sk-1",
            "FOURNISSEUR_LOCAL_BASE_URL": "http://localhost:8880/v1",
        })
        assert retenus == {
            "oai": {"base_url": "https://api.openai.com/v1", "api_key": "sk-1"},
            "local": {"base_url": "http://localhost:8880/v1", "api_key": ""},
        }
        assert ecartes == []

    @pytest.mark.parametrize("nom", ["openai", "mistral", "groq", "qwen", "moonshotai"])
    def test_nom_reserve_ecarte(self, nom):
        """`openai/gpt-oss-120b` est un modèle Groq : un fournisseur `openai` le détournerait."""
        retenus, ecartes = config.lire_fournisseurs_compatibles({
            "FOURNISSEURS_COMPATIBLES": nom,
            f"FOURNISSEUR_{nom.upper()}_BASE_URL": "https://x.test/v1",
        })
        assert retenus == {} and "réservé" in ecartes[0]

    def test_nom_invalide_ou_url_absente_ecartes(self):
        retenus, ecartes = config.lire_fournisseurs_compatibles(
            {"FOURNISSEURS_COMPATIBLES": "2oai,sans_url"})
        assert retenus == {}
        assert "invalide" in ecartes[0] and "BASE_URL absente" in ecartes[1]

    def test_rien_de_declare_par_defaut(self):
        assert config.lire_fournisseurs_compatibles({}) == ({}, [])

    def test_catalogue_de_voix_lu(self):
        assert config.lire_catalogue_voix("nova:Nova:female, onyx:Onyx ,:Vide,seul") == (
            ("nova", "Nova", "female"), ("onyx", "Onyx", None))
        assert config.lire_catalogue_voix("") == ()

    def test_demarrage_affiche_les_fournisseurs_jamais_la_cle(self):
        with patch.object(config, "FOURNISSEURS_COMPATIBLES", DECLARES), \
             patch.object(config, "FOURNISSEURS_ECARTES", ["openai (nom réservé)"]):
            lignes = "\n".join(config.etat_configuration())
        assert "oai → https://api.exemple.test/v1 (clé définie)" in lignes
        assert "écarté : openai (nom réservé)" in lignes
        assert "sk-test" not in lignes

    def test_env_example_documente_le_branchement(self):
        texte = (RACINE / ".env.example").read_text(encoding="utf-8")
        for cle in ("FOURNISSEURS_COMPATIBLES=", "FOURNISSEUR_OAI_BASE_URL=",
                    "FOURNISSEUR_OAI_API_KEY=", "VOIX_CATALOGUE="):
            assert cle in texte


# ═════════════════════════════════════════════════════════════════════════════
# Routage
# ═════════════════════════════════════════════════════════════════════════════
class TestRoutage:
    def test_prefixe_declare_routé_vers_son_client(self):
        with patch.dict(passerelle.FOURNISSEURS_COMPATIBLES, DECLARES, clear=True), \
             patch.dict(passerelle._clients_compatibles, {}, clear=True):
            client = passerelle._resoudre_client(CTX, "oai/gpt-4o-mini-tts")
            assert str(client.base_url).rstrip("/") == "https://api.exemple.test/v1"
            assert passerelle._resoudre_client(CTX, "oai/autre") is client   # créé une fois
            assert passerelle._modele_envoye("oai/gpt-4o-mini-tts") == "gpt-4o-mini-tts"

    def test_modele_groq_a_espace_de_noms_reste_sur_groq(self):
        with patch.dict(passerelle.FOURNISSEURS_COMPATIBLES, DECLARES, clear=True):
            assert passerelle._resoudre_client(CTX, "openai/gpt-oss-120b") is passerelle._client
            assert passerelle._modele_envoye("openai/gpt-oss-120b") == "openai/gpt-oss-120b"

    def test_prefixe_non_declare_reste_sur_groq(self):
        with patch.dict(passerelle.FOURNISSEURS_COMPATIBLES, {}, clear=True):
            assert passerelle._resoudre_client(CTX, "oai/gpt-4o-mini-tts") is passerelle._client

    def test_reasoning_effort_propre_a_groq_jamais_envoye(self):
        with patch.dict(passerelle.FOURNISSEURS_COMPATIBLES, DECLARES, clear=True):
            assert not passerelle._accepte_reasoning_effort("oai/gpt-4o")
            assert passerelle._accepte_reasoning_effort("openai/gpt-oss-120b")

    def test_hook_url_sans_v1_gemini(self):
        """Gemini sert son API compatible sous `/v1beta/openai` : l'URL déclarée est prise telle quelle."""
        requete = httpx.Request(
            "POST", "https://generativelanguage.googleapis.com/v1beta/openai/openai/v1/chat/completions")
        passerelle._reecrire_chemin_compatible(requete)
        assert requete.url.path == "/v1beta/openai/chat/completions"

    def test_hook_retire_la_route_groq(self):
        requete = httpx.Request("POST", "https://api.exemple.test/v1/openai/v1/audio/speech")
        passerelle._reecrire_chemin_compatible(requete)
        assert str(requete.url) == "https://api.exemple.test/v1/audio/speech"


# ═════════════════════════════════════════════════════════════════════════════
# Voix et dictée au format OpenAI
# ═════════════════════════════════════════════════════════════════════════════
class TestVoixOpenAI:
    def test_synthese_envoyee_au_format_openai(self, fournisseur, conso_en_base):
        reponse = passerelle.synthetiser(ctx=CTX, texte="Arrosez ce soir.", voix_id="nova")
        assert reponse.audio == MP3 and reponse.modele == "oai/gpt-4o-mini-tts"
        (requete,) = fournisseur.requetes
        assert str(requete.url) == "https://api.exemple.test/v1/audio/speech"
        assert requete.headers["authorization"] == "Bearer sk-test"
        assert json.loads(requete.content) == {
            "model": "gpt-4o-mini-tts", "input": "Arrosez ce soir.",
            "voice": "nova", "response_format": "mp3"}
        (ligne,) = _lignes_conso(conso_en_base)
        assert (ligne.appel_type, ligne.issue, ligne.tokens_in) == ("voix", "ok", 16)
        assert ligne.modele == "oai/gpt-4o-mini-tts"

    def test_voix_refusee_rend_voix_inconnue(self, fournisseur):
        fournisseur.statut_voix = 400
        fournisseur.corps_erreur = {"error": {"message": "Invalid value for 'voice'"}}
        with pytest.raises(VoixInconnueError):
            passerelle.synthetiser(ctx=CTX, texte="Bonjour", voix_id="voice_592")

    def test_panne_du_fournisseur_rend_indisponible(self, fournisseur, conso_en_base):
        fournisseur.statut_voix = 503
        with pytest.raises(LLMIndisponibleError):
            passerelle.synthetiser(ctx=CTX, texte="Bonjour", voix_id="nova")

    def test_dictee_envoyee_au_fournisseur(self, fournisseur, conso_en_base):
        reponse = passerelle.dicter(ctx=CTX, contenu=b"webm", nom_fichier="d.webm", duree_s=2.4)
        assert reponse.texte == "Trois rangs de carottes."
        (requete,) = fournisseur.requetes
        assert str(requete.url) == "https://api.exemple.test/v1/audio/transcriptions"
        assert b"gpt-4o-mini-transcribe" in requete.content
        (ligne,) = _lignes_conso(conso_en_base)
        assert (ligne.appel_type, ligne.issue, ligne.tokens_in) == ("dictee", "ok", 3)


# ═════════════════════════════════════════════════════════════════════════════
# Catalogue de voix
# ═════════════════════════════════════════════════════════════════════════════
class TestCatalogue:
    @pytest.fixture(autouse=True)
    def _caches_vides(self):
        catalogue.reinitialiser_caches()
        yield
        catalogue.reinitialiser_caches()

    def test_voix_catalogue_remplace_mistral(self):
        with patch.object(config, "VOIX_CATALOGUE", (("nova", "Nova", "female"), ("onyx", "Onyx", None))), \
             patch("llm.passerelle.lister_voix_mistral") as mistral:
            lu = catalogue.lire_catalogue()
        mistral.assert_not_called()
        assert lu.ids() == ["nova", "onyx"] and not lu.liste_de_secours

    def test_hors_mistral_sans_catalogue_seule_la_voix_par_defaut(self):
        with patch.object(config, "VOIX_CATALOGUE", ()), \
             patch.object(config, "VOIX_PAR_DEFAUT", "nova"), \
             patch.dict(passerelle.GROQ_MODELE_PAR_TYPE, {TYPE_VOIX: "oai/gpt-4o-mini-tts"}), \
             patch("llm.passerelle.lister_voix_mistral") as mistral:
            lu = catalogue.lire_catalogue()
        mistral.assert_not_called()
        assert lu.ids() == ["nova"]

    def test_mistral_sans_catalogue_inchange(self):
        with patch.object(config, "VOIX_CATALOGUE", ()), \
             patch.dict(passerelle.GROQ_MODELE_PAR_TYPE, {TYPE_VOIX: "mistral/voxtral-mini-tts-3-0"}), \
             patch("llm.passerelle.lister_voix_mistral",
                   return_value=[{"slug": "voice_592", "name": "Marie", "languages": ["fr"]}]):
            assert catalogue.lire_catalogue().ids() == ["voice_592"]

    def test_extrait_synthetise_avec_le_fournisseur(self, fournisseur, conso_en_base):
        with patch.object(config, "VOIX_CATALOGUE", (("nova", "Nova", "female"),)):
            assert catalogue.extrait(CTX, "nova") == MP3
        assert fournisseur.requetes[0].url.path == "/v1/audio/speech"


# ═════════════════════════════════════════════════════════════════════════════
# Aucune adresse de fournisseur écrite dans le code
# ═════════════════════════════════════════════════════════════════════════════
class TestAdressesEnConfiguration:
    def test_mistral_sans_adresse_indisponible(self):
        with patch("llm.passerelle.MISTRAL_API_KEY", "cle"), \
             patch("llm.passerelle.MISTRAL_BASE_URL", ""), \
             patch("llm.passerelle._client_mistral", None):
            with pytest.raises(LLMIndisponibleError, match="MISTRAL_BASE_URL"):
                passerelle._client_pour_mistral()

    def test_aucune_url_de_fournisseur_dans_le_code(self):
        for chemin in ("app/config.py", "llm/passerelle.py"):
            source = (RACINE / chemin).read_text(encoding="utf-8")
            assert "api.mistral.ai" not in source and "api.groq.com" not in source, chemin

    def test_demarrage_signale_la_cle_mistral_sans_adresse(self):
        with patch.object(config, "MISTRAL_API_KEY", "cle"), patch.object(config, "MISTRAL_BASE_URL", ""):
            lignes = "\n".join(config.etat_configuration())
        assert "adresse absente : Mistral inutilisable" in lignes


class TestValeursMalFormees:
    def test_commentaire_colle_a_la_valeur_rogne(self):
        assert config.nettoyer_modele("mistral/voxtral-mini-tts-3-0            (voix : texte → MP3)") \
            == ("mistral/voxtral-mini-tts-3-0", True)
        assert config.nettoyer_modele(" oai/gpt-4o-mini-tts ") == ("oai/gpt-4o-mini-tts", False)

    def test_aucun_modele_retenu_ne_contient_d_espace(self):
        assert all(" " not in m for m in config.GROQ_MODELE_PAR_TYPE.values())

    def test_demarrage_signale_le_rognage_et_la_voix_hors_catalogue(self):
        with patch.object(config, "MODELES_ROGNES", {"voix": "mistral/x   (voix)"}), \
             patch.object(config, "VOIX_CATALOGUE", (("nova", "Nova", None),)), \
             patch.object(config, "VOIX_PAR_DEFAUT", "voice_592"):
            lignes = "\n".join(config.etat_configuration())
        assert "rogné au premier mot" in lignes
        assert "« voice_592 » absente de VOIX_CATALOGUE" in lignes

    def test_env_example_sans_commentaire_sur_une_ligne_de_valeur(self):
        for ligne in (RACINE / ".env.example").read_text(encoding="utf-8").splitlines():
            valeur = ligne.lstrip("# ").partition("=")
            if valeur[1] and valeur[0].startswith("GROQ_MODEL"):   # un modèle n'a jamais d'espace
                # « x   # note » est un commentaire lu comme tel ; « x   (note) » fait partie de la valeur.
                assert len(valeur[2].split(" #")[0].split()) <= 1, ligne

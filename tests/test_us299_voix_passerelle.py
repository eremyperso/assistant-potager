"""
tests/test_us299_voix_passerelle.py — US-299 : dictée et voix Voxtral par la passerelle

Socle du compagnon vocal de la PWA : deux types d'appel (`dictee`, `voix`), mesurés,
journalisés, en indisponibilité typée, derrière le service `app/services/voix/`.

Aucun appel réseau : les clients Mistral et Groq sont simulés, la clé Mistral est
forcée, et les modèles des deux types sont fixés (`.env.test` ne les décide pas).
FFmpeg est simulé (`shutil.which`, `subprocess.run`).
"""
from __future__ import annotations

import base64
import inspect
import logging
import os
import pathlib
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import groq
import httpx
import pytest

from app import config
from app.services import voix
from app.services.context import TenantContext
from app.services.voix import conversion, dictee, nettoyage, synthese
from llm import passerelle
from llm.passerelle import (
    DelaiLLMDepasseError,
    FournisseurLLMIndisponibleError,
    LLMIndisponibleError,
    TYPE_DICTEE,
    TYPE_TRANSCRIPTION,
    TYPE_VOIX,
    VoixInconnueError,
)

RACINE = pathlib.Path(__file__).resolve().parent.parent
CTX = TenantContext(user_id=7, potager_id=3, role="owner")
MODELE_DICTEE = "mistral/voxtral-mini-transcribe-3-0"
MODELE_VOIX = "mistral/voxtral-mini-tts-3-0"
MP3 = b"ID3\x04\x00faux-mp3"
AUDIO_WEBM = b"\x1aE\xdf\xa3faux-webm"


# ─────────────────────────────────────────────────────────────────────────────
# Outillage
# ─────────────────────────────────────────────────────────────────────────────
def _transcription(texte: str = "J'ai semé des radis ce matin.", secondes=4.2):
    usage = {"prompt_audio_seconds": secondes} if secondes is not None else None
    return SimpleNamespace(text=texte, usage=usage)


def _speech(audio: bytes = MP3) -> dict:
    return {"audio_data": base64.b64encode(audio).decode()}


def _erreur(statut: int, body=None, chemin: str = "/v1/audio/speech"):
    requete = httpx.Request("POST", f"https://api.mistral.ai{chemin}")
    reponse = httpx.Response(statut, request=requete)
    classe = {404: groq.NotFoundError, 400: groq.BadRequestError,
              422: groq.UnprocessableEntityError}.get(statut, groq.InternalServerError)
    return classe("erreur", response=reponse, body=body)


def _timeout():
    return groq.APITimeoutError(request=httpx.Request("POST", "https://api.mistral.ai/v1/audio/speech"))


@pytest.fixture
def fournisseurs():
    """Mistral et Groq simulés ; les deux types vocaux pointés sur Voxtral."""
    faux_mistral, faux_groq = MagicMock(), MagicMock()
    faux_mistral.audio.transcriptions.create.return_value = _transcription()
    faux_mistral.post.return_value = _speech()
    faux_groq.audio.transcriptions.create.return_value = "deux kilos de tomates"
    with patch.dict(passerelle.GROQ_MODELE_PAR_TYPE,
                    {TYPE_DICTEE: MODELE_DICTEE, TYPE_VOIX: MODELE_VOIX}), \
         patch("llm.passerelle.MISTRAL_API_KEY", "cle-de-test"), \
         patch("llm.passerelle.MISTRAL_BASE_URL", "https://api.mistral.ai"), \
         patch("llm.passerelle._client_mistral", faux_mistral), \
         patch("llm.passerelle._client", faux_groq), \
         patch("llm.passerelle.time.sleep"):
        yield SimpleNamespace(mistral=faux_mistral, groq=faux_groq)


@pytest.fixture
def conso_en_base(test_db):
    """Redirige l'écriture de `conso_tokens` vers la base de test."""
    with patch("llm.passerelle.SessionLocal", lambda: test_db):
        yield test_db


def _lignes_conso(db):
    from database.models import ConsoTokens
    return db.query(ConsoTokens).order_by(ConsoTokens.id).all()


def _config_sans_variables(**forcees: str) -> dict:
    """Valeurs de `GROQ_MODELE_PAR_TYPE` lues dans un interpréteur neuf, sans fichier
    d'environnement ni variable `GROQ_MODEL*`/`VOIX_*` (les défauts du code), hormis
    celles passées en `forcees`."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("GROQ_MODEL", "VOIX_"))}
    env.update(forcees)
    env.update(APP_ENV="pytest_us299_sans_fichier", DATABASE_URL="sqlite:///:memory:",
               JWT_SECRET="test-secret-not-for-production")
    code = ("import json; from app.config import GROQ_MODELE_PAR_TYPE, GROQ_WHISPER_MODEL, "
            "VOIX_FORMATS_A_CONVERTIR as F; print(json.dumps({**GROQ_MODELE_PAR_TYPE, "
            "'_whisper': GROQ_WHISPER_MODEL, '_formats': sorted(F)}))")
    sortie = subprocess.run([sys.executable, "-c", code], cwd=RACINE, env=env,
                            capture_output=True, text=True, timeout=60, check=True)
    import json
    return json.loads(sortie.stdout.strip().splitlines()[-1])


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — type `dictee`
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1Dictee:

    def test_us299_ca1_type_dictee_declare(self):
        assert TYPE_DICTEE == "dictee"
        assert TYPE_DICTEE in passerelle.TYPES_APPEL

    def test_us299_ca1_defaut_voxtral_transcribe(self):
        valeurs = _config_sans_variables()
        assert valeurs["dictee"] == MODELE_DICTEE

    def test_us299_ca1_variable_groq_model_dictee_prise_en_compte(self):
        valeurs = _config_sans_variables(GROQ_MODEL_DICTEE="mistral/voxtral-small-transcribe-3-0")
        assert valeurs["dictee"] == "mistral/voxtral-small-transcribe-3-0"

    def test_us299_ca1_dictee_transcrite_en_francais_chez_mistral(self, fournisseurs):
        reponse = passerelle.dicter(ctx=CTX, contenu=AUDIO_WEBM, nom_fichier="dictee.webm")

        assert reponse.texte == "J'ai semé des radis ce matin."
        kwargs = fournisseurs.mistral.audio.transcriptions.create.call_args.kwargs
        assert kwargs["model"] == "voxtral-mini-transcribe-3-0", "préfixe de routage retiré"
        assert kwargs["language"] == "fr"
        assert kwargs["file"] == ("dictee.webm", AUDIO_WEBM)
        fournisseurs.groq.audio.transcriptions.create.assert_not_called()

    def test_us299_ca1_texte_rogne(self, fournisseurs):
        fournisseurs.mistral.audio.transcriptions.create.return_value = _transcription("  Bonjour  \n")
        assert passerelle.dicter(ctx=CTX, contenu=b"x", nom_fichier="a.ogg").texte == "Bonjour"

    def test_us299_ca1_dictee_sans_contexte_refusee(self, fournisseurs):
        with pytest.raises(passerelle.ContexteAppelManquantError):
            passerelle.dicter(ctx=None, contenu=b"x", nom_fichier="a.webm")
        fournisseurs.mistral.audio.transcriptions.create.assert_not_called()

    def test_us299_ca1_reponse_sans_texte_indisponible(self, fournisseurs, conso_en_base):
        fournisseurs.mistral.audio.transcriptions.create.return_value = SimpleNamespace(text=None)
        with pytest.raises(FournisseurLLMIndisponibleError):
            passerelle.dicter(ctx=CTX, contenu=b"x", nom_fichier="a.webm")
        assert _lignes_conso(conso_en_base)[-1].issue == "erreur"


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — type `voix`, voix inconnue distincte d'une indisponibilité
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2Voix:

    def test_us299_ca2_type_voix_et_defaut(self):
        assert TYPE_VOIX in passerelle.TYPES_APPEL
        assert _config_sans_variables()["voix"] == MODELE_VOIX

    def test_us299_ca2_mp3_rendu_par_appel_dedie(self, fournisseurs):
        reponse = passerelle.synthetiser(ctx=CTX, texte="Bonjour", voix_id="voice_592")

        assert reponse.audio == MP3
        assert reponse.format_audio == "mp3"
        chemin = fournisseurs.mistral.post.call_args.args[0]
        corps = fournisseurs.mistral.post.call_args.kwargs["body"]
        assert chemin == "/v1/audio/speech"
        assert corps == {"model": "voxtral-mini-tts-3-0", "input": "Bonjour",
                         "voice_id": "voice_592", "response_format": "mp3"}

    def test_us299_ca2_audio_absent_du_repr(self, fournisseurs):
        reponse = passerelle.synthetiser(ctx=CTX, texte="Bonjour", voix_id="voice_592")
        assert "faux-mp3" not in repr(reponse)

    def test_us299_ca2_voix_inconnue_erreur_typee_distincte(self, fournisseurs, conso_en_base):
        fournisseurs.mistral.post.side_effect = _erreur(
            404, {"object": "error", "message": "Voice not found", "type": "invalid_voice",
                  "code": "3051"})

        with pytest.raises(VoixInconnueError) as erreur:
            passerelle.synthetiser(ctx=CTX, texte="Bonjour", voix_id="voice_inexistante")

        assert not isinstance(erreur.value, LLMIndisponibleError), \
            "une voix inconnue n'est pas une indisponibilité"
        assert fournisseurs.mistral.post.call_count == 1, "un 404 ne se rejoue pas"
        assert _lignes_conso(conso_en_base)[-1].issue == "voix_inconnue"

    def test_us299_ca2_autre_404_reste_une_indisponibilite(self, fournisseurs):
        fournisseurs.mistral.post.side_effect = _erreur(
            404, {"message": "Model not found", "type": "invalid_model"})
        with pytest.raises(FournisseurLLMIndisponibleError):
            passerelle.synthetiser(ctx=CTX, texte="Bonjour", voix_id="voice_592")

    def test_us299_ca2_voix_refusee_par_le_modele_reconnue(self, fournisseurs):
        """US-298 : `-2603` et `-latest` refusent les voix 3 (code 3051)."""
        fournisseurs.mistral.post.side_effect = _erreur(400, {"code": 3051, "message": "x"})
        with pytest.raises(VoixInconnueError):
            passerelle.synthetiser(ctx=CTX, texte="Bonjour", voix_id="voice_592")

    def test_us299_ca2_texte_vide_refuse_sans_appel(self, fournisseurs):
        with pytest.raises(ValueError):
            passerelle.synthetiser(ctx=CTX, texte="   ", voix_id="voice_592")
        fournisseurs.mistral.post.assert_not_called()

    def test_us299_ca2_format_inconnu_refuse(self, fournisseurs):
        with pytest.raises(ValueError):
            passerelle.synthetiser(ctx=CTX, texte="Bonjour", voix_id="v", format_audio="aiff")

    def test_us299_ca2_reponse_sans_audio_indisponible(self, fournisseurs, conso_en_base):
        fournisseurs.mistral.post.return_value = {"audio_data": ""}
        with pytest.raises(FournisseurLLMIndisponibleError):
            passerelle.synthetiser(ctx=CTX, texte="Bonjour", voix_id="voice_592")
        assert _lignes_conso(conso_en_base)[-1].issue == "erreur"

    def test_us299_ca2_base64_invalide_indisponible(self, fournisseurs):
        fournisseurs.mistral.post.return_value = {"audio_data": "pas du base64 !!"}
        with pytest.raises(FournisseurLLMIndisponibleError):
            passerelle.synthetiser(ctx=CTX, texte="Bonjour", voix_id="voice_592")

    def test_us299_ca2_modele_non_mistral_indisponible(self, fournisseurs, conso_en_base):
        with patch.dict(passerelle.GROQ_MODELE_PAR_TYPE, {TYPE_VOIX: "playai-tts"}):
            with pytest.raises(FournisseurLLMIndisponibleError):
                passerelle.synthetiser(ctx=CTX, texte="Bonjour", voix_id="voice_592")
        fournisseurs.groq.post.assert_not_called()
        assert _lignes_conso(conso_en_base)[-1].issue == "erreur"


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — mesure et journal
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3Mesure:

    def test_us299_ca3_dictee_comptee_en_secondes(self, fournisseurs, conso_en_base):
        passerelle.dicter(ctx=CTX, contenu=AUDIO_WEBM, nom_fichier="dictee.webm")

        ligne = _lignes_conso(conso_en_base)[-1]
        assert ligne.appel_type == "dictee"
        assert ligne.modele == MODELE_DICTEE
        assert ligne.tokens_in == 5, "4,2 s d'audio arrondies à la seconde supérieure"
        assert ligne.tokens_out == 0
        assert ligne.issue == "ok"
        assert ligne.latence_ms >= 0
        assert ligne.potager_id == 3 and ligne.user_id == 7

    def test_us299_ca3_duree_fournie_par_l_appelant_en_repli(self, fournisseurs, conso_en_base):
        fournisseurs.mistral.audio.transcriptions.create.return_value = _transcription(secondes=None)
        reponse = passerelle.dicter(ctx=CTX, contenu=b"x", nom_fichier="a.webm", duree_s=7.0)
        assert reponse.duree_audio_s == 7
        assert _lignes_conso(conso_en_base)[-1].tokens_in == 7

    def test_us299_ca3_duree_inconnue_vaut_zero(self, fournisseurs):
        fournisseurs.mistral.audio.transcriptions.create.return_value = _transcription(secondes=None)
        assert passerelle.dicter(ctx=CTX, contenu=b"x", nom_fichier="a.webm").duree_audio_s == 0

    def test_us299_ca3_voix_comptee_en_caracteres(self, fournisseurs, conso_en_base):
        passerelle.synthetiser(ctx=CTX, texte="Bonjour, je suis Gaston", voix_id="voice_592")

        ligne = _lignes_conso(conso_en_base)[-1]
        assert ligne.appel_type == "voix"
        assert ligne.modele == MODELE_VOIX
        assert ligne.tokens_in == 23
        assert ligne.issue == "ok"

    def test_us299_ca3_echec_compte_aussi(self, fournisseurs, conso_en_base):
        fournisseurs.mistral.post.side_effect = _timeout()
        with pytest.raises(DelaiLLMDepasseError):
            passerelle.synthetiser(ctx=CTX, texte="Bonjour", voix_id="voice_592")
        ligne = _lignes_conso(conso_en_base)[-1]
        assert (ligne.appel_type, ligne.issue) == ("voix", "delai")

    def test_us299_ca3_journal_sans_contenu(self, fournisseurs, caplog):
        caplog.set_level(logging.INFO, logger="potager")
        with patch("llm.passerelle._enregistrer_conso"):
            passerelle.synthetiser(ctx=CTX, texte="Mon secret de jardin", voix_id="voice_592")
            fournisseurs.mistral.audio.transcriptions.create.return_value = \
                _transcription("Phrase privée dictée")
            passerelle.dicter(ctx=CTX, contenu=b"x", nom_fichier="a.webm")

        journal = caplog.text
        assert "voix" in journal and "dictee" in journal
        assert "20 caractères" in journal and "5 s d'audio" in journal
        assert "secret" not in journal and "privée" not in journal


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — indisponibilité typée, jamais une exception brute
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4Indisponibilite:

    @pytest.mark.parametrize("fonction", ["dicter", "synthetiser"])
    def test_us299_ca4_sans_cle_mistral_indisponibilite_comptee(self, fournisseurs, conso_en_base,
                                                                fonction):
        with patch("llm.passerelle.MISTRAL_API_KEY", ""):
            with pytest.raises(LLMIndisponibleError):
                if fonction == "dicter":
                    passerelle.dicter(ctx=CTX, contenu=b"x", nom_fichier="a.webm")
                else:
                    passerelle.synthetiser(ctx=CTX, texte="Bonjour", voix_id="voice_592")
        fournisseurs.mistral.audio.transcriptions.create.assert_not_called()
        fournisseurs.mistral.post.assert_not_called()
        ligne = _lignes_conso(conso_en_base)[-1]
        assert ligne.issue == "erreur"
        assert ligne.appel_type == ("dictee" if fonction == "dicter" else "voix")

    def test_us299_ca4_delai_depasse_type(self, fournisseurs):
        fournisseurs.mistral.audio.transcriptions.create.side_effect = _timeout()
        with pytest.raises(DelaiLLMDepasseError):
            passerelle.dicter(ctx=CTX, contenu=b"x", nom_fichier="a.webm")

    def test_us299_ca4_erreur_5xx_rejouee_une_fois_puis_typee(self, fournisseurs):
        fournisseurs.mistral.post.side_effect = _erreur(503)
        with pytest.raises(FournisseurLLMIndisponibleError):
            passerelle.synthetiser(ctx=CTX, texte="Bonjour", voix_id="voice_592")
        assert fournisseurs.mistral.post.call_count == 2

    def test_us299_ca4_service_rend_l_indisponibilite(self, fournisseurs):
        fournisseurs.mistral.audio.transcriptions.create.side_effect = _erreur(
            502, chemin="/v1/audio/transcriptions")
        with pytest.raises(voix.LLMIndisponibleError):
            voix.dicter(CTX, AUDIO_WEBM, "dictee.webm")

    def test_us299_ca4_message_pwa(self):
        assert "voix est indisponible" in voix.MESSAGE_VOIX_INDISPONIBLE
        assert "écrivez votre message" in voix.MESSAGE_VOIX_INDISPONIBLE


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — service `app/services/voix/`, nettoyage repris de utils/tts.py
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5Service:

    def test_us299_ca5_texte_nettoye_avant_synthese(self, fournisseurs):
        voix.synthetiser(CTX, "## **Bonjour** 🌱 voir [la fiche](https://x.fr/f) ou https://a.b/c",
                         voix_id="voice_3137")
        corps = fournisseurs.mistral.post.call_args.kwargs["body"]
        assert corps["input"] == "Bonjour voir la fiche ou"
        assert corps["voice_id"] == "voice_3137"

    def test_us299_ca5_voix_par_defaut_marie(self, fournisseurs):
        voix.synthetiser(CTX, "Bonjour")
        assert fournisseurs.mistral.post.call_args.kwargs["body"]["voice_id"] == "voice_592"
        assert voix.VOIX_PAR_DEFAUT == "voice_592"

    def test_us299_ca5_rien_a_dire_sans_appel(self, fournisseurs):
        with pytest.raises(ValueError):
            voix.synthetiser(CTX, "🌱 🍅 https://x.fr")
        fournisseurs.mistral.post.assert_not_called()

    @pytest.mark.parametrize("brut, attendu", [
        ("**gras** et _italique_ et `code`", "gras et italique et code"),
        ("# Titre\nTexte", "Titre Texte"),
        ("Arrose 💧 demain.", "Arrose demain."),
        ("", ""),
    ])
    def test_us299_ca5_nettoyage(self, brut, attendu):
        assert voix.nettoyer_pour_voix(brut) == attendu

    def test_us299_ca5_nettoyage_identique_a_utils_tts(self):
        """Mêmes règles que `utils.tts._strip_markdown` sur un texte sans lien nu."""
        from utils import tts
        texte = "### **Récolte** du _jour_ 🍅 : voir [la fiche](https://x.fr) `ok`"
        assert voix.nettoyer_pour_voix(texte) == tts._strip_markdown(texte)

    def test_us299_ca5_service_sans_dependance_a_utils_tts(self):
        for module in (voix, conversion, dictee, nettoyage, synthese):
            assert "utils.tts" not in inspect.getsource(module)

    def test_us299_ca5_aucune_route_n_appelle_la_passerelle_vocale(self):
        """Les routes passeront par `app.services.voix`, jamais par la passerelle."""
        for dossier in ("app/api", "app/bot"):
            for fichier in (RACINE / dossier).rglob("*.py"):
                source = fichier.read_text(encoding="utf-8")
                assert "passerelle.dicter" not in source, fichier
                assert "passerelle.synthetiser" not in source, fichier


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — conversion FFmpeg d'un format refusé
# ═════════════════════════════════════════════════════════════════════════════
def _faux_ffmpeg(code: int = 0, sortie: bytes = b"RIFF....WAVEfaux"):
    """Simule `subprocess.run(["ffmpeg", ..., cible])` : écrit la cible si code 0."""
    def _run(commande, **_kwargs):
        if code == 0:
            pathlib.Path(commande[-1]).write_bytes(sortie)
        return SimpleNamespace(returncode=code, stdout=b"", stderr=b"")
    return _run


class TestCA6Conversion:

    def test_us299_ca6_aucun_format_converti_par_defaut(self):
        assert _config_sans_variables()["_formats"] == []

    def test_us299_ca6_variable_lue(self):
        assert _config_sans_variables(VOIX_FORMATS_A_CONVERTIR=" MP4, .m4a ,")["_formats"] == ["m4a", "mp4"]

    def test_us299_ca6_format_accepte_envoye_tel_quel(self, fournisseurs):
        with patch.object(config, "VOIX_FORMATS_A_CONVERTIR", frozenset({"mp4"})), \
             patch("app.services.voix.conversion.subprocess.run") as run:
            voix.dicter(CTX, AUDIO_WEBM, "dictee.webm")
        run.assert_not_called()
        kwargs = fournisseurs.mistral.audio.transcriptions.create.call_args.kwargs
        assert kwargs["file"] == ("dictee.webm", AUDIO_WEBM)

    def test_us299_ca6_format_refuse_converti_en_wav(self, fournisseurs):
        with patch.object(config, "VOIX_FORMATS_A_CONVERTIR", frozenset({"mp4"})), \
             patch("app.services.voix.conversion.shutil.which", return_value="/usr/bin/ffmpeg"), \
             patch("app.services.voix.conversion.subprocess.run",
                   side_effect=_faux_ffmpeg()) as run:
            voix.dicter(CTX, b"faux-mp4", "dictee.mp4")

        commande = run.call_args.args[0]
        assert commande[0] == "ffmpeg" and "-ar" in commande and commande[-1].endswith(".wav")
        nom, contenu = fournisseurs.mistral.audio.transcriptions.create.call_args.kwargs["file"]
        assert (nom, contenu) == ("dictee.wav", b"RIFF....WAVEfaux")

    def test_us299_ca6_format_deduit_du_type_mime(self, fournisseurs):
        with patch.object(config, "VOIX_FORMATS_A_CONVERTIR", frozenset({"mp4"})), \
             patch("app.services.voix.conversion.shutil.which", return_value="/usr/bin/ffmpeg"), \
             patch("app.services.voix.conversion.subprocess.run", side_effect=_faux_ffmpeg()) as run:
            voix.dicter(CTX, b"faux-mp4", "blob", type_mime="audio/mp4;codecs=mp4a.40.2")
        run.assert_called_once()

    def test_us299_ca6_sans_ffmpeg_erreur_typee_qui_nomme_le_format(self, fournisseurs):
        with patch.object(config, "VOIX_FORMATS_A_CONVERTIR", frozenset({"mp4"})), \
             patch("app.services.voix.conversion.shutil.which", return_value=None):
            with pytest.raises(voix.FormatAudioNonConvertibleError) as erreur:
                voix.dicter(CTX, b"faux-mp4", "dictee.mp4")

        assert erreur.value.format_audio == "mp4"
        assert "mp4" in str(erreur.value) and "FFmpeg" in str(erreur.value)
        fournisseurs.mistral.audio.transcriptions.create.assert_not_called()

    def test_us299_ca6_ffmpeg_en_echec_erreur_typee(self, fournisseurs):
        with patch.object(config, "VOIX_FORMATS_A_CONVERTIR", frozenset({"mp4"})), \
             patch("app.services.voix.conversion.shutil.which", return_value="/usr/bin/ffmpeg"), \
             patch("app.services.voix.conversion.subprocess.run", side_effect=_faux_ffmpeg(code=1)):
            with pytest.raises(voix.FormatAudioNonConvertibleError):
                voix.dicter(CTX, b"faux-mp4", "dictee.mp4")

    def test_us299_ca6_ffmpeg_trop_long_erreur_typee(self, fournisseurs):
        with patch.object(config, "VOIX_FORMATS_A_CONVERTIR", frozenset({"mp4"})), \
             patch("app.services.voix.conversion.shutil.which", return_value="/usr/bin/ffmpeg"), \
             patch("app.services.voix.conversion.subprocess.run",
                   side_effect=subprocess.TimeoutExpired("ffmpeg", 30)):
            with pytest.raises(voix.FormatAudioNonConvertibleError):
                voix.dicter(CTX, b"faux-mp4", "dictee.mp4")

    def test_us299_ca6_runbook_mentionne_ffmpeg_pour_la_dictee(self):
        runbook = (RACINE / "docs/RUNBOOK/RUNBOOK_DEPLOIEMENT_PRODUCTION.md").read_text(encoding="utf-8")
        assert "VOIX_FORMATS_A_CONVERTIR" in runbook
        assert "US-299" in runbook


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — l'audio n'est jamais gardé
# ═════════════════════════════════════════════════════════════════════════════
class TestCA7AudioJete:

    @pytest.fixture
    def dossiers_crees(self, tmp_path, monkeypatch):
        crees: list[pathlib.Path] = []
        vrai_mkdtemp = conversion.tempfile.mkdtemp

        def _mkdtemp(**kwargs):
            chemin = pathlib.Path(vrai_mkdtemp(dir=tmp_path, **kwargs))
            crees.append(chemin)
            return str(chemin)

        monkeypatch.setattr(conversion.tempfile, "mkdtemp", _mkdtemp)
        return crees

    @pytest.mark.parametrize("code", [0, 1])
    def test_us299_ca7_fichier_temporaire_supprime(self, fournisseurs, dossiers_crees, code):
        with patch.object(config, "VOIX_FORMATS_A_CONVERTIR", frozenset({"mp4"})), \
             patch("app.services.voix.conversion.shutil.which", return_value="/usr/bin/ffmpeg"), \
             patch("app.services.voix.conversion.subprocess.run", side_effect=_faux_ffmpeg(code=code)):
            try:
                voix.dicter(CTX, b"faux-mp4", "dictee.mp4")
            except voix.FormatAudioNonConvertibleError:
                assert code == 1

        assert len(dossiers_crees) == 1
        assert not dossiers_crees[0].exists(), "le dossier de conversion doit disparaître"

    def test_us299_ca7_fichier_supprime_si_le_fournisseur_echoue(self, fournisseurs, dossiers_crees):
        fournisseurs.mistral.audio.transcriptions.create.side_effect = _timeout()
        with patch.object(config, "VOIX_FORMATS_A_CONVERTIR", frozenset({"mp4"})), \
             patch("app.services.voix.conversion.shutil.which", return_value="/usr/bin/ffmpeg"), \
             patch("app.services.voix.conversion.subprocess.run", side_effect=_faux_ffmpeg()):
            with pytest.raises(DelaiLLMDepasseError):
                voix.dicter(CTX, b"faux-mp4", "dictee.mp4")
        assert dossiers_crees and not any(d.exists() for d in dossiers_crees)

    def test_us299_ca7_sans_conversion_aucun_fichier(self, fournisseurs, dossiers_crees):
        voix.dicter(CTX, AUDIO_WEBM, "dictee.webm")
        assert dossiers_crees == []

    def test_us299_ca7_rien_d_audio_en_base(self, fournisseurs, conso_en_base):
        voix.dicter(CTX, AUDIO_WEBM, "dictee.webm")
        voix.synthetiser(CTX, "Bonjour")

        from database.models import Base
        for table in Base.metadata.tables.values():
            for ligne in conso_en_base.execute(table.select()).fetchall():
                for valeur in ligne:
                    assert not isinstance(valeur, (bytes, bytearray, memoryview)), table.name
        assert [l.appel_type for l in _lignes_conso(conso_en_base)] == ["dictee", "voix"]

    def test_us299_ca7_dictee_vide_refusee(self, fournisseurs):
        with pytest.raises(ValueError):
            voix.dicter(CTX, b"", "dictee.webm")
        fournisseurs.mistral.audio.transcriptions.create.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — Telegram (Whisper) et gTTS inchangés
# ═════════════════════════════════════════════════════════════════════════════
class TestCA8TelegramInchange:

    def test_us299_ca8_transcription_garde_whisper_par_defaut(self):
        valeurs = _config_sans_variables()
        assert valeurs["transcription"] == valeurs["_whisper"]
        assert valeurs["transcription"] != valeurs["dictee"]

    def test_us299_ca8_transcription_reste_chez_groq(self, fournisseurs, tmp_path):
        fichier = tmp_path / "message.ogg"
        fichier.write_bytes(b"faux-audio")
        with patch.dict(passerelle.GROQ_MODELE_PAR_TYPE, {TYPE_TRANSCRIPTION: "whisper-large-v3"}):
            reponse = passerelle.transcrire(ctx=CTX, chemin_fichier=str(fichier))

        assert reponse.texte == "deux kilos de tomates"
        assert reponse.appel_type == "transcription"
        fournisseurs.groq.audio.transcriptions.create.assert_called_once()
        assert fournisseurs.groq.audio.transcriptions.create.call_args.kwargs["response_format"] == "text"
        fournisseurs.mistral.audio.transcriptions.create.assert_not_called()

    def test_us299_ca8_transcription_telegram_fonctionne_sans_cle_mistral(self, fournisseurs, tmp_path):
        """Gherkin : sans MISTRAL_API_KEY, la transcription Telegram fonctionne toujours."""
        fichier = tmp_path / "message.ogg"
        fichier.write_bytes(b"faux-audio")
        with patch("llm.passerelle.MISTRAL_API_KEY", ""), \
             patch.dict(passerelle.GROQ_MODELE_PAR_TYPE, {TYPE_TRANSCRIPTION: "whisper-large-v3"}):
            assert passerelle.transcrire(ctx=CTX, chemin_fichier=str(fichier)).texte

    def test_us299_ca8_utils_tts_garde_gtts(self):
        from utils import tts
        assert tts.gTTS.__module__.startswith("gtts")
        for nom in ("_strip_markdown", "_truncate_for_tts", "set_tts_enabled", "is_tts_enabled",
                    "send_voice_reply"):
            assert hasattr(tts, nom), nom
        assert "app.services.voix" not in inspect.getsource(tts)
        assert "passerelle" not in inspect.getsource(tts)


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — documentation de la configuration
# ═════════════════════════════════════════════════════════════════════════════
class TestCA9Configuration:

    def test_us299_ca9_env_example_documente_en_commentaire(self):
        lignes = (RACINE / ".env.example").read_text(encoding="utf-8").splitlines()
        for nom in ("GROQ_MODEL_DICTEE", "GROQ_MODEL_VOIX", "VOIX_FORMATS_A_CONVERTIR"):
            concernees = [l for l in lignes if f"{nom}=" in l]
            assert concernees, nom
            assert all(l.lstrip().startswith("#") for l in concernees), f"{nom} doit rester commenté"

    def test_us299_ca9_affichage_au_demarrage(self):
        etat = "\n".join(config.etat_configuration())
        assert "GROQ_MODEL_DICTEE" in etat
        assert "GROQ_MODEL_VOIX" in etat
        assert "VOIX_FORMATS_A_CONVERTIR" in etat


# ═════════════════════════════════════════════════════════════════════════════
# CA10 — registre RGPD
# ═════════════════════════════════════════════════════════════════════════════
def test_us299_ca10_registre_rgpd():
    fiche = (RACINE / "docs/RGPD/RGPD_COMPAGNON_VOCAL.md").read_text(encoding="utf-8")
    assert "Mistral AI" in fiche
    assert "jamais écrit dans notre base" in fiche
    assert "non confirmé" in fiche
    assert "Europe" in fiche


# ═════════════════════════════════════════════════════════════════════════════
# Scénario Gherkin
# ═════════════════════════════════════════════════════════════════════════════
def test_us299_gherkin_synthese_puis_dictee_sans_cle(fournisseurs, conso_en_base, tmp_path):
    # Given GROQ_MODEL_VOIX vaut "mistral/voxtral-mini-tts-3-0"
    assert passerelle.modele_pour(TYPE_VOIX) == "mistral/voxtral-mini-tts-3-0"
    # When le service synthétise "Bonjour, je suis Gaston" avec la voix "voice_592"
    reponse = voix.synthetiser(CTX, "Bonjour, je suis Gaston", voix_id="voice_592")
    # Then il rend un MP3 non vide
    assert reponse.audio and reponse.format_audio == "mp3"
    # And une ligne conso_tokens de type "voix" porte 23 caractères et l'issue "ok"
    ligne = _lignes_conso(conso_en_base)[-1]
    assert (ligne.appel_type, ligne.tokens_in, ligne.issue) == ("voix", 23, "ok")

    # Given MISTRAL_API_KEY est vide
    with patch("llm.passerelle.MISTRAL_API_KEY", ""):
        # When le service tente une dictée / Then indisponibilité typée de la passerelle
        with pytest.raises(LLMIndisponibleError):
            voix.dicter(CTX, AUDIO_WEBM, "dictee.webm")
        # And la transcription Telegram par Groq Whisper fonctionne toujours
        fichier = tmp_path / "message.ogg"
        fichier.write_bytes(b"faux-audio")
        with patch.dict(passerelle.GROQ_MODELE_PAR_TYPE, {TYPE_TRANSCRIPTION: "whisper-large-v3"}):
            assert passerelle.transcrire(ctx=CTX, chemin_fichier=str(fichier)).texte

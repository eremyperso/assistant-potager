"""
tests/test_us302_dictee_compagnon.py — US-302 : dicter une phrase au compagnon depuis la PWA

Côté serveur : `POST /compagnon/voix/transcrire` (multipart → `{ texte }`), ses refus
(403 sans mode vocal, 413 trop long ou trop lourd, 422 texte trop long, 429 plafond du jour,
503 Voxtral indisponible) et l'absence de tout envoi au compagnon depuis cette route : la PWA
envoie la phrase elle-même par `/compagnon/messages` (D4), donc par la carte de confirmation.
La logique du bouton (états, format, messages) est testée par `node --test`
(`frontend/src/lib/voix.test.js`). Aucun appel réseau : la dictée est simulée.
"""
from __future__ import annotations

import pathlib
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app import config
from app.services import voix
from app.services.context import TenantContext
from app.services.voix import preferences as prefs
from app.services.voix import transcription as dictee
from database.models import ConsoTokens, User
from llm.passerelle import LLMIndisponibleError, ReponseDictee

RACINE = pathlib.Path(__file__).resolve().parent.parent
CTX = TenantContext(user_id=1, potager_id=1, role="owner")
CTX_AUTRE = TenantContext(user_id=2, potager_id=1, role="editor")
AUDIO = b"\x1aE\xdf\xa3faux-webm-opus"
PHRASE = "j'ai semé 30 graines de radis sur la planche 2"


def _reponse(texte: str = PHRASE, duree: int = 4) -> ReponseDictee:
    return ReponseDictee(texte=texte, modele="mistral/voxtral-mini-transcribe-3-0",
                         duree_audio_s=duree, latence_ms=120)


@pytest.fixture(autouse=True)
def _jardiniers(test_db):
    test_db.add_all([User(id=1, email="un@exemple.fr"), User(id=2, email="deux@exemple.fr")])
    test_db.commit()


@pytest.fixture(autouse=True)
def _catalogue_hors_ligne():
    """La lecture des préférences consulte le catalogue des voix : jamais l'API réelle."""
    with patch("llm.passerelle.lister_voix_mistral", return_value=[]):
        yield


@pytest.fixture
def mode_vocal(test_db):
    prefs.enregistrer(test_db, CTX, mode_vocal=True)


@pytest.fixture
def voxtral():
    with patch("app.services.voix.transcription.dicter", return_value=_reponse()) as appel:
        yield appel


@pytest.fixture
def client(test_engine):
    from app.api import main
    fabrique = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    main.app.dependency_overrides[main.get_current_user_ctx] = lambda: CTX
    with patch.object(main, "SessionLocal", fabrique):
        with TestClient(main.app) as c:
            yield c
    main.app.dependency_overrides.pop(main.get_current_user_ctx, None)


def _envoyer(client, contenu: bytes = AUDIO, nom: str = "dictee.webm",
             type_mime: str = "audio/webm;codecs=opus", duree_s: float | None = 4.2):
    donnees = {} if duree_s is None else {"duree_s": str(duree_s)}
    return client.post("/compagnon/voix/transcrire",
                       files={"audio": (nom, contenu, type_mime)}, data=donnees)


def _dictees(test_db, n: int, user_id: int = 1, jour: date | None = None, issue: str = "ok",
             appel_type: str = "dictee") -> None:
    for _ in range(n):
        test_db.add(ConsoTokens(potager_id=1, user_id=user_id, date=jour or date.today(),
                                appel_type=appel_type, modele="m", tokens_in=4, issue=issue))
    test_db.commit()


# ═════════════════════════════════════════════════════════════════════════════
# CA3 / CA5 / CA12 — réglages
# ═════════════════════════════════════════════════════════════════════════════
class TestReglages:

    def test_us302_defauts(self):
        assert config.VOIX_DICTEE_DUREE_MAX_S == 60
        assert config.VOIX_PLAFOND_DICTEES_JOUR == 100
        assert config.VOIX_DICTEE_TAILLE_MAX_KO > 0

    def test_us302_valeur_invalide_rend_le_defaut(self, monkeypatch):
        monkeypatch.setenv("ESSAI_US302", "pas-un-nombre")
        assert config._entier_positif("ESSAI_US302", 60) == 60
        monkeypatch.setenv("ESSAI_US302", "-5")
        assert config._entier_positif("ESSAI_US302", 60) == 60
        monkeypatch.setenv("ESSAI_US302", "45")
        assert config._entier_positif("ESSAI_US302", 60) == 45

    def test_us302_ca3_la_pwa_lit_la_duree_maximale(self, client):
        r = client.get("/compagnon/voix/preferences")
        assert r.status_code == 200
        assert r.json()["dictee_duree_max_s"] == config.VOIX_DICTEE_DUREE_MAX_S

    def test_us302_reglages_documentes(self):
        exemple = (RACINE / ".env.example").read_text(encoding="utf-8")
        for nom in ("VOIX_DICTEE_DUREE_MAX_S", "VOIX_DICTEE_TAILLE_MAX_KO", "VOIX_PLAFOND_DICTEES_JOUR"):
            assert nom in exemple


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — la route de transcription
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5Transcrire:

    def test_us302_ca5_rend_le_texte(self, client, mode_vocal, voxtral):
        r = _envoyer(client)
        assert r.status_code == 200
        assert r.json() == {"texte": PHRASE}

    def test_us302_ca5_transmet_fichier_format_et_duree(self, client, mode_vocal, voxtral):
        _envoyer(client, nom="dictee.mp4", type_mime="audio/mp4", duree_s=12.5)
        ctx, contenu, nom, type_mime, duree = voxtral.call_args.args
        assert (ctx.user_id, contenu, nom, type_mime, duree) == (1, AUDIO, "dictee.mp4", "audio/mp4", 12.5)

    def test_us302_ca5_sans_duree_accepte(self, client, mode_vocal, voxtral):
        assert _envoyer(client, duree_s=None).status_code == 200

    def test_us302_ca5_mode_vocal_eteint_403(self, client, voxtral):
        r = _envoyer(client)
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "mode_vocal_eteint"
        voxtral.assert_not_called()

    def test_us302_ca5_mode_vocal_d_un_autre_jardinier_ne_compte_pas(self, client, test_db, voxtral):
        prefs.enregistrer(test_db, CTX_AUTRE, mode_vocal=True)
        assert _envoyer(client).status_code == 403

    def test_us302_ca5_fichier_trop_lourd_413(self, client, mode_vocal, voxtral, monkeypatch):
        monkeypatch.setattr(config, "VOIX_DICTEE_TAILLE_MAX_KO", 1)
        r = _envoyer(client, contenu=b"x" * 2048)
        assert r.status_code == 413
        assert r.json()["detail"]["code"] == "dictee_trop_longue"
        voxtral.assert_not_called()

    def test_us302_ca5_dictee_trop_longue_413(self, client, mode_vocal, voxtral):
        r = _envoyer(client, duree_s=config.VOIX_DICTEE_DUREE_MAX_S + 30)
        assert r.status_code == 413
        voxtral.assert_not_called()

    def test_us302_ca3_arret_pile_a_la_duree_max_accepte(self, client, mode_vocal, voxtral):
        """La PWA s'arrête à 60 s : l'enregistrement arrive avec quelques dixièmes de plus."""
        assert _envoyer(client, duree_s=config.VOIX_DICTEE_DUREE_MAX_S + 0.6).status_code == 200

    def test_us302_ca5_fichier_vide_422(self, client, mode_vocal):
        r = _envoyer(client, contenu=b"")
        assert r.status_code == 422
        assert r.json()["detail"]["code"] == "dictee_vide"

    def test_us302_ca5_route_sans_logique(self):
        source = (RACINE / "app" / "api" / "main.py").read_text(encoding="utf-8")
        debut = source.index('@app.post("/compagnon/voix/transcrire")')
        route = source[debut:source.index("\n\n\n", debut)]
        assert "svc_dictee.transcrire(" in route
        assert "db.query" not in route and "passerelle" not in route


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — la phrase part par le chemin d'une phrase tapée, jamais d'ici
# ═════════════════════════════════════════════════════════════════════════════
class TestCA6EnvoiParLaPwa:

    def test_us302_ca6_la_transcription_n_envoie_rien_au_compagnon(self, client, mode_vocal, voxtral):
        with patch("app.services.compagnon.echange_pwa.repondre") as repondre:
            assert _envoyer(client).status_code == 200
        repondre.assert_not_called()

    def test_us302_ca6_le_service_n_ecrit_aucun_geste(self):
        source = (RACINE / "app" / "services" / "voix" / "transcription.py").read_text(encoding="utf-8")
        for interdit in ("evenements", "orchestrateur", "echange_pwa", "gestes"):
            assert f"import {interdit}" not in source and f".{interdit} import" not in source


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — transcription vide, transcription trop longue
# ═════════════════════════════════════════════════════════════════════════════
class TestCA7Longueurs:

    def test_us302_ca7_rien_entendu_rend_un_texte_vide(self, client, mode_vocal):
        with patch("app.services.voix.transcription.dicter", return_value=_reponse("   ")):
            r = _envoyer(client)
        assert r.status_code == 200
        assert r.json() == {"texte": ""}

    def test_us302_ca7_plus_de_1000_caracteres_refuse(self, client, mode_vocal):
        with patch("app.services.voix.transcription.dicter", return_value=_reponse("a" * 1001)):
            r = _envoyer(client)
        assert r.status_code == 422
        assert r.json()["detail"] == {"code": "message_trop_long", "message": "Message trop long, découpez-le."}

    def test_us302_ca7_1000_caracteres_acceptes(self, client, mode_vocal):
        with patch("app.services.voix.transcription.dicter", return_value=_reponse("a" * 1000)):
            assert _envoyer(client).status_code == 200


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — Voxtral indisponible
# ═════════════════════════════════════════════════════════════════════════════
class TestCA9Indisponible:

    @pytest.mark.parametrize("erreur", [
        LLMIndisponibleError("délai"),
        voix.FormatAudioNonConvertibleError("mp4", "FFmpeg absent"),
    ])
    def test_us302_ca9_503_avec_le_message_de_repli(self, client, mode_vocal, erreur):
        with patch("app.services.voix.transcription.dicter", side_effect=erreur):
            r = _envoyer(client)
        assert r.status_code == 503
        assert r.json()["detail"]["message"] == \
            "La dictée est indisponible pour le moment, écrivez votre message."


# ═════════════════════════════════════════════════════════════════════════════
# CA12 — plafond de dictées par jour
# ═════════════════════════════════════════════════════════════════════════════
class TestCA12Plafond:

    def test_us302_ca12_plafond_atteint_429(self, client, test_db, mode_vocal, voxtral, monkeypatch):
        monkeypatch.setattr(config, "VOIX_PLAFOND_DICTEES_JOUR", 3)
        _dictees(test_db, 3)
        r = _envoyer(client)
        assert r.status_code == 429
        assert r.json()["detail"]["message"] == "Limite de dictées du jour atteinte."
        voxtral.assert_not_called()

    def test_us302_ca12_sous_le_plafond_passe(self, client, test_db, mode_vocal, voxtral, monkeypatch):
        monkeypatch.setattr(config, "VOIX_PLAFOND_DICTEES_JOUR", 3)
        _dictees(test_db, 2)
        assert _envoyer(client).status_code == 200

    def test_us302_ca12_ne_compte_que_les_dictees_reussies_du_jardinier_aujourd_hui(self, test_db):
        _dictees(test_db, 2)
        _dictees(test_db, 4, user_id=2)                                   # un autre jardinier
        _dictees(test_db, 4, jour=date.today() - timedelta(days=1))       # hier
        _dictees(test_db, 4, issue="erreur")                              # échecs non facturés
        _dictees(test_db, 4, appel_type="voix")                           # lectures
        assert dictee.dictees_du_jour(test_db, CTX) == 2


# ═════════════════════════════════════════════════════════════════════════════
# CA11 / CA13 — le panneau et sa logique pure (vérifications de structure)
# ═════════════════════════════════════════════════════════════════════════════
class TestPwa:
    PANNEAU = RACINE / "frontend" / "src" / "components" / "PanneauCompagnon.jsx"
    HOOK = RACINE / "frontend" / "src" / "hooks" / "useDictee.js"

    def test_us302_ca11_logique_dans_lib_voix(self):
        hook = self.HOOK.read_text(encoding="utf-8")
        for fonction in ("etatSuivant", "choisirTypeMime", "dureeAtteinte", "arreterLectures"):
            assert fonction in hook

    def test_us302_ca4_micro_libere(self):
        assert "piste.stop()" in self.HOOK.read_text(encoding="utf-8")

    def test_us302_ca6_envoi_par_le_chemin_d_une_phrase_tapee(self):
        panneau = self.PANNEAU.read_text(encoding="utf-8")
        assert "envoyer(phrase, undefined, true)" in panneau
        assert 'aria-label="Phrase dictée"' in panneau

    def test_us302_ca13_cibles_de_44_px_en_plein_ecran(self):
        assert "const tailleRonde = plein ? 'h-11 w-11'" in self.PANNEAU.read_text(encoding="utf-8")

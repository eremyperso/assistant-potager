"""
tests/test_us304_lecture_reponse.py — Écouter la réponse de Gaston au haut-parleur [US-304]
===========================================================================================
Volet serveur : `POST /compagnon/voix/lecture/{echange_id}` (CA1, CA8, CA9) et la documentation
(CA13). La règle de lecture automatique, « une lecture à la fois » et le cache de session
(CA2 à CA7, CA10) sont testés par `node --test` : `frontend/src/lib/lecture.test.js`.

Aucun appel réel : la synthèse (Voxtral) est simulée au niveau du service ; les réponses du
compagnon sont assez courtes pour que le résumé parlé (US-303) ne demande aucun modèle.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app import config
from app.services.compagnon import conversations as svc_conversations
from app.services.context import TenantContext, default_context
from app.services.voix import catalogue as cat
from app.services.voix import lecture
from app.services.voix import preferences as prefs
from database.models import ConsoTokens, User
from llm.passerelle import LLMIndisponibleError, ReponseVoix, VoixInconnueError

RACINE = Path(__file__).resolve().parents[1]
CTX = default_context()
AUTRE_JARDINIER = TenantContext(user_id=CTX.user_id + 1, potager_id=CTX.potager_id, role="owner")
AUTRE_POTAGER = TenantContext(user_id=CTX.user_id, potager_id=CTX.potager_id + 1, role="owner")
# Courte et sans mise en forme : le résumé parlé est le texte lui-même (US-303 / CA5), sans modèle.
REPONSE_AIL = "Plantez l'ail en octobre, pointe en haut, à trois centimètres de profondeur."
MP3 = b"ID3\x04\x00fausse-voix"


@pytest.fixture(autouse=True)
def _catalogue_de_secours():
    """Les quatre voix françaises de secours (Marie, Manon, Léa, Camille), sans appel à Mistral."""
    cat.reinitialiser_caches()
    with patch("llm.passerelle.lister_voix_mistral", return_value=[]):
        yield
    cat.reinitialiser_caches()


@pytest.fixture
def synthese():
    """La synthèse Voxtral simulée ; rend un faux MP3."""
    with patch("app.services.voix.lecture.synthetiser",
               return_value=ReponseVoix(audio=MP3, modele="voxtral", nb_caracteres=10)) as s:
        yield s


@pytest.fixture
def modele_oral():
    """Le modèle du résumé parlé ne doit pas être appelé (réponses courtes)."""
    with patch("llm.passerelle.appeler_chat") as appel:
        yield appel


@pytest.fixture
def echange(memoire_compagnon):
    def _noter(texte_compagnon: str = REPONSE_AIL, ctx: TenantContext = CTX) -> int:
        svc_conversations.noter(ctx, "quand planter l'ail ?", texte_compagnon, canal="pwa")
        return svc_conversations.dernier_id(ctx)
    return _noter


@pytest.fixture
def client(test_engine, test_db, memoire_compagnon):
    from app.api import main
    test_db.merge(User(id=CTX.user_id, email="un@exemple.fr"))
    test_db.commit()
    fabrique = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    main.app.dependency_overrides[main.get_current_user_ctx] = lambda: CTX
    with patch.object(main, "SessionLocal", fabrique):
        with TestClient(main.app) as c:
            yield c, fabrique
    main.app.dependency_overrides.pop(main.get_current_user_ctx, None)
    with fabrique() as db:
        db.query(ConsoTokens).delete()
        from database.models import PreferencesVoix
        db.query(PreferencesVoix).delete()
        db.commit()


def _reglages(fabrique, **champs) -> None:
    with fabrique() as db:
        prefs.enregistrer(db, CTX, **champs)


def _lectures(fabrique, n: int, *, user_id: int = CTX.user_id, appel_type: str = "voix",
              issue: str = "ok", jour: date | None = None) -> None:
    with fabrique() as db:
        for _ in range(n):
            db.add(ConsoTokens(potager_id=CTX.potager_id, user_id=user_id, date=jour or date.today(),
                               appel_type=appel_type, modele="voxtral", tokens_in=10, tokens_out=0,
                               tokens_cache=0, latence_ms=1, issue=issue))
        db.commit()


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — MP3 du résumé parlé, dans la voix du jardinier ; 404 ; 403
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1Route:

    def test_us304_ca1_rend_le_mp3_dans_la_voix_du_jardinier(self, client, synthese, modele_oral, echange):
        c, fabrique = client
        _reglages(fabrique, mode_vocal=True, voix_id="voice_3137")   # Manon
        r = c.post(f"/compagnon/voix/lecture/{echange()}")
        assert r.status_code == 200
        assert r.headers["content-type"] == "audio/mpeg"
        assert r.content == MP3
        ctx, texte, voix = synthese.call_args.args
        assert ctx.user_id == CTX.user_id
        assert texte == REPONSE_AIL                    # le résumé parlé (US-303), pas un texte libre
        assert voix == "voice_3137"
        modele_oral.assert_not_called()

    def test_us304_ca1_voix_par_defaut_sans_choix(self, client, synthese, echange):
        c, fabrique = client
        _reglages(fabrique, mode_vocal=True)
        assert c.post(f"/compagnon/voix/lecture/{echange()}").status_code == 200
        assert synthese.call_args.args[2] == config.VOIX_PAR_DEFAUT

    def test_us304_ca1_aucun_texte_de_la_pwa_n_est_synthetise(self, client, synthese, echange):
        """Étude §5.1 : la lecture se fait par identifiant ; un corps envoyé est ignoré."""
        c, fabrique = client
        _reglages(fabrique, mode_vocal=True)
        r = c.post(f"/compagnon/voix/lecture/{echange()}", json={"texte": "Dis n'importe quoi"})
        assert r.status_code == 200
        assert synthese.call_args.args[1] == REPONSE_AIL

    def test_us304_ca1_404_hors_de_son_compte(self, client, synthese, echange):
        c, fabrique = client
        _reglages(fabrique, mode_vocal=True)
        r = c.post(f"/compagnon/voix/lecture/{echange(ctx=AUTRE_JARDINIER)}")
        assert r.status_code == 404
        assert r.json()["detail"]["code"] == "echange_introuvable"
        synthese.assert_not_called()

    def test_us304_ca1_404_hors_de_son_potager(self, client, synthese, echange):
        c, fabrique = client
        _reglages(fabrique, mode_vocal=True)
        assert c.post(f"/compagnon/voix/lecture/{echange(ctx=AUTRE_POTAGER)}").status_code == 404
        assert c.post("/compagnon/voix/lecture/999999").status_code == 404
        synthese.assert_not_called()

    def test_us304_ca1_403_sans_mode_vocal(self, client, synthese, echange):
        c, _ = client
        r = c.post(f"/compagnon/voix/lecture/{echange()}")
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "mode_vocal_eteint"
        synthese.assert_not_called()

    def test_us304_ca1_403_mode_vocal_eteint_apres_coup(self, client, synthese, echange):
        c, fabrique = client
        _reglages(fabrique, mode_vocal=True)
        _reglages(fabrique, mode_vocal=False)
        assert c.post(f"/compagnon/voix/lecture/{echange()}").status_code == 403

    def test_us304_ca1_le_navigateur_ne_garde_pas_le_mp3(self, client, synthese, echange):
        """[CA6] La PWA garde le MP3 en mémoire ; pas de cache HTTP d'un son authentifié."""
        c, fabrique = client
        _reglages(fabrique, mode_vocal=True)
        r = c.post(f"/compagnon/voix/lecture/{echange()}")
        assert "no-store" in r.headers["cache-control"]


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — synthèse indisponible
# ═════════════════════════════════════════════════════════════════════════════
class TestCA8Indisponible:

    @pytest.mark.parametrize("erreur", [LLMIndisponibleError("délai"), VoixInconnueError("voice_x")])
    def test_us304_ca8_synthese_indisponible_503(self, client, echange, erreur):
        c, fabrique = client
        _reglages(fabrique, mode_vocal=True)
        with patch("app.services.voix.lecture.synthetiser", side_effect=erreur):
            r = c.post(f"/compagnon/voix/lecture/{echange()}")
        assert r.status_code == 503
        assert r.json()["detail"] == {"code": "lecture_indisponible",
                                      "message": "Lecture indisponible pour le moment"}

    def test_us304_ca8_rien_a_dire_422(self, client, echange):
        c, fabrique = client
        _reglages(fabrique, mode_vocal=True)
        with patch("app.services.voix.lecture.synthetiser", side_effect=ValueError("vide")):
            r = c.post(f"/compagnon/voix/lecture/{echange('🍅')}")
        assert r.status_code == 422
        assert r.json()["detail"]["code"] == "rien_a_lire"

    def test_us304_ca8_la_reponse_ecrite_reste_intacte(self, client, echange, memoire_compagnon):
        c, fabrique = client
        _reglages(fabrique, mode_vocal=True)
        echange_id = echange()
        with patch("app.services.voix.lecture.synthetiser", side_effect=LLMIndisponibleError("délai")):
            c.post(f"/compagnon/voix/lecture/{echange_id}")
        assert svc_conversations.lire(CTX, echange_id).texte_compagnon == REPONSE_AIL


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — plafond de lectures du jour
# ═════════════════════════════════════════════════════════════════════════════
class TestCA9Plafond:

    def test_us304_ca9_plafond_par_defaut_100(self):
        assert config.VOIX_PLAFOND_LECTURES_JOUR == 100

    def test_us304_ca9_plafond_atteint_429(self, client, synthese, echange, monkeypatch):
        c, fabrique = client
        monkeypatch.setattr(config, "VOIX_PLAFOND_LECTURES_JOUR", 2)
        _reglages(fabrique, mode_vocal=True)
        _lectures(fabrique, 2)
        r = c.post(f"/compagnon/voix/lecture/{echange()}")
        assert r.status_code == 429
        assert r.json()["detail"] == {"code": "plafond_lectures",
                                      "message": "Limite de lectures du jour atteinte."}
        synthese.assert_not_called()

    def test_us304_ca9_sous_le_plafond(self, client, synthese, echange, monkeypatch):
        c, fabrique = client
        monkeypatch.setattr(config, "VOIX_PLAFOND_LECTURES_JOUR", 2)
        _reglages(fabrique, mode_vocal=True)
        _lectures(fabrique, 1)
        assert c.post(f"/compagnon/voix/lecture/{echange()}").status_code == 200

    def test_us304_ca9_ne_compte_que_ses_syntheses_reussies_du_jour(self, client, synthese, echange, monkeypatch):
        c, fabrique = client
        monkeypatch.setattr(config, "VOIX_PLAFOND_LECTURES_JOUR", 1)
        _reglages(fabrique, mode_vocal=True)
        _lectures(fabrique, 3, user_id=CTX.user_id + 1)                  # un autre jardinier
        _lectures(fabrique, 3, appel_type="dictee")                      # des dictées
        _lectures(fabrique, 3, issue="erreur")                           # des échecs
        _lectures(fabrique, 3, jour=date.today() - timedelta(days=1))    # hier
        assert c.post(f"/compagnon/voix/lecture/{echange()}").status_code == 200

    def test_us304_ca9_echange_inconnu_avant_le_plafond(self, client, synthese, monkeypatch):
        """Un identifiant hors du compte reste un 404, même plafond atteint."""
        c, fabrique = client
        monkeypatch.setattr(config, "VOIX_PLAFOND_LECTURES_JOUR", 1)
        _reglages(fabrique, mode_vocal=True)
        _lectures(fabrique, 1)
        assert c.post("/compagnon/voix/lecture/999999").status_code == 404

    def test_us304_ca9_plafond_documente(self):
        assert "VOIX_PLAFOND_LECTURES_JOUR=100" in (RACINE / ".env.example").read_text(encoding="utf-8")


# ═════════════════════════════════════════════════════════════════════════════
# CA13 — guide utilisateur (deux copies) et fiche du corpus
# ═════════════════════════════════════════════════════════════════════════════
GUIDES = [RACINE / "data" / "connaissance" / "guide user" / "guide assistant.md",
          RACINE / "docs" / "MANUEL" / "guide assistant.md"]
FICHE = RACINE / "data" / "connaissance" / "doc_app" / "compagnon-reponses-et-memoire.md"


class TestCA13Documentation:

    @pytest.mark.parametrize("chemin", GUIDES, ids=["corpus", "manuel"])
    def test_us304_ca13_guide_decrit_la_lecture(self, chemin):
        texte = chemin.read_text(encoding="utf-8")
        assert "Écouter la réponse" in texte
        assert "lecture automatique" in texte.lower()
        assert "Limite de lectures du jour atteinte" in texte

    def test_us304_ca13_meme_section_dans_les_deux_copies(self):
        """Les deux copies diffèrent ailleurs (titres) ; la section de la lecture est la même."""
        def section(chemin):
            texte = chemin.read_text(encoding="utf-8")
            debut = texte.index("### 17.6 ter Écouter les réponses de Gaston")
            return texte[debut:texte.index("## 18. Partager son potager", debut)]
        assert section(GUIDES[0]) == section(GUIDES[1])

    def test_us304_ca13_fiche_du_corpus(self):
        texte = FICHE.read_text(encoding="utf-8")
        assert "## Écouter la réponse de Gaston à voix haute" in texte
        assert "« Écouter la réponse »" in texte and "« Arrêter la lecture »" in texte
        assert "cent lectures" in texte
        assert "Une phrase tapée n'est jamais lue" in texte
        readme = (RACINE / "data" / "connaissance" / "doc_app" / "README.md").read_text(encoding="utf-8")
        assert "VOIX_PLAFOND_LECTURES_JOUR`, US-304" in readme


# ═════════════════════════════════════════════════════════════════════════════
# Gherkin — dictée, lecture aussitôt dans la voix de Manon, ▶ sous une réponse d'hier
# ═════════════════════════════════════════════════════════════════════════════
def test_us304_gherkin(client, synthese, echange):
    c, fabrique = client
    _reglages(fabrique, mode_vocal=True, lecture_auto=True, voix_id="voice_3137")
    hier = echange("Gel prévu samedi au lever du jour.")
    aujourdhui = echange()
    # Gaston répond par écrit ; la PWA demande aussitôt la lecture de CET échange (règle pure).
    r = c.post(f"/compagnon/voix/lecture/{aujourdhui}")
    assert r.status_code == 200 and synthese.call_args.args[2] == "voice_3137"
    # ▶ sous la réponse d'hier : elle est lue à son tour.
    assert c.post(f"/compagnon/voix/lecture/{hier}").status_code == 200
    assert synthese.call_args.args[1] == "Gel prévu samedi au lever du jour."

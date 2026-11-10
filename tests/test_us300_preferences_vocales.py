"""
tests/test_us300_preferences_vocales.py — US-300 : préférences vocales et catalogue des voix

Préférence de la personne (table `preferences_voix`), catalogue des voix françaises lu
sur l'API Mistral avec cache 24 h et liste de secours, extrait de voix gardé en cache.
Aucun appel réseau : la passerelle est simulée.
"""
from __future__ import annotations

import inspect
import pathlib
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app import config
from app.services import voix
from app.services.context import TenantContext
from app.services.voix import catalogue as cat
from app.services.voix import preferences as prefs
from database.models import PreferencesVoix, User
from llm import passerelle

RACINE = pathlib.Path(__file__).resolve().parent.parent
CTX = TenantContext(user_id=1, potager_id=1, role="owner")
CTX_AUTRE = TenantContext(user_id=2, potager_id=1, role="editor")
MP3 = b"ID3\x04\x00faux-mp3"


def _api(nom, slug, langues=("fr",), genre="female", uuid=None):
    return {"name": nom, "slug": slug, "languages": list(langues), "gender": genre,
            "id": uuid or f"uuid-{slug}", "type": "preset"}


REPONSE_MISTRAL = [
    _api("Marie", "voice_592"), _api("Manon", "voice_3137"),
    _api("Lea", "voice_589"), _api("Camille", "voice_3141"),
    _api("Marie - Sad", "fr_marie_sad", langues=("fr_fr",)),   # ancienne voix Voxtral 2
    _api("James", "voice_3150", langues=("en_us",), genre="male"),
]


@pytest.fixture(autouse=True)
def _caches_propres():
    cat.reinitialiser_caches()
    yield
    cat.reinitialiser_caches()


@pytest.fixture
def mistral_voix():
    """L'API des voix répond avec le catalogue réel d'US-298 (français, anglais, anciennes voix)."""
    with patch("llm.passerelle.lister_voix_mistral", return_value=list(REPONSE_MISTRAL)) as liste:
        yield liste


@pytest.fixture
def api_en_panne():
    with patch("llm.passerelle.lister_voix_mistral",
               side_effect=passerelle.FournisseurLLMIndisponibleError("panne")) as liste:
        yield liste


@pytest.fixture(autouse=True)
def _jardiniers(test_db):
    test_db.add_all([
        User(id=1, email="un@exemple.fr"),
        User(id=2, email="deux@exemple.fr"),
    ])
    test_db.commit()


@pytest.fixture
def client(test_engine):
    from app.api import main
    fabrique = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    main.app.dependency_overrides[main.get_current_user_ctx] = lambda: CTX
    with patch.object(main, "SessionLocal", fabrique):
        with TestClient(main.app) as c:
            yield c
    main.app.dependency_overrides.pop(main.get_current_user_ctx, None)


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — table, migration, rollback, isolation par jardinier
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1Migration:

    def test_us300_ca1_migration_v71(self):
        sql = (RACINE / "migrations/migration_v71.sql").read_text(encoding="utf-8")
        assert "CREATE TABLE IF NOT EXISTS preferences_voix" in sql
        assert "user_id      INTEGER     PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE" in sql
        assert "mode_vocal   BOOLEAN     NOT NULL DEFAULT FALSE" in sql
        assert "voix_id      VARCHAR(64) NULL" in sql
        assert "lecture_auto BOOLEAN     NOT NULL DEFAULT TRUE" in sql
        assert "maj_le" in sql

    def test_us300_ca1_rollback_v71(self):
        sql = (RACINE / "migrations/rollback_v71.sql").read_text(encoding="utf-8")
        assert "DROP TABLE IF EXISTS preferences_voix" in sql

    def test_us300_ca1_modele_aligne_sur_la_migration(self):
        colonnes = {c.name: c for c in PreferencesVoix.__table__.columns}
        assert set(colonnes) == {"user_id", "mode_vocal", "voix_id", "lecture_auto", "maj_le"}
        assert colonnes["user_id"].primary_key
        assert colonnes["voix_id"].nullable
        assert not any(c.name == "potager_id" for c in PreferencesVoix.__table__.columns)

    def test_us300_ca1_un_jardinier_ne_voit_que_sa_ligne(self, test_db, mistral_voix):
        prefs.enregistrer(test_db, CTX, mode_vocal=True, voix_id="voice_3137")
        assert prefs.lire(test_db, CTX_AUTRE).mode_vocal is False
        assert prefs.lire(test_db, CTX_AUTRE).voix_choisie is None
        prefs.enregistrer(test_db, CTX_AUTRE, lecture_auto=False)
        assert prefs.lire(test_db, CTX).lecture_auto is True
        assert prefs.lire(test_db, CTX).voix_choisie == "voice_3137"
        assert test_db.query(PreferencesVoix).count() == 2

    def test_us300_ca1_meme_voix_d_un_potager_a_l_autre(self, test_db, mistral_voix):
        """Préférence de la personne : le potager du contexte n'y change rien."""
        prefs.enregistrer(test_db, CTX, voix_id="voice_589")
        autre_potager = TenantContext(user_id=1, potager_id=2, role="owner")
        assert prefs.lire(test_db, autre_potager).voix_id == "voice_589"


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — GET des préférences : défauts sans rien écrire
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2LirePreferences:

    def test_us300_ca2_defauts_sans_ligne(self, client, test_db, mistral_voix):
        r = client.get("/compagnon/voix/preferences")
        assert r.status_code == 200
        assert r.json() == {"mode_vocal": False, "voix_id": config.VOIX_PAR_DEFAUT,
                            "lecture_auto": True,
                            # [US-302 / CA3] la lecture dit aussi la durée maximale d'une dictée
                            "dictee_duree_max_s": config.VOIX_DICTEE_DUREE_MAX_S}

    def test_us300_ca2_la_lecture_n_ecrit_rien(self, client, test_db, mistral_voix):
        client.get("/compagnon/voix/preferences")
        client.get("/compagnon/voix/preferences")
        assert test_db.query(PreferencesVoix).count() == 0

    def test_us300_ca2_voix_par_defaut_de_la_configuration(self, client, mistral_voix):
        with patch.object(config, "VOIX_PAR_DEFAUT", "voice_3141"):
            assert client.get("/compagnon/voix/preferences").json()["voix_id"] == "voice_3141"

    def test_us300_ca2_defaut_est_marie(self):
        assert config.VOIX_PAR_DEFAUT == "voice_592"


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — PUT : enregistre, refuse une voix hors catalogue (422 + liste)
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3EnregistrerPreferences:

    def test_us300_ca3_enregistre_les_trois_reglages(self, client, test_db, mistral_voix):
        r = client.put("/compagnon/voix/preferences",
                       json={"mode_vocal": True, "voix_id": "voice_3137", "lecture_auto": False})
        assert r.status_code == 200
        assert r.json() == {"mode_vocal": True, "voix_id": "voice_3137", "lecture_auto": False}
        ligne = test_db.query(PreferencesVoix).one()
        assert (ligne.user_id, ligne.mode_vocal, ligne.voix_id, ligne.lecture_auto) == \
            (1, True, "voice_3137", False)
        assert ligne.maj_le is not None

    def test_us300_ca3_reglage_partiel_laisse_le_reste(self, client, test_db, mistral_voix):
        client.put("/compagnon/voix/preferences", json={"voix_id": "voice_589", "mode_vocal": True})
        r = client.put("/compagnon/voix/preferences", json={"lecture_auto": False})
        assert r.json() == {"mode_vocal": True, "voix_id": "voice_589", "lecture_auto": False}

    def test_us300_ca3_voix_inconnue_422_avec_la_liste(self, client, test_db, mistral_voix):
        r = client.put("/compagnon/voix/preferences", json={"voix_id": "voice_0000"})
        assert r.status_code == 422
        assert r.json()["detail"]["voix_valides"] == ["voice_592", "voice_3137", "voice_589", "voice_3141"]
        assert test_db.query(PreferencesVoix).count() == 0, "un refus n'écrit rien"

    def test_us300_ca3_ancienne_voix_voxtral2_refusee(self, client, mistral_voix):
        assert client.put("/compagnon/voix/preferences",
                          json={"voix_id": "fr_marie_sad"}).status_code == 422

    def test_us300_ca3_voix_null_remet_la_voix_par_defaut(self, client, test_db, mistral_voix):
        client.put("/compagnon/voix/preferences", json={"voix_id": "voice_589"})
        r = client.put("/compagnon/voix/preferences", json={"voix_id": None})
        assert r.json()["voix_id"] == config.VOIX_PAR_DEFAUT
        assert test_db.query(PreferencesVoix).one().voix_id is None

    def test_us300_ca3_booleen_null_ignore(self, client, mistral_voix):
        client.put("/compagnon/voix/preferences", json={"mode_vocal": True})
        r = client.put("/compagnon/voix/preferences", json={"mode_vocal": None})
        assert r.json()["mode_vocal"] is True

    def test_us300_ca3_corps_vide_cree_la_ligne_aux_defauts(self, client, test_db, mistral_voix):
        assert client.put("/compagnon/voix/preferences", json={}).status_code == 200


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — catalogue lu sur Mistral, cache 24 h
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4Catalogue:

    def test_us300_ca4_voix_francaises_seulement(self, client, mistral_voix):
        r = client.get("/compagnon/voix/catalogue")
        assert r.status_code == 200
        corps = r.json()
        assert corps["liste_de_secours"] is False
        assert corps["voix"] == [
            {"id": "voice_592", "nom": "Marie", "genre": "female", "par_defaut": True},
            {"id": "voice_3137", "nom": "Manon", "genre": "female", "par_defaut": False},
            {"id": "voice_589", "nom": "Lea", "genre": "female", "par_defaut": False},
            {"id": "voice_3141", "nom": "Camille", "genre": "female", "par_defaut": False},
        ]

    def test_us300_ca4_nouvelle_voix_sans_redeploiement(self, client, mistral_voix):
        mistral_voix.return_value = REPONSE_MISTRAL + [_api("Élise", "voice_9999", genre=None)]
        ids = [v["id"] for v in client.get("/compagnon/voix/catalogue").json()["voix"]]
        assert "voice_9999" in ids
        assert client.get("/compagnon/voix/catalogue").json()["voix"][-1]["genre"] is None

    def test_us300_ca4_la_voix_par_defaut_est_reperee(self, client, mistral_voix):
        """US-301 / maquette : la pastille « par défaut » suit VOIX_PAR_DEFAUT, cache intact."""
        client.get("/compagnon/voix/catalogue")
        with patch.object(config, "VOIX_PAR_DEFAUT", "voice_3141"):
            voix_api = client.get("/compagnon/voix/catalogue").json()["voix"]
        assert [v["id"] for v in voix_api if v["par_defaut"]] == ["voice_3141"]
        assert mistral_voix.call_count == 1

    def test_us300_ca4_cache_de_24_h(self, client, mistral_voix):
        client.get("/compagnon/voix/catalogue")
        client.get("/compagnon/voix/catalogue")
        assert mistral_voix.call_count == 1
        assert cat.DUREE_CACHE_S == 24 * 3600

    def test_us300_ca4_le_cache_expire_apres_24_h(self, mistral_voix):
        cat.lire_catalogue()
        cat._cache["expire_a"] = 0.0
        cat.lire_catalogue()
        assert mistral_voix.call_count == 2

    def test_us300_ca4_entrees_incompletes_ignorees(self, mistral_voix):
        mistral_voix.return_value = [
            {"name": "", "slug": "voice_1", "languages": ["fr"]},
            {"name": "SansSlug", "languages": ["fr"]},
            {"name": "Ok", "slug": "voice_2", "languages": ["fr"], "gender": 3},
        ]
        catalogue = cat.lire_catalogue()
        assert catalogue.ids() == ["voice_2"] and catalogue.voix[0].genre is None

    def test_us300_ca4_catalogue_demande_une_authentification(self):
        from app.api import main
        with TestClient(main.app) as c:
            assert c.get("/compagnon/voix/catalogue").status_code in (401, 403)


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — liste de secours, aucune erreur montrée
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5ListeDeSecours:

    def test_us300_ca5_api_en_panne_les_quatre_voix(self, client, api_en_panne):
        r = client.get("/compagnon/voix/catalogue")
        assert r.status_code == 200
        corps = r.json()
        assert corps["liste_de_secours"] is True
        assert [(v["id"], v["nom"]) for v in corps["voix"]] == [
            ("voice_592", "Marie"), ("voice_3137", "Manon"),
            ("voice_589", "Léa"), ("voice_3141", "Camille")]

    def test_us300_ca5_sans_cle_mistral_meme_repli(self, client):
        with patch("llm.passerelle.MISTRAL_API_KEY", ""), patch("llm.passerelle._client_mistral", None):
            corps = client.get("/compagnon/voix/catalogue").json()
        assert corps["liste_de_secours"] is True and len(corps["voix"]) == 4

    def test_us300_ca5_aucune_voix_francaise_rendue_repli(self, client, mistral_voix):
        mistral_voix.return_value = [_api("James", "voice_3150", langues=("en_us",))]
        assert client.get("/compagnon/voix/catalogue").json()["liste_de_secours"] is True

    def test_us300_ca5_on_retente_vite_apres_une_panne(self, api_en_panne):
        cat.lire_catalogue()
        assert cat._cache["expire_a"] - __import__("time").monotonic() <= cat.DUREE_CACHE_SECOURS_S
        assert cat.DUREE_CACHE_SECOURS_S < cat.DUREE_CACHE_S

    def test_us300_ca5_le_choix_reste_possible_avec_la_liste_de_secours(self, client, api_en_panne):
        r = client.put("/compagnon/voix/preferences", json={"voix_id": "voice_589"})
        assert r.status_code == 200 and r.json()["voix_id"] == "voice_589"


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — extrait de voix
# ═════════════════════════════════════════════════════════════════════════════
class TestCA6Extrait:

    def test_us300_ca6_extrait_fourni_par_mistral(self, client, mistral_voix):
        with patch("llm.passerelle.extrait_voix_mistral", return_value=MP3) as extrait, \
             patch("llm.passerelle.synthetiser") as synth:
            r = client.get("/compagnon/voix/catalogue/voice_589/extrait")
        assert r.status_code == 200
        assert r.headers["content-type"] == "audio/mpeg"
        assert r.content == MP3
        extrait.assert_called_once_with("uuid-voice_589")
        synth.assert_not_called()

    def test_us300_ca6_sinon_phrase_synthetisee_une_seule_fois(self, client, mistral_voix):
        synth = SimpleNamespace(audio=MP3)
        with patch("llm.passerelle.extrait_voix_mistral", return_value=None), \
             patch("llm.passerelle.synthetiser", return_value=synth) as appel:
            premier = client.get("/compagnon/voix/catalogue/voice_3137/extrait")
            second = client.get("/compagnon/voix/catalogue/voice_3137/extrait")
        assert premier.content == second.content == MP3
        assert appel.call_count == 1, "le deuxième appel ne coûte rien"
        kwargs = appel.call_args.kwargs
        assert kwargs["texte"] == "Bonjour, je suis Gaston, votre compagnon du potager"
        assert kwargs["voix_id"] == "voice_3137"

    def test_us300_ca6_un_extrait_mistral_est_garde_aussi(self, client, mistral_voix):
        with patch("llm.passerelle.extrait_voix_mistral", return_value=MP3) as extrait:
            client.get("/compagnon/voix/catalogue/voice_589/extrait")
            client.get("/compagnon/voix/catalogue/voice_589/extrait")
        assert extrait.call_count == 1

    def test_us300_ca6_liste_de_secours_synthetise(self, client, api_en_panne):
        with patch("llm.passerelle.extrait_voix_mistral") as extrait, \
             patch("llm.passerelle.synthetiser", return_value=SimpleNamespace(audio=MP3)):
            r = client.get("/compagnon/voix/catalogue/voice_592/extrait")
        assert r.status_code == 200
        extrait.assert_not_called()

    def test_us300_ca6_voix_inconnue_404_avec_la_liste(self, client, mistral_voix):
        r = client.get("/compagnon/voix/catalogue/voice_0000/extrait")
        assert r.status_code == 404
        assert "voice_592" in r.json()["detail"]["voix_valides"]

    def test_us300_ca6_voix_refusee_par_le_fournisseur_404_jamais_500(self, client, mistral_voix):
        """Voix au catalogue (ex. VOIX_CATALOGUE OpenAI) mais inconnue du fournisseur (Mistral)."""
        from llm.passerelle import VoixInconnueError
        with patch("llm.passerelle.extrait_voix_mistral", return_value=None), \
             patch("llm.passerelle.synthetiser", side_effect=VoixInconnueError("voix inconnue (404)")):
            r = client.get("/compagnon/voix/catalogue/voice_3137/extrait")
        assert r.status_code == 404
        assert "inconnue du fournisseur" in r.json()["detail"]["message"]

    def test_us300_ca6_synthese_en_panne_503_lisible(self, client, mistral_voix):
        with patch("llm.passerelle.extrait_voix_mistral", return_value=None), \
             patch("llm.passerelle.synthetiser",
                   side_effect=passerelle.DelaiLLMDepasseError("délai")):
            r = client.get("/compagnon/voix/catalogue/voice_592/extrait")
        assert r.status_code == 503
        assert "écrivez votre message" in r.json()["detail"]

    @pytest.mark.parametrize("reponse, attendu", [
        (b"\xff\xfbfaux", b"\xff\xfbfaux"),
        ({"audio_data": "SUQzeHg="}, b"ID3xx"),
        ({"audio_data": "pas du base64 !!"}, None),
        ({}, None),
        (b"", None),
    ])
    def test_us300_ca6_formats_de_reponse_de_l_extrait(self, reponse, attendu):
        faux = SimpleNamespace(get=lambda *a, **k: reponse)
        with patch("llm.passerelle._client_pour_mistral", return_value=faux):
            assert passerelle.extrait_voix_mistral("uuid") == attendu

    def test_us300_ca6_extrait_mistral_ne_leve_jamais(self):
        def _echec(*a, **k):
            raise RuntimeError("boom")
        with patch("llm.passerelle._client_pour_mistral", return_value=SimpleNamespace(get=_echec)):
            assert passerelle.extrait_voix_mistral("uuid") is None


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — voix retirée par Mistral : repli sans erreur
# ═════════════════════════════════════════════════════════════════════════════
class TestCA7VoixRetiree:

    def test_us300_ca7_lecture_retombe_sur_la_voix_par_defaut(self, test_db, mistral_voix):
        prefs.enregistrer(test_db, CTX, voix_id="voice_3141")
        mistral_voix.return_value = [_api("Marie", "voice_592")]   # Camille retirée
        cat.reinitialiser_caches()

        lues = prefs.lire(test_db, CTX)
        assert lues.voix_id == config.VOIX_PAR_DEFAUT
        assert lues.voix_choisie == "voice_3141", "la lecture ne corrige rien en base"

    def test_us300_ca7_preference_corrigee_au_prochain_enregistrement(self, test_db, mistral_voix):
        prefs.enregistrer(test_db, CTX, voix_id="voice_3141")
        mistral_voix.return_value = [_api("Marie", "voice_592")]
        cat.reinitialiser_caches()

        prefs.enregistrer(test_db, CTX, lecture_auto=False)
        assert test_db.query(PreferencesVoix).one().voix_id is None

    def test_us300_ca7_voix_choisie_encore_valide_conservee(self, test_db, mistral_voix):
        prefs.enregistrer(test_db, CTX, voix_id="voice_589")
        prefs.enregistrer(test_db, CTX, mode_vocal=True)
        assert test_db.query(PreferencesVoix).one().voix_id == "voice_589"

    def test_us300_ca7_synthese_retombe_sur_la_voix_par_defaut_sans_erreur(self):
        """Mistral refuse la voix au moment de lire : on relit avec la voix par défaut."""
        appels = []

        def _synth(*, ctx, texte, voix_id, format_audio):
            appels.append(voix_id)
            if voix_id == "voice_3141":
                raise passerelle.VoixInconnueError("retirée")
            return passerelle.ReponseVoix(audio=MP3, format_audio="mp3", nb_caracteres=len(texte))

        with patch("llm.passerelle.synthetiser", side_effect=_synth):
            reponse = voix.synthetiser(CTX, "Bonjour", voix_id="voice_3141")
        assert reponse.audio == MP3
        assert appels == ["voice_3141", config.VOIX_PAR_DEFAUT]

    def test_us300_ca7_voix_par_defaut_refusee_remonte(self):
        with patch("llm.passerelle.synthetiser", side_effect=passerelle.VoixInconnueError("x")) as s:
            with pytest.raises(passerelle.VoixInconnueError):
                voix.synthetiser(CTX, "Bonjour")
        assert s.call_count == 1


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — suppression du compte
# ═════════════════════════════════════════════════════════════════════════════
class TestCA8SuppressionDuCompte:

    def test_us300_ca8_cle_etrangere_en_cascade(self):
        cle = next(iter(PreferencesVoix.__table__.c.user_id.foreign_keys))
        assert cle.column.table.name == "users"
        assert cle.ondelete == "CASCADE"

    def test_us300_ca8_la_migration_cascade_aussi(self):
        sql = (RACINE / "migrations/migration_v71.sql").read_text(encoding="utf-8")
        assert "REFERENCES users(id) ON DELETE CASCADE" in sql


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — aucune logique dans les routes
# ═════════════════════════════════════════════════════════════════════════════
class TestCA9RoutesMinces:

    @pytest.mark.parametrize("route", [
        "lire_preferences_voix", "enregistrer_preferences_voix", "catalogue_voix", "extrait_voix"])
    def test_us300_ca9_pas_de_requete_ni_de_passerelle_dans_les_routes(self, route):
        from app.api import main
        source = inspect.getsource(getattr(main, route))
        assert "db.query" not in source and "passerelle" not in source
        assert "svc_voix." in source

    def test_us300_ca9_service_porte_la_requete(self):
        assert "db.query(PreferencesVoix)" in inspect.getsource(prefs)


# ═════════════════════════════════════════════════════════════════════════════
# Passerelle — liste des voix Mistral
# ═════════════════════════════════════════════════════════════════════════════
class TestListeMistral:

    def test_us300_liste_des_voix_demande_100_voix_predefinies(self):
        faux = SimpleNamespace(get=lambda chemin, **kw: (
            seen.update(chemin=chemin, **kw) or {"items": [{"slug": "voice_592"}, "intrus"]}))
        seen: dict = {}
        with patch("llm.passerelle._client_pour_mistral", return_value=faux):
            voix_api = passerelle.lister_voix_mistral()
        assert seen["chemin"] == "/v1/audio/voices"
        assert seen["options"] == {"params": {"limit": 100, "type": "preset"}}
        assert voix_api == [{"slug": "voice_592"}]

    def test_us300_liste_sans_cle_indisponibilite_typee(self):
        with patch("llm.passerelle.MISTRAL_API_KEY", ""), patch("llm.passerelle._client_mistral", None):
            with pytest.raises(passerelle.LLMIndisponibleError):
                passerelle.lister_voix_mistral()

    def test_us300_liste_reponse_inexploitable(self):
        faux = SimpleNamespace(get=lambda *a, **k: {"pas_items": []})
        with patch("llm.passerelle._client_pour_mistral", return_value=faux):
            with pytest.raises(passerelle.FournisseurLLMIndisponibleError):
                passerelle.lister_voix_mistral()

    def test_us300_liste_erreur_5xx_typee(self):
        import groq
        import httpx
        requete = httpx.Request("GET", "https://api.mistral.ai/v1/audio/voices")

        def _echec(*a, **k):
            raise groq.InternalServerError("x", response=httpx.Response(503, request=requete), body=None)

        with patch("llm.passerelle._client_pour_mistral", return_value=SimpleNamespace(get=_echec)):
            with pytest.raises(passerelle.FournisseurLLMIndisponibleError):
                passerelle.lister_voix_mistral()

    def test_us300_liste_delai_depasse_type(self):
        import groq
        import httpx

        def _echec(*a, **k):
            raise groq.APITimeoutError(request=httpx.Request("GET", "https://api.mistral.ai/v1/audio/voices"))

        with patch("llm.passerelle._client_pour_mistral", return_value=SimpleNamespace(get=_echec)):
            with pytest.raises(passerelle.DelaiLLMDepasseError):
                passerelle.lister_voix_mistral()


# ═════════════════════════════════════════════════════════════════════════════
# Scénario Gherkin
# ═════════════════════════════════════════════════════════════════════════════
def test_us300_gherkin(client, test_db, test_engine, mistral_voix):
    # Given le jardinier n'a jamais réglé la voix
    # When la PWA lit GET /compagnon/voix/preferences
    base = client.get("/compagnon/voix/preferences").json()
    # Then mode vocal éteint, lecture automatique active, voix de VOIX_PAR_DEFAUT
    assert base == {"mode_vocal": False, "voix_id": config.VOIX_PAR_DEFAUT, "lecture_auto": True,
                    "dictee_duree_max_s": config.VOIX_DICTEE_DUREE_MAX_S}  # [US-302 / CA3]

    # When il enregistre la voix "voice_3137" (Manon) depuis son PC
    assert client.put("/compagnon/voix/preferences", json={"voix_id": "voice_3137"}).status_code == 200
    # And ouvre la PWA sur son téléphone (autre session, même compte)
    with TestClient(client.app) as telephone:
        # Then la voix lue est "voice_3137"
        assert telephone.get("/compagnon/voix/preferences").json()["voix_id"] == "voice_3137"

    # Given l'API des voix de Mistral ne répond pas
    cat.reinitialiser_caches()
    mistral_voix.side_effect = passerelle.FournisseurLLMIndisponibleError("panne")
    # When la PWA lit le catalogue
    corps = client.get("/compagnon/voix/catalogue").json()
    # Then Marie, Manon, Léa et Camille marquées "liste de secours"
    assert corps["liste_de_secours"] is True
    assert [v["nom"] for v in corps["voix"]] == ["Marie", "Manon", "Léa", "Camille"]


# ═════════════════════════════════════════════════════════════════════════════
# Recette visuelle — CORS : le PUT des réglages passe depuis Vite (localhost:5173) vers l'API
# ═════════════════════════════════════════════════════════════════════════════
def test_us300_cors_autorise_le_put_des_reglages_depuis_vite(client):
    r = client.options(
        "/compagnon/voix/preferences",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "PUT",
                 "Access-Control-Request-Headers": "authorization,content-type"},
    )
    assert r.status_code == 200
    assert "PUT" in r.headers["access-control-allow-methods"]

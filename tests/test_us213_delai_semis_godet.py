"""
tests/test_us213_delai_semis_godet.py — Délai semis → repiquage en godet [US-213]
================================================================================

La Pépinière trie ses lots par « jours d'écart au repiquage attendu » : elle
suppose que le référentiel connaît le délai entre le semis et le passage de la
barquette au godet. Cette suite couvre les neuf critères d'acceptance :

- CA1  cinquième étape de `duree_culturale`, sans migration, pour la pépinière
- CA2  fixée / retirée au bot, locale au potager, jamais écrasée par un rejeu
- CA3  dictée — le mot « godet » est exigé, « repiquage » seul garde son sens
- CA4  lue par `/calendrier`, `GET /cultures/{c}/calendrier`, `GET /plan/calendriers`
- CA5  jamais déduite d'une autre durée
- CA6  gabarit interne livré vide ; la source ouverte ne la porte pas (SOURCE.md)
- CA7  aucun calcul existant ne change
- CA8  fiches du corpus et guide relus (contrôlés aussi par test_us099)
- CA9  ce fichier

Les durées écrites ici sont des VALEURS DE TEST : elles n'engagent aucune
agronomie.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import adaptateur_wind_river as svc_adaptateur
from app.services import calendrier_cultural as cal
from app.services import import_referentiel as svc_import
from app.services import interpreteur_commandes as interp
from app.services import recalage_calendrier as rec
from app.services.context import TenantContext
from database.db import Base
from database.models import CultureConfig, DureeCulturale, Evenement, Parcelle, Potager, User

RACINE = Path(__file__).resolve().parent.parent
MANIFESTE_WIND_RIVER = RACINE / "data" / "referentiel" / "wind_river_attributs.json"
GABARIT_INTERNE = RACINE / "data" / "referentiel" / "calendrier_redaction_interne.json"
SOURCE_MD = RACINE / "data" / "referentiel" / "wind_river_greens" / "SOURCE.md"
CORPUS_DICTEE = RACINE / "tests" / "corpus" / "us172_commandes.csv"

CTX_A = TenantContext(user_id=1, potager_id=1, role="owner")
CTX_B = TenantContext(user_id=2, potager_id=2, role="owner")

PEPINIERE = {"oceanique": {"semis_pepiniere": "février-avril", "plantation": "mai-juin"}}
EN_PLACE = {"oceanique": {"semis_pleine_terre": "mars-juin"}}


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def db(test_db):
    """Deux potagers, deux parcelles — le décor de l'isolement (CA2)."""
    test_db.add_all([User(id=1, email="a@potager.test"), User(id=2, email="b@potager.test")])
    test_db.flush()
    test_db.add_all([
        Potager(id=1, nom="Jardin A", proprietaire_id=1, zone_climatique="oceanique"),
        Potager(id=2, nom="Jardin B", proprietaire_id=2, zone_climatique="oceanique"),
    ])
    test_db.flush()
    test_db.add_all([
        Parcelle(id=1, nom="nord", nom_normalise="nord", potager_id=1),
        Parcelle(id=2, nom="sud", nom_normalise="sud", potager_id=1),
    ])
    test_db.commit()
    return test_db


def _source():
    return {"code": "wikidata", "libelle": "Wikidata", "licence": "CC0",
            "attribution": "Wikidata — CC0 1.0 Universal (domaine public)",
            "url": "https://www.wikidata.org/", "partageable": True}


def _culture(db, nom, organe="reproducteur"):
    db.add(CultureConfig(nom=nom, type_organe_recolte=organe, potager_id=None))
    db.commit()


def _importer(db, *entrees):
    return svc_import.importer(db, {"source": _source(), "cultures_calendriers": list(entrees)})


def _referentiel(db, culture, organe="reproducteur", **entree):
    _culture(db, culture, organe)
    _importer(db, {"culture": culture, **entree})


def _godet(db, culture, potager_id=1):
    """La durée semis → godet lue pour ce potager, ou None si l'étape n'est pas servie."""
    return cal.lire_calendrier(db, culture, potager_id).itineraires[0].duree(cal.ETAPE_SEMIS_GODET)


def _evt(db, action, culture, jour, parcelle_id=1, **champs):
    evenement = Evenement(
        type_action=action, culture=culture,
        date=datetime.combine(jour, datetime.min.time()),
        parcelle_id=parcelle_id, potager_id=champs.pop("potager_id", 1), **champs,
    )
    db.add(evenement)
    db.commit()
    return evenement


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — une cinquième étape, pour ce qui passe par la pépinière
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1CinquiemeEtape:

    def test_us213_ca1_l_etape_existe_avec_un_libelle_distinct_de_repiquage(self):
        assert cal.ETAPE_SEMIS_GODET in cal.ETAPES
        libelle = cal.LIBELLES_ETAPES[cal.ETAPE_SEMIS_GODET]
        assert "godet" in libelle
        assert libelle != cal.LIBELLES_ETAPES[cal.ETAPE_REPIQUAGE]

    def test_us213_ca1_aucune_migration_le_nom_tient_dans_la_colonne(self):
        """Précédent d'US-177 : `duree_culturale.etape` est un VARCHAR(20) sans CHECK."""
        assert len(cal.ETAPE_SEMIS_GODET) <= DureeCulturale.etape.type.length

    @pytest.mark.parametrize("saisi", [
        "semis_godet", "semis-godet", "Semis Godet", "godet", "repiquage-en-godet", "mise en godet",
    ])
    def test_us213_ca1_les_formes_saisies_menent_a_la_meme_etape(self, saisi):
        assert cal.normaliser_etape(saisi) == cal.ETAPE_SEMIS_GODET

    @pytest.mark.parametrize("saisi", ["repiquage", "plantation"])
    def test_us213_ca1_repiquage_et_plantation_seuls_gardent_leur_sens(self, saisi):
        assert cal.normaliser_etape(saisi) == cal.ETAPE_REPIQUAGE

    @pytest.mark.parametrize("valeur,attendu", [
        ("10-15", "10 à 15 jours"), ("12", "12 jours"),
    ])
    def test_us213_ca1_en_jours_ou_en_fourchette(self, db, valeur, attendu):
        _referentiel(db, "chou", fenetres=PEPINIERE)
        assert cal.corriger_duree(db, CTX_A, "chou", "semis-godet", valeur)[1] == attendu

    def test_us213_ca1_en_mention_libre(self, db):
        _referentiel(db, "chou", fenetres=PEPINIERE)
        cal.corriger_duree(db, CTX_A, "chou", "semis-godet", "selon la météo")
        assert _godet(db, "chou").mention == "selon la météo"

    def test_us213_ca1_portee_par_un_itineraire_qui_passe_par_la_pepiniere(self, db):
        _referentiel(db, "chou", fenetres=PEPINIERE)
        etape = _godet(db, "chou")
        assert etape is not None and not etape.renseignee

    def test_us213_ca1_pas_servie_pour_une_culture_semee_en_place(self, db):
        _referentiel(db, "carotte", durees={"levee": "10", "recolte": "70-80"}, fenetres=EN_PLACE)
        assert _godet(db, "carotte") is None

    def test_us213_ca1_pas_servie_pour_l_itineraire_implicite(self, db):
        _culture(db, "topinambour")
        assert _godet(db, "topinambour") is None

    def test_us213_ca1_refusee_sur_un_itineraire_sans_semis_en_pepiniere(self, db):
        _referentiel(db, "carotte", fenetres=EN_PLACE)
        with pytest.raises(cal.ValeurCalendrierInvalideError, match="pépinière"):
            cal.corriger_duree(db, CTX_A, "carotte", "semis_godet", "10-15")
        assert db.query(DureeCulturale).filter(
            DureeCulturale.etape == cal.ETAPE_SEMIS_GODET).count() == 0

    def test_us213_ca1_acceptee_sur_un_itineraire_sans_aucune_fenetre(self, db):
        """Un itinéraire vide ne préjuge de rien : le jardinier sait, lui."""
        _culture(db, "poireau")
        assert cal.corriger_duree(db, CTX_A, "poireau", "semis_godet", "20-30") == (
            cal.NON_RENSEIGNE, "20 à 30 jours")

    def test_us213_ca1_une_valeur_posee_reste_lue_sans_fenetre_de_pepiniere(self, db):
        """Une valeur importée sur un itinéraire sans fenêtre ne disparaît pas de l'écran."""
        _referentiel(db, "poireau", durees={"semis_godet": "20-30"})
        assert _godet(db, "poireau").affichage == "20 à 30 jours"


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — fixée au bot, locale au potager, jamais écrasée
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2CorrectionLocale:

    def test_us213_ca2_gherkin_fixer_le_delai_au_bot(self, db):
        _referentiel(db, "chou", fenetres=PEPINIERE)
        avant, apres = cal.corriger_duree(db, CTX_A, "chou", "semis-godet", "10-15")
        assert (avant, apres) == (cal.NON_RENSEIGNE, "10 à 15 jours")
        assert (_godet(db, "chou").jours_min, _godet(db, "chou").jours_max) == (10, 15)

    def test_us213_ca2_ne_vaut_que_pour_le_potager_qui_la_corrige(self, db):
        _referentiel(db, "chou", fenetres=PEPINIERE)
        cal.corriger_duree(db, CTX_A, "chou", "semis-godet", "10-15")
        assert _godet(db, "chou", potager_id=2).affichage == cal.NON_RENSEIGNE

    def test_us213_ca2_aucune_la_retire(self, db):
        _referentiel(db, "chou", durees={"semis_godet": "10-15"}, fenetres=PEPINIERE)
        assert cal.corriger_duree(db, CTX_A, "chou", "semis_godet", "aucune") == (
            "10 à 15 jours", cal.NON_RENSEIGNE)
        assert not _godet(db, "chou").renseignee

    def test_us213_ca2_un_rejeu_d_import_n_ecrase_pas_la_correction(self, db):
        _referentiel(db, "chou", durees={"semis_godet": "10-15"}, fenetres=PEPINIERE)
        cal.corriger_duree(db, CTX_A, "chou", "semis_godet", "12-18")
        _importer(db, {"culture": "chou", "durees": {"semis_godet": "8-9"}})
        assert _godet(db, "chou").affichage == "12 à 18 jours"
        # … et le potager qui n'a rien corrigé lit toujours la valeur partagée.
        assert _godet(db, "chou", potager_id=2).affichage == "8 à 9 jours"

    def test_us213_ca2_le_decoupage_du_bot_reconnait_la_sous_commande(self):
        """Ce que fait `/calendrier duree chou semis-godet 10-15`."""
        from app import bot

        decoupe = bot._decouper_correction(
            ["chou", "semis-godet", "10-15"], cal.est_etape, cal.parser_duree)
        assert decoupe == (["chou"], "semis-godet", "10-15")


class TestCA2HandlerTelegram:
    """Le handler réellement enregistré — Telegram mocké, aucun appel réseau."""

    async def _appeler(self, db, *args, tenant=CTX_A):
        from app import bot

        update = MagicMock()
        update.message.reply_text = AsyncMock()
        ctx = MagicMock()
        ctx.args = list(args)
        with patch.object(bot, "SessionLocal", return_value=db), \
             patch.object(bot, "current_context", return_value=tenant):
            await bot.cmd_calendrier(update, ctx)
        return update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_us213_ca2_bot_fixe_et_confirme(self, db):
        _referentiel(db, "chou", fenetres=PEPINIERE)
        texte = await self._appeler(db, "duree", "chou", "semis-godet", "10-15")
        assert "Semis → repiquage en godet" in texte
        assert "10 à 15 jours" in texte and "propre à votre potager" in texte
        assert _godet(db, "chou").affichage == "10 à 15 jours"

    @pytest.mark.asyncio
    async def test_us213_ca2_bot_refus_lisible_sur_culture_semee_en_place(self, db):
        _referentiel(db, "carotte", fenetres=EN_PLACE)
        texte = await self._appeler(db, "duree", "carotte", "semis-godet", "10")
        assert "❌" in texte and "Rien n'a été modifié" in texte

    @pytest.mark.asyncio
    async def test_us213_ca2_bot_valeur_mal_formee_ne_touche_a_rien(self, db):
        _referentiel(db, "chou", durees={"semis_godet": "10-15"}, fenetres=PEPINIERE)
        texte = await self._appeler(db, "duree", "chou", "semis-godet", "trois semaines")
        assert "❌" in texte
        assert _godet(db, "chou").affichage == "10 à 15 jours"

    @pytest.mark.asyncio
    async def test_us213_ca2_bot_l_usage_annonce_la_sous_commande(self, db):
        assert "semis-godet" in await self._appeler(db)


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — la dictée : le mot « godet » est exigé
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3Dictee:

    @pytest.mark.parametrize("phrase,jours_min,jours_max", [
        ("délai de repiquage en godet des choux : 10 à 15 jours", "10", "15"),
        ("les tomates se mettent en godet 15 à 20 jours après le semis", "15", "20"),
        ("délai entre le semis et le repiquage en godet des poireaux : 20 à 30 jours", "20", "30"),
        ("les choux se repiquent en godet au bout de 10 jours", "10", None),
        ("corrige le délai de mise en godet des tomates à 15 jours", "15", None),
        ("délai de repiquage en godet des tomates : 15 à 20 jours", "15", "20"),
    ])
    def test_us213_ca3_la_dictee_avec_godet_est_reconnue(self, phrase, jours_min, jours_max):
        candidate = interp.interpreter(phrase, None, False)
        assert candidate is not None, phrase
        assert (candidate.forme.commande, candidate.forme.sous_commande) == ("calendrier", "duree")
        assert candidate.valeurs["etape"] == "semis_godet"
        assert candidate.valeurs["jours_min"] == jours_min
        assert candidate.valeurs.get("jours_max") == jours_max

    def test_us213_ca3_gherkin_dictee_avec_godet_la_culture_est_nettoyee(self):
        candidate = interp.interpreter("délai de repiquage en godet des tomates : 15 à 20 jours", None, False)
        assert candidate.valeurs["culture"] == "tomates"

    def test_us213_ca3_gherkin_sans_godet_le_sens_actuel_est_garde(self):
        candidate = interp.interpreter("délai de repiquage des tomates : 42 à 56 jours", None, False)
        assert candidate.valeurs["etape"] == "repiquage"
        assert (candidate.valeurs["jours_min"], candidate.valeurs["jours_max"]) == ("42", "56")
        assert candidate.valeurs["culture"] == "tomates"

    def test_us213_ca3_delai_avant_plantation_n_est_pas_touche(self):
        candidate = interp.interpreter("délai avant plantation des tomates : 42 à 56 jours", None, False)
        assert candidate.valeurs["etape"] == "repiquage"

    def test_us213_ca3_la_regle_generique_ne_depend_pas_de_l_ordre(self):
        """La règle `calendrier_duree` refuse d'elle-même « … repiquage en godet … »."""
        generique = next(r for r in interp._REGLES if r.nom == "calendrier_duree")
        assert generique.motif.match(
            "delai de repiquage en godet des choux : 10 a 15 jours") is None
        assert generique.motif.match(
            "delai de repiquage des choux : 42 a 56 jours") is not None

    def test_us213_ca3_une_saisie_de_geste_reste_une_saisie(self):
        """« j'ai mis les tomates en godet » est un geste, pas un délai."""
        candidate = interp.interpreter("j'ai mis 20 tomates en godet", None, False)
        assert candidate is None or candidate.valeurs.get("etape") != "semis_godet"

    def test_us213_ca3_la_commande_dictee_produit_les_arguments_du_bot(self):
        """La phrase et la commande tapée mènent au MÊME handler, mêmes args."""
        candidate = interp.interpreter("délai de repiquage en godet des choux : 10 à 15 jours", None, False)
        args = list(candidate.args)
        assert args[0] == "duree" and args[1] in ("chou", "choux")
        assert cal.normaliser_etape(args[2]) == cal.ETAPE_SEMIS_GODET
        assert args[3:] == ["10", "15"]
        from app.bot import _decouper_correction
        decoupe = _decouper_correction(args[1:], cal.est_etape, cal.parser_duree)
        assert decoupe is not None and decoupe[0] == [args[1]]

    def test_us213_ca3_le_corpus_porte_les_deux_formes_cote_a_cote(self):
        lignes = CORPUS_DICTEE.read_text(encoding="utf-8").splitlines()
        avec = [i for i, l in enumerate(lignes) if "en godet des choux" in l and "calendrier duree" in l]
        sans = [i for i, l in enumerate(lignes) if "repiquage des tomates : 42" in l and "calendrier duree" in l]
        assert avec and sans
        assert abs(avec[0] - sans[0]) <= 6


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — lecture : bot, API de la culture, API du plan
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def _moteur_api():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def client_api(_moteur_api, monkeypatch):
    from app.api import main

    monkeypatch.setattr(main, "SessionLocal", sessionmaker(bind=_moteur_api))
    main.app.state.limiter.reset()
    with TestClient(main.app) as client:
        yield client


def _compte(moteur, email="jardinier@example.com"):
    from app.services import auth as svc_auth

    session = sessionmaker(bind=moteur)()
    user = svc_auth.inscrire_utilisateur(session, email, "motdepasse123")
    entete = {"Authorization": f"Bearer {svc_auth.creer_access_token(user.id)}"}
    session.close()
    return entete


class TestCA4Lecture:

    def test_us213_ca4_non_renseigne_quand_la_valeur_manque(self, db):
        _referentiel(db, "chou", durees={"levee": "10-15"}, fenetres=PEPINIERE)
        etape = _godet(db, "chou")
        assert etape.affichage == "non renseigné" and not etape.renseignee

    def test_us213_ca4_les_autres_etapes_gardent_le_tiret(self, db):
        """Aucune régression : seul le délai de godet dit « non renseigné »."""
        _referentiel(db, "chou", fenetres=PEPINIERE)
        it = cal.lire_calendrier(db, "chou", 1).itineraires[0]
        assert it.duree(cal.ETAPE_LEVEE).affichage == cal.TIRET
        assert it.duree(cal.ETAPE_REPIQUAGE).affichage == cal.TIRET

    @pytest.mark.asyncio
    async def test_us213_ca4_le_bot_l_affiche_pour_une_culture_de_pepiniere(self, db):
        _referentiel(db, "chou", durees={"semis_godet": "10-15"}, fenetres=PEPINIERE)
        texte = await TestCA2HandlerTelegram()._appeler(db, "chou")
        assert "Semis → repiquage en godet" in texte and "10 à 15 jours" in texte

    @pytest.mark.asyncio
    async def test_us213_ca4_gherkin_le_bot_dit_non_renseigne(self, db):
        _referentiel(db, "poireau", durees={"levee": "10-15"}, fenetres=PEPINIERE)
        texte = await TestCA2HandlerTelegram()._appeler(db, "poireau")
        assert "Semis → repiquage en godet : non renseigné" in texte

    @pytest.mark.asyncio
    async def test_us213_ca4_le_bot_ne_l_affiche_pas_pour_une_culture_semee_en_place(self, db):
        _referentiel(db, "carotte", fenetres=EN_PLACE)
        texte = await TestCA2HandlerTelegram()._appeler(db, "carotte")
        assert "godet" not in texte

    def test_us213_ca4_l_api_de_la_culture_l_expose_sans_rien_retirer(self, client_api, _moteur_api):
        entete = _compte(_moteur_api)
        client_api.post("/potagers", json={"nom": "Jardin"}, headers=entete)
        session = sessionmaker(bind=_moteur_api)()
        _referentiel(session, "chou", durees={"levee": "7-14", "semis_godet": "10-15"},
                     fenetres=PEPINIERE)
        session.close()

        corps = client_api.get("/cultures/chou/calendrier", headers=entete).json()
        durees = {d["etape"]: d for d in corps["itineraires"][0]["durees"]}
        assert durees["semis_godet"] == {
            "etape": "semis_godet", "jours_min": 10, "jours_max": 15,
            "mention": None, "affichage": "10 à 15 jours",
        }
        # Aucun champ ni aucune étape retirés ou renommés.
        assert {"levee", "recolte", "repiquage"} <= set(durees)
        assert set(corps) >= {"culture", "culture_connue", "zone_climatique", "itineraires"}

    def test_us213_ca4_l_api_de_la_culture_omet_l_etape_hors_pepiniere(self, client_api, _moteur_api):
        entete = _compte(_moteur_api)
        client_api.post("/potagers", json={"nom": "Jardin"}, headers=entete)
        session = sessionmaker(bind=_moteur_api)()
        _referentiel(session, "carotte", durees={"levee": "10", "recolte": "70-80"}, fenetres=EN_PLACE)
        session.close()

        corps = client_api.get("/cultures/carotte/calendrier", headers=entete).json()
        assert "semis_godet" not in [d["etape"] for d in corps["itineraires"][0]["durees"]]

    def test_us213_ca4_le_plan_l_expose_et_garde_ses_champs(self, client_api, _moteur_api):
        entete = _compte(_moteur_api)
        client_api.post("/potagers", json={"nom": "Jardin"}, headers=entete)
        session = sessionmaker(bind=_moteur_api)()
        _referentiel(session, "chou", durees={"recolte": "90-100", "semis_godet": "10-15"},
                     fenetres=PEPINIERE)
        _referentiel(session, "poireau", fenetres=PEPINIERE)
        _referentiel(session, "carotte", durees={"recolte": "70-80"}, fenetres=EN_PLACE)
        session.close()

        corps = client_api.get(
            "/plan/calendriers?culture=chou&culture=poireau&culture=carotte", headers=entete
        ).json()
        cultures = corps["cultures"]
        assert cultures["chou"]["duree_semis_godet"] == {
            "etape": "semis_godet", "jours_min": 10, "jours_max": 15,
            "mention": None, "affichage": "10 à 15 jours",
        }
        assert cultures["poireau"]["duree_semis_godet"]["affichage"] == "non renseigné"
        assert cultures["poireau"]["duree_semis_godet"]["jours_min"] is None
        assert cultures["carotte"]["duree_semis_godet"] is None
        # Champs historiques intacts (US-176) — aucun retiré, aucun renommé.
        assert cultures["chou"]["duree_recolte"] == "90 à 100 jours"
        assert {"culture_connue", "renseigne", "itineraire", "mois", "duree_recolte"} <= set(cultures["chou"])

    def test_us213_ca4_le_plan_d_une_culture_inconnue_porte_le_champ_a_none(self, db):
        corps = cal.calendriers_du_plan(db, ["inconnue"], 1)
        assert corps["cultures"]["inconnue"]["duree_semis_godet"] is None


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — jamais déduite
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5JamaisDeduite:

    def test_us213_ca5_gherkin_jamais_deduit_de_la_levee(self, db):
        _referentiel(db, "poireau", durees={"levee": "10-15"}, fenetres=PEPINIERE)
        etape = _godet(db, "poireau")
        assert etape.affichage == "non renseigné"
        assert etape.jours_min is None and etape.jours_max is None

    def test_us213_ca5_pas_deduit_du_delai_avant_plantation(self, db):
        _referentiel(db, "tomate", durees={"levee": "7-14", "repiquage": "42-56"},
                     fenetres=PEPINIERE)
        assert not _godet(db, "tomate").renseignee

    def test_us213_ca5_corriger_repiquage_ne_touche_pas_au_godet(self, db):
        _referentiel(db, "tomate", durees={"semis_godet": "15-20", "repiquage": "42-56"},
                     fenetres=PEPINIERE)
        cal.corriger_duree(db, CTX_A, "tomate", "repiquage", "40-50")
        assert _godet(db, "tomate").affichage == "15 à 20 jours"

    def test_us213_ca5_corriger_le_godet_ne_touche_pas_a_repiquage(self, db):
        _referentiel(db, "tomate", durees={"semis_godet": "15-20", "repiquage": "42-56"},
                     fenetres=PEPINIERE)
        cal.corriger_duree(db, CTX_A, "tomate", "semis-godet", "10-12")
        it = cal.lire_calendrier(db, "tomate", 1).itineraires[0]
        assert it.duree(cal.ETAPE_REPIQUAGE).affichage == "42 à 56 jours"

    def test_us213_ca5_l_adaptateur_wind_river_ne_la_produit_pas(self):
        """La source n'a pas de colonne pour ce délai : `repiquage` ne s'y recopie jamais."""
        manifeste = json.loads(MANIFESTE_WIND_RIVER.read_text(encoding="utf-8"))
        for entree in manifeste["cultures_calendriers"]:
            assert not (entree.get("durees") or {}).get("semis_godet"), entree["culture"]
        assert not hasattr(svc_adaptateur, "_retenir_semis_godet")


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — gabarit livré vide ; la source ne la porte pas
# ═════════════════════════════════════════════════════════════════════════════
class TestCA6Gabarit:

    def test_us213_ca6_le_gabarit_interne_expose_l_etape_vide(self):
        gabarit = json.loads(GABARIT_INTERNE.read_text(encoding="utf-8"))
        durees = [e["durees"] for e in gabarit["cultures_calendriers"]]
        assert durees
        assert all("semis_godet" in d for d in durees)
        assert all(d["semis_godet"] is None for d in durees)

    def test_us213_ca6_importer_le_gabarit_en_l_etat_n_ecrit_rien(self, db):
        gabarit = json.loads(GABARIT_INTERNE.read_text(encoding="utf-8"))
        _culture(db, gabarit["cultures_calendriers"][0]["culture"])
        svc_import.importer(db, gabarit)
        assert db.query(DureeCulturale).filter(
            DureeCulturale.etape == cal.ETAPE_SEMIS_GODET).count() == 0

    def test_us213_ca6_le_mode_d_emploi_du_gabarit_la_nomme(self):
        gabarit = json.loads(GABARIT_INTERNE.read_text(encoding="utf-8"))
        texte = "\n".join(gabarit["_lisez_moi"])
        assert "semis_godet" in texte and "jamais par un modèle de langage" in texte

    def test_us213_ca6_source_md_dit_que_la_source_ne_la_porte_pas(self):
        texte = SOURCE_MD.read_text(encoding="utf-8")
        assert "semis_godet" in texte
        ligne = next(l for l in texte.splitlines() if "repiquage en godet" in l and l.startswith("|"))
        assert "absente" in ligne


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — aucun calcul existant ne change
# ═════════════════════════════════════════════════════════════════════════════
class TestCA7AucunCalculTouche:

    def test_us213_ca7_les_projections_sont_identiques_avec_ou_sans_la_valeur(self, db):
        _referentiel(db, "chou", durees={"levee": "7-14", "recolte": "90-100"},
                     fenetres={"oceanique": {"semis_pepiniere": "février-avril",
                                             "recolte": "juillet-septembre"}})
        _evt(db, "semis", "chou", date(2026, 3, 1), contexte_semis="pepiniere")
        sans = rec.projections_du_plan(db, ["chou"], 1, date(2026, 4, 1))
        cal.corriger_duree(db, CTX_A, "chou", "semis_godet", "10-15")
        avec = rec.projections_du_plan(db, ["chou"], 1, date(2026, 4, 1))
        assert sans == avec

    def test_us213_ca7_le_plan_garde_la_meme_frise_et_la_meme_duree(self, db):
        _referentiel(db, "chou", durees={"recolte": "90-100"}, fenetres=PEPINIERE)
        avant = cal.calendriers_du_plan(db, ["chou"], 1)["cultures"]["chou"]
        cal.corriger_duree(db, CTX_A, "chou", "semis_godet", "10-15")
        apres = cal.calendriers_du_plan(db, ["chou"], 1)["cultures"]["chou"]
        for cle in ("mois", "duree_recolte", "renseigne", "itineraire"):
            assert avant[cle] == apres[cle], cle

    def test_us213_ca7_la_confiance_ne_lit_pas_l_etape(self):
        import inspect

        from app.services import confiance_semis, contexte_semis

        for module in (confiance_semis, contexte_semis, rec):
            assert "ETAPE_SEMIS_GODET" not in inspect.getsource(module), module.__name__

    def test_us213_ca7_aucune_ecriture_d_evenement(self, db):
        _referentiel(db, "chou", fenetres=PEPINIERE)
        avant = db.query(Evenement).count()
        cal.corriger_duree(db, CTX_A, "chou", "semis_godet", "10-15")
        assert db.query(Evenement).count() == avant


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — la documentation suit
# ═════════════════════════════════════════════════════════════════════════════
class TestCA8Documentation:

    def test_us213_ca8_la_fiche_du_corpus_parle_du_delai_de_godet(self):
        fiche = (RACINE / "data" / "connaissance" / "doc_app"
                 / "calendrier-et-zone-climatique.md").read_text(encoding="utf-8")
        assert "repiquage en godet" in fiche and "non renseigné" in fiche

    def test_us213_ca8_le_guide_utilisateur_donne_la_commande(self):
        guide = (RACINE / "data" / "connaissance" / "guide user"
                 / "guide assistant.md").read_text(encoding="utf-8")
        assert "/calendrier duree chou semis-godet 10-15" in guide

    def test_us213_ca8_la_fiche_de_domaine_porte_la_cinquieme_etape(self):
        fiche = (RACINE / "docs" / "domaines" / "calendrier-cultural.md").read_text(encoding="utf-8")
        assert "[US-213]" in fiche and "semis_godet" in fiche
        assert "repiquage" in fiche.split("[US-213]")[1][:1500]

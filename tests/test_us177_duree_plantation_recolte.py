"""
tests/test_us177_duree_plantation_recolte.py — Plantation → première récolte [US-177]
=====================================================================================

Un plant acheté en jardinerie n'a pas de semis : sans durée comptée depuis la
PLANTATION, il n'a aucune récolte attendue (US-070 / CA11). Cette suite couvre
les dix critères d'acceptance :

- CA1  quatrième étape de durée, en jours ou en mention, commune aux zones
- CA2  pré-remplie depuis la source là où elle compte depuis la plantation,
       JAMAIS par soustraction de `repiquage` à `recolte`
- CA3  portée par ce qui se plante, et par cela seulement — seule pour l'ail
- CA4  corrigeable au bot, locale au potager, jamais écrasée par l'import
- CA5  dictée reconnue, sans confusion avec `repiquage` ni avec une fenêtre
- CA6  forme de lecture de l'API, sans régression pour l'existant
- CA7  projection depuis la date réelle de plantation ; jamais empruntée
- CA8  le semis reste la référence quand il existe — règle à un seul endroit
- CA9  fiche d'aide relue (contrôlée par tests/test_us099_corpus_fonctionnement)
- CA10 ce fichier

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

CTX_A = TenantContext(user_id=1, potager_id=1, role="owner")
CTX_B = TenantContext(user_id=2, potager_id=2, role="owner")


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def db(test_db):
    """Deux potagers, trois parcelles — le décor de l'isolement (CA4)."""
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


def _evt(db, action, culture, jour, parcelle_id=1, **champs):
    evenement = Evenement(
        type_action=action, culture=culture,
        date=datetime.combine(jour, datetime.min.time()),
        parcelle_id=parcelle_id, potager_id=champs.pop("potager_id", 1), **champs,
    )
    db.add(evenement)
    db.commit()
    return evenement


def _projection(db, culture, date_ref, potager_id=1):
    projections = rec.projections_du_plan(db, [culture], potager_id, date_ref)
    assert len(projections) == 1, projections
    return projections[0]


def _lignes(nombre, **champs):
    return [dict(champs) for _ in range(nombre)]


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — une quatrième étape, de même nature que les trois autres
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1QuatriemeEtape:

    def test_us177_ca1_l_etape_existe_et_porte_un_libelle_sans_ambiguite(self):
        assert cal.ETAPE_PLANTATION_RECOLTE in cal.ETAPES
        libelle = cal.LIBELLES_ETAPES[cal.ETAPE_PLANTATION_RECOLTE]
        assert libelle == "Plantation → première récolte"
        # Le point de vigilance de l'US : impossible de la confondre en lisant
        # l'écran avec `repiquage`, qui se lit « semis → plantation en place ».
        assert libelle != cal.LIBELLES_ETAPES[cal.ETAPE_REPIQUAGE]
        assert all(v.startswith("Semis →") for e, v in cal.LIBELLES_ETAPES.items()
                   if e != cal.ETAPE_PLANTATION_RECOLTE)

    def test_us177_ca1_le_nom_stocke_tient_dans_la_colonne_sans_migration(self):
        """Aucune migration : `duree_culturale.etape` est un VARCHAR(20)."""
        assert len(cal.ETAPE_PLANTATION_RECOLTE) <= DureeCulturale.etape.type.length

    @pytest.mark.parametrize("saisi", [
        "plantation_recolte", "plantation-recolte", "Plantation Récolte",
        "plantation_premiere_recolte", "PLANTATION-RECOLTE",
    ])
    def test_us177_ca1_les_formes_saisies_se_ramenent_a_l_etape(self, saisi):
        assert cal.normaliser_etape(saisi) == cal.ETAPE_PLANTATION_RECOLTE
        assert cal.est_etape(saisi)

    def test_us177_ca1_plantation_seul_reste_le_repiquage(self):
        """« plantation » seul n'a pas changé de sens : semis → mise en place."""
        assert cal.normaliser_etape("plantation") == cal.ETAPE_REPIQUAGE

    def test_us177_ca1_fourchette_mention_et_commune_a_toutes_les_zones(self, db):
        _referentiel(db, "tomate",
                     durees={"plantation_recolte": "60-80"},
                     fenetres={"oceanique": {"plantation": "mai-juin"},
                               "mediterraneen": {"plantation": "avril-mai"}})
        for zone in ("oceanique", "mediterraneen"):
            db.get(Potager, 1).zone_climatique = zone
            db.commit()
            duree = cal.lire_calendrier(db, "tomate", 1).itineraires[0].duree(
                cal.ETAPE_PLANTATION_RECOLTE)
            assert (duree.jours_min, duree.jours_max) == (60, 80)
            assert duree.affichage == "60 à 80 jours"
        # Une seule ligne en base : la durée ne se répète pas par zone.
        assert db.query(DureeCulturale).filter(
            DureeCulturale.etape == cal.ETAPE_PLANTATION_RECOLTE).count() == 1

    def test_us177_ca1_une_mention_libre_est_acceptee(self, db):
        _referentiel(db, "rhubarbe", durees={"plantation_recolte": "vivace"},
                     fenetres={"oceanique": {"plantation": "novembre-mars"}})
        duree = cal.lire_calendrier(db, "rhubarbe", 1).itineraires[0].duree(
            cal.ETAPE_PLANTATION_RECOLTE)
        assert duree.affichage == "vivace" and duree.jours_min is None


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — pré-remplissage depuis la source, jamais par soustraction
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2PreRemplissage:

    def test_us177_ca2_gherkin_la_source_compte_depuis_la_plantation(self):
        """Gherkin 1 — tomate élevée à l'abri : `days_to_harvest` est repris."""
        par_culture = {"tomate": _lignes(
            5, sowing_method="Start indoors 6-8 weeks before last frost",
            days_to_germination="7-14", days_to_harvest="72")}
        resultat = svc_adaptateur.ResultatAdaptation()
        durees = svc_adaptateur.construire_calendriers(par_culture, resultat)[0]["durees"]
        assert durees["plantation_recolte"] == "72-72"
        # Et « semis → récolte » reste vide : la source ne compte pas depuis le semis.
        assert "recolte" not in durees

    def test_us177_ca2_gherkin_jamais_recolte_moins_repiquage(self):
        """Gherkin 1 (suite) — la valeur n'est pas une différence calculée."""
        par_culture = {"tomate": _lignes(
            5, sowing_method="Start indoors 6-8 weeks before last frost",
            days_to_germination="7-14", days_to_harvest="72")}
        resultat = svc_adaptateur.ResultatAdaptation()
        durees = svc_adaptateur.construire_calendriers(par_culture, resultat)[0]["durees"]
        repiquage_min, repiquage_max = (int(x) for x in durees["repiquage"].split("-"))
        plantation_min, plantation_max = (int(x) for x in durees["plantation_recolte"].split("-"))
        # 72 lu tel quel, et non 72 - 42 ni 72 - 56 : la valeur est une LECTURE.
        assert (plantation_min, plantation_max) == (72, 72)
        assert plantation_min != 72 - repiquage_min and plantation_max != 72 - repiquage_max

    def test_us177_ca2_semis_en_place_n_alimente_pas_cette_etape(self):
        """Semé en place : `days_to_harvest` compte depuis le semis — pas ici."""
        par_culture = {"carotte": _lignes(
            5, sowing_method="Direct sow", days_to_germination="10", days_to_harvest="70-80")}
        resultat = svc_adaptateur.ResultatAdaptation()
        durees = svc_adaptateur.construire_calendriers(par_culture, resultat)[0]["durees"]
        assert durees["recolte"] == "70-80"
        assert "plantation_recolte" not in durees

    def test_us177_ca2_mode_indetermine_n_alimente_rien(self):
        """La source ne dit pas depuis quand elle compte : on n'écrit rien."""
        lignes = [{"sowing_method": m, "days_to_germination": "10", "days_to_harvest": "70"}
                  for m in ("Direct sow", "Start indoors 6 weeks", "Direct sow", "Start indoors 6 weeks")]
        resultat = svc_adaptateur.ResultatAdaptation()
        entrees = svc_adaptateur.construire_calendriers({"chou": lignes}, resultat)
        durees = entrees[0]["durees"] if entrees else {}
        assert "plantation_recolte" not in durees

    def test_us177_ca2_memes_regles_de_rejet_que_les_autres_durees(self):
        """Source muette sur la durée : écartée et SIGNALÉE, jamais comblée."""
        par_culture = {"aubergine": _lignes(
            5, sowing_method="Start indoors 8 weeks before last frost",
            days_to_germination="10", days_to_harvest="")}
        resultat = svc_adaptateur.ResultatAdaptation()
        entrees = svc_adaptateur.construire_calendriers(par_culture, resultat)
        durees = entrees[0]["durees"] if entrees else {}
        assert "plantation_recolte" not in durees
        assert any("aubergine.plantation_recolte" in e for e in resultat.durees_ecartees)

    def test_us177_ca2_base_de_cultivars_trop_faible_n_ecrit_rien(self):
        """Un seul cultivar : le mode n'est pas établi, donc rien n'est écrit."""
        par_culture = {"aubergine": _lignes(
            1, sowing_method="Start indoors 8 weeks before last frost",
            days_to_germination="10", days_to_harvest="70")}
        resultat = svc_adaptateur.ResultatAdaptation()
        assert svc_adaptateur.construire_calendriers(par_culture, resultat) == []

    def test_us177_ca2_le_manifeste_versionne_porte_la_duree(self):
        """La donnée est LIVRÉE, pas seulement calculable."""
        manifeste = json.loads(MANIFESTE_WIND_RIVER.read_text(encoding="utf-8"))
        avec = {e["culture"]: e["durees"]["plantation_recolte"]
                for e in manifeste["cultures_calendriers"]
                if (e.get("durees") or {}).get("plantation_recolte")}
        assert "tomate" in avec, "la culture du Gherkin est pré-remplie"
        assert "ail" in avec, "[CA3] une culture qui se plante seule l'est aussi"
        for culture, valeur in avec.items():
            assert cal.parser_duree(valeur)[0] is not None, culture

    def test_us177_ca2_le_gabarit_interne_expose_l_etape_vide(self):
        """Le gabarit se remplit à la main, et il est livré VIDE."""
        gabarit = json.loads(GABARIT_INTERNE.read_text(encoding="utf-8"))
        durees = [e["durees"] for e in gabarit["cultures_calendriers"]]
        assert durees, "le gabarit porte des cultures"
        assert all("plantation_recolte" in d for d in durees)
        assert all(d["plantation_recolte"] is None for d in durees)


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — portée par ce qui se plante, et seulement par cela
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3PorteeDeLEtape:

    def test_us177_ca3_culture_semee_en_place_ne_porte_pas_l_etape(self, db):
        _referentiel(db, "carotte", durees={"levee": "10", "recolte": "70-80"},
                     fenetres={"oceanique": {"semis_pleine_terre": "mars-juin"}})
        etapes = [d.etape for d in cal.lire_calendrier(db, "carotte", 1).itineraires[0].durees]
        assert etapes == [cal.ETAPE_LEVEE, cal.ETAPE_RECOLTE]

    def test_us177_ca3_une_fenetre_de_plantation_suffit_a_la_porter(self, db):
        _referentiel(db, "tomate", durees={"levee": "7-14"},
                     fenetres={"oceanique": {"semis_pepiniere": "février-avril",
                                             "plantation": "mai-juin"}})
        durees = cal.lire_calendrier(db, "tomate", 1).itineraires[0].durees
        etape = next(d for d in durees if d.etape == cal.ETAPE_PLANTATION_RECOLTE)
        # Portée mais NON renseignée : un tiret, jamais une estimation (CA13 d'US-068).
        assert etape.affichage == cal.TIRET and not etape.renseignee

    def test_us177_ca3_gherkin_l_ail_la_porte_seule(self, db):
        """L'ail se plante sans se semer : ni levée, ni repiquage, mais celle-ci."""
        _referentiel(db, "ail", organe="végétatif",
                     durees={"plantation_recolte": "240-270"},
                     fenetres={"oceanique": {"plantation": "octobre-novembre",
                                             "recolte": "juin-juillet"}})
        it = cal.lire_calendrier(db, "ail", 1).itineraires[0]
        assert it.duree(cal.ETAPE_REPIQUAGE) is None
        assert it.duree(cal.ETAPE_PLANTATION_RECOLTE).affichage == "240 à 270 jours"
        assert it.duree(cal.ETAPE_LEVEE).affichage == cal.TIRET

    def test_us177_ca3_une_duree_renseignee_suffit_sans_fenetre(self, db):
        """Saisie au bot sans fenêtre de plantation au référentiel : elle reste lue."""
        _referentiel(db, "fraise", durees={"plantation_recolte": "90-120"})
        it = cal.lire_calendrier(db, "fraise", 1).itineraires[0]
        assert it.duree(cal.ETAPE_PLANTATION_RECOLTE).affichage == "90 à 120 jours"

    def test_us177_ca3_l_itineraire_implicite_ne_la_porte_pas(self, db):
        _culture(db, "topinambour")
        it = cal.lire_calendrier(db, "topinambour", 1).itineraires[0]
        assert it.implicite and it.duree(cal.ETAPE_PLANTATION_RECOLTE) is None


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — correction au bot, locale au potager, jamais écrasée
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4CorrectionAuBot:

    def test_us177_ca4_la_correction_confirme_les_deux_valeurs(self, db):
        _referentiel(db, "tomate", durees={"plantation_recolte": "60-80"},
                     fenetres={"oceanique": {"plantation": "mai-juin"}})
        assert cal.corriger_duree(db, CTX_A, "tomate", "plantation-recolte", "70 à 90") == (
            "60 à 80 jours", "70 à 90 jours")

    def test_us177_ca4_la_correction_est_locale_au_potager(self, db):
        _referentiel(db, "tomate", durees={"plantation_recolte": "60-80"},
                     fenetres={"oceanique": {"plantation": "mai-juin"}})
        cal.corriger_duree(db, CTX_A, "tomate", "plantation_recolte", "70-90")
        lu = lambda potager: cal.lire_calendrier(db, "tomate", potager).itineraires[0].duree(
            cal.ETAPE_PLANTATION_RECOLTE).affichage
        assert lu(1) == "70 à 90 jours"
        assert lu(2) == "60 à 80 jours", "le voisin garde le calendrier partagé"

    def test_us177_ca4_un_rejeu_de_l_import_n_ecrase_pas_la_correction(self, db):
        _referentiel(db, "tomate", durees={"plantation_recolte": "60-80"},
                     fenetres={"oceanique": {"plantation": "mai-juin"}})
        cal.corriger_duree(db, CTX_A, "tomate", "plantation_recolte", "70-90")
        _importer(db, {"culture": "tomate", "durees": {"plantation_recolte": "50-60"}})
        assert cal.lire_calendrier(db, "tomate", 1).itineraires[0].duree(
            cal.ETAPE_PLANTATION_RECOLTE).affichage == "70 à 90 jours"

    def test_us177_ca4_effacer_la_duree(self, db):
        _referentiel(db, "tomate", durees={"plantation_recolte": "60-80"},
                     fenetres={"oceanique": {"plantation": "mai-juin"}})
        assert cal.corriger_duree(db, CTX_A, "tomate", "plantation_recolte", "aucune")[1] == cal.TIRET

    def test_us177_ca4_refusee_sur_un_itineraire_qui_ne_se_plante_pas(self, db):
        """[CA3] Même garde que le repiquage, sur l'autre phase."""
        _referentiel(db, "carotte", durees={"recolte": "70-80"},
                     fenetres={"oceanique": {"semis_pleine_terre": "mars-juin"}})
        with pytest.raises(cal.ValeurCalendrierInvalideError) as err:
            cal.corriger_duree(db, CTX_A, "carotte", "plantation_recolte", "60-80")
        assert "ne se plante pas" in str(err.value)

    def test_us177_ca4_acceptee_sur_un_itineraire_sans_aucune_fenetre(self, db):
        """Un itinéraire vide ne préjuge de rien : le jardinier sait, lui."""
        _culture(db, "fraise")
        assert cal.corriger_duree(db, CTX_A, "fraise", "plantation_recolte", "90-120") == (
            cal.TIRET, "90 à 120 jours")

    def test_us177_ca4_le_decoupage_du_bot_reconnait_la_sous_commande(self):
        """Ce que fait `/calendrier duree tomate plantation-recolte 60-80`."""
        from app import bot

        decoupe = bot._decouper_correction(
            ["tomate", "plantation-recolte", "60-80"], cal.est_etape, cal.parser_duree)
        assert decoupe == (["tomate"], "plantation-recolte", "60-80")


class TestCA4HandlerTelegram:
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
    async def test_us177_ca4_bot_corrige_et_confirme(self, db):
        _referentiel(db, "tomate", durees={"plantation_recolte": "60-80"},
                     fenetres={"oceanique": {"plantation": "mai-juin"}})
        texte = await self._appeler(db, "duree", "tomate", "plantation-recolte", "70-90")
        assert "60 à 80 jours" in texte and "70 à 90 jours" in texte
        assert cal.lire_calendrier(db, "tomate", 2).itineraires[0].duree(
            cal.ETAPE_PLANTATION_RECOLTE).affichage == "60 à 80 jours"

    @pytest.mark.asyncio
    async def test_us177_ca4_bot_consultation_affiche_le_libelle(self, db):
        _referentiel(db, "ail", organe="végétatif", durees={"plantation_recolte": "240-270"},
                     fenetres={"oceanique": {"plantation": "octobre-novembre"}})
        texte = await self._appeler(db, "ail")
        assert "Plantation → première récolte" in texte
        assert "240 à 270 jours" in texte

    @pytest.mark.asyncio
    async def test_us177_ca4_bot_refus_lisible_sur_culture_semee_en_place(self, db):
        _referentiel(db, "carotte", durees={"recolte": "70-80"},
                     fenetres={"oceanique": {"semis_pleine_terre": "mars-juin"}})
        texte = await self._appeler(db, "duree", "carotte", "plantation_recolte", "60")
        assert "ne se plante pas" in texte
        assert db.query(DureeCulturale).filter(
            DureeCulturale.etape == cal.ETAPE_PLANTATION_RECOLTE).count() == 0

    @pytest.mark.asyncio
    async def test_us177_ca4_bot_valeur_mal_formee_ne_touche_a_rien(self, db):
        _referentiel(db, "tomate", durees={"plantation_recolte": "60-80"},
                     fenetres={"oceanique": {"plantation": "mai-juin"}})
        texte = await self._appeler(db, "duree", "tomate", "plantation-recolte", "trois semaines")
        assert "❌" in texte
        assert cal.lire_calendrier(db, "tomate", 1).itineraires[0].duree(
            cal.ETAPE_PLANTATION_RECOLTE).affichage == "60 à 80 jours"

    @pytest.mark.asyncio
    async def test_us177_ca4_bot_l_usage_annonce_la_sous_commande(self, db):
        assert "plantation-recolte" in await self._appeler(db)


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — la dictée, sans confusion possible
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5Dictee:

    @pytest.mark.parametrize("phrase", [
        "délai entre la plantation et la récolte des tomates : 60 à 80 jours",
        "delai entre plantation et recolte des tomates 60 a 80 jours",
        "durée de la plantation à la récolte de la tomate : 60 à 80 jours",
        "temps entre la mise en place et la première récolte des tomates : 60 à 80 jours",
    ])
    def test_us177_ca5_gherkin_la_dictee_est_reconnue(self, phrase):
        candidate = interp.interpreter(phrase)
        assert candidate is not None, phrase
        assert (candidate.forme.commande, candidate.forme.sous_commande) == ("calendrier", "duree")
        assert candidate.valeurs["etape"] == "plantation_recolte"
        assert candidate.valeurs["jours_min"] == "60"
        assert candidate.valeurs["jours_max"] == "80"

    def test_us177_ca5_gherkin_non_confondue_avec_le_repiquage(self):
        """« délai avant plantation » reste la durée semis → mise en place."""
        candidate = interp.interpreter("délai avant plantation des tomates : 42 à 56 jours")
        assert candidate.valeurs["etape"] == "repiquage"

    def test_us177_ca5_gherkin_non_confondue_avec_une_fenetre(self):
        """Des MOIS restent une fenêtre : la nature de la valeur tranche (CA29)."""
        candidate = interp.interpreter("plantation des poireaux : juin-juillet")
        assert candidate.forme.sous_commande == "fenetre"
        assert candidate.valeurs["phase"] == "plantation"

    def test_us177_ca5_la_commande_dictee_produit_les_arguments_du_bot(self):
        """La phrase et la commande tapée mènent au MÊME handler, mêmes args."""
        candidate = interp.interpreter(
            "délai entre la plantation et la récolte des tomates : 60 à 80 jours")
        args = list(candidate.args)
        # Le pluriel dicté traverse tel quel : c'est `fiches_visibles` qui le
        # ramène au singulier à la lecture (US-068), pas l'interpréteur.
        assert args[0] == "duree" and args[1] in ("tomate", "tomates")
        assert cal.normaliser_etape(args[2]) == cal.ETAPE_PLANTATION_RECOLTE
        assert args[3:] == ["60", "80"]
        from app.bot import _decouper_correction
        decoupe = _decouper_correction(
            args[1:], cal.est_etape, cal.parser_duree)
        assert decoupe is not None and decoupe[0] == [args[1]]


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — forme de lecture de l'API, sans régression
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


class TestCA6FormeDeLecture:

    def test_us177_ca6_l_api_rend_l_etape_comme_les_autres(self, client_api, _moteur_api):
        entete = _compte(_moteur_api)
        client_api.post("/potagers", json={"nom": "Jardin"}, headers=entete)
        session = sessionmaker(bind=_moteur_api)()
        _referentiel(session, "tomate", durees={"levee": "7-14", "plantation_recolte": "60-80"},
                     fenetres={"oceanique": {"semis_pepiniere": "février-avril",
                                             "plantation": "mai-juin"}})
        session.close()

        corps = client_api.get("/cultures/tomate/calendrier", headers=entete).json()
        durees = {d["etape"]: d for d in corps["itineraires"][0]["durees"]}
        assert durees["plantation_recolte"] == {
            "etape": "plantation_recolte", "jours_min": 60, "jours_max": 80,
            "mention": None, "affichage": "60 à 80 jours",
        }

    def test_us177_ca6_omise_pour_une_culture_qui_ne_se_plante_pas(self, client_api, _moteur_api):
        entete = _compte(_moteur_api)
        client_api.post("/potagers", json={"nom": "Jardin"}, headers=entete)
        session = sessionmaker(bind=_moteur_api)()
        _referentiel(session, "carotte", durees={"levee": "10", "recolte": "70-80"},
                     fenetres={"oceanique": {"semis_pleine_terre": "mars-juin"}})
        session.close()

        corps = client_api.get("/cultures/carotte/calendrier", headers=entete).json()
        etapes = [d["etape"] for d in corps["itineraires"][0]["durees"]]
        assert "plantation_recolte" not in etapes

    def test_us177_ca6_le_plan_sert_toujours_la_duree_depuis_le_semis(self, db):
        """Non-régression d'US-176 : `duree_recolte` n'a pas changé de sens."""
        _referentiel(db, "tomate", durees={"recolte": "100-110", "plantation_recolte": "60-80"},
                     fenetres={"oceanique": {"plantation": "mai-juin"}})
        corps = cal.calendriers_du_plan(db, ["tomate"], 1)
        assert corps["cultures"]["tomate"]["duree_recolte"] == "100 à 110 jours"


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — projection depuis la plantation réelle
# ═════════════════════════════════════════════════════════════════════════════
class TestCA7ProjectionDepuisLaPlantation:

    def test_us177_ca7_gherkin_plant_achete_recolte_projetee(self, db):
        """Gherkin 2 — tomate plantée le 10 mai, 60 à 80 jours : 9 → 29 juillet."""
        _referentiel(db, "tomate", durees={"plantation_recolte": "60-80"},
                     fenetres={"oceanique": {"plantation": "mai-juin"}})
        _evt(db, "plantation", "tomate", date(2026, 5, 10))

        projection = _projection(db, "tomate", date(2026, 6, 1))
        assert projection["etat"] == rec.ETAT_A_VENIR
        assert projection["origine"] == {"action": "plantation", "date": "2026-05-10",
                                         "contexte": None}
        assert projection["recolte_attendue"] == {"debut": "2026-07-09", "fin": "2026-07-29"}

    def test_us177_ca7_gherkin_sans_duree_aucune_projection_empruntee(self, db):
        """Gherkin 5 — poireau planté le 3 juin, durée absente : mode dégradé."""
        _referentiel(db, "poireau", durees={"levee": "14-21", "recolte": "150-180"},
                     fenetres={"oceanique": {"semis_pepiniere": "février-avril",
                                             "plantation": "mai-juillet"}})
        _evt(db, "plantation", "poireau", date(2026, 6, 3))

        projection = _projection(db, "poireau", date(2026, 7, 1))
        assert projection["etat"] == rec.ETAT_SANS_RECALAGE
        assert projection["motif"] == rec.MOTIF_PLANTATION_SANS_SEMIS
        assert projection["recolte_attendue"] is None
        # Surtout pas la durée semis → récolte appliquée à la plantation.
        assert projection["jours_restants"] is None

    def test_us177_ca7_aucune_levee_annoncee_pour_un_plant(self, db):
        """Un plant a déjà levé : lui promettre une levée serait faux."""
        _referentiel(db, "tomate", durees={"levee": "7-14", "plantation_recolte": "60-80"},
                     fenetres={"oceanique": {"plantation": "mai-juin"}})
        _evt(db, "plantation", "tomate", date(2026, 5, 10))
        projection = _projection(db, "tomate", date(2026, 6, 1))
        assert projection["levee_attendue"] is None
        assert projection["decalage_plantation_jours"] is None

    def test_us177_ca7_la_frise_marque_la_plantation_et_la_croissance(self, db):
        _referentiel(db, "tomate", durees={"plantation_recolte": "60-80"},
                     fenetres={"oceanique": {"plantation": "mai-juin", "recolte": "juillet-septembre"}})
        _evt(db, "plantation", "tomate", date(2026, 5, 10))
        mois = _projection(db, "tomate", date(2026, 6, 1))["mois"]
        assert mois["plantation"] == [5]
        assert mois["semis_pepiniere"] == [] and mois["semis_pleine_terre"] == []
        assert 6 in mois["croissance"] and 7 in mois["recolte"]

    def test_us177_ca7_une_recolte_reelle_prime_sur_l_attendu(self, db):
        _referentiel(db, "tomate", durees={"plantation_recolte": "60-80"},
                     fenetres={"oceanique": {"plantation": "mai-juin"}})
        _evt(db, "plantation", "tomate", date(2026, 5, 10))
        _evt(db, "recolte", "tomate", date(2026, 7, 15))
        projection = _projection(db, "tomate", date(2026, 7, 20))
        assert projection["etat"] == rec.ETAT_EN_RECOLTE
        assert projection["recolte_reelle"]["premiere"] == "2026-07-15"

    def test_us177_ca7_aucune_ecriture(self, db):
        _referentiel(db, "tomate", durees={"plantation_recolte": "60-80"},
                     fenetres={"oceanique": {"plantation": "mai-juin"}})
        _evt(db, "plantation", "tomate", date(2026, 5, 10))
        avant = db.query(Evenement).count(), db.query(DureeCulturale).count()
        _projection(db, "tomate", date(2026, 6, 1))
        assert (db.query(Evenement).count(), db.query(DureeCulturale).count()) == avant


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — le semis reste la référence, et la règle vit à un seul endroit
# ═════════════════════════════════════════════════════════════════════════════
class TestCA8PrioriteDuSemis:

    def _tomate(self, db):
        _referentiel(db, "tomate",
                     durees={"levee": "7-14", "recolte": "100-110", "repiquage": "42-56",
                             "plantation_recolte": "60-80"},
                     fenetres={"oceanique": {"semis_pepiniere": "février-avril",
                                             "plantation": "mai-juin"}})

    def test_us177_ca8_gherkin_semis_chaine_le_semis_fait_foi(self, db):
        """Gherkin 3 — semée en godet le 15 mars, plantée le 10 mai."""
        self._tomate(db)
        semis = _evt(db, "semis", "tomate", date(2026, 3, 15), parcelle_id=2,
                     contexte_semis="pepiniere")
        godet = _evt(db, "mise_en_godet", "tomate", date(2026, 4, 10), parcelle_id=2,
                     origine_graines_id=semis.id)
        _evt(db, "plantation", "tomate", date(2026, 5, 10),
             source_evenement_ids=str(godet.id))

        projection = _projection(db, "tomate", date(2026, 6, 1))
        assert projection["origine"]["date"] == "2026-03-15"
        # 100-110 jours depuis le SEMIS, pas 60-80 depuis la plantation.
        assert projection["recolte_attendue"]["debut"] == "2026-06-23"
        assert projection["levee_attendue"] is not None

    def test_us177_ca8_la_regle_vit_dans_ancrer_serie(self, db):
        """La priorité est une fonction, pas une condition dispersée."""
        self._tomate(db)
        it = cal.lire_calendrier(db, "tomate", 1).itineraires[0]
        semis = rec.Geste(id=1, action="semis", jour=date(2026, 3, 15), parcelle_id=1,
                          culture="tomate", contexte_semis="pepiniere")
        plantation = rec.Geste(id=2, action="plantation", jour=date(2026, 5, 10),
                               parcelle_id=1, culture="tomate")

        avec_semis, _ = rec.ancrer_serie(
            rec.Serie(semis=semis, plantation=plantation, contexte="pepiniere"), it)
        assert (avec_semis.mode, avec_semis.depart) == (rec.ORIGINE_SEMIS, date(2026, 3, 15))
        assert avec_semis.duree_recolte == (100, 110)

        sans_semis, _ = rec.ancrer_serie(
            rec.Serie(semis=None, plantation=plantation, contexte=None), it)
        assert (sans_semis.mode, sans_semis.depart) == (rec.ORIGINE_PLANTATION, date(2026, 5, 10))
        assert sans_semis.duree_recolte == (60, 80)

    def test_us177_ca8_un_semis_sans_duree_n_emprunte_pas_celle_de_la_plantation(self, db):
        """Les deux ne comptent pas depuis le même geste : pas de repli."""
        _referentiel(db, "tomate", durees={"plantation_recolte": "60-80"},
                     fenetres={"oceanique": {"semis_pepiniere": "février-avril",
                                             "plantation": "mai-juin"}})
        _evt(db, "semis", "tomate", date(2026, 3, 15), contexte_semis="pepiniere")
        projection = _projection(db, "tomate", date(2026, 6, 1))
        assert projection["etat"] == rec.ETAT_SANS_RECALAGE
        assert projection["motif"] == rec.MOTIF_DUREE_RECOLTE_ABSENTE

    def test_us177_ca8_un_semis_sans_contexte_reste_degrade(self, db):
        """Non-régression d'US-070 / CA11 : rien n'est deviné."""
        self._tomate(db)
        _evt(db, "semis", "tomate", date(2026, 3, 15))
        projection = _projection(db, "tomate", date(2026, 6, 1))
        assert projection["motif"] == rec.MOTIF_CONTEXTE_INCONNU

    def test_us177_ca8_sans_referentiel_rien_n_est_projete(self, db):
        _culture(db, "topinambour")
        _evt(db, "plantation", "topinambour", date(2026, 5, 10))
        projection = _projection(db, "topinambour", date(2026, 6, 1))
        assert projection["motif"] == rec.MOTIF_REFERENTIEL_ABSENT

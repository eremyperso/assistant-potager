"""
tests/test_us068_calendrier_cultural.py — Référentiel de calendrier cultural [US-068]
====================================================================================

Couvre les seize critères d'acceptance et les sept scénarios Gherkin :

- CA1  une culture, un ou plusieurs itinéraires ; l'implicite « standard »
- CA2  trois fenêtres indépendantes, chacune pouvant être vide
- CA3  levée / récolte / repiquage (pépinière seulement)
- CA4  jours, fourchettes, mention libre — jamais une date
- CA5  aucune colonne d'écartement dupliquée
- CA6  fenêtres par zone, durées communes
- CA7  zone du potager : choisie > localisation > défaut, modifiable
- CA8  potager sans zone pleinement fonctionnel
- CA9  pré-remplissage : cultures existantes seulement, jamais d'écrasement
- CA10 correction au bot, ancienne et nouvelle valeur confirmées
- CA11 correction isolée au potager
- CA12 casse et accents indifférents
- CA13 rien d'inventé : frise neutre, durée en tiret
- CA14 création de culture à la volée sans calendrier
- CA15 non-régression des lectures de `culture_config`
- CA16 ce fichier

Les valeurs de fenêtres et de durées écrites ici sont des VALEURS DE TEST : elles
n'engagent aucune agronomie, et ne constituent pas un pré-remplissage.
"""
from __future__ import annotations

import csv
import json
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
from app.services import potagers as svc_potagers
from app.services import referentiel_sources as svc_sources
from app.services.context import TenantContext
from app.services.permissions import PermissionInsuffisanteError, PotagerArchiveError
from database.db import Base
from database.models import (
    CultureConfig,
    DureeCulturale,
    FenetreCulturale,
    ItineraireCultural,
    Potager,
    PotagerMembre,
    User,
)

RACINE = Path(__file__).resolve().parent.parent
MANIFESTE_WIND_RIVER = RACINE / "data" / "referentiel" / "wind_river_attributs.json"
GABARIT_INTERNE = RACINE / "data" / "referentiel" / "calendrier_redaction_interne.json"


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def db(test_db):
    """Deux potagers, deux jardiniers — le décor de l'isolement (CA11)."""
    test_db.add_all([User(id=1, email="a@potager.test"), User(id=2, email="b@potager.test")])
    test_db.flush()
    test_db.add_all([
        Potager(id=1, nom="Jardin A", proprietaire_id=1),
        Potager(id=2, nom="Jardin B", proprietaire_id=2),
    ])
    test_db.commit()
    return test_db


CTX_A = TenantContext(user_id=1, potager_id=1, role="owner")
CTX_B = TenantContext(user_id=2, potager_id=2, role="owner")


def _culture(db, nom, potager_id=None, type_organe="reproducteur"):
    config = CultureConfig(nom=nom, type_organe_recolte=type_organe, potager_id=potager_id)
    db.add(config)
    db.commit()
    return config


def _source_test():
    return {
        "code": "wikidata", "libelle": "Wikidata", "licence": "CC0",
        "attribution": "Wikidata — CC0 1.0 Universal (domaine public)",
        "url": "https://www.wikidata.org/", "partageable": True,
    }


def _manifeste(*entrees):
    return {"source": _source_test(), "cultures_calendriers": list(entrees)}


def _importer(db, *entrees):
    return svc_import.importer(db, _manifeste(*entrees))


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — itinéraires culturaux
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1Itineraires:

    def test_us068_ca1_culture_sans_itineraire_porte_un_standard_implicite(self, db):
        _culture(db, "topinambour")
        calendrier = cal.lire_calendrier(db, "topinambour", 1)
        assert calendrier.culture_connue
        assert [it.nom for it in calendrier.itineraires] == ["standard"]
        assert calendrier.itineraires[0].implicite
        assert not calendrier.renseigne
        # Aucune ligne n'a été créée pour cet itinéraire implicite.
        assert db.query(ItineraireCultural).count() == 0

    def test_us068_gherkin_deux_itineraires_pour_une_meme_culture(self, db):
        """Gherkin 1 — chou-fleur précoce et d'hiver, fenêtres et durées propres."""
        _culture(db, "chou-fleur")
        _importer(
            db,
            {"culture": "chou-fleur", "itineraire": "culture précoce",
             "durees": {"recolte": "90-100"},
             "fenetres": {"oceanique": {"semis_pepiniere": "février-mars", "recolte": "juin-juillet"}}},
            {"culture": "chou-fleur", "itineraire": "culture d'hiver",
             "durees": {"recolte": "180-240"},
             "fenetres": {"oceanique": {"semis_pepiniere": "mai-juin", "recolte": "novembre-mars"}}},
        )
        calendrier = cal.lire_calendrier(db, "chou-fleur", 1)
        noms = {it.nom for it in calendrier.itineraires}
        assert noms == {"culture précoce", "culture d'hiver"}
        hiver = next(it for it in calendrier.itineraires if it.nom == "culture d'hiver")
        precoce = next(it for it in calendrier.itineraires if it.nom == "culture précoce")
        assert hiver.fenetre(cal.PHASE_RECOLTE).mois == [11, 12, 1, 2, 3]
        assert precoce.fenetre(cal.PHASE_RECOLTE).mois == [6, 7]
        assert hiver.duree(cal.ETAPE_RECOLTE).affichage == "180 à 240 jours"
        assert precoce.duree(cal.ETAPE_RECOLTE).affichage == "90 à 100 jours"

    def test_us068_ca1_le_standard_se_lit_en_premier(self, db):
        _culture(db, "carotte")
        _importer(
            db,
            {"culture": "carotte", "itineraire": "carotte d'hiver", "durees": {"levee": "15"}},
            {"culture": "carotte", "durees": {"levee": "10"}},
        )
        noms = [it.nom for it in cal.lire_calendrier(db, "carotte", 1).itineraires]
        assert noms[0] == "standard"

    def test_us068_ca1_nom_d_itineraire_casse_et_apostrophe_indifferentes(self):
        assert cal.normaliser_itineraire("Culture d’Hiver") == cal.normaliser_itineraire("culture d'hiver")
        assert cal.normaliser_itineraire(None) == "standard"


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — fenêtres
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2Fenetres:

    def test_us068_gherkin_culture_semee_uniquement_en_pleine_terre(self, db):
        """Gherkin 2 — pas de fenêtre de pépinière pour la carotte."""
        _culture(db, "carotte")
        _importer(db, {"culture": "carotte", "fenetres": {"oceanique": {
            "semis_pepiniere": None, "semis_pleine_terre": "mars-juin", "recolte": "juin-octobre"}}})
        it = cal.lire_calendrier(db, "carotte", 1).itineraires[0]
        assert [f.phase for f in it.fenetres] == [cal.PHASE_SEMIS_PLEINE_TERRE, cal.PHASE_RECOLTE]
        assert it.fenetre(cal.PHASE_SEMIS_PEPINIERE) is None
        # Pas de pépinière, donc pas de délai de repiquage proposé (CA3).
        assert [d.etape for d in it.durees] == [cal.ETAPE_LEVEE, cal.ETAPE_RECOLTE]

    def test_us068_ca2_vivace_avec_une_seule_fenetre_de_recolte(self, db):
        _culture(db, "asperge")
        _importer(db, {"culture": "asperge", "durees": {"recolte": "vivace"},
                       "fenetres": {"oceanique": {"recolte": "avril-juin"}}})
        it = cal.lire_calendrier(db, "asperge", 1).itineraires[0]
        assert [f.phase for f in it.fenetres] == [cal.PHASE_RECOLTE]
        assert it.duree(cal.ETAPE_RECOLTE).affichage == "vivace"

    @pytest.mark.parametrize("saisie, attendu", [
        ("mars-mai", (3, 5)), ("mars à mai", (3, 5)), ("novembre → février", (11, 2)),
        ("juin", (6, 6)), ("02-04", (2, 4)), ("février avril", (2, 4)), ("Sept - Oct", (9, 10)),
        ([3, 5], (3, 5)), ("aucune", None), (None, None),
    ])
    def test_us068_ca2_lecture_d_une_fenetre(self, saisie, attendu):
        assert cal.parser_fenetre(saisie) == attendu

    @pytest.mark.parametrize("saisie", ["mars-mai-juin", "printemps", "jui", "13"])
    def test_us068_ca2_fenetre_mal_formee_refusee(self, saisie):
        with pytest.raises(cal.ValeurCalendrierInvalideError):
            cal.parser_fenetre(saisie)

    def test_us068_ca2_fenetre_chevauchant_l_annee(self):
        assert cal.mois_couverts(11, 2) == [11, 12, 1, 2]
        assert cal.formater_fenetre(11, 2) == "novembre → février"
        assert cal.formater_fenetre(6, 6) == "juin"


# ═════════════════════════════════════════════════════════════════════════════
# CA3, CA4 — durées
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3CA4Durees:

    @pytest.mark.parametrize("saisie, attendu", [
        ("10", (10, 10, None)), ("70-90", (70, 90, None)), ("70 à 90 jours", (70, 90, None)),
        ("14 21", (14, 21, None)), (95, (95, 95, None)), ([7, 14], (7, 14, None)),
        ("vivace", (None, None, "vivace")), ("aucune", None),
    ])
    def test_us068_ca4_lecture_d_une_duree(self, saisie, attendu):
        assert cal.parser_duree(saisie) == attendu

    @pytest.mark.parametrize("saisie", ["90-70", "3 semaines", "0", "1000", True])
    def test_us068_ca4_duree_invraisemblable_ou_mal_formee_refusee(self, saisie):
        with pytest.raises(cal.ValeurCalendrierInvalideError):
            cal.parser_duree(saisie)

    def test_us068_ca4_une_fourchette_n_est_jamais_une_date(self):
        assert cal.formater_duree(70, 90) == "70 à 90 jours"
        assert cal.formater_duree(1, 1) == "1 jour"
        assert cal.formater_duree(None, None) == cal.TIRET
        assert cal.formater_duree(None, None, "vivace") == "vivace"

    def test_us068_ca3_repiquage_propose_pour_un_itineraire_en_pepiniere(self, db):
        _culture(db, "tomate")
        _importer(db, {"culture": "tomate", "fenetres": {"oceanique": {"semis_pepiniere": "mars-avril"}}})
        it = cal.lire_calendrier(db, "tomate", 1).itineraires[0]
        assert [d.etape for d in it.durees] == [cal.ETAPE_LEVEE, cal.ETAPE_RECOLTE, cal.ETAPE_REPIQUAGE]

    def test_us068_ca3_repiquage_refuse_sans_pepiniere(self, db):
        _culture(db, "carotte")
        _importer(db, {"culture": "carotte", "fenetres": {"oceanique": {"semis_pleine_terre": "mars-juin"}}})
        with pytest.raises(cal.ValeurCalendrierInvalideError, match="pépinière"):
            cal.corriger_duree(db, CTX_A, "carotte", "repiquage", "30")
        # La copie personnalisée n'a pas survécu au refus.
        assert db.query(ItineraireCultural).filter(ItineraireCultural.potager_id == 1).count() == 0


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — pas d'écartement dupliqué
# ═════════════════════════════════════════════════════════════════════════════
def test_us068_ca5_aucune_colonne_d_ecartement_dans_le_referentiel():
    for modele in (ItineraireCultural, FenetreCulturale, DureeCulturale):
        colonnes = set(modele.__table__.columns.keys())
        assert not {c for c in colonnes if "espacement" in c or "surface" in c}
    assert {"espacement", "surface_m2"} <= set(CultureConfig.__table__.columns.keys())


# ═════════════════════════════════════════════════════════════════════════════
# CA6, CA7, CA8 — zone climatique
# ═════════════════════════════════════════════════════════════════════════════
class TestZoneClimatique:

    def _courgette(self, db):
        _culture(db, "courgette")
        _importer(db, {"culture": "courgette", "durees": {"recolte": "95"}, "fenetres": {
            "continental": {"semis_pleine_terre": "mai-juin"},
            "mediterraneen": {"semis_pleine_terre": "avril-mai"},
        }})

    def test_us068_gherkin_fenetres_decalees_selon_la_zone(self, db):
        """Gherkin 3 — un potager méditerranéen sème la courgette en avril."""
        self._courgette(db)
        db.get(Potager, 1).zone_climatique = "mediterraneen"
        db.commit()
        fenetre = cal.lire_calendrier(db, "courgette", 1).itineraires[0].fenetre(cal.PHASE_SEMIS_PLEINE_TERRE)
        assert fenetre.mois_debut == 4

    def test_us068_gherkin_duree_identique_quelle_que_soit_la_zone(self, db):
        """Gherkin 4 — 95 jours pour les deux potagers, de zones différentes."""
        self._courgette(db)
        db.get(Potager, 1).zone_climatique = "mediterraneen"
        db.get(Potager, 2).zone_climatique = "continental"
        db.commit()
        durees = {
            cal.lire_calendrier(db, "courgette", pid).itineraires[0].duree(cal.ETAPE_RECOLTE).jours_min
            for pid in (1, 2)
        }
        assert durees == {95}

    def test_us068_gherkin_potager_sans_zone_lit_la_zone_par_defaut(self, db):
        """Gherkin 5 — pas de zone, pas de localisation : zone par défaut, sans erreur."""
        self._courgette(db)
        with patch("app.config.CALENDRIER_ZONE_DEFAUT", "continental"):
            calendrier = cal.lire_calendrier(db, "courgette", 1)
        assert (calendrier.zone, calendrier.zone_origine) == ("continental", cal.ORIGINE_ZONE_DEFAUT)
        assert calendrier.itineraires[0].fenetre(cal.PHASE_SEMIS_PLEINE_TERRE).mois_debut == 5

    def test_us068_ca8_zone_par_defaut_hors_vocabulaire_retombe_sur_oceanique(self):
        with patch("app.config.CALENDRIER_ZONE_DEFAUT", "tropical"):
            assert cal.zone_par_defaut() == "oceanique"

    def test_us068_ca8_potager_inexistant_ne_bloque_rien(self, db):
        _culture(db, "tomate")
        calendrier = cal.lire_calendrier(db, "tomate", 999)
        assert calendrier.zone_origine == cal.ORIGINE_ZONE_DEFAUT

    def test_us068_ca13_aucune_fenetre_empruntee_a_une_autre_zone(self, db):
        self._courgette(db)
        db.get(Potager, 1).zone_climatique = "montagnard"
        db.commit()
        it = cal.lire_calendrier(db, "courgette", 1).itineraires[0]
        assert it.fenetres == []
        assert set(it.zones_renseignees) == {"continental", "mediterraneen"}
        assert all(phases == [] for phases in it.frise().values())

    @pytest.mark.parametrize("lat, lon, attendu", [
        (43.61, 3.88, "mediterraneen"),   # Montpellier
        (43.30, 5.37, "mediterraneen"),   # Marseille
        (42.15, 9.10, "mediterraneen"),   # Corse
        (48.58, 7.75, "continental"),     # Strasbourg
        (47.32, 5.04, "continental"),     # Dijon
        (48.85, 2.35, "oceanique"),       # Paris
        (47.22, -1.55, "oceanique"),      # Nantes
        (43.60, 1.44, "oceanique"),       # Toulouse
        (40.71, -74.0, None),             # hors de France
        (None, 2.35, None),
    ])
    def test_us068_ca7_zone_deduite_de_la_localisation(self, lat, lon, attendu):
        assert cal.zone_depuis_localisation(lat, lon) == attendu

    def test_us068_ca7_montagnard_n_est_jamais_suppose(self):
        # Chamonix : la position seule ne dit rien de l'altitude.
        assert cal.zone_depuis_localisation(45.92, 6.87) != "montagnard"

    def test_us068_ca7_le_choix_du_jardinier_prime_sur_la_localisation(self, db):
        potager = db.get(Potager, 1)
        potager.latitude, potager.longitude = 43.30, 5.37
        db.commit()
        assert cal.zone_effective(potager) == ("mediterraneen", cal.ORIGINE_ZONE_LOCALISATION)

        avant, apres = cal.definir_zone(db, CTX_A, "Montagne")
        assert avant == ("mediterraneen", cal.ORIGINE_ZONE_LOCALISATION)
        assert apres == ("montagnard", cal.ORIGINE_ZONE_JARDINIER)

        _, retour = cal.definir_zone(db, CTX_A, "auto")
        assert retour == ("mediterraneen", cal.ORIGINE_ZONE_LOCALISATION)
        assert db.get(Potager, 1).zone_climatique is None

    def test_us068_ca7_zone_hors_vocabulaire_refusee_sans_ecriture(self, db):
        with pytest.raises(cal.ValeurCalendrierInvalideError):
            cal.definir_zone(db, CTX_A, "tropical")
        assert db.get(Potager, 1).zone_climatique is None

    def test_us068_ca7_seul_le_proprietaire_change_la_zone(self, db):
        editeur = TenantContext(user_id=2, potager_id=1, role="editor")
        with pytest.raises(PermissionInsuffisanteError):
            cal.definir_zone(db, editeur, "continental")

    def test_us068_ca7_zone_refusee_sur_un_potager_archive(self, db):
        db.get(Potager, 1).etat = "archive"
        db.commit()
        with pytest.raises(PotagerArchiveError):
            cal.definir_zone(db, CTX_A, "continental")

    def test_us068_ca7_libelle_dit_l_origine_de_la_zone(self):
        # [US-193] Le choix du jardinier se dit aussi, comme les deux autres origines.
        assert cal.libelle_zone("mediterraneen", cal.ORIGINE_ZONE_JARDINIER) == "méditerranéen (choix du jardinier)"
        assert "localisation" in cal.libelle_zone("oceanique", cal.ORIGINE_ZONE_LOCALISATION)
        assert "par défaut" in cal.libelle_zone("oceanique", cal.ORIGINE_ZONE_DEFAUT)


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — pré-remplissage
# ═════════════════════════════════════════════════════════════════════════════
class TestCA9PreRemplissage:

    def test_us068_ca9_import_ecrit_le_partage_avec_son_origine(self, db):
        _culture(db, "haricot")
        resultat = _importer(db, {"culture": "haricot", "durees": {"levee": "7-10", "recolte": "56-60"},
                                  "fenetres": {"oceanique": {"semis_pleine_terre": "mai-juillet"}}})
        assert resultat.calendriers_itineraires_crees == ["haricot / standard"]
        assert len(resultat.calendriers_valeurs_ecrites) == 3
        source = svc_sources.get_source(db, "wikidata")
        for modele in (ItineraireCultural, FenetreCulturale, DureeCulturale):
            lignes = db.query(modele).all()
            assert lignes and all(l.potager_id is None and l.source_id == source.id for l in lignes)
        calendrier = cal.lire_calendrier(db, "haricot", 1)
        assert "Wikidata" in " ".join(calendrier.attributions)

    def test_us068_ca9_aucune_culture_creee(self, db):
        resultat = _importer(db, {"culture": "kiwano", "durees": {"levee": "10"}})
        assert resultat.cultures_ignorees == ["kiwano"]
        assert db.query(CultureConfig).count() == 0
        assert db.query(ItineraireCultural).count() == 0

    def test_us068_ca9_culture_creee_pour_un_potager_est_pre_remplie(self, db):
        """Une culture dictée naît rattachée à son potager : l'import la voit."""
        _culture(db, "courgette", potager_id=1)
        _importer(db, {"culture": "courgette", "durees": {"levee": "7-10"}})
        assert cal.lire_calendrier(db, "courgette", 1).itineraires[0].duree(cal.ETAPE_LEVEE).jours_min == 7
        # Le potager B ne voit pas la fiche du potager A, ni donc son calendrier.
        assert not cal.lire_calendrier(db, "courgette", 2).culture_connue

    def test_us068_ca9_rejeu_idempotent(self, db):
        _culture(db, "haricot")
        entree = {"culture": "haricot", "durees": {"levee": "7-10"},
                  "fenetres": {"oceanique": {"semis_pleine_terre": "mai-juillet"}}}
        _importer(db, entree)
        second = _importer(db, entree)
        assert second.calendriers_itineraires_crees == []
        assert second.calendriers_valeurs_ecrites == []
        assert db.query(FenetreCulturale).count() == 1
        assert db.query(DureeCulturale).count() == 1

    def test_us068_ca9_une_autre_origine_n_est_jamais_ecrasee(self, db):
        _culture(db, "haricot")
        _importer(db, {"culture": "haricot", "durees": {"levee": "7-10"}})
        manifeste = {
            "source": {"code": "redaction_interne"},
            "cultures_calendriers": [{"culture": "haricot", "durees": {"levee": "5-8", "recolte": "60"}}],
        }
        resultat = svc_import.importer(db, manifeste)
        assert resultat.calendriers_valeurs_preservees == ["haricot / standard / levee"]
        assert resultat.calendriers_valeurs_ecrites == ["haricot / standard / recolte"]
        levee = db.query(DureeCulturale).filter(DureeCulturale.etape == "levee").one()
        assert (levee.jours_min, levee.jours_max) == (7, 10)

    def test_us068_ca9_n_ecrase_jamais_une_correction_du_jardinier(self, db):
        _culture(db, "tomate")
        _importer(db, {"culture": "tomate", "fenetres": {"oceanique": {"semis_pepiniere": "mars-avril"}}})
        cal.corriger_fenetre(db, CTX_A, "tomate", "pepiniere", "février-avril")
        _importer(db, {"culture": "tomate", "fenetres": {"oceanique": {"semis_pepiniere": "avril-mai"}}})
        assert cal.lire_calendrier(db, "tomate", 1).itineraires[0].fenetre(
            cal.PHASE_SEMIS_PEPINIERE).mois_debut == 2

    def test_us068_ca9_valeur_mal_formee_refusee_sans_bloquer_ses_voisines(self, db):
        _culture(db, "carotte")
        resultat = _importer(db, {"culture": "carotte", "durees": {"levee": "trois semaines", "recolte": "70-80"},
                                  "fenetres": {"tropical": {"recolte": "mai"},
                                               "oceanique": {"semis": "mars", "recolte": "juin-octobre"}}})
        assert set(resultat.calendriers_valeurs_refusees) == {
            "carotte / standard / levee", "carotte / standard / tropical",
            "carotte / standard / oceanique.semis",
        }
        assert len(resultat.calendriers_valeurs_ecrites) == 2

    def test_us068_ca9_simulation_n_ecrit_rien(self, db):
        _culture(db, "carotte")
        resultat = svc_import.importer(db, _manifeste({"culture": "carotte", "durees": {"levee": "10"}}), dry_run=True)
        assert resultat.calendriers_valeurs_ecrites
        assert db.query(ItineraireCultural).count() == 0

    def test_us068_ca9_le_gabarit_livre_est_vide_et_inoffensif(self, db):
        manifeste = json.loads(GABARIT_INTERNE.read_text(encoding="utf-8"))
        for entree in manifeste["cultures_calendriers"]:
            _culture(db, entree["culture"])
            assert all(v is None for v in entree["durees"].values())
            assert all(v is None for phases in entree["fenetres"].values() for v in phases.values())
        resultat = svc_import.importer(db, manifeste)
        assert resultat.total_ecritures == 0
        assert db.query(ItineraireCultural).count() == 0

    def test_us068_ca25_le_gabarit_porte_la_plantation_pour_chaque_zone(self):
        """[CA25] Quatre phases par zone, dans chaque bloc — une case par phase du service."""
        manifeste = json.loads(GABARIT_INTERNE.read_text(encoding="utf-8"))
        for entree in manifeste["cultures_calendriers"]:
            assert set(entree["fenetres"]) == set(cal.ZONES_CLIMATIQUES), entree["culture"]
            for phases in entree["fenetres"].values():
                assert tuple(phases) == cal.PHASES, entree["culture"]

    def test_us068_ca25_le_gabarit_couvre_toutes_les_cultures_connues(self):
        """[CA25] Plus seulement les dix du périmètre initial : chaque culture semée
        par les migrations, et chaque culture du manifeste de la source, a sa case."""
        import re

        manifeste = json.loads(GABARIT_INTERNE.read_text(encoding="utf-8"))
        cultures = [e["culture"] for e in manifeste["cultures_calendriers"]]
        assert len(cultures) == len(set(cultures)), "une culture en double dans le gabarit"

        semees: set[str] = set()
        for migration in ("migration_v5", "migration_v6", "migration_v13"):
            texte = (RACINE / "migrations" / f"{migration}.sql").read_text(encoding="utf-8")
            for bloc in re.findall(r"INSERT INTO culture_config[^;]*;", texte, re.S):
                semees |= {m.group(1).replace("''", "'") for m in
                           re.finditer(r"\(\s*(?:\d+\s*,\s*)?'((?:[^']|'')*)'", bloc)}
        semees.discard("courge butternut")  # supprimée par migration_v13
        source = {e["culture"] for e in
                  json.loads(MANIFESTE_WIND_RIVER.read_text(encoding="utf-8"))["cultures_calendriers"]}
        assert (semees | source) - set(cultures) == set()

    def test_us068_ca9_les_calendriers_remontent_dans_les_donnees_derivees(self, db):
        _culture(db, "haricot")
        _importer(db, {"culture": "haricot", "durees": {"levee": "7-10"},
                       "fenetres": {"oceanique": {"recolte": "juillet-septembre"}}})
        tables = {d["table"] for d in svc_sources.donnees_derivees(db, "wikidata")}
        assert {"itineraire_cultural", "fenetre_culturale", "duree_culturale"} <= tables

    def test_us068_ca9_le_compte_rendu_console_nomme_le_calendrier(self, db):
        _culture(db, "haricot")
        texte = svc_import.formater_resultat(_importer(db, {"culture": "haricot", "durees": {"levee": "7"}}))
        assert "Calendrier cultural [US-068]" in texte


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — l'adaptateur Wind River Greens (durées seulement)
# ═════════════════════════════════════════════════════════════════════════════
class TestCA9AdaptateurWindRiver:

    @pytest.mark.parametrize("texte, attendu", [
        ("Direct sow after last frost", svc_adaptateur.MODE_PLEINE_TERRE),
        ("Start indoors 6-8 weeks before last frost.", svc_adaptateur.MODE_PEPINIERE),
        ("Start seeds indoors 8-10 weeks before last frost", svc_adaptateur.MODE_PEPINIERE),
        ("Direct sow after soil reaches 65°F, or start indoors 2-3 weeks", svc_adaptateur.MODE_MIXTE),
        ("Plant cloves pointed end up, 2 inches deep in fall", svc_adaptateur.MODE_NON_SEMIS),
        ("", None),
    ])
    def test_us068_ca9_mode_de_semis(self, texte, attendu):
        assert svc_adaptateur.classer_mode_semis(texte) == attendu

    def _lignes(self, n, **champs):
        return [dict(champs) for _ in range(n)]

    def test_us068_ca9_pleine_terre_donne_levee_et_recolte(self):
        par_culture = {"carotte": self._lignes(
            4, sowing_method="Direct sow 2-3 weeks before last frost",
            days_to_germination="14-21", days_to_harvest="65-75")}
        resultat = svc_adaptateur.ResultatAdaptation()
        entrees = svc_adaptateur.construire_calendriers(par_culture, resultat)
        assert entrees == [{"culture": "carotte", "itineraire": "standard",
                            "durees": {"levee": "14-21", "recolte": "65-75"}}]

    def test_us068_ca9_pepiniere_donne_repiquage_jamais_recolte(self):
        par_culture = {"tomate": self._lignes(
            5, sowing_method="Start indoors 6-8 weeks before last frost",
            days_to_germination="7-14", days_to_harvest="72")}
        resultat = svc_adaptateur.ResultatAdaptation()
        durees = svc_adaptateur.construire_calendriers(par_culture, resultat)[0]["durees"]
        # [US-177 / CA2] `days_to_harvest` reste écarté de `recolte` — il ne
        # compte pas depuis le semis — et alimente désormais l'étape qui, elle,
        # compte depuis la plantation.
        assert durees == {"levee": "7-14", "repiquage": "42-56", "plantation_recolte": "72-72"}
        assert any("tomate.recolte" in e for e in resultat.durees_ecartees)

    def test_us068_ca9_ce_qui_ne_se_seme_pas_ne_donne_aucune_duree_de_semis(self):
        par_culture = {"ail": self._lignes(
            4, sowing_method="Plant cloves 2 inches deep in fall",
            days_to_germination="14-21", days_to_harvest="240-270")}
        resultat = svc_adaptateur.ResultatAdaptation()
        durees = svc_adaptateur.construire_calendriers(par_culture, resultat)[0]["durees"]
        # Aucune durée comptée depuis un semis qui n'existe pas ; [US-177 / CA3]
        # la plantation, elle, est le seul geste d'origine de l'ail.
        assert "levee" not in durees and "recolte" not in durees and "repiquage" not in durees
        assert durees == {"plantation_recolte": "240-270"}

    def test_us068_ca9_base_trop_faible_ecartee(self):
        par_culture = {"blette": self._lignes(
            1, sowing_method="Direct sow", days_to_germination="7-14", days_to_harvest="32")}
        resultat = svc_adaptateur.ResultatAdaptation()
        assert svc_adaptateur.construire_calendriers(par_culture, resultat) == []

    def test_us068_ca9_la_mediane_ecarte_un_cultivar_atypique(self):
        lignes = [
            {"sowing_method": "Direct sow", "days_to_germination": "10", "days_to_harvest": h}
            for h in ("65-75", "70-80", "68-75", "21")
        ]
        resultat = svc_adaptateur.ResultatAdaptation()
        durees = svc_adaptateur.construire_calendriers({"carotte": lignes}, resultat)[0]["durees"]
        jours_min, jours_max = (int(x) for x in durees["recolte"].split("-"))
        assert jours_min >= 60 and jours_max >= 70

    def test_us068_ca9_le_manifeste_versionne_est_lisible(self):
        manifeste = json.loads(MANIFESTE_WIND_RIVER.read_text(encoding="utf-8"))
        assert manifeste["cultures_calendriers"], "le bloc du calendrier est livré"
        for entree in manifeste["cultures_calendriers"]:
            # [US-177] Le vocabulaire est celui du service — quatre étapes.
            assert set(entree["durees"]) <= set(cal.ETAPES)
            for valeur in entree["durees"].values():
                assert cal.parser_duree(valeur) is not None
            for zone, phases in entree.get("fenetres", {}).items():
                assert zone in cal.ZONES_CLIMATIQUES
                for phase, valeur in phases.items():
                    assert phase in cal.PHASES
                    debut, fin = cal.parser_fenetre(valeur)
                    assert debut <= fin, "aucune fenêtre à cheval sur l'année ne sort de la source"

    def test_us068_ca9_le_manifeste_versionne_ecarte_l_ail_et_la_blette(self):
        manifeste = json.loads(MANIFESTE_WIND_RIVER.read_text(encoding="utf-8"))
        avec_fenetres = {e["culture"] for e in manifeste["cultures_calendriers"] if e.get("fenetres")}
        assert "tomate" in avec_fenetres
        assert not {"ail", "blette"} & avec_fenetres

    def test_us068_ca3_pas_de_repiquage_sans_fenetre_de_pepiniere_dans_le_manifeste(self):
        manifeste = json.loads(MANIFESTE_WIND_RIVER.read_text(encoding="utf-8"))
        for entree in manifeste["cultures_calendriers"]:
            if "repiquage" in entree["durees"] and entree.get("fenetres"):
                assert any(
                    cal.PHASE_SEMIS_PEPINIERE in phases for phases in entree["fenetres"].values()
                ), entree["culture"]

    def test_us068_ca9_le_manifeste_versionne_s_importe(self, db):
        manifeste = json.loads(MANIFESTE_WIND_RIVER.read_text(encoding="utf-8"))
        for entree in manifeste["cultures_calendriers"]:
            _culture(db, entree["culture"])
        resultat = svc_import.importer(db, manifeste)
        assert resultat.calendriers_valeurs_refusees == []
        assert any(".semis_pepiniere" in e for e in resultat.calendriers_valeurs_ecrites)
        assert db.query(FenetreCulturale).filter(FenetreCulturale.potager_id.is_(None)).count() > 0


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — l'adaptateur Wind River Greens : fenêtres de planting_calendar.csv
# ═════════════════════════════════════════════════════════════════════════════
class TestCA9FenetresWindRiver:

    SEMIS_ABRI = "Start indoors 6-8 weeks before last frost"

    def _cultivars(self, n, categorie="tomato", sowing_method=SEMIS_ABRI):
        return [
            {"id": str(i), "category": categorie, "sowing_method": sowing_method}
            for i in range(1, n + 1)
        ]

    def _ligne(self, identifiant, zone, categorie="tomato", **mois):
        ligne = {"variety_id": str(identifiant), "usda_zone": str(zone), "category": categorie}
        for colonnes in svc_adaptateur.COLONNES_PHASE.values():
            for colonne in colonnes:
                ligne[colonne] = mois.get(colonne, "")
        return ligne

    def _fenetres(self, par_culture, calendrier):
        resultat = svc_adaptateur.ResultatAdaptation()
        return svc_adaptateur.construire_fenetres(par_culture, calendrier, resultat), resultat

    def test_us068_ca9_chaque_zone_climatique_lit_une_zone_usda_declaree(self):
        assert set(svc_adaptateur.ZONE_USDA_PAR_ZONE) == set(cal.ZONES_CLIMATIQUES)
        # De la plus tardive à la plus précoce : l'ordre des dernières gelées.
        z = svc_adaptateur.ZONE_USDA_PAR_ZONE
        assert z["montagnard"] < z["continental"] < z["oceanique"] < z["mediterraneen"]

    def test_us068_ca9_mois_source_vers_forme_du_gabarit(self):
        ligne = self._ligne(1, 7, indoor_sow_start="February", indoor_sow_end="March",
                            harvest_start="July", harvest_end="July")
        assert svc_adaptateur.fenetre_source(ligne, cal.PHASE_SEMIS_PEPINIERE) == (2, 3)
        assert svc_adaptateur.fenetre_source(ligne, cal.PHASE_SEMIS_PLEINE_TERRE) is None
        assert svc_adaptateur.formater_mois(2, 3) == "février-mars"
        assert svc_adaptateur.formater_mois(7, 7) == "juillet"

    def test_us068_ca9_la_zone_oceanique_lit_sa_zone_usda_et_aucune_autre(self):
        usda = svc_adaptateur.ZONE_USDA_PAR_ZONE["oceanique"]
        calendrier = [
            self._ligne(i, usda, indoor_sow_start="February", indoor_sow_end="March") for i in (1, 2, 3)
        ] + [
            self._ligne(i, usda + 1, indoor_sow_start="January", indoor_sow_end="January") for i in (1, 2, 3)
        ]
        fenetres, _ = self._fenetres({"tomate": self._cultivars(3)}, calendrier)
        assert fenetres["tomate"]["oceanique"] == {"semis_pepiniere": "février-mars"}
        assert fenetres["tomate"]["mediterraneen"] == {"semis_pepiniere": "janvier"}
        # [CA13] Aucune ligne pour leur zone USDA : rien d'emprunté à une voisine.
        assert "continental" not in fenetres["tomate"]
        assert "montagnard" not in fenetres["tomate"]

    def test_us068_ca9_jointure_par_identifiant_et_categorie(self):
        usda = svc_adaptateur.ZONE_USDA_PAR_ZONE["oceanique"]
        # Même identifiant, autre catégorie : la ligne ne décrit pas ce cultivar.
        calendrier = [
            self._ligne(i, usda, categorie="rose", indoor_sow_start="May", indoor_sow_end="June")
            for i in (1, 2, 3)
        ]
        fenetres, _ = self._fenetres({"tomate": self._cultivars(3)}, calendrier)
        assert fenetres == {}

    def test_us068_ca9_ce_qui_ne_se_seme_pas_ne_recoit_aucune_fenetre(self):
        usda = svc_adaptateur.ZONE_USDA_PAR_ZONE["oceanique"]
        cultivars = self._cultivars(3, categorie="allium", sowing_method="Plant cloves in fall")
        calendrier = [
            self._ligne(i, usda, categorie="allium", direct_sow_start="March", direct_sow_end="May")
            for i in (1, 2, 3)
        ]
        fenetres, resultat = self._fenetres({"ail": cultivars}, calendrier)
        assert fenetres == {}
        assert any(e.startswith("ail — ne se sème pas") for e in resultat.fenetres_ecartees)

    def test_us068_ca9_fenetre_a_cheval_sur_l_annee_rejetee_comme_artefact(self):
        usda = svc_adaptateur.ZONE_USDA_PAR_ZONE["oceanique"]
        calendrier = [
            self._ligne(i, usda, harvest_start="December", harvest_end="November") for i in (1, 2, 3)
        ]
        fenetres, resultat = self._fenetres({"tomate": self._cultivars(3)}, calendrier)
        assert fenetres == {}
        assert any("à cheval sur l'année" in e for e in resultat.fenetres_ecartees)

    def test_us068_ca9_phase_minoritaire_ecartee(self):
        usda = svc_adaptateur.ZONE_USDA_PAR_ZONE["oceanique"]
        calendrier = [
            self._ligne(i, usda, direct_sow_start="April", direct_sow_end="June",
                        **({"indoor_sow_start": "March", "indoor_sow_end": "April"} if i <= 3 else {}))
            for i in range(1, 11)
        ]
        cultivars = self._cultivars(10, categorie="tomato",
                                    sowing_method="Direct sow, or start indoors 2-3 weeks")
        fenetres, resultat = self._fenetres({"courgette": cultivars}, calendrier)
        assert fenetres["courgette"]["oceanique"] == {"semis_pleine_terre": "avril-juin"}
        assert any("courgette.oceanique.semis_pepiniere" in e for e in resultat.fenetres_ecartees)

    def test_us068_ca9_mediane_basse_un_mois_reellement_observe(self):
        usda = svc_adaptateur.ZONE_USDA_PAR_ZONE["oceanique"]
        recoltes = [("July", "September")] * 2 + [("August", "October")] * 2
        calendrier = [
            self._ligne(i, usda, harvest_start=debut, harvest_end=fin)
            for i, (debut, fin) in enumerate(recoltes, start=1)
        ]
        fenetres, _ = self._fenetres({"tomate": self._cultivars(4)}, calendrier)
        assert fenetres["tomate"]["oceanique"]["recolte"] == "juillet-septembre"

    def test_us068_ca9_base_trop_faible_une_seule_ligne_au_compte_rendu(self):
        usda = svc_adaptateur.ZONE_USDA_PAR_ZONE["oceanique"]
        calendrier = [self._ligne(1, usda, direct_sow_start="April", direct_sow_end="May")]
        fenetres, resultat = self._fenetres({"blette": self._cultivars(1)}, calendrier)
        assert fenetres == {}
        assert resultat.fenetres_ecartees == ["blette — base trop faible (1 cultivar(s), minimum 3)"]

    def test_us068_ca9_sans_calendrier_les_durees_seules_sont_produites(self):
        par_culture = {"carotte": [
            {"id": str(i), "category": "root-vegetable", "sowing_method": "Direct sow",
             "days_to_germination": "14-21", "days_to_harvest": "65-75"} for i in range(4)
        ]}
        resultat = svc_adaptateur.ResultatAdaptation()
        entrees = svc_adaptateur.construire_calendriers(par_culture, resultat)
        assert "fenetres" not in entrees[0]

    def test_us068_ca9_fenetres_seules_suffisent_a_produire_une_entree(self):
        usda = svc_adaptateur.ZONE_USDA_PAR_ZONE["continental"]
        cultivars = self._cultivars(3)
        calendrier = [
            self._ligne(i, usda, indoor_sow_start="March", indoor_sow_end="March") for i in (1, 2, 3)
        ]
        resultat = svc_adaptateur.ResultatAdaptation()
        entrees = svc_adaptateur.construire_calendriers({"tomate": cultivars}, resultat, calendrier)
        assert entrees == [{
            "culture": "tomate", "itineraire": "standard", "durees": {"repiquage": "42-56"},
            "fenetres": {"continental": {"semis_pepiniere": "mars"}},
        }]

    # ── Périmètre étendu à culture_config ───────────────────────────────────

    @pytest.mark.parametrize("texte, attendu", [
        ("Plant seed potatoes 3-4 inches deep, 2-3 weeks before last frost.", svc_adaptateur.MODE_NON_SEMIS),
        ("Transplant crowns after last spring frost", svc_adaptateur.MODE_NON_SEMIS),
        ("Start from cuttings or purchased plants only - does not produce viable seeds.",
         svc_adaptateur.MODE_NON_SEMIS),
        ("Start from seed indoors 10-12 weeks before last frost.", svc_adaptateur.MODE_PEPINIERE),
        ("Start indoors 6-8 weeks before last frost or direct seed in warm climates.",
         svc_adaptateur.MODE_MIXTE),
    ])
    def test_us068_ca9_plantation_et_semis_distingues(self, texte, attendu):
        assert svc_adaptateur.classer_mode_semis(texte) == attendu

    def test_us068_ca9_une_option_secondaire_ne_masque_pas_la_pepiniere(self):
        modes = [svc_adaptateur.MODE_PEPINIERE] * 7 + [svc_adaptateur.MODE_MIXTE] * 3
        mode, _ = svc_adaptateur._mode_dominant(modes)
        assert mode == svc_adaptateur.MODE_PEPINIERE
        partage = [svc_adaptateur.MODE_PEPINIERE] * 4 + [svc_adaptateur.MODE_MIXTE] * 6
        assert svc_adaptateur._mode_dominant(partage)[0] is None

    def test_us068_ca9_plantation_majoritaire_ecarte_toute_la_culture(self):
        usda = svc_adaptateur.ZONE_USDA_PAR_ZONE["oceanique"]
        cultivars = (
            self._cultivars(2, categorie="berry", sowing_method="Transplant crowns in spring")
            + [{"id": "3", "category": "berry", "sowing_method": "Direct sow after last frost"}]
        )
        calendrier = [
            self._ligne(i, usda, categorie="berry", harvest_start="July", harvest_end="October")
            for i in (1, 2, 3)
        ]
        fenetres, resultat = self._fenetres({"fraise": cultivars}, calendrier)
        assert fenetres == {}
        assert resultat.fenetres_ecartees[0].startswith("fraise — ne se sème pas")

    def test_us068_ca9_semis_contredit_par_les_fiches_ecarte(self):
        usda = svc_adaptateur.ZONE_USDA_PAR_ZONE["oceanique"]
        cultivars = self._cultivars(4, categorie="herb", sowing_method="Direct sow after last frost")
        calendrier = [
            self._ligne(i, usda, categorie="herb", indoor_sow_start="February", indoor_sow_end="March",
                        harvest_start="June", harvest_end="November")
            for i in (1, 2, 3, 4)
        ]
        fenetres, resultat = self._fenetres({"fenouil": cultivars}, calendrier)
        assert fenetres["fenouil"]["oceanique"] == {"recolte": "juin-novembre"}
        assert any("contredite par les fiches" in e for e in resultat.fenetres_ecartees)

    def test_us068_ca9_semis_d_automne_signale_incomplet(self):
        usda = svc_adaptateur.ZONE_USDA_PAR_ZONE["oceanique"]
        cultivars = self._cultivars(
            3, categorie="root-vegetable", sowing_method="Direct sow in early spring or late summer")
        calendrier = [
            self._ligne(i, usda, categorie="root-vegetable", direct_sow_start="March", direct_sow_end="May")
            for i in (1, 2, 3)
        ]
        fenetres, resultat = self._fenetres({"navet": cultivars}, calendrier)
        assert fenetres["navet"]["oceanique"] == {"semis_pleine_terre": "mars-mai"}
        assert resultat.fenetres_incompletes and resultat.fenetres_incompletes[0].startswith("navet")

    def test_us068_ca9_un_alias_recoit_le_calendrier_de_sa_reference(self):
        usda = svc_adaptateur.ZONE_USDA_PAR_ZONE["oceanique"]
        cultivars = self._cultivars(3, categorie="lettuce", sowing_method="Direct sow in spring")
        calendrier = [
            self._ligne(i, usda, categorie="lettuce", direct_sow_start="March", direct_sow_end="May")
            for i in (1, 2, 3)
        ]
        resultat = svc_adaptateur.ResultatAdaptation()
        entrees = svc_adaptateur.construire_calendriers({"laitue": cultivars}, resultat, calendrier)
        par_nom = {e["culture"]: e for e in entrees}
        assert set(svc_adaptateur.ALIAS_CALENDRIER.values()) <= {"laitue"}
        assert par_nom["salade"]["fenetres"] == par_nom["laitue"]["fenetres"]

    # ── Fenêtre de plantation — amendement du 15/09/2026 (CA17 à CA26) ───────

    def test_us068_ca21_plantation_lue_dans_outdoor_transplant(self):
        usda = svc_adaptateur.ZONE_USDA_PAR_ZONE["continental"]
        calendrier = [
            self._ligne(i, usda, indoor_sow_start="March", indoor_sow_end="March",
                        outdoor_transplant_start="May", outdoor_transplant_end="June")
            for i in (1, 2, 3)
        ]
        fenetres, _ = self._fenetres({"tomate": self._cultivars(3)}, calendrier)
        assert fenetres["tomate"]["continental"] == {"semis_pepiniere": "mars", "plantation": "mai-juin"}
        # Ordre du geste : la plantation vient entre les semis et la récolte.
        assert list(svc_adaptateur.COLONNES_PHASE) == list(cal.PHASES)

    def test_us068_ca22_plantation_contredite_par_des_fiches_de_semis_en_place(self):
        usda = svc_adaptateur.ZONE_USDA_PAR_ZONE["oceanique"]
        cultivars = (
            self._cultivars(3, categorie="cucumber", sowing_method="Direct sow after last frost")
            + [{"id": "4", "category": "cucumber",
                "sowing_method": "Direct sow, or start indoors 3 weeks before"}]
        )
        calendrier = [
            self._ligne(i, usda, categorie="cucumber", direct_sow_start="May", direct_sow_end="June",
                        outdoor_transplant_start="May", outdoor_transplant_end="May")
            for i in (1, 2, 3, 4)
        ]
        fenetres, resultat = self._fenetres({"cornichon": cultivars}, calendrier)
        assert fenetres["cornichon"]["oceanique"] == {"semis_pleine_terre": "mai-juin"}
        assert any(
            e.startswith("cornichon.oceanique.plantation — contredite") and "mise en place" in e
            for e in resultat.fenetres_ecartees
        )

    def test_us068_ca23_ce_qui_ne_se_seme_pas_garde_sa_plantation(self):
        usda = svc_adaptateur.ZONE_USDA_PAR_ZONE["oceanique"]
        cultivars = self._cultivars(3, categorie="herb", sowing_method="Plant divisions in spring")
        calendrier = [
            self._ligne(i, usda, categorie="herb", direct_sow_start="March", direct_sow_end="May",
                        outdoor_transplant_start="April", outdoor_transplant_end="June",
                        harvest_start="June", harvest_end="October")
            for i in (1, 2, 3)
        ]
        fenetres, resultat = self._fenetres({"menthe": cultivars}, calendrier)
        # Semis et récolte, calculés depuis un semis qui n'existe pas, restent écartés.
        assert fenetres["menthe"]["oceanique"] == {"plantation": "avril-juin"}
        assert resultat.fenetres_ecartees[0].startswith("menthe — ne se sème pas")

    def test_us068_ca23_une_plantation_d_automne_contredit_le_gabarit_de_printemps(self):
        usda = svc_adaptateur.ZONE_USDA_PAR_ZONE["oceanique"]
        cultivars = self._cultivars(3, categorie="berry",
                                    sowing_method="Plant dormant canes in early spring or fall.")
        calendrier = [
            self._ligne(i, usda, categorie="berry",
                        outdoor_transplant_start="May", outdoor_transplant_end="June")
            for i in (1, 2, 3)
        ]
        fenetres, resultat = self._fenetres({"framboise": cultivars}, calendrier)
        assert fenetres == {}
        assert any(e.startswith("framboise.plantation — contredite") for e in resultat.fenetres_ecartees)

    def test_us068_ca24_incoherence_signalee_jamais_corrigee(self):
        resultat = svc_adaptateur.ResultatAdaptation()
        fenetres = {
            "oceanique": {"semis_pepiniere": "avril", "plantation": "mars-mai"},
            # Semé au 1er mars au plus tôt + 42 jours = avril : planter en mars est trop tôt.
            "continental": {"semis_pepiniere": "mars", "plantation": "mars"},
            "mediterraneen": {"semis_pepiniere": "février", "plantation": "avril-mai"},
        }
        copie = json.loads(json.dumps(fenetres))
        svc_adaptateur.signaler_incoherences("tomate", {"repiquage": "42-56"}, fenetres, resultat)
        assert fenetres == copie, "rien n'est ajusté"
        assert len(resultat.fenetres_incoherentes) == 2
        assert "commence avant le semis" in resultat.fenetres_incoherentes[0]
        assert "42 jours" in resultat.fenetres_incoherentes[1]
        # Sans semis en pépinière (plants achetés), aucune incohérence possible.
        resultat = svc_adaptateur.ResultatAdaptation()
        svc_adaptateur.signaler_incoherences("tomate", {}, {"oceanique": {"plantation": "mai"}}, resultat)
        assert resultat.fenetres_incoherentes == []

    def test_us068_ca26_le_manifeste_versionne_porte_la_plantation_de_la_source(self):
        manifeste = json.loads(MANIFESTE_WIND_RIVER.read_text(encoding="utf-8"))
        par_nom = {e["culture"]: e for e in manifeste["cultures_calendriers"]}
        assert par_nom["tomate"]["fenetres"]["oceanique"]["plantation"] == "avril-mai"
        for zone in cal.ZONES_CLIMATIQUES:
            assert "plantation" in par_nom["poivron"]["fenetres"][zone]
        # Semé en place, contredit par ses fiches, ou absent de la source : rien.
        for culture in ("carotte", "haricot", "cornichon", "courgette", "poireau"):
            assert all("plantation" not in p for p in par_nom[culture].get("fenetres", {}).values()), culture
        # L'ail n'a aucune FENÊTRE issue de la source ; [US-177 / CA3] il porte en
        # revanche sa durée plantation → récolte, seule, sans levée ni repiquage.
        assert not par_nom.get("ail", {}).get("fenetres")
        assert set(par_nom["ail"]["durees"]) == {"plantation_recolte"}

    def test_us068_ca9_le_particulier_passe_avant_le_general(self):
        lignes = [
            {"id": "1", "category": "bean", "name": "Kentucky Wonder Pole", "slug": "kentucky-wonder-pole",
             "scientific_name": "Phaseolus vulgaris"},
            {"id": "2", "category": "bean", "name": "Provider", "slug": "provider",
             "scientific_name": "Phaseolus vulgaris"},
            {"id": "3", "category": "squash", "name": "Red Kuri Squash", "slug": "red-kuri-squash",
             "scientific_name": "Cucurbita maxima"},
            # Un microgreen porte le nom du légume : la catégorie l'écarte.
            {"id": "4", "category": "microgreen", "name": "Broccoli", "slug": "broccoli-microgreens",
             "scientific_name": "Brassica oleracea"},
        ]
        par_culture = svc_adaptateur.selectionner_cultivars(lignes, svc_adaptateur.APPARIEMENTS_CALENDRIER)
        assert [l["id"] for l in par_culture["haricot grimpant"]] == ["1"]
        assert [l["id"] for l in par_culture["haricot"]] == ["2"]
        assert [l["id"] for l in par_culture["potimarron"]] == ["3"]
        assert par_culture["potiron"] == [] and par_culture["brocoli"] == []

    def test_us068_ca9_les_attributs_restent_sur_le_perimetre_initial(self):
        manifeste = json.loads(MANIFESTE_WIND_RIVER.read_text(encoding="utf-8"))
        initiales = {a.culture for a in svc_adaptateur.APPARIEMENTS}
        assert {e["culture"] for e in manifeste["cultures_attributs"]} <= initiales
        assert {e["culture"] for e in manifeste["cultures_calendriers"]} - initiales, \
            "le calendrier couvre plus que les dix cultures initiales"

    def test_us068_ca9_le_calendrier_versionne_est_un_extrait_du_perimetre(self):
        dossier = RACINE / "data" / "referentiel" / "wind_river_greens"
        with open(dossier / "varieties.csv", encoding="utf-8", newline="") as flux:
            identifiants = {l["id"] for l in csv.DictReader(flux)}
        with open(dossier / "planting_calendar.csv", encoding="utf-8", newline="") as flux:
            lignes = list(csv.DictReader(flux))
        assert lignes
        assert {l["variety_id"] for l in lignes} <= identifiants


# ═════════════════════════════════════════════════════════════════════════════
# CA10, CA11 — correction propre au potager
# ═════════════════════════════════════════════════════════════════════════════
class TestCA10CA11Correction:

    def test_us068_gherkin_correction_propre_a_un_potager(self, db):
        """Gherkin 6 — A avance sa pépinière de tomates en février, B reste en mars."""
        _culture(db, "tomate")
        _importer(db, {"culture": "tomate", "durees": {"levee": "7-14"},
                       "fenetres": {"oceanique": {"semis_pepiniere": "mars-avril", "recolte": "juillet-octobre"}}})

        zone, avant, apres = cal.corriger_fenetre(db, CTX_A, "tomate", "pepiniere", "février-avril")
        assert (zone, avant, apres) == ("oceanique", "mars → avril", "février → avril")

        a = cal.lire_calendrier(db, "tomate", 1).itineraires[0]
        b = cal.lire_calendrier(db, "tomate", 2).itineraires[0]
        assert a.fenetre(cal.PHASE_SEMIS_PEPINIERE).mois_debut == 2
        assert b.fenetre(cal.PHASE_SEMIS_PEPINIERE).mois_debut == 3
        assert a.personnalise and not b.personnalise
        # Le reste du calendrier partagé a été repris dans la copie de A.
        assert a.fenetre(cal.PHASE_RECOLTE).affichage == "juillet → octobre"
        assert a.duree(cal.ETAPE_LEVEE).affichage == "7 à 14 jours"

    def test_us068_ca11_la_copie_garde_l_origine_des_valeurs_non_corrigees(self, db):
        _culture(db, "tomate")
        _importer(db, {"culture": "tomate", "durees": {"levee": "7-14"},
                       "fenetres": {"oceanique": {"semis_pepiniere": "mars-avril"}}})
        cal.corriger_duree(db, CTX_A, "tomate", "repiquage", "42-56")
        wikidata = svc_sources.get_source(db, "wikidata").id
        manuelle = svc_sources.get_source(db, "saisie_manuelle").id
        locales = {d.etape: d.source_id for d in db.query(DureeCulturale).filter(DureeCulturale.potager_id == 1)}
        assert locales == {"levee": wikidata, "repiquage": manuelle}

    def test_us068_ca10_correction_d_une_duree_confirme_les_deux_valeurs(self, db):
        _culture(db, "courgette")
        _importer(db, {"culture": "courgette", "durees": {"recolte": "50-55"}})
        assert cal.corriger_duree(db, CTX_A, "courgette", "recolte", "50 à 60") == ("50 à 55 jours", "50 à 60 jours")

    def test_us068_ca10_correction_sans_referentiel_prealable(self, db):
        _culture(db, "topinambour")
        assert cal.corriger_duree(db, CTX_A, "topinambour", "recolte", "vivace") == (cal.TIRET, "vivace")
        it = db.query(ItineraireCultural).one()
        assert (it.potager_id, it.nom) == (1, "standard")

    def test_us068_ca10_vider_une_fenetre_ne_retombe_pas_sur_le_partage(self, db):
        _culture(db, "tomate")
        _importer(db, {"culture": "tomate", "fenetres": {"oceanique": {"semis_pleine_terre": "mai"}}})
        cal.corriger_fenetre(db, CTX_A, "tomate", "pleine_terre", "aucune")
        assert cal.lire_calendrier(db, "tomate", 1).itineraires[0].fenetre(cal.PHASE_SEMIS_PLEINE_TERRE) is None
        assert cal.lire_calendrier(db, "tomate", 2).itineraires[0].fenetre(cal.PHASE_SEMIS_PLEINE_TERRE) is not None

    def test_us068_ca10_la_fenetre_corrigee_vaut_pour_la_zone_du_potager(self, db):
        _culture(db, "tomate")
        db.get(Potager, 1).zone_climatique = "mediterraneen"
        db.commit()
        zone, _, _ = cal.corriger_fenetre(db, CTX_A, "tomate", "recolte", "juin-octobre")
        assert zone == "mediterraneen"
        assert db.query(FenetreCulturale).one().zone_climatique == "mediterraneen"

    def test_us068_ca10_correction_d_un_itineraire_nomme(self, db):
        _culture(db, "chou-fleur")
        cal.corriger_fenetre(db, CTX_A, "chou-fleur", "recolte", "novembre-février", itineraire="culture d'hiver")
        noms = [it.nom for it in cal.lire_calendrier(db, "chou-fleur", 1).itineraires]
        assert noms == ["culture d'hiver"]

    def test_us068_ca10_valeur_refusee_avant_toute_ecriture(self, db):
        _culture(db, "tomate")
        with pytest.raises(cal.ValeurCalendrierInvalideError):
            cal.corriger_fenetre(db, CTX_A, "tomate", "pepiniere", "printemps")
        with pytest.raises(cal.ValeurCalendrierInvalideError):
            cal.corriger_fenetre(db, CTX_A, "tomate", "semis_lunaire", "mars")
        assert db.query(ItineraireCultural).count() == 0

    def test_us068_ca10_culture_inconnue(self, db):
        with pytest.raises(cal.CultureInconnueError):
            cal.corriger_duree(db, CTX_A, "kiwano", "levee", "10")
        assert db.query(CultureConfig).count() == 0

    def test_us068_ca10_un_lecteur_ne_corrige_pas(self, db):
        _culture(db, "tomate")
        lecteur = TenantContext(user_id=2, potager_id=1, role="lecteur")
        with pytest.raises(PermissionInsuffisanteError):
            cal.corriger_duree(db, lecteur, "tomate", "levee", "10")

    def test_us068_ca10_pas_de_correction_sur_un_potager_archive(self, db):
        _culture(db, "tomate")
        db.get(Potager, 1).etat = "archive"
        db.commit()
        with pytest.raises(PotagerArchiveError):
            cal.corriger_duree(db, CTX_A, "tomate", "levee", "10")

    def test_us068_ca11_la_fiche_d_un_autre_potager_reste_invisible(self, db):
        _culture(db, "pastèque", potager_id=2)
        with pytest.raises(cal.CultureInconnueError):
            cal.corriger_duree(db, CTX_A, "pastèque", "levee", "10")


# ═════════════════════════════════════════════════════════════════════════════
# CA12, CA13, CA14 — résolution, honnêteté, saisie à la volée
# ═════════════════════════════════════════════════════════════════════════════
class TestCA12CA13CA14:

    def test_us068_ca12_casse_accents_et_pluriel_indifferents(self, db):
        _culture(db, "céleri")
        _importer(db, {"culture": "celeri", "durees": {"levee": "15"}})
        for saisie in ("CÉLERI", "celeri", "céleris"):
            calendrier = cal.lire_calendrier(db, saisie, 1)
            assert calendrier.itineraires[0].duree(cal.ETAPE_LEVEE).jours_min == 15, saisie

    def test_us068_ca12_separation_culture_et_itineraire(self, db):
        _culture(db, "petit pois")
        _culture(db, "petit")
        assert cal.separer_culture_itineraire(db, ["petit", "pois", "culture", "précoce"], 1) == (
            "petit pois", "culture précoce")
        assert cal.separer_culture_itineraire(db, ["kiwano"], 1) == ("kiwano", "standard")

    def test_us068_gherkin_culture_sans_referentiel(self, db):
        """Gherkin 7 — topinambour : frise neutre, durées en tiret."""
        _culture(db, "topinambour")
        donnees = cal.calendrier_en_dict(cal.lire_calendrier(db, "topinambour", 1))
        it = donnees["itineraires"][0]
        assert donnees["renseigne"] is False
        assert all(phases == [] for phases in it["frise"].values())
        assert [d["affichage"] for d in it["durees"]] == [cal.TIRET, cal.TIRET]
        assert all(d["jours_min"] is None for d in it["durees"])

    def test_us068_ca13_culture_inconnue_rend_un_calendrier_vide(self, db):
        calendrier = cal.lire_calendrier(db, "kiwano", 1)
        assert not calendrier.culture_connue and calendrier.itineraires == []

    def test_us068_gherkin_ca14_semis_d_une_culture_inconnue_sans_question_calendrier(self, db):
        """Gherkin 7 / CA14 — la création à la volée n'exige ni fenêtre ni durée."""
        from app.services import parcelles as svc_parcelles

        config = svc_parcelles.creer_culture_config(db, CTX_A, "topinambour", "végétatif")
        assert config.id is not None
        assert db.query(ItineraireCultural).count() == 0
        assert cal.lire_calendrier(db, "topinambour", 1).itineraires[0].implicite


# ═════════════════════════════════════════════════════════════════════════════
# CA15 — non-régression : culture_config inchangée, purge complète
# ═════════════════════════════════════════════════════════════════════════════
class TestCA15NonRegression:

    def test_us068_ca15_aucune_colonne_de_culture_config_modifiee(self):
        colonnes = set(CultureConfig.__table__.columns.keys())
        assert not {c for c in colonnes if "zone" in c or "fenetre" in c or "itineraire" in c}

    def test_us068_ca15_zone_climatique_est_nullable(self):
        assert Potager.__table__.columns["zone_climatique"].nullable

    def test_us068_purge_emporte_les_calendriers_personnalises_seulement(self, db):
        _culture(db, "tomate")
        _importer(db, {"culture": "tomate", "durees": {"levee": "7-14"},
                       "fenetres": {"oceanique": {"semis_pepiniere": "mars-avril"}}})
        cal.corriger_fenetre(db, CTX_A, "tomate", "pepiniere", "février-avril")
        cal.corriger_fenetre(db, CTX_B, "tomate", "pepiniere", "avril")

        volumes = svc_potagers.purger_potager(db, 1)["volumes"]
        assert (volumes["itineraire_cultural"], volumes["fenetre_culturale"], volumes["duree_culturale"]) == (1, 1, 1)
        assert db.query(ItineraireCultural).filter(ItineraireCultural.potager_id == 1).count() == 0
        assert db.query(ItineraireCultural).filter(ItineraireCultural.potager_id.is_(None)).count() == 1
        assert cal.lire_calendrier(db, "tomate", 2).itineraires[0].fenetre(cal.PHASE_SEMIS_PEPINIERE).mois_debut == 4


# ═════════════════════════════════════════════════════════════════════════════
# CA10 — le bot : /calendrier
# ═════════════════════════════════════════════════════════════════════════════
class TestCA10Bot:

    def _update(self):
        update = MagicMock()
        update.message.reply_text = AsyncMock()
        return update

    def _ctx(self, *args):
        ctx = MagicMock()
        ctx.args = list(args)
        return ctx

    async def _appeler(self, db, *args, tenant=CTX_A):
        from app import bot
        update = self._update()
        with patch.object(bot, "SessionLocal", return_value=db), \
             patch.object(bot, "current_context", return_value=tenant):
            await bot.cmd_calendrier(update, self._ctx(*args))
        return update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_us068_bot_sans_argument_affiche_l_usage(self, db):
        assert "Usage" in await self._appeler(db)

    @pytest.mark.asyncio
    async def test_us068_bot_consultation(self, db):
        _culture(db, "tomate")
        _importer(db, {"culture": "tomate", "durees": {"levee": "7-14"},
                       "fenetres": {"oceanique": {"semis_pepiniere": "mars-avril"}}})
        texte = await self._appeler(db, "tomate")
        assert "Semis en pépinière" in texte and "mars → avril" in texte
        assert "7 à 14 jours" in texte
        assert "Semis → première récolte : —" in texte
        assert "zone par défaut" in texte
        assert "jamais des dates" in texte

    @pytest.mark.asyncio
    async def test_us068_ca27_consultation_affiche_la_plantation_dans_l_ordre_du_geste(self, db):
        _culture(db, "tomate")
        _importer(db, {"culture": "tomate", "fenetres": {"oceanique": {
            "recolte": "juillet-septembre", "plantation": "mai-juin", "semis_pepiniere": "mars-avril"}}})
        texte = await self._appeler(db, "tomate")
        assert "Plantation : *mai → juin*" in texte
        assert texte.index("Semis en pépinière") < texte.index("Plantation") < texte.index("Récolte")

    @pytest.mark.asyncio
    async def test_us068_ca27_plantation_vide_dite_quand_une_autre_phase_est_renseignee(self, db):
        """[CA27, CA18] L'aubergine a un semis en pépinière et un délai de
        repiquage : sa plantation reste « — », jamais calculée."""
        _culture(db, "aubergine")
        _importer(db, {"culture": "aubergine", "durees": {"repiquage": "42-56"},
                       "fenetres": {"oceanique": {"semis_pepiniere": "mars"}}})
        texte = await self._appeler(db, "aubergine")
        assert "Plantation : —" in texte
        assert "Semis en pleine terre" not in texte

    @pytest.mark.asyncio
    async def test_us068_ca27_correction_de_la_plantation_confirme_avant_et_apres(self, db):
        _culture(db, "tomate")
        _importer(db, {"culture": "tomate", "fenetres": {"oceanique": {"plantation": "avril-mai"}}})
        texte = await self._appeler(db, "fenetre", "tomate", "plantation", "mai-juin")
        assert "avril → mai" in texte and "mai → juin" in texte
        assert "propre à votre potager" in texte
        partage = cal.lire_calendrier(db, "tomate", 2).itineraires[0].fenetre(cal.PHASE_PLANTATION)
        assert (partage.mois_debut, partage.mois_fin) == (4, 5)

    @pytest.mark.asyncio
    async def test_us068_ca29_au_bot_la_sous_commande_tranche_entre_fenetre_et_duree(self, db):
        """[CA29] « plantation » est aussi l'alias de la durée `repiquage` : c'est
        la sous-commande qui dit laquelle des deux on corrige."""
        _culture(db, "tomate")
        _importer(db, {"culture": "tomate", "fenetres": {"oceanique": {"semis_pepiniere": "mars"}}})
        texte = await self._appeler(db, "duree", "tomate", "plantation", "42-56")
        assert "42 à 56 jours" in texte
        it = cal.lire_calendrier(db, "tomate", 1).itineraires[0]
        assert it.fenetre(cal.PHASE_PLANTATION) is None

    @pytest.mark.asyncio
    async def test_us068_bot_consultation_dit_ce_qui_manque_pour_la_zone(self, db):
        _culture(db, "tomate")
        _importer(db, {"culture": "tomate", "fenetres": {"continental": {"recolte": "août"}}})
        texte = await self._appeler(db, "tomate")
        assert "Aucune fenêtre renseignée pour la zone océanique" in texte
        assert "continental" in texte

    @pytest.mark.asyncio
    async def test_us068_bot_culture_inconnue(self, db):
        assert "Culture inconnue" in await self._appeler(db, "kiwano")

    @pytest.mark.asyncio
    async def test_us068_bot_correction_de_fenetre_confirme_avant_et_apres(self, db):
        _culture(db, "chou-fleur")
        _importer(db, {"culture": "chou-fleur", "itineraire": "culture d'hiver",
                       "fenetres": {"oceanique": {"recolte": "décembre-mars"}}})
        texte = await self._appeler(db, "fenetre", "chou-fleur", "culture", "d'hiver", "recolte", "novembre", "à", "février")
        assert "décembre → mars" in texte and "novembre → février" in texte
        assert "propre à votre potager" in texte

    @pytest.mark.asyncio
    async def test_us068_bot_pleine_terre_en_deux_mots(self, db):
        _culture(db, "pomme de terre")
        texte = await self._appeler(db, "fenetre", "pomme", "de", "terre", "pleine", "terre", "mars-avril")
        assert "Semis en pleine terre" in texte and "mars → avril" in texte

    @pytest.mark.asyncio
    async def test_us068_bot_correction_de_duree(self, db):
        _culture(db, "courgette")
        texte = await self._appeler(db, "duree", "courgette", "recolte", "50-60")
        assert "—" in texte and "50 à 60 jours" in texte

    @pytest.mark.asyncio
    async def test_us068_bot_correction_non_reconnue(self, db):
        texte = await self._appeler(db, "duree", "courgette", "bientot")
        assert "pas reconnu" in texte

    @pytest.mark.asyncio
    async def test_us068_bot_repiquage_refuse_explique(self, db):
        _culture(db, "carotte")
        _importer(db, {"culture": "carotte", "fenetres": {"oceanique": {"semis_pleine_terre": "mars"}}})
        texte = await self._appeler(db, "duree", "carotte", "repiquage", "30")
        assert "Rien n'a été modifié" in texte

    @pytest.mark.asyncio
    async def test_us068_bot_lecteur_refuse(self, db):
        _culture(db, "tomate")
        lecteur = TenantContext(user_id=2, potager_id=1, role="lecteur")
        texte = await self._appeler(db, "duree", "tomate", "levee", "10", tenant=lecteur)
        assert texte.startswith("⛔")

    @pytest.mark.asyncio
    async def test_us068_bot_zone_lue_puis_choisie(self, db):
        assert "zone par défaut" in await self._appeler(db, "zone")
        texte = await self._appeler(db, "zone", "méditerranéen")
        assert "méditerranéen" in texte
        assert db.get(Potager, 1).zone_climatique == "mediterraneen"

    @pytest.mark.asyncio
    async def test_us068_bot_zone_hors_vocabulaire(self, db):
        texte = await self._appeler(db, "zone", "tropical")
        assert texte.startswith("❌")

    def test_us068_bot_commande_enregistree_au_menu_et_a_l_aide(self):
        from app import bot
        from app.services import menu_commandes as svc_menu

        assert "calendrier" in svc_menu.DESCRIPTIONS
        assert len(svc_menu.DESCRIPTIONS["calendrier"]) <= svc_menu.LONGUEUR_MAX_DESCRIPTION
        assert "calendrier" in bot._HELP_DOMAINES
        assert bot._HELP_CONTEXTUEL["calendrier"] is bot._HELP_CALENDRIER


# ═════════════════════════════════════════════════════════════════════════════
# US-172 — /calendrier est dictable
# ═════════════════════════════════════════════════════════════════════════════
class TestDictable:

    @pytest.mark.parametrize("phrase, cle, valeurs", [
        ("quand semer les tomates ?", ("calendrier", None), {"culture": "tomates"}),
        ("montre-moi le calendrier de la tomate", ("calendrier", None), {"culture": "tomate"}),
        ("passe mon potager en zone méditerranéenne", ("calendrier", "zone"), {"zone": "mediterraneen"}),
        ("corrige la période de semis en pépinière des tomates de février à avril", ("calendrier", "fenetre"),
         {"culture": "tomates", "phase": "semis_pepiniere", "mois_debut": "février", "mois_fin": "avril"}),
        ("délai de levée des carottes : 14 à 21 jours", ("calendrier", "duree"),
         {"culture": "carottes", "etape": "levee", "jours_min": "14", "jours_max": "21"}),
        # [CA29] Plantation : des MOIS corrigent la fenêtre…
        ("plantation des poireaux : juin-juillet", ("calendrier", "fenetre"),
         {"culture": "poireaux", "phase": "plantation", "mois_debut": "juin", "mois_fin": "juillet"}),
        ("corrige la période de plantation des tomates de mai à juin", ("calendrier", "fenetre"),
         {"culture": "tomates", "phase": "plantation", "mois_debut": "mai", "mois_fin": "juin"}),
        # … des JOURS corrigent la durée semis → plantation en place.
        ("délai avant plantation des tomates : 42 à 56 jours", ("calendrier", "duree"),
         {"culture": "tomates", "etape": "repiquage", "jours_min": "42", "jours_max": "56"}),
        ("quand planter les poireaux ?", ("calendrier", None), {"culture": "poireaux"}),
    ])
    def test_us068_phrase_reconnue(self, phrase, cle, valeurs):
        commande = interp.reconnaitre_par_regles(phrase)
        assert (commande.commande, commande.sous_commande) == cle
        assert commande.valeurs == valeurs

    @pytest.mark.parametrize("phrase", [
        "quand ai-je semé les tomates ?",           # journal du potager (US-096)
        "à quelle profondeur semer les carottes ?",  # attribut de conduite (US-161)
        "à quelle période faut-il semer une culture ?",  # savoir général (US-099)
        "calendrier des semis",
        "qu'est-ce que le délai de levée des carottes ?",
        "j'ai semé les tomates en pépinière en février",
        "quand ai-je planté les tomates ?",           # [CA29] journal du potager (US-096)
        "plantation de 10 poireaux le 3 mai",         # un geste daté, pas une fenêtre
        "plantation des poireaux le 3 mai",
        "plantation des tomates : 42",                # [CA29] la valeur ne tranche pas
        "délai de plantation des poireaux : juin",    # des mois pour une durée : refusé
    ])
    def test_us068_phrase_voisine_non_captee(self, phrase):
        assert interp.reconnaitre_par_regles(phrase) is None

    def test_us068_ca28_les_phases_proposees_en_boutons_sont_celles_du_service(self):
        """[CA28] Quatre boutons, lus à `PHASES` — jamais recopiés."""
        from app.services import menu_commandes as svc_menu

        forme = {f.cle: f for f in svc_menu.FORMES_DICTABLES}[("calendrier", "fenetre")]
        phase = next(a for a in forme.arguments if a.nom == "phase")
        assert phase.vocabulaire == cal.PHASES
        assert "plantation" in phase.question

    def test_us068_ecriture_dictee_toujours_confirmee(self):
        from app.services import menu_commandes as svc_menu

        formes = {f.cle: f for f in svc_menu.FORMES_DICTABLES if f.commande == "calendrier"}
        assert formes[("calendrier", None)].confirmation is False
        for sous in ("zone", "fenetre", "duree"):
            assert formes[("calendrier", sous)].confirmation is True

    @pytest.mark.asyncio
    async def test_us068_arguments_dictes_executes_par_le_handler(self, db):
        """Les arguments produits par l'interpréteur passent tels quels au handler."""
        from app import bot

        _culture(db, "tomate")
        commande = interp.reconnaitre_par_regles(
            "corrige la période de semis en pépinière des tomates de février à avril")
        update = MagicMock()
        update.message.reply_text = AsyncMock()
        ctx = MagicMock()
        ctx.args = list(commande.args)
        with patch.object(bot, "SessionLocal", return_value=db), \
             patch.object(bot, "current_context", return_value=CTX_A):
            await bot.cmd_calendrier(update, ctx)
        assert "février → avril" in update.message.reply_text.call_args[0][0]
        fenetre = cal.lire_calendrier(db, "tomate", 1).itineraires[0].fenetre(cal.PHASE_SEMIS_PEPINIERE)
        assert (fenetre.mois_debut, fenetre.mois_fin) == (2, 4)


# ═════════════════════════════════════════════════════════════════════════════
# API — GET /cultures/{culture}/calendrier, zone dans /potagers
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


class TestAPI:

    def test_us068_api_calendrier_d_une_culture(self, client_api, _moteur_api):
        entete = _compte(_moteur_api)
        potager_id = client_api.post("/potagers", json={"nom": "Jardin"}, headers=entete).json()["id"]
        session = sessionmaker(bind=_moteur_api)()
        session.add(CultureConfig(nom="haricot", type_organe_recolte="reproducteur", potager_id=None))
        session.commit()
        svc_import.importer(session, _manifeste({"culture": "haricot", "durees": {"levee": "7-10"},
                                                 "fenetres": {"oceanique": {"semis_pleine_terre": "mai-juillet"}}}))
        session.close()

        reponse = client_api.get("/cultures/Haricot/calendrier", headers=entete)
        assert reponse.status_code == 200
        corps = reponse.json()
        assert corps["culture_connue"] and corps["renseigne"]
        assert corps["zone_climatique"] == "oceanique"
        it = corps["itineraires"][0]
        assert it["fenetres"][0]["mois"] == [5, 6, 7]
        assert it["frise"]["6"] == ["semis_pleine_terre"]
        assert it["durees"][0] == {"etape": "levee", "jours_min": 7, "jours_max": 10,
                                   "mention": None, "affichage": "7 à 10 jours"}
        assert potager_id

    def test_us068_api_culture_inconnue_toujours_200(self, client_api, _moteur_api):
        entete = _compte(_moteur_api)
        client_api.post("/potagers", json={"nom": "Jardin"}, headers=entete)
        corps = client_api.get("/cultures/kiwano/calendrier", headers=entete).json()
        assert corps["culture_connue"] is False and corps["itineraires"] == []

    def test_us068_api_zone_deduite_puis_choisie_puis_rendue(self, client_api, _moteur_api):
        entete = _compte(_moteur_api)
        potager_id = client_api.post(
            "/potagers", json={"nom": "Jardin", "latitude": 43.61, "longitude": 3.88}, headers=entete,
        ).json()["id"]

        potager = client_api.get("/potagers", headers=entete).json()["potagers"][0]
        assert (potager["zone_climatique"], potager["zone_climatique_origine"]) == ("mediterraneen", "localisation")

        corps = client_api.patch(f"/potagers/{potager_id}", json={"zone_climatique": "montagnard"},
                                 headers=entete).json()
        assert (corps["zone_climatique"], corps["zone_climatique_origine"]) == ("montagnard", "jardinier")

        corps = client_api.patch(f"/potagers/{potager_id}", json={"zone_climatique": "auto"},
                                 headers=entete).json()
        assert corps["zone_climatique_origine"] == "localisation"

    def test_us068_api_zone_invalide_400_sans_ecriture(self, client_api, _moteur_api):
        entete = _compte(_moteur_api)
        potager_id = client_api.post("/potagers", json={"nom": "Jardin"}, headers=entete).json()["id"]
        reponse = client_api.patch(f"/potagers/{potager_id}", json={"nom": "Autre", "zone_climatique": "tropical"},
                                   headers=entete)
        assert reponse.status_code == 400
        assert client_api.get("/potagers", headers=entete).json()["potagers"][0]["nom"] == "Jardin"


# ═════════════════════════════════════════════════════════════════════════════
# Migration — la structure décrite en SQL est celle du modèle
# ═════════════════════════════════════════════════════════════════════════════
def test_us068_migration_et_rollback_existent_et_ne_sement_aucun_calendrier():
    migration = (RACINE / "migrations" / "migration_v46.sql").read_text(encoding="utf-8")
    rollback = (RACINE / "migrations" / "rollback_v46.sql").read_text(encoding="utf-8")
    for table in ("itineraire_cultural", "fenetre_culturale", "duree_culturale"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in migration
        assert f"ENABLE ROW LEVEL SECURITY" in migration
        assert f"DROP TABLE IF EXISTS {table}" in rollback
    assert "ADD COLUMN IF NOT EXISTS zone_climatique" in migration
    assert "INSERT INTO itineraire_cultural" not in migration
    assert "INSERT INTO fenetre_culturale" not in migration
    assert "INSERT INTO duree_culturale" not in migration

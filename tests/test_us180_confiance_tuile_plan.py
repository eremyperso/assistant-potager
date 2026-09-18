"""
tests/test_us180_confiance_tuile_plan.py — Confiance sur les tuiles du Plan [US-180]
=====================================================================================

L'écran Plan lit le moteur d'US-178 ; ce fichier vérifie ce que la lecture doit
lui donner, critère par critère :

- CA1  une action EN FENÊTRE OU À UN MOIS de la date de référence est candidate
- CA2  deux phases candidates : la mieux notée d'abord, l'égalité laissée au front
       (la règle de priorité des phases vit avec la frise — `lib/calendrier.js`)
- CA3  hors fenêtre → aucune candidate ; sans calendrier → `a_calendrier` faux,
       et les deux cas se distinguent l'un de l'autre
- CA4  la date de référence recalcule l'action retenue
- CA5  la fiche de détail a de quoi s'écrire : règles, points, récolte attendue
- CA6  UNE lecture groupée, UNE lecture météo pour tout l'écran
- CA7  la lecture ne casse jamais l'écran : toujours 200, jamais de repli
- CA12 ce fichier, et `frontend/src/lib/confiance.test.js` pour l'affichage

⚠️ Les fenêtres, durées et rusticités écrites ici sont des VALEURS DE TEST :
elles n'engagent aucune agronomie.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import calendrier_cultural as cal
from app.services import confiance_semis as conf
from app.services import previsions_meteo as svc_previsions
from app.services.context import TenantContext
from database.db import Base
from database.models import (
    CultureConfig, DureeCulturale, FenetreCulturale, ItineraireCultural,
    Parcelle, Potager, ReferentielSource, User,
)

CTX = TenantContext(user_id=1, potager_id=1, role="owner")

LE_5_MAI = date(2027, 5, 5)
LE_20_FEVRIER = date(2027, 2, 20)
LE_15_AOUT = date(2027, 8, 15)


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures et graines
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def db(test_db):
    """Un potager localisé en zone océanique, une parcelle ordinaire."""
    test_db.add(User(id=1, email="a@potager.test"))
    test_db.flush()
    test_db.add(Potager(id=1, nom="Jardin", proprietaire_id=1, zone_climatique="oceanique",
                        latitude=47.2, longitude=-1.55))
    test_db.flush()
    test_db.add(Parcelle(id=1, nom="nord", nom_normalise="nord", potager_id=1))
    test_db.add(ReferentielSource(
        id=1, code="test", libelle="Test", licence="CC0",
        attribution="Valeurs de test", partageable=True, importee=True,
    ))
    test_db.commit()
    return test_db


def _seed_culture(db, nom: str, *, rusticite=None, fenetres=None, durees=None) -> None:
    """Une culture, son itinéraire standard, ses fenêtres et ses durées."""
    fiche = CultureConfig(nom=nom, type_organe_recolte="fruit", rusticite_min_c=rusticite)
    db.add(fiche)
    db.flush()
    it = ItineraireCultural(
        culture_id=fiche.id, nom="standard", nom_normalise="standard", source_id=1,
    )
    db.add(it)
    db.flush()
    for phase, (debut, fin) in (fenetres or {}).items():
        db.add(FenetreCulturale(
            itineraire_id=it.id, zone_climatique="oceanique", phase=phase,
            mois_debut=debut, mois_fin=fin, source_id=1,
        ))
    for etape, (jours_min, jours_max) in (durees or {}).items():
        db.add(DureeCulturale(
            itineraire_id=it.id, etape=etape, jours_min=jours_min, jours_max=jours_max,
            source_id=1,
        ))
    db.commit()


def _tomate(db) -> None:
    """Pépinière février-mars, plantation avril-mai, récolte juillet-septembre."""
    _seed_culture(
        db, "tomate", rusticite=5.0,
        fenetres={
            cal.PHASE_SEMIS_PEPINIERE: (2, 3),
            cal.PHASE_PLANTATION: (4, 5),
            cal.PHASE_RECOLTE: (7, 9),
        },
        durees={cal.ETAPE_RECOLTE: (100, 120), cal.ETAPE_PLANTATION_RECOLTE: (60, 80)},
    )


def _concombre(db) -> None:
    """Semis en place ET plantation en mai : deux phases candidates le même mois."""
    _seed_culture(
        db, "concombre", rusticite=5.0,
        fenetres={
            cal.PHASE_SEMIS_PLEINE_TERRE: (5, 6),
            cal.PHASE_PLANTATION: (5, 6),
            cal.PHASE_RECOLTE: (7, 9),
        },
        durees={cal.ETAPE_RECOLTE: (55, 70), cal.ETAPE_PLANTATION_RECOLTE: (45, 60)},
    )


def _meteo(depart: date, tmin: float, gel_le: date = None):
    """Quatorze jours de prévision d'US-182, sans réseau ni cache."""
    return svc_previsions.LecturePrevision(
        statut=svc_previsions.STATUT_DISPONIBLE,
        meteo={"previsions_etendues": [
            {"date": (depart + timedelta(days=i)).isoformat(),
             "temp_min": -1.0 if gel_le == depart + timedelta(days=i) else tmin,
             "temp_max": tmin + 10, "horizon_jours": i + 1}
            for i in range(14)
        ]},
        source=svc_previsions.SOURCE_CACHE,
    )


def _sans_meteo():
    """Potager sans localisation : R3 et R4 restent indéterminées (US-178 / CA5)."""
    return svc_previsions.LecturePrevision(
        statut=svc_previsions.STATUT_LOCALISATION_MANQUANTE, meteo=None, source=None,
    )


# ═════════════════════════════════════════════════════════════════════════════
# CA1 / CA3 — ce qui fait une candidate, et ce qui n'en fait pas
# ═════════════════════════════════════════════════════════════════════════════
class TestCandidates:
    def test_us180_action_en_fenetre_est_candidate(self, db):
        """[Gherkin: Tuile en fenêtre de plantation] Le 5 mai, la tomate se plante."""
        _tomate(db)
        lu = conf.confiances_de_culture(db, "tomate", LE_5_MAI, 1, _meteo(LE_5_MAI, 11.0))
        assert lu.a_calendrier is True
        assert [c.action for c in lu.candidates] == [conf.ACTION_PLANTATION]
        assert lu.candidates[0].etoiles == 3

    def test_us180_action_a_un_mois_est_candidate(self, db):
        """[CA1] Un mois avant la fenêtre suffit — R1 la donne à 20 points, et c'est
        le SEUL mécanisme d'approche : aucune marge ne vit en double ici."""
        le_20_janvier = date(2027, 1, 20)
        _tomate(db)
        lu = conf.confiances_de_culture(db, "tomate", le_20_janvier, 1, _meteo(le_20_janvier, 2.0))
        assert [c.action for c in lu.candidates] == [conf.ACTION_SEMIS_PEPINIERE]
        motif_r1 = next(m for m in lu.candidates[0].motifs if m.regle == conf.R1_FENETRE)
        assert motif_r1.points == conf.POINTS_R1_MOIS_ADJACENT

    def test_us180_hors_fenetre_aucune_candidate(self, db):
        """[Gherkin: Rien à faire cette semaine] Le 15 août, rien ne se sème ni ne se
        plante : la tuile se tait, mais la culture A un calendrier."""
        _tomate(db)
        lu = conf.confiances_de_culture(db, "tomate", LE_15_AOUT, 1, _meteo(LE_15_AOUT, 14.0))
        assert lu.candidates == []
        assert lu.a_calendrier is True

    def test_us180_sans_calendrier_se_distingue_de_rien_a_faire(self, db):
        """[CA3] Aucune fenêtre pour la zone : `a_calendrier` faux — c'est ce que la
        fiche de détail oppose au silence de « rien à faire cette semaine »."""
        _seed_culture(db, "ail", fenetres={}, durees={})
        lu = conf.confiances_de_culture(db, "ail", LE_5_MAI, 1, _meteo(LE_5_MAI, 11.0))
        assert lu.candidates == [] and lu.a_calendrier is False
        assert lu.culture_connue is True

    def test_us180_culture_inconnue_ne_leve_pas(self, db):
        """[CA7] Une culture absente du référentiel n'a ni calendrier ni erreur."""
        lu = conf.confiances_de_culture(db, "salsifis", LE_5_MAI, 1, _meteo(LE_5_MAI, 11.0))
        assert lu.candidates == [] and lu.a_calendrier is False
        assert lu.culture_connue is False

    def test_us180_recolte_n_est_jamais_une_action_de_tuile(self, db):
        """[CA1] On ne décide pas de récolter : la récolte n'est pas une candidate."""
        assert cal.PHASE_RECOLTE not in conf.ACTIONS_DE_TUILE
        _tomate(db)
        le_1er_aout = date(2027, 8, 1)
        lu = conf.confiances_de_culture(db, "tomate", le_1er_aout, 1, _meteo(le_1er_aout, 14.0))
        assert all(c.action != cal.PHASE_RECOLTE for c in lu.candidates)


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — deux phases candidates le même mois
# ═════════════════════════════════════════════════════════════════════════════
class TestDeuxPhases:
    def test_us180_deux_phases_candidates_triees_par_score(self, db):
        """[Gherkin: Deux phases candidates] Semis en place et plantation du concombre
        en mai : les deux sortent, la mieux notée en tête."""
        le_10_mai = date(2027, 5, 10)
        _concombre(db)
        lu = conf.confiances_de_culture(db, "concombre", le_10_mai, 1, _meteo(le_10_mai, 11.0))
        assert {c.action for c in lu.candidates} == {
            conf.ACTION_SEMIS_PLEINE_TERRE, conf.ACTION_PLANTATION,
        }
        scores = [c.score for c in lu.candidates]
        assert scores == sorted(scores, reverse=True)

    def test_us180_egalite_rendue_dans_l_ordre_du_geste(self, db):
        """[CA2] À score égal, le serveur ne tranche PAS : il rend les ex æquo dans
        l'ordre du geste et laisse l'arbitrage à la règle de priorité de la frise."""
        le_10_mai = date(2027, 5, 10)
        _concombre(db)
        lu = conf.confiances_de_culture(db, "concombre", le_10_mai, 1, _meteo(le_10_mai, 11.0))
        meilleur = lu.candidates[0].score
        ex_aequo = [c.action for c in lu.candidates if c.score == meilleur]
        assert ex_aequo == [a for a in conf.ACTIONS_DE_TUILE if a in set(ex_aequo)]

    def test_us180_aucune_seconde_regle_de_priorite_dans_le_moteur(self):
        """[CA2] La règle de priorité des phases vit au même endroit que celle de la
        frise (`PRIORITE_PHASES`, `frontend/src/lib/calendrier.js`). Ce test interdit
        qu'une copie apparaisse côté moteur."""
        source = Path(conf.__file__).read_text(encoding="utf-8")
        assert "PRIORITE" not in source


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — la date de référence recalcule tout
# ═════════════════════════════════════════════════════════════════════════════
class TestDateDeReference:
    def test_us180_reculer_la_date_change_l_action(self, db):
        """[Gherkin: La date de référence recalcule l'indicateur] Plantation au 5 mai,
        semis en pépinière au 20 février — même culture, même zone."""
        _tomate(db)
        en_mai = conf.confiances_de_culture(db, "tomate", LE_5_MAI, 1, _meteo(LE_5_MAI, 11.0))
        en_fevrier = conf.confiances_de_culture(db, "tomate", LE_20_FEVRIER, 1,
                                                _meteo(LE_20_FEVRIER, 3.0))
        assert en_mai.candidates[0].action == conf.ACTION_PLANTATION
        assert en_fevrier.candidates[0].action == conf.ACTION_SEMIS_PEPINIERE

    def test_us180_la_date_cible_est_celle_demandee(self, db):
        """[CA4] Chaque candidate porte la date de référence, pas aujourd'hui."""
        _tomate(db)
        lu = conf.confiances_de_culture(db, "tomate", LE_5_MAI, 1, _meteo(LE_5_MAI, 11.0))
        assert all(c.date_cible == LE_5_MAI for c in lu.candidates)


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — de quoi écrire la fiche de détail
# ═════════════════════════════════════════════════════════════════════════════
class TestFicheDeDetail:
    def test_us180_chaque_regle_porte_points_motif_et_etat(self, db):
        """[CA5] Cinq règles, chacune avec ses points sur son maximum et son état."""
        _tomate(db)
        lu = conf.confiances_de_culture(db, "tomate", LE_5_MAI, 1, _meteo(LE_5_MAI, 11.0))
        corps = conf.confiances_culture_en_dict(lu)["candidates"][0]
        assert len(corps["motifs"]) == 5
        assert all(
            m["libelle"] and m["regle_libelle"]
            and m["etat"] in {"gagne", "perdu", "indetermine"}
            and 0 <= m["points"] <= m["points_max"]
            for m in corps["motifs"]
        )

    def test_us180_recolte_attendue_est_une_fourchette(self, db):
        """[CA5] La récolte attendue si le geste est fait à la date de référence —
        une fourchette, jamais une date sèche."""
        _tomate(db)
        lu = conf.confiances_de_culture(db, "tomate", LE_5_MAI, 1, _meteo(LE_5_MAI, 11.0))
        plantation = lu.candidates[0]
        assert plantation.recolte_min == LE_5_MAI + timedelta(days=60)
        assert plantation.recolte_max == LE_5_MAI + timedelta(days=80)

    def test_us180_recolte_inconnue_reste_vide(self, db):
        """[CA5] Sans durée, aucune borne : la fiche affiche un tiret, pas une date."""
        _seed_culture(db, "poireau", rusticite=-10.0,
                      fenetres={cal.PHASE_PLANTATION: (5, 6), cal.PHASE_RECOLTE: (10, 12)})
        lu = conf.confiances_de_culture(db, "poireau", LE_5_MAI, 1, _meteo(LE_5_MAI, 11.0))
        corps = conf.confiances_culture_en_dict(lu)["candidates"][0]
        assert corps["recolte_attendue"] == {"min": None, "max": None}

    def test_us180_potager_non_localise_laisse_la_meteo_indeterminee(self, db):
        """[Gherkin: Potager non localisé] R3 et R4 indéterminées, plafond abaissé :
        la fiche a de quoi inviter à localiser le potager."""
        _tomate(db)
        lu = conf.confiances_de_culture(db, "tomate", LE_5_MAI, 1, _sans_meteo())
        plantation = lu.candidates[0]
        indetermines = {m.regle for m in plantation.motifs if m.indetermine}
        assert indetermines == {conf.R3_GEL_ANNONCE, conf.R4_NUITS_DOUCES}
        assert plantation.score_max_atteignable == 70
        assert plantation.avertissements


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — une seule lecture groupée, une seule lecture météo
# ═════════════════════════════════════════════════════════════════════════════
class TestLectureGroupee:
    def test_us180_une_seule_lecture_meteo_pour_tout_l_ecran(self, db):
        """[CA6] Trois cultures × trois actions : la météo est lue UNE fois."""
        _tomate(db)
        _concombre(db)
        _seed_culture(db, "ail", fenetres={}, durees={})
        with patch.object(svc_previsions, "lire_prevision_potager",
                          return_value=_meteo(LE_5_MAI, 11.0)) as lecture:
            lu = conf.confiances_du_plan(db, ["tomate", "concombre", "ail"], LE_5_MAI, 1)
        assert lecture.call_count == 1
        assert set(lu) == {"tomate", "concombre", "ail"}

    def test_us180_cultures_dedoublonnees(self, db):
        """[CA6] La même culture sur deux parcelles ne se lit pas deux fois."""
        _tomate(db)
        with patch.object(svc_previsions, "lire_prevision_potager",
                          return_value=_meteo(LE_5_MAI, 11.0)):
            lu = conf.confiances_du_plan(db, ["tomate", "tomate", "", None], LE_5_MAI, 1)
        assert list(lu) == ["tomate"]


# ═════════════════════════════════════════════════════════════════════════════
# US-178 / CA11 — la lecture de l'écran Plan n'écrit rien
# ═════════════════════════════════════════════════════════════════════════════
def test_us180_lecture_sans_ecriture(db):
    """Aucune fenêtre, aucune durée, aucun itinéraire créé par la consultation."""
    _tomate(db)
    compter = lambda: (db.query(FenetreCulturale).count(), db.query(DureeCulturale).count(),
                       db.query(ItineraireCultural).count())
    avant = compter()
    with patch.object(svc_previsions, "lire_prevision_potager",
                      return_value=_meteo(LE_5_MAI, 11.0)):
        conf.confiances_du_plan(db, ["tomate"], LE_5_MAI, 1)
    assert compter() == avant


# ═════════════════════════════════════════════════════════════════════════════
# CA6 / CA7 — l'API de l'écran
# ═════════════════════════════════════════════════════════════════════════════
class TestApi:
    """L'API tourne dans le thread du client de test : son propre moteur SQLite."""

    @pytest.fixture
    def db_api(self):
        moteur = create_engine("sqlite:///:memory:",
                               connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=moteur)
        session = sessionmaker(bind=moteur)()
        session.add(User(id=1, email="a@potager.test"))
        session.flush()
        session.add(Potager(id=1, nom="Jardin", proprietaire_id=1,
                            zone_climatique="oceanique", latitude=47.2, longitude=-1.55))
        session.add(ReferentielSource(id=1, code="test", libelle="Test", licence="CC0",
                                      attribution="Valeurs de test", partageable=True,
                                      importee=True))
        session.commit()
        yield session, moteur
        session.close()
        moteur.dispose()

    @pytest.fixture
    def client(self, db_api, monkeypatch):
        from app.api import main as api

        _, moteur = db_api
        monkeypatch.setattr(api, "SessionLocal", sessionmaker(bind=moteur))
        api.app.dependency_overrides[api.get_current_user_ctx] = lambda: CTX
        api.app.state.limiter.reset()
        with TestClient(api.app) as client:
            yield client
        api.app.dependency_overrides.clear()

    def test_us180_api_candidates_du_plan(self, db_api, client):
        """[CA6] Toutes les tuiles de l'écran en un appel, à la date de référence."""
        _tomate(db_api[0])
        _concombre(db_api[0])
        with patch.object(svc_previsions, "lire_prevision_potager",
                          return_value=_meteo(LE_5_MAI, 11.0)):
            r = client.get("/plan/confiances/candidates", params={
                "culture": ["tomate", "concombre"], "date": "2027-05-05",
            })
        assert r.status_code == 200
        corps = r.json()
        assert corps["date"] == "2027-05-05"
        assert set(corps["cultures"]) == {"tomate", "concombre"}
        tomate = corps["cultures"]["tomate"]
        assert tomate["a_calendrier"] is True
        assert tomate["candidates"][0]["action"] == conf.ACTION_PLANTATION
        # Le libellé du moteur reste celui du bot (US-179) ; « Planter » est un
        # libellé d'INTERFACE, écrit côté PWA (`lib/confiance.js`).
        assert tomate["candidates"][0]["action_libelle"] == "plantation"
        assert tomate["candidates"][0]["etoiles"] == 3

    def test_us180_api_sans_calendrier_rend_200_et_le_dit(self, db_api, client):
        """[CA3, CA7] Jamais d'erreur, jamais de repli : `a_calendrier` faux et aucune
        candidate — la tuile n'affiche alors rien."""
        _seed_culture(db_api[0], "ail", fenetres={}, durees={})
        r = client.get("/plan/confiances/candidates",
                       params={"culture": ["ail"], "date": "2027-05-05"})
        assert r.status_code == 200
        assert r.json()["cultures"]["ail"] == {
            "culture": "ail", "culture_connue": True, "a_calendrier": False, "candidates": [],
            "actions": [],
        }

    def test_us180_api_sans_culture_rend_un_corps_vide(self, db_api, client):
        """[CA7] Un écran sans culture n'appelle rien d'exotique : 200, aucune culture."""
        r = client.get("/plan/confiances/candidates")
        assert r.status_code == 200 and r.json()["cultures"] == {}

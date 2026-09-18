"""
tests/test_us182_previsions_meteo.py — [US-182] Prévisions météo à 14 jours, en cache
--------------------------------------------------------------------------------------
Couvre CA1 (14 jours, non-régression des clés), CA2 (cache partagé par
localisation), CA3 (validité déclarée une fois, rafraîchissement à la lecture),
CA4 (lecture groupée en un appel), CA5 (indisponibilité avec/sans cache, âge
exposé), CA6 (potager sans localisation), CA7 (journalisation) et CA8
(non-régression GET /meteo, job 5 h / `/meteo` Telegram sans cache).

Le cache est vidé avant chaque test par la fixture autouse de `conftest.py`.
"""
import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import requests as req_module
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import auth as svc_auth
from app.services import potagers as svc_potagers
from app.services import previsions_meteo as svc
from database.db import Base
from utils.meteo import (
    METEO_HORIZON_PREVISION_JOURS,
    fetch_meteo,
    fetch_meteo_groupe,
    format_meteo_commentaire,
    jour_local,
)

MAINTENANT = datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc)  # 10 h à Paris
PARIS = (48.961, 2.204)
MARSEILLE = (43.296, 5.381)
LYON = (45.764, 4.836)


# ── Fixtures : réponse Open-Meteo simulée (aujourd'hui + 14 jours) ─────────────

def _reponse_open_meteo(nb_jours: int = METEO_HORIZON_PREVISION_JOURS + 1, tmin_depart: float = 5.0) -> dict:
    jours = [(datetime(2026, 6, 1) + timedelta(days=i)).date().isoformat() for i in range(nb_jours)]
    return {
        "current": {"temperature_2m": 18.4, "apparent_temperature": 17.1,
                    "relative_humidity_2m": 62, "wind_speed_10m": 12.3, "weather_code": 2},
        "hourly": {
            "time"                     : [f"2026-06-01T{h:02d}:00" for h in range(24)],
            "temperature_2m"           : [10.0 + h * 0.3 for h in range(24)],
            "precipitation_probability": [5] * 24,
            "precipitation"            : [0.0] * 24,
            "windspeed_10m"            : [10.0] * 24,
            "weathercode"              : [2] * 24,
        },
        "daily": {
            "time"                          : jours,
            "weathercode"                   : [(i * 7) % 4 for i in range(nb_jours)],
            "temperature_2m_max"            : [20.0 + i for i in range(nb_jours)],
            "temperature_2m_min"            : [tmin_depart - i for i in range(nb_jours)],
            "precipitation_sum"             : [0.0] * nb_jours,
            "precipitation_probability_max" : [10] * nb_jours,
            "windspeed_10m_max"             : [15.0] * nb_jours,
            "sunrise"                       : [f"{j}T05:50" for j in jours],
            "sunset"                        : [f"{j}T21:40" for j in jours],
        },
    }


def _mock_response(data) -> MagicMock:
    m = MagicMock()
    m.json.return_value = data
    m.raise_for_status.return_value = None
    return m


def _reponse_pour(*_, params=None, **__) -> MagicMock:
    """Répond à un appel simple ou groupé avec autant de localisations que demandé."""
    nb = len(str(params["latitude"]).split(","))
    return _mock_response(_reponse_open_meteo() if nb == 1 else [_reponse_open_meteo()] * nb)


def _patch_open_meteo(**kwargs):
    if not kwargs:
        kwargs = {"side_effect": _reponse_pour}
    return patch("utils.meteo.requests.get", **kwargs)


# ── CA1 — Quatorze jours, clés existantes conservées ────────────────────────────

def test_us182_fetch_meteo_demande_horizon_complet() -> None:
    """CA1 — `forecast_days` découle de l'horizon déclaré (aujourd'hui + 14)."""
    with _patch_open_meteo() as mock_get:
        fetch_meteo()
    assert mock_get.call_args[1]["params"]["forecast_days"] == METEO_HORIZON_PREVISION_JOURS + 1


def test_us182_fetch_meteo_quatorze_jours() -> None:
    """CA1 — Gherkin « Quatorze jours de prévision » : Tmin, Tmax, code et horizon par jour."""
    with _patch_open_meteo():
        meteo = fetch_meteo()
    etendues = meteo["previsions_etendues"]
    assert len(etendues) == 14
    assert [j["horizon_jours"] for j in etendues] == list(range(1, 15))
    assert etendues[0]["date"] == "2026-06-02"
    assert etendues[-1]["date"] == "2026-06-15"
    for jour in etendues:
        assert {"temp_min", "temp_max", "wmo_code"}.issubset(jour)
    assert etendues[13]["temp_min"] == pytest.approx(5.0 - 14)


def test_us182_fetch_meteo_non_regression_des_cles() -> None:
    """CA1 / CA8 — aucune clé US-075 renommée ni retirée ; `previsions` reste à 5 jours."""
    cles_existantes = {
        "wmo_code", "emoji", "label", "temp_min", "temp_max", "temp_matin", "temp_aprem",
        "precipitations", "proba_pluie", "proba_matin", "proba_aprem", "vent_max_kmh",
        "lever_soleil", "coucher_soleil", "conseil", "date",
        "previsions", "temp_actuelle", "ressenti", "humidite", "vent_actuel_kmh",
    }
    with _patch_open_meteo():
        meteo = fetch_meteo()
    assert cles_existantes.issubset(meteo)
    assert len(meteo["previsions"]) == 5
    assert "horizon_jours" not in meteo["previsions"][0]
    assert format_meteo_commentaire(meteo)


def test_us182_fetch_meteo_reponse_courte_ne_leve_pas() -> None:
    """CA1 — Open-Meteo rend moins de jours que demandé : on rend ce qui existe, sans inventer."""
    with _patch_open_meteo(return_value=_mock_response(_reponse_open_meteo(nb_jours=4))):
        meteo = fetch_meteo()
    assert len(meteo["previsions_etendues"]) == 3
    assert len(meteo["previsions"]) == 3


def test_us182_lecture_potager_rend_quatorze_jours() -> None:
    """CA1 — la lecture en cache d'un potager localisé rend les 14 jours."""
    potager = SimpleNamespace(id=1, latitude=PARIS[0], longitude=PARIS[1])
    with _patch_open_meteo():
        lecture = svc.lire_prevision_potager(potager, maintenant=MAINTENANT)
    assert lecture.disponible
    assert len(lecture.meteo["previsions_etendues"]) == 14
    assert lecture.source == svc.SOURCE_OPEN_METEO
    assert lecture.age_secondes == 0


# ── CA2 — Cache partagé par localisation ────────────────────────────────────────

def test_us182_cache_deux_potagers_meme_localisation_un_appel() -> None:
    """CA2 — Gherkin « Cache partagé par localisation »."""
    potager_a = SimpleNamespace(id=1, latitude=PARIS[0], longitude=PARIS[1])
    potager_b = SimpleNamespace(id=2, latitude=PARIS[0], longitude=PARIS[1])
    with _patch_open_meteo() as mock_get:
        premiere = svc.lire_prevision_potager(potager_a, maintenant=MAINTENANT)
        seconde = svc.lire_prevision_potager(potager_b, maintenant=MAINTENANT + timedelta(minutes=5))
    assert mock_get.call_count == 1
    assert premiere.source == svc.SOURCE_OPEN_METEO
    assert seconde.source == svc.SOURCE_CACHE
    assert seconde.age_secondes == 300


def test_us182_cache_coordonnees_arrondies_partagent_l_entree() -> None:
    """CA2 — deux potagers à quelques mètres l'un de l'autre partagent l'entrée."""
    with _patch_open_meteo() as mock_get:
        svc.lire_previsions(48.96101, 2.20399, maintenant=MAINTENANT)
        svc.lire_previsions(48.96098, 2.20402, maintenant=MAINTENANT)
    assert mock_get.call_count == 1
    assert svc.cle_localisation(48.96101, 2.20399) == svc.cle_localisation(48.96098, 2.20402)


def test_us182_cache_localisations_distinctes_ne_partagent_pas() -> None:
    """CA2 — deux lieux différents font chacun leur appel."""
    with _patch_open_meteo() as mock_get:
        svc.lire_previsions(*PARIS, maintenant=MAINTENANT)
        svc.lire_previsions(*MARSEILLE, maintenant=MAINTENANT)
    assert mock_get.call_count == 2


def test_us182_cache_fuseau_distinct_ne_partage_pas() -> None:
    """CA2 — le fuseau découpe les journées : une prévision de Paris n'est pas servie pour Montréal."""
    with _patch_open_meteo() as mock_get:
        svc.lire_previsions(*PARIS, fuseau="Europe/Paris", maintenant=MAINTENANT)
        svc.lire_previsions(*PARIS, fuseau="America/Montreal", maintenant=MAINTENANT)
    assert mock_get.call_count == 2


def test_us182_cache_copie_protege_l_entree() -> None:
    """CA2 — un consommateur qui modifie sa météo ne corrompt pas la lecture suivante."""
    with _patch_open_meteo():
        premiere = svc.lire_previsions(*PARIS, maintenant=MAINTENANT)
        premiere.meteo["previsions_etendues"].clear()
        seconde = svc.lire_previsions(*PARIS, maintenant=MAINTENANT)
    assert len(seconde.meteo["previsions_etendues"]) == 14


# ── CA3 — Validité déclarée une fois, rafraîchissement à la lecture ─────────────

def test_us182_cache_valide_avant_expiration() -> None:
    """CA3 — juste avant l'expiration, aucune relecture réseau."""
    with _patch_open_meteo() as mock_get:
        svc.lire_previsions(*PARIS, maintenant=MAINTENANT)
        lecture = svc.lire_previsions(
            *PARIS, maintenant=MAINTENANT + svc.DUREE_VALIDITE_CACHE - timedelta(seconds=1),
        )
    assert mock_get.call_count == 1
    assert lecture.source == svc.SOURCE_CACHE


def test_us182_cache_expire_rafraichi_a_la_lecture_suivante() -> None:
    """CA3 — une entrée expirée est rafraîchie par la lecture, pas par un job."""
    plus_tard = MAINTENANT + svc.DUREE_VALIDITE_CACHE
    with _patch_open_meteo() as mock_get:
        svc.lire_previsions(*PARIS, maintenant=MAINTENANT)
        lecture = svc.lire_previsions(*PARIS, maintenant=plus_tard)
    assert mock_get.call_count == 2
    assert lecture.source == svc.SOURCE_OPEN_METEO
    assert lecture.recuperee_le == plus_tard
    assert lecture.age_secondes == 0


def test_us182_cache_duree_lue_depuis_la_seule_declaration(monkeypatch) -> None:
    """CA3 — changer `DUREE_VALIDITE_CACHE` suffit à changer le comportement."""
    monkeypatch.setattr(svc, "DUREE_VALIDITE_CACHE", timedelta(minutes=10))
    with _patch_open_meteo() as mock_get:
        svc.lire_previsions(*PARIS, maintenant=MAINTENANT)
        svc.lire_previsions(*PARIS, maintenant=MAINTENANT + timedelta(minutes=11))
    assert mock_get.call_count == 2


def test_us182_cache_changement_de_jour_force_un_appel() -> None:
    """CA3 — le lendemain, même dans la durée de validité, la clé change."""
    avant_minuit = datetime(2026, 6, 1, 21, 50, tzinfo=timezone.utc)   # 23 h 50 à Paris
    apres_minuit = datetime(2026, 6, 1, 22, 10, tzinfo=timezone.utc)   # 00 h 10 à Paris
    with _patch_open_meteo() as mock_get:
        svc.lire_previsions(*PARIS, maintenant=avant_minuit)
        lecture = svc.lire_previsions(*PARIS, maintenant=apres_minuit)
    assert mock_get.call_count == 2
    assert lecture.source == svc.SOURCE_OPEN_METEO


def test_us182_cache_purge_les_jours_passes() -> None:
    """CA3 — l'entrée d'hier est purgée au premier rafraîchissement du jour."""
    with _patch_open_meteo():
        svc.lire_previsions(*PARIS, maintenant=MAINTENANT)
        svc.lire_previsions(*MARSEILLE, maintenant=MAINTENANT + timedelta(days=1))
    assert {cle[3] for cle in svc._CACHE} == {jour_local(maintenant=MAINTENANT + timedelta(days=1))}


def test_us182_jour_local_suit_le_fuseau_du_potager() -> None:
    """CA3 — 23 h 30 UTC est déjà le lendemain à Paris."""
    instant = datetime(2026, 6, 1, 23, 30, tzinfo=timezone.utc)
    assert jour_local("Europe/Paris", instant).isoformat() == "2026-06-02"
    assert jour_local("UTC", instant).isoformat() == "2026-06-01"


def test_us182_jour_local_fuseau_inconnu_journalise(caplog) -> None:
    """CA3 / CA7 — un fuseau inconnu retombe sur la date fournie, sans silence."""
    with caplog.at_level(logging.WARNING, logger="potager"):
        jour = jour_local("Nulle/Part", MAINTENANT)
    assert jour == MAINTENANT.date()
    assert "fuseau inconnu" in caplog.text


# ── CA4 — Lecture groupée ───────────────────────────────────────────────────────

def test_us182_groupe_deux_en_cache_un_seul_appel() -> None:
    """CA4 — Gherkin « Lecture groupée » : trois localisations dont deux en cache."""
    with _patch_open_meteo():
        svc.lire_previsions(*PARIS, maintenant=MAINTENANT)
        svc.lire_previsions(*MARSEILLE, maintenant=MAINTENANT)
    with _patch_open_meteo() as mock_get:
        lectures = svc.lire_previsions_groupees([PARIS, MARSEILLE, LYON], maintenant=MAINTENANT)
    assert mock_get.call_count == 1
    params = mock_get.call_args[1]["params"]
    assert params["latitude"] == pytest.approx(LYON[0])
    assert [l.source for l in lectures] == [svc.SOURCE_CACHE, svc.SOURCE_CACHE, svc.SOURCE_OPEN_METEO]


def test_us182_groupe_toutes_en_cache_aucun_appel() -> None:
    """CA4 — aucune localisation à rafraîchir : aucun appel réseau."""
    with _patch_open_meteo():
        svc.lire_previsions_groupees([PARIS, MARSEILLE], maintenant=MAINTENANT)
    with _patch_open_meteo(side_effect=AssertionError("ne doit pas être appelé")):
        lectures = svc.lire_previsions_groupees([PARIS, MARSEILLE], maintenant=MAINTENANT)
    assert all(l.source == svc.SOURCE_CACHE for l in lectures)


def test_us182_groupe_plusieurs_absentes_en_un_appel() -> None:
    """CA4 — trois localisations absentes du cache : un seul appel Open-Meteo groupé."""
    with _patch_open_meteo() as mock_get:
        lectures = svc.lire_previsions_groupees([PARIS, MARSEILLE, LYON], maintenant=MAINTENANT)
    assert mock_get.call_count == 1
    params = mock_get.call_args[1]["params"]
    assert params["latitude"] == f"{PARIS[0]},{MARSEILLE[0]},{LYON[0]}"
    assert params["longitude"] == f"{PARIS[1]},{MARSEILLE[1]},{LYON[1]}"
    assert all(l.disponible and len(l.meteo["previsions_etendues"]) == 14 for l in lectures)


def test_us182_groupe_ordre_et_doublons_conserves() -> None:
    """CA4 — une lecture par localisation reçue, dans l'ordre ; un doublon ne coûte rien."""
    with _patch_open_meteo() as mock_get:
        lectures = svc.lire_previsions_groupees(
            [PARIS, (None, None), PARIS, MARSEILLE], maintenant=MAINTENANT,
        )
    assert mock_get.call_count == 1
    assert mock_get.call_args[1]["params"]["latitude"] == f"{PARIS[0]},{MARSEILLE[0]}"
    assert [l.statut for l in lectures] == [
        svc.STATUT_DISPONIBLE, svc.STATUT_LOCALISATION_MANQUANTE,
        svc.STATUT_DISPONIBLE, svc.STATUT_DISPONIBLE,
    ]


def test_us182_groupe_par_potager() -> None:
    """CA4 — lecture groupée de potagers, indexée par identifiant."""
    potagers = [
        SimpleNamespace(id=10, latitude=PARIS[0], longitude=PARIS[1]),
        SimpleNamespace(id=11, latitude=None, longitude=None),
        SimpleNamespace(id=12, latitude=MARSEILLE[0], longitude=MARSEILLE[1]),
    ]
    with _patch_open_meteo() as mock_get:
        lectures = svc.lire_previsions_potagers(potagers, maintenant=MAINTENANT)
    assert mock_get.call_count == 1
    assert set(lectures) == {10, 11, 12}
    assert lectures[11].statut == svc.STATUT_LOCALISATION_MANQUANTE
    assert lectures[10].disponible and lectures[12].disponible


def test_us182_groupe_vide_aucun_appel() -> None:
    """CA4 — rien à lire, rien à appeler."""
    with _patch_open_meteo(side_effect=AssertionError("ne doit pas être appelé")):
        assert svc.lire_previsions_groupees([], maintenant=MAINTENANT) == []
        assert fetch_meteo_groupe([]) == []


def test_us182_fetch_groupe_reponse_partiellement_malformee(caplog) -> None:
    """CA4 / CA5 — une réponse malformée n'annule pas les autres, et se journalise."""
    with caplog.at_level(logging.WARNING, logger="potager"):
        with _patch_open_meteo(return_value=_mock_response([_reponse_open_meteo(), {"error": True}])):
            resultats = fetch_meteo_groupe([PARIS, MARSEILLE])
    assert resultats[0] is not None and resultats[1] is None
    assert "issue=echec_format" in caplog.text
    assert "issue=succes_partiel" in caplog.text


def test_us182_fetch_groupe_nombre_de_reponses_incoherent() -> None:
    """CA4 / CA5 — Open-Meteo rend moins de localisations que demandé : rien n'est attribué au hasard."""
    with _patch_open_meteo(return_value=_mock_response([_reponse_open_meteo()])):
        assert fetch_meteo_groupe([PARIS, MARSEILLE]) is None


# ── CA5 — Indisponibilité ───────────────────────────────────────────────────────

def test_us182_indisponible_avec_cache_rend_l_entree_et_son_age() -> None:
    """CA5 — Gherkin « Service indisponible, cache présent »."""
    plus_tard = MAINTENANT + svc.DUREE_VALIDITE_CACHE + timedelta(minutes=30)
    with _patch_open_meteo():
        svc.lire_previsions(*PARIS, maintenant=MAINTENANT)
    with _patch_open_meteo(side_effect=req_module.RequestException("timeout")) as mock_get:
        lecture = svc.lire_previsions(*PARIS, maintenant=plus_tard)
    assert mock_get.call_count == 1
    assert lecture.disponible
    assert lecture.source == svc.SOURCE_CACHE_EXPIRE
    assert lecture.recuperee_le == MAINTENANT
    assert lecture.age_secondes == int((plus_tard - MAINTENANT).total_seconds())
    assert len(lecture.meteo["previsions_etendues"]) == 14


def test_us182_indisponible_sans_cache_ne_rend_rien(caplog) -> None:
    """CA5 — Gherkin « Service indisponible, pas de cache » : aucune prévision, échec journalisé."""
    with caplog.at_level(logging.WARNING, logger="potager"):
        with _patch_open_meteo(side_effect=req_module.RequestException("timeout")):
            lecture = svc.lire_previsions(*PARIS, maintenant=MAINTENANT)
    assert lecture.statut == svc.STATUT_INDISPONIBLE
    assert lecture.meteo is None and lecture.age_secondes is None
    assert "issue=echec_reseau" in caplog.text


def test_us182_indisponible_cache_d_hier_jamais_servi() -> None:
    """CA5 — la prévision d'hier n'est pas présentée comme celle d'aujourd'hui."""
    with _patch_open_meteo():
        svc.lire_previsions(*PARIS, maintenant=MAINTENANT)
    with _patch_open_meteo(side_effect=req_module.RequestException("down")):
        lecture = svc.lire_previsions(*PARIS, maintenant=MAINTENANT + timedelta(days=1))
    assert lecture.statut == svc.STATUT_INDISPONIBLE


def test_us182_indisponible_reponse_malformee_sans_cache() -> None:
    """CA5 — une réponse illisible vaut une indisponibilité, pas une prévision vide."""
    with _patch_open_meteo(return_value=_mock_response({"error": True})):
        lecture = svc.lire_previsions(*PARIS, maintenant=MAINTENANT)
    assert lecture.statut == svc.STATUT_INDISPONIBLE


def test_us182_indisponible_n_ecrase_pas_le_cache() -> None:
    """CA5 — un échec ne remplace pas l'entrée existante : elle reste servie avec son âge réel."""
    t1 = MAINTENANT + svc.DUREE_VALIDITE_CACHE
    t2 = t1 + timedelta(minutes=10)
    with _patch_open_meteo():
        svc.lire_previsions(*PARIS, maintenant=MAINTENANT)
    with _patch_open_meteo(side_effect=req_module.RequestException("down")):
        svc.lire_previsions(*PARIS, maintenant=t1)
        lecture = svc.lire_previsions(*PARIS, maintenant=t2)
    assert lecture.recuperee_le == MAINTENANT
    assert lecture.source == svc.SOURCE_CACHE_EXPIRE


# ── CA6 — Potager sans localisation ─────────────────────────────────────────────

@pytest.mark.parametrize("latitude, longitude", [(None, None), (48.9, None), (None, 2.2)])
def test_us182_sans_localisation_aucun_appel(latitude, longitude) -> None:
    """CA6 — Gherkin « Potager sans localisation »."""
    potager = SimpleNamespace(id=1, latitude=latitude, longitude=longitude)
    with _patch_open_meteo(side_effect=AssertionError("ne doit pas être appelé")):
        lecture = svc.lire_prevision_potager(potager, maintenant=MAINTENANT)
    assert lecture.statut == svc.STATUT_LOCALISATION_MANQUANTE
    assert lecture.statut != svc.STATUT_INDISPONIBLE
    assert not lecture.disponible and lecture.meteo is None


def test_us182_potager_absent_vaut_localisation_manquante() -> None:
    """CA6 — aucun potager résolu : pas d'appel, pas d'erreur réseau simulée."""
    with _patch_open_meteo(side_effect=AssertionError("ne doit pas être appelé")):
        lecture = svc.lire_prevision_potager(None)
    assert lecture.statut == svc.STATUT_LOCALISATION_MANQUANTE


# ── CA7 — Journalisation ────────────────────────────────────────────────────────

def test_us182_journal_appel_reussi(caplog) -> None:
    """CA7 — localisation arrondie, jour, issue et durée, au format structuré."""
    with caplog.at_level(logging.INFO, logger="potager"):
        with _patch_open_meteo():
            fetch_meteo_groupe([PARIS, MARSEILLE])
    lignes = [r for r in caplog.records if "MÉTÉO APPEL" in r.getMessage()]
    assert len(lignes) == 1
    message = lignes[0].getMessage()
    assert lignes[0].levelno == logging.INFO
    assert "loc=48.96,2.20;43.30,5.38" in message
    assert f"jour={jour_local().isoformat()}" in message
    assert "issue=succes" in message
    assert " ms " in message


def test_us182_journal_coordonnees_non_precises(caplog) -> None:
    """CA7 — les coordonnées exactes du potager n'apparaissent pas dans les journaux."""
    with caplog.at_level(logging.INFO, logger="potager"):
        with _patch_open_meteo():
            fetch_meteo(lat=48.960824, lon=2.203829)
    assert "48.960824" not in caplog.text and "2.203829" not in caplog.text
    assert "loc=48.96,2.20" in caplog.text


def test_us182_journal_echec_reseau_en_erreur(caplog) -> None:
    """CA7 — un échec est journalisé en erreur avec son motif, jamais avalé en silence."""
    with caplog.at_level(logging.INFO, logger="potager"):
        with _patch_open_meteo(side_effect=req_module.RequestException("délai dépassé")):
            assert fetch_meteo(*PARIS) is None
    erreurs = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(erreurs) == 1
    assert "issue=echec_reseau" in erreurs[0].getMessage()
    assert "délai dépassé" in erreurs[0].getMessage()


def test_us182_journal_reponse_malformee_en_erreur(caplog) -> None:
    """CA7 — une réponse illisible de `fetch_meteo` est une erreur journalisée, pas un `None` muet."""
    with caplog.at_level(logging.ERROR, logger="potager"):
        with _patch_open_meteo(return_value=_mock_response({"error": True})):
            assert fetch_meteo(*PARIS) is None
    assert "issue=echec_format" in caplog.text


def test_us182_journal_cache_expire_servi(caplog) -> None:
    """CA7 — servir une entrée expirée faute de réseau laisse une trace avec l'âge."""
    with _patch_open_meteo():
        svc.lire_previsions(*PARIS, maintenant=MAINTENANT)
    with caplog.at_level(logging.WARNING, logger="potager"):
        with _patch_open_meteo(side_effect=req_module.RequestException("down")):
            svc.lire_previsions(*PARIS, maintenant=MAINTENANT + timedelta(hours=2))
    assert "issue=cache_expire" in caplog.text
    assert "age=7200s" in caplog.text


# ── CA8 — Non-régression : GET /meteo, job 5 h, /meteo Telegram ─────────────────

@pytest.fixture
def _engine():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def app_client(_engine, monkeypatch):
    from app.api import main
    monkeypatch.setattr(main, "SessionLocal", sessionmaker(bind=_engine))
    main.app.state.limiter.reset()
    with TestClient(main.app) as c:
        yield c


def _compte_avec_potager(engine, email: str, latitude=None, longitude=None) -> dict:
    db = sessionmaker(bind=engine)()
    user = svc_auth.inscrire_utilisateur(db, email, "motdepasse123")
    svc_potagers.creer_potager(db, user.id, "Jardin", ville="Montmorency", latitude=latitude, longitude=longitude)
    headers = {"Authorization": f"Bearer {svc_auth.creer_access_token(user.id)}"}
    db.close()
    return headers


def test_us182_api_meteo_expose_quatorze_jours_et_age(app_client, _engine) -> None:
    """CA1 / CA5 / CA8 — GET /meteo garde le widget et ajoute les 14 jours et l'âge."""
    headers = _compte_avec_potager(_engine, "a@example.com", *PARIS)
    with _patch_open_meteo():
        body = app_client.get("/meteo", headers=headers).json()
    assert body["localisation_manquante"] is False
    assert body["ville"] == "Montmorency"
    assert len(body["previsions"]) == 5
    assert len(body["previsions_etendues"]) == 14
    assert body["source_donnees"] == svc.SOURCE_OPEN_METEO
    assert body["age_donnees_secondes"] == 0


def test_us182_api_meteo_deux_membres_meme_lieu_un_appel(app_client, _engine) -> None:
    """CA2 — deux comptes, deux potagers au même endroit : un seul appel Open-Meteo."""
    headers_a = _compte_avec_potager(_engine, "a@example.com", *PARIS)
    headers_b = _compte_avec_potager(_engine, "b@example.com", *PARIS)
    with _patch_open_meteo() as mock_get:
        assert app_client.get("/meteo", headers=headers_a).status_code == 200
        body = app_client.get("/meteo", headers=headers_b).json()
    assert mock_get.call_count == 1
    assert body["source_donnees"] == svc.SOURCE_CACHE


def test_us182_api_meteo_indisponible_avec_cache_200(app_client, _engine, monkeypatch) -> None:
    """CA5 / CA8 — Open-Meteo en panne mais entrée du jour en cache : le widget reste servi."""
    headers = _compte_avec_potager(_engine, "a@example.com", *PARIS)
    with _patch_open_meteo():
        app_client.get("/meteo", headers=headers)
    monkeypatch.setattr(svc, "DUREE_VALIDITE_CACHE", timedelta(0))
    with _patch_open_meteo(side_effect=req_module.RequestException("down")):
        resp = app_client.get("/meteo", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["source_donnees"] == svc.SOURCE_CACHE_EXPIRE


def test_us182_api_meteo_indisponible_sans_cache_502(app_client, _engine) -> None:
    """CA5 / CA8 — sans cache, l'erreur amont reste un 502 (comportement US-075)."""
    headers = _compte_avec_potager(_engine, "a@example.com", *PARIS)
    with _patch_open_meteo(side_effect=req_module.RequestException("down")):
        assert app_client.get("/meteo", headers=headers).status_code == 502


def test_us182_api_meteo_sans_localisation_inchange(app_client, _engine) -> None:
    """CA6 / CA8 — réponse US-075 inchangée, aucun appel."""
    headers = _compte_avec_potager(_engine, "a@example.com")
    with _patch_open_meteo(side_effect=AssertionError("ne doit pas être appelé")):
        resp = app_client.get("/meteo", headers=headers)
    assert resp.json() == {"localisation_manquante": True}


def test_us182_job_et_commande_telegram_hors_cache() -> None:
    """CA8 — `fetch_meteo()` (job 5 h, /meteo Telegram) interroge toujours Open-Meteo, sans cache."""
    with _patch_open_meteo() as mock_get:
        fetch_meteo()
        fetch_meteo()
    assert mock_get.call_count == 2
    assert svc._CACHE == {}


def test_us182_save_meteo_observation_inchangee(test_db) -> None:
    """CA8 — l'observation du job 5 h garde son commentaire et sa date."""
    from database.models import Evenement
    from utils.meteo import save_meteo_observation

    with _patch_open_meteo():
        meteo = save_meteo_observation(test_db)
    evenement = test_db.query(Evenement).filter(Evenement.texte_original == "[AUTO-METEO]").one()
    assert evenement.commentaire == format_meteo_commentaire(meteo)
    assert "previsions_etendues" not in evenement.commentaire

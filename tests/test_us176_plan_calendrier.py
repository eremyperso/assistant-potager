"""
tests/test_us176_plan_calendrier.py — Calendrier du référentiel sur l'écran Plan [US-176]
=======================================================================================

Volet serveur de l'US : `calendrier_cultural.calendriers_du_plan` et
`GET /plan/calendriers`. Le volet d'affichage (conversion des mois, mode
dégradé, rétrocompatibilité de `MonthStrip`) est couvert par
`frontend/src/lib/calendrier.test.js` (`npm test`).

Les valeurs de fenêtres et de durées sont des VALEURS DE TEST.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import calendrier_cultural as cal
from app.services import import_referentiel as svc_import
from app.services.context import TenantContext
from database.db import Base
from database.models import CultureConfig, Potager, User

RACINE = Path(__file__).resolve().parent.parent
CTX_A = TenantContext(user_id=1, potager_id=1, role="owner")


@pytest.fixture
def db(test_db):
    test_db.add_all([User(id=1, email="a@potager.test"), User(id=2, email="b@potager.test")])
    test_db.flush()
    test_db.add_all([
        Potager(id=1, nom="Jardin A", proprietaire_id=1, zone_climatique="mediterraneen"),
        Potager(id=2, nom="Jardin B", proprietaire_id=2, zone_climatique="mediterraneen"),
    ])
    test_db.commit()
    return test_db


def _source(attribution="Wind River Greens — CC BY 4.0"):
    return {"code": "wikidata", "libelle": "Source de test", "licence": "CC0",
            "attribution": attribution, "url": "https://example.org/", "partageable": True}


def _culture(db, nom):
    db.add(CultureConfig(nom=nom, type_organe_recolte="reproducteur", potager_id=None))
    db.commit()


def _importer(db, *entrees):
    return svc_import.importer(db, {"source": _source(), "cultures_calendriers": list(entrees)})


@pytest.fixture
def referentiel(db):
    for nom in ("tomate", "ail", "chou-fleur", "mache"):
        _culture(db, nom)
    _importer(
        db,
        {"culture": "tomate", "durees": {"recolte": "70-90"},
         "fenetres": {"mediterraneen": {"semis_pepiniere": "février-mars", "recolte": "juin-septembre"}}},
        {"culture": "chou-fleur", "itineraire": "culture d'hiver", "durees": {"recolte": "150-180"},
         "fenetres": {"mediterraneen": {"semis_pleine_terre": "juin-juillet"}}},
        {"culture": "mache", "fenetres": {"oceanique": {"semis_pleine_terre": "août-septembre"}}},
    )
    return db


# ── CA1 / CA3 / CA4 ──────────────────────────────────────────────────────────
def test_us176_ca1_fenetres_lues_pour_la_zone_du_potager(referentiel):
    corps = cal.calendriers_du_plan(referentiel, ["tomate"], 1)
    tomate = corps["cultures"]["tomate"]
    assert tomate["mois"]["semis_pepiniere"] == [2, 3]
    assert tomate["mois"]["recolte"] == [6, 7, 8, 9]
    assert corps["zone_climatique"] == "mediterraneen"


def test_us176_ca3_quatre_phases_du_referentiel(referentiel):
    # [CA3 amendé le 15/09/2026] La plantation est une phase du référentiel.
    tomate = cal.calendriers_du_plan(referentiel, ["tomate"], 1)["cultures"]["tomate"]
    assert set(tomate["mois"]) == set(cal.PHASES)
    assert set(cal.PHASES) == {"semis_pepiniere", "semis_pleine_terre", "plantation", "recolte"}
    # Aucune projection : ni pleine terre ni plantation ne sont déduites.
    assert tomate["mois"]["semis_pleine_terre"] == []
    assert tomate["mois"]["plantation"] == []


def test_us176_ca3_plantation_lue_jamais_reconstituee_depuis_le_repiquage(db):
    for nom in ("tomate", "aubergine"):
        _culture(db, nom)
    _importer(
        db,
        {"culture": "tomate", "fenetres": {"oceanique": {
            "semis_pepiniere": "février-mars", "plantation": "mai-juin"}}},
        {"culture": "aubergine", "durees": {"repiquage": "56-70"},
         "fenetres": {"oceanique": {"semis_pepiniere": "février-mars"}}},
    )
    cultures = cal.calendriers_du_plan(db, ["tomate", "aubergine"], None)["cultures"]
    assert cultures["tomate"]["mois"]["plantation"] == [5, 6]
    # Semis en pépinière + délai de repiquage ne font PAS une plantation (US-068 / CA18).
    assert cultures["aubergine"]["mois"]["plantation"] == []


def test_us176_ca4_duree_semis_recolte_en_forme_de_lecture(referentiel):
    corps = cal.calendriers_du_plan(referentiel, ["tomate", "ail"], 1)
    assert corps["cultures"]["tomate"]["duree_recolte"] == "70 à 90 jours"
    assert corps["cultures"]["ail"]["duree_recolte"] == cal.TIRET


def test_us176_ca3_fenetre_a_cheval_sur_l_annee(db):
    _culture(db, "epinard")
    _importer(db, {"culture": "epinard",
                   "fenetres": {"mediterraneen": {"recolte": "novembre-février"}}})
    assert cal.calendriers_du_plan(db, ["epinard"], 1)["cultures"]["epinard"]["mois"]["recolte"] == [11, 12, 1, 2]


# ── CA2 — correction locale prioritaire ──────────────────────────────────────
def test_us176_ca2_correction_au_bot_visible_et_isolee(referentiel):
    cal.corriger_fenetre(referentiel, CTX_A, "tomate", "pepiniere", "mars-avril")
    a = cal.calendriers_du_plan(referentiel, ["tomate"], 1)["cultures"]["tomate"]
    b = cal.calendriers_du_plan(referentiel, ["tomate"], 2)["cultures"]["tomate"]
    assert a["mois"]["semis_pepiniere"] == [3, 4]
    assert b["mois"]["semis_pepiniere"] == [2, 3]


def test_us176_ca2_changement_de_zone_visible(referentiel):
    cal.definir_zone(referentiel, CTX_A, "oceanique")
    corps = cal.calendriers_du_plan(referentiel, ["tomate", "mache"], 1)
    assert corps["cultures"]["tomate"]["mois"]["semis_pepiniere"] == []
    assert corps["cultures"]["mache"]["mois"]["semis_pleine_terre"] == [8, 9]


# ── CA5 — itinéraire non standard ────────────────────────────────────────────
def test_us176_ca5_itineraire_non_standard_nomme_sans_fusion(referentiel):
    chou = cal.calendriers_du_plan(referentiel, ["chou-fleur"], 1)["cultures"]["chou-fleur"]
    assert chou["itineraire"] == "culture d'hiver"
    assert chou["itineraire_standard"] is False
    tomate = cal.calendriers_du_plan(referentiel, ["tomate"], 1)["cultures"]["tomate"]
    assert tomate["itineraire_standard"] is True


# ── CA6 — trois cas du mode dégradé ──────────────────────────────────────────
@pytest.mark.parametrize("culture", ["kiwano", "ail", "mache"])
def test_us176_ca6_mode_degrade_sans_emprunt(referentiel, culture):
    """Absente du référentiel, connue sans fenêtre, renseignée pour une autre zone."""
    entree = cal.calendriers_du_plan(referentiel, [culture], 1)["cultures"][culture]
    assert all(mois == [] for mois in entree["mois"].values())
    assert entree["duree_recolte"] == cal.TIRET
    assert entree["renseigne"] is False


# ── CA8 / CA9 — zone et attribution une seule fois ───────────────────────────
def test_us176_ca8_zone_deduite_de_la_localisation(db):
    potager = db.get(Potager, 1)
    potager.zone_climatique, potager.latitude, potager.longitude = None, 48.58, 7.75  # Strasbourg
    db.commit()
    corps = cal.calendriers_du_plan(db, ["tomate"], 1)
    assert (corps["zone_climatique"], corps["zone_climatique_origine"]) == ("continental", "localisation")
    assert "déduite de la localisation" in corps["zone_libelle"]


def test_us176_ca9_attribution_rendue_une_fois(referentiel):
    corps = cal.calendriers_du_plan(referentiel, ["tomate", "chou-fleur", "ail"], 1)
    assert len(corps["attributions"]) == 1
    assert all("attributions" not in c for c in corps["cultures"].values())


def test_us176_ca9_aucune_attribution_sans_valeur_affichee(referentiel):
    assert cal.calendriers_du_plan(referentiel, ["ail", "mache"], 1)["attributions"] == []


def test_us176_ca11_doublons_et_noms_vides_ignores(referentiel):
    corps = cal.calendriers_du_plan(referentiel, ["tomate", "tomate", " ", ""], 1)
    assert list(corps["cultures"]) == ["tomate"]


# ── API ──────────────────────────────────────────────────────────────────────
@pytest.fixture
def _moteur_api():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def client_api(_moteur_api, monkeypatch):
    import main
    monkeypatch.setattr(main, "SessionLocal", sessionmaker(bind=_moteur_api))
    main.app.state.limiter.reset()
    with TestClient(main.app) as client:
        yield client


def _compte(moteur):
    from app.services import auth as svc_auth

    session = sessionmaker(bind=moteur)()
    user = svc_auth.inscrire_utilisateur(session, "jardinier@example.com", "motdepasse123")
    entete = {"Authorization": f"Bearer {svc_auth.creer_access_token(user.id)}"}
    session.close()
    return entete


def test_us176_ca11_api_lecture_groupee_en_un_appel(client_api, _moteur_api):
    entete = _compte(_moteur_api)
    client_api.post("/potagers", json={"nom": "Jardin"}, headers=entete)
    session = sessionmaker(bind=_moteur_api)()
    _culture(session, "haricot")
    _importer(session, {"culture": "haricot", "durees": {"recolte": "55-75"},
                        "fenetres": {"oceanique": {"semis_pleine_terre": "mai-juillet"}}})
    session.close()

    reponse = client_api.get("/plan/calendriers?culture=haricot&culture=ail", headers=entete)
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["cultures"]["haricot"]["mois"]["semis_pleine_terre"] == [5, 6, 7]
    assert corps["cultures"]["haricot"]["duree_recolte"] == "55 à 75 jours"
    assert corps["cultures"]["ail"]["culture_connue"] is False
    assert corps["zone_climatique_origine"] == "defaut"


def test_us176_api_sans_culture_rend_une_reponse_vide(client_api, _moteur_api):
    entete = _compte(_moteur_api)
    client_api.post("/potagers", json={"nom": "Jardin"}, headers=entete)
    corps = client_api.get("/plan/calendriers", headers=entete).json()
    assert corps["cultures"] == {} and corps["attributions"] == []


def test_us176_api_exige_une_authentification(client_api):
    assert client_api.get("/plan/calendriers?culture=tomate").status_code in (401, 403)


# ── CA13 / CA14 / CA15 — sources ─────────────────────────────────────────────
def test_us176_ca13_table_provisoire_supprimee_du_frontend():
    source = (RACINE / "frontend" / "src" / "lib" / "calendrier.js").read_text(encoding="utf-8")
    assert "const CALENDRIER" not in source
    assert "plant:" not in source
    plan = (RACINE / "frontend" / "src" / "views" / "Plan.jsx").read_text(encoding="utf-8")
    assert "calendrierDe" not in plan
    assert "calendriersPlan" in plan


def test_us176_ca14_autres_usages_de_la_frise_inchanges():
    apercu = (RACINE / "frontend" / "src" / "views" / "_DesignSystemPreview.jsx").read_text(encoding="utf-8")
    assert "<MonthStrip semis={[2, 3]} plant={[4, 5]} rec={[6, 7, 8]} legend />" in apercu
    frise = (RACINE / "frontend" / "src" / "components" / "ui" / "MonthStrip.jsx").read_text(encoding="utf-8")
    assert "semis = [], plant = [], rec = []" in frise


def test_us176_ca15_fiche_d_aide_mentionne_l_ecran_plan():
    fiche = (RACINE / "data" / "connaissance" / "doc_app" / "calendrier-et-zone-climatique.md").read_text(encoding="utf-8")
    assert "écran Plan" in fiche

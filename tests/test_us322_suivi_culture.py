"""
tests/test_us322_suivi_culture.py — [US-322] Ouvrir le suivi d'une culture depuis le plan
-----------------------------------------------------------------------------------------
Le panneau se teste côté frontend (`frontend/src/lib/suiviCulture.test.js`) et à l'écran.
Ce fichier tient la LECTURE unique qui l'alimente (CA4), `GET /plan/suivi` :

- l'origine distingue pépinière (lot n°), achat et semis direct (CA3, S9) ;
- le cumul récolté de la saison, ramené en kg (S7) ;
- les notes, les plus récentes d'abord (S10) ;
- la localisation et la ligne de place (S2, S3) ;
- l'étape courante et la frise (S4, S8), venues d'US-320 ;
- 404 pour une culture absente ou une parcelle d'un autre potager.
"""
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import auth as svc_auth
from app.services import potagers as svc_potagers
from app.services import suivi_culture as svc_suivi
from app.services.context import TenantContext
from database.db import Base
from database.models import Evenement
from utils.parcelles import create_parcelle

RACINE = Path(__file__).resolve().parent.parent


@pytest.fixture
def _engine():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def client(_engine, monkeypatch):
    from app.api import main
    monkeypatch.setattr(main, "SessionLocal", sessionmaker(bind=_engine))
    main.app.state.limiter.reset()
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def db(_engine):
    session = sessionmaker(bind=_engine)()
    yield session
    session.close()


def _potager(db, email="jardinier@example.com"):
    user = svc_auth.inscrire_utilisateur(db, email, "motdepasse123")
    potager = svc_potagers.creer_potager(db, user.id, "Potager de test")
    return user, potager


def _headers(user):
    return {"Authorization": f"Bearer {svc_auth.creer_access_token(user.id)}"}


def _ctx(user, potager):
    return TenantContext(user_id=user.id, potager_id=potager.id, role="owner")


def _geste(db, potager, **champs) -> Evenement:
    e = Evenement(potager_id=potager.id, **champs)
    db.add(e)
    db.commit()
    return e


@pytest.fixture
def chou_du_lot_18(db):
    """Gherkin 1 : le chou de Bruxelles du rang 3 vient du lot #18, en récolte depuis le
    20 octobre, 2,9 kg récoltés, trois notes."""
    user, potager = _potager(db)
    serre = create_parcelle(db, "serre", potager_id=potager.id)
    serre.est_pepiniere, serre.type_pepiniere = True, "froide"
    centrale = create_parcelle(db, "planche centrale", potager_id=potager.id)
    centrale.nb_rangs = 5
    db.commit()
    semis = _geste(db, potager, type_action="semis", culture="chou de bruxelles", quantite=30, unite="graines",
                   parcelle_id=serre.id, numero_lot=18, date=datetime(2026, 4, 2, 9))
    godet = _geste(db, potager, type_action="mise_en_godet", culture="chou de bruxelles", nb_plants_godets=14,
                   origine_graines_id=semis.id, parcelle_id=serre.id, date=datetime(2026, 5, 2, 9))
    _geste(db, potager, type_action="plantation", culture="chou de bruxelles", quantite=12, unite="plants",
           parcelle_id=centrale.id, rang_position=3, source_evenement_ids=str(godet.id),
           date=datetime(2026, 6, 10, 9))
    _geste(db, potager, type_action="recolte", culture="chou de bruxelles", quantite=2.5, unite="kg",
           parcelle_id=centrale.id, date=datetime(2026, 10, 20, 9))
    _geste(db, potager, type_action="recolte", culture="chou de bruxelles", quantite=400, unite="g",
           parcelle_id=centrale.id, date=datetime(2026, 11, 2, 9))
    for jour, texte in ((14, "chenilles retirées"), (20, "première récolte"), (28, "choux bien fermés")):
        mois = 9 if jour == 14 else 10
        _geste(db, potager, type_action="observation", culture="chou de bruxelles", commentaire=texte,
               parcelle_id=centrale.id, date=datetime(2026, mois, jour, 9))
    return user, potager, centrale


def test_us322_gherkin1_suivre_un_chou_venu_de_la_pepiniere(client, db, chou_du_lot_18):
    """[Gherkin 1, CA3, CA4] Une lecture : lot #18, en récolte, 2,9 kg, trois notes."""
    user, potager, centrale = chou_du_lot_18
    resp = client.get("/plan/suivi", params={"parcelle_id": centrale.id, "culture": "chou de bruxelles"},
                      headers=_headers(user))
    assert resp.status_code == 200, resp.text
    s = resp.json()
    assert s["origine"]["type"] == "pepiniere"
    assert s["origine"]["numero_lot"] == 18
    assert s["origine"]["date_semis"] == "2026-04-02"
    assert s["origine"]["godets"] == 14
    assert s["origine"]["plantes"] == 12
    assert s["recolte"] == {"quantite": 2.9, "unite": "kg"}
    assert [n["texte"] for n in s["notes"]] == ["choux bien fermés", "première récolte", "chenilles retirées"]
    assert all(n["dictee"] is None for n in s["notes"])
    assert s["etapes"]["etape"] == "en_recolte"
    assert s["rangs"] == [3]
    assert s["parcelle"] == "planche centrale"
    assert s["quantite"] == 12


def test_us322_s9_plantation_directe_d_un_semis_de_lot(db):
    """[S9] Une plantation rattachée directement au semis (`origine_graines_id`)."""
    user, potager = _potager(db)
    planche = create_parcelle(db, "planche", potager_id=potager.id)
    serre = create_parcelle(db, "serre", potager_id=potager.id)
    serre.est_pepiniere = True
    db.commit()
    semis = _geste(db, potager, type_action="semis", culture="tomate", quantite=20, unite="graines",
                   parcelle_id=serre.id, numero_lot=7, date=datetime(2026, 3, 1, 9))
    _geste(db, potager, type_action="plantation", culture="tomate", quantite=6, unite="plants",
           parcelle_id=planche.id, origine_graines_id=semis.id, date=datetime(2026, 5, 15, 9))
    s = svc_suivi.suivi_culture(db, _ctx(user, potager), planche.id, "tomate")
    assert s["origine"]["type"] == "pepiniere" and s["origine"]["numero_lot"] == 7
    assert s["origine"]["godets"] is None


def test_us322_s9_achat_plantation_sans_lot(db):
    """[S9] Une plantation sans lot est un achat ; le commentaire en est le texte libre."""
    user, potager = _potager(db)
    planche = create_parcelle(db, "planche", potager_id=potager.id)
    _geste(db, potager, type_action="plantation", culture="fraisier", quantite=12, unite="plants",
           parcelle_id=planche.id, commentaire="jardinerie du village", date=datetime(2026, 4, 3, 9))
    s = svc_suivi.suivi_culture(db, _ctx(user, potager), planche.id, "fraisier")
    assert s["origine"] == {"type": "achat", "texte": "jardinerie du village", "date_plantation": "2026-04-03"}
    assert s["recolte"] is None
    assert s["notes"] == []


def test_us322_s9_semis_direct(db):
    """[S9] Un semis en place : « semé en place le … »."""
    user, potager = _potager(db)
    planche = create_parcelle(db, "planche", potager_id=potager.id)
    _geste(db, potager, type_action="semis", culture="radis", quantite=2, unite="m",
           parcelle_id=planche.id, contexte_semis="pleine_terre", date=datetime(2026, 10, 1, 9))
    s = svc_suivi.suivi_culture(db, _ctx(user, potager), planche.id, "radis")
    assert s["origine"] == {"type": "semis_direct", "date": "2026-10-01"}


def test_us322_s7_recolte_en_unites_non_ponderales(db):
    """[S7] Des pièces se cumulent en pièces ; une autre variété ne compte pas."""
    user, potager = _potager(db)
    planche = create_parcelle(db, "planche", potager_id=potager.id)
    for variete in ("batavia", "feuille de chêne"):
        _geste(db, potager, type_action="plantation", culture="salade", variete=variete, quantite=10,
               unite="plants", parcelle_id=planche.id, date=datetime(2026, 9, 1, 9))
    for q in (3, 2):
        _geste(db, potager, type_action="recolte", culture="salade", variete="batavia", quantite=q,
               unite="pièces", parcelle_id=planche.id, date=datetime(2026, 10, q, 9))
    _geste(db, potager, type_action="recolte", culture="salade", variete="feuille de chêne", quantite=4,
           unite="pièces", parcelle_id=planche.id, date=datetime(2026, 10, 9, 9))
    s = svc_suivi.suivi_culture(db, _ctx(user, potager), planche.id, "salade", "batavia")
    assert s["recolte"] == {"quantite": 5.0, "unite": "pièces"}


def test_us322_ca4_culture_absente_ou_autre_potager_404(client, db, chou_du_lot_18):
    """[CA4] Une culture qui n'est pas en place, ou la parcelle d'un autre potager : 404."""
    user, potager, centrale = chou_du_lot_18
    absente = client.get("/plan/suivi", params={"parcelle_id": centrale.id, "culture": "courgette"},
                         headers=_headers(user))
    assert absente.status_code == 404
    voisin, _ = _potager(db, "voisin@example.com")
    ailleurs = client.get("/plan/suivi", params={"parcelle_id": centrale.id, "culture": "chou de bruxelles"},
                          headers=_headers(voisin))
    assert ailleurs.status_code == 404


def test_us322_ca4_parametres_obligatoires(client, db):
    """[CA4] Sans parcelle ni culture, la lecture est refusée (422), rien n'est deviné."""
    user, _ = _potager(db)
    assert client.get("/plan/suivi", headers=_headers(user)).status_code == 422


# ── S3 : la ligne de place ───────────────────────────────────────────────────

def test_us322_s3_place_sur_le_rang():
    """[S3] Pieds, mètres occupés sur la longueur, espacement, mètres libres."""
    place = svc_suivi._place_sur_le_rang(
        [{"places": 20, "places_prises": 12, "depassement_places": 0, "espacement_rang_cm": 30, "part_m": None}], 6.0)
    assert place == {"pieds": 12, "places": 20, "espacement_cm": 30, "longueur_m": 6.0,
                     "metres_occupes": 3.6, "metres_libres": 2.4, "depassement_pieds": 0}


def test_us322_s3_depassement_et_part_d_un_rang_partage():
    """[S3, US-326] Sur un rang partagé, la longueur est la part ; un dépassement est dit."""
    place = svc_suivi._place_sur_le_rang(
        [{"places": 5, "places_prises": 5, "depassement_places": 3, "espacement_rang_cm": 40, "part_m": 2.0}], 6.0)
    assert place["longueur_m"] == 2.0
    assert place["pieds"] == 8
    assert place["depassement_pieds"] == 3
    assert place["metres_libres"] == 0.0


def test_us322_s3_place_non_calculable():
    """[S3] Sans places calculables (pas de longueur, pas d'espacement), le bloc est absent."""
    assert svc_suivi._place_sur_le_rang([{"places": None}], 6.0) is None
    assert svc_suivi._place_sur_le_rang([], None) is None


def test_us322_ca4_une_seule_lecture_cote_ecran():
    """[CA4] Le composant du suivi ne fait qu'UNE lecture : `api.suiviCulture`."""
    src = (RACINE / "frontend/src/components/SuiviCulture.jsx").read_text(encoding="utf-8")
    import re
    assert set(re.findall(r"api\.(\w+)\(", src)) == {"suiviCulture"}


def test_us322_ca8_la_fiche_decrit_le_suivi():
    """[CA8] La fiche `parcelles-et-plan.md` décrit le suivi d'une culture."""
    fiche = (RACINE / "data/connaissance/doc_app/parcelles-et-plan.md").read_text(encoding="utf-8")
    assert "## Suivre une culture depuis le plan" in fiche
    for mot in ("origine", "Voir le lot", "récoltés", "Noter"):
        assert mot.lower() in fiche.lower(), mot

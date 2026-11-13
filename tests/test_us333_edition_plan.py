"""
tests/test_us333_edition_plan.py — [US-333] Modifier le plan sur ordinateur : poser, dimensionner, orienter
===========================================================================================================
Côté serveur : « Enregistrer » écrit en UN seul appel la géométrie de toutes les parcelles modifiées et
l'orientation du potager (CA3) ; un refus n'écrit rien, nomme la parcelle et le champ ; réduire les rangs
sous les rangs occupés est refusé (E6) ; la fiche ne s'aligne jamais seule (CA4) ; réservé à un éditeur (CA7).
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import auth as svc_auth
from app.services import potagers as svc_potagers
from database.db import Base
from database.models import Evenement, Parcelle, Potager
from utils.parcelles import create_parcelle


@pytest.fixture
def _engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
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


def _plan(db):
    user = svc_auth.inscrire_utilisateur(db, "jardinier@example.com", "motdepasse123")
    potager = svc_potagers.creer_potager(db, user.id, "Potager de test")
    centrale = create_parcelle(db, "centrale", superficie_m2=69.0, potager_id=potager.id)
    centrale.longueur_m, centrale.largeur_m, centrale.nb_rangs, centrale.x_m, centrale.y_m = 12.0, 5.0, 8, 2.0, 2.0
    haricots = create_parcelle(db, "haricots", superficie_m2=20.0, potager_id=potager.id)
    db.commit()
    return user, potager, centrale, haricots


def _post(client, user, corps):
    return client.post("/plan/edition", json=corps,
                       headers={"Authorization": f"Bearer {svc_auth.creer_access_token(user.id)}"})


def test_ca3_enregistrer_ecrit_tout_en_un_appel(client, db):
    user, potager, centrale, haricots = _plan(db)
    r = _post(client, user, {
        "parcelles": [
            {"id": haricots.id, "x_m": 2.5, "y_m": 9.0, "longueur_m": 10, "largeur_m": 2, "rotation_deg": 0,
             "sens_rangs": "longueur", "forme": "planche"},
            {"id": centrale.id, "x_m": 3.0, "y_m": 2.0},
        ],
        "potager": {"orientation_nord": "ne", "angle_deg": -2.5},
    })
    assert r.status_code == 200, r.text
    assert r.json()["parcelles"] == 2
    db.expire_all()
    h = db.get(Parcelle, haricots.id)
    assert (h.x_m, h.y_m, h.longueur_m, h.largeur_m, h.sens_rangs) == (2.5, 9.0, 10.0, 2.0, "longueur")
    assert db.get(Parcelle, centrale.id).x_m == 3.0
    p = db.get(Potager, potager.id)
    assert (p.orientation_nord, p.angle_deg) == ("ne", 357.5)


def test_ca3_un_refus_n_ecrit_rien_et_nomme_la_parcelle_et_le_champ(client, db):
    user, potager, centrale, haricots = _plan(db)
    r = _post(client, user, {"parcelles": [
        {"id": centrale.id, "x_m": 9.0, "y_m": 9.0},
        {"id": haricots.id, "x_m": 1.0, "y_m": 1.0, "sens_rangs": "diagonale"},
    ]})
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["parcelle"] == "haricots" and detail["champ"] == "sens_rangs"
    db.expire_all()
    assert db.get(Parcelle, centrale.id).x_m == 2.0          # la première n'a pas été écrite


def test_e6_reduire_les_rangs_sous_les_rangs_occupes_est_refuse(client, db):
    user, potager, centrale, _ = _plan(db)
    for rang in (1, 2, 3):
        db.add(Evenement(type_action="plantation", culture=f"c{rang}", quantite=4, unite="plants",
                         parcelle_id=centrale.id, potager_id=potager.id, rang_position=rang))
    db.commit()
    r = _post(client, user, {"parcelles": [{"id": centrale.id, "nb_rangs": 2}]})
    assert r.status_code == 400
    assert r.json()["detail"]["champ"] == "nb_rangs" and "occupé" in r.json()["detail"]["message"]
    assert _post(client, user, {"parcelles": [{"id": centrale.id, "nb_rangs": 4}]}).status_code == 200


def test_ca4_la_fiche_ne_s_aligne_jamais_seule(client, db):
    user, potager, centrale, _ = _plan(db)           # fiche 69 m², posée 60 m²
    r = _post(client, user, {"parcelles": [{"id": centrale.id, "x_m": 3.0, "y_m": 3.0}]})
    assert r.status_code == 200
    db.expire_all()
    assert db.get(Parcelle, centrale.id).superficie_m2 == 69.0
    r = _post(client, user, {"parcelles": [{"id": centrale.id, "aligner_superficie": True}]})
    db.expire_all()
    assert db.get(Parcelle, centrale.id).superficie_m2 == 60.0


def test_ca7_un_lecteur_n_enregistre_pas(client, db):
    from app.services.permissions import NIVEAUX_ROLE  # noqa: F401  (le rôle lecteur existe)
    user, potager, centrale, _ = _plan(db)
    lecteur = svc_auth.inscrire_utilisateur(db, "lecteur@example.com", "motdepasse123")
    from database.models import PotagerMembre
    db.add(PotagerMembre(potager_id=potager.id, user_id=lecteur.id, role="lecteur"))
    lecteur.potager_actif_id = potager.id
    db.commit()
    r = _post(client, lecteur, {"parcelles": [{"id": centrale.id, "x_m": 5.0, "y_m": 5.0}]})
    assert r.status_code in (403, 409)
    db.expire_all()
    assert db.get(Parcelle, centrale.id).x_m == 2.0


def test_e4_retirer_du_plan_efface_la_position_pas_la_parcelle(client, db):
    user, potager, centrale, _ = _plan(db)
    r = _post(client, user, {"parcelles": [{"id": centrale.id, "x_m": None, "y_m": None}]})
    assert r.status_code == 200
    db.expire_all()
    c = db.get(Parcelle, centrale.id)
    assert (c.x_m, c.y_m, c.actif) == (None, None, True)


def test_une_parcelle_d_un_autre_potager_est_introuvable(client, db):
    user, potager, centrale, _ = _plan(db)
    etranger = svc_auth.inscrire_utilisateur(db, "autre@example.com", "motdepasse123")
    svc_potagers.creer_potager(db, etranger.id, "Autre")
    assert _post(client, etranger, {"parcelles": [{"id": centrale.id, "x_m": 1.0, "y_m": 1.0}]}).status_code == 404

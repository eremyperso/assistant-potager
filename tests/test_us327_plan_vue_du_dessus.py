"""
tests/test_us327_plan_vue_du_dessus.py — [US-327] Le plan du potager vu du dessus
---------------------------------------------------------------------------------
Le rendu se teste côté frontend (`frontend/src/lib/planDessus.test.js`, `npm test`) et
à l'écran (chrome-devtools). Ce fichier tient ce que le SERVEUR doit au plan, puisque
CA1 impose que tout sorte de la seule lecture de `GET /plan` :

- les lots en cours d'une pépinière, que le plan dessine en vignettes (P6) ;
- les parcelles inactives, servies à part pour rester sur le plan, grisées (P7) ;
- les compteurs des filtres, calculés par le service et jamais par l'écran (CA4) ;
- la fiche du corpus « Lire le plan » (CA9).
"""
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import auth as svc_auth
from app.services import plan as svc_plan
from app.services import potagers as svc_potagers
from app.services.context import TenantContext
from app.services.repartition_rangs import repartition_du_plan
from database.db import Base
from database.models import Evenement
from utils.parcelles import calcul_occupation_parcelles, create_parcelle

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


def _parcelle(db, potager, nom, *, pepiniere=None, nb_rangs=None, actif=True, x=None, y=None):
    p = create_parcelle(db, nom, potager_id=potager.id)
    p.nb_rangs = nb_rangs
    p.est_pepiniere = pepiniere is not None
    p.type_pepiniere = pepiniere
    p.actif = actif
    p.x_m, p.y_m, p.longueur_m, p.largeur_m = x, y, (4.0 if x is not None else None), (1.2 if x is not None else None)
    db.commit()
    return p


def _semis(db, potager, parcelle, culture, numero, jour=2):
    db.add(Evenement(
        type_action="semis", culture=culture, quantite=40, unite="graines",
        parcelle_id=parcelle.id, potager_id=potager.id, numero_lot=numero,
        date=datetime(2026, 10, jour, 9), texte_original=f"semé {culture}",
    ))
    db.commit()


# ── P6 : les lots d'une pépinière ────────────────────────────────────────────

def test_us327_p6_la_pepiniere_porte_ses_lots_en_cours(client, db):
    """[P6] La disposition d'une pépinière liste ses lots : numéro, culture, variété."""
    user, potager = _potager(db)
    serre = _parcelle(db, potager, "serre", pepiniere="chaude")
    _semis(db, potager, serre, "tomate", 18)
    _semis(db, potager, serre, "poivron", 19, jour=3)

    resp = client.get("/plan", headers=_headers(user))
    assert resp.status_code == 200, resp.text
    d = {p["nom"]: p for p in resp.json()["parcelles"]}["serre"]["disposition"]
    assert d["nb_lots_en_cours"] == 2
    assert {(l["numero_lot"], l["culture"]) for l in d["lots_en_cours"]} == {(18, "tomate"), (19, "poivron")}
    assert all(l["lot_id"] for l in d["lots_en_cours"])


def test_us327_p6_une_parcelle_ordinaire_n_a_aucun_lot(db):
    """[P6] Hors pépinière, ni compte ni liste : None, comme avant (R8)."""
    user, potager = _potager(db)
    planche = _parcelle(db, potager, "planche", nb_rangs=3)
    occupation = calcul_occupation_parcelles(db, None, potager_id=potager.id)
    d = repartition_du_plan(db, [planche], occupation, potager.id)["dispositions"]["planche"]
    assert d["nb_lots_en_cours"] is None
    assert d["lots_en_cours"] is None


def test_us327_p6_un_compte_seul_reste_accepte(db, monkeypatch):
    """[R8] Compatibilité : un compte (ancien contrat) donne le nombre, sans liste."""
    from app.services import repartition_rangs
    user, potager = _potager(db)
    serre = _parcelle(db, potager, "serre", pepiniere="froide")
    monkeypatch.setattr(repartition_rangs, "_lots_en_cours_par_parcelle", lambda *a: {"serre": 3})
    occupation = calcul_occupation_parcelles(db, None, potager_id=potager.id)
    d = repartition_du_plan(db, [serre], occupation, potager.id)["dispositions"]["serre"]
    assert d["nb_lots_en_cours"] == 3
    assert d["lots_en_cours"] == []


# ── P7 : les parcelles inactives ─────────────────────────────────────────────

def test_us327_p7_une_parcelle_inactive_est_servie_a_part_avec_sa_geometrie(client, db):
    """[P7] Inactive : hors de `parcelles` (contrat inchangé), dans `parcelles_inactives`."""
    user, potager = _potager(db)
    _parcelle(db, potager, "planche centrale", x=9.0, y=1.0)
    _parcelle(db, potager, "planche haricots", actif=False, x=19.0, y=11.0)

    corps = client.get("/plan", headers=_headers(user)).json()
    assert [p["nom"] for p in corps["parcelles"]] == ["planche centrale"]
    [inactive] = corps["parcelles_inactives"]
    assert inactive["nom"] == "planche haricots"
    assert inactive["actif"] is False
    assert inactive["geometrie"]["placee"] is True
    assert (inactive["geometrie"]["x_m"], inactive["geometrie"]["y_m"]) == (19.0, 11.0)


def test_us327_p7_les_inactives_d_un_autre_potager_ne_fuient_pas(db):
    """[P7] Le service ne sert que le potager du contexte."""
    user, potager = _potager(db)
    autre_user, autre = _potager(db, "voisin@example.com")
    _parcelle(db, autre, "chez le voisin", actif=False)
    _parcelle(db, potager, "au repos", actif=False)
    noms = [p["nom"] for p in svc_plan.parcelles_inactives(db, _ctx(user, potager))]
    assert noms == ["au repos"]


# ── CA4 : les compteurs des filtres ──────────────────────────────────────────

def _ligne(etape, a_confirmer=False):
    return {"etapes": {"etape": etape, "a_confirmer": a_confirmer}}


def test_us327_ca4_compteurs_des_filtres():
    """[CA4] À confirmer, en récolte, rangs libres — les pépinières ne comptent pas."""
    parcelles = [
        {"est_pepiniere": False, "cultures": [_ligne("levee", True), _ligne("en_recolte"), _ligne("en_recolte", True)],
         "disposition": {"rangs_libres": 2}},
        {"est_pepiniere": False, "cultures": [{"etapes": None}], "disposition": {"rangs_libres": None}},
        {"est_pepiniere": True, "cultures": [_ligne("levee", True)], "disposition": {"rangs_libres": 4}},
    ]
    assert svc_plan.compteurs_filtres(parcelles) == {"a_confirmer": 2, "en_recolte": 2, "rangs_libres": 2}
    assert svc_plan.compteurs_filtres([]) == {"a_confirmer": 0, "en_recolte": 0, "rangs_libres": 0}


def test_us327_ca4_get_plan_sert_les_compteurs(client, db):
    """[CA4] `GET /plan` sert `filtres_plan` ; les rangs libres sont ceux déclarés et vides."""
    user, potager = _potager(db)
    planche = _parcelle(db, potager, "planche", nb_rangs=4, x=0.0, y=0.0)
    db.add(Evenement(type_action="plantation", culture="poireau", quantite=20, unite="plants",
                     parcelle_id=planche.id, potager_id=potager.id, date=datetime(2026, 9, 1, 9)))
    db.commit()
    corps = client.get("/plan", headers=_headers(user)).json()
    assert corps["filtres_plan"]["rangs_libres"] == 3
    assert set(corps["filtres_plan"]) == {"a_confirmer", "en_recolte", "rangs_libres"}


# ── CA9 : la fiche du corpus ─────────────────────────────────────────────────

def test_us327_ca9_la_fiche_dit_comment_lire_le_plan():
    """[CA9] La fiche `parcelles-et-plan.md` décrit le plan vu du dessus (« Lire le plan »)."""
    fiche = (RACINE / "data/connaissance/doc_app/parcelles-et-plan.md").read_text(encoding="utf-8")
    assert "## Lire le plan" in fiche
    for mot in ("vu du dessus", "À confirmer", "Rangs libres", "à placer", "rose des vents", "grisée"):
        assert mot.lower() in fiche.lower(), mot


def test_us327_ca9_le_guide_utilisateur_annonce_le_plan():
    """[CA9] Les deux copies du guide utilisateur ne disent plus « Vue plan à l'échelle … à venir »."""
    for chemin in ("docs/MANUEL/guide assistant.md", "data/connaissance/guide user/guide assistant.md"):
        guide = (RACINE / chemin).read_text(encoding="utf-8")
        assert "Vue plan à l'échelle et Rotation" not in guide, chemin
        assert "vu du dessus" in guide, chemin

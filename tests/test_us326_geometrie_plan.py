"""
tests/test_us326_geometrie_plan.py — [US-326] Géométrie du potager, des parcelles
et position des rangs
------------------------------------------------------------------------------
Ce que ce fichier tient :

- la migration v76 : colonnes nullables, sans backfill, rollback fourni (CA1) ;
- la géométrie d'une parcelle passe par `PATCH /parcelles/{id}`, réservé à un
  éditeur, et la superficie suit G1 / G2 (CA2, Gherkin 1) ;
- `GET /plan` expose géométrie, rangs et parts ; une parcelle non placée est « à
  placer », sans coordonnées (CA3, G6, Gherkin 3) ;
- sans aucune position, la répartition d'US-198 est inchangée (CA4) ;
- « au rang 3 » est une POSITION, lue par le parseur et écrite (CA5) ; sans rang dit,
  la culture prend le premier bloc libre (G5) ;
- un rang ne se partage que si la parcelle a une longueur (P4, Gherkin 2).
"""
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import auth as svc_auth
from app.services import geometrie as svc_geometrie
from app.services import potagers as svc_potagers
from app.services.context import TenantContext
from app.services.evenements import PositionRangRefuseeError, creer_evenement_confirme
from app.services.repartition_rangs import (
    NUMEROTATION_MIXTE, NUMEROTATION_ORDRE_INSTALLATION, NUMEROTATION_POSITIONS,
    SOURCE_INSTALLATION, SOURCE_JARDINIER, repartition_du_plan,
)
from database.db import Base
from database.models import CultureConfig, Evenement, Parcelle, Potager, PotagerMembre
from llm.parseur_deterministe import parser_saisie
from utils.parcelles import calcul_occupation_parcelles, create_parcelle

RACINE = Path(__file__).resolve().parent.parent


# ── Fixtures ─────────────────────────────────────────────────────────────────

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


def _planche(db, potager, nom="planche centrale", *, nb_rangs=5, longueur=None, superficie=None):
    parcelle = create_parcelle(db, nom, superficie_m2=superficie, potager_id=potager.id)
    parcelle.nb_rangs = nb_rangs
    parcelle.longueur_m = longueur
    db.commit()
    return parcelle


def _headers(user):
    return {"Authorization": f"Bearer {svc_auth.creer_access_token(user.id)}"}


def _ctx(user, potager):
    return TenantContext(user_id=user.id, potager_id=potager.id, role="owner")


def _plante(db, potager, parcelle, culture, quantite, jour, *, position=None, rangs=None,
            longueur_rang=None, variete=None):
    db.add(Evenement(
        type_action="plantation", culture=culture, variete=variete, quantite=quantite,
        unite="plants", parcelle_id=parcelle.id, potager_id=potager.id,
        date=datetime(2026, 4, jour, 9), rang=rangs, rang_position=position,
        rang_longueur_m=longueur_rang, texte_original=f"planté {culture}",
    ))
    db.commit()


def _disposition(db, potager, parcelle):
    occupation = calcul_occupation_parcelles(db, None, potager_id=potager.id)
    return repartition_du_plan(db, [parcelle], occupation, potager.id)["dispositions"][parcelle.nom]


def _occupes(disposition):
    return [(r["numero"], r["culture"]) for r in disposition["rangs"] if not r["libre"]]


# ── CA1 : la migration ───────────────────────────────────────────────────────

def test_us326_ca1_migration_v76_nullable_sans_backfill():
    sql = (RACINE / "migrations" / "migration_v76.sql").read_text(encoding="utf-8")
    for colonne in ("emprise_longueur_m", "emprise_largeur_m", "angle_deg", "orientation_nord",
                    "forme", "x_m", "y_m", "largeur_m", "rotation_deg", "sens_rangs",
                    "rang_position", "rang_longueur_m"):
        assert f"ADD COLUMN IF NOT EXISTS {colonne}" in sql, colonne
    assert "NOT NULL" not in sql.split("BEGIN;")[1].replace("IS NOT NULL", "")
    assert "UPDATE " not in sql, "aucun backfill de position"


def test_us326_ca1_rollback_v76_retire_tout():
    sql = (RACINE / "migrations" / "rollback_v76.sql").read_text(encoding="utf-8")
    for colonne in ("orientation_nord", "forme", "x_m", "sens_rangs", "rang_position", "rang_longueur_m"):
        assert f"DROP COLUMN IF EXISTS {colonne}" in sql, colonne


def test_us326_ca1_colonnes_orm_nullables():
    for table, colonnes in (
        (Potager, ("emprise_longueur_m", "emprise_largeur_m", "angle_deg", "orientation_nord")),
        (Parcelle, ("forme", "x_m", "y_m", "largeur_m", "rotation_deg", "sens_rangs")),
        (Evenement, ("rang_position", "rang_longueur_m")),
    ):
        for nom in colonnes:
            assert table.__table__.columns[nom].nullable, nom


# ── CA2, G1, G2 : poser la géométrie d'une planche ───────────────────────────

def test_us326_gherkin1_poser_une_planche_garde_la_superficie_declaree(client, db):
    """12 × 5 m, rangs dans la longueur : 60 m² posés, 69 m² gardés et signalés."""
    user, potager = _potager(db)
    parcelle = _planche(db, potager, superficie=69.0)

    resp = client.patch(f"/parcelles/{parcelle.id}", headers=_headers(user), json={
        "longueur_m": 12, "largeur_m": 5, "sens_rangs": "longueur",
    })

    assert resp.status_code == 200, resp.text
    corps = resp.json()
    assert corps["longueur_m"] == 12.0
    assert corps["largeur_m"] == 5.0
    assert corps["geometrie"]["superficie_posee_m2"] == 60.0
    assert corps["superficie_m2"] == 69.0          # G2 : la fiche n'est pas écrasée
    assert corps["geometrie"]["ecart_superficie"] == {"posee_m2": 60.0, "fiche_m2": 69.0}
    assert corps["geometrie"]["sens_rangs"] == "longueur"


def test_us326_g2_aligner_la_fiche_puis_elle_suit_la_geometrie(client, db):
    user, potager = _potager(db)
    parcelle = _planche(db, potager, superficie=69.0)
    client.patch(f"/parcelles/{parcelle.id}", headers=_headers(user),
                 json={"longueur_m": 12, "largeur_m": 5})

    resp = client.patch(f"/parcelles/{parcelle.id}", headers=_headers(user),
                        json={"aligner_superficie": True})
    assert resp.json()["superficie_m2"] == 60.0
    assert resp.json()["geometrie"]["ecart_superficie"] is None

    # Alignée, la fiche suit désormais chaque changement de géométrie (G1).
    resp = client.patch(f"/parcelles/{parcelle.id}", headers=_headers(user), json={"largeur_m": 4})
    assert resp.json()["superficie_m2"] == 48.0


def test_us326_g1_superficie_deduite_quand_la_fiche_est_vide(client, db):
    user, potager = _potager(db)
    parcelle = _planche(db, potager)
    resp = client.patch(f"/parcelles/{parcelle.id}", headers=_headers(user),
                        json={"longueur_m": 10, "largeur_m": 1.2})
    assert resp.json()["superficie_m2"] == 12.0
    assert resp.json()["geometrie"]["ecart_superficie"] is None


def test_us326_g2_une_superficie_dite_l_emporte(client, db):
    user, potager = _potager(db)
    parcelle = _planche(db, potager)
    resp = client.patch(f"/parcelles/{parcelle.id}", headers=_headers(user),
                        json={"longueur_m": 10, "largeur_m": 1.2, "superficie_m2": 11})
    assert resp.json()["superficie_m2"] == 11.0
    assert resp.json()["geometrie"]["ecart_superficie"] == {"posee_m2": 12.0, "fiche_m2": 11.0}


def test_us326_ca2_position_forme_rotation(client, db):
    user, potager = _potager(db)
    parcelle = _planche(db, potager)
    resp = client.patch(f"/parcelles/{parcelle.id}", headers=_headers(user), json={
        "forme": "Butte", "x_m": 3.5, "y_m": 7, "rotation_deg": 370, "sens_rangs": "en travers",
    })
    assert resp.status_code == 200, resp.text
    geo = resp.json()["geometrie"]
    assert geo["forme"] == "butte"
    assert (geo["x_m"], geo["y_m"], geo["placee"]) == (3.5, 7.0, True)
    assert geo["rotation_deg"] == 10.0          # 370° = 10°
    assert geo["sens_rangs"] == "travers"


@pytest.mark.parametrize("champs,champ_fautif", [
    ({"forme": "igloo"}, "forme"),
    ({"x_m": 3}, "x_m"),                       # x sans y : ni placée, ni à placer
    ({"largeur_m": 0}, "largeur_m"),
    ({"sens_rangs": "diagonale"}, "sens_rangs"),
])
def test_us326_ca2_valeur_refusee_nomme_le_champ(client, db, champs, champ_fautif):
    user, potager = _potager(db)
    parcelle = _planche(db, potager)
    resp = client.patch(f"/parcelles/{parcelle.id}", headers=_headers(user), json=champs)
    assert resp.status_code == 400
    assert resp.json()["detail"]["champ"] == champ_fautif


def test_us326_ca2_rien_n_est_ecrit_a_moitie(client, db):
    user, potager = _potager(db)
    parcelle = _planche(db, potager)
    resp = client.patch(f"/parcelles/{parcelle.id}", headers=_headers(user),
                        json={"forme": "bac", "sens_rangs": "diagonale"})
    assert resp.status_code == 400
    db.refresh(parcelle)
    assert parcelle.forme is None


def test_us326_ca2_reserve_a_un_editeur(client, db):
    owner, potager = _potager(db)
    parcelle = _planche(db, potager)
    lecteur = svc_auth.inscrire_utilisateur(db, "lecteur@example.com", "motdepasse123")
    db.add(PotagerMembre(user_id=lecteur.id, potager_id=potager.id, role="lecteur"))
    lecteur.potager_actif_id = potager.id
    db.commit()
    resp = client.patch(f"/parcelles/{parcelle.id}", headers=_headers(lecteur),
                        json={"x_m": 1, "y_m": 1})
    assert resp.status_code in (403, 404)
    db.refresh(parcelle)
    assert parcelle.x_m is None


# ── CA3, G6 : GET /plan ──────────────────────────────────────────────────────

def test_us326_gherkin3_parcelle_non_placee_listee_a_placer_sans_coordonnees(client, db):
    user, potager = _potager(db)
    _planche(db, potager, "planche haricots")
    placee = _planche(db, potager, "planche centrale")
    placee.x_m, placee.y_m, placee.largeur_m, placee.longueur_m = 2.0, 4.0, 1.2, 10.0
    db.commit()

    resp = client.get("/plan", headers=_headers(user))
    assert resp.status_code == 200, resp.text
    par_nom = {p["nom"]: p for p in resp.json()["parcelles"]}
    haricots = par_nom["planche haricots"]["geometrie"]
    assert haricots["a_placer"] is True
    assert haricots["x_m"] is None and haricots["y_m"] is None
    centrale = par_nom["planche centrale"]
    assert centrale["geometrie"]["placee"] is True
    assert (centrale["geometrie"]["x_m"], centrale["geometrie"]["y_m"]) == (2.0, 4.0)
    # G1 : une largeur posée n'est plus « déduite ».
    assert centrale["largeur_m"] == 1.2 and centrale["largeur_deduite"] is False


def test_us326_geometrie_du_potager_ecrite_et_lue(client, db):
    user, potager = _potager(db)
    resp = client.patch("/plan/geometrie", headers=_headers(user), json={
        "emprise_longueur_m": 30, "emprise_largeur_m": 18, "angle_deg": -15,
        "orientation_nord": "nord-est",
    })
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"emprise_longueur_m": 30.0, "emprise_largeur_m": 18.0,
                           "angle_deg": 345.0, "orientation_nord": "ne"}
    plan = client.get("/plan", headers=_headers(user)).json()
    assert plan["potager_geometrie"]["orientation_nord"] == "ne"
    assert "butte" in plan["potager_geometrie"]["vocabulaires"]["formes"]


def test_us326_geometrie_du_potager_refuse_une_orientation_inconnue(client, db):
    user, _ = _potager(db)
    resp = client.patch("/plan/geometrie", headers=_headers(user), json={"orientation_nord": "haut"})
    assert resp.status_code == 400
    assert resp.json()["detail"]["champ"] == "orientation_nord"


# ── CA4 : sans géométrie, rien ne change ─────────────────────────────────────

def test_us326_ca4_sans_position_numerotation_d_installation_inchangee(db):
    _, potager = _potager(db)
    parcelle = _planche(db, potager)
    _plante(db, potager, parcelle, "tomate", 8, 1)
    _plante(db, potager, parcelle, "salade", 12, 2, rangs=2)
    _plante(db, potager, parcelle, "poireau", 30, 3)

    d = _disposition(db, potager, parcelle)

    assert d["mode_numerotation"] == NUMEROTATION_ORDRE_INSTALLATION
    assert _occupes(d) == [(1, "tomate"), (2, "salade"), (3, "salade"), (4, "poireau")]
    assert [r["numero"] for r in d["rangs"] if r["libre"]] == [5]
    assert (d["rangs_occupes"], d["rangs_libres"], d["depassement"]) == (4, 1, 0)
    assert all(r["position_source"] == SOURCE_INSTALLATION for r in d["rangs"] if not r["libre"])
    # « 12 salades sur 2 rangs » : la quantité est PAR rang (US-198).
    assert [r["quantite_par_rang"] for r in d["rangs"] if r["culture"] == "salade"] == [12, 12]


def test_us326_ca4_une_position_ne_change_aucune_quantite(db):
    _, potager = _potager(db)
    parcelle = _planche(db, potager)
    _plante(db, potager, parcelle, "tomate", 8, 1)
    _plante(db, potager, parcelle, "salade", 12, 2, rangs=2)
    avant = calcul_occupation_parcelles(db, None, potager_id=potager.id)
    quantites_avant = sorted(r["quantite_par_rang"] for r in _disposition(db, potager, parcelle)["rangs"]
                             if not r["libre"])

    db.query(Evenement).filter(Evenement.culture == "tomate").update({"rang_position": 4})
    db.commit()

    assert calcul_occupation_parcelles(db, None, potager_id=potager.id) == avant
    quantites = sorted(r["quantite_par_rang"] for r in _disposition(db, potager, parcelle)["rangs"]
                       if not r["libre"])
    assert quantites == quantites_avant


# ── CA5, G3, G5 : la position d'un rang ──────────────────────────────────────

def test_us326_ca5_une_position_dite_pose_la_culture_sur_ce_rang(db):
    _, potager = _potager(db)
    parcelle = _planche(db, potager)
    _plante(db, potager, parcelle, "tomate", 8, 1, position=3)

    d = _disposition(db, potager, parcelle)

    assert d["mode_numerotation"] == NUMEROTATION_POSITIONS
    assert _occupes(d) == [(3, "tomate")]
    assert [r["numero"] for r in d["rangs"] if r["libre"]] == [1, 2, 4, 5]
    assert d["rangs_libres"] == 4
    tomate = next(r for r in d["rangs"] if r["culture"] == "tomate")
    assert tomate["position_source"] == SOURCE_JARDINIER


def test_us326_g3_g5_sans_rang_dit_la_culture_prend_le_premier_bloc_libre(db):
    """« 4 salades sur 3 rangs » : trois rangs consécutifs à partir du premier libre."""
    _, potager = _potager(db)
    parcelle = _planche(db, potager, nb_rangs=6)
    _plante(db, potager, parcelle, "tomate", 8, 1, position=2)
    _plante(db, potager, parcelle, "salade", 4, 2, rangs=3)
    _plante(db, potager, parcelle, "poireau", 20, 3)

    d = _disposition(db, potager, parcelle)

    assert d["mode_numerotation"] == NUMEROTATION_MIXTE
    assert _occupes(d) == [(1, "poireau"), (2, "tomate"), (3, "salade"), (4, "salade"), (5, "salade")]
    sources = {r["culture"]: r["position_source"] for r in d["rangs"] if not r["libre"]}
    assert sources == {"tomate": SOURCE_JARDINIER, "salade": SOURCE_INSTALLATION,
                       "poireau": SOURCE_INSTALLATION}


def test_us326_ca5_parseur_lit_au_rang_3_comme_une_position(test_db):
    test_db.add(Parcelle(id=10, nom="planche centrale", nom_normalise="planchecentrale",
                         actif=True, potager_id=1, est_pepiniere=False))
    test_db.add(CultureConfig(nom="tomate", type_organe_recolte="reproducteur", potager_id=1))
    test_db.flush()
    ctx = TenantContext(user_id=1, potager_id=1, role="owner")

    item = parser_saisie("planté 8 tomates au rang 3 de la planche centrale", ctx, db=test_db).items[0]

    assert item["rang_position"] == 3
    assert item["rang"] is None                       # pas le multiplicateur
    assert (item["action"], item["culture"], item["quantite"]) == ("plantation", "tomate", 8)
    assert item["parcelle"] == "planche centrale"


@pytest.mark.parametrize("phrase,position", [
    ("planté 8 tomates dans le rang 2 de la planche centrale", 2),
    ("planté 8 tomates au troisième rang de la planche centrale", 3),
    ("planté 8 tomates au 4e rang de la planche centrale", 4),
])
def test_us326_ca5_parseur_tournures_de_position(test_db, phrase, position):
    test_db.add(Parcelle(id=10, nom="planche centrale", nom_normalise="planchecentrale",
                         actif=True, potager_id=1, est_pepiniere=False))
    test_db.add(CultureConfig(nom="tomate", type_organe_recolte="reproducteur", potager_id=1))
    test_db.flush()
    resultat = parser_saisie(phrase, TenantContext(user_id=1, potager_id=1, role="owner"), db=test_db)
    assert resultat.items and resultat.items[0]["rang_position"] == position


def test_us326_g5_sur_3_rangs_reste_un_multiplicateur_lu_par_le_modele(test_db):
    test_db.add(Parcelle(id=10, nom="planche centrale", nom_normalise="planchecentrale",
                         actif=True, potager_id=1, est_pepiniere=False))
    test_db.add(CultureConfig(nom="salade", type_organe_recolte="vegetatif", potager_id=1))
    test_db.flush()
    resultat = parser_saisie("planté 4 salades sur 3 rangs planche centrale",
                             TenantContext(user_id=1, potager_id=1, role="owner"), db=test_db)
    assert resultat.items is None
    assert "rangs" in resultat.raison


def test_us326_ca5_le_geste_confirme_enregistre_la_position(db):
    user, potager = _potager(db)
    parcelle = _planche(db, potager)
    parsed = {"action": "plantation", "culture": "tomate", "quantite": 8, "unite": "plants",
              "parcelle": parcelle.nom, "rang_position": 3}
    event = creer_evenement_confirme(db, _ctx(user, potager), parsed,
                                     "planté 8 tomates au rang 3", parcelle)
    assert event.rang_position == 3
    assert event.rang is None


@pytest.mark.parametrize("parsed,attendu", [
    ({"rang_position": 7}, "5 rangs"),
    ({"rang_position": 4, "rang": 3}, "pas de rang 6"),
    ({"rang_position": 2, "rang_longueur_m": 3}, "n'a pas de longueur"),
    ({"rang_longueur_m": 3}, "numéro du rang"),
])
def test_us326_ca5_position_impossible_refusee(db, parsed, attendu):
    user, potager = _potager(db)
    parcelle = _planche(db, potager)
    base = {"action": "plantation", "culture": "tomate", "quantite": 8, "unite": "plants",
            "parcelle": parcelle.nom}
    with pytest.raises(PositionRangRefuseeError, match=attendu):
        creer_evenement_confirme(db, _ctx(user, potager), {**base, **parsed}, "planté", parcelle)
    assert db.query(Evenement).count() == 0


def test_us326_ca5_position_refusee_dans_une_pepiniere(db):
    user, potager = _potager(db)
    serre = _planche(db, potager, "serre", nb_rangs=None)
    serre.est_pepiniere = True
    db.commit()
    parsed = {"action": "plantation", "culture": "tomate", "quantite": 8, "unite": "plants",
              "parcelle": "serre", "rang_position": 1}
    with pytest.raises(PositionRangRefuseeError, match="pépinière"):
        creer_evenement_confirme(db, _ctx(user, potager), parsed, "planté", serre)


def test_us326_ca5_position_sans_parcelle_refusee():
    with pytest.raises(svc_geometrie.PositionRangRefuseeError, match="quelle parcelle"):
        svc_geometrie.verifier_position_rang(
            None, 1, parcelle=None, culture="tomate", variete=None, rang_position=3,
        )


def test_us326_ca5_une_recolte_ne_se_pose_pas_a_un_rang(db):
    user, potager = _potager(db)
    parcelle = _planche(db, potager)
    _plante(db, potager, parcelle, "tomate", 8, 1)
    parsed = {"action": "recolte", "culture": "tomate", "quantite": 2, "unite": "kg",
              "parcelle": parcelle.nom, "rang_position": 1}
    with pytest.raises(PositionRangRefuseeError, match="semis ou une plantation"):
        creer_evenement_confirme(db, _ctx(user, potager), parsed, "récolté", parcelle)


# ── P4, G4 : le rang partagé ─────────────────────────────────────────────────

def test_us326_p4_sans_longueur_un_rang_porte_une_seule_culture(db):
    user, potager = _potager(db)
    parcelle = _planche(db, potager)                       # pas de longueur
    _plante(db, potager, parcelle, "chou de Bruxelles", 6, 1, position=3)
    parsed = {"action": "plantation", "culture": "chou kale", "quantite": 4, "unite": "plants",
              "parcelle": parcelle.nom, "rang_position": 3}
    with pytest.raises(PositionRangRefuseeError, match="un rang ne porte qu'une culture"):
        creer_evenement_confirme(db, _ctx(user, potager), parsed, "planté", parcelle)


def test_us326_p4_la_meme_culture_peut_revenir_sur_son_rang(db):
    user, potager = _potager(db)
    parcelle = _planche(db, potager)
    _plante(db, potager, parcelle, "chou de Bruxelles", 6, 1, position=3)
    parsed = {"action": "plantation", "culture": "chou de Bruxelles", "quantite": 2,
              "unite": "plants", "parcelle": parcelle.nom, "rang_position": 3}
    event = creer_evenement_confirme(db, _ctx(user, potager), parsed, "planté", parcelle)
    assert event.rang_position == 3


def test_us326_p4_une_culture_sans_position_n_empeche_rien(db):
    """G3 : une numérotation d'installation n'est pas une place en terre."""
    user, potager = _potager(db)
    parcelle = _planche(db, potager)
    _plante(db, potager, parcelle, "poireau", 20, 1)                # rang 1 par installation
    parsed = {"action": "plantation", "culture": "tomate", "quantite": 8, "unite": "plants",
              "parcelle": parcelle.nom, "rang_position": 1}
    creer_evenement_confirme(db, _ctx(user, potager), parsed, "planté", parcelle)
    d = _disposition(db, potager, parcelle)
    assert _occupes(d) == [(1, "tomate"), (2, "poireau")]


def test_us326_gherkin2_un_rang_partage_porte_deux_cultures_et_leurs_parts(db):
    user, potager = _potager(db)
    parcelle = _planche(db, potager, longueur=10.0)
    _plante(db, potager, parcelle, "chou de Bruxelles", 6, 1, position=3, longueur_rang=6.0)
    parsed = {"action": "plantation", "culture": "chou kale", "quantite": 4, "unite": "plants",
              "parcelle": parcelle.nom, "rang_position": 3, "rang_longueur_m": 4}
    creer_evenement_confirme(db, _ctx(user, potager), parsed, "planté", parcelle)

    d = _disposition(db, potager, parcelle)

    rang3 = sorted((r for r in d["rangs"] if r["numero"] == 3), key=lambda r: r["culture"])
    assert [(r["culture"], r["part_m"], r["part"]) for r in rang3] == [
        ("chou de Bruxelles", 6.0, 0.6), ("chou kale", 4.0, 0.4),
    ]
    assert all(r["part_source"] == SOURCE_JARDINIER for r in rang3)
    assert d["rangs_occupes"] == 1                      # un rang partagé compte une fois
    assert d["rangs_libres"] == 4


def test_us326_g4_part_non_dite_repartit_le_reste(db):
    _, potager = _potager(db)
    parcelle = _planche(db, potager, longueur=10.0)
    _plante(db, potager, parcelle, "chou de Bruxelles", 6, 1, position=3, longueur_rang=6.0)
    _plante(db, potager, parcelle, "chou kale", 4, 2, position=3)
    kale = next(r for r in _disposition(db, potager, parcelle)["rangs"] if r["culture"] == "chou kale")
    assert (kale["part_m"], kale["part"], kale["part_source"]) == (4.0, 0.4, "repartie")


def test_us326_g4_seule_sur_son_rang_une_culture_l_occupe_entier(db):
    _, potager = _potager(db)
    parcelle = _planche(db, potager, longueur=10.0)
    _plante(db, potager, parcelle, "tomate", 8, 1)
    tomate = next(r for r in _disposition(db, potager, parcelle)["rangs"] if r["culture"] == "tomate")
    assert (tomate["part_m"], tomate["part"], tomate["part_source"]) == (10.0, 1.0, "rang_entier")


def test_us326_p4_longueurs_dites_ne_depassent_pas_le_rang(db):
    user, potager = _potager(db)
    parcelle = _planche(db, potager, longueur=10.0)
    _plante(db, potager, parcelle, "chou de Bruxelles", 6, 1, position=3, longueur_rang=7.0)
    parsed = {"action": "plantation", "culture": "chou kale", "quantite": 4, "unite": "plants",
              "parcelle": parcelle.nom, "rang_position": 3, "rang_longueur_m": 4}
    with pytest.raises(PositionRangRefuseeError, match="ne tiennent pas"):
        creer_evenement_confirme(db, _ctx(user, potager), parsed, "planté", parcelle)


def test_us326_gherkin2_le_plan_expose_les_parts(client, db):
    user, potager = _potager(db)
    parcelle = _planche(db, potager, longueur=10.0)
    _plante(db, potager, parcelle, "chou de Bruxelles", 6, 1, position=3, longueur_rang=6.0)
    _plante(db, potager, parcelle, "chou kale", 4, 2, position=3, longueur_rang=4.0)

    plan = client.get("/plan", headers=_headers(user)).json()

    disposition = next(p for p in plan["parcelles"] if p["id"] == parcelle.id)["disposition"]
    rang3 = [r for r in disposition["rangs"] if r["numero"] == 3]
    assert {r["culture"]: r["part"] for r in rang3} == {"chou de Bruxelles": 0.6, "chou kale": 0.4}
    assert disposition["mode_numerotation"] == NUMEROTATION_POSITIONS


# ── Vocabulaire et bornes du service ─────────────────────────────────────────

def test_us326_validation_pure_du_service():
    propres = svc_geometrie.valider_geometrie_parcelle(
        {"forme": "Pépinière", "x_m": None, "y_m": None, "rotation_deg": -90}
    )
    assert propres == {"forme": "pepiniere", "x_m": None, "y_m": None, "rotation_deg": 270.0}
    with pytest.raises(svc_geometrie.GeometrieInvalideError):
        svc_geometrie.valider_geometrie_parcelle({"x_m": 1, "y_m": None})
    assert svc_geometrie.superficie_posee(12, 5) == 60.0
    assert svc_geometrie.superficie_posee(None, 5) is None

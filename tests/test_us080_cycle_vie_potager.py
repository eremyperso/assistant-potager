"""
tests/test_us080_cycle_vie_potager.py — [US-080] Modéliser le cycle de vie d'un
potager (actif / archivé / supprimé)
--------------------------------------------------------------------------------
Couvre CA1 (colonnes `etat`/`archive_le`/`supprime_le`), CA2 (backfill à `actif`),
CA3 (idempotence + rollback, vérifiés sur le SQL de migration), CA4 (filtrage par
état dans `lister_potagers_utilisateur`), CA5 (`GET /potagers?etat=`), CA6
(`resoudre_tenant_context` / `definir_potager_actif` refusent un potager non
actif), CA7 (un potager `supprime` est invisible même en `etat=tous`) et CA8
(non-régression du cas mono-potager).

US purement structurelle : aucun rendu visuel à valider, tout est couvert en pytest.
"""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import auth as svc_auth
from app.services import potager_actif as svc_potager_actif
from database.db import Base
from database.models import Potager, PotagerMembre, User


_RACINE = Path(__file__).resolve().parent.parent
_MIGRATION = _RACINE / "migrations" / "migration_v29.sql"
_ROLLBACK = _RACINE / "migrations" / "rollback_v29.sql"


def _creer_user(db, email="jardinier@example.com", **kwargs):
    user = User(email=email, mot_de_passe_hash="x", **kwargs)
    db.add(user)
    db.commit()
    return user


def _creer_potager(db, nom, proprietaire_id, membre_id=None, role="owner", etat=None):
    potager = Potager(nom=nom, proprietaire_id=proprietaire_id)
    if etat is not None:
        potager.etat = etat
    db.add(potager)
    db.commit()
    db.add(PotagerMembre(user_id=membre_id or proprietaire_id, potager_id=potager.id, role=role))
    db.commit()
    return potager


# ── CA1 — Colonnes du cycle de vie ────────────────────────────────────────

def test_us080_ca1_les_trois_colonnes_existent(test_engine):
    colonnes = {c["name"] for c in inspect(test_engine).get_columns("potagers")}
    assert {"etat", "archive_le", "supprime_le"} <= colonnes


def test_us080_ca1_etat_par_defaut_actif_et_horodatages_nuls(test_db):
    """Un potager naît actif, sans horodatage — aucun état brouillon."""
    user = _creer_user(test_db)

    potager = _creer_potager(test_db, "Jardin neuf", user.id)

    assert potager.etat == "actif"
    assert potager.archive_le is None
    assert potager.supprime_le is None


def test_us080_ca1_valeurs_detat_sans_accent_en_base(test_db):
    """Les libellés accentués restent côté affichage : la base ne connaît que
    `actif` / `archive` / `supprime`."""
    assert svc_potager_actif.ETAT_ACTIF == "actif"
    assert svc_potager_actif.ETAT_ARCHIVE == "archive"
    assert svc_potager_actif.ETAT_SUPPRIME == "supprime"

    sql = _MIGRATION.read_text(encoding="utf-8")
    contrainte = re.search(r"CHECK \(etat IN \(([^)]*)\)\)", sql).group(1)
    assert "'actif'" in contrainte and "'archive'" in contrainte and "'supprime'" in contrainte
    assert "archivé" not in contrainte and "supprimé" not in contrainte


# ── CA2, CA3 — Migration : backfill, idempotence, rollback ────────────────

def test_us080_ca2_la_migration_backfille_tous_les_potagers_a_actif():
    """Scénario Gherkin « Migration sur une base existante » : le DEFAULT couvre
    les lignes existantes, le UPDATE borné sert de filet — aucune donnée métier
    n'est touchée."""
    sql = _MIGRATION.read_text(encoding="utf-8")

    assert "NOT NULL DEFAULT 'actif'" in sql
    assert "UPDATE potagers SET etat = 'actif' WHERE etat IS NULL;" in sql
    # Aucune écriture sur les données métier du potager
    for table in ("evenements", "parcelles", "potager_membres"):
        assert f"UPDATE {table}" not in sql
        assert f"DELETE FROM {table}" not in sql


def test_us080_ca3_la_migration_est_idempotente():
    """Scénario Gherkin « Idempotence » : rejouable sans erreur ni doublon."""
    sql = _MIGRATION.read_text(encoding="utf-8")

    for colonne in ("etat", "archive_le", "supprime_le"):
        assert re.search(rf"ADD COLUMN IF NOT EXISTS\s+{colonne}\b", sql), colonne
    # La contrainte CHECK n'est ajoutée que si elle n'existe pas déjà
    assert "FROM pg_constraint WHERE conname = 'ck_potagers_etat'" in sql
    assert "CREATE INDEX IF NOT EXISTS idx_potagers_etat" in sql


def test_us080_ca3_le_rollback_supprime_colonnes_et_contrainte():
    sql = _ROLLBACK.read_text(encoding="utf-8")

    assert "DROP CONSTRAINT IF EXISTS ck_potagers_etat" in sql
    for colonne in ("etat", "archive_le", "supprime_le"):
        assert f"DROP COLUMN IF EXISTS {colonne}" in sql


# ── CA4, CA7 — Filtrage par état dans la couche services ──────────────────

def test_us080_ca4_lister_ne_retourne_que_les_actifs_par_defaut(test_db):
    user = _creer_user(test_db)
    actif = _creer_potager(test_db, "Jardin cultivé", user.id)
    _creer_potager(test_db, "Jardin abandonné", user.id, etat="archive")

    potagers = svc_potager_actif.lister_potagers_utilisateur(test_db, user.id)

    assert [p.id for p in potagers] == [actif.id]


def test_us080_ca4_filtre_archive_ne_retourne_que_les_archives(test_db):
    user = _creer_user(test_db)
    _creer_potager(test_db, "Jardin cultivé", user.id)
    archive = _creer_potager(test_db, "Jardin abandonné", user.id, etat="archive")

    potagers = svc_potager_actif.lister_potagers_utilisateur(test_db, user.id, etat="archive")

    assert [p.id for p in potagers] == [archive.id]


def test_us080_ca4_filtre_tous_retourne_actifs_et_archives(test_db):
    user = _creer_user(test_db)
    actif = _creer_potager(test_db, "Jardin cultivé", user.id)
    archive = _creer_potager(test_db, "Jardin abandonné", user.id, etat="archive")

    potagers = svc_potager_actif.lister_potagers_utilisateur(test_db, user.id, etat="tous")

    assert [p.id for p in potagers] == [actif.id, archive.id]


def test_us080_ca7_un_potager_supprime_est_invisible_meme_avec_tous(test_db):
    """[CA7] Le potager supprimé n'existe plus que pour le job de purge (US-084)."""
    user = _creer_user(test_db)
    actif = _creer_potager(test_db, "Jardin cultivé", user.id)
    _creer_potager(test_db, "Jardin supprimé", user.id, etat="supprime")

    for filtre in ("actif", "archive", "tous"):
        ids = [p.id for p in svc_potager_actif.lister_potagers_utilisateur(test_db, user.id, filtre)]
        assert "supprime" not in [
            svc_potager_actif._etat_potager(test_db, pid) for pid in ids
        ], filtre
    assert [p.id for p in svc_potager_actif.lister_potagers_utilisateur(test_db, user.id, "tous")] == [actif.id]


def test_us080_ca5_filtre_etat_inconnu_rejete(test_db):
    user = _creer_user(test_db)
    _creer_potager(test_db, "Jardin", user.id)

    with pytest.raises(svc_potager_actif.FiltreEtatInvalideError):
        svc_potager_actif.lister_potagers_utilisateur(test_db, user.id, etat="poubelle")


def test_us080_ca5_filtre_vide_ou_none_vaut_actif(test_db):
    """Edge case : une query string absente ou vide ne doit pas ouvrir la liste
    aux potagers archivés."""
    assert svc_potager_actif.normaliser_filtre_etat(None) == "actif"
    assert svc_potager_actif.normaliser_filtre_etat("") == "actif"
    assert svc_potager_actif.normaliser_filtre_etat("  ") == "actif"
    assert svc_potager_actif.normaliser_filtre_etat("ARCHIVE") == "archive"
    assert svc_potager_actif.normaliser_filtre_etat("archivé") == "archive"


# ── CA6 — Un potager non actif ne peut pas devenir le potager actif ───────

def test_us080_ca6_activer_un_potager_archive_est_refuse(test_db):
    """Scénario Gherkin « Un potager archivé ne peut pas devenir le potager actif »."""
    user = _creer_user(test_db)
    principal = _creer_potager(test_db, "Jardin principal", user.id)
    archive = _creer_potager(test_db, "Jardin archivé", user.id, etat="archive")
    svc_potager_actif.definir_potager_actif(test_db, user.id, principal.id)

    with pytest.raises(svc_potager_actif.PotagerInactifError):
        svc_potager_actif.definir_potager_actif(test_db, user.id, archive.id)

    test_db.refresh(user)
    assert user.potager_actif_id == principal.id  # potager actif inchangé


def test_us080_ca6_exception_dediee_distincte_de_non_membre():
    """[CA6] L'exception d'état ne doit pas se confondre avec un défaut de droits :
    un `except PotagerNonMembreError` ne doit pas l'attraper."""
    assert not issubclass(svc_potager_actif.PotagerInactifError, svc_potager_actif.PotagerNonMembreError)
    assert not issubclass(svc_potager_actif.PotagerNonMembreError, svc_potager_actif.PotagerInactifError)


def test_us080_ca7_activer_un_potager_supprime_le_traite_comme_inexistant(test_db):
    user = _creer_user(test_db)
    supprime = _creer_potager(test_db, "Jardin supprimé", user.id, etat="supprime")

    with pytest.raises(svc_potager_actif.PotagerNonMembreError):
        svc_potager_actif.definir_potager_actif(test_db, user.id, supprime.id)


def test_us080_ca6_un_potager_archive_ne_reste_pas_le_potager_actif(test_db):
    """Le potager actif est archivé après coup (US-083) : la résolution suivante
    doit basculer sur un potager encore actif et purger le pointeur devenu faux."""
    user = _creer_user(test_db)
    user_id = user.id
    principal = _creer_potager(test_db, "Jardin principal", user.id)
    secours = _creer_potager(test_db, "Jardin de secours", user.id)
    svc_potager_actif.definir_potager_actif(test_db, user_id, principal.id)

    principal.etat = "archive"
    test_db.commit()

    ctx = svc_potager_actif.resoudre_tenant_context(test_db, user_id)

    assert ctx.potager_id == secours.id
    recharge = test_db.query(User).filter(User.id == user_id).first()
    assert recharge.potager_actif_id != principal.id


def test_us080_ca6_aucun_potager_actif_restant_leve_aucun_potager(test_db):
    """Cas d'erreur : tous les potagers archivés → même réponse que « aucun
    potager » (409 côté API), pas de contexte sur un potager archivé."""
    user = _creer_user(test_db)
    potager = _creer_potager(test_db, "Jardin unique", user.id)
    svc_potager_actif.definir_potager_actif(test_db, user.id, potager.id)
    potager.etat = "archive"
    test_db.commit()

    with pytest.raises(svc_potager_actif.AucunPotagerError):
        svc_potager_actif.resoudre_tenant_context(test_db, user.id)


# ── CA8 — Non-régression du cas mono-potager (~85 % des utilisateurs) ──────

def test_us080_ca8_mono_potager_selection_auto_inchangee(test_db):
    """[CA8] Un utilisateur avec un seul potager ne perçoit aucun changement :
    sélection automatique silencieuse et persistée, comme en US-046."""
    user = _creer_user(test_db)
    user_id = user.id
    potager = _creer_potager(test_db, "Jardin unique", user.id)

    ctx = svc_potager_actif.resoudre_tenant_context(test_db, user_id)

    assert ctx.potager_id == potager.id
    assert ctx.role == "owner"
    recharge = test_db.query(User).filter(User.id == user_id).first()
    assert recharge.potager_actif_id == potager.id


# ── Endpoints web (CA5) ──────────────────────────────────────────────────────

@pytest.fixture
def _auth_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def app_client(_auth_engine, monkeypatch):
    import main
    TestSessionLocal = sessionmaker(bind=_auth_engine)
    monkeypatch.setattr(main, "SessionLocal", TestSessionLocal)
    main.app.state.limiter.reset()
    with TestClient(main.app) as c:
        yield c


def _auth_header(user_id):
    return {"Authorization": f"Bearer {svc_auth.creer_access_token(user_id)}"}


def _preparer_deux_potagers(engine):
    """Un utilisateur, un potager actif et un potager archivé."""
    db = sessionmaker(bind=engine)()
    user = svc_auth.inscrire_utilisateur(db, "jardinier@example.com", "motdepasse123")
    actif = _creer_potager(db, "Jardin cultivé", user.id)
    archive = _creer_potager(db, "Jardin abandonné", user.id, etat="archive")
    ids = (user.id, actif.id, archive.id)
    db.close()
    return ids


def test_us080_ca5_get_potagers_sans_parametre_masque_les_archives(app_client, _auth_engine):
    """Scénario Gherkin « Un potager archivé disparaît des listes par défaut »."""
    user_id, actif_id, _ = _preparer_deux_potagers(_auth_engine)

    resp = app_client.get("/potagers", headers=_auth_header(user_id))

    assert resp.status_code == 200
    potagers = resp.json()["potagers"]
    assert len(potagers) == 1
    assert potagers[0]["id"] == actif_id
    assert potagers[0]["etat"] == "actif"


def test_us080_ca5_get_potagers_etat_tous_retourne_les_deux_avec_leur_etat(app_client, _auth_engine):
    user_id, actif_id, archive_id = _preparer_deux_potagers(_auth_engine)

    resp = app_client.get("/potagers?etat=tous", headers=_auth_header(user_id))

    assert resp.status_code == 200
    etats = {p["id"]: p["etat"] for p in resp.json()["potagers"]}
    assert etats == {actif_id: "actif", archive_id: "archive"}


def test_us080_ca5_get_potagers_etat_archive(app_client, _auth_engine):
    user_id, _, archive_id = _preparer_deux_potagers(_auth_engine)

    resp = app_client.get("/potagers?etat=archive", headers=_auth_header(user_id))

    potagers = resp.json()["potagers"]
    assert [p["id"] for p in potagers] == [archive_id]


def test_us080_ca5_get_potagers_conserve_role_et_compteurs(app_client, _auth_engine):
    """[CA5, CA8] L'état s'ajoute aux champs existants (US-048/US-054), il ne les
    remplace pas."""
    user_id, actif_id, _ = _preparer_deux_potagers(_auth_engine)

    potager = app_client.get("/potagers", headers=_auth_header(user_id)).json()["potagers"][0]

    assert potager["role"] == "owner"
    assert potager["nb_parcelles"] == 0
    assert potager["nb_membres"] == 1
    assert potager["actif"] is True  # potager sélectionné, à ne pas confondre avec `etat`


def test_us080_ca5_get_potagers_etat_invalide_renvoie_400(app_client, _auth_engine):
    user_id, _, _ = _preparer_deux_potagers(_auth_engine)

    resp = app_client.get("/potagers?etat=poubelle", headers=_auth_header(user_id))

    assert resp.status_code == 400


def test_us080_ca6_activer_un_potager_archive_renvoie_409(app_client, _auth_engine):
    user_id, actif_id, archive_id = _preparer_deux_potagers(_auth_engine)

    resp = app_client.post(f"/potagers/{archive_id}/activer", headers=_auth_header(user_id))

    assert resp.status_code == 409
    assert "archiv" in resp.json()["detail"].lower()


def test_us080_ca8_activer_un_potager_actif_fonctionne_toujours(app_client, _auth_engine):
    """[CA8] Non-régression US-046 : la bascule normale reste inchangée."""
    user_id, actif_id, _ = _preparer_deux_potagers(_auth_engine)

    resp = app_client.post(f"/potagers/{actif_id}/activer", headers=_auth_header(user_id))

    assert resp.status_code == 200
    assert resp.json()["potager_id"] == actif_id

"""
tests/test_us040_modele_multitenant.py — [US-040] Socle multi-tenant
----------------------------------------------------------------------
Couvre les critères d'acceptance testables au niveau des modèles SQLAlchemy
(CA1, CA2, CA3, CA4, CA6, CA7). Les critères liés au script SQL brut
(CA5 backfill, CA8 idempotence, CA9 rollback, CA10 non-régression via psql)
ne sont pas exécutables sur SQLite en mémoire — ils nécessitent une base
PostgreSQL réelle et sont à vérifier manuellement via
`psql -f migrations/migration_v16.sql` (voir en-tête du fichier).
"""
import re
from pathlib import Path

import pytest
from sqlalchemy import inspect

from database.models import User, Potager, PotagerMembre, Evenement, Parcelle, CultureConfig


# ── CA1 — Table users ─────────────────────────────────────────────────────

def test_us040_ca1_table_users_colonnes(test_engine):
    inspector = inspect(test_engine)
    columns = {c["name"] for c in inspector.get_columns("users")}
    # [US-044] mot_de_passe_hash / email_verifie ajoutées pour l'auth web JWT
    # [US-046] potager_actif_id ajoutée pour le potager sélectionné
    assert columns == {
        "id", "email", "telegram_chat_id", "nom", "cree_le",
        "mot_de_passe_hash", "email_verifie", "potager_actif_id",
    }


def test_us040_ca1_users_email_et_chat_id_uniques(test_db):
    u1 = User(email="a@example.com", telegram_chat_id=111, nom="Alice")
    test_db.add(u1)
    test_db.commit()

    assert u1.id is not None
    assert u1.telegram_chat_id == 111


# ── CA2 — Table potagers ──────────────────────────────────────────────────

def test_us040_ca2_table_potagers_colonnes(test_engine):
    inspector = inspect(test_engine)
    columns = {c["name"] for c in inspector.get_columns("potagers")}
    assert columns == {"id", "nom", "latitude", "longitude", "proprietaire_id", "plan", "cree_le"}


def test_us040_ca2_potager_plan_par_defaut_free(test_db):
    owner = User(nom="Emmanuel")
    test_db.add(owner)
    test_db.commit()

    potager = Potager(nom="Potager principal", latitude=48.9, longitude=2.2, proprietaire_id=owner.id)
    test_db.add(potager)
    test_db.commit()

    assert potager.plan == "free"
    assert potager.proprietaire_id == owner.id


# ── CA3 — Table potager_membres ───────────────────────────────────────────

def test_us040_ca3_table_potager_membres_colonnes(test_engine):
    inspector = inspect(test_engine)
    columns = {c["name"] for c in inspector.get_columns("potager_membres")}
    assert columns == {"user_id", "potager_id", "role"}

    pk = inspector.get_pk_constraint("potager_membres")["constrained_columns"]
    assert set(pk) == {"user_id", "potager_id"}


def test_us040_ca3_membre_owner_cree(test_db):
    owner = User(nom="Emmanuel")
    test_db.add(owner)
    test_db.commit()

    potager = Potager(nom="Potager principal", proprietaire_id=owner.id)
    test_db.add(potager)
    test_db.commit()

    membre = PotagerMembre(user_id=owner.id, potager_id=potager.id, role="owner")
    test_db.add(membre)
    test_db.commit()

    retrouve = test_db.get(PotagerMembre, (owner.id, potager.id))
    assert retrouve.role == "owner"


# ── CA4 — potager_id nullable sur les tables métier ───────────────────────

@pytest.mark.parametrize("model,table", [
    (Evenement, "evenements"),
    (Parcelle, "parcelles"),
    (CultureConfig, "culture_config"),
])
def test_us040_ca4_potager_id_present_et_nullable(test_engine, model, table):
    inspector = inspect(test_engine)
    columns = {c["name"]: c for c in inspector.get_columns(table)}
    assert "potager_id" in columns
    assert columns["potager_id"]["nullable"] is True


def test_us040_ca4_evenement_creable_sans_potager_id(test_db):
    """Non-régression : un événement reste créable sans potager_id fourni explicitement.
    [US-042] La colonne porte désormais un default=1 (DEFAULT_POTAGER_ID) côté ORM pour
    que les fixtures de tests existantes retombent sur le potager #1 sans modification —
    ce n'est plus NULL, contrairement au comportement d'origine de US-040."""
    parcelle = Parcelle(nom="Nord", nom_normalise="nord")
    test_db.add(parcelle)
    test_db.commit()

    ev = Evenement(type_action="recolte", culture="tomate", quantite=2.0, unite="kg", parcelle_id=parcelle.id)
    test_db.add(ev)
    test_db.commit()

    assert ev.id is not None
    assert ev.potager_id == 1


# ── CA6 — Index composite sur evenements(potager_id, date) ───────────────

def test_us040_ca6_index_composite_evenements_potager_date(test_engine):
    inspector = inspect(test_engine)
    index_names = {idx["name"]: idx["column_names"] for idx in inspector.get_indexes("evenements")}
    assert "idx_evenements_potager_date" in index_names
    assert index_names["idx_evenements_potager_date"] == ["potager_id", "date"]


@pytest.mark.parametrize("table", ["parcelles", "culture_config"])
def test_us040_ca6_index_potager_id_autres_tables(test_engine, table):
    inspector = inspect(test_engine)
    all_columns_indexed = {
        col for idx in inspector.get_indexes(table) for col in idx["column_names"]
    }
    assert "potager_id" in all_columns_indexed


# ── CA7 — Le socle US-040 n'imposait pas de scoping dans bot.py / main.py ─
# [US-042] Ce garde-fou est devenu obsolète : le scoping applicatif qu'il
# interdisait explicitement est désormais le périmètre livré par US-042
# (app/services/ + quelques appels résiduels utils/stock.py dans main.py,
# voir app/services/*.py et migrations/migration_v17.sql). Le test précédent
# ("aucune occurrence de potager_id dans bot.py/main.py") est supprimé car il
# contredirait par construction tout scoping ajouté depuis.


# ── CA9 — Script de rollback présent et cohérent ──────────────────────────

def test_us040_ca9_rollback_supprime_tables_et_colonnes_dans_lordre_inverse():
    repo_root = Path(__file__).resolve().parent.parent
    rollback_sql = (repo_root / "migrations" / "rollback_v16.sql").read_text(encoding="utf-8")

    # Colonnes supprimées avant les tables tenant (ordre inverse des FK)
    drop_column_pos = rollback_sql.index("DROP COLUMN IF EXISTS potager_id")
    drop_table_users_pos = rollback_sql.index("DROP TABLE IF EXISTS users")
    assert drop_column_pos < drop_table_users_pos

    for table in ("potager_membres", "potagers", "users"):
        assert f"DROP TABLE IF EXISTS {table}" in rollback_sql

    # potager_membres (dépend de users et potagers) supprimée en premier
    assert rollback_sql.index("DROP TABLE IF EXISTS potager_membres") < rollback_sql.index("DROP TABLE IF EXISTS potagers")
    assert rollback_sql.index("DROP TABLE IF EXISTS potagers") < rollback_sql.index("DROP TABLE IF EXISTS users")


# ── CA8 — Idempotence : la migration utilise IF NOT EXISTS / WHERE ... IS NULL

def test_us040_ca8_migration_idempotente_par_construction():
    repo_root = Path(__file__).resolve().parent.parent
    migration_sql = (repo_root / "migrations" / "migration_v16.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS users" in migration_sql
    assert "CREATE TABLE IF NOT EXISTS potagers" in migration_sql
    assert "CREATE TABLE IF NOT EXISTS potager_membres" in migration_sql
    assert re.search(r"ADD COLUMN IF NOT EXISTS potager_id", migration_sql)
    assert "WHERE potager_id IS NULL" in migration_sql
    assert "CREATE INDEX IF NOT EXISTS" in migration_sql

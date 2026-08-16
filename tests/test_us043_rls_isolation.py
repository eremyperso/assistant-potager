"""
tests/test_us043_rls_isolation.py — [US-043]
-----------------------------------------------------------------------
Row-Level Security PostgreSQL en défense en profondeur.

RLS est une fonctionnalité PostgreSQL — non disponible sur SQLite (moteur des
tests unitaires du reste du projet, voir tests/conftest.py). Ce fichier est
donc un test d'INTÉGRATION, sauté automatiquement si aucune base PostgreSQL
de test n'est configurée.

Pour l'exécuter réellement (recommandé avant tout déploiement en production
de migration_v18.sql) :

    $env:RLS_TEST_DATABASE_URL = "postgresql://potager_user:motdepasse@localhost:5432/potager_rls_test"
    $env:RLS_TEST_APP_USER_PASSWORD = "un-mot-de-passe-test"
    pytest tests/test_us043_rls_isolation.py -v

⚠️ Pointer IMPÉRATIVEMENT vers une base de test dédiée et jetable — ce test
crée/détruit les tables et le rôle `app_user` à chaque exécution. Ne jamais
utiliser potager_dev ou potager_prod ici.

Couvre :
- CA6 : une requête volontairement non scopée (SELECT * FROM evenements sans
  filtre potager_id), exécutée avec le rôle app_user, ne retourne que les
  lignes du potager positionné via app.potager_id.
- CA5 : sans SET LOCAL app.potager_id, la requête échoue explicitement
  (fail-fast), plutôt que de renvoyer zéro ligne silencieusement.
- CA7 : le rôle admin/propriétaire des tables n'est pas soumis aux policies.
"""
import os
from datetime import datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

RLS_TEST_DATABASE_URL = os.environ.get("RLS_TEST_DATABASE_URL")
RLS_TEST_APP_USER_PASSWORD = os.environ.get("RLS_TEST_APP_USER_PASSWORD", "test-password-rls")

pytestmark = pytest.mark.skipif(
    not RLS_TEST_DATABASE_URL,
    reason="RLS_TEST_DATABASE_URL non défini — test d'intégration PostgreSQL sauté "
           "(voir docstring du fichier pour l'exécuter réellement)",
)


@pytest.fixture(scope="module")
def admin_engine():
    engine = create_engine(RLS_TEST_DATABASE_URL)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def rls_setup(admin_engine):
    """Crée un schéma minimal (evenements + parcelles + potagers), applique
    RLS + le rôle app_user (équivalent condensé de migration_v18.sql), insère
    des données pour deux potagers distincts, puis nettoie tout à la fin."""
    with admin_engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS evenements CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS parcelles CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS potagers CASCADE"))
        conn.execute(text("""
            CREATE TABLE potagers (
                id SERIAL PRIMARY KEY,
                nom VARCHAR(100) NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE evenements (
                id SERIAL PRIMARY KEY,
                type_action VARCHAR,
                culture VARCHAR,
                quantite FLOAT,
                unite VARCHAR,
                date TIMESTAMP,
                potager_id INTEGER NOT NULL REFERENCES potagers(id)
            )
        """))
        conn.execute(text("INSERT INTO potagers (id, nom) VALUES (1, 'Potager A'), (2, 'Potager B')"))
        conn.execute(text(
            "INSERT INTO evenements (type_action, culture, quantite, unite, date, potager_id) "
            "VALUES ('recolte', 'tomate', 5.0, 'kg', :d, 1), "
            "('recolte', 'courgette', 9.0, 'kg', :d, 2)"
        ), {"d": datetime.now()})

        conn.execute(text(
            "DO $$ BEGIN "
            "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN "
            "EXECUTE format('CREATE ROLE app_user LOGIN PASSWORD %L', :pwd); "
            "END IF; END $$;"
        ).bindparams(pwd=RLS_TEST_APP_USER_PASSWORD))
        conn.execute(text("GRANT USAGE ON SCHEMA public TO app_user"))
        conn.execute(text("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user"))
        conn.execute(text("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user"))

        conn.execute(text("ALTER TABLE evenements ENABLE ROW LEVEL SECURITY"))
        conn.execute(text("DROP POLICY IF EXISTS tenant_isolation_evenements ON evenements"))
        conn.execute(text(
            "CREATE POLICY tenant_isolation_evenements ON evenements "
            "USING (potager_id = current_setting('app.potager_id')::int) "
            "WITH CHECK (potager_id = current_setting('app.potager_id')::int)"
        ))

    yield

    with admin_engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS evenements CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS parcelles CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS potagers CASCADE"))
        conn.execute(text("DROP ROLE IF EXISTS app_user"))


def _app_user_engine():
    base = RLS_TEST_DATABASE_URL
    # Remplace les identifiants de connexion par ceux de app_user, conserve host/port/db.
    from sqlalchemy.engine import make_url
    url = make_url(base).set(username="app_user", password=RLS_TEST_APP_USER_PASSWORD)
    return create_engine(url)


def test_ca6_requete_non_scopee_isolee_par_rls(rls_setup):
    """[CA6] Une requête volontairement non filtrée par potager_id, exécutée
    avec le rôle app_user, ne retourne que les lignes du potager courant."""
    engine = _app_user_engine()
    try:
        with engine.connect() as conn:
            with conn.begin():
                conn.execute(text("SET LOCAL app.potager_id = '1'"))
                # Requête délibérément non scopée — SANS filtre potager_id.
                rows = conn.execute(text("SELECT culture, potager_id FROM evenements")).fetchall()
        cultures = {r.culture for r in rows}
        assert cultures == {"tomate"}
        assert all(r.potager_id == 1 for r in rows)
    finally:
        engine.dispose()


def test_ca6_bis_isolation_symetrique_potager_b(rls_setup):
    """Même test côté potager B — aucune fuite dans l'autre sens."""
    engine = _app_user_engine()
    try:
        with engine.connect() as conn:
            with conn.begin():
                conn.execute(text("SET LOCAL app.potager_id = '2'"))
                rows = conn.execute(text("SELECT culture, potager_id FROM evenements")).fetchall()
        cultures = {r.culture for r in rows}
        assert cultures == {"courgette"}
        assert all(r.potager_id == 2 for r in rows)
    finally:
        engine.dispose()


def test_ca5_fail_fast_sans_setting_leve_une_erreur(rls_setup):
    """[CA5] Sans SET LOCAL app.potager_id, la requête échoue explicitement —
    jamais de zéro ligne silencieux."""
    engine = _app_user_engine()
    try:
        with pytest.raises(Exception) as exc_info:
            with engine.connect() as conn:
                with conn.begin():
                    conn.execute(text("SELECT culture FROM evenements")).fetchall()
        # Message PostgreSQL attendu : "unrecognized configuration parameter"
        assert "app.potager_id" in str(exc_info.value) or "configuration parameter" in str(exc_info.value)
    finally:
        engine.dispose()


def test_ca7_role_admin_non_soumis_aux_policies(admin_engine, rls_setup):
    """[CA7] Le rôle admin/propriétaire des tables voit toutes les lignes,
    sans policy bloquante — migrations et sauvegardes non affectées."""
    with admin_engine.connect() as conn:
        rows = conn.execute(text("SELECT culture FROM evenements")).fetchall()
    cultures = {r.culture for r in rows}
    assert cultures == {"tomate", "courgette"}

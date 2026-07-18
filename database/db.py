import contextvars
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from config import DATABASE_URL

engine       = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base         = declarative_base()

# ─────────────────────────────────────────────────────────────────────────────
# [US-043] Défense en profondeur RLS PostgreSQL
# -----------------------------------------------------------------------------
# `current_potager_id` est positionné une fois par requête/update entrante
# (voir bot.py::_arm_tenant_context, main.py::_tenant_context_middleware,
# et bot.py::job_meteo_quotidienne pour le job de fond hors dispatch Telegram)
# à partir du TenantContext courant (US-041/US-042 — aujourd'hui toujours
# default_context() en attendant l'authentification réelle US-110/112).
#
# Chaque nouvelle transaction SQLAlchemy sur une connexion PostgreSQL arme le
# GUC de session `app.potager_id`, lu par les policies RLS créées en
# migration_v18.sql sur evenements / parcelles / culture_config.
#
# Fail-fast (CA5) : si `current_potager_id` n'a pas été positionné, aucun SET
# LOCAL n'est émis — `current_setting('app.potager_id')` (sans le paramètre
# `missing_ok`) lève alors nativement une erreur PostgreSQL explicite
# ("unrecognized configuration parameter") dès qu'une requête touche une table
# protégée par RLS, plutôt que de renvoyer silencieusement zéro ligne. Les
# requêtes sur des tables non protégées (users, potagers...) ne sont pas
# affectées par cette absence.
#
# SQLite (tests, `DATABASE_URL=sqlite:///:memory:`) ne supporte pas RLS : le
# listener est un no-op sur ce dialecte, le scoping applicatif US-042 reste la
# seule protection dans les tests unitaires.
# ─────────────────────────────────────────────────────────────────────────────
current_potager_id: "contextvars.ContextVar[int | None]" = contextvars.ContextVar(
    "current_potager_id", default=None
)


@event.listens_for(Session, "after_begin")
def _arm_rls_potager_setting(session, transaction, connection):
    """[US-043 / CA4] Arme `app.potager_id` pour la transaction qui démarre."""
    if connection.dialect.name != "postgresql":
        return
    potager_id = current_potager_id.get()
    if potager_id is None:
        return
    connection.execute(text("SET LOCAL app.potager_id = :pid"), {"pid": potager_id})


@contextmanager
def tenant_scope(potager_id: int):
    """[US-043] Positionne `current_potager_id` pour la durée du bloc — utilisé
    par les points d'entrée applicatifs (middleware FastAPI, handler Telegram)
    qui ne s'exécutent pas nécessairement dans une Task asyncio fraîche."""
    token = current_potager_id.set(potager_id)
    try:
        yield
    finally:
        current_potager_id.reset(token)

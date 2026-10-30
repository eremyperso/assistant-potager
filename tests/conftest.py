import os
# Variables d'environnement de test — doivent être définies avant tout import de config
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test_token")
os.environ.setdefault("GROQ_API_KEY", "test_groq_key")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.db import Base


@pytest.fixture(autouse=True)
def _sans_accueil_du_compagnon(monkeypatch):
    """[US-258] L'accueil du premier échange (message de plus) a ses propres tests ;
    les autres tests de l'agent lisent LA réponse, pas l'accueil qui la suit."""
    from unittest.mock import AsyncMock
    from app.bot import interpretation
    monkeypatch.setattr(interpretation, "accueil_premier_contact", AsyncMock())


@pytest.fixture(autouse=True)
def _cache_previsions_meteo_vide():
    """[US-182] Le cache météo vit dans la mémoire du processus : chaque test
    part d'un cache vide, sinon une prévision mise en cache par un test serait
    servie au suivant sans appel Open-Meteo."""
    from app.services import previsions_meteo
    previsions_meteo.vider_cache()
    yield
    previsions_meteo.vider_cache()


@pytest.fixture(scope="session")
def _moteur_compagnon():
    """[US-259] Une base SQLite en mémoire, partagée par toutes les connexions du test
    (StaticPool) : les propositions et les échanges du compagnon y vivent."""
    from sqlalchemy.pool import StaticPool
    import database.models  # noqa: F401 — enregistre les tables dans Base.metadata

    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture(autouse=True)
def memoire_compagnon(_moteur_compagnon, monkeypatch):
    """[US-259] Propositions et conversation sont en base, plus en mémoire du bot :
    chaque test part d'une mémoire vide. Rend la fabrique de sessions, pour les
    tests qui y lisent ou y écrivent directement. [US-261] Les actions menées y sont aussi."""
    from app.services.compagnon import actions_menees, conversations, propositions
    from database.models import ActionMenee, EchangeConversation, Proposition

    fabrique = sessionmaker(bind=_moteur_compagnon, autocommit=False, autoflush=False)
    monkeypatch.setattr(propositions, "SessionLocal", fabrique)
    monkeypatch.setattr(conversations, "SessionLocal", fabrique)
    monkeypatch.setattr(actions_menees, "SessionLocal", fabrique)
    yield fabrique
    with _moteur_compagnon.begin() as connexion:
        connexion.execute(ActionMenee.__table__.delete())
        connexion.execute(EchangeConversation.__table__.delete())
        connexion.execute(Proposition.__table__.delete())


@pytest.fixture(scope="session")
def test_engine():
    """Engine de test SQLite en mémoire."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture
def test_db(test_engine):
    """Session DB de test."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    db = SessionLocal()
    # Clear all tables
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield db
    db.rollback()
    db.close()
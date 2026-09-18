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
def _cache_previsions_meteo_vide():
    """[US-182] Le cache météo vit dans la mémoire du processus : chaque test
    part d'un cache vide, sinon une prévision mise en cache par un test serait
    servie au suivant sans appel Open-Meteo."""
    from app.services import previsions_meteo
    previsions_meteo.vider_cache()
    yield
    previsions_meteo.vider_cache()


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
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import DATABASE_URL

engine       = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,   # reconnecte automatiquement si la connexion est morte
    pool_recycle=300,     # recycle les connexions toutes les 5 min (< timeout PG de 30 min)
)
SessionLocal = sessionmaker(bind=engine)
Base         = declarative_base()

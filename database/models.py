from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func
from database.db import Base


class Evenement(Base):
    __tablename__ = "evenements"

    id             = Column(Integer, primary_key=True, index=True)
    # ⚠️ Plus de server_default : on passe toujours la date explicitement
    # pour respecter "hier", "lundi dernier", etc.
    date           = Column(DateTime, nullable=True, index=True)

    # Action principale
    type_action    = Column(String, index=True)

    # Culture
    culture        = Column(String, index=True)
    variete        = Column(String)

    # Quantité
    quantite       = Column(Float)
    unite          = Column(String)

    # Localisation
    parcelle       = Column(String, index=True)
    rang           = Column(String)

    # Détails
    duree          = Column(Integer)
    traitement     = Column(String)
    commentaire    = Column(String)

    # Texte original dicté
    texte_original = Column(String)

    # Type d'organe récolté (végétatif | reproducteur | null)
    type_organe_recolte = Column(String)


class CultureConfig(Base):
    """Configuration des cultures avec leur type d'organe récolté."""
    __tablename__ = "culture_config"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, unique=True, index=True)  # ex: "salade", "tomate"
    type_organe_recolte = Column(String)  # "végétatif" | "reproducteur"
    description_agronomique = Column(String)  # Description courte du type

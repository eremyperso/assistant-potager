"""
database/models.py — Modèles SQLAlchemy pour l'Assistant Potager
-----------------------------------------------------------------
[US-001] Ajout colonne type_organe_recolte sur Evenement
[US-001] Ajout modèle CultureConfig (table culture_config)
[US-040] Ajout socle multi-tenant (User, Potager, PotagerMembre) + potager_id
"""
from sqlalchemy import Column, Integer, BigInteger, String, Float, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database.db import Base


class User(Base):
    """[US-040] Utilisateur de la plateforme (compte web et/ou Telegram lié)."""
    __tablename__ = "users"

    id               = Column(Integer, primary_key=True, index=True)
    email            = Column(String(255), unique=True, nullable=True)
    telegram_chat_id = Column(BigInteger, unique=True, nullable=True)
    nom              = Column(String(100), nullable=True)
    cree_le          = Column(DateTime, server_default=func.now())


class Potager(Base):
    """[US-040] Un potager (jardin partagé) — le tenant de l'application."""
    __tablename__ = "potagers"

    id               = Column(Integer, primary_key=True, index=True)
    nom              = Column(String(100), nullable=False)
    latitude         = Column(Float, nullable=True)
    longitude        = Column(Float, nullable=True)
    proprietaire_id  = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan             = Column(String(20), default="free")
    cree_le          = Column(DateTime, server_default=func.now())


class PotagerMembre(Base):
    """[US-040] Appartenance d'un utilisateur à un potager, avec son rôle."""
    __tablename__ = "potager_membres"

    user_id    = Column(Integer, ForeignKey("users.id"), primary_key=True)
    potager_id = Column(Integer, ForeignKey("potagers.id"), primary_key=True)
    role       = Column(String(10), nullable=False)  # 'owner' | 'editor' | 'lecteur'


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
    # [migration_v12] colonne parcelle (texte dénormalisé) supprimée — parcelle_id est l'unique référence
    parcelle_id    = Column(Integer, ForeignKey("parcelles.id"), nullable=True, index=True)
    rang           = Column(Integer)   # [migration_v3] INTEGER (pas String)

    # Détails
    duree          = Column(Integer)
    traitement     = Column(String)
    commentaire    = Column(String)

    # Texte original dicté (+ traces [CORR ...])
    texte_original = Column(String)

    # [US-001] Classification agronomique héritée depuis culture_config
    # Valeurs : "végétatif" | "reproducteur" | null
    type_organe_recolte = Column(String, nullable=True)

    # [US_Enregistrer_mise_en_godet] Pépinière : nb graines semées → nb plants obtenus
    nb_graines_semees   = Column(Integer, nullable=True)
    nb_plants_godets    = Column(Integer, nullable=True)

    # [migration_v12] Traçabilité pépinière : événement source (semis → godet → plantation)
    origine_graines_id  = Column(Integer, ForeignKey("evenements.id", ondelete="SET NULL"), nullable=True)

    # [US-029] Chaînage plantation → godet(s) source (IDs séparés par ";" si multi-lots)
    source_evenement_ids = Column(String, nullable=True)

    # [US-040] Rattachement tenant — NULLABLE à ce stade (backfill = potager #1),
    # NOT NULL réservé à une US ultérieure de scoping applicatif
    potager_id = Column(Integer, ForeignKey("potagers.id"), nullable=True)

    # Relation vers la parcelle — permet d'accéder à e.parcelle_rel.nom
    parcelle_rel = relationship("Parcelle", foreign_keys=[parcelle_id])

    __table_args__ = (
        Index("idx_evenements_potager_date", "potager_id", "date"),
    )

    @property
    def parcelle(self) -> str | None:
        """Nom de la parcelle (compatibilité avec l'ancien champ texte dénormalisé)."""
        return self.parcelle_rel.nom if self.parcelle_rel else None


class CultureConfig(Base):
    """
    [US-001] Configuration des cultures avec leur type d'organe récolté.

    Permet de distinguer :
    - "végétatif"    : récolte destructive (salade, carotte, radis...)
                       → 1 récolte = 1 plant consommé/détruit
    - "reproducteur" : récolte continue (tomate, courgette, poivron...)
                       → la plante reste en vie, produit plusieurs fois
    """
    __tablename__ = "culture_config"

    id                      = Column(Integer, primary_key=True, index=True)
    nom                     = Column(String, unique=True, index=True, nullable=False)
    type_organe_recolte     = Column(String, nullable=False)   # "végétatif" | "reproducteur"
    description_agronomique = Column(String)
    espacement              = Column(String, nullable=True)    # ex: "30 × 40 cm"
    surface_m2              = Column(Float,  nullable=True)    # surface au sol par plant en m²

    # [US-040] NULL = fiche référentiel globale partagée entre potagers ;
    # non NULL = fiche personnalisée à un potager (le backfill ne force pas
    # cette colonne, contrairement aux tables purement métier)
    potager_id               = Column(Integer, ForeignKey("potagers.id"), nullable=True, index=True)


class Parcelle(Base):
    """
    [US_Plan_occupation_parcelles / CA8]
    Représente une parcelle physique du potager.

    - nom_normalise : forme canonique unique (strip + lower + unidecode + sans tirets/espaces)
    - ordre         : position pour l'affichage trié du plan
    - actif         : permet de désactiver sans supprimer
    - est_pepiniere : [migration_v13] une parcelle pépinière/serre n'est jamais comptée
                      comme "pleine terre" pour un semis, même avec un parcelle_id renseigné
                      (voir utils.stock._cond_semis_pleine_terre)
    """
    __tablename__ = "parcelles"

    id            = Column(Integer, primary_key=True, index=True)
    nom           = Column(String, nullable=False)
    nom_normalise = Column(String, unique=True, nullable=False, index=True)
    exposition    = Column(String, nullable=True)
    superficie_m2 = Column(Float, nullable=True)
    ordre         = Column(Integer, default=0)
    actif         = Column(Boolean, default=True, nullable=False)
    est_pepiniere = Column(Boolean, default=False, nullable=False)

    # [US-040] Rattachement tenant — NULLABLE à ce stade (backfill = potager #1)
    potager_id    = Column(Integer, ForeignKey("potagers.id"), nullable=True, index=True)

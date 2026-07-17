"""
app/services/parcelles.py — Requêtes Parcelle / CultureConfig [US-041]
-----------------------------------------------------------------------
Complète app/services/evenements.py pour les accès directs à `parcelles`
et `culture_config` qui ne portent pas sur Evenement. Les opérations de
haut niveau déjà isolées dans utils/parcelles.py (resolve_parcelle,
create_parcelle, calcul_occupation_parcelles...) restent appelées
directement — elles ne contiennent aucun db.query dispersé dans
bot.py/main.py, donc rien à centraliser de plus pour elles ici.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.services.context import TenantContext
from database.models import CultureConfig, Evenement, Parcelle


def get_parcelle(db: Session, ctx: TenantContext, parcelle_id: int) -> Optional[Parcelle]:
    return db.get(Parcelle, parcelle_id)


def lister_cultures_config(db: Session, ctx: TenantContext) -> list[CultureConfig]:
    """[GET /cultures] Toutes les fiches culture configurées, triées par nom."""
    return db.query(CultureConfig).order_by(CultureConfig.nom).all()


def get_culture_config(db: Session, ctx: TenantContext, nom: str) -> Optional[CultureConfig]:
    return db.query(CultureConfig).filter(CultureConfig.nom == nom).first()


def creer_culture_config(db: Session, ctx: TenantContext, nom: str, type_organe: str) -> CultureConfig:
    """[US-037 CA7] Crée une fiche culture minimale suite à la clarification végétatif/reproducteur."""
    cfg = CultureConfig(nom=nom, type_organe_recolte=type_organe)
    db.add(cfg)
    db.commit()
    return cfg


def parcelles_avec_culture(db: Session, ctx: TenantContext, culture: str, variete: Optional[str]) -> list[Parcelle]:
    """Parcelles actives distinctes où `culture` (+ variété optionnelle) a été plantée
    ou semée en pleine terre. Réutilise la condition de localisation d'evenements.py."""
    from app.services.evenements import _cond_localisation_culture

    q = (
        db.query(Parcelle)
        .join(Evenement, Evenement.parcelle_id == Parcelle.id)
        .filter(Parcelle.actif == True, _cond_localisation_culture(), Evenement.culture == culture)
    )
    if variete:
        q = q.filter(Evenement.variete == variete)
    return q.distinct().all()

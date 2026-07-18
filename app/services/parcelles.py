"""
app/services/parcelles.py — Requêtes Parcelle / CultureConfig [US-041 / US-042]
-----------------------------------------------------------------------
Complète app/services/evenements.py pour les accès directs à `parcelles`
et `culture_config` qui ne portent pas sur Evenement.

[US-042] Toutes les requêtes filtrent par ctx.potager_id. `culture_config`
reste un cas particulier : une fiche avec potager_id NULL est un
référentiel global partagé (US-040) — elle reste visible dans tous les
potagers, en plus des fiches propres au potager courant.
"""
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.services.context import TenantContext
from database.models import CultureConfig, Evenement, Parcelle


def get_parcelle(db: Session, ctx: TenantContext, parcelle_id: int) -> Optional[Parcelle]:
    parcelle = db.get(Parcelle, parcelle_id)
    if parcelle is None or parcelle.potager_id != ctx.potager_id:
        return None
    return parcelle


def lister_cultures_config(db: Session, ctx: TenantContext) -> list[CultureConfig]:
    """[GET /cultures] Toutes les fiches culture configurées (globales + propres au
    potager courant), triées par nom."""
    return (
        db.query(CultureConfig)
        .filter(or_(CultureConfig.potager_id == ctx.potager_id, CultureConfig.potager_id.is_(None)))
        .order_by(CultureConfig.nom)
        .all()
    )


def get_culture_config(db: Session, ctx: TenantContext, nom: str) -> Optional[CultureConfig]:
    return (
        db.query(CultureConfig)
        .filter(
            CultureConfig.nom == nom,
            or_(CultureConfig.potager_id == ctx.potager_id, CultureConfig.potager_id.is_(None)),
        )
        .first()
    )


def creer_culture_config(db: Session, ctx: TenantContext, nom: str, type_organe: str) -> CultureConfig:
    """[US-037 CA7] Crée une fiche culture minimale suite à la clarification végétatif/reproducteur.
    [US-042] Rattachée au potager courant (fiche personnalisée, pas globale)."""
    cfg = CultureConfig(nom=nom, type_organe_recolte=type_organe, potager_id=ctx.potager_id)
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
        .filter(
            Parcelle.actif == True,
            Parcelle.potager_id == ctx.potager_id,
            Evenement.potager_id == ctx.potager_id,
            _cond_localisation_culture(ctx.potager_id),
            Evenement.culture == culture,
        )
    )
    if variete:
        q = q.filter(Evenement.variete == variete)
    return q.distinct().all()

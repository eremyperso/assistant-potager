"""
app/services/plan.py — Plan d'occupation des parcelles [US-041 / CA6]
-------------------------------------------------------------------------
Enveloppe tenant autour de utils/parcelles.calcul_occupation_parcelles()
et get_all_parcelles(), déjà isolées. Ajoute l'index surface_m2 par
culture (auparavant un db.query(CultureConfig) direct dans main.py /plan).
"""
from datetime import date as _date
from typing import Optional

from sqlalchemy.orm import Session

from app.services.context import TenantContext
from app.services.parcelles import lister_cultures_config
from database.models import Parcelle
import utils.parcelles as _parcelles_mod


def get_parcelles(db: Session, ctx: TenantContext) -> list[Parcelle]:
    # Appel qualifié (pas d'import direct de la fonction) pour que les patches de
    # test sur utils.parcelles.get_all_parcelles restent effectifs.
    return _parcelles_mod.get_all_parcelles(db)


def get_occupation(db: Session, ctx: TenantContext, date_ref: Optional[_date] = None) -> dict:
    return _parcelles_mod.calcul_occupation_parcelles(db, date_ref)


def surface_par_culture(db: Session, ctx: TenantContext) -> dict[str, float]:
    """[GET /plan] Index surface_m2 par nom de culture (insensible à la casse)."""
    configs = lister_cultures_config(db, ctx)
    return {c.nom.lower(): (c.surface_m2 or 0.0) for c in configs}

"""
app/services/stock.py — Enveloppe tenant autour de utils/stock.py [US-041 / CA5]
-----------------------------------------------------------------------------------
utils/stock.py est déjà isolé (aucune dépendance à bot.py/main.py) et ne fait
aucun accès direct db.query hors de ses propres fonctions : ce module se
contente d'exposer les mêmes fonctions derrière une signature acceptant
`ctx: TenantContext`, pour que bot.py et main.py n'appellent plus jamais
utils/stock.py directement.
"""
from datetime import date as _date
from typing import Optional

from sqlalchemy.orm import Session

from app.services.context import TenantContext
from utils import stock as _stock


def calcul_stock_cultures(db: Session, ctx: TenantContext, date_ref: Optional[_date] = None):
    return _stock.calcul_stock_cultures(db, date_ref)


def calcul_semis(db: Session, ctx: TenantContext, date_ref: Optional[_date] = None):
    return _stock.calcul_semis(db, date_ref)


def calcul_semis_par_culture(db: Session, ctx: TenantContext, culture: str, date_ref: Optional[_date] = None):
    return _stock.calcul_semis_par_culture(db, culture, date_ref)


def calcul_godets(db: Session, ctx: TenantContext, include_epuises: bool = False, date_ref: Optional[_date] = None):
    return _stock.calcul_godets(db, include_epuises, date_ref)


def calcul_godets_par_culture(db: Session, ctx: TenantContext, culture: str, date_ref: Optional[_date] = None):
    return _stock.calcul_godets_par_culture(db, culture, date_ref)


def calcul_stock_par_variete(db: Session, ctx: TenantContext, culture: str, date_ref: Optional[_date] = None):
    return _stock.calcul_stock_par_variete(db, culture, date_ref)


def calcul_rendement_mensuel(db: Session, ctx: TenantContext, annee: int, date_ref: Optional[_date] = None):
    return _stock.calcul_rendement_mensuel(db, annee, date_ref)


def calcul_activite_quotidienne(db: Session, ctx: TenantContext, annee: int, date_ref: Optional[_date] = None):
    return _stock.calcul_activite_quotidienne(db, annee, date_ref)


def get_type_organe(db: Session, ctx: TenantContext, culture: str) -> Optional[str]:
    return _stock.get_type_organe(db, culture)

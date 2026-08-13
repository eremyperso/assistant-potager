"""
app/services/stock.py — Enveloppe tenant autour de utils/stock.py [US-041 / CA5, US-042]
-----------------------------------------------------------------------------------
[US-042] utils/stock.py accepte désormais un paramètre `potager_id` optionnel sur
chacune de ses fonctions (None = comportement historique non scopé, réservé aux
tests unitaires directs de utils/). Ce module transmet systématiquement
`ctx.potager_id` — c'est le seul point d'entrée applicatif vers utils/stock.py.
"""
from datetime import date as _date
from typing import Optional

from sqlalchemy.orm import Session

from app.services.context import TenantContext
from utils import stock as _stock


def calcul_stock_cultures(db: Session, ctx: TenantContext, date_ref: Optional[_date] = None):
    return _stock.calcul_stock_cultures(db, date_ref, potager_id=ctx.potager_id)


def calcul_semis(db: Session, ctx: TenantContext, date_ref: Optional[_date] = None):
    return _stock.calcul_semis(db, date_ref, potager_id=ctx.potager_id)


def calcul_semis_par_culture(db: Session, ctx: TenantContext, culture: str, date_ref: Optional[_date] = None):
    return _stock.calcul_semis_par_culture(db, culture, date_ref, potager_id=ctx.potager_id)


def calcul_godets(db: Session, ctx: TenantContext, include_epuises: bool = False, date_ref: Optional[_date] = None):
    return _stock.calcul_godets(db, include_epuises, date_ref, potager_id=ctx.potager_id)


def calcul_lots_pepiniere(db: Session, ctx: TenantContext, date_ref: Optional[_date] = None):
    """[US-065] Lecture de la pépinière par lot de semis — s'ajoute à calcul_godets(),
    dont le contrat agrégé par culture + variété reste inchangé (CA5)."""
    return _stock.calcul_lots_pepiniere(db, date_ref, potager_id=ctx.potager_id)


def lots_candidats_mise_en_godet(
    db: Session, ctx: TenantContext, culture: str, variete: Optional[str] = None,
    date_ref: Optional[_date] = None, graines_requises: int = 0,
):
    """[fix rattachement lot godet] Lots de semis pouvant encore recevoir une mise en godet."""
    return _stock.lots_candidats_mise_en_godet(
        db, culture, variete, date_ref, potager_id=ctx.potager_id,
        graines_requises=graines_requises,
    )


def lot_pepiniere_par_semis(db: Session, ctx: TenantContext, semis_id: int, date_ref: Optional[_date] = None):
    """[US-066] État d'un lot désigné par son semis — sert à rappeler au jardinier
    combien de graines y restent non soldées."""
    return _stock.lot_pepiniere_par_semis(db, semis_id, date_ref, potager_id=ctx.potager_id)


def calcul_godets_par_culture(db: Session, ctx: TenantContext, culture: str, date_ref: Optional[_date] = None):
    return _stock.calcul_godets_par_culture(db, culture, date_ref, potager_id=ctx.potager_id)


def calcul_stock_par_variete(db: Session, ctx: TenantContext, culture: str, date_ref: Optional[_date] = None):
    return _stock.calcul_stock_par_variete(db, culture, date_ref, potager_id=ctx.potager_id)


def calcul_rendement_mensuel(db: Session, ctx: TenantContext, annee: int, date_ref: Optional[_date] = None):
    return _stock.calcul_rendement_mensuel(db, annee, date_ref, potager_id=ctx.potager_id)


def calcul_activite_quotidienne(db: Session, ctx: TenantContext, annee: int, date_ref: Optional[_date] = None):
    return _stock.calcul_activite_quotidienne(db, annee, date_ref, potager_id=ctx.potager_id)


def get_type_organe(db: Session, ctx: TenantContext, culture: str) -> Optional[str]:
    return _stock.get_type_organe(db, culture, potager_id=ctx.potager_id)

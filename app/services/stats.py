"""
app/services/stats.py — Agrégation des statistiques potager [US-041 / CA4]
-------------------------------------------------------------------------------
Calcule une fois les agrégats bruts (stock, godets, semis pleine terre,
traitements, cultures avec godet) ; GET /stats (main.py) les sérialise en
JSON, cmd_stats (bot.py) les formate en texte Telegram — zéro duplication
de la logique de calcul entre les deux.
"""
from dataclasses import dataclass, field
from datetime import date as _date
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.services import evenements as _evenements
from app.services import stock as _stock
from app.services.context import TenantContext


@dataclass
class StatsResult:
    date_ref_effective: _date
    total_evenements: int
    stocks: dict = field(default_factory=dict)
    godets: dict = field(default_factory=dict)
    semis: dict = field(default_factory=dict)
    traitements: List[Tuple[Optional[str], int]] = field(default_factory=list)
    cultures_avec_godet: set = field(default_factory=set)


def calculer_stats(db: Session, ctx: TenantContext, date_ref: Optional[_date] = None) -> StatsResult:
    """[GET /stats, /stats] Calcule l'ensemble des agrégats statistiques du potager.
    `date_ref` reconstitue l'état à une date passée (US-030) — None = comportement par défaut."""
    today = _date.today()
    dr = min(date_ref, today) if date_ref else None
    date_ref_effective = dr or today

    total = _evenements.compter_evenements(db, ctx, jusqua=dr)
    stocks = _stock.calcul_stock_cultures(db, ctx, dr)
    godets = _stock.calcul_godets(db, ctx, date_ref=dr)
    semis = _stock.calcul_semis(db, ctx, dr)
    traitements = _evenements.traitements_appliques(db, ctx)
    cultures_avec_godet = _evenements.cultures_avec_mise_en_godet(db, ctx)

    return StatsResult(
        date_ref_effective=date_ref_effective,
        total_evenements=total,
        stocks=stocks,
        godets=godets,
        semis=semis,
        traitements=traitements,
        cultures_avec_godet=cultures_avec_godet,
    )

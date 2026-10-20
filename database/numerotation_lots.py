"""
database/numerotation_lots.py — Numéro court des lots de pépinière [US-209 / CA1-CA4]
------------------------------------------------------------------------------------
Un semis en pépinière forme un lot ; il reçoit un numéro entier, unique dans son
potager, attribué dans l'ordre de création à partir de 1 et jamais réutilisé.

Le numéro est posé par un écouteur `before_flush` : TOUS les chemins d'écriture
(saisie bot, API, correction, import) y passent, dans la transaction du semis
(CA2). Le prochain numéro se prend par `UPDATE potagers SET compteur_lots =
compteur_lots + 1` : la ligne du potager est verrouillée jusqu'au commit, deux
semis simultanés ne peuvent donc pas obtenir le même numéro, et le compteur ne
recule jamais — supprimer un semis ne libère pas son numéro.

Ensemble numéroté = ensemble de `GET /pepiniere/lots` : un semis dont la parcelle
est absente ou marquée pépinière, avec une culture, et dont la filière n'est pas
déclarée « pleine terre ». Un semis corrigé en pleine terre GARDE son numéro
(CA4) ; corrigé dans l'autre sens, il en reçoit un s'il n'en avait pas.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

log = logging.getLogger("potager")

CONTEXTE_PLEINE_TERRE = "pleine_terre"
_POTAGER_PAR_DEFAUT = 1   # = default de Evenement.potager_id


def est_lot_de_pepiniere(session: Session, evenement) -> bool:
    """[US-209 / CA1] Ce semis fait-il partie des lots de pépinière ?"""
    from database.models import Parcelle

    if evenement.type_action != "semis" or not evenement.culture:
        return False
    if evenement.contexte_semis == CONTEXTE_PLEINE_TERRE:
        return False
    parcelle = evenement.parcelle_rel
    if parcelle is None and evenement.parcelle_id is not None:
        parcelle = session.get(Parcelle, evenement.parcelle_id)
    return parcelle is None or bool(parcelle.est_pepiniere)


def _numero_suivant(session: Session, potager_id: int, deja_pris: dict) -> int:
    from database.models import Evenement, Potager

    table = Potager.__table__
    res = session.execute(
        table.update().where(table.c.id == potager_id)
        .values(compteur_lots=table.c.compteur_lots + 1)
    )
    if res.rowcount:
        numero = session.execute(
            select(table.c.compteur_lots).where(table.c.id == potager_id)
        ).scalar_one()
    else:
        # Aucune ligne potager (fixtures, scripts) : repli sur le plus grand numéro connu.
        base = session.execute(
            select(func.max(Evenement.numero_lot)).where(Evenement.potager_id == potager_id)
        ).scalar() or 0
        numero = max(base, deja_pris.get(potager_id, 0)) + 1
    deja_pris[potager_id] = numero
    return numero


@event.listens_for(Session, "before_flush")
def _attribuer_numeros_de_lot(session: Session, flush_context, instances) -> None:
    from database.models import Evenement

    candidats = [
        o for o in list(session.new) + list(session.dirty)
        if isinstance(o, Evenement) and o.type_action == "semis" and o.numero_lot is None
    ]
    if not candidats:
        return
    deja_pris: dict = {}
    with session.no_autoflush:
        for o in candidats:
            if not est_lot_de_pepiniere(session, o):
                continue
            pid = o.potager_id if o.potager_id is not None else _POTAGER_PAR_DEFAUT
            o.numero_lot = _numero_suivant(session, pid, deja_pris)
            log.info("[US-209] Semis → lot n° %s (potager %s)", o.numero_lot, pid)

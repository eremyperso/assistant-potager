"""
app/services/alerte_recolte.py — Récolte imminente selon l'âge et l'organe récolté
==================================================================================
[US_Plan_occupation_parcelles / CA3] Une culture en place dont l'âge dépasse le
seuil typique de son organe récolté est signalée « récolte imminente ».

[US-266 / CA4] Déplacé de `app/bot/commandes_plan.py`, sans changement de
comportement : le `/plan` du bot et le veilleur du compagnon lisent la même règle.
"""
from __future__ import annotations

from typing import Optional

#: [US_Plan_occupation_parcelles / CA3] Seuils d'alerte par type d'organe (jours).
SEUIL_ALERTE: dict[str, int] = {"végétatif": 45, "reproducteur": 90}


def alerte_recolte(type_organe: Optional[str], age_jours: int) -> bool:
    """[CA3] Retourne True si la culture dépasse le seuil d'alerte."""
    if type_organe and type_organe in SEUIL_ALERTE:
        return age_jours >= SEUIL_ALERTE[type_organe]
    return False

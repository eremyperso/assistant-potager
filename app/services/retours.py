"""
app/services/retours.py — Retour du jardinier sur une réponse [US-097]
========================================================================
[CA9] Toute réponse issue du savoir ou du raisonnement (étages 2 et 3) propose
un retour 👍 / 👎. Ce module porte l'écriture de cet avis, rattaché à l'entrée
de journal (`routage_logs`) qui a produit la réponse (CA10).

[CA11] Un avis est facultatif, ne bloque rien, et n'est jamais redemandé pour
la même réponse : la contrainte UNIQUE sur `routage_retours.routage_log_id`
(migration_v32) est l'application concrète de cette règle, pas seulement une
convention côté interface.

[CA13] Ce module n'appelle jamais un modèle : recevoir un avis négatif n'est
pas une invitation à dépenser davantage, c'est une information de pilotage.
"""
from __future__ import annotations

import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models import RoutageLog, RoutageRetour

log = logging.getLogger("potager")

AVIS_POSITIF = "positif"
AVIS_NEGATIF = "negatif"
AVIS_VALIDES: frozenset[str] = frozenset({AVIS_POSITIF, AVIS_NEGATIF})


class RetourError(Exception):
    """Racine des erreurs de retour du jardinier."""


class RoutageLogIntrouvableError(RetourError):
    """L'entrée de journal ciblée n'existe pas, ou n'appartient pas à ce
    potager (isolation inter-potagers, invariant projet)."""


class RetourDejaEnregistreError(RetourError):
    """[CA11] Un avis existe déjà pour cette entrée de journal."""


def enregistrer_retour(db: Session, potager_id: int, routage_log_id: int, avis: str) -> RoutageRetour:
    """[CA9, CA10, CA11] Enregistre l'avis du jardinier sur une réponse déjà
    servie.

    Lève `RoutageLogIntrouvableError` si l'entrée n'existe pas pour ce potager,
    `RetourDejaEnregistreError` si un avis existe déjà. Aucun appel modèle
    n'est déclenché ici, quel que soit l'avis (CA13).
    """
    if avis not in AVIS_VALIDES:
        raise ValueError(f"avis invalide : {avis!r} (attendu parmi {sorted(AVIS_VALIDES)})")

    entree = (
        db.query(RoutageLog)
        .filter(RoutageLog.id == routage_log_id, RoutageLog.potager_id == potager_id)
        .first()
    )
    if entree is None:
        raise RoutageLogIntrouvableError(
            f"routage_log {routage_log_id} introuvable pour le potager {potager_id}"
        )

    retour = RoutageRetour(routage_log_id=routage_log_id, potager_id=potager_id, avis=avis)
    db.add(retour)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise RetourDejaEnregistreError(
            f"un avis existe déjà pour routage_log {routage_log_id}"
        )
    db.refresh(retour)
    return retour

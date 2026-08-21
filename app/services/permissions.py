"""
app/services/permissions.py — Garde de rôle centralisé [US-047]
-----------------------------------------------------------------------
Matrice de permissions unique (lecteur < editor < owner) : point d'appel
unique `require_role()`, réutilisé aussi bien par les services d'écriture
(app/services/evenements.py, défense en profondeur) que par bot.py/main.py
(garde précoce, avant tout appel de parsing LLM — CA4). La logique de
comparaison des rôles ne vit qu'ici, jamais recopiée ailleurs (CA6).

[US-083 / CA4] `require_potager_non_archive` suit le même principe (logique
centralisée dans ce module, appelée par la couche services partout où un
événement s'écrit) mais reste une fonction distincte de `require_role` : un
potager archivé doit rester désarchivable, un garde fusionné dans
`require_role` bloquerait `desarchiver_potager` lui-même, qui appelle aussi
`require_role(ctx, "owner", ...)`.
"""
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.services.context import TenantContext

log = logging.getLogger("potager")

# [US-047] Rôles ordonnés par niveau croissant de droits.
NIVEAUX_ROLE = {"lecteur": 0, "editor": 1, "owner": 2}


class PermissionInsuffisanteError(Exception):
    """[CA1, CA2, CA3] Le rôle du membre n'atteint pas le rôle minimum requis
    pour l'action demandée. Message identique bot/PWA (CA5) — l'appelant n'a
    qu'à afficher `str(exception)` à l'utilisateur."""

    def __init__(self, role_actuel: Optional[str], action_label: str):
        self.role_actuel = role_actuel
        self.action_label = action_label
        libelle_role = role_actuel or "sans rôle"
        super().__init__(
            f"Tu es {libelle_role} sur ce potager, tu ne peux pas {action_label}."
        )


def require_role(ctx: TenantContext, role_minimum: str, action_label: str = "effectuer cette action") -> None:
    """[CA1, CA2, CA3, CA6] Garde unique : lève `PermissionInsuffisanteError` si le
    rôle courant (`ctx.role`) n'atteint pas `role_minimum`. Ne lève jamais d'autre
    exception — une tentative refusée est simplement journalisée (CA7) puis
    remontée sous une forme que bot.py/main.py savent traduire en message
    utilisateur, sans dupliquer la logique de comparaison des rôles.
    """
    niveau_requis = NIVEAUX_ROLE[role_minimum]
    niveau_actuel = NIVEAUX_ROLE.get(ctx.role or "", -1)
    if niveau_actuel < niveau_requis:
        log.warning(
            "[US-047] Permission refusée : user_id=%s potager_id=%s role=%s requis=%s action=%r",
            ctx.user_id, ctx.potager_id, ctx.role, role_minimum, action_label,
        )
        raise PermissionInsuffisanteError(ctx.role, action_label)


class PotagerArchiveError(Exception):
    """[US-083 / CA4] Le potager est archivé (lecture seule) : l'écriture demandée
    est refusée jusqu'à désarchivage. Message identique bot/PWA (CA4), comme
    `PermissionInsuffisanteError` — l'appelant se contente d'afficher `str(...)`."""

    def __init__(self, action_label: str = "effectuer cette action"):
        self.action_label = action_label
        super().__init__(
            f"Ce potager est archivé (lecture seule), tu ne peux pas {action_label}. "
            "Désarchive-le depuis « Paramètres du potager » pour y écrire à nouveau."
        )


def require_potager_non_archive(db: Session, ctx: TenantContext, action_label: str = "effectuer cette action") -> None:
    """[US-083 / CA4] Garde d'écriture : lève `PotagerArchiveError` si le potager
    ciblé par `ctx` est archivé. Nécessite une requête DB (l'état du potager ne
    fait pas partie de `TenantContext`) — appelée une seule fois par écriture
    dans la couche services (app/services/evenements.py), jamais dupliquée par
    endpoint bot/API (ceux-ci se contentent de traduire l'exception en message)."""
    from app.services.potager_actif import ETAT_ARCHIVE
    from database.models import Potager

    potager = db.query(Potager).filter(Potager.id == ctx.potager_id).first()
    if potager is not None and potager.etat == ETAT_ARCHIVE:
        log.warning(
            "[US-083] Écriture refusée (potager archivé) : user_id=%s potager_id=%s action=%r",
            ctx.user_id, ctx.potager_id, action_label,
        )
        raise PotagerArchiveError(action_label)

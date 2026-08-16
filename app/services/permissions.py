"""
app/services/permissions.py — Garde de rôle centralisé [US-047]
-----------------------------------------------------------------------
Matrice de permissions unique (lecteur < editor < owner) : point d'appel
unique `require_role()`, réutilisé aussi bien par les services d'écriture
(app/services/evenements.py, défense en profondeur) que par bot.py/main.py
(garde précoce, avant tout appel de parsing LLM — CA4). La logique de
comparaison des rôles ne vit qu'ici, jamais recopiée ailleurs (CA6).
"""
import logging
from typing import Optional

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

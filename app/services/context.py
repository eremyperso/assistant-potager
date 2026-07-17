"""
app/services/context.py — Contexte tenant partagé bot ⇄ PWA [US-041]
-----------------------------------------------------------------------
Toute fonction de app/services/ prend un TenantContext en premier
paramètre après la session DB. Objectif : coder l'isolation par potager
une seule fois, plus tard (voir US-042), au lieu de la dupliquer entre
bot.py et main.py.

⚠️ Cette US ne fait pas le scoping applicatif (filtre potager_id sur les
requêtes) : c'est le périmètre de US-042. TenantContext existe déjà pour
que les signatures de services n'aient pas à changer quand le scoping
sera ajouté.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TenantContext:
    """Identité + tenant courant pour un appel de service.

    role : 'owner' | 'editor' | 'lecteur' | None (rôles réels introduits par US-113)
    """
    user_id: Optional[int]
    potager_id: int
    role: Optional[str] = None


# [US-041] Pendant la transition (avant US-110/US-112 authentification web +
# sélection du potager actif), tous les appelants utilisent le potager #1 /
# user #1 issus du backfill US-040. À supprimer dès que le contexte réel
# (utilisateur authentifié, potager actif) est disponible.
DEFAULT_POTAGER_ID = 1
DEFAULT_USER_ID = 1


def default_context() -> TenantContext:
    """Contexte tenant temporaire — potager #1 en dur (transition US-040 → US-110/112)."""
    return TenantContext(user_id=DEFAULT_USER_ID, potager_id=DEFAULT_POTAGER_ID, role="owner")

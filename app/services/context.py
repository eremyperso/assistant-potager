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
import contextvars
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


# ─────────────────────────────────────────────────────────────────────────────
# [US-046] TenantContext réel résolu une fois par requête/Update
# -----------------------------------------------------------------------------
# `bot.py` appelle historiquement default_context() dans des dizaines de
# fonctions utilitaires qui ne reçoivent pas toutes le `ctx` Telegram en
# paramètre — plutôt que de re-threader `ctx` partout, on suit exactement le
# même principe que `database.db.current_potager_id` (contextvar RLS, US-043) :
# le garde de liaison (bot.py::_verifier_liaison_ou_onboarding) résout le
# TenantContext réel UNE SEULE FOIS par Update et l'arme ici via
# set_current_context() ; tout le code appelé dans la foulée (même hors
# handlers, sans `ctx` en paramètre) le relit via current_context() au lieu de
# default_context(). PTB v20 traite tous les groupes de handlers d'un même
# Update dans une seule Task asyncio, donc le contextvar reste visible pour
# tout le traitement de cet Update sans fuite entre Updates concurrents.
#
# Côté web (main.py), ce mécanisme n'est PAS utilisé : chaque endpoint reçoit
# déjà son TenantContext explicitement via Depends(get_current_user_ctx).
# -----------------------------------------------------------------------------
_current_context: "contextvars.ContextVar[Optional[TenantContext]]" = contextvars.ContextVar(
    "current_tenant_context", default=None
)


def set_current_context(ctx: TenantContext) -> None:
    """[US-046] Arme le TenantContext résolu pour le reste du traitement de l'Update courant."""
    _current_context.set(ctx)


def current_context() -> TenantContext:
    """[US-046] TenantContext résolu pour l'Update en cours (potager actif réel).
    Retombe sur default_context() si rien n'a été armé (commandes d'onboarding
    exemptées du garde — /start, /help, /lier — ou tests unitaires existants)."""
    ctx = _current_context.get()
    return ctx if ctx is not None else default_context()

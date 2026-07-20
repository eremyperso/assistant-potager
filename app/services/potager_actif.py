"""
app/services/potager_actif.py — Sélection du potager actif [US-046]
-------------------------------------------------------------------------------
Résout le TenantContext réel (potager actif + rôle) d'un utilisateur à partir
de `potager_membres` et `users.potager_actif_id`, et permet de le changer
explicitement (bot `/potager`, sélecteur PWA).

⚠️ Comme app/services/auth.py et liaison_telegram.py, ce module ne prend pas
TenantContext en paramètre : c'est justement lui qui le produit.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.services.context import TenantContext
from database.models import Potager, PotagerMembre, User


class AucunPotagerError(Exception):
    """[CA5] L'utilisateur n'est membre d'aucun potager."""


class PotagerNonMembreError(Exception):
    """[CA2] Tentative de sélection d'un potager dont l'utilisateur n'est pas membre."""


def lister_potagers_utilisateur(db: Session, user_id: int) -> list[Potager]:
    """[CA2] Potagers dont l'utilisateur est membre, triés par id (ordre stable)."""
    return (
        db.query(Potager)
        .join(PotagerMembre, PotagerMembre.potager_id == Potager.id)
        .filter(PotagerMembre.user_id == user_id)
        .order_by(Potager.id)
        .all()
    )


def _role_utilisateur(db: Session, user_id: int, potager_id: int) -> Optional[str]:
    membre = (
        db.query(PotagerMembre)
        .filter(PotagerMembre.user_id == user_id, PotagerMembre.potager_id == potager_id)
        .first()
    )
    return membre.role if membre else None


def resoudre_tenant_context(db: Session, user_id: int) -> TenantContext:
    """[CA1, CA5, CA6] Résout le TenantContext réel d'un utilisateur.

    - Potager actif déjà choisi et toujours valide → utilisé tel quel.
    - Un seul potager, aucun choix encore fait → sélection automatique
      silencieuse, persistée (CA1).
    - Plusieurs potagers, aucun choix encore fait → potager par défaut
      transitoire (le premier, non persisté) — l'utilisateur choisit
      explicitement via /potager ou le sélecteur PWA (CA2) pour changer.
    - Aucun potager → AucunPotagerError (CA5).
    """
    user = db.query(User).filter(User.id == user_id).first()
    potagers = lister_potagers_utilisateur(db, user_id)
    if not potagers:
        raise AucunPotagerError("Aucun potager associé à cet utilisateur")

    potagers_par_id = {p.id: p for p in potagers}

    if user.potager_actif_id is not None and user.potager_actif_id in potagers_par_id:
        potager_id = user.potager_actif_id
    elif len(potagers) == 1:
        potager_id = potagers[0].id
        user.potager_actif_id = potager_id  # [CA1] persisté silencieusement
        db.commit()
    else:
        potager_id = potagers[0].id  # défaut transitoire, non persisté (CA2 attend un choix explicite)

    role = _role_utilisateur(db, user_id, potager_id)
    return TenantContext(user_id=user_id, potager_id=potager_id, role=role)


def definir_potager_actif(db: Session, user_id: int, potager_id: int) -> TenantContext:
    """[CA2, CA3, CA4] Change explicitement le potager actif — persisté."""
    role = _role_utilisateur(db, user_id, potager_id)
    if role is None:
        raise PotagerNonMembreError("Cet utilisateur n'est pas membre de ce potager")

    user = db.query(User).filter(User.id == user_id).first()
    user.potager_actif_id = potager_id
    db.commit()

    return TenantContext(user_id=user_id, potager_id=potager_id, role=role)

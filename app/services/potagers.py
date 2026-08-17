"""
app/services/potagers.py — Création de potager & invitations self-service [US-048]
--------------------------------------------------------------------------------
Referme le parcours de l'ÉPIC 2 : création d'un potager (CA1/CA2), invitation
d'un membre par code à usage unique (CA3/CA8, même principe que
liaison_telegram.py / US-045), acceptation (CA4) et retrait (CA5/CA6).

⚠️ Comme auth.py / liaison_telegram.py, `creer_potager` et `accepter_invitation`
ne prennent pas TenantContext en paramètre : ils s'exécutent avant/en dehors
d'un potager résolu. `creer_invitation`/`retirer_membre` visent un potager
explicite (potager_id de l'URL), pas nécessairement le potager actif de
l'appelant — le TenantContext est donc construit ici, ciblé sur ce potager,
via `potager_actif.role_utilisateur`, puis passé à `require_role`.
"""
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.services.context import TenantContext
from app.services.permissions import require_role
from app.services import potager_actif as svc_potager_actif
from database.models import Invitation, Potager, PotagerMembre, User

log = logging.getLogger("potager")

# Même alphabet que liaison_telegram.py — sans caractères ambigus (0/O, 1/I/l)
_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
_LONGUEUR_CODE = 8
_TTL_JOURS = 7
_ROLES_INVITABLES = {"editor", "lecteur"}


class RoleInvalideError(Exception):
    """[CA3] Le rôle proposé n'est ni 'editor' ni 'lecteur'."""


class InvitationInvalideError(Exception):
    """[CA8] Code d'invitation inconnu."""


class InvitationExpireeError(Exception):
    """[CA8] Invitation générée il y a plus de son délai de validité."""


class InvitationDejaUtiliseeError(Exception):
    """[CA8] Invitation déjà acceptée."""


class DejaMembreError(Exception):
    """L'utilisateur qui accepte est déjà membre de ce potager."""


class MembreInconnuError(Exception):
    """[CA5] Tentative de retrait d'un utilisateur qui n'est pas membre du potager."""


def _generer_code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(_LONGUEUR_CODE))


def _ctx_pour_potager(db: Session, user_id: int, potager_id: int) -> TenantContext:
    role = svc_potager_actif.role_utilisateur(db, user_id, potager_id)
    return TenantContext(user_id=user_id, potager_id=potager_id, role=role)


def creer_potager(
    db: Session,
    user_id: int,
    nom: str,
    ville: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> Potager:
    """[CA1, CA2] Crée un potager — l'utilisateur en devient owner et ce potager
    devient immédiatement son potager actif. La localisation est simplement
    capturée et stockée (alimente la météo par potager, US-074/US-075).

    [US-074] `ville` est le libellé choisi par l'utilisateur dans le module de
    recherche de ville (géocodage Open-Meteo côté frontend) — jamais recalculé
    côté serveur."""
    potager = Potager(nom=nom, ville=ville, latitude=latitude, longitude=longitude, proprietaire_id=user_id)
    db.add(potager)
    db.commit()
    db.refresh(potager)

    db.add(PotagerMembre(user_id=user_id, potager_id=potager.id, role="owner"))
    user = db.query(User).filter(User.id == user_id).first()
    user.potager_actif_id = potager.id
    db.commit()

    log.info("[US-048] Potager créé : potager_id=%s nom=%r owner_id=%s", potager.id, nom, user_id)
    return potager


def modifier_potager(
    db: Session,
    user_id: int,
    potager_id: int,
    nom: Optional[str] = None,
    ville: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> Potager:
    """[US-074 / CA4] Un owner corrige nom/ville/localisation d'un potager déjà
    créé — seul moyen de localiser un potager créé avant l'existence de cette
    fonctionnalité (CA6 : rien n'est jamais réécrit à une valeur inventée, un
    paramètre omis (`None`) laisse la colonne existante inchangée)."""
    ctx = _ctx_pour_potager(db, user_id, potager_id)
    require_role(ctx, "owner", "modifier le potager")

    potager = db.query(Potager).filter(Potager.id == potager_id).first()
    if nom is not None:
        potager.nom = nom
    if ville is not None:
        potager.ville = ville
    if latitude is not None:
        potager.latitude = latitude
    if longitude is not None:
        potager.longitude = longitude
    db.commit()
    db.refresh(potager)

    log.info("[US-074] Potager modifié : potager_id=%s par=%s", potager_id, user_id)
    return potager


def creer_invitation(
    db: Session, user_id: int, potager_id: int, role_propose: str, email_invite: Optional[str] = None
) -> Invitation:
    """[CA3] Un owner invite un membre par code, avec un rôle proposé."""
    ctx = _ctx_pour_potager(db, user_id, potager_id)
    require_role(ctx, "owner", "inviter un membre")

    if role_propose not in _ROLES_INVITABLES:
        raise RoleInvalideError("Le rôle proposé doit être 'editor' ou 'lecteur'")

    maintenant = datetime.utcnow()
    code = _generer_code()
    while db.query(Invitation).filter(Invitation.code == code).first() is not None:
        code = _generer_code()

    invitation = Invitation(
        code=code,
        potager_id=potager_id,
        invite_par_id=user_id,
        email_invite=email_invite,
        role_propose=role_propose,
        expire_le=maintenant + timedelta(days=_TTL_JOURS),
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)

    log.info(
        "[US-048] Invitation créée : potager_id=%s role=%s invite_par=%s",
        potager_id, role_propose, user_id,
    )
    return invitation


def accepter_invitation(db: Session, user_id: int, code: str) -> PotagerMembre:
    """[CA4, CA8] Valide un code d'invitation et rattache l'utilisateur au potager
    avec le rôle proposé. Sélectionne ce potager comme potager actif si
    l'utilisateur n'en avait encore aucun."""
    invitation = db.query(Invitation).filter(Invitation.code == code.strip().upper()).first()
    if invitation is None:
        raise InvitationInvalideError("Code d'invitation inconnu")

    if invitation.utilisee_le is not None:
        raise InvitationDejaUtiliseeError("Cette invitation a déjà été utilisée")

    if datetime.utcnow() > invitation.expire_le:
        raise InvitationExpireeError("Cette invitation a expiré")

    deja_membre = (
        db.query(PotagerMembre)
        .filter(PotagerMembre.user_id == user_id, PotagerMembre.potager_id == invitation.potager_id)
        .first()
    )
    if deja_membre is not None:
        raise DejaMembreError("Vous êtes déjà membre de ce potager")

    membre = PotagerMembre(user_id=user_id, potager_id=invitation.potager_id, role=invitation.role_propose)
    db.add(membre)

    invitation.utilisee_le = datetime.utcnow()

    user = db.query(User).filter(User.id == user_id).first()
    if user.potager_actif_id is None:
        user.potager_actif_id = invitation.potager_id

    db.commit()
    log.info(
        "[US-048] Invitation acceptée : potager_id=%s user_id=%s role=%s",
        invitation.potager_id, user_id, invitation.role_propose,
    )
    return membre


def lister_membres(db: Session, potager_id: int) -> list[dict]:
    """Membres d'un potager (email, nom, rôle), triés par id utilisateur.

    [US-055] `nom` ajouté (colonne déjà existante sur `User`, aucune migration)
    pour que le menu Compte affiche un nom plutôt qu'un e-mail brut, à l'image
    de GET /auth/me qui l'expose déjà pour le compte connecté.
    """
    rows = (
        db.query(PotagerMembre, User)
        .join(User, User.id == PotagerMembre.user_id)
        .filter(PotagerMembre.potager_id == potager_id)
        .order_by(User.id)
        .all()
    )
    return [{"user_id": u.id, "email": u.email, "nom": u.nom, "role": m.role} for m, u in rows]


def retirer_membre(db: Session, user_id: int, potager_id: int, membre_user_id: int) -> None:
    """[CA5, CA6] Un owner retire un membre — celui-ci perd l'accès immédiatement :
    si ce potager était son potager actif, il est invalidé (l'utilisateur retiré
    reçoit alors un 409 'aucun potager' au prochain accès, cf. get_current_user_ctx)."""
    ctx = _ctx_pour_potager(db, user_id, potager_id)
    require_role(ctx, "owner", "retirer un membre")

    membre = (
        db.query(PotagerMembre)
        .filter(PotagerMembre.user_id == membre_user_id, PotagerMembre.potager_id == potager_id)
        .first()
    )
    if membre is None:
        raise MembreInconnuError("Cet utilisateur n'est pas membre de ce potager")

    db.delete(membre)

    membre_user = db.query(User).filter(User.id == membre_user_id).first()
    if membre_user.potager_actif_id == potager_id:
        membre_user.potager_actif_id = None  # [CA6] invalidation immédiate

    db.commit()
    log.info("[US-048] Membre retiré : potager_id=%s membre_user_id=%s par=%s", potager_id, membre_user_id, user_id)

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

[US-085] Source de vérité des droits : `potager_membres.role`, et elle seule —
c'est elle qu'interroge `require_role` (via `role_utilisateur`). Un potager peut
compter plusieurs owners. `Potager.proprietaire_id` (socle US-040) n'est que le
CRÉATEUR D'ORIGINE : posé une fois à `creer_potager`, jamais relu pour décider
d'un droit, jamais réécrit par un changement de rôle, un retrait ou un départ.
La règle « un potager garde au moins un owner » vit dans UNE fonction,
`_garantir_un_owner_restant`, appelée par tout chemin qui peut retirer un owner.
"""
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.services.context import TenantContext
from app.services.permissions import LIBELLES_ROLE, NIVEAUX_ROLE, require_role
from app.services import auth as svc_auth
from app.services import cache_questions as svc_cache_questions
from app.services import connaissance as svc_connaissance
from app.services import potager_actif as svc_potager_actif
from app.services import telegram_notify as svc_telegram_notify
from database.db import tenant_scope
from database.models import (
    CultureConfig, DureeCulturale, Evenement, FenetreCulturale, Invitation, ItineraireCultural,
    Parcelle, Potager, PotagerMembre, RoutageLog, RoutageRetour, User,
)

log = logging.getLogger("potager")

# Même alphabet que liaison_telegram.py — sans caractères ambigus (0/O, 1/I/l)
_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
_LONGUEUR_CODE = 8
_TTL_JOURS = 7
_ROLES_INVITABLES = {"editor", "lecteur"}
# [US-085 / CA1] Un rôle se CHANGE vers n'importe lequel des trois — contrairement à
# l'invitation, qui ne propose jamais `owner` (le rôle se donne à un membre déjà là).
_ROLES_ATTRIBUABLES = set(NIVEAUX_ROLE)

# [US-085 / CA8] Ce que le nouveau rôle permet, dit au membre concerné par Telegram.
_CE_QUE_PERMET_LE_ROLE = {
    "owner": (
        "Tu peux désormais tout faire sur ce potager : enregistrer des événements, "
        "inviter ou retirer des membres, l'archiver ou le supprimer."
    ),
    "editor": (
        "Tu peux enregistrer des événements (semis, récoltes, observations…), "
        "mais pas gérer les membres ni le potager."
    ),
    "lecteur": "Tu peux consulter le potager, sans y enregistrer d'événement.",
}

# [US-084 / CA7] Délai de grâce entre la suppression logique (soft-delete) et la
# purge physique — l'owner peut restaurer son potager pendant toute cette durée.
DELAI_GRACE_JOURS = 30

# [US-084 / CA4] Nombre d'échecs consécutifs de re-saisie du mot de passe au
# terme duquel l'opération est abandonnée.
MAX_ECHECS_MOT_DE_PASSE = 3


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


class DernierOwnerError(Exception):
    """[US-085 / CA3, CA4] L'opération laisserait le potager sans aucun owner.

    Une seule exception pour les trois chemins qui peuvent faire disparaître un
    owner — changement de rôle, retrait par un owner (`retirer_membre`, US-048) et
    départ volontaire (US-086) : même message et même statut HTTP côté PWA, comme
    `PermissionInsuffisanteError`. `propose_archivage` ajoute la seconde issue
    (archiver puis supprimer) quand l'appelant cherche à SORTIR du potager ; un
    owner qui veut seulement se rétrograder n'a, lui, qu'une marche à suivre."""

    def __init__(self, action_label: str, propose_archivage: bool = False) -> None:
        self.action_label = action_label
        message = (
            f"Tu es le seul propriétaire de ce potager, tu ne peux pas {action_label}. "
            "Désigne d'abord un autre propriétaire"
        )
        if propose_archivage:
            message += ", ou archive puis supprime le potager"
        super().__init__(message + ".")


class PotagerNonArchiveError(Exception):
    """[US-084 / CA1] Suppression demandée sur un potager qui n'est pas archivé.

    Volontairement distincte de `PermissionInsuffisanteError` : les droits sont
    là, c'est le cycle de vie qui bloque — l'archivage (US-083) lève l'obstacle,
    exactement comme `PotagerInactifError` face à une activation refusée."""

    def __init__(self) -> None:
        super().__init__(
            "Ce potager doit d'abord être archivé avant de pouvoir être supprimé."
        )


class MotDePasseInvalideError(Exception):
    """[US-084 / CA4] Re-saisie du mot de passe incorrecte — tentative comptée."""

    def __init__(self, tentatives_restantes: int):
        self.tentatives_restantes = tentatives_restantes
        super().__init__(
            f"Mot de passe incorrect — {tentatives_restantes} tentative"
            f"{'s' if tentatives_restantes > 1 else ''} restante"
            f"{'s' if tentatives_restantes > 1 else ''}."
        )


class TropDEchecsMotDePasseError(Exception):
    """[US-084 / CA4] Trois échecs consécutifs : l'opération est abandonnée."""

    def __init__(self) -> None:
        super().__init__(
            f"{MAX_ECHECS_MOT_DE_PASSE} tentatives infructueuses — suppression abandonnée."
        )


class PotagerNonSupprimeError(Exception):
    """[US-084 / CA6] Restauration demandée sur un potager qui n'est pas à l'état
    `supprime` — rien à restaurer."""

    def __init__(self) -> None:
        super().__init__("Ce potager n'est pas supprimé — il n'y a rien à restaurer.")


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
    activer: bool = True,
    altitude: Optional[float] = None,
) -> Potager:
    """[CA1, CA2] Crée un potager — l'utilisateur en devient owner et ce potager
    devient immédiatement son potager actif. La localisation est simplement
    capturée et stockée (alimente la météo par potager, US-074/US-075).

    [US-074] `ville` est le libellé choisi par l'utilisateur dans le module de
    recherche de ville (géocodage Open-Meteo côté frontend) — jamais recalculé
    côté serveur.

    [US-081 / CA4] `activer` pilote la bascule. Sa valeur par défaut reproduit
    le comportement historique (l'onboarding US-058 en dépend) ; un jardinier
    qui crée un potager additionnel en pleine saison peut au contraire rester
    sur son potager courant. Dans les deux cas la création est atomique et le
    potager naît à l'état `actif` (US-080) — jamais de brouillon.

    Un utilisateur qui n'a encore aucun potager actif se voit toujours attribuer
    celui-ci, même avec `activer=False` : le laisser sans potager actif le
    renverrait sur l'onboarding (409 « aucun potager », cf. US-046 / CA5).

    [US-193 / CA1] `altitude` accompagne les coordonnées de la ville choisie ;
    sans coordonnées, elle n'a pas de sens et n'est pas conservée."""
    if latitude is None or longitude is None:
        altitude = None
    potager = Potager(
        nom=nom, ville=ville, latitude=latitude, longitude=longitude, altitude=altitude,
        proprietaire_id=user_id,
    )
    db.add(potager)
    db.commit()
    db.refresh(potager)

    db.add(PotagerMembre(user_id=user_id, potager_id=potager.id, role="owner"))
    user = db.query(User).filter(User.id == user_id).first()
    if activer or user.potager_actif_id is None:
        user.potager_actif_id = potager.id
    db.commit()

    log.info(
        "[US-048] Potager créé : potager_id=%s nom=%r owner_id=%s actif=%s",
        potager.id, nom, user_id, user.potager_actif_id == potager.id,
    )
    return potager


def modifier_potager(
    db: Session,
    user_id: int,
    potager_id: int,
    nom: Optional[str] = None,
    ville: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    altitude: Optional[float] = None,
) -> Potager:
    """[US-074 / CA4] Un owner corrige nom/ville/localisation d'un potager déjà
    créé — seul moyen de localiser un potager créé avant l'existence de cette
    fonctionnalité (CA6 : rien n'est jamais réécrit à une valeur inventée, un
    paramètre omis (`None`) laisse la colonne existante inchangée).

    [US-193 / CA2] Latitude, longitude et altitude changent ENSEMBLE : dès que
    les coordonnées CHANGENT, l'altitude fournie les accompagne — `None` compris.
    Un potager ne garde jamais l'altitude de son ancienne ville. Des coordonnées
    renvoyées à l'identique sans altitude (simple renommage depuis un écran qui
    ne la connaît pas) ne l'effacent pas."""
    ctx = _ctx_pour_potager(db, user_id, potager_id)
    require_role(ctx, "owner", "modifier le potager")

    potager = db.query(Potager).filter(Potager.id == potager_id).first()
    coordonnees_changees = (
        (latitude is not None and latitude != potager.latitude)
        or (longitude is not None and longitude != potager.longitude)
    )
    if nom is not None:
        potager.nom = nom
    if ville is not None:
        potager.ville = ville
    if latitude is not None:
        potager.latitude = latitude
    if longitude is not None:
        potager.longitude = longitude
    if coordonnees_changees or altitude is not None:
        potager.altitude = altitude
    db.commit()
    db.refresh(potager)

    log.info("[US-074] Potager modifié : potager_id=%s par=%s", potager_id, user_id)
    return potager


def renseigner_altitudes_manquantes(
    db: Session,
    fournisseur: Callable[[list[tuple[float, float]]], list[Optional[float]]],
) -> tuple[int, int]:
    """[US-193 / CA3] Reprise : donne leur altitude aux potagers déjà localisés.

    Ne touche que les potagers à coordonnées connues et altitude NULL — rejouée,
    elle ne réécrit rien, et n'écrase jamais l'altitude d'une ville choisie.
    `fournisseur` reçoit les coordonnées et rend une altitude par point (`None`
    si inconnue) : la base ne parle jamais au réseau, l'appelant si
    (`utils.altitude.altitudes_depuis_coordonnees`). La zone CHOISIE n'est pas
    touchée (CA11).

    Retourne (potagers sans altitude trouvés, altitudes renseignées)."""
    potagers = (
        db.query(Potager)
        .filter(Potager.altitude.is_(None), Potager.latitude.isnot(None), Potager.longitude.isnot(None))
        .order_by(Potager.id)
        .all()
    )
    if not potagers:
        return 0, 0
    altitudes = fournisseur([(p.latitude, p.longitude) for p in potagers])
    renseignes = 0
    for potager, altitude in zip(potagers, altitudes):
        if altitude is None:
            continue
        potager.altitude = altitude
        renseignes += 1
        log.info("[US-193] Altitude renseignée : potager_id=%s altitude=%s m", potager.id, altitude)
    db.commit()
    return len(potagers), renseignes


def _notifier_cycle_vie(
    db: Session, potager: Potager, acteur_id: int, texte_action: str, precision: str = "",
    roles_destinataires: Optional[frozenset[str]] = None,
) -> None:
    """[US-083 / CA9] Notifie chaque AUTRE membre du potager ayant un compte
    Telegram lié — l'acteur de l'action n'a pas besoin de se notifier lui-même.
    Best-effort : `telegram_notify.envoyer_message` n'échoue jamais bruyamment,
    donc l'absence de liaison ou une panne Telegram ne remonte jamais ici.

    [US-084 / CA9] `precision` complète la phrase pour les actions dont la
    conséquence n'est pas évidente au seul énoncé de l'action (date effective
    de purge après une suppression).

    [US-086 / CA7, US-087 / CA8] `roles_destinataires` restreint la diffusion aux
    membres portant l'un de ces rôles — les owners, pour un départ ou une arrivée,
    qui ne concernent pas les autres membres. `None` : tous les autres membres."""
    acteur = db.query(User).filter(User.id == acteur_id).first()
    nom_acteur = (acteur.nom or acteur.email) if acteur else "Un membre"

    requete = (
        db.query(PotagerMembre, User)
        .join(User, User.id == PotagerMembre.user_id)
        .filter(PotagerMembre.potager_id == potager.id, PotagerMembre.user_id != acteur_id)
    )
    if roles_destinataires is not None:
        requete = requete.filter(PotagerMembre.role.in_(roles_destinataires))
    for _membre, membre_user in requete.all():
        if membre_user.telegram_chat_id is None:
            continue
        texte = f"{nom_acteur} a {texte_action} le potager « {potager.nom} »."
        if precision:
            texte = f"{texte} {precision}"
        svc_telegram_notify.envoyer_message(membre_user.telegram_chat_id, texte)


def archiver_potager(db: Session, user_id: int, potager_id: int) -> Potager:
    """[US-083 / CA1, CA2, CA5, CA9] Un owner archive son potager : il passe en
    lecture seule (CA4 refuse toute écriture d'événement tant qu'il le reste).

    [CA5] Pour chaque membre dont ce potager était le potager actif, celui-ci
    est invalidé — même mécanisme que `retirer_membre` (US-048), généralisé à
    tous les membres plutôt qu'à un seul. La ré-sélection automatique d'un
    autre potager (ou le retour à `NULL`) reste portée par
    `resoudre_tenant_context`, appelée paresseusement à la prochaine requête de
    chaque membre concerné — aucune bascule ne doit être recalculée ici."""
    ctx = _ctx_pour_potager(db, user_id, potager_id)
    require_role(ctx, "owner", "archiver ce potager")

    potager = db.query(Potager).filter(Potager.id == potager_id).first()
    potager.etat = svc_potager_actif.ETAT_ARCHIVE
    potager.archive_le = datetime.utcnow()

    membres = db.query(PotagerMembre).filter(PotagerMembre.potager_id == potager_id).all()
    for membre in membres:
        membre_user = db.query(User).filter(User.id == membre.user_id).first()
        if membre_user.potager_actif_id == potager_id:
            membre_user.potager_actif_id = None  # [CA5] invalidation, bascule reprise au prochain accès

    db.commit()
    db.refresh(potager)

    log.info("[US-083] Potager archivé : potager_id=%s par=%s", potager_id, user_id)
    _notifier_cycle_vie(db, potager, user_id, "archivé")
    return potager


def desarchiver_potager(db: Session, user_id: int, potager_id: int) -> Potager:
    """[US-083 / CA2, CA8, CA9] Un owner désarchive son potager : l'écriture y
    redevient immédiatement possible. Ne rebascule le potager actif de
    personne (CA8) — aucune invalidation ni ré-sélection ici, contrairement à
    l'archivage."""
    ctx = _ctx_pour_potager(db, user_id, potager_id)
    require_role(ctx, "owner", "désarchiver ce potager")

    potager = db.query(Potager).filter(Potager.id == potager_id).first()
    potager.etat = svc_potager_actif.ETAT_ACTIF
    potager.archive_le = None
    db.commit()
    db.refresh(potager)

    log.info("[US-083] Potager désarchivé : potager_id=%s par=%s", potager_id, user_id)
    _notifier_cycle_vie(db, potager, user_id, "désarchivé")
    return potager


# ─────────────────────────────────────────────────────────────────────────────
# [US-084] Suppression définitive avec délai de grâce
# -----------------------------------------------------------------------------
# Cycle complet : `archive` --supprimer--> `supprime` (soft-delete, CA2)
#                            <--restaurer--                (CA6, droit au remords)
#                                        --purge J+30-->  effacement physique (CA7)
# ─────────────────────────────────────────────────────────────────────────────

# [CA4] Compteur d'échecs consécutifs de re-saisie du mot de passe, par
# (utilisateur, potager). Volontairement en mémoire du process : il ne protège
# pas d'une attaque distribuée (le rate-limit HTTP et le hachage argon2 s'en
# chargent) mais matérialise l'abandon d'UNE opération de suppression en cours,
# qui n'a pas de sens au-delà de la session courante. Remis à zéro dès qu'une
# vérification réussit ou que l'opération est abandonnée.
_echecs_mot_de_passe: dict[tuple[int, int], int] = {}


def _verifier_mot_de_passe_ou_abandonner(
    db: Session, user_id: int, potager_id: int, mot_de_passe: str
) -> None:
    """[CA4] Vérifie la re-saisie du mot de passe du compte web. Lève
    `MotDePasseInvalideError` tant qu'il reste des tentatives, puis
    `TropDEchecsMotDePasseError` au troisième échec consécutif.

    Un compte sans mot de passe web (compte Telegram-only, US-045) ne peut pas
    confirmer : la suppression lui est refusée de la même manière qu'un mot de
    passe erroné, sans compter de tentative — aucune re-saisie ne pourrait
    aboutir."""
    cle = (user_id, potager_id)
    user = db.query(User).filter(User.id == user_id).first()
    if not user.mot_de_passe_hash:
        raise MotDePasseInvalideError(MAX_ECHECS_MOT_DE_PASSE)

    if svc_auth.verifier_mot_de_passe(mot_de_passe or "", user.mot_de_passe_hash):
        _echecs_mot_de_passe.pop(cle, None)
        return

    echecs = _echecs_mot_de_passe.get(cle, 0) + 1
    if echecs >= MAX_ECHECS_MOT_DE_PASSE:
        _echecs_mot_de_passe.pop(cle, None)
        log.warning(
            "[US-084] Suppression abandonnée après %s échecs de mot de passe : user_id=%s potager_id=%s",
            MAX_ECHECS_MOT_DE_PASSE, user_id, potager_id,
        )
        raise TropDEchecsMotDePasseError()

    _echecs_mot_de_passe[cle] = echecs
    log.warning(
        "[US-084] Mot de passe incorrect à la confirmation de suppression : user_id=%s potager_id=%s tentative=%s",
        user_id, potager_id, echecs,
    )
    raise MotDePasseInvalideError(MAX_ECHECS_MOT_DE_PASSE - echecs)


def compter_impact_suppression(db: Session, user_id: int, potager_id: int) -> dict:
    """[CA3] Décompte réel de ce qui sera perdu — jamais approximé : chaque
    nombre vient d'un COUNT sur la table concernée.

    `nb_photos` vaut structurellement 0 aujourd'hui : le projet ne stocke aucune
    photo (aucune table ni colonne média, cf. `database/models.py`). Le champ est
    exposé quand même, pour que l'écran de confirmation n'ait pas à changer de
    forme le jour où le stockage de photos existera — mais il n'affiche jamais un
    chiffre inventé : il affiche le compte réel, qui est nul.

    Réservé à l'owner : c'est l'écran de confirmation de SA suppression."""
    ctx = _ctx_pour_potager(db, user_id, potager_id)
    require_role(ctx, "owner", "supprimer ce potager")

    potager = db.query(Potager).filter(Potager.id == potager_id).first()
    return {
        "potager_id": potager_id,
        "nom": potager.nom if potager else None,
        "etat": potager.etat if potager else None,
        "nb_evenements": db.query(Evenement).filter(Evenement.potager_id == potager_id).count(),
        "nb_parcelles": db.query(Parcelle).filter(Parcelle.potager_id == potager_id).count(),
        "nb_photos": 0,
        "nb_membres": db.query(PotagerMembre).filter(PotagerMembre.potager_id == potager_id).count(),
        "delai_grace_jours": DELAI_GRACE_JOURS,
    }


def date_purge_prevue(potager: Potager) -> Optional[datetime]:
    """[CA7] Date effective de purge d'un potager supprimé, `None` s'il ne l'est pas."""
    if potager.supprime_le is None:
        return None
    return potager.supprime_le + timedelta(days=DELAI_GRACE_JOURS)


def supprimer_potager(db: Session, user_id: int, potager_id: int, mot_de_passe: str) -> Potager:
    """[CA1, CA2, CA4, CA5, CA9, CA10] Suppression LOGIQUE d'un potager archivé.

    Owner uniquement (CA1/CA10), potager obligatoirement à l'état `archive`
    (CA1 : on ne supprime jamais un potager en cours d'usage), confirmation par
    re-saisie du mot de passe (CA4). Aucune donnée n'est détruite ici (CA2) :
    seul l'état bascule, la purge physique attend le délai de grâce (CA7).

    [CA5] Le potager actif de chaque membre qui pointait dessus est invalidé —
    même mécanisme qu'`archiver_potager` (US-083/CA5) ; la ré-sélection reste
    paresseuse, portée par `resoudre_tenant_context`."""
    ctx = _ctx_pour_potager(db, user_id, potager_id)
    require_role(ctx, "owner", "supprimer ce potager")

    potager = db.query(Potager).filter(Potager.id == potager_id).first()
    if potager.etat != svc_potager_actif.ETAT_ARCHIVE:
        log.warning(
            "[US-084] Suppression refusée, potager non archivé : potager_id=%s etat=%s",
            potager_id, potager.etat,
        )
        raise PotagerNonArchiveError()

    _verifier_mot_de_passe_ou_abandonner(db, user_id, potager_id, mot_de_passe)

    potager.etat = svc_potager_actif.ETAT_SUPPRIME
    potager.supprime_le = datetime.utcnow()

    membres = db.query(PotagerMembre).filter(PotagerMembre.potager_id == potager_id).all()
    for membre in membres:
        membre_user = db.query(User).filter(User.id == membre.user_id).first()
        if membre_user.potager_actif_id == potager_id:
            membre_user.potager_actif_id = None  # [CA5] invalidation, bascule reprise au prochain accès

    db.commit()
    db.refresh(potager)

    purge_le = date_purge_prevue(potager)
    log.info(
        "[US-084] Potager supprimé (logique) : potager_id=%s par=%s purge_prevue=%s",
        potager_id, user_id, purge_le.isoformat(),
    )
    _notifier_cycle_vie(
        db, potager, user_id, "supprimé",
        precision=f"Ses données seront définitivement effacées le {purge_le.strftime('%d/%m/%Y')}.",
    )
    return potager


def restaurer_potager(db: Session, user_id: int, potager_id: int) -> Potager:
    """[CA6] Droit au remords : pendant le délai de grâce, l'owner restaure son
    potager. Il repasse à l'état `archive` — jamais directement `actif` : la
    remise en écriture reste un geste explicite de désarchivage (US-083)."""
    ctx = _ctx_pour_potager(db, user_id, potager_id)
    require_role(ctx, "owner", "restaurer ce potager")

    potager = db.query(Potager).filter(Potager.id == potager_id).first()
    if potager is None or potager.etat != svc_potager_actif.ETAT_SUPPRIME:
        raise PotagerNonSupprimeError()

    potager.etat = svc_potager_actif.ETAT_ARCHIVE
    potager.supprime_le = None
    if potager.archive_le is None:
        potager.archive_le = datetime.utcnow()
    db.commit()
    db.refresh(potager)

    log.info("[US-084] Potager restauré : potager_id=%s par=%s", potager_id, user_id)
    _notifier_cycle_vie(
        db, potager, user_id, "restauré", precision="Il est de nouveau consultable, en lecture seule."
    )
    return potager


def lister_potagers_supprimes(db: Session, user_id: int) -> list[dict]:
    """[CA6] Point d'accès dédié à la restauration : potagers supprimés dont
    l'utilisateur est owner, encore dans leur délai de grâce.

    Volontairement hors de `lister_potagers_utilisateur` (US-080/CA7 : un
    potager supprimé n'apparaît dans AUCUNE liste, `etat=tous` compris) — cette
    corbeille est le seul endroit qui les montre, et uniquement à qui peut les
    restaurer."""
    potagers = (
        db.query(Potager)
        .join(PotagerMembre, PotagerMembre.potager_id == Potager.id)
        .filter(
            PotagerMembre.user_id == user_id,
            PotagerMembre.role == "owner",
            Potager.etat == svc_potager_actif.ETAT_SUPPRIME,
        )
        .order_by(Potager.id)
        .all()
    )
    return [
        {
            "id": p.id,
            "nom": p.nom,
            "etat": p.etat,
            "supprime_le": p.supprime_le,
            "purge_prevue_le": date_purge_prevue(p),
        }
        for p in potagers
    ]


def purger_potager(db: Session, potager_id: int) -> dict:
    """[CA7] Effacement PHYSIQUE d'un potager et de toutes ses données rattachées.

    Fonction de purge UNIQUE (note technique de l'US) : la tâche planifiée
    (`bot.py::job_purge_potagers`), la commande d'administration
    (`tools/purger_potagers.py`) et la future suppression de compte (RGPD)
    passent toutes par ici, jamais par une seconde implémentation.

    Ordre imposé par les clés étrangères : pointeurs `users.potager_actif_id`
    d'abord (ils référencent `potagers`), puis les tables métier de la plus
    dépendante à la moins dépendante, le potager en dernier — aucun orphelin
    ne subsiste.

    [US-043] La suppression s'exécute sous `tenant_scope(potager_id)` : les
    policies RLS sur `evenements`/`parcelles`/`culture_config` restent armées,
    la purge ne contourne pas l'isolation, elle s'y conforme potager par potager.
    """
    potager = db.query(Potager).filter(Potager.id == potager_id).first()
    if potager is None:
        return {"potager_id": potager_id, "purge": False}

    nom = potager.nom
    with tenant_scope(potager_id):
        db.query(User).filter(User.potager_actif_id == potager_id).update(
            {User.potager_actif_id: None}, synchronize_session=False
        )
        volumes = {
            "evenements": db.query(Evenement).filter(Evenement.potager_id == potager_id)
                            .delete(synchronize_session=False),
            "parcelles": db.query(Parcelle).filter(Parcelle.potager_id == potager_id)
                           .delete(synchronize_session=False),
            "invitations": db.query(Invitation).filter(Invitation.potager_id == potager_id)
                             .delete(synchronize_session=False),
            # [US-068] Calendriers PERSONNALISÉS du potager — valeurs d'abord,
            # itinéraires ensuite (clés étrangères), et avant culture_config à
            # laquelle un itinéraire se rattache. Le partagé n'est pas touché.
            "duree_culturale": db.query(DureeCulturale).filter(DureeCulturale.potager_id == potager_id)
                                 .delete(synchronize_session=False),
            "fenetre_culturale": db.query(FenetreCulturale).filter(FenetreCulturale.potager_id == potager_id)
                                   .delete(synchronize_session=False),
            "itineraire_cultural": db.query(ItineraireCultural).filter(ItineraireCultural.potager_id == potager_id)
                                     .delete(synchronize_session=False),
            "culture_config": db.query(CultureConfig).filter(CultureConfig.potager_id == potager_id)
                                .delete(synchronize_session=False),
            "membres": db.query(PotagerMembre).filter(PotagerMembre.potager_id == potager_id)
                         .delete(synchronize_session=False),
            # [US-097 / CA3] routage_retours avant routage_logs (clé étrangère).
            "routage_retours": db.query(RoutageRetour).filter(RoutageRetour.potager_id == potager_id)
                                  .delete(synchronize_session=False),
            "routage_logs": db.query(RoutageLog).filter(RoutageLog.potager_id == potager_id)
                              .delete(synchronize_session=False),
            # [US-095] Cache de reponses : aucune donnee de potager n'y est
            # stockee (les entrees ne portent qu'un aiguillage), mais elles
            # nomment ses cultures et ses parcelles. Elles partent avec lui.
            "questions_cache": svc_cache_questions.purger_potager(db, potager_id),
            # [US-098] Connaissance PRIVEE du potager (US-141). Le savoir global
            # (`potager_id IS NULL`) n'appartient a personne et n'est pas touche.
            "knowledge_chunks": svc_connaissance.purger_potager(db, potager_id),
        }
        db.delete(potager)
        db.commit()

    # [CA7] Seule trace qui subsiste après effacement — d'où le détail des volumes.
    log.info(
        "[US-084] Purge physique : potager_id=%s nom=%r evenements=%s parcelles=%s "
        "invitations=%s culture_config=%s membres=%s routage_logs=%s routage_retours=%s "
        "questions_cache=%s knowledge_chunks=%s itineraire_cultural=%s fenetre_culturale=%s "
        "duree_culturale=%s",
        potager_id, nom, volumes["evenements"], volumes["parcelles"],
        volumes["invitations"], volumes["culture_config"], volumes["membres"],
        volumes["routage_logs"], volumes["routage_retours"], volumes["questions_cache"],
        volumes["knowledge_chunks"], volumes["itineraire_cultural"],
        volumes["fenetre_culturale"], volumes["duree_culturale"],
    )
    return {"potager_id": potager_id, "nom": nom, "purge": True, "volumes": volumes}


def potagers_a_purger(db: Session, maintenant: Optional[datetime] = None) -> list[Potager]:
    """[CA7, CA8] Potagers éligibles à la purge : supprimés ET hors délai de grâce.

    Sélection isolée dans sa propre fonction pour que le mode `--dry-run` de
    `tools/purger_potagers.py` montre exactement ce que la purge effacerait —
    et non une requête écrite une seconde fois, qui pourrait diverger."""
    reference = (maintenant or datetime.utcnow()) - timedelta(days=DELAI_GRACE_JOURS)
    return (
        db.query(Potager)
        .filter(Potager.etat == svc_potager_actif.ETAT_SUPPRIME, Potager.supprime_le <= reference)
        .order_by(Potager.id)
        .all()
    )


def purger_potagers_supprimes(db: Session, maintenant: Optional[datetime] = None) -> list[dict]:
    """[CA7, CA8] Purge tous les potagers supprimés dont le délai de grâce est
    écoulé, et eux seuls.

    [CA8] Idempotente et rejouable : la sélection ne retient que
    `etat = 'supprime'` ET `supprime_le <= maintenant - 30 jours`. Relancée
    aussitôt, elle ne trouve plus rien (les potagers purgés n'existent plus) et
    ne touche jamais un potager encore dans son délai de grâce. N'avoir aucun
    potager à purger est une exécution normale, pas une erreur.

    `maintenant` est injectable pour les tests — jamais renseigné en production.
    """
    potagers = potagers_a_purger(db, maintenant)
    if not potagers:
        log.info("[US-084] Purge : aucun potager au-delà du délai de grâce (%s jours)", DELAI_GRACE_JOURS)
        return []

    resultats = [purger_potager(db, p.id) for p in potagers]
    log.info("[US-084] Purge terminée : %s potager(s) effacé(s)", len(resultats))
    return resultats


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


@dataclass(frozen=True)
class AdhesionPotager:
    """[US-087] Ce dont le bot a besoin pour répondre à un `/rejoindre` réussi.

    `devenu_actif` : le potager rejoint est devenu le potager actif (l'utilisateur n'en
    avait aucun). Sinon `potager_actif_nom` nomme le potager actif, resté inchangé."""
    potager_id: int
    potager_nom: str
    role: str
    role_libelle: str
    peut_ecrire: bool
    devenu_actif: bool
    potager_actif_nom: Optional[str]


def rejoindre_potager(db: Session, user_id: int, code: str) -> AdhesionPotager:
    """[US-087 / CA3, CA6, CA8] Adhésion par code depuis Telegram : enveloppe d'`accepter_invitation`,
    qui reste la SEULE à connaître les règles de validation (code inconnu, expiré, déjà utilisé,
    déjà membre — ses exceptions remontent telles quelles au handler du bot).

    [CA6] Jamais de bascule silencieuse (US-046) : un utilisateur qui avait un potager actif le
    garde — y compris quand ce n'était que le défaut TRANSITOIRE de `resoudre_tenant_context`
    (plusieurs potagers, aucun choix persisté), que `accepter_invitation` écraserait sinon
    puisque `potager_actif_id` est alors NULL. Sans potager actif, le potager rejoint le devient.

    [CA8] Les owners du potager ayant un compte Telegram lié sont informés de l'arrivée. Propre à
    cette porte d'entrée : `POST /invitations/{code}/accepter` (PWA) ne notifie personne.
    Le code d'invitation n'est jamais journalisé ici."""
    try:
        actif_avant = svc_potager_actif.resoudre_tenant_context(db, user_id).potager_id
    except svc_potager_actif.AucunPotagerError:
        actif_avant = None

    membre = accepter_invitation(db, user_id, code)

    user = db.query(User).filter(User.id == user_id).first()
    if actif_avant is not None and user.potager_actif_id != actif_avant:
        user.potager_actif_id = actif_avant
        db.commit()

    potager = db.query(Potager).filter(Potager.id == membre.potager_id).first()
    potager_actif_nom = None
    if actif_avant is not None:
        actif = db.query(Potager).filter(Potager.id == actif_avant).first()
        potager_actif_nom = actif.nom if actif else None
    devenu_actif = (
        actif_avant is None
        and user.potager_actif_id == potager.id
        and potager.etat == svc_potager_actif.ETAT_ACTIF
    )

    role_libelle = LIBELLES_ROLE.get(membre.role, membre.role)
    log.info(
        "[US-087] Potager rejoint depuis Telegram : potager_id=%s user_id=%s role=%s devenu_actif=%s",
        potager.id, user_id, membre.role, devenu_actif,
    )
    _notifier_cycle_vie(
        db, potager, user_id, "rejoint", precision=f"Rôle : {role_libelle}.",
        roles_destinataires=frozenset({"owner"}),
    )
    return AdhesionPotager(
        potager_id=potager.id,
        potager_nom=potager.nom,
        role=membre.role,
        role_libelle=role_libelle,
        peut_ecrire=NIVEAUX_ROLE.get(membre.role, -1) >= NIVEAUX_ROLE["editor"],
        devenu_actif=devenu_actif,
        potager_actif_nom=potager_actif_nom,
    )


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


def _garantir_un_owner_restant(
    db: Session, potager_id: int, membre_user_id: int, action_label: str, propose_archivage: bool = False,
) -> None:
    """[US-085 / CA3, CA4] Garde UNIQUE « un potager garde au moins un owner » : lève
    `DernierOwnerError` si `membre_user_id` est le dernier owner, donc si lui retirer
    son rôle (rétrogradation, retrait, départ) laisserait le potager orphelin.

    ⚠️ À appeler DANS la transaction qui écrit ensuite, avant le `commit` : le
    `SELECT … FOR UPDATE` garde les lignes des owners verrouillées jusqu'à ce
    commit. Sans lui, deux owners qui se rétrogradent en même temps liraient chacun
    « l'autre est encore owner » et le potager finirait sans propriétaire. Le second
    attend, relit après le commit du premier — sous PostgreSQL une ligne devenue
    non-owner sort du résultat — et se voit refuser. (SQLite, qui sert aux tests,
    ignore `FOR UPDATE` : un seul écrivain à la fois de toute façon.)"""
    owners = [
        uid for (uid,) in (
            db.query(PotagerMembre.user_id)
            .filter(PotagerMembre.potager_id == potager_id, PotagerMembre.role == "owner")
            .order_by(PotagerMembre.user_id)  # même ordre de verrouillage partout : pas d'interblocage
            .with_for_update()
            .all()
        )
    ]
    if owners == [membre_user_id]:
        raise DernierOwnerError(action_label, propose_archivage)


def _supprimer_appartenance(
    db: Session, potager_id: int, membre_user_id: int, action_label: str, propose_archivage: bool = False,
) -> None:
    """[US-048 / CA5, CA6 ; US-085 / CA4] Supprime le lien d'appartenance d'un membre —
    logique commune au retrait par un owner (`retirer_membre`) et au départ volontaire
    (US-086) : la garde « dernier owner » et l'invalidation du potager actif ne
    vivent qu'ici. Le contrôle des droits reste à la charge de l'appelant. Ne touche
    à aucune donnée métier : événements, parcelles et photos restent au potager.

    L'invalidation (`potager_actif_id = NULL`) suffit à couper l'accès : au prochain
    accès, `resoudre_tenant_context` rebascule sur un autre potager de l'intéressé
    ou lève `AucunPotagerError` (409 « aucun potager », cf. get_current_user_ctx)."""
    membre = (
        db.query(PotagerMembre)
        .filter(PotagerMembre.user_id == membre_user_id, PotagerMembre.potager_id == potager_id)
        .first()
    )
    if membre is None:
        raise MembreInconnuError("Cet utilisateur n'est pas membre de ce potager")

    if membre.role == "owner":
        _garantir_un_owner_restant(db, potager_id, membre_user_id, action_label, propose_archivage)

    db.delete(membre)

    membre_user = db.query(User).filter(User.id == membre_user_id).first()
    if membre_user.potager_actif_id == potager_id:
        membre_user.potager_actif_id = None  # [CA6] invalidation immédiate

    db.commit()


def retirer_membre(db: Session, user_id: int, potager_id: int, membre_user_id: int) -> None:
    """[CA5, CA6] Un owner retire un membre — celui-ci perd l'accès immédiatement :
    si ce potager était son potager actif, il est invalidé (l'utilisateur retiré
    reçoit alors un 409 'aucun potager' au prochain accès, cf. get_current_user_ctx).

    [US-085 / CA4] Un owner ne peut pas se retirer s'il est le dernier."""
    ctx = _ctx_pour_potager(db, user_id, potager_id)
    require_role(ctx, "owner", "retirer un membre")

    _supprimer_appartenance(db, potager_id, membre_user_id, "te retirer", propose_archivage=True)
    log.info("[US-048] Membre retiré : potager_id=%s membre_user_id=%s par=%s", potager_id, membre_user_id, user_id)


def quitter_potager(db: Session, user_id: int, potager_id: int) -> None:
    """[US-086 / CA1-CA5, CA7, CA8] Un membre se retire LUI-MÊME d'un potager — sans autre
    permission que d'en être membre : l'asymétrie d'avant (un owner retire, un membre ne
    peut pas partir) disparaît.

    [CA2, CA3] Un owner non unique part comme n'importe quel membre ; le dernier owner est
    refusé par la garde unique d'US-085 (`DernierOwnerError`, avec la marche à suivre :
    désigner un autre propriétaire, ou archiver puis supprimer).
    [CA4, CA8] La suppression d'appartenance et l'invalidation du potager actif sont
    celles de `retirer_membre` (`_supprimer_appartenance`) : dès la requête suivante,
    API comme bot, le potager n'apparaît plus dans les potagers de l'ancien membre.
    [CA5] Aucune donnée métier n'est touchée : le potager appartient au collectif.
    [CA7] Les owners restants ayant un compte Telegram lié sont informés du départ."""
    role = svc_potager_actif.role_utilisateur(db, user_id, potager_id)
    if role is None:
        raise svc_potager_actif.PotagerNonMembreError("Cet utilisateur n'est pas membre de ce potager")

    _supprimer_appartenance(db, potager_id, user_id, "le quitter", propose_archivage=True)
    log.info("[US-086] Potager quitté : potager_id=%s user_id=%s role=%s", potager_id, user_id, role)

    potager = db.query(Potager).filter(Potager.id == potager_id).first()
    _notifier_cycle_vie(db, potager, user_id, "quitté", roles_destinataires=frozenset({"owner"}))


def _notifier_changement_role(
    db: Session, potager: Potager, acteur_id: int, membre_user_id: int, nouveau_role: str
) -> None:
    """[US-085 / CA8] Informe le membre dont le rôle vient de changer, s'il a un compte
    Telegram lié (US-045) : son nouveau rôle et ce qu'il lui permet. Best-effort comme
    `_notifier_cycle_vie` — l'absence de liaison ou une panne Telegram ne fait jamais
    échouer le changement de rôle."""
    membre_user = db.query(User).filter(User.id == membre_user_id).first()
    if membre_user is None or membre_user.telegram_chat_id is None:
        return
    acteur = db.query(User).filter(User.id == acteur_id).first()
    nom_acteur = (acteur.nom or acteur.email) if acteur else "Un propriétaire"
    texte = (
        f"{nom_acteur} a changé ton rôle sur le potager « {potager.nom} » : "
        f"tu es maintenant {LIBELLES_ROLE[nouveau_role]}. {_CE_QUE_PERMET_LE_ROLE[nouveau_role]}"
    )
    svc_telegram_notify.envoyer_message(membre_user.telegram_chat_id, texte)


def modifier_role_membre(
    db: Session, user_id: int, potager_id: int, membre_user_id: int, nouveau_role: str,
) -> PotagerMembre:
    """[US-085 / CA1-CA6, CA8] Un owner change le rôle d'un membre du potager : correction
    d'un rôle mal attribué (`lecteur` ↔ `editor`), promotion d'un autre owner (CA2) ou
    rétrogradation de lui-même (CA3). Réservé aux owners (CA5) : un editor ou un lecteur
    ne peut modifier aucun rôle, y compris le sien.

    [CA3, CA4] Rétrograder un owner — soi-même ou un autre — passe par la garde unique
    `_garantir_un_owner_restant` : le dernier owner ne peut jamais l'être. La garde et
    l'écriture partagent la même transaction (pas de course entre deux rétrogradations).

    [CA6] Le changement est immédiat : `potager_membres.role` est relu à chaque requête
    (`resoudre_tenant_context`, `role_utilisateur`), sans jeton ni cache à invalider.
    `Potager.proprietaire_id` n'est pas touché — cf. la docstring du module.

    Demander le rôle que le membre a déjà est sans effet et ne notifie personne."""
    ctx = _ctx_pour_potager(db, user_id, potager_id)
    require_role(ctx, "owner", "modifier le rôle d'un membre")

    if nouveau_role not in _ROLES_ATTRIBUABLES:
        raise RoleInvalideError("Le rôle doit être 'owner', 'editor' ou 'lecteur'")

    membre = (
        db.query(PotagerMembre)
        .filter(PotagerMembre.user_id == membre_user_id, PotagerMembre.potager_id == potager_id)
        .first()
    )
    if membre is None:
        raise MembreInconnuError("Cet utilisateur n'est pas membre de ce potager")

    ancien_role = membre.role
    if ancien_role == nouveau_role:
        return membre

    if ancien_role == "owner":
        _garantir_un_owner_restant(
            db, potager_id, membre_user_id,
            "te rétrograder" if membre_user_id == user_id else "rétrograder ce propriétaire",
        )

    membre.role = nouveau_role
    db.commit()
    log.info(
        "[US-085] Rôle modifié : potager_id=%s membre_user_id=%s %s→%s par=%s",
        potager_id, membre_user_id, ancien_role, nouveau_role, user_id,
    )

    potager = db.query(Potager).filter(Potager.id == potager_id).first()
    _notifier_changement_role(db, potager, user_id, membre_user_id, nouveau_role)
    return membre

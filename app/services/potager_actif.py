"""
app/services/potager_actif.py — Sélection du potager actif [US-046]
-------------------------------------------------------------------------------
Résout le TenantContext réel (potager actif + rôle) d'un utilisateur à partir
de `potager_membres` et `users.potager_actif_id`, et permet de le changer
explicitement (bot `/potager`, sélecteur PWA).

⚠️ Comme app/services/auth.py et liaison_telegram.py, ce module ne prend pas
TenantContext en paramètre : c'est justement lui qui le produit.
"""
import logging
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.services.context import TenantContext
from database.models import Parcelle, Potager, PotagerMembre, User


log = logging.getLogger("potager")

# [US-080] États du cycle de vie du potager — valeurs sans accent, telles
# qu'elles sont stockées (contrainte CHECK, migration_v29.sql). Les libellés
# accentués « archivé » / « supprimé » n'existent que côté affichage.
ETAT_ACTIF = "actif"
ETAT_ARCHIVE = "archive"
ETAT_SUPPRIME = "supprime"

# Filtre de lecture supplémentaire, accepté partout où un état est demandé.
FILTRE_TOUS = "tous"

# [CA7] Un potager supprimé est traité comme inexistant par TOUTES les lectures,
# `tous` compris : il n'appartient qu'au job de purge (US-084).
ETATS_VISIBLES = (ETAT_ACTIF, ETAT_ARCHIVE)

_FILTRES_ETAT_VALIDES = (ETAT_ACTIF, ETAT_ARCHIVE, FILTRE_TOUS)
# Tolérance d'entrée : le document de conception et les libellés d'IHM emploient
# la forme accentuée, la base ne connaît que la forme sans accent.
_ALIAS_FILTRES = {"archivé": ETAT_ARCHIVE, "archivée": ETAT_ARCHIVE}


class AucunPotagerError(Exception):
    """[CA5] L'utilisateur n'est membre d'aucun potager (actif)."""


class PotagerNonMembreError(Exception):
    """[CA2] Tentative de sélection d'un potager dont l'utilisateur n'est pas membre."""


class PotagerInactifError(Exception):
    """[US-080 / CA6] Le potager existe et l'utilisateur en est membre, mais son
    état interdit d'en faire le potager actif (potager archivé).

    Volontairement distincte de `PotagerNonMembreError` : ce n'est pas un
    problème de droits mais de cycle de vie — le désarchivage (US-083) suffit
    à débloquer la situation, contrairement à une absence d'appartenance."""


class FiltreEtatInvalideError(Exception):
    """[CA5] Filtre d'état demandé hors de `actif` / `archive` / `tous`."""


def normaliser_filtre_etat(etat: Optional[str]) -> str:
    """[CA5] Valide et normalise un filtre d'état venu de l'extérieur (query
    string, appelant de service). `None` et chaîne vide valent `actif` : sans
    demande explicite, on ne montre que les potagers actifs."""
    if etat is None or not str(etat).strip():
        return ETAT_ACTIF
    filtre = str(etat).strip().lower()
    filtre = _ALIAS_FILTRES.get(filtre, filtre)
    if filtre not in _FILTRES_ETAT_VALIDES:
        raise FiltreEtatInvalideError(
            f"État inconnu : {etat!r} (attendu : {', '.join(_FILTRES_ETAT_VALIDES)})"
        )
    return filtre


def lister_potagers_utilisateur(
    db: Session, user_id: int, etat: Optional[str] = ETAT_ACTIF
) -> list[Potager]:
    """[CA2 ; US-080 / CA4, CA7] Potagers dont l'utilisateur est membre, triés
    par id (ordre stable), filtrés par état.

    `etat` vaut `actif` par défaut : un potager archivé ou supprimé n'est
    **jamais** retourné sans demande explicite. `tous` élargit aux archivés
    uniquement — un potager supprimé reste invisible en toutes circonstances.
    """
    filtre = normaliser_filtre_etat(etat)
    requete = (
        db.query(Potager)
        .join(PotagerMembre, PotagerMembre.potager_id == Potager.id)
        .filter(PotagerMembre.user_id == user_id)
    )
    if filtre == FILTRE_TOUS:
        requete = requete.filter(Potager.etat.in_(ETATS_VISIBLES))
    else:
        requete = requete.filter(Potager.etat == filtre)
    return requete.order_by(Potager.id).all()


def compter_parcelles_par_potager(db: Session, potager_ids: list[int]) -> dict[int, int]:
    """[US-054 / CA1] Nombre de parcelles actives par potager, pour l'affichage du
    sélecteur de potager.

    Une seule requête groupée quel que soit le nombre de potagers (pas de N+1).
    Les parcelles désactivées (`actif = False`, suppression douce) ne sont pas
    comptées. Un potager sans parcelle est absent du dictionnaire — à l'appelant
    de retomber sur 0.
    """
    if not potager_ids:
        return {}
    lignes = (
        db.query(Parcelle.potager_id, func.count(Parcelle.id))
        .filter(Parcelle.potager_id.in_(potager_ids), Parcelle.actif.is_(True))
        .group_by(Parcelle.potager_id)
        .all()
    )
    return {potager_id: nombre for potager_id, nombre in lignes}


def compter_membres_par_potager(db: Session, potager_ids: list[int]) -> dict[int, int]:
    """[US-054 / CA1] Nombre de membres par potager, tous rôles confondus.

    Même principe que `compter_parcelles_par_potager` : une seule requête groupée.
    """
    if not potager_ids:
        return {}
    lignes = (
        db.query(PotagerMembre.potager_id, func.count(PotagerMembre.user_id))
        .filter(PotagerMembre.potager_id.in_(potager_ids))
        .group_by(PotagerMembre.potager_id)
        .all()
    )
    return {potager_id: nombre for potager_id, nombre in lignes}


def _role_utilisateur(db: Session, user_id: int, potager_id: int) -> Optional[str]:
    membre = (
        db.query(PotagerMembre)
        .filter(PotagerMembre.user_id == user_id, PotagerMembre.potager_id == potager_id)
        .first()
    )
    return membre.role if membre else None


def _etat_potager(db: Session, potager_id: int) -> Optional[str]:
    """[US-080] État courant d'un potager, ou `None` s'il n'existe pas."""
    potager = db.query(Potager).filter(Potager.id == potager_id).first()
    return potager.etat if potager else None


def role_utilisateur(db: Session, user_id: int, potager_id: int) -> Optional[str]:
    """[US-048] Rôle d'un utilisateur sur un potager donné, ou None s'il n'en est
    pas membre — utilisé pour construire un TenantContext ciblé sur un potager
    précis (invitation/retrait de membre), indépendamment du potager actif."""
    return _role_utilisateur(db, user_id, potager_id)


def obtenir_potager(db: Session, user_id: int, potager_id: int) -> Optional[dict]:
    """[US-082 / CA2, CA7] Détail d'un potager pour l'écran Paramètres — réservé
    à ses membres, quel que soit leur rôle (lecture seule pour editor/lecteur).

    Retourne `None` si le potager n'existe pas, s'il est `supprime` (traité
    comme inexistant en toutes circonstances, même règle que
    `lister_potagers_utilisateur`), ou si l'appelant n'en est pas membre — dans
    les trois cas le refus reste générique côté API, sans révéler laquelle de
    ces situations s'applique (CA7)."""
    potager = db.query(Potager).filter(Potager.id == potager_id).first()
    if potager is None or potager.etat == ETAT_SUPPRIME:
        return None
    role = _role_utilisateur(db, user_id, potager_id)
    if role is None:
        return None
    nb_parcelles = compter_parcelles_par_potager(db, [potager_id]).get(potager_id, 0)
    nb_membres = compter_membres_par_potager(db, [potager_id]).get(potager_id, 0)
    return {
        "id": potager.id,
        "nom": potager.nom,
        "ville": potager.ville,
        "latitude": potager.latitude,
        "longitude": potager.longitude,
        "etat": potager.etat,
        "role": role,
        "nb_parcelles": nb_parcelles,
        "nb_membres": nb_membres,
    }


def resoudre_tenant_context(db: Session, user_id: int) -> TenantContext:
    """[CA1, CA5, CA6] Résout le TenantContext réel d'un utilisateur.

    - Potager actif déjà choisi et toujours valide → utilisé tel quel.
    - Un seul potager, aucun choix encore fait → sélection automatique
      silencieuse, persistée (CA1).
    - Plusieurs potagers, aucun choix encore fait → potager par défaut
      transitoire (le premier, non persisté) — l'utilisateur choisit
      explicitement via /potager ou le sélecteur PWA (CA2) pour changer.
    - Aucun potager → AucunPotagerError (CA5).

    [US-080 / CA6] Seuls les potagers `actif` entrent dans la résolution : un
    potager archivé ou supprimé ne peut ni devenir ni **rester** le potager
    actif — le pointeur `users.potager_actif_id` qui viserait un tel potager
    est invalidé ici, et la sélection repart des potagers encore actifs.
    """
    user = db.query(User).filter(User.id == user_id).first()
    potagers = lister_potagers_utilisateur(db, user_id)
    potagers_par_id = {p.id: p for p in potagers}

    if user.potager_actif_id is not None and user.potager_actif_id not in potagers_par_id:
        # Soit l'utilisateur n'est plus membre (US-048), soit le potager n'est
        # plus actif (US-080) : dans les deux cas le pointeur ne vaut plus rien.
        if _etat_potager(db, user.potager_actif_id) != ETAT_ACTIF:
            log.info(
                "[US-080] Potager actif invalidé (état non actif) : user_id=%s potager_id=%s",
                user_id, user.potager_actif_id,
            )
            user.potager_actif_id = None
            db.commit()

    if not potagers:
        raise AucunPotagerError("Aucun potager actif associé à cet utilisateur")

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
    """[CA2, CA3, CA4] Change explicitement le potager actif — persisté.

    [US-080 / CA6, CA7] Refuse un potager dont l'état n'est pas `actif` :
    - potager `supprime` (ou inexistant) → `PotagerNonMembreError`, il est
      traité comme inexistant, l'utilisateur n'apprend rien de plus ;
    - potager `archive` → `PotagerInactifError`, distincte, car il suffit de
      le désarchiver (US-083) pour pouvoir y revenir.
    """
    etat = _etat_potager(db, potager_id)
    if etat is None or etat == ETAT_SUPPRIME:
        raise PotagerNonMembreError("Cet utilisateur n'est pas membre de ce potager")

    role = _role_utilisateur(db, user_id, potager_id)
    if role is None:
        raise PotagerNonMembreError("Cet utilisateur n'est pas membre de ce potager")

    if etat != ETAT_ACTIF:
        log.info(
            "[US-080] Activation refusée, potager non actif : user_id=%s potager_id=%s etat=%s",
            user_id, potager_id, etat,
        )
        raise PotagerInactifError("Ce potager est archivé — désarchivez-le pour le réactiver")

    user = db.query(User).filter(User.id == user_id).first()
    user.potager_actif_id = potager_id
    db.commit()

    return TenantContext(user_id=user_id, potager_id=potager_id, role=role)

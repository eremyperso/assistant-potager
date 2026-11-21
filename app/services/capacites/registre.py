"""
app/services/capacites/registre.py — Le registre de capacités, couche neutre [US-338]
=====================================================================================

Une CAPACITÉ est une question de jardinier (« voir le plan », « que faire maintenant ») ou une proposition
d'écriture, appelable par deux clients :

* le serveur MCP (`app/services/mcp/serveur.py`), pour les assistants extérieurs (Claude, Le Chat) : il ajoute
  l'authentification, les quotas, la portée du connecteur et le journal `mcp_appels`, rien d'autre ;
* le compagnon de l'application (`appeler`, `lister`), sans OAuth ni JSON-RPC, pour un jardinier et un potager
  donnés (il ne s'en sert pas encore : US-342).

Les deux voient le MÊME registre : mêmes noms, mêmes descriptions, mêmes schémas, même code exécuté. La règle
d'écriture d'une capacité (R1 à R5) est dans `docs/EPIC 20 - COMPAGNON CLIENT DES CAPACITES/07_REGLE_D_UNE_CAPACITE.md`.

Ce module ne connaît ni le protocole MCP, ni les jetons, ni les quotas.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from app.services.context import TenantContext
from app.services.permissions import NIVEAUX_ROLE
from database.db import tenant_scope

log = logging.getLogger("potager")

REFUS_LECTEUR = "Tu es lecteur sur ce potager"
#: Le client du compagnon de l'application, tel qu'il apparaît dans les traces des capacités.
CLIENT_COMPAGNON = "compagnon"
PORTEE_ECRITURE = "ecriture"


@dataclass(frozen=True)
class Appelant:
    """Qui appelle une capacité, vu par les capacités : le jardinier, le nom du client, les potagers qu'il peut viser
    et s'il peut proposer d'écrire. La `Connexion` du MCP a les mêmes attributs ; le compagnon en construit un par
    `appelant_compagnon`."""
    user_id: int
    client: str
    potager_ids: tuple[int, ...] = ()
    portee: str = PORTEE_ECRITURE

    @property
    def ecriture(self) -> bool:
        return self.portee == PORTEE_ECRITURE


@dataclass
class AppelCapacite:
    """Ce qu'une capacité reçoit : l'appelant, le contexte locataire résolu, ses arguments."""
    appelant: Any  # Appelant, ou la Connexion du MCP (mêmes attributs)
    ctx: Optional[TenantContext]
    arguments: dict


@dataclass(frozen=True)
class Capacite:
    """Une capacité. `ecriture` déclenche la garde de rôle (et, côté MCP, la garde de portée)."""
    nom: str
    titre: str
    description: str
    executer: Callable[[Session, AppelCapacite], Any]
    proprietes: dict = field(default_factory=dict)
    requis: tuple[str, ...] = ()
    ecriture: bool = False
    destructeur: bool = False
    idempotent: bool = True
    besoin_potager: bool = True
    #: [US-292] Le potager visé quand l'appel n'en nomme pas : celui de la proposition à confirmer, plutôt que le
    #: potager actif. None → le potager actif (résolu par le client).
    potager_de: Optional[Callable[[Session, Any, dict], Optional[int]]] = None

    def schema_entree(self) -> dict:
        """Le schéma JSON des arguments, le même pour les deux clients."""
        proprietes = dict(self.proprietes)
        if self.besoin_potager:
            proprietes.setdefault("potager", {
                "type": ["string", "integer"],
                "description": "Nom ou identifiant du potager ; sans lui, le potager actif.",
            })
        schema: dict = {"type": "object", "properties": proprietes, "additionalProperties": False}
        if self.requis:
            schema["required"] = list(self.requis)
        return schema


class RefusCapacite(Exception):
    """Un refus métier rendu au modèle et, côté MCP, journalisé en `refus`."""

    def __init__(self, message: str, motif: str):
        super().__init__(message)
        self.message = message
        self.motif = motif


REGISTRE: dict[str, Capacite] = {}


def enregistrer_capacite(capacite: Capacite) -> Capacite:
    """Ajoute une capacité au registre (les lectures d'US-291, les propositions d'US-292, les commandes d'US-293)."""
    if capacite.destructeur:
        # L7 : aucune destruction par une capacité — un modèle peut enchaîner proposer + confirmer sans que le
        # jardinier ait vraiment dit oui. Une suppression se fait dans l'application, au bouton.
        raise ValueError(f"Outil destructeur refusé sur le canal MCP : {capacite.nom}")
    REGISTRE[capacite.nom] = capacite
    return capacite


def peut_ecrire(role: Optional[str]) -> bool:
    return NIVEAUX_ROLE.get(role or "", -1) >= NIVEAUX_ROLE["editor"]


def verifier_arguments(capacite: Capacite, arguments: dict) -> None:
    """Aucun argument hors schéma, aucun argument requis manquant."""
    connus = set(capacite.schema_entree()["properties"])
    inconnus = set(arguments) - connus
    if inconnus:
        raise RefusCapacite(f"Argument inconnu : {', '.join(sorted(inconnus))}.", "arguments")
    manquants = [nom for nom in capacite.requis if arguments.get(nom) in (None, "")]
    if manquants:
        raise RefusCapacite(f"Argument obligatoire manquant : {', '.join(manquants)}.", "arguments")


def verifier_role(capacite: Capacite, ctx: Optional[TenantContext]) -> None:
    """Un `lecteur` ne propose jamais d'écrire, quel que soit le client."""
    if capacite.ecriture and ctx is not None and not peut_ecrire(ctx.role):
        raise RefusCapacite(REFUS_LECTEUR, "role")


def executer(db: Session, capacite: Capacite, appel: AppelCapacite) -> Any:
    """Exécute la capacité, sous le GUC RLS du potager visé quand elle en a besoin, et valide."""
    if appel.ctx is not None:
        with tenant_scope(appel.ctx.potager_id):
            donnees = capacite.executer(db, appel)
            db.commit()
    else:
        donnees = capacite.executer(db, appel)
        db.commit()
    return donnees


def lister(*, ecriture: bool = True) -> list[Capacite]:
    """Les capacités du registre, par nom ; `ecriture=False` → les lectures seules."""
    return [c for c in sorted(REGISTRE.values(), key=lambda c: c.nom) if ecriture or not c.ecriture]


def appelant_compagnon(ctx: TenantContext) -> Appelant:
    """L'appelant du compagnon de l'application : le jardinier du contexte, sur ce seul potager."""
    return Appelant(user_id=ctx.user_id, client=CLIENT_COMPAGNON, potager_ids=(ctx.potager_id,))


def appeler(db: Session, ctx: TenantContext, nom: str, arguments: Optional[dict] = None, *,
            appelant: Optional[Appelant] = None) -> Any:
    """[CA1] Le compagnon appelle une capacité pour un jardinier et un potager donnés : mêmes gardes que le MCP sur
    les arguments et le rôle, même code exécuté ; ni jeton, ni quota, ni journal `mcp_appels`.

    Lève `RefusCapacite` (capacité inconnue, argument invalide, lecteur qui propose d'écrire, refus métier)."""
    capacite = REGISTRE.get(nom) if isinstance(nom, str) else None
    if capacite is None:
        raise RefusCapacite(f"Capacité inconnue : {nom}", "inconnue")
    arguments = {} if arguments is None else arguments
    if not isinstance(arguments, dict):
        raise RefusCapacite("Les arguments doivent être un objet JSON.", "arguments")
    verifier_arguments(capacite, arguments)
    verifier_role(capacite, ctx)
    appel = AppelCapacite(appelant or appelant_compagnon(ctx), ctx if capacite.besoin_potager else None, arguments)
    db.commit()  # la transaction suivante s'ouvre sous le GUC RLS du potager (database.db, after_begin)
    try:
        donnees = executer(db, capacite, appel)
    except Exception:
        db.rollback()
        raise
    log.info("[US-338] Capacité %s appelée par %s (potager %s)", nom, appel.appelant.client, ctx.potager_id)
    return donnees

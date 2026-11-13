"""app/services/retrait_parcelle.py — Retirer une parcelle sans perdre son histoire [US-332]
------------------------------------------------------------------------------------
Rendre inactive ou supprimer : deux gestes, une seule vérification, toujours calculée depuis les
données (jamais par un modèle).

- **Le bilan** (`bilan`) dit ce que la parcelle porte : cultures en place, lots de pépinière,
  gestes d'historique (R2, R6).
- **Rendre inactive** (R3, R5) : la parcelle reste sur le plan, grisée, avec son historique et sa
  rotation ; elle sort seulement des listes de choix d'un nouveau geste (CA4). Elle se réactive.
- **Supprimer** (R4, CA5) : réelle, et réservée à une parcelle sans culture ni historique — une
  parcelle créée par erreur. Sinon `ParcelleNonVideError` explique pourquoi et propose l'inactivation
  (CA3). Le potager et le rôle sont ceux du contexte : une parcelle d'un autre potager est introuvable.

Le chemin d'écriture est unique : le bot (`/parcelle supprimer`), la PWA (carte de confirmation du
compagnon) et le MCP passent tous par `supprimer` et `inactiver`.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.services import parcelles as svc_parcelles
from app.services.context import TenantContext
from app.services.permissions import require_role
from database.models import Evenement, Parcelle
from utils import parcelles as _parcelles

log = logging.getLogger("potager")


class ParcelleNonVideError(ValueError):
    """[CA3] La suppression est refusée : la parcelle a des cultures ou un historique.

    `str(e)` est le message lu par le jardinier — il explique et propose l'inactivation.
    """

    def __init__(self, message: str, bilan: dict) -> None:
        super().__init__(message)
        self.bilan = bilan


def _trouver(db: Session, ctx: TenantContext, nom: str) -> Optional[Parcelle]:
    """La parcelle ACTIVE de ce nom (exact, jamais un voisin) dans le potager courant."""
    exacte, _ = _parcelles.find_doublon(db, _parcelles.normalize_parcelle_name(nom), potager_id=ctx.potager_id)
    return exacte if exacte is not None and exacte.actif else None


def _pluriel(n: int, un: str, plusieurs: str) -> str:
    return f"{n} {un if n == 1 else plusieurs}"


def bilan(db: Session, ctx: TenantContext, parcelle: Parcelle) -> dict:
    """[R2, R6] Ce que porte la parcelle : `cultures` (« 12 plants de tomate »), `lots` (pépinière),
    `nb_gestes` (historique) et `vide` — vrai seulement sans geste ni culture ni lot."""
    from app.services import anticipation_commande as anticipation

    nb_gestes = (
        db.query(Evenement)
        .filter(Evenement.potager_id == ctx.potager_id)
        .filter((Evenement.parcelle_id == parcelle.id) | (Evenement.parcelle_origine_id == parcelle.id))
        .count()
    )
    cultures = anticipation._cultures_en_place(db, ctx, parcelle)  # noqa: SLF001 — même lecture que US-253
    lots = anticipation._lots_en_pepiniere(db, ctx, parcelle)  # noqa: SLF001
    return {
        "parcelle_id": parcelle.id, "nom": parcelle.nom, "actif": bool(parcelle.actif),
        "pepiniere": bool(parcelle.est_pepiniere),
        "cultures": cultures, "nb_cultures": len(cultures), "lots": lots, "nb_gestes": nb_gestes,
        "vide": nb_gestes == 0 and not cultures and not lots,
    }


def lignes_du_bilan(b: dict) -> list[str]:
    """[R3] Les lignes de la carte de confirmation : ce qui reste en place, ce qui est conservé."""
    lignes: list[str] = []
    if b["nb_cultures"]:
        lignes.append(f"🌱 {_pluriel(b['nb_cultures'], 'culture en place', 'cultures en place')} (à terminer ou déplacer ensuite)")
    if b["lots"]:
        lignes.append(f"🌱 {_pluriel(b['lots'], 'lot de pépinière', 'lots de pépinière')} encore suivi{'s' if b['lots'] > 1 else ''}")
    if b["nb_gestes"]:
        lignes.append("📚 Historique et rotation conservés")
    if not b["vide"]:
        lignes.append("⏸ Reste sur le plan, grisée ; se réactive à tout moment")
    return lignes


def ce_quelle_porte(b: dict) -> str:
    """« 7 cultures en place et 124 gestes d'historique » — ce qui interdit la suppression."""
    porte = []
    if b["nb_cultures"]:
        porte.append(_pluriel(b["nb_cultures"], "culture en place", "cultures en place"))
    if b["lots"]:
        porte.append(_pluriel(b["lots"], "lot de pépinière suivi", "lots de pépinière suivis"))
    if b["nb_gestes"]:
        porte.append(_pluriel(b["nb_gestes"], "geste d'historique", "gestes d'historique"))
    return " et ".join(porte)


def message_refus(b: dict) -> str:
    """[CA3] Pourquoi on ne supprime pas, et ce qu'on propose à la place."""
    return (
        f"La parcelle « {b['nom']} » a {ce_quelle_porte(b)} : je ne la supprime pas, pour ne pas "
        f"perdre sa rotation. Je te propose de la rendre inactive — elle reste sur le plan, grisée, "
        f"avec son historique (/parcelle modifier {b['nom']} actif=non)."
    )


def inactiver(db: Session, ctx: TenantContext, nom: str) -> str:
    """[R3, R5] Rend la parcelle inactive, historique conservé. LookupError si elle n'est pas active."""
    require_role(ctx, "editor", "rendre une parcelle inactive")
    parcelle = _trouver(db, ctx, nom)
    if parcelle is None:
        raise LookupError(nom)
    svc_parcelles.modifier_parcelle(db, ctx, parcelle.id, {"actif": False})
    log.info("[US-332] Parcelle %r rendue inactive (potager %s)", parcelle.nom, ctx.potager_id)
    return f"Parcelle « {parcelle.nom} » rendue inactive : elle reste sur le plan, grisée, avec son historique."


def reactiver(db: Session, ctx: TenantContext, nom: str) -> str:
    """[R5] Remet en service une parcelle inactive. LookupError si aucune parcelle inactive de ce nom."""
    require_role(ctx, "editor", "réactiver une parcelle")
    exacte, _ = _parcelles.find_doublon(db, _parcelles.normalize_parcelle_name(nom), potager_id=ctx.potager_id)
    if exacte is None or exacte.actif:
        raise LookupError(nom)
    svc_parcelles.modifier_parcelle(db, ctx, exacte.id, {"actif": True})
    log.info("[US-332] Parcelle %r réactivée (potager %s)", exacte.nom, ctx.potager_id)
    return f"Parcelle « {exacte.nom} » réactivée."


def supprimer(db: Session, ctx: TenantContext, nom: str) -> str:
    """[R4, CA3, CA5] Supprime RÉELLEMENT une parcelle vide ; sinon `ParcelleNonVideError`.

    LookupError si la parcelle n'existe pas dans ce potager. Le bilan est relu ici, au moment
    d'écrire : une culture plantée entre la proposition et la confirmation bloque la suppression.
    """
    require_role(ctx, "editor", "supprimer une parcelle")
    parcelle = _trouver(db, ctx, nom)
    if parcelle is None:
        raise LookupError(nom)
    b = bilan(db, ctx, parcelle)
    if not b["vide"]:
        log.info("[US-332 / CA3] Suppression de %r refusée : %s geste(s), %s culture(s), %s lot(s)",
                 parcelle.nom, b["nb_gestes"], b["nb_cultures"], b["lots"])
        raise ParcelleNonVideError(message_refus(b), b)
    nom_supprime = parcelle.nom
    db.delete(parcelle)
    db.commit()
    log.info("[US-332 / CA5] Parcelle %r supprimée (potager %s)", nom_supprime, ctx.potager_id)
    return f"Parcelle « {nom_supprime} » supprimée."

"""app/services/anticipation_commande.py — Anticiper la conséquence ou la suite d'une commande [US-253]
-----------------------------------------------------------------------------------
Le compagnon exécute fidèlement ce qui est demandé ; ce module regarde l'état du potager
autour de la commande. Deux lectures, toutes deux calculées depuis les données, sans modèle (CA5) :

- `avertissements` : ce qui dépend de ce qu'on va supprimer ou archiver (CA1) — une
  INFORMATION ajoutée au récapitulatif, qui ne bloque rien ;
- `suite_suggeree` : l'étape qui manque après une commande exécutée (CA2) — une PROPOSITION,
  jamais une action : elle repasse par la confirmation habituelle (CA3), et au plus une par
  commande (CA4).

Ni l'un ni l'autre ne lève : l'anticipation est un confort, une panne de lecture ne doit pas
empêcher une commande d'être proposée ni d'être exécutée.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.services import interpreteur_commandes as interpreteur
from app.services import plan as svc_plan
from app.services import stock as svc_stock
from app.services.context import TenantContext

log = logging.getLogger("potager")

#: Au-delà, les cultures en place sont comptées plutôt que nommées (récapitulatif court).
NB_CULTURES_NOMMEES = 3


def _parcelle_de(db: Session, ctx: TenantContext, commande):
    """La parcelle visée par la commande, par son nom EXACT (jamais un voisin), ou None."""
    from utils.parcelles import find_doublon, normalize_parcelle_name

    nom = commande.valeurs.get("nom")
    if not nom:
        return None
    exact, _ = find_doublon(db, normalize_parcelle_name(nom), potager_id=ctx.potager_id)
    return exact


def _retire_la_parcelle(commande) -> bool:
    """Une suppression, ou un archivage (« mets hors service » : `actif=non`)."""
    if commande.forme.cle == ("parcelle", "supprimer"):
        return True
    if commande.forme.cle != ("parcelle", "modifier"):
        return False
    return interpreteur._valeur_de(commande.valeurs.get("modification") or "", "actif") in ("non", "false")


def _nombre(valeur: float) -> str:
    return str(int(valeur)) if float(valeur).is_integer() else f"{valeur:g}".replace(".", ",")


def _cultures_en_place(db: Session, ctx: TenantContext, parcelle) -> list[str]:
    """« 12 pieds de tomate » : ce que la parcelle porte encore, du plus au moins nombreux."""
    cle = interpreteur._cle_nom(parcelle.nom)
    portees = [
        entree
        for nom, entrees in svc_plan.get_occupation(db, ctx).items()
        if nom is not None and interpreteur._cle_nom(nom) == cle
        for entree in entrees
        if (entree.get("nb_plants") or 0) > 0
    ]
    portees.sort(key=lambda entree: -entree["nb_plants"])
    morceaux = []
    for entree in portees:
        unite = entree.get("unite") or "plants"
        if entree["nb_plants"] == 1 and unite.endswith("s"):
            unite = unite[:-1]
        morceaux.append(f"{_nombre(entree['nb_plants'])} {unite} de {entree['culture']}")
    return morceaux


def _lots_en_pepiniere(db: Session, ctx: TenantContext, parcelle) -> int:
    """Les lots qui ont encore des graines en germination ou des godets sur cette parcelle."""
    return sum(
        1
        for lot in svc_stock.calcul_lots_pepiniere(db, ctx)
        if (lot.get("emplacement") or {}).get("parcelle_id") == parcelle.id
        and ((lot.get("graines_en_germination") or 0) > 0 or (lot.get("stock_residuel_godet") or 0) > 0)
    )


def _enumeration(morceaux: list[str]) -> str:
    if len(morceaux) > NB_CULTURES_NOMMEES:
        reste = len(morceaux) - NB_CULTURES_NOMMEES
        morceaux = morceaux[:NB_CULTURES_NOMMEES] + [f"{reste} autre{'s' if reste > 1 else ''}"]
    return morceaux[0] if len(morceaux) == 1 else f"{', '.join(morceaux[:-1])} et {morceaux[-1]}"


def avertissements(db: Session, ctx: TenantContext, commande) -> list[str]:
    """[CA1] Ce qui dépend de la parcelle qu'on va supprimer ou archiver, en une ligne chacun.

    Vide pour toute autre commande, pour une parcelle introuvable, et quand rien n'en dépend.
    """
    try:
        if not isinstance(commande, interpreteur.CommandeInterpretee) or not _retire_la_parcelle(commande):
            return []
        parcelle = _parcelle_de(db, ctx, commande)
        if parcelle is None:
            return []
        lignes = []
        cultures = _cultures_en_place(db, ctx, parcelle)
        if cultures:
            verbe = "est" if len(cultures) == 1 and cultures[0].startswith("1 ") else "sont"
            lignes.append(f"⚠️ {_enumeration(cultures)} {verbe} encore en place sur cette parcelle")
        lots = _lots_en_pepiniere(db, ctx, parcelle)
        if lots:
            lignes.append(
                f"⚠️ {lots} lot{'s' if lots > 1 else ''} de pépinière "
                f"{'y sont' if lots > 1 else 'y est'} encore suivi{'s' if lots > 1 else ''}"
            )
        return lignes
    except Exception:  # noqa: BLE001 — une information de confort ne bloque jamais la commande
        log.exception("[US-253 / CA1] Dépendances de la commande illisibles")
        return []


def suite_suggeree(db: Session, ctx: TenantContext, commande) -> Optional["interpreteur.CommandeInterpretee"]:
    """[CA2, CA3, CA4] La suite à proposer APRÈS une commande exécutée, ou None.

    Aujourd'hui : une parcelle devenue pépinière sans type. Le calcul se fait sur l'état de la
    base APRÈS l'exécution — si la commande a échoué, ou si le type a été donné, il n'y a rien à
    suggérer. La suite est une commande de modification dont la valeur est une question à
    boutons : elle repasse par le récapitulatif et la confirmation habituels.
    """
    try:
        if not isinstance(commande, interpreteur.CommandeInterpretee):
            return None
        if commande.forme.cle != ("parcelle", "modifier"):
            return None
        if interpreteur._valeur_de(commande.valeurs.get("modification") or "", "pepiniere") is None:
            return None
        parcelle = _parcelle_de(db, ctx, commande)
        if parcelle is None or not parcelle.est_pepiniere or parcelle.type_pepiniere:
            return None
        from app.services import vocabulaire_parcelle as vocabulaire

        carac = vocabulaire.caracteristique("pepiniere")
        nom = interpreteur._md_simple(parcelle.nom)
        precision = interpreteur.PrecisionDemandee(
            mot="", caracteristique=carac.cle, libelle="type de pépinière", options=carac.valeurs,
            invite=(
                f"*{nom}* est une pépinière sans type : "
                f"*{'* ou *'.join(carac.valeurs)}* ? Vous pouvez aussi le préciser plus tard."
            ),
        )
        return interpreteur.CommandeInterpretee(
            commande=commande.commande,
            sous_commande=commande.sous_commande,
            forme=commande.forme,
            valeurs={"nom": parcelle.nom},
            origine=interpreteur.ORIGINE_REGLE,
            confiance=1.0,
            regle=interpreteur.REGLE_ANTICIPATION,
            precision=precision,
        )
    except Exception:  # noqa: BLE001 — une suggestion de confort ne casse jamais une commande exécutée
        log.exception("[US-253 / CA2] Suite de la commande illisible")
        return None

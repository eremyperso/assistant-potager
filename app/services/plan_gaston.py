"""app/services/plan_gaston.py — Ce que le plan demande à Gaston [US-332, US-333]
==================================================================================
Deux demandes partent de l'écran du plan et passent par une carte de confirmation, jamais par une
écriture directe :

- **Créer** (US-333 / E3) : poser une forme NOUVELLE dans l'éditeur. La carte dit « Créer une planche
  de 3,5 × 3 m, rangs dans la longueur, à l'endroit posé » ; rien n'existe avant « Confirmer ».
- **Retirer** (US-332 / R2-R4) : « Rendre inactive ou supprimer… ». Gaston vérifie les cultures et
  l'historique ; une parcelle qui a vécu se rend inactive, une parcelle vide se supprime.

La demande devient une `CommandeInterpretee` du catalogue (`/parcelle ajouter`, `/parcelle supprimer`
ou `/parcelle modifier … actif=non`) — la même que dicterait le jardinier, rangée comme toute commande
(journal, carte, double canal). Aucun modèle de langage n'y intervient.

La géométrie d'une création voyage dans `valeurs["geometrie"]` : des `clé=valeur` séparés par des
espaces, comme `modification`. Elle n'est pas un argument du catalogue : le bot et l'agent ne la
connaissent pas, seule l'exécution PWA l'applique (`agent.executeurs`).
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.services import geometrie as svc_geometrie
from app.services import interpreteur_commandes as interpreteur
from app.services import retrait_parcelle as svc_retrait
from app.services.context import TenantContext
from app.services.menu_commandes import FORMES_PAR_CLE
from app.services.parcelles import get_parcelle
from utils import parcelles as _parcelles

log = logging.getLogger("potager")

ACTION_CREER = "creer"
ACTION_RETIRER = "retirer"
REGLE = "plan_editeur"

#: Les champs de géométrie d'une création, dans l'ordre où la carte les dit.
CHAMPS_CREATION: tuple[str, ...] = (
    "forme", "longueur_m", "largeur_m", "x_m", "y_m", "rotation_deg", "sens_rangs", "nb_rangs",
)
#: Le libellé d'une forme, pour nommer la parcelle (« Planche 9 »).
NOMS_DE_FORME = {"planche": "Planche", "bac": "Bac", "butte": "Butte", "serre": "Serre", "pepiniere": "Pépinière"}
ARTICLES_DE_FORME = {"planche": "une", "bac": "un", "butte": "une", "serre": "une", "pepiniere": "une"}


class DemandePlanInvalideError(ValueError):
    """La demande du plan est mal formée (422)."""


# ── Codec de la géométrie ────────────────────────────────────────────────────
def encoder(champs: dict) -> str:
    """`{"forme": "planche", "longueur_m": 3.5}` → « forme=planche longueur_m=3.5 »."""
    return " ".join(f"{cle}={champs[cle]}" for cle in CHAMPS_CREATION if champs.get(cle) is not None)


def decoder(texte: Optional[str]) -> dict:
    """L'inverse d'`encoder` ; une valeur numérique redevient un nombre."""
    champs: dict = {}
    for morceau in (texte or "").split():
        cle, signe, valeur = morceau.partition("=")
        if not signe or cle not in CHAMPS_CREATION:
            continue
        try:
            champs[cle] = int(valeur) if cle == "nb_rangs" else float(valeur) if cle.endswith(("_m", "_deg")) else valeur
        except ValueError:
            champs[cle] = valeur
    return champs


def _m(valeur: float) -> str:
    return f"{valeur:g}".replace(".", ",")


def decrire(champs: dict) -> str:
    """« une planche de 3,5 × 3 m · 10,5 m², rangs dans la longueur, à l'endroit posé »."""
    forme = (champs.get("forme") or "planche").lower()
    nom_forme = NOMS_DE_FORME.get(forme, forme.capitalize())
    longueur, largeur = champs.get("longueur_m"), champs.get("largeur_m")
    dim = ""
    if longueur and largeur:
        superficie = svc_geometrie.superficie_posee(longueur, largeur)
        dim = f" de {_m(longueur)} × {_m(largeur)} m · {_m(superficie)} m²"
    sens = champs.get("sens_rangs")
    rangs = (f", rangs {'dans la longueur' if sens == svc_geometrie.SENS_LONGUEUR else 'en travers'}") if sens else ""
    nb = f" ({champs['nb_rangs']} rangs)" if champs.get("nb_rangs") else ""
    lieu = ", à l'endroit posé" if champs.get("x_m") is not None else ""
    return f"{ARTICLES_DE_FORME.get(forme, 'une')} {nom_forme.lower()}{dim}{rangs}{nb}{lieu}"


# ── Nom proposé ──────────────────────────────────────────────────────────────
def nom_propose(db: Session, ctx: TenantContext, forme: str) -> str:
    """[CA2] « Planche 9 » : unique dans le potager (les parcelles inactives gardent leur nom)."""
    from database.models import Parcelle

    base = NOMS_DE_FORME.get((forme or "planche").lower(), "Planche")
    n = db.query(Parcelle).filter(Parcelle.potager_id == ctx.potager_id).count() + 1
    while _parcelles.find_doublon(db, _parcelles.normalize_parcelle_name(f"{base} {n}"), potager_id=ctx.potager_id)[0]:
        n += 1
    return f"{base} {n}"


# ── Les commandes ────────────────────────────────────────────────────────────
def lire_demande(brut: Optional[dict]) -> Optional[dict]:
    """La demande envoyée par la PWA, normalisée ; None si absente. Lève `DemandePlanInvalideError`."""
    if brut is None:
        return None
    if not isinstance(brut, dict) or brut.get("action") not in (ACTION_CREER, ACTION_RETIRER):
        raise DemandePlanInvalideError("Demande du plan mal formée.")
    return brut


def commande_de_creation(db: Session, ctx: TenantContext, brut: dict):
    """[US-332 / R1, CA2] `/parcelle ajouter <nom proposé>` + la géométrie posée, validée AVANT la carte."""
    champs = {cle: brut[cle] for cle in CHAMPS_CREATION if brut.get(cle) is not None}
    try:
        svc_geometrie.valider_geometrie_parcelle(
            {c: champs[c] for c in ("forme", "x_m", "y_m", "largeur_m", "rotation_deg", "sens_rangs") if c in champs})
    except svc_geometrie.GeometrieInvalideError as e:
        raise DemandePlanInvalideError(str(e)) from None
    nom = (brut.get("nom") or "").strip() or nom_propose(db, ctx, champs.get("forme", "planche"))
    valeurs = {"nom": nom, "geometrie": encoder(champs)}
    longueur, largeur = champs.get("longueur_m"), champs.get("largeur_m")
    if longueur and largeur:
        valeurs["superficie"] = f"{svc_geometrie.superficie_posee(longueur, largeur):g}"
    return interpreteur.CommandeInterpretee(
        commande="parcelle", sous_commande="ajouter", forme=FORMES_PAR_CLE[("parcelle", "ajouter")],
        valeurs=valeurs, origine=interpreteur.ORIGINE_REGLE, confiance=1.0, regle=REGLE,
        texte_origine=f"Créer {decrire(champs)}",
    )


def commande_de_retrait(db: Session, ctx: TenantContext, brut: dict):
    """[US-332 / R2-R4] Une parcelle qui a vécu se rend inactive ; une parcelle vide se supprime.

    Rend `(commande, bilan)`. LookupError si la parcelle n'existe pas dans ce potager.
    """
    parcelle = get_parcelle(db, ctx, int(brut.get("parcelle_id") or 0))
    if parcelle is None or not parcelle.actif:
        raise LookupError(brut.get("parcelle_id"))
    b = svc_retrait.bilan(db, ctx, parcelle)
    if b["vide"]:
        sous, valeurs = "supprimer", {"nom": parcelle.nom}
    else:
        sous, valeurs = "modifier", {"nom": parcelle.nom, "modification": "actif=non"}
    commande = interpreteur.CommandeInterpretee(
        commande="parcelle", sous_commande=sous, forme=FORMES_PAR_CLE[("parcelle", sous)],
        valeurs=valeurs, origine=interpreteur.ORIGINE_REGLE, confiance=1.0, regle=REGLE,
        texte_origine=f"Rendre inactive ou supprimer {parcelle.nom}",
    )
    return commande, b


def phrase_de_retrait(b: dict) -> str:
    """Ce que Gaston dit avant la carte : il a vérifié, et il explique son choix (R3, CA3)."""
    if b["vide"]:
        return f"« {b['nom']} » n'a ni culture ni historique : je peux la supprimer, c'est définitif."
    return (
        f"« {b['nom']} » a {svc_retrait.ce_quelle_porte(b)} : je ne la supprime pas, pour ne pas perdre sa "
        "rotation. Je te propose de la rendre inactive : elle reste sur le plan, grisée, avec son historique."
    )


def lignes_de_carte(db: Session, ctx: TenantContext, commande) -> list[str]:
    """Les lignes que la carte ajoute au résumé : la géométrie d'une création, le bilan d'un retrait."""
    cle = commande.forme.cle
    if cle == ("parcelle", "ajouter") and commande.valeurs.get("geometrie"):
        return [f"Créer {decrire(decoder(commande.valeurs['geometrie']))}"]
    est_retrait = cle == ("parcelle", "supprimer") or (
        cle == ("parcelle", "modifier") and (commande.valeurs.get("modification") or "").strip() == "actif=non")
    if not est_retrait:
        return []
    exacte, _ = _parcelles.find_doublon(
        db, _parcelles.normalize_parcelle_name(commande.valeurs.get("nom", "")), potager_id=ctx.potager_id)
    if exacte is None or not exacte.actif:
        return []
    b = svc_retrait.bilan(db, ctx, exacte)
    lignes = svc_retrait.lignes_du_bilan(b)
    if cle == ("parcelle", "supprimer") and not b["vide"]:
        lignes.insert(0, "⚠️ Elle ne sera pas supprimée : elle a des cultures ou un historique.")
    return lignes

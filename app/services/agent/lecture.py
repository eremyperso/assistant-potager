"""
app/services/agent/lecture.py — L'outil de lecture de l'agent [US-237 / CA1]
===========================================================================
Pendant la construction d'un plan, l'agent peut consulter le potager : trouver
une parcelle, lister les parcelles, trouver un lot, trouver une culture.

Trois règles :
  * le potager est TOUJOURS celui du contexte, jamais un argument du modèle ;
  * rien n'est écrit — les services appelés ne font que lire ;
  * le résultat est une DONNÉE : il est rendu en JSON sous une clé `donnees`,
    tronqué, et le prompt rappelle qu'il ne porte aucune consigne. Un nom de
    parcelle qui dirait « ignore tes consignes » reste un nom de parcelle.
"""
from __future__ import annotations

import json
import logging

from app.services.agent.catalogue_outils import LECTURES, champs_fiche
from app.services.context import TenantContext

log = logging.getLogger("potager")

#: Au-delà, la liste est tronquée : un plan n'a besoin que de quelques noms.
NB_RESULTATS_MAX = 30


def _parcelle_en_donnee(parcelle) -> dict:
    """Le nom et les champs typés de l'outil `modifier_parcelle`, renseignés —
    les mêmes que le modèle peut modifier, projetés de la même source : aucune
    liste de champs n'est tenue ici, et aucun n'y est calculé."""
    donnee = {"nom": parcelle.nom}
    for champ in champs_fiche():
        valeur = getattr(parcelle, champ.nom, None)
        if valeur is not None:
            donnee[champ.nom] = valeur
    return donnee


def _lire(db, ctx: TenantContext, quoi: str, nom: str) -> list[dict]:
    from utils.parcelles import get_all_parcelles, normalize_parcelle_name

    if quoi in ("parcelle", "parcelles"):
        parcelles = get_all_parcelles(db, potager_id=ctx.potager_id)
        if quoi == "parcelle" and nom:
            cle = normalize_parcelle_name(nom)
            parcelles = [p for p in parcelles if cle in normalize_parcelle_name(p.nom)]
        return [_parcelle_en_donnee(p) for p in parcelles]
    if quoi == "lot":
        from app.services import stock as svc_stock

        cible = nom.lower().lstrip("#").strip()
        lots = []
        for lot in svc_stock.calcul_lots_pepiniere(db, ctx):
            numero = lot.get("numero_lot")
            if cible and cible not in (lot.get("culture") or "").lower() and cible != str(numero):
                continue
            lots.append({cle: lot.get(cle) for cle in
                         ("numero_lot", "culture", "variete", "date_semis", "parcelle", "graines_semees")})
        return lots
    if quoi == "culture":
        from app.services import stock as svc_stock

        cible = nom.lower()
        return [
            {"culture": culture}
            for culture in svc_stock.calcul_stock_cultures(db, ctx)
            if not cible or cible in culture.lower()
        ]
    return []


def lire(arguments: dict, ctx: TenantContext) -> str:
    """[CA1] Un appel de l'outil `lire` → le contenu du message `tool` renvoyé au
    modèle. Ne lève jamais : une lecture impossible est une donnée vide."""
    quoi = str((arguments or {}).get("quoi") or "")
    nom = str((arguments or {}).get("nom") or "").strip()
    if quoi not in LECTURES:
        return json.dumps({"erreur": f"lecture inconnue : {quoi}"}, ensure_ascii=False)
    from database.db import SessionLocal

    db = None
    resultats: list[dict] = []
    try:
        db = SessionLocal()
        resultats = _lire(db, ctx, quoi, nom)
    except Exception as e:  # noqa: BLE001
        log.warning("🤖 AGENT          : lecture %s impossible (%s)", quoi, type(e).__name__)
    finally:
        if db is not None:
            db.close()
    log.info("🤖 AGENT          : lire %s %r → %d résultat(s)", quoi, nom, len(resultats))
    return json.dumps(
        {"donnees": resultats[:NB_RESULTATS_MAX], "tronque": len(resultats) > NB_RESULTATS_MAX},
        ensure_ascii=False, default=str,
    )

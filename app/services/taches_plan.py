"""
[US-328] « Aujourd'hui au potager » — ce qui est à confirmer, à libérer et à placer.

Le panneau de droite du Plan (et les deux boutons du mobile, US-329) lisent ces trois
listes telles quelles : elles sont calculées ICI, à la date de référence, depuis la
réponse de `GET /plan` déjà construite — aucune lecture de plus pour « à confirmer » et
« à libérer », et les comptes ne peuvent pas diverger des filtres du plan (CA2) :

- « À confirmer » suit la MÊME règle que `plan.compteurs_filtres` (pépinières exclues,
  `etapes.a_confirmer`) ;
- « À libérer » reprend les cultures terminées dont le rang n'est pas libéré (US-320, E8) ;
- « À placer » regroupe les lots de pépinière prêts à planter (US-217) et les cultures sans
  parcelle (ancienne carte « Cultures non localisées », US-200 / V17) : elles sont LISTÉES,
  jamais dessinées comme un lieu (CA3).
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("potager")

#: [CA3] D'où vient une carte « À placer ».
ORIGINE_LOT = "lot"
ORIGINE_SANS_PARCELLE = "sans_parcelle"

#: L'étape « terminée » d'US-320 : sa date est la date de fin d'une culture à libérer.
ETAPE_TERMINEE = "terminee"


def _premier_rang(culture: dict) -> Optional[int]:
    """Le premier rang qu'occupe la culture, ou None (rangs non numérotés)."""
    rangs = [r for r in (culture.get("numeros_rangs") or []) if isinstance(r, int)]
    return min(rangs) if rangs else None


def _date_de_fin(etapes: dict) -> Optional[str]:
    """[A3] La date de l'étape « terminée », sinon celle de l'étape courante."""
    for e in etapes.get("etapes") or []:
        if e.get("code") == ETAPE_TERMINEE and e.get("date"):
            return e["date"]
    return etapes.get("etape_date")


def a_confirmer(parcelles: list[dict]) -> list[dict]:
    """[A2, CA2] Une ligne par culture en place dont l'étape prévue est due."""
    lignes: list[dict] = []
    for p in parcelles:
        if p.get("est_pepiniere"):
            continue   # même règle que le filtre « À confirmer » du plan
        for c in p.get("cultures") or []:
            etapes = c.get("etapes") or {}
            if not etapes.get("a_confirmer"):
                continue
            lignes.append({
                "parcelle_id": p["id"],
                "parcelle": p.get("nom"),
                "rang": _premier_rang(c),
                "culture": c.get("culture"),
                "variete": c.get("variete"),
                "etape": etapes.get("etape"),
                "etape_libelle": etapes.get("etape_libelle"),
                "etape_date": etapes.get("etape_date"),
                "etapes": etapes,
            })
    return lignes


def a_liberer(parcelles: list[dict]) -> list[dict]:
    """[A3] Une ligne par culture terminée dont le rang n'est pas libéré, avec sa date de fin."""
    lignes: list[dict] = []
    for p in parcelles:
        for l in p.get("a_liberer") or []:
            lignes.append({
                "parcelle_id": p["id"],
                "parcelle": p.get("nom"),
                "rang": None,
                "culture": l.get("culture"),
                "variete": l.get("variete"),
                "fin_le": _date_de_fin(l),
                "etapes": {k: v for k, v in l.items() if k not in ("parcelle_id", "parcelle_nom", "culture", "variete")},
            })
    return lignes


def a_placer(lots_prets: list[dict], non_localisees: list[dict]) -> list[dict]:
    """[A4, CA3] Les lots prêts à planter, puis les cultures sans parcelle."""
    cartes: list[dict] = [
        {
            "origine": ORIGINE_LOT,
            "lot_id": lot.get("lot_id"),
            "numero_lot": lot.get("numero_lot"),
            "culture": lot.get("culture"),
            "variete": lot.get("variete"),
            "quantite": lot.get("quantite"),
            "unite": "plants",
            "pepiniere": lot.get("pepiniere"),
        }
        for lot in lots_prets
    ]
    cartes += [
        {
            "origine": ORIGINE_SANS_PARCELLE,
            "lot_id": None,
            "numero_lot": None,
            "culture": c.get("culture"),
            "variete": c.get("variete"),
            "quantite": c.get("nb_plants"),
            "unite": c.get("unite") or "plants",
            "pepiniere": None,
        }
        for c in non_localisees
    ]
    return cartes


def taches_du_jour(parcelles: list[dict], non_localisees: list[dict], lots_prets: list[dict]) -> dict:
    """[US-328 / CA1-CA3] Les trois listes du panneau « Aujourd'hui au potager », et leurs comptes."""
    taches = {
        "a_confirmer": a_confirmer(parcelles),
        "a_liberer": a_liberer(parcelles),
        "a_placer": a_placer(lots_prets, non_localisees),
    }
    taches["comptes"] = {cle: len(liste) for cle, liste in taches.items()}
    log.info(
        "[US-328] Aujourd'hui au potager : à confirmer=%d à libérer=%d à placer=%d",
        *(taches["comptes"][c] for c in ("a_confirmer", "a_liberer", "a_placer")),
    )
    return taches

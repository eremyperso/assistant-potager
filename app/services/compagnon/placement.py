"""
app/services/compagnon/placement.py — placer une carte « À placer » sur un rang libre [US-328]
=============================================================================================
Glisser une carte « À placer » (un lot de pépinière prêt, une culture sans parcelle) sur un
rang libre du plan n'écrit rien (CA4) : la PWA ouvre Gaston, qui reçoit le rang en contexte
d'écran (US-323 : parcelle + rang) et la carte en `placement`. Ce module en fait, SANS modèle
de langage, l'item d'une plantation :

* la parcelle et le rang viennent du contexte VÉRIFIÉ (jamais du client) ;
* la part du rang (US-326 / P4) : un rang libre partagé n'en offre qu'une fraction — elle
  devient `rang_longueur_m`, mesurée par `geometrie.longueur_de_la_part`, sinon le rang entier ;
* pour un lot, son numéro (`numero_lot_cite`) : `lots_pepiniere.resoudre_references` rattache
  la plantation aux godets du lot (US-209), comme une phrase « plante le lot 42 » (CA5).

L'item passe ensuite les MÊMES contrôles que tout geste (`gestes_conversation.controler`) et
devient une carte « À enregistrer » : seule la confirmation écrit.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from app.services.compagnon.contexte_ecran import ContexteEcran
from app.services.compagnon.noter import Lecture

log = logging.getLogger("potager")

TEXTE_SANS_RANG = "Sur quel rang ? Glissez la carte sur un rang libre du plan, ou dites-le à Gaston."
TEXTE_SANS_CULTURE = "Je ne sais pas quoi placer : la carte n'a pas de culture."

class PlacementInvalideError(ValueError):
    """La carte à placer est mal formée (422)."""


def _quantite(valeur) -> Optional[float]:
    try:
        q = float(valeur)
    except (TypeError, ValueError):
        return None
    if q <= 0:
        return None
    return int(q) if q.is_integer() else q


def lire_placement(brut: Optional[dict]) -> Optional[dict]:
    """La carte envoyée par la PWA, normalisée ; None si absente. Lève `PlacementInvalideError`."""
    if brut is None:
        return None
    if not isinstance(brut, dict):
        raise PlacementInvalideError("Carte à placer mal formée.")
    part = brut.get("part")
    if part is not None:
        try:
            part = float(part)
        except (TypeError, ValueError):
            raise PlacementInvalideError("Part de rang invalide.") from None
        if not 0 < part <= 1:
            raise PlacementInvalideError("Part de rang invalide : entre 0 et 1.")
    numero = brut.get("numero_lot")
    if numero is not None:
        try:
            numero = int(numero)
        except (TypeError, ValueError):
            raise PlacementInvalideError("Numéro de lot invalide.") from None
    return {
        "culture": (brut.get("culture") or "").strip() or None,
        "variete": (brut.get("variete") or "").strip() or None,
        "quantite": _quantite(brut.get("quantite")),
        "unite": (brut.get("unite") or "plants").strip() or "plants",
        "numero_lot": numero,
        "part": part,
    }


def phrase_de_placement(placement: dict, contexte: ContexteEcran) -> str:
    """[Gherkin] « Placer 12 fraisiers Mara des bois · Planche haricots, rang 2 »."""
    quoi = " ".join(str(x) for x in (
        placement.get("quantite"), placement.get("culture"), placement.get("variete"),
    ) if x)
    lieu = contexte.parcelle + (f", rang {contexte.rang}" if contexte.rang else "")
    return f"Placer {quoi} · {lieu}"


def items_du_placement(
    placement: dict, contexte: Optional[ContexteEcran], longueur_part: Optional[float] = None,
) -> Lecture:
    """[US-328 / CA4, CA5] L'item de plantation d'une carte posée sur un rang, sans modèle.

    `longueur_part` : la part du rang en mètres (`geometrie.longueur_de_la_part`), None = rang entier.
    """
    if not placement.get("culture"):
        return Lecture(precision=TEXTE_SANS_CULTURE)
    if contexte is None or not contexte.rang:
        return Lecture(precision=TEXTE_SANS_RANG)
    item = {
        "action": "plantation",
        "culture": placement["culture"],
        "variete": placement.get("variete"),
        "parcelle": contexte.parcelle,
        "quantite": placement.get("quantite"),
        "unite": placement.get("unite") or "plants",
        "rang": None,                         # un multiplicateur, pas une position
        "rang_position": contexte.rang,       # [US-326] le rang où l'on plante
        "rang_longueur_m": longueur_part,
        "date": date.today().isoformat(),
        "commentaire": None,
        "origine_parsing": "placement",
    }
    if placement.get("numero_lot") is not None:
        item["numero_lot_cite"] = placement["numero_lot"]
    log.info("[US-328] Placement proposé : %s", phrase_de_placement(placement, contexte))
    return Lecture(items=[item])

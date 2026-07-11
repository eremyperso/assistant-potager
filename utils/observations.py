"""
utils/observations.py — [US-039] Routage des observations (US-038) vers Plan / Stocks.

Règle de routage (décidée avec le PO — révision exclusive) :
  1. culture ET variete renseignés  → toujours une LIGNE CULTURE (jamais l'icône parcelle) :
       - parcelle_id déjà renseigné sur la note → cette parcelle directement
       - parcelle_id absent → résolution dynamique via calcul_occupation_parcelles :
           plantée dans UNE seule parcelle actuellement → cette parcelle
           plantée dans 0 ou plusieurs parcelles → repli sur Stocks (cas 2)
  2. culture renseignée SANS variete (parcelle_id renseigné ou non) → toujours Stocks
       (agrégat culture — pas assez précis pour cibler une ligne dans Plan)
  3. aucune culture, parcelle_id renseigné → icône PARCELLE (header) uniquement
  4. ni parcelle_id ni culture → hors périmètre (reste dans Historique)

Une même observation n'apparaît jamais à deux endroits (Plan/Stocks mutuellement
exclusifs, et au sein de Plan : parcelle OU ligne culture, jamais les deux).
"""
import re
from collections import defaultdict
from datetime import datetime

from database.models import Evenement

_CATEGORIE_RE = re.compile(r"^\[([^\]]+)\]\s*")


def strip_categorie(commentaire: str | None) -> str:
    """Retire le préfixe '[Catégorie] ' ajouté par la saisie guidée US-038."""
    if not commentaire:
        return ""
    return _CATEGORIE_RE.sub("", commentaire).strip()


def _serialize(ev: Evenement) -> dict:
    return {
        "date":  ev.date.strftime("%d/%m") if ev.date else "",
        "texte": strip_categorie(ev.commentaire),
    }


def _sorted_serialized(events: list[Evenement]) -> list[dict]:
    events_sorted = sorted(events, key=lambda e: e.date or datetime.min, reverse=True)
    return [_serialize(e) for e in events_sorted]


def _resolve_parcelle_unique(occupation: dict, parcelle_id_par_nom: dict, culture: str, variete: str) -> int | None:
    """Retourne l'id de LA parcelle si culture+variete y est planté dans une seule parcelle actuellement."""
    matches = [
        nom for nom, cultures in occupation.items()
        if any(
            (c.get("culture") or "").lower() == culture.lower()
            and (c.get("variete") or "") == variete
            for c in cultures
        )
    ]
    if len(matches) == 1:
        return parcelle_id_par_nom.get(matches[0])
    return None


def build_observations_index(db) -> dict:
    """
    [US-039 / CA1-CA6] Construit en une seule passe l'index de routage :
      - "parcelle"    : {parcelle_id: [obs...]}                          → header carte parcelle (Plan)
      - "culture_row" : {(parcelle_id, culture_lower, variete): [obs...]} → ligne culture (Plan)
      - "stocks"      : {culture_lower: [obs...]}                        → ligne culture agrégée (Stocks)
    """
    from utils.parcelles import calcul_occupation_parcelles, get_all_parcelles

    events = (
        db.query(Evenement)
        .filter(Evenement.type_action == "observation")
        .all()
    )

    parcelle_map = defaultdict(list)
    culture_row_map = defaultdict(list)
    stocks_map = defaultdict(list)

    # [CA4] Occupation actuelle, réutilisée pour résoudre les notes culture+variete
    # sans parcelle_id — calculée une seule fois, indépendamment du nombre d'events.
    occupation = calcul_occupation_parcelles(db)
    parcelle_id_par_nom = {p.nom: p.id for p in get_all_parcelles(db)}

    for e in events:
        if e.culture and e.variete:
            # Cas 1 : culture+variete précis → toujours une ligne culture, jamais l'icône parcelle
            target_pid = e.parcelle_id
            if target_pid is None:
                target_pid = _resolve_parcelle_unique(occupation, parcelle_id_par_nom, e.culture, e.variete)
            if target_pid is not None:
                culture_row_map[(target_pid, e.culture.lower(), e.variete)].append(e)
            else:
                stocks_map[e.culture.lower()].append(e)
        elif e.culture:
            # Cas 2 : culture sans variete → Stocks, que parcelle_id soit renseigné ou non
            stocks_map[e.culture.lower()].append(e)
        elif e.parcelle_id is not None:
            # Cas 3 : ni culture ni variete, mais une parcelle → icône parcelle
            parcelle_map[e.parcelle_id].append(e)
        # Cas 4 : ni parcelle_id ni culture → hors périmètre, ignoré (reste dans Historique)

    return {
        "parcelle":    {k: _sorted_serialized(v) for k, v in parcelle_map.items()},
        "culture_row": {k: _sorted_serialized(v) for k, v in culture_row_map.items()},
        "stocks":      {k: _sorted_serialized(v) for k, v in stocks_map.items()},
    }

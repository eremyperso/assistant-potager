"""
utils/altitude.py — Altitude d'un point, par l'API d'élévation Open-Meteo [US-193]
---------------------------------------------------------------------------------
Même fournisseur que la météo (utils/meteo.py) et la recherche de ville de la
PWA (VilleSearch.jsx) : gratuit, sans clé. Sert à la REPRISE des potagers
localisés avant US-193 (CA3) ; un potager localisé depuis reçoit son altitude
avec sa ville, sans passer par ici.

Jamais bloquant : une panne réseau rend des `None`, la zone déduite reste alors
celle de la seule position — jamais « montagnard » supposé.
"""
import logging
from typing import Optional

import requests

log = logging.getLogger("potager")

OPEN_METEO_ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"
#: Limite de points par requête de l'API d'élévation.
POINTS_PAR_REQUETE = 100


def altitudes_depuis_coordonnees(points: list[tuple[float, float]]) -> list[Optional[float]]:
    """[US-193 / CA3] Une altitude (m) par (latitude, longitude), `None` si inconnue."""
    resultat: list[Optional[float]] = []
    for debut in range(0, len(points), POINTS_PAR_REQUETE):
        lot = points[debut:debut + POINTS_PAR_REQUETE]
        params = {
            "latitude": ",".join(str(lat) for lat, _ in lot),
            "longitude": ",".join(str(lon) for _, lon in lot),
        }
        try:
            resp = requests.get(OPEN_METEO_ELEVATION_URL, params=params, timeout=10)
            resp.raise_for_status()
            elevations = resp.json().get("elevation") or []
        except (requests.RequestException, ValueError) as err:
            log.warning("[US-193] Altitude indisponible pour %d point(s) : %s", len(lot), err)
            elevations = []
        if len(elevations) != len(lot):
            elevations = [None] * len(lot)
        resultat.extend(float(e) if isinstance(e, (int, float)) else None for e in elevations)
    return resultat

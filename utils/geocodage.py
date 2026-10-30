"""
utils/geocodage.py — Retrouver un lieu par son nom
==================================================
Géocodage Open-Meteo (gratuit, sans clé) : le même service, avec les mêmes paramètres,
que la recherche de ville du frontend (`frontend/src/components/ui/VilleSearch.jsx`),
pour qu'un lieu dit au compagnon et une ville choisie à l'écran se résolvent pareil.

Aucun état, aucune base : un nom entre, des lieux sortent. Les résultats sont rendus dans
l'ordre d'Open-Meteo (le plus peuplé d'abord) — le premier est « le » lieu quand le nom est
ambigu, et l'appelant le dit au jardinier.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

log = logging.getLogger("potager")

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
NB_RESULTATS = 6
TIMEOUT_S = 8
TIMEZONE_PAR_DEFAUT = "Europe/Paris"


@dataclass(frozen=True)
class Lieu:
    """Un lieu trouvé par son nom."""

    nom: str
    latitude: float
    longitude: float
    region: Optional[str] = None
    pays: Optional[str] = None
    timezone: str = TIMEZONE_PAR_DEFAUT

    def libelle(self) -> str:
        """« Lyon, Auvergne-Rhône-Alpes, France » : de quoi voir de quel Lyon il s'agit."""
        return ", ".join(p for p in (self.nom, self.region, self.pays) if p)


def chercher_lieu(nom: str, langue: str = "fr") -> Optional[list[Lieu]]:
    """Les lieux qui portent ce nom, du plus peuplé au moins peuplé.

    Retourne `[]` quand rien ne porte ce nom, et `None` quand le service est injoignable :
    « je ne connais pas ce lieu » et « je n'ai pas pu chercher » ne se disent pas pareil.
    """
    recherche = (nom or "").strip()
    if len(recherche) < 2:
        return []
    debut = time.perf_counter()
    try:
        reponse = requests.get(
            GEOCODING_URL,
            params={"name": recherche, "count": NB_RESULTATS, "language": langue, "format": "json"},
            timeout=TIMEOUT_S,
        )
        reponse.raise_for_status()
        corps = reponse.json()
    except (requests.RequestException, ValueError) as e:
        log.warning("🧭 GÉOCODAGE      : %r → injoignable (%s)", recherche, type(e).__name__)
        return None
    lieux: list[Lieu] = []
    for entree in corps.get("results") or []:
        try:
            lieux.append(Lieu(
                nom=str(entree["name"]),
                latitude=float(entree["latitude"]),
                longitude=float(entree["longitude"]),
                region=entree.get("admin1"),
                pays=entree.get("country"),
                timezone=entree.get("timezone") or TIMEZONE_PAR_DEFAUT,
            ))
        except (KeyError, TypeError, ValueError):
            continue  # une entrée malformée ne fait pas perdre les autres
    log.info(
        "🧭 GÉOCODAGE      : %r → %d lieu(x) │ %d ms │ 1er : %s",
        recherche, len(lieux), int((time.perf_counter() - debut) * 1000),
        lieux[0].libelle() if lieux else "-",
    )
    return lieux

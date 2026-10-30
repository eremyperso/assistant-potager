"""
app/services/meteo_lieu.py — La météo d'un autre lieu que le potager
====================================================================
« Quel temps fait-il à Lyon ? » : la météo du jour d'une ville que le jardinier nomme, quand
elle n'est pas celle de son potager. Lecture seule : rien n'est enregistré, ni observation ni
cache — la météo d'un potager (`utils.meteo.save_meteo_observation`) reste celle de SON
potager, et le journal météo ne se pollue pas d'un lieu de passage.

Le service nomme le lieu retenu avec sa région et son pays : un nom ambigu (« Lyon » existe
ailleurs qu'en France) se voit dans la réponse, il n'est jamais choisi en silence.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from unidecode import unidecode

from utils import geocodage
from utils.geocodage import Lieu
from utils.meteo import fetch_meteo, format_meteo_commentaire

log = logging.getLogger("potager")


class LieuIntrouvable(Exception):
    """Aucun lieu ne porte ce nom."""


class ServiceIndisponible(Exception):
    """Le géocodage ou la météo n'a pas répondu : réessayer plus tard."""


@dataclass(frozen=True)
class MeteoLieu:
    lieu: Lieu
    meteo: dict
    #: Les autres lieux de même nom, pour dire qu'il y en a (« Lyon » ailleurs qu'en France).
    autres: tuple[Lieu, ...] = ()

    def commentaire(self) -> str:
        return format_meteo_commentaire(self.meteo)

    def homonymes(self) -> str:
        """« Il existe aussi : Lyon, Ontario, Canada ; … » — vide quand le nom est sans équivoque."""
        return " ; ".join(autre.libelle() for autre in self.autres[:2])


def _cle(nom: str) -> str:
    """Le nom sans casse, accents ni tirets : « Saint-Étienne » = « saint etienne »."""
    return " ".join(re.findall(r"[a-z0-9]+", unidecode(nom or "").lower()))


def meteo_du_lieu(nom: str) -> MeteoLieu:
    """La météo du jour du lieu `nom`.

    Lève `LieuIntrouvable` si rien ne porte ce nom, `ServiceIndisponible` si le géocodage
    ou la prévision n'a pas répondu. Ne lit ni n'écrit la base.
    """
    lieux = geocodage.chercher_lieu(nom)
    if lieux is None:
        raise ServiceIndisponible("géocodage injoignable")
    if not lieux:
        raise LieuIntrouvable(nom)
    lieu = lieux[0]
    meteo = fetch_meteo(lieu.latitude, lieu.longitude, lieu.timezone)
    if meteo is None:
        raise ServiceIndisponible("prévision injoignable")
    # Les homonymes : le MÊME nom ailleurs (autre région ou autre pays) — ni « Lyons », ni
    # « Saint-Étienne-du-Rouvray », que le géocodage rend aussi, ni le doublon d'une même ville.
    autres = tuple(
        l for l in lieux[1:]
        if _cle(l.nom) == _cle(lieu.nom) and (l.pays, l.region) != (lieu.pays, lieu.region)
    )
    log.info("🌤️  MÉTÉO AILLEURS  : %r → %s │ %s", nom, lieu.libelle(), meteo.get("label"))
    return MeteoLieu(lieu=lieu, meteo=meteo, autres=autres)

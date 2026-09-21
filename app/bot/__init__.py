"""Bot Telegram de l'Assistant Potager — package `app.bot`.

L'ancien `bot.py` monolithique est découpé en modules par domaine (voir
`app/bot/CLAUDE.md`). Ce fichier est une FAÇADE : il expose tous les noms de
tous les sous-modules, et propage toute affectation d'attribut
(`monkeypatch.setattr(bot, "SessionLocal", ...)`, `patch("app.bot.X")`) vers
chaque sous-module qui lie ce nom. Sans cela, un test qui remplace
`bot.SessionLocal` ne toucherait pas la variable globale lue par
`app.bot.saisie`, et la suite entière tomberait en base réelle.

Lancement : `python -m app.bot`.
"""
import sys as _sys
import types as _types

from . import (
    noyau,
    etat,
    normalisation,
    aide,
    liaison,
    enregistrement,
    godets,
    pertes,
    notes,
    interpretation,
    questions,
    saisie,
    correction,
    deplacement,
    commandes_parcelle,
    commandes_culture,
    commandes_calendrier,
    commandes_confiance,
    commandes_plan,
    commandes_stats,
    meteo_jobs,
    file_gestes,
    messages,
    application,
)

_SOUS_MODULES = (
    noyau,
    etat,
    normalisation,
    aide,
    liaison,
    enregistrement,
    godets,
    pertes,
    notes,
    interpretation,
    questions,
    saisie,
    correction,
    deplacement,
    commandes_parcelle,
    commandes_culture,
    commandes_calendrier,
    commandes_confiance,
    commandes_plan,
    commandes_stats,
    meteo_jobs,
    file_gestes,
    messages,
    application,
)


def _exporter() -> None:
    """Expose dans la façade chaque nom de chaque sous-module (premier vu gagne)."""
    espace = globals()
    for _mod in _SOUS_MODULES:
        for _nom, _val in vars(_mod).items():
            if _nom.startswith("__"):
                continue
            espace.setdefault(_nom, _val)


_exporter()


class _Facade(_types.ModuleType):
    """Module dont les affectations d'attribut se propagent aux sous-modules."""

    def __setattr__(self, nom: str, valeur) -> None:
        super().__setattr__(nom, valeur)
        for _mod in _SOUS_MODULES:
            if nom in vars(_mod):
                setattr(_mod, nom, valeur)

    def __delattr__(self, nom: str) -> None:
        super().__delattr__(nom)


_sys.modules[__name__].__class__ = _Facade

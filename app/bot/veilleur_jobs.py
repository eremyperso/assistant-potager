"""Le planificateur du veilleur : passage horaire et bilan du dimanche [US-266].

Le veilleur DÉTECTE (`app/services/compagnon/veilleur.py`) ; ses signaux sont en base
(`signaux`) et dans les journaux. Toute la logique est dans
`app/services/compagnon/veilleur_passage.py` : ce module ne fait que la planifier, hors
dispatch Telegram.

[US-267] Un signal détecté part aussitôt chez le distributeur, qui décide du moment et de
la forme (`app/services/compagnon/distribution.py`) ; `COMPAGNON_PROACTIF` éteint, rien
ne part.
"""
import asyncio

from telegram.ext import ContextTypes

from app.services.compagnon import distribution as svc_distribution
from app.services.compagnon import veilleur as svc_veilleur
from app.services.compagnon import veilleur_passage as svc_veilleur_passage
from .file_gestes import job_file_gestes
from .noyau import log


async def _distribuer() -> None:
    """[US-267] Ce qui vient d'être détecté part tout de suite, sans attendre le passage
    suivant du distributeur. Un échec ici ne retient pas la détection."""
    try:
        await asyncio.to_thread(svc_distribution.passer)
    except Exception as e:  # noqa: BLE001 — un job de fond ne tue jamais le bot
        log.error("❌ JOB DISTRIBUTEUR : %s", e)


async def job_veilleur(context: ContextTypes.DEFAULT_TYPE) -> None:
    """[CA5, CA7] Le rendez-vous horaire du veilleur.

    1. **Suivis** : la file de gestes d'US-224 (relance, avertissement, purge), rattachée
       au veilleur comme thème « suivis », SANS changement de comportement : c'est le même
       `job_file_gestes`, appelé à la même cadence, qui envoie ses messages comme avant.
    2. **Détecteurs** : gel, canicule, pluies, sécheresse, échéances, récoltes, levées,
       fenêtres de semis — potager par potager, sous `tenant_scope`. Le passage lit la
       base et Open-Meteo de façon bloquante : il tourne hors de la boucle du bot.

    Les deux parties sont indépendantes : une panne des détecteurs ne retient jamais une
    relance de la file, et inversement.
    """
    await job_file_gestes(context)
    try:
        await asyncio.to_thread(svc_veilleur_passage.passer, svc_veilleur.DETECTEURS_HORAIRES)
    except Exception as e:  # noqa: BLE001 — un job de fond ne tue jamais le bot
        log.error("❌ JOB VEILLEUR     : %s", e)
    await _distribuer()


async def job_bilan_semaine(context: ContextTypes.DEFAULT_TYPE) -> None:
    """[CA2, CA5] Le bilan de la semaine, le dimanche à 18 h : un signal « resume » par potager actif."""
    try:
        await asyncio.to_thread(
            svc_veilleur_passage.passer, svc_veilleur.DETECTEURS_HEBDOMADAIRES, None, False,
        )
    except Exception as e:  # noqa: BLE001 — un job de fond ne tue jamais le bot
        log.error("❌ JOB BILAN SEMAINE : %s", e)
    await _distribuer()

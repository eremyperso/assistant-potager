"""Le planificateur du pilotage LLM : évaluation des seuils, résumé quotidien, bilan hebdomadaire [US-316, US-317].

Toute la logique est dans `app/services/pilotage/` (`seuils.evaluer`, `bilans.passer`) : ce module ne
fait que la planifier, hors dispatch Telegram, avec le mécanisme du veilleur du compagnon (US-266) —
le bot est déjà le seul processus qui tient des tâches de fond, aucune unité systemd à ajouter.

Ni l'une ni l'autre des tâches n'appelle un modèle. Les envois partent de la boucle des threads
(`asyncio.to_thread`) : l'API Telegram et Brevo sont appelées de façon bloquante.
"""
import asyncio

from telegram.ext import ContextTypes

from app.services.pilotage import bilans as svc_bilans
from app.services.pilotage import seuils as svc_seuils
from database.db import SessionLocal

from .noyau import log

#: Cadence du résumé et du bilan : assez fine pour rejouer un envoi échoué, rattraper un redémarrage
#: du bot, et laisser la trace décider (jamais deux envois pour la même période).
INTERVALLE_BILANS_SECONDES = 1800


def passer_evaluation() -> int:
    """[US-316 / CA5] Évalue les seuils actifs. Rend le nombre d'événements (ouverture, rappel, résolution)."""
    db = SessionLocal()
    try:
        return sum(1 for _, evenement in svc_seuils.evaluer(db) if evenement)
    finally:
        db.close()


def passer_bilans() -> dict:
    """[US-317] Envoie ce qui est dû (résumé du matin, bilan du lundi) et pas encore parti."""
    db = SessionLocal()
    try:
        return svc_bilans.passer(db)
    finally:
        db.close()


async def job_evaluation_seuils(context: ContextTypes.DEFAULT_TYPE) -> None:
    """[US-316 / CA5] Le passage périodique (15 minutes par défaut, `PILOTAGE_EVALUATION_MINUTES`)."""
    try:
        await asyncio.to_thread(passer_evaluation)
    except Exception as e:  # noqa: BLE001 — un job de fond ne tue jamais le bot
        log.error("❌ JOB SEUILS PILOTAGE : %s", e)


async def job_bilans_pilotage(context: ContextTypes.DEFAULT_TYPE) -> None:
    """[US-317 / CA1, CA3, CA8] Le passage du résumé quotidien et du bilan hebdomadaire."""
    try:
        await asyncio.to_thread(passer_bilans)
    except Exception as e:  # noqa: BLE001 — idem
        log.error("❌ JOB BILANS PILOTAGE : %s", e)

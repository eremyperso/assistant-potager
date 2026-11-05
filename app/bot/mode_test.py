"""[US-288] `/reset_test` — remise à zéro du potager de test (mode test seulement).

Enregistrée par `application._construire_application` uniquement quand `APP_ENV=test`.
La logique est dans `app.services.mode_test` ; ici, les états en attente du processus.
"""
from telegram import Update
from telegram.ext import ContextTypes

from app.services import mode_test as svc_mode_test
from app.services.context import current_context
from database.db import SessionLocal
from . import etat
from .noyau import log


def vider_etats_en_attente() -> int:
    """Vide chaque dictionnaire `_*_PENDING` de `etat` ; rend le nombre d'entrées retirées."""
    retirees = 0
    for nom, valeur in vars(etat).items():
        if nom.endswith("_PENDING") and isinstance(valeur, dict):
            retirees += len(valeur)
            valeur.clear()
    return retirees


async def cmd_reset_test(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Vide les données du potager actif et les états en attente, puis répond « RESET_OK »."""
    if not svc_mode_test.actif():
        await update.message.reply_text("⛔ Commande réservée au mode test.")
        return
    potager_id = current_context().potager_id
    db = SessionLocal()
    try:
        bilan = svc_mode_test.remettre_a_zero(db, potager_id)
    finally:
        db.close()
    en_attente = vider_etats_en_attente()
    log.info("[US-288] /reset_test potager=%s tables=%s états_en_attente=%s",
             potager_id, bilan, en_attente)
    anomalies = [t for t, n in bilan.items() if n < 0]
    await update.message.reply_text(
        "RESET_OK" + (f" · anomalies : {', '.join(anomalies)}" if anomalies else "")
    )

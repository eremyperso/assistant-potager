"""Commande /meteo et tâches planifiées (météo quotidienne, purge des potagers).

Module extrait de l'ancien bot.py monolithique (découpage 2026-09).
"""
from telegram import Update
from telegram.ext import ContextTypes
from database.db import SessionLocal, tenant_scope
from utils.meteo import (
    LocalisationPotagerManquanteError,
    fetch_meteo,
    format_meteo_commentaire,
    localisation_potager,
    save_meteo_observation,
)
from app.services.context import current_context, default_context
from app.services import potagers as svc_potagers
from app.services import metriques_routage as svc_metriques_routage
from .noyau import _md, log


# ══════════════════════════════════════════════════════════════════════════════
# MÉTÉO
# ══════════════════════════════════════════════════════════════════════════════

def _libelle_lieu(potager) -> str:
    """Ville et coordonnées du potager, pour situer la météo affichée."""
    coordonnees = f"{potager.latitude:.4f}, {potager.longitude:.4f}"
    if potager.ville:
        return f"📍 {_md(potager.ville)} ({coordonnees})"
    return f"📍 {coordonnees}"


async def cmd_meteo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    /meteo — Déclenche manuellement la récupération météo et l'enregistre en base.
    Utile pour tester ou forcer une mise à jour hors du job automatique 5h00.

    Météo calculée sur la localisation du potager actif (US-074), observation
    rattachée à ce potager — pas les coordonnées globales du bot. Sans
    localisation, aucun appel : même règle que `GET /meteo` (US-075 / CA4).
    """
    msg = await update.message.reply_text("🌤️ *Récupération météo en cours...*", parse_mode="Markdown")
    potager_id = current_context().potager_id
    db  = SessionLocal()
    try:
        try:
            potager = localisation_potager(db, potager_id)
        except LocalisationPotagerManquanteError:
            await msg.edit_text(
                "📍 Ce potager n'a pas encore de localisation : renseignez sa ville "
                "dans l'application web pour obtenir sa météo."
            )
            return
        lieu = _libelle_lieu(potager)
        meteo = save_meteo_observation(db, potager_id=potager_id)
        if meteo is None:
            # Doublon ou erreur — tenter un fetch sans sauvegarde pour afficher quand même
            meteo = fetch_meteo(potager.latitude, potager.longitude)
            if meteo:
                commentaire = format_meteo_commentaire(meteo)
                await msg.edit_text(
                    f"🌤️ *Météo du jour* _(déjà enregistrée aujourd'hui)_\n{lieu}\n\n`{commentaire}`",
                    parse_mode="Markdown"
                )
            else:
                await msg.edit_text("❌ Impossible de récupérer la météo. Vérifiez votre connexion.")
            return

        commentaire = format_meteo_commentaire(meteo)
        await msg.edit_text(
            f"🌤️ *Météo enregistrée !*\n{lieu}\n\n`{commentaire}`",
            parse_mode="Markdown"
        )
        log.info(f"🌤️  MÉTÉO MANUELLE  : déclenchée par /meteo (potager_id={potager_id})")
    except Exception as e:
        log.error(f"❌ MÉTÉO COMMANDE   : {e}")
        await msg.edit_text(f"❌ Erreur : {e}")
    finally:
        db.close()


async def job_meteo_quotidienne(context: ContextTypes.DEFAULT_TYPE):
    """
    Job planifié à 05h00 chaque matin (Europe/Paris).
    Récupère la météo Open-Meteo et l'enregistre silencieusement en base
    comme action 'observation' avec texte_original='[AUTO-METEO]'.
    Aucun message Telegram envoyé.
    Zéro token Groq consommé.
    """
    log.info("🌅 JOB MÉTÉO       : déclenchement automatique 05h00")
    # [US-043] Job de fond hors dispatch Telegram (JobQueue, pas d'Update) :
    # doit armer app.potager_id lui-même. Un seul potager aujourd'hui — à
    # boucler potager par potager le jour où ce job devient multi-tenant.
    db = SessionLocal()
    try:
        with tenant_scope(default_context().potager_id):
            meteo = save_meteo_observation(db)
        if meteo:
            log.info(
                f"🌤️  MÉTÉO AUTO      : {meteo['emoji']} {meteo['label']} | "
                f"{meteo['temp_matin']}°C matin / {meteo['temp_aprem']}°C AM | "
                f"Pluie {meteo['precipitations']}mm ({meteo['proba_pluie']}%)"
            )
        else:
            log.warning("⚠️  MÉTÉO AUTO      : aucune donnée sauvée (doublon ou erreur réseau)")
    except Exception as e:
        log.error(f"❌ JOB MÉTÉO ERREUR : {e}")
    finally:
        db.close()


async def job_purge_potagers(context: ContextTypes.DEFAULT_TYPE):
    """[US-084 / CA7, CA8] Job planifié à 04h00 chaque matin (Europe/Paris).

    Efface physiquement les potagers supprimés dont le délai de grâce de 30
    jours est écoulé. Aucune logique de purge ici : tout est porté par la
    fonction de service unique `svc_potagers.purger_potagers_supprimes`,
    également appelée par `tools/purger_potagers.py` (déclenchement manuel).

    Le job n'arme pas `tenant_scope` lui-même, contrairement à
    `job_meteo_quotidienne` : la purge est multi-tenant par nature et pose le
    contexte potager par potager (US-043).

    [CA8] Une exécution sans rien à purger est le cas normal, pas une erreur.
    """
    log.info("🗑️  JOB PURGE       : déclenchement automatique 04h00")
    db = SessionLocal()
    try:
        resultats = svc_potagers.purger_potagers_supprimes(db)
        log.info("🗑️  PURGE AUTO      : %s potager(s) effacé(s) définitivement", len(resultats))
        # [US-097 / CA3] Rétention documentée du journal de routage (12 mois) —
        # même job quotidien, la purge des entrées expirées n'a pas besoin
        # d'une planification dédiée.
        nb_routage = svc_metriques_routage.purger_routage_logs_expires(db)
        if nb_routage:
            log.info("🗑️  PURGE AUTO      : %s entrée(s) de routage_logs expirée(s) effacée(s)", nb_routage)
    except Exception as e:
        log.error(f"❌ JOB PURGE ERREUR : {e}")
    finally:
        db.close()

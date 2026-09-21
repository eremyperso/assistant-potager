"""Construction de l'application Telegram, enregistrement des handlers, main().

Module extrait de l'ancien bot.py monolithique (découpage 2026-09).
"""
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler, TypeHandler
from app.config import TELEGRAM_BOT_TOKEN
from database.db import current_potager_id
from utils.tts import is_tts_enabled
from app.services.context import default_context
from app.services import menu_commandes as svc_menu_commandes
from .noyau import log
from .aide import cmd_help, cmd_version
from .liaison import (
    _potager_select_cb,
    _verifier_liaison_ou_onboarding,
    cmd_delier,
    cmd_lier,
    cmd_potager,
    cmd_rejoindre,
    cmd_start,
)
from .enregistrement import _action_confirm_cb
from .godets import _godet_graines_cb, _godet_lot_cb, _godet_variete_cb
from .pertes import _handle_perte_callback, _vendu_variete_cb
from .notes import _note_confirm_cb, _note_start
from .interpretation import _interp_cb
from .questions import _retour_routage_cb
from .saisie import (
    _creation_parcelle_geste_cb,
    _recolte_variete_cb,
    _semis_organe_cb,
    cmd_vendre,
)
from .correction import _corr_start
from .commandes_parcelle import _cmd_parcelles_lister, _parcelle_suppr_cb, cmd_parcelle
from .commandes_culture import (
    cmd_association,
    cmd_bioagresseur,
    cmd_culture,
    cmd_fiche,
    cmd_rotation,
)
from .commandes_calendrier import cmd_calendrier
from .commandes_confiance import cmd_confiance, _confiance_cb
from .commandes_plan import cmd_plan
from .commandes_stats import (
    cmd_ask,
    cmd_historique,
    cmd_stats,
    cmd_tts,
    cmd_tts_off,
    cmd_tts_on,
)
from .meteo_jobs import cmd_meteo, job_meteo_quotidienne, job_purge_potagers
from .messages import handle_text, handle_voice


# LANCEMENT
# ══════════════════════════════════════════════════════════════════════════════
# [US-043] Arme app.potager_id (défense en profondeur RLS) pour tout le
# traitement de cet Update — PTB v20 traite tous les groupes de handlers d'un
# même Update séquentiellement dans une seule Task asyncio, donc un simple
# .set() (sans reset) ici reste visible pour les handlers des groupes
# suivants ; chaque nouvel Update est traité dans sa propre Task, donc sans
# fuite entre mises à jour concurrentes (sémantique standard de contextvars).
async def _arm_tenant_context(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_potager_id.set(default_context().potager_id)


# ──────────────────────────────────────────────────────────────────────────────
# [US-045 / CA6, CA7 révisés] Garde de liaison centralisé sur les commandes slash
# ──────────────────────────────────────────────────────────────────────────────
# Constat QA : une première implémentation ne posait le garde que sur
# handle_voice/handle_text — les commandes slash métier (/plan, /parcelle
# lister...) restaient accessibles sans liaison. Pour qu'aucune commande
# (existante ou future) ne puisse y échapper par oubli, l'enregistrement de
# CHAQUE CommandHandler passe obligatoirement par _enregistrer_commande()
# ci-dessous plutôt que par un appel direct à app.add_handler(CommandHandler(...)).
_COMMANDES_SANS_GARDE_LIAISON = {"start", "help", "lier", "delier"}  # [CA9] onboarding + [US-050] identité seule

# [US-087 / CA1, CA6] Commandes soumises au garde de liaison — un chat non relié est
# renvoyé vers le parcours de liaison — mais qui n'exigent PAS de potager résolu :
# `/rejoindre` sert précisément à en obtenir un. Sans cette exception, le garde
# répondrait « vous n'êtes membre d'aucun potager » à qui n'en a pas encore, donc à
# celui qui en a le plus besoin.
_COMMANDES_SANS_EXIGENCE_DE_POTAGER = {"rejoindre"}


def _avec_garde_liaison(handler, exiger_potager: bool = True):
    """[CA6, CA7] Enveloppe un handler de commande pour exiger une liaison active
    avant d'exécuter le moindre traitement métier (priorité 0)."""
    async def _handler_garde(update: Update, ctx: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not await _verifier_liaison_ou_onboarding(update, ctx, exiger_potager=exiger_potager):
            return
        return await handler(update, ctx, *args, **kwargs)
    _handler_garde._garde_liaison = True  # introspectable par les tests (CA6/CA7)
    return _handler_garde


# ──────────────────────────────────────────────────────────────────────────────
# [US-171] Menu de commandes natif Telegram
# ──────────────────────────────────────────────────────────────────────────────
def _noms_commandes_enregistrees(app: "Application") -> set[str]:
    """Noms des commandes réellement servies par le bot, par introspection.

    Dérivé des `CommandHandler` de l'Application plutôt que d'une liste recopiée :
    c'est ce qui garantit qu'aucune commande morte ne figure au menu et qu'une
    commande nouvellement enregistrée y entre d'elle-même (CA3, CA6).
    """
    noms: set[str] = set()
    for handlers in app.handlers.values():
        for handler in handlers:
            if isinstance(handler, CommandHandler):
                noms.update(handler.commands)
    return noms


async def _publier_menu_commandes(app: "Application") -> None:
    """Déclare le menu de commandes auprès de Telegram, à chaque démarrage (CA1, CA6).

    Rejoué sans intervention manuelle : la liste envoyée écrase la précédente,
    donc une commande ajoutée ou retirée du bot se reflète au redémarrage suivant.
    Un échec réseau est journalisé mais ne fait jamais échouer le démarrage du
    bot — le menu est un confort, pas une condition de service.
    """
    entrees = svc_menu_commandes.construire_menu(_noms_commandes_enregistrees(app))
    try:
        await app.bot.set_my_commands(
            [BotCommand(nom, description) for nom, description in entrees]
        )
        log.info("⌨️  MENU TELEGRAM  : %d commandes déclarées", len(entrees))
    except Exception as e:  # noqa: BLE001 — observabilité, jamais bloquant
        log.warning("⌨️  MENU TELEGRAM  : déclaration impossible (%s)", e)


def _enregistrer_commande(app: "Application", nom: str, handler) -> None:
    """[US-045] Point d'enregistrement unique des CommandHandler — applique le
    garde de liaison sauf pour les commandes d'onboarding (CA9)."""
    if nom in _COMMANDES_SANS_GARDE_LIAISON:
        app.add_handler(CommandHandler(nom, handler))
    else:
        exiger_potager = nom not in _COMMANDES_SANS_EXIGENCE_DE_POTAGER
        app.add_handler(CommandHandler(nom, _avec_garde_liaison(handler, exiger_potager)))


def _construire_application() -> "Application":
    """Construit l'Application PTB et enregistre tous les handlers (sans lancer
    le polling) — séparé de main() pour être testable/introspectable (CA6/CA7)."""
    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(15)
        .pool_timeout(30)
        # [US-171 / CA6] Le menu est (re)déclaré à chaque démarrage du bot.
        .post_init(_publier_menu_commandes)
        .build()
    )

    # [US-043] Arme app.potager_id (défense en profondeur RLS) avant tout autre
    # handler, pour chaque Update entrant — groupe -1 = exécuté en premier,
    # ne bloque pas la propagation vers les handlers des groupes suivants.
    app.add_handler(TypeHandler(Update, _arm_tenant_context), group=-1)

    # Commandes — TOUTES enregistrées via _enregistrer_commande (CA6/CA7/CA9)
    _enregistrer_commande(app, "start",      cmd_start)
    _enregistrer_commande(app, "help",       cmd_help)
    _enregistrer_commande(app, "version",    cmd_version)  # [US-008]
    _enregistrer_commande(app, "stats",      cmd_stats)
    _enregistrer_commande(app, "historique", cmd_historique)
    _enregistrer_commande(app, "ask",        cmd_ask)
    _enregistrer_commande(app, "corriger",   lambda u, c: _corr_start(u, c))
    _enregistrer_commande(app, "note",       lambda u, c: _note_start(u, c))  # [US-038]
    _enregistrer_commande(app, "lier",       cmd_lier)  # [US-045]
    _enregistrer_commande(app, "delier",     cmd_delier)  # [US-050]
    _enregistrer_commande(app, "potager",    cmd_potager)  # [US-046]
    _enregistrer_commande(app, "rejoindre",  cmd_rejoindre)  # [US-087]

    # Commandes TTS
    _enregistrer_commande(app, "tts",        cmd_tts)
    _enregistrer_commande(app, "tts_on",     cmd_tts_on)
    _enregistrer_commande(app, "tts_off",    cmd_tts_off)

    # Commande météo manuelle
    _enregistrer_commande(app, "meteo",      cmd_meteo)

    # [US_Plan_occupation_parcelles / CA1, CA13] Plan et gestion des parcelles
    _enregistrer_commande(app, "plan",      cmd_plan)
    _enregistrer_commande(app, "parcelle",  cmd_parcelle)
    _enregistrer_commande(app, "parcelles", _cmd_parcelles_lister)  # alias /parcelle lister
    _enregistrer_commande(app, "culture",   cmd_culture)  # [US-067]
    _enregistrer_commande(app, "fiche",     cmd_fiche)  # [US-164]
    _enregistrer_commande(app, "calendrier", cmd_calendrier)  # [US-068]
    _enregistrer_commande(app, "confiance", cmd_confiance)  # [US-179]
    _enregistrer_commande(app, "association", cmd_association)  # [US-163]
    _enregistrer_commande(app, "rotation",    cmd_rotation)  # [US-163]
    _enregistrer_commande(app, "bioagresseur", cmd_bioagresseur)  # [US-162]

    _enregistrer_commande(app, "vendre",    cmd_vendre)

    # [US-019] Sélection variété mise en godet — boutons inline
    app.add_handler(CallbackQueryHandler(_godet_variete_cb, pattern=r"^godet_"))
    # [fix rattachement lot godet] Motif distinct de "^godet_" (pas d'underscore
    # après "godet") — les deux handlers ne se recouvrent jamais.
    app.add_handler(CallbackQueryHandler(_godet_lot_cb, pattern=r"^godetlot"))
    # [US-066] Motif également disjoint de "^godet_" et de "^godetlot".
    app.add_handler(CallbackQueryHandler(_godet_graines_cb, pattern=r"^godetgraines"))

    # Sélection variété récolte — boutons inline
    app.add_handler(CallbackQueryHandler(_recolte_variete_cb, pattern=r"^recolte_"))
    app.add_handler(CallbackQueryHandler(_vendu_variete_cb,  pattern=r"^vendu_"))

    # [perte_godet/vendu] Disambiguation perte jardin vs pépinière
    app.add_handler(CallbackQueryHandler(_handle_perte_callback, pattern=r"^perte_"))

    # [US-021] Confirmation avant enregistrement — boutons inline
    app.add_handler(CallbackQueryHandler(_action_confirm_cb, pattern=r"^action_"))
    app.add_handler(CallbackQueryHandler(_semis_organe_cb, pattern=r"^semis_organe"))
    # [US-179] Filière, enregistrement, question décalée de dix jours
    app.add_handler(CallbackQueryHandler(_confiance_cb, pattern=r"^conf:"))

    # [US-038] Confirmation avant enregistrement d'une note — boutons inline
    app.add_handler(CallbackQueryHandler(_note_confirm_cb, pattern=r"^note_"))

    # [US-009] Suppression parcelle — boutons inline
    app.add_handler(CallbackQueryHandler(_parcelle_suppr_cb, pattern=r"^parcelle_suppr_"))

    # [US-046] Sélection du potager actif — boutons inline
    app.add_handler(CallbackQueryHandler(_potager_select_cb, pattern=r"^potager_select_"))

    # [US-097] Retour 👍/👎 sur une réponse de savoir/raisonnement
    app.add_handler(CallbackQueryHandler(_retour_routage_cb, pattern=r"^retour_routage:"))

    # [US-172] Commande dictée : confirmation, refus, complétion d'un argument,
    # choix d'un nom voisin. Motif disjoint de "^interpparc:" ci-dessous.
    app.add_handler(CallbackQueryHandler(_interp_cb, pattern=r"^interp:"))
    # [US-172 / CA19] Création de la parcelle citée par un geste
    app.add_handler(CallbackQueryHandler(_creation_parcelle_geste_cb, pattern=r"^interpparc:"))

    # Messages
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # ── Job météo quotidien à 05h00 (Europe/Paris) ────────────────────────────
    import pytz
    from datetime import time as dtime
    tz_paris = pytz.timezone("Europe/Paris")
    app.job_queue.run_daily(
        job_meteo_quotidienne,
        time=dtime(hour=5, minute=0, second=0, tzinfo=tz_paris),
        name="meteo_quotidienne",
    )
    log.info("🌅 JOB MÉTÉO       : planifié à 05h00 Europe/Paris")

    # ── [US-084 / CA7] Job de purge quotidien à 04h00 (Europe/Paris) ──────────
    # Avant le job météo : la purge nettoie, la météo écrit — inutile de créer
    # des observations sur un potager que la purge va effacer dans la foulée.
    app.job_queue.run_daily(
        job_purge_potagers,
        time=dtime(hour=4, minute=0, second=0, tzinfo=tz_paris),
        name="purge_potagers_supprimes",
    )
    log.info("🗑️  JOB PURGE       : planifié à 04h00 Europe/Paris")

    return app


def main():
    print("🌿 Démarrage du bot Telegram potager...")
    print(f"   Token : {TELEGRAM_BOT_TOKEN[:10]}...")
    print(f"   TTS   : {'🔊 activé' if is_tts_enabled() else '🔇 désactivé'} (commande /tts pour changer)")
    print(f"   Météo : 🌤️ job planifié à 05h00 Europe/Paris · /meteo pour déclencher manuellement")

    app = _construire_application()

    print("   Bot prêt ! Ouvrez Telegram et parlez à votre bot.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

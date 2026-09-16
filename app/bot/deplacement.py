"""Déplacement d'une culture d'une parcelle à une autre [US-007].

Module extrait de l'ancien bot.py monolithique (découpage 2026-09).
"""
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import SessionLocal
from utils.parcelles import calcul_occupation_parcelles, find_doublon, create_parcelle, get_all_parcelles, resolve_parcelle
from app.services.context import current_context
from app.services import evenements as svc_evenements
from app.services import parcelles as svc_parcelles
from .noyau import AFTER_RECORD_KEYBOARD, MENU_KEYBOARD, log


# ══════════════════════════════════════════════════════════════════════════════
# [US-007] DÉPLACEMENT / RÉASSOCIATION CULTURE → PARCELLE
# ══════════════════════════════════════════════════════════════════════════════

MODES_DEPLACER = {
    'depl_culture_ask',    # CA11 — culture non détectée, on demande
    'depl_variete_select', # CA4  — plusieurs variétés, choix
    'depl_parcelle_select', # CA5  — liste des parcelles, saisie cible
    'depl_confirm',         # CA7  — récapitulatif, attente confirmation
}


async def _depl_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE, culture: str | None):
    """
    [US-007] Point d'entrée du flux de réassociation.
    - Si culture=None → mode depl_culture_ask (CA11)
    - Sinon → cherche les plantations, route vers variété ou parcelle
    """
    if not culture:
        ctx.user_data['mode'] = 'depl_culture_ask'
        await update.message.reply_text(
            "🔀 *Réassociation culture → parcelle*\n\nQuelle culture souhaitez-vous déplacer ?",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([["❌ Annuler"]], resize_keyboard=True),
        )
        return

    from unidecode import unidecode
    culture = culture.strip().lower()
    culture_norm = unidecode(culture)  # supprime accents pour la comparaison

    db = SessionLocal()
    try:
        # Essai 1 : correspondance exacte (insensible casse)
        rows = svc_evenements.evenements_localises_exact(db, current_context(), culture)
        # Essai 2 : correspondance partielle (gère typos, accents, pluriel)
        if not rows:
            rows = svc_evenements.evenements_localises_recherche_partielle(db, current_context(), culture_norm[:6])
            if rows:
                # Utiliser le nom exact stocké en base pour la suite du flux
                culture = rows[0].culture.lower()
                log.info(f"[US-007] Culture corrigée : '{culture}' trouvée via recherche partielle")
    finally:
        db.close()

    if not rows:
        await update.message.reply_text(
            f"❌ Aucune plantation ni semis pleine terre de *{culture}* trouvé en base.\n\n"
            f"_Vérifiez le nom avec /stats_",
            parse_mode="Markdown",
            reply_markup=MENU_KEYBOARD,
        )
        ctx.user_data['mode'] = None
        log.info(f"[US-007 CA2] Aucune plantation/semis pleine terre pour culture='{culture}'")
        return

    ctx.user_data['depl_culture'] = culture

    # Collecter les variétés distinctes (None = sans variété précisée)
    varietes = list({(e.variete or "") for e in rows})
    varietes_remplies = [v for v in varietes if v]

    if len(varietes_remplies) > 1:
        # CA4 — plusieurs variétés → demander laquelle
        ctx.user_data['mode'] = 'depl_variete_select'
        lines = [f"🌿 J'ai trouvé *{len(varietes_remplies)} variété(s)* de *{culture}* plantée(s) :\n"]
        for v in varietes_remplies:
            nb = sum(1 for e in rows if (e.variete or "") == v)
            lines.append(f"• *{v}* — {nb} enregistrement(s)")
        lines.append("\nSouhaitez-vous déplacer *toutes* les variétés ou une en particulier ?")
        lines.append("Tapez `toutes` ou le nom d'une variété.")
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([["toutes"], ["❌ Annuler"]], resize_keyboard=True),
        )
        log.info(f"[US-007 CA4] Plusieurs variétés pour '{culture}' : {varietes_remplies}")
    else:
        # CA3 — une seule variété ou aucune → passer directement à la sélection de parcelle
        variete_unique = varietes_remplies[0] if varietes_remplies else None
        ctx.user_data['depl_variete'] = variete_unique
        log.info(f"[US-007 CA3] Variété unique '{variete_unique}' → sélection parcelle directe")
        await _depl_show_parcelles(update, ctx)


async def _depl_show_parcelles(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """[US-007 / CA5] Affiche la liste des parcelles avec occupation actuelle."""
    culture = ctx.user_data.get('depl_culture', '?')
    variete = ctx.user_data.get('depl_variete')
    var_str = f" (variété : {variete})" if variete else " (toutes variétés)"

    db = SessionLocal()
    try:
        parcelles = get_all_parcelles(db, potager_id=current_context().potager_id)
        occupation = calcul_occupation_parcelles(db, potager_id=current_context().potager_id)
    finally:
        db.close()

    lines = [f"📋 Où souhaitez-vous placer *{culture}*{var_str} ?\n"]
    for p in parcelles:
        cultures_p = occupation.get(p.nom, [])
        if not cultures_p:
            lines.append(f"🟢 *{p.nom.upper()}* — Libre")
        else:
            resumes = []
            for c in cultures_p[:3]:
                cult_label = c['culture']
                if c.get('variete'):
                    cult_label += f" {c['variete']}"
                nb = int(c['nb_plants']) if c['nb_plants'] == int(c['nb_plants']) else c['nb_plants']
                resumes.append(f"{cult_label} ({nb} {c.get('unite', 'plants')})")
            suffix = " …" if len(cultures_p) > 3 else ""
            lines.append(f"📍 *{p.nom.upper()}* — {', '.join(resumes)}{suffix}")

    lines.append("\nTapez le nom de la parcelle cible (ou *annuler*).")
    ctx.user_data['mode'] = 'depl_parcelle_select'
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["❌ Annuler"]], resize_keyboard=True),
    )


async def _depl_variete_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE, texte: str):
    """[US-007 / CA4] L'utilisateur choisit 'toutes' ou une variété spécifique."""
    t = texte.strip().lower()
    if "annuler" in t or "menu" in t or "retour" in t:
        _depl_reset(ctx)
        await update.message.reply_text("↩️ Déplacement annulé.", reply_markup=MENU_KEYBOARD)
        return

    if t in ("toutes", "toutes les variétés", "toutes les varietes", "all"):
        ctx.user_data['depl_variete'] = None
    else:
        ctx.user_data['depl_variete'] = texte.strip()

    await _depl_show_parcelles(update, ctx)


async def _depl_parcelle_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE, texte: str):
    """[US-007 / CA5, CA6] L'utilisateur saisit le nom de la parcelle cible."""
    t = texte.strip().lower()
    if "annuler" in t or "menu" in t or "retour" in t:
        _depl_reset(ctx)
        await update.message.reply_text("↩️ Déplacement annulé.", reply_markup=MENU_KEYBOARD)
        return

    culture = ctx.user_data.get('depl_culture', '')
    variete = ctx.user_data.get('depl_variete')
    nom_parcelle = texte.strip()

    db = SessionLocal()
    try:
        # Résoudre la parcelle (CA6 : accepter une parcelle inconnue)
        parcelle_obj = resolve_parcelle(db, nom_parcelle, potager_id=current_context().potager_id)
        parcelle_id_cible = parcelle_obj.id if parcelle_obj else None
        nom_affiche = parcelle_obj.nom.upper() if parcelle_obj else nom_parcelle.upper()

        # Compter les enregistrements plantation/semis pleine terre concernés
        nb_records = len(svc_evenements.evenements_localises_pour_maj(db, current_context(), culture, variete))
    finally:
        db.close()

    if nb_records == 0:
        await update.message.reply_text(
            f"❌ Aucune plantation ni semis pleine terre de *{culture}* trouvé.",
            parse_mode="Markdown",
        )
        _depl_reset(ctx)
        return

    ctx.user_data['depl_parcelle_cible'] = nom_parcelle
    ctx.user_data['depl_parcelle_cible_id'] = parcelle_id_cible
    ctx.user_data['depl_nb_records'] = nb_records
    ctx.user_data['mode'] = 'depl_confirm'

    var_str = f" — variété : {variete}" if variete else " — toutes variétés"
    recap = (
        f"✅ *Récapitulatif :*\n"
        f"🌿 Culture : *{culture}*{var_str}\n"
        f"📍 Nouvelle parcelle : *{nom_affiche}*\n"
        f"📝 Enregistrements mis à jour : *{nb_records}* plantation(s)/semis\n\n"
        f"Confirmez-vous ? (*oui* / *non*)"
    )
    await update.message.reply_text(
        recap,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["oui", "non"], ["❌ Annuler"]], resize_keyboard=True),
    )
    log.info(f"[US-007 CA7] Récapitulatif : culture={culture} variete={variete} → {nom_affiche} ({nb_records} records)")


async def _depl_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE, texte: str):
    """[US-007 / CA8] Confirmation finale — exécute l'UPDATE groupé."""
    t = texte.strip().lower()

    if "annuler" in t or "menu" in t or "retour" in t or t in ("non", "n", "no"):
        _depl_reset(ctx)
        await update.message.reply_text("↩️ Déplacement annulé.", reply_markup=MENU_KEYBOARD)
        return

    if t not in ("oui", "o", "yes", "y", "confirmer", "confirme", "✅ confirmer"):
        await update.message.reply_text(
            "❓ Tapez *oui* pour confirmer ou *non* pour annuler.",
            parse_mode="Markdown",
        )
        return

    culture      = ctx.user_data.get('depl_culture', '')
    variete      = ctx.user_data.get('depl_variete')
    nom_parcelle = ctx.user_data.get('depl_parcelle_cible', '')
    parcelle_id  = ctx.user_data.get('depl_parcelle_cible_id')
    nb_records   = ctx.user_data.get('depl_nb_records', 0)

    db = SessionLocal()
    try:
        # CA6 : créer la parcelle si elle n'existe pas encore
        if parcelle_id is None:
            from utils.parcelles import create_parcelle, find_doublon
            doublon = find_doublon(db, nom_parcelle, potager_id=current_context().potager_id)
            if doublon:
                parcelle_id = doublon.id
                nom_affiche = doublon.nom.upper()
            else:
                new_p = create_parcelle(db, nom_parcelle, potager_id=current_context().potager_id)
                parcelle_id = new_p.id
                nom_affiche = new_p.nom.upper()
                log.info(f"[US-007 CA6] Nouvelle parcelle créée : {nom_affiche!r}")
        else:
            parc = svc_parcelles.get_parcelle(db, current_context(), parcelle_id)
            nom_affiche = parc.nom.upper() if parc else nom_parcelle.upper()

        # [US-037] Réassocie les événements localisés (plantations ET semis pleine
        # terre) — un semis pépinière n'est jamais concerné (pas de localisation).
        nb_updated = svc_evenements.deplacer_evenements(
            db, current_context(), culture, variete, parcelle_id, nom_affiche
        )
    except Exception as e:
        db.rollback()
        log.error(f"[US-007] Erreur UPDATE : {e}")
        await update.message.reply_text(f"❌ Erreur : {e}", reply_markup=MENU_KEYBOARD)
        _depl_reset(ctx)
        return
    finally:
        db.close()

    _depl_reset(ctx)
    var_str = f" {variete}" if variete else ""
    await update.message.reply_text(
        f"✅ *{nb_updated} plantation(s) de {culture}{var_str}* associée(s) à la parcelle *{nom_affiche}*.",
        parse_mode="Markdown",
        reply_markup=AFTER_RECORD_KEYBOARD,
    )


def _depl_reset(ctx: ContextTypes.DEFAULT_TYPE):
    """[US-007 / CA9] Réinitialise tous les clés du flux DEPLACER."""
    for k in ['mode', 'depl_culture', 'depl_variete', 'depl_parcelle_cible',
              'depl_parcelle_cible_id', 'depl_nb_records']:
        ctx.user_data.pop(k, None)

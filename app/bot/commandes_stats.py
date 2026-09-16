"""Commandes /stats, /historique, /ask, /tts.

Module extrait de l'ancien bot.py monolithique (découpage 2026-09).
"""
from telegram import Update
from telegram.ext import ContextTypes
from database.db import SessionLocal
from utils.tts import send_voice_reply, set_tts_enabled, is_tts_enabled
from utils.stock import calcul_stock_cultures, format_stock_ligne_telegram
from utils.cultures_icons import get_emoji_culture
from app.services.context import current_context
from app.services import evenements as svc_evenements
from app.services import contexte_semis as svc_contexte_semis
from datetime import date
from .noyau import (
    MENU_KEYBOARD,
    _looks_like_date,
    _parse_date_arg,
    _send_chunked,
    log,
)
from .questions import _ask_question


async def cmd_stats(update, ctx):
    """
    /stats — Statistiques rapides du potager.

    [US-003 / CA1] Cultures végétatives : affiche "X plants récoltés"
    [US-003 / CA2] Cultures reproductrices : affiche "X plants actifs, Y kg cumulés"
    [US-003 / CA3] Deux sections distinctes : végétatif vs reproducteur
    [US-002 / CA3] Calcul stock différencié selon type_organe_recolte
    [US-002 / CA4] Champs stock_plants + rendement_total distincts via /stats API
    [US_Stats_detail_par_variete / CA1] Sans argument → synthèse générale inchangée
    [US_Stats_detail_par_variete / CA3] Avec argument → détail par variété de la culture
    [US-030 / CA11-CA14] Accepte une date optionnelle : /stats 2025-05-01, /stats tomate 01/05/2025
    """
    from utils.stock import (
        calcul_stock_cultures, format_stock_ligne_telegram, calcul_semis,
        calcul_stock_par_variete, format_variete_bloc_telegram, _fmt_date_variete,
        calcul_semis_par_culture, calcul_godets, calcul_godets_par_culture,
    )

    # [US-030 / CA12-CA14] Parser les args : date optionnelle + culture optionnelle
    date_ref: date | None = None
    culture_arg: str | None = None
    if ctx and getattr(ctx, "args", None):
        for a in ctx.args:
            parsed_d = _parse_date_arg(a)
            if parsed_d is not None:
                date_ref = parsed_d
            elif _looks_like_date(a):
                # [US-030 / CA14] Ressemble à une date mais invalide
                await update.effective_message.reply_text(
                    "❌ Format de date invalide — utilise `JJ/MM/AAAA` ou `AAAA-MM-JJ`",
                    parse_mode="Markdown",
                )
                return
            elif culture_arg is None:
                culture_arg = a.lower()

    # [US-030 / CA13] Bannière date de référence
    date_banner = ""
    if date_ref:
        date_banner = f"📅 _État au {date_ref.strftime('%d/%m/%Y')}_\n\n"

    db = SessionLocal()
    try:
        # ── [US_Stats_detail_par_variete / CA3] Mode détail variété ──────────
        if culture_arg:
            _pid = current_context().potager_id
            varietes      = calcul_stock_par_variete(db, culture_arg, date_ref, potager_id=_pid)
            semis_culture = calcul_semis_par_culture(db, culture_arg, date_ref, potager_id=_pid)
            godets_culture = calcul_godets_par_culture(db, culture_arg, date_ref, potager_id=_pid)  # [US-018]

            # [US-014 / CA5] Culture sans plantation mais avec semis → on continue
            if not varietes and not semis_culture and not godets_culture:
                await _send_chunked(update, f"_Aucune donnée pour {culture_arg}_", reply_markup=MENU_KEYBOARD)
                return

            # Emoji selon type_organe (plantation ou semis)
            type_organe = varietes[0]["type_organe"] if varietes else None
            emoji = get_emoji_culture(culture_arg, type_organe)
            culture_display = culture_arg.capitalize()

            lines_out = [date_banner + f"{emoji} *{culture_display} — détail par variété*\n"]

            current_year_sv = __import__("datetime").datetime.now().year

            # Blocs plantations
            for v in varietes:
                lines_out.append(format_variete_bloc_telegram(v))
                lines_out.append("")

            # [US-014 / CA3+CA4 | US-017 / CA5] Section semis avec stock résiduel par variété
            if semis_culture:
                lines_out.append("🌱 *Semis en cours :*")
                for s in semis_culture:
                    var_label = s["variete"] or "Variété non précisée"
                    date_s    = s["date_premier_semis"]
                    date_str  = _fmt_date_variete(date_s, current_year_sv) if date_s else "?"
                    if s["total_seme"]:
                        semis_label = f"semis de {int(s['total_seme'])} {s['unite']}"
                    else:
                        semis_label = f"{s['nb_semis']} semis"
                    en_godet = s.get("plants_en_godet", 0)
                    residuel = s.get("stock_residuel", 0)
                    if en_godet > 0:
                        godet_str = f" · {en_godet} en godet"
                        if residuel > 0:
                            godet_str += f" · *{residuel} restantes*"
                    else:
                        godet_str = ""
                    lines_out.append(f"  • *{var_label}* : {semis_label}{godet_str} · 🗓️ {date_str}")
                lines_out.append("")

            # [US-018 / CA1, CA2] [US-022 / CA3, CA4] Section pépinière — godets non encore plantés
            if godets_culture:
                current_year_g = __import__("datetime").datetime.now().year
                lines_out.append("🪴 *Pépinière :*")
                for g in godets_culture:
                    var_g    = g["variete"] or "Variété non précisée"
                    nb_p     = g["nb_plants_godets"]
                    nb_pl    = g.get("nb_plantes", 0)
                    nb_v     = g.get("nb_vendus", 0)
                    nb_pg    = g.get("nb_pertes_godet", 0)
                    residuel = g.get("stock_residuel_godet", nb_p)
                    taux     = g["taux_reussite"]
                    d_godet  = g["date_derniere_mise_en_godet"]
                    date_g   = _fmt_date_variete(d_godet, current_year_g) if d_godet else "?"
                    taux_str = f" · taux *{taux}%*" if taux is not None else ""
                    sorties  = []
                    if nb_pl > 0: sorties.append(f"{nb_pl} plantés")
                    if nb_v  > 0: sorties.append(f"{nb_v} vendus")
                    if nb_pg > 0: sorties.append(f"{nb_pg} perdus")
                    detail   = f" ({nb_p} repiqués · {', '.join(sorties)})" if sorties else ""
                    lines_out.append(f"  • *{var_g}* : *{residuel} plants*{detail}{taux_str} · 🗓️ {date_g} → en cours")
                lines_out.append("")

            lines_out.append("_Pour revenir à la synthèse : /stats_")
            texte_final = "\n".join(lines_out)

            log.info(f"📊 STATS VARIETE  : culture='{culture_arg}', {len(varietes)} variété(s), {len(godets_culture)} godet(s)")
            await _send_chunked(update, texte_final, reply_markup=MENU_KEYBOARD)
            await send_voice_reply(update, texte_final)
            return

        # ── [US_Stats_detail_par_variete / CA1] Mode synthèse (comportement existant) ──
        lines_out = [date_banner + "📊 *Statistiques potager*\n"]

        # ── [US-002] Calcul stock agronomique différencié ──────────────────────
        stocks = calcul_stock_cultures(db, date_ref, potager_id=current_context().potager_id)

        if stocks:
            # [US-003 / CA3] Séparer végétatif et reproducteur
            veg_stocks  = {c: s for c, s in stocks.items() if not s.is_reproducteur}
            repr_stocks = {c: s for c, s in stocks.items() if s.is_reproducteur}

            # [US-003 / CA1] Section végétatif — "cultures à récolte unique"
            if veg_stocks:
                lines_out.append("🥬 *Cultures végétatives (récolte destructive) :*")
                for culture, s in veg_stocks.items():
                    lines_out.append("  " + format_stock_ligne_telegram(s))

            # [US-003 / CA2] Section reproducteur — "cultures productives continues"
            if repr_stocks:
                lines_out.append("\n🍅 *Cultures reproductrices (récolte continue) :*")
                for culture, s in repr_stocks.items():
                    lines_out.append("  " + format_stock_ligne_telegram(s))

        else:
            lines_out.append("_Aucune plantation enregistrée._")

        # ── Semis ──────────────────────────────────────────────────────────────
        semis = calcul_semis(db, date_ref, potager_id=current_context().potager_id)
        if semis:
            # Pleine terre : semis directement associés à une parcelle
            semis_pt = {c: s for c, s in semis.items() if s.get("parcelles_pleine_terre")}
            # Pépinière : semis sans parcelle et non entièrement mis en godet
            semis_pep = {
                c: s for c, s in semis.items()
                if not s.get("parcelles_pleine_terre")
                and not (s.get("stock_residuel", 0) == 0 and s.get("plants_en_godet", 0) > 0)
            }

            def _ligne_semis_pep(culture: str, s: dict) -> str:
                residuel = s.get("stock_residuel", 0)
                unite    = s.get("unite", "graines")
                if residuel > 0:
                    return f"  • {culture} : *{residuel} {unite} restantes*"
                elif s.get("total_seme"):
                    return f"  • {culture} : *{int(s['total_seme'])} {unite}*"
                return f"  • {culture} : *{s['nb_semis']} semis*"

            if semis_pt or semis_pep:
                lines_out.append("\n🌱 *Semis :*")

                # Pleine terre
                if semis_pt:
                    lines_out.append("  _🌿 En pleine terre :_")
                    for culture, s in semis_pt.items():
                        total         = s.get("total_seme", 0)
                        unite         = s.get("unite", "graines")
                        parcelles_str = ", ".join(s["parcelles_pleine_terre"])
                        lines_out.append(f"  • {culture} : *{int(total)} {unite}* · _{parcelles_str}_")

                # Pépinière — semences en stock
                if semis_pep:
                    if semis_pt:
                        lines_out.append("  _📦 Pépinière — semences :_")
                    veg_pep  = {c: s for c, s in semis_pep.items() if s["type_organe"] != "reproducteur"}
                    repr_pep = {c: s for c, s in semis_pep.items() if s["type_organe"] == "reproducteur"}
                    if veg_pep:
                        lines_out.append("  _→ Récolte destructive (végétatif)_")
                        for culture, s in veg_pep.items():
                            lines_out.append(_ligne_semis_pep(culture, s))
                    if repr_pep:
                        lines_out.append("  _→ Récolte continue (reproducteur)_")
                        for culture, s in repr_pep.items():
                            lines_out.append(_ligne_semis_pep(culture, s))

        # ── [US-069 / CA6] Semis par filière : trois totaux par culture ─────────
        # Pépinière, pleine terre, et SANS CONTEXTE — compté, jamais tu (CA9).
        saison_courante = (date_ref or date.today()).year
        lignes_filiere = svc_contexte_semis.semis_par_contexte(
            db, current_context().potager_id, date_ref=date_ref, saison=saison_courante,
        )
        lines_out.extend(svc_contexte_semis.formater_semis_par_contexte_telegram(lignes_filiere, saison_courante))

        # ── Pépinière (godets) ─────────────────────────────────────────────────
        godets_stats = calcul_godets(db, date_ref=date_ref, potager_id=current_context().potager_id)
        if godets_stats:
            lines_out.append("\n🪴 *Pépinière :*")
            for key, g in godets_stats.items():
                residuel = g.get("stock_residuel_godet", g["nb_plants_godets"])
                nb_pl    = g.get("nb_plantes", 0)
                taux     = g["taux_reussite"]
                taux_str = f" · taux *{taux}%*" if taux is not None else ""
                detail   = f" ({g['nb_plants_godets']} repiqués · {nb_pl} plantés)" if nb_pl > 0 else ""
                lines_out.append(f"  • {key} : *{residuel} plants*{detail}{taux_str}")

        # ── Traitements (bonus) ───────────────────────────────────────────────
        nb_traitements = svc_evenements.compter_traitements(db, current_context())
        if nb_traitements:
            lines_out.append(f"\n💊 *Traitements :* {nb_traitements} applications")

        # [US_Stats_detail_par_variete / CA2] Hint pour le détail par variété
        lines_out.append("\n_Pour le détail d'une variété : /stats [culture]_")

        texte_final = "\n".join(lines_out)

        await _send_chunked(update, texte_final, reply_markup=MENU_KEYBOARD)

        # ── Synthèse vocale ───────────────────────────────────────────────────
        await send_voice_reply(update, texte_final)

    finally:
        db.close()


async def cmd_historique(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """20 derniers événements."""
    db = SessionLocal()
    try:
        events = svc_evenements.evenements_recents(db, current_context(), limit=10)
        if not events:
            await update.message.reply_text("📭 Aucun événement enregistré.")
            return

        lines = ["📋 *10 derniers événements :*\n"]
        for e in events:
            d      = str(e.date)[:10] if e.date else "?"
            action = (e.type_action or "?").upper()
            cult   = " ".join(filter(None, [e.culture, e.variete]))
            qte    = f"{e.quantite} {e.unite or ''}" if e.quantite else ""
            parc   = f"· {e.parcelle}" if e.parcelle else "· Non localisé"
            rang   = f" x{e.rang}rangs" if e.rang else ""
            trt    = f" ({e.traitement})" if e.traitement else ""
            lines.append(f"*{d}* — {action}\n  {cult} {qte} {parc}{rang}{trt}".strip())

        await update.message.reply_text(
            "\n\n".join(lines),
            parse_mode="Markdown",
            reply_markup=MENU_KEYBOARD
        )
        # ── Synthèse vocale de l'historique ───────────────────────────────────
        await send_voice_reply(update, "\n\n".join(lines))
    finally:
        db.close()


async def cmd_ask(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Commande /ask."""
    question = " ".join(ctx.args) if ctx.args else None
    if not question:
        await update.message.reply_text(
            "🔍 *Posez votre question :*\n\nEx : `/ask Combien de tomates cette saison ?`",
            parse_mode="Markdown"
        )
        return
    await _ask_question(update, question)


# ── COMMANDES TTS ────────────────────────────────────────────────────────────────
async def cmd_tts(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Affiche l'état de la synthèse vocale + rappel des commandes."""
    etat = "🔊 *activée*" if is_tts_enabled() else "🔇 *désactivée*"
    await update.message.reply_text(
        f"Synthèse vocale : {etat}\n\n"
        f"• `/tts_on`  — activer les réponses vocales\n"
        f"• `/tts_off` — désactiver les réponses vocales",
        parse_mode="Markdown"
    )


async def cmd_tts_on(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Active les réponses vocales (persiste au redémarrage)."""
    set_tts_enabled(True)
    log.info("🔊 TTS ACTIVÉ      : par commande utilisateur")
    await update.message.reply_text(
        "🔊 *Synthèse vocale activée !*\n\n"
        "Je vais maintenant lire mes réponses à voix haute.\n"
        "Tapez `/tts_off` pour désactiver.",
        parse_mode="Markdown"
    )


async def cmd_tts_off(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Désactive les réponses vocales (persiste au redémarrage)."""
    set_tts_enabled(False)
    log.info("🔇 TTS DÉSACTIVÉ   : par commande utilisateur")
    await update.message.reply_text(
        "🔇 *Synthèse vocale désactivée.*\n\n"
        "Tapez `/tts_on` pour réactiver.",
        parse_mode="Markdown"
    )

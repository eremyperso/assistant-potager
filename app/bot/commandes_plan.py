"""Commande /plan.

Module extrait de l'ancien bot.py monolithique (découpage 2026-09).
"""
from database.db import SessionLocal
from utils.parcelles import calcul_occupation_parcelles, get_all_parcelles
from utils.tts import send_voice_reply
from utils.cultures_icons import get_emoji_culture
from app.services.context import current_context
from .noyau import (
    MENU_KEYBOARD,
    _looks_like_date,
    _parse_date_arg,
    log,
)


# ── COMMANDES ───────────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────────────────────
# [US_Plan_occupation_parcelles / CA1-CA7, CA9] Commande /plan
# ──────────────────────────────────────────────────────────────────────────────

# [US_Plan_occupation_parcelles / CA3] Seuils d'alerte par type d'organe (jours)
SEUIL_ALERTE = {"végétatif": 45, "reproducteur": 90}


async def cmd_plan(update, ctx) -> None:
    """
    /plan [parcelle|date] — Plan d'occupation du potager.

    [CA1] Vue globale : cultures actives par parcelle avec variété et nb plants
    [CA2] Âge J+ depuis la première plantation
    [CA3] Alerte ⚠️ si âge > seuil typique (végétatif ≥ 45j, reproducteur ≥ 90j)
    [CA4] Parcelles libres affichées 🟢 [NOM] — Libre
    [CA5] /plan nord filtre sur la parcelle "nord" (insensible à la casse)
    [CA6] Hint en pied de message
    [CA7] Cultures sans parcelle sous 📍 Non localisé
    [US-030 / CA10] /plan 2025-05-01 ou /plan 01/05/2025 → état au 01/05/2025
    """
    from datetime import date as date_type
    db = SessionLocal()
    try:
        # ── [US-030] Détection date de référence dans les args ────────────────
        date_ref: date_type | None = None
        raw_args = list(ctx.args) if ctx.args else []
        args_sans_date = []
        for a in raw_args:
            parsed = _parse_date_arg(a)
            if parsed is not None:
                date_ref = parsed
            elif _looks_like_date(a):
                # [US-030 / CA14] Ressemble à une date mais invalide
                await update.message.reply_text(
                    "❌ Format de date invalide — utilise `JJ/MM/AAAA` ou `AAAA-MM-JJ`",
                    parse_mode="Markdown",
                )
                return
            else:
                args_sans_date.append(a)

        occupation = calcul_occupation_parcelles(db, date_ref, potager_id=current_context().potager_id)
        parcelles_bdd = get_all_parcelles(db, potager_id=current_context().potager_id)

        # ── [US-030] Bannière date de référence ───────────────────────────────
        date_banner = ""
        if date_ref:
            date_banner = f"📅 _État au {date_ref.strftime('%d/%m/%Y')}_\n\n"

        # ── Filtre parcelle spécifique (CA5) ──────────────────────────────────
        filtre_arg = (args_sans_date[0].strip().lower() if args_sans_date else None)

        if filtre_arg:
            # Vue détaillée d'une parcelle
            cles_norm = {
                (k.strip().lower() if k else None): k
                for k in occupation
            }
            cle_originale = cles_norm.get(filtre_arg)

            if cle_originale is None and cle_originale not in occupation:
                # Chercher dans toutes les clés normalisées
                for k in occupation:
                    if k and k.strip().lower() == filtre_arg:
                        cle_originale = k
                        break

            cultures = occupation.get(cle_originale, [])
            if not cultures:
                await update.message.reply_text(
                    f"Aucune culture active sur la parcelle *{filtre_arg.upper()}*.",
                    parse_mode="Markdown",
                )
                return

            nom_affiche = (cle_originale or filtre_arg).upper()
            lignes = [date_banner + f"📍 *{nom_affiche}* — Plan détaillé\n"]
            for c in sorted(cultures, key=lambda x: x["culture"]):
                var = f" {c['variete']}" if c["variete"] else ""
                nb = int(c["nb_plants"])
                unite = c["unite"] or "plants"
                date_str = (
                    c["date_plantation"].strftime("%d %b").lstrip("0")
                    if c["date_plantation"] else "?"
                )
                if c.get("type_action") == "semis":
                    lignes.append(
                        f"🌱 *{c['culture']}{var}*\n"
                        f"  {nb} {unite} semés le {date_str} (J+{c['age_jours']})"
                    )
                else:
                    alerte = _alerte_recolte(c["type_organe"], c["age_jours"])
                    emoji = get_emoji_culture(c["culture"], c["type_organe"])
                    lignes.append(
                        f"{emoji} *{c['culture']}{var}*\n"
                        f"  {nb} {unite} actifs · plantés le {date_str} (J+{c['age_jours']})"
                    )
                    if c["type_organe"]:
                        lignes.append(f"  Type : {c['type_organe']}")
                    if alerte:
                        seuil = SEUIL_ALERTE.get(c["type_organe"], 0)
                        lignes.append(f"  ⚠️ Récolte imminente ({c['type_organe']} > {seuil} j)")

            lignes.append(
                f"\n_Historique de rotation : \"rotation parcelle {filtre_arg}\"_"
            )
            await update.message.reply_text("\n".join(lignes), parse_mode="Markdown")
            await send_voice_reply(update, f"Détail de la parcelle {filtre_arg}")
            return

        # ── Vue globale ────────────────────────────────────────────────────────
        today = date_type.today()
        ref_day = date_ref or today
        date_str = ref_day.strftime("%d %b %Y").lstrip("0") if hasattr(ref_day, "strftime") else str(ref_day)

        lignes = [date_banner + f"📋 *Plan d'occupation — {date_str}*\n"]

        # Parcelles connues en BDD → ordre défini
        noms_bdd = {p.nom.strip().lower(): p.nom for p in parcelles_bdd}
        affichees: set = set()

        def _bloc_parcelle(nom_cle, cultures_liste: list) -> list:
            """Formate le bloc d'une parcelle avec ses cultures."""
            bloc = []
            nom_affiche = (nom_cle or "").upper()
            nb = len(cultures_liste)
            bloc.append(f"📍 *{nom_affiche}* · {nb} culture{'s' if nb > 1 else ''} active{'s' if nb > 1 else ''}")
            for c in sorted(cultures_liste, key=lambda x: x["culture"]):
                var = f" {c['variete']}" if c["variete"] else ""
                nb_plants = int(c["nb_plants"])
                unite = c["unite"] or "plants"
                if c.get("type_action") == "semis":
                    bloc.append(
                        f"  🌱 {c['culture']}{var} — {nb_plants} {unite} semés · J+{c['age_jours']}"
                    )
                else:
                    emoji = get_emoji_culture(c["culture"], c["type_organe"])
                    alerte = _alerte_recolte(c["type_organe"], c["age_jours"])
                    alerte_str = " ⚠️ récolte imminente" if alerte else ""
                    bloc.append(
                        f"  {emoji} {c['culture']}{var} — {nb_plants} {unite} · J+{c['age_jours']}{alerte_str}"
                    )
            return bloc

        # Parcelles BDD actives (ordonnées)
        for p in parcelles_bdd:
            nom_key = p.nom.strip()
            nom_lower = nom_key.lower()
            affichees.add(nom_lower)

            cultures = occupation.get(nom_key, [])
            # Essai avec la clé telle quelle, puis en ignorant la casse
            if not cultures:
                for k in occupation:
                    if k and k.strip().lower() == nom_lower:
                        cultures = occupation[k]
                        break

            if cultures:
                lignes.extend(_bloc_parcelle(nom_key, cultures))
            else:
                # [CA4] Parcelle libre
                lignes.append(f"🟢 *{nom_key.upper()}* — Libre")
            lignes.append("")  # ligne vide entre parcelles

        # Parcelles dans occupation mais pas en BDD (non référencées)
        for nom_cle, cultures in occupation.items():
            if nom_cle is None:
                continue
            if nom_cle.strip().lower() not in affichees:
                lignes.extend(_bloc_parcelle(nom_cle, cultures))
                lignes.append("")

        # [CA7] Cultures sans parcelle
        sans_parcelle = occupation.get(None, [])
        if sans_parcelle:
            nb = len(sans_parcelle)
            lignes.append(f"📍 *Non localisé* · {nb} culture{'s' if nb > 1 else ''}")
            for c in sorted(sans_parcelle, key=lambda x: x["culture"]):
                emoji = get_emoji_culture(c["culture"], c["type_organe"])
                var = f" {c['variete']}" if c["variete"] else ""
                nb_plants = int(c["nb_plants"])
                unite = c["unite"] or "plants"
                alerte = _alerte_recolte(c["type_organe"], c["age_jours"])
                alerte_str = " ⚠️ récolte imminente" if alerte else ""
                lignes.append(
                    f"  {emoji} {c['culture']}{var} — {nb_plants} {unite} · J+{c['age_jours']}{alerte_str}"
                )
            lignes.append("")

        # [CA6] Pied du message
        lignes.append("_Pour le détail : /plan [nom parcelle]_")
        lignes.append("_Historique de rotation : \"rotation parcelle X\"_")

        texte_final = "\n".join(lignes).strip()
        await update.message.reply_text(texte_final, parse_mode="Markdown")
        await send_voice_reply(update, "Plan du potager affiché")

    except Exception as e:
        log.error(f"[US_Plan_occupation_parcelles] cmd_plan erreur : {e}")
        await update.message.reply_text(f"❌ Erreur : {e}", reply_markup=MENU_KEYBOARD)
    finally:
        db.close()


def _alerte_recolte(type_organe: str | None, age_jours: int) -> bool:
    """[CA3] Retourne True si la culture dépasse le seuil d'alerte."""
    if type_organe and type_organe in SEUIL_ALERTE:
        return age_jours >= SEUIL_ALERTE[type_organe]
    return False

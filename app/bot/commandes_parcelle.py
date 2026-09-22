"""Commande /parcelle et suppression confirmée.

Module extrait de l'ancien bot.py monolithique (découpage 2026-09).
"""
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from database.db import SessionLocal
from utils.parcelles import normalize_parcelle_name, find_doublon, update_parcelle, get_all_parcelles, resolve_parcelle, rename_parcelle
from app.services.context import current_context
from app.services import evenements as svc_evenements
from app.services import parcelles as svc_parcelles
from .noyau import MENU_KEYBOARD, _md, log
from .liaison import _refuser_si_role_insuffisant


async def cmd_parcelle(update, ctx) -> None:
    """
    /parcelle <sous-commande> — Gestion des parcelles.

    Sous-commandes :
      ajouter [nom] [exposition] [superficie]  — créer une parcelle (CA10, CA12, CA13)
      modifier [nom] clé=valeur ...             — mettre à jour les métadonnées
      lister                                    — afficher toutes les parcelles
    """
    USAGE = (
        "*Usage :*\n"
        "  /parcelle ajouter [nom] [exposition] [superficie]\n"
        "  /parcelle modifier [nom] exposition=sud superficie=8.5\n"
        "  /parcelle renommer <ancien_nom> <nouveau_nom>\n"
        "  /parcelle lister\n\n"
        "Exemples :\n"
        "  /parcelle ajouter nord sud 12.5\n"
        "  /parcelle modifier nord exposition=sud superficie=8.5\n"
        "  /parcelle modifier serre pepiniere=true\n"
        "  /parcelle modifier nord rangs=5   (ou rangs=aucun)\n"
        "  /parcelle renommer sud carré-sud\n\n"
        "_Pour supprimer une parcelle : /help parcelle_"
    )

    if not ctx.args:
        await update.message.reply_text(USAGE, parse_mode="Markdown")
        return

    sous_cmd = ctx.args[0].lower()

    # ── /parcelle lister ──────────────────────────────────────────────────────
    if sous_cmd == "lister":
        db = SessionLocal()
        try:
            parcelles = get_all_parcelles(db, potager_id=current_context().potager_id)
            if not parcelles:
                await update.message.reply_text(
                    "📋 Aucune parcelle enregistrée.\n"
                    "Créez-en une : /parcelle ajouter [nom]",
                    parse_mode="Markdown",
                )
                return
            lignes = [f"📋 *Parcelles enregistrées ({len(parcelles)})*\n"]
            for p in parcelles:
                details = []
                if p.exposition:
                    details.append(f"exposition {p.exposition}")
                if p.superficie_m2 is not None:
                    details.append(f"{p.superficie_m2} m²")
                if p.est_pepiniere:
                    details.append("🌱 pépinière")
                if p.abri and p.abri != "aucun":
                    details.append(f"abri : {p.abri}")
                if p.paillage:
                    details.append("paillée")
                # [US-197 / CA5] Le nombre de rangs se dit TOUJOURS, y compris
                # absent : c'est le dénominateur de la Vue plan, et son silence
                # se lirait comme « zéro rang » plutôt que « jamais déclaré ».
                details.append(
                    f"{p.nb_rangs} rang{'s' if p.nb_rangs > 1 else ''}"
                    if p.nb_rangs is not None else "rangs non renseignés"
                )
                detail_str = f" · {' · '.join(details)}" if details else ""
                lignes.append(f"📍 *{p.nom.upper()}*{detail_str}")
            lignes.append("\n_Ajouter : /parcelle ajouter [nom] [exposition] [superficie]_")
            lignes.append("_Modifier : /parcelle modifier [nom] clé=valeur_")
            await update.message.reply_text("\n".join(lignes), parse_mode="Markdown")
        except Exception as e:
            log.error(f"[US_Plan_occupation_parcelles] cmd_parcelle lister erreur : {e}")
            await update.message.reply_text(f"❌ Erreur : {e}")
        finally:
            db.close()
        return

    # ── /parcelle modifier [nom] clé=valeur ... ───────────────────────────────
    if sous_cmd == "modifier":
        if await _refuser_si_role_insuffisant(update, "modifier une parcelle"):
            return
        if len(ctx.args) < 3:
            await update.message.reply_text(
                "❌ Usage : /parcelle modifier [nom] clé=valeur ...\n"
                "Exemple : /parcelle modifier nord exposition=sud superficie=8.5",
                parse_mode="Markdown",
            )
            return

        nom = ctx.args[1].strip()
        kwargs: dict = {}
        for token in ctx.args[2:]:
            if "=" in token:
                k, _, v = token.partition("=")
                kwargs[k.lower().strip()] = v.strip()
            else:
                await update.message.reply_text(
                    f"❌ Paramètre invalide : *{token}*\n"
                    "Format attendu : clé=valeur (ex : exposition=sud)",
                    parse_mode="Markdown",
                )
                return

        db = SessionLocal()
        try:
            parc, modifs = update_parcelle(db, nom, potager_id=current_context().potager_id, **kwargs)
            lignes = [f"✅ Parcelle *{parc.nom.upper()}* mise à jour :"]
            for m in modifs:
                lignes.append(f"  · {m}")
            await update.message.reply_text("\n".join(lignes), parse_mode="Markdown")
        except LookupError:
            all_p = get_all_parcelles(db, potager_id=current_context().potager_id)
            noms = ", ".join(p.nom.lower() for p in all_p) or "(aucune)"
            await update.message.reply_text(
                f"❌ Parcelle *{nom}* introuvable.\nParcelles connues : {noms}",
                parse_mode="Markdown",
            )
        except ValueError as e:
            await update.message.reply_text(f"❌ {e}", parse_mode="Markdown")
        except Exception as e:
            log.error(f"[US_Plan_occupation_parcelles] cmd_parcelle modifier erreur : {e}")
            await update.message.reply_text(f"❌ Erreur : {e}")
        finally:
            db.close()
        return

    # ── /parcelle ajouter [nom] [exposition] [superficie] ─────────────────────
    if sous_cmd == "ajouter":
        if await _refuser_si_role_insuffisant(update, "créer une parcelle"):
            return
        if len(ctx.args) < 2:
            await update.message.reply_text(
                "❌ Précisez le nom de la parcelle.\nExemple : /parcelle ajouter nord",
                parse_mode="Markdown",
            )
            return

        nom = ctx.args[1].strip()
        # Parsing optionnel : arg[2]=exposition (texte), arg[3]=superficie (float)
        exposition: str | None = None
        superficie_m2: float | None = None
        extra = ctx.args[2:]
        for tok in extra:
            try:
                superficie_m2 = float(tok.replace(",", "."))
            except ValueError:
                exposition = tok

        nom_normalise = normalize_parcelle_name(nom)

        db = SessionLocal()
        try:
            exact, proche = find_doublon(db, nom_normalise, potager_id=current_context().potager_id)

            # [US-172] Une parcelle supprimée porte toujours son nom en base :
            # elle bloquait la recréation sans être visible nulle part. La
            # recréer la remet en service (`utils.parcelles.create_parcelle`),
            # et le récapitulatif le dit plutôt que de laisser croire à une
            # création neuve.
            remise_en_service = bool(exact) and not exact.actif

            # [CA10] Doublon exact
            if exact and exact.actif:
                log.info(f"[US_Plan_occupation_parcelles] Doublon exact : {nom!r} → {exact.nom!r}")
                await update.message.reply_text(
                    f"❌ La parcelle *{_md(exact.nom.upper())}* existe déjà.\n"
                    "Utilisez /plan pour consulter les parcelles existantes.",
                    parse_mode="Markdown",
                )
                return

            # [CA12] Variante proche
            if proche:
                log.info(f"[US_Plan_occupation_parcelles] Variante proche : {nom!r} ≈ {proche.nom!r}")
                ctx.user_data['mode'] = 'parcelle_confirm'
                ctx.user_data['parcelle_pending'] = {
                    "nom": nom,
                    "exposition": exposition,
                    "superficie_m2": superficie_m2,
                }
                await update.message.reply_text(
                    f"⚠️ Une parcelle similaire existe : *{_md(proche.nom.upper())}*.\n"
                    f"Confirmer la création de *{_md(nom.upper())}* ? _(oui / non)_",
                    parse_mode="Markdown",
                )
                return

            # [CA13] Pas de doublon → récapitulatif + confirmation
            parcelles_existantes = get_all_parcelles(db, potager_id=current_context().potager_id)
            lignes = ["📋 *Parcelles existantes :*"]
            for p in parcelles_existantes:
                lignes.append(f"  · {_md(p.nom.upper())}")
            if not parcelles_existantes:
                lignes.append("  _(aucune pour l'instant)_")

            detail_parts = []
            if exposition:
                detail_parts.append(f"exposition : {exposition}")
            if superficie_m2 is not None:
                detail_parts.append(f"superficie : {superficie_m2} m²")
            detail_conf = f" ({', '.join(detail_parts)})" if detail_parts else ""
            if remise_en_service:
                lignes.append(
                    f"\n♻️ La parcelle *{_md(nom.upper())}* avait été supprimée."
                    f"\nLa remettre en service{detail_conf} ? _(oui / non)_"
                    f"\n_Les gestes qu'elle portait restent « non localisés »._"
                )
            else:
                lignes.append(
                    f"\n➕ Créer la parcelle *{_md(nom.upper())}*{detail_conf} ? _(oui / non)_"
                )

            ctx.user_data['mode'] = 'parcelle_confirm'
            ctx.user_data['parcelle_pending'] = {
                "nom": nom,
                "exposition": exposition,
                "superficie_m2": superficie_m2,
            }
            await update.message.reply_text("\n".join(lignes), parse_mode="Markdown")

        except Exception as e:
            log.error(f"[US_Plan_occupation_parcelles] cmd_parcelle ajouter erreur : {e}")
            await update.message.reply_text(f"❌ Erreur : {e}", reply_markup=MENU_KEYBOARD)
        finally:
            db.close()
        return

    # ── /parcelle renommer <ancien> <nouveau> ─────────────────────────────────
    if sous_cmd == "renommer":
        if await _refuser_si_role_insuffisant(update, "renommer une parcelle"):
            return
        if len(ctx.args) < 3:
            await update.message.reply_text(
                "❌ Usage : /parcelle renommer \\<ancien\\_nom\\> \\<nouveau\\_nom\\>\n"
                "Exemple : /parcelle renommer sud carré\\-sud",
                parse_mode="MarkdownV2",
            )
            return
        ancien = ctx.args[1].strip()
        nouveau = " ".join(ctx.args[2:]).strip()  # supporte noms avec espaces
        db = SessionLocal()
        try:
            parc, nb = rename_parcelle(db, ancien, nouveau, potager_id=current_context().potager_id)
            await update.message.reply_text(
                f"✅ Parcelle renommée : *{ancien}* → *{parc.nom}* "
                f"({nb} événement{'s' if nb > 1 else ''} mis à jour)",
                parse_mode="Markdown",
            )
        except LookupError:
            await update.message.reply_text(
                f"❌ Parcelle introuvable : *{ancien}*",
                parse_mode="Markdown",
            )
        except ValueError:
            await update.message.reply_text(
                "❌ Ce nom est déjà utilisé par une autre parcelle",
                parse_mode="Markdown",
            )
        except Exception as e:
            log.error(f"[US-006] cmd_parcelle renommer erreur : {e}")
            await update.message.reply_text(f"❌ Erreur : {e}")
        finally:
            db.close()
        return

    # ── /parcelle supprimer <nom> ─────────────────────────────────────────────
    if sous_cmd == "supprimer":
        if await _refuser_si_role_insuffisant(update, "supprimer une parcelle"):
            return
        if len(ctx.args) < 2:
            await update.message.reply_text(
                "❌ Précisez le nom de la parcelle.\nExemple : /parcelle supprimer serre-1",
                parse_mode="Markdown",
            )
            return
        nom = " ".join(ctx.args[1:]).strip()
        db = SessionLocal()
        try:
            parcelle = resolve_parcelle(db, nom, potager_id=current_context().potager_id)
            if parcelle is None:
                all_p = get_all_parcelles(db, potager_id=current_context().potager_id)
                noms = ", ".join(p.nom.lower() for p in all_p) or "(aucune)"
                await update.message.reply_text(
                    f"❌ Parcelle introuvable : *{nom}*\nParcelles connues : {noms}",
                    parse_mode="Markdown",
                )
                return
            nb = svc_evenements.compter_evenements_parcelle(db, current_context(), parcelle.id)
            nb_str = (
                f"⚠️ *{nb} événement{'s' if nb > 1 else ''}* seront réaffectés en *Non localisé*."
                if nb > 0 else "Aucun événement associé."
            )
            buttons = [[
                InlineKeyboardButton("✅ Confirmer", callback_data=f"parcelle_suppr_confirm:{parcelle.id}"),
                InlineKeyboardButton("❌ Annuler",   callback_data="parcelle_suppr_cancel"),
            ]]
            log.info(f"[US-009] Demande suppression : {parcelle.nom!r} — {nb} événements")
            await update.message.reply_text(
                f"🗑 Supprimer la parcelle *{parcelle.nom.upper()}* ?\n{nb_str}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        except Exception as e:
            log.error(f"[US-009] cmd_parcelle supprimer erreur : {e}")
            await update.message.reply_text(f"❌ Erreur : {e}")
        finally:
            db.close()
        return

    # Sous-commande inconnue
    await update.message.reply_text(USAGE, parse_mode="Markdown")


async def _cmd_parcelles_lister(update, ctx) -> None:
    """Alias /parcelles → /parcelle lister."""
    ctx.args = ["lister"]
    await cmd_parcelle(update, ctx)


# ── [US-009] CALLBACK SUPPRESSION PARCELLE ──────────────────────────────────────

async def _parcelle_suppr_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """[US-009] Callback inline — confirmation ou annulation de suppression de parcelle."""
    query = update.callback_query
    await query.answer()

    if query.data == "parcelle_suppr_cancel":
        await query.edit_message_text("Suppression annulée — la parcelle est conservée.", reply_markup=None)
        return

    # parcelle_suppr_confirm:<parcelle_id>
    try:
        parcelle_id = int(query.data.split(":")[1])
    except (IndexError, ValueError):
        await query.edit_message_text("❌ Données invalides.", reply_markup=None)
        return

    db = SessionLocal()
    try:
        tenant_ctx = current_context()
        parcelle = svc_parcelles.get_parcelle(db, tenant_ctx, parcelle_id)
        if parcelle is None or not parcelle.actif:
            await query.edit_message_text("❌ Parcelle introuvable ou déjà supprimée.", reply_markup=None)
            return
        nom = parcelle.nom
        nb = svc_evenements.liberer_evenements_parcelle(db, tenant_ctx, parcelle_id)
        parcelle.actif = False
        db.commit()
        log.info(f"[US-009] Parcelle supprimée : {nom!r} — {nb} événements réaffectés")
        if nb > 0:
            msg = (
                f"✅ Parcelle *{nom.upper()}* supprimée — "
                f"{nb} événement{'s' if nb > 1 else ''} réaffectés en *Non localisé*"
            )
        else:
            msg = f"✅ Parcelle *{nom.upper()}* supprimée"
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=None)
    except Exception as e:
        db.rollback()
        log.error(f"[US-009] _parcelle_suppr_cb erreur : {e}")
        await query.edit_message_text(f"❌ Erreur : {e}", reply_markup=None)
    finally:
        db.close()

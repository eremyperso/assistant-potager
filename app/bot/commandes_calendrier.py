"""Commande /calendrier [US-068].

Module extrait de l'ancien bot.py monolithique (découpage 2026-09).
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from database.db import SessionLocal
from app.services.context import current_context
from app.services import calendrier_cultural as svc_calendrier
from app.services.permissions import PermissionInsuffisanteError, PotagerArchiveError
from .noyau import _md, log


# ──────────────────────────────────────────────────────────────────────────────
# [US-068 / CA10, CA11] Commande /calendrier — calendrier cultural et zone climatique
# ──────────────────────────────────────────────────────────────────────────────
def _fusionner_pleine_terre(jetons: list[str]) -> list[str]:
    """« pleine terre » tapé en deux mots devient un seul jeton de phase."""
    fusion: list[str] = []
    for jeton in jetons:
        if fusion and fusion[-1].lower() == "pleine" and jeton.lower() == "terre":
            fusion[-1] = "pleine_terre"
        else:
            fusion.append(jeton)
    return fusion


def _decouper_correction(jetons: list[str], est_cle, parser) -> "tuple[list[str], str, str] | None":
    """
    Découpe « <culture> [itinéraire] <clé> <valeur> » en partant de la FIN.

    La clé (phase ou étape) est la dernière position dont le reste se lit comme
    une valeur valide : « pomme de terre recolte juillet » ne confond pas
    « terre » avec une phase, et « mars à mai » reste une seule valeur.
    Retourne (jetons de culture et d'itinéraire, clé, valeur) ou None.
    """
    for i in range(len(jetons) - 2, 0, -1):
        if not est_cle(jetons[i]):
            continue
        valeur = " ".join(jetons[i + 1:])
        try:
            parser(valeur)
        except svc_calendrier.ValeurCalendrierInvalideError:
            continue
        return jetons[:i], jetons[i], valeur
    return None


def _formater_calendrier(calendrier, itineraire_cible: "str | None" = None) -> str:
    """Rendu Telegram d'un calendrier — aucune date calculée, aucune valeur empruntée."""
    lignes = [
        f"📅 *{_md(calendrier.culture)}* — calendrier cultural",
        f"Zone : {_md(svc_calendrier.libelle_zone(calendrier.zone, calendrier.zone_origine, calendrier.zone_altitude))}",
    ]
    itineraires = calendrier.itineraires
    if itineraire_cible:
        cle = svc_calendrier.normaliser_itineraire(itineraire_cible)
        itineraires = [
            it for it in itineraires if svc_calendrier.normaliser_itineraire(it.nom) == cle
        ] or itineraires

    for it in itineraires:
        lignes.append("")
        entete = f"*{_md(it.nom)}*"
        if it.personnalise:
            entete += " — propre à votre potager"
        lignes.append(entete)
        if it.fenetres:
            lues = {fenetre.phase: fenetre for fenetre in it.fenetres}
            for phase in svc_calendrier.PHASES:
                fenetre = lues.get(phase)
                if fenetre:
                    lignes.append(f"• {fenetre.libelle} : *{_md(fenetre.affichage)}*")
                elif phase == svc_calendrier.PHASE_PLANTATION:
                    # [US-068 / CA27] La plantation se dit vide plutôt que de se
                    # taire : c'est le geste que la plupart des jardiniers font,
                    # et son absence ne se déduit jamais du semis (CA18).
                    lignes.append(f"• {svc_calendrier.LIBELLES_PHASES[phase]} : —")
        else:
            # [CA13] Frise neutre : dire qu'on ne sait pas, sans rien emprunter.
            texte = (
                "Aucune fenêtre renseignée pour la zone "
                f"{svc_calendrier.LIBELLES_ZONES.get(calendrier.zone, calendrier.zone)}"
            )
            autres = [
                svc_calendrier.LIBELLES_ZONES[z] for z in it.zones_renseignees if z != calendrier.zone
            ]
            if autres:
                texte += f" (renseignée pour : {', '.join(autres)})"
            lignes.append(f"• {_md(texte)}")
        for duree in it.durees:
            valeur = f"*{_md(duree.affichage)}*" if duree.renseignee else duree.affichage
            lignes.append(f"• {duree.libelle} : {valeur}")

    lignes.append("")
    # [CA4] Une fourchette n'est jamais une date certaine.
    lignes.append("_Durées indicatives : des ordres de grandeur, jamais des dates._")
    if calendrier.attributions:
        lignes.append("Source : " + " · ".join(calendrier.attributions))
    return "\n".join(lignes)


# ──────────────────────────────────────────────────────────────────────────────
# [US-279] /calendrier maj — remplacer une copie personnalisée par le référentiel
# ──────────────────────────────────────────────────────────────────────────────
def _nom_ecart(ecart) -> str:
    """« courgette », ou « chou-fleur — culture d'hiver » hors itinéraire standard."""
    if svc_calendrier.normaliser_itineraire(ecart.itineraire) == svc_calendrier.ITINERAIRE_PAR_DEFAUT:
        return ecart.culture
    return f"{ecart.culture} — {ecart.itineraire}"


def _resume_differences(ecart) -> str:
    nb = len(ecart.differences)
    texte = f"{nb} valeur{'s' if nb > 1 else ''} différente{'s' if nb > 1 else ''}" if nb else "aucune valeur pour votre zone"
    if ecart.autres_zones:
        texte += ", et d'autres zones"
    return texte


def _texte_liste(ecarts) -> str:
    """[CA3] Les cultures en retard sur le référentiel, une ligne chacune."""
    lignes = ["🔄 *Le référentiel a évolué pour des cultures que vous avez personnalisées :*", ""]
    for ecart in ecarts:
        lignes.append(f"• *{_md(_nom_ecart(ecart))}* — {_md(_resume_differences(ecart))}")
    lignes.append("")
    lignes.append("Choisissez une culture pour voir ce qui change.")
    return "\n".join(lignes)


def _clavier_liste(ecarts) -> InlineKeyboardMarkup:
    lignes = [
        [InlineKeyboardButton(_nom_ecart(e), callback_data=f"calmaj:v:{e.itineraire_id}")]
        for e in ecarts
    ]
    # [CA3] À partir de deux cultures, tout d'un coup.
    if len(ecarts) >= 2:
        lignes.append([InlineKeyboardButton(f"Tout mettre à jour ({len(ecarts)})", callback_data="calmaj:t")])
    return InlineKeyboardMarkup(lignes)


def _texte_ecart(ecart) -> str:
    """[CA4] Avant/après pour la zone du potager et les durées, et l'avertissement."""
    lignes = [f"🔄 *{_md(_nom_ecart(ecart))}* — votre calendrier et le référentiel", ""]
    for diff in ecart.differences:
        lignes.append(f"• {_md(diff.libelle)} : {_md(diff.avant)} → *{_md(diff.apres)}*")
    if ecart.autres_zones:
        lignes.append("• D'autres zones climatiques changent aussi.")
    lignes.append("")
    lignes.append(
        "_Remplacer reprend tout le calendrier du référentiel : les corrections "
        "faites sur ce calendrier seront perdues._"
    )
    return "\n".join(lignes)


def _clavier_ecart(ecart) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Remplacer par le référentiel", callback_data=f"calmaj:r:{ecart.itineraire_id}"),
        InlineKeyboardButton("🔒 Garder ma version", callback_data=f"calmaj:g:{ecart.itineraire_id}"),
    ]])


async def _repondre_maj(message, db, tenant_ctx, jetons: list[str]) -> None:
    """[CA3, CA4] `/calendrier maj [culture]` — lecture seule, rien n'est écrit."""
    if not jetons:
        ecarts = svc_calendrier.ecarts_referentiel(db, tenant_ctx.potager_id)
        log.info(f"[US-279] /calendrier maj : {len(ecarts)} culture(s) en retard (potager_id={tenant_ctx.potager_id})")
        if not ecarts:
            await message.reply_text("✅ Le calendrier de votre potager suit déjà le référentiel.")
            return
        await message.reply_text(_texte_liste(ecarts), parse_mode="Markdown", reply_markup=_clavier_liste(ecarts))
        return

    culture, _ = svc_calendrier.separer_culture_itineraire(db, list(jetons), tenant_ctx.potager_id)
    etat = svc_calendrier.etat_mise_a_jour(db, tenant_ctx.potager_id, culture)
    log.info(f"[US-279] /calendrier maj '{culture}' : {etat.statut} (potager_id={tenant_ctx.potager_id})")
    raisons = {
        svc_calendrier.STATUT_CULTURE_INCONNUE: (
            f"❌ Culture inconnue : *{_md(culture)}*\nElle doit avoir déjà été dictée au moins une fois."
        ),
        svc_calendrier.STATUT_SANS_COPIE: (
            f"✅ *{_md(culture)}* : vous n'avez pas personnalisé son calendrier, "
            "il suit déjà le référentiel."
        ),
        svc_calendrier.STATUT_A_JOUR: (
            f"✅ *{_md(culture)}* : le référentiel n'a pas évolué depuis votre version."
        ),
    }
    if etat.statut != svc_calendrier.STATUT_ECART:
        await message.reply_text(raisons[etat.statut], parse_mode="Markdown")
        return
    for ecart in etat.ecarts:
        await message.reply_text(_texte_ecart(ecart), parse_mode="Markdown", reply_markup=_clavier_ecart(ecart))


async def _calendrier_maj_cb(update, ctx) -> None:
    """
    [US-279] Boutons de `/calendrier maj` :
      calmaj:v:<id>  détail d'une copie           calmaj:r:<id>  remplacer (CA5)
      calmaj:g:<id>  garder ma version (CA7)      calmaj:t       tout : confirmation
      calmaj:T       tout : confirmé (CA6)        calmaj:x       annuler
    Le clic sur ✅ EST la confirmation : rien n'est écrit avant.
    """
    query = update.callback_query
    await query.answer()
    _, action, *reste = query.data.split(":")
    tenant_ctx = current_context()
    db = SessionLocal()
    try:
        if action == "x":
            await query.edit_message_text("D'accord, je ne change rien.")
            return

        if action == "v":
            ecart = next(
                (e for e in svc_calendrier.ecarts_referentiel(db, tenant_ctx.potager_id)
                 if e.itineraire_id == int(reste[0])),
                None,
            )
            if ecart is None:
                await query.message.reply_text("✅ Ce calendrier suit déjà le référentiel.")
                return
            await query.message.reply_text(
                _texte_ecart(ecart), parse_mode="Markdown", reply_markup=_clavier_ecart(ecart)
            )
            return

        if action == "t":
            ecarts = svc_calendrier.ecarts_referentiel(db, tenant_ctx.potager_id)
            if not ecarts:
                await query.edit_message_text("✅ Le calendrier de votre potager suit déjà le référentiel.")
                return
            noms = ", ".join(_nom_ecart(e) for e in ecarts)
            await query.message.reply_text(
                f"Remplacer par le référentiel le calendrier de : *{_md(noms)}* ?\n"
                "_Les corrections faites sur ces calendriers seront perdues._",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(f"✅ Tout remplacer ({len(ecarts)})", callback_data="calmaj:T"),
                    InlineKeyboardButton("❌ Annuler", callback_data="calmaj:x"),
                ]]),
            )
            return

        if action in ("r", "T"):
            ids = (
                [int(reste[0])] if action == "r"
                else [e.itineraire_id for e in svc_calendrier.ecarts_referentiel(db, tenant_ctx.potager_id)]
            )
            remplaces = svc_calendrier.remplacer_par_referentiel(db, tenant_ctx, ids)
            noms = ", ".join(_nom_ecart(e) for e in remplaces)
            await query.edit_message_text(
                f"✅ Calendrier remplacé par le référentiel : *{_md(noms)}*\n"
                "_Il suit désormais les mises à jour du référentiel, jusqu'à votre prochaine correction._",
                parse_mode="Markdown",
            )
            return

        if action == "g":
            ecart = svc_calendrier.garder_version_locale(db, tenant_ctx, int(reste[0]))
            await query.edit_message_text(
                f"🔒 Vous gardez votre calendrier : *{_md(_nom_ecart(ecart))}*\n"
                "_Je vous le reproposerai si le référentiel évolue de nouveau._",
                parse_mode="Markdown",
            )
            return
    except svc_calendrier.ValeurCalendrierInvalideError as err:
        await query.message.reply_text(f"❌ {err}\nRien n'a été modifié.")
    except (PermissionInsuffisanteError, PotagerArchiveError) as err:
        await query.message.reply_text(f"⛔ {err}")
    except Exception as e:
        log.error(f"[US-279] _calendrier_maj_cb erreur : {e}")
        # [CA6] Tout ou rien : le service a annulé la transaction.
        await query.message.reply_text("❌ La mise à jour a échoué : rien n'a été modifié.")
    finally:
        db.close()


async def cmd_calendrier(update, ctx) -> None:
    """
    /calendrier — Calendrier cultural d'une culture et zone climatique du potager (US-068).

    Sous-commandes :
      <culture> [itinéraire]                               — consulter (zéro jeton)
      zone [oceanique|continental|mediterraneen|montagnard|auto]
                                                           — lire ou choisir la zone (CA7)
      fenetre <culture> [itinéraire] <pepiniere|pleine_terre|plantation|recolte> <mars-mai|aucune>
      duree <culture> [itinéraire] <levee|recolte|repiquage|plantation-recolte|semis-godet> <jours|70-90|mention|aucune>
                                                           — corriger (CA10)
      maj [culture]                                        — remplacer une copie personnalisée
                                                             par le référentiel (US-279)

    Aucune logique métier ici : lecture, validation et écriture vivent dans
    `app.services.calendrier_cultural`. Une correction est TOUJOURS propre au
    potager courant (CA11) et confirme l'ancienne et la nouvelle valeur (CA10).
    """
    USAGE = (
        "*Usage :*\n"
        "  /calendrier <culture>\n"
        "  /calendrier zone [océanique|continental|méditerranéen|montagnard|auto]\n"
        "  /calendrier fenetre <culture> [itinéraire] <pepiniere|pleine\\_terre|plantation|recolte> <mois-mois|aucune>\n"
        "  /calendrier duree <culture> [itinéraire] <levee|recolte|repiquage|plantation-recolte|semis-godet> <jours|aucune>\n"
        "  /calendrier maj [culture]\n\n"
        "Exemples :\n"
        "  /calendrier tomate\n"
        "  /calendrier zone méditerranéen\n"
        "  /calendrier fenetre tomate pepiniere février-avril\n"
        "  /calendrier fenetre tomate plantation mai-juin\n"
        "  /calendrier fenetre chou-fleur culture d'hiver recolte novembre-février\n"
        "  /calendrier duree courgette recolte 50-60\n"
        "  /calendrier duree tomate plantation-recolte 60-80\n"
        "  /calendrier duree chou semis-godet 10-15\n"
        "  /calendrier maj courgette\n\n"
        "_Vos corrections ne valent que pour votre potager. /calendrier maj dit si le "
        "référentiel a évolué depuis, et propose de reprendre sa version._"
    )

    if not ctx.args:
        await update.message.reply_text(USAGE, parse_mode="Markdown")
        return

    sous_cmd = svc_calendrier.normaliser_itineraire(ctx.args[0])
    tenant_ctx = current_context()
    db = SessionLocal()
    try:
        # ── /calendrier zone [valeur] ─────────────────────────────────────────
        if sous_cmd == "zone":
            if len(ctx.args) == 1:
                zone, origine, altitude = svc_calendrier.zone_et_altitude_du_potager(db, tenant_ctx.potager_id)
                await update.message.reply_text(
                    f"🗺️ Zone climatique du potager : *{_md(svc_calendrier.libelle_zone(zone, origine, altitude))}*\n"
                    "Pour la choisir : /calendrier zone <océanique|continental|méditerranéen|montagnard>\n"
                    "Pour revenir à la localisation : /calendrier zone auto",
                    parse_mode="Markdown",
                )
                return
            valeur = " ".join(ctx.args[1:]).strip()
            try:
                avant, apres = svc_calendrier.definir_zone(db, tenant_ctx, valeur)
            except svc_calendrier.ValeurCalendrierInvalideError as err:
                await update.message.reply_text(f"❌ {_md(str(err))}", parse_mode="Markdown")
                return
            except (PermissionInsuffisanteError, PotagerArchiveError) as err:
                await update.message.reply_text(f"⛔ {err}")
                return
            # [US-193 / CA7] L'altitude est celle du potager, avant comme après.
            altitude = svc_calendrier.zone_et_altitude_du_potager(db, tenant_ctx.potager_id)[2]
            await update.message.reply_text(
                f"✅ Zone climatique : *{_md(svc_calendrier.libelle_zone(*avant, altitude))}* → "
                f"*{_md(svc_calendrier.libelle_zone(*apres, altitude))}*",
                parse_mode="Markdown",
            )
            return

        # ── /calendrier maj [culture] — US-279 ────────────────────────────────
        if sous_cmd in ("maj", "mise-a-jour"):
            await _repondre_maj(update.message, db, tenant_ctx, " ".join(ctx.args[1:]).split())
            return

        # ── /calendrier fenetre|duree … ───────────────────────────────────────
        if sous_cmd in ("fenetre", "fenetres", "duree", "durees"):
            est_fenetre = sous_cmd.startswith("fenetre")
            # Un argument dicté peut porter plusieurs mots (« petit pois ») :
            # le découpage se fait sur les mots, comme pour une commande tapée.
            jetons = _fusionner_pleine_terre(" ".join(ctx.args[1:]).split())
            decoupe = _decouper_correction(
                jetons,
                svc_calendrier.est_phase if est_fenetre else svc_calendrier.est_etape,
                svc_calendrier.parser_fenetre if est_fenetre else svc_calendrier.parser_duree,
            )
            if decoupe is None:
                exemple = (
                    "/calendrier fenetre tomate pepiniere février-avril" if est_fenetre
                    else "/calendrier duree courgette recolte 50-60"
                )
                await update.message.reply_text(
                    "❌ Je n'ai pas reconnu la correction.\n"
                    f"Exemple : {_md(exemple)}\n\n{USAGE}",
                    parse_mode="Markdown",
                )
                return
            jetons_culture, cle, valeur = decoupe
            culture, itineraire = svc_calendrier.separer_culture_itineraire(
                db, jetons_culture, tenant_ctx.potager_id
            )
            try:
                if est_fenetre:
                    zone, avant, apres = svc_calendrier.corriger_fenetre(
                        db, tenant_ctx, culture, cle, valeur, itineraire=itineraire
                    )
                    libelle = (
                        f"{svc_calendrier.LIBELLES_PHASES[svc_calendrier.normaliser_phase(cle)]} "
                        f"(zone {svc_calendrier.LIBELLES_ZONES.get(zone, zone)})"
                    )
                else:
                    avant, apres = svc_calendrier.corriger_duree(
                        db, tenant_ctx, culture, cle, valeur, itineraire=itineraire
                    )
                    libelle = svc_calendrier.LIBELLES_ETAPES[svc_calendrier.normaliser_etape(cle)]
            except svc_calendrier.CultureInconnueError:
                await update.message.reply_text(
                    f"❌ Culture inconnue : *{_md(culture)}*\n"
                    "Elle doit avoir déjà été dictée au moins une fois.",
                    parse_mode="Markdown",
                )
                return
            except svc_calendrier.ValeurCalendrierInvalideError as err:
                await update.message.reply_text(
                    f"❌ {_md(str(err))}\nRien n'a été modifié.", parse_mode="Markdown"
                )
                return
            except (PermissionInsuffisanteError, PotagerArchiveError) as err:
                await update.message.reply_text(f"⛔ {err}")
                return
            log.info(
                f"[US-068] /calendrier {sous_cmd} '{culture}' / '{itineraire}' {cle} : "
                f"'{avant}' → '{apres}' (potager_id={tenant_ctx.potager_id})"
            )
            await update.message.reply_text(
                f"✅ *{_md(culture)}* — {_md(itineraire)}\n"
                f"{_md(libelle)} : *{_md(avant)}* → *{_md(apres)}*\n"
                "_Correction propre à votre potager._",
                parse_mode="Markdown",
            )
            return

        # ── /calendrier <culture> [itinéraire] ────────────────────────────────
        jetons = " ".join(
            ctx.args[1:] if sous_cmd in ("voir", "lire", "consulter") else ctx.args
        ).split()
        if not jetons:
            await update.message.reply_text(USAGE, parse_mode="Markdown")
            return
        culture, itineraire = svc_calendrier.separer_culture_itineraire(
            db, list(jetons), tenant_ctx.potager_id
        )
        calendrier = svc_calendrier.lire_calendrier(db, culture, tenant_ctx.potager_id)
        log.info(
            f"[US-068] /calendrier '{culture}' : connue={calendrier.culture_connue} "
            f"renseigne={calendrier.renseigne} zone={calendrier.zone} ({calendrier.zone_origine}), 0 jeton"
        )
        if not calendrier.culture_connue:
            await update.message.reply_text(
                f"❌ Culture inconnue : *{_md(culture)}*\n"
                "Elle doit avoir déjà été dictée au moins une fois.",
                parse_mode="Markdown",
            )
            return
        cible = itineraire if itineraire != svc_calendrier.ITINERAIRE_PAR_DEFAUT else None
        texte = _formater_calendrier(calendrier, cible)
        # [US-279 / CA8] Indice passif : dit qu'une mise à jour attend, sans
        # jamais rien envoyer spontanément.
        if svc_calendrier.etat_mise_a_jour(db, tenant_ctx.potager_id, culture).statut == svc_calendrier.STATUT_ECART:
            texte += (
                "\n\nℹ️ Le référentiel a évolué depuis votre copie — "
                f"/calendrier maj {_md(culture)}"
            )
        await update.message.reply_text(texte, parse_mode="Markdown")
    except Exception as e:
        log.error(f"[US-068] cmd_calendrier erreur : {e}")
        await update.message.reply_text(f"❌ Erreur : {e}")
    finally:
        db.close()

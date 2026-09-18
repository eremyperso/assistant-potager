"""Commande /calendrier [US-068].

Module extrait de l'ancien bot.py monolithique (découpage 2026-09).
"""
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


async def cmd_calendrier(update, ctx) -> None:
    """
    /calendrier — Calendrier cultural d'une culture et zone climatique du potager (US-068).

    Sous-commandes :
      <culture> [itinéraire]                               — consulter (zéro jeton)
      zone [oceanique|continental|mediterraneen|montagnard|auto]
                                                           — lire ou choisir la zone (CA7)
      fenetre <culture> [itinéraire] <pepiniere|pleine_terre|plantation|recolte> <mars-mai|aucune>
      duree <culture> [itinéraire] <levee|recolte|repiquage|plantation-recolte> <jours|70-90|mention|aucune>
                                                           — corriger (CA10)

    Aucune logique métier ici : lecture, validation et écriture vivent dans
    `app.services.calendrier_cultural`. Une correction est TOUJOURS propre au
    potager courant (CA11) et confirme l'ancienne et la nouvelle valeur (CA10).
    """
    USAGE = (
        "*Usage :*\n"
        "  /calendrier <culture>\n"
        "  /calendrier zone [océanique|continental|méditerranéen|montagnard|auto]\n"
        "  /calendrier fenetre <culture> [itinéraire] <pepiniere|pleine\\_terre|plantation|recolte> <mois-mois|aucune>\n"
        "  /calendrier duree <culture> [itinéraire] <levee|recolte|repiquage|plantation-recolte> <jours|aucune>\n\n"
        "Exemples :\n"
        "  /calendrier tomate\n"
        "  /calendrier zone méditerranéen\n"
        "  /calendrier fenetre tomate pepiniere février-avril\n"
        "  /calendrier fenetre tomate plantation mai-juin\n"
        "  /calendrier fenetre chou-fleur culture d'hiver recolte novembre-février\n"
        "  /calendrier duree courgette recolte 50-60\n"
        "  /calendrier duree tomate plantation-recolte 60-80\n\n"
        "_Vos corrections ne valent que pour votre potager._"
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
        await update.message.reply_text(
            _formater_calendrier(calendrier, cible), parse_mode="Markdown"
        )
    except Exception as e:
        log.error(f"[US-068] cmd_calendrier erreur : {e}")
        await update.message.reply_text(f"❌ Erreur : {e}")
    finally:
        db.close()

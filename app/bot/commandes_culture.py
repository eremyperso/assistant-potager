"""Commandes /culture, /association, /bioagresseur, /rotation, /fiche.

Module extrait de l'ancien bot.py monolithique (découpage 2026-09).
"""
from database.db import SessionLocal
from utils.parcelles import resolve_parcelle
from app.services.context import current_context
from app.services import familles as svc_familles
from app.services import attributs_culture as svc_attributs
from app.services import fiche_culture as svc_fiche_culture
from app.services import associations as svc_associations
from app.services import rotation as svc_rotation
from app.services import bioagresseurs as svc_bioagresseurs
from .noyau import _md, log
from .liaison import _refuser_si_role_insuffisant


# ──────────────────────────────────────────────────────────────────────────────
# [US-067 / CA4, CA12, CA14] Commande /culture — famille botanique + délai de retour
# [US-161 / CA4, CA5] Attributs agronomiques de conduite : lecture et correction
# ──────────────────────────────────────────────────────────────────────────────
async def cmd_culture(update, ctx) -> None:
    """
    /culture <sous-commande> — Famille botanique, délai de retour, attributs de conduite.

    Sous-commandes :
      famille <culture> <famille>       — corriger/renseigner la famille d'une culture (US-067/CA4)
      delai_retour <famille> <années>   — corriger le délai de retour d'une famille (US-067/CA14)
      attributs <culture>               — lire les attributs agronomiques (US-161/CA4)
      exposition|eau|profondeur|rusticite <culture> <valeur>
                                        — corriger un attribut agronomique (US-161/CA5)

    Aucune logique métier ici (convention projet) : la validation du vocabulaire
    fermé et l'écriture vivent dans `app.services.attributs_culture`, seul point
    d'écriture, partagé avec l'import du référentiel structuré.
    """
    USAGE = (
        "*Usage :*\n"
        "  /culture famille <culture> <famille>\n"
        "  /culture delai_retour <famille> <années>\n"
        "  /culture attributs <culture>\n"
        "  /culture exposition <culture> <plein soleil|mi-ombre|ombre>\n"
        "  /culture eau <culture> <faible|moyen|élevé>\n"
        "  /culture profondeur <culture> <cm>\n"
        "  /culture rusticite <culture> <°C>\n\n"
        "Exemples :\n"
        "  /culture famille pâtisson Cucurbitacée\n"
        "  /culture delai_retour Solanacée 4\n"
        "  /culture attributs carotte\n"
        "  /culture exposition courgette plein soleil\n"
        "  /culture profondeur carotte 1"
    )

    if not ctx.args:
        await update.message.reply_text(USAGE, parse_mode="Markdown")
        return

    sous_cmd = ctx.args[0].lower()

    # ── /culture famille <culture> <famille> ──────────────────────────────────
    if sous_cmd == "famille":
        if await _refuser_si_role_insuffisant(update, "corriger une famille botanique"):
            return
        if len(ctx.args) < 3:
            await update.message.reply_text(
                "❌ Usage : /culture famille <culture> <famille>\n"
                "Exemple : /culture famille pâtisson Cucurbitacée",
                parse_mode="Markdown",
            )
            return
        culture = ctx.args[1].strip()
        famille_nom = " ".join(ctx.args[2:]).strip()
        db = SessionLocal()
        try:
            fiches, ancienne = svc_familles.corriger_famille_culture(db, culture, famille_nom)
            avant = _md(ancienne) if ancienne else "Autres"
            log.info(
                f"[US-067] Famille corrigée : '{culture}' : '{ancienne or 'Autres'}' → "
                f"'{fiches[0].famille_rel.nom}' ({len(fiches)} fiche(s))"
            )
            await update.message.reply_text(
                f"✅ Famille de *{_md(culture)}* : *{avant}* → *{_md(fiches[0].famille_rel.nom)}*",
                parse_mode="Markdown",
            )
        except LookupError:
            await update.message.reply_text(
                f"❌ Culture inconnue : *{_md(culture)}*\n"
                "Elle doit avoir déjà été dictée au moins une fois.",
                parse_mode="Markdown",
            )
        except Exception as e:
            log.error(f"[US-067] cmd_culture famille erreur : {e}")
            await update.message.reply_text(f"❌ Erreur : {e}")
        finally:
            db.close()
        return

    # ── /culture delai_retour <famille> <années> ──────────────────────────────
    if sous_cmd in ("delai_retour", "delai"):
        if await _refuser_si_role_insuffisant(update, "corriger un délai de retour"):
            return
        if len(ctx.args) < 3:
            await update.message.reply_text(
                "❌ Usage : /culture delai_retour <famille> <années>\n"
                "Exemple : /culture delai_retour Solanacée 4",
                parse_mode="Markdown",
            )
            return
        *famille_tokens, annees_brut = ctx.args[1:]
        famille_nom = " ".join(famille_tokens).strip()
        try:
            annees = int(annees_brut)
            if annees < 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                f"❌ Le délai de retour doit être un nombre entier positif d'années "
                f"(reçu : *{_md(annees_brut)}*)",
                parse_mode="Markdown",
            )
            return
        db = SessionLocal()
        try:
            famille, ancien = svc_familles.corriger_delai_retour(db, famille_nom, annees)
            avant = f"{ancien} ans" if ancien is not None else "non renseigné"
            log.info(f"[US-067] Délai de retour corrigé : '{famille.nom}' : {avant} → {annees} ans")
            await update.message.reply_text(
                f"✅ Délai de retour de *{_md(famille.nom)}* : {avant} → *{annees} ans*",
                parse_mode="Markdown",
            )
        except LookupError:
            await update.message.reply_text(
                f"❌ Famille inconnue : *{_md(famille_nom)}*",
                parse_mode="Markdown",
            )
        except Exception as e:
            log.error(f"[US-067] cmd_culture delai_retour erreur : {e}")
            await update.message.reply_text(f"❌ Erreur : {e}")
        finally:
            db.close()
        return

    # ── /culture attributs <culture> ──────────────────────────────────────────
    # [US-161 / CA4] Lecture pure : des colonnes et leur origine, zéro jeton, et
    # « non renseigné » dit tel quel — jamais une valeur devinée ni moyennée.
    if sous_cmd in ("attributs", "attribut", "fiche"):
        if len(ctx.args) < 2:
            await update.message.reply_text(
                "❌ Usage : /culture attributs <culture>\n"
                "Exemple : /culture attributs carotte",
                parse_mode="Markdown",
            )
            return
        culture = " ".join(ctx.args[1:]).strip()
        db = SessionLocal()
        try:
            lus = svc_attributs.lire_attributs(db, culture)
            lignes = [f"🌱 *{_md(culture)}* — attributs agronomiques"]
            for attribut in lus:
                # Une valeur absente se lit en clair (CA4) : la mettre en gras
                # comme une vraie valeur donnerait à « non renseigné » le poids
                # d'une réponse.
                valeur = (
                    f"*{_md(attribut.affichage)}*" if attribut.renseigne
                    else attribut.affichage
                )
                lignes.append(f"• {attribut.libelle} : {valeur}")

            # [US-166 / CA1] L'attribution, pas le code technique : `wind_river_greens`
            # ne dit rien au jardinier, et CC BY oblige à créditer la source AVEC la
            # réponse, pas dans un README. Une mention par source, dédupliquée, en
            # texte brut — Telegram parse mal les underscores d'un identifiant.
            attributions = []
            for attribut in lus:
                if attribut.attribution and attribut.attribution not in attributions:
                    attributions.append(attribut.attribution)
            if attributions:
                lignes.append("")
                lignes.append("Source : " + " · ".join(attributions))

            await update.message.reply_text("\n".join(lignes), parse_mode="Markdown")
        except LookupError:
            await update.message.reply_text(
                f"❌ Culture inconnue : *{_md(culture)}*\n"
                "Elle doit avoir déjà été dictée au moins une fois.",
                parse_mode="Markdown",
            )
        except Exception as e:
            log.error(f"[US-161] cmd_culture attributs erreur : {e}")
            await update.message.reply_text(f"❌ Erreur : {e}")
        finally:
            db.close()
        return

    # ── /culture <attribut> <culture> <valeur> ────────────────────────────────
    # [US-161 / CA5] Correction depuis le bot, sans livraison ni intervention en
    # base — exactement comme la famille botanique. La réponse confirme
    # l'ancienne ET la nouvelle valeur.
    try:
        cle_attribut = svc_attributs.resoudre_cle(sous_cmd)
    except KeyError:
        cle_attribut = None

    if cle_attribut is not None:
        if await _refuser_si_role_insuffisant(update, "corriger un attribut de culture"):
            return
        attribut = svc_attributs.ATTRIBUTS_PAR_CLE[cle_attribut]
        if len(ctx.args) < 3:
            admis = (
                " | ".join(attribut.vocabulaire) if attribut.est_qualitatif
                else f"un nombre en {attribut.unite}"
            )
            await update.message.reply_text(
                f"❌ Usage : /culture {sous_cmd} <culture> <valeur>\n"
                f"Valeurs admises : {admis}",
                parse_mode="Markdown",
            )
            return
        culture = ctx.args[1].strip()
        valeur = " ".join(ctx.args[2:]).strip()
        db = SessionLocal()
        try:
            fiches, avant, apres = svc_attributs.corriger_attribut(
                db, culture, cle_attribut, valeur
            )
            log.info(
                f"[US-161] {attribut.libelle} corrigée : '{culture}' : "
                f"'{avant}' → '{apres}' ({len(fiches)} fiche(s))"
            )
            await update.message.reply_text(
                f"✅ {attribut.libelle} de *{_md(culture)}* : "
                f"*{_md(avant)}* → *{_md(apres)}*",
                parse_mode="Markdown",
            )
        except svc_attributs.ValeurHorsVocabulaireError as err:
            # [CA2] L'attribut conserve sa valeur précédente : rien n'a été écrit.
            await update.message.reply_text(
                f"❌ {_md(str(err))}\nL'attribut conserve sa valeur précédente.",
                parse_mode="Markdown",
            )
        except LookupError:
            await update.message.reply_text(
                f"❌ Culture inconnue : *{_md(culture)}*\n"
                "Elle doit avoir déjà été dictée au moins une fois.",
                parse_mode="Markdown",
            )
        except Exception as e:
            log.error(f"[US-161] cmd_culture {sous_cmd} erreur : {e}")
            await update.message.reply_text(f"❌ Erreur : {e}")
        finally:
            db.close()
        return

    # Sous-commande inconnue
    await update.message.reply_text(USAGE, parse_mode="Markdown")


# ──────────────────────────────────────────────────────────────────────────────
# [US-163 / CA1-CA5, CA10] Commande /association — associations de cultures
# ──────────────────────────────────────────────────────────────────────────────
async def cmd_association(update, ctx) -> None:
    """
    /association <sous-commande> — Associations favorables/défavorables/neutres
    entre cultures ou familles botaniques (US-163).

    Sous-commandes :
      lister <culture>                                            — associations connues (CA4, CA5)
      saisir <cultureA> <cultureB> <nature> <preuve> <motif>       — saisir/corriger (CA1, CA2, CA10)

    Aucune logique métier ici (convention projet) : la résolution des entités,
    la validation du vocabulaire fermé et l'écriture vivent dans
    `app.services.associations`, seul point d'écriture.
    """
    USAGE = (
        "*Usage :*\n"
        "  /association lister <culture>\n"
        "  /association saisir <cultureA> <cultureB> <favorable|defavorable|neutre> "
        "<etabli|traditionnel> <motif>\n\n"
        "Exemples :\n"
        "  /association lister carotte\n"
        "  /association saisir carotte aneth defavorable etabli concurrence racinaire\n"
        "  /association saisir tomate basilic favorable traditionnel repousse les pucerons"
    )

    if not ctx.args:
        await update.message.reply_text(USAGE, parse_mode="Markdown")
        return

    sous_cmd = ctx.args[0].lower()

    # ── /association lister <culture> ─────────────────────────────────────────
    if sous_cmd in ("lister", "liste", "voir"):
        if len(ctx.args) < 2:
            await update.message.reply_text(
                "❌ Usage : /association lister <culture>\n"
                "Exemple : /association lister carotte",
                parse_mode="Markdown",
            )
            return
        culture = " ".join(ctx.args[1:]).strip()
        db = SessionLocal()
        try:
            associations = svc_associations.lire_associations(db, culture)
            if not associations:
                await update.message.reply_text(
                    f"ℹ️ Aucune association connue pour *{_md(culture)}*.",
                    parse_mode="Markdown",
                )
                return
            lignes = [f"🌿 *{_md(culture)}* — associations connues"]
            attributions: list[str] = []
            for a in associations:
                cible = f"la famille {a.autre_partie}" if a.autre_est_famille else a.autre_partie
                lignes.append(f"• {_md(cible)} : *{_md(a.formulation)}* — {_md(a.motif)}")
                if a.attribution and a.attribution not in attributions:
                    attributions.append(a.attribution)
            if attributions:
                lignes.append("")
                lignes.append("Source : " + " · ".join(attributions))
            await update.message.reply_text("\n".join(lignes), parse_mode="Markdown")
        except svc_associations.EntiteInconnueError:
            await update.message.reply_text(
                f"❌ Culture ou famille inconnue : *{_md(culture)}*",
                parse_mode="Markdown",
            )
        except Exception as e:
            log.error(f"[US-163] cmd_association lister erreur : {e}")
            await update.message.reply_text(f"❌ Erreur : {e}")
        finally:
            db.close()
        return

    # ── /association saisir <cultureA> <cultureB> <nature> <preuve> <motif> ───
    if sous_cmd in ("saisir", "corriger", "ajouter"):
        if await _refuser_si_role_insuffisant(update, "saisir une association"):
            return
        if len(ctx.args) < 6:
            await update.message.reply_text(
                "❌ Usage : /association saisir <cultureA> <cultureB> "
                "<favorable|defavorable|neutre> <etabli|traditionnel> <motif>\n"
                "Exemple : /association saisir carotte aneth defavorable etabli concurrence racinaire",
                parse_mode="Markdown",
            )
            return
        cote_a, cote_b = ctx.args[1], ctx.args[2]
        nature, niveau_preuve = ctx.args[3].lower(), ctx.args[4].lower()
        motif = " ".join(ctx.args[5:]).strip()
        db = SessionLocal()
        try:
            association, creee = svc_associations.enregistrer_association(
                db, cote_a, cote_b, nature, motif, niveau_preuve
            )
            verbe = "saisie" if creee else "corrigée"
            log.info(
                f"[US-163] Association {verbe} : '{cote_a}' ↔ '{cote_b}' : "
                f"{nature}/{niveau_preuve}"
            )
            await update.message.reply_text(
                f"✅ Association {verbe} : *{_md(cote_a)}* ↔ *{_md(cote_b)}* — "
                f"*{_md(svc_associations.formuler_nature(nature, niveau_preuve))}*",
                parse_mode="Markdown",
            )
        except svc_associations.EntiteInconnueError as err:
            await update.message.reply_text(
                f"❌ Culture ou famille inconnue : *{_md(str(err))}*\n"
                "Elle doit déjà exister (culture déjà dictée, ou famille déjà connue).",
                parse_mode="Markdown",
            )
        except svc_associations.ValeurAssociationInvalideError as err:
            await update.message.reply_text(f"❌ {_md(str(err))}", parse_mode="Markdown")
        except Exception as e:
            log.error(f"[US-163] cmd_association saisir erreur : {e}")
            await update.message.reply_text(f"❌ Erreur : {e}")
        finally:
            db.close()
        return

    # Sous-commande inconnue
    await update.message.reply_text(USAGE, parse_mode="Markdown")


# ──────────────────────────────────────────────────────────────────────────────
# [US-163 / CA6-CA9] Commande /rotation — conflit de rotation calculé, à la campagne
# ──────────────────────────────────────────────────────────────────────────────
async def cmd_bioagresseur(update, ctx) -> None:
    """
    /bioagresseur <sous-commande> — Ce qui attaque une culture (US-162).

    Sous-commandes :
      lister <culture>                                  — restitution à ZÉRO jeton (CA2, CA13)
      declarer <categorie> <nom>                        — identité LOCALE au potager (CA1, CA3)
      rattacher <culture> <frequence> <bioagresseur>    — arête locale (CA2, CA3)
      orphelins                                         — identités sans arête connue (CA12)

    Aucune logique métier ici (convention projet) : la résolution, la validation
    du vocabulaire fermé et l'écriture vivent dans `app.services.bioagresseurs`,
    seul point d'écriture — le même que traverse l'import de manifeste.

    [CA3] Toute saisie faite ici est LOCALE au potager courant. Rien dans ce
    chemin ne promeut une saisie au partagé : c'est une décision humaine, prise
    ailleurs.

    [CA10] Aucun dosage ni recommandation d'emploi n'est restitué — il n'existe
    aucune colonne où en stocker. Ce que l'application peut dire d'un traitement
    se lit à la source officielle, qui est citée.
    """
    USAGE = (
        "*Usage :*\n"
        "  /bioagresseur lister <culture>\n"
        "  /bioagresseur declarer <champignon|insecte|mollusque|nematode|bacterie|virus|abiotique|carence> <nom>\n"
        "  /bioagresseur rattacher <culture> <courant|occasionnel|rare> <bioagresseur>\n"
        "  /bioagresseur orphelins\n\n"
        "Exemples :\n"
        "  /bioagresseur lister poireau\n"
        "  /bioagresseur declarer insecte teigne du poireau\n"
        "  /bioagresseur rattacher poireau courant teigne du poireau"
    )

    if not ctx.args:
        await update.message.reply_text(USAGE, parse_mode="Markdown")
        return

    sous_cmd = ctx.args[0].lower()
    tenant_ctx = current_context()
    db = SessionLocal()
    try:
        # ── /bioagresseur lister <culture> ────────────────────────────────────
        if sous_cmd in ("lister", "liste", "voir"):
            if len(ctx.args) < 2:
                await update.message.reply_text(
                    "❌ Usage : /bioagresseur lister <culture>\n"
                    "Exemple : /bioagresseur lister poireau",
                    parse_mode="Markdown",
                )
                return
            culture = " ".join(ctx.args[1:]).strip()
            try:
                trouves = svc_bioagresseurs.lire_bioagresseurs(
                    db, culture, potager_id=tenant_ctx.potager_id
                )
            except svc_bioagresseurs.CultureInconnueError:
                await update.message.reply_text(
                    f"❌ Culture inconnue : *{_md(culture)}*", parse_mode="Markdown"
                )
                return

            log.info(
                f"[US-162] /bioagresseur lister '{culture}' : {len(trouves)} résultat(s), 0 jeton"
            )
            if not trouves:
                # [CA12] Ne jamais laisser lire « rien ne l'attaque ».
                await update.message.reply_text(
                    f"ℹ️ *{_md(culture)}* — {_md(svc_bioagresseurs.MESSAGE_AUCUNE_INFO)}",
                    parse_mode="Markdown",
                )
                return

            lignes = [f"🐛 *{_md(culture)}* — ce qui l'attaque"]
            attributions: list[str] = []
            for b in trouves:
                details = [b.frequence]
                if b.periode_risque:
                    details.append(b.periode_risque)
                else:
                    details.append("période non renseignée")
                details.append(b.categorie)
                if b.local:
                    details.append("propre à votre potager")
                ligne = f"• *{_md(b.nom_commun_fr)}* — {_md(' · '.join(details))}"
                if b.nom_scientifique:
                    ligne += f"\n  _{_md(b.nom_scientifique)}_"
                lignes.append(ligne)
                if b.attribution and b.attribution not in attributions:
                    attributions.append(b.attribution)
            if attributions:
                lignes.append("")
                lignes.append("Source : " + " · ".join(attributions))
            await update.message.reply_text("\n".join(lignes), parse_mode="Markdown")
            return

        # ── /bioagresseur declarer <categorie> <nom> ──────────────────────────
        if sous_cmd in ("declarer", "déclarer", "ajouter"):
            if await _refuser_si_role_insuffisant(update, "déclarer un bioagresseur"):
                return
            if len(ctx.args) < 3:
                await update.message.reply_text(
                    "❌ Usage : /bioagresseur declarer "
                    "<champignon|insecte|mollusque|nematode|bacterie|virus|abiotique|carence> <nom>\n"
                    "Exemple : /bioagresseur declarer insecte teigne du poireau",
                    parse_mode="Markdown",
                )
                return
            categorie = ctx.args[1].lower()
            nom = " ".join(ctx.args[2:]).strip()
            try:
                _, cree = svc_bioagresseurs.enregistrer_bioagresseur(
                    db, nom_commun_fr=nom, categorie=categorie,
                    potager_id=tenant_ctx.potager_id,
                )
            except svc_bioagresseurs.ValeurBioagresseurInvalideError as err:
                await update.message.reply_text(f"❌ {err}")
                return
            verbe = "déclaré" if cree else "corrigé"
            await update.message.reply_text(
                f"✅ *{_md(nom)}* {verbe} ({_md(categorie)}) — pour votre potager uniquement.\n"
                f"Rattachez-le à une culture : /bioagresseur rattacher <culture> "
                f"<courant|occasionnel|rare> {_md(nom)}",
                parse_mode="Markdown",
            )
            return

        # ── /bioagresseur rattacher <culture> <frequence> <bioagresseur> ──────
        if sous_cmd in ("rattacher", "relier"):
            if await _refuser_si_role_insuffisant(update, "rattacher un bioagresseur"):
                return
            if len(ctx.args) < 4:
                await update.message.reply_text(
                    "❌ Usage : /bioagresseur rattacher <culture> "
                    "<courant|occasionnel|rare> <bioagresseur>\n"
                    "Exemple : /bioagresseur rattacher poireau courant teigne du poireau",
                    parse_mode="Markdown",
                )
                return
            culture, frequence = ctx.args[1], ctx.args[2].lower()
            nom = " ".join(ctx.args[3:]).strip()
            try:
                _, cree = svc_bioagresseurs.rattacher(
                    db, culture=culture, bioagresseur=nom, frequence=frequence,
                    potager_id=tenant_ctx.potager_id,
                )
            except svc_bioagresseurs.ValeurBioagresseurInvalideError as err:
                await update.message.reply_text(f"❌ {err}")
                return
            except svc_bioagresseurs.CultureInconnueError:
                await update.message.reply_text(
                    f"❌ Culture inconnue : *{_md(culture)}*", parse_mode="Markdown"
                )
                return
            except svc_bioagresseurs.BioagresseurInconnuError:
                await update.message.reply_text(
                    f"❌ Bioagresseur inconnu : *{_md(nom)}*\n"
                    f"Déclarez-le d'abord : /bioagresseur declarer <categorie> {_md(nom)}",
                    parse_mode="Markdown",
                )
                return
            verbe = "rattaché" if cree else "mis à jour"
            await update.message.reply_text(
                f"✅ *{_md(nom)}* {verbe} à *{_md(culture)}* ({_md(frequence)}).",
                parse_mode="Markdown",
            )
            return

        # ── /bioagresseur orphelins ───────────────────────────────────────────
        if sous_cmd in ("orphelins", "orphelin", "nonrattaches"):
            orphelins = svc_bioagresseurs.lister_non_rattaches(
                db, potager_id=tenant_ctx.potager_id
            )
            if not orphelins:
                await update.message.reply_text(
                    "✅ Tous les bioagresseurs connus sont rattachés à au moins une culture."
                )
                return
            # [CA12] Ils restent en base et se lisent comme non rattachés — ni
            # supprimés, ni comptés comme couverture.
            lignes = [f"🔎 *{len(orphelins)}* bioagresseur(s) connu(s) mais rattaché(s) à aucune culture"]
            lignes += [f"• {_md(b.nom_commun_fr)} ({_md(b.categorie)})" for b in orphelins]
            await update.message.reply_text("\n".join(lignes), parse_mode="Markdown")
            return

        await update.message.reply_text(USAGE, parse_mode="Markdown")
    except Exception as e:
        log.error(f"[US-162] cmd_bioagresseur erreur : {e}")
        await update.message.reply_text(f"❌ Erreur : {e}")
    finally:
        db.close()


async def cmd_rotation(update, ctx) -> None:
    """
    /rotation <parcelle> <culture> — Un conflit de rotation se calcule, il ne se
    rédige pas (CA6). Consultation à la demande ; l'alerte automatique déclenchée
    à la plantation est le périmètre d'US-167, qui réutilise
    `app.services.rotation.evaluer_rotation` sans le réécrire.
    """
    if len(ctx.args) < 2:
        await update.message.reply_text(
            "*Usage :* /rotation <parcelle> <culture>\nExemple : /rotation NORD poivron",
            parse_mode="Markdown",
        )
        return

    nom_parcelle = ctx.args[0]
    culture = " ".join(ctx.args[1:]).strip()
    tenant_ctx = current_context()
    db = SessionLocal()
    try:
        parcelle = resolve_parcelle(db, nom_parcelle, potager_id=tenant_ctx.potager_id)
        if parcelle is None:
            await update.message.reply_text(
                f"❌ Parcelle inconnue : *{_md(nom_parcelle)}*", parse_mode="Markdown"
            )
            return
        evaluation = svc_rotation.evaluer_rotation(db, tenant_ctx, parcelle.id, culture)
        prefixe = {
            svc_rotation.STATUT_CONFLIT: "⚠️",
            svc_rotation.STATUT_OK: "✅",
        }.get(evaluation.statut, "ℹ️")
        log.info(
            f"[US-163] /rotation '{culture}' sur '{parcelle.nom}' : statut={evaluation.statut}"
        )
        await update.message.reply_text(f"{prefixe} {evaluation.message}")
    except Exception as e:
        log.error(f"[US-163] cmd_rotation erreur : {e}")
        await update.message.reply_text(f"❌ Erreur : {e}")
    finally:
        db.close()


# ──────────────────────────────────────────────────────────────────────────────
# [US-164 / CA1-CA11, CA13] Commande /fiche — fiche courte, générée, sans aucun jeton
# ──────────────────────────────────────────────────────────────────────────────
async def cmd_fiche(update, ctx) -> None:
    """
    /fiche <culture> — Fiche courte au bot, sur commande uniquement.

    [CA1] Commande préfixée, reconnue au tout premier étage du routage
    (CommandHandler) : zéro jeton, zéro appel réseau, zéro effet de bord.
    [CA4] N'introduit AUCUNE restitution spontanée : c'est le seul chemin vers
    la fiche, aucun autre flux (notamment `handle_text`) n'y touche.
    [CA3] Aucune logique métier ici (convention projet) : le gabarit est
    assemblé par `app.services.fiche_culture`, seul point de lecture.
    """
    if not ctx.args:
        await update.message.reply_text(
            "❌ Usage : /fiche <culture>\nExemple : /fiche tomate",
            parse_mode="Markdown",
        )
        return

    culture = " ".join(ctx.args).strip()
    tenant_ctx = current_context()
    db = SessionLocal()
    try:
        # [US-174 / CA6] Le potager courant est passé pour que les bioagresseurs
        # déclarés localement par un jardinier ne fuient pas vers un autre
        # potager. Il ne scope QUE cette rubrique (CA7).
        fiche = svc_fiche_culture.generer_fiche_courte(
            db, culture, potager_id=tenant_ctx.potager_id
        )

        lignes = [f"🌱 *{_md(fiche.culture)}*"]
        # [CA6] Famille non renseignée : dite telle quelle, jamais omise ni devinée.
        if fiche.famille:
            lignes.append(f"Famille : *{_md(fiche.famille)}*")
            if fiche.delai_retour_annees is not None:
                lignes.append(f"Délai de retour : *{fiche.delai_retour_annees} ans*")
        else:
            lignes.append("Famille : non renseignée")

        for attribut in fiche.attributs:
            # [CA6] Une valeur absente se lit en clair, jamais mise en gras
            # comme une vraie valeur — même convention que /culture attributs.
            valeur = (
                f"*{_md(attribut.affichage)}*" if attribut.renseigne
                else attribut.affichage
            )
            lignes.append(f"• {attribut.libelle} : {valeur}")

        # ── [US-174 / CA1-CA5] Ce qui attaque la culture ──────────────────
        # Placée avant la description : un jardinier qui ouvre la fiche d'une
        # culture attaquée cherche cela, pas un champ de texte libre.
        lignes.append("")
        if fiche.bioagresseurs_connus:
            lignes.append("*À surveiller :*")
            for b in fiche.bioagresseurs:
                # [CA2] La période n'apparaît que si elle est renseignée —
                # répéter « non renseignée » cinq fois noierait la rubrique.
                details = [b.frequence]
                if b.periode_risque:
                    details.append(b.periode_risque)
                # [CA3] Le local se distingue du partagé, comme dans
                # /bioagresseur lister.
                if b.local:
                    details.append("votre potager")
                lignes.append(f"• {_md(b.nom_commun_fr)} — {_md(' · '.join(details))}")
            # [CA4] La fiche courte reste courte : ce qui déborde est compté, et
            # la commande qui montre tout est rappelée.
            if fiche.bioagresseurs_non_affiches:
                lignes.append(
                    f"_+ {fiche.bioagresseurs_non_affiches} autre(s) — "
                    f"/bioagresseur lister {_md(fiche.culture)}_"
                )
        else:
            # [CA5] Aucune arête connue : jamais une rubrique vide, jamais
            # « rien ne l'attaque » — l'ignorance se dit (US-162 / CA12).
            lignes.append(
                "*À surveiller :* information non connue — cela ne veut pas dire "
                "que cette culture n'est pas exposée."
            )

        # [CA13] Champ de texte libre : affiché quand renseigné, jamais omis ni
        # comblé sinon — même principe d'honnêteté que CA6, appliqué à ce champ.
        if fiche.description_agronomique:
            lignes.append(f"Description : *{_md(fiche.description_agronomique)}*")
        else:
            lignes.append("Description : incomplète")

        # [CA7 / US-166] L'attribution, pas le code technique de la source —
        # une mention par source, dédupliquée, en texte brut.
        if fiche.attributions:
            lignes.append("")
            lignes.append("Source : " + " · ".join(fiche.attributions))

        log.info(f"[US-164] Fiche courte servie : '{culture}' (0 jeton, 0 appel modèle)")
        await update.message.reply_text("\n".join(lignes), parse_mode="Markdown")
    except LookupError:
        # [CA5] Honnêteté : jamais une fiche voisine forcée ni une réponse générée.
        await update.message.reply_text(
            f"🤷 Je n'ai pas de fiche sur cette culture : *{_md(culture)}*.",
            parse_mode="Markdown",
        )
    except Exception as e:
        log.error(f"[US-164] cmd_fiche erreur : {e}")
        await update.message.reply_text(f"❌ Erreur : {e}")
    finally:
        db.close()

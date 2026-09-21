"""Points d'entrée des messages libres : handle_voice et handle_text.

Module extrait de l'ancien bot.py monolithique (découpage 2026-09).
"""
import os
import re
import tempfile
from telegram import Update
from telegram.ext import ContextTypes
from database.db import SessionLocal
from utils.parcelles import create_parcelle
from llm.groq_client import parse_message
from llm import passerelle
from llm import routeur
from llm.parseur_deterministe import parser_saisie
from llm.passerelle import LLMIndisponibleError, MESSAGE_REPLI_IA
from utils.deplacer import is_deplacer_request as _is_deplacer_request, extract_culture_deplacer as _extract_culture_deplacer
from utils.notes import is_note_request as _is_note_request
from app.services.context import current_context
from app.services import interpreteur_commandes as svc_interpreteur
from .noyau import MENU_KEYBOARD, log
from .etat import _GODET_GRAINES_PENDING, _QUANTITE_PENDING, _RECOLTE_PIECES_PENDING
from .liaison import _delier_confirm, _verifier_liaison_ou_onboarding, cmd_start
from .enregistrement import _parse_multi
from .godets import _godet_graines_reponse
from .notes import _note_category_selected, _note_details_received, _note_start
from .interpretation import _INTERP_MODE_COMPLETION, _interp_completion_texte, _traiter_commande_interpretee
from .questions import (
    NAV_CORRIGER,
    NAV_HISTORIQUE,
    NAV_INTERROGER,
    NAV_MENU,
    NAV_NOTE,
    NAV_NOUVELLE,
    NAV_STATS,
    NAV_SUPPRIMER,
    _ask_question,
    _consulter_godets,
    _is_requete_godets,
)
from .saisie import _parse_and_save
from .correction import (
    _corr_annuler_dernier,
    _corr_apply,
    _corr_confirm,
    _corr_confirm_delete,
    _corr_search,
    _corr_select,
    _corr_start,
)
from .deplacement import (
    MODES_DEPLACER,
    _depl_confirm,
    _depl_parcelle_select,
    _depl_start,
    _depl_variete_select,
)
from .commandes_plan import cmd_plan
from .commandes_stats import cmd_historique, cmd_stats


async def handle_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Message vocal → transcription Groq Whisper → parsing → PostgreSQL."""
    # [US-045 / CA6, CA7] Priorité 0 — aucun appel Groq (Whisper) tant que le
    # chat n'est pas lié à un compte. Pas de code déductible d'un vocal : on
    # ne tente jamais la transcription pour un chat non lié.
    if not await _verifier_liaison_ou_onboarding(update, ctx):
        return

    msg = await update.message.reply_text("🎤 *Transcription en cours...*", parse_mode="Markdown")

    # ── 1. Télécharger le fichier audio ────────────────────────────────────────
    voice_file = await update.message.voice.get_file()

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp_path = tmp.name
        await voice_file.download_to_drive(tmp_path)

    # ── 2. Transcrire via la passerelle LLM [US-092 / CA4] ─────────────────────
    try:
        texte = passerelle.transcrire(
            ctx=current_context(),
            chemin_fichier=tmp_path,
            nom_fichier="message.ogg",
        ).texte
        os.unlink(tmp_path)
    except LLMIndisponibleError:
        # [CA9] Pas de repli utile pour un vocal : sans transcription il n'y a
        # rien à enregistrer. Message explicite, et invitation à passer au
        # clavier — le reste du bot (déterministe) fonctionne toujours.
        os.unlink(tmp_path)
        await msg.edit_text(
            f"⏳ {MESSAGE_REPLI_IA}.\n\n"
            "En attendant, tape ton action ou ta question au clavier : "
            "/stats, /plan, /historique et le stock restent disponibles."
        )
        return
    except Exception as e:
        os.unlink(tmp_path)
        await msg.edit_text(f"❌ Erreur transcription : {e}")
        return

    if not texte:
        await msg.edit_text("❌ Je n'ai pas compris. Réessayez en parlant plus distinctement.")
        return

    log.info(f"🎤 TRANSCRIPTION  : {texte}")

    await msg.edit_text(f"🗣 _\"{texte}\"_\n\n⏳ Analyse en cours...", parse_mode="Markdown")

    # ── 2b. [US-066 / CA6] Nombre de graines d'origine en attente ? ────────────
    # Le flux doit fonctionner à la voix comme au clavier : la transcription est
    # ici une réponse à une question déjà posée, jamais une nouvelle action à
    # classifier. (Les autres flux en attente — _QUANTITE_PENDING,
    # _RECOLTE_PIECES_PENDING — ne sont interceptés que dans handle_text : limite
    # existante, hors périmètre d'US-066.)
    if update.effective_user.id in _GODET_GRAINES_PENDING:
        await msg.delete()
        await _godet_graines_reponse(update, texte)
        return

    # ── 3. Modes correction actifs : bypass intent classification ──────────────
    # Quand on est en pleine conversation de correction, on ne reclassifie pas —
    # le texte est une réponse dans un flux déjà engagé.
    mode = ctx.user_data.get('mode')
    MODES_CORR = {'corr_search','corr_select','corr_apply','corr_confirm','corr_confirm_delete'}
    if mode in MODES_CORR:
        if mode == 'corr_search':
            await _corr_search(update, ctx, texte)
        elif mode == 'corr_select':
            await _corr_select(update, ctx, texte)
        elif mode == 'corr_apply':
            await msg.delete()
            await _corr_apply(update, ctx, texte)
        elif mode == 'corr_confirm':
            await _corr_confirm(update, ctx, texte)
        elif mode == 'corr_confirm_delete':
            await _corr_confirm_delete(update, ctx, texte)
        return

    # ── 3b. [US-007] Modes déplacement actifs : bypass intent classification ────
    if mode in MODES_DEPLACER:
        if mode == 'depl_culture_ask':
            culture = _extract_culture_deplacer(texte) or texte.strip().lower()
            ctx.user_data.pop('mode', None)
            await _depl_start(update, ctx, culture)
        elif mode == 'depl_variete_select':
            await _depl_variete_select(update, ctx, texte)
        elif mode == 'depl_parcelle_select':
            await _depl_parcelle_select(update, ctx, texte)
        elif mode == 'depl_confirm':
            await _depl_confirm(update, ctx, texte)
        return

    # ── 3c. [US-038] Flux note guidée actif : bypass intent classification ─────
    if mode in ('note_category', 'note_details'):
        if mode == 'note_category':
            await _note_category_selected(update, ctx, texte)
        elif mode == 'note_details':
            await _note_details_received(update, ctx, texte)
        return

    # ── 4. Mode ask actif : bypass aussi ──────────────────────────────────────
    if mode == 'ask':
        ctx.user_data['mode'] = None
        await _ask_question(update, texte)
        return

    # ── 4bis. [US-172 / CA5] La dictée ne change rien : l'interpréteur voit la
    # transcription au même point du flux que `handle_text` voit la frappe —
    # après toutes les gardes de conversation ci-dessus, avant le parsing de
    # geste. Sans cela, « supprime la parcelle nord » dicté serait parti au
    # parseur d'événement, qui n'a aucune façon d'en faire quoi que ce soit.
    resultat_commande = svc_interpreteur.interpreter(texte, current_context())
    if await _traiter_commande_interpretee(update, ctx, resultat_commande, msg=msg):
        return

    # ── 5. [US-094 / CA1] Étage 0 — la grammaire déterministe d'abord ────────
    # Une forme qu'elle reconnaît est une saisie par construction : elle porte
    # un geste en tête, une culture connue du potager et rien d'inexpliqué.
    # Aucune classification n'est donc à payer, et le mode dégradé 429 laisse
    # cette voie entièrement ouverte (CA12). Placé ici, après toutes les gardes
    # de conversation ci-dessus, l'ordre critique des flux reste intact.
    resultat_deterministe = parser_saisie(texte, current_context())
    if resultat_deterministe.reconnu:
        await _parse_and_save(update, texte, msg, pre_parsed_items=resultat_deterministe.items)
        return

    # ── 5bis. [US-172] Une QUESTION dictée n'est pas un ordre ────────────────
    # `handle_text` demande sa nature au routeur depuis US-170 ; ce canal-ci
    # était resté sur les seuls intents de `parse_message`, qui ne connaissent
    # ni le socle de connaissance, ni la mémoire du potager. Une question dictée
    # n'atteignait donc la cascade que si le modèle la classait INTERROGER —
    # et « comment supprimer une parcelle ? » était lue comme l'intent
    # SUPPRIMER, le bot proposant d'effacer le dernier geste enregistré au lieu
    # d'expliquer la procédure. Constaté en dictée réelle le 08/09/2026, et en
    # contradiction directe avec le CA2 : la même phrase TAPÉE recevait bien
    # l'explication du socle.
    #
    # Seul l'étage des RÈGLES est consulté (`classer_par_regles`), et c'est
    # délibéré : `classer_demande` paierait un appel de classification sur tout
    # ce que les règles ne tranchent pas, alors que `parse_message` ci-dessous
    # classe et parse déjà en un seul appel. Une règle qui tranche évite
    # l'erreur, une règle qui se tait laisse la main — « supprime ma dernière
    # saisie », qu'aucune règle ne reconnaît, continue donc d'atteindre son
    # intent SUPPRIMER et d'annuler le dernier geste, comme avant.
    #
    # Placé APRÈS la grammaire déterministe : ce qu'elle reconnaît est une
    # saisie par construction, et n'a pas à être classé.
    nature_reglee = routeur.classer_par_regles(texte)
    if nature_reglee is not None and nature_reglee != routeur.NATURE_ACTION:
        log.info(f"❓ QUESTION VOCALE : nature={nature_reglee} → _ask_question")
        await msg.edit_text("🔍 *Analyse en cours...*", parse_mode="Markdown")
        await _ask_question(update, texte)
        return

    # ── 5ter. Analyse unifiée intent + parsing via la passerelle (single-pass) ──
    try:
        parsed = parse_message(texte, ctx=current_context())
    except LLMIndisponibleError:
        # [US-092 / CA9, CA10] Repli déclaré : le routage par le modèle est
        # indisponible, mais tout le bot déterministe reste accessible — on
        # oriente vers les commandes qui ne consomment aucun appel LLM.
        log.warning("⏳ ROUTAGE         : IA indisponible → orientation commandes déterministes")
        await msg.edit_text(
            f"⏳ {MESSAGE_REPLI_IA}.\n\n"
            "En attendant, ces commandes fonctionnent normalement :\n"
            "/stats · /plan · /historique · /meteo · /parcelles"
        )
        return
    intent = parsed["intent"]

    # ── 6. Routage selon intent ────────────────────────────────────────────────
    if intent == "STATS":
        await msg.edit_text("📊 *Statistiques*", parse_mode="Markdown")
        # culture extraite par le LLM (remplace _extract_stats_culture)
        culture_vocal = parsed.get("culture")
        if culture_vocal:
            log.info(f"📊 STATS VOCAL VARIETE : culture='{culture_vocal}'")
            ctx.args = [culture_vocal]
        else:
            ctx.args = []
        await cmd_stats(update, ctx)
        return
    if intent == "HISTORIQUE":
        await msg.edit_text("📋 *Historique*", parse_mode="Markdown")
        await cmd_historique(update, ctx)
        return
    # [US_Plan_occupation_parcelles / CA9] Routage vocal PLAN
    if intent == "PLAN":
        await msg.edit_text("🗺 *Plan du potager...*", parse_mode="Markdown")
        # parcelle extraite par le LLM (remplace _extract_plan_parcelle)
        parcelle_vocal = parsed.get("parcelle")
        if parcelle_vocal:
            log.info(f"🗺 PLAN VOCAL PARCELLE : parcelle='{parcelle_vocal}'")
            ctx.args = [parcelle_vocal]
        else:
            ctx.args = []
        await cmd_plan(update, ctx)
        return
    if intent == "INTERROGER":
        if _is_requete_godets(texte):
            log.info(f"🪴 GODETS VOCAL    : détecté → _consulter_godets")
            await msg.edit_text("🪴 *Godets en attente...*", parse_mode="Markdown")
            await _consulter_godets(update)
            return
        mots = texte.strip().split()
        if len(mots) > 4:
            log.info(f"❓ QUESTION DIRECTE : '{texte}' → traitement immédiat")
            await msg.edit_text("🔍 *Analyse de vos données...*", parse_mode="Markdown")
            await _ask_question(update, texte)
        else:
            await msg.edit_text(
                "🔍 *Quelle est votre question ?*\n\nPosez-la en vocal ou par écrit.",
                parse_mode="Markdown"
            )
            ctx.user_data['mode'] = 'ask'
        return
    if intent == "CORRIGER":
        await msg.edit_text("✏️ *Mode correction*", parse_mode="Markdown")
        for k in ['mode','corr_event_id','corr_candidates','corr_last_id',
                  'corr_pending','corr_event_actuel']:
            ctx.user_data.pop(k, None)
        await _corr_start(update, ctx)
        return
    if intent == "SUPPRIMER":
        await msg.edit_text("🗑 *Suppression*", parse_mode="Markdown")
        await _corr_annuler_dernier(update, ctx)
        return
    if intent == "MENU":
        await msg.edit_text("🏠 *Menu principal*", parse_mode="Markdown")
        await cmd_start(update, ctx)
        return
    if intent == "NOUVELLE":
        await msg.edit_text(
            "🎤 *Je vous écoute !*\n\nDites-moi ce que vous avez fait au potager.",
            parse_mode="Markdown", reply_markup=MENU_KEYBOARD
        )
        return
    # [US-007 / CA10] Routage vocal DEPLACER
    if intent == "DEPLACER":
        await msg.edit_text("🔀 *Réassociation culture → parcelle...*", parse_mode="Markdown")
        culture = parsed.get("culture") or _extract_culture_deplacer(texte)
        log.info(f"🔀 DEPLACER VOCAL  : culture='{culture}'")
        await _depl_start(update, ctx, culture)
        return
    # [US-038] Routage vocal NOTE
    if intent == "NOTE":
        await msg.edit_text("📝 *Nouvelle note...*", parse_mode="Markdown")
        await _note_start(update, ctx)
        return

    # intent == "ACTION" : items pré-parsés par parse_message, pas de 2e appel LLM
    await _parse_and_save(update, texte, msg, pre_parsed_items=parsed.get("items"))


async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Message texte → parsing direct ou commande de navigation."""
    texte_raw = update.message.text.strip()
    texte     = texte_raw.lower()  # comparaison insensible à la casse

    # [US-050 / CA5] Confirmation de dissociation : interceptée AVANT le garde de
    # liaison standard, qui exige un potager actif (_resoudre_et_armer_contexte) —
    # la dissociation doit rester utilisable même sans aucun potager.
    if ctx.user_data.get('mode') == 'delier_confirm':
        await _delier_confirm(update, ctx, texte_raw)
        return

    # [US-045 / CA6, CA7] Priorité 0 — avant tout log ou appel Groq. Un texte
    # brut ressemblant à un code de liaison est tenté ici (CA2).
    if not await _verifier_liaison_ou_onboarding(update, ctx, texte_raw):
        return

    log.info(f"💬 MESSAGE TEXTE  : {texte_raw}")

    # [US-066 / CA6] Nombre de graines d'origine en attente ? Intercepté avant tout
    # parsing : la réponse est un nombre, pas une nouvelle action à analyser.
    user_id = update.effective_user.id
    if user_id in _GODET_GRAINES_PENDING:
        await _godet_graines_reponse(update, texte_raw)
        return

    # [US-036 CA10] Nombre de pieds en attente (récolte végétative pesée) ?
    if user_id in _RECOLTE_PIECES_PENDING:
        pending = _RECOLTE_PIECES_PENDING.pop(user_id)
        items = pending["items"]

        import re
        match = re.search(r"(\d+)", texte_raw)
        if match:
            nb_pieds = match.group(1)
            pieces_item = dict(items[0])
            pieces_item["quantite"] = nb_pieds
            pieces_item["unite"]    = "plants"
            items.append(pieces_item)
            log.info(f"[US-036 CA10] Nombre de pieds détecté: {nb_pieds} — user_id={user_id}")
            await _parse_and_save(
                update, pending["texte"], pre_parsed_items=items,
                geste_file=pending.get("geste_file"),
            )
            return
        else:
            await update.message.reply_text(
                "❌ Nombre de pieds non reconnu. Précisez un nombre (ex: _2_, _3 pieds_)",
                parse_mode="Markdown"
            )
            _RECOLTE_PIECES_PENDING[user_id] = pending  # remettre en attente
            return

    # [US-021 CA9] Quantité en attente ? Traiter comme quantité
    if user_id in _QUANTITE_PENDING:
        pending = _QUANTITE_PENDING.pop(user_id)
        items = pending["items"]

        # Parser la quantité du texte (simple regex)
        import re
        match = re.search(r"([\d.]+)\s*(\w+)?", texte_raw)
        if match:
            qty = match.group(1)
            unite = match.group(2) or ""
            items[0]["quantite"] = qty
            if unite:
                items[0]["unite"] = unite
            log.info(f"[US-021 CA9] Quantité détectée: {qty} {unite} — user_id={user_id}")

            # Continuer avec confirmation
            # [INC-003] `geste_file` reprend ici la valeur mise de côté par
            # `_QUANTITE_PENDING` — sans quoi le geste de la file est enregistré
            # sans jamais être retiré de la file.
            await _parse_and_save(
                update, pending["texte"], pre_parsed_items=items,
                geste_file=pending.get("geste_file"),
            )
            return
        else:
            await update.message.reply_text(
                "❌ Quantité non reconnue. Précisez un nombre (ex: _2 kg_, _15 plants_)",
                parse_mode="Markdown"
            )
            _QUANTITE_PENDING[user_id] = pending  # remettre en attente
            return

    # Réinitialiser le mode SAUF si on est en plein flux de correction, déplacement ou en attente de question
    MODES_CORRECTION = {
        'corr_select', 'corr_apply', 'corr_search', 'corr_confirm_delete', 'corr_confirm',
        'ask', 'parcelle_confirm',
        # [US-007] flux déplacement
        'depl_culture_ask', 'depl_variete_select', 'depl_parcelle_select', 'depl_confirm',
        # [US-038] flux note guidée
        'note_category', 'note_details',
        # [US-172 / CA13] complétion guidée d'un argument de commande
        _INTERP_MODE_COMPLETION,
    }
    if ctx.user_data.get('mode') not in MODES_CORRECTION:
        ctx.user_data['mode'] = None

    # Boutons de navigation (avec ou sans émoji, texte libre accepté)
    if texte in NAV_NOUVELLE:
        await update.message.reply_text(
            "🎤 *Je vous écoute !*\n\nEnvoyez-moi un message vocal ou tapez votre action.",
            parse_mode="Markdown",
            reply_markup=MENU_KEYBOARD
        )
        return

    if texte in NAV_INTERROGER:
        await update.message.reply_text(
            "🔍 *Quelle est votre question ?*\n\n"
            "Exemples :\n"
            "• _Combien de kg de tomates cette saison ?_\n"
            "• _Quand ai-je récolté mes patates douces ?_\n"
            "• _Historique des traitements courgettes_",
            parse_mode="Markdown"
        )
        ctx.user_data['mode'] = 'ask'
        return

    if texte in NAV_HISTORIQUE:
        await cmd_historique(update, ctx)
        return

    if texte in NAV_STATS:
        await cmd_stats(update, ctx)
        return

    if texte in NAV_MENU:
        await cmd_start(update, ctx)
        return

    if texte in NAV_NOTE:
        await _note_start(update, ctx)
        return

    # ── PRIORITÉ 1 : modes correction actifs
    mode = ctx.user_data.get('mode')
    MODES_CORR = {'corr_search','corr_select','corr_apply','corr_confirm','corr_confirm_delete'}

    # Si l'utilisateur tape "corriger" ou un mot-clé NAV en plein milieu d'une correction
    # → reset complet et redémarrage propre (évite les états bloqués)
    if mode in MODES_CORR and (
        texte in NAV_CORRIGER
        or texte in NAV_MENU
        or texte in NAV_STATS
        or texte in NAV_HISTORIQUE
        or texte in NAV_INTERROGER
    ):
        log.info(f"🔄 RESET CORRECTION : mode={mode}, texte='{texte}' → nettoyage")
        for k in ['mode','corr_event_id','corr_candidates','corr_last_id',
                  'corr_pending','corr_event_actuel']:
            ctx.user_data.pop(k, None)
        # Laisser le flux normal gérer la commande (pas de return ici)
    elif mode == 'corr_search':
        await _corr_search(update, ctx, texte_raw)
        return
    elif mode == 'corr_select':
        await _corr_select(update, ctx, texte_raw)
        return
    elif mode == 'corr_apply':
        await _corr_apply(update, ctx, texte_raw)
        return
    elif mode == 'corr_confirm':
        await _corr_confirm(update, ctx, texte_raw)
        return
    elif mode == 'corr_confirm_delete':
        await _corr_confirm_delete(update, ctx, texte_raw)
        return

    # ── PRIORITÉ 1b : [US-007] flux déplacement actif
    elif mode == 'depl_culture_ask':
        culture = _extract_culture_deplacer(texte_raw) or texte_raw.strip().lower()
        ctx.user_data.pop('mode', None)
        await _depl_start(update, ctx, culture)
        return
    elif mode == 'depl_variete_select':
        await _depl_variete_select(update, ctx, texte_raw)
        return
    elif mode == 'depl_parcelle_select':
        await _depl_parcelle_select(update, ctx, texte_raw)
        return
    elif mode == 'depl_confirm':
        await _depl_confirm(update, ctx, texte_raw)
        return

    # ── PRIORITÉ 1c : [US-038] flux note guidée actif
    elif mode == 'note_category':
        await _note_category_selected(update, ctx, texte_raw)
        return
    elif mode == 'note_details':
        await _note_details_received(update, ctx, texte_raw)
        return

    # ── PRIORITÉ 1d : [US-172 / CA13, CA21] complétion d'argument en cours
    # Un flux engagé reste prioritaire : le message est une réponse à une
    # question déjà posée, pas une nouvelle demande à interpréter.
    elif mode == _INTERP_MODE_COMPLETION:
        await _interp_completion_texte(update, ctx, texte_raw)
        return

    # ── PRIORITÉ 2 : mode question analytique actif
    if mode == 'ask':
        ctx.user_data['mode'] = None
        log.info(f"❓ MODE ASK        : reroutage → _ask_question")
        await _ask_question(update, texte_raw)
        return

    # ── PRIORITÉ 2b : confirmation parcelle en attente [US_Plan_occupation_parcelles / CA12, CA13]
    if mode == 'parcelle_confirm':
        pending = ctx.user_data.get('parcelle_pending', {})
        ctx.user_data.pop('parcelle_pending', None)
        ctx.user_data['mode'] = None
        reponse = texte.strip().lower()
        if reponse in {"oui", "o", "yes", "y"}:
            nom = pending.get("nom", "")
            if nom:
                try:
                    db = SessionLocal()
                    try:
                        new_p = create_parcelle(
                            db, nom,
                            exposition=pending.get("exposition"),
                            superficie_m2=pending.get("superficie_m2"),
                            potager_id=current_context().potager_id,
                        )
                        log.info(f"[US_Plan_occupation_parcelles] Parcelle confirmée : {new_p.nom!r}")
                        details = []
                        if new_p.exposition:
                            details.append(f"exposition {new_p.exposition}")
                        if new_p.superficie_m2 is not None:
                            details.append(f"{new_p.superficie_m2} m²")
                        detail_str = f" ({', '.join(details)})" if details else ""
                        await update.message.reply_text(
                            f"✅ Parcelle *{new_p.nom.upper()}* créée{detail_str}.",
                            parse_mode="Markdown",
                        )
                    finally:
                        db.close()
                except ValueError as e:
                    await update.message.reply_text(f"❌ {e}", parse_mode="Markdown")
            return
        else:
            await update.message.reply_text("↩️ Création annulée.", parse_mode="Markdown")
            return

    # ── [US-172] Reconnaissance déterministe — calculée ici, appliquée en 3e
    # Elle ne coûte ni jeton ni requête (CA3), et elle est CONSULTÉE dès
    # maintenant parce que le raccourci destructeur ci-dessous en dépend :
    # « supprimer la parcelle nord » n'est pas « annuler ma dernière saisie »,
    # et l'exécuter comme telle serait précisément la suppression erronée que le
    # CA16 pose en couperet. Le raccourci reste inchangé pour tout ce que
    # l'interpréteur ne reconnaît pas — un « supprimer » nu, notamment.
    commande_reglee = svc_interpreteur.reconnaitre_par_regles(texte_raw)

    # ── PRIORITÉ 3 : mots-clés correction/suppression
    if texte in NAV_SUPPRIMER or (
        any(texte.startswith(k) for k in ["supprimer", "effacer", "annuler"])
        and commande_reglee is None
    ):
        await _corr_annuler_dernier(update, ctx)
        return
    if texte in NAV_CORRIGER or (
        any(texte.startswith(k) for k in ["corriger", "modifier"])
        and commande_reglee is None
    ):
        # Nettoyer tout contexte correction résiduel avant de démarrer
        for k in ['mode','corr_event_id','corr_candidates','corr_last_id',
                  'corr_pending','corr_event_actuel']:
            ctx.user_data.pop(k, None)
        await _corr_start(update, ctx)
        return

    # ── PRIORITÉ 3b : requête godets en attente ──────────────────────────────
    if _is_requete_godets(texte_raw):
        log.info(f"🪴 GODETS          : détecté → _consulter_godets")
        await _consulter_godets(update)
        return

    # ── PRIORITÉ 3c : [US-007 / CA10] détection déplacement culture → parcelle
    if _is_deplacer_request(texte_raw):
        culture = _extract_culture_deplacer(texte_raw)
        log.info(f"🔀 DEPLACER TEXTE  : détecté → culture='{culture}'")
        await _depl_start(update, ctx, culture)
        return

    # ── PRIORITÉ 3d : [US-038 / CA2] détection demande de note guidée
    if _is_note_request(texte_raw):
        log.info(f"📝 NOTE TEXTE      : détectée → _note_start")
        await _note_start(update, ctx)
        return

    # ── PRIORITÉ 3e : [US-172] la phrase désigne-t-elle une COMMANDE ?
    # Placé après toutes les gardes de flux de conversation et après les flux
    # guidés déjà dictables (godets, déplacement, note), et AVANT le routeur :
    # une phrase reconnue comme commande n'atteint jamais le parseur de geste.
    # Le repli modèle n'est tenté qu'ici — pas plus haut : le calculer avant les
    # flux ci-dessus aurait payé des jetons pour des phrases qu'ils traitent déjà.
    resultat_commande = commande_reglee or svc_interpreteur.interpreter(
        texte_raw, current_context()
    )
    if await _traiter_commande_interpretee(update, ctx, resultat_commande):
        return

    # ── PRIORITÉ 4 : nature de la demande décidée par le routeur [US-170 CA6, CA7]
    # Remplace _is_question(), dont la moitié du critère (le point d'interrogation
    # en fin de phrase) est absente du canal vocal — voir
    # docs/ANALYSE_ROUTAGE_QUESTIONS_2026-08-30.md. Le routeur porte déjà les
    # règles, la règle de geste, le catalogue, le cache de classification et le
    # modèle en dernier recours (US-093) ; le filet US-011 plus bas reste le
    # rattrapage des cas résiduels (CA10), inchangé.
    decision_routage = routeur.classer_demande(texte_raw, current_context())
    if decision_routage.nature != routeur.NATURE_ACTION:
        log.info(f"❓ QUESTION AUTO   : nature={decision_routage.nature} → reroutage vers _ask_question")
        await _ask_question(update, texte_raw)
        return

    # Sinon : parser comme action(s) potager
    # Si multi-lignes → traiter chaque ligne séparément
    lignes = [l.strip() for l in texte_raw.split("\n") if l.strip()]
    if len(lignes) > 1:
        msg = await update.message.reply_text(
            f"⏳ *{len(lignes)} actions détectées*, traitement en cours...",
            parse_mode="Markdown"
        )
        await _parse_multi(update, lignes, msg)
    else:
        msg = await update.message.reply_text("⏳ Analyse en cours...", parse_mode="Markdown")
        await _parse_and_save(update, texte_raw, msg)

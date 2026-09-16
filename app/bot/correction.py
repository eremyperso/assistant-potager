"""Correction et suppression d'un événement enregistré.

Module extrait de l'ancien bot.py monolithique (découpage 2026-09).
"""
import json
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import SessionLocal
from utils.parcelles import resolve_parcelle
from llm import passerelle
from llm.passerelle import LLMIndisponibleError, MESSAGE_REPLI_IA
from app.services.context import current_context
from app.services import evenements as svc_evenements
from app.services import contexte_semis as svc_contexte_semis
from app.services.permissions import require_role, PermissionInsuffisanteError
from datetime import date, timedelta
from .noyau import AFTER_RECORD_KEYBOARD, MENU_KEYBOARD, log


# ══════════════════════════════════════════════════════════════════════════════
# SYSTÈME DE CORRECTION
# ══════════════════════════════════════════════════════════════════════════════

CORR_KEYBOARD = ReplyKeyboardMarkup(
    [["✏️ Corriger", "🗑 Supprimer"], ["❌ Annuler"]],
    resize_keyboard=True, one_time_keyboard=True
)


def _fmt_event(e) -> str:
    """Formate un événement en une ligne lisible."""
    d    = e.date.strftime("%d/%m") if e.date else "?"
    act  = e.type_action or "?"
    cult = f" {e.culture}" if e.culture else ""
    var  = f" ({e.variete})" if e.variete else ""
    qte  = f" {e.quantite}{e.unite or ''}" if e.quantite else ""
    parc = f" [{e.parcelle}]" if e.parcelle else ""
    rang = f" x{e.rang}rangs" if e.rang else ""
    trt  = f" ({e.traitement})" if e.traitement else ""
    # [US-069] La filière d'un semis, seulement si elle est connue.
    ctxs = (
        f" · {svc_contexte_semis.libelle_contexte(e.contexte_semis)}"
        if getattr(e, "contexte_semis", None) else ""
    )
    return f"#{e.id} {d} — {act}{cult}{var}{qte}{rang}{parc}{trt}{ctxs}"


def _normalize_action_search(action: str) -> str:
    """Normalise une action retournée par Groq pour correspondre aux valeurs en base."""
    from unidecode import unidecode
    mapping = {
        "recolte": "recolte", "récolte": "recolte", "recolter": "recolte", "récolter": "recolte",
        "plantation": "plantation", "planter": "plantation", "planté": "plantation",
        "semis": "semis", "semer": "semis", "semé": "semis",
        "repiquage": "repiquage", "repiquer": "repiquage", "repiqué": "repiquage",
        "arrosage": "arrosage", "arroser": "arrosage", "arrosé": "arrosage",
        "traitement": "traitement", "traiter": "traitement", "traité": "traitement",
        "desherbage": "desherbage", "désherbage": "desherbage", "desherber": "desherbage",
        "paillage": "paillage", "pailler": "paillage", "paillé": "paillage",
        "taille": "taille", "tailler": "taille", "taillé": "taille",
        "tuteurage": "tuteurage", "tuteurer": "tuteurage", "tuteuré": "tuteurage",
        "fertilisation": "fertilisation", "fertiliser": "fertilisation",
        "observation": "observation", "observer": "observation",
        "mise_en_godet": "mise_en_godet", "godet": "mise_en_godet",
        "mis en godet": "mise_en_godet", "mise en godet": "mise_en_godet",
        "perte": "perte",
    }
    key = unidecode(action.lower().strip())
    return mapping.get(action.lower().strip(), mapping.get(key, action.lower().strip()))


def _find_candidates(description: str, limit: int = 3) -> list:
    """Le modèle extrait les critères → SQL retrouve les événements.

    [US-092 / CA6] La description dictée par l'utilisateur — seule partie
    variable d'un appel à l'autre — passe en message utilisateur séparé, après
    la consigne, au lieu d'être enchâssée en tête du prompt.
    """
    import json

    today     = date.today()
    last_week = (today - timedelta(days=7)).isoformat()
    last_month= (today - timedelta(days=30)).isoformat()

    prompt = f"""Aujourd'hui : {today.isoformat()} (année {today.year}).
L'utilisateur veut retrouver un événement potager, décrit dans le message suivant.

Retourne UNIQUEMENT ce JSON (null si non mentionné) :
{{"action": string|null, "culture": string|null, "variete": string|null, "date_debut": "YYYY-MM-DD"|null, "date_fin": "YYYY-MM-DD"|null, "parcelle": string|null}}

RÈGLES :
- action SANS accent : recolte, plantation, semis, mise_en_godet, arrosage, paillage, traitement, desherbage, taille, observation, tuteurage, fertilisation, perte, repiquage
- "godet", "mis en godet", "mise en godet", "repiquer en godet" → action="mise_en_godet"
- culture au singulier minuscule (conserver les accents si applicable, ex: "échalote", "courgette")
- variete : mot ou groupe de mots décrivant la variété (ex: "ronde", "cerise", "noire de crimée"), null si non mentionné
- "11 mars" ou "11 mars dernier" → date_debut="{today.year}-03-11", date_fin="{today.year}-03-11"  
- "la semaine dernière" → date_debut="{last_week}", date_fin="{today.isoformat()}"
- "ce mois" → date_debut="{last_month}", date_fin="{today.isoformat()}"
- "le dernier/la dernière" → pas de date, juste l'action/culture
- Toujours utiliser l'année {today.year} sauf si explicitement dit autrement
JSON brut uniquement."""

    try:
        # [fix bug id=357] `reasoning=True` (défaut) : sans reasoning_effort, le
        # modèle (gpt-oss, raisonneur) dépense tout le budget max_tokens dans son
        # raisonnement interne caché et coupe avant d'écrire le JSON de réponse
        # (finish_reason="length", content=""). Résultat en prod : "mise en godet
        # fève du 20/07" ne retournait aucun critère exploité, la recherche
        # retombait sur les 3 derniers événements toutes cultures confondues.
        # [US-092] Le garde-fou n'a plus à être répliqué ici : la passerelle
        # l'applique pour tout appel de chat.
        reponse = passerelle.appeler_chat(
            appel_type=passerelle.TYPE_PARSING,
            ctx=current_context(),
            prompt_fixe=prompt,
            message_utilisateur=description,
            max_tokens=200,
        )
        raw = reponse.texte
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:-1])
        criteres = json.loads(raw)
    except LLMIndisponibleError:
        # [CA9] Pas de repli utile : sans critères, la recherche retomberait sur
        # les 3 derniers événements toutes cultures confondues et proposerait de
        # corriger le mauvais. Mieux vaut ne rien proposer et le dire.
        raise
    except Exception as e:
        log.error(f"Extraction de critères en échec : {e}")
        criteres = {}

    # Normaliser l'action
    if criteres.get("action"):
        criteres["action"] = _normalize_action_search(criteres["action"])

    log.info(f"🔎 CRITÈRES RECHERCHE : {criteres}")

    db = SessionLocal()
    try:
        results = svc_evenements.find_candidates(db, current_context(), criteres, limit=limit)
        log.info(f"🔎 RÉSULTATS SQL   : {len(results)} trouvé(s)")
        return results
    finally:
        db.close()


async def _corr_annuler_dernier(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Propose correction ou suppression du dernier événement."""
    # [US-047 CA1] Garde de rôle — un lecteur ne peut ni corriger ni supprimer.
    try:
        require_role(current_context(), "editor", "corriger ou supprimer un événement")
    except PermissionInsuffisanteError as e:
        await update.message.reply_text(f"⛔ {e}")
        return

    db = SessionLocal()
    try:
        event = svc_evenements.dernier_evenement(db, current_context())
        if not event:
            await update.message.reply_text("❌ Aucun événement en base.")
            return
        ctx.user_data['corr_event_id'] = event.id
        ctx.user_data['mode'] = 'corr_select'
        ctx.user_data['corr_candidates'] = [event.id]
        await update.message.reply_text(
            f"Voici le dernier enregistrement :\n\n`{_fmt_event(event)}`\n\n"
            f"Que souhaitez-vous faire ?",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(
                [["✏️ Corriger", "🗑 Supprimer"], ["❌ Annuler"]],
                resize_keyboard=True, one_time_keyboard=True
            )
        )
    finally:
        db.close()


async def _corr_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Étape 1 — Demande à l'utilisateur de décrire l'événement à corriger."""
    # [US-047 CA1, CA4] Garde de rôle avant d'entrer dans le flux de correction —
    # bloque aussi, en amont, l'appel Groq de _corr_apply (étape 4).
    try:
        require_role(current_context(), "editor", "corriger un événement")
    except PermissionInsuffisanteError as e:
        await update.message.reply_text(f"⛔ {e}")
        return

    db = SessionLocal()
    try:
        last = svc_evenements.dernier_evenement(db, current_context())
        last_id  = last.id          if last else None
        last_fmt = _fmt_event(last) if last else None
    finally:
        db.close()

    ctx.user_data['mode'] = 'corr_search'
    ctx.user_data['corr_last_id'] = last_id

    txt = "✏️ *Mode correction*\n\nDécrivez l'action à retrouver :\n_Ex : récolte de tomates du 11 mars, dernier arrosage, paillage courgettes..._"
    if last_fmt:
        txt += f"\n\n_Ou tapez_ *1* _pour sélectionner directement le dernier :_\n`{last_fmt}`"

    await update.message.reply_text(
        txt, parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["1", "❌ Annuler"]], resize_keyboard=True)
    )


async def _corr_search(update: Update, ctx: ContextTypes.DEFAULT_TYPE, texte: str):
    """Étape 2 — Recherche les candidats en base."""
    if "annuler" in texte.lower():
        ctx.user_data['mode'] = None
        await update.message.reply_text("↩️ Correction annulée.", reply_markup=MENU_KEYBOARD)
        return

    # Raccourci "1" → dernier événement
    if texte.strip() == "1" and ctx.user_data.get('corr_last_id'):
        db = SessionLocal()
        try:
            event = svc_evenements.get_evenement(db, current_context(), ctx.user_data['corr_last_id'])
            candidates = [event] if event else []
            candidates_fmt = [_fmt_event(e) for e in candidates]
        finally:
            db.close()
    else:
        msg_wait = await update.message.reply_text("🔎 Recherche en cours...")
        try:
            candidates = _find_candidates(texte)  # charge déjà parcelle_rel via selectinload
        except LLMIndisponibleError:
            # [US-092 / CA9] Le raccourci "1" (dernier événement) reste, lui,
            # entièrement déterministe : on le rappelle plutôt que de proposer
            # des candidats devinés au hasard.
            log.warning("⏳ RECHERCHE       : IA indisponible, recherche par description impossible")
            await msg_wait.edit_text(
                f"⏳ {MESSAGE_REPLI_IA}.\n\n"
                "Tape *1* pour corriger directement le dernier événement enregistré.",
                parse_mode="Markdown",
            )
            return
        candidates_fmt = [_fmt_event(e) for e in candidates]
        try:
            await msg_wait.delete()
        except Exception:
            pass

    if not candidates:
        await update.message.reply_text(
            "❌ Aucun événement trouvé avec ces critères.\n\n"
            "💡 Essayez en précisant : l'action (_récolte, plantation..._), "
            "la culture (_tomate, carotte..._) ou la date (_11 mars, hier..._)",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([["❌ Annuler"]], resize_keyboard=True)
        )
        return

    ctx.user_data['corr_candidates'] = [e.id for e in candidates]
    ctx.user_data['mode'] = 'corr_select'

    if len(candidates) == 1:
        # Un seul résultat → directement en mode corr_apply, sans étape intermédiaire
        e = candidates[0]
        ctx.user_data['corr_event_id'] = e.id
        ctx.user_data['mode'] = 'corr_apply'   # ← clé du fix
        await update.message.reply_text(
            f"✅ Événement trouvé :\n\n`{candidates_fmt[0]}`\n\n"
            f"✏️ Dites-moi ce que vous souhaitez modifier :\n"
            f"_Ex : c'est 3 kg / la date c'est le 9 mars / ajouter parcelle nord_\n\n"
            f"Ou : [🗑 Supprimer] pour effacer cet événement.",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(
                [["🗑 Supprimer"], ["❌ Annuler"]],
                resize_keyboard=True
            )
        )
    else:
        lines = ["*Plusieurs événements trouvés, lequel voulez-vous modifier ?*\n"]
        for i, fmt in enumerate(candidates_fmt, 1):
            lines.append(f"*{i}.* `{fmt}`")
        btns = [[str(i) for i in range(1, len(candidates)+1)], ["❌ Annuler"]]
        await update.message.reply_text(
            "\n".join(lines), parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(btns, resize_keyboard=True)
        )


async def _corr_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE, texte: str):
    """Étape 3 — L'utilisateur choisit l'action (corriger/supprimer) ou le numéro."""
    t = texte.strip().lower()

    if "annuler" in t:
        ctx.user_data['mode'] = None
        await update.message.reply_text("↩️ Correction annulée.", reply_markup=MENU_KEYBOARD)
        return

    # Si event_id déjà défini (un seul candidat) → action directe
    event_id = ctx.user_data.get('corr_event_id')
    just_selected_from_list = False  # True si on vient d'extraire l'id depuis une liste

    # Sinon extraire le numéro depuis la liste de candidats
    if not event_id:
        try:
            num = int(t) - 1
            candidates = ctx.user_data.get('corr_candidates', [])
            event_id = candidates[num]
            ctx.user_data['corr_event_id'] = event_id
            just_selected_from_list = True  # ne pas auto-forwarder le "2" à corr_apply
        except (ValueError, IndexError):
            await update.message.reply_text("❓ Tapez le numéro affiché (1, 2, 3...).")
            return

    # Relire l'événement
    db = SessionLocal()
    try:
        event = svc_evenements.get_evenement(db, current_context(), event_id)
        event_fmt = _fmt_event(event) if event else None
    finally:
        db.close()

    if not event:
        await update.message.reply_text("❌ Événement introuvable.")
        ctx.user_data['mode'] = None
        return

    # Bouton supprimer
    if "supprimer" in t:
        ctx.user_data['mode'] = 'corr_confirm_delete'
        await update.message.reply_text(
            f"⚠️ *Confirmer la suppression ?*\n\n`{event_fmt}`\n\nCette action est irréversible.",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(
                [["✅ Oui, supprimer"], ["❌ Non, annuler"]], resize_keyboard=True
            )
        )
        return

    # Bouton corriger explicite
    if t in ("✏️ corriger", "corriger"):
        ctx.user_data['mode'] = 'corr_apply'
        await update.message.reply_text(
            f"✏️ Événement à corriger :\n\n`{event_fmt}`\n\n"
            f"Dites-moi ce que vous souhaitez modifier :\n"
            f"_Ex : c'était 3 kg et non 2 / la date c'était le 10 mars / ajouter parcelle nord_",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([["❌ Annuler"]], resize_keyboard=True)
        )
        return

    # ── Cas clé : l'utilisateur décrit directement la correction sans passer par le bouton
    # Ex : "changer la date au 9 mars", "c'était 1.5 kg", "parcelle nord", "associer parcelle tomate"
    # → on saute directement à corr_apply avec ce texte
    MOTS_CORRECTION = ("changer", "modifier", "mettre", "c'était", "c etait",
                       "il s'agit", "il s agit", "ajouter", "enlever", "suppr",
                       "corriger", "plutôt", "plutot", "non ", "pas ",
                       "associer", "affecter", "rattacher", "lier", "parcelle",
                       "la culture", "la variete", "la variété", "la quantite", "la quantité")
    if any(t.startswith(m) or m in t for m in MOTS_CORRECTION):
        log.info(f"⚡ CORRECTION DIRECTE : texte '{texte}' → saut vers corr_apply")
        ctx.user_data['mode'] = 'corr_apply'
        await _corr_apply(update, ctx, texte)
        return

    # Si l'event était déjà sélectionné AVANT cet appel (pas juste extrait d'une liste),
    # et que le texte décrit une correction → forwarder directement à corr_apply
    if ctx.user_data.get('corr_event_id') and not just_selected_from_list:
        log.info(f"⚡ CORRECTION DIRECTE (event déjà sélectionné) : texte '{texte}' → corr_apply")
        ctx.user_data['mode'] = 'corr_apply'
        await _corr_apply(update, ctx, texte)
        return

    # Sinon : premier choix de l'event dans une liste → proposer les boutons
    ctx.user_data['corr_event_id'] = event_id
    await update.message.reply_text(
        f"Événement sélectionné :\n\n`{event_fmt}`\n\nQue souhaitez-vous faire ?",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(
            [["✏️ Corriger", "🗑 Supprimer"], ["❌ Annuler"]],
            resize_keyboard=True, one_time_keyboard=True
        )
    )


async def _corr_confirm_delete(update: Update, ctx: ContextTypes.DEFAULT_TYPE, texte: str):
    """Confirmation suppression."""
    t = texte.strip().lower()
    event_id = ctx.user_data.get('corr_event_id')

    if "oui" in t or "supprimer" in t:
        db = SessionLocal()
        try:
            svc_evenements.supprimer_evenement(db, current_context(), event_id)
        except Exception as e:
            db.rollback()
            log.error(f"Erreur suppression : {e}")
            await update.message.reply_text(f"❌ Erreur : {e}", reply_markup=MENU_KEYBOARD)
            return
        finally:
            db.close()
        ctx.user_data['mode'] = None
        ctx.user_data.pop('corr_event_id', None)
        await update.message.reply_text(
            f"🗑 Événement #{event_id} supprimé avec succès.",
            reply_markup=MENU_KEYBOARD
        )
    else:
        ctx.user_data['mode'] = None
        ctx.user_data.pop('corr_event_id', None)
        await update.message.reply_text("↩️ Suppression annulée.", reply_markup=MENU_KEYBOARD)


async def _corr_apply(update: Update, ctx: ContextTypes.DEFAULT_TYPE, texte: str):
    """Étape 4 — Groq identifie les champs à modifier → présente un résumé pour confirmation."""
    t = texte.strip().lower()
    if "annuler" in t:
        ctx.user_data['mode'] = None
        await update.message.reply_text("↩️ Correction annulée.", reply_markup=MENU_KEYBOARD)
        return
    # Suppression demandée depuis corr_apply (bouton 🗑)
    if "supprimer" in t:
        event_id = ctx.user_data.get('corr_event_id')
        if event_id:
            ctx.user_data['corr_event_id'] = event_id
            ctx.user_data['mode'] = 'corr_confirm_delete'
            db = SessionLocal()
            try:
                ev = svc_evenements.get_evenement(db, current_context(), event_id)
                txt = _fmt_event(ev) if ev else f"#{event_id}"
            finally:
                db.close()
            await update.message.reply_text(
                f"⚠️ *Confirmer la suppression ?*\n\n`{txt}`",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup(
                    [["✅ Oui, supprimer"], ["❌ Non, annuler"]], resize_keyboard=True
                )
            )
        return

    event_id = ctx.user_data.get('corr_event_id')
    if not event_id:
        ctx.user_data['mode'] = None
        return

    db = SessionLocal()
    try:
        event = svc_evenements.get_evenement(db, current_context(), event_id)
        if not event:
            await update.message.reply_text("❌ Événement introuvable.")
            ctx.user_data['mode'] = None
            return
        event_actuel = {
            "action": event.type_action, "culture": event.culture,
            "variete": event.variete, "quantite": float(event.quantite) if event.quantite else None,
            "unite": event.unite, "parcelle": event.parcelle,
            "rang": event.rang, "duree_minutes": event.duree,
            "traitement": event.traitement, "commentaire": event.commentaire,
            "date": event.date.strftime("%Y-%m-%d") if event.date else None
        }
        # [US-069 / CA4] Seul un semis porte un contexte — et seul un semis
        # peut en recevoir un à la correction.
        if event.type_action == svc_contexte_semis.ACTION_SEMIS:
            event_actuel["contexte_semis"] = event.contexte_semis
    finally:
        db.close()

    msg_wait = await update.message.reply_text("⏳ Analyse de la correction...")

    import json

    today     = date.today()
    yesterday = (today - timedelta(days=1)).isoformat()

    prompt = f"""Aujourd'hui : {today.isoformat()}. Hier : {yesterday}.

Retourne UNIQUEMENT un JSON avec les champs MODIFIÉS (seulement ceux qui changent) :
{{"champ": nouvelle_valeur, ...}}

Champs disponibles : action, culture, variete, quantite, unite, parcelle, rang, duree_minutes, traitement, commentaire, date (format YYYY-MM-DD)
Exemples :
"c'était 3 kg pas 2" → {{"quantite": 3}}
"la date c'était le 10 mars" → {{"date": "{today.year}-03-10"}}
"ajouter parcelle nord" → {{"parcelle": "nord"}}
"enlever la parcelle" → {{"parcelle": null}}
"c'était 4 plants et non 5" → {{"quantite": 4}}
JSON brut uniquement."""

    # [US-092 / CA6] L'événement à corriger et la demande de l'utilisateur — les
    # deux seules parties variables — passent après la consigne, pas avant.
    prompt_variable = (
        f"\nÉvénement actuel : {json.dumps(event_actuel, ensure_ascii=False)}\n"
    )

    # [US-069 / CA4] « non, c'était en pépinière » : une correction qui ne dit
    # QUE le contexte d'un semis se lit sans modèle — et reste possible quand
    # l'IA est indisponible. Une phrase qui corrige autre chose passe par le
    # modèle, puis le contexte qu'elle dit est ajouté ci-dessous.
    est_semis = "contexte_semis" in event_actuel
    contexte_seul = svc_contexte_semis.correction_contexte_seule(texte) if est_semis else None
    if contexte_seul is not None:
        corrections = {"contexte_semis": contexte_seul}
        log.info(f"[US-069 / CA4] Correction du contexte sans modèle : {contexte_seul}")
    else:
        try:
            reponse = passerelle.appeler_chat(
                appel_type=passerelle.TYPE_PARSING,
                ctx=current_context(),
                prompt_fixe=prompt,
                prompt_variable=prompt_variable,
                message_utilisateur=f'Correction demandée : "{texte}"',
                max_tokens=300,
                reasoning=False,   # comportement constant : cet appel n'en passait pas
            )
            raw = reponse.texte
            if raw.startswith("```"):
                raw = "\n".join(raw.split("\n")[1:-1])
            corrections = json.loads(raw)
        except LLMIndisponibleError:
            # [CA9] Aucun repli utile : appliquer une correction devinée serait pire
            # que ne rien faire. L'événement reste intact, la correction est différée.
            log.warning("⏳ CORRECTION      : IA indisponible, correction différée")
            await msg_wait.edit_text(
                f"⏳ {MESSAGE_REPLI_IA}.\n\n"
                "Ton événement n'a pas été modifié — retente la correction dans un moment."
            )
            return
        except Exception as e:
            log.error(f"Analyse de correction en échec : {e}")
            await msg_wait.edit_text("❌ Je n'ai pas compris la correction. Reformulez.")
            return

        contexte_dit = svc_contexte_semis.detecter_contexte(texte) if est_semis else None
        if contexte_dit and isinstance(corrections, dict):
            corrections["contexte_semis"] = contexte_dit
            # Le modèle lit parfois « en pépinière » comme une parcelle : un
            # libellé de contexte qui ne nomme aucune parcelle réelle est retiré.
            nom_p = corrections.get("parcelle")
            if nom_p and svc_contexte_semis.detecter_contexte(f"en {nom_p}") == contexte_dit:
                db_p = SessionLocal()
                try:
                    if resolve_parcelle(db_p, nom_p, potager_id=current_context().potager_id) is None:
                        corrections.pop("parcelle", None)
                finally:
                    db_p.close()

    if not corrections:
        await msg_wait.edit_text(
            "❓ Je n'ai identifié aucun champ à modifier.\n"
            "Précisez davantage : _ex : c'était 3 kg, la date c'était hier..._",
            parse_mode="Markdown"
        )
        return

    # ── Validation FK parcelle ────────────────────────────────────────────────
    nom_parcelle_corr = corrections.get("parcelle")
    if nom_parcelle_corr is not None:
        db_check = SessionLocal()
        try:
            parcelle_resolue = resolve_parcelle(db_check, nom_parcelle_corr, potager_id=current_context().potager_id)
        finally:
            db_check.close()
        if parcelle_resolue is None:
            log.warning(f"⚠️ CORRECTION BLOQUÉE : parcelle inconnue {nom_parcelle_corr!r}")
            await msg_wait.edit_text(
                f"❌ La parcelle *{nom_parcelle_corr}* n'existe pas dans votre potager.\n\n"
                f"Créez-la d'abord avec : `/parcelle ajouter {nom_parcelle_corr}`",
                parse_mode="Markdown"
            )
            # Rester en corr_apply pour permettre une nouvelle correction
            return
        # Normaliser le nom vers la forme canonique de la BDD
        corrections["parcelle"] = parcelle_resolue.nom
        corrections["_parcelle_id"] = parcelle_resolue.id
        log.info(f"✅ PARCELLE RÉSOLUE : {nom_parcelle_corr!r} → {parcelle_resolue.nom!r} (id={parcelle_resolue.id})")

    log.info(f"✏️ CORRECTIONS     : {corrections}")

    # Préparer le résumé lisible avant confirmation
    LABELS = {
        "action": "Action", "culture": "Culture", "variete": "Variété",
        "quantite": "Quantité", "unite": "Unité", "parcelle": "Parcelle",
        "rang": "Rangs", "duree_minutes": "Durée (min)", "traitement": "Traitement",
        "commentaire": "Commentaire", "date": "Date", "contexte_semis": "Filière",
    }
    mapping = {
        "action": "type_action", "culture": "culture", "variete": "variete",
        "quantite": "quantite", "unite": "unite", "parcelle": "parcelle",
        "rang": "rang", "duree_minutes": "duree", "traitement": "traitement",
        "commentaire": "commentaire"
    }

    lines = [f"📋 *Résumé des modifications sur #{event_id} :*\n"]
    for champ, nouvelle_val in corrections.items():
        if champ.startswith("_"):   # champs internes (_parcelle_id…)
            continue
        ancienne_val = event_actuel.get(champ, "—") or "—"
        if champ == "contexte_semis":   # [US-069] libellés, pas valeurs stockées
            ancienne_val = svc_contexte_semis.libelle_contexte(event_actuel.get(champ))
            nouvelle_val = svc_contexte_semis.libelle_contexte(nouvelle_val)
        label = LABELS.get(champ, champ)
        lines.append(f"• *{label}* : `{ancienne_val}` → `{nouvelle_val if nouvelle_val is not None else 'supprimé'}`")

    lines.append("\nConfirmez-vous ces modifications ?")

    # Sauvegarder les corrections en attente + état avant modification
    ctx.user_data['corr_pending']      = corrections
    ctx.user_data['corr_event_actuel'] = event_actuel
    ctx.user_data['mode'] = 'corr_confirm'

    await msg_wait.edit_text(
        "\n".join(lines), parse_mode="Markdown"
    )
    await update.message.reply_text(
        "Confirmez ?",
        reply_markup=ReplyKeyboardMarkup(
            [["✅ Confirmer"], ["✏️ Modifier autre chose"], ["❌ Annuler"]],
            resize_keyboard=True, one_time_keyboard=True
        )
    )


async def _corr_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE, texte: str):
    """Étape 5 — Confirmation finale avant UPDATE en base."""
    t = texte.strip().lower()

    if "annuler" in t:
        ctx.user_data['mode'] = None
        await update.message.reply_text("↩️ Correction annulée.", reply_markup=MENU_KEYBOARD)
        return

    if "modifier" in t or "autre" in t:
        # Retour à l'étape de saisie de correction
        ctx.user_data['mode'] = 'corr_apply'
        db = SessionLocal()
        try:
            event = svc_evenements.get_evenement(db, current_context(), ctx.user_data['corr_event_id'])
            event_fmt = _fmt_event(event) if event else "?"
        finally:
            db.close()
        await update.message.reply_text(
            f"✏️ Que souhaitez-vous modifier d'autre ?\n\n`{event_fmt}`",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([["❌ Annuler"]], resize_keyboard=True)
        )
        return

    if "confirm" in t or "oui" in t or t == "✅ confirmer":
        event_id    = ctx.user_data.get('corr_event_id')
        corrections = ctx.user_data.get('corr_pending', {})
        event_actuel= ctx.user_data.get('corr_event_actuel', {})

        # ── Trace de correction dans texte_original ───────────────────
        LABELS = {
            "action": "action", "culture": "culture", "variete": "variété",
            "quantite": "quantité", "unite": "unité", "parcelle": "parcelle",
            "rang": "rangs", "duree_minutes": "durée", "traitement": "traitement",
            "commentaire": "commentaire", "date": "date", "contexte_semis": "filière",
        }
        details = ", ".join(
            f"{LABELS.get(k, k)}: {event_actuel.get(k, '—') or '—'} → {v if v is not None else 'supprimé'}"
            for k, v in corrections.items()
            if not k.startswith("_")   # ignorer champs internes (_parcelle_id…)
        )
        trace = f" | [CORR {date.today().isoformat()}] {details}"

        db = SessionLocal()
        try:
            event = svc_evenements.corriger_evenement(db, current_context(), event_id, corrections, trace)
            log.info(f"📝 TRACE CORRECTION: {trace}")
            log.info(f"✅ CORRIGÉ         : id={event_id} → {_fmt_event(event)}")
            result_fmt = _fmt_event(event)
        except Exception as e:
            db.rollback()
            log.error(f"Erreur UPDATE : {e}")
            await update.message.reply_text(f"❌ Erreur : {e}", reply_markup=MENU_KEYBOARD)
            return
        finally:
            db.close()

        ctx.user_data['mode'] = None
        ctx.user_data.pop('corr_pending', None)
        ctx.user_data.pop('corr_event_id', None)
        ctx.user_data.pop('corr_event_actuel', None)

        await update.message.reply_text(
            f"✅ *Modification enregistrée !*\n\n`{result_fmt}`",
            parse_mode="Markdown",
            reply_markup=AFTER_RECORD_KEYBOARD
        )
    else:
        await update.message.reply_text(
            "❓ Tapez *✅ Confirmer* pour valider ou *❌ Annuler*.",
            parse_mode="Markdown"
        )

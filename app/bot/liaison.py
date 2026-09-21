"""Onboarding, liaison du chat Telegram au compte, choix du potager actif, garde de rôle.

Module extrait de l'ancien bot.py monolithique (découpage 2026-09).
"""
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from app.config import PWA_URL
from database.db import SessionLocal, current_potager_id
from utils.parcelles import normalize_parcelle_name
from utils.tts import is_tts_enabled
from app.services.context import current_context, set_current_context
from app.services import evenements as svc_evenements
from app.services import liaison_telegram as svc_liaison_telegram
from app.services import potager_actif as svc_potager_actif
from app.services import potagers as svc_potagers
from app.services.permissions import require_role, PermissionInsuffisanteError
from database.models import Potager as _Potager
from .noyau import MENU_KEYBOARD, _md, log


# ══════════════════════════════════════════════════════════════════════════════
# HANDLERS PRINCIPAUX
# ══════════════════════════════════════════════════════════════════════════════

async def _demarrer_avec_code(update: Update, ctx: ContextTypes.DEFAULT_TYPE, code: str) -> None:
    """[US-091 / CA8-CA11] `/start <code>` — variante deep-link de `/lier` :
    mêmes refus (CA8), mais accueil contextualisé en cas de succès (CA10) et
    tolérance à l'absence de potager (CA11) plutôt que le message générique de
    `/lier`. `lier_chat_id` applique déjà tous les cas de refus, y compris
    CA9 (chat déjà lié) — seul le libellé du refus CA9 est adapté ici pour
    renvoyer vers la déliaison PWA plutôt que répéter le message générique."""
    chat_id = update.effective_chat.id
    db = SessionLocal()
    try:
        try:
            user = svc_liaison_telegram.lier_chat_id(db, code, chat_id)
        except svc_liaison_telegram.CodeInvalideError:
            await update.message.reply_text("❌ Code invalide.")
            return
        except svc_liaison_telegram.CodeExpireError:
            await update.message.reply_text(
                "⌛ Ce lien d'activation a expiré (validité 10 minutes). "
                "Générez-en un nouveau depuis l'application web."
            )
            return
        except svc_liaison_telegram.CodeDejaUtiliseError:
            await update.message.reply_text("❌ Ce lien d'activation a déjà été utilisé.")
            return
        except svc_liaison_telegram.ChatDejaLieError:
            # [CA9] Cas légitime (changement de téléphone) : deux gestes, pas
            # d'écrasement silencieux — cf. app/services/liaison_telegram.py.
            await update.message.reply_text(
                "❌ Ce chat Telegram est déjà lié à un autre compte.\n\n"
                "Déliez-le d'abord depuis l'application web (menu Compte), "
                "puis réessayez ce lien d'activation."
            )
            return

        ctx.user_data['tenant_user_id'] = user.id
        prenom = _md(update.effective_user.first_name or "jardinier")  # non-régression US-007

        try:
            tenant_ctx = svc_potager_actif.resoudre_tenant_context(db, user.id)
        except svc_potager_actif.AucunPotagerError:
            # [CA11] La liaison réussit quand même — aucun blocage, aucune erreur.
            await update.message.reply_text(
                f"✅ *Compagnon activé, {prenom} !*\n\n{_MSG_AUCUN_POTAGER}",
                parse_mode="Markdown",
            )
            return

        set_current_context(tenant_ctx)
        current_potager_id.set(tenant_ctx.potager_id)
        potager = db.query(_Potager).filter(_Potager.id == tenant_ctx.potager_id).first()
        nom_potager = _md(potager.nom) if potager else ""

        await update.message.reply_text(
            f"✅ *Compagnon activé, {prenom} !*\n\n"
            f"Votre potager *{nom_potager}* est prêt. Dictez-moi votre première "
            f"observation, à la voix ou par texte — je m'occupe du reste.\n\n"
            f"Ex : _\"Récolté 3 kg de tomates variété cerise parcelle nord\"_",
            parse_mode="Markdown",
            reply_markup=MENU_KEYBOARD,
        )
    finally:
        db.close()


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Message de bienvenue — gère aussi les deux deep-links `/start <code>` :
    activation du compagnon [US-091 / CA8-CA12] et geste préparé dans la PWA
    [US-196 / CA5]. Volontairement hors du garde de
    liaison (_COMMANDES_SANS_GARDE_LIAISON) : c'est justement le point
    d'entrée qui doit pouvoir lire le payload du deep-link avant tout blocage."""
    if ctx.args:
        # [US-196, US-224] Deux familles de codes passent désormais par ici, et
        # le préfixe seul les distingue : un code de liaison (US-045/US-091)
        # garde intégralement son traitement, y compris quand il est inconnu.
        from app.services import file_gestes as svc_file_gestes
        if svc_file_gestes.est_code_geste(ctx.args[0]):
            from .file_gestes import traiter_code_geste
            await traiter_code_geste(update, ctx, ctx.args[0])
            return
        await _demarrer_avec_code(update, ctx, ctx.args[0])
        return

    chat_id = update.effective_chat.id
    db = SessionLocal()
    try:
        user_id = svc_liaison_telegram.resoudre_user_id_pour_chat(db, chat_id)
        if user_id is None:
            # [CA12] Visiteur non lié arrivé sans code (recherche Telegram) —
            # message d'onboarding, aucune donnée enregistrée.
            await update.message.reply_text(_onboarding_liaison_msg(), parse_mode="Markdown")
            return

        ctx.user_data['tenant_user_id'] = user_id
        if not await _resoudre_et_armer_contexte(update, ctx, db, user_id):
            return
        nb = svc_evenements.compter_evenements(db, current_context())
    finally:
        db.close()

    prenom = update.effective_user.first_name or "jardinier"
    tts_etat = "🔊 activée" if is_tts_enabled() else "🔇 désactivée"

    await update.message.reply_text(
        f"🌿 *Bonjour {prenom} !*\n\n"
        f"Je suis votre assistant potager.\n"
        f"📦 *{nb} événements* enregistrés dans votre base.\n"
        f"Synthèse vocale : {tts_etat}\n\n"
        f"Envoyez-moi un *message vocal* ou *texte* pour enregistrer une action.\n"
        f"Ex : _\"Récolté 3 kg de tomates variété cerise parcelle nord\"_\n\n"
        # [US-171 / CA10] Le menu natif remplace les anciens boutons du bas.
        f"⌨️ Toutes les commandes sont dans le menu, à gauche de la zone de saisie.\n"
        f"📖 Tapez /help pour l'aide en ligne.",
        parse_mode="Markdown",
        reply_markup=MENU_KEYBOARD
    )


# ──────────────────────────────────────────────────────────────────────────────
# [US-045] Liaison chat Telegram ⇄ compte web
# ──────────────────────────────────────────────────────────────────────────────
def _onboarding_liaison_msg() -> str:
    """Message statique (aucun appel LLM — CA6) invitant à lier le chat.
    Fonction (et non constante module) car `_md()` est défini plus bas dans ce
    fichier — évite un NameError à l'import si l'ordre de définition change."""
    return (
        "👋 *Ce chat n'est pas encore relié à votre compte.*\n\n"
        f"1️⃣ Inscrivez-vous ou connectez-vous sur {_md(PWA_URL)}\n"
        # [US-091 / CA12] Enrichi du geste d'activation en un clic (deep-link +
        # QR), sans retirer le repli manuel /lier — non-régression US-045.
        "2️⃣ Générez votre lien d'activation depuis l'application (écran d'accueil ou menu Compte)\n"
        "3️⃣ Ouvrez-le ici, ou envoyez-moi le code affiché, ou tapez `/lier VOTRECODE`\n\n"
        "_Tant que ce chat n'est pas relié, aucune donnée n'est enregistrée._"
    )


_MSG_AUCUN_POTAGER = (
    "🌱 *Vous n'êtes membre d'aucun potager pour l'instant.*\n\n"
    "Créez ou rejoignez un potager depuis l'application web pour commencer à l'utiliser ici."
)


async def _resoudre_et_armer_contexte(update: Update, ctx: ContextTypes.DEFAULT_TYPE, db, user_id: int) -> bool:
    """[US-046 / CA1, CA5, CA6] Résout le TenantContext réel (potager actif) de
    `user_id` et l'arme pour tout le reste du traitement de cet Update — via
    set_current_context() (relu par current_context() partout dans bot.py) et
    en réarmant le GUC RLS current_potager_id (US-043) avec le vrai potager.
    Renvoie False (et bloque, message CA5) si l'utilisateur n'a aucun potager.
    """
    try:
        tenant_ctx = svc_potager_actif.resoudre_tenant_context(db, user_id)
    except svc_potager_actif.AucunPotagerError:
        await update.message.reply_text(_MSG_AUCUN_POTAGER, parse_mode="Markdown")
        return False
    set_current_context(tenant_ctx)
    current_potager_id.set(tenant_ctx.potager_id)
    return True


async def _verifier_liaison_ou_onboarding(
    update: Update, ctx: ContextTypes.DEFAULT_TYPE, texte_brut: str | None = None,
    exiger_potager: bool = True,
) -> bool:
    """[US-045 / CA6, CA7] Garde de priorité 0 — appelée en tout premier dans
    handle_voice/handle_text, avant tout appel Groq (transcription ou
    classification). Renvoie True si le chat est lié (ou vient d'être lié via
    un code envoyé en texte brut) ET rattaché à un potager (US-046 / CA5,
    sinon bloqué) et que le traitement normal peut continuer ; False si un
    message d'onboarding/d'erreur a déjà été envoyé et que le handler
    appelant doit s'arrêter immédiatement (`return`).

    [US-087 / CA1, CA6] `exiger_potager=False` : la liaison reste exigée (un chat non lié
    est renvoyé vers le parcours de liaison), mais l'absence de potager ne bloque plus —
    c'est la situation même de qui utilise `/rejoindre` pour obtenir son premier potager.
    """
    chat_id = update.effective_chat.id
    db = SessionLocal()
    try:
        user_id = svc_liaison_telegram.resoudre_user_id_pour_chat(db, chat_id)
        if user_id is not None:
            ctx.user_data['tenant_user_id'] = user_id  # [CA8] disponible pour construire un TenantContext
            if not exiger_potager:
                return True
            return await _resoudre_et_armer_contexte(update, ctx, db, user_id)

        # [CA2] Un message texte (pas vocal — pas d'appel Groq) ressemblant à un
        # code peut être envoyé sans le préfixe /lier.
        if texte_brut and svc_liaison_telegram.ressemble_a_un_code(texte_brut):
            try:
                user = svc_liaison_telegram.lier_chat_id(db, texte_brut, chat_id)
                ctx.user_data['tenant_user_id'] = user.id
                await update.message.reply_text(
                    "✅ *Chat relié avec succès !* Vous pouvez maintenant dicter vos actions.",
                    parse_mode="Markdown",
                )
                return await _resoudre_et_armer_contexte(update, ctx, db, user.id)
            except svc_liaison_telegram.CodeExpireError:
                await update.message.reply_text(
                    "⌛ Ce code a expiré (validité 10 minutes). Générez-en un nouveau depuis l'application web."
                )
                return False
            except svc_liaison_telegram.CodeDejaUtiliseError:
                await update.message.reply_text("❌ Ce code a déjà été utilisé.")
                return False
            except svc_liaison_telegram.ChatDejaLieError:
                await update.message.reply_text("❌ Ce chat Telegram est déjà lié à un autre compte.")
                return False
            except svc_liaison_telegram.CodeInvalideError:
                pass  # ne ressemble à aucun code connu → message d'onboarding générique ci-dessous

        await update.message.reply_text(_onboarding_liaison_msg(), parse_mode="Markdown")
        return False
    finally:
        db.close()


async def cmd_lier(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/lier <code> — [US-045] Relie ce chat Telegram à un compte web via un code à usage unique."""
    if not ctx.args:
        await update.message.reply_text(
            "🔗 *Liaison de compte*\n\n"
            "Usage : `/lier VOTRECODE`\n\n"
            "Générez un code depuis l'application web (menu profil), valable 10 minutes.",
            parse_mode="Markdown",
        )
        return

    code = ctx.args[0]
    chat_id = update.effective_chat.id
    db = SessionLocal()
    try:
        try:
            user = svc_liaison_telegram.lier_chat_id(db, code, chat_id)
            ctx.user_data['tenant_user_id'] = user.id
            await update.message.reply_text("✅ *Chat relié avec succès !*", parse_mode="Markdown")
        except svc_liaison_telegram.CodeInvalideError:
            await update.message.reply_text("❌ Code invalide.")
        except svc_liaison_telegram.CodeExpireError:
            await update.message.reply_text(
                "⌛ Ce code a expiré (validité 10 minutes). Générez-en un nouveau depuis l'application web."
            )
        except svc_liaison_telegram.CodeDejaUtiliseError:
            await update.message.reply_text("❌ Ce code a déjà été utilisé.")
        except svc_liaison_telegram.ChatDejaLieError:
            await update.message.reply_text("❌ Ce chat Telegram est déjà lié à un autre compte.")
    finally:
        db.close()


_DELIER_CLAVIER_CONFIRMATION = ReplyKeyboardMarkup(
    [["✅ Oui, délier", "❌ Non, annuler"]], resize_keyboard=True, one_time_keyboard=True
)


async def cmd_delier(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/delier — [US-050 / CA2] Dissocie ce chat Telegram de son compte web, après
    confirmation. Volontairement HORS du garde de liaison standard
    (_COMMANDES_SANS_GARDE_LIAISON) : l'action porte sur l'identité elle-même, pas
    sur des données potager — elle doit rester utilisable même sans potager actif
    (CA5, notes techniques US-050)."""
    chat_id = update.effective_chat.id
    db = SessionLocal()
    try:
        user_id = svc_liaison_telegram.resoudre_user_id_pour_chat(db, chat_id)
    finally:
        db.close()

    if user_id is None:
        # [notes techniques US-050] Chat non lié → même message d'onboarding que
        # les autres commandes métier, pas de cas particulier.
        await update.message.reply_text(_onboarding_liaison_msg(), parse_mode="Markdown")
        return

    ctx.user_data['mode'] = 'delier_confirm'
    ctx.user_data['delier_user_id'] = user_id
    await update.message.reply_text(
        "⚠️ *Dissocier ce chat Telegram de votre compte ?*\n\n"
        "Vous ne recevrez plus de réponses ici tant que vous n'aurez pas relié un "
        "nouveau code depuis l'application web.",
        parse_mode="Markdown",
        reply_markup=_DELIER_CLAVIER_CONFIRMATION,
    )


async def _delier_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE, texte: str):
    """[US-050 / CA2, CA3] Étape 2 — applique ou annule la dissociation selon la
    réponse à cmd_delier. Ne passe jamais par current_context()/TenantContext
    (CA5) : `delier_user_id` vient de la résolution faite dans cmd_delier."""
    t = texte.strip().lower()
    user_id = ctx.user_data.get('delier_user_id')
    ctx.user_data['mode'] = None
    ctx.user_data.pop('delier_user_id', None)

    if "oui" in t or "délier" in t or "delier" in t:
        db = SessionLocal()
        try:
            svc_liaison_telegram.delier_chat_id(db, user_id)
        finally:
            db.close()
        ctx.user_data.pop('tenant_user_id', None)
        await update.message.reply_text(
            "✅ *Chat dissocié.* Générez un nouveau code depuis l'application web "
            "(menu profil) pour relier ce chat ou un autre avec `/lier`.",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        await update.message.reply_text("↩️ Dissociation annulée.", reply_markup=MENU_KEYBOARD)


# ──────────────────────────────────────────────────────────────────────────────
# [US-087] Rejoindre un potager avec un code d'invitation
# ──────────────────────────────────────────────────────────────────────────────

_MSG_AIDE_REJOINDRE = (
    "🔑 *Rejoindre un potager*\n\n"
    "Usage : `/rejoindre VOTRECODE`\n\n"
    "Le code compte 8 caractères : ton hôte le génère depuis l'application web "
    "(réglages de son potager, onglet Membres)."
)
_MSG_REJOINDRE_CODE_INCONNU = "❌ Ce code d'invitation est inconnu. Vérifie-le : il compte 8 caractères."
_MSG_REJOINDRE_CODE_EXPIRE = (
    "⌛ Ce code d'invitation a expiré. Demande à ton hôte d'en générer un nouveau "
    "depuis l'application web."
)
_MSG_REJOINDRE_CODE_UTILISE = (
    "❌ Ce code d'invitation a déjà été utilisé. Demande à ton hôte d'en générer un nouveau."
)
_MSG_REJOINDRE_DEJA_MEMBRE = "ℹ️ Tu es déjà membre de ce potager : rien à faire."


def _message_potager_rejoint(adhesion: svc_potagers.AdhesionPotager) -> str:
    """[US-087 / CA4, CA6] Confirmation en français courant : le potager rejoint et le rôle
    obtenu, puis — selon le cas — l'annonce du potager actif ou le rappel de `/potager`."""
    libelle = adhesion.role_libelle
    en_tant_que = f"en tant qu'{libelle}" if libelle[:1] in "aeiouyéèêîô" else f"en tant que {libelle}"
    texte = f"✅ Tu as rejoint *{_md(adhesion.potager_nom)}* {en_tant_que}."
    if adhesion.devenu_actif:
        suite = (
            "tu peux y saisir tes événements." if adhesion.peut_ecrire
            else "tu peux le consulter, sans y enregistrer d'événement."
        )
        texte += f"\n\nC'est maintenant ton potager actif : {suite}"
    elif adhesion.potager_actif_nom:
        texte += (
            f"\n\nTon potager actif reste *{_md(adhesion.potager_actif_nom)}*. "
            f"Pour basculer sur *{_md(adhesion.potager_nom)}*, envoie /potager."
        )
    return texte


async def cmd_rejoindre(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/rejoindre <code> — [US-087] Rejoint un potager avec un code d'invitation (US-048).

    Une porte d'entrée de plus vers `svc_potagers.rejoindre_potager`, qui réutilise
    `accepter_invitation` : aucune règle de validation n'est écrite ici, seulement la
    traduction de chaque refus en un message qui lui est propre (CA5). Enregistrée par
    `_enregistrer_commande` : le garde de liaison exige un chat relié (CA1), sans exiger
    de potager. Commande de slash pure — aucun appel Groq (CA9). Le code n'est jamais
    journalisé, ni ici ni dans la réponse."""
    if not ctx.args:
        await update.message.reply_text(_MSG_AIDE_REJOINDRE, parse_mode="Markdown")
        return

    # La casse et les espaces parasites sont absorbés par `accepter_invitation` (CA7).
    code = ctx.args[0].strip()
    user_id = ctx.user_data.get('tenant_user_id')
    db = SessionLocal()
    try:
        try:
            adhesion = svc_potagers.rejoindre_potager(db, user_id, code)
        except svc_potagers.InvitationInvalideError:
            await update.message.reply_text(_MSG_REJOINDRE_CODE_INCONNU)
            return
        except svc_potagers.InvitationExpireeError:
            await update.message.reply_text(_MSG_REJOINDRE_CODE_EXPIRE)
            return
        except svc_potagers.InvitationDejaUtiliseeError:
            await update.message.reply_text(_MSG_REJOINDRE_CODE_UTILISE)
            return
        except svc_potagers.DejaMembreError:
            await update.message.reply_text(_MSG_REJOINDRE_DEJA_MEMBRE)
            return
    finally:
        db.close()

    await update.message.reply_text(_message_potager_rejoint(adhesion), parse_mode="Markdown")


# ──────────────────────────────────────────────────────────────────────────────
# [US-046] Sélection du potager actif
# ──────────────────────────────────────────────────────────────────────────────

async def cmd_potager(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/potager [nom] — [US-046 / CA2] Liste les potagers de l'utilisateur,
    potager actif marqué, boutons inline pour en changer.

    [US-172 / CA9] L'argument facultatif `nom` bascule directement sur le
    potager nommé, en passant par `definir_potager_actif` — le même service que
    le bouton inline, jamais une seconde règle. Il existe pour que « passe sur
    le potager de la maison » ait une commande tapée strictement équivalente :
    sans lui, la phrase dictée aurait dû réimplémenter la bascule, ce que le CA9
    interdit. Sans argument, le comportement est celui d'avant, à l'identique.
    Un nom qui ne correspond exactement à aucun potager n'en substitue jamais un
    autre (CA12) : la liste complète est affichée, et le jardinier choisit.
    """
    user_id = ctx.user_data.get('tenant_user_id')
    db = SessionLocal()
    try:
        potagers = svc_potager_actif.lister_potagers_utilisateur(db, user_id)
        if not potagers:
            await update.message.reply_text(_MSG_AUCUN_POTAGER, parse_mode="Markdown")
            return

        nom_demande = " ".join(ctx.args).strip() if getattr(ctx, "args", None) else ""
        if nom_demande:
            cible = normalize_parcelle_name(nom_demande)
            correspondances = [
                p for p in potagers if normalize_parcelle_name(p.nom) == cible
            ]
            if len(correspondances) == 1:
                tenant_ctx = svc_potager_actif.definir_potager_actif(
                    db, user_id, correspondances[0].id
                )
                set_current_context(tenant_ctx)
                current_potager_id.set(tenant_ctx.potager_id)
                log.info(f"[US-172] Potager actif changé par commande : {correspondances[0].nom!r}")
                await update.message.reply_text(
                    f"✅ Potager actif : *{_md(correspondances[0].nom)}*",
                    parse_mode="Markdown",
                )
                return
            log.info(
                f"[US-172 CA12] Potager {nom_demande!r} sans correspondance exacte "
                f"({len(correspondances)} candidat(s)) → liste proposée"
            )

        actif_id = current_context().potager_id
        boutons = [
            [InlineKeyboardButton(
                f"{'✅ ' if p.id == actif_id else ''}{p.nom}",
                callback_data=f"potager_select_{p.id}",
            )]
            for p in potagers
        ]
        await update.message.reply_text(
            "🌻 *Vos potagers* — sélectionnez le potager actif :",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(boutons),
        )
    finally:
        db.close()


async def _potager_select_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """[US-046 / CA2, CA3, CA4] Callback inline — change le potager actif."""
    query = update.callback_query
    await query.answer()

    try:
        potager_id = int(query.data[len("potager_select_"):])
    except ValueError:
        await query.edit_message_text("❌ Données invalides.", reply_markup=None)
        return

    user_id = ctx.user_data.get('tenant_user_id')
    db = SessionLocal()
    try:
        try:
            tenant_ctx = svc_potager_actif.definir_potager_actif(db, user_id, potager_id)
        except svc_potager_actif.PotagerNonMembreError:
            await query.edit_message_text("❌ Vous n'êtes pas membre de ce potager.", reply_markup=None)
            return
        except svc_potager_actif.PotagerInactifError:
            # [US-080 / CA6] Le potager a été archivé entre l'affichage de la
            # liste et le clic — le bouton pointe sur un potager devenu inactif.
            await query.edit_message_text(
                "📦 Ce potager est archivé. Désarchivez-le depuis l'application web pour l'utiliser.",
                reply_markup=None,
            )
            return

        set_current_context(tenant_ctx)
        current_potager_id.set(tenant_ctx.potager_id)

        potager = db.query(_Potager).filter(_Potager.id == potager_id).first()
        nom = potager.nom if potager else str(potager_id)
        await query.edit_message_text(f"✅ Potager actif : *{nom}*", parse_mode="Markdown", reply_markup=None)
    finally:
        db.close()


# ──────────────────────────────────────────────────────────────────────────────
# [US_Plan_occupation_parcelles / CA10, CA12, CA13] Commande /parcelle
# ──────────────────────────────────────────────────────────────────────────────

async def _refuser_si_role_insuffisant(update, action_label: str) -> bool:
    """[US-047 / US-172 CA14] Garde de rôle des commandes d'ÉCRITURE du bot.

    Posé dans le handler, et non dans l'interpréteur : c'est ce qui garantit
    qu'une commande dictée traverse exactement les mêmes contrôles que la même
    commande tapée. Un garde qui ne vivrait que dans l'interpréteur ouvrirait un
    chemin d'accès parallèle — l'inverse exact de ce que le CA14 demande.

    Les commandes de CONSULTATION (/plan, /stats, /fiche, /rotation…) n'en
    portent pas : un lecteur a le droit de lire.

    Retourne True si la commande doit s'arrêter là.
    """
    try:
        require_role(current_context(), "editor", action_label)
        return False
    except PermissionInsuffisanteError as e:
        await update.message.reply_text(f"⛔ {e}")
        return True

"""Commandes /help et /version — les domaines d'aide (_HELP_DOMAINES) vivent ici.

Module extrait de l'ancien bot.py monolithique (découpage 2026-09).
"""
import os
from telegram import Update
from telegram.ext import ContextTypes
from .noyau import _APP_GIT_SHA, _APP_VERSION


# ──────────────────────────────────────────────────────────────────────────────
# [US_Aide_contextuelle_par_commande] Textes d'aide contextuels par mot-clé
# ──────────────────────────────────────────────────────────────────────────────

_HELP_PARCELLE = (
    "📍 *Aide — Parcelles*\n"
    "Gérer et consulter vos parcelles du potager.\n\n"
    "*── Plan d'occupation ──*\n"
    "• Vue globale de toutes les parcelles\n"
    "  → /plan\n"
    "  → _\"plan du potager\"_\n"
    "• Vue détaillée d'une parcelle\n"
    "  → /plan nord\n"
    "  → _\"plan parcelle nord\"_\n"
    "  → _\"qu'est-ce qui pousse en nord ?\"_\n\n"
    "*── Gestion des parcelles ──*\n"
    "• Lister toutes les parcelles connues\n"
    "  → /parcelle lister\n"
    "  → /parcelles\n"
    "• Créer une nouvelle parcelle\n"
    "  → /parcelle ajouter nord\n"
    "  → /parcelle ajouter nord sud 12.5\n"
    "  _(nom · exposition · superficie en m²)_\n"
    "• Modifier les métadonnées d'une parcelle\n"
    "  → /parcelle modifier nord exposition=sud\n"
    "  → /parcelle modifier nord superficie=8.5\n"
    "  → /parcelle modifier nord exposition=sud superficie=8.5\n"
    "  → /parcelle modifier serre pepiniere=true\n"
    "  → /parcelle modifier serre abri=serre paillage=oui\n"
    "  → \"la parcelle 2 est sous serre\" · \"rang 3 paillé\"\n"
    "  _Paramètres : exposition · superficie · ordre · pepiniere · abri · paillage_\n"
    "  _abri : aucun · voile · châssis · tunnel · serre — il pèse sur la confiance_\n"
    "  _pepiniere=true : une serre/pépinière ne compte jamais comme_\n"
    "  _pleine terre — un semis qui y est rattaché reste en pépinière_\n"
    "  _tant qu'aucune plantation réelle n'a eu lieu ailleurs._\n"
    "• Renommer une parcelle (propagation sur tout l'historique)\n"
    "  → /parcelle renommer sud carré-sud\n"
    "• Supprimer une parcelle (soft-delete — historique conservé)\n"
    "  → /parcelle supprimer serre-1\n"
    "  ⚠️ _Les événements liés deviennent « Non localisé »_\n\n"
    "💡 _Noms de parcelle insensibles à la casse.\n"
    "   Les doublons sont détectés automatiquement._"
)


_HELP_SEMIS = (
    "🌱 *Aide — Semis*\n"
    "Enregistrer vos semis en pépinière ou en pleine terre.\n\n"
    "*Actions disponibles :*\n"
    "• Semis en pépinière\n"
    "  → _\"semis tomates variété Saint-Pierre le 5 mars\"_\n"
    "  → _\"j'ai semé 30 graines de basilic en plateau\"_\n"
    "• Semis en pleine terre\n"
    "  → _\"semis direct carottes en parcelle B2\"_\n"
    "  → _\"semis radis pleine terre parcelle A3 le 8 avril\"_\n"
    "• Consulter les semis en cours\n"
    "  → _\"liste de mes semis\"_\n"
    "  → _\"quels semis sont en cours ?\"_\n\n"
    "💡 _Précisez toujours : culture · variété (optionnel) · date · lieu_"
)


_HELP_GODET = (
    "🪴 *Aide — Mise en godet*\n"
    "Suivre le repiquage des plants de pépinière en godet.\n\n"
    "*Actions disponibles :*\n"
    "• Enregistrer une mise en godet\n"
    "  → _\"mise en godet 20 tomates Saint-Pierre\"_\n"
    "  → _\"mis en godet 24 tomates sur 30 graines\"_ (taux calculé)\n"
    "  → _\"repiquer 15 plants de poivron en godet le 10 mars\"_\n"
    "• Consulter les godets en attente\n"
    "  → _\"liste des godets\"_\n"
    "  → _\"quels plants sont en godet ?\"_\n"
    "• Voir les stats pépinière\n"
    "  → /stats  (section 🪴 Pépinière)\n\n"
    "💡 _La mise en godet est l'étape entre le semis plateau\n"
    "   et la plantation en parcelle._"
)


_HELP_RECOLTE = (
    "🧺 *Aide — Récoltes*\n"
    "Enregistrer vos récoltes ponctuelles ou finales.\n\n"
    "*Actions disponibles :*\n"
    "• Récolte ponctuelle (culture continue)\n"
    "  → _\"récolté 800g de tomates en A1\"_\n"
    "  → _\"cueilli 3 courgettes parcelle B2 aujourd'hui\"_\n"
    "• Récolte finale / clôture de culture\n"
    "  → _\"récolte finale haricots parcelle A3\"_\n"
    "  → _\"dernière récolte courgettes B2, culture terminée\"_\n"
    "• Récolte de graines\n"
    "  → _\"récolte graines tomates Saint-Pierre 15g\"_\n"
    "  → _\"mis de côté graines courge pour semis prochain\"_\n"
    "• Consulter l'historique\n"
    "  → _\"historique récoltes\"_\n"
    "  → _\"mes récoltes du mois de mars\"_"
)


_HELP_STOCK = (
    "📦 *Aide — Stock*\n"
    "Suivre vos stocks de semences et intrants.\n\n"
    "*Actions disponibles :*\n"
    "• Consulter le stock\n"
    "  → _\"stock tomates\"_\n"
    "  → _\"combien de graines de basilic il me reste ?\"_\n"
    "• Ajouter au stock\n"
    "  → _\"ajout stock carottes Nantaise 50g\"_\n"
    "  → _\"reçu 1 sachet poivron Corno di Toro\"_\n"
    "• Déduire du stock (automatique après semis)\n"
    "  → _Le stock est mis à jour automatiquement_\n"
    "  → _à chaque semis enregistré._\n"
    "• Alertes stock faible\n"
    "  → _Le bot signale automatiquement si un stock_\n"
    "  → _passe sous le seuil critique._"
)


_HELP_STATS = (
    "📊 *Aide — Statistiques*\n"
    "Consulter les bilans de votre potager.\n\n"
    "*Actions disponibles :*\n"
    "• Statistiques générales\n"
    "  → /stats\n"
    "  → _\"bilan du potager\"_\n"
    "• Stats par culture\n"
    "  → _\"stats tomates\"_\n"
    "  → _\"bilan courgettes cette saison\"_\n"
    "• Stats par parcelle\n"
    "  → _\"stats parcelle A1\"_\n"
    "  → _\"bilan rotation parcelle B2\"_\n"
    "• Synthèse des semis\n"
    "  → _\"synthèse semis\"_\n"
    "  → _\"récapitulatif de mes semis\"_\n"
    "• Bilan de rotation\n"
    "  → _\"rotation des cultures\"_\n"
    "  → _\"quelles familles ont occupé chaque parcelle ?\"_"
)


_HELP_NOTE = (
    "📝 *Aide — Notes*\n"
    "Consigner rapidement une observation de terrain, guidé par l'assistant.\n\n"
    "*Catégories disponibles :*\n"
    "🔍 Observation — remarque générale de suivi\n"
    "🐛 Maladie / ravageur — problème sanitaire détecté\n"
    "💧 Arrosage (remarque) — constat qualitatif (sol sec...), sans créer d'événement d'arrosage réel\n"
    "🌿 Paillage — constat ou action de paillage informelle\n\n"
    "*Comment noter :*\n"
    "• /note — ouvre le menu de catégories\n"
    "• _\"je veux noter une observation\"_ (vocal ou texte)\n\n"
    "L'assistant pose une question adaptée à la catégorie choisie, puis vous répondez\n"
    "en langage naturel. Un récapitulatif s'affiche avant enregistrement définitif."
)


_HELP_CULTURE = (
    "🌿 *Aide — Famille botanique*\n"
    "Corriger ou renseigner la famille d'une culture, sans livraison ni "
    "intervention en base (US-067).\n\n"
    "*Corriger la famille d'une culture :*\n"
    "  → /culture famille pâtisson Cucurbitacée\n"
    "  → /culture famille petit\\_pois Fabacée\n"
    "_La culture doit avoir déjà été dictée au moins une fois._\n\n"
    "*Corriger le délai de retour d'une famille (années) :*\n"
    "  → /culture delai\\_retour Solanacée 4\n"
    "_S'applique aussitôt à toutes les cultures de cette famille — "
    "un délai de retour est un fait de la famille, pas de chaque culture._"
)


_HELP_FICHE = (
    "🌱 *Aide — Fiche culture*\n"
    "Restituer l'essentiel d'une culture depuis le référentiel, en zéro jeton (US-164).\n\n"
    "*Consulter la fiche d'une culture :*\n"
    "  → /fiche tomate\n"
    "  → /fiche CELERI\n"
    "_Casse et accents indifférents. Une culture sans fiche connue le dit "
    "explicitement — jamais une fiche voisine forcée._"
)


_HELP_CALENDRIER = (
    "📅 *Aide — Calendrier cultural*\n"
    "Quand semer, en pépinière ou en pleine terre, et quand récolter — "
    "avec les délais de levée et de récolte, sans appel à l'IA.\n\n"
    "*Consulter le calendrier d'une culture :*\n"
    "  → /calendrier tomate\n"
    "*Lire ou choisir la zone climatique du potager :*\n"
    "  → /calendrier zone\n"
    "  → /calendrier zone méditerranéen\n"
    "*Corriger une fenêtre (pour la zone du potager) :*\n"
    "  → /calendrier fenetre tomate pepiniere février-avril\n"
    "*Corriger une durée (en jours, ou une fourchette) :*\n"
    "  → /calendrier duree courgette recolte 50-60\n"
    "  → /calendrier duree tomate plantation-recolte 60-80\n"
    "_Vos corrections ne valent que pour votre potager. Sans donnée, "
    "rien n'est inventé : la frise reste vide et la durée s'affiche en tiret._"
)


# [US-099 / CA7] Les domaines de l'aide ciblée, dans l'ordre où ils s'affichent.
# C'est la liste de référence : `/help` en dérive son sommaire, et le corpus de
# connaissance doit couvrir chacun d'eux par au moins une fiche
# (`tools/controler_aide_corpus.py`, vérifié en intégration continue).
# Les entrées de `_HELP_CONTEXTUEL` qui n'y figurent pas sont des synonymes de
# saisie (« parcelles », « plan », « famille »…), pas des domaines à couvrir.
_HELP_DOMAINES: tuple[str, ...] = (
    "parcelle", "semis", "godet", "recolte", "stock", "stats", "note", "culture", "fiche",
    "calendrier",
)


# Dérivé, jamais recopié : un domaine ajouté ci-dessus entre au sommaire sans
# qu'on ait à y penser, et le contrôle de couverture du corpus le réclame aussitôt.
_HELP_MOTS_CLES = " · ".join(_HELP_DOMAINES)


_HELP_CONTEXTUEL: dict[str, str] = {
    "parcelle":  _HELP_PARCELLE,
    "parcelles": _HELP_PARCELLE,
    "plan":      _HELP_PARCELLE,
    "semis":     _HELP_SEMIS,
    "godet":     _HELP_GODET,
    "godets":    _HELP_GODET,
    "recolte":   _HELP_RECOLTE,
    "recoltes":  _HELP_RECOLTE,
    "stock":     _HELP_STOCK,
    "stocks":    _HELP_STOCK,
    "stats":     _HELP_STATS,
    "statistiques": _HELP_STATS,
    "note":      _HELP_NOTE,
    "notes":     _HELP_NOTE,
    "culture":   _HELP_CULTURE,
    "famille":   _HELP_CULTURE,
    "fiche":     _HELP_FICHE,
    "calendrier": _HELP_CALENDRIER,  # [US-068]
}


async def cmd_version(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """[US-008] Affiche la version déployée, le SHA git et l'environnement actif."""
    app_env = os.environ.get("APP_ENV", "dev")
    texte = (
        "🌿 *Assistant Potager*\n"
        f"Version : `{_APP_VERSION}`\n"
        f"Commit  : `{_APP_GIT_SHA}`\n"
        f"Env     : `{app_env}`"
    )
    await update.message.reply_text(texte, parse_mode="Markdown")


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """[US_Aide_contextuelle_par_commande] Aide générale ou ciblée via /help [mot-clé]."""
    from unidecode import unidecode as _uni

    mot_cle = (ctx.args[0].lower().strip() if ctx.args else None)
    if mot_cle:
        mot_cle = _uni(mot_cle)  # insensible aux accents

    if mot_cle and mot_cle in _HELP_CONTEXTUEL:
        await update.message.reply_text(
            _HELP_CONTEXTUEL[mot_cle], parse_mode="Markdown"
        )
        return

    if mot_cle and mot_cle not in _HELP_CONTEXTUEL:
        await update.message.reply_text(
            f'❓ Mot-clé \"*{mot_cle}*\" non reconnu.\n\n'
            f"Mots-clés disponibles :\n  {_HELP_MOTS_CLES}\n\n"
            f"Exemple : /help parcelle",
            parse_mode="Markdown",
        )
        return

    # ── Aide générale (comportement existant / CA5) ────────────────────────────
    texte = (
        "🌿 *AIDE — Assistant Potager*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "*📝 Enregistrer une action*\n"
        "Parlez ou écrivez naturellement :\n"
        "• _\"Récolté 2 kg de tomates cerise\"_\n"
        "• _\"Planté 6 poivrons en 2 rangs\"_\n"
        "• _\"Semé carottes Nantaise rang 4\"_\n"
        "• _\"Arrosé les courgettes 30 min\"_\n"
        "• _\"Traité rosiers au savon noir\"_\n"
        "• _\"Observation : pucerons sur fèves\"_\n\n"
        "*Actions reconnues :*\n"
        "récolte · plantation · semis · repiquage\n"
        "arrosage · paillage · traitement\n"
        "désherbage · taille · tuteurage\n"
        "amendement · protection · observation\n\n"
        "*Dates :* hier · avant-hier · lundi… \"le 5 mars\"\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        # [US-171 / CA10] Le menu natif est le chemin d'accès aux commandes.
        "*⌨️ Commandes* — toutes accessibles depuis le bouton *Menu*,\n"
        "à gauche de la zone de saisie.\n"
        "/start — Accueil\n"
        "/plan — Plan d'occupation des parcelles\n"
        "/parcelle ajouter [nom] — Créer une parcelle\n"
        "/culture famille [culture] [famille] — Corriger une famille botanique\n"
        "/fiche [culture] — Fiche courte agronomique, zéro jeton\n"
        "/calendrier [culture] — Quand semer et récolter, selon votre zone\n"
        "/stats — Statistiques saison\n"
        "/historique — 10 derniers événements\n"
        "/ask — Question analytique\n"
        "/corriger — Modifier un événement\n"
        "/note — Noter une observation (guidé)\n"
        "/lier [code] — Relier ce chat à votre compte web\n"
        "/delier — Dissocier ce chat de votre compte web\n"
        "/potager — Changer de potager actif\n"
        # [US-087 / CA10] Même section que /lier et /potager : c'est de l'appartenance.
        "/rejoindre [code] — Rejoindre un potager avec un code d'invitation\n"
        "/meteo — Météo + conseil potager\n"
        "/tts\\_on · /tts\\_off — Vocal on/off\n"
        "/version — Version déployée\n"
        "/help — Cette aide\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "*💡 Aide ciblée par domaine*\n"
        f"  {_HELP_MOTS_CLES}\n"
        "Exemple : /help parcelle\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "*🔍 Exemples de questions*\n"
        "• _\"Combien de kg de tomates récoltés ?\"_\n"
        "• _\"Quand ai-je planté les courgettes ?\"_\n"
        "• _\"Bilan de ma saison de carottes\"_\n"
        "• _\"Dernier arrosage des poivrons\"_\n\n"
        "💡 _Plusieurs actions : séparez par un retour à la ligne._"
    )
    await update.message.reply_text(texte, parse_mode="Markdown")

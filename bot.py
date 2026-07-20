"""
bot.py — Bot Telegram pour l'Assistant Potager
------------------------------------------------
Fonctionnalités :
  - Message vocal → transcription Groq Whisper → parsing → PostgreSQL
  - Message texte → parsing direct → PostgreSQL
  - Récapitulatif vocal structuré après chaque enregistrement
  - /ask  → question analytique sur l'historique
  - /stats → statistiques rapides
  - /historique → derniers événements
  - /tts → afficher l'état de la synthèse vocale
  - /tts_on → activer les réponses vocales
  - /tts_off → désactiver les réponses vocales
  - Guidage conversationnel (propose les suites possibles)

Installation :
  pip install python-telegram-bot groq sqlalchemy psycopg2-binary unidecode python-dotenv gtts

Lancement :
  python bot.py
"""

import os
import json
import asyncio
import tempfile
import logging
import subprocess
from datetime import date, datetime

# ── Logging console ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"  # Affiche date + heure
)
log = logging.getLogger("potager")

# ── Suppression logs verbeux (HTTP Telegram, httpx, etc.) ──────────────────────
logging.getLogger("httpx").setLevel(logging.WARNING)  # Supprime logs HTTP
logging.getLogger("telegram").setLevel(logging.WARNING)  # Supprime logs telegram.ext
logging.getLogger("apscheduler").setLevel(logging.WARNING)  # Supprime logs scheduler

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters, ConversationHandler, CallbackQueryHandler, TypeHandler
)
from groq import Groq

from config import GROQ_API_KEY, DATABASE_URL, TELEGRAM_BOT_TOKEN, GROQ_WHISPER_MODEL
from database.db import SessionLocal, Base, engine, tenant_scope, current_potager_id
from utils.actions import normalize_action
from utils.parcelles import (
    calcul_occupation_parcelles, normalize_parcelle_name,
    find_doublon, create_parcelle, update_parcelle, get_all_parcelles,
    resolve_parcelle, rename_parcelle, supprimer_parcelle,
)
from llm.groq_client import parse_commande, repondre_question, parse_message, extract_note_fields
from utils.ia_orchestrator import build_question_context
from utils.date_utils import parse_date
from utils.tts import send_voice_reply, set_tts_enabled, is_tts_enabled
from utils.stock import calcul_stock_cultures, format_stock_ligne_telegram
from utils.meteo import save_meteo_observation, fetch_meteo, format_meteo_commentaire
from utils.deplacer import is_deplacer_request as _is_deplacer_request, extract_culture_deplacer as _extract_culture_deplacer  # [US-007]
from utils.cultures_icons import get_emoji_culture
from utils.notes import NOTE_CATEGORIES, is_note_request as _is_note_request, match_note_category  # [US-038]
from utils.culture_resolve import resolve_culture, resolve_variete  # [US-038]
from app.services.context import default_context
from app.services import evenements as svc_evenements
from app.services import parcelles as svc_parcelles
from app.services import plan as svc_plan
from app.services import questions as svc_questions

# ── Init ────────────────────────────────────────────────────────────────────────
Base.metadata.create_all(bind=engine)

# ── Version [US-008] ────────────────────────────────────────────────────────────
def _lire_version() -> str:
    """Lit le numéro de version depuis le fichier VERSION à la racine."""
    try:
        _base = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(_base, "VERSION"), encoding="utf-8") as _f:
            return _f.read().strip()
    except OSError:
        return "inconnue"

def _lire_git_sha() -> str:
    """Retourne le SHA court du commit courant via git."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5, check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "inconnu"

_APP_VERSION = _lire_version()
_APP_GIT_SHA = _lire_git_sha()

# ── Dictionnaire mots-clés → action ─────────────────────────────────────────
ACTION_KEYWORDS = {
    "arrosage"     : "arrosage",
    "arroser"      : "arrosage",
    "arrosé"       : "arrosage",
    "semis"        : "semis",
    "semé"         : "semis",
    "semer"        : "semis",
    "planté"       : "plantation",
    "planter"      : "plantation",
    "plantation"   : "plantation",
    "récolté"      : "recolte",
    "récolter"     : "recolte",
    "récolte"      : "recolte",
    "cueilli"      : "recolte",
    "ramassé"      : "recolte",
    "repiqué"      : "repiquage",
    "repiquer"     : "repiquage",
    "repiquage"    : "repiquage",
    "traité"       : "traitement",
    "traiter"      : "traitement",
    "traitement"   : "traitement",
    "désherbé"     : "desherbage",
    "désherber"    : "desherbage",
    "desherbage"   : "desherbage",
    "paillé"       : "paillage",
    "pailler"      : "paillage",
    "paillage"     : "paillage",
    "taillé"       : "taille",
    "tailler"      : "taille",
    "taille"       : "taille",
    "tuteuré"      : "tuteurage",
    "tuteurer"     : "tuteurage",
    "tuteurage"    : "tuteurage",
    "fertilisé"    : "fertilisation",
    "fertiliser"   : "fertilisation",
    "fertilisation": "fertilisation",
    "observé"      : "observation",
    "observer"     : "observation",
    "observation"  : "observation",
    "constaté"     : "observation",
    "perdu"        : "perte",
    "perte"        : "perte",
    "mort"         : "perte",
    "arraché"      : "perte",
    "crevé"        : "perte",
}

# ── Légumes connus ────────────────────────────────────────────────────────────
CULTURES_CONNUES = {
    "tomate","tomates","carotte","carottes","courgette","courgettes",
    "salade","salades","laitue","laitues","radis","poireau","poireaux",
    "oignon","oignons","ail","ails","poivron","poivrons","aubergine",
    "aubergines","concombre","concombres","haricot","haricots","petits pois",
    "pois","épinard","épinards","chou","choux","chou-fleur","choux-fleurs",
    "brocoli","brocolis","celeri","céleri","panais","navet","navets",
    "betterave","betteraves","potiron","potirons","courge","courges",
    "mûre","mûres","fraise","fraises","framboise","framboises",
    "patate","patates","pomme de terre","pommes de terre","patate douce",
    "patates douces","maïs","persil","basilic","thym","romarin",
    "poireau","poireaux","échalote","échalotes","melon","melons",
    "pastèque","tomate cerise","tomates cerises",
}

# ── Mots temporels ─────────────────────────────────────────────────────────────
from datetime import date, timedelta

TEMPORAL_MAP = {
    "hier"        : lambda: (date.today() - timedelta(days=1)).isoformat(),
    "avant-hier"  : lambda: (date.today() - timedelta(days=2)).isoformat(),
    "aujourd'hui" : lambda: date.today().isoformat(),
    "aujourd hui" : lambda: date.today().isoformat(),
    "lundi"       : lambda: _last_weekday(0),
    "mardi"       : lambda: _last_weekday(1),
    "mercredi"    : lambda: _last_weekday(2),
    "jeudi"       : lambda: _last_weekday(3),
    "vendredi"    : lambda: _last_weekday(4),
    "samedi"      : lambda: _last_weekday(5),
    "dimanche"    : lambda: _last_weekday(6),
}

def _last_weekday(weekday: int) -> str:
    today = date.today()
    days_ago = (today.weekday() - weekday) % 7 or 7
    return (today - timedelta(days=days_ago)).isoformat()

def _infer_action(texte: str) -> str | None:
    """Déduit l'action depuis le texte si Groq a retourné action=null."""
    words = texte.lower().replace(",", " ").replace(".", " ").split()
    for word in words:
        if word in ACTION_KEYWORDS:
            return ACTION_KEYWORDS[word]
    return None

def _infer_culture(texte: str) -> str | None:
    """Extrait le légume depuis le texte si Groq a retourné culture=null."""
    t = texte.lower()
    # Chercher d'abord les expressions multi-mots (plus spécifiques)
    for cult in sorted(CULTURES_CONNUES, key=len, reverse=True):
        if cult in t:
            # Retourner au singulier
            return cult.rstrip("s") if cult.endswith("s") and len(cult) > 4 else cult
    return None

def _infer_date(texte: str) -> str | None:
    """Extrait la date depuis le texte si Groq a retourné date=null."""
    t = texte.lower()
    for mot, fn in TEMPORAL_MAP.items():
        if mot in t:
            return fn()
    return None


def _normalize_items(items: list, texte_original: str = "") -> list:
    """
    Normalise la réponse Groq :
    1. Si action=null → inférence depuis le texte original
    2. Si culture/quantite sont des listes → explosion en objets séparés
    """
    normalized = []
    for item in items:
        # ── Inférence des champs null depuis le texte original ───────────────
        item = dict(item)
        if texte_original:
            if item.get("action") is None:
                inferred = _infer_action(texte_original)
                if inferred:
                    item["action"] = inferred
                    log.info(f"🔧 ACTION INFÉRÉE  : '{inferred}'")
            if item.get("culture") is None:
                action = item.get("action","")
                if action not in {"arrosage","desherbage","fertilisation"}:
                    inferred = _infer_culture(texte_original)
                    if inferred:
                        item["culture"] = inferred
                        log.info(f"🔧 CULTURE INFÉRÉE : '{inferred}'")
            if item.get("date") is None:
                # N'inférer la date que si le texte source contient un mot temporel explicite
                if texte_original and any(m in texte_original.lower() for m in TEMPORAL_MAP):
                    inferred = _infer_date(texte_original)
                    if inferred:
                        item["date"] = inferred
                        log.info(f"🔧 DATE INFÉRÉE    : '{inferred}'")

        culture  = item.get("culture")
        quantite = item.get("quantite")

        # Cas normal : culture est une string → pas de transformation
        if not isinstance(culture, list):
            normalized.append(item)
            continue

        # Cas Groq défaillant : culture est une liste
        log.warning(f"⚠️  NORMALISATION  : Groq a retourné des listes, explosion en {len(culture)} objets")
        for i, cult in enumerate(culture):
            new_item = dict(item)
            new_item["culture"] = cult
            if isinstance(quantite, list) and i < len(quantite):
                new_item["quantite"] = quantite[i]
            elif isinstance(quantite, list):
                new_item["quantite"] = None
            normalized.append(new_item)

    return normalized
groq_client = Groq(api_key=GROQ_API_KEY)

# ── Clavier principal ────────────────────────────────────────────────────────────
MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🎤 Nouvelle action vocale"), KeyboardButton("🔍 Interroger")],
        [KeyboardButton("📋 Historique"),             KeyboardButton("📊 Stats")],
        [KeyboardButton("✏️ Corriger"),               KeyboardButton("📝 Note")],
    ],
    resize_keyboard=True,
    is_persistent=True
)

AFTER_RECORD_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("➕ Autre action"), KeyboardButton("🔍 Interroger mes données")],
        [KeyboardButton("📋 Historique"),  KeyboardButton("🏠 Menu principal")],
    ],
    resize_keyboard=True
)

# ── États conversation ───────────────────────────────────────────────────────────
WAITING_ASK = 1


# ══════════════════════════════════════════════════════════════════════════════
# HANDLERS PRINCIPAUX
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Message de bienvenue."""
    prenom = update.effective_user.first_name or "jardinier"
    db = SessionLocal()
    nb = svc_evenements.compter_evenements(db, default_context())
    db.close()

    tts_etat = "🔊 activée" if is_tts_enabled() else "🔇 désactivée"

    await update.message.reply_text(
        f"🌿 *Bonjour {prenom} !*\n\n"
        f"Je suis votre assistant potager.\n"
        f"📦 *{nb} événements* enregistrés dans votre base.\n"
        f"Synthèse vocale : {tts_etat}\n\n"
        f"Envoyez-moi un *message vocal* ou *texte* pour enregistrer une action.\n"
        f"Ex : _\"Récolté 3 kg de tomates variété cerise parcelle nord\"_\n\n"
        f"Ou utilisez les boutons ci-dessous.\n"
        f"📖 Tapez /help pour l'aide en ligne.",
        parse_mode="Markdown",
        reply_markup=MENU_KEYBOARD
    )


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
    "  _Paramètres : exposition · superficie · ordre · pepiniere_\n"
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

_HELP_MOTS_CLES = "parcelle · semis · godet · recolte · stock · stats · note"

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
        "*⌨️ Commandes*\n"
        "/start — Menu principal\n"
        "/plan — Plan d'occupation des parcelles\n"
        "/parcelle ajouter [nom] — Créer une parcelle\n"
        "/stats — Statistiques saison\n"
        "/historique — 10 derniers événements\n"
        "/ask — Question analytique\n"
        "/corriger — Modifier un événement\n"
        "/note — Noter une observation (guidé)\n"
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


async def handle_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Message vocal → transcription Groq Whisper → parsing → PostgreSQL."""
    msg = await update.message.reply_text("🎤 *Transcription en cours...*", parse_mode="Markdown")

    # ── 1. Télécharger le fichier audio ────────────────────────────────────────
    voice_file = await update.message.voice.get_file()

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp_path = tmp.name
        await voice_file.download_to_drive(tmp_path)

    # ── 2. Transcrire via Groq Whisper ──────────────────────────────────────────
    try:
        with open(tmp_path, "rb") as audio:
            transcription = groq_client.audio.transcriptions.create(
                file=("message.ogg", audio),
                model=GROQ_WHISPER_MODEL,
                language="fr",
                response_format="text"
            )
        texte = transcription.strip()
        os.unlink(tmp_path)
    except Exception as e:
        os.unlink(tmp_path)
        await msg.edit_text(f"❌ Erreur transcription : {e}")
        return

    if not texte:
        await msg.edit_text("❌ Je n'ai pas compris. Réessayez en parlant plus distinctement.")
        return

    log.info(f"🎤 TRANSCRIPTION  : {texte}")

    await msg.edit_text(f"🗣 _\"{texte}\"_\n\n⏳ Analyse en cours...", parse_mode="Markdown")

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

    # ── 5. Analyse unifiée intent + parsing via Groq (single-pass) ───────────
    parsed = parse_message(texte)
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


# Mots déclencheurs de QUESTION analytique (début de phrase)
QUESTION_STARTERS = (
    "combien", "quand", "quel", "quelle", "quels", "quelles",
    "est-ce", "depuis", "total", "bilan de", "liste des",
    "montre", "donne", "rappelle", "résume", "résumé de",
    "quelle quantité", "quelle date", "à quelle", "a quelle",
    "date des", "dates des", "date de", "dates de",
    "liste de", "liste des", "historique de", "historique des",
    "dernière", "dernier", "derniers", "dernières",
    "quelles cultures", "quel traitement", "quels traitements",
    "mes récoltes", "mes semis", "mes plantations", "mes arrosages",
)

# Verbes d'action potager — ne jamais les traiter comme des questions
ACTION_VERBS = (
    "arros", "semé", "semer", "planté", "planter", "récolté", "récolter",
    "cueilli", "cueillir", "ramassé", "ramasser", "repiqué", "repiquer",
    "traité", "traiter", "désherbé", "désherber", "paillé", "pailler",
    "taillé", "tailler", "tuteurer", "tuteuré", "fertilisé", "fertiliser",
    "observé", "observer", "constaté", "constater", "mis en", "mis ",
    "posé", "appliqué", "installé", "sorti",
    "godet", "mis en godet", "mise en godet",
)

_GODETS_KEYWORDS = (
    "liste des godets", "liste godets", "quels plants en godet",
    "quels plants sont en godet", "plants en godet", "godets en attente",
    "mes godets", "voir les godets", "mes plants en godet",
)


def _is_requete_godets(texte: str) -> bool:
    """Retourne True si la phrase porte sur la consultation des godets en attente."""
    t = texte.lower().strip()
    return any(kw in t for kw in _GODETS_KEYWORDS) or (
        "godet" in t and any(w in t for w in ("liste", "quels", "combien", "voir", "etat", "état"))
    )


def _is_question(texte: str) -> bool:
    """Retourne True si la phrase ressemble à une question analytique."""
    t = texte.lower().strip()
    # Si ça commence par un verbe d'action → jamais une question
    if t.startswith(ACTION_VERBS):
        return False
    return t.startswith(QUESTION_STARTERS) or t.endswith("?")


# [US-007] _is_deplacer_request et _extract_culture_deplacer sont importées de utils/deplacer.py

# Mots-clés de navigation reconnus (avec ou sans émoji, insensible à la casse)
NAV_NOUVELLE = {"🎤 nouvelle action vocale", "➕ autre action", "autre action",
                "nouvelle action", "nouvelle", "action"}
NAV_INTERROGER = {"🔍 interroger", "🔍 interroger mes données", "interroger",
                  "interrogation", "question", "demander", "analyser",
                  "requête", "requete", "analyse", "recherche", "cherche"}
NAV_HISTORIQUE = {"📋 historique", "historique", "histo", "journal",
                  "historiques", "derniers", "dernier", "liste", "log"}
NAV_STATS      = {"📊 stats", "📊 statistiques", "stats", "statistiques", "stat",
                  "statistique", "chiffres", "résumé", "resume", "bilan",
                  "données", "donnees"}
NAV_MENU       = {"🏠 menu principal", "menu", "accueil", "home", "retour"}
NAV_CORRIGER   = {"✏️ corriger", "corriger", "modifier", "correction", "corriger le dernier",
                  "modifier le dernier", "annuler le dernier", "corriger une saisie",
                  "modifier une saisie", "/corriger",
                  "corrigé", "corrigée", "corrigés", "corrigées",
                  "modifié", "modifiée", "modifiés", "modifiées",
                  "une correction", "faire une correction", "une modification",
                  "je veux corriger", "je veux modifier"}
NAV_SUPPRIMER  = {"🗑 supprimer", "supprimer", "supprimer le dernier", "annuler",
                  "effacer", "effacer le dernier", "delete",
                  "supprimé", "supprimée", "supprimés", "effacé", "effacée"}
# [US-038] Déclencheurs du flux guidé de note/observation
NAV_NOTE       = {"📝 note", "note", "notes", "une note", "ajouter une note",
                  "prendre une note", "/note"}

# ── Intent classification via Groq ─────────────────────────────────────────
# Intents possibles retournés par classify_intent()
INTENTS = {
    "STATS",        # statistiques, bilan, résumé
    "HISTORIQUE",   # journal, historique, derniers événements
    "INTERROGER",   # question, analyser, demander
    "CORRIGER",     # corriger, modifier, changer un enregistrement
    "SUPPRIMER",    # supprimer, effacer, annuler le dernier
    "MENU",         # retour accueil, menu
    "NOUVELLE",     # nouvelle action, autre chose
    "ACTION",       # action potager à enregistrer (récolte, semis, arrosage...)
    "PLAN",         # [US_Plan_occupation_parcelles / CA9] plan d'occupation parcelles
    "DEPLACER",     # [US-007] réassocier une culture à une nouvelle parcelle
}

_CLASSIFY_PROMPT = """Tu es un assistant potager spécialisé dans la classification de messages.
L'utilisateur t'envoie un message (vocal transcrit ou texte).

CLASSE CE MESSAGE EN UNE SEULE CATÉGORIE :

🧮 STATS       : veut voir des statistiques, bilan, résumé, chiffres totaux, OU demande le détail d'une culture
  MOTS-CLÉS : stats, statistiques, bilan, résumé, détail, affiche le détail, montre le détail, infos sur
  Exemples :
    ✅ "stats", "statistiques", "bilan de saison"
    ✅ "affiche le détail de la culture courgette"
    ✅ "affiche moi le détail de la courgette"
    ✅ "montre le détail sur les tomates"
    ✅ "détail courgette"
    ✅ "infos sur mes poivrons"
    ✅ "donne moi les stats de la tomate"

📖 HISTORIQUE  : veut voir l'historique, le journal, les derniers événements
  Exemples : "historique", "histo", "journal", "derniers événements", "liste des actions"

❓ INTERROGER  : pose une QUESTION ou demande d'AFFICHER/MONTRER des données
  MOTS-CLÉS : combien, quand, quel, affiche, afficher, montre, montrer, voir, liste, consulter, détail, detail, historique de, date de
  PRONOMS DE POSSESSION : "mes X", "mon X", "ma X", "les X de", "la X de" → INTERROGER car l'utilisateur demande à VOIR ses données
  Exemples :
    ✅ "Combien de kg de tomates ai-je récolté cette saison ?"
    ✅ "Quand ai-je planté mes courgettes ?"
    ✅ "Afficher les récoltes de carotte variété nantaise"
    ✅ "Affiche le détail sur la culture courgette"
    ✅ "Montre-moi les semis de radis"
    ✅ "Date des traitements sur les poivrons"
    ✅ "Historique des arrosages courgettes"
    ✅ "Montrer mes semis de radis"
    ✅ "Voir les dernières récoltes"
    ✅ "Quel est le total de mes semis ?"
    ✅ "Consulter les pertes de cette saison"
    ✅ "Liste des plantations de mai"
    ✅ "Combien ai-je perdu de plants ?"
    ✅ "Quels légumes ai-je arrosés cette semaine ?"
    ✅ "Détail des récoltes de courgettes"
    ✅ "Donne-moi les infos sur mes tomates"
    ✅ "mes récoltes de blette" (pronom possessif → c'est une INTERROGATION)
    ✅ "mes plantations de ce mois" (pronom possessif → INTERROGATION)
    ✅ "récolte de blette ce mois-ci" ("récolte" est un NOM ici, pas un verbe → INTERROGATION)
    ✅ "dernière récolte de blette" ("dernière" indique une consultation → INTERROGATION)
    ✅ "dernière plantation de tomates ?" (demande d'info → INTERROGATION)
    ✅ "semis de radis cette semaine" ("semis" est un NOM → INTERROGATION si pas de verbe d'action)
    ❌ "J'ai récolté 2 kg de tomates" (c'est une ACTION, pas une INTERROGATION)
    ❌ "Semé des carottes hier" (c'est une ACTION)

✏️ CORRIGER    : veut corriger, modifier, changer un enregistrement existant
  Exemples : "corriger", "modifier", "changer", "rectifier"

🗑️ SUPPRIMER   : veut supprimer ou effacer un enregistrement
  Exemples : "supprimer", "effacer", "annuler", "delete"

🏠 MENU        : veut revenir au menu, accueil, annuler, retour
  Exemples : "menu", "accueil", "retour", "home", "annuler"

🎤 NOUVELLE    : veut saisir une nouvelle action (après en avoir enregistré une)
  Exemples : "nouvelle action", "autre action", "ajouter une autre"

🌱 ACTION      : décrit une action potager RÉELLEMENT RÉALISÉE à enregistrer
  Verbes d'action : récolté, semé, planté, arrosé, paillé, traité, désherbé, taillé, tuteuré, repiqué, fertilisé, perdu
  Exemples :
    ✅ "J'ai récolté 2 kg de tomates"
    ✅ "Semé des carottes hier"
    ✅ "Planté 12 plants de poivrons en 3 rangs"
    ✅ "Arrosé les courgettes 30 minutes"
    ✅ "Récolte 500g de carotte nantaise"
    ✅ "Paillé la parcelle nord"
    ✅ "Repiqué 20 plants de laitue"
    ✅ "Traité les tomates contre le mildiou"
    ✅ "Tuteuré les haricots"
    ✅ "Perdu 5 plants de courgettes au gel"
    ❌ "Combien de tomates ?" (c'est une INTERROGATION, pas une ACTION)
    ❌ "Afficher mes récoltes" (c'est une INTERROGATION)

🗺️ PLAN        : veut voir le plan d'occupation des parcelles
  Exemples : "plan du potager", "plan parcelle nord", "montre-moi le plan"

🔀 DEPLACER    : veut réassocier une culture à une nouvelle parcelle (associer, déplacer, changer de parcelle)
  MOTS-CLÉS : associer, déplacer, changer de parcelle, rattacher, affecter, réassocier, déménager
  Exemples :
    ✅ "j'ai besoin d'associer ma zone tomate sur une nouvelle parcelle"
    ✅ "déplacer mes carottes sur la parcelle nord"
    ✅ "changer la parcelle de mes courgettes"
    ✅ "réassocier mes tomates cerise à la parcelle serre"
    ✅ "affecter mes poivrons à une autre parcelle"
    ✅ "rattacher mes aubergines à la parcelle est"
    ✅ "déménager mes salades vers la parcelle sud"
    ❌ "planté des tomates dans la parcelle nord" (c'est une ACTION, pas un déplacement)
    ❌ "j'ai déplacé un pot" (pas une culture de parcelle)

RÈGLE IMPORTANTE #1 :
Si le message contient "affiche", "afficher", "montre", "montrer", "voir", "liste", "consulter", "détail", "combien", "quand", "quel"
→ c'est INTERROGER ou HISTORIQUE, JAMAIS ACTION (même sans "?" en fin de phrase).

RÈGLE IMPORTANTE #2 :
Si le message COMMENCE par un verbe d'action au PASSÉ COMPOSÉ (récolté, semé, planté, arrosé, paillé, traité...)
ET SANS "?" → c'est ACTION, jamais INTERROGER.
ATTENTION : "récolte" (sans accent final, forme nominale) ≠ "récolté" (participe passé).
"récolte de blette" = NOM → INTERROGER. "récolté des blettes" = VERBE PASSÉ → ACTION.

RÈGLE IMPORTANTE #3 :
Si le message COMMENCE par un pronom possessif (mes, mon, ma, les, nos, leurs, des...)
suivi d'un nom de culture ou d'action → c'est INTERROGER (l'utilisateur consulte ses données).
Exemples : "mes récoltes de blette" → INTERROGER, "mes plantations" → INTERROGER.

RÈGLE IMPORTANTE #4 :
Si le message contient "dernière", "dernier", "première", "premier", "ce mois-ci", "cette semaine"
SANS verbe d'action au passé → c'est INTERROGER (consultation de données existantes).

Message utilisateur : "{texte}"

Réponds avec UN SEUL MOT en majuscules parmi :
STATS | HISTORIQUE | INTERROGER | CORRIGER | SUPPRIMER | MENU | NOUVELLE | ACTION | PLAN | DEPLACER

Réponse :"""

def classify_intent(texte: str) -> str:
    """Utilise Groq pour classer l'intention du message en un intent canonique."""
    from groq import Groq
    from config import GROQ_API_KEY, GROQ_MODEL
    client = Groq(api_key=GROQ_API_KEY)
    try:
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": _CLASSIFY_PROMPT.format(texte=texte)}],
            temperature=0.0,
            max_tokens=10,
        )
        intent = resp.choices[0].message.content.strip().upper().rstrip(".!? ")
        if intent not in INTENTS:
            log.warning(f"⚠️ INTENT INCONNU  : '{intent}' → fallback ACTION")
            intent = "ACTION"
        log.info(f"🧭 INTENT          : '{texte}' → {intent}")
        return intent
    except Exception as e:
        log.error(f"Erreur classify_intent : {e}")
        return "ACTION"  # fallback sûr


def _extract_stats_culture(texte: str) -> str | None:
    """
    [US_Stats_detail_par_variete / CA8]
    Extrait la culture depuis une phrase vocale type 'stats tomate' ou
    'affiche le détail de la culture courgette'.

    Exemples reconnus :
      "stats tomate"                              → "tomate"
      "statistiques de la tomate"                → "tomate"
      "affiche le détail de la culture courgette" → "courgette"
      "affiche moi le détail de la courgette"    → "courgette"
      "montre le détail sur les tomates"         → "tomates"
      "détail courgette"                         → "courgette"
      "infos sur mes poivrons"                   → "poivrons"
      "stats" seul                               → None
    """
    import re
    t = texte.lower().strip()

    # Pattern 1 — "stats/statistiques [de [la/les/du]] <culture>"
    m = re.match(
        r'^(?:stats?|statistiques?)\s+(?:de\s+(?:la\s+|les?\s+|des?\s+)?|du\s+)?(\w+)$',
        t,
    )
    if m:
        return m.group(1)

    # Pattern 2 — "affiche/montre [moi] le détail [de [la culture/les/du]] <culture>"
    m = re.search(
        r'(?:affiche?(?:r)?|montre?(?:r)?)\s+(?:moi\s+)?(?:le\s+)?d[eé]tail\s+'
        r'(?:de\s+(?:la\s+culture\s+|la\s+|les?\s+|des?\s+|du\s+)?'
        r'|sur\s+(?:la\s+culture\s+|les?\s+cultures?\s+|la\s+|les?\s+)?)?(\w+)',
        t,
    )
    if m:
        return m.group(1)

    # Pattern 3 — "détail <culture>" ou "détail de [la] <culture>"
    m = re.match(
        r'^d[eé]tail\s+(?:de\s+(?:la\s+|les?\s+|des?\s+|du\s+)?)?(\w+)$',
        t,
    )
    if m:
        return m.group(1)

    # Pattern 4 — "infos sur [mes/les/la] <culture>"
    m = re.search(r'infos?\s+sur\s+(?:mes?\s+|les?\s+|la\s+)?(\w+)', t)
    if m:
        return m.group(1)

    # Pattern 5 — "donne moi les stats de [la] <culture>"
    m = re.search(
        r'(?:donne(?:r)?(?:\s+moi)?)\s+(?:les?\s+)?stats?\s+(?:de\s+(?:la\s+|les?\s+|des?\s+)?)?(\w+)',
        t,
    )
    if m:
        return m.group(1)

    return None


def _extract_plan_parcelle(texte: str) -> str | None:
    """
    [US_Plan_occupation_parcelles / CA9]
    Extrait le nom de parcelle depuis une phrase vocale type 'plan parcelle nord'.

    Exemples reconnus :
      "plan du potager"     → None  (vue globale)
      "plan parcelle nord"  → "nord"
      "plan nord"           → "nord"
    """
    m = re.search(
        r'plan\s+(?:parcelle\s+)?(\w+)',
        texte.lower().strip(),
    )
    if m:
        mot = m.group(1)
        # Ignorer les mots génériques qui ne sont pas des noms de parcelle
        if mot in {"du", "des", "le", "la", "les", "potager", "jardin"}:
            return None
        return mot
    return None


async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Message texte → parsing direct ou commande de navigation."""
    texte_raw = update.message.text.strip()
    texte     = texte_raw.lower()  # comparaison insensible à la casse
    log.info(f"💬 MESSAGE TEXTE  : {texte_raw}")

    # [US-036 CA10] Nombre de pieds en attente (récolte végétative pesée) ?
    user_id = update.effective_user.id
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
            await _parse_and_save(update, pending["texte"], pre_parsed_items=items)
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
            await _parse_and_save(update, pending["texte"], pre_parsed_items=items)
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

    # ── PRIORITÉ 3 : mots-clés correction/suppression
    if texte in NAV_SUPPRIMER or any(texte.startswith(k) for k in ["supprimer", "effacer", "annuler"]):
        await _corr_annuler_dernier(update, ctx)
        return
    if texte in NAV_CORRIGER or any(texte.startswith(k) for k in ["corriger", "modifier"]):
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

    # ── PRIORITÉ 4 : détection automatique question
    if _is_question(texte_raw):
        log.info(f"❓ QUESTION AUTO   : détectée → reroutage vers _ask_question")
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


# ── PARSING MULTI-LIGNES ─────────────────────────────────────────────────────────
async def _parse_multi(update, lignes: list, msg=None):
    """Traite chaque ligne séparément → chaque événement a son propre texte_original et sa propre date."""
    log.info(f"📋 MULTI-LIGNES    : {len(lignes)} phrases à traiter séparément")
    total_saved = []

    for i, ligne in enumerate(lignes, 1):
        log.info(f"  [{i}/{len(lignes)}] Traitement : {ligne}")
        try:
            items = parse_commande(ligne)
            items = _normalize_items(items, ligne)
            from utils.validation import strip_culture_hallucinee
            for j, item in enumerate(items):
                culture_avant = item.get("culture")
                items[j] = strip_culture_hallucinee(item, ligne)
                if culture_avant and items[j].get("culture") is None:
                    log.warning(f"  [{i}] ⚠️ CULTURE HALLUCINÉE : '{culture_avant}' absente du texte → retirée | ligne={ligne!r}")
        except Exception as e:
            log.error(f"  [{i}] Erreur parsing : {e}")
            continue

        first = items[0] if items else {}
        if not (first.get("action") or first.get("culture") or first.get("quantite")):
            log.warning(f"  [{i}] JSON sans action ni culture — ignoré : {ligne}")
            continue

        db = SessionLocal()
        try:
            for parsed in items:
                event = svc_evenements.creer_evenement_ligne(db, default_context(), parsed, ligne)
                log.info(f"  💾 DB SAVE : id={event.id} | action={event.type_action} | culture={event.culture} | parcelle_id={event.parcelle_id} | date={event.date}")
                total_saved.append((parsed, event.id))
        except Exception as e:
            db.rollback()
            log.error(f"  [{i}] Erreur DB : {e}")
        finally:
            db.close()

    # Récapitulatif global
    if not total_saved:
        if msg: await msg.edit_text("❌ Aucune action reconnue.")
        return

    lines_out = [f"✅ *{len(total_saved)} action(s) enregistrée(s)*\n"]
    for parsed, eid in total_saved:
        cult  = parsed.get("culture") or "—"
        act   = parsed.get("action")  or "?"
        d     = parsed.get("date")    or "aujourd'hui"
        lines_out.append(f"• #{eid} *{act}* — {cult} _{d}_")

    recap = "\n".join(lines_out)
    if msg:   await msg.edit_text(recap, parse_mode="Markdown")
    else:     await update.message.reply_text(recap, parse_mode="Markdown")
    await update.message.reply_text(
        "_Que voulez-vous faire ensuite ?_",
        parse_mode="Markdown",
        reply_markup=AFTER_RECORD_KEYBOARD
    )
    refreshed = SessionLocal()
    try:
        nb = svc_evenements.compter_evenements(refreshed, default_context())
        # pas de reply ici, juste log
        log.info(f"📦 TOTAL BASE     : {nb} événements")
    finally:
        refreshed.close()


# ── [US-019] SÉLECTION VARIÉTÉ MISE EN GODET ────────────────────────────────────
# Stocke les items mise_en_godet en attente de sélection de variété {user_id: {parsed, texte, ts}}
_GODET_PENDING: dict[int, dict] = {}
_GODET_TIMEOUT = 60  # secondes

# [vendu/perte_godet] Disambiguation perte jardin vs pépinière {user_id: {item, texte, godets, ts}}
_PERTE_PENDING: dict[int, dict] = {}
_PERTE_TIMEOUT = 90  # secondes

# [US-021] Actions en attente de confirmation {user_id: {items, texte, ts}}
_ACTION_PENDING: dict[int, dict] = {}
_ACTION_TIMEOUT = 60  # secondes

# [US-038] Notes en attente de confirmation {user_id: {categorie, fields, texte, ts}}
_NOTE_PENDING: dict[int, dict] = {}
_NOTE_TIMEOUT = 60  # secondes

_UNITES_SEMIS_VALIDES: frozenset[str] = frozenset({"graine", "graines", "plant", "plants"})

# [US-037] La normalisation d'unité de semis ("graines"|"pieds"|"m²") vit désormais
# dans app/services/evenements.py (seul appelant : creer_evenement_confirme).

_RECOLTE_PENDING: dict[int, dict] = {}
_RECOLTE_TIMEOUT = 60  # secondes

_VENDU_PENDING: dict[int, dict] = {}
_VENDU_TIMEOUT  = 60  # secondes

_QUANTITE_PENDING: dict[int, dict] = {}
_QUANTITE_TIMEOUT = 60  # secondes

# [US-036 CA10] Récolte végétative pesée sans nombre de pieds → clarification {user_id: {items, texte, ts}}
_RECOLTE_PIECES_PENDING: dict[int, dict] = {}
_RECOLTE_PIECES_TIMEOUT = 60  # secondes

# [US-037 CA7] Semis d'une culture absente de CultureConfig → clarification végétatif/reproducteur
_SEMIS_CULTURE_PENDING: dict[int, dict] = {}
_SEMIS_CULTURE_TIMEOUT = 90  # secondes


async def _save_godet_item(update: Update, parsed: dict, texte: str) -> None:
    """Sauvegarde un item mise_en_godet et affiche le récapitulatif."""
    db = SessionLocal()
    try:
        event = svc_evenements.creer_evenement_godet(db, default_context(), parsed, texte)
    except Exception as e:
        db.rollback()
        await update.effective_message.reply_text(f"❌ Erreur base de données : {e}")
        return
    finally:
        db.close()

    recap = _build_recap(parsed, event.id)
    await update.effective_message.reply_text(recap, parse_mode="Markdown", reply_markup=AFTER_RECORD_KEYBOARD)
    await send_voice_reply(update, _build_recap_tts(parsed))


async def _recolte_variete_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback inline — sélection de variété pour une récolte ambiguë."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    pending = _RECOLTE_PENDING.pop(user_id, None)

    if pending is None:
        await query.edit_message_text("⏱ Action expirée. Veuillez re-saisir votre récolte.")
        return

    import time as _time_mod
    if _time_mod.time() - pending["ts"] > _RECOLTE_TIMEOUT:
        await query.edit_message_text("⏱ *Action annulée* (timeout 60 s). Veuillez re-saisir.", parse_mode="Markdown")
        return

    data = query.data  # recolte_var:{variete} | recolte_cancel

    if data == "recolte_cancel":
        await query.edit_message_text("❌ Récolte annulée.", reply_markup=None)
        return

    if data.startswith("recolte_var:"):
        variete = data[len("recolte_var:"):]
        item    = pending["item"]
        texte   = pending["texte"]
        item["variete"] = variete
        log.info("[recolte_cb] Variété '%s' sélectionnée pour '%s' — user_id=%s", variete, item.get("culture"), user_id)

        await query.edit_message_text(
            f"✅ Variété *{variete}* sélectionnée.",
            parse_mode="Markdown",
            reply_markup=None,
        )
        # Relancer le flux de confirmation avec la variété renseignée
        await _parse_and_save(update, texte, pre_parsed_items=[item])


async def _vendu_variete_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback inline — sélection de variété godet pour une vente ambiguë."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    pending = _VENDU_PENDING.pop(user_id, None)

    if pending is None:
        await query.edit_message_text("⏱ Action expirée. Veuillez re-saisir votre vente.")
        return

    import time as _time_mod
    if _time_mod.time() - pending["ts"] > _VENDU_TIMEOUT:
        await query.edit_message_text("⏱ *Action annulée* (timeout 60 s). Veuillez re-saisir.", parse_mode="Markdown")
        return

    data = query.data  # vendu_var:{variete} | vendu_cancel

    if data == "vendu_cancel":
        await query.edit_message_text("❌ Vente annulée.", reply_markup=None)
        return

    if data.startswith("vendu_var:"):
        variete = data[len("vendu_var:"):]
        variete = variete if variete != "__none__" else None
        item    = pending["item"]
        texte   = pending["texte"]
        item["variete"] = variete
        log.info("[vendu_cb] Variété '%s' sélectionnée pour '%s' — user_id=%s", variete, item.get("culture"), user_id)
        await query.edit_message_text(
            f"✅ Variété *{variete or 'non précisée'}* sélectionnée.",
            parse_mode="Markdown",
            reply_markup=None,
        )
        # _parse_and_save utilise update.message (None dans un callback) → utiliser _save_perte_item
        # qui utilise update.effective_message, compatible callback ET message
        await _save_perte_item(update, item, texte)


async def _save_perte_item(update: Update, item: dict, texte: str) -> None:
    """
    Sauvegarde directe d'un item perte ou perte_godet depuis un callback inline.

    N'utilise PAS _parse_and_save (qui nécessite update.message).
    Utilise update.effective_message qui fonctionne dans les contextes callback ET message.
    """
    db = SessionLocal()
    try:
        event = svc_evenements.creer_evenement_perte(db, default_context(), item, texte)
    except Exception as e:
        db.rollback()
        await update.effective_message.reply_text(f"❌ Erreur base de données : {e}")
        return
    finally:
        db.close()

    recap = _build_recap(item, event.id)
    await update.effective_message.reply_text(recap, parse_mode="Markdown", reply_markup=AFTER_RECORD_KEYBOARD)
    await send_voice_reply(update, _build_recap_tts(item))


async def _godet_variete_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """[US-019] Callback inline — sélection de variété pour une mise en godet ambiguë."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    pending = _GODET_PENDING.pop(user_id, None)

    if pending is None:
        await query.edit_message_text("⏱ Action expirée. Veuillez re-saisir votre mise en godet.")
        return

    import time
    if time.time() - pending["ts"] > _GODET_TIMEOUT:
        await query.edit_message_text("⏱ *Action annulée* (timeout 60 s). Veuillez re-saisir.", parse_mode="Markdown")
        return

    data = query.data  # godet_var:{variete} | godet_confirm | godet_cancel | godet_force

    if data == "godet_cancel":
        await query.edit_message_text("❌ Mise en godet annulée.", reply_markup=None)
        return

    parsed = pending["parsed"]
    texte  = pending["texte"]

    if data.startswith("godet_var:"):
        variete = data[len("godet_var:"):]
        parsed["variete"] = variete if variete != "__none__" else None
    elif data in ("godet_confirm", "godet_force"):
        pass  # variété déjà dans parsed (CA2) ou aucune (CA3)

    await query.edit_message_text(
        f"✅ Variété confirmée : *{parsed.get('variete') or 'non précisée'}*",
        parse_mode="Markdown",
        reply_markup=None,
    )
    await _save_godet_item(update, parsed, texte)


# ── [vendu/perte_godet] CALLBACK DISAMBIGUATION PERTE ────────────────────────────

def _stock_variete_jardin(v: dict) -> int:
    """Calcule le stock actif d'une variété au jardin."""
    plants = (v.get("plants_plantes") or 0) - (v.get("plants_perdus") or 0)
    if v.get("type_organe") != "reproducteur":
        plants -= (v.get("recoltes_total") or 0)
    return max(0, int(plants))


async def _handle_perte_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Flux disambiguation perte en 2 étapes :
      Étape 1 : potager ou pépinière ? (toujours en premier)
      Étape 2 : quelle variété ? (uniquement si plusieurs variétés actives dans ce contexte)

    Callbacks :
      perte_source:jardin     → sélection contexte jardin
      perte_source:pepiniere  → sélection contexte pépinière
      perte_var_j:{variete}   → variété jardin choisie → save perte
      perte_var_p:{variete}   → variété pépinière choisie → save perte_godet
      perte_cancel            → annulation
    """
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    pending = _PERTE_PENDING.get(user_id)

    if pending is None:
        await query.edit_message_text("⏱ Action expirée. Veuillez re-saisir.")
        return

    import time as _time
    if _time.time() - pending["ts"] > _PERTE_TIMEOUT:
        _PERTE_PENDING.pop(user_id, None)
        await query.edit_message_text("⏱ *Action expirée* (timeout). Veuillez re-saisir.", parse_mode="Markdown")
        return

    data    = query.data
    item    = pending["item"]
    texte   = pending["texte"]
    culture = item.get("culture", "")
    qte     = item.get("quantite", "?")

    if data == "perte_cancel":
        _PERTE_PENDING.pop(user_id, None)
        await query.edit_message_text("❌ Annulé.", reply_markup=None)
        return

    # ── ÉTAPE 1 : contexte choisi → maintenant sélection variété ────────────

    if data == "perte_source:jardin":
        jardin_varietes = [v for v in pending.get("jardin_varietes", []) if _stock_variete_jardin(v) > 0]

        if len(jardin_varietes) == 0:
            # Aucune variété active au jardin → enregistrer sans variété
            _PERTE_PENDING.pop(user_id, None)
            item["action"] = "perte"
            await query.edit_message_text("🌿 Enregistrement perte au potager...", reply_markup=None)
            await _save_perte_item(update, item, texte)

        elif len(jardin_varietes) == 1:
            _PERTE_PENDING.pop(user_id, None)
            item["action"]  = "perte"
            item["variete"] = jardin_varietes[0]["variete"]
            var_lbl = item["variete"] or "non précisée"
            await query.edit_message_text(f"🌿 *{culture} {var_lbl}* — enregistrement...", parse_mode="Markdown", reply_markup=None)
            await _save_perte_item(update, item, texte)

        else:
            # Plusieurs variétés actives au jardin → demander laquelle
            buttons = []
            for v in jardin_varietes:
                var   = v["variete"] or "non précisée"
                stock = _stock_variete_jardin(v)
                cb    = v["variete"] if v["variete"] else "__none__"
                buttons.append([InlineKeyboardButton(f"🌿 {var} ({stock} plants actifs)", callback_data=f"perte_var_j:{cb}")])
            buttons.append([InlineKeyboardButton("❌ Annuler", callback_data="perte_cancel")])
            await query.edit_message_text(
                f"🌿 Quelle variété de *{_md(culture)}* au potager ?",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        return

    if data == "perte_source:pepiniere":
        godets_actifs = pending.get("godets", [])

        if len(godets_actifs) == 0:
            _PERTE_PENDING.pop(user_id, None)
            item["action"] = "perte_godet"
            item.pop("parcelle", None)
            await query.edit_message_text("🪴 Enregistrement perte pépinière...", reply_markup=None)
            await _save_perte_item(update, item, texte)

        elif len(godets_actifs) == 1:
            _PERTE_PENDING.pop(user_id, None)
            item["action"]  = "perte_godet"
            item["variete"] = godets_actifs[0]["variete"]
            item.pop("parcelle", None)
            var_lbl = item["variete"] or "non précisée"
            await query.edit_message_text(f"🪴 *{culture} {var_lbl}* — enregistrement...", parse_mode="Markdown", reply_markup=None)
            await _save_perte_item(update, item, texte)

        else:
            # Plusieurs variétés en godet → demander laquelle
            buttons = []
            for g in godets_actifs:
                var = g["variete"] or "non précisée"
                cb  = g["variete"] if g["variete"] else "__none__"
                buttons.append([InlineKeyboardButton(f"🪴 {var} ({g['stock_residuel_godet']} en godet)", callback_data=f"perte_var_p:{cb}")])
            buttons.append([InlineKeyboardButton("❌ Annuler", callback_data="perte_cancel")])
            await query.edit_message_text(
                f"🪴 Quelle variété de *{_md(culture)}* en pépinière ?",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        return

    # ── ÉTAPE 2 : variété choisie ────────────────────────────────────────────

    if data.startswith("perte_var_j:"):
        _PERTE_PENDING.pop(user_id, None)
        variete         = data[len("perte_var_j:"):]
        variete         = variete if variete != "__none__" else None
        item["action"]  = "perte"
        item["variete"] = variete
        var_lbl         = variete or "non précisée"
        log.info(f"[perte] Jardin variété={var_lbl}")
        await query.edit_message_text(f"🌿 *{culture} {var_lbl}* — enregistrement perte potager...", parse_mode="Markdown", reply_markup=None)
        await _save_perte_item(update, item, texte)
        return

    if data.startswith("perte_var_p:"):
        _PERTE_PENDING.pop(user_id, None)
        variete         = data[len("perte_var_p:"):]
        variete         = variete if variete != "__none__" else None
        item["action"]  = "perte_godet"
        item["variete"] = variete
        item.pop("parcelle", None)
        var_lbl         = variete or "non précisée"
        log.info(f"[perte] Pépinière variété={var_lbl}")
        await query.edit_message_text(f"🪴 *{culture} {var_lbl}* — enregistrement perte pépinière...", parse_mode="Markdown", reply_markup=None)
        await _save_perte_item(update, item, texte)
        return


# ── [US-021] CONFIRMATION AVANT ENREGISTREMENT ──────────────────────────────────

# Actions qui créent la présence d'une culture (source) → liste complète des parcelles
_ACTIONS_SOURCE = {"plantation", "semis", "mise_en_godet", "vendu", "perte_godet"}


    # [US-037] La condition de "localisation" d'une culture (_cond_localisation_culture)
    # vit désormais dans app/services/evenements.py, seul module qui construit encore
    # des requêtes sur Evenement/Parcelle pour cette logique.


def _get_parcelles_avec_culture(db, culture: str, variete: str | None) -> list:
    """Retourne les parcelles distinctes où cette culture a été plantée ou semée en pleine terre."""
    return svc_parcelles.parcelles_avec_culture(db, default_context(), culture, variete)


def _build_action_summary(items: list[dict]) -> str:
    """Construit le résumé lisible d'une ou plusieurs actions avant confirmation."""
    if len(items) == 1:
        p = items[0]
        lines = ["📝 *Je vais enregistrer :*\n"]
        action = p.get("action") or "action"
        lines.append(f"🌱 Action : *{action}*")
        if p.get("culture"):   lines.append(f"🥬 Culture : *{p['culture']}*")
        if p.get("variete"):   lines.append(f"🏷 Variété : *{p['variete']}*")
        if p.get("quantite") is not None:
            qte   = p["quantite"]
            unite = p.get("unite") or ""
            rang  = p.get("rang")
            if rang:
                lines.append(f"⚖️ Quantité : *{int(qte)} {unite}/rang × {rang} rangs*")
            else:
                lines.append(f"⚖️ Quantité : *{qte} {unite}*".strip())
        if p.get("parcelle"):
            lines.append(f"📍 Parcelle : *{p['parcelle']}*")
        elif p.get("_parcelle_demandee") is not True:
            lines.append("📍 Parcelle : ❓ non détectée")
        if p.get("date"):      lines.append(f"📅 Date : *{p['date']}*")
        if p.get("commentaire"): lines.append(f"📝 Note : *{p['commentaire']}*")
        if p.get("_avertissement_coherence"):
            lines.append(f"\n{p['_avertissement_coherence']}")
        lines.append("\nC'est correct ?")
        return "\n".join(lines)
    else:
        lines = [f"📝 *Je vais enregistrer {len(items)} actions :*\n"]
        avertissements = []
        for i, p in enumerate(items, 1):
            action  = p.get("action") or "action"
            culture = p.get("culture") or "?"
            qte_str = f" — {p['quantite']} {p.get('unite') or ''}".strip() if p.get("quantite") is not None else ""
            lines.append(f"{i}. *{action}* {culture}{qte_str}")
            if p.get("_avertissement_coherence"):
                avertissements.append(f"{i}. {p['_avertissement_coherence']}")
        if avertissements:
            lines.append("")
            lines.extend(avertissements)
        lines.append("\nC'est correct ?")
        return "\n".join(lines)


async def _do_save_items(update: Update, items: list[dict], texte: str, msg=None) -> None:
    """[US-021] Sauvegarde effective en base après confirmation utilisateur."""
    db = SessionLocal()
    saved_items = []
    try:
        for parsed in items:
            # [US-049] La résolution reste ici (nécessaire pour construire l'Evenement
            # avec le bon parcelle_id), mais le BLOCAGE si la parcelle ne résout à rien
            # est désormais décidé uniquement par la validation centrale à l'intérieur
            # de creer_evenement_confirme (valider_evenement) — plus de duplication de
            # la règle "parcelle inconnue" à cet endroit.
            nom_parcelle = parsed.get("parcelle")
            parcelle_obj = resolve_parcelle(db, nom_parcelle) if nom_parcelle else None

            try:
                # [fix bug id=351] mise_en_godet doit toujours passer par
                # creer_evenement_godet (parcelle_id forcé à None + auto-link au
                # semis d'origine), jamais par creer_evenement_confirme — même
                # quand la variété est déjà connue (seul cas jusqu'ici routé vers
                # la fonction dédiée, via l'interception _GODET_PENDING plus haut).
                if normalize_action(parsed.get("action")) == "mise_en_godet":
                    event = svc_evenements.creer_evenement_godet(db, default_context(), parsed, texte)
                else:
                    event = svc_evenements.creer_evenement_confirme(db, default_context(), parsed, texte, parcelle_obj)
            except svc_evenements.ParcelleInconnueError as e:
                db.rollback()
                log.warning(f"⚠️ PARCELLE INCONNUE : {nom_parcelle!r} — sauvegarde bloquée")
                err_msg = f"❌ {e}\n\nCréez-la d'abord avec : `/parcelle ajouter {nom_parcelle}`"
                if msg:  await msg.edit_text(err_msg, parse_mode="Markdown")
                else:    await update.effective_message.reply_text(err_msg, parse_mode="Markdown", reply_markup=MENU_KEYBOARD)
                return
            except svc_evenements.EvenementInvalideError as e:
                # [US-049] Filet de sécurité final — la validation centrale a rejeté
                # l'événement au moment même de l'écriture. Les contrôles amont dans
                # _parse_and_save couvrent déjà l'UX normale ; ce cas ne devrait se
                # produire que si l'état du potager a changé entre la confirmation et
                # l'écriture, ou via un chemin qui aurait échappé aux contrôles amont.
                db.rollback()
                log.warning(f"❌ ÉVÉNEMENT INVALIDE (écriture) : {e} | texte={texte!r}")
                err_msg = f"❌ {e}"
                if msg:  await msg.edit_text(err_msg, parse_mode="Markdown")
                else:    await update.effective_message.reply_text(err_msg, parse_mode="Markdown", reply_markup=MENU_KEYBOARD)
                return
            saved_items.append((parsed, event.id))
    except Exception as e:
        db.rollback()
        await update.effective_message.reply_text(f"❌ Erreur base de données : {e}")
        return
    finally:
        db.close()

    if len(saved_items) == 1:
        parsed, event_id = saved_items[0]
        recap = _build_recap(parsed, event_id)
        if msg:  await msg.edit_text(recap, parse_mode="Markdown")
        else:    await update.effective_message.reply_text(recap, parse_mode="Markdown")
    else:
        lines_out = [f"✅ *{len(saved_items)} actions enregistrées !*\n"]
        for parsed, event_id in saved_items:
            cult  = parsed.get("culture") or "?"
            qte   = str(parsed["quantite"]) + " " + (parsed.get("unite") or "") if parsed.get("quantite") else ""
            d     = parsed.get("date") or str(date.today())
            lines_out.append(f"• *{cult}* {qte} — _{d}_ ✔")
        recap_multi = "\n".join(lines_out)
        if msg:  await msg.edit_text(recap_multi, parse_mode="Markdown")
        else:    await update.effective_message.reply_text(recap_multi, parse_mode="Markdown")

    await update.effective_message.reply_text(
        "_Que voulez-vous faire ensuite ?_",
        parse_mode="Markdown",
        reply_markup=AFTER_RECORD_KEYBOARD,
    )

    if len(saved_items) == 1:
        parsed, _ = saved_items[0]
        await send_voice_reply(update, _build_recap_tts(parsed))


async def _semis_organe_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """[US-037 CA7] Callback inline — végétatif/reproducteur pour une culture inconnue lors d'un semis."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    data    = query.data  # semis_organe:végétatif | semis_organe:reproducteur | semis_organe_cancel

    if data == "semis_organe_cancel":
        _SEMIS_CULTURE_PENDING.pop(user_id, None)
        log.info(f"[US-037 CA7] Semis annulé (culture inconnue) — user_id={user_id}")
        await query.edit_message_text("❌ Semis annulé.", reply_markup=None)
        return

    pending = _SEMIS_CULTURE_PENDING.pop(user_id, None)
    if pending is None:
        await query.edit_message_text("⏱ Action expirée. Veuillez re-saisir votre semis.")
        return

    import time as _time_mod
    if _time_mod.time() - pending["ts"] > _SEMIS_CULTURE_TIMEOUT:
        await query.edit_message_text(f"⏱ *Confirmation expirée ({_SEMIS_CULTURE_TIMEOUT} s), semis annulé.*", parse_mode="Markdown")
        return

    type_organe = data[len("semis_organe:"):]
    items       = pending["items"]
    culture     = (items[0].get("culture") or "").strip()

    db = SessionLocal()
    try:
        tenant_ctx = default_context()
        cfg = svc_parcelles.get_culture_config(db, tenant_ctx, culture)
        if cfg is None:
            svc_parcelles.creer_culture_config(db, tenant_ctx, culture, type_organe)
            log.info(f"[US-037 CA7] CultureConfig créée : '{culture}' → {type_organe}")
    finally:
        db.close()

    await query.edit_message_text(
        f"✅ *{culture.capitalize()}* enregistrée comme culture *{type_organe}*.",
        parse_mode="Markdown",
        reply_markup=None,
    )
    await _parse_and_save(update, pending["texte"], pre_parsed_items=items)


async def _action_confirm_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """[US-021] Callback inline — sélection parcelle, confirmation ou annulation."""
    import time
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    data    = query.data

    # Annulation valide à toutes les étapes
    if data == "action_cancel":
        _ACTION_PENDING.pop(user_id, None)
        log.info(f"[US-021] Action annulée — user_id={user_id}")
        await query.edit_message_text("❌ Action annulée.", reply_markup=None)
        return

    pending = _ACTION_PENDING.get(user_id)  # ne pas pop avant confirmation finale

    if pending is None:
        await query.edit_message_text("⏱ Action expirée. Veuillez re-saisir votre commande.")
        return

    if time.time() - pending["ts"] > _ACTION_TIMEOUT:
        _ACTION_PENDING.pop(user_id, None)
        await query.edit_message_text("⏱ *Confirmation expirée (60 s), action annulée.*", parse_mode="Markdown")
        return

    # [CA9/CA10] Sélection de parcelle
    if data.startswith("action_parcelle:") or data == "action_parcelle_none":
        parcelle_nom = None if data == "action_parcelle_none" else data[len("action_parcelle:"):]
        for item in pending["items"]:
            item["parcelle"] = parcelle_nom
            item.pop("_parcelle_demandee", None)
        log.info(f"[US-021 CA9] Parcelle sélectionnée : {parcelle_nom!r} — user_id={user_id}")
        summary = _build_action_summary(pending["items"])
        buttons = [[
            InlineKeyboardButton("✅ Confirmer", callback_data="action_confirm"),
            InlineKeyboardButton("❌ Annuler",   callback_data="action_cancel"),
        ]]
        await query.edit_message_text(summary, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
        return

    # action_confirm → sauvegarde effective
    _ACTION_PENDING.pop(user_id, None)
    await query.edit_message_text("⏳ Enregistrement en cours...", reply_markup=None)
    log.info(f"[US-021] Confirmation reçue — user_id={user_id}, {len(pending['items'])} item(s)")
    await _do_save_items(update, pending["items"], pending["texte"])


# ── [US-038] SAISIE GUIDÉE DE NOTES/OBSERVATIONS ────────────────────────────────
_NOTE_CATEGORY_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton(NOTE_CATEGORIES["observation"]["label"]), KeyboardButton(NOTE_CATEGORIES["maladie"]["label"])],
        [KeyboardButton(NOTE_CATEGORIES["arrosage"]["label"]),    KeyboardButton(NOTE_CATEGORIES["paillage"]["label"])],
        [KeyboardButton("❌ Annuler")],
    ],
    resize_keyboard=True,
)

_NOTE_CANCEL_KEYWORDS = {"❌ annuler", "annuler"}


def _note_reset(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    ctx.user_data.pop('mode', None)
    ctx.user_data.pop('note_category', None)


async def _note_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """[US-038 / CA1, CA2] Démarre le flux guidé : affiche le menu de catégories."""
    _note_reset(ctx)
    ctx.user_data['mode'] = 'note_category'
    await update.effective_message.reply_text(
        "📝 *Nouvelle note*\n\nQuelle catégorie souhaites-tu noter ?",
        parse_mode="Markdown",
        reply_markup=_NOTE_CATEGORY_KEYBOARD,
    )


async def _note_category_selected(update: Update, ctx: ContextTypes.DEFAULT_TYPE, texte: str) -> None:
    """[US-038 / CA3] Étape 2 — la catégorie est choisie, on pose la question guidée."""
    if texte.strip().lower() in _NOTE_CANCEL_KEYWORDS:
        _note_reset(ctx)
        await update.effective_message.reply_text("↩️ Note annulée.", reply_markup=MENU_KEYBOARD)
        return

    categorie = match_note_category(texte)
    if categorie is None:
        await update.effective_message.reply_text(
            "❓ Catégorie non reconnue. Choisis un des boutons ci-dessous :",
            reply_markup=_NOTE_CATEGORY_KEYBOARD,
        )
        return

    ctx.user_data['note_category'] = categorie
    ctx.user_data['mode'] = 'note_details'
    log.info(f"[US-038] Catégorie sélectionnée : {categorie}")
    await update.effective_message.reply_text(
        NOTE_CATEGORIES[categorie]["question"],
        reply_markup=ReplyKeyboardMarkup([["❌ Annuler"]], resize_keyboard=True),
    )


def _build_note_summary(categorie: str, fields: dict) -> str:
    label = NOTE_CATEGORIES[categorie]["label"]
    lines = [f"{label}\n"]
    if fields.get("culture"):
        lines.append(f"🥬 Culture : *{fields['culture']}*")
    if fields.get("variete"):
        lines.append(f"🏷 Variété : *{fields['variete']}*")
    if fields.get("parcelle"):
        lines.append(f"📍 Parcelle : *{fields['parcelle']}*")
    lines.append(f"📝 Constat : *{fields['constat']}*")
    if fields.get("traitement"):
        lines.append(f"🧪 Traitement / matériau : *{fields['traitement']}*")
    if fields.get("duree_minutes"):
        lines.append(f"⏱ Durée constatée : *{fields['duree_minutes']} min*")
    lines.append("\nC'est correct ?")
    return "\n".join(lines)


async def _note_details_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE, texte: str) -> None:
    """[US-038 / CA4, CA5] Étape 3 — extraction Groq des champs + récapitulatif."""
    import time

    if texte.strip().lower() in _NOTE_CANCEL_KEYWORDS:
        _note_reset(ctx)
        await update.effective_message.reply_text("↩️ Note annulée.", reply_markup=MENU_KEYBOARD)
        return

    categorie = ctx.user_data.get('note_category')
    if categorie is None:
        # État incohérent (ex: redémarrage du bot en plein flux) → on repart proprement
        await _note_start(update, ctx)
        return

    fields = extract_note_fields(categorie, texte)

    # [feedback] Résout culture/variete vers les valeurs canoniques déjà en base
    # (Groq peut renvoyer "haricot"/"nain" alors que la BDD a "haricot"/"vert nain Contender")
    if fields.get("culture"):
        db = SessionLocal()
        try:
            culture_resolue = resolve_culture(db, fields["culture"])
            if culture_resolue != fields["culture"]:
                log.info(f"[US-038] Culture résolue : '{fields['culture']}' → '{culture_resolue}'")
            fields["culture"] = culture_resolue
            if fields.get("variete"):
                variete_resolue = resolve_variete(db, culture_resolue, fields["variete"])
                if variete_resolue != fields["variete"]:
                    log.info(f"[US-038] Variété résolue : '{fields['variete']}' → '{variete_resolue}'")
                fields["variete"] = variete_resolue
        finally:
            db.close()

    _note_reset(ctx)

    user_id = update.effective_user.id
    _NOTE_PENDING[user_id] = {
        "categorie": categorie,
        "fields": fields,
        "texte": texte,
        "ts": time.time(),
    }

    summary = _build_note_summary(categorie, fields)
    buttons = [[
        InlineKeyboardButton("✅ Confirmer", callback_data="note_confirm"),
        InlineKeyboardButton("❌ Annuler",   callback_data="note_cancel"),
    ]]
    await update.effective_message.reply_text(
        summary, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons)
    )


async def _save_note_event(update: Update, pending: dict) -> None:
    """[US-038 / CA6, CA7] Sauvegarde l'Evenement observation — aucune colonne ajoutée."""
    categorie = pending["categorie"]
    fields    = pending["fields"]
    label     = NOTE_CATEGORIES[categorie]["label"].split(" ", 1)[-1]  # retire l'emoji

    db = SessionLocal()
    try:
        event = svc_evenements.creer_evenement_observation(db, default_context(), fields, pending["texte"], label)
    except Exception as e:
        db.rollback()
        await update.effective_message.reply_text(f"❌ Erreur base de données : {e}")
        return
    finally:
        db.close()

    await update.effective_message.reply_text(
        f"✅ *Note enregistrée* — {NOTE_CATEGORIES[categorie]['label']}",
        parse_mode="Markdown",
    )
    await update.effective_message.reply_text(
        "_Que voulez-vous faire ensuite ?_",
        parse_mode="Markdown",
        reply_markup=AFTER_RECORD_KEYBOARD,
    )


async def _note_confirm_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """[US-038 / CA5, CA9] Callback inline — confirmation ou annulation de la note."""
    import time
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    data    = query.data

    if data == "note_cancel":
        _NOTE_PENDING.pop(user_id, None)
        log.info(f"[US-038] Note annulée — user_id={user_id}")
        await query.edit_message_text("❌ Note annulée.", reply_markup=None)
        return

    pending = _NOTE_PENDING.get(user_id)
    if pending is None:
        await query.edit_message_text("⏱ Note expirée. Veuillez recommencer avec /note.")
        return

    if time.time() - pending["ts"] > _NOTE_TIMEOUT:
        _NOTE_PENDING.pop(user_id, None)
        await query.edit_message_text(f"⏱ *Confirmation expirée ({_NOTE_TIMEOUT} s), note annulée.*", parse_mode="Markdown")
        return

    _NOTE_PENDING.pop(user_id, None)
    await query.edit_message_text("⏳ Enregistrement en cours...", reply_markup=None)
    await _save_note_event(update, pending)


# ── PARSING + SAUVEGARDE ────────────────────────────────────────────────────────
async def _parse_and_save(update: Update, texte: str, msg=None, pre_parsed_items=None):
    """Parse le texte → liste d'événements → PostgreSQL → récapitulatif.

    pre_parsed_items : items déjà extraits par parse_message() (single-pass).
    Si None, appel de secours à parse_commande() (bulk, multi-lignes, fallback).
    """
    # Gestion des callback queries : update.message peut être None
    message = update.message or (update.callback_query.message if update.callback_query else None)

    try:
        if pre_parsed_items is not None:
            items = pre_parsed_items   # déjà parsé — pas de 2e appel LLM
        else:
            items = parse_commande(texte)   # fallback : parse_commande classique
    except Exception as e:
        log.error(f"❌ ERREUR PARSING  : {e}")
        txt = f"❌ Erreur parsing : {e}\n\nEssayez de reformuler votre action."
        if msg: await msg.edit_text(txt)
        else:   await message.reply_text(txt)
        return

    log.info(f"🤖 GROQ PARSING   : {json.dumps(items, ensure_ascii=False)}")
    items = _normalize_items(items, texte)
    if len(items) > 1:
        log.info(f"📦 ITEMS NORMALISÉS: {len(items)} événements à sauvegarder")

    # [US-011 bis] Retire toute culture hallucinée (absente du texte source) avant validation
    from utils.validation import strip_culture_hallucinee
    for i, item in enumerate(items):
        culture_avant = item.get("culture")
        items[i] = strip_culture_hallucinee(item, texte)
        if culture_avant and items[i].get("culture") is None:
            log.warning(f"⚠️ CULTURE HALLUCINÉE : '{culture_avant}' absente du texte → retirée | texte={texte!r}")

    # [fix doublons orthographiques] Résout culture/variété vers les valeurs canoniques
    # déjà en base (ex: "creme"/"cerise" dictés → variété déjà connue), pour ce pipeline
    # de dictée directe. Jusqu'ici cette canonisation n'existait que dans le flux "notes"
    # (_note_details_received) — le flux normal enregistrait la variété brute telle
    # quelle, fragmentant silencieusement les variétés en base au moindre écart d'orthographe.
    if any(item.get("culture") for item in items):
        db_resolve = SessionLocal()
        try:
            for item in items:
                if not item.get("culture"):
                    continue
                culture_resolue = resolve_culture(db_resolve, item["culture"])
                if culture_resolue != item["culture"]:
                    log.info(f"[resolve] Culture '{item['culture']}' → '{culture_resolue}'")
                item["culture"] = culture_resolue
                if item.get("variete"):
                    variete_resolue = resolve_variete(db_resolve, culture_resolue, item["variete"])
                    if variete_resolue != item["variete"]:
                        log.info(f"[resolve] Variété '{item['variete']}' → '{variete_resolue}'")
                    item["variete"] = variete_resolue
        finally:
            db_resolve.close()

    # [US-011] Validation post-parsing — filtre les hallucinations Groq en Python pur
    from utils.validation import validate_parsed_action
    validated = []
    action_none_detected = False
    for item in items:
        is_valid, reason = validate_parsed_action(item, texte)
        if not is_valid:
            log.warning(f"❌ VALIDATION US011: {reason} | item={json.dumps(item, ensure_ascii=False)}")
            if "manquante" in reason or "None" in reason:
                action_none_detected = True
        else:
            validated.append(item)
    items = validated

    if not items:
        if action_none_detected:
            # Groq a parsé une question comme action → reroutage vers le flux interrogation
            log.info(f"❓ REROUTAGE US011 : action=None détectée → _ask_question('{texte}')")
            await _ask_question(update, texte)
        else:
            await message.reply_text("❌ Aucune action détectée.")
        return

    # Cas JSON sans action ni culture → phrase non reconnue comme action potager
    first = items[0] if items else {}
    if not (first.get("action") or first.get("culture") or first.get("quantite")):
        log.warning("⚠️  JSON SANS ACTION NI CULTURE : phrase non reconnue, pas de sauvegarde")
        await message.reply_text(
            "🤔 Je n'ai pas compris cette action.\n\n"
            "• Pour enregistrer : _\"Récolté 2 kg de tomates hier\"_\n"
            "• Pour interroger  : _\"Combien de tomates ai-je récolté ?\"_",
            parse_mode="Markdown",
            reply_markup=MENU_KEYBOARD
        )
        return

    # Cas ambiguïté rang/quantité détectée par Groq
    if len(items) == 1 and items[0].get("action") == "AMBIGUE":
        hint = items[0].get("commentaire", "précisez le nombre de plants par rang et le nombre de rangs")
        await message.reply_text(
            "🤔 *Précision nécessaire*\n\n"
            "Je n'ai pas bien compris la quantité et les rangs.\n\n"
            "Reformulez en précisant :\n"
            f"_{hint}_\n\n"
            "Exemple : _planter 10 choux-fleurs par rang sur 3 rangs parcelle nord_",
            parse_mode="Markdown",
            reply_markup=MENU_KEYBOARD
        )
        return

    # [US-049] Garde-fou "culture jamais plantée" — appelle la validation centrale
    # unique (app/services/evenements.py::valider_evenement), qui reste de toute
    # façon l'autorité finale au moment de l'écriture (défense en profondeur) ;
    # l'appel ici n'est qu'un raccourci UX pour bloquer AVANT d'afficher un
    # récapitulatif de confirmation voué à échouer. Contrôle appliqué à CHAQUE item,
    # pas seulement au premier — c'est l'ancienne restriction `len(items) == 1` qui
    # avait laissé passer une culture hallucinée quand Groq segmente une phrase
    # multi-culture ("cueilli 2 kilos de cerise, tomates, nord") en plusieurs items
    # dans la même réponse JSON.
    from app.services.evenements import valider_evenement as _valider_evenement, CultureInconnueError
    db_chk = SessionLocal()
    try:
        for _item_chk in items:
            if not _item_chk.get("culture"):
                continue
            try:
                _valider_evenement(
                    db_chk, default_context(),
                    action=_item_chk.get("action"), culture=_item_chk["culture"],
                    variete=_item_chk.get("variete"), parcelle=None,
                )
            except CultureInconnueError as e:
                log.warning(f"❌ CULTURE JAMAIS PLANTÉE : '{_item_chk['culture']}' — action bloquée | texte={texte!r}")
                err = (
                    f"❌ {e}\n\n"
                    f"Vérifiez le nom, ou enregistrez d'abord un semis/plantation de *{_item_chk['culture']}*."
                )
                if msg: await msg.edit_text(err, parse_mode="Markdown")
                else:   await message.reply_text(err, parse_mode="Markdown", reply_markup=MENU_KEYBOARD)
                return
    finally:
        db_chk.close()

    # [US-037 / CA7] Semis d'une culture inconnue de CultureConfig — demander
    # à l'utilisateur si elle est végétative ou reproductive avant d'enregistrer.
    if (
        len(items) == 1
        and normalize_action(items[0].get("action")) == "semis"
        and items[0].get("culture")
    ):
        culture_semis_ca7 = items[0]["culture"].strip()
        from utils.stock import get_type_organe as _get_type_organe_ca7
        db_tmp = SessionLocal()
        try:
            type_organe_connu = _get_type_organe_ca7(db_tmp, culture_semis_ca7)
        finally:
            db_tmp.close()

        if type_organe_connu is None:
            import time as _time_ca7
            user_id = update.effective_user.id
            _SEMIS_CULTURE_PENDING[user_id] = {"items": items, "texte": texte, "ts": _time_ca7.time()}
            buttons = [
                [InlineKeyboardButton("🌱 Végétative (récolte = plante entière)", callback_data="semis_organe:végétatif")],
                [InlineKeyboardButton("🔁 Reproductive (récoltes multiples)", callback_data="semis_organe:reproducteur")],
                [InlineKeyboardButton("❌ Annuler", callback_data="semis_organe_cancel")],
            ]
            await message.reply_text(
                f"🤔 *{culture_semis_ca7.capitalize()}* est une culture inconnue.\n\n"
                "Est-elle *végétative* (on récolte la plante entière, ex: carotte, salade) "
                "ou *reproductive* (on cueille plusieurs fois, ex: tomate, haricot) ?",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            log.info(
                "[US-037 CA7] Culture '%s' inconnue de CultureConfig — clarification demandée user_id=%s",
                culture_semis_ca7, user_id,
            )
            return

    # [US-019 / CA1-CA3] Interception mise_en_godet sans variété — sélection assistée
    import time as _time
    if (
        len(items) == 1
        and normalize_action(items[0].get("action")) == "mise_en_godet"
        and not items[0].get("variete")
    ):
        parsed_godet = items[0]
        culture      = parsed_godet.get("culture", "")
        user_id      = update.effective_user.id

        from utils.stock import calcul_semis_par_culture
        db_tmp = SessionLocal()
        try:
            semis_var = [
                s for s in calcul_semis_par_culture(db_tmp, culture)
                if s["stock_residuel"] > 0
            ]
        finally:
            db_tmp.close()

        _GODET_PENDING[user_id] = {"parsed": parsed_godet, "texte": texte, "ts": _time.time()}

        if len(semis_var) > 1:
            # CA1 — plusieurs variétés disponibles → menu inline
            buttons = []
            for s in semis_var:
                var_label = s["variete"] or "non précisée"
                cb_key    = s["variete"] if s["variete"] else "__none__"
                buttons.append([InlineKeyboardButton(
                    f"{var_label} ({s['stock_residuel']} restantes)",
                    callback_data=f"godet_var:{cb_key}"
                )])
            buttons.append([InlineKeyboardButton("❌ Annuler", callback_data="godet_cancel")])
            await message.reply_text(
                f"🪴 Pour quelle variété de *{culture}* ?",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        elif len(semis_var) == 1:
            # CA2 — une seule variété → confirmation automatique
            s   = semis_var[0]
            var = s["variete"] or "non précisée"
            parsed_godet["variete"] = s["variete"]
            buttons = [
                [InlineKeyboardButton("✅ Confirmer", callback_data="godet_confirm"),
                 InlineKeyboardButton("❌ Annuler",   callback_data="godet_cancel")]
            ]
            await message.reply_text(
                f"🪴 Je suppose la variété *{var}* (seule en pépinière, {s['stock_residuel']} restantes). Confirmer ?",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        else:
            # CA3 — aucun semis actif pour cette culture
            buttons = [
                [InlineKeyboardButton("✅ Enregistrer quand même", callback_data="godet_force"),
                 InlineKeyboardButton("❌ Annuler",                callback_data="godet_cancel")]
            ]
            await message.reply_text(
                f"⚠️ Aucun semis de *{culture}* en pépinière. Voulez-vous quand même enregistrer cette mise en godet ?",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        return  # attente callback — pas de sauvegarde immédiate

    # ── Disambiguation récolte — variété + parcelle ──────────────────────────────
    if (
        len(items) == 1
        and normalize_action(items[0].get("action")) == "recolte"
        and items[0].get("culture")
        and not items[0].get("variete")
    ):
        item_r  = items[0]
        culture = item_r["culture"]
        user_id = update.effective_user.id

        from utils.stock import calcul_stock_par_variete
        db_tmp = SessionLocal()
        try:
            varietes_stock = [
                v for v in calcul_stock_par_variete(db_tmp, culture)
                if (v["plants_plantes"] - v["plants_perdus"]) > 0
                and v["variete"] != "Variété non précisée"
            ]
        finally:
            db_tmp.close()

        if len(varietes_stock) > 1:
            # Plusieurs variétés en stock → menu inline
            _RECOLTE_PENDING[user_id] = {"item": item_r, "texte": texte, "ts": _time.time()}
            buttons = [
                [InlineKeyboardButton(
                    f"🌿 {v['variete']} ({int(v['plants_plantes'] - v['plants_perdus'])} plants)",
                    callback_data=f"recolte_var:{v['variete']}"
                )]
                for v in varietes_stock
            ]
            buttons.append([InlineKeyboardButton("❌ Annuler", callback_data="recolte_cancel")])
            await message.reply_text(
                f"🥬 *{culture.capitalize()}* — Quelle variété récoltez-vous ?",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            log.info("[recolte] %d variétés pour '%s' — menu inline user_id=%s", len(varietes_stock), culture, user_id)
            return

        elif len(varietes_stock) == 1:
            # Une seule variété → auto-remplir silencieusement
            item_r["variete"] = varietes_stock[0]["variete"]
            log.info("[recolte] Variété '%s' auto-déduite pour '%s'", item_r["variete"], culture)
            # pas de return → continue vers la confirmation normale

    # ── [US-036 CA10] Récolte végétative pesée sans nombre de pieds — clarification ──
    if (
        len(items) == 1
        and normalize_action(items[0].get("action")) == "recolte"
        and items[0].get("culture")
        and (items[0].get("unite") or "").lower() in {"kg", "g", "mg"}
    ):
        culture_p = items[0]["culture"]
        from utils.stock import get_type_organe
        db_tmp = SessionLocal()
        try:
            type_organe_p = get_type_organe(db_tmp, culture_p)
        finally:
            db_tmp.close()

        if type_organe_p == "végétatif":
            user_id = update.effective_user.id
            _RECOLTE_PIECES_PENDING[user_id] = {"items": items, "texte": texte, "ts": _time.time()}
            log.info("[US-036 CA10] Poids sans nb de pieds pour '%s' (végétatif) — user_id=%s", culture_p, user_id)
            await message.reply_text(
                f"🌿 Combien de pieds de *{culture_p}* avez-vous récoltés au total ? "
                "_(le poids sera conservé séparément pour le rendement)_",
                parse_mode="Markdown",
            )
            return

    # ── Disambiguation vendu — variété godet ─────────────────────────────────────
    if (
        len(items) == 1
        and normalize_action(items[0].get("action")) == "vendu"
        and items[0].get("culture")
        and not items[0].get("variete")
    ):
        item_v  = items[0]
        culture = item_v["culture"]
        user_id = update.effective_user.id

        from utils.stock import calcul_godets_par_culture as _cgpc_v
        db_tmp = SessionLocal()
        try:
            godets_dispo = _cgpc_v(db_tmp, culture)
        finally:
            db_tmp.close()

        if len(godets_dispo) > 1:
            # Plusieurs variétés en godet → menu inline
            _VENDU_PENDING[user_id] = {"item": item_v, "texte": texte, "ts": _time.time()}
            buttons = [
                [InlineKeyboardButton(
                    f"🪴 {g['variete'] or 'non précisée'} ({g['stock_residuel_godet']} en godet)",
                    callback_data=f"vendu_var:{g['variete'] if g['variete'] else '__none__'}",
                )]
                for g in godets_dispo
            ]
            buttons.append([InlineKeyboardButton("❌ Annuler", callback_data="vendu_cancel")])
            await message.reply_text(
                f"🪴 *{culture.capitalize()}* — Quelle variété vendez-vous ?",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            log.info("[vendu] %d variétés godet pour '%s' — menu inline user_id=%s", len(godets_dispo), culture, user_id)
            return

        elif len(godets_dispo) == 1:
            # Une seule variété → auto-remplir silencieusement
            item_v["variete"] = godets_dispo[0]["variete"]
            log.info("[vendu] Variété '%s' auto-déduite depuis godet pour '%s'", item_v["variete"], culture)
            # pas de return → continue vers la confirmation

    # ── [vendu/perte_godet] Disambiguation perte — intelligence contextuelle ──────
    if (
        len(items) == 1
        and normalize_action(items[0].get("action")) == "perte"
        and items[0].get("culture")
    ):
        item    = items[0]
        culture = item.get("culture", "")
        variete = item.get("variete")

        # ── 1. Détection du contexte dans le texte brut ─────────────────────
        from unidecode import unidecode as _ud
        texte_n = _ud(texte.lower())
        _MOTS_JARDIN    = {"potager", "jardin", "pleine terre", "en terre", "sol"}
        _MOTS_PEPINIERE = {"pepiniere", "godet", "en godet", "semis"}
        ctx_jardin    = any(m in texte_n for m in _MOTS_JARDIN)
        ctx_pepiniere = any(m in texte_n for m in _MOTS_PEPINIERE)

        # ── 2. Nettoyage : si Groq a mis un mot-clé de contexte dans variete ─
        if variete:
            v_n = _ud(variete.lower())
            if any(m in v_n for m in _MOTS_JARDIN | _MOTS_PEPINIERE):
                if any(m in v_n for m in _MOTS_PEPINIERE): ctx_pepiniere = True
                if any(m in v_n for m in _MOTS_JARDIN):    ctx_jardin    = True
                variete         = None
                item["variete"] = None

        # ── 3. Chargement des stocks disponibles ────────────────────────────
        from utils.stock import calcul_godets_par_culture as _cgpc, calcul_stock_par_variete as _csv
        from utils.parcelles import levenshtein_distance as _lev
        db_perte = SessionLocal()
        try:
            godets_dispo    = _cgpc(db_perte, culture)
            varietes_jardin = _csv(db_perte, culture)
        finally:
            db_perte.close()

        jardin_actif  = [v for v in varietes_jardin if _stock_variete_jardin(v) > 0]

        # ── 4. Fuzzy match variété sur les candidats disponibles ─────────────
        def _fuzzy_variete(needle: str, candidates: list[str]) -> str | None:
            """Retourne le candidat le plus proche (Levenshtein ≤ 2), ou None."""
            needle_n = _ud(needle.lower())
            best, best_d = None, 99
            for c in candidates:
                if not c: continue
                d = _lev(needle_n, _ud(c.lower()))
                if d < best_d:
                    best, best_d = c, d
            return best if best_d <= 2 else None

        var_jardin_matched    = None
        var_pepiniere_matched = None
        if variete:
            var_jardin_matched    = _fuzzy_variete(variete, [v.get("variete") or "" for v in jardin_actif])
            var_pepiniere_matched = _fuzzy_variete(variete, [g.get("variete") or "" for g in godets_dispo])

        # ── 5. Décision : contexte connu → court-circuit des menus ──────────
        ctx_connu = ctx_jardin or ctx_pepiniere

        if ctx_jardin and not ctx_pepiniere:
            # Contexte jardin clair
            item["action"] = "perte"
            if var_jardin_matched:
                # Variété reconnue (fuzzy) → sauvegarder directement
                item["variete"] = var_jardin_matched
                log.info(f"[perte-auto] Jardin, variété fuzzy '{variete}'→'{var_jardin_matched}'")
                await _save_perte_item(update, item, texte)
                return
            elif len(jardin_actif) == 1:
                item["variete"] = jardin_actif[0]["variete"]
                log.info(f"[perte-auto] Jardin, variété unique '{item['variete']}'")
                await _save_perte_item(update, item, texte)
                return
            elif len(jardin_actif) > 1:
                # Afficher sélection variété jardin directement (sans question source)
                import time as _time
                _PERTE_PENDING[update.effective_user.id] = {
                    "item": item, "texte": texte,
                    "godets": godets_dispo, "jardin_varietes": varietes_jardin,
                    "ts": _time.time(),
                }
                buttons = []
                for v in jardin_actif:
                    var   = v["variete"] or "non précisée"
                    stock = _stock_variete_jardin(v)
                    cb    = v["variete"] if v["variete"] else "__none__"
                    buttons.append([InlineKeyboardButton(f"🌿 {var} ({stock} plants actifs)", callback_data=f"perte_var_j:{cb}")])
                buttons.append([InlineKeyboardButton("❌ Annuler", callback_data="perte_cancel")])
                await update.message.reply_text(
                    f"🌿 Quelle variété de *{_md(culture)}* au potager ?",
                    parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons),
                )
                return
            # Aucune variété active au jardin → sauvegarder sans variété
            log.info(f"[perte-auto] Jardin, aucune variété active → save sans variété")
            await _save_perte_item(update, item, texte)
            return

        if ctx_pepiniere and not ctx_jardin:
            # Contexte pépinière clair
            item["action"] = "perte_godet"
            item.pop("parcelle", None)
            if var_pepiniere_matched:
                item["variete"] = var_pepiniere_matched
                log.info(f"[perte-auto] Pépinière, variété fuzzy '{variete}'→'{var_pepiniere_matched}'")
                await _save_perte_item(update, item, texte)
                return
            elif len(godets_dispo) == 1:
                item["variete"] = godets_dispo[0]["variete"]
                log.info(f"[perte-auto] Pépinière, variété unique '{item['variete']}'")
                await _save_perte_item(update, item, texte)
                return
            elif len(godets_dispo) > 1:
                import time as _time
                _PERTE_PENDING[update.effective_user.id] = {
                    "item": item, "texte": texte,
                    "godets": godets_dispo, "jardin_varietes": varietes_jardin,
                    "ts": _time.time(),
                }
                buttons = []
                for g in godets_dispo:
                    var = g["variete"] or "non précisée"
                    cb  = g["variete"] if g["variete"] else "__none__"
                    buttons.append([InlineKeyboardButton(f"🪴 {var} ({g['stock_residuel_godet']} en godet)", callback_data=f"perte_var_p:{cb}")])
                buttons.append([InlineKeyboardButton("❌ Annuler", callback_data="perte_cancel")])
                await update.message.reply_text(
                    f"🪴 Quelle variété de *{_md(culture)}* en pépinière ?",
                    parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons),
                )
                return
            # Aucun godet → sauvegarder sans variété
            log.info(f"[perte-auto] Pépinière, aucune variété en godet → save sans variété")
            await _save_perte_item(update, item, texte)
            return

        # ── 6. Contexte non connu : menu source si godet en stock ───────────
        import time as _time
        godets_pertinents = godets_dispo
        if godets_pertinents:
            user_id = update.effective_user.id
            _PERTE_PENDING[user_id] = {
                "item":           item,
                "texte":          texte,
                "godets":         godets_pertinents,
                "jardin_varietes": varietes_jardin,
                "ts":             _time.time(),
            }
            culture_md    = _md(culture)
            qte           = item.get("quantite", "?")
            nb_godets     = len(godets_pertinents)
            nb_jardin     = len(jardin_actif)
            lbl_jardin    = f"🌿 Au potager ({nb_jardin} variété{'s' if nb_jardin > 1 else ''} active{'s' if nb_jardin > 1 else ''})" if nb_jardin > 1 else "🌿 Au potager"
            lbl_pepiniere = f"🪴 Pépinière ({nb_godets} variété{'s' if nb_godets > 1 else ''} en godet)" if nb_godets > 1 else f"🪴 Pépinière ({godets_pertinents[0]['stock_residuel_godet']} en godet)"
            buttons = [
                [InlineKeyboardButton(lbl_jardin,    callback_data="perte_source:jardin")],
                [InlineKeyboardButton(lbl_pepiniere, callback_data="perte_source:pepiniere")],
                [InlineKeyboardButton("❌ Annuler",   callback_data="perte_cancel")],
            ]
            var_lbl = f" *{variete}*" if variete else ""
            await update.message.reply_text(
                f"🤔 Perte de *{qte} {culture_md}*{var_lbl} — au potager ou en pépinière ?",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            return  # attente callback

        # ── 7. Aucun godet, aucun contexte → disambiguation variété jardin ───
        # (même logique que récolte : auto-remplir si unique, menu si plusieurs)
        if not godets_pertinents and jardin_actif and not variete:
            if len(jardin_actif) == 1:
                item["variete"] = jardin_actif[0]["variete"]
                log.info("[perte-auto] Aucun godet, variété unique jardin '%s' → auto-remplie", item["variete"])
                # pas de return → continue vers la confirmation
            else:
                # Plusieurs variétés au jardin → menu inline
                _PERTE_PENDING[update.effective_user.id] = {
                    "item": item, "texte": texte,
                    "godets": [], "jardin_varietes": varietes_jardin,
                    "ts": _time.time(),
                }
                buttons_var = [
                    [InlineKeyboardButton(
                        f"🌿 {v['variete'] or 'non précisée'} ({_stock_variete_jardin(v)} plants actifs)",
                        callback_data=f"perte_var_j:{v['variete'] if v['variete'] else '__none__'}",
                    )]
                    for v in jardin_actif
                ]
                buttons_var.append([InlineKeyboardButton("❌ Annuler", callback_data="perte_cancel")])
                await update.message.reply_text(
                    f"🌿 Quelle variété de *{_md(culture)}* avez-vous perdu ?",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(buttons_var),
                )
                log.info("[perte] %d variétés jardin pour '%s', aucun godet — menu inline user_id=%s",
                         len(jardin_actif), culture, update.effective_user.id)
                return

    # [US-021] Confirmation avant enregistrement
    import time as _time
    user_id = update.effective_user.id
    _ACTION_PENDING[user_id] = {"items": items, "texte": texte, "ts": _time.time()}

    # Actions pépinière → jamais de parcelle (godets non localisés dans une parcelle)
    # [fix bug id=351] mise_en_godet ajouté — un godet n'est jamais rattaché à une
    # parcelle, cette liste doit rester alignée avec `parcelle_id=None` forcé par
    # creer_evenement_godet (sinon CA8 propose une parcelle réelle, ex. "serre",
    # qui finit par être assignée à un événement qui ne devrait jamais en avoir).
    _ACTIONS_PEPINIERE = {"vendu", "perte_godet", "mise_en_godet"}

    # [US-049] Incohérence culture/variété ↔ parcelle citée — appelle la validation
    # centrale (app/services/evenements.py::valider_evenement) au lieu de recalculer
    # le prédicat ici, pour ne jamais diverger de la règle réellement appliquée à
    # l'écriture. Si invalide, la parcelle citée n'est PAS retenue telle quelle —
    # elle est retirée pour que le bloc CA8 ci-dessous la redétermine (auto-
    # assignation ou menu, cas item unique), exactement comme si l'utilisateur
    # n'avait rien précisé. Contrôle appliqué à CHAQUE item (CA3 US-049 : aucune
    # règle ne doit dépendre du nombre d'items traités dans le même appel).
    from app.services.evenements import valider_evenement as _valider_evenement2, ParcelleIncoherenteError
    db_tmp = SessionLocal()
    try:
        for _item_coh in items:
            if not (_item_coh.get("parcelle") and _item_coh.get("culture")):
                continue
            if (_item_coh.get("type_action") or _item_coh.get("action") or "") in _ACTIONS_SOURCE:
                continue
            culture      = _item_coh["culture"]
            variete      = _item_coh.get("variete") or None
            nom_parcelle = _item_coh["parcelle"]
            parcelle_resolue = resolve_parcelle(db_tmp, nom_parcelle)
            if parcelle_resolue is None:
                continue   # parcelle inconnue : gérée séparément au moment de l'écriture
            try:
                _valider_evenement2(
                    db_tmp, default_context(),
                    action=_item_coh.get("action"), culture=culture,
                    variete=variete, parcelle=parcelle_resolue,
                )
            except ParcelleIncoherenteError as e:
                autres = []
                if variete:
                    # La variété n'est pas connue sur CETTE parcelle : indiquer où
                    # elle a été plantée si elle existe ailleurs, pour aider au choix.
                    parcelles_culture_seule = _get_parcelles_avec_culture(db_tmp, culture, None)
                    autres = sorted({
                        p.nom for p in parcelles_culture_seule if p.id != parcelle_resolue.id
                    })
                suffixe = f" (trouvé sur : {', '.join(autres)})" if autres else ""
                label = f"{e.culture} {e.variete}" if e.variete else e.culture
                _item_coh["_avertissement_coherence"] = (
                    f"⚠️ Aucune trace de *{label}* sur *{e.parcelle_nom}*{suffixe}."
                )
                log.warning("[coherence-check] %s — parcelle retirée, redétection via CA8", str(e))
                del _item_coh["parcelle"]
    finally:
        db_tmp.close()

    # [CA8/CA11] Parcelle absente sur action simple → sélection intelligente
    if len(items) == 1 and not items[0].get("parcelle"):
        action_type = items[0].get("type_action") or items[0].get("action") or ""
        culture     = items[0].get("culture") or ""
        variete     = items[0].get("variete") or None

        if action_type not in _ACTIONS_PEPINIERE:
            db_tmp = SessionLocal()
            try:
                if action_type not in _ACTIONS_SOURCE and culture:
                    # Actions sur culture déjà en place → chercher les parcelles où elle a été plantée
                    parcelles_culture = _get_parcelles_avec_culture(db_tmp, culture, variete)
                else:
                    parcelles_culture = []

                if parcelles_culture and len(parcelles_culture) == 1:
                    # Une seule parcelle connue → auto-assignation silencieuse
                    items[0]["parcelle"] = parcelles_culture[0].nom
                    log.info(f"[US-021] Parcelle auto-détectée : {parcelles_culture[0].nom!r} pour {culture!r}")

                elif parcelles_culture:
                    # Plusieurs parcelles avec cette culture → proposer uniquement celles-là
                    items[0]["_parcelle_demandee"] = True
                    summary = _build_action_summary(items)
                    buttons = [
                        [InlineKeyboardButton(f"📍 {p.nom}", callback_data=f"action_parcelle:{p.nom}")]
                        for p in parcelles_culture
                    ]
                    buttons.append([InlineKeyboardButton("📍 Sans parcelle", callback_data="action_parcelle_none")])
                    log.info(f"[US-021 CA8] {len(parcelles_culture)} parcelles pour {culture!r} — user_id={user_id}")
                    await update.message.reply_text(
                        summary + f"\n\n*Dans quelle parcelle ?* _(parcelles avec {culture})_",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup(buttons),
                    )
                    return

                else:
                    # Aucune plantation connue ou action source → liste complète
                    parcelles_actives = get_all_parcelles(db_tmp)
                    if parcelles_actives:
                        items[0]["_parcelle_demandee"] = True
                        summary = _build_action_summary(items)
                        buttons = [
                            [InlineKeyboardButton(f"📍 {p.nom}", callback_data=f"action_parcelle:{p.nom}")]
                            for p in parcelles_actives
                        ]
                        buttons.append([InlineKeyboardButton("📍 Sans parcelle", callback_data="action_parcelle_none")])
                        log.info(f"[US-021 CA8] Sélection parcelle (liste complète) — user_id={user_id}")
                        await message.reply_text(
                            summary + "\n\n*Quelle parcelle ?*",
                            parse_mode="Markdown",
                            reply_markup=InlineKeyboardMarkup(buttons),
                        )
                        return
            finally:
                db_tmp.close()

    # [US-021 CA9] Quantité manquante pour actions clés → demander avant confirmation
    if (
        len(items) == 1
        and normalize_action(items[0].get("action")) in ["recolte", "semis", "plantation"]
        and not items[0].get("quantite")
    ):
        user_id = update.effective_user.id
        _QUANTITE_PENDING[user_id] = {"items": items, "texte": texte, "ts": _time.time()}
        log.info(f"[US-021 CA9] Quantité manquante pour '{items[0].get('action')}' — user_id={user_id}")
        await message.reply_text(
            "Quelle quantité ? (ex: 2 kg, 15 plants, 1 sachet...)"
        )
        return

    # Parcelle déjà renseignée ou aucune parcelle active → confirmation directe
    summary = _build_action_summary(items)
    buttons = [[
        InlineKeyboardButton("✅ Confirmer", callback_data="action_confirm"),
        InlineKeyboardButton("❌ Annuler",   callback_data="action_cancel"),
    ]]
    log.info(f"[US-021] Confirmation demandée — user_id={user_id}, {len(items)} item(s)")
    await message.reply_text(
        summary,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


def _build_recap_tts(p: dict) -> str:
    """
    Version vocale du récapitulatif — phrase naturelle sans Markdown ni émoji.
    Ex : "Récolte enregistrée. 3 kg de tomates cerise, parcelle nord, le 2026-03-11."
    """
    parties = []
    action = p.get("action") or "action"
    parties.append(f"{action.capitalize()} enregistrée.")

    if p.get("culture"):
        qte    = p.get("quantite")
        unite  = p.get("unite") or ""
        cult   = p.get("culture")
        variete = p.get("variete")
        label  = f"{cult} {variete}".strip() if variete else cult
        if qte:
            rang = p.get("rang")
            if rang:
                total = int(qte) * int(rang)
                parties.append(f"{total} {unite} de {label} sur {rang} rangs.")
            else:
                parties.append(f"{qte} {unite} de {label}.".strip())
        else:
            parties.append(f"Culture : {label}.")

    if p.get("parcelle"):
        parties.append(f"Parcelle {p['parcelle']}.")
    if p.get("duree_minutes"):
        parties.append(f"Durée : {p['duree_minutes']} minutes.")
    if p.get("traitement"):
        parties.append(f"Traitement : {p['traitement']}.")
    if p.get("date"):
        parties.append(f"Date : {p['date']}.")
    if p.get("commentaire"):
        parties.append(p["commentaire"])

    return " ".join(parties)


def _build_recap(p: dict, event_id: int) -> str:
    """Construit le message de récapitulatif."""
    lines = ["✅ *C'est noté !* _(ID #%d)_\n" % event_id]

    # Cas spécial mise_en_godet : repiquage de plantules barquette → godet [US-016]
    action_norm = normalize_action(p.get("action")) or p.get("action") or ""
    if action_norm == "mise_en_godet":
        nb_g = p.get("nb_graines_semees")   # graines d'origine dans la barquette (optionnel)
        nb_p = p.get("nb_plants_godets")    # plants repiqués en godet (champ principal)
        taux_str = ""
        if nb_g and nb_p:
            taux = round(nb_p / nb_g * 100)
            taux_str = f" → *{taux}% de réussite*"
        lines.append("🪴 Action : *mise en godet* (repiquage plantules → godet)")
        if p.get("culture"):      lines.append(f"🥬 Culture : *{p['culture']}*")
        if p.get("variete"):      lines.append(f"🏷 Variété : *{p['variete']}*")
        if nb_p:                  lines.append(f"🌱 Plants repiqués en godet : *{nb_p}*{taux_str}")
        if nb_g:                  lines.append(f"🌾 Graines en barquette d'origine : *{nb_g}*")
        if p.get("parcelle"):     lines.append(f"📍 Parcelle : *{p['parcelle']}*")
        if p.get("date"):         lines.append(f"📅 Date : *{p['date']}*")
        if p.get("commentaire"):  lines.append(f"📝 Note : *{p['commentaire']}*")
        lines.append("\n_Que voulez-vous faire ensuite ?_")
        return "\n".join(lines)

    # Calcul quantité totale si rang présent
    qte_str  = None
    if p.get("quantite") is not None:
        qte_val = p["quantite"]
        unite   = p.get("unite") or ""
        rang    = p.get("rang")
        if rang:
            total   = int(qte_val) * int(rang)
            qte_str = f"{int(qte_val)} {unite}/rang × {rang} rangs = *{total} {unite} total*"
        else:
            qte_str = f"{qte_val} {unite}".strip()

    fields = [
        ("🌱 Action",      p.get("action")),
        ("🥬 Culture",     p.get("culture")),
        ("🏷 Variété",     p.get("variete")),
        ("⚖️ Quantité",   qte_str),
        ("📍 Parcelle",    p.get("parcelle")),
        ("🌾 Rangs",       str(p["rang"]) + " rangs" if p.get("rang") else None),
        ("⏱ Durée",       str(p["duree_minutes"]) + " min" if p.get("duree_minutes") else None),
        ("💊 Traitement",  p.get("traitement")),
        ("📅 Date",        p.get("date")),
        ("📝 Note",        p.get("commentaire")),
    ]

    for label, val in fields:
        if val:
            lines.append(f"{label} : *{val}*")

    lines.append("\n_Que voulez-vous faire ensuite ?_")
    return "\n".join(lines)


# ── QUESTION ANALYTIQUE ─────────────────────────────────────────────────────────
async def _ask_question(update: Update, question: str):
    """
    [US-012] Interroge l'historique via SQL agent — zéro hallucination, zéro Groq pour la réponse.

    Flux : extract_intent_query() [~100 tokens] → query_agent_answer() [0 tokens] → réponse.
    """
    log.info(f"🔍 QUESTION       : {question}")
    msg = await update.message.reply_text("🔍 *Analyse de vos données...*", parse_mode="Markdown")
    try:
        reponse = svc_questions.repondre_question(default_context(), question)
        log.info(f"💡 RÉPONSE SQL    : {reponse[:200]}{'...' if len(reponse) > 200 else ''}")

        try:
            await msg.edit_text(f"🔍 *Réponse :*\n\n{reponse}", parse_mode="Markdown")
        except Exception:
            await msg.edit_text(f"🔍 Réponse :\n\n{reponse}")

        await update.message.reply_text(
            "_Autre question ou action ?_",
            parse_mode="Markdown",
            reply_markup=AFTER_RECORD_KEYBOARD
        )
        await send_voice_reply(update, reponse)
    except Exception as e:
        log.error(f"❌ Erreur _ask_question: {e}")
        await update.message.reply_text(f"❌ Erreur : {e}", reply_markup=MENU_KEYBOARD)


async def _consulter_godets(update) -> None:
    """[US_mise_en_godet] Affiche les plants en godet sans plantation postérieure."""
    db = SessionLocal()
    try:
        en_attente = svc_evenements.godets_en_attente(db, default_context())

        if not en_attente:
            await update.message.reply_text(
                "🪴 *Aucun plant en godet actuellement.*\n\n"
                "Enregistrez une mise en godet :\n"
                "_\"mise en godet 20 tomates Saint-Pierre\"_",
                parse_mode="Markdown",
                reply_markup=AFTER_RECORD_KEYBOARD,
            )
            return

        lines = ["🪴 *Plants actuellement en godet :*\n"]
        for g in en_attente:
            cult = g.culture or "?"
            var  = f" ({g.variete})" if g.variete else ""
            nb   = f" — *{g.nb_plants_godets} plants*" if g.nb_plants_godets else ""
            date_str = f" _{g.date.strftime('%d/%m/%Y')}_" if g.date else ""
            lines.append(f"• 🌱 {cult}{var}{nb}{date_str}")

        lines.append("\n💡 _Plantez-les avec : \"planté X tomates en A1\"_")
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode="Markdown",
            reply_markup=AFTER_RECORD_KEYBOARD,
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Erreur : {e}", reply_markup=MENU_KEYBOARD)
    finally:
        db.close()


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

        occupation = calcul_occupation_parcelles(db, date_ref)
        parcelles_bdd = get_all_parcelles(db)

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


import re as _re

_DATE_ISO_RE  = _re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATE_FR_RE   = _re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")


def _parse_date_arg(s: str) -> date | None:
    """[US-030 / CA10-CA14] Tente de parser une chaîne en date (YYYY-MM-DD ou JJ/MM/AAAA).
    Retourne None si invalide. Future → capée à aujourd'hui."""
    try:
        if _DATE_ISO_RE.match(s):
            d = date.fromisoformat(s)
        elif m := _DATE_FR_RE.match(s):
            d = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        else:
            return None
        return min(d, date.today())
    except ValueError:
        return None


def _looks_like_date(s: str) -> bool:
    """Retourne True si la chaîne ressemble à une date (format reconnu) mais pourrait être invalide."""
    return bool(_DATE_ISO_RE.match(s) or _DATE_FR_RE.match(s))


# ──────────────────────────────────────────────────────────────────────────────
# [US_Plan_occupation_parcelles / CA10, CA12, CA13] Commande /parcelle
# ──────────────────────────────────────────────────────────────────────────────

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
            parcelles = get_all_parcelles(db)
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
            parc, modifs = update_parcelle(db, nom, **kwargs)
            lignes = [f"✅ Parcelle *{parc.nom.upper()}* mise à jour :"]
            for m in modifs:
                lignes.append(f"  · {m}")
            await update.message.reply_text("\n".join(lignes), parse_mode="Markdown")
        except LookupError:
            all_p = get_all_parcelles(db)
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
            exact, proche = find_doublon(db, nom_normalise)

            # [CA10] Doublon exact
            if exact:
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
            parcelles_existantes = get_all_parcelles(db)
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
            parc, nb = rename_parcelle(db, ancien, nouveau)
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
        if len(ctx.args) < 2:
            await update.message.reply_text(
                "❌ Précisez le nom de la parcelle.\nExemple : /parcelle supprimer serre-1",
                parse_mode="Markdown",
            )
            return
        nom = " ".join(ctx.args[1:]).strip()
        db = SessionLocal()
        try:
            parcelle = resolve_parcelle(db, nom)
            if parcelle is None:
                all_p = get_all_parcelles(db)
                noms = ", ".join(p.nom.lower() for p in all_p) or "(aucune)"
                await update.message.reply_text(
                    f"❌ Parcelle introuvable : *{nom}*\nParcelles connues : {noms}",
                    parse_mode="Markdown",
                )
                return
            nb = svc_evenements.compter_evenements_parcelle(db, default_context(), parcelle.id)
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


async def _send_chunked(update, texte: str, reply_markup=None, parse_mode: str = "Markdown"):
    """Envoie un texte long en découpant par blocs de ≤4096 chars sur des sauts de ligne."""
    MAX = 4096
    lines = texte.split("\n")
    chunks, current = [], ""
    for line in lines:
        candidate = (current + "\n" + line) if current else line
        if len(candidate) > MAX:
            if current:
                chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)

    for i, chunk in enumerate(chunks):
        is_last = (i == len(chunks) - 1)
        try:
            await update.effective_message.reply_text(
                chunk,
                parse_mode=parse_mode,
                reply_markup=reply_markup if is_last else None,
            )
        except Exception:
            await update.effective_message.reply_text(
                chunk.replace("*", "").replace("_", ""),
                reply_markup=reply_markup if is_last else None,
            )


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
            varietes      = calcul_stock_par_variete(db, culture_arg, date_ref)
            semis_culture = calcul_semis_par_culture(db, culture_arg, date_ref)
            godets_culture = calcul_godets_par_culture(db, culture_arg, date_ref)  # [US-018]

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
        stocks = calcul_stock_cultures(db, date_ref)

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
        semis = calcul_semis(db, date_ref)
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

        # ── Pépinière (godets) ─────────────────────────────────────────────────
        godets_stats = calcul_godets(db, date_ref=date_ref)
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
        nb_traitements = svc_evenements.compter_traitements(db, default_context())
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
        events = svc_evenements.evenements_recents(db, default_context(), limit=10)
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


# ── HELPERS ─────────────────────────────────────────────────────────────────────
def _md(text: str) -> str:
    """Échappe les underscores dans un nom pour éviter les conflits Markdown Telegram."""
    return text.replace("_", "\\_")


def _to_float(v):
    try:    return float(v) if v is not None else None
    except: return None

def _to_int(v):
    try:    return int(float(v)) if v is not None else None
    except: return None



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
    return f"#{e.id} {d} — {act}{cult}{var}{qte}{rang}{parc}{trt}"


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
    """Groq extrait les critères → SQL retrouve les événements."""
    from groq import Groq
    from config import GROQ_API_KEY, GROQ_MODEL, GROQ_REASONING_EFFORT
    import json

    client = Groq(api_key=GROQ_API_KEY)
    today     = date.today()
    last_week = (today - timedelta(days=7)).isoformat()
    last_month= (today - timedelta(days=30)).isoformat()

    prompt = f"""Aujourd'hui : {today.isoformat()} (année {today.year}).
L'utilisateur veut retrouver un événement potager.
Description : "{description}"

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
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0, max_tokens=200,
            # [fix bug id=357] Sans reasoning_effort, le modèle (gpt-oss, raisonneur)
            # dépense tout le budget max_tokens dans son raisonnement interne caché
            # et coupe avant d'écrire le JSON de réponse (finish_reason="length",
            # content=""). Résultat en prod : "mise en godet fève du 20/07" ne
            # retournait aucun critère exploité, la recherche retombait sur les 3
            # derniers événements toutes cultures confondues (petit pois, tomate),
            # sans lien avec "fève". Même garde-fou que _REASONING_KWARGS dans
            # llm/groq_client.py, à répliquer ici (client Groq distinct, pas
            # partagé) pour tout appel utilisant GROQ_MODEL avec un budget de
            # tokens serré.
            **({"reasoning_effort": GROQ_REASONING_EFFORT} if GROQ_REASONING_EFFORT else {}),
        )
        raw = resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:-1])
        criteres = json.loads(raw)
    except Exception as e:
        log.error(f"Groq critères erreur : {e}")
        criteres = {}

    # Normaliser l'action
    if criteres.get("action"):
        criteres["action"] = _normalize_action_search(criteres["action"])

    log.info(f"🔎 CRITÈRES RECHERCHE : {criteres}")

    db = SessionLocal()
    try:
        results = svc_evenements.find_candidates(db, default_context(), criteres, limit=limit)
        log.info(f"🔎 RÉSULTATS SQL   : {len(results)} trouvé(s)")
        return results
    finally:
        db.close()


async def _corr_annuler_dernier(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Propose correction ou suppression du dernier événement."""
    db = SessionLocal()
    try:
        event = svc_evenements.dernier_evenement(db, default_context())
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
    db = SessionLocal()
    try:
        last = svc_evenements.dernier_evenement(db, default_context())
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
            event = svc_evenements.get_evenement(db, default_context(), ctx.user_data['corr_last_id'])
            candidates = [event] if event else []
            candidates_fmt = [_fmt_event(e) for e in candidates]
        finally:
            db.close()
    else:
        msg_wait = await update.message.reply_text("🔎 Recherche en cours...")
        candidates = _find_candidates(texte)  # charge déjà parcelle_rel via selectinload
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
        event = svc_evenements.get_evenement(db, default_context(), event_id)
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
            svc_evenements.supprimer_evenement(db, default_context(), event_id)
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
                ev = svc_evenements.get_evenement(db, default_context(), event_id)
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
        event = svc_evenements.get_evenement(db, default_context(), event_id)
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
    finally:
        db.close()

    msg_wait = await update.message.reply_text("⏳ Analyse de la correction...")

    from groq import Groq
    from config import GROQ_API_KEY, GROQ_MODEL
    import json

    client = Groq(api_key=GROQ_API_KEY)
    today     = date.today()
    yesterday = (today - timedelta(days=1)).isoformat()

    prompt = f"""Aujourd'hui : {today.isoformat()}. Hier : {yesterday}.
Événement actuel : {json.dumps(event_actuel, ensure_ascii=False)}
Correction demandée : "{texte}"

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

    try:
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0, max_tokens=300
        )
        raw = resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:-1])
        corrections = json.loads(raw)
    except Exception as e:
        log.error(f"Groq correction erreur : {e}")
        await msg_wait.edit_text("❌ Je n'ai pas compris la correction. Reformulez.")
        return

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
            parcelle_resolue = resolve_parcelle(db_check, nom_parcelle_corr)
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
        "commentaire": "Commentaire", "date": "Date"
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
            event = svc_evenements.get_evenement(db, default_context(), ctx.user_data['corr_event_id'])
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
            "commentaire": "commentaire", "date": "date"
        }
        details = ", ".join(
            f"{LABELS.get(k, k)}: {event_actuel.get(k, '—') or '—'} → {v if v is not None else 'supprimé'}"
            for k, v in corrections.items()
            if not k.startswith("_")   # ignorer champs internes (_parcelle_id…)
        )
        trace = f" | [CORR {date.today().isoformat()}] {details}"

        db = SessionLocal()
        try:
            event = svc_evenements.corriger_evenement(db, default_context(), event_id, corrections, trace)
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


# ══════════════════════════════════════════════════════════════════════════════
# [US-007] DÉPLACEMENT / RÉASSOCIATION CULTURE → PARCELLE
# ══════════════════════════════════════════════════════════════════════════════

MODES_DEPLACER = {
    'depl_culture_ask',    # CA11 — culture non détectée, on demande
    'depl_variete_select', # CA4  — plusieurs variétés, choix
    'depl_parcelle_select', # CA5  — liste des parcelles, saisie cible
    'depl_confirm',         # CA7  — récapitulatif, attente confirmation
}


async def _depl_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE, culture: str | None):
    """
    [US-007] Point d'entrée du flux de réassociation.
    - Si culture=None → mode depl_culture_ask (CA11)
    - Sinon → cherche les plantations, route vers variété ou parcelle
    """
    if not culture:
        ctx.user_data['mode'] = 'depl_culture_ask'
        await update.message.reply_text(
            "🔀 *Réassociation culture → parcelle*\n\nQuelle culture souhaitez-vous déplacer ?",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([["❌ Annuler"]], resize_keyboard=True),
        )
        return

    from unidecode import unidecode
    culture = culture.strip().lower()
    culture_norm = unidecode(culture)  # supprime accents pour la comparaison

    db = SessionLocal()
    try:
        # Essai 1 : correspondance exacte (insensible casse)
        rows = svc_evenements.evenements_localises_exact(db, default_context(), culture)
        # Essai 2 : correspondance partielle (gère typos, accents, pluriel)
        if not rows:
            rows = svc_evenements.evenements_localises_recherche_partielle(db, default_context(), culture_norm[:6])
            if rows:
                # Utiliser le nom exact stocké en base pour la suite du flux
                culture = rows[0].culture.lower()
                log.info(f"[US-007] Culture corrigée : '{culture}' trouvée via recherche partielle")
    finally:
        db.close()

    if not rows:
        await update.message.reply_text(
            f"❌ Aucune plantation ni semis pleine terre de *{culture}* trouvé en base.\n\n"
            f"_Vérifiez le nom avec /stats_",
            parse_mode="Markdown",
            reply_markup=MENU_KEYBOARD,
        )
        ctx.user_data['mode'] = None
        log.info(f"[US-007 CA2] Aucune plantation/semis pleine terre pour culture='{culture}'")
        return

    ctx.user_data['depl_culture'] = culture

    # Collecter les variétés distinctes (None = sans variété précisée)
    varietes = list({(e.variete or "") for e in rows})
    varietes_remplies = [v for v in varietes if v]

    if len(varietes_remplies) > 1:
        # CA4 — plusieurs variétés → demander laquelle
        ctx.user_data['mode'] = 'depl_variete_select'
        lines = [f"🌿 J'ai trouvé *{len(varietes_remplies)} variété(s)* de *{culture}* plantée(s) :\n"]
        for v in varietes_remplies:
            nb = sum(1 for e in rows if (e.variete or "") == v)
            lines.append(f"• *{v}* — {nb} enregistrement(s)")
        lines.append("\nSouhaitez-vous déplacer *toutes* les variétés ou une en particulier ?")
        lines.append("Tapez `toutes` ou le nom d'une variété.")
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([["toutes"], ["❌ Annuler"]], resize_keyboard=True),
        )
        log.info(f"[US-007 CA4] Plusieurs variétés pour '{culture}' : {varietes_remplies}")
    else:
        # CA3 — une seule variété ou aucune → passer directement à la sélection de parcelle
        variete_unique = varietes_remplies[0] if varietes_remplies else None
        ctx.user_data['depl_variete'] = variete_unique
        log.info(f"[US-007 CA3] Variété unique '{variete_unique}' → sélection parcelle directe")
        await _depl_show_parcelles(update, ctx)


async def _depl_show_parcelles(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """[US-007 / CA5] Affiche la liste des parcelles avec occupation actuelle."""
    culture = ctx.user_data.get('depl_culture', '?')
    variete = ctx.user_data.get('depl_variete')
    var_str = f" (variété : {variete})" if variete else " (toutes variétés)"

    db = SessionLocal()
    try:
        parcelles = get_all_parcelles(db)
        occupation = calcul_occupation_parcelles(db)
    finally:
        db.close()

    lines = [f"📋 Où souhaitez-vous placer *{culture}*{var_str} ?\n"]
    for p in parcelles:
        cultures_p = occupation.get(p.nom, [])
        if not cultures_p:
            lines.append(f"🟢 *{p.nom.upper()}* — Libre")
        else:
            resumes = []
            for c in cultures_p[:3]:
                cult_label = c['culture']
                if c.get('variete'):
                    cult_label += f" {c['variete']}"
                nb = int(c['nb_plants']) if c['nb_plants'] == int(c['nb_plants']) else c['nb_plants']
                resumes.append(f"{cult_label} ({nb} {c.get('unite', 'plants')})")
            suffix = " …" if len(cultures_p) > 3 else ""
            lines.append(f"📍 *{p.nom.upper()}* — {', '.join(resumes)}{suffix}")

    lines.append("\nTapez le nom de la parcelle cible (ou *annuler*).")
    ctx.user_data['mode'] = 'depl_parcelle_select'
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["❌ Annuler"]], resize_keyboard=True),
    )


async def _depl_variete_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE, texte: str):
    """[US-007 / CA4] L'utilisateur choisit 'toutes' ou une variété spécifique."""
    t = texte.strip().lower()
    if "annuler" in t or "menu" in t or "retour" in t:
        _depl_reset(ctx)
        await update.message.reply_text("↩️ Déplacement annulé.", reply_markup=MENU_KEYBOARD)
        return

    if t in ("toutes", "toutes les variétés", "toutes les varietes", "all"):
        ctx.user_data['depl_variete'] = None
    else:
        ctx.user_data['depl_variete'] = texte.strip()

    await _depl_show_parcelles(update, ctx)


async def _depl_parcelle_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE, texte: str):
    """[US-007 / CA5, CA6] L'utilisateur saisit le nom de la parcelle cible."""
    t = texte.strip().lower()
    if "annuler" in t or "menu" in t or "retour" in t:
        _depl_reset(ctx)
        await update.message.reply_text("↩️ Déplacement annulé.", reply_markup=MENU_KEYBOARD)
        return

    culture = ctx.user_data.get('depl_culture', '')
    variete = ctx.user_data.get('depl_variete')
    nom_parcelle = texte.strip()

    db = SessionLocal()
    try:
        # Résoudre la parcelle (CA6 : accepter une parcelle inconnue)
        parcelle_obj = resolve_parcelle(db, nom_parcelle)
        parcelle_id_cible = parcelle_obj.id if parcelle_obj else None
        nom_affiche = parcelle_obj.nom.upper() if parcelle_obj else nom_parcelle.upper()

        # Compter les enregistrements plantation/semis pleine terre concernés
        nb_records = len(svc_evenements.evenements_localises_pour_maj(db, default_context(), culture, variete))
    finally:
        db.close()

    if nb_records == 0:
        await update.message.reply_text(
            f"❌ Aucune plantation ni semis pleine terre de *{culture}* trouvé.",
            parse_mode="Markdown",
        )
        _depl_reset(ctx)
        return

    ctx.user_data['depl_parcelle_cible'] = nom_parcelle
    ctx.user_data['depl_parcelle_cible_id'] = parcelle_id_cible
    ctx.user_data['depl_nb_records'] = nb_records
    ctx.user_data['mode'] = 'depl_confirm'

    var_str = f" — variété : {variete}" if variete else " — toutes variétés"
    recap = (
        f"✅ *Récapitulatif :*\n"
        f"🌿 Culture : *{culture}*{var_str}\n"
        f"📍 Nouvelle parcelle : *{nom_affiche}*\n"
        f"📝 Enregistrements mis à jour : *{nb_records}* plantation(s)/semis\n\n"
        f"Confirmez-vous ? (*oui* / *non*)"
    )
    await update.message.reply_text(
        recap,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["oui", "non"], ["❌ Annuler"]], resize_keyboard=True),
    )
    log.info(f"[US-007 CA7] Récapitulatif : culture={culture} variete={variete} → {nom_affiche} ({nb_records} records)")


async def _depl_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE, texte: str):
    """[US-007 / CA8] Confirmation finale — exécute l'UPDATE groupé."""
    t = texte.strip().lower()

    if "annuler" in t or "menu" in t or "retour" in t or t in ("non", "n", "no"):
        _depl_reset(ctx)
        await update.message.reply_text("↩️ Déplacement annulé.", reply_markup=MENU_KEYBOARD)
        return

    if t not in ("oui", "o", "yes", "y", "confirmer", "confirme", "✅ confirmer"):
        await update.message.reply_text(
            "❓ Tapez *oui* pour confirmer ou *non* pour annuler.",
            parse_mode="Markdown",
        )
        return

    culture      = ctx.user_data.get('depl_culture', '')
    variete      = ctx.user_data.get('depl_variete')
    nom_parcelle = ctx.user_data.get('depl_parcelle_cible', '')
    parcelle_id  = ctx.user_data.get('depl_parcelle_cible_id')
    nb_records   = ctx.user_data.get('depl_nb_records', 0)

    db = SessionLocal()
    try:
        # CA6 : créer la parcelle si elle n'existe pas encore
        if parcelle_id is None:
            from utils.parcelles import create_parcelle, find_doublon
            doublon = find_doublon(db, nom_parcelle)
            if doublon:
                parcelle_id = doublon.id
                nom_affiche = doublon.nom.upper()
            else:
                new_p = create_parcelle(db, nom_parcelle)
                parcelle_id = new_p.id
                nom_affiche = new_p.nom.upper()
                log.info(f"[US-007 CA6] Nouvelle parcelle créée : {nom_affiche!r}")
        else:
            parc = svc_parcelles.get_parcelle(db, default_context(), parcelle_id)
            nom_affiche = parc.nom.upper() if parc else nom_parcelle.upper()

        # [US-037] Réassocie les événements localisés (plantations ET semis pleine
        # terre) — un semis pépinière n'est jamais concerné (pas de localisation).
        nb_updated = svc_evenements.deplacer_evenements(
            db, default_context(), culture, variete, parcelle_id, nom_affiche
        )
    except Exception as e:
        db.rollback()
        log.error(f"[US-007] Erreur UPDATE : {e}")
        await update.message.reply_text(f"❌ Erreur : {e}", reply_markup=MENU_KEYBOARD)
        _depl_reset(ctx)
        return
    finally:
        db.close()

    _depl_reset(ctx)
    var_str = f" {variete}" if variete else ""
    await update.message.reply_text(
        f"✅ *{nb_updated} plantation(s) de {culture}{var_str}* associée(s) à la parcelle *{nom_affiche}*.",
        parse_mode="Markdown",
        reply_markup=AFTER_RECORD_KEYBOARD,
    )


def _depl_reset(ctx: ContextTypes.DEFAULT_TYPE):
    """[US-007 / CA9] Réinitialise tous les clés du flux DEPLACER."""
    for k in ['mode', 'depl_culture', 'depl_variete', 'depl_parcelle_cible',
              'depl_parcelle_cible_id', 'depl_nb_records']:
        ctx.user_data.pop(k, None)


# ══════════════════════════════════════════════════════════════════════════════
# MÉTÉO
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_meteo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    /meteo — Déclenche manuellement la récupération météo et l'enregistre en base.
    Utile pour tester ou forcer une mise à jour hors du job automatique 5h00.
    """
    msg = await update.message.reply_text("🌤️ *Récupération météo en cours...*", parse_mode="Markdown")
    db  = SessionLocal()
    try:
        meteo = save_meteo_observation(db)
        if meteo is None:
            # Doublon ou erreur — tenter un fetch sans sauvegarde pour afficher quand même
            meteo = fetch_meteo()
            if meteo:
                commentaire = format_meteo_commentaire(meteo)
                await msg.edit_text(
                    f"🌤️ *Météo du jour* _(déjà enregistrée aujourd'hui)_\n\n`{commentaire}`",
                    parse_mode="Markdown"
                )
            else:
                await msg.edit_text("❌ Impossible de récupérer la météo. Vérifiez votre connexion.")
            return

        commentaire = format_meteo_commentaire(meteo)
        await msg.edit_text(
            f"🌤️ *Météo enregistrée !*\n\n`{commentaire}`",
            parse_mode="Markdown"
        )
        log.info("🌤️  MÉTÉO MANUELLE  : déclenchée par /meteo")
    except Exception as e:
        log.error(f"❌ MÉTÉO COMMANDE   : {e}")
        await msg.edit_text(f"❌ Erreur : {e}")
    finally:
        db.close()


async def job_meteo_quotidienne(context: ContextTypes.DEFAULT_TYPE):
    """
    Job planifié à 05h00 chaque matin (Europe/Paris).
    Récupère la météo Open-Meteo et l'enregistre silencieusement en base
    comme action 'observation' avec texte_original='[AUTO-METEO]'.
    Aucun message Telegram envoyé.
    Zéro token Groq consommé.
    """
    log.info("🌅 JOB MÉTÉO       : déclenchement automatique 05h00")
    # [US-043] Job de fond hors dispatch Telegram (JobQueue, pas d'Update) :
    # doit armer app.potager_id lui-même. Un seul potager aujourd'hui — à
    # boucler potager par potager le jour où ce job devient multi-tenant.
    db = SessionLocal()
    try:
        with tenant_scope(default_context().potager_id):
            meteo = save_meteo_observation(db)
        if meteo:
            log.info(
                f"🌤️  MÉTÉO AUTO      : {meteo['emoji']} {meteo['label']} | "
                f"{meteo['temp_matin']}°C matin / {meteo['temp_aprem']}°C AM | "
                f"Pluie {meteo['precipitations']}mm ({meteo['proba_pluie']}%)"
            )
        else:
            log.warning("⚠️  MÉTÉO AUTO      : aucune donnée sauvée (doublon ou erreur réseau)")
    except Exception as e:
        log.error(f"❌ JOB MÉTÉO ERREUR : {e}")
    finally:
        db.close()


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
        tenant_ctx = default_context()
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


# ══════════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════
# [vendu/perte_godet] Commande /vendre
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_vendre(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /vendre [culture] [variete] [quantite] — Enregistre une vente de plants de pépinière.

    Exemple : /vendre tomate cerise 5
    """
    if not ctx.args or len(ctx.args) < 2:
        await update.message.reply_text(
            "🪴 *Vente de plants pépinière*\n\n"
            "Usage : `/vendre [culture] [variété] [quantité]`\n"
            "Exemple : `/vendre tomate cerise 5`\n\n"
            "Ou dictez naturellement : _\"vendu 5 tomates cerise\"_",
            parse_mode="Markdown",
        )
        return

    # Parse des arguments
    args = ctx.args
    try:
        quantite = int(args[-1])
        if len(args) >= 3:
            culture = args[0].lower()
            variete = " ".join(args[1:-1])
        else:
            culture = args[0].lower()
            variete = None
    except ValueError:
        culture  = args[0].lower()
        variete  = " ".join(args[1:]) if len(args) > 1 else None
        quantite = None

    texte_synth = f"vendu {quantite or ''} {culture}{' ' + variete if variete else ''}".strip()
    item = {
        "action":   "vendu",
        "culture":  culture,
        "variete":  variete,
        "quantite": quantite,
        "unite":    "plants",
    }
    await _parse_and_save(update, texte_synth, pre_parsed_items=[item])


# LANCEMENT
# ══════════════════════════════════════════════════════════════════════════════
# [US-043] Arme app.potager_id (défense en profondeur RLS) pour tout le
# traitement de cet Update — PTB v20 traite tous les groupes de handlers d'un
# même Update séquentiellement dans une seule Task asyncio, donc un simple
# .set() (sans reset) ici reste visible pour les handlers des groupes
# suivants ; chaque nouvel Update est traité dans sa propre Task, donc sans
# fuite entre mises à jour concurrentes (sémantique standard de contextvars).
async def _arm_tenant_context(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_potager_id.set(default_context().potager_id)


def main():
    print("🌿 Démarrage du bot Telegram potager...")
    print(f"   Token : {TELEGRAM_BOT_TOKEN[:10]}...")
    print(f"   TTS   : {'🔊 activé' if is_tts_enabled() else '🔇 désactivé'} (commande /tts pour changer)")
    print(f"   Météo : 🌤️ job planifié à 05h00 Europe/Paris · /meteo pour déclencher manuellement")

    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(15)
        .pool_timeout(30)
        .build()
    )

    # [US-043] Arme app.potager_id (défense en profondeur RLS) avant tout autre
    # handler, pour chaque Update entrant — groupe -1 = exécuté en premier,
    # ne bloque pas la propagation vers les handlers des groupes suivants.
    app.add_handler(TypeHandler(Update, _arm_tenant_context), group=-1)

    # Commandes
    app.add_handler(CommandHandler("start",      cmd_start))
    app.add_handler(CommandHandler("help",       cmd_help))
    app.add_handler(CommandHandler("version",    cmd_version))  # [US-008]
    app.add_handler(CommandHandler("stats",      cmd_stats))
    app.add_handler(CommandHandler("historique", cmd_historique))
    app.add_handler(CommandHandler("ask",        cmd_ask))
    app.add_handler(CommandHandler("corriger",   lambda u,c: _corr_start(u,c)))
    app.add_handler(CommandHandler("note",       lambda u,c: _note_start(u,c)))  # [US-038]

    # Commandes TTS
    app.add_handler(CommandHandler("tts",        cmd_tts))
    app.add_handler(CommandHandler("tts_on",     cmd_tts_on))
    app.add_handler(CommandHandler("tts_off",    cmd_tts_off))

    # Commande météo manuelle
    app.add_handler(CommandHandler("meteo",      cmd_meteo))

    # [US_Plan_occupation_parcelles / CA1, CA13] Plan et gestion des parcelles
    app.add_handler(CommandHandler("plan",      cmd_plan))
    app.add_handler(CommandHandler("parcelle",  cmd_parcelle))
    app.add_handler(CommandHandler("parcelles", _cmd_parcelles_lister))  # alias /parcelle lister

    app.add_handler(CommandHandler("vendre",    cmd_vendre))

    # [US-019] Sélection variété mise en godet — boutons inline
    app.add_handler(CallbackQueryHandler(_godet_variete_cb, pattern=r"^godet_"))

    # Sélection variété récolte — boutons inline
    app.add_handler(CallbackQueryHandler(_recolte_variete_cb, pattern=r"^recolte_"))
    app.add_handler(CallbackQueryHandler(_vendu_variete_cb,  pattern=r"^vendu_"))

    # [perte_godet/vendu] Disambiguation perte jardin vs pépinière
    app.add_handler(CallbackQueryHandler(_handle_perte_callback, pattern=r"^perte_"))

    # [US-021] Confirmation avant enregistrement — boutons inline
    app.add_handler(CallbackQueryHandler(_action_confirm_cb, pattern=r"^action_"))
    app.add_handler(CallbackQueryHandler(_semis_organe_cb, pattern=r"^semis_organe"))

    # [US-038] Confirmation avant enregistrement d'une note — boutons inline
    app.add_handler(CallbackQueryHandler(_note_confirm_cb, pattern=r"^note_"))

    # [US-009] Suppression parcelle — boutons inline
    app.add_handler(CallbackQueryHandler(_parcelle_suppr_cb, pattern=r"^parcelle_suppr_"))

    # Messages
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # ── Job météo quotidien à 05h00 (Europe/Paris) ────────────────────────────
    import pytz
    from datetime import time as dtime
    tz_paris = pytz.timezone("Europe/Paris")
    app.job_queue.run_daily(
        job_meteo_quotidienne,
        time=dtime(hour=5, minute=0, second=0, tzinfo=tz_paris),
        name="meteo_quotidienne",
    )
    log.info("🌅 JOB MÉTÉO       : planifié à 05h00 Europe/Paris")

    print("   Bot prêt ! Ouvrez Telegram et parlez à votre bot.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

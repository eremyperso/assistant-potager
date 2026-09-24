"""Socle du bot : journalisation, version, claviers, petits utilitaires partagés.

Module extrait de l'ancien bot.py monolithique (découpage 2026-09).
"""
import os
import logging
import subprocess
from telegram import ReplyKeyboardRemove
from database.db import Base, engine
from datetime import date
import re as _re
# Noms que l'ancien bot.py importait sans les utiliser : conservés pour la façade
# `app.bot` (compatibilité des tests et outils qui les lisaient sur le module).
import asyncio  # noqa: F401
from datetime import datetime  # noqa: F401
from telegram.ext import ConversationHandler  # noqa: F401
from app.config import DATABASE_URL  # noqa: F401
from utils.parcelles import supprimer_parcelle  # noqa: F401
from utils.ia_orchestrator import build_question_context  # noqa: F401
from utils.date_utils import parse_date  # noqa: F401
from app.services import plan as svc_plan  # noqa: F401


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


# ── Init ────────────────────────────────────────────────────────────────────────
Base.metadata.create_all(bind=engine)


# ── Version [US-008] ────────────────────────────────────────────────────────────
def _lire_version() -> str:
    """Lit le numéro de version depuis le fichier VERSION à la racine."""
    try:
        # app/bot/noyau.py -> app/bot -> app -> racine du dépôt
        _base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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


# ── Plus de clavier de raccourcis permanent [US-171 / CA7, CA8, CA12] ───────────
# Les raccourcis du bas d'écran (« Nouvelle action vocale », « Interroger »,
# « Historique », « Stats », « Corriger », « Note », et le clavier d'après
# enregistrement) sont remplacés par le menu de commandes natif de Telegram —
# voir `app.services.menu_commandes` et `_publier_menu_commandes()`.
#
# Le clavier n'est pas seulement retiré du code : il est **activement retiré de
# l'écran** (CA8). Un clavier permanent Telegram persiste côté client tant que le
# bot ne demande pas son retrait ; supprimer les `reply_markup=` aurait laissé
# l'ancien clavier affiché indéfiniment chez les jardiniers qui l'avaient déjà.
# D'où `ReplyKeyboardRemove()` posé sur exactement les mêmes messages qu'avant :
# le premier message reçu après la mise à jour nettoie l'écran, et aucun message
# suivant ne le fait réapparaître (CA12).
#
# Les deux noms historiques survivent volontairement — ils sont posés sur une
# quarantaine de messages et référencés par les tests existants (CA13) — mais ils
# désignent désormais la même absence de clavier.
SANS_CLAVIER = ReplyKeyboardRemove()


MENU_KEYBOARD = SANS_CLAVIER


AFTER_RECORD_KEYBOARD = SANS_CLAVIER


# ── États conversation ───────────────────────────────────────────────────────────
WAITING_ASK = 1


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


def _decouper_en_blocs(texte: str, max_len: int = 4096) -> list:
    """Découpe un texte en blocs de ≤max_len caractères sur des sauts de ligne."""
    lines = texte.split("\n")
    chunks, current = [], ""
    for line in lines:
        candidate = (current + "\n" + line) if current else line
        if len(candidate) > max_len:
            if current:
                chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


async def _send_chunked(update, texte: str, reply_markup=None, parse_mode: str = "Markdown"):
    """Envoie un texte long en découpant par blocs de ≤4096 chars sur des sauts de ligne."""
    chunks = _decouper_en_blocs(texte)

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

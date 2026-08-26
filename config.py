from dotenv import load_dotenv
import os

# Charge le bon fichier .env selon APP_ENV (dev | prod) — défaut : dev
_env = os.environ.get("APP_ENV", "dev")
load_dotenv(f".env.{_env}", override=True)

GROQ_API_KEY       = os.environ["GROQ_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
DATABASE_URL       = os.environ["DATABASE_URL"]
GROQ_MODEL         = "openai/gpt-oss-120b"
GROQ_WHISPER_MODEL = "whisper-large-v3-turbo"

# [US-044] Authentification web JWT — secret jamais codé en dur ni versionné
JWT_SECRET           = os.environ["JWT_SECRET"]
JWT_ALGORITHM        = "HS256"
JWT_ACCESS_TTL_MIN   = int(os.environ.get("JWT_ACCESS_TTL_MIN", "15"))
JWT_REFRESH_TTL_DAYS = int(os.environ.get("JWT_REFRESH_TTL_DAYS", "30"))

# [US-044] Vérification d'e-mail à l'inscription — envoi via l'API Brevo
# (choisie pour son hébergement UE natif + offre gratuite 300 mails/jour).
# BREVO_API_KEY absente/vide → mode dégradé (app/services/email.py logue le
# lien au lieu d'appeler l'API), utilisé en dev/test tant qu'aucun compte
# Brevo n'est configuré.
BREVO_API_KEY  = os.environ.get("BREVO_API_KEY", "")
EMAIL_FROM     = os.environ.get("EMAIL_FROM", "noreply@assistant-potager.fr")
EMAIL_FROM_NOM = os.environ.get("EMAIL_FROM_NOM", "Assistant Potager")
# URL de base de la PWA pour construire le lien de vérification d'e-mail
# (ex. https://assistant-potager.netlify.app) — distincte de PWA_URL ci-dessous
# qui est un texte d'affichage Telegram, pas forcément une URL cliquable.
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

# [US-090] Fédération d'identité Google (OpenID Connect) — identifiants lus
# exclusivement depuis l'environnement, jamais codés en dur ni versionnés (CA9).
# Absents ou vides → connecteur Google totalement masqué côté PWA (CA4) : le
# développement local et les tests fonctionnent sans compte Google Cloud.
GOOGLE_CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
# [CA8] Liste blanche des `redirect_uri` acceptées, séparées par des virgules.
# Elles pointent sur l'API (l'échange du code se fait côté serveur, CA5), pas
# sur le frontend — ex. http://localhost:8000/auth/oauth/google/callback en dev.
GOOGLE_REDIRECT_URIS = [
    uri.strip()
    for uri in os.environ.get("GOOGLE_REDIRECT_URIS", "").split(",")
    if uri.strip()
]

# [US-045] URL de la PWA — référencée dans le message d'onboarding Telegram
# (chat non lié). Pas de domaine en dur : reste un placeholder générique tant
# que PWA_URL n'est pas configurée en environnement.
PWA_URL = os.environ.get("PWA_URL", "l'application web Assistant Potager")

# Niveau de raisonnement Groq ("low" | "medium" | "high" | None).
# Uniquement supporté par les modèles reasoning (ex: gpt-oss-120b, qwen3.6-27b).
# Mettre à None pour les modèles non-reasoning (ex: llama-3.3-70b-versatile),
# sinon l'API Groq renvoie une erreur 400 "reasoning_effort is not supported".
GROQ_REASONING_EFFORT = "low"

# ─────────────────────────────────────────────────────────────────────────────
# [US-092 / CA3] Passerelle LLM — un modèle configurable PAR TYPE D'APPEL
# -----------------------------------------------------------------------------
# Les quotas Groq sont comptés *par modèle* : pouvoir router la classification
# (petit modèle rapide) et le parsing/la synthèse (grand modèle) séparément est
# ce qui rendra possible la répartition multi-modèles. Changer de modèle pour un
# type est un changement de configuration, jamais un changement de code.
#
# Défaut volontaire : tous les types retombent sur GROQ_MODEL (et la
# transcription sur GROQ_WHISPER_MODEL) — la passerelle est livrée à
# comportement constant, l'exercice réel de la répartition relève d'US-093.
# ─────────────────────────────────────────────────────────────────────────────
GROQ_MODELE_PAR_TYPE = {
    "classification": os.environ.get("GROQ_MODEL_CLASSIFICATION", GROQ_MODEL),
    "parsing":        os.environ.get("GROQ_MODEL_PARSING",        GROQ_MODEL),
    "question":       os.environ.get("GROQ_MODEL_QUESTION",       GROQ_MODEL),
    "synthese":       os.environ.get("GROQ_MODEL_SYNTHESE",       GROQ_MODEL),
    "transcription":  os.environ.get("GROQ_MODEL_TRANSCRIPTION",  GROQ_WHISPER_MODEL),
}

# [US-092 / CA12] Délai maximal par appel LLM, en secondes. Un appel qui
# n'aboutit pas dans ce délai emprunte le même chemin de repli qu'un 429.
GROQ_TIMEOUT_S = float(os.environ.get("GROQ_TIMEOUT_S", "30"))

# [US-092 / CA12] Plafond de la temporisation avant l'unique nouvelle tentative.
# La passerelle est appelée depuis des handlers Telegram et des endpoints HTTP :
# au-delà de ce plafond on bascule en mode dégradé plutôt que de faire attendre.
GROQ_RETRY_MAX_S = float(os.environ.get("GROQ_RETRY_MAX_S", "2"))

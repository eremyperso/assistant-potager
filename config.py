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

# [US-045] URL de la PWA — référencée dans le message d'onboarding Telegram
# (chat non lié). Pas de domaine en dur : reste un placeholder générique tant
# que PWA_URL n'est pas configurée en environnement.
PWA_URL = os.environ.get("PWA_URL", "l'application web Assistant Potager")

# Niveau de raisonnement Groq ("low" | "medium" | "high" | None).
# Uniquement supporté par les modèles reasoning (ex: gpt-oss-120b, qwen3.6-27b).
# Mettre à None pour les modèles non-reasoning (ex: llama-3.3-70b-versatile),
# sinon l'API Groq renvoie une erreur 400 "reasoning_effort is not supported".
GROQ_REASONING_EFFORT = "low"

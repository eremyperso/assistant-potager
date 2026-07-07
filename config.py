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

# Niveau de raisonnement Groq ("low" | "medium" | "high" | None).
# Uniquement supporté par les modèles reasoning (ex: gpt-oss-120b, qwen3.6-27b).
# Mettre à None pour les modèles non-reasoning (ex: llama-3.3-70b-versatile),
# sinon l'API Groq renvoie une erreur 400 "reasoning_effort is not supported".
GROQ_REASONING_EFFORT = "low"

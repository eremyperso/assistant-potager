from dotenv import load_dotenv
import os

# Charge le bon fichier .env selon APP_ENV (dev | prod) — défaut : dev
_env = os.environ.get("APP_ENV", "dev")
load_dotenv(f".env.{_env}", override=True)

GROQ_API_KEY       = os.environ["GROQ_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
DATABASE_URL       = os.environ["DATABASE_URL"]
GROQ_MODEL         = "llama-3.3-70b-versatile"
GROQ_WHISPER_MODEL = "whisper-large-v3-turbo"

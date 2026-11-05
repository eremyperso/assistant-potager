"""Réglages du harnais, lus dans `.env.test` (à la racine) puis dans l'environnement.

Ce module n'importe ni `app` ni `database` : valider des scénarios (`--dry-run`) ne doit
demander ni base ni clé."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

RACINE = Path(__file__).resolve().parents[2]
DOSSIER_SCENARIOS = RACINE / "tests_conv" / "scenarios"
DOSSIER_RAPPORTS = RACINE / "rapports_conv"

os.environ.setdefault("APP_ENV", "test")
load_dotenv(RACINE / ".env.test", override=False)


class ConfigIncomplete(Exception):
    pass


@dataclass(frozen=True)
class Config:
    api_id: int
    api_hash: str
    session: str
    bot: str                    # nom d'utilisateur du bot de test, sans @
    quiescence_s: float         # silence qui clôt un tour
    premiere_reponse_s: float   # attente maximale de la première réponse
    plafond_tour_s: float       # durée maximale d'un tour
    pause_s: float              # délai minimal entre deux envois (limites de débit Telegram)


def lire(exiger_session: bool = True) -> Config:
    manquants = [n for n in ("TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_TEST_BOT_USERNAME")
                 if not os.environ.get(n)]
    if exiger_session and not os.environ.get("TELEGRAM_TEST_SESSION"):
        manquants.append("TELEGRAM_TEST_SESSION (créée par `python -m tests_conv session`)")
    if manquants:
        raise ConfigIncomplete("absent de .env.test : " + ", ".join(manquants))
    return Config(
        api_id=int(os.environ["TELEGRAM_API_ID"]),
        api_hash=os.environ["TELEGRAM_API_HASH"],
        session=os.environ.get("TELEGRAM_TEST_SESSION", ""),
        bot=os.environ["TELEGRAM_TEST_BOT_USERNAME"].lstrip("@"),
        quiescence_s=float(os.environ.get("CONV_QUIESCENCE_S", "5")),
        premiere_reponse_s=float(os.environ.get("CONV_PREMIERE_REPONSE_S", "45")),
        plafond_tour_s=float(os.environ.get("CONV_PLAFOND_TOUR_S", "120")),
        pause_s=float(os.environ.get("CONV_PAUSE_S", "1.5")),
    )

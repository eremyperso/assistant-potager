from dotenv import load_dotenv
import os

# Charge le bon fichier .env selon APP_ENV (dev | prod) — défaut : dev.
# Cherché d'abord dans le répertoire courant (contrat historique, US-004), puis
# à la RACINE du dépôt (app/config.py -> app -> racine) : un outil lancé depuis
# un autre dossier trouve ainsi le même fichier que `python -m app.bot`.
APP_ENV = os.environ.get("APP_ENV", "dev")
RACINE_PROJET = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_fichier_env = f".env.{APP_ENV}"
if not os.path.exists(_fichier_env):
    _fichier_env = os.path.join(RACINE_PROJET, _fichier_env)
load_dotenv(_fichier_env, override=True)

GROQ_API_KEY       = os.environ["GROQ_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
DATABASE_URL       = os.environ["DATABASE_URL"]
GROQ_MODEL         = "openai/gpt-oss-120b"
#GROQ_MODEL         = "groq/compound-mini"
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
    # [US-233 / CA2] Agent interpréteur : modèle PROPRE, distinct de celui de la
    # classification — l'agent appelle des outils, ce que tout modèle ne fait pas
    # avec la même fiabilité, et son choix se décide sur une mesure (US-233).
    "agent":          os.environ.get("GROQ_MODEL_AGENT",          GROQ_MODEL),
    "transcription":  os.environ.get("GROQ_MODEL_TRANSCRIPTION",  GROQ_WHISPER_MODEL),
}

# ─────────────────────────────────────────────────────────────────────────────
# Fournisseur tiers Mistral — un type d'appel bascule par son seul modèle
# -----------------------------------------------------------------------------
# Un modèle préfixé `mistral/` dans `GROQ_MODEL_<TYPE>` (ex.
# `GROQ_MODEL_AGENT=mistral/ministral-3b-latest`) est servi par l'API Mistral,
# compatible OpenAI ; les autres types restent sur Groq. Sans clé, un type
# basculé sur Mistral rend une indisponibilité (repli de l'appelant), jamais un
# appel muet à Groq.
# ─────────────────────────────────────────────────────────────────────────────
MISTRAL_API_KEY  = os.environ.get("MISTRAL_API_KEY", "")
MISTRAL_BASE_URL = os.environ.get("MISTRAL_BASE_URL", "https://api.mistral.ai").rstrip("/")

# ─────────────────────────────────────────────────────────────────────────────
# [US-233 / CA5] Agent interpréteur — réglages lus ici, sans effet tant
# qu'aucun agent ne les utilise (US-235 et suivantes).
# -----------------------------------------------------------------------------
# AGENT_MODE : "off" (défaut — le bot se comporte comme avant), "ombre" (l'agent
# interprète et journalise ce qu'il AURAIT proposé, sans rien montrer) ou
# "actif" (ses propositions sont affichées). Une valeur inconnue retombe sur
# "off" : une faute de frappe ne doit jamais activer l'agent.
# AGENT_MAX_TOURS : borne de la boucle conversationnelle de l'agent (US-257,
# architecture §12.4 : lecture, proposition, correction après le verdict du
# validateur, réponse) ; un entier strictement positif, 6 sinon.
# ─────────────────────────────────────────────────────────────────────────────
AGENT_MODES = ("off", "ombre", "actif")
AGENT_MODE = os.environ.get("AGENT_MODE", "off").strip().lower()
if AGENT_MODE not in AGENT_MODES:
    AGENT_MODE = "off"


def _entier_strictement_positif(nom: str, defaut: int) -> int:
    try:
        valeur = int(os.environ.get(nom, defaut))
    except ValueError:
        return defaut
    return valeur if valeur >= 1 else defaut


AGENT_MAX_TOURS = _entier_strictement_positif("AGENT_MAX_TOURS", 6)

# [US-092 / CA12] Délai maximal par appel LLM, en secondes. Un appel qui
# n'aboutit pas dans ce délai emprunte le même chemin de repli qu'un 429.
GROQ_TIMEOUT_S = float(os.environ.get("GROQ_TIMEOUT_S", "30"))

# [US-092 / CA12] Plafond de la temporisation avant l'unique nouvelle tentative.
# La passerelle est appelée depuis des handlers Telegram et des endpoints HTTP :
# au-delà de ce plafond on bascule en mode dégradé plutôt que de faire attendre.
GROQ_RETRY_MAX_S = float(os.environ.get("GROQ_RETRY_MAX_S", "2"))

# [US-097 / CA7] E-mail du compte administrateur de la plateforme — seul compte
# autorisé à consulter les métriques de routage. Absent/vide → endpoints admin
# totalement inaccessibles (403), pas de repli sur un compte par défaut.
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")

# ─────────────────────────────────────────────────────────────────────────────
# [US-098] Étage 2 — socle de connaissance (recherche plein texte)
# -----------------------------------------------------------------------------
# RAG_ACTIF est un INTERRUPTEUR, pas un verrou de livraison : tant que le corpus
# est vide (il l'est jusqu'à US-099/US-140/US-141), l'étage est inerte de
# lui-même et la cascade se comporte exactement comme avant. Il existe pour
# qu'on puisse le couper en production SANS redéploiement le jour où la mesure
# du CA13 (`python tools/mesurer_corpus_savoir.py`) montrerait que le bon
# fragment ne sort pas dans les trois premiers résultats — cette mesure
# conditionne l'activation de l'étage, elle ne se suppose pas.
RAG_ACTIF = os.environ.get("RAG_ACTIF", "1").strip().lower() not in ("0", "false", "non", "")

# Au-dessus de ce score de confiance global, et à condition que le passage soit
# marqué `verifie`, la réponse est servie telle quelle à coût nul (CA7). En
# dessous, le contexte descend à l'étage de raisonnement.
#
# ⚠️ La valeur 0.6 est étalonnée sur le repli SQLite des tests, où le score est
# une couverture de termes. En production, le score est un `ts_rank_cd`
# normalisé PostgreSQL : la MÊME question n'y produit PAS le même nombre. Les
# deux échelles sont bornées dans [0, 1] mais ne se superposent pas, et un seuil
# repris tel quel rendrait l'étage soit muet, soit trop bavard. C'est
# précisément ce que `python tools/mesurer_corpus_savoir.py` doit établir contre
# la production avant l'arrivée du corpus (US-099/US-140) — la valeur se règle
# alors ici, par variable d'environnement, sans redéploiement.
RAG_SEUIL_CONFIANCE = float(os.environ.get("RAG_SEUIL_CONFIANCE", "0.6"))

# Nombre de passages retenus par recherche. 3 par défaut, comme la cible du
# CA13 (« le bon fragment figure dans les trois premiers résultats ») : au-delà,
# on allongerait le contexte envoyé à l'étage 3 sans améliorer la mesure.
RAG_MAX_PASSAGES = int(os.environ.get("RAG_MAX_PASSAGES", "3"))

# ─────────────────────────────────────────────────────────────────────────────
# [US-165] Pré-diagnostic déterministe à partir des symptômes décrits
# -----------------------------------------------------------------------------
# Score minimal en deçà duquel une description N'EST PAS reconnue comme un
# symptôme du référentiel. C'est le réglage du CA8, celui qui décide entre « je
# n'ai pas de piste » et un rapprochement forcé : le corpus de mesure réserve 25
# de ses 44 entrées à ce seul test d'honnêteté, parce qu'une piste inventée sur
# un symptôme mal compris est le risque le plus élevé de tout l'épic.
#
# ⚠️ Même avertissement d'échelle que RAG_SEUIL_CONFIANCE, et il vaut ici aussi :
# le repli SQLite score une COUVERTURE DE TERMES, PostgreSQL un `ts_rank_cd`
# normalisé. Les deux sont dans [0, 1] et ne se superposent pas. La valeur se
# réétalonne contre la production avec `python tools/mesurer_prediagnostic.py`,
# par variable d'environnement, sans redéploiement.
PREDIAGNOSTIC_SEUIL_SYMPTOME = float(os.environ.get("PREDIAGNOSTIC_SEUIL_SYMPTOME", "0.35"))

# [CA5] « Deux à trois hypothèses sont toujours présentées » — une hypothèse
# unique se lit comme une conclusion, quelle que soit la prudence qui l'entoure.
# Le plafond est ici ; le plancher, lui, n'est pas un réglage : quand le
# croisement n'en produit qu'une, l'application le DIT (voir
# `prediagnostic.ISSUE_PISTE_UNIQUE`) au lieu d'en inventer une seconde.
PREDIAGNOSTIC_MAX_PISTES = int(os.environ.get("PREDIAGNOSTIC_MAX_PISTES", "3"))

# ─────────────────────────────────────────────────────────────────────────────
# [US-068 / CA8] Calendrier cultural — zone climatique par défaut
# -----------------------------------------------------------------------------
# Zone dont un potager lit les fenêtres quand il n'a ni zone choisie par le
# jardinier, ni localisation dont on puisse la déduire. `oceanique` par défaut :
# c'est le climat de la plus grande part des jardins de France métropolitaine.
# Réglable sans redéploiement ; une valeur hors vocabulaire retombe sur
# `oceanique` (voir app.services.calendrier_cultural.zone_par_defaut).
CALENDRIER_ZONE_DEFAUT = os.environ.get("CALENDRIER_ZONE_DEFAUT", "oceanique").strip().lower()

# [US-193 / CA4] Altitude (mètres) à partir de laquelle la zone DÉDUITE d'un
# potager localisé est montagnarde, quelles que soient latitude et longitude.
# 700 m par défaut (à confirmer avec le porteur du produit). Réglable sans
# redéploiement ; le choix du jardinier (`/calendrier zone`) prime toujours.
try:
    CALENDRIER_SEUIL_MONTAGNARD_M = float(os.environ.get("CALENDRIER_SEUIL_MONTAGNARD_M", "700"))
except ValueError:
    CALENDRIER_SEUIL_MONTAGNARD_M = 700.0


# ─────────────────────────────────────────────────────────────────────────────
# État de la configuration, affiché au démarrage du bot
# -----------------------------------------------------------------------------
# Pour contrôler ce que le système RETIENT : la valeur effective de chaque
# réglage, et d'où elle vient — « défini » (environnement ou fichier .env) ou
# « défaut ». Une valeur invalide qui retombe sur son défaut est signalée : une
# faute de frappe dans `AGENT_MODE` ne doit pas passer inaperçue.
#
# Aucun secret n'est jamais affiché : clés, jetons et mots de passe sont rendus
# « défini » ou « absent », sans le moindre caractère de leur valeur.
# ─────────────────────────────────────────────────────────────────────────────
def etat_configuration() -> list[str]:
    """Les lignes à afficher au démarrage : un réglage par ligne, valeur retenue."""
    lignes: list[str] = []

    def _origine(nom: str) -> str:
        return "défini" if nom in os.environ else "défaut"

    def _ligne(nom: str, retenu, invalide: bool = False) -> None:
        brut = os.environ.get(nom)
        alerte = f" ⚠️ « {brut} » non retenu → valeur par défaut" if invalide and brut is not None else ""
        lignes.append(f"   {nom:<30}: {retenu}  ({_origine(nom)}){alerte}")

    def _secret(nom: str, valeur) -> None:
        lignes.append(f"   {nom:<30}: {'défini' if valeur else 'absent'}")

    existe = os.path.exists(_fichier_env)
    lignes.append(f"   Fichier d'environnement     : {os.path.basename(_fichier_env)} "
                  f"({'chargé' if existe else 'introuvable'})")
    _ligne("APP_ENV", APP_ENV)

    # Agent interpréteur — ce que l'on contrôle le plus souvent.
    brut_mode = os.environ.get("AGENT_MODE")
    _ligne("AGENT_MODE", AGENT_MODE,
           invalide=brut_mode is not None and brut_mode.strip().lower() != AGENT_MODE)
    brut_tours = os.environ.get("AGENT_MAX_TOURS")
    _ligne("AGENT_MAX_TOURS", AGENT_MAX_TOURS,
           invalide=brut_tours is not None and brut_tours.strip() != str(AGENT_MAX_TOURS))

    for type_appel, modele in GROQ_MODELE_PAR_TYPE.items():
        _ligne(f"GROQ_MODEL_{type_appel.upper()}", modele)
    _ligne("GROQ_TIMEOUT_S", GROQ_TIMEOUT_S)
    _ligne("GROQ_RETRY_MAX_S", GROQ_RETRY_MAX_S)
    _ligne("RAG_ACTIF", "oui" if RAG_ACTIF else "non")
    _ligne("RAG_SEUIL_CONFIANCE", RAG_SEUIL_CONFIANCE)
    _ligne("RAG_MAX_PASSAGES", RAG_MAX_PASSAGES)
    _ligne("PREDIAGNOSTIC_SEUIL_SYMPTOME", PREDIAGNOSTIC_SEUIL_SYMPTOME)
    _ligne("PREDIAGNOSTIC_MAX_PISTES", PREDIAGNOSTIC_MAX_PISTES)
    _ligne("CALENDRIER_ZONE_DEFAUT", CALENDRIER_ZONE_DEFAUT)
    _ligne("CALENDRIER_SEUIL_MONTAGNARD_M", CALENDRIER_SEUIL_MONTAGNARD_M)

    for nom, valeur in (
        ("GROQ_API_KEY", GROQ_API_KEY), ("MISTRAL_API_KEY", MISTRAL_API_KEY),
        ("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN),
        ("DATABASE_URL", DATABASE_URL), ("JWT_SECRET", JWT_SECRET),
        ("BREVO_API_KEY", BREVO_API_KEY), ("GOOGLE_CLIENT_ID", GOOGLE_CLIENT_ID),
        ("GOOGLE_CLIENT_SECRET", GOOGLE_CLIENT_SECRET), ("ADMIN_EMAIL", ADMIN_EMAIL),
    ):
        _secret(nom, valeur)
    return lignes

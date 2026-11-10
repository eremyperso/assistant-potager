from dotenv import load_dotenv
import os
import re
from typing import Optional

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
# Groq, fournisseur de la plateforme. Adresse : `GROQ_BASE_URL` (absente → celle du SDK Groq).
# Les deux modèles ci-dessous sont des valeurs de repli, remplacées par l'environnement.
GROQ_BASE_URL      = os.environ.get("GROQ_BASE_URL", "").strip().rstrip("/") or None
GROQ_MODEL         = os.environ.get("GROQ_MODEL", "").strip() or "openai/gpt-oss-120b"
GROQ_WHISPER_MODEL = os.environ.get("GROQ_WHISPER_MODEL", "").strip() or "whisper-large-v3-turbo"

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
EMAIL_FROM_NOM = os.environ.get("EMAIL_FROM_NOM", "Les bons gestes")
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

# [US-290] Canal MCP — assistants IA externes (Claude, ChatGPT, Le Chat).
# MCP_URL_PUBLIQUE : adresse publique de l'API, sans « / » final ; c'est
# l'émetteur OAuth et la base de l'URL du connecteur (`{MCP_URL_PUBLIQUE}/mcp`).
# Elle doit être exactement celle que voit l'assistant (https en prod).
MCP_URL_PUBLIQUE = os.environ.get("MCP_URL_PUBLIQUE", "http://localhost:8000").rstrip("/")
# [CA6] Plafond d'appels d'outils par connecteur : par minute glissante et par
# 24 h glissantes. Au-delà, rien n'est exécuté et un message clair est rendu.
MCP_QUOTA_MINUTE = int(os.environ.get("MCP_QUOTA_MINUTE", "30"))
MCP_QUOTA_JOUR = int(os.environ.get("MCP_QUOTA_JOUR", "1000"))
# Durées de vie : jeton d'accès (minutes), jeton de rafraîchissement (jours),
# jeton personnel par défaut (jours, CA9).
MCP_ACCES_TTL_MIN = int(os.environ.get("MCP_ACCES_TTL_MIN", "60"))
MCP_RAFRAICHISSEMENT_TTL_JOURS = int(os.environ.get("MCP_RAFRAICHISSEMENT_TTL_JOURS", "30"))
MCP_PERSONNEL_TTL_JOURS = int(os.environ.get("MCP_PERSONNEL_TTL_JOURS", "90"))

# [US-045] URL de la PWA — référencée dans le message d'onboarding Telegram
# (chat non lié). Pas de domaine en dur : reste un placeholder générique tant
# que PWA_URL n'est pas configurée en environnement.
PWA_URL = os.environ.get("PWA_URL", "l'application web Les bons gestes")

# Niveau de raisonnement Groq ("low" | "medium" | "high" | None).
# Uniquement supporté par les modèles reasoning (ex: gpt-oss-120b, qwen3.6-27b).
# Mettre à None pour les modèles non-reasoning (ex: llama-3.3-70b-versatile),
# sinon l'API Groq renvoie une erreur 400 "reasoning_effort is not supported".
# `GROQ_REASONING_EFFORT=aucun` (ou vide) : le paramètre n'est jamais envoyé.
_effort = os.environ.get("GROQ_REASONING_EFFORT", "low").strip().lower()
GROQ_REASONING_EFFORT = None if _effort in ("", "aucun", "none") else _effort

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
# [US-267 / CA6] La rédaction d'un message spontané : un type d'appel à part, compté à part
# dans `conso_tokens` (le coût suit le volume de signaux). Par défaut, le modèle de l'agent :
# c'est lui qui « rédige sans décider ».
GROQ_MODELE_PAR_TYPE["compagnon_signal"] = os.environ.get(
    "GROQ_MODEL_COMPAGNON_SIGNAL", GROQ_MODELE_PAR_TYPE["agent"],
)
# [US-273 / CA3] L'analyse approfondie (mode Extra) : un type d'appel à part, compté à part. Par
# défaut le modèle de l'agent ; c'est le seul endroit où une montée de modèle se justifie, et elle
# se fait ici, par `GROQ_MODEL_ANALYSE`, sans code (cadrage §4.5).
GROQ_MODELE_PAR_TYPE["analyse"] = os.environ.get(
    "GROQ_MODEL_ANALYSE", GROQ_MODELE_PAR_TYPE["agent"],
)
# [US-299 / CA1, CA2] Compagnon vocal de la PWA (Voxtral, Mistral). Deux types à part,
# distincts de `transcription` (Telegram, Whisper) : changer la voix de la PWA ne touche
# jamais le bot (décision D7). Identifiants relevés par l'essai US-298 (`-3` et `-3-0`
# acceptés pour la dictée ; seul `voxtral-mini-tts-3-0` / `-3` accepte les voix 3).
GROQ_MODELE_PAR_TYPE["dictee"] = os.environ.get(
    "GROQ_MODEL_DICTEE", "mistral/voxtral-mini-transcribe-3-0",
)
GROQ_MODELE_PAR_TYPE["voix"] = os.environ.get(
    "GROQ_MODEL_VOIX", "mistral/voxtral-mini-tts-3-0",
)
# [US-303] Résumé parlé d'une réponse (appel de chat ordinaire) : le modèle de l'agent par défaut.
GROQ_MODELE_PAR_TYPE["oral"] = os.environ.get("GROQ_MODEL_ORAL", GROQ_MODELE_PAR_TYPE["agent"])


def nettoyer_modele(brut: str) -> tuple[str, bool]:
    """Un identifiant de modèle ne contient jamais d'espace : seul le premier mot est
    retenu (`mistral/x   (voix : texte → MP3)` → `mistral/x`). Rend (modèle, rogné ?)."""
    mots = (brut or "").split()
    return (mots[0] if mots else brut), len(mots) > 1


# Une explication laissée sur la ligne de la valeur dans le .env en ferait partie, et
# ce texte serait envoyé au fournisseur comme nom de modèle. On la retire, signalée au démarrage.
MODELES_ROGNES: dict[str, str] = {}
for _type, _brut in list(GROQ_MODELE_PAR_TYPE.items()):
    _propre, _rogne = nettoyer_modele(_brut)
    GROQ_MODELE_PAR_TYPE[_type] = _propre
    if _rogne:
        MODELES_ROGNES[_type] = _brut

# [US-300 / CA2] Voix du compagnon tant que le jardinier n'en a pas choisi (ou si la sienne
# a été retirée par Mistral) : Marie, voix française de Voxtral 3.
VOIX_PAR_DEFAUT = os.environ.get("VOIX_PAR_DEFAUT", "").strip() or "voice_592"

# [US-299 / CA6] Formats audio de dictée convertis par FFmpeg avant l'envoi à Mistral
# (extensions séparées par des virgules, ex. `mp4,m4a`). Vide par défaut : l'essai US-298 a
# vu `webm` (Chrome, Edge) et `ogg` (Firefox) acceptés tels quels ; `mp4` (Safari) n'y a
# pas été essayé. Un format listé ici part en WAV mono 16 kHz.
VOIX_FORMATS_A_CONVERTIR: frozenset[str] = frozenset(
    f.strip().lower().lstrip(".")
    for f in os.environ.get("VOIX_FORMATS_A_CONVERTIR", "").split(",")
    if f.strip()
)

def _entier_positif(nom: str, defaut: int) -> int:
    """Entier strictement positif lu dans l'environnement ; la valeur par défaut sinon."""
    try:
        valeur = int(os.environ.get(nom, "").strip() or defaut)
    except ValueError:
        return defaut
    return valeur if valeur > 0 else defaut


# [US-302 / CA3, CA5, CA12] Dictée de la PWA : durée maximale d'un enregistrement (la PWA
# s'arrête seule), poids maximal du fichier reçu, et nombre de dictées par jardinier et par jour.
VOIX_DICTEE_DUREE_MAX_S = _entier_positif("VOIX_DICTEE_DUREE_MAX_S", 60)
VOIX_DICTEE_TAILLE_MAX_KO = _entier_positif("VOIX_DICTEE_TAILLE_MAX_KO", 3072)
VOIX_PLAFOND_DICTEES_JOUR = _entier_positif("VOIX_PLAFOND_DICTEES_JOUR", 100)

# [US-303 / CA2] Résumé parlé d'une réponse du compagnon : 300 caractères au plus.
VOIX_ORAL_MAX_CARACTERES = _entier_positif("VOIX_ORAL_MAX_CARACTERES", 300)

# [US-304 / CA9] Lectures à voix haute des réponses de Gaston, par jardinier et par jour.
VOIX_PLAFOND_LECTURES_JOUR = _entier_positif("VOIX_PLAFOND_LECTURES_JOUR", 100)

# ─────────────────────────────────────────────────────────────────────────────
# Fournisseur tiers Mistral — un type d'appel bascule par son seul modèle
# -----------------------------------------------------------------------------
# Un modèle préfixé `mistral/` dans `GROQ_MODEL_<TYPE>` (ex.
# `GROQ_MODEL_AGENT=mistral/ministral-3b-latest`) est servi par l'API Mistral,
# compatible OpenAI ; les autres types restent sur Groq. Sans clé OU sans adresse
# (`MISTRAL_BASE_URL`, aucune valeur dans le code), un type basculé sur Mistral rend
# une indisponibilité (repli de l'appelant), jamais un appel muet à Groq.
# ─────────────────────────────────────────────────────────────────────────────
MISTRAL_API_KEY  = os.environ.get("MISTRAL_API_KEY", "")
MISTRAL_BASE_URL = os.environ.get("MISTRAL_BASE_URL", "").strip().rstrip("/")

# ─────────────────────────────────────────────────────────────────────────────
# Fournisseurs compatibles OpenAI, déclarés dans l'environnement
# -----------------------------------------------------------------------------
# Brancher un autre fournisseur (OpenAI, un serveur local de voix, un hébergeur
# compatible…) est un changement de configuration, jamais de code :
#
#   FOURNISSEURS_COMPATIBLES=oai,local
#   FOURNISSEUR_OAI_BASE_URL=https://api.openai.com/v1      (URL AVEC /v1)
#   FOURNISSEUR_OAI_API_KEY=sk-...
#   GROQ_MODEL_VOIX=oai/gpt-4o-mini-tts
#
# Le préfixe `<nom>/` d'un modèle désigne le fournisseur, comme `mistral/`. Les noms
# qui sont déjà des espaces de modèles Groq (`openai/gpt-oss-120b`…) sont refusés :
# ils détourneraient des modèles Groq existants.
# ─────────────────────────────────────────────────────────────────────────────
NOMS_FOURNISSEURS_RESERVES: frozenset[str] = frozenset({
    "mistral", "groq", "openai", "meta-llama", "qwen", "moonshotai", "deepseek",
    "google", "canopylabs", "playai", "allam", "compound",
})


def lire_fournisseurs_compatibles(environ) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Fournisseurs déclarés `{nom: {"base_url", "api_key"}}`, et les noms écartés (motif)."""
    retenus: dict[str, dict[str, str]] = {}
    ecartes: list[str] = []
    for brut in (environ.get("FOURNISSEURS_COMPATIBLES") or "").split(","):
        nom = brut.strip().lower()
        if not nom:
            continue
        if not re.fullmatch(r"[a-z][a-z0-9_]*", nom):
            ecartes.append(f"{nom} (nom invalide : lettres, chiffres, _)")
            continue
        if nom in NOMS_FOURNISSEURS_RESERVES:
            ecartes.append(f"{nom} (nom réservé)")
            continue
        base = (environ.get(f"FOURNISSEUR_{nom.upper()}_BASE_URL") or "").strip().rstrip("/")
        if not base:
            ecartes.append(f"{nom} (FOURNISSEUR_{nom.upper()}_BASE_URL absente)")
            continue
        retenus[nom] = {"base_url": base,
                        "api_key": (environ.get(f"FOURNISSEUR_{nom.upper()}_API_KEY") or "").strip()}
    return retenus, ecartes


FOURNISSEURS_COMPATIBLES, FOURNISSEURS_ECARTES = lire_fournisseurs_compatibles(os.environ)


def lire_catalogue_voix(brut: str) -> tuple[tuple[str, str, Optional[str]], ...]:
    """`VOIX_CATALOGUE=id:Nom[:genre],…` → ((id, nom, genre), …), entrées incomplètes ignorées."""
    voix = []
    for entree in (brut or "").split(","):
        morceaux = [m.strip() for m in entree.split(":")]
        if len(morceaux) >= 2 and morceaux[0] and morceaux[1]:
            voix.append((morceaux[0], morceaux[1], (morceaux[2] or None) if len(morceaux) > 2 else None))
    return tuple(voix)


# Voix proposées dans « Mon compagnon » quand la synthèse n'est pas servie par Mistral
# (le catalogue Mistral n'a alors plus de sens). Définie, elle remplace aussi le
# catalogue Mistral. `VOIX_PAR_DEFAUT` doit en faire partie.
VOIX_CATALOGUE = lire_catalogue_voix(os.environ.get("VOIX_CATALOGUE", ""))

# ─────────────────────────────────────────────────────────────────────────────
# [US-233 / CA5] Agent interpréteur — réglages lus ici, sans effet tant
# qu'aucun agent ne les utilise (US-235 et suivantes).
# -----------------------------------------------------------------------------
# AGENT_MODE : "off" (défaut — le bot se comporte comme avant), "ombre" (l'agent
# interprète et journalise ce qu'il AURAIT proposé, sans rien montrer) ou
# "actif" (ses propositions sont affichées). Une valeur inconnue retombe sur
# "off" : une faute de frappe ne doit jamais activer l'agent.
# [Agent d'abord, mesure du 01/11/2026] "prioritaire" : toute phrase libre va
# d'abord à l'agent, qui voit tout le catalogue et les outils de savoir ; les
# règles ne servent plus qu'en mode dégradé (agent indisponible). À mesurer
# avec `tools/evaluer_dialogues.py --mode prioritaire` avant tout usage.
# AGENT_MAX_TOURS : borne de la boucle conversationnelle de l'agent (US-257,
# architecture §12.4 : lecture, proposition, correction après le verdict du
# validateur, réponse) ; un entier strictement positif, 6 sinon.
# ─────────────────────────────────────────────────────────────────────────────
AGENT_MODES = ("off", "ombre", "actif", "prioritaire")
AGENT_MODE = os.environ.get("AGENT_MODE", "off").strip().lower()
if AGENT_MODE not in AGENT_MODES:
    AGENT_MODE = "off"

# ─────────────────────────────────────────────────────────────────────────────
# [US-267 / CA11] Les messages spontanés du compagnon. « oui » : le distributeur
# envoie dans Telegram ce que le veilleur a détecté. Tout autre valeur (défaut
# « non ») : le veilleur détecte toujours, rien ne part. Le retour arrière est ce
# seul réglage, sans redéploiement de code.
# ─────────────────────────────────────────────────────────────────────────────
_VALEURS_OUI = ("oui", "1", "true", "on", "actif")
COMPAGNON_PROACTIF = os.environ.get("COMPAGNON_PROACTIF", "non").strip().lower() in _VALEURS_OUI


def _entier_strictement_positif(nom: str, defaut: int) -> int:
    try:
        valeur = int(os.environ.get(nom, defaut))
    except ValueError:
        return defaut
    return valeur if valeur >= 1 else defaut


AGENT_MAX_TOURS = _entier_strictement_positif("AGENT_MAX_TOURS", 6)

# [US-273 / CA3] Les bornes de l'analyse approfondie, réglables sans redéploiement de code.
# ANALYSE_MAX_TOURS : au plus ce nombre de tours de LECTURE (un tour = un appel du modèle).
# ANALYSE_MAX_JETONS : au-delà de ce cumul de jetons (entrée + sortie), plus aucune lecture ;
# la rédaction finale s'y ajoute. Dans les deux cas, l'analyse rend ce qu'elle a, avec une mention.
ANALYSE_MAX_TOURS = _entier_strictement_positif("ANALYSE_MAX_TOURS", 6)
ANALYSE_MAX_JETONS = _entier_strictement_positif("ANALYSE_MAX_JETONS", 20000)

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
    _ligne("ANALYSE_MAX_TOURS", ANALYSE_MAX_TOURS)
    _ligne("ANALYSE_MAX_JETONS", ANALYSE_MAX_JETONS)
    _ligne("COMPAGNON_PROACTIF", "oui" if COMPAGNON_PROACTIF else "non")

    for type_appel, modele in GROQ_MODELE_PAR_TYPE.items():
        _ligne(f"GROQ_MODEL_{type_appel.upper()}", modele)
    for type_appel, brut in MODELES_ROGNES.items():
        lignes.append(f"   {'GROQ_MODEL_' + type_appel.upper():<30}: ⚠️ « {brut} » rogné au premier "
                      "mot (commentaire sur la ligne de la valeur ?)")
    if VOIX_CATALOGUE and VOIX_PAR_DEFAUT not in {v[0] for v in VOIX_CATALOGUE}:
        lignes.append(f"   {'VOIX_PAR_DEFAUT':<30}: ⚠️ « {VOIX_PAR_DEFAUT} » absente de VOIX_CATALOGUE")
    _ligne("VOIX_PAR_DEFAUT", VOIX_PAR_DEFAUT)
    _ligne("VOIX_FORMATS_A_CONVERTIR", ",".join(sorted(VOIX_FORMATS_A_CONVERTIR)) or "aucun")
    _ligne("VOIX_DICTEE_DUREE_MAX_S", VOIX_DICTEE_DUREE_MAX_S)
    _ligne("VOIX_DICTEE_TAILLE_MAX_KO", VOIX_DICTEE_TAILLE_MAX_KO)
    _ligne("VOIX_PLAFOND_DICTEES_JOUR", VOIX_PLAFOND_DICTEES_JOUR)
    _ligne("VOIX_ORAL_MAX_CARACTERES", VOIX_ORAL_MAX_CARACTERES)
    _ligne("VOIX_PLAFOND_LECTURES_JOUR", VOIX_PLAFOND_LECTURES_JOUR)
    _ligne("GROQ_BASE_URL", GROQ_BASE_URL or "adresse du SDK Groq")
    _ligne("GROQ_MODEL", GROQ_MODEL)
    _ligne("GROQ_WHISPER_MODEL", GROQ_WHISPER_MODEL)
    _ligne("GROQ_REASONING_EFFORT", GROQ_REASONING_EFFORT or "aucun")
    _ligne("MISTRAL_BASE_URL", MISTRAL_BASE_URL or "absente")
    if MISTRAL_API_KEY and not MISTRAL_BASE_URL:
        lignes.append(f"   {'MISTRAL_BASE_URL':<30}: ⚠️ clé Mistral définie mais adresse absente : "
                      "Mistral inutilisable")
    _ligne("VOIX_CATALOGUE", ", ".join(v[0] for v in VOIX_CATALOGUE) or "catalogue Mistral")
    _ligne("FOURNISSEURS_COMPATIBLES", ", ".join(
        f"{nom} → {f['base_url']} (clé {'définie' if f['api_key'] else 'absente'})"
        for nom, f in FOURNISSEURS_COMPATIBLES.items()) or "aucun")
    for ecarte in FOURNISSEURS_ECARTES:
        lignes.append(f"   {'FOURNISSEURS_COMPATIBLES':<30}: ⚠️ écarté : {ecarte}")
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

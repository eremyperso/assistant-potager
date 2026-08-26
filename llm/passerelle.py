"""
llm/passerelle.py — Passerelle unique vers le fournisseur de modèles [US-092]
=============================================================================
*Le LLM est la ressource de dernier recours, pas le moteur central.* Ce module
est l'endroit qui rend ce principe mesurable : **tout** appel à un modèle de
langage (chat comme transcription) transite par ici, y déclare son type et son
tenant, y est mesuré, et y échoue proprement.

Ce que la passerelle garantit
-----------------------------
* **CA1** — point de passage unique : aucun appel direct au client Groq ne
  subsiste ailleurs dans le code applicatif. L'audit est exécutable
  (`python tools/audit_appels_llm.py`) et rejoué par le test
  `test_us092_ca1_aucun_appel_direct_hors_passerelle`.
* **CA2** — aucun appel anonyme : `appel_type` doit appartenir à `TYPES_APPEL`
  et le `TenantContext` doit être fourni avec un `potager_id`, sinon
  `ContexteAppelManquantError` est levée *avant* tout appel réseau.
* **CA3** — le modèle est choisi **par type d'appel**, via les variables
  d'environnement `GROQ_MODEL_<TYPE>` (voir `config.GROQ_MODELE_PAR_TYPE`).
  Changer de modèle pour un type est une opération de configuration.
* **CA4** — la transcription vocale passe par la passerelle (type
  `transcription`), tout en conservant son propre modèle et son propre quota.
* **CA5** — chaque appel alimente la table `conso_tokens` (migration_v31).
  Cette US **mesure**, elle ne plafonne pas : aucun budget, aucun blocage ici.
* **CA6** — les prompts sont assemblés partie fixe en tête, variables en fin,
  pour rester éligibles au cache de prompt du fournisseur. Les jetons servis
  depuis ce cache sont enregistrés séparément (`tokens_cache`) dès que le
  fournisseur les expose.
* **CA8/CA9/CA12** — un 429 est intercepté et converti en
  `QuotaLLMDepasseError` ; un délai dépassé en `DelaiLLMDepasseError` ; une
  panne fournisseur en `FournisseurLLMIndisponibleError`. Les trois héritent de
  `LLMIndisponibleError`, que chaque appelant rattrape pour déclarer son repli
  (à défaut de repli utile : `MESSAGE_REPLI_IA`). Une seule nouvelle tentative
  au maximum, temporisée par l'en-tête `Retry-After`.
* **CA11** — les en-têtes `x-ratelimit-*` renvoyés par le fournisseur sont lus
  au niveau transport (hook httpx) et journalisés. On collecte la matière ; le
  freinage préventif relève de l'US de quotas.
* **CA13** — les journaux de la passerelle ne portent que des métadonnées de
  consommation : jamais de clé, jamais de secret, jamais le contenu d'un prompt
  ou d'un `texte_original`.

Ce que la passerelle ne fait PAS
--------------------------------
* Aucun plafond, aucun budget, aucun blocage au dépassement — périmètre de l'US
  de quotas, qui consommera la table alimentée ici.
* Aucun repli silencieux d'un modèle vers un autre (arbitrage tranché de l'US) :
  un 429 dégrade fonctionnellement, il ne se rejoue jamais en douce ailleurs,
  sans quoi la saturation que cette US existe pour rendre visible resterait
  invisible.
* Aucun BYOK : `_resoudre_client()` est le point d'extension prévu pour
  « quel client pour ce potager ? » (US-143) ; il retourne aujourd'hui toujours
  le client plateforme.

Ordre de grandeur de consommation avant / après (CA7)
------------------------------------------------------
Consigné dans `docs/AUDIT_PASSERELLE_LLM_US092.md` : la passerelle est une
réorganisation à comportement constant — mêmes prompts, mêmes modèles, mêmes
budgets `max_tokens` qu'avant. Le delta attendu est nul en nominal ; le gain
mesurable vient du cache de prompt (CA6), désormais visible appel par appel.
"""
from __future__ import annotations

import contextvars
import logging
import time
from dataclasses import dataclass
from datetime import date
from typing import Optional

import groq
from groq import Groq

from app.services.context import TenantContext, current_context
from config import (
    GROQ_API_KEY,
    GROQ_MODELE_PAR_TYPE,
    GROQ_REASONING_EFFORT,
    GROQ_RETRY_MAX_S,
    GROQ_TIMEOUT_S,
)
from database.db import SessionLocal
from database.models import ConsoTokens

log = logging.getLogger("potager")


# ─────────────────────────────────────────────────────────────────────────────
# Types d'appel [CA2] — un appel qui n'en déclare aucun est refusé
# ─────────────────────────────────────────────────────────────────────────────
TYPE_CLASSIFICATION = "classification"
TYPE_PARSING        = "parsing"
TYPE_QUESTION       = "question"
TYPE_SYNTHESE       = "synthese"
TYPE_TRANSCRIPTION  = "transcription"

TYPES_APPEL: frozenset[str] = frozenset({
    TYPE_CLASSIFICATION, TYPE_PARSING, TYPE_QUESTION, TYPE_SYNTHESE, TYPE_TRANSCRIPTION,
})

# Valeurs de la colonne `conso_tokens.issue` [CA5]
ISSUE_OK      = "ok"
ISSUE_QUOTA   = "quota"
ISSUE_DELAI   = "delai"
ISSUE_ERREUR  = "erreur"


# ─────────────────────────────────────────────────────────────────────────────
# Exceptions typées [CA8, CA12]
# ─────────────────────────────────────────────────────────────────────────────
class AppelLLMError(Exception):
    """Racine des erreurs de la passerelle."""


class ContexteAppelManquantError(AppelLLMError):
    """[CA2] Appel sans type valide ou sans contexte de tenant — refusé avant
    tout appel réseau. Ce n'est PAS une indisponibilité : c'est un défaut de
    programmation, il ne doit jamais être converti en repli utilisateur."""


class LLMIndisponibleError(AppelLLMError):
    """[CA9] Racine des indisponibilités : c'est l'exception que chaque appelant
    rattrape pour déclarer son comportement de repli. Les trois causes possibles
    mènent au même repli utilisateur mais restent distinguables dans les
    journaux — sans quoi le diagnostic de saturation devient impossible."""

    issue = ISSUE_ERREUR


class QuotaLLMDepasseError(LLMIndisponibleError):
    """[CA8] Le fournisseur a répondu 429 (quota dépassé), nouvelle tentative
    comprise."""

    issue = ISSUE_QUOTA


class DelaiLLMDepasseError(LLMIndisponibleError):
    """[CA12] L'appel n'a pas abouti dans le délai maximal configuré."""

    issue = ISSUE_DELAI


class FournisseurLLMIndisponibleError(LLMIndisponibleError):
    """[CA12] Panne réseau ou 5xx du fournisseur, nouvelle tentative comprise."""

    issue = ISSUE_ERREUR


# [CA9] Message invariable servi au jardinier à défaut de repli utile. Jamais un
# silence, jamais un plantage, jamais une réponse inventée.
MESSAGE_REPLI_IA = (
    "L'analyse avancée par IA est temporairement indisponible, "
    "réessaie dans quelques minutes"
)


# ─────────────────────────────────────────────────────────────────────────────
# Réponse normalisée
# ─────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class ReponseLLM:
    """Réponse d'un appel passé par la passerelle, accompagnée de sa mesure."""

    texte: str
    modele: str
    appel_type: str
    tokens_in: int = 0
    tokens_out: int = 0
    tokens_cache: int = 0
    latence_ms: int = 0

    @property
    def tokens_total(self) -> int:
        return self.tokens_in + self.tokens_out


# ─────────────────────────────────────────────────────────────────────────────
# [CA11] En-têtes de limitation de débit — lus au niveau transport
# -----------------------------------------------------------------------------
# Le hook httpx observe TOUTES les réponses du fournisseur, y compris celles qui
# lèvent ensuite une exception SDK (429, 5xx). On mémorise le dernier jeu
# d'en-têtes vu pour le journaliser avec la mesure de l'appel : c'est la matière
# qui permettra, dans l'US de quotas, de freiner *avant* le 429 plutôt que de le
# subir. Aucune décision n'est prise ici.
# ─────────────────────────────────────────────────────────────────────────────
_ENTETES_DEBIT_SUIVIS = (
    "x-ratelimit-limit-requests",
    "x-ratelimit-remaining-requests",
    "x-ratelimit-limit-tokens",
    "x-ratelimit-remaining-tokens",
    "x-ratelimit-reset-requests",
    "x-ratelimit-reset-tokens",
    "retry-after",
)

_derniers_entetes_debit: dict[str, str] = {}


def entetes_debit() -> dict[str, str]:
    """[CA11] Dernier jeu d'en-têtes de limitation de débit observé."""
    return dict(_derniers_entetes_debit)


def _capturer_entetes_debit(reponse) -> None:
    """Hook httpx — mémorise les en-têtes `x-ratelimit-*` de la réponse."""
    try:
        entetes = {
            nom: reponse.headers[nom]
            for nom in _ENTETES_DEBIT_SUIVIS
            if nom in reponse.headers
        }
    except Exception:  # pragma: no cover — un hook ne doit jamais casser l'appel
        return
    if entetes:
        _derniers_entetes_debit.clear()
        _derniers_entetes_debit.update(entetes)


def _creer_client_plateforme() -> Groq:
    """Client Groq de la plateforme.

    `max_retries=0` : la politique de nouvelle tentative est celle de la
    passerelle (CA12 — une seule, temporisée par `Retry-After`), pas celle du
    SDK, qui en tenterait deux de son côté sans que rien n'en soit mesuré.
    """
    try:
        import httpx

        http_client = httpx.Client(
            timeout=GROQ_TIMEOUT_S,
            event_hooks={"response": [_capturer_entetes_debit]},
        )
        return Groq(
            api_key=GROQ_API_KEY,
            max_retries=0,
            timeout=GROQ_TIMEOUT_S,
            http_client=http_client,
        )
    except Exception as e:  # pragma: no cover — filet si httpx change de contrat
        log.warning("⚠️  LLM │ hook d'en-têtes de débit indisponible (%s)", type(e).__name__)
        return Groq(api_key=GROQ_API_KEY, max_retries=0, timeout=GROQ_TIMEOUT_S)


_client = _creer_client_plateforme()


def _resoudre_client(ctx: TenantContext) -> Groq:
    """Point d'extension « quel client pour ce potager ? » (US-143 — BYOK).

    Retourne aujourd'hui **toujours** le client plateforme : la clé propre à un
    potager n'existe pas encore. La fonction est déjà là pour que le branchement
    d'un modèle tiers reste un changement local à la passerelle.
    """
    return _client


# ─────────────────────────────────────────────────────────────────────────────
# Garde de contexte [CA2]
# ─────────────────────────────────────────────────────────────────────────────
def _valider_appel(appel_type: str, ctx: Optional[TenantContext]) -> TenantContext:
    """Refuse tout appel anonyme ou non typé, avant le moindre octet réseau."""
    if appel_type not in TYPES_APPEL:
        raise ContexteAppelManquantError(
            f"type d'appel LLM invalide : {appel_type!r} "
            f"(attendu parmi {sorted(TYPES_APPEL)})"
        )
    if ctx is None or getattr(ctx, "potager_id", None) is None:
        raise ContexteAppelManquantError(
            f"appel LLM '{appel_type}' sans contexte de tenant : "
            "un appel non imputable ne serait compté nulle part"
        )
    return ctx


def modele_pour(appel_type: str) -> str:
    """[CA3] Modèle configuré pour ce type d'appel (variable d'environnement)."""
    if appel_type not in TYPES_APPEL:
        raise ContexteAppelManquantError(f"type d'appel LLM invalide : {appel_type!r}")
    return GROQ_MODELE_PAR_TYPE[appel_type]


# ─────────────────────────────────────────────────────────────────────────────
# Mesure [CA5]
# ─────────────────────────────────────────────────────────────────────────────
def _enregistrer_conso(
    ctx: TenantContext,
    appel_type: str,
    modele: str,
    tokens_in: int,
    tokens_out: int,
    tokens_cache: int,
    latence_ms: int,
    issue: str,
) -> None:
    """Écrit une ligne dans `conso_tokens`. Ne lève jamais : la mesure est de
    l'observabilité, une panne d'écriture ne doit pas casser un appel réussi."""
    db = None
    try:
        db = SessionLocal()
        db.add(ConsoTokens(
            potager_id   = ctx.potager_id,
            user_id      = ctx.user_id,
            date         = date.today(),
            appel_type   = appel_type,
            modele       = modele,
            tokens_in    = tokens_in,
            tokens_out   = tokens_out,
            tokens_cache = tokens_cache,
            latence_ms   = latence_ms,
            issue        = issue,
        ))
        db.commit()
    except Exception as e:
        log.warning("⚠️  CONSO LLM │ enregistrement impossible : %s", type(e).__name__)
        if db is not None:
            try:
                db.rollback()
            except Exception:
                pass
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass


def _journaliser(
    ctx: TenantContext, appel_type: str, modele: str,
    tokens_in: int, tokens_out: int, tokens_cache: int,
    latence_ms: int, issue: str,
) -> None:
    """[CA7, CA11, CA13] Journal de consommation — métadonnées uniquement.
    Aucun prompt, aucun contenu utilisateur, aucune clé n'y transite."""
    log.info(
        "🔌 LLM %-14s │ modele=%s │ potager=%s │ in=%d out=%d cache=%d │ %d ms │ issue=%s",
        appel_type, modele, ctx.potager_id, tokens_in, tokens_out,
        tokens_cache, latence_ms, issue,
    )
    if _derniers_entetes_debit:
        log.info("📉 LLM DEBIT       │ %s", _derniers_entetes_debit)


def _mesurer(usage) -> tuple[int, int, int]:
    """Extrait (tokens_in, tokens_out, tokens_cache) de l'objet `usage` du SDK.

    [CA6] `tokens_cache` reste à 0 tant que le fournisseur n'expose pas les
    jetons servis depuis son cache de prompt ; dès qu'il le fait, ils sont
    distingués ici sans changement d'appelant.
    """
    def _entier(valeur) -> int:
        return valeur if isinstance(valeur, int) else 0

    if usage is None:
        return 0, 0, 0
    tokens_in  = _entier(getattr(usage, "prompt_tokens", None))
    tokens_out = _entier(getattr(usage, "completion_tokens", None))

    details = getattr(usage, "prompt_tokens_details", None)
    tokens_cache = _entier(getattr(details, "cached_tokens", None)) if details is not None else 0
    return tokens_in, tokens_out, tokens_cache


# ─────────────────────────────────────────────────────────────────────────────
# Politique de nouvelle tentative [CA12]
# ─────────────────────────────────────────────────────────────────────────────
def _delai_retry_after(erreur: Exception) -> float:
    """Temporisation à respecter, lue dans l'en-tête `Retry-After` de l'erreur.

    Plafonnée par `GROQ_RETRY_MAX_S` : la passerelle est appelée depuis des
    handlers Telegram et des endpoints HTTP, on ne dort jamais longtemps —
    au-delà, on bascule en mode dégradé, ce qui rend justement la saturation
    visible au lieu de la faire attendre.
    """
    brut = None
    reponse = getattr(erreur, "response", None)
    if reponse is not None:
        try:
            brut = reponse.headers.get("retry-after")
        except Exception:
            brut = None
    if brut is None:
        brut = _derniers_entetes_debit.get("retry-after")
    try:
        delai = float(brut)
    except (TypeError, ValueError):
        delai = 0.5
    return max(0.0, min(delai, GROQ_RETRY_MAX_S))


def _convertir(erreur: Exception) -> LLMIndisponibleError:
    """Convertit une erreur du SDK en exception typée de la passerelle [CA8]."""
    if isinstance(erreur, groq.RateLimitError):
        return QuotaLLMDepasseError("quota du fournisseur de modèles dépassé (429)")
    if isinstance(erreur, groq.APITimeoutError):
        return DelaiLLMDepasseError(f"délai maximal dépassé ({GROQ_TIMEOUT_S} s)")
    return FournisseurLLMIndisponibleError(
        f"fournisseur de modèles indisponible ({type(erreur).__name__})"
    )


def _est_rejouable(erreur: Exception) -> bool:
    """[CA12] Une seule nouvelle tentative, sur 429 et 5xx uniquement.
    Un délai dépassé n'est pas rejoué : il emprunte directement le repli."""
    if isinstance(erreur, groq.RateLimitError):
        return True
    if isinstance(erreur, groq.APITimeoutError):
        return False
    statut = getattr(erreur, "status_code", None)
    return isinstance(statut, int) and statut >= 500


def _executer_avec_repli(appel, ctx: TenantContext, appel_type: str, modele: str):
    """Exécute `appel()` en appliquant la politique CA12 puis, en cas d'échec,
    mesure l'appel raté (CA5 — les échecs sont comptés eux aussi) et lève
    l'exception typée correspondante (CA8)."""
    debut = time.monotonic()
    derniere: Exception | None = None

    for tentative in range(2):  # 1 appel + 1 nouvelle tentative au maximum
        try:
            return appel(), int((time.monotonic() - debut) * 1000)
        except (groq.APIStatusError, groq.APIConnectionError, groq.APITimeoutError) as e:
            derniere = e
            if tentative == 0 and _est_rejouable(e):
                attente = _delai_retry_after(e)
                log.warning(
                    "🔁 LLM %-14s │ %s → nouvelle tentative dans %.1f s",
                    appel_type, type(e).__name__, attente,
                )
                if attente:
                    time.sleep(attente)
                continue
            break

    latence_ms = int((time.monotonic() - debut) * 1000)
    typee = _convertir(derniere)
    _journaliser(ctx, appel_type, modele, 0, 0, 0, latence_ms, typee.issue)
    _enregistrer_conso(ctx, appel_type, modele, 0, 0, 0, latence_ms, typee.issue)
    raise typee from derniere


# ─────────────────────────────────────────────────────────────────────────────
# API publique — chat
# ─────────────────────────────────────────────────────────────────────────────
def appeler_chat(
    *,
    appel_type: str,
    ctx: Optional[TenantContext],
    prompt_fixe: str,
    prompt_variable: str = "",
    message_utilisateur: Optional[str] = None,
    max_tokens: int = 512,
    temperature: float = 0.0,
    reasoning: bool = True,
    role_prompt: str = "system",
) -> ReponseLLM:
    """Unique porte de sortie vers un modèle de chat.

    [CA6] Le prompt est assemblé **partie fixe en tête, variables en fin** :
    `prompt_fixe` (invariant d'un appel à l'autre, donc cacheable côté
    fournisseur) puis `prompt_variable` (date du jour, historique, contexte),
    et enfin `message_utilisateur` dans un message séparé. Les appelants ne
    concatènent jamais eux-mêmes dans l'autre sens.

    Lève `ContexteAppelManquantError` si l'appel n'est pas imputable (CA2), et
    `LLMIndisponibleError` (quota / délai / panne) si le fournisseur n'a pas
    répondu (CA8, CA12).
    """
    ctx = _valider_appel(appel_type, ctx)
    modele = modele_pour(appel_type)
    client = _resoudre_client(ctx)

    contenu_prompt = prompt_fixe + prompt_variable
    if message_utilisateur is None:
        messages = [{"role": role_prompt, "content": contenu_prompt}]
    else:
        messages = [
            {"role": "system", "content": contenu_prompt},
            {"role": "user",   "content": message_utilisateur},
        ]

    kwargs = {
        "model": modele,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if reasoning and GROQ_REASONING_EFFORT:
        kwargs["reasoning_effort"] = GROQ_REASONING_EFFORT

    chat, latence_ms = _executer_avec_repli(
        lambda: client.chat.completions.create(**kwargs), ctx, appel_type, modele
    )

    tokens_in, tokens_out, tokens_cache = _mesurer(getattr(chat, "usage", None))
    _journaliser(ctx, appel_type, modele, tokens_in, tokens_out, tokens_cache, latence_ms, ISSUE_OK)
    _enregistrer_conso(ctx, appel_type, modele, tokens_in, tokens_out, tokens_cache,
                       latence_ms, ISSUE_OK)

    # [US-097 / CA5] Alimente l'accumulateur de cascade s'il est armé — voir
    # demarrer_mesure_cascade(). N'a aucun effet hors d'une cascade en cours.
    accumulateur = _accumulateur_cascade.get()
    if accumulateur is not None:
        accumulateur[0] += tokens_in + tokens_out

    contenu = chat.choices[0].message.content
    return ReponseLLM(
        texte        = (contenu or "").strip(),
        modele       = modele,
        appel_type   = appel_type,
        tokens_in    = tokens_in,
        tokens_out   = tokens_out,
        tokens_cache = tokens_cache,
        latence_ms   = latence_ms,
    )


# ─────────────────────────────────────────────────────────────────────────────
# API publique — transcription [CA4]
# ─────────────────────────────────────────────────────────────────────────────
def transcrire(
    *,
    ctx: Optional[TenantContext],
    chemin_fichier: str,
    nom_fichier: str = "audio.ogg",
    langue: str = "fr",
) -> ReponseLLM:
    """Transcription vocale — même passerelle, même mesure, même mode dégradé.

    [CA4] Le modèle et le quota restent propres à la transcription (Whisper est
    compté séparément côté fournisseur) : c'est précisément le quota qui
    saturera le premier en usage vocal, et il serait invisible hors passerelle.
    Le nombre de jetons n'a pas de sens ici (facturation à la seconde d'audio) :
    la ligne `conso_tokens` porte la latence et l'issue, jetons à zéro.
    """
    ctx = _valider_appel(TYPE_TRANSCRIPTION, ctx)
    modele = modele_pour(TYPE_TRANSCRIPTION)
    client = _resoudre_client(ctx)

    def _appel():
        with open(chemin_fichier, "rb") as audio:
            return client.audio.transcriptions.create(
                file=(nom_fichier, audio),
                model=modele,
                language=langue,
                response_format="text",
            )

    brut, latence_ms = _executer_avec_repli(_appel, ctx, TYPE_TRANSCRIPTION, modele)

    _journaliser(ctx, TYPE_TRANSCRIPTION, modele, 0, 0, 0, latence_ms, ISSUE_OK)
    _enregistrer_conso(ctx, TYPE_TRANSCRIPTION, modele, 0, 0, 0, latence_ms, ISSUE_OK)

    return ReponseLLM(
        texte      = (brut or "").strip(),
        modele     = modele,
        appel_type = TYPE_TRANSCRIPTION,
        latence_ms = latence_ms,
    )


# ─────────────────────────────────────────────────────────────────────────────
# [US-097 / CA5] Mesure des jetons d'une cascade complète (routage inclus)
# -----------------------------------------------------------------------------
# `conso_tokens` compte chaque appel isolément ; le routeur (`llm/routeur.py`)
# a besoin du TOTAL des jetons consommés pour produire UNE réponse, y compris
# l'appel de classification qui la précède. Plutôt qu'une nouvelle table ou un
# identifiant de corrélation à threader partout, un accumulateur de contexte
# borné à la durée de la cascade suffit : `demarrer_mesure_cascade()` l'arme,
# chaque `appeler_chat()` qui s'exécute pendant que l'accumulateur est actif y
# ajoute ses jetons, `cumul_mesure_cascade()` lit le total et désarme.
# ─────────────────────────────────────────────────────────────────────────────
_accumulateur_cascade: "contextvars.ContextVar[Optional[list[int]]]" = contextvars.ContextVar(
    "accumulateur_tokens_cascade", default=None
)


def demarrer_mesure_cascade() -> contextvars.Token:
    """[US-097] Arme l'accumulateur pour la cascade en cours. Retourne un jeton
    à passer à `cumul_mesure_cascade()` une fois la cascade terminée."""
    return _accumulateur_cascade.set([0])


def cumul_mesure_cascade(jeton: contextvars.Token) -> int:
    """[US-097] Total des jetons consommés depuis `demarrer_mesure_cascade()`,
    puis désarme l'accumulateur (restaure l'état précédent)."""
    accumulateur = _accumulateur_cascade.get()
    total = accumulateur[0] if accumulateur else 0
    _accumulateur_cascade.reset(jeton)
    return total


def contexte_courant() -> TenantContext:
    """Contexte tenant à imputer quand l'appelant n'en fournit pas explicitement.

    [CA2] Ce n'est PAS une dérogation à l'interdiction des appels anonymes :
    `current_context()` (US-046) résout le potager actif réellement armé pour
    l'Update / la requête en cours. La passerelle, elle, refuse toujours un
    contexte absent.
    """
    return current_context()

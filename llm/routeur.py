"""
llm/routeur.py — Routeur des demandes, règles avant tout appel au LLM [US-093]
================================================================================
Enrichissement de la classification d'intention existante (`bot.classify_intent`,
`bot._is_question`) : ce module ajoute la distinction *data / savoir / hybride*
au-dessus de ce qui distingue déjà action et question. Il ne remplace rien de
l'existant, il vient s'insérer **après** les gardes de conversation (modes
`corr_*`, mode `ask`, navigation, `_is_question`) — jamais avant (CA13).

Principe : **les règles d'abord** (CA2). Le modèle n'est sollicité que si les
règles et le cache échouent (CA4) — un routeur qui appellerait le LLM à chaque
message contredirait son propre objectif de coût. Le résultat d'un appel modèle
alimente un cache en mémoire (CA3) : borné, éviction par ancienneté, **pas** en
base ni Redis — une classification est peu coûteuse à reconstituer après un
redémarrage, et Redis relève de l'US d'état conversationnel persistant (non
livrée). Le passage à Redis se ferait sans changement de contrat le jour venu.

Remontée de cascade (CA6/CA7/CA8) : un étage qui ne produit pas de réponse
exploitable rend la main à l'étage suivant, une fois — jamais par exception,
jamais par interprétation à distance d'une réponse vide. C'est pour cela que
`app.services.questions.repondre_question_avec_confiance` et
`llm.sql_agent.query_agent_answer_avec_confiance` renvoient explicitement un
booléen `confiant` : la décision « je n'ai pas su » est prise à la source, pas
reconstituée ici en inspectant le texte produit. Aucun message intermédiaire
(« je cherche ailleurs ») n'est jamais visible du jardinier (CA8).

Portée volontairement limitée à ce que le code sait déjà faire aujourd'hui :
l'étage 2 (RAG / connaissance, US-098) et l'étage 3 (raisonnement multi-sources,
US-142) ne sont pas encore construits. Les natures SAVOIR et HYBRIDE utilisent
donc dès maintenant le seul étage de raisonnement disponible — un appel direct
au modèle via la passerelle, éventuellement enrichi du contexte data quand il
existe (HYBRIDE) — en attendant que ces étages soient livrés séparément. Le
contrat de `classer_demande`/`repondre_avec_cascade` ne change pas ce jour-là :
seul l'intérieur du branchement SAVOIR/HYBRIDE sera enrichi.

[CA12] Coût moyen recalculé, routage inclus : les demandes aiguillées par une
règle ou par le cache coûtent 0 jeton de routage (l'écrasante majorité, c'est
tout l'objet de CA2/CA3). Seule une demande ambiguë (ni règle, ni cache) coûte
un appel de classification (~15 jetons de sortie, prompt fixe caché côté
fournisseur) avant même d'atteindre l'étage qui répond. L'estimation de ~180
jetons/question du document d'architecture (§7.1), qui omettait ce coût, doit
donc être lue comme "~180 jetons + coût de routage sur la frange ambiguë",
frange que le corpus de `tests/test_us093_routeur_regles_first.py` mesure.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Optional

from unidecode import unidecode

from app.services.context import TenantContext
from database.db import SessionLocal
from database.models import RoutageLog
from llm import passerelle

log = logging.getLogger("potager")


# ─────────────────────────────────────────────────────────────────────────────
# Natures de demande [CA1]
# ─────────────────────────────────────────────────────────────────────────────
NATURE_ACTION           = "ACTION"
NATURE_QUESTION_DATA    = "QUESTION_DATA"
NATURE_QUESTION_SAVOIR  = "QUESTION_SAVOIR"
NATURE_QUESTION_HYBRIDE = "QUESTION_HYBRIDE"

NATURES: frozenset[str] = frozenset({
    NATURE_ACTION, NATURE_QUESTION_DATA, NATURE_QUESTION_SAVOIR, NATURE_QUESTION_HYBRIDE,
})

# Origine de la décision — matière première de l'US-097 (CA11)
ORIGINE_REGLE  = "regle"
ORIGINE_CACHE  = "cache"
ORIGINE_MODELE = "modele"

# [CA5] En dessous de ce seuil, la confiance du petit modèle est jugée trop
# faible : on préfère une réponse un peu plus chère (étage hybride) à une
# non-réponse forcée dans un étage trop étroit.
SEUIL_CONFIANCE_FAIBLE = 0.6

# [US-097 / CA1] Étage ayant produit la réponse FINALE — distinct de l'origine
# de la classification (regle/cache/modele ci-dessus). ETAGE_SAVOIR est déjà
# défini pour le contrat de journalisation, mais n'est encore jamais écrit :
# l'étage 2 (RAG, US-098) n'existe pas, les demandes SAVOIR sont aujourd'hui
# honnêtement journalisées sous ETAGE_RAISONNEMENT (voir repondre_avec_cascade)
# — c'est précisément l'écart que CA6 doit publier tel quel.
ETAGE_DONNEE       = "donnee"
ETAGE_SAVOIR       = "savoir"
ETAGE_RAISONNEMENT = "raisonnement"


@dataclass(frozen=True)
class DecisionRoutage:
    """[CA11] Décision de routage — journalisée telle quelle à chaque demande."""

    nature: str
    origine: str      # "regle" | "cache" | "modele"
    confiance: float
    latence_ms: int = 0


# ─────────────────────────────────────────────────────────────────────────────
# Étage 0 — règles [CA2]
# -----------------------------------------------------------------------------
# Auto-suffisant (ne réutilise PAS bot.ACTION_VERBS / bot.QUESTION_STARTERS) :
# bot.py importe déjà des modules de llm/, un import inverse créerait un cycle.
# Les motifs ci-dessous reprennent volontairement le même esprit.
# ─────────────────────────────────────────────────────────────────────────────

_VERBES_ACTION: tuple[str, ...] = (
    "arros", "semé", "semer", "planté", "planter", "récolté", "récolter",
    "cueilli", "cueillir", "ramassé", "ramasser", "repiqué", "repiquer",
    "traité", "traiter", "désherbé", "désherber", "paillé", "pailler",
    "taillé", "tailler", "tuteurer", "tuteuré", "fertilisé", "fertiliser",
    "observé", "observer", "constaté", "constater", "mis en", "mis ",
    "posé", "appliqué", "installé", "sorti",
)

# [CA2] "il me reste combien de tomates ?" — demande explicitement une donnée
# personnelle qui exige néanmoins un raisonnement d'opinion → priorité maximale.
_MARQUEURS_HYBRIDE: tuple[str, ...] = (
    "qu'en penses-tu", "qu en penses-tu", "que penses-tu", "à ton avis",
    "a ton avis", "un conseil", "que me conseilles-tu", "que dois-je faire",
    "que faire d'après toi", "que faire d'apres toi",
)

# [CA2] Connaissance générale — agronomie ou fonctionnement de l'application,
# indépendante des événements propres au potager qui pose la question.
_MARQUEURS_SAVOIR: tuple[str, ...] = (
    "pourquoi mes", "pourquoi ma", "pourquoi mon", "pourquoi les",
    "comment fonctionne", "comment faire", "comment planter", "comment semer",
    "comment soigner", "comment reconnaitre", "comment reconnaître",
    "comment eviter", "comment éviter", "comment arroser", "comment calcul",
    "c'est quoi", "c est quoi", "qu'est-ce que", "qu est ce que",
    "à quelle profondeur", "a quelle profondeur", "quelle est la meilleure",
    "quelle distance", "quelle variété choisir", "difference entre",
    "différence entre", "que faire contre", "traitement contre",
)

# [CA2] Consultation d'une donnée déjà enregistrée dans CE potager.
_MARQUEURS_DATA: tuple[str, ...] = (
    "combien de", "combien ai-je", "combien j'ai", "quand ai-je", "quand j'ai",
    "il me reste", "il me manque", "stock de", "mon stock", "mes stocks",
    "ma récolte", "mes récoltes", "dernière récolte", "dernier arrosage",
    "dernière plantation", "dernier semis", "historique de mes",
    "historique de ma", "historique de mon", "quelle quantité de mes",
    "quelle quantité de ma", "date de mes", "date de ma", "liste de mes",
    "liste de mon", "mes plantations", "mes semis", "mes traitements",
)


def _regle_par_mots_cles(texte: str) -> Optional[str]:
    """[CA2] Retourne la nature si un motif fréquent et non ambigu matche,
    sinon `None` (la demande passe alors au cache puis au modèle)."""
    t = (texte or "").strip().lower()
    if not t:
        return None
    if t.startswith("/"):
        return NATURE_ACTION
    if t.startswith(_VERBES_ACTION) and not t.endswith("?"):
        return NATURE_ACTION
    if any(m in t for m in _MARQUEURS_HYBRIDE):
        return NATURE_QUESTION_HYBRIDE
    if any(m in t for m in _MARQUEURS_SAVOIR):
        return NATURE_QUESTION_SAVOIR
    if any(m in t for m in _MARQUEURS_DATA):
        return NATURE_QUESTION_DATA
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Normalisation [CA3] — réutilise le procédé déjà en place pour les noms de
# parcelles/cultures (strip + lower + unidecode, voir utils/parcelles.py),
# étendu à la ponctuation puisqu'il porte ici sur une phrase entière et non un
# simple nom (les espaces séparant les mots sont conservés, eux).
# ─────────────────────────────────────────────────────────────────────────────
_PONCTUATION = re.compile(r"[^\w\s]", re.UNICODE)
_ESPACES_MULTIPLES = re.compile(r"\s+")


def _normaliser_question(texte: str) -> str:
    s = unidecode((texte or "").strip().lower())
    s = _PONCTUATION.sub("", s)
    s = _ESPACES_MULTIPLES.sub(" ", s).strip()
    return s


# ─────────────────────────────────────────────────────────────────────────────
# Étage 0bis — cache de classification [CA3]
# -----------------------------------------------------------------------------
# En mémoire du processus, borné, éviction par ancienneté. Alimenté uniquement
# par les décisions issues du modèle (les décisions par règle sont déjà
# gratuites — les mettre en cache n'apporterait rien).
# ─────────────────────────────────────────────────────────────────────────────
_TTL_CACHE_S = 24 * 3600
_CACHE_MAX_ENTREES = 2000

_cache: dict[str, tuple[DecisionRoutage, float]] = {}


def _cache_lire(cle: str) -> Optional[DecisionRoutage]:
    entree = _cache.get(cle)
    if entree is None:
        return None
    decision, pose_a = entree
    if time.time() - pose_a > _TTL_CACHE_S:
        _cache.pop(cle, None)
        return None
    return decision


def _cache_ecrire(cle: str, decision: DecisionRoutage) -> None:
    if len(_cache) >= _CACHE_MAX_ENTREES and cle not in _cache:
        plus_ancienne = min(_cache, key=lambda k: _cache[k][1])
        _cache.pop(plus_ancienne, None)
    _cache[cle] = (decision, time.time())


def vider_cache() -> None:
    """Utilitaire de test — vide le cache de classification en mémoire."""
    _cache.clear()


# ─────────────────────────────────────────────────────────────────────────────
# Étage modèle — classification par le petit modèle rapide [CA4, CA5, CA14]
# -----------------------------------------------------------------------------
# Passe par la passerelle unique (US-092), `appel_type=TYPE_CLASSIFICATION` :
# c'est ce type d'appel qui résout déjà vers le petit modèle rapide configuré
# (GROQ_MODEL_CLASSIFICATION), avec repli grand modèle possible par simple
# configuration (CA14) — jamais en dur ici.
# ─────────────────────────────────────────────────────────────────────────────
_PROMPT_FIXE_ROUTEUR = """Tu es le routeur de l'assistant potager. Classe le message ci-dessous en une seule des quatre natures suivantes :

ACTION            : décrit une action potager déjà réalisée (semis, arrosage, récolte...)
QUESTION_DATA     : demande une donnée déjà enregistrée dans CE potager (stock, historique, quantité)
QUESTION_SAVOIR    : demande une connaissance générale (agronomie, maladies, fonctionnement de l'application)
QUESTION_HYBRIDE  : mélange une donnée personnelle et une demande de raisonnement/diagnostic/conseil

Réponds STRICTEMENT au format : NATURE|CONFIANCE
où NATURE est un des quatre mots ci-dessus et CONFIANCE un nombre entre 0 et 1.
Exemple de réponse : QUESTION_DATA|0.92
"""


def _parser_reponse_modele(brut: str) -> tuple[str, float]:
    parts = (brut or "").strip().upper().split("|")
    nature = parts[0].strip() if parts else ""
    if nature not in NATURES:
        return NATURE_QUESTION_HYBRIDE, 0.0
    confiance = 0.5
    if len(parts) > 1:
        try:
            confiance = max(0.0, min(1.0, float(parts[1].strip())))
        except ValueError:
            confiance = 0.5
    return nature, confiance


def _appeler_modele_classification(texte: str, ctx: Optional[TenantContext]) -> tuple[str, float]:
    """N'échoue jamais vers l'appelant : une classification indisponible se
    replie sur QUESTION_HYBRIDE à confiance nulle (le doute profite à la
    réponse, jamais à l'économie — même logique que CA5)."""
    try:
        reponse = passerelle.appeler_chat(
            appel_type=passerelle.TYPE_CLASSIFICATION,
            ctx=ctx,
            prompt_fixe=_PROMPT_FIXE_ROUTEUR,
            prompt_variable="",
            message_utilisateur=texte,
            max_tokens=16,
            reasoning=False,
            role_prompt="user",
        )
        return _parser_reponse_modele(reponse.texte)
    except Exception as e:
        log.warning(f"⚠️ ROUTEUR MODELE  : classification indisponible ({type(e).__name__}) → repli HYBRIDE")
        return NATURE_QUESTION_HYBRIDE, 0.0


def _journaliser(texte: str, decision: DecisionRoutage) -> None:
    """[CA11] Une ligne par décision : nature, origine, confiance, latence."""
    log.info(
        "🧭 ROUTEUR         │ origine=%-6s │ nature=%-17s │ confiance=%.2f │ %d ms │ '%s'",
        decision.origine, decision.nature, decision.confiance, decision.latence_ms,
        texte[:80],
    )


# ─────────────────────────────────────────────────────────────────────────────
# API publique — classification [CA1 → CA5]
# ─────────────────────────────────────────────────────────────────────────────
def classer_demande(texte: str, ctx: Optional[TenantContext] = None) -> DecisionRoutage:
    """Classe une demande entrante en une des quatre natures (CA1).

    Ordre strict : règles (CA2) → cache (CA3) → modèle (CA4). Le modèle n'est
    donc appelé que pour la frange réellement ambiguë. `ctx` n'est nécessaire
    que si l'appel modèle a lieu — les chemins règle/cache n'y touchent jamais.
    """
    debut = time.monotonic()
    texte_brut = texte or ""

    nature_regle = _regle_par_mots_cles(texte_brut)
    if nature_regle is not None:
        decision = DecisionRoutage(
            nature=nature_regle, origine=ORIGINE_REGLE, confiance=1.0,
            latence_ms=int((time.monotonic() - debut) * 1000),
        )
        _journaliser(texte_brut, decision)
        return decision

    cle = _normaliser_question(texte_brut)
    en_cache = _cache_lire(cle)
    if en_cache is not None:
        decision = DecisionRoutage(
            nature=en_cache.nature, origine=ORIGINE_CACHE, confiance=en_cache.confiance,
            latence_ms=int((time.monotonic() - debut) * 1000),
        )
        _journaliser(texte_brut, decision)
        return decision

    nature, confiance = _appeler_modele_classification(texte_brut, ctx)
    if confiance < SEUIL_CONFIANCE_FAIBLE:
        nature = NATURE_QUESTION_HYBRIDE  # [CA5]
    decision = DecisionRoutage(
        nature=nature, origine=ORIGINE_MODELE, confiance=confiance,
        latence_ms=int((time.monotonic() - debut) * 1000),
    )
    _cache_ecrire(cle, decision)
    _journaliser(texte_brut, decision)
    return decision


# ─────────────────────────────────────────────────────────────────────────────
# Étage raisonnement — seul étage de savoir/synthèse disponible aujourd'hui
# (US-098/US-142 non livrées, voir docstring de module) [CA6]
# ─────────────────────────────────────────────────────────────────────────────
_PROMPT_FIXE_RAISONNEMENT = """Tu es l'assistant d'un potager amateur. Réponds à la question de jardinage
posée, de façon concise et concrète (2 à 4 phrases). Si un contexte de données
du potager est fourni, appuie-toi dessus ; sinon réponds depuis tes
connaissances générales d'agronomie ou de fonctionnement de l'application."""


def _repondre_raisonnement(ctx: TenantContext, question: str, contexte_donnees: str = "") -> str:
    """Étage de dernier recours : raisonnement/savoir général via la passerelle.
    Peut lever `LLMIndisponibleError` — volontairement non rattrapée ici, pour
    que l'appelant (bot._ask_question) affiche le même repli dégradé standard
    qu'aujourd'hui (US-092), sans dupliquer ce message."""
    message = question
    if contexte_donnees:
        message = f"{question}\n\nDonnées du potager déjà connues : {contexte_donnees}"
    reponse = passerelle.appeler_chat(
        appel_type=passerelle.TYPE_QUESTION,
        ctx=ctx,
        prompt_fixe=_PROMPT_FIXE_RAISONNEMENT,
        prompt_variable="",
        message_utilisateur=message,
        max_tokens=400,
        reasoning=True,
        role_prompt="user",
    )
    return reponse.texte


@dataclass(frozen=True)
class ReponseCascade:
    """[US-097] Réponse enrichie des métadonnées nécessaires à l'observabilité
    et au retour du jardinier (CA9-CA10). `texte` reste le seul élément visible
    du jardinier ; `etage_resolveur` et `routage_log_id` servent à bot.py/main.py
    pour proposer les boutons 👍/👎 et les rattacher à l'entrée de journal.
    `routage_log_id` est `None` si l'écriture du journal a échoué — l'échec de
    l'écriture ne doit jamais empêcher la réponse d'être servie (note technique
    de l'US), il désactive simplement le retour pour cette réponse-là."""

    texte: str
    etage_resolveur: str
    routage_log_id: Optional[int]


def _persister_routage_log(
    ctx: TenantContext,
    question: str,
    decision: DecisionRoutage,
    etage_resolveur: str,
    cascade_remontee: bool,
    latence_ms: int,
    tokens_consommes: int,
) -> Optional[int]:
    """[CA1, CA2, CA4] Écrit une ligne dans `routage_logs`. Ne lève jamais : la
    journalisation est de l'observabilité, une panne d'écriture ne doit pas
    faire échouer une réponse déjà produite."""
    db = None
    try:
        db = SessionLocal()
        entree = RoutageLog(
            potager_id=ctx.potager_id,
            question_normalisee=_normaliser_question(question),
            nature=decision.nature,
            origine_classification=decision.origine,
            etage_resolveur=etage_resolveur,
            cascade_remontee=cascade_remontee,
            confiance=decision.confiance,
            latence_ms=latence_ms,
            tokens_consommes=tokens_consommes,
        )
        db.add(entree)
        db.commit()
        db.refresh(entree)
        return entree.id
    except Exception as e:
        log.warning("⚠️  ROUTAGE LOG    │ enregistrement impossible : %s", type(e).__name__)
        if db is not None:
            try:
                db.rollback()
            except Exception:
                pass
        return None
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# API publique — cascade complète [CA6, CA7, CA8]
# ─────────────────────────────────────────────────────────────────────────────
def repondre_avec_cascade(ctx: TenantContext, question: str) -> ReponseCascade:
    """Classe la demande puis produit une réponse, avec au plus une remontée
    de cascade (CA7). Ne renvoie jamais de message intermédiaire — seule la
    réponse finale est visible du jardinier (CA8).

    [US-097 / CA1] Journalise la cascade dans `routage_logs` une fois la
    réponse produite (succès uniquement — une cascade qui lève une exception,
    ex. `LLMIndisponibleError`, n'a rien à journaliser : aucune réponse n'a été
    servie). Le total de jetons journalisé (CA5) couvre tout appel modèle
    déclenché pendant la cascade, y compris la classification elle-même
    (`passerelle.demarrer_mesure_cascade`/`cumul_mesure_cascade`)."""
    from app.services.questions import repondre_question_avec_confiance

    debut = time.monotonic()
    jeton_mesure = passerelle.demarrer_mesure_cascade()
    decision = classer_demande(question, ctx)
    cascade_remontee = False
    etage_resolveur = ETAGE_RAISONNEMENT

    try:
        if decision.nature == NATURE_QUESTION_DATA:
            texte, confiant = repondre_question_avec_confiance(ctx, question)
            if confiant:
                etage_resolveur = ETAGE_DONNEE
            else:
                log.info(f"↪️ ROUTEUR REMONTÉE : donnée non exploitable → raisonnement (1 saut) : '{question[:80]}'")
                cascade_remontee = True
                texte = _repondre_raisonnement(ctx, question)
        elif decision.nature == NATURE_QUESTION_SAVOIR:
            # [CA6] Étage 2 (RAG, US-098) non livré — journalisé honnêtement
            # sous ETAGE_RAISONNEMENT, voir docstring d'ETAGE_SAVOIR ci-dessus.
            texte = _repondre_raisonnement(ctx, question)
        else:
            # QUESTION_HYBRIDE (et ACTION mal aiguillée jusqu'ici) : tente
            # d'enrichir le raisonnement avec la donnée si elle existe, sans
            # remontée dédiée — cet étage héberge déjà le raisonnement, un
            # second saut n'aurait pas de sens.
            texte_donnees, confiant = repondre_question_avec_confiance(ctx, question)
            texte = _repondre_raisonnement(ctx, question, contexte_donnees=texte_donnees if confiant else "")
    except Exception:
        passerelle.cumul_mesure_cascade(jeton_mesure)  # désarme sans persister
        raise

    latence_ms = int((time.monotonic() - debut) * 1000)
    tokens_consommes = passerelle.cumul_mesure_cascade(jeton_mesure)
    routage_log_id = _persister_routage_log(
        ctx, question, decision, etage_resolveur, cascade_remontee, latence_ms, tokens_consommes,
    )
    return ReponseCascade(texte=texte, etage_resolveur=etage_resolveur, routage_log_id=routage_log_id)

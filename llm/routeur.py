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
from utils.actions import ACTION_MAP

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
    # [US-096] Formulations servies par un gabarit sur agrégat SQL, à coût nul.
    # Sans ces marqueurs, elles tombaient dans la frange ambiguë : le routeur
    # payait une classification, puis l'étage hybride payait un raisonnement —
    # pour une question dont la réponse exacte était déjà calculable en SQL.
    # Constaté en usage réel le 26/08/2026 sur « qu'est-ce qu'il y a en
    # pépinière ? » et « quel est le rendement de la saison ? ».
    "pépinière", "pepiniere", "en godet", "mes godets", "semis en cours",
    "rendement", "ma production", "mes récoltes", "combien de pieds",
    "combien de plants", "où en sont", "ou en sont", "où en est", "ou en est",
    "dans la parcelle", "sur la parcelle", "occupation",
)


# Nombre de mots de tête examinés par `_regle_par_geste`. Une saisie annonce
# son geste d'emblée (« mise en godet 20 tomates ») ; une question de savoir
# ne le mentionne, s'il apparaît, que dans une subordonnée de contexte
# (« … sur les tiges après la récolte »). Quatre mots suffisent à couvrir
# « mise en godet » sans mordre sur la subordonnée : mesuré le 27/08/2026 sur
# les 205 saisies de production (97 % captées) et les 44 questions du corpus
# CA11 (2 faux positifs). Élargir à 5 mots n'apporte rien.
_FENETRE_GESTE_MOTS = 4


def _construire_motif_geste() -> "re.Pattern[str]":
    """Motif des gestes de jardinage, bâti sur `utils.actions.ACTION_MAP`.

    Le référentiel lexical du parseur est réutilisé tel quel plutôt que
    recopié : deux listes de gestes divergeraient à la première action
    ajoutée, et la divergence ne se verrait pas — elle se paierait en saisies
    routées vers une réponse au lieu d'être enregistrées.

    [US-168 CA13] Le supplément temporaire `_GESTES_HORS_REFERENTIEL` (gestes
    attestés en production mais absents d'ACTION_MAP — binage, eclaircie,
    pluriels, coquilles de transcription...) a disparu : ses entrées ont été
    versées dans ACTION_MAP (utils/actions.py), le référentiel unique. Ce motif
    n'a donc plus qu'une seule source lexicale.
    """
    gestes: set[str] = set()
    for canonique, variantes in ACTION_MAP.items():
        for forme in (canonique, *variantes):
            gestes.add(unidecode(forme.lower().replace("_", " ")).strip())
    gestes.discard("")
    # Les plus longs d'abord : « mise en godet » doit l'emporter sur « godet ».
    alternatives = "|".join(re.escape(g) for g in sorted(gestes, key=len, reverse=True))
    return re.compile(rf"\b({alternatives})\b")


_MOTIF_GESTE = _construire_motif_geste()


def _regle_par_geste(texte: str) -> Optional[str]:
    """[Action 0] ACTION si l'un des premiers mots nomme un geste de jardinage.

    Comble le trou entre `_VERBES_ACTION` — un test de préfixe, qui n'attrape
    donc pas les formes nominales (« plantation 14 plants… ») — et les
    marqueurs DATA, testés eux par sous-chaîne n'importe où dans la phrase.
    Une saisie qui ne commençait pas par un verbe connu tombait de ce fait
    dans un marqueur DATA fortuit : « mise en godet 20 tomates » était classée
    QUESTION_DATA par « en godet », et le jardinier recevait un agrégat SQL au
    lieu de voir son évènement enregistré. 28 saisies sur 205 dans ce cas.

    Testée APRÈS les marqueurs HYBRIDE et SAVOIR, qui sont explicites et
    gardent la priorité, mais AVANT les marqueurs DATA et le catalogue.
    """
    tete = " ".join(unidecode((texte or "").strip().lower()).split()[:_FENETRE_GESTE_MOTS])
    return NATURE_ACTION if tete and _MOTIF_GESTE.search(tete) else None


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
    nature_geste = _regle_par_geste(t)
    if nature_geste is not None and not t.endswith("?"):
        return nature_geste
    if any(m in t for m in _MARQUEURS_DATA):
        return NATURE_QUESTION_DATA
    return None


def _regle_par_catalogue(texte: str, ctx: Optional[TenantContext]) -> Optional[str]:
    """[US-096] Le catalogue de réponses chiffrées est lui-même une règle.

    Si `app.services.reponses_chiffrees` reconnaît une de ses familles, la
    demande porte sur les données du potager — par construction, sans qu'aucune
    liste de mots-clés n'ait à le prévoir ici. C'est ce qui évite d'entretenir
    deux listes de motifs, celle du routeur et celle du catalogue, qui
    divergeraient dès la première famille ajoutée.

    Coût : deux lectures SQL brèves, zéro jeton — à comparer à l'appel de
    classification qu'elle remplace. N'est consultée qu'après les mots-clés
    ci-dessus, qui, eux, ne touchent pas la base.
    """
    if ctx is None:
        return None
    try:
        # Import local : `app.services` importe déjà `llm`, un import de module
        # créerait un cycle.
        from app.services.reponses_chiffrees import reconnait_famille

        return NATURE_QUESTION_DATA if reconnait_famille(ctx, texte) else None
    except Exception as e:
        log.debug("ROUTEUR CATALOGUE : indisponible (%s)", type(e).__name__)
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
# [Action 0, vague 2] La formulation « mélange une donnée personnelle et une
# demande de raisonnement » faisait basculer en HYBRIDE toute question portant
# un possessif : « mes salades sont mangées la nuit » était classée HYBRIDE à
# 0,93 de confiance, alors qu'y répondre (les limaces) ne demande aucune donnée
# enregistrée. Mesuré le 27/08/2026 sur le corpus CA11 : 40 questions de savoir
# sur 44 aiguillées vers HYBRIDE. Le discriminant explicité ci-dessous est donc
# « faut-il LIRE l'historique pour répondre ? », et non « le message parle-t-il
# de SES plantes ? » — un symptôme décrit est du contexte, pas une donnée.
_PROMPT_FIXE_ROUTEUR = """Tu es le routeur de l'assistant potager. Classe le message ci-dessous en une seule des quatre natures suivantes :

ACTION            : décrit une action potager déjà réalisée (semis, arrosage, récolte...)
QUESTION_DATA     : demande une donnée déjà enregistrée dans CE potager (stock, historique, quantité, dates)
QUESTION_SAVOIR   : demande une connaissance générale (agronomie, maladies, ravageurs, fonctionnement de l'application)
QUESTION_HYBRIDE  : exige À LA FOIS de consulter les données enregistrées du potager ET de raisonner dessus

Test décisif entre QUESTION_SAVOIR et QUESTION_HYBRIDE : pour répondre, faut-il aller
LIRE l'historique enregistré du potager (dates, quantités, parcelles) ? Si non, la
réponse est QUESTION_SAVOIR. Un possessif (« mes tomates », « mon ail ») ne suffit PAS
à rendre une question hybride : décrire un symptôme que l'on observe, c'est fournir du
contexte, ce n'est pas interroger une donnée enregistrée.

Exemples :
mes salades sont mangées la nuit, il reste que le trognon -> QUESTION_SAVOIR|0.9
mes semis de tomates font des tiges toutes fines et molles -> QUESTION_SAVOIR|0.9
combien de tomates ai-je récolté cette saison ? -> QUESTION_DATA|0.95
mes courgettes jaunissent et j'ai beaucoup arrosé cette semaine, qu'en penses-tu ? -> QUESTION_HYBRIDE|0.9

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
            # ⚠️ NE PAS DESCENDRE SOUS ~120, et NE PAS REPASSER À
            # `reasoning=False` : les deux réglages se tiennent.
            #
            # `openai/gpt-oss-120b` émet des jetons de raisonnement AVANT son
            # contenu, et `max_tokens` plafonne les deux ensemble. À 16 — la
            # valeur d'origine, calibrée sur la réponse « NATURE|confiance »
            # qui tient en 8 jetons — le budget partait intégralement dans le
            # raisonnement : le contenu revenait vide, `_parser_reponse_modele`
            # repliait sur QUESTION_HYBRIDE/0.0, et l'étage modèle n'a jamais
            # rien classé. Mesuré le 27/08/2026 : 210 classifications, toutes à
            # confiance 0.00, `issue=ok`, `tokens_out=16` exactement.
            #
            # `reasoning=True` ne demande pas au modèle de raisonner davantage :
            # il n'active que l'ENVOI de `GROQ_REASONING_EFFORT` (= "low"), que
            # `reasoning=False` supprimait — laissant le modèle raisonner à son
            # effort par défaut, bien plus bavard. Sans lui, 200 jetons ne
            # suffisent toujours pas sur les formulations confuses
            # (« Carotte manque d'eau trop petit . Culture perdu » :
            # `out=200` pile, contenu vide).
            max_tokens=200,
            reasoning=True,
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

    Ordre strict : règles (CA2) → catalogue chiffré (US-096) → cache (CA3) →
    modèle (CA4). Le modèle n'est donc appelé que pour la frange réellement
    ambiguë — et une question que les gabarits savent servir n'en fait jamais
    partie, quelle que soit sa formulation. `ctx` n'est nécessaire
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

    nature_catalogue = _regle_par_catalogue(texte_brut, ctx)
    if nature_catalogue is not None:
        decision = DecisionRoutage(
            nature=nature_catalogue, origine=ORIGINE_REGLE, confiance=1.0,
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

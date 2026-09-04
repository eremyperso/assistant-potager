"""
llm/routeur.py — Routeur des demandes, règles avant tout appel au LLM [US-093]
================================================================================
[US-170 / CA17 — révision de CA13] `classer_demande()` décide désormais
lui-même la nature ACTION / QUESTION_* de la demande, appelé depuis
`bot.handle_text` à la place de `bot._is_question` (supprimée) — et non plus
seulement en aval d'elle. Le motif : la moitié du critère de `_is_question`
reposait sur le point d'interrogation, un signal absent de la dictée vocale
(mesuré le 30/08/2026 : 55 % des questions du corpus de routage rejetées une
fois le `?` retiré). Ce module ne remplace toujours pas les gardes de
**conversation** (modes `corr_*`, mode `ask`, navigation), qui restent
consultées avant lui sans exception — elles portent un état de dialogue, pas
une classification, et les déplacer casserait les dialogues en cours.

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

[US-170 / CA18 — révision de CA6/CA7, sur le *quand* remonter, pas sur le
principe] `repondre_avec_cascade` ne remonte plus sur le seul `confiant=False`
côté QUESTION_DATA : une famille du catalogue qui a matché a *produit* une
phrase (`chiffree is not None`), même quand elle porte `present=False` — « je
n'ai aucune récolte de concombre enregistrée » est une réponse exacte, pas un
échec. `confiant` (donc `present`) ne tranche plus seul cette remontée ; seule
l'absence de toute famille matchée, ou un agent SQL qui n'a lui-même rien
trouvé, la déclenche encore. Voir le commentaire au point d'appel.

[US-098] L'étage 2 (connaissance, recherche plein texte) est désormais branché
sur la nature SAVOIR, exactement comme la docstring précédente l'annonçait :
seul l'intérieur du branchement a changé, le contrat de
`classer_demande`/`repondre_avec_cascade` est resté le même. Une question de
savoir consulte d'abord `app.services.connaissance` — zéro jeton, zéro appel
modèle ; si la confiance est suffisante, le passage écrit et relu est servi tel
quel (CA7), sinon les passages trouvés DESCENDENT en contexte vers l'étage de
raisonnement, qui reste seul à rédiger (CA8). Une confiance faible ne déclare
donc jamais la question sans réponse : elle change d'étage.

L'étage 3 multi-sources (US-142) n'est toujours pas construit : c'est
`_repondre_raisonnement` qui en tient lieu, et la nature HYBRIDE ne consulte
pas encore le socle de connaissance — croiser savoir et données du potager est
précisément le périmètre d'US-142, pas celui d'US-098.

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
from config import RAG_ACTIF, RAG_SEUIL_CONFIANCE
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
# de la classification (regle/cache/modele ci-dessus).
#
# [US-098] ETAGE_SAVOIR est désormais réellement écrit : une question de savoir
# à laquelle le socle de connaissance répond avec une confiance suffisante est
# résolue à l'étage 2, à zéro jeton. Tant que le corpus est vide (US-099 /
# US-140 / US-141 ne sont pas livrées), la recherche ne trouve rien et la
# demande remonte à ETAGE_RAISONNEMENT — le journal continue donc de dire la
# vérité, sans que l'écart ait besoin d'être commenté.
ETAGE_DONNEE       = "donnee"
ETAGE_SAVOIR       = "savoir"
ETAGE_RAISONNEMENT = "raisonnement"
# [US-095] Étage 0bis — réponse servie depuis `questions_cache`, avant toute
# classification. C'est par cette valeur, et non par `origine_classification`,
# que se mesure le taux de service du cache de RÉPONSES (US-097 / CA12) : la
# colonne `origine_classification = 'cache'` désigne, elle, le cache en mémoire
# des CLASSIFICATIONS, qui est une tout autre chose.
ETAGE_CACHE        = "cache"


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
# Auto-suffisant (bot.py n'a plus d'équivalent depuis US-170 — _is_question,
# ACTION_VERBS et QUESTION_STARTERS ont disparu avec elle) : de toute façon,
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


def normaliser_question(texte: str) -> str:
    """[CA3] Forme normalisée d'une question — clé du cache de classification,
    de la journalisation (`routage_logs.question_normalisee`) et du motif du
    cache de réponses (US-095 / CA2).

    Publique parce qu'elle est partagée : US-095 exige explicitement « la même
    normalisation que le routeur, jamais une variante ». Une seconde
    implémentation, même identique le jour où elle est écrite, divergerait au
    premier ajustement — et la divergence se paierait en entrées de cache
    jamais retrouvées, donc en réponses repayées.
    """
    s = unidecode((texte or "").strip().lower())
    s = _PONCTUATION.sub("", s)
    s = _ESPACES_MULTIPLES.sub(" ", s).strip()
    return s


# Nom historique, conservé pour les appels internes de ce module.
_normaliser_question = normaliser_question


# ─────────────────────────────────────────────────────────────────────────────
# Cache de CLASSIFICATION [CA3] — à ne pas confondre avec le cache de RÉPONSES
# -----------------------------------------------------------------------------
# Celui-ci mémorise « de quelle nature est cette demande ? », en mémoire du
# processus, borné, éviction par ancienneté. Alimenté uniquement par les
# décisions issues du modèle (les décisions par règle sont déjà gratuites — les
# mettre en cache n'apporterait rien).
#
# Le cache de RÉPONSES (US-095, `app/services/cache_questions.py`) est un autre
# objet : il vit en base, mémorise « comment répondre à cette question », et
# intervient AVANT celui-ci, dans `repondre_avec_cascade`. Les deux se mesurent
# séparément (US-097) : `origine_classification='cache'` pour celui-ci,
# `etage_resolveur='cache'` pour celui-là.
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
connaissances générales d'agronomie ou de fonctionnement de l'application.
Si des passages issus de la base de connaissance sont fournis, ils font
autorité : appuie-toi dessus en priorité et ne les contredis pas."""


def _repondre_raisonnement(
    ctx: TenantContext,
    question: str,
    contexte_donnees: str = "",
    contexte_savoir: str = "",
) -> str:
    """Étage de dernier recours : raisonnement/savoir général via la passerelle.
    Peut lever `LLMIndisponibleError` — volontairement non rattrapée ici, pour
    que l'appelant (bot._ask_question) affiche le même repli dégradé standard
    qu'aujourd'hui (US-092), sans dupliquer ce message.

    [US-098 / CA7] `contexte_savoir` porte les passages que l'étage 2 a trouvés
    sans assez de confiance pour les servir seuls. Les descendre ici plutôt que
    les jeter est tout l'intérêt d'une cascade : une recherche à demi
    concluante vaut mieux qu'une réponse de culture générale."""
    message = question
    if contexte_savoir:
        message = f"{message}\n\nPassages de la base de connaissance :\n{contexte_savoir}"
    if contexte_donnees:
        message = f"{message}\n\nDonnées du potager déjà connues : {contexte_donnees}"
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
    score_savoir: Optional[float] = None,
    issue_savoir: Optional[str] = None,
) -> Optional[int]:
    """[CA1, CA2, CA4] Écrit une ligne dans `routage_logs`. Ne lève jamais : la
    journalisation est de l'observabilité, une panne d'écriture ne doit pas
    faire échouer une réponse déjà produite.

    [US-098 / CA14] `score_savoir` et `issue_savoir` ne sont renseignés que si
    la question a traversé l'étage 2. Ce sont eux qui rendent interrogeable la
    seule question qui compte au démarrage du socle : « à quoi la base ne
    répond-elle pas ? » — donc « que faut-il écrire ensuite ? »."""
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
            score_savoir=score_savoir,
            issue_savoir=issue_savoir,
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
# [US-098] Étage 2 — consultation du socle de connaissance
# ─────────────────────────────────────────────────────────────────────────────
def _consulter_savoir(ctx: TenantContext, question: str):
    """Interroge l'étage 2 et rend son contexte, ou `None`.

    Ne lève jamais et ne rédige jamais : l'étage du savoir est un ACCÉLÉRATEUR,
    pas un passage obligé. Une base absente (migration non jouée), vide (le
    corpus arrive avec US-099/US-140/US-141) ou en panne doit laisser la cascade
    se dérouler exactement comme avant cette US — un socle indisponible ne peut
    pas coûter une réponse au jardinier.

    `RAG_ACTIF=0` court-circuite l'étage sans redéploiement, le jour où la
    mesure du CA13 le justifierait (voir `config.py`).
    """
    from app.services import connaissance

    if not RAG_ACTIF:
        return None
    db = None
    try:
        db = SessionLocal()
        return connaissance.rechercher(db, ctx, question)
    except Exception as e:
        log.warning("⚠️  SAVOIR         │ recherche impossible (%s) — cascade poursuivie", type(e).__name__)
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
    # Imports locaux : `app.services` importe déjà `llm`, un import de module
    # créerait un cycle (même raison que `_regle_par_catalogue` ci-dessus).
    from app.services import cache_questions, connaissance
    from app.services.questions import repondre_question_detaille

    debut = time.monotonic()
    jeton_mesure = passerelle.demarrer_mesure_cascade()

    # ── Étage 0bis — cache de questions [US-095] ─────────────────────────────
    # AVANT la classification : une question déjà rencontrée n'a pas à être
    # reclassée, et une entrée `template_sql` recalcule ses valeurs, donc ne
    # peut pas servir un chiffre périmé. Le jardinier ne voit aucune différence
    # (US-095 / CA13) — seul le journal garde trace de l'origine.
    depuis_cache = cache_questions.servir(ctx, question)
    if depuis_cache is not None:
        decision_cache = DecisionRoutage(
            nature=(NATURE_QUESTION_SAVOIR if depuis_cache.type_reponse == cache_questions.TYPE_FIGEE
                    else NATURE_QUESTION_DATA),
            origine=ORIGINE_CACHE,
            confiance=1.0,
        )
        routage_log_id = _persister_routage_log(
            ctx, question, decision_cache, ETAGE_CACHE, False,
            int((time.monotonic() - debut) * 1000),
            passerelle.cumul_mesure_cascade(jeton_mesure),
        )
        return ReponseCascade(
            texte=depuis_cache.texte, etage_resolveur=ETAGE_CACHE, routage_log_id=routage_log_id,
        )

    decision = classer_demande(question, ctx)
    cascade_remontee = False
    etage_resolveur = ETAGE_RAISONNEMENT
    chiffree = None
    savoir = None  # [US-098] ContexteConnaissance, si l'étage 2 a été consulté

    try:
        if decision.nature == NATURE_QUESTION_DATA:
            texte, confiant, chiffree = repondre_question_detaille(ctx, question)
            # [Chantier 2 / US-170, révise CA6-CA7] Une famille du catalogue qui a
            # matché a PRODUIT une phrase, même quand `present=False` : « je n'ai
            # aucune récolte de concombre enregistrée » est une réponse exacte, pas
            # une non-réponse. Remonter la cascade dans ce cas remplaçait une
            # réponse juste par un conseil d'agronomie hors sujet (mesuré le
            # 30/08/2026, 1 087 jetons pour quatre formulations). Seule l'absence
            # de TOUTE famille matchée — `chiffree is None` — ou un agent SQL qui
            # n'a lui-même pas su répondre justifie encore la remontée.
            if chiffree is not None or confiant:
                etage_resolveur = ETAGE_DONNEE
            else:
                log.info(f"↪️ ROUTEUR REMONTÉE : donnée non exploitable → raisonnement (1 saut) : '{question[:80]}'")
                cascade_remontee = True
                chiffree = None
                texte = _repondre_raisonnement(ctx, question)
        elif decision.nature == NATURE_QUESTION_SAVOIR:
            # ── [US-098] Étage 2 — le socle de connaissance ──────────────────
            # Consulté AVANT tout appel modèle : c'est toute la raison d'être de
            # cet étage. Une recherche qui trouve à coup sûr coûte zéro jeton ;
            # une recherche qui ne trouve rien coûte zéro jeton aussi, et le
            # raisonnement reprend exactement comme avant cette US.
            savoir = _consulter_savoir(ctx, question)
            if savoir is not None and savoir.suffisant:
                # [CA7, CA8] Le texte servi est le passage HUMAINEMENT écrit,
                # recopié — pas une génération. Zéro appel modèle sur ce chemin.
                texte = connaissance.restituer(savoir)
                etage_resolveur = ETAGE_SAVOIR
            else:
                # [CA7] Confiance insuffisante : le contexte DESCEND vers
                # l'étage de raisonnement, il ne se perd pas. La question n'est
                # jamais déclarée sans réponse.
                passages = (
                    connaissance.contexte_pour_raisonnement(savoir)
                    if savoir is not None else ""
                )
                cascade_remontee = bool(passages)
                if passages:
                    # Deux causes très différentes mènent ici, et les confondre
                    # envoie chercher un défaut de recherche là où il n'y en a
                    # pas : un score sous le seuil, ou une fiche qui se déclare
                    # elle-même non relue. Le log doit dire laquelle.
                    motif = (
                        "fiche %s, non servie telle quelle"
                        % savoir.passages[0].niveau_confiance
                        if savoir.confiance >= RAG_SEUIL_CONFIANCE
                        else "score sous le seuil (%.2f)" % RAG_SEUIL_CONFIANCE
                    )
                    log.info(
                        "↪️ ROUTEUR REMONTÉE : %s (score=%.2f) → raisonnement (1 saut) : '%s'",
                        motif, savoir.confiance, question[:80],
                    )
                texte = _repondre_raisonnement(ctx, question, contexte_savoir=passages)
                # [CA7] L'attribution suit le contenu, même quand le modèle l'a
                # RÉÉCRIT. Sur le chemin `servi`, `restituer()` ajoute
                # « _Source : … _ » ; sur celui-ci, la même matière partait sans
                # aucune mention — le jardinier ne pouvait plus savoir que la
                # réponse venait du corpus, ni de quelle fiche.
                #
                # Ce n'est pas qu'une commodité de lecture : `referentiel_source`
                # porte des licences à attribution obligatoire à l'affichage
                # (wind_river_greens est en CC BY 4.0). Une licence de ce type
                # couvre aussi les œuvres DÉRIVÉES — une réponse rédigée à partir
                # du texte en est une. Le libellé dit « d'après » et non
                # « source » : le texte servi ici n'est pas celui de la fiche.
                if savoir is not None and savoir.sources:
                    texte = f"{texte}\n\n_D'après : {', '.join(savoir.sources)}_"
        else:
            # QUESTION_HYBRIDE (et ACTION mal aiguillée jusqu'ici) : tente
            # d'enrichir le raisonnement avec la donnée si elle existe, sans
            # remontée dédiée — cet étage héberge déjà le raisonnement, un
            # second saut n'aurait pas de sens.
            texte_donnees, confiant, _ = repondre_question_detaille(ctx, question)
            texte = _repondre_raisonnement(ctx, question, contexte_donnees=texte_donnees if confiant else "")
    except Exception:
        passerelle.cumul_mesure_cascade(jeton_mesure)  # désarme sans persister
        raise

    latence_ms = int((time.monotonic() - debut) * 1000)
    tokens_consommes = passerelle.cumul_mesure_cascade(jeton_mesure)
    routage_log_id = _persister_routage_log(
        ctx, question, decision, etage_resolveur, cascade_remontee, latence_ms, tokens_consommes,
        score_savoir=savoir.confiance if savoir is not None else None,
        issue_savoir=savoir.issue if savoir is not None else None,
    )
    # [US-095] Mémorisation APRÈS coup, et seulement sur une réponse réellement
    # produite : une cascade qui lève (mode dégradé 429, US-092) n'arrive jamais
    # ici — mémoriser une non-réponse la ferait servir comme une réponse.
    _memoriser_reponse(ctx, question, decision, etage_resolveur, chiffree, texte, savoir)
    return ReponseCascade(texte=texte, etage_resolveur=etage_resolveur, routage_log_id=routage_log_id)


def _memoriser_reponse(
    ctx: TenantContext,
    question: str,
    decision: DecisionRoutage,
    etage_resolveur: str,
    chiffree,
    texte: str,
    savoir=None,
) -> None:
    """[US-095 / CA1, CA3, CA8] Alimente l'étage 0bis avec la réponse qui vient
    d'être produite — quand, et seulement quand, elle est mémorisable.

    Deux cas, et aucun autre :

    - l'étage des données a répondu par un gabarit du catalogue → on mémorise
      son **aiguillage** (`template_sql`). Les valeurs seront recalculées à
      chaque service : c'est ce qui rend cette entrée incapable de mentir ;
    - la demande était de la connaissance générale (QUESTION_SAVOIR), à
      laquelle aucune donnée du potager n'a été transmise → on mémorise le
      texte (`figee`), partagé entre tous les potagers, sous réserve du
      contrôle d'absence de donnée de potager (CA8).

    Une réponse HYBRIDE n'est jamais mémorisée : elle mêle par définition du
    raisonnement et des données du potager, donc ni rejouable ni partageable.
    Une réponse de l'agent SQL non plus (aucune famille à rejouer, et son texte
    porte des chiffres). Ne lève jamais : rater une mémorisation coûte un
    recalcul, la faire échouer coûterait la réponse.

    [US-098 / CA11] Quand la réponse dérive du socle de connaissance, elle est
    mémorisée AVEC la référence du fragment dont elle est issue : c'est ce lien,
    et lui seul, qui permet à une réingestion de la faire tomber au lieu de la
    laisser vivre des mois (`cache_questions.invalider_par_fragment`).

    Un contexte de savoir contenant un passage PRIVÉ (US-141) interdit toute
    mémorisation : une entrée figée est partagée entre tous les potagers
    (`potager_id = NULL`), y verser un savoir privé serait la fuite que le
    contrôle textuel d'US-095 / CA8 ne rattraperait qu'au hasard des mots.
    """
    from app.services import cache_questions

    db = None
    try:
        if chiffree is not None and chiffree.present and chiffree.aiguillage:
            db = SessionLocal()
            cache_questions.memoriser_template_sql(db, ctx, question, chiffree.aiguillage)
        elif (
            decision.nature == NATURE_QUESTION_SAVOIR
            and etage_resolveur in (ETAGE_SAVOIR, ETAGE_RAISONNEMENT)
        ):
            if savoir is not None and not savoir.contexte_partageable:
                log.info(
                    "⛔ CACHE QUESTION │ mémorisation écartée (passage privé au contexte) : '%s'",
                    question[:80],
                )
                return
            db = SessionLocal()
            cache_questions.memoriser_figee(
                db, ctx, question, texte,
                source_etage=(cache_questions.SOURCE_RAG if etage_resolveur == ETAGE_SAVOIR
                              else cache_questions.SOURCE_LLM),
                fragment_id=(savoir.passages[0].reference
                             if savoir is not None and savoir.passages else None),
            )
    except Exception as e:
        log.warning("⚠️ CACHE QUESTION │ mémorisation impossible (%s)", type(e).__name__)
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

"""
app/services/cache_questions.py — Étage 0bis : cache qui ne ment jamais [US-095]
================================================================================
Les mêmes questions reviennent en boucle (« mon stock de tomates ? », « ma
dernière récolte ? »). Les retraiter à neuf à chaque fois est du gaspillage —
mais les mémoriser naïvement est pire : le scénario le plus banal de
l'application est aussi le pire. Le jardinier demande son stock de tomates,
enregistre « récolté 5 kg de tomates », repose la même question, et reçoit
l'ancienne valeur. **Un assistant qui affirme une donnée fausse avec assurance
perd plus de confiance qu'il n'en gagne en étant rapide.**

Deux mécanismes indépendants garantissent que cela ne peut pas arriver ici :

1. **Le paramétré est la règle, le figé l'exception** (arbitrage tranché de
   l'US). Toute question qui touche aux données du potager est mémorisée en
   `template_sql` : on ne mémorise que le motif et l'AIGUILLAGE (famille du
   catalogue, culture, parcelle), jamais un chiffre. Les valeurs sont
   recalculées à chaque service par l'étage des données (US-096,
   `reponses_chiffrees.servir_aiguillage`). La réponse est donc juste par
   construction — la classe entière des réponses périmées est structurellement
   impossible, pas seulement improbable.

2. **L'invalidation événementielle** (CA5), pour tout ce que le point 1 ne
   couvre pas et pour que le cache ne survive jamais à ce qui le contredit :
   toute écriture d'évènement supprime les entrées du potager dont la culture
   et les natures de donnée recoupent celles du geste enregistré. C'est une
   SUPPRESSION, pas un marquage — une entrée périmée qui subsisterait est
   exactement le défaut que cette US existe pour empêcher.

**Deux natures de réponse, donc deux espaces de clés** (CA2) — c'est la
distinction structurante de ce module :

- une réponse `template_sql` est clefée sur son **aiguillage**
  (`famille|culture|parcelle`), jamais sur la phrase. « quel est ma production
  de concombre », « ma production de concombre » et « production de concombre »
  sont trois façons de poser une seule question : une seule entrée. L'espace
  des aiguillages est borné — quelques centaines par potager — là où celui des
  formulations ne l'est pas. Corrigé le 29/08/2026 : la première version clefait
  sur la phrase, et ces trois formulations avaient créé trois lignes en 29
  secondes sans jamais servir une réponse ;
- une réponse `figee` est clefée sur la **phrase normalisée**, parce qu'il n'y
  a rien d'autre : du savoir général n'a pas d'aiguillage. Sur une entrée
  paramétrée, `motif_normalise` reste renseigné mais ne sert qu'à l'audit — il
  dit quelle formulation a créé l'entrée.

Ce qui est délibérément écrit ici, et pourquoi :

- **[CA2] Un seul normaliseur.** Le motif est produit par
  `llm.routeur.normaliser_question`, la fonction du routeur elle-même. Une
  copie, même identique aujourd'hui, divergerait au premier ajustement, et la
  divergence se paierait en entrées jamais retrouvées.
- **[CA5] Un seul point d'invalidation.** `invalider_pour_evenement()` n'est
  appelée que par la couche services d'écriture (`app/services/evenements.py`).
  Ni `bot.py` ni `main.py` ne l'appellent : dupliquée, elle divergerait au
  premier chemin d'écriture ajouté — et l'oubli ne se verrait pas, il se
  paierait en réponse fausse.
- **[CA7] Corriger et supprimer invalident comme créer.** Ce sont les chemins
  les plus faciles à oublier, ils sont donc branchés au même endroit que la
  création, et testés nommément.
- **[CA8] Le savoir général ne peut pas fuir.** Une entrée `figee` porte
  toujours `potager_id = NULL` : elle est partagée par tous les potagers. Un
  contrôle à l'écriture refuse de mémoriser un texte qui cite un nom de
  parcelle ou une variété du potager d'origine — c'est par là qu'une fuite
  serait la plus discrète et la plus durable.
- **[CA13] Indiscernable d'une réponse fraîche.** Aucune mention « réponse en
  cache » n'est ajoutée au texte servi. Seul le journal en garde trace.

Ce que ce module ne fait PAS, volontairement :

- **Aucun préchauffage** (arbitrage tranché) : le cache se remplit de ce qui
  est réellement demandé. Précalculer des réponses jamais lues serait du coût
  pur.
- **Aucun job planifié** (CA11) : les entrées périmées sont écartées à la
  lecture et nettoyées au fil de l'eau, à l'occasion d'une écriture.
- **Aucune mémorisation en mode dégradé** : une cascade interrompue par
  `LLMIndisponibleError` ne produit pas de réponse, donc rien à mémoriser. Une
  non-réponse mémorisée serait servie comme une réponse. Le même raisonnement
  vaut pour un appel qui a RÉUSSI mais dont le modèle avoue son ignorance
  (« je n'ai pas accès à… ») : voir `est_non_reponse()`.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from unidecode import unidecode

from app.services import reponses_chiffrees
from app.services.context import TenantContext
from database.db import SessionLocal
from database.models import Evenement, Parcelle, QuestionCache
from llm.routeur import normaliser_question
from utils.dependances_donnee import NATURES_TOUTES, natures_impactees

log = logging.getLogger("potager")

# Tout ce qui n'est ni lettre ni chiffre devient un espace — voir
# `_normaliser_phrase` pour la raison de ne pas reutiliser le
# normaliseur du routeur ici.
_ESPACES = re.compile(r"[^a-z0-9]+")

# ─────────────────────────────────────────────────────────────────────────────
# Vocabulaire de la table [CA1]
# ─────────────────────────────────────────────────────────────────────────────
TYPE_TEMPLATE_SQL = "template_sql"
TYPE_FIGEE = "figee"

SOURCE_SQL = "sql"
SOURCE_RAG = "rag"
SOURCE_LLM = "llm"

# [CA10] Une réponse figée porte 90 jours de validité : c'est du savoir
# général, il bouge lentement — mais il bouge (une pratique culturale
# recommandée change, une fiche est corrigée). Le lien `fragment_id` la fait
# tomber plus tôt le jour où sa source est corrigée.
TTL_FIGEE_JOURS = 90

# Une entrée paramétrée ne peut pas porter de valeur fausse : sa durée de vie
# ne protège de rien d'autre que d'une dérive du catalogue (famille renommée,
# motif retouché). 30 jours suffisent, et bornent la table sans effort.
TTL_TEMPLATE_JOURS = 30

# Note technique de l'US : borne haute par potager, pour qu'une saisie
# erratique ne fasse pas croître la table indéfiniment.
#
# Depuis que la clé d'une réponse paramétrée est son AIGUILLAGE et non sa
# formulation, l'espace des clés est borné par construction bien en dessous :
# quelques centaines de valeurs (familles × cultures + familles × parcelles)
# pour un potager, contre un espace de formulations sans limite. Cette borne
# cesse donc d'être une contrainte de fonctionnement pour redevenir ce qu'elle
# doit être — un filet contre un potager pathologique. Et l'éviction par
# ancienneté redevient sûre : plus aucun quasi-doublon ne concourt pour une
# place.
MAX_ENTREES_PAR_POTAGER = 1000

# Longueur minimale d'un nom propre du potager (parcelle, variété) pour servir
# de témoin de fuite dans un texte figé (CA8). En dessous, un nom de deux ou
# trois lettres produirait des faux positifs sur des mots courants.
_LONGUEUR_MIN_TEMOIN = 4

# [CA8] Valeurs qui SE TROUVENT dans `evenements.variete` sans être des noms
# propres du potager. Le champ est libre : il reçoit aussi bien « Gariguette »
# que « autre », « blanc » ou « variété non précisée ». Les secondes sont des
# mots français ordinaires, qui apparaissent naturellement dans une réponse
# agronomique générale — les retenir comme témoins de fuite ne protège rien et
# interdit de mémoriser le savoir le plus banal.
#
# Constaté le 04/09/2026 sur le potager #1 : 23 fragments sur 96 du corpus
# agronomique contenaient un tel « témoin », donc aucune réponse qui les
# reprend ne pouvait être mémorisée — chaque question répétée sur ces sujets
# repayait un appel modèle complet, indéfiniment.
#
# Le critère reste celui de la docstring de `_temoins_du_potager` : un témoin
# est un nom que SEUL ce potager emploie. Une couleur ou un mot de conduite
# n'en est pas un. Contrepartie assumée : un jardinier qui nommerait vraiment
# une variété « Blanc » ne serait plus protégé sur ce mot précis — un texte
# général contenant « blanc » n'est de toute façon pas une fuite.
_TEMOINS_GENERIQUES: frozenset[str] = frozenset({
    # remplissages du champ libre
    "autre", "autres", "divers", "diverses", "inconnu", "inconnue",
    "non precisee", "non precise", "variete non precisee", "non localise",
    "non localisee", "standard", "classique", "ordinaire", "commun", "commune",
    "mixte", "melange", "maison", "serre", "greffe", "greffee",
    # couleurs seules
    "blanc", "blanche", "noir", "noire", "rouge", "rose", "jaune", "vert",
    "verte", "violet", "violette", "orange", "gris", "grise", "bleu", "bleue",
    # qualificatifs horticoles courants
    "cerise", "cerises", "precoce", "tardive", "hative", "native", "naine",
    "grimpante", "grimpant", "ronde", "longue", "plate", "douce", "amere",
    "sucree", "geante", "petite", "grosse", "mini", "bio", "ancienne",
    "hybride", "citronne", "cannelle", "commune",
})

# Un témoin qui porte une année est une NOTE de saisie (« récolte de 2025 »,
# « année 2024 »), pas un nom propre du potager.
_ANNEE_DANS_TEMOIN = re.compile(r"\d{4}")


# ─────────────────────────────────────────────────────────────────────────────
# Sérialisation des dépendances [CA4]
# -----------------------------------------------------------------------------
# Les natures sont stockées encadrées de « | » (ex. `|stock|recolte|journal|`)
# plutôt qu'en table de liaison : le test d'appartenance devient un simple
# LIKE '%|stock|%', portable SQLite ↔ PostgreSQL — les deux moteurs de ce
# projet — et l'invalidation reste une seule instruction SQL.
# ─────────────────────────────────────────────────────────────────────────────
def _encoder_natures(natures) -> str:
    """Chaîne vide = AUCUNE nature, et c'est une valeur légitime : une réponse
    figée ne dérive d'aucun potager, donc aucun évènement ne peut la
    contredire. Ne pas replier ce cas sur `|journal|` — ce serait déclarer une
    dépendance qui n'existe pas, et faire passer le test d'isolation du CA10
    pour la mauvaise raison (il ne tiendrait plus que par le filtre
    `potager_id`)."""
    ordonnees = sorted(set(natures))
    return "|" + "|".join(ordonnees) + "|" if ordonnees else ""


# ─────────────────────────────────────────────────────────────────────────────
# Lecture — étage 0bis
# ─────────────────────────────────────────────────────────────────────────────
class ReponseCache:
    """Réponse servie depuis le cache. `texte` est le seul élément visible du
    jardinier, et il est indiscernable d'une réponse fraîche (CA13)."""

    __slots__ = ("texte", "type_reponse", "source_etage", "partagee")

    def __init__(self, texte: str, type_reponse: str, source_etage: str, partagee: bool):
        self.texte = texte
        self.type_reponse = type_reponse
        self.source_etage = source_etage
        # Vrai pour une entrée de savoir général (potager_id NULL).
        self.partagee = partagee


def _non_perimee(maintenant: datetime):
    """[CA11] Les entrées périmées sont écartées ici, à la lecture, avant même
    d'être nettoyées."""
    return or_(
        QuestionCache.valide_jusqu_au.is_(None),
        QuestionCache.valide_jusqu_au > maintenant,
    )


def _entree_parametree(
    db: Session, ctx: TenantContext, cle: str, maintenant: datetime
) -> Optional[QuestionCache]:
    """[CA2, CA9] Entrée paramétrée de CE potager pour cet aiguillage.

    Jamais `potager_id IS NULL` : une entrée paramétrée recalcule sur les
    données d'un potager, la partager serait exactement la fuite que CA8
    interdit. Le filtre l'écrit plutôt que de le supposer.
    """
    return (
        db.query(QuestionCache)
        .filter(
            QuestionCache.cle_aiguillage == cle,
            QuestionCache.potager_id == ctx.potager_id,
            QuestionCache.type_reponse == TYPE_TEMPLATE_SQL,
            _non_perimee(maintenant),
        )
        .order_by(QuestionCache.cree_le.desc())
        .first()
    )


def _entree_figee(
    db: Session, motif: str, maintenant: datetime
) -> Optional[QuestionCache]:
    """[CA1, CA8] Entrée de savoir général pour cette phrase. `potager_id` est
    toujours NULL : c'est ce qui la rend partageable entre tous les potagers,
    et ce qui justifie le contrôle d'absence de donnée de potager à
    l'écriture."""
    return (
        db.query(QuestionCache)
        .filter(
            QuestionCache.motif_normalise == motif,
            QuestionCache.potager_id.is_(None),
            QuestionCache.type_reponse == TYPE_FIGEE,
            _non_perimee(maintenant),
        )
        .order_by(QuestionCache.cree_le.desc())
        .first()
    )


def servir(
    ctx: TenantContext, question: str, db: Optional[Session] = None
) -> Optional[ReponseCache]:
    """[CA1, CA2, CA3, CA9, CA13] Sert cette question depuis le cache, ou rend
    la main (`None`) — la cascade se déroule alors exactement comme avant cette
    US.

    **Deux recherches, une par nature de réponse** (CA2) :

    1. Le catalogue reconnaît-il une famille ? Si oui, la question a un
       *aiguillage*, et c'est lui la clé — pas la phrase. Trois formulations
       d'une même question retombent ainsi sur une seule entrée.
    2. Sinon, la question relève du savoir général : la phrase normalisée est
       tout ce qu'on a, et sert de clé.

    Pour une entrée `template_sql`, servir veut dire **recalculer** : la
    famille du catalogue est rejouée sur la base telle qu'elle est maintenant.
    Le cache n'économise donc jamais la vérité.

    Ne lève jamais : une lecture de cache impossible (table absente, base
    indisponible) se lit « pas d'entrée », et la question suit son cours.
    """
    if ctx is None or ctx.potager_id is None or not (question or "").strip():
        return None

    motif = normaliser_question(question)
    if not motif:
        return None

    session_locale = db is None
    session = db if db is not None else SessionLocal()
    try:
        maintenant = datetime.utcnow()

        reconnue = reponses_chiffrees.reconnaitre(ctx, question, db=session)
        if reconnue is not None:
            famille, params = reconnue
            cle = reponses_chiffrees.cle_aiguillage(
                reponses_chiffrees.aiguillage_de(famille, params)
            )
            entree = _entree_parametree(session, ctx, cle, maintenant)
            if entree is not None:
                aiguillage = json.loads(entree.template or "{}")
                chiffree = reponses_chiffrees.servir_aiguillage(
                    ctx, aiguillage, question, db=session
                )
                # `present=False` : la donnée a disparu depuis la mémorisation
                # (évènement supprimé, culture arrachée). On ne sert pas une
                # phrase d'absence depuis le cache — la cascade reprend, et
                # saura peut-être mieux répondre.
                if chiffree is not None and chiffree.present:
                    log.info(
                        "⚡ CACHE QUESTION │ servie=template_sql │ cle=%-28s │ 0 jeton │ '%s'",
                        cle, question[:60],
                    )
                    return ReponseCache(
                        chiffree.texte, TYPE_TEMPLATE_SQL, entree.source_etage, False,
                    )
            # Famille reconnue mais rien en cache (ou donnée disparue) : c'est
            # une question de données, elle n'a rien à aller chercher du côté
            # du savoir général — la cascade la sert par l'étage 1.
            return None

        figee = _entree_figee(session, motif, maintenant)
        if figee is not None and figee.reponse_figee:
            log.info(
                "⚡ CACHE QUESTION │ servie=figee │ source=%s │ 0 jeton │ '%s'",
                figee.source_etage, question[:60],
            )
            return ReponseCache(figee.reponse_figee, TYPE_FIGEE, figee.source_etage, True)
        return None
    except Exception as erreur:
        log.warning(
            "⚠️ CACHE QUESTION │ lecture impossible (%s) → poursuite de la cascade : '%s'",
            type(erreur).__name__, (question or "")[:80],
        )
        return None
    finally:
        if session_locale:
            session.close()


# ─────────────────────────────────────────────────────────────────────────────
# Écriture — mémorisation
# ─────────────────────────────────────────────────────────────────────────────
def _nettoyer_perimees(db: Session, potager_id: Optional[int], maintenant: datetime) -> int:
    """[CA11] Nettoyage au fil de l'eau : à l'occasion d'une écriture, les
    entrées périmées de ce potager (et le savoir général périmé) partent.
    Aucun job planifié n'est ajouté pour cela — le cache se nettoie là où il
    grossit."""
    return (
        db.query(QuestionCache)
        .filter(
            QuestionCache.valide_jusqu_au.isnot(None),
            QuestionCache.valide_jusqu_au <= maintenant,
            or_(
                QuestionCache.potager_id == potager_id,
                QuestionCache.potager_id.is_(None),
            ),
        )
        .delete(synchronize_session=False)
    )


def _borner(db: Session, potager_id: Optional[int]) -> int:
    """Note technique de l'US : borne haute par potager. Au-delà, les entrées
    les plus anciennes cèdent la place — une saisie erratique ne doit pas faire
    croître la table indéfiniment."""
    total = db.query(QuestionCache).filter(QuestionCache.potager_id == potager_id).count()
    surplus = total - MAX_ENTREES_PAR_POTAGER
    if surplus <= 0:
        return 0
    ids = [
        ligne.id
        for ligne in db.query(QuestionCache.id)
        .filter(QuestionCache.potager_id == potager_id)
        .order_by(QuestionCache.cree_le.asc(), QuestionCache.id.asc())
        .limit(surplus)
        .all()
    ]
    return (
        db.query(QuestionCache)
        .filter(QuestionCache.id.in_(ids))
        .delete(synchronize_session=False)
    )


def memoriser_template_sql(
    db: Session, ctx: TenantContext, question: str, aiguillage: dict
) -> Optional[QuestionCache]:
    """[CA1, CA2, CA3, CA4] Mémorise l'aiguillage d'une réponse chiffrée —
    jamais sa valeur. La culture et les natures dont elle dérive sont
    enregistrées avec elle : ce sont elles que l'invalidation événementielle
    consultera.

    **Une entrée par aiguillage, pas par formulation.** La recherche de
    l'existante se fait sur `cle_aiguillage` : reposer la même question
    autrement rafraîchit l'entrée au lieu d'en créer une nouvelle. Avant cette
    règle, « quel est ma production de concombre », « ma production de
    concombre » et « production de concombre » avaient produit trois lignes en
    29 secondes — et servi zéro réponse depuis le cache.
    """
    motif = normaliser_question(question)
    famille = (aiguillage or {}).get("famille")
    if not motif or not famille:
        return None
    cle = reponses_chiffrees.cle_aiguillage(aiguillage)

    maintenant = datetime.utcnow()
    _nettoyer_perimees(db, ctx.potager_id, maintenant)

    existante = (
        db.query(QuestionCache)
        .filter(
            QuestionCache.cle_aiguillage == cle,
            QuestionCache.potager_id == ctx.potager_id,
            QuestionCache.type_reponse == TYPE_TEMPLATE_SQL,
        )
        .first()
    )
    if existante is not None:
        # L'aiguillage est déjà connu : on rafraîchit son échéance plutôt que
        # d'empiler une ligne par tournure de phrase. `motif_normalise` n'est
        # PAS réécrit — il garde la formulation qui a créé l'entrée, ce qui en
        # fait une trace d'audit stable plutôt qu'un champ qui change au gré
        # des reformulations.
        existante.template = json.dumps(aiguillage, ensure_ascii=False)
        existante.culture = aiguillage.get("culture")
        existante.natures = _encoder_natures(aiguillage.get("dependances") or NATURES_TOUTES)
        existante.valide_jusqu_au = maintenant + timedelta(days=TTL_TEMPLATE_JOURS)
        db.commit()
        return existante

    entree = QuestionCache(
        potager_id=ctx.potager_id,
        motif_normalise=motif,
        cle_aiguillage=cle,
        type_reponse=TYPE_TEMPLATE_SQL,
        template=json.dumps(aiguillage, ensure_ascii=False),
        reponse_figee=None,
        source_etage=SOURCE_SQL,
        culture=aiguillage.get("culture"),
        natures=_encoder_natures(aiguillage.get("dependances") or NATURES_TOUTES),
        valide_jusqu_au=maintenant + timedelta(days=TTL_TEMPLATE_JOURS),
        cree_le=maintenant,
    )
    db.add(entree)
    # Poussee avant le bornage : sans cela, la ligne qui vient d'etre
    # ajoutee ne serait pas comptee et la borne serait depassee de un a
    # chaque ecriture (autoflush est desactive sur les sessions du projet).
    db.flush()
    _borner(db, ctx.potager_id)
    db.commit()
    log.info(
        "🧠 CACHE QUESTION │ mémorisé=template_sql │ cle=%-28s │ '%s'",
        cle, question[:60],
    )
    return entree


def _temoins_du_potager(db: Session, potager_id: int) -> set[str]:
    """[CA8] Noms propres au potager, qui n'ont aucune raison d'apparaître dans
    une réponse de savoir général : noms de parcelles et variétés cultivées.

    Volontairement PAS les noms de culture : « carotte » appartient au savoir
    général autant qu'au potager, l'y inclure interdirait de mémoriser la
    moindre réponse agronomique. Le témoin retenu est le nom propre — celui
    que seul ce potager emploie.
    """
    temoins: set[str] = set()
    for (nom,) in db.query(Parcelle.nom).filter(Parcelle.potager_id == potager_id).all():
        temoins.add(_normaliser_temoin(nom))
    for (variete,) in (
        db.query(Evenement.variete)
        .filter(Evenement.potager_id == potager_id, Evenement.variete.isnot(None))
        .distinct()
        .all()
    ):
        temoins.add(_normaliser_temoin(variete))
    return {t for t in temoins if _est_temoin_exploitable(t)}


def _est_temoin_exploitable(temoin: str) -> bool:
    """[CA8] Un témoin doit être un nom que SEUL ce potager emploie.

    Trois disqualifications, toutes constatées dans de vraies données : trop
    court pour ne pas croiser un mot courant, porteur d'une année (donc une
    note de saisie, pas un nom), ou membre du vocabulaire générique du champ
    libre `variete`.
    """
    if len(temoin) < _LONGUEUR_MIN_TEMOIN:
        return False
    if _ANNEE_DANS_TEMOIN.search(temoin):
        return False
    return temoin not in _TEMOINS_GENERIQUES


def _normaliser_temoin(valeur: Optional[str]) -> str:
    return unidecode((valeur or "").strip().lower())


def contient_donnee_potager(db: Session, potager_id: int, texte: str) -> bool:
    """[CA8] Vrai si ce texte cite un nom propre au potager — nom de parcelle ou
    variété. C'est le contrôle à l'écriture qui interdit qu'une réponse figée,
    partagée entre tous les potagers, emporte une donnée de l'un d'eux.

    Le contrôle est volontairement grossier et ne prétend pas détecter toute
    fuite concevable : il vise le cas réaliste, une réponse de raisonnement qui
    reprend « la parcelle nord » ou « Marmande ». La garantie principale reste
    structurelle — seules les questions classées SAVOIR, auxquelles aucune
    donnée de potager n'a été transmise, atteignent ce contrôle.
    """
    normalise = _normaliser_temoin(texte)
    if not normalise:
        return True
    return any(
        _cite_le_temoin(normalise, temoin)
        for temoin in _temoins_du_potager(db, potager_id)
    )


def _cite_le_temoin(texte_normalise: str, temoin: str) -> bool:
    """[CA8] Le témoin doit apparaître comme un MOT, pas comme une sous-chaîne.

    Sans cette borne, la recherche mordait au milieu des mots et refusait du
    savoir parfaitement général — constaté le 04/09/2026 sur le corpus
    agronomique :

        « une racine ouverte se conserve moins bien »  → témoin « verte »
        « des plantules serrees se concurrencent »     → témoin « serre »
        « d'autres insectes peuvent laisser… »         → témoin « autre »

    Aucune de ces phrases ne cite quoi que ce soit du potager. Le `s?` final
    tolère le pluriel d'un vrai nom (« des Gariguettes ») sans rouvrir la
    porte : « serrees » n'est pas « serre » suivi d'un `s`.
    """
    return re.search(rf"\b{re.escape(temoin)}s?\b", texte_normalise) is not None


# Formulations par lesquelles un modèle annonce qu'il ne répond PAS. Elles
# arrivent en réponse d'apparence normale — `issue=ok`, jetons consommés — et
# ne se distinguent d'un vrai savoir que par leur contenu.
#
# La note technique de l'US dit « ne pas mettre en cache les réponses produites
# en mode dégradé : elles seraient mémorisées comme des non-réponses ». Elle
# visait le 429, couvert ailleurs (une cascade qui lève ne mémorise rien). Mais
# un modèle qui répond poliment « je n'ai pas accès à cette information »
# produit exactement le même défaut, en pire : l'entrée est du savoir général,
# donc PARTAGÉE À TOUS LES POTAGERS pendant 90 jours. Observé en production le
# 29/08/2026 sur « quelle météo le 10/04 dernier ».
#
# ⚠️ Ne pas retirer cette garde en la croyant redondante avec le traitement du
# mode dégradé : elle couvre le cas où l'appel a RÉUSSI.
_MARQUEURS_NON_REPONSE: tuple[str, ...] = (
    "je n ai pas acces", "je n ai pas access", "je ne peux pas",
    "je ne dispose pas", "je n ai pas d information", "je n ai pas d informations",
    "je ne sais pas", "je n ai pas la possibilite", "je suis incapable",
    "en tant qu assistant", "en tant qu ia", "je n ai pas de donnees",
    "impossible de vous", "je ne suis pas en mesure",
)

# Marqueurs qui ancrent une question dans le temps. Une réponse figée est du
# savoir général : elle doit être vraie indépendamment du moment où elle a été
# mémorisée. « quelle météo le 10/04 dernier » n'est ni générale ni reposable —
# elle ne sera jamais redemandée à l'identique, et signifierait autre chose
# l'an prochain.
_DEICTIQUES_TEMPORELS: tuple[str, ...] = (
    "hier", "dernier", "derniere", "aujourd hui", "ce matin", "cet apres midi",
    "la semaine", "ce mois", "cette annee", "cette saison", "en ce moment",
)


def _normaliser_phrase(texte: Optional[str]) -> str:
    """Minuscules, sans accents, ponctuation ramenée à des ESPACES.

    Volontairement différent de `normaliser_question` (celle du routeur), qui
    SUPPRIME la ponctuation et souderait « qu'assistant » en « quassistant » —
    utilisable comme clé, inutilisable pour reconnaître une locution. Même
    procédé que `reponses_chiffrees._normaliser`, pour la même raison : ici on
    cherche des tournures, pas une clé.
    """
    return _ESPACES.sub(" ", unidecode((texte or "").strip().lower())).strip()


def est_non_reponse(texte: str) -> bool:
    """Vrai si ce texte est un aveu d'ignorance du modèle plutôt qu'un savoir.
    Mémoriser une non-réponse la ferait servir comme une réponse."""
    normalise = _normaliser_phrase(texte)
    return any(marqueur in normalise for marqueur in _MARQUEURS_NON_REPONSE)


def est_question_datee(motif: str) -> bool:
    """Vrai si la question est ancrée dans le temps — un chiffre (une date
    dictée, « le 10/04 ») ou un déictique temporel. Une telle question n'a pas
    de réponse générale, donc rien à mémoriser en savoir partagé."""
    normalise = motif or ""
    if any(caractere.isdigit() for caractere in normalise):
        return True
    return any(f" {mot} " in f" {normalise} " for mot in _DEICTIQUES_TEMPORELS)


def memoriser_figee(
    db: Session,
    ctx: TenantContext,
    question: str,
    texte: str,
    source_etage: str = SOURCE_LLM,
    fragment_id: Optional[str] = None,
) -> Optional[QuestionCache]:
    """[CA1, CA8, CA10] Mémorise une réponse de savoir général, partageable
    entre tous les potagers (`potager_id = NULL`).

    Trois refus, tous journalisés, tous du bon côté — refuser ne coûte qu'un
    recalcul, accepter à tort pollue le savoir de TOUS les potagers pendant 90
    jours :

    1. le texte cite un nom propre au potager d'origine (CA8) — la fuite
       inter-potagers serait discrète et durable ;
    2. le texte est une non-réponse du modèle ;
    3. la question est ancrée dans le temps, donc sans réponse générale.
    """
    motif = normaliser_question(question)
    if not motif or not (texte or "").strip():
        return None

    if contient_donnee_potager(db, ctx.potager_id, texte):
        log.warning(
            "⛔ CACHE QUESTION │ mémorisation figée REFUSÉE (donnée de potager détectée) : '%s'",
            question[:80],
        )
        return None

    if est_non_reponse(texte):
        log.warning(
            "⛔ CACHE QUESTION │ mémorisation figée REFUSÉE (non-réponse du modèle) : '%s'",
            question[:80],
        )
        return None

    if est_question_datee(motif):
        log.info(
            "⛔ CACHE QUESTION │ mémorisation figée écartée (question datée, sans réponse générale) : '%s'",
            question[:80],
        )
        return None

    maintenant = datetime.utcnow()
    _nettoyer_perimees(db, ctx.potager_id, maintenant)

    existante = (
        db.query(QuestionCache)
        .filter(
            QuestionCache.motif_normalise == motif,
            QuestionCache.potager_id.is_(None),
        )
        .first()
    )
    if existante is not None:
        existante.reponse_figee = texte
        existante.source_etage = source_etage
        existante.fragment_id = fragment_id
        existante.valide_jusqu_au = maintenant + timedelta(days=TTL_FIGEE_JOURS)
        db.commit()
        return existante

    entree = QuestionCache(
        # NULL, toujours : une réponse figée est du savoir général ou n'est pas
        # mémorisée du tout. C'est ce qui rend le contrôle ci-dessus suffisant.
        potager_id=None,
        motif_normalise=motif,
        type_reponse=TYPE_FIGEE,
        template=None,
        reponse_figee=texte,
        source_etage=source_etage,
        culture=None,
        # Aucune nature de donnée de potager : rien de ce qu'un évènement écrit
        # ne peut contredire une réponse qui ne dérive d'aucun potager.
        natures=_encoder_natures([]),
        fragment_id=fragment_id,
        valide_jusqu_au=maintenant + timedelta(days=TTL_FIGEE_JOURS),
        cree_le=maintenant,
    )
    db.add(entree)
    # Poussee avant le bornage : sans cela, la ligne qui vient d'etre
    # ajoutee ne serait pas comptee et la borne serait depassee de un a
    # chaque ecriture (autoflush est desactive sur les sessions du projet).
    db.flush()
    _borner(db, None)
    db.commit()
    log.info(
        "🧠 CACHE QUESTION │ mémorisé=figee │ source=%s │ fragment=%s │ '%s'",
        source_etage, fragment_id or "-", question[:60],
    )
    return entree


# ─────────────────────────────────────────────────────────────────────────────
# Invalidation [CA5, CA7] — le critère bloquant de l'US
# ─────────────────────────────────────────────────────────────────────────────
def invalider_pour_evenement(
    db: Session,
    potager_id: Optional[int],
    culture: Optional[str],
    type_action: Optional[str],
) -> int:
    """[CA5, CA7] Supprime les entrées de cache du potager que cet évènement
    rend caduques. Retourne le nombre d'entrées supprimées.

    **Appelée depuis un seul endroit** : la couche services d'écriture des
    évènements (`app/services/evenements.py`), création, correction et
    suppression confondues. Ni `bot.py` ni `main.py` ne l'appellent — dupliquée
    en deux endroits, elle divergerait au premier chemin d'écriture ajouté, et
    l'oubli ne se verrait pas : il se paierait en réponse fausse servie avec
    assurance.

    Portée, selon l'arbitrage « invalider large plutôt que fin » :
    - une entrée sans culture (stock global, rendement global, contenu de la
      pépinière) est touchée par tout évènement du potager ;
    - un évènement sans culture connue touche toutes les entrées du potager ;
    - une action inconnue du référentiel impacte toutes les natures.

    Ne lève jamais : une invalidation impossible est journalisée en warning.
    Elle ne doit pas faire échouer l'enregistrement du geste du jardinier —
    mais elle laisse alors le cache dans un état dont il faut pouvoir suivre
    la trace, d'où le niveau de journalisation.
    """
    if potager_id is None:
        return 0

    natures = natures_impactees(type_action)
    try:
        requete = db.query(QuestionCache).filter(QuestionCache.potager_id == potager_id)

        if culture:
            # Une entrée sans culture dérive de l'ensemble du potager : elle
            # tombe avec n'importe quelle culture.
            requete = requete.filter(
                or_(
                    QuestionCache.culture.is_(None),
                    func.lower(QuestionCache.culture) == culture.strip().lower(),
                )
            )
        # culture absente → aucun filtre : on invalide toutes les entrées du
        # potager. Recalculer coûte zéro jeton, se tromper coûte la confiance.

        requete = requete.filter(
            or_(*[QuestionCache.natures.like(f"%|{nature}|%") for nature in sorted(natures)])
        )
        nb = requete.delete(synchronize_session=False)
        if nb:
            log.info(
                "♻️ CACHE QUESTION │ invalidé=%d │ potager=%s │ culture=%s │ action=%s",
                nb, potager_id, culture or "(toutes)", type_action or "(inconnue)",
            )
        return nb
    except Exception as erreur:
        log.warning(
            "⚠️ CACHE QUESTION │ invalidation impossible (%s) │ potager=%s culture=%s action=%s",
            type(erreur).__name__, potager_id, culture, type_action,
        )
        return 0


def invalider_par_fragment(db: Session, fragment_id: str) -> int:
    """[CA10] Supprime les réponses figées dérivées d'un fragment de
    connaissance corrigé ou réingéré.

    Le lien est une simple référence stockée sur l'entrée (note technique de
    l'US) — surtout pas un mécanisme d'événements. Reste sans effet tant
    qu'US-098 n'existe pas : aucune réponse figée d'origine RAG n'est produite
    aujourd'hui, donc aucune entrée ne porte de `fragment_id`. La fonction
    existe et est testée dès maintenant pour que corriger une fiche
    agronomique ne laisse pas vivre des mois une réponse erronée le jour où
    le socle de connaissance arrivera.
    """
    if not fragment_id:
        return 0
    nb = (
        db.query(QuestionCache)
        .filter(QuestionCache.fragment_id == fragment_id)
        .delete(synchronize_session=False)
    )
    db.commit()
    if nb:
        log.info("♻️ CACHE QUESTION │ invalidé=%d │ fragment=%s", nb, fragment_id)
    return nb


def purger_potager(db: Session, potager_id: int) -> int:
    """Supprime toutes les entrées d'un potager — appelée par la purge physique
    (`app.services.potagers.purger_potager`, US-084 / CA7). Ne commit pas :
    la purge est une transaction unique, le cache en fait partie."""
    return (
        db.query(QuestionCache)
        .filter(QuestionCache.potager_id == potager_id)
        .delete(synchronize_session=False)
    )

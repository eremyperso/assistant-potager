"""
app/services/connaissance.py — Étage 2 : le socle de connaissance [US-098]
================================================================================
Le contenant, pas le contenu. Ce module sait indexer des fragments, les
retrouver en plein texte français et rendre un CONTEXTE — jamais une réponse
rédigée. Le corpus lui-même est écrit ailleurs : US-099 (fonctionnement de
l'application), US-140 (agronomie), US-141 (mémoire du potager).

Trois invariants portent l'US, et ce module les tient tous les trois à un seul
endroit :

- **[CA5] Le filtre d'isolation est porté par la recherche, pas par l'appelant.**
  `_requete_base` est le SEUL constructeur de requête sur `knowledge_chunks` du
  projet, et il pose `potager_id IS NULL OR potager_id = :potager_courant` sans
  condition. Un appelant ne peut pas l'oublier puisqu'il ne l'écrit jamais.
  `tests/test_us098_socle_connaissance.py` vérifie qu'aucun autre module
  n'interroge la table.

- **[CA8] La recherche ne rédige pas.** `rechercher()` retourne un
  `ContexteConnaissance` : des passages, leurs sources, un score. Aucun appel
  modèle n'existe dans ce fichier — il n'importe même pas `llm.passerelle`.
  Servir directement (`restituer`) est un assemblage mécanique du texte
  HUMAINEMENT écrit dans le dépôt, à zéro jeton : c'est une citation, pas une
  génération. La génération reste au seul étage 3.

- **[CA2 amendé — docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md §1.3] La culture
  d'un fragment est une référence.** La résolution nom → `culture_config.id` se
  fait à la RECHERCHE ; le fragment, lui, ne stocke que l'identifiant. Renommer
  une culture depuis le bot n'orpheline donc rien (CA2bis) : le lien survit au
  libellé.

Deux moteurs, une seule sémantique
----------------------------------
La recherche de production est celle de PostgreSQL, en dictionnaire `french`
(CA4) : `to_tsvector` maintenu à l'écriture, `plainto_tsquery` à la lecture,
classement par `ts_rank_cd`. Les tests tournent en SQLite (voir
`tests/conftest.py`), qui n'a ni dictionnaire ni `tsvector` : le repli
`_SQLITE` ci-dessous reproduit la même sémantique — mêmes lexèmes indexés,
même pondération titre/contenu, même échelle de score — avec un radicalisateur
minimal au lieu du stemmer Snowball. C'est un repli de test, pas un second
moteur : la mesure du CA13 qui conditionne l'activation en production doit être
rejouée sur PostgreSQL, via `tools/mesurer_corpus_savoir.py`.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy import Text, cast, func, or_, text
from sqlalchemy.dialects.postgresql import TSQUERY
from sqlalchemy.orm import Session
from unidecode import unidecode

from app.services.context import TenantContext
from config import RAG_MAX_PASSAGES, RAG_SEUIL_CONFIANCE
from database.models import CultureConfig, KnowledgeChunk, KnowledgeDocument

log = logging.getLogger("potager")


# ─────────────────────────────────────────────────────────────────────────────
# Vocabulaire [CA1, CA2]
# -----------------------------------------------------------------------------
# Fermé et validé ici, pas par un CHECK en base : même arbitrage que
# `culture_config.exposition` (migration_v39) — un vocabulaire révisable en
# produit, dont l'unique point d'écriture est ce module.
# ─────────────────────────────────────────────────────────────────────────────
FAMILLE_AGRONOMIE = "agronomie"
FAMILLE_DOC_APP = "doc_app"
FAMILLE_MEMOIRE_POTAGER = "memoire_potager"
FAMILLES: frozenset[str] = frozenset({
    FAMILLE_AGRONOMIE, FAMILLE_DOC_APP, FAMILLE_MEMOIRE_POTAGER,
})

NIVEAU_VERIFIE = "verifie"
NIVEAU_INDICATIF = "indicatif"
NIVEAUX_CONFIANCE: frozenset[str] = frozenset({NIVEAU_VERIFIE, NIVEAU_INDICATIF})

# [CA14] Issue d'une recherche, journalisée dans `routage_logs.issue_savoir`.
# Trois valeurs, et le journal doit pouvoir les distinguer : « rien trouvé » et
# « trouvé mais pas assez sûr » n'appellent pas le même travail éditorial.
ISSUE_SERVI = "servi"        # confiance élevée → réponse servie telle quelle, zéro jeton
ISSUE_TRANSMIS = "transmis"  # passages trouvés, confiance insuffisante → descend à l'étage 3
ISSUE_VIDE = "vide"          # aucun passage : c'est CETTE ligne qui définit le contenu à écrire

# [CA4] La configuration du dictionnaire est EXPLICITE et partagée avec
# `migrations/migration_v42.sql`, qui la crée. Elle sert à l'ÉCRITURE du vecteur
# comme à l'INTERROGATION : les deux côtés doivent employer la même, sinon rien
# ne se retrouve jamais.
#
# `french_sans_accent` dérive de `french` (lemmatisation intacte : « semé »
# retrouve « semer », « arrosé » retrouve « arroser ») et lui ajoute `unaccent`. Ce n'est pas un raffinement : `french` seule traite « récolter »
# et « recolter » comme DEUX LEXÈMES SANS RAPPORT, et sur un clavier mobile
# taper sans accent est la norme. Constaté en production le 04/09/2026 —
# « quand recolter mes carottes ? » servait une réponse sur les carottes
# fourchues, là où la même question accentuée trouvait la bonne section.
#
# Le repli SQLite passe par `unidecode` (voir `lexemes`), donc il retirait DÉJÀ
# les accents : les deux moteurs divergeaient en silence, et toute mesure locale
# était optimiste sur les termes accentués. Ils s'accordent désormais.
CONFIG_FTS = "french_sans_accent"

# Pondération `ts_rank_cd` : un fragment dont le TITRE porte le terme cherché
# répond mieux qu'un fragment qui ne fait que le mentionner. Poids PostgreSQL
# 'A' pour le titre du document et l'intitulé de section, 'B' pour le contenu.
_POIDS_TITRE = "A"
_POIDS_CONTENU = "B"

# `ts_rank_cd(..., 32)` normalise le rang en `rang / (rang + 1)` : le score sort
# borné dans [0, 1[, directement comparable au seuil de confiance, sans
# étalonnage arbitraire côté Python.
_NORMALISATION_RANG = 32


# ─────────────────────────────────────────────────────────────────────────────
# Contrat de retour [CA7, CA8] — des passages, des sources, un score
# ─────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Passage:
    """Un fragment retrouvé, tel qu'il est écrit dans le dépôt.

    `contenu` n'est jamais reformulé : c'est le texte relu et versionné, pas une
    paraphrase. `reference` est l'identité stable du fragment — c'est elle qui
    part dans `questions_cache.fragment_id` (CA11) pour qu'une correction de la
    fiche fasse tomber les réponses qui en dérivaient.
    """

    reference: str
    titre_document: str
    intitule: Optional[str]
    contenu: str
    source: str
    niveau_confiance: str
    score: float
    # Vrai si le fragment appartient à un potager précis (US-141). Un passage
    # privé ne peut jamais alimenter une réponse mémorisée en savoir PARTAGÉ —
    # voir `contexte_partageable` ci-dessous.
    prive: bool = False

    @property
    def titre_complet(self) -> str:
        """[CA12] Le titre du document est conservé sur chaque fragment : sans
        lui, « arroser deux fois par semaine » ne dit pas de quelle culture."""
        return f"{self.titre_document} — {self.intitule}" if self.intitule else self.titre_document


@dataclass(frozen=True)
class ContexteConnaissance:
    """[CA8] Ce que l'étage du savoir retourne — et rien d'autre.

    Pas de champ `reponse`, pas de texte rédigé, volontairement : la seule façon
    d'obtenir une phrase depuis cet objet est `restituer()`, qui recopie un
    passage humainement écrit. Aucun appel modèle n'a lieu dans ce chemin.
    """

    question: str
    passages: tuple[Passage, ...] = ()
    # [CA7] Score de confiance GLOBAL de la recherche, dans [0, 1].
    confiance: float = 0.0
    # [CA7] Deux issues, et deux seulement : servie directement, ou transmise.
    suffisant: bool = False
    issue: str = ISSUE_VIDE
    latence_ms: int = 0
    # [CA6] Métadonnées effectivement appliquées — vide si elles ont dû être
    # relâchées pour ne pas vider le résultat. Sert au diagnostic, pas au
    # filtrage.
    metadonnees_appliquees: dict[str, str] = field(default_factory=dict)

    @property
    def sources(self) -> tuple[str, ...]:
        """Sources citées, dédoublonnées, dans l'ordre du classement."""
        vues: list[str] = []
        for passage in self.passages:
            if passage.source and passage.source not in vues:
                vues.append(passage.source)
        return tuple(vues)

    @property
    def references(self) -> tuple[str, ...]:
        return tuple(passage.reference for passage in self.passages)

    @property
    def contexte_partageable(self) -> bool:
        """Vrai si aucun passage privé n'a été retenu — condition pour qu'une
        réponse qui en dérive puisse être mémorisée en savoir partagé
        (`questions_cache`, `potager_id = NULL`). Un seul passage privé suffit à
        interdire le partage : c'est la fuite inter-potagers qu'US-095 / CA8
        contrôle déjà côté texte, refusée ici en amont, à la source."""
        return all(not passage.prive for passage in self.passages)


# ─────────────────────────────────────────────────────────────────────────────
# Indexation du texte — le même découpage en lexèmes des deux côtés
# ─────────────────────────────────────────────────────────────────────────────
_NON_ALPHANUM = re.compile(r"[^a-z0-9]+")

# Mots vides français, pour le repli SQLite uniquement : PostgreSQL les retire
# lui-même via le dictionnaire `french`. Liste courte et assumée — elle ne vise
# que les mots qui, présents dans presque toutes les questions, feraient
# ressortir n'importe quel fragment (« pourquoi mes tomates » ne doit pas
# matcher sur « mes »).
_MOTS_VIDES: frozenset[str] = frozenset({
    "a", "au", "aux", "avec", "ce", "ces", "cet", "cette", "dans", "de", "des",
    "du", "elle", "en", "est", "et", "eux", "il", "ils", "je", "la", "le",
    "les", "leur", "lui", "ma", "mais", "me", "mes", "moi", "mon", "ne", "nos",
    "notre", "nous", "on", "ou", "par", "pas", "peu", "pour", "qu", "que",
    "qui", "sa", "se", "ses", "son", "sur", "ta", "te", "tes", "toi", "ton",
    "tu", "un", "une", "vos", "votre", "vous", "y", "ai", "ont", "sont", "ete",
    "etre", "avoir", "fait", "faire", "plus", "moins", "tres", "bien", "quoi",
    "dois", "doit", "peut", "puis", "quand", "comme",
})

_LONGUEUR_MIN_LEXEME = 3


def _radical(mot: str) -> str:
    """Radicalisation minimale — repli SQLite uniquement.

    Ce n'est PAS un stemmer : il ne coupe que les marques de pluriel et le `e`
    final, ce qui suffit à rapprocher « tomates » de « tomate » et « semis » de
    « semi ». Sur PostgreSQL, c'est Snowball qui fait ce travail, bien mieux.
    Toute divergence de résultat entre les deux moteurs vient d'ici, et c'est
    la raison pour laquelle la mesure du CA13 doit être rejouée sur PostgreSQL.
    """
    for suffixe in ("aux", "es", "s", "x"):
        if len(mot) > len(suffixe) + 2 and mot.endswith(suffixe):
            return mot[: -len(suffixe)]
    return mot


def lexemes(texte: Optional[str]) -> list[str]:
    """Découpe un texte en lexèmes normalisés (minuscules, sans accents, sans
    mots vides). Utilisée pour l'indexation ET pour l'interrogation du repli
    SQLite : les deux côtés doivent produire les mêmes formes, sinon rien ne se
    retrouve jamais."""
    normalise = _NON_ALPHANUM.sub(" ", unidecode((texte or "").strip().lower()))
    retenus = []
    for mot in normalise.split():
        if len(mot) < _LONGUEUR_MIN_LEXEME or mot in _MOTS_VIDES:
            continue
        retenus.append(_radical(mot))
    return retenus


def _est_postgresql(db: Session) -> bool:
    return db.get_bind().dialect.name == "postgresql"


def _valeur_recherche_fts(db: Session, titre: str, intitule: Optional[str], contenu: str,
                          termes_indexation: str = ""):
    """[CA4, note technique] Valeur du vecteur de recherche, calculée À
    L'ÉCRITURE du fragment — jamais à chaque requête.

    Sous PostgreSQL, une expression SQL `setweight(to_tsvector('french', …))`
    qui part telle quelle dans l'INSERT : c'est le moteur qui applique le
    dictionnaire, pas Python. Sous SQLite, la suite des lexèmes indexés, le
    titre répété pour lui donner le poids que `setweight` lui donne côté
    PostgreSQL.

    `termes_indexation` porte les formulations sous lesquelles le jardinier
    désigne le sujet (« cul noir » pour une nécrose apicale, « poudre blanche »
    pour l'oïdium). Elles rejoignent le poids `A`, avec le titre et l'intitulé :
    c'est exactement le rôle d'un alias, peser comme un titre. Elles ne sont
    JAMAIS versées dans `contenu`, qui reste le seul texte que `restituer()`
    recopie — un alias ne doit pas pouvoir fuir vers le jardinier.
    """
    entete = " ".join(filter(None, (titre, intitule)))
    if _est_postgresql(db):
        vecteur_entete = func.to_tsvector(CONFIG_FTS, entete)
        poids_a = func.setweight(vecteur_entete, _POIDS_TITRE)
        if termes_indexation:
            # Un alias n'apporte QUE le vocabulaire que la section n'a pas déjà.
            # `ts_rank_cd` compte les occurrences : sans ce retrait, une ligne
            # d'alias qui répète le nom de la culture (« ver carotte ; galeries
            # carotte ; mouche de la carotte ») triple son poids `A` sur un mot
            # que le titre du document porte DÉJÀ sur tous les fragments de la
            # fiche. Le gain est nul pour trouver la fiche — elle est trouvée de
            # toute façon — et la section vole le classement à ses voisines.
            # Mesuré : cette seule section remportait « comment éclaircir mes
            # carottes ? » et « quand récolter mes carottes ? ».
            # Le retrait se fait par lexèmes et côté moteur (`ts_delete` sur
            # `tsvector_to_array`) : le dictionnaire `french` reste maître du
            # stemming, aucun découpage n'est réécrit en Python.
            poids_a = poids_a.op("||")(func.setweight(
                func.ts_delete(
                    func.to_tsvector(CONFIG_FTS, termes_indexation),
                    func.tsvector_to_array(vecteur_entete),
                ),
                _POIDS_TITRE,
            ))
        return poids_a.op("||")(
            func.setweight(func.to_tsvector(CONFIG_FTS, contenu or ""), _POIDS_CONTENU)
        )
    lexemes_entete = lexemes(entete)
    deja = set(lexemes_entete)
    lexemes_entete += [l for l in lexemes(termes_indexation) if l not in deja]
    return " ".join(lexemes_entete + lexemes_entete + lexemes(contenu))


def _tsquery(question: str):
    """Requête plein texte PostgreSQL, en OU plutôt qu'en ET.

    `plainto_tsquery` assemble ses termes avec `&` : « pourquoi mes tomates ont
    le cul noir » exigerait alors que le fragment contienne AUSSI « pourquoi »,
    et ne retrouverait donc jamais une fiche qui répond pourtant exactement à la
    question. Le `replace` bascule l'opérateur en `|` sans quitter le
    dictionnaire `french` — c'est lui, et non un découpage écrit en Python, qui
    reste maître du stemming et des mots vides. Le classement par `ts_rank_cd`
    fait ensuite le tri : un fragment qui porte tous les termes passe devant
    celui qui n'en porte qu'un.
    """
    return cast(
        func.replace(cast(func.plainto_tsquery(CONFIG_FTS, question), Text), "&", "|"),
        TSQUERY,
    )


# ─────────────────────────────────────────────────────────────────────────────
# [CA5] LE filtre d'isolation — un seul endroit, jamais chez l'appelant
# ─────────────────────────────────────────────────────────────────────────────
def _requete_base(db: Session, ctx: TenantContext):
    """Unique constructeur de requête sur `knowledge_chunks` du projet.

    Toute lecture de la table passe par ici, et le filtre est posé
    inconditionnellement : c'est ce qui rend vraie — et vérifiable — la phrase
    « il n'existe aucun chemin de code capable d'interroger la table sans ce
    filtre » (CA5). Un `potager_id` absent du contexte est refusé plutôt que
    replié sur une valeur par défaut : sans tenant courant, une recherche n'est
    pas isolable, donc elle n'a pas lieu.
    """
    if ctx is None or ctx.potager_id is None:
        raise ValueError("Aucun potager courant : recherche de connaissance refusée")
    return (
        db.query(KnowledgeChunk, KnowledgeDocument)
        .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
        .filter(or_(
            KnowledgeChunk.potager_id.is_(None),
            KnowledgeChunk.potager_id == ctx.potager_id,
        ))
    )


# ─────────────────────────────────────────────────────────────────────────────
# [CA6] Métadonnées — elles restreignent quand elles sont là, jamais autrement
# ─────────────────────────────────────────────────────────────────────────────
# Vocabulaire OUVERT côté fragments : ces motifs servent à restreindre une
# recherche, jamais à valider une saisie. Un type absent d'ici reste indexable
# et retrouvable, il ne bénéficie simplement d'aucune restriction.
TYPES_FRAGMENT: dict[str, tuple[str, ...]] = {
    "maladie": ("maladie", "mildiou", "oidium", "rouille", "pourriture", "pourri",
                "tache", "taches", "jaunit", "jaunissent", "fane", "fanent",
                "ravageur", "puceron", "limace", "chenille", "cul noir", "champignon"),
    "semis":   ("semis", "semer", "seme", "germination", "germe", "godet",
                "repiquage", "repiquer", "levee"),
    "association": ("associer", "association", "compagnon", "compagnonnage",
                    "a cote de", "voisinage"),
    "rotation": ("rotation", "assolement", "precedent cultural", "delai de retour",
                 "revenir sur"),
    "arrosage": ("arroser", "arrosage", "irrigation", "paillage", "pailler"),
    "recolte": ("recolter", "recolte", "cueillir", "maturite", "conservation"),
}


def detecter_type(question: str) -> Optional[str]:
    """Type de question déduit du vocabulaire employé — déterministe, zéro jeton.

    Retourne `None` dès qu'aucun motif ne ressort : CA6 exige qu'une métadonnée
    absente soit ignorée, pas devinée. Deviner ici reviendrait à poser un filtre
    faux, donc à vider un résultat qui aurait été bon.
    """
    normalisee = _NON_ALPHANUM.sub(" ", unidecode((question or "").strip().lower()))
    meilleur: Optional[tuple[str, int]] = None
    for type_fragment, motifs in TYPES_FRAGMENT.items():
        for motif in motifs:
            if re.search(rf"\b{re.escape(motif)}", normalisee):
                if meilleur is None or len(motif) > meilleur[1]:
                    meilleur = (type_fragment, len(motif))
    return meilleur[0] if meilleur else None


def resoudre_culture(db: Session, ctx: TenantContext, question: str) -> Optional[int]:
    """[CA2, CA6] Identifiant de la culture nommée dans la question, ou `None`.

    La résolution se fait contre `culture_config`, le référentiel réel — c'est
    ce qui fait que renommer une culture change ce que cette fonction reconnaît,
    sans toucher au moindre fragment (CA2bis). Le libellé le plus long gagne,
    pour que « chou de Bruxelles » l'emporte sur « chou ».
    """
    normalisee = _NON_ALPHANUM.sub(" ", unidecode((question or "").strip().lower()))
    if not normalisee:
        return None
    fiches = (
        db.query(CultureConfig.id, CultureConfig.nom)
        .filter(or_(
            CultureConfig.potager_id.is_(None),
            CultureConfig.potager_id == ctx.potager_id,
        ))
        .all()
    )
    meilleur: Optional[tuple[int, int]] = None
    for culture_id, nom in fiches:
        nom_normalise = _NON_ALPHANUM.sub(" ", unidecode((nom or "").strip().lower())).strip()
        if len(nom_normalise) < _LONGUEUR_MIN_LEXEME:
            continue
        # Chaque mot du nom est réduit à son radical puis rouvert à sa flexion :
        # « courgette verte » doit reconnaître « mes courgettes vertes ». Un nom
        # de culture est accordé dans une question, il ne s'y cite pas au
        # singulier — et un renommage produit précisément des noms composés.
        motif = r"\s+".join(
            rf"{re.escape(_radical(mot))}\w*" for mot in nom_normalise.split()
        )
        if re.search(rf"\b{motif}", normalisee):
            if meilleur is None or len(nom_normalise) > meilleur[1]:
                meilleur = (culture_id, len(nom_normalise))
    return meilleur[0] if meilleur else None


# ─────────────────────────────────────────────────────────────────────────────
# [CA4, CA6, CA7] La recherche
# ─────────────────────────────────────────────────────────────────────────────
def _classer_postgresql(db: Session, ctx: TenantContext, question: str,
                        culture_id: Optional[int], type_fragment: Optional[str],
                        limite: int) -> list[tuple[KnowledgeChunk, KnowledgeDocument, float]]:
    requete_texte = _tsquery(question)
    rang = func.ts_rank_cd(
        KnowledgeChunk.recherche_fts, requete_texte, _NORMALISATION_RANG,
    )
    requete = _requete_base(db, ctx).add_columns(rang.label("rang")).filter(
        KnowledgeChunk.recherche_fts.op("@@")(requete_texte)
    )
    requete = _restreindre(requete, culture_id, type_fragment)
    lignes = requete.order_by(text("rang DESC")).limit(limite).all()
    return [(fragment, document, float(score or 0.0)) for fragment, document, score in lignes]


def _classer_sqlite(db: Session, ctx: TenantContext, question: str,
                    culture_id: Optional[int], type_fragment: Optional[str],
                    limite: int) -> list[tuple[KnowledgeChunk, KnowledgeDocument, float]]:
    """Repli de test — même sémantique, moteur sans dictionnaire.

    Le classement est fait en Python sur les seuls fragments qui portent au
    moins un lexème de la question : c'est le pendant exact du `@@` PostgreSQL,
    à ceci près que le score est une couverture de termes plutôt qu'un
    `ts_rank_cd`. Les deux restent dans [0, 1] et rangent dans le même ordre sur
    les cas usuels.
    """
    termes = lexemes(question)
    if not termes:
        return []
    requete = _requete_base(db, ctx).filter(
        or_(*[KnowledgeChunk.recherche_fts.like(f"%{terme}%") for terme in termes])
    )
    requete = _restreindre(requete, culture_id, type_fragment)

    classees: list[tuple[KnowledgeChunk, KnowledgeDocument, float]] = []
    for fragment, document in requete.all():
        indexe = (fragment.recherche_fts or "").split()
        if not indexe:
            continue
        presents = [terme for terme in set(termes) if any(mot.startswith(terme) for mot in indexe)]
        if not presents:
            continue
        couverture = len(presents) / len(set(termes))
        # Densité : un terme répété (donc porté par le titre, dupliqué à
        # l'indexation) pèse davantage — c'est l'équivalent du `setweight`.
        densite = sum(1 for mot in indexe if any(mot.startswith(t) for t in presents)) / len(indexe)
        classees.append((fragment, document, round(couverture * (0.85 + 0.15 * min(densite * 4, 1.0)), 6)))
    classees.sort(key=lambda ligne: (-ligne[2], ligne[0].id))
    return classees[:limite]


def _restreindre(requete, culture_id: Optional[int], type_fragment: Optional[str]):
    """[CA6] Restriction par métadonnée — appliquée seulement quand elle existe."""
    if culture_id is not None:
        requete = requete.filter(KnowledgeChunk.culture_id == culture_id)
    if type_fragment:
        requete = requete.filter(KnowledgeChunk.type == type_fragment)
    return requete


def rechercher(
    db: Session,
    ctx: TenantContext,
    question: str,
    *,
    culture_id: Optional[int] = None,
    type_fragment: Optional[str] = None,
    detecter_metadonnees: bool = True,
    limite: int = RAG_MAX_PASSAGES,
    seuil: float = RAG_SEUIL_CONFIANCE,
) -> ContexteConnaissance:
    """[CA4 → CA9] Retrouve les passages qui répondent à la question.

    Ne rédige rien, n'appelle aucun modèle, ne lève pas sur une base vide : une
    recherche sans résultat est une issue légitime (`ISSUE_VIDE`), et c'est même
    l'issue la plus utile au début — c'est elle qui dit quoi écrire (CA14).

    [CA6] Les métadonnées restreignent quand elles sont présentes et sont
    IGNORÉES quand elles ne le sont pas. Mieux : si la restriction vide le
    résultat, elle est relâchée et la recherche est rejouée sans elle. Un filtre
    qui vide un résultat est un filtre faux — mieux vaut un passage un peu large
    qu'aucun passage.
    """
    debut = time.monotonic()
    question = (question or "").strip()
    if not question:
        return ContexteConnaissance(question=question, issue=ISSUE_VIDE)

    if detecter_metadonnees:
        if culture_id is None:
            culture_id = resoudre_culture(db, ctx, question)
        if type_fragment is None:
            type_fragment = detecter_type(question)

    classer = _classer_postgresql if _est_postgresql(db) else _classer_sqlite

    # [CA6] Relâchement PROGRESSIF, du plus restrictif au plus large. Une
    # restriction qui vide le résultat ne vaut rien, mais tout relâcher d'un
    # coup jetterait aussi la métadonnée qui, elle, était bonne : la culture est
    # un signal bien plus sûr que le type de question, elle est donc la dernière
    # abandonnée. « des taches sur les feuilles de courgette » ne doit pas
    # perdre « courgette » parce qu'aucun fragment ne porte le type « maladie ».
    tentatives = [(culture_id, type_fragment)]
    if culture_id is not None and type_fragment:
        tentatives.append((culture_id, None))
        tentatives.append((None, type_fragment))
    if culture_id is not None or type_fragment:
        tentatives.append((None, None))

    lignes: list = []
    metadonnees: dict[str, str] = {}
    for culture_essai, type_essai in tentatives:
        lignes = classer(db, ctx, question, culture_essai, type_essai, limite)
        if lignes:
            if culture_essai is not None:
                metadonnees["culture_id"] = str(culture_essai)
            if type_essai:
                metadonnees["type"] = type_essai
            break

    passages = tuple(
        Passage(
            reference=fragment.reference,
            titre_document=fragment.titre_document,
            intitule=fragment.intitule,
            contenu=fragment.contenu,
            source=document.source,
            niveau_confiance=document.niveau_confiance,
            score=score,
            prive=fragment.potager_id is not None,
        )
        for fragment, document, score in lignes
    )

    confiance = _confiance_globale(passages)
    # [CA7] Deux issues, et deux seulement. Un passage seulement `indicatif`
    # n'est jamais servi tel quel : le donner comme réponse ferait passer pour
    # établi ce que le corpus lui-même déclare incertain. Il descend en
    # contexte à l'étage 3, qui peut le nuancer.
    suffisant = bool(
        passages
        and confiance >= seuil
        and passages[0].niveau_confiance == NIVEAU_VERIFIE
    )
    if not passages:
        issue = ISSUE_VIDE
    elif suffisant:
        issue = ISSUE_SERVI
    else:
        issue = ISSUE_TRANSMIS

    contexte = ContexteConnaissance(
        question=question,
        passages=passages,
        confiance=confiance,
        suffisant=suffisant,
        issue=issue,
        latence_ms=int((time.monotonic() - debut) * 1000),
        metadonnees_appliquees=metadonnees,
    )
    # [CA14] Trace immédiate : le journal en base (`routage_logs`) n'est écrit
    # qu'en fin de cascade, cette ligne-ci sert au diagnostic à chaud.
    #
    # Elle nomme le passage de tête, et pas seulement leur NOMBRE : un
    # `passages=3` sans dire lesquels se lit comme un échec de recherche alors
    # que la bonne section est là. C'est ce qui a fait conclure à tort, le
    # 04/09/2026, qu'une fiche n'avait pas été trouvée — elle l'était, en tête.
    log.info(
        "📚 SAVOIR         │ issue=%-8s │ score=%.3f │ passages=%d │ %d ms │ %s │ '%s'",
        issue, confiance, len(passages), contexte.latence_ms,
        _passages_lisibles(passages),
        question[:60],
    )
    return contexte


def _passages_lisibles(passages: tuple[Passage, ...]) -> str:
    """TOUS les passages retenus, en une bribe lisible dans le journal.

    Nommer le seul passage de tête est pire que de n'en nommer aucun : sur le
    chemin `transmis`, les trois partent ensemble dans le prompt, et la réponse
    peut très bien se construire sur le deuxième et le troisième. Le 04/09/2026,
    une réponse sur l'enroulement des feuilles de tomate était entièrement tirée
    des passages 2 et 3 — le journal ne montrait que le premier, qui traitait
    d'effeuillage, et la relecture est allée chercher dans la mauvaise fiche.

    Le fichier et l'intitulé, pas la référence complète : celle-ci fait parfois
    cent trente caractères et noierait le reste de la ligne.
    """
    if not passages:
        return "passages=—"
    bribes = []
    for rang, passage in enumerate(passages, start=1):
        fichier = passage.reference.rsplit("/", 1)[-1].split("#", 1)[0]
        intitule = (passage.intitule or "préambule")[:38]
        bribes.append(f"{rang}·{fichier}::{intitule}")
    return " ┊ ".join(bribes)


def _confiance_globale(passages: tuple[Passage, ...]) -> float:
    """[CA7] Score de confiance GLOBAL de la recherche, dans [0, 1].

    Le meilleur passage commande, avec un léger bonus quand un second passage
    le corrobore : deux fragments concordants valent mieux qu'un seul, sans que
    la corroboration puisse jamais compenser un premier passage faible — sinon
    la quantité tiendrait lieu de qualité.
    """
    if not passages:
        return 0.0
    meilleur = passages[0].score
    corroboration = passages[1].score if len(passages) > 1 else 0.0
    return round(min(1.0, meilleur + 0.1 * corroboration), 6)


# ─────────────────────────────────────────────────────────────────────────────
# [CA7, CA8] Restitution — citation, jamais génération
# ─────────────────────────────────────────────────────────────────────────────
def restituer(contexte: ContexteConnaissance) -> str:
    """Assemble la réponse servie directement, à coût nul (CA7).

    Aucune rédaction : le texte est celui du fragment, recopié tel qu'il a été
    relu et versionné, suivi de sa source. Cette fonction ne fait que coller —
    elle n'a aucune raison d'exister ailleurs qu'ici, et surtout aucune raison
    d'appeler un modèle.
    """
    if not contexte.passages:
        return ""
    passage = contexte.passages[0]
    lignes = [passage.contenu.strip()]
    if passage.source:
        lignes.append(f"\n_Source : {passage.source}_")
    return "\n".join(lignes)


def contexte_pour_raisonnement(contexte: ContexteConnaissance, max_passages: int = RAG_MAX_PASSAGES) -> str:
    """[CA7] Ce qui descend vers l'étage 3 quand la confiance est insuffisante.

    Des passages étiquetés, pas une réponse : l'étage de raisonnement reçoit de
    la matière et reste seul à rédiger. Une confiance insuffisante ne déclare
    donc jamais la question sans réponse — elle change seulement d'étage.
    """
    if not contexte.passages:
        return ""
    blocs = [
        f"[{passage.titre_complet} — {passage.source}, {passage.niveau_confiance}]\n{passage.contenu.strip()}"
        for passage in contexte.passages[:max_passages]
    ]
    return "\n\n".join(blocs)


# ─────────────────────────────────────────────────────────────────────────────
# [CA10, CA11, CA12] Écriture — appelée par l'outil d'ingestion, et par lui seul
# ─────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class FragmentAIngerer:
    """Un fragment prêt à indexer, tel que le découpage l'a produit."""

    reference: str
    ordre: int
    intitule: Optional[str]
    contenu: str
    culture_id: Optional[int] = None
    type: Optional[str] = None
    saison: Optional[str] = None
    # Alias d'indexation extraits de la fiche : indexés au poids du titre,
    # jamais stockés dans `contenu`, donc jamais affichés.
    termes_indexation: str = ""


def valider_entete(famille: str, niveau_confiance: str) -> None:
    """Refuse un vocabulaire hors périmètre à l'écriture — l'ingestion doit
    échouer sur un en-tête fautif, pas indexer un document inclassable."""
    if famille not in FAMILLES:
        raise ValueError(f"Famille inconnue : {famille!r} (attendu : {', '.join(sorted(FAMILLES))})")
    if niveau_confiance not in NIVEAUX_CONFIANCE:
        raise ValueError(
            f"Niveau de confiance inconnu : {niveau_confiance!r} "
            f"(attendu : {', '.join(sorted(NIVEAUX_CONFIANCE))})"
        )


def enregistrer_document(
    db: Session,
    *,
    reference: str,
    titre: str,
    famille: str,
    source: str,
    niveau_confiance: str,
    empreinte: str,
    potager_id: Optional[int] = None,
) -> tuple[KnowledgeDocument, bool]:
    """[CA10] Crée ou met à jour le document. Retourne `(document, inchangé)`.

    `inchangé` vrai signifie « même empreinte » : l'appelant n'a alors rien à
    réécrire, et c'est exactement ce qui rend l'ingestion idempotente — un rejeu
    sans modification ne touche pas une ligne.
    """
    valider_entete(famille, niveau_confiance)
    document = (
        db.query(KnowledgeDocument)
        .filter(KnowledgeDocument.reference == reference)
        .first()
    )
    if document is None:
        document = KnowledgeDocument(
            reference=reference, titre=titre, famille=famille, source=source,
            niveau_confiance=niveau_confiance, empreinte=empreinte, potager_id=potager_id,
        )
        db.add(document)
        db.flush()
        return document, False

    if document.empreinte == empreinte:
        return document, True

    document.titre = titre
    document.famille = famille
    document.source = source
    document.niveau_confiance = niveau_confiance
    document.empreinte = empreinte
    document.potager_id = potager_id
    document.mis_a_jour_le = datetime.utcnow()
    db.flush()
    return document, False


def remplacer_fragments(
    db: Session, document: KnowledgeDocument, fragments: Iterable[FragmentAIngerer],
) -> tuple[int, list[str]]:
    """[CA11] Remplace INTÉGRALEMENT les fragments d'un document.

    Retourne le nombre de fragments écrits et **toutes** les références que le
    document portait avant le remplacement — ce sont elles que l'appelant passe
    à `cache_questions.invalider_par_fragment` (US-095 / CA10).

    Toutes, et non les seules références disparues : une section corrigée garde
    son intitulé, donc sa référence, alors que son CONTENU vient de changer. Ne
    retenir que les références disparues laisserait vivre pendant des mois
    exactement la réponse erronée que le CA11 veut faire tomber — la correction
    la plus fréquente étant précisément celle qui ne renomme rien.

    Remplacement complet plutôt que réconciliation fragment par fragment : le
    découpage lui-même change quand le document change (une section coupée en
    deux, deux sections fusionnées), et une réconciliation par intitulé ferait
    survivre des fragments qui n'existent plus dans le texte relu.
    """
    anciennes = [
        reference
        for (reference,) in db.query(KnowledgeChunk.reference)
        .filter(KnowledgeChunk.document_id == document.id)
        .all()
    ]
    db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == document.id).delete(
        synchronize_session=False
    )
    # Les fragments supprimés peuvent rester dans l'identity map de la session
    # appelante ; sans cela, un moteur qui réattribue les mêmes identifiants
    # (SQLite) déclencherait un avertissement d'identité au réinsertion.
    db.expire_all()

    ecrits = 0
    for fragment in fragments:
        db.add(KnowledgeChunk(
            document_id=document.id,
            # [CA2] Dénormalisation depuis le document : jamais saisie à part,
            # sans quoi les deux valeurs pourraient diverger et le filtre
            # d'isolation porterait sur la mauvaise.
            potager_id=document.potager_id,
            reference=fragment.reference,
            ordre=fragment.ordre,
            titre_document=document.titre,
            intitule=fragment.intitule,
            contenu=fragment.contenu,
            culture_id=fragment.culture_id,
            type=fragment.type,
            saison=fragment.saison,
            recherche_fts=_valeur_recherche_fts(
                db, document.titre, fragment.intitule, fragment.contenu,
                fragment.termes_indexation,
            ),
        ))
        ecrits += 1
    db.flush()
    return ecrits, anciennes


def supprimer_document(db: Session, reference: str) -> tuple[int, list[str]]:
    """Retire un document et ses fragments — pour un fichier disparu du dépôt.
    Retourne `(fragments supprimés, références retirées)`, à invalider comme
    pour une réingestion (CA11)."""
    document = (
        db.query(KnowledgeDocument)
        .filter(KnowledgeDocument.reference == reference)
        .first()
    )
    if document is None:
        return 0, []
    references = [
        ref for (ref,) in db.query(KnowledgeChunk.reference)
        .filter(KnowledgeChunk.document_id == document.id).all()
    ]
    db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == document.id).delete(
        synchronize_session=False
    )
    db.delete(document)
    db.flush()
    return len(references), references


def purger_potager(db: Session, potager_id: int) -> int:
    """Supprime la connaissance PRIVÉE d'un potager — appelée par la purge
    physique (`app.services.potagers.purger_potager`, US-084 / CA7). Le savoir
    global (`potager_id IS NULL`) n'est jamais touché : il n'appartient à
    personne. Ne commit pas — la purge est une transaction unique."""
    supprimes = (
        db.query(KnowledgeChunk)
        .filter(KnowledgeChunk.potager_id == potager_id)
        .delete(synchronize_session=False)
    )
    db.query(KnowledgeDocument).filter(KnowledgeDocument.potager_id == potager_id).delete(
        synchronize_session=False
    )
    return supprimes


def compter(db: Session) -> dict[str, int]:
    """Volumétrie du socle — utilisée par l'outil d'ingestion et la mesure du
    CA13. Lecture d'administration, hors périmètre tenant : elle ne rend aucun
    contenu, seulement des compteurs."""
    return {
        "documents": db.query(func.count(KnowledgeDocument.id)).scalar() or 0,
        "fragments": db.query(func.count(KnowledgeChunk.id)).scalar() or 0,
    }

"""
app/services/interpreteur_commandes.py — Piloter le bot par une phrase [US-172]
================================================================================
Le compagnon de terrain savait interpréter **un geste de jardin** dicté en
langage naturel — les dix-huit gestes du référentiel — et rien d'autre. Tout le
reste, les vingt-quatre commandes du bot et leurs sous-commandes, n'était
atteignable qu'en tapant la commande exacte, avec ses arguments dans le bon
ordre. US-171 a rendu ces commandes **visibles** dans le menu natif ; elle ne
les a pas rendues **dictables**.

Ce module est l'interpréteur que l'étage 0 de la cascade
(`docs/ARCHITECTURE_CIBLE_V2_reponses.md` §2.1) annonçait sans le fournir. Le
routeur d'US-093 distingue une action d'une question ; celui-ci distingue, à
l'intérieur des actions, **le geste au jardin** (qui produit un événement) de
**la commande de gestion** (qui pilote l'application).

Ce qu'il fait, et où il s'arrête
--------------------------------
Il traduit une phrase en **une** commande du catalogue et s'arrête là. Aucune
planification, aucune boucle d'outils, aucun enchaînement autonome : « crée la
parcelle nord et plante-y 6 tomates » est hors périmètre, une commande par
message. Il ne réimplémente non plus **aucun** comportement de commande (CA9) —
il produit un nom de commande et une liste d'arguments, que `bot.py` passe au
handler réellement enregistré, retrouvé par introspection. Même service, mêmes
contrôles, mêmes messages, mêmes claviers, mêmes droits.

Les règles d'abord, le modèle en repli sous contrainte fermée
-------------------------------------------------------------
Même doctrine qu'US-094 : les formes fréquentes sont reconnues par règles, à
zéro jeton (CA3). Le modèle n'intervient que sur ce que les règles laissent
passer, et **sous contrainte fermée** (CA4) : il choisit dans le catalogue
existant, et toute valeur qu'il produit doit se retrouver dans la phrase. Une
sortie non conforme est rejetée, jamais rattrapée — c'est la seule façon
d'empêcher une commande inventée d'être proposée à la validation.

Quatre gardes qui décident du reste
-----------------------------------
1. **Vouloir faire n'est pas demander comment faire** (CA2). « Comment supprimer
   une parcelle ? » reste une question de savoir servie par le socle (US-099) ;
   « supprime la parcelle nord » exécute. Les deux formes partagent presque tous
   leurs mots : c'est la confusion la plus probable de cette US, et
   `_est_demande_de_savoir` est ce qui l'empêche. Elle est testée AVANT toute
   règle.
2. **Une question n'est pas une déclaration.** Les règles qui lisent une phrase
   déclarative pour ÉCRIRE une valeur (« le mildiou attaque souvent la tomate »)
   sont refusées dès que la phrase s'ouvre comme une question. Sans ce garde,
   « qu'est-ce qui attaque mes poireaux ? » — la question phare d'US-173, servie
   par gabarit à zéro jeton — se serait transformée en écriture au référentiel.
   C'est le même discriminant qu'US-173 / CA3, et pour la même raison : à la
   dictée, le point d'interrogation n'existe pas, seule l'ouverture le dit.
3. **Le doute ne fait jamais agir** (CA12). Plusieurs commandes candidates
   conduisent à une demande de précision, jamais à l'exécution de la plus
   probable. Et une commande destructrice n'est jamais exécutée sur un
   rapprochement approximatif de nom : `resolve_parcelle` sait rapprocher
   « planche nord-est » de « Planche Nord » (Levenshtein ≤ 2, sous-chaîne), ce
   qui est le bon comportement pour rattacher un geste — et le mauvais pour
   supprimer. Le nom voisin est donc **proposé**, jamais substitué.
4. **Un argument manquant se complète, il n'échoue pas** (CA13). Une phrase
   incomplète ouvre une complétion guidée, et une valeur de vocabulaire fermé y
   est proposée en boutons — jamais devinée à partir d'un synonyme approchant.

Ce que ce module ne contient pas
--------------------------------
Ni la liste des commandes, ni la forme de leurs arguments, ni les vocabulaires
fermés : tout cela est déclaré dans `app.services.menu_commandes`, à côté du
catalogue de menu dont il se dérive (CA6), et les vocabulaires y sont lus aux
services qui les valident. Ce module ne porte que la **reconnaissance**.

Limite connue, assumée : un nom de parcelle en plusieurs mots est passé au
handler comme un seul argument (c'est le sens voulu), là où la même commande
tapée le découperait. La « commande équivalente » rappelée au jardinier (CA10)
est donc exacte pour un nom d'un seul mot, et indicative au-delà.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field, replace
from typing import Callable, Optional

from unidecode import unidecode

from app.services.context import TenantContext
from app.services.menu_commandes import (
    FORMES_PAR_CLE,
    TYPE_NOMBRE,
    TYPE_VOCABULAIRE,
    Argument,
    FormeCommande,
)

log = logging.getLogger("potager")


# ─────────────────────────────────────────────────────────────────────────────
# Origine de la décision — même vocabulaire que le routeur
# (`llm.routeur.ORIGINE_*`), pour que les deux journaux se lisent ensemble sans
# table de correspondance.
# ─────────────────────────────────────────────────────────────────────────────
ORIGINE_REGLE = "regle"
ORIGINE_MODELE = "modele"

#: Nature écrite au journal (CA18). Le routeur en connaît quatre (ACTION,
#: QUESTION_*) ; celle-ci est la cinquième, et elle se décide avant lui.
NATURE_COMMANDE = "COMMANDE"

#: Étage ayant résolu la demande, écrit dans `routage_logs.etage_resolveur`.
#: Distinct des étages du routeur : une commande n'est ni une donnée, ni un
#: savoir, ni un raisonnement — elle est résolue avant eux, à coût nul.
ETAGE_COMMANDE = "commande"

#: Issues journalisées (CA18) — ce qu'il est advenu de l'interprétation.
ISSUE_PROPOSEE = "proposee"      # récapitulatif affiché, en attente du jardinier
ISSUE_CONFIRMEE = "confirmee"
ISSUE_REFUSEE = "refusee"
ISSUE_ABANDONNEE = "abandonnee"  # précision demandée, jamais donnée

#: [CA4, CA12] En dessous de cette confiance, la sortie du modèle n'est pas
#: retenue : le doute rend la main à la cascade normale plutôt que d'exécuter la
#: commande la plus probable.
SEUIL_CONFIANCE_MODELE = 0.7


# ─────────────────────────────────────────────────────────────────────────────
# Résultat d'une interprétation
# ─────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class CommandeInterpretee:
    """Une phrase traduite en une commande du catalogue.

    `valeurs` est la forme de référence : un argument y est nommé, jamais
    positionnel. `args` en est la projection dans l'ordre du catalogue — ce qui
    sera posé dans `ctx.args` avant d'appeler le handler réellement enregistré,
    sous-commande en tête, exactement comme si le jardinier l'avait tapée.
    Passer par les noms est ce qui permet à un argument facultatif d'être omis
    sans décaler la lecture des suivants.
    """

    commande: str
    sous_commande: Optional[str]
    forme: FormeCommande
    valeurs: dict[str, str]
    origine: str
    confiance: float
    regle: Optional[str] = None
    latence_ms: int = 0
    texte_origine: str = ""
    #: [CA13] Arguments obligatoires que la phrase ne portait pas.
    manquants: tuple[Argument, ...] = ()
    #: [CA12] Noms voisins trouvés en base quand le nom dicté n'existe pas
    #: exactement — proposés, jamais substitués.
    candidats: tuple[str, ...] = ()
    #: L'argument sur lequel porte la proposition de candidats (CA12).
    argument_candidat: Optional[str] = None

    @property
    def args(self) -> tuple[str, ...]:
        valeurs = [self.sous_commande] if self.sous_commande else []
        valeurs += [
            self.valeurs[argument.nom]
            for argument in self.forme.arguments
            if self.valeurs.get(argument.nom)
        ]
        return tuple(valeurs)

    @property
    def complete(self) -> bool:
        return not self.manquants and not self.candidats

    def commande_equivalente(self) -> str:
        """[CA10] La commande tapée qui produirait le même effet — rappelée au
        jardinier pour qu'il apprenne la syntaxe sans avoir eu à l'apprendre."""
        return " ".join([f"/{self.commande}", *self.args]).strip()

    def avec(self, **valeurs: str) -> "CommandeInterpretee":
        """Une copie enrichie des valeurs collectées par la complétion guidée.

        Renseigner l'argument sur lequel portait une proposition de noms voisins
        lève d'elle-même cette proposition : le jardinier a choisi, le doute est
        levé — c'est le seul chemin par lequel un nom approchant devient une
        valeur, et il passe par lui (CA12).
        """
        fusion = dict(self.valeurs)
        fusion.update({nom: valeur for nom, valeur in valeurs.items() if valeur})
        tranche = self.argument_candidat is not None and fusion.get(self.argument_candidat)
        return replace(
            self,
            valeurs=fusion,
            manquants=tuple(a for a in self.manquants if not fusion.get(a.nom)),
            candidats=() if tranche else self.candidats,
            argument_candidat=None if tranche else self.argument_candidat,
        )

    def avec_candidats(self, argument: str, candidats: tuple[str, ...]) -> "CommandeInterpretee":
        """[CA12] Le nom dicté n'existe pas exactement : les noms voisins sont
        PROPOSÉS, et la valeur dictée est retirée pour qu'aucun chemin ne puisse
        l'exécuter telle quelle."""
        valeurs = {nom: v for nom, v in self.valeurs.items() if nom != argument}
        return replace(
            self, valeurs=valeurs, candidats=candidats, argument_candidat=argument
        )


@dataclass(frozen=True)
class Ambiguite:
    """[CA12] Plusieurs commandes candidates — une précision est demandée, rien
    n'est exécuté. Ce n'est pas un échec : c'est le refus d'agir sur la plus
    probable."""

    candidats: tuple[CommandeInterpretee, ...]
    texte_origine: str = ""
    latence_ms: int = 0


# ─────────────────────────────────────────────────────────────────────────────
# Normalisation — accents, casse, apostrophes, traits d'union, espaces
# -----------------------------------------------------------------------------
# La ponctuation N'EST PAS retirée, contrairement à `routeur.normaliser_question` :
# ce module doit lire des VALEURS, et « 8,5 m² » dont on retire la virgule
# devient « 85 m2 ». Une superficie multipliée par dix est exactement le genre
# d'erreur que le CA11 demande d'empêcher — la retirer ici la rendrait
# indétectable en aval.
#
# Le trait d'union, lui, est ramené à une espace : « montre-moi », « qu'est-ce »
# et « est-ce que » sont écrits avec, dictés sans, et les deux doivent se
# comporter à l'identique. Les valeurs qui en portent un (« mi-ombre »,
# « nord-est ») sont reconstruites à la sortie, jamais lues telles quelles.
#
# La table d'index rend chaque caractère normalisé traçable jusqu'à sa position
# d'origine : c'est elle qui permet de rendre « PlancheTomate » avec sa casse,
# ou « carré-sud » avec son trait d'union, alors que la reconnaissance travaille
# en minuscules sans accents.
# ─────────────────────────────────────────────────────────────────────────────
_SEPARATEURS = "'’ʼ`-–—"


def normaliser(texte: str) -> tuple[str, list[int]]:
    """Forme normalisée d'une phrase, et l'index de chaque caractère vers le
    texte d'origine."""
    sortie: list[str] = []
    index: list[int] = []
    espace_en_cours = True  # évite l'espace de tête
    brut = texte or ""
    for position, caractere in enumerate(brut):
        # Un tiret suivi d'un chiffre en tête de mot est un SIGNE MOINS, pas un
        # trait d'union : « la tomate gèle à -2 °C » écrirait sinon +2 °C au
        # référentiel partagé, soit exactement la valeur fausse que le CA11
        # demande d'empêcher.
        if (
            caractere in "-–—"
            and espace_en_cours
            and position + 1 < len(brut)
            and brut[position + 1].isdigit()
        ):
            sortie.append("-")
            index.append(position)
            espace_en_cours = False
            continue
        if caractere in _SEPARATEURS or caractere.isspace():
            if not espace_en_cours:
                sortie.append(" ")
                index.append(position)
                espace_en_cours = True
            continue
        traduit = unidecode(caractere.lower())
        if not traduit:
            continue
        espace_en_cours = False
        for lettre in traduit:
            sortie.append(lettre)
            index.append(position)
    while sortie and sortie[-1] == " ":
        sortie.pop()
        index.pop()
    return "".join(sortie), index


def _fragment_source(texte: str, index: list[int], debut: int, fin: int) -> str:
    """Rend le fragment d'ORIGINE (casse, accents et traits d'union intacts)
    correspondant aux bornes d'un groupe capturé sur la forme normalisée."""
    if debut >= fin or not index:
        return ""
    depart = index[debut]
    arrivee = index[min(fin, len(index)) - 1]
    return texte[depart:arrivee + 1].strip()


# ─────────────────────────────────────────────────────────────────────────────
# Garde 1 (CA2) — vouloir faire n'est pas demander comment faire
# -----------------------------------------------------------------------------
# La liste est volontairement courte et ancrée en tête de phrase. Élargie, elle
# finirait par neutraliser les règles qu'elle protège : « qu'est-ce que j'ai
# fait dernièrement ? » (historique), « avec quoi associer la carotte ? »
# (associations) et « quel temps fait-il ? » (météo) sont bien des commandes,
# et s'ouvrent toutes par un interrogatif.
# ─────────────────────────────────────────────────────────────────────────────
_MOTIF_SAVOIR = re.compile(
    r"\A(?:"
    r"comment\b"
    r"|pourquoi\b"
    r"|c est quoi\b|qu est ce que c est\b"
    r"|a quoi sert\b|a quoi ca sert\b"
    r"|peut on\b|est il possible\b|est ce possible\b|est ce qu on peut\b"
    r"|ou trouve t on\b|ou est ce que je (?:trouve|peux voir)\b"
    r"|explique\b|dis moi comment\b|je ne sais pas comment\b"
    r")"
)

#: Le même garde, mais n'importe où dans la phrase : « dis-moi comment
#: supprimer une parcelle » ne s'ouvre pas par « comment ».
_MOTIF_SAVOIR_INTERNE = re.compile(
    r"\b(?:comment (?:on |je |l on )?(?:fait|faire|s y prend|creer|cree|supprimer|"
    r"supprime|renommer|renomme|modifier|modifie|ajouter|ajoute|noter|note|"
    r"corriger|corrige|declarer|declare|changer|change|activer|active)"
    r"|a quoi sert)\b"
)


def _est_demande_de_savoir(normalise: str) -> bool:
    """[CA2] La phrase demande-t-elle une PROCÉDURE plutôt qu'une exécution ?

    Répondre « voici comment supprimer une parcelle » à quelqu'un qui vient de
    demander qu'on la supprime est la forme la plus agaçante de la non-réponse.
    L'inverse — supprimer la parcelle de quelqu'un qui demandait comment faire —
    est bien pire. D'où un garde testé le premier, et jamais après une règle.
    """
    return bool(_MOTIF_SAVOIR.match(normalise) or _MOTIF_SAVOIR_INTERNE.search(normalise))


# ─────────────────────────────────────────────────────────────────────────────
# Garde 2 — une question n'est pas une déclaration
# -----------------------------------------------------------------------------
# Motif repris d'`llm.routeur._MOTIF_INTERROGATIF` dans son esprit, restreint
# ici aux ouvertures qui ne peuvent pas commencer une commande : « quel temps
# fait-il ? » et « avec quoi associer la carotte ? » en sont, elles, et ne
# doivent surtout pas être bloquées.
# ─────────────────────────────────────────────────────────────────────────────
_MOTIF_INTERROGATIF = re.compile(
    r"\A(?:qu est ce|quest ce|qu est|que |quoi |qui |qu y a t il|"
    r"y a t il|y a t elle|dis moi ce)"
)


def _ouverture_interrogative(normalise: str) -> bool:
    return bool(_MOTIF_INTERROGATIF.match(normalise + " "))


# ─────────────────────────────────────────────────────────────────────────────
# Briques de motifs partagées
# ─────────────────────────────────────────────────────────────────────────────
#: « je veux », « peux-tu », « j'aimerais »… — l'intention, à distinguer de
#: l'impératif (« supprime ») et de l'ellipse (« bilan des tomates »). Les trois
#: formes sont couvertes par le corpus du CA15.
_INTENTION = (
    r"(?:(?:je (?:veux|voudrais|souhaite|souhaiterais|desire)(?: que)?|"
    r"j aimerais(?: que)?|peux tu|pourrais tu|tu peux|il faut(?: que)?|"
    r"merci de|j ai besoin de|je vais|je dois)\s+)?"
)
_ARTICLE = r"(?:(?:la|le|les|l|ma|mon|mes|une|un|des|du|de la|de)\s+)?"
_MONTRER = (
    r"(?:(?:montre|montrer|affiche|afficher|donne|donner|voir|ouvre|ouvrir|"
    r"lis|lire|consulte|consulter|liste|lister|listes|enumere|enumerer)"
    r"(?:\s+moi)?\s+)?"
)
#: Le verbe de correction en tête — « corrige le délai de retour… ». Facultatif :
#: la même phrase se dit aussi bien sans lui (« délai de retour des solanacées :
#: 4 ans »), et les deux formes doivent se comporter à l'identique.
_CORRIGER = (
    r"(?:(?:corrige|corriger|change|changer|mets|mettre|fixe|fixer|"
    r"passe|passer|modifie|modifier|regle|regler)\s+)?"
)
_NOMBRE = r"(?P<{}>-?\d+(?:[.,]\d+)?)"

#: Mots qui ne peuvent pas être un nom de parcelle, de culture ou de potager :
#: leur présence signale qu'on a capturé trop large.
_MOTS_NON_NOM: frozenset[str] = frozenset({
    "", "la", "le", "les", "l", "de", "du", "des", "un", "une", "ma", "mon",
    "mes", "ce", "cette", "cet", "moi", "ici", "ca", "cela", "au", "aux", "a",
    "en", "vers", "sur", "dans", "pour", "d", "potager", "jardin", "parcelle",
    "parcelles", "culture", "cultures", "saison", "annee", "tout", "toutes",
    "tous", "famille",
})

_PREPOSITIONS_DE_TETE = re.compile(
    r"\A\s*(?:d|de|du|de la|des|la|le|les|l|ma|mon|mes|un|une|au|aux|a|en|"
    r"vers|sur|pour|dans)\b\s*",
    re.IGNORECASE,
)


def _nettoyer_nom(fragment: str) -> str:
    """Retire les articles et prépositions de tête et la ponctuation de bord.

    N'applique aucune autre normalisation : celle des noms de parcelle
    (`utils.parcelles.normalize_parcelle_name`) et celle des cultures
    (`utils.culture_resolve`) sont appliquées par les services appelés, et le
    projet n'en tolère pas une seconde.
    """
    propre = (fragment or "").strip().strip(".,;:!?\"«»()")
    precedent = None
    while propre != precedent:
        precedent = propre
        propre = _PREPOSITIONS_DE_TETE.sub("", propre).strip()
    return re.sub(r"\s+", " ", propre).strip()


def _nom_plausible(fragment: str) -> bool:
    normalise, _ = normaliser(fragment or "")
    return bool(normalise) and normalise not in _MOTS_NON_NOM and len(normalise) <= 60


# ─────────────────────────────────────────────────────────────────────────────
# Dates — celles d'US-094, jamais une seconde règle
# ─────────────────────────────────────────────────────────────────────────────
def _extraire_date(fragment: str) -> tuple[Optional[str], str]:
    """Résout un éventuel ancrage temporel et rend la phrase privée de celui-ci.

    Réutilise `utils.date_utils.resoudre_ancrage_temporel` — la grammaire de
    dates du projet, sans exception : « le plan au 1er mai » se date là où
    « planté le 1er mai » se date déjà. L'expression reconnue est retirée par
    RECHERCHE et non par ses bornes : `date_utils` normalise à sa façon (les
    traits d'union y survivent), et deux tables d'index différentes ne se
    superposent pas.
    """
    from utils.date_utils import ANCRAGE_RESOLU, resoudre_ancrage_temporel

    ancrage = resoudre_ancrage_temporel(fragment)
    if ancrage.statut != ANCRAGE_RESOLU or not ancrage.date_iso:
        return None, fragment

    normalise, index = normaliser(fragment)
    expression, _ = normaliser(ancrage.expression or "")
    debut = normalise.find(expression) if expression else -1
    if debut < 0:
        return ancrage.date_iso, fragment
    avant = _fragment_source(fragment, index, 0, debut)
    apres = _fragment_source(fragment, index, debut + len(expression), len(index))
    return ancrage.date_iso, f"{avant} {apres}".strip()


# ─────────────────────────────────────────────────────────────────────────────
# Le tableau des règles
# -----------------------------------------------------------------------------
# Chaque règle porte un nom : il est journalisé, et c'est lui qui dit quelle
# formulation enrichir quand une phrase n'est pas comprise (CA18). Une règle
# rend un dictionnaire {nom d'argument: valeur} — jamais une liste positionnelle,
# pour qu'un argument facultatif omis ne décale pas la lecture des suivants.
# ─────────────────────────────────────────────────────────────────────────────
Valeurs = dict[str, str]


@dataclass(frozen=True)
class Regle:
    nom: str
    motif: "re.Pattern[str]"
    commande: str
    sous_commande: Optional[str]
    #: Construit les valeurs à partir des groupes capturés. Retourne `None` pour
    #: renoncer — une règle a le droit de refuser ce qu'elle vient de
    #: reconnaître (un nom vide, une valeur hors vocabulaire).
    construire: Callable[[dict[str, str]], Optional[Valeurs]]
    #: [Garde 2] La règle lit une phrase DÉCLARATIVE pour écrire une valeur.
    #: Elle est refusée sur une ouverture interrogative.
    declarative: bool = False


_REGLES: list[Regle] = []


def _regle(nom, motif, commande, sous_commande, declarative=False):
    """Déclare une règle — décorateur, pour que le motif et sa construction de
    valeurs restent côte à côte et ne puissent pas se désynchroniser."""

    def _decorateur(construire):
        _REGLES.append(
            Regle(nom, re.compile(motif), commande, sous_commande, construire, declarative)
        )
        return construire

    return _decorateur


# ── Parcelles ────────────────────────────────────────────────────────────────
_MOTIF_SUPERFICIE = re.compile(r"(-?\d+(?:[.,]\d+)?)\s*(?:m2|m\b|metres? carres?)")
_MOTIF_EXPOSITION_PARCELLE = re.compile(
    r"(?:exposition|exposee?|expose|orientee?|oriente|plein|en|au)\s+"
    r"(nord est|nord ouest|sud est|sud ouest|nord|sud|est|ouest|mi ombre|ombre|soleil)\b"
)


def _decouper_details_parcelle(
    tail: str,
) -> tuple[str, Optional[str], Optional[str], bool]:
    """Sépare « PlancheTomate, plein sud, 12 m² » en nom, exposition, superficie.

    La virgule est le séparateur naturel de la dictée ; en son absence, la
    superficie et l'exposition sont retirées du nom par leurs motifs propres.
    """
    # La virgule sépare les annotations (« PlancheTomate, plein sud, 12 m² »),
    # SAUF entre deux chiffres, où elle est décimale : découper « 8,5 m² » en
    # deux segments faisait lire une superficie de 5 m² au lieu de 8,5 — une
    # valeur fausse écrite sans que rien ne le signale, exactement ce que le
    # CA11 demande d'empêcher.
    segments = [s.strip() for s in re.split(r"(?<!\d),|,(?!\d)", tail or "")]
    nom = segments[0]
    exposition: Optional[str] = None
    superficie: Optional[str] = None

    for segment in segments[1:] + [nom]:
        normalise, _ = normaliser(segment)
        if superficie is None:
            trouve = _MOTIF_SUPERFICIE.search(normalise)
            if trouve:
                superficie = trouve.group(1).replace(",", ".")
        if exposition is None:
            trouve = _MOTIF_EXPOSITION_PARCELLE.search(normalise)
            if trouve:
                exposition = trouve.group(1).replace(" ", "-")

    # Le nom est ce qui PRÉCÈDE la première annotation.
    #
    # ⚠️ Ne jamais reconstruire le nom en retirant les annotations par
    # substitution : la longueur de la chaîne substituée ne dit plus rien des
    # positions dans la chaîne d'origine, et l'appliquer comme un décalage
    # collait au nom une partie de ce qu'on venait d'en retirer — « crée la
    # parcelle planche tomate sud 12 mètres carrés » donnait le nom « planche
    # tomate sud 12 », relevé en dictée réelle le 08/09/2026. Les BORNES, elles,
    # se lisent sur la chaîne normalisée et se traduisent exactement.
    normalise_nom, index_nom = normaliser(nom)
    bornes = [
        trouve.start()
        for trouve in (
            _MOTIF_SUPERFICIE.search(normalise_nom),
            _MOTIF_EXPOSITION_PARCELLE.search(normalise_nom),
        )
        if trouve is not None
    ]
    ambigu = bool(_DIRECTION_COLLEE_A_UNE_SUPERFICIE.search(f" {normalise_nom}"))
    if bornes:
        nom = _fragment_source(nom, index_nom, 0, min(bornes))
    return _nettoyer_nom(nom), exposition, superficie, ambigu


#: Une direction suivie IMMÉDIATEMENT d'une superficie, dans le même segment :
#: « planche tomate sud 12 m² ». Rien ne dit si « sud » ferme le nom ou annonce
#: l'exposition. Séparée par une virgule (« carré nord, 12 m² ») ou présentée
#: par un mot (« exposée sud »), elle ne pose plus de question.
_DIRECTION_COLLEE_A_UNE_SUPERFICIE = re.compile(
    r"\s(?:nord est|nord ouest|sud est|sud ouest|nord|sud|est|ouest)\s+"
    r"(?=-?\d+(?:[.,]\d+)?\s*(?:m2|m|metres? carres?))"
)


@_regle(
    "parcelle_ajouter",
    _INTENTION
    + r"(?:cree|creer|cre|ajoute|ajouter|rajoute|rajouter|nouvelle|declare|declarer|"
    + r"creation de|creation d)\s+"
    + r"(?:moi\s+)?" + _ARTICLE + r"(?:nouvelle\s+)?parcelle\s+"
    + r"(?:nommee\s+|appelee\s+|qui s appelle\s+|du nom de\s+)?"
    + r"(?P<tail>.+)",
    "parcelle",
    "ajouter",
)
def _construire_parcelle_ajouter(groupes):
    nom, exposition, superficie, ambigu = _decouper_details_parcelle(groupes["tail"])
    if not _nom_plausible(nom):
        return None
    # « planche tomate sud 12 m² » : « sud » est-il la fin du nom, ou
    # l'exposition ? « Planche Sud » est un nom de parcelle parfaitement
    # courant, et trancher au jugé écrirait un nom mutilé une fois sur deux.
    # La règle RENONCE donc, et laisse le modèle lire la phrase — c'est
    # exactement le partage prévu par la cascade : les règles traitent ce qui
    # est sans doute, le repli traite l'ambigu (CA3, CA4). Sans superficie
    # derrière, il n'y a pas d'ambiguïté : la direction fait partie du nom.
    if ambigu and exposition is None:
        log.info(
            "🎛️  INTERPRETEUR   : « %s » — nom ou exposition ? règle abandonnée, "
            "repli modèle", nom,
        )
        return None
    valeurs = {"nom": nom}
    if exposition:
        valeurs["exposition"] = exposition
    if superficie:
        valeurs["superficie"] = superficie
    return valeurs


@_regle(
    "parcelle_renommer",
    _INTENTION
    + r"(?:renomme|renommer|rebaptise|rebaptiser|change le nom de|changer le nom de|"
    + r"changement de nom de|changement de nom d)\s+"
    + _ARTICLE + r"(?:parcelle\s+)?(?P<ancien>.+?)\s+en\s+" + _ARTICLE
    + r"(?:parcelle\s+)?(?P<nouveau>.+)",
    "parcelle",
    "renommer",
)
def _construire_parcelle_renommer(groupes):
    ancien = _nettoyer_nom(groupes["ancien"])
    nouveau = _nettoyer_nom(groupes["nouveau"])
    if not (_nom_plausible(ancien) and _nom_plausible(nouveau)):
        return None
    return {"ancien": ancien, "nouveau": nouveau}


@_regle(
    "parcelle_supprimer",
    _INTENTION
    + r"(?:supprime|supprimer|efface|effacer|retire|retirer|enleve|enlever|detruis|"
    + r"detruire|suppression de|suppression d)\s+"
    + _ARTICLE + r"parcelle\s+(?P<nom>.+)",
    "parcelle",
    "supprimer",
)
def _construire_parcelle_supprimer(groupes):
    nom = _nettoyer_nom(groupes["nom"])
    if not _nom_plausible(nom):
        return None
    return {"nom": nom}


@_regle(
    "parcelle_pepiniere",
    r"\A" + _INTENTION + _ARTICLE + r"(?:parcelle\s+)?(?P<nom>.+?)\s+"
    r"(?:est|devient|sert de|sert d|passe en|passe comme)\s+"
    + _ARTICLE + r"(?:nouvelle\s+)?pepiniere\b",
    "parcelle",
    "modifier",
    declarative=True,
)
def _construire_parcelle_pepiniere(groupes):
    nom = _nettoyer_nom(groupes["nom"])
    if not _nom_plausible(nom):
        return None
    return {"nom": nom, "modification": "pepiniere=true"}


@_regle(
    "parcelle_pepiniere_imperatif",
    r"\A" + _INTENTION
    + r"(?:mets|mettre|passe|passer|declare|declarer|transforme|transformer)\s+"
    + _ARTICLE + r"(?:parcelle\s+)?(?P<nom>.+?)\s+(?:en|comme)\s+"
    + _ARTICLE + r"pepiniere\b",
    "parcelle",
    "modifier",
)
def _construire_parcelle_pepiniere_imperatif(groupes):
    # L'impératif est verbe-en-tête (« mets la serre en pépinière »), la
    # déclaration est nom-en-tête (« la serre est une pépinière ») : deux
    # ordres de mots, deux motifs, une seule construction d'arguments.
    return _construire_parcelle_pepiniere(groupes)


@_regle(
    "parcelle_superficie",
    _INTENTION
    + r"(?:la\s+|le\s+)?(?:superficie|surface|taille)\s+(?:de\s+)?" + _ARTICLE
    + r"(?:parcelle\s+)?(?P<nom>.+?)\s+(?:est|fait|passe a|:|=)\s*(?:de\s+|a\s+)?"
    + _NOMBRE.format("valeur") + r"\s*(?:m2|m\b|metres? carres?)",
    "parcelle",
    "modifier",
    declarative=True,
)
def _construire_parcelle_superficie(groupes):
    nom = _nettoyer_nom(groupes["nom"])
    if not _nom_plausible(nom):
        return None
    return {"nom": nom, "modification": f"superficie={groupes['valeur'].replace(',', '.')}"}


@_regle(
    "parcelle_superficie_verbe",
    r"\A" + _INTENTION + _ARTICLE + r"(?:parcelle\s+)?(?P<nom>.+?)\s+"
    r"(?:fait|fasse|mesure)\s+" + _NOMBRE.format("valeur")
    + r"\s*(?:m2|m\b|metres? carres?)",
    "parcelle",
    "modifier",
    declarative=True,
)
def _construire_parcelle_superficie_verbe(groupes):
    return _construire_parcelle_superficie(groupes)


@_regle(
    "parcelle_exposition",
    _INTENTION
    + r"(?:l\s+)?exposition\s+(?:de\s+)?" + _ARTICLE + r"(?:parcelle\s+)?"
    + r"(?P<nom>.+?)\s+(?:est|passe a|devient|:|=)\s*(?:plein\s+|au\s+|le\s+)?"
    + r"(?P<valeur>nord est|nord ouest|sud est|sud ouest|nord|sud|est|ouest|mi ombre|ombre)\b",
    "parcelle",
    "modifier",
    declarative=True,
)
def _construire_parcelle_exposition(groupes):
    nom = _nettoyer_nom(groupes["nom"])
    if not _nom_plausible(nom):
        return None
    return {"nom": nom, "modification": f"exposition={groupes['valeur'].replace(' ', '-')}"}


@_regle(
    "parcelle_lister",
    r"\A" + _INTENTION + _MONTRER + _ARTICLE + r"(?:liste des\s+)?parcelles\s*\Z",
    "parcelle",
    "lister",
)
def _construire_parcelle_lister(groupes):
    return {}


# ── Consultation ─────────────────────────────────────────────────────────────
_MOTS_CIBLE_GENERIQUE: frozenset[str] = frozenset({
    "potager", "jardin", "occupation", "general", "generale", "complet",
    "parcelles", "cultures", "aujourd hui", "actuel", "saison", "annee",
    "annee ecoulee", "tout", "an", "moi",
})


def _cible_ou_rien(fragment: str) -> Optional[str]:
    """Un nom de parcelle ou de culture cité en fin de phrase — ou rien.

    « bilan de la saison » ne nomme aucune culture, « plan du potager » aucune
    parcelle : ces mots génériques sont écartés plutôt que passés en argument,
    où ils produiraient un filtre vide et une réponse fausse d'apparence juste.
    """
    cible = _nettoyer_nom(re.sub(r"\b(?:parcelle|culture|cultures)\b", " ", fragment or ""))
    normalise, _ = normaliser(cible)
    if not cible or normalise in _MOTS_CIBLE_GENERIQUE or not _nom_plausible(cible):
        return None
    return cible


@_regle(
    "plan",
    r"\A" + _INTENTION + _MONTRER + _ARTICLE + r"plan\b(?P<tail>.*)",
    "plan",
    None,
)
def _construire_plan(groupes):
    date_iso, tail = _extraire_date(groupes.get("tail") or "")
    valeurs: Valeurs = {}
    cible = _cible_ou_rien(tail)
    if cible:
        valeurs["parcelle"] = cible
    if date_iso:
        valeurs["date"] = date_iso
    return valeurs


@_regle(
    "stats",
    r"\A" + _INTENTION + _MONTRER + _ARTICLE
    + r"(?:stats|statistiques|bilan|bilans|chiffres)\b(?P<tail>.*)",
    "stats",
    None,
)
def _construire_stats(groupes):
    date_iso, tail = _extraire_date(groupes.get("tail") or "")
    valeurs: Valeurs = {}
    cible = _cible_ou_rien(re.sub(r"\b(?:ma|mes)\b", " ", tail))
    if cible:
        valeurs["culture"] = cible
    if date_iso:
        valeurs["date"] = date_iso
    return valeurs


@_regle(
    "historique",
    r"\A" + _INTENTION + _MONTRER + _ARTICLE
    + r"(?:historique\b(?!\s+(?:de|des|du|d)\b)"
    r"|derniers evenements\b|dernieres saisies\b|derniers gestes\b"
    r"|qu est ce que j ai fait\b|ce que j ai fait\b|qu ai je fait\b)",
    "historique",
    None,
)
def _construire_historique(groupes):
    return {}


@_regle(
    "meteo",
    r"\A" + _INTENTION + _MONTRER + _ARTICLE
    + r"(?:meteo\b|previsions?\b|quel temps\b|le temps qu il fait\b|"
    r"il va (?:pleuvoir|geler)\b|va t il pleuvoir\b)",
    "meteo",
    None,
)
def _construire_meteo(groupes):
    return {}


@_regle(
    "fiche",
    r"\A" + _INTENTION + _MONTRER + _ARTICLE + r"fiche\s+"
    r"(?:(?:de|du|de la|des|sur|pour)\s+)?" + _ARTICLE + r"(?P<culture>.+)",
    "fiche",
    None,
)
def _construire_fiche(groupes):
    culture = _nettoyer_nom(groupes["culture"])
    if not _nom_plausible(culture):
        return None
    return {"culture": culture}


@_regle(
    "rotation_question",
    r"\A(?:est ce que\s+)?(?:je peux|puis je|j ai le droit de|c est possible de)\s+"
    r"(?:y\s+)?(?:planter|semer|mettre|cultiver|repiquer)\s+" + _ARTICLE
    + r"(?P<culture>.+?)\s+(?:sur|dans|en|a)\s+" + _ARTICLE
    + r"(?:parcelle\s+)?(?P<parcelle>.+)",
    "rotation",
    None,
)
def _construire_rotation_question(groupes):
    culture = _nettoyer_nom(groupes["culture"])
    parcelle = _nettoyer_nom(groupes["parcelle"])
    if not (_nom_plausible(culture) and _nom_plausible(parcelle)):
        return None
    return {"parcelle": parcelle, "culture": culture}


@_regle(
    "rotation_explicite",
    r"\A" + _INTENTION
    + r"(?:(?:verifie|verifier|controle|controler|calcule|calculer)\s+)?" + _ARTICLE
    + r"rotation\s+(?:de\s+|pour\s+|d\s+)?" + _ARTICLE
    + r"(?P<culture>.+?)\s+(?:sur|dans|en)\s+" + _ARTICLE
    + r"(?:parcelle\s+)?(?P<parcelle>.+)",
    "rotation",
    None,
)
def _construire_rotation_explicite(groupes):
    return _construire_rotation_question(groupes)


# ── Associations ─────────────────────────────────────────────────────────────
@_regle(
    "association_lister",
    r"\A" + _INTENTION + _MONTRER
    + r"(?:avec quoi\s+(?:associer|planter|semer|marier)|"
    r"(?:quelles?|quels?)\s+associations?(?:\s+pour)?|"
    r"(?:les\s+)?associations?\s+(?:de|du|de la|pour)|"
    r"(?:qu est ce qui|qui)\s+(?:s associe|va) (?:bien )?avec)\s+"
    + _ARTICLE + r"(?P<culture>.+)",
    "association",
    "lister",
)
def _construire_association_lister(groupes):
    culture = _nettoyer_nom(groupes["culture"])
    if not _nom_plausible(culture):
        return None
    return {"culture": culture}


@_regle(
    "association_saisir",
    r"\A" + _INTENTION
    + r"(?:(?:note|noter|saisis|saisir|enregistre|enregistrer|ajoute|ajouter|"
    r"declare|declarer)\s+)?" + _ARTICLE
    + r"association\s+entre\s+" + _ARTICLE
    + r"(?P<culture_a>.+?)\s+et\s+" + _ARTICLE + r"(?P<culture_b>.+)",
    "association",
    "saisir",
)
def _construire_association_saisir(groupes):
    culture_a = _nettoyer_nom(groupes["culture_a"])
    culture_b = _nettoyer_nom(groupes["culture_b"])
    if not (_nom_plausible(culture_a) and _nom_plausible(culture_b)):
        return None
    # La nature, le niveau de preuve et le motif ne se devinent pas : ils sont
    # demandés par la complétion guidée (CA13), boutons à l'appui pour les deux
    # vocabulaires fermés.
    return {"culture_a": culture_a, "culture_b": culture_b}


# ── Fiche de culture partagée ────────────────────────────────────────────────
@_regle(
    "culture_attributs",
    r"\A" + _INTENTION + _MONTRER + _ARTICLE + r"attributs?\s+"
    r"(?:(?:de|du|de la|des|pour)\s+)?" + _ARTICLE + r"(?P<culture>.+)",
    "culture",
    "attributs",
)
def _construire_culture_attributs(groupes):
    culture = _nettoyer_nom(groupes["culture"])
    if not _nom_plausible(culture):
        return None
    return {"culture": culture}


#: Une famille botanique se reconnaît à son suffixe : l'exiger évite que « la
#: tomate est un fruit » soit pris pour une correction de famille.
_SUFFIXE_FAMILLE = r"[a-z]+(?:acee|acees|aceae|iacee|iacees)"


@_regle(
    "culture_famille_inverse",
    r"\A" + _INTENTION + _CORRIGER
    + r"(?:la\s+)?famille\s+(?:de\s+|du\s+|de la\s+|d\s+)?" + _ARTICLE
    + r"(?P<culture>.+?)\s+(?:est|soit|:|=|en)\s*" + _ARTICLE
    + r"(?P<famille>" + _SUFFIXE_FAMILLE + r")\b",
    "culture",
    "famille",
    declarative=True,
)
def _construire_culture_famille_inverse(groupes):
    culture = _nettoyer_nom(groupes["culture"])
    famille = _nettoyer_nom(groupes["famille"])
    if not (_nom_plausible(culture) and _nom_plausible(famille)):
        return None
    return {"culture": culture, "famille": famille}


@_regle(
    "culture_famille",
    r"\A" + _INTENTION + _ARTICLE + r"(?P<culture>.+?)\s+"
    r"(?:est|soit|fait partie|appartient|est de|se range)\s+"
    r"(?:une |un |de la famille des |a la famille des |aux |dans les |des )?"
    r"(?P<famille>" + _SUFFIXE_FAMILLE + r")\b",
    "culture",
    "famille",
    declarative=True,
)
def _construire_culture_famille(groupes):
    return _construire_culture_famille_inverse(groupes)


@_regle(
    "culture_delai_retour",
    r"\A" + _INTENTION + _CORRIGER + r"(?:le\s+)?delai(?: de retour)?\s+"
    r"(?:(?:de|des|de la|du|pour|pour les|pour la)\s+)?" + _ARTICLE
    + r"(?P<famille>" + _SUFFIXE_FAMILLE + r")\s*"
    r"(?:est|soit|:|=|de|a)?\s*(?:de\s+)?" + _NOMBRE.format("annees")
    + r"\s*(?:ans?|annees?)?",
    "culture",
    "delai_retour",
    declarative=True,
)
def _construire_culture_delai_retour(groupes):
    famille = _nettoyer_nom(groupes["famille"])
    if not _nom_plausible(famille):
        return None
    return {"famille": famille, "annees": groupes["annees"].replace(",", ".")}


_VALEURS_EXPOSITION: dict[str, str] = {
    "plein soleil": "plein soleil",
    "soleil": "plein soleil",
    "mi ombre": "mi-ombre",
    "demi ombre": "mi-ombre",
    "ombre": "ombre",
}


@_regle(
    "culture_exposition",
    r"\A" + _INTENTION + _ARTICLE + r"(?P<culture>.+?)\s+"
    r"(?:veut|aime|prefere|demande|a besoin|se cultive|se plante|pousse|"
    r"se met|doit etre|est|soit)\s+"
    r"(?:de\s+|du\s+|d\s+|de l\s+|en\s+|a\s+|au\s+|sous\s+|dans\s+|l\s+|la\s+|"
    r"exposition\s+|cultivee?\s+|plantee?\s+|mise?\s+)*"
    r"(?P<valeur>plein soleil|mi ombre|demi ombre|ombre|soleil)\b",
    "culture",
    "exposition",
    declarative=True,
)
def _construire_culture_exposition(groupes):
    culture = _nettoyer_nom(groupes["culture"])
    valeur = _VALEURS_EXPOSITION.get((groupes["valeur"] or "").strip())
    if not _nom_plausible(culture) or valeur is None:
        return None
    return {"culture": culture, "valeur": valeur}


@_regle(
    "culture_exposition_imperatif",
    r"\A" + _INTENTION
    + r"(?:mets|mettre|passe|passer|cultive|cultiver|plante|planter|"
    r"corrige|corriger|change|changer)\s+"
    + _ARTICLE + r"(?P<culture>.+?)\s+(?:en|a|au|sous|vers)\s+" + _ARTICLE
    + r"(?P<valeur>plein soleil|mi ombre|demi ombre|ombre|soleil)\b",
    "culture",
    "exposition",
)
def _construire_culture_exposition_imperatif(groupes):
    return _construire_culture_exposition(groupes)


@_regle(
    "culture_famille_imperatif",
    r"\A" + _INTENTION
    + r"(?:corrige|corriger|change|changer|mets|mettre|range|ranger|classe|classer)\s+"
    + _ARTICLE + r"(?:famille\s+(?:de\s+|du\s+|de la\s+|d\s+)?)?" + _ARTICLE
    + r"(?P<culture>.+?)\s+(?:en|dans les|dans la|parmi les|comme|avec les)\s+"
    + _ARTICLE + r"(?P<famille>" + _SUFFIXE_FAMILLE + r")\b",
    "culture",
    "famille",
)
def _construire_culture_famille_imperatif(groupes):
    return _construire_culture_famille_inverse(groupes)


_VALEURS_EAU: dict[str, str] = {
    "faible": "faible", "moyen": "moyen", "moyenne": "moyen",
    "eleve": "élevé", "elevee": "élevé", "fort": "élevé", "forte": "élevé",
}


@_regle(
    "culture_eau",
    r"\A" + _INTENTION + _CORRIGER + _ARTICLE
    + r"(?:le\s+)?(?:besoin en eau|besoins en eau|arrosage)\s+"
    r"(?:(?:de|du|de la|d|pour)\s+)?" + _ARTICLE
    + r"(?P<culture>.+?)\s+(?:est|soit|:|=|a|en)\s*" + _ARTICLE
    + r"(?P<valeur>faible|moyenne|moyen|elevee|eleve|forte|fort)\b",
    "culture",
    "eau",
    declarative=True,
)
def _construire_culture_eau(groupes):
    culture = _nettoyer_nom(groupes["culture"])
    valeur = _VALEURS_EAU.get((groupes["valeur"] or "").strip())
    if not _nom_plausible(culture) or valeur is None:
        return None
    return {"culture": culture, "valeur": valeur}


@_regle(
    "culture_eau_verbe",
    r"\A" + _INTENTION + _ARTICLE + r"(?P<culture>.+?)\s+a\s+un\s+besoin\s+en\s+eau\s+"
    r"(?P<valeur>faible|moyenne|moyen|elevee|eleve|forte|fort)\b",
    "culture",
    "eau",
    declarative=True,
)
def _construire_culture_eau_verbe(groupes):
    return _construire_culture_eau(groupes)


@_regle(
    "culture_profondeur",
    r"\A" + _INTENTION + _CORRIGER + _ARTICLE + r"profondeur(?: de semis)?\s+"
    r"(?:(?:de|du|de la|d|pour)\s+)?" + _ARTICLE
    + r"(?P<culture>.+?)\s*(?:est|soit|:|=|a)\s*(?:de\s+|a\s+)?"
    + _NOMBRE.format("valeur") + r"\s*(?:cm|centimetres?)?",
    "culture",
    "profondeur",
    declarative=True,
)
def _construire_culture_profondeur(groupes):
    culture = _nettoyer_nom(groupes["culture"])
    if not _nom_plausible(culture):
        return None
    return {"culture": culture, "valeur": groupes["valeur"].replace(",", ".")}


@_regle(
    "culture_profondeur_verbe",
    r"\A" + _INTENTION + _ARTICLE + r"(?P<culture>.+?)\s+"
    r"(?:se seme|se sement|se plante|se plantent|doit etre semee?)\s+"
    r"(?:a|vers)\s+" + _NOMBRE.format("valeur")
    + r"\s*(?:cm|centimetres?)\s*(?:de profondeur)?",
    "culture",
    "profondeur",
    declarative=True,
)
def _construire_culture_profondeur_verbe(groupes):
    return _construire_culture_profondeur(groupes)


@_regle(
    "culture_rusticite",
    r"\A" + _INTENTION + _CORRIGER + _ARTICLE + r"rusticite\s+"
    r"(?:(?:de|du|de la|d|pour)\s+)?" + _ARTICLE
    + r"(?P<culture>.+?)\s*(?:est|soit|:|=|a)\s*(?:de\s+|a\s+)?(?P<moins>moins\s+)?"
    + _NOMBRE.format("valeur") + r"\s*(?:degres?|c\b)?",
    "culture",
    "rusticite",
    declarative=True,
)
def _construire_culture_rusticite(groupes):
    culture = _nettoyer_nom(groupes["culture"])
    if not _nom_plausible(culture):
        return None
    valeur = groupes["valeur"].replace(",", ".")
    # « moins deux degrés » est la forme DICTÉE du signe moins : la
    # transcription vocale n'écrit presque jamais « -2 ».
    if groupes.get("moins") and not valeur.startswith("-"):
        valeur = f"-{valeur}"
    return {"culture": culture, "valeur": valeur}


@_regle(
    "culture_rusticite_verbe",
    r"\A" + _INTENTION + _ARTICLE + r"(?P<culture>.+?)\s+"
    r"(?:gele|resiste|tient|supporte)\s+(?:jusqu a|a|des)\s+(?P<moins>moins\s+)?"
    + _NOMBRE.format("valeur") + r"\s*(?:degres?|c\b)",
    "culture",
    "rusticite",
    declarative=True,
)
def _construire_culture_rusticite_verbe(groupes):
    return _construire_culture_rusticite(groupes)


# ── Bioagresseurs ────────────────────────────────────────────────────────────
def _vocabulaire_de(commande: str, sous_commande: Optional[str], nom_argument: str) -> tuple[str, ...]:
    forme = FORMES_PAR_CLE[(commande, sous_commande)]
    for argument in forme.arguments:
        if argument.nom == nom_argument:
            return argument.vocabulaire
    return ()


@_regle(
    "bioagresseur_declarer",
    r"\A" + _INTENTION
    + r"(?:(?:declare|declarer|ajoute|ajouter|enregistre|enregistrer)\s+)?" + _ARTICLE
    + r"(?:nouveau\s+|nouvelle\s+)?bioagresseur\s*[:,]?\s*" + _ARTICLE
    + r"(?P<nom>.+?)\s*(?:,|:|\s+comme\s+|\s+en tant que\s+|\s+c est\s+|\s+est\s+)\s*"
    + _ARTICLE + r"(?P<categorie>[a-z]+)\b",
    "bioagresseur",
    "declarer",
)
def _construire_bioagresseur_declarer(groupes):
    nom = _nettoyer_nom(groupes["nom"])
    categorie = (groupes["categorie"] or "").strip().lower()
    if not _nom_plausible(nom) or categorie not in _vocabulaire_de("bioagresseur", "declarer", "categorie"):
        return None
    return {"categorie": categorie, "nom": nom}


_FREQUENCES_DITES: dict[str, str] = {
    "souvent": "courant", "couramment": "courant", "frequemment": "courant",
    "occasionnellement": "occasionnel", "parfois": "occasionnel",
    "rarement": "rare",
}


@_regle(
    "bioagresseur_rattacher",
    r"\A" + _INTENTION + _ARTICLE + r"(?P<bioagresseur>.+?)\s+"
    r"(?:attaque|touche|s attaque a|affecte)\s+"
    r"(?:(?P<frequence>souvent|couramment|frequemment|occasionnellement|parfois|rarement)\s+)?"
    + _ARTICLE + r"(?P<culture>.+)",
    "bioagresseur",
    "rattacher",
    declarative=True,
)
def _construire_bioagresseur_rattacher(groupes):
    bioagresseur = _nettoyer_nom(groupes["bioagresseur"])
    culture = _nettoyer_nom(groupes["culture"])
    if not (_nom_plausible(bioagresseur) and _nom_plausible(culture)):
        return None
    valeurs = {"culture": culture, "bioagresseur": bioagresseur}
    frequence = _FREQUENCES_DITES.get((groupes.get("frequence") or "").strip())
    if frequence:
        valeurs["frequence"] = frequence
    # Sans mot de fréquence explicite dans la phrase, elle est DEMANDÉE, jamais
    # présumée « courant » (CA13) : c'est une valeur de vocabulaire fermé, et
    # aucun synonyme approchant ne doit pouvoir la produire.
    return valeurs


@_regle(
    "bioagresseur_rattacher_imperatif",
    r"\A" + _INTENTION
    + r"(?:rattache|rattacher|relie|relier|associe|associer)\s+" + _ARTICLE
    + r"(?P<bioagresseur>.+?)\s+(?:a|au|a la|aux|sur|avec)\s+"
    + _ARTICLE + r"(?:culture\s+)?(?P<culture>.+)",
    "bioagresseur",
    "rattacher",
)
def _construire_bioagresseur_rattacher_imperatif(groupes):
    # Aucune fréquence n'est présumée : le motif n'en capture pas, elle sera
    # demandée en boutons (CA13). Présumer « courant » écrirait au potager une
    # information que personne n'a dite.
    return _construire_bioagresseur_rattacher(groupes)


@_regle(
    "bioagresseur_orphelins",
    r"\A" + _INTENTION + _MONTRER
    + r"(?:(?:quels?|quelles?)\s+)?" + _ARTICLE
    + r"bioagresseurs?\s+(?:ne sont|n est|sans culture|orphelins?|"
    r"rattaches? a aucune culture)",
    "bioagresseur",
    "orphelins",
)
def _construire_bioagresseur_orphelins(groupes):
    return {}


# ── Potager, parcours guidés, confort ────────────────────────────────────────
@_regle(
    "potager_changer",
    r"\A" + _INTENTION
    + r"(?:passe|passer|bascule|basculer|change|changer|va|aller|travaille|travailler)\s+"
    r"(?:sur|vers|a|au|dans|de)\s+" + _ARTICLE + r"potager\s+"
    r"(?:(?:de|du|de la|d|nomme|appele)\s+)?" + _ARTICLE + r"(?P<nom>.+)",
    "potager",
    None,
)
def _construire_potager_changer(groupes):
    nom = _nettoyer_nom(groupes["nom"])
    return {"nom": nom} if _nom_plausible(nom) else {}


@_regle(
    "potager_lister",
    r"\A" + _INTENTION
    + r"(?:(?:change|changer|choisis|choisir|selectionne|selectionner)\s+)?"
    r"(?:de\s+)?potager\s*\Z",
    "potager",
    None,
)
def _construire_potager_lister(groupes):
    return {}


@_regle(
    "note",
    r"\A" + _INTENTION
    # Le mot « nouvelle » est EXIGÉ dans la forme sans verbe : sans lui,
    # « observation : pucerons sur fèves » — une saisie que `/help` donne en
    # exemple — serait détournée vers le parcours guidé au lieu d'être
    # enregistrée comme le geste qu'elle est.
    + r"(?:(?:note|noter|prendre|prends|saisir|saisis|ajouter|ajoute|faire|fais)\s+"
    + _ARTICLE + r"(?:nouvelle\s+)?|nouvelle\s+)(?:note|observation|remarque)\b",
    "note",
    None,
)
def _construire_note(groupes):
    return {}


@_regle(
    "corriger",
    r"\A" + _INTENTION
    + r"(?:je me suis trompe|je me suis plante|j ai fait une erreur|"
    r"il y a une erreur|c est faux|corriger (?:une|ma|mon|un)\b|"
    r"corrige (?:une|ma|mon|un)\b|je veux corriger|je voudrais corriger)",
    "corriger",
    None,
)
def _construire_corriger(groupes):
    return {}


@_regle(
    "vendre",
    r"\A" + _INTENTION
    + r"(?:vendre|mettre en vente|proposer a la vente|vente de|vente d)\s+" + _ARTICLE
    + r"(?:plants?|godets?)\b(?P<tail>.*)",
    "vendre",
    None,
)
def _construire_vendre(groupes):
    # Une vente AVEC quantité reste un geste du référentiel (« j'ai vendu 6
    # plants de tomate ») : deux chemins vers la même écriture seraient une
    # divergence en germe. La règle ne se déclenche que sur l'infinitif, donc
    # sur la forme sans quantité, celle qui ouvre le parcours guidé.
    culture = _nettoyer_nom(groupes.get("tail") or "")
    return {"culture": culture} if _nom_plausible(culture) else {}


@_regle(
    "tts_on",
    r"\A" + _INTENTION
    + r"(?:lis moi|lire|active|activer|remets|remettre|mets|mettre)\s+"
    r"(?:moi\s+)?" + _ARTICLE
    + r"(?:reponses?|lecture vocale|voix|synthese vocale|vocal|audio)\b",
    "tts_on",
    None,
)
def _construire_tts_on(groupes):
    return {}


@_regle(
    "tts_off",
    r"\A" + _INTENTION
    + r"(?:coupe|couper|desactive|desactiver|arrete|arreter|stoppe|stopper|"
    r"ne (?:me )?(?:lis|parle) plus)\s+"
    r"(?:de\s+)?(?:moi\s+)?" + _ARTICLE
    + r"(?:reponses?|lecture vocale|voix|synthese vocale|vocal|audio|parler)\b",
    "tts_off",
    None,
)
def _construire_tts_off(groupes):
    return {}


@_regle(
    "tts_etat",
    r"\A(?:est ce que\s+|dis moi si\s+|sais tu si\s+|"
    r"je (?:veux|voudrais) savoir si\s+)?" + _ARTICLE
    + r"(?:lecture vocale|voix|synthese vocale|vocal)\s+"
    r"(?:est|est elle|est il)\s+(?:activee?|allumee?|en marche)",
    "tts",
    None,
)
def _construire_tts_etat(groupes):
    return {}


@_regle(
    "help",
    r"\A" + _INTENTION
    + r"(?:j ai\s+)?(?:aide|a l aide|help|besoin d aide|au secours)\b"
    r"(?:\s+(?:sur|pour|concernant|a propos de|avec)\s+" + _ARTICLE
    + r"(?P<domaine>.+))?\s*\Z",
    "help",
    None,
)
def _construire_help(groupes):
    domaine = _nettoyer_nom(groupes.get("domaine") or "")
    return {"domaine": domaine} if _nom_plausible(domaine) else {}


# ─────────────────────────────────────────────────────────────────────────────
# Reconnaissance par règles — zéro jeton (CA3)
# ─────────────────────────────────────────────────────────────────────────────
#: Les groupes dont la valeur est une DONNÉE validée (chiffre, valeur d'un
#: vocabulaire fermé) sont relus sur la forme normalisée : c'est elle que le
#: motif a validée. Les autres sont relus sur le texte d'origine, casse et
#: accents intacts.
_GROUPES_NORMALISES: frozenset[str] = frozenset({
    "valeur", "annees", "categorie", "frequence",
})


def _construire_commande(
    forme: FormeCommande,
    valeurs: Valeurs,
    origine: str,
    confiance: float,
    texte: str,
    regle: Optional[str] = None,
) -> CommandeInterpretee:
    manquants = tuple(
        argument for argument in forme.arguments
        if argument.obligatoire and not valeurs.get(argument.nom)
    )
    return CommandeInterpretee(
        commande=forme.commande,
        sous_commande=forme.sous_commande,
        forme=forme,
        valeurs=valeurs,
        origine=origine,
        confiance=confiance,
        regle=regle,
        texte_origine=texte,
        manquants=manquants,
    )


def _appliquer_regle(
    regle: Regle, texte: str, normalise: str, index: list[int]
) -> Optional[CommandeInterpretee]:
    if regle.declarative and _ouverture_interrogative(normalise):
        return None
    trouve = regle.motif.search(normalise)
    if trouve is None:
        return None

    groupes: dict[str, str] = {}
    for nom, valeur in (trouve.groupdict() or {}).items():
        if valeur is None:
            groupes[nom] = ""
        elif nom in _GROUPES_NORMALISES:
            groupes[nom] = valeur
        else:
            debut, fin = trouve.span(nom)
            groupes[nom] = _fragment_source(texte, index, debut, fin) if debut >= 0 else valeur

    valeurs = regle.construire(groupes)
    if valeurs is None:
        return None
    forme = FORMES_PAR_CLE.get((regle.commande, regle.sous_commande))
    if forme is None:  # pragma: no cover — le test de parité l'interdit
        log.error(
            "🎛️  INTERPRETEUR   : la règle %r vise /%s %s, absente du catalogue",
            regle.nom, regle.commande, regle.sous_commande,
        )
        return None
    return _construire_commande(forme, valeurs, ORIGINE_REGLE, 1.0, texte, regle.nom)


def reconnaitre_par_regles(texte: str) -> "CommandeInterpretee | Ambiguite | None":
    """[CA1, CA3] Reconnaissance déterministe — aucun appel modèle, aucun jeton.

    Publique et sans effet de bord : `bot.handle_text` l'appelle avant les
    raccourcis par mots-clés hérités, pour savoir si la phrase désigne un objet
    de l'application (« supprimer LA PARCELLE nord » n'est pas « annuler ma
    dernière saisie »), et n'agit dessus qu'à sa place dans l'ordre des flux.
    """
    brut = (texte or "").strip()
    if not brut or brut.startswith("/"):
        return None
    normalise, index = normaliser(brut)
    if not normalise or _est_demande_de_savoir(normalise):
        return None

    trouvees: list[CommandeInterpretee] = []
    cibles: set[tuple[str, Optional[str]]] = set()
    for regle in _REGLES:
        candidate = _appliquer_regle(regle, brut, normalise, index)
        if candidate is None or candidate.forme.cle in cibles:
            continue
        cibles.add(candidate.forme.cle)
        trouvees.append(candidate)

    if not trouvees:
        return None
    if len(trouvees) == 1:
        return trouvees[0]
    # [CA12] Deux commandes distinctes reconnues dans la même phrase : le doute
    # ne fait jamais agir. La précision est demandée, la plus probable n'est pas
    # exécutée.
    return Ambiguite(candidats=tuple(trouvees), texte_origine=brut)


# ─────────────────────────────────────────────────────────────────────────────
# Repli modèle — sous contrainte fermée (CA4)
# -----------------------------------------------------------------------------
# Le prompt fixe est construit depuis le catalogue : une commande ajoutée à
# `FORMES_DICTABLES` y entre sans qu'on y touche, et il est impossible d'y
# décrire une commande qui n'existe pas.
# ─────────────────────────────────────────────────────────────────────────────
def _decrire_catalogue() -> str:
    lignes: list[str] = []
    for forme in sorted(FORMES_PAR_CLE.values(), key=lambda f: (f.commande, f.sous_commande or "")):
        nom = f"{forme.commande} {forme.sous_commande}" if forme.sous_commande else forme.commande
        arguments = []
        for argument in forme.arguments:
            detail = "|".join(argument.vocabulaire) if argument.vocabulaire else argument.type
            marque = "" if argument.obligatoire else "?"
            arguments.append(f"<{argument.nom}:{detail}{marque}>")
        lignes.append(f"{nom} {' '.join(arguments)}".strip() + f"  — {forme.libelle}")
    return "\n".join(lignes)


_PROMPT_FIXE = """Tu traduis une phrase de jardinier en UNE commande d'application, choisie dans
le catalogue ci-dessous. Tu n'inventes jamais une commande absente du catalogue,
jamais un argument absent de la phrase, jamais une valeur hors du vocabulaire
déclaré.

Si la phrase ne désigne aucune de ces commandes — un geste au jardin
(« récolté 2 kg de tomates »), une question d'agronomie, une demande de
procédure (« comment supprimer une parcelle ? ») — réponds AUCUNE.

Catalogue :
__CATALOGUE__

Réponds STRICTEMENT au format :
COMMANDE|SOUS_COMMANDE|arg1;arg2;arg3|CONFIANCE

SOUS_COMMANDE vaut - si la commande n'en a pas. Les arguments sont ceux du
catalogue, dans l'ordre, séparés par des points-virgules ; un argument absent de
la phrase est laissé vide. CONFIANCE est un nombre entre 0 et 1.
Exemple : parcelle|supprimer|nord|0.95
Exemple : AUCUNE|-||1.0
"""


def _prompt_fixe() -> str:
    # `.replace()`, jamais `.format()` — invariant projet : le prompt contient
    # des accolades de vocabulaire, et `.format()` les interpréterait.
    return _PROMPT_FIXE.replace("__CATALOGUE__", _decrire_catalogue())


def _valider_sortie_modele(brut: str, texte: str) -> Optional[CommandeInterpretee]:
    """[CA4] Rejette tout ce qui n'est pas exactement une commande du catalogue.

    Trois refus, et aucune tolérance : une commande hors catalogue, une valeur
    hors vocabulaire fermé, un argument que la phrase ne contient pas. Le
    dernier est le plus important — c'est lui qui empêche une parcelle que
    personne n'a nommée d'être proposée à la suppression.
    """
    morceaux = (brut or "").strip().split("|")
    if len(morceaux) < 4:
        return None
    commande = morceaux[0].strip().lower()
    sous_commande = morceaux[1].strip().lower()
    sous_commande = None if sous_commande in ("-", "", "none") else sous_commande
    if commande in ("aucune", ""):
        return None
    forme = FORMES_PAR_CLE.get((commande, sous_commande))
    if forme is None:
        log.info("🎛️  INTERPRETEUR   : sortie modèle hors catalogue (%r) → rejetée", brut[:80])
        return None

    try:
        confiance = max(0.0, min(1.0, float(morceaux[3].strip())))
    except ValueError:
        confiance = 0.0

    normalise_phrase, _ = normaliser(texte)
    donnees = [m.strip() for m in morceaux[2].split(";")] if morceaux[2].strip() else []
    valeurs: Valeurs = {}
    for rang, argument in enumerate(forme.arguments):
        valeur = donnees[rang] if rang < len(donnees) else ""
        if not valeur:
            continue
        if argument.vocabulaire and valeur not in argument.vocabulaire:
            log.info(
                "🎛️  INTERPRETEUR   : valeur %r hors du vocabulaire de %s → rejetée",
                valeur, argument.nom,
            )
            return None
        # L'argument doit se retrouver dans la phrase — y compris une valeur de
        # vocabulaire fermé, qu'aucun synonyme approchant ne doit pouvoir
        # produire (CA13).
        normalise_valeur, _ = normaliser(valeur)
        if normalise_valeur not in normalise_phrase:
            log.info(
                "🎛️  INTERPRETEUR   : argument %r absent de la phrase → rejeté", valeur
            )
            return None
        valeurs[argument.nom] = valeur

    return _construire_commande(forme, valeurs, ORIGINE_MODELE, confiance, texte)


def _appeler_modele(texte: str, ctx: Optional[TenantContext]) -> Optional[CommandeInterpretee]:
    """Repli modèle. N'échoue jamais vers l'appelant : une indisponibilité rend
    la main à la cascade normale — la phrase repart au routeur, exactement comme
    avant cette US."""
    from llm import passerelle

    try:
        reponse = passerelle.appeler_chat(
            appel_type=passerelle.TYPE_CLASSIFICATION,
            ctx=ctx,
            prompt_fixe=_prompt_fixe(),
            prompt_variable="",
            message_utilisateur=texte,
            # Même réglage que le routeur, et pour la même raison : le petit
            # modèle émet des jetons de raisonnement AVANT son contenu, et
            # `max_tokens` plafonne les deux ensemble.
            max_tokens=200,
            reasoning=True,
            role_prompt="user",
        )
    except Exception as e:  # noqa: BLE001 — la cascade normale reprend la main
        log.warning(
            "🎛️  INTERPRETEUR   : repli modèle indisponible (%s) → cascade normale",
            type(e).__name__,
        )
        return None
    return _valider_sortie_modele(reponse.texte, texte)


# ─────────────────────────────────────────────────────────────────────────────
# API publique
# ─────────────────────────────────────────────────────────────────────────────
def interpreter(
    texte: str,
    ctx: Optional[TenantContext] = None,
    autoriser_modele: bool = True,
) -> "CommandeInterpretee | Ambiguite | None":
    """[CA1 → CA5] Traduit une phrase en une commande du catalogue, ou rien.

    Ordre strict : garde de savoir (CA2) → règles (CA3) → modèle sous contrainte
    fermée (CA4). `None` signifie « ce n'est pas une commande » et rend la main à
    la cascade normale — jamais « je n'ai pas compris ».

    La dictée vocale ne change rien (CA5) : ce module ne voit qu'un texte, et
    `bot.handle_voice` lui passe la transcription au même point du flux que
    `bot.handle_text` lui passe la frappe.
    """
    debut = time.monotonic()
    resultat = reconnaitre_par_regles(texte)
    if resultat is not None:
        latence = int((time.monotonic() - debut) * 1000)
        if isinstance(resultat, Ambiguite):
            return Ambiguite(resultat.candidats, resultat.texte_origine, latence)
        return replace(resultat, latence_ms=latence)

    if not autoriser_modele:
        return None
    brut = (texte or "").strip()
    if not brut or brut.startswith("/"):
        return None
    normalise, _ = normaliser(brut)
    if not normalise or _est_demande_de_savoir(normalise):
        return None

    candidate = _appeler_modele(brut, ctx)
    if candidate is None:
        return None
    if candidate.confiance < SEUIL_CONFIANCE_MODELE:
        # [CA12] Le doute ne fait jamais agir : sous le seuil, la phrase repart
        # à la cascade normale plutôt que d'exécuter la plus probable.
        log.info(
            "🎛️  INTERPRETEUR   : confiance %.2f < %.2f → rendu à la cascade",
            candidate.confiance, SEUIL_CONFIANCE_MODELE,
        )
        return None
    return replace(candidate, latence_ms=int((time.monotonic() - debut) * 1000))


# ─────────────────────────────────────────────────────────────────────────────
# CA11 — une valeur dictée est relue avant d'être écrite
# ─────────────────────────────────────────────────────────────────────────────
_UNITES_LETTRES: tuple[str, ...] = (
    "zéro", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit",
    "neuf", "dix", "onze", "douze", "treize", "quatorze", "quinze", "seize",
)
_DIZAINES_LETTRES: dict[int, str] = {
    2: "vingt", 3: "trente", 4: "quarante", 5: "cinquante", 6: "soixante",
}


def _entier_en_lettres(valeur: int) -> str:
    if valeur < 0:
        return f"moins {_entier_en_lettres(-valeur)}"
    if valeur < 17:
        return _UNITES_LETTRES[valeur]
    if valeur < 100:
        if valeur < 70:
            dizaine, unite = divmod(valeur, 10)
            base = _DIZAINES_LETTRES[dizaine]
        elif valeur < 80:
            base, unite = "soixante", valeur - 60
        else:
            base, unite = "quatre-vingt", valeur - 80
        if unite == 0:
            return base + ("s" if base == "quatre-vingt" else "")
        if unite == 1 and valeur < 70:
            return f"{base}-et-un"
        if unite == 11 and 70 <= valeur < 80:
            return "soixante-et-onze"
        return f"{base}-{_entier_en_lettres(unite)}"
    if valeur < 1000:
        centaine, reste = divmod(valeur, 100)
        tete = "cent" if centaine == 1 else f"{_UNITES_LETTRES[centaine]}-cent"
        if reste == 0:
            return tete + ("s" if centaine > 1 else "")
        return f"{tete}-{_entier_en_lettres(reste)}"
    return str(valeur)


def nombre_en_lettres(valeur: str) -> str:
    """[CA11] Un nombre écrit en toutes lettres — « 1 » et « 10 » ne s'entendent
    pas, « un » et « dix » si.

    C'est tout l'objet de la restitution : la transcription vocale échoue
    précisément là, et la valeur part dans un référentiel partagé.
    """
    texte = str(valeur or "").strip().replace(",", ".")
    negatif = texte.startswith("-")
    texte = texte.lstrip("+-")
    if not texte or not texte.replace(".", "", 1).isdigit():
        return str(valeur)
    entier, _, decimales = texte.partition(".")
    lettres = _entier_en_lettres(int(entier or 0))
    if decimales and decimales.strip("0"):
        lettres += " virgule " + " ".join(
            _UNITES_LETTRES[int(chiffre)] for chiffre in decimales
        )
    return f"moins {lettres}" if negatif else lettres


#: Unités des clés `clé=valeur` de `/parcelle modifier` — le seul argument du
#: catalogue qui porte plusieurs valeurs sous un même nom. La superficie y est
#: chiffrée, donc relue en toutes lettres comme les autres (CA11).
_UNITES_MODIFICATION: dict[str, Optional[str]] = {
    "superficie": "m²", "exposition": None, "pepiniere": None, "ordre": None,
}
_LIBELLES_MODIFICATION: dict[str, str] = {
    "superficie": "superficie", "exposition": "exposition",
    "pepiniere": "pépinière", "ordre": "ordre d'affichage",
}


def _ligne_valeur(libelle: str, valeur: str, unite: Optional[str], chiffree: bool) -> str:
    suffixe = f" {unite}" if unite else ""
    if chiffree:
        return f"• {libelle} : *{valeur}{suffixe}* ({nombre_en_lettres(valeur)}{suffixe})"
    return f"• {libelle} : *{valeur}*"


def recapitulatif(commande: CommandeInterpretee) -> str:
    """[CA10, CA11] Ce qui va être fait, en clair, et la commande équivalente.

    Le rappel de la syntaxe n'est pas décoratif : c'est ainsi que le jardinier
    apprend la commande sans avoir eu à l'apprendre. Et tout nombre y est
    restitué en chiffres ET en toutes lettres, avec son unité — « profondeur
    1 » et « profondeur 10 » ne s'entendent pas, et la seconde écrirait une
    donnée fausse dans un référentiel partagé.
    """
    lignes = [f"*{commande.forme.libelle}*"]
    for argument in commande.forme.arguments:
        valeur = commande.valeurs.get(argument.nom)
        if not valeur:
            continue
        libelle = argument.nom.replace("_", " ")
        if argument.nom == "modification" and "=" in valeur:
            cle, _, brute = valeur.partition("=")
            cle = cle.strip().lower()
            lisible = {"true": "oui", "false": "non"}.get(brute.strip().lower(), brute.strip())
            lignes.append(_ligne_valeur(
                _LIBELLES_MODIFICATION.get(cle, cle),
                lisible,
                _UNITES_MODIFICATION.get(cle),
                chiffree=_est_chiffre(lisible),
            ))
            continue
        lignes.append(_ligne_valeur(
            libelle, valeur, argument.unite, chiffree=(argument.type == TYPE_NOMBRE)
        ))
    lignes.append("")
    lignes.append(f"Équivalent tapé : `{commande.commande_equivalente()}`")
    return "\n".join(lignes)


def _est_chiffre(valeur: str) -> bool:
    return bool(re.fullmatch(r"-?\d+(?:[.,]\d+)?", (valeur or "").strip()))


def persister_journal(
    ctx: TenantContext,
    commande: CommandeInterpretee,
    issue: str,
    log_id: Optional[int] = None,
) -> Optional[int]:
    """[CA18] Écrit (ou met à jour) la ligne de `routage_logs` de cette
    interprétation, et rend son identifiant.

    Une interprétation vit en deux temps : elle est PROPOSÉE, puis confirmée,
    refusée ou abandonnée. La ligne est donc écrite au premier temps et
    complétée au second — `log_id` porte le lien entre les deux.

    Ne lève jamais : la journalisation est de l'observabilité, et une panne
    d'écriture ne doit pas empêcher une commande d'être proposée ni exécutée.
    C'est la même règle que `llm.routeur._persister_routage_log`, dont cette
    fonction partage la table.
    """
    from database.db import SessionLocal
    from database.models import RoutageLog
    from llm.routeur import normaliser_question

    nom_commande = f"{commande.commande} {commande.sous_commande or ''}".strip()
    db = None
    try:
        db = SessionLocal()
        if log_id is not None:
            entree = db.get(RoutageLog, log_id)
            if entree is not None:
                entree.issue_interpretation = issue
                db.commit()
                return entree.id
        entree = RoutageLog(
            potager_id=ctx.potager_id,
            # La question NORMALISÉE, jamais le message brut — même règle
            # qu'US-097 / CA2, et la même fonction de normalisation : une
            # seconde implémentation divergerait au premier ajustement.
            question_normalisee=normaliser_question(commande.texte_origine or ""),
            nature=NATURE_COMMANDE,
            origine_classification=commande.origine,
            etage_resolveur=ETAGE_COMMANDE,
            cascade_remontee=False,
            confiance=commande.confiance,
            latence_ms=commande.latence_ms,
            # Une commande reconnue par règle ne consomme aucun jeton (CA3, CA17).
            tokens_consommes=0,
            commande_interpretee=nom_commande,
            issue_interpretation=issue,
        )
        db.add(entree)
        db.commit()
        return entree.id
    except Exception as e:  # noqa: BLE001 — observabilité, jamais bloquant
        log.warning(
            "🎛️  INTERPRETEUR   : journal non écrit (%s) — la commande suit son cours",
            type(e).__name__,
        )
        if db is not None:
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass
        return None
    finally:
        if db is not None:
            db.close()


def journaliser(commande: CommandeInterpretee, issue: str) -> None:
    """[CA18] Une ligne par interprétation — nature, commande, sous-commande,
    origine, confiance, latence, issue. C'est la seule façon de savoir quelles
    formulations enrichir ensuite."""
    log.info(
        "🎛️  INTERPRETEUR   │ nature=%s │ origine=%-6s │ /%-12s %-12s │ "
        "confiance=%.2f │ %d ms │ issue=%-10s │ regle=%-24s │ '%s'",
        NATURE_COMMANDE,
        commande.origine,
        commande.commande,
        commande.sous_commande or "",
        commande.confiance,
        commande.latence_ms,
        issue,
        commande.regle or "-",
        (commande.texte_origine or "")[:80],
    )

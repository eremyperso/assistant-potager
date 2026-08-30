"""
llm/parseur_deterministe.py — Étage 0 de la cascade, versant saisie [US-094]
================================================================================
Grammaire déterministe qui transforme les phrases de saisie **fréquentes** en
items parsés, dans le format exact que produit déjà le modèle
(`llm.groq_client.parse_commande`), **sans aucun appel au fournisseur**.

Ce module vit dans `llm/` aux côtés de `llm/routeur.py` parce qu'il est un
étage de la même cascade et qu'il décide, lui aussi, s'il faut payer un appel
au modèle — pas parce qu'il en fait un : il n'en fait jamais.

Principe directeur, tranché par l'US : **la précision prime sur la couverture.**
Le parseur est volontairement conservateur. Sa règle centrale n'est pas
« reconnaître le maximum » mais **« tout expliquer »** : chaque mot de la
phrase doit être attribué à un champ (geste, quantité, unité, parcelle,
culture, variété, date) ou figurer dans la liste close des mots vides. Le
moindre résidu inexpliqué fait basculer la phrase entière sur le repli LLM.
C'est ce qui garantit CA6 : un faux positif silencieux (« 2 kg » compris comme
« 2 pieds ») coûte infiniment plus cher qu'un appel au modèle.

Ce qu'il ne fait PAS, délibérément :

* il ne crée jamais de culture ni de parcelle inconnue (CA4) — une culture
  absente du potager ou un nom de parcelle qui ne résout vers rien font
  basculer sur le repli et sur le flux de désambiguïsation existant ;
* il n'applique aucune règle métier : stock, type d'organe, cohérence
  culture/parcelle restent à la validation centrale d'US-049, traversée à
  l'identique par les deux chemins (CA7) ;
* il n'introduit aucune seconde normalisation (CA3) : cultures et variétés
  passent par `utils.culture_resolve`, les parcelles par
  `utils.parcelles.resolve_parcelle`, les gestes par `utils.actions.ACTION_MAP`,
  les dates par `utils.date_utils.resoudre_ancrage_temporel` ;
* il ne s'auto-enrichit pas : la grammaire reste lisible et modifiable à la
  main, alimentée par les saisies réellement tombées en repli (mesurables via
  `origine_parsing`, CA10).

La grammaire est **par langue** et le projet est francophone : rien ici n'est
généralisé prématurément à d'autres langues.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date as _date
from typing import Optional

from unidecode import unidecode

from app.services.context import TenantContext
from utils.actions import ACTION_MAP
from utils.date_utils import (
    ANCRAGE_INCONNU,
    ANCRAGE_RESOLU,
    NOMBRES_LETTRES,
    SOURCE_PRESUMEE,
    resoudre_ancrage_temporel,
)

log = logging.getLogger("potager")

ORIGINE_DETERMINISTE = "deterministe"
ORIGINE_LLM = "llm"


@dataclass(frozen=True)
class ResultatParseur:
    """Issue de la lecture déterministe d'une phrase.

    `items` est None dès que la grammaire déclare ne pas savoir ; `raison` dit
    alors pourquoi, et c'est cette raison qui alimente la maintenance de la
    grammaire (quelles formes tombent réellement en repli).
    """

    items: Optional[list[dict]] = None
    raison: str = ""

    @property
    def reconnu(self) -> bool:
        return self.items is not None


# ─────────────────────────────────────────────────────────────────────────────
# Périmètre des gestes couverts
# -----------------------------------------------------------------------------
# Sous-ensemble strict du référentiel unique `utils.actions.ACTION_MAP`
# (US-168) : on n'y ajoute aucun geste, on en retire ceux dont l'extraction
# n'est pas déterministe.
#   * `observation` porte du texte libre, et dispose de son propre flux guidé
#     (US-038) ;
#   * `traitement` exige d'identifier un produit, ce qu'aucune règle lexicale
#     ne fait sans deviner.
# ─────────────────────────────────────────────────────────────────────────────
GESTES_NON_COUVERTS: frozenset[str] = frozenset({"observation", "traitement"})
GESTES_COUVERTS: frozenset[str] = frozenset(ACTION_MAP) - GESTES_NON_COUVERTS

# Variantes lexicales trop génériques pour décider seules d'un geste. « ajouté »
# introduit aussi bien un amendement (« ajouté du compost ») qu'une plantation
# (« ajouté 2 pieds de ciboulette ») — mesuré sur le corpus de production, où
# le chemin modèle tranche « plantation » là où la seule table de variantes
# donne « amendement ». Elles restent dans ACTION_MAP, qui sert aussi à
# reconnaître a posteriori ; c'est ici, sur le chemin d'écriture, qu'elles ne
# suffisent pas.
VARIANTES_TROP_GENERIQUES: frozenset[str] = frozenset({
    "ajout", "ajoute", "apport", "apporte",
})

# Gestes qui portent structurellement sur une culture précise — même liste que
# `app.services.evenements.CultureManquanteError`, dont le parseur anticipe le
# rejet plutôt que de produire un item voué à être refusé.
GESTES_EXIGEANT_CULTURE: frozenset[str] = frozenset({
    "semis", "plantation", "mise_en_godet", "recolte", "perte", "perte_godet", "vendu",
})

# Gestes pour lesquels un simple dénombrement sans unité prononcée signifie
# « des pieds ». C'est la convention retenue par US-168 (« plants » est
# l'unité canonique de dénombrement) et celle que le modèle applique déjà.
# Un semis en est exclu : sans unité dictée, semer met des graines en terre —
# c'est le défaut posé par `_normalize_unite_semis`.
GESTES_DENOMBREMENT_IMPLICITE: frozenset[str] = frozenset({
    "plantation", "recolte", "perte", "perte_godet", "vendu",
})

# Fenêtre de tête où le geste est cherché — même raison et même valeur que
# `llm.routeur._FENETRE_GESTE_MOTS` : une saisie annonce son geste d'emblée.
_FENETRE_GESTE_MOTS = 4


# ─────────────────────────────────────────────────────────────────────────────
# Vocabulaire clos
# ─────────────────────────────────────────────────────────────────────────────

# Unités reconnues → forme émise, identique à celle que produit le modèle.
# La normalisation finale reste à l'écriture (`_normalize_unite_denombrement`
# et `_normalize_unite_semis` dans app/services/evenements.py) : rien n'est
# dupliqué ici.
_UNITES: dict[str, str] = {
    "kg": "kg", "kilo": "kg", "kilos": "kg", "kilogramme": "kg", "kilogrammes": "kg",
    "g": "g", "gr": "g", "gramme": "g", "grammes": "g",
    "l": "l", "litre": "l", "litres": "l",
    "graine": "graines", "graines": "graines",
    "plant": "plants", "plants": "plants", "plante": "plants", "plantes": "plants",
    "pied": "plants", "pieds": "plants",
    "m2": "m²",
}

# Mots vides : présents dans la phrase, porteurs d'aucune information de champ.
# Liste CLOSE — c'est elle qui rend la règle « tout expliquer » tenable.
_MOTS_VIDES: frozenset[str] = frozenset({
    "de", "du", "des", "d", "l", "la", "le", "les", "a", "au", "aux", "en",
    "et", "sur", "dans", "pour", "avec", "mes", "mon", "ma", "ce", "cet",
    "cette", "ces", "j", "ai", "je", "on", "nous", "il", "y", "s",
    "que", "qui", "effectue", "effectuee", "effectues", "effectuees",
    "fait", "faite", "faits", "faites", "total", "totale", "environ",
    # « variété » annonce la variété qui suit ; le mot lui-même ne porte rien.
    "variete", "varietes",
})
# « est » et « sont » sont volontairement ABSENTS de la liste ci-dessus : dans
# une saisie de potager, « est » est presque toujours le point cardinal
# (« carré est »), pas le verbe. Les traiter comme mots vides faisait perdre le
# nom de la parcelle.

# Marqueurs de parcelle : le nom qui suit est résolu contre les parcelles
# réelles du potager, jamais créé (CA4).
_MARQUEURS_PARCELLE: frozenset[str] = frozenset({"parcelle", "parcelles", "carre", "planche", "serre"})

# Vocabulaire de rangs : le partage quantité/rang est justement l'ambiguïté que
# le modèle signale par `action="AMBIGUE"`. La grammaire ne tranche pas.
_MOTS_RANG: frozenset[str] = frozenset({
    "rang", "rangs", "rangee", "rangees", "range", "ranges", "ranger", "rangers",
    "ilot", "ilots", "poquet", "poquets", "barquette", "barquettes",
})

# Articles indéfinis : nombres en toutes lettres, mais bien plus souvent de
# simples déterminants. Ils ne valent « 1 » que collés à une unité (« un kilo »).
_NOMBRES_AMBIGUS: frozenset[str] = frozenset({"un", "une"})


# ─────────────────────────────────────────────────────────────────────────────
# Normalisation et découpage
# ─────────────────────────────────────────────────────────────────────────────
_DECIMALE_VIRGULE = re.compile(r"(\d),(\d)")
_NOMBRE_COLLE = re.compile(r"(?<=\d)(?=[a-z])")
_NON_SIGNIFIANT = re.compile(r"[^a-z0-9.\s]")
_POINT_ORPHELIN = re.compile(r"(?<!\d)\.|\.(?!\d)")


def _normaliser(texte: str) -> str:
    """Minuscules, sans accents, ponctuation neutralisée — les décimales et les
    unités collées au nombre (« 600g ») survivent au passage."""
    s = unidecode((texte or "").lower()).replace("’", "'")
    s = _DECIMALE_VIRGULE.sub(r"\1.\2", s)      # 2,5 kg → 2.5 kg
    s = _NON_SIGNIFIANT.sub(" ", s)             # ponctuation, apostrophes, *, +…
    s = _POINT_ORPHELIN.sub(" ", s)             # points de phrase, pas les décimales
    s = _NOMBRE_COLLE.sub(" ", s)               # 600g → 600 g
    return re.sub(r"\s+", " ", s).strip()


def _singulier(mot: str) -> str:
    """Dépluralisation simple, suffisante en français de potager."""
    if len(mot) > 3 and mot.endswith("x"):
        return mot[:-1]
    if len(mot) > 3 and mot.endswith("s"):
        return mot[:-1]
    return mot


def _cle(mots: list[str]) -> str:
    """Clé de comparaison d'un groupe de mots : mots vides retirés, chaque mot
    ramené au singulier. Permet à « courgettes jaunes » de rejoindre la variété
    « jaune » déjà en base sans introduire de règle de casse concurrente."""
    return " ".join(_singulier(m) for m in mots if m not in _MOTS_VIDES)


# ─────────────────────────────────────────────────────────────────────────────
# Étapes de la grammaire — chacune CONSOMME les mots qu'elle explique
# ─────────────────────────────────────────────────────────────────────────────

def _variantes_de_geste() -> list[tuple[str, str]]:
    """(forme normalisée, geste canonique), les plus longues d'abord —
    « mise en godet » doit l'emporter sur « godet »."""
    formes: list[tuple[str, str]] = []
    for canonique, variantes in ACTION_MAP.items():
        if canonique not in GESTES_COUVERTS:
            continue
        for forme in (canonique, *variantes):
            if forme in VARIANTES_TROP_GENERIQUES:
                continue
            normalisee = _normaliser(forme.replace("_", " "))
            if normalisee:
                formes.append((normalisee, canonique))
    return sorted(set(formes), key=lambda t: len(t[0]), reverse=True)


_VARIANTES_GESTE = _variantes_de_geste()


def _extraire_geste(mots: list[str]) -> tuple[Optional[str], list[str]]:
    """Cherche un geste dans les premiers mots. Retourne (geste, mots restants).

    Seule la tête est examinée : une saisie annonce son geste d'emblée. Un
    geste cité plus loin est du contexte, pas une déclaration d'action.
    """
    tete = mots[:_FENETRE_GESTE_MOTS]
    for forme, canonique in _VARIANTES_GESTE:
        cible = forme.split()
        for debut in range(len(tete) - len(cible) + 1):
            if tete[debut:debut + len(cible)] == cible:
                return canonique, mots[:debut] + mots[debut + len(cible):]
    return None, mots


def _extraire_nombres(mots: list[str]) -> tuple[list[tuple[int, float]], list[str]]:
    """Repère les nombres exploitables. Retourne [(position, valeur)] et les mots.

    Les nombres ne sont pas encore retirés : leur signification dépend de
    l'unité qui les suit, résolue à l'étape suivante.
    """
    trouves: list[tuple[int, float]] = []
    for i, mot in enumerate(mots):
        if re.fullmatch(r"\d+(?:\.\d+)?", mot):
            trouves.append((i, float(mot)))
        elif mot in NOMBRES_LETTRES and mot not in _NOMBRES_AMBIGUS:
            trouves.append((i, float(NOMBRES_LETTRES[mot])))
        elif mot in _NOMBRES_AMBIGUS and i + 1 < len(mots) and mots[i + 1] in _UNITES:
            # « un kilo de tomates » — déterminant devenu quantité par l'unité
            # qui le suit immédiatement, et seulement dans ce cas.
            trouves.append((i, 1.0))
    return trouves, mots


def _extraire_parcelle(mots: list[str], cultures: dict[str, str]) -> tuple[Optional[str], list[str], bool]:
    """Extrait le libellé de parcelle cité. Retourne (libellé, restants, cité).

    `cité` distingue « aucune parcelle dans la phrase » (le potager en déduira
    l'emplacement comme aujourd'hui) de « une parcelle est nommée » — auquel cas
    elle DOIT résoudre, sinon la phrase part au repli (CA4).
    """
    for i, mot in enumerate(mots):
        if mot not in _MARQUEURS_PARCELLE:
            continue
        libelle: list[str] = []
        j = i + 1
        while j < len(mots):
            suivant = mots[j]
            if suivant in _MOTS_VIDES:
                break
            # « parcelle planche ombre » : le second marqueur fait partie du
            # nom, il ne le termine pas — il ne l'interrompt qu'une fois le
            # libellé commencé (« planche ombre parcelle … »).
            if suivant in _MARQUEURS_PARCELLE and libelle:
                break
            if _singulier(suivant) in cultures or suivant in cultures:
                break
            libelle.append(suivant)
            j += 1
        # « serre » et « planche » sont des noms de parcelle à part entière
        # quand rien ne les suit ; « parcelle » seul ne nomme rien.
        if not libelle and mot in ("serre", "planche"):
            libelle = [mot]
        if not libelle:
            return None, mots, True
        return " ".join(libelle), mots[:i] + mots[j:], True
    return None, mots, False


def _index_cultures(connues: list[str]) -> dict[str, str]:
    """Index normalisé → nom canonique, singulier et pluriel confondus."""
    index: dict[str, str] = {}
    for nom in connues:
        normalise = _normaliser(nom)
        if not normalise:
            continue
        index.setdefault(normalise, nom)
        index.setdefault(_cle(normalise.split()), nom)
    return index


def _extraire_culture(mots: list[str], cultures: dict[str, str]) -> tuple[Optional[str], list[str], int]:
    """Trouve LA culture citée. Retourne (nom canonique, restants, nb trouvées).

    Deux cultures dans la même phrase (« arrosage oignons et échalotes »)
    produisent deux évènements distincts côté modèle : la grammaire ne tranche
    pas ce découpage et rend la main.
    """
    trouvees: list[tuple[int, int, str]] = []
    i = 0
    while i < len(mots):
        appariee = None
        for longueur in (3, 2, 1):
            if i + longueur > len(mots):
                continue
            groupe = mots[i:i + longueur]
            for candidate in (" ".join(groupe), _cle(groupe)):
                if candidate and candidate in cultures:
                    appariee = (i, i + longueur, cultures[candidate])
                    break
            if appariee:
                break
        if appariee:
            trouvees.append(appariee)
            i = appariee[1]
        else:
            i += 1

    if len(trouvees) != 1:
        return None, mots, len(trouvees)
    debut, fin, nom = trouvees[0]
    return nom, mots[:debut] + mots[fin:], 1


# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée
# ─────────────────────────────────────────────────────────────────────────────

def _repli(raison: str, texte: str) -> ResultatParseur:
    log.info("🔤 PARSEUR DÉTERM. : repli modèle — %s | texte=%r", raison, texte)
    return ResultatParseur(items=None, raison=raison)


def parser_saisie(
    texte: str,
    ctx: TenantContext,
    db=None,
    aujourd_hui: Optional[_date] = None,
) -> ResultatParseur:
    """[US-094 / CA1] Lit une saisie courante sans appel au modèle.

    Retourne un `ResultatParseur` dont `items` a exactement la forme produite
    par `llm.groq_client.parse_commande` — un item par évènement — ou None dès
    que la grammaire déclare ne pas savoir.

    `db` est optionnel : sans session fournie, une session courte est ouverte
    pour lire le catalogue du potager (cultures, variétés, parcelles).
    """
    if not texte or not texte.strip():
        return _repli("texte vide", texte)

    normalise = _normaliser(texte)
    if not normalise:
        return _repli("texte sans contenu exploitable", texte)

    # ── 1. Ancrage temporel (CA2) ────────────────────────────────────────────
    ancrage = resoudre_ancrage_temporel(texte, aujourd_hui=aujourd_hui)
    if ancrage.statut == ANCRAGE_INCONNU:
        return _repli("expression de date non couverte", texte)
    date_iso = ancrage.date_iso if ancrage.statut == ANCRAGE_RESOLU else None
    # [US-169 / CA5] La grammaire connaît déjà la nature de l'ancrage qu'elle a
    # lu (dicté en clair / relatif résolu) ; sans ancrage, la date retombera
    # sur la convention « aujourd'hui » — présumée, jamais « inconnue ».
    date_source = ancrage.source if ancrage.statut == ANCRAGE_RESOLU else SOURCE_PRESUMEE
    if ancrage.statut == ANCRAGE_RESOLU and ancrage.debut >= 0:
        # Découpe aux bornes rendues par la grammaire temporelle, pas par une
        # substitution de motif : « hier » dicté deux fois ne doit disparaître
        # qu'une fois, et seulement là où la date a réellement été lue.
        source = _normaliser_pour_retrait(texte)
        normalise = _normaliser(source[:ancrage.debut] + " " + source[ancrage.fin:])

    mots = normalise.split()

    # ── 2. Geste (CA1) ───────────────────────────────────────────────────────
    geste, mots = _extraire_geste(mots)
    if geste is None:
        return _repli("aucun geste reconnu en tête de phrase", texte)

    if any(m in _MOTS_RANG for m in mots):
        return _repli("vocabulaire de rangs — partage quantité/rang ambigu", texte)

    fermer_db = db is None
    if fermer_db:
        from database.db import SessionLocal
        db = SessionLocal()
    try:
        from utils.culture_resolve import cultures_connues, resolve_culture, resolve_variete, varietes_connues
        from utils.parcelles import resolve_parcelle

        cultures = _index_cultures(cultures_connues(db, ctx.potager_id))

        # ── 3. Parcelle (CA3, CA4) ───────────────────────────────────────────
        libelle_parcelle, mots, parcelle_citee = _extraire_parcelle(mots, cultures)
        parcelle_nom: Optional[str] = None
        if parcelle_citee:
            if not libelle_parcelle:
                return _repli("parcelle citée sans nom exploitable", texte)
            parcelle = resolve_parcelle(db, libelle_parcelle, potager_id=ctx.potager_id)
            if parcelle is None:
                return _repli(f"parcelle inconnue du potager : {libelle_parcelle!r}", texte)
            parcelle_nom = parcelle.nom

        # ── 4. Quantités et unités ───────────────────────────────────────────
        nb_graines_semees: Optional[int] = None
        if geste == "mise_en_godet":
            mots, nb_graines_semees = _detacher_graines_semees(mots)

        nombres, mots = _extraire_nombres(mots)
        if len(nombres) > 1:
            return _repli("plusieurs quantités dans la phrase", texte)

        quantite: Optional[float] = None
        unite: Optional[str] = None
        if nombres:
            position, quantite = nombres[0]
            suivant = position + 1
            if suivant < len(mots) and mots[suivant] in _UNITES:
                unite = _UNITES[mots[suivant]]
                mots = mots[:position] + mots[suivant + 1:]
            else:
                mots = mots[:position] + mots[position + 1:]

        # Une unité orpheline signale une quantité que la grammaire n'a pas su
        # lire (« ajouté pied de thym », « sur les pieds de tomate ») : en
        # déduire « 1 » serait exactement le faux positif que CA6 interdit.
        if any(m in _UNITES for m in mots):
            return _repli("unité sans quantité rattachée", texte)

        if unite is None and quantite is not None and geste in GESTES_DENOMBREMENT_IMPLICITE:
            unite = "plants"

        # ── 5. Culture puis variété (CA3, CA4) ───────────────────────────────
        culture, mots, nb_cultures = _extraire_culture(mots, cultures)
        if culture is None and nb_cultures > 1:
            return _repli("plusieurs cultures dans la phrase", texte)
        if culture is None and geste in GESTES_EXIGEANT_CULTURE:
            return _repli("culture absente ou inconnue du potager", texte)
        if culture is None and parcelle_nom is None:
            return _repli("ni culture ni parcelle identifiées", texte)

        variete: Optional[str] = None
        residus = [m for m in mots if m not in _MOTS_VIDES]
        if residus:
            if culture is None:
                return _repli(f"mots non attribués : {' '.join(residus)!r}", texte)
            candidate = _cle(residus)
            connues = {_cle(_normaliser(v).split()): v for v in varietes_connues(db, ctx.potager_id, culture)}
            if candidate not in connues:
                return _repli(f"mots non attribués : {' '.join(residus)!r}", texte)
            variete = connues[candidate]

        # ── 6. Canonisation, à l'identique du chemin modèle (CA3) ────────────
        culture_finale = resolve_culture(db, ctx.potager_id, culture) if culture else None
        variete_finale = resolve_variete(db, ctx.potager_id, culture_finale, variete) if variete else None
    finally:
        if fermer_db:
            db.close()

    item: dict = {
        "action": geste,
        "culture": culture_finale,
        "variete": variete_finale,
        "quantite": quantite,
        "unite": unite,
        "parcelle": parcelle_nom,
        "rang": None,
        "duree_minutes": None,
        "traitement": None,
        "date": date_iso,
        "commentaire": None,
        "nb_graines_semees": nb_graines_semees,
        "nb_plants_godets": None,
        "origine_parsing": ORIGINE_DETERMINISTE,
        "date_source": date_source,
    }

    if geste == "mise_en_godet":
        # Une mise en godet compte des plants repiqués, jamais une quantité
        # générique : même contrat que le prompt de parsing.
        item["nb_plants_godets"] = int(quantite) if quantite is not None else None
        item["quantite"] = None
        item["unite"] = None

    log.info(
        "🔤 PARSEUR DÉTERM. : reconnu sans modèle | geste=%s culture=%s qte=%s %s parcelle=%s date=%s",
        geste, culture_finale, item["quantite"], item["unite"] or "", parcelle_nom, date_iso,
    )
    return ResultatParseur(items=[item], raison="")


_MOTIF_GRAINES_SEMEES = re.compile(r"\bsur\s+(\d{1,4})(\s+graines?)?\b")


def _detacher_graines_semees(mots: list[str]) -> tuple[list[str], Optional[int]]:
    """« mise en godet 8 plants de blette sur 20 » — le nombre introduit par
    « sur » est la barquette d'origine, pas une seconde quantité."""
    phrase = " ".join(mots)
    m = _MOTIF_GRAINES_SEMEES.search(phrase)
    if not m:
        return mots, None
    restant = (phrase[:m.start()] + " " + phrase[m.end():]).strip()
    return restant.split(), int(m.group(1))


def _normaliser_pour_retrait(texte: str) -> str:
    """Normalisation *sans* neutralisation de la ponctuation interne aux dates :
    l'expression rendue par `resoudre_ancrage_temporel` porte encore ses « / »
    et ses « - », il faut donc la retirer d'un texte qui les a conservés."""
    s = unidecode((texte or "").lower()).replace("’", "'")
    return re.sub(r"\s+", " ", s).strip()

"""
app/services/reponses_chiffrees.py — Étage 1 : gabarits sur agrégats SQL [US-096]
================================================================================
Les questions du jardinier qui portent sur **ses propres chiffres** se répondent
en SQL et en français, sans jamais passer par un modèle : une agrégation donne
une réponse *exacte*, immédiate et gratuite là où une reformulation donnerait une
réponse approximative, lente et facturée.

Le catalogue est le livrable central de cette US, et il se lit d'un coup d'œil :

    une famille de question  →  une agrégation du catalogue  →  un gabarit

Ajouter une famille consiste à ajouter une ligne à `FAMILLES`, une fonction
décorée `@catalogue_sql.enregistrer` et un gabarit dans `GABARITS` — **sans
toucher au routeur** (US-093), qui ne connaît que `repondre_chiffre()`.

Ce qui est délibérément écrit ici, et pourquoi :

- **[CA2] Le gabarit, pas la reformulation.** Les phrases sont des chaînes à
  trous remplies côté Python (`_remplir`, à base de `.replace()` — jamais
  `.format()`, dont les accolades sont un piège dès qu'un gabarit est réutilisé
  dans un prompt). On accepte des phrases moins variées contre une exactitude
  parfaite, une latence nulle et un coût nul.
- **[CA3] Le type d'organe commande la phrase.** Pour une culture
  *reproductrice* (tomate, haricot, courgette — le pied reste en place), le
  rendement cumulé et le nombre de pieds actifs sont deux grandeurs distinctes,
  présentées comme telles ; une cueillette n'y est **jamais** présentée comme
  une diminution de stock. Pour une culture *végétative* (carotte, salade — la
  récolte consomme le pied), le stock diminue bien.
- **[CA4] Une seule vérité chiffrée.** Les agrégations appellent les mêmes
  fonctions de service que les écrans web (`utils/stock.py`,
  `utils/parcelles.py`) et réutilisent leurs formateurs
  (`poids_lisible`, `quantite_lisible`). Recalculer un total « pour le bot »
  créerait une seconde vérité, immédiatement divergente.
- **[CA7] Vide n'est pas zéro.** L'absence de donnée est portée par le champ
  `present` du résultat d'agrégation — dans le *type de retour*, pas seulement
  dans la phrase finale. « Je n'ai aucune récolte de fraises enregistrée » et
  « tu as récolté 0 kg » sont deux réponses différentes ; la confusion ferait
  douter le jardinier de son propre journal.
- **[CA8] Rendre la main plutôt que conclure.** Un résultat absent renvoie
  `present=False` : `app/services/questions.py` le traduit en `confiant=False`,
  et la cascade d'US-093 remonte d'un étage — sans qu'aucun appel modèle n'ait
  été payé pour le constater.
- **[CA9, CA10, CA11] Les garde-fous ne sont pas ici.** Ils sont dans
  `app/services/catalogue_sql.py`, seul point d'exécution autorisé : catalogue
  fermé, lecture seule, délai maximal, `potager_id` vérifié à l'exécution.

[CA1] Familles couvertes, toutes sans appel modèle : total récolté par culture et
par période · dernière occurrence d'un type d'action · stock courant · nombre de
pieds actifs · rendement cumulé de la saison · contenu de la pépinière ·
occupation d'une parcelle.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date as _date, datetime
from typing import Callable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session
from unidecode import unidecode

from app.services import catalogue_sql
from app.services.catalogue_sql import GardeCatalogueError
from app.services.context import TenantContext
from database.db import SessionLocal
from database.models import Evenement
from utils import parcelles as _parcelles
from utils import stock as _stock
from utils.actions import ACTION_MAP
from utils.culture_resolve import cultures_connues

log = logging.getLogger("potager")

# Deux plafonds, parce qu'il y a deux publics — les confondre revenait à
# amputer la réponse du jardinier pour un budget de jetons qui ne le concerne pas.
#
# [Affichage] Ce que le jardinier lit. Il a demandé sa pépinière : il doit voir
# sa pépinière, comme la PWA la lui montre. Le plafond ne protège que de la
# limite de 4 096 caractères d'un message Telegram — et quand il joue, la
# réponse le DIT (« … et 19 autres »), au lieu de laisser croire à une liste
# complète qui contredirait le nombre annoncé juste au-dessus.
MAX_LIGNES_AFFICHEES = 25

# [CA5] Ce qui descend à l'étage de raisonnement, quand un habillage en langage
# naturel est nécessaire : un résumé déjà agrégé, très en deçà de 1 000 jetons.
MAX_LIGNES_RESUME = 8

# Libellé et genre de chaque action canonique : un gabarit doit produire du
# français correct (« dernier semis », « dernière récolte »), sans quoi la
# réponse déterministe sonne moins juste que la reformulation qu'elle remplace.
LIBELLES_ACTION: dict[str, tuple[str, str]] = {
    "recolte": ("récolte", "f"), "semis": ("semis", "m"),
    "plantation": ("plantation", "f"), "arrosage": ("arrosage", "m"),
    "desherbage": ("désherbage", "m"), "paillage": ("paillage", "m"),
    "amendement": ("amendement", "m"), "taille": ("taille", "f"),
    "tuteurage": ("tuteurage", "m"), "traitement": ("traitement", "m"),
    "protection": ("protection", "f"), "observation": ("observation", "f"),
    "perte": ("perte", "f"), "mise_en_godet": ("mise en godet", "f"),
    "vendu": ("vente", "f"), "perte_godet": ("perte en pépinière", "f"),
}

MOIS: dict[str, int] = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "decembre": 12,
}


# ═════════════════════════════════════════════════════════════════════════════
# Les gabarits [CA2] — des chaînes à trous, remplies côté Python
# ═════════════════════════════════════════════════════════════════════════════
GABARITS: dict[str, str] = {
    # Total récolté par culture et par période
    "total_recolte":            "Tu as récolté {total} de {culture} {periode} ({nb}).",
    "total_recolte_vide":       "Je n'ai aucune récolte de {culture} enregistrée {periode}.",

    # Dernière occurrence d'un type d'action
    "derniere_occurrence":      "{dernier} {action} de {culture} : le {date}{quantite}.",
    "derniere_occurrence_sans_culture": "{dernier} {action} : le {date}{culture_citee}{quantite}.",
    "derniere_occurrence_vide": "Je n'ai {aucun} {action} de {culture} enregistré{e}.",
    "derniere_occurrence_vide_sans_culture": "Je n'ai {aucun} {action} enregistré{e}.",

    # Stock courant — végétatif : la récolte consomme le pied [CA3]
    "stock_vegetatif":          "Il te reste {stock} {unite} de {culture} (planté {plantes}{details}).",
    # Stock courant — reproducteur : la cueillette ne diminue rien [CA3]
    "stock_reproducteur":       "Côté {culture} : {pieds} {unite} toujours en place — la cueillette ne les diminue pas. Rendement cumulé : {rendement}.",
    "stock_vide":               "Je n'ai aucun pied de {culture} enregistré dans ce potager.",

    # Nombre de pieds actifs
    "pieds_actifs":             "{pieds} {unite} de {culture} sont en place aujourd'hui (planté {plantes}{details}).",

    # Rendement cumulé de la saison — les deux grandeurs restent distinctes [CA3]
    "rendement_reproducteur":   "Rendement cumulé de {culture} {periode} : {rendement} ({nb}). Et {pieds} {unite} sont toujours en place.",
    "rendement_vegetatif":      "Récolte cumulée de {culture} {periode} : {rendement} ({nb}). Il te reste {pieds} {unite}.",
    "rendement_vide":           "Je n'ai aucune récolte de {culture} enregistrée {periode}.",

    # Rendement de la saison, toutes cultures confondues
    "rendement_global":         "Rendement cumulé {periode} : {total} au total.\n{lignes}",
    "rendement_global_vide":    "Je n'ai aucune récolte pesée enregistrée {periode}.",

    # Stock courant, toutes cultures confondues
    "stock_global":             "Ton stock actuel :\n{lignes}",
    "stock_global_vide":        "Je n'ai aucune culture en place enregistrée dans ce potager.",

    # Contenu de la pépinière
    "pepiniere":                "Ta pépinière contient {nb} lot(s) de semis :\n{lignes}",
    "pepiniere_vide":           "Je n'ai aucun lot de semis en pépinière enregistré.",

    # Parcelles libres — la place disponible pour la prochaine culture
    "parcelles_libres":         "{nb} parcelle(s) libre(s) sur {total} :\n{lignes}",
    "parcelles_libres_aucune":  "Aucune parcelle libre : tes {total} parcelles sont toutes occupées.",

    # Occupation d'une parcelle
    "occupation":               "La parcelle {parcelle} accueille :\n{lignes}",
    "occupation_vide":          "Je n'ai aucune culture en place enregistrée sur la parcelle {parcelle}.",
}


def _remplir(gabarit: str, valeurs: dict[str, str]) -> str:
    """[CA2] Remplit un gabarit par substitution littérale. `.replace()` et
    jamais `.format()` : les gabarits sont susceptibles d'être réutilisés dans
    un prompt, où une accolade non doublée casse le rendu (invariant projet)."""
    texte = gabarit
    for cle, valeur in valeurs.items():
        texte = texte.replace("{" + cle + "}", str(valeur))
    return re.sub(r"\s+([.,])", r"\1", texte).replace("  ", " ").strip()


_MARKDOWN_SENSIBLE = re.compile(r"([*_`\[\]])")


def _sur(valeur: Optional[str]) -> str:
    """Échappe les caractères Markdown d'une valeur venue de la base (nom de
    culture, de variété, de parcelle) — invariant projet sur les sorties du bot."""
    return _MARKDOWN_SENSIBLE.sub(r"\\\1", valeur or "")


_NON_ALPHANUM = re.compile(r"[^a-z0-9]+")


def _normaliser(texte: Optional[str]) -> str:
    """Minuscules, sans accents, ponctuation ramenée à des espaces.

    La dictée vocale ne produit ni apostrophe ni tiret fiables — c'est le constat
    de méthode du §8.4 de `docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md` (« à la
    dictée vocale, le point d'interrogation n'existe pas »). Tous les motifs de
    familles s'écrivent donc en mots séparés, jamais avec de la ponctuation :
    « qu'est-ce qu'il y a » et « qu est ce qu il y a » doivent aiguiller pareil."""
    return _NON_ALPHANUM.sub(" ", unidecode((texte or "").strip().lower())).strip()


# ═════════════════════════════════════════════════════════════════════════════
# Paramètres extraits de la question — déterministe, zéro appel modèle
# ═════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Periode:
    """Fenêtre temporelle demandée. `debut`/`fin` à None = tout l'historique."""

    debut: Optional[_date] = None
    fin: Optional[_date] = None
    libelle: str = "au total"
    annee: Optional[int] = None


@dataclass(frozen=True)
class Parametres:
    question: str
    normalisee: str
    culture: Optional[str] = None
    action: Optional[str] = None
    parcelle: Optional[str] = None
    periode: Periode = field(default_factory=Periode)


def _detecter_periode(normalisee: str, aujourdhui: _date) -> Periode:
    """Détecte une fenêtre temporelle par motifs figés. Aucune interprétation
    hasardeuse : une formulation non reconnue ne restreint rien, plutôt que de
    risquer une réponse fausse sur une période devinée."""
    annee = aujourdhui.year

    correspondance = re.search(r"\ben (20\d{2})\b", normalisee)
    if correspondance:
        cible = int(correspondance.group(1))
        return Periode(_date(cible, 1, 1), _date(cible, 12, 31), f"en {cible}", cible)

    if re.search(r"\bl'?an(nee)? derniere?\b|\bl an derniere?\b|\bannee derniere\b", normalisee):
        cible = annee - 1
        return Periode(_date(cible, 1, 1), _date(cible, 12, 31), "l'an dernier", cible)

    saisons = {
        "printemps": (3, 1, 5, 31, "ce printemps"),
        "ete": (6, 1, 8, 31, "cet été"),
        "automne": (9, 1, 11, 30, "cet automne"),
    }
    for mot, (m1, j1, m2, j2, libelle) in saisons.items():
        if re.search(rf"\bcet?t?e? {mot}\b|\bdu {mot}\b|\bde l ?{mot}\b", normalisee):
            return Periode(_date(annee, m1, j1), _date(annee, m2, j2), libelle, annee)

    if re.search(r"\bcet hiver\b", normalisee):
        return Periode(_date(annee - 1, 12, 1), _date(annee, 2, 28), "cet hiver", annee)

    if re.search(r"\bce mois\b|\bce mois ci\b", normalisee):
        debut = _date(annee, aujourdhui.month, 1)
        return Periode(debut, aujourdhui, "ce mois-ci", annee)

    for nom_mois, numero in MOIS.items():
        if re.search(rf"\ben {nom_mois}\b|\bau mois de {nom_mois}\b|\bde {nom_mois}\b", normalisee):
            dernier_jour = 31 if numero in (1, 3, 5, 7, 8, 10, 12) else (30 if numero != 2 else 28)
            return Periode(_date(annee, numero, 1), _date(annee, numero, dernier_jour), f"en {nom_mois}", annee)

    # Même fenêtre, deux libellés : le jardinier qui dit « la saison » doit se
    # voir répondre « cette saison », pas « cette année ». La fenêtre reste
    # l'année civile — c'est celle sur laquelle le web agrège déjà.
    # « la saison » seul est volontairement absent : « la saison passée » ne
    # désigne pas la saison en cours, et une fenêtre devinée à l'envers vaut
    # moins qu'une absence de fenêtre.
    if re.search(r"\bcette saison\b|\bde la saison\b", normalisee):
        return Periode(_date(annee, 1, 1), _date(annee, 12, 31), "cette saison", annee)

    if re.search(r"\bcette annee\b|\bde l annee\b", normalisee):
        return Periode(_date(annee, 1, 1), _date(annee, 12, 31), "cette année", annee)

    return Periode()


def _detecter_dans(normalisee: str, candidats: list[str]) -> Optional[str]:
    """Retourne le candidat le plus long dont le nom normalisé apparaît dans la
    question — le plus long d'abord, pour que « chou de Bruxelles » l'emporte
    sur « chou »."""
    meilleur: Optional[str] = None
    for candidat in candidats:
        normalise = _normaliser(candidat)
        if not normalise:
            continue
        if re.search(rf"\b{re.escape(normalise)}", normalisee):
            if meilleur is None or len(normalise) > len(_normaliser(meilleur)):
                meilleur = candidat
    return meilleur


def _detecter_action(normalisee: str) -> Optional[str]:
    """Reconnaît un type d'action canonique à partir des synonymes déjà
    référencés dans `utils/actions.ACTION_MAP` — pas de second référentiel."""
    meilleure: Optional[tuple[str, int]] = None
    for canonique, synonymes in ACTION_MAP.items():
        for synonyme in synonymes:
            normalise = _normaliser(synonyme)
            if len(normalise) < 4:
                continue
            if re.search(rf"\b{re.escape(normalise)}", normalisee):
                if meilleure is None or len(normalise) > meilleure[1]:
                    meilleure = (canonique, len(normalise))
    return meilleure[0] if meilleure else None


# Mots qui, dans une question, annoncent un nom de parcelle. « planche »,
# « carré » et « butte » figurent souvent DANS le nom lui-même
# (« test-planche-nord ») : ils servent alors de point d'ancrage, pas de filtre.
_DESIGNATEURS_PARCELLE = (
    "parcelle", "parcelles", "planche", "carre", "carreau", "zone", "butte", "bac", "serre",
)

# Mots qui suivent parfois le désignateur sans faire partie du nom.
_MOTS_VIDES_PARCELLE = frozenset({"la", "le", "les", "de", "du", "des", "ma", "mon", "mes", "l"})


def _detecter_parcelle(db: Session, ctx: TenantContext, normalisee: str) -> Optional[str]:
    """Résout la parcelle désignée dans la question.

    Le jardinier dit « la parcelle nord » alors que la parcelle s'appelle
    « test-planche-nord » : chercher le nom complet dans la phrase ne trouve
    rien. On reprend donc la stratégie déjà en place dans le projet
    (`utils/parcelles.resolve_parcelle`, `utils/culture_resolve`) — nom exact,
    puis Levenshtein ≤ 2, puis sous-chaîne — appliquée aux mots qui suivent un
    désignateur de parcelle.

    **Une désignation ambiguë n'est jamais tranchée au hasard** : si plusieurs
    parcelles correspondent (« la parcelle test » quand trois noms commencent
    par « test »), la fonction rend `None` et la cascade reprend la main. Une
    réponse exacte sur la mauvaise parcelle serait pire qu'une non-réponse.
    """
    parcelles = _parcelles.get_all_parcelles(db, potager_id=ctx.potager_id)
    if not parcelles:
        return None

    # 1. Le nom complet apparaît tel quel dans la question — cas le plus sûr.
    complet = _detecter_dans(normalisee, [p.nom for p in parcelles])
    if complet:
        return complet

    # 2. Les mots qui suivent un désignateur, du plus long au plus court.
    mots = normalisee.split()
    candidats: list[str] = []
    for indice, mot in enumerate(mots):
        if mot not in _DESIGNATEURS_PARCELLE:
            continue
        suite = [m for m in mots[indice + 1:indice + 4] if m not in _MOTS_VIDES_PARCELLE]
        for longueur in range(len(suite), 0, -1):
            candidats.append("".join(suite[:longueur]))
    if not candidats:
        return None

    index = {_parcelles.normalize_parcelle_name(p.nom): p.nom for p in parcelles}
    for candidat in candidats:
        if candidat in index:
            return index[candidat]
        proches = [
            nom for cle, nom in index.items()
            if _parcelles.levenshtein_distance(cle, candidat) <= 2
        ]
        if len(proches) == 1:
            return proches[0]
        contenus = [nom for cle, nom in index.items() if candidat and candidat in cle]
        if len(contenus) == 1:
            return contenus[0]
        if len(contenus) > 1:
            log.info(
                "🪧 PARCELLE AMBIGUË │ '%s' correspond à %d parcelles — aucune supposition",
                candidat, len(contenus),
            )
            return None
    return None


def _extraire_parametres(db: Session, ctx: TenantContext, question: str) -> Parametres:
    normalisee = _normaliser(question)
    cultures = cultures_connues(db, ctx.potager_id)
    return Parametres(
        question=question,
        normalisee=normalisee,
        culture=_detecter_dans(normalisee, cultures),
        action=_detecter_action(normalisee),
        parcelle=_detecter_parcelle(db, ctx, normalisee),
        periode=_detecter_periode(normalisee, _date.today()),
    )


# ═════════════════════════════════════════════════════════════════════════════
# Le catalogue d'agrégations [CA9] — toutes paramétrées, toutes scopées
# ═════════════════════════════════════════════════════════════════════════════
def _bornes(periode: Periode) -> tuple[Optional[datetime], Optional[datetime]]:
    debut = datetime(periode.debut.year, periode.debut.month, periode.debut.day) if periode.debut else None
    fin = datetime(periode.fin.year, periode.fin.month, periode.fin.day, 23, 59, 59) if periode.fin else None
    return debut, fin


@catalogue_sql.enregistrer("total_recolte")
def _agreger_total_recolte(db: Session, ctx: TenantContext, culture: str, periode: Periode) -> dict:
    """Total récolté d'une culture sur une période. Poids et pièces restent dans
    deux pools distincts, comme dans `utils/stock.py` — 3 kg et 4 pieds ne
    s'additionnent pas."""
    debut, fin = _bornes(periode)
    requete = (
        db.query(Evenement.unite, func.count(Evenement.id), func.sum(Evenement.quantite))
        .filter(
            Evenement.potager_id == ctx.potager_id,
            Evenement.type_action == "recolte",
            func.lower(Evenement.culture) == culture.lower(),
        )
    )
    if debut is not None:
        requete = requete.filter(Evenement.date >= debut)
    if fin is not None:
        requete = requete.filter(Evenement.date <= fin)
    lignes = requete.group_by(Evenement.unite).all()

    poids_g, pieces, nb = 0.0, 0.0, 0
    unite_pieces = ""
    for unite, compte, total in lignes:
        nb += compte or 0
        unite_normalisee = (unite or "").lower()
        if unite_normalisee in _stock.UNITES_POIDS_EN_G:
            poids_g += (total or 0.0) * _stock.UNITES_POIDS_EN_G[unite_normalisee]
        else:
            pieces += total or 0.0
            unite_pieces = unite or "pièces"
    return {
        "present": nb > 0,
        # Le libellé de période voyage AVEC l'agrégat : le rendu ne le redevine
        # pas depuis la question, il restitue exactement la fenêtre interrogée.
        "periode": periode.libelle,
        "nb": nb,
        "poids_g": poids_g,
        "pieces": pieces,
        "unite_pieces": unite_pieces,
    }


@catalogue_sql.enregistrer("derniere_occurrence")
def _agreger_derniere_occurrence(
    db: Session, ctx: TenantContext, action: str, culture: Optional[str]
) -> dict:
    """Dernière occurrence d'un type d'action, éventuellement pour une culture."""
    requete = db.query(Evenement).filter(
        Evenement.potager_id == ctx.potager_id,
        Evenement.type_action == action,
    )
    if culture:
        requete = requete.filter(func.lower(Evenement.culture) == culture.lower())
    evenement = requete.order_by(Evenement.date.desc().nullslast(), Evenement.id.desc()).first()
    if evenement is None:
        return {"present": False}
    return {
        "present": True,
        "date": evenement.date,
        "culture": evenement.culture,
        "variete": evenement.variete,
        "quantite": evenement.quantite,
        "unite": evenement.unite,
    }


@catalogue_sql.enregistrer("stock_culture")
def _agreger_stock_culture(db: Session, ctx: TenantContext, culture: str) -> dict:
    """Stock courant, pieds actifs et rendement d'une culture — lus par la même
    fonction de service que /stats et que l'API web [CA4]."""
    stocks = _stock.calcul_stock_cultures(db, potager_id=ctx.potager_id)
    fiche = stocks.get(culture)
    if fiche is None:
        for nom, valeur in stocks.items():
            if nom.lower() == culture.lower():
                fiche = valeur
                break
    if fiche is None:
        return {"present": False}
    return {
        "present": True,
        "culture": fiche.culture,
        "unite": fiche.unite,
        "reproducteur": fiche.is_reproducteur,
        "type_organe": fiche.type_organe,
        "stock": fiche.stock_plants,
        "plantes": fiche.plants_plantes,
        "perdus": fiche.plants_perdus,
        "recoltes_pieces": fiche.recoltes_total,
        "unite_recolte": fiche.unite_recolte,
        "rendement": fiche.rendement_total,
        "unite_rendement": fiche.unite_rendement,
        "nb_recoltes": fiche.nb_recoltes_poids,
    }


@catalogue_sql.enregistrer("rendement_saison")
def _agreger_rendement_saison(
    db: Session, ctx: TenantContext, culture: str, periode: Periode
) -> dict:
    """Rendement cumulé (poids) sur la saison + pieds actifs — deux grandeurs
    distinctes, jamais confondues pour une culture reproductrice [CA3]."""
    total = _agreger_total_recolte(db, ctx, culture=culture, periode=periode)
    fiche = _agreger_stock_culture(db, ctx, culture=culture)
    return {
        "present": total["present"] or fiche["present"],
        "periode": periode.libelle,
        "recolte": total,
        "stock": fiche,
    }


@catalogue_sql.enregistrer("rendement_global")
def _agreger_rendement_global(db: Session, ctx: TenantContext, periode: Periode) -> dict:
    """Rendement cumulé de la saison, toutes cultures confondues — lu par
    `utils/stock.calcul_rendement_mensuel`, la fonction qui alimente déjà la
    courbe de rendement du web [CA4]. Comme elle, ne retient que les récoltes
    **pesées** : additionner des kilos et des pieds ne voudrait rien dire, et
    afficher ici un total que le graphique web n'affiche pas créerait la seconde
    vérité que l'US interdit."""
    annee = periode.annee or _date.today().year
    mesure = _stock.calcul_rendement_mensuel(db, annee, potager_id=ctx.potager_id)
    return {
        "present": bool(mesure["cultures"]),
        "periode": periode.libelle,
        "total_kg": mesure["total_general_kg"],
        "cultures": mesure["cultures"][:MAX_LIGNES_AFFICHEES],
        "nb": len(mesure["cultures"]),
    }


@catalogue_sql.enregistrer("stock_global")
def _agreger_stock_global(db: Session, ctx: TenantContext) -> dict:
    """Stock courant de toutes les cultures en place — même source que /stats."""
    stocks = _stock.calcul_stock_cultures(db, potager_id=ctx.potager_id)
    actives = [fiche for fiche in stocks.values() if fiche.stock_plants > 0]
    actives.sort(key=lambda fiche: fiche.stock_plants, reverse=True)
    return {
        "present": bool(actives),
        "cultures": [
            {
                "culture": fiche.culture,
                "stock": fiche.stock_plants,
                "unite": fiche.unite,
                "reproducteur": fiche.is_reproducteur,
            }
            for fiche in actives[:MAX_LIGNES_AFFICHEES]
        ],
        "nb": len(actives),
    }


@catalogue_sql.enregistrer("pepiniere")
def _agreger_pepiniere(db: Session, ctx: TenantContext) -> dict:
    """Contenu de la pépinière, lot par lot — `utils/stock.calcul_lots_pepiniere`
    (US-065), la même lecture que l'écran pépinière du web [CA4]."""
    lots = _stock.calcul_lots_pepiniere(db, potager_id=ctx.potager_id)
    actifs = [lot for lot in lots if (lot.get("stock_residuel_godet") or 0) > 0
              or (lot.get("graines_en_germination") or 0) > 0]
    return {"present": bool(actifs), "lots": actifs[:MAX_LIGNES_AFFICHEES], "nb": len(actifs)}


@catalogue_sql.enregistrer("parcelles_libres")
def _agreger_parcelles_libres(db: Session, ctx: TenantContext) -> dict:
    """Parcelles de pleine terre sans culture en place — déduites de la même
    occupation que /plan [CA4]. Les pépinières sont exclues : une serre n'est
    pas une place libre pour la prochaine culture, c'est un autre usage.

    `present` est vrai dès que le potager a des parcelles : « aucune parcelle
    libre » est une réponse chiffrée légitime (CA7), pas une absence de donnée.
    Un potager sans aucune parcelle, lui, n'a rien à répondre."""
    occupation = _parcelles.calcul_occupation_parcelles(db, potager_id=ctx.potager_id)
    occupees = {nom for nom, cultures in occupation.items() if nom and cultures}
    pleine_terre = [
        parcelle for parcelle in _parcelles.get_all_parcelles(db, potager_id=ctx.potager_id)
        if not parcelle.est_pepiniere
    ]
    libres = [parcelle.nom for parcelle in pleine_terre if parcelle.nom not in occupees]
    return {
        "present": bool(pleine_terre),
        "total": len(pleine_terre),
        "libres": libres[:MAX_LIGNES_AFFICHEES],
        "nb": len(libres),
    }


@catalogue_sql.enregistrer("occupation_parcelle")
def _agreger_occupation_parcelle(db: Session, ctx: TenantContext, parcelle: str) -> dict:
    """Occupation d'une parcelle — `utils/parcelles.calcul_occupation_parcelles`,
    la fonction qui alimente déjà /plan et l'écran d'occupation [CA4]."""
    occupation = _parcelles.calcul_occupation_parcelles(db, potager_id=ctx.potager_id)
    entrees: list[dict] = []
    for nom, cultures in occupation.items():
        if nom and _normaliser(nom) == _normaliser(parcelle):
            entrees = list(cultures)
            break
    return {
        "present": bool(entrees),
        "parcelle": parcelle,
        "entrees": entrees[:MAX_LIGNES_AFFICHEES],
        "nb": len(entrees),
    }


# ═════════════════════════════════════════════════════════════════════════════
# Le rendu — un agrégat, un gabarit [CA2, CA3, CA7]
# ═════════════════════════════════════════════════════════════════════════════
def _formater_recolte(agregat: dict) -> str:
    """Poids et pièces côte à côte, avec les arrondis de `utils/stock.py` [CA4]."""
    morceaux: list[str] = []
    if agregat["poids_g"]:
        valeur, unite = _stock.poids_lisible(agregat["poids_g"])
        morceaux.append(f"{valeur:g} {unite}")
    if agregat["pieces"]:
        unite = agregat["unite_pieces"] or "pièces"
        morceaux.append(f"{_stock.quantite_lisible(agregat['pieces'], unite):g} {unite}")
    return " et ".join(morceaux) if morceaux else "0"


def _lignes_avec_reste(lignes: list[str], total: int) -> str:
    """Assemble une liste et, si elle est tronquée, annonce ce qui manque.
    Une liste amputée en silence contredirait le nombre annoncé juste au-dessus
    et ferait douter le jardinier de son propre journal — le même principe que
    le CA7 sur les résultats vides."""
    reste = total - len(lignes)
    if reste > 0:
        lignes = lignes + [f"  … et {reste} autre(s), tout est dans l'application"]
    return "\n".join(lignes)


def _fois(nb: int) -> str:
    return "1 récolte" if nb == 1 else f"{nb} récoltes"


def _details_stock(agregat: dict) -> str:
    unite = agregat["unite"]
    details: list[str] = []
    if agregat["perdus"]:
        details.append(f"perdu {_stock.quantite_lisible(agregat['perdus'], unite):g}")
    if agregat["recoltes_pieces"] and not agregat["reproducteur"]:
        # L'unité du pool « pièces » peut différer de celle du stock (5 m² semés,
        # 15 pieds récoltés — cas d'unités incompatibles tranché par US-037/CA2).
        # Le CHIFFRE reste celui qu'affiche /stats (CA4) ; on nomme seulement son
        # unité, sans quoi « récolté 15 » se lirait « 15 m² ».
        unite_recolte = agregat.get("unite_recolte") or unite
        valeur = _stock.quantite_lisible(agregat["recoltes_pieces"], unite_recolte)
        details.append(f"récolté {valeur:g} {unite_recolte}".strip())
    return (", " + ", ".join(details)) if details else ""


def _rendu_total_recolte(params: Parametres, agregat: dict) -> str:
    valeurs = {"culture": _sur(params.culture), "periode": agregat["periode"]}
    if not agregat["present"]:
        return _remplir(GABARITS["total_recolte_vide"], valeurs)
    valeurs |= {"total": _formater_recolte(agregat), "nb": _fois(agregat["nb"])}
    return _remplir(GABARITS["total_recolte"], valeurs)


def _rendu_derniere_occurrence(params: Parametres, agregat: dict) -> str:
    libelle, genre = LIBELLES_ACTION.get(params.action or "", (params.action or "action", "f"))
    accords = {
        "dernier": "Dernier" if genre == "m" else "Dernière",
        "aucun": "aucun" if genre == "m" else "aucune",
        "e": "" if genre == "m" else "e",
    }
    if not agregat["present"]:
        if not params.culture:
            return _remplir(GABARITS["derniere_occurrence_vide_sans_culture"],
                            accords | {"action": libelle})
        return _remplir(
            GABARITS["derniere_occurrence_vide"],
            accords | {"action": libelle, "culture": _sur(params.culture)},
        )
    date_evenement = agregat["date"]
    quantite = ""
    if agregat["quantite"]:
        unite = agregat["unite"] or ""
        quantite = f" — {agregat['quantite']:g} {unite}".rstrip()
    valeurs = accords | {
        "action": libelle,
        "date": date_evenement.strftime("%d/%m/%Y") if date_evenement else "date inconnue",
        "quantite": quantite,
    }
    if params.culture:
        return _remplir(GABARITS["derniere_occurrence"], valeurs | {"culture": _sur(params.culture)})
    citee = f" ({_sur(agregat['culture'])})" if agregat.get("culture") else ""
    return _remplir(GABARITS["derniere_occurrence_sans_culture"], valeurs | {"culture_citee": citee})


def _rendu_stock(params: Parametres, agregat: dict) -> str:
    if not agregat["present"]:
        return _remplir(GABARITS["stock_vide"], {"culture": _sur(params.culture)})
    unite = agregat["unite"]
    commun = {
        "culture": _sur(agregat["culture"]),
        "unite": unite,
        "plantes": f"{_stock.quantite_lisible(agregat['plantes'], unite):g}",
        "details": _details_stock(agregat),
    }
    if agregat["reproducteur"]:
        # [CA3] Le pied reste en place : jamais « il te reste », jamais une
        # cueillette présentée comme une diminution de stock.
        rendement = (
            f"{round(agregat['rendement'], 2):g} {agregat['unite_rendement']}"
            if agregat["rendement"] else "aucune récolte pesée enregistrée"
        )
        return _remplir(GABARITS["stock_reproducteur"], commun | {
            "pieds": f"{_stock.quantite_lisible(agregat['stock'], unite):g}",
            "rendement": rendement,
        })
    return _remplir(GABARITS["stock_vegetatif"], commun | {
        "stock": f"{_stock.quantite_lisible(agregat['stock'], unite):g}",
    })


def _rendu_pieds_actifs(params: Parametres, agregat: dict) -> str:
    if not agregat["present"]:
        return _remplir(GABARITS["stock_vide"], {"culture": _sur(params.culture)})
    unite = agregat["unite"]
    return _remplir(GABARITS["pieds_actifs"], {
        "pieds": f"{_stock.quantite_lisible(agregat['stock'], unite):g}",
        "unite": unite,
        "culture": _sur(agregat["culture"]),
        "plantes": f"{_stock.quantite_lisible(agregat['plantes'], unite):g}",
        "details": _details_stock(agregat),
    })


def _rendu_rendement(params: Parametres, agregat: dict) -> str:
    recolte, fiche = agregat["recolte"], agregat["stock"]
    if not recolte["present"]:
        return _remplir(
            GABARITS["rendement_vide"],
            {"culture": _sur(params.culture), "periode": agregat["periode"]},
        )
    unite = fiche.get("unite", "plants")
    valeurs = {
        "culture": _sur(params.culture),
        "periode": agregat["periode"],
        "rendement": _formater_recolte(recolte),
        "nb": _fois(recolte["nb"]),
        "pieds": f"{_stock.quantite_lisible(fiche.get('stock', 0.0), unite):g}",
        "unite": unite,
    }
    # [CA3] Reproducteur : rendement cumulé ET pieds en place, séparément.
    gabarit = "rendement_reproducteur" if fiche.get("reproducteur") else "rendement_vegetatif"
    return _remplir(GABARITS[gabarit], valeurs)


def _rendu_rendement_global(params: Parametres, agregat: dict) -> str:
    if not agregat["present"]:
        return _remplir(GABARITS["rendement_global_vide"], {"periode": agregat["periode"]})
    lignes = [
        f"  • {_sur(entree['culture'])} — {entree['total']:g} {entree['unite']}"
        for entree in agregat["cultures"]
    ]
    return _remplir(GABARITS["rendement_global"], {
        "periode": agregat["periode"],
        "total": f"{agregat['total_kg']:g} kg",
        "lignes": _lignes_avec_reste(lignes, agregat["nb"]),
    })


def _rendu_stock_global(params: Parametres, agregat: dict) -> str:
    if not agregat["present"]:
        return GABARITS["stock_global_vide"]
    lignes = []
    for entree in agregat["cultures"]:
        unite = entree["unite"]
        quantite = f"{_stock.quantite_lisible(entree['stock'], unite):g} {unite}"
        # [CA3] « en place » pour une reproductrice — sa cueillette ne diminue
        # rien ; « restants » pour une végétative, dont la récolte consomme le pied.
        etat = "en place" if entree["reproducteur"] else "restants"
        lignes.append(f"  • {_sur(entree['culture'])} — {quantite} {etat}")
    return _remplir(GABARITS["stock_global"], {"lignes": _lignes_avec_reste(lignes, agregat["nb"])})


def _rendu_pepiniere(params: Parametres, agregat: dict) -> str:
    if not agregat["present"]:
        return GABARITS["pepiniere_vide"]
    lignes = []
    for lot in agregat["lots"]:
        variete = f" {_sur(lot.get('variete'))}" if lot.get("variete") else ""
        date_semis = lot.get("date_semis")
        # Un lot « sans semis rattaché » (US-065) n'a pas de date : le dire ainsi
        # plutôt que d'afficher « semé le date inconnue ».
        semis = f"semé le {date_semis.strftime('%d/%m/%Y')}" if date_semis else "sans semis rattaché"
        lignes.append(
            f"  • {_sur(lot.get('culture'))}{variete} — {semis}, "
            f"{int(lot.get('stock_residuel_godet') or 0)} plant(s) en godet, "
            f"{int(lot.get('graines_en_germination') or 0)} graine(s) en germination"
        )
    return _remplir(GABARITS["pepiniere"], {
        "nb": agregat["nb"], "lignes": _lignes_avec_reste(lignes, agregat["nb"]),
    })


def _rendu_parcelles_libres(params: Parametres, agregat: dict) -> str:
    if not agregat["present"]:
        return "Je n'ai aucune parcelle enregistrée dans ce potager."
    if not agregat["nb"]:
        return _remplir(GABARITS["parcelles_libres_aucune"], {"total": agregat["total"]})
    lignes = _lignes_avec_reste([f"  • {_sur(nom)}" for nom in agregat["libres"]], agregat["nb"])
    return _remplir(GABARITS["parcelles_libres"], {
        "nb": agregat["nb"], "total": agregat["total"], "lignes": lignes,
    })


def _rendu_occupation(params: Parametres, agregat: dict) -> str:
    if not agregat["present"]:
        return _remplir(GABARITS["occupation_vide"], {"parcelle": _sur(agregat["parcelle"])})
    lignes = []
    for entree in agregat["entrees"]:
        variete = f" {_sur(entree.get('variete'))}" if entree.get("variete") else ""
        unite = entree.get("unite") or "plants"
        lignes.append(
            f"  • {_sur(entree.get('culture'))}{variete} — "
            f"{_stock.quantite_lisible(entree.get('nb_plants') or 0, unite):g} {unite}"
        )
    return _remplir(
        GABARITS["occupation"],
        {"parcelle": _sur(agregat["parcelle"]), "lignes": _lignes_avec_reste(lignes, agregat["nb"])},
    )


# ═════════════════════════════════════════════════════════════════════════════
# Les familles de questions [CA1] — l'ajout d'une famille tient en une ligne
# ═════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Famille:
    """Une famille de question : le motif qui la reconnaît, l'agrégation du
    catalogue qui la sert, le gabarit qui la formule."""

    nom: str
    agregation: str
    motif: re.Pattern
    exige: tuple[str, ...]
    arguments: Callable[[Parametres], dict]
    rendu: Callable[[Parametres, dict], str]
    # Motif de disqualification : ce qui, s'il apparaît, retire la question à
    # cette famille même si `motif` a matché. Sert aux familles volontairement
    # larges, qui doivent rendre la main plutôt que servir un chiffre à une
    # question qui n'en attend pas.
    exclut: Optional[re.Pattern] = None


FAMILLES: tuple[Famille, ...] = (
    Famille(
        nom="pepiniere",
        agregation="pepiniere",
        motif=re.compile(r"\bpepiniere\b|\ben godet\b|\bmes godets\b|\bsemis en cours\b"),
        exige=(),
        arguments=lambda p: {},
        rendu=_rendu_pepiniere,
    ),
    Famille(
        nom="parcelles_libres",
        agregation="parcelles_libres",
        motif=re.compile(
            r"\bparcelles? (?:vides?|libres?|disponibles?)\b|"
            r"\bparcelles? (?:sont )?(?:vides?|libres?)\b|\bplace (?:libre|disponible)\b|"
            r"\bde (?:la )?place\b|\bou (?:puis je|je peux) planter\b"
        ),
        exige=(),
        arguments=lambda p: {},
        rendu=_rendu_parcelles_libres,
    ),
    Famille(
        nom="derniere_occurrence",
        agregation="derniere_occurrence",
        motif=re.compile(
            r"\bquand ai je\b|\bquand j ai\b|\bdernier(?:e|es|s)? \w+|\ba quelle date\b|"
            r"\bderniere fois\b|\bquand est ce que j ai\b"
        ),
        exige=("action",),
        arguments=lambda p: {"action": p.action, "culture": p.culture},
        rendu=_rendu_derniere_occurrence,
    ),
    Famille(
        nom="rendement_saison",
        agregation="rendement_saison",
        motif=re.compile(r"\brendement\b|\bou en sont\b|\bou en est\b|\bproduction de\b|\bproduit\b"),
        exige=("culture",),
        arguments=lambda p: {"culture": p.culture, "periode": _periode_saison(p.periode)},
        rendu=_rendu_rendement,
    ),
    Famille(
        nom="rendement_global",
        agregation="rendement_global",
        # « mes récoltes » est volontairement absent : c'est une demande
        # d'historique (« quelles sont mes récoltes ? »), pas de rendement
        # cumulé — l'agent SQL la sert déjà, et mieux.
        motif=re.compile(r"\brendement\b|\bma production\b|\bj ai produit\b"),
        exige=(),
        arguments=lambda p: {"periode": _periode_saison(p.periode)},
        rendu=_rendu_rendement_global,
    ),
    Famille(
        nom="total_recolte",
        agregation="total_recolte",
        motif=re.compile(
            r"\bcombien de .*recolt|\bcombien ai je recolt|\bcombien j ai recolt|"
            r"\btotal .*recolt|\brecolte totale\b|\bcombien .*cueilli"
        ),
        exige=("culture",),
        arguments=lambda p: {"culture": p.culture, "periode": p.periode},
        rendu=_rendu_total_recolte,
    ),
    Famille(
        nom="pieds_actifs",
        agregation="stock_culture",
        motif=re.compile(
            r"\bpieds? (?:actifs?|en place|vivants?|encore)\b|\bcombien de pieds?\b|"
            r"\bcombien de plants?\b|\bplants? en place\b"
        ),
        exige=("culture",),
        arguments=lambda p: {"culture": p.culture},
        rendu=_rendu_pieds_actifs,
    ),
    Famille(
        nom="stock_courant",
        agregation="stock_culture",
        motif=re.compile(
            r"\bil me reste\b|\bcombien me reste\b|\bstock de\b|\bmon stock\b|\bmes stocks\b|"
            r"\breste t il\b|\bj en ai combien\b"
        ),
        exige=("culture",),
        arguments=lambda p: {"culture": p.culture},
        rendu=_rendu_stock,
    ),
    Famille(
        nom="stock_global",
        agregation="stock_global",
        motif=re.compile(
            r"\bmon stock\b|\bmes stocks\b|\bquel est mon stock\b|\betat du stock\b|"
            r"\bce qu il me reste\b|\bqu est ce qu il me reste\b"
        ),
        exige=(),
        arguments=lambda p: {},
        rendu=_rendu_stock_global,
    ),
    Famille(
        # En DERNIER, et volontairement large : dès qu'une parcelle est nommée
        # et qu'aucune famille plus précise n'explique la question, le sens
        # attendu est « ce qu'il y a dessus ».
        #
        # Le motif ne cherche plus une tournure interrogative exacte
        # (« qu'est-ce qu'il y a… ») : la dictée vocale et la frappe au pouce
        # produisent « sur ma parcelle nord », « u'est ce qu'il y a » — des
        # formes qu'aucune liste littérale ne rattrapera jamais toutes. Ce qui
        # identifie la question, c'est la parcelle résolue, pas la grammaire.
        nom="occupation_parcelle",
        agregation="occupation_parcelle",
        motif=re.compile(r"\b(?:parcelles?|planches?|carre|carreau|zone|butte|bac)\b"),
        # …mais une question de savoir ou de conseil qui mentionne une parcelle
        # n'attend pas un inventaire : elle rend la main à la cascade.
        exclut=re.compile(
            r"\bpourquoi\b|\bcomment\b|\bfaut il\b|\bdois je\b|\bque faire\b|"
            r"\bconseil\b|\bpenses tu\b|\ba ton avis\b|\bmaladie\b|\bpuis je\b"
        ),
        exige=("parcelle",),
        arguments=lambda p: {"parcelle": p.parcelle},
        rendu=_rendu_occupation,
    ),
)


def _periode_saison(periode: Periode) -> Periode:
    """« Rendement cumulé de la saison » : à défaut de période explicite dans la
    question, la saison en cours — et le libellé le dit, pour ne jamais laisser
    croire à un total historique."""
    if periode.debut is not None or periode.fin is not None:
        return periode
    annee = _date.today().year
    return Periode(_date(annee, 1, 1), _date(annee, 12, 31), "cette saison", annee)


def _choisir_famille(params: Parametres) -> Optional[Famille]:
    """Première famille dont le motif matche ET dont les paramètres obligatoires
    ont été extraits. Une famille reconnue sans sa culture (« combien j'ai
    récolté ? ») n'est pas servie approximativement : elle n'est pas servie."""
    for famille in FAMILLES:
        if not famille.motif.search(params.normalisee):
            continue
        if famille.exclut is not None and famille.exclut.search(params.normalisee):
            continue
        if all(getattr(params, nom) for nom in famille.exige):
            return famille
    return None


# ═════════════════════════════════════════════════════════════════════════════
# API publique
# ═════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class ReponseChiffree:
    """Réponse de l'étage 1. `present=False` signale une absence de donnée —
    la phrase reste honnête (CA7) mais la main est rendue à l'étage suivant
    (CA8). `resume` est le seul élément transmissible à un modèle (CA5) : un
    résumé déjà agrégé, jamais une ligne d'événement."""

    texte: str
    famille: str
    present: bool

    @property
    def resume(self) -> str:
        """[CA5] Le texte, ramené à ce qui peut descendre à l'étage de
        raisonnement : les premières lignes et le compte du reste. L'affichage,
        lui, n'est pas amputé pour autant — ce sont deux publics différents."""
        lignes = self.texte.split("\n")
        if len(lignes) <= MAX_LIGNES_RESUME + 1:
            return self.texte
        garde = lignes[:MAX_LIGNES_RESUME + 1]
        garde.append(f"  … et {len(lignes) - len(garde)} autre(s)")
        return "\n".join(garde)


def reconnait_famille(
    ctx: TenantContext, question: str, db: Optional[Session] = None
) -> Optional[str]:
    """Nom de la famille qui saurait servir cette question, ou `None`.

    Reconnaître n'est pas répondre : aucune agrégation n'est exécutée ici, on
    s'arrête à l'extraction des paramètres et au choix de la famille. C'est ce
    qui permet au routeur (US-093) de s'en servir comme d'une règle
    supplémentaire, à coût nul en jetons.

    **Pourquoi le routeur interroge le catalogue plutôt que d'énumérer ses
    propres motifs :** parce que deux listes de motifs, une ici et une là-bas,
    divergent à la première famille ajoutée — et la divergence ne se voit pas,
    elle se paie en appels au modèle. « qu'est-ce que j'ai en parcelle sud ? »
    l'a montré le 26/08/2026 : le catalogue savait répondre, le routeur ne le
    savait pas, et la question a coûté deux appels pour une réponse que le
    gabarit avait déjà produite gratuitement.

    Ne lève jamais : une reconnaissance impossible se lit « je ne reconnais
    pas », et la classification se poursuit normalement.
    """
    session_locale = db is None
    session = db if db is not None else SessionLocal()
    try:
        with catalogue_sql.garde_lecture_seule(session):
            params = _extraire_parametres(session, ctx, question)
        famille = _choisir_famille(params)
        return famille.nom if famille is not None else None
    except Exception as erreur:
        log.debug("GABARIT SQL : reconnaissance impossible (%s)", type(erreur).__name__)
        return None
    finally:
        if session_locale:
            session.close()


def repondre_chiffre(
    ctx: TenantContext, question: str, db: Optional[Session] = None
) -> Optional[ReponseChiffree]:
    """[CA1, CA2] Répond à une question chiffrée par un gabarit, sans aucun appel
    au modèle. Retourne `None` si la question ne relève d'aucune famille du
    catalogue — l'appelant poursuit alors la cascade normalement.

    Un refus de garde (`catalogue_sql.GardeCatalogueError`) n'est jamais
    présenté au jardinier comme une erreur : il est journalisé, et la question
    poursuit la cascade comme si l'étage n'avait pas su répondre. Il en va de
    même pour toute autre erreur d'agrégation : cet étage accélère la cascade,
    il ne doit jamais l'interrompre.
    """
    session_locale = db is None
    session = db if db is not None else SessionLocal()
    try:
        with catalogue_sql.garde_lecture_seule(session):
            params = _extraire_parametres(session, ctx, question)
        famille = _choisir_famille(params)
        if famille is None:
            return None

        agregat = catalogue_sql.executer(
            famille.agregation, session, ctx, **famille.arguments(params)
        )
        texte = famille.rendu(params, agregat)
        log.info(
            "📐 GABARIT SQL     │ famille=%-19s │ donnee=%s │ 0 jeton │ '%s'",
            famille.nom, "oui" if agregat["present"] else "aucune", question[:60],
        )
        return ReponseChiffree(texte=texte, famille=famille.nom, present=bool(agregat["present"]))
    except GardeCatalogueError as erreur:
        catalogue_sql.journaliser_refus(erreur, question)
        return None
    except Exception as erreur:
        # L'étage 1 est une optimisation, jamais un point de défaillance : une
        # base indisponible ou une agrégation en erreur rend la main à la
        # cascade telle qu'elle existait avant cette US, au lieu de faire
        # échouer une réponse que les étages suivants savent encore produire.
        log.warning(
            "⚠️ GABARIT SQL     │ agrégation impossible (%s) → poursuite de la cascade : '%s'",
            type(erreur).__name__, (question or "")[:80],
        )
        return None
    finally:
        if session_locale:
            session.close()

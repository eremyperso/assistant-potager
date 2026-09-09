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
- **[US-095] Une famille est rejouable.** Chaque réponse porte son
  *aiguillage* (`_aiguillage`) — famille, culture, parcelle, dépendances — et
  `servir_aiguillage()` sait le rejouer en recalculant les valeurs. C'est ce
  qui permet au cache de questions de mémoriser une réponse chiffrée sans
  jamais mémoriser un chiffre. Chaque famille déclare aussi les natures de
  donnée dont elle dérive (`dependances`), qui commandent son invalidation.

[CA1] Familles couvertes, toutes sans appel modèle : total récolté par culture et
par période · dernière occurrence d'un type d'action · stock courant · nombre de
pieds actifs · nombre de godets produits [US-170] · rendement cumulé de la
saison · contenu de la pépinière · occupation d'une parcelle · parcelles où une
culture est en place · parcelles portant une famille botanique · notes du jardinier sur une
culture ou une parcelle [US-141].
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

from app.services import bioagresseurs as svc_bioagresseurs
from app.services import catalogue_sql
from app.services import familles as _familles
from app.services import memoire_potager as _memoire
from app.services.catalogue_sql import GardeCatalogueError
from app.services.context import TenantContext
from database.db import SessionLocal
from database.models import Evenement, FamilleBotanique, Parcelle
from llm.routeur import MOTIF_MEMOIRE
from utils import parcelles as _parcelles
from utils import stock as _stock
from utils.actions import ACTION_MAP
from utils.culture_resolve import cultures_connues, normaliser_culture
from utils.dependances_donnee import (
    NATURE_JOURNAL,
    NATURE_PEPINIERE,
    NATURE_PLAN,
    NATURE_RECOLTE,
    NATURE_SEMIS,
    NATURE_STOCK,
)

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

# ─────────────────────────────────────────────────────────────────────────────
# [US-141] La mémoire du potager, servie en SQL — les trois plafonds
# -----------------------------------------------------------------------------
# Décisions PRODUIT, nommées et justifiées plutôt qu'enfouies dans une tranche,
# sur le modèle de `fiche_culture.LIMITE_BIOAGRESSEURS` : elles se révisent sans
# relire le code qui les applique.
# ─────────────────────────────────────────────────────────────────────────────
#: Notes CITÉES en entier dans une réponse. Au-delà, le jardinier ne lit plus,
#: il fait défiler — et ce qu'il cherchait est au milieu. La réponse bascule
#: alors sur des REPÈRES temporels, qui disent où regarder plutôt que de tout
#: dérouler.
LIMITE_NOTES_CITEES = 8

#: Notes citées SOUS des repères : de quoi reconnaître le fil sans le dérouler.
APERCU_NOTES_RECENTES = 3

#: Budget de caractères des notes citées. Telegram REFUSE un message de plus de
#: 4 096 caractères — un refus est une réponse perdue, pas tronquée. Une note
#: pèse jusqu'à `memoire_potager.TAILLE_MAX_FRAGMENT` (900) caractères : huit
#: d'entre elles peuvent dépasser à elles seules. Une note est donc citée
#: ENTIÈRE ou comptée dans le reste — jamais coupée en son milieu, ce qui la
#: citerait de travers.
BUDGET_CARACTERES_NOTES = 3000

#: Les trois niveaux de lecture d'un historique de notes.
ZOOM_DETAIL = "detail"
ZOOM_SAISON = "saison"
ZOOM_ANNEE = "annee"

# [US-141] SAISON AGRONOMIQUE, jamais trimestre calendaire — arbitrage tranché.
#
# Trois raisons, dans l'ordre de leur poids. (1) `_detecter_periode` encode DÉJÀ
# ces quatre fenêtres, parce que c'est le vocabulaire dans lequel les questions
# arrivent ; un découpage par trimestre ferait cohabiter deux vérités
# temporelles dans ce fichier, l'une pour lire les questions, l'autre pour
# écrire les réponses. (2) Un repère n'a d'intérêt que si l'on peut dire
# « montre-moi celui-là » : « ce printemps » et « en 2025 » sont relus tels
# quels, « le T2 » n'est reconnu par rien et le jardinier ne le prononce pas.
# (3) Le trimestre coupe le cycle aux mauvais endroits — janvier-mars mêle le
# cœur de l'hiver et le démarrage des semis.
#
# Seul coût, nommé et payé : l'hiver enjambe l'année civile. Décembre est
# rattaché à l'année de son janvier (d'où le décalage +1), de sorte qu'une note
# du 12/12/2025 et une du 08/01/2026 se lisent ensemble sous « hiver 2026 ».
# C'est le choix que `_detecter_periode` fait déjà pour « cet hiver » : on
# l'aligne, on ne l'invente pas.
SAISONS_AGRONOMIQUES: dict[int, tuple[str, int]] = {
    3: ("printemps", 0), 4: ("printemps", 0), 5: ("printemps", 0),
    6: ("été", 0), 7: ("été", 0), 8: ("été", 0),
    9: ("automne", 0), 10: ("automne", 0), 11: ("automne", 0),
    12: ("hiver", 1), 1: ("hiver", 0), 2: ("hiver", 0),
}

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

    # Nombre de godets produits — distinct du rendement récolté [chantier 3 / US-170]
    "godets_produits":          "Tu as mis en godet {total} plant(s) de {culture} {periode} ({nb}).",
    "godets_produits_vide":     "Je n'ai aucune mise en godet de {culture} enregistrée {periode}.",

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

    # Parcelles où une culture est en place — « où sont mes tomates ? »
    # [US-173 / CA5, CA7] Ce qui attaque une culture. Trois gabarits, parce
    # qu'il y a trois situations distinctes et qu'en confondre deux trompe le
    # jardinier : la liste, l'ignorance sur une culture dont le référentiel a
    # une fiche, et l'absence de fiche pour une culture pourtant cultivée ici.
    "bioagresseurs_culture":        "Sur {culture}, à surveiller :\n{lignes}",
    "bioagresseurs_culture_aucun":  ("Je n'ai aucun bioagresseur rattaché à {culture}. "
                                     "Cela ne veut pas dire que cette culture n'est pas "
                                     "exposée : l'information n'a pas encore été renseignée."),
    "bioagresseurs_culture_sans_fiche": ("Je n'ai pas de fiche de référentiel pour {culture}, "
                                         "donc rien à dire sur ce qui l'attaque. Ce n'est pas "
                                         "un constat d'absence de risque."),

    "parcelles_par_culture":    "Je trouve {culture} sur {nb} parcelle(s) :\n{lignes}",
    "parcelles_par_culture_aucune": "Côté {culture} : aucune parcelle n'en porte en ce moment.",

    # Parcelles portant une famille botanique — le référentiel des familles
    # (US-067/US-166) croisé avec l'occupation qu'affiche déjà /plan
    "parcelles_par_famille":    "{nb} parcelle(s) portent des cultures de la famille {famille} :\n{lignes}",
    "parcelles_par_famille_aucune":   "Aucune parcelle ne porte de culture de la famille {famille} en ce moment. Cultures rattachées : {cultures}.",
    "parcelles_par_famille_inconnue": "Aucune fiche culture n'est rattachée à la famille {famille} — je ne peux pas dire quelles parcelles en portent.",

    # Occupation d'une parcelle
    "occupation":               "La parcelle {parcelle} accueille :\n{lignes}",
    "occupation_vide":          "Je n'ai aucune culture en place enregistrée sur la parcelle {parcelle}.",

    # [US-141 / CA5] La mémoire du potager, quand la question nomme sa cible.
    # Seul l'EN-TÊTE passe par `_remplir` : le corps des notes, jamais — il en
    # ressortirait renormalisé, donc retouché (voir `_bloc_note`).
    "notes_detail":   "📓 Tes notes sur {cible} — {nb}{periode}, de la plus récente à la plus ancienne :",
    "notes_reperes":  "📓 Tes notes sur {cible} — {nb}{periode}, {etendue}. Voici comment elles se répartissent :",
    "notes_apercu":   "Les {apercu} plus récentes :",
    "notes_zoom":     "Dis-moi « mes notes sur {cible} {exemple} » pour lire une période en détail.",
    "notes_vide":     ("Je n'ai aucune note sur {cible} dans ton carnet{periode}. "
                       "Les semis, arrosages et récoltes, eux, se comptent autrement."),
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
    # Famille botanique nommée dans la question (« des solanacées »), résolue
    # contre le référentiel `familles_botaniques` — jamais contre une liste
    # tenue ici, qui divergerait du référentiel au premier import.
    famille_botanique: Optional[str] = None
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


# [US-141] Le zoom EXPLICITEMENT demandé sur un historique de notes.
_MOTIFS_ZOOM: tuple[tuple[str, "re.Pattern[str]"], ...] = (
    (ZOOM_DETAIL, re.compile(r"\ben detail\b|\bdans le detail\b|\btoutes mes notes\b|\bune par une\b|\bla liste complete\b")),
    (ZOOM_SAISON, re.compile(r"\bpar saisons?\b|\bsaison par saison\b")),
    (ZOOM_ANNEE, re.compile(r"\bpar annees?\b|\bpar an\b|\bannee par annee\b")),
)


def _detecter_zoom(normalisee: str) -> Optional[str]:
    """[US-141] Le niveau de lecture demandé par la question, ou `None`.

    `None` n'est pas une valeur par défaut : c'est l'ABSENCE de demande, et c'est
    alors l'ampleur de l'historique qui tranche (`_zoom_effectif`). Deviner ici
    un zoom que le jardinier n'a pas demandé serait le même travers que deviner
    une période — une réponse exacte sur une découpe qu'il n'a pas voulue.

    Volontairement HORS de `Parametres` et hors de l'aiguillage : comme la
    période, il est redérivé de la phrase au moment de servir, si bien que
    « mes notes sur la tomate » et « … par saison » partagent une entrée de
    cache et reçoivent chacune leur réponse.
    """
    for niveau, motif in _MOTIFS_ZOOM:
        if motif.search(normalisee):
            return niveau
    return None


def _saison_de(valeur: datetime) -> tuple[str, int]:
    """(« printemps », 2026) — saison agronomique et année de rattachement."""
    nom, decalage = SAISONS_AGRONOMIQUES[valeur.month]
    return nom, valeur.year + decalage


def _zoom_effectif(demande: Optional[str], nb: int, annees: set[int]) -> str:
    """[US-141] Le niveau auquel l'historique se lit : détail, saison ou année.

    Trois règles, dans cet ordre. Une demande explicite l'emporte toujours. Un
    historique qui tient à l'écran se lit en entier — le repère n'a d'intérêt que
    quand il y a trop à lire. Au-delà, c'est l'ÉTENDUE qui commande : plusieurs
    années se lisent par année, parce que la saison seule y perdrait le fil du
    temps (« printemps » trois fois de suite ne dit pas lesquels) ; une seule
    année se lit par saison, qui est la maille du jardin.
    """
    if demande is not None:
        return demande
    if nb <= LIMITE_NOTES_CITEES:
        return ZOOM_DETAIL
    return ZOOM_ANNEE if len(annees) > 1 else ZOOM_SAISON


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


def _detecter_famille_botanique(db: Session, normalisee: str) -> Optional[str]:
    """Résout la famille botanique nommée dans la question, contre le seul
    référentiel `familles_botaniques` (US-067/US-166).

    Deux tolérances, et deux seulement, parce que la question est dictée : le
    nom scientifique vaut le nom français (« Solanaceae » = « Solanacées »), et
    le singulier vaut le pluriel (« une solanacée » = « des solanacées »).
    L'accord n'a jamais fait partie de la question.

    Retourne toujours le nom du référentiel, pas la forme écrite par le
    jardinier : c'est lui qui sera affiché et lui qui sert de clé.
    """
    candidats: dict[str, str] = {}
    for famille in db.query(FamilleBotanique).all():
        for nom in (famille.nom, famille.nom_scientifique):
            if not nom:
                continue
            candidats.setdefault(nom, famille.nom)
            if nom.lower().endswith("s"):
                candidats.setdefault(nom[:-1], famille.nom)
    trouve = _detecter_dans(normalisee, list(candidats))
    return candidats.get(trouve) if trouve else None


def _extraire_parametres(db: Session, ctx: TenantContext, question: str) -> Parametres:
    normalisee = _normaliser(question)
    cultures = cultures_connues(db, ctx.potager_id)
    return Parametres(
        question=question,
        normalisee=normalisee,
        culture=_detecter_dans(normalisee, cultures),
        action=_detecter_action(normalisee),
        parcelle=_detecter_parcelle(db, ctx, normalisee),
        famille_botanique=_detecter_famille_botanique(db, normalisee),
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


@catalogue_sql.enregistrer("total_mise_en_godet")
def _agreger_total_mise_en_godet(db: Session, ctx: TenantContext, culture: str, periode: Periode) -> dict:
    """[Chantier 3 / US-170] Total de plants mis en godet d'une culture sur une
    période — le nombre de GODETS produits, une grandeur distincte du rendement
    récolté que le motif trop large de `rendement_saison` confondait avec elle
    (« combien de godet de tomate produit cette saison ? » rendait un poids
    récolté). `nb_plants_godets` est le champ dédié de `Evenement`, déjà utilisé
    comme source unique par `utils/stock.calcul_godets` [CA4]."""
    debut, fin = _bornes(periode)
    requete = (
        db.query(func.count(Evenement.id), func.sum(Evenement.nb_plants_godets))
        .filter(
            Evenement.potager_id == ctx.potager_id,
            Evenement.type_action == "mise_en_godet",
            func.lower(Evenement.culture) == culture.lower(),
        )
    )
    if debut is not None:
        requete = requete.filter(Evenement.date >= debut)
    if fin is not None:
        requete = requete.filter(Evenement.date <= fin)
    nb, total = requete.one()
    total = int(total or 0)
    return {
        "present": total > 0,
        "periode": periode.libelle,
        "nb": nb or 0,
        "total": total,
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


@catalogue_sql.enregistrer("bioagresseurs_culture")
def _agreger_bioagresseurs_culture(db: Session, ctx: TenantContext, culture: str) -> dict:
    """[US-173 / CA5, CA7, CA8, CA11] Ce qui attaque une culture — lecture pure
    du référentiel d'US-162, à zéro jeton.

    Délègue à `app.services.bioagresseurs.lire_bioagresseurs`, qui porte déjà
    l'ordre par fréquence, l'isolation par potager et la recomposition
    d'attribution. **Aucune requête n'est réécrite ici** (CA11) : la commande
    `/bioagresseur lister`, cette réponse en langage naturel et la commande
    dictée d'US-172 traversent le même code — trois portes, une seule vérité.

    Trois issues distinctes, jamais confondues :
      - `present=True` + entrées : la liste ;
      - `present=True` sans entrée : la culture a une fiche, aucune arête n'y
        est rattachée — l'application ne sait pas, ce qui n'est pas « rien ne
        l'attaque » (CA12 d'US-162) ;
      - `present=False` : la culture est cultivée ici mais n'a aucune fiche de
        référentiel — troisième situation, troisième message (CA7).
    """
    try:
        trouves = svc_bioagresseurs.lire_bioagresseurs(
            db, culture, potager_id=ctx.potager_id
        )
    except svc_bioagresseurs.CultureInconnueError:
        return {"present": False, "culture": culture, "entrees": [], "nb": 0, "nb_lignes": 0}

    entrees = [
        {
            "nom": b.nom_commun_fr,
            "frequence": b.frequence,
            "periode": b.periode_risque,
            "local": b.local,
        }
        for b in trouves
    ]
    return {
        "present": True,
        "culture": culture,
        "entrees": entrees[:MAX_LIGNES_AFFICHEES],
        "nb": len(entrees),
        "nb_lignes": len(entrees),
    }


@catalogue_sql.enregistrer("notes_du_jardinier")
def _agreger_notes_du_jardinier(
    db: Session,
    ctx: TenantContext,
    culture: Optional[str] = None,
    parcelle: Optional[str] = None,
    periode: Optional[Periode] = None,
    zoom: Optional[str] = None,
) -> dict:
    """[US-141 / CA5] Les notes du jardinier sur une culture ou une parcelle —
    EXHAUSTIVES, de la plus récente à la plus ancienne, à zéro jeton.

    Constaté en production le 09/09/2026 : « qu'avais-je noté sur mes tomates ? »
    partait à la recherche lexicale, qui classe par RESSEMBLANCE et s'arrête à
    trois passages. Elle rendait donc ce qui ressemblait le plus, jamais ce qui
    manquait. Mais la question ne demande aucune ressemblance : elle demande tout
    ce qui a été écrit sur la tomate — une lecture exacte du journal, du même
    ordre qu'un total de récolte, et qui se répond donc ici.

    ⚠️ **Le périmètre des notes n'est PAS défini ici.** Il est lu à
    `app/services/memoire_potager.py` — `TYPE_ACTION_NOTE` et `est_memorisable()`
    — le module qui décide déjà de ce qui entre dans l'INDEX de mémoire. Deux
    définitions de « ce qu'est une note » sont le vrai risque de cette
    correction : le jardinier verrait cette liste et la recherche documentaire
    diverger sur le même carnet, sans qu'aucune des deux ne paraisse fausse. Les
    bulletins météo automatiques, notamment, sont écartés par `est_memorisable()`
    et par elle seule.

    ⚠️ **`memoire_potager.titre_note()` n'est pas appelée**, alors qu'elle
    compose exactement l'en-tête voulu : elle résout la parcelle par
    `db.get(Parcelle, ...)`, une requête sans `potager_id` que le garde
    d'isolation du catalogue refuse à raison (US-096 / CA11). Les noms sont donc
    chargés en une requête filtrée, et l'en-tête recomposé au rendu à partir des
    mêmes briques. La différence porte sur la JOINTURE, jamais sur le contenu.

    [US-096 / CA7] `present` reste vrai dès que la cible est résolue : « je n'ai
    aucune note sur la tomate » est un constat exact tiré du journal, pas une
    absence de donnée — même arbitrage que `parcelles_par_culture`. Faire
    remonter la cascade y substituerait un conseil d'agronomie, c'est-à-dire une
    non-réponse payante à une question dont la réponse était certaine.
    """
    periode = periode or Periode()
    debut, fin = _bornes(periode)

    # Une seule requête, filtrée sur le potager : voir la docstring. Sans
    # `actif` — une note ancienne garde le nom du lieu où elle a été écrite, même
    # si la parcelle a depuis été supprimée (US-009, suppression logique).
    noms_parcelles = {
        p.id: p.nom
        for p in db.query(Parcelle).filter(Parcelle.potager_id == ctx.potager_id).all()
    }

    requete = db.query(Evenement).filter(
        Evenement.potager_id == ctx.potager_id,
        Evenement.type_action == _memoire.TYPE_ACTION_NOTE,
    )
    if culture:
        requete = requete.filter(func.lower(Evenement.culture) == culture.lower())
    if parcelle:
        cibles = [
            pid for pid, nom in noms_parcelles.items()
            if _normaliser(nom) == _normaliser(parcelle)
        ]
        # `[-1]` plutôt qu'un court-circuit : une parcelle nommée mais introuvable
        # doit rendre une liste vide, pas la totalité du carnet.
        requete = requete.filter(Evenement.parcelle_id.in_(cibles or [-1]))
    if debut is not None:
        requete = requete.filter(Evenement.date >= debut)
    if fin is not None:
        requete = requete.filter(Evenement.date <= fin)

    candidats = requete.order_by(Evenement.date.desc(), Evenement.id.desc()).all()
    notes = [e for e in candidats if _memoire.est_memorisable(e)]

    # Les repères se calculent sur L'ENSEMBLE, jamais sur la tranche affichée :
    # un repère tiré des seules notes citées annoncerait ce qu'on montre déjà,
    # au lieu de dire ce qu'on ne montre pas.
    datees = [e for e in notes if e.date]
    annees = {e.date.year for e in datees}
    niveau = _zoom_effectif(zoom, len(notes), annees)
    reperes = _reperes_temporels(datees, niveau)

    plafond = LIMITE_NOTES_CITEES if niveau == ZOOM_DETAIL else APERCU_NOTES_RECENTES
    entrees: list[dict] = []
    budget = BUDGET_CARACTERES_NOTES
    for evenement in notes[:plafond]:
        texte = _memoire.texte_note(evenement)
        # Une note est citée ENTIÈRE ou comptée dans le reste. La première passe
        # toujours : une réponse qui ne citerait rien ne serait pas une réponse.
        if entrees and len(texte) > budget:
            break
        budget -= len(texte)
        entrees.append({
            "date_lisible": _memoire.date_lisible(evenement.date),
            "texte": texte,
            "categorie": _memoire.categorie_note(evenement),
            "parcelle": noms_parcelles.get(evenement.parcelle_id),
            "culture": evenement.culture,
        })

    return {
        "present": True,
        "cible": culture or parcelle,
        "culture": culture,
        "parcelle": parcelle,
        "periode": periode.libelle if (debut or fin) else "",
        "zoom": niveau,
        "nb": len(notes),
        "nb_cites": len(entrees),
        "entrees": entrees,
        "reperes": reperes,
        "etendue": _etendue_lisible(datees),
        "exemple_zoom": _exemple_de_zoom(reperes, niveau),
    }


#: Ordre de lecture des saisons dans une année — celui du jardin, pas l'alphabet.
_ORDRE_SAISON: dict[str, int] = {"hiver": 0, "printemps": 1, "été": 2, "automne": 3}


def _reperes_temporels(datees: list, niveau: str) -> list[dict]:
    """[US-141] Comment un carnet volumineux se répartit dans le temps.

    Par année, chaque année détaillant ses saisons ; ou par saison seule quand
    tout tient dans une année. Vide au niveau `detail`, où les notes sont citées
    une à une et où un repère ne dirait rien de plus.
    """
    if niveau == ZOOM_DETAIL or not datees:
        return []

    groupes: dict[tuple, int] = {}
    saisons: dict[int, dict[str, int]] = {}
    for evenement in datees:
        saison, annee_saison = _saison_de(evenement.date)
        if niveau == ZOOM_ANNEE:
            cle = (evenement.date.year,)
            groupes[cle] = groupes.get(cle, 0) + 1
            par_annee = saisons.setdefault(evenement.date.year, {})
            par_annee[saison] = par_annee.get(saison, 0) + 1
        else:
            cle = (annee_saison, saison)
            groupes[cle] = groupes.get(cle, 0) + 1

    reperes: list[dict] = []
    if niveau == ZOOM_ANNEE:
        for cle in sorted(groupes, reverse=True):
            annee = cle[0]
            # Ordre du TEMPS, pas de la fréquence : tout le reste de la
            # réponse va du plus récent au plus ancien, et un repère qui
            # inverserait cet ordre se lirait comme un classement.
            detail = sorted(
                saisons.get(annee, {}).items(),
                key=lambda kv: _ORDRE_SAISON[kv[0]], reverse=True,
            )
            reperes.append({
                "libelle": str(annee),
                "nb": groupes[cle],
                "detail": ", ".join(f"{nom} {nb}" for nom, nb in detail),
                "zoom": f"en {annee}",
            })
    else:
        ordonnees = sorted(
            groupes, key=lambda c: (c[0], _ORDRE_SAISON[c[1]]), reverse=True
        )
        for cle in ordonnees:
            annee, saison = cle
            reperes.append({
                "libelle": f"{saison} {annee}",
                "nb": groupes[cle],
                "detail": "",
                # Une saison ne se redemande sans ambiguïté que dans l'année en
                # cours (« ce printemps ») ; ailleurs, l'année est le repère que
                # `_detecter_periode` sait relire.
                "zoom": f"en {annee}",
            })
    return reperes


def _etendue_lisible(datees: list) -> str:
    """« de mai 2024 à septembre 2026 » — sur quoi porte le carnet, en un souffle."""
    if len(datees) < 2:
        return ""
    dates = sorted(e.date for e in datees)
    mois = {numero: nom for nom, numero in MOIS.items()}
    debut = f"{mois[dates[0].month]} {dates[0].year}"
    fin = f"{mois[dates[-1].month]} {dates[-1].year}"
    return "" if debut == fin else f"de {debut} à {fin}"


def _exemple_de_zoom(reperes: list[dict], niveau: str) -> str:
    """La période à proposer au jardinier pour lire un repère en détail.

    Le repère le plus fourni, exprimé dans une formulation que `_detecter_periode`
    sait RELIRE (« en 2025 ») : c'est ce qui referme la boucle du zoom sans
    écrire un second analyseur de dates. Une formulation que la question ne
    saurait pas reprendre serait une invitation à une commande qui n'existe pas.
    """
    if niveau == ZOOM_DETAIL or not reperes:
        return ""
    return max(reperes, key=lambda repere: repere["nb"])["zoom"]


@catalogue_sql.enregistrer("parcelles_par_culture")
def _agreger_parcelles_par_culture(db: Session, ctx: TenantContext, culture: str) -> dict:
    """Parcelles où une culture est en place — la question inverse de
    `occupation_parcelle`, sur la même occupation (`utils/parcelles`, CA4).

    [CA7] `present` reste vrai quand la culture n'est nulle part : « aucune
    parcelle ne porte de tomate en ce moment » est un constat EXACT tiré du
    plan, pas une absence de donnée. La culture, elle, n'est reconnue que si
    elle est déjà connue du potager (`cultures_connues`) — le cas « je ne sais
    pas de quelle plante tu parles » ne se pose donc pas ici.
    """
    cible = normaliser_culture(culture)
    occupation = _parcelles.calcul_occupation_parcelles(db, potager_id=ctx.potager_id)
    trouvees = [
        {
            "parcelle": nom_parcelle,
            "variete": entree.get("variete"),
            "nb_plants": entree.get("nb_plants") or 0,
            "unite": entree.get("unite") or "plants",
        }
        for nom_parcelle, entrees in occupation.items()
        for entree in entrees
        if normaliser_culture(entree.get("culture") or "") == cible
    ]
    # La case « non localisé » (parcelle_id nul, CA7 d'US-030) en dernier :
    # elle fait partie de la réponse sans prétendre être une parcelle.
    trouvees.sort(key=lambda e: (e["parcelle"] is None, (e["parcelle"] or "").lower(),
                                 (e["variete"] or "").lower()))
    return {
        "present": True,
        "culture": culture,
        "entrees": trouvees[:MAX_LIGNES_AFFICHEES],
        "nb": len({e["parcelle"] for e in trouvees}),
        "nb_lignes": len(trouvees),
    }


@catalogue_sql.enregistrer("parcelles_par_famille")
def _agreger_parcelles_par_famille(
    db: Session, ctx: TenantContext, famille_botanique: str
) -> dict:
    """Parcelles portant, en ce moment, une culture d'une famille botanique.

    [CA4] Deux vérités se rencontrent ici, et aucune n'est recalculée pour le
    bot : l'occupation vient de `utils/parcelles.calcul_occupation_parcelles`
    (celle de /plan), le rattachement culture → famille vient de
    `app/services/familles.familles_par_culture` (celui des fiches culture,
    US-067).

    [CA7] `present` sépare deux « rien » qui se ressemblent et ne se valent
    pas. Une famille dont AUCUNE fiche culture visible du potager ne relève —
    référentiel incomplet, cas normal pour une famille jamais renseignée — est
    une **non-réponse** : répondre « aucune parcelle » ferait dire au silence
    du référentiel ce qu'il ne dit pas. Une famille bien rattachée mais absente
    des parcelles, elle, est une réponse chiffrée légitime.
    """
    cible = _familles.normaliser_famille(famille_botanique)
    rattachees = {
        culture
        for culture, nom in _familles.familles_par_culture(db, ctx).items()
        if _familles.normaliser_famille(nom) == cible
    }

    occupation = _parcelles.calcul_occupation_parcelles(db, potager_id=ctx.potager_id)
    par_parcelle: dict[Optional[str], list[str]] = {}
    for nom_parcelle, entrees in occupation.items():
        for entree in entrees:
            if normaliser_culture(entree.get("culture") or "") not in rattachees:
                continue
            cultures = par_parcelle.setdefault(nom_parcelle, [])
            if entree.get("culture") not in cultures:
                cultures.append(entree.get("culture"))

    # Les parcelles nommées d'abord, la case « non localisé » (parcelle_id nul,
    # CA7 d'US-030) en dernier — elle répond à la question sans prétendre être
    # une parcelle.
    ordonnees = sorted(
        par_parcelle.items(), key=lambda item: (item[0] is None, (item[0] or "").lower())
    )
    return {
        "present": bool(rattachees),
        "famille": famille_botanique,
        "rattachees": sorted(rattachees),
        "parcelles": [
            {"parcelle": nom, "cultures": cultures}
            for nom, cultures in ordonnees[:MAX_LIGNES_AFFICHEES]
        ],
        "nb": len(ordonnees),
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


def _lignes_avec_reste(lignes: list[str], total: int, separateur: str = "\n") -> str:
    """Assemble une liste et, si elle est tronquée, annonce ce qui manque.
    Une liste amputée en silence contredirait le nombre annoncé juste au-dessus
    et ferait douter le jardinier de son propre journal — le même principe que
    le CA7 sur les résultats vides.

    [US-141] `separateur` existe parce qu'une « ligne » n'en est pas toujours
    une : un bloc de note tient sur deux lignes — son en-tête, puis son texte
    cité — et les coller les rendrait illisibles. L'annonce du reste, elle, ne
    change pas : c'est tout l'intérêt de ne pas avoir écrit une seconde
    fonction."""
    reste = total - len(lignes)
    if reste > 0:
        lignes = lignes + [f"  … et {reste} autre(s), tout est dans l'application"]
    return separateur.join(lignes)


def _fois(nb: int) -> str:
    return "1 récolte" if nb == 1 else f"{nb} récoltes"


def _mises(nb: int) -> str:
    return "1 mise en godet" if nb == 1 else f"{nb} mises en godet"


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


def _rendu_godets_produits(params: Parametres, agregat: dict) -> str:
    valeurs = {"culture": _sur(params.culture), "periode": agregat["periode"]}
    if not agregat["present"]:
        return _remplir(GABARITS["godets_produits_vide"], valeurs)
    valeurs |= {"total": agregat["total"], "nb": _mises(agregat["nb"])}
    return _remplir(GABARITS["godets_produits"], valeurs)


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


def _rendu_bioagresseurs_culture(params: Parametres, agregat: dict) -> str:
    """[US-173 / CA5, CA6, CA10] Gabarit assemblé, jamais rédigé par un modèle.

    La période n'apparaît que si elle est renseignée (CA6) — « non renseignée »
    répété cinq fois noierait la réponse. Aucun produit, aucun dosage n'est
    formulable ici : l'agrégat n'en porte pas (CA10).
    """
    culture = _sur(agregat["culture"])
    if not agregat["present"]:
        return _remplir(GABARITS["bioagresseurs_culture_sans_fiche"], {"culture": culture})
    if not agregat["nb"]:
        return _remplir(GABARITS["bioagresseurs_culture_aucun"], {"culture": culture})

    lignes = []
    for entree in agregat["entrees"]:
        details = [entree["frequence"]]
        if entree["periode"]:
            details.append(entree["periode"])
        if entree["local"]:
            details.append("votre potager")
        lignes.append(f"  • {_sur(entree['nom'])} — {_sur(' · '.join(details))}")
    return _remplir(GABARITS["bioagresseurs_culture"], {
        "culture": culture,
        "lignes": _lignes_avec_reste(lignes, agregat["nb_lignes"]),
    })


def _notes_lisibles(nb: int) -> str:
    """« 1 note » ou « 8 notes » — le nombre est connu, « note(s) » ne l'est pas."""
    return "1 note" if nb == 1 else f"{nb} notes"


def _bloc_note(entree: dict) -> str:
    """[US-141 / CA5] Une note citée : sa date, son lieu, sa catégorie, son texte.

    Les guillemets ne sont pas un ornement : ils disent que ce qui suit n'a pas
    été retouché.

    ⚠️ Ce bloc ne traverse JAMAIS `_remplir` : celui-ci renormalise les espaces
    et la ponctuation de toute la chaîne qu'il assemble, et retoucherait donc la
    parole du jardinier — précisément ce que l'arbitrage « extrait fidèle,
    jamais résumé » d'US-141 interdit. Le gabarit ne couvre que l'en-tête, les
    blocs sont concaténés après.

    ⚠️ `_sur()` est appliqué au TEXTE de la note, et pas seulement aux noms.
    C'est la première fois que du texte libre du jardinier traverse le rendu du
    catalogue : une note contenant « arroser 2*/semaine » ou « voir [carnet] »
    ferait échouer le parse Markdown de Telegram, donc perdrait la réponse
    entière. `bot._md()`, qui n'échappe que l'underscore, n'y suffirait pas.
    """
    entete = " — ".join(filter(None, (
        entree["date_lisible"],
        f"parcelle {_sur(entree['parcelle'])}" if entree["parcelle"] else "",
        _sur(entree["culture"]) if entree["culture"] else "",
        _sur(entree["categorie"]) if entree["categorie"] else "",
    )))
    return f"• {entete}\n« {_sur(entree['texte'])} »"


def _rendu_notes(params: Parametres, agregat: dict) -> str:
    """[US-141 / CA5] Le carnet du jardinier, cité ou repéré selon son ampleur.

    Deux formes, une seule décision — celle qu'a prise `_zoom_effectif`. Un
    carnet qui tient à l'écran se lit en entier ; au-delà, la réponse dit
    d'abord OÙ REGARDER (par année, ou par saison), ne cite que les plus
    récentes, et rappelle la phrase qui ouvre une période.
    """
    cible = _sur(agregat["cible"])
    periode = f" {agregat['periode']}" if agregat["periode"] else ""
    if not agregat["nb"]:
        return _remplir(GABARITS["notes_vide"], {"cible": cible, "periode": periode})

    nb_lisible = _notes_lisibles(agregat["nb"])
    blocs_notes = [_bloc_note(entree) for entree in agregat["entrees"]]

    if agregat["zoom"] == ZOOM_DETAIL:
        entete = _remplir(GABARITS["notes_detail"], {
            "cible": cible, "nb": nb_lisible, "periode": periode,
        })
        # `_lignes_avec_reste` sur les BLOCS : le nombre annoncé en tête et ce
        # qui est montré ne peuvent jamais se contredire, même quand le budget
        # de caractères a coupé avant le plafond.
        return entete + "\n\n" + _lignes_avec_reste(
            blocs_notes, agregat["nb"], separateur="\n\n"
        )

    lignes_reperes = [
        f"  • {repere['libelle']} — {_notes_lisibles(repere['nb'])}"
        + (f" ({repere['detail']})" if repere["detail"] else "")
        for repere in agregat["reperes"][:MAX_LIGNES_AFFICHEES]
    ]
    entete = _remplir(GABARITS["notes_reperes"], {
        "cible": cible, "nb": nb_lisible, "periode": periode,
        "etendue": agregat["etendue"] or "sur toute leur durée",
    })
    apercu = _remplir(GABARITS["notes_apercu"], {"apercu": str(len(blocs_notes))})
    zoom = _remplir(GABARITS["notes_zoom"], {
        "cible": cible, "exemple": agregat["exemple_zoom"],
    })
    return "\n\n".join([
        entete,
        _lignes_avec_reste(lignes_reperes, len(agregat["reperes"])),
        apercu,
        "\n\n".join(blocs_notes),
        zoom,
    ])


def _rendu_parcelles_par_culture(params: Parametres, agregat: dict) -> str:
    culture = _sur(agregat["culture"])
    if not agregat["nb"]:
        return _remplir(GABARITS["parcelles_par_culture_aucune"], {"culture": culture})
    lignes = []
    for entree in agregat["entrees"]:
        nom = _sur(entree["parcelle"]) if entree["parcelle"] else "sans parcelle renseignée"
        variete = f"{_sur(entree['variete'])}, " if entree["variete"] else ""
        lignes.append(
            f"  • {nom} — {variete}"
            f"{_stock.quantite_lisible(entree['nb_plants'], entree['unite']):g} {entree['unite']}"
        )
    return _remplir(GABARITS["parcelles_par_culture"], {
        "culture": culture, "nb": agregat["nb"],
        "lignes": _lignes_avec_reste(lignes, agregat["nb_lignes"]),
    })


def _rendu_parcelles_par_famille(params: Parametres, agregat: dict) -> str:
    famille = _sur(agregat["famille"])
    if not agregat["present"]:
        return _remplir(GABARITS["parcelles_par_famille_inconnue"], {"famille": famille})
    if not agregat["nb"]:
        return _remplir(GABARITS["parcelles_par_famille_aucune"], {
            "famille": famille,
            "cultures": ", ".join(_sur(culture) for culture in agregat["rattachees"]),
        })
    lignes = [
        "  • {} — {}".format(
            _sur(entree["parcelle"]) if entree["parcelle"] else "sans parcelle renseignée",
            ", ".join(_sur(culture) for culture in entree["cultures"]),
        )
        for entree in agregat["parcelles"]
    ]
    return _remplir(GABARITS["parcelles_par_famille"], {
        "nb": agregat["nb"], "famille": famille,
        "lignes": _lignes_avec_reste(lignes, agregat["nb"]),
    })


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
    # [US-095 / CA4] Natures de donnée dont la réponse de cette famille dérive.
    # Déclarées ICI, au plus près de l'agrégation qui les lit, et jamais dans
    # le cache : une famille ajoutée sans ses dépendances serait une famille
    # dont les réponses mémorisées survivraient à l'évènement qui les
    # contredit. Le champ est obligatoire pour que l'oubli soit impossible.
    dependances: tuple[str, ...]
    # Motif de disqualification : ce qui, s'il apparaît, retire la question à
    # cette famille même si `motif` a matché. Sert aux familles volontairement
    # larges, qui doivent rendre la main plutôt que servir un chiffre à une
    # question qui n'en attend pas.
    exclut: Optional[re.Pattern] = None


# Ce qui retire une question aux familles volontairement larges (celles qui se
# contentent d'une parcelle, d'une culture ou d'une famille botanique nommée
# quelque part dans la phrase) : une
# question de savoir ou de conseil n'attend pas un inventaire. Écrit une fois
# et partagé — deux copies divergeraient au premier ajout, et la divergence se
# paierait en appels au modèle sans se voir.
_EXCLUT_SAVOIR = re.compile(
    r"\bpourquoi\b|\bcomment\b|\bfaut il\b|\bdois je\b|\bque faire\b|"
    r"\bconseil\b|\bpenses tu\b|\ba ton avis\b|\bmaladie\b|\bpuis je\b"
)


# [US-141] Ce qui retire une question aux familles de MÉMOIRE. « Combien
# d'observations ai-je faites ? » est un COMPTAGE : il se répond par un nombre,
# pas par une liste de citations, et le catalogue le sert déjà ailleurs.
#
# ⚠️ « maladie » est volontairement ABSENT, contrairement à `_EXCLUT_SAVOIR` :
# « quelles maladies avais-je notées sur mes tomates ? » demande bien ce que le
# jardinier a ÉCRIT, et c'est cette famille-ci qui doit la servir — pas une
# fiche d'agronomie sur les maladies de la tomate en général.
_EXCLUT_NOTES = re.compile(
    r"\bcombien\b|\bnombre de\b|\bpourquoi\b|\bque faire\b|\bdois je\b|\bfaut il\b"
)


FAMILLES: tuple[Famille, ...] = (
    Famille(
        # [US-141] EN TÊTE, comme `bioagresseurs_culture` et pour la même
        # raison : le motif est étroit — il exige ENSEMBLE un nom d'écrit et une
        # marque de rappel — donc il ne peut voler aucune question à une famille
        # plus large. Le placer plus bas laisserait `occupation_parcelle`,
        # volontairement large, capter « qu'avais-je noté sur la planche
        # nord ? » pour rendre un inventaire de cultures à la place d'une note.
        #
        # Le motif est celui du ROUTEUR (`llm.routeur.MOTIF_MEMOIRE`), importé
        # et jamais recopié : deux définitions de « question de rappel »
        # produiraient une question routée vers le catalogue que le catalogue ne
        # reconnaîtrait plus — une cascade qui tourne à vide, sans rien dans le
        # journal pour le dire.
        nom="notes_culture",
        # La réponse dérive du journal : toute écriture d'événement la périme.
        dependances=(NATURE_JOURNAL,),
        agregation="notes_du_jardinier",
        motif=MOTIF_MEMOIRE,
        exclut=_EXCLUT_NOTES,
        exige=("culture",),
        arguments=lambda p: {
            "culture": p.culture,
            "parcelle": p.parcelle,
            "periode": p.periode,
            "zoom": _detecter_zoom(p.normalisee),
        },
        rendu=_rendu_notes,
    ),
    Famille(
        # Même famille de question, autre désignation de la cible. Deux entrées
        # plutôt qu'une parce que `exige` est une conjonction : « culture OU
        # parcelle » ne s'y exprime pas. L'AGRÉGATION, elle, reste unique — comme
        # `stock_culture` sert déjà `pieds_actifs` et `stock_courant`.
        #
        # APRÈS `notes_culture` : « mes notes sur les tomates de la planche
        # nord » se lit d'abord comme une question sur la tomate, et la parcelle
        # y est un filtre supplémentaire, que `notes_culture` transmet déjà.
        nom="notes_parcelle",
        dependances=(NATURE_JOURNAL,),
        agregation="notes_du_jardinier",
        motif=MOTIF_MEMOIRE,
        exclut=_EXCLUT_NOTES,
        exige=("parcelle",),
        arguments=lambda p: {
            "culture": None,
            "parcelle": p.parcelle,
            "periode": p.periode,
            "zoom": _detecter_zoom(p.normalisee),
        },
        rendu=_rendu_notes,
    ),
    Famille(
        # [US-173] EN PREMIER, et volontairement spécifique : le vocabulaire de
        # l'agression ne se confond avec aucune autre famille, et le placer en
        # tête évite qu'une famille plus large ne capte « quelles maladies sur
        # mes tomates » pour servir un inventaire de parcelles.
        #
        # ⚠️ Cette famille ne porte PAS `_EXCLUT_SAVOIR`, contrairement aux
        # familles larges : ce motif exclut « maladie », qui est ici le mot
        # central de la question. L'exclusion dont elle a besoin est autre —
        # voir `exclut` ci-dessous.
        nom="bioagresseurs_culture",
        # [US-173 / CA1] Cette réponse dérive du référentiel PARTAGÉ (US-162)
        # et non des évènements du potager : aucune nature de donnée ne la
        # décrit vraiment. `NATURE_JOURNAL` est donc déclarée au titre de
        # l'arbitrage « invalider large » d'utils/dependances_donnee — toute
        # écriture périme l'entrée, ce qui ne coûte qu'un recalcul SQL.
        #
        # Déclarer un tuple vide aurait produit le MÊME effet par un autre
        # chemin (`cache_questions` retombe alors sur NATURES_TOUTES), mais sans
        # le dire : une famille sans dépendance se lit comme un oubli, et le
        # garde-fou d'US-095 la refuse à raison.
        #
        # La fraîcheur, elle, ne dépend de toute façon pas de ce champ :
        # `servir_aiguillage` réexécute l'agrégation à chaque service, le cache
        # ne mémorise que le choix de la famille et sa culture.
        dependances=(NATURE_JOURNAL,),
        agregation="bioagresseurs_culture",
        motif=re.compile(
            # Les trois registres du CA2 : le ravageur, la maladie, l'anticipation.
            r"\battaque(?:nt|s|r)?\b|\bs attaquent?\b|\bmaladies?\b|\bravageurs?\b|"
            r"\bnuisibles?\b|\bparasites?\b|\bbioagresseurs?\b|\bbestioles?\b|"
            r"\bbetes\b|\bqui (?:mange|ronge|abime|devore)\b|\bmangent\b|"
            r"\bm attendre\b|\bme attendre\b|\bcraindre\b|\bsurveiller\b"
        ),
        # [US-173 / CA4] Ce qui retire la question à cette famille : une SAISIE
        # d'observation, qui rapporte un fait au lieu de poser une question.
        # « observé une attaque de mildiou sur les tomates » doit s'enregistrer,
        # pas déclencher un inventaire. Le routeur l'attrape déjà avant nous
        # (les verbes d'action y sont testés en premier) ; ceci est la défense
        # en profondeur, au cas où la phrase l'atteindrait autrement.
        exclut=re.compile(
            r"\bobserve\b|\bobservee?s?\b|\bconstate\b|\bconstatee?s?\b|\bremarque\b|"
            r"\bj ai vu\b|\bjai vu\b|\bnote\b|\btraite\b|\bpulverise\b"
        ),
        exige=("culture",),
        arguments=lambda p: {"culture": p.culture},
        rendu=_rendu_bioagresseurs_culture,
    ),
    Famille(
        nom="pepiniere",
        dependances=(NATURE_PEPINIERE, NATURE_SEMIS),
        agregation="pepiniere",
        motif=re.compile(r"\bpepiniere\b|\ben godet\b|\bmes godets\b|\bsemis en cours\b"),
        exige=(),
        arguments=lambda p: {},
        rendu=_rendu_pepiniere,
    ),
    Famille(
        nom="parcelles_libres",
        dependances=(NATURE_PLAN, NATURE_STOCK),
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
        # La dernière occurrence d'un geste ne dépend d'aucun agrégat mais
        # de l'existence des lignes : c'est `journal`, impacté par TOUTE
        # écriture, y compris un simple arrosage.
        dependances=(NATURE_JOURNAL,),
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
        # [Chantier 3 / US-170] AVANT rendement_saison, exprès : sans cet ordre,
        # « combien de godet de tomate produit cette saison ? » atteindrait
        # rendement_saison en premier et rendrait un poids récolté à la place
        # d'un nombre de godets — une réponse fausse d'apparence juste, pire
        # que l'ancienne interception hors sujet de `bot._is_requete_godets`.
        nom="godets_produits",
        dependances=(NATURE_PEPINIERE, NATURE_SEMIS),
        agregation="total_mise_en_godet",
        motif=re.compile(
            r"\bgodets? produits?\b|\bcombien de godets?\b|\bcombien de plants? en godet\b"
        ),
        exige=("culture",),
        arguments=lambda p: {"culture": p.culture, "periode": _periode_saison(p.periode)},
        rendu=_rendu_godets_produits,
    ),
    Famille(
        nom="rendement_saison",
        dependances=(NATURE_RECOLTE, NATURE_STOCK),
        agregation="rendement_saison",
        # [Chantier 3 / US-170] `\bproduit\b` seul a été retiré : « produit »
        # est aussi un nom commun du jardinage (« quel produit contre le
        # mildiou ? »), et le motif bare captait ces questions de savoir comme
        # des questions de rendement. Les tournures ci-dessous exigent un verbe
        # conjugué juste avant « produit », qui désigne réellement une récolte.
        motif=re.compile(
            r"\brendement\b|\bou en sont\b|\bou en est\b|\bproduction de\b|"
            r"\b(?:j ai|a|as|ont|avons|avez) (?:bien |beaucoup |peu |deja )?produit\b"
        ),
        exige=("culture",),
        arguments=lambda p: {"culture": p.culture, "periode": _periode_saison(p.periode)},
        rendu=_rendu_rendement,
    ),
    Famille(
        nom="rendement_global",
        dependances=(NATURE_RECOLTE, NATURE_STOCK),
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
        dependances=(NATURE_RECOLTE, NATURE_STOCK),
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
        dependances=(NATURE_STOCK, NATURE_PLAN),
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
        dependances=(NATURE_STOCK, NATURE_RECOLTE, NATURE_SEMIS, NATURE_PLAN),
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
        dependances=(NATURE_STOCK, NATURE_RECOLTE, NATURE_SEMIS, NATURE_PLAN),
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
        # La question INVERSE d'`occupation_parcelle` : celle-ci part d'une
        # parcelle et rend ses cultures, celle-là part d'une culture et rend
        # ses parcelles. L'association parcelle ↔ culture était déjà acquise
        # (c'est celle de /plan) mais aucune famille ne savait la lire dans ce
        # sens : « sur quelles parcelles je trouve des tomates ? » repartait à
        # l'agent SQL, qui en a rendu un « Historique observation de tomate »
        # — le geste inventé par l'extraction d'intention, appliqué à la bonne
        # culture (constaté en usage réel le 02/09/2026).
        #
        # Le motif reste étroit — des tournures de LOCALISATION explicites, pas
        # un simple `\bparcelle\b` : sans quoi cette famille prendrait à
        # `occupation_parcelle` toute question qui nomme une parcelle et une
        # culture, alors que le jardinier y demande l'inventaire de la parcelle.
        nom="parcelles_par_culture",
        dependances=(NATURE_PLAN, NATURE_STOCK),
        agregation="parcelles_par_culture",
        motif=re.compile(
            r"\b(?:sur|dans|a|de) quelles? (?:parcelles?|planches?|carre|carreau|zone|butte|bac)\b|"
            r"\bquelles? (?:parcelles?|planches?)\b|"
            r"\bou (?:sont|est|se trouve|se trouvent|pousse|poussent|ai je|j ai)\b|"
            r"\bparcelles? avec\b|\blocalisation\b|\bemplacement\b"
        ),
        exclut=_EXCLUT_SAVOIR,
        exige=("culture",),
        arguments=lambda p: {"culture": p.culture},
        rendu=_rendu_parcelles_par_culture,
    ),
    Famille(
        # AVANT `occupation_parcelle`, qui exige UNE parcelle désignée : « quelles
        # parcelles contiennent des solanacées ? » parle de parcelles au pluriel
        # sans en nommer aucune, le filet ne pouvait donc pas la servir. Sans
        # cette famille, la question repartait à l'agent SQL, dont l'extraction
        # d'intention choisit dans un vocabulaire fermé : elle en revenait avec
        # `action="observation"` et un « Top cultures — observation » exact,
        # hors sujet, et assez assuré pour que la cascade ne remonte pas
        # (constaté en usage réel le 02/09/2026).
        #
        # La question ne se reconnaît pas à sa grammaire mais à la famille
        # botanique RÉSOLUE contre le référentiel : « où sont mes solanacées »,
        # « mes parcelles avec des cucurbitacées » et « quelles planches portent
        # des Apiaceae » sont la même question.
        nom="parcelles_par_famille",
        dependances=(NATURE_PLAN, NATURE_STOCK),
        agregation="parcelles_par_famille",
        motif=re.compile(
            r"\bparcelles?\b|\bplanches?\b|\bcarre\b|\bcarreau\b|\bzone\b|\bbutte\b|\bbac\b|"
            r"\bou (?:sont|est|ai je|se trouvent?|j ai)\b|\bdans quelle?s?\b"
        ),
        exclut=_EXCLUT_SAVOIR,
        exige=("famille_botanique",),
        arguments=lambda p: {"famille_botanique": p.famille_botanique},
        rendu=_rendu_parcelles_par_famille,
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
        dependances=(NATURE_PLAN, NATURE_STOCK),
        agregation="occupation_parcelle",
        motif=re.compile(r"\b(?:parcelles?|planches?|carre|carreau|zone|butte|bac)\b"),
        # …mais une question de savoir ou de conseil qui mentionne une parcelle
        # n'attend pas un inventaire : elle rend la main à la cascade.
        exclut=_EXCLUT_SAVOIR,
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


_FAMILLES_PAR_NOM: dict[str, Famille] = {famille.nom: famille for famille in FAMILLES}


def famille_par_nom(nom: str) -> Optional[Famille]:
    """[US-095] Famille du catalogue portant ce nom, ou `None` si le nom ne
    correspond à rien — cas d'une entrée de cache mémorisée par une version
    antérieure du catalogue, dont la famille a depuis été renommée ou retirée.
    L'appelant rend alors la main à la cascade plutôt que d'échouer."""
    return _FAMILLES_PAR_NOM.get(nom)


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
    # [US-095 / CA3] Aiguillage de la réponse : ce qui suffit à la REJOUER, et
    # rien de plus — famille du catalogue, culture, parcelle, dépendances.
    # Aucune valeur chiffrée n'y figure : c'est précisément ce qui permet de
    # mémoriser cette réponse sans jamais mémoriser un chiffre qui pourrait
    # devenir faux. Vide si la famille n'est pas rejouable telle quelle.
    aiguillage: dict = field(default_factory=dict)

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


def reconnaitre(
    ctx: TenantContext, question: str, db: Optional[Session] = None
) -> Optional[tuple[Famille, Parametres]]:
    """Famille qui saurait servir cette question, ET les paramètres extraits.

    Reconnaître n'est pas répondre : aucune agrégation n'est exécutée ici, on
    s'arrête à l'extraction des paramètres et au choix de la famille. C'est ce
    qui permet au routeur (US-093) de s'en servir comme d'une règle
    supplémentaire, à coût nul en jetons.

    [US-095] Rend aussi les paramètres, et pas seulement la famille : le cache
    de questions en a besoin pour construire la clé d'aiguillage
    (`cle_aiguillage`), qui porte la culture et la parcelle. Sans eux, il
    faudrait refaire l'extraction immédiatement après.

    Ne lève jamais : une reconnaissance impossible se lit « je ne reconnais
    pas », et la classification se poursuit normalement.
    """
    session_locale = db is None
    session = db if db is not None else SessionLocal()
    try:
        with catalogue_sql.garde_lecture_seule(session):
            params = _extraire_parametres(session, ctx, question)
        famille = _choisir_famille(params)
        return (famille, params) if famille is not None else None
    except Exception as erreur:
        log.debug("GABARIT SQL : reconnaissance impossible (%s)", type(erreur).__name__)
        return None
    finally:
        if session_locale:
            session.close()


def reconnait_famille(
    ctx: TenantContext, question: str, db: Optional[Session] = None
) -> Optional[str]:
    """Nom de la famille qui saurait servir cette question, ou `None`.

    **Pourquoi le routeur interroge le catalogue plutôt que d'énumérer ses
    propres motifs :** parce que deux listes de motifs, une ici et une là-bas,
    divergent à la première famille ajoutée — et la divergence ne se voit pas,
    elle se paie en appels au modèle. « qu'est-ce que j'ai en parcelle sud ? »
    l'a montré le 26/08/2026 : le catalogue savait répondre, le routeur ne le
    savait pas, et la question a coûté deux appels pour une réponse que le
    gabarit avait déjà produite gratuitement.

    Contrat inchangé pour le routeur, qui n'a besoin que du nom.
    """
    reconnue = reconnaitre(ctx, question, db=db)
    return reconnue[0].nom if reconnue is not None else None


def aiguillage_de(famille: Famille, params: Parametres) -> dict:
    """[US-095 / CA3, CA4] Ce qui suffit à rejouer cette famille plus tard.

    **Seuls la culture et la parcelle y figurent** — les deux paramètres dont
    l'extraction demande une lecture en base (liste des cultures connues,
    résolution du nom de parcelle). La période et le type d'action, eux, sont
    RE-dérivés du motif au moment de servir, par pure analyse de la phrase
    (`_detecter_periode`, `_detecter_action`).

    Ce n'est pas une économie, c'est une question de justesse : une période
    résolue en décembre (« cette saison » → 2026-01-01…2026-12-31) et
    mémorisée telle quelle servirait encore les chiffres de 2026 en janvier
    suivant. Une réponse fausse d'un an, sans qu'aucun évènement ne l'ait
    contredite — donc qu'aucune invalidation n'aurait rattrapée. Redériver la
    période à chaque service rend cette classe d'erreur impossible, au même
    titre que le paramétré la rend impossible pour les valeurs.
    """
    return {
        "famille": famille.nom,
        "culture": params.culture,
        "parcelle": params.parcelle,
        "dependances": list(famille.dependances),
    }


def cle_aiguillage(aiguillage: dict) -> str:
    """[US-095 / CA2] Clé canonique d'un aiguillage — l'identité d'une question,
    débarrassée de la façon dont elle a été formulée.

    « quel est ma production de concombre », « ma production de concombre » et
    « production de concombre » sont trois phrases pour une seule question :
    elles produisent le même aiguillage, donc la même clé, donc une seule entrée
    de cache. Constaté en usage réel le 29/08/2026 — trois formulations en 29
    secondes avaient créé trois entrées et n'avaient jamais servi une seule
    réponse depuis le cache.

    Les `dependances` n'entrent PAS dans la clé : elles se déduisent de la
    famille, les inclure ne distinguerait rien et rendrait la clé instable au
    premier ajustement d'une déclaration de dépendances.

    Le type d'action et la période n'y entrent pas non plus, et c'est
    volontaire : `servir_aiguillage()` les redérive de la phrase vivante. Deux
    questions de même aiguillage mais de période différente (« récolté en
    juillet » / « en août ») partagent donc l'entrée et reçoivent chacune leur
    réponse exacte. L'entrée dit « cette forme de question est connue » ; la
    réponse, elle, vient toujours de l'état réel.
    """
    aiguillage = aiguillage or {}
    return "|".join((
        aiguillage.get("famille") or "",
        (aiguillage.get("culture") or "").lower(),
        (aiguillage.get("parcelle") or "").lower(),
    ))


def servir_aiguillage(
    ctx: TenantContext, aiguillage: dict, question: str, db: Optional[Session] = None
) -> Optional[ReponseChiffree]:
    """[US-095 / CA3] Rejoue une famille déjà mémorisée : **les valeurs sont
    recalculées**, seul l'aiguillage vient du cache.

    C'est la fonction qui fait qu'une réponse `template_sql` ne peut pas être
    périmée : elle exécute la même agrégation, sur la base telle qu'elle est
    maintenant, et la met en forme avec le même gabarit. Le cache ne fait donc
    jamais l'économie de la vérité — seulement celle du choix de la famille et
    de l'extraction de ses paramètres.

    Retourne `None` si la famille n'existe plus au catalogue ou si l'agrégation
    échoue : l'appelant reprend alors la cascade normale, comme si aucune
    entrée n'avait été trouvée.
    """
    famille = famille_par_nom((aiguillage or {}).get("famille") or "")
    if famille is None:
        return None

    session_locale = db is None
    session = db if db is not None else SessionLocal()
    try:
        normalisee = _normaliser(question)
        params = Parametres(
            question=question,
            normalisee=normalisee,
            culture=aiguillage.get("culture"),
            # Redérivés de la phrase, jamais relus du cache — voir `_aiguillage`.
            action=_detecter_action(normalisee),
            parcelle=aiguillage.get("parcelle"),
            # Redérivée elle aussi : « quelles parcelles portent des
            # solanacées ? » et « … des cucurbitacées ? » partagent l'entrée
            # de cache et reçoivent chacune sa réponse exacte, exactement
            # comme deux périodes différentes (voir `cle_aiguillage`).
            famille_botanique=_detecter_famille_botanique(session, normalisee),
            periode=_detecter_periode(normalisee, _date.today()),
        )
        if not all(getattr(params, nom) for nom in famille.exige):
            return None

        agregat = catalogue_sql.executer(
            famille.agregation, session, ctx, **famille.arguments(params)
        )
        return ReponseChiffree(
            texte=famille.rendu(params, agregat),
            famille=famille.nom,
            present=bool(agregat["present"]),
            aiguillage=aiguillage_de(famille, params),
        )
    except GardeCatalogueError as erreur:
        catalogue_sql.journaliser_refus(erreur, question)
        return None
    except Exception as erreur:
        log.warning(
            "⚠️ GABARIT SQL     │ rejeu d'aiguillage impossible (%s) → poursuite de la cascade : '%s'",
            type(erreur).__name__, (question or "")[:80],
        )
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
        return ReponseChiffree(
            texte=texte, famille=famille.nom, present=bool(agregat["present"]),
            aiguillage=aiguillage_de(famille, params),
        )
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

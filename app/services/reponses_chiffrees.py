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
culture ou une parcelle [US-141] · pré-diagnostic à partir d'un symptôme décrit [US-165].

[US-165] Deux familles servent désormais le référentiel PARTAGÉ et non les
chiffres du potager : `bioagresseurs_culture` (« qu'est-ce qui attaque mes
poireaux ») et `prediagnostic_symptome` (« mes tomates ont des taches marron »).
Elles sont ici et pas ailleurs pour une raison unique : ce sont des réponses
EXACTES, servies par gabarit, à zéro jeton — exactement le contrat de cet étage.
Ce qu'elles agrègent est une jointure de référentiel plutôt qu'une somme
d'évènements, et cela ne change rien à ce contrat.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date as _date, datetime, timedelta
from typing import Callable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session
from unidecode import unidecode

from app.services import bioagresseurs as svc_bioagresseurs
from app.services import catalogue_sql
from app.services import prediagnostic as svc_prediagnostic
from app.services import familles as _familles
from app.services import memoire_potager as _memoire
from app.services import potager_actif as _potager_actif
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

    # [US-248] Classement des récoltes et total de la période ; les pièces sont à part
    "classement_recoltes":      "Récoltes {periode}, de la plus à la moins productive :\n{lignes}",
    "total_recoltes":           "Tu as récolté {total} {periode}, toutes cultures confondues.",
    "recoltes_pieces":          "À part, comptées à la pièce (jamais additionnées aux kilos) :\n{lignes}",
    "recoltes_pieces_seules":   "Tu n'as aucune récolte pesée {periode}. Comptées à la pièce :\n{lignes}",
    "recoltes_aucune":          "Je n'ai aucune récolte enregistrée {periode}.",
    # [US-249] Le potager actif
    "potager_actif":            "Ton potager actif est « {actif} ».",
    "potager_actif_autres":     "Tu as aussi accès à : {autres}. Pour changer de potager actif : /potager.",
    "potagers_nombre":          "Tu as accès à {nb} potager(s) : {liste}.",
    "potager_actif_inconnu":    "Je ne retrouve pas ton potager actif. Pour en choisir un : /potager.",
    "potagers_nombre_un":       "Tu as accès à un seul potager : « {actif} », ton potager actif.",

    # Stock courant, toutes cultures confondues
    "stock_global":            "Ton stock actuel :\n{lignes}",
    "stock_global_vide":        "Je n'ai aucune culture en place enregistrée dans ce potager.",

    # Contenu de la pépinière
    "pepiniere":                "Ta pépinière contient {nb} lot(s) de semis :\n{lignes}",
    "pepiniere_vide":           "Je n'ai aucun lot de semis en pépinière enregistré.",

    # Parcelles libres — la place disponible pour la prochaine culture
    "parcelles_libres":         "{nb} parcelle(s) libre(s) sur {total} :\n{lignes}",
    "liste_parcelles":          "Tu as {nb} parcelle(s) dans ce potager :\n{lignes}",
    # [US-244] Caractéristiques d'une parcelle et parcelles filtrées sur l'une d'elles
    "attribut_parcelle":        "{parcelle} — {lignes}",
    "attribut_parcelle_vide":   "{libelle} de {parcelle} : non renseigné. Pour le renseigner : /parcelle modifier {parcelle} {cle}=…",
    "parcelles_filtrees":       "{nb} parcelle(s) {libelle} sur {total} :\n{lignes}",
    "parcelles_filtrees_aucune": "Aucune parcelle {libelle} sur tes {total} parcelles.",
    # [US-245] Inventaire des cultures et variétés
    "cultures_en_place":        "Cultures en place ({nb}) :\n{lignes}",
    "cultures_en_place_aucune": "Aucune culture en place pour l'instant.",
    "varietes_culture":         "{nb} variété(s) de {culture} :\n{lignes}",
    "varietes_culture_nombre":  "{nb} variété(s) de {culture}.",
    "varietes_culture_aucune":  "Aucune variété de {culture} enregistrée dans ce potager.",
    # [US-246] Compter un geste, relire l'historique d'un type de geste
    "nombre_occurrences":       "{nb} {action} de {culture} {periode}.",
    "nombre_occurrences_sans_culture": "{nb} {action} {periode}, toutes cultures confondues.",
    "nombre_occurrences_vide":  "Je n'ai {aucun} {action} de {culture} enregistré{e} {periode}.",
    "nombre_occurrences_vide_sans_culture": "Je n'ai {aucun} {action} enregistré{e} {periode}, toutes cultures confondues.",
    "historique_action":        "{nb} {action} de {culture} {periode} :\n{lignes}",
    "historique_action_sans_culture": "{nb} {action} {periode} :\n{lignes}",
    # [US-247] Ce que j'ai fait sur une période
    "journal_periode":          "Ce que tu as fait {periode} ({nb} geste(s)) :\n{lignes}",
    "journal_periode_resume":   "Ce que tu as fait {periode} : {nb} gestes — {resume}.\nLe détail jour par jour est dans l'historique de l'application.",
    "journal_periode_vide":     "Rien d'enregistré {periode}.",
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

    # [US-165] Le pré-diagnostic. Cinq gabarits pour cinq situations, parce que
    # les confondre trompe le jardinier — et parce que trois d'entre elles sont
    # des IGNORANCES différentes, qu'il a le droit de distinguer.
    #
    # ⚠️ `FORMULE_EVOCATION` est reprise du service, jamais recopiée : la
    # formulation du CA4 est imposée et non négociable, et une seconde
    # occurrence littérale dériverait à la première reformulation. Les trois
    # messages d'ignorance viennent du service pour la même raison.
    "prediagnostic":        "Sur {culture}, ce que tu décris ({symptome}) "
                            + svc_prediagnostic.FORMULE_EVOCATION + " :\n{lignes}",
    "prediagnostic_unique": "Sur {culture}, ce que tu décris ({symptome}) "
                            + svc_prediagnostic.FORMULE_EVOCATION + " :\n{lignes}\n\n"
                            + svc_prediagnostic.MESSAGE_PISTE_UNIQUE,
    "prediagnostic_symptome_inconnu": svc_prediagnostic.MESSAGE_SYMPTOME_INCONNU,
    "prediagnostic_culture_sans_fiche": svc_prediagnostic.MESSAGE_CULTURE_SANS_FICHE,
    "prediagnostic_aucun_croisement": svc_prediagnostic.MESSAGE_AUCUN_CROISEMENT,

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

    # [US-247] Les périodes COURTES du journal. Du plus précis au plus large :
    # « avant-hier » avant « hier », « la semaine dernière » avant « cette semaine ».
    if re.search(r"\bavant hier\b", normalisee):
        jour = aujourdhui - timedelta(days=2)
        return Periode(jour, jour, "avant-hier", jour.year)
    if re.search(r"\bhier\b", normalisee):
        jour = aujourdhui - timedelta(days=1)
        return Periode(jour, jour, "hier", jour.year)
    if re.search(r"\baujourd hui\b|\bce jour\b", normalisee):
        return Periode(aujourdhui, aujourdhui, "aujourd'hui", annee)
    lundi = aujourdhui - timedelta(days=aujourdhui.weekday())
    if re.search(r"\bsemaine (?:derniere|passee)\b", normalisee):
        return Periode(lundi - timedelta(days=7), lundi - timedelta(days=1), "la semaine dernière", annee)
    if re.search(r"\bcette semaine\b", normalisee):
        return Periode(lundi, aujourdhui, "cette semaine", annee)
    jour_cite = re.search(rf"\ble (\d{{1,2}}) (?:er )?({'|'.join(MOIS)})\b", normalisee)
    if jour_cite:
        try:
            jour = _date(annee, MOIS[jour_cite.group(2)], int(jour_cite.group(1)))
        except ValueError:
            jour = None
        if jour is not None:
            return Periode(jour, jour, f"le {jour.day} {jour_cite.group(2)}", annee)

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


#: [US-246] Occurrences citées dans l'historique d'un geste ; le reste est annoncé.
LIMITE_HISTORIQUE_GESTE = 10

#: [US-247] Au-delà, le journal d'une période se RÉSUME par type de geste au lieu
#: de se dérouler : quinze lignes se lisent, soixante se font défiler.
LIMITE_LIGNES_JOURNAL = 15

#: [US-247] Période par défaut de « qu'est-ce que j'ai fait ? », dite dans la réponse.
JOURS_JOURNAL_PAR_DEFAUT = 7


def _evenements_filtres(
    db: Session, ctx: TenantContext, periode: Periode,
    action: Optional[str] = None, culture: Optional[str] = None,
):
    """Requête commune des familles de journal : potager actif, geste, culture et
    fenêtre de dates, dans cet ordre — la même lecture pour compter et pour lister."""
    debut, fin = _bornes(periode)
    requete = db.query(Evenement).filter(Evenement.potager_id == ctx.potager_id)
    if action:
        requete = requete.filter(Evenement.type_action == action)
    if culture:
        requete = requete.filter(func.lower(Evenement.culture) == culture.lower())
    if debut is not None:
        requete = requete.filter(Evenement.date >= debut)
    if fin is not None:
        requete = requete.filter(Evenement.date <= fin)
    return requete


def _noms_parcelles(db: Session, ctx: TenantContext, evenements) -> dict[int, str]:
    ids = {e.parcelle_id for e in evenements if e.parcelle_id}
    if not ids:
        return {}
    lignes = db.query(Parcelle.id, Parcelle.nom).filter(
        Parcelle.potager_id == ctx.potager_id, Parcelle.id.in_(ids)
    ).all()
    return {identifiant: nom for identifiant, nom in lignes}


def _ligne_evenement(e: Evenement, noms: dict[int, str]) -> dict:
    return {
        "date": e.date, "action": e.type_action, "culture": e.culture, "variete": e.variete,
        "quantite": e.quantite, "unite": e.unite, "produit": e.traitement,
        "parcelle": noms.get(e.parcelle_id),
    }


@catalogue_sql.enregistrer("nombre_occurrences")
def _agreger_nombre_occurrences(
    db: Session, ctx: TenantContext, action: str, culture: Optional[str], periode: Periode
) -> dict:
    """[US-246 / CA1, CA4, CA6] Nombre de saisies d'un type de geste, avec le total
    de pieds pour une perte. `present` est toujours vrai : zéro est une réponse."""
    evenements = _evenements_filtres(db, ctx, periode, action, culture).all()
    pieces, unite_pieces = 0.0, ""
    for e in evenements:
        if (e.unite or "").lower() not in _stock.UNITES_POIDS_EN_G and e.quantite:
            pieces += e.quantite
            unite_pieces = e.unite or "pieds"
    return {
        "present": True, "periode": periode.libelle, "nb": len(evenements),
        "pieces": pieces, "unite_pieces": unite_pieces,
    }


@catalogue_sql.enregistrer("historique_action")
def _agreger_historique_action(
    db: Session, ctx: TenantContext, action: str, culture: Optional[str], periode: Periode
) -> dict:
    """[US-246 / CA3, CA6] Les occurrences d'un geste, de la plus récente à la plus
    ancienne, plafonnées ; le total est celui de toute la fenêtre."""
    requete = _evenements_filtres(db, ctx, periode, action, culture)
    nb = requete.count()
    evenements = requete.order_by(Evenement.date.desc().nullslast(), Evenement.id.desc()).limit(
        LIMITE_HISTORIQUE_GESTE
    ).all()
    noms = _noms_parcelles(db, ctx, evenements)
    return {
        "present": True, "periode": periode.libelle, "nb": nb,
        "lignes": [_ligne_evenement(e, noms) for e in evenements],
    }


@catalogue_sql.enregistrer("journal_periode")
def _agreger_journal_periode(
    db: Session, ctx: TenantContext, periode: Periode, culture: Optional[str] = None
) -> dict:
    """[US-247 / CA1-CA5] Tous les gestes d'une période, du plus ancien au plus
    récent. Au-delà de `LIMITE_LIGNES_JOURNAL`, seul le décompte par type de geste
    est rendu — les lignes ne sont alors pas chargées."""
    requete = _evenements_filtres(db, ctx, periode, None, culture).filter(Evenement.date.isnot(None))
    nb = requete.count()
    par_type = dict(
        _evenements_filtres(db, ctx, periode, None, culture)
        .filter(Evenement.date.isnot(None))
        .with_entities(Evenement.type_action, func.count(Evenement.id))
        .group_by(Evenement.type_action).all()
    )
    lignes: list[dict] = []
    if 0 < nb <= LIMITE_LIGNES_JOURNAL:
        evenements = requete.order_by(Evenement.date.asc(), Evenement.id.asc()).all()
        noms = _noms_parcelles(db, ctx, evenements)
        lignes = [_ligne_evenement(e, noms) for e in evenements]
    return {"present": True, "periode": periode.libelle, "nb": nb, "par_type": par_type, "lignes": lignes}


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


@catalogue_sql.enregistrer("classement_recoltes")
def _agreger_classement_recoltes(db: Session, ctx: TenantContext, periode: Periode) -> dict:
    """[US-248 / CA1-CA4, CA6] Les récoltes de la période, par culture : le poids
    (classé du plus au moins productif) et, À PART, ce qui se compte en pièces ou
    en bottes. Mêmes règles que `utils/stock.calcul_rendement_mensuel`, qui
    alimente la courbe de rendement du web : seules les saisies de récolte d'une
    culture nommée et chiffrée comptent, et le poids est converti par la même
    table d'unités — le total est donc celui du web, pas une seconde vérité.
    Le nombre de pieds n'entre jamais ici : toutes les cueillettes s'additionnent."""
    debut, fin = _bornes(periode)
    requete = (
        db.query(Evenement.culture, Evenement.unite, func.sum(Evenement.quantite))
        .filter(
            Evenement.potager_id == ctx.potager_id,
            Evenement.type_action == "recolte",
            Evenement.culture.isnot(None),
            Evenement.quantite.isnot(None),
        )
    )
    if debut is not None:
        requete = requete.filter(Evenement.date >= debut)
    if fin is not None:
        requete = requete.filter(Evenement.date <= fin)

    poids_g: dict[str, float] = {}
    pieces: dict[tuple[str, str], float] = {}
    for culture, unite, total in requete.group_by(Evenement.culture, Evenement.unite).all():
        unite_normalisee = (unite or "").lower()
        if unite_normalisee in _stock.UNITES_POIDS_EN_G:
            poids_g[culture] = poids_g.get(culture, 0.0) + (total or 0.0) * _stock.UNITES_POIDS_EN_G[unite_normalisee]
        else:
            cle = (culture, unite or "pièces")
            pieces[cle] = pieces.get(cle, 0.0) + (total or 0.0)

    classement = sorted(poids_g.items(), key=lambda entree: entree[1], reverse=True)
    a_part = sorted(pieces.items(), key=lambda entree: entree[1], reverse=True)
    return {
        "present": bool(classement or a_part),
        "periode": periode.libelle,
        "total_g": sum(poids_g.values()),
        "cultures": classement[:MAX_LIGNES_AFFICHEES],
        "nb": len(classement),
        "pieces": a_part[:MAX_LIGNES_AFFICHEES],
        "nb_pieces": len(a_part),
    }


@catalogue_sql.enregistrer("potager_actif")
def _agreger_potager_actif(db: Session, ctx: TenantContext) -> dict:
    """[US-249 / CA1-CA4] Le potager actif et les potagers auxquels le jardinier
    a accès. Les potagers viennent de `lister_potagers_utilisateur` (appartenance
    réelle, comme /potager) : jamais ceux d'un autre compte. Un potager actif dont
    le jardinier n'est pas membre n'est pas cité — la question retombe alors
    sur la cascade plutôt que de révéler le nom d'un potager étranger."""
    accessibles = (
        _potager_actif.lister_potagers_utilisateur(db, ctx.user_id, etat="tous")
        if ctx.user_id is not None else []
    )
    actif = next((p for p in accessibles if p.id == ctx.potager_id), None)
    return {
        "present": actif is not None,
        "actif": actif.nom if actif is not None else "",
        "autres": [p.nom for p in accessibles if p.id != ctx.potager_id][:MAX_LIGNES_AFFICHEES],
        "nb": len(accessibles),
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
              or _stock.graines_restantes(lot) > 0]
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


@catalogue_sql.enregistrer("liste_parcelles")
def _agreger_liste_parcelles(db: Session, ctx: TenantContext) -> dict:
    """Les parcelles actives du potager — `utils/parcelles.get_all_parcelles`,
    la lecture de /parcelle lister [CA4]. Relevé du 21/10/2026 : « combien de
    parcelle ? » ne trouvait aucune famille et finissait en réponse générique."""
    parcelles = _parcelles.get_all_parcelles(db, potager_id=ctx.potager_id)
    return {
        "present": bool(parcelles),
        "parcelles": [(p.nom, bool(p.est_pepiniere)) for p in parcelles[:MAX_LIGNES_AFFICHEES]],
        "nb": len(parcelles),
    }


# [US-244] Les caractéristiques d'une parcelle : clé de la commande /parcelle
# modifier, libellé de la réponse, motif qui la désigne dans la question. Une
# seule table pour les trois lectures (une parcelle, un filtre, un libellé) :
# deux copies divergeraient au premier attribut ajouté.
ATTRIBUTS_PARCELLE: dict[str, tuple[str, re.Pattern]] = {
    "pepiniere":      ("le statut de pépinière", re.compile(r"\bpepiniere\b")),
    "type_sol":       ("le type de sol", re.compile(r"\bsol\b|\bterrain\b")),
    "rangs":          ("le nombre de rangs", re.compile(r"\brangs?\b|\brangees?\b")),
    "longueur":       ("la longueur", re.compile(r"\blongueur\b|\bde long\b|\blongue?\b")),
    "superficie":     ("la superficie", re.compile(r"\bsuperficie\b|\bsurface\b|\bm2\b|\bmetres? carres?\b")),
    "exposition":     ("l'exposition", re.compile(r"\bexposition\b|\bexposee?\b|\borientation\b|\borientee?\b")),
    "ensoleillement": ("l'ensoleillement", re.compile(r"\bensoleillement\b|\bensoleillee?\b|\bsoleil\b|\bombre\b")),
    "paillage":       ("le paillage", re.compile(r"\bpaill\w*")),
    "abri":           ("l'abri", re.compile(r"\babris?\b|\babrit\w*|\bsous (?:serre|tunnel|voile|chassis)\b")),
}


def _attributs_cites(normalisee: str) -> list[str]:
    """Les caractéristiques de parcelle que la question désigne, dans l'ordre de
    la table. Redérivées de la phrase à chaque service (voir `aiguillage_de`)."""
    return [cle for cle, (_, motif) in ATTRIBUTS_PARCELLE.items() if motif.search(normalisee)]


def _valeur_attribut(parcelle, cle: str) -> Optional[str]:
    """La valeur lisible d'une caractéristique, `None` si elle n'est pas renseignée.
    « Non renseigné » n'est jamais remplacé par une valeur par défaut [CA4]."""
    c = _parcelles.caracteristiques_declarees(parcelle)
    if cle == "pepiniere":
        if not c["est_pepiniere"]:
            return "pleine terre (pas une pépinière)"
        return {"chaude": "pépinière chaude", "froide": "pépinière froide"}.get(
            c["genre_pepiniere"] or "", "pépinière (type non renseigné)")
    if cle == "paillage":
        return None if c["paillage"] is None else ("paillée" if c["paillage"] else "non paillée")
    if cle == "abri":
        if not c["abri"]:
            return None
        return "aucun abri" if c["abri"] == _parcelles.ABRI_AUCUN else _parcelles.LIBELLES_ABRI.get(
            c["abri"], c["abri"])
    brut = c[cle]
    if brut in (None, ""):
        return None
    if cle == "rangs":
        return f"{brut} rang(s)"
    if cle == "longueur":
        return f"{brut:g} m"
    if cle == "superficie":
        return f"{brut:g} m²"
    return str(brut)


@catalogue_sql.enregistrer("attributs_parcelle")
def _agreger_attributs_parcelle(db: Session, ctx: TenantContext, parcelle: str, attributs: list) -> dict:
    """[US-244 / CA3, CA4] Les caractéristiques enregistrées d'UNE parcelle du
    potager — `utils/parcelles.get_all_parcelles`, la lecture de /parcelle lister.
    `present` est vrai dès que la parcelle existe : « non renseigné » est une
    réponse exacte, pas une absence de donnée."""
    cible = _normaliser(parcelle)
    for fiche in _parcelles.get_all_parcelles(db, potager_id=ctx.potager_id):
        if _normaliser(fiche.nom) == cible:
            return {
                "present": True,
                "parcelle": fiche.nom,
                "valeurs": {cle: _valeur_attribut(fiche, cle) for cle in attributs},
            }
    return {"present": False, "parcelle": parcelle, "valeurs": {}}


# [US-244 / CA2, CA5] Les filtres de liste : « quelles parcelles sont paillées ? »
_FILTRES_PARCELLES: tuple[tuple[str, re.Pattern, str], ...] = (
    ("pepiniere", re.compile(r"\bpepinieres?\b"), "en pépinière"),
    ("paillage", re.compile(r"\bpaill\w*"), "paillée(s)"),
    ("abri_serre", re.compile(r"\bsous serre\b"), "sous serre"),
    ("abri_tunnel", re.compile(r"\bsous tunnel\b"), "sous tunnel"),
    ("abri_voile", re.compile(r"\bsous voile\b"), "sous voile"),
    ("abri_chassis", re.compile(r"\bsous chassis\b"), "sous châssis"),
    ("abri", re.compile(r"\babrit\w*|\bsous abri\b"), "sous abri"),
    ("mi_ombre", re.compile(r"\bmi ombre\b"), "en mi-ombre"),
    ("plein_soleil", re.compile(r"\bplein soleil\b|\bau soleil\b"), "en plein soleil"),
    ("ombre", re.compile(r"\bombre\b|\bombragees?\b"), "à l'ombre"),
)


def _filtre_cite(normalisee: str) -> Optional[tuple[str, str]]:
    for cle, motif, libelle in _FILTRES_PARCELLES:
        if motif.search(normalisee):
            return cle, libelle
    return None


def _parcelle_retenue(fiche, filtre: str) -> Optional[bool]:
    """Vrai/faux si la parcelle porte la caractéristique, `None` si elle n'est pas
    renseignée (comptée à part : elle n'est ni oui ni non)."""
    c = _parcelles.caracteristiques_declarees(fiche)
    if filtre == "pepiniere":
        return c["est_pepiniere"]
    if filtre == "paillage":
        return c["paillage"]
    if filtre.startswith("abri"):
        if not c["abri"]:
            return None
        if filtre == "abri":
            return c["abri"] != _parcelles.ABRI_AUCUN
        return c["abri"] == filtre.split("_", 1)[1]
    if not c["ensoleillement"]:
        return None
    return c["ensoleillement"] == {
        "mi_ombre": "mi-ombre", "plein_soleil": "plein soleil", "ombre": "ombre",
    }[filtre]


@catalogue_sql.enregistrer("parcelles_filtrees")
def _agreger_parcelles_filtrees(db: Session, ctx: TenantContext, filtre: str, libelle: str) -> dict:
    """[US-244 / CA2, CA5] Les parcelles qui portent une caractéristique. `present`
    est vrai dès que le potager a des parcelles : « aucune parcelle paillée » est
    une réponse chiffrée (CA7 d'US-096), pas une absence de donnée."""
    fiches = _parcelles.get_all_parcelles(db, potager_id=ctx.potager_id)
    retenues: list[dict] = []
    inconnues = 0
    for fiche in fiches:
        verdict = _parcelle_retenue(fiche, filtre)
        if verdict is None:
            inconnues += 1
        elif verdict:
            detail = _valeur_attribut(fiche, "pepiniere") if filtre == "pepiniere" else None
            retenues.append({"nom": fiche.nom, "detail": detail})
    return {
        "present": bool(fiches), "filtre": filtre, "libelle": libelle,
        "parcelles": retenues[:MAX_LIGNES_AFFICHEES], "nb": len(retenues),
        "total": len(fiches), "non_renseignees": inconnues,
    }


@catalogue_sql.enregistrer("cultures_en_place")
def _agreger_cultures_en_place(db: Session, ctx: TenantContext) -> dict:
    """[US-245 / CA1-CA3, CA6, CA7] L'inventaire du potager : les cultures qui ont
    au moins un pied en place, et à part ce qui est encore en pépinière.

    Le stock est celui de `calcul_stock_cultures` (la source de /stats et de
    `stock_global`) : une culture végétative entièrement récoltée n'y figure plus,
    une reproductrice cueillie y reste, la cueillette ne retire pas le pied. Les
    parcelles viennent de `calcul_occupation_parcelles`, la lecture de /plan.
    `present` est toujours vrai : « aucune culture en place » est une réponse."""
    stocks = _stock.calcul_stock_cultures(db, potager_id=ctx.potager_id)
    actives = sorted(
        (fiche for fiche in stocks.values() if fiche.stock_plants > 0),
        key=lambda fiche: fiche.culture,
    )
    parcelles_par_culture: dict[str, list[str]] = {}
    for nom, entrees in _parcelles.calcul_occupation_parcelles(db, potager_id=ctx.potager_id).items():
        for entree in entrees:
            if nom and nom not in parcelles_par_culture.setdefault(entree["culture"], []):
                parcelles_par_culture[entree["culture"]].append(nom)
    lots = _stock.calcul_lots_pepiniere(db, potager_id=ctx.potager_id)
    en_pepiniere: dict[str, int] = {}
    for lot in lots:
        restant = (lot.get("stock_residuel_godet") or 0) + _stock.graines_restantes(lot)
        if restant > 0 and lot.get("culture"):
            en_pepiniere[lot["culture"]] = en_pepiniere.get(lot["culture"], 0) + 1
    return {
        "present": True,
        "cultures": [
            {
                "culture": fiche.culture,
                "stock": fiche.stock_plants,
                "unite": fiche.unite,
                "parcelles": parcelles_par_culture.get(fiche.culture, []),
            }
            for fiche in actives[:MAX_LIGNES_AFFICHEES]
        ],
        "nb": len(actives),
        "pepiniere": [{"culture": culture, "lots": nb} for culture, nb in sorted(en_pepiniere.items())],
    }


@catalogue_sql.enregistrer("varietes_culture")
def _agreger_varietes_culture(db: Session, ctx: TenantContext, culture: str) -> dict:
    """[US-245 / CA4, CA5, CA7] Les variétés d'une culture, avec les pieds en place
    de chacune — `utils/stock.calcul_stock_varietes`, la lecture de l'écran Stocks
    du web. Les variétés encore en godet sont comptées à part : ce ne sont pas des
    pieds en place."""
    lignes = [v for v in _stock.calcul_stock_varietes(db, potager_id=ctx.potager_id)
              if _normaliser(v["culture"]) == _normaliser(culture)]
    varietes: list[dict] = []
    for ligne in lignes:
        if ligne["etat"] == "pep":
            varietes.append({"variete": ligne["variete"], "stock": 0, "unite": ligne["unite"],
                             "en_pepiniere": ligne["stock_actuel"]})
        else:
            varietes.append({"variete": ligne["variete"], "stock": ligne["stock_actuel"],
                             "unite": ligne["unite"], "en_pepiniere": 0})
    return {"present": True, "culture": culture, "varietes": varietes[:MAX_LIGNES_AFFICHEES],
            "nb": len(varietes)}


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


@catalogue_sql.enregistrer("prediagnostic_symptome")
def _agreger_prediagnostic(db: Session, ctx: TenantContext, culture: str, description: str) -> dict:
    """[US-165 / CA3, CA5, CA8, CA9] Des pistes ordonnées — à zéro jeton.

    Délègue à `app.services.prediagnostic.prediagnostic`, qui porte la recherche
    plein texte, le croisement avec les bioagresseurs de la culture et les cinq
    issues. **Aucune requête n'est réécrite ici** : la même règle que pour
    `bioagresseurs_culture` (US-173 / CA11).

    ⚠️ Le POIDS des arêtes ne figure PAS dans l'agrégat, et c'est délibéré
    (CA2) : ce qui n'est pas transmis ne peut pas être affiché comme un
    pourcentage. L'ordre des pistes porte à lui seul la plausibilité relative.

    `present` est vrai dès qu'une piste sort — les trois issues d'ignorance
    produisent chacune leur phrase et rendent `present=False`, ce qui laisse la
    cascade décider (US-170 / CA18 : une phrase produite reste une réponse).
    """
    resultat = svc_prediagnostic.prediagnostic(
        db, description, culture, potager_id=ctx.potager_id
    )
    return {
        "present": bool(resultat.pistes),
        "issue": resultat.issue,
        "culture": resultat.culture,
        "symptome": resultat.symptome,
        "entrees": [
            {
                "bioagresseur": piste.bioagresseur,
                "categorie": piste.categorie,
                "frequence": piste.frequence,
            }
            for piste in resultat.pistes
        ],
        "nb": len(resultat.pistes),
        "reserve": resultat.reserve,
        "sources": list(resultat.sources),
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


def _accords_action(action: Optional[str]) -> tuple[str, dict[str, str]]:
    libelle, genre = LIBELLES_ACTION.get(action or "", (action or "geste", "f"))
    return libelle, {"aucun": "aucun" if genre == "m" else "aucune", "e": "" if genre == "m" else "e"}


def _pluriel_action(action: Optional[str], nb: float) -> str:
    """« 1 arrosage », « 4 arrosages », « 2 mises en godet », « 3 semis »."""
    libelle, _ = _accords_action(action)
    if nb < 2:
        return libelle
    premier, _, reste = libelle.partition(" ")
    if not premier.endswith(("s", "x")):
        premier += "s"
    return f"{premier} {reste}".strip()


def _rendu_nombre_occurrences(params: Parametres, agregat: dict) -> str:
    libelle, accords = _accords_action(params.action)
    valeurs = {"periode": agregat["periode"]}
    if params.culture:
        valeurs["culture"] = _sur(params.culture)
    if not agregat["nb"]:
        cle = "nombre_occurrences_vide" if params.culture else "nombre_occurrences_vide_sans_culture"
        return _remplir(GABARITS[cle], valeurs | accords | {"action": libelle})
    cle = "nombre_occurrences" if params.culture else "nombre_occurrences_sans_culture"
    texte = _remplir(GABARITS[cle], valeurs | {
        "nb": agregat["nb"], "action": _pluriel_action(params.action, agregat["nb"]),
    })
    if params.action in ("perte", "perte_godet") and agregat["pieces"]:
        texte += f" Au total : {agregat['pieces']:g} {_sur(agregat['unite_pieces'])} perdu(s)."
    return texte


def _texte_geste(ligne: dict, avec_culture: bool = True, avec_action: bool = True) -> str:
    """Un geste en une ligne : ce qui est saisi est dit, ce qui ne l'est pas est tu."""
    libelle, _ = _accords_action(ligne["action"])
    morceaux = []
    if avec_action:
        cible = f" de {_sur(ligne['culture'])}" if avec_culture and ligne["culture"] else ""
        morceaux.append(libelle + cible)
    elif avec_culture and ligne["culture"]:
        morceaux.append(_sur(ligne["culture"]))
    if ligne["variete"]:
        morceaux.append(f"variété {_sur(ligne['variete'])}")
    if ligne["produit"]:
        morceaux.append(f"produit : {_sur(ligne['produit'])}")
    if ligne["quantite"]:
        morceaux.append(f"{ligne['quantite']:g} {_sur(ligne['unite'])}".strip())
    if ligne["parcelle"]:
        morceaux.append(f"parcelle {_sur(ligne['parcelle'])}")
    return " — ".join(morceaux)


def _rendu_historique_action(params: Parametres, agregat: dict) -> str:
    if not agregat["nb"]:
        return _rendu_nombre_occurrences(params, agregat)
    lignes = [
        "  • {} : {}".format(
            f"{ligne['date']:%d/%m/%Y}" if ligne["date"] else "date inconnue",
            _texte_geste(ligne, avec_culture=not params.culture, avec_action=False),
        ).rstrip(" :")
        for ligne in agregat["lignes"]
    ]
    cle = "historique_action" if params.culture else "historique_action_sans_culture"
    texte = _remplir(GABARITS[cle], {
        "nb": agregat["nb"], "action": _pluriel_action(params.action, agregat["nb"]),
        "culture": _sur(params.culture), "periode": agregat["periode"],
        "lignes": _lignes_avec_reste(lignes, agregat["nb"]),
    })
    if params.action in ("perte", "perte_godet"):
        total = sum(ligne["quantite"] or 0 for ligne in agregat["lignes"])
        if total and agregat["nb"] == len(agregat["lignes"]):
            texte += f"\nAu total : {total:g} perdu(s)."
    return texte


def _rendu_journal_periode(params: Parametres, agregat: dict) -> str:
    periode = agregat["periode"]
    if not agregat["nb"]:
        return _remplir(GABARITS["journal_periode_vide"], {"periode": periode})
    if not agregat["lignes"]:
        resume = ", ".join(
            f"{nb} {_pluriel_action(action, nb)}"
            for action, nb in sorted(agregat["par_type"].items(), key=lambda t: (-t[1], str(t[0])))
        )
        return _remplir(GABARITS["journal_periode_resume"], {
            "periode": periode, "nb": agregat["nb"], "resume": resume,
        })
    jours = sorted({ligne["date"].date() for ligne in agregat["lignes"]})
    lignes: list[str] = []
    for jour in jours:
        if len(jours) > 1:
            lignes.append(f"{jour:%d/%m/%Y} :")
        lignes += [
            f"  • {_texte_geste(ligne)}" for ligne in agregat["lignes"] if ligne["date"].date() == jour
        ]
    return _remplir(GABARITS["journal_periode"], {
        "periode": periode, "nb": agregat["nb"], "lignes": "\n".join(lignes),
    })


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


def _poids_lisible(poids_g: float) -> str:
    valeur, unite = _stock.poids_lisible(poids_g)
    return f"{valeur:g} {unite}"


def _rendu_classement_recoltes(params: Parametres, agregat: dict) -> str:
    """[US-248] « Quelle culture a le plus produit ? » classe ; « combien de kg ai-je
    récoltés ? » donne le total. Dans les deux cas, ce qui se compte en pièces est
    présenté à part, avec son unité, et jamais additionné aux kilos [CA3]."""
    if not agregat["present"]:
        return _remplir(GABARITS["recoltes_aucune"], {"periode": agregat["periode"]})
    lignes_pieces = _lignes_avec_reste(
        [f"  • {_sur(culture)} — {_stock.quantite_lisible(total, unite):g} {unite}"
         for (culture, unite), total in agregat["pieces"]],
        agregat["nb_pieces"],
    )
    if not agregat["cultures"]:
        return _remplir(GABARITS["recoltes_pieces_seules"], {
            "periode": agregat["periode"], "lignes": lignes_pieces,
        })
    if re.search(r"\bcombien\b", params.normalisee):
        texte = _remplir(GABARITS["total_recoltes"], {
            "total": _poids_lisible(agregat["total_g"]), "periode": agregat["periode"],
        })
    else:
        lignes = _lignes_avec_reste(
            [f"  {rang}. {_sur(culture)} — {_poids_lisible(poids)}"
             for rang, (culture, poids) in enumerate(agregat["cultures"], start=1)],
            agregat["nb"],
        )
        texte = _remplir(GABARITS["classement_recoltes"], {"periode": agregat["periode"], "lignes": lignes})
    if agregat["pieces"]:
        texte += "\n" + _remplir(GABARITS["recoltes_pieces"], {"lignes": lignes_pieces})
    return texte


def _rendu_potager_actif(params: Parametres, agregat: dict) -> str:
    """[US-249] Le nom du potager actif ; avec plusieurs potagers, les autres et
    la commande pour en changer. « Combien de potagers ? » donne le nombre."""
    if not agregat["present"]:
        return GABARITS["potager_actif_inconnu"]
    if re.search(r"\bcombien\b", params.normalisee):
        if agregat["nb"] <= 1:
            return _remplir(GABARITS["potagers_nombre_un"], {"actif": _sur(agregat["actif"])})
        noms = [f"{_sur(agregat['actif'])} (actif)"] + [_sur(nom) for nom in agregat["autres"]]
        return _remplir(GABARITS["potagers_nombre"], {"nb": agregat["nb"], "liste": ", ".join(noms)})
    texte = _remplir(GABARITS["potager_actif"], {"actif": _sur(agregat["actif"])})
    if agregat["autres"]:
        texte += " " + _remplir(GABARITS["potager_actif_autres"], {
            "autres": ", ".join(f"« {_sur(nom)} »" for nom in agregat["autres"]),
        })
    return texte


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


def _rendu_liste_parcelles(params: Parametres, agregat: dict) -> str:
    if not agregat["present"]:
        return "Je n'ai aucune parcelle enregistrée dans ce potager."
    lignes = _lignes_avec_reste(
        [f"  • {_sur(nom)}{' (pépinière)' if pepiniere else ''}" for nom, pepiniere in agregat["parcelles"]],
        agregat["nb"],
    )
    return _remplir(GABARITS["liste_parcelles"], {"nb": agregat["nb"], "lignes": lignes})


def _rendu_attributs_parcelle(params: Parametres, agregat: dict) -> str:
    nom = _sur(agregat["parcelle"])
    valeurs = agregat["valeurs"]
    if len(valeurs) == 1:
        cle, valeur = next(iter(valeurs.items()))
        libelle = ATTRIBUTS_PARCELLE[cle][0]
        if valeur is None:
            return _remplir(GABARITS["attribut_parcelle_vide"], {
                "libelle": libelle[0].upper() + libelle[1:], "parcelle": nom, "cle": cle})
        return f"{libelle[0].upper() + libelle[1:]} de {nom} : {_sur(valeur)}."
    lignes = "\n".join(
        f"  • {ATTRIBUTS_PARCELLE[cle][0]} : {_sur(valeur) if valeur is not None else 'non renseigné'}"
        for cle, valeur in valeurs.items()
    )
    return _remplir(GABARITS["attribut_parcelle"], {"parcelle": nom, "lignes": "\n" + lignes}).replace("— \n", "—\n")


def _rendu_parcelles_filtrees(params: Parametres, agregat: dict) -> str:
    if not agregat["present"]:
        return "Je n'ai aucune parcelle enregistrée dans ce potager."
    if not agregat["nb"]:
        texte = _remplir(GABARITS["parcelles_filtrees_aucune"], {
            "libelle": agregat["libelle"], "total": agregat["total"]})
    else:
        lignes = _lignes_avec_reste(
            [f"  • {_sur(p['nom'])}" + (f" ({p['detail']})" if p["detail"] else "")
             for p in agregat["parcelles"]],
            agregat["nb"],
        )
        texte = _remplir(GABARITS["parcelles_filtrees"], {
            "nb": agregat["nb"], "libelle": agregat["libelle"], "total": agregat["total"], "lignes": lignes})
    if agregat["non_renseignees"]:
        texte += f"\n_{agregat['non_renseignees']} parcelle(s) sans cette information renseignée._"
    return texte


def _rendu_cultures_en_place(params: Parametres, agregat: dict) -> str:
    morceaux: list[str] = []
    if agregat["nb"]:
        lignes = []
        for fiche in agregat["cultures"]:
            quantite = _stock.quantite_lisible(fiche["stock"], fiche["unite"])
            ou = f" — {', '.join(_sur(n) for n in fiche['parcelles'])}" if fiche["parcelles"] else ""
            lignes.append(f"  • {_sur(fiche['culture'])} : {quantite:g} {fiche['unite']}{ou}")
        morceaux.append(_remplir(GABARITS["cultures_en_place"], {
            "nb": agregat["nb"], "lignes": _lignes_avec_reste(lignes, agregat["nb"])}))
    if agregat["pepiniere"]:
        morceaux.append("En pépinière : " + ", ".join(
            f"{_sur(p['culture'])} ({p['lots']} lot(s))" for p in agregat["pepiniere"]) + ".")
    return "\n\n".join(morceaux) if morceaux else GABARITS["cultures_en_place_aucune"]


def _rendu_varietes_culture(params: Parametres, agregat: dict) -> str:
    culture = _sur(agregat["culture"])
    if not agregat["nb"]:
        return _remplir(GABARITS["varietes_culture_aucune"], {"culture": culture})
    if re.search(r"\bcombien\b", params.normalisee):
        return _remplir(GABARITS["varietes_culture_nombre"], {"nb": agregat["nb"], "culture": culture})
    lignes = []
    for v in agregat["varietes"]:
        nom = _sur(v["variete"] or _stock.LABEL_VARIETE_NON_PRECISEE)
        detail = f"{_stock.quantite_lisible(v['stock'], v['unite']):g} {v['unite']} en place" if v["stock"] else ""
        if v["en_pepiniere"]:
            detail = (detail + " · " if detail else "") + f"{v['en_pepiniere']:g} en pépinière"
        lignes.append(f"  • {nom} : {detail or 'aucun pied en place'}")
    return _remplir(GABARITS["varietes_culture"], {
        "nb": agregat["nb"], "culture": culture, "lignes": _lignes_avec_reste(lignes, agregat["nb"])})


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


def _rendu_prediagnostic(params: Parametres, agregat: dict) -> str:
    """[US-165 / CA4, CA5, CA6, CA7] Gabarit assemblé, jamais rédigé par un modèle.

    Rien ici ne peut affirmer : la seule tournure disponible est
    `svc_prediagnostic.FORMULE_EVOCATION`, portée par les gabarits. Rien ici ne
    peut prescrire non plus : l'agrégat ne porte ni produit ni dose, faute de
    colonne où les stocker (CA7) — l'impossibilité est structurelle, pas
    rédactionnelle.

    L'ordre des lignes EST l'information de plausibilité. Aucun nombre ne
    l'accompagne (CA2) : un pourcentage se lirait comme une probabilité mesurée.
    """
    culture = _sur(agregat["culture"])
    issue = agregat["issue"]
    if issue == svc_prediagnostic.ISSUE_CULTURE_SANS_FICHE:
        return _remplir(GABARITS["prediagnostic_culture_sans_fiche"], {"culture": culture})
    if issue == svc_prediagnostic.ISSUE_SYMPTOME_INCONNU:
        return GABARITS["prediagnostic_symptome_inconnu"]
    if issue == svc_prediagnostic.ISSUE_AUCUN_CROISEMENT:
        return _remplir(GABARITS["prediagnostic_aucun_croisement"], {"culture": culture})

    lignes = [
        f"  • {_sur(entree['bioagresseur'])} — {_sur(entree['categorie'])}, "
        f"{_sur(entree['frequence'])} sur cette culture"
        for entree in agregat["entrees"]
    ]
    gabarit = (
        GABARITS["prediagnostic_unique"]
        if issue == svc_prediagnostic.ISSUE_PISTE_UNIQUE
        else GABARITS["prediagnostic"]
    )
    texte = _remplir(gabarit, {
        "culture": culture,
        "symptome": _sur(agregat["symptome"]),
        "lignes": "\n".join(lignes),
    })
    # [CA6] La réserve d'abord — elle porte sur ce qui vient d'être dit — puis
    # l'attribution. Ni l'une ni l'autre ne passe par `_remplir` : la première
    # est la phrase d'US-140/CA8 mot pour mot, la seconde un nom de source, et
    # les renormaliser reviendrait à les retoucher.
    if agregat["reserve"]:
        texte = f"{texte}\n\n{agregat['reserve']}"
    if agregat["sources"]:
        texte = f"{texte}\n\n_D'après : {', '.join(agregat['sources'])}_"
    return texte


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
    # Paramètres qui, s'ils sont présents, retirent la question à cette famille :
    # « combien de rangs de carottes sur la parcelle nord » nomme une culture, ce
    # n'est pas la caractéristique de la parcelle qui est demandée.
    incompatible: tuple[str, ...] = ()


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


# [US-165] Ce qui retire une phrase au pré-diagnostic. Deux natures, et il faut
# les deux :
#
# 1. `_EXCLUT_SAVOIR` — une question qui demande une EXPLICATION n'attend pas
#    une liste de pistes. « mes tomates ont le cul noir » décrit et appelle un
#    pré-diagnostic ; « POURQUOI mes tomates ont le cul noir ? » demande la
#    cause expliquée, que la fiche d'agronomie d'US-140 rend bien mieux à
#    l'étage 2. Les deux se ressemblent à un mot près, et ce mot tranche.
#    Le motif partagé est repris tel quel plutôt que recopié : il exclut aussi
#    « maladie », ce qui convient ici — une phrase qui NOMME la maladie ne
#    décrit plus un symptôme, elle avance déjà une conclusion.
#
# 2. La SAISIE d'observation — elle rapporte un fait au lieu d'en demander la
#    cause. « j'ai observé des taches brunes sur les tomates » doit
#    s'enregistrer. Le routeur l'attrape déjà avant nous (les verbes de geste y
#    sont testés en tête) ; ceci est la défense en profondeur, pour la phrase
#    qui l'atteindrait autrement — même garde qu'US-173 / CA4.
#
# La question d'INVENTAIRE (« qu'est-ce qui attaque mes poireaux »), elle, n'est
# pas exclue ici : c'est l'ORDRE des familles qui la lui retire. L'écrire aux
# deux endroits ferait diverger la frontière au premier ajustement.
_EXCLUT_PREDIAGNOSTIC = re.compile(
    _EXCLUT_SAVOIR.pattern
    + r"|\bobserve\b|\bobservee?s?\b|\bconstate\b|\bconstatee?s?\b"
    + r"|\bremarque\b|\bj ai vu\b|\bjai vu\b|\bj ai note\b|\btraite\b"
    + r"|\bpulverise\b"
)


# [US-246] « combien de fois » ou « combien d'<un geste du référentiel> » : le motif
# s'ancre sur le NOM du geste, tiré des synonymes d'`ACTION_MAP` (pas de second
# référentiel). Un « combien » seul laisserait passer « combien de physalis ai-je
# récolté » — culture inconnue — qui serait alors comptée toutes cultures confondues.
_NOMS_GESTE = "|".join(sorted(
    {re.escape(_normaliser(synonyme)) for synonymes in ACTION_MAP.values() for synonyme in synonymes
     if len(_normaliser(synonyme)) >= 4},
    key=len, reverse=True,
))
_MOTIF_NOMBRE_OCCURRENCES = re.compile(
    r"\b(?:combien|nombre) (?:de fois\b|(?:d |de |des |du )(?:" + _NOMS_GESTE + r"))"
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
        # [US-173] Volontairement spécifique : le vocabulaire de l'agression ne
        # se confond avec aucune autre famille, et le placer haut évite qu'une
        # famille plus large ne capte « quelles maladies sur mes tomates » pour
        # servir un inventaire de parcelles.
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
        # [US-165] APRÈS `bioagresseurs_culture`, et l'ordre est le seul point
        # d'articulation entre les deux familles.
        #
        # Elles se ressemblent — même culture, même référentiel — mais ne
        # répondent pas à la même demande : « qu'est-ce qui attaque mes pommes
        # de terre » demande l'INVENTAIRE de ce qui pourrait arriver ; « mes
        # tomates ont des taches marron » DÉCRIT ce qu'on voit et attend des
        # pistes.
        #
        # L'inventaire passe donc d'abord, sans exception ni carve-out : son
        # motif est étroit, il exige le vocabulaire de l'agression, et US-173
        # garantit par test qu'aucune famille ne le précède. Le prix de cet
        # ordre est connu et mesuré — deux formulations du corpus de mesure
        # (« des petites bêtes rayées jaune et noir sur mes pommes de terre »,
        # « des bestioles noires collées en grappe ») reçoivent l'inventaire
        # plutôt qu'un pré-diagnostic. Aucune des 19 entrées du périmètre v1
        # n'est concernée, et l'inventaire reste une réponse juste.
        #
        # L'alternative — passer devant et carver l'inventaire par `exclut` —
        # a été essayée : elle demande de prévoir toutes les formes de la
        # question d'inventaire (« quelles bestioles sur mes poireaux »,
        # « qui mange mes poireaux »), donc de réécrire chez nous le motif
        # d'US-173. Deux définitions de la même frontière, et la divergence au
        # premier ajustement.
        nom="prediagnostic_symptome",
        # [US-165 / CA9] Comme `bioagresseurs_culture`, cette réponse dérive du
        # référentiel PARTAGÉ et non des évènements du potager : `NATURE_JOURNAL`
        # est déclarée au titre de l'arbitrage « invalider large », qui ne coûte
        # qu'un recalcul SQL. Un tuple vide produirait le même effet sans le
        # dire, et se lirait comme un oubli.
        dependances=(NATURE_JOURNAL,),
        agregation="prediagnostic_symptome",
        motif=re.compile(
            # Le vocabulaire du SYMPTÔME, celui du jardinier — pas celui de
            # l'agronome, qui nomme déjà la cause et relève d'une autre famille.
            r"\btaches?\b|\bpoudre blanche\b|\bpoudreux\b|\bfarineu|\bfeutrage\b|"
            r"\bmoisissure\b|\bcul noir\b|\bpourri|\bmoisi\b|"
            r"\bjaunit\b|\bjaunissent\b|\bjaunissement\b|\bpalissent\b|\bdecolore|"
            r"\bfletri|\bfanent\b|\bfane\b|\bfond sur place\b|\bfondent\b|"
            r"\btrous?\b|\btroue|\bcrible|\bmange|\bgrignote|\bdevore|\bnervures\b|"
            r"\bgaleries?\b|\bvereu|\bvers blancs\b|\bmineuse|\basticots\b|"
            r"\benroulent\b|\benroulee|\bcloquee|\bmarbree|\bdifforme|\bcrochu|"
            r"\bfourchue|\bfendue|\bfendent\b|\beclate|\bcraquel|"
            r"\bmolles?\b|\brabougri|\bboursoufle|\brenflement|"
            r"\bamer|\bcreux\b|\bsans gout\b|\bpiquant|"
            r"\bbetes\b|\bbestioles\b|\bpucerons?\b|\blimaces?\b|\bchenilles?\b|"
            r"\btoiles?\b|\baltises?\b|\bdoryphores?\b|\bmiellat\b|\bcollantes?\b|"
            r"\bne levent pas\b|\bmal leve\b|\bpas leve\b|\bmonte en graine\b|"
            r"\bmontaison\b|\bcoulure\b|\bavort|"
            r"\bfleurs? qui tombent\b|\bperdent (?:toutes )?leurs fleurs\b|"
            r"\btraits orange\b|\brouille\b|\bpustules?\b|\betiole|\bfilants?\b"
        ),
        exclut=_EXCLUT_PREDIAGNOSTIC,
        exige=("culture",),
        # La DESCRIPTION est la question elle-même : c'est sur elle que porte la
        # recherche plein texte, mot pour mot, sans reformulation ni extraction.
        # Redérivée à chaque service (`servir_aiguillage` repasse la phrase
        # réelle), donc deux symptômes différents sur la même culture ne peuvent
        # pas se servir la réponse l'un de l'autre depuis le cache.
        arguments=lambda p: {"culture": p.culture, "description": p.question},
        rendu=_rendu_prediagnostic,
    ),
    Famille(
        # [US-244] AVANT `pepiniere` et `occupation_parcelle` : « quelle est
        # l'exposition de la parcelle nord ? » nomme une parcelle et recevait la
        # liste de ses cultures — la seule famille qui rendait une réponse FAUSSE
        # plutôt qu'absente (mesure du 21/10/2026).
        nom="attributs_parcelle",
        dependances=(NATURE_PLAN,),
        agregation="attributs_parcelle",
        motif=re.compile("|".join(motif.pattern for _, motif in ATTRIBUTS_PARCELLE.values())),
        exclut=_EXCLUT_SAVOIR,
        exige=("parcelle",),
        incompatible=("culture",),
        arguments=lambda p: {"parcelle": p.parcelle, "attributs": _attributs_cites(p.normalisee)},
        rendu=_rendu_attributs_parcelle,
    ),
    Famille(
        nom="parcelles_filtrees",
        dependances=(NATURE_PLAN,),
        agregation="parcelles_filtrees",
        motif=re.compile(
            r"\b(?:quelles?|liste\w*|combien|affiche\w*|montre\w*)\b.*\bpepinieres\b|^(?:mes )?pepinieres$|"
            # « combien de pépinière ? » (singulier) = combien de PARCELLES pépinière ;
            # « combien de lots en pépinière » garde le gabarit du contenu.
            r"\bcombien (?:de |d )?(?:parcelles? |planches? )?(?:en )?pepinieres?\b|"
            r"\b(?:parcelles?|planches?)\b.*(?:\bpaill\w*|\babrit\w*|\bsous (?:abri|serre|tunnel|voile|chassis)\b|"
            r"\bplein soleil\b|\bmi ombre\b|\bombre\b|\bombragees?\b|\bau soleil\b)"
        ),
        exclut=_EXCLUT_SAVOIR,
        exige=(),
        arguments=lambda p: dict(zip(("filtre", "libelle"), _filtre_cite(p.normalisee) or ("pepiniere", "en pépinière"))),
        rendu=_rendu_parcelles_filtrees,
    ),
    Famille(
        # [US-245] L'inventaire du potager, sans culture ni parcelle nommée.
        nom="cultures_en_place",
        dependances=(NATURE_STOCK, NATURE_RECOLTE, NATURE_SEMIS, NATURE_PLAN, NATURE_PEPINIERE),
        agregation="cultures_en_place",
        motif=re.compile(
            r"\bqu est ce que je cultive\b|\bce que je cultive\b|\bje cultive quoi\b|"
            r"\bquelles? (?:sont )?(?:mes |les )?cultures\b|"
            r"\b(?:liste\w*|affiche\w*|montre\w*|donne\w*)(?: moi)?(?: la liste)?(?: de| des)? (?:mes|les) cultures\b|"
            r"\bcultures? (?:en place|actuelles?|en cours|plantees?)\b"
        ),
        exclut=_EXCLUT_SAVOIR,
        exige=(),
        incompatible=("culture",),
        arguments=lambda p: {},
        rendu=_rendu_cultures_en_place,
    ),
    Famille(
        # [US-245] Les variétés d'UNE culture — pas « quelles variétés planter ? »,
        # qui est une question de conseil : une marque de possession est exigée.
        nom="varietes_culture",
        dependances=(NATURE_STOCK, NATURE_SEMIS, NATURE_PLAN, NATURE_PEPINIERE),
        agregation="varietes_culture",
        motif=re.compile(
            r"^(?=.*\b(?:j ai|ai je|mes|mon|ma|combien|en place|cultive\w*|potager|plante\w*)\b).*\bvarietes?\b"
        ),
        exclut=re.compile(
            _EXCLUT_SAVOIR.pattern + r"|\bplanter\b|\bsemer\b|\bchoisir\b|\brecommand\w*|\bconseill\w*|"
            r"\bmeilleur\w*|\bresistan\w*|\bexistent?\b|\bexiste\b"
        ),
        exige=("culture",),
        arguments=lambda p: {"culture": p.culture},
        rendu=_rendu_varietes_culture,
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
        # [US-248] « Quelle culture a le plus produit ? », « combien de kg ai-je
        # récoltés cette année ? » : aucune culture nommée — dès qu'une l'est, ce
        # sont `total_recolte` et `rendement_saison` qui répondent, plus précisément.
        nom="classement_recoltes",
        dependances=(NATURE_RECOLTE, NATURE_STOCK),
        agregation="classement_recoltes",
        motif=re.compile(
            r"\bmeilleures? recoltes?\b|\bquelles? cultures? (?:a|ont) (?:le |la )?(?:plus|mieux) (?:produit|donne|rapporte|recolte)\b|"
            r"\bcultures? (?:la|les) plus (?:productives?|rentables?)\b|\bqu est ce qui a (?:le )?(?:plus|mieux) (?:produit|donne)\b|"
            r"\bclassement\b.*\b(?:recoltes?|cultures?)\b|"
            r"\bcombien (?:de |d )?(?:kg|kilos?|kilogrammes?)\b.*\b(?:recolt|cueilli|produit)|"
            r"\bcombien (?:ai je|j ai) (?:recolte|cueilli)\b|\bpoids total\b.*\brecolt"
        ),
        exclut=_EXCLUT_SAVOIR,
        incompatible=("culture",),
        exige=(),
        arguments=lambda p: {"periode": _periode_saison(p.periode)},
        rendu=_rendu_classement_recoltes,
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
        # [US-246] Compter un geste : « combien de fois j'ai arrosé », « combien
        # d'arrosages ce mois-ci », « combien de pertes de carottes ». APRÈS
        # `total_recolte`, `pieds_actifs` et les stocks, qui prennent « combien de
        # haricots récoltés », « combien de plants » et « combien il me reste » :
        # ce motif large (un comptage + un geste reconnu) ne leur vole rien.
        nom="nombre_occurrences",
        dependances=(NATURE_JOURNAL,),
        agregation="nombre_occurrences",
        motif=_MOTIF_NOMBRE_OCCURRENCES,
        exclut=re.compile(_EXCLUT_SAVOIR.pattern + r"|\bil me reste\b|\bdernier\w*\b|\bparcelles?\b"),
        exige=("action",),
        arguments=lambda p: {"action": p.action, "culture": p.culture, "periode": _periode_saison(p.periode)},
        rendu=_rendu_nombre_occurrences,
    ),
    Famille(
        # [US-246] L'historique d'un type de geste : « quels traitements ai-je
        # faits sur les haricots ». Le motif exige une tournure de LISTE (ou une
        # demande explicite) ET un geste reconnu ; sans période citée, c'est tout
        # le journal du geste, plafonné.
        nom="historique_action",
        dependances=(NATURE_JOURNAL,),
        agregation="historique_action",
        motif=re.compile(
            r"\bquel(?:le)?s? \w+ (?:ai je|j ai|ont ete|a t on)\b|"
            r"\b(?:liste|lister|montre|affiche|donne)\w*(?: moi)? (?:mes|les|tous mes|tous les)\b|"
            r"\bhistorique d\w* \w+"
        ),
        exclut=_EXCLUT_SAVOIR,
        exige=("action",),
        arguments=lambda p: {"action": p.action, "culture": p.culture, "periode": p.periode},
        rendu=_rendu_historique_action,
    ),
    Famille(
        # [US-247] Ce que j'ai fait sur une période : « qu'ai-je fait hier ».
        # Après `notes_culture` (« qu'avais-je noté »), qui ne parle pas de gestes.
        # Sans période citée, les 7 derniers jours — et la réponse le dit.
        nom="journal_periode",
        dependances=(NATURE_JOURNAL,),
        agregation="journal_periode",
        motif=re.compile(
            r"\bqu ai je fait\b|\bqu est ce que j ai fait\b|\bce que j ai fait\b|\bqu est ce qui s est passe\b|"
            r"\bmes derniers gestes\b|\bmon journal\b"
        ),
        exclut=_EXCLUT_SAVOIR,
        exige=(),
        arguments=lambda p: {"periode": _periode_journal(p.periode), "culture": p.culture},
        rendu=_rendu_journal_periode,
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
        # [US-249] Le potager actif est dans le contexte de chaque message : le
        # demander ne doit coûter ni requête écrite par le modèle, ni modèle de
        # réponse. Pas `_EXCLUT_SAVOIR` : il retire « comment », or « comment
        # s'appelle mon potager ? » EST la question.
        nom="potager_actif",
        dependances=(NATURE_PLAN,),
        agregation="potager_actif",
        motif=re.compile(
            r"\bquel (?:est|c est) (?:mon|le) potager(?: actif| courant| actuel)?\s*$|"
            r"\b(?:mon|le) potager (?:actif|courant|actuel)\b|"
            r"\bsur quel potager (?:je suis|suis je|je travaille|on est|j enregistre)\b|"
            r"\bcomment s appelle (?:mon|le) potager\b|"
            r"\bcombien de potagers?\b"
        ),
        exclut=re.compile(r"\bpourquoi\b|\bfaut il\b|\bdois je\b|\bque faire\b|\bconseils?\b|\bcreer\b|\bsupprimer\b"),
        exige=(),
        arguments=lambda p: {},
        rendu=_rendu_potager_actif,
    ),
    Famille(
        # Avant `occupation_parcelle`, qui exige une parcelle nommée : « combien
        # de parcelles ? » n'en nomme aucune et ne trouvait aucune famille.
        nom="liste_parcelles",
        dependances=(NATURE_PLAN,),
        agregation="liste_parcelles",
        motif=re.compile(
            r"\b(?:combien|nombre)(?: de)? (?:parcelles?|planches?)\b|"
            r"\b(?:liste|lister|affiche\w*|montre\w*|donne\w*)(?: moi)?(?: la liste)?(?: de| des)? (?:mes|les) parcelles\b|"
            r"\bquelles sont (?:mes|les) parcelles\s*$|^(?:mes|les) parcelles\s*$"
        ),
        exclut=_EXCLUT_SAVOIR,
        exige=(),
        arguments=lambda p: {},
        rendu=_rendu_liste_parcelles,
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


def _periode_journal(periode: Periode) -> Periode:
    """[US-247 / CA4] Sans période citée, les 7 derniers jours aujourd'hui compris."""
    if periode.debut is not None or periode.fin is not None:
        return periode
    aujourdhui = _date.today()
    return Periode(
        aujourdhui - timedelta(days=JOURS_JOURNAL_PAR_DEFAUT - 1), aujourdhui,
        f"ces {JOURS_JOURNAL_PAR_DEFAUT} derniers jours", aujourdhui.year,
    )


def _choisir_famille(params: Parametres) -> Optional[Famille]:
    """Première famille dont le motif matche ET dont les paramètres obligatoires
    ont été extraits. Une famille reconnue sans sa culture (« combien j'ai
    récolté ? ») n'est pas servie approximativement : elle n'est pas servie."""
    for famille in FAMILLES:
        if not famille.motif.search(params.normalisee):
            continue
        if famille.exclut is not None and famille.exclut.search(params.normalisee):
            continue
        if any(getattr(params, nom) for nom in famille.incompatible):
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

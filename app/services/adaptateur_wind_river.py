"""
app/services/adaptateur_wind_river.py — Wind River Greens → manifeste [US-161]
--------------------------------------------------------------------------------
Traduit les CSV du jeu de données **Wind River Greens Plant Database** (CC BY 4.0)
en un manifeste au format que `import_referentiel` consomme déjà. Aucun second
mécanisme d'ingestion : l'adaptateur produit un fichier, l'import fait le reste.

Ce module ne touche jamais la base et n'appelle jamais le réseau. Il transforme
des lignes de CSV en un dict — testable sans fichier, sans terminal et sans
PostgreSQL.

Ce qu'on retient de la source, et surtout ce qu'on écarte
---------------------------------------------------------
Le jeu de données est nord-américain, au niveau **cultivar** (1 972 lignes), et
son README annonce un schéma normalisé que les CSV ne respectent pas :
`water_requirement` y porte **579 valeurs distinctes** en texte libre, pas les
trois annoncées. D'où trois décisions, mesurées et non intuitées :

- ✅ **Exposition et besoin en eau** sont retenus. Ce sont des attributs
  qualitatifs de conduite ; leur valeur source, une fois normalisée, est stable
  sur nos cultures (90 des 91 cultivars de tomate portent la même exposition).
- ❌ **La rusticité est écartée.** `usda_zone_min` décrit la zone où la plante
  est *pérenne*, pas celle où on la cultive : les tomates du jeu de données sont
  en « zones 10-11 », sauf Roma en « 4-9 ». Pour des annuelles, c'est faux.
  Dériver `rusticite_min_c` de là produirait un chiffre, et un chiffre faux.
- ❌ **La profondeur de semis est absente** du jeu de données — aucune colonne.
- ✅ **Les DURÉES sont retenues [US-068].** Le délai entre semis et levée
  ou récolte relève de la physiologie de la plante, pas de la latitude : c'est
  précisément pourquoi US-068 ne les décline pas par zone. Trois règles fermées,
  décrites à `construire_calendriers`, bornent ce qu'on en tire.
- ⚠️ **Les FENÊTRES sont retenues sous conditions [US-068, 14/09/2026].**
  `planting_calendar.csv` est en mois × zone USDA. Il n'est PAS rédigé cultivar
  par cultivar : c'est un gabarit par catégorie (10 profils pour 91 tomates, un
  seul pour 84 aromatiques), dont la fin de récolte est une constante de
  catégorie. D'où une table de zones déclarée (`ZONE_USDA_PAR_ZONE`) et six
  règles de rejet, décrites à `construire_fenetres` — ce qui ne les franchit pas
  reste vide, jamais complété. La PLANTATION (`outdoor_transplant_*`) y entre
  depuis l'amendement d'US-068 du 15/09/2026, sous les mêmes règles.

Les associations (`companion_plants.csv`, 21 880 arêtes, réduites à 217 sur notre
périmètre) sont d'abord extraites **brutes** dans un fichier séparé
(`envelopper_associations`) — en anglais, non canonicalisées, exactement comme
l'audit du 01/09/2026 les a trouvées. C'est `curer_associations` [US-163] qui les
rend importables : traduction, rattachement à une culture ou une famille de ce
référentiel, retrait de ce qui n'a pas sa place ou d'un motif recyclé d'une autre
plante, nouvelle détection de contradiction une fois les doublons de libellé
fusionnés. Le résultat rejoint le manifeste principal, bloc `cultures_associations`
— import unique avec les attributs de conduite, même source, même commande.

L'agrégation cultivar → culture
--------------------------------
Nos cultures sont des espèces (« tomate »), la source décrit des cultivars
(« Cherokee Purple »). Il faut donc agréger, et l'agrégation est l'endroit où on
inventerait sans le vouloir. La règle est fermée, lisible et testable :

1. On normalise la valeur de **chaque cultivar** vers le vocabulaire fermé.
2. On retient la valeur majoritaire **seulement si** elle réunit au moins
   `SEUIL_ACCORD` des cultivars qui portent une valeur, et que la culture compte
   au moins `MIN_CULTIVARS` cultivars appariés.
3. Sinon `None` — donc « non renseigné », jamais une moyenne ni un arbitrage.

C'est ce qui écarte la blette : un seul cultivar apparié dans la source, base
trop faible pour conclure. Elle restera à saisir à la main, et c'est le
comportement correct.
"""
from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from collections import Counter, defaultdict
from statistics import median, median_low
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from app.services import attributs_culture as svc_attributs
from app.services import calendrier_cultural as svc_calendrier
from app.services import referentiel_sources as svc_sources

log = logging.getLogger("potager")

#: Part des cultivars devant s'accorder pour qu'une valeur soit retenue.
SEUIL_ACCORD = 0.80

#: En dessous, la base est trop faible pour qu'un accord veuille dire quelque
#: chose — un cultivar unanime avec lui-même n'est pas un consensus.
MIN_CULTIVARS = 3


@dataclass(frozen=True)
class Appariement:
    """
    Comment une de nos cultures se retrouve dans le jeu de données.

    L'appariement croise la **catégorie** et le **nom**, car ni l'une ni l'autre
    ne suffit : chercher « tomato » dans les noms ne trouve que 3 lignes sur 91
    (« Cherokee Purple » ne contient pas le mot), et la catégorie seule confond
    poivrons et piments, concombres et cornichons. C'est le « vrai travail
    technique » annoncé au §5.2 du document de conception : borné, fait une fois,
    et relu ici plutôt que deviné à l'exécution.
    """

    culture: str
    categorie: Optional[str] = None
    inclusion: Optional[str] = None
    exclusion: Optional[str] = None

    def correspond(self, ligne: dict) -> bool:
        if self.categorie and (ligne.get("category") or "").strip() != self.categorie:
            return False
        texte = " ".join(
            (ligne.get(champ) or "") for champ in ("name", "slug", "scientific_name")
        ).lower()
        if self.inclusion and not re.search(self.inclusion, texte):
            return False
        if self.exclusion and re.search(self.exclusion, texte):
            return False
        return True


#: Les dix cultures du périmètre initial (US-140 / CA1), et rien d'autre :
#: l'adaptateur ne peut pas produire un manifeste plus large que ce que l'import
#: accepterait d'écrire (US-161 / CA7).
APPARIEMENTS: tuple[Appariement, ...] = (
    Appariement("tomate", categorie="tomato"),
    Appariement("haricot", categorie="bean", exclusion=r"soy|fava|broad"),
    Appariement("courgette", categorie="squash", inclusion=r"zucchini|courgette"),
    Appariement("chou", categorie="brassica", inclusion=r"\bcabbage\b", exclusion=r"chinese|napa"),
    Appariement("carotte", categorie="root-vegetable", inclusion=r"\bcarrot"),
    # Concombre et cornichon partagent la catégorie `cucumber` : ce sont les
    # motifs de nom qui les séparent, dans un sens puis dans l'autre.
    Appariement("concombre", categorie="cucumber", exclusion=r"pickl|gherkin"),
    Appariement("cornichon", categorie="cucumber", inclusion=r"pickl|gherkin"),
    # `pepper` mélange poivrons doux et piments forts — l'exclusion est ici une
    # question de justesse, pas de confort : un piment n'a pas la conduite d'un
    # poivron.
    Appariement("poivron", categorie="pepper", inclusion=r"bell|sweet|pimento",
                exclusion=r"hot|chili|jalape|habanero|cayenne"),
    Appariement("ail", categorie="allium", inclusion=r"\bgarlic\b", exclusion=r"chive"),
    Appariement("blette", inclusion=r"\bchard\b"),
)

#: [US-068] Appariement ÉTENDU, pour le calendrier seulement : toutes les
#: cultures de `culture_config` qu'on sait retrouver dans la source. Les
#: attributs de conduite et les associations restent sur `APPARIEMENTS` — leur
#: périmètre est celui d'US-161/US-163, et leur curation (traductions de motifs)
#: n'existe que pour les dix cultures initiales.
#:
#: L'ORDRE COMPTE : un cultivar va à la PREMIÈRE culture qui le reconnaît. Le
#: particulier passe donc avant le général (haricot grimpant avant haricot,
#: pâtisson / butternut / potimarron / potiron avant courge, pois gourmand
#: avant petit pois). La catégorie est exigée chaque fois qu'elle discrimine :
#: les noms scientifiques de la source sont par endroits faux (`golden-beet` y
#: est un zinnia, `nelson-carrot` un radis), et les microgreens partagent les
#: noms des légumes. Aucune entrée pour ce que la source ne contient pas
#: (asperge, rhubarbe, épinard perpétuel) : une culture sans cultivar apparié
#: n'a simplement pas de calendrier.
APPARIEMENTS_CALENDRIER: tuple[Appariement, ...] = (
    Appariement("tomate", categorie="tomato"),
    Appariement("haricot grimpant", categorie="bean",
                inclusion=r"\bpole\b|runner|vining|climbing|yard-long|noodle",
                exclusion=r"soy|fava|broad"),
    Appariement("haricot", categorie="bean", exclusion=r"soy|fava|broad"),
    Appariement("courgette", categorie="squash", inclusion=r"zucchini|courgette"),
    Appariement("pâtisson", categorie="squash", inclusion=r"pattypan|scallop"),
    Appariement("butternut", categorie="squash", inclusion=r"butternut"),
    Appariement("potimarron", categorie="squash", inclusion=r"\bkuri\b|hokkaido"),
    Appariement("potiron", categorie="squash", inclusion=r"cucurbita maxima|pumpkin"),
    Appariement("courge", categorie="squash", inclusion=r"squash|cushaw",
                exclusion=r"summer|crookneck|straightneck|marrow|tromboncino|gourd"),
    Appariement("chou de Bruxelles", categorie="brassica", inclusion=r"brussels"),
    Appariement("brocoli", categorie="brassica", inclusion=r"broccoli"),
    Appariement("chou frisé", categorie="brassica", inclusion=r"\bkale\b"),
    Appariement("chou", categorie="brassica", inclusion=r"\bcabbage\b", exclusion=r"chinese|napa"),
    Appariement("carotte", categorie="root-vegetable", inclusion=r"\bcarrot"),
    Appariement("radis", categorie="root-vegetable", inclusion=r"radish|raphanus"),
    Appariement("betterave", categorie="root-vegetable", inclusion=r"\bbeet"),
    Appariement("navet", categorie="root-vegetable", inclusion=r"turnip"),
    Appariement("pomme de terre", categorie="root-vegetable", inclusion=r"solanum tuberosum"),
    Appariement("concombre", categorie="cucumber", exclusion=r"pickl|gherkin"),
    Appariement("cornichon", categorie="cucumber", inclusion=r"pickl|gherkin"),
    Appariement("poivron", categorie="pepper", inclusion=r"bell|sweet|pimento",
                exclusion=r"hot|chili|jalape|habanero|cayenne"),
    Appariement("aubergine", categorie="eggplant"),
    Appariement("melon", categorie="melon", inclusion=r"cucumis melo"),
    Appariement("pastèque", categorie="melon", inclusion=r"citrullus|watermelon"),
    Appariement("pois gourmand", categorie="pea",
                inclusion=r"sugar|snow|snap|carouby|saccharatum|mangetout"),
    Appariement("petit pois", categorie="pea"),
    Appariement("fève", categorie="bean", inclusion=r"vicia faba|fava|broad bean"),
    Appariement("ail", categorie="allium", inclusion=r"\bgarlic\b", exclusion=r"chive"),
    Appariement("échalote", categorie="allium", inclusion=r"shallot|aggregatum"),
    Appariement("poireau", categorie="allium", inclusion=r"\bleek|porrum|ampeloprasum"),
    # La ciboulette chinoise (Allium tuberosum) est une autre espèce.
    Appariement("ciboulette", categorie="allium", inclusion=r"schoenoprasum"),
    Appariement("oignon", categorie="allium", inclusion=r"onion|allium cepa",
                exclusion=r"bunching|fistulosum"),
    Appariement("laitue", categorie="lettuce", inclusion=r"lactuca sativa"),
    Appariement("épinard", categorie="lettuce", inclusion=r"spinacia"),
    Appariement("mâche", categorie="lettuce", inclusion=r"valerianella|corn salad"),
    Appariement("oseille", categorie="lettuce", inclusion=r"rumex"),
    Appariement("roquette", inclusion=r"arugula|eruca", exclusion=r"microgreen"),
    Appariement("mesclun", categorie="lettuce", inclusion=r"greens mix|mesclun"),
    Appariement("blette", inclusion=r"\bchard\b"),
    Appariement("basilic", categorie="herb", inclusion=r"\bbasil", exclusion=r"oregano"),
    Appariement("persil", categorie="herb", inclusion=r"parsley|petroselinum"),
    Appariement("coriandre", categorie="herb", inclusion=r"cilantro|coriandrum"),
    Appariement("thym", categorie="herb", inclusion=r"thyme|thymus"),
    Appariement("menthe", categorie="herb", inclusion=r"\bmint\b|mentha", exclusion=r"marigold"),
    Appariement("romarin", categorie="herb", inclusion=r"rosemar"),
    Appariement("céleri", categorie="herb", inclusion=r"celery|apium"),
    Appariement("fenouil", categorie="herb", inclusion=r"foeniculum vulgare"),
    Appariement("fraise", categorie="berry", inclusion=r"fragaria"),
    Appariement("framboise", categorie="berry", inclusion=r"rubus idaeus"),
    Appariement("capucine", categorie="flower", inclusion=r"tropaeolum"),
)

#: [US-068] Noms de `culture_config` qui désignent la MÊME culture qu'une entrée
#: d'`APPARIEMENTS_CALENDRIER` : ils reçoivent le même calendrier. Décision
#: relue en diff, jamais une similarité calculée — « salade » est, dans ce
#: référentiel, la laitue (même rapprochement que celui déclaré pour US-162).
ALIAS_CALENDRIER: dict[str, str] = {
    "salade": "laitue",
}

# ── Normalisation des valeurs sources vers le vocabulaire fermé ─────────────

#: [US-161 / CA2] `sun_requirement` porte 29 formulations libres. Les plages
#: (« Full sun to partial shade ») sont ramenées à leur **borne haute**, c'est-à-
#: dire à l'optimum d'ensoleillement : le vocabulaire fermé du projet n'a pas de
#: valeur pour « tolère les deux », et c'est l'optimum que le jardinier doit
#: viser. Choix assumé, qui perd l'information de tolérance.
_EXPOSITION_REGLES: tuple[tuple[str, str], ...] = (
    (r"full shade|deep shade", "ombre"),
    (r"full sun", "plein soleil"),
    (r"part(ial)? sun|part(ial)? shade|bright indirect", "mi-ombre"),
)

#: [US-161 / CA2] `water_requirement` porte 579 formulations, dont beaucoup sont
#: des quantités (« 1-1.5 inches per week ») et non des catégories. Les seuils en
#: pouces par semaine sont ceux de la source elle-même, pas une invention : un
#: pouce hebdomadaire est la référence du potager, au-dessus c'est un besoin
#: élevé, en dessous un besoin faible. Aucun chiffre n'est produit ni stocké —
#: seule la catégorie l'est (CA10).
_EAU_REGLES: tuple[tuple[str, str], ...] = (
    (r"^\s*(high|heavy)\b|high\s*[—-]", "élevé"),
    (r"^\s*(low|minimal|drought)\b|drought[- ]tolerant|low\s*[—-]", "faible"),
    (r"^\s*(moderate|medium|regular|average)\b|moderate\s*[—-]", "moyen"),
)

#: Bornes en pouces/semaine, appliquées quand la valeur source est une quantité.
_EAU_SEUIL_ELEVE = 1.5
_EAU_SEUIL_FAIBLE = 1.0


def _quantite_pouces(brut: str) -> Optional[float]:
    """Extrait la borne haute d'une quantité « 1-1.5 inches per week », ou None."""
    trouve = re.search(r"(\d+(?:\.\d+)?)\s*(?:-\s*(\d+(?:\.\d+)?))?\s*inch", brut.lower())
    if not trouve:
        return None
    return float(trouve.group(2) or trouve.group(1))


def normaliser_exposition(brut: Optional[str]) -> Optional[str]:
    """Ramène une exposition source au vocabulaire fermé, ou None si illisible."""
    texte = (brut or "").strip().lower()
    if not texte:
        return None
    for motif, valeur in _EXPOSITION_REGLES:
        if re.search(motif, texte):
            return valeur
    return None


def normaliser_besoin_eau(brut: Optional[str]) -> Optional[str]:
    """Ramène un besoin en eau source au vocabulaire fermé, ou None.

    Deux chemins : une catégorie explicite (« High — consistent moisture »), ou
    une quantité hebdomadaire ramenée à une catégorie par les seuils ci-dessus.
    Une valeur qui ne relève ni de l'un ni de l'autre est laissée à None plutôt
    que rattachée au cas le plus proche."""
    texte = (brut or "").strip().lower()
    if not texte:
        return None
    for motif, valeur in _EAU_REGLES:
        if re.search(motif, texte):
            return valeur
    pouces = _quantite_pouces(texte)
    if pouces is None:
        return None
    if pouces >= _EAU_SEUIL_ELEVE:
        return "élevé"
    if pouces < _EAU_SEUIL_FAIBLE:
        return "faible"
    return "moyen"


NORMALISEURS = {
    "exposition": ("sun_requirement", normaliser_exposition),
    "besoin_eau": ("water_requirement", normaliser_besoin_eau),
}


@dataclass
class ResultatAdaptation:
    """Ce que l'adaptation a réellement produit — la matière du compte rendu."""

    cultivars_apparies: dict[str, int] = field(default_factory=dict)
    attributs_retenus: list[str] = field(default_factory=list)
    #: Attributs écartés faute d'accord suffisant entre cultivars, avec le motif.
    attributs_ecartes: list[str] = field(default_factory=list)
    associations: int = 0
    #: Paires dites bénéfiques par un cultivar et nuisibles par un autre : la
    #: source se contredit, on ne tranche pas à sa place.
    associations_contradictoires: list[str] = field(default_factory=list)
    #: [US-163] Résultat de `curer_associations` — None si aucun compagnon
    #: n'a été fourni (`--sans-associations`).
    curation_associations: "Optional[RapportCuration]" = None
    #: [US-068] Durées retenues / écartées, avec leur motif.
    durees_retenues: list[str] = field(default_factory=list)
    durees_ecartees: list[str] = field(default_factory=list)
    #: [US-068] Fenêtres retenues / écartées, avec leur motif.
    fenetres_retenues: list[str] = field(default_factory=list)
    fenetres_ecartees: list[str] = field(default_factory=list)
    #: [US-068] Cultures dont les fiches parlent d'un semis de fin d'été ou
    #: d'automne que le calendrier source ignore : retenues, mais incomplètes.
    fenetres_incompletes: list[str] = field(default_factory=list)
    #: [US-068 / CA24] Semis en pépinière, délai de repiquage et plantation qui
    #: ne s'enchaînent pas — SIGNALÉS, jamais corrigés.
    fenetres_incoherentes: list[str] = field(default_factory=list)
    #: [US-068] Cultivars appariés par culture pour le calendrier (table étendue).
    cultivars_calendrier: dict[str, int] = field(default_factory=dict)


def _voter(valeurs: list[str]) -> tuple[Optional[str], str]:
    """
    Applique la règle d'agrégation. Retourne (valeur retenue ou None, motif).

    Le motif est destiné au compte rendu : un attribut écarté doit dire
    *pourquoi* il l'est, sans quoi on ne sait pas s'il faut le saisir à la main
    ou corriger l'appariement.
    """
    renseignees = [v for v in valeurs if v]
    if len(renseignees) < MIN_CULTIVARS:
        return None, f"base trop faible ({len(renseignees)} cultivar(s), minimum {MIN_CULTIVARS})"
    majoritaire, occurrences = Counter(renseignees).most_common(1)[0]
    accord = occurrences / len(renseignees)
    if accord < SEUIL_ACCORD:
        return None, f"pas de consensus ({accord:.0%} d'accord, seuil {SEUIL_ACCORD:.0%})"
    return majoritaire, f"{accord:.0%} de {len(renseignees)} cultivars"


def selectionner_cultivars(
    lignes: Iterable[dict], appariements: tuple[Appariement, ...] = APPARIEMENTS
) -> dict[str, list[dict]]:
    """Range les lignes de `varieties.csv` sous celle de nos cultures qu'elles
    décrivent. Une ligne qui n'en décrit aucune est simplement ignorée — le jeu
    de données couvre 1 972 cultivars, notre périmètre en concerne une fraction."""
    par_culture: dict[str, list[dict]] = {a.culture: [] for a in appariements}
    for ligne in lignes:
        for appariement in appariements:
            if appariement.correspond(ligne):
                par_culture[appariement.culture].append(ligne)
                break
    return par_culture


def construire_attributs(
    par_culture: dict[str, list[dict]], resultat: ResultatAdaptation
) -> list[dict]:
    """Produit le bloc `cultures_attributs` du manifeste."""
    entrees: list[dict] = []
    for culture, lignes in par_culture.items():
        resultat.cultivars_apparies[culture] = len(lignes)
        if not lignes:
            continue

        entree: dict[str, Any] = {"culture": culture}
        for cle, (colonne, normaliser) in NORMALISEURS.items():
            valeur, motif = _voter([normaliser(l.get(colonne)) for l in lignes])
            if valeur is None:
                resultat.attributs_ecartes.append(f"{culture}.{cle} — {motif}")
                continue
            # Ceinture et bretelles : la valeur produite doit franchir la même
            # validation que n'importe quelle saisie (CA2). Si elle échoue ici,
            # c'est une règle de normalisation à corriger, pas une valeur à écrire.
            entree[cle] = svc_attributs.normaliser_valeur(cle, valeur)
            resultat.attributs_retenus.append(f"{culture}.{cle} = {valeur} ({motif})")

        if len(entree) > 1:
            entrees.append(entree)
    return entrees


# ── [US-068] Durées du calendrier cultural ───────────────────────────────────

#: Mode de semis d'un cultivar, lu dans `sowing_method` (texte libre).
MODE_PLEINE_TERRE = "pleine_terre"
MODE_PEPINIERE = "pepiniere"
MODE_MIXTE = "mixte"
MODE_NON_SEMIS = "non_semis"


def classer_mode_semis(texte: Optional[str]) -> Optional[str]:
    """
    [US-068] Range la consigne de semis d'un cultivar.

    - « Direct sow … » sans « start indoors » → pleine terre ;
    - « Start (seeds) indoors … » sans « direct sow » → pépinière ;
    - les deux à la fois (« direct sow, or start indoors… ») → mixte ;
    - ni semis ni graine (« Plant cloves… ») → non semis : l'ail se plante en
      caïeux, un délai « de levée » n'y a pas le sens d'une germination ;
    - une multiplication végétative nommée (« Plant seed potatoes », « Plant
      sets », « Transplant crowns », « Start from cuttings ») → non semis aussi,
      même quand le mot « seed » apparaît : un plant de pomme de terre n'est pas
      une graine.
    """
    brut = (texte or "").strip().lower()
    if not brut:
        return None
    direct = bool(re.search(r"direct (sow|seed)", brut))
    abri = bool(re.search(r"start(ed)? (from )?(seeds? )?indoors", brut))
    if direct and abri:
        return MODE_MIXTE
    if direct:
        return MODE_PLEINE_TERRE
    if abri:
        return MODE_PEPINIERE
    if "sow" not in brut and "seed" not in brut:
        return MODE_NON_SEMIS
    if re.search(_MULTIPLICATION_VEGETATIVE, brut):
        return MODE_NON_SEMIS
    return None


#: [US-068] Ce qui se plante sans se semer, tel que la source l'écrit.
_MULTIPLICATION_VEGETATIVE = (
    r"seed potato|\bsets?\b|\bbulbs?\b|\bcrowns?\b|cuttings?|divisions?|\bcloves?\b|purchased plants"
)


def _bornes_jours(texte: Optional[str]) -> Optional[tuple[int, int]]:
    """« 7-14 », « 7-10 days », « 14-21 (sprouting) », « 60 » → (min, max)."""
    nombres = [int(n) for n in re.findall(r"\d+", texte or "")[:2]]
    if not nombres:
        return None
    return min(nombres), max(nombres)


def _semaines_abri(texte: Optional[str]) -> Optional[tuple[int, int]]:
    """« Start indoors 6-8 weeks before last frost » → (42, 56) jours."""
    trouve = re.search(r"indoors\s+(\d+)\s*-\s*(\d+)\s*weeks", (texte or "").lower())
    if trouve is None:
        return None
    return int(trouve.group(1)) * 7, int(trouve.group(2)) * 7


def _agreger_bornes(bornes: list[Optional[tuple[int, int]]]) -> tuple[Optional[tuple[int, int]], str]:
    """
    Fourchette d'une culture à partir de celles de ses cultivars : médiane des
    minima, médiane des maxima. La médiane et non la moyenne — un cultivar
    « baby » à 21 jours ne tire pas la carotte vers le bas.
    """
    valides = [b for b in bornes if b is not None]
    if len(valides) < MIN_CULTIVARS:
        return None, f"base trop faible ({len(valides)} cultivar(s), minimum {MIN_CULTIVARS})"
    jours_min = int(round(median(b[0] for b in valides)))
    jours_max = int(round(median(b[1] for b in valides)))
    return (min(jours_min, jours_max), max(jours_min, jours_max)), f"médiane de {len(valides)} cultivars"


# ── [US-068] Fenêtres du calendrier cultural ─────────────────────────────────

#: [US-068] Zone USDA dont le calendrier est lu pour chaque zone climatique.
#:
#: ⚠️ DÉCISION DÉCLARÉE, À VALIDER — pas une équivalence. Une zone USDA mesure
#: le froid hivernal minimal ; lue comme zone de RUSTICITÉ, la France océanique
#: tomberait en 8-9, soit le calendrier du Texas et de la Géorgie : tomates
#: plantées en avril à Rennes. Mais `planting_calendar.csv` ne se sert de la zone
#: que pour caler ses mois sur la date moyenne de DERNIÈRE GELÉE du printemps —
#: c'est donc sur ce critère, et sur lui seul, que la correspondance se fait :
#: chaque zone climatique reçoit la zone USDA dont le printemps démarre au même
#: moment, de la plus tardive (montagnard) à la plus précoce (méditerranéen).
#: Un seul mois de décalage change une fenêtre : cette table se relit en diff,
#: et la modifier impose de régénérer le manifeste.
ZONE_USDA_PAR_ZONE: dict[str, int] = {
    "oceanique": 7,
    "continental": 6,
    "mediterraneen": 8,
    "montagnard": 4,
}

#: Colonnes source de chaque phase. [US-068 / CA21, amendement du 15/09/2026]
#: `outdoor_transplant_*` est repris pour la fenêtre de PLANTATION — mise en
#: place définitive, lue telle quelle, jamais recalculée depuis le semis en
#: pépinière et le délai de repiquage (CA18).
COLONNES_PHASE: dict[str, tuple[str, str]] = {
    svc_calendrier.PHASE_SEMIS_PEPINIERE: ("indoor_sow_start", "indoor_sow_end"),
    svc_calendrier.PHASE_SEMIS_PLEINE_TERRE: ("direct_sow_start", "direct_sow_end"),
    svc_calendrier.PHASE_PLANTATION: ("outdoor_transplant_start", "outdoor_transplant_end"),
    svc_calendrier.PHASE_RECOLTE: ("harvest_start", "harvest_end"),
}

_MOIS_SOURCE: dict[str, int] = {
    nom: numero for numero, nom in enumerate((
        "january", "february", "march", "april", "may", "june", "july",
        "august", "september", "october", "november", "december",
    ), start=1)
}

def fenetre_source(ligne: dict, phase: str) -> Optional[tuple[int, int]]:
    """Mois (début, fin) d'une phase dans une ligne du calendrier source, ou None
    si la ligne n'en porte pas. Un seul des deux mois renseigné → None."""
    debut, fin = (
        _MOIS_SOURCE.get((ligne.get(colonne) or "").strip().lower())
        for colonne in COLONNES_PHASE[phase]
    )
    if debut is None or fin is None:
        return None
    return debut, fin


def formater_mois(debut: int, fin: int) -> str:
    """(3, 5) → « mars-mai » ; (6, 6) → « juin » — la forme du gabarit d'US-068."""
    if debut == fin:
        return svc_calendrier.MOIS[debut - 1]
    return f"{svc_calendrier.MOIS[debut - 1]}-{svc_calendrier.MOIS[fin - 1]}"


#: [US-068] Part des fiches d'une culture à partir de laquelle la source est
#: jugée contredire son propre calendrier (règles 1 et 6 de construire_fenetres).
SEUIL_COHERENCE = 0.5

#: Modes (lus dans `sowing_method`) qui justifient chaque phase. [CA22] Une
#: plantation est justifiée par tout ce qui passe par une mise en place : élevé
#: à l'abri, mixte, ou planté sans être semé.
_MODES_DE_PHASE: dict[str, frozenset] = {
    "semis_pepiniere": frozenset({MODE_PEPINIERE, MODE_MIXTE}),
    "semis_pleine_terre": frozenset({MODE_PLEINE_TERRE, MODE_MIXTE}),
    "plantation": frozenset({MODE_PEPINIERE, MODE_MIXTE, MODE_NON_SEMIS}),
}

#: [CA23] Ce qui, dans la fiche d'une culture qui ne se sème pas, annonce une
#: plantation d'automne — que le calendrier source, printemps seulement, ignore.
#: « Plant dormant canes in early spring or fall » (framboise) contredit la
#: fenêtre de printemps que le gabarit de catégorie lui donne.
_PLANTATION_AUTOMNE = r"\bor (in )?(the )?fall\b|\bin (the )?fall\b|\bfall plant|autumn|overwinter"

#: Ce qui, dans une fiche, annonce un semis ou une plantation hors printemps.
_SEMIS_TARDIF = (
    r"late summer|mid-summer for fall|\bin (the )?fall\b|\bfall (sow|plant|crop|harvest)"
    r"|autumn|overwinter"
)


def construire_fenetres(
    par_culture: dict[str, list[dict]],
    calendrier: Iterable[dict],
    resultat: ResultatAdaptation,
) -> dict[str, dict[str, dict[str, str]]]:
    """
    [US-068 / CA9] Fenêtres par culture, zone climatique et phase, lues dans
    `planting_calendar.csv`. Retourne `{culture: {zone: {phase: "mars-mai"}}}`.

    Le calendrier source est un GABARIT PAR CATÉGORIE, pas une donnée par
    cultivar : les semis d'une catégorie sont identiques d'un cultivar à l'autre,
    la fin de récolte y est une constante. Six règles fermées bornent ce qu'on
    en tire ; ce qui ne les franchit pas reste vide :

    1. **Ce qui ne se sème pas ne reçoit aucune fenêtre.** La source se contredit
       sur l'ail : `varieties.csv` dit « planted in fall, harvest mid-summer »,
       son calendrier le sème en mars-mai et le récolte de décembre à novembre.
       Dès que la MOITIÉ des fiches classées décrivent une plantation (caïeux,
       plants de pomme de terre, bulbes, griffes, boutures), ses fenêtres de
       semis ET de récolte sont écartées — la récolte aussi, puisque le gabarit
       de la catégorie la calcule depuis un semis qui n'existe pas. [CA23,
       amendement du 15/09/2026] Sa **plantation** reste lue — c'est sa phase —
       sauf si une de ses fiches décrit une plantation d'automne
       (`_PLANTATION_AUTOMNE`) : le gabarit de printemps est alors contredit.
    2. **Jointure par identifiant ET catégorie.** Le slug n'est pas unique dans
       la source (`black-beauty` y est une aubergine, une courgette et un rosier).
    3. **Une fenêtre à cheval sur l'année est rejetée.** Dans ce jeu de données,
       c'est l'artefact d'un début de récolte calculé au-delà de la fin de saison
       fixe de la catégorie — jamais une vraie récolte d'hiver.
    4. **Une phase n'est retenue que si la culture la porte**, c'est-à-dire au
       moins `SEUIL_ACCORD` des cultivars ayant une ligne pour la zone, et au
       moins `MIN_CULTIVARS` : un cultivar semé à l'abri ne met pas toute la
       courgette en pépinière.
    5. **Bornes : médiane basse des débuts, médiane basse des fins** — un mois
       réellement observé, jamais une moyenne ; même esprit que les durées. Une
       médiane dont le début dépasse la fin est écartée.
    6. **Un semis que les fiches de la source ne décrivent pas est écarté.** Le
       gabarit des aromatiques met le fenouil en pépinière, alors que trois de
       ses quatre fiches disent « direct sow ». Une phase de semis n'est retenue
       que si au moins la MOITIÉ des fiches classées décrivent ce mode (mixte
       compris) : la source contre elle-même, sans aucun avis agronomique.
       [CA22] Une fenêtre de **plantation** n'est retenue que si la moitié des
       fiches classées décrivent une mise en place (abri, mixte ou plantée) :
       un cornichon semé en place n'a pas de plantation.

    Une culture dont les fiches mentionnent un semis de fin d'été ou d'automne
    est retenue mais signalée incomplète (`fenetres_incompletes`) : le calendrier
    source ne connaît que le printemps.
    """
    calendrier_par_id: dict[tuple[str, str], dict] = {}
    for ligne in calendrier:
        cle = ((ligne.get("variety_id") or "").strip(), (ligne.get("usda_zone") or "").strip())
        calendrier_par_id[cle] = ligne

    fenetres: dict[str, dict[str, dict[str, str]]] = {}
    for culture, cultivars in par_culture.items():
        if not cultivars:
            continue
        if len(cultivars) < MIN_CULTIVARS:
            resultat.fenetres_ecartees.append(
                f"{culture} — base trop faible ({len(cultivars)} cultivar(s), minimum {MIN_CULTIVARS})"
            )
            continue
        modes = [m for m in (classer_mode_semis(c.get("sowing_method")) for c in cultivars) if m]
        plantes = sum(1 for m in modes if m == MODE_NON_SEMIS)
        phases_lues: tuple[str, ...] = tuple(COLONNES_PHASE)
        if modes and plantes / len(modes) >= SEUIL_COHERENCE:
            # [CA23] Règle 1 révisée : ce qui ne se sème pas perd ses fenêtres de
            # semis et de récolte (calculées depuis un semis qui n'existe pas),
            # mais pas sa plantation — c'est précisément sa phase.
            resultat.fenetres_ecartees.append(
                f"{culture} — ne se sème pas ({plantes} fiche(s) sur {len(modes)} décrivent une "
                "plantation) : semis et récolte écartés, le calendrier source lui applique le "
                "gabarit de semis de sa catégorie"
            )
            automne = sum(
                1 for c in cultivars
                if re.search(_PLANTATION_AUTOMNE, (c.get("sowing_method") or "").lower())
            )
            if automne:
                resultat.fenetres_ecartees.append(
                    f"{culture}.plantation — contredite par les fiches de la source ({automne} sur "
                    f"{len(cultivars)} décrivent une plantation d'automne, absente du calendrier source)"
                )
                continue
            phases_lues = (svc_calendrier.PHASE_PLANTATION,)
        semis = [m for m in modes if m != MODE_NON_SEMIS]
        automne = sum(
            1 for c in cultivars
            if re.search(_SEMIS_TARDIF, f"{c.get('sowing_method') or ''} {c.get('growing_season') or ''}".lower())
        )
        if automne:
            resultat.fenetres_incompletes.append(
                f"{culture} — {automne} fiche(s) sur {len(cultivars)} mentionnent un semis ou une "
                "plantation de fin d'été / d'automne, absent du calendrier source"
            )

        for zone, zone_usda in ZONE_USDA_PAR_ZONE.items():
            lignes = []
            for cultivar in cultivars:
                ligne = calendrier_par_id.get(((cultivar.get("id") or "").strip(), str(zone_usda)))
                if ligne is not None and ligne.get("category") == cultivar.get("category"):
                    lignes.append(ligne)
            if not lignes:
                continue

            for phase in phases_lues:
                brutes = [fenetre_source(l, phase) for l in lignes]
                portees = [f for f in brutes if f is not None]
                if not portees:
                    continue
                etiquette = f"{culture}.{zone}.{phase}"
                modes_admis = _MODES_DE_PHASE.get(phase)
                if modes_admis is not None:
                    # [CA22] La plantation se juge sur TOUTES les fiches classées,
                    # plantées comprises ; un semis, sur les seules fiches de semis.
                    base = modes if phase == svc_calendrier.PHASE_PLANTATION else semis
                    decrits = sum(1 for m in base if m in modes_admis)
                    if not base or decrits / len(base) < SEUIL_COHERENCE:
                        mode_dit = "une mise en place" if base is modes else "ce mode de semis"
                        resultat.fenetres_ecartees.append(
                            f"{etiquette} — contredite par les fiches de la source "
                            f"({decrits} sur {len(base)} décrivent {mode_dit})"
                        )
                        continue
                valides = [f for f in portees if f[0] <= f[1]]
                artefacts = len(portees) - len(valides)
                precision = f", {artefacts} à cheval sur l'année rejetée(s)" if artefacts else ""
                part = len(valides) / len(lignes)
                if len(valides) < MIN_CULTIVARS:
                    resultat.fenetres_ecartees.append(
                        f"{etiquette} — base trop faible ({len(valides)} cultivar(s), "
                        f"minimum {MIN_CULTIVARS}{precision})"
                    )
                    continue
                if part < SEUIL_ACCORD:
                    resultat.fenetres_ecartees.append(
                        f"{etiquette} — portée par {part:.0%} des cultivars seulement "
                        f"(seuil {SEUIL_ACCORD:.0%}{precision})"
                    )
                    continue
                debut = median_low(f[0] for f in valides)
                fin = median_low(f[1] for f in valides)
                if debut > fin:
                    resultat.fenetres_ecartees.append(f"{etiquette} — médianes incohérentes")
                    continue
                valeur = formater_mois(debut, fin)
                fenetres.setdefault(culture, {}).setdefault(zone, {})[phase] = valeur
                resultat.fenetres_retenues.append(
                    f"{etiquette} = {valeur} (médiane de {len(valides)} cultivars, "
                    f"zone USDA {zone_usda}{precision})"
                )
    return fenetres


def _mode_dominant(modes: list[Optional[str]]) -> tuple[Optional[str], str]:
    """
    [US-068] Vote du mode de semis, qui ne laisse pas une option secondaire
    masquer la conduite principale. « Start indoors 6-8 weeks, or direct seed in
    warm climates » est une fiche MIXTE ; mais 69 tomates en pépinière et 22
    mixtes restent une culture élevée à l'abri.

    Sans consensus au sens de `_voter`, un mode franc (pépinière ou pleine terre)
    est retenu si, avec les fiches mixtes, il réunit `SEUIL_ACCORD` des fiches
    classées ET qu'il est plus fréquent que le mixte. Sinon, le résultat du vote.
    """
    mode, motif = _voter(modes)
    if mode is not None:
        return mode, motif
    renseignes = [m for m in modes if m]
    if len(renseignes) < MIN_CULTIVARS:
        return mode, motif
    compte = Counter(renseignes)
    for franc in (MODE_PEPINIERE, MODE_PLEINE_TERRE):
        compatibles = (compte[franc] + compte[MODE_MIXTE]) / len(renseignes)
        if compatibles >= SEUIL_ACCORD and compte[franc] > compte[MODE_MIXTE]:
            return franc, (
                f"{compte[franc]} en {franc} et {compte[MODE_MIXTE]} mixtes sur {len(renseignes)} cultivars"
            )
    return mode, motif


def signaler_incoherences(
    culture: str, durees: dict[str, Any], fenetres: dict[str, dict[str, str]], resultat: ResultatAdaptation
) -> None:
    """
    [US-068 / CA24] Signale, zone par zone, une plantation qui ne s'enchaîne pas
    avec le semis en pépinière de la même culture. Deux contrôles, au mois :

    - la plantation commence AVANT le semis en pépinière ;
    - la plantation est TERMINÉE avant qu'un plant semé au premier jour de la
      fenêtre de pépinière ait atteint le délai de repiquage minimal.

    Rien n'est ajusté : la source est rapportée telle quelle, et c'est au
    relecteur de trancher. Une plantation sans semis en pépinière (plants
    achetés) n'est jamais une incohérence.
    """
    delai_min = None
    if durees.get("repiquage"):
        delai_min = (svc_calendrier.parser_duree(durees["repiquage"]) or (None,))[0]
    for zone, phases in fenetres.items():
        pepiniere = phases.get(svc_calendrier.PHASE_SEMIS_PEPINIERE)
        plantation = phases.get(svc_calendrier.PHASE_PLANTATION)
        if not pepiniere or not plantation:
            continue
        (semis_debut, _), (plant_debut, plant_fin) = (
            svc_calendrier.parser_fenetre(pepiniere), svc_calendrier.parser_fenetre(plantation)
        )
        etiquette = f"{culture}.{zone} — semis en pépinière {pepiniere}, plantation {plantation}"
        if plant_debut < semis_debut:
            resultat.fenetres_incoherentes.append(f"{etiquette} : la plantation commence avant le semis")
        elif delai_min is not None:
            pret = (date(2001, semis_debut, 1) + timedelta(days=delai_min)).month
            if plant_fin < pret:
                resultat.fenetres_incoherentes.append(
                    f"{etiquette} : terminée avant qu'un plant semé au plus tôt ait "
                    f"{delai_min} jours (repiquage)"
                )


def _retenir_plantation_recolte(
    culture: str,
    lignes: list[dict],
    durees: dict[str, Any],
    resultat: ResultatAdaptation,
    motif_mode: str,
) -> None:
    """
    [US-177 / CA2] Durée plantation → première récolte, lue dans `days_to_harvest`
    et **seulement** là où la source la compte depuis la plantation :

    - culture élevée à l'abri (`MODE_PEPINIERE`) — SOURCE.md le consigne, et
      c'est le motif même pour lequel cette colonne est écartée de `recolte` ;
    - culture qui ne se sème pas (`MODE_NON_SEMIS` : ail, pomme de terre,
      fraise) — la plantation est alors le seul geste d'origine possible, ce
      n'est pas une convention supposée mais la seule lecture qui ait un sens.

    Jamais pour un semis en place ni pour un mode indéterminé, et JAMAIS par
    soustraction de `repiquage` à `recolte` : la valeur est lue ou elle est vide.
    Mêmes règles d'agrégation que les autres durées (`_agreger_bornes`).
    """
    recolte, motif = _agreger_bornes([_bornes_jours(l.get("days_to_harvest")) for l in lignes])
    if recolte is None:
        resultat.durees_ecartees.append(f"{culture}.plantation_recolte — {motif}")
        return
    durees["plantation_recolte"] = f"{recolte[0]}-{recolte[1]}"
    resultat.durees_retenues.append(
        f"{culture}.plantation_recolte = {recolte[0]}-{recolte[1]} j "
        f"({motif}, {motif_mode} : la source compte depuis la plantation)"
    )


def construire_calendriers(
    par_culture: dict[str, list[dict]],
    resultat: ResultatAdaptation,
    calendrier: Iterable[dict] = (),
) -> list[dict]:
    """
    [US-068 / CA3, CA9] Produit le bloc `cultures_calendriers` sur l'itinéraire
    « standard » : les durées, et les fenêtres de `construire_fenetres` quand
    le calendrier source est fourni.

    Trois règles fermées pour les durées, parce qu'une durée mal comprise est
    une durée fausse :

    1. **Le mode de semis se vote** (`classer_mode_semis`, même seuil d'accord que
       les attributs). Sans consensus, aucune durée dépendante du mode.
    2. **Semis → première récolte n'est retenu qu'en pleine terre.** Les
       catalogues comptent `days_to_harvest` depuis la PLANTATION pour les
       cultures élevées à l'abri (tomate, poivron) : l'additionner au temps de
       pépinière reposerait sur une convention que la source ne déclare pas. Pour
       ces cultures, la durée reste vide — le jardinier la complète au bot.
    3. **Semis → repiquage n'est retenu qu'en pépinière**, depuis la consigne
       « start indoors N-M weeks ».
    4. **Plantation → première récolte [US-177 / CA2]** reprend `days_to_harvest`
       là où la source le compte depuis la plantation — à l'abri, ou pour ce qui
       ne se sème pas. Voir `_retenir_plantation_recolte`.

    Semis → levée vaut quel que soit le mode, sauf pour ce qui ne se sème pas.
    Le mode voté tient compte des fiches « mixtes » (`_mode_dominant`).
    """
    fenetres = construire_fenetres(par_culture, calendrier, resultat)
    entrees: list[dict] = []
    for culture, lignes in par_culture.items():
        if not lignes:
            continue
        mode, motif_mode = _mode_dominant([classer_mode_semis(l.get("sowing_method")) for l in lignes])
        durees: dict[str, Any] = {}

        if mode == MODE_NON_SEMIS:
            resultat.durees_ecartees.append(f"{culture} — ne se sème pas ({motif_mode})")
            _retenir_plantation_recolte(culture, lignes, durees, resultat, "ne se sème pas")
        else:
            levee, motif = _agreger_bornes([_bornes_jours(l.get("days_to_germination")) for l in lignes])
            if levee is None:
                resultat.durees_ecartees.append(f"{culture}.levee — {motif}")
            else:
                durees["levee"] = f"{levee[0]}-{levee[1]}"
                resultat.durees_retenues.append(f"{culture}.levee = {levee[0]}-{levee[1]} j ({motif})")

        if mode == MODE_PLEINE_TERRE:
            recolte, motif = _agreger_bornes([_bornes_jours(l.get("days_to_harvest")) for l in lignes])
            if recolte is None:
                resultat.durees_ecartees.append(f"{culture}.recolte — {motif}")
            else:
                durees["recolte"] = f"{recolte[0]}-{recolte[1]}"
                resultat.durees_retenues.append(
                    f"{culture}.recolte = {recolte[0]}-{recolte[1]} j ({motif}, semis en place)"
                )
        elif mode == MODE_PEPINIERE:
            repiquage, motif = _agreger_bornes([_semaines_abri(l.get("sowing_method")) for l in lignes])
            if repiquage is None:
                resultat.durees_ecartees.append(f"{culture}.repiquage — {motif}")
            else:
                durees["repiquage"] = f"{repiquage[0]}-{repiquage[1]}"
                resultat.durees_retenues.append(
                    f"{culture}.repiquage = {repiquage[0]}-{repiquage[1]} j ({motif})"
                )
            resultat.durees_ecartees.append(
                f"{culture}.recolte — élevée à l'abri : la source compte depuis la plantation"
            )
            # [US-177 / CA2] Ce qui disqualifiait `days_to_harvest` pour l'étape
            # ci-dessus le qualifie pour celle-ci : la source compte depuis la
            # plantation, c'est exactement ce que cette durée mesure.
            _retenir_plantation_recolte(culture, lignes, durees, resultat, "élevée à l'abri")
        elif mode == MODE_MIXTE:
            resultat.durees_ecartees.append(
                f"{culture}.recolte — semée en place OU à l'abri selon le cultivar : "
                f"la source ne dit pas depuis quand elle compte ({motif_mode})"
            )
        elif mode != MODE_NON_SEMIS:
            resultat.durees_ecartees.append(
                f"{culture}.recolte — mode de semis indéterminé ({motif_mode})"
            )

        signaler_incoherences(culture, durees, fenetres.get(culture, {}), resultat)

        if durees or culture in fenetres:
            entree: dict[str, Any] = {"culture": culture, "itineraire": "standard", "durees": durees}
            if culture in fenetres:
                entree["fenetres"] = fenetres[culture]
            entrees.append(entree)

    # Les alias reçoivent une COPIE de l'entrée de leur culture de référence.
    par_nom = {e["culture"]: e for e in entrees}
    for alias, reference in ALIAS_CALENDRIER.items():
        if reference in par_nom and alias not in par_nom:
            entrees.append({**par_nom[reference], "culture": alias})
            resultat.fenetres_retenues.append(f"{alias} = calendrier de « {reference} » (ALIAS_CALENDRIER)")
    return entrees


def construire_associations(
    lignes: Iterable[dict], par_culture: dict[str, list[dict]], resultat: ResultatAdaptation
) -> list[dict]:
    """
    Extrait les arêtes d'association — matière première pour US-163.

    ⚠️ Cette extraction est **brute et non révisée**. Elle est produite parce
    que le travail est fait une fois, pas parce qu'elle serait exploitable en
    l'état : `envelopper_associations` documente ce qui reste à traiter.

    Les libellés de compagnons restent **en anglais, tels quels** : les traduire
    serait une décision d'appariement qui appartient à US-163, laquelle devra les
    rattacher à nos cultures. Le motif source est conservé pour la même raison.

    Une paire que la source dit bénéfique pour un cultivar et nuisible pour un
    autre est **écartée** : la source se contredit, et trancher à sa place serait
    exactement ce que le §6.5 interdit sur les associations.
    """
    slugs_par_culture = {
        culture: {l.get("slug") for l in lignes_culture}
        for culture, lignes_culture in par_culture.items()
    }

    natures: dict[tuple[str, str], set[str]] = defaultdict(set)
    motifs: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for ligne in lignes:
        slug = ligne.get("variety_slug")
        compagnon = (ligne.get("companion_name") or "").strip()
        relation = (ligne.get("relationship") or "").strip().lower()
        if not slug or not compagnon or relation not in ("beneficial", "harmful"):
            continue
        for culture, slugs in slugs_par_culture.items():
            if slug in slugs:
                cle = (culture, compagnon)
                natures[cle].add("favorable" if relation == "beneficial" else "defavorable")
                motifs[cle][(ligne.get("reason") or "").strip()] += 1
                break

    entrees: list[dict] = []
    for (culture, compagnon), valeurs in sorted(natures.items()):
        if len(valeurs) > 1:
            resultat.associations_contradictoires.append(f"{culture} × {compagnon}")
            continue
        motif = motifs[(culture, compagnon)].most_common(1)[0][0]
        entrees.append({
            "culture": culture,
            "compagnon_source": compagnon,
            "nature": next(iter(valeurs)),
            "motif_source": motif,
            # [§6.5] La source ne distingue pas l'établi du traditionnel. Ne
            # rien affirmer de plus qu'elle : US-163 tranchera, avec sa colonne
            # `niveau_preuve`.
            "niveau_preuve": "traditionnel",
        })
    resultat.associations = len(entrees)
    return entrees


def construire_manifeste(
    varieties: Iterable[dict],
    companions: Iterable[dict] = (),
    extrait_le: Optional[str] = None,
    calendrier: Iterable[dict] = (),
) -> tuple[dict[str, Any], Optional[dict[str, Any]], ResultatAdaptation]:
    """
    Assemble le manifeste d'import et, séparément, l'extraction d'associations.

    Retourne `(manifeste, associations, resultat)`. `associations` vaut None si
    aucun CSV de compagnons n'est fourni. Les deux ne sont **jamais** fusionnés :
    le manifeste ne porte que ce qui s'importe aujourd'hui.

    Le bloc `source` reprend la fiche du registre — code, licence et attribution
    exacte exigée par CC BY. L'import la revalidera de toute façon (CA6) ; la
    faire figurer ici garantit que le fichier produit est lisible et vérifiable
    sans la base.
    """
    fiche = next(
        f for f in svc_sources.SOURCES_SOCLE if f["code"] == svc_sources.SOURCE_WIND_RIVER
    )
    resultat = ResultatAdaptation()
    varieties = list(varieties)
    par_culture = selectionner_cultivars(varieties)
    # [US-068] Le calendrier couvre toutes les cultures de culture_config qu'on
    # sait retrouver dans la source ; attributs et associations restent sur les dix.
    par_culture_calendrier = selectionner_cultivars(varieties, APPARIEMENTS_CALENDRIER)
    resultat.cultivars_calendrier = {c: len(l) for c, l in par_culture_calendrier.items()}

    manifeste: dict[str, Any] = {
        "_lisez_moi": [
            "[US-161] Manifeste produit par tools/adapter_wind_river.py — NE PAS ÉDITER À LA MAIN.",
            "Régénérer avec l'adaptateur après toute mise à jour des CSV source.",
            "Pour corriger une valeur : /culture <attribut> <culture> <valeur> au bot.",
            "La correction porte l'origine 'saisie_manuelle' et survit à tout rejeu (CA6).",
            "",
            "[US-163] Le bloc 'cultures_associations' est une extraction CURÉE et",
            "TRADUITE de companion_plants.csv (voir adaptateur_wind_river.curer_associations) :",
            "hors périmètre, motifs recyclés et contradictions déjà écartés — voir le compte",
            "rendu de 'python tools/adapter_wind_river.py' pour le détail des exclusions.",
            "Pour corriger une association : /association saisir <cultureA> <cultureB> ... au bot.",
            "La correction porte l'origine 'saisie_manuelle' et survit à tout rejeu (CA5/CA10).",
            "",
            "L'extraction BRUTE, non traduite et non curée, reste disponible séparément",
            "dans wind_river_associations.json — matériau de relecture, jamais à importer.",
            "",
            "[US-068] Le bloc 'cultures_calendriers' porte des DURÉES (levée, récolte en pleine",
            "terre, repiquage en pépinière) et des FENÊTRES lues dans planting_calendar.csv :",
            "semis en pépinière, semis en pleine terre, PLANTATION (outdoor_transplant_*,",
            "amendement du 15/09/2026 — lue, jamais recalculée depuis le repiquage) et récolte.",
            "⚠️ Les fenêtres amont sont en zones USDA : la zone lue pour chaque zone climatique",
            "est une DÉCISION déclarée (adaptateur_wind_river.ZONE_USDA_PAR_ZONE, calée sur la",
            "date de dernière gelée), pas une équivalence. Printemps seulement : la source ne",
            "connaît aucun semis de fin d'été ni d'automne. Toutes les cultures de culture_config",
            "retrouvées dans la source (APPARIEMENTS_CALENDRIER). Voir wind_river_greens/SOURCE.md.",
            "Pour corriger : /calendrier fenetre|duree <culture> ... au bot, correction propre",
            "au potager qu'aucun rejeu n'écrasera.",
        ],
        "source": {
            "code": fiche["code"],
            "libelle": fiche["libelle"],
            "licence": fiche["licence"],
            "attribution": fiche["attribution"],
            "url": fiche["url"],
            "partageable": fiche["partageable"],
        },
        "extrait_le": extrait_le,
        "cultures_attributs": construire_attributs(par_culture, resultat),
        # [US-068] Durées et fenêtres — voir construire_calendriers / construire_fenetres.
        "cultures_calendriers": construire_calendriers(par_culture_calendrier, resultat, calendrier),
    }

    companions = list(companions)
    associations = None
    if companions:
        aretes_brutes = construire_associations(companions, par_culture, resultat)
        associations = envelopper_associations(aretes_brutes, manifeste["source"], extrait_le)
        entrees_curees, rapport_curation = curer_associations(aretes_brutes)
        manifeste["cultures_associations"] = entrees_curees
        resultat.curation_associations = rapport_curation

    log.info(
        "[adaptateur_wind_river] %s culture(s) appariée(s), %s attribut(s) retenu(s), "
        "%s écarté(s), %s association(s) extraite(s)",
        sum(1 for n in resultat.cultivars_apparies.values() if n),
        len(resultat.attributs_retenus), len(resultat.attributs_ecartes),
        resultat.associations,
    )
    return manifeste, associations, resultat


def envelopper_associations(
    aretes: list[dict], source: dict[str, Any], extrait_le: Optional[str] = None
) -> dict[str, Any]:
    """
    Emballe les arêtes dans un fichier qui dit **ce qu'il vaut**.

    L'avertissement ci-dessous n'est pas une précaution de style : c'est le
    résultat d'un audit mené le 01/09/2026 sur la release `v1.0.0`, et c'est la
    liste de travail d'US-163. Les chiffres sont datés et figés comme toute
    mesure du projet — les recompter à chaque exécution donnerait l'illusion
    d'un contrôle qualité automatique, alors que ces défauts demandent une
    relecture humaine, pas un filtre.

    Ce fichier n'est **pas** un manifeste d'import et ne doit jamais être passé
    à `tools/importer_referentiel.py` : il ne déclare aucun bloc importable.
    """
    return {
        "_lisez_moi": [
            "[US-161] Extraction BRUTE, en anglais, non canonicalisée des associations",
            "de cultures. Ce fichier n'est PAS un manifeste d'import et ne doit pas être",
            "passé à tools/importer_referentiel.py.",
            "",
            "[US-163] La version CURÉE, traduite et importable de cette extraction vit",
            "dans le bloc 'cultures_associations' de wind_river_attributs.json — produite",
            "par adaptateur_wind_river.curer_associations à partir de CES MÊMES arêtes.",
            "Ce fichier-ci reste le matériau de relecture : ce que la curation a retenu,",
            "traduit et écarté s'y vérifie contre la donnée source, ligne par ligne.",
            "",
            "⚠️ AUDIT DU 01/09/2026 SUR LA RELEASE v1.0.0 — traité par la curation d'US-163 :",
            "",
            "  • 41 paires de libellés doublonnés désignent le même compagnon :",
            "    'Marigold'/'Marigolds', 'Onion'/'Onions', 'Black Walnut'/'Walnut Trees'…",
            "    La déduplication compare les libellés à l'identique et ne les fusionne pas.",
            "",
            "  • Au moins 1 contradiction est masquée par ces doublons : courgette ×",
            "    herbes aromatiques est donnée favorable sous 'Aromatic Herbs' et",
            "    défavorable sous 'Aromatic herbs (Sage)'. Les 3 contradictions détectées",
            "    ne sont donc pas les seules.",
            "",
            "  • 8 motifs décrivent une AUTRE plante que la culture — texte recyclé d'une",
            "    variété à l'autre dans la source amont : 'tomate × Catnip' explique qu'il",
            "    protège « eggplant foliage », 'tomate × Alyssum' parle de « rose pests »,",
            "    'haricot × Mint' de « pea seeds and pods ».",
            "",
            "  • 1 auto-association : 'tomate × Tomatoes = favorable'.",
            "",
            "  • Les libellés de compagnons sont en ANGLAIS et non appariés à nos cultures.",
            "    Beaucoup sont hors du potager (Black Walnut, Apricot Trees, Gladiolus).",
            "",
            "  • niveau_preuve vaut 'traditionnel' partout : la source ne distingue pas",
            "    l'établi du traditionnel, et on n'affirme pas plus qu'elle (§6.5).",
        ],
        "source": source,
        "extrait_le": extrait_le,
        "revise": False,
        "cultures_associations": aretes,
    }


# ═════════════════════════════════════════════════════════════════════════════
# [US-163] Curation des associations — traduction, périmètre, doublons
# ═════════════════════════════════════════════════════════════════════════════
# `construire_associations` ci-dessus produit une extraction BRUTE, en anglais,
# non canonicalisée : c'était le travail d'US-161, délibérément arrêté là (voir
# sa docstring). Ce qui suit EST le travail d'US-163 qu'elle annonçait : chaque
# compagnon est rattaché à une culture ou une famille de notre référentiel, ou
# écarté s'il n'y a pas sa place ; les motifs sont traduits en français, courts,
# dans le style déjà utilisé ailleurs dans le projet (« concurrence
# racinaire ») plutôt que la phrase explicative complète de la source anglaise.
#
# Un compagnon dont le nom traduit COÏNCIDE avec la culture elle-même
# (auto-association, ex. « tomate × Tomatoes ») est également écarté : il ne
# décrit rien qu'une rotation ou une association puisse exploiter.

#: [CIBLE_COMPAGNONS] Pour chaque libellé source anglais : `None` si le
#: compagnon est hors du périmètre d'un potager POTAGER — ornementale, arbre,
#: plante non suivie par ce référentiel — aucune traduction ne lui donnerait sa
#: place ici, quelle que soit la culture visée. Sinon `("culture", nom)` ou
#: `("famille", nom)` : une CIBLE PLAUSIBLE et son nom français, jamais une
#: garantie qu'une fiche existe réellement en base — cette vérification est le
#: travail de l'import (`app.services.associations._resoudre_cote`), pas de
#: cette table. Une cible non résolue à l'import est comptée
#: `associations_ignorees`, jamais fabriquée (même invariant que CA7 d'US-161).
#:
#: Niveau famille plutôt que culture précise dans deux cas : le compagnon
#: source est déjà générique dans le texte anglais (« Aromatic Herbs »), ou il
#: désigne une espèce absente du pré-remplissage de `migration_v37.sql` mais
#: botaniquement certaine (origan, sauge — Lamiacées comme basilic et thym).
#: Une famille reste un fait défendable là où une espèce précise ne le serait
#: pas.
CIBLE_COMPAGNONS: dict[str, Optional[tuple[str, str]]] = {
    # ── Hors périmètre : ornementales, arbres, plantes non suivies ───────────
    "Alyssum": None, "Apricot Trees": None, "Asparagus": None, "Borage": None,
    "Black Walnut": None, "Black Walnut Trees": None, "Walnut Trees": None,
    "Catmint": None, "Catnip": None, "Chamomile": None, "Clematis": None,
    "Gladiolus": None, "Large Trees": None, "Lavender": None,
    "Marigold": None, "Marigolds": None, "Nasturtium": None, "Nasturtiums": None,
    "Roses": None, "Rue": None, "Summer Savory": None,
    "Sunflower": None, "Sunflowers": None,

    # ── Niveau famille ────────────────────────────────────────────────────────
    "Aromatic Herbs": ("famille", "Lamiacée"),
    "Aromatic Herbs (Oregano, Thyme)": ("famille", "Lamiacée"),
    "Aromatic herbs": ("famille", "Lamiacée"),
    "Aromatic herbs (Sage)": ("famille", "Lamiacée"),
    "Aromatic herbs (Sage, Rosemary)": ("famille", "Lamiacée"),
    "Aromatic herbs (sage, rosemary)": ("famille", "Lamiacée"),
    "Aromatic herbs (strong)": ("famille", "Lamiacée"),
    "Brassicas": ("famille", "Brassicacée"),
    "Brassicas (Broccoli)": ("famille", "Brassicacée"),
    "Brassicas (Cabbage family)": ("famille", "Brassicacée"),
    "Oregano": ("famille", "Lamiacée"),
    "Sage": ("famille", "Lamiacée"),

    # ── Niveau culture ────────────────────────────────────────────────────────
    "Basil": ("culture", "basilic"),
    "Bean": ("culture", "haricot"), "Beans": ("culture", "haricot"),
    "Bush Beans": ("culture", "haricot"),
    "Pole Bean": ("culture", "haricot grimpant"), "Pole Beans": ("culture", "haricot grimpant"),
    "Cabbage": ("culture", "chou"),
    "Carrot": ("culture", "carotte"), "Carrots": ("culture", "carotte"),
    "Celery": ("culture", "céleri"),
    "Chives": ("culture", "ciboulette"),
    "Coriander": ("culture", "coriandre"),
    "Corn": ("culture", "maïs"), "Sweet Corn": ("culture", "maïs"),
    "Cucumber": ("culture", "concombre"), "Cucumbers": ("culture", "concombre"),
    "Dill": ("culture", "aneth"),
    "Fennel": ("culture", "fenouil"),
    "Garlic": ("culture", "ail"),
    "Hot Peppers": ("culture", "piment"),
    "Kohlrabi": ("culture", "chou-rave"),
    "Leeks": ("culture", "poireau"),
    "Lettuce": ("culture", "laitue"),
    "Melon": ("culture", "melon"), "Melons": ("culture", "melon"),
    "Mint": ("culture", "menthe"),
    "Onion": ("culture", "oignon"), "Onions": ("culture", "oignon"),
    "Parsley": ("culture", "persil"),
    "Parsnips": ("culture", "panais"),
    "Peas": ("culture", "pois"),
    "Peppers": ("culture", "poivron"),
    "Potato": ("culture", "pomme de terre"), "Potatoes": ("culture", "pomme de terre"),
    "Pumpkins": ("culture", "potiron"),
    "Radish": ("culture", "radis"), "Radishes": ("culture", "radis"),
    "Rosemary": ("culture", "romarin"),
    "Spinach": ("culture", "épinard"),
    "Squash": ("culture", "courge"), "Summer Squash": ("culture", "courge"),
    "Strawberry": ("culture", "fraise"), "Strawberries": ("culture", "fraise"),
    "Thyme": ("culture", "thym"),
    "Tomato": ("culture", "tomate"), "Tomatoes": ("culture", "tomate"),
}

#: [Audit du 01/09/2026, release v1.0.0] Motifs qui décrivent une AUTRE plante
#: que `culture` — texte recyclé d'un cultivar à l'autre dans la source amont
#: (ex. « tomate × Catnip » explique qu'il protège « eggplant foliage »).
#: Identifiées par relecture humaine, pas par un filtre : aucune règle générale
#: ne distingue fiablement un motif recyclé d'un motif légitime qui nomme
#: incidemment une autre culture (« ail × haricot » mentionne légitimement le
#: haricot, qui EST le sujet). Figées comme toute mesure du projet — les
#: recompter à chaque exécution donnerait l'illusion d'un contrôle qualité
#: automatique là où il a fallu une relecture. Clé : (culture, libellé source).
MOTIFS_RECYCLES_A_EXCLURE: frozenset = frozenset({
    ("tomate", "Alyssum"),      # motif parle de pucerons du rosier
    ("tomate", "Catnip"),       # motif parle du feuillage de l'aubergine
    ("tomate", "Hot Peppers"),  # motif parle des feuilles de l'aubergine
    ("tomate", "Lavender"),     # motif parle de pucerons du rosier
    ("tomate", "Pole Beans"),   # motif parle de l'ombrage sur des aubergines
    ("haricot", "Mint"),        # motif parle des graines et gousses du pois
    ("haricot", "Cucumbers"),   # motif parle de l'azote fixé par le pois
    ("haricot", "Gladiolus"),   # motif parle du développement des gousses de pois
})

#: [US-163] Motif traduit et condensé, à l'usage attendu du référentiel — une
#: phrase courte, pas la traduction mot à mot de la phrase explicative anglaise
#: de la source (CA1 : « ce qui rend l'avertissement compréhensible »). Clé :
#: (culture, cible française) après canonicalisation des doublons de libellé.
#: Une entrée retenue par `curer_associations` sans traduction ici est un défaut
#: de cette table à corriger, pas un comportement attendu — voir son assertion
#: de couverture dans `tests/test_us163_adaptateur_wind_river_associations.py`.
MOTIFS_FR: dict[tuple[str, str], str] = {
    ("ail", "carotte"): "répulsif croisé contre la mouche de la carotte",
    ("ail", "chou"): "répulsif contre la piéride du chou et les pucerons",
    ("ail", "fraise"): "répulsif contre limaces, pucerons et acariens",
    ("ail", "haricot"): "inhibe la fixation d'azote du haricot",
    ("ail", "laitue"): "protège des pucerons et limaces sans concurrence",
    ("ail", "pois"): "perturbe la fixation d'azote symbiotique du pois",
    ("ail", "poivron"): "répulsif contre pucerons et acariens du poivron",
    ("ail", "tomate"): "répulsif contre pucerons et sphinx de la tomate",
    ("ail", "épinard"): "protège contre pucerons et mineuses, besoins en eau proches",
    ("blette", "ail"): "répulsif naturel, limite les maladies fongiques",
    ("blette", "carotte"): "racines à profondeurs différentes, aucune concurrence",
    ("blette", "fenouil"): "composés allélopathiques défavorables à la blette",
    ("blette", "haricot grimpant"): "ombrage excessif et concurrence racinaire",
    ("blette", "laitue"): "racines superficielles complémentaires, paillage vivant",
    ("blette", "maïs"): "ombrage excessif, forte concurrence nutritive",
    ("blette", "oignon"): "répulsif contre pucerons et altises de la blette",
    ("blette", "radis"): "croissance rapide, ameublit le sol avant que la blette n'occupe l'espace",
    ("blette", "épinard"): "besoins de culture proches, bonne culture en succession",
    ("carotte", "aneth"): "ralentit la carotte plantée trop près",
    ("carotte", "ciboulette"): "répulsif contre la mouche de la carotte et les pucerons",
    ("carotte", "coriandre"): "attire la mouche de la carotte, freine la germination",
    ("carotte", "fenouil"): "composés allélopathiques défavorables à la germination",
    ("carotte", "laitue"): "racines superficielles complémentaires, garde l'humidité",
    ("carotte", "oignon"): "répulsif contre la mouche de la carotte et les vers du pied",
    ("carotte", "panais"): "concurrence directe pour le sol, mêmes ravageurs",
    ("carotte", "poireau"): "répulsif croisé, mouche de la carotte et teigne du poireau",
    ("carotte", "pois"): "fixe l'azote, feuillage léger n'ombrage pas la carotte",
    ("carotte", "radis"): "ameublit le sol pour la racine, récolté rapidement",
    ("carotte", "romarin"): "masque l'odeur de la carotte contre sa mouche",
    ("carotte", "tomate"): "ameublit le sol pour la tomate, qui lui apporte de l'ombre",
    ("carotte", "Lamiacée"): "répulsif contre la mouche de la carotte, attire les auxiliaires",
    ("chou", "ail"): "fongicide naturel contre hernie du chou et nervation noire",
    ("chou", "aneth"): "attire les guêpes parasites contre la piéride du chou",
    ("chou", "carotte"): "ameublit le sol sans concurrence, bonne occupation de l'espace",
    ("chou", "céleri"): "répulsif contre la piéride, racines complémentaires",
    ("chou", "fraise"): "freine la fraise, sensibilités telluriques communes",
    ("chou", "haricot grimpant"): "ombrage excessif, concurrence pour l'azote",
    ("chou", "laitue"): "couvre-sol efficace sans concurrence nutritive",
    ("chou", "oignon"): "répulsif contre mouche du chou, pucerons et altises",
    ("chou", "thym"): "répulsif contre piéride et altises, attire les pollinisateurs",
    ("chou", "tomate"): "concurrence nutritive et allélopathie défavorables au chou",
    ("chou", "épinard"): "paillage vivant, besoins nutritifs différents",
    ("concombre", "aneth"): "attire les guêpes parasites contre les ravageurs",
    ("concombre", "basilic"): "répulsif contre pucerons, acariens et thrips",
    ("concombre", "fenouil"): "composés allélopathiques défavorables au concombre",
    ("concombre", "haricot"): "fixe l'azote et sert de tuteur naturel",
    ("concombre", "laitue"): "couvre-sol qui garde l'humidité et limite les adventices",
    ("concombre", "maïs"): "ombrage et protection contre le vent",
    ("concombre", "melon"): "concurrence directe, risque accru de flétrissement bactérien",
    ("concombre", "pomme de terre"): "concurrence nutritive, sensibilité accrue aux maladies",
    ("concombre", "radis"): "répulsif contre la chrysomèle, récolté avant de gêner",
    ("concombre", "tomate"): "deux cultures gourmandes en concurrence, maladies partagées",
    ("concombre", "Lamiacée"): "odeurs fortes défavorables à la croissance et à la saveur",
    ("cornichon", "aneth"): "attire les guêpes prédatrices contre les ravageurs",
    ("cornichon", "basilic"): "répulsif contre pucerons, acariens et thrips",
    ("cornichon", "fenouil"): "sécrétions racinaires allélopathiques défavorables",
    ("cornichon", "haricot"): "fixe l'azote et couvre le sol",
    ("cornichon", "laitue"): "profite de l'ombre du cornichon, bonne occupation de l'espace",
    ("cornichon", "maïs"): "tuteur naturel et ombrage partiel",
    ("cornichon", "melon"): "mêmes ravageurs, pression accrue de la chrysomèle",
    ("cornichon", "pomme de terre"): "concurrence nutritive, sensibilité accrue aux maladies",
    ("cornichon", "radis"): "répulsif contre chrysomèle et punaise, améliore le sol",
    ("cornichon", "Lamiacée"): "huiles essentielles défavorables à la germination",
    ("courgette", "ail"): "répulsif contre pucerons, punaises et maladies fongiques",
    ("courgette", "aneth"): "attire les guêpes parasites contre les ravageurs",
    ("courgette", "basilic"): "répulsif contre pucerons et aleurodes",
    ("courgette", "concombre"): "concurrence directe, mêmes ravageurs (chrysomèle)",
    ("courgette", "fenouil"): "composés allélopathiques défavorables à la courgette",
    ("courgette", "haricot"): "fixe l'azote pour la courgette, grande consommatrice",
    ("courgette", "laitue"): "profite de l'ombre de la courgette, couvre-sol efficace",
    ("courgette", "maïs"): "support vertical et ombrage partiel (les trois sœurs)",
    ("courgette", "melon"): "mêmes ravageurs, pression accrue",
    ("courgette", "pomme de terre"): "deux cultures gourmandes en concurrence directe",
    ("courgette", "potiron"): "pollinisation croisée pouvant affecter les fruits",
    ("courgette", "radis"): "répulsif contre la pyrale et la chrysomèle",
    ("courgette", "Brassicacée"): "besoins de sol différents, concurrence défavorable",
    ("haricot", "ail"): "composés allélopathiques défavorables au haricot",
    ("haricot", "basilic"): "répulsif contre pucerons, acariens et thrips",
    ("haricot", "carotte"): "ameublit le sol pour le haricot, sans concurrence",
    ("haricot", "chou-rave"): "forte concurrence nutritive défavorable au haricot",
    ("haricot", "ciboulette"): "répulsif contre pucerons, assainit le potager",
    ("haricot", "concombre"): "conditions de culture proches, le haricot apporte l'azote",
    ("haricot", "courge"): "couvre-sol qui limite les adventices et garde l'humidité",
    ("haricot", "fenouil"): "composés allélopathiques défavorables au haricot",
    ("haricot", "fraise"): "niveau de sol différent, profite de l'azote fixé",
    ("haricot", "laitue"): "profite de l'azote fixé par le haricot, paillage vivant",
    ("haricot", "maïs"): "tuteur naturel pour le haricot grimpant (les trois sœurs)",
    ("haricot", "oignon"): "sécrétions racinaires qui freinent la fixation d'azote",
    ("haricot", "radis"): "croissance rapide, ameublit le sol, répulsif contre la bruche",
    ("haricot", "romarin"): "répulsif contre la bruche du haricot",
    ("haricot", "épinard"): "profite de l'azote fixé, profondeurs racinaires différentes",
    ("poivron", "basilic"): "répulsif contre pucerons, acariens et thrips",
    ("poivron", "carotte"): "ameublit le sol pour le poivron, sans concurrence",
    ("poivron", "chou-rave"): "forte concurrence nutritive défavorable au poivron",
    ("poivron", "ciboulette"): "répulsif contre pucerons et vers gris",
    ("poivron", "fenouil"): "composés allélopathiques défavorables au poivron",
    ("poivron", "laitue"): "paillage vivant, récoltée avant que le poivron n'ait besoin de place",
    ("poivron", "oignon"): "répulsif contre pucerons et thrips du poivron",
    ("poivron", "persil"): "attire syrphes et guêpes parasites contre les ravageurs",
    ("poivron", "tomate"): "besoins de culture proches, peuvent partager un tuteurage",
    ("poivron", "Brassicacée"): "forte concurrence racinaire défavorable au poivron",
    ("poivron", "Lamiacée"): "répulsif contre la chrysomèle, garde l'humidité du sol",
    ("tomate", "ail"): "fongicide naturel contre le mildiou, répulsif divers",
    ("tomate", "basilic"): "répulsif contre pucerons, aleurodes et sphinx",
    ("tomate", "carotte"): "ameublit le sol pour la tomate, sans concurrence",
    ("tomate", "ciboulette"): "répulsif contre pucerons, limiterait les maladies fongiques",
    ("tomate", "fenouil"): "composés allélopathiques défavorables à la tomate",
    ("tomate", "laitue"): "profite de l'ombre de la tomate, sans concurrence",
    ("tomate", "maïs"): "attire le même ravageur (noctuelle), pression accrue",
    ("tomate", "persil"): "attire syrphes et guêpes parasites",
    ("tomate", "poivron"): "besoins de culture proches, systèmes racinaires compatibles",
    ("tomate", "Brassicacée"): "concurrence nutritive défavorable à la tomate",
    ("tomate", "Lamiacée"): "répulsif divers, améliorerait la saveur de la tomate",
}


@dataclass
class RapportCuration:
    """Ce que `curer_associations` a réellement fait — matière du compte rendu."""

    brutes: int = 0
    hors_perimetre: list[str] = field(default_factory=list)
    motifs_recycles: list[str] = field(default_factory=list)
    auto_associations: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    #: [Filet de sécurité] Paire retenue mais absente de MOTIFS_FR — le motif
    #: anglais brut est alors utilisé tel quel, et la paire est signalée ici :
    #: la table de traduction a un trou à combler, pas un comportement voulu.
    motifs_non_traduits: list[str] = field(default_factory=list)
    retenues: int = 0


def curer_associations(aretes_brutes: list[dict]) -> tuple[list[dict], RapportCuration]:
    """
    [US-163] Traduit et curate l'extraction brute de `construire_associations`
    en un bloc `cultures_associations` prêt pour le manifeste d'import.

    Quatre écarts, chacun compté séparément dans le rapport, avant toute
    traduction :
    1. Compagnon hors périmètre (`CIBLE_COMPAGNONS` vaut None) — ornementale,
       arbre : aucune culture ni famille de ce référentiel ne l'accueille.
    2. Motif recyclé d'une autre plante (`MOTIFS_RECYCLES_A_EXCLURE`, audit du
       01/09/2026).
    3. Auto-association : la cible traduite est la culture elle-même.
    4. Contradiction : une fois les libellés doublonnés fusionnés vers une même
       cible, la source affirme à la fois « favorable » et « défavorable » — on
       ne tranche pas à sa place (§6.5 de la conception), la paire entière est
       écartée. C'est ici, et seulement ici, qu'une contradiction que l'audit
       avait laissée passer sous deux libellés différents (« courgette ×
       Aromatic Herbs » / « Aromatic herbs (Sage) ») devient visible : la
       fusion précède la détection.

    Chaque arête retenue porte `niveau_preuve = 'traditionnel'` sans exception :
    la source ne distingue pas l'établi du traditionnel (US-161), et cette
    curation ne lui fait dire ni plus ni moins que ce qu'elle affirme.

    Ne résout AUCUN nom vers une fiche réelle : `culture` et `compagnon` sont
    des noms français plausibles, la vérification qu'une fiche `culture_config`
    ou `familles_botaniques` existe réellement est le travail de l'import
    (`app.services.associations.importer_association`), jamais de cette
    fonction — elle ne touche ni la base ni le réseau.
    """
    rapport = RapportCuration(brutes=len(aretes_brutes))
    natures: dict[tuple[str, str], set[str]] = defaultdict(set)

    for arete in aretes_brutes:
        culture = arete["culture"]
        compagnon = arete["compagnon_source"]
        libelle = f"{culture} × {compagnon}"

        cible = CIBLE_COMPAGNONS.get(compagnon)
        if cible is None:
            rapport.hors_perimetre.append(libelle)
            continue
        if (culture, compagnon) in MOTIFS_RECYCLES_A_EXCLURE:
            rapport.motifs_recycles.append(libelle)
            continue
        _type_cible, nom_cible = cible
        if nom_cible == culture:
            rapport.auto_associations.append(libelle)
            continue

        natures[(culture, nom_cible)].add(arete["nature"])

    contradictions = {cle for cle, valeurs in natures.items() if len(valeurs) > 1}
    for cle in contradictions:
        culture, nom_cible = cle
        rapport.contradictions.append(f"{culture} × {nom_cible}")

    entrees: list[dict] = []
    for (culture, nom_cible), valeurs in sorted(natures.items()):
        if (culture, nom_cible) in contradictions:
            continue
        motif = MOTIFS_FR.get((culture, nom_cible))
        if motif is None:
            rapport.motifs_non_traduits.append(f"{culture} × {nom_cible}")
            continue
        entrees.append({
            "culture": culture,
            "compagnon": nom_cible,
            "nature": next(iter(valeurs)),
            "motif": motif,
            "niveau_preuve": "traditionnel",
        })
    rapport.retenues = len(entrees)
    return entrees, rapport


def formater_resultat(resultat: ResultatAdaptation) -> str:
    """Compte rendu console de l'adaptation."""
    lignes = ["", "Adaptation Wind River Greens → manifeste [US-161]", "─" * 48, ""]
    lignes.append("  Cultivars appariés par culture :")
    for culture, nombre in resultat.cultivars_apparies.items():
        alerte = "  ⚠️ base faible" if 0 < nombre < MIN_CULTIVARS else ("  ⛔ aucun" if not nombre else "")
        lignes.append(f"     {culture:12s} {nombre:4d}{alerte}")
    lignes.append("")
    lignes.append(f"  ✅ Attributs retenus : {len(resultat.attributs_retenus)}")
    for entree in resultat.attributs_retenus:
        lignes.append(f"     • {entree}")
    lignes.append("")
    lignes.append(f"  ⬜ Attributs écartés : {len(resultat.attributs_ecartes)} — à saisir à la main")
    for entree in resultat.attributs_ecartes:
        lignes.append(f"     • {entree}")
    lignes.append("")
    lignes.append(
        f"  🔗 Associations extraites (brutes) : {resultat.associations} — "
        "wind_river_associations.json, matériau de relecture, jamais à importer"
    )
    if resultat.associations_contradictoires:
        lignes.append(
            f"  ⚠️  Paires contradictoires écartées à l'extraction : {len(resultat.associations_contradictoires)} — "
            f"{', '.join(resultat.associations_contradictoires[:5])}"
            f"{'…' if len(resultat.associations_contradictoires) > 5 else ''}"
        )
    lignes.append("")
    curation = resultat.curation_associations
    if curation is not None:
        lignes.append("  Curation des associations [US-163] — bloc cultures_associations, importable :")
        lignes.append(f"     ✅ retenues, traduites            : {curation.retenues} / {curation.brutes}")
        lignes.append(f"     ⛔ hors périmètre (ornementales…) : {len(curation.hors_perimetre)}")
        lignes.append(f"     ⛔ motifs recyclés (audit)         : {len(curation.motifs_recycles)}")
        lignes.append(f"     ⛔ auto-associations               : {len(curation.auto_associations)}")
        if curation.contradictions:
            lignes.append(
                f"     ⚠️  contradictions après fusion des doublons : {len(curation.contradictions)} — "
                f"{', '.join(curation.contradictions)}"
            )
        if curation.motifs_non_traduits:
            lignes.append(
                f"     ⚠️  sans traduction dans MOTIFS_FR (à corriger) : "
                f"{len(curation.motifs_non_traduits)} — {', '.join(curation.motifs_non_traduits)}"
            )
        lignes.append("")
    lignes.append(f"  ⏱️  Durées du calendrier retenues [US-068] : {len(resultat.durees_retenues)}")
    for entree in resultat.durees_retenues:
        lignes.append(f"     • {entree}")
    lignes.append(f"  ⬜ Durées écartées : {len(resultat.durees_ecartees)} — à saisir au bot si besoin")
    for entree in resultat.durees_ecartees:
        lignes.append(f"     • {entree}")
    lignes.append("")
    zones = ", ".join(f"{zone} ← USDA {usda}" for zone, usda in ZONE_USDA_PAR_ZONE.items())
    lignes.append(f"  🗓️  Fenêtres du calendrier retenues [US-068] : {len(resultat.fenetres_retenues)}")
    lignes.append(f"     Zones lues ({zones}) — décision déclarée, à valider")
    for entree in resultat.fenetres_retenues:
        lignes.append(f"     • {entree}")
    lignes.append(f"  ⬜ Fenêtres écartées : {len(resultat.fenetres_ecartees)} — à saisir au bot si besoin")
    for entree in resultat.fenetres_ecartees:
        lignes.append(f"     • {entree}")
    lignes.append(
        f"  ⚠️  Calendriers incomplets (printemps seulement) : {len(resultat.fenetres_incompletes)}"
    )
    for entree in resultat.fenetres_incompletes:
        lignes.append(f"     • {entree}")
    lignes.append(
        f"  ⚠️  Pépinière / repiquage / plantation qui ne s'enchaînent pas [CA24] : "
        f"{len(resultat.fenetres_incoherentes)} — signalés, rien n'est ajusté"
    )
    for entree in resultat.fenetres_incoherentes:
        lignes.append(f"     • {entree}")
    sans_cultivar = [c for c, n in resultat.cultivars_calendrier.items() if not n]
    if sans_cultivar:
        lignes.append(f"  ⛔ Aucun cultivar apparié pour le calendrier : {', '.join(sans_cultivar)}")
    lignes.append("")
    lignes.append("  ⛔ Non produits par cet adaptateur, par construction :")
    lignes.append("     profondeur_semis_cm — absente du jeu de données")
    lignes.append("     rusticite_min_c     — usda_zone_min décrit la pérennité, pas la culture")
    lignes.append("     semis d'été/automne — le calendrier source ne connaît que le printemps")
    lignes.append("")
    return "\n".join(lignes)

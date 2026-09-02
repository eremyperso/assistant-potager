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
- ❌ **Le calendrier est écarté.** Il est en mois × zone USDA, calé sur des dates
  de gelée nord-américaines. La zone 8 USDA contient Seattle et Dallas : elle ne
  mesure que le froid hivernal minimal, ni les étés ni la pluviométrie. Le
  calendrier français relève d'US-068, décliné par zone climatique et recalé sur
  les événements réels — pas d'une conversion de zone USDA.

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
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from app.services import attributs_culture as svc_attributs
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


def selectionner_cultivars(lignes: Iterable[dict]) -> dict[str, list[dict]]:
    """Range les lignes de `varieties.csv` sous celle de nos cultures qu'elles
    décrivent. Une ligne qui n'en décrit aucune est simplement ignorée — le jeu
    de données couvre 1 972 cultivars, notre périmètre en concerne une fraction."""
    par_culture: dict[str, list[dict]] = {a.culture: [] for a in APPARIEMENTS}
    for ligne in lignes:
        for appariement in APPARIEMENTS:
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
    lignes.append("  ⛔ Non produits par cet adaptateur, par construction :")
    lignes.append("     profondeur_semis_cm — absente du jeu de données")
    lignes.append("     rusticite_min_c     — usda_zone_min décrit la pérennité, pas la culture")
    lignes.append("     calendrier          — zones USDA nord-américaines, relève d'US-068")
    lignes.append("")
    return "\n".join(lignes)

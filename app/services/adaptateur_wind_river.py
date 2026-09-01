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

Les associations (`companion_plants.csv`, 21 880 arêtes) sont extraites dans un
**fichier séparé**, jamais dans le manifeste d'import. Un manifeste sert à
importer ; y laisser un bloc que l'import ignore aujourd'hui reviendrait à parier
qu'aucune évolution future ne le consommera sans revue. Leur table d'accueil est
celle d'US-163, et l'audit du 01/09/2026 (voir `envelopper_associations`) montre
qu'elles ont besoin d'une relecture avant d'y entrer.

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
            "Le bloc 'cultures_associations' n'est PAS importé aujourd'hui : sa table",
            "d'accueil relève d'US-163. Il est extrait ici pour ne pas refaire le travail.",
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
        associations = envelopper_associations(
            construire_associations(companions, par_culture, resultat),
            manifeste["source"], extrait_le,
        )

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
            "[US-161] Extraction BRUTE et NON RÉVISÉE des associations de cultures.",
            "Matière première pour US-163 — ce fichier n'est PAS un manifeste d'import",
            "et ne doit pas être passé à tools/importer_referentiel.py.",
            "",
            "⚠️ AUDIT DU 01/09/2026 SUR LA RELEASE v1.0.0 — à traiter avant tout usage :",
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
        f"  🔗 Associations extraites : {resultat.associations} — fichier séparé, "
        "BRUTES et non révisées (US-163)"
    )
    if resultat.associations_contradictoires:
        lignes.append(
            f"  ⚠️  Paires contradictoires écartées : {len(resultat.associations_contradictoires)} — "
            f"{', '.join(resultat.associations_contradictoires[:5])}"
            f"{'…' if len(resultat.associations_contradictoires) > 5 else ''}"
        )
    lignes.append("")
    lignes.append("  ⛔ Non produits par cet adaptateur, par construction :")
    lignes.append("     profondeur_semis_cm — absente du jeu de données")
    lignes.append("     rusticite_min_c     — usda_zone_min décrit la pérennité, pas la culture")
    lignes.append("     calendrier          — zones USDA nord-américaines, relève d'US-068")
    lignes.append("")
    return "\n".join(lignes)

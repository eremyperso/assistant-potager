"""
tools/controler_corpus_agronomie.py — La relecture, rendue exécutable [US-140]
================================================================================
US-140 répète six fois la même phrase sous six formes : *une fiche qui contient
ceci est refusée à la relecture*. Une relecture humaine ne tient pas cette
promesse sur la durée — elle la tient le jour de la livraison, puis se fatigue.
Ce contrôle en fait une commande, exécutée au déploiement au même titre que
`tools/controler_aide_corpus.py` l'est pour US-099.

Ce qu'il refuse, et le critère qui l'exige :

| Refus | Critère |
|---|---|
| licence absente ou hors socle | CA2, CA3 |
| `source:` qui n'est pas l'attribution du registre pour cette licence | CA4 |
| plan de fiche non conforme (thème, métadonnées de section) | CA13 (c) |
| moins de trois alias dans « On parle aussi de » | CA6 |
| un chiffre, une unité, un mois, une durée dans le texte servi | CA7, CA13 (a) |
| une association de cultures ou une règle de rotation | CA7bis |
| un dosage, un produit de traitement | CA10 |
| une section de diagnostic affirmative, sans hypothèse | CA9 |

**Le texte contrôlé est celui qui sera SERVI**, pas le fichier brut : les lignes
`**Intention :**`, `**Organes concernés :**` et `**On parle aussi de :**` sont
retirées par le découpage d'US-098 avant d'atteindre le jardinier, et le
contrôle les retire exactement de la même façon — en réutilisant le découpage
de `tools/ingerer_connaissance.py`, jamais en en écrivant un second. Un alias
« taches marron » n'est donc pas compté comme du contenu, et une consigne de
rédaction n'est pas contrôlée comme une phrase servie.

Utilisation :
    python tools/controler_corpus_agronomie.py
    python tools/controler_corpus_agronomie.py --detail
    python tools/controler_corpus_agronomie.py --racine <dossier>

Zéro appel réseau, zéro appel modèle, zéro accès base — comme les deux autres
outils de corpus. Il lit le DÉPÔT, qui est la source.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# La console Windows par défaut est en cp1252 : sans cela, le rapport plante à
# l'affichage sur un simple « ✅ ». Un outil de contrôle ne doit pas échouer sur
# son encodage de sortie.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):  # flux redirigé qui ne le supporte pas
    pass

from unidecode import unidecode  # noqa: E402

from app.services import referentiel_sources  # noqa: E402
from tools.ingerer_connaissance import (  # noqa: E402
    DocumentInvalide, Section, decouper, lire_entete, valider_licence,
)

RACINE_PAR_DEFAUT = "data/connaissance/agronomie"

# [CA13 (c)] « Plan de fiche imposé et identique pour toutes ». Le thème est
# porté par le NOM DU FICHIER, `<culture>-<theme>.md` : c'est ce qui rend le
# plan visible au premier coup d'œil sur le dossier, sans ouvrir une fiche.
THEMES_IMPOSES: frozenset[str] = frozenset({"problemes", "conduite-recolte"})

# [CA5] Ce que chaque culture retenue doit posséder, au minimum : « maladies et
# ravageurs courants avec leurs symptômes, et gestes courants d'entretien et de
# récolte ». Un thème par besoin, pas un de plus.
THEMES_REQUIS_PAR_CULTURE: tuple[str, ...] = ("problemes", "conduite-recolte")

# [CA13 (c)] Les trois lignes de métadonnée qu'une section porte SANS EXCEPTION.
# Elles ne s'affichent pas ; deux d'entre elles sont indexées au poids du titre,
# et c'est par elles que la recherche lexicale retrouve la fiche (CA6).
METADONNEES_DE_SECTION: tuple[str, ...] = (
    "Intention", "Organes concernés", "On parle aussi de",
)

# [CA6] Nombre minimal d'alias dans « On parle aussi de ». Trois n'est pas un
# chiffre magique : c'est le minimum pour qu'une section porte le mot du
# jardinier, celui de l'agronome, et la variante que l'un des deux emploie.
ALIAS_MINIMUM = 3

# Règle ④ du runbook : au-delà, le passage servi devient un mur de texte dans un
# message Telegram ; en deçà, ce n'est pas une réponse.
LONGUEUR_MIN = 80
LONGUEUR_MAX = 1200

_SEPARATEURS_ALIAS = (";", "·")
_LIGNE_METADONNEE = re.compile(
    r"^[ \t]*\*\*(?P<cle>[^:*\n]+?)[ \t]*:\*\*[ \t]*(?P<valeur>[^\n]*)$", re.MULTILINE
)
_TITRE_SECTION = re.compile(r"^##\s+(.*?)\s*$", re.MULTILINE)


# ─────────────────────────────────────────────────────────────────────────────
# Ce qu'une fiche ne contient jamais — un motif, un critère, un message
# ─────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Interdit:
    critere: str
    motif: "re.Pattern[str]"
    explication: str


#: Les motifs s'appliquent au texte SERVI, débarrassé de ses accents et mis en
#: minuscules — un jardinier écrit « oidium », une fiche écrit « oïdium », et un
#: contrôle qui distinguerait les deux ne contrôlerait qu'une moitié du corpus.
INTERDITS: tuple[Interdit, ...] = (
    Interdit(
        "CA7/CA13a", re.compile(r"[0-9]"),
        "un chiffre — dates, durées, doses et profondeurs relèvent du référentiel "
        "calendrier (US-068) et du référentiel structuré (US-161), jamais d'une fiche",
    ),
    Interdit(
        "CA7", re.compile(
            r"\b(janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|"
            r"octobre|novembre|decembre)\b"
        ),
        "un nom de mois — le calendrier appartient à US-068, décliné par zone climatique",
    ),
    Interdit(
        "CA7", re.compile(
            r"\b(jours?|semaines?|mois|ans?|annees?|heures?|minutes?)\b"
        ),
        "une durée — une fiche décrit un état observable, elle ne chiffre pas le temps",
    ),
    Interdit(
        "CA7/CA13a", re.compile(
            r"\b(cm|mm|centimetres?|metres?|litres?|grammes?|kilos?|kg|degres?)\b"
        ),
        "une unité de mesure — espacements, profondeurs et doses viennent du "
        "référentiel structuré ou ne figurent pas",
    ),
    # Volontairement ancré sur les tournures RELATIONNELLES, pas sur le verbe
    # « associer » seul : « un duvet gris associé à des plages jaunes » décrit un
    # symptôme, pas une association de cultures. Un motif trop large refuse des
    # fiches justes, et une règle qu'on doit contourner à la rédaction finit
    # désactivée.
    Interdit(
        "CA7bis", re.compile(
            r"\b(associations? de cultures?|cultures? associees?|associer (?:la|le|les|avec|a) \w+|"
            r"compagnonnage|plantes? compagnes?|bon voisinage|rotation|assolement|"
            r"precedent cultural|delai de retour)\b"
        ),
        "une association ou une rotation — ce sont des arêtes entre cultures "
        "(US-163), invisibles du calcul si elles sont écrites dans une fiche",
    ),
    Interdit(
        "CA7bis", re.compile(
            r"\b(planter|semer|cultiver|remettre|revenir)\b[^.]{0,40}\bapres\b"
        ),
        "une règle de succession sur la parcelle — c'est le calcul de rotation "
        "(US-163), pas du texte de fiche",
    ),
    Interdit(
        "CA10", re.compile(
            r"\b(dose|doses|dosage|diluer|dilution|bouillie bordelaise|insecticide|"
            r"fongicide|pesticide|phytosanitaire|soufre|sulfate de cuivre|pyrethre|"
            r"savon noir|purin de)\b"
        ),
        "un produit ou un dosage — « l'assistant n'est pas un conseiller en traitement »",
    ),
    Interdit(
        "CA10", re.compile(r"%"),
        "un pourcentage — presque toujours une dilution déguisée",
    ),
)

# [CA9] « Une réponse de diagnostic présente des hypothèses ordonnées, jamais une
# certitude. » La marque de la prudence est LEXICALE et se contrôle : une section
# de diagnostic qui n'emploie aucune de ces tournures affirme.
MARQUEURS_PRUDENCE: tuple[str, ...] = (
    "peut ", "peuvent ", "souvent", "parfois", "plutot", "probable", "probablement",
    "oriente vers", "orientent vers", "evoque", "evoquent", "suggere", "suggerent",
    "plusieurs causes", "n'est pas une preuve", "ne suffit pas", "en cas de doute",
    "generalement", "rarement", "sans certitude", "pas forcement", "incertain",
)


# ─────────────────────────────────────────────────────────────────────────────
# Lecture
# ─────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class SectionLue:
    intitule: str
    contenu: str                 # le texte SERVI, métadonnées retirées
    metadonnees: dict[str, str]  # les lignes `**Clé :** valeur` de la section


@dataclass(frozen=True)
class FicheAgronomie:
    chemin: Path
    entete: dict[str, str]
    sections: tuple[SectionLue, ...]

    @property
    def culture(self) -> str:
        return self.chemin.stem.split("-", 1)[0]

    @property
    def theme(self) -> str:
        return self.chemin.stem.split("-", 1)[1] if "-" in self.chemin.stem else ""


@dataclass
class Rapport:
    fiches: int = 0
    sections: int = 0
    refus: list[str] = field(default_factory=list)

    @property
    def conforme(self) -> bool:
        return not self.refus


def _aplatir(texte: str) -> str:
    """Forme comparable : sans accent, en minuscules, espaces normalisés."""
    return " ".join(unidecode(texte).lower().split())


def lire_fiche(chemin: Path) -> FicheAgronomie:
    """Lit une fiche et en rend les sections telles qu'elles seront SERVIES.

    Le découpage vient de `tools/ingerer_connaissance.decouper` : contrôler un
    texte différent de celui qui part à l'index reviendrait à contrôler un
    document qui n'existe pas.
    """
    texte = chemin.read_text(encoding="utf-8")
    entete, corps = lire_entete(texte)

    # Les métadonnées, elles, se relisent sur le corps brut : le découpage les a
    # justement retirées, et le CA13 (c) porte sur leur présence.
    brutes: dict[str, dict[str, str]] = {}
    positions = [(m.start(), m.end(), m.group(1)) for m in _TITRE_SECTION.finditer(corps)]
    for index, (_, fin_titre, intitule) in enumerate(positions):
        fin = positions[index + 1][0] if index + 1 < len(positions) else len(corps)
        brutes[intitule.strip()] = {
            _aplatir(m.group("cle")): m.group("valeur").strip()
            for m in _LIGNE_METADONNEE.finditer(corps[fin_titre:fin])
        }

    sections: list[SectionLue] = []
    for decoupee in decouper(corps):  # type: Section
        if decoupee.intitule is None:
            # Un préambule dans une fiche d'agronomie est un défaut de plan :
            # le CA13 (c) impose des sections, et une idée hors section n'a pas
            # d'intitulé, donc pas de question à laquelle répondre.
            sections.append(SectionLue(intitule="", contenu=decoupee.contenu, metadonnees={}))
            continue
        sections.append(SectionLue(
            intitule=decoupee.intitule,
            contenu=decoupee.contenu,
            metadonnees=brutes.get(decoupee.intitule.strip(), {}),
        ))
    return FicheAgronomie(chemin=chemin, entete=entete, sections=tuple(sections))


def decouper_alias(valeur: str) -> tuple[str, ...]:
    """Les alias de « On parle aussi de », séparés par `;` ou `·`.

    La virgule n'est PAS un séparateur ici, contrairement aux domaines d'aide :
    un alias de jardinier en contient (« des taches marron, plutôt huileuses »),
    et le découper produirait des alias tronqués qui ne correspondent à rien.
    """
    fragments = [valeur]
    for separateur in _SEPARATEURS_ALIAS:
        fragments = [b for morceau in fragments for b in morceau.split(separateur)]
    return tuple(f.strip() for f in fragments if f.strip())


# ─────────────────────────────────────────────────────────────────────────────
# Contrôles
# ─────────────────────────────────────────────────────────────────────────────
def controler_fiche(fiche: FicheAgronomie) -> list[str]:
    """Rend la liste des refus opposés à cette fiche — vide si elle passe."""
    refus: list[str] = []
    nom = fiche.chemin.name

    # ── CA2, CA3 — la licence, avant tout le reste ───────────────────────────
    try:
        valider_licence(fiche.entete.get("famille", ""), fiche.entete.get("licence"))
    except DocumentInvalide as erreur:
        refus.append(f"{nom} · [CA3] {erreur}")

    # ── CA4 — l'attribution affichée est celle du registre ───────────────────
    licence = (fiche.entete.get("licence") or "").strip()
    source = (fiche.entete.get("source") or "").strip()
    attributions = {
        entree["attribution"]
        for entree in referentiel_sources.SOURCES_SOCLE
        if entree["licence"] == licence
    }
    if licence and attributions and source not in attributions:
        refus.append(
            f"{nom} · [CA4] `source:` affiché « {source} » n'est pas l'attribution du "
            f"registre pour la licence « {licence} » — attendu parmi : "
            f"{', '.join(sorted(attributions))}"
        )

    # ── CA13 (c) — le plan imposé ────────────────────────────────────────────
    if fiche.theme not in THEMES_IMPOSES:
        refus.append(
            f"{nom} · [CA13c] thème « {fiche.theme or '—'} » hors du plan imposé "
            f"({', '.join(sorted(THEMES_IMPOSES))}) — le nom de fichier porte le plan"
        )
    if (fiche.entete.get("culture") or "").strip() == "":
        refus.append(f"{nom} · [CA13c] en-tête sans `culture:` — le fragment perdrait son rattachement")

    for section in fiche.sections:
        etiquette = f"{nom} · « {section.intitule or 'préambule'} »"
        if not section.intitule:
            refus.append(f"{etiquette} · [CA13c] texte hors section — une idée sans intitulé n'a pas de question")
            continue
        for cle in METADONNEES_DE_SECTION:
            if _aplatir(cle) not in section.metadonnees:
                refus.append(f"{etiquette} · [CA13c] ligne `**{cle} :**` absente")

        # ── CA6 — les deux registres, dans la section ────────────────────────
        alias = decouper_alias(section.metadonnees.get(_aplatir("On parle aussi de"), ""))
        if len(alias) < ALIAS_MINIMUM:
            refus.append(
                f"{etiquette} · [CA6] {len(alias)} alias dans « On parle aussi de », "
                f"{ALIAS_MINIMUM} attendus — c'est la ligne qui décide si la fiche est retrouvée"
            )

        # ── Règle ④ du runbook — ni trop court, ni mur de texte ──────────────
        longueur = len(section.contenu.strip())
        if longueur < LONGUEUR_MIN:
            refus.append(f"{etiquette} · [US-098/CA12] {longueur} caractères — trop court pour porter une idée")
        if longueur > LONGUEUR_MAX:
            refus.append(f"{etiquette} · [runbook ④] {longueur} caractères — mur de texte dans un message")

        # ── CA7, CA7bis, CA10, CA13 (a) — ce qui ne s'écrit jamais ───────────
        aplati = _aplatir(f"{section.intitule} {section.contenu}")
        for interdit in INTERDITS:
            trouve = interdit.motif.search(aplati)
            if trouve:
                refus.append(
                    f"{etiquette} · [{interdit.critere}] « {trouve.group(0)} » : {interdit.explication}"
                )

        # ── CA9 — un diagnostic propose, il n'affirme pas ────────────────────
        if fiche.theme == "problemes" and not any(m in aplati for m in MARQUEURS_PRUDENCE):
            refus.append(
                f"{etiquette} · [CA9] aucune tournure d'hypothèse — une section de diagnostic "
                "présente des causes possibles par ordre de probabilité, jamais une certitude"
            )

    return refus


def controler_couverture(fiches: list[FicheAgronomie], cultures: tuple[str, ...]) -> list[str]:
    """[CA1, CA5] Chaque culture du périmètre possède les thèmes du plan.

    Une culture qui n'aurait que ses problèmes serait un assistant qui sait dire
    ce qui va mal et pas quoi faire — exactement l'inverse de l'US.
    """
    refus: list[str] = []
    presents = {(fiche.culture, fiche.theme) for fiche in fiches}
    for culture in cultures:
        for theme in THEMES_REQUIS_PAR_CULTURE:
            if (culture, theme) not in presents:
                refus.append(f"[CA1/CA5] {culture} : fiche « {theme} » absente du périmètre")
    return refus


def controler(racine: Path, cultures: tuple[str, ...] = ()) -> tuple[Rapport, list[FicheAgronomie]]:
    rapport = Rapport()
    fiches: list[FicheAgronomie] = []
    for chemin in sorted(racine.rglob("*.md")):
        if chemin.name.upper() == "README.MD":
            continue
        try:
            fiche = lire_fiche(chemin)
        except DocumentInvalide as erreur:
            rapport.refus.append(f"{chemin.name} : {erreur}")
            continue
        fiches.append(fiche)
        rapport.fiches += 1
        rapport.sections += len(fiche.sections)
        rapport.refus.extend(controler_fiche(fiche))
    if cultures:
        rapport.refus.extend(controler_couverture(fiches, cultures))
    return rapport, fiches


def cultures_du_perimetre(racine: Path) -> tuple[str, ...]:
    """Les cultures effectivement présentes, déduites des noms de fichier.

    Volontairement déduites et non codées en dur : le périmètre du CA1 est
    révisable sur mesure de production, et une liste figée ici rendrait cette
    révision plus coûteuse qu'un renommage de fichiers.
    """
    return tuple(sorted({
        chemin.stem.split("-", 1)[0]
        for chemin in racine.rglob("*.md")
        if chemin.name.upper() != "README.MD"
    }))


def main(argv: "Optional[list[str]]" = None) -> int:
    parser = argparse.ArgumentParser(
        description="Contrôle éditorial du corpus agronomique (US-140 / CA3-CA13)."
    )
    parser.add_argument("--racine", default=RACINE_PAR_DEFAUT,
                        help=f"Dossier des fiches d'agronomie (défaut : {RACINE_PAR_DEFAUT})")
    parser.add_argument("--detail", action="store_true",
                        help="Liste chaque fiche et son nombre de sections")
    args = parser.parse_args(argv)

    racine_depot = Path(__file__).resolve().parent.parent
    racine = Path(args.racine)
    if not racine.is_absolute():
        racine = (racine_depot / racine).resolve()
    if not racine.is_dir():
        print(f"Racine introuvable : {racine}")
        return 2

    cultures = cultures_du_perimetre(racine)
    rapport, fiches = controler(racine, cultures)

    print(f"── RELECTURE DU CORPUS AGRONOMIQUE (US-140) · {racine} ──")
    print(f"Fiches   : {rapport.fiches} · sections : {rapport.sections} · "
          f"cultures : {len(cultures)}")
    if args.detail:
        for fiche in fiches:
            marque = "✅" if not controler_fiche(fiche) else "❌"
            print(f"  {marque} {fiche.chemin.name:<34} {len(fiche.sections)} section(s) · "
                  f"{fiche.entete.get('niveau_confiance', '—')}")

    if rapport.refus:
        print(f"\n❌ {len(rapport.refus)} refus à la relecture :")
        for ligne in rapport.refus:
            print(f"   · {ligne}")
        print("\nUne fiche refusée se corrige dans le dépôt, jamais en base.")
        return 1

    print("\n✅ Toutes les fiches passent la relecture.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

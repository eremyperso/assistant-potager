"""
tools/ingerer_connaissance.py — Ingestion du corpus de connaissance [US-098 / CA10-CA12]
==========================================================================================
Transforme les documents Markdown VERSIONNÉS DANS LE DÉPÔT en documents et
fragments indexés. La base est l'index, le dépôt est la source (arbitrage
tranché de l'US) : ce script ne crée jamais de contenu, il projette celui du
dépôt. Rien ne s'édite en base, tout se corrige dans les fichiers puis se
réingère.

Utilisation :
    python tools/ingerer_connaissance.py                     # ingère data/connaissance/
    python tools/ingerer_connaissance.py --dry-run           # rapport seul, aucune écriture
    python tools/ingerer_connaissance.py --racine <dossier>  # autre racine (corpus de test)
    python tools/ingerer_connaissance.py --strict            # échoue sur un défaut de découpage
    python tools/ingerer_connaissance.py --elaguer           # retire aussi les documents disparus du dépôt

[CA10] Idempotent et rejouable. L'empreinte SHA-256 du fichier décide : même
empreinte, aucune écriture — pas même un UPDATE. Relancer deux fois de suite ne
crée aucun doublon et ne touche aucune ligne au second passage.

[CA11] Un document MODIFIÉ voit ses fragments intégralement remplacés, et les
réponses figées qui dérivaient des fragments disparus sont invalidées
(`app.services.cache_questions.invalider_par_fragment`, US-095 / CA10).
Corriger une fiche ne doit pas laisser survivre des mois une réponse erronée.

[CA12] Le découpage suit les titres de niveau 2 (`## `) : une section, un
fragment, une idée répondable. Le titre du document est conservé sur chaque
fragment. Les fragments qui n'ont manifestement pas de sens seuls (trop courts,
ouverts par un connecteur ou un pronom de reprise) sont SIGNALÉS : un fragment
qui n'a de sens qu'avec le précédent est un défaut de découpage, et il doit se
voir avant d'être indexé, pas se découvrir dans une mauvaise réponse.

⚠️ RLS (migration_v42) : les documents GLOBAUX (`potager_id` absent de
l'en-tête) ne peuvent être écrits que par le rôle propriétaire de la base,
jamais par `app_user` — même règle que `tools/importer_referentiel.py` pour le
référentiel partagé. Vérifier le `DATABASE_URL` avant d'exécuter en production.

Format attendu d'un fichier
---------------------------
    ---
    titre: "Problèmes observables de tomate"
    famille: agronomie                     # agronomie | doc_app | memoire_potager
    source: "Rédaction interne"            # ce qui s'affiche « _Source : …_ »
    niveau_confiance: a-valider            # verifie | indicatif | a-valider
    culture: tomate                        # facultatif — DOIT exister dans culture_config
    type: maladie                          # facultatif
    saison: ete                            # facultatif
    potager_id: 3                          # facultatif — savoir privé (US-141)
    index_terms:                           # index de relecture — NON indexé
      - "cul noir"
    sources:                               # organismes consultés — NON indexé
      - organisme: "USDA National Agricultural Library"
        licence: "Domaine public"
    ---

    # Problèmes observables de tomate        ← H1 ignoré (recopie `titre:`)

    ## Mes tomates ont le cul noir par dessous

    **Intention :** diagnostic                ← retiré du texte, NON indexé
    **Organes concernés :** fruit             ← retiré du texte, INDEXÉ
    **On parle aussi de :** cul noir ; nécrose apicale ; manque de calcium

    …une idée, répondable telle quelle…

    ## Sources et licence                     ← section ignorée (pied de fiche)

    …

L'en-tête est lu par un analyseur `clé: valeur` écrit ici même, volontairement :
le projet n'a pas de dépendance YAML et l'US en interdit d'en ajouter une. Les
blocs en liste sont tolérés et traversés sans être lus — le schéma n'a qu'un
champ `source` scalaire, et `index_terms` au niveau du document dilue plus qu'il
ne discrimine (mesuré : 19/19 en tête sans lui, 18/19 avec).

Deux registres obligatoires dans « On parle aussi de » : celui du jardinier
(« cul noir », « poudre blanche ») ET celui de l'agronome (« nécrose apicale »,
« oïdium »). La recherche est LEXICALE : un lemme absent de l'index est un
rapprochement impossible, quelle que soit la qualité du texte.

Zéro appel réseau, zéro appel modèle — comme `tools/importer_referentiel.py`.
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# La console Windows par défaut est en cp1252 : sans cela, le rapport plante à
# l'affichage sur un simple « ✅ ». Un outil de mesure ne doit pas échouer sur
# son encodage de sortie.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):  # flux redirigé qui ne le supporte pas
    pass


from app.services import cache_questions, connaissance  # noqa: E402
from database.db import SessionLocal  # noqa: E402
from database.models import CultureConfig, KnowledgeDocument  # noqa: E402

log = logging.getLogger("potager")

RACINE_PAR_DEFAUT = "data/connaissance"

# [CA12] Un fragment plus court que ceci ne porte pas une idée : c'est un
# titre orphelin ou une phrase de liaison.
_LONGUEUR_MIN_FRAGMENT = 80

# [CA12] Ouvertures qui trahissent une dépendance au fragment précédent — un
# fragment autonome nomme son sujet, il ne le reprend pas par un pronom.
_OUVERTURES_DEPENDANTES = (
    "il ", "elle ", "ils ", "elles ", "celui", "celle", "ceux", "cela ", "ça ",
    "ensuite", "puis ", "en revanche", "au contraire", "de plus", "par ailleurs",
    "c'est pourquoi", "pour cela", "dans ce cas", "à l'inverse", "a l'inverse",
    "cette ", "ce dernier", "cette dernière", "cette derniere",
)

_ENTETE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_TITRE_SECTION = re.compile(r"^##\s+(.*?)\s*$", re.MULTILINE)
_NON_ALPHANUM = re.compile(r"[^a-z0-9]+")

# Un `# H1` en tête de corps reprend `titre:` — c'est un réflexe Markdown
# normal, pas du contenu. L'indexer produisait un fragment de préambule qui
# sortait en tête sur le seul nom de la culture, sans rien répondre.
_H1 = re.compile(r"^#\s+[^\n]*$", re.MULTILINE)

# Sections de pied de fiche : lisibles par un relecteur humain, sans valeur de
# réponse. Sans cette exclusion, « Sources et licence » remontait à 0.919 de
# confiance — un fragment servi comme faisant autorité qui ne répond rien.
_SECTIONS_NON_INDEXEES = frozenset({
    "sources et licence", "sources et licences", "sources", "licence", "licences",
    "references", "reference",
})

# Métadonnée éditoriale d'une section, format `**Clé :** valeur`. Ces lignes
# sont RETIRÉES du contenu — donc jamais servies au jardinier — et, pour
# certaines, versées dans l'index au poids du titre.
_LIGNE_METADONNEE = re.compile(
    r"^[ \t]*\*\*(?P<cle>[^:*\n]+?)[ \t]*:\*\*[ \t]*(?P<valeur>[^\n]*)$", re.MULTILINE
)

# Ce qui est indexé : les mots que le jardinier tape réellement. « On parle
# aussi de » porte les deux registres, amateur et agronomique (« cul noir » et
# « nécrose apicale ») ; « Organes concernés » porte « mes feuilles », « le
# fruit ». Un lemme absent de l'index est un rapprochement impossible.
_METADONNEES_INDEXEES = frozenset({
    "on parle aussi de", "organes concernes", "organe", "aliases", "alias",
})
# `intention` (« diagnostic », « comprendre la cause ») reste dans le fichier
# comme repère de rédaction mais n'est PAS indexé : personne ne tape ces mots,
# et les verser à l'index n'ajoute que du bruit.
_METADONNEES_CONNUES = _METADONNEES_INDEXEES | frozenset({"intention"})

# États éditoriaux tolérés en en-tête, repliés sur le vocabulaire du schéma.
# `niveau_confiance` pilote un comportement binaire — servir mot pour mot, ou
# descendre en contexte vers l'étage de raisonnement — et une fiche non encore
# relue phrase par phrase se comporte comme `indicatif`. L'intention éditoriale
# reste portée par le fichier (`version:`), qui est la source.
_NIVEAUX_EDITORIAUX = {
    "a-valider": connaissance.NIVEAU_INDICATIF,
    "a valider": connaissance.NIVEAU_INDICATIF,
}


# ─────────────────────────────────────────────────────────────────────────────
# Lecture d'un fichier
# ─────────────────────────────────────────────────────────────────────────────
class DocumentInvalide(Exception):
    """Le fichier n'est pas ingérable en l'état — signalé, jamais deviné."""


@dataclass(frozen=True)
class Section:
    intitule: Optional[str]
    contenu: str
    # Alias d'indexation : indexés au poids du titre, absents de `contenu`.
    termes_indexation: str = ""


def _sans_guillemets(valeur: str) -> str:
    """Retire une PAIRE de guillemets encadrants, jamais un apostrophe isolé —
    `d'été` doit traverser intact."""
    valeur = valeur.strip()
    if len(valeur) >= 2 and valeur[0] == valeur[-1] and valeur[0] in "\"'":
        return valeur[1:-1].strip()
    return valeur


def lire_entete(texte: str) -> tuple[dict[str, str], str]:
    """Sépare l'en-tête `clé: valeur` du corps.

    Analyseur volontairement minimal : pas d'imbrication, pas de YAML — l'US
    interdit toute dépendance nouvelle. Une ligne sans deux-points reste
    refusée plutôt qu'ignorée, sauf deux cas qui ne sont pas des fautes :

    · les **continuations indentées** d'un bloc en liste (`sources:`,
      `index_terms:`) ; elles restent dans le `.md` pour le relecteur humain et
      ne remontent pas en base, où `source` est un champ scalaire — celui
      affiché au jardinier, pas la liste des organismes consultés ;
    · les **guillemets** encadrant une valeur, convention d'écriture répandue
      qui ne change pas le sens.

    `index_terms` au niveau du DOCUMENT est donc lu comme une clé à valeur vide,
    et n'est pas indexé — décision mesurée : il pèse identiquement sur toutes
    les sections de la fiche, donc il dilue exactement ce que les alias de
    section discriminent (19/19 en tête sans lui, 18/19 avec). Il garde toute sa
    valeur d'index de relecture dans le fichier.
    """
    correspondance = _ENTETE.match(texte)
    if correspondance is None:
        raise DocumentInvalide("en-tête absent (bloc `---` attendu en tête de fichier)")
    entete: dict[str, str] = {}
    for numero, ligne in enumerate(correspondance.group(1).splitlines(), start=2):
        if ligne[:1] in (" ", "\t"):
            continue  # continuation indentée d'un bloc en liste
        depouillee = ligne.strip()
        if not depouillee or depouillee.startswith("#"):
            continue
        if depouillee.startswith("-"):
            continue  # élément de liste non indenté
        if ":" not in depouillee:
            raise DocumentInvalide(f"ligne d'en-tête {numero} illisible : {depouillee!r}")
        cle, valeur = depouillee.split(":", 1)
        entete[cle.strip().lower()] = _sans_guillemets(valeur)
    return entete, texte[correspondance.end():]


def _normaliser(valeur: str) -> str:
    """Comparaison d'intitulé insensible à la casse et aux accents."""
    from unidecode import unidecode
    return " ".join(unidecode(valeur).lower().split())


def extraire_indexation(contenu: str) -> tuple[str, str]:
    """Sépare les métadonnées de section du texte lisible.

    Rend `(contenu_propre, termes_indexation)`. Les lignes `**Clé :** valeur`
    d'un vocabulaire connu quittent le contenu ; celles d'un vocabulaire indexé
    partent en plus vers `recherche_fts`, au poids du titre.

    Ce partage est le cœur de l'affaire : un alias doit peser à l'index et ne
    jamais s'afficher. Sans lui, le message envoyé au jardinier s'ouvrait sur
    `**Intention :** diagnostic / **Organes concernés :** fruit / **On parle
    aussi de :** cul noir tomate ; …` avant d'en venir à la réponse.

    Une ligne `**Attention :** …` — clé hors vocabulaire — reste du contenu :
    on ne retire que ce qu'on sait nommer.
    """
    termes: list[str] = []

    def _trancher(correspondance: "re.Match[str]") -> str:
        cle = _normaliser(correspondance.group("cle"))
        if cle not in _METADONNEES_CONNUES:
            return correspondance.group(0)
        if cle in _METADONNEES_INDEXEES:
            valeur = correspondance.group("valeur").strip()
            if valeur:
                termes.append(valeur)
        return ""

    propre = _LIGNE_METADONNEE.sub(_trancher, contenu)
    propre = re.sub(r"\n{3,}", "\n\n", propre).strip()
    return propre, " ".join(termes)


def decouper(corps: str) -> list[Section]:
    """[CA12] Une section de niveau 2 = un fragment. Le texte qui précède le
    premier `##` forme un fragment de préambule (sans intitulé) — le perdre
    reviendrait à jeter la définition qui ouvre certaines fiches.

    Deux exclusions, l'une et l'autre mesurées sur du corpus réel :

    · le `# H1` de tête, qui recopie `titre:` ; indexé, il produisait un
      fragment servi à 1.000 de confiance sur « problèmes observables de chou »
      alors qu'il ne contient que ce titre ;
    · les sections de pied (`## Sources et licence`), identiques d'une fiche à
      l'autre, qui remontaient en réponse sur toute question touchant aux mots
      « source » ou « licence ».

    Aucune des deux ne disparaît du fichier : elles restent lisibles par un
    relecteur humain, elles n'entrent simplement pas à l'index.
    """
    sections: list[Section] = []
    positions = [(m.start(), m.end(), m.group(1)) for m in _TITRE_SECTION.finditer(corps)]

    preambule = corps[: positions[0][0]] if positions else corps
    preambule = _H1.sub("", preambule)
    contenu, termes = extraire_indexation(preambule)
    if contenu:
        sections.append(Section(intitule=None, contenu=contenu, termes_indexation=termes))

    for index, (_, fin_titre, intitule) in enumerate(positions):
        debut_suivant = positions[index + 1][0] if index + 1 < len(positions) else len(corps)
        if _normaliser(intitule) in _SECTIONS_NON_INDEXEES:
            continue
        contenu, termes = extraire_indexation(corps[fin_titre:debut_suivant])
        if contenu:
            sections.append(Section(intitule=intitule, contenu=contenu,
                                    termes_indexation=termes))
    return sections


def controler_autonomie(section: Section) -> Optional[str]:
    """[CA12] Signale un fragment qui n'a manifestement pas de sens seul.

    Ne bloque pas par défaut (`--strict` le fait) : c'est un contrôle de
    rédaction, et un faux positif ne doit pas empêcher d'ingérer un corpus par
    ailleurs correct. Mais il doit être VU — sans lui, « il faut alors pailler »
    partirait à l'index comme une réponse à part entière.
    """
    contenu = section.contenu.strip()
    if len(contenu) < _LONGUEUR_MIN_FRAGMENT:
        return f"fragment trop court ({len(contenu)} caractères) pour porter une idée répondable"
    debut = contenu.lower().lstrip("*_-# ")
    for ouverture in _OUVERTURES_DEPENDANTES:
        if debut.startswith(ouverture):
            return f"ouvre par « {ouverture.strip()} » — dépend du fragment précédent"
    return None


def _ardoise(valeur: str) -> str:
    """Fragment d'identifiant lisible et stable tiré d'un intitulé."""
    from unidecode import unidecode
    return _NON_ALPHANUM.sub("-", unidecode(valeur.strip().lower())).strip("-")[:60]


def reference_document(chemin: Path, racine_depot: Path) -> str:
    """[CA10] Identité stable du document : son chemin relatif au dépôt.

    Relatif au DÉPÔT et non à la racine scannée, pour deux raisons : la
    référence reste la même quelle que soit la façon dont on lance l'outil, et
    un corpus de test (`tests/corpus/…`) ne peut jamais entrer en collision avec
    le corpus de production (`data/connaissance/…`).
    """
    absolu = chemin.resolve()
    try:
        return absolu.relative_to(racine_depot).as_posix()
    except ValueError:
        return absolu.as_posix()


# ─────────────────────────────────────────────────────────────────────────────
# Ingestion
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Rapport:
    crees: int = 0
    mis_a_jour: int = 0
    inchanges: int = 0
    supprimes: int = 0
    fragments: int = 0
    invalidations: int = 0
    avertissements: list[str] = None
    erreurs: list[str] = None

    def __post_init__(self):
        self.avertissements = self.avertissements or []
        self.erreurs = self.erreurs or []


def _resoudre_culture(db, nom: Optional[str], potager_id: Optional[int]) -> Optional[int]:
    """[CA2 amendé] Le libellé de l'en-tête est résolu en RÉFÉRENCE vers
    `culture_config`. Une culture absente du référentiel est une erreur, pas un
    `NULL` silencieux : le fragment perdrait sa métadonnée sans que personne ne
    s'en aperçoive avant une mauvaise réponse."""
    if not nom:
        return None
    from sqlalchemy import func, or_
    fiche = (
        db.query(CultureConfig)
        .filter(
            func.lower(CultureConfig.nom) == nom.strip().lower(),
            or_(CultureConfig.potager_id.is_(None), CultureConfig.potager_id == potager_id),
        )
        .first()
    )
    if fiche is None:
        raise DocumentInvalide(
            f"culture {nom!r} absente de culture_config — la rattacher au référentiel "
            f"avant d'ingérer ce document (CA2 : une référence, jamais un libellé)"
        )
    return fiche.id


def ingerer_fichier(db, chemin: Path, racine_depot: Path, rapport: Rapport,
                    dry_run: bool = False) -> None:
    texte = chemin.read_text(encoding="utf-8")
    reference = reference_document(chemin, racine_depot)
    empreinte = hashlib.sha256(texte.encode("utf-8")).hexdigest()

    entete, corps = lire_entete(texte)
    manquantes = [cle for cle in ("titre", "famille", "source", "niveau_confiance") if not entete.get(cle)]
    if manquantes:
        raise DocumentInvalide(f"en-tête incomplet, clés manquantes : {', '.join(manquantes)}")

    potager_id = int(entete["potager_id"]) if entete.get("potager_id") else None
    niveau = _NIVEAUX_EDITORIAUX.get(entete["niveau_confiance"].lower(),
                                     entete["niveau_confiance"])
    connaissance.valider_entete(entete["famille"], niveau)
    culture_id = _resoudre_culture(db, entete.get("culture"), potager_id)

    sections = decouper(corps)
    if not sections:
        raise DocumentInvalide("aucun contenu après l'en-tête")
    for section in sections:
        defaut = controler_autonomie(section)
        if defaut is not None:
            rapport.avertissements.append(
                f"{reference} · « {section.intitule or 'préambule'} » : {defaut}"
            )

    # [CA10] Comparaison d'empreinte AVANT toute écriture : c'est elle, et rien
    # d'autre, qui rend le rejeu gratuit.
    existant = (
        db.query(KnowledgeDocument).filter(KnowledgeDocument.reference == reference).first()
    )
    if existant is not None and existant.empreinte == empreinte:
        rapport.inchanges += 1
        return

    if dry_run:
        if existant is None:
            rapport.crees += 1
        else:
            rapport.mis_a_jour += 1
        rapport.fragments += len(sections)
        return

    document, inchange = connaissance.enregistrer_document(
        db,
        reference=reference,
        titre=entete["titre"],
        famille=entete["famille"],
        source=entete["source"],
        niveau_confiance=niveau,
        empreinte=empreinte,
        potager_id=potager_id,
    )
    if inchange:  # défense : le contrôle ci-dessus l'a déjà écarté
        rapport.inchanges += 1
        return

    fragments = [
        connaissance.FragmentAIngerer(
            reference=f"{reference}#{ordre:02d}-{_ardoise(section.intitule or 'preambule')}",
            ordre=ordre,
            intitule=section.intitule,
            contenu=section.contenu,
            culture_id=culture_id,
            type=entete.get("type") or None,
            saison=entete.get("saison") or None,
            termes_indexation=section.termes_indexation,
        )
        for ordre, section in enumerate(sections)
    ]
    ecrits, retirees = connaissance.remplacer_fragments(db, document, fragments)
    db.commit()

    # [CA11] Les réponses figées dérivées des fragments disparus tombent — même
    # mécanisme que celui prévu par US-095 / CA10, ni plus ni moins.
    for ancienne in retirees:
        rapport.invalidations += cache_questions.invalider_par_fragment(db, ancienne)

    rapport.fragments += ecrits
    if existant is None:
        rapport.crees += 1
    else:
        rapport.mis_a_jour += 1


def elaguer(db, racine: Path, racine_depot: Path, presents: set[str], rapport: Rapport,
            dry_run: bool = False) -> None:
    """Retire les documents dont le fichier a disparu du dépôt.

    Borné au préfixe de la racine scannée : ingérer un corpus de test ne peut
    donc jamais élaguer le corpus de production, et réciproquement.
    """
    prefixe = reference_document(racine, racine_depot).rstrip("/") + "/"
    orphelins = [
        reference
        for (reference,) in db.query(KnowledgeDocument.reference)
        .filter(KnowledgeDocument.reference.like(f"{prefixe}%"))
        .all()
        if reference not in presents
    ]
    for reference in orphelins:
        rapport.supprimes += 1
        if dry_run:
            continue
        _, retirees = connaissance.supprimer_document(db, reference)
        db.commit()
        for ancienne in retirees:
            rapport.invalidations += cache_questions.invalider_par_fragment(db, ancienne)


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ingère le corpus de connaissance Markdown du dépôt (US-098 / CA10-CA12)."
    )
    parser.add_argument("--racine", default=RACINE_PAR_DEFAUT,
                        help=f"Dossier des documents Markdown (défaut : {RACINE_PAR_DEFAUT})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Rapport seul — aucune écriture en base")
    parser.add_argument("--strict", action="store_true",
                        help="Échoue si un fragment est signalé non autonome (CA12)")
    parser.add_argument("--elaguer", action="store_true",
                        help="Retire aussi les documents dont le fichier a disparu du dépôt")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    racine_depot = Path(__file__).resolve().parent.parent
    racine = Path(args.racine)
    if not racine.is_absolute():
        racine = (racine_depot / racine).resolve()
    if not racine.is_dir():
        print(f"Racine introuvable : {racine}")
        return 2

    fichiers = sorted(racine.rglob("*.md"))
    # Le README documente le format, il n'est pas du contenu.
    fichiers = [f for f in fichiers if f.name.upper() != "README.MD"]
    if not fichiers:
        print(f"Aucun document Markdown sous {racine} — rien à ingérer.")
        return 0

    rapport = Rapport()
    presents: set[str] = set()
    db = SessionLocal()
    try:
        for chemin in fichiers:
            presents.add(reference_document(chemin, racine_depot))
            try:
                ingerer_fichier(db, chemin, racine_depot, rapport, dry_run=args.dry_run)
            except DocumentInvalide as erreur:
                db.rollback()
                rapport.erreurs.append(f"{reference_document(chemin, racine_depot)} : {erreur}")
            except ValueError as erreur:  # vocabulaire d'en-tête refusé
                db.rollback()
                rapport.erreurs.append(f"{reference_document(chemin, racine_depot)} : {erreur}")

        if args.elaguer:
            elaguer(db, racine, racine_depot, presents, rapport, dry_run=args.dry_run)

        volumes = connaissance.compter(db)
    finally:
        db.close()

    entete = "SIMULATION (aucune écriture)" if args.dry_run else "INGESTION"
    print(f"── {entete} · {racine} ──")
    print(f"Documents  : {rapport.crees} créé(s), {rapport.mis_a_jour} mis à jour, "
          f"{rapport.inchanges} inchangé(s), {rapport.supprimes} retiré(s)")
    print(f"Fragments  : {rapport.fragments} écrit(s)")
    print(f"Cache      : {rapport.invalidations} réponse(s) figée(s) invalidée(s) [CA11]")
    print(f"En base    : {volumes['documents']} document(s), {volumes['fragments']} fragment(s)")

    if rapport.avertissements:
        print(f"\n⚠️  {len(rapport.avertissements)} défaut(s) de découpage signalé(s) [CA12] :")
        for ligne in rapport.avertissements:
            print(f"   · {ligne}")

    if rapport.erreurs:
        print(f"\n❌ {len(rapport.erreurs)} document(s) NON ingéré(s) :")
        for ligne in rapport.erreurs:
            print(f"   · {ligne}")
        return 1

    if args.strict and rapport.avertissements:
        print("\n❌ --strict : des fragments ne sont pas autonomes (CA12).")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

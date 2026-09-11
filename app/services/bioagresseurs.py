"""
app/services/bioagresseurs.py — Identités de bioagresseurs et arêtes vers les
cultures [US-162]
------------------------------------------------------------------------------
« Qu'est-ce qui attaque mes poireaux ? » doit se résoudre par une **requête**, à
zéro jeton (CA2, `docs/CONCEPTION_REFERENTIEL_CONNAISSANCE_CULTURES.md` §5.2,
étage 1) — jamais par une recherche de similarité sur du texte. Ce module est le
**seul point d'écriture** des deux tables d'US-162, traversé aussi bien par la
saisie au bot (`bot.cmd_bioagresseur`) que par l'import de manifeste
(`app.services.import_referentiel`) : « aucun second mécanisme », comme le pose
US-140, exactement comme `app.services.associations` pour les arêtes d'US-163.

Ce que ce module NE fait pas — et ne fera pas ici
-------------------------------------------------
- **Aucune prescription (CA10).** Ni dosage, ni produit, ni conduite à tenir. La
  garantie n'est pas une consigne de rédaction : c'est l'absence de colonne où
  les stocker. Ce que l'application peut dire d'un traitement — « légalement
  utilisable en jardin amateur » — se lit dans E-Phy, à la source, et s'y
  renvoie ; il ne se recopie pas ici.
- **Aucun narratif (CA11).** Description, symptômes et biologie relèvent d'US-140
  et s'ingèrent par US-098. Ce module livre les identités et les arêtes
  **auxquelles** ce texte se rattachera — il ne les double pas d'un résumé.

Les trois honnêtetés du module
------------------------------
1. **L'absence de lien n'est pas une absence de risque (CA12).** Une culture sans
   arête connue se lit « je n'ai pas d'information », jamais « rien ne l'attaque ».
   `lire_bioagresseurs` retourne une liste vide, et c'est `MESSAGE_AUCUNE_INFO`
   qui porte la nuance — pas l'appelant, qui la perdrait un jour.
   Symétriquement, un bioagresseur sans aucune arête **reste en base** et se lit
   comme non rattaché (`lister_non_rattaches`) : il n'est ni supprimé, ni promu.
2. **Le local ne devient jamais du partagé (CA3).** `potager_id` NULL = partagé,
   le pattern d'isolation du projet réappliqué tel quel. Une saisie au bot est
   TOUJOURS locale au potager courant : la promotion au partagé est une décision
   humaine, jamais un effet de bord d'une saisie. La lecture, elle, réunit le
   partagé et le local du potager qui interroge — jamais le local d'un autre.
3. **Aucune identité anonyme (CA4).** `source_id` est NOT NULL des deux côtés :
   toute écriture s'attribue une origine du registre d'US-166.

Zéro jeton (CA2, CA13)
----------------------
`lire_bioagresseurs` est une lecture de colonnes déjà en base — aucun import de
client LLM ici, et c'est vérifiable : ce module n'importe ni `llm`, ni
`groq_client`, ni `httpx`. Le tri par fréquence est un ordre métier
(`ORDRE_FREQUENCE`), pas un score.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session
from unidecode import unidecode

from app.services import referentiel_sources as svc_sources
from app.services.attributs_culture import fiches_de_culture
from database.models import Bioagresseur, CultureBioagresseur, CultureConfig, ReferentielSource
from utils.culture_resolve import normaliser_culture

log = logging.getLogger("potager")

# ── [CA1] Vocabulaire fermé des catégories ───────────────────────────────────
#
# Fermé, mais RÉVISABLE en produit — c'est pourquoi `bioagresseur.categorie` ne
# porte aucun `CHECK` en base (migration_v43, même arbitrage que migration_v39
# et v41) : élargir le vocabulaire est une décision applicative d'une ligne, pas
# un `ALTER TYPE`.
#
# ⚠️ Élargi le 06/09/2026, à la première relecture d'un référentiel réel de 68
# identités. `mollusque` et `nematode` n'étaient pas dans les six catégories
# annoncées par le CA1, et leur absence forçait deux classements faux : les
# limaces (`Deroceras reticulatum`) et les nématodes à galles (`Meloidogyne
# incognita`) tombaient en `insecte`, faute de case. Ce n'est pas un détail de
# taxonomie : la limace est le premier ravageur du potager amateur, et un
# jardinier à qui l'application annonce « insecte » cesse de la croire sur le
# reste. Un vocabulaire qui force une erreur est un vocabulaire incomplet, pas
# une contrainte à respecter.
CATEGORIE_CHAMPIGNON = "champignon"
CATEGORIE_INSECTE = "insecte"
CATEGORIE_MOLLUSQUE = "mollusque"
CATEGORIE_NEMATODE = "nematode"
CATEGORIE_BACTERIE = "bacterie"
CATEGORIE_VIRUS = "virus"
CATEGORIE_ABIOTIQUE = "abiotique"
CATEGORIE_CARENCE = "carence"
CATEGORIES: tuple[str, ...] = (
    CATEGORIE_CHAMPIGNON, CATEGORIE_INSECTE, CATEGORIE_MOLLUSQUE,
    CATEGORIE_NEMATODE, CATEGORIE_BACTERIE, CATEGORIE_VIRUS,
    CATEGORIE_ABIOTIQUE, CATEGORIE_CARENCE,
)

# ── [CA2] Vocabulaire fermé des fréquences ───────────────────────────────────
FREQUENCE_COURANT = "courant"
FREQUENCE_OCCASIONNEL = "occasionnel"
FREQUENCE_RARE = "rare"
FREQUENCES: tuple[str, ...] = (FREQUENCE_COURANT, FREQUENCE_OCCASIONNEL, FREQUENCE_RARE)

#: [CA2] L'ordre de restitution est un ordre MÉTIER, pas alphabétique : ce qui
#: arrive souvent se lit en premier. Porté ici, jamais recalculé par l'appelant.
ORDRE_FREQUENCE: dict[str, int] = {nom: rang for rang, nom in enumerate(FREQUENCES)}

#: [CA12] La phrase qui empêche de confondre « je ne sais pas » et « il n'y a
#: rien ». Elle vit ici parce que c'est une règle d'honnêteté du domaine, pas une
#: formulation d'interface : le bot, la PWA et US-165 doivent dire la même chose.
MESSAGE_AUCUNE_INFO = (
    "Aucun bioagresseur connu n'est rattaché à cette culture dans le référentiel. "
    "Cela ne veut pas dire qu'elle n'est pas exposée : cela veut dire que "
    "l'information n'a pas encore été renseignée."
)


class ValeurBioagresseurInvalideError(ValueError):
    """[CA1, CA2] Catégorie, fréquence ou nom hors vocabulaire fermé / vide."""


class BioagresseurInconnuError(LookupError):
    """Le nom donné ne désigne aucun bioagresseur connu du potager courant.

    Jamais créé à la volée depuis un rattachement : même invariant que
    `associations.EntiteInconnueError` — un nom inconnu à ce moment-là est plus
    probablement une faute de frappe qu'une identité réellement nouvelle. Une
    identité se déclare explicitement (`enregistrer_bioagresseur`)."""


class CultureInconnueError(LookupError):
    """[CA7 d'US-161, même invariant] La culture n'existe pas dans
    `culture_config` — l'import comme la saisie enrichissent le référentiel, ils
    ne le peuplent pas de cultures fantômes."""


def normaliser_nom(nom: str) -> str:
    """Casse/accents indifférents — même stratégie que `familles.normaliser_famille`
    et `utils.culture_resolve.normaliser_culture`."""
    return unidecode((nom or "").strip().lower())


@dataclass(frozen=True)
class BioagresseurLu:
    """Ce qu'une culture restitue — déjà ordonné, déjà attribué (CA2, CA4)."""

    nom_commun_fr: str
    nom_scientifique: Optional[str]
    categorie: str
    code_eppo: Optional[str]
    frequence: str
    periode_risque: Optional[str]
    #: [CA3] True = arête propre au potager qui interroge, jamais partagée.
    local: bool
    source_code: Optional[str]
    attribution: Optional[str]


def _valider_identite(nom_commun_fr: str, categorie: str) -> tuple[str, str]:
    """[CA1] Valide avant toute résolution comme toute écriture — une valeur
    refusée ne doit toucher à rien (même garde que `associations._valider`)."""
    nom = (nom_commun_fr or "").strip()
    if not nom:
        raise ValeurBioagresseurInvalideError(
            "Le nom commun français est obligatoire : une identité sans nom n'est "
            "pas une identité."
        )
    categorie_propre = (categorie or "").strip().lower()
    if categorie_propre not in CATEGORIES:
        raise ValeurBioagresseurInvalideError(
            f"« {categorie} » n'est pas une catégorie admise. "
            f"Valeurs possibles : {', '.join(CATEGORIES)}."
        )
    return nom, categorie_propre


def _valider_frequence(frequence: str) -> str:
    """[CA2] Vocabulaire fermé de la fréquence."""
    valeur = (frequence or "").strip().lower()
    if valeur not in FREQUENCES:
        raise ValeurBioagresseurInvalideError(
            f"« {frequence} » n'est pas une fréquence admise. "
            f"Valeurs possibles : {', '.join(FREQUENCES)}."
        )
    return valeur


def _visible_par(potager_id: Optional[int]):
    """[CA3] Filtre de visibilité : le partagé, plus le local du potager qui
    interroge — jamais le local d'un autre. `potager_id=None` ne voit que le
    partagé, ce qui est exactement ce que doit voir un import ou un rapport."""
    if potager_id is None:
        return Bioagresseur.potager_id.is_(None)
    return or_(Bioagresseur.potager_id.is_(None), Bioagresseur.potager_id == potager_id)


def get_bioagresseur(
    db: Session, nom: str, potager_id: Optional[int] = None
) -> Optional[Bioagresseur]:
    """
    Résout un nom (ou un code EPPO) vers l'identité visible par ce potager.

    [CA1] Le code EPPO prime sur le nom quand il correspond : c'est la seule clé
    fiable entre sources, un nom commun ne l'est pas. [CA3] Une identité locale
    au potager courant prime sur l'identité partagée de même nom — le jardinier
    a délibérément déclaré la sienne.
    """
    cible = (nom or "").strip()
    if not cible:
        return None

    candidats = (
        db.query(Bioagresseur)
        .filter(_visible_par(potager_id))
        .filter(
            or_(
                Bioagresseur.nom_normalise == normaliser_nom(cible),
                Bioagresseur.code_eppo == cible.upper(),
            )
        )
        .all()
    )
    if not candidats:
        return None
    # Le local d'abord, le partagé ensuite (CA3).
    return next((c for c in candidats if c.potager_id is not None), candidats[0])


def enregistrer_bioagresseur(
    db: Session,
    nom_commun_fr: str,
    categorie: str,
    nom_scientifique: Optional[str] = None,
    code_eppo: Optional[str] = None,
    potager_id: Optional[int] = None,
    source_code: str = svc_sources.SOURCE_SAISIE_MANUELLE,
) -> tuple[Bioagresseur, bool]:
    """
    [CA1, CA3, CA4] Déclare ou corrige une identité de bioagresseur.

    Retourne `(bioagresseur, créé)`.

    Appelée depuis le bot avec le `potager_id` du jardinier : la fiche est alors
    **locale**, et le reste (CA3). Rien ici ne promeut une fiche locale au
    partagé — c'est une décision humaine, hors du chemin de saisie.

    Idempotent côté saisie : une fiche déjà déclarée pour ce nom, dans ce même
    périmètre (local ou partagé), est corrigée plutôt que dupliquée.
    """
    nom, categorie_propre = _valider_identite(nom_commun_fr, categorie)
    code = (code_eppo or "").strip().upper() or None

    existante = (
        db.query(Bioagresseur)
        .filter(
            Bioagresseur.nom_normalise == normaliser_nom(nom),
            Bioagresseur.potager_id.is_(None) if potager_id is None
            else Bioagresseur.potager_id == potager_id,
        )
        .first()
    )
    origine = svc_sources.garantir_source(db, source_code)

    if existante is not None:
        existante.nom_commun_fr = nom
        existante.categorie = categorie_propre
        if nom_scientifique is not None:
            existante.nom_scientifique = nom_scientifique.strip() or None
        if code is not None:
            existante.code_eppo = code
        existante.source_id = origine.id
        db.commit()
        log.info("[US-162] bioagresseur « %s » corrigé (potager=%s)", nom, potager_id)
        return existante, False

    bioagresseur = Bioagresseur(
        code_eppo=code,
        nom_commun_fr=nom,
        nom_normalise=normaliser_nom(nom),
        nom_scientifique=(nom_scientifique or "").strip() or None,
        categorie=categorie_propre,
        potager_id=potager_id,
        source_id=origine.id,
    )
    db.add(bioagresseur)
    db.commit()
    log.info("[US-162] bioagresseur « %s » déclaré (potager=%s)", nom, potager_id)
    return bioagresseur, True


def _fiche_culture(db: Session, culture: str, potager_id: Optional[int]):
    """Résout une culture vers LA fiche `culture_config` à rattacher.

    Préfère la fiche globale (`potager_id` NULL) quand plusieurs fiches
    homonymes existent : la sensibilité d'une culture à un bioagresseur est un
    fait agronomique, pas une préférence de jardinier — même arbitrage que
    `associations._resoudre_cote`. Lève `CultureInconnueError` si aucune fiche
    ne porte ce nom : aucune culture n'est créée ici, jamais (CA7 d'US-161).
    """
    fiches = fiches_de_culture(db, culture)
    if not fiches:
        raise CultureInconnueError(culture)
    return next((f for f in fiches if f.potager_id is None), fiches[0])


def _trouver_arete(
    db: Session, culture_id: int, bioagresseur_id: int, potager_id: Optional[int]
) -> Optional[CultureBioagresseur]:
    """[CA5] Une même arête, dans un même périmètre, est une ligne à corriger —
    jamais une seconde ligne concurrente. C'est ce qui rend le rejeu hebdomadaire
    du manifeste E-Phy banal plutôt que dédoublonnant."""
    return (
        db.query(CultureBioagresseur)
        .filter(
            CultureBioagresseur.culture_id == culture_id,
            CultureBioagresseur.bioagresseur_id == bioagresseur_id,
            CultureBioagresseur.potager_id.is_(None) if potager_id is None
            else CultureBioagresseur.potager_id == potager_id,
        )
        .first()
    )


def rattacher(
    db: Session,
    culture: str,
    bioagresseur: str,
    frequence: str,
    periode_risque: Optional[str] = None,
    potager_id: Optional[int] = None,
    source_code: str = svc_sources.SOURCE_SAISIE_MANUELLE,
) -> tuple[CultureBioagresseur, bool]:
    """
    [CA2, CA3, CA4] Pose ou corrige l'arête culture × bioagresseur depuis le bot.

    Retourne `(arête, créée)`. Lève `ValeurBioagresseurInvalideError` (fréquence
    hors vocabulaire), `CultureInconnueError` ou `BioagresseurInconnuError` — le
    bioagresseur doit avoir été déclaré au préalable, il n'est jamais fabriqué
    par un rattachement.
    """
    frequence_propre = _valider_frequence(frequence)
    fiche = _fiche_culture(db, culture, potager_id)

    identite = get_bioagresseur(db, bioagresseur, potager_id=potager_id)
    if identite is None:
        raise BioagresseurInconnuError(bioagresseur)

    origine = svc_sources.garantir_source(db, source_code)
    periode = (periode_risque or "").strip() or None

    existante = _trouver_arete(db, fiche.id, identite.id, potager_id)
    if existante is not None:
        existante.frequence = frequence_propre
        if periode is not None:
            existante.periode_risque = periode
        existante.source_id = origine.id
        db.commit()
        return existante, False

    arete = CultureBioagresseur(
        culture_id=fiche.id,
        bioagresseur_id=identite.id,
        frequence=frequence_propre,
        periode_risque=periode,
        potager_id=potager_id,
        source_id=origine.id,
    )
    db.add(arete)
    db.commit()
    log.info(
        "[US-162] « %s » rattaché à « %s » (%s, potager=%s)",
        identite.nom_commun_fr, fiche.nom, frequence_propre, potager_id,
    )
    return arete, True


# ── Import : mêmes issues que `associations.importer_association` ────────────
IMPORT_CREEE = "creee"
IMPORT_ECRITE = "ecrite"
IMPORT_PRESERVEE = "preservee"
IMPORT_INCHANGEE = "inchangee"


def importer_bioagresseur(
    db: Session,
    nom_commun_fr: str,
    categorie: str,
    source: ReferentielSource,
    nom_scientifique: Optional[str] = None,
    code_eppo: Optional[str] = None,
) -> str:
    """
    [CA5, CA6] Écrit une identité **partagée** depuis un manifeste importé.

    Ne commite pas : l'appelant (`import_referentiel.importer`) contrôle la
    transaction pour pouvoir simuler tout un manifeste d'un coup (`dry_run`).

    Un import ne pose JAMAIS de fiche locale à un potager (CA3) : il alimente la
    connaissance partagée, par définition. Le rapprochement se fait d'abord par
    code EPPO — la seule clé fiable (CA1) — puis par nom normalisé.

    Retourne `IMPORT_CREEE`, `IMPORT_ECRITE`, `IMPORT_INCHANGEE` ou
    `IMPORT_PRESERVEE` (la ligne porte une autre origine : la saisie du
    jardinier n'est jamais écrasée par un rejeu — même invariant que
    `import_referentiel._peut_ecrire`, appliqué à la ligne entière).
    """
    nom, categorie_propre = _valider_identite(nom_commun_fr, categorie)
    code = (code_eppo or "").strip().upper() or None
    scientifique = (nom_scientifique or "").strip() or None

    existante = None
    if code:
        existante = (
            db.query(Bioagresseur)
            .filter(Bioagresseur.code_eppo == code, Bioagresseur.potager_id.is_(None))
            .first()
        )
    if existante is None:
        existante = (
            db.query(Bioagresseur)
            .filter(
                Bioagresseur.nom_normalise == normaliser_nom(nom),
                Bioagresseur.potager_id.is_(None),
            )
            .first()
        )

    if existante is None:
        db.add(Bioagresseur(
            code_eppo=code,
            nom_commun_fr=nom,
            nom_normalise=normaliser_nom(nom),
            nom_scientifique=scientifique,
            categorie=categorie_propre,
            potager_id=None,
            source_id=source.id,
        ))
        return IMPORT_CREEE

    if existante.source_id is not None and existante.source_id != source.id:
        return IMPORT_PRESERVEE

    avant = (existante.nom_commun_fr, existante.categorie,
             existante.nom_scientifique, existante.code_eppo)
    existante.nom_commun_fr = nom
    existante.nom_normalise = normaliser_nom(nom)
    existante.categorie = categorie_propre
    if scientifique is not None:
        existante.nom_scientifique = scientifique
    if code is not None:
        existante.code_eppo = code
    existante.source_id = source.id
    apres = (existante.nom_commun_fr, existante.categorie,
             existante.nom_scientifique, existante.code_eppo)
    return IMPORT_INCHANGEE if avant == apres else IMPORT_ECRITE


def importer_rattachement(
    db: Session,
    culture: str,
    bioagresseur: str,
    frequence: str,
    source: ReferentielSource,
    periode_risque: Optional[str] = None,
) -> str:
    """
    [CA2, CA5] Écrit une arête **partagée** depuis un manifeste importé.

    Ne commite pas (même raison que `importer_bioagresseur`). Ni la culture ni
    le bioagresseur ne sont créés à la volée : un côté absent lève
    `CultureInconnueError` / `BioagresseurInconnuError`, et l'appelant le compte
    ignoré. La règle de non-écrasement porte sur la LIGNE : une arête saisie par
    le jardinier survit à tout rejeu.
    """
    frequence_propre = _valider_frequence(frequence)
    fiche = _fiche_culture(db, culture, None)

    identite = get_bioagresseur(db, bioagresseur, potager_id=None)
    if identite is None:
        raise BioagresseurInconnuError(bioagresseur)

    periode = (periode_risque or "").strip() or None
    existante = _trouver_arete(db, fiche.id, identite.id, None)

    if existante is None:
        db.add(CultureBioagresseur(
            culture_id=fiche.id,
            bioagresseur_id=identite.id,
            frequence=frequence_propre,
            periode_risque=periode,
            potager_id=None,
            source_id=source.id,
        ))
        return IMPORT_CREEE

    if existante.source_id is not None and existante.source_id != source.id:
        return IMPORT_PRESERVEE

    inchangee = (existante.frequence, existante.periode_risque) == (frequence_propre, periode)
    existante.frequence = frequence_propre
    existante.periode_risque = periode
    existante.source_id = source.id
    return IMPORT_INCHANGEE if inchangee else IMPORT_ECRITE


def fiches_visibles(db: Session, culture: str, potager_id: Optional[int]):
    """
    [CA3] Fiches `culture_config` portant ce nom et visibles par ce potager.

    Publique depuis US-165 : le pré-diagnostic doit résoudre une culture
    exactement comme la lecture des bioagresseurs le fait, garde de
    `catalogue_sql` comprise. Une seconde résolution répondrait « je n'ai pas de
    fiche pour cette culture » là où `/bioagresseur lister` en trouve une, ou
    l'inverse — et le jardinier n'aurait aucun moyen de comprendre pourquoi.

    Se distingue de `attributs_culture.fiches_de_culture`, qui balaie TOUTES les
    fiches sans distinction de potager, sur deux points qui comptent tous les
    deux ici :

    1. **L'isolation est appliquée** — une fiche personnalisée par un autre
       potager ne doit pas résoudre la culture de celui qui interroge.
    2. **Le filtre est posé en SQL, pas en Python.** Ce n'est pas un détail de
       performance : `catalogue_sql.garde_lecture_seule` (US-096 / CA11) refuse
       à l'exécution toute lecture de `culture_config` dont l'instruction ne
       porte pas de filtre `potager_id`. Sans cette clause, la réponse en
       langage naturel d'US-173 est rejetée par la garde — à raison.
    """
    portee = (
        CultureConfig.potager_id.is_(None) if potager_id is None
        else or_(CultureConfig.potager_id.is_(None), CultureConfig.potager_id == potager_id)
    )
    cible = normaliser_culture(culture)
    return [
        fiche for fiche in db.query(CultureConfig).filter(portee).all()
        if normaliser_culture(fiche.nom) == cible
    ]


def lire_bioagresseurs(
    db: Session, culture: str, potager_id: Optional[int] = None
) -> list[BioagresseurLu]:
    """
    [CA2, CA3, CA12, CA13] Ce qui attaque une culture — **à zéro jeton**.

    Une jointure, un tri métier, rien d'autre : ni appel à un modèle de langage,
    ni recherche de similarité. C'est l'étage 1 de la cascade
    (`docs/CONCEPTION_REFERENTIEL_CONNAISSANCE_CULTURES.md` §5.2).

    Restitue le partagé PLUS le local du potager qui interroge, jamais le local
    d'un autre (CA3). Ordonné par fréquence décroissante d'occurrence
    (`courant` d'abord), puis par nom — un ordre stable, testable.

    Retourne une liste **vide** si la culture n'a aucune arête connue : le
    silence est honnête, et c'est `MESSAGE_AUCUNE_INFO` qui le formule (CA12).
    Lève `CultureInconnueError` si la culture elle-même est inconnue — ne rien
    savoir d'une culture connue et ne pas connaître la culture sont deux
    situations différentes, et les confondre trompe le jardinier.
    """
    fiches = fiches_visibles(db, culture, potager_id)
    if not fiches:
        raise CultureInconnueError(culture)
    ids_fiches = [f.id for f in fiches]

    portee_arete = (
        CultureBioagresseur.potager_id.is_(None) if potager_id is None
        else or_(
            CultureBioagresseur.potager_id.is_(None),
            CultureBioagresseur.potager_id == potager_id,
        )
    )
    lignes = (
        db.query(CultureBioagresseur, Bioagresseur)
        .join(Bioagresseur, CultureBioagresseur.bioagresseur_id == Bioagresseur.id)
        .filter(CultureBioagresseur.culture_id.in_(ids_fiches))
        .filter(portee_arete)
        .filter(_visible_par(potager_id))
        .all()
    )

    resultats: list[BioagresseurLu] = []
    for arete, identite in lignes:
        source = db.get(ReferentielSource, arete.source_id)
        resultats.append(BioagresseurLu(
            nom_commun_fr=identite.nom_commun_fr,
            nom_scientifique=identite.nom_scientifique,
            categorie=identite.categorie,
            code_eppo=identite.code_eppo,
            frequence=arete.frequence,
            periode_risque=arete.periode_risque,
            local=arete.potager_id is not None or identite.potager_id is not None,
            source_code=source.code if source is not None else None,
            # [CA4, CA7] Passe par le registre plutôt que par `source.attribution`
            # brut : c'est lui qui recompose la date de dernier téléchargement
            # qu'exige la licence EPPO.
            attribution=(
                svc_sources.attribution_affichee(db, source.code)
                if source is not None else None
            ),
        ))
    resultats.sort(
        key=lambda b: (ORDRE_FREQUENCE.get(b.frequence, len(FREQUENCES)), b.nom_commun_fr)
    )
    return resultats


def lister_non_rattaches(
    db: Session, potager_id: Optional[int] = None
) -> list[Bioagresseur]:
    """
    [CA12] Les bioagresseurs qui ne sont rattachés à AUCUNE culture.

    Ils restent en base et se lisent comme non rattachés — ils ne sont ni
    supprimés (une identité importée reste une identité valide), ni comptés
    comme couverture. C'est aussi la liste de travail de la revue humaine : ce
    qui est entré sans qu'on sache encore à quoi le relier.
    """
    rattachees = {
        ligne[0]
        for ligne in db.query(CultureBioagresseur.bioagresseur_id).distinct().all()
    }
    return [
        b
        for b in db.query(Bioagresseur).filter(_visible_par(potager_id))
        .order_by(Bioagresseur.nom_commun_fr).all()
        if b.id not in rattachees
    ]

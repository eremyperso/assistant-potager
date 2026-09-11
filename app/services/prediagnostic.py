"""
app/services/prediagnostic.py — Pré-diagnostic déterministe [US-165]
================================================================================
« Mes pieds de tomates ont des taches marron sur les feuilles du bas qui
remontent » recevait jusqu'ici un silence, ou une généralité. Ce module ferme la
boucle que l'application détenait déjà aux deux extrémités :

    observation (action existante) → PRÉ-DIAGNOSTIC (ici) → traitement (action
    existante) → suivi (événements existants)

Deux mots décrivent tout le mécanisme, et aucun n'est « modèle » :

    recherche plein texte sur les symptômes et leurs SYNONYMES  (CA1, CA9)
    puis jointure avec les bioagresseurs connus pour CETTE culture  (CA3)

Ce que ce module NE fait pas — et ne fera pas ici
-------------------------------------------------
- **Aucun appel modèle (CA9).** Ce fichier n'importe ni `llm`, ni `groq_client`,
  ni `httpx`, et c'est vérifiable par un test. Le modèle n'intervient qu'à
  l'étage supérieur, pour le diagnostic multi-facteurs d'US-142.
- **Aucune prescription (CA7).** Ni dosage, ni produit, ni conduite à tenir. La
  garantie n'est pas une consigne de rédaction : `symptome` et
  `symptome_bioagresseur` n'ont aucune colonne où les stocker (migration_v45),
  exactement comme les tables d'US-162.
- **Aucun diagnostic.** Une piste n'est pas une cause : `FORMULE_EVOCATION` est
  la seule tournure que ce module produise, et `_rendu_prediagnostic` (US-096)
  la seule à l'assembler.

Les quatre honnêtetés — le risque 🔴 le plus élevé de l'épic
------------------------------------------------------------
Un jardinier qui traite au cuivre sur une suspicion fausse a perdu plus que si
l'application s'était tue. D'où quatre garde-fous, chacun structurel :

1. **« Cela peut évoquer », jamais « c'est » (CA4).** La formulation est imposée
   et non négociable. Elle vit dans `FORMULE_EVOCATION`, à un seul endroit, et
   `tests/test_us165_prediagnostic.py` refuse toute tournure affirmative dans les
   textes produits.
2. **Deux à trois pistes, jamais une seule qui se lise comme une conclusion
   (CA5).** Quand le croisement n'en produit qu'une, l'application le DIT
   (`ISSUE_PISTE_UNIQUE`) au lieu d'en inventer une seconde : une piste fabriquée
   pour tenir un compte serait pire que le déséquilibre qu'elle corrige.
3. **Un symptôme non reconnu produit un refus, pas un rapprochement approximatif
   (CA8).** `PREDIAGNOSTIC_SEUIL_SYMPTOME` est le réglage de cette honnêteté, et
   25 des 44 entrées du corpus de mesure ne servent qu'à la contrôler (CA12).
4. **La réserve suit le contenu non relu (CA6).** `niveau_confiance` reprend le
   vocabulaire d'US-098, et la réserve servie est `connaissance.RESERVE_INDICATIF`
   — la même phrase, jamais une variante.

Deux moteurs, une seule sémantique
----------------------------------
La recherche est celle d'US-098, réutilisée telle quelle
(`connaissance.valeur_recherche_fts`, `connaissance.tsquery`) : PostgreSQL en
dictionnaire `french_sans_accent` en production, repli par couverture de termes
en SQLite pour les tests. Il n'y a pas de second moteur ici, et c'est délibéré —
deux implémentations de la même recherche divergeraient du côté où on ne les
regarde pas. La mesure qui décide de l'avenir du vectoriel (CA13) doit être
rejouée sur PostgreSQL : `python tools/mesurer_prediagnostic.py`.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session
from unidecode import unidecode

from app.services import bioagresseurs as svc_bioagresseurs
from app.services import connaissance
from app.services import referentiel_sources as svc_sources
from config import PREDIAGNOSTIC_MAX_PISTES, PREDIAGNOSTIC_SEUIL_SYMPTOME
from database.models import (
    Bioagresseur,
    CultureBioagresseur,
    ReferentielSource,
    Symptome,
    SymptomeBioagresseur,
)

log = logging.getLogger("potager")

# ── [CA1] Vocabulaire fermé des organes atteints ─────────────────────────────
#
# Fermé mais RÉVISABLE en produit : aucun CHECK en base (migration_v45), même
# arbitrage que `bioagresseurs.CATEGORIES` — élargir est une décision applicative
# d'une ligne, pas un `ALTER TYPE`. Les cinq premières valeurs sont celles que le
# CA1 nomme ; `fleur`, `graine` et `bulbe` s'y ajoutent parce que les refuser
# forçait un classement faux — même motif que l'ajout de `mollusque` et
# `nematode` à US-162, et constaté de la même façon, en rédigeant le référentiel :
# des fleurs qui coulent ne sont pas un fruit, un caïeu d'ail pourri n'est ni une
# racine ni un plant entier, et une graine qui n'a pas levé n'est encore aucun
# organe de la plante. Un vocabulaire qui force une erreur est un vocabulaire
# incomplet, pas une contrainte à respecter.
ORGANE_FEUILLE = "feuille"
ORGANE_FRUIT = "fruit"
ORGANE_TIGE = "tige"
ORGANE_RACINE = "racine"
ORGANE_PLANT_ENTIER = "plant entier"
ORGANE_FLEUR = "fleur"
ORGANE_GRAINE = "graine"
ORGANE_BULBE = "bulbe"
ORGANES: tuple[str, ...] = (
    ORGANE_FEUILLE, ORGANE_FRUIT, ORGANE_TIGE, ORGANE_RACINE,
    ORGANE_PLANT_ENTIER, ORGANE_FLEUR, ORGANE_GRAINE, ORGANE_BULBE,
)

# ── [CA6] Niveaux de confiance — ceux d'US-098, jamais un second vocabulaire ──
NIVEAU_VERIFIE = connaissance.NIVEAU_VERIFIE
NIVEAU_INDICATIF = connaissance.NIVEAU_INDICATIF
NIVEAUX_CONFIANCE = connaissance.NIVEAUX_CONFIANCE

# ── [CA2] Bornes du poids ────────────────────────────────────────────────────
#: Plausibilité relative. Elle ORDONNE et ne se montre jamais : `Piste` ne porte
#: aucun champ de poids, et c'est cette absence — pas une consigne — qui empêche
#: qu'un pourcentage soit un jour affiché au jardinier.
POIDS_MIN = 0.0
POIDS_MAX = 1.0

# ── [CA4] LA formulation, imposée et non négociable ──────────────────────────
#
# Écrite ici et à cet endroit seul. Le risque le plus élevé de tout l'épic est
# qu'un pré-diagnostic soit pris pour un diagnostic ; la prudence ne peut donc
# pas être une intention de rédaction répartie sur plusieurs gabarits, où elle
# s'éroderait à la première reformulation.
FORMULE_EVOCATION = "cela peut évoquer"

#: [CA5] Ce qui accompagne une piste unique. La phrase ne s'excuse pas d'un
#: manque : elle dit ce que le référentiel sait et ce qu'il ne sait pas, pour que
#: l'unique piste ne se lise pas comme une conclusion.
MESSAGE_PISTE_UNIQUE = (
    "Je n'ai qu'une seule piste à te proposer pour cette description : "
    "ne la lis pas comme une conclusion, d'autres causes existent que le "
    "référentiel ne connaît pas encore."
)

#: [CA8] Le refus honnête. Il ne propose AUCUN rapprochement approximatif — un
#: symptôme voisin servi faute de mieux est exactement ce que ce message
#: remplace.
MESSAGE_SYMPTOME_INCONNU = (
    "Je ne reconnais pas ce symptôme dans mon référentiel, et je préfère te le "
    "dire plutôt que de te proposer une piste au hasard. Décris-le autrement si "
    "tu veux réessayer — ce que tu vois, sur quel organe, depuis quand."
)

#: [CA3, scénario « Culture hors périmètre »] Trois situations, trois messages :
#: ne pas connaître la culture, ne rien savoir de ses bioagresseurs, et ne pas
#: reconnaître le symptôme sont des ignorances différentes, et les confondre
#: trompe le jardinier.
MESSAGE_CULTURE_SANS_FICHE = (
    "Je n'ai pas de fiche de référentiel pour {culture}, donc aucune piste à "
    "proposer sur ce qu'elle montre. Ce n'est pas un constat d'absence de risque."
)

MESSAGE_AUCUN_CROISEMENT = (
    "Je reconnais ce symptôme, mais aucun des bioagresseurs qu'il peut évoquer "
    "n'est rattaché à {culture} dans mon référentiel. L'information n'a pas "
    "encore été renseignée — ce n'est pas une absence de risque."
)

# ── Issues d'un pré-diagnostic — le journal doit pouvoir les distinguer ──────
ISSUE_PISTES = "pistes"                      # 2 ou 3 pistes ordonnées (CA5)
ISSUE_PISTE_UNIQUE = "piste_unique"          # une seule, dite comme telle (CA5)
ISSUE_SYMPTOME_INCONNU = "symptome_inconnu"  # refus honnête (CA8)
ISSUE_CULTURE_SANS_FICHE = "culture_sans_fiche"
ISSUE_AUCUN_CROISEMENT = "aucun_croisement"  # symptôme connu, culture sans arête


class ValeurSymptomeInvalideError(ValueError):
    """[CA1, CA2] Libellé vide, organe hors vocabulaire, ou poids hors bornes."""


class SymptomeInconnuError(LookupError):
    """Le libellé donné ne désigne aucun symptôme connu du potager courant.

    Jamais créé à la volée depuis un rattachement — même invariant que
    `bioagresseurs.BioagresseurInconnuError` : un libellé inconnu à ce moment-là
    est plus probablement une faute de frappe qu'un symptôme réellement nouveau.
    """


def normaliser_libelle(libelle: str) -> str:
    """Casse/accents indifférents — même stratégie que
    `bioagresseurs.normaliser_nom` et `familles.normaliser_famille`."""
    return unidecode((libelle or "").strip().lower())


@dataclass(frozen=True)
class Piste:
    """[CA2, CA4, CA6] Une hypothèse — jamais une cause.

    ⚠️ Aucun champ de poids, et c'est le point : le CA2 interdit qu'une
    plausibilité relative soit montrée comme un pourcentage, et la façon la plus
    sûre de tenir cet interdit est de ne pas la faire sortir du service. Ce que
    l'appelant reçoit est un ORDRE, pas un nombre.
    """

    bioagresseur: str
    categorie: str
    #: Fréquence de l'arête culture × bioagresseur (US-162) — « courant » se lit
    #: comme un renfort de plausibilité, et c'est une information du référentiel,
    #: pas un calcul.
    frequence: str
    #: Le symptôme du référentiel qui a mené à cette piste : c'est lui que le
    #: jardinier doit pouvoir reconnaître ou rejeter.
    symptome: str
    niveau_confiance: str
    source_code: Optional[str]
    attribution: Optional[str]


@dataclass(frozen=True)
class Prediagnostic:
    """Ce que le service rend — des pistes, une issue, une réserve. Jamais un
    texte rédigé : la mise en phrase appartient au gabarit d'US-096, et aucune
    autre tournure que `FORMULE_EVOCATION` n'existe pour la produire."""

    issue: str
    culture: str
    #: Libellé du symptôme reconnu, ou `None` si aucun ne l'a été (CA8).
    symptome: Optional[str] = None
    pistes: tuple[Piste, ...] = ()
    #: [CA6] Réserve à joindre, ou chaîne vide. C'est
    #: `connaissance.RESERVE_INDICATIF`, mot pour mot.
    reserve: str = ""
    #: Score de reconnaissance du symptôme, dans [0, 1]. Diagnostic interne :
    #: sert à la mesure du CA11 et au réétalonnage du seuil, jamais à l'affichage.
    score: float = 0.0

    @property
    def sources(self) -> tuple[str, ...]:
        """[CA6] Attributions à citer, dédoublonnées, dans l'ordre des pistes."""
        vues: list[str] = []
        for piste in self.pistes:
            if piste.attribution and piste.attribution not in vues:
                vues.append(piste.attribution)
        return tuple(vues)


# ═════════════════════════════════════════════════════════════════════════════
# Écriture — validation d'abord, résolution ensuite
# ═════════════════════════════════════════════════════════════════════════════
def _valider_symptome(libelle: str, organe: str) -> tuple[str, str]:
    """[CA1] Valide avant toute résolution comme toute écriture — une valeur
    refusée ne doit toucher à rien (même garde que `bioagresseurs._valider_identite`)."""
    propre = (libelle or "").strip()
    if not propre:
        raise ValeurSymptomeInvalideError(
            "Le libellé du symptôme est obligatoire : un symptôme sans libellé "
            "n'est pas un symptôme."
        )
    organe_propre = (organe or "").strip().lower()
    if organe_propre not in ORGANES:
        raise ValeurSymptomeInvalideError(
            f"« {organe} » n'est pas un organe admis. "
            f"Valeurs possibles : {', '.join(ORGANES)}."
        )
    return propre, organe_propre


def _valider_poids(poids: float) -> float:
    """[CA2] Plausibilité relative dans ]0, 1]. Un poids nul dirait « cette piste
    n'en est pas une » : ce n'est pas un poids, c'est une arête à ne pas écrire."""
    try:
        valeur = float(poids)
    except (TypeError, ValueError):
        raise ValeurSymptomeInvalideError(f"« {poids} » n'est pas un poids numérique.")
    if not (POIDS_MIN < valeur <= POIDS_MAX):
        raise ValeurSymptomeInvalideError(
            f"Le poids doit être dans ]{POIDS_MIN}, {POIDS_MAX}] — reçu {valeur}."
        )
    return valeur


def _valider_niveau(niveau: str) -> str:
    """[CA6] Le vocabulaire d'US-098, et rien d'autre."""
    valeur = (niveau or "").strip().lower()
    if valeur not in NIVEAUX_CONFIANCE:
        raise ValeurSymptomeInvalideError(
            f"« {niveau} » n'est pas un niveau de confiance admis. "
            f"Valeurs possibles : {', '.join(sorted(NIVEAUX_CONFIANCE))}."
        )
    return valeur


def _visible_par(potager_id: Optional[int]):
    """[CA3 d'US-162] Le partagé, plus le local du potager qui interroge — jamais
    le local d'un autre."""
    if potager_id is None:
        return Symptome.potager_id.is_(None)
    return or_(Symptome.potager_id.is_(None), Symptome.potager_id == potager_id)


def get_symptome(
    db: Session, libelle: str, potager_id: Optional[int] = None
) -> Optional[Symptome]:
    """Résout un libellé vers le symptôme visible par ce potager.

    Un symptôme local au potager courant prime sur le symptôme partagé de même
    libellé — le jardinier a délibérément décrit le sien.
    """
    cible = normaliser_libelle(libelle)
    if not cible:
        return None
    candidats = (
        db.query(Symptome)
        .filter(_visible_par(potager_id))
        .filter(Symptome.libelle_normalise == cible)
        .all()
    )
    if not candidats:
        return None
    return next((c for c in candidats if c.potager_id is not None), candidats[0])


def _vecteur(db: Session, libelle: str, synonymes: Optional[str]):
    """[CA1, CA9] Le vecteur de recherche d'un symptôme.

    Le libellé ET les synonymes pèsent comme un TITRE — ce sont deux façons de
    nommer la même chose, et un jardinier n'emploie presque jamais celle du
    libellé. La fonction est celle d'US-098, appelée avec un `contenu` vide : un
    symptôme n'a pas de corps de texte, il n'est QUE ses désignations.
    """
    return connaissance.valeur_recherche_fts(
        db, libelle, None, "", termes_indexation=(synonymes or ""),
    )


def enregistrer_symptome(
    db: Session,
    libelle: str,
    organe: str,
    synonymes: Optional[str] = None,
    potager_id: Optional[int] = None,
    source_code: str = svc_sources.SOURCE_SAISIE_MANUELLE,
) -> tuple[Symptome, bool]:
    """
    [CA1] Décrit ou corrige un symptôme. Retourne `(symptôme, créé)`.

    Idempotent dans son périmètre : un symptôme déjà décrit sous ce libellé, au
    même niveau (local ou partagé), est corrigé plutôt que dupliqué. Un ajout
    local n'est JAMAIS promu au partagé — décision humaine, pas effet de bord.
    """
    propre, organe_propre = _valider_symptome(libelle, organe)
    origine = svc_sources.garantir_source(db, source_code)
    liste = (synonymes or "").strip() or None

    existant = (
        db.query(Symptome)
        .filter(
            Symptome.libelle_normalise == normaliser_libelle(propre),
            Symptome.potager_id.is_(None) if potager_id is None
            else Symptome.potager_id == potager_id,
        )
        .first()
    )
    if existant is not None:
        existant.libelle = propre
        existant.organe = organe_propre
        if liste is not None:
            existant.synonymes = liste
        existant.recherche_fts = _vecteur(db, propre, existant.synonymes)
        existant.source_id = origine.id
        db.commit()
        return existant, False

    symptome = Symptome(
        libelle=propre,
        libelle_normalise=normaliser_libelle(propre),
        organe=organe_propre,
        synonymes=liste,
        recherche_fts=_vecteur(db, propre, liste),
        potager_id=potager_id,
        source_id=origine.id,
    )
    db.add(symptome)
    db.commit()
    log.info("[US-165] symptôme « %s » décrit (potager=%s)", propre, potager_id)
    return symptome, True


def _trouver_arete(
    db: Session, symptome_id: int, bioagresseur_id: int, potager_id: Optional[int]
) -> Optional[SymptomeBioagresseur]:
    """[CA2] Une même arête, dans un même périmètre, est une ligne à corriger —
    jamais une seconde ligne concurrente."""
    return (
        db.query(SymptomeBioagresseur)
        .filter(
            SymptomeBioagresseur.symptome_id == symptome_id,
            SymptomeBioagresseur.bioagresseur_id == bioagresseur_id,
            SymptomeBioagresseur.potager_id.is_(None) if potager_id is None
            else SymptomeBioagresseur.potager_id == potager_id,
        )
        .first()
    )


def rattacher(
    db: Session,
    symptome: str,
    bioagresseur: str,
    poids: float,
    niveau_confiance: str = NIVEAU_INDICATIF,
    potager_id: Optional[int] = None,
    source_code: str = svc_sources.SOURCE_SAISIE_MANUELLE,
) -> tuple[SymptomeBioagresseur, bool]:
    """
    [CA2, CA6] Pose ou corrige l'arête pondérée symptôme × bioagresseur.

    Ni le symptôme ni le bioagresseur ne sont fabriqués ici : un côté absent lève
    `SymptomeInconnuError` ou `bioagresseurs.BioagresseurInconnuError`. Le défaut
    de `niveau_confiance` est `indicatif` et non `verifie` — rien n'est vérifié
    tant qu'un jardinier ne l'a pas constaté au champ.
    """
    valeur = _valider_poids(poids)
    niveau = _valider_niveau(niveau_confiance)

    cible = get_symptome(db, symptome, potager_id=potager_id)
    if cible is None:
        raise SymptomeInconnuError(symptome)

    identite = svc_bioagresseurs.get_bioagresseur(db, bioagresseur, potager_id=potager_id)
    if identite is None:
        raise svc_bioagresseurs.BioagresseurInconnuError(bioagresseur)

    origine = svc_sources.garantir_source(db, source_code)
    existante = _trouver_arete(db, cible.id, identite.id, potager_id)
    if existante is not None:
        existante.poids = valeur
        existante.niveau_confiance = niveau
        existante.source_id = origine.id
        db.commit()
        return existante, False

    arete = SymptomeBioagresseur(
        symptome_id=cible.id,
        bioagresseur_id=identite.id,
        poids=valeur,
        niveau_confiance=niveau,
        potager_id=potager_id,
        source_id=origine.id,
    )
    db.add(arete)
    db.commit()
    return arete, True


# ── Import : mêmes issues que `bioagresseurs.importer_*` ─────────────────────
IMPORT_CREEE = svc_bioagresseurs.IMPORT_CREEE
IMPORT_ECRITE = svc_bioagresseurs.IMPORT_ECRITE
IMPORT_PRESERVEE = svc_bioagresseurs.IMPORT_PRESERVEE
IMPORT_INCHANGEE = svc_bioagresseurs.IMPORT_INCHANGEE


def importer_symptome(
    db: Session,
    libelle: str,
    organe: str,
    source: ReferentielSource,
    synonymes: Optional[str] = None,
) -> str:
    """[CA1] Écrit un symptôme **partagé** depuis un manifeste importé.

    Ne commite pas : l'appelant (`import_referentiel.importer`) contrôle la
    transaction pour pouvoir simuler tout un manifeste d'un coup (`dry_run`).
    Un import ne pose jamais de symptôme local à un potager — il alimente la
    connaissance partagée, par définition. Une ligne portant une autre origine
    est PRÉSERVÉE : la description du jardinier n'est jamais écrasée par un rejeu.
    """
    propre, organe_propre = _valider_symptome(libelle, organe)
    liste = (synonymes or "").strip() or None

    existant = (
        db.query(Symptome)
        .filter(
            Symptome.libelle_normalise == normaliser_libelle(propre),
            Symptome.potager_id.is_(None),
        )
        .first()
    )
    if existant is None:
        db.add(Symptome(
            libelle=propre,
            libelle_normalise=normaliser_libelle(propre),
            organe=organe_propre,
            synonymes=liste,
            recherche_fts=_vecteur(db, propre, liste),
            potager_id=None,
            source_id=source.id,
        ))
        return IMPORT_CREEE

    if existant.source_id is not None and existant.source_id != source.id:
        return IMPORT_PRESERVEE

    avant = (existant.libelle, existant.organe, existant.synonymes)
    existant.libelle = propre
    existant.libelle_normalise = normaliser_libelle(propre)
    existant.organe = organe_propre
    if liste is not None:
        existant.synonymes = liste
    existant.recherche_fts = _vecteur(db, propre, existant.synonymes)
    existant.source_id = source.id
    apres = (existant.libelle, existant.organe, existant.synonymes)
    return IMPORT_INCHANGEE if avant == apres else IMPORT_ECRITE


def importer_rattachement(
    db: Session,
    symptome: str,
    bioagresseur: str,
    poids: float,
    source: ReferentielSource,
    niveau_confiance: str = NIVEAU_INDICATIF,
) -> str:
    """[CA2, CA6] Écrit une arête **partagée** depuis un manifeste. Ne commite pas.

    Ni le symptôme ni le bioagresseur ne sont créés à la volée : un côté absent
    lève, et l'appelant le compte ignoré.
    """
    valeur = _valider_poids(poids)
    niveau = _valider_niveau(niveau_confiance)

    cible = get_symptome(db, symptome, potager_id=None)
    if cible is None:
        raise SymptomeInconnuError(symptome)
    identite = svc_bioagresseurs.get_bioagresseur(db, bioagresseur, potager_id=None)
    if identite is None:
        raise svc_bioagresseurs.BioagresseurInconnuError(bioagresseur)

    existante = _trouver_arete(db, cible.id, identite.id, None)
    if existante is None:
        db.add(SymptomeBioagresseur(
            symptome_id=cible.id,
            bioagresseur_id=identite.id,
            poids=valeur,
            niveau_confiance=niveau,
            potager_id=None,
            source_id=source.id,
        ))
        return IMPORT_CREEE

    if existante.source_id is not None and existante.source_id != source.id:
        return IMPORT_PRESERVEE

    inchangee = (existante.poids, existante.niveau_confiance) == (valeur, niveau)
    existante.poids = valeur
    existante.niveau_confiance = niveau
    existante.source_id = source.id
    return IMPORT_INCHANGEE if inchangee else IMPORT_ECRITE


# ═════════════════════════════════════════════════════════════════════════════
# [CA9] La recherche — plein texte, déterministe, zéro jeton
# ═════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class SymptomeTrouve:
    """Un symptôme reconnu dans une description, et à quel point."""

    symptome: Symptome
    score: float


def _classer_postgresql(
    db: Session, description: str, potager_id: Optional[int], limite: int
) -> list[SymptomeTrouve]:
    from sqlalchemy import func, text

    requete_texte = connaissance.tsquery(description)
    rang = func.ts_rank_cd(Symptome.recherche_fts, requete_texte, 32)
    lignes = (
        db.query(Symptome, rang.label("rang"))
        .filter(_visible_par(potager_id))
        .filter(Symptome.recherche_fts.op("@@")(requete_texte))
        .order_by(text("rang DESC"))
        .limit(limite)
        .all()
    )
    return [SymptomeTrouve(symptome=s, score=float(r or 0.0)) for s, r in lignes]


def _classer_sqlite(
    db: Session, description: str, potager_id: Optional[int], limite: int
) -> list[SymptomeTrouve]:
    """Repli de test — même sémantique, moteur sans dictionnaire.

    Le score est une couverture de termes plutôt qu'un `ts_rank_cd`, comme dans
    `connaissance._classer_sqlite` : le pendant exact du `@@` PostgreSQL, borné
    dans [0, 1] et rangeant dans le même ordre sur les cas usuels.

    ⚠️ Le score est celui d'US-098 (`connaissance.score_lexical`), appelé et non
    réécrit. Une première version calculait ici la part du SYMPTÔME couverte par
    la description, et l'inverse : mesurée sur le corpus, elle punissait
    exactement ce que le CA1 demande d'encourager — une liste de synonymes riche
    faisait chuter le score, et « mes tomates ont le cul noir » passait sous le
    seuil alors que le symptôme portait « cul noir » en toutes lettres.
    """
    termes = set(connaissance.lexemes(description))
    if not termes:
        return []
    candidats = (
        db.query(Symptome)
        .filter(_visible_par(potager_id))
        .filter(or_(*[Symptome.recherche_fts.like(f"%{terme}%") for terme in termes]))
        .all()
    )
    classes: list[SymptomeTrouve] = []
    for symptome in candidats:
        score = connaissance.score_lexical(termes, (symptome.recherche_fts or "").split())
        if score:
            classes.append(SymptomeTrouve(symptome=symptome, score=score))
    classes.sort(key=lambda t: (-t.score, t.symptome.id))
    return classes[:limite]


def rechercher_symptomes(
    db: Session,
    description: str,
    potager_id: Optional[int] = None,
    limite: int = 5,
) -> list[SymptomeTrouve]:
    """[CA1, CA9] Les symptômes du référentiel que cette description évoque.

    Ne filtre pas sur le seuil : c'est `prediagnostic()` qui tranche entre
    reconnaître et refuser (CA8), et la mesure du CA11 a besoin de voir le
    classement complet pour dire à quel rang la bonne piste sort.
    """
    if not (description or "").strip():
        return []
    classer = _classer_postgresql if connaissance.est_postgresql(db) else _classer_sqlite
    return classer(db, description, potager_id, limite)


# ═════════════════════════════════════════════════════════════════════════════
# [CA3, CA5, CA6, CA8] Le croisement — c'est lui qui fait le pré-diagnostic
# ═════════════════════════════════════════════════════════════════════════════
def _arete_culture(
    db: Session, ids_cultures: list[int], potager_id: Optional[int]
) -> dict[int, CultureBioagresseur]:
    """Les bioagresseurs réellement connus pour CETTE culture (US-162), indexés
    par identité. C'est cette table qui empêche de proposer un mildiou de la
    pomme de terre sur une carotte (CA3)."""
    portee = (
        CultureBioagresseur.potager_id.is_(None) if potager_id is None
        else or_(
            CultureBioagresseur.potager_id.is_(None),
            CultureBioagresseur.potager_id == potager_id,
        )
    )
    aretes = (
        db.query(CultureBioagresseur)
        .filter(CultureBioagresseur.culture_id.in_(ids_cultures))
        .filter(portee)
        .all()
    )
    # Une même identité peut être rattachée par une arête partagée ET par une
    # arête locale : la locale prime, c'est la connaissance de terrain du
    # jardinier sur son propre potager.
    par_identite: dict[int, CultureBioagresseur] = {}
    for arete in aretes:
        courante = par_identite.get(arete.bioagresseur_id)
        if courante is None or (courante.potager_id is None and arete.potager_id is not None):
            par_identite[arete.bioagresseur_id] = arete
    return par_identite


def prediagnostic(
    db: Session,
    description: str,
    culture: str,
    potager_id: Optional[int] = None,
    max_pistes: int = PREDIAGNOSTIC_MAX_PISTES,
    seuil: float = PREDIAGNOSTIC_SEUIL_SYMPTOME,
) -> Prediagnostic:
    """
    [CA3, CA5, CA6, CA8, CA9] Des pistes ordonnées, ou un refus honnête.

    Cinq issues, jamais confondues — les distinguer est tout le sujet du CA8 :

      - `culture_sans_fiche`  : la culture n'est pas au référentiel ;
      - `symptome_inconnu`    : aucun symptôme au-dessus du seuil ;
      - `aucun_croisement`    : symptôme reconnu, mais aucun de ses bioagresseurs
                                n'est rattaché à cette culture ;
      - `piste_unique`        : une seule piste, dite comme telle (CA5) ;
      - `pistes`              : deux ou trois hypothèses ordonnées.

    Zéro appel modèle sur tous ces chemins, par construction.
    """
    cible = (culture or "").strip()
    fiches = svc_bioagresseurs.fiches_visibles(db, cible, potager_id)
    if not fiches:
        return Prediagnostic(issue=ISSUE_CULTURE_SANS_FICHE, culture=cible)

    trouves = rechercher_symptomes(db, description, potager_id=potager_id, limite=5)
    retenus = [t for t in trouves if t.score >= seuil]
    if not retenus:
        return Prediagnostic(
            issue=ISSUE_SYMPTOME_INCONNU,
            culture=cible,
            score=trouves[0].score if trouves else 0.0,
        )

    tete = retenus[0]
    connus = _arete_culture(db, [f.id for f in fiches], potager_id)

    portee_arete = (
        SymptomeBioagresseur.potager_id.is_(None) if potager_id is None
        else or_(
            SymptomeBioagresseur.potager_id.is_(None),
            SymptomeBioagresseur.potager_id == potager_id,
        )
    )
    # ⚠️ Les symptômes retenus sont TOUS interrogés, pas seulement celui de tête.
    # Une description couvre souvent deux symptômes voisins (« les feuilles
    # jaunissent ET le pied flétrit ») ; n'en garder qu'un jetterait la moitié des
    # pistes que le croisement pouvait produire — et ferait tomber sous les deux
    # hypothèses que le CA5 exige.
    scores_symptome = {t.symptome.id: t.score for t in retenus}
    lignes = (
        db.query(SymptomeBioagresseur, Bioagresseur)
        .join(Bioagresseur, SymptomeBioagresseur.bioagresseur_id == Bioagresseur.id)
        .filter(SymptomeBioagresseur.symptome_id.in_(list(scores_symptome)))
        .filter(portee_arete)
        .filter(SymptomeBioagresseur.bioagresseur_id.in_(list(connus) or [-1]))
        .all()
    )

    # Une même identité peut être atteinte par deux symptômes : on garde la
    # meilleure plausibilité, sans jamais l'additionner — deux indices concordants
    # rendent une piste plus probable, ils ne la rendent pas deux fois vraie.
    meilleures: dict[int, tuple[float, SymptomeBioagresseur, Bioagresseur, str]] = {}
    for arete, identite in lignes:
        plausibilite = scores_symptome[arete.symptome_id] * float(arete.poids)
        libelle_symptome = next(
            t.symptome.libelle for t in retenus if t.symptome.id == arete.symptome_id
        )
        courante = meilleures.get(identite.id)
        if courante is None or plausibilite > courante[0]:
            meilleures[identite.id] = (plausibilite, arete, identite, libelle_symptome)

    ordonnees = sorted(
        meilleures.values(),
        key=lambda e: (
            -e[0],
            svc_bioagresseurs.ORDRE_FREQUENCE.get(
                connus[e[2].id].frequence, len(svc_bioagresseurs.FREQUENCES)
            ),
            e[2].nom_commun_fr,
        ),
    )[:max_pistes]

    if not ordonnees:
        return Prediagnostic(
            issue=ISSUE_AUCUN_CROISEMENT,
            culture=cible,
            symptome=tete.symptome.libelle,
            score=tete.score,
        )

    pistes: list[Piste] = []
    for _, arete, identite, libelle_symptome in ordonnees:
        source = db.get(ReferentielSource, arete.source_id)
        pistes.append(Piste(
            bioagresseur=identite.nom_commun_fr,
            categorie=identite.categorie,
            frequence=connus[identite.id].frequence,
            symptome=libelle_symptome,
            niveau_confiance=arete.niveau_confiance,
            source_code=source.code if source is not None else None,
            # Passe par le registre plutôt que par `source.attribution` brut :
            # c'est lui qui recompose la date de dernier téléchargement qu'exige
            # la licence EPPO (US-162 / CA7).
            attribution=(
                svc_sources.attribution_affichee(db, source.code)
                if source is not None else None
            ),
        ))

    # [CA6] La réserve est décidée sur les pistes SERVIES, et une seule suffit à
    # la déclencher : le jardinier ne peut pas savoir laquelle des trois n'a pas
    # été relue, donc la prudence porte sur l'ensemble. La phrase est celle
    # d'US-140/CA8, importée et jamais recopiée.
    reserve = (
        connaissance.RESERVE_INDICATIF
        if any(p.niveau_confiance != NIVEAU_VERIFIE for p in pistes) else ""
    )

    resultat = Prediagnostic(
        issue=ISSUE_PISTE_UNIQUE if len(pistes) == 1 else ISSUE_PISTES,
        culture=cible,
        symptome=tete.symptome.libelle,
        pistes=tuple(pistes),
        reserve=reserve,
        score=tete.score,
    )
    log.info(
        "🔎 PRÉ-DIAGNOSTIC │ issue=%-16s │ score=%.3f │ pistes=%d │ %s │ '%s'",
        resultat.issue, resultat.score, len(pistes), cible, (description or "")[:60],
    )
    return resultat

"""
app/services/associations.py — Associations de cultures, saisies et lues dans les
deux sens [US-163]
--------------------------------------------------------------------------------------------
Une association est une **arête typée** (CA1) entre deux cultures et/ou familles
botaniques — jamais un paragraphe dans une fiche narrative. C'est l'arbitrage
tranché par US-140/CA7bis (docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md §1.2) :
une relation écrite dans une fiche est un texte, elle ne peut ni être jointe à
l'historique d'une parcelle, ni déclencher un avertissement.

**Les associations sont saisies, pas importées** (arbitrage option A sur la
licence — zéro CC-BY-SA dans le socle) : ce module est le seul point d'écriture,
traversé par la correction au bot (`bot.cmd_association`) — « aucun second
mécanisme », comme le pose US-140. Chaque écriture s'attribue l'origine
`saisie_manuelle` au registre d'US-166 (CA10) : aucune arête anonyme.

**Honnêteté à deux niveaux (CA2, CA3).** La tradition horticole et la
littérature scientifique divergent souvent sur ce sujet. `niveau_preuve`
('etabli' | 'traditionnel') distingue les deux, et `formuler_nature` restitue
une formulation différente selon le niveau — jamais la même phrase pour un fait
établi et une croyance traditionnelle, exactement ce que l'Épic 5 impose déjà
sur les dates.

**Stockage orienté, lecture symétrique (CA5).** `AssociationCulture` porte un
côté A et un côté B, une ligne par couple saisi — comme `Evenement`. C'est
`lire_associations` qui garantit qu'interroger B restitue une relation saisie
A→B : une orientation de stockage ne doit jamais devenir une asymétrie de
réponse.

**Porté par la famille (CA4).** Un côté peut référencer une famille botanique
plutôt qu'une culture précise, et vaut alors pour toutes les cultures qui s'y
rattachent — la mesure du 25/08/2026 le justifie : les cucurbitacées se
répartissent sur dix libellés distincts, soit plus d'événements que la tomate.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.services import familles as svc_familles
from app.services import referentiel_sources as svc_sources
from app.services.attributs_culture import fiches_de_culture
from database.models import AssociationCulture, CultureConfig, FamilleBotanique, ReferentielSource

# ── [CA1] Vocabulaire fermé de la nature d'une association ──────────────────
NATURE_FAVORABLE = "favorable"
NATURE_DEFAVORABLE = "defavorable"
NATURE_NEUTRE = "neutre"
NATURES: tuple[str, ...] = (NATURE_FAVORABLE, NATURE_DEFAVORABLE, NATURE_NEUTRE)

# ── [CA2] Vocabulaire fermé du niveau de preuve ──────────────────────────────
NIVEAU_ETABLI = "etabli"
NIVEAU_TRADITIONNEL = "traditionnel"
NIVEAUX_PREUVE: tuple[str, ...] = (NIVEAU_ETABLI, NIVEAU_TRADITIONNEL)

#: [CA3] Formulation différenciée à la restitution — jamais la même phrase pour
#: un fait établi et une pratique traditionnelle non démontrée.
_FORMULATIONS: dict[str, dict[str, str]] = {
    NIVEAU_ETABLI: {
        NATURE_FAVORABLE: "favorable",
        NATURE_DEFAVORABLE: "défavorable",
        NATURE_NEUTRE: "neutre",
    },
    NIVEAU_TRADITIONNEL: {
        NATURE_FAVORABLE: "recommandé par la pratique traditionnelle",
        NATURE_DEFAVORABLE: "déconseillé par la pratique traditionnelle",
        NATURE_NEUTRE: "considéré neutre par la pratique traditionnelle",
    },
}


class EntiteInconnueError(LookupError):
    """[CA4] Le nom saisi ne désigne ni une culture ni une famille botanique
    déjà connues — jamais créé à la volée : contrairement à une famille
    corrigée sur une culture (US-067), un nom inconnu ici est plus probablement
    une faute de frappe qu'une entité réellement nouvelle."""


class ValeurAssociationInvalideError(ValueError):
    """[CA1, CA2] Nature ou niveau de preuve hors vocabulaire fermé, ou motif vide."""


@dataclass(frozen=True)
class AssociationLue:
    """Une association restituée du point de vue de la culture/famille interrogée (CA5)."""

    autre_partie: str
    autre_est_famille: bool
    nature: str
    motif: str
    niveau_preuve: str
    #: [CA3] Formulation déjà différenciée — jamais à recalculer côté appelant.
    formulation: str
    source_code: Optional[str]
    attribution: Optional[str]


def _valider(nature: str, niveau_preuve: str, motif: str) -> str:
    """[CA1, CA2] Vérifie nature/niveau_preuve/motif, communs à la saisie au bot
    et à l'import. Retourne le motif nettoyé, ou lève avant toute résolution ni
    écriture — une valeur refusée ne doit toucher à rien."""
    if nature not in NATURES:
        raise ValeurAssociationInvalideError(
            f"« {nature} » n'est pas une nature d'association admise. "
            f"Valeurs possibles : {', '.join(NATURES)}."
        )
    if niveau_preuve not in NIVEAUX_PREUVE:
        raise ValeurAssociationInvalideError(
            f"« {niveau_preuve} » n'est pas un niveau de preuve admis. "
            f"Valeurs possibles : {', '.join(NIVEAUX_PREUVE)}."
        )
    motif_propre = (motif or "").strip()
    if not motif_propre:
        raise ValeurAssociationInvalideError(
            "Le motif est obligatoire : c'est ce qui rend l'avertissement compréhensible "
            "plutôt qu'autoritaire."
        )
    return motif_propre


def formuler_nature(nature: str, niveau_preuve: str) -> str:
    """[CA3] Formulation différenciée à la restitution : « défavorable » pour une
    relation établie, « déconseillé par la pratique traditionnelle » pour une
    relation seulement traditionnelle — jamais la même phrase pour les deux."""
    try:
        return _FORMULATIONS[niveau_preuve][nature]
    except KeyError:
        raise ValeurAssociationInvalideError(
            f"Nature « {nature} » ou niveau de preuve « {niveau_preuve} » inconnu."
        ) from None


def _identites(db: Session, nom: str) -> tuple[list[int], Optional[int], str]:
    """
    Résout un nom vers les ids de fiches `culture_config` qui le partagent
    (CA6 d'US-067 : globales et personnalisées), et la famille à interroger —
    soit la famille éponyme si `nom` désigne directement une famille, soit la
    famille DE la culture désignée par `nom` (CA4 : une association saisie au
    niveau de la famille vaut pour toutes ses cultures, y compris celles qui
    n'ont jamais reçu leur propre saisie).

    Retourne (ids de fiches culture_config, id de famille à interroger, libellé
    d'affichage). Les deux premiers valent (`[]`, `None`) si `nom` ne désigne
    rien de connu.
    """
    fiches = fiches_de_culture(db, nom)
    if fiches:
        famille_id = next((f.famille_id for f in fiches if f.famille_id is not None), None)
        return [f.id for f in fiches], famille_id, fiches[0].nom
    famille = svc_familles.get_famille(db, nom)
    if famille is not None:
        return [], famille.id, famille.nom
    return [], None, nom


def _resoudre_cote(db: Session, nom: str) -> tuple[Optional[int], Optional[int], str]:
    """
    [CA4] Résout un côté d'association vers (culture_id, famille_id, libellé) —
    l'un des deux premiers est toujours None, l'autre renseigné. Une culture
    homonyme d'une famille est préférée à la famille (cas non rencontré en
    pratique — les noms de famille comme les noms de culture sont distincts).

    Préfère la fiche `culture_config` globale (potager_id NULL) quand plusieurs
    fiches partagent ce nom : une association est un fait agronomique, jamais
    une préférence de jardinier — même principe que US-067/CA7 et US-161. La
    lecture (`lire_associations`), elle, retrouve TOUTES les fiches homonymes
    quelle que soit celle retenue ici à l'écriture.

    Lève `EntiteInconnueError` si `nom` ne désigne ni une culture ni une
    famille déjà connues — l'une des deux doit avoir déjà été dictée/saisie.
    """
    fiches = fiches_de_culture(db, nom)
    if fiches:
        fiche = next((f for f in fiches if f.potager_id is None), fiches[0])
        return fiche.id, None, fiche.nom
    famille = svc_familles.get_famille(db, nom)
    if famille is not None:
        return None, famille.id, famille.nom
    raise EntiteInconnueError(nom)


def _trouver_association_existante(
    db: Session,
    culture_a_id: Optional[int], famille_a_id: Optional[int],
    culture_b_id: Optional[int], famille_b_id: Optional[int],
) -> Optional[AssociationCulture]:
    """[CA10] Une même paire, saisie dans l'une ou l'autre orientation, est une
    seule arête à corriger — jamais une seconde ligne concurrente."""
    directe = (
        db.query(AssociationCulture)
        .filter(
            AssociationCulture.culture_a_id == culture_a_id,
            AssociationCulture.famille_a_id == famille_a_id,
            AssociationCulture.culture_b_id == culture_b_id,
            AssociationCulture.famille_b_id == famille_b_id,
        )
        .first()
    )
    if directe is not None:
        return directe
    return (
        db.query(AssociationCulture)
        .filter(
            AssociationCulture.culture_a_id == culture_b_id,
            AssociationCulture.famille_a_id == famille_b_id,
            AssociationCulture.culture_b_id == culture_a_id,
            AssociationCulture.famille_b_id == famille_a_id,
        )
        .first()
    )


def enregistrer_association(
    db: Session,
    cote_a: str,
    cote_b: str,
    nature: str,
    motif: str,
    niveau_preuve: str = NIVEAU_ETABLI,
) -> tuple[AssociationCulture, bool]:
    """
    [CA1, CA2, CA4, CA10] Saisit ou corrige une association depuis le bot.

    La validation précède toute résolution comme toute écriture (même garde que
    `app.services.attributs_culture.corriger_attribut`, CA2) : une valeur
    refusée ne doit toucher à rien.

    Idempotent côté saisie : une association déjà connue pour cette paire, dans
    l'une ou l'autre orientation, est mise à jour plutôt que dupliquée.

    Retourne (association, créée) — `créée=False` si une ligne existante a été
    corrigée.

    Lève `ValeurAssociationInvalideError` si la nature, le niveau de preuve ou
    le motif sont invalides. Lève `EntiteInconnueError` si l'un des deux côtés
    ne désigne ni une culture ni une famille déjà connues.
    """
    motif_propre = _valider(nature, niveau_preuve, motif)

    culture_a_id, famille_a_id, _ = _resoudre_cote(db, cote_a)
    culture_b_id, famille_b_id, _ = _resoudre_cote(db, cote_b)

    origine = svc_sources.garantir_source(db, svc_sources.SOURCE_SAISIE_MANUELLE).id
    existante = _trouver_association_existante(
        db, culture_a_id, famille_a_id, culture_b_id, famille_b_id
    )

    if existante is not None:
        existante.nature = nature
        existante.motif = motif_propre
        existante.niveau_preuve = niveau_preuve
        existante.source_id = origine
        db.commit()
        return existante, False

    association = AssociationCulture(
        culture_a_id=culture_a_id, famille_a_id=famille_a_id,
        culture_b_id=culture_b_id, famille_b_id=famille_b_id,
        nature=nature, motif=motif_propre, niveau_preuve=niveau_preuve,
        source_id=origine,
    )
    db.add(association)
    db.commit()
    return association, True


#: Issues possibles d'`importer_association` — voir sa docstring.
IMPORT_CREEE = "creee"
IMPORT_ECRITE = "ecrite"
IMPORT_PRESERVEE = "preservee"
IMPORT_INCHANGEE = "inchangee"


def importer_association(
    db: Session,
    culture: str,
    compagnon: str,
    nature: str,
    motif: str,
    niveau_preuve: str,
    source: ReferentielSource,
) -> str:
    """
    [US-166/CA5, import] Écrit une association depuis un manifeste importé —
    même invariant « rejouable sans écraser l'humain » que
    `app.services.import_referentiel._peut_ecrire`, appliqué à la ligne entière :
    une association n'a qu'une seule origine, contrairement à un attribut de
    conduite qui en porte une par colonne (US-161).

    Ne commite pas : l'appelant (`import_referentiel.importer`) contrôle la
    transaction pour pouvoir simuler (`dry_run`) tout le manifeste d'un coup.

    Retourne :
    - `IMPORT_CREEE` — aucune ligne n'existait pour cette paire.
    - `IMPORT_ECRITE` — une ligne existait, déjà de la même origine (rejeu), et
      la valeur a changé.
    - `IMPORT_INCHANGEE` — idem, mais la valeur était déjà identique.
    - `IMPORT_PRESERVEE` — une ligne existe déjà avec une AUTRE origine (le plus
      souvent `saisie_manuelle`) : elle n'est jamais écrasée par un import.

    Lève `EntiteInconnueError` si `culture` ou `compagnon` ne désigne ni une
    culture ni une famille déjà connues — jamais créée à la volée (même
    invariant que CA7 d'US-161 : l'import enrichit le référentiel, il ne le
    peuple pas). Lève `ValeurAssociationInvalideError` si nature/niveau_preuve/
    motif sont invalides.
    """
    motif_propre = _valider(nature, niveau_preuve, motif)

    culture_a_id, famille_a_id, _ = _resoudre_cote(db, culture)
    culture_b_id, famille_b_id, _ = _resoudre_cote(db, compagnon)

    existante = _trouver_association_existante(
        db, culture_a_id, famille_a_id, culture_b_id, famille_b_id
    )

    if existante is None:
        association = AssociationCulture(
            culture_a_id=culture_a_id, famille_a_id=famille_a_id,
            culture_b_id=culture_b_id, famille_b_id=famille_b_id,
            nature=nature, motif=motif_propre, niveau_preuve=niveau_preuve,
            source_id=source.id,
        )
        db.add(association)
        return IMPORT_CREEE

    if existante.source_id is not None and existante.source_id != source.id:
        return IMPORT_PRESERVEE

    inchangee = (
        (existante.nature, existante.motif, existante.niveau_preuve)
        == (nature, motif_propre, niveau_preuve)
    )
    existante.nature = nature
    existante.motif = motif_propre
    existante.niveau_preuve = niveau_preuve
    existante.source_id = source.id
    return IMPORT_INCHANGEE if inchangee else IMPORT_ECRITE


def lire_associations(db: Session, nom: str) -> list[AssociationLue]:
    """
    [CA4, CA5] Associations connues pour une culture ou une famille, lues dans
    les deux sens : que la relation ait été saisie A→B ou B→A, interroger
    l'autre côté la restitue. Inclut les associations portées par la famille de
    la culture interrogée (CA4), pas seulement celles saisies pour son nom exact.

    Lève `EntiteInconnueError` si `nom` ne désigne ni une culture ni une
    famille connue.
    """
    culture_ids, famille_id, _ = _identites(db, nom)
    if not culture_ids and famille_id is None:
        raise EntiteInconnueError(nom)

    filtres = []
    if culture_ids:
        filtres.append(AssociationCulture.culture_a_id.in_(culture_ids))
        filtres.append(AssociationCulture.culture_b_id.in_(culture_ids))
    if famille_id is not None:
        filtres.append(AssociationCulture.famille_a_id == famille_id)
        filtres.append(AssociationCulture.famille_b_id == famille_id)

    lignes = db.query(AssociationCulture).filter(or_(*filtres)).all()

    resultats: list[AssociationLue] = []
    for ligne in lignes:
        cote_a_correspond = (
            (culture_ids and ligne.culture_a_id in culture_ids)
            or (famille_id is not None and ligne.famille_a_id == famille_id)
        )
        if cote_a_correspond:
            autre_culture_id, autre_famille_id = ligne.culture_b_id, ligne.famille_b_id
        else:
            autre_culture_id, autre_famille_id = ligne.culture_a_id, ligne.famille_a_id

        if autre_culture_id is not None:
            autre = db.get(CultureConfig, autre_culture_id)
            autre_partie, autre_est_famille = (autre.nom if autre else "?"), False
        else:
            autre = db.get(FamilleBotanique, autre_famille_id)
            autre_partie, autre_est_famille = (autre.nom if autre else "?"), True

        source = db.get(ReferentielSource, ligne.source_id)
        resultats.append(AssociationLue(
            autre_partie=autre_partie,
            autre_est_famille=autre_est_famille,
            nature=ligne.nature,
            motif=ligne.motif,
            niveau_preuve=ligne.niveau_preuve,
            formulation=formuler_nature(ligne.nature, ligne.niveau_preuve),
            source_code=source.code if source is not None else None,
            attribution=source.attribution if source is not None else None,
        ))
    return resultats

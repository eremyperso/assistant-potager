"""
app/services/fiche_culture.py — Fiche courte au bot, sans aucun jeton [US-164]
--------------------------------------------------------------------------------
Assemble par gabarit ce que le référentiel connaît déjà d'une culture : famille
botanique et délai de retour (US-067), attributs agronomiques de conduite
(US-161), et **ce qui attaque la culture** (US-162, branché ici par US-174).

⚠️ Deux conséquences de l'arrivée des bioagresseurs, qui ne sont pas des détails
d'affichage :

1. **La fiche n'est plus aveugle au potager (US-174 / CA6).** Famille, délai de
   retour, attributs et description sont des faits partagés ; un bioagresseur,
   lui, peut être déclaré localement par un potager et ne doit JAMAIS fuir
   ailleurs (US-162 / CA3). `generer_fiche_courte` prend donc un `potager_id` —
   omis, elle ne restitue que la connaissance partagée, ce qui est exactement
   le bon défaut pour un appelant qui n'a pas de contexte de potager.
2. **La fiche courte reste courte (US-174 / CA4).** Une culture porte parfois
   quinze bioagresseurs — mesuré sur la tomate le 07/09/2026, sur un référentiel
   de 335 arêtes. Les lister tous ferait perdre les rubriques suivantes, qui
   sont lues elles aussi : `LIMITE_BIOAGRESSEURS` en affiche les plus fréquents
   et compte le reste.

Les associations (US-163) et la rotation calculable s'y ajouteront de la même
façon — la fiche affiche ce qui existe en base, rien de plus (CA3).

**Aucun texte de fiche n'est stocké rédigé.** Ce module ne fait que lire des
colonnes déjà validées ailleurs (`app.services.attributs_culture`,
`app.services.familles`) : une correction du référentiel s'y propage
instantanément, et il n'y a rien à resynchroniser (CA3). C'est aussi ce qui la
rend gratuite — zéro jeton, zéro latence de modèle (CA9) — puisqu'aucun appel
au modèle de langage n'a de raison d'exister sur un simple assemblage de
colonnes déjà en base.

Honnêteté (CA5, CA6, CA13) : une culture sans aucune fiche `culture_config`
lève `LookupError` — au bot d'en faire un message d'absence, jamais une fiche
voisine forcée. Un attribut, une famille ou la description agronomique non
renseignés se lisent tels quels, jamais devinés.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date
from typing import Optional

from sqlalchemy.orm import Session

from app.services import associations as svc_associations
from app.services import attributs_culture as svc_attributs
from app.services import bioagresseurs as svc_bioagresseurs
from app.services import calendrier_cultural as svc_calendrier
from app.services import recalage_calendrier as svc_recalage
from app.services.associations import AssociationLue
from app.services.attributs_culture import AttributLu
from app.services.bioagresseurs import BioagresseurLu
from app.services.calendrier_cultural import DureeLue
from database.models import Parcelle
from utils.culture_resolve import normaliser_culture

#: [US-174 / CA4] Nombre maximum de bioagresseurs affichés dans la fiche courte.
#: Paramètre NOMMÉ et non constante enfouie : c'est une décision produit —
#: « la fiche tient sur un écran de téléphone » — révisable sans relire le code
#: qui l'applique. Au-delà, la fiche dit combien restent et par où les voir.
LIMITE_BIOAGRESSEURS = 5


@dataclass(frozen=True)
class FicheCourte:
    """Fiche courte d'une culture — gabarit assemblé à la lecture, jamais rédigé (CA3)."""

    culture: str
    famille: Optional[str]
    famille_attribution: Optional[str]
    delai_retour_annees: Optional[int]
    description_agronomique: Optional[str]
    attributs: tuple[AttributLu, ...]
    #: [US-174 / CA1, CA4] Les bioagresseurs RÉELLEMENT affichés — déjà ordonnés
    #: par fréquence et déjà tronqués. L'appelant n'a ni à trier ni à couper.
    bioagresseurs: tuple[BioagresseurLu, ...] = ()
    #: [US-174 / CA4] Combien la troncature a laissés de côté. 0 = tout est là.
    bioagresseurs_non_affiches: int = 0

    @property
    def bioagresseurs_connus(self) -> bool:
        """[US-174 / CA5] La culture a-t-elle au moins une arête connue ?

        Distingue « rien de rattaché » (l'application ne sait pas) d'une liste
        tronquée. Sans ce prédicat, l'appelant devrait déduire l'ignorance d'un
        tuple vide — et un jour la lirait comme « rien ne l'attaque », ce que le
        CA12 d'US-162 interdit précisément."""
        return bool(self.bioagresseurs)

    @property
    def attributions(self) -> list[str]:
        """[CA7, US-174/CA8] Mentions de source à afficher avec la réponse,
        dédupliquées — une seule ligne pour toute la fiche, jamais une par
        rubrique.

        Ne porte que les sources des bioagresseurs RÉELLEMENT affichés :
        l'obligation d'attribution naît de l'affichage, et citer la source d'une
        ligne tronquée mentionnerait une donnée que le jardinier ne voit pas."""
        vues: list[str] = []
        if self.famille_attribution and self.famille_attribution not in vues:
            vues.append(self.famille_attribution)
        for attribut in self.attributs:
            if attribut.attribution and attribut.attribution not in vues:
                vues.append(attribut.attribution)
        for bioagresseur in self.bioagresseurs:
            if bioagresseur.attribution and bioagresseur.attribution not in vues:
                vues.append(bioagresseur.attribution)
        return vues


def generer_fiche_courte(
    db: Session, culture: str, potager_id: Optional[int] = None
) -> FicheCourte:
    """
    [CA3, CA5, CA6, CA7] Assemble la fiche courte d'une culture depuis le
    référentiel, sans aucun appel au modèle de langage.

    [US-174 / CA6, CA7] `potager_id` ne scope QUE les bioagresseurs — la seule
    matière de cette fiche qui puisse être privée (US-162 / CA3). Famille, délai
    de retour, attributs de conduite et description restent partagés et rendus à
    l'identique quel que soit le potager : rendre la fiche consciente du potager
    ne doit rien rendre privé qui ne l'était pas. Omettre l'argument restitue la
    seule connaissance partagée — le bon défaut pour un appelant sans contexte.

    Lève `LookupError` si aucune fiche `culture_config` n'existe pour cette
    culture (CA5, CA10) — le bot en fait un message d'honnêteté explicite,
    jamais une fiche voisine forcée : la résolution est un nom exact après
    normalisation (casse/accents), jamais une correspondance approchée qui
    risquerait de restituer une culture différente.
    """
    fiches = svc_attributs.fiches_de_culture(db, culture)
    if not fiches:
        raise LookupError(culture)

    # [US-067 / CA7] La famille est partagée entre les fiches d'une même
    # culture (globale + personnalisées) : la première qui la renseigne suffit,
    # même stratégie que lire_attributs pour les attributs de conduite.
    famille_nom, famille_attribution, delai_retour = None, None, None
    for fiche in fiches:
        if fiche.famille_rel is not None:
            famille_nom = fiche.famille_rel.nom
            delai_retour = fiche.famille_rel.delai_retour_annees
            if fiche.famille_source_rel is not None:
                famille_attribution = fiche.famille_source_rel.attribution
            break

    # [CA13] Champ de texte libre indépendant des quatre attributs de conduite
    # d'US-161 — même stratégie de repli entre fiches globale/personnalisées.
    description_agronomique = None
    for fiche in fiches:
        if fiche.description_agronomique:
            description_agronomique = fiche.description_agronomique
            break

    attributs = tuple(svc_attributs.lire_attributs(db, culture))

    # [US-174 / CA1, CA4] Déjà ordonnés par fréquence par le service d'US-162 :
    # l'ordre métier vit là-bas, il n'est pas recalculé ici. La troncature, elle,
    # est une décision d'affichage propre à la fiche courte — d'où sa place ici
    # et non dans le service de lecture, que `/bioagresseur lister` utilise sans
    # limite.
    tous = svc_bioagresseurs.lire_bioagresseurs(db, culture, potager_id=potager_id)
    retenus = tuple(tous[:LIMITE_BIOAGRESSEURS])

    return FicheCourte(
        culture=fiches[0].nom,
        famille=famille_nom,
        famille_attribution=famille_attribution,
        delai_retour_annees=delai_retour,
        description_agronomique=description_agronomique,
        attributs=attributs,
        bioagresseurs=retenus,
        bioagresseurs_non_affiches=max(0, len(tous) - len(retenus)),
    )


# ═════════════════════════════════════════════════════════════════════════════
# Fiche structurée pour la PWA [US-206]
# ═════════════════════════════════════════════════════════════════════════════
#: [CA3] Les quatre étapes de durée toujours rendues, dans cet ordre — une
#: étape absente de l'itinéraire vaut « non renseignée », jamais omise : la
#: maquette du 25/09 en fait des lignes fixes du bloc Référentiel.
_ETAPES_DUREE: tuple[str, ...] = (
    svc_calendrier.ETAPE_LEVEE,
    svc_calendrier.ETAPE_RECOLTE,
    svc_calendrier.ETAPE_REPIQUAGE,
    svc_calendrier.ETAPE_PLANTATION_RECOLTE,
)


@dataclass(frozen=True)
class ParcelleEnPlace:
    """[CA4] Une parcelle où une variété est en place, avec la phase du moment
    (US-194) — même lecture que le Plan, jamais une seconde règle."""

    parcelle_id: int
    nom_parcelle: Optional[str]
    phase: str
    phase_depuis: str
    phase_depuis_nature: str


@dataclass(frozen=True)
class VarieteCultivee:
    """[CA4] Une variété d'une culture, à la date de référence.

    `parcelles` peut être vide sans que la variété soit masquée : c'est le cas
    d'une variété seulement en pépinière — le lot lui-même (numéro, stade,
    emplacement) n'est rendu qu'à partir d'US-209/US-210 (`lots_pepiniere`,
    jamais inventé avant leur livraison, CA4)."""

    variete: str
    nom_variete: str
    parcelles: tuple[ParcelleEnPlace, ...]
    lots_pepiniere: tuple = ()


@dataclass(frozen=True)
class FichePWA:
    """[US-206] Fiche structurée d'une culture pour la PWA — assemblage de
    lecture seule, jamais un texte stocké (même garde que `FicheCourte`)."""

    culture: str
    nom_culture: str
    #: [CA8] Culture absente du référentiel : les autres champs de référentiel
    #: restent à leur valeur neutre, `varietes_cultivees` reste rendu.
    fiche_absente: bool
    famille: Optional[str]
    famille_attribution: Optional[str]
    delai_retour_annees: Optional[int]
    type_organe_recolte: Optional[str]
    itineraires_connus: tuple[str, ...]
    attributs: tuple[AttributLu, ...]
    #: [CA3] Toujours quatre entrées, dans l'ordre de `_ETAPES_DUREE`.
    durees: tuple[DureeLue, ...]
    varietes_cultivees: tuple[VarieteCultivee, ...]
    associations: tuple[AssociationLue, ...]
    #: [CA9] Distingue « aucune association connue » de « rien à charger ».
    associations_connues: bool
    bioagresseurs: tuple[BioagresseurLu, ...]
    #: [CA9] Distingue « rien ne lui est rattaché » de « pas d'information ».
    bioagresseurs_connus: bool
    attributions: tuple[str, ...]


def _lire_varietes_cultivees(
    db: Session, culture_normalisee: str, potager_id: Optional[int], date_ref: _date
) -> tuple[VarieteCultivee, ...]:
    """
    [CA4 ; US-194] Variétés cultivées à `date_ref`, groupées par variété, avec
    leurs parcelles et la phase du moment — mêmes fonctions que le Plan
    (`lire_tuiles`, `phases_du_plan`) : la fiche culture ne recalcule rien.

    Une tuile sans phase (semis de pépinière sans plantation) laisse sa
    variété dans le résultat, avec une liste de parcelles vide (CA4) : c'est
    `phases_du_plan` qui exclut la parcelle de la phase, jamais la variété
    elle-même.
    """
    tuiles, _index = svc_recalage.lire_tuiles(db, [culture_normalisee], potager_id, date_ref)
    if not tuiles:
        return ()
    phases = svc_recalage.phases_du_plan(db, [culture_normalisee], potager_id, date_ref)

    parcelle_ids = {t.parcelle_id for t in tuiles}
    noms_parcelles = dict(
        db.query(Parcelle.id, Parcelle.nom).filter(Parcelle.id.in_(parcelle_ids)).all()
    )

    par_variete: dict[str, dict] = {}
    for tuile in tuiles:
        entree = par_variete.setdefault(
            tuile.variete, {"nom_variete": tuile.nom_variete, "parcelles": []}
        )
        phase = phases.get((tuile.parcelle_id, tuile.culture, tuile.variete))
        if phase is not None:
            entree["parcelles"].append(ParcelleEnPlace(
                parcelle_id=tuile.parcelle_id,
                nom_parcelle=noms_parcelles.get(tuile.parcelle_id),
                phase=phase["phase"],
                phase_depuis=phase["phase_depuis"],
                phase_depuis_nature=phase["phase_depuis_nature"],
            ))

    return tuple(
        VarieteCultivee(
            variete=variete,
            nom_variete=donnees["nom_variete"],
            parcelles=tuple(donnees["parcelles"]),
        )
        for variete, donnees in sorted(par_variete.items())
    )


def composer_fiche_pwa(
    db: Session, culture: str, potager_id: Optional[int], date_ref: _date
) -> FichePWA:
    """
    [US-206] Fiche structurée d'une culture pour la PWA.

    [CA10] Réutilise exactement les fonctions de lecture de la fiche du bot :
    `generer_fiche_courte` pour l'identité et les attributs de conduite,
    `bioagresseurs.lire_bioagresseurs` pour ce qui l'attaque — ici SANS
    troncature (CA6, contrairement à la fiche courte du bot) —,
    `associations.lire_associations` pour les voisinages (US-163),
    `calendrier_cultural.lire_calendrier` pour les durées (US-177), et
    `recalage_calendrier.lire_tuiles`/`phases_du_plan` pour les variétés
    cultivées (US-194) — le même calcul que le Plan.

    [CA8] Ne lève jamais : une culture inconnue du référentiel rend
    `fiche_absente=True`, tous les champs de référentiel à leur valeur
    neutre, mais `varietes_cultivees` reste lu depuis les événements, qui
    n'ont pas besoin d'un référentiel pour exister.

    [CA11] Zéro jeton, zéro appel réseau externe : uniquement des lectures en
    base, exactement comme le bot.
    """
    culture_normalisee = normaliser_culture(culture)

    try:
        courte = generer_fiche_courte(db, culture, potager_id)
        fiche_absente = False
    except LookupError:
        courte = None
        fiche_absente = True

    type_organe_recolte: Optional[str] = None
    itineraires_connus: tuple[str, ...] = ()
    durees: tuple[DureeLue, ...] = ()
    associations: tuple[AssociationLue, ...] = ()
    associations_connues = False
    bioagresseurs: tuple[BioagresseurLu, ...] = ()
    bioagresseurs_connus = False

    if not fiche_absente:
        fiches = svc_attributs.fiches_de_culture(db, culture)
        type_organe_recolte = fiches[0].type_organe_recolte if fiches else None

        calendrier = svc_calendrier.lire_calendrier(db, culture, potager_id)
        itineraires_connus = tuple(it.nom for it in calendrier.itineraires)
        itineraire = calendrier.itineraires[0] if calendrier.itineraires else None
        durees = tuple(
            (itineraire.duree(etape) if itineraire else None) or DureeLue(
                etape=etape,
                libelle=svc_calendrier.LIBELLES_ETAPES[etape],
                jours_min=None, jours_max=None, mention=None,
                affichage=svc_calendrier.TIRET, attribution=None,
            )
            for etape in _ETAPES_DUREE
        )

        try:
            associations = tuple(svc_associations.lire_associations(db, culture))
        except svc_associations.EntiteInconnueError:
            associations = ()
        associations_connues = bool(associations)

        try:
            bioagresseurs = tuple(
                svc_bioagresseurs.lire_bioagresseurs(db, culture, potager_id=potager_id)
            )
        except svc_bioagresseurs.CultureInconnueError:
            bioagresseurs = ()
        bioagresseurs_connus = bool(bioagresseurs)

    varietes_cultivees = _lire_varietes_cultivees(db, culture_normalisee, potager_id, date_ref)

    # [CA7] Une source par ligne, dédoublonnée sur toute la fiche.
    attributions: list[str] = []

    def _ajouter(source: Optional[str]) -> None:
        if source and source not in attributions:
            attributions.append(source)

    if courte is not None:
        _ajouter(courte.famille_attribution)
        for attribut in courte.attributs:
            _ajouter(attribut.attribution)
    for duree in durees:
        _ajouter(duree.attribution)
    for association in associations:
        _ajouter(association.attribution)
    for bioagresseur in bioagresseurs:
        _ajouter(bioagresseur.attribution)

    return FichePWA(
        culture=culture_normalisee,
        nom_culture=courte.culture if courte is not None else culture,
        fiche_absente=fiche_absente,
        famille=courte.famille if courte is not None else None,
        famille_attribution=courte.famille_attribution if courte is not None else None,
        delai_retour_annees=courte.delai_retour_annees if courte is not None else None,
        type_organe_recolte=type_organe_recolte,
        itineraires_connus=itineraires_connus,
        attributs=courte.attributs if courte is not None else (),
        durees=durees,
        varietes_cultivees=varietes_cultivees,
        associations=associations,
        associations_connues=associations_connues,
        bioagresseurs=bioagresseurs,
        bioagresseurs_connus=bioagresseurs_connus,
        attributions=tuple(attributions),
    )


def fiche_pwa_en_dict(fiche: FichePWA) -> dict:
    """[US-206] Forme sérialisable de `FichePWA`, servie par l'API."""
    return {
        "culture": fiche.culture,
        "nom_culture": fiche.nom_culture,
        "fiche_absente": fiche.fiche_absente,
        "famille": fiche.famille,
        "famille_attribution": fiche.famille_attribution,
        "delai_retour_annees": fiche.delai_retour_annees,
        "type_organe_recolte": fiche.type_organe_recolte,
        "itineraires_connus": list(fiche.itineraires_connus),
        "attributs": [
            {
                "cle": a.cle, "libelle": a.libelle, "valeur": a.valeur,
                "affichage": a.affichage, "source_code": a.source_code,
                "attribution": a.attribution,
            }
            for a in fiche.attributs
        ],
        "durees": [
            {
                "etape": d.etape, "libelle": d.libelle,
                "jours_min": d.jours_min, "jours_max": d.jours_max,
                "mention": d.mention, "affichage": d.affichage,
                "attribution": d.attribution,
            }
            for d in fiche.durees
        ],
        "varietes_cultivees": [
            {
                "variete": v.variete,
                "nom_variete": v.nom_variete,
                "parcelles": [
                    {
                        "parcelle_id": p.parcelle_id, "nom_parcelle": p.nom_parcelle,
                        "phase": p.phase, "phase_depuis": p.phase_depuis,
                        "phase_depuis_nature": p.phase_depuis_nature,
                    }
                    for p in v.parcelles
                ],
                "lots_pepiniere": list(v.lots_pepiniere),
            }
            for v in fiche.varietes_cultivees
        ],
        "associations": [
            {
                "autre_partie": a.autre_partie, "autre_est_famille": a.autre_est_famille,
                "nature": a.nature, "motif": a.motif, "niveau_preuve": a.niveau_preuve,
                "formulation": a.formulation, "source_code": a.source_code,
                "attribution": a.attribution,
            }
            for a in fiche.associations
        ],
        "associations_connues": fiche.associations_connues,
        "bioagresseurs": [
            {
                "nom_commun_fr": b.nom_commun_fr, "nom_scientifique": b.nom_scientifique,
                "categorie": b.categorie, "code_eppo": b.code_eppo,
                "frequence": b.frequence, "periode_risque": b.periode_risque,
                "local": b.local, "source_code": b.source_code,
                "attribution": b.attribution,
            }
            for b in fiche.bioagresseurs
        ],
        "bioagresseurs_total": len(fiche.bioagresseurs),
        "bioagresseurs_connus": fiche.bioagresseurs_connus,
        "attributions": list(fiche.attributions),
    }

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
from typing import Optional

from sqlalchemy.orm import Session

from app.services import attributs_culture as svc_attributs
from app.services import bioagresseurs as svc_bioagresseurs
from app.services.attributs_culture import AttributLu
from app.services.bioagresseurs import BioagresseurLu

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

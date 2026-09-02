"""
app/services/fiche_culture.py — Fiche courte au bot, sans aucun jeton [US-164]
--------------------------------------------------------------------------------
Assemble par gabarit ce que le référentiel connaît déjà d'une culture : famille
botanique et délai de retour (US-067), attributs agronomiques de conduite
(US-161). Les relations d'US-162 (associations) et US-163 (rotation calculable)
s'y ajouteront quand elles seront livrées — aucune n'existe encore en base, la
fiche affiche donc ce qui existe aujourd'hui, rien de plus (CA3).

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
from app.services.attributs_culture import AttributLu


@dataclass(frozen=True)
class FicheCourte:
    """Fiche courte d'une culture — gabarit assemblé à la lecture, jamais rédigé (CA3)."""

    culture: str
    famille: Optional[str]
    famille_attribution: Optional[str]
    delai_retour_annees: Optional[int]
    description_agronomique: Optional[str]
    attributs: tuple[AttributLu, ...]

    @property
    def attributions(self) -> list[str]:
        """[CA7] Mentions de source à afficher avec la réponse, dédupliquées."""
        vues: list[str] = []
        if self.famille_attribution and self.famille_attribution not in vues:
            vues.append(self.famille_attribution)
        for attribut in self.attributs:
            if attribut.attribution and attribut.attribution not in vues:
                vues.append(attribut.attribution)
        return vues


def generer_fiche_courte(db: Session, culture: str) -> FicheCourte:
    """
    [CA3, CA5, CA6, CA7] Assemble la fiche courte d'une culture depuis le
    référentiel, sans aucun appel au modèle de langage.

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

    return FicheCourte(
        culture=fiches[0].nom,
        famille=famille_nom,
        famille_attribution=famille_attribution,
        delai_retour_annees=delai_retour,
        description_agronomique=description_agronomique,
        attributs=attributs,
    )

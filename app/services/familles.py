"""
app/services/familles.py — Familles botaniques : référentiel + corrections bot [US-067]
------------------------------------------------------------------------------------------
`familles_botaniques` est une table globale (aucun potager_id, CA7) : la
famille d'une culture donnée est un fait, identique quel que soit le potager,
jamais une préférence de jardinier.

Conséquence directe pour `corriger_famille_culture` : la correction s'applique
à TOUTES les fiches `culture_config` qui partagent ce nom de culture (casse et
accents indifférents, CA6), qu'elles soient globales (potager_id NULL) ou
personnalisées à un potager précis (créées à la volée par
`app.services.parcelles.creer_culture_config`) — jamais à la seule fiche
résolue pour le potager courant, sous peine de laisser deux potagers avec deux
familles différentes pour la même culture (violation directe de CA7).
"""
from typing import Optional

from unidecode import unidecode
from sqlalchemy.orm import Session

from app.services.context import TenantContext
from app.services.parcelles import lister_cultures_config
from database.models import CultureConfig, FamilleBotanique
from utils.culture_resolve import normaliser_culture


def normaliser_famille(nom: str) -> str:
    """Casse/accents indifférents (CA6) — même stratégie que Parcelle.nom_normalise
    et utils.culture_resolve.normaliser_culture."""
    return unidecode((nom or "").strip().lower())


def get_famille(db: Session, nom: str) -> Optional[FamilleBotanique]:
    """Résout un nom de famille vers sa fiche, insensible à la casse/aux accents."""
    if not nom or not nom.strip():
        return None
    return (
        db.query(FamilleBotanique)
        .filter(FamilleBotanique.nom_normalise == normaliser_famille(nom))
        .first()
    )


def get_or_create_famille(db: Session, nom: str) -> FamilleBotanique:
    """Récupère la famille par son nom (casse/accents indifférents) ou la crée,
    délai de retour NULL (CA12/CA13), si elle est réellement nouvelle — le
    jardinier n'est jamais bloqué par une famille absente du pré-remplissage."""
    famille = get_famille(db, nom)
    if famille is not None:
        return famille
    famille = FamilleBotanique(nom=nom.strip(), nom_normalise=normaliser_famille(nom))
    db.add(famille)
    db.commit()
    return famille


def familles_par_culture(db: Session, ctx: TenantContext) -> dict[str, str]:
    """Culture normalisée (CA6) → nom de famille, pour les fiches culture_config
    visibles depuis ce potager (globales + propres) qui ont une famille
    renseignée. Une culture absente de ce dict n'a pas de famille (CA3) — à
    afficher "Autres" côté appelant, jamais stocké tel quel ici."""
    configs = lister_cultures_config(db, ctx)
    return {
        normaliser_culture(c.nom): c.famille_rel.nom
        for c in configs
        if c.famille_rel is not None
    }


def corriger_famille_culture(
    db: Session, culture: str, famille_nom: str
) -> tuple[list[CultureConfig], Optional[str]]:
    """
    [CA4, CA6, CA7] Corrige/renseigne la famille d'une culture depuis le bot.

    Lève LookupError si aucune fiche culture_config n'existe pour cette culture
    — elle doit avoir déjà été dictée au moins une fois (clarification
    végétatif/reproducteur) : `type_organe_recolte` est NOT NULL, la famille ne
    peut donc pas créer la fiche seule.

    Retourne (fiches modifiées, ancien nom de famille affiché avant correction —
    None si la culture n'avait encore aucune famille).
    """
    cible = normaliser_culture(culture)
    fiches = [c for c in db.query(CultureConfig).all() if normaliser_culture(c.nom) == cible]
    if not fiches:
        raise LookupError(culture)

    ancienne = fiches[0].famille_rel.nom if fiches[0].famille_rel is not None else None
    famille = get_or_create_famille(db, famille_nom)
    for fiche in fiches:
        fiche.famille_id = famille.id
    db.commit()
    return fiches, ancienne


def corriger_delai_retour(
    db: Session, famille_nom: str, annees: Optional[int]
) -> tuple[FamilleBotanique, Optional[int]]:
    """
    [CA14] Corrige le délai de retour d'une famille — vaut immédiatement pour
    toutes les cultures qui s'y rattachent, sans reprise individuelle, puisque
    le délai est porté par la famille et non par chaque culture (CA12).

    Lève LookupError si la famille est inconnue.
    Retourne (famille modifiée, ancien délai en années — None si non renseigné).
    """
    famille = get_famille(db, famille_nom)
    if famille is None:
        raise LookupError(famille_nom)
    ancien = famille.delai_retour_annees
    famille.delai_retour_annees = annees
    db.commit()
    return famille, ancien

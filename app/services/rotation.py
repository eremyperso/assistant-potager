"""
app/services/rotation.py — Rotation calculable à la campagne [US-163]
--------------------------------------------------------------------------------
Un conflit de rotation se CALCULE — il ne se rédige pas (CA6). « Quelles
cultures puis-je planter sur la parcelle NORD, sachant que j'y ai eu des
tomates l'an dernier ? » est une requête de graphe croisée avec l'historique
réel d'une parcelle ; aucune recherche plein texte ni vectorielle ne la produit.
Ce module croise trois faits déjà en base — l'historique de la parcelle,
la famille botanique de chaque culture qui y est passée, et le délai de retour
de cette famille (US-067/CA12) — sans qu'aucun ne soit dupliqué dans une fiche
(US-140/CA7bis, docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md §1.2).

**Quatre issues honnêtes, jamais confondues (CA7, CA8) :**
  - `conflit` / `ok` : un antécédent exploitable existe (ou non) pour la même
    famille — le prédicat est calculé, positif ou négatif ;
  - `aucun_antecedent` : la parcelle ne porte AUCUN événement exploitable —
    jamais interprété comme « aucun conflit » (CA8) ;
  - `indisponible` : la culture visée n'a pas de famille connue, ou sa famille
    n'a pas de délai de retour renseigné — jamais interprété comme « aucun
    conflit » non plus (US-067/CA13, réaffirmé ici).

**[CA9] Le calcul raisonne à la CAMPAGNE** (l'année de la date de l'événement),
jamais au jour près. C'est le domaine qui l'impose, et c'est aussi ce qui
protège le calcul d'une donnée de date imparfaite : une saisie sans ancrage
temporel retombe silencieusement sur le jour de saisie (`date_source =
'presumee'`), mais reste juste au niveau de l'année — un raisonnement au jour
près serait bâti sur du sable. Ce module ne filtre donc PAS sur `date_source` :
toute date non nulle est exploitable à ce grain.

**Deux gardes contre le bruit de l'historique réel (notes techniques US-163) :**
  - les bulletins météo automatiques (`texte_original = '[AUTO-METEO]'`, ~96 des
    321 événements mesurés le 25/08/2026) sont exclus : ils ne portent aucune
    culture ;
  - un événement dont la culture ne correspond à AUCUNE fiche `culture_config`
    connue (culture fantôme, ex. 'radi' né d'un échec de parsing) n'est jamais
    traité comme un antécédent établi.

**[CA11] Zéro jeton** : lecture pure de colonnes déjà en base, aucun appel à un
modèle de langage.

**Ce que ce module ne fait pas** : il ne restitue pas de texte figé côté bot.
`EvaluationRotation.message` est un gabarit unique assemblé depuis le
prédicat — CA6 le dit explicitement, le résultat est « un prédicat, exploitable
par une alerte », pas un passage de texte pré-rédigé. La restitution
proactive à la plantation est le périmètre d'US-167, qui réutilise
`evaluer_rotation` sans le réécrire.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.services import attributs_culture as svc_attributs
from app.services.context import TenantContext
from app.services.parcelles import lister_cultures_config
from database.models import Evenement
from utils.culture_resolve import normaliser_culture

#: Marqueur exact posé par le job météo quotidien (bot.py::job_meteo_quotidienne).
BULLETIN_AUTO_METEO = "[AUTO-METEO]"

STATUT_CONFLIT = "conflit"
STATUT_OK = "ok"
STATUT_AUCUN_ANTECEDENT = "aucun_antecedent"
STATUT_INDISPONIBLE = "indisponible"


@dataclass(frozen=True)
class EvaluationRotation:
    """[CA6] Le prédicat de rotation — une donnée structurée, exploitable par une
    alerte (US-167), jamais un texte rédigé à l'avance."""

    statut: str
    culture: str
    campagne_reference: int
    famille: Optional[str] = None
    delai_retour_annees: Optional[int] = None
    culture_precedente: Optional[str] = None
    campagne_derniere_occurrence: Optional[int] = None
    motif_indisponible: Optional[str] = None

    @property
    def en_conflit(self) -> bool:
        return self.statut == STATUT_CONFLIT

    @property
    def message(self) -> str:
        """Gabarit unique — un seul endroit qui sait dire ces quatre issues,
        réutilisé tel quel par le bot (`/rotation`) comme par une future
        alerte proactive (US-167)."""
        if self.statut == STATUT_AUCUN_ANTECEDENT:
            return (
                "Je n'ai pas d'antécédent sur cette parcelle : impossible de "
                "vérifier la rotation, je ne conclus pas à l'absence de conflit."
            )
        if self.statut == STATUT_INDISPONIBLE:
            return (
                f"Évaluation de rotation indisponible : {self.motif_indisponible}. "
                "Je n'affirme pas l'absence de conflit."
            )
        if self.statut == STATUT_CONFLIT:
            reste = self.delai_retour_annees - (
                self.campagne_reference - self.campagne_derniere_occurrence
            )
            return (
                f"Conflit de rotation : {self.culture} appartient à la famille "
                f"{self.famille}, déjà présente sur cette parcelle en "
                f"{self.campagne_derniere_occurrence} ({self.culture_precedente}). "
                f"Délai de retour recommandé : {self.delai_retour_annees} an(s) — "
                f"encore {reste} an(s) à attendre."
            )
        return (
            f"Aucun conflit de rotation connu pour {self.culture} sur cette "
            f"parcelle (famille {self.famille}, délai de retour "
            f"{self.delai_retour_annees} an(s))."
        )


def _campagne(evenement_date) -> Optional[int]:
    """[CA9] La campagne d'un événement est l'année de sa date — jamais plus fin."""
    return evenement_date.year if evenement_date is not None else None


def _familles_id_par_culture(db: Session, ctx: TenantContext) -> dict[str, int]:
    """Culture normalisée → id de sa famille, pour les fiches visibles depuis ce
    potager qui ont une famille renseignée. Une culture absente de ce dict n'a
    pas de famille connue — c'est ce qui exclut une culture fantôme (ex. 'radi')
    de l'historique exploitable, exactement comme une culture absente du
    référentiel : elle ne peut jamais devenir un antécédent établi."""
    configs = lister_cultures_config(db, ctx)
    mapping: dict[str, int] = {}
    for config in configs:
        cle = normaliser_culture(config.nom)
        if cle not in mapping and config.famille_id is not None:
            mapping[cle] = config.famille_id
    return mapping


def evaluer_rotation(
    db: Session,
    ctx: TenantContext,
    parcelle_id: int,
    culture: str,
    campagne_reference: Optional[int] = None,
) -> EvaluationRotation:
    """
    [CA6-CA9] Évalue si planter `culture` sur `parcelle_id` entre en conflit de
    rotation avec l'historique réel de cette parcelle.

    `campagne_reference` par défaut l'année en cours — surchageable pour un
    calcul situé dans le temps (tests, simulation « et si je plantais l'an
    prochain »).
    """
    campagne_reference = (
        campagne_reference if campagne_reference is not None else _date.today().year
    )

    fiches = svc_attributs.fiches_de_culture(db, culture)
    fiche_avec_famille = next((f for f in fiches if f.famille_id is not None), None)
    if not fiches or fiche_avec_famille is None:
        return EvaluationRotation(
            statut=STATUT_INDISPONIBLE,
            culture=culture,
            campagne_reference=campagne_reference,
            motif_indisponible=(
                f"la culture « {culture} » n'est pas rattachée à une famille "
                "botanique connue"
            ),
        )
    famille = fiche_avec_famille.famille_rel
    if famille.delai_retour_annees is None:
        return EvaluationRotation(
            statut=STATUT_INDISPONIBLE,
            culture=culture,
            campagne_reference=campagne_reference,
            famille=famille.nom,
            motif_indisponible=(
                f"le délai de retour de la famille « {famille.nom} » n'est pas renseigné"
            ),
        )

    # [Notes techniques] Bulletins météo exclus : aucune culture, pas un antécédent.
    evenements = (
        db.query(Evenement)
        .filter(
            Evenement.potager_id == ctx.potager_id,
            Evenement.parcelle_id == parcelle_id,
            Evenement.culture.isnot(None),
            Evenement.date.isnot(None),
            or_(
                Evenement.texte_original.is_(None),
                Evenement.texte_original != BULLETIN_AUTO_METEO,
            ),
        )
        .all()
    )

    familles_par_culture = _familles_id_par_culture(db, ctx)

    # [Notes techniques] Une culture inconnue du référentiel (fantôme, ex.
    # 'radi') n'entre jamais dans l'historique exploitable.
    exploitables: list[tuple[str, int, int]] = []
    for evenement in evenements:
        famille_id = familles_par_culture.get(normaliser_culture(evenement.culture))
        if famille_id is None:
            continue
        campagne = _campagne(evenement.date)
        if campagne is None:
            continue
        exploitables.append((evenement.culture, campagne, famille_id))

    if not exploitables:
        return EvaluationRotation(
            statut=STATUT_AUCUN_ANTECEDENT,
            culture=culture,
            campagne_reference=campagne_reference,
        )

    memes_famille = [
        (nom, campagne) for nom, campagne, famille_id in exploitables
        if famille_id == fiche_avec_famille.famille_id and campagne <= campagne_reference
    ]
    if not memes_famille:
        return EvaluationRotation(
            statut=STATUT_OK,
            culture=culture,
            campagne_reference=campagne_reference,
            famille=famille.nom,
            delai_retour_annees=famille.delai_retour_annees,
        )

    culture_precedente, campagne_derniere = max(memes_famille, key=lambda t: t[1])
    ecart = campagne_reference - campagne_derniere
    statut = STATUT_CONFLIT if ecart < famille.delai_retour_annees else STATUT_OK
    return EvaluationRotation(
        statut=statut,
        culture=culture,
        campagne_reference=campagne_reference,
        famille=famille.nom,
        delai_retour_annees=famille.delai_retour_annees,
        culture_precedente=culture_precedente,
        campagne_derniere_occurrence=campagne_derniere,
    )

"""
app/services/plan.py — Plan d'occupation des parcelles [US-041 / CA6]
-------------------------------------------------------------------------
Enveloppe tenant autour de utils/parcelles.calcul_occupation_parcelles()
et get_all_parcelles(), déjà isolées. Ajoute l'index surface_m2 par
culture (auparavant un db.query(CultureConfig) direct dans main.py /plan).
"""
from datetime import date as _date
from typing import Optional

from sqlalchemy.orm import Session

from app.services.context import TenantContext
from app.services.espacement_rang import espacement_rang_cm  # [US-226]
from app.services.parcelles import lister_cultures_config
from database.models import Parcelle
import utils.parcelles as _parcelles_mod


def get_parcelles(db: Session, ctx: TenantContext) -> list[Parcelle]:
    # Appel qualifié (pas d'import direct de la fonction) pour que les patches de
    # test sur utils.parcelles.get_all_parcelles restent effectifs.
    return _parcelles_mod.get_all_parcelles(db, potager_id=ctx.potager_id)


def get_occupation(db: Session, ctx: TenantContext, date_ref: Optional[_date] = None) -> dict:
    return _parcelles_mod.calcul_occupation_parcelles(db, date_ref, potager_id=ctx.potager_id)


def attributs_par_culture(db: Session, ctx: TenantContext) -> dict[str, dict]:
    """[US-226 / CA5, CA6] Surface au sol ET espacement sur le rang, en UNE lecture.

    `GET /plan` lisait déjà toutes les fiches culture pour la surface : la
    dérivation de l'espacement se branche dessus et ne coûte donc aucune requête
    supplémentaire — jamais une lecture par culture (RT6).

    [CA6] Une fiche personnalisée au potager (`potager_id` non nul, US-040) prime
    sur la fiche globale de même nom, comme pour tout autre attribut : le potager
    lit la fiche qu'il voit, pas la fiche partagée.
    """
    # [US-226 / CA3] Une incohérence de référentiel ne s'écrit qu'une fois par
    # lecture, quel que soit le nombre de lignes du plan qui portent la culture.
    journal: set = set()
    index: dict[str, dict] = {}
    for config in lister_cultures_config(db, ctx):
        cle = config.nom.lower()
        precedente = index.get(cle)
        if precedente is not None and precedente["personnalisee"] and config.potager_id is None:
            continue
        index[cle] = {
            "surface_m2": config.surface_m2 or 0.0,
            "espacement": config.espacement,
            "espacement_rang_cm": espacement_rang_cm(
                config.espacement,
                surface_m2=config.surface_m2,
                culture=config.nom,
                journal=journal,
            ),
            "personnalisee": config.potager_id is not None,
            # [US-217 / CA2] L'exposition conseillée (US-161), lue dans la même
            # passe : « Où les mettre » la compare à celle de la parcelle.
            "exposition": getattr(config, "exposition", None),
        }
    return index


def surface_par_culture(db: Session, ctx: TenantContext) -> dict[str, float]:
    """[GET /plan] Index surface_m2 par nom de culture (insensible à la casse)."""
    return {
        nom: attributs["surface_m2"]
        for nom, attributs in attributs_par_culture(db, ctx).items()
    }


# ── [US-327] Plan vu du dessus ───────────────────────────────────────────────

def parcelles_inactives(db: Session, ctx: TenantContext) -> list[dict]:
    """[US-327 / P7] Les parcelles INACTIVES du potager, dans l'ordre du chemin.

    Le plan les garde à leur place, grisées : une parcelle mise au repos reste un
    morceau du terrain. Elles ne portent ni culture ni rang — seulement de quoi les
    dessiner (nom, nature, géométrie)."""
    from app.services import geometrie as svc_geometrie   # import local : pas de cycle

    q = db.query(Parcelle).filter(Parcelle.actif.is_(False))
    if ctx.potager_id is not None:
        q = q.filter(Parcelle.potager_id == ctx.potager_id)
    return [
        {
            "id": p.id,
            "nom": p.nom,
            "actif": False,
            "ordre": p.ordre,
            "est_pepiniere": bool(p.est_pepiniere),
            "type_pepiniere": p.type_pepiniere,
            "geometrie": svc_geometrie.geometrie_parcelle(p),
        }
        for p in q.order_by(Parcelle.ordre).all()
    ]


#: [US-327 / P8] Les filtres du plan, dans l'ordre de la maquette.
FILTRE_A_CONFIRMER = "a_confirmer"
FILTRE_EN_RECOLTE = "en_recolte"
FILTRE_RANGS_LIBRES = "rangs_libres"


def compteurs_filtres(parcelles: list[dict]) -> dict:
    """[US-327 / CA4] Les compteurs des filtres du plan, calculés ICI et nulle part
    ailleurs : l'écran les affiche tels quels.

    - `a_confirmer` : cultures en place dont l'étape est prévue et due à la date de
      référence (US-320 le dit, `etapes.a_confirmer`) ;
    - `en_recolte` : cultures en place à l'étape « En récolte » ;
    - `rangs_libres` : rangs déclarés et libres (une parcelle sans nombre de rangs
      déclaré n'en compte aucun — inconnu n'est pas libre, R6).

    Les pépinières n'ont ni étapes ni rangs : elles ne comptent dans aucun filtre.
    """
    a_confirmer = en_recolte = rangs_libres = 0
    for p in parcelles:
        if p.get("est_pepiniere"):
            continue
        for c in p.get("cultures") or []:
            etapes = c.get("etapes") or {}
            if etapes.get("a_confirmer"):
                a_confirmer += 1
            if etapes.get("etape") == "en_recolte":
                en_recolte += 1
        rangs_libres += (p.get("disposition") or {}).get("rangs_libres") or 0
    return {
        FILTRE_A_CONFIRMER: a_confirmer,
        FILTRE_EN_RECOLTE: en_recolte,
        FILTRE_RANGS_LIBRES: rangs_libres,
    }

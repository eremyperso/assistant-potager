"""
app/services/suivi_culture.py — Le suivi d'une culture en place [US-322]
------------------------------------------------------------------------
Une culture, sur sa parcelle : d'où elle vient, où elle est, sa place sur le rang, ses
étapes, ce qui a été récolté, ses notes. UNE lecture alimente tout le suivi (CA4) ;
l'écran n'y recalcule aucune règle.

Ce n'est pas la fiche culture d'US-207, qui reste la fiche RÉFÉRENTIEL d'une espèce :
ici, c'est CETTE culture, sur CE rang.

Rien n'est inventé : chaque bloc absent de la donnée revient à None (CA2, « absent
plutôt que vide »). Les règles viennent de leurs services — étapes (US-320), rangs et
places (US-198, US-227, US-326), lots (US-209) — ce module ne fait que les assembler.
"""
from __future__ import annotations

import logging
from datetime import date as _date, datetime, time
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.services.context import TenantContext
from app.services import etapes_culture as svc_etapes
from app.services import plan as svc_plan
from app.services import repartition_rangs as svc_rangs
from app.services.parcelles import get_parcelle
from database.models import Evenement
from utils.culture_resolve import normaliser_culture

log = logging.getLogger("potager")

#: [S9] Les trois origines d'une culture en place.
ORIGINE_PEPINIERE = "pepiniere"
ORIGINE_ACHAT = "achat"
ORIGINE_SEMIS_DIRECT = "semis_direct"

#: [S10] Nombre de notes servies : les plus récentes d'abord.
NOTES_MAX = 20

_UNITES_POIDS = {"kg": 1.0, "g": 0.001}


def _meme_culture(colonne, culture: str):
    return func.lower(colonne) == (culture or "").strip().lower()


def _meme_variete(query, variete: Optional[str]):
    if variete:
        return query.filter(func.lower(Evenement.variete) == variete.strip().lower())
    return query.filter((Evenement.variete.is_(None)) | (Evenement.variete == ""))


def _jour(valeur) -> Optional[str]:
    if valeur is None:
        return None
    return (valeur.date() if isinstance(valeur, datetime) else valeur).isoformat()


def _fin_de_journee(jour: _date) -> datetime:
    return datetime.combine(jour, time.max)


# ── S2, S3 : la localisation et la place sur le rang ─────────────────────────

def _place_sur_le_rang(rangs: list[dict], longueur_parcelle: Optional[float]) -> Optional[dict]:
    """[S3] Ce que la culture occupe sur la longueur de son premier rang : pieds,
    mètres occupés, espacement, mètres libres ou dépassement. None si la place n'est
    pas calculable (pas de longueur, pas d'espacement, semis en surface — US-227)."""
    rang = next((r for r in rangs if r.get("places")), None)
    if rang is None:
        return None
    espacement = rang.get("espacement_rang_cm")
    longueur = rang.get("part_m") if rang.get("part_m") is not None else longueur_parcelle
    pieds = int(rang.get("places_prises") or 0) + int(rang.get("depassement_places") or 0)
    occupes = round(pieds * espacement / 100, 1) if espacement else None
    libres = round(max(0.0, float(longueur) - occupes), 1) if (longueur and occupes is not None) else None
    return {
        "pieds": pieds,
        "places": rang.get("places"),
        "espacement_cm": espacement,
        "longueur_m": longueur,
        "metres_occupes": occupes,
        "metres_libres": libres,
        "depassement_pieds": int(rang.get("depassement_places") or 0),
    }


# ── S7 : le cumul récolté ────────────────────────────────────────────────────

def _cumul_recolte(db: Session, potager_id, parcelle_id: int, culture: str,
                   variete: Optional[str], depuis: Optional[_date], jusqua: _date) -> Optional[dict]:
    """[S7] Ce qui a été récolté sur CETTE culture depuis son installation. Les poids
    sont ramenés en kg ; une autre unité (pièces, bottes) se cumule à part. None si
    rien n'a été récolté."""
    q = (
        db.query(Evenement.quantite, Evenement.unite)
        .filter(Evenement.type_action == "recolte")
        .filter(Evenement.parcelle_id == parcelle_id)
        .filter(_meme_culture(Evenement.culture, culture))
        .filter(Evenement.date <= _fin_de_journee(jusqua))
    )
    q = _meme_variete(q, variete)
    if potager_id is not None:
        q = q.filter(Evenement.potager_id == potager_id)
    if depuis is not None:
        q = q.filter(Evenement.date >= datetime.combine(depuis, time.min))
    kg = 0.0
    autres: dict[str, float] = {}
    for quantite, unite in q.all():
        u = (unite or "").strip().lower()
        if u in _UNITES_POIDS:
            kg += float(quantite or 0) * _UNITES_POIDS[u]
        elif quantite:
            autres[u or "unités"] = autres.get(u or "unités", 0.0) + float(quantite)
    if kg > 0:
        return {"quantite": round(kg, 1), "unite": "kg"}
    if autres:
        unite, quantite = max(autres.items(), key=lambda kv: kv[1])
        return {"quantite": round(quantite, 1), "unite": unite}
    return None


# ── S9 : l'origine ───────────────────────────────────────────────────────────

def _ids(texte: Optional[str]) -> list[int]:
    return [int(x) for x in (texte or "").split(";") if x.strip().isdigit()]


def _lot_de_plantation(db: Session, plantation: Evenement) -> Optional[Evenement]:
    """Le semis (le lot) d'où vient une plantation : directement (`origine_graines_id`)
    ou par ses godets (`source_evenement_ids`, US-029)."""
    if plantation.origine_graines_id:
        semis = db.get(Evenement, plantation.origine_graines_id)
        if semis is not None and semis.type_action == "semis":
            return semis
        if semis is not None and semis.origine_graines_id:
            return db.get(Evenement, semis.origine_graines_id)
    for source_id in _ids(plantation.source_evenement_ids):
        source = db.get(Evenement, source_id)
        if source is None:
            continue
        if source.type_action == "semis":
            return source
        if source.origine_graines_id:
            semis = db.get(Evenement, source.origine_graines_id)
            if semis is not None and semis.type_action == "semis":
                return semis
    return None


def _installation(db: Session, potager_id, parcelle_id: int, culture: str,
                  variete: Optional[str], jusqua: _date) -> Optional[Evenement]:
    """Le geste qui a mis la culture sur CETTE parcelle : la dernière plantation, ou le
    dernier semis en place, à la date de référence."""
    q = (
        db.query(Evenement)
        .filter(Evenement.type_action.in_(("plantation", "semis")))
        .filter(Evenement.parcelle_id == parcelle_id)
        .filter(_meme_culture(Evenement.culture, culture))
        .filter(Evenement.date <= _fin_de_journee(jusqua))
    )
    q = _meme_variete(q, variete)
    if potager_id is not None:
        q = q.filter(Evenement.potager_id == potager_id)
    return q.order_by(Evenement.date.desc(), Evenement.id.desc()).first()


def _origine(db: Session, installation: Optional[Evenement], serie: Optional[Evenement]) -> Optional[dict]:
    """[S9] Pépinière (lot n°, semé le, godets, plantés), achat (texte libre) ou semis
    direct (semé en place le). Le geste d'installation sur la parcelle fait foi ; le
    geste d'origine de la série (US-320 — le semis du lot, pour un plant de pépinière)
    ne sert que s'il manque. None si rien ne permet de le dire."""
    if installation is None:
        if serie is not None and serie.type_action == "semis" and serie.numero_lot is not None:
            return {"type": ORIGINE_PEPINIERE, "numero_lot": serie.numero_lot,
                    "date_semis": _jour(serie.date), "godets": None, "plantes": None,
                    "date_plantation": None}
        return None
    origine = installation
    if origine.type_action == "semis":
        return {"type": ORIGINE_SEMIS_DIRECT, "date": _jour(origine.date)}
    lot = _lot_de_plantation(db, origine)
    if lot is None and serie is not None and serie.type_action == "semis" and serie.id != origine.id             and serie.parcelle_id != origine.parcelle_id:
        lot = serie   # la série sait d'où vient le plant quand la plantation ne le dit pas
    if lot is None:
        # [Notes] L'origine « Achat » est déduite d'une plantation sans lot.
        return {"type": ORIGINE_ACHAT, "texte": (origine.commentaire or "").strip() or None,
                "date_plantation": _jour(origine.date)}
    godets = (
        db.query(func.coalesce(func.sum(Evenement.nb_plants_godets), 0))
        .filter(Evenement.type_action == "mise_en_godet")
        .filter(Evenement.origine_graines_id == lot.id)
        .scalar()
    )
    return {
        "type": ORIGINE_PEPINIERE,
        "numero_lot": lot.numero_lot,
        "date_semis": _jour(lot.date),
        "godets": int(godets or 0) or None,
        "plantes": int(origine.quantite or 0) or None,
        "date_plantation": _jour(origine.date),
    }


# ── S10 : les notes ──────────────────────────────────────────────────────────

def _notes(db: Session, potager_id, parcelle_id: int, culture: str,
           variete: Optional[str], jusqua: _date) -> list[dict]:
    """[S10] Les notes (observations) de cette culture sur cette parcelle, les plus
    récentes d'abord. `dictee` reste None : aucun geste ne dit encore s'il a été dicté."""
    q = (
        db.query(Evenement)
        .filter(Evenement.type_action == "observation")
        .filter(Evenement.parcelle_id == parcelle_id)
        .filter(_meme_culture(Evenement.culture, culture))
        .filter(Evenement.date <= _fin_de_journee(jusqua))
    )
    q = _meme_variete(q, variete)
    if potager_id is not None:
        q = q.filter(Evenement.potager_id == potager_id)
    return [
        {
            "id": e.id,
            "date": _jour(e.date),
            "texte": (e.commentaire or e.texte_original or "").strip(),
            "dictee": None,
        }
        for e in q.order_by(Evenement.date.desc(), Evenement.id.desc()).limit(NOTES_MAX).all()
    ]


# ── Le suivi ─────────────────────────────────────────────────────────────────

def suivi_culture(
    db: Session,
    ctx: TenantContext,
    parcelle_id: int,
    culture: str,
    variete: Optional[str] = None,
    date_ref: Optional[_date] = None,
) -> dict:
    """[US-322 / CA4] Tout le suivi d'une culture en place, en une lecture.

    Lève LookupError si la parcelle n'existe pas dans ce potager, ou si la culture
    n'y est pas en place à la date de référence."""
    today = _date.today()
    dr = min(date_ref, today) if date_ref else None
    jour = dr or today
    parcelle = get_parcelle(db, ctx, parcelle_id)
    if parcelle is None:
        raise LookupError(f"parcelle {parcelle_id}")

    occupation = svc_plan.get_occupation(db, ctx, dr)
    cle_culture = normaliser_culture(culture or "")
    cle_variete = (variete or "").strip().lower()
    entree = next(
        (e for e in occupation.get(parcelle.nom, []) or []
         if normaliser_culture(e.get("culture") or "") == cle_culture
         and (e.get("variete") or "").strip().lower() == cle_variete),
        None,
    )
    if entree is None:
        raise LookupError(f"{culture} {variete or ''} n'est pas en place sur {parcelle.nom}")

    # S2, S3 — la répartition du plan, pour cette parcelle seulement.
    attributs = svc_plan.attributs_par_culture(db, ctx)
    repartition = svc_rangs.repartition_du_plan(
        db, [parcelle], occupation, ctx.potager_id, dr, attributs_culture=attributs,
    )
    ligne = repartition["lignes"].get(svc_rangs.cle_ligne(parcelle.nom, entree), {})
    rangs = [
        r for r in (repartition["dispositions"].get(parcelle.nom) or {}).get("rangs", [])
        if not r.get("libre") and r.get("culture") == entree.get("culture")
        and (r.get("variete") or None) == (entree.get("variete") or None)
    ]

    # S4, S5, S8 — les étapes (US-320).
    cle = svc_etapes.cle_ligne(parcelle.id, entree.get("culture"), entree.get("variete"))
    etapes_lignes, _ = svc_etapes.etapes_du_plan(db, ctx.potager_id, jour, {cle})
    etapes = etapes_lignes.get(cle)

    # S9 — le geste qui a installé la culture sur cette parcelle, et l'origine de sa
    # série (US-320), qui peut être le semis du lot en pépinière.
    serie = db.get(Evenement, etapes["serie_id"]) if etapes and etapes.get("serie_id") else None
    installation = _installation(db, ctx.potager_id, parcelle.id, entree.get("culture"),
                                 entree.get("variete"), jour)
    debut = installation or serie
    depuis = (debut.date.date() if debut is not None and debut.date
              else ligne.get("date_installation"))

    unite = entree.get("unite") or "plants"
    suivi = {
        "parcelle_id": parcelle.id,
        "parcelle": parcelle.nom,
        "est_pepiniere": bool(parcelle.est_pepiniere),
        "culture": entree.get("culture"),
        "variete": entree.get("variete"),
        "quantite": entree.get("nb_plants"),
        "unite": unite,
        "date_ref_effective": jour.isoformat(),
        "rangs": ligne.get("numeros_rangs") or [],
        "position_source": ligne.get("position_source"),
        "place": _place_sur_le_rang(rangs, parcelle.longueur_m),
        "etapes": etapes,
        "recolte": _cumul_recolte(db, ctx.potager_id, parcelle.id, entree.get("culture"),
                                  entree.get("variete"), depuis, jour),
        "origine": _origine(db, installation, serie),
        "notes": _notes(db, ctx.potager_id, parcelle.id, entree.get("culture"),
                        entree.get("variete"), jour),
    }
    log.info(
        "[US-322] Suivi culture : potager_id=%s parcelle=%s culture=%s variete=%s "
        "etape=%s origine=%s notes=%d",
        ctx.potager_id, parcelle.nom, suivi["culture"], suivi["variete"],
        (etapes or {}).get("etape"), (suivi["origine"] or {}).get("type"), len(suivi["notes"]),
    )
    return suivi

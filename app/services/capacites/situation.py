"""
app/services/capacites/situation.py — La capacité `situation_culture` : « est-ce le moment ? » [US-339]
=====================================================================================================

Pour une culture dite par le jardinier, une seule réponse rend ce que la PWA montre à plusieurs endroits :

- le **verdict de saison** de la fiche culture, toutes actions confondues (CA1, CA2) —
  `app/services/situation_culture.py` fait le même choix que la section « Maintenant », sur les mêmes
  lectures (`GET /plan/confiances/candidates`, `GET /plan/calendriers`) ;
- **où elle en est chez lui** (CA3) : parcelles du Plan avec leur étape (US-320), lots de la Pépinière,
  récoltes notées au carnet cette saison ;
- **ses chiffres** (CA4) : ceux de l'écran Statistiques — pieds actifs et rendement cumulé pour une
  culture reproductive, pieds restants pour une végétative ;
- le **geste suivant** plausible (CA5), jamais écrit : la proposition reste à `proposer_geste`.

Une culture inconnue du référentiel est dite comme telle, sans verdict (CA6). Aucune règle n'est recopiée :
chaque morceau vient de la fonction d'endpoint que l'écran appelle (R3 de `07_REGLE_D_UNE_CAPACITE.md`).
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.services import situation_culture as svc_situation
from app.services.capacites.lectures import _api, _appeler, _cle, _date_iso, _enveloppe, _ligne_statistique, _texte
from app.services.capacites.registre import AppelCapacite, Capacite, RefusCapacite, enregistrer_capacite
from database.models import CultureConfig
from utils.culture_resolve import _meilleure_correspondance, normaliser_culture

log = logging.getLogger("potager")

RECOLTES_MAX = 100
PARCELLES_MAX = 20

#: [CA5] Le geste suivant d'un lot de pépinière, tel que la Pépinière le suggère.
_GESTE_DE_LOT = {
    "mise_en_godet": "mettre en godet", "repiquage": "mettre en godet", "endurcissement": "endurcir",
    "plantation": "planter", "planter": "planter",
}


def referentiel(db: Session, potager_id: Optional[int]) -> list[str]:
    """Les cultures du référentiel visibles de ce potager (catalogue partagé et cultures propres)."""
    lignes = (db.query(CultureConfig.nom)
              .filter(or_(CultureConfig.potager_id == potager_id, CultureConfig.potager_id.is_(None))).all())
    return sorted({nom for (nom,) in lignes if nom})


def resoudre_culture(db: Session, potager_id: Optional[int], dite: str) -> Optional[str]:
    """[CA1] La culture du référentiel que le jardinier désigne : nom exact, puis faute courante ou pluriel
    (Levenshtein ≤ 2, « salades » → « salade »), puis mot contenu. `None` : culture inconnue (CA6).
    « salade » reste « salade » : elle a sa propre fiche, jamais remplacée par « laitue »."""
    return _meilleure_correspondance(dite, referentiel(db, potager_id))


def _chez_toi(culture: str, plan: dict, pepiniere: dict, recoltes: list[dict]) -> dict:
    """[CA3] Où en est la culture chez le jardinier : en place, en pépinière, récoltée cette saison."""
    cle = _cle(culture)
    en_place = [
        {"parcelle": p.get("nom"), "variete": c.get("variete"), "pieds": c.get("nb_plants"), "unite": c.get("unite"),
         "etape": (c.get("etapes") or {}).get("etape"), "rang": c.get("rang")}
        for p in plan.get("parcelles") or [] if not p.get("est_pepiniere")
        for c in p.get("cultures") or [] if _cle(c.get("culture")) == cle
    ]
    lots = [
        {"lot": lot.get("numero") or lot.get("lot_id"), "variete": lot.get("variete"), "stade": lot.get("stade"),
         "action_suggeree": lot.get("action_suggeree")}
        for lot in pepiniere.get("lots") or [] if _cle(lot.get("culture")) == cle
    ]
    etats = [e for e, present in (("en_place", en_place), ("en_pepiniere", lots), ("recoltee_cette_saison", recoltes))
             if present]
    return {
        "etat": etats or ["absente"],
        "en_place": [{k: v for k, v in e.items() if v is not None} for e in en_place[:PARCELLES_MAX]],
        "lots_pepiniere": [{k: v for k, v in lot.items() if v is not None} for lot in lots],
        "recoltes_cette_saison": len(recoltes),
    }


def _geste_suivant(verdict: dict, chez_toi: dict) -> str:
    """[CA5] Le geste suivant plausible, jamais écrit : récolter ce qui est en récolte, faire avancer un lot,
    sinon le geste de la fiche (maintenant ou à la prochaine fenêtre)."""
    if any(e.get("etape") == "en_recolte" for e in chez_toi["en_place"]):
        return "récolter"
    for lot in chez_toi["lots_pepiniere"]:
        geste = _GESTE_DE_LOT.get(str(lot.get("action_suggeree") or "").lower())
        if geste:
            return f"{geste} le lot {lot.get('lot')}" if lot.get("lot") else geste
    if chez_toi["en_place"]:
        return "suivre la culture en place"
    if verdict["verdict"] == svc_situation.VERDICT_MAINTENANT:
        return verdict["geste"].lower()
    prochaine = verdict.get("prochaine_fenetre")
    if prochaine:
        return f"{prochaine['geste'].lower()} en {prochaine['fenetre']}"
    return ""


def verdict_de_saison(db: Session, appel: AppelCapacite, culture: str, quand: date) -> tuple[dict, dict]:
    """Le verdict de la fiche culture pour `culture` à `quand`, et le calendrier de la zone lu au passage."""
    api = _api()
    confiances = _appeler(api.get_confiances_candidates_plan, culture=[culture], date_cible=quand,
                          potager_id=None, ctx=appel.ctx)
    calendriers = _appeler(api.get_calendriers_plan, culture=[culture], potager_id=None, date_ref=None,
                           ctx=appel.ctx)
    entree = confiances["cultures"].get(culture)
    mois = (calendriers["cultures"].get(culture) or {}).get("mois")
    return svc_situation.verdict(entree, mois, culture, mois_courant=quand.month), calendriers


def _situation_culture(db: Session, appel: AppelCapacite) -> dict:
    """[CA1-CA6] Verdict de saison, état au potager, chiffres et geste suivant d'une culture."""
    dite = _texte(appel.arguments, "culture")
    if not dite:
        raise RefusCapacite("Précise la culture (argument `culture`).", "arguments")
    quand = _date_iso(appel.arguments, "date") or date.today()
    culture = resoudre_culture(db, appel.ctx.potager_id, dite)
    if culture is None:
        log.info("[US-339] situation_culture : « %s » inconnue du référentiel (potager %s)", dite, appel.ctx.potager_id)
        return _enveloppe({
            "culture_dite": dite, "verdict": svc_situation.VERDICT_INCONNUE,
            "texte": f"« {dite} » n'est pas dans le référentiel des cultures : je n'ai ni calendrier ni fiche. "
                     "Je ne donne pas de période au hasard.",
        })

    verdict, calendriers = verdict_de_saison(db, appel, culture, quand)
    api = _api()
    plan = _appeler(api.get_plan, date_ref=None, potager_id=None, ctx=appel.ctx)
    pepiniere = _appeler(api.get_pepiniere_lots, date_ref=None, potager_id=None, ctx=appel.ctx)
    recoltes = _appeler(
        api.historique, limit=RECOLTES_MAX, offset=0, action="recolte", culture=culture, parcelle=None,
        from_date=date(quand.year, 1, 1).isoformat(), to_date=quand.isoformat(),
        date_ref=None, potager_id=None, ctx=appel.ctx,
    )["evenements"]
    stats = _appeler(api.stats, date_ref=None, potager_id=None, ctx=appel.ctx)
    chiffres = next((_ligne_statistique(e) for e in stats["stock_par_culture"]
                     if normaliser_culture(e.get("culture")) == normaliser_culture(culture)), None)

    chez_toi = _chez_toi(culture, plan, pepiniere, recoltes)
    donnees = {
        "culture": culture, "date": quand.isoformat(),
        "zone_climatique": calendriers.get("zone_libelle") or calendriers.get("zone_climatique"),
        **verdict,
        "chez_toi": chez_toi,
        "geste_suivant": _geste_suivant(verdict, chez_toi),
        "a_ecrire": "rien : pour noter un geste, proposer_geste, puis l'accord du jardinier",
        "source": "fiche culture de l'application (calendrier de la zone et confiance du jour)",
    }
    if culture != dite:
        donnees["culture_dite"] = dite
    if chiffres:  # [CA4]
        donnees["chiffres"] = chiffres
    log.info("[US-339] situation_culture : %s le %s → %s ; chez toi %s", culture, quand, verdict["verdict"],
             chez_toi["etat"])
    return _enveloppe(donnees)


enregistrer_capacite(Capacite(
    nom="situation_culture", titre="Est-ce le moment pour cette culture ?",
    description=(
        "Répond à « est-ce le moment de semer ou planter telle culture ? » : le verdict de la fiche culture "
        "de l'application, toutes actions confondues : c'est le moment, pas ce mois-ci avec la prochaine "
        "fenêtre, hors calendrier connu, ou culture inconnue ; puis où elle en est chez le jardinier (parcelles et "
        "étape, lots en pépinière, récoltes de la saison), ses pieds et son rendement, et le geste suivant "
        "plausible. À appeler AVANT de parler de saison. Lecture seule : n'écrit rien."
    ),
    proprietes={
        "culture": {"type": "string", "description": "La culture, comme le jardinier l'a dite (salades, tomate…)."},
        "date": {"type": "string", "description": "Date visée, ISO (AAAA-MM-JJ) ; aujourd'hui par défaut."},
    },
    requis=("culture",), executer=_situation_culture,
))

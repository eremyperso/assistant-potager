"""
app/services/capacites/que_faire.py — La capacité `que_faire_maintenant` : « qu'est-ce que je fais au potager ? » [US-340]
==========================================================================================================

Le compagnon (et l'assistant IA du MCP) reçoit **un verdict déjà trié**, pas trois lectures à recouper :

- les **gestes à faire** (CA1) : les trois listes de l'écran « Aujourd'hui au potager » (US-328 : à confirmer, à
  libérer, à placer), les lots de pépinière à traiter, les rappels et les récoltes attendues dépassées
  (`voir_echeances`), classés par urgence ;
- les cultures qu'il est **temps de semer ou de planter ce mois-ci** (CA2), selon le climat du potager, avec la
  source de chaque verdict : le calcul de la Pépinière pour les semis en pépinière, les fenêtres de la zone pour la
  pleine terre et la plantation.

R3 de `07_REGLE_D_UNE_CAPACITE.md` : rien n'est recopié. Les listes de l'écran sont celles de `GET /plan`
(`taches_du_jour`), rendues telles quelles dans `aujourdhui` (CA3, un test les compare) ; les échéances viennent de
`voir_echeances`, les semis de `que_semer_ce_mois`.

CA4 — Une culture **reproductive** déjà en récolte (tomate, haricot…) ne se « termine » pas parce qu'une étape
prévue est atteinte : la capacité propose une **nouvelle cueillette**, et ne parle de fin de culture que si le
jardinier arrache ou arrête. CA5 — un potager neuf, où rien n'est en place, le dit et ne rend que les semis du mois.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.services import calendrier_cultural as svc_calendrier
from app.services import echeances_lots as svc_echeances
from app.services.capacites.lectures import _api, _appeler, _enveloppe, _voir_echeances
from app.services.capacites.potager_ecrans import _liste, _que_semer_ce_mois
from app.services.capacites.registre import AppelCapacite, Capacite, enregistrer_capacite
from app.services.etapes_culture import ETAPE_EN_RECOLTE, ETAPE_TERMINEE
from app.services.situation_culture import fenetre_lisible
from database.models import CultureConfig
from utils.culture_resolve import normaliser_culture

log = logging.getLogger("potager")

GESTES_MAX = 15

#: [CA1] Les classes d'urgence, de la plus pressante à la moins pressante.
URGENCE_EN_RETARD = 1
URGENCE_AUJOURD_HUI = 2
URGENCE_A_TRAITER = 3
#: À urgence et retard égaux : ce qui est daté à la journée (rappel) avant ce qui attend une confirmation.
ORDRE_ORIGINE = {"rappel": 0, "recolte_attendue": 1, "a_confirmer": 2, "pepiniere": 3, "a_placer": 4, "a_liberer": 5}
LIBELLE_URGENCE = {URGENCE_EN_RETARD: "en retard", URGENCE_AUJOURD_HUI: "aujourd'hui", URGENCE_A_TRAITER: "à traiter"}


def cultures_reproductives(db: Session, potager_id: Optional[int]) -> set[str]:
    """Les cultures dont l'organe récolté est reproducteur (fruit, gousse, graine) : on les cueille à plusieurs reprises."""
    lignes = db.query(CultureConfig.nom, CultureConfig.type_organe_recolte).filter(
        (CultureConfig.potager_id == potager_id) | (CultureConfig.potager_id.is_(None))).all()
    return {normaliser_culture(nom) for nom, organe in lignes
            if nom and normaliser_culture(organe or "").startswith("reprod")}


def _jours_de_retard(iso: Optional[str], aujourdhui: date) -> Optional[int]:
    try:
        return (aujourdhui - date.fromisoformat((iso or "")[:10])).days
    except ValueError:
        return None


def _urgence(retard: Optional[int]) -> int:
    if retard is None:
        return URGENCE_A_TRAITER
    return URGENCE_EN_RETARD if retard > 0 else URGENCE_AUJOURD_HUI if retard == 0 else URGENCE_A_TRAITER


def _geste_a_confirmer(ligne: dict, reproductives: set[str]) -> str:
    """[CA4] Ce que le jardinier est invité à faire pour une étape prévue atteinte."""
    etape = ligne.get("etape")
    reproductive = normaliser_culture(ligne.get("culture") or "") in reproductives
    if etape in (ETAPE_EN_RECOLTE, ETAPE_TERMINEE) and reproductive:
        # Une récolte répétée n'est jamais la fin de la culture : la fin se note quand il arrache ou arrête.
        return "nouvelle cueillette"
    if etape == ETAPE_EN_RECOLTE:
        return "récolte possible"
    if etape == ETAPE_TERMINEE:
        return "fin de culture à confirmer"
    return f"{(ligne.get('etape_libelle') or 'étape').lower()} à confirmer"


#: [US-340] Le geste que `proposer_geste` écrit pour confirmer une étape. Une observation ne porte AUCUNE quantité ;
#: pour les autres, la quantité n'est jamais devinée : on la demande au jardinier.
GESTE_PAR_ETAPE = {
    "levee": {"type": "observation", "note": "levée constatée", "quantite": "aucune"},
    "semee": {"type": "semis", "quantite": "à demander au jardinier"},
    "plantee": {"type": "plantation", "quantite": "à demander au jardinier"},
    ETAPE_EN_RECOLTE: {"type": "recolte", "quantite": "à demander au jardinier"},
}


def _geste_a_proposer(ligne: dict, reproductive: bool) -> Optional[dict]:
    """Le geste qui confirmerait cette étape, ou `None` quand l'application n'a pas de geste à proposer."""
    etape = ligne.get("etape")
    if etape == ETAPE_TERMINEE:
        return GESTE_PAR_ETAPE[ETAPE_EN_RECOLTE] if reproductive else None  # une fin de culture se note dans l'application
    return GESTE_PAR_ETAPE.get(etape)


def _lieu(parcelle: Optional[str], rang: Optional[int] = None) -> str:
    return f"{parcelle} · R{rang}" if parcelle and rang else (parcelle or "")


def gestes_a_faire(taches: dict, echeances: dict, reproductives: set[str], aujourdhui: date) -> list[dict]:
    """[CA1] Les gestes du jour, classés par urgence puis par retard. Fonction pure."""
    gestes: list[dict] = []
    for ligne in taches.get("a_confirmer") or []:
        retard = _jours_de_retard(ligne.get("etape_date"), aujourdhui)
        proposable = _geste_a_proposer(ligne, normaliser_culture(ligne.get("culture") or "") in reproductives)
        gestes.append({"origine": "a_confirmer", "geste": _geste_a_confirmer(ligne, reproductives),
                       **({"geste_a_proposer": proposable} if proposable else {}),
                       "culture": ligne.get("culture"), "variete": ligne.get("variete"),
                       "lieu": _lieu(ligne.get("parcelle"), ligne.get("rang")),
                       "date_prevue": ligne.get("etape_date"), "retard_jours": retard, "urgence": _urgence(retard)})
    for ligne in taches.get("a_liberer") or []:
        gestes.append({"origine": "a_liberer", "geste": "libérer le rang", "culture": ligne.get("culture"),
                       "variete": ligne.get("variete"), "lieu": _lieu(ligne.get("parcelle")),
                       "date_prevue": ligne.get("fin_le"), "retard_jours": None, "urgence": URGENCE_A_TRAITER})
    for carte in taches.get("a_placer") or []:
        gestes.append({"origine": "a_placer", "geste": "planter" if carte.get("origine") == "lot" else "placer sur le plan",
                       "culture": carte.get("culture"), "variete": carte.get("variete"),
                       "lieu": carte.get("pepiniere") or "", "quantite": carte.get("quantite"),
                       "date_prevue": None, "retard_jours": None, "urgence": URGENCE_A_TRAITER})
    for lot in echeances.get("lots_a_traiter") or []:
        action = lot.get("action")
        gestes.append({"origine": "pepiniere", "geste": (action.get("libelle") if isinstance(action, dict) else action),
                       "culture": lot.get("culture"), "variete": lot.get("variete"), "lieu": "pépinière",
                       "lot": lot.get("lot"), "date_prevue": None, "retard_jours": None, "urgence": URGENCE_A_TRAITER})
    for recolte in echeances.get("recoltes_attendues_depassees") or []:
        reproductive = normaliser_culture(recolte.get("culture") or "") in reproductives
        gestes.append({"origine": "recolte_attendue", "geste": "nouvelle cueillette" if reproductive else "récolte attendue",
                       "culture": recolte.get("culture"), "variete": recolte.get("variete"),
                       "lieu": _lieu(recolte.get("parcelle_nom")), "date_prevue": None, "retard_jours": None,
                       "urgence": URGENCE_EN_RETARD})
    for rappel in echeances.get("rappels") or []:
        retard = _jours_de_retard(rappel.get("echeance"), aujourdhui)
        gestes.append({"origine": "rappel", "geste": rappel.get("objet"), "culture": None, "lieu": "",
                       "date_prevue": rappel.get("echeance"), "retard_jours": retard, "urgence": _urgence(retard)})
    gestes.sort(key=lambda g: (g["urgence"], -(g["retard_jours"] or 0), ORDRE_ORIGINE.get(g["origine"], 9)))
    return gestes


def a_semer_ou_planter(semis: dict, f_pleine_terre: list, f_plantation: list, mois: int, zone: Optional[str]) -> list[dict]:
    """[CA2] Les cultures dont une fenêtre est ouverte ce mois-ci, chacune avec le geste, la fenêtre et sa source."""
    lignes: list[dict] = []
    source_pepiniere = "Pépinière de l'application : « Le bon moment pour semer » (calendrier de la zone)"
    for c in semis.get("a_semer") or []:
        lignes.append({"culture": c["culture"], "geste": "semer en pépinière", "fenetre": c.get("fenetre"),
                       "graines_en_stock": bool(c.get("varietes_en_stock")), "source": source_pepiniere})
    for nom in semis.get("a_semer_sans_graines") or []:
        lignes.append({"culture": nom, "geste": "semer en pépinière", "graines_en_stock": False, "source": source_pepiniere})
    zone_dite = f"calendrier de la zone {zone}" if zone else "calendrier de la zone du potager"
    for geste, fenetres in (("semer en pleine terre", f_pleine_terre), ("planter", f_plantation)):
        vus: set[str] = set()
        for nom, debut, fin in sorted(fenetres):
            if mois in svc_calendrier.mois_couverts(debut, fin) and nom not in vus:
                vus.add(nom)
                lignes.append({"culture": nom, "geste": geste,
                               "fenetre": fenetre_lisible(svc_calendrier.mois_couverts(debut, fin)), "source": zone_dite})
    return lignes


def _texte(potager_neuf: bool, gestes: list[dict], a_faire_ce_mois: list[dict]) -> str:
    morceaux: list[str] = []
    if potager_neuf:
        morceaux.append("Rien n'est encore en place dans ce potager (ni culture, ni lot, ni rappel).")
    elif gestes:
        liste = "; ".join(
            f"{g['geste']}" + (f" — {g['culture']}" if g.get("culture") else "") + (f" ({g['lieu']})" if g.get("lieu") else "")
            + f" [{LIBELLE_URGENCE[g['urgence']]}]" for g in gestes[:GESTES_MAX])
        morceaux.append(f"{len(gestes)} geste(s) à faire : {liste}.")
    else:
        morceaux.append("Aucun geste à faire pour le moment.")
    if a_faire_ce_mois:
        noms = sorted({f"{c['culture']} ({c['geste']})" for c in a_faire_ce_mois})
        morceaux.append("Ce mois-ci, selon le climat : " + _liste(noms) + ".")
    else:
        morceaux.append("Aucune culture à semer ou planter ce mois-ci.")
    return " ".join(morceaux)


def _que_faire_maintenant(db: Session, appel: AppelCapacite) -> dict:
    """[CA1-CA5] Les gestes du jour classés par urgence, puis ce qui se sème ou se plante ce mois-ci."""
    api = _api()
    plan = _appeler(api.get_plan, date_ref=None, potager_id=None, ctx=appel.ctx)
    aujourdhui = date.fromisoformat(plan["date_ref_effective"])
    taches = plan["taches_du_jour"]
    echeances = _voir_echeances(db, appel)
    semis = _que_semer_ce_mois(db, appel)
    potager_id = appel.ctx.potager_id
    zone, f_pleine_terre = svc_echeances.fenetres_de_phase(db, potager_id, svc_calendrier.PHASE_SEMIS_PLEINE_TERRE)
    _, f_plantation = svc_echeances.fenetres_de_phase(db, potager_id, svc_calendrier.PHASE_PLANTATION)
    zone_libelle = svc_calendrier.LIBELLES_ZONES.get(zone, zone)

    en_place = any(c.get("culture") for p in plan["parcelles"] if not p.get("est_pepiniere") for c in p.get("cultures") or [])
    lots = _appeler(api.get_pepiniere_lots, date_ref=None, potager_id=None, ctx=appel.ctx)["lots"]
    potager_neuf = not (en_place or lots or plan.get("non_localisees") or echeances.get("rappels"))  # [CA5]
    gestes = [] if potager_neuf else gestes_a_faire(taches, echeances, cultures_reproductives(db, potager_id), aujourdhui)
    ce_mois = a_semer_ou_planter(semis, f_pleine_terre, f_plantation, aujourdhui.month, zone_libelle)
    donnees = {
        "date": aujourdhui.isoformat(), "potager_neuf": potager_neuf, "zone_climatique": zone_libelle,
        "gestes": gestes[:GESTES_MAX], "nombre_de_gestes": len(gestes),
        "aujourdhui": taches,
        "a_semer_ou_planter_ce_mois": ce_mois,
        "texte": _texte(potager_neuf, gestes, ce_mois),
        "consigne": ("Réponds d'après `texte` et `gestes`, dans l'ordre : l'urgence est déjà triée. Liste ce qui est à "
                     "faire, puis arrête-toi : ne propose pas d'enregistrer, de noter ni de rappeler. Si, et seulement "
                     "si, le jardinier demande de noter un geste, utilise `geste_a_proposer.type` de la ligne ; une "
                     "observation ne porte aucune quantité, et une quantité jamais dite se demande, elle ne se "
                     "devine pas. Une culture reproductive déjà en récolte se cueille à nouveau : ne parle jamais de "
                     "fin de culture à moins que le jardinier arrache ou arrête."),
        "source": "écran « Aujourd'hui au potager » (plan), Pépinière et calendrier de la zone",
    }
    log.info("[US-340] que_faire_maintenant : %s → %d gestes, %d à semer ou planter ce mois-ci, neuf=%s",
             aujourdhui, len(gestes), len(ce_mois), potager_neuf)
    return _enveloppe(donnees)


enregistrer_capacite(Capacite(
    nom="que_faire_maintenant", titre="Qu'est-ce que je fais au potager ?",
    description=(
        "Répond à « qu'est-ce que je dois faire au potager ? » et « qu'est-ce que je peux semer ce mois-ci ? » : la "
        "liste des gestes du jour, déjà classée par urgence (étapes à confirmer, cultures à libérer, lots à planter, "
        "pépinière à traiter, rappels, nouvelles cueillettes), la même que l'écran « Aujourd'hui au potager », puis "
        "les cultures à semer ou planter ce mois-ci selon le climat du potager, chacune avec sa source. Un potager "
        "neuf le dit et ne rend que les semis du mois. Lecture seule."
    ),
    executer=_que_faire_maintenant,
))

"""
app/services/capacites/potager_ecrans.py — Trois lectures que la PWA sait déjà [US-351]
======================================================================================

Les références humaines du 18/11/2026 (`REFERENCE_HUMAINE_B01.md`) montrent que la première cause d'échec du
compagnon est de ne pas lire ce que l'application sait. Trois lectures servent déjà un écran et n'avaient aucun
chemin vers lui :

- `voisinages_culture` — les associations d'une culture, celles de la fiche culture (`GET /cultures/{culture}/fiche`,
  US-163, US-206) : favorables et à éviter, cultures et familles séparées, avec leur origine (CA1) ;
- `que_semer_ce_mois` — « Le bon moment pour semer » de l'onglet Parcours de la Pépinière
  (`GET /pepiniere/lots` → `parcours`, `echeances_lots`, US-218, US-240) : les cultures à semer, sinon
  « aucun semis ce mois-ci » et la prochaine ouverture (CA2) ;
- `voir_mon_potager` — la ville, la zone, les abris et les pépinières déclarés (Paramètres du potager, plan),
  pour ne jamais demander « as-tu une serre ? » ni citer une ville que rien ne porte (CA3).

Chaque réponse vient de la fonction de l'écran (R3 de `07_REGLE_D_UNE_CAPACITE.md`), en lecture seule, sous le
potager du jardinier (CA4). Aucune description ne donne une ville en exemple (CA3).
"""
from __future__ import annotations

import logging
from datetime import date

from sqlalchemy.orm import Session

from app.services import calendrier_cultural as svc_calendrier
from app.services import plan as svc_plan
from app.services import potager_actif as svc_potager_actif
from app.services.capacites.lectures import _api, _appeler, _date_iso, _enveloppe, _texte
from app.services.capacites.registre import AppelCapacite, Capacite, RefusCapacite, enregistrer_capacite
from app.services.capacites.situation import resoudre_culture
from app.services.situation_culture import MOIS_NOMS
from utils.parcelles import ABRI_AUCUN, LIBELLES_ABRI

log = logging.getLogger("potager")

#: [CA3] Où le jardinier règle la ville du potager dans la PWA (vérifié le 21/11/2026 : `ParametresPotager.jsx`,
#: section Identité ; « Localiser » ouvre la même saisie depuis la carte météo et la fiche calendrier).
REGLAGE_VILLE = ("Menu du potager › Paramètres du potager › Identité › Ville "
                 "(ou « Localiser » sur la carte météo d'accueil)")
#: Où un abri se déclare : la fiche de la parcelle, champ « Abri » (US-181).
REGLAGE_ABRI = "Plan › la parcelle › champ « Abri » (voile, châssis, tunnel, serre)"


# ── 1. voisinages_culture ─────────────────────────────────────────────────────
def listes_de_voisinage(associations: list[dict]) -> dict:
    """[CA1] Les associations de la fiche culture en deux listes, cultures et familles séparées, avec leur origine.
    Fonction pure : la fiche les sert déjà dans cette forme, on ne fait que les ranger."""
    listes: dict = {"favorables": [], "familles_favorables": [], "a_eviter": [], "familles_a_eviter": []}
    for a in associations:
        sens = "favorables" if a.get("nature") == "favorable" else "a_eviter"
        cle = f"familles_{sens}" if a.get("autre_est_famille") else sens
        listes[cle].append({
            "nom": a.get("autre_partie"),
            "preuve": "établie" if a.get("niveau_preuve") == "etabli" else "pratique traditionnelle",
            **({"motif": a["motif"]} if a.get("motif") else {}),
            **({"origine": a["attribution"]} if a.get("attribution") else {}),
        })
    return listes


def _voisinages_culture(db: Session, appel: AppelCapacite) -> dict:
    """[CA1] Les bons et les mauvais voisins d'une culture, ceux de la fiche culture de l'application."""
    dite = _texte(appel.arguments, "culture")
    if not dite:
        raise RefusCapacite("Précise la culture (argument `culture`).", "arguments")
    culture = resoudre_culture(db, appel.ctx.potager_id, dite)
    if culture is None:
        return _enveloppe({"culture_dite": dite, "culture_connue": False,
                           "texte": f"« {dite} » n'est pas dans le référentiel des cultures : je n'ai pas ses voisinages."})
    fiche = _appeler(_api().get_fiche_culture, culture=culture, date_cible=None, potager_id=None, ctx=appel.ctx)
    zone, _origine = svc_calendrier.zone_du_potager(db, appel.ctx.potager_id)
    donnees = {"culture": culture, "zone_climatique": svc_calendrier.LIBELLES_ZONES.get(zone, zone),
               "source": "fiche culture de l'application, rubrique Voisinages"}
    if culture != dite:
        donnees["culture_dite"] = dite
    if fiche.get("fiche_absente") or not fiche.get("associations_connues") or not fiche.get("associations"):
        donnees["texte"] = f"Aucune association connue pour {culture} dans la fiche : je ne cite aucun voisin."
        donnees.update({"favorables": [], "a_eviter": [], "familles_favorables": [], "familles_a_eviter": []})
    else:
        donnees.update(listes_de_voisinage(fiche["associations"]))
        donnees["consigne"] = "Ne cite que ces voisins : une culture absente de ces listes n'est pas dans la fiche."
    log.info("[US-351] voisinages_culture : %s → %d favorables, %d à éviter", culture,
             len(donnees["favorables"]) + len(donnees["familles_favorables"]),
             len(donnees["a_eviter"]) + len(donnees["familles_a_eviter"]))
    return _enveloppe(donnees)


# ── 2. que_semer_ce_mois ──────────────────────────────────────────────────────
def bon_moment_pour_semer(parcours: dict, quand: date) -> dict:
    """[CA2] « Le bon moment pour semer » tel que l'onglet Parcours l'affiche : les cultures à semer (avec ou sans
    graines en stock), sinon « aucun semis ce mois-ci » et la prochaine ouverture du calendrier de semis."""
    a_semer = [{"culture": c["culture"], "fenetre": c.get("fenetre"),
                "varietes_en_stock": [v.get("variete") if isinstance(v, dict) else v
                                      for v in c.get("varietes_en_stock") or []]}
               for c in parcours.get("a_semer") or []]
    sans_graines = [c["culture"] for c in parcours.get("a_semer_sans_graines") or []]
    donnees: dict = {"mois": MOIS_NOMS[quand.month - 1], "a_semer": a_semer, "a_semer_sans_graines": sans_graines}
    if a_semer or sans_graines:
        noms = [c["culture"] for c in a_semer] + sans_graines
        donnees["texte"] = "À semer en pépinière ce mois-ci : " + ", ".join(noms) + "."
        if sans_graines:
            donnees["texte"] += " Sans graines en stock : " + ", ".join(sans_graines) + "."
        return donnees
    calendrier = parcours.get("calendrier_semis") or {}
    donnees["zone_climatique"] = calendrier.get("zone")
    ouverture = next((m for m in calendrier.get("mois") or [] if m.get("s_ouvrent")), None)
    donnees["texte"] = "Aucun semis ce mois-ci."
    if ouverture:
        numero = int(ouverture["mois"][5:7])
        donnees["prochaine_ouverture"] = {"mois": MOIS_NOMS[numero - 1], "date": (calendrier.get(
            "prochaine_ouverture") or {}).get("date"), "cultures": ouverture["s_ouvrent"]}
        donnees["texte"] += (f" Prochaine ouverture : {MOIS_NOMS[numero - 1]} ("
                             + ", ".join(ouverture["s_ouvrent"]) + ").")
    return donnees


def _que_semer_ce_mois(db: Session, appel: AppelCapacite) -> dict:
    """[CA2] Ce qui se sème en pépinière ce mois-ci, par le calcul de l'onglet Parcours."""
    quand = _date_iso(appel.arguments, "date") or date.today()
    pepiniere = _appeler(_api().get_pepiniere_lots, date_ref=quand, potager_id=None, ctx=appel.ctx)
    reference = date.fromisoformat(pepiniere["date_ref_effective"])
    donnees = {"date": reference.isoformat(), **bon_moment_pour_semer(pepiniere["parcours"], reference),
               "source": "Pépinière de l'application, onglet Parcours, « Le bon moment pour semer »"}
    if reference != quand:
        donnees["note"] = "La Pépinière se lit au plus tard aujourd'hui : la date demandée a été ramenée à aujourd'hui."
    log.info("[US-351] que_semer_ce_mois : %s → %d à semer", reference, len(donnees["a_semer"]))
    return _enveloppe(donnees)


# ── 3. voir_mon_potager ───────────────────────────────────────────────────────
def _voir_mon_potager(db: Session, appel: AppelCapacite) -> dict:
    """[CA3] La ville, la zone, les abris et les pépinières déclarés du potager."""
    detail = svc_potager_actif.obtenir_potager(db, appel.ctx.user_id, appel.ctx.potager_id) or {}
    zone, origine = svc_calendrier.zone_du_potager(db, appel.ctx.potager_id)
    parcelles = svc_plan.get_parcelles(db, appel.ctx)
    abris = [{"parcelle": p.nom, "abri": LIBELLES_ABRI.get(p.abri, p.abri)}
             for p in parcelles if p.abri and p.abri != ABRI_AUCUN]
    pepinieres = [{"parcelle": p.nom, "type": p.type_pepiniere or "non renseigné"}
                  for p in parcelles if p.est_pepiniere]
    ville = (detail.get("ville") or "").strip() or None
    donnees = {
        "potager": detail.get("nom"), "ville": ville,
        "zone_climatique": svc_calendrier.libelle_zone(zone, origine),
        "parcelles": [p.nom for p in parcelles if not p.est_pepiniere],
        "abris": abris, "pepinieres": pepinieres,
        "serre_declaree": any(a["abri"] == LIBELLES_ABRI["serre"] for a in abris),
        "pepiniere_chaude_declaree": any(p["type"] == "chaude" for p in pepinieres),
        "parcelles_sans_abri_renseigne": [p.nom for p in parcelles if not p.est_pepiniere and p.abri is None],
        "reglage_abri": REGLAGE_ABRI,
    }
    if ville is None:
        donnees["ville_absente"] = ("Aucune ville n'est réglée pour ce potager : la météo n'est pas lisible. "
                                    "Ne cite aucune ville ; propose de la régler.")
        donnees["reglage_ville"] = REGLAGE_VILLE
    if not abris and not pepinieres:
        donnees["texte"] = "Aucun abri (serre, tunnel, châssis, voile) ni pépinière n'est déclaré dans ce potager."
    log.info("[US-351] voir_mon_potager : potager %s ville=%s abris=%d pépinières=%d", appel.ctx.potager_id,
             "oui" if ville else "non", len(abris), len(pepinieres))
    return _enveloppe(donnees)


# ── Déclarations ──────────────────────────────────────────────────────────────
enregistrer_capacite(Capacite(
    nom="voisinages_culture", titre="Quels voisins pour cette culture ?",
    description=(
        "Répond à « que planter à côté de telle culture, quoi éviter ? » : les associations de la fiche culture de "
        "l'application, en deux listes (favorables, à éviter), cultures et familles botaniques séparées, avec leur "
        "niveau de preuve. Une culture sans association connue le dit. Ne cite jamais un voisin absent de ces "
        "listes. Lecture seule."
    ),
    proprietes={"culture": {"type": "string", "description": "La culture, comme le jardinier l'a dite."}},
    requis=("culture",), executer=_voisinages_culture,
))
enregistrer_capacite(Capacite(
    nom="que_semer_ce_mois", titre="Que semer ce mois-ci ?",
    description=(
        "Répond à « qu'est-ce que je peux semer en ce moment ? » : les cultures dont la fenêtre de semis en "
        "pépinière est ouverte ce mois-ci pour la zone du potager, avec ou sans graines en stock — le calcul de "
        "la Pépinière de l'application. Un mois vide le dit (« aucun semis ce mois-ci ») avec la prochaine "
        "ouverture. Lecture seule."
    ),
    proprietes={"date": {"type": "string", "description": "Date visée, ISO (AAAA-MM-JJ), au plus tard aujourd'hui ; "
                                                          "aujourd'hui par défaut."}},
    executer=_que_semer_ce_mois,
))
enregistrer_capacite(Capacite(
    nom="voir_mon_potager", titre="Que contient mon potager ?",
    description=(
        "Répond à « ai-je une serre, une pépinière chaude, une ville réglée ? » : la ville du potager (ou son "
        "absence et où la régler), sa zone climatique, ses parcelles, ses abris déclarés (voile, châssis, "
        "tunnel, serre) et ses pépinières (chaude ou froide). À lire AVANT de demander au jardinier ce que son "
        "potager contient. Lecture seule."
    ),
    executer=_voir_mon_potager,
))

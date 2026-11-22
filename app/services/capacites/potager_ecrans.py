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
from app.services import echeances_lots as svc_echeances
from app.services import plan as svc_plan
from app.services import potager_actif as svc_potager_actif
from app.services.capacites.lectures import _api, _appeler, _date_iso, _enveloppe, _texte
from app.services.capacites.registre import AppelCapacite, Capacite, RefusCapacite, enregistrer_capacite
from app.services.capacites.situation import resoudre_culture
from app.services.situation_culture import MOIS_NOMS
from database.models import CultureConfig, FamilleBotanique
from utils.culture_resolve import normaliser_culture
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


EXEMPLES_DE_FAMILLE = 3


def _cle_famille(nom: str) -> str:
    """« Brassicacées » et « Brassicacée » sont la même famille : sans accent, sans pluriel."""
    cle = normaliser_culture(nom)
    return cle[:-1] if cle.endswith("s") else cle


def exemples_de_famille(db: Session, potager_id, famille: str, exclus: list[str]) -> list[str]:
    """[CA1] Deux ou trois cultures du référentiel qui sont de cette famille, pour que « la famille des Brassicacées »
    parle au jardinier. Jamais une culture déjà citée à part ni deux fois la même (« chou » et « chou frisé »)."""
    ids = [f.id for f in db.query(FamilleBotanique).all() if _cle_famille(f.nom) == _cle_famille(famille)]
    if not ids:
        return []
    noms = sorted({n for (n,) in db.query(CultureConfig.nom).filter(
        CultureConfig.famille_id.in_(ids),
        (CultureConfig.potager_id == potager_id) | (CultureConfig.potager_id.is_(None))).all() if n})
    premiers = {normaliser_culture(e).split()[0] for e in exclus if e}
    exemples: list[str] = []
    for nom in noms:
        mot = normaliser_culture(nom).split()[0]
        if mot in premiers:
            continue
        premiers.add(mot)
        exemples.append(nom)
        if len(exemples) == EXEMPLES_DE_FAMILLE:
            break
    return exemples


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
        listes = listes_de_voisinage(fiche["associations"])
        for entree in listes["familles_a_eviter"] + listes["familles_favorables"]:
            deja = [c["nom"] for c in listes["a_eviter"] + listes["favorables"]] + [culture]
            entree["exemples"] = exemples_de_famille(db, appel.ctx.potager_id, entree["nom"], deja)
        sens = _texte(appel.arguments, "sens")
        if sens in ("a_eviter", "favorables"):  # la question ne porte que sur une liste : on ne rend que celle-là
            autre = "favorables" if sens == "a_eviter" else "a_eviter"
            listes.pop(autre), listes.pop(f"familles_{autre}")
            donnees["liste_demandee"] = sens
        donnees.update(listes)
        donnees["consigne"] = (
            "Ne cite que ces voisins : une culture absente de ces listes n'est pas dans la fiche. Une famille se dit "
            "comme famille, avec ses `exemples` (jamais une culture inventée). "
            + ("Réponds seulement à la liste demandée." if sens in ("a_eviter", "favorables")
               else "Donne les deux listes."))
    log.info("[US-351] voisinages_culture : %s → %d favorables, %d à éviter", culture,
             len(donnees.get("favorables", [])) + len(donnees.get("familles_favorables", [])),
             len(donnees.get("a_eviter", [])) + len(donnees.get("familles_a_eviter", [])))
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


NB_MOIS_SUITE = 6
#: Les gestes d'une saison précédente qui valent « habitude » : ceux des trois mois qui viennent.
MOIS_HABITUDES = 3
HABITUDES_MAX = 10


def _ouverts_ce_mois(fenetres: list[tuple[str, int, int]], mois: int) -> list[str]:
    return sorted({nom for nom, debut, fin in fenetres if mois in svc_calendrier.mois_couverts(debut, fin)})


def suite_du_calendrier(pepiniere: list[tuple[str, int, int]], pleine_terre: list[tuple[str, int, int]],
                        quand: date) -> list[dict]:
    """[CA2] Les mois qui viennent où une fenêtre de semis S'OUVRE, pour les deux phases : « sous abri » se lit en
    pépinière. Un mois sans ouverture n'est pas listé. Fonction pure."""
    suite = []
    for decalage in range(1, NB_MOIS_SUITE):
        numero = (quand.month - 1 + decalage) % 12 + 1
        ouvrent_p = sorted({n for n, debut, _ in pepiniere if debut == numero})
        ouvrent_t = sorted({n for n, debut, _ in pleine_terre if debut == numero})
        if ouvrent_p or ouvrent_t:
            suite.append({"mois": MOIS_NOMS[numero - 1], "en_pepiniere": ouvrent_p, "en_pleine_terre": ouvrent_t})
    return suite


def habitudes_de_saison(evenements: list[dict], quand: date) -> list[dict]:
    """[CA2] Ce que le jardinier a semé aux mêmes mois des saisons précédentes (le mois courant et les deux
    suivants) : une HABITUDE à citer comme telle, jamais un conseil. Un geste de ce mois-ci ne compte pas."""
    vues: dict[tuple[str, int], set[int]] = {}
    for e in evenements:
        try:
            jour = date.fromisoformat((e.get("date") or "")[:10])
        except ValueError:
            continue
        if (quand - jour).days <= 60 or (jour.month - quand.month) % 12 >= MOIS_HABITUDES or not e.get("culture"):
            continue
        vues.setdefault((e["culture"], jour.month), set()).add(jour.year)
    lignes = [{"culture": c, "mois": MOIS_NOMS[m - 1], "annees": sorted(a)} for (c, m), a in vues.items()]
    lignes.sort(key=lambda x: ((MOIS_NOMS.index(x["mois"]) - quand.month + 1) % 12, x["culture"]))
    return lignes[:HABITUDES_MAX]


def _liste(noms: list[str]) -> str:
    return ", ".join(noms[:8]) + (" …" if len(noms) > 8 else "")


def _texte_de_la_suite(suite: list[dict]) -> str:
    morceaux = []
    for m in suite:
        parties = ([f"en pépinière : {_liste(m['en_pepiniere'])}"] if m["en_pepiniere"] else []) + \
                  ([f"en pleine terre : {_liste(m['en_pleine_terre'])}"] if m["en_pleine_terre"] else [])
        morceaux.append(f"{m['mois']} ({' ; '.join(parties)})")
    return ("Ensuite, ça s'ouvre : " + " ; ".join(morceaux) + ".") if morceaux else ""


def _que_semer_ce_mois(db: Session, appel: AppelCapacite) -> dict:
    """[CA2] Ce qui se sème ce mois-ci : « Le bon moment pour semer » de la Pépinière (calcul de l'onglet Parcours),
    recoupé avec les fenêtres de semis en pleine terre de la même zone, puis la suite du calendrier et les habitudes
    du jardinier aux mêmes mois des saisons précédentes."""
    quand = _date_iso(appel.arguments, "date") or date.today()
    pepiniere = _appeler(_api().get_pepiniere_lots, date_ref=quand, potager_id=None, ctx=appel.ctx)
    reference = date.fromisoformat(pepiniere["date_ref_effective"])
    donnees = {"date": reference.isoformat(), **bon_moment_pour_semer(pepiniere["parcours"], reference),
               "source": "Pépinière de l'application, onglet Parcours, « Le bon moment pour semer », "
                         "recoupé avec les fenêtres de semis en pleine terre de la zone"}
    potager_id = appel.ctx.potager_id
    _, f_pepiniere = svc_echeances.fenetres_de_phase(db, potager_id, svc_calendrier.PHASE_SEMIS_PEPINIERE)
    _, f_terre = svc_echeances.fenetres_de_phase(db, potager_id, svc_calendrier.PHASE_SEMIS_PLEINE_TERRE)
    en_terre = _ouverts_ce_mois(f_terre, reference.month)
    suite = suite_du_calendrier(f_pepiniere, f_terre, reference)
    donnees.update({"a_semer_pleine_terre": en_terre, "suite_du_calendrier": suite})
    rien_en_pepiniere = not (donnees["a_semer"] or donnees["a_semer_sans_graines"])
    if rien_en_pepiniere and not en_terre:
        donnees["texte"] = ("Aucun semis ce mois-ci, ni en pépinière ni en pleine terre. "
                            + _texte_de_la_suite(suite)).strip()
    elif rien_en_pepiniere:
        donnees["texte"] = f"Rien à semer en pépinière ce mois-ci. En pleine terre : {_liste(en_terre)}."
    elif en_terre:
        donnees["texte"] += f" En pleine terre : {_liste(en_terre)}."
    anterieurs = _appeler(
        _api().historique, limit=100, offset=0, action="semis", culture=None, parcelle=None,
        from_date=date(reference.year - 2, 1, 1).isoformat(), to_date=reference.isoformat(),
        date_ref=None, potager_id=None, ctx=appel.ctx)["evenements"]
    donnees["habitudes"] = habitudes_de_saison(anterieurs, reference)
    donnees["consigne"] = (
        "Réponds d'après `texte`, `suite_du_calendrier` et `habitudes` seulement : aucune culture que ces champs "
        "n'ouvrent. Les `habitudes` sont ce que le jardinier a semé les saisons précédentes à ces mois : dis-le comme "
        "une habitude, jamais comme un conseil, et seulement s'il y en a. Ne propose ni rappel ni geste non demandé.")
    if reference != quand:
        donnees["note"] = "La Pépinière se lit au plus tard aujourd'hui : la date demandée a été ramenée à aujourd'hui."
    log.info("[US-351] que_semer_ce_mois : %s → %d à semer en pépinière, %d en pleine terre, %d habitudes", reference,
             len(donnees["a_semer"]), len(en_terre), len(donnees["habitudes"]))
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
    donnees["consigne"] = (
        "Une serre ou un abri se lit ICI, jamais en le demandant au jardinier ni en le supposant. S'il n'y en a pas, "
        "dis où le déclarer (`reglage_abri`). La ville n'a rien à voir avec la serre. Le référentiel des cultures ne "
        "couvre pas la culture sous serre chauffée : dis-le au lieu de donner des dates.")
    log.info("[US-351] voir_mon_potager : potager %s ville=%s abris=%d pépinières=%d", appel.ctx.potager_id,
             "oui" if ville else "non", len(abris), len(pepinieres))
    return _enveloppe(donnees)


# ── Déclarations ──────────────────────────────────────────────────────────────
enregistrer_capacite(Capacite(
    nom="voisinages_culture", titre="Quels voisins pour cette culture ?",
    description=(
        "Répond à « que planter à côté de telle culture, quoi éviter ? » : les associations de la fiche culture de "
        "l'application, en deux listes (favorables, à éviter), cultures et familles botaniques séparées, avec leur "
        "niveau de preuve ; une famille vient avec des exemples de cultures. Une culture sans association connue "
        "le dit. Ne cite jamais un voisin absent de ces listes. Si la question ne porte que sur une liste (« quoi "
        "éviter ? », « qui lui fait du bien ? »), passe `sens`. Lecture seule."
    ),
    proprietes={
        "culture": {"type": "string", "description": "La culture, comme le jardinier l'a dite."},
        "sens": {"type": "string", "enum": ["a_eviter", "favorables"],
                 "description": "Seulement si la question ne porte que sur les voisins à éviter ou que sur les favorables."},
    },
    requis=("culture",), executer=_voisinages_culture,
))
enregistrer_capacite(Capacite(
    nom="que_semer_ce_mois", titre="Que semer ce mois-ci ?",
    description=(
        "Répond à « qu'est-ce que je peux semer en ce moment ? » : les cultures dont la fenêtre de semis est "
        "ouverte ce mois-ci pour la zone du potager, en pépinière (le calcul de la Pépinière de l'application, avec "
        "ou sans graines en stock) et en pleine terre. Un mois vide le dit (« aucun semis ce mois-ci ») avec les "
        "mois où ça s'ouvre ensuite, et ce que le jardinier a semé aux mêmes mois les saisons précédentes. "
        "Lecture seule."
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
        "tunnel, serre) et ses pépinières (chaude ou froide). À appeler dès que le jardinier parle de serre, "
        "d'abri, de châssis ou de pépinière chaude, et AVANT de lui demander ce que son potager contient. "
        "Lecture seule."
    ),
    executer=_voir_mon_potager,
))

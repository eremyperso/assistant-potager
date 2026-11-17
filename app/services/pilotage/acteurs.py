"""
app/services/pilotage/acteurs.py — La vue « Potagers et jardiniers » de la PWA d'administration [US-319]
=======================================================================================================
Qui consomme quoi : les mêmes mesures que les autres vues, ventilées par potager et par jardinier, avec
les potagers et les comptes qui n'ont jamais appelé l'assistant (une information d'adoption).

Tout se lit par `agregats` (`_agreger`, `_filtrer`, `_executer`, `serie`, `ventilation`, `echanges`) : mêmes
filtres, mêmes provenances par défaut (`usage` et `fond`), même chemin de lecture hors périmètre de potager
[US-310]. Les tables `potagers`, `potager_membres` et `users` ne sont lues que pour le nom d'un potager,
l'adresse e-mail d'un compte, un rôle, un décompte et une date d'inscription : jamais un contenu de
message, jamais une donnée de culture [CA10].

Définitions (affichées par l'écran, testées ici) :
- **Actif** [CA3] : au moins une ligne de provenance `usage` sur la période, quelle que soit la provenance
  demandée (même définition que la vue « Coût »).
- **Usage élevé** [CA7] : un potager ou un jardinier actif dont le coût de la période dépasse
  `FACTEUR_USAGE_ELEVE` fois la médiane des coûts des actifs de même nature. Valeur de départ, à valider.
- **Tâches automatiques** [CA8] : les appels de fond (sans utilisateur) restent rattachés à leur potager ;
  dans la vue par jardinier, ils forment une ligne à part.
"""
from __future__ import annotations

import math
from dataclasses import replace
from datetime import date
from typing import Optional

from sqlalchemy import func

from database.models import ConsoTokens, Potager, PotagerMembre, User
from llm import contexte_appel
from . import agregats
from .agregats import Filtres, _Cumul, _executer, _filtrer, percentile

#: [CA7] « Trois fois la médiane » : une valeur de départ, à valider sur les données réelles.
FACTEUR_USAGE_ELEVE = 3
REGLE_USAGE_ELEVE = (
    "Usage élevé : coût de la période supérieur à 3 fois la médiane des coûts des actifs de même nature "
    "(valeur de départ, à valider sur les données réelles)."
)
TACHES_AUTOMATIQUES = "Tâches automatiques"
ISSUE_OK = "ok"


# ─────────────────────────────────────────────────────────────────────────────
# Briques
# ─────────────────────────────────────────────────────────────────────────────

def _taux_echec(cumul: _Cumul) -> Optional[float]:
    """Appels dont l'issue n'est pas `ok` ÷ tous les appels ; `None` sans appel."""
    if not cumul.appels:
        return None
    return 1 - cumul.issues.get(ISSUE_OK, 0) / cumul.appels


def _actifs(db, filtres: Filtres, colonne) -> set[int]:
    """[CA3] Les identifiants (potager ou utilisateur) ayant au moins une ligne `usage` sur la période."""
    usage = replace(filtres, provenances=(contexte_appel.PROVENANCE_USAGE,))
    requete = _filtrer(db.query(colonne), usage).filter(colonne.isnot(None)).distinct()
    return {int(ligne[0]) for ligne in _executer(db, requete)}


def _derniers_appels(db, filtres: Filtres, colonne) -> dict[int, date]:
    requete = _filtrer(db.query(colonne, func.max(ConsoTokens.date)), filtres).group_by(colonne)
    return {int(cle): jour for cle, jour in _executer(db, requete) if cle is not None}


def _usage_eleve(couts: dict[int, Optional[int]], actifs: set[int]) -> tuple[Optional[float], set[int]]:
    """[CA7] La médiane des coûts des actifs et ceux qui la dépassent de plus de 3 fois."""
    chiffres = [c for i, c in couts.items() if i in actifs and c is not None]
    mediane = percentile(chiffres, 0.5)
    if mediane is None or mediane <= 0:
        return mediane, set()
    return mediane, {i for i, c in couts.items() if i in actifs and c is not None and c > FACTEUR_USAGE_ELEVE * mediane}


def _mesures(cumul: _Cumul, nb_echanges: int, canaux: list[str], dernier: Optional[date], total_cout: int) -> dict:
    cout = cumul.cout_micro_eur
    return {
        "appels": cumul.appels,
        "echanges": nb_echanges,
        "jetons_entree": cumul.jetons_entree,
        "jetons_sortie": cumul.jetons_sortie,
        "cout_micro_eur": cout,
        "part_cout": (cout / total_cout) if (cout is not None and total_cout) else None,
        "canaux": canaux,
        "taux_echec": _taux_echec(cumul),
        "dernier_appel": dernier.isoformat() if dernier else None,
    }


def _par_cle(db, filtres: Filtres, colonne) -> tuple[dict, dict, dict, dict]:
    """Pour une colonne (`potager_id` ou `user_id`) : cumuls, échanges, canaux et dernier appel par valeur."""
    cumuls = {c[0]: v for c, v in agregats._agreger(db, filtres, [colonne]).items()}
    echanges: dict = {}
    for (cle, echange), _ in agregats._agreger(db, filtres, [colonne, ConsoTokens.echange_ref]).items():
        if echange:
            echanges[cle] = echanges.get(cle, 0) + 1
    canaux: dict = {}
    for (cle, canal), _ in agregats._agreger(db, filtres, [colonne, ConsoTokens.canal]).items():
        canaux.setdefault(cle, []).append(canal)
    dernier = _derniers_appels(db, filtres, colonne)
    return cumuls, echanges, {k: sorted(v) for k, v in canaux.items()}, dernier


def _ordre(lignes: list[dict]) -> list[dict]:
    """Par coût décroissant (les non chiffrés après), puis appels, puis libellé."""
    return sorted(lignes, key=lambda l: (-(l["cout_micro_eur"] if l["cout_micro_eur"] is not None else -1), -l["appels"], l["libelle"]))


# ─────────────────────────────────────────────────────────────────────────────
# CA1, CA2, CA3, CA7, CA8 — les listes et le bandeau
# ─────────────────────────────────────────────────────────────────────────────

def _lignes_potagers(db, filtres: Filtres) -> tuple[list[dict], set[int], Optional[float]]:
    cumuls, echanges, canaux, dernier = _par_cle(db, filtres, ConsoTokens.potager_id)
    total_cout = sum(c.cout for c in cumuls.values())
    membres = {int(p): int(n) for p, n in db.query(PotagerMembre.potager_id, func.count()).group_by(PotagerMembre.potager_id).all()}
    potagers = db.query(Potager.id, Potager.nom).filter(Potager.etat != "supprime").all()
    actifs = _actifs(db, filtres, ConsoTokens.potager_id)
    couts = {int(i): (cumuls[i].cout_micro_eur if i in cumuls else None) for i, _ in potagers}
    mediane, eleves = _usage_eleve(couts, actifs)
    lignes = []
    for pid, nom in potagers:
        pid = int(pid)
        cumul = cumuls.get(pid) or _Cumul()
        lignes.append({
            "id": pid, "libelle": nom, "membres": membres.get(pid, 0), "actif": pid in actifs, "usage_eleve": pid in eleves,
            **_mesures(cumul, echanges.get(pid, 0), canaux.get(pid, []), dernier.get(pid), total_cout),
        })
    return _ordre(lignes), actifs, mediane


def _libelle_compte(email: Optional[str], uid: int) -> str:
    return email or f"Compte sans e-mail (n° {uid})"


def _lignes_utilisateurs(db, filtres: Filtres) -> tuple[list[dict], set[int], Optional[float]]:
    cumuls, echanges, canaux, dernier = _par_cle(db, filtres, ConsoTokens.user_id)
    total_cout = sum(c.cout for c in cumuls.values())
    nb_potagers = {int(u): int(n) for u, n in db.query(PotagerMembre.user_id, func.count()).group_by(PotagerMembre.user_id).all()}
    comptes = db.query(User.id, User.email, User.cree_le).all()
    actifs = _actifs(db, filtres, ConsoTokens.user_id)
    couts = {int(i): (cumuls[i].cout_micro_eur if i in cumuls else None) for i, _, _ in comptes}
    mediane, eleves = _usage_eleve(couts, actifs)
    lignes = []
    for uid, email, cree_le in comptes:
        uid = int(uid)
        cumul = cumuls.get(uid) or _Cumul()
        lignes.append({
            "id": uid, "libelle": _libelle_compte(email, uid), "potagers": nb_potagers.get(uid, 0),
            "inscrit_le": cree_le.date().isoformat() if cree_le else None,
            "actif": uid in actifs, "usage_eleve": uid in eleves, "automatique": False,
            **_mesures(cumul, echanges.get(uid, 0), canaux.get(uid, []), dernier.get(uid), total_cout),
        })
    if None in cumuls:  # [CA8] les appels de fond : une ligne à part, jamais un jardinier
        lignes.append({
            "id": None, "libelle": TACHES_AUTOMATIQUES, "potagers": None, "inscrit_le": None,
            "actif": False, "usage_eleve": False, "automatique": True,
            **_mesures(cumuls[None], echanges.get(None, 0), canaux.get(None, []), dernier.get(None), total_cout),
        })
    return _ordre(lignes), actifs, mediane


def _part_premier_decile(couts: list[int]) -> Optional[float]:
    """[CA3] La part du coût portée par le premier décile des jardiniers actifs (au moins un)."""
    total = sum(couts)
    if not couts or total <= 0:
        return None
    haut = max(1, math.ceil(len(couts) / 10))
    return sum(sorted(couts, reverse=True)[:haut]) / total


def _bandeau(db, filtres: Filtres, lignes_p: list[dict], actifs_p: set[int], lignes_u: list[dict], actifs_u: set[int]) -> dict:
    couts = [l["cout_micro_eur"] or 0 for l in lignes_u if l["actif"]]
    chiffres = [l["cout_micro_eur"] for l in lignes_u if l["actif"] and l["cout_micro_eur"] is not None]
    return {
        "potagers_existants": len(lignes_p),
        "potagers_actifs": len(actifs_p & {l["id"] for l in lignes_p}),
        "jardiniers_inscrits": len([l for l in lignes_u if not l["automatique"]]),
        "jardiniers_actifs": len(actifs_u),
        "cout_median_par_jardinier_micro_eur": percentile(chiffres, 0.5),
        "cout_p95_par_jardinier_micro_eur": percentile(chiffres, 0.95),
        "part_cout_premier_decile": _part_premier_decile(couts),
        "facteur_usage_eleve": FACTEUR_USAGE_ELEVE,
        "regle_usage_eleve": REGLE_USAGE_ELEVE,
    }


def _contexte(db, filtres: Filtres) -> tuple[list[dict], set[int], Optional[float], list[dict], set[int], Optional[float]]:
    lp, ap, mp = _lignes_potagers(db, filtres)
    lu, au, mu = _lignes_utilisateurs(db, filtres)
    return lp, ap, mp, lu, au, mu


def potagers(db, filtres: Filtres) -> dict:
    """[CA1, CA3, CA7, CA8, CA9] Tous les potagers (ceux sans appel à zéro), le bandeau, la règle d'usage élevé."""
    lp, ap, mp, lu, au, _ = _contexte(db, filtres)
    return {
        "periode": filtres.vers_dict(), "bandeau": _bandeau(db, filtres, lp, ap, lu, au),
        "mediane_cout_micro_eur": mp, "lignes": lp,
    }


def utilisateurs(db, filtres: Filtres) -> dict:
    """[CA2, CA3, CA7, CA8, CA9] Tous les comptes (ceux sans appel à zéro) et la ligne « tâches automatiques »."""
    lp, ap, _, lu, au, mu = _contexte(db, filtres)
    return {
        "periode": filtres.vers_dict(), "bandeau": _bandeau(db, filtres, lp, ap, lu, au),
        "mediane_cout_micro_eur": mu, "lignes": lu,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CA5, CA6 — les fiches
# ─────────────────────────────────────────────────────────────────────────────

def _graphique(db, filtres: Filtres) -> dict:
    appels = agregats.serie(db, filtres, mesure="appels")
    cout = agregats.serie(db, filtres, mesure="cout_micro_eur")
    return {"pas": appels["pas"], "points": appels["points"], "appels": appels["total"], "cout_micro_eur": cout["total"]}


def _repartition(db, filtres: Filtres, dimension: str) -> list[dict]:
    lignes = agregats.ventilation(db, filtres, dimension, mesure="cout_micro_eur", limite=200)["lignes"]
    return [
        {"cle": l["cle"], "libelle": l["libelle"], "appels": l["appels"], "cout_micro_eur": l["cout_micro_eur"], "part": l["part"]}
        for l in lignes
    ]


def _issues(db, filtres: Filtres) -> dict:
    cumul = agregats._agreger(db, filtres).get(()) or _Cumul()
    return dict(sorted(cumul.issues.items()))


def _commun(db, filtres: Filtres) -> dict:
    echanges = agregats.echanges(db, filtres)
    return {
        "graphique": _graphique(db, filtres),
        "par_type": _repartition(db, filtres, "appel_type"),
        "par_canal": _repartition(db, filtres, "canal"),
        "echange": {"nb": echanges["nb_echanges"], "cout_micro_eur": echanges["cout_micro_eur"], "appels": echanges["appels"]},
        "issues": _issues(db, filtres),
    }


def _part(valeur: Optional[int], total: Optional[int], appels: int, total_appels: int) -> Optional[float]:
    """Part de la consommation : en coût quand il est connu, en appels sinon."""
    if valeur is not None and total:
        return valeur / total
    return (appels / total_appels) if total_appels else None


def fiche_potager(db, filtres: Filtres, potager_id: int) -> Optional[dict]:
    """[CA5, CA8] La fiche d'un potager : séries, répartitions, coût d'un échange, issues, membres et leur part."""
    ligne = next((l for l in _lignes_potagers(db, filtres)[0] if l["id"] == potager_id), None)
    if ligne is None:
        return None
    f = replace(filtres, potager_id=potager_id)
    cumuls = {c[0]: v for c, v in agregats._agreger(db, f, [ConsoTokens.user_id]).items()}
    total_cout, total_appels = ligne["cout_micro_eur"], ligne["appels"]
    membres = []
    roles = db.query(PotagerMembre.user_id, PotagerMembre.role, User.email).join(User, User.id == PotagerMembre.user_id) \
        .filter(PotagerMembre.potager_id == potager_id).all()
    for uid, role, email in roles:
        cumul = cumuls.get(int(uid)) or _Cumul()
        membres.append({
            "id": int(uid), "libelle": _libelle_compte(email, int(uid)), "role": role, "automatique": False,
            "appels": cumul.appels, "cout_micro_eur": cumul.cout_micro_eur,
            "part": _part(cumul.cout_micro_eur, total_cout, cumul.appels, total_appels),
        })
    if None in cumuls:  # [CA8]
        cumul = cumuls[None]
        membres.append({
            "id": None, "libelle": TACHES_AUTOMATIQUES, "role": None, "automatique": True, "appels": cumul.appels,
            "cout_micro_eur": cumul.cout_micro_eur, "part": _part(cumul.cout_micro_eur, total_cout, cumul.appels, total_appels),
        })
    membres.sort(key=lambda m: (-(m["cout_micro_eur"] or 0), -m["appels"], m["libelle"]))
    return {"periode": filtres.vers_dict(), "potager": ligne, "membres": membres, **_commun(db, f)}


def fiche_utilisateur(db, filtres: Filtres, user_id: int) -> Optional[dict]:
    """[CA6] La fiche d'un jardinier : les mêmes éléments, répartis entre ses potagers."""
    ligne = next((l for l in _lignes_utilisateurs(db, filtres)[0] if l["id"] == user_id), None)
    if ligne is None:
        return None
    f = replace(filtres, user_id=user_id)
    cumuls = {c[0]: v for c, v in agregats._agreger(db, f, [ConsoTokens.potager_id]).items()}
    noms = {int(i): nom for i, nom in db.query(Potager.id, Potager.nom).all()}
    roles = {int(p): r for p, r in db.query(PotagerMembre.potager_id, PotagerMembre.role).filter(PotagerMembre.user_id == user_id).all()}
    total_cout, total_appels = ligne["cout_micro_eur"], ligne["appels"]
    repartis = []
    for pid in sorted(set(roles) | {c for c in cumuls if c is not None}):
        cumul = cumuls.get(pid) or _Cumul()
        repartis.append({
            "id": pid, "libelle": noms.get(pid, f"Potager n° {pid}"), "role": roles.get(pid),
            "appels": cumul.appels, "cout_micro_eur": cumul.cout_micro_eur,
            "part": _part(cumul.cout_micro_eur, total_cout, cumul.appels, total_appels),
        })
    repartis.sort(key=lambda m: (-(m["cout_micro_eur"] or 0), -m["appels"], m["libelle"]))
    return {"periode": filtres.vers_dict(), "utilisateur": ligne, "potagers": repartis, **_commun(db, f)}

"""
app/services/pilotage/cout.py — La vue « Coût » de la PWA d'administration [US-313]
==================================================================================
Ce que coûte l'assistant : la période, le mois en cours, la projection de fin de mois, le coût par
jardinier actif, ce que coûte UN échange par canal, et ce que ce coût laisse comme marge sur un
abonnement. Les montants viennent de `conso_tokens.cout_micro_eur` (US-309), au tarif public
(décision D6) ; rien n'est recalculé ici que des sommes et des percentiles, par `agregats`.

Définitions (affichées par l'écran, testées ici) :
- **Jardinier actif** [CA2] : un utilisateur qui a au moins une ligne de provenance `usage` sur la
  période (et sur les autres filtres : canal, modèle, type, potager). La provenance demandée ne
  change pas cette définition.
- **Mois en cours** [CA1] : du 1er du mois d'`aujourd_hui` à `aujourd_hui`, mêmes filtres que la
  période hors dates.
- **Projection de fin de mois** [CA1] : coût du mois à ce jour + moyenne quotidienne des 7 derniers
  jours × jours restants du mois.
- **Coût mensuel d'un jardinier** [CA6] : son coût sur la période ramené à 30 jours.
"""
from __future__ import annotations

import calendar
from dataclasses import replace
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import func

from database.models import ConsoTokens
from llm import contexte_appel
from . import agregats
from .agregats import Filtres, _Cumul, _distribution, _executer, _filtrer

#: Une durée de référence pour comparer des périodes de longueurs différentes à un abonnement mensuel.
JOURS_PAR_MOIS_DE_REFERENCE = 30
#: Fenêtre de la moyenne qui prolonge le mois.
JOURS_DE_PROJECTION = 7


def _aujourd_hui() -> date:
    """Le jour de référence du mois en cours et de la projection ; un seul point à figer pour un test."""
    return date.today()


def _cout(db, filtres: Filtres) -> _Cumul:
    return agregats._agreger(db, filtres).get(()) or _Cumul()


def _jardiniers_actifs(db, filtres: Filtres) -> list[int]:
    """[CA2] Les utilisateurs ayant au moins une ligne `usage` sur la période."""
    usage = replace(filtres, provenances=(contexte_appel.PROVENANCE_USAGE,))
    requete = _filtrer(db.query(ConsoTokens.user_id), usage).filter(ConsoTokens.user_id.isnot(None)).distinct()
    return sorted(int(ligne[0]) for ligne in _executer(db, requete))


def _modeles_non_chiffres(db, filtres: Filtres) -> list[dict]:
    """[CA7] Les modèles dont des lignes n'ont pas de coût (absents de la grille tarifaire)."""
    requete = (
        _filtrer(db.query(ConsoTokens.modele, func.count()), filtres)
        .filter(ConsoTokens.cout_micro_eur.is_(None))
        .group_by(ConsoTokens.modele)
    )
    lignes = [{"modele": m, "appels": int(n)} for m, n in _executer(db, requete)]
    return sorted(lignes, key=lambda l: (-l["appels"], l["modele"]))


def _version_de_grille(db, filtres: Filtres) -> dict:
    """[CA8] La version de grille tarifaire qui a chiffré le plus de lignes de la période."""
    requete = (
        _filtrer(db.query(ConsoTokens.tarif_version, func.count()), filtres)
        .filter(ConsoTokens.tarif_version.isnot(None))
        .group_by(ConsoTokens.tarif_version)
    )
    versions = {v: int(n) for v, n in _executer(db, requete)}
    dominante = min(versions, key=lambda v: (-versions[v], v)) if versions else None
    return {"tarif_version": dominante, "versions_tarif": dict(sorted(versions.items()))}


def _par_jardinier(db, filtres: Filtres, actifs: list[int]) -> dict:
    """[CA6] Le coût de chaque jardinier actif sur la période : médiane, P95, maximum — et la même
    distribution ramenée à 30 jours. Un jardinier actif sans ligne chiffrée compte pour 0."""
    groupes = agregats._agreger(db, filtres, [ConsoTokens.user_id])
    par_utilisateur = {cle[0]: c.cout for cle, c in groupes.items() if cle[0] in set(actifs)}
    couts = [par_utilisateur.get(u, 0) for u in actifs]
    reference = JOURS_PAR_MOIS_DE_REFERENCE / filtres.jours
    mensuels = [c * reference for c in couts]
    return {
        "nb": len(actifs),
        "periode": _distribution(couts),
        "mensuel": _distribution(mensuels),
    }


def _echanges_par_canal(db, filtres: Filtres) -> list[dict]:
    """[CA4] Ce que coûte UNE réponse, par canal : coût (médiane, P95, maximum) et nombre d'appels
    par échange (médiane, P95, maximum). Les lignes sans échange (avant v74) n'y entrent pas."""
    groupes = agregats._agreger(db, filtres, [ConsoTokens.canal, ConsoTokens.echange_ref])
    par_canal: dict[str, list[_Cumul]] = {}
    for (canal, echange), cumul in groupes.items():
        if echange:
            par_canal.setdefault(canal, []).append(cumul)
    lignes = []
    for canal, cumuls in par_canal.items():
        couts = [c.cout_micro_eur for c in cumuls if c.cout_micro_eur is not None]
        lignes.append({
            "canal": canal,
            "nb_echanges": len(cumuls),
            "echanges_non_chiffres": len(cumuls) - len(couts),
            "cout_micro_eur": _distribution(couts),
            "appels": _distribution([c.appels for c in cumuls]),
        })
    return sorted(lignes, key=lambda l: (-l["nb_echanges"], l["canal"]))


def _fenetre_du_mois(filtres: Filtres, aujourd_hui: date) -> Filtres:
    return replace(filtres, depuis=aujourd_hui.replace(day=1), jusqu_a=aujourd_hui)


def _projection(cout_mois: Optional[int], cout_7_jours: Optional[int], aujourd_hui: date) -> Optional[int]:
    """[CA1] Coût du mois à ce jour + moyenne quotidienne des 7 derniers jours × jours restants."""
    if cout_mois is None:
        return None
    jours_du_mois = calendar.monthrange(aujourd_hui.year, aujourd_hui.month)[1]
    restants = jours_du_mois - aujourd_hui.day
    moyenne = (cout_7_jours or 0) / JOURS_DE_PROJECTION
    return int(round(cout_mois + moyenne * restants))


def cout(db, filtres: Filtres, aujourd_hui: Optional[date] = None) -> dict:
    """[CA1, CA2, CA4, CA6, CA7, CA8] Tout ce que la vue « Coût » lit hors graphique et classement
    (qui sont les routes `series` et `ventilation`, mesure `cout_micro_eur`)."""
    aujourd_hui = aujourd_hui or _aujourd_hui()
    periode = _cout(db, filtres)
    actifs = _jardiniers_actifs(db, filtres)

    mois = _cout(db, _fenetre_du_mois(filtres, aujourd_hui))
    sept_jours = _cout(db, replace(filtres, depuis=aujourd_hui - timedelta(days=JOURS_DE_PROJECTION - 1), jusqu_a=aujourd_hui))

    cout_periode = periode.cout_micro_eur
    par_actif = int(round(cout_periode / len(actifs))) if (cout_periode is not None and actifs) else None
    return {
        "periode": filtres.vers_dict(),
        "appels": periode.appels,
        "cout_micro_eur": cout_periode,
        "mois": {
            "depuis": aujourd_hui.replace(day=1).isoformat(),
            "jusqu_a": aujourd_hui.isoformat(),
            "cout_micro_eur": mois.cout_micro_eur,
            "projection_fin_de_mois_micro_eur": _projection(mois.cout_micro_eur, sept_jours.cout_micro_eur, aujourd_hui),
            "cout_7_jours_micro_eur": sept_jours.cout_micro_eur,
        },
        "jardiniers_actifs": len(actifs),
        "cout_par_jardinier_actif_micro_eur": par_actif,
        "par_jardinier": _par_jardinier(db, filtres, actifs),
        "echanges_par_canal": _echanges_par_canal(db, filtres),
        "lignes_non_chiffrees": periode.appels - periode.lignes_chiffrees,
        "modeles_non_chiffres": _modeles_non_chiffres(db, filtres),
        **_version_de_grille(db, filtres),
    }

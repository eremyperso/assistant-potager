"""
app/services/pilotage/fiabilite.py — La vue « Fiabilité » de la PWA d'administration [US-314]
============================================================================================
Ce que le jardinier subit : échecs, quotas atteints, latences, par modèle et par type d'appel.
Les issues viennent de `conso_tokens.issue` : `ok`, `quota`, `erreur`, `delai`, `voix_inconnue`, et
toute valeur que la passerelle ajouterait un jour — elle est comptée et rendue telle quelle, jamais
écartée parce que l'écran ne la connaît pas [CA2].

Définitions (affichées par l'écran, testées ici) :
- **Taux de succès / de quota / d'erreur** : appels d'une issue ÷ tous les appels du périmètre.
  Une issue autre (`voix_inconnue`, `delai`…) compte au dénominateur, jamais au numérateur d'un succès.
- **Latence** [CA7] : médiane et P95 des seuls appels réussis. La latence des échecs est rendue à part
  (`latence_echecs_*`) : un quota qui répond en 2 s ne doit pas tirer vers le bas la latence du service.
- Aucun contenu de message n'existe dans `conso_tokens`, donc aucune liste ne peut en rendre [CA6].
"""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from typing import Optional

from database.models import ConsoTokens
from llm.passerelle import ISSUE_ERREUR, ISSUE_OK, ISSUE_QUOTA
from .agregats import Filtres, _executer, _filtrer, percentile

#: [CA6] Combien d'échecs récents la liste rend.
NB_DERNIERS_ECHECS = 20
#: [CA5] La grille heure × jour couvre ce nombre de jours, jusqu'au dernier jour de la période.
JOURS_DE_LA_GRILLE = 7

ISSUES_CONNUES = (ISSUE_OK, ISSUE_QUOTA, ISSUE_ERREUR, "delai")


class _Groupe:
    """Les appels d'un groupe : décomptes par issue et latences (succès / échecs séparées)."""
    __slots__ = ("issues", "latences_succes", "latences_echecs")

    def __init__(self) -> None:
        self.issues: dict[str, int] = {}
        self.latences_succes: list[int] = []
        self.latences_echecs: list[int] = []

    def ajouter(self, issue: str, latence_ms: Optional[int]) -> None:
        self.issues[issue] = self.issues.get(issue, 0) + 1
        (self.latences_succes if issue == ISSUE_OK else self.latences_echecs).append(latence_ms or 0)

    @property
    def appels(self) -> int:
        return sum(self.issues.values())

    def vers_dict(self) -> dict:
        n = self.appels
        succes = self.issues.get(ISSUE_OK, 0)
        quota = self.issues.get(ISSUE_QUOTA, 0)
        erreur = self.issues.get(ISSUE_ERREUR, 0)
        delai = self.issues.get("delai", 0)
        autres = {i: c for i, c in sorted(self.issues.items()) if i not in ISSUES_CONNUES}
        return {
            "appels": n,
            "succes": succes,
            "quota": quota,
            "erreur": erreur,
            "delai": delai,
            "autres": autres,
            "issues": dict(sorted(self.issues.items())),
            "taux_succes": (succes / n) if n else None,
            "taux_quota": (quota / n) if n else None,
            "taux_erreur": (erreur / n) if n else None,
            "latence_p50_ms": percentile(self.latences_succes, 0.5),
            "latence_p95_ms": percentile(self.latences_succes, 0.95),
            "latence_echecs_p50_ms": percentile(self.latences_echecs, 0.5),
            "latence_echecs_p95_ms": percentile(self.latences_echecs, 0.95),
        }


def _bilan(db, filtres: Filtres) -> dict:
    """Le périmètre entier, puis par modèle et par type d'appel — en une seule lecture, pour que les
    trois découpages soient cohérents à l'appel près."""
    requete = _filtrer(
        db.query(ConsoTokens.modele, ConsoTokens.appel_type, ConsoTokens.issue, ConsoTokens.latence_ms),
        filtres,
    )
    total = _Groupe()
    par_modele: dict[str, _Groupe] = {}
    par_type: dict[str, _Groupe] = {}
    for modele, appel_type, issue, latence in _executer(db, requete):
        total.ajouter(issue, latence)
        par_modele.setdefault(modele, _Groupe()).ajouter(issue, latence)
        par_type.setdefault(appel_type, _Groupe()).ajouter(issue, latence)

    def lignes(groupes: dict[str, _Groupe]) -> list[dict]:
        rendu = [{"cle": cle, **g.vers_dict()} for cle, g in groupes.items()]
        return sorted(rendu, key=lambda l: (-l["appels"], str(l["cle"])))

    return {"mesures": total.vers_dict(), "par_modele": lignes(par_modele), "par_type": lignes(par_type)}


def _grille_quota(db, filtres: Filtres) -> dict:
    """[CA5] Le nombre d'appels en `quota`, par modèle, heure × jour, sur les 7 derniers jours de la
    période. `cellules[j][h]` : le jour `jours[j]`, l'heure `h` (0-23). Les filtres s'appliquent."""
    fin = filtres.jusqu_a
    debut = fin - timedelta(days=JOURS_DE_LA_GRILLE - 1)
    jours = [(debut + timedelta(days=i)).isoformat() for i in range(JOURS_DE_LA_GRILLE)]
    requete = _filtrer(
        db.query(ConsoTokens.modele, ConsoTokens.date, ConsoTokens.cree_le),
        replace(filtres, depuis=debut, jusqu_a=fin),
    ).filter(ConsoTokens.issue == ISSUE_QUOTA)

    modeles: dict[str, list[list[int]]] = {}
    for modele, jour, cree_le in _executer(db, requete):
        cellules = modeles.setdefault(modele, [[0] * 24 for _ in jours])
        # La date d'imputation place le jour ; l'heure se lit sur l'horodatage de l'appel.
        cellules[(jour - debut).days][cree_le.hour if cree_le else 0] += 1

    rendus = [
        {"modele": m, "total": sum(sum(j) for j in c), "maximum": max(max(j) for j in c), "cellules": c}
        for m, c in modeles.items()
    ]
    rendus.sort(key=lambda r: (-r["total"], r["modele"]))
    return {"depuis": debut.isoformat(), "jusqu_a": fin.isoformat(), "jours": jours, "modeles": rendus}


def _derniers_echecs(db, filtres: Filtres) -> list[dict]:
    """[CA6] Les derniers appels en échec (toute issue autre que `ok`) : heure, type, modèle, issue,
    canal, latence. Jamais de contenu de message."""
    requete = (
        _filtrer(
            db.query(
                ConsoTokens.cree_le, ConsoTokens.date, ConsoTokens.appel_type, ConsoTokens.modele,
                ConsoTokens.issue, ConsoTokens.canal, ConsoTokens.latence_ms,
            ),
            filtres,
        )
        .filter(ConsoTokens.issue != ISSUE_OK)
        .order_by(ConsoTokens.cree_le.desc(), ConsoTokens.id.desc())
        .limit(NB_DERNIERS_ECHECS)
    )
    return [
        {
            "cree_le": cree_le.isoformat() if cree_le else None,
            "date": jour.isoformat(),
            "appel_type": appel_type,
            "modele": modele,
            "issue": issue,
            "canal": canal,
            "latence_ms": latence,
        }
        for cree_le, jour, appel_type, modele, issue, canal, latence in _executer(db, requete)
    ]


def fiabilite(db, filtres: Filtres) -> dict:
    """[CA1, CA3, CA4, CA5, CA6, CA7, CA8] Tout ce que la vue « Fiabilité » lit hors graphique par jour
    (la route `series`, mesure `appels`, dimension `issue`, qui rend toute issue présente en base)."""
    actuel = _bilan(db, filtres)
    precedent = _bilan(db, filtres.periode_precedente())
    return {
        "periode": filtres.vers_dict(),
        "mesures": actuel["mesures"],
        "periode_precedente": filtres.periode_precedente().vers_dict(),
        "mesures_precedentes": precedent["mesures"],
        "par_modele": actuel["par_modele"],
        "par_type": actuel["par_type"],
        "grille_quota": _grille_quota(db, filtres),
        "derniers_echecs": _derniers_echecs(db, filtres),
    }

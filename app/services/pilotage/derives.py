"""
app/services/pilotage/derives.py — La vue « Dérives » de la PWA d'administration [US-315]
========================================================================================
Une livraison a-t-elle alourdi le prompt de l'agent ou allongé sa boucle ? La vue compare la taille
des appels et le nombre d'appels par échange d'une version de l'application à l'autre
(`conso_tokens.version_app`, US-307).

Définitions (affichées par l'écran, testées ici) :
- **Un appel mesuré** : un appel d'unité `jeton` (la dictée et la voix comptent des secondes et des
  caractères, jamais comparables à des jetons) **et réussi** (`ok`) : un échec a zéro jeton et
  tirerait la médiane vers le bas sans rien dire du prompt.
- **Un échange** [CA3] : tous les appels qui partagent un `echange_ref`, échecs compris — une boucle de
  l'agent qui retente est précisément ce que la vue veut voir. Les lignes sans échange n'y entrent pas.
- **Échantillon faible** [CA5] : moins de `SEUIL_ECHANTILLON` appels (ou échanges) : le chiffre est
  rendu, mais l'écran ne le met pas en évidence.
- **Avant suivi des versions** [CA7] : les lignes sans `version_app` forment un groupe à part
  (`version: null`), jamais fondues dans une version.
- **Dix dernières versions** [CA1] : les dix plus récentes (ordre des numéros, pas de la date) qui ont
  des appels sur le périmètre, plus le groupe « avant suivi » s'il en a.
"""
from __future__ import annotations

import re
from dataclasses import replace
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import func

from database.models import ConsoTokens
from llm.passerelle import ISSUE_OK, UNITE_JETON
from . import agregats
from .agregats import Filtres, _executer, _filtrer, percentile

#: [CA1] Combien de versions la vue rend.
NB_VERSIONS = 10
#: [CA5] En dessous, l'échantillon est faible.
SEUIL_ECHANTILLON = 20
#: [CA4] Au-delà de cet écart relatif, la comparaison est mise en évidence.
SEUIL_ECART = 0.20
#: [CA2] Le type d'appel de la courbe quand rien n'est demandé.
TYPE_PAR_DEFAUT = "agent"


def cle_de_version(version: str) -> tuple:
    """Ordre des numéros : « 3.127.0 » < « 3.128.0 » < « 3.1000.0 ». Une version qui n'est pas un
    numéro pointé se range avant tous les numéros, entre elles par ordre alphabétique."""
    if re.fullmatch(r"\d+(\.\d+)*", version or ""):
        return (1, tuple(int(p) for p in version.split(".")), "")
    return (0, (), version or "")


def _versions_retenues(db, filtres: Filtres) -> tuple[list[str], bool]:
    """Les dix versions les plus récentes ayant des appels, plus : y a-t-il des appels sans version ?"""
    requete = _filtrer(db.query(ConsoTokens.version_app), filtres).distinct()
    presentes = {v for (v,) in _executer(db, requete)}
    sans_version = None in presentes or "" in presentes
    versions = sorted((v for v in presentes if v), key=cle_de_version, reverse=True)
    return versions[:NB_VERSIONS], sans_version


def _lignes_mesurees(db, filtres: Filtres, colonnes: list):
    """Les appels réussis d'unité `jeton`, une ligne par appel, les colonnes demandées d'abord."""
    requete = _filtrer(db.query(*colonnes), filtres).filter(
        ConsoTokens.unite == UNITE_JETON, ConsoTokens.issue == ISSUE_OK,
    )
    return _executer(db, requete)


def _par_version_et_type(db, filtres: Filtres, versions: list[str], sans_version: bool) -> list[dict]:
    """[CA1] Par version et par type d'appel : appels, médiane et P95 des jetons d'entrée, médiane des
    jetons de sortie, taux de cache."""
    gardees = set(versions) | ({None} if sans_version else set())
    groupes: dict[tuple, dict[str, list[int]]] = {}
    colonnes = [ConsoTokens.version_app, ConsoTokens.appel_type, ConsoTokens.tokens_in,
                ConsoTokens.tokens_out, ConsoTokens.tokens_cache]
    for version, appel_type, entree, sortie, cache in _lignes_mesurees(db, filtres, colonnes):
        version = version or None
        if version not in gardees:
            continue
        g = groupes.setdefault((version, appel_type), {"entree": [], "sortie": [], "cache": []})
        g["entree"].append(entree or 0)
        g["sortie"].append(sortie or 0)
        g["cache"].append(cache or 0)

    lignes = []
    for (version, appel_type), g in groupes.items():
        appels, entree_totale = len(g["entree"]), sum(g["entree"])
        lignes.append({
            "version": version,
            "appel_type": appel_type,
            "appels": appels,
            "entree_mediane": percentile(g["entree"], 0.5),
            "entree_p95": percentile(g["entree"], 0.95),
            "sortie_mediane": percentile(g["sortie"], 0.5),
            "taux_cache": (sum(g["cache"]) / entree_totale) if entree_totale else None,
            "echantillon_faible": appels < SEUIL_ECHANTILLON,
        })
    return lignes


def _courbe(db, filtres: Filtres, appel_type: str) -> dict:
    """[CA2] La médiane des jetons d'entrée par appel, jour par jour, pour un type d'appel ; un jour
    sans appel est `None` (pas zéro : une médiane de zéro mentirait). Les repères sont les versions
    dont la première apparition (toute l'histoire du périmètre) tombe dans la période."""
    points = [(filtres.depuis + timedelta(days=i)).isoformat() for i in range(filtres.jours)]
    par_jour: dict[str, list[int]] = {}
    colonnes = [ConsoTokens.date, ConsoTokens.tokens_in]
    for jour, entree in _lignes_mesurees(db, replace(filtres, appel_type=appel_type), colonnes):
        par_jour.setdefault(jour.isoformat(), []).append(entree or 0)

    toute_l_histoire = replace(filtres, depuis=date(2000, 1, 1), appel_type=None)
    premieres = _executer(db, _filtrer(
        db.query(ConsoTokens.version_app, func.min(ConsoTokens.date)), toute_l_histoire,
    ).filter(ConsoTokens.version_app.isnot(None)).group_by(ConsoTokens.version_app))
    reperes = [
        {"version": version, "date": jour.isoformat()}
        for version, jour in premieres
        if version and filtres.depuis <= jour <= filtres.jusqu_a
    ]
    reperes.sort(key=lambda r: (r["date"], cle_de_version(r["version"])))
    return {
        "appel_type": appel_type,
        "points": points,
        "valeurs": [percentile(par_jour[p], 0.5) if p in par_jour else None for p in points],
        "appels": [len(par_jour.get(p, [])) for p in points],
        "reperes": reperes,
    }


def _par_version_et_canal(db, filtres: Filtres, versions: list[str], sans_version: bool) -> list[dict]:
    """[CA3] Par version et par canal : nombre d'appels par échange (médiane, P95), jetons d'entrée
    médians par échange, coût médian par échange quand il est chiffré."""
    gardees = set(versions) | ({None} if sans_version else set())
    groupes = agregats._agreger(db, filtres, [ConsoTokens.version_app, ConsoTokens.canal, ConsoTokens.echange_ref])
    par_cle: dict[tuple, list] = {}
    for (version, canal, echange), cumul in groupes.items():
        version = version or None
        if not echange or version not in gardees:
            continue
        par_cle.setdefault((version, canal), []).append(cumul)

    lignes = []
    for (version, canal), cumuls in par_cle.items():
        couts = [c.cout_micro_eur for c in cumuls if c.cout_micro_eur is not None]
        appels = [c.appels for c in cumuls]
        lignes.append({
            "version": version,
            "canal": canal,
            "echanges": len(cumuls),
            "appels_par_echange_mediane": percentile(appels, 0.5),
            "appels_par_echange_p95": percentile(appels, 0.95),
            "entree_par_echange_mediane": percentile([c.jetons_entree for c in cumuls], 0.5),
            "cout_par_echange_mediane_micro_eur": percentile(couts, 0.5),
            "echantillon_faible": len(cumuls) < SEUIL_ECHANTILLON,
        })
    return lignes


def _ordre(lignes: list[dict], ordre_des_versions: list, secondaire: str) -> list[dict]:
    """Les versions dans l'ordre rendu (la plus récente d'abord, « avant suivi » en dernier) ; à version
    égale, la clé secondaire (type d'appel ou canal) par ordre alphabétique."""
    rang = {v: i for i, v in enumerate(ordre_des_versions)}
    return sorted(lignes, key=lambda l: (rang[l["version"]], str(l[secondaire])))


def derives(db, filtres: Filtres, appel_type: Optional[str] = None) -> dict:
    """[CA1 à CA7] Tout ce que la vue « Dérives » lit. `appel_type` : le type de la courbe (CA2)."""
    appel_type = appel_type or TYPE_PAR_DEFAUT
    versions, sans_version = _versions_retenues(db, filtres)
    ordre = versions + ([None] if sans_version else [])
    return {
        "periode": filtres.vers_dict(),
        "seuil_echantillon": SEUIL_ECHANTILLON,
        "seuil_ecart": SEUIL_ECART,
        "versions": ordre,
        "par_version_et_type": _ordre(_par_version_et_type(db, filtres, versions, sans_version), ordre, "appel_type"),
        "courbe": _courbe(db, filtres, appel_type),
        "par_version_et_canal": _ordre(_par_version_et_canal(db, filtres, versions, sans_version), ordre, "canal"),
    }

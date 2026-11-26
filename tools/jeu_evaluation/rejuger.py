"""Rejouer l'APPRÉCIATION d'une mesure déjà faite [US-337] : les traces ne bougent pas, aucun tour du compagnon n'est
rejoué. Les contrôles du code sont recalculés (sans appel), le juge est rappelé (deux appels par trace).

Le dossier d'origine n'est jamais modifié. Un verdict déjà lisible dans le dossier de sortie est repris : une relance
après une coupure de quota ne paie que ce qui manque.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Callable, Iterable, Optional

from tools.jeu_evaluation import campagne, controles
from tools.jeu_evaluation.jeu import Jeu
from tools.jeu_evaluation.juge import APPELS_JUGE_PAR_CAS, Juge, Verdict
from tools.jeu_evaluation.trace import TraceCas


def lire_relus(chemin: Path) -> dict[tuple[str, str, int], dict]:
    """Les verdicts humains (`verdicts_humains.json`), par (moteur, cas, passage)."""
    return {(v["moteur"], v["cas"], int(v["passage"])): v["humain"]
            for v in json.loads(Path(chemin).read_text(encoding="utf-8"))}


def a_rejouer(mesure: campagne.Mesure, *, cas: Iterable[str] = (), relus: Optional[dict] = None) -> list:
    voulus = set(cas)
    return [r for r in mesure.resultats
            if (not voulus or r.cas in voulus) and (relus is None or (mesure.moteur, r.cas, r.passage) in relus)]


def deja_juge(sortie: Path, chemin_trace: str) -> Optional[Verdict]:
    """Le verdict lisible d'une relance précédente, s'il y en a un."""
    fichier = sortie / chemin_trace
    if not chemin_trace or not fichier.is_file():
        return None
    verdict = json.loads(fichier.read_text(encoding="utf-8")).get("verdict")
    return Verdict.depuis_dict(verdict) if verdict and not verdict.get("illisible") else None


def appels_a_faire(mesure: campagne.Mesure, sortie: Path, *, cas: Iterable[str] = (),
                   relus: Optional[dict] = None) -> int:
    return APPELS_JUGE_PAR_CAS * sum(1 for r in a_rejouer(mesure, cas=cas, relus=relus)
                                     if r.trace and not r.erreur and deja_juge(sortie, r.trace) is None)


def rejuger(mesure: campagne.Mesure, jeu: Jeu, *, source: Path, sortie: Path, juge: Optional[Juge],
            cas: Iterable[str] = (), relus: Optional[dict] = None,
            detail: Callable[[str], None] = lambda _: None) -> campagne.Mesure:
    """La même mesure, renotée. Le jour est celui de la mesure : « hier » doit y désigner la même date."""
    jour = date.fromisoformat(mesure.date[:10])
    connues = tuple({c.fiche["culture"] for c in jeu.cas if c.fiche.get("culture")})
    par_id = {c.id: c for c in jeu.cas}
    resultats: list[campagne.ResultatCas] = []
    for ancien in a_rejouer(mesure, cas=cas, relus=relus):
        brut = json.loads((source / ancien.trace).read_text(encoding="utf-8"))
        brut.pop("notes", None)
        brut.pop("verdict", None)
        trace = TraceCas.depuis_dict(brut)
        le_cas = par_id[trace.cas]
        notes = controles.noter_cas(le_cas, trace, jour=jour, connues=connues)
        verdict = deja_juge(sortie, ancien.trace)
        if verdict is None and juge is not None and not trace.erreur:
            juge.jour = jour
            verdict = juge.noter(le_cas, trace)
        chemin = campagne.ecrire_trace(sortie, trace, notes, verdict)
        resultats.append(campagne.ResultatCas.depuis_dict(
            {**ancien.a_dict(), "notes": notes.a_dict(), "verdict": verdict.a_dict() if verdict else None,
             "trace": chemin}))
        detail(f"  {ancien.cas:8} p{ancien.passage} utile={getattr(verdict, 'utile', None)} "
               f"aboutit={getattr(verdict, 'aboutit', None)}")
    nouvelle = campagne.Mesure.depuis_dict({**mesure.a_dict(), "resultats": []})
    nouvelle.resultats = resultats
    nouvelle.juge = juge.modele if juge else mesure.juge
    nouvelle.configuration = f"appréciation rejouée sur les traces du {mesure.date}"
    return nouvelle


def accord_avec_l_humain(mesure: campagne.Mesure, relus: dict) -> dict[str, tuple[int, int]]:
    """Par critère : (verdicts identiques à l'humain, verdicts comparables)."""
    bilan = {}
    for critere in ("utile", "aboutit"):
        paires = [((r.verdict or {}).get(critere), relus.get((mesure.moteur, r.cas, r.passage), {}).get(critere))
                  for r in mesure.resultats]
        comparables = [(j, h) for j, h in paires if j is not None and h is not None]
        bilan[critere] = (sum(j == h for j, h in comparables), len(comparables))
    return bilan


def traces_coupees_sans_carte(mesure: campagne.Mesure, source: Path) -> int:
    """Les dialogues de l'ancien jardinier simulé, arrêtés par un clic sans carte : « aboutit » y reste faussé."""
    total = 0
    for r in mesure.resultats:
        tours = json.loads((source / r.trace).read_text(encoding="utf-8")).get("tours", [])
        total += any(t.get("clic") and not avant.get("proposition_en_attente") for avant, t in zip(tours, tours[1:]))
    return total

"""Jouer le jeu [US-337] : un dialogue, un passage, une campagne.

* `jouer_cas` joue un cas avec un moteur et le jardinier simulé, et rend la trace complète ;
* `jouer_passage` joue tout le jeu une fois pour un moteur, note chaque cas (code, puis juge) et garde chaque trace ;
* `Mesure` range ce qu'un moteur a obtenu sur tous ses passages : c'est ce que lit le rapport.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from tools.jeu_evaluation import controles
from tools.jeu_evaluation.jeu import Cas, Jeu
from tools.jeu_evaluation.juge import Juge, Verdict
from tools.jeu_evaluation.trace import TraceCas
from tools.jeu_evaluation.utilisateur import JardinierSimule

#: [CA6b] Chaque cas est joué au moins 3 fois par moteur.
PASSAGES_MIN = 3


def jouer_cas(cas: Cas, moteur: Any, *, passage: int = 1, pause_s: float = 0.0,
              dormir: Callable[[float], None] = time.sleep) -> TraceCas:
    """Joue un cas : l'ouverture, les phrases écrites d'avance, puis le jardinier simulé tant que le compagnon lui
    pose une question ou lui propose d'agir, dans la limite de `tours_max` tours."""
    trace = TraceCas(cas=cas.id, moteur=moteur.nom, passage=passage, modele_simule=bool(moteur.modele_simule))
    utilisateur = JardinierSimule(cas.fiche, mode_confirmation=moteur.mode_confirmation)
    ecrites = list(cas.phrases_ecrites)
    try:
        moteur.ouvrir(cas)
        rang, dernier = 0, None
        limite = max(cas.tours_max, len(ecrites))
        while rang < limite:
            if ecrites:
                phrase, clic = ecrites.pop(0), ""
            elif cas.simule and dernier is not None:
                if dernier.erreur:
                    break
                reponse = utilisateur.repondre(dernier.texte, proposition_en_attente=dernier.proposition_en_attente)
                if reponse.fin:
                    break
                phrase, clic = reponse.phrase, reponse.clic
            else:
                break
            rang += 1
            dernier = moteur.jouer(rang, phrase=phrase, clic=clic)
            trace.tours.append(dernier)
            if pause_s and dernier.etapes:
                dormir(pause_s)
    except Exception as e:  # noqa: BLE001 — un cas en erreur est consigné, la campagne continue
        trace.erreur = f"{type(e).__name__}: {e}"
    finally:
        moteur.fermer()
    trace.modele = getattr(moteur, "modele", "") or ""
    return trace


@dataclass
class ResultatCas:
    """Ce qu'un passage a donné pour un cas : la note du code, le verdict du juge, et les mesures de coût."""

    cas: str
    passage: int
    besoin: str
    notes: dict
    verdict: Optional[dict] = None
    tours: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    tokens_cache: int = 0
    #: Latence de chaque tour qui a appelé un modèle, en ms (le p95 se calcule sur tous les tours du moteur).
    latences_ms: list[int] = field(default_factory=list)
    tokens_in_par_tour: list[int] = field(default_factory=list)
    tokens_cache_par_tour: list[int] = field(default_factory=list)
    modele_simule: bool = False
    erreur: str = ""
    trace: str = ""
    jeu_de_donnees: str = ""
    renouvelable: bool = False

    def a_dict(self) -> dict:
        return dict(self.__dict__)

    @classmethod
    def depuis_dict(cls, d: dict) -> "ResultatCas":
        return cls(**d)


def resultat_de(cas: Cas, trace: TraceCas, notes: controles.Notes, verdict: Optional[Verdict],
                chemin_trace: str = "") -> ResultatCas:
    avec_modele = [t for t in trace.tours if t.etapes]
    return ResultatCas(
        cas=cas.id, passage=trace.passage, besoin=cas.besoin, notes=notes.a_dict(),
        verdict=verdict.a_dict() if verdict else None, tours=len(trace.tours),
        tokens_in=sum(t.tokens_in for t in trace.tours), tokens_out=sum(t.tokens_out for t in trace.tours),
        tokens_cache=sum(t.tokens_cache for t in trace.tours),
        latences_ms=[t.latence_ms for t in avec_modele], tokens_in_par_tour=[t.tokens_in for t in avec_modele],
        tokens_cache_par_tour=[t.tokens_cache for t in avec_modele], modele_simule=trace.modele_simule,
        erreur=trace.erreur or next((t.erreur for t in trace.tours if t.erreur), ""), trace=chemin_trace,
        jeu_de_donnees=cas.jeu_de_donnees, renouvelable=cas.renouvelable)


@dataclass
class Mesure:
    """Tout ce qu'un moteur a obtenu : ses passages, cas par cas. C'est le fichier que le rapport compare."""

    moteur: str
    modele: str = ""
    #: Faux dès qu'un passage a tourné sur un modèle simulé : le rapport ne la présente alors jamais comme mesure.
    mesure_reelle: bool = True
    potager: dict = field(default_factory=dict)
    jeu: str = ""
    date: str = ""
    passages: int = 0
    juge: str = ""
    resultats: list[ResultatCas] = field(default_factory=list)
    configuration: str = ""

    def a_dict(self) -> dict:
        return {**{k: v for k, v in self.__dict__.items() if k != "resultats"},
                "resultats": [r.a_dict() for r in self.resultats], "version": 1}

    @classmethod
    def depuis_dict(cls, d: dict) -> "Mesure":
        corps = {k: v for k, v in d.items() if k not in ("resultats", "version")}
        return cls(**corps, resultats=[ResultatCas.depuis_dict(r) for r in d.get("resultats", [])])

    def ecrire(self, chemin: Path) -> Path:
        chemin = Path(chemin)
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(json.dumps(self.a_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
        return chemin

    @classmethod
    def lire(cls, chemin: Path) -> "Mesure":
        return cls.depuis_dict(json.loads(Path(chemin).read_text(encoding="utf-8")))

    def par_cas(self) -> dict[str, list[ResultatCas]]:
        rangs: dict[str, list[ResultatCas]] = {}
        for r in self.resultats:
            rangs.setdefault(r.cas, []).append(r)
        return rangs


def ecrire_trace(dossier: Path, trace: TraceCas, notes: controles.Notes, verdict: Optional[Verdict]) -> str:
    """CA5 : la trace complète d'un cas, avec ses notes, dans `<dossier>/<moteur>/passage_<n>/<cas>.json`."""
    chemin = Path(dossier) / trace.moteur / f"passage_{trace.passage}" / f"{trace.cas}.json"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps({**trace.a_dict(), "notes": notes.a_dict(),
                                  "verdict": verdict.a_dict() if verdict else None},
                                 ensure_ascii=False, indent=1), encoding="utf-8")
    return str(chemin.relative_to(dossier)).replace("\\", "/")


def jouer_passage(
    jeu: Jeu, moteur_pour: Callable[[Cas], Any], *, passage: int, dossier: Optional[Path] = None,
    juge: Optional[Juge] = None, jour: Optional[date] = None, pause_s: float = 0.0,
    detail: Callable[[str], None] = lambda _: None, dormir: Callable[[float], None] = time.sleep,
) -> list[ResultatCas]:
    """Un passage : tous les cas du jeu, une fois. `moteur_pour(cas)` rend le moteur du jeu de données du cas (le
    potager neuf et le potager 33 ne partagent pas de contexte locataire)."""
    connues = tuple({c.fiche["culture"] for c in jeu.cas if c.fiche.get("culture")})
    resultats: list[ResultatCas] = []
    for cas in jeu.cas:
        moteur = moteur_pour(cas)
        trace = jouer_cas(cas, moteur, passage=passage, pause_s=pause_s, dormir=dormir)
        notes = controles.noter_cas(cas, trace, jour=jour, connues=connues)
        verdict = juge.noter(cas, trace) if juge is not None and not trace.erreur else None
        chemin = ecrire_trace(dossier, trace, notes, verdict) if dossier is not None else ""
        resultat = resultat_de(cas, trace, notes, verdict, chemin)
        resultats.append(resultat)
        marques = [c for c in controles.CRITERES_A_100 if not notes.tient(c)] + (["hors_sujet"] if notes.hors_sujet else [])
        detail(f"  {cas.id:8} p{passage} {'✅' if not marques else '🛑 ' + ', '.join(marques)}"
               f"{'  ⚠️ ' + resultat.erreur if resultat.erreur else ''}")
    return resultats


def maintenant() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def horodatage() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def moteurs_utilises(resultats: Iterable[ResultatCas]) -> set[bool]:
    return {r.modele_simule for r in resultats}

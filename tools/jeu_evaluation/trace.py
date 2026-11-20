"""La trace complète de chaque tour [US-337 / CA5] : appels d'outils, arguments, résultats, texte montré,
jetons, part en cache, latence. Elle se sérialise telle quelle en JSON : c'est ce que relit le juge, l'humain
qui contrôle l'échantillon, et le rapport."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

#: Un résultat d'outil est tronqué dans la trace : elle sert à relire, pas à rejouer.
LONGUEUR_RESULTAT_MAX = 4000


def tronquer(texte: Any, longueur: int = LONGUEUR_RESULTAT_MAX) -> str:
    texte = texte if isinstance(texte, str) else str(texte)
    return texte if len(texte) <= longueur else texte[:longueur] + f"… [tronqué, {len(texte)} caractères]"


@dataclass
class AppelTrace:
    nom: str
    arguments: dict = field(default_factory=dict)
    resultat: str = ""
    refus: bool = False
    #: Vrai pour une proposition ou une décision d'écriture. Jamais exécutée par la mesure.
    ecriture: bool = False
    #: Vrai quand le résultat a été fabriqué par la mesure (écriture simulée au schéma du registre).
    simule: bool = False


@dataclass
class TraceTour:
    rang: int
    #: Ce que dit le jardinier ; `clic` si c'est un bouton (« Confirmer »).
    jardinier: str = ""
    clic: str = ""
    #: Tout ce que le jardinier lit à ce tour (texte du compagnon, récapitulatif, source).
    texte: str = ""
    appels: list[AppelTrace] = field(default_factory=list)
    #: Les propositions d'écriture montrées au jardinier (arguments tels que transmis).
    propositions: list[dict] = field(default_factory=list)
    #: Les écritures que la confirmation aurait exécutées (jamais exécutées par la mesure).
    executions: list[dict] = field(default_factory=list)
    #: Une proposition attend la confirmation du jardinier à la fin du tour.
    proposition_en_attente: bool = False
    etapes: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    tokens_cache: int = 0
    latence_ms: int = 0
    erreur: str = ""

    @property
    def phrase(self) -> str:
        return self.jardinier or (f"[clic] {self.clic}" if self.clic else "")


@dataclass
class TraceCas:
    cas: str
    moteur: str
    passage: int
    modele: str = ""
    #: Vrai quand le modèle était simulé : rien de ce passage n'est une mesure (US-337 / CA7).
    modele_simule: bool = False
    tours: list[TraceTour] = field(default_factory=list)
    erreur: str = ""

    def a_dict(self) -> dict:
        return asdict(self)

    @property
    def tokens_in(self) -> int:
        return sum(t.tokens_in for t in self.tours)

    @property
    def tokens_cache(self) -> int:
        return sum(t.tokens_cache for t in self.tours)

    def textes_du_compagnon(self) -> list[str]:
        return [t.texte for t in self.tours]

    def phrases_du_jardinier(self) -> list[str]:
        return [t.jardinier for t in self.tours if t.jardinier]

    @classmethod
    def depuis_dict(cls, d: dict) -> "TraceCas":
        tours = [TraceTour(**{**t, "appels": [AppelTrace(**a) for a in t.get("appels", [])]}) for t in d.get("tours", [])]
        return cls(**{**d, "tours": tours})


def dernier_tour_utile(trace: TraceCas) -> Optional[TraceTour]:
    return next((t for t in reversed(trace.tours) if t.texte or t.propositions), None)

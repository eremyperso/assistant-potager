"""Joue les scénarios : remise à zéro, semis de l'état initial, tours, verdict par scénario.

Verdict (un scénario = N passages) :
* un passage RÉUSSIT si aucune vérification bloquante n'échoue, si le bot a répondu à
  chaque tour et si aucun clic n'est resté sans bouton ;
* le scénario est ÉCHEC si la part de passages réussis est sous son `seuil`,
  À SURVEILLER si elle est au-dessus mais sous 100 %, RÉUSSI sinon.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

from .assertions import Observation, Resultat, evaluer_tour
from .driver import BoutonIntrouvable, PiloteTelegram
from .parser import Scenario, Tour

log = logging.getLogger("conv")

REUSSI, SURVEILLER, ECHEC = "RÉUSSI", "À SURVEILLER", "ÉCHEC"


@dataclass
class ResultatTour:
    tour: Tour
    observation: Observation
    resultats: list[Resultat] = field(default_factory=list)
    erreur: str = ""

    @property
    def ok(self) -> bool:
        if self.erreur or self.observation.silence:
            return False
        return all(r.ok is not False for r in self.resultats if r.verification.bloquante)


@dataclass
class ResultatPassage:
    numero: int
    tours: list[ResultatTour] = field(default_factory=list)
    erreur: str = ""

    @property
    def ok(self) -> bool:
        return not self.erreur and all(t.ok for t in self.tours)


@dataclass
class ResultatScenario:
    scenario: Scenario
    passages: list[ResultatPassage] = field(default_factory=list)

    @property
    def taux(self) -> float:
        return sum(p.ok for p in self.passages) / len(self.passages) if self.passages else 0.0

    @property
    def statut(self) -> str:
        if self.taux < self.scenario.seuil:
            return ECHEC
        return REUSSI if self.taux == 1.0 else SURVEILLER


async def jouer_passage(pilote: PiloteTelegram, base, sc: Scenario, numero: int,
                        avancer: Optional[Callable[[str], None]] = None) -> ResultatPassage:
    passage = ResultatPassage(numero)
    if not await pilote.reinitialiser():
        passage.erreur = "remise à zéro refusée : le bot n'a pas répondu RESET_OK (APP_ENV=test ? base de test ?)"
        return passage
    if sc.parcelles:
        base.semer_parcelles(sc.parcelles)
    for tour in sc.tours:
        if avancer:
            avancer(f"{sc.id} passage {numero} tour {tour.numero}")
        avant = base.instantane()
        try:
            obs = await (pilote.envoyer(tour.message) if tour.message else pilote.cliquer(tour.clic))
        except BoutonIntrouvable as e:
            passage.tours.append(ResultatTour(tour, Observation(), erreur=str(e)))
            break
        # `echanges_conversation` s'écrit juste après la réponse : on laisse la base rattraper
        await asyncio.sleep(0.5)
        base.completer(obs, avant)
        passage.tours.append(ResultatTour(tour, obs, evaluer_tour(tour.verifications, obs)))
    return passage


async def jouer(scenarios: list[Scenario], pilote: PiloteTelegram, base, passages: Optional[int] = None,
                avancer: Optional[Callable[[str], None]] = None) -> list[ResultatScenario]:
    sorties: list[ResultatScenario] = []
    for sc in scenarios:
        res = ResultatScenario(sc)
        for n in range(1, (passages or sc.passages) + 1):
            res.passages.append(await jouer_passage(pilote, base, sc, n, avancer))
        sorties.append(res)
    return sorties


def nombre_de_messages(scenarios: list[Scenario], passages: Optional[int] = None) -> int:
    """Messages envoyés au bot (et donc, au pire, appels au modèle) pour cette campagne."""
    return sum((passages or sc.passages) * (len(sc.tours) + 1) for sc in scenarios)

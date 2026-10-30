"""
app/services/vocabulaire_parcelle.py — Les valeurs admises d'une parcelle [US-251]
==================================================================================
Une seule liste de valeurs admises par caractéristique (type de pépinière, abri,
type de sol, ensoleillement, exposition), lue par la reconnaissance par règles
(`interpreteur_commandes`) ET par l'agent (`agent.catalogue_outils`, qui en fait
les `enum` de ses outils, et `agent.validation`, qui refuse une valeur hors liste).

Les listes ne sont pas écrites ici : elles viennent du domaine
(`parcelles.vocabulaires_fiche()` et `utils.parcelles.TYPES_PEPINIERE`). Ce module
y ajoute ce que la fiche ne sait pas faire : rapprocher un mot mal dit d'une
valeur admise, sans appel au modèle.

Le rapprochement est volontairement étroit (CA2) : une valeur dite ne se rapproche
que si elle ne diffère d'une valeur admise que par la casse, les accents, les
tirets, le genre ou le nombre (« chaud » → chaude, « argileuse » → argileux).
Elle est alors PROPOSÉE, visible au récapitulatif, jamais écrite en silence. Une
valeur qui irait à deux valeurs (CA4) ou à aucune (CA5) n'est jamais tranchée.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterable, Optional

from unidecode import unidecode

log = logging.getLogger("potager")

EXACT = "exact"
CORRIGE = "corrige"
AMBIGU = "ambigu"
AUCUN = "aucun"


@dataclass(frozen=True)
class Caracteristique:
    """Une caractéristique de parcelle à liste de valeurs admises."""

    #: La clé de `/parcelle modifier <nom> <cle>=<valeur>`.
    cle: str
    #: Comment on la dit au jardinier, article compris : « le type de pépinière ».
    libelle: str
    #: Les valeurs admises, telles que la fiche et les outils de l'agent les écrivent.
    valeurs: tuple[str, ...]
    #: `True` : la liste est une règle ; `False` : une proposition (l'exposition).
    ferme: bool = True
    #: Ce qu'une règle écrit tant que le jardinier n'a rien précisé (« pepiniere=oui »).
    non_precisees: tuple[str, ...] = ()

    def pour_commande(self, valeur: str) -> str:
        """La valeur telle qu'elle s'écrit dans `<cle>=<valeur>` : un seul mot."""
        return valeur.strip().replace(" ", "-")


@dataclass(frozen=True)
class Rapprochement:
    """Ce que devient un mot dit face à une liste de valeurs admises."""

    statut: str
    #: La valeur admise retenue — seulement pour `exact` et `corrige`.
    valeur: Optional[str] = None
    #: Les valeurs possibles — deux ou plus pour `ambigu`.
    candidats: tuple[str, ...] = ()


def caracteristiques() -> dict[str, Caracteristique]:
    """Le registre, lu au domaine à chaque appel : il ne peut pas se périmer."""
    from app.services.parcelles import vocabulaires_fiche
    from utils.parcelles import TYPES_PEPINIERE

    fiche = vocabulaires_fiche()

    def _valeurs(nom: str) -> tuple[str, ...]:
        return tuple(str(option["valeur"]) for option in fiche[nom]["options"])

    return {
        "pepiniere": Caracteristique(
            "pepiniere", "le type de pépinière", tuple(TYPES_PEPINIERE), non_precisees=("oui",),
        ),
        "abri": Caracteristique("abri", "l'abri", _valeurs("abri")),
        "type_sol": Caracteristique("type_sol", "le type de sol", _valeurs("type_sol")),
        "ensoleillement": Caracteristique(
            "ensoleillement", "l'ensoleillement", _valeurs("ensoleillement"),
        ),
        "exposition": Caracteristique(
            "exposition", "l'exposition", _valeurs("exposition"), ferme=False,
        ),
    }


def caracteristique(cle: str) -> Optional[Caracteristique]:
    return caracteristiques().get((cle or "").strip().lower())


def valeurs_admises(cle: str) -> tuple[str, ...]:
    """[CA1] Les valeurs admises de `cle`, ou () si la caractéristique n'a pas de liste."""
    trouvee = caracteristique(cle)
    return trouvee.valeurs if trouvee is not None else ()


# ─────────────────────────────────────────────────────────────────────────────
# Le rapprochement — sans modèle (CA7)
# ─────────────────────────────────────────────────────────────────────────────
def _mots(texte: str) -> list[str]:
    """Casse, accents, tirets et espaces ramenés à des mots simples."""
    return re.findall(r"[a-z0-9]+", unidecode(texte or "").lower())


def _racine(mot: str) -> str:
    """Le mot au masculin singulier : « chaudes » → chaud, « argileuse » → argileux."""
    if mot.endswith("euses"):
        mot = mot[:-5] + "eux"
    elif mot.endswith("euse"):
        mot = mot[:-4] + "eux"
    elif len(mot) > 3 and mot.endswith("s") and not mot.endswith("ss"):
        mot = mot[:-1]
    if len(mot) > 3 and mot.endswith("e"):
        mot = mot[:-1]
    return mot


def _cle(texte: str) -> str:
    return " ".join(_racine(mot) for mot in _mots(texte))


def rapprocher(dit: str, valeurs: Iterable[str]) -> Rapprochement:
    """[CA2, CA4, CA5, CA7] Le mot dit face à une liste de valeurs admises.

    - `exact`   : la valeur est admise, aux accents, à la casse et aux tirets près ;
    - `corrige` : une seule valeur admise ne s'en distingue que par le genre ou le nombre ;
    - `ambigu`  : plusieurs valeurs admises s'en rapprochent — aucune n'est choisie ;
    - `aucun`   : rien ne s'en rapproche.
    """
    admises = tuple(valeurs)
    mots = " ".join(_mots(dit))
    if not mots:
        return Rapprochement(AUCUN)
    for valeur in admises:
        if " ".join(_mots(valeur)) == mots:
            return Rapprochement(EXACT, valeur, (valeur,))
    cle = _cle(dit)
    proches = tuple(valeur for valeur in admises if _cle(valeur) == cle)
    if len(proches) == 1:
        log.info("🎛️  VOCABULAIRE     : %r rapproché de %r", dit, proches[0])
        return Rapprochement(CORRIGE, proches[0], proches)
    if len(proches) > 1:
        return Rapprochement(AMBIGU, None, proches)
    return Rapprochement(AUCUN)


def rapprocher_caracteristique(cle: str, dit: str) -> Rapprochement:
    """`rapprocher` sur les valeurs admises de la caractéristique `cle`."""
    return rapprocher(dit, valeurs_admises(cle))

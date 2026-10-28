"""
app/services/agent/projection.py — Le catalogue que voit le modèle, selon la phrase [US-276]
============================================================================================
Le code sait déjà reconnaître une demande de savoir et un verbe de destruction ;
il décide donc, AVANT l'appel, quels outils le modèle voit. Le modèle ne fait
plus que choisir dans un catalogue réduit (cadrage du compagnon actif, §4.5).

Trois projections, bornées et dans l'ordre du catalogue (`catalogue_outils.PROJECTIONS`) :

  * une phrase INTERROGATIVE ne voit que la lecture et les outils de réponse
    (CA2) : « est-ce que je peux supprimer la planche sud ? » ne peut plus
    devenir une suppression à confirmer ;
  * une phrase qui porte un verbe de destruction voit tout (CA3) — la liste est
    celle de la règle `parcelle_supprimer`, `VERBES_DE_DESTRUCTION`, jamais une
    seconde ;
  * toute autre phrase voit tout, sauf les outils destructeurs.

Ce qui fait une phrase interrogative : un point d'interrogation, « est-ce que »,
« comment », « quand », « peux-tu » — sauf une formule de demande suivie d'un
verbe d'action (« peux-tu renommer la planche sud ? »), que `demande_d_agir`
reconnaît déjà comme une demande d'agir (INC-018). Une demande de procédure
(`_est_demande_de_savoir`) en est une aussi, quelle que soit sa ponctuation.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from app.services.agent.catalogue_outils import (
    PROJECTION_COMPLETE,
    PROJECTION_SANS_DESTRUCTION,
    PROJECTION_SANS_ECRITURE,
)
from app.services.interpreteur_commandes import (
    VERBES_DE_DESTRUCTION,
    _est_demande_de_savoir,
    demande_d_agir,
    normaliser,
)

log = logging.getLogger("potager")

#: CA2 — les marques d'une question, cherchées n'importe où dans la phrase normalisée.
_MARQUES_DE_QUESTION = re.compile(
    r"\b(?:est ce que|est ce qu|comment|quand|peux tu|pourrais tu|pouvez vous|pourriez vous)\b"
)
_VERBE_DE_DESTRUCTION = re.compile(rf"\b(?:{VERBES_DE_DESTRUCTION})\b")
#: `demande_d_agir` reconnaît aussi « montre », « affiche » : ce n'est pas une écriture.
_COMMANDE_D_AFFICHAGE = "/menu"


def est_interrogative(phrase: str) -> bool:
    """[CA2] La phrase pose-t-elle une question plutôt qu'elle ne demande d'agir ?"""
    normalise = normaliser(phrase or "")[0]
    demande = demande_d_agir(normalise)
    if demande is not None and demande != _COMMANDE_D_AFFICHAGE:
        return False
    return (
        "?" in normalise
        or bool(_MARQUES_DE_QUESTION.search(normalise))
        or _est_demande_de_savoir(normalise)
    )


def demande_une_destruction(texte: str) -> bool:
    """[CA3] La phrase porte-t-elle un verbe de destruction de la règle `parcelle_supprimer` ?"""
    return bool(_VERBE_DE_DESTRUCTION.search(normaliser(texte or "")[0]))


def projection_pour(phrase: str, texte_en_contexte: Optional[str] = None) -> str:
    """[CA2, CA3] La projection du catalogue pour cette phrase.

    `phrase` : ce que le jardinier vient de dire — c'est elle qui est, ou non, une
    question. `texte_en_contexte` : la phrase précédée de la demande en attente
    (US-238) ; « non, la sud » prolonge « supprime la planche » et garde l'outil
    destructeur, jamais une question qui suit.
    """
    if est_interrogative(phrase):
        return PROJECTION_SANS_ECRITURE
    if demande_une_destruction(texte_en_contexte or phrase):
        return PROJECTION_COMPLETE
    return PROJECTION_SANS_DESTRUCTION

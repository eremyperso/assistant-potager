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


#: Au moins ce nombre de mots après le dernier « ? » : une demande y suit la question.
_MOTS_DE_LA_SUITE = 3


def _apres_la_derniere_question(normalise: str) -> str:
    """« Bon, tu m'entends ? Alors, je veux que tu me crées une parcelle nord… » : la phrase
    parle de ce qui SUIT le dernier « ? », pas de la politesse qui l'ouvre. Une réponse de un
    ou deux mots après la question (« … ? oui ») n'en fait pas une demande."""
    avant, point, suite = normalise.rpartition("?")
    if point and len(suite.split()) >= _MOTS_DE_LA_SUITE:
        return suite.strip()
    return normalise


def est_interrogative(phrase: str) -> bool:
    """[CA2] La phrase pose-t-elle une question plutôt qu'elle ne demande d'agir ?"""
    normalise = _apres_la_derniere_question(normaliser(phrase or "")[0])
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


#: [US-263 / CA5] Un constat de dégât ou de maladie (« les limaces ont bouffé mes salades ») n'est pas un
#: geste : le compagnon lit, conseille et PROPOSE de noter, il n'écrit rien. Le constat est un
#: signe du problème (ravageur, maladie, dégât) dit sans demande d'agir et sans geste accompli.
_SIGNE_DE_PROBLEME = re.compile(
    r"\b(?:bouff\w*|mange[a-z]*|mangent|rong\w*|grignot\w*|devor\w*|ravag\w*|attaqu\w*|degats?|"
    r"limaces?|escargots?|pucerons?|doryphores?|chenilles?|mildiou|oidium|rouille|campagnols?|taupes?|"
    r"jauni\w*|fane\w*|pourri\w*|moisi\w*|malades?|taches?)\b"
)
_GESTE_ACCOMPLI = re.compile(
    r"\bj ai (?:\w+ )?(?:traite|pulverise|epandu|mis|pose|ramasse|enleve|arrache|desherbe|paille|"
    r"arrose|plante|seme|recolte|repique|taille|bine|butte|fertilise|ferti)\w*"
)


def est_un_constat_de_probleme(phrase: str) -> bool:
    """[US-263 / CA5] La phrase dit un problème au jardin, sans demander d'agir ni rapporter un geste."""
    normalise = normaliser(phrase or "")[0]
    if demande_d_agir(normalise) is not None or _GESTE_ACCOMPLI.search(normalise):
        return False
    return bool(_SIGNE_DE_PROBLEME.search(normalise))


def projection_pour(phrase: str, texte_en_contexte: Optional[str] = None) -> str:
    """[CA2, CA3] La projection du catalogue pour cette phrase.

    `phrase` : ce que le jardinier vient de dire — c'est elle qui est, ou non, une
    question. `texte_en_contexte` : la phrase précédée de la demande en attente
    (US-238) ; « non, la sud » prolonge « supprime la planche » et garde l'outil
    destructeur, jamais une question qui suit.
    [US-263 / CA5] Un constat de problème se lit comme une question : aucune écriture.
    """
    if est_interrogative(phrase) or (texte_en_contexte in (None, phrase) and est_un_constat_de_probleme(phrase)):
        return PROJECTION_SANS_ECRITURE
    if demande_une_destruction(texte_en_contexte or phrase):
        return PROJECTION_COMPLETE
    return PROJECTION_SANS_DESTRUCTION

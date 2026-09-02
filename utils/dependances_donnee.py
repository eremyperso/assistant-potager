"""
utils/dependances_donnee.py — Natures de donnée d'un potager [US-095 / CA4]
================================================================================
Vocabulaire minimal partagé par deux modules qui, sans lui, entretiendraient
chacun sa liste :

- `app/services/reponses_chiffrees.py` déclare, pour chaque famille de question,
  les natures de donnée dont sa réponse dérive ;
- `app/services/cache_questions.py` traduit une écriture d'évènement en natures
  impactées, pour invalider exactement les entrées de cache concernées.

Deux listes séparées divergeraient à la première action ajoutée au référentiel,
et la divergence ne se verrait pas : elle se paierait en réponses périmées
servies avec assurance. Ce module vit dans `utils/` parce qu'il ne dépend que
du référentiel lexical des actions (`utils/actions.py`) et d'aucune couche
service — les deux modules ci-dessus peuvent donc l'importer sans cycle.

**Arbitrage de l'US — invalider large plutôt que fin :** en cas de doute, une
action rend caduques PLUS d'entrées que nécessaire. Recalculer une réponse
paramétrée coûte zéro jeton ; servir une donnée fausse coûte la confiance.
C'est pourquoi une action inconnue impacte toutes les natures, et pourquoi
`journal` est impacté par toute écriture sans exception.
"""
from __future__ import annotations

from typing import Optional

from utils.actions import normalize_action

# ─────────────────────────────────────────────────────────────────────────────
# Les natures de donnée [CA4]
# ─────────────────────────────────────────────────────────────────────────────
# Stock courant d'une culture (pieds en place, quantité restante).
NATURE_STOCK = "stock"
# Récoltes et rendements cumulés.
NATURE_RECOLTE = "recolte"
# Semis, quel que soit leur support.
NATURE_SEMIS = "semis"
# Occupation des parcelles, place disponible.
NATURE_PLAN = "plan"
# Lots de godets en attente de plantation.
NATURE_PEPINIERE = "pepiniere"
# Le journal brut lui-même : « quand ai-je arrosé pour la dernière fois ? » ne
# dépend d'aucune des natures ci-dessus, mais de l'existence des lignes. Toute
# écriture l'impacte, y compris un simple arrosage.
NATURE_JOURNAL = "journal"

NATURES_TOUTES: frozenset[str] = frozenset({
    NATURE_STOCK, NATURE_RECOLTE, NATURE_SEMIS,
    NATURE_PLAN, NATURE_PEPINIERE, NATURE_JOURNAL,
})

# Natures impactées par chaque action canonique du référentiel
# (`utils/actions.ACTION_MAP`), EN PLUS de `journal` qui l'est toujours.
# Une action absente de cette table n'est pas une erreur : elle impacte toutes
# les natures (voir `natures_impactees`).
_NATURES_PAR_ACTION: dict[str, tuple[str, ...]] = {
    # Le geste change ce qui a été récolté, donc aussi le stock restant d'une
    # culture végétative — les deux natures partent ensemble.
    "recolte": (NATURE_RECOLTE, NATURE_STOCK),
    "vendu": (NATURE_STOCK,),
    "perte": (NATURE_STOCK, NATURE_PLAN),
    "plantation": (NATURE_STOCK, NATURE_PLAN, NATURE_PEPINIERE),
    "semis": (NATURE_SEMIS, NATURE_PEPINIERE, NATURE_STOCK),
    "mise_en_godet": (NATURE_PEPINIERE, NATURE_SEMIS),
    "perte_godet": (NATURE_PEPINIERE, NATURE_SEMIS),
    # Gestes d'entretien : ils ne déplacent ni stock ni plan. Seul le journal
    # bouge — et c'est bien assez pour périmer « quand ai-je arrosé ? ».
    "arrosage": (),
    "desherbage": (),
    "paillage": (),
    "amendement": (),
    "taille": (),
    "tuteurage": (),
    "traitement": (),
    "protection": (),
    "observation": (),
    "binage": (),
    # Un éclaircissage supprime des pieds : le stock et le plan bougent.
    "eclaircie": (NATURE_STOCK, NATURE_PLAN),
}


def natures_impactees(type_action: Optional[str]) -> frozenset[str]:
    """[CA5] Natures de donnée rendues caduques par l'écriture d'un évènement
    de ce type d'action.

    Une action absente du référentiel — ou absente tout court — renvoie
    `NATURES_TOUTES` : on ne sait pas ce qu'elle change, donc on considère
    qu'elle change tout. C'est l'arbitrage « invalider large » appliqué au seul
    endroit où il compte, celui où l'on ne sait pas.
    """
    canonique = normalize_action(type_action) if type_action else None
    specifiques = _NATURES_PAR_ACTION.get(canonique or "")
    if specifiques is None:
        return NATURES_TOUTES
    return frozenset(specifiques) | {NATURE_JOURNAL}

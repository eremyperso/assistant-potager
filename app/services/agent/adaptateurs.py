"""
app/services/agent/adaptateurs.py — Un appel d'outil typé → les arguments de la commande [US-235 / CA2]
=====================================================================================================
L'outil `modifier_parcelle` expose des champs TYPÉS ; le handler de
`/parcelle modifier`, lui, lit toujours des `clé=valeur`. L'adaptateur les
resérialise, et le handler reste inchangé :

    {parcelle: "Serre extérieure", est_pepiniere: false}
        → valeurs = {"nom": "Serre extérieure", "modification": "pepiniere=non"}
        → /parcelle modifier Serre extérieure pepiniere=non

Plusieurs champs donnent plusieurs `clé=valeur`, séparés par une espace — ce
que le handler découpe déjà quand la commande est tapée. Une valeur ne porte
donc jamais d'espace : « plein soleil » devient « plein-soleil », que le point
d'écriture normalise déjà (tirets et espaces s'y valent).

Aucune valeur n'est validée ici : c'est le rôle de `validation`, qui appelle
cet adaptateur sur des champs déjà contrôlés.
"""
from __future__ import annotations

from typing import Optional

from app.services.agent.catalogue_outils import CHAMP_TYPE_PEPINIERE, ChampFiche


def texte_nombre(valeur: float) -> str:
    """« 6 » et non « 6.0 », « 12.5 » et non « 12.50 » : ce qui sera relu au jardinier."""
    nombre = float(valeur)
    if nombre == int(nombre):
        return str(int(nombre))
    return f"{round(nombre, 2):g}"


def _texte_valeur(champ: ChampFiche, valeur) -> str:
    if champ.type_json == "boolean":
        return "oui" if valeur else "non"
    if champ.type_json in ("integer", "number"):
        return texte_nombre(valeur)
    return str(valeur).strip().replace(" ", "-")


def modification_parcelle(champs: list[tuple[ChampFiche, object]]) -> Optional[str]:
    """[CA2] Les champs typés retenus → la chaîne `clé=valeur …` du handler, ou None.

    Le statut et le type de pépinière tiennent dans UNE clé (`pepiniere=`) :
    « pépinière chaude » s'écrit `pepiniere=chaude`, « n'est plus une
    pépinière » `pepiniere=non` — le type dit avec une négation n'a pas de sens
    et n'est pas écrit (US-208 : retirer le statut retire le type).
    """
    par_nom = {champ.nom: (champ, valeur) for champ, valeur in champs}
    est_pepiniere = par_nom.get("est_pepiniere", (None, None))[1]
    type_dit = par_nom.get(CHAMP_TYPE_PEPINIERE, (None, None))[1]

    morceaux: list[str] = []
    for champ, valeur in champs:
        if champ.nom == CHAMP_TYPE_PEPINIERE:
            continue
        if champ.nom == "est_pepiniere":
            if valeur and type_dit:
                morceaux.append(f"pepiniere={type_dit}")
            else:
                morceaux.append(f"pepiniere={_texte_valeur(champ, valeur)}")
            continue
        morceaux.append(f"{champ.cle}={_texte_valeur(champ, valeur)}")
    if type_dit and est_pepiniere is None:
        # « la serre est une pépinière chaude » sans booléen : le type dit la pépinière.
        morceaux.append(f"pepiniere={type_dit}")
    return " ".join(morceaux) or None

"""
app/services/espacement_rang.py — Espacement sur le rang d'une culture [US-226]
------------------------------------------------------------------------------
Seul endroit où `culture_config.espacement` — une **chaîne libre** (« 110 × 135
cm »), jamais un nombre — devient un espacement sur le rang exploitable, en
centimètres. US-227 y lit combien de pieds tiennent sur une longueur de planche
(US-225), US-228 le dessine.

La chaîne suit une convention vérifiable, constatée sur toutes les entrées de
`migrations/migration_v13.sql` : `A × B cm` avec `A ≤ B` et
`surface_m2 = A × B ÷ 10000`. **A est l'espacement sur le rang**, B l'écart
entre rangs, et `surface_m2` sert de contrôle (CA3).

La notation `A à B cm` du référentiel suit la même convention : deux
distances, et non une fourchette de valeurs.

Ce module ne crée aucune colonne, n'écrit rien et n'appelle aucun modèle. Il
s'arrête là où la donnée s'arrête : une culture sans espacement lisible n'a
**pas** de places, et l'écran le dira (RT2) — jamais une valeur moyenne, jamais
l'espacement d'une culture voisine.

⚖️ Arbitrage A24 du plan des épics : lire la chaîne existante plutôt qu'ouvrir
une colonne numérique déclarable. Si le terrain montre que le référentiel est
faux pour le jardinier — des tomates conduites tous les 40 cm et non 50 —, la
colonne déclarable devient une US à part, sans rien invalider ici.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from unidecode import unidecode

log = logging.getLogger("potager")

#: [CA2] Bornes d'un espacement sur le rang plausible au potager. Hors de là, la
#: chaîne est illisible plutôt que fausse : « non renseigné », jamais zéro.
ESPACEMENT_MIN_CM, ESPACEMENT_MAX_CM = 1, 400

#: [CA3] Tolérance du contrôle `A × B ÷ 10000` ↔ `surface_m2`. Au-delà, la
#: valeur est retenue quand même : c'est une anomalie de RÉFÉRENTIEL, pas une
#: erreur d'exécution, et corriger en silence serait pire que la signaler.
TOLERANCE_SURFACE = 0.10

#: L'unité est retirée avant lecture — « 110 × 135 cm », « 110x135cm »,
#: « 110 × 135 centimètres » disent la même chose.
_UNITE = re.compile(r"(?:cm|centimetres?)\b")
#: Deux valeurs séparées : « × » (que `unidecode` ramène à « x »), « x », « * »,
#: « / » ou un tiret. Le tiret n'introduit jamais un nombre négatif ici : le
#: motif exige un chiffre AVANT le séparateur.
_DEUX_VALEURS = re.compile(
    r"\A(\d+(?:[.,]\d+)?)(?:\s*[x*/\-]\s*|\s+a\s+)"
    r"(\d+(?:[.,]\d+)?)\s*\Z"
)
#: Une seule valeur : « 50 cm », « 50 » — lue comme l'espacement sur le rang (CA2).
_UNE_VALEUR = re.compile(r"\A(\d+(?:[.,]\d+)?)\s*\Z")


def _nombre(fragment: str) -> float:
    return float(fragment.replace(",", "."))


def _lire(chaine: Optional[str]) -> tuple[Optional[float], Optional[float]]:
    """Lit `A × B cm` ou `A à B cm`, ou une valeur unique.

    Rend `(A, B)`, `(A, None)` ou `(None, None)`.
    Aucune validation de bornes ici : la lecture dit ce que la chaîne contient,
    `espacement_rang_cm` dit ce qui en est exploitable.
    """
    brut = unidecode(str(chaine or "")).strip().lower()
    brut = _UNITE.sub(" ", brut).strip()
    if not brut:
        return None, None
    trouve = _DEUX_VALEURS.match(brut)
    if trouve:
        return _nombre(trouve.group(1)), _nombre(trouve.group(2))
    trouve = _UNE_VALEUR.match(brut)
    if trouve:
        return _nombre(trouve.group(1)), None
    return None, None


def espacement_rang_cm(
    espacement: Optional[str],
    surface_m2: Optional[float] = None,
    culture: Optional[str] = None,
    journal: Optional[set] = None,
) -> Optional[int]:
    """[CA1, CA2, CA3] Espacement sur le rang, en centimètres entiers, ou None.

    Args:
        espacement : la chaîne libre du référentiel (`culture_config.espacement`)
        surface_m2 : la surface au sol de la fiche, qui sert de CONTRÔLE (CA3) —
                     jamais de source de repli : une surface seule ne donne
                     aucun espacement sur le rang
        culture    : le nom de la culture, pour que l'anomalie journalisée dise
                     laquelle corriger
        journal    : jeu des cultures déjà signalées pendant CETTE lecture, pour
                     qu'une incohérence de référentiel ne s'écrive qu'une fois
                     par lecture du plan (CA3). `None` = journaliser à chaque appel

    Returns:
        Un entier de 1 à 400, ou `None` pour « non renseigné » — jamais zéro,
        jamais une valeur de repli.
    """
    sur_le_rang, entre_rangs = _lire(espacement)
    if sur_le_rang is None:
        return None
    # Les bornes se contrôlent sur la valeur LUE, avant tout arrondi : « 0,5 cm »
    # n'est pas un espacement de potager, et l'arrondir d'abord l'aurait fait
    # entrer à 1 cm par la petite porte.
    if not ESPACEMENT_MIN_CM <= sur_le_rang <= ESPACEMENT_MAX_CM:
        return None
    # Arrondi au plus proche, la moitié vers le haut — `round()` de Python
    # arrondit 30,5 à 30 (arrondi bancaire), ce qui n'est pas ce qu'un jardinier
    # lit dans « 30,5 cm ».
    arrondi = int(sur_le_rang + 0.5)

    # [CA3] Contrôle de cohérence — la valeur est retenue quoi qu'il arrive.
    if entre_rangs and surface_m2:
        attendue = sur_le_rang * entre_rangs / 10000
        if abs(attendue - float(surface_m2)) > TOLERANCE_SURFACE * float(surface_m2):
            cle = (culture or "").strip().lower()
            if journal is None or cle not in journal:
                if journal is not None:
                    journal.add(cle)
                log.warning(
                    "🌱 RÉFÉRENTIEL   : espacement incohérent pour %r — "
                    "%s donne %.3f m² au sol, la fiche annonce %.3f m². "
                    "Valeur retenue : %d cm sur le rang.",
                    culture or "culture inconnue", espacement, attendue,
                    float(surface_m2), arrondi,
                )
    return arrondi

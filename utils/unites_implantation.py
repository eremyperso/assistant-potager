"""
[US-199] unites_implantation.py — le poquet et le mètre de rang, unités d'implantation.

Deux unités s'ajoutent au vocabulaire normalisé à l'écriture (US-168) :

* ``poquets`` — « 5 poquets de courge » : un segment du Plan = un poquet ;
* ``ml``      — « 3 mètres de carottes » : mètre de rang, jamais un m².

Python pur, aucun accès à la base ni au modèle : le chemin déterministe
(`llm.parseur_deterministe`), le chemin modèle (`app.services.evenements`) et le
garde-fou de pépinière lisent tous la même table, ce qui donne CA2 par
construction. Rien n'est converti : un poquet reste un poquet, un mètre de rang
reste un mètre de rang (CA5).
"""
import re
from typing import Optional

from unidecode import unidecode

UNITE_POQUETS = "poquets"
UNITE_ML = "ml"
UNITES_IMPLANTATION: frozenset[str] = frozenset({UNITE_POQUETS, UNITE_ML})

#: Gestes qui se comptent en poquets ou en mètres de rang. Une mise en godet, un
#: semis en pépinière se comptent en plants — voir `refus_en_pepiniere`.
GESTES_IMPLANTATION: frozenset[str] = frozenset({"semis", "plantation"})

# Formes qui ne laissent aucun doute, quel que soit le geste.
_POQUETS = frozenset({"poquet", "poquets"})
_ML = frozenset({
    "ml", "metre de rang", "metres de rang", "metre lineaire", "metres lineaires",
    "metre de ligne", "metres de ligne", "m de rang", "m lineaire", "m lineaires",
})

# « touffe » et « trou » ne sont des poquets que dans une phrase de semis ou de
# plantation : « une touffe de mauvaises herbes » n'est pas un geste (point de
# vigilance de l'US). Idem pour « mètre » seul, qui n'a de sens qu'en semis.
_POQUETS_DE_GESTE = frozenset({"trou", "trous", "touffe", "touffes"})
_ML_DE_GESTE = frozenset({"m", "metre", "metres"})

_SURFACES = frozenset({
    "m2", "m²", "m^2", "metre carre", "metres carres", "m carre", "m carres",
})


def _cle(brute: Optional[str]) -> str:
    """Minuscule, sans accent, sans point ni espace superflu."""
    return re.sub(r"\s+", " ", unidecode((brute or "").lower()).replace(".", "")).strip()


def normaliser_unite_implantation(brute: Optional[str], geste: Optional[str] = None) -> Optional[str]:
    """[CA1, CA3] Forme brute → ``"poquets"`` | ``"ml"`` | ``None``.

    ``None`` dit « ce n'est pas une unité d'implantation » : l'appelant garde sa
    propre normalisation (``m2`` reste ``m2``, ``plants`` reste ``plants``).
    ``geste`` est le geste canonique ; sans lui, seules les formes sans ambiguïté
    sont reconnues.
    """
    cle = _cle(brute)
    if not cle or cle in _SURFACES:
        return None
    if cle in _POQUETS:
        return UNITE_POQUETS
    if cle in _ML:
        return UNITE_ML
    if geste in GESTES_IMPLANTATION:
        if cle in _POQUETS_DE_GESTE:
            return UNITE_POQUETS
        if cle in _ML_DE_GESTE:
            return UNITE_ML
    return None


# Une unité dite dans la phrase, derrière un nombre : « 4 poquets », « 3 m de rang ».
_NOMBRE = r"\d+(?:[.,]\d+)?"
_RE_POQUETS = re.compile(rf"\b{_NOMBRE}\s*poquets?\b")
_RE_ML = re.compile(
    rf"\b{_NOMBRE}\s*(?:ml|m(?:etres?)?\s+(?:de\s+(?:rang|ligne)|lineaires?))\b"
)
_RE_METRE_SEUL = re.compile(rf"\b{_NOMBRE}\s*(?:metres?|m)\b(?!\s*(?:carres?|2|\^2))")


def unite_implantation_dans_texte(texte: Optional[str], geste: Optional[str] = None) -> Optional[str]:
    """[CA4] Unité d'implantation que la PHRASE prononce, ou ``None``.

    Le refus en pépinière ne peut pas se fier au seul champ ``unite`` : une mise
    en godet range sa quantité dans ``nb_plants_godets`` et efface l'unité, de
    sorte que « mis en godet 4 poquets de tomate » n'en garderait aucune trace.
    """
    norme = unidecode((texte or "").lower()).replace("²", "2").replace("’", "'")
    norme = re.sub(r"\s+", " ", norme)
    if _RE_POQUETS.search(norme):
        return UNITE_POQUETS
    if _RE_ML.search(norme):
        return UNITE_ML
    if geste in GESTES_IMPLANTATION and _RE_METRE_SEUL.search(norme):
        return UNITE_ML
    return None


def libelle_unite(unite: Optional[str], quantite: Optional[float] = None) -> str:
    """[CA7] L'unité écrite en toutes lettres pour le récapitulatif du bot :
    « 5 poquets », « 1 poquet », « 3 m de rang ». Toute autre unité traverse."""
    cle = (unite or "").strip().lower()
    if cle == UNITE_POQUETS:
        return "poquet" if quantite is not None and 0 < quantite <= 1 else "poquets"
    if cle == UNITE_ML:
        return "m de rang"
    return unite or ""

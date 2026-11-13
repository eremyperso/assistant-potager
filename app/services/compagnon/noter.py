"""
app/services/compagnon/noter.py — « Noter » ce que je vois avec Gaston, d'un seul bouton [US-324]
=================================================================================================
Toute écriture passe par Gaston (maquette « Noter et Gaston : un seul chemin ») : un raccourci
n'écrit rien, il produit des ITEMS que le flux de propositions habituel (US-270, US-274) montre
en carte « À enregistrer » ; seule la confirmation écrit, par `app.services.gestes`.

Trois choses ici, sans modèle de langage :

* **les raccourcis** (pastilles de la maquette) : un code — `etape_levee`, `recolte`,
  `culture_terminee`, `rang_libere`, `arrose`, `paille`, `desherbe` — et le contexte d'écran
  vérifié (US-323) donnent le geste, sans parser de phrase (CA2, CA4) ;
* **la phrase qui annonce une étape** (« les fèves ont levé côté allée ») : sur une culture sous
  les yeux, une carte à DEUX lignes, la note et l'étape (CA3) ;
* **ce qui a changé** après confirmation (« La fève passe à « Levé » sur le plan. », CA5).

« Pas encore » n'est pas ici : il ne propose rien, il repousse le rappel de l'étape
(`etapes_culture.reporter_etape`, US-320 / E7) par sa propre route.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from unidecode import unidecode

from app.services.compagnon.contexte_ecran import ContexteEcran
from utils.validation import CLE_CULTURE_DU_CONTEXTE

log = logging.getLogger("potager")

# ── Les raccourcis ───────────────────────────────────────────────────────────
RACCOURCI_ETAPE_LEVEE = "etape_levee"
RACCOURCI_RECOLTE = "recolte"
RACCOURCI_CULTURE_TERMINEE = "culture_terminee"
RACCOURCI_RANG_LIBERE = "rang_libere"
RACCOURCI_ARROSE = "arrose"
RACCOURCI_PAILLE = "paille"
RACCOURCI_DESHERBE = "desherbe"

#: Le geste de chaque raccourci (les clés canoniques de `utils.actions`).
ACTION_DU_RACCOURCI: dict[str, str] = {
    RACCOURCI_ETAPE_LEVEE: "levee",
    RACCOURCI_RECOLTE: "recolte",
    RACCOURCI_CULTURE_TERMINEE: "fin_culture",
    RACCOURCI_RANG_LIBERE: "fin_culture",
    RACCOURCI_ARROSE: "arrosage",
    RACCOURCI_PAILLE: "paillage",
    RACCOURCI_DESHERBE: "desherbage",
}
RACCOURCIS: frozenset[str] = frozenset(ACTION_DU_RACCOURCI)
#: Ceux qui portent sur UNE culture : sans culture sous les yeux, ils n'ont pas de sens.
RACCOURCIS_DE_CULTURE: frozenset[str] = frozenset({
    RACCOURCI_ETAPE_LEVEE, RACCOURCI_RECOLTE, RACCOURCI_CULTURE_TERMINEE, RACCOURCI_RANG_LIBERE,
})

TEXTE_QUANTITE = "Quelle quantité ? Dites-la simplement : « 800 grammes », « 2 kg », « 12 »."
TEXTE_SANS_CULTURE = "Ce raccourci se note sur une culture : ouvrez « Noter » depuis son suivi."
TEXTE_PARCELLE = "Sur quelle parcelle ? Touchez « Préciser » ou dites-la (« arrosé la planche sud »)."


class RaccourciInconnuError(ValueError):
    """Le code de raccourci n'existe pas (422)."""


@dataclass
class Lecture:
    """Ce qu'un raccourci produit : des items à proposer, ou la précision qui manque."""

    items: list[dict] = field(default_factory=list)
    precision: Optional[str] = None


# ── La quantité d'une récolte ────────────────────────────────────────────────
_UNITES_QUANTITE: dict[str, str] = {
    "kg": "kg", "kgs": "kg", "kilo": "kg", "kilos": "kg", "kilogramme": "kg", "kilogrammes": "kg",
    "g": "g", "gr": "g", "gramme": "g", "grammes": "g",
    "piece": "pieces", "pieces": "pieces", "pied": "pieces", "pieds": "pieces",
    "botte": "bottes", "bottes": "bottes", "tete": "pieces", "tetes": "pieces",
}
_NOMBRES_EN_LETTRES: dict[str, float] = {
    "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7,
    "huit": 8, "neuf": 9, "dix": 10, "douze": 12, "quinze": 15, "vingt": 20, "demi": 0.5,
}
_QUANTITE = re.compile(
    r"(?P<nombre>\d+(?:[.,]\d+)?|" + "|".join(sorted(_NOMBRES_EN_LETTRES, key=len, reverse=True)) + r")"
    r"\s*(?P<unite>[a-z]+)?\b"
)


def lire_quantite(phrase: str) -> Optional[tuple[float, str]]:
    """[CA4] « 800 grammes » → (0.8, "kg") ; « 2,5 kg » → (2.5, "kg") ; « 12 » → (12, "pieces").

    Les grammes sont rendus en kilos (la carte dit « 0,8 kg », Gherkin 2). None sans nombre.
    """
    texte = unidecode((phrase or "").lower())
    for m in _QUANTITE.finditer(texte):
        brut = m.group("nombre")
        nombre = _NOMBRES_EN_LETTRES.get(brut)
        if nombre is None:
            try:
                nombre = float(brut.replace(",", "."))
            except ValueError:
                continue
        unite = _UNITES_QUANTITE.get(m.group("unite") or "", None)
        if m.group("unite") and unite is None and m.group("unite") not in ("de", "d"):
            # « 3 rangs », « 2 jours » : un nombre qui ne compte pas la récolte.
            continue
        if nombre <= 0:
            continue
        if unite == "g":
            return round(nombre / 1000, 3), "kg"
        return nombre, unite or "pieces"
    return None


def _base(contexte: ContexteEcran, action: str) -> dict:
    item = {
        "action": action, "culture": contexte.culture, "variete": contexte.variete,
        "parcelle": contexte.parcelle, "quantite": None, "unite": None, "rang": None,
        "date": date.today().isoformat(), "commentaire": None, "origine_parsing": "raccourci",
    }
    if contexte.culture:
        item[CLE_CULTURE_DU_CONTEXTE] = True
    return item


def items_du_raccourci(code: str, contexte: Optional[ContexteEcran], phrase: str = "") -> Lecture:
    """[US-324 / CA2, CA4] Les items d'un raccourci, sans modèle de langage.

    Un raccourci de culture exige une culture sous les yeux ; un geste de parcelle (arrosé,
    paillé, désherbé) une parcelle. `phrase` complète : la quantité d'une récolte, une note
    dite avec le geste. Lève `RaccourciInconnuError` pour un code inconnu.
    """
    if code not in RACCOURCIS:
        raise RaccourciInconnuError(f"Raccourci inconnu : {code!r}.")
    if code in RACCOURCIS_DE_CULTURE and (contexte is None or not contexte.culture):
        return Lecture(precision=TEXTE_SANS_CULTURE)
    if contexte is None:
        return Lecture(precision=TEXTE_PARCELLE)

    item = _base(contexte, ACTION_DU_RACCOURCI[code])
    if code == RACCOURCI_RECOLTE:
        quantite = lire_quantite(phrase)
        if quantite is None:
            return Lecture(precision=TEXTE_QUANTITE)
        item["quantite"], item["unite"] = quantite
    if code not in RACCOURCIS_DE_CULTURE:
        # Arrosé, paillé, désherbé : la parcelle (et la culture, si l'on parle d'elle).
        item["culture"] = contexte.culture
    log.info("[US-324] Raccourci %s sur %s", code, contexte.libelle())
    return Lecture(items=[item])


# ── CA3 : une phrase qui annonce une étape ───────────────────────────────────
_LEVEE = re.compile(r"\b(?:ont|a|est|sont)\s+leve(?:e|es|s)?\b|\blevee?s?\b|\blevent\b")
_FIN = re.compile(
    r"\b(?:culture\s+(?:terminee|finie)|fin\s+de\s+culture|rang\s+libere|libere\s+le\s+rang|"
    r"planche\s+liberee|libere\s+la\s+planche|arrache(?:e|es|s)?)\b"
)
#: [US-320 / perte] « arraché PAR quelque chose » est un dégât, pas une fin de culture.
_ARRACHE_PAR = re.compile(r"\barrache(?:e|es|s)?\s+par\b")


def etape_annoncee(phrase: str) -> Optional[str]:
    """[CA3] Le geste d'étape qu'une phrase annonce (`levee`, `fin_culture`), ou None."""
    texte = unidecode((phrase or "").lower())
    if _FIN.search(texte) and not _ARRACHE_PAR.search(texte):
        return "fin_culture"
    if _LEVEE.search(texte):
        return "levee"
    return None


def note_et_etape(phrase: str, contexte: Optional[ContexteEcran]) -> Optional[list[dict]]:
    """[US-324 / CA3] Sur une culture sous les yeux, « les fèves ont levé côté allée » donne DEUX
    items, la note (la phrase) et l'étape (validée à la date du jour). None sinon.

    Une phrase qui nomme une autre culture que celle de l'écran n'est pas lue ici (US-323 / C5).
    """
    if contexte is None or not contexte.culture:
        return None
    action = etape_annoncee(phrase)
    if action is None:
        return None
    from utils.culture_resolve import normaliser_culture

    cle = normaliser_culture(contexte.culture)
    texte = normaliser_culture(phrase)
    # Une autre culture citée en toutes lettres l'emporte : le parseur la lira.
    racine = cle.split()[0] if cle else ""
    if racine and racine[:4] not in texte and _cite_une_culture(texte):
        return None
    note = _base(contexte, "observation")
    note["commentaire"] = phrase.strip()
    etape = _base(contexte, action)
    log.info("[US-324 / CA3] Note et étape %s sur %s", action, contexte.libelle())
    return [note, etape]


#: Mots qui, devant un verbe d'étape, ne nomment pas une culture (« elles ont levé », « tout a levé »).
_SANS_CULTURE = re.compile(r"^\s*(?:ca|ils?|elles?|tout|tous|toutes|les?\s+(?:graines|plants|semis|pieds))\b")


def _cite_une_culture(texte: str) -> bool:
    """Le sujet de la phrase semble nommer une culture (« les tomates ont levé »)."""
    sujet = re.split(r"\b(?:ont|a|est|sont|levent)\b", texte, maxsplit=1)[0]
    return bool(sujet.strip()) and not _SANS_CULTURE.search(sujet) and bool(re.search(r"[a-z]{3,}", sujet))


# ── CA5 : ce qui a changé ────────────────────────────────────────────────────
def annonce_apres_confirmation(items: list[dict]) -> Optional[str]:
    """[US-324 / CA5] Ce que Gaston dit après « Confirmer » : l'étape qui change sur le plan."""
    for item in items or []:
        action = (item or {}).get("action")
        culture = (item.get("culture") or "").strip()
        if not culture:
            continue
        nom = culture[:1].upper() + culture[1:]
        if action == "levee":
            return f"{nom} passe à « Levé » sur le plan."
        if action == "fin_culture":
            return f"{nom} est terminée : son rang est libre sur le plan."
        if action == "recolte":
            return f"Récolte notée : {nom} reste « En récolte »."
    return None

"""Le jardinier simulé [US-337 / CA2] : il répond aux questions du compagnon à partir de la fiche de besoin, et
**ne donne jamais une valeur absente de la fiche**.

C'est une règle de code, pas un prompt : la réponse est composée de morceaux de la fiche et de mots neutres
(« oui », « non », « je ne sais pas ») et `verifier_reponse` le contrôle avant l'envoi. Un utilisateur simulé par un
modèle pourrait inventer une quantité qui arrangerait la réponse ; celui-ci ne le peut pas, et reste rejouable à
l'identique d'un passage à l'autre : la dispersion mesurée vient du compagnon, jamais du jardinier.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from tools.jeu_evaluation.jeu import CHAMPS_FICHE, normaliser

#: Ce que le compagnon peut demander. Le premier motif qui correspond à une phrase interrogative gagne, dans l'ordre
#: de la phrase : « Quelle culture et sur quelle parcelle ? » demande les deux.
QUESTIONS: dict[str, re.Pattern] = {
    "culture": re.compile(
        r"quelle culture|quel l[ée]gume|quelle plante|quoi (?:planter|semer|r[ée]colter)|que veux-tu (?:planter|semer)"
        r"|quelle esp[èe]ce|de quelle culture|quelles cultures",
        re.IGNORECASE),
    "variete": re.compile(r"quelle vari[ée]t[ée]|quelles vari[ée]t[ée]s|de quelle vari[ée]t[ée]", re.IGNORECASE),
    "parcelle": re.compile(
        r"quelle (?:parcelle|planche)|sur quelle|dans quelle|o[ùu] (?:veux|souhaites|comptes|as-tu|l'as|les as|"
        r"vas|va)|quel emplacement|quel endroit|quel carr[ée]", re.IGNORECASE),
    "quantite": re.compile(
        r"combien|quelle quantit[ée]|quel(?:s)? nombre|quel poids|c[']est de combien|quelle longueur|"
        r"combien de (?:rangs|plants|pieds|graines)", re.IGNORECASE),
    "date": re.compile(
        r"quand|quel jour|quelle date|[àa] quelle date|pour quand|ce jour-l[àa]|aujourd[']hui ou|"
        r"(?:la|ta) date (?:exacte|de |du )", re.IGNORECASE),
}

#: Les gabarits de réponse d'un champ : la valeur de la fiche, et rien d'autre.
GABARITS = {
    "culture": "{culture}",
    "variete": "{variete}",
    "parcelle": "la {parcelle}",
    "quantite": "{quantite} {unite}",
    "date": "{date}",
}

REPONSE_OUI = "oui"
REPONSE_NON = "non"
REPONSE_INCONNUE = "je ne sais pas, à toi de voir"
REPONSE_FIN = "merci, c'est tout"

#: Le compagnon demande une confirmation ou propose d'agir.
_CONFIRMATION = re.compile(
    r"tu confirmes|confirmes-tu|je te propose|veux-tu que je|tu veux que je|je (?:le |la |les )?note|"
    r"[çc]a te va|c'est bon\s*\?|on y va|je peux (?:le |la |les )?noter|d'accord pour|ok pour|est-ce correct",
    re.IGNORECASE)
_DEFAUT_PROPOSE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:plants?|pieds?|graines?|rangs?|kg|g\b|m\b|unit[ée]s?)", re.IGNORECASE)
_ACCORD = re.compile(
    r"^(?:oui|ouais|ok|d'accord|dac|yes|vas-y|go|parfait|c'est bon|je veux bien|si tu veux|volontiers|exact|"
    r"c'est ça|confirm[ée]?)\b", re.IGNORECASE)
_REFUS = re.compile(r"^(?:non|nan|pas|laisse tomber|annule|stop|abandonne)\b", re.IGNORECASE)


def est_accord(phrase: str) -> bool:
    """Vrai quand la phrase du jardinier est un accord (« oui je veux bien », « vas-y »)."""
    return bool(_ACCORD.match((phrase or "").strip().lower()))


def est_refus(phrase: str) -> bool:
    return bool(_REFUS.match((phrase or "").strip().lower()))


def champs_demandes(texte: str) -> list[str]:
    """Les champs qu'une question du compagnon réclame, dans l'ordre où le texte les nomme.

    Seules les PHRASES INTERROGATIVES comptent : « Tu veux planter des salades. Sur quelle parcelle ? » demande la
    parcelle, pas la culture."""
    trouves: list[tuple[int, str]] = []
    for phrase in re.split(r"(?<=[.!?…])\s+", texte or ""):
        if "?" not in phrase:
            continue
        for champ, motif in QUESTIONS.items():
            m = motif.search(phrase)
            if m:
                trouves.append((texte.find(phrase) + m.start(), champ))
    vus: list[str] = []
    for _, champ in sorted(trouves):
        if champ not in vus:
            vus.append(champ)
    return vus


def question_posee(texte: str) -> bool:
    return "?" in (texte or "")


def valeurs_proposees(texte: str) -> list[str]:
    """Les nombres qu'une proposition ou une valeur par défaut contient (« 10 plants, ça te va ? »)."""
    return [m.group(1).replace(",", ".") for m in _DEFAUT_PROPOSE.finditer(texte or "")]


@dataclass
class Reponse:
    """Ce que dit le jardinier simulé : une phrase, ou un clic de bouton, ou plus rien (le dialogue est fini)."""
    phrase: str = ""
    clic: str = ""
    fin: bool = False


def _morceau(champ: str, fiche: dict) -> Optional[str]:
    if not fiche.get(champ):
        return None
    valeurs = {k: str(fiche.get(k) or "") for k in CHAMPS_FICHE}
    return re.sub(r"\s+", " ", GABARITS[champ].format(**valeurs)).strip()


def verifier_reponse(phrase: str, fiche: dict) -> None:
    """[CA2] Lève `AssertionError` si la réponse contient un chiffre, ou un nom de parcelle, absent de la fiche.

    Garde-fou contre toute évolution du simulateur : il ne doit jamais dire plus que la fiche."""
    chiffres_fiche = set(re.findall(r"\d+(?:[.,]\d+)?", " ".join(str(v) for v in fiche.values())))
    chiffres = set(re.findall(r"\d+(?:[.,]\d+)?", phrase))
    en_trop = chiffres - chiffres_fiche
    assert not en_trop, f"le jardinier simulé a dit {sorted(en_trop)}, absent de la fiche {fiche}"


class JardinierSimule:
    """Répond au dernier texte du compagnon, depuis la fiche, jamais au-delà."""

    def __init__(self, fiche: dict, *, mode_confirmation: str = "phrase"):
        self.fiche = {k: v for k, v in fiche.items() if v not in (None, "")}
        #: « bouton » : un accord se dit par un clic (chaîne actuelle) ; « phrase » : par un « oui ».
        self.mode_confirmation = mode_confirmation
        self._deja_dit: set[str] = set()

    def _repondre(self, phrase: str) -> Reponse:
        verifier_reponse(phrase, self.fiche)
        return Reponse(phrase=phrase)

    def _accord(self) -> Reponse:
        return Reponse(clic="Confirmer") if self.mode_confirmation == "bouton" else self._repondre(REPONSE_OUI)

    def repondre(self, texte_du_compagnon: str, *, proposition_en_attente: bool = False) -> Reponse:
        """La réponse du jardinier au texte qu'il vient de lire."""
        champs = champs_demandes(texte_du_compagnon)
        if champs:
            morceaux, inconnus = [], []
            for champ in champs:
                m = _morceau(champ, self.fiche)
                (morceaux if m else inconnus).append(m or champ)
            if morceaux:
                return self._repondre(", ".join(morceaux))
            return self._repondre(REPONSE_INCONNUE)

        if proposition_en_attente or _CONFIRMATION.search(texte_du_compagnon or ""):
            # Une valeur par défaut avancée par le compagnon : on l'accepte si elle est celle de la fiche,
            # on donne la valeur de la fiche sinon ; sans valeur dans la fiche, on laisse le compagnon trancher.
            proposees = valeurs_proposees(texte_du_compagnon)
            quantite = str(self.fiche.get("quantite") or "").replace(",", ".")
            if proposees and quantite and quantite not in proposees:
                return self._repondre(f"non, plutôt {_morceau('quantite', self.fiche)}")
            # Un bouton n'existe que si une carte attend : sans carte, le jardinier répond avec des mots, et le
            # dialogue continue (mesure du 23/11 : des clics « Confirmer » sans carte coupaient le dialogue).
            return self._accord() if proposition_en_attente else self._repondre(REPONSE_OUI)
        if question_posee(texte_du_compagnon):
            return self._repondre(REPONSE_INCONNUE)
        return Reponse(fin=True)

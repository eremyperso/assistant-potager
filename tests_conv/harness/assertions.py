"""Vérifications déterministes d'un tour : texte, boutons, base de test. Aucune n'appelle un modèle."""
import re
from dataclasses import dataclass, field
from typing import Optional

from .parser import Verification
from .texte import norm


@dataclass
class Observation:
    """Tout ce que le harnais a vu pendant un tour."""
    messages: list[str] = field(default_factory=list)      # texte final de chaque message du bot
    boutons: list[str] = field(default_factory=list)       # libellés de tous les boutons rencontrés
    latence_s: float = 0.0                                 # envoi → première réponse
    evenements: list[dict] = field(default_factory=list)   # créés pendant le tour (base)
    actions: int = 0                                       # `actions_menees` réussies créées pendant le tour
    outils: tuple[str, ...] = ()                           # outils notés dans `echanges_conversation`
    silence: bool = False                                  # aucune réponse avant le délai

    @property
    def texte(self) -> str:
        return "\n".join(self.messages)


@dataclass
class Resultat:
    verification: Verification
    ok: Optional[bool]        # None : non évaluée (juge)
    detail: str = ""


def _egal(attendu: str, obtenu) -> bool:
    if obtenu is None:
        return False
    try:
        return abs(float(attendu.replace(",", ".")) - float(obtenu)) < 1e-9
    except (TypeError, ValueError):
        return norm(attendu) == norm(str(obtenu))


def _evenement_correspond(attendu: str, evenement: dict) -> bool:
    for morceau in attendu.split(","):
        champ, _, valeur = morceau.partition("=")
        if not _egal(valeur.strip(), evenement.get(norm(champ).replace(" ", "_"))):
            return False
    return True


def evaluer(v: Verification, obs: Observation) -> Resultat:
    g = v.genre
    texte_norm = norm(obs.texte)
    if g == "texte_contient":
        ok = norm(v.valeur) in texte_norm
        return Resultat(v, ok, "" if ok else f"« {v.valeur} » absent de la réponse")
    if g == "texte_absent":
        ok = norm(v.valeur) not in texte_norm
        return Resultat(v, ok, "" if ok else f"« {v.valeur} » présent dans la réponse")
    if g == "texte_regex":
        ok = re.search(v.valeur, obs.texte, re.IGNORECASE | re.DOTALL) is not None
        return Resultat(v, ok, "" if ok else f"motif /{v.valeur}/ sans correspondance")
    if g == "bouton":
        ok = any(norm(v.valeur) in norm(b) for b in obs.boutons)
        return Resultat(v, ok, "" if ok else f"bouton « {v.valeur} » absent (vus : {', '.join(obs.boutons) or 'aucun'})")
    if g == "aucun_bouton":
        return Resultat(v, not obs.boutons, "" if not obs.boutons else f"boutons vus : {', '.join(obs.boutons)}")
    if g == "aucune_ecriture":
        n = len(obs.evenements) + obs.actions
        return Resultat(v, n == 0, "" if n == 0 else f"{len(obs.evenements)} événement(s), {obs.actions} action(s) écrits")
    if g == "ecriture":
        types = [e.get("type_action") for e in obs.evenements]
        ok = any(norm(v.valeur) == norm(str(t)) for t in types)
        return Resultat(v, ok, "" if ok else f"aucun événement « {v.valeur} » (écrits : {', '.join(map(str, types)) or 'aucun'})")
    if g == "evenement":
        ok = any(_evenement_correspond(v.valeur, e) for e in obs.evenements)
        return Resultat(v, ok, "" if ok else f"aucun événement ne correspond à {v.valeur} (écrits : {obs.evenements or 'aucun'})")
    if g == "outil":
        ok = any(norm(v.valeur) == norm(o) for o in obs.outils)
        return Resultat(v, ok, "" if ok else f"outil « {v.valeur} » non appelé (appelés : {', '.join(obs.outils) or 'aucun'})")
    if g == "latence_max":
        limite = float(v.valeur.replace(",", ".").removesuffix("s"))
        return Resultat(v, obs.latence_s <= limite, f"{obs.latence_s:.1f} s pour {limite:g} s max")
    if g == "juge":
        return Resultat(v, None, "juge LLM non branché (phase 2)")
    raise ValueError(f"genre de vérification inconnu : {g}")


def evaluer_tour(verifications, obs: Observation) -> list[Resultat]:
    return [evaluer(v, obs) for v in verifications]

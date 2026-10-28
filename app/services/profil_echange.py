"""
app/services/profil_echange.py — Profil d'échange du compagnon [US-258]
-----------------------------------------------------------------------
Le compagnon appelle le jardinier par son prénom et parle sur le ton choisi.
Le profil est rangé par COUPLE (jardinier × potager) : un registre différent sur
deux potagers est respecté (CA8).

  - **Prénom** : proposé (prénom Telegram, sinon nom du compte), jamais supposé
    (CA1) ; validé (CA2) ; une saisie qui ressemble à une phrase est refusée (CA5).
  - **Registre** : `sobre`, `voisin` (défaut) ou `gouailleur` (CA3). Il change le
    TON, jamais le fond : mêmes faits, mêmes prudences, mêmes sources (CA7).
  - **Injection** : le profil entre dans la partie VARIABLE du prompt, balisé comme
    une donnée, jamais mêlé aux consignes (CA4, R10).

Aucun appel au modèle ici.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.services.context import TenantContext
from database.models import PotagerMembre

log = logging.getLogger("potager")

REGISTRE_SOBRE = "sobre"
REGISTRE_VOISIN = "voisin"
REGISTRE_GOUAILLEUR = "gouailleur"
REGISTRES: tuple[str, ...] = (REGISTRE_SOBRE, REGISTRE_VOISIN, REGISTRE_GOUAILLEUR)
REGISTRE_DEFAUT = REGISTRE_VOISIN

#: Le libellé que voit le jardinier sur les boutons et dans `/profil`.
LIBELLES_REGISTRE: dict[str, str] = {
    REGISTRE_SOBRE: "Sobre",
    REGISTRE_VOISIN: "Comme un voisin",
    REGISTRE_GOUAILLEUR: "Gouailleur",
}

PRENOM_LONGUEUR_MAX = 30
#: Un prénom compte un ou deux mots (« Marie Claire », « Jean-Pierre ») : au-delà,
#: c'est une phrase, et une phrase n'est pas un prénom (CA5).
PRENOM_MOTS_MAX = 2
_PRENOM = re.compile(r"^[^\W\d_]+(?:[ \-][^\W\d_]+)*$", re.UNICODE)

#: Balise de la donnée dans le prompt (CA4).
BALISE_PROFIL = "profil_jardinier"

ERREUR_PRENOM = (
    "Je n'ai pas retenu ce prénom : des lettres, des espaces ou des tirets, "
    f"{PRENOM_LONGUEUR_MAX} caractères au plus, et pas une phrase."
)


@dataclass(frozen=True)
class Profil:
    """Ce que le compagnon sait du jardinier sur CE potager."""
    prenom: Optional[str] = None
    registre: str = REGISTRE_DEFAUT
    accueilli: bool = False


def valider_prenom(saisie: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """[CA2, CA5] → (prénom mis en forme, None) ou (None, explication du refus)."""
    prenom = " ".join((saisie or "").split())
    if (not prenom or len(prenom) > PRENOM_LONGUEUR_MAX or not _PRENOM.match(prenom)
            or len(prenom.split()) > PRENOM_MOTS_MAX):
        return None, ERREUR_PRENOM
    return "-".join(" ".join(p.capitalize() for p in morceau.split()) for morceau in prenom.split("-")), None


def prenom_propose(first_name: Optional[str], nom_compte: Optional[str] = None) -> Optional[str]:
    """[CA1] Le prénom à PROPOSER : celui de Telegram, sinon le nom du compte web.
    None si aucun des deux n'est un prénom valide."""
    for candidat in (first_name, (nom_compte or "").split(" ")[0] if nom_compte else None):
        prenom, _ = valider_prenom(candidat)
        if prenom:
            return prenom
    return None


def _membre(db: Session, ctx: TenantContext) -> Optional[PotagerMembre]:
    """L'appartenance du jardinier à CE potager, qui porte son profil."""
    if ctx.user_id is None:
        return None
    return (db.query(PotagerMembre)
            .filter(PotagerMembre.user_id == ctx.user_id, PotagerMembre.potager_id == ctx.potager_id)
            .first())


def lire(db: Session, ctx: TenantContext) -> Optional[Profil]:
    """Le profil du couple (jardinier, potager), ou None sans appartenance."""
    membre = _membre(db, ctx)
    if membre is None:
        return None
    return Profil(prenom=membre.prenom_compagnon, registre=membre.registre_compagnon or REGISTRE_DEFAUT,
                  accueilli=bool(membre.compagnon_accueilli))


def est_premier_contact(db: Session, ctx: TenantContext) -> bool:
    """[CA1] Le jardinier n'a pas encore été accueilli sur ce potager."""
    profil = lire(db, ctx)
    return profil is not None and not profil.accueilli


def marquer_accueilli(db: Session, ctx: TenantContext) -> None:
    """Le premier contact a eu lieu : le compagnon ne redemande plus d'office."""
    membre = _membre(db, ctx)
    if membre is not None:
        membre.compagnon_accueilli = True
        db.commit()


def definir_prenom(db: Session, ctx: TenantContext, saisie: str) -> tuple[Optional[Profil], Optional[str]]:
    """[CA2] Enregistre le prénom validé → (profil, None) ou (None, explication)."""
    prenom, erreur = valider_prenom(saisie)
    membre = _membre(db, ctx)
    if erreur or membre is None:
        log.info("[US-258] Prénom refusé (%r)", (saisie or "")[:40])
        return None, erreur or ERREUR_PRENOM
    membre.prenom_compagnon, membre.compagnon_accueilli = prenom, True
    db.commit()
    log.info("[US-258] Prénom enregistré (user %s, potager %s)", ctx.user_id, ctx.potager_id)
    return lire(db, ctx), None


def definir_registre(db: Session, ctx: TenantContext, registre: str) -> Optional[Profil]:
    """[CA3] Enregistre le registre ; None si ce n'en est pas un ou sans appartenance."""
    membre = _membre(db, ctx)
    if registre not in REGISTRES or membre is None:
        return None
    membre.registre_compagnon, membre.compagnon_accueilli = registre, True
    db.commit()
    log.info("[US-258] Registre %s (user %s, potager %s)", registre, ctx.user_id, ctx.potager_id)
    return lire(db, ctx)


def bloc_prompt(profil: Optional[Profil]) -> str:
    """[CA4] Le profil comme DONNÉE balisée, pour la partie variable du prompt.

    Le registre vient d'une liste fermée et le prénom a passé `valider_prenom` :
    aucun caractère de balisage ne peut y entrer. Vide sans profil.
    """
    if profil is None:
        return ""
    lignes = [f"<{BALISE_PROFIL}>"]
    if profil.prenom:
        lignes.append(f"prénom : {profil.prenom}")
    lignes.append(f"registre : {profil.registre if profil.registre in REGISTRES else REGISTRE_DEFAUT}")
    lignes.append(f"</{BALISE_PROFIL}>")
    return "\n".join(lignes) + "\n"

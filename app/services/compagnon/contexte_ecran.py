"""
app/services/compagnon/contexte_ecran.py — Ce que le jardinier a sous les yeux [US-323]
========================================================================================
Ouvert depuis le plan (« Noter » d'un suivi de culture, d'une parcelle), le panneau du
compagnon envoie avec chaque phrase le CONTEXTE d'écran : la culture sélectionnée, sinon
la parcelle, sinon rien (tout le potager) — règle C1.

* **C4** — le contexte voyage en IDENTIFIANTS (parcelle, culture, variété, rang), jamais en
  texte reconstruit. `resoudre` les vérifie contre le potager actif : un identifiant étranger
  lève `ContexteIntrouvableError` (404 « Contexte introuvable », sans dire ce qui manque).
* **C5** — le contexte est une PRÉCISION PAR DÉFAUT. `appliquer` complète un geste qui ne dit
  ni culture ni parcelle ; une phrase qui nomme une autre culture ou une autre parcelle
  l'emporte (« j'ai arrosé la serre » va à la serre, pas au chou).
* **CA3** — un constat sans geste (« feuilles du bas un peu jaunies ») dit sur une culture
  devient une NOTE de cette culture : une observation datée du jour, à confirmer.

Rien n'est écrit ici : le module complète des items que le chemin habituel propose
(carte à confirmer, US-270) et que seule la confirmation écrit.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.services.context import TenantContext
from utils.culture_resolve import normaliser_culture
from utils.parcelles import normalize_parcelle_name
from utils.validation import CLE_CULTURE_DU_CONTEXTE

log = logging.getLogger("potager")

#: Au-delà, un numéro de rang n'est pas un rang (même borne que la géométrie, US-326).
RANG_MAX = 99

NIVEAU_CULTURE = "culture"
NIVEAU_PARCELLE = "parcelle"

ACTION_NOTE = "observation"


class ContexteIntrouvableError(LookupError):
    """Un identifiant du contexte n'appartient pas au potager actif (ou n'existe pas)."""


@dataclass(frozen=True)
class ContexteEcran:
    """Le contexte d'écran VÉRIFIÉ : noms canoniques relus en base, jamais ceux du client."""

    parcelle_id: int
    parcelle: str
    culture: Optional[str] = None
    variete: Optional[str] = None
    rang: Optional[int] = None

    @property
    def niveau(self) -> str:
        """[C1] La culture si elle est désignée, sinon la parcelle."""
        return NIVEAU_CULTURE if self.culture else NIVEAU_PARCELLE

    def libelle(self) -> str:
        """« chou de Bruxelles Groninger · Planche centrale, rang 3 » — pour le prompt et les journaux."""
        lieu = self.parcelle + (f", rang {self.rang}" if self.rang else "")
        if not self.culture:
            return lieu
        culture = " ".join(x for x in (self.culture, self.variete) if x)
        return f"{culture} · {lieu}"

    def pour_l_agent(self) -> dict:
        """[C5] Ce que l'agent lit : des noms, pas des identifiants techniques."""
        donnees: dict[str, Any] = {"parcelle": self.parcelle}
        if self.rang:
            donnees["rang"] = self.rang
        if self.culture:
            donnees["culture"] = self.culture
            if self.variete:
                donnees["variete"] = self.variete
        return donnees

    def pour_le_journal(self) -> dict:
        """[CA6] Ce que l'échange garde : identifiants ET noms, pour mesurer l'effet du contexte."""
        return {"niveau": self.niveau, "parcelle_id": self.parcelle_id, **self.pour_l_agent()}


# ═════════════════════════════════════════════════════════════════════════════
# C4 — vérifier les identifiants
# ═════════════════════════════════════════════════════════════════════════════
def _entier(valeur: Any) -> Optional[int]:
    if valeur is None or valeur == "":
        return None
    if isinstance(valeur, bool):
        raise ContexteIntrouvableError("rang")
    try:
        return int(valeur)
    except (TypeError, ValueError):
        raise ContexteIntrouvableError("identifiant illisible") from None


def resoudre(
    db: Session,
    ctx: TenantContext,
    parcelle_id: Any = None,
    culture: Optional[str] = None,
    variete: Optional[str] = None,
    rang: Any = None,
    date_ref: Optional[date] = None,
) -> Optional[ContexteEcran]:
    """[US-323 / C4, CA2] Le contexte d'écran vérifié contre le potager actif, ou None (tout le potager).

    Lève `ContexteIntrouvableError` quand un identifiant est étranger au potager actif : parcelle
    d'un autre potager ou inexistante, culture qui n'y est pas en place, rang hors de 1 à 99.
    Une culture ou un rang sans parcelle n'a pas de sens : refusé aussi.
    """
    from app.services import plan as svc_plan
    from app.services.parcelles import get_parcelle

    pid = _entier(parcelle_id)
    numero = _entier(rang)
    culture = (culture or "").strip() or None
    variete = (variete or "").strip() or None
    if pid is None:
        if culture or variete or numero is not None:
            raise ContexteIntrouvableError("contexte sans parcelle")
        return None

    parcelle = get_parcelle(db, ctx, pid)
    if parcelle is None or parcelle.actif is False:
        raise ContexteIntrouvableError("parcelle")

    # Le rang situe la culture pour l'affichage et le journal ; il ne s'écrit sur aucun geste.
    # Borné comme une position de rang (US-326), sans lire le nombre de rangs déclaré (US-197 / CA7).
    if numero is not None and not 1 <= numero <= RANG_MAX:
        raise ContexteIntrouvableError("rang")

    if culture is None:
        return ContexteEcran(parcelle_id=parcelle.id, parcelle=parcelle.nom, rang=numero)

    cle_culture = normaliser_culture(culture)
    cle_variete = (variete or "").lower()
    occupation = svc_plan.get_occupation(db, ctx, date_ref) or {}
    entree = next(
        (e for e in occupation.get(parcelle.nom, []) or []
         if normaliser_culture(e.get("culture") or "") == cle_culture
         and (e.get("variete") or "").strip().lower() == cle_variete),
        None,
    )
    if entree is None:
        raise ContexteIntrouvableError("culture")
    return ContexteEcran(
        parcelle_id=parcelle.id, parcelle=parcelle.nom,
        culture=entree.get("culture"), variete=entree.get("variete") or None, rang=numero,
    )


# ═════════════════════════════════════════════════════════════════════════════
# C5 — la précision par défaut
# ═════════════════════════════════════════════════════════════════════════════
def _meme_parcelle(nom: Optional[str], contexte: ContexteEcran) -> bool:
    return normalize_parcelle_name(nom or "") == normalize_parcelle_name(contexte.parcelle)


def _meme_culture(nom: Optional[str], contexte: ContexteEcran) -> bool:
    return normaliser_culture(nom or "") == normaliser_culture(contexte.culture or "")


def _note(texte: str, contexte: ContexteEcran) -> dict:
    """[CA3] Le constat devient une note de la culture, datée du jour (la validation l'exige)."""
    return {
        "action": ACTION_NOTE, "culture": contexte.culture, "variete": contexte.variete,
        "parcelle": contexte.parcelle, "quantite": None, "unite": None, "rang": None,
        "date": date.today().isoformat(), "commentaire": texte.strip(),
        "origine_parsing": "contexte_ecran", CLE_CULTURE_DU_CONTEXTE: True,
    }


def appliquer(items: list, contexte: Optional[ContexteEcran], texte: str) -> list:
    """[US-323 / C5, CA3, CA4] Complète les items du parseur avec le contexte d'écran.

    * un item qui nomme une AUTRE parcelle, ou une autre culture que celle du contexte, est
      laissé tel quel : la phrase l'emporte ;
    * sinon, la parcelle manquante est celle du contexte, et la culture manquante celle du
      contexte quand il en désigne une ;
    * une observation reçoit le jour quand la phrase n'en dit pas, et la phrase pour texte ;
    * aucun geste lu (un constat) et une culture sous les yeux : une note de cette culture.

    Le rang du contexte n'est pas reporté sur le geste : il situe la culture, il ne dit pas
    où une nouvelle installation se fait (la position se dit, US-326).
    """
    if contexte is None:
        return items
    complets: list = []
    for item in items or []:
        if not isinstance(item, dict):
            complets.append(item)
            continue
        dite = item.get("parcelle")
        if dite and not _meme_parcelle(dite, contexte):
            complets.append(item)
            continue
        culture_dite = item.get("culture")
        if contexte.culture and culture_dite and not _meme_culture(culture_dite, contexte):
            complets.append(item)
            continue
        item = dict(item)
        if not dite:
            item["parcelle"] = contexte.parcelle
        if contexte.culture and not culture_dite:
            item["culture"] = contexte.culture
            item[CLE_CULTURE_DU_CONTEXTE] = True  # vient de la base : pas une culture hallucinée
            if contexte.variete and not item.get("variete"):
                item["variete"] = contexte.variete
        if (item.get("action") or "").lower() == ACTION_NOTE:
            item["date"] = item.get("date") or date.today().isoformat()
            item["commentaire"] = item.get("commentaire") or texte.strip()
        complets.append(item)

    a_un_geste = any(isinstance(i, dict) and i.get("action") for i in complets)
    if not a_un_geste and contexte.culture and (texte or "").strip():
        log.info("[US-323 / CA3] Constat noté sur la culture sous les yeux : %s", contexte.libelle())
        return [_note(texte, contexte)]
    return complets


def oriente_vers_un_geste(texte: str, contexte: Optional[ContexteEcran]) -> bool:
    """[US-323 / C5, CA3] Avec une culture ou une parcelle sous les yeux, une phrase qui n'est pas
    une question est un geste ou une note : elle ne part pas à la classification par le modèle."""
    if contexte is None:
        return False
    from app.services.agent.projection import est_interrogative

    return not est_interrogative(texte or "")

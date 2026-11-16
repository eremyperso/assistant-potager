"""
app/services/pilotage/chiffrage.py — Rejouer le coût des lignes de `conso_tokens` [US-309 / CA8]
================================================================================================
Les lignes écrites avant la migration v75 n'ont ni coût ni version de grille. Ce service les
chiffre **d'après une grille donnée** (`tools/chiffrer_historique.py` en est la ligne de commande).

* **Simulation par défaut** : sans `appliquer=True`, rien n'est écrit, le bilan dit ce qui le serait.
* **Jamais une ligne déjà chiffrée** : seules les lignes sans coût ET sans version de grille sont
  examinées. Une ligne écrite en direct dont le modèle était absent de la grille (coût nul, version
  renseignée) n'est donc pas réécrite : sa version dit la grille de son jour.
* Les lignes rejouées sont **marquées** par la `tarif_version` de la grille utilisée.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable

from sqlalchemy.orm import Session

from app.services.pilotage import tarifs
from database.models import ConsoTokens

log = logging.getLogger("potager")

TAILLE_LOT = 500


@dataclass
class BilanRejeu:
    """Ce que le rejeu a examiné, chiffré ou laissé sans coût."""

    grille: str
    appliquer: bool
    examinees: int = 0
    chiffrees: int = 0
    sans_tarif: int = 0
    cout_total_micro_eur: int = 0
    modeles_sans_tarif: dict[str, int] = field(default_factory=dict)

    @property
    def lignes_ecrites(self) -> int:
        return self.examinees if self.appliquer else 0


def rejouer_cout(
    db: Session, grille: tarifs.GrilleTarifaire, *, appliquer: bool = False,
    compatibles: Iterable[str] = (),
) -> BilanRejeu:
    """Chiffre les lignes jamais chiffrées d'après `grille`. Rend le bilan ; n'écrit que si `appliquer`."""
    bilan = BilanRejeu(grille=grille.version, appliquer=appliquer)
    compatibles = frozenset(compatibles)
    lignes = (
        db.query(ConsoTokens)
        .filter(ConsoTokens.tarif_version.is_(None), ConsoTokens.cout_micro_eur.is_(None))
        .order_by(ConsoTokens.id)
        .yield_per(TAILLE_LOT)
    )
    for ligne in lignes:
        bilan.examinees += 1
        cout = tarifs.chiffrer(
            grille, ligne.modele, ligne.unite or tarifs.UNITE_JETON, ligne.tokens_in or 0,
            ligne.tokens_out or 0, ligne.tokens_cache or 0, ligne.issue, compatibles,
        )
        if cout.cout_micro_eur is None:
            bilan.sans_tarif += 1
            bilan.modeles_sans_tarif[ligne.modele] = bilan.modeles_sans_tarif.get(ligne.modele, 0) + 1
        else:
            bilan.chiffrees += 1
            bilan.cout_total_micro_eur += cout.cout_micro_eur
        if appliquer:
            ligne.fournisseur = cout.fournisseur
            ligne.cout_micro_eur = cout.cout_micro_eur
            ligne.tarif_version = cout.tarif_version
            if bilan.examinees % TAILLE_LOT == 0:
                db.flush()
    if appliquer:
        db.commit()
        log.info("💶 TARIFS │ rejeu %s │ %d lignes marquées", grille.version, bilan.examinees)
    else:
        db.rollback()
    return bilan

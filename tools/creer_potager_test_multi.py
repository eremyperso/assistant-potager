"""
tools/creer_potager_test_multi.py — Le potager « multi-parcelles » du jeu d'évaluation [US-336]
===============================================================================================
La même culture sur DEUX parcelles : sans lui, aucun cas ne demande au compagnon « sur quelle parcelle ? » pour une
récolte ou une perte (remarque du porteur, relecture G2 du 27/11/2026).

Deux parcelles, « planche légumes » et « planche nord », avec des haricots semés en place sur chacune. Rejouable et
refusé hors base de test, comme `creer_potager_test_neuf.py` dont il reprend la remise à neuf.

    $env:APP_ENV="test"; python tools/creer_potager_test_multi.py

Il affiche les numéros à passer au lanceur (`--potager-multi`, `--utilisateur-multi`).
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

RACINE = Path(__file__).resolve().parent.parent
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

from tools import creer_potager_test_neuf as neuf  # noqa: E402

EMAIL = "eval-compagnon-multi@test.invalid"
NOM_POTAGER = "Potager multi-parcelles d'évaluation"
SECONDE_PARCELLE = "planche nord"
CULTURE = "haricot"
GRAINES = {neuf.NOM_PARCELLE: 30, SECONDE_PARCELLE: 20}
JOURS_DEPUIS_LE_SEMIS = 90


def creer_ou_reinitialiser(db, *, email: str = EMAIL, url_base: Optional[str] = None) -> neuf.PotagerNeuf:
    """Le potager multi-parcelles dans son état de départ. Idempotent."""
    from app.services import evenements, parcelles
    from app.services.context import TenantContext
    from database.db import tenant_scope
    from utils.parcelles import resolve_parcelle

    base = neuf.creer_ou_reinitialiser(db, email=email, url_base=url_base, nom_potager=NOM_POTAGER)
    ctx = TenantContext(user_id=base.utilisateur_id, potager_id=base.potager_id, role="owner")
    with tenant_scope(base.potager_id):
        parcelles.creer_parcelle(db, ctx, SECONDE_PARCELLE, exposition=neuf.EXPOSITION,
                                 superficie_m2=neuf.SUPERFICIE_M2)
        jour = (date.today() - timedelta(days=JOURS_DEPUIS_LE_SEMIS)).isoformat()
        for nom, graines in GRAINES.items():
            geste = {"action": "semis", "culture": CULTURE, "quantite": graines, "unite": "graines", "date": jour,
                     "parcelle": nom}
            evenements.creer_evenement_confirme(db, ctx, geste, f"semé {graines} graines de {CULTURE} sur {nom}",
                                                resolve_parcelle(db, nom, potager_id=base.potager_id))
        db.commit()
    return base


def main() -> int:
    from database.db import SessionLocal

    db = SessionLocal()
    try:
        resultat = creer_ou_reinitialiser(db)
    except neuf.BaseNonTestError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2
    finally:
        db.close()
    print(f"utilisateur {resultat.utilisateur_id}, potager {resultat.potager_id}\n\nPour le lanceur :\n"
          f"  --potager-multi {resultat.potager_id} --utilisateur-multi {resultat.utilisateur_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

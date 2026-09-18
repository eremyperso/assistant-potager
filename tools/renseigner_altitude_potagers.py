"""
tools/renseigner_altitude_potagers.py — Reprise de l'altitude des potagers [US-193 / CA3]
=======================================================================================
Donne leur altitude aux potagers localisés avant US-193, à partir de leurs
coordonnées existantes : le jardinier n'a pas à ressaisir sa ville.

Utilisation :
    python tools/renseigner_altitude_potagers.py            # renseigne les altitudes manquantes
    python tools/renseigner_altitude_potagers.py --dry-run  # compte seulement, aucun appel réseau

Lancé juste après les migrations (deploy.yml, deploy-dev.yml,
scripts/update_dev.ps1), comme le complément de migration_v48.sql.

Idempotent : seuls les potagers à altitude NULL et coordonnées connues sont
concernés. Jamais bloquant pour un déploiement : une panne d'Open-Meteo laisse
les altitudes à NULL (la zone déduite ne suppose alors jamais « montagnard ») et
l'outil rend 0 — il sera rejoué au déploiement suivant.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

from app.services import potagers as svc_potagers  # noqa: E402
from database.db import SessionLocal  # noqa: E402
from utils.altitude import altitudes_depuis_coordonnees  # noqa: E402

log = logging.getLogger("potager")


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée — rend toujours 0 (la reprise ne bloque jamais un déploiement)."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--dry-run", action="store_true", help="compter sans appeler Open-Meteo ni écrire")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s │ %(message)s")

    db = SessionLocal()
    try:
        if args.dry_run:
            trouves, _ = svc_potagers.renseigner_altitudes_manquantes(db, lambda points: [None] * len(points))
            print(f"[US-193] {trouves} potager(s) localisé(s) sans altitude — aucune écriture (--dry-run)")
            return 0
        trouves, renseignes = svc_potagers.renseigner_altitudes_manquantes(db, altitudes_depuis_coordonnees)
        print(f"[US-193] Altitude : {renseignes}/{trouves} potager(s) renseigné(s)")
        if renseignes < trouves:
            print("[US-193] ⚠️ altitudes restées inconnues : reprise rejouée au prochain déploiement")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

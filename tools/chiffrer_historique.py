"""
tools/chiffrer_historique.py — Rejouer le coût des lignes existantes de `conso_tokens` [US-309 / CA8]
=====================================================================================================
Chiffre les lignes écrites avant la migration v75 (ni coût, ni version de grille) d'après une
grille tarifaire donnée, et les marque de sa `tarif_version`. N'appelle AUCUN modèle.

    python tools/chiffrer_historique.py                      # SIMULATION : bilan, rien n'est écrit
    python tools/chiffrer_historique.py --grille autre.json  # simuler avec une autre grille
    python tools/chiffrer_historique.py --appliquer          # écrire

* Simulation par défaut : il faut `--appliquer` pour écrire.
* Ne touche JAMAIS une ligne déjà chiffrée (coût ou version de grille renseignés).
* Un modèle absent de la grille reste sans coût (NULL), jamais un coût inventé ; le bilan les liste.
* Idempotent : une seconde exécution n'a plus rien à rejouer.

Aucune logique ici : tout est dans `app.services.pilotage.chiffrage`.
"""
import argparse
import logging
import os
import sys
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.pilotage import chiffrage, tarifs  # noqa: E402
from database.db import SessionLocal  # noqa: E402

log = logging.getLogger("potager")


def main(argv: Optional[list[str]] = None) -> int:
    for flux in (sys.stdout, sys.stderr):
        if hasattr(flux, "reconfigure"):
            flux.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Rejoue le coût des lignes de conso_tokens jamais chiffrées (US-309)")
    parser.add_argument("--grille", help=f"grille à utiliser (défaut : {tarifs.CHEMIN_GRILLE})")
    parser.add_argument("--appliquer", action="store_true", help="écrire (sans cette option : simulation)")
    args = parser.parse_args(argv)

    try:
        grille = tarifs.charger_grille(args.grille) if args.grille else tarifs.GRILLE
    except tarifs.GrilleTarifaireInvalideError as e:
        print(f"❌ {e}")
        return 2

    from app.config import FOURNISSEURS_COMPATIBLES
    db = SessionLocal()
    try:
        bilan = chiffrage.rejouer_cout(db, grille, appliquer=args.appliquer,
                                       compatibles=FOURNISSEURS_COMPATIBLES)
    finally:
        db.close()

    mode = "ÉCRITURE" if args.appliquer else "SIMULATION (rien n'est écrit — --appliquer pour écrire)"
    print(f"Grille {bilan.grille} — {mode}")
    print(f"  lignes jamais chiffrées examinées : {bilan.examinees}")
    print(f"  chiffrées                         : {bilan.chiffrees} "
          f"({bilan.cout_total_micro_eur / tarifs.MICRO:.4f} € au total)")
    print(f"  sans tarif (coût nul)             : {bilan.sans_tarif}")
    for modele, n in sorted(bilan.modeles_sans_tarif.items(), key=lambda x: -x[1]):
        print(f"      {n:>6} × {modele}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

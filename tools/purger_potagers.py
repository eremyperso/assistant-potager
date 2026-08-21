"""
tools/purger_potagers.py — Purge physique des potagers supprimés [US-084 / CA7, CA8]
------------------------------------------------------------------------------------
Commande d'administration : efface définitivement les potagers dont la
suppression logique remonte à plus de `DELAI_GRACE_JOURS` (30 jours), et eux
seuls. Un potager encore dans son délai de grâce n'est jamais touché.

Ce script ne contient AUCUNE logique de purge : il appelle
`app.services.potagers.purger_potagers_supprimes`, la fonction de service
unique également utilisée par la tâche planifiée du bot
(`bot.py::job_purge_potagers`). Deux déclencheurs, un seul code d'effacement.

Utilisation :
    python tools/purger_potagers.py            # purge réelle
    python tools/purger_potagers.py --dry-run  # liste sans rien effacer

[CA8] Idempotent : relancer la commande aussitôt après ne provoque ni erreur
ni suppression supplémentaire.
"""
import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import potagers as svc_potagers  # noqa: E402
from database.db import SessionLocal  # noqa: E402

log = logging.getLogger("potager")


def main() -> int:
    parser = argparse.ArgumentParser(description="Purge les potagers supprimés au-delà du délai de grâce")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Liste les potagers qui seraient purgés, sans rien effacer",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    db = SessionLocal()
    try:
        if args.dry_run:
            candidats = svc_potagers.potagers_a_purger(db)
            if not candidats:
                print(f"Aucun potager au-delà du délai de grâce ({svc_potagers.DELAI_GRACE_JOURS} jours).")
                return 0
            print(f"{len(candidats)} potager(s) seraient purgés :")
            for potager in candidats:
                print(f"  - #{potager.id} « {potager.nom} » supprimé le {potager.supprime_le}")
            return 0

        resultats = svc_potagers.purger_potagers_supprimes(db)
        if not resultats:
            print(f"Aucun potager au-delà du délai de grâce ({svc_potagers.DELAI_GRACE_JOURS} jours).")
            return 0
        for resultat in resultats:
            volumes = resultat["volumes"]
            print(
                f"Purgé : #{resultat['potager_id']} « {resultat['nom']} » — "
                f"{volumes['evenements']} événement(s), {volumes['parcelles']} parcelle(s), "
                f"{volumes['invitations']} invitation(s), {volumes['culture_config']} fiche(s) culture, "
                f"{volumes['membres']} membre(s)"
            )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

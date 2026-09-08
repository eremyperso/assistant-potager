"""
tools/indexer_memoire_potager.py — Reprise initiale de la mémoire [US-141 / CA3]
================================================================================
Indexe les observations et notes libres DÉJÀ enregistrées, pour que la mémoire
d'un potager ne commence pas le jour du déploiement. Les notes écrites ensuite
sont indexées automatiquement à l'enregistrement (CA2) : cet outil ne sert qu'au
rattrapage.

Il est **rejouable et sans doublon**, et il ne le doit à aucune précaution prise
ici : la référence d'un document de mémoire est dérivée de l'événement
(`memoire/potager-3/evenement-812`), donc un second passage retrouve le même
document, et l'empreinte fait que ce second passage n'écrit rien. C'est le
mécanisme d'idempotence d'US-098 / CA10, réemployé tel quel.

Trois usages, un seul verbe :

    python tools/indexer_memoire_potager.py --dry-run     # ce qui serait fait
    python tools/indexer_memoire_potager.py               # tous les potagers
    python tools/indexer_memoire_potager.py --potager 3   # un seul

`--sans-elagage` désactive le retrait des documents de mémoire dont l'événement
a disparu sans passer par la couche services (base restaurée, suppression en SQL
direct). L'élagage est actif par DÉFAUT : une mémoire orpheline est exactement
ce que le CA11 interdit, et une option qu'il faut penser à activer ne protège
personne.

⚠️ RLS (migration_v42), comme pour `tools/ingerer_connaissance.py` : la mémoire
d'un potager s'écrit avec un rôle qui a le droit d'écrire dans
`knowledge_documents` / `knowledge_chunks` pour ce potager.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import memoire_potager  # noqa: E402
from database.db import SessionLocal  # noqa: E402

log = logging.getLogger("potager")


def main(argv: "list[str] | None" = None) -> int:
    analyseur = argparse.ArgumentParser(
        description="Reprise initiale de la mémoire du potager (US-141 / CA3)",
    )
    analyseur.add_argument(
        "--potager", type=int, default=None,
        help="n'indexer que ce potager (défaut : tous)",
    )
    analyseur.add_argument(
        "--dry-run", action="store_true",
        help="rapport seul, aucune écriture",
    )
    analyseur.add_argument(
        "--sans-elagage", action="store_true",
        help="ne pas retirer les documents de mémoire dont l'événement a disparu",
    )
    args = analyseur.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(levelname)-7s │ %(message)s", stream=sys.stdout,
    )

    db = SessionLocal()
    try:
        rapport = memoire_potager.reprise_initiale(
            db,
            potager_id=args.potager,
            elaguer=not args.sans_elagage,
            dry_run=args.dry_run,
        )
    except Exception as e:
        db.rollback()
        print(f"❌ Reprise interrompue : {type(e).__name__} — {e}")
        return 1
    finally:
        db.close()

    portee = f"potager {args.potager}" if args.potager is not None else "tous les potagers"
    print(f"\n🧠 Mémoire du potager — {portee}{' (à blanc)' if args.dry_run else ''}")
    print(f"   notes trouvées ......... {rapport['notes']}")
    print(f"   indexées / réindexées .. {rapport['indexees']}")
    print(f"   déjà à jour ............ {rapport['inchangees']}")
    print(f"   élaguées ............... {rapport['elaguees']}")
    if args.dry_run:
        print("\n   Aucune écriture — relancer sans --dry-run pour appliquer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

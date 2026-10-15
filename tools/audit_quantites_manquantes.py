"""
tools/audit_quantites_manquantes.py — Événements de pépinière sans nombre de plants [US-224]
===========================================================================================
Liste, en LECTURE SEULE, les événements écrits avant la règle « le nombre de plants
est obligatoire » : perte de godet, vente ou mise en terre sans quantité, mise en
godet sans `nb_plants_godets`. Ils ne font bouger aucun stock et laissent leur lot
« indéterminé ». Le nombre réel n'est connu que du jardinier : l'outil ne corrige
rien et n'invente aucune valeur — il dit quoi corriger, avec `/corriger` au bot.

Usage
-----
    python tools/audit_quantites_manquantes.py --potager 26

Sortie : une ligne par événement (identifiant, date, action, culture, lot, texte).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parseur.add_argument("--potager", type=int, required=True, help="identifiant du potager à auditer")
    args = parseur.parse_args(argv)

    from database.db import SessionLocal
    from app.services import evenements as svc_evenements
    from app.services.context import TenantContext

    ctx = TenantContext(user_id=0, potager_id=args.potager, role="viewer")
    db = SessionLocal()
    try:
        evenements = svc_evenements.evenements_pepiniere_sans_quantite(db, ctx)
        lignes = [
            (
                e.id,
                str(e.date)[:10],
                e.type_action,
                f"{e.culture or '?'}{' ' + e.variete if e.variete else ''}",
                f"lot semis #{e.origine_graines_id}" if e.origine_graines_id else "sans lot",
                (e.texte_original or "")[:60],
            )
            for e in evenements
        ]
    finally:
        db.close()

    if not lignes:
        print(f"Potager {args.potager} : aucun événement de pépinière sans nombre de plants.")
        return 0
    print(f"Potager {args.potager} : {len(lignes)} événement(s) sans nombre de plants — à corriger avec /corriger")
    for ligne in lignes:
        print("  #{} | {} | {} | {} | {} | {}".format(*ligne))
    return 1


if __name__ == "__main__":
    sys.exit(main())

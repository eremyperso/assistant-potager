"""
tools/importer_referentiel.py — Import du référentiel structuré [US-166]
-------------------------------------------------------------------------
Commande d'administration : importe un manifeste de `data/referentiel/` dans les
tables du référentiel, puis publie le **rapport de couverture** qui pilote la
suite de l'ÉPIC 6.

Ce script vit dans `tools/` et **jamais** dans `migrations/` : il est rejouable
à volonté et ne fait pas partie de la séquence de migration. Il ne contient
aucune logique d'import — celle-ci est dans `app/services/import_referentiel.py`
et `app/services/rapport_couverture.py`, testables sans terminal. Deux
déclencheurs possibles, un seul code d'écriture.

Utilisation :
    python tools/importer_referentiel.py data/referentiel/wikidata_familles.json
    python tools/importer_referentiel.py data/referentiel/wikidata_familles.json --dry-run
    python tools/importer_referentiel.py --rapport-seul
    python tools/importer_referentiel.py --derive-de wikidata     # que faut-il retirer ?
    python tools/importer_referentiel.py --lister-sources

[CA5] Idempotent : rejouer le même manifeste ne crée aucun doublon et ne
réécrase aucune correction humaine.
[US-161] Le bloc `cultures_attributs` d'un manifeste pré-remplit les attributs
agronomiques de conduite (exposition, besoin en eau, profondeur de semis,
rusticité) des dix cultures du périmètre initial, et d'elles seules.
[CA6] Un manifeste dont la licence est hors socle est refusé, et rien n'est créé.
[CA8] Aucun appel réseau : le script lit un fichier local et écrit en base.
"""
import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import import_referentiel as svc_import  # noqa: E402
from app.services import rapport_couverture as svc_rapport  # noqa: E402
from app.services import referentiel_sources as svc_sources  # noqa: E402
from database.db import SessionLocal  # noqa: E402
from database.models import ReferentielSource  # noqa: E402

log = logging.getLogger("potager")


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(
        description="Importe le référentiel structuré et publie le rapport de couverture [US-166]"
    )
    parser.add_argument(
        "manifeste", nargs="?",
        help="Fichier JSON de data/referentiel/ à importer",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Simule l'import : compte ce qui serait écrit, sans rien écrire",
    )
    parser.add_argument(
        "--rapport-seul", action="store_true",
        help="Produit le rapport de couverture sans importer quoi que ce soit",
    )
    parser.add_argument(
        "--sans-rapport", action="store_true",
        help="Importe sans publier le rapport de couverture",
    )
    parser.add_argument(
        "--derive-de", metavar="CODE",
        help="[CA4] Liste tout ce qui dérive d'une source, avant de la retirer",
    )
    parser.add_argument(
        "--lister-sources", action="store_true",
        help="Affiche le registre des sources : licence, attribution, dernier import",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    # Certains shells Windows retombent sur cp1252, qui ne sait pas encoder les
    # emojis du rapport — même précaution que tools/jira_tracker.py.
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    if not any([args.manifeste, args.rapport_seul, args.derive_de, args.lister_sources]):
        parser.print_help(sys.stderr)
        return 2

    db = SessionLocal()
    try:
        if args.lister_sources:
            svc_sources.semer_sources_socle(db)
            print("\nRegistre des sources du référentiel [US-166]\n")
            for source in db.query(ReferentielSource).order_by(ReferentielSource.code).all():
                nature = "importée" if source.importee else "origine interne (non importée)"
                partage = "partageable" if source.partageable else "⛔ NON partageable"
                dernier = source.date_dernier_import or "jamais importée"
                print(f"  • {source.code} — {source.libelle} [{nature}, {partage}]")
                print(f"      licence     : {source.licence}")
                print(f"      attribution : {source.attribution}")
                print(f"      url         : {source.url or '—'}")
                print(f"      dernier import : {dernier}")
            print()
            return 0

        if args.derive_de:
            lignes = svc_sources.donnees_derivees(db, args.derive_de)
            if not lignes:
                print(
                    f"Aucune donnée ne dérive de « {args.derive_de} » "
                    "(source inconnue du registre, ou aucun enregistrement rattaché)."
                )
                return 0
            print(f"\n{len(lignes)} enregistrement(s) dérivent de « {args.derive_de} » :\n")
            for ligne in lignes:
                print(f"  • {ligne['table']}#{ligne['id']} — {ligne['libelle']} (via {ligne['colonne']})")
            print()
            return 0

        if args.manifeste:
            try:
                resultat = svc_import.importer_fichier(db, args.manifeste, dry_run=args.dry_run)
            except svc_sources.LicenceHorsSocleError as err:
                print(f"❌ Import refusé — {err}", file=sys.stderr)
                return 1
            except svc_import.ManifesteInvalideError as err:
                print(f"❌ {err}", file=sys.stderr)
                return 2
            print(svc_import.formater_resultat(resultat))

        if not args.sans_rapport:
            print(svc_rapport.formater_rapport(svc_rapport.construire_rapport(db)))

        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

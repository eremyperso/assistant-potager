"""
tools/adapter_wind_river.py — Wind River Greens → manifeste d'import [US-161]
------------------------------------------------------------------------------
Commande d'administration : lit les CSV versionnés du jeu de données Wind River
Greens (CC BY 4.0) et produit un manifeste que `tools/importer_referentiel.py`
importe ensuite. Deux outils, deux responsabilités — l'adaptation ne touche
jamais la base, l'import ne connaît jamais le format d'une source.

Utilisation :
    # 1. Produire le manifeste depuis les CSV versionnés
    #    (écrit aussi wind_river_associations.json — extraction BRUTE pour US-163,
    #     qui ne s'importe pas et attend une relecture humaine)
    python tools/adapter_wind_river.py

    # 2. L'importer (le manifeste est un manifeste comme un autre)
    python tools/importer_referentiel.py data/referentiel/wind_river_attributs.json

    # Filtrer des CSV complets vers l'extrait versionné du périmètre
    python tools/adapter_wind_river.py --extraire <repertoire_csv_complets>

[CA8] Aucun appel réseau. Les CSV sont récupérés hors ligne, à la main, depuis
un *tagged release* immuable — jamais depuis `main`, que le dépôt amont
rafraîchit chaque mois par GitHub Actions. La commande de récupération est
documentée dans data/referentiel/wind_river_greens/SOURCE.md.
"""
import argparse
import csv
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import adaptateur_wind_river as svc_adaptateur  # noqa: E402

log = logging.getLogger("potager")

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPERTOIRE_CSV = os.path.join(RACINE, "data", "referentiel", "wind_river_greens")
MANIFESTE = os.path.join(RACINE, "data", "referentiel", "wind_river_attributs.json")
#: Extraction brute des associations — fichier SÉPARÉ du manifeste : il ne
#: s'importe pas, il attend la relecture d'US-163.
ASSOCIATIONS = os.path.join(RACINE, "data", "referentiel", "wind_river_associations.json")

#: Version amont figée. Toute régénération doit repartir de ce tag, sinon le
#: manifeste et les CSV versionnés décrivent deux états différents du monde.
TAG_SOURCE = "v1.0.0"


def _lire_csv(chemin: str) -> list[dict]:
    if not os.path.exists(chemin):
        return []
    with open(chemin, encoding="utf-8", newline="") as flux:
        return list(csv.DictReader(flux))


def _extraire(repertoire_source: str) -> int:
    """Filtre des CSV complets vers l'extrait du périmètre, versionnable.

    Les CSV amont pèsent ~5 Mo pour 1 972 cultivars dont nous n'utilisons qu'une
    fraction. On versionne l'extrait plutôt que le dump — même choix que
    `wikidata_familles.json`, qui n'est pas un dump de Wikidata."""
    varieties = _lire_csv(os.path.join(repertoire_source, "varieties.csv"))
    companions = _lire_csv(os.path.join(repertoire_source, "companion_plants.csv"))
    if not varieties:
        print(f"❌ Aucun varieties.csv lisible dans {repertoire_source}", file=sys.stderr)
        return 2

    par_culture = svc_adaptateur.selectionner_cultivars(varieties)
    retenues = [l for lignes in par_culture.values() for l in lignes]
    slugs = {l.get("slug") for l in retenues}

    os.makedirs(REPERTOIRE_CSV, exist_ok=True)
    with open(os.path.join(REPERTOIRE_CSV, "varieties.csv"), "w", encoding="utf-8", newline="") as flux:
        redacteur = csv.DictWriter(flux, fieldnames=varieties[0].keys())
        redacteur.writeheader()
        redacteur.writerows(retenues)

    arêtes = [l for l in companions if l.get("variety_slug") in slugs]
    if companions:
        with open(os.path.join(REPERTOIRE_CSV, "companion_plants.csv"), "w", encoding="utf-8", newline="") as flux:
            redacteur = csv.DictWriter(flux, fieldnames=companions[0].keys())
            redacteur.writeheader()
            redacteur.writerows(arêtes)

    print(
        f"\n✅ Extrait du périmètre écrit dans {REPERTOIRE_CSV}\n"
        f"   {len(retenues)} cultivars retenus sur {len(varieties)}\n"
        f"   {len(arêtes)} arêtes d'association retenues sur {len(companions)}\n"
    )
    return 0


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(
        description="Adapte les CSV Wind River Greens en manifeste d'import [US-161]"
    )
    parser.add_argument(
        "--extraire", metavar="REPERTOIRE",
        help="Filtre des CSV complets vers l'extrait versionné du périmètre",
    )
    parser.add_argument(
        "--sortie", default=MANIFESTE,
        help=f"Fichier manifeste à écrire (défaut : {MANIFESTE})",
    )
    parser.add_argument(
        "--sans-associations", action="store_true",
        help="N'extrait pas les associations dans leur fichier séparé (US-163)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    if args.extraire:
        return _extraire(args.extraire)

    varieties = _lire_csv(os.path.join(REPERTOIRE_CSV, "varieties.csv"))
    if not varieties:
        print(
            f"❌ Aucun varieties.csv dans {REPERTOIRE_CSV}.\n"
            f"   Récupérer les CSV du tag {TAG_SOURCE} puis lancer --extraire "
            "(voir data/referentiel/wind_river_greens/SOURCE.md).",
            file=sys.stderr,
        )
        return 2
    companions = [] if args.sans_associations else _lire_csv(
        os.path.join(REPERTOIRE_CSV, "companion_plants.csv")
    )

    manifeste, associations, resultat = svc_adaptateur.construire_manifeste(
        varieties, companions, extrait_le=TAG_SOURCE
    )
    with open(args.sortie, "w", encoding="utf-8", newline="\n") as flux:
        json.dump(manifeste, flux, ensure_ascii=False, indent=2)
        flux.write("\n")
    if associations is not None:
        with open(ASSOCIATIONS, "w", encoding="utf-8", newline="\n") as flux:
            json.dump(associations, flux, ensure_ascii=False, indent=2)
            flux.write("\n")

    print(svc_adaptateur.formater_resultat(resultat))
    print(f"  📄 Manifeste écrit : {args.sortie}")
    if associations is not None:
        print(f"  📄 Associations brutes : {ASSOCIATIONS} — NE PAS importer")
    print(
        "     Importer avec : python tools/importer_referentiel.py "
        f"{os.path.relpath(args.sortie, RACINE)}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

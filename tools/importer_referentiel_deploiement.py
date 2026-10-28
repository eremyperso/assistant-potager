"""
tools/importer_referentiel_deploiement.py — Import du référentiel au déploiement [US-254]
----------------------------------------------------------------------------------------
Importe, dans l'ordre, les manifestes de `data/referentiel/deploiement.json`
(clé « importer »), comme le déploiement ingère le corpus de connaissance.

[CA1] Idempotent : l'import d'un manifeste inchangé n'écrit rien (US-166).
[CA2] Tout échec (liste incohérente, manifeste invalide, licence refusée, base
      indisponible) rend un code non nul : le workflow s'arrête avant le
      redémarrage des services. Les manifestes sont tous validés AVANT la
      première écriture.
[CA4] Le compte rendu de chaque import est affiché, puis le rapport de couverture.
[CA5] Un fichier JSON de data/referentiel/ absent des listes « importer » et
      « exclus » est une erreur : l'exclusion doit être explicite.

Utilisation :
    python tools/importer_referentiel_deploiement.py
    python tools/importer_referentiel_deploiement.py --dry-run
"""
import argparse
import json
import logging
import os
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app.services import import_referentiel as svc_import  # noqa: E402
from app.services import rapport_couverture as svc_rapport  # noqa: E402
from app.services import referentiel_sources as svc_sources  # noqa: E402
from database.db import SessionLocal  # noqa: E402

log = logging.getLogger("potager")

DOSSIER_REFERENTIEL = RACINE / "data" / "referentiel"
LISTE_DEPLOIEMENT = "deploiement.json"


def lire_liste(dossier: Path) -> "tuple[list[str], dict[str, str]]":
    """Lit la liste de déploiement et la confronte au contenu du dossier.

    Lève `ValueError` si un manifeste listé manque, est listé deux fois, ou si
    un fichier JSON du dossier n'est ni importé ni explicitement exclu.
    """
    with open(dossier / LISTE_DEPLOIEMENT, encoding="utf-8") as f:
        liste = json.load(f)
    a_importer: list[str] = list(liste.get("importer", []))
    exclus: dict[str, str] = dict(liste.get("exclus", {}))

    erreurs: list[str] = []
    doublons = {n for n in a_importer if a_importer.count(n) > 1} | (set(a_importer) & set(exclus))
    for nom in sorted(doublons):
        erreurs.append(f"{nom} : listé plusieurs fois (importer / exclus)")
    for nom in a_importer + list(exclus):
        if not (dossier / nom).is_file():
            erreurs.append(f"{nom} : fichier introuvable dans {dossier.name}/")
    connus = set(a_importer) | set(exclus) | {LISTE_DEPLOIEMENT}
    for fichier in sorted(dossier.glob("*.json")):
        if fichier.name not in connus:
            erreurs.append(
                f"{fichier.name} : ni importé ni exclu — à ajouter à {LISTE_DEPLOIEMENT}"
            )
    if erreurs:
        raise ValueError("Liste de déploiement incohérente :\n  - " + "\n  - ".join(erreurs))
    return a_importer, exclus


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(
        description="Importe les manifestes de la liste de déploiement [US-254]"
    )
    parser.add_argument("--dry-run", action="store_true", help="Simule, n'écrit rien")
    parser.add_argument("--dossier", default=str(DOSSIER_REFERENTIEL), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    dossier = Path(args.dossier)
    try:
        a_importer, exclus = lire_liste(dossier)
        for nom in a_importer:  # validation de tous les manifestes avant la 1re écriture
            svc_import.charger_manifeste(dossier / nom)
    except (ValueError, OSError, svc_import.ManifesteInvalideError) as err:
        print(f"❌ {err}", file=sys.stderr)
        return 2

    for nom, motif in exclus.items():
        print(f"  [-] {nom} exclu : {motif}")

    db = SessionLocal()
    try:
        for nom in a_importer:
            print(f"\n>>> Import de {nom}")
            try:
                resultat = svc_import.importer_fichier(db, dossier / nom, dry_run=args.dry_run)
            except svc_sources.LicenceHorsSocleError as err:
                print(f"❌ {nom} : import refusé — {err}", file=sys.stderr)
                return 1
            except svc_import.ManifesteInvalideError as err:
                print(f"❌ {nom} : {err}", file=sys.stderr)
                return 2
            print(svc_import.formater_resultat(resultat))
        print(svc_rapport.formater_rapport(svc_rapport.construire_rapport(db)))
        return 0
    except Exception as err:  # base indisponible, erreur d'écriture : on arrête le déploiement
        log.exception("[US-254] import du référentiel en échec")
        print(f"❌ Import du référentiel en échec : {err}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

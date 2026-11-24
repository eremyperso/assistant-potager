"""
tools/carte_couverture_corpus.py — Quelles cultures ont une fiche, et lesquelles n'en ont pas [US-341 / CA6]
=============================================================================================================
Produit la carte de couverture du corpus agronomique : pour chaque culture du référentiel, a-t-elle une fiche de
**conduite et récolte** et une fiche de **problèmes** ? Elle sert à orienter US-348 (rédiger les fiches qui manquent)
et à comprendre pourquoi le compagnon dit « pas de fiche salade » (US-341 / CA3).

Utilisation :
    APP_ENV=dev python tools/carte_couverture_corpus.py                 # tableau markdown sur la sortie
    APP_ENV=dev python tools/carte_couverture_corpus.py --sortie carte.md

Lecture seule : aucune écriture en base ni dans le dépôt (hors `--sortie`). La source est le DÉPÔT
(`data/connaissance/agronomie/`, en-tête `culture:`), pas la base : c'est le dépôt qu'US-348 complète. Le référentiel
vient de `culture_config` (cultures communes à tous les potagers).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

from unidecode import unidecode  # noqa: E402

RACINE_PAR_DEFAUT = Path("data/connaissance/agronomie")
#: Les deux fiches que le compagnon attend pour une culture : le suffixe du fichier dit laquelle.
SUFFIXES = {"conduite_recolte": "-conduite-recolte", "problemes": "-problemes"}
_CULTURE = re.compile(r"^culture\s*:\s*[\"']?([^\"'\n#]+?)[\"']?\s*(?:#.*)?$", re.MULTILINE)


def _cle(nom: str) -> str:
    return unidecode((nom or "").strip().lower())


def fiches_du_depot(racine: Path) -> dict[str, set[str]]:
    """Les types de fiche présents par culture : `{culture normalisée: {"conduite_recolte", "problemes"}}`."""
    trouvees: dict[str, set[str]] = {}
    for chemin in sorted(racine.glob("*.md")):
        if chemin.name.lower() == "readme.md":
            continue
        contenu = chemin.read_text(encoding="utf-8")
        entete = contenu.split("---", 2)[1] if contenu.startswith("---") else ""
        trouve = _CULTURE.search(entete)
        if not trouve:
            continue
        for type_fiche, suffixe in SUFFIXES.items():
            if chemin.stem.endswith(suffixe):
                trouvees.setdefault(_cle(trouve.group(1)), set()).add(type_fiche)
    return trouvees


def carte(cultures: list[str], fiches: dict[str, set[str]]) -> list[dict]:
    """Une ligne par culture du référentiel, triée : les cultures sans aucune fiche d'abord (le travail d'US-348)."""
    lignes = []
    for nom in sorted(set(cultures), key=_cle):
        presentes = fiches.get(_cle(nom), set())
        lignes.append({"culture": nom, "conduite_recolte": "conduite_recolte" in presentes,
                       "problemes": "problemes" in presentes})
    lignes.sort(key=lambda l: (l["conduite_recolte"] + l["problemes"], _cle(l["culture"])))
    return lignes


def en_markdown(lignes: list[dict]) -> str:
    ok = lambda b: "✅" if b else "❌"  # noqa: E731
    sans = [l for l in lignes if not (l["conduite_recolte"] or l["problemes"])]
    partielles = [l for l in lignes if (l["conduite_recolte"] != l["problemes"])]
    en_tete = [
        "# Carte de couverture du corpus agronomique", "",
        f"{len(lignes)} cultures au référentiel : **{len(sans)} sans aucune fiche**, {len(partielles)} avec une "
        f"seule des deux, {len(lignes) - len(sans) - len(partielles)} complètes.", "",
        "| Culture | Conduite et récolte | Problèmes |", "|---|---|---|",
    ]
    return "\n".join(en_tete + [f"| {l['culture']} | {ok(l['conduite_recolte'])} | {ok(l['problemes'])} |" for l in lignes]) + "\n"


def cultures_du_referentiel() -> list[str]:
    from database.db import SessionLocal
    from database.models import CultureConfig

    db = SessionLocal()
    try:
        return [nom for (nom,) in db.query(CultureConfig.nom).filter(CultureConfig.potager_id.is_(None)).all() if nom]
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Carte de couverture du corpus agronomique (US-341 / CA6)")
    parser.add_argument("--racine", type=Path, default=RACINE_PAR_DEFAUT, help="dossier des fiches")
    parser.add_argument("--sortie", type=Path, help="fichier markdown à écrire (défaut : sortie standard)")
    args = parser.parse_args()
    texte = en_markdown(carte(cultures_du_referentiel(), fiches_du_depot(args.racine)))
    if args.sortie:
        args.sortie.write_text(texte, encoding="utf-8")
        print(f"Carte écrite : {args.sortie}")
    else:
        print(texte)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
tools/controler_espacements.py — Où manque l'espacement sur le rang ? [US-226 / CA8]
====================================================================================
Le référentiel est **très inégalement rempli** : hors cucurbitacées (migration
v13), la plupart des fiches n'ont pas d'espacement, et beaucoup de rangs
afficheront donc « places non calculées ». C'est assumé et honnête — mais il
faut savoir où porter l'effort.

Ce contrôle liste les cultures **réellement présentes dans les potagers** dont
l'espacement est absent ou illisible. Pas les 300 fiches du catalogue : celles
qu'un jardinier a semées ou plantées, et pour lesquelles l'absence se voit à
l'écran. Il signale aussi les fiches dont l'espacement se lit mais **contredit**
la surface au sol de plus de 10 % (CA3) : celles-là ne manquent pas, elles
mentent.

Il ne modifie **rien** : ni fiche, ni colonne, ni ligne. C'est un rapport.

Utilisation :
    python tools/controler_espacements.py                  # tous les potagers
    python tools/controler_espacements.py --potager 1      # un seul potager
    python tools/controler_espacements.py --tout           # y compris les fiches lisibles

Code de retour toujours 0 : un référentiel incomplet n'est pas une régression,
c'est un état de fait qu'on améliore fiche par fiche.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import or_  # noqa: E402

from app.services.espacement_rang import (  # noqa: E402
    TOLERANCE_SURFACE,
    _lire,
    espacement_rang_cm,
)
from database.db import SessionLocal  # noqa: E402
from database.models import CultureConfig, Evenement  # noqa: E402


def cultures_en_usage(db, potager_id: int | None) -> list[str]:
    """Noms de culture réellement dictés au moins une fois, triés, sans doublon."""
    requete = db.query(Evenement.culture).filter(Evenement.culture.isnot(None)).distinct()
    if potager_id is not None:
        requete = requete.filter(Evenement.potager_id == potager_id)
    return sorted({(nom or "").strip() for (nom,) in requete.all() if (nom or "").strip()})


def fiches_par_nom(db, potager_id: int | None) -> dict[str, CultureConfig]:
    """[CA6] Les fiches que le potager VOIT — la personnalisée prime sur la globale."""
    requete = db.query(CultureConfig)
    if potager_id is not None:
        requete = requete.filter(
            or_(CultureConfig.potager_id == potager_id, CultureConfig.potager_id.is_(None))
        )
    index: dict[str, CultureConfig] = {}
    for fiche in requete.all():
        cle = (fiche.nom or "").strip().lower()
        precedente = index.get(cle)
        if precedente is not None and precedente.potager_id is not None and fiche.potager_id is None:
            continue
        index[cle] = fiche
    return index


def analyser(db, potager_id: int | None) -> tuple[list, list, list]:
    """Rend `(manquantes, incoherentes, lisibles)` pour les cultures en usage."""
    fiches = fiches_par_nom(db, potager_id)
    manquantes, incoherentes, lisibles = [], [], []
    for culture in cultures_en_usage(db, potager_id):
        fiche = fiches.get(culture.lower())
        brut = fiche.espacement if fiche is not None else None
        surface = fiche.surface_m2 if fiche is not None else None
        # `journal=None` : ce rapport VEUT une ligne par culture, à la différence
        # de la lecture du plan, qui n'en veut qu'une par lecture.
        valeur = espacement_rang_cm(brut, surface_m2=surface, culture=culture)
        if valeur is None:
            manquantes.append((culture, brut, fiche is None))
            continue
        sur_le_rang, entre_rangs = _lire(brut)
        if entre_rangs and surface:
            attendue = sur_le_rang * entre_rangs / 10000
            if abs(attendue - float(surface)) > TOLERANCE_SURFACE * float(surface):
                incoherentes.append((culture, brut, attendue, float(surface)))
                continue
        lisibles.append((culture, brut, valeur))
    return manquantes, incoherentes, lisibles


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--potager", type=int, default=None, help="limiter à un potager")
    parseur.add_argument("--tout", action="store_true", help="lister aussi les fiches lisibles")
    args = parseur.parse_args(argv)

    # La console Windows est en cp1252 : sans cela, le premier « ── » du rapport
    # fait tomber l'outil en UnicodeEncodeError (relevé du 23/09/2026).
    for flux in (sys.stdout, sys.stderr):
        if hasattr(flux, "reconfigure"):
            flux.reconfigure(encoding="utf-8", errors="replace")

    db = SessionLocal()
    try:
        manquantes, incoherentes, lisibles = analyser(db, args.potager)
    finally:
        db.close()

    total = len(manquantes) + len(incoherentes) + len(lisibles)
    portee = f"potager {args.potager}" if args.potager else "tous les potagers"
    print(f"── ESPACEMENT SUR LE RANG (US-226 / CA8) · {portee} ──")
    print(f"Cultures réellement en usage : {total}\n")

    if manquantes:
        print(f"❌ {len(manquantes)} culture(s) sans espacement exploitable :")
        for culture, brut, sans_fiche in manquantes:
            motif = "aucune fiche culture" if sans_fiche else f"espacement = {brut!r}"
            print(f"   · {culture} — {motif}")
        print("   → ces rangs afficheront « places non calculées ».\n")

    if incoherentes:
        print(f"⚠️  {len(incoherentes)} fiche(s) dont l'espacement contredit la surface au sol :")
        for culture, brut, attendue, surface in incoherentes:
            print(f"   · {culture} — {brut!r} donne {attendue:.3f} m², la fiche dit {surface:.3f} m²")
        print("   → la valeur est retenue quand même ; c'est le référentiel qu'il faut corriger.\n")

    if args.tout and lisibles:
        print(f"✅ {len(lisibles)} culture(s) lisible(s) :")
        for culture, brut, valeur in lisibles:
            print(f"   · {culture} — {brut!r} → {valeur} cm sur le rang")
        print()

    if not manquantes and not incoherentes:
        print("✅ Toutes les cultures en usage ont un espacement sur le rang exploitable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

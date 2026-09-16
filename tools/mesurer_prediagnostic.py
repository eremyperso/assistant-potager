"""
tools/mesurer_prediagnostic.py — Mesure du pré-diagnostic [US-165 / CA11-CA14]
==============================================================================
CA11 : « La mesure se fait sur `docs/CORPUS_QUESTIONS_DIAGNOSTIC_CA11.md` — 44
entrées, dont 19 dans le périmètre v1 couvrant les dix cultures. Cible : la
bonne piste figure dans les trois premiers résultats dans au moins 80 % des cas
de l'assiette v1. »

CA12 : « Les 25 entrées hors périmètre ne comptent pas dans le rappel : elles
mesurent l'honnêteté du CA8. Confondre les deux assiettes plafonnerait
mécaniquement la mesure sous les 80 % et ferait échouer l'US pour une raison de
découpage, pas de qualité. »

CA13 : « Le résultat de cette mesure DÉCIDE de l'activation ou non de la
recherche sémantique. » C'est donc un livrable, pas un journal — et c'est
pourquoi ce script imprime les deux assiettes séparément, verdict compris.

DEUX ASSIETTES, DEUX QUESTIONS DIFFÉRENTES
------------------------------------------
  périmètre v1 (19)   RAPPEL — la bonne piste sort-elle dans les trois premières ?
  hors périmètre (25) HONNÊTETÉ — une piste servie est-elle toujours une piste
                      RÉELLEMENT rattachée à cette culture, ou l'application
                      force-t-elle un rapprochement approximatif ?

Une entrée hors périmètre est comptée honnête si l'application refuse
explicitement (culture sans fiche, symptôme inconnu, aucun croisement) OU si les
pistes servies contiennent celle que le corpus attend. Elle est comptée
MALHONNÊTE si des pistes sont servies alors que le corpus n'en attend aucune, ou
si aucune des pistes servies n'est celle attendue : c'est exactement la piste
forcée que le CA8 interdit.

⚠️ MÊME AVERTISSEMENT D'ÉCHELLE QUE tools/mesurer_corpus_savoir.py, et il vaut
ici aussi : en SQLite ce script mesure le repli de test (couverture de termes),
pas la recherche plein texte PostgreSQL en dictionnaire français. La mesure qui
conditionne le CA13 doit être rejouée contre PostgreSQL, et le seuil
`PREDIAGNOSTIC_SEUIL_SYMPTOME` y être réétalonné. Le script le rappelle dans son
propre rapport, il ne compte pas sur la mémoire de qui le lance.

Utilisation :
    python tools/mesurer_prediagnostic.py                  # mesure ce qui est en base
    python tools/mesurer_prediagnostic.py --importer       # importe d'abord les manifestes
    python tools/mesurer_prediagnostic.py --detail         # une ligne par entrée
    python tools/mesurer_prediagnostic.py --corpus <csv>

Lecture seule par défaut (aucune écriture sans `--importer`), zéro appel réseau,
zéro appel modèle — le pré-diagnostic n'en fait aucun, par construction (CA9).
"""
from __future__ import annotations

import argparse
import csv
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# La console Windows par défaut est en cp1252 : sans cela, le rapport plante à
# l'affichage sur un simple « ✅ ». Un outil de mesure ne doit pas échouer sur
# son encodage de sortie.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):  # flux redirigé qui ne le supporte pas
    pass


from app.services import prediagnostic as svc_prediagnostic  # noqa: E402
from config import PREDIAGNOSTIC_SEUIL_SYMPTOME  # noqa: E402
from database.db import SessionLocal  # noqa: E402

CORPUS_PAR_DEFAUT = "tests/corpus/us165_prediagnostic.csv"

#: Manifestes joués par `--importer`, DANS CET ORDRE — les identités avant les
#: arêtes, les bioagresseurs avant les symptômes. Un ordre différent compte des
#: lignes « ignorées » qui ne le sont pas vraiment.
MANIFESTES_PAR_DEFAUT = (
    "data/referentiel/eppo/bioagresseurs_eppo.json",
    "data/referentiel/bioagresseurs_redaction_interne_complet.json",
    "data/referentiel/symptomes_redaction_interne.json",
)

# [CA11] Cible : la bonne piste dans les trois premières.
RANG_CIBLE = svc_prediagnostic.PREDIAGNOSTIC_MAX_PISTES
TAUX_CIBLE = 0.80

# [CA8] L'honnêteté n'a pas de « cible » négociable : une seule piste forcée est
# une piste de trop, puisque c'est sur elle qu'un jardinier traitera.
TAUX_HONNETETE_CIBLE = 1.00

# Le pré-diagnostic est annoncé « déterministe ET immédiat ». Le second terme se
# mesure aussi. Même seuil de perception que tools/mesurer_corpus_savoir.py.
SEUIL_LATENCE_MS = 150.0

PERIMETRE_V1 = "v1"

#: [CA14] Le cas de désambiguïsation, écrit ici parce qu'il ne se déduit
#: d'aucune ligne du corpus prise isolément : c'est la MÊME description servie
#: sur trois cultures différentes qui doit produire trois pistes différentes.
#: Le corpus porte deux de ces trois lignes (#38 poireau, #44 ail) ; la
#: troisième est ajoutée ici pour que le contraste soit visible d'un coup d'œil.
DESAMBIGUISATION = (
    "des traits orange qui partent en poussière quand je frotte les feuilles",
    ("ail", "poireau", "haricot", "asperge"),
)


def charger_corpus(chemin: Path) -> list[dict]:
    with chemin.open(encoding="utf-8", newline="") as fichier:
        return [ligne for ligne in csv.DictReader(fichier) if (ligne.get("description") or "").strip()]


def _importer(manifestes: list[Path]) -> int:
    """Joue les manifestes — ÉCRITURE, donc explicitement demandée."""
    from app.services import import_referentiel

    db = SessionLocal()
    try:
        for chemin in manifestes:
            if not chemin.is_file():
                print(f"⚠️  Manifeste introuvable, ignoré : {chemin}")
                continue
            resultat = import_referentiel.importer_fichier(db, chemin)
            print(f"  {chemin.name} — {resultat.total_ecritures} écriture(s)")
    except Exception as erreur:  # noqa: BLE001 — un import raté doit se lire, pas planter
        print(f"Import en erreur ({type(erreur).__name__}) : {erreur}")
        return 1
    finally:
        db.close()
    return 0


def _rang_de(resultat, attendue: str) -> Optional[int]:
    """Rang de la piste attendue dans les pistes servies, ou `None`."""
    noms = [
        svc_prediagnostic.normaliser_libelle(piste.bioagresseur)
        for piste in resultat.pistes
    ]
    cible = svc_prediagnostic.normaliser_libelle(attendue)
    return noms.index(cible) + 1 if cible in noms else None


def _est_honnete(resultat, attendue: str) -> bool:
    """[CA8, CA12] L'application a-t-elle refusé plutôt que de forcer ?

    Trois refus explicites valent honnêteté. Des pistes servies ne valent
    honnêteté que si celle qu'attend le corpus s'y trouve — sinon ce sont des
    pistes rapprochées faute de mieux, exactement ce que le CA8 interdit.
    """
    if not resultat.pistes:
        return True
    return bool(attendue) and _rang_de(resultat, attendue) is not None


def main(argv: "Optional[list[str]]" = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mesure le pré-diagnostic sur le corpus de diagnostic (US-165 / CA11-CA14)."
    )
    parser.add_argument("--corpus", default=CORPUS_PAR_DEFAUT,
                        help=f"CSV du corpus (défaut : {CORPUS_PAR_DEFAUT})")
    parser.add_argument("--manifeste", action="append", default=None,
                        help="Manifeste à importer (répétable). Défaut : les trois du référentiel.")
    parser.add_argument("--importer", action="store_true",
                        help="Importe d'abord les manifestes (ÉCRIT en base)")
    parser.add_argument("--detail", action="store_true",
                        help="Liste chaque entrée, son rang et les pistes servies")
    parser.add_argument("--potager-id", type=int, default=None,
                        help="Potager du contexte (défaut : le référentiel partagé seul)")
    args = parser.parse_args(argv)

    racine_depot = Path(__file__).resolve().parent.parent
    corpus = Path(args.corpus)
    if not corpus.is_absolute():
        corpus = racine_depot / corpus
    if not corpus.is_file():
        print(f"Corpus introuvable : {corpus}")
        return 2

    if args.importer:
        chemins = [
            (racine_depot / m) if not Path(m).is_absolute() else Path(m)
            for m in (args.manifeste or list(MANIFESTES_PAR_DEFAUT))
        ]
        print("Import des manifestes :")
        code = _importer(chemins)
        if code != 0:
            print("Import en erreur — mesure abandonnée.")
            return code
        print()

    entrees = charger_corpus(corpus)
    db = SessionLocal()
    try:
        moteur = db.get_bind().dialect.name
        latences: list[float] = []
        mesures: list[tuple[dict, object, Optional[int]]] = []

        for entree in entrees:
            debut = time.perf_counter()
            resultat = svc_prediagnostic.prediagnostic(
                db,
                entree["description"],
                entree["culture"],
                potager_id=args.potager_id,
            )
            latences.append((time.perf_counter() - debut) * 1000)
            attendue = (entree.get("piste_attendue") or "").strip()
            mesures.append((entree, resultat, _rang_de(resultat, attendue) if attendue else None))

        desambiguisation = []
        description, cultures = DESAMBIGUISATION
        for culture in cultures:
            resultat = svc_prediagnostic.prediagnostic(db, description, culture, potager_id=args.potager_id)
            desambiguisation.append((culture, [p.bioagresseur for p in resultat.pistes]))
    finally:
        db.close()

    v1 = [(e, r, rang) for e, r, rang in mesures if e["perimetre"] == PERIMETRE_V1]
    hors = [(e, r, rang) for e, r, rang in mesures if e["perimetre"] != PERIMETRE_V1]

    dans_cible = sum(1 for _, _, rang in v1 if rang is not None and rang <= RANG_CIBLE)
    premiers = sum(1 for _, _, rang in v1 if rang == 1)
    taux = dans_cible / len(v1) if v1 else 0.0

    honnetes = sum(
        1 for e, r, _ in hors if _est_honnete(r, (e.get("piste_attendue") or "").strip())
    )
    taux_honnetete = honnetes / len(hors) if hors else 0.0

    latences.sort()
    p50 = statistics.median(latences) if latences else 0.0
    p95 = latences[max(0, int(len(latences) * 0.95) - 1)] if latences else 0.0

    print("── MESURE DU PRÉ-DIAGNOSTIC (US-165 / CA11-CA14) ──")
    print(f"Moteur     : {moteur}")
    print(f"Corpus     : {len(mesures)} entrée(s) — {corpus.name}")
    print(f"Seuil de reconnaissance du symptôme : {PREDIAGNOSTIC_SEUIL_SYMPTOME}")
    print()
    print(f"[CA11] RAPPEL — périmètre v1 ({len(v1)} entrées)")
    print(f"       bonne piste dans le top {RANG_CIBLE} : {dans_cible}/{len(v1)} "
          f"({taux:.0%}) — cible {TAUX_CIBLE:.0%}")
    print(f"       dont en 1re position           : {premiers}/{len(v1)}")
    print()
    print(f"[CA12] HONNÊTETÉ — hors périmètre ({len(hors)} entrées)")
    print(f"       refus explicite ou piste juste : {honnetes}/{len(hors)} "
          f"({taux_honnetete:.0%}) — cible {TAUX_HONNETETE_CIBLE:.0%}")
    print()
    print(f"[perf] Latence p50 / p95 (ms)         : {p50:.1f} / {p95:.1f} "
          f"— seuil {SEUIL_LATENCE_MS:.0f}")
    print(f"[CA9]  Appels modèle                  : 0 (par construction — "
          f"app/services/prediagnostic.py n'importe aucun client LLM)")

    print()
    print(f"[CA14] DÉSAMBIGUÏSATION — « {description} »")
    for culture, pistes in desambiguisation:
        print(f"       {culture:<10} → {', '.join(pistes) or '— aucune piste'}")

    if args.detail:
        print("\nDétail :")
        for entree, resultat, rang in mesures:
            if entree["perimetre"] == PERIMETRE_V1:
                marque = "✅" if rang is not None and rang <= RANG_CIBLE else "❌"
            else:
                marque = "✅" if _est_honnete(
                    resultat, (entree.get("piste_attendue") or "").strip()
                ) else "❌"
            pistes = ", ".join(p.bioagresseur for p in resultat.pistes) or "—"
            print(
                f"  {marque} #{entree['numero']:>2} [{entree['perimetre']:<4}] "
                f"{entree['culture']:<15} rang={rang or '—'} "
                f"issue={resultat.issue:<18} score={resultat.score:.2f}"
            )
            print(f"        attendu : {entree.get('piste_attendue') or '— (non-couverture attendue)'}")
            print(f"        servi   : {pistes}")

    print()
    if moteur != "postgresql":
        print(
            "⚠️  Mesure effectuée sur le REPLI SQLite (couverture de termes), pas sur\n"
            "    la recherche plein texte PostgreSQL. Les deux échelles de score sont\n"
            "    bornées dans [0, 1] et ne se superposent pas : cette mesure ne décide\n"
            "    de rien tant qu'elle n'a pas été rejouée contre la production, avec\n"
            "    PREDIAGNOSTIC_SEUIL_SYMPTOME réétalonné (CA13)."
        )
    elif taux >= TAUX_CIBLE:
        print(
            "✅ Au-dessus du seuil : l'enrichissement des synonymes (CA1) suffit, la\n"
            "   question de la recherche SÉMANTIQUE reste fermée (CA13, US-140/CA12)."
        )
    else:
        print(
            "⚠️  SOUS LE SEUIL. Avant d'ouvrir le sujet du vectoriel, enrichir la\n"
            "    colonne `synonymes` des symptômes manqués : c'est l'arbitrage tranché\n"
            "    de l'US — les fiches sont écrites en vocabulaire technique, les\n"
            "    questions posées en vocabulaire courant, et écrire les deux supprime\n"
            "    la majeure partie du besoin sémantique (CA13)."
        )

    return 0 if (taux >= TAUX_CIBLE and taux_honnetete >= TAUX_HONNETETE_CIBLE) else 1


if __name__ == "__main__":
    raise SystemExit(main())

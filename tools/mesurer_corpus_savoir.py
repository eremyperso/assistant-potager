"""
tools/mesurer_corpus_savoir.py — Mesure de la recherche de savoir [US-098 / CA4, CA13]
=========================================================================================
CA13 : « Un corpus d'au moins 30 questions de savoir réelles est constitué avec
le fragment attendu pour chacune ; la cible est que le bon fragment figure dans
les trois premiers résultats. **Cette mesure conditionne l'activation de l'étage
en production.** »

CA4 : « les temps de réponse sont mesurés et restent sous le seuil de
perception ».

Ce script ne mesure pas « en général » : il mesure sur la base réellement
configurée par `DATABASE_URL`. Lancé avec `.env.dev` chargé, il ne dit rien de
la production — et surtout, en SQLite il mesure le repli de test de
`app/services/connaissance.py`, pas la recherche plein texte PostgreSQL en
dictionnaire français. **La mesure qui conditionne l'activation doit être
rejouée contre PostgreSQL**, comme `tools/mesurer_rotation.py` l'exige déjà pour
la rotation. Le script le rappelle dans son propre rapport, il ne compte pas
sur la mémoire de qui le lance.

Utilisation :
    python tools/mesurer_corpus_savoir.py                    # mesure le corpus déjà en base
    python tools/mesurer_corpus_savoir.py --ingerer          # ingère d'abord le corpus de mesure
    python tools/mesurer_corpus_savoir.py --detail           # liste chaque question et son rang
    python tools/mesurer_corpus_savoir.py --corpus <csv> --racine <dossier>

Lecture seule par défaut (aucune écriture sans `--ingerer`), zéro appel réseau,
zéro appel modèle — l'étage 2 n'en fait aucun, par construction (CA8).
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


from app.services import connaissance  # noqa: E402
from app.services.context import default_context  # noqa: E402
from database.db import SessionLocal  # noqa: E402

CORPUS_PAR_DEFAUT = "tests/corpus/us098_questions_savoir.csv"
RACINE_PAR_DEFAUT = "tests/corpus/us098_connaissance"

# [CA13] Cible : le bon fragment dans les trois premiers résultats.
RANG_CIBLE = 3
# Part minimale de questions atteignant la cible pour que l'étage mérite d'être
# activé. 0.8 est un seuil de décision, pas une vérité : il vaut ce que vaut le
# corpus qui le mesure, et se relit à chaque enrichissement du corpus.
TAUX_CIBLE = 0.80
# [CA4] Seuil de perception. Au-delà, la réponse « instantanée » ne l'est plus,
# et l'intérêt de l'étage (répondre sans jeton ET sans attente) s'érode.
SEUIL_LATENCE_MS = 150.0


def charger_corpus(chemin: Path, prefixe: str) -> list[tuple[str, str]]:
    """Lit le corpus `question,fragment_attendu`. Le fragment attendu est écrit
    relatif à la racine du corpus, pour rester lisible : on le préfixe ici de la
    référence réelle du document, celle que porte la base."""
    lignes: list[tuple[str, str]] = []
    with chemin.open(encoding="utf-8", newline="") as fichier:
        for ligne in csv.DictReader(fichier):
            question = (ligne.get("question") or "").strip()
            attendu = (ligne.get("fragment_attendu") or "").strip()
            if question and attendu:
                lignes.append((question, f"{prefixe}/{attendu}"))
    return lignes


def _ingerer(racine: Path) -> int:
    """Ingère le corpus de mesure — écriture, donc explicitement demandée."""
    from tools import ingerer_connaissance
    return ingerer_connaissance.main(["--racine", str(racine)])


def main(argv: "Optional[list[str]]" = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mesure la recherche de savoir sur un corpus de questions (US-098 / CA4, CA13)."
    )
    parser.add_argument("--corpus", default=CORPUS_PAR_DEFAUT,
                        help=f"CSV question,fragment_attendu (défaut : {CORPUS_PAR_DEFAUT})")
    parser.add_argument("--racine", default=RACINE_PAR_DEFAUT,
                        help=f"Racine des documents du corpus (défaut : {RACINE_PAR_DEFAUT})")
    parser.add_argument("--ingerer", action="store_true",
                        help="Ingère d'abord les documents de la racine (ÉCRIT en base)")
    parser.add_argument("--detail", action="store_true",
                        help="Liste chaque question, son rang et son score")
    parser.add_argument("--potager-id", type=int, default=None,
                        help="Potager du contexte de recherche (défaut : contexte courant)")
    args = parser.parse_args(argv)

    racine_depot = Path(__file__).resolve().parent.parent
    corpus = Path(args.corpus)
    if not corpus.is_absolute():
        corpus = racine_depot / corpus
    racine = Path(args.racine)
    if not racine.is_absolute():
        racine = racine_depot / racine
    if not corpus.is_file():
        print(f"Corpus introuvable : {corpus}")
        return 2

    if args.ingerer:
        code = _ingerer(racine)
        if code != 0:
            print("Ingestion en erreur — mesure abandonnée.")
            return code
        print()

    prefixe = racine.resolve().relative_to(racine_depot).as_posix()
    questions = charger_corpus(corpus, prefixe)
    if len(questions) < 30:
        print(f"⚠️  Corpus de {len(questions)} questions — le CA13 en exige au moins 30.")

    ctx = default_context()
    if args.potager_id is not None:
        from dataclasses import replace
        ctx = replace(ctx, potager_id=args.potager_id)

    db = SessionLocal()
    try:
        moteur = db.get_bind().dialect.name
        volumes = connaissance.compter(db)
        rangs: list[Optional[int]] = []
        latences: list[float] = []
        detail: list[tuple[str, Optional[int], float]] = []

        for question, attendu in questions:
            debut = time.perf_counter()
            # Fenêtre volontairement plus large que RANG_CIBLE : mesurer le rang
            # réel d'un fragment classé quatrième vaut mieux que de le compter
            # « absent » — c'est la différence entre « à retravailler » et
            # « à écrire ».
            contexte = connaissance.rechercher(db, ctx, question, limite=10)
            latences.append((time.perf_counter() - debut) * 1000)
            references = list(contexte.references)
            rang = references.index(attendu) + 1 if attendu in references else None
            rangs.append(rang)
            detail.append((question, rang, contexte.confiance))
    finally:
        db.close()

    total = len(rangs)
    dans_cible = sum(1 for rang in rangs if rang is not None and rang <= RANG_CIBLE)
    premiers = sum(1 for rang in rangs if rang == 1)
    absents = sum(1 for rang in rangs if rang is None)
    taux = dans_cible / total if total else 0.0
    latences.sort()
    p50 = statistics.median(latences) if latences else 0.0
    p95 = latences[max(0, int(len(latences) * 0.95) - 1)] if latences else 0.0

    print(f"── MESURE DU CORPUS DE SAVOIR (US-098 / CA4, CA13) ──")
    print(f"Moteur     : {moteur}")
    print(f"En base    : {volumes['documents']} document(s), {volumes['fragments']} fragment(s)")
    print(f"Corpus     : {total} question(s) — {corpus.name}")
    print()
    print(f"[CA13] Bon fragment dans le top {RANG_CIBLE} : {dans_cible}/{total} ({taux:.0%}) — cible {TAUX_CIBLE:.0%}")
    print(f"       dont en 1re position               : {premiers}/{total}")
    print(f"       jamais retrouvé                    : {absents}/{total}")
    print(f"[CA4]  Latence p50 / p95 (ms)             : {p50:.1f} / {p95:.1f} — seuil {SEUIL_LATENCE_MS:.0f}")

    if args.detail:
        print("\nDétail :")
        for question, rang, score in detail:
            marque = "✅" if rang is not None and rang <= RANG_CIBLE else "❌"
            position = f"rang {rang}" if rang is not None else "absent"
            print(f"  {marque} [{position:>8}] score={score:.3f} · {question}")

    echecs = [question for question, rang, _ in detail if rang is None or rang > RANG_CIBLE]
    if echecs:
        print(f"\n[CA14] {len(echecs)} question(s) hors cible — ce sont elles qui disent quoi écrire ou relire :")
        for question in echecs:
            print(f"   · {question}")

    if moteur != "postgresql":
        print(
            "\n⚠️  Mesure effectuée sur "
            f"{moteur}, donc sur le REPLI de test de app/services/connaissance.py — "
            "pas sur la recherche plein texte française de PostgreSQL. Elle ne peut PAS "
            "servir à décider de l'activation de l'étage en production (CA13) : "
            "rejouer ce script avec un DATABASE_URL pointant la production."
        )

    hors_cible = taux < TAUX_CIBLE
    trop_lent = p95 > SEUIL_LATENCE_MS
    if hors_cible:
        print(f"\n❌ CA13 non satisfait : {taux:.0%} < {TAUX_CIBLE:.0%}.")
    if trop_lent:
        print(f"❌ CA4 non satisfait : p95 = {p95:.1f} ms > {SEUIL_LATENCE_MS:.0f} ms.")
    if hors_cible or trop_lent:
        return 1
    print("\n✅ CA13 et CA4 satisfaits sur ce corpus et ce moteur.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

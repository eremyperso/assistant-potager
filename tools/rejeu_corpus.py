"""Rejeu d'un corpus contre le routeur d'US-093 — Action 0 de la vague 2.

Mesure le TAUX DE BON ROUTAGE sur deux corpus qui ne mesurent pas la même
chose et ne doivent jamais être fusionnés (cf.
`docs/decisions-prerequis-vague2-piste-a.md` §6) :

* corpus « action » : les saisies réelles de production, extraites par
  `tools/extraction_corpus_rejeu.sql`. Branche attendue : ACTION.
* corpus « savoir » : `docs/CORPUS_QUESTIONS_DIAGNOSTIC_CA11.md`, 44 entrées
  dont 19 dans le périmètre v1. Branche attendue : QUESTION_SAVOIR.

⚠️ NE JAMAIS EXÉCUTER CONTRE LA PRODUCTION. Le script suppose une base dev
rechargée avec les données de prod (`APP_ENV=dev`), et le mode `cascade`
écrit dans `routage_logs`.

Deux modes, deux coûts :

    --mode classification  (défaut) : appelle `llm.routeur.classer_demande`.
        Mesure exactement ce que l'Action 0 demande. Les décisions par règle
        et par catalogue sont gratuites ; seule la frange ambiguë appelle le
        modèle. N'écrit PAS dans `routage_logs`.

    --mode cascade : appelle `llm.routeur.repondre_avec_cascade`, donc produit
        aussi la réponse et journalise dans `routage_logs`. Au moins un appel
        modèle par question — coût réel sur la clé Groq.

Usage :
    python tools/rejeu_corpus.py --corpus action --fichier rejeu_action.csv
    python tools/rejeu_corpus.py --corpus savoir
    python tools/rejeu_corpus.py --corpus savoir --v1-seulement --mode cascade
"""
from __future__ import annotations

import argparse
import csv
import logging
import os
import re
import sys
import time
from collections import Counter, deque
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

log = logging.getLogger("potager")

CORPUS_SAVOIR_MD = RACINE / "docs" / "CORPUS_QUESTIONS_DIAGNOSTIC_CA11.md"


# ─────────────────────────────────────────────────────────────────────────────
# Chargement des corpus
# ─────────────────────────────────────────────────────────────────────────────
def charger_corpus_action(chemin: Path) -> list[dict]:
    """CSV produit par `tools/extraction_corpus_rejeu.sql`.

    Déduplique sur la question normalisée : une même phrase dictée a pu créer
    plusieurs évènements (« Récolte 4,8 kg oignons blancs. » en produit deux,
    un en kg et un en plants). Le routeur, lui, ne l'a vue qu'une seule fois —
    la rejouer deux fois gonflerait mécaniquement le dénominateur.
    """
    from llm.routeur import _normaliser_question

    vues: dict[str, dict] = {}
    doublons = 0
    with open(chemin, encoding="utf-8", newline="") as f:
        for ligne in csv.DictReader(f):
            # `left(…, position('[CORR' …))` laisse un « | » orphelin en fin de
            # champ pour les 35 saisies corrigées : on le retire ici plutôt que
            # de compliquer le SQL d'extraction.
            question = re.sub(r"\s*\|\s*$", "", (ligne["question"] or "").strip())
            if not question:
                continue
            cle = _normaliser_question(question)
            if cle in vues:
                doublons += 1
                continue
            vues[cle] = {
                "id": ligne["id"],
                "corpus": "action",
                "question": question,
                "nature_attendue": "ACTION",
                "dans_v1": True,
            }
    if doublons:
        log.info("REJEU : %d doublons de texte dicté écartés", doublons)
    return list(vues.values())


def charger_corpus_savoir(chemin: Path = CORPUS_SAVOIR_MD) -> list[dict]:
    """Partie 1 du corpus markdown (44 entrées numérotées).

    La question rejouée est le symptôme dicté, c'est-à-dire ce qui précède la
    première flèche : l'hypothèse et la période qui suivent sont l'annotation
    du rédacteur, pas les mots du jardinier.

    Le drapeau v1 (19 entrées, assiette de la mesure de rappel du CA11) est lu
    dans la colonne ✅ de la table de la partie 2.
    """
    texte = chemin.read_text(encoding="utf-8")

    v1 = set()
    for ligne in texte.splitlines():
        correspondance = re.match(r"^\|\s*(\d+)\s*\|\s*✅", ligne)
        if correspondance:
            v1.add(int(correspondance.group(1)))

    partie1 = texte.split("## Partie 1")[1].split("## Partie 2")[0]
    entrees = []
    for ligne in partie1.splitlines():
        correspondance = re.match(r"^(\d+)\.\s+(.*)$", ligne.strip())
        if not correspondance:
            continue
        numero = int(correspondance.group(1))
        question = correspondance.group(2).split("→")[0].strip()
        entrees.append({
            "id": str(numero),
            "corpus": "savoir",
            "question": question,
            "nature_attendue": "QUESTION_SAVOIR",
            "dans_v1": numero in v1,
        })
    return entrees


# ─────────────────────────────────────────────────────────────────────────────
# Rejeu
# ─────────────────────────────────────────────────────────────────────────────
def rejouer(entrees: list[dict], ctx, mode: str, rpm: int = 18) -> list[dict]:
    """Rejoue les entrées en régulant le débit vers Groq.

    La régulation ne compte que les appels RÉELLEMENT partis au modèle : une
    décision par règle ou par catalogue ne consomme aucun quota, l'attendre
    allongerait le rejeu sans rien protéger. Les horodatages des appels modèle
    sont conservés sur une fenêtre glissante de 60 s ; dès que la fenêtre est
    pleine, on patiente jusqu'à ce que le plus ancien en sorte.

    ⚠️ La limite qui mord n'est pas le nombre de requêtes mais les jetons par
    minute : ~250 jetons d'entrée + ~150 de raisonnement par classification,
    contre un plafond de 7,7 K/min sur le palier actuel — d'où un défaut à 18
    et non à 30. `llm/passerelle.py` rejoue une fois sur 429, mais un rejeu qui
    s'appuie sur ce filet mesure des latences de rattrapage, pas les vraies.
    """
    from llm.routeur import (
        _normaliser_question,
        classer_demande,
        repondre_avec_cascade,
    )

    appels_modele: deque[float] = deque()

    def patienter() -> None:
        if len(appels_modele) < rpm:
            return
        attente = 60.0 - (time.monotonic() - appels_modele[0])
        if attente > 0:
            print(f"  ⏸ quota atteint — pause {attente:.0f} s", file=sys.stderr)
            time.sleep(attente)
        appels_modele.popleft()

    resultats = []
    total = len(entrees)
    for rang, entree in enumerate(entrees, start=1):
        patienter()
        debut = time.monotonic()
        etage, log_id = "", ""
        try:
            if mode == "cascade":
                reponse = repondre_avec_cascade(ctx, entree["question"])
                etage = reponse.etage_resolveur
                log_id = reponse.routage_log_id or ""
            # La classification est relue dans les deux modes : en cascade elle
            # sort du cache alimenté juste au-dessus, donc sans appel modèle
            # supplémentaire ni double comptage de jetons.
            decision = classer_demande(entree["question"], ctx)
            nature, origine, confiance = decision.nature, decision.origine, decision.confiance
            erreur = ""
            # En cascade, la réponse elle-même part toujours au modèle : la
            # classification relue sort du cache (origine='cache') et ne
            # refléterait donc plus la consommation réelle.
            if mode == "cascade" or origine == "modele":
                appels_modele.append(time.monotonic())
        except Exception as e:  # un échec isolé ne doit pas interrompre le rejeu
            nature, origine, confiance = "ERREUR", "", None
            erreur = f"{type(e).__name__}: {e}"
            log.warning("REJEU : échec sur %r — %s", entree["question"][:60], erreur)

        resultats.append({
            **entree,
            "question_normalisee": _normaliser_question(entree["question"]),
            "nature_obtenue": nature,
            "origine_classification": origine,
            "confiance": confiance,
            "correct": nature == entree["nature_attendue"],
            "etage_resolveur": etage,
            "routage_log_id": log_id,
            "latence_ms": int((time.monotonic() - debut) * 1000),
            "erreur": erreur,
        })
        if rang % 25 == 0 or rang == total:
            print(f"  … {rang}/{total}", file=sys.stderr)
    return resultats


# ─────────────────────────────────────────────────────────────────────────────
# Restitution
# ─────────────────────────────────────────────────────────────────────────────
def restituer(resultats: list[dict], corpus: str) -> None:
    total = len(resultats)
    if not total:
        print("Aucune entrée rejouée.")
        return
    bons = sum(1 for r in resultats if r["correct"])
    barre = "=" * 72
    print(f"\n{barre}\nCORPUS « {corpus} » — {total} questions\n{barre}")
    print(f"Bien routées    : {bons}/{total}  ({100.0 * bons / total:.1f} %)")

    origines = Counter(r["origine_classification"] for r in resultats)
    for nom in ("regle", "cache", "modele", ""):
        if origines.get(nom):
            print(f"  origine {nom or '(erreur)':<8}: {origines[nom]}")

    latences = sorted(r["latence_ms"] for r in resultats)
    print(f"Latence médiane : {latences[total // 2]} ms")

    erreurs = [r for r in resultats if not r["correct"]]
    if erreurs:
        print(f"\nMatrice des erreurs ({len(erreurs)}) :")
        for (attendu, obtenu), n in Counter(
            (r["nature_attendue"], r["nature_obtenue"]) for r in erreurs
        ).most_common():
            print(f"  {attendu:<16} → {obtenu:<16} : {n}")
        print("\nDétail des 15 premières :")
        for r in erreurs[:15]:
            print(f"  [{r['id']:>4}] {r['nature_obtenue']:<16} « {r['question'][:60]} »")


def ecrire_csv(resultats: list[dict], chemin: Path) -> None:
    colonnes = [
        "id", "corpus", "dans_v1", "question", "question_normalisee",
        "nature_attendue", "nature_obtenue", "correct",
        "origine_classification", "confiance", "etage_resolveur",
        "routage_log_id", "latence_ms", "erreur",
    ]
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        graveur = csv.DictWriter(f, fieldnames=colonnes)
        graveur.writeheader()
        graveur.writerows(resultats)
    print(f"\nRésultats détaillés → {chemin}")


def main() -> int:
    analyseur = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    analyseur.add_argument("--corpus", choices=("action", "savoir"), required=True)
    analyseur.add_argument("--fichier", type=Path, help="CSV du corpus action")
    analyseur.add_argument("--mode", choices=("classification", "cascade"), default="classification")
    analyseur.add_argument("--sortie", type=Path, help="CSV de résultats (défaut : rejeu_<corpus>_resultats.csv)")
    analyseur.add_argument("--potager", type=int, default=1)
    analyseur.add_argument("--rpm", type=int, default=18,
                           help="appels modele par minute au maximum (defaut 18)")
    analyseur.add_argument("--v1-seulement", action="store_true",
                           help="corpus savoir : limiter aux 19 entrées du périmètre v1")
    analyseur.add_argument("--limite", type=int, help="n'en rejouer que les N premières (mise au point)")
    args = analyseur.parse_args()

    if os.getenv("APP_ENV") == "prod":
        print("REFUS : APP_ENV=prod. Ce rejeu ne doit jamais viser la production.", file=sys.stderr)
        return 2

    # La console Windows est en cp1252 : sans cela, la matrice des erreurs
    # (« → ») fait planter le script APRÈS le rejeu, donc avant l'écriture du
    # CSV — on perdrait les appels modèle déjà payés.
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s — %(levelname)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.corpus == "action":
        if not args.fichier:
            print("--fichier est requis pour le corpus action.", file=sys.stderr)
            return 2
        entrees = charger_corpus_action(args.fichier)
    else:
        entrees = charger_corpus_savoir()
        if args.v1_seulement:
            entrees = [e for e in entrees if e["dans_v1"]]

    if args.limite:
        entrees = entrees[: args.limite]

    from app.services.context import TenantContext

    ctx = TenantContext(user_id=1, potager_id=args.potager, role="owner")

    print(f"Rejeu « {args.corpus} » — {len(entrees)} questions, "
          f"mode {args.mode}, potager {args.potager}, <= {args.rpm} appels modele/min")
    resultats = rejouer(entrees, ctx, args.mode, rpm=args.rpm)

    restituer(resultats, args.corpus)
    ecrire_csv(resultats, args.sortie or Path(f"rejeu_{args.corpus}_resultats.csv"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

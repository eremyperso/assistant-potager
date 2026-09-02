"""
tools/mesurer_rotation.py — Mesure le temps de réponse réel de la rotation [US-163/CA12]
-------------------------------------------------------------------------------------------
CA12 : « Le temps de réponse de la requête de rotation (historique de deux
campagnes × culture × famille) est mesuré sur la base de production avant
d'être câblé dans un chemin synchrone du bot. Attendu sous les 50 ms avec les
index existants ; à vérifier, pas à supposer. »

Ce script ne mesure PAS lui-même sur la production : il donne l'outil pour que
CE SOIT vérifié — contre la base réellement configurée par DATABASE_URL. Lancé
avec `.env.dev` chargé, il ne mesure que le jeu de développement, qui ne
reflète pas le volume réel. C'est un opérateur humain qui doit le rejouer avec
`.env.prod` (ou toute configuration pointant la production) avant que
`app.services.rotation.evaluer_rotation` ne soit câblée dans un chemin
automatique (US-167).

Utilisation :
    python tools/mesurer_rotation.py <parcelle_id> <culture>
    python tools/mesurer_rotation.py <parcelle_id> <culture> --potager-id 1 --repetitions 50

Aucune écriture : lecture seule, à travers exactement le chemin qu'emprunterait
un appel réel (`evaluer_rotation`), zéro appel réseau (US-163/CA11).
"""
import argparse
import os
import sys
import time
from dataclasses import replace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import rotation as svc_rotation  # noqa: E402
from app.services.context import default_context  # noqa: E402
from database.db import SessionLocal  # noqa: E402

SEUIL_MS = 50.0


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mesure le temps de réponse réel de evaluer_rotation (US-163/CA12) — "
                    "à exécuter contre la production avant tout câblage automatique."
    )
    parser.add_argument("parcelle_id", type=int, help="Id de la parcelle à évaluer")
    parser.add_argument("culture", help="Culture candidate à la plantation")
    parser.add_argument(
        "--potager-id", type=int, default=None,
        help="Potager propriétaire de la parcelle (défaut : potager du contexte courant)",
    )
    parser.add_argument(
        "--repetitions", type=int, default=20,
        help="Nombre d'appels mesurés (défaut : 20) — chaque appel rouvre le chemin complet",
    )
    args = parser.parse_args(argv)

    ctx = default_context()
    if args.potager_id is not None:
        ctx = replace(ctx, potager_id=args.potager_id)

    db = SessionLocal()
    try:
        evaluation = None
        durees_ms: list[float] = []
        for _ in range(args.repetitions):
            debut = time.perf_counter()
            evaluation = svc_rotation.evaluer_rotation(db, ctx, args.parcelle_id, args.culture)
            durees_ms.append((time.perf_counter() - debut) * 1000)

        durees_ms.sort()
        p50 = durees_ms[len(durees_ms) // 2]
        p95 = durees_ms[max(0, int(len(durees_ms) * 0.95) - 1)]

        print(f"Statut du dernier appel : {evaluation.statut}")
        print(f"Répétitions             : {len(durees_ms)}")
        print(
            f"Min / p50 / p95 / Max (ms) : "
            f"{durees_ms[0]:.2f} / {p50:.2f} / {p95:.2f} / {durees_ms[-1]:.2f}"
        )
        if p95 > SEUIL_MS:
            print(f"⚠️  p95 au-dessus du seuil attendu de {SEUIL_MS:.0f} ms — CA12 non satisfait tel quel.")
            return 1
        print(f"✅ p95 sous le seuil attendu de {SEUIL_MS:.0f} ms.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

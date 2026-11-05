"""Ligne de commande du harnais conversationnel [US-288].

    python -m tests_conv validate                 # parse les scénarios, 0 appel, 0 réseau
    python -m tests_conv session                  # crée la session Telethon (une fois, interactif)
    python -m tests_conv seed                     # crée compte + potager de test, lie le compte Telegram
    python -m tests_conv run --go                 # joue tous les scénarios
    python -m tests_conv run --id SC-010 --passages 5 --go
    python -m tests_conv run --tag critique --go

`run` sans `--go` annonce le volume (messages envoyés au bot, donc appels au vrai modèle) et
s'arrête : une campagne se lance en connaissance de cause.

Codes de sortie : 0 aucun scénario en échec ; 1 au moins un échec ; 2 mesure impossible.
"""
import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

from .harness import config as cfg_mod
from .harness.parser import ScenarioInvalide, charger_dossier
from .harness.runner import ECHEC, jouer, nombre_de_messages


def _scenarios(args):
    dossier = Path(args.dossier) if args.dossier else cfg_mod.DOSSIER_SCENARIOS
    try:
        tous = charger_dossier(dossier)
    except ScenarioInvalide as e:
        print(f"❌ {e}")
        raise SystemExit(2)
    if getattr(args, "id", None):
        tous = [s for s in tous if s.id in args.id]
    if getattr(args, "tag", None):
        tous = [s for s in tous if args.tag in s.tags]
    return tous


def _valider(args) -> int:
    scenarios = _scenarios(args)
    for s in scenarios:
        print(f"✔ {s.id:8} {len(s.tours)} tour(s) × {s.passages} passage(s) — {s.titre}")
    print(f"\n{len(scenarios)} scénario(s) valide(s). Messages envoyés au bot : {nombre_de_messages(scenarios)}")
    return 0


def _session(_args) -> int:
    from telethon.sessions import StringSession
    from telethon.sync import TelegramClient
    api_id = int(input("api_id (my.telegram.org) : ").strip())
    api_hash = input("api_hash : ").strip()
    with TelegramClient(StringSession(), api_id, api_hash) as client:  # demande téléphone, code, 2FA
        moi = client.get_me()
        print(f"\nConnecté : {moi.first_name} (id {moi.id})\n")
        print("Copier la ligne ci-dessous dans .env.test (c'est un SECRET, ne jamais la commiter) :\n")
        print(f"TELEGRAM_TEST_SESSION={client.session.save()}")
    return 0


async def _avec_pilote(fonction):
    from .harness.driver import PiloteTelegram
    async with PiloteTelegram(cfg_mod.lire()) as pilote:
        return await fonction(pilote)


def _seed(_args) -> int:
    from .harness.base import creer_potager_de_test

    async def chat(pilote):
        return pilote.mon_id
    chat_id = asyncio.run(_avec_pilote(chat))
    print(creer_potager_de_test(chat_id))
    return 0


def _lancer(args) -> int:
    scenarios = _scenarios(args)
    if not scenarios:
        print("Aucun scénario retenu.")
        return 2
    volume = nombre_de_messages(scenarios, args.passages)
    print(f"{len(scenarios)} scénario(s) · {volume} message(s) envoyés au bot de test, "
          f"donc jusqu'à {volume} appel(s) au modèle de l'agent.")
    if not args.go:
        print("Rien n'est lancé. Relancer avec --go pour jouer la campagne.")
        return 2

    from .harness import report
    from .harness.base import BaseTest

    async def campagne(pilote):
        base = BaseTest(pilote.mon_id)
        avant = base.jetons()
        resultats = await jouer(scenarios, pilote, base, args.passages, avancer=lambda s: print(f"  … {s}", flush=True))
        apres = base.jetons()
        return resultats, {k: apres[k] - avant[k] for k in apres}

    resultats, jetons = asyncio.run(_avec_pilote(campagne))
    dossier = cfg_mod.DOSSIER_RAPPORTS / datetime.now().strftime("%Y%m%d-%H%M%S")
    chemins = report.ecrire(dossier, resultats, report.meta(cfg_mod.RACINE, jetons))
    for r in resultats:
        print(f"{r.statut:13} {r.scenario.id:8} {r.taux:4.0%}  {r.scenario.titre}")
    print(f"\nRapport : {chemins['html']}")
    return 1 if any(r.statut == ECHEC for r in resultats) else 0


def main(argv=None) -> int:
    for flux in (sys.stdout, sys.stderr):  # console Windows en cp1252 : les ✔ et les accents passent
        if hasattr(flux, "reconfigure"):
            flux.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="python -m tests_conv", description="Scénarios de dialogue joués sur Telegram")
    p.add_argument("--dossier", help="dossier de scénarios (défaut : tests_conv/scenarios)")
    sub = p.add_subparsers(dest="commande", required=True)
    sub.add_parser("validate", help="parse les scénarios sans rien exécuter")
    sub.add_parser("session", help="crée la session Telethon (interactif)")
    sub.add_parser("seed", help="crée le compte et le potager de test, lie le compte Telegram")
    r = sub.add_parser("run", help="joue les scénarios")
    r.add_argument("--id", nargs="+", help="identifiants de scénarios")
    r.add_argument("--tag", help="ne jouer que ce tag")
    r.add_argument("--passages", type=int, help="remplace le nombre de passages des scénarios")
    r.add_argument("--go", action="store_true", help="confirme l'envoi (sinon : annonce du volume seulement)")
    args = p.parse_args(argv)
    try:
        return {"validate": _valider, "session": _session, "seed": _seed, "run": _lancer}[args.commande](args)
    except cfg_mod.ConfigIncomplete as e:
        print(f"❌ {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())

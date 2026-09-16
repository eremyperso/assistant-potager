"""
tools/mesurer_modeles_llm.py — Comparaison mesurée de modèles Groq
==================================================================
Changer le modèle d'un type d'appel est une décision de configuration (US-092 /
CA3). Ce script existe pour qu'elle se **mesure** au lieu de se supposer : il
rejoue les mêmes saisies réelles sur plusieurs modèles et compare, champ à
champ, ce que chacun extrait.

Ce qui est mesuré, par modèle :

* **exactitude** — action / culture / quantité / unité contre la vérité terrain
  du corpus. C'est le seul chiffre qui décide : un modèle deux fois moins cher
  qui enregistre la mauvaise culture ne fait économiser à personne.
* **coût** — jetons d'entrée, de sortie, et jetons servis depuis le cache de
  prompt du fournisseur. Un modèle qui rend le préfixe non cachable annule la
  garantie CA6 de la passerelle, ce qui ne se voit pas sur le prix affiché.
* **latence** — médiane et p95, la queue comptant plus que la moyenne pour un
  jardinier qui attend une réponse dans Telegram.

Le corpus (`tests/corpus/us094_saisies_reelles.csv`) porte des saisies
RÉELLES de production, pas des phrases imaginées. Seules les phrases à vérité
terrain non ambiguë entrent dans l'assiette : ligne unique par texte (une phrase
à deux évènements n'a pas d'attendu unique) et `corrigee=0` (une valeur corrigée
à la main n'est plus la sortie d'un modèle) — même règle que le CA6 d'US-094.

Le champ `date` n'est pas noté : il dépend du jour d'ancrage de la saisie, pas
de la qualité du modèle.

Utilisation :
    python tools/mesurer_modeles_llm.py --dry-run          # le plan, sans dépenser un jeton
    python tools/mesurer_modeles_llm.py                    # 250 requêtes, 2 modèles
    python tools/mesurer_modeles_llm.py --requetes 40 --modeles openai/gpt-oss-120b

⚠️ Chaque exécution consomme le quota Groq réel de la clé configurée : 250
requêtes sur le prompt de parsing représentent de l'ordre de 500 k jetons
d'entrée. `--dry-run` affiche l'assiette et le nombre d'appels avant d'engager
quoi que ce soit.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
import time
from collections import defaultdict
from datetime import date, timedelta
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


import groq  # noqa: E402
from groq import Groq  # noqa: E402

from app.services.evenements import (  # noqa: E402
    _normalize_unite_denombrement,
    _normalize_unite_semis,
)
from config import GROQ_API_KEY, GROQ_REASONING_EFFORT, GROQ_TIMEOUT_S  # noqa: E402
from llm.groq_client import PARSE_PROMPT, _nettoyer_backticks, _today_context  # noqa: E402
from llm.passerelle import _accepte_reasoning_effort  # noqa: E402

CORPUS_PAR_DEFAUT = "tests/corpus/us094_saisies_reelles.csv"
MODELES_PAR_DEFAUT = "groq/compound-mini,openai/gpt-oss-120b"
REQUETES_PAR_DEFAUT = 250

# Champs notés. `date` en est exclu (dépend du jour d'ancrage, pas du modèle) et
# `parcelle` aussi : le corpus la porte normalisée, le modèle en clair.
CHAMPS_NOTES = ("action", "culture", "quantite", "unite")


def _valeur(brut: str) -> Optional[str]:
    """Cellule vide du corpus = absence, pas chaîne vide."""
    brut = (brut or "").strip()
    return brut or None


def charger_corpus(chemin: Path) -> list[dict]:
    """Saisies à vérité terrain non ambiguë : un seul attendu par texte, non
    corrigé à la main. Les autres sortent de l'assiette de comparaison."""
    par_texte: dict[str, list[dict]] = defaultdict(list)
    with chemin.open(encoding="utf-8", newline="") as fichier:
        for ligne in csv.DictReader(fichier):
            texte = (ligne.get("texte") or "").strip()
            if texte:
                par_texte[texte].append(ligne)

    assiette = []
    for texte, lignes in par_texte.items():
        if len(lignes) != 1 or lignes[0].get("corrigee") == "1":
            continue
        ligne = lignes[0]
        if not _valeur(ligne["action"]):
            continue  # sans action attendue, aucun champ noté n'est décidable
        assiette.append({
            "texte":    texte,
            "action":   _valeur(ligne["action"]),
            "culture":  _valeur(ligne["culture"]),
            "quantite": float(ligne["quantite"]) if ligne["quantite"] else None,
            "unite":    _valeur(ligne["unite"]),
        })
    assiette.sort(key=lambda l: l["texte"])  # ordre stable d'une exécution à l'autre
    return assiette


def construire_prompt() -> str:
    """Le prompt RÉEL de `groq_client.parse_commande()` — mesurer sur un prompt
    de laboratoire ne dirait rien du comportement en production."""
    aujourd_hui = date.today()
    return PARSE_PROMPT.format(
        date_context = _today_context(),
        today_iso    = aujourd_hui.isoformat(),
        yesterday    = (aujourd_hui - timedelta(days=1)).isoformat(),
        day_before   = (aujourd_hui - timedelta(days=2)).isoformat(),
    )


def _premier_item(brut: str) -> Optional[dict]:
    """Le parsing peut rendre un objet ou un tableau : on note le premier item."""
    charge = json.loads(_nettoyer_backticks(brut))
    if isinstance(charge, list):
        charge = charge[0] if charge else None
    return charge if isinstance(charge, dict) else None


def _normaliser_unite(item: dict, texte: str) -> Optional[str]:
    """Même normalisation que le CA6 d'US-094 : sans elle on compterait comme
    écart ce que la validation centrale aurait de toute façon harmonisé.

    `texte` n'est pas décoratif : `_normalize_unite_semis` ne retient une unité
    autre que « graines » que si elle est réellement prononcée dans la dictée.
    Lui passer une chaîne vide ramènerait tous les semis à « graines » et
    fabriquerait des écarts qui n'existent pas.
    """
    unite = item.get("unite")
    action = item.get("action")
    if action == "semis":
        return _normalize_unite_semis(unite, texte)
    return _normalize_unite_denombrement(unite, action)


def comparer(item: dict, attendu: dict) -> dict[str, bool]:
    """Compare champ à champ. Retourne {champ: exact}."""
    quantite = item.get("quantite")
    if isinstance(quantite, (int, float)):
        quantite = float(quantite)
    elif quantite is not None:
        try:
            quantite = float(str(quantite).replace(",", "."))
        except ValueError:
            quantite = None

    return {
        "action":   item.get("action") == attendu["action"],
        "culture":  item.get("culture") == attendu["culture"],
        "quantite": quantite == attendu["quantite"],
        "unite":    _normaliser_unite(item, attendu["texte"]) == attendu["unite"],
    }


def _attente_recommandee(erreur: Exception, defaut: float) -> float:
    """Temporisation dictée par l'en-tête `retry-after` du fournisseur.

    Contrairement à la passerelle — qui plafonne court parce qu'un jardinier
    attend derrière (CA12) —, une mesure hors ligne a tout intérêt à patienter
    le temps demandé : abandonner transformerait une limite de débit en « échec
    du modèle », ce qui fausserait la comparaison au lieu de la retarder.
    """
    reponse = getattr(erreur, "response", None)
    try:
        brut = reponse.headers.get("retry-after") if reponse is not None else None
        return max(float(brut), 0.0)
    except (AttributeError, TypeError, ValueError):
        return defaut


def appeler(client: Groq, modele: str, prompt: str, texte: str,
            tentatives: int = 5, attente_max: float = 90.0) -> dict:
    """Un appel, mesuré. Mêmes paramètres que `passerelle.appeler_chat()` sur le
    type `parsing`, garde `reasoning_effort` comprise — sinon on mesurerait un
    chemin que l'application n'emprunte pas.

    La latence rapportée est celle du dernier essai : le temps passé à attendre
    une fenêtre de débit n'est pas un temps de réponse du modèle et n'a rien à
    faire dans la médiane.
    """
    kwargs = {
        "model": modele,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user",   "content": texte},
        ],
        "temperature": 0.0,
        "max_tokens": 1024,
        "stream": False,
    }
    if GROQ_REASONING_EFFORT and _accepte_reasoning_effort(modele):
        kwargs["reasoning_effort"] = GROQ_REASONING_EFFORT

    attendu_total = 0.0
    for essai in range(tentatives):
        debut = time.monotonic()
        try:
            reponse = client.chat.completions.create(**kwargs)
            break
        except groq.RateLimitError as e:
            if essai == tentatives - 1:
                return {"issue": "quota", "erreur": "RateLimitError",
                        "latence_ms": int((time.monotonic() - debut) * 1000),
                        "attente_s": round(attendu_total, 1)}
            attente = min(_attente_recommandee(e, 2.0 * (essai + 1)), attente_max)
            attendu_total += attente
            time.sleep(attente)
        except Exception as e:
            return {"issue": "erreur", "erreur": type(e).__name__,
                    "latence_ms": int((time.monotonic() - debut) * 1000),
                    "attente_s": round(attendu_total, 1)}

    latence_ms = int((time.monotonic() - debut) * 1000)
    usage = getattr(reponse, "usage", None)
    details = getattr(usage, "prompt_tokens_details", None)
    return {
        "issue":        "ok",
        "contenu":      reponse.choices[0].message.content or "",
        "tokens_in":    getattr(usage, "prompt_tokens", 0) or 0,
        "tokens_out":   getattr(usage, "completion_tokens", 0) or 0,
        "tokens_cache": (getattr(details, "cached_tokens", 0) or 0) if details else 0,
        "latence_ms":   latence_ms,
        "attente_s":    round(attendu_total, 1),
    }


def _resume(modele: str, lignes: list[dict]) -> dict:
    reussis = [l for l in lignes if l["issue"] == "ok"]
    lisibles = [l for l in reussis if l["json_valide"]]
    latences = [l["latence_ms"] for l in reussis] or [0]
    latences_triees = sorted(latences)
    exacts = [l for l in lisibles if l["exact"]]
    return {
        "modele":       modele,
        "appels":       len(lignes),
        "erreurs":      len(lignes) - len(reussis),
        "json_valide":  len(lisibles),
        "exacts":       len(exacts),
        "exactitude":   (len(exacts) / len(lignes) * 100) if lignes else 0.0,
        "tokens_in":    sum(l.get("tokens_in", 0) for l in reussis),
        "tokens_out":   sum(l.get("tokens_out", 0) for l in reussis),
        "tokens_cache": sum(l.get("tokens_cache", 0) for l in reussis),
        "latence_med":  statistics.median(latences),
        "latence_p95":  latences_triees[min(len(latences_triees) - 1,
                                            int(len(latences_triees) * 0.95))],
        "attente_s":    sum(l.get("attente_s", 0.0) for l in lignes),
        **{f"champ_{c}": sum(1 for l in lisibles if l[f"exact_{c}"]) for c in CHAMPS_NOTES},
    }


def main(argv: "Optional[list[str]]" = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare des modèles Groq sur les saisies réelles du corpus US-094.",
    )
    parser.add_argument("--modeles", default=MODELES_PAR_DEFAUT,
                        help=f"modèles à comparer, séparés par une virgule (défaut : {MODELES_PAR_DEFAUT})")
    parser.add_argument("--requetes", type=int, default=REQUETES_PAR_DEFAUT,
                        help=f"nombre TOTAL d'appels, réparti entre les modèles (défaut : {REQUETES_PAR_DEFAUT})")
    parser.add_argument("--corpus", default=CORPUS_PAR_DEFAUT,
                        help=f"corpus de saisies réelles (défaut : {CORPUS_PAR_DEFAUT})")
    parser.add_argument("--sortie", default=None,
                        help="fichier CSV de résultat (défaut : docs/MESURE_MODELES_LLM_<date>.csv)")
    parser.add_argument("--pause", type=float, default=0.0,
                        help="temporisation entre deux appels, en secondes (limites de débit)")
    parser.add_argument("--dry-run", action="store_true",
                        help="affiche l'assiette et le nombre d'appels sans rien envoyer")
    args = parser.parse_args(argv)

    racine = Path(__file__).resolve().parent.parent
    chemin_corpus = Path(args.corpus)
    if not chemin_corpus.is_absolute():
        chemin_corpus = racine / chemin_corpus
    if not chemin_corpus.exists():
        print(f"❌ corpus introuvable : {chemin_corpus}")
        return 1

    modeles = [m.strip() for m in args.modeles.split(",") if m.strip()]
    if not modeles:
        print("❌ aucun modèle à comparer")
        return 1

    assiette = charger_corpus(chemin_corpus)
    par_modele = args.requetes // len(modeles)
    if par_modele == 0:
        print(f"❌ --requetes {args.requetes} pour {len(modeles)} modèles : moins d'un appel par modèle")
        return 1
    tronquee = par_modele > len(assiette)
    phrases = assiette[:par_modele]
    appels = len(phrases) * len(modeles)

    print("═" * 78)
    print("MESURE COMPARATIVE DE MODÈLES — parsing de saisies réelles")
    print("═" * 78)
    print(f"corpus          : {chemin_corpus.relative_to(racine)}")
    print(f"assiette        : {len(assiette)} saisies à vérité terrain non ambiguë")
    print(f"modèles         : {', '.join(modeles)}")
    print(f"phrases/modèle  : {len(phrases)}")
    print(f"appels au total : {appels}")
    if tronquee:
        print(f"⚠️  corpus trop court pour {par_modele} phrases/modèle : réduit à {len(phrases)}")
    if args.dry_run:
        print("\n(--dry-run : aucun appel envoyé, aucun jeton dépensé)")
        return 0

    sortie = Path(args.sortie) if args.sortie else (
        racine / "docs" / f"MESURE_MODELES_LLM_{date.today().isoformat()}.csv")
    if not sortie.is_absolute():
        sortie = racine / sortie
    sortie.parent.mkdir(parents=True, exist_ok=True)

    colonnes = ["modele", "texte", "issue", "erreur", "exact", "json_valide"]
    for champ in CHAMPS_NOTES:
        colonnes += [f"attendu_{champ}", f"obtenu_{champ}", f"exact_{champ}"]
    colonnes += ["tokens_in", "tokens_out", "tokens_cache", "latence_ms", "attente_s"]

    client = Groq(api_key=GROQ_API_KEY, max_retries=0, timeout=GROQ_TIMEOUT_S)
    prompt = construire_prompt()
    resultats: list[dict] = []

    # Écriture au fil de l'eau, jamais à la fin : sous limite de débit une
    # mesure de 250 appels dure une heure, et un run interrompu à la 240ᵉ ne
    # doit pas repartir de rien.
    fichier = sortie.open("w", encoding="utf-8", newline="")
    redacteur = csv.DictWriter(fichier, fieldnames=colonnes)
    redacteur.writeheader()
    fichier.flush()

    for modele in modeles:
        print(f"\n▶ {modele}", flush=True)
        for i, attendu in enumerate(phrases, 1):
            mesure = appeler(client, modele, prompt, attendu["texte"])
            ligne = {
                "modele":       modele,
                "texte":        attendu["texte"],
                "issue":        mesure["issue"],
                "erreur":       mesure.get("erreur", ""),
                "latence_ms":   mesure.get("latence_ms", 0),
                "attente_s":    mesure.get("attente_s", 0.0),
                "tokens_in":    mesure.get("tokens_in", 0),
                "tokens_out":   mesure.get("tokens_out", 0),
                "tokens_cache": mesure.get("tokens_cache", 0),
                "json_valide":  False,
                "exact":        False,
            }
            for champ in CHAMPS_NOTES:
                ligne[f"attendu_{champ}"] = attendu[champ]
                ligne[f"obtenu_{champ}"] = ""
                ligne[f"exact_{champ}"] = False

            if mesure["issue"] == "ok":
                try:
                    item = _premier_item(mesure["contenu"])
                except Exception:
                    item = None
                if item is not None:
                    ligne["json_valide"] = True
                    exactitudes = comparer(item, attendu)
                    for champ in CHAMPS_NOTES:
                        valeur = (_normaliser_unite(item, attendu["texte"])
                                  if champ == "unite" else item.get(champ))
                        ligne[f"obtenu_{champ}"] = "" if valeur is None else valeur
                        ligne[f"exact_{champ}"] = exactitudes[champ]
                    ligne["exact"] = all(exactitudes.values())

            resultats.append(ligne)
            redacteur.writerow(ligne)
            fichier.flush()
            if i % 25 == 0 or i == len(phrases):
                justes = sum(1 for l in resultats if l["modele"] == modele and l["exact"])
                print(f"   {i:>4}/{len(phrases)} appels │ {justes} exacts", flush=True)
            if args.pause:
                time.sleep(args.pause)

    fichier.close()

    print("\n" + "═" * 78)
    print("RÉSULTAT")
    print("═" * 78)
    entete = (f"{'modèle':<24} {'exact':>12} {'JSON':>6} {'err':>4} "
              f"{'jetons in':>10} {'out':>7} {'cache':>7} {'méd':>6} {'p95':>6}")
    print(entete)
    print("─" * len(entete))
    resumes = []
    for modele in modeles:
        r = _resume(modele, [l for l in resultats if l["modele"] == modele])
        resumes.append(r)
        print(f"{modele:<24} {r['exacts']:>4}/{r['appels']:<3} {r['exactitude']:>4.0f}% "
              f"{r['json_valide']:>6} {r['erreurs']:>4} "
              f"{r['tokens_in']:>10} {r['tokens_out']:>7} {r['tokens_cache']:>7} "
              f"{r['latence_med']:>5.0f}ms {r['latence_p95']:>5.0f}ms")

    print("\nExactitude par champ (sur les réponses au JSON lisible) :")
    entete_champs = f"{'modèle':<24}" + "".join(f"{c:>12}" for c in CHAMPS_NOTES)
    print(entete_champs)
    print("─" * len(entete_champs))
    for r in resumes:
        ligne = f"{r['modele']:<24}"
        for champ in CHAMPS_NOTES:
            total = r["json_valide"] or 1
            ligne += f"{r[f'champ_{champ}'] / total * 100:>11.0f}%"
        print(ligne)

    attente = sum(r["attente_s"] for r in resumes)
    if attente:
        print(f"\n⏳ {attente:.0f} s passées à attendre une fenêtre de débit "
              f"(hors latences ci-dessus, qui ne comptent que le temps du modèle).")

    if len(resumes) > 1 and all(r["tokens_cache"] == 0 for r in resumes):
        print("\n⚠️  aucun jeton servi depuis le cache de prompt sur AUCUN modèle :")
        print("   la garantie CA6 de la passerelle ne joue pas dans cette mesure")
        print("   (prompt reconstruit à chaque appel, préfixe jamais réchauffé).")

    print(f"\n📄 détail par requête : {sortie}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

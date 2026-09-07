"""
tools/controler_aide_corpus.py — `/help` et le corpus disent-ils la même chose ? [US-099 / CA7]
================================================================================================
`/help` est le **sommaire court**, le corpus de connaissance en est la **forme
longue**. Le CA7 exige que les deux ne divergent pas, et surtout qu'un domaine
d'aide ne se retrouve jamais sans fiche : un jardinier à qui `/help` annonce un
domaine et à qui l'assistant répond « je ne sais pas » sur ce domaine perd
confiance dans les deux à la fois.

Ce contrôle compare donc deux listes, et rien d'autre :

* les **domaines déclarés par la commande d'aide** — `bot._HELP_DOMAINES`, la
  liste dont `/help` dérive lui-même son sommaire (elle n'est pas recopiée) ;
* les **domaines déclarés par les fiches** — la clé `domaines_aide:` de leur
  en-tête, lue par l'analyseur d'en-tête d'US-098 et par lui seul.

Il lit le DÉPÔT, pas la base : c'est l'arbitrage d'US-098 (« la base est
l'index, le dépôt est la source »). Une fiche corrigée mais pas encore ingérée
doit faire passer le contrôle ; une fiche ingérée mais supprimée du dépôt doit
le faire échouer. L'inverse reviendrait à valider un corpus que personne ne peut
plus relire.

Deux écarts sont signalés, et un seul est bloquant :

* **domaine non couvert** — `/help` annonce un domaine qu'aucune fiche ne
  traite. Bloquant : c'est exactement la promesse non tenue décrite plus haut.
* **domaine orphelin** — une fiche se réclame d'un domaine que `/help` ne
  connaît pas. Signalé sans bloquer : c'est presque toujours une faute de frappe
  ou un domaine retiré du sommaire, jamais une régression pour le jardinier.

Utilisation :
    python tools/controler_aide_corpus.py             # rapport + code de retour
    python tools/controler_aide_corpus.py --detail    # liste les fiches par domaine
    python tools/controler_aide_corpus.py --racine <dossier>

Zéro appel réseau, zéro appel modèle, zéro accès base — comme
`tools/ingerer_connaissance.py`, dont il réutilise l'analyseur d'en-tête plutôt
que d'en écrire un second : deux lecteurs du même format finiraient par diverger.
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# La console Windows par défaut est en cp1252 : sans cela, le rapport plante à
# l'affichage sur un simple « ✅ ». Un outil de contrôle ne doit pas échouer sur
# son encodage de sortie.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):  # flux redirigé qui ne le supporte pas
    pass

from unidecode import unidecode  # noqa: E402

from tools.ingerer_connaissance import DocumentInvalide, lire_entete  # noqa: E402

RACINE_PAR_DEFAUT = "data/connaissance/doc_app"

# Clé d'en-tête portant les domaines d'aide couverts par la fiche. L'ingestion
# ne la lit pas — elle n'a rien à indexer là-dedans — mais elle la traverse sans
# broncher, comme `theme:` ou `version:` : un repère éditorial de plus.
CLE_DOMAINES = "domaines_aide"

# Séparateurs tolérés dans la valeur : `culture ; fiche` comme `culture, fiche`.
_SEPARATEURS = (";", ",", "·")


def _normaliser(valeur: str) -> str:
    """Comparaison insensible à la casse et aux accents — « Récolte » et
    « recolte » désignent le même domaine, comme dans `/help` lui-même."""
    return " ".join(unidecode(valeur).lower().split())


@dataclass(frozen=True)
class FicheAide:
    """Une fiche du corpus, réduite à ce que ce contrôle a besoin de savoir."""

    chemin: Path
    titre: str
    famille: str
    domaines: tuple[str, ...]


@dataclass
class Rapport:
    couverture: dict[str, tuple[str, ...]] = field(default_factory=dict)
    manquants: tuple[str, ...] = ()
    orphelins: tuple[str, ...] = ()
    erreurs: list[str] = field(default_factory=list)

    @property
    def conforme(self) -> bool:
        """Seul un domaine non couvert fait échouer le contrôle — un orphelin
        se signale, il ne bloque pas une livraison."""
        return not self.manquants and not self.erreurs


def decouper_domaines(valeur: Optional[str]) -> tuple[str, ...]:
    """Découpe la valeur de `domaines_aide:` en domaines normalisés."""
    if not valeur:
        return ()
    fragments = [valeur]
    for separateur in _SEPARATEURS:
        fragments = [bribe for morceau in fragments for bribe in morceau.split(separateur)]
    return tuple(dict.fromkeys(_normaliser(f) for f in fragments if f.strip()))


def lire_fiches(racine: Path) -> tuple[list[FicheAide], list[str]]:
    """Lit les fiches d'un dossier de corpus. Rend `(fiches, erreurs)`.

    Une fiche illisible est une ERREUR remontée, jamais une fiche ignorée en
    silence : un en-tête cassé ne doit pas se traduire par « domaine non
    couvert » sans qu'on sache pourquoi.
    """
    fiches: list[FicheAide] = []
    erreurs: list[str] = []
    for chemin in sorted(racine.rglob("*.md")):
        if chemin.name.upper() == "README.MD":
            continue  # le gabarit documente le format, ce n'est pas du contenu
        try:
            entete, _ = lire_entete(chemin.read_text(encoding="utf-8"))
        except DocumentInvalide as erreur:
            erreurs.append(f"{chemin.name} : {erreur}")
            continue
        fiches.append(FicheAide(
            chemin=chemin,
            titre=entete.get("titre", chemin.stem),
            famille=entete.get("famille", ""),
            domaines=decouper_domaines(entete.get(CLE_DOMAINES)),
        ))
    return fiches, erreurs


def controler(domaines_aide: Iterable[str], fiches: Iterable[FicheAide],
              erreurs: Optional[Iterable[str]] = None) -> Rapport:
    """Compare les domaines de `/help` à ceux que les fiches déclarent couvrir."""
    attendus = tuple(dict.fromkeys(_normaliser(d) for d in domaines_aide))
    fiches = list(fiches)

    couverture: dict[str, tuple[str, ...]] = {}
    for domaine in attendus:
        couverture[domaine] = tuple(
            fiche.chemin.name for fiche in fiches if domaine in fiche.domaines
        )

    declares = {domaine for fiche in fiches for domaine in fiche.domaines}
    return Rapport(
        couverture=couverture,
        manquants=tuple(d for d in attendus if not couverture[d]),
        orphelins=tuple(sorted(declares - set(attendus))),
        erreurs=list(erreurs or []),
    )


def domaines_de_l_aide() -> tuple[str, ...]:
    """Les domaines déclarés par la commande d'aide, lus dans `bot.py`.

    Import tardif et volontairement local : ce module doit rester importable
    (et testable) sans `python-telegram-bot` ni jeton, exactement comme
    `app/services/menu_commandes.py` se construit à partir de noms qu'on lui
    passe plutôt qu'en allant les chercher lui-même.
    """
    from bot import _HELP_DOMAINES
    return tuple(_HELP_DOMAINES)


def main(argv: "Optional[list[str]]" = None) -> int:
    parser = argparse.ArgumentParser(
        description="Vérifie que chaque domaine de /help possède au moins une fiche (US-099 / CA7)."
    )
    parser.add_argument("--racine", default=RACINE_PAR_DEFAUT,
                        help=f"Dossier des fiches de fonctionnement (défaut : {RACINE_PAR_DEFAUT})")
    parser.add_argument("--detail", action="store_true",
                        help="Liste les fiches retenues pour chaque domaine")
    args = parser.parse_args(argv)

    racine_depot = Path(__file__).resolve().parent.parent
    racine = Path(args.racine)
    if not racine.is_absolute():
        racine = (racine_depot / racine).resolve()
    if not racine.is_dir():
        print(f"Racine introuvable : {racine}")
        return 2

    fiches, erreurs = lire_fiches(racine)
    rapport = controler(domaines_de_l_aide(), fiches, erreurs)

    print(f"── COHÉRENCE /help ↔ CORPUS (US-099 / CA7) · {racine} ──")
    print(f"Fiches lues : {len(fiches)} · domaines annoncés par /help : {len(rapport.couverture)}")
    if args.detail:
        for domaine, noms in rapport.couverture.items():
            marque = "✅" if noms else "❌"
            print(f"  {marque} {domaine:<10} {', '.join(noms) if noms else '— aucune fiche'}")

    if rapport.orphelins:
        print(f"\n⚠️  {len(rapport.orphelins)} domaine(s) déclaré(s) par une fiche mais absent(s) de /help :")
        for domaine in rapport.orphelins:
            print(f"   · {domaine}")

    if rapport.erreurs:
        print(f"\n❌ {len(rapport.erreurs)} fiche(s) illisible(s) :")
        for ligne in rapport.erreurs:
            print(f"   · {ligne}")

    if rapport.manquants:
        print(f"\n❌ {len(rapport.manquants)} domaine(s) de /help sans aucune fiche :")
        for domaine in rapport.manquants:
            print(f"   · {domaine}")
        print("\nÉcrire la fiche manquante, ou retirer le domaine du sommaire de /help.")
        return 1

    if not rapport.conforme:
        return 1
    print("\n✅ Chaque domaine annoncé par /help est couvert par au moins une fiche.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

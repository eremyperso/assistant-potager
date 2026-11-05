"""Markdown → objets `Scenario`, avec des erreurs qui disent le fichier et la ligne.

Format d'un scénario (un fichier `.md` = un scénario) :

    ---
    id: SC-010
    titre: Plantation de tomates avec confirmation
    tags: [critique, plantation]
    passages: 3          # exécutions, remise à zéro entre chacune (défaut 1)
    seuil: 0.8           # part de passages réussis exigée (défaut 1.0)
    parcelles: [Serre, Carré nord]     # créées avant chaque passage
    ---

    ## Tour 1
    > j'ai planté 12 tomates dans la serre

    - texte contient: tomate
    - bouton: Confirmer
    - aucune écriture

    ## Tour 2 — le jardinier confirme
    [clic] Confirmer

    - écriture: plantation
    - événement: culture=tomate, quantite=12

Un tour a UN message (`> ...`, plusieurs lignes `>` se joignent) OU UN clic (`[clic] libellé`).
Chaque puce `- clé: valeur` est une vérification BLOQUANTE ; `- ? clé: valeur` est
informative (elle ne fait pas échouer le passage). Tout le reste du texte est commentaire.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from .texte import norm

#: clé normalisée (sans accent, minuscule) → genre interne
CLES = {
    "texte contient": "texte_contient",
    "texte ne contient pas": "texte_absent",
    "texte regex": "texte_regex",
    "bouton": "bouton",
    "aucun bouton": "aucun_bouton",
    "aucune ecriture": "aucune_ecriture",
    "ecriture": "ecriture",
    "evenement": "evenement",
    "outil": "outil",
    "latence max": "latence_max",
    "juge": "juge",
}
SANS_VALEUR = {"aucun_bouton", "aucune_ecriture"}
CHAMPS_EVENEMENT = {"type_action", "culture", "variete", "quantite", "unite", "rang", "parcelle"}


class ScenarioInvalide(Exception):
    def __init__(self, fichier: Path, ligne: int, message: str):
        super().__init__(f"{fichier.name}:{ligne} — {message}")
        self.fichier, self.ligne, self.message = fichier, ligne, message


@dataclass(frozen=True)
class Verification:
    genre: str
    valeur: str = ""
    bloquante: bool = True
    ligne: int = 0

    @property
    def libelle(self) -> str:
        return f"{self.genre}: {self.valeur}" if self.valeur else self.genre


@dataclass(frozen=True)
class Tour:
    numero: int
    titre: str
    message: str = ""
    clic: str = ""
    verifications: tuple[Verification, ...] = ()


@dataclass(frozen=True)
class Scenario:
    id: str
    titre: str
    fichier: Path
    tours: tuple[Tour, ...]
    tags: tuple[str, ...] = ()
    passages: int = 1
    seuil: float = 1.0
    parcelles: tuple[str, ...] = ()


def _verification(fichier: Path, ligne: int, brut: str) -> Verification:
    bloquante = True
    if brut.startswith("?"):
        bloquante, brut = False, brut[1:].strip()
    cle, _, valeur = brut.partition(":")
    genre = CLES.get(norm(cle))
    if genre is None:
        connues = ", ".join(sorted(CLES))
        raise ScenarioInvalide(fichier, ligne, f"vérification inconnue « {cle.strip()} » (connues : {connues})")
    valeur = valeur.strip()
    if genre in SANS_VALEUR:
        if valeur:
            raise ScenarioInvalide(fichier, ligne, f"« {cle.strip()} » ne prend pas de valeur")
        return Verification(genre, "", bloquante, ligne)
    if not valeur:
        raise ScenarioInvalide(fichier, ligne, f"« {cle.strip()} » demande une valeur après les deux-points")
    if genre == "texte_regex":
        try:
            re.compile(valeur)
        except re.error as e:
            raise ScenarioInvalide(fichier, ligne, f"expression régulière invalide : {e}") from e
    if genre == "latence_max":
        try:
            float(valeur.replace(",", ".").removesuffix("s"))
        except ValueError as e:
            raise ScenarioInvalide(fichier, ligne, "latence max attend un nombre de secondes") from e
    if genre == "evenement":
        for morceau in valeur.split(","):
            champ, egal, _ = morceau.partition("=")
            if not egal or norm(champ).replace(" ", "_") not in CHAMPS_EVENEMENT:
                raise ScenarioInvalide(
                    fichier, ligne,
                    f"événement : « {morceau.strip()} » n'est pas champ=valeur — les champs sont séparés par "
                    f"des virgules, les décimales s'écrivent avec un point (champs : {', '.join(sorted(CHAMPS_EVENEMENT))})")
    return Verification(genre, valeur, bloquante, ligne)


def _entete(fichier: Path, texte: str) -> tuple[dict, int]:
    lignes = texte.splitlines()
    if not lignes or lignes[0].strip() != "---":
        raise ScenarioInvalide(fichier, 1, "le fichier doit commencer par un en-tête `---`")
    for i, ligne in enumerate(lignes[1:], start=2):
        if ligne.strip() == "---":
            try:
                donnees = yaml.safe_load("\n".join(lignes[1:i - 1])) or {}
            except yaml.YAMLError as e:
                raise ScenarioInvalide(fichier, 1, f"en-tête YAML illisible : {e}") from e
            if not isinstance(donnees, dict):
                raise ScenarioInvalide(fichier, 1, "l'en-tête doit être une suite de `clé: valeur`")
            return donnees, i
    raise ScenarioInvalide(fichier, 1, "en-tête `---` jamais refermé")


def charger(fichier: Path) -> Scenario:
    texte = fichier.read_text(encoding="utf-8")
    meta, fin_entete = _entete(fichier, texte)
    for obligatoire in ("id", "titre"):
        if not meta.get(obligatoire):
            raise ScenarioInvalide(fichier, 1, f"en-tête : `{obligatoire}` est obligatoire")
    passages = meta.get("passages", 1)
    seuil = meta.get("seuil", 1.0)
    if not isinstance(passages, int) or passages < 1:
        raise ScenarioInvalide(fichier, 1, "en-tête : `passages` doit être un entier ≥ 1")
    if not isinstance(seuil, (int, float)) or not 0 < seuil <= 1:
        raise ScenarioInvalide(fichier, 1, "en-tête : `seuil` doit être compris entre 0 (exclu) et 1")

    tours: list[Tour] = []
    courant: Optional[dict] = None

    def clore() -> None:
        if courant is None:
            return
        if bool(courant["message"]) == bool(courant["clic"]):
            raise ScenarioInvalide(
                fichier, courant["ligne"],
                f"le tour {courant['numero']} doit avoir un message (`> ...`) OU un clic (`[clic] ...`)")
        tours.append(Tour(courant["numero"], courant["titre"], courant["message"], courant["clic"],
                          tuple(courant["verifs"])))

    for n, ligne in enumerate(texte.splitlines()[fin_entete:], start=fin_entete + 1):
        brut = ligne.strip()
        m = re.match(r"^##\s+Tour\s+(\d+)\s*(?:[—:-]\s*(.*))?$", brut, re.IGNORECASE)
        if m:
            clore()
            numero = int(m.group(1))
            if numero != len(tours) + 1:
                raise ScenarioInvalide(fichier, n, f"les tours se numérotent 1, 2, 3… (lu : {numero})")
            courant = {"numero": numero, "titre": (m.group(2) or "").strip(), "message": "",
                       "clic": "", "verifs": [], "ligne": n}
            continue
        if courant is None:
            continue
        if brut.startswith(">"):
            morceau = brut[1:].strip()
            courant["message"] = f"{courant['message']}\n{morceau}".strip() if courant["message"] else morceau
        elif brut.lower().startswith("[clic]"):
            courant["clic"] = brut[6:].strip()
        elif brut.startswith("- ") or brut == "-":
            courant["verifs"].append(_verification(fichier, n, brut[1:].strip()))
    clore()
    if not tours:
        raise ScenarioInvalide(fichier, fin_entete, "aucun tour : ajouter au moins un `## Tour 1`")

    tags = meta.get("tags") or []
    parcelles = meta.get("parcelles") or []
    if not isinstance(tags, list) or not isinstance(parcelles, list):
        raise ScenarioInvalide(fichier, 1, "en-tête : `tags` et `parcelles` sont des listes")
    return Scenario(
        id=str(meta["id"]), titre=str(meta["titre"]), fichier=fichier, tours=tuple(tours),
        tags=tuple(str(t) for t in tags), passages=passages, seuil=float(seuil),
        parcelles=tuple(str(p) for p in parcelles),
    )


def charger_dossier(dossier: Path) -> list[Scenario]:
    """Tous les `.md` du dossier (sauf `README.md`), triés par nom ; les identifiants sont uniques."""
    scenarios = [charger(f) for f in sorted(dossier.glob("*.md")) if f.name.lower() != "readme.md"]
    vus: dict[str, Path] = {}
    for sc in scenarios:
        if sc.id in vus:
            raise ScenarioInvalide(sc.fichier, 1, f"identifiant `{sc.id}` déjà pris par {vus[sc.id].name}")
        vus[sc.id] = sc.fichier
    return scenarios

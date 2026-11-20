"""Le jeu d'évaluation du compagnon [US-336] : son format, son chargement, ses contrôles.

Le fichier `tests/corpus/jeu_evaluation_compagnon.json` range des BESOINS ; chaque besoin porte une fiche de
besoin par défaut, des attendus par défaut et 5 à 10 FORMULATIONS. Le chargeur développe chaque formulation en
un CAS autonome (fiche et attendus résolus) : c'est le cas qui se joue, se note et se rapporte.

Le format est décrit dans `docs/EPIC - AGENT INTERPRETEUR/JEU_EVALUATION_COMPAGNON.md`.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from unidecode import unidecode

RACINE = Path(__file__).resolve().parent.parent.parent
JEU = RACINE / "tests" / "corpus" / "jeu_evaluation_compagnon.json"

JEU_NEUF = "neuf"
JEU_REMPLI = "rempli"
JEUX_DE_DONNEES = (JEU_NEUF, JEU_REMPLI)

GENRES = ("directe", "familiere", "incomplete", "faute", "deux_temps", "culture_absente", "reel")
#: Ce que le jardinier peut dire, et qu'on ne lui redemande pas une fois dit.
CHAMPS_FICHE = ("culture", "variete", "parcelle", "quantite", "unite", "date")
#: Faits de la fiche qui ne se redemandent pas mais que le jardinier peut dire s'il y est invité.
CHAMPS_LIBRES = ("symptome", "cause", "contexte")
VALEURS_PAR_DEFAUT = ("permise", "aucune")
COUVRE = ("semis_initial", "premiere_recolte", "nieme_recolte", "fin_de_vie")
CULTURE_TYPES = ("vegetatif", "reproducteur_pleine_terre", "reproducteur_plants", "aucune")

#: Minimums de la story (CA1 à CA6 d'US-336).
BESOINS_MIN = 20
FORMULATIONS_MIN = 5
CAS_COUVERTURE_ABSENTE_MIN = 3
PART_RENOUVELABLE_MIN = 1 / 3

_CLES_FORMULATION = {"genre", "ouverture", "suite", "renouvelable", "simule", "tours_max", "source", "fiche",
                     "attendus", "attendus_tours", "couverture_absente"}
_CLES_BESOIN = {"id", "libelle", "categorie", "jeu_de_donnees", "culture_type", "fiche", "attendus",
                "formulations", "couvre"}


class JeuInvalideError(ValueError):
    """Le fichier du jeu n'a pas la forme attendue."""


def normaliser(texte: Any) -> str:
    """Minuscules, sans accent ni ponctuation, espaces réduits : la forme pour comparer deux phrases."""
    brut = unidecode(str(texte or "")).lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", brut)).strip()


def singulier(mot: str) -> str:
    return mot[:-1] if len(mot) > 3 and mot.endswith("s") else mot


@dataclass(frozen=True)
class Attendus:
    """Ce qu'est une bonne réponse, et ce qui est interdit. Tout ce qui est contrôlable par le code l'est."""

    bonne_reponse: str
    #: Valeurs de la fiche qu'on ne redemande jamais une fois dites (culture, parcelle, quantite, date…).
    ne_jamais_redemander: tuple[str, ...] = ()
    #: Types de geste ou noms d'outil d'écriture interdits ; « * » : aucune écriture du tout.
    ecritures_interdites: tuple[str, ...] = ()
    #: Aucun passage d'une autre culture que celle de la fiche n'est montré comme réponse.
    passages_hors_culture_interdits: bool = True
    #: Cultures autres que la fiche qu'une bonne réponse peut citer (« * » : toutes — que semer ce mois-ci…).
    cultures_admises: tuple[str, ...] = ()
    #: La culture n'a pas de fiche agronomique : la réponse doit dire que la couverture est absente.
    couverture_absente: bool = False
    #: « permise » : proposer une valeur par défaut que le jardinier accepte (« 10 plants, ça te va ? »).
    #: Jamais une valeur non dite DANS une proposition d'écriture, jamais la même question à chaque tour.
    valeur_par_defaut: str = "permise"
    #: Groupes d'alternatives : chaque groupe doit être couvert par au moins une expression du texte lu.
    textes_attendus: tuple[tuple[str, ...], ...] = ()
    textes_interdits: tuple[str, ...] = ()
    #: [Références humaines du 18/11] Groupes d'outils : chaque groupe doit voir au moins un de ses outils appelé
    #: (« meteo » / « voir_meteo »…). « lire:parcelles » : l'outil `lire` avec `quoi=parcelles`.
    outils_attendus: tuple[tuple[str, ...], ...] = ()
    #: Types de geste qu'une proposition ne porte jamais sans parcelle (« plantation ») : le compagnon la demande.
    parcelle_requise: tuple[str, ...] = ()

    @classmethod
    def depuis_dict(cls, d: dict) -> "Attendus":
        inconnues = set(d) - {f for f in cls.__dataclass_fields__}
        if inconnues:
            raise JeuInvalideError(f"attendus : clé(s) inconnue(s) {sorted(inconnues)}")
        d = dict(d)
        cultures_admises = tuple(d.get("cultures_admises") or ())
        valeur = d.get("valeur_par_defaut", "permise")
        if valeur not in VALEURS_PAR_DEFAUT:
            raise JeuInvalideError(f"attendus : valeur_par_defaut {valeur!r} inconnue")
        return cls(
            bonne_reponse=str(d.get("bonne_reponse") or "").strip(),
            ne_jamais_redemander=tuple(d.get("ne_jamais_redemander") or ()),
            ecritures_interdites=tuple(d.get("ecritures_interdites") or ()),
            passages_hors_culture_interdits=bool(d.get("passages_hors_culture_interdits", not cultures_admises)),
            cultures_admises=cultures_admises, couverture_absente=bool(d.get("couverture_absente", False)),
            valeur_par_defaut=valeur,
            textes_attendus=tuple(tuple(g) for g in (d.get("textes_attendus") or ())),
            textes_interdits=tuple(d.get("textes_interdits") or ()),
            outils_attendus=tuple(tuple(g) for g in (d.get("outils_attendus") or ())),
            parcelle_requise=tuple(d.get("parcelle_requise") or ()),
        )

    @property
    def interdit_toute_ecriture(self) -> bool:
        return "*" in self.ecritures_interdites

    @property
    def admet_toute_culture(self) -> bool:
        return "*" in self.cultures_admises


@dataclass(frozen=True)
class Cas:
    id: str
    besoin: str
    libelle: str
    categorie: str
    genre: str
    ouverture: str
    #: Phrases écrites d'avance, jouées après l'ouverture ; ensuite, l'utilisateur simulé répond.
    suite: tuple[str, ...]
    #: Faux : le dialogue est rejoué tel qu'écrit, sans utilisateur simulé (dialogue réel du 14/11).
    simule: bool
    tours_max: int
    jeu_de_donnees: str
    culture_type: str
    fiche: dict
    attendus: Attendus
    #: Attendus supplémentaires d'un tour précis (rang du tour → dict), ex. le texte attendu au tour 1.
    attendus_tours: dict = field(default_factory=dict)
    renouvelable: bool = False
    source: str = ""
    couvre: str = ""

    @property
    def phrases_ecrites(self) -> tuple[str, ...]:
        return (self.ouverture, *self.suite)

    def attendus_du_tour(self, rang: int) -> Optional[Attendus]:
        """Les attendus propres au tour `rang`, ou `None`."""
        brut = self.attendus_tours.get(str(rang))
        if not brut:
            return None
        return Attendus.depuis_dict({"bonne_reponse": self.attendus.bonne_reponse, **brut})


@dataclass(frozen=True)
class Jeu:
    cas: tuple[Cas, ...]
    besoins: tuple[dict, ...]
    jeux_de_donnees: dict
    configurations: tuple[dict, ...]
    chemin: Optional[Path] = None

    def cas_par_id(self, identifiant: str) -> Cas:
        for c in self.cas:
            if c.id == identifiant:
                return c
        raise KeyError(identifiant)

    def filtrer(self, *, besoins: Iterable[str] = (), jeu: str = "", renouvelables: Optional[bool] = None,
                limite: int = 0) -> "Jeu":
        retenus = [c for c in self.cas
                   if (not besoins or c.besoin in set(besoins))
                   and (not jeu or c.jeu_de_donnees == jeu)
                   and (renouvelables is None or c.renouvelable == renouvelables)]
        if limite:
            retenus = retenus[:limite]
        return Jeu(tuple(retenus), self.besoins, self.jeux_de_donnees, self.configurations, self.chemin)


def _fusion_attendus(base: dict, surcharge: dict) -> dict:
    return {**base, **surcharge}


def charger(chemin: Path = JEU) -> Jeu:
    """Lit le jeu, développe les formulations en cas, et refuse toute clé inconnue (une faute de frappe dans un
    attendu ne doit pas passer pour « aucun attendu »)."""
    brut = json.loads(Path(chemin).read_text(encoding="utf-8"))
    jeux_de_donnees = brut.get("jeux_de_donnees") or {}
    cas: list[Cas] = []
    ids: set[str] = set()
    for b in brut.get("besoins", []):
        inconnues = set(b) - _CLES_BESOIN
        if inconnues:
            raise JeuInvalideError(f"{b.get('id')} : clé(s) inconnue(s) {sorted(inconnues)}")
        if b["jeu_de_donnees"] not in JEUX_DE_DONNEES:
            raise JeuInvalideError(f"{b['id']} : jeu de données inconnu {b['jeu_de_donnees']!r}")
        if b["culture_type"] not in CULTURE_TYPES:
            raise JeuInvalideError(f"{b['id']} : type de culture inconnu {b['culture_type']!r}")
        if b.get("couvre") and b["couvre"] not in COUVRE:
            raise JeuInvalideError(f"{b['id']} : « couvre » inconnu {b['couvre']!r}")
        if "fiche" not in b:
            raise JeuInvalideError(f"{b['id']} : un besoin porte sa fiche de besoin (vide si rien n'est à dire)")
        for rang, f in enumerate(b.get("formulations", []), 1):
            identifiant = f"{b['id']}-F{rang}"
            inconnues = set(f) - _CLES_FORMULATION
            if inconnues:
                raise JeuInvalideError(f"{identifiant} : clé(s) inconnue(s) {sorted(inconnues)}")
            if f["genre"] not in GENRES:
                raise JeuInvalideError(f"{identifiant} : genre inconnu {f['genre']!r}")
            if identifiant in ids:
                raise JeuInvalideError(f"identifiant en double : {identifiant}")
            ids.add(identifiant)
            attendus = _fusion_attendus(b["attendus"], f.get("attendus") or {})
            if "couverture_absente" in f:
                attendus["couverture_absente"] = f["couverture_absente"]
            fiche = {**b["fiche"], **(f.get("fiche") or {})}
            suite = tuple(f.get("suite") or ())
            cas.append(Cas(
                id=identifiant, besoin=b["id"], libelle=b["libelle"], categorie=b["categorie"], genre=f["genre"],
                ouverture=f["ouverture"], suite=suite, simule=bool(f.get("simule", True)),
                tours_max=int(f.get("tours_max", 4)), jeu_de_donnees=b["jeu_de_donnees"],
                culture_type=b["culture_type"], fiche=fiche, attendus=Attendus.depuis_dict(attendus),
                attendus_tours=dict(f.get("attendus_tours") or {}), renouvelable=bool(f.get("renouvelable", False)),
                source=f.get("source", ""), couvre=b.get("couvre", ""),
            ))
    return Jeu(tuple(cas), tuple(brut.get("besoins", [])), jeux_de_donnees, tuple(brut.get("configurations", [])),
               Path(chemin))


# ═════════════════════════════════════════════════════════════════════════════
# Les exigences de la story (CA1 à CA8), contrôlées sur le fichier
# ═════════════════════════════════════════════════════════════════════════════
DIALOGUE_1411 = ("j'aimerai planter des salades", "oui si tu veux", "oui je veux bien", "la planche légumes",
                 "demain", "des salades", "comment je plante des salades ?")


def controler_exigences(jeu: Jeu) -> list[str]:
    """La liste des écarts entre le jeu et les critères d'acceptance d'US-336 ; vide quand tout tient."""
    ecarts: list[str] = []
    par_besoin: dict[str, list[Cas]] = {}
    for c in jeu.cas:
        par_besoin.setdefault(c.besoin, []).append(c)

    # CA1 — au moins 20 besoins, au moins 5 formulations chacun, chacune avec fiche et attendus
    if len(par_besoin) < BESOINS_MIN:
        ecarts.append(f"CA1 : {len(par_besoin)} besoin(s), {BESOINS_MIN} attendus au moins")
    for besoin, cas in par_besoin.items():
        if len(cas) < FORMULATIONS_MIN:
            ecarts.append(f"CA1 : {besoin} n'a que {len(cas)} formulation(s), {FORMULATIONS_MIN} au moins")
        for c in cas:
            if not c.attendus.bonne_reponse:
                ecarts.append(f"CA1 : {c.id} sans attendu « bonne réponse »")
            if not (c.attendus.ne_jamais_redemander or c.attendus.ecritures_interdites
                    or c.attendus.passages_hors_culture_interdits or c.attendus.cultures_admises):
                ecarts.append(f"CA1 : {c.id} sans aucun attendu contrôlable")

    # CA2 — le dialogue du 14/11 est le cas n° 1
    if not jeu.cas:
        return ecarts + ["le jeu est vide"]
    premier = jeu.cas[0]
    if premier.genre != "reel" or premier.phrases_ecrites != DIALOGUE_1411 or premier.simule:
        ecarts.append("CA2 : le premier cas n'est pas le dialogue du 14/11 en 7 phrases réelles")
    if premier.jeu_de_donnees != JEU_NEUF:
        ecarts.append("CA2 : le dialogue du 14/11 se joue sur le potager neuf")
    tour_1 = premier.attendus_tours.get("1", {})
    if not tour_1.get("textes_attendus"):
        ecarts.append("CA2 : l'attendu du tour 1 (saison, prochaine fenêtre, salade absente) manque")

    # CA3 — chaque cas indique son jeu de données ; le potager neuf vient d'un script rejouable
    for c in jeu.cas:
        if c.jeu_de_donnees not in jeu.jeux_de_donnees:
            ecarts.append(f"CA3 : {c.id} : jeu de données {c.jeu_de_donnees!r} non décrit")
    if not (jeu.jeux_de_donnees.get(JEU_NEUF) or {}).get("script"):
        ecarts.append("CA3 : le potager neuf n'indique pas son script de création")

    # CA4 — les écritures d'une culture reproductive semée en pleine terre
    couverts = {c.couvre for c in jeu.cas if c.couvre and c.culture_type == "reproducteur_pleine_terre"}
    for attendu in ("semis_initial", "premiere_recolte", "nieme_recolte", "fin_de_vie"):
        if attendu not in couverts:
            ecarts.append(f"CA4 : aucun besoin « {attendu} » sur une culture reproductrice semée en pleine terre")
    for c in jeu.cas:
        if c.couvre in ("premiere_recolte", "nieme_recolte") and "perte" not in c.attendus.ecritures_interdites:
            ecarts.append(f"CA4 : {c.id} : une récolte ne doit jamais être attendue comme une perte de stock")

    # Les trois types de culture (story : végétatif, reproducteur en pleine terre, reproducteur en plants)
    types = {c.culture_type for c in jeu.cas}
    for t in ("vegetatif", "reproducteur_pleine_terre", "reproducteur_plants"):
        if t not in types:
            ecarts.append(f"Cultures : aucun cas « {t} »")

    # CA5 — au moins 3 cas sur une culture sans fiche agronomique
    sans_fiche = [c for c in jeu.cas if c.attendus.couverture_absente]
    if len(sans_fiche) < CAS_COUVERTURE_ABSENTE_MIN:
        ecarts.append(f"CA5 : {len(sans_fiche)} cas « couverture absente », {CAS_COUVERTURE_ABSENTE_MIN} au moins")

    # CA6 — un tiers renouvelable
    renouvelables = [c for c in jeu.cas if c.renouvelable]
    if jeu.cas and len(renouvelables) / len(jeu.cas) < PART_RENOUVELABLE_MIN:
        ecarts.append(f"CA6 : {len(renouvelables)} cas renouvelables sur {len(jeu.cas)}, un tiers au moins")

    # CA8 — les quatre configurations de référence, avec leurs résultats du 14/11
    ids = {c.get("id"): c for c in jeu.configurations}
    for k in ("A", "B", "C", "D"):
        if k not in ids:
            ecarts.append(f"CA8 : configuration {k} absente")
        elif not ids[k].get("resultats_14_11"):
            ecarts.append(f"CA8 : configuration {k} sans résultats du 14/11")

    # Les formulations couvrent les genres de la story
    genres = {c.genre for c in jeu.cas}
    for g in ("directe", "familiere", "incomplete", "faute", "deux_temps", "culture_absente"):
        if g not in genres:
            ecarts.append(f"Formulations : aucune formulation « {g} »")
    return ecarts


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — les cas renouvelables n'apparaissent dans aucun exemple de prompt
# ═════════════════════════════════════════════════════════════════════════════
_GUILLEMETS = re.compile(r"«\s*([^»]+?)\s*»|“([^”]+)”|\"([^\"\n]{3,200})\"")


def exemples_de_prompt(textes: Iterable[str]) -> set[str]:
    """Les exemples cités entre guillemets dans les textes de prompt, normalisés."""
    exemples: set[str] = set()
    for texte in textes:
        for m in _GUILLEMETS.finditer(texte or ""):
            exemple = normaliser(next(g for g in m.groups() if g))
            if exemple:
                exemples.add(exemple)
    return exemples


def controler_renouvelables(jeu: Jeu, textes_de_prompt: Iterable[str]) -> list[str]:
    """Les cas renouvelables dont une phrase figure dans un exemple de prompt (liste vide : contrôle passé).

    Une phrase d'au moins deux mots est « dans » un exemple quand elle lui est égale, ou quand l'une contient l'autre et que la plus
    courte compte au moins trois mots : « planter salade » n'est pas dans tout exemple qui contient « planter »."""
    exemples = exemples_de_prompt(textes_de_prompt)
    fautifs: list[str] = []
    for c in jeu.cas:
        if not c.renouvelable:
            continue
        for phrase in c.phrases_ecrites:
            p = normaliser(phrase)
            if len(p.split()) < 2:
                continue  # « oui », « demain » : une réponse d'un mot n'est la propriété d'aucun prompt
            if any(p == e or (len(p.split()) >= 3 and p in e) or (len(e.split()) >= 3 and e in p)
                   for e in exemples):
                fautifs.append(c.id)
                break
    return fautifs


def textes_des_prompts_livres() -> list[str]:
    """Tout ce qui est présenté au modèle comme exemple : prompts de l'agent actuel, prompt de la boucle à
    capacités, descriptions du catalogue et du registre."""
    textes: list[str] = []
    from app.services.agent import catalogue_outils, interpreteur_agent

    for nom in dir(interpreteur_agent):
        valeur = getattr(interpreteur_agent, nom)
        if "PROMPT" in nom and isinstance(valeur, str):
            textes.append(valeur)
    try:
        textes.append(json.dumps(catalogue_outils.schemas(catalogue_outils.PROJECTION_COMPLETE), ensure_ascii=False))
        textes.append(json.dumps(catalogue_outils.schemas_savoir(), ensure_ascii=False))
    except Exception:  # noqa: BLE001 — un catalogue illisible ne doit pas masquer le contrôle des prompts
        pass
    from tools.jeu_evaluation import moteurs

    textes.append(moteurs.PROMPT_CAPACITES)
    textes.append(moteurs.PROMPT_CLAUDE_MCP)
    return textes

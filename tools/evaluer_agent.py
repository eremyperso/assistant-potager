"""
tools/evaluer_agent.py — Mesure du modèle de l'agent interpréteur [US-233 / CA6, CA7, CA8]
============================================================================================
Le modèle de langage comprend-il une demande en français quand on lui décrit les
commandes sous forme d'OUTILS TYPÉS ? C'est la question du spike S0 de
l'architecture (`docs/EPIC - AGENT INTERPRETEUR/ARCHITECTURE_AGENT_INTERPRETEUR.md`,
§6) : ce script y répond par des chiffres, avant d'avoir construit le reste.

La mesure passe par la VRAIE passerelle (`llm.passerelle.appeler_chat_outils`) :
journalisation, consommation imputée au type `agent`, repli 429 — le chemin que
suivront les US suivantes, pas un script jetable. Aucun appel direct au SDK ici
(l'audit `tools/audit_appels_llm.py` y veille).

Ce qui est mesuré, par catégorie de phrases (`tests/corpus/us233_agent_echantillon.csv`) :

* **bon outil** — le premier outil appelé est celui attendu ;
* **bons paramètres** — chaque paramètre attendu est présent et juste (booléens et
  nombres exacts, textes à la casse, aux accents et aux espaces près), et le
  modèle n'a PAS ajouté de champ que le jardinier n'avait pas évoqué (c'est le
  risque que le validateur de l'architecture, règle 9, devra couvrir) ;
* **précision demandée quand il le fallait** — `demander_precision` sur les phrases
  ambiguës, jamais une commande complétée par supposition ;
* **latence** p50 / p95, **jetons** moyens par phrase et part servie par le cache.

[US-257] L'agent converse : `tool_choice="auto"`, une question ou un doute se disent en
texte (pseudo-attendu `texte` de l'échantillon : aucun appel, ou aucun qui écrive), ce
que l'application ne sait pas faire par le signal `manque_catalogue`. Ce script en mesure
le PREMIER tour, sur des phrases isolées ; la mesure de livraison, en plusieurs tours et
par la cascade du bot, est `tools/evaluer_dialogues.py`.

[INC-018] La mesure porte sur ce qui est LIVRÉ : `interpreteur_agent.PROMPT_FIXE` et
`catalogue_outils.schemas()` (le catalogue généré depuis `FORMES_DICTABLES`), pas
sur une copie. Un prompt ou un schéma retouché se remesure ici, sur le vrai modèle,
avant d'être remis en `AGENT_MODE=actif` : les tests simulent le modèle et ne voient
donc ni un 400 `tool_use_failed` ni un champ inventé.

L'échantillon d'origine (US-233, exprimé dans un catalogue provisoire) est traduit
dans le catalogue livré et enrichi des phrases d'INC-018 : créations avec ou sans
caractéristiques, phrases à plusieurs actions, conseils qui contiennent un verbe
d'action, doutes. Une séquence d'outils se note `a+b` (chacun doit être appelé).

Le prompt n'est pas ajusté pour faire passer l'échantillon : retoucher les
consignes jusqu'à ce qu'il passe mesurerait le prompt, pas le modèle.

Utilisation :
    python tools/evaluer_agent.py --dry-run                 # le plan, sans dépenser un jeton
    python tools/evaluer_agent.py                           # le modèle de GROQ_MODEL_AGENT
    python tools/evaluer_agent.py --modeles openai/gpt-oss-120b,openai/gpt-oss-20b
    python tools/evaluer_agent.py --detail --limite 10

⚠️ Chaque exécution consomme le quota Groq réel de la clé configurée (une
cinquantaine d'appels de ~1 000 jetons par modèle) et écrit des lignes
`conso_tokens` de type `agent` : c'est la preuve que la mesure passe par le chemin
réel. Le rapport est versé dans `docs/EPIC - AGENT INTERPRETEUR/` (celui d'US-233, mesuré
sur le catalogue provisoire, est conservé tel quel : `--rapport` choisit le fichier).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Callable, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# La console Windows par défaut est en cp1252 : sans cela, le rapport plante à
# l'affichage sur un simple « ✅ ». Un outil de mesure ne doit pas échouer sur
# son encodage de sortie.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):  # flux redirigé qui ne le supporte pas
    pass

from unidecode import unidecode  # noqa: E402

from app.services.agent import catalogue_outils, interpreteur_agent  # noqa: E402
from app.services.agent.projection import projection_pour  # noqa: E402
from app.services.context import TenantContext, default_context  # noqa: E402
from llm import passerelle  # noqa: E402

RACINE = Path(__file__).resolve().parent.parent
ECHANTILLON = RACINE / "tests" / "corpus" / "us233_agent_echantillon.csv"
CORPUS_US172 = RACINE / "tests" / "corpus" / "us172_commandes.csv"
RAPPORT = RACINE / "docs" / "EPIC - AGENT INTERPRETEUR" / "RAPPORT_US233_MESURE_MODELE.md"
RAPPORT_LIVRE = RACINE / "docs" / "EPIC - AGENT INTERPRETEUR" / "RAPPORT_INC018_MESURE_PROMPT_LIVRE.md"

#: Parcelles du potager fictif de la mesure : la liste que l'agent recevra en
#: contexte (architecture §3.4) pour rattacher « la serre » à « Serre extérieure ».
PARCELLES_DU_POTAGER = (
    "Serre extérieure", "Planche Nord", "Planche Sud", "Planche Centrale",
    "Carré des aromatiques", "Tunnel",
)

#: Champs de l'argument qui NOMMENT une entité existante : un rapprochement par
#: inclusion est accepté (« serre » pour « Serre extérieure »), l'égalité exacte
#: étant l'affaire du validateur d'US-235. Les autres textes sont comparés à égalité.
CHAMPS_ENTITE_EXISTANTE = frozenset({"parcelle", "ancien"})

#: Outils de l'architecture §3.3 qui ne sont pas des commandes : ils aiguillent ou signalent.
OUTILS_TERMINAUX = (*catalogue_outils.OUTILS_TERMINAUX, catalogue_outils.OUTIL_MANQUE_CATALOGUE)
#: [US-257] Une réponse en texte : aucun appel, ou aucun qui écrive.
PSEUDO_TEXTE = "texte"

#: Catégories qui relèvent de l'aiguillage (US-236), pas de la compréhension d'une commande.
CATEGORIES_AIGUILLAGE = ("question", "geste", "hors_perimetre")

#: [INC-018] Les phrases qui créent : le défaut venait d'un schéma refusé à l'écriture.
CATEGORIES_CREATION = ("creation", "creation_caracteristiques", "deux_actions")


# ═════════════════════════════════════════════════════════════════════════════
# Ce qui est mesuré : le prompt et le catalogue LIVRÉS [INC-018]
# ═════════════════════════════════════════════════════════════════════════════
PROMPT_FIXE = interpreteur_agent.PROMPT_FIXE
NOMS_OUTILS = tuple(outil.nom for outil in catalogue_outils.outils())


def prompt_variable(jour: Optional[date] = None) -> str:
    """Partie variable, celle que l'agent livré construit : date et parcelles du potager fictif."""
    return interpreteur_agent.prompt_variable(PARCELLES_DU_POTAGER, jour)


# ═════════════════════════════════════════════════════════════════════════════
# Échantillon
# ═════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Phrase:
    texte: str
    categorie: str
    outils_attendus: tuple[str, ...]      # un ou plusieurs outils acceptables
    parametres: dict
    source: str


def _valeur_typee(brut: str):
    brut = brut.strip()
    if brut.lower() in ("true", "false"):
        return brut.lower() == "true"
    try:
        return int(brut)
    except ValueError:
        pass
    try:
        return float(brut)
    except ValueError:
        return brut


def lire_parametres(brut: str) -> dict:
    """`cle=valeur|cle=valeur` → dict typé (booléens, entiers, décimaux, textes)."""
    resultat = {}
    for morceau in (brut or "").split("|"):
        if "=" in morceau:
            cle, valeur = morceau.split("=", 1)
            resultat[cle.strip()] = _valeur_typee(valeur)
    return resultat


def charger_echantillon(chemin: Path = ECHANTILLON) -> list[Phrase]:
    with chemin.open(encoding="utf-8", newline="") as fichier:
        return [
            Phrase(
                texte=ligne["phrase"].strip(),
                categorie=ligne["categorie"].strip(),
                outils_attendus=tuple(o.strip() for o in ligne["outil_attendu"].split("/")),
                parametres=lire_parametres(ligne["parametres_attendus"]),
                source=ligne["source"].strip(),
            )
            for ligne in csv.DictReader(fichier)
            if ligne["phrase"].strip()
        ]


# ═════════════════════════════════════════════════════════════════════════════
# Notation — pure, sans réseau
# ═════════════════════════════════════════════════════════════════════════════
def _normaliser(texte) -> str:
    return " ".join(unidecode(str(texte)).lower().split())


def valeur_conforme(champ: str, attendu, obtenu) -> bool:
    """Un paramètre est juste : booléen et nombre exacts, texte aux accents près."""
    if isinstance(attendu, bool):
        return obtenu is attendu
    if isinstance(attendu, (int, float)):
        return isinstance(obtenu, (int, float)) and not isinstance(obtenu, bool) \
            and float(obtenu) == float(attendu)
    a, o = _normaliser(attendu), _normaliser(obtenu)
    if champ in CHAMPS_ENTITE_EXISTANTE:
        return bool(a) and bool(o) and (a in o or o in a)
    return a == o


@dataclass(frozen=True)
class Notes:
    outil_ok: bool
    parametres_ok: Optional[bool]          # None : la phrase n'attend aucun paramètre
    champs_en_trop: tuple[str, ...]
    appels_multiples: bool
    destructif_errone: bool
    echec_technique: bool
    #: [INC-018] Le serveur a rejeté l'appel (400 `tool_use_failed`) : la phrase était
    #: peut-être comprise, c'est le schéma ou la génération qui a échoué.
    appel_invalide: bool = False
    #: [INC-018] `demander_precision` alors que l'attendu était autre chose.
    precision_inutile: bool = False

    @property
    def reussite(self) -> bool:
        """Le bon outil, avec de bons paramètres, sans champ ajouté."""
        return (self.outil_ok and self.parametres_ok in (True, None)
                and not self.champs_en_trop and not self.echec_technique)


def _sequence_ok(attendu: tuple[str, ...], appels: tuple) -> bool:
    """Une séquence `a+b` : chaque outil attendu est appelé, autant de fois qu'il est dit."""
    restants = [a.nom for a in appels]
    for souhaite in attendu[0].split("+"):
        if souhaite not in restants:
            return False
        restants.remove(souhaite)
    return True


def noter(phrase: Phrase, appels: tuple, statut: str) -> Notes:
    """Note UNE réponse. `appels` : les `AppelOutil` de la passerelle."""
    if PSEUDO_TEXTE in phrase.outils_attendus and statut == passerelle.STATUT_OK and all(
        a.nom in (catalogue_outils.OUTIL_LIRE, catalogue_outils.OUTIL_CONSULTER, catalogue_outils.OUTIL_MANQUE_CATALOGUE)
        for a in appels
    ):
        # [US-257] Répondre en texte, sans écriture, est la réponse attendue.
        return Notes(True, None, (), False, False, False)
    echec = (statut != passerelle.STATUT_OK or not appels
             or any(not a.arguments_valides for a in appels))
    premier = appels[0] if appels else None
    sequence = len(phrase.outils_attendus) == 1 and "+" in phrase.outils_attendus[0]
    if sequence:
        outil_ok = bool(appels) and _sequence_ok(phrase.outils_attendus, appels)
    else:
        outil_ok = premier is not None and premier.nom in phrase.outils_attendus

    parametres_ok: Optional[bool] = None
    en_trop: tuple[str, ...] = ()
    if phrase.parametres:
        arguments = premier.arguments if premier is not None else {}
        parametres_ok = outil_ok and all(
            cle in arguments and valeur_conforme(cle, valeur, arguments[cle])
            for cle, valeur in phrase.parametres.items()
        )
        if outil_ok:
            en_trop = tuple(sorted(
                cle for cle, valeur in arguments.items()
                if cle not in phrase.parametres and valeur not in (None, "")
            ))
    destructif = (any(a.nom == "supprimer_parcelle" for a in appels)
                  and "supprimer_parcelle" not in phrase.outils_attendus)
    return Notes(
        outil_ok, parametres_ok, en_trop,
        # Une séquence attendue n'est pas un défaut : plusieurs appels sont l'attendu.
        appels_multiples=len(appels) > 1 and not sequence,
        destructif_errone=destructif, echec_technique=echec,
        appel_invalide=statut == passerelle.STATUT_APPEL_INVALIDE,
        precision_inutile=bool(appels) and appels[0].nom == "demander_precision"
        and "demander_precision" not in phrase.outils_attendus,
    )


@dataclass
class Resultat:
    phrase: Phrase
    statut: str = passerelle.STATUT_OK     # ou "indisponible"
    appels: tuple = ()
    latence_ms: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    tokens_cache: int = 0
    quotas_429: int = 0
    notes: Optional[Notes] = None

    def obtenu(self) -> str:
        if not self.appels:
            return f"[{self.statut}]"
        return " + ".join(
            f"{a.nom}({json.dumps(a.arguments, ensure_ascii=False)})" for a in self.appels
        )


def percentile(valeurs: list[float], p: float) -> float:
    """Rang le plus proche (méthode usuelle des latences) ; 0 si aucune valeur."""
    if not valeurs:
        return 0.0
    ordonnees = sorted(valeurs)
    return float(ordonnees[max(0, math.ceil(p * len(ordonnees)) - 1)])


@dataclass
class Agregat:
    n: int = 0
    outil_ok: int = 0
    avec_parametres: int = 0
    parametres_ok: int = 0
    reussites: int = 0
    champs_en_trop: int = 0
    appels_multiples: int = 0
    destructifs_errones: int = 0
    echecs_techniques: int = 0
    appels_invalides: int = 0
    precisions_inutiles: int = 0
    quotas_429: int = 0
    latences: list = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    tokens_cache: int = 0

    @staticmethod
    def _taux(a: int, b: int) -> float:
        return 100.0 * a / b if b else 0.0

    @property
    def taux_outil(self) -> float:
        return self._taux(self.outil_ok, self.n)

    @property
    def taux_parametres(self) -> float:
        return self._taux(self.parametres_ok, self.avec_parametres)

    @property
    def taux_reussite(self) -> float:
        return self._taux(self.reussites, self.n)

    @property
    def taux_champs_en_trop(self) -> float:
        return self._taux(self.champs_en_trop, self.avec_parametres)

    @property
    def taux_echecs_techniques(self) -> float:
        return self._taux(self.echecs_techniques, self.n)

    @property
    def p50(self) -> float:
        return float(statistics.median(self.latences)) if self.latences else 0.0

    @property
    def p95(self) -> float:
        return percentile(self.latences, 0.95)

    @property
    def jetons_par_phrase(self) -> tuple[float, float]:
        appels = len(self.latences)
        return (self.tokens_in / appels, self.tokens_out / appels) if appels else (0.0, 0.0)

    @property
    def part_cache(self) -> float:
        return self._taux(self.tokens_cache, self.tokens_in)


def agreger(resultats: list[Resultat]) -> dict[str, Agregat]:
    """Un agrégat par catégorie, plus la clé « TOTAL »."""
    agregats: dict[str, Agregat] = defaultdict(Agregat)
    for r in resultats:
        n = r.notes
        for cle in (r.phrase.categorie, "TOTAL"):
            a = agregats[cle]
            a.n += 1
            a.outil_ok += n.outil_ok
            if n.parametres_ok is not None:
                a.avec_parametres += 1
                a.parametres_ok += bool(n.parametres_ok)
                a.champs_en_trop += bool(n.champs_en_trop)
            a.reussites += n.reussite
            a.appels_multiples += n.appels_multiples
            a.destructifs_errones += n.destructif_errone
            a.echecs_techniques += n.echec_technique
            a.appels_invalides += n.appel_invalide
            a.precisions_inutiles += n.precision_inutile
            a.quotas_429 += r.quotas_429
            if r.latence_ms:
                a.latences.append(r.latence_ms)
            a.tokens_in += r.tokens_in
            a.tokens_out += r.tokens_out
            a.tokens_cache += r.tokens_cache
    return dict(agregats)


# ═════════════════════════════════════════════════════════════════════════════
# Go / no-go [CA8] — les seuils sont fixés AVANT de voir les chiffres
# ═════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Critere:
    code: str
    libelle: str
    attendu: str
    mesure: str
    ok: bool
    critique: bool


def _combine(agregats: dict[str, Agregat], categories: tuple[str, ...]) -> Agregat:
    total = Agregat()
    for cat in categories:
        a = agregats.get(cat)
        if a is None:
            continue
        total.n += a.n
        total.reussites += a.reussites
        total.avec_parametres += a.avec_parametres
        total.champs_en_trop += a.champs_en_trop
        total.appels_invalides += a.appels_invalides
        total.precisions_inutiles += a.precisions_inutiles
    return total


def evaluer_criteres(agregats: dict[str, Agregat]) -> list[Critere]:
    """Les neuf critères du go / no-go. `critique` : un seul échec suffit à dire no-go."""
    total = agregats.get("TOTAL", Agregat())
    negations = agregats.get("negation", Agregat())
    paires = agregats.get("declaration_question", Agregat())
    ambigus = agregats.get("ambigu", Agregat())
    aiguillage = _combine(agregats, CATEGORIES_AIGUILLAGE)
    creations = _combine(agregats, CATEGORIES_CREATION)
    hors_doute = _combine(agregats, tuple(c for c in agregats if c not in ("TOTAL", "ambigu", "doute")))

    def pct(valeur: float) -> str:
        return f"{valeur:.1f} %"

    return [
        Critere("C1", "Bon outil, toutes phrases", "≥ 90 %", pct(total.taux_outil),
                total.taux_outil >= 90, True),
        Critere("C2", "Bons paramètres (phrases qui en attendent)", "≥ 90 %", pct(total.taux_parametres),
                total.taux_parametres >= 90, True),
        Critere("C3", "Négations et retraits : outil, paramètres, sans champ ajouté", "≥ 85 %",
                pct(negations.taux_reussite), negations.taux_reussite >= 85, True),
        Critere("C4", "Déclaration / question : la bonne des deux", "≥ 90 %",
                pct(paires.taux_reussite), paires.taux_reussite >= 90, True),
        Critere("C5", "Aucun appel destructeur erroné", "0",
                str(total.destructifs_errones), total.destructifs_errones == 0, True),
        Critere("C6", "Échecs techniques (appel malformé, outils refusés, indisponibilité)", "≤ 5 %",
                pct(total.taux_echecs_techniques), total.taux_echecs_techniques <= 5, True),
        Critere("C7", "Latence p95", "≤ 4 000 ms", f"{total.p95:.0f} ms", total.p95 <= 4000, True),
        Critere("C8", "Précision demandée sur les phrases ambiguës", "≥ 75 %",
                pct(ambigus.taux_reussite), ambigus.taux_reussite >= 75, False),
        Critere("C9", "Champs ajoutés sans avoir été évoqués", "≤ 10 %",
                pct(total.taux_champs_en_trop), total.taux_champs_en_trop <= 10, False),
        Critere("C10", "Aiguillage (question, geste, hors périmètre)", "≥ 85 %",
                pct(aiguillage.taux_reussite), aiguillage.taux_reussite >= 85, False),
        # [INC-018] Critères de sortie de l'étape 0 : sur le vrai modèle, aucune création
        # rejetée par le serveur, aucun champ inventé, aucune précision demandée pour rien.
        Critere("C11", "Appels rejetés par le serveur (`appel_invalide`), créations et plans", "0",
                str(creations.appels_invalides), creations.appels_invalides == 0, True),
        Critere("C12", "Champs inventés, toutes phrases à paramètres", "0",
                str(total.champs_en_trop), total.champs_en_trop == 0, True),
        Critere("C13", "Précisions demandées pour rien (phrases qui ne sont ni ambiguës ni douteuses)",
                "≤ 5 %", pct(100.0 * hors_doute.precisions_inutiles / hors_doute.n if hors_doute.n else 0.0),
                (hors_doute.precisions_inutiles / hors_doute.n if hors_doute.n else 0.0) <= 0.05, False),
    ]


def verdict(criteres: list[Critere]) -> str:
    if any(c.critique and not c.ok for c in criteres):
        return "NO-GO"
    return "GO" if all(c.ok for c in criteres) else "GO avec réserves"


def modele_retenu(evaluations: dict[str, tuple[dict[str, Agregat], list[Critere]]]) -> Optional[str]:
    """Parmi les modèles qui ne sont pas NO-GO : le plus juste, puis le plus rapide."""
    candidats = []
    for modele, (agregats, criteres) in evaluations.items():
        if verdict(criteres) == "NO-GO":
            continue
        total = agregats["TOTAL"]
        candidats.append((-total.taux_reussite, total.p95, modele))
    return min(candidats)[2] if candidats else None


# ═════════════════════════════════════════════════════════════════════════════
# Exécution — le seul endroit qui parle au modèle, et par la passerelle
# ═════════════════════════════════════════════════════════════════════════════
def lecture_fictive(arguments: dict, ctx: TenantContext) -> str:
    """Le résultat d'un appel de `lire` sur le potager fictif : les parcelles de la mesure,
    sans base. Seule la forme compte (`donnees`) : la mesure note l'appel suivant du modèle."""
    cible = str((arguments or {}).get("nom") or "").lower()
    donnees = [
        {"nom": nom, "nb_rangs": 4, "longueur_m": 10.0, "exposition": "Sud"}
        for nom in PARCELLES_DU_POTAGER
        if not cible or cible in nom.lower()
    ]
    return json.dumps({"donnees": donnees, "tronque": False}, ensure_ascii=False)


def appeler_agent(ctx: TenantContext, phrase: str, *, reasoning: bool = True):
    """La boucle de l'agent livré, par la passerelle, avec le catalogue et le prompt LIVRÉS.

    Elle rejoue `interpreteur_agent.proposer` : au plus `AGENT_MAX_TOURS` appels ; un tour
    sans `lire` la clôt, comme un outil terminal. Une écriture n'est jamais exécutée — le
    modèle lit « noté » — et `lire` reçoit un potager fictif. La réponse rendue porte les
    appels UTILES (hors `lire`), la latence et les jetons cumulés : c'est ce que le jardinier
    attend, et ce que mesure la boucle, pas un tour isolé.

    `reasoning=False` pour un modèle qui n'accepte pas `reasoning_effort` (llama,
    kimi…) : l'API répondrait 400 et la mesure serait celle d'un paramètre, pas du modèle.
    """
    historique: list[dict] = []
    utiles: list = []
    cumul = {"latence_ms": 0, "tokens_in": 0, "tokens_out": 0, "tokens_cache": 0}
    reponse = None
    for tour in range(1, interpreteur_agent._max_tours() + 1):
        arguments = dict(
            ctx=ctx,
            outils=catalogue_outils.schemas(projection_pour(phrase)),   # [US-276] comme le bot
            prompt_fixe=PROMPT_FIXE,
            prompt_variable=prompt_variable(),
            message_utilisateur=phrase,
            tool_choice="auto",   # [US-257] l'agent peut répondre en texte
            reasoning=reasoning,
        )
        if historique:
            arguments["historique"] = historique
        suivante = passerelle.appeler_chat_outils(**arguments)
        if reponse is not None and not suivante.ok:
            break  # le tour 1 a répondu : un échec ensuite ne l'annule pas
        reponse = suivante
        for cle in cumul:
            cumul[cle] += int(getattr(reponse, cle, 0) or 0)
        if not reponse.ok or not reponse.appels:
            break
        lit = any(a.nom == catalogue_outils.OUTIL_LIRE for a in reponse.appels)
        utiles += [a for a in reponse.appels if a.nom != catalogue_outils.OUTIL_LIRE]
        terminal = any(a.nom in OUTILS_TERMINAUX for a in utiles)
        if not lit or terminal or tour == interpreteur_agent._max_tours():
            break
        historique += interpreteur_agent._tour_suivant(reponse.appels, tour, ctx, lire=lecture_fictive)
    return replace(reponse, appels=tuple(utiles), **cumul) if reponse.ok else reponse


def executer_phrase(
    phrase: Phrase,
    appeler: Callable[[str], "passerelle.ReponseOutils"],
    *,
    tentatives: int = 4,
    attente_s: float = 20.0,
    dormir: Callable[[float], None] = time.sleep,
) -> Resultat:
    """Joue une phrase. Un 429 est ATTENDU puis rejoué (le quota gratuit se compte
    à la minute) et dénombré dans le rapport ; une panne ou un délai est noté comme
    échec technique sans interrompre la mesure."""
    resultat = Resultat(phrase=phrase)
    reponse = None
    for essai in range(1, tentatives + 1):
        try:
            reponse = appeler(phrase.texte)
            break
        except passerelle.QuotaLLMDepasseError:
            resultat.quotas_429 += 1
            dormir(attente_s * essai)
        except passerelle.LLMIndisponibleError:
            break
    if reponse is None:
        resultat.statut = "indisponible"
    else:
        resultat.statut = reponse.statut
        resultat.appels = reponse.appels
        resultat.latence_ms = reponse.latence_ms
        resultat.tokens_in = reponse.tokens_in
        resultat.tokens_out = reponse.tokens_out
        resultat.tokens_cache = reponse.tokens_cache
    resultat.notes = noter(phrase, resultat.appels, resultat.statut)
    return resultat


def evaluer_modele(
    modele: str,
    echantillon: list[Phrase],
    appeler: Callable[[str], "passerelle.ReponseOutils"],
    *,
    pause_s: float = 1.0,
    dormir: Callable[[float], None] = time.sleep,
    detail: bool = False,
) -> list[Resultat]:
    resultats = []
    for i, phrase in enumerate(echantillon, 1):
        resultat = executer_phrase(phrase, appeler, dormir=dormir)
        resultats.append(resultat)
        if detail:
            marque = "✅" if resultat.notes.reussite else "❌"
            print(f"  {marque} [{i:>2}/{len(echantillon)}] {phrase.texte}\n"
                  f"       attendu : {'/'.join(phrase.outils_attendus)} {phrase.parametres or ''}\n"
                  f"       obtenu  : {resultat.obtenu()}  ({resultat.latence_ms} ms)")
        if pause_s and i < len(echantillon):
            dormir(pause_s)
    return resultats


# ═════════════════════════════════════════════════════════════════════════════
# Rapport
# ═════════════════════════════════════════════════════════════════════════════
ORDRE_CATEGORIES = (
    "commande", "negation", "declaration_question", "ancrage_champ",
    "creation", "creation_caracteristiques", "deux_actions", "conseil_action", "doute",
    "question", "geste", "ambigu", "hors_perimetre",
)

LIBELLES_CATEGORIES = {
    "commande": "Commandes (corpus US-172)",
    "creation": "Créations (INC-018)",
    "creation_caracteristiques": "Créations avec caractéristiques",
    "deux_actions": "Phrases à plusieurs actions",
    "conseil_action": "Conseils avec un verbe d'action",
    "doute": "Doutes (action risquée ou sous-déterminée)",
    "negation": "Négations et retraits",
    "declaration_question": "Paires déclaration / question",
    "ancrage_champ": "Ancrage du champ (rien d'ajouté)",
    "question": "Questions (savoir, données)",
    "geste": "Gestes rapportés",
    "ambigu": "Demandes ambiguës",
    "hors_perimetre": "Hors périmètre",
}


def _ligne_categorie(cle: str, a: Agregat) -> str:
    parametres = f"{a.taux_parametres:.0f} % ({a.parametres_ok}/{a.avec_parametres})" if a.avec_parametres else "—"
    return (f"| {LIBELLES_CATEGORIES.get(cle, cle)} | {a.n} | {a.taux_outil:.0f} % ({a.outil_ok}/{a.n}) "
            f"| {parametres} | {a.champs_en_trop} | {a.appels_invalides} | {a.precisions_inutiles} "
            f"| {a.taux_reussite:.0f} % |")


def rediger_rapport(
    evaluations: dict[str, tuple[dict[str, Agregat], list[Critere], list[Resultat]]],
    *,
    jour: Optional[date] = None,
) -> str:
    """Rapport markdown. Il contient les chiffres et le verdict calculé ; le
    commentaire argumenté de l'analyste s'écrit à la suite (CA8)."""
    jour = jour or date.today()
    classement = {m: (ag, cr) for m, (ag, cr, _) in evaluations.items()}
    retenu = modele_retenu(classement)
    lignes = [
        f"# INC-018 — Mesure du prompt et du catalogue livrés, sur le vrai modèle ({jour.isoformat()})",
        "",
        "> Rapport produit par `python tools/evaluer_agent.py`. Les chiffres et le verdict "
        "calculé viennent de l'outil ; la section « Lecture » est écrite à la main.",
        "",
        "## Protocole",
        "",
        f"- **Échantillon** : {next(iter(evaluations.values()))[0]['TOTAL'].n} phrases "
        "(`tests/corpus/us233_agent_echantillon.csv`) : les phrases du corpus US-172 (source `us172`), "
        "des négations, des paires déclaration / question, des demandes ambiguës (source `nouveau`), puis "
        "les créations, phrases à plusieurs actions, conseils et doutes d'INC-018 (source `inc018`).",
        f"- **Catalogue d'outils** : celui livré (`catalogue_outils.schemas()`), {len(NOMS_OUTILS)} outils "
        f"({', '.join(NOMS_OUTILS)}), champs facultatifs nullables.",
        "- **Chemin** : `llm.passerelle.appeler_chat_outils`, `tool_choice=\"auto\"`, une seule tentative "
        "de la passerelle sur 429 (puis attente et nouvel essai par l'outil, dénombrés ci-dessous).",
        "- **Prompt** : `interpreteur_agent.PROMPT_FIXE`, tel que livré, **non ajusté sur ces résultats**.",
        "- **Notation** : bon outil = premier outil appelé ; bons paramètres = chaque paramètre attendu juste "
        "et aucun champ non évoqué ajouté.",
        "",
    ]
    for modele, (agregats, criteres, resultats) in evaluations.items():
        total = agregats["TOTAL"]
        jin, jout = total.jetons_par_phrase
        lignes += [
            f"## Modèle `{modele}` — {verdict(criteres)}",
            "",
            "### Par catégorie",
            "",
            "| Catégorie | Phrases | Bon outil | Bons paramètres | Champs ajoutés | Appels rejetés | Précisions inutiles | Réussite complète |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        lignes += [_ligne_categorie(c, agregats[c]) for c in ORDRE_CATEGORIES if c in agregats]
        lignes += [
            _ligne_categorie("TOTAL", total).replace("| TOTAL |", "| **Total** |"),
            "",
            "### Latence et jetons",
            "",
            "| p50 | p95 | Jetons d'entrée / phrase | Jetons de sortie / phrase | Part servie par le cache | 429 rencontrés |",
            "|---:|---:|---:|---:|---:|---:|",
            f"| {total.p50:.0f} ms | {total.p95:.0f} ms | {jin:.0f} | {jout:.0f} | {total.part_cache:.0f} % | {total.quotas_429} |",
            "",
            "### Critères du go / no-go",
            "",
            "| | Critère | Seuil | Mesuré | |",
            "|---|---|---:|---:|---|",
        ]
        for c in criteres:
            lignes.append(
                f"| {c.code}{' (critique)' if c.critique else ''} | {c.libelle} | {c.attendu} | {c.mesure} "
                f"| {'✅' if c.ok else '❌'} |"
            )
        echecs = sum(1 for r in resultats if not r.notes.reussite)
        lignes += [
            "", f"### Détail par phrase ({echecs} non réussie(s) sur {len(resultats)})", "",
            "| | Phrase | Attendu | Obtenu | Latence |",
            "|---|---|---|---|---:|",
        ]
        for r in resultats:
            attendu = "/".join(r.phrase.outils_attendus) + (f" {r.phrase.parametres}" if r.phrase.parametres else "")
            ligne = (f"| {'✅' if r.notes.reussite else '❌'} | {r.phrase.texte} | `{attendu}` "
                     f"| `{r.obtenu()}` | {r.latence_ms} ms |")
            lignes.append(ligne.replace("\n", " "))
        lignes.append("")

    lignes += [
        "## Verdict calculé",
        "",
        f"**Modèle retenu : {f'`{retenu}`' if retenu else 'aucun'}.** "
        + ("; ".join(f"`{m}` : {verdict(cr)}" for m, (_, cr) in classement.items()) + "."),
        "",
        "Règle : NO-GO si un critère critique (C1 à C7, C11, C12) échoue ; GO avec réserves si seuls C8 à C10 et C13 échouent ; "
        "GO sinon. Parmi les modèles qui ne sont pas NO-GO, le plus juste, puis le plus rapide.",
        "",
    ]
    return "\n".join(lignes)


# ═════════════════════════════════════════════════════════════════════════════
# Programme
# ═════════════════════════════════════════════════════════════════════════════
def estimer_jetons_entree(projection: str = catalogue_outils.PROJECTION_COMPLETE) -> int:
    """Ordre de grandeur du préfixe fixe, sans appel : ≈ 5 caractères par jeton,
    calibré sur la mesure du 21/10/2026 (977 jetons mesurés pour ≈ 4 960 caractères).
    [US-276] Par projection du catalogue : le complet par défaut."""
    schemas = catalogue_outils.schemas(projection)
    return int((len(json.dumps(schemas, ensure_ascii=False)) + len(PROMPT_FIXE)) / 5.0)


def plan(echantillon: list[Phrase], modeles: list[str]) -> str:
    categories = defaultdict(int)
    for p in echantillon:
        categories[p.categorie] += 1
    return "\n".join([
        "Plan de la mesure (rien n'est envoyé) :",
        f"  • modèles        : {', '.join(modeles)}",
        f"  • phrases        : {len(echantillon)} ("
        + ", ".join(f"{c} {n}" for c, n in categories.items()) + ")",
        f"  • outils         : {len(NOMS_OUTILS)} ({', '.join(NOMS_OUTILS)})",
        f"  • appels         : {len(echantillon) * len(modeles)}",
        f"  • jetons d'entrée: ≈ {estimer_jetons_entree()} par appel, soit ≈ "
        f"{estimer_jetons_entree() * len(echantillon) * len(modeles):,} au total".replace(",", " "),
    ])


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Mesure du prompt et du catalogue livrés de l'agent interpréteur (US-233, INC-018)")
    parser.add_argument("--dry-run", action="store_true", help="affiche le plan, n'appelle aucun modèle")
    parser.add_argument("--modeles", help="modèles à comparer, séparés par des virgules (défaut : GROQ_MODEL_AGENT)")
    parser.add_argument("--sans-raisonnement", default="",
                        help="modèles (séparés par des virgules) qui n'acceptent pas reasoning_effort")
    parser.add_argument("--limite", type=int, help="ne jouer que les N premières phrases")
    parser.add_argument("--pause", type=float, default=1.0, help="secondes entre deux appels (défaut 1)")
    parser.add_argument("--detail", action="store_true", help="affiche chaque phrase, son attendu et son obtenu")
    parser.add_argument("--rapport", default=str(RAPPORT_LIVRE), help="fichier du rapport markdown")
    parser.add_argument("--sans-rapport", action="store_true", help="n'écrit aucun fichier")
    args = parser.parse_args(argv)

    echantillon = charger_echantillon()
    if args.limite:
        echantillon = echantillon[: args.limite]
    modeles = [m.strip() for m in args.modeles.split(",")] if args.modeles else [passerelle.modele_pour(passerelle.TYPE_AGENT)]

    print(plan(echantillon, modeles))
    if args.dry_run:
        return 0

    ctx = default_context()
    sans_raisonnement = {m.strip() for m in args.sans_raisonnement.split(",") if m.strip()}
    evaluations = {}
    for modele in modeles:
        print(f"\n▶ {modele}")
        passerelle.GROQ_MODELE_PAR_TYPE[passerelle.TYPE_AGENT] = modele
        passerelle.reinitialiser_capacites_outils()
        raisonnement = modele not in sans_raisonnement
        resultats = evaluer_modele(
            modele, echantillon,
            lambda texte, r=raisonnement: appeler_agent(ctx, texte, reasoning=r),
            pause_s=args.pause, detail=args.detail,
        )
        agregats = agreger(resultats)
        evaluations[modele] = (agregats, evaluer_criteres(agregats), resultats)
        total = agregats["TOTAL"]
        print(f"  bon outil {total.taux_outil:.0f} % · paramètres {total.taux_parametres:.0f} % · "
              f"p95 {total.p95:.0f} ms · verdict {verdict(evaluations[modele][1])}")

    rapport = rediger_rapport(evaluations)
    if args.sans_rapport:
        print("\n" + rapport)
    else:
        chemin = Path(args.rapport)
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(rapport, encoding="utf-8")
        print(f"\nRapport écrit : {chemin}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

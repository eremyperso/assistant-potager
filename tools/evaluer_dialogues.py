"""
tools/evaluer_dialogues.py — Mesure du compagnon en plusieurs tours [US-256]
============================================================================
`tools/evaluer_agent.py` rejoue des PHRASES ISOLÉES. Le compagnon se juge sur
des DIALOGUES : une phrase, la proposition du bot, un clic ou une phrase de
suivi (« non 4 rangs », « en fait c'était 3 rangs »). Ce script rejoue le
corpus `tests/corpus/us256_dialogues.json` — les dialogues du §12.2 de
l'architecture, du §16.1 de l'étude d'articulation et du §1 du cadrage —
sur le vrai modèle, et dit par catégorie ce qu'il tient et ce qu'il rate.

Ce qui est rejoué est ce qui est LIVRÉ (CA3) :

* `interpreteur_commandes.interpreter` en mode `actif` : la cascade du bot —
  règles, garde de savoir, filtre « geste annoncé », puis l'agent
  (`interpreteur_agent.proposer`) avec la vraie boucle, le vrai prompt, le vrai
  catalogue et le vrai validateur. Une phrase que la cascade prend avant l'agent
  est notée sur son chemin et sortie des taux de l'agent : on ne mesure pas le
  modèle sur des phrases qu'il ne voit jamais ;
* le vrai contexte court (US-238), construit entre deux tours comme le fait le
  bot — une proposition en attente le nourrit, un clic le vide. Rien n'est
  exécuté : le potager est fictif, `lire` est simulé, l'aiguillage n'est pas
  persisté et l'ancien repli (`_appeler_modele`) est coupé ;
* la passerelle `llm.passerelle` : journalisation, repli 429 et ligne
  `conso_tokens` (`appel_type = 'agent'`) comme en production.

La clé d'API est DISTINCTE de celle du bot (CA3) : l'outil lit
`MISTRAL_API_KEY_MESURE`, refuse de tourner sans elle, et refuse qu'elle soit
identique à `MISTRAL_API_KEY`. La mesure ne consomme donc jamais le débit du bot.

Les trois modèles (CA4) : `ministral-3b-latest` est la référence ; `ministral-8b`
et `mistral-small` ne servent qu'à situer l'écart.

Le rapport (CA5, CA6, CA7) donne par catégorie le taux de bon outil, de bons
paramètres, les couperets du §12.10, la latence p50/p95 et les jetons par message.
Les couperets se comptent à deux niveaux : ce que le MODÈLE propose (une
tendance), et ce qui ARRIVE AU JARDINIER après le validateur et la cascade (le
niveau bloquant, qui fixe le code de sortie) ;
pour chaque catégorie en échec, d'abord l'ALLÈGEMENT du §4.5 du cadrage qui la
corrigerait, et seulement ensuite le modèle qui la corrigerait, avec son surcoût.
Il relève la grille tarifaire utilisée et ce que la mesure dit du cache de prompt.

Le prompt n'est jamais retouché pour faire passer le corpus : on mesure le
prompt livré, pas un prompt ajusté.

Utilisation :
    python tools/evaluer_dialogues.py --dry-run                      # le plan, la clé, 0 appel
    python tools/evaluer_dialogues.py                                # les trois modèles
    python tools/evaluer_dialogues.py --modeles mistral/ministral-3b-latest --detail
    python tools/evaluer_dialogues.py --categorie negations,doutes --limite 3

Code de sortie : 0 si aucun couperet n'atteint le jardinier sur le modèle de
référence, 1 sinon, 2 si la mesure ne peut pas partir (clé absente ou non distincte).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Callable, Iterator, Optional

RACINE = Path(__file__).resolve().parent.parent
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

# Console Windows en cp1252 : un « ✅ » ne doit pas faire échouer l'affichage.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

from app import config  # noqa: E402
from app.services import interpreteur_commandes  # noqa: E402
from app.services.agent import catalogue_outils, contexte_court, interpreteur_agent, lecture  # noqa: E402
from app.services.context import TenantContext, default_context  # noqa: E402
from app.services.interpreteur_commandes import (  # noqa: E402
    VERS_GESTE, VERS_QUESTION, Aiguillage, Ambiguite, CommandeInterpretee, Plan, ReponseAgent,
)
from llm import passerelle  # noqa: E402
from tools import evaluer_agent as ev  # noqa: E402

CORPUS = RACINE / "tests" / "corpus" / "us256_dialogues.json"
RAPPORT = RACINE / "docs" / "EPIC - COMPAGNON CONVERSATIONNEL" / "RAPPORT_US256_MESURE_COMPAGNON.md"

#: CA3 : la mesure a sa clé, jamais celle du bot.
VARIABLE_CLE_MESURE = "MISTRAL_API_KEY_MESURE"

#: CA4 : la référence d'abord, puis les deux modèles qui ne servent qu'à situer l'écart.
MODELE_REFERENCE = "mistral/ministral-3b-latest"
MODELES_PAR_DEFAUT = (MODELE_REFERENCE, "mistral/ministral-8b-latest", "mistral/mistral-small-latest")

#: En dessous, une catégorie est « en échec » (cadrage §7 : bonne action désignée ≥ 95 %).
SEUIL_REUSSITE = 0.90

#: Volumes du §12.9 de l'architecture, pour chiffrer un surcoût : messages par jour.
VOLUMES = (("régime stable", 50), ("mois de découverte", 200))

CLICS = ("Confirmer", "Annuler", "Corriger", "Tout confirmer")
PSEUDO_AUCUNE_ECRITURE = "aucune_ecriture"
#: [US-257] Une réponse en texte (une question, une explication), sans aucune écriture.
PSEUDO_TEXTE = "texte"

#: Ce qui ne modifie rien. Tout autre nom d'outil — y compris un nom inconnu — est une écriture.
OUTILS_SANS_ECRITURE = frozenset({
    catalogue_outils.OUTIL_LIRE, catalogue_outils.OUTIL_CONSULTER, catalogue_outils.OUTIL_MANQUE_CATALOGUE,
})

#: Couperet « 0 texte qui annonce une action non exécutée » (§12.10) : rien n'est jamais
#: exécuté pendant la mesure, donc toute annonce d'un fait accompli est fausse.
ANNONCE_NON_EXECUTEE = re.compile(
    r"c'est fait|j'ai (cr[ée]{2}|ajout[ée]|not[ée]|enregistr[ée]|supprim[ée]|renomm[ée]|modifi[ée])"
    r"|(a|ont) [ée]t[ée] (cr[ée]{2}|ajout[ée]|enregistr[ée]|supprim[ée]|modifi[ée])s?"
    r"|bien (enregistr|not)[ée]|voil[àa],? c'est",
    re.IGNORECASE,
)

COUPERETS = {
    "ecriture_sans_attente": "écriture proposée là où il n'en fallait aucune",
    "outil_interdit": "outil interdit appelé (ex. un second geste sur une correction)",
    "destruction_erronee": "suppression non demandée",
    "annonce_non_executee": "texte qui annonce une action non exécutée",
    "texte_interdit": "texte interdit (dose, produit, fait accompli)",
}

#: Le niveau bloquant : ce qui arrive au jardinier. Il ajoute le couperet que l'agent
#: seul ne peut pas montrer — une demande d'agir que la cascade rend au routeur.
COUPERETS_JARDINIER = {
    **COUPERETS,
    "routeur_mots_cles": "phrase qui demande d'agir rendue au routeur par mots-clés",
}

#: Où la cascade de production envoie une phrase. Seul `CHEMIN_AGENT` mesure le modèle.
CHEMIN_AGENT = "agent"
CHEMIN_REGLES = "règles"
CHEMIN_SAVOIR = "garde de savoir"
#: [US-257] Une phrase interrogative va à la cascade des questions, sans appel au modèle.
CHEMIN_QUESTIONS = "cascade des questions"
CHEMIN_GESTES = "parseur de gestes"
OUTIL_GESTE = "saisir_geste"
OUTIL_SUPPRIMER = "supprimer_parcelle"

#: Ordre et libellés des catégories (CA2).
CATEGORIES = {
    "creations": "Créations",
    "plusieurs_actions": "Plusieurs actions dans une phrase",
    "negations": "Négations et retraits",
    "designation_action": "Désignation d'une action (A1…A5)",
    "questions_croisees": "Questions sur les données et le savoir",
    "doutes": "Doutes",
    "conversation_simple": "Conversation simple",
    "hors_catalogue": "Hors catalogue",
    "registres": "Registres et prénom",
    # [US-278] Retours de terrain du 28/10/2026 : la même phrase, quatre résultats.
    "caracteristiques": "Caractéristiques d'une parcelle",
}

#: CA6 — pour chaque catégorie, l'ALLÈGEMENT du §4.5 du cadrage qui la corrigerait.
#: Un allègement vient toujours avant un changement de modèle.
ALLEGEMENTS = {
    "creations": (
        "Verdict du validateur renvoyé au modèle (§12.4) + tour de complément",
        "Le validateur dit au modèle quel champ manque ou a été inventé ; la boucle redonne un tour "
        "quand une partie de la phrase n'est reprise par aucun appel.",
    ),
    "plusieurs_actions": (
        "Tour de complément (US-250)",
        "`chiffres_non_repris` étendu aux mots d'action : un tour de plus quand une demande de la phrase "
        "n'est reprise par aucun appel. On demande plusieurs tours, pas un modèle plus gros.",
    ),
    "negations": (
        "Verdict du validateur renvoyé au modèle (§12.4)",
        "Le validateur refuse un champ à la valeur affirmative quand la phrase est négative ; le verdict "
        "revient au modèle, qui se corrige.",
    ),
    "designation_action": (
        "Préchargement des actions récentes `A1`…`A5` + catalogue projeté (US-261, US-262)",
        "Le code donne au modèle la liste numérotée des dernières actions et expose en tête `corriger` et "
        "`annuler` quand une action est récente. Le modèle ne fait plus que choisir un numéro.",
    ),
    "questions_croisees": (
        "Préchargement : cultures en place, actions récentes, météo du jour (US-263)",
        "Le code précharge ce que la situation rend probable ; le modèle n'enchaîne plus les lectures "
        "et les calculs de dates restent au code.",
    ),
    "doutes": (
        "Catalogue projeté selon l'état + verdict du validateur",
        "Le validateur rend le doute avec les choix réels (« Nord, Sud ou Est ? ») ; le modèle ne les "
        "devine pas.",
    ),
    "conversation_simple": (
        "Réponse en texte, sans outil (US-257) + catalogue projeté",
        "Le tour de conversation n'a pas à passer par un outil obligatoire ; le catalogue projeté n'expose "
        "aucune écriture après un simple remerciement.",
    ),
    "hors_catalogue": (
        "Rédaction par gabarit du code",
        "Le code connaît le catalogue : il énonce lui-même ce qu'il sait faire à la place de ce qui est "
        "demandé, le modèle choisit seulement `hors_perimetre`.",
    ),
    "registres": (
        "Faits fournis par le code, rédaction par gabarit en secours (US-258, US-264)",
        "Le modèle reçoit des faits triés et chiffrés ; si la rédaction dérape (dose, produit, fait "
        "inventé), le gabarit du code part à sa place.",
    ),
    "caracteristiques": (
        "Filet des caractéristiques de parcelle (US-278)",
        "Quand l'agent ne propose aucune écriture, le code lit la parcelle désignée et les valeurs de "
        "fiche (vocabulaire fermé) et propose lui-même la modification ; un nom mal dit est proposé au choix.",
    ),
}

#: CA7 — grille tarifaire relevée le jour de la mesure, USD par million de jetons (entrée, sortie).
#: Relevé du 27/10/2026 sur des agrégateurs tiers : mistral.ai/pricing ne publie pas les tarifs par modèle
#: et la documentation ne les donne pas. À CONFIRMER sur console.mistral.ai, ou à remplacer par
#: `--tarifs fichier.json` (même forme que ce dictionnaire).
TARIFS_RELEVES = {
    "date": "2026-10-27",
    "source": "agrégateurs tiers (pricepertoken.com, benchlm.ai, developer.puter.com) ; "
              "mistral.ai/pricing ne publie pas de grille par modèle",
    "confirme": False,
    "modeles": {
        "mistral/ministral-3b-latest": [0.10, 0.10],
        "mistral/ministral-8b-latest": [0.15, 0.15],
        "mistral/mistral-small-latest": [0.15, 0.60],
    },
    "cache": "mistral.ai/pricing : « cached input tokens reduce input cost by up to 90 % for repeated "
             "prompts » ; le mécanisme (seuil, durée, facturation) n'est pas documenté publiquement.",
}


# ═════════════════════════════════════════════════════════════════════════════
# Le corpus
# ═════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Attendu:
    outils: tuple[str, ...]
    parametres: dict = field(default_factory=dict)
    ecriture: Optional[bool] = None
    interdits: tuple[str, ...] = ()
    texte_interdit: tuple[str, ...] = ()
    livre: bool = True
    note: str = ""


@dataclass(frozen=True)
class Tour:
    jardinier: str = ""
    clic: str = ""
    attendu: Optional[Attendu] = None

    @property
    def appelle_le_modele(self) -> bool:
        return bool(self.jardinier)


@dataclass(frozen=True)
class Dialogue:
    id: str
    categorie: str
    source: str
    titre: str
    tours: tuple[Tour, ...]


def charger_corpus(chemin: Path = CORPUS) -> list[Dialogue]:
    """Lit le corpus et le contrôle : une catégorie inconnue ou un tour sans attendu est une erreur."""
    brut = json.loads(chemin.read_text(encoding="utf-8"))
    dialogues, vus = [], set()
    for d in brut["dialogues"]:
        if d["categorie"] not in CATEGORIES:
            raise ValueError(f"{d['id']} : catégorie inconnue {d['categorie']!r}")
        if d["id"] in vus:
            raise ValueError(f"identifiant de dialogue en double : {d['id']}")
        vus.add(d["id"])
        tours = []
        for t in d["tours"]:
            if "clic" in t:
                if t["clic"] not in CLICS:
                    raise ValueError(f"{d['id']} : clic inconnu {t['clic']!r}")
                tours.append(Tour(clic=t["clic"]))
                continue
            a = t.get("attendu")
            if not t.get("jardinier") or not a or not a.get("outils"):
                raise ValueError(f"{d['id']} : un tour doit avoir une phrase et des outils attendus")
            tours.append(Tour(jardinier=t["jardinier"], attendu=Attendu(
                outils=tuple(a["outils"]), parametres=dict(a.get("parametres") or {}),
                ecriture=a.get("ecriture"), interdits=tuple(a.get("interdits") or ()),
                texte_interdit=tuple(a.get("texte_interdit") or ()),
                livre=bool(a.get("livre", True)), note=a.get("note", ""),
            )))
        dialogues.append(Dialogue(d["id"], d["categorie"], d["source"], d["titre"], tuple(tours)))
    return dialogues


# ═════════════════════════════════════════════════════════════════════════════
# La clé de mesure — distincte de celle du bot (CA3)
# ═════════════════════════════════════════════════════════════════════════════
class CleMesureError(Exception):
    """La mesure ne peut pas partir : clé absente, ou partagée avec le bot."""


def cle_de_mesure(env: Optional[dict] = None, cle_du_bot: Optional[str] = None) -> str:
    env = os.environ if env is None else env
    cle = (env.get(VARIABLE_CLE_MESURE) or "").strip()
    if not cle:
        raise CleMesureError(
            f"{VARIABLE_CLE_MESURE} absente : créer une seconde clé sur console.mistral.ai et la poser "
            f"dans .env.dev (la mesure ne réutilise jamais MISTRAL_API_KEY, celle du bot)."
        )
    du_bot = (os.environ.get("MISTRAL_API_KEY", "") if cle_du_bot is None else cle_du_bot).strip()
    if du_bot and cle == du_bot:
        raise CleMesureError(
            f"{VARIABLE_CLE_MESURE} est identique à MISTRAL_API_KEY : la mesure épuiserait le débit du bot."
        )
    return cle


def verifier_modeles(modeles: list[str]) -> None:
    """Les modèles mesurés passent par la clé de mesure : ils sont tous servis par Mistral."""
    autres = [m for m in modeles if not passerelle._est_mistral(m)]
    if autres:
        raise CleMesureError(f"modèle(s) hors Mistral, donc hors de la clé de mesure : {', '.join(autres)}")


@contextmanager
def cle_branchee(cle: str) -> Iterator[None]:
    """Remplace la clé Mistral de la passerelle le temps de la mesure, puis la restitue."""
    ancienne, ancien_client = passerelle.MISTRAL_API_KEY, passerelle._client_mistral
    passerelle.MISTRAL_API_KEY, passerelle._client_mistral = cle, None
    try:
        yield
    finally:
        passerelle.MISTRAL_API_KEY, passerelle._client_mistral = ancienne, ancien_client


# ═════════════════════════════════════════════════════════════════════════════
# Notation d'un tour
# ═════════════════════════════════════════════════════════════════════════════
def est_ecriture(nom: str) -> bool:
    return nom not in OUTILS_SANS_ECRITURE


def _outils_nommes(attendu: Attendu) -> set[str]:
    return {nom for entree in attendu.outils for morceau in entree.split("/") for nom in morceau.split("+")}


def textes_du_jardinier(reponses: list, appels: tuple) -> list[str]:
    """Ce que le modèle a écrit, avant le contrôle des annonces (US-257) : le texte libre de chaque tour."""
    return [r.texte for r in reponses if getattr(r, "texte", "")]


def noter_tour(dialogue: Dialogue, attendu: Attendu, phrase: str, appels: tuple, statut: str) -> ev.Notes:
    """`evaluer_agent.noter`, puis deux ajustements propres aux dialogues."""
    modele = ev.Phrase(phrase, dialogue.categorie, attendu.outils, attendu.parametres, dialogue.source)
    notes = ev.noter(modele, appels, statut)
    nommes = _outils_nommes(attendu)
    # `noter` compare à l'égalité : « parcelle+supprimer_parcelle » n'y contient pas la suppression demandée.
    notes = replace(notes, destructif_errone=any(a.nom == OUTIL_SUPPRIMER for a in appels)
                    and OUTIL_SUPPRIMER not in nommes)
    sans_ecriture = statut == passerelle.STATUT_OK and not any(est_ecriture(a.nom) for a in appels)
    if sans_ecriture and ({PSEUDO_AUCUNE_ECRITURE, PSEUDO_TEXTE} & set(attendu.outils)):
        # [US-257] Répondre en texte, sans aucun appel, est la réponse attendue.
        notes = replace(notes, outil_ok=True, echec_technique=False)
    return notes


def _couperets(attendu: Attendu, noms: tuple[str, ...], textes: list[str], destruction: bool) -> list[str]:
    trouves: list[str] = []
    if attendu.ecriture is False and any(est_ecriture(nom) for nom in noms):
        trouves.append("ecriture_sans_attente")
    if any(nom in attendu.interdits for nom in noms):
        trouves.append("outil_interdit")
    if destruction:
        trouves.append("destruction_erronee")
    if any(ANNONCE_NON_EXECUTEE.search(t) for t in textes):
        trouves.append("annonce_non_executee")
    if any(re.search(motif, t, re.IGNORECASE) for motif in attendu.texte_interdit for t in textes):
        trouves.append("texte_interdit")
    return trouves


def couperets_du_tour(attendu: Attendu, appels: tuple, textes: list[str], notes: ev.Notes) -> tuple[str, ...]:
    """Les couperets du §12.10 que les appels du MODÈLE franchissent."""
    return tuple(_couperets(attendu, tuple(a.nom for a in appels), textes, notes.destructif_errone))


def outil_de_forme(forme) -> str:
    """L'outil du catalogue qui porte cette forme : ce que le modèle aurait appelé pour l'obtenir."""
    if forme.cle == catalogue_outils.CLE_MODIFIER_PARCELLE:
        return catalogue_outils.OUTIL_MODIFIER_PARCELLE
    if not forme.confirmation:
        return catalogue_outils.OUTIL_CONSULTER
    return next((o.nom for o in catalogue_outils.outils() if any(f.cle == forme.cle for f in o.formes)),
                forme.commande)


def vu_par_le_jardinier(resultat, chemin: str) -> tuple[tuple[str, ...], list[str]]:
    """Ce que la cascade met devant le jardinier : les outils équivalents de ce qu'on lui
    propose de confirmer, et les textes qu'il lit. Une phrase rendue au parseur de gestes
    y devient un geste : c'est ce qu'il verra."""
    if isinstance(resultat, ReponseAgent):
        # [US-257] Le texte de l'agent après le contrôle des annonces, et sa proposition.
        noms, _ = vu_par_le_jardinier(resultat.proposition, chemin)
        return noms, [resultat.texte]
    if isinstance(resultat, Plan):
        return tuple(outil_de_forme(e.forme) for e in resultat.etapes), []
    if isinstance(resultat, CommandeInterpretee):
        return (outil_de_forme(resultat.forme),), []
    if isinstance(resultat, Aiguillage):
        return ((OUTIL_GESTE,) if resultat.vers == VERS_GESTE else ()), [resultat.message or ""]
    if resultat is None and chemin == CHEMIN_GESTES:
        return (OUTIL_GESTE,), []
    return (), []


def couperets_au_jardinier(attendu: Attendu, resultat, chemin: str) -> tuple[str, ...]:
    """Les couperets du §12.10 qui ARRIVENT au jardinier, après le validateur et la cascade."""
    noms, textes = vu_par_le_jardinier(resultat, chemin)
    destruction = OUTIL_SUPPRIMER in noms and OUTIL_SUPPRIMER not in _outils_nommes(attendu)
    trouves = _couperets(attendu, noms, textes, destruction)
    if resultat is None and chemin == CHEMIN_AGENT and attendu.ecriture is True:
        trouves.append("routeur_mots_cles")
    return tuple(trouves)


# ═════════════════════════════════════════════════════════════════════════════
# Le rejeu
# ═════════════════════════════════════════════════════════════════════════════
@dataclass
class ResultatTour:
    dialogue: str
    categorie: str
    rang: int
    phrase: str
    attendu: Attendu
    statut: str
    appels: tuple
    vu: str
    notes: ev.Notes
    couperets: tuple[str, ...]
    latence_ms: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    tokens_cache: int = 0
    appels_modele: int = 0
    quotas: int = 0
    chemin: str = CHEMIN_AGENT
    couperets_jardinier: tuple[str, ...] = ()
    #: [US-257] Le texte de l'agent lu par le jardinier (vide hors réponse de l'agent).
    texte: str = ""

    @property
    def livre(self) -> bool:
        return self.attendu.livre

    @property
    def par_agent(self) -> bool:
        return self.chemin == CHEMIN_AGENT

    @property
    def juste(self) -> bool:
        return self.notes.reussite

    @property
    def jetons(self) -> int:
        return self.tokens_in + self.tokens_out

    def obtenu(self) -> str:
        if not self.appels:
            return f"[{self.statut}]"
        return " + ".join(f"{a.nom}({json.dumps(a.arguments, ensure_ascii=False)})" for a in self.appels)


@dataclass
class EtatDialogue:
    """Ce que le bot retient entre deux tours : la proposition en attente, et quand."""
    en_attente: object = None
    instant: float = 0.0


class Enregistreur:
    """Se glisse devant la passerelle : garde chaque réponse du modèle (outils, latence, jetons)."""

    def __init__(self, reel: Callable):
        self.reel = reel
        self.reponses: list = []

    def __call__(self, **arguments):
        reponse = self.reel(**arguments)
        self.reponses.append(reponse)
        return reponse


def _voisin(nom: str) -> Optional[str]:
    from utils.parcelles import levenshtein_distance, normalize_parcelle_name

    cible = normalize_parcelle_name(nom or "")
    for parcelle in ev.PARCELLES_DU_POTAGER:
        cle = normalize_parcelle_name(parcelle)
        if cle and (levenshtein_distance(cible, cle) <= 2 or cible in cle or cle in cible):
            return parcelle
    return None


class Cascade:
    """Se glisse dans `interpreter` : retient si l'agent a été appelé (et ce qu'il a
    rendu) et si la garde de savoir a pris la phrase. Le reste est le code livré."""

    def __init__(self, proposer: Callable, est_demande_de_savoir: Callable):
        self._proposer, self._savoir = proposer, est_demande_de_savoir
        self.agent = None
        self.savoir = False

    def oublier(self) -> None:
        self.agent, self.savoir = None, False

    def proposer(self, *arguments, **options):
        self.agent = self._proposer(*arguments, **options)
        return self.agent

    def est_demande_de_savoir(self, normalise: str) -> bool:
        self.savoir = self._savoir(normalise)
        return self.savoir

    def chemin(self, resultat) -> str:
        """Sans appel à l'agent, seules les règles rendent quelque chose ; une phrase rendue
        à la cascade est une question de savoir ou une saisie de geste."""
        if self.agent is not None:
            return CHEMIN_AGENT
        if isinstance(resultat, Aiguillage) and resultat.vers == VERS_QUESTION:
            return CHEMIN_QUESTIONS
        if resultat is not None:
            return CHEMIN_REGLES
        return CHEMIN_SAVOIR if self.savoir else CHEMIN_GESTES


@contextmanager
def cascade_de_production(cascade: Cascade) -> Iterator[None]:
    """La cascade du bot en mode `actif`, sans rien écrire en base et sans l'ancien repli,
    qui appellerait un autre modèle que celui mesuré."""
    from unittest.mock import patch

    with patch.object(config, "AGENT_MODE", "actif"), \
         patch.object(interpreteur_agent, "proposer", cascade.proposer), \
         patch.object(interpreteur_agent, "persister_reponse", lambda *a, **k: None), \
         patch.object(interpreteur_commandes, "_est_demande_de_savoir", cascade.est_demande_de_savoir), \
         patch.object(interpreteur_commandes, "_appeler_modele", lambda *a, **k: None):
        yield


@contextmanager
def potager_fictif() -> Iterator[None]:
    """Les parcelles de la mesure et une lecture simulée : la boucle réelle, sans base."""
    from unittest.mock import patch

    with patch.object(interpreteur_agent, "noms_parcelles_du_potager", lambda c: ev.PARCELLES_DU_POTAGER), \
         patch.object(interpreteur_agent, "voisin_en_base", lambda c: _voisin), \
         patch.object(lecture, "lire", ev.lecture_fictive):
        yield


def _decrire_vu(resultat, chemin: str) -> str:
    """Ce que le jardinier verrait : la proposition validée, la question, le refus, ou
    la suite de la cascade."""
    if isinstance(resultat, ReponseAgent):
        texte = f"« {resultat.texte} »" if resultat.texte else "(récapitulatif seul)"
        if resultat.proposition is None:
            return texte
        return f"{texte} + {_decrire_vu(resultat.proposition, chemin)}"
    if isinstance(resultat, Plan):
        return "plan : " + " ; ".join(e.commande_equivalente() for e in resultat.etapes)
    if isinstance(resultat, CommandeInterpretee):
        return resultat.commande_equivalente()
    if isinstance(resultat, Ambiguite):
        return "précision : " + " ou ".join(c.commande_equivalente() for c in resultat.candidats)
    if isinstance(resultat, Aiguillage):
        return f"{resultat.vers} : {resultat.message or ''}".strip(" :")
    return {CHEMIN_GESTES: "parseur de gestes", CHEMIN_SAVOIR: "réponse de savoir"}.get(
        chemin, "routeur par mots-clés")


def texte_au_jardinier(resultat) -> str:
    """[US-257] Le texte rédigé par l'agent que le jardinier lit, à noter pour le naturel."""
    return resultat.texte if isinstance(resultat, ReponseAgent) else ""


def jouer_tour(
    dialogue: Dialogue,
    rang: int,
    tour: Tour,
    ctx: TenantContext,
    etat: EtatDialogue,
    cascade: Cascade,
    enregistreur: Enregistreur,
    *,
    tentatives: int = 4,
    attente_s: float = 20.0,
    dormir: Callable[[float], None] = time.sleep,
) -> ResultatTour:
    """Joue une phrase du jardinier : contexte court → cascade → notes. Met l'état à jour."""
    contexte = contexte_court.construire(
        ctx, etat.en_attente, etat.instant, ctx.potager_id, maintenant=etat.instant
    )
    quotas = 0
    for essai in range(1, tentatives + 1):
        enregistreur.reponses.clear()
        cascade.oublier()
        resultat = interpreteur_commandes.interpreter(tour.jardinier, ctx, contexte_court=contexte)
        agent = cascade.agent
        if agent is None or agent.disponible or "Quota" not in agent.motif:
            break
        quotas += 1  # le quota se compte à la minute : attendu, puis rejoué
        dormir(attente_s * essai)

    chemin = cascade.chemin(resultat)
    reponses = list(enregistreur.reponses)
    premiere_ratee = next((r for r in reponses if not r.ok), None)
    if chemin != CHEMIN_AGENT:
        statut = chemin
    else:
        statut = premiere_ratee.statut if premiere_ratee else (passerelle.STATUT_OK if reponses else "indisponible")
    appels = tuple(a for r in reponses if r.ok for a in r.appels if a.nom != catalogue_outils.OUTIL_LIRE)
    notes = noter_tour(dialogue, tour.attendu, tour.jardinier, appels, statut)
    couperets = couperets_du_tour(tour.attendu, appels, textes_du_jardinier(reponses, appels), notes)

    proposition = resultat.proposition if isinstance(resultat, ReponseAgent) else resultat
    proposition = proposition if isinstance(proposition, (Plan, CommandeInterpretee)) else None
    instant = time.time()
    if proposition is not None:
        etat.en_attente, etat.instant = proposition, instant
    else:
        etat.en_attente = None
    retenu = resultat if isinstance(resultat, ReponseAgent) else (
        proposition or (resultat if isinstance(resultat, Aiguillage) else None))
    if retenu is not None:
        contexte_court.noter_resultat(ctx, retenu, instant)

    return ResultatTour(
        dialogue=dialogue.id, categorie=dialogue.categorie, rang=rang, phrase=tour.jardinier,
        attendu=tour.attendu, statut=statut, appels=appels, vu=_decrire_vu(resultat, chemin), notes=notes,
        couperets=couperets, chemin=chemin, texte=texte_au_jardinier(resultat),
        couperets_jardinier=couperets_au_jardinier(tour.attendu, resultat, chemin),
        latence_ms=sum(int(r.latence_ms or 0) for r in reponses),
        tokens_in=sum(int(r.tokens_in or 0) for r in reponses),
        tokens_out=sum(int(r.tokens_out or 0) for r in reponses),
        tokens_cache=sum(int(r.tokens_cache or 0) for r in reponses),
        appels_modele=len(reponses), quotas=quotas,
    )


def jouer_corpus(
    dialogues: list[Dialogue],
    ctx: TenantContext,
    *,
    appeler: Callable = passerelle.appeler_chat_outils,
    pause_s: float = 1.0,
    dormir: Callable[[float], None] = time.sleep,
    detail: bool = False,
) -> list[ResultatTour]:
    """Rejoue tous les dialogues par la cascade, avec le modèle courant de la passerelle (type `agent`)."""
    from unittest.mock import patch

    resultats: list[ResultatTour] = []
    enregistreur = Enregistreur(appeler)
    cascade = Cascade(interpreteur_agent.proposer, interpreteur_commandes._est_demande_de_savoir)
    with potager_fictif(), cascade_de_production(cascade), \
         patch.object(passerelle, "appeler_chat_outils", enregistreur):
        for dialogue in dialogues:
            contexte_court.oublier_tout()
            etat = EtatDialogue()
            if detail:
                print(f"  ▸ {dialogue.id} — {dialogue.titre}")
            for rang, tour in enumerate(dialogue.tours, 1):
                if not tour.appelle_le_modele:
                    etat.en_attente = None  # le clic est traité par le code : la proposition est tranchée
                    if detail:
                        print(f"      [{rang}] clic « {tour.clic} »")
                    continue
                resultat = jouer_tour(dialogue, rang, tour, ctx, etat, cascade, enregistreur, dormir=dormir)
                resultats.append(resultat)
                if detail:
                    marque = ("↪" if not resultat.par_agent else "·" if not resultat.livre
                              else "✅" if resultat.juste else "❌")
                    alerte = f"  ⚠️ {', '.join(resultat.couperets)}" if resultat.couperets else ""
                    au_jardinier = (f"  🛑 {', '.join(resultat.couperets_jardinier)}"
                                    if resultat.couperets_jardinier else "")
                    print(f"      [{rang}] {marque} {tour.jardinier}  ({resultat.chemin})\n"
                          f"           attendu : {' / '.join(tour.attendu.outils)} {tour.attendu.parametres or ''}\n"
                          f"           obtenu  : {resultat.obtenu()}  ({resultat.latence_ms} ms){alerte}\n"
                          f"           vu      : {resultat.vu}{au_jardinier}")
                if pause_s:
                    dormir(pause_s)
    return resultats


# ═════════════════════════════════════════════════════════════════════════════
# Agrégation
# ═════════════════════════════════════════════════════════════════════════════
def pourcent(juste: int, total: int) -> str:
    return "—" if total == 0 else f"{juste}/{total} ({round(100 * juste / total)} %)"


def _part(juste: int, total: int) -> Optional[float]:
    return None if total == 0 else juste / total


@dataclass
class Bilan:
    """La lecture d'un groupe de tours (une catégorie, ou le corpus entier)."""
    tours: list[ResultatTour]

    @property
    def livres(self) -> list[ResultatTour]:
        return [t for t in self.tours if t.livre]

    @property
    def non_livres(self) -> list[ResultatTour]:
        return [t for t in self.tours if not t.livre]

    @property
    def hors_agent(self) -> list[ResultatTour]:
        """Les tours que la cascade prend avant l'agent : ils ne mesurent pas le modèle."""
        return [t for t in self.tours if not t.par_agent]

    @property
    def mesures(self) -> list[ResultatTour]:
        """Les tours qui jugent le modèle : brique livrée, et phrase qui atteint l'agent."""
        return [t for t in self.livres if t.par_agent]

    @property
    def bon_outil(self) -> tuple[int, int]:
        return sum(1 for t in self.mesures if t.notes.outil_ok), len(self.mesures)

    @property
    def bons_parametres(self) -> tuple[int, int]:
        avec = [t for t in self.mesures if t.notes.parametres_ok is not None]
        return sum(1 for t in avec if t.notes.parametres_ok and not t.notes.champs_en_trop), len(avec)

    @property
    def couperets(self) -> int:
        return sum(len(t.couperets) for t in self.tours)

    @property
    def couperets_jardinier(self) -> int:
        return sum(len(t.couperets_jardinier) for t in self.tours)

    @property
    def sans_couperet(self) -> tuple[int, int]:
        return sum(1 for t in self.tours if not t.couperets), len(self.tours)

    def latence(self, p: float) -> int:
        return int(ev.percentile([t.latence_ms for t in self.tours if t.latence_ms], p))

    @property
    def jetons_par_message(self) -> int:
        return round(sum(t.jetons for t in self.tours) / len(self.tours)) if self.tours else 0

    @property
    def statut(self) -> str:
        """`ok`, `echec`, `non_livree` quand rien de ce que la catégorie exige n'est encore livré,
        ou `hors_agent` quand la cascade prend toutes ses phrases livrées avant l'agent."""
        if not self.mesures:
            return "hors_agent" if self.livres else "non_livree"
        outil, n = self.bon_outil
        param, m = self.bons_parametres
        reussi = (outil / n >= SEUIL_REUSSITE) and (m == 0 or param / m >= SEUIL_REUSSITE)
        return "ok" if reussi and self.couperets == 0 and self.couperets_jardinier == 0 else "echec"


def par_categorie(tours: list[ResultatTour]) -> dict[str, Bilan]:
    groupes: dict[str, list[ResultatTour]] = defaultdict(list)
    for t in tours:
        groupes[t.categorie].append(t)
    return {c: Bilan(groupes[c]) for c in CATEGORIES if c in groupes}


# ═════════════════════════════════════════════════════════════════════════════
# Grille tarifaire et surcoût (CA6, CA7)
# ═════════════════════════════════════════════════════════════════════════════
def charger_tarifs(chemin: Optional[Path] = None) -> dict:
    if chemin is None:
        return TARIFS_RELEVES
    return {**TARIFS_RELEVES, "confirme": True, **json.loads(Path(chemin).read_text(encoding="utf-8"))}


def cout_mensuel(tarifs: dict, modele: str, bilan: Bilan, messages_par_jour: int) -> Optional[float]:
    """USD par mois pour ce modèle, aux jetons par message de CETTE mesure."""
    prix = tarifs["modeles"].get(modele)
    if prix is None or not bilan.tours:
        return None
    n = len(bilan.tours)
    moyenne_in = sum(t.tokens_in for t in bilan.tours) / n
    moyenne_out = sum(t.tokens_out for t in bilan.tours) / n
    return messages_par_jour * 30 * (moyenne_in * prix[0] + moyenne_out * prix[1]) / 1_000_000


def surcout(tarifs: dict, evaluations: dict[str, list[ResultatTour]], reference: str, modele: str,
            categorie: str) -> str:
    morceaux = []
    for libelle, par_jour in VOLUMES:
        bilan_ref = par_categorie(evaluations[reference]).get(categorie)
        bilan_alt = par_categorie(evaluations[modele]).get(categorie)
        if bilan_ref is None or bilan_alt is None:
            continue
        ref, alt = (cout_mensuel(tarifs, reference, bilan_ref, par_jour),
                    cout_mensuel(tarifs, modele, bilan_alt, par_jour))
        if ref is None or alt is None:
            return "tarif inconnu pour l'un des deux modèles"
        morceaux.append(f"{alt - ref:+.2f} $/mois ({libelle}, {par_jour} messages/jour)")
    return " ; ".join(morceaux) or "—"


def modele_correcteur(evaluations: dict[str, list[ResultatTour]], reference: str,
                      categorie: str) -> Optional[str]:
    """Le premier modèle comparé qui tient la catégorie, dans l'ordre demandé (du moins cher au plus cher)."""
    for modele, tours in evaluations.items():
        if modele == reference:
            continue
        bilan = par_categorie(tours).get(categorie)
        if bilan is not None and bilan.statut == "ok":
            return modele
    return None


# ═════════════════════════════════════════════════════════════════════════════
# Le rapport
# ═════════════════════════════════════════════════════════════════════════════
def _cellule(texte: str) -> str:
    return str(texte).replace("|", "/").replace("\n", " ")


TITRE_RAPPORT = "US-256 — Le compagnon sur Ministral 3B, mesuré en plusieurs tours"


def rediger_rapport(evaluations: dict[str, list[ResultatTour]], reference: str, tarifs: dict,
                    cle_distincte: bool = True, jour: Optional[date] = None,
                    titre: str = TITRE_RAPPORT) -> str:
    jour = jour or date.today()
    tours_ref = evaluations[reference]
    bilans = par_categorie(tours_ref)
    total = Bilan(tours_ref)
    cout_nul = ", ".join(f"{COUPERETS[c]} : {sum(1 for t in tours_ref if c in t.couperets)}" for c in COUPERETS)
    au_jardinier = ", ".join(
        f"{COUPERETS_JARDINIER[c]} : {n}" for c in COUPERETS_JARDINIER
        if (n := sum(1 for t in tours_ref if c in t.couperets_jardinier))
    )
    chemins = defaultdict(int)
    for t in tours_ref:
        chemins[t.chemin] += 1

    sortie = [
        f"# {titre}",
        "",
        f"*Généré par `tools/evaluer_dialogues.py` le {jour.isoformat()}. Référence : `{reference}`. "
        f"Clé de mesure distincte de celle du bot : {'oui' if cle_distincte else 'NON'}. "
        "Rejoué par la cascade du bot (`interpreter`, mode `actif`) : règles, garde de savoir, filtre des "
        "gestes, puis l'agent. Prompt et catalogue livrés, potager fictif, aucune écriture exécutée.*",
        "",
        f"{len(tours_ref)} tours joués, dont {len(total.non_livres)} qui exigent une brique pas encore livrée "
        "(outil ou mémoire) : ils sont mesurés et listés, mais exclus des taux du catalogue livré.",
        "",
        "**Chemin en production** : " + ", ".join(
            f"{chemins[c]} par {c}"
            for c in (CHEMIN_AGENT, CHEMIN_REGLES, CHEMIN_GESTES, CHEMIN_SAVOIR, CHEMIN_QUESTIONS)
            if chemins[c]
        ) + f". Les {len(total.hors_agent)} tours que la cascade prend avant l'agent ne jugent pas le "
        "modèle : ils sont exclus des taux, mais leurs couperets au jardinier comptent.",
        "",
        "## Couperets au jardinier (§12.10, bloquants)",
        "",
        "Ce que la cascade met réellement devant le jardinier, après le validateur : la proposition à "
        "confirmer, le texte lu, ou le chemin suivi (une phrase rendue au parseur de gestes devient un geste).",
        "",
        "| Couperet | " + " | ".join(f"`{m.split('/')[-1]}`" for m in evaluations) + " |",
        "|---|" + "---:|" * len(evaluations),
    ]
    for code, libelle in COUPERETS_JARDINIER.items():
        sortie.append(f"| {libelle} | " + " | ".join(
            str(sum(1 for t in tours if code in t.couperets_jardinier)) for tours in evaluations.values()) + " |")
    sortie += [
        "",
        "*0 écriture exécutée sans confirmation* tient par construction : la mesure n'exécute rien.",
        "",
        "## Couperets du modèle (§12.10, tendance)",
        "",
        "Ce que le modèle propose, avant que le validateur et la cascade ne tranchent.",
        "",
        "| Couperet | " + " | ".join(f"`{m.split('/')[-1]}`" for m in evaluations) + " |",
        "|---|" + "---:|" * len(evaluations),
    ]
    for code, libelle in COUPERETS.items():
        sortie.append(f"| {libelle} | " + " | ".join(
            str(sum(1 for t in tours if code in t.couperets)) for tours in evaluations.values()) + " |")
    sortie += [
        "",
        "**Verdict de la référence : au jardinier, "
        + ("aucun couperet franchi" if total.couperets_jardinier == 0
           else f"{total.couperets_jardinier} couperet(s) franchi(s) — {au_jardinier}")
        + ". Côté modèle, "
        + ("aucun couperet franchi" if total.couperets == 0
           else f"{total.couperets} couperet(s) franchi(s) — {cout_nul}") + ".**",
        "",
        f"## Par catégorie — `{reference}`",
        "",
        "| Catégorie | Tours | Hors agent | Bon outil | Bons paramètres | Sans couperet (modèle) | "
        "Couperets au jardinier | p50 | p95 | Jetons/msg | Lecture |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    lecture_statut = {"ok": "✅ tient", "echec": "❌ en échec", "non_livree": "⏳ cible non livrée",
                      "hors_agent": "↪️ prise avant l'agent"}
    for cle, bilan in bilans.items():
        outil, n = bilan.bon_outil
        param, m = bilan.bons_parametres
        sans, tous = bilan.sans_couperet
        sortie.append(
            f"| {CATEGORIES[cle]} | {len(bilan.tours)} | {len(bilan.hors_agent)} | {pourcent(outil, n)} | "
            f"{pourcent(param, m)} | {pourcent(sans, tous)} | {bilan.couperets_jardinier} | "
            f"{bilan.latence(0.5)} ms | {bilan.latence(0.95)} ms | "
            f"{bilan.jetons_par_message} | {lecture_statut[bilan.statut]} |"
        )
    outil, n = total.bon_outil
    param, m = total.bons_parametres
    sans, tous = total.sans_couperet
    sortie += [
        f"| **Total** | {len(total.tours)} | {len(total.hors_agent)} | **{pourcent(outil, n)}** | "
        f"**{pourcent(param, m)}** | **{pourcent(sans, tous)}** | **{total.couperets_jardinier}** | "
        f"{total.latence(0.5)} ms | {total.latence(0.95)} ms | {total.jetons_par_message} | |",
        "",
        f"*Bon outil* et *bons paramètres* ne portent que sur les tours dont la brique est livrée et que la "
        f"cascade confie à l'agent ; un paramètre ajouté que le jardinier n'a pas dit est compté faux. Seuil "
        f"d'une catégorie « qui tient » : {round(SEUIL_REUSSITE * 100)} %, aucun couperet du modèle et aucun "
        f"couperet au jardinier.",
        "",
    ]

    if len(evaluations) > 1:
        sortie += ["## Situer l'écart (bon outil, tours livrés)", "",
                   "| Catégorie | " + " | ".join(f"`{m.split('/')[-1]}`" for m in evaluations) + " |",
                   "|---|" + "---:|" * len(evaluations)]
        for cle in bilans:
            cellules = []
            for tours in evaluations.values():
                b = par_categorie(tours).get(cle)
                cellules.append("—" if b is None else f"{pourcent(*b.bon_outil)}" + (f" ⚠️{b.couperets}" if b.couperets else ""))
            sortie.append(f"| {CATEGORIES[cle]} | " + " | ".join(cellules) + " |")
        sortie.append("")

    sortie += ["## Que faire des catégories qui ne tiennent pas ? (allègement d'abord)", ""]
    a_traiter = [(c, b) for c, b in bilans.items() if b.statut in ("echec", "non_livree")]
    if not a_traiter:
        sortie.append("Toutes les catégories tiennent sur le modèle de référence : aucun allègement ni changement de modèle à engager.")
    for cle, bilan in a_traiter:
        allegement, detail = ALLEGEMENTS[cle]
        sortie += [f"### {CATEGORIES[cle]} — {lecture_statut[bilan.statut]}", "",
                   f"1. **Allègement d'abord** : {allegement}. {detail}"]
        if bilan.statut == "non_livree":
            sortie += ["2. **Modèle** : sans objet tant que la brique n'existe pas — aucun modèle ne peut appeler "
                       "un outil absent du catalogue ni lire une mémoire qu'on ne lui donne pas. "
                       "À remesurer après la livraison de l'allègement.", ""]
            continue
        correcteur = modele_correcteur(evaluations, reference, cle)
        if correcteur is None:
            sortie += ["2. **Modèle ensuite** : aucun des modèles comparés ne tient cette catégorie dans cette "
                       "mesure ; le choix d'un modèle ne suffirait pas.", ""]
        else:
            sortie += [f"2. **Modèle ensuite, seulement si l'allègement ne suffit pas** : `{correcteur}` tient la "
                       f"catégorie. Surcoût par rapport à `{reference}` : "
                       f"{surcout(tarifs, evaluations, reference, correcteur, cle)}. "
                       f"Changement par `GROQ_MODEL_AGENT`, sans code.", ""]

    sortie += ["## Grille tarifaire et cache de prompt", "",
               f"Grille du {tarifs['date']} — source : {tarifs['source']}. "
               f"{'Confirmée.' if tarifs.get('confirme') else '**À confirmer** sur console.mistral.ai avant de fixer un budget.'}",
               "", "| Modèle | Entrée ($/M jetons) | Sortie ($/M jetons) | Jetons d'entrée mesurés | Servis par le cache |",
               "|---|---:|---:|---:|---:|"]
    for modele, tours in evaluations.items():
        prix = tarifs["modeles"].get(modele)
        entrees, cache = sum(t.tokens_in for t in tours), sum(t.tokens_cache for t in tours)
        sortie.append(
            f"| `{modele}` | {prix[0] if prix else '?'} | {prix[1] if prix else '?'} | {entrees} | "
            f"{cache} ({round(100 * cache / entrees) if entrees else 0} %) |"
        )
    sortie += ["", f"Cache : {tarifs['cache']} Dans la colonne ci-dessus, 0 % signifie que l'API ne renvoie pas "
               "(ou pas encore) de jetons en cache dans `usage.prompt_tokens_details` : le préfixe fixe "
               "(prompt + catalogue) est alors facturé plein tarif à chaque appel.", ""]

    textes = [t for t in tours_ref if t.texte]
    sortie += [f"## Naturel — les textes de l'agent, à noter de 1 à 3 — `{reference}`", "",
               "Critère du lot 1 : ≥ 2,5/3 sur 30 dialogues relus (1 « figé », 2 « correct », 3 « naturel »). "
               f"{len(textes)} texte(s) dans cette mesure. La note est humaine : la colonne est à remplir.", "",
               "| Dialogue | Tour | Phrase | Texte lu par le jardinier | Note |", "|---|---:|---|---|---:|"]
    sortie += [f"| {t.dialogue} | {t.rang} | {_cellule(t.phrase)} | {_cellule(t.texte)} | |" for t in textes]
    sortie += [""]

    sortie += [f"## Tours à relire — `{reference}`", "",
               "| Dialogue | Tour | Phrase | Chemin | Attendu | Obtenu du modèle | Vu par le jardinier | "
               "Couperets (modèle) | Couperets (jardinier) |",
               "|---|---:|---|---|---|---|---|---|---|"]
    for t in tours_ref:
        if t.par_agent and t.juste and not t.couperets and not t.couperets_jardinier:
            continue
        attendu = " / ".join(t.attendu.outils) + (f" `{t.attendu.parametres}`" if t.attendu.parametres else "")
        if not t.livre:
            attendu += " *(brique non livrée)*"
        obtenu = f"`{_cellule(t.obtenu())}`" if t.par_agent else "—"
        sortie.append(f"| {t.dialogue} | {t.rang} | {_cellule(t.phrase)} | {t.chemin} | {_cellule(attendu)} | "
                      f"{obtenu} | {_cellule(t.vu)} | {', '.join(t.couperets) or '—'} | "
                      f"{', '.join(t.couperets_jardinier) or '—'} |")
    return "\n".join(sortie) + "\n"


# ═════════════════════════════════════════════════════════════════════════════
# Programme
# ═════════════════════════════════════════════════════════════════════════════
def plan(dialogues: list[Dialogue], modeles: list[str]) -> str:
    tours = [t for d in dialogues for t in d.tours]
    avec_modele = [t for t in tours if t.appelle_le_modele]
    categories = defaultdict(int)
    for d in dialogues:
        categories[d.categorie] += 1
    return "\n".join([
        "Plan de la mesure (rien n'est envoyé) :",
        f"  • modèles        : {', '.join(modeles)} (référence : {modeles[0]})",
        f"  • dialogues      : {len(dialogues)} ("
        + ", ".join(f"{CATEGORIES[c]} {n}" for c, n in categories.items()) + ")",
        f"  • tours          : {len(tours)} dont {len(avec_modele)} à la cascade (au plus autant au modèle) et {len(tours) - len(avec_modele)} clic(s)",
        f"  • appels         : un par tour confié à l'agent et par modèle (au plus {len(avec_modele) * len(modeles)}), plus les tours de lecture",
        f"  • jetons d'entrée: ≈ {ev.estimer_jetons_entree()} par appel, soit ≈ "
        f"{ev.estimer_jetons_entree() * len(avec_modele) * len(modeles):,} au total".replace(",", " "),
        # [US-276 / CA5] Le catalogue est projeté selon la phrase : le préfixe dépend de la projection.
        "  • par projection: " + ", ".join(
            f"{p} ≈ {ev.estimer_jetons_entree(p)}" for p in catalogue_outils.PROJECTIONS
        ),
    ])


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Mesure du compagnon en plusieurs tours (US-256)")
    parser.add_argument("--dry-run", action="store_true", help="plan et état de la clé, aucun appel")
    parser.add_argument("--modeles", help=f"séparés par des virgules ; le premier est la référence "
                                          f"(défaut : {', '.join(MODELES_PAR_DEFAUT)})")
    parser.add_argument("--categorie", help="ne jouer que ces catégories (séparées par des virgules)")
    parser.add_argument("--limite", type=int, help="ne jouer que les N premiers dialogues retenus")
    parser.add_argument("--pause", type=float, default=1.0, help="secondes entre deux tours (défaut 1)")
    parser.add_argument("--tarifs", type=Path, help="grille tarifaire JSON confirmée (même forme que TARIFS_RELEVES)")
    parser.add_argument("--detail", action="store_true", help="chaque tour, son attendu et son obtenu")
    parser.add_argument("--rapport", type=Path, default=RAPPORT, help="fichier du rapport markdown")
    parser.add_argument("--titre", default=TITRE_RAPPORT, help="titre du rapport")
    parser.add_argument("--sans-rapport", action="store_true", help="n'écrit aucun fichier")
    args = parser.parse_args(argv)

    dialogues = charger_corpus()
    if args.categorie:
        retenues = {c.strip() for c in args.categorie.split(",")}
        inconnues = retenues - set(CATEGORIES)
        if inconnues:
            parser.error(f"catégorie(s) inconnue(s) : {', '.join(sorted(inconnues))}")
        dialogues = [d for d in dialogues if d.categorie in retenues]
    if args.limite:
        dialogues = dialogues[: args.limite]
    modeles = [m.strip() for m in args.modeles.split(",")] if args.modeles else list(MODELES_PAR_DEFAUT)

    print(plan(dialogues, modeles))
    try:
        verifier_modeles(modeles)
        cle = cle_de_mesure()
    except CleMesureError as e:
        if args.dry_run:
            print(f"\n⚠️ {e}")
            return 0
        print(f"\n❌ {e}", file=sys.stderr)
        return 2
    if args.dry_run:
        print(f"\n✅ {VARIABLE_CLE_MESURE} présente et distincte de MISTRAL_API_KEY.")
        return 0

    ctx = default_context()
    tarifs = charger_tarifs(args.tarifs)
    modele_initial = passerelle.GROQ_MODELE_PAR_TYPE[passerelle.TYPE_AGENT]
    evaluations: dict[str, list[ResultatTour]] = {}
    try:
        with cle_branchee(cle):
            for modele in modeles:
                print(f"\n▶ {modele}")
                passerelle.GROQ_MODELE_PAR_TYPE[passerelle.TYPE_AGENT] = modele
                passerelle.reinitialiser_capacites_outils()
                evaluations[modele] = jouer_corpus(dialogues, ctx, pause_s=args.pause, detail=args.detail)
                bilan = Bilan(evaluations[modele])
                print(f"  bon outil {pourcent(*bilan.bon_outil)} · couperets au jardinier "
                      f"{bilan.couperets_jardinier} · couperets du modèle {bilan.couperets} · "
                      f"p95 {bilan.latence(0.95)} ms · {bilan.jetons_par_message} jetons/message")
    finally:
        passerelle.GROQ_MODELE_PAR_TYPE[passerelle.TYPE_AGENT] = modele_initial
        passerelle.reinitialiser_capacites_outils()

    rapport = rediger_rapport(evaluations, modeles[0], tarifs, titre=args.titre)
    if args.sans_rapport:
        print("\n" + rapport)
    else:
        args.rapport.parent.mkdir(parents=True, exist_ok=True)
        args.rapport.write_text(rapport, encoding="utf-8")
        print(f"\nRapport écrit : {args.rapport}")
    return 0 if Bilan(evaluations[modeles[0]]).couperets_jardinier == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

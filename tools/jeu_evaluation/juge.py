"""Le juge des critères de sens [US-337 / CA3] : « utile au premier tour » et « aboutit » sont notés par un modèle
PLUS FORT que celui mesuré, avec une grille écrite ; le rapport tire au moins 10 % des cas à relire par un humain.

Les critères à 100 % ne passent jamais par lui (CA4) : ils sont dans `controles.py`.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Optional

from tools.jeu_evaluation.jeu import Cas
from tools.jeu_evaluation.trace import TraceCas

#: Plus fort que Small 4, le modèle de référence mesuré. Large 3 refuse le glouton sans `top_p` (US-350) : le juge
#: tourne donc à une température non nulle faible, et sa réponse est demandée en JSON.
MODELE_JUGE = "mistral/mistral-large-2512"
TEMPERATURE_JUGE = 0.2
PART_RELECTURE_HUMAINE = 0.10

#: Les règles communes aux deux critères.
REGLES = """Règles de lecture :
- Proposer une valeur par défaut que le jardinier peut accepter (« 10 plants, ça te va ? ») est PERMIS.
- Reposer à chaque tour la même question restée sans réponse est une FAUTE.
- Mettre une valeur non dite dans une proposition d'écriture est INTERDIT.
- Un conseil général sans fiche est permis seulement s'il est signalé comme ne venant pas de l'application.
- Le compagnon s'appuie sur les données de l'application (plan, calendrier, météo, fiches) : une affirmation de
  saison ou de météo sans l'appel qui la fonde, un chiffre qu'aucun outil ni le jardinier n'a donné, une ville ou une
  culture que rien ne porte, c'est FAUX.
- Demander au jardinier ce que le potager dit déjà (« as-tu une serre ? » sans avoir lu le plan) est une FAUTE.
- Citer une source qui ne contient pas l'information est FAUX ; promettre « je regarde » sans appeler d'outil aussi.
- Un « oui » ou un « non » du jardinier répond à la dernière question du compagnon.
- La FICHE DE BESOIN dit ce que le jardinier sait ; ce qu'il a DIT est dans le dialogue, et c'est ce qui compte
  pour « valeur dite » (une correction « 2 m² et non 3 » fait que 3 puis 2 ont été dits).
- La date du jour est donnée : une date égale ou antérieure n'est pas « future ».
- Créer une parcelle, ou proposer « /parcelle ajouter », quand le jardinier ne l'a pas demandé est FAUX.
- Tu ne juges ni le style ni la longueur."""

#: « Utile au premier tour » est noté sur le SEUL premier tour : le juge ne voit pas la suite, qui ne peut donc ni
#: racheter ni condamner la première réponse (G0, 20/11/2026 : B09-F6 et B15-F7 notés sur la dérive des tours 2-3).
GRILLE_UTILE = f"""Tu es le relecteur d'un compagnon de jardinage. Tu lis le PREMIER tour d'un dialogue entre un
jardinier et son compagnon, et rien d'autre : la suite n'existe pas pour toi, ne la suppose pas.
Tu n'as pas la fiche de besoin : le jardinier n'a dit QUE sa première phrase.
Tu notes un seul critère, vrai ou faux, uniquement d'après l'attendu fourni et ce que le jardinier a lu.

UTILE AU PREMIER TOUR — vrai si le premier texte du compagnon répond au besoin, ou pose la SEULE question nécessaire.
Faux s'il répond à côté, redemande ce que le jardinier a déjà dit, passe sous silence ce que l'attendu exige
(saison, couverture absente…), montre un passage sur une autre culture, ou renvoie à une commande sans rapport.

L'ATTENDU décrit tout le dialogue. Au premier tour, seule compte la part de l'attendu qui répond à la PREMIÈRE phrase
du jardinier : ce que l'attendu prévoit après une phrase suivante (une correction, une précision, une confirmation)
n'est pas dû au premier tour, et son absence ne rend pas le premier tour inutile.

{REGLES}

Réponds par un seul objet JSON, sans autre texte :
{{"utile": true|false, "raison": "une phrase"}}"""

GRILLE_ABOUTIT = f"""Tu es le relecteur d'un compagnon de jardinage. Tu notes UN dialogue entre un jardinier et son compagnon.
Tu notes un seul critère, vrai ou faux, uniquement d'après l'attendu fourni et ce que le jardinier a lu.

ABOUTIT — vrai si, en 3 tours du jardinier au plus, il obtient la bonne réponse ou la bonne proposition décrite par
l'attendu. Faux s'il tourne en rond, s'il n'obtient qu'une question de plus, ou si la proposition porte une valeur
que le jardinier n'a pas dite.

{REGLES}

Réponds par un seul objet JSON, sans autre texte :
{{"aboutit": true|false, "raison": "une phrase"}}"""

#: Deux appels au juge par cas : « utile » sur le premier tour, « aboutit » sur le dialogue entier.
APPELS_JUGE_PAR_CAS = 2


@dataclass
class Verdict:
    utile: Optional[bool]
    aboutit: Optional[bool]
    raison: str = ""
    modele: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    #: Vrai quand la réponse du juge n'était pas lisible : le cas n'est noté ni vrai ni faux.
    illisible: bool = False

    def a_dict(self) -> dict:
        return {"utile": self.utile, "aboutit": self.aboutit, "raison": self.raison, "modele": self.modele,
                "tokens_in": self.tokens_in, "tokens_out": self.tokens_out, "illisible": self.illisible}

    @classmethod
    def depuis_dict(cls, d: Optional[dict]) -> Optional["Verdict"]:
        return cls(**d) if d else None


def transcrire(cas: Cas, trace: TraceCas, jour: Optional[date] = None, jusqu_au_tour: Optional[int] = None) -> str:
    """Le dialogue tel que le juge le lit : ce que le jardinier a dit, ce qu'il a lu, ce que le compagnon a appelé.
    `jusqu_au_tour` coupe la transcription après ce tour : le juge ne voit rien de la suite, ni la fiche de besoin.
    Avec la fiche, il prenait ce que le jardinier SAIT pour ce qu'il a DIT (21/11/2026 : B15-F7 « la fiche dit 2 m² »,
    B09-F6 « la fiche dit 20 graines »)."""
    lignes = ([f"AUJOURD'HUI : {jour.isoformat()}"] if jour else []) + [f"BESOIN : {cas.libelle}"]
    if jusqu_au_tour is None:
        lignes.append(f"FICHE DE BESOIN (ce que le jardinier sait et peut dire) : "
                      f"{json.dumps(cas.fiche, ensure_ascii=False)}")
    lignes.append(f"ATTENDU : {cas.attendus.bonne_reponse}")
    if cas.attendus.couverture_absente:
        lignes.append("COUVERTURE : la culture n'a pas de fiche agronomique ; la réponse doit le dire.")
    if cas.attendus.interdit_toute_ecriture:
        lignes.append("ÉCRITURE : aucune écriture n'est attendue pour ce besoin.")
    elif cas.attendus.ecritures_interdites:
        lignes.append(f"ÉCRITURES INTERDITES : {', '.join(cas.attendus.ecritures_interdites)}")
    tours = [t for t in trace.tours if jusqu_au_tour is None or t.rang <= jusqu_au_tour]
    lignes.append("DIALOGUE (premier tour seulement) :" if jusqu_au_tour is not None else "DIALOGUE :")
    for t in tours:
        lignes.append(f"[Tour {t.rang}] Jardinier : {t.phrase or '(rien)'}")
        for a in t.appels:
            lignes.append(f"    · appel {a.nom}({json.dumps(a.arguments, ensure_ascii=False)})"
                          + (" → refusé" if a.refus else ""))
        lignes.append(f"[Tour {t.rang}] Compagnon (lu par le jardinier) : {t.texte or '(rien)'}"
                      + (f"  [erreur : {t.erreur}]" if t.erreur else ""))
    return "\n".join(lignes)


def lire_verdict(texte: str) -> Optional[dict]:
    """Le premier objet JSON de la réponse du juge, ou `None`."""
    for m in re.finditer(r"\{.*?\}", texte or "", flags=re.DOTALL):
        try:
            d = json.loads(m.group(0))
        except ValueError:
            continue
        if isinstance(d, dict) and ("utile" in d or "aboutit" in d):
            return d
    return None


def _booleen(valeur: Any) -> Optional[bool]:
    if isinstance(valeur, bool):
        return valeur
    if isinstance(valeur, str) and valeur.strip().lower() in ("true", "vrai", "oui"):
        return True
    if isinstance(valeur, str) and valeur.strip().lower() in ("false", "faux", "non"):
        return False
    return None


class Juge:
    """Note un dialogue avec les deux grilles, un appel par critère. `appeler(prompt_fixe, message) -> (texte, jetons_in, jetons_out)` est
    injectable : les tests y mettent un faux, la mesure y met la passerelle (`appeler_par_la_passerelle`)."""

    def __init__(self, appeler: Callable[[str, str], tuple[str, int, int]], modele: str = MODELE_JUGE,
                 jour: Optional[date] = None):
        self._appeler, self.modele, self.jour = appeler, modele, jour

    def _critere(self, grille: str, message: str, cle: str) -> tuple[Optional[bool], str, int, int, bool]:
        """Un critère, un appel : (valeur, raison, jetons entrée, jetons sortie, illisible)."""
        try:
            texte, entree, sortie = self._appeler(grille, message)
        except Exception as e:  # noqa: BLE001 — un juge en panne n'invente pas de note
            return None, f"juge indisponible : {type(e).__name__}", 0, 0, True
        brut = lire_verdict(texte)
        if brut is None or _booleen(brut.get(cle)) is None:
            return None, "réponse du juge illisible", entree, sortie, True
        return _booleen(brut.get(cle)), str(brut.get("raison") or "")[:300], entree, sortie, False

    def noter(self, cas: Cas, trace: TraceCas) -> Verdict:
        if not trace.tours:
            return Verdict(False, False, "aucun tour joué", self.modele)
        premier = min(t.rang for t in trace.tours)
        utile, r_utile, e1, s1, i1 = self._critere(
            GRILLE_UTILE, transcrire(cas, trace, self.jour, jusqu_au_tour=premier), "utile")
        aboutit, r_aboutit, e2, s2, i2 = self._critere(GRILLE_ABOUTIT, transcrire(cas, trace, self.jour), "aboutit")
        return Verdict(utile, aboutit, f"utile : {r_utile} | aboutit : {r_aboutit}"[:600], self.modele,
                       e1 + e2, s1 + s2, illisible=i1 or i2)


def appeler_par_la_passerelle(ctx, modele: str = MODELE_JUGE) -> Callable[[str, str], tuple[str, int, int]]:
    """Le juge par la passerelle, sur la clé de mesure : le type d'appel `synthese` est mis le temps de l'appel sur
    le modèle du juge, puis restitué."""
    from llm import passerelle

    def appeler(prompt_fixe: str, message: str) -> tuple[str, int, int]:
        ancien = passerelle.GROQ_MODELE_PAR_TYPE[passerelle.TYPE_SYNTHESE]
        passerelle.GROQ_MODELE_PAR_TYPE[passerelle.TYPE_SYNTHESE] = modele
        try:
            r = passerelle.appeler_chat(appel_type=passerelle.TYPE_SYNTHESE, ctx=ctx, prompt_fixe=prompt_fixe,
                                        message_utilisateur=message, max_tokens=300,
                                        temperature=TEMPERATURE_JUGE, reasoning=False)
        finally:
            passerelle.GROQ_MODELE_PAR_TYPE[passerelle.TYPE_SYNTHESE] = ancien
        return r.texte, int(r.tokens_in or 0), int(r.tokens_out or 0)

    return appeler


def echantillon_humain(identifiants: list[str], part: float = PART_RELECTURE_HUMAINE, graine: str = "") -> list[str]:
    """Au moins `part` des cas, à relire par un humain : tirage déterministe (même graine, même échantillon), au
    moins un cas dès qu'il y en a un."""
    if not identifiants:
        return []
    n = max(1, math.ceil(len(identifiants) * part))
    classes = sorted(set(identifiants), key=lambda i: hashlib.sha256(f"{graine}|{i}".encode()).hexdigest())
    return sorted(classes[:n])

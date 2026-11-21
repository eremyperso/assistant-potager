"""Les moteurs que le lanceur sait jouer [US-337] : `actuel` (la chaîne livrée), `capacites` (la boucle cible,
point de départ : le prototype du 14/11, configuration C) et `claude_mcp` (la configuration D, rejouable sur le même
potager que les autres).

Un moteur joue UN dialogue : `ouvrir(cas)`, puis `jouer(rang, phrase=…)` ou `jouer(rang, clic=…)` pour chaque tour,
qui rend une `TraceTour`. Il n'écrit jamais dans le potager (CA6c) : les lectures se font dans une transaction
annulée, les écritures sont simulées au schéma du registre ; seules les lignes `conso_tokens` de la passerelle sont
créées.
"""
from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Callable, Iterator, Optional

from tools.jeu_evaluation.jeu import Cas
from tools.jeu_evaluation.trace import AppelTrace, TraceTour, tronquer

log = logging.getLogger("potager")

MOTEUR_ACTUEL = "actuel"
MOTEUR_CAPACITES = "capacites"
MOTEUR_CLAUDE_MCP = "claude_mcp"
MOTEURS = (MOTEUR_ACTUEL, MOTEUR_CAPACITES, MOTEUR_CLAUDE_MCP)

#: Les lectures du registre (US-291, US-339) que la configuration C appelle.
LECTURES = ("voir_plan", "voir_pepiniere", "voir_stock", "consulter_carnet", "voir_statistiques", "voir_meteo",
            "voir_calendrier", "voir_echeances", "chercher_connaissance",
            "situation_culture",  # [US-339] le verdict de saison de la fiche culture
            "voisinages_culture", "que_semer_ce_mois", "voir_mon_potager")  # [US-351] lectures d'écran
#: Dans la configuration C, une seule écriture : proposer le geste, simulée au schéma du MCP.
ECRITURES_SIMULEES = ("proposer_geste",)
DECISIONS_SIMULEES = ("confirmer_proposition", "abandonner_proposition")

#: Nombre d'étapes (appels au modèle) au plus par tour : protège de la boucle (§4.3 de l'architecture).
ETAPES_MAX = 6

PROMPT_CAPACITES = """Tu es le compagnon de l'Assistant Potager, un carnet de potager pour jardiniers amateurs. Tu parles français, simplement et court.
Tu lis avant de répondre : les outils te donnent le potager du jardinier, le calendrier de sa zone, sa météo, son carnet et la connaissance de l'application.
N'invente jamais une parcelle, une culture, une quantité ni une date : une valeur que le jardinier a déjà dite ne se redemande pas, et tu ne poses que la question qui manque, une seule à la fois.
Si une valeur manque, tu peux en avancer une dans ta réponse (« 10 plants, ça te va ? ») et attendre son accord ; ne la mets jamais dans une proposition d'écriture avant qu'il l'ait acceptée.
Pour noter un geste (semis, plantation, récolte, perte), appelle proposer_geste : l'application fait confirmer le jardinier. Tu n'écris jamais toi-même dans son carnet.
Un passage de connaissance qui parle d'une autre culture ne répond pas à sa question : ne le présente pas comme une réponse.
Quand l'application n'a rien sur le sujet, dis-le, puis donne au plus un conseil général en précisant qu'il ne vient pas de l'application.
Ne donne jamais de dose ni de produit de traitement.
"""

PROMPT_CLAUDE_MCP = (
    "Tu es un assistant de jardinage connecté au carnet de potager du jardinier par les outils fournis. "
    "Réponds en français, simplement."
)

#: Les gestes qui demandent une quantité pour être proposés (le contrôle réel la réclame en question).
_SANS_QUANTITE = ("observation",)


# ═════════════════════════════════════════════════════════════════════════════
# Le registre vu du client : lectures dans une transaction annulée, écritures simulées
# ═════════════════════════════════════════════════════════════════════════════
class RegistreMesure:
    """Exécute les capacités du registre MCP pour un moteur, sans rien écrire (CA6c).

    * une LECTURE s'exécute pour de vrai, sous le contexte locataire du potager mesuré, dans une session dont
      `commit` est remplacé par `rollback` : même une lecture qui voudrait valider ne laisse rien ;
    * une ÉCRITURE n'est jamais exécutée : `proposer_geste` rend un récapitulatif fabriqué au schéma du registre,
      `confirmer_proposition` ne fait que noter l'exécution qui aurait eu lieu."""

    def __init__(self, ctx, *, decisions: bool = False, ouvrir_session: Optional[Callable] = None,
                 jour: Optional[date] = None):
        from app.services.capacites.registre import REGISTRE  # [US-338] le registre neutre, partagé avec le MCP
        import app.services.capacites  # noqa: F401 — l'import remplit le registre (lectures, écritures, commandes)

        self.ctx, self.jour = ctx, jour or date.today()
        self.registre = REGISTRE
        manquants = [n for n in (*LECTURES, *ECRITURES_SIMULEES, *DECISIONS_SIMULEES) if n not in REGISTRE]
        if manquants:
            raise RuntimeError(f"capacités absentes du registre : {manquants}")
        for nom in LECTURES:
            if REGISTRE[nom].ecriture:
                raise RuntimeError(f"{nom} n'est plus une lecture : la mesure ne peut plus l'exécuter")
        self.noms = (*LECTURES, *ECRITURES_SIMULEES, *(DECISIONS_SIMULEES if decisions else ()))
        self._ouvrir_session = ouvrir_session
        self._propositions: dict[int, dict] = {}
        self._prochaine = 900_000_000  # identifiants simulés, hors de toute plage réelle
        self.appels: int = 0

    # ── ce que le modèle voit ───────────────────────────────────────────────
    def schemas_openai(self) -> list[dict]:
        return [{"type": "function", "function": {
            "name": self.registre[n].nom, "description": self.registre[n].description,
            "parameters": self.registre[n].schema_entree()}} for n in self.noms]

    def schemas_anthropic(self) -> list[dict]:
        return [{"name": self.registre[n].nom, "description": self.registre[n].description,
                 "input_schema": self.registre[n].schema_entree()} for n in self.noms]

    # ── exécution ───────────────────────────────────────────────────────────
    @contextmanager
    def _session(self) -> Iterator[Any]:
        from database.db import SessionLocal, tenant_scope

        db = (self._ouvrir_session or SessionLocal)()
        db.commit = db.rollback  # CA6c : rien ne se valide jamais
        try:
            with tenant_scope(self.ctx.potager_id):
                yield db
        finally:
            try:
                db.rollback()
            finally:
                db.close()

    def executer(self, nom: str, arguments: Any, tour: TraceTour) -> AppelTrace:
        """Exécute (ou simule) un appel d'outil et le range dans la trace du tour."""
        from app.services.capacites.registre import AppelCapacite, RefusCapacite, appelant_compagnon, verifier_arguments

        arguments = arguments if isinstance(arguments, dict) else {}
        appel = AppelTrace(nom=nom, arguments=arguments)
        tour.appels.append(appel)
        self.appels += 1
        outil = self.registre.get(nom)
        if outil is None or nom not in self.noms:
            appel.refus, appel.resultat = True, f"Outil inconnu : {nom}"
            return appel
        try:
            verifier_arguments(outil, arguments)
            if nom in ECRITURES_SIMULEES:
                appel.ecriture, appel.simule = True, True
                donnees = self._proposer_geste_simule(arguments, tour)
            elif nom in DECISIONS_SIMULEES:
                appel.ecriture, appel.simule = True, True
                donnees = self._decision_simulee(nom, arguments, tour)
            else:
                with self._session() as db:
                    donnees = outil.executer(db, AppelCapacite(appelant_compagnon(self.ctx), self.ctx, arguments))
            appel.resultat = tronquer(json.dumps(donnees, ensure_ascii=False, default=str))
        except RefusCapacite as refus:
            appel.refus, appel.resultat = True, tronquer(str(refus.message))
        except Exception as e:  # noqa: BLE001 — un outil en erreur est un résultat, pas la fin de la mesure
            log.warning("[US-337] %s en erreur : %s", nom, e)
            appel.refus, appel.resultat = True, f"Erreur interne ({type(e).__name__})"
        return appel

    # ── écritures simulées au schéma du registre ────────────────────────────
    def _proposer_geste_simule(self, arguments: dict, tour: TraceTour) -> dict:
        from app.services.compagnon import gestes_conversation as dits
        from app.services.capacites import ecritures
        from app.services.capacites.registre import RefusCapacite as RefusOutil

        item = ecritures._item({**arguments, **({} if arguments.get("date") else {"date": self.jour.isoformat()})})
        if item.get("action") not in _SANS_QUANTITE and item.get("quantite") is None and item.get("rang") is None:
            # Le contrôle réel rend la question à poser ; rien n'est proposé (étude §6).
            return {"proposition": None, "question": "Quelle quantité ?",
                    "a_faire": "Pose cette question au jardinier, puis rappelle proposer_geste avec sa réponse.",
                    "simule": True}
        if item.get("date") and date.fromisoformat(item["date"]) > self.jour:
            raise RefusOutil("Une date future est refusée : un geste se note après coup.", "geste_invalide")
        self._prochaine += 1
        identifiant = self._prochaine
        recap = dits.resume(item)
        self._propositions[identifiant] = {"outil": "proposer_geste", "arguments": dict(arguments)}
        tour.propositions.append({"outil": "proposer_geste", "arguments": dict(arguments), "id": identifiant,
                                  "recapitulatif": recap})
        tour.proposition_en_attente = True
        return {"proposition": identifiant, "etat": "en_attente", "simule": True,
                "recapitulatif": [{"geste": dits.libelle_action(item.get("action")), "culture": item.get("culture"),
                                   "parcelle": item.get("parcelle"), "quantite": item.get("quantite"),
                                   "unite": item.get("unite"), "date": item.get("date"), "resume": recap}],
                "stock": "(simulé : le stock n'est pas calculé par la mesure)", "avertissements": [],
                "a_faire": ecritures.TEXTE_A_FAIRE}

    def _decision_simulee(self, nom: str, arguments: dict, tour: TraceTour) -> dict:
        identifiant = arguments.get("proposition")
        proposition = self._propositions.get(identifiant if isinstance(identifiant, int) else -1)
        if proposition is None:
            return {"erreur": "proposition inconnue ou déjà traitée", "simule": True}
        if nom == "confirmer_proposition":
            tour.executions.append({"proposition": identifiant, "outil": proposition["outil"], "simule": True})
            self._propositions.pop(identifiant, None)
            tour.proposition_en_attente = False
            return {"confirmee": True, "simule": True, "ecrit": "NON : la mesure n'écrit rien"}
        self._propositions.pop(identifiant, None)
        tour.proposition_en_attente = False
        return {"abandonnee": True, "simule": True}

    @property
    def propositions_en_attente(self) -> int:
        return len(self._propositions)


# ═════════════════════════════════════════════════════════════════════════════
# Le modèle simulé : pour essayer le lanceur sans rien consommer — jamais une mesure
# ═════════════════════════════════════════════════════════════════════════════
class ModeleSimule:
    """Un « modèle » qui répond par une phrase fixe sans outil. Sert à `--simule` et aux tests : tout passage obtenu
    avec lui porte `modele_simule=True` et n'est jamais présenté comme une mesure (CA7)."""

    nom = "simule"

    def __init__(self, reponses: Optional[list] = None):
        self._reponses = list(reponses or [])
        self.appels: list[dict] = []

    def __call__(self, **arguments):
        from llm import passerelle

        # L'historique est une liste vivante : on en garde l'état à l'instant de l'appel.
        self.appels.append({**arguments, "historique": list(arguments.get("historique") or [])})
        if self._reponses:
            r = self._reponses.pop(0)
            if isinstance(r, passerelle.ReponseOutils):
                return r
            texte = str(r)
        else:
            texte = "Simulation : aucune réponse de modèle."
        return passerelle.ReponseOutils(texte=texte, modele="simule", appel_type=passerelle.TYPE_AGENT,
                                        tokens_in=100, tokens_out=20, tokens_cache=80, latence_ms=1)


# ═════════════════════════════════════════════════════════════════════════════
# La boucle à capacités — le prototype du 14/11 (configuration C)
# ═════════════════════════════════════════════════════════════════════════════
def _message_assistant(reponse) -> dict:
    return {"role": "assistant", "content": reponse.texte or None, "tool_calls": [
        {"id": a.id or f"appel_{i}", "type": "function",
         "function": {"name": a.nom, "arguments": json.dumps(a.arguments, ensure_ascii=False)}}
        for i, a in enumerate(reponse.appels)]}


class MoteurCapacites:
    """Small 4 + capacités + historique complet : les neuf lectures du registre, `proposer_geste` simulé, la vraie
    passerelle (`appeler_chat_outils`), l'historique complet (résultats d'outils compris) et le prompt générique.

    `tool_choice="auto"` : le modèle lit ce qu'il veut, puis rédige. Un tour s'arrête au premier texte sans appel,
    ou après `ETAPES_MAX` étapes."""

    nom = MOTEUR_CAPACITES
    mode_confirmation = "phrase"

    def __init__(self, ctx, *, appeler: Optional[Callable] = None, modele_simule: bool = False,
                 decisions: bool = False, jour: Optional[date] = None, registre: Optional[RegistreMesure] = None,
                 ouvrir_session: Optional[Callable] = None):
        from llm import passerelle

        self.ctx = ctx
        self._appeler = appeler or passerelle.appeler_chat_outils
        self.modele_simule = modele_simule
        self.jour = jour or date.today()
        self.registre = registre or RegistreMesure(ctx, decisions=decisions, ouvrir_session=ouvrir_session,
                                                   jour=self.jour)
        self.messages: list[dict] = []
        self.modele = ""
        self._decisions = decisions

    # ── dialogue ────────────────────────────────────────────────────────────
    def ouvrir(self, cas: Cas) -> None:
        self.messages = []
        self.registre = RegistreMesure(self.ctx, decisions=self._decisions,
                                       ouvrir_session=self.registre._ouvrir_session, jour=self.jour)

    def fermer(self) -> None:
        self.messages = []

    def _prompt_variable(self) -> str:
        jours = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
        return f"\nAujourd'hui : {jours[self.jour.weekday()]} {self.jour.isoformat()}."

    def jouer(self, rang: int, phrase: str = "", clic: str = "") -> TraceTour:
        tour = TraceTour(rang=rang, jardinier=phrase, clic=clic)
        # Un clic « Confirmer » s'entend comme un « oui » : la boucle à capacités confirme par une phrase.
        dit = phrase or {"Confirmer": "oui", "Annuler": "non, laisse tomber"}.get(clic, clic)
        self.messages.append({"role": "user", "content": dit})
        schemas = self.registre.schemas_openai()
        for _ in range(ETAPES_MAX):
            try:
                reponse = self._appeler(
                    ctx=self.ctx, outils=schemas, prompt_fixe=PROMPT_CAPACITES,
                    prompt_variable=self._prompt_variable(), message_utilisateur=None, historique=self.messages,
                    tool_choice="auto", max_tokens=1024)
            except Exception as e:  # noqa: BLE001 — quota, panne : le tour est marqué, la mesure continue
                tour.erreur = f"{type(e).__name__}: {e}"
                break
            tour.etapes += 1
            tour.tokens_in += int(reponse.tokens_in or 0)
            tour.tokens_out += int(reponse.tokens_out or 0)
            tour.tokens_cache += int(reponse.tokens_cache or 0)
            tour.latence_ms += int(reponse.latence_ms or 0)
            self.modele = reponse.modele or self.modele
            if not reponse.ok:
                tour.erreur = f"statut {reponse.statut}"
                break
            if not reponse.appels:
                tour.texte = reponse.texte
                self.messages.append({"role": "assistant", "content": reponse.texte})
                break
            self.messages.append(_message_assistant(reponse))
            for i, a in enumerate(reponse.appels):
                appel = self.registre.executer(a.nom, a.arguments if a.arguments_valides else {}, tour)
                self.messages.append({"role": "tool", "tool_call_id": a.id or f"appel_{i}",
                                      "content": appel.resultat})
        else:
            tour.erreur = f"plus de {ETAPES_MAX} étapes sans réponse"
        tour.texte = _avec_carte(tour)
        return tour


def _avec_carte(tour: TraceTour) -> str:
    """Le texte lu par le jardinier : la réponse du modèle, plus la carte de chaque proposition (c'est le code qui
    l'ajoute dans l'application, §4.3)."""
    cartes = [f"[Proposition] {p['recapitulatif']}" for p in tour.propositions if p.get("recapitulatif")]
    return "\n".join(x for x in (tour.texte, *cartes) if x)


# ═════════════════════════════════════════════════════════════════════════════
# Configuration D — Claude + MCP, sur le même potager que les autres
# ═════════════════════════════════════════════════════════════════════════════
VARIABLE_CLE_CLAUDE = "ANTHROPIC_API_KEY_MESURE"
MODELE_CLAUDE = "claude-sonnet-5-5"


class MoteurClaudeMcp:
    """Claude, avec le même registre de capacités que le connecteur MCP, sur le potager mesuré : la configuration D du
    14/11 ne se mélange plus au potager, au modèle et aux capacités des autres (CA6d).

    Le client est celui du SDK `anthropic` (importé à l'ouverture seulement) ; sa clé est `ANTHROPIC_API_KEY_MESURE`.
    Les outils sont ceux du registre, lus par le même `RegistreMesure` que la boucle à capacités."""

    nom = MOTEUR_CLAUDE_MCP
    mode_confirmation = "phrase"

    def __init__(self, ctx, *, client: Any = None, modele: str = MODELE_CLAUDE, modele_simule: bool = False,
                 jour: Optional[date] = None, ouvrir_session: Optional[Callable] = None):
        self.ctx, self.modele, self.modele_simule = ctx, modele, modele_simule
        self.jour = jour or date.today()
        self._client = client
        self._ouvrir_session = ouvrir_session
        self.registre = RegistreMesure(ctx, decisions=True, ouvrir_session=ouvrir_session, jour=self.jour)
        self.messages: list[dict] = []

    def _client_claude(self) -> Any:
        if self._client is None:
            import os

            cle = (os.environ.get(VARIABLE_CLE_CLAUDE) or "").strip()
            if not cle:
                raise RuntimeError(f"{VARIABLE_CLE_CLAUDE} absente : la configuration D se joue avec sa propre clé")
            try:
                import anthropic
            except ImportError as e:  # pragma: no cover — dépend de l'environnement
                raise RuntimeError("le SDK `anthropic` n'est pas installé (pip install anthropic)") from e
            self._client = anthropic.Anthropic(api_key=cle)
        return self._client

    def ouvrir(self, cas: Cas) -> None:
        self.messages = []
        self.registre = RegistreMesure(self.ctx, decisions=True, ouvrir_session=self._ouvrir_session, jour=self.jour)

    def fermer(self) -> None:
        self.messages = []

    def jouer(self, rang: int, phrase: str = "", clic: str = "") -> TraceTour:
        tour = TraceTour(rang=rang, jardinier=phrase, clic=clic)
        dit = phrase or {"Confirmer": "oui", "Annuler": "non, laisse tomber"}.get(clic, clic)
        self.messages.append({"role": "user", "content": dit})
        schemas = self.registre.schemas_anthropic()
        systeme = f"{PROMPT_CLAUDE_MCP}\nAujourd'hui : {self.jour.isoformat()}."
        for _ in range(ETAPES_MAX):
            debut = time.monotonic()
            try:
                reponse = self._client_claude().messages.create(
                    model=self.modele, max_tokens=1024, system=systeme, tools=schemas, messages=self.messages)
            except Exception as e:  # noqa: BLE001
                tour.erreur = f"{type(e).__name__}: {e}"
                break
            tour.etapes += 1
            tour.latence_ms += int((time.monotonic() - debut) * 1000)
            usage = getattr(reponse, "usage", None)
            tour.tokens_in += int(getattr(usage, "input_tokens", 0) or 0)
            tour.tokens_out += int(getattr(usage, "output_tokens", 0) or 0)
            tour.tokens_cache += int(getattr(usage, "cache_read_input_tokens", 0) or 0)
            blocs = list(getattr(reponse, "content", []) or [])
            self.messages.append({"role": "assistant", "content": [_bloc_vers_dict(b) for b in blocs]})
            utilises = [b for b in blocs if getattr(b, "type", "") == "tool_use"]
            if not utilises:
                tour.texte = "\n".join(getattr(b, "text", "") for b in blocs if getattr(b, "type", "") == "text")
                break
            resultats = []
            for b in utilises:
                appel = self.registre.executer(b.name, dict(b.input or {}), tour)
                resultats.append({"type": "tool_result", "tool_use_id": b.id, "content": appel.resultat,
                                  "is_error": appel.refus})
            self.messages.append({"role": "user", "content": resultats})
        else:
            tour.erreur = f"plus de {ETAPES_MAX} étapes sans réponse"
        tour.texte = _avec_carte(tour)
        return tour


class ClientClaudeSimule:
    """Un client `anthropic` de pacotille : une phrase fixe, aucun appel. Jamais une mesure."""

    def __init__(self, texte: str = "Simulation : aucune réponse de modèle."):
        from types import SimpleNamespace

        self._reponse = SimpleNamespace(
            content=[SimpleNamespace(type="text", text=texte)],
            usage=SimpleNamespace(input_tokens=100, output_tokens=20, cache_read_input_tokens=80))
        self.messages = SimpleNamespace(create=lambda **_: self._reponse)


def _bloc_vers_dict(bloc: Any) -> dict:
    if getattr(bloc, "type", "") == "tool_use":
        return {"type": "tool_use", "id": bloc.id, "name": bloc.name, "input": dict(bloc.input or {})}
    return {"type": "text", "text": getattr(bloc, "text", "")}


# ═════════════════════════════════════════════════════════════════════════════
# La chaîne actuelle — la cascade du bot, rejouée telle qu'elle est livrée
# ═════════════════════════════════════════════════════════════════════════════
class MoteurActuel:
    """La cascade du bot (`interpreteur_commandes.interpreter`, agent compris) jouée par les pièces d'US-256 :
    vrai contexte court, vrai prompt, vrai catalogue, vrai validateur. Rien n'est exécuté : l'échange n'est pas
    persisté, l'ancien repli est coupé, un clic « Confirmer » vide la proposition sans l'exécuter.

    `fictif=True` : parcelles et lectures simulées (potager neuf sans base) ; sinon, les vraies données du potager
    de `ctx`, en lecture seule."""

    nom = MOTEUR_ACTUEL
    mode_confirmation = "bouton"

    def __init__(self, ctx, *, mode: str = "prioritaire", fictif: bool = False, appeler: Optional[Callable] = None,
                 modele_simule: bool = False, parcelles: Optional[tuple[str, ...]] = None):
        from llm import passerelle
        from tools import evaluer_dialogues as ed

        self.ctx, self.mode, self.fictif, self.modele_simule = ctx, mode, fictif, modele_simule
        self._ed = ed
        self._appeler = appeler or passerelle.appeler_chat_outils
        self.enregistreur = ed.Enregistreur(self._appeler)
        self.cascade = ed.Cascade(ed.interpreteur_agent.proposer, ed.interpreteur_commandes._est_demande_de_savoir)
        self.etat = ed.EtatDialogue()
        self.modele = ""
        self._pile: Optional[Any] = None
        self._lectures: list[tuple[dict, str]] = []
        #: (nom d'outil, ce qu'il a rendu au modèle) — toutes les lectures du tour, pas seulement `lire`.
        self._resultats: list[tuple[str, str]] = []
        #: Les gestes que le parseur a rangés en attente pendant le cas (effacés à `fermer`), et celui qui attend.
        self._gestes_crees: list[int] = []
        self._geste_en_attente: Optional[tuple[int, str]] = None

    def ouvrir(self, cas: Cas) -> None:
        from contextlib import ExitStack
        from unittest.mock import patch

        from app.services.agent import lecture
        from llm import passerelle

        ed = self._ed
        self.etat = ed.EtatDialogue()
        self._lectures = []
        self._resultats = []
        pile = ExitStack()
        lire_reel = lecture.lire

        def lire_enregistre(arguments, ctx):
            resultat = lire_reel(arguments, ctx) if not self.fictif else ed.ev.lecture_fictive(arguments, ctx)
            self._lectures.append((dict(arguments or {}), str(resultat)))
            return resultat

        from app.services.agent import interpreteur_agent as ia

        tour_suivant_reel = ia._tour_suivant

        def tour_suivant_enregistre(appels, *arguments, **options):
            """Garde ce que chaque outil a rendu au modèle : le contrôle des chiffres (rien d'inventé) en a besoin."""
            messages = tour_suivant_reel(appels, *arguments, **options)
            noms = {tc["id"]: tc["function"]["name"] for m in messages if m.get("role") == "assistant"
                    for tc in (m.get("tool_calls") or [])}
            for m in messages:
                if m.get("role") == "tool" and m.get("content") != ia.REPONSE_ECRITURE:
                    self._resultats.append((noms.get(m.get("tool_call_id"), ""), str(m.get("content") or "")))
            return messages

        pile.enter_context(patch.object(ia, "_tour_suivant", tour_suivant_enregistre))
        if self.fictif:
            pile.enter_context(ed.potager_fictif())
        else:
            pile.enter_context(ed.potager_reel())
        pile.enter_context(ed.cascade_de_production(self.cascade, self.mode))
        pile.enter_context(patch.object(passerelle, "appeler_chat_outils", self.enregistreur))
        pile.enter_context(patch.object(lecture, "lire", lire_enregistre))
        self._pile = pile

    def fermer(self) -> None:
        try:
            self._oublier_gestes(tuple(self._gestes_crees))
        finally:
            self._gestes_crees, self._geste_en_attente = [], None
            if self._pile is not None:
                self._pile.close()
                self._pile = None

    def jouer(self, rang: int, phrase: str = "", clic: str = "") -> TraceTour:
        from dataclasses import replace

        from app.services.agent import contexte_court
        from app.services import interpreteur_commandes as ic

        ed = self._ed
        tour = TraceTour(rang=rang, jardinier=phrase, clic=clic)
        if clic and self._geste_en_attente is not None:
            identifiant, resume = self._geste_en_attente
            if clic == "Confirmer":
                tour.executions.append({"proposition": resume, "simule": True})
            self._oublier_gestes((identifiant,))
            self._geste_en_attente = None
            tour.texte = {"Confirmer": "(Confirmé : la mesure n'exécute rien.)",
                          "Annuler": "(Annulé.)"}.get(clic, "")
            return tour
        if clic:
            en_attente = self.etat.en_attente
            if clic == "Confirmer" and en_attente is not None:
                tour.executions.append({"proposition": _decrire_proposition(en_attente), "simule": True})
            self.etat.en_attente = None
            tour.texte = {"Confirmer": "(Confirmé : la mesure n'exécute rien.)",
                          "Annuler": "(Annulé.)"}.get(clic, "")
            return tour

        maintenant = self.etat.instant
        contexte = contexte_court.construire(
            self.ctx, self.etat.en_attente, self.etat.instant, self.ctx.potager_id, maintenant=maintenant,
            echanges=tuple(self.etat.echanges), question=contexte_court.question_de(tuple(self.etat.echanges)))
        self.enregistreur.reponses.clear()
        self.cascade.oublier()
        self._lectures.clear()
        self._resultats.clear()
        try:
            resultat = ic.interpreter(phrase, self.ctx, contexte_court=contexte)
        except Exception as e:  # noqa: BLE001
            tour.erreur = f"{type(e).__name__}: {e}"
            return tour
        chemin = self.cascade.chemin(resultat)
        reponses = list(self.enregistreur.reponses)
        for r in reponses:
            tour.etapes += 1
            tour.tokens_in += int(r.tokens_in or 0)
            tour.tokens_out += int(r.tokens_out or 0)
            tour.tokens_cache += int(r.tokens_cache or 0)
            tour.latence_ms += int(r.latence_ms or 0)
            self.modele = r.modele or self.modele
            if not r.ok:
                tour.erreur = tour.erreur or f"statut {r.statut}"
            for a in r.appels:
                tour.appels.append(AppelTrace(nom=a.nom, arguments=dict(a.arguments or {}),
                                              ecriture=ed.est_ecriture(a.nom) and a.nom not in ("lire",)))
        for (arguments, texte) in self._lectures:
            for a in tour.appels:
                if a.nom == "lire" and not a.resultat and a.arguments == arguments:
                    a.resultat = tronquer(texte)
                    break
        for (nom, texte) in self._resultats:
            for a in tour.appels:
                if a.nom == nom and not a.resultat:
                    a.resultat = tronquer(texte)
                    break
        noms, textes = ed.vu_par_le_jardinier(resultat, chemin)
        tour.texte = "\n".join(t for t in textes if t)
        proposition = resultat.proposition if isinstance(resultat, ic.ReponseAgent) else resultat
        proposition = proposition if isinstance(proposition, (ic.Plan, ic.CommandeInterpretee)) else None
        if proposition is not None:
            tour.propositions.append(_decrire_proposition_dict(proposition))
            tour.proposition_en_attente = True
            tour.texte = "\n".join(x for x in (tour.texte, f"[Proposition] {ed._decrire_vu(proposition, chemin)}") if x)
        elif not tour.texte:
            tour.texte = ed._decrire_vu(resultat, chemin)
        instant = time.time()
        if proposition is not None:
            self.etat.en_attente, self.etat.instant = proposition, instant
        else:
            self.etat.en_attente = None
        retenu = resultat if isinstance(resultat, ic.ReponseAgent) else (
            proposition or (resultat if isinstance(resultat, ic.Aiguillage) else None))
        echange = contexte_court.echange_de(retenu, instant) if retenu is not None else None
        if echange is not None:
            self.etat.echanges = (self.etat.echanges + [echange])[-contexte_court.NB_ECHANGES_MAX:]
        elif self.etat.echanges and self.etat.echanges[-1].question is not None:
            self.etat.echanges[-1] = replace(self.etat.echanges[-1], question=None)
        if isinstance(resultat, ic.Aiguillage) and resultat.vers == ic.VERS_GESTE and not self.fictif:
            self._suivre_le_geste(phrase, tour, instant)
        return tour

    def _suivre_le_geste(self, phrase: str, tour: TraceTour, instant: float) -> None:
        """[G0, 20/11/2026] Ce que fait la PWA d'un aiguillage « geste » (`echange_pwa._proposer_un_geste`) : le
        parseur des gestes lit la phrase ; ce qui manque devient une question, un geste compris devient une carte
        EN ATTENTE (vraie proposition en base de test, pour que le tour suivant la voie, comme dans la PWA). La carte
        ne part pas dans Telegram, rien n'est confirmé ; la proposition est effacée à la fin du cas."""
        from app.services.agent import contexte_court
        from app.services.compagnon import gestes_conversation as gestes_dits
        from app.services.compagnon import orchestrateur
        from app.services.compagnon import propositions as svc_propositions

        try:
            with svc_propositions.session_sur(self.ctx.potager_id) as db:
                preparation = gestes_dits.preparer(db, self.ctx, phrase)
            if preparation.question:
                tour.texte = orchestrateur.repondre_a_une_question(self.ctx, phrase, None).texte
                return
            if preparation.precision or not preparation.items:
                tour.texte = preparation.precision or "Je n'ai détecté aucune action à enregistrer."
                resume_echange = tour.texte
            else:
                geste = gestes_dits.proposer(self.ctx, preparation.items, phrase)
                self._gestes_crees.append(geste.id)
                resumes = [gestes_dits.resume(i) for i in preparation.items]
                for item in preparation.items:
                    tour.propositions.append({"outil": "geste", "arguments": dict(item), "id": geste.id})
                tour.proposition_en_attente = True
                tour.texte = ("Voici ce que j'ai compris. Je n'écris rien tant que tu n'as pas confirmé.\n"
                              + "\n".join(f"[Proposition] {r}" for r in resumes))
                self._geste_en_attente = (geste.id, " ; ".join(resumes))
                resume_echange = "proposition : " + " ; ".join(resumes)
        except Exception as e:  # noqa: BLE001 — le parseur peut manquer de modèle (quota) : on le trace
            tour.erreur = tour.erreur or f"geste : {type(e).__name__}: {e}"
            return
        echange = contexte_court.Echange(phrase, resume_echange, instant)
        self.etat.echanges = (self.etat.echanges + [echange])[-contexte_court.NB_ECHANGES_MAX:]

    def _oublier_gestes(self, identifiants) -> None:
        """Efface les propositions que la mesure a rangées en base de test : aucune ne survit au cas."""
        from app.services.compagnon import propositions as svc_propositions
        from database.models import Proposition

        ids = [i for i in identifiants if i is not None]
        if not ids:
            return
        with svc_propositions.session_sur(self.ctx.potager_id) as db:
            db.query(Proposition).filter(Proposition.id.in_(ids)).delete(synchronize_session=False)
            db.commit()


def _decrire_proposition(proposition: Any) -> str:
    try:
        from app.services.interpreteur_commandes import Plan

        if isinstance(proposition, Plan):
            return " ; ".join(e.commande_equivalente() for e in proposition.etapes)
        return proposition.commande_equivalente()
    except Exception:  # noqa: BLE001
        return str(proposition)


def _decrire_proposition_dict(proposition: Any) -> dict:
    """Une proposition de la chaîne actuelle, rangée comme une proposition de la boucle à capacités."""
    from app.services.interpreteur_commandes import Plan
    from tools import evaluer_dialogues as ed

    commandes = proposition.etapes if isinstance(proposition, Plan) else (proposition,)
    premiere = commandes[0]
    return {"outil": ed.outil_de_forme(premiere.forme), "arguments": dict(premiere.valeurs or {}),
            "recapitulatif": _decrire_proposition(proposition)}


# ═════════════════════════════════════════════════════════════════════════════
def creer_moteur(nom: str, ctx, *, simule: bool = False, jour: Optional[date] = None, **options) -> Any:
    """Le moteur `nom` pour le potager `ctx`. `simule=True` : un modèle de pacotille (`ModeleSimule`), rien n'est
    consommé et rien n'est une mesure."""
    appeler = ModeleSimule() if simule else None
    if nom == MOTEUR_ACTUEL:
        return MoteurActuel(ctx, appeler=appeler, modele_simule=simule, **options)
    if nom == MOTEUR_CAPACITES:
        return MoteurCapacites(ctx, appeler=appeler, modele_simule=simule, jour=jour,
                               **{k: v for k, v in options.items() if k in ("decisions", "ouvrir_session")})
    if nom == MOTEUR_CLAUDE_MCP:
        options = {k: v for k, v in options.items() if k in ("client", "modele", "ouvrir_session")}
        if simule and "client" not in options:
            options["client"] = ClientClaudeSimule()
        return MoteurClaudeMcp(ctx, modele_simule=simule, jour=jour, **options)
    raise ValueError(f"moteur inconnu : {nom!r} (attendu : {', '.join(MOTEURS)})")

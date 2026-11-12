"""
llm/contexte_appel.py — Contexte d'un appel au modèle [US-306, US-307]
======================================================================
Ce que la passerelle (`llm/passerelle.py`) écrit dans `conso_tokens` au-delà de
l'appel lui-même — d'où il vient, à quel échange il appartient — ne voyage jamais
en paramètre d'une fonction métier : c'est un **contexte** (`ContextVar`), posé
une fois par le point d'entrée (bot, API, MCP, outil de `tools/`) et lu par la
passerelle au moment d'écrire la ligne. Même mécanisme que `TenantContext`
(US-046) et que l'accumulateur de cascade (US-097) : il suit la tâche asyncio ou
la requête, sans fuite entre deux traitements concurrents.

Ce module ne dépend ni de la base ni de la passerelle : il est importable de
partout (outils, harnais, mode test) sans cycle.

Échange, canal [US-307 / D4]
----------------------------
Un **échange** est tout ce que le modèle a fait pour produire UNE réponse : la
dictée, la boucle d'agent, la classification, le résumé parlé, la synthèse vocale.
Son identifiant (`echange_ref`) est créé à l'entrée de chaque interaction (Update
Telegram, requête de l'API, appel d'outil MCP, exécution d'un outil de `tools/`) et
partagé par toutes les lignes écrites pendant son traitement. Le **canal** dit par
où l'interaction est arrivée. Aucun des deux n'est un paramètre de fonction métier.

Provenance [US-306 / D3]
------------------------
`usage` (un jardinier), `mesure` (une campagne de `tools/`), `test` (harnais
conversationnel, mode test), `fond` (une tâche sans utilisateur) et `historique`
(lignes d'avant la colonne). `historique` est réservé à la migration : aucun code
ne peut l'écrire.
"""
from __future__ import annotations

import contextvars
import logging
import re
import uuid
from contextlib import contextmanager
from typing import Iterator, Optional

log = logging.getLogger("potager")

# ─────────────────────────────────────────────────────────────────────────────
# Provenance [US-306 / CA1]
# ─────────────────────────────────────────────────────────────────────────────
PROVENANCE_USAGE      = "usage"
PROVENANCE_MESURE     = "mesure"
PROVENANCE_TEST       = "test"
PROVENANCE_FOND       = "fond"
PROVENANCE_HISTORIQUE = "historique"

#: Les valeurs qu'un code peut écrire. `historique` n'en fait pas partie [CA1].
PROVENANCES_ECRITES: frozenset[str] = frozenset({
    PROVENANCE_USAGE, PROVENANCE_MESURE, PROVENANCE_TEST, PROVENANCE_FOND,
})
#: Les valeurs que la contrainte de la colonne accepte.
PROVENANCES: frozenset[str] = PROVENANCES_ECRITES | {PROVENANCE_HISTORIQUE}

#: Type d'appel dont l'auteur n'est pas un jardinier même quand un `user_id` est
#: porté (rédaction d'un message spontané du compagnon) [US-306 / CA3].
_TYPES_DE_FOND = frozenset({"compagnon_signal"})


class ProvenanceInvalideError(ValueError):
    """Une provenance hors de `PROVENANCES_ECRITES` : défaut de programmation, jamais
    converti en repli — une ligne mal classée fausse durablement les séries."""


_provenance: "contextvars.ContextVar[Optional[str]]" = contextvars.ContextVar(
    "provenance_appel", default=None
)


def fixer_provenance(valeur: str) -> contextvars.Token:
    """[US-306 / CA2] Fixe la provenance de tous les appels du traitement en cours.

    Appelée UNE fois par le point d'entrée (`main()` d'un outil, harnais), jamais par
    un appelant métier. Retourne le jeton à passer à `reinitialiser_provenance`."""
    if valeur not in PROVENANCES_ECRITES:
        raise ProvenanceInvalideError(
            f"provenance invalide : {valeur!r} (attendu parmi {sorted(PROVENANCES_ECRITES)})"
        )
    return _provenance.set(valeur)


def reinitialiser_provenance(jeton: contextvars.Token) -> None:
    """Restaure la provenance d'avant `fixer_provenance`."""
    _provenance.reset(jeton)


@contextmanager
def provenance(valeur: str) -> Iterator[None]:
    """Fixe la provenance le temps d'un bloc (`with provenance("mesure"): …`)."""
    jeton = fixer_provenance(valeur)
    try:
        yield
    finally:
        reinitialiser_provenance(jeton)


def provenance_fixee() -> Optional[str]:
    """La provenance posée par le point d'entrée, ou `None` si aucune ne l'a été."""
    return _provenance.get()


def _en_mode_test() -> bool:
    """Le bot ou l'API tourne sur la base du mode test conversationnel [US-288]."""
    try:
        from app.services import mode_test
        return mode_test.actif()
    except Exception:  # noqa: BLE001 — jamais bloquer la mesure pour un défaut de configuration
        return False


def resoudre_provenance(appel_type: str, user_id: Optional[int]) -> str:
    """[US-306 / CA2, CA3, CA5] Provenance à écrire pour un appel.

    Ordre : la valeur posée par le point d'entrée ; sinon `test` si le processus
    tourne en mode test ; sinon `fond` pour un appel sans utilisateur (signal du
    compagnon, veilleur, bilan) ; sinon `usage` (bot, API)."""
    fixee = _provenance.get()
    if fixee is not None:
        return fixee
    if _en_mode_test():
        return PROVENANCE_TEST
    if user_id is None or appel_type in _TYPES_DE_FOND:
        return PROVENANCE_FOND
    return PROVENANCE_USAGE


# ─────────────────────────────────────────────────────────────────────────────
# Modèle simulé [US-306 / CA6]
# ─────────────────────────────────────────────────────────────────────────────
# Un appel dont le modèle est simulé (client factice, `unittest.mock`) n'a rien
# consommé : 0 jeton, 0 ms. Il ne doit pas laisser de ligne dans une base qui n'est
# pas celle d'une session de test. La passerelle détecte elle-même un client
# `unittest.mock` ; un outil dont la simulation est d'une autre nature le déclare ici.
_modele_simule: "contextvars.ContextVar[bool]" = contextvars.ContextVar(
    "modele_simule", default=False
)


@contextmanager
def modele_simule() -> Iterator[None]:
    """Déclare que les appels du bloc passent par un modèle simulé."""
    jeton = _modele_simule.set(True)
    try:
        yield
    finally:
        _modele_simule.reset(jeton)


def simulation_declaree() -> bool:
    return _modele_simule.get()


# ─────────────────────────────────────────────────────────────────────────────
# Canal [US-307 / CA1] — par où l'interaction est arrivée
# ─────────────────────────────────────────────────────────────────────────────
CANAL_TELEGRAM = "telegram"
CANAL_PWA      = "pwa"
CANAL_MCP      = "mcp"      # [US-290] un assistant IA externe, via le serveur MCP
CANAL_FOND     = "fond"     # tâche sans interaction (veilleur, bilan, purge)
CANAL_OUTIL    = "outil"    # un outil de `tools/`
CANAL_INCONNU  = "inconnu"

CANAUX: frozenset[str] = frozenset({
    CANAL_TELEGRAM, CANAL_PWA, CANAL_MCP, CANAL_FOND, CANAL_OUTIL, CANAL_INCONNU,
})

#: Le canal du traitement en cours : posé par le point d'entrée (le bot pour Telegram, le
#: middleware de l'API pour la PWA, le serveur MCP, un outil), lu par l'écriture des actions
#: menées [US-261] et par la passerelle [US-307]. Une `ContextVar`, comme le contexte de
#: tenant : elle suit la tâche asyncio ou la requête.
canal_courant: "contextvars.ContextVar[str]" = contextvars.ContextVar("canal_courant", default=CANAL_INCONNU)


def resoudre_canal(provenance_resolue: str) -> str:
    """[US-307 / CA1] Canal à écrire : celui du point d'entrée ; à défaut, `fond` pour un appel
    de fond (aucune interaction ne l'a déclenché), sinon `inconnu`."""
    canal = canal_courant.get()
    if canal != CANAL_INCONNU:
        return canal
    return CANAL_FOND if provenance_resolue == PROVENANCE_FOND else CANAL_INCONNU


# ─────────────────────────────────────────────────────────────────────────────
# Échange [US-307 / CA3, CA4]
# ─────────────────────────────────────────────────────────────────────────────
_FORMAT_ECHANGE = re.compile(r"^[0-9a-f]{32}$")

_echange_ref: "contextvars.ContextVar[Optional[str]]" = contextvars.ContextVar(
    "echange_ref", default=None
)


def nouvel_identifiant_echange() -> str:
    """Un identifiant d'échange : 32 caractères hexadécimaux, sans lien avec une personne."""
    return uuid.uuid4().hex


def identifiant_valide(ref: object) -> bool:
    return isinstance(ref, str) and bool(_FORMAT_ECHANGE.match(ref))


def ouvrir_echange() -> contextvars.Token:
    """[CA3] Ouvre un échange pour le traitement en cours (à l'entrée de l'interaction).
    Retourne le jeton à passer à `fermer_echange` quand l'appelant borne l'échange (MCP) ;
    un point d'entrée qui a sa propre tâche (Update, requête) n'a rien à restituer."""
    return _echange_ref.set(nouvel_identifiant_echange())


def fermer_echange(jeton: contextvars.Token) -> None:
    _echange_ref.reset(jeton)


def reprendre_echange(ref: Optional[str]) -> bool:
    """[CA3] Rattache le traitement en cours à un échange DÉJÀ ouvert : la lecture à voix haute
    d'une réponse, demandée dans une autre requête que la réponse elle-même, écrit ses lignes
    sous l'échange de cette réponse. Un identifiant absent ou mal formé est ignoré (l'échange
    courant reste en place) ; rend vrai si l'échange a été repris."""
    if not identifiant_valide(ref):
        return False
    _echange_ref.set(ref)
    return True


def echange_courant() -> Optional[str]:
    """L'échange ouvert pour le traitement en cours, ou `None` hors de toute interaction."""
    return _echange_ref.get()


def echange_a_ecrire() -> str:
    """[CA3, CA4] Identifiant à écrire sur une ligne : l'échange ouvert ; sans interaction (tâche
    de fond), un identifiant propre à cet appel."""
    return _echange_ref.get() or nouvel_identifiant_echange()


def demarrer_outil() -> None:
    """[US-306 / CA4, US-307 / CA4] À appeler une fois au début du `main()` d'un outil de `tools/`
    qui appelle un modèle : provenance « mesure », canal « outil », et UN identifiant pour toute
    l'exécution de l'outil."""
    fixer_provenance(PROVENANCE_MESURE)
    canal_courant.set(CANAL_OUTIL)
    ouvrir_echange()

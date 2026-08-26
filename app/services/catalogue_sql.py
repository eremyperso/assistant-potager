"""
app/services/catalogue_sql.py — Garde-fous d'exécution des agrégations [US-096]
================================================================================
Ce module ne calcule rien : il **contraint** la façon dont les agrégations de
l'étage 1 (réponses chiffrées, `app/services/reponses_chiffrees.py`) sont
exécutées. Il porte à lui seul les quatre invariants de sécurité de l'US, et
c'est volontairement le seul endroit où ils sont écrits :

- **CA9 — pas de SQL libre.** Seule une agrégation *enregistrée* dans le
  catalogue peut être exécutée (`enregistrer()` / `executer()`). Le nom de
  l'agrégation vient d'un aiguillage par règles, jamais d'un modèle : un modèle
  ne peut donc ni composer une requête, ni en désigner une qui n'existe pas.
  Il n'y a par construction aucun chemin où une chaîne SQL produite ailleurs
  arriverait jusqu'au moteur.
- **CA10 — lecture seule + délai maximal.** Chaque instruction émise pendant
  une agrégation est inspectée : tout ce qui n'est pas une lecture est refusé
  (`EcritureInterditeError`), et le budget de temps est vérifié à chaque
  instruction (`DelaiRequeteDepasseError`). Sur PostgreSQL, un
  `statement_timeout` est en plus armé côté serveur — la vérification Python
  seule ne pourrait pas interrompre une requête déjà partie.
- **CA11 — `potager_id` par construction.** Toute instruction qui lit une table
  porteuse de données de potager doit mentionner `potager_id`. Une agrégation
  qui « oublierait » le filtre est refusée **à l'exécution**
  (`RequeteNonIsoleeError`), pas signalée en revue de code. C'est la différence
  entre une isolation démontrable et une isolation probable.

Le contrôle est branché sur le `bind` de la session le temps de l'agrégation,
puis retiré : il ne pèse sur aucun autre appel de l'application.
"""
from __future__ import annotations

import logging
import re
import time
from contextlib import contextmanager
from typing import Callable, Iterator

from sqlalchemy import event, text
from sqlalchemy.orm import Session

from app.services.context import TenantContext

log = logging.getLogger("potager")

# [CA10] Budget d'exécution d'une agrégation du catalogue, bornes comprises.
DELAI_MAX_MS = 2000

# [CA11] Tables porteuses de données propres à un potager. Une lecture sur
# l'une d'elles sans `potager_id` dans l'instruction est un défaut d'isolation.
TABLES_TENANT: frozenset[str] = frozenset({"evenements", "parcelles", "culture_config"})

# Verbes de lecture tolérés — tout le reste est une écriture (CA10). `SET`,
# `BEGIN`, `COMMIT`, `ROLLBACK`, `SAVEPOINT`, `RELEASE` et `PRAGMA` sont de la
# plomberie de transaction émise par SQLAlchemy lui-même, pas de la donnée.
_VERBES_LECTURE: frozenset[str] = frozenset({
    "select", "with", "show", "explain", "pragma",
    "set", "begin", "commit", "rollback", "savepoint", "release",
})

# Un `potager_id` présent dans la LISTE des colonnes sélectionnées ne prouve
# rien : c'est un filtre qu'on exige. Le motif ne reconnaît donc `potager_id`
# que suivi d'une comparaison (`= ?`, `IN (...)`, `IS NULL`).
_FILTRE_TENANT = re.compile(
    r"\bpotager_id\s*(?:=|<>|!=|\bin\b|\bis\b)", re.IGNORECASE,
)

_TABLE_LUE = re.compile(
    r"\b(?:from|join)\s+[\"`\[]?(" + "|".join(sorted(TABLES_TENANT)) + r")\b",
    re.IGNORECASE,
)


class GardeCatalogueError(RuntimeError):
    """Racine des refus d'exécution — jamais rattrapée silencieusement."""


class RequeteHorsCatalogueError(GardeCatalogueError):
    """[CA9] Agrégation demandée par un nom absent du catalogue."""


class EcritureInterditeError(GardeCatalogueError):
    """[CA10] Instruction autre qu'une lecture émise pendant une agrégation."""


class RequeteNonIsoleeError(GardeCatalogueError):
    """[CA11] Lecture d'une table de potager sans filtre `potager_id`."""


class DelaiRequeteDepasseError(GardeCatalogueError):
    """[CA10] Budget de temps dépassé pendant une agrégation."""


# ─────────────────────────────────────────────────────────────────────────────
# Le catalogue — CA9
# ─────────────────────────────────────────────────────────────────────────────
_CATALOGUE: dict[str, Callable] = {}


def enregistrer(nom: str) -> Callable:
    """Déclare une agrégation comme membre du catalogue. Décorateur volontairement
    minimal : le catalogue doit rester lisible d'un coup d'œil (note technique
    de l'US), une famille de question = une fonction = un gabarit."""

    def _decorateur(fonction: Callable) -> Callable:
        if nom in _CATALOGUE:
            raise ValueError(f"Agrégation '{nom}' déjà enregistrée au catalogue")
        _CATALOGUE[nom] = fonction
        return fonction

    return _decorateur


def noms_catalogue() -> tuple[str, ...]:
    """Noms des agrégations exécutables — la liste exhaustive, sans exception."""
    return tuple(sorted(_CATALOGUE))


# ─────────────────────────────────────────────────────────────────────────────
# Le garde d'exécution — CA10, CA11
# ─────────────────────────────────────────────────────────────────────────────
def _premier_verbe(instruction: str) -> str:
    depouillee = instruction.lstrip().lstrip("(").lstrip()
    return depouillee.split(None, 1)[0].lower() if depouillee else ""


def _controler_instruction(instruction: str) -> None:
    """[CA10, CA11] Refuse une instruction d'écriture ou non isolée."""
    verbe = _premier_verbe(instruction)
    if verbe not in _VERBES_LECTURE:
        raise EcritureInterditeError(
            f"Instruction '{verbe.upper()}' interdite : l'étage des réponses chiffrées est en lecture seule"
        )
    if verbe in ("select", "with"):
        table = _TABLE_LUE.search(instruction)
        if table and not _FILTRE_TENANT.search(instruction):
            raise RequeteNonIsoleeError(
                f"Lecture de '{table.group(1)}' sans filtre potager_id — requête refusée à l'exécution"
            )


@contextmanager
def garde_lecture_seule(db: Session, budget_ms: int = DELAI_MAX_MS) -> Iterator[None]:
    """[CA10, CA11] Arme les contrôles pour la durée du bloc, sur le moteur
    réellement utilisé par `db` (celui des tests comme celui de production)."""
    bind = db.get_bind()
    debut = time.monotonic()

    # Le `statement_timeout` PostgreSQL est armé AVANT le branchement du
    # contrôle : c'est le seul ordre qui n'a pas à être lui-même contrôlé.
    if bind.dialect.name == "postgresql":
        db.execute(text(f"SET LOCAL statement_timeout = {int(budget_ms)}"))

    def _avant_execution(conn, cursor, instruction, parametres, contexte, executemany):
        _controler_instruction(instruction)
        ecoule_ms = (time.monotonic() - debut) * 1000
        if ecoule_ms > budget_ms:
            raise DelaiRequeteDepasseError(
                f"Agrégation interrompue après {ecoule_ms:.0f} ms (budget {budget_ms} ms)"
            )

    event.listen(bind, "before_cursor_execute", _avant_execution)
    try:
        yield
    finally:
        event.remove(bind, "before_cursor_execute", _avant_execution)


def executer(nom: str, db: Session, ctx: TenantContext, **parametres):
    """[CA9, CA10, CA11] Exécute une agrégation du catalogue, et rien d'autre.

    `ctx.potager_id` est obligatoire : sans tenant courant, aucune agrégation
    n'a de sens et aucune ne serait isolable — le refus est immédiat, avant même
    d'atteindre la base.
    """
    fonction = _CATALOGUE.get(nom)
    if fonction is None:
        raise RequeteHorsCatalogueError(
            f"Agrégation '{nom}' absente du catalogue — aucune requête composée librement n'est exécutable"
        )
    if ctx is None or ctx.potager_id is None:
        raise RequeteNonIsoleeError("Aucun potager courant : agrégation refusée")

    with garde_lecture_seule(db):
        return fonction(db, ctx, **parametres)


def catalogue_pour_tests() -> dict[str, Callable]:
    """Vue du catalogue réservée aux tests d'invariants — jamais utilisée par le code applicatif."""
    return dict(_CATALOGUE)


def journaliser_refus(erreur: Exception, question: str) -> None:
    """Trace structurée d'un refus de garde — un refus est un événement de
    sécurité, il ne doit jamais disparaître dans un `except` muet."""
    log.warning(
        "⛔ CATALOGUE SQL   │ %s │ %s │ '%s'",
        type(erreur).__name__, erreur, (question or "")[:80],
    )

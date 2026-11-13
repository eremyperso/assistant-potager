"""
app/services/compagnon/conversations.py — La mémoire courte du compagnon [US-259]
==================================================================================
Les derniers échanges entre le jardinier et le compagnon, en base, communs à
Telegram et à la PWA (CA1). Ils remplacent les échanges que le contexte court
d'US-238 gardait en mémoire du bot, et les `_sessions` que l'API écrivait sans
jamais les relire (CA7).

Trois bornes :

* **par jardinier ET par potager** — deux membres d'un même potager ne partagent
  rien, et un même jardinier a une conversation par potager ;
* **30 minutes glissantes** — la conversation vit tant qu'on lui parle : chaque
  échange repousse l'échéance. Un silence de plus d'une demi-heure la clôt, et la
  suivante repart de zéro ;
* **les 10 derniers échanges**, purgés à 30 jours.

Rien ici ne lève : une mémoire indisponible prive l'agent de contexte, elle ne
prive jamais le jardinier de sa réponse.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator, Optional

from sqlalchemy.orm import Session

from app.services.agent.contexte_court import Echange
from app.services.context import TenantContext
from database.db import SessionLocal, tenant_scope
from database.models import EchangeConversation, Potager

log = logging.getLogger("potager")

#: [CA1] Les 10 derniers échanges…
NB_ECHANGES = 10
#: … sur 30 minutes glissantes…
FENETRE = timedelta(minutes=30)
#: … purgés à 30 jours.
RETENTION_JOURS = 30


@contextmanager
def _session(potager_id: int) -> Iterator[Session]:
    """RLS stricte : un échange s'écrit et se lit dans le potager où il a eu lieu."""
    with tenant_scope(potager_id):
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()


def noter(
    ctx: TenantContext, texte_jardinier: str, texte_compagnon: str, *, canal: str,
    outils: tuple[str, ...] = (), proposition_id: Optional[int] = None,
    signal: Optional[str] = None, maintenant: Optional[datetime] = None,
    question: Optional[dict] = None, contexte: Optional[dict] = None,
) -> None:
    """[CA1] Retient un échange : ce qu'a dit le jardinier, ce que le compagnon en a fait.

    [US-284 / CA1] `question` : la question que le compagnon vient de poser pour faire ce que la
    phrase demandait. Un échange sans question efface, de fait, la précédente (`recents` ne lit
    que celle du dernier échange).

    [US-323 / CA6] `contexte` : ce que le jardinier avait sous les yeux dans la PWA (identifiants
    et noms), pour mesurer l'effet du contexte d'écran sur l'interprétation."""
    try:
        with _session(ctx.potager_id) as db:
            db.add(EchangeConversation(
                user_id=ctx.user_id, potager_id=ctx.potager_id, canal=canal,
                texte_jardinier=texte_jardinier or "", texte_compagnon=texte_compagnon or "",
                outils=list(outils) or None, proposition_id=proposition_id, signal=signal,
                question=question or None, contexte=contexte or None, cree_le=maintenant or datetime.utcnow(),
            ))
            db.commit()
    except Exception:  # noqa: BLE001 — la mémoire ne casse jamais la réponse
        log.exception("[US-259 / CA1] Échange non retenu (user_id=%s potager_id=%s)",
                      ctx.user_id, ctx.potager_id)


def _ts(instant: datetime) -> float:
    return instant.replace(tzinfo=timezone.utc).timestamp()


def recents(ctx: TenantContext, maintenant: Optional[datetime] = None) -> tuple[Echange, ...]:
    """[CA1] La conversation en cours : au plus 10 échanges, du plus ancien au plus récent.

    Glissante : on remonte depuis le dernier échange tant que deux échanges
    successifs sont à moins de 30 minutes l'un de l'autre. Un dernier échange
    vieux de plus de 30 minutes : la conversation est close, rien n'est rendu.
    """
    return tuple(echange for _, echange in recents_avec_id(ctx, maintenant))


def recents_avec_id(ctx: TenantContext, maintenant: Optional[datetime] = None) -> tuple[tuple[int, Echange], ...]:
    """[US-303 / CA8] `recents`, chaque échange accompagné de son identifiant : la PWA en a besoin
    pour demander la lecture d'une réponse ancienne."""
    instant = maintenant or datetime.utcnow()
    try:
        with _session(ctx.potager_id) as db:
            lignes = (
                db.query(EchangeConversation)
                .filter(
                    EchangeConversation.user_id == ctx.user_id,
                    EchangeConversation.potager_id == ctx.potager_id,
                    EchangeConversation.cree_le <= instant,
                )
                .order_by(EchangeConversation.cree_le.desc(), EchangeConversation.id.desc())
                .limit(NB_ECHANGES)
                .all()
            )
    except Exception:  # noqa: BLE001
        log.exception("[US-259 / CA1] Échanges illisibles (user_id=%s potager_id=%s)",
                      ctx.user_id, ctx.potager_id)
        return ()

    retenus: list[EchangeConversation] = []
    suivant = instant
    for ligne in lignes:
        if suivant - ligne.cree_le > FENETRE:
            break
        retenus.append(ligne)
        suivant = ligne.cree_le
    return tuple(
        (ligne.id, Echange(ligne.texte_jardinier, ligne.texte_compagnon, _ts(ligne.cree_le), ligne.question or None))
        for ligne in reversed(retenus)
    )


def dernier_id(ctx: TenantContext) -> Optional[int]:
    """[US-303 / CA8] L'identifiant du dernier échange du jardinier dans ce potager ; None s'il n'y
    en a aucun ou si la mémoire est illisible."""
    try:
        with _session(ctx.potager_id) as db:
            ligne = (
                db.query(EchangeConversation.id)
                .filter(EchangeConversation.user_id == ctx.user_id,
                        EchangeConversation.potager_id == ctx.potager_id)
                .order_by(EchangeConversation.id.desc())
                .first()
            )
        return ligne[0] if ligne else None
    except Exception:  # noqa: BLE001 — la mémoire ne casse jamais la réponse
        log.exception("[US-303 / CA8] Dernier échange illisible (user_id=%s potager_id=%s)",
                      ctx.user_id, ctx.potager_id)
        return None


def lire(ctx: TenantContext, echange_id: int) -> Optional[EchangeConversation]:
    """[US-303 / CA8] Un échange du jardinier dans ce potager, détaché de sa session ; None pour un
    échange d'un autre jardinier ou d'un autre potager (la PWA répond 404)."""
    with _session(ctx.potager_id) as db:
        ligne = (
            db.query(EchangeConversation)
            .filter(EchangeConversation.id == echange_id,
                    EchangeConversation.user_id == ctx.user_id,
                    EchangeConversation.potager_id == ctx.potager_id)
            .first()
        )
        if ligne is not None:
            db.expunge(ligne)
        return ligne


def retenir_texte_oral(ctx: TenantContext, echange_id: int, texte_oral: str) -> None:
    """[US-303 / CA7] Garde le résumé parlé sur l'échange : une seconde lecture le reprend tel quel."""
    with _session(ctx.potager_id) as db:
        (
            db.query(EchangeConversation)
            .filter(EchangeConversation.id == echange_id,
                    EchangeConversation.user_id == ctx.user_id,
                    EchangeConversation.potager_id == ctx.potager_id)
            .update({EchangeConversation.texte_oral: texte_oral}, synchronize_session=False)
        )
        db.commit()


def clore_question(ctx: TenantContext) -> None:
    """[US-284 / CA4] Efface la question en attente : une phrase l'a lue sans laisser d'échange
    (rien compris), elle ne doit pas attendre la suivante."""
    try:
        with _session(ctx.potager_id) as db:
            nb = (
                db.query(EchangeConversation)
                .filter(
                    EchangeConversation.user_id == ctx.user_id,
                    EchangeConversation.potager_id == ctx.potager_id,
                    EchangeConversation.question.isnot(None),
                )
                .update({EchangeConversation.question: None}, synchronize_session=False)
            )
            db.commit()
        if nb:
            log.info("[US-284 / CA4] Question en attente effacée (user_id=%s potager_id=%s)",
                     ctx.user_id, ctx.potager_id)
    except Exception:  # noqa: BLE001 — la mémoire ne casse jamais la réponse
        log.exception("[US-284 / CA4] Question en attente non effacée (user_id=%s potager_id=%s)",
                      ctx.user_id, ctx.potager_id)


def purger(maintenant: Optional[datetime] = None) -> int:
    """[CA1] Efface les échanges de plus de 30 jours, potager par potager.

    La RLS de la table est stricte : sans potager armé, rien ne se lit ni ne
    s'efface. Le balayage passe donc chaque potager sous son propre GUC, comme
    `potagers.purger_potagers_supprimes`.
    """
    limite = (maintenant or datetime.utcnow()) - timedelta(days=RETENTION_JOURS)
    with tenant_scope(None):
        db = SessionLocal()
        try:
            potagers = [ligne[0] for ligne in db.query(Potager.id).all()]
        finally:
            db.close()
    total = 0
    for potager_id in potagers:
        with _session(potager_id) as db:
            nb = (
                db.query(EchangeConversation)
                .filter(EchangeConversation.potager_id == potager_id,
                        EchangeConversation.cree_le < limite)
                .delete(synchronize_session=False)
            )
            db.commit()
            total += nb
    if total:
        log.info("[US-259 / CA1] %s échange(s) de conversation effacé(s) après %s jours",
                 total, RETENTION_JOURS)
    return total

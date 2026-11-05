"""
app/services/compagnon/file_agent.py — La file de gestes vue par l'agent [US-286]
===============================================================================
Deux choses, et seulement elles :

* **la mémoire** — un message que le bot envoie de lui-même à propos de la file
  (invitation, relance, avertissement, purge) entre dans la conversation, comme
  les messages spontanés d'US-267. Sans elle, « vide le geste » juste après une
  purge n'avait aucun sens pour l'agent, qui le prenait pour une entrée du carnet ;
* **la lecture** — les gestes qui attendent encore, et l'abandon d'un geste de
  la file, que le jardinier confirme au bouton.

Rien ici ne lève pour la mémoire : un message non retenu prive l'agent de contexte,
il ne fait jamais échouer l'envoi.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from app.services import file_gestes as svc_file
from app.services.context import TenantContext
from database.models import Proposition

log = logging.getLogger("potager")

#: [CA1] Les signaux notés dans `echanges_conversation.signal`.
SIGNAL_INVITATION = "file:invitation"
SIGNAL_RELANCE = "file:relance"
SIGNAL_AVERTISSEMENT = "file:avertissement"
SIGNAL_PURGE = "file:purge"

#: Le texte rendu à l'agent quand rien n'attend : il le redit tel quel au jardinier.
TEXTE_FILE_VIDE = "Aucun geste n'attend dans ta file."

_ECHAPPEMENT_MARKDOWN = re.compile(r"\\([_*\[\]()~`>#+\-=|{}.!\\])")


def en_clair(texte: str) -> str:
    """Le message Telegram sans sa mise en forme Markdown : l'agent le relit comme du texte."""
    return _ECHAPPEMENT_MARKDOWN.sub(r"\1", texte or "").replace("*", "").strip()


def noter_envoi(user_id: int, gestes: list[Proposition], texte: str, signal: str) -> None:
    """[CA1] Le message envoyé entre dans la conversation du jardinier, potager par potager.

    La file est celle d'un COMPTE (elle peut couvrir plusieurs potagers) mais la
    conversation, elle, est par potager : le message est retenu dans celui de chacun
    des gestes qu'il nomme.
    """
    try:
        from app.services.compagnon import conversations
        from app.services.compagnon.propositions import CANAL_TELEGRAM

        potagers = sorted({geste.potager_id for geste in gestes if geste.potager_id is not None})
        for potager_id in potagers:
            conversations.noter(
                TenantContext(user_id=user_id, potager_id=potager_id), "", en_clair(texte),
                canal=CANAL_TELEGRAM, signal=signal,
            )
    except Exception:  # noqa: BLE001 — la mémoire ne casse jamais l'envoi
        log.exception("[US-286 / CA1] Message de la file non retenu (user_id=%s, %s)", user_id, signal)


def _en_donnees(geste: Proposition) -> dict:
    item = geste.contenu or {}
    donnee = {"id": geste.code, "geste": en_clair(svc_file.libelle_court(geste))}
    for cle in ("action", "culture", "parcelle", "date"):
        if item.get(cle):
            donnee[cle] = item[cle]
    return donnee


def lister(ctx: TenantContext) -> list[dict]:
    """[CA2] Les gestes qui attendent ce jardinier, tous potagers confondus (la file est celle du compte)."""
    if ctx.user_id is None:
        return []
    with svc_file.lecture_hors_tenant() as db:
        return [_en_donnees(geste) for geste in svc_file.lister_en_attente(db, ctx.user_id)]


def existe(user_id: Optional[int], code: str) -> bool:
    """[CA4] Ce code désigne-t-il un geste en attente de CE jardinier ?"""
    if user_id is None or not code:
        return False
    with svc_file.lecture_hors_tenant() as db:
        return any(geste.code == code for geste in svc_file.lister_en_attente(db, user_id))


def a_des_gestes(user_id: Optional[int]) -> bool:
    """[CA2] La file n'est-elle pas vide ? Décide si l'agent se voit offrir l'abandon d'un geste."""
    if user_id is None:
        return False
    try:
        with svc_file.lecture_hors_tenant() as db:
            return svc_file.compter_en_attente(db, user_id) > 0
    except Exception:  # noqa: BLE001 — une file illisible ne prive pas le jardinier de sa réponse
        log.exception("[US-286 / CA2] File de gestes illisible (user_id=%s)", user_id)
        return False


def libelle(user_id: int, code: str) -> Optional[str]:
    """[CA4] Le libellé en clair du geste en attente désigné par ce code, ou None."""
    with svc_file.lecture_hors_tenant() as db:
        for geste in svc_file.lister_en_attente(db, user_id):
            if geste.code == code:
                return en_clair(svc_file.libelle_court(geste))
    return None


def abandonner(user_id: int, geste_id: int) -> Optional[str]:
    """[CA4] Le jardinier a confirmé au bouton : le geste quitte la file, et son libellé est rendu.

    None : ce geste n'est plus en attente (traité entre-temps, ou jamais le sien) — rien n'est fait.
    """
    with svc_file.lecture_hors_tenant() as db:
        geste = next((g for g in svc_file.lister_en_attente(db, user_id) if g.id == geste_id), None)
        if geste is None:
            return None
        texte = en_clair(svc_file.libelle_court(geste))
        db.expunge(geste)
    if not svc_file.abandonner(geste):
        return None
    log.info("[US-286 / CA4] Geste de la file abandonné à la demande du jardinier : id=%s", geste_id)
    return texte


def id_par_code(user_id: int, code: str) -> Optional[int]:
    """L'identifiant du geste en attente que ce code désigne (celui que porte le bouton)."""
    with svc_file.lecture_hors_tenant() as db:
        for geste in svc_file.lister_en_attente(db, user_id):
            if geste.code == code:
                return geste.id
    return None

"""
app/services/compagnon/signaux.py — Les signaux du veilleur, en base [US-266]
==========================================================================
Ce que le veilleur a détecté reste en base 30 jours, avec son sort. Un même fait
ne produit qu'un signal par potager (CA3) : la clé unique est vérifiée avant
l'écriture, et la contrainte `uq_signaux_potager_cle` le garantit si deux passages
se croisaient.

RLS stricte (migration_v65) : un signal s'écrit et se lit dans le potager où il
a été détecté. Rien n'est envoyé ici : le distributeur d'US-267 lira les signaux
`detecte` et les fera avancer.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Iterable, Iterator, Optional

import pytz
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.services.compagnon.veilleur import Signal
from database.db import SessionLocal, tenant_scope
from database.models import EnvoiSignal, MessageSpontane, Potager, Rappel, SignalVeilleur

log = logging.getLogger("potager")

ETAT_DETECTE = "detecte"
ETAT_ENVOYE = "envoye"
ETAT_REGROUPE = "regroupe"
ETAT_IGNORE = "ignore"
ETAT_REPONDU = "repondu"

RAPPEL_PROGRAMME = "programme"

#: Signaux et rappels sont un journal d'initiative, pas un historique : 30 jours.
RETENTION_JOURS = 30

FUSEAU = pytz.timezone("Europe/Paris")


@contextmanager
def _session(potager_id: int) -> Iterator[Session]:
    """RLS stricte : un signal s'écrit et se lit dans le potager où il a été détecté."""
    with tenant_scope(potager_id):
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()


def _ligne(potager_id: int, signal: Signal, maintenant: datetime) -> SignalVeilleur:
    return SignalVeilleur(
        potager_id=potager_id, theme=signal.theme, cle_unique=signal.cle_unique[:160],
        priorite=signal.priorite, expire_le=signal.expire_le, donnees=signal.donnees,
        etat=ETAT_DETECTE, detecte_le=maintenant,
    )


def enregistrer(potager_id: int, signaux: Iterable[Signal], maintenant: datetime) -> list[str]:
    """[CA3] Écrit les signaux dont le fait est nouveau ; rend les clés effectivement créées.

    Un signal déjà en base pour ce potager (même `cle_unique`) n'est pas réécrit, même
    si ses données ont changé : c'est le même fait. Chaque création est journalisée,
    pour qu'on puisse suivre le veilleur avant qu'il ne parle (US-267).
    """
    candidats: dict[str, Signal] = {}
    for signal in signaux:
        candidats.setdefault(signal.cle_unique[:160], signal)
    if not candidats:
        return []
    with _session(potager_id) as db:
        deja = {
            cle for (cle,) in db.query(SignalVeilleur.cle_unique).filter(
                SignalVeilleur.potager_id == potager_id,
                SignalVeilleur.cle_unique.in_(list(candidats)),
            )
        }
        nouveaux = [(cle, s) for cle, s in candidats.items() if cle not in deja]
        crees: list[str] = []
        try:
            db.add_all([_ligne(potager_id, s, maintenant) for _, s in nouveaux])
            db.commit()
            crees = [cle for cle, _ in nouveaux]
        except IntegrityError:
            # Un autre passage a écrit l'un de ces faits entre-temps : un par un.
            db.rollback()
            for cle, signal in nouveaux:
                try:
                    db.add(_ligne(potager_id, signal, maintenant))
                    db.commit()
                    crees.append(cle)
                except IntegrityError:
                    db.rollback()
    for cle in crees:
        signal = candidats[cle]
        log.info("[US-266] 🔔 Signal détecté : %s · %s · %s · expire %s (potager %s)",
                 signal.theme, cle, signal.priorite, signal.expire_le.isoformat(timespec="minutes"),
                 potager_id)
    return crees


def lister(potager_id: int, etat: Optional[str] = None) -> list[SignalVeilleur]:
    """Les signaux d'un potager, du plus récent au plus ancien (détachés de la session)."""
    with _session(potager_id) as db:
        requete = db.query(SignalVeilleur).filter(SignalVeilleur.potager_id == potager_id)
        if etat is not None:
            requete = requete.filter(SignalVeilleur.etat == etat)
        lignes = requete.order_by(SignalVeilleur.detecte_le.desc(), SignalVeilleur.id.desc()).all()
        db.expunge_all()
        return lignes


def purger(maintenant: Optional[datetime] = None) -> int:
    """Efface, potager par potager (RLS stricte), les signaux de plus de 30 jours et les
    rappels échus depuis plus de 30 jours. Un rappel encore programmé n'est jamais effacé."""
    # Les horodatages sont en heure de Paris (`veilleur_passage.maintenant_local`) : la
    # limite aussi, quel que soit le fuseau du serveur.
    limite = (maintenant or datetime.now(FUSEAU).replace(tzinfo=None)) - timedelta(days=RETENTION_JOURS)
    with tenant_scope(None):
        db = SessionLocal()
        try:
            potagers = [ligne[0] for ligne in db.query(Potager.id).all()]
        finally:
            db.close()
    total = 0
    for potager_id in potagers:
        with _session(potager_id) as db:
            # [US-267] Le sort des signaux par jardinier et les messages partis suivent les
            # signaux : un message est toujours plus jeune que les signaux qu'il porte.
            anciens = db.query(SignalVeilleur.id).filter(
                SignalVeilleur.potager_id == potager_id, SignalVeilleur.detecte_le < limite)
            (db.query(EnvoiSignal)
             .filter(EnvoiSignal.potager_id == potager_id, EnvoiSignal.signal_id.in_(anciens.subquery()))
             .delete(synchronize_session=False))
            (db.query(MessageSpontane)
             .filter(MessageSpontane.potager_id == potager_id, MessageSpontane.envoye_le < limite)
             .delete(synchronize_session=False))
            total += (
                db.query(SignalVeilleur)
                .filter(SignalVeilleur.potager_id == potager_id, SignalVeilleur.detecte_le < limite)
                .delete(synchronize_session=False)
            )
            total += (
                db.query(Rappel)
                .filter(
                    Rappel.potager_id == potager_id, Rappel.etat != RAPPEL_PROGRAMME,
                    Rappel.echeance_le < limite,
                )
                .delete(synchronize_session=False)
            )
            db.commit()
    if total:
        log.info("[US-266] %s signal(s) et rappel(s) effacé(s) après %s jours", total, RETENTION_JOURS)
    return total

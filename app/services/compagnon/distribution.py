"""
app/services/compagnon/distribution.py — Faire partir les signaux, et lire leur réponse [US-267]
==============================================================================================
Le passage du distributeur, potager par potager, sous `tenant_scope` (RLS stricte) :

1. **Planifier** : chaque signal `detecte` est pris de façon ATOMIQUE (`detecte` →
   `planifie`, un seul passage gagne) ; pour chaque jardinier du potager, les règles pures
   de `distributeur` décident du mode et de l'heure. Une ligne `envois_signaux` par
   jardinier (UNIQUE `(signal_id, user_id)`).
2. **Envoyer** : les envois dus d'un jardinier sont pris de façon atomique (`en_attente` →
   `envoye`), regroupés en UN message, rédigés (`redaction_signal`) et postés dans
   Telegram. L'identifiant du message est gardé (F2). Telegram refuse : les envois
   reviennent en attente.

Seul le planificateur du bot appelle ce passage (CA11) ; l'API ne distribue jamais. Tout
s'éteint avec `COMPAGNON_PROACTIF` : le veilleur détecte toujours, rien ne part.

La réponse (CA5, CA8) : le message spontané du jardinier encore « en cours » (douze heures
sans réponse, puis trente minutes de conversation après la première), et la réaction qui
remet le compteur de la bascule à zéro.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Iterator, Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import config
from app.services import profil_echange
from app.services import telegram_notify
from app.services.compagnon import conversations
from app.services.compagnon import distributeur as regles
from app.services.compagnon import propositions as svc_propositions
from app.services.compagnon import redaction_signal as redaction
from app.services.compagnon import reponse_signal
from app.services.compagnon import signaux as svc_signaux
from app.services.compagnon import veilleur_passage
from app.services.compagnon.redaction_signal import SignalARediger
from app.services.context import TenantContext
from database.db import SessionLocal, tenant_scope
from database.models import EnvoiSignal, MessageSpontane, PotagerMembre, SignalVeilleur, User

log = logging.getLogger("potager")

#: Ceux qui jardinent reçoivent les messages ; un lecteur ne pourrait rien confirmer.
ROLES_DESTINATAIRES: tuple[str, ...] = ("owner", "editor")
GENRE_SIGNAL = "signal"
GENRE_RESUME = "resume"
SIGNAL_PLANIFIE = "planifie"
#: [US-272 / CA9] Plus utilisé : sans Telegram, le message va au panneau. Gardé pour les lignes anciennes.
MOTIF_SANS_TELEGRAM = "sans_telegram"
MOTIF_PLUS_MEMBRE = "plus_membre"
#: [CA8] Un message spontané attend sa réponse douze heures…
FENETRE_REPONSE = timedelta(hours=12)
#: … puis, une fois la réponse venue, la conversation dure comme une autre (30 minutes).
FENETRE_SUITE = conversations.FENETRE
#: [CA5] Les derniers messages regardés pour compter ceux d'un thème restés sans réaction.
NB_MESSAGES_REGARDES = 20

#: `(chat_id, texte, boutons) → message_id | None` — `telegram_notify.envoyer` en production.
Envoyeur = Callable[..., Optional[int]]


def actif() -> bool:
    """[CA11] `COMPAGNON_PROACTIF=oui` : le distributeur fait partir les messages."""
    return bool(config.COMPAGNON_PROACTIF)


@contextmanager
def _session(potager_id: int) -> Iterator[Session]:
    """RLS stricte : signaux, envois et messages se lisent dans le potager où ils sont nés."""
    with tenant_scope(potager_id):
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()


# ═════════════════════════════════════════════════════════════════════════════
# Les destinataires et leurs réglages (profil, partie 3)
# ═════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Destinataire:
    user_id: int
    chat_id: Optional[int]
    reglages: regles.Reglages
    prenom: Optional[str] = None
    registre: str = profil_echange.REGISTRE_DEFAUT


def reglages_du_membre(membre: PotagerMembre) -> regles.Reglages:
    return regles.reglages_depuis(
        membre.proactivite_compagnon, membre.silence_debut, membre.silence_fin, membre.heure_resume,
    )


def destinataires(db: Session, potager_id: int) -> list[Destinataire]:
    lignes = (
        db.query(PotagerMembre, User.telegram_chat_id)
        .join(User, User.id == PotagerMembre.user_id)
        .filter(PotagerMembre.potager_id == potager_id, PotagerMembre.role.in_(ROLES_DESTINATAIRES))
        .order_by(PotagerMembre.user_id)
        .all()
    )
    return [
        Destinataire(membre.user_id, chat_id, reglages_du_membre(membre), membre.prenom_compagnon,
                     membre.registre_compagnon or profil_echange.REGISTRE_DEFAUT)
        for membre, chat_id in lignes
    ]


def _reactions_du_theme(
    db: Session, potager_id: int, user_id: int, theme: str, depuis: Optional[datetime],
) -> list[Optional[datetime]]:
    """[CA5] La réaction aux derniers messages de ce thème, du plus récent au plus ancien.
    Seuls comptent les messages envoyés depuis le dernier changement de mode du thème."""
    messages = (
        db.query(MessageSpontane)
        .filter(MessageSpontane.potager_id == potager_id, MessageSpontane.user_id == user_id,
                MessageSpontane.genre == GENRE_SIGNAL)
        .order_by(MessageSpontane.envoye_le.desc(), MessageSpontane.id.desc())
        .limit(NB_MESSAGES_REGARDES)
        .all()
    )
    return [
        m.reaction_le for m in messages
        if theme in (m.themes or []) and (depuis is None or m.envoye_le >= depuis)
    ]


def _basculer(db: Session, potager_id: int, user_id: int, theme: str, maintenant: datetime) -> regles.Reglages:
    """[CA5] Le thème passe au point du matin : le distributeur l'écrit lui-même, et le message
    qui portera le signal le dira au jardinier, qui peut revenir en arrière par /profil."""
    membre = (db.query(PotagerMembre)
              .filter(PotagerMembre.user_id == user_id, PotagerMembre.potager_id == potager_id).first())
    membre.proactivite_compagnon = regles.proactivite_avec(
        membre.proactivite_compagnon, theme, regles.MODE_RESUME, maintenant, auto=True)
    log.info("[US-267 / CA5] Thème %s → point du matin après %s messages sans réaction (user %s, potager %s)",
             theme, regles.NB_SANS_REACTION, user_id, potager_id)
    return reglages_du_membre(membre)


# ═════════════════════════════════════════════════════════════════════════════
# 1. Planifier
# ═════════════════════════════════════════════════════════════════════════════
def _envoi(potager_id: int, signal_id: int, user_id: int, decision: regles.Decision,
           maintenant: datetime) -> EnvoiSignal:
    return EnvoiSignal(
        potager_id=potager_id, signal_id=signal_id, user_id=user_id, mode=decision.mode,
        etat=decision.etat, envoyer_le=decision.envoyer_le, motif=decision.motif,
        annonce_bascule=decision.annonce_bascule,
        traite_le=maintenant if decision.etat == regles.ETAT_IGNORE else None,
    )


def planifier_potager(potager_id: int, maintenant: datetime) -> int:
    """[CA1 → CA5, CA11] Décide du sort des signaux `detecte` ; rend le nombre de signaux pris."""
    with _session(potager_id) as db:
        ids = [i for (i,) in db.query(SignalVeilleur.id)
               .filter(SignalVeilleur.potager_id == potager_id, SignalVeilleur.etat == svc_signaux.ETAT_DETECTE)
               .order_by(SignalVeilleur.detecte_le, SignalVeilleur.id)]
        if not ids:
            return 0
        vises = destinataires(db, potager_id)
        reglages = {d.user_id: d.reglages for d in vises}
        pris_total = 0
        for signal_id in ids:
            # [CA11] Consommation atomique : un seul passage fait avancer un signal.
            pris = (db.query(SignalVeilleur)
                    .filter(SignalVeilleur.id == signal_id, SignalVeilleur.etat == svc_signaux.ETAT_DETECTE)
                    .update({SignalVeilleur.etat: SIGNAL_PLANIFIE}, synchronize_session=False))
            db.commit()
            if pris != 1:
                continue
            pris_total += 1
            signal = db.get(SignalVeilleur, signal_id)
            decisions: list[regles.Decision] = []
            for dest in vises:
                if signal.user_id is not None and dest.user_id != signal.user_id:
                    continue
                r = reglages[dest.user_id]
                # [US-272 / CA9] Un compte sans Telegram lié n'est plus ignoré : son message va au
                # panneau de la PWA seul (`_envoyer_message`), avec les mêmes règles d'envoi.
                sans_reaction = r.mode(signal.theme) == regles.MODE_IMMEDIAT and regles.doit_basculer(
                    signal.theme,
                    _reactions_du_theme(db, potager_id, dest.user_id, signal.theme, r.depuis_le(signal.theme)))
                decision = regles.planifier(signal.theme, signal.expire_le, r, maintenant, sans_reaction)
                if decision.annonce_bascule:
                    reglages[dest.user_id] = _basculer(db, potager_id, dest.user_id, signal.theme, maintenant)
                db.add(_envoi(potager_id, signal_id, dest.user_id, decision, maintenant))
                decisions.append(decision)
            if all(d.etat == regles.ETAT_IGNORE for d in decisions):
                signal.etat = svc_signaux.ETAT_IGNORE
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                log.warning("[US-267 / CA11] Signal %s déjà planifié par un autre passage", signal_id)
                continue
            log.info("[US-267] Signal %s (%s) → %s", signal.cle_unique, signal.theme,
                     ", ".join(f"{d.mode}/{d.etat}{'/' + d.motif if d.motif else ''} à "
                               f"{d.envoyer_le:%d/%m %H:%M}" for d in decisions) or "aucun destinataire")
        return pris_total


# ═════════════════════════════════════════════════════════════════════════════
# 2. Envoyer
# ═════════════════════════════════════════════════════════════════════════════
def _ignorer(db: Session, envois: list[EnvoiSignal], motif: str, maintenant: datetime) -> None:
    for envoi in envois:
        envoi.etat, envoi.motif, envoi.traite_le = regles.ETAT_IGNORE, motif, maintenant
    if envois:
        db.commit()
        log.info("[US-267] %s envoi(s) consommé(s) sans message : %s", len(envois), motif)


def _prendre(db: Session, envois: list[EnvoiSignal], maintenant: datetime) -> list[EnvoiSignal]:
    """[CA11] Prend les envois de façon atomique : un envoi pris ailleurs est laissé."""
    pris = []
    for envoi in envois:
        n = (db.query(EnvoiSignal)
             .filter(EnvoiSignal.id == envoi.id, EnvoiSignal.etat == regles.ETAT_EN_ATTENTE)
             .update({EnvoiSignal.etat: regles.ETAT_ENVOYE, EnvoiSignal.traite_le: maintenant},
                     synchronize_session=False))
        if n == 1:
            pris.append(envoi)
    db.commit()
    return pris


def _a_rediger(envois: list[EnvoiSignal], signaux: dict[int, SignalVeilleur]) -> list[SignalARediger]:
    """Les signaux du message : ce qui part tout de suite d'abord, puis le point du matin."""
    ordonnes = sorted(envois, key=lambda e: (e.mode != regles.MODE_IMMEDIAT, signaux[e.signal_id].detecte_le, e.id))
    return [
        SignalARediger(theme=signaux[e.signal_id].theme, cle_unique=signaux[e.signal_id].cle_unique,
                       expire_le=signaux[e.signal_id].expire_le, donnees=signaux[e.signal_id].donnees or {},
                       signal_id=e.signal_id, envoi_id=e.id)
        for e in ordonnes
    ]


def _envoyer_message(
    db: Session, potager_id: int, dest: Destinataire, pris: list[EnvoiSignal],
    signaux: dict[int, SignalVeilleur], maintenant: datetime, envoyer: Envoyeur, avec_modele: bool,
) -> bool:
    """Rédige, poste dans Telegram et range le message ; rend False si Telegram l'a refusé.

    [US-272 / CA9] Sans Telegram lié, le message est rangé pour le panneau de la PWA seul
    (aucun identifiant de message Telegram) : il n'est jamais perdu.
    """
    ctx = TenantContext(user_id=dest.user_id, potager_id=potager_id)
    a_rediger = _a_rediger(pris, signaux)
    resume = any(e.mode == regles.MODE_RESUME for e in pris)
    bascules = sorted({signaux[e.signal_id].theme for e in pris if e.annonce_bascule})
    redac = redaction.composer(
        a_rediger, ctx, maintenant=maintenant, prenom=dest.prenom,
        profil_bloc=profil_echange.bloc_prompt(profil_echange.Profil(prenom=dest.prenom, registre=dest.registre)),
        resume=resume, potager=svc_propositions.potager_a_nommer(dest.user_id, potager_id),
        bascules=bascules, avec_modele=avec_modele,
    )
    clavier = [[(b.libelle, b.callback) for b in rangee] for rangee in reponse_signal.boutons(potager_id, a_rediger)]
    panneau_seul = dest.chat_id is None
    message_telegram = None if panneau_seul else envoyer(dest.chat_id, redac.texte, clavier)
    if message_telegram is None and not panneau_seul:
        for envoi in pris:
            envoi.etat, envoi.traite_le = regles.ETAT_EN_ATTENTE, None
        db.commit()
        log.warning("[US-267] Telegram n'a pas pris le message (user %s, potager %s) : %s envoi(s) "
                    "remis en attente", dest.user_id, potager_id, len(pris))
        return False
    message = MessageSpontane(
        potager_id=potager_id, user_id=dest.user_id, genre=GENRE_RESUME if resume else GENRE_SIGNAL,
        themes=sorted({signaux[e.signal_id].theme for e in pris}), texte=redac.texte,
        redige="agent" if redac.redige else "gabarit", telegram_chat_id=dest.chat_id,
        telegram_message_id=message_telegram, envoye_le=maintenant,
    )
    db.add(message)
    db.flush()
    seul = len(pris) == 1 and not resume
    for envoi in pris:
        envoi.message_id = message.id
        signaux[envoi.signal_id].etat = svc_signaux.ETAT_ENVOYE if seul else svc_signaux.ETAT_REGROUPE
    db.commit()
    # [CA8] Le message entre dans la conversation : une réponse dans la demi-heure le retrouve.
    canal = svc_propositions.CANAL_PWA if panneau_seul else svc_propositions.CANAL_TELEGRAM
    conversations.noter(ctx, "", redac.texte, canal=canal, signal=f"spontane:{message.id}")
    log.info("[US-267] 📨 Message spontané %s → user %s (potager %s) : %s signal(aux), %s, %s, "
             "telegram_message_id=%s", message.genre, dest.user_id, potager_id, len(pris), message.themes,
             message.redige, message_telegram)
    return True


def envoyer_dus(potager_id: int, maintenant: datetime, envoyer: Envoyeur, avec_modele: bool = True) -> int:
    """[CA2, CA3, CA4, CA10, CA11] Les envois dus, un message par jardinier ; rend le nombre envoyé."""
    with _session(potager_id) as db:
        dus = (db.query(EnvoiSignal)
               .filter(EnvoiSignal.potager_id == potager_id, EnvoiSignal.etat == regles.ETAT_EN_ATTENTE,
                       EnvoiSignal.envoyer_le <= maintenant)
               .order_by(EnvoiSignal.user_id, EnvoiSignal.id)
               .all())
        if not dus:
            return 0
        par_jardinier: dict[int, list[EnvoiSignal]] = defaultdict(list)
        for envoi in dus:
            par_jardinier[envoi.user_id].append(envoi)
        vises = {d.user_id: d for d in destinataires(db, potager_id)}
        signaux = {s.id: s for s in db.query(SignalVeilleur).filter(SignalVeilleur.id.in_({e.signal_id for e in dus}))}
        envoyes = 0
        for user_id, envois in par_jardinier.items():
            dest = vises.get(user_id)
            if dest is None:
                _ignorer(db, envois, MOTIF_PLUS_MEMBRE, maintenant)
                continue
            expires = [e for e in envois if signaux[e.signal_id].expire_le <= maintenant]
            _ignorer(db, expires, regles.MOTIF_EXPIRE, maintenant)
            vivants = [e for e in envois if e not in expires]
            if not vivants:
                continue
            dernier = (db.query(func.max(MessageSpontane.envoye_le))
                       .filter(MessageSpontane.potager_id == potager_id, MessageSpontane.user_id == user_id)
                       .scalar())
            report = regles.report_de_regroupement(
                dernier, maintenant, dest.reglages, [signaux[e.signal_id].expire_le for e in vivants])
            if report is not None:
                for envoi in vivants:
                    envoi.envoyer_le = report
                db.commit()
                log.info("[US-267 / CA2] %s envoi(s) groupé(s) avec la demi-heure en cours → %s (user %s)",
                         len(vivants), f"{report:%H:%M}", user_id)
                continue
            pris = _prendre(db, vivants, maintenant)
            if pris and _envoyer_message(db, potager_id, dest, pris, signaux, maintenant, envoyer, avec_modele)                     and dest.chat_id is not None:
                envoyes += 1  # [US-272 / CA9] le compte est celui des messages partis dans Telegram
        return envoyes


def passer(maintenant: Optional[datetime] = None, envoyer: Optional[Envoyeur] = None,
           avec_modele: bool = True) -> dict[int, int]:
    """[CA11] Un passage du distributeur ; rend, par potager, le nombre de messages envoyés.

    `COMPAGNON_PROACTIF` éteint : rien n'est pris, rien ne part, les signaux attendent.
    """
    if not actif():
        log.debug("[US-267] Distributeur éteint (COMPAGNON_PROACTIF)")
        return {}
    maintenant = maintenant or veilleur_passage.maintenant_local()
    envoyer = envoyer or telegram_notify.envoyer
    resultats: dict[int, int] = {}
    for potager in veilleur_passage.potagers_a_veiller():
        try:
            planifier_potager(potager.id, maintenant)
            resultats[potager.id] = envoyer_dus(potager.id, maintenant, envoyer, avec_modele)
        except Exception:  # noqa: BLE001 — un potager en échec ne prive pas les suivants
            log.exception("[US-267] Distributeur : passage en échec pour le potager %s", potager.id)
    if any(resultats.values()):
        log.info("[US-267] 📨 DISTRIBUTEUR : %s message(s) envoyé(s)", sum(resultats.values()))
    return resultats


# ═════════════════════════════════════════════════════════════════════════════
# CA5, CA7, CA8 — La réponse du jardinier
# ═════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class MessageEnContexte:
    """Le message spontané auquel le jardinier répond, avec ses signaux."""

    message_id: int
    potager_id: int
    texte: str
    envoye_le: datetime
    signaux: tuple[SignalARediger, ...]

    def donnees(self) -> dict:
        """Pour l'agent : ce qu'il a écrit, et les faits du signal d'origine."""
        return {
            "texte": self.texte[-600:],
            "signaux": [{"sujet": s.genre, **(s.donnees or {}), **({"question": s.question} if s.question else {})}
                        for s in self.signaux],
        }


def _signaux_du_message(db: Session, message: MessageSpontane) -> tuple[SignalARediger, ...]:
    envois = db.query(EnvoiSignal).filter(EnvoiSignal.message_id == message.id).order_by(EnvoiSignal.id).all()
    signaux = {s.id: s for s in db.query(SignalVeilleur).filter(SignalVeilleur.id.in_({e.signal_id for e in envois}))}
    return tuple(_a_rediger([e for e in envois if e.signal_id in signaux], signaux))


def message_en_contexte(
    potager_id: int, user_id: Optional[int], maintenant: Optional[datetime] = None,
    telegram_message_id: Optional[int] = None,
) -> Optional[MessageEnContexte]:
    """[CA8] Le message spontané auquel cette phrase répond, ou None.

    Celui que le jardinier cite (réponse Telegram à un message), sinon le dernier : envoyé il
    y a moins de douze heures et resté sans réponse, ou répondu il y a moins de trente minutes
    (la conversation continue). Ne lève jamais : sans lui, la phrase passe sans contexte.
    """
    if user_id is None:
        return None
    instant = maintenant or veilleur_passage.maintenant_local()
    try:
        with _session(potager_id) as db:
            # [US-272 / CA9] Un message rangé pour le panneau seul n'a pas de réponse Telegram à attendre.
            requete = db.query(MessageSpontane).filter(
                MessageSpontane.potager_id == potager_id, MessageSpontane.user_id == user_id,
                MessageSpontane.telegram_message_id.isnot(None))
            cite = None
            if telegram_message_id is not None:
                cite = requete.filter(MessageSpontane.telegram_message_id == telegram_message_id).first()
            message = cite or requete.order_by(MessageSpontane.envoye_le.desc(), MessageSpontane.id.desc()).first()
            if message is None:
                return None
            if cite is None:
                if instant - message.envoye_le > FENETRE_REPONSE:
                    return None
                if message.reaction_le is not None and instant - message.reaction_le > FENETRE_SUITE:
                    return None
            return MessageEnContexte(message.id, potager_id, message.texte, message.envoye_le,
                                     _signaux_du_message(db, message))
    except Exception:  # noqa: BLE001 — la mémoire ne casse jamais la réponse
        log.exception("[US-267 / CA8] Message spontané illisible (user %s, potager %s)", user_id, potager_id)
        return None


def noter_reaction(potager_id: int, user_id: Optional[int], message_id: int,
                   maintenant: Optional[datetime] = None) -> bool:
    """[CA5] Le jardinier a réagi (clic ou réponse) : le message compte comme répondu, et ses
    signaux passent à `repondu`. Rend True à la première réaction seulement."""
    if user_id is None:
        return False
    instant = maintenant or veilleur_passage.maintenant_local()
    try:
        with _session(potager_id) as db:
            n = (db.query(MessageSpontane)
                 .filter(MessageSpontane.id == message_id, MessageSpontane.user_id == user_id,
                         MessageSpontane.reaction_le.is_(None))
                 .update({MessageSpontane.reaction_le: instant}, synchronize_session=False))
            if n:
                ids = [i for (i,) in db.query(EnvoiSignal.signal_id).filter(EnvoiSignal.message_id == message_id)]
                if ids:
                    (db.query(SignalVeilleur).filter(SignalVeilleur.id.in_(ids))
                     .update({SignalVeilleur.etat: svc_signaux.ETAT_REPONDU}, synchronize_session=False))
            db.commit()
            if n:
                log.info("[US-267 / CA5] Réaction au message spontané %s (user %s)", message_id, user_id)
            return bool(n)
    except Exception:  # noqa: BLE001
        log.exception("[US-267 / CA5] Réaction non notée (message %s)", message_id)
        return False


def signal_du_bouton(potager_id: int, user_id: Optional[int], envoi_id: int,
                     maintenant: Optional[datetime] = None) -> Optional[SignalARediger]:
    """[CA7] Le signal derrière un bouton, s'il a bien été envoyé à CE jardinier ; la réaction
    est notée au passage. None : bouton d'un autre, ou d'un message purgé."""
    if user_id is None:
        return None
    with _session(potager_id) as db:
        envoi = db.query(EnvoiSignal).filter(EnvoiSignal.id == envoi_id, EnvoiSignal.user_id == user_id).first()
        if envoi is None or envoi.message_id is None:
            return None
        signal = db.get(SignalVeilleur, envoi.signal_id)
        if signal is None:
            return None
        message_id = envoi.message_id
        trouve = _a_rediger([envoi], {signal.id: signal})[0]
    noter_reaction(potager_id, user_id, message_id, maintenant)
    return trouve


def messages_du_jardinier(ctx: TenantContext, limite: int = 10) -> list[dict]:
    """[US-271 / CA3] Les derniers messages spontanés envoyés à ce jardinier dans ce potager.

    Le panneau de la PWA les range avec la conversation : ce que le compagnon a dit de lui-même,
    qu'il soit parti dans Telegram ou non. Du plus ancien au plus récent ; lecture seule, propre
    au jardinier et au potager (RLS stricte). Ne lève jamais : sans eux, le panneau reste vide
    de ce côté.
    """
    try:
        with _session(ctx.potager_id) as db:
            lignes = (
                db.query(MessageSpontane)
                .filter(MessageSpontane.potager_id == ctx.potager_id, MessageSpontane.user_id == ctx.user_id)
                .order_by(MessageSpontane.envoye_le.desc(), MessageSpontane.id.desc())
                .limit(limite)
                .all()
            )
            return [
                {"id": m.id, "genre": m.genre, "themes": list(m.themes or []), "texte": m.texte,
                 "envoye_le": m.envoye_le.isoformat(), "reagi": m.reaction_le is not None}
                for m in reversed(lignes)
            ]
    except Exception:  # noqa: BLE001
        log.exception("[US-271 / CA3] Messages spontanés illisibles (user %s, potager %s)", ctx.user_id, ctx.potager_id)
        return []

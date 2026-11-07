"""
app/services/compagnon/deux_canaux.py — Une proposition, deux fenêtres [US-272]
===============================================================================
Une proposition ne vit pas dans un canal : elle est en base (US-259), rattachée au
jardinier et à SON potager. Telegram et la PWA en sont deux fenêtres (cadrage §4.7, D11).
Ce module range ce que la seconde fenêtre doit voir de la première :

* **D13 / CA1** — toute proposition née dans la PWA part dans Telegram dès sa création
  (`notifier`), même si elle est confirmée aussitôt dans le portail. Aucune condition de
  présence, aucune temporisation (D12) : le fil Telegram est le journal complet ;
* **F1 / CA2** — la première réponse l'emporte : c'est la sortie atomique de
  `propositions.sortir`, pas ce module. Ici, seulement ce qu'on DIT au second
  (`texte_deja_traitee` : « Déjà confirmé depuis le portail à 14:32 ») ;
* **F2 / CA3, F3 / CA4** — au changement d'état, la carte Telegram est réécrite
  (`reecrire`) : « ✅ Confirmé depuis le portail », « Remplacée : voir la nouvelle
  proposition ». Si la réécriture échoue (message trop ancien, supprimé), F1 suffit ;
* **F4** — une proposition notifiée prend la durée de la file (`propositions.marquer_notifiee`) ;
* **F5 / CA6** — la carte nomme le potager quand le jardinier en a plusieurs ;
* **CA9** — un compte sans Telegram lié lit tout dans le panneau, et y est invité UNE fois
  à lier Telegram (`invitation_telegram`).

Le service CALCULE les cartes ; l'envoi passe par `telegram_notify` (HTTP, pour l'API) ou
par le bot lui-même (`rendu_de_la_carte`, pour ne pas bloquer sa boucle asyncio). L'envoi
HTTP part en arrière-plan : un Telegram lent (jusqu'à 10 s de délai) ne retient pas la
réponse du portail. La course « confirmée avant que l'envoi ait rendu son identifiant »
est rattrapée après l'envoi : la carte est réécrite tout de suite.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Optional

from app.services import telegram_notify
from app.services.compagnon import propositions as svc_propositions
from app.services.compagnon.decisions import heure_locale
from database.models import Proposition, User

log = logging.getLogger("potager")

#: Où une proposition a été traitée, tel qu'on l'écrit sur la carte.
_DEPUIS = {
    svc_propositions.CANAL_PWA: "depuis le portail",
    svc_propositions.CANAL_TELEGRAM: "depuis Telegram",
}

TEXTE_REMPLACEE = "↪️ Remplacée : voir la nouvelle proposition."
TEXTE_PERIMEE = "⏱ Expirée, rien n'a été fait."
TEXTE_ORIGINE_PORTAIL = "💻 Proposé depuis le portail"

#: [CA9] Vocabulaire d'US-091 / CA15 : un compagnon de terrain à ACTIVER, jamais « relier Telegram ».
TEXTE_INVITATION_TELEGRAM = (
    "📱 Ton compagnon de terrain n'est pas activé : mes messages et mes propositions n'arrivent "
    "qu'ici. Active-le (menu du compte → « Activer mon compagnon ») pour les recevoir aussi sur "
    "ton téléphone, dans Telegram, et y répondre d'un bouton."
)

#: Préfixe des boutons d'un geste dit dans le portail, posé dans Telegram (`app/bot/cartes_compagnon.py`).
#: Une commande ou un plan reprend les boutons `interp:` de la conversation : même proposition,
#: même gestionnaire.
PREFIXE_GESTE = "cmp"

#: [Tests] True : l'envoi se fait dans l'appel, pour qu'un test lise le résultat sans attendre.
SYNCHRONE = False
_executeur = ThreadPoolExecutor(max_workers=2, thread_name_prefix="deux-canaux")


def _lancer(fonction: Callable, *args) -> None:
    """Envoi Telegram en arrière-plan ; une erreur est journalisée, jamais remontée (best-effort)."""
    def _protege() -> None:
        try:
            fonction(*args)
        except Exception:  # noqa: BLE001
            log.exception("[US-272] Envoi vers Telegram en échec (%s)", getattr(fonction, "__name__", fonction))

    if SYNCHRONE:
        _protege()
    else:
        _executeur.submit(_protege)


# ═════════════════════════════════════════════════════════════════════════════
# Ce qu'une carte dit de son état
# ═════════════════════════════════════════════════════════════════════════════
def _quand(traite_le: Optional[datetime]) -> str:
    return f" à {heure_locale(traite_le)}" if traite_le is not None else ""


def _depuis(canal: Optional[str]) -> str:
    return f" {_DEPUIS[canal]}" if canal in _DEPUIS else ""


def texte_etat(etat: str, canal: Optional[str], traite_le: Optional[datetime]) -> str:
    """[CA3, CA4] La première ligne d'une carte réécrite : « ✅ Confirmé depuis le portail à 14:32 »."""
    if etat == svc_propositions.ETAT_CONFIRMEE:
        return f"✅ Confirmé{_depuis(canal)}{_quand(traite_le)}"
    if etat == svc_propositions.ETAT_ABANDONNEE:
        return f"❌ Laissé tomber{_depuis(canal)}{_quand(traite_le)}"
    if etat == svc_propositions.ETAT_REMPLACEE:
        return TEXTE_REMPLACEE
    if etat == svc_propositions.ETAT_PERIMEE:
        return TEXTE_PERIMEE
    return ""


def texte_deja_traitee(etat: str, canal: Optional[str], traite_le: Optional[datetime]) -> str:
    """[CA2 / F1] Ce que lit celui qui répond en second : « Déjà confirmé depuis le portail à 14:32 »."""
    if etat == svc_propositions.ETAT_CONFIRMEE:
        return f"Déjà confirmé{_depuis(canal)}{_quand(traite_le)} : rien n'est refait."
    if etat == svc_propositions.ETAT_ABANDONNEE:
        return f"Déjà laissé tomber{_depuis(canal)}{_quand(traite_le)} : rien n'est fait."
    if etat == svc_propositions.ETAT_REMPLACEE:
        return TEXTE_REMPLACEE + " Rien n'a été fait."
    return TEXTE_PERIMEE


# ═════════════════════════════════════════════════════════════════════════════
# La carte d'une proposition dans Telegram
# ═════════════════════════════════════════════════════════════════════════════
def lignes_de(ligne: Proposition) -> list[str]:
    """Ce que la proposition ferait, une ligne par geste ou par étape — les lignes de la carte du portail."""
    from app.services import interpreteur_commandes as svc_interpreteur
    from app.services.compagnon import gestes_conversation as svc_gestes_dits

    contenu = ligne.contenu or {}
    if ligne.nature == svc_propositions.NATURE_GESTE:
        return [svc_gestes_dits.resume(item) for item in contenu.get("items") or []]
    try:
        commande = svc_propositions.deserialiser(ligne.nature, contenu["proposition"])
    except Exception:  # noqa: BLE001 — une ligne illisible n'empêche pas de dire son état
        log.exception("[US-272] Proposition id=%s illisible pour sa carte", ligne.id)
        return []
    if isinstance(commande, svc_interpreteur.Plan):
        return [etape.commande_equivalente() for etape in commande.etapes]
    return [commande.commande_equivalente()]


def boutons_de(ligne: Proposition) -> list[list[telegram_notify.Bouton]]:
    """[CA1] Les boutons de la carte : un geste a les siens, une commande ou un plan ceux de la conversation."""
    prefixe = PREFIXE_GESTE if ligne.nature == svc_propositions.NATURE_GESTE else "interp"
    confirmer = "✅ Tout confirmer" if ligne.nature == svc_propositions.NATURE_PLAN else "✅ Confirmer"
    return [[(confirmer, f"{prefixe}:ok:{ligne.code}"), ("❌ Annuler", f"{prefixe}:non:{ligne.code}")]]


def _corps(ligne: Proposition, lignes: list[str]) -> str:
    nom = svc_propositions.potager_a_nommer(ligne.user_id, ligne.potager_id)  # [CA6 / F5]
    entete = [f"🏡 {nom}"] if nom else []
    origine = [TEXTE_ORIGINE_PORTAIL] if ligne.canal == svc_propositions.CANAL_PWA else []
    return "\n".join(entete + origine + [f"• {texte}" for texte in lignes])


def texte_de_la_carte(ligne: Proposition) -> str:
    """La carte telle qu'on la poste : potager (s'il y en a plusieurs), origine, lignes."""
    return _corps(ligne, lignes_de(ligne))


def texte_reecrit(ligne: Proposition) -> str:
    """La carte telle qu'on la réécrit : son état d'abord, puis ce qu'elle proposait (sans boutons)."""
    etat = texte_etat(ligne.etat, ligne.traite_canal, ligne.traite_le)
    return f"{etat}\n{_corps(ligne, lignes_de(ligne))}".strip()


# ═════════════════════════════════════════════════════════════════════════════
# Lire, poster, réécrire
# ═════════════════════════════════════════════════════════════════════════════
def _ligne(db, proposition_id: int) -> Optional[Proposition]:
    return db.query(Proposition).filter(Proposition.id == int(proposition_id)).first()


def chat_de(db, user_id: int) -> Optional[int]:
    """Le chat Telegram du compte, ou None s'il n'en a pas lié."""
    utilisateur = db.get(User, user_id)
    return getattr(utilisateur, "telegram_chat_id", None)


def noter_message(proposition_id: int, potager_id: int, chat_id: int, message_id: int) -> bool:
    """[F2] Retient la carte Telegram de la proposition, pour la réécrire plus tard."""
    with svc_propositions.session_sur(potager_id) as db:
        nb = (
            db.query(Proposition).filter(Proposition.id == int(proposition_id))
            .update({"telegram_chat_id": int(chat_id), "telegram_message_id": int(message_id)},
                    synchronize_session=False)
        )
        db.commit()
    return nb == 1


def notifier(proposition_id: int, potager_id: int) -> bool:
    """[CA1 / D13] Poste dans Telegram la carte d'une proposition née dans la PWA.

    Rend False sans rien poster si le compte n'a pas lié Telegram (CA9 : le panneau seul),
    si la proposition est introuvable ou si sa carte est déjà postée. L'envoi lui-même part
    en arrière-plan ; un envoi perdu l'est sans bruit (le panneau reste juste).
    """
    with svc_propositions.session_sur(potager_id) as db:
        ligne = _ligne(db, proposition_id)
        if ligne is None or ligne.telegram_message_id is not None:
            return False
        chat_id = chat_de(db, ligne.user_id)
        if chat_id is None:
            log.info("[US-272 / CA9] Proposition id=%s : pas de Telegram lié, le panneau seul", ligne.id)
            return False
        texte, boutons = texte_de_la_carte(ligne), boutons_de(ligne)
    _lancer(_poster, int(proposition_id), int(potager_id), int(chat_id), texte, boutons)
    return True


def _poster(proposition_id: int, potager_id: int, chat_id: int, texte: str, boutons) -> None:
    message_id = telegram_notify.envoyer(chat_id, texte, boutons)
    if message_id is None:
        log.warning("[US-272 / CA1] Carte de la proposition id=%s non postée dans Telegram", proposition_id)
        return
    noter_message(proposition_id, potager_id, chat_id, message_id)
    svc_propositions.marquer_notifiee(proposition_id, potager_id)  # [F4] trois jours, comme la file
    log.info("[US-272 / CA1] Proposition id=%s postée dans Telegram (message %s)", proposition_id, message_id)
    # D13 : confirmée (ou remplacée) pendant l'envoi → la carte suit son état tout de suite.
    with svc_propositions.session_sur(potager_id) as db:
        ligne = _ligne(db, proposition_id)
        a_reecrire = ligne is not None and ligne.etat != svc_propositions.ETAT_EN_ATTENTE
        texte_suite = texte_reecrit(ligne) if a_reecrire else None
    if texte_suite:
        _editer(chat_id, message_id, texte_suite, proposition_id)


@dataclass
class CarteAReecrire:
    """Ce que le canal doit poser à la place de la carte : le bot l'envoie lui-même, de façon asynchrone."""

    chat_id: int
    message_id: int
    texte: str


def rendu_de_la_carte(proposition_id: int) -> Optional[CarteAReecrire]:
    """[CA3, CA4] La carte Telegram réécrite d'une proposition sortie de l'attente, ou None.

    None : pas de carte postée, ou proposition encore en attente (rien à réécrire).
    Lue GUC désarmé, comme `par_code` : l'appelant ne sait pas toujours de quel potager elle relève.
    """
    with svc_propositions.session_sur(None) as db:
        ligne = _ligne(db, proposition_id)
        if ligne is None or ligne.telegram_message_id is None or ligne.telegram_chat_id is None:
            return None
        if ligne.etat == svc_propositions.ETAT_EN_ATTENTE:
            return None
        return CarteAReecrire(int(ligne.telegram_chat_id), int(ligne.telegram_message_id), texte_reecrit(ligne))


def reecrire(proposition_id: Optional[int]) -> bool:
    """[CA3, CA4 / F2] Réécrit la carte Telegram d'une proposition traitée HORS de Telegram.

    Best-effort : rend True si une réécriture est lancée. Un clic dans Telegram, lui, réécrit
    son propre message (le bot répond sur la carte) : ce chemin ne sert qu'au portail et au
    remplacement d'une proposition par une nouvelle.
    """
    if proposition_id is None:
        return False
    carte = rendu_de_la_carte(proposition_id)
    if carte is None:
        return False
    _lancer(_editer, carte.chat_id, carte.message_id, carte.texte, proposition_id)
    return True


def _editer(chat_id: int, message_id: int, texte: str, proposition_id: int) -> None:
    if telegram_notify.editer_message(chat_id, message_id, texte):
        log.info("[US-272 / F2] Carte Telegram de la proposition id=%s réécrite", proposition_id)
    else:
        # F2 : un message trop ancien ne se réécrit plus ; F1 (la sortie atomique) suffit.
        log.info("[US-272 / F2] Carte de la proposition id=%s non réécrite : le refus motivé suffit", proposition_id)


def remplacees_par(proposition_id: int, potager_id: int) -> list[int]:
    """[CA4 / F3] Les propositions que celle-ci a remplacées et dont la carte est dans Telegram."""
    with svc_propositions.session_sur(potager_id) as db:
        return [
            pid for (pid,) in db.query(Proposition.id).filter(
                Proposition.remplacee_par_id == int(proposition_id),
                Proposition.telegram_message_id.isnot(None),
            )
        ]


def apres_creation(proposition_id: int, potager_id: int) -> bool:
    """[CA1, CA4] Ce que la PWA fait d'une proposition qu'elle vient de ranger : réécrire les cartes
    qu'elle remplace, puis poster la sienne dans Telegram. Rend True si une carte part."""
    for ancienne in remplacees_par(proposition_id, potager_id):
        reecrire(ancienne)
    return notifier(proposition_id, potager_id)


# ═════════════════════════════════════════════════════════════════════════════
# [CA9] Un compte sans Telegram : le panneau seul, et une invitation
# ═════════════════════════════════════════════════════════════════════════════
def telegram_lie(user_id: int) -> bool:
    with svc_propositions.session_sur(None) as db:
        return chat_de(db, user_id) is not None


#: [CA9] « Une fois » = une visite : l'invitation reste servie ce temps-là après sa première remise, pour
#: qu'une relecture de l'historique (double appel de React en développement, « Recommencer », réseau
#: qui rejoue) ne la perde pas. Au-delà, plus jamais.
DUREE_INVITATION = timedelta(minutes=10)


def invitation_telegram(user_id: int, maintenant: Optional[datetime] = None) -> Optional[str]:
    """[CA9] L'invitation à lier Telegram, UNE visite par compte ; None ensuite, ou si Telegram est lié.

    La première remise est posée par un UPDATE conditionnel (`invitation_telegram_le IS NULL`) ;
    elle reste servie `DUREE_INVITATION`, puis plus jamais.
    """
    instant = maintenant or datetime.utcnow()
    with svc_propositions.session_sur(None) as db:
        utilisateur = db.get(User, user_id)
        if utilisateur is None or utilisateur.telegram_chat_id is not None:
            return None
        if utilisateur.invitation_telegram_le is not None:
            return TEXTE_INVITATION_TELEGRAM if instant - utilisateur.invitation_telegram_le < DUREE_INVITATION else None
        nb = (
            db.query(User)
            .filter(User.id == user_id, User.invitation_telegram_le.is_(None))
            .update({"invitation_telegram_le": instant}, synchronize_session=False)
        )
        db.commit()
    if nb:
        log.info("[US-272 / CA9] user_id=%s invité à lier Telegram", user_id)
    return TEXTE_INVITATION_TELEGRAM

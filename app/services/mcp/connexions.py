"""
app/services/mcp/connexions.py — Voir et révoquer les assistants IA connectés [US-294]
======================================================================================
L'écran « Assistants connectés » de la PWA s'appuie sur les autorisations et le journal d'US-290
(la révocation, le jeton personnel et le consentement restent dans `autorisation.py`) ; ce module
porte ce qu'US-294 ajoute :

* `lister` : chaque connexion, avec ses potagers nommés et son statut (CA1, CA2) ;
* `activite` : les 100 derniers appels d'une connexion, jamais leur contenu (CA3) ;
* `interdire_assistants` : le propriétaire ferme un potager aux assistants externes (CA6, D6) ;
* `notifier_nouvelle_connexion` et `assistants_du_potager` : les membres d'un potager partagé
  savent qu'un des leurs a connecté un assistant (CA5), par Telegram et dans l'écran « Membres ».
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.services import potager_actif as svc_potager_actif
from app.services import telegram_notify
from app.services.mcp import autorisation as svc_autorisation
from database.models import (
    Evenement, McpAppel, McpAutorisation, McpJeton, Potager, PotagerMembre, User,
)

log = logging.getLogger("potager")

LIMITE_ACTIVITE = 100
STATUT_ACTIVE, STATUT_REVOQUEE, STATUT_EXPIREE = "active", "revoquee", "expiree"
LIBELLE_PORTEE = {"lecture": "lecture", "ecriture": "lecture + écriture"}


class PasProprietaireError(PermissionError):
    """Seul le propriétaire d'un potager décide des assistants externes (CA6)."""


def _statut(db: Session, autorisation: McpAutorisation) -> str:
    if autorisation.revoque_le is not None:
        return STATUT_REVOQUEE
    maintenant = svc_autorisation._maintenant()
    jetons = db.query(McpJeton).filter(McpJeton.autorisation_id == autorisation.id, McpJeton.revoque_le.is_(None)).all()
    # Une connexion sans jeton valide (rafraîchissement compris) n'ouvre plus rien : elle est expirée.
    if not any(j.expire_le >= maintenant for j in jetons):
        return STATUT_EXPIREE
    return STATUT_ACTIVE


def lister(db: Session, user_id: int) -> list[dict]:
    """[CA1, CA2] Chaque connexion : client, dates, portée, potagers NOMMÉS (ceux fermés aux assistants
    portent `interdit`), statut. La plus récente d'abord."""
    noms = {p.id: p for p in svc_potager_actif.lister_potagers_utilisateur(db, user_id)}
    connexions = []
    for ligne in svc_autorisation.lister_connexions(db, user_id):
        autorisation = db.get(McpAutorisation, ligne["id"])
        connexions.append({
            **ligne,
            "portee_libelle": LIBELLE_PORTEE.get(ligne["portee"], ligne["portee"]),
            "statut": _statut(db, autorisation),
            "potagers": [
                {"id": pid, "nom": noms[pid].nom if pid in noms else "potager indisponible",
                 "interdit": bool(noms[pid].assistants_externes_interdits) if pid in noms else False}
                for pid in ligne["potager_ids"]
            ],
        })
    return connexions


def activite(db: Session, user_id: int, autorisation_id: int, limite: int = LIMITE_ACTIVITE) -> Optional[list[dict]]:
    """[CA3] Les derniers appels d'une connexion DU JARDINIER : date, outil, potager, résultat. Une écriture
    confirmée porte le geste écrit et sa date, pour renvoyer au Journal. None si la connexion n'est pas la sienne."""
    autorisation = db.query(McpAutorisation).filter(
        McpAutorisation.id == autorisation_id, McpAutorisation.user_id == user_id).first()
    if autorisation is None:
        return None
    appels = (
        db.query(McpAppel).filter(McpAppel.autorisation_id == autorisation_id)
        .order_by(McpAppel.horodatage.desc(), McpAppel.id.desc()).limit(min(limite, LIMITE_ACTIVITE)).all()
    )
    potagers = {p.id: p.nom for p in svc_potager_actif.lister_potagers_utilisateur(db, user_id, etat="tous")}
    evenements = {
        e.id: e for e in db.query(Evenement).filter(
            Evenement.id.in_([a.evenement_id for a in appels if a.evenement_id])).all()
    } if any(a.evenement_id for a in appels) else {}
    lignes = []
    for appel in appels:
        evenement = evenements.get(appel.evenement_id)
        lignes.append({
            "date": appel.horodatage.isoformat() if appel.horodatage else None,
            "outil": appel.outil,
            "potager": potagers.get(appel.potager_id),
            "potager_id": appel.potager_id,
            "resultat": appel.resultat,
            "motif": appel.motif,
            "geste": None if evenement is None else {
                "id": evenement.id,
                "date": evenement.date.date().isoformat() if evenement.date else None,
            },
        })
    return lignes


def interdire_assistants(db: Session, user_id: int, potager_id: int, interdit: bool) -> dict:
    """[CA6, D6] Le propriétaire ferme (ou rouvre) un potager aux assistants externes. Les connexions existantes
    n'y ont plus accès dès leur appel suivant (relu à chaque appel), et restent valables ailleurs."""
    if svc_potager_actif.role_utilisateur(db, user_id, potager_id) != "owner":
        raise PasProprietaireError("Seul le propriétaire du potager peut interdire les assistants externes.")
    potager = db.get(Potager, potager_id)
    if potager is None:
        raise LookupError("Potager introuvable.")
    potager.assistants_externes_interdits = bool(interdit)
    db.commit()
    log.info("[US-294] Assistants externes %s pour le potager %s par l'utilisateur %s",
             "interdits" if interdit else "de nouveau autorisés", potager_id, user_id)
    return {"potager_id": potager_id, "assistants_externes_interdits": bool(interdit)}


# ── Potagers partagés : prévenir les autres membres (CA5) ─────────────────────
def _deja_connecte(db: Session, autorisation: McpAutorisation, potager_id: int) -> bool:
    """Ce membre avait-il déjà (même révoquée) cet assistant sur ce potager ? Alors rien à annoncer."""
    precedentes = db.query(McpAutorisation).filter(
        McpAutorisation.user_id == autorisation.user_id, McpAutorisation.id != autorisation.id,
        McpAutorisation.type == autorisation.type,
    ).all()
    for autre in precedentes:
        meme = (autre.client_id == autorisation.client_id) if autorisation.client_id else (autre.libelle == autorisation.libelle)
        if meme and potager_id in (autre.potager_ids or []):
            return True
    return False


def notifier_nouvelle_connexion(db: Session, autorisation: McpAutorisation) -> int:
    """[CA5] Première connexion d'un membre à un assistant sur un potager PARTAGÉ : les autres membres sont
    prévenus par Telegram (« Camille a connecté ChatGPT à ce potager, en lecture »). Rend le nombre d'envois.
    Ne lève jamais : une notification manquée ne défait pas une connexion."""
    envoyes = 0
    try:
        auteur = db.get(User, autorisation.user_id)
        qui = (auteur.nom or auteur.email) if auteur else "Un membre"
        portee = "lecture" if autorisation.portee == "lecture" else "lecture et écriture"
        for potager_id in autorisation.potager_ids or []:
            if _deja_connecte(db, autorisation, potager_id):
                continue
            potager = db.get(Potager, potager_id)
            autres = (
                db.query(User).join(PotagerMembre, PotagerMembre.user_id == User.id)
                .filter(PotagerMembre.potager_id == potager_id, User.id != autorisation.user_id,
                        User.telegram_chat_id.isnot(None)).all()
            )
            texte = (f"{qui} a connecté {autorisation.libelle} à ce potager, en {portee}"
                     f" (« {potager.nom if potager else potager_id} »). "
                     "Les données lues partent chez l'éditeur de l'assistant.")
            for membre in autres:
                if telegram_notify.envoyer(membre.telegram_chat_id, texte) is not None:
                    envoyes += 1
    except Exception:  # noqa: BLE001
        log.exception("[US-294] Notification de connexion non envoyée (autorisation=%s)", autorisation.id)
    return envoyes


def assistants_du_potager(db: Session, potager_id: int) -> dict[int, list[dict]]:
    """[CA5] Par membre, les assistants actuellement connectés à ce potager : l'écran « Membres » les mentionne."""
    par_membre: dict[int, list[dict]] = {}
    for autorisation in db.query(McpAutorisation).filter(McpAutorisation.revoque_le.is_(None)).all():
        if potager_id in (autorisation.potager_ids or []) and _statut(db, autorisation) == STATUT_ACTIVE:
            par_membre.setdefault(autorisation.user_id, []).append(
                {"client": autorisation.libelle, "portee": autorisation.portee})
    return par_membre

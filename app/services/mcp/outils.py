"""
app/services/mcp/outils.py — Les outils du serveur MCP [US-290]
===============================================================

US-290 pose le socle et un seul outil, `lister_potagers`, qui suffit à vérifier une
connexion de bout en bout (CA10). Les lectures du catalogue (§5.1 de l'étude) vivent
dans `lectures.py` (US-291), les propositions d'écriture avec US-292 : elles s'enregistrent ici, au
même registre, et héritent des garde-fous de `serveur.appeler_outil`.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.services import calendrier_cultural as svc_calendrier
from app.services import potager_actif as svc_potager_actif
from app.services.mcp.serveur import AppelOutil, Outil, _peut_ecrire, enregistrer_outil
from app.services.permissions import LIBELLES_ROLE
from database.models import User


def _lister_potagers(db: Session, appel: AppelOutil) -> dict:
    """Les potagers que ce connecteur peut lire : rôle, potager actif, zone climatique."""
    connexion = appel.connexion
    utilisateur = db.query(User).filter(User.id == connexion.user_id).first()
    actif = utilisateur.potager_actif_id if utilisateur else None
    consentis = set(connexion.potager_ids)
    potagers = []
    for potager in svc_potager_actif.lister_potagers_utilisateur(db, connexion.user_id):
        if potager.id not in consentis or potager.assistants_externes_interdits:  # [US-294 / CA6]
            continue
        role = svc_potager_actif.role_utilisateur(db, connexion.user_id, potager.id)
        zone, _origine = svc_calendrier.zone_effective(potager)
        potagers.append({
            "id": potager.id,
            "nom": potager.nom,
            "role": LIBELLES_ROLE.get(role, role),
            "actif": potager.id == actif,
            "zone_climatique": zone,
            "ecriture_possible": connexion.ecriture and _peut_ecrire(role),
        })
    return {"potagers": potagers, "portee": connexion.portee}


enregistrer_outil(Outil(
    nom="lister_potagers",
    titre="Lister mes potagers",
    description=(
        "Liste les potagers du jardinier que ce connecteur peut lire : nom, identifiant, "
        "rôle du jardinier, potager actif, zone climatique, écriture possible ou non."
    ),
    executer=_lister_potagers,
    besoin_potager=False,
))


# US-291 : les dix lectures du catalogue s'enregistrent au même registre.
from app.services.mcp import lectures  # noqa: E402,F401
# US-292 : les propositions d'écriture (geste, correction, confirmer, abandonner).
from app.services.mcp import ecritures  # noqa: E402,F401
# US-293 : les commandes non destructives (proposer_commande) et les liens vers l'application.
from app.services.mcp import commandes  # noqa: E402,F401

"""
app/services/capacites/potagers.py — La capacité `lister_potagers` [US-290, US-338]
==================================================================================

US-290 a posé cette capacité, qui suffit à vérifier une connexion MCP de bout en bout (CA10). Elle vivait dans
`app/services/mcp/outils.py` ; depuis US-338 elle est au registre neutre, comme les lectures (`lectures.py`), les
propositions d'écriture (`ecritures.py`) et les commandes (`commandes.py`).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.services import calendrier_cultural as svc_calendrier
from app.services import potager_actif as svc_potager_actif
from app.services.capacites.registre import AppelCapacite, Capacite, enregistrer_capacite, peut_ecrire
from app.services.permissions import LIBELLES_ROLE
from database.models import User


def _lister_potagers(db: Session, appel: AppelCapacite) -> dict:
    """Les potagers que ce connecteur peut lire : rôle, potager actif, zone climatique."""
    connexion = appel.appelant
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
            "ecriture_possible": connexion.ecriture and peut_ecrire(role),
        })
    return {"potagers": potagers, "portee": connexion.portee}


enregistrer_capacite(Capacite(
    nom="lister_potagers",
    titre="Lister mes potagers",
    description=(
        "Liste les potagers du jardinier que ce connecteur peut lire : nom, identifiant, "
        "rôle du jardinier, potager actif, zone climatique, écriture possible ou non."
    ),
    executer=_lister_potagers,
    besoin_potager=False,
))


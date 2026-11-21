"""
app/services/capacites — Le registre de capacités, couche neutre [US-338]
=========================================================================

Le registre (`registre.py`) et ses capacités : `lister_potagers` (`potagers.py`), les dix lectures (`lectures.py`,
US-291), les propositions d'écriture (`ecritures.py`, US-292) et les commandes (`commandes.py`, US-293).
La capacité `situation_culture` (`situation.py`, US-339) rend le verdict de saison de la fiche culture.
Importer le paquet remplit le registre ; le serveur MCP n'en est qu'un adaptateur.
"""
from app.services.capacites import registre  # noqa: F401
from app.services.capacites import potagers  # noqa: E402,F401
from app.services.capacites import lectures  # noqa: E402,F401
from app.services.capacites import ecritures  # noqa: E402,F401
from app.services.capacites import commandes  # noqa: E402,F401
from app.services.capacites import situation  # noqa: E402,F401 — [US-339] situation_culture

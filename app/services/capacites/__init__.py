"""
app/services/capacites — Le registre de capacités, couche neutre [US-338]
=========================================================================

Le registre (`registre.py`) et ses capacités : `lister_potagers` (`potagers.py`), les dix lectures (`lectures.py`,
US-291), les propositions d'écriture (`ecritures.py`, US-292) et les commandes (`commandes.py`, US-293).
Importer le paquet remplit le registre ; le serveur MCP n'en est qu'un adaptateur.
"""
from app.services.capacites import registre  # noqa: F401
from app.services.capacites import potagers  # noqa: E402,F401
from app.services.capacites import lectures  # noqa: E402,F401
from app.services.capacites import ecritures  # noqa: E402,F401
from app.services.capacites import commandes  # noqa: E402,F401

"""
app/services/mcp/commandes.py — Alias [US-338]
=========================================

Les capacités vivent dans `app/services/capacites/commandes.py`, au registre neutre partagé par le compagnon et le
serveur MCP. Ce nom reste importable pour les appelants d'avant l'extraction : c'est le MÊME module (pas une copie),
un `monkeypatch` sur l'un vaut pour l'autre.
"""
import sys

from app.services.capacites import commandes as _module

sys.modules[__name__] = _module

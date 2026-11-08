"""
app/services/mcp — Le canal MCP : un assistant IA externe lit (et, si on l'autorise,
propose d'écrire dans) le potager du jardinier [US-290].

- `autorisation` : serveur d'autorisation OAuth 2.1 (PKCE), consentement, jetons
  opaques et jetons personnels ; la résolution d'un jeton en connexion.
- `serveur` : le protocole MCP (JSON-RPC sur HTTP), le registre des outils, les
  garde-fous de portée et de rôle, le plafond d'appels et le journal.
- `outils` : les outils exposés (US-290 : `lister_potagers` ; US-291 et suivantes
  ajoutent les leurs au même registre).

Aucune règle métier ici : les outils projettent les services existants, appelés sous
le `TenantContext` du jardinier, RLS comprise. Aucun appel à un modèle de langage.
"""

# Assistants IA connectés (MCP) — paragraphe destiné à la politique de confidentialité

**Produit par US-290 (CA3, limitation L17 de l'étude MCP). À intégrer par US-132 (RGPD &
conformité), avec `RGPD_FEDERATION_GOOGLE.md` et `RGPD_CARNET_COMPAGNON.md`.**

Le jardinier peut connecter son propre assistant IA (Claude, ChatGPT, Le Chat…) à son potager.
L'assistant lit alors les données du potager pour lui répondre. Cette fiche dit ce qui sort, ce
que nous gardons, et comment couper l'accès.

---

## Paragraphe à insérer — « Connecter votre assistant IA à votre potager »

> Vous pouvez autoriser un assistant IA que vous utilisez déjà (Claude, ChatGPT, Le Chat ou un
> autre) à consulter votre potager, et, si vous le cochez, à **proposer** des enregistrements
> que vous confirmez. Rien n'est connecté sans votre accord explicite : une page vous demande
> quels potagers partager et si l'assistant peut proposer des écritures (la lecture seule est
> le choix par défaut).
>
> **Ce que l'assistant lit quitte Assistant Potager.** Les données consultées (parcelles,
> cultures, gestes, notes, météo…) sont transmises à l'éditeur de l'assistant (par exemple
> Anthropic, OpenAI ou Mistral AI) et relèvent alors de **sa** politique de confidentialité,
> de conservation et d'entraînement. Nous ne pouvons ni les effacer chez lui, ni contrôler
> l'usage qu'il en fait.
>
> Dans un potager partagé, connecter votre assistant lui donne accès aux données communes,
> y compris les gestes et les notes des autres membres.
>
> De notre côté, nous conservons pour chaque connexion : l'assistant concerné, la portée
> accordée, les potagers choisis, et un journal des appels (date, outil appelé, potager,
> résultat, durée) — **jamais** le contenu de vos messages à l'assistant ni des textes
> échangés. Vous pouvez révoquer une connexion à tout moment depuis l'application ; l'accès
> est coupé immédiatement. La suppression de votre compte supprime toutes vos connexions.

---

## Pour l'équipe

- **Tables** (migration v69) : `mcp_clients`, `mcp_autorisations` (portée, potagers, révocation),
  `mcp_jetons` (empreinte SHA-256 seule), `mcp_codes_autorisation`, `mcp_appels` (journal, sans
  contenu libre). Tables de compte, sans RLS ; `ON DELETE CASCADE` depuis `users`.
- **Base légale** : consentement explicite, recueilli sur la page `/connecteur-ia` de la PWA
  (avertissement L17 affiché avant l'accord).
- **Durée de conservation du journal** : non bornée en v1 — à fixer avec US-132 (proposition :
  12 mois, comme une trace d'accès).
- **Prévenir les autres membres d'un potager partagé** (décision D6) : US-294 / CA5.
- **Code** : `app/services/mcp/`, `app/api/mcp.py`, `frontend/src/views/ConsentementConnecteur.jsx`.

**ID :** US-290
**Titre :** Connecter son assistant IA à son potager (serveur MCP authentifié)
**Épic :** ÉPIC 16 — Potager dans les assistants IA (MCP) *(numéro à valider, voir `docs/EPIC 16 - POTAGER DANS LES ASSISTANTS IA/ETUDE_MCP_POTAGER.md`)*

**Story :**
En tant que jardinier qui utilise déjà Claude, ChatGPT ou Le Chat
Je veux ajouter mon potager comme connecteur de mon assistant, en me connectant avec mon compte Assistant Potager
Afin que mon assistant puisse lire (et, si je l'autorise, proposer d'écrire) dans mon potager sans que je change d'outil

**Contexte fonctionnel :**
Socle de l'épic : un serveur MCP distant, hébergé sur le même domaine que l'API, joignable par une URL unique. Il ne porte aucune règle métier : il projette les registres existants et appelle les services sous le `TenantContext` du jardinier. Aucun appel LLM côté application sur ce canal. Voir l'étude §4 et §7.

**Critères d'acceptance :**
- [ ] CA1 : Une URL publique unique (ex. `https://potager.eremy.fr/mcp`) répond au protocole MCP en transport HTTP distant ; un client sans jeton reçoit une invitation à s'authentifier, jamais de données.
- [ ] CA2 : La connexion suit OAuth 2.1 avec PKCE : le jardinier se connecte avec son compte (e-mail ou Google), puis voit une page de consentement qui nomme l'assistant, la portée (lecture seule cochée par défaut, écriture à cocher) et le ou les potagers concernés.
- [ ] CA3 : La page de consentement avertit que les données lues partent chez l'éditeur de l'assistant et suivent sa politique de confidentialité (limitation L17).
- [ ] CA4 : Chaque appel construit le contexte locataire (utilisateur, potager, rôle) ; un potager hors du consentement ou dont le jardinier n'est pas membre est refusé, RLS comprise.
- [ ] CA5 : Les outils exposés dépendent de la portée et du rôle : portée lecture ou rôle `lecteur` → outils de lecture seulement ; un appel d'écriture forcé est refusé avec « Tu es lecteur sur ce potager » ou « Écriture non autorisée pour ce connecteur ».
- [ ] CA6 : Un plafond d'appels par minute et par jour s'applique par jeton ; au-delà, un message clair est rendu et rien n'est exécuté (L14).
- [ ] CA7 : Chaque appel est journalisé (date, client, outil, potager, résultat ok/refus/erreur, durée), sans le contenu des textes libres.
- [ ] CA8 : Un jeton révoqué (US-294) ou un compte supprimé coupe l'accès au plus tard à l'appel suivant.
- [ ] CA9 : Un jeton personnel, créé depuis la PWA, permet aussi la connexion des clients de développement (MCP Inspector, Claude Code) ; il porte la même portée et se révoque de la même façon.
- [ ] CA10 : La connexion est vérifiée de bout en bout avec au moins un client grand public (Claude) et MCP Inspector.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction assistant IA externe (nouveau canal `mcp`)
- Migration BDD requise : oui (clients OAuth, autorisations et jetons, journal des appels MCP)
- Dépendances : US-110 (JWT), US-113 (rôles), conception sécurisation API (quotas)
- Décisions liées : D1 (dans l'API ou à part), D2 (OAuth + jeton personnel), D3 (lecture seule par défaut)
- RGPD : mise à jour de la politique de confidentialité (`docs/RGPD/`)
- Fiche du corpus à créer : `data/connaissance/doc_app/assistants-ia-mcp.md` (US-099 / CA9), en lien avec US-295

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Given un jardinier membre "owner" du potager "Les Mésanges"
When il ajoute l'URL du connecteur dans Claude et se connecte
And il laisse cochée la seule portée "Lecture" sur "Les Mésanges"
Then Claude liste uniquement les outils de lecture
And un appel d'écriture forcé est refusé avec "Écriture non autorisée pour ce connecteur"
And l'appel figure dans le journal avec le résultat "refus"
```

**Labels GitHub :** `us`, `mcp`, `securite`, `api`

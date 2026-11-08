**ID :** US-294
**Titre :** Voir et révoquer les assistants IA connectés à son potager
**Épic :** ÉPIC 16 — Potager dans les assistants IA (MCP) *(numéro à valider, voir `docs/EPIC 16 - POTAGER DANS LES ASSISTANTS IA/ETUDE_MCP_POTAGER.md`)*

**Story :**
En tant que jardinier (et en tant que propriétaire d'un potager partagé)
Je veux voir quels assistants IA ont accès à mes potagers, ce qu'ils y ont fait, et pouvoir leur retirer l'accès
Afin de garder la maîtrise de mes données, qui partent chez un éditeur tiers dès qu'un assistant les lit

**Contexte fonctionnel :**
Écran « Assistants connectés » dans la PWA (compte). Il s'appuie sur les autorisations et le journal d'US-290. Il porte aussi la règle D6 pour les potagers partagés (L18).

**Critères d'acceptance :**
- [ ] CA1 : L'écran liste chaque connexion : nom du client (Claude, ChatGPT, Le Chat, jeton personnel…), date de connexion, dernier appel, portée (lecture / lecture + écriture), potagers concernés.
- [ ] CA2 : « Révoquer » coupe la connexion immédiatement (CA8 d'US-290) après confirmation ; la ligne passe en « Révoquée » avec la date.
- [ ] CA3 : « Activité » affiche les 100 derniers appels d'une connexion : date, outil, potager, résultat (ok / refusé / erreur) ; les écritures confirmées renvoient vers le geste dans le Journal.
- [ ] CA4 : Le jardinier peut créer un jeton personnel (CA9 d'US-290), affiché une seule fois, avec une portée et une date d'expiration.
- [ ] CA5 : Dans un potager partagé, la première connexion d'un membre à un assistant notifie les autres membres (« Camille a connecté ChatGPT à ce potager, en lecture ») ; l'écran « Membres » le mentionne.
- [ ] CA6 : Le propriétaire d'un potager peut interdire les assistants externes pour ce potager ; les connexions existantes perdent alors l'accès à ce potager, et la page de consentement ne le propose plus.
- [ ] CA7 : Un lien « Qu'est-ce que c'est ? » ouvre le mode d'emploi d'US-295 et rappelle que les données lues suivent la politique de l'éditeur de l'assistant (L17).
- [ ] CA type : Le rendu correspond visuellement à la maquette de référence à 375px/768px/desktop.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation, compte (PWA)
- Migration BDD requise : oui (réglage « assistants externes interdits » par potager ; le reste vient d'US-290)
- Dépendances : US-290 ; maquette à produire dans Claude Design
- Décision liée : D6
- Fiche du corpus : `potager-partage-et-roles.md` à compléter (US-099 / CA9)

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given Camille, membre "editor" du potager "Jardin partagé", connecte ChatGPT en lecture
Then Paul, propriétaire, reçoit "Camille a connecté ChatGPT à ce potager, en lecture"
When Paul interdit les assistants externes pour "Jardin partagé"
Then l'appel suivant de ChatGPT sur ce potager est refusé
And la connexion de Camille reste valable pour ses autres potagers
```

**Labels GitHub :** `us`, `mcp`, `pwa`, `rgpd`

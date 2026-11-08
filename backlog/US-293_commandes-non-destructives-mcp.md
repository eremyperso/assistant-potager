**ID :** US-293
**Titre :** Gérer parcelles et rappels depuis un assistant IA, sans destruction
**Épic :** ÉPIC 16 — Potager dans les assistants IA (MCP) *(numéro à valider, voir `docs/EPIC 16 - POTAGER DANS LES ASSISTANTS IA/ETUDE_MCP_POTAGER.md`)*

**Story :**
En tant que jardinier `editor` ou `owner` qui a autorisé l'écriture pour son assistant
Je veux que mon assistant puisse proposer de créer ou modifier une parcelle, programmer un rappel ou compléter le calendrier d'une culture
Afin d'organiser mon potager depuis mon assistant, en gardant les actions irréversibles dans l'application

**Contexte fonctionnel :**
Outils `proposer_commande` et `ouvrir_dans_l_application`. Seules les commandes **non destructrices** qui ont un exécuteur de service sont proposables (L6) ; leur liste vient de `FORMES_DICTABLES`, jamais d'une liste recopiée. Les destructions rendent un lien vers la carte, confirmée au bouton (L7).

**Critères d'acceptance :**
- [ ] CA1 : `proposer_commande` accepte les formes non destructrices qui ont un exécuteur de service (lot 1 d'US-289 : `/parcelle ajouter`, `/parcelle modifier` hors `actif=non` ; puis celles ouvertes par US-289 CA7 : rappel, calendrier, carnet…) ; la liste est lue du registre des commandes.
- [ ] CA2 : Une forme sans exécuteur de service est refusée avec « se fait encore dans Telegram » et la commande à taper.
- [ ] CA3 : Une forme destructrice (`/parcelle supprimer`, `/parcelle modifier actif=non`, annulation de geste, suppression de potager) n'est jamais proposée par `proposer_commande` ; `ouvrir_dans_l_application` rend un lien profond vers l'écran et l'action, et rien n'est exécuté.
- [ ] CA4 : La gestion des membres, des invitations, des rôles, de la clé BYOK et du compte n'est exposée par aucun outil (L5).
- [ ] CA5 : Le récapitulatif d'une modification donne l'avant → après (« Sud : 2 rangs → 3 rangs ») ; la confirmation suit CA8 et CA9 d'US-292 (atomique, trois fenêtres).
- [ ] CA6 : Un plan de plusieurs commandes s'exécute étape par étape, arrêt à la première en échec, avec le compte rendu ✅ ❌ ⏭ d'US-237.
- [ ] CA7 : Un refus du service (valeur invalide, nom déjà pris, parcelle disparue) est rendu avec sa raison ; rien n'est écrit.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement, administration du potager (canal `mcp`)
- Migration BDD requise : non
- Dépendances : US-292, US-289 (CA7 pour élargir la liste), US-237, US-260
- Le périmètre de cette US grandit avec US-289 CA7 sans nouvelle US : c'est le registre qui décide

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given la parcelle "planche test" existe dans "Les Mésanges"
When le jardinier dit à son assistant "supprime la planche test"
Then aucun outil d'écriture n'exécute la suppression
And l'assistant rend un lien vers la carte de suppression dans l'application
When le jardinier dit ensuite "passe la sud à 3 rangs"
Then l'assistant appelle proposer_commande et présente "Sud : 2 rangs → 3 rangs"
```

**Labels GitHub :** `us`, `mcp`, `commandes`

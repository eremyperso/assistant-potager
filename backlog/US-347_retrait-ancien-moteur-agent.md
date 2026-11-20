**ID :** US-347
**Titre :** Retirer l'ancien moteur de l'agent une fois la boucle à capacités mesurée
**Épic :** ÉPIC 20 — Compagnon client des capacités

**Story :**
En tant que porteur du produit
Je veux supprimer l'ancien moteur, son catalogue projeté, sa mémoire courte et ses règles de langage
Afin qu'un seul système interprète la phrase du jardinier et que la maintenance ne porte plus sur deux moteurs

**Contexte fonctionnel :**
Lot 5, §5 de `ARCHITECTURE_COMPAGNON_CAPACITES.md`. Le retrait est le **dernier** lot : il ne démarre que lorsque les lots 2 à 4 ont passé le jeu d'évaluation. L'arbitrage A1 fait de ce document la référence à la place du §12 d'`ARCHITECTURE_AGENT_INTERPRETEUR.md`.

**Retiré / gardé :**

| Élément | Sort |
|---|---|
| Catalogue projeté des commandes comme interface du modèle | Retiré (les formes dictables restent pour les commandes tapées) |
| Contexte court, ancre, question en attente | Retirés |
| Règles de langage autour du modèle (demande nouvelle, offre une action, refus…) | Retirées, sauf celles qu'une mesure garde (P7) |
| Texte réécrit par le code (relances, résumé de passage) | Retiré |
| Validateur, propositions, confirmation, exécution, actions menées | Gardés |
| Passerelle, `conso_tokens`, pilotage LLM | Gardés |
| Commandes tapées, boutons, cascade de `/ask` | Gardés |
| Parseur de gestes déterministe | Gardé seulement s'il bat la boucle à la mesure (A5) |

**Critères d'acceptance :**
- [ ] CA1 : Le dernier rapport de mesure montre que la boucle à capacités atteint les seuils du §7.2 sur les deux canaux, sans régression sur un critère à 100 %
- [ ] CA2 : Les éléments marqués « retiré » sont supprimés avec leurs tests ; l'interrupteur `COMPAGNON_MOTEUR` disparaît, la boucle devient le seul moteur
- [ ] CA3 : Chaque règle déterministe conservée est justifiée par une mesure qui la montre meilleure que le modèle ; la liste est écrite dans le dossier de l'épic
- [ ] CA4 : La suite de tests ne compte pas plus d'échecs qu'à HEAD avant le retrait
- [ ] CA5 : `ARCHITECTURE_AGENT_INTERPRETEUR.md` porte en en-tête un renvoi vers `ARCHITECTURE_COMPAGNON_CAPACITES.md` ; ses §2.2, §3.5 et §3.7 restent cités comme référence de la sécurité de l'écriture
- [ ] CA6 : `/help`, le guide utilisateur, la fiche `doc_app` du compagnon et la documentation de domaine sont mis à jour, puis le corpus est réingéré
- [ ] CA7 : Les US en cours sur l'ancien moteur sont tranchées selon A7 (terminées si elles servent l'évaluation ou la sécurité de l'écriture, sinon gelées) et leur ticket Jira mis à jour

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction (compagnon), documentation
- Migration BDD requise : non (les colonnes devenues inutiles d'`echanges_conversation` restent jusqu'à une migration de nettoyage séparée)
- Dépendances : US-342 à US-346 ; arbitrages **A1**, **A5**, **A7**
- Modèle / effort conseillé : **Sonnet 5.5, `high`** — suppression large, risque de code mort ou de dépendance oubliée

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given la boucle à capacités a passé le jeu d'évaluation sur la PWA et sur Telegram
When l'ancien moteur est retiré
Then toute phrase libre du jardinier est interprétée par la seule boucle à capacités
And les commandes tapées et les boutons fonctionnent comme avant
And aucune écriture ne se fait sans confirmation
```

**Labels GitHub :** `us`, `sprint-X`, `compagnon`, `refactoring`, `documentation`

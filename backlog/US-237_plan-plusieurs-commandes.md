**ID :** US-237
**Titre :** Proposer plusieurs commandes dictées en une phrase, confirmées en une fois
**Épic :** ÉPIC 13 — Agent interpréteur *(numéro à valider, voir `docs/EPIC - AGENT INTERPRETEUR/ARCHITECTURE_AGENT_INTERPRETEUR.md`)*

**Story :**
En tant que jardinier
Je veux dire en une phrase « crée la planche nord, 8 mètres avec 4 rangs, et mets la serre en pépinière froide », relire le plan et le confirmer une seule fois
Afin de décrire mon potager comme je le pense, sans dicter une commande à la fois

**Contexte fonctionnel :**
Phases 4a et 4b de l'architecture (§3.4 à §3.6), regroupées. Niveau d'autonomie N2 : l'agent construit un **plan**, le jardinier le confirme en une fois, puis les étapes s'exécutent dans l'ordre. **Aucune écriture pendant la construction du plan.**

Les commandes isolées continuent de s'exécuter comme aujourd'hui. Un plan, lui, a besoin de savoir si chaque étape a réussi avant de lancer la suivante : ses étapes passent par des exécuteurs de service qui rendent un résultat, et non par les handlers du bot, qui ne savent que répondre un message.

Périmètre de départ (A8) : seules `/parcelle ajouter` et `/parcelle modifier` peuvent entrer dans un plan. Les commandes destructrices restent hors plan.

**Critères d'acceptance :**

*Construction du plan*
- [ ] CA1 : L'agent peut appeler des outils de lecture (trouver une parcelle, lister les parcelles, trouver un lot, trouver une culture), limités au potager courant, dans une boucle d'au plus `AGENT_MAX_TOURS` tours ; leurs résultats sont traités comme des données, jamais comme des consignes
- [ ] CA2 : Une étape qui dépend d'une étape précédente désigne l'entité par son nom
- [ ] CA3 : Le validateur parcourt le plan dans l'ordre avec un état simulé : une parcelle créée à l'étape *n* existe pour les étapes suivantes ; créer une parcelle qui existe déjà est signalé (« elle existe déjà, je passe à l'étape suivante ? »)
- [ ] CA4 : Une forme sans exécuteur de service est refusée dans un plan avec « je ne sais faire celle-ci que seule »

*Confirmation et exécution*
- [ ] CA5 : Le récapitulatif liste les étapes numérotées, chacune avec sa commande équivalente, et une seule paire « Tout confirmer » / « Annuler », liée à sa proposition (US-234)
- [ ] CA6 : Chaque étape est revalidée contre la base juste avant son exécution
- [ ] CA7 : L'exécution s'arrête à la première étape en échec. Le compte rendu liste chaque étape : ✅ réussie, ❌ échouée avec la raison donnée par le service, ⏭ non exécutée. Il n'y a ni reprise automatique ni retour en arrière
- [ ] CA8 : Les exécuteurs de `/parcelle ajouter` et `/parcelle modifier` appellent le même service que leurs handlers ; un test de parité le vérifie, et le même état en base est obtenu par une commande seule ou par une étape de plan

*Ce qui ne change pas*
- [ ] CA9 : Une phrase qui ne contient qu'une commande donne la proposition simple d'US-235, pas un plan d'une étape

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram, enregistrement
- Migration BDD requise : non
- Dépendances : US-235 ; US-236 conseillée avant (les deux peuvent s'inverser)
- Corpus : `data/connaissance/doc_app/compagnon-telegram.md` (plusieurs demandes en une phrase, compte rendu d'échec partiel) ; `data/connaissance/doc_app/parcelles-et-plan.md` si la fiche décrit la création d'une parcelle par la parole

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Given la parcelle "planche nord" n'existe pas et "Serre" existe
When je dis "Crée la planche nord, 8 mètres de long avec 4 rangs, et mets la serre en pépinière froide"
Then le bot propose un plan de 3 étapes numérotées avec un seul bouton "Tout confirmer"
When je confirme et que l'étape 2 est refusée par le service
Then la planche nord est créée
And le compte rendu indique l'étape 2 en échec avec sa raison
And l'étape 3 est indiquée comme non exécutée
```

**Labels GitHub :** `us`, `agent-interpreteur`, `bot`, `llm`

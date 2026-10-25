**ID :** US-253
**Titre :** Anticiper la conséquence ou la suite logique d'une commande
**Épic :** ÉPIC 13 — Agent interpréteur *(numéro à valider, voir `docs/EPIC - AGENT INTERPRETEUR/ARCHITECTURE_AGENT_INTERPRETEUR.md`)*

**Story :**
En tant que jardinier
Je veux que le compagnon me prévienne de ce qu'une commande va entraîner, et me propose l'étape qui manque
Afin d'éviter une erreur coûteuse et de ne pas laisser mon potager à moitié renseigné

**Contexte fonctionnel :**
Le compagnon exécute fidèlement ce qui est demandé, mais ne regarde pas l'état du potager autour de la commande. Exemples : supprimer une parcelle qui porte encore des cultures ; déclarer une pépinière sans type ; ajouter une parcelle sans dimensions alors que le plan les attend. L'anticipation est **une information et une proposition**, jamais une action faite à la place du jardinier.

**Critères d'acceptance :**
- [ ] CA1 : Avant de confirmer une suppression ou un archivage, le récapitulatif signale ce qui en dépend (cultures en place, lots en pépinière) avec leur nombre.
- [ ] CA2 : Après une commande qui laisse une caractéristique utile vide (type de pépinière, longueur, nombre de rangs), le compagnon propose de la renseigner par des boutons, sans obligation.
- [ ] CA3 : Une proposition d'anticipation ne s'enchaîne jamais seule : chaque étape suggérée passe par la confirmation habituelle.
- [ ] CA4 : Au plus une suggestion de suite par commande, pour ne pas transformer chaque geste en questionnaire.
- [ ] CA5 : Les avertissements et suggestions sont calculés depuis les données du potager, sans appel au modèle.
- [ ] CA6 : Ignorer la suggestion ne bloque rien : la phrase suivante est traitée comme une demande nouvelle.
- [ ] CA7 : La fiche du corpus de fonctionnement qui décrit les commandes en une phrase est mise à jour.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram
- Migration BDD requise : non
- Dépendances : US-250, US-252, US-238

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given une parcelle "plantation" portant 12 pieds de tomate
When le jardinier écrit "supprimer la parcelle plantation"
Then le récapitulatif signale "12 pieds de tomate sont encore en place sur cette parcelle"
And la suppression n'a lieu qu'après confirmation

Given une parcelle "serre" sans type de pépinière
When le jardinier confirme "la serre est une pépinière"
Then le compagnon propose "Chaude" ou "Froide" pour préciser le type
```

**Labels GitHub :** `us`, `agent-interpreteur`, `commandes`, `anticipation`

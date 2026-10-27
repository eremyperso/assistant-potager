**ID :** US-277
**Titre :** Laisser à l'agent les phrases composées ou négatives que les règles déforment
**Épic :** ÉPIC 13 — Agent interpréteur *(numéro à valider, voir `docs/EPIC - AGENT INTERPRETEUR/ARCHITECTURE_AGENT_INTERPRETEUR.md`)*

**Story :**
En tant que jardinier
Je veux qu'une phrase qui demande deux actions, ou qui exprime un retrait, soit comprise en entier
Afin de ne jamais recevoir une proposition qui renomme ma planche en « planche des courges et supprime la planche nord », ou qui active le paillage quand je dis qu'il n'y en a plus

**Contexte fonctionnel :**
Lot 1 du cadrage `docs/EPIC - COMPAGNON CONVERSATIONNEL/CADRAGE_COMPAGNON_ACTIF.md`, à livrer **avant** US-276.

Le bot comprend une phrase en trois étages, dans cet ordre : les **règles** (reconnaissance sans modèle, instantanée et gratuite), le **filtre des gestes**, puis l'**agent** (Mistral). Les règles passent donc avant l'agent, et elles ont raison sur les phrases simples (« renomme la planche sud en planche des courges »).

La mesure US-256 rejouée par la cascade le 27/10/2026 montre qu'elles prennent aussi des phrases qu'elles ne savent pas lire, et qu'elles les déforment. C'est déjà le cas en production, indépendamment du modèle :

| Phrase du jardinier | Ce que proposent les règles aujourd'hui |
|---|---|
| « renomme la planche sud en planche des courges et supprime la planche nord » | Renommer « planche sud » en « planche des courges et supprime la planche nord » |
| « et la planche sud n'est plus paillée » | Paillage **activé** sur une parcelle nommée « et la planche sud n'est plus » |
| « mets la serre en pépinière froide et la planche centrale en pépinière chaude » | Une seule action (la serre en pépinière), sans le type « froide » ; la planche centrale est perdue |

La confirmation au bouton évite l'écriture, mais le jardinier lit une proposition fausse et doit tout redire. Le principe du §4.5 s'applique : le code garde ce dont il est sûr, et il passe le reste à l'agent. Les règles ne gardent que les phrases simples.

**Critères d'acceptance :**
- [ ] CA1 : Une phrase qui enchaîne deux demandes d'action (une liaison « et », « puis » ou une virgule, suivie d'un verbe d'action) n'est jamais traduite par les règles. Elle passe à l'agent.
- [ ] CA2 : Une phrase négative ou de retrait (« n'est plus », « ne … pas », « ne … plus », « plus de », « sans ») n'est jamais traduite par les règles. Elle passe à l'agent.
- [ ] CA3 : Une phrase qui commence par une liaison (« et la planche sud… », « et le tunnel aussi ») n'est jamais traduite par les règles : c'est la suite d'une demande précédente, que seul l'agent relie au contexte.
- [ ] CA4 : Les phrases simples restent prises par les règles, avec la même proposition qu'avant : « renomme la planche sud en planche des courges », « supprime la planche nord », « mets la serre en pépinière froide ».
- [ ] CA5 : Un nom de parcelle qui contient un de ces mots ne fait pas basculer la phrase (« renomme la planche sans nom en planche Est » reste une phrase simple si « planche sans nom » est une parcelle du potager).
- [ ] CA6 : Quand l'agent est indisponible ou désactivé (`AGENT_MODE` à `off`, quota, panne), une phrase écartée par les règles n'est pas traduite de travers. Le jardinier lit qu'elle n'a pas été traitée et ce qu'il peut taper à la place, comme pour une demande d'agir non comprise (INC-018).
- [ ] CA7 : Rejeu `tools/evaluer_dialogues.py` (US-256) sur Ministral 3B : PLU-1, PLU-2 et NEG-2 (tour 2) passent par l'agent. Aucun tour n'est pris par les règles avec une proposition déformée. Le rapport est commité avec la livraison.
- [ ] CA8 : Les fiches de `data/connaissance/doc_app/` qui décrivent ce que comprend le bot sont relues et corrigées si elles promettent qu'une phrase composée est comprise par les règles.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram (compréhension des commandes)
- Migration BDD requise : non
- Dépendances : US-256 (mesure par la cascade, CA9). Précède US-276
- Production conseillée : **Sonnet 5.5, effort `high`**. Le changement est petit, mais il touche à l'ordre des étages de compréhension et demande de couvrir les cas négatifs (CA4, CA5, CA6)

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given le potager contient les parcelles "Planche Sud" et "Planche Nord"
When le jardinier écrit "renomme la planche sud en planche des courges et supprime la planche nord"
Then les règles ne proposent aucun renommage
And la phrase est confiée à l'agent

When le jardinier écrit "et la planche sud n'est plus paillée"
Then aucune proposition n'active le paillage
And la phrase est confiée à l'agent

When le jardinier écrit "renomme la planche sud en planche des courges"
Then les règles proposent le renommage, comme avant
```

**Labels GitHub :** `us`, `agent-interpreteur`, `compagnon`, `comprehension`

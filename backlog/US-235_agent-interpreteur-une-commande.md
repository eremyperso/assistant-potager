**ID :** US-235
**Titre :** Comprendre une commande dictée par l'agent interpréteur, négations comprises
**Épic :** ÉPIC 13 — Agent interpréteur *(numéro à valider, voir `docs/EPIC - AGENT INTERPRETEUR/ARCHITECTURE_AGENT_INTERPRETEUR.md`)*

**Story :**
En tant que jardinier
Je veux dire une commande avec mes mots — « ma serre extérieure n'est plus une pépinière », « retire le paillage de la planche sud » — et recevoir la bonne proposition à confirmer
Afin de piloter mon potager sans connaître la tournure exacte que le bot attend

**Contexte fonctionnel :**
Phase 2 de l'architecture (§3.3 à §3.5). L'agent remplace le repli modèle actuel de l'interpréteur US-172, à la même place dans le flux et avec la même sortie : une proposition qui passe par le récapitulatif et la confirmation existants. **L'agent propose, il n'exécute jamais.**

Les règles de commande existantes passent toujours avant l'agent : ce qu'elles reconnaissent aujourd'hui ne change pas. À partir de cette US, on n'écrit plus de nouvelle règle pour couvrir une tournure (A3) : une tournure ratée devient une ligne du corpus d'évaluation.

**Révision explicite de CA4 d'US-172** (A1) : une valeur d'une liste fermée ou un oui / non peut être **déduit** du sens de la phrase. Les noms d'entités, les nombres et les textes libres doivent toujours venir de la phrase.

**Critères d'acceptance :**

*Catalogue*
- [ ] CA1 : Les outils sont générés depuis le catalogue des formes dictables et les caractéristiques de parcelle ; aucun outil n'est écrit à la main. Une quinzaine d'outils au plus, regroupés par commande
- [ ] CA2 : La modification d'une parcelle est un outil à champs typés (pépinière en oui / non, abri et exposition en listes fermées, longueur et rangs en nombres), traduit pour la commande existante sans la modifier
- [ ] CA3 : Un test de parité échoue si une forme dictable n'a pas d'outil, ou si un outil ne correspond à aucune forme

*Validation (§3.5, règles 1 à 6 et 9)*
- [ ] CA4 : Un nom de parcelle doit exister en base ; un nom voisin est **proposé**, jamais substitué (CA12 d'US-172) ; un nom inconnu déclenche une demande de précision
- [ ] CA5 : Un nombre doit avoir été dit, en chiffres ou en lettres
- [ ] CA6 : Une valeur fermée déduite n'est gardée que si le champ a été évoqué dans la phrase (son nom ou l'une de ses valeurs) ; sinon le champ est retiré de la proposition
- [ ] CA7 : Une commande destructrice exige un nom exact, jamais déduit
- [ ] CA8 : Le potager est toujours celui du contexte, jamais une valeur produite par le modèle
- [ ] CA9 : Le seuil de confiance ne s'applique pas sur ce chemin (A9) ; il reste en place sur l'ancien chemin

*Comportement*
- [ ] CA10 : « Ma serre extérieure n'est plus une pépinière » donne la proposition « je retire le statut pépinière de Serre extérieure », avec la commande équivalente affichée
- [ ] CA11 : Le récapitulatif nomme chaque champ modifié et son sens (« je **retire** », « je **passe à** 6 rangs »)
- [ ] CA12 : `AGENT_MODE=ombre` : le bot se comporte comme avant, et le journal enregistre ce que l'agent aurait proposé. `actif` : l'agent remplace l'ancien repli. `off` : l'agent n'est jamais appelé
- [ ] CA13 : Modèle indisponible (429, panne, outils non gérés) : retour silencieux au comportement actuel
- [ ] CA14 : Le journal des commandes interprétées porte `origine=agent` et le nom des outils appelés

*Seuil de mise en service*
- [ ] CA15 : L'évaluation réelle sur le corpus US-172 enrichi donne **0 exécution destructrice erronée** et aucune régression sur ce que les règles reconnaissent. Le passage de `ombre` à `actif` est un réglage, pas une livraison

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram, analyse
- Migration BDD requise : non, sauf si le journal des commandes n'a pas de place pour les noms d'outils (à vérifier en conception)
- Dépendances : US-233 (go du spike), US-234
- À ce stade, une phrase que l'agent ne prend pas comme commande poursuit son chemin habituel (routeur, cascade des questions) : l'aiguillage arrive avec US-236
- Corpus : `data/connaissance/doc_app/compagnon-telegram.md` (on peut dire une commande avec ses mots, négations comprises) ; `docs/domaines/commandes-bot.md` (révision de CA4, gel des règles)

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Given la parcelle "Serre extérieure" est une pépinière
And AGENT_MODE vaut actif
When je dis "Ma serre extérieure n'est plus une pépinière"
Then le bot propose "Je retire le statut pépinière de Serre extérieure"
And il affiche la commande équivalente "/parcelle modifier serre extérieure pepiniere=non"
When je confirme
Then "Serre extérieure" n'est plus une pépinière
```

**Labels GitHub :** `us`, `agent-interpreteur`, `bot`, `llm`

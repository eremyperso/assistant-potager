**ID :** US-328
**Titre :** Lister ce qui est à confirmer, à libérer et à placer aujourd'hui
**Épic :** ÉPIC 19 — Plan du potager sur vue du dessus *(numéro à valider)*

**Story :**
En tant que jardinier
Je veux qu'à l'ouverture du plan une colonne me dise ce qui m'attend aujourd'hui au potager
Afin de traiter les étapes à confirmer, les rangs à libérer et les cultures à placer sans les chercher sur le plan

**Contexte fonctionnel :**
Maquette de référence : `Plan - Pistes.html`, panneau de droite sans sélection (« Aujourd'hui au potager ») et principe « **Ce qui manque devient une tâche** ». Les cultures sans parcelle ne sont plus dessinées sur une zone fictive en fin de plan (ancienne carte « Cultures non localisées », US-200 / V17) : elles sont **listées**, jamais dessinées comme un lieu.

**Contenu :**

| # | Bloc | Contenu |
|---|---|---|
| A1 | En-tête | « Aujourd'hui au potager », date, température, alerte météo (« gel possible samedi ») |
| A2 | À confirmer · N | une ligne par culture à confirmer : emoji, nom, parcelle · rang, étape prévue, pastille « À confirmer » |
| A3 | À libérer · N | une ligne par culture terminée dont le rang n'est pas libéré, avec sa date de fin |
| A4 | À placer · N | les cultures sans rang : plants prêts d'un lot de pépinière, cultures dites au compagnon sans parcelle ; emoji, nom, variété, quantité, origine |
| A5 | Aide | « Glissez sur un rang libre du plan. Touchez une culture pour ouvrir son suivi. » |

**Règles :**
- Toucher une ligne A2 ou A3 ouvre le suivi de la culture (US-322)
- **Glisser** une carte « À placer » sur un rang libre du plan ouvre Gaston avec la proposition « Placer 12 fraisiers Mara des bois · Planche haricots, rang 2 », à confirmer : rien n'est écrit sans confirmation
- Sur mobile : deux boutons sous le plan, « N à confirmer » et « N à libérer », ouvrent la première culture de la liste ; le glisser-déposer n'existe pas (placement par Gaston, par la parole)

**Critères d'acceptance :**
- [ ] CA1 : Sans sélection, le panneau de droite affiche A1 à A5 ; chaque liste vide le dit (« Rien à confirmer »)
- [ ] CA2 : Les trois listes viennent du serveur, à la date de référence, avec les mêmes comptes que les filtres du plan (US-327)
- [ ] CA3 : La liste « À placer » regroupe les lots de pépinière prêts à planter et les cultures sans parcelle ; elle remplace la carte « Cultures non localisées »
- [ ] CA4 : Le glisser-déposer est utilisable au clavier (sélectionner la carte, puis le rang) et annoncé aux lecteurs d'écran ; il n'écrit rien, il ouvre Gaston avec la carte de placement
- [ ] CA5 : La confirmation du placement enregistre le rang et la part du rang (US-326) et, pour un lot, la plantation depuis ce lot
- [ ] CA6 : La météo vient des prévisions existantes (US-074, US-266) ; absente, la ligne disparaît sans erreur
- [ ] CA7 : Mobile : les boutons « à confirmer » et « à libérer » suivent la règle, cibles de 44 px
- [ ] CA type : Le rendu correspond visuellement à la maquette de référence à 375 px / 768 px / desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation et enregistrement (via le compagnon)
- Migration BDD requise : non
- Dépendances : **US-320** (étapes), **US-323** (contexte de Gaston), **US-326** (rang), **US-327** (plan) ; US-217 (où mettre les plants d'un lot, livrée) pour la liste des lots prêts
- Modèle / effort conseillé : Sonnet 5.5, `high` — glisser-déposer accessible et proposition de placement

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Ce qui m'attend aujourd'hui
  Given la levée des fèves et celle de l'épinard sont à confirmer
  And la tomate cerise est terminée depuis le 30 octobre
  When j'ouvre le Plan sans rien sélectionner
  Then "À confirmer · 2" liste la fève et l'épinard
  And "À libérer · 1" liste la tomate cerise

Scénario: Placer des fraisiers de la pépinière
  Given le lot #42 de fraisiers est prêt à planter
  When je glisse sa carte sur le rang 2 libre de la planche haricots
  Then Gaston propose "Placer 12 fraisiers · Planche haricots, rang 2"
  And rien n'est enregistré avant "Confirmer"
```

**Labels GitHub :** `us`, `frontend`, `backend`, `pwa`, `plan`

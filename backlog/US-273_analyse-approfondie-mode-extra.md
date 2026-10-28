**ID :** US-273
**Titre :** Analyser le potager en profondeur, sans rien modifier (mode Extra)
**Épic :** ÉPIC 15 — Compagnon dans la PWA *(numéro à valider, voir `docs/EPIC - COMPAGNON CONVERSATIONNEL/CADRAGE_COMPAGNON_ACTIF.md`)*

**Story :**
En tant que jardinier
Je veux demander une analyse approfondie de ma saison ou d'un problème
Afin d'obtenir une synthèse qui croise plusieurs lectures de mon potager

**Contexte fonctionnel :**
Lot 7 du cadrage ; mode Extra de l'étude d'articulation (§5.4). Usage le plus exigeant pour le modèle : c'est là qu'une montée de modèle a le plus de chances de se justifier, par `GROQ_MODEL_ANALYSE`, sans code (§4.5).

**Critères d'acceptance :**
- [ ] CA1 : Un bouton « Approfondir » (panneau PWA) et une commande équivalente dans le bot lancent l'analyse.
- [ ] CA2 : La boucle n'expose **que** des outils de lecture ; un test vérifie qu'aucun outil d'écriture n'est atteignable (R2).
- [ ] CA3 : Type d'appel `analyse`, bornes de tours et de jetons réglables ; au-delà, l'analyse rend ce qu'elle a avec une mention.
- [ ] CA4 : Les chiffres cités sont ceux lus ; les sources sont citées.
- [ ] CA5 : L'analyse peut finir par **proposer** des actions, jamais les exécuter.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse
- Migration BDD requise : non
- Dépendances : US-263, US-271
- Production conseillée : **Sonnet 5.5, effort `high`** — boucle de lecture seule réutilisant le registre d'outils ; le garde-fou R2 est structurel et testable.

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Given un potager avec une saison de récoltes enregistrée
When le jardinier clique "Approfondir" sur "pourquoi mes tomates ont peu donné ?"
Then une synthèse croise récoltes, météo et parcelles, avec ses sources
And aucune écriture n'a eu lieu
```

**Labels GitHub :** `us`, `compagnon`, `analyse`

**ID :** US-313
**Titre :** Suivre le coût et la rentabilité
**Épic :** ÉPIC 18 — Pilotage LLM

**Story :**
En tant qu'administrateur de la plateforme
Je veux voir ce que coûte l'assistant par jour, par jardinier actif et par échange
Afin de tenir un budget et de fixer un prix d'abonnement sur des chiffres mesurés

**Contexte fonctionnel :**
Vue « Coût » de la PWA d'administration. Les coûts viennent de `conso_tokens.cout_micro_eur` (US-309), au tarif public (décision D6).

**Critères d'acceptance :**
- [ ] CA1 : Un bandeau donne le coût de la période, le coût du mois en cours, la projection de fin de mois (moyenne des 7 derniers jours prolongée) et le coût par jardinier actif.
- [ ] CA2 : Un jardinier actif est un utilisateur ayant au moins une ligne de provenance `usage` sur la période ; la définition est affichée.
- [ ] CA3 : Un graphique par jour montre le coût, ventilé au choix par modèle, type d'appel ou canal.
- [ ] CA4 : Un bloc « coût d'un échange » donne la médiane, le P95 et le maximum, et le nombre médian d'appels par échange, par canal.
- [ ] CA5 : Un tableau classe les 10 potagers les plus coûteux de la période (coût, appels, part du total).
- [ ] CA6 : Un champ « prix d'abonnement mensuel envisagé » (gardé sur l'appareil, non enregistré) affiche la marge par jardinier actif médian et par jardinier au P95.
- [ ] CA7 : Les lignes sans coût (modèle absent de la grille) sont comptées et signalées : « n appels non chiffrés », avec la liste des modèles concernés.
- [ ] CA8 : Les montants sont affichés en euros avec la précision utile (millièmes sous 1 €) ; la version de grille tarifaire dominante de la période est affichée.
- [ ] CA9 : La mention « coût estimé au tarif public, hors palier gratuit » est visible.
- [ ] CA10 : Le rendu réutilise sans variante les composants de la maquette de référence de la vue Consommation (US-318) et reste conforme à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA d'administration)
- Cadrage : `docs/EPIC 18 - PILOTAGE LLM/CADRAGE_PILOTAGE_LLM.md` (numéro d'épic à valider)
- Migration BDD requise : non
- Dépendances : US-309, US-310, US-311, US-312 (composants), US-318 (maquette)
- Décisions liées : D5, D6
- Le classement par potager renvoie vers la fiche du potager d'US-319, qui porte le détail et l'inscription au registre RGPD.

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given sur 30 jours, 4 jardiniers actifs ont coûté 1,20 € au total
When j'ouvre la vue Coût sur 30 jours
Then le coût par jardinier actif affiche 0,30 €
When je saisis un prix d'abonnement de 3 €
Then la marge par jardinier médian est affichée
```

**Labels GitHub :** `us`, `pwa`, `admin`, `cout`

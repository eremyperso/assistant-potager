**ID :** US-059
**Titre :** Migrer les composants transverses de consultation vers le design system

**Story :**
En tant que jardinier utilisant l'interface web
Je veux que les éléments communs à tous mes écrans de consultation (filtre de culture, sélecteur de date, bandeau de métriques, panneau d'observations, écrans de chargement et d'erreur) aient partout la même apparence
Afin de ne pas avoir l'impression de passer d'une application à une autre en changeant d'onglet

**Contexte fonctionnel :**
Première US du Lot B de la refonte de l'interface web (voir `docs/ANALYSE_REFONTE_UI_WEB_2026.md` §7.3 et §7.4). Six composants sont partagés par les quatre écrans du lot (Plan, Pépinière, Stocks, Journal) : le sélecteur de date de référence, le filtre par culture, le bandeau de métriques, le panneau d'observations, l'écran de chargement et l'écran d'erreur. Ils portent encore 42 références aux alias de couleurs `--g-*` posés temporairement par US-052, et n'utilisent pas les composants du design system (`SearchField`, `Stat`, `Card`, `Badge`) qui font pourtant exactement leur travail.

Les traiter en premier, dans une US dédiée, évite que les quatre US d'écran retouchent les mêmes fichiers en concurrence, et les rend parallélisables ensuite. Cette US ne modifie **aucun comportement** : ni les données affichées, ni les appels au serveur, ni les interactions.

**Critères d'acceptance :**
- [ ] CA1 : Les six composants transverses (sélecteur de date de référence, filtre par culture, bandeau de métriques, panneau d'observations, écran de chargement, écran d'erreur) n'utilisent plus aucun alias de couleur `--g-*` ni classe `bg-g-*` / `text-g-*` / `border-g-*` — uniquement les tokens sémantiques de la nouvelle palette (`bg-surface`, `bg-card`, `text-txt`, `text-txt2`, `text-txt3`, `border-border`, `brand`, `amber`, `red`…)
- [ ] CA2 : Le filtre par culture s'appuie sur le composant de recherche du design system, et le bandeau de métriques sur le composant de statistique du design system, au lieu de redéfinir leur propre habillage
- [ ] CA3 : Le panneau d'observations (icône dépliante + liste des notes, US-039) reprend l'habillage de carte du design system, en conservant à l'identique le chargement à la demande et le compteur de notes affiché sur l'icône
- [ ] CA4 : Les composants susceptibles d'apparaître dans plusieurs contextes de mise en page (bandeau de métriques, icône et panneau d'observations) s'adaptent via `container-type: inline-size` et des règles `@container`, jamais via un breakpoint d'écran (règle non négociable de `CLAUDE.md`, section « Responsive frontend »)
- [ ] CA5 : Aucune régression fonctionnelle sur les quatre écrans qui consomment ces composants : la date de référence continue de filtrer les données à la date choisie, le filtre culture continue de filtrer côté client sans être persisté, l'écran d'erreur continue de proposer une nouvelle tentative, et les paramètres transmis par chaque écran restent inchangés
- [ ] CA type (US avec impact visuel/UI) : Le rendu de chacun de ces six composants correspond visuellement à la maquette de référence à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (interface web uniquement, aucune commande Telegram concernée)
- Migration BDD requise : non
- Dépendances : US-052 (tokens et composants du design system) — bloquante pour US-060, US-061, US-062 et US-063, qui consomment toutes ces six briques

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Apparence identique d'un écran à l'autre
  Given l'utilisateur consulte l'écran "Plan"
  When il bascule vers l'écran "Stocks" puis vers l'écran "Pépinière"
  Then le filtre par culture, le sélecteur de date de référence et le bandeau de métriques ont exactement la même apparence sur les trois écrans

Scénario: Non-régression du filtre par date de référence
  Given l'utilisateur a choisi une date de référence passée sur l'écran "Plan"
  When il consulte les cartes de parcelles
  Then les données affichées sont celles connues à cette date, comme avant la refonte

Scénario: Non-régression du panneau d'observations
  Given une parcelle porte trois observations
  When l'utilisateur clique sur l'icône d'observation de cette parcelle
  Then les trois notes se déplient sous la carte, chargées à la demande, et le compteur affiche bien 3
```

**Labels GitHub :** `us`, `sprint-refonte-ui-2026`, `frontend`, `design-system`

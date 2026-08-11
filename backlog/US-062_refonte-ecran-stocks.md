**ID :** US-062
**Titre :** Refondre l'écran Stocks avec bascule tableau / cartes

**Story :**
En tant que jardinier utilisant l'interface web
Je veux consulter mes stocks sous forme de tableau sur ordinateur et de cartes empilées sur téléphone
Afin de comparer rapidement plusieurs cultures en un coup d'œil sur grand écran, sans perdre en lisibilité sur mobile

**Contexte fonctionnel :**
Quatrième US du Lot B de la refonte de l'interface web (voir `docs/ANALYSE_REFONTE_UI_WEB_2026.md` §7.3). L'écran Stocks (`views/Stocks.jsx`) présente aujourd'hui, en cartes empilées uniquement, deux sections : les cultures au potager (avec leur origine, leur rendement cumulé et leurs pertes) et les lots en pépinière prêts à replanter. C'est le seul écran du lot pour lequel la maquette introduit un **changement de forme de présentation** : bascule tableau sur grand écran / cartes empilées sur mobile, à contenu strictement identique (§4). Il porte 39 références aux alias de couleurs `--g-*` (§7.4, point 1).

Refonte **strictement visuelle** : les données, leur regroupement et les appels serveur ne changent pas.

**Critères d'acceptance :**
- [ ] CA1 : Sur grand écran, les stocks s'affichent sous forme de tableau (une ligne par culture) ; sur petit écran, sous forme de cartes empilées. Les deux présentations affichent exactement les mêmes informations, aucune colonne n'est masquée en mobile ni ajoutée en desktop
- [ ] CA2 : La bascule entre tableau et cartes est pilotée par la largeur du conteneur (`container-type: inline-size` + `@container`) et non par un breakpoint d'écran (règle non négociable de `CLAUDE.md`)
- [ ] CA3 : Les deux sections sont conservées avec leurs intitulés et leur compteur de cultures : « Au potager » et « En pépinière — prêt à replanter »
- [ ] CA4 : Aucune régression fonctionnelle sur la section « Au potager » — sont conservés à l'identique : le stock de pieds avec son unité, les badges d'origine (pépinière, pied acheté, semis pleine terre, non localisé) portés par le composant de badge du design system, le rendement cumulé affiché dès qu'une récolte pesée existe, y compris pour les cultures végétatives (US-036), le nombre de pieds perdus, et les lignes de semis en pleine terre avec leur total semé
- [ ] CA5 : Aucune régression fonctionnelle sur la section « En pépinière » — sont conservés : le stock résiduel en godet, le taux de germination, et le détail des sorties du lot (repiqués, plantés, vendus, perdus)
- [ ] CA6 : Le filet de sécurité anti-double-comptage est préservé : une culture déjà présente dans les stocks au potager n'est jamais affichée une seconde fois en tant que semis en pleine terre, même si le serveur renvoie un chevauchement
- [ ] CA7 : Le sélecteur de date de référence, le filtre par culture, le bandeau de métriques (au potager / à replanter / perdus) et les observations agrégées par culture (US-039) sont conservés et utilisent les composants migrés par US-059
- [ ] CA8 : L'écran ne contient plus aucun alias de couleur `--g-*` ni classe `bg-g-*` / `text-g-*` / `border-g-*` — uniquement les tokens sémantiques de la nouvelle palette
- [ ] CA type (US avec impact visuel/UI) : Le rendu de l'écran correspond visuellement à la maquette de référence à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non
- Dépendances : US-052 (design system), US-053 (coquille de navigation), US-059 (composants transverses migrés)

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Bascule tableau vers cartes
  Given l'utilisateur consulte l'écran "Stocks" sur un écran de 1440px et voit un tableau
  When il redimensionne la fenêtre jusqu'à 375px
  Then le tableau laisse place à des cartes empilées affichant exactement les mêmes informations

Scénario: Non-régression du rendement des cultures végétatives
  Given une laitue dont plusieurs récoltes ont été pesées
  When l'utilisateur consulte l'écran "Stocks"
  Then le rendement cumulé de la laitue est affiché, comme pour une culture reproductrice

Scénario: Absence de double comptage
  Given une culture de haricots présente à la fois dans les stocks au potager et dans les semis en pleine terre renvoyés par le serveur
  When l'utilisateur consulte l'écran "Stocks"
  Then cette culture n'apparaît qu'une seule fois, dans les stocks au potager
```

**Labels GitHub :** `us`, `sprint-refonte-ui-2026`, `frontend`, `stocks`

**ID :** US-064
**Titre :** Clôturer la dette d'alias de couleurs sur le périmètre du Lot B

**Story :**
En tant qu'administrateur du projet
Je veux constater que tous les écrans refondus par le Lot B utilisent bien la palette de la nouvelle charte et savoir précisément ce qui reste à migrer ailleurs
Afin de ne pas laisser une dette technique invisible s'installer et de savoir à quelle condition les anciennes couleurs pourront être définitivement supprimées

**Contexte fonctionnel :**
Dernière US du Lot B de la refonte de l'interface web (voir `docs/ANALYSE_REFONTE_UI_WEB_2026.md` §7.4, point 1). Pour éviter de réécrire d'un coup les centaines d'occurrences des anciens noms de couleurs, US-052 les a redéfinies comme **alias pointant vers la nouvelle palette** : toute l'application affiche donc déjà les bonnes couleurs, mais chaque écran doit être migré vers les tokens sémantiques au fil des US.

Cette US vérifie que le périmètre du Lot B est entièrement propre. Elle **ne supprime pas** le bloc d'alias : celui-ci reste nécessaire pour l'écran Statistiques (dont la refonte a été rattachée au Lot D, puisqu'il devient un sous-écran du Tableau de bord) et pour trois vues hors du périmètre de la refonte (écran « aucun potager », ancien sélecteur de potager, écran de vérification d'e-mail). La suppression définitive est donc reportée au Lot D, et cette US en documente explicitement la condition.

**Critères d'acceptance :**
- [ ] CA1 : Aucun des quatre écrans du Lot B (Plan, Pépinière, Stocks, Journal) ni aucun des six composants transverses migrés par US-059 ne référence plus un alias de couleur `--g-*` ni une classe `bg-g-*` / `text-g-*` / `border-g-*`
- [ ] CA2 : Le bloc d'alias reste défini dans la feuille de styles et la configuration Tailwind, mais son commentaire est mis à jour pour recenser **nommément** les fichiers qui l'utilisent encore et le lot dont ils relèvent : l'écran Statistiques (Lot D), l'écran « aucun potager », l'ancien sélecteur de potager et l'écran de vérification d'e-mail
- [ ] CA3 : La condition de suppression du bloc d'alias est écrite noir sur blanc dans ce même commentaire : le bloc pourra être retiré dès que les quatre fichiers listés en CA2 auront été migrés, ce qui relève du Lot D et non du Lot B
- [ ] CA4 : Aucune régression visuelle sur les écrans hors périmètre : les quatre fichiers encore sur les alias continuent de s'afficher normalement, dans les deux thèmes
- [ ] CA5 : La dette résiduelle est reportée dans `docs/ANALYSE_REFONTE_UI_WEB_2026.md` §7.4, qui doit refléter le fait que la clôture du Lot B ne supprime pas les alias et indiquer ce qu'il reste à faire

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (dette technique frontend, aucun impact utilisateur attendu)
- Migration BDD requise : non
- Dépendances : US-059, US-060, US-061, US-062 et US-063 — toutes doivent être livrées avant cette US, qui est la dernière du lot

**Estimation :** 2 points

**Scénario Gherkin :**
```gherkin
Scénario: Périmètre du Lot B entièrement migré
  Given les cinq US précédentes du Lot B sont livrées
  When on recherche les anciens noms de couleurs dans les quatre écrans du lot et les six composants transverses
  Then aucune occurrence n'est trouvée

Scénario: Alias conservés et documentés
  Given l'écran Statistiques n'est pas encore refondu
  When on consulte la définition du bloc d'alias
  Then le bloc est toujours présent, accompagné de la liste nominative des fichiers qui l'utilisent encore et de la condition de sa suppression

Scénario: Aucune régression hors périmètre
  Given un utilisateur sans potager
  When il ouvre l'application en thème sombre
  Then l'écran "aucun potager" s'affiche normalement, sans couleur cassée
```

**Labels GitHub :** `us`, `sprint-refonte-ui-2026`, `frontend`, `dette-technique`

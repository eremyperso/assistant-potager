**ID :** US-063
**Titre :** Refondre l'écran Journal

**Story :**
En tant que jardinier utilisant l'interface web
Je veux relire l'ensemble de mes interventions dans un journal lisible et facile à filtrer
Afin de retrouver rapidement quand j'ai semé, arrosé ou récolté telle culture, sur téléphone comme sur ordinateur

**Contexte fonctionnel :**
Cinquième US du Lot B de la refonte de l'interface web (voir `docs/ANALYSE_REFONTE_UI_WEB_2026.md` §7.3). L'écran affiche la liste paginée des événements enregistrés, avec des pastilles de filtre par type d'action, un filtre par culture, un sélecteur de période et le sélecteur de date de référence. Il porte 54 références aux alias de couleurs `--g-*` (§7.4, point 1), dont un cas particulier : la couleur des pastilles d'arrosage est écrite en dur en hexadécimal, avec une seconde table de correspondance dédiée au thème sombre — un contournement que les tokens sémantiques rendent inutile.

Cette US achève par ailleurs le renommage « Historique → Journal » (§5.4) : le libellé affiché a été traité par US-053, il reste à aligner le nom du fichier de vue sur la clé de navigation `journal` déjà en place.

Refonte **strictement visuelle** : aucune donnée nouvelle, aucun changement dans les filtres transmis au serveur.

**Critères d'acceptance :**
- [ ] CA1 : La liste des événements reprend l'habillage de carte du design system, chaque ligne affichant la date, la pastille de type d'action, la culture et sa variété, la parcelle et la quantité avec son unité, conformément à la maquette
- [ ] CA2 : Les pastilles de type d'action utilisent exclusivement les tokens sémantiques de la nouvelle palette, y compris l'arrosage : plus aucune couleur hexadécimale écrite en dur, et plus de table de correspondance séparée pour le thème sombre — la bascule clair/sombre est assurée par les tokens eux-mêmes
- [ ] CA3 : Aucune régression fonctionnelle sur les filtres — sont conservés à l'identique : les pastilles de filtre par type d'action (Tous, Récolte, Semis, Plantation, Arrosage, Perte, Godet) avec leur état actif, le filtre par culture portant aussi sur la variété, le sélecteur de période avec ses deux dates et son bouton d'effacement, et le sélecteur de date de référence, qui reste prioritaire sur la date de fin de période comme aujourd'hui
- [ ] CA4 : La pagination est conservée : 20 événements par page, numéro de page courante, nombre total de pages et compteur total d'événements, avec les boutons précédent/suivant désactivés aux extrémités ; tout changement de filtre ramène à la première page
- [ ] CA5 : Sur grand écran, la liste adopte une mise en page adaptée à la largeur disponible plutôt que de s'étirer en lignes démesurées ; l'adaptation est pilotée par la largeur du conteneur (`container-type: inline-size` + `@container`) et non par un breakpoint d'écran (règle non négociable de `CLAUDE.md`)
- [ ] CA6 : Le fichier de vue est renommé pour porter le nom « Journal », en cohérence avec la clé de navigation `journal` et le libellé déjà affichés depuis US-053 — dernier reliquat du renommage décrit au §5.4
- [ ] CA7 : L'écran ne contient plus aucun alias de couleur `--g-*` ni classe `bg-g-*` / `text-g-*` / `border-g-*` — uniquement les tokens sémantiques de la nouvelle palette
- [ ] CA type (US avec impact visuel/UI) : Le rendu de l'écran correspond visuellement à la maquette de référence à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non
- Dépendances : US-052 (design system), US-053 (coquille de navigation et renommage du libellé), US-059 (composants transverses migrés)

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Pastille d'arrosage lisible dans les deux thèmes
  Given le journal contient des événements d'arrosage
  When l'utilisateur bascule du thème clair vers le thème sombre
  Then la pastille "arrosage" reste lisible et cohérente avec les autres pastilles, sans couleur codée en dur

Scénario: Non-régression de la pagination
  Given le journal contient 45 événements
  When l'utilisateur ouvre l'écran "Journal"
  Then 20 événements sont affichés, la pagination indique "Page 1 / 3" et le total de 45 événements

Scénario: Retour à la première page au changement de filtre
  Given l'utilisateur consulte la page 3 du journal
  When il active la pastille de filtre "Récolte"
  Then la liste revient à la première page des récoltes

Scénario: Priorité de la date de référence sur la période
  Given l'utilisateur a défini une date de référence et une date de fin de période
  When la liste se recharge
  Then c'est la date de référence qui borne les résultats, comme avant la refonte
```

**Labels GitHub :** `us`, `sprint-refonte-ui-2026`, `frontend`, `journal`

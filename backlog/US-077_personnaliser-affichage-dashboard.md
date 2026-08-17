**ID :** US-077
**Titre :** Personnaliser les widgets affichés sur la Vue d'ensemble du Tableau de bord

**Story :**
En tant que jardinier
Je veux choisir quels widgets apparaissent sur mon Tableau de bord
Afin de ne garder visible que les informations qui m'intéressent au quotidien

**Contexte fonctionnel :**
Quatrième US du Lot C, demandée explicitement au cadrage en même temps que le widget météo
(US-076), bien qu'elle relève par nature du Tableau de bord dans son ensemble (Lot D, non
cadré) plutôt que de la seule météo.

**Terminologie précisée au cadrage :** le mot « tip » utilisé initialement dans les échanges
désignait en réalité un **widget** — un des blocs de contenu du Tableau de bord (météo, à
faire cette semaine, récoltes de la saison, dernières interventions, les quatre déjà nommés
dans le `Placeholder` actuel de `App.jsx`). Personnaliser l'affichage = choisir lesquels de ces
widgets sont visibles ; ce n'est pas un catalogue de conseils textuels séparé.

**Aucune maquette Claude Design ne couvre ce composant précis.** Une exploration distincte du
projet (`pot-content.jsx`, écran Statistiques) montre un mécanisme de widgets glissables et
redimensionnables (« Personnalisez ce tableau de bord : glissez-déposez un bloc pour changer
son ordre… ») — mais c'est de la réorganisation/redimensionnement, pas du masquage. Le besoin
exprimé ici est plus simple : **afficher/masquer un widget**, sans réordonnancement ni
redimensionnement. Le réordonnancement pourra faire l'objet d'une US ultérieure si le besoin se
confirme à l'usage ; il n'est pas dans le périmètre de cette US.

Seul le widget météo (US-076) est aujourd'hui réel — les trois autres restent des
`Placeholder`. Le mécanisme de personnalisation doit néanmoins être générique : quand un futur
widget devient réel (Lot D), il doit suffire de l'enregistrer dans le catalogue des widgets
personnalisables, sans réécrire la modale.

**Décision assumée, à réviser si besoin :** le choix de widgets affichés est une préférence de
présentation personnelle, pas une donnée métier partagée par le potager — elle est stockée
côté client (navigateur), pas en base. Aucun nouvel endpoint, aucune migration. Conséquence
assumée : la préférence ne se synchronise pas entre appareils.

**Critères d'acceptance :**
- [ ] CA1 : Un bouton « Personnaliser l'affichage » est visible sur l'écran Vue d'ensemble
      (en tête d'écran, aux côtés du titre de page) et ouvre une modale listant les widgets
      disponibles (météo, à faire cette semaine, récoltes de la saison, dernières
      interventions), chacun avec une case à cocher
- [ ] CA2 : Décocher un widget le retire immédiatement de l'écran ; le recocher le restaure,
      sans perte du reste de la sélection
- [ ] CA3 : Le choix est mémorisé par utilisateur, localement (stockage navigateur), et
      persiste d'une session à l'autre sur le même appareil
- [ ] CA4 : Au moins un widget doit rester affiché en permanence — la modale empêche de
      décocher le dernier widget encore actif (pas d'état vide)
- [ ] CA5 : Le mécanisme est générique — le catalogue de widgets personnalisables est une liste
      déclarative unique ; ajouter un futur widget réel (Lot D) ne demande pas de modifier la
      structure de la modale
- [ ] CA6 : Masquer un widget encore en `Placeholder` (à faire cette semaine, récoltes de la
      saison, dernières interventions) le retire de l'écran comme n'importe quel widget réel —
      aucun traitement spécial pour les widgets non encore implémentés
- [ ] CA type (US avec impact visuel/UI) : Le rendu de la modale suit les conventions du design
      system (`Modal`, `Btn`, cases à cocher — US-052) à 375px/768px/desktop ; aucune maquette
      Claude Design dédiée n'existant, ce CA porte sur la cohérence avec le design system, pas
      sur une conformité pixel à une maquette de référence

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (préférence d'affichage)
- Migration BDD requise : non — préférence stockée côté client
- Dépendances : US-076 (au moins un widget réel à personnaliser), US-052 (design system, modale)
- Point ouvert assumé : pas de synchronisation multi-appareil de la préférence — à réviser si le besoin émerge

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Masquer un widget
  Given l'écran Vue d'ensemble avec ses quatre widgets affichés
  When l'utilisateur ouvre "Personnaliser l'affichage" et décoche "Dernières interventions"
  Then ce widget disparaît immédiatement de l'écran, les autres restent inchangés

Scénario: Préférence conservée après rechargement
  Given un utilisateur qui a masqué "Récoltes de la saison"
  When il recharge l'application sur le même navigateur
  Then "Récoltes de la saison" reste masqué, sans action supplémentaire

Scénario: Impossible de tout masquer
  Given un utilisateur qui n'a plus qu'un seul widget coché dans la modale
  When il tente de décocher ce dernier widget
  Then l'action est empêchée, au moins un widget reste sélectionné
```

**Labels GitHub :** `us`, `sprint-refonte-ui-2026`, `frontend`, `lot-c`

**ID :** US-060
**Titre :** Refondre l'écran Plan (liste des parcelles)

**Story :**
En tant que jardinier utilisant l'interface web
Je veux consulter l'occupation de mes parcelles dans une mise en page lisible aussi bien sur mon téléphone au potager que sur mon ordinateur
Afin de voir d'un coup d'œil quelles parcelles sont chargées et lesquelles sont encore libres, sans faire défiler une longue colonne unique sur grand écran

**Contexte fonctionnel :**
Deuxième US du Lot B de la refonte de l'interface web (voir `docs/ANALYSE_REFONTE_UI_WEB_2026.md` §7.3). L'écran Plan (`views/Plan.jsx`) est aujourd'hui une pile de cartes de parcelles conçue pour le mobile uniquement : depuis US-053 qui a retiré la contrainte de largeur maximale, ces cartes s'étirent sur toute la largeur d'un écran d'ordinateur, ce qui donne un rendu dégradé (§7.4, point 2). L'écran porte par ailleurs 29 références aux alias de couleurs `--g-*` à migrer (§7.4, point 1).

Il s'agit d'une refonte **strictement visuelle** : aucune donnée nouvelle, aucun appel serveur nouveau, aucune règle métier touchée.

**Critères d'acceptance :**
- [ ] CA1 : Les cartes de parcelle reprennent l'habillage de carte et la barre de progression du design system, avec la barre d'accent latérale colorée selon le taux d'occupation, conformément à la maquette
- [ ] CA2 : Sur grand écran, les cartes de parcelle se répartissent en plusieurs colonnes au lieu de s'étirer sur toute la largeur ; la bascule est pilotée par la largeur du conteneur (`container-type: inline-size` + `@container`) et non par un breakpoint d'écran (règle non négociable de `CLAUDE.md`)
- [ ] CA3 : Aucune régression fonctionnelle — sont conservés à l'identique : le code couleur d'occupation (vert sous 55 %, ambre de 55 à 79 %, rouge à partir de 80 %), le pourcentage de surface occupée, le badge « Libre » sur une parcelle sans culture, le compteur de cultures, l'exposition et la superficie, la pastille distinguant les cultures végétatives des reproductrices avec sa légende, le nombre de pieds par culture, la variété affichée à côté de la culture
- [ ] CA4 : Les observations (US-039) restent accessibles aux deux niveaux — sur la parcelle elle-même et sur chaque couple culture + variété — avec leur compteur, leur ouverture à la demande et le fait qu'un seul panneau reste ouvert à la fois
- [ ] CA5 : Le sélecteur de date de référence, le filtre par culture (filtrant à la fois sur le nom de parcelle et sur les cultures et variétés qu'elle contient) et le bandeau « parcelles actives / cultures en place » sont conservés et utilisent les composants migrés par US-059
- [ ] CA6 : L'écran ne contient plus aucun alias de couleur `--g-*` ni classe `bg-g-*` / `text-g-*` / `border-g-*` — uniquement les tokens sémantiques de la nouvelle palette
- [ ] CA7 : Les tuiles de sous-navigation « Vue plan » et « Rotation » restent en l'état (écran « à venir » posé par US-053) — leur contenu fonctionnel est hors périmètre, il relève du Lot G
- [ ] CA type (US avec impact visuel/UI) : Le rendu de l'écran correspond visuellement à la maquette de référence à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non
- Dépendances : US-052 (design system), US-053 (coquille de navigation), US-059 (composants transverses migrés)

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Mise en page multi-colonnes sur grand écran
  Given l'utilisateur consulte l'écran "Plan" avec six parcelles enregistrées
  When il affiche l'application sur un écran de 1440px
  Then les cartes de parcelle se répartissent sur plusieurs colonnes au lieu de s'étirer sur toute la largeur

Scénario: Repli en colonne unique sur mobile
  Given l'utilisateur consulte l'écran "Plan" sur un téléphone de 375px
  When la page s'affiche
  Then les cartes de parcelle s'empilent en une seule colonne, avec le même contenu que sur grand écran

Scénario: Non-régression du code couleur d'occupation
  Given une parcelle occupée à 85 % de sa surface
  When l'utilisateur consulte l'écran "Plan"
  Then la barre d'accent, le compteur de cultures et la barre de progression de cette parcelle sont en rouge

Scénario: Non-régression des observations à deux niveaux
  Given une parcelle porte deux observations et l'une de ses cultures en porte une
  When l'utilisateur ouvre le panneau d'observations de la culture
  Then seule la note de cette culture s'affiche, et le panneau de la parcelle se referme
```

**Labels GitHub :** `us`, `sprint-refonte-ui-2026`, `frontend`, `plan`

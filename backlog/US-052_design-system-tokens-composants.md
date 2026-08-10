**ID :** US-052
**Titre :** Poser les fondations du design system web (tokens et composants UI réutilisables)

**Story :**
En tant que jardinier utilisant l'interface web
Je veux une interface visuellement cohérente et responsive sur toutes les tailles d'écran
Afin de naviguer confortablement aussi bien sur mobile que sur tablette ou desktop

**Contexte fonctionnel :**
Première brique de la refonte de l'interface web (voir `docs/ANALYSE_REFONTE_UI_WEB_2026.md`, Lot A). Le frontend actuel (`frontend/src/`) est mobile-only, sans breakpoint desktop/tablette, avec des composants UI dupliqués par vue (`ParcellCard`, `CultureCard`, `StatTile`, `DonutRing`...) plutôt que factorisés. Cette US pose les tokens de la nouvelle palette et un socle de composants UI réutilisables, sans toucher à la navigation ni au contenu des écrans (traités dans les US suivantes du même lot).

**Critères d'acceptance :**
- [ ] CA1 : Les tokens de couleur actuels (`--g-bg`, `--g-acc`, `--g-amb`, `--g-red`…, thèmes clair "parchemin" et sombre "kaki forêt") sont remplacés par la nouvelle palette verte de la maquette (brand `#4A7C22` clair / `#8EC452` sombre, brandSoft, amber, red, blue, violet, txt/txt2/txt3), déclinée en thème clair et sombre, sans régression du mécanisme de bascule existant (toggle + persistance déjà en place via `useTheme.js`)
- [ ] CA2 : Les composants UI atomiques de la maquette (Card, Btn avec ses 4 variantes primary/ghost/soft/quiet, Badge, Stat, ProgressBar, MonthStrip, SearchField, Select, TileNav, InfoBanner, Tip) sont implémentés une seule fois dans un dossier `components/ui/` partagé, et non dupliqués par vue comme c'est le cas aujourd'hui
- [ ] CA3 : Tout composant de `components/ui/` destiné à apparaître dans plus d'un contexte de mise en page (ex. une `Card` affichée à la fois en pleine largeur et dans une grille) est construit avec `container-type: inline-size` sur son conteneur et des règles `@container` — pas de media query globale à l'intérieur de ces composants (règle non négociable, cf. `CLAUDE.md` section « Responsive frontend »)
- [ ] CA4 : La police Lora reste utilisée pour les titres et valeurs mises en avant, cohérente avec l'existant
- [ ] CA type (US avec impact visuel/UI) : Le rendu de chaque composant du design system correspond visuellement à la maquette de référence à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (interface web, aucune commande Telegram concernée)
- Migration BDD requise : non
- Dépendances : aucune — US fondatrice du chantier de refonte, bloquante pour US-053, US-054, US-055

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Bascule de thème sans régression
  Given un utilisateur affiche l'interface web en thème clair
  When il bascule vers le thème sombre
  Then tous les composants du design system (Card, Btn, Badge, Stat...) changent de palette sans perte de lisibilité

Scénario: Composant réutilisable indépendant de la taille de son conteneur parent
  Given une Card affichée en pleine largeur sur une page
  And la même Card affichée dans une grille à 3 colonnes sur une autre page
  When la largeur du conteneur parent change
  Then l'agencement interne de la Card s'adapte selon des règles @container, pas selon la largeur de l'écran
```

**Labels GitHub :** `us`, `sprint-refonte-ui-2026`, `frontend`, `design-system`

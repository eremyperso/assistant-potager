**ID :** US-053
**Titre :** Refondre la coquille applicative en navigation à deux niveaux

**Story :**
En tant que jardinier utilisant l'interface web
Je veux une navigation claire avec un niveau principal et des sous-sections par thème
Afin de retrouver rapidement une fonctionnalité sans naviguer à l'aveugle dans une liste plate d'onglets

**Contexte fonctionnel :**
Aujourd'hui, la navigation web (`TopBar.jsx` + `BottomNav.jsx`) n'a qu'un seul niveau (5 onglets à plat : Plan, Stocks, Pépinière, Historique, Stats), pas de header de page, et aucun layout desktop distinct. La maquette introduit une navigation à deux niveaux : navigation principale (6 entrées) dans un bandeau haut qui bascule en barre d'onglets basse sous 900px, et des tuiles de sous-navigation sous le titre de page pour les écrans qui en ont besoin. Voir `docs/ANALYSE_REFONTE_UI_WEB_2026.md` §5.1 pour le détail de la rupture structurante.

**Critères d'acceptance :**
- [ ] CA1 : Sur desktop/tablette large (≥ 900px), la navigation principale (Tableau de bord, Plan, Cultures, Pépinière, Stocks, Journal) s'affiche dans le bandeau du haut ; en dessous de 900px, elle bascule en barre d'onglets basse (4 onglets visibles + bouton « Plus » pour les 2 restants), sur le principe du `BottomNav.jsx` actuel mais avec les 6 entrées au lieu des 5 actuelles
- [ ] CA2 : Chaque écran affiche un en-tête de page (titre + sous-titre descriptif) sous le bandeau de navigation — nouveauté par rapport au `TopBar.jsx` actuel qui n'affiche qu'un titre court sans description
- [ ] CA3 : Les écrans qui ont des sous-sections (Tableau de bord → Vue d'ensemble/Statistiques ; Plan → Parcelles/Vue plan/Rotation) affichent des tuiles de sous-navigation sous l'en-tête de page ; les écrans sans sous-section (Cultures, Pépinière, Stocks, Journal) n'affichent pas cette zone
- [ ] CA4 : L'écran « Tableau de bord » devient le nouvel écran d'accueil par défaut au chargement de l'app, remplaçant « Plan »
- [ ] CA5 : Le renommage « Historique » → « Journal » est appliqué partout dans l'UI web (libellé de navigation, titre de page) ; le bot Telegram utilisant déjà « Journal du potager » par endroits, aucune incohérence supplémentaire n'est introduite
- [ ] CA6 : Les entrées « Vue plan » et « Rotation » (sous-tuiles de Plan) sont visibles et cliquables, et affichent un écran de type « à venir » explicite (pas d'erreur, pas de lien mort) — leur contenu fonctionnel complet est hors périmètre de cette US (chantier séparé, cf. Lot G du document d'analyse)
- [ ] CA type (US avec impact visuel/UI) : Le rendu de la navigation (bandeau haut, barre basse, tuiles) correspond visuellement à la maquette de référence à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non
- Dépendances : US-052 (design system) ; bloquante pour US-054 et US-055 (même coquille applicative)

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Scénario: Bascule desktop vers mobile
  Given l'utilisateur affiche l'interface web sur un écran de 1440px
  When il redimensionne la fenêtre en dessous de 900px
  Then la navigation principale disparaît du bandeau haut et apparaît en barre d'onglets basse

Scénario: Accès à une sous-section
  Given l'utilisateur est sur l'écran "Tableau de bord"
  When il clique sur la tuile "Statistiques"
  Then l'écran affiche les statistiques, avec la tuile "Statistiques" marquée comme active

Scénario: Écran d'accueil par défaut
  Given un utilisateur ouvre l'application web
  When l'application se charge
  Then l'écran "Tableau de bord" s'affiche en premier

Scénario: Sous-écran non implémenté sans lien mort
  Given l'utilisateur est sur l'écran "Plan"
  When il clique sur la tuile "Vue plan"
  Then un écran "à venir" explicite s'affiche, sans erreur ni page blanche
```

**Labels GitHub :** `us`, `sprint-refonte-ui-2026`, `frontend`, `navigation`

# US-023 : Socle technique frontend — initialisation, layout, auth, dark/light mode

**En tant que** : Admin  
**Je veux** : disposer d'une application web fonctionnelle avec navigation, authentification légère et support dark/light mode  
**Afin que** : toutes les vues suivantes (parcelles, stocks, pépinière, historique, graphiques) puissent être développées sur une base stable et cohérente

## Critères d'acceptation
- [ ] CA1 : L'application React (Vite) est initialisée avec Tailwind CSS, Shadcn/UI, Lucide React
- [ ] CA2 : Un layout commun existe : **bottom tab bar** mobile-first (onglets en bas, accessibles aux pouces) + topbar titre + zone de contenu principale
- [ ] CA3 : La bottom tab bar comporte **5 onglets** avec icône Lucide + label : Plan (`LayoutGrid`), Stocks (`BarChart`), Pépinière (`Sprout`), Historique (`List`), Stats (`AreaChart`)
- [ ] CA4 : Une authentification par token statique (header `Authorization`) protège toutes les routes — token configurable en variable d'environnement côté front
- [ ] CA5 : Dark mode / light mode fonctionnel via le `ThemeProvider` Shadcn — persisté en localStorage, icône de bascule dans la topbar
- [ ] CA6 : Un composant `ApiError` et un composant `LoadingSkeleton` génériques sont disponibles pour toutes les vues
- [ ] CA7 : L'application est buildable en statique (`npm run build`) et déployable sur Netlify
- [ ] CA8 : États gérés : loading skeleton, erreur API, données vides

## Composant UI ciblé
| Élément           | Librairie  | Composant exact                        | Props / variante                                         |
|-------------------|------------|----------------------------------------|----------------------------------------------------------|
| **Bottom tab bar**| Custom CSS | `<nav>` + `<button>` × 5              | `flex`, onglet actif : couleur `#1D9E75`, icône + label  |
| Topbar            | Custom CSS | `<header>` titre + icônes             | Refresh (`ti-refresh`) + ModeToggle (`ti-moon`)          |
| Thème             | Shadcn/UI  | `ThemeProvider` + `ModeToggle`        | dark / light / system                                    |
| Squelette charg.  | Shadcn/UI  | `<Skeleton />`                        | Réutilisé dans chaque vue                                |
| Erreur API        | Shadcn/UI  | `<Alert variant="destructive" />`     | Message + icône `AlertTriangle` Lucide                   |

## Données affichées
- **Source** : aucune (socle technique — pas de données métier dans cette US)
- **Format** : N/A
- **Fréquence refresh** : N/A

## Risques / Notes techniques
- Vite + React : bundle statique léger, pas de SSR → zéro impact RAM VPS au runtime
- Token statique suffit pour un admin unique — ne pas implémenter de système de rôles
- Déploiement Netlify : configurer `_redirects` pour le routing côté client (SPA)
- Bottom tab bar native CSS (pas `NavigationMenu` Shadcn qui est conçu pour desktop horizontal)

**Estimation :** 3 points  
**Labels GitHub :** `us`, `sprint-frontend`, `frontend`, `socle`

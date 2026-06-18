# US-028 : Vue graphiques — évolution des récoltes et semis sur la saison

**En tant que** : Admin  
**Je veux** : visualiser l'évolution de mes récoltes et semis sous forme de graphiques temporels, filtrables par culture et période  
**Afin que** : j'aie une lecture analytique de ma saison (pics de production, cycles) sans quitter l'interface web

## Critères d'acceptation
- [ ] CA1 : Un graphe en aire affiche les récoltes cumulées par semaine sur la saison courante
- [ ] CA2 : Un graphe en barres groupées compare semis vs récoltes vs pertes par culture
- [ ] CA3 : Un sélecteur de période permet de choisir : 7 jours, 30 jours, saison entière
- [ ] CA4 : Un sélecteur de culture (optionnel) filtre les graphes sur une culture précise
- [ ] CA5 : Les graphes sont responsives — lisibles sur mobile (simplification automatique via Recharts `ResponsiveContainer`)
- [ ] CA6 : Chaque point du graphe temporel affiche un tooltip : date, culture, quantité + unité
- [ ] CA7 : États gérés : loading skeleton, erreur API, aucune donnée sur la période sélectionnée

## Composant UI ciblé
| Élément                | Librairie  | Composant exact              | Props / variante                                         |
|------------------------|------------|------------------------------|----------------------------------------------------------|
| Récoltes dans le temps | Recharts   | `<AreaChart />`              | XAxis=semaine, YAxis=quantité, données `/historique`     |
| Comparaison par type   | Recharts   | `<BarChart />` groupé        | 3 séries : semis, récolte, perte                         |
| Sélecteur période      | Shadcn/UI  | `<Tabs />` ou `<Select />`   | "7j" / "30j" / "Saison"                                 |
| Sélecteur culture      | Shadcn/UI  | `<Select />` avec recherche  | Options issues de `GET /cultures`                        |
| Tooltip                | Recharts   | `<CustomTooltip />`          | Date + culture + quantité + unité                        |
| Skeleton graphe        | Shadcn/UI  | `<Skeleton />`               | Rectangle hauteur 200px                                  |

## Données affichées
- **Source** : endpoint FastAPI `GET /historique?from=&to=&culture=` (existant enrichi par US-027)
- **Agrégation** : côté client (regroupement par semaine en JS) — pas de nouvel endpoint
- **Format** : `{ events: [{ date, type_action, culture, quantite, unite }] }`
- **Fréquence refresh** : à chaque changement de filtre période ou culture

## Risques / Notes techniques
- L'agrégation hebdomadaire est réalisée en JS côté client — pas de charge supplémentaire sur le VPS
- `ResponsiveContainer` Recharts : obligatoire pour le rendu mobile — hauteur fixe recommandée (200px mobile, 350px desktop)
- Si la saison contient > 200 événements, envisager un endpoint `/stats/evolution` dédié plutôt que de charger tout l'historique

**Estimation :** 5 points  
**Dépendances :** US-023, US-027  
**Labels GitHub :** `us`, `sprint-frontend`, `frontend`, `analytique`

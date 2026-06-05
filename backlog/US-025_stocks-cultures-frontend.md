# US-025 : Vue stocks cultures en cours

**En tant que** : Admin  
**Je veux** : consulter en un coup d'œil les stocks de toutes mes cultures (végétatives et reproductrices) avec quantités et unités  
**Afin que** : je sache ce qu'il me reste à récolter ou ce qui a déjà été perdu, sans ouvrir le bot Telegram

## Critères d'acceptation
- [ ] CA1 : La vue présente deux sections distinctes : "Cultures végétatives" et "Cultures reproductrices"
- [ ] CA2 : Pour chaque culture : nom, nombre de plants actifs, quantité récoltée ou perdue (avec unité)
- [ ] CA3 : Un graphe en barres compare le semis/plantation vs la récolte vs la perte par culture
- [ ] CA4 : Une section "Semis en cours" liste les cultures semées non encore plantées (avec quantité restante)
- [ ] CA5 : Un filtre texte permet de rechercher une culture dans le tableau
- [ ] CA6 : États gérés : loading skeleton, erreur API, aucun stock enregistré

## Composant UI ciblé
| Élément               | Librairie    | Composant exact                     | Props / variante                                    |
|-----------------------|--------------|-------------------------------------|-----------------------------------------------------|
| Tableau cultures      | Shadcn/UI    | `<DataTable />` (TanStack Table)    | Colonnes : culture, plants, récolté, perdu          |
| Filtre recherche      | Shadcn/UI    | `<Input />` + `<Search />` Lucide   | Filtre côté client (TanStack)                       |
| Graphe comparatif     | Recharts     | `<BarChart />`                      | Semis vs récolte vs perte, groupé par culture       |
| Badge type organe     | Shadcn/UI    | `<Badge />`                         | vert=végétatif, orange=reproducteur                 |
| Section semis         | Shadcn/UI    | `<Card />` + liste `<Badge />`      | Quantité restante mise en avant                     |

## Données affichées
- **Source** : endpoint FastAPI `GET /stats` (existant)
- **Format** : `{ vegetatif: [...], reproducteur: [...], semis: [...] }`
- **Fréquence refresh** : manuel (bouton)

## Risques / Notes techniques
- TanStack Table : pagination côté client suffisante (< 50 cultures attendues) — pas de pagination serveur
- Le `<BarChart />` Recharts peut être lourd sur mobile si nombreuses cultures — limiter à 10 cultures par défaut avec option "voir tout"

**Estimation :** 5 points  
**Dépendances :** US-023  
**Labels GitHub :** `us`, `sprint-frontend`, `frontend`, `consultation`

## Scénarios Gherkin

```gherkin
Feature: Vue stocks cultures

  Scenario: Affichage des deux sections
    Given l'API /stats retourne des cultures végétatives et reproductrices
    When l'utilisateur ouvre la vue Stocks
    Then deux sections distinctes "Cultures végétatives" et "Cultures reproductrices" sont visibles

  Scenario: Filtre de recherche
    Given la vue Stocks est chargée avec plusieurs cultures
    When l'utilisateur saisit "tomate" dans le champ de recherche
    Then seules les lignes dont le nom contient "tomate" sont affichées

  Scenario: Graphe comparatif
    Given la vue Stocks est chargée
    Then un graphe en barres groupées (planté / récolté / perdu) est affiché
    And il est limité aux 10 premières cultures

  Scenario: État vide
    Given l'API /stats retourne une liste stock_par_culture vide
    When l'utilisateur ouvre la vue Stocks
    Then le message "Aucun stock enregistré" est affiché

  Scenario: Erreur API
    Given l'API /stats retourne une erreur
    When l'utilisateur ouvre la vue Stocks
    Then le composant ApiError est affiché avec un bouton de retry
```

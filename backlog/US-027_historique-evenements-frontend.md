# US-027 : Vue historique des événements — tableau filtrable

**En tant que** : Admin  
**Je veux** : consulter l'historique complet des actions enregistrées avec filtres par culture, action et période  
**Afin que** : je puisse retrouver un événement précis ou auditer l'activité de ma saison sans passer par le bot

## Critères d'acceptation
- [ ] CA1 : Chaque ligne affiche : date, badge action coloré, culture + variété, parcelle, quantité + unité
- [ ] CA2 : La liste est paginée (20 lignes par page) avec chevrons de navigation accessibles aux pouces
- [ ] CA3 : Un filtre texte "culture" réduit les résultats en temps réel côté client
- [ ] CA4 : Un filtre **chips horizontaux défilants** (Tous / Récolte / Semis / Plantation / Arrosage…) remplace le Select — interaction plus rapide sur mobile
- [ ] CA5 : Un bouton "Période" (icône calendrier) ouvre un `<DatePicker />` double pour filtrer `from` / `to` côté serveur
- [ ] CA6 : Le badge coloré par `type_action` suit la palette : teal=récolte, bleu=arrosage, orange=semis, vert=plantation, gris=désherbage, rouge=perte
- [ ] CA7 : États gérés : loading skeleton (lignes fantômes), erreur API, historique vide

## Composant UI ciblé
| Élément             | Librairie    | Composant exact                     | Props / variante                                         |
|---------------------|--------------|-------------------------------------|----------------------------------------------------------|
| Chips filtre action | Custom CSS   | `<div class="filter-bar">` + chips  | Défilement horizontal, chip actif couleur teal           |
| Filtre culture      | Shadcn/UI    | `<Input />`                         | Filtre client-side sur le jeu de données courant         |
| Sélecteur période   | Shadcn/UI    | `<DatePicker />` double             | `from` / `to` → query params FastAPI, debounce 300ms     |
| Ligne événement     | Custom CSS   | `<div class="table-row">`           | Date / Badge / Culture+Variété+Parcelle / Quantité       |
| Badge action        | Shadcn/UI    | `<Badge />`                         | Couleur selon `type_action` (palette ci-dessus)          |
| Pagination          | Custom CSS   | Chevrons `<i>` + numéro page        | `Page X / N`, chevrons larges accessibles mobile         |
| Skeleton lignes     | Shadcn/UI    | `<Skeleton />`                      | 20 lignes de hauteur fixe                                |

> ⚠️ Le `<Select />` Shadcn pour le filtre action est **remplacé par des filter chips horizontaux défilants** (validé maquette + recommandation UX mobile).

## Données affichées
- **Source** : endpoint FastAPI `GET /historique?from=&to=&limit=20&offset=0` (**à enrichir** — retourne actuellement les 10 derniers fixes)
- **Format** : `{ total: int, events: [{ id, date, type_action, culture, variete, quantite, unite, parcelle }] }`
- **Fréquence refresh** : à chaque changement de filtre période (requête serveur) — filtre culture en client-side

## Risques / Notes techniques
- `GET /historique` sans pagination ni filtres date = **point bloquant backend** à traiter avant le sprint frontend
- Debounce 300ms obligatoire sur le DatePicker pour éviter les appels en rafale sur Scaleway 1 Go RAM
- TanStack Table : pagination côté client suffisante si < 500 événements chargés ; au-delà, pagination serveur nécessaire

**Estimation :** 5 points  
**Dépendances :** US-023  
**Labels GitHub :** `us`, `sprint-frontend`, `frontend`, `consultation`

## Scénarios Gherkin

```gherkin
Feature: Vue historique événements

  Scenario: Affichage liste paginée
    Given l'API /historique retourne 20 événements
    When l'utilisateur ouvre la vue Historique
    Then 20 lignes sont affichées avec date, badge action, culture, parcelle, quantité

  Scenario: Filtre par type d'action (chips)
    Given la vue Historique est chargée
    When l'utilisateur clique sur le chip "Récolte"
    Then seuls les événements de type "recolte" sont visibles
    And le chip "Récolte" est mis en surbrillance teal

  Scenario: Filtre texte culture
    Given la vue Historique est chargée avec des événements tomate et salade
    When l'utilisateur saisit "tomate" dans le champ culture
    Then seules les lignes dont la culture contient "tomate" sont affichées

  Scenario: Filtre période côté serveur
    Given la vue Historique est chargée
    When l'utilisateur sélectionne from=2026-05-01 et to=2026-05-31
    Then l'API est appelée avec from=2026-05-01&to=2026-05-31
    And les résultats sont rechargés depuis le serveur

  Scenario: Pagination
    Given l'API retourne total=45 événements
    When l'utilisateur est sur la page 1
    Then "Page 1 / 3" est affiché
    When l'utilisateur clique sur le chevron suivant
    Then l'API est appelée avec offset=20

  Scenario: État vide
    Given l'API /historique retourne evenements=[]
    Then le message "Aucun événement enregistré" est affiché

  Scenario: Erreur API
    Given l'API /historique retourne une erreur 500
    Then le composant ApiError est affiché avec bouton retry
```

# US-014 — Corriger l'affichage des semis dans /stats et /stats [culture]

## Contexte

Le potager suit des **itinéraires culturaux décalés** : une même culture (ex: courgette)
peut avoir des plants déjà en production ET de nouveaux semis lancés plus tard pour un
deuxième cycle. Ce sont des lots indépendants.

Deux bugs sont identifiés dans la commande `/stats` :

### Bug #1 — /stats global : les récoltes des plantations apparaissent dans la section Semis

`calcul_semis()` (utils/stock.py) agrège toutes les récoltes d'une culture et les associe
aux semis par simple correspondance de nom de culture. Or, une récolte est toujours liée
à une **plantation** (plants en terre), jamais à un **semis** (graines en cours de
germination). Il n'existe aucun lien DB entre un semis et une récolte.

**Avant** :
```
🌱 Semis :
  • courgette : 20 graines (1 semis) · 10.01 kg récoltés (2 fois)   ← FAUX
```
**Après** :
```
🌱 Semis :
  • courgette : 20 graines (1 semis)
```

### Bug #2 — /stats [culture] : les semis sont absents de la vue détail par variété

`calcul_stock_par_variete()` ne requête que plantations/pertes/récoltes. Les semis sont
ignorés. De plus, un `return []` si aucune plantation bloque l'affichage même si des
semis existent.

**Avant** :
```
🍅 Courgette — détail par variété
🔸 jaune  • 10 plants actifs (planté 10)  📅 11 avr → en cours
```
**Après** :
```
🍅 Courgette — détail par variété
🔸 jaune  • 10 plants actifs (planté 10)  📅 11 avr → en cours
           🌱 20 graines semées · 📅 20 avr
```

## Critères d'acceptance

### CA1 — /stats global : pas de récoltes dans la section Semis
- Given: une culture a des semis ET des plantations avec récoltes
- When: /stats est affiché
- Then: la section Semis n'affiche que nb_semis et quantité semée, jamais de récoltes

### CA2 — /stats global : les semis sans quantité s'affichent correctement
- Given: un semis sans quantite (NULL)
- When: /stats est affiché
- Then: "• persil : 1 semis" (pas de crash)

### CA3 — /stats [culture] : les semis apparaissent dans le bloc de leur variété
- Given: une culture a des semis variété "jaune" et une plantation variété "jaune"
- When: /stats courgette est demandé
- Then: le bloc variété "jaune" affiche "🌱 20 graines semées · 📅 20 avr"

### CA4 — /stats [culture] : les semis sans variété correspondante s'affichent séparément
- Given: une culture a des semis sans variété mais des plantations avec variétés
- When: /stats [culture] est demandé
- Then: une section "🌱 Semis sans variété correspondante" est ajoutée en bas

### CA5 — /stats [culture] : culture avec uniquement des semis (pas de plantation)
- Given: une culture a des semis mais aucune plantation
- When: /stats [culture] est demandé
- Then: la section Semis est affichée (pas de "Aucune donnée")

### CA6 — Non-régression : les récoltes restent correctement dans la section Plantations
- Given: des plantations avec récoltes
- When: /stats est affiché
- Then: les récoltes apparaissent dans 🥬/🍅, pas dans 🌱

### CA7 — Non-régression : /stats [culture] sans semis reste inchangé
- Given: une culture sans semis (ex: salade)
- When: /stats salade est demandé
- Then: pas de section Semis affichée, comportement identique à avant

## Scénarios Gherkin

```gherkin
Feature: Affichage correct des semis dans /stats

  Scenario: CA1 - Semis sans récoltes dans /stats global
    Given une culture "courgette" avec 1 semis de 20 graines
    And des plantations de courgette avec 10.01 kg récoltés
    When l'utilisateur demande /stats
    Then la section Semis affiche "courgette : 20 graines (1 semis)"
    And la section Semis n'affiche PAS "récoltés"

  Scenario: CA3 - Semis intégrés au bloc variété dans /stats [culture]
    Given une culture "courgette" avec semis variété "jaune" de 20 graines le 20 avr
    And une plantation variété "jaune" de 10 plants
    When l'utilisateur demande /stats courgette
    Then le bloc "jaune" contient "🌱 20 graines semées"
    And le bloc "jaune" contient "📅 20 avr"

  Scenario: CA5 - Culture avec uniquement des semis
    Given une culture "basilic" avec 1 semis et aucune plantation
    When l'utilisateur demande /stats basilic
    Then une section Semis est affichée avec les données du semis
    And aucun message "Aucune donnée" n'est retourné

  Scenario: CA7 - Culture sans semis inchangée
    Given une culture "salade" avec plantations et récoltes, sans semis
    When l'utilisateur demande /stats salade
    Then aucune section Semis n'apparaît
    And le stock de plants est correct
```

## Composants fonctionnels impactés

| Fichier | Fonction | Changement |
|---------|----------|-----------|
| `utils/stock.py` | `calcul_semis()` | Supprimer le fetch récoltes |
| `utils/stock.py` | `calcul_stock_par_variete()` | Ajouter fetch semis par variété |
| `utils/stock.py` | `calcul_semis_par_culture()` | CRÉER — semis filtrés par culture+variété |
| `bot.py` | `cmd_stats` section Semis | Retirer affichage récoltes (l.1963-1966, 1976-1979) |
| `bot.py` | `cmd_stats` mode détail | Ajouter affichage semis dans bloc variété |

## Dépendances

- Aucune migration SQL nécessaire (données existantes)
- US-002 (stock végétatif/reproducteur) — non impactée

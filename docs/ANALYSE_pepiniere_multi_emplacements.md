# Analyse — Suivi spatial de la pépinière (préparation US)

> Document d'analyse technique, à destination de l'agent PO pour la rédaction d'une future User Story.
> Ce n'est **pas** une US formatée — c'est le constat qui doit nourrir sa rédaction.
> Date de l'analyse : 2026-07-17.

## Contexte

En validant l'US-041 (couche `app/services/`) sur une base de dev contenant 6 parcelles dont une
serre marquée pépinière (`est_pepiniere = true`), un comportement a été observé : la vue **Plan**
du dashboard n'affiche jamais rien sur la parcelle Serre, alors que la vue **Stocks > Pépinière**
affiche bien des plants en godet et des semis en attente. Cette différence a été investiguée — ce
n'est pas un bug, c'est la conséquence directe de la logique existante décrite ci-dessous.

## Constat — comportement actuel

### 1. Le Plan ignore délibérément les parcelles pépinière

`calcul_occupation_parcelles()` (`utils/parcelles.py:387`) ne peuple une parcelle qu'à partir de
deux types d'événements :
- `plantation`, sans restriction
- `semis`, **uniquement si la parcelle n'est pas marquée `est_pepiniere`** (`_cond_semis_pleine_terre`,
  introduite en migration_v13 / US-037)

Un semis rattaché à une parcelle pépinière est donc **explicitement exclu** de l'occupation du sol.
C'est un choix voulu : le Plan sert à la rotation de culture en pleine terre, pas au suivi de la
pépinière.

### 2. Les mises en godet ne sont jamais localisées, quel que soit le nombre de pépinières

Un événement `mise_en_godet` est créé avec `parcelle_id = NULL` codé en dur
(`app/services/evenements.py::creer_evenement_godet`, hérité du comportement historique de
`bot.py::_save_godet_item`). Peu importe où sont physiquement les godets (serre, châssis, étagère
intérieure...), l'événement n'est **jamais** rattaché à une parcelle. Avoir plusieurs parcelles
pépinière ne change donc rien pour les godets : ils ne sont localisés nulle part.

### 3. Les stocks de pépinière sont agrégés uniquement par (culture, variété), jamais par lieu

`calcul_godets()` et `calcul_semis()` (`utils/stock.py`) — utilisés par les endpoints
`GET /godets`, `GET /godets/detail`, `GET /stats` et par `/stats` côté bot — regroupent les
événements pépinière (semis + godets) exclusivement par `(culture, variété)`. La parcelle
d'origine n'entre jamais dans la clé d'agrégation.

## Problème identifié

**Le modèle de données actuel ne supporte pas plusieurs emplacements de pépinière distincts.**

Si un jardinier déclare deux parcelles pépinière (ex. "Serre" et "Châssis froid") et sème 50 graines
de carotte dans l'une et 30 dans l'autre :
- Le Plan continuera de ne rien afficher pour aucune des deux — cohérent avec l'existant, pas de
  régression.
- Stocks > Pépinière affichera **"carotte : 80 graines"** en un seul bloc, sans aucun moyen de
  savoir que c'est réparti sur deux emplacements physiques différents.
- Les godets liés à ces semis (mise en godet) resteront non localisés dans tous les cas, comme
  aujourd'hui avec une seule pépinière.

Ajouter une deuxième parcelle `est_pepiniere = true` ne casse rien, mais n'apporte aucune valeur :
le modèle n'a tout simplement pas la notion de "quelle pépinière".

## Cas d'usage potentiellement concernés

- Jardinier avec plusieurs zones de semis (serre chauffée + châssis froid + étagère intérieure) qui
  veut savoir ce qui occupe chaque zone, pas seulement le total par culture.
- Question du type *"est-ce que j'ai encore de la place dans ma serre ?"* — actuellement sans
  réponse possible via l'application, malgré la donnée `superficie_m2` déjà présente sur la
  parcelle Serre.
- Futur multi-tenant (potager partagé) : deux jardiniers du même potager pourraient chacun gérer
  une pépinière distincte (ex. balcon perso vs serre commune) — la distinction devient encore plus
  utile dans ce contexte.

## Pistes de solution (non tranchées — à la charge de la future US)

1. **A minima** : ajouter une vue "occupation de la pépinière" à part (distincte du Plan pleine
   terre), qui affiche par parcelle pépinière les semis qui y sont rattachés — sans toucher aux
   godets ni à l'agrégation existante.
2. **Plus complet** : rattacher les mises en godet à une parcelle (rendre `parcelle_id` optionnel
   mais renseignable pour `mise_en_godet`, avec sélection à la dictée comme pour les autres
   actions), puis inclure la parcelle dans la clé d'agrégation de `calcul_godets()`/`calcul_semis()`.
3. Dans tous les cas : décider si l'agrégat "toutes pépinières confondues" doit rester affiché par
   défaut (utile pour une vue rapide) avec un détail par emplacement en option, ou l'inverse.

## Composants techniques concernés (pour la future US)

| Fichier | Rôle actuel |
|---------|-------------|
| `utils/parcelles.py::calcul_occupation_parcelles` | Exclut les semis pépinière du Plan (`_cond_semis_pleine_terre`) |
| `utils/stock.py::calcul_godets` | Agrège les godets par (culture, variété), sans notion de parcelle |
| `utils/stock.py::calcul_semis` | Agrège les semis par (culture, variété), sans notion de parcelle |
| `app/services/evenements.py::creer_evenement_godet` | Crée toujours l'événement avec `parcelle_id = NULL` |
| `database/models.py::Parcelle.est_pepiniere` | Flag booléen existant, actuellement binaire (pépinière ou non), pas d'identification de laquelle en aval |

## Hors périmètre de cette analyse

- Aucun changement de code n'a été fait suite à ce constat — c'est un sujet à part, indépendant de
  l'US-041 (couche services) qui l'a fait remonter.
- La priorisation (est-ce un besoin réel maintenant, ou théorique) reste à évaluer côté produit
  avant rédaction de l'US.

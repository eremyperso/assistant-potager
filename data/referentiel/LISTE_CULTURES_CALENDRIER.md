# Calendriers des cultures : liste de travail

**Fichiers de référence pour identifier les cultures :**
- `calendrier_redaction_interne.json` : modèle, 106 cultures (liste complète)
- `wind_river_attributs.json` : sortie à compléter, section `cultures_calendriers`

## Avancement

| État | Nombre |
|---|---|
| Traitées (fenêtres et durées à jour) | 0 |
| En cours (tomate, courgette, concombre) | 3 |
| Partiellement renseignées | 34 |
| Absentes | 69 |
| **Total** | **106** |

## À compléter : partiellement renseignées (34)

haricot, chou, carotte, cornichon, poivron, ail, salade, laitue, betterave, radis, navet, oignon, échalote, poireau, brocoli, pomme de terre, aubergine, melon, pastèque, fraise, chou frisé, petit pois, haricot grimpant, pois gourmand, potiron, pâtisson, persil, basilic, thym, menthe, capucine, framboise, fenouil, courge

## À remplir : absentes (69)

bette, épinard, mâche, panais, céleri, chou-fleur, artichaut, patate douce, asperge, roquette, mesclun, cresson, chou de Bruxelles, chou rouge, chou rave, endive, chicorée, oseille, épinard perpétuel, persil racine, scorsonère, salsifis, rutabaga, topinambour, céleri-rave, oignon blanc, ciboulette, ail rose, fève, romarin, coriandre, aneth, estragon, sarriette, cerfeuil, bourrache, souci, groseille, cassis, rhubarbe, pâtisson panaché, pâtisson verruqueux, citrouille, citrouille de Touraine, courge spaghetti, rouge vif d'Étampes, jaune gros de Paris, bleu de Hongrie, blanc de Corné, noir du Brésil, Atlantic Giant, galeuse d'Eysines, giraumon, bonnet turc, potimarron Red Curry, potimarron à gros fruits, courge longue de Nice, courge musquée de Provence, courge pleine de Naples, courge sucrine du Berry, musqué de Provence, hubbard, hubbard vert verruqueux, hubbard Navajo, hubbard bleu, hubbard Golden, butternut Waltham, butternut Ponca, Neck Pumpkin

## Tomate et courgette : fait / pas fait

**Tomate** (en cours)
- ✅ Fenêtres des 4 climats
- ✅ `levee` 7-14, `repiquage` 42-56
- ⚠️ `plantation_recolte` 75-78 gardée : Cyril n'a pas donné de chiffre
- ❌ `recolte` (durée) : à demander
- ❌ `semis_godet` : à demander

**Courgette** (en cours)
- ✅ Fenêtres des 4 climats
- ✅ `levee` 7-10
- ❌ `recolte`, `repiquage`, `plantation_recolte`, `semis_godet` : `null`, à demander

## Concombre : fait / pas fait (en cours)

Source : Cyril, réponses du 27/10/2026 (après réinitialisation du chat).

Fenêtres (sortie actuelle à gauche, réponse de Cyril à droite) :

| Climat | semis_pepiniere | semis_pleine_terre | plantation | recolte |
|---|---|---|---|---|
| océanique | ecart (mars-avril / avril, « à partir de mi-avril ») | ecart (mai-juin / mai, « à partir de mi-mai ») | validee (mai) | validee (juillet-septembre) |
| continental | ecart (avril / mars-avril) | ecart (mai-juillet / mai-juin) | non_chiffree (« une fois les gelées passées ») | ecart (août-septembre / juillet-septembre) |
| méditerranéen | ecart (mars / février-mars) | ecart (avril-juin / avril, « à partir de la mi-avril ») | ecart (avril-mai / avril, « à partir de mi-avril ») | ecart (juillet-août / juin-septembre) |
| montagnard | validee (avril-mai) | ecart (juin-juillet / mai, « après la mi-mai ») | ecart (juin / mai-juin, « fin mai à juin ») | ecart (août-octobre / juillet-septembre) |

Durées (océanique) :
- `levee` : validee, 7-10 (identique à la sortie)
- `repiquage` : lue, 21-28 (« 3 à 4 semaines après les semis en pépinière ») ajoutée à la sortie
- `plantation_recolte` : lue, 56-70 (« 8 à 10 semaines » après la plantation mi-mai) ajoutée à la sortie
- `semis_godet` : lue, 21-28 (« 3 à 4 semaines avant le repiquage », même réponse que `repiquage`, à recouper) ajoutée à la sortie
- `recolte` : non_chiffree (Cyril répond « juillet à septembre », une période et non une durée) → `null`

Écarts en attente de confirmation (sortie non modifiée) : 12. À trancher avant d'écrire.
Les valeurs « à partir de » sans fin (`mai`, `avril`) sont à signaler : la borne de fin n'est pas donnée.

## Intégré : avant / après

**Tomate** (source : Cyril)

| Climat | Champ | Avant | Après |
|---|---|---|---|
| océanique | plantation | avril-mai | **mai** |
| océanique | recolte | juillet-septembre | **juillet-octobre** |
| océanique | semis_pleine_terre | absent | **null** |
| continental | plantation | mai-juin | **mai** |
| continental | recolte | août-octobre | **juillet-septembre** |
| continental | semis_pleine_terre | absent | **null** |
| méditerranéen | plantation | avril-mai | **avril** |
| méditerranéen | recolte | juillet-septembre | **juin-septembre** |
| méditerranéen | semis_pleine_terre | absent | **avril** |
| montagnard | semis_pepiniere | mars-avril | **mars** |
| montagnard | recolte | août-octobre | **juillet-septembre** |
| montagnard | semis_pleine_terre | absent | **null** |

**Courgette** (avant = copie `wind_river_attributs.json.bak`)
- Ajout des `semis_pepiniere` : océanique avril, continental avril, méditerranéen mars, montagnard avril
- Ajout des `plantation` : océanique mai, continental mai-juin, méditerranéen avril, montagnard mai-juin
- Ajout des durées `recolte`, `repiquage`, `plantation_recolte`, `semis_godet` à `null`

**Concombre** (avant = copie `wind_river_attributs.json.avant-concombre.bak`)
- Durées océanique : `levee` 7-10 inchangée ; ajout `recolte` à `null`, `repiquage` 21-28, `plantation_recolte` 56-70, `semis_godet` 21-28
- Fenêtres : aucune modification (12 écarts en attente)

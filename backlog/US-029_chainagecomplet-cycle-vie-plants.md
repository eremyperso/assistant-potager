**ID :** US-029  
**Titre :** Chaînage complet du cycle de vie semis → godet → plantation

**Story :**  
En tant que jardinier  
Je veux que chaque événement du cycle de vie d'un plant soit explicitement lié à son parent (semis → godet → plantation)  
Afin de garantir une traçabilité complète, d'hériter automatiquement de la variété à chaque étape, et de déduire les stocks avec précision même en cas de lots multiples

**Contexte métier :**  

Cycle de vie complet :
```
Semis (graines en barquette)
  └─ Mise en godet [origine_graines_id → semis parent]
       └─ Plantation pleine terre [source_evenement_ids → godet(s) parent(s)]
```

**Problème actuel constaté :**  
- La colonne `origine_graines_id` existe (migration v12) mais reste NULL — US-020 non implémentée  
- Aucun lien n'existe entre `plantation` et le(s) `mise_en_godet` sources  
- La variété n'est pas recopiée dans `plantation` même quand elle est déductible du godet  
- Le calcul de stock repose sur des heuristiques CA6/CA6-reverse qui se neutralisent mutuellement (bug actif)  

Exemple base réelle (butternut) :
| id | action | culture | variete | quantite |
|----|--------|---------|---------|----------|
| 65 | semis | butternut | récolte de 2025 | 20 graines |
| 125 | mise_en_godet | butternut | récolte de 2025 | — (20 plants) |
| 210 | plantation | butternut | **NULL** | 10 plants |

→ La variété "récolte de 2025" aurait dû être recopiée en id=210, et le lien 210→125 établi.

**Critères d'acceptance :**

**Schéma BDD :**
- [ ] CA1 : Nouvelle colonne `source_evenement_ids TEXT NULL` sur la table `evenements` (IDs séparés par `;` si plusieurs sources)
- [ ] CA2 : Migration SQL fournie avec rétro-alimentation des données existantes : pour chaque `plantation` sans variété, chercher le(s) `mise_en_godet` matchant sur `culture` + `variete` (ou culture seule si une variété unique) antérieur(s) à la date de plantation, et renseigner `source_evenement_ids` + `variete`

**Mise en godet → semis :**
- [ ] CA3 : À la sauvegarde d'une `mise_en_godet`, `origine_graines_id` est automatiquement renseigné avec l'id du semis parent (lot unique → automatique, lots multiples → menu inline, cf. US-020)
- [ ] CA4 : La variété du semis est héritée dans la mise en godet si elle n'a pas été précisée par l'utilisateur

**Plantation → godet :**
- [ ] CA5 : À la sauvegarde d'une `plantation` sans variété précisée, le bot cherche les godets actifs pour cette culture ; si une seule variété disponible → recopie la variété dans l'événement `plantation` ET renseigne `source_evenement_ids` avec l'id du godet
- [ ] CA6 : Si plusieurs variétés en godet → menu inline de sélection (comportement actuel conservé), puis recopie variété + lien source après sélection
- [ ] CA7 : Si la plantation consomme des plants issus de **2 lots de godets distincts** (ex : lot A épuisé à 3 plants, compléter avec lot B), `source_evenement_ids` contient les deux IDs séparés par `;` (ex : `"125;147"`)
- [ ] CA8 : Allocation FIFO : les plants sont consommés en priorité depuis le lot de godets **le plus ancien** (date `mise_en_godet` la plus ancienne), puis du suivant si le premier est insuffisant

**Calcul de stock :**
- [ ] CA9 : `calcul_godets_par_culture()` utilise en priorité les liens `source_evenement_ids` pour déduire les plantations par lot de godets — les heuristiques CA6/CA6-reverse ne s'appliquent que sur les événements sans lien (rétrocompatibilité données historiques)
- [ ] CA10 : Suppression du conflit CA6/CA6-reverse : les deux blocs de code ne s'appliquent plus simultanément sur le même événement

**Affichage :**
- [ ] CA11 : `/stats <culture>` — section Pépinière affiche le stock résiduel par lot en précisant le lien : "récolte de 2025 : 10 plants · 10 plantés (→ id#210)"
- [ ] CA12 : La commande `/corriger` permet de retrouver un événement en cherchant par id parent ou enfant ("godet lié à plantation #210")

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement (bot.py `_parse_and_save`, `_do_save_items`), calcul stock (`utils/stock.py`), affichage (`cmd_stats`)
- Migration BDD requise : **oui** — nouvelle colonne `source_evenement_ids`, rétro-alimentation best-effort des données existantes
- Le choix d'un champ texte `source_evenement_ids` (vs table de liaison) est volontaire pour limiter la complexité schéma ; acceptable car les cas multi-sources sont rares (2 lots max en pratique)
- Dépendances : US-020 (origine_graines_id semis→godet — absorbe et remplace), US-022 (déduction godet→plantation — affecte les heuristiques CA6/CA6-reverse)
- **Risque** : la migration rétroactive est best-effort (correspondance par culture+variété+date) ; les cas ambigus restent NULL et conservent le comportement heuristique actuel

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Scenario: Plantation variété unique — héritage automatique + lien
  Given une mise_en_godet id=125 "butternut/récolte de 2025" 20 plants le 02/05
  When l'utilisateur saisit "plantation 10 butternuts"
  Then le bot propose "récolte de 2025 (10 en godet)" sans demander la variété
  And la plantation est sauvegardée avec variete="récolte de 2025"
  And source_evenement_ids="125"
  And le stock godet "récolte de 2025" passe de 20 à 10

Scenario: Plantation multi-lots FIFO
  Given mise_en_godet id=125 "butternut/récolte de 2025" 3 plants le 02/05 (stock résiduel 3)
  And mise_en_godet id=147 "butternut/récolte de 2025" 10 plants le 15/05 (stock résiduel 10)
  When l'utilisateur saisit "plantation 8 butternuts récolte de 2025"
  Then la plantation est sauvegardée avec source_evenement_ids="125;147"
  And le stock lot id=125 passe à 0
  And le stock lot id=147 passe à 5

Scenario: Rétrocompatibilité données sans lien
  Given des plantations existantes sans source_evenement_ids renseigné
  When l'utilisateur consulte /stats butternut
  Then le calcul de stock utilise l'heuristique CA6 (agrégat culture+variété)
  And aucune erreur n'est générée

Scenario: Migration rétroactive
  Given plantation id=210 "butternut" variete=NULL source_evenement_ids=NULL
  And mise_en_godet id=125 "butternut/récolte de 2025" antérieure à id=210
  When la migration SQL est appliquée
  Then evenements id=210 a variete="récolte de 2025" et source_evenement_ids="125"
```

**Labels GitHub :** `us`, `sprint-9`, `stock`, `traçabilité`, `schema`, `migration`

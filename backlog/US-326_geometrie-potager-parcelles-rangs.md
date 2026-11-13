**ID :** US-326
**Titre :** Enregistrer la géométrie du potager, de ses parcelles et de leurs rangs
**Épic :** ÉPIC 19 — Plan du potager sur vue du dessus *(numéro à valider)*

**Story :**
En tant que jardinier
Je veux que l'application connaisse la place réelle de chaque parcelle dans mon potager, sa forme, son orientation et le sens de ses rangs, et le rang exact de chaque culture
Afin que le plan ressemble au terrain, au lieu d'aligner des rectangles identiques dans l'ordre de la base

**Contexte fonctionnel :**
Maquette de référence : `Plan - Pistes.html`, encart « Impact données (à vérifier sur le schéma) ». La cause première relevée par la maquette : **aucune position ni taille relative n'est enregistrée**. Aujourd'hui une parcelle porte `superficie_m2`, `longueur_m` (US-225), `nb_rangs` (US-197), `ordre`, et le « rang » d'un événement est un **multiplicateur** (US-198), pas une position.

**Données ajoutées :**

| Objet | Champs | Remarque |
|---|---|---|
| Potager | emprise (longueur × largeur en m), angle du potager, orientation du nord (8 directions) | le fond et le recalage sont l'objet d'US-335 |
| Parcelle | **forme** (planche, bac, butte, serre, pépinière), **x, y** (m), **longueur, largeur** (m), **rotation** (°), **sens des rangs** (dans la longueur / en travers) | x et y nuls = **pas encore placée** |
| Culture en place | **rang** (position, de 1 à `nb_rangs`) et **part du rang** occupée, pour les rangs partagés | absorbe US-203 |

**Règles :**

| # | Règle |
|---|---|
| G1 | **Une seule source pour la géométrie** : longueur, largeur et sens des rangs se règlent sur le plan ; la superficie s'en déduit (longueur × largeur). La longueur du plan **est** `longueur_m` d'US-225 : pas de second champ |
| G2 | Une parcelle déjà dotée d'une superficie déclarée garde cette valeur jusqu'à ce que le jardinier pose sa géométrie ; l'éditeur signale l'écart (« Surface posée 60 m², fiche parcelle 69 m² ») et propose d'aligner la fiche |
| G3 | Le rang d'une culture est une **position**. Les cultures existantes reçoivent la numérotation d'installation d'US-198, et le disent, tant que le jardinier ne les a pas placées |
| G4 | Un rang peut être partagé : la part de chaque culture est une **fraction** (0,6 / 0,4) ou une **position en mètres** — arbitrage **P4** |
| G5 | Le « rang multiplicateur » de la dictée (« 4 salades sur 3 rangs ») reste compris : il occupe trois rangs consécutifs à partir du premier libre |
| G6 | `GET /plan` expose la géométrie, la position des rangs et la part de chaque culture ; aucune géométrie n'est inventée pour une parcelle non placée |

**Critères d'acceptance :**
- [ ] CA1 : La migration ajoute les champs du tableau, nullables, sans backfill de position ; son rollback est fourni
- [ ] CA2 : `PATCH /parcelles/{id}` (US-230) accepte les champs de géométrie, réservés à un membre éditeur ; la superficie se recalcule selon G1
- [ ] CA3 : Le rang et la part d'une culture se lisent dans `GET /plan` ; une parcelle non placée est listée sans coordonnées
- [ ] CA4 : Les calculs existants (répartition US-198, places US-227, stock, rotation) restent justes — test de comparaison avant / après sur un potager sans géométrie
- [ ] CA5 : Un geste dicté « planté 8 tomates au rang 3 de la planche centrale » enregistre la position 3 ; sans rang dit, la culture prend le premier rang libre (G5)
- [ ] CA6 : La migration est jouée sur la base de test et de dev dans la même livraison, et `scripts/update_dev.ps1` la prend en charge
- [ ] CA7 : `docs/domaines/plan-et-rangs.md` décrit la géométrie, G1 et le double sens du mot « rang » ; la fiche `parcelles-et-plan.md` est corrigée ; corpus vert

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement et analyse
- Migration BDD requise : **oui**
- Dépendances : US-197, US-198, US-225 (livrées) ; **remplace US-203** (position du rang à la saisie), à fermer dans Jira
- Arbitrages **P4** (rang partagé) et **P7** (la « forme » est-elle un nouveau champ, distinct d'`abri` et de `type_pepiniere` ?) à trancher avant de démarrer
- Modèle / effort conseillé : **Opus 5.5, `high`** — migration, chemin d'écriture et parseur de dictée

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Scénario: Poser la géométrie d'une planche
  Given la planche centrale a une superficie déclarée de 69 m²
  When je pose sur le plan une planche de 12 × 5 m, rangs dans la longueur
  Then sa longueur vaut 12 m, sa largeur 5 m, sa superficie 60 m²
  And la fiche parcelle signale l'écart tant que je ne l'ai pas alignée

Scénario: Un rang partagé
  Given le rang 3 de la planche centrale porte des choux de Bruxelles et des choux kale
  When je lis le plan
  Then le rang 3 porte les deux cultures, chacune avec sa part du rang

Scénario: Parcelle pas encore placée
  Given la planche haricots n'a pas de position
  When je lis le plan
  Then elle est listée "à placer", sans coordonnées
```

**Labels GitHub :** `us`, `backend`, `migration`, `plan`

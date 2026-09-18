**ID :** US-193
**Titre :** Déduire la zone climatique du potager à partir de sa latitude, sa longitude et son altitude
**Épic :** ÉPIC 8 — Confiance et personnalisation du calendrier *(numéro à valider, voir le plan de l'épic)*

**Story :**
En tant que jardinier
Je veux que la zone climatique proposée pour mon potager tienne compte de l'altitude de ma ville, et pas seulement de sa position sur la carte
Afin qu'un potager de montagne ou de l'est de la France ne reçoive pas le calendrier de la façade atlantique, avec des plantations conseillées un mois trop tôt, en pleine période de gel

**Contexte fonctionnel :**
US-068 / CA7 pré-positionne la zone d'un potager à partir de sa localisation, avec une règle volontairement grossière : latitude et longitude seulement, et **jamais « montagnard »**, faute d'altitude. Constaté le 16/09/2026 : un potager localisé à **Briançon (1 326 m)** lit le calendrier **océanique**, comme Brest. Il tombe à 10 km sous la limite du quart nord-est, et la règle ne sait pas proposer la montagne. Le bot l'affiche sans réserve : « Zone : océanique (déduite de la localisation) ».

D'autres villes sont mal rangées par la règle actuelle :
- **Reims, Troyes, Clermont-Ferrand** : lues en océanique, alors que leurs gelées sont tardives, comme dans l'est.
- **Valence, Montélimar, Carcassonne** : lues en océanique, alors que leur printemps est proche du méditerranéen.

L'erreur n'a pas le même coût dans les deux sens. Lire une ville de montagne en océanique fait **geler des plants**. Lire une ville de plaine en montagnard ne fait que retarder les dates. La règle doit donc surtout éviter la première erreur.

L'altitude est **déjà disponible** : le service de recherche de ville utilisé à la création et à la modification du potager la renvoie avec les coordonnées. Aujourd'hui, elle n'est simplement pas conservée.

Rappel de la lecture du calendrier source (Wind River Greens), inchangée par cette US : montagnard ← USDA 4, continental ← 6, océanique ← 7, méditerranéen ← 8.

**Critères d'acceptance :**
- [ ] CA1 : Le potager conserve son **altitude en mètres**, à côté de sa latitude et de sa longitude. Elle est renseignée automatiquement quand le jardinier choisit la ville de son potager, à la création comme à la modification. Il n'a rien à saisir de plus.
- [ ] CA2 : Changer la ville d'un potager met à jour **ensemble** latitude, longitude et altitude. Un potager ne garde jamais l'altitude d'une ancienne ville avec les coordonnées de la nouvelle.
- [ ] CA3 : Les potagers déjà localisés avant cette US reçoivent leur altitude à partir de leurs coordonnées existantes, sans que le jardinier ait à ressaisir sa ville. Tant qu'un potager n'a pas d'altitude, il garde la règle actuelle, sans jamais supposer « montagnard ».
- [ ] CA4 : Au-delà d'un **seuil d'altitude**, la zone déduite est **montagnard**, quelles que soient la latitude et la longitude. Le seuil est un réglage modifiable sans redéploiement, **700 m par défaut**, valeur à confirmer avec le porteur du produit.
- [ ] CA5 : Sous ce seuil, les limites entre océanique, continental et méditerranéen sont revues pour que les **villes de référence** ci-dessous donnent la zone attendue. Ce tableau fait foi pour la recette.

  | Ville | Altitude approx. | Zone attendue |
  |---|---|---|
  | Brest | 50 m | océanique |
  | Rennes | 30 m | océanique |
  | Bordeaux | 10 m | océanique |
  | Paris | 35 m | océanique |
  | Lille | 20 m | océanique |
  | Toulouse | 150 m | océanique |
  | Reims | 80 m | continental |
  | Strasbourg | 140 m | continental |
  | Nancy | 200 m | continental |
  | Dijon | 245 m | continental |
  | Lyon | 170 m | continental |
  | Grenoble | 212 m | continental |
  | Montpellier | 30 m | méditerranéen |
  | Marseille | 10 m | méditerranéen |
  | Nice | 20 m | méditerranéen |
  | Perpignan | 30 m | méditerranéen |
  | Ajaccio | 20 m | méditerranéen |
  | Montélimar | 80 m | méditerranéen |
  | Briançon | 1 326 m | montagnard |
  | Chamonix | 1 035 m | montagnard |
  | Pontarlier | 837 m | montagnard |
  | Le Mont-Dore | 1 050 m | montagnard |

  Cas **à arbitrer par le porteur du produit** avant la recette, sans bloquer le reste :
  - Clermont-Ferrand (358 m) : océanique ou continental ?
  - Troyes (110 m) : continental ?
  - Valence (125 m) : continental ou méditerranéen ?
  - Carcassonne (110 m) : océanique ou méditerranéen ?
  - Gérardmer (670 m) et Le Puy-en-Velay (630 m) : juste sous le seuil, doivent-ils être montagnard ?
- [ ] CA6 : Le **choix du jardinier prime toujours** sur la zone déduite (comportement d'US-068 inchangé). `/calendrier zone montagnard` reste respecté quelle que soit l'altitude, et `/calendrier zone auto` revient à la déduction, qui tient désormais compte de l'altitude.
- [ ] CA7 : Quand la zone est **déduite de la localisation**, la réponse du bot le dit et indique l'altitude retenue, par exemple : « Zone : montagnard (déduite de la localisation, 1 326 m) ». Sans altitude connue, elle précise qu'en montagne la zone est à choisir soi-même, et indique la commande pour le faire.
- [ ] CA8 : Le bot (`/calendrier`) et la PWA (écran Plan, calendrier d'une culture) affichent **la même zone** pour un même potager.
- [ ] CA9 : Hors de la France métropolitaine (Corse comprise), aucune zone n'est déduite, comme aujourd'hui, même si l'altitude est connue. Le potager lit la zone par défaut.
- [ ] CA10 : La fiche de fonctionnement du calendrier dans `data/connaissance/doc_app/` est mise à jour **dans la même livraison** : zone déduite de l'altitude, seuil, choix du jardinier prioritaire (règle US-099 / CA9).
- [ ] CA11 : Aucun potager existant ne voit sa zone **choisie** modifiée. Seule la zone **déduite** peut changer, et l'écran ou la réponse le montre à la consultation suivante.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (calendrier cultural), enregistrement (localisation du potager)
- Migration BDD requise : **oui**, altitude du potager, avec rollback
- Dépendances : US-068 (zones et calendrier), US-074 (localisation du potager), US-176 (calendrier sur l'écran Plan)
- Hors périmètre : microclimat (fond de vallée, versant), altitude saisie à la main, cinquième zone climatique, modification de la correspondance USDA

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Feature: Zone climatique déduite avec l'altitude

  Scenario: Un potager de montagne lit le calendrier montagnard
    Given un potager localisé à "Briançon" sans zone choisie par le jardinier
    And son altitude enregistrée est de 1326 m
    When le jardinier envoie "/calendrier tomate"
    Then la zone affichée est "montagnard (déduite de la localisation, 1 326 m)"
    And les fenêtres affichées sont celles de la zone montagnard

  Scenario: Changer de ville met à jour l'altitude et la zone
    Given un potager localisé à "Rennes" sans zone choisie
    When le jardinier change la ville du potager pour "Chamonix"
    Then l'altitude du potager est d'environ 1035 m
    And "/calendrier tomate" affiche la zone "montagnard"

  Scenario: Le choix du jardinier prime sur l'altitude
    Given un potager localisé à "Briançon"
    And le jardinier a choisi la zone "continental"
    When le jardinier envoie "/calendrier tomate"
    Then la zone affichée est "continental (choix du jardinier)"

  Scenario: Un potager ancien sans altitude reçoit la sienne
    Given un potager localisé à "Pontarlier" avant cette US, sans altitude
    When la migration de l'altitude est appliquée
    Then l'altitude du potager est d'environ 837 m
    And sa zone déduite est "montagnard"

  Scenario: Une ville de plaine de l'est n'est plus lue en océanique
    Given un potager localisé à "Reims" sans zone choisie
    When le jardinier envoie "/calendrier tomate"
    Then la zone affichée est "continental (déduite de la localisation, 80 m)"
```

**Labels GitHub :** `us`, `epic-8`, `calendrier`, `migration`

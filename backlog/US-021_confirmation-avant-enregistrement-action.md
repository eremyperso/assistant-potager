**ID :** US-021  
**Titre :** Confirmation avant enregistrement + sélection guidée parcelle manquante

**Story :**  
En tant que jardinier  
Je veux que le bot me présente un résumé de l'action détectée, me propose de choisir la parcelle si elle n'a pas été détectée, puis me demande de confirmer avant d'enregistrer  
Afin d'éviter les enregistrements erronés et de toujours associer mes actions à la bonne parcelle sans avoir à reformuler

**Critères d'acceptance :**
- [x] CA1 : Après parsing d'une commande de type action (semis, plantation, mise en godet, récolte, perte, arrosage, désherbage, taille, paillage, tuteurage, fertilisation, observation), le bot affiche un résumé lisible de ce qu'il s'apprête à enregistrer
- [x] CA2 : Le résumé est suivi de deux boutons inline : `✅ Confirmer` et `❌ Annuler`
- [x] CA3 : L'enregistrement en base n'a lieu qu'après appui sur `✅ Confirmer`
- [x] CA4 : Si l'utilisateur appuie sur `❌ Annuler`, aucun événement n'est créé et un message "Action annulée." est affiché
- [x] CA5 : Si l'utilisateur ne répond pas dans un délai de 1 minute, l'action est automatiquement annulée et un message d'expiration est affiché
- [x] CA6 : Les intents de type interrogation (INTERROGER, STATS, HISTORIQUE, PLAN) ne déclenchent PAS de confirmation — ils sont exécutés directement comme aujourd'hui
- [x] CA7 : Le flux de confirmation est compatible avec les flux à étapes multiples existants (US-019 sélection variété, US-020 sélection lot) — la confirmation intervient en dernier, après toutes les sélections
- [x] CA8 : Si la parcelle est absente du résumé (non détectée par Groq), le bot affiche un menu inline avec toutes les parcelles actives + un bouton `📍 Sans parcelle` — **avant** d'afficher les boutons Confirmer/Annuler
- [x] CA9 : Une fois la parcelle sélectionnée via le menu, le résumé est mis à jour avec la parcelle choisie, puis les boutons `✅ Confirmer` / `❌ Annuler` apparaissent
- [x] CA10 : Si le jardinier choisit `📍 Sans parcelle`, l'enregistrement se fait avec `parcelle_id = NULL` — comportement identique à aujourd'hui
- [x] CA11 : Si aucune parcelle active n'existe en base, le menu de sélection n'est pas affiché — le bot passe directement à la confirmation avec `parcelle_id = NULL`
- [x] CA12 : Le TTL de 1 minute s'applique à l'ensemble du flux (sélection parcelle + confirmation) — pas de remise à zéro entre les étapes

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram, enregistrement
- Migration BDD requise : non
- Dépendances : US-019, US-020 (ordre des étapes : variété → lot → parcelle → confirmation)
- CA1 à CA7 déjà implémentés — seuls CA8 à CA12 sont à développer
- Le menu parcelle s'insère dans le flux `_ACTION_PENDING` existant : après sélection, les données enrichies restent dans le dict pending et le bot affiche la confirmation
- Actions concernées par la sélection de parcelle : semis, plantation, mise en godet, récolte, perte, arrosage (toutes les actions sauf observation si pas de culture liée)
- Le bouton `📍 Sans parcelle` doit toujours être présent pour ne pas bloquer l'utilisateur
- Affichage du menu : boutons inline 1 par ligne, triés par ordre de parcelle (`Parcelle.ordre`)

**Estimation :** 3 points *(CA1-CA7 déjà livrés)*

**Scénario Gherkin :**
```gherkin
Scenario: Parcelle absente — sélection proposée puis confirmation
  Given je dis "plantation 10 plants de tomate"
  When le bot parse la commande sans parcelle détectée
  Then il affiche le résumé sans parcelle
  And un menu inline propose [zone-tomates] [zone-oignons] [nord] [📍 Sans parcelle]
  When je sélectionne "zone-tomates"
  Then le résumé est mis à jour avec "📍 Parcelle : zone-tomates"
  And les boutons "✅ Confirmer" et "❌ Annuler" apparaissent
  When j'appuie sur "✅ Confirmer"
  Then l'événement est enregistré avec parcelle_id = id de zone-tomates

Scenario: Parcelle déjà détectée — pas de menu intermédiaire
  Given je dis "plantation 10 plants de tomate en zone-tomates"
  When le bot parse la commande avec parcelle = "zone-tomates"
  Then il affiche directement le résumé avec parcelle
  And les boutons "✅ Confirmer" et "❌ Annuler" apparaissent sans étape intermédiaire

Scenario: Choix Sans parcelle
  Given je dis "arrosage tomates"
  When le menu de sélection de parcelle s'affiche
  And je sélectionne "📍 Sans parcelle"
  Then les boutons "✅ Confirmer" et "❌ Annuler" apparaissent
  And l'enregistrement se fait avec parcelle_id = NULL

Scenario: Aucune parcelle active en base
  Given aucune parcelle n'est enregistrée dans la base
  When le bot parse une commande sans parcelle détectée
  Then il affiche directement le résumé + boutons Confirmer/Annuler sans menu intermédiaire

Scenario: Expiration pendant la sélection de parcelle
  Given le menu de sélection de parcelle est affiché
  When 1 minute s'écoule sans interaction
  Then l'action en attente est supprimée
  And le bot envoie "⏱️ Confirmation expirée, action annulée."
```

**Labels GitHub :** `us`, `sprint-9`, `ux`, `confirmation`, `parcelle`, `enregistrement`

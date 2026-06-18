# US-033 — Saisie guidée d'un arrosage par culture via Telegram

**ID :** US-033
**Titre :** Enregistrer un arrosage par culture avec niveau d'intensité

**Story :**
En tant que jardinier
Je veux indiquer rapidement quelle(s) culture(s) j'ai arrosée(s) et avec quelle intensité
Afin d'avoir un historique précis de mes arrosages sans avoir à retaper les noms à la main

---

## Critères d'acceptance

- [ ] CA1 : La commande `/arroser` (ou `/arrosage`) affiche une liste de boutons inline listant toutes les cultures actuellement en place dans le potager (issues des parcelles actives)
- [ ] CA2 : Après sélection d'une culture, le bot propose 3 niveaux d'arrosage sous forme de boutons : **Léger 🌿** · **Normal 💧** · **Abondant 🌊**
- [ ] CA3 : Chaque niveau correspond à un volume estimatif par pied : Léger = 0,5 L/pied · Normal = 1 L/pied · Abondant = 2 L/pied — la quantité totale est calculée automatiquement à partir du nb_plants en place
- [ ] CA4 : L'arrosage est enregistré en base comme `type_action = "arrosage"` avec `quantite` (volume total en L), `unite = "L"`, et `commentaire` précisant le niveau (léger/normal/abondant)
- [ ] CA5 : L'utilisateur peut sélectionner plusieurs cultures à la suite dans le même flux, sans repasser par `/arroser`
- [ ] CA6 : La dictée vocale reste fonctionnelle — "j'ai arrosé les tomates abondamment" est reconnu et enregistré sans passer par le clavier inline
- [ ] CA7 : Un récapitulatif est envoyé en fin de session : cultures arrosées, volumes, volume total déduit de la réserve (voir US-034)
- [ ] CA8 : Si aucune culture n'est en place dans le potager, le bot répond avec un message explicite

---

## Notes fonctionnelles

- Zone fonctionnelle concernée : interaction Telegram (clavier inline + vocale)
- Migration BDD requise : non — utilise la table `evenements` existante (`type_action = "arrosage"`)
- Le nb_plants par culture est issu de `calcul_occupation_parcelles()` (déjà disponible)
- Les niveaux Léger / Normal / Abondant sont des valeurs par défaut ajustables ; l'utilisateur peut aussi dicter un volume précis ("j'ai mis 15 litres aux courgettes")
- Dépendances : US-024 (plan parcelles), US-034 (réserve eau)

**Estimation :** 3 points

---

## Scénario Gherkin

```gherkin
Feature: Saisie guidée d'un arrosage

  Scenario: Arrosage normal des tomates via le clavier inline
    Given le potager contient des tomates (14 plants) dans la parcelle maison
    When le jardinier envoie /arroser
    Then le bot affiche une liste de boutons avec toutes les cultures en place
    When le jardinier sélectionne "Tomate"
    Then le bot propose 3 boutons : "Léger 🌿", "Normal 💧", "Abondant 🌊"
    When le jardinier sélectionne "Normal 💧"
    Then l'arrosage est enregistré : culture=tomate, quantite=14, unite=L, commentaire=normal
    And le bot confirme : "✅ Tomates arrosées — 14 L (normal) · Réserve : 850 L restants"

  Scenario: Arrosage vocal libre
    Given le jardinier dicte "j'ai bien arrosé les courgettes aujourd'hui"
    When Groq classifie l'intent en ACTION / arrosage
    Then l'événement est enregistré avec type_action=arrosage, culture=courgette
    And le niveau est déduit du vocabulaire ("bien arrosé" → normal)
```

**Labels GitHub :** `us`, `sprint-4`, `arrosage`, `telegram`

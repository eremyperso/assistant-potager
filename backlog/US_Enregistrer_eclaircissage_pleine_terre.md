**Titre :** Enregistrer un éclaircissage en pleine terre (déduction stock)

**Story :**
En tant que jardinier
Je veux enregistrer un éclaircissage en pleine terre comme une sortie de stock volontaire
Afin que le stock de plants en culture reflète exactement ce qui est réellement en terre

**Critères d'acceptance :**
- [ ] CA1 : Un type d'action `eclaircissage_pleine_terre` est reconnu (vocal et texte), distinct d'une `perte` involontaire
- [ ] CA2 : L'action décrémente le stock actif du nombre de plants éclaircis (ex : -3 plants)
- [ ] CA3 : Ex : _"Éclairci 3 carottes rang 2 parcelle nord"_ → stock carottes -= 3, événement tracé
- [ ] CA4 : L'action apparaît dans /historique et les stats avec le libellé "éclaircissage" distinctement des pertes
- [ ] CA5 : Si la quantité éclaircée dépasse le stock estimé, le bot avertit sans bloquer l'enregistrement

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement (bot), analyse (LLM), calcul stock
- Migration BDD requise : **non** — nouveau type d'action dans le domaine existant, même structure
- Dépendances : US_Adapter_stock_selon_type_organe
- Règle métier : sortie de stock **volontaire** ≠ `perte` (involontaire). La distinction est importante pour les bilans de productivité.

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Feature: Éclaircissage pleine terre

  Scenario: Enregistrement d'un éclaircissage
    Given 12 plants de carottes sont en stock actif parcelle nord
    When le jardinier envoie "Éclairci 3 carottes rang 2 parcelle nord"
    Then une action eclaircissage_pleine_terre est enregistrée
    And le stock actif carottes parcelle nord passe à 9
    And l'événement est distinct d'une perte dans l'historique

  Scenario: Éclaircissage supérieur au stock estimé
    Given 5 plants de radis sont en stock actif
    When le jardinier enregistre un éclaircissage de 8 radis
    Then le bot enregistre l'action
    And affiche un avertissement "stock estimé dépassé (5 plants)"
```

**Labels GitHub :** `us`, `priorite-haute`, `stock`, `culture-en-place`

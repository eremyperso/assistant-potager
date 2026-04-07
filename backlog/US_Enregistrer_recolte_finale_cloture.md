**Titre :** Enregistrer une récolte finale qui clôture la culture

**Story :**
En tant que jardinier
Je veux enregistrer une récolte finale distincte d'une récolte partielle
Afin de clôturer proprement une culture, remettre son stock à zéro et permettre des bilans de saison fiables

**Critères d'acceptance :**
- [ ] CA1 : Un type d'action `recolte_finale` est reconnu (vocal et texte), distinct de `recolte` (partielle)
- [ ] CA2 : L'enregistrement d'une récolte finale passe le stock actif de la culture concernée à **zéro** et marque la culture comme **clôturée**
- [ ] CA3 : Ex : _"Récolte finale tomates cerise parcelle nord, 1.2 kg, fin de culture"_ → stock = 0, statut = clôturé
- [ ] CA4 : Une culture clôturée n'apparaît plus dans le stock actif mais reste dans l'historique et les stats
- [ ] CA5 : La commande /stats présente le rendement total (somme récoltes partielles + finale) et la durée de culture (date plantation → date récolte finale)

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement, calcul stock, statistiques
- Migration BDD requise : **oui** — champ `statut` sur la culture ou l'événement (`active` / `cloturee`), ou table `cycle_culture`
- Dépendances : US_Adapter_stock_selon_type_organe, US_Modéliser_type_organe_récolté
- Règle métier : une récolte finale solde le stock. Elle peut coexister avec des récoltes partielles précédentes sur la même culture/parcelle.

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Feature: Récolte finale et clôture de culture

  Scenario: Enregistrement d'une récolte finale
    Given 6 plants de tomates cerise sont en stock actif parcelle nord
    When le jardinier envoie "Récolte finale tomates cerise, 1.2 kg, fin de culture"
    Then une action recolte_finale est enregistrée avec quantite=1.2 kg
    And le stock actif tomates cerise parcelle nord passe à 0
    And la culture est marquée comme clôturée

  Scenario: Bilan de saison après récolte finale
    Given plusieurs récoltes partielles + une récolte finale existent
    When le jardinier demande "Bilan tomates cerise cette saison"
    Then le bot restitue : rendement total, durée culture, nb récoltes
```

**Labels GitHub :** `us`, `priorite-haute`, `recolte`, `stock`, `stats`

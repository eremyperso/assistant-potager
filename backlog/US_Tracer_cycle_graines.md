**Titre :** Tracer le cycle graines (récolte graines → lien semis suivant)

**Story :**
En tant que jardinier pratiquant la sélection variétale
Je veux enregistrer une récolte de graines et la relier au semis de l'année suivante
Afin de tracer la boucle complète : semis A → culture B → récolte graines C → semis D

**Critères d'acceptance :**
- [ ] CA1 : Un type d'action `recolte_graines` est reconnu (vocal et texte), avec les champs : culture, variété, quantité (g), date
- [ ] CA2 : Ex : _"Récolté graines tomates cœur de bœuf, 15 g"_ → action `recolte_graines` enregistrée, retour vers pépinière
- [ ] CA3 : Un champ optionnel `origine_graines` sur l'action `semis` permet de référencer l'id de la `recolte_graines` source
- [ ] CA4 : Une question analytique peut restituer la généalogie variétale : _"D'où viennent mes graines de tomate cœur de bœuf ?"_
- [ ] CA5 : La `recolte_graines` n'est **pas** comptabilisée dans le stock de récolte alimentaire (distincte de `recolte` et `recolte_finale`)

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement, analyse LLM, base de données
- Migration BDD requise : **oui** — nouveau type d'action `recolte_graines` + champ `origine_graines_id` (FK nullable) sur `evenement`
- Dépendances : US_Enregistrer_mise_en_godet, US_Distinguer_semis_pepiniere_pleine_terre
- Règle métier : le cycle graines est une boucle pépinière → pépinière. Il ne modifie pas le stock de culture actif.
- Priorité de livraison : après les US de stock (cette US est enrichissement, pas correctif)

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Feature: Cycle graines traçable

  Scenario: Récolte de graines
    Given une culture de tomate cœur de bœuf est clôturée
    When le jardinier envoie "Récolté graines tomates cœur de bœuf 15 g"
    Then une action recolte_graines est enregistrée
    And la quantité n'est PAS ajoutée au stock de récolte alimentaire
    And l'entrée est visible dans la zone pépinière

  Scenario: Lien semis → origine graines
    Given une recolte_graines id=42 existe
    When le jardinier enregistre un semis avec "graines de l'an dernier"
    Then le champ origine_graines_id = 42 est renseigné

  Scenario: Question généalogie variétale
    When le jardinier demande "D'où viennent mes graines de cœur de bœuf ?"
    Then le bot retrace la chaîne semis → culture → recolte_graines
```

**Labels GitHub :** `us`, `priorite-moyenne`, `pepiniere`, `graines`, `traçabilite`

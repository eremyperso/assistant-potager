**Titre :** Enregistrer un arrachage ou fin de culture (solde stock à zéro)

**Story :**
En tant que jardinier
Je veux enregistrer un arrachage ou une fin de culture forcée (gel, maladie, fin de saison)
Afin de solder le stock actif à zéro, clore la culture dans l'historique et libérer la parcelle pour la rotation

**Critères d'acceptance :**
- [ ] CA1 : Un type d'action `arrachage` est reconnu (vocal et texte), avec un motif optionnel : `gel`, `maladie`, `fin_saison`, `ravageur`, `volontaire`
- [ ] CA2 : L'enregistrement passe le stock actif de la culture/parcelle concernée à **zéro** et marque la culture comme **terminée**
- [ ] CA3 : Ex : _"Arraché toutes les courgettes parcelle est, fin de saison"_ → stock = 0, motif = fin_saison
- [ ] CA4 : L'arrachage apparaît dans l'historique avec le libellé distinct de `perte` et de `recolte_finale`
- [ ] CA5 : La parcelle concernée est libérée et apparaît comme disponible dans un futur bilan de rotation

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement (bot), calcul stock, rotation parcelle
- Migration BDD requise : **non** — nouveau type d'action dans la structure existante + champ `motif_fin` (nullable)
- Dépendances : US_Enregistrer_recolte_finale_cloture (partage la logique de clôture de stock)
- Règle métier : `arrachage` ≠ `recolte_finale` (on arrache sans récolter, ex : culture ratée) ≠ `perte` (perte partielle involontaire)

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Feature: Arrachage et fin de culture

  Scenario: Arrachage fin de saison
    Given des courgettes sont en stock actif parcelle est
    When le jardinier envoie "Arraché toutes les courgettes, fin de saison"
    Then une action arrachage est enregistrée avec motif = fin_saison
    And le stock actif courgettes parcelle est passe à 0
    And la parcelle est est marquée disponible

  Scenario: Arrachage suite à maladie
    When le jardinier envoie "Arraché les poireaux, mildiou"
    Then une action arrachage est enregistrée avec motif = maladie
    And l'événement est distinct d'une perte partielle
```

**Labels GitHub :** `us`, `priorite-moyenne`, `stock`, `arrachage`, `rotation`

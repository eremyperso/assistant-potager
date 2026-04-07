**Titre :** Enregistrer une mise en godet avec taux de réussite germination

**Story :**
En tant que jardinier
Je veux enregistrer la mise en godet de jeunes plants avec le nombre de graines semées et le nombre de plants obtenus
Afin de calculer le taux de réussite à la germination et distinguer la pépinière du stock en terre

**Critères d'acceptance :**
- [ ] CA1 : Un nouveau type d'action `mise_en_godet` est reconnu (vocal et texte), avec extraction des champs `nb_graines_semees` et `nb_plants_godets`
- [ ] CA2 : L'action est rattachée au domaine **Pépinière** (hors comptabilisation du stock de culture actif)
- [ ] CA3 : Le taux de réussite germination (`nb_plants_godets / nb_graines_semees × 100`) est calculé et stocké (ou calculable à la requête)
- [ ] CA4 : Ex : _"Mis en godet 24 tomates cerise sur 30 graines semées"_ → action enregistrée, taux = 80 %
- [ ] CA5 : La commande /stats ou une question analytique peut restituer le taux de réussite par culture / variété

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement (bot), analyse (LLM), base de données
- Migration BDD requise : **oui** — nouveaux champs `nb_graines_semees` (int), `nb_plants_godets` (int) sur la table `evenement` ou table dédiée `pepiniere`
- Dépendances : US_Modéliser_type_organe_récolté, US_Afficher_synthese_semis_dans_stats
- Règle métier : hors stock actif — ne déclenche **pas** le compteur de plants en terre

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Feature: Mise en godet pépinière

  Scenario: Enregistrement d'une mise en godet
    Given le bot est en écoute
    When le jardinier envoie "Mis en godet 24 tomates cerise sur 30 graines"
    Then une action mise_en_godet est enregistrée
    And nb_graines_semees = 30, nb_plants_godets = 24
    And le taux de réussite calculé est 80%
    And le stock de culture actif n'est PAS incrémenté

  Scenario: Question analytique sur le taux de germination
    Given des mises en godet existent en base
    When le jardinier demande "Quel est mon taux de réussite sur les tomates ?"
    Then le bot restitue le taux moyen par culture / variété
```

**Labels GitHub :** `us`, `priorite-haute`, `pepiniere`, `stock`

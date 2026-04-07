**Titre :** Distinguer semis pépinière et semis pleine terre dans les stats

**Story :**
En tant que jardinier
Je veux que les semis réalisés en pépinière (hors sol) soient distingués des semis en pleine terre dans les statistiques
Afin de savoir précisément combien de cultures sont issues d'une filière "semis → godet → plantation" vs "semis direct"

**Critères d'acceptance :**
- [ ] CA1 : Le type d'action `semis` accepte un attribut de contexte : `pepiniere` (hors sol, en godet) ou `pleine_terre` (semis direct en parcelle)
- [ ] CA2 : Ex : _"Semé 50 graines de tomates cerise en pépinière"_ vs _"Semé des carottes rang 3 pleine terre"_ → catégories distinctes
- [ ] CA3 : La commande /stats ou une question analytique restitue deux totaux séparés : semis pépinière / semis pleine terre par culture et saison
- [ ] CA4 : Les semis pépinière n'incrémentent pas le stock de culture actif (cohérence avec US_Enregistrer_mise_en_godet)
- [ ] CA5 : Par défaut (si non précisé), le LLM infère le contexte selon la culture (ex : tomate → pépinière probable, carotte → pleine terre probable)

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement (bot), analyse LLM (rag/groq_client), statistiques
- Migration BDD requise : **oui** — champ `contexte_semis` (`pepiniere` / `pleine_terre`) sur la table `evenement`
- Dépendances : US_Enregistrer_mise_en_godet, US_Afficher_synthese_semis_dans_stats
- Note : cette US enrichit l'existant sans casser le modèle actuel (champ nullable avec valeur par défaut)

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Feature: Distinction semis pépinière / pleine terre

  Scenario: Semis en pépinière
    Given le bot est en écoute
    When le jardinier envoie "Semé 50 graines tomates cerise en pépinière"
    Then l'action semis est enregistrée avec contexte_semis = pepiniere
    And le stock de culture actif n'est PAS incrémenté

  Scenario: Semis pleine terre
    When le jardinier envoie "Semé carottes Nantaise rang 3"
    Then l'action semis est enregistrée avec contexte_semis = pleine_terre

  Scenario: Stats avec distinction
    When le jardinier demande "Combien de semis en pépinière cette saison ?"
    Then le bot restitue uniquement les semis de type pepiniere
```

**Labels GitHub :** `us`, `priorite-moyenne`, `pepiniere`, `semis`, `stats`

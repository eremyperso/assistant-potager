**Titre :** Afficher un bilan de rotation par parcelle

**Story :**
En tant que jardinier
Je veux interroger l'assistant pour obtenir l'historique des cultures par parcelle
Afin de planifier les rotations, éviter les mono-cultures et respecter les règles de succession

**Critères d'acceptance :**
- [ ] CA1 : Une question analytique de type _"Quoi a poussé parcelle nord ?"_ ou _"Rotation parcelle A"_ retourne la liste chronologique des cultures par parcelle avec dates de plantation et de clôture
- [ ] CA2 : Le résultat distingue les cultures actives (en cours) des cultures clôturées (recolte_finale ou arrachage)
- [ ] CA3 : Le bilan indique pour chaque culture : nom, variété, date début, date fin (si clôturée), rendement total si disponible
- [ ] CA4 : La réponse est synthétique et lisible sur mobile (≤ 10 lignes pour une parcelle standard)
- [ ] CA5 : Le bilan peut porter sur toutes les parcelles (_"Bilan de rotation global"_) ou une parcelle spécifique

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interrogation analytique (ia_orchestrator, groq_client, rag)
- Migration BDD requise : **non** — requête sur données existantes, enrichie par les champs `statut` et `motif_fin` des US précédentes
- Dépendances : US_Enregistrer_recolte_finale_cloture, US_Enregistrer_arrachage_fin_culture (nécessaires pour la clôture de culture)
- La réponse est générée par le LLM Groq avec le contexte JSON des événements filtrés par parcelle

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Feature: Bilan de rotation par parcelle

  Scenario: Historique d'une parcelle
    Given plusieurs cultures ont été enregistrées sur la parcelle nord
    When le jardinier demande "Quoi a poussé parcelle nord ?"
    Then le bot retourne la liste chronologique des cultures
    And chaque entrée indique : culture, variété, date début, date fin ou "en cours"

  Scenario: Bilan global toutes parcelles
    When le jardinier demande "Bilan de rotation global"
    Then le bot retourne un résumé par parcelle avec les dernières cultures

  Scenario: Aide à la planification
    When le jardinier demande "J'ai mis des tomates parcelle nord l'an dernier, que planter ?"
    Then le bot identifie la succession et propose une famille différente
```

**Labels GitHub :** `us`, `priorite-basse`, `rotation`, `parcelle`, `stats`

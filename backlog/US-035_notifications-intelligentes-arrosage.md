# US-035 — Notifications intelligentes d'arrosage selon météo et historique

**ID :** US-035
**Titre :** Envoyer des rappels d'arrosage contextuels basés sur la météo et l'historique

**Story :**
En tant que jardinier
Je veux recevoir des rappels d'arrosage intelligents qui tiennent compte de la météo du jour et de la date de mon dernier arrosage par culture
Afin de ne jamais oublier d'arroser sans le faire inutilement quand il a plu

---

## Critères d'acceptance

- [ ] CA1 : Chaque matin (au même moment que la météo, 07h00), le système analyse pour chaque culture active :
  - La date du dernier arrosage enregistré
  - La météo du jour (pluie prévue, températures)
  - Un seuil de fréquence par type de culture (végétatif vs reproducteur)
- [ ] CA2 : Si la météo prévoit ≥ 5 mm de précipitations → aucune notification d'arrosage envoyée, message optionnel "🌧️ Pluie prévue — pas besoin d'arroser aujourd'hui"
- [ ] CA3 : Si température max > 28°C et aucune pluie prévue → seuil d'alerte abaissé (arrosage recommandé si dernier arrosage > 1 jour pour les cultures sensibles)
- [ ] CA4 : La notification liste les cultures à arroser en priorité, avec le nb de jours depuis le dernier arrosage : "💧 À arroser aujourd'hui : Tomates (3j), Courgettes (2j), Basilic (4j)"
- [ ] CA5 : Un bouton inline "Arroser maintenant" dans la notification lance directement le flux guidé (US-033) pré-filtré sur les cultures listées
- [ ] CA6 : Les cultures entièrement arrosées dans les dernières 24h n'apparaissent pas dans la liste
- [ ] CA7 : Le jardinier peut configurer les seuils de fréquence par culture via commande : `/arrosage seuil tomate 2` (tous les 2 jours)
- [ ] CA8 : La notification intelligente peut être déclenchée manuellement via `/arrosage check` à tout moment

---

## Notes fonctionnelles

- Zone fonctionnelle concernée : notifications Telegram + analyse (zéro Groq)
- Migration BDD requise : **non** — s'appuie sur les arrosages existants dans `evenements` + les données météo du job matinal
- Seuils de fréquence par défaut (ajustables) :
  - Cultures végétatives (laitue, carotte, basilic) : tous les 1–2 jours
  - Cultures reproductrices (tomate, courgette, concombre) : tous les 2–3 jours
  - Cultures résistantes (oignon, ail, échalote) : tous les 4–5 jours
- La météo est déjà disponible depuis `utils/meteo.py` — le champ `precipitations` et `temp_max` sont exploitables sans appel API supplémentaire
- Le calcul "dernier arrosage par culture" est une requête SQL simple sur `evenements` filtrée par `type_action = "arrosage"`
- Dépendances : US-033 (arrosage guidé), US-034 (réserve eau), `utils/meteo.py` (météo quotidienne)

**Estimation :** 5 points

---

## Scénario Gherkin

```gherkin
Feature: Notifications intelligentes d'arrosage

  Scenario: Jour de chaleur sans pluie — rappel envoyé
    Given il est 07h00
    And la météo prévoit 32°C et 0 mm de pluie
    And les tomates n'ont pas été arrosées depuis 2 jours
    And les courgettes ont été arrosées hier
    When le job matinal se déclenche
    Then le bot envoie :
      "☀️ Chaleur — Penser à arroser ce soir
       💧 Priorité : Tomates (2j sans arrosage)
       ℹ️  Courgettes : arrosées hier, ok pour aujourd'hui"
    And un bouton "Arroser maintenant 💧" est proposé

  Scenario: Jour pluvieux — pas de notification
    Given la météo prévoit 12 mm de pluie
    When le job matinal se déclenche
    Then aucune notification d'arrosage n'est envoyée
    And le log indique "arrosage ignoré — pluie prévue (12mm)"

  Scenario: Vérification manuelle
    When le jardinier envoie "/arrosage check"
    Then le bot analyse l'historique et la météo en temps réel
    And retourne immédiatement la liste des cultures à arroser avec les délais
```

**Labels GitHub :** `us`, `sprint-5`, `arrosage`, `notifications`, `meteo`

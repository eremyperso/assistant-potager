# US-034 — Gestion de la réserve d'eau (réservoir 1000 L)

**ID :** US-034
**Titre :** Suivre la consommation et le remplissage du réservoir d'eau

**Story :**
En tant que jardinier
Je veux gérer ma réserve d'eau de 1000 L comme un réservoir de carburant
Afin de savoir en temps réel combien de litres il me reste et anticiper un remplissage avant d'être à court

---

## Critères d'acceptance

- [ ] CA1 : La commande `/reservoir` affiche l'état actuel : volume restant (L), pourcentage, date du dernier remplissage, volume consommé depuis le remplissage
- [ ] CA2 : Le remplissage s'enregistre via Telegram : `/reservoir remplir` (ou dictée "j'ai rempli la cuve") → remet le compteur à 1000 L avec la date du jour
- [ ] CA3 : Chaque arrosage enregistré (US-033) déduit automatiquement son volume de la réserve courante
- [ ] CA4 : L'état de la réserve est visible dans le récapitulatif de chaque arrosage ("Réserve : 750 L restants — 75%")
- [ ] CA5 : Une alerte Telegram est envoyée automatiquement quand la réserve passe sous **20%** (< 200 L)
- [ ] CA6 : La réserve affiche une jauge visuelle en texte : `🟩🟩🟩🟩🟨⬜⬜⬜⬜⬜ 42% — 420 L`
- [ ] CA7 : L'historique des remplissages et consommations est consultable via `/reservoir historique` (10 dernières opérations)
- [ ] CA8 : La capacité du réservoir (1000 L par défaut) est configurable via une variable d'environnement ou une commande admin, sans modification de code

---

## Notes fonctionnelles

- Zone fonctionnelle concernée : enregistrement + interaction Telegram + notifications
- Migration BDD requise : **oui** — nouvelle table `reservoir` ou utilisation de la table `evenements` avec `type_action = "remplissage_reservoir"` et `type_action = "arrosage"` (à arbitrer)
  - Option recommandée : table dédiée `reservoir_operations (id, type [remplissage|consommation], volume_l, date, evenement_id)` + vue agrégée
  - Alternative légère : stocker dans `evenements` avec `culture = "_reservoir"` et `unite = "L"` — zéro migration
- Le solde courant est calculé : `capacite - Σ(arrosages depuis dernier remplissage)`
- Le volume des arrosages vocaux sans quantité explicite est estimé via les niveaux (CA3 de US-033)
- Dépendances : US-033 (arrosage guidé)

**Estimation :** 3 points

---

## Scénario Gherkin

```gherkin
Feature: Gestion réserve d'eau

  Scenario: Consultation de la réserve
    Given la cuve a été remplie le 10/06 (1000 L)
    And 3 arrosages ont consommé 380 L au total depuis
    When le jardinier envoie /reservoir
    Then le bot répond :
      """
      💧 Réserve d'eau
      🟩🟩🟩🟩🟩🟩⬜⬜⬜⬜  62% — 620 L
      Remplie le 10/06 · 380 L consommés
      """

  Scenario: Alerte réserve basse
    Given la réserve est à 180 L (18%)
    When un nouvel arrosage est enregistré
    Then le bot envoie une notification proactive :
      "⚠️ Réserve basse — 180 L restants (18%). Pensez à remplir la cuve."

  Scenario: Remplissage de la cuve
    Given la réserve est à 320 L
    When le jardinier envoie "/reservoir remplir"
    Then le bot enregistre un remplissage à la date du jour
    And la réserve revient à 1000 L
    And le bot confirme : "✅ Cuve remplie — 1000 L disponibles"
```

**Labels GitHub :** `us`, `sprint-4`, `arrosage`, `reservoir`

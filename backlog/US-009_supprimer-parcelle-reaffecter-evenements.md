**ID :** US-009
**Titre :** Supprimer une parcelle et réaffecter ses événements en "non localisé"

**Story :**
En tant que jardinier
Je veux pouvoir supprimer une parcelle devenue obsolète via `/parcelle supprimer <nom>`
Afin de garder mon plan de potager propre sans perdre l'historique des cultures qui y ont été réalisées

**Critères d'acceptance :**
- [ ] CA1 : La sous-commande `/parcelle supprimer <nom>` est reconnue par le bot et déclenche un flux de confirmation
- [ ] CA2 : Avant de supprimer, le bot affiche un message de confirmation indiquant : le nom exact de la parcelle et le nombre d'événements qui vont être réaffectés en "non localisé" — puis attend la réponse du jardinier (`oui` / `non`)
- [ ] CA3 : Après confirmation (`oui`), tous les événements liés à cette parcelle ont leur `parcelle_id` mis à `NULL` (= "non localisé") de manière atomique
- [ ] CA4 : La parcelle est désactivée (`actif = False`) — elle disparaît de `/parcelle lister` et de `/plan` sans être physiquement supprimée de la base
- [ ] CA5 : Un message de confirmation finale récapitule : nom supprimé et nombre d'événements réaffectés
- [ ] CA6 : Si la parcelle est introuvable (nom inconnu ou déjà supprimée), le bot répond avec un message d'erreur explicite et n'engage aucune modification
- [ ] CA7 : Si le jardinier répond `non` (ou envoie autre chose qu'`oui`), la suppression est annulée sans aucune modification et le bot le confirme
- [ ] CA8 : Les événements réaffectés (`parcelle_id = NULL`) s'affichent sous le libellé `Non localisé` dans `/historique`, `/stats` et les réponses de confirmation d'action
- [ ] CA9 : Si la parcelle ne possède aucun événement, le message de confirmation l'indique explicitement (`"Aucun événement associé"`) et la suppression reste soumise à confirmation

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram (`bot.py`), gestion parcelles (`utils/parcelles.py`), affichage (`/historique`, `/stats`, `/plan`)
- Migration BDD requise : **non** — `parcelle_id` est déjà `nullable=True` (migration v12) ; `Parcelle.actif` existe déjà
- Le flux de confirmation peut s'appuyer sur `ConversationHandler` (pattern déjà utilisé dans `/corriger`) ou sur un état stocké dans `context.user_data`
- La réaffectation et la désactivation doivent être atomiques (même transaction SQL) pour éviter un état incohérent en cas d'erreur
- Le libellé `Non localisé` est à centraliser (constante ou helper) pour une cohérence entre toutes les vues
- Ne pas exposer `/parcelle supprimer` dans le `/help` général : commande à risque, réserver à une aide ciblée (`/help parcelle`)
- Dépendances : US_Plan_occupation_parcelles (architecture `/parcelle` déjà en place), US-006 (pattern renommer)

**Estimation :** 3 points

**Ajustements de scénarios proposés (discussion PO) :**

> **Ajustement 1 — Confirmation avec compte rendu :**
> Le message de confirmation affiche le nombre d'événements *avant* de demander l'accord. Cela permet au jardinier de prendre une décision informée ("32 événements vont être délocalisés" vs "0 événement").
>
> **Ajustement 2 — Réponse libre vs boutons inline :**
> Pour la confirmation, privilégier les boutons inline Telegram (`✅ Confirmer` / `❌ Annuler`) plutôt que la saisie libre `oui/non` — plus sûr sur mobile, moins de gestion d'erreur de frappe.
>
> **Ajustement 3 — Pas de suppression physique (soft delete) :**
> `actif = False` est préféré à `DELETE` pour préserver l'intégrité référentielle et permettre une restauration manuelle en base si nécessaire.

**Scénario Gherkin :**
```gherkin
Feature: Suppression d'une parcelle avec réaffectation des événements

  Scenario: Suppression nominale d'une parcelle avec événements
    Given une parcelle nommée "serre-1" existe et possède 12 événements
    When le jardinier envoie la commande /parcelle supprimer serre-1
    Then le bot affiche "Supprimer serre-1 ? 12 événements seront réaffectés en Non localisé."
    And le bot propose les boutons "✅ Confirmer" et "❌ Annuler"
    When le jardinier appuie sur "✅ Confirmer"
    Then les 12 événements ont parcelle_id = NULL
    And la parcelle serre-1 a actif = False
    And le bot confirme "✅ Parcelle serre-1 supprimée — 12 événements réaffectés en Non localisé"

  Scenario: Annulation de la suppression
    Given une parcelle nommée "potager" existe et possède 5 événements
    When le jardinier envoie la commande /parcelle supprimer potager
    And le jardinier appuie sur "❌ Annuler"
    Then aucune modification n'est effectuée en base
    And le bot répond "Suppression annulée — la parcelle potager est conservée"

  Scenario: Suppression d'une parcelle sans événements
    Given une parcelle nommée "essai" existe et ne possède aucun événement
    When le jardinier envoie la commande /parcelle supprimer essai
    Then le bot affiche "Supprimer essai ? Aucun événement associé."
    And le bot propose les boutons "✅ Confirmer" et "❌ Annuler"
    When le jardinier appuie sur "✅ Confirmer"
    Then la parcelle essai a actif = False
    And le bot confirme "✅ Parcelle essai supprimée"

  Scenario: Parcelle introuvable
    Given aucune parcelle nommée "inexistante" n'existe dans la base
    When le jardinier envoie la commande /parcelle supprimer inexistante
    Then le bot répond "❌ Parcelle introuvable : inexistante"
    And aucune modification n'est effectuée en base

  Scenario: Affichage des événements réaffectés dans /historique
    Given 3 événements ont été réaffectés en Non localisé suite à la suppression de "serre-1"
    When le jardinier envoie la commande /historique
    Then les 3 événements apparaissent avec le libellé "Non localisé" à la place de "serre-1"
```

**Labels GitHub :** `us`, `sprint-5`, `bot-telegram`, `parcelles`

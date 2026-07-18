**ID :** US-047
**Titre :** Contrôler les actions par rôle (owner / editor / lecteur)
**Épic :** ÉPIC 2 — Identité & accès

**Story :**
En tant que propriétaire d'un potager partagé
Je veux que chaque membre n'agisse que selon le rôle qui lui a été attribué
Afin qu'un simple lecteur ne puisse ni modifier ni supprimer des données, et que la gestion du potager reste réservée aux personnes de confiance

**Contexte fonctionnel :**
Le socle `potager_membres` (US-040) porte déjà un `role` (`owner`, `editor`, `lecteur`) mais rien ne le vérifie aujourd'hui. Cette US applique la matrice de permissions dans la couche services (US-041), au même endroit pour le bot et la PWA — un seul point de vérification, jamais dupliqué. Elle doit aussi couper court à l'appel LLM de parsing pour un lecteur qui dicterait une action, ce qui a un impact tokens positif direct.

**Critères d'acceptance :**
- [ ] CA1 : Un membre `lecteur` peut consulter (stats, historique, questions via `/ask`) mais toute tentative d'enregistrer, corriger ou supprimer un événement est refusée
- [ ] CA2 : Un membre `editor` peut consulter et saisir/corriger/supprimer des événements, mais ne peut pas gérer les membres du potager ni ses paramètres
- [ ] CA3 : Un membre `owner` a tous les droits de l'`editor`, plus la gestion des membres (invitation, changement de rôle, retrait) et la suppression du potager
- [ ] CA4 : La vérification du rôle a lieu **avant** tout appel au parsing LLM (`parse_actions`) : un lecteur qui dicte "j'ai récolté 2 kg de tomates" ne déclenche aucun appel Groq, et reçoit un message expliquant qu'il n'a pas les droits nécessaires
- [ ] CA5 : Le message de refus est explicite et cohérent entre le bot Telegram et la PWA (ex. « Tu es lecteur sur ce potager, tu ne peux pas enregistrer d'action »)
- [ ] CA6 : La vérification de rôle est centralisée dans la couche services (garde unique, ex. `require_role(ctx, 'editor')`), jamais dupliquée dans `bot.py` ou `main.py`
- [ ] CA7 : Une tentative d'action non autorisée est journalisée (log structuré) sans lever d'exception non gérée côté utilisateur

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : couche services (garde de rôle) + interaction Telegram + PWA (messages d'erreur)
- Migration BDD requise : **non** — la colonne `role` existe déjà depuis US-040 (`potager_membres.role`)
- Dépendances : US-040 (`potager_membres.role`), US-041 (couche services centralisée), US-046 (potager actif, nécessaire pour savoir sur quel potager évaluer le rôle du membre)
- Impact tokens : **positif** — blocage avant appel LLM pour les lecteurs (CA4), à mesurer et loguer comme les autres US touchant au coût Groq
- Invariants projet : ordre critique des flux de conversation préservé — le garde de rôle s'insère dans le pipeline de traitement d'une action AVANT le parsing, sans perturber les modes `corr_*`/`ask` déjà en place (US-102/US-042)

**Notes techniques (pour Persona Developer) :**
- Composants impactés : `services/` (nouveau garde `require_role`, appliqué dans chaque fonction de service d'écriture : `enregistrer_evenement`, corrections, suppressions), `bot.py` et `main.py` (propagation du message de refus, pas de logique de rôle dupliquée)
- La matrice de permissions (lecteur/editor/owner) doit être définie une seule fois, idéalement sous forme de table ou constante partagée, pour éviter toute divergence entre bot et PWA
- La gestion des membres elle-même (invitation, changement de rôle, retrait) est développée dans US-048 — cette US se limite à faire respecter les rôles existants sur les actions déjà en place
- Vérifier que le garde s'applique aussi aux endpoints REST de la PWA équivalents (pas seulement au bot), sous peine de contourner la protection via l'API directement

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Lecteur bloqué avant appel LLM
  Given un membre avec le rôle "lecteur" sur son potager actif
  When il dicte "j'ai récolté 2 kg de tomates"
  Then aucun appel au parsing LLM n'a lieu
  And rien n'est enregistré
  And il reçoit un message expliquant qu'il n'a pas les droits nécessaires

Scénario: Lecteur autorisé en consultation
  Given un membre avec le rôle "lecteur"
  When il demande ses statistiques ou pose une question via /ask
  Then la réponse lui est fournie normalement

Scénario: Editor autorisé à saisir
  Given un membre avec le rôle "editor"
  When il dicte "j'ai récolté 2 kg de tomates"
  Then l'événement est enregistré normalement

Scénario: Editor refusé sur la gestion des membres
  Given un membre avec le rôle "editor"
  When il tente d'inviter un nouveau membre ou de changer un rôle
  Then l'action est refusée avec un message explicite

Scénario: Owner autorisé sur toutes les actions
  Given un membre avec le rôle "owner"
  When il gère les membres, saisit des événements ou consulte des données
  Then toutes ces actions sont autorisées
```

**Labels GitHub :** `us`, `sprint-identite-acces`, `security`, `multi-tenant`, `permissions`

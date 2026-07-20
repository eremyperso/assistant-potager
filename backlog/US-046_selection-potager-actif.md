**ID :** US-046
**Titre :** Sélectionner et changer de potager actif
**Épic :** ÉPIC 2 — Identité & accès

**Story :**
En tant qu'utilisateur membre de plusieurs potagers
Je veux choisir sur quel potager portent mes saisies et mes questions à un instant donné
Afin de ne jamais enregistrer ou consulter des données dans le mauvais potager

**Contexte fonctionnel :**
Un même utilisateur peut appartenir à plusieurs potagers (table `potager_membres` du socle US-040). Depuis US-044/US-045, l'identité est établie côté web et Telegram, mais le `TenantContext` n'a pas encore de `potager_id` fiable dès qu'un utilisateur a plus d'un potager. Cette US introduit la notion de potager actif, mémorisée par utilisateur et utilisée pour construire le `TenantContext` de chaque requête, côté web comme côté Telegram.

**Critères d'acceptance :**
- [ ] CA1 : Un utilisateur membre d'un seul potager voit ce potager sélectionné automatiquement comme potager actif, sans action de sa part
- [ ] CA2 : Un utilisateur membre de plusieurs potagers peut lister ses potagers via la commande `/potager` (Telegram, boutons inline) et via un sélecteur dans la PWA
- [ ] CA3 : Le changement de potager actif est immédiatement pris en compte : toute saisie ou question suivante (bot ou PWA) porte sur le nouveau potager sélectionné
- [ ] CA4 : Le potager actif est mémorisé par utilisateur (persistant entre sessions), pas seulement pour la durée d'une conversation
- [ ] CA5 : Un utilisateur qui n'appartient à aucun potager reçoit un message clair l'invitant à en créer un ou à rejoindre un potager existant (renvoi vers le parcours de US-048)
- [ ] CA6 : Le `TenantContext` construit à chaque requête (bot et API) utilise systématiquement le potager actif de l'utilisateur, sans valeur en dur

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram (commande `/potager`) + PWA (sélecteur de potager) + couche services (construction du `TenantContext`)
- Migration BDD requise : **oui** — colonne `users.potager_actif_id` (nullable, FK vers `potagers`) ; peut être livrée avec US-045 dans la même migration si les deux US sont développées ensemble
- Dépendances : US-040 (`potager_membres`), US-041 (`TenantContext`), US-045 (identité Telegram liée, nécessaire pour proposer `/potager` à un chat identifié)
- Zéro impact tokens Groq (hors cas où le changement de potager déclenche un message de confirmation, négligeable)
- Invariants projet : `TenantContext` reste construit une fois par requête dans la couche services, jamais recalculé ad hoc dans `bot.py`/`main.py`

**Notes techniques (pour Persona Developer) :**
- Composants impactés : `bot.py` (nouvelle commande `/potager` + callback inline de sélection), PWA (composant sélecteur), `services/` (fonction de résolution du `TenantContext` à partir de `users.potager_actif_id`), migration SQL
- Le cas "sélection automatique silencieuse" (CA1) doit rester silencieux même si l'utilisateur rejoint un deuxième potager ultérieurement — à ce moment-là, bascule explicite requise (ne pas changer le potager actif sans action utilisateur)
- Cette US ne gère pas la création de potager ni l'invitation de membres (US-048) — elle suppose que l'utilisateur est déjà membre d'au moins un potager pour les CA1-CA4
- Prévoir l'invalidation du potager actif si l'utilisateur perd son accès (retrait par un owner, cf. US-048) — dépendance croisée à documenter, l'implémentation complète du retrait relève de US-048

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Sélection automatique pour un seul potager
  Given un utilisateur membre d'un seul potager
  When il se connecte ou envoie un message au bot
  Then ce potager est automatiquement son potager actif

Scénario: Changement de potager actif via Telegram
  Given un utilisateur membre de deux potagers "Jardin Nord" et "Jardin Sud"
  When il envoie "/potager" et sélectionne "Jardin Sud"
  Then son potager actif devient "Jardin Sud"
  And ses saisies suivantes sont enregistrées dans "Jardin Sud"

Scénario: Persistance entre sessions
  Given un utilisateur a sélectionné "Jardin Sud" comme potager actif
  When il ferme et rouvre la PWA le lendemain
  Then "Jardin Sud" reste son potager actif

Scénario: Utilisateur sans potager
  Given un utilisateur n'appartient à aucun potager
  When il tente de dicter une action
  Then il reçoit un message l'invitant à créer ou rejoindre un potager
```

**Labels GitHub :** `us`, `sprint-identite-acces`, `telegram`, `pwa`, `multi-tenant`

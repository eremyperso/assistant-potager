**ID :** US-048
**Titre :** Créer un potager et inviter des membres en self-service
**Épic :** ÉPIC 2 — Identité & accès

**Story :**
En tant que nouvel utilisateur ou propriétaire de potager
Je veux créer un potager, inviter des membres et gérer leur accès sans intervention d'un administrateur
Afin de pouvoir démarrer et faire vivre un potager partagé de bout en bout, de l'inscription à la première saisie vocale

**Contexte fonctionnel :**
C'est l'US qui referme le parcours complet de l'ÉPIC 2 : jusqu'ici, la création d'un potager et le rattachement d'un membre nécessitaient une opération manuelle (comme aujourd'hui pour le potager #1). Cette US rend tout le cycle self-service : inscription (US-044) → création ou adhésion à un potager → liaison Telegram (US-045) → sélection du potager actif (US-046) → première saisie, sans qu'un administrateur n'ait à toucher la base de données.

**Critères d'acceptance :**
- [ ] CA1 : Un utilisateur connecté peut créer un nouveau potager depuis la PWA en renseignant un nom et une localisation (latitude/longitude, ou adresse résolue en coordonnées) ; il en devient automatiquement `owner`
- [ ] CA2 : La localisation saisie est celle qui alimentera la météo par potager dans une US ultérieure (US-124) — cette US se limite à la capturer et la stocker correctement
- [ ] CA3 : Un `owner` peut inviter un membre par e-mail ou par lien/code d'invitation, en proposant un rôle (`editor` ou `lecteur`) au moment de l'invitation
- [ ] CA4 : L'acceptation d'une invitation (par la personne invitée, après inscription si elle n'a pas encore de compte) insère une ligne dans `potager_membres` avec le rôle proposé
- [ ] CA5 : Un `owner` peut retirer un membre de son potager à tout moment
- [ ] CA6 : Un membre retiré perd l'accès immédiatement : son potager actif (US-046) est invalidé s'il pointait vers ce potager, et toute requête ultérieure sur ce potager est refusée
- [ ] CA7 : Le parcours complet (inscription → création ou adhésion à un potager → liaison Telegram → première saisie vocale réussie) est réalisable sans aucune intervention manuelle en base de données ni sur le serveur
- [ ] CA8 : Une invitation expirée ou déjà utilisée est refusée avec un message explicite, sur le même principe que le code de liaison Telegram (US-045)

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : PWA (création de potager, gestion des membres, acceptation d'invitation) + couche services
- Migration BDD requise : **oui** — table `invitations` (potager_id, email ou code, role_propose, cree_le, expire_le, utilisee_le), numéro de migration à vérifier au moment de l'implémentation
- Dépendances : US-040 (`potagers`, `potager_membres`), US-041 (couche services), US-044 (identité web pour créer un compte et accepter une invitation), US-046 (invalidation du potager actif lors d'un retrait), US-047 (seul un `owner` peut inviter/retirer — la garde de rôle doit déjà être en place)
- Zéro impact tokens Groq direct
- Invariants projet : migration en fichier séparé idempotent avec rollback documenté ; envoi d'e-mail (si retenu pour l'invitation) doit être un service isolé et remplaçable, cohérent avec le choix technique déjà fait ou à faire pour la réinitialisation de mot de passe (US-044, hors périmètre)

**Notes techniques (pour Persona Developer) :**
- Composants impactés : nouveau service `services/potagers.py` (création, invitation, retrait de membre), nouveaux endpoints PWA (`POST /potagers`, `POST /potagers/{id}/invitations`, `POST /invitations/{code}/accepter`, `DELETE /potagers/{id}/membres/{user_id}`), migration SQL
- Si l'envoi d'e-mail transactionnel n'est pas encore disponible dans le projet, prévoir en repli un lien/code d'invitation copiable manuellement (pas de blocage total de l'US pour cette raison) — à trancher explicitement dans le raffinement de l'US avant développement
- CA6 (invalidation immédiate) dépend de la mécanique de potager actif de US-046 : vérifier que le retrait déclenche bien une resélection ou un message clair au prochain accès du membre retiré, pas une erreur technique brute
- Le cas du dernier `owner` qui quitte ou retire son propre accès à un potager partagé n'est PAS couvert par cette US (transfert de propriété ou suppression du potager) — explicitement hors périmètre, à traiter dans US-132 (RGPD, suppression de compte) qui mentionne déjà ce risque

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Scénario: Création d'un potager
  Given un utilisateur connecté sans potager
  When il crée un potager avec un nom et une localisation
  Then le potager est créé
  And l'utilisateur en est owner
  And ce potager devient son potager actif

Scénario: Invitation et acceptation
  Given un owner d'un potager
  When il invite un nouvel utilisateur avec le rôle "editor"
  And l'utilisateur invité accepte l'invitation
  Then l'utilisateur invité devient membre du potager avec le rôle "editor"

Scénario: Invitation expirée
  Given une invitation générée il y a plus de son délai de validité
  When l'invité tente de l'accepter
  Then l'acceptation est refusée avec un message explicite

Scénario: Retrait d'un membre
  Given un owner et un membre "editor" sur le même potager
  When l'owner retire ce membre
  Then le membre perd immédiatement l'accès au potager
  And si ce potager était son potager actif, il en est notifié au prochain accès

Scénario: Parcours complet sans intervention manuelle
  Given un nouvel utilisateur sans compte
  When il s'inscrit, crée un potager, lie son compte Telegram et effectue sa première saisie vocale
  Then toutes ces étapes réussissent sans aucune action d'un administrateur
```

**Labels GitHub :** `us`, `sprint-identite-acces`, `pwa`, `onboarding`, `multi-tenant`

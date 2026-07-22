**ID :** US-050
**Titre :** Dissocier un chat Telegram d'un compte
**Épic :** ÉPIC 2 — Identité & accès

**Story :**
En tant qu'utilisateur ayant lié un chat Telegram à mon compte web
Je veux pouvoir dissocier ce chat de mon compte
Afin de pouvoir relier un autre chat Telegram (changement de téléphone, compte de test, erreur de liaison) sans dépendre d'une intervention manuelle en base de données

**Contexte fonctionnel :**
US-045 a délibérément laissé cette action hors périmètre : CA5 de US-045 mentionne explicitement qu'une tentative de liaison d'un `chat_id` déjà lié à un autre compte doit « proposer une procédure de déliaison, hors périmètre technique de cette US si elle nécessite une action de support ». En pratique, la seule procédure existante aujourd'hui est un `UPDATE users SET telegram_chat_id = NULL` manuel en base — un goulot d'étranglement dès qu'il y a plus d'un compte de test ou un utilisateur réel qui change de téléphone. Cette US referme ce trou en rendant la dissociation self-service, sans intervention d'un administrateur.

**Critères d'acceptance :**
- [ ] CA1 : Depuis la PWA (utilisateur authentifié), un écran/bouton permet de dissocier le chat Telegram actuellement lié à son compte
- [ ] CA2 : Depuis Telegram, la commande `/delier` (envoyée depuis le chat actuellement lié) propose une confirmation explicite avant d'exécuter la dissociation (même principe que la confirmation de suppression d'un événement, US existant `/corriger`)
- [ ] CA3 : Après dissociation, `users.telegram_chat_id` repasse à `NULL` et le chat est immédiatement traité comme non lié dès l'interaction suivante — le garde de liaison déjà en place (US-045 CA6/CA7) s'applique sans aucune modification de sa part
- [ ] CA4 : Une fois dissocié, l'utilisateur peut générer un nouveau code depuis la PWA (US-045 CA1) et lier le même chat ou un chat différent, sans délai d'attente artificiel
- [ ] CA5 : La dissociation ne dépend d'aucun rôle potager (`ctx.role`, US-047) — c'est une action d'identité, disponible à un membre `lecteur` comme à un `owner`, indépendamment du potager actif ; elle ne doit jamais passer par `require_role`/`TenantContext`
- [ ] CA6 : Aucune donnée métier n'est supprimée ou modifiée par la dissociation — événements, parcelles et appartenance aux potagers (`potager_membres`) restent strictement inchangés, seul le lien `telegram_chat_id ↔ user_id` est rompu
- [ ] CA7 : Toute dissociation est journalisée (log structuré `potager`) avec `user_id` et l'ancien `chat_id`, pour traçabilité en cas de support

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram (nouvelle commande `/delier`) + PWA (action dans les paramètres de compte)
- Migration BDD requise : **non** — `users.telegram_chat_id` est déjà une colonne nullable (US-040), aucune structure supplémentaire nécessaire
- Dépendances : US-045 (liaison Telegram — cette US en est le pendant symétrique), US-047 (rappel explicite CA5 : ne pas réutiliser le garde de rôle potager pour cette action)
- Impact tokens : nul — aucun appel Groq impliqué
- Invariants projet : logging structuré conservé (invariant projet) ; ne pas confondre l'identité (`user_id` ↔ `telegram_chat_id`, stable et permanente une fois liée — cf. note d'architecture de US-045) avec le potager actif (US-046, qui lui varie par requête) — la dissociation ne touche que la première

**Notes techniques (pour Persona Developer) :**
- Composants impactés : `app/services/liaison_telegram.py` (nouvelle fonction `delier_chat_id(db, user_id)` — symétrique de `lier_chat_id`), `bot.py` (commande `/delier` avec étape de confirmation, sur le même modèle que `_corr_confirm_delete`), `main.py` (nouvel endpoint PWA, ex. `POST /auth/lien/delier`, protégé par `get_current_user` — **pas** `get_current_user_ctx` —, cohérent avec `POST /auth/lien/generer-code` qui ne dépend déjà pas d'un potager)
- `/delier` doit être accessible même à un chat dont l'utilisateur n'a aucun potager (l'action porte sur l'identité, pas sur les données potager) — vérifier qu'elle n'est pas placée derrière le garde de liaison au potager actif par erreur
- Réutiliser le pattern de confirmation déjà présent dans `bot.py` (`ReplyKeyboardMarkup` oui/non) plutôt qu'une exécution immédiate sur simple `/delier`, pour éviter une perte accidentelle d'accès vocal
- Si le chat qui envoie `/delier` n'est pas actuellement lié (cas déjà couvert par le garde de liaison générique de US-045), le message d'onboarding standard s'affiche — pas de cas particulier à coder

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Dissociation depuis la PWA
  Given un utilisateur authentifié dont le chat Telegram est lié
  When il dissocie son chat depuis la PWA
  Then users.telegram_chat_id repasse à NULL
  And le chat est traité comme non lié dès le message suivant

Scénario: Dissociation depuis Telegram avec confirmation
  Given un chat actuellement lié à un compte
  When l'utilisateur envoie "/delier" et confirme
  Then le chat est dissocié
  And un message de confirmation est renvoyé

Scénario: Dissociation annulée
  Given un chat actuellement lié à un compte
  When l'utilisateur envoie "/delier" mais répond "non" à la confirmation
  Then le chat reste lié
  And aucune modification n'est effectuée

Scénario: Reliaison après dissociation
  Given un compte dont le chat vient d'être dissocié
  When l'utilisateur génère un nouveau code depuis la PWA et le saisit via "/lier"
  Then le chat est de nouveau lié, au même compte ou à un autre

Scénario: Dissociation indépendante du rôle potager
  Given un membre avec le rôle "lecteur" sur son potager actif
  When il dissocie son chat Telegram
  Then l'action réussit normalement
  And aucune vérification de rôle potager n'a été effectuée
```

**Labels GitHub :** `us`, `sprint-identite-acces`, `telegram`, `security`

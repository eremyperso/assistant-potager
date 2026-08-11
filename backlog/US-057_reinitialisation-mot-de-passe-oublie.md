**ID :** US-057
**Titre :** Permettre la réinitialisation du mot de passe oublié
**Épic :** ÉPIC 2 — Identité & accès

**Story :**
En tant qu'utilisateur ayant oublié son mot de passe
Je veux recevoir un lien par e-mail pour en définir un nouveau
Afin de retrouver l'accès à mon compte sans intervention manuelle

**Contexte fonctionnel :**
Aucun mécanisme de réinitialisation n'existe aujourd'hui côté backend (`main.py` n'expose que `/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/verify-email`, `/auth/resend-verification`). Le lien "Mot de passe oublié ?" introduit par la maquette sur l'écran de connexion (US-056) n'a donc, avant cette US, aucun comportement fonctionnel. Cette US réutilise l'infrastructure d'envoi d'e-mail déjà en place (Brevo, `app/services/email.py`, dégradée en log si `BREVO_API_KEY` absent — cf. section "Vérification d'e-mail" de `CLAUDE.md`) et reprend le même schéma de token à usage unique que la vérification d'e-mail (`verification_token_hash` / `_expire_le` / `_utilise_le` sur `User`, US-044) : seul le hash du token est stocké, jamais la valeur brute.

**Critères d'acceptance :**
- [ ] CA1 : Depuis le lien "Mot de passe oublié ?" (US-056), un formulaire demande l'adresse e-mail ; sa soumission appelle `POST /auth/mot-de-passe-oublie`, qui répond toujours avec un message générique de succès (n'indique jamais si le compte existe, même logique que `/auth/register` CA7) et envoie un e-mail contenant un lien de réinitialisation à durée limitée (1h) uniquement si le compte existe
- [ ] CA2 : Le lien reçu ouvre un écran demandant un nouveau mot de passe + sa confirmation, avec la même règle de validité qu'à l'inscription (8 caractères minimum)
- [ ] CA3 : La soumission appelle `POST /auth/reinitialiser-mot-de-passe` (token + nouveau mot de passe) ; le mot de passe est mis à jour (haché, jamais stocké en clair) et le token est marqué utilisé (usage unique, comme `LiaisonTelegram.utilise_le`)
- [ ] CA4 : Un token expiré, déjà utilisé ou invalide renvoie une erreur explicite invitant à redemander un lien, jamais un échec silencieux ou une page blanche
- [ ] CA5 : `POST /auth/mot-de-passe-oublie` est soumis à un rate-limiting cohérent avec les autres endpoints d'auth (`/auth/login` : 10/minute, `/auth/register` : 5/minute), pour limiter l'énumération de comptes par e-mail
- [ ] CA type (US avec impact visuel/UI) : les deux nouveaux écrans (demande de réinitialisation, nouveau mot de passe) suivent les tokens et composants du design system livré en US-052/US-056 — aucune maquette de référence Claude Design ne couvre spécifiquement ces deux écrans, la cohérence visuelle avec l'écran de connexion (US-056) fait foi plutôt qu'un rendu pixel-perfect à valider à 375/768/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction web, authentification
- Migration BDD requise : oui — nouvelles colonnes sur `users` (`reset_mdp_token_hash`, `reset_mdp_token_expire_le`, `reset_mdp_token_utilise_le`), même pattern que `verification_token_*` (migration_v25.sql)
- Dépendances : US-056 (écran de connexion — point d'entrée du lien), US-044 (schéma de token à usage unique et infra Brevo réutilisés)
- Limite connue, assumée pour cette US : les tokens d'accès/refresh (JWT stateless, sans registre de révocation) déjà émis avant la réinitialisation restent valides jusqu'à leur expiration naturelle (max 30 jours) — invalider les sessions actives à la volée nécessiterait un mécanisme de révocation qui n'existe pas encore et sort du périmètre de cette US

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Demande de réinitialisation pour un compte existant
  Given un utilisateur avec un compte e-mail vérifié
  When il soumet son e-mail sur l'écran "Mot de passe oublié"
  Then il reçoit un message générique de succès et un e-mail avec un lien de réinitialisation valable 1h

Scénario: Demande de réinitialisation pour un e-mail inconnu
  Given une adresse e-mail qui ne correspond à aucun compte
  When elle est soumise sur l'écran "Mot de passe oublié"
  Then le même message générique de succès est affiché, sans e-mail envoyé, et sans indication que le compte n'existe pas

Scénario: Réinitialisation réussie
  Given un lien de réinitialisation valide reçu par e-mail
  When l'utilisateur saisit un nouveau mot de passe valide et confirme
  Then son mot de passe est mis à jour et il peut se connecter avec le nouveau mot de passe

Scénario: Lien de réinitialisation déjà utilisé
  Given un lien de réinitialisation déjà utilisé une première fois
  When l'utilisateur tente de le réutiliser
  Then une erreur explicite l'invite à redemander un nouveau lien
```

**Labels GitHub :** `us`, `sprint-refonte-ui-2026`, `backend`, `auth`

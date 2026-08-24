# Connexion Google — paragraphe destiné à la politique de confidentialité

**Produit par US-090 (CA20). À intégrer par US-132 (RGPD & conformité).**

La politique de confidentialité d'Assistant Potager n'existe pas encore : les
liens de l'écran d'authentification (`frontend/src/views/Auth.jsx`) pointent
toujours sur `#`. US-090 livre donc **le texte**, pas sa publication — cette
dépendance documentaire ne bloque pas la livraison de la fonctionnalité, mais
elle reste ouverte tant qu'US-132 ne l'a pas reprise.

---

## Paragraphe à insérer — « Connexion via un fournisseur d'identité »

> ### Connexion avec votre compte Google
>
> Assistant Potager vous permet de créer votre compte et de vous connecter avec
> votre compte Google. Ce mode de connexion est **facultatif** : la création
> d'un compte par adresse e-mail et mot de passe reste disponible et donne accès
> aux mêmes fonctionnalités.
>
> **Ce que nous recevons de Google.** Lorsque vous choisissez « Continuer avec
> Google » et que vous donnez votre consentement sur l'écran affiché par Google,
> nous recevons uniquement :
>
> | Donnée | Usage | Conservation |
> |---|---|---|
> | Un identifiant technique de compte (`sub`) | Reconnaître votre compte d'une connexion à l'autre, y compris si votre adresse e-mail change | Durée de vie du compte |
> | Votre adresse e-mail et l'indication que Google la considère comme vérifiée | Identifier votre compte, vous adresser les messages liés au service, et rattacher automatiquement une connexion Google à un compte que vous auriez déjà ouvert avec la même adresse | Durée de vie du compte |
> | Votre nom | Vous nommer dans l'application | Durée de vie du compte |
>
> Nous ne demandons **aucun** autre accès à votre compte Google : ni vos
> contacts, ni votre agenda, ni vos fichiers, ni l'autorisation d'agir en votre
> nom hors de votre présence.
>
> **Ce que nous ne conservons pas.** Les jetons émis par Google au moment de la
> connexion servent uniquement à vérifier votre identité pendant les quelques
> secondes de celle-ci, puis sont abandonnés : ils ne sont jamais enregistrés.
> Une fois votre identité vérifiée, votre session repose exclusivement sur les
> jetons émis par Assistant Potager.
>
> **Ce que Google apprend de nous.** Google est informé que vous vous connectez
> à Assistant Potager, à la date et à l'heure de chaque connexion. Le
> traitement que Google fait de cette information relève de sa propre politique
> de confidentialité.
>
> **Base légale.** Votre consentement, exprimé au moment où vous acceptez le
> partage de votre profil sur l'écran affiché par Google.
>
> **Comment revenir en arrière.**
>
> - Vous pouvez retirer à tout moment l'accès d'Assistant Potager à votre compte
>   Google depuis la page « Applications tierces ayant accès à votre compte » de
>   votre compte Google. Cela vous empêchera de vous reconnecter par ce moyen ;
>   votre compte Assistant Potager et vos données de potager restent intacts.
> - Pour continuer à accéder à votre compte sans Google, utilisez « Mot de passe
>   oublié ? » depuis l'écran de connexion : vous recevrez un lien vous
>   permettant de définir un mot de passe.
> - La suppression de votre compte Assistant Potager et de ses données relève de
>   la procédure décrite au chapitre « Suppression de votre compte ».

---

## Notes d'intégration pour US-132

- **Sous-traitance / transfert hors UE** : Google Ireland Limited est
  responsable de traitement pour l'authentification. Le paragraphe ci-dessus
  décrit ce que *nous* recevons ; le chapitre « Destinataires et transferts »
  de la politique doit mentionner Google au même titre que Brevo (envoi
  d'e-mails, hébergement UE) et Groq (traitement des commandes en langage
  naturel).
- **Registre des traitements** : ajouter la finalité « authentification des
  utilisateurs par fédération d'identité », base légale « consentement »,
  catégories de données « identifiant technique, e-mail, nom ».
- **Cohérence avec l'écran d'inscription** : le texte de consentement affiché
  sous le formulaire d'inscription (`Auth.jsx`, CA20) nomme déjà Google et les
  trois catégories de données. Toute reformulation ici doit y être répercutée.
- **Facebook** : abandonné définitivement (US-090), aucun paragraphe à prévoir.
- **Telegram** : le canal Telegram (US-091) n'est pas un fournisseur d'identité.
  Il relève d'un paragraphe distinct, à rédiger avec cette US.

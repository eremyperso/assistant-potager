**ID :** US-056
**Titre :** Refondre l'écran de connexion et d'inscription selon la maquette "potager 2026"
**Épic :** ÉPIC 2 — Identité & accès

**Story :**
En tant que visiteur non encore authentifié
Je veux un écran de connexion/inscription au design cohérent avec le reste de l'application refondue
Afin que la première impression de l'application (avant même d'entrer dans le potager) soit alignée avec le nouveau design system

**Contexte fonctionnel :**
`frontend/src/views/Auth.jsx` (US-044) est aujourd'hui une simple carte centrée, mobile-only, sur les alias `var(--g-*)` — un seul écran pour connexion/inscription, e-mail + mot de passe uniquement, pas de layout desktop dédié. La maquette Claude Design "potager 2026" a été enrichie d'un module `login-screens.jsx` (fichier focal `Potager - Connexion.html`, dépendances `web-tokens.jsx` / `web-parts.jsx`) qui propose un écran scindé : panneau de marque à gauche (visible ≥ 900px de conteneur) + formulaire à droite, bascule Connexion/Créer un compte, connecteurs OAuth (Google/Facebook/Telegram), et un champ "Nom" à l'inscription. Voir `docs/ANALYSE_REFONTE_UI_WEB_2026.md` §5.7.

Cette US porte le **portage visuel et les ajustements mineurs à iso-périmètre** (nouveau champ Nom, affichage des connecteurs OAuth en état désactivé). Elle ne couvre ni la réinitialisation de mot de passe (US-057), ni le branchement réel d'une authentification OAuth (hors périmètre, voir écarts assumés en §5.7).

**Critères d'acceptance :**
- [ ] CA1 : L'écran reproduit le layout scindé de la maquette : sous 900px de largeur de conteneur, le formulaire occupe toute la largeur avec logo + bouton de thème en tête et un pied de page compact (mentions légales) ; à partir de 900px, un panneau de marque apparaît à gauche (accroche produit + repères génériques, non liés à un compte réel puisque l'écran est affiché avant authentification — pas de chiffres personnels comme dans la maquette de démonstration)
- [ ] CA2 : La bascule "Créer un compte" / "Se connecter" fonctionne comme aujourd'hui (même composant, changement de mode) et conserve le comportement métier actuel (`login`/`register` de `AuthContext.jsx`, vérification e-mail post-inscription inchangée)
- [ ] CA3 : Le formulaire d'inscription ajoute un champ "Nom" requis, transmis à `POST /auth/register` et stocké dans la colonne `User.nom` déjà existante (aucune migration) ; le formulaire de connexion garde uniquement e-mail + mot de passe
- [ ] CA4 : Le bouton d'affichage/masquage du mot de passe (déjà existant dans `Auth.jsx` actuel) est conservé, porté visuellement dans le nouveau champ de formulaire
- [ ] CA5 : Les trois connecteurs "Continuer avec Google / Facebook / Telegram" sont affichés conformément à la maquette (libellé complet en une colonne sous 420px de conteneur, icône seule sur trois colonnes à partir de 420px) mais **désactivés**, avec une indication visuelle explicite (ex. "Bientôt disponible") — aucune tentative d'authentification OAuth n'est déclenchée par cette US
- [ ] CA6 : Le lien "Mot de passe oublié ?" est visible en mode Connexion ; il ouvre le parcours livré par l'US-057 (peut renvoyer vers une route non encore fonctionnelle tant que l'US-057 n'est pas livrée, sans erreur JavaScript bloquante)
- [ ] CA7 : Le thème clair/sombre reste togglable depuis cet écran, cohérent avec le mécanisme déjà en place dans le reste de l'application
- [ ] CA type (US avec impact visuel/UI) : Le rendu (mode Connexion et Créer un compte, panneau visible et masqué) correspond visuellement à la maquette de référence à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction web (portage visuel très majoritaire ; seul le champ "Nom" à l'inscription est une extension fonctionnelle mineure)
- Migration BDD requise : non (colonne `User.nom` déjà existante, actuellement non alimentée à l'inscription)
- Dépendances : US-052 (design system — tokens, `Btn`, `Card`…), US-044 (logique de connexion/inscription actuelle, reprise sans changement)
- Nouveaux composants `components/ui/` à prévoir : champ de formulaire avec libellé/erreur (`Field`), bouton pleine largeur (réutilisable depuis `Btn` si compatible), bouton connecteur OAuth désactivé

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Scénario: Écran de connexion en desktop
  Given un visiteur non authentifié sur un écran ≥ 1280px
  When la page de connexion se charge
  Then le panneau de marque est visible à gauche et le formulaire de connexion à droite

Scénario: Écran de connexion en mobile
  Given un visiteur non authentifié sur un écran de 375px
  When la page de connexion se charge
  Then seul le formulaire est visible, avec le logo en tête et le pied de page compact

Scénario: Inscription avec le nouveau champ Nom
  Given un visiteur en mode "Créer un compte"
  When il remplit nom, e-mail et mot de passe puis valide
  Then le compte est créé avec ce nom, et le parcours de vérification e-mail existant se déclenche normalement

Scénario: Connecteur OAuth non fonctionnel
  Given un visiteur sur l'écran de connexion
  When il clique sur "Continuer avec Google"
  Then aucune authentification n'est déclenchée et l'état "Bientôt disponible" reste visible
```

**Labels GitHub :** `us`, `sprint-refonte-ui-2026`, `frontend`, `auth`

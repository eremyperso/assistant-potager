**ID :** US-055
**Titre :** Regrouper compte, membres et liaison Telegram dans un menu Compte unifié
**Épic :** ÉPIC 2 — Identité & accès

**Story :**
En tant qu'utilisateur de l'interface web
Je veux retrouver mon identité, mon rôle, la liaison Telegram et la gestion des membres dans un seul menu Compte
Afin de ne pas chercher ces actions dispersées en icônes séparées dans le bandeau

**Contexte fonctionnel :**
Aujourd'hui (`TopBar.jsx`), l'actualisation, le thème, la liaison Telegram, la gestion des membres (visible seulement pour le rôle `owner`) et la déconnexion sont des icônes indépendantes alignées à droite du bandeau — chacune déjà fonctionnelle (`LierTelegram.jsx`, `GestionMembres.jsx`, `useAuth().logout`). Cette US ne change **aucune logique métier** : elle regroupe ces actions dans un menu Compte (`AccountMenu` de la maquette) déclenché depuis l'avatar utilisateur, avec deux modales dédiées reprenant le contenu actuel de `LierTelegram.jsx` et `GestionMembres.jsx`. Voir `docs/ANALYSE_REFONTE_UI_WEB_2026.md` §5.6.

**Critères d'acceptance :**
- [ ] CA1 : Un menu Compte s'ouvre depuis l'avatar/nom de l'utilisateur en haut à droite du bandeau, affichant l'identité (nom, e-mail), le rôle de l'utilisateur sur le potager actif, puis les actions « Relier Telegram » (avec son état actuel : relié / à faire) et « Gérer les membres » (visible uniquement si le rôle sur le potager actif est `owner`, non-régression de la règle actuelle), la déconnexion, et la version de l'API en pied de menu
- [ ] CA2 : « Relier Telegram » ouvre une modale reprenant le contenu fonctionnel actuel de `LierTelegram.jsx` (état de la liaison, génération de code à durée limitée) sans changement de logique
- [ ] CA3 : « Gérer les membres » ouvre une modale reprenant le contenu fonctionnel actuel de `GestionMembres.jsx` (liste des membres, génération d'un code d'invitation avec rôle proposé, retrait d'un membre) sans changement de logique
- [ ] CA4 : Sous 900px de largeur, seuls le bouton de thème et l'avatar restent visibles en permanence dans le bandeau ; l'actualisation manuelle des données et les notifications basculent dans la première section du menu Compte plutôt que de disparaître
- [ ] CA5 : L'actualisation manuelle des données (fonction déjà existante via le bouton `RefreshCw` de `TopBar.jsx`) reste accessible aussi bien en desktop (icône dans le bandeau) qu'en mobile (entrée du menu Compte) — non-régression, cette fonction ne doit devenir inaccessible sur aucune taille d'écran
- [ ] CA6 : À 390px de large (mobile), la déconnexion, la liaison Telegram et la gestion des membres restent toutes accessibles depuis le menu Compte, sans être coupées ou masquées par manque de place
- [ ] CA type (US avec impact visuel/UI) : Le rendu du menu Compte (fermé et ouvert, desktop et mobile) correspond visuellement à la maquette de référence à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (portage UI de fonctionnalités existantes, aucune nouvelle règle métier)
- Migration BDD requise : non
- Dépendances : US-052 (design system), US-053 (coquille applicative), US-045 (liaison Telegram — logique déjà implémentée), US-047 (rôles — condition d'affichage de « Gérer les membres »)

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Ouverture du menu Compte
  Given un utilisateur owner de son potager actif
  When il clique sur son avatar dans le bandeau
  Then le menu affiche son identité, son rôle "owner", "Relier Telegram", "Gérer les membres", la déconnexion et la version de l'API

Scénario: Masquage de "Gérer les membres" pour un non-owner
  Given un utilisateur avec le rôle "editor" ou "lecteur" sur son potager actif
  When il ouvre le menu Compte
  Then l'entrée "Gérer les membres" n'apparaît pas

Scénario: Actualisation toujours accessible en mobile
  Given un utilisateur sur un écran de 390px de large
  When il ouvre le menu Compte
  Then l'action "Actualiser les données" y est présente et fonctionnelle

Scénario: Liaison Telegram inchangée fonctionnellement
  Given un utilisateur ouvre la modale "Relier Telegram" depuis le nouveau menu Compte
  When il génère un code de liaison
  Then le comportement (durée de validité, usage unique) est identique à celui de LierTelegram.jsx actuel
```

**Labels GitHub :** `us`, `sprint-refonte-ui-2026`, `frontend`, `multi-tenant`

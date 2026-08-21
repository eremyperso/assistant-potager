**ID :** US-082
**Titre :** Regrouper la gestion d'un potager dans un écran « Paramètres du potager »
**Épic :** ÉPIC 5 — Cycle de vie du potager

**Story :**
En tant que jardinier owner d'un potager
Je veux retrouver au même endroit l'identité, la localisation, les membres et les actions de cycle de vie de mon potager
Afin de ne plus chercher chaque réglage dans une modale différente et de comprendre d'un coup d'œil qui a accès à mon jardin

**Contexte fonctionnel :**
`docs/CONCEPTION_CYCLE_DE_VIE_POTAGER.md` §6.4 (proposée sous le numéro provisoire US-152) demande un
écran « Paramètres du potager ». Le cadrage a été écrit avant la livraison d'US-074 : une partie du
périmètre initial (renommer, modifier la localisation, `PATCH /potagers/{id}`) **existe déjà** dans
`ModalModifierPotager.jsx`, et la gestion des membres existe dans `GestionMembres.jsx` (US-048/US-055).

Cette US ne réinvente donc rien : elle **rassemble** ce qui est éclaté et crée l'emplacement d'accueil
des actions de cycle de vie livrées par US-083 (archiver), US-084 (supprimer), US-085 (transférer la
propriété) et US-086 (quitter). Sans cet écran, chaque US suivante ajouterait sa propre modale
orpheline dans un menu déjà chargé.

**Critères d'acceptance :**
- [ ] CA1 : Un écran « Paramètres du potager » est accessible depuis `PotagerMenu` ; l'entrée
      « Modifier le potager » (US-074) est **remplacée** par « Paramètres du potager » — pas de doublon d'accès
- [ ] CA2 : L'écran affiche en tête l'identité du potager : nom, ville (ou mention explicite « localisation
      non renseignée », jamais de valeur inventée — non-régression US-074/CA6), état (US-080), rôle de
      l'utilisateur courant, nombre de parcelles et de membres
- [ ] CA3 : Section « Identité » — modification du nom et de la localisation via le composant de
      recherche de ville existant (`VilleSearch`), reposant sur `PATCH /potagers/{id}` déjà livré ;
      réservée au rôle `owner`
- [ ] CA4 : Section « Membres » — réutilise la gestion existante (liste, rôle, invitation par code,
      retrait) sans en modifier le comportement
- [ ] CA5 : Section « Zone sensible », visuellement distincte et placée en bas : accueille les actions
      irréversibles ou lourdes (archiver, supprimer, transférer la propriété, quitter). Tant que les US
      correspondantes ne sont pas livrées, la section n'affiche que les actions disponibles — **jamais
      de bouton inactif ou factice**
- [ ] CA6 : Un membre `editor` ou `lecteur` accède à l'écran en lecture : il voit l'identité et les
      membres, ne voit **aucune** action `owner`, et l'écran explique en une phrase pourquoi (« Seul le
      propriétaire du potager peut modifier ces réglages »)
- [ ] CA7 : Nouvel endpoint `GET /potagers/{id}` réservé aux membres du potager : nom, ville,
      latitude/longitude, état, rôle de l'appelant, compteurs parcelles/membres — un non-membre reçoit
      le refus standard, sans révéler l'existence du potager
- [ ] CA8 : L'écran fonctionne pour un potager **archivé** (US-083) : il reste consultable, et seules
      les actions compatibles avec cet état sont proposées
- [ ] CA type (US avec impact visuel/UI) : Le rendu correspond au design system (US-052) et à la
      structure de navigation existante (US-053) à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation + configuration (PWA uniquement — hors périmètre Telegram, cf. §4.2 du document de conception)
- Migration BDD requise : non
- Dépendances : US-080 (état affiché), US-074 (`PATCH /potagers/{id}`, `VilleSearch`, `ModalModifierPotager` à absorber), US-048 (membres/invitations), US-047 (`require_role`), US-052/US-053 (design system et coquille)
- Prépare : US-083, US-084, US-085, US-086 — toutes y branchent leur action
- Zéro token Groq

**Notes techniques (pour Persona Developer) :**
- Composants impactés : nouvelle vue `frontend/src/views/ParametresPotager.jsx`, `PotagerMenu.jsx`, `ModalModifierPotager.jsx` (contenu réemployé, modale supprimée si plus appelée), `GestionMembres.jsx` (intégré, non dupliqué), `main.py` (`GET /potagers/{id}`)
- Ne pas dupliquer la logique de permission côté front : le front masque, le back refuse (invariant §9.4 du document de conception — double contrôle service + API)
- Sections destinées à plusieurs largeurs de conteneur : appliquer les **container queries** (règle projet CLAUDE.md), les breakpoints Tailwind restant réservés à la structure de page
- Vérifier la non-régression du parcours US-074 : localiser un potager créé avant la fonctionnalité doit rester possible en un chemin au moins aussi court

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: L'owner consulte les paramètres de son potager
  Given un jardinier owner du potager "Jardin de Vitry" comptant 4 parcelles et 2 membres
  When il ouvre "Paramètres du potager" depuis le menu potager
  Then il voit le nom, la ville, l'état "actif", son rôle, 4 parcelles et 2 membres
  And il peut modifier le nom et la localisation

Scénario: Un editor consulte les paramètres
  Given un membre au rôle "editor" du même potager
  When il ouvre "Paramètres du potager"
  Then il voit l'identité et la liste des membres
  And aucune action réservée au propriétaire ne lui est proposée
  And une phrase lui explique que seul le propriétaire peut modifier ces réglages

Scénario: Un non-membre tente d'accéder au détail
  Given un utilisateur qui n'est pas membre du potager 42
  When il appelle GET /potagers/42
  Then la requête est refusée sans révéler l'existence du potager

Scénario: Localisation absente
  Given un potager sans ville ni coordonnées
  When son owner ouvre les paramètres
  Then l'écran indique "localisation non renseignée" et propose de la renseigner
```

**Labels GitHub :** `us`, `sprint-cycle-vie-potager`, `frontend`, `backend`

**ID :** US-085
**Titre :** Changer le rôle d'un membre et transférer la propriété d'un potager
**Épic :** ÉPIC 5 — Cycle de vie du potager

**Story :**
En tant que jardinier owner d'un potager partagé
Je veux changer le rôle d'un membre et pouvoir désigner un autre propriétaire
Afin de passer la main sur un jardin collectif, ou de corriger un rôle mal attribué, sans supprimer puis réinviter la personne

**Contexte fonctionnel :**
**US non prévue par `docs/CONCEPTION_CYCLE_DE_VIE_POTAGER.md`, ajoutée après confrontation au code
existant.** Le document (§5.5) pose la règle : *« l'owner unique ne peut pas quitter son potager tant
qu'il n'a pas désigné un autre owner »* — mais **aucun moyen de désigner un autre owner n'existe
aujourd'hui**. Le rôle est figé au moment de l'invitation (`role_propose` dans la table `invitations`,
US-048) ; `app/services/potagers.py` sait inviter, lister et retirer un membre, jamais changer son
rôle. Sans cette US, US-086 (quitter) enferme définitivement tout owner unique et le transfert prévu
au titre du RGPD (§5.5) est irréalisable.

Deux besoins distincts, une seule mécanique : la **correction de rôle** (`lecteur` ↔ `editor`) est une
action courante et réversible ; le **transfert de propriété** (`owner`) est une action rare et à sens
unique du point de vue de celui qui la déclenche — il perd son propre pouvoir de la défaire.

**Décision produit** : le modèle autorise **plusieurs owners** sur un potager (la table
`potager_membres` ne l'interdit pas). Le transfert consiste donc à promouvoir un membre `owner` ; se
rétrograder soi-même n'est possible que s'il reste au moins un autre owner — le potager n'est jamais
orphelin.

**Critères d'acceptance :**
- [ ] CA1 : Nouvel endpoint de modification du rôle d'un membre (`owner` uniquement), acceptant les
      trois rôles `owner`, `editor`, `lecteur`, avec les mêmes libellés et le même vocabulaire que
      l'invitation (US-048) et l'affichage des rôles existant
- [ ] CA2 : Un owner peut **promouvoir** un membre au rôle `owner` : le potager compte alors plusieurs
      propriétaires, tous disposant des mêmes droits
- [ ] CA3 : Un owner peut **se rétrograder** lui-même en `editor` ou `lecteur` **uniquement** s'il
      reste au moins un autre owner — sinon l'opération est refusée avec un message expliquant qu'il
      faut d'abord désigner un autre propriétaire
- [ ] CA4 : Le **dernier owner** d'un potager ne peut jamais être rétrogradé ni retiré, ni par
      lui-même ni par un autre : la garde est posée dans la couche services et s'applique aussi au
      retrait de membre existant (`retirer_membre`, US-048) — non-régression à vérifier
- [ ] CA5 : Un `editor` ou un `lecteur` ne peut modifier aucun rôle, y compris le sien (§5.5 du
      document de conception : *« un membre change son propre rôle : impossible par principe »*)
- [ ] CA6 : Le changement de rôle est **immédiat** : le `TenantContext` reconstruit à la requête
      suivante porte le nouveau rôle, côté API comme côté bot, sans reconnexion ni redémarrage
- [ ] CA7 : La promotion au rôle `owner` demande une confirmation explicite rappelant que le nouvel
      owner pourra archiver, supprimer le potager et gérer les membres
- [ ] CA8 : Le membre dont le rôle change et qui a un compte Telegram lié (US-045) en est informé par
      un message précisant son nouveau rôle et ce qu'il peut désormais faire
- [ ] CA9 : L'action est disponible depuis la gestion des membres de l'écran « Paramètres du potager »
      (US-082), à côté du retrait de membre déjà présent
- [ ] CA type (US avec impact visuel/UI) : Le sélecteur de rôle réutilise le composant existant
      (`RoleSelect`) et reste lisible à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : configuration (PWA) + couche services (rôles) + notification Telegram
- Migration BDD requise : non — la colonne `potager_membres.role` existe déjà et accepte déjà les trois valeurs
- Dépendances : US-047 (rôles et `require_role`), US-048 (membres et invitations), US-082 (écran d'accueil de l'action)
- Prépare : US-086 (quitter un potager suppose de pouvoir passer la main), et la future US RGPD de suppression de compte (transfert automatique au membre le plus ancien, §5.5)
- Zéro token Groq

**Notes techniques (pour Persona Developer) :**
- Composants impactés : `app/services/potagers.py` (changement de rôle + garde « dernier owner »), `main.py`, `frontend/src/components/GestionMembres.jsx`, `frontend/src/components/ui/RoleSelect.jsx`
- La garde « il reste au moins un owner » doit être une **fonction unique** appelée par le changement de rôle, le retrait de membre et le futur départ volontaire (US-086) — trois chemins, une seule règle
- Attention à la course : compter les owners et écrire dans la même transaction, sinon deux rétrogradations simultanées peuvent laisser un potager sans owner
- `Potager.proprietaire_id` (colonne du socle US-040) et `potager_membres.role` doivent rester cohérents : décider explicitement lequel fait foi et documenter le choix dans le code — la source de vérité des droits est `potager_membres.role` (c'est elle qu'interroge `require_role`)

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Promouvoir un membre propriétaire
  Given un potager partagé avec un owner et un membre "editor"
  When l'owner promeut ce membre au rôle "owner" et confirme
  Then le potager compte deux owners
  And le membre promu peut désormais gérer les membres et archiver le potager

Scénario: Passer la main puis se retirer du pouvoir
  Given un potager avec deux owners
  When l'un d'eux se rétrograde au rôle "editor"
  Then l'opération réussit et le potager conserve un owner

Scénario: Le dernier owner ne peut pas se rétrograder
  Given un potager avec un seul owner
  When celui-ci tente de se rétrograder en "editor"
  Then l'opération est refusée avec un message invitant à désigner d'abord un autre propriétaire

Scénario: Corriger un rôle mal attribué
  Given un membre invité par erreur en "lecteur"
  When l'owner le passe en "editor"
  Then ce membre peut enregistrer des événements dès sa requête suivante, sans se reconnecter

Scénario: Un editor ne peut pas changer de rôle
  Given un membre au rôle "editor"
  When il tente de se promouvoir owner via l'API
  Then la requête est refusée
```

**Labels GitHub :** `us`, `sprint-cycle-vie-potager`, `backend`, `frontend`

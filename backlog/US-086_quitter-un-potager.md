**ID :** US-086
**Titre :** Quitter un potager dont on est membre
**Épic :** ÉPIC 5 — Cycle de vie du potager

**Story :**
En tant que jardinier membre d'un potager qui n'est pas le mien
Je veux pouvoir m'en retirer moi-même
Afin de ne plus voir ce jardin dans mes écrans quand je cesse d'y participer, sans devoir demander à son propriétaire de me retirer

**Contexte fonctionnel :**
`docs/CONCEPTION_CYCLE_DE_VIE_POTAGER.md` §5.5 et §7.2 (numéro provisoire US-155). Aujourd'hui, la
sortie d'un potager est **asymétrique** : un owner peut retirer un membre (`retirer_membre`, US-048,
`DELETE /potagers/{id}/membres/{user_id}`), mais un membre ne dispose d'aucun moyen de partir de
lui-même. Le cas est concret pour les personas U3 (membre d'un jardin partagé associatif) et U4
(potagiste aidant un proche) — participations par nature temporaires.

Le départ ne supprime **rien** : les événements saisis par le membre restent attachés au potager,
qui appartient au collectif et non à celui qui l'a alimenté. Seul le lien d'appartenance disparaît.

**Critères d'acceptance :**
- [ ] CA1 : Nouvel endpoint `POST /potagers/{id}/quitter` : l'appelant se retire lui-même de
      `potager_membres`, sans aucune permission particulière autre que d'être membre du potager
- [ ] CA2 : Le départ est **refusé** si l'appelant est le dernier `owner` du potager, avec un message
      indiquant la marche à suivre : désigner d'abord un autre propriétaire (US-085), ou archiver puis
      supprimer le potager (US-083/US-084) — la garde « dernier owner » est celle d'US-085/CA4, réutilisée
- [ ] CA3 : Un owner **non unique** peut quitter le potager comme n'importe quel membre
- [ ] CA4 : Si le potager quitté était le potager actif de l'appelant, celui-ci est invalidé
      immédiatement — bascule vers un autre potager dont il est membre, ou aucun potager actif s'il
      n'en a plus (comportement déjà en place, US-046/CA5 et `retirer_membre`)
- [ ] CA5 : Les événements, parcelles et photos saisis par le partant restent intacts dans le potager :
      quitter n'efface aucune donnée métier
- [ ] CA6 : L'action est proposée dans la zone sensible de « Paramètres du potager » (US-082) pour tout
      membre non-owner, avec une confirmation rappelant qu'il faudra une nouvelle invitation pour revenir
- [ ] CA7 : Le ou les owners du potager ayant un compte Telegram lié (US-045) sont informés du départ
- [ ] CA8 : Après son départ, l'ancien membre n'a plus aucun accès en lecture ni en écriture au
      potager, immédiatement (dès la requête suivante, API comme bot)
- [ ] CA type (US avec impact visuel/UI) : La confirmation de départ est visuellement rattachée à la
      zone sensible d'US-082 et lisible à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : configuration (PWA) + couche services (appartenances) + notification Telegram
- Migration BDD requise : non
- Dépendances : US-085 (garde « dernier owner » et transfert de propriété), US-048 (`retirer_membre`, mécanisme d'invalidation du potager actif à réutiliser), US-082 (écran d'accueil), US-047 (rôles)
- Non exposé côté bot : action rare et engageante, réservée à la PWA (§4.2 du document de conception)
- Zéro token Groq

**Notes techniques (pour Persona Developer) :**
- Composants impactés : `app/services/potagers.py`, `main.py`, `frontend/src/views/ParametresPotager.jsx`
- Le départ volontaire et le retrait par un owner partagent la même logique de suppression d'appartenance et d'invalidation du potager actif : factoriser, ne pas dupliquer `retirer_membre`
- Vérifier le cas limite : un membre qui quitte son **dernier** potager retombe sur le parcours d'onboarding/adhésion sans écran d'erreur ni page blanche
- Prévoir le test d'isolation : après départ, toute requête de l'ancien membre scopée sur ce potager doit être refusée (cf. tests US-042/US-043)

**Estimation :** 2 points

**Scénario Gherkin :**
```gherkin
Scénario: Quitter un jardin partagé
  Given un jardinier membre "editor" du potager associatif "Jardin des Lilas"
  And il est aussi owner de son potager personnel
  When il quitte "Jardin des Lilas" et confirme
  Then il n'est plus membre de ce potager
  And ses événements passés y restent visibles pour les autres membres
  And son potager actif est son potager personnel

Scénario: Le dernier owner ne peut pas quitter
  Given un jardinier seul owner de son potager
  When il tente de le quitter
  Then l'opération est refusée avec un message proposant de désigner un autre propriétaire ou d'archiver le potager

Scénario: Quitter son potager actif et son dernier potager
  Given un jardinier membre d'un seul potager dont il n'est pas owner
  When il le quitte
  Then il n'a plus de potager actif
  And il est dirigé vers le parcours de création ou d'adhésion à un potager

Scénario: Accès coupé immédiatement
  Given un membre qui vient de quitter un potager
  When il envoie un message au bot ou consulte la PWA
  Then aucune donnée de ce potager ne lui est accessible
```

**Labels GitHub :** `us`, `sprint-cycle-vie-potager`, `backend`, `frontend`

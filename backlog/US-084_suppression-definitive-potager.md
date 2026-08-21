**ID :** US-084
**Titre :** Supprimer définitivement un potager avec délai de grâce
**Épic :** ÉPIC 5 — Cycle de vie du potager

**Story :**
En tant que jardinier owner d'un potager archivé dont je n'ai plus l'usage
Je veux le supprimer définitivement, en sachant exactement ce que je perds et en gardant un droit au remords
Afin de nettoyer mon compte et d'exercer mon droit à l'effacement, sans risque de perte accidentelle

**Contexte fonctionnel :**
`docs/CONCEPTION_CYCLE_DE_VIE_POTAGER.md` §5.1, §5.4 et §7.2 (numéro provisoire US-154). Dernier état
du cycle de vie : `actif` → `archivé` → `supprimé`.

Deux garde-fous structurent cette US : **le passage obligé par l'archivage** (on ne supprime jamais un
potager en cours d'usage) et **le délai de grâce de 30 jours** (la suppression est d'abord logique,
la purge physique vient après). Entre les deux, l'owner peut annuler.

La suppression touche des données potentiellement partagées : dans un jardin collectif, les événements
saisis par d'autres membres disparaissent aussi. D'où l'exigence de dénombrement explicite et de
notification. L'articulation avec la suppression de **compte** (RGPD, US non encore rédigée sous la
numérotation réelle — `US-132` du plan initial) est traitée en §5.5 du document de conception :
transfert automatique au membre le plus ancien, suppression du potager si plus aucun membre.

**Critères d'acceptance :**
- [ ] CA1 : Nouvel endpoint `DELETE /potagers/{id}`, réservé au rôle `owner`, **refusé** si le potager
      n'est pas à l'état `archive` — un potager actif doit d'abord être archivé (US-083)
- [ ] CA2 : L'appel positionne `etat = 'supprime'` et `supprime_le = now()` : **aucune donnée n'est
      détruite à cet instant** (soft-delete)
- [ ] CA3 : Avant confirmation, l'écran affiche le décompte réel de ce qui sera perdu : nombre
      d'événements, de parcelles, de photos et de membres concernés — chiffres calculés, jamais approximés
- [ ] CA4 : La confirmation exige la **re-saisie du mot de passe** du compte web (US-044) ; trois échecs
      consécutifs abandonnent l'opération
- [ ] CA5 : Dès la suppression logique, le potager disparaît pour **tous** les membres (y compris avec
      `etat=tous`, cf. US-080/CA7) ; le potager actif de chaque membre concerné est invalidé selon le
      même mécanisme qu'US-083/CA5
- [ ] CA6 : Pendant le délai de grâce, l'owner peut **restaurer** le potager depuis un point d'accès
      dédié : il repasse à l'état `archive` (jamais directement `actif`), `supprime_le` remis à `NULL`
- [ ] CA7 : Une purge physique supprime définitivement le potager et toutes ses données rattachées
      (événements, parcelles, invitations, appartenances, photos) **30 jours** après `supprime_le`,
      dans l'ordre des dépendances de clés étrangères, en journalisant le volume supprimé
- [ ] CA8 : La purge est **idempotente et rejouable** : la relancer ne provoque ni erreur ni suppression
      d'un potager encore dans son délai de grâce
- [ ] CA9 : Les autres membres ayant un compte Telegram lié (US-045) sont notifiés de la suppression
      programmée, avec le nom du potager, son auteur et la date effective de purge
- [ ] CA10 : Un `editor` ou un `lecteur` ne peut jamais déclencher cette action — ni depuis l'UI (action
      absente), ni depuis l'API (refus explicite)
- [ ] CA type (US avec impact visuel/UI) : L'écran de confirmation est visuellement distinct des actions
      réversibles (zone sensible d'US-082) et lisible à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : configuration (PWA) + tâche de fond (purge) + notification Telegram
- Migration BDD requise : non (colonnes posées par US-080) — vérifier que les clés étrangères des tables métier permettent une suppression ordonnée sans orphelins
- Dépendances : US-080 (états), US-083 (archivage préalable obligatoire), US-082 (écran d'accueil), US-044 (mot de passe), US-047 (`require_role`)
- Lien RGPD : à raccorder à la future US de suppression de compte (§5.5 et §8.6 du document de conception) — les deux parcours doivent aboutir au même code de purge, pas à deux implémentations
- Zéro token Groq

**Notes techniques (pour Persona Developer) :**
- Composants impactés : `app/services/potagers.py` (suppression logique, restauration, purge), `main.py` (`DELETE /potagers/{id}`, restauration), `frontend/src/views/ParametresPotager.jsx`, mécanisme de tâche planifiée
- La purge doit s'exécuter **hors requête HTTP** : tâche planifiée ou commande d'administration dans `tools/`, déclenchable manuellement pour les tests — choix technique laissé au Developer, mais le code de purge doit être une fonction de service unique, appelée par le planificateur comme par la commande
- Compatibilité RLS (US-043) : la purge itère potager par potager en posant le contexte adéquat, elle ne contourne pas l'isolation
- Journaliser chaque purge (potager_id, volumes supprimés, date) : c'est la seule trace restante après effacement

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Supprimer un potager archivé
  Given un potager archivé contenant 214 événements, 6 parcelles et 12 photos
  And l'utilisateur en est owner
  When il demande la suppression définitive
  Then l'écran lui indique précisément les 214 événements, 6 parcelles et 12 photos concernés
  When il re-saisit son mot de passe et confirme
  Then le potager passe à l'état supprimé avec sa date
  And il disparaît de toutes les listes, pour tous les membres

Scénario: Suppression refusée sur un potager actif
  Given un potager à l'état actif
  When son owner tente de le supprimer
  Then l'opération est refusée avec un message invitant à l'archiver d'abord

Scénario: Droit au remords
  Given un potager supprimé il y a 5 jours
  When son owner le restaure
  Then le potager repasse à l'état archivé et redevient consultable en lecture seule

Scénario: Purge après le délai de grâce
  Given un potager supprimé il y a 31 jours
  When la purge s'exécute
  Then le potager et toutes ses données rattachées sont physiquement supprimés
  And le volume supprimé est journalisé
  When la purge est relancée
  Then aucune erreur n'est levée

Scénario: Un editor ne peut pas supprimer
  Given un membre au rôle "editor" d'un potager archivé
  When il appelle DELETE /potagers/{id}
  Then la requête est refusée
```

**Labels GitHub :** `us`, `sprint-cycle-vie-potager`, `backend`, `frontend`, `bdd`

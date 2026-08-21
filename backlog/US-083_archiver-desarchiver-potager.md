**ID :** US-083
**Titre :** Archiver et désarchiver un potager
**Épic :** ÉPIC 5 — Cycle de vie du potager

**Story :**
En tant que jardinier owner d'un potager que je ne cultive plus
Je veux l'archiver sans rien effacer
Afin qu'il cesse d'encombrer mes écrans et mes saisies, tout en gardant l'historique consultable si j'en ai besoin plus tard

**Contexte fonctionnel :**
`docs/CONCEPTION_CYCLE_DE_VIE_POTAGER.md` §5.1, §5.4 et §7.2 (numéro provisoire US-153). L'archivage
est le **passage obligé** avant toute suppression définitive (US-084) : il donne un filet de sécurité
et évite les suppressions impulsives.

Sémantique retenue : un potager archivé est en **lecture seule**. Ses données restent intactes et
consultables, mais plus aucun événement ne peut y être enregistré, ni depuis la PWA ni depuis le bot.
Il disparaît des sélecteurs par défaut (filtrage posé par US-080/CA4) et ne peut plus être le potager
actif de personne.

Cas typique : U5, l'utilisateur en migration (§3.1) — il déménage, archive l'ancien jardin, crée le
nouveau (US-081). Cas à ne **pas** confondre : le changement de saison, qui ne justifie jamais un
archivage (le potager est un lieu, pas une campagne — §2.3).

**Révision (retour terrain post-implémentation initiale de CA7) :** la première implémentation de
CA6/CA7 a introduit une notion de « potager consulté » distincte du potager actif, avec un mécanisme
de sélection différent selon que le potager cliqué est archivé ou non. Résultat : le bouton de
sélection en en-tête restait figé sur le potager actif pendant qu'on consultait un archivé (aucun
retour visuel sur ce qu'on regardait réellement), le menu déroulant perdait toute indication de
« potager courant » une fois sur un archivé, et le désarchivage déclenché depuis la bannière de
lecture seule laissait l'écran dans un état incohérent (modale non fermée, bannière non rafraîchie).
CA6 et CA7 sont réécrits ci-dessous pour lever cette ambiguïté : le geste de sélection doit rester
**unique et identique**, qu'un potager soit archivé ou non — seule la couleur/l'étiquette et la
conséquence (lecture seule vs écriture possible) diffèrent. Le potager actif côté serveur (celui que
cible le bot Telegram) reste en revanche **toujours** un potager non archivé — CA5 et CA8 ne changent
pas : archiver invalide le potager actif des membres concernés, et le désarchivage ne le restaure pas
automatiquement. Seul l'**affichage courant côté PWA** peut pointer vers un potager archivé.

**Critères d'acceptance :**
- [ ] CA1 : Nouveaux endpoints `POST /potagers/{id}/archiver` et `POST /potagers/{id}/desarchiver`,
      réservés au rôle `owner` (double contrôle service `require_role` + dépendance API)
- [ ] CA2 : L'archivage positionne `etat = 'archive'` et `archive_le = now()` ; le désarchivage
      repasse à `etat = 'actif'` et remet `archive_le` à `NULL`
- [ ] CA3 : Depuis « Paramètres du potager » (US-082), l'archivage demande une **double confirmation**
      expliquant la conséquence : « Ce potager passera en lecture seule. Personne ne pourra plus y
      enregistrer d'événement. Tu pourras le désarchiver plus tard. »
- [ ] CA4 : Toute tentative d'écriture sur un potager archivé est refusée dans la **couche services**
      (une seule garde, pas une vérification par endpoint) avec un message explicite, côté API comme
      côté bot — la lecture reste autorisée
- [ ] CA5 : Pour **chaque** membre dont ce potager était le potager actif, celui-ci est invalidé au
      moment de l'archivage : bascule automatique vers un autre potager actif dont il est membre, ou
      `NULL` s'il n'en a aucun (il retombe alors sur l'onboarding, comportement US-046/CA5 déjà en place)
- [ ] CA6 (révisé) : `PotagerMenu` et la vue « Tous mes potagers » masquent les potagers archivés par
      défaut et proposent une bascule « Voir les potagers archivés ». Un clic sur un potager archivé
      **bascule immédiatement l'affichage de la PWA dessus** — même geste, même immédiateté qu'un clic
      sur un potager non archivé — mais **sans** en faire le potager actif côté serveur : le potager
      actif du compte (celui que cible le bot Telegram, CA5/CA8) reste inchangé. Le bouton de
      sélection en en-tête reflète alors le potager réellement affiché, pas le potager actif serveur :
      son nom et sa couleur (variante « archivé ») changent en conséquence. Dans le menu déroulant, le
      potager actuellement affiché — qu'il soit actif ou archivé — porte l'indicateur de sélection
      courante ; le badge d'état « archivé » reste un badge indépendant, affiché en plus sur les
      potagers archivés listés
- [ ] CA7 (révisé) : Un potager archivé reste consultable en lecture (journal, statistiques, plan,
      pépinière, stocks) via la bascule d'affichage décrite en CA6, avec un bandeau permanent
      « Potager archivé — lecture seule » donnant un accès direct à « Paramètres du potager » (pour un
      éventuel désarchivage, CA8) sans avoir à revenir au menu. Le désarchivage déclenché depuis ce
      contexte de consultation referme la modale Paramètres et répercute immédiatement le nouvel état
      sur tout l'écran (bandeau, bouton de sélection, menu déroulant) sans action manuelle
      supplémentaire de l'utilisateur (pas de rechargement resté à mi-chemin, pas de bandeau obsolète)
- [ ] CA8 : Le désarchivage est possible à tout moment tant que le potager n'a pas été supprimé
      (US-084) et rend immédiatement l'écriture possible ; il ne rebascule **pas** le potager actif de
      qui que ce soit sans action explicite (cohérent avec US-046 : aucune bascule silencieuse)
- [ ] CA9 : Les autres membres du potager ayant un compte Telegram lié (US-045) reçoivent un message
      informatif à l'archivage et au désarchivage, précisant qui a effectué l'action et le nom du potager
- [ ] CA type (US avec impact visuel/UI) : Badge d'état, bandeau de lecture seule, bouton de sélection
      en variante « archivé » et bascule « voir les archivés » sont cohérents avec le design system
      (US-052) à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : configuration (PWA) + enregistrement (garde d'écriture, bot et API) + notification Telegram
- Migration BDD requise : non (colonnes posées par US-080)
- Dépendances : US-080 (états et filtrage), US-082 (écran d'accueil de l'action), US-047 (`require_role`), US-045 (comptes Telegram liés, pour CA9)
- Prépare : US-084 (la suppression n'est possible que depuis l'état archivé)
- Zéro token Groq
- **Arbitrage tranché ici** (point ouvert §8.7 du document de conception) : oui, les membres sont notifiés — un jardin partagé qui passe en lecture seule sans prévenir est un incident de collaboration, pas une commodité

**Notes techniques (pour Persona Developer) :**
- Composants impactés : `app/services/potagers.py` (archiver/désarchiver), `app/services/potager_actif.py` (invalidation en masse), garde d'écriture dans la couche services, `main.py`, `bot.py` (message de refus en écriture), `frontend/src/views/ParametresPotager.jsx`, `PotagerMenu.jsx`, `PotagerSelector.jsx`
- La garde « potager archivé = lecture seule » doit être posée **au même endroit** que la garde de rôle (US-047), pour ne pas multiplier les points de contrôle
- L'invalidation du potager actif réutilise exactement le mécanisme déjà implémenté au retrait de membre (`retirer_membre`, US-048) — ne pas en écrire une seconde version
- Les notifications Telegram passent par le mécanisme d'envoi sortant existant ; l'absence de compte lié ne doit jamais faire échouer l'archivage
- **Potager affiché vs potager actif serveur (CA6/CA7)** : la PWA distingue déjà le potager actif
  serveur (celui du compte, ciblé par le bot) de l'affichage courant côté client. Sélectionner un
  potager non archivé fait aujourd'hui les deux à la fois (active + affiche, via un rechargement
  complet, cf. `activer()` dans `PotagerContext.jsx`) ; sélectionner un archivé ne doit changer que
  l'affichage, jamais appeler l'activation serveur (ce qui casserait CA5/CA8 et enverrait le bot écrire
  sur un potager verrouillé). Le bouton de sélection et le menu déroulant doivent lire l'un OU l'autre
  état selon ce qui est réellement affiché, pas systématiquement le potager actif serveur.
- **Rafraîchissement après désarchivage depuis la consultation (CA7)** : tous les points d'entrée
  existants qui changent l'état global du potager (`activer`, `creerPotager` quand `activer:true`,
  `accepterInvitation`) évitent la classe de bug « état obsolète dans les composants déjà montés » via
  un `window.location.reload()` complet plutôt qu'une synchronisation manuelle multi-composants
  (bandeau + bouton + menu). Le désarchivage déclenché depuis le bandeau de lecture seule doit suivre
  la **même convention** plutôt que tenter de fermer/rafraîchir chaque morceau d'UI individuellement —
  c'est la cause directe de la régression « on reste sur cette modale ».

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Archiver un potager après un déménagement
  Given un jardinier owner de "Ancien jardin", qui est son potager actif
  And il est aussi membre de "Nouveau jardin"
  When il archive "Ancien jardin" et confirme deux fois
  Then "Ancien jardin" passe à l'état archivé avec sa date d'archivage
  And son potager actif bascule sur "Nouveau jardin"
  And "Ancien jardin" n'apparaît plus dans le sélecteur par défaut

Scénario: Écriture refusée sur un potager archivé
  Given un potager archivé
  When un membre tente d'y enregistrer un semis depuis le bot ou la PWA
  Then l'enregistrement est refusé avec un message expliquant que le potager est archivé
  And la consultation de son historique reste possible

Scénario: Consultation d'un potager archivé (CA6/CA7 révisés)
  Given un jardinier dont le potager actif est "Nouveau jardin"
  And il ouvre la liste des potagers archivés et clique sur "Ancien jardin"
  Then l'affichage de la PWA bascule immédiatement sur "Ancien jardin" (journal, plan, stats, pépinière, stocks)
  And le bouton de sélection en en-tête affiche "Ancien jardin" dans sa couleur "archivé"
  And le potager actif côté serveur reste "Nouveau jardin" (le bot continue d'y écrire)
  And un bandeau permanent "Potager archivé — lecture seule" est visible, avec un accès à Paramètres

Scénario: Désarchivage depuis la consultation en lecture seule
  Given un jardinier consultant "Ancien jardin", potager archivé, bandeau de lecture seule visible
  When il ouvre Paramètres depuis le bandeau et désarchive "Ancien jardin"
  Then la modale Paramètres se ferme
  And le bandeau de lecture seule disparaît immédiatement
  And le bouton de sélection et le menu déroulant reflètent le nouvel état sans action manuelle supplémentaire

Scénario: Archivage du dernier potager
  Given un jardinier owner d'un seul potager, qui est son potager actif
  When il l'archive
  Then il n'a plus de potager actif
  And il est dirigé vers le parcours de création ou d'adhésion à un potager

Scénario: Notification des membres
  Given un potager partagé avec 2 autres membres ayant lié leur compte Telegram
  When l'owner archive le potager
  Then chacun reçoit un message indiquant le nom du potager, l'action et son auteur

Scénario: Désarchivage
  Given un potager archivé depuis 3 mois
  When son owner le désarchive
  Then il repasse à l'état actif, l'écriture redevient possible
  And le potager actif des membres n'est pas modifié automatiquement
```

**Labels GitHub :** `us`, `sprint-cycle-vie-potager`, `backend`, `frontend`, `bot`

**ID :** US-195
**Titre :** Ouvrir un écran depuis un autre en emportant son contexte — parcelle, culture, lot, date
**Épic :** ÉPIC 9 — Socle commun Plan, Cultures, Pépinière *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux qu'un lien d'un écran m'amène directement sur ce qu'il désigne — la bonne parcelle, le bon lot, le journal du bon jour
Afin de passer du Plan à la Pépinière ou au Journal sans chercher à nouveau ce que je regardais

**Contexte fonctionnel :**
Les wireframes relient les trois écrans par des liens qui portent un contexte (plan des épics § 3) : « Fiche parcelle → » ouvre l'onglet Parcelles **sur cette parcelle**, la carte d'une pépinière ouvre la Pépinière **sur cet emplacement**, « Journal du jour » ouvre le Journal **filtré sur la date**, un scan d'étiquette ouvre **ce lot**.

La coquille actuelle (US-053) ne sait changer que de vue : `App.jsx` tient un état `view` et `setView(id)`, sans paramètre ni routeur. Une vue ne peut donc rien recevoir de celle qui l'ouvre.

Cette US ajoute ce mécanisme, **sans introduire de routeur** : une vue peut en ouvrir une autre avec une **intention** (un petit objet de contexte), que la vue d'arrivée applique une fois. La même intention peut arriver par l'adresse de la page, pour les liens partagés et les étiquettes (US-221).

⚖️ Les **fiches** (culture, calendrier, lot) ne sont pas des navigations : ce sont des panneaux ouverts par-dessus l'écran. Les fermer rend l'écran dans son état exact — règle déjà posée par US-183 / CA3, généralisée ici.

**Critères d'acceptance :**

*L'intention entre deux écrans*
- [ ] CA1 : La coquille expose `aller(vue, intention)`. La vue d'arrivée reçoit l'intention, l'applique **une fois** puis la consomme : revenir plus tard sur cette vue par la navigation normale ne la réapplique pas
- [ ] CA2 : Intentions reconnues au terme des épics 9 à 12 — et elles seules :

  | Vue | Clés | Effet |
  |---|---|---|
  | `plan` (Parcelles) | `parcelle` | sélectionne la parcelle et l'amène à l'écran |
  | `plan-vue` | `parcelle` | fait défiler jusqu'à sa carte |
  | `cultures` | `culture` | ouvre la fiche de la culture |
  | `pepiniere` | `onglet`, `emplacement`, `lot` | ouvre l'onglet, filtre l'emplacement, ouvre la fiche du lot |
  | `journal` | `date`, `culture` | pose le filtre de date, et de culture s'il est donné |

  Une clé inconnue est ignorée ; une vue sans intention se comporte exactement comme aujourd'hui
- [ ] CA3 : Une intention qui désigne une chose absente — parcelle supprimée, lot inconnu, culture hors référentiel — ouvre la vue normalement avec un message court (« Cette parcelle n'existe plus »), jamais une erreur ni un écran vide
- [ ] CA4 : Le focus clavier est porté sur l'élément désigné (parcelle sélectionnée, fiche ouverte) et son arrivée est annoncée aux lecteurs d'écran

*L'intention par l'adresse*
- [ ] CA5 : Une adresse de la forme `/?vue=pepiniere&lot=128` est lue **une fois** au démarrage, validée contre la liste du CA2, appliquée, puis **retirée de la barre d'adresse** : recharger la page ne la rejoue pas
- [ ] CA6 : Une intention reçue par l'adresse **survit à la connexion** : un jardinier déconnecté qui ouvre le lien se connecte, puis arrive sur ce qu'il désignait
- [ ] CA7 : Une intention par l'adresse peut nommer un potager. Si l'utilisateur en est membre et que ce n'est pas son potager actif, la bascule est faite **et dite** (même mécanisme que le sélecteur de potager, US-054 / US-088) ; s'il n'en est pas membre, l'intention est abandonnée avec un message, sans rien révéler du potager

*Les panneaux*
- [ ] CA8 : Ouvrir puis fermer une fiche (culture, calendrier, lot) rend l'écran dans son état exact : onglet, recherche, tri, filtre, sélection, position de défilement. Deux fiches peuvent s'empiler (fiche culture puis fiche calendrier) ; Échap ferme la plus haute seulement

*Hors périmètre, dit explicitement*
- [ ] CA9 : Aucun routeur n'est introduit et le bouton Retour du navigateur garde son comportement actuel ; c'est noté comme dette dans `ANALYSE_REFONTE_UI_WEB_2026.md`

*Définition de terminé*
- [ ] CA10 : La lecture, la validation et la consommation d'une intention vivent dans une lib (`frontend/src/lib/intentions.js`) couverte par `npm test` : clés reconnues, valeurs invalides, clé inconnue, intention par l'adresse, retrait de l'adresse, conservation à travers la connexion
- [ ] CA11 : Aucune fiche du corpus n'est concernée (navigation d'interface) ; la note d'architecture de la coquille (`ANALYSE_REFONTE_UI_WEB_2026.md`) décrit le mécanisme en une section

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA, coquille)
- Migration BDD requise : **non**
- Dépendances : US-053 (coquille à deux niveaux, livrée), US-054 et US-088 (potager actif, livrées)
- Consommateurs : US-201 (sorties de la Vue plan), US-207 (fiche culture), US-215 et US-216 (Pépinière), US-221 (étiquettes)
- Impact tokens : zéro
- Point de vigilance : l'intention est un **contexte de lecture**, jamais une commande. Elle ne déclenche aucune écriture, même par l'adresse (règle d'US-221 : « le scan ne fait que remplacer la navigation »)
- Point de vigilance : l'intention par l'adresse ne porte que des identifiants courts (numéro de lot, identifiant de parcelle) ; le jeton d'une étiquette (US-221) est résolu côté serveur, jamais interprété par le front
- Point de vigilance : le mécanisme de l'adresse doit cohabiter avec les deux entrées existantes — `/reinitialiser-mot-de-passe?token=…` (US-057) et le fragment de retour OAuth (US-090) — sans les intercepter

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: De la Vue plan à la fiche parcelle
  Given la Vue plan affiche la carte "planche-ombre"
  When j'appuie sur "Fiche parcelle →" de cette carte
  Then l'onglet Parcelles s'ouvre avec "planche-ombre" sélectionnée
  And le focus est posé sur sa fiche

Scénario: Journal du jour
  Given la date de référence est le 19 septembre
  When j'ouvre le Journal depuis "Journal du jour"
  Then le Journal est filtré sur le 19 septembre

Scénario: Lien partagé vers un lot, déconnecté
  Given je ne suis pas connecté
  When j'ouvre l'adresse "/?vue=pepiniere&lot=128"
  And je me connecte
  Then la Pépinière s'ouvre sur la fiche du lot 128
  And l'adresse ne porte plus "lot=128"

Scénario: Parcelle supprimée entre-temps
  Given une intention désigne une parcelle supprimée
  When l'onglet Parcelles s'ouvre
  Then un message indique que cette parcelle n'existe plus
  And la première parcelle de la liste est sélectionnée

Scénario: Fermer une fiche rend l'écran intact
  Given l'écran Cultures est trié par confiance et filtré sur "tom"
  When j'ouvre puis je ferme la fiche de la tomate
  Then le tri, le filtre et la position de défilement sont inchangés
```

**Labels GitHub :** `us`, `frontend`, `pwa`, `navigation`

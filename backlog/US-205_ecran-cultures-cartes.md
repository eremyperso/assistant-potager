**ID :** US-205
**Titre :** Afficher l'écran Cultures — une carte par culture, au potager ou dans tout le référentiel
**Épic :** ÉPIC 11 — Cultures : tout savoir d'une culture *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux un écran qui me montre chacune de mes cultures — et toutes celles que l'application connaît — avec son calendrier dans ma zone, où elle en est chez moi et ce qu'il est bon de faire maintenant
Afin de décider quoi semer ou planter cette semaine sans passer d'une fiche à l'autre

**Contexte fonctionnel :**
Le menu principal porte une entrée « Cultures » (« Mes cultures — Fiches, variétés et calendrier cultural de la saison ») qui n'ouvre qu'un écran d'attente depuis US-053. Le wireframe v1 le dessine : une **grille de cartes**, deux onglets, une recherche, un tri par confiance, et la suggestion de la semaine en pointillé. Chaque carte ouvre la **fiche culture** (US-207).

Cet écran se distingue de Stocks par ce qu'il ne montre pas : aucune quantité. Stocks dit *combien* ; Cultures dit *quoi* et *quand* (plan des épics § 2).

Les données viennent d'une seule lecture (US-204). L'écran n'y ajoute aucune règle : il met en forme.

⚖️ **Conception faite (RT9).** Le wireframe v1 § 2 fixe la structure. La **maquette haute
fidélité est gelée depuis le 25/09/2026** : `Cultures - Ecran et fiche.html` (projet Claude
Design *potager 2026*), à déposer dans `maquette front/haute-fidelite/`. Elle rejoue les cinq
états de l'écran à trois largeurs. C'est elle qui fait foi sur le rendu et sur le responsive,
et qui a fait naître les CA18 à CA23 ci-dessous.

**Critères d'acceptance :**

*Structure*
- [ ] CA1 : L'entrée « Cultures » ouvre cet écran à la place de son écran d'attente. En tête : le titre **Cultures** et les onglets **« Au potager · N »** (par défaut) et **« Toutes · M »** ; en dessous, la barre d'outils portant la date de référence (RT3), la recherche, le tri et les filtres, dans la forme qu'impose la largeur (CA18)
- [ ] CA2 : Tri **« confiance ↓ »** par défaut — les étoiles d'abord, puis la fenêtre (*maintenant*, *bientôt*, *plus tard*, *aucune*), puis le nom — et, au choix, « A → Z » ou « par famille ». Une culture sans étoile n'est jamais placée au-dessus d'une culture étoilée
- [ ] CA3 : Filtres par **famille** (pastilles) et par **mois** (les cultures qui ont une fenêtre de semis ou de plantation ce mois-là, dans la zone du potager), disponibles dans les deux onglets
- [ ] CA4 : La recherche porte sur le nom de la culture et, dans « Au potager », sur ses variétés. Elle est commune aux deux onglets : dans « Au potager », si elle trouve des cultures absentes du potager, une ligne « N autres dans Toutes → » bascule d'onglet en gardant la recherche

*La carte*
- [ ] CA5 : Chaque carte porte : le nom ; « N variétés · famille » (famille seule pour une culture absente du potager) ; à droite, les **étoiles** du geste le mieux noté avec leur équivalent écrit, ou « pas de calendrier » ; la **frise** des douze mois de la zone, mois de la date de référence encadré (composant `MonthStrip` existant, **non modifié**) ; en pied, à gauche la **phase la plus avancée** (`PastillePhase`, US-194) et « · N parcelles », ou « en pépinière · N lots », ou « pas au potager » en pointillé ; à droite le **libellé de fenêtre** (« semer maintenant » en gras, « prochaine fenêtre : planter avril → mai »)
- [ ] CA6 : Une culture sans calendrier pour la zone affiche, à la place des étoiles, une puce pointillée **« pas de calendrier »**, sa frise reste dessinée mais **atténuée**, et un lien **« compléter »** déplie **dans la carte** un bloc d'aide qui nomme la culture et la zone et donne la phrase exacte à dire au compagnon (« Dis au compagnon : `/calendrier fenetre ail …` », même texte que la fiche calendrier). Ce lien et le bloc déplié n'ouvrent pas la fiche : l'appui y est arrêté
- [ ] CA7 : Les **suggestions de la semaine** (US-204 / CA6) figurent dans l'onglet « Au potager », à leur place dans le tri, en carte pointillée marquée « suggestion — pas au potager »
- [ ] CA8 : Une culture **hors référentiel** a sa carte, sans frise ni étoile, avec la mention « hors référentiel »
- [ ] CA9 : Un appui sur une carte ouvre la **fiche culture** (US-207) par-dessus l'écran ; la fermer rend l'écran dans son état exact — onglet, recherche, tri, filtres, défilement (US-195 / CA8)

*Mise en page et états*
- [ ] CA10 : Grille en **container queries** sur un conteneur dédié : une colonne sous 520 px de conteneur, deux de 520 à 900 px, trois au-delà. Aucun défilement horizontal à 375 px, et la largeur du contenu est plafonnée à **1320 px**, centrée : la grille ne passe jamais à quatre colonnes
- [ ] CA11 : La légende de la frise et la ligne « zone climatique et son origine » s'affichent **une fois pour l'écran**, jamais sur chaque carte, avec l'attribution de la source (US-176 / CA8, CA9)
- [ ] CA12 : **Cinq états**, tous rejoués par la maquette. *Nominal*. *Chargement* : six cartes squelettes dans la grille, jamais de tirets qui se remplissent. *Échec de lecture* : une carte portant « Les cultures n'ont pas pu être lues. Rien n'a été modifié. » et un bouton « Réessayer ». *Confiance indisponible* : bandeau ambre « Confiance indisponible — la météo du potager n'a pas pu être lue », les cartes gardant frise, présence et fenêtre sans aucune étoile ni valeur de repli dans le tri. *« Au potager » vide* : une carte « Rien au potager en ce moment », la raison datée, un lien « Voir les N cultures du référentiel → » qui bascule sur « Toutes », suivie de la grille des seules suggestions
- [ ] CA13 : Accessibilité : les onglets forment une liste d'onglets ; chaque carte est un bouton dont le nom accessible dit la culture, la phase, la confiance en toutes lettres et la fenêtre ; les filtres sont nommés ; la couleur ne porte jamais seule une information (RT4)

*Définition de terminé*
- [ ] CA14 : Le tri (les trois ordres, dont le regroupement par famille), les filtres, la recherche commune, le comptage des filtres actifs et l'assemblage du **libellé de fenêtre** à partir des valeurs brutes d'US-204 / CA5 vivent dans une lib sans React (`frontend/src/lib/cultures.js`) couverte par `npm test` (RT7). Le front n'y ajoute aucune règle métier
- [ ] CA15 : Une nouvelle fiche `data/connaissance/doc_app/cultures-et-fiche-culture.md` répond aux questions du jardinier — où voir tout ce que l'application sait d'une culture, que veulent dire les étoiles et la pastille, pourquoi une culture apparaît en pointillé, que faire d'une culture sans calendrier. Elle entre dans la table de relecture du `README.md` du corpus, et ses questions dans `tests/corpus/us099_questions_fonctionnement.csv`, qui reste à 100 % dans les trois premiers résultats (US-099 / CA9, CA11)
- [ ] CA16 : `ANALYSE_REFONTE_UI_WEB_2026.md` note que l'écran Cultures existe désormais, distinct de Stocks, et pourquoi
- [ ] CA17 : Le rendu correspond à la maquette gelée `Cultures - Ecran et fiche.html` **à 375 px, 768 px et 1180 px, en thème clair et en thème sombre** ; vérification chrome-devtools à 375 px et à 768 px, sur les cinq états de CA12

*Responsive et design system (amendement du 25/09)*
- [ ] CA18 : **Deux formes de barre d'outils**, pas une barre qui se replie au hasard.
  *Large* : ligne 1 = bouton de date « au 18 sept. 2026 », recherche extensible plafonnée à 340 px, sélecteur de tri, sélecteur de mois ; ligne 2 = pastilles de familles ; ligne 3 = légende dépliée.
  *Étroit* (375 px) : les onglets passent **pleine largeur** sous le titre ; une seule ligne = date compactée (« 18 sept. »), recherche extensible, bouton **Filtres** et bouton **Légende**, tous deux de 44 px. Tri, mois, familles et « Tout effacer » vivent dans le panneau *Filtres* ; la légende vit dans le panneau *Légende*. Les deux panneaux s'ouvrent l'un après l'autre, jamais ensemble
- [ ] CA19 : Le bouton **Filtres** porte le **nombre de filtres actifs** (famille, mois, tri autre que celui par défaut) et prend la teinte de marque dès qu'il y en a un ; le panneau offre **« Tout effacer »** qui les remet tous à leur valeur par défaut. Son nom accessible énonce ce compte
- [ ] CA20 : Le tri **« Par famille »** rend une suite de groupes titrés « FAMILLE · N », chacun portant sa propre grille ; les cultures hors référentiel forment le groupe « Hors référentiel ». Les deux autres tris rendent une grille unique
- [ ] CA21 : **Pastille « En pépinière »** — `PastillePhase` gagne une quatrième valeur pour la culture qui n'a aucune ligne en terre mais des lots en cours (US-204 / CA3), et une variante **compacte** pour la fiche culture. Elle se distingue des trois phases par un contour plutôt qu'une teinte pleine : la palette reste celle des phases (RT4). La culture absente du potager porte une pastille **pointillée** « pas au potager », ou « suggestion — pas au potager » à la teinte de marque quand c'en est une (CA7)
- [ ] CA22 : **Cibles d'appui de 44 px** à 375 px sur la date, la recherche, les deux boutons de panneau, les onglets, les pastilles de famille et les cartes (RT5). Aucun survol ne porte seul une information : l'effet de survol des cartes est décoratif
- [ ] CA23 : La **carte** garde une hauteur cohérente en grille : nom et sous-titre en tête, frise au milieu, pied (présence à gauche, fenêtre à droite) **poussé en bas**, pour que les pieds de deux cartes voisines s'alignent. À 375 px, présence et fenêtre passent à la ligne sans jamais tronquer ni la pastille ni le libellé

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA)
- Migration BDD requise : **non**
- Dépendances : **US-204** (lecture), **US-207** (fiche culture ouverte par la carte), **US-194** (pastille de phase)
- Impact tokens : zéro
- Impact design system : réutilise `MonthStrip`, `MonthStripLegend`, `Etoiles`, `PuceConfiance`, `PastillePhase`, `SearchField`, `Select`, `InfoBanner`, `Card`, `Btn`, `Badge` — tous livrés. **Deux évolutions du design system**, portées par cette US : (1) `PastillePhase` gagne la valeur « en pépinière » et une variante compacte (CA21) ; (2) un composant `CarteCulture` nouveau, plus son squelette. Rien d'autre n'est modifié : `MonthStrip` en particulier est repris **tel quel**
- Point de vigilance : `frontend/src/lib/phases.js` est le seul endroit où phase → libellé → teinte est écrit. La valeur « en pépinière » de CA21 s'y ajoute ; aucune teinte n'est écrite dans un composant
- Point de vigilance : pas de quantité sur la carte, même « pour aider » ; le lien vers les quantités, c'est Stocks
- Point de vigilance : la frise de la carte est la frise **conseillée** de la zone. La frise recalée d'une culture en place vit dans la fiche calendrier (US-183) — v2 : « conseillée dans l'une, recalée dans l'autre. C'est la raison d'être des deux écrans »
- Wireframe : `maquette front/wireframes/Wireframes - Plan Cultures Pepiniere.html`, § 2 et ses notes

**Estimation :** 8 points (hors conception — relevée de 5 à 8 le 25/09 : les deux formes de barre d'outils, les deux panneaux, les cinq états et la quatrième pastille de phase)

**Scénario Gherkin :**
```gherkin
Scénario: Ce qu'il est bon de faire remonte
  Given au 18 septembre, l'épinard a une fenêtre ouverte à trois étoiles et n'est pas au potager
  And la tomate est en récolte, sans geste possible avant février
  When j'ouvre l'écran Cultures
  Then la carte de l'épinard, en pointillé, apparaît avant celle de la tomate
  And elle porte "suggestion — pas au potager" et "semer maintenant"

Scénario: Filtrer le référentiel par mois
  Given l'onglet "Toutes" est ouvert
  When je choisis le mois de mars
  Then seules les cultures ayant une fenêtre de semis ou de plantation en mars sont affichées

Scénario: Recherche commune aux deux onglets
  Given l'onglet "Au potager" est ouvert et aucun poireau n'est au potager
  When je cherche "poireau"
  Then une ligne "1 autre dans Toutes →" est proposée
  When j'appuie dessus
  Then l'onglet "Toutes" s'ouvre avec la recherche "poireau"

Scénario: Culture sans calendrier
  Given l'ail n'a aucune fenêtre pour ma zone
  When j'ouvre l'écran Cultures
  Then la carte de l'ail affiche "pas de calendrier" et "compléter"
  And aucune étoile n'est affichée

Scénario: Retour à l'état exact
  Given l'écran est trié "A → Z" et filtré sur les Solanacées
  When j'ouvre puis je ferme la fiche de l'aubergine
  Then le tri et le filtre sont inchangés
```

**Labels GitHub :** `us`, `frontend`, `pwa`, `cultures`, `design-system`

---

## 🆕 Amendement du 25/09/2026 — maquette gelée « Cultures — écran et fiche »

Source : projet Claude Design *potager 2026*, `Cultures - Ecran et fiche.html` et les six
fichiers qu'il importe (`cultures-data.jsx`, `cultures-ecran.jsx`, `cultures-fiche.jsx`,
`fiche-calendrier.jsx`, `web-parts.jsx`, `web-tokens.jsx`). Maquette **gelée au sens de RT9**.

Ce qu'elle change ici : **rien au périmètre**, tout au **rendu et au responsive**.

| Ce que la maquette tranche | CA |
|---|---|
| Grille 1 / 2 / 3 colonnes à 520 et 900 px de conteneur, contenu plafonné à 1320 px | CA10 (confirmé, plafond ajouté) |
| Deux formes de barre d'outils, dont la forme étroite à panneaux *Filtres* et *Légende* | **CA18** |
| Compteur de filtres actifs et « Tout effacer » | **CA19** |
| Tri « Par famille » en groupes titrés | **CA20** |
| Quatrième pastille « En pépinière », pastilles pointillées « pas au potager » | **CA21** |
| Cibles de 44 px à 375 px | **CA22** (RT5) |
| Pied de carte aligné en bas de grille | **CA23** |
| Aide « compléter » dépliée dans la carte | CA6 (précisé) |
| Cinq états rejoués, thème sombre inclus | CA12, CA17 |

Ce qu'elle **ne** rouvre pas : l'absence de quantité sur la carte, la frise *conseillée*
(la recalée reste à la fiche calendrier), la distinction avec Stocks, la suggestion de la
semaine comme lecture et non comme recommandation.

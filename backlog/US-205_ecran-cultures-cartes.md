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

⚖️ **Conception avant implémentation (RT9).** Le wireframe v1 § 2 fixe la structure ; la maquette haute fidélité est gelée avant le code.

**Critères d'acceptance :**

*Structure*
- [ ] CA1 : L'entrée « Cultures » ouvre cet écran à la place de son écran d'attente. En tête : la date de référence (RT3), les onglets **« Au potager · N »** (par défaut) et **« Toutes · M »**, la recherche, le tri
- [ ] CA2 : Tri **« confiance ↓ »** par défaut — les étoiles d'abord, puis la fenêtre (*maintenant*, *bientôt*, *plus tard*, *aucune*), puis le nom — et, au choix, « A → Z » ou « par famille ». Une culture sans étoile n'est jamais placée au-dessus d'une culture étoilée
- [ ] CA3 : Filtres par **famille** (pastilles) et par **mois** (les cultures qui ont une fenêtre de semis ou de plantation ce mois-là, dans la zone du potager), disponibles dans les deux onglets
- [ ] CA4 : La recherche porte sur le nom de la culture et, dans « Au potager », sur ses variétés. Elle est commune aux deux onglets : dans « Au potager », si elle trouve des cultures absentes du potager, une ligne « N autres dans Toutes → » bascule d'onglet en gardant la recherche

*La carte*
- [ ] CA5 : Chaque carte porte : le nom ; « N variétés · famille » (famille seule pour une culture absente du potager) ; à droite, les **étoiles** du geste le mieux noté avec leur équivalent écrit, ou « pas de calendrier » ; la **frise** des douze mois de la zone, mois de la date de référence encadré (composant `MonthStrip` existant, **non modifié**) ; en pied, à gauche la **phase la plus avancée** (`PastillePhase`, US-194) et « · N parcelles », ou « en pépinière · N lots », ou « pas au potager » en pointillé ; à droite le **libellé de fenêtre** (« semer maintenant » en gras, « prochaine fenêtre : planter avril → mai »)
- [ ] CA6 : Une culture sans calendrier pour la zone affiche « pas de calendrier » et un lien « compléter » qui explique, sans rien estimer, la phrase à dire au compagnon (« /calendrier fenetre ail … », même texte que la fiche calendrier)
- [ ] CA7 : Les **suggestions de la semaine** (US-204 / CA6) figurent dans l'onglet « Au potager », à leur place dans le tri, en carte pointillée marquée « suggestion — pas au potager »
- [ ] CA8 : Une culture **hors référentiel** a sa carte, sans frise ni étoile, avec la mention « hors référentiel »
- [ ] CA9 : Un appui sur une carte ouvre la **fiche culture** (US-207) par-dessus l'écran ; la fermer rend l'écran dans son état exact — onglet, recherche, tri, filtres, défilement (US-195 / CA8)

*Mise en page et états*
- [ ] CA10 : Grille en container queries : une colonne sous 520 px de conteneur, deux jusqu'à 900 px, trois au-delà ; aucun défilement horizontal à 375 px
- [ ] CA11 : La légende de la frise et la ligne « zone climatique et son origine » s'affichent **une fois pour l'écran**, jamais sur chaque carte, avec l'attribution de la source (US-176 / CA8, CA9)
- [ ] CA12 : Chargement : squelette de cartes. Échec : message et relance. Confiance indisponible : les cartes gardent frise et présence, sans étoile, et un bandeau le dit. « Au potager » vide : un message, les suggestions et un lien vers « Toutes »
- [ ] CA13 : Accessibilité : les onglets forment une liste d'onglets ; chaque carte est un bouton dont le nom accessible dit la culture, la phase, la confiance en toutes lettres et la fenêtre ; les filtres sont nommés ; la couleur ne porte jamais seule une information (RT4)

*Définition de terminé*
- [ ] CA14 : Le tri, les filtres, la recherche commune et le libellé de fenêtre vivent dans une lib sans React (`frontend/src/lib/cultures.js`) couverte par `npm test`
- [ ] CA15 : Une nouvelle fiche `data/connaissance/doc_app/cultures-et-fiche-culture.md` répond aux questions du jardinier — où voir tout ce que l'application sait d'une culture, que veulent dire les étoiles et la pastille, pourquoi une culture apparaît en pointillé, que faire d'une culture sans calendrier. Elle entre dans la table de relecture du `README.md` du corpus, et ses questions dans `tests/corpus/us099_questions_fonctionnement.csv`, qui reste à 100 % dans les trois premiers résultats (US-099 / CA9, CA11)
- [ ] CA16 : `ANALYSE_REFONTE_UI_WEB_2026.md` note que l'écran Cultures existe désormais, distinct de Stocks, et pourquoi
- [ ] CA17 : Le rendu correspond à la maquette haute fidélité gelée à 375 px, 768 px et desktop ; vérification chrome-devtools à 375 px

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA)
- Migration BDD requise : **non**
- Dépendances : **US-204** (lecture), **US-207** (fiche culture ouverte par la carte), **US-194** (pastille de phase)
- Impact tokens : zéro
- Impact design system : réutilise `MonthStrip`, `MonthStripLegend`, `Etoiles`, `PuceConfiance`, `PastillePhase`, `SearchField`, `Select`, `Badge` ; un composant `CarteCulture` nouveau, en container query
- Point de vigilance : pas de quantité sur la carte, même « pour aider » ; le lien vers les quantités, c'est Stocks
- Point de vigilance : la frise de la carte est la frise **conseillée** de la zone. La frise recalée d'une culture en place vit dans la fiche calendrier (US-183) — v2 : « conseillée dans l'une, recalée dans l'autre. C'est la raison d'être des deux écrans »
- Wireframe : `maquette front/wireframes/Wireframes - Plan Cultures Pepiniere.html`, § 2 et ses notes

**Estimation :** 5 points (hors conception)

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

**Labels GitHub :** `us`, `frontend`, `pwa`, `cultures`

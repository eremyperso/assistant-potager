# Brief — Refonte de l'écran Stocks en écran transverse unique des cultures

Document de travail à emporter dans la conversation Claude Design (projet
`10f5afa7-58f8-4eb0-8dae-ca5834dfff59`, "potager 2026") pour retravailler la maquette
de l'écran Stocks. Rédigé le 2026-08-14, à éditer librement avant de le coller.

## Décision actée

**L'écran Stocks devient l'écran transverse unique pour retrouver le suivi de toutes
les cultures du potager**, tous états confondus (en place, en pépinière, en semis
pleine terre). Conséquence backlog :

- **US-071** (« Refondre l'écran Cultures — vue transverse par famille botanique »),
  rédigée mais non implémentée, **devient caduque en tant qu'écran séparé** : son
  ambition (regroupement par famille, calendrier, agrégation multi-parcelles) est
  absorbée par Stocks. À retirer du backlog ou à réécrire comme fusion dans US-062.
- **US-062** (« Refondre l'écran Stocks avec bascule tableau/cartes ») était cadrée
  comme une refonte *strictement visuelle*, données inchangées. Ce cadrage ne tient
  plus : il y a désormais un changement réel de structure de l'information, pas
  seulement d'habillage. US-062 doit être réécrite avant implémentation.

## Ce qui existe et doit être préservé (`frontend/src/views/Stocks.jsx`, code réel)

Fonctionnalités déjà livrées, aucune régression tolérée :

- Section **« Au potager »** : cultures en place avec badge d'origine (pépinière,
  pied acheté, semis pleine terre, non localisé), stock en pieds avec unité réelle,
  rendement cumulé dès qu'une récolte pesée existe (y compris cultures végétatives,
  US-036), pieds perdus.
- Ligne **semis pleine terre** distincte, avec filet anti-double-comptage : une
  culture déjà comptée « au potager » n'est jamais réaffichée en semis.
- Section **« En pépinière — prêt à replanter »** : lots en godet avec stock résiduel,
  taux de germination, détail des sorties (repiqués / plantés / vendus / perdus).
  **Absente des deux prototypes de maquette ci-dessous** — à ne pas perdre.
- Sélecteur de date de référence, filtre recherche par culture, bandeau de métriques
  (au potager / à replanter / perdus), observations agrégées par culture (US-039).

## Ce qui est réutilisable dans la maquette — prototype `ScreenStocks`

(`web-screens.jsx`, fonction `ScreenStocks`, non retouché récemment)

- Bascule **tableau (desktop) / cartes (mobile)** déjà dessinée (`wstock-table` /
  `wstock-cards`), colonnes Culture / Famille / Origine / Quantité / Récolté.
- Chips de filtre par **famille botanique** avec compteur par famille.
- Index alphabétique latéral (A→Z) pour sauter directement à une culture.
- Bandeau de stats en tête (unités au potager / à replanter / pertes).

## Ce qui est réutilisable dans la maquette — prototype `ScreenCultures`

(`web-screens.jsx`, fonction `ScreenCultures` — écran qu'US-071 devait porter)

- Regroupement par famille via `GroupHead` : nom de famille, nombre de cultures,
  total de pieds du groupe.
- Calendrier `MonthStrip` par fiche — **absent du prototype Stocks**, à intégrer.
- Sélecteur « Toutes les familles » + liste des familles réellement présentes.

**Décisions déjà arbitrées par US-071, à transporter telles quelles** (ne pas
rouvrir le débat) :
- La fiche culture reprend la tuile `CultureTile` du Plan (US-060) plutôt que la
  fiche du prototype (icône feuille générique, badges exposition/eau, lieu unique).
- Une culture doit lister **toutes ses parcelles d'origine**, jamais un lieu unique
  — le prototype `ScreenCultures` a un `c.lieu` singulier, c'est un défaut connu.
- La granularité d'une fiche est le couple **(culture, variété)** normalisé, jamais
  la culture seule. Deux variétés = deux fiches.
- Exposition / besoin en eau : **hors périmètre**, aucune donnée ni table
  provisoire n'existe pour ces deux attributs — ne pas les faire apparaître.
- Famille et calendrier cultural lisent les tables provisoires existantes
  (`frontend/src/lib/familles.js`, `calendrier.js`) ; une culture absente s'affiche
  en mode dégradé (frise neutre, tirets), jamais de valeur horticole inventée.

## Questions ouvertes à trancher (avec une recommandation)

1. **Calendrier en vue tableau** — le `MonthStrip` est pensé pour une carte, pas une
   ligne de tableau dense. *Recommandation : colonne calendrier compacte en
   desktop (barre réduite), pleine frise uniquement en mode carte mobile — à
   confirmer avec Claude Design selon ce qui reste lisible dans une ligne de
   tableau.*
2. **Niveau de groupement principal** — famille botanique en tête (comme
   `ScreenCultures`), avec l'état (au potager / en pépinière / semis pleine terre)
   porté par un badge sur chaque fiche ? Ou sections par état d'abord (comme
   aujourd'hui), avec la famille en sous-groupe ? *Recommandation : famille en
   groupement principal — c'est ce qui manque aujourd'hui et qui justifie la
   fusion avec US-071 ; l'état devient un badge, pas une section.*
3. **Coexistence avec l'index alphabétique** — s'il reste, il doit sauter à une
   famille ou à une fiche précise à travers les groupes. *Recommandation : le
   garder comme raccourci de navigation secondaire, pas comme structure
   principale de la liste.*

## Contraintes transverses à rappeler à Claude Design

- **Container queries, pas de breakpoints d'écran** pour tout composant réutilisable
  (règle non négociable de `CLAUDE.md`) : la bascule tableau/cartes doit réagir à
  la largeur du conteneur, pas à la largeur de la fenêtre.
- Tokens sémantiques de la nouvelle palette uniquement — plus aucun alias `--g-*`
  hérité de l'ancien thème parchemin/kaki (39 occurrences aujourd'hui dans
  `Stocks.jsx`, à faire disparaître).
- Aucun nouvel endpoint ni migration attendus a priori : `GET /stats` et
  `GET /godets` couvrent déjà les données nécessaires (comme `GET /plan` le
  faisait pour US-071) — à confirmer une fois la structure de l'écran arrêtée.

**ID :** US-073
**Titre :** Refondre l'écran Stocks en vue transverse unique des cultures, groupée par famille botanique

**Story :**
En tant que jardinier utilisant l'interface web
Je veux consulter en un seul écran toutes mes cultures — au potager, en pépinière et en semis pleine terre — groupées par famille botanique, avec un accès direct à l'historique détaillé des récoltes de chaque variété et un export de mes données
Afin de raisonner mon potager dans son ensemble sans naviguer entre plusieurs écrans, ni ressaisir mes chiffres ailleurs

**Contexte fonctionnel :**
Écran d'implémentation du chantier documenté dans `docs/BRIEF_REFONTE_STOCKS_TRANSVERSE.md` (2026-08-14), qui acte que **l'écran Stocks devient l'écran transverse unique pour retrouver le suivi de toutes les cultures du potager, tous états confondus**. Porte la maquette figée `ScreenStocks` (`Maquette figée/web-screens.jsx`, projet Claude Design "potager 2026", gel du 15/08/2026 — fichier faisant foi `Potager - Application Web - FIGE 2026-08-15.html`, seule source valable pour l'implémentation d'après `Maquette figée/LISEZ-MOI.md`).

Cette US a deux conséquences actées par le brief :
- **US-071** (« Refondre l'écran Cultures — vue transverse par famille botanique »), rédigée mais non implémentée, **devient caduque en tant qu'écran séparé** : son ambition (regroupement par famille, agrégation multi-parcelles) est absorbée ici. À retirer du backlog actif.
- **US-062** (« Refondre l'écran Stocks avec bascule tableau/cartes »), cadrée comme une refonte strictement visuelle à données inchangées, **devient caduque** : il y a désormais un changement réel de structure de l'information (fusion de 3 sections en une liste groupée par famille), pas seulement d'habillage. Cette US-073 la remplace intégralement.

Dépend de **US-072** (nouvelle agrégation par variété avec parcelles), qui fournit la donnée consommée ici.

**Trois points laissés ouverts par le brief sont tranchés par la maquette figée elle-même**, qui n'existait pas encore au moment de sa rédaction :
1. *Calendrier en vue tableau* — la maquette gelée **n'affiche aucun calendrier** (`MonthStrip`) sur cet écran, contrairement au prototype `ScreenCultures` antérieur. Non repris.
2. *Niveau de groupement principal* — la **famille botanique est le regroupement principal**, confirmé par l'infobulle de la maquette (« La famille botanique est le regroupement principal de cet écran : c'est elle qui commande les rotations de culture »). L'état (au potager / en pépinière / semis pleine terre) devient un badge par ligne, pas une section.
3. *Coexistence avec l'index alphabétique* — le rail alphabétique est un **raccourci secondaire** combiné à la recherche et au filtre famille, jamais une structure de liste à lui seul.

**Critères d'acceptance :**

*Filtres et export*
- [ ] CA1 : La barre de filtres comporte un champ de recherche (nom de culture ou de variété), le sélecteur de date de référence (US-030/031), un filtre par origine (Pépinière / Pied acheté / Semis pleine terre / Non localisé), et deux actions d'export alignées à droite : « Exporter en CSV » et « Exporter en JSON »
- [ ] CA2 : L'export CSV et l'export JSON téléchargent exactement les lignes **actuellement visibles** après application de la recherche, du filtre famille, du filtre lettre et du filtre origine — jamais l'intégralité du potager si un filtre est actif. Les colonnes exportées reprennent celles du tableau (culture, variété, famille, état, origine, parcelles, unités, en place, vendu si applicable, perdu, récolté)
- [ ] CA3 : Les deux exports sont générés entièrement côté navigateur à partir des données déjà chargées pour l'affichage — aucun nouvel endpoint, aucun envoi de données au serveur

*Bandeau de métriques*
- [ ] CA4 : Un bandeau de 4 métriques est affiché en tête : unités au potager (état `potager` uniquement, avec l'infobulle « Pieds, gousses ou godets réellement en place à la date de référence »), godets à replanter (état `pep`), kilogrammes récoltés sur la saison, unités perdues (avec l'infobulle « Pieds ou godets déclarés perdus : non germés, arrachés, malades »)

*Groupement par famille et filtres secondaires*
- [ ] CA5 : Les cultures sont regroupées **par famille botanique** en sections repliables (composant `GroupHead`/`useGroups`, repris tel quel de l'écran Pépinière, US-061), via `familleDe()` (`frontend/src/lib/familles.js`) — même dette que Plan et Pépinière, non rouverte ici, cf. US-067
- [ ] CA6 : Des chips de filtre par famille (« Toutes » + une par famille réellement présente dans les données, avec compteur) permettent de restreindre la liste à une seule famille
- [ ] CA7 : Un rail alphabétique secondaire (A→Z + « Tout ») filtre en plus par initiale du nom de culture ; les lettres sans culture dans le filtre famille courant sont désactivées, pas masquées
- [ ] CA8 : Chaque en-tête de groupe famille porte le nom de la famille, le nombre de cultures/variétés du groupe, le nombre de parcelles distinctes concernées, et les totaux du groupe pour les colonnes unités / en place / vendu / perdu / récolté

*Bascule tableau / cartes*
- [ ] CA9 : Sur grand écran, la liste s'affiche en tableau (une ligne par couple culture + variété) ; sur petit écran, en cartes empilées. Les deux présentations affichent exactement les mêmes informations
- [ ] CA10 : La bascule est pilotée par `container-type: inline-size` + `@container`, jamais par un breakpoint d'écran (règle non négociable de `CLAUDE.md`)
- [ ] CA11 : Chaque ligne/carte affiche : nom de la culture (serif) + variété (italique, « variété non précisée » si absente), badge d'état (Au potager / En pépinière / Semis pleine terre), badge d'origine, la ou les parcelles d'origine (ou rien pour l'état pépinière, cf. US-072 CA4), unités totales avec leur unité réelle, quantité en place, quantité vendue **uniquement si le champ est renseigné** (US-072 CA6 — jamais un `0` inventé pour une culture au potager ou en semis), quantité perdue, poids récolté

*Synthèse des récoltes par variété*
- [ ] CA12 : Chaque ligne/carte affiche un lien « N récolte(s) » lorsqu'au moins une récolte pesée existe pour cette variété (nombre de récoltes pesées > 0), ou la mention « non pesé » sinon (sans lien)
- [ ] CA13 : Cliquer sur ce lien ouvre une modale listant chronologiquement chaque récolte pesée de cette variété précise (date + kg), avec le total cumulé en pied de modale — données issues de `GET /historique` filtré par culture et `action=recolte`, la variété étant isolée côté client
- [ ] CA14 : Si le nombre d'événements de récolte dépasse la pagination retournée par `/historique`, la modale le signale explicitement plutôt que d'afficher un total silencieusement tronqué

*Non-régression*
- [ ] CA15 : Aucune perte fonctionnelle par rapport à l'écran actuel : filet anti-double-comptage (porté par US-072 CA7), rendement cumulé affiché dès qu'une récolte pesée existe y compris pour les cultures végétatives (US-036), observations agrégées par culture (US-039, remontées sur chaque ligne/carte)
- [ ] CA16 : L'écran ne contient plus aucun alias de couleur `--g-*` ni classe `bg-g-*` / `text-g-*` / `border-g-*` — uniquement les tokens sémantiques de la nouvelle palette (39 occurrences aujourd'hui dans `Stocks.jsx`, à faire disparaître)
- [ ] CA type (US avec impact visuel/UI) : Le rendu de l'écran correspond visuellement à la maquette figée à 375px/768px/1180px/1440px, dans les deux thèmes clair et sombre

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non
- Dépendances : US-052 (design system), US-053 (coquille de navigation), US-059 (composants transverses migrés), US-061 (`GroupHead`/`useGroups` réutilisés), US-030/031 (date de référence), **US-072** (nouvelle agrégation par variété, bloquante)
- Rend caduques : US-062 (refonte visuelle de Stocks, remplacée intégralement), US-071 (écran Cultures transverse, absorbé ici)
- Écarts assumés à documenter dans `docs/ANALYSE_REFONTE_UI_WEB_2026.md` une fois l'écran livré, sur le modèle du §5.10 : absence de calendrier `MonthStrip` (conforme à la maquette gelée), champ « vendu » restreint à l'état pépinière (US-072 CA6)

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Scénario: Fusion des trois états dans un seul groupement par famille
  Given des tomates au potager, des courges en pépinière et des oignons en semis pleine terre, toutes de la famille Solanacée à Alliacée
  When l'utilisateur consulte l'écran "Stocks"
  Then chaque groupe de famille affiche des cultures dans n'importe lequel des trois états
  And l'état de chaque ligne est visible via son badge, pas via une section séparée

Scénario: Export CSV respecte le filtre actif
  Given l'utilisateur a filtré sur la famille "Solanacée" et la recherche "tom"
  When il clique sur "Exporter en CSV"
  Then le fichier téléchargé ne contient que les lignes de tomates actuellement visibles

Scénario: Lien de récoltes absent pour une variété jamais pesée
  Given une aubergine plantée sans aucune récolte pesée enregistrée
  When l'utilisateur consulte l'écran "Stocks"
  Then la ligne affiche "non pesé" sans lien cliquable

Scénario: Détail des récoltes d'une variété précise
  Given des tomates Cœur de bœuf avec 6 récoltes pesées et des tomates Cerise avec 3 récoltes pesées
  When l'utilisateur clique sur "6 récoltes" pour les Cœur de bœuf
  Then la modale n'affiche que les 6 récoltes des Cœur de bœuf, pas celles des Cerise

Scénario: Bascule tableau vers cartes
  Given l'utilisateur consulte l'écran "Stocks" sur un écran de 1440px et voit un tableau
  When il redimensionne la fenêtre jusqu'à 375px
  Then le tableau laisse place à des cartes empilées affichant exactement les mêmes informations

Scénario: Champ vendu jamais inventé
  Given des tomates plantées au potager, sans aucun événement de vente possible à ce stade
  When l'utilisateur consulte la ligne correspondante
  Then aucune valeur "vendu" n'est affichée, ni "0" ni tiret trompeur — le champ est simplement absent de la ligne
```

**Labels GitHub :** `us`, `sprint-refonte-ui-2026`, `frontend`, `stocks`

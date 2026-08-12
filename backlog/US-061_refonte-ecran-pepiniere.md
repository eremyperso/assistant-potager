**ID :** US-061
**Titre :** Refondre l'écran Pépinière avec les trois stades d'avancement

**Story :**
En tant que jardinier utilisant l'interface web
Je veux voir, pour chaque lot de ma pépinière, où en sont mes plants entre la germination, le godet et la mise en terre
Afin de savoir d'un coup d'œil ce qu'il me reste à repiquer et à planter, sans avoir à ouvrir le détail de chaque lot

**Contexte fonctionnel :**
Troisième US du Lot B de la refonte de l'interface web (voir `docs/ANALYSE_REFONTE_UI_WEB_2026.md` §3 et §7.3). L'écran Pépinière (`views/Pepiniere.jsx`) est le plus riche du lot : cartes de culture avec compteur circulaire de plants disponibles, badges de taux de germination et de ventes, phrase de synthèse, bandeaux de récapitulatif, et un **panneau de détail portant la timeline de traçabilité complète d'un lot** (semis → mise en godet → plantation / vente / perte pépinière) construite par US-020 et US-029. Il porte 80 références aux alias de couleurs `--g-*`, le plus gros volume du lot (§7.4, point 1).

La maquette introduit, par lot, **trois barres d'avancement — Germination, Godet, Terre**. Toute la partie données nécessaire à ces barres — suivi par lot de semis, calcul correct des graines encore en germination, état de germination à trois valeurs — est portée par **US-065**, dont cette US dépend. Le présent périmètre est l'habillage : mise en forme des barres, badge de phase, et migration de l'écran vers le design system.

**Règle d'affichage des trois barres**

Par lot, à la date de référence affichée, à partir des quantités exposées par US-065 :

| Symbole | Définition |
|---|---|
| `S` | graines semées du lot |
| `R` | graines encore en germination |
| `P` | plants obtenus |
| `T` | plants mis en terre |
| `G` | plants encore en godet |
| `D` | dénominateur : `P` si la germination est close, sinon `S` |

- **Germination %** = `P / S` — proportion de graines ayant effectivement levé
- **Godet %** = `G / D`
- **Terre %** = `T / D`

Déroulé de référence, lot de 10 graines de tomate :

| Événement | Germination | Godet | Terre |
|---|---|---|---|
| Semis de 10 graines | 0 % | 0 % | 0 % |
| Mise en godet de 5 plants sur 5 graines | 50 % | 50 % | 0 % |
| Mise en godet de 2 plants sur les 5 graines restantes | 70 % | 100 % | 0 % |
| Plantation de 5 godets | 70 % | 29 % (2/7) | 71 % (5/7) |

**Critères d'acceptance :**
- [ ] CA1 : Chaque carte affiche les trois stades **Germination / Godet / Terre** sous forme de barres de progression reprenant le composant du design system, chacune accompagnée de son pourcentage **et de la quantité réelle correspondante** — un pourcentage peut reposer sur un dénominateur provisoire, une quantité de plants ne ment jamais
- [ ] CA2 : Les pourcentages respectent la règle ci-dessus, dénominateur variable compris, et le déroulé de référence en quatre événements donne exactement les valeurs du tableau
- [ ] CA3 : Un badge de phase surmonte les barres et **nomme le stade plutôt que de répéter un chiffre** : `🌱 Germination X %` tant que la germination est en cours, `✓ Réussite X %` une fois close, et une mention explicite d'information manquante lorsque l'état est indéterminé (nombre de graines d'origine non déclaré sur au moins une mise en godet, cf. US-065). Le même pourcentage n'a pas le même sens selon la phase : « 70 %, ça peut encore monter » et « 70 %, c'est définitif » doivent être distinguables
- [ ] CA4 : Une carte par **lot de semis**, identifiée par sa date de semis, de sorte que deux semis échelonnés d'une même variété soient lisibles séparément ; les mises en godet sans semis rattaché forment une carte distincte explicitement libellée comme telle
- [ ] CA5 : Les cas où un pourcentage n'a pas de sens sont rendus explicitement plutôt que par un zéro trompeur : la barre Germination affiche « — » quand aucun semis n'est rattaché au lot, et une incohérence de saisie signalée par US-065 (plus de plants que de graines semées) est rendue visible sur la carte au lieu d'être bornée silencieusement à 100 %
- [ ] CA6 : Les plants sortis de la pépinière autrement que par plantation — vendus, perdus en godet — ne sont comptés dans aucune des trois barres ; le reliquat est mentionné en clair sous les barres (par exemple « 2 vendus · 1 perdu »), de sorte que l'écart à 100 % soit toujours explicable
- [ ] CA7 : Les trois barres remplacent la phrase de synthèse actuelle de la carte (« X plants en godet · Y plantés · Z en attente »), qui porte exactement la même information sous forme rédigée — changement de forme, pas perte d'information
- [ ] CA8 : Les cartes reprennent l'habillage de carte du design system, avec la barre d'accent latérale reflétant le stock résiduel (vert au-dessus de 40 % du lot, ambre de 15 à 40 %, rouge en dessous) et le compteur circulaire de plants disponibles, conformément à la maquette
- [ ] CA9 : Sur grand écran, les cartes se répartissent en plusieurs colonnes ; la bascule est pilotée par la largeur du conteneur (`container-type: inline-size` + `@container`) et non par un breakpoint d'écran (règle non négociable de `CLAUDE.md`)
- [ ] CA10 : Le panneau de détail s'ouvre dans la fenêtre modale du design system, **ciblé sur le lot de la carte ouverte**, et conserve intégralement sa timeline de traçabilité : semis avec son identifiant, son nombre de graines et sa parcelle d'origine, lots de godets numérotés, taux de germination, plantations avec la parcelle de destination et les identifiants des lots consommés, ventes, pertes en pépinière, ainsi que les mentions explicites « semis non lié » et « pas encore planté » quand le maillon est absent
- [ ] CA11 : Aucune régression fonctionnelle sur la liste — sont conservés : la distinction entre lots en attente de mise en place et lots entièrement plantés, le badge de pieds vendus, le code couleur du taux de germination (vert à partir de 80 %, ambre de 50 à 79 %, rouge en dessous), et les trois métriques de tête (godets disponibles, réussite moyenne, nombre de cultures)
- [ ] CA12 : Les deux bandeaux de récapitulatif — « cultures entièrement plantées » et « pieds vendus cette saison » — sont portés par le composant de bandeau d'information du design system, en conservant leur contenu et leur condition d'affichage
- [ ] CA13 : Le sélecteur de date de référence et le filtre par culture (portant à la fois sur la culture et sur la variété) sont conservés et utilisent les composants migrés par US-059, y compris sur l'écran vide « aucun godet en pépinière » ; les trois barres reflètent l'état à la date de référence choisie
- [ ] CA14 : L'écran ne contient plus aucun alias de couleur `--g-*` ni classe `bg-g-*` / `text-g-*` / `border-g-*` — uniquement les tokens sémantiques de la nouvelle palette
- [ ] CA type (US avec impact visuel/UI) : Le rendu de l'écran, panneau de détail compris, correspond visuellement à la maquette de référence à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non
- Dépendances : **US-065 (bloquante)** — suivi par lot, calcul des graines en germination et état de phase ; US-052 (design system), US-053 (coquille de navigation), US-059 (composants transverses migrés) ; s'appuie sur la traçabilité d'US-020 et US-029, qui ne doit pas être altérée

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Déroulé de référence des trois stades
  Given un lot de 10 graines de tomate semé en pépinière
  When le jardinier met en godet 5 plants issus de 5 de ces graines
  Then la carte du lot affiche Germination 50%, Godet 50% et Terre 0%
  When il met en godet 2 plants supplémentaires issus des 5 graines restantes
  Then la carte affiche Germination 70%, Godet 100% et Terre 0%
  When il plante 5 de ces godets
  Then la carte affiche Germination 70%, Godet 29% et Terre 71%

Scénario: Le badge nomme la phase, pas seulement le chiffre
  Given un lot dont il reste des graines en germination
  Then le badge affiche "Germination 50%"
  When toutes les graines semées ont été soldées par une mise en godet
  Then le badge affiche "Réussite 70%", signifiant que la valeur est désormais définitive

Scénario: Information manquante affichée comme telle
  Given un lot dont une mise en godet n'a pas déclaré son nombre de graines d'origine
  When le jardinier consulte la carte de ce lot
  Then le badge indique une information manquante, et non une germination en cours

Scénario: Deux semis échelonnés lisibles séparément
  Given un semis de tomate en mars et un autre de la même variété en avril
  When le jardinier consulte l'écran "Pépinière"
  Then deux cartes distinctes s'affichent, identifiées par leur date de semis
  And chaque carte affiche l'avancement de son propre lot, permettant de voir lequel est prêt à être repiqué

Scénario: Germination sans référence connue
  Given un lot de 12 plants en godet sans semis rattaché
  When le jardinier consulte l'écran "Pépinière"
  Then la barre Germination affiche "—" au lieu de 0%, et les barres Godet et Terre se calculent sur les 12 plants

Scénario: Ventes et pertes explicables
  Given un lot de 7 plants dont 3 plantés, 2 vendus et 1 perdu en godet
  When le jardinier consulte la carte de ce lot
  Then les barres affichent Germination 70%, Godet 14% et Terre 43%
  And la mention "2 vendus · 1 perdu" figure sous les barres pour expliquer l'écart à 100%

Scénario: Trois stades à une date de référence passée
  Given un lot dont les plants ont été mis en terre en juin
  When le jardinier fixe la date de référence au mois de mai
  Then les trois barres reflètent l'état du lot en mai, avec Terre à 0%

Scénario: Non-régression de la timeline de traçabilité
  Given un lot issu d'un semis, réparti en deux lots de godets, dont une partie a été plantée et une autre vendue
  When l'utilisateur ouvre le détail de ce lot
  Then la timeline affiche successivement le semis, les deux lots de godets numérotés, le taux de germination, la plantation avec sa parcelle de destination et les identifiants des lots consommés, puis la vente

Scénario: Mise en page multi-colonnes sur grand écran
  Given l'utilisateur consulte l'écran "Pépinière" avec six lots en godet
  When il affiche l'application sur un écran de 1440px
  Then les cartes se répartissent sur plusieurs colonnes au lieu de s'étirer sur toute la largeur
```

**Labels GitHub :** `us`, `sprint-refonte-ui-2026`, `frontend`, `pepiniere`

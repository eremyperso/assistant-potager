**ID :** US-061
**Titre :** Refondre l'écran Pépinière

**Story :**
En tant que jardinier utilisant l'interface web
Je veux suivre mes lots en godet et leur parcours complet dans une présentation claire et adaptée à la taille de mon écran
Afin de savoir combien de plants sont encore disponibles à replanter et d'où vient chacun d'eux, sans me perdre dans une longue liste

**Contexte fonctionnel :**
Troisième US du Lot B de la refonte de l'interface web (voir `docs/ANALYSE_REFONTE_UI_WEB_2026.md` §7.3). L'écran Pépinière (`views/Pepiniere.jsx`) est le plus riche du lot : cartes de culture avec compteur circulaire de plants disponibles, badges de taux de germination et de ventes, phrase de synthèse, bandeaux de récapitulatif, et surtout un **panneau de détail portant la timeline de traçabilité complète d'un lot** (semis → mise en godet → plantation / vente / perte pépinière) construite par US-020 et US-029. Il porte 80 références aux alias de couleurs `--g-*`, le plus gros volume du lot (§7.4, point 1).

Refonte **strictement visuelle** : la chaîne de traçabilité, les calculs de taux et de stock résiduel, et les appels serveur restent inchangés. C'est le volume de surface à réhabiller — et le risque de régression sur la timeline — qui justifie une estimation plus élevée que les autres écrans du lot.

**Critères d'acceptance :**
- [ ] CA1 : Les cartes de culture reprennent l'habillage de carte du design system, avec la barre d'accent latérale reflétant le stock résiduel (vert au-dessus de 40 % du lot, ambre de 15 à 40 %, rouge en dessous) et le compteur circulaire de plants disponibles, conformément à la maquette
- [ ] CA2 : Sur grand écran, les cartes de culture se répartissent en plusieurs colonnes ; la bascule est pilotée par la largeur du conteneur (`container-type: inline-size` + `@container`) et non par un breakpoint d'écran (règle non négociable de `CLAUDE.md`)
- [ ] CA3 : Le panneau de détail d'un lot s'ouvre dans la fenêtre modale du design system, et conserve **intégralement** sa timeline de traçabilité : étape de semis avec son identifiant, son nombre de graines et sa parcelle d'origine, lots de godets numérotés avec leur position quand il y en a plusieurs, taux de germination, plantations avec la parcelle de destination et les identifiants des lots consommés, ventes, pertes en pépinière, ainsi que les mentions explicites « semis non lié » et « pas encore planté » quand le maillon est absent
- [ ] CA4 : Aucune régression fonctionnelle sur la liste — sont conservés à l'identique : la distinction entre lots en attente de mise en place et cultures entièrement plantées, le statut « en germination » avec son décompte de graines non encore repiquées, le badge de taux de germination et son code couleur (vert à partir de 80 %, ambre de 50 à 79 %, rouge en dessous), le badge de pieds vendus, la phrase de synthèse de chaque carte, et les trois métriques de tête (godets disponibles, réussite moyenne, nombre de cultures)
- [ ] CA5 : Les deux bandeaux de récapitulatif — « cultures entièrement plantées » et « pieds vendus cette saison » — sont portés par le composant de bandeau d'information du design system, en conservant leur contenu et leur condition d'affichage
- [ ] CA6 : Le sélecteur de date de référence et le filtre par culture (portant à la fois sur la culture et sur la variété) sont conservés et utilisent les composants migrés par US-059, y compris sur l'écran vide « aucun godet en pépinière »
- [ ] CA7 : L'écran ne contient plus aucun alias de couleur `--g-*` ni classe `bg-g-*` / `text-g-*` / `border-g-*` — uniquement les tokens sémantiques de la nouvelle palette
- [ ] CA type (US avec impact visuel/UI) : Le rendu de l'écran, panneau de détail compris, correspond visuellement à la maquette de référence à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non
- Dépendances : US-052 (design system), US-053 (coquille de navigation), US-059 (composants transverses migrés) ; s'appuie sur la traçabilité livrée par US-020 et US-029, qui ne doit pas être altérée

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Scénario: Non-régression de la timeline de traçabilité
  Given un lot de tomates issu d'un semis, réparti en deux lots de godets, dont une partie a été plantée et une autre vendue
  When l'utilisateur ouvre le détail de cette culture
  Then la timeline affiche successivement le semis, les deux lots de godets numérotés, le taux de germination, la plantation avec sa parcelle de destination et les identifiants des lots consommés, puis la vente

Scénario: Maillon manquant explicite
  Given un lot de godets sans semis rattaché et jamais planté
  When l'utilisateur ouvre le détail de cette culture
  Then la timeline affiche "Semis non lié" et "Pas encore planté" au lieu de masquer ces étapes

Scénario: Culture en germination
  Given des graines semées mais pas encore repiquées en godet
  When l'utilisateur consulte l'écran "Pépinière"
  Then la carte de cette culture affiche le statut "En germination" et le décompte de graines, sans compteur circulaire de plants disponibles

Scénario: Mise en page multi-colonnes sur grand écran
  Given l'utilisateur consulte l'écran "Pépinière" avec six cultures en godet
  When il affiche l'application sur un écran de 1440px
  Then les cartes de culture se répartissent sur plusieurs colonnes au lieu de s'étirer sur toute la largeur
```

**Labels GitHub :** `us`, `sprint-refonte-ui-2026`, `frontend`, `pepiniere`

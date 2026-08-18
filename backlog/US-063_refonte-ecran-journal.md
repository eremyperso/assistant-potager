**ID :** US-063
**Titre :** Refondre l'écran Journal

**Story :**
En tant que jardinier utilisant l'interface web
Je veux relire l'ensemble de mes interventions dans un journal lisible et facile à filtrer
Afin de retrouver rapidement quand j'ai semé, arrosé ou récolté telle culture, sur téléphone comme sur ordinateur

**Contexte fonctionnel :**
Cinquième US du Lot B de la refonte de l'interface web (voir `docs/ANALYSE_REFONTE_UI_WEB_2026.md` §7.3). L'écran affiche la liste paginée des événements enregistrés, avec des pastilles de filtre par type d'action, un filtre par culture, un sélecteur de période et le sélecteur de date de référence. Il porte 54 références aux alias de couleurs `--g-*` (§7.4, point 1), dont un cas particulier : la couleur des pastilles d'arrosage est écrite en dur en hexadécimal, avec une seconde table de correspondance dédiée au thème sombre — un contournement que les tokens sémantiques rendent inutile.

Cette US achève par ailleurs le renommage « Historique → Journal » (§5.4) : le libellé affiché a été traité par US-053, il reste à aligner le nom du fichier de vue sur la clé de navigation `journal` déjà en place.

**Mise à jour du 2026-08-18 :** la maquette Claude Design a été actualisée (projet `10f5afa7-58f8-4eb0-8dae-ca5834dfff59`, fichier `Potager - Application Web - Proposition.html`, imports `web-tokens.jsx`/`web-parts.jsx`/`web-screens.jsx`/`web-shell.jsx`/`web-account.jsx`) et redessine aussi les filtres de l'écran Journal, pas seulement leur habillage — décision produit : on suit cette maquette plutôt que de conserver les filtres actuels à l'identique. Le périmètre est revu en conséquence (voir CA1/CA3/CA4/CA8 ci-dessous) : le filtre d'action passe de pastilles à un menu à icônes reprenant les 9 catégories de la maquette, la période à deux dates devient une date unique, la date de référence est retirée de cet écran, et un export CSV/JSON est ajouté (à la manière de l'écran Stocks — export **client**, sans nouvel appel serveur).

Cette US n'est donc plus « strictement visuelle » au sens initial de sa première rédaction. Elle reste sans migration BDD et sans nouvel endpoint, mais elle **étend `GET /historique`** sur deux points, tous deux rétrocompatibles : le paramètre `action` accepte plusieurs types séparés par des virgules (les catégories de la maquette en recouvrent plusieurs — « Entretien » à elle seule en couvre six, et filtrer côté client fausserait la pagination calculée côté serveur), et la réponse expose `nb_plants_godets` (une mise en godet ne renseigne pas `quantite`, son compte ne vit que dans ce champ).

Ni la maquette gelée du 15/08/2026 ni la nouvelle proposition ne collent exactement au modèle de données réel — la maquette affiche une heure et une phrase pré-composée par événement, dont ni l'une ni l'autre n'existent en base. Comme pour l'écran Stocks (US-073), la maquette fournit le langage visuel et les tokens ; l'implémentation reconstruit la phrase à partir des champs réels et se passe de l'heure plutôt que d'inventer une valeur.

**Critères d'acceptance :**
- [ ] CA1 : L'écran affiche une **liste**, pas une grille de vignettes : les événements de la page courante sont groupés par jour, chaque journée formant une carte du design system précédée d'un bandeau de section portant sa date, et chaque événement occupant une ligne à l'intérieur de cette carte, séparée de la suivante par un filet — structure de la maquette. Chaque ligne porte un badge d'icône teinté selon le type d'action, la **phrase de l'événement** et la parcelle. La phrase est reconstruite à partir des champs réels selon le patron « <action> de <quantité> <unité> de <culture> <variété> » (ex. « Récolte de 1,2 kg de courgette Jaune », « Plantation de 3 pieds d'aubergine »), chaque segment absent de la donnée étant omis plutôt que comblé — « Arrosage » tout court est une phrase valide. Aucune heure n'est affichée : contrairement à la maquette qui l'illustre avec des données fictives, l'heure n'existe nulle part dans le modèle réel (`parse_date()` tronque à `%Y-%m-%d`, et `GET /historique` re-tronque via `str(e.date)[:10]`)
- [ ] CA2 : Les badges de type d'action utilisent exclusivement les tokens sémantiques de la nouvelle palette (`Badge` du design system, tints `brand`/`amber`/`blue`/`red`/`violet`), y compris l'arrosage : plus aucune couleur hexadécimale écrite en dur, et plus de table de correspondance séparée pour le thème sombre — la bascule clair/sombre est assurée par les tokens eux-mêmes
- [ ] CA3 : Les filtres suivent la nouvelle maquette : le filtre par type d'action devient une liste déroulante à sélection unique (Toutes les actions, Récolte, Semis, Plantation, Arrosage, Perte, Godet — les mêmes 6 types qu'aujourd'hui ; seule la forme du contrôle change, pas les valeurs envoyées au serveur) ; le sélecteur de période à deux dates est remplacé par un contrôle à une date unique (envoyée au serveur à la fois comme `from` et `to`) ; le sélecteur de date de référence est retiré de cet écran — le Journal n'est plus affecté par la date de référence globale, qui continue de s'appliquer normalement sur Tableau de bord/Stocks/Pépinière ; le filtre par culture est conservé à l'identique, y compris la recherche sur la variété
- [ ] CA4 : La pagination est conservée : 20 événements par page, numéro de page courante, nombre total de pages et compteur total d'événements, avec les boutons précédent/suivant désactivés aux extrémités ; le regroupement par jour (CA1) est un simple habillage visuel des 20 événements déjà chargés, pas un rechargement ni un agrégat supplémentaire ; tout changement de filtre transmis au serveur (action, date) ramène à la première page — le filtre culture reste, comme aujourd'hui, un filtrage local de la page affichée qui ne recharge rien et ne change donc pas la pagination
- [ ] CA5 : La ligne d'événement occupe la largeur disponible sans laisser un grand vide à droite : au-delà d'une carte large, la parcelle rejoint la phrase sur la même ligne et se cale à droite (la place qu'occupe l'heure dans la maquette) ; sur une carte étroite elle repasse sous la phrase. L'adaptation est pilotée par la largeur du conteneur (`container-type: inline-size` + `@container`, ici le conteneur `card` déjà porté par le composant `Card`) et non par un breakpoint d'écran (règle non négociable de `CLAUDE.md`)
- [ ] CA6 : Le fichier de vue est renommé pour porter le nom « Journal », en cohérence avec la clé de navigation `journal` et le libellé déjà affichés depuis US-053 — dernier reliquat du renommage décrit au §5.4
- [ ] CA7 : L'écran ne contient plus aucun alias de couleur `--g-*` ni classe `bg-g-*` / `text-g-*` / `border-g-*` — uniquement les tokens sémantiques de la nouvelle palette
- [ ] CA8 : Un export CSV et un export JSON sont proposés, comme sur l'écran Stocks, limités aux événements de la page actuellement affichée après filtres — jamais l'intégralité de l'historique, qui reste paginé côté serveur
- [ ] CA type (US avec impact visuel/UI) : Le rendu de l'écran correspond visuellement à la maquette de référence à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non
- Dépendances : US-052 (design system), US-053 (coquille de navigation et renommage du libellé), US-059 (composants transverses migrés)

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Phrase reconstruite à partir des champs de l'événement
  Given un événement de récolte de 1,2 kg de courgette variété Jaune
  When l'utilisateur ouvre l'écran "Journal"
  Then la ligne affiche "Récolte de 1,2 kg de courgette Jaune"

Scénario: Phrase d'un événement sans quantité ni culture
  Given un événement d'arrosage sans quantité et sans culture
  When l'utilisateur ouvre l'écran "Journal"
  Then la ligne affiche "Arrosage", sans segment vide ni tiret de remplissage

Scénario: Badge d'arrosage lisible dans les deux thèmes
  Given le journal contient des événements d'arrosage
  When l'utilisateur bascule du thème clair vers le thème sombre
  Then le badge "arrosage" reste lisible et cohérent avec les autres badges, sans couleur codée en dur

Scénario: Non-régression de la pagination
  Given le journal contient 45 événements
  When l'utilisateur ouvre l'écran "Journal"
  Then 20 événements sont affichés, la pagination indique "Page 1 / 3" et le total de 45 événements

Scénario: Retour à la première page au changement de filtre
  Given l'utilisateur consulte la page 3 du journal
  When il sélectionne "Récolte" dans la liste déroulante des types d'action
  Then la liste revient à la première page des récoltes

Scénario: Filtrage par une date précise
  Given l'utilisateur consulte le journal sans filtre de date
  When il choisit une date précise dans le sélecteur de date
  Then seuls les événements de ce jour sont affichés et la liste revient à la première page
```

**Labels GitHub :** `us`, `sprint-refonte-ui-2026`, `frontend`, `journal`

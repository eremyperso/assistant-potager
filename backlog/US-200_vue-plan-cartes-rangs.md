**ID :** US-200
**Titre :** Afficher la Vue plan — une carte par parcelle, un trait par rang
**Épic :** ÉPIC 10 — Plan : l'occupation en rangs *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux voir toutes mes planches d'un coup, chacune avec ses rangs, ce qui y pousse, où en est chaque culture et ce qui reste libre
Afin de savoir en trois secondes où est quoi et où je peux encore semer ou planter

**Contexte fonctionnel :**
Le sous-onglet « Vue plan » est un écran d'attente depuis US-053 (« Représentation en plan des planches et des rangs, avec placement des cultures par glisser-déposer »). Trois versions ont été dessinées : une treemap à aire proportionnelle (v1), un plan géométrique à l'échelle (v2), puis la **V1 retenue** (v3, *Plan simplifié*) : « Une parcelle affiche ses rangs, un rang par culture. Un rang est un trait horizontal dont la longueur dit la quantité relative dans cette parcelle. Aucun plant n'est dessiné, aucune surface réelle n'est calculée. »

Cette US dessine cette V1 à partir de la répartition calculée par US-198, avec les **règles de rendu 1 à 9, 14b, 15 et 16** du wireframe v3 et les arbitrages A1, A2, A3, A5, A6 du plan des épics. Les **interactions** (appui sur un rang, liens de sortie, « Journal du jour ») sont l'objet d'US-201, le **réordonnancement** d'US-202 : ici, les éléments sont posés et accessibles, leurs destinations viennent ensuite.

Le jardinier lit, dans l'ordre (v3) : les cultures présentes, un libellé par rang, jamais masqué ; le nombre de rangs occupés, qui fait la hauteur de la carte ; qui prend le plus de place, le trait le plus long ; ce qui est semé en surface, la trame ; la phase, la couleur et le mot.

⚖️ **Conception avant implémentation (RT9).** Le wireframe v3 fixe la structure et les règles ; la maquette haute fidélité est produite dans le projet Claude Design « potager 2026 » et **gelée avant le code**, après tranchage des arbitrages du plan des épics.

**Règles de rendu :**

| # | Règle |
|---|---|
| V1 | **Une carte par parcelle**, de largeur égale, dans l'ordre déclaré (`ordre`, puis nom). Pas d'aire proportionnelle, pas de position, pas de forme |
| V2 | **Un rang = une ligne**, du rang 1 au dernier ; la hauteur de la carte vient du nombre de rangs |
| V3 | **Longueur** = quantité par rang ÷ quantité par rang la plus forte de la parcelle **à unité égale**. Plancher 12 %, plafond 100 % : jamais de dépassement de trait (A2) |
| V4 | **Forme = mode** : trait plein (rang), trait tramé à 45° (surface), trait segmenté (poquet) — un segment par poquet, douze au plus, et « ×18 » écrit au-delà. En mode poquet, douze segments font la largeur entière |
| V5 | **Couleur = phase** (US-194) : semée, en place, en récolte. Jamais la famille, jamais la confiance |
| V6 | **Libellé toujours visible** à droite du trait : culture, variété si connue, quantité et unité du rang. Aucun survol requis |
| V7 | **Rang libre** : trait pointillé, mot « libre », action « ajouter une culture » |
| V8 | **Parcelle pépinière** : carte hachurée, type de pépinière (US-208, « type non renseigné » sinon), nombre de lots en cours, lien vers la Pépinière. Aucun rang de semis. Une plantation faite dans cette parcelle reste dessinée en rang sous le compte des lots |
| V9 | **Donnée manquante** (A6) : sans nombre de rangs, les cultures restent dessinées, sans rang libre, avec la mention « nombre de rangs non renseigné » et la phrase à dire au compagnon. Sans nombre de rangs **et** sans culture : carte en pointillé, sans dessin, même mention. Une parcelle ne disparaît jamais du Plan, et l'écran ne propose jamais de la corriger |
| V10 | **Dépassement** : « 6 rangs occupés pour 5 déclarés », en teinte d'alerte, toutes les lignes affichées |
| V11 | **En-tête de carte** : nom · superficie (ou « superficie non renseignée ») · « N rangs sur M » · « Fiche parcelle → ». Pas de pourcentage sur la carte (A3) |
| V12 | **Numérotation** (A5) : « Rang 1… » dans l'ordre d'installation, et la légende le dit une fois pour l'écran. Les rangs suivants d'une culture posée sur plusieurs rangs sont regroupés visuellement et leur libellé réduit à la quantité |
| V13 | **Légende** en tête : les trois phases et « rang libre », les trois formes, la règle de numérotation |
| V14 | **Pied de vue** : total en m², rangs occupés sur rangs déclarés avec leur pourcentage, rangs libres par parcelle, nombre de parcelles sans nombre de rangs. « Trois chiffres, pas un tableau de bord » |
| V15 | **Date de référence** affichée en haut ; la phase est celle de ce jour, jamais une projection |
| V16 | **La couleur ne porte jamais seule** : la phase est aussi écrite en mot sur chaque rang, le mode se lit à la forme ; l'écran reste lisible en niveaux de gris |
| V17 | Les cultures **non localisées** forment une dernière carte, sans rang ni numéro, avec la phrase à dire pour les rattacher |

**Critères d'acceptance :**

*Rendu*
- [ ] CA1 : Le sous-onglet « Vue plan » remplace son écran d'attente et applique les règles V1 à V17 à partir de la seule lecture de `GET /plan` (US-198) — aucune autre requête
- [ ] CA2 : Les longueurs, plancher, plafond, segments et « ×N », le texte du pied de vue et les libellés de rang sont calculés par une lib sans React (`frontend/src/lib/planVue.js`) couverte par `npm test`, sur le modèle de `plan.js` et `pepiniere.js`
- [ ] CA3 : Les teintes de phase viennent de `PastillePhase` / `LegendePhases` (US-194) ; les trames (surface, rang libre, pépinière) sont des tokens du design system avec leur variante sombre
- [ ] CA4 : Les composants de carte, de rang et de trait acceptent une **palette en paramètre**, pour que l'onglet Rotation (hors périmètre, en construction) les reprenne sans les modifier

*Mise en page*
- [ ] CA5 : Deux colonnes de cartes à partir de 720 px de **largeur de conteneur**, une en dessous, jamais trois (A1) ; container queries, jamais de breakpoint d'écran (règle « Responsive » de `frontend/CLAUDE.md`)
- [ ] CA6 : À 375 px, une colonne : numéro abrégé (« R1 »), trait, libellé court ; la phase **reste écrite** sous le libellé (V16) — la colonne de pastille du desktop se replie, elle ne disparaît pas
- [ ] CA7 : Aucun défilement horizontal de la page à 375 px, libellés longs compris (troncature avec texte complet accessible)

*États*
- [ ] CA8 : Chargement : squelette, jamais de traits qui se remplissent. Échec : message et relance (`ApiError`), sans valeur de repli. Aucune parcelle : même message que l'onglet Parcelles
- [ ] CA9 : Au premier jour — aucune parcelle n'a encore de nombre de rangs — l'écran reste pleinement lisible : chaque culture a son trait, chaque carte sa mention (V9), et le pied de vue compte les parcelles sans nombre de rangs

*Accessibilité*
- [ ] CA10 : Chaque rang est un élément focalisable dont le nom accessible dit tout (« Rang 2, tomate cerise, 5 plants, en place ») ; le trait est décoratif ; ordre de tabulation carte par carte, rang par rang ; contrastes AA dans les deux thèmes

*Définition de terminé*
- [ ] CA11 : Une page de contrôle visuel (sur le modèle de `/fiche-calendrier`, US-183 / CA18) rejoue avec des réponses simulées : carte normale, trois formes, poquets au-delà de douze, rang libre, parcelle sans nombre de rangs avec et sans culture, dépassement, pépinière chaude avec une plantation, non localisé, thème sombre
- [ ] CA12 : Le rendu correspond à la **maquette haute fidélité gelée** à 375 px, 768 px et desktop ; vérification chrome-devtools à 375 px avant de déclarer l'US terminée (`frontend/CLAUDE.md`)
- [ ] CA13 : La fiche `parcelles-et-plan.md` gagne une section « Lire la Vue plan » : formes, couleurs, rangs libres, numérotation, parcelle sans nombre de rangs (US-099 / CA9) ; `ANALYSE_REFONTE_UI_WEB_2026.md` (§ 5.3 bis, Lot G) note que la Vue plan est livrée et que la Rotation reste à venir

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA, écran Plan)
- Migration BDD requise : **non**
- Dépendances : **US-198** (répartition, bloquante), **US-194** (phase et pastille, bloquante) ; US-208 (type de pépinière) et US-199 (unité poquet) enrichissent le rendu sans le bloquer
- Suites : US-201 (interactions et sorties), US-202 (réordonner)
- Impact tokens : zéro
- Impact design system : nouveaux composants `CartePlanParcelle`, `RangPlan`, `TraitRang` (quatre variantes : plein, tramé, segmenté, libre) ; `PastillePhase` et `LegendePhases` réutilisés ; aucun composant existant modifié
- Point de vigilance : les observations (US-039) ne sont **pas** portées sur la Vue plan ; elles restent sur l'onglet Parcelles
- Point de vigilance : « la quantité est toujours écrite à côté du trait, c'est ce qui rend l'échelle inoffensive » (v3). Un trait de plants ne se compare jamais à un trait de m² : chaque unité a son propre maximum dans la parcelle
- Wireframe : `maquette front/wireframes/Wireframes v3 - Plan simplifie.html`, § 1, 1b, 2, 2b, 3 (colonne « Rendu »)

**Estimation :** 8 points (hors conception : la maquette haute fidélité est un préalable)

**Scénario Gherkin :**
```gherkin
Scénario: Lecture d'une planche
  Given la planche centrale porte 5 rangs
  And y sont en place 8 tomates noire de Crimée, 5 tomates cerise, 3 courgettes en récolte et 2 m² de carottes semées
  When j'ouvre la Vue plan
  Then la carte "planche-centrale" affiche "12 m² · 4 rangs sur 5"
  And le rang des 8 tomates a le trait le plus long parmi les rangs en plants
  And le rang des 5 tomates cerise mesure 62 % de ce trait
  And le rang de carottes est tramé et pleine longueur, avec "2 m²" écrit à côté
  And le rang 5 est en pointillé avec le mot "libre"

Scénario: Poquets au-delà de douze
  Given 18 poquets de haricots à rames en place
  When j'ouvre la Vue plan
  Then leur rang affiche douze segments et le libellé "×18"

Scénario: Parcelle sans nombre de rangs
  Given la planche est n'a pas de nombre de rangs et porte 3 courgettes
  When j'ouvre la Vue plan
  Then la carte "planche-est" dessine le rang de courgettes
  And n'affiche aucun rang libre
  And porte la mention "nombre de rangs non renseigné" avec la phrase à dire au compagnon

Scénario: Pépinière
  Given la serre est une pépinière chaude qui abrite 3 lots
  When j'ouvre la Vue plan
  Then la carte "SERRE" est hachurée, porte "pépinière chaude · 3 lots en cours" et aucun rang de semis

Scénario: Lecture en niveaux de gris
  Given l'affichage est en niveaux de gris
  When j'ouvre la Vue plan
  Then chaque rang porte sa phase écrite en toutes lettres
  And les trois modes restent distincts par leur forme
```

**Labels GitHub :** `us`, `frontend`, `pwa`, `plan`, `design-system`

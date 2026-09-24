**ID :** US-228
**Titre :** Dessiner le rang comme une piste de places
**Épic :** ÉPIC 10 — Plan : l'occupation en rangs et le zoom d'information *(numéro à valider, voir le plan des épics 9 à 12)*

**Ajustement de rendu validé après implémentation :** la référence devient
`maquette front/Plan - Rangs et places.html`, avec **sept symboles
proportionnels**. La dernière validation demande les **emoji de culture exacts
de la maquette**, dans la piste et en tête de rang sur les cartes larges, ainsi
que les graines, la jeune pousse et le panier dans les pastilles et la légende.
Elle remplace le choix intermédiaire de repères neutres et l'arbitrage A27.
Les places restantes portent une pousse en contour ; les rangs libres n'ont
plus de lien « ajouter une culture ». Cet ajustement
remplace les silhouettes et le regroupement par seize décrits ci-dessous
(P1, P2, P13, CA3) : aucun repère ne vaut un nombre de plants. Le nombre plein
est l'arrondi de `prises / places × 7`, borné à sept et au minimum un si une
place est prise ; le fond garde la proportion et le plancher de P3. Les comptes
exacts et la phase écrite restent visibles. Les calculs serveur, les modes
dégradés et le périmètre des US livrées restent inchangés : **pas de largeur
standard de 40 cm pour les surfaces**, ni d'interactions US-201/222/223.
Les critères ci-dessous et les notes de livraison initiale restent l'historique
de la première version ; la nouvelle référence s'applique aux contrôles visuels
CA1/7/12 et à la documentation CA13.

L'en-tête P11 suit également cette référence : quatre pictogrammes distincts
(superficie, longueur, largeur, rangs), valeurs manquantes en rouge avec « ? »,
total de rangs inconnu explicitement signalé, rangs libres affichés si connus.
La largeur reste fournie par le serveur ; une incohérence reste signalée, et
les pépinières conservent leur compte de lots.

**Story :**
En tant que jardinier
Je veux voir sur chaque rang mes pieds installés et les places qui restent
Afin de lire ma planche comme je la vois sur le terrain, et non comme un diagramme en barres

**Contexte fonctionnel :**
La maquette haute fidélité `maquette front/haute-fidelite/Plan - Rangs et places.html`, gelée le 23/09/2026 (RT9), remplace le trait d'US-200 / V3 par une **piste de places** : un rail par rang, un pictogramme par pied installé, une place en creux par place libre, un remplissage coloré par la phase, et à droite le reste en chiffres.

C'est un changement de nature, pas d'habillage. Le trait d'US-200 disait une quantité **relative** (« ce rang est le plus fourni de la parcelle ») ; la piste dit une quantité **absolue** (« il reste 15 places »). La longueur relative ne disparaît pas pour autant : la maquette la conserve comme **mode dégradé**, dessiné tel quel avec la mention « N places ? », pour toute parcelle sans longueur ou toute culture sans espacement.

⚖️ **Elle étend US-200, elle ne la refait pas.** US-200 livre la carte, les lignes de rang, l'en-tête, le pied de vue, la légende, les états et l'accessibilité — tout cela reste. Cette US remplace **V3** (longueur relative) par la piste, étend **V6** (le libellé porte l'espacement), **V11** (l'en-tête porte longueur et largeur), **V13** (la légende explique le pictogramme et la place en creux) et **V14** (le pied compte les parcelles sans longueur). `V4` (forme = mode) et `V5` (couleur = phase) tiennent inchangées.

⚖️ **Pictogrammes, pas emoji** (arbitrage A27). La maquette utilise des emoji système (🍅 🥒 🎃) pour aller vite ; la livraison les remplace par un jeu de **pictogrammes SVG monochromes** du design system, teintés par la phase. Un emoji change de dessin et de couleur selon le poste, et sa couleur entre en concurrence avec la couleur de phase (RT4) : ce serait une troisième palette.

**Règles de rendu — elles prolongent V1 à V17 d'US-200 :**

| # | Règle |
|---|---|
| P1 | **Le rang est une piste** de largeur fixe, divisée en autant de fentes que le rang a de places (US-227 / R10). Les places prises portent le pictogramme de la culture, les places restantes une **marque en creux**. Le remplissage coloré s'arrête à la dernière place prise |
| P2 | **Seize fentes au plus.** Au-delà, une fente vaut plusieurs places : `pieds_par_fente = ⌈places ÷ 16⌉`, et la légende du rang le dit (« 1 pictogramme = 2 plants »). Jamais de fente illisible |
| P3 | **Plancher de lisibilité** : une piste dont une seule place est prise affiche tout de même un remplissage visible (8 % au minimum), la quantité restant écrite à côté (A2, transposé) |
| P4 | **Dépassement de rang** (US-227 / R14) : la piste est pleine et porte « +N » en pastille d'alerte ; la colonne de droite écrit « N en trop ». Le libellé conserve la quantité déclarée, jamais tronquée |
| P5 | **Colonne de reste**, à droite de la piste : « reste **15** plants », ou « N en trop » en teinte d'alerte, ou rien quand les places ne sont pas calculables |
| P6 | **Mode dégradé** — places non calculables (US-227 / R11) : la piste retombe sur la **longueur relative** d'US-200 / V3, sans place en creux, et la colonne de droite écrit la quantité suivie de « places ? ». C'est le dessin que la maquette donne à `planche-est` |
| P7 | **Semis en ligne** (unité `ml`) : la piste est remplie à la part semée (US-227 / R15), sans place en creux ni colonne de reste. Le libellé écrit « 3 m semés » |
| P8 | **Semis en surface** (`m2`) : la piste garde la trame à 45° d'US-200 / V4 et le mode dégradé du P6. Une surface n'a pas de places |
| P9 | **Rang libre** : piste entièrement en creux, bordure pointillée, mot « libre », et sous le libellé la longueur du rang suivie, s'il y en a une, de la capacité d'exemple **nommée** d'US-227 / R16 (« 12 m · ex. 24 tomates »). Jamais d'exemple sans culture de référence |
| P10 | **Libellé du rang** (V6 étendu) : culture, variété, puis en seconde ligne la quantité avec son unité et, si elle est connue, l'espacement sur le rang précédé de son pictogramme de cote (« 9 plants · ↔ 50 cm ») |
| P11 | **En-tête de carte** (V11 étendu) : nom · superficie · **« rangs de 12 m · largeur 5,75 m »** précédé du pictogramme de cote · « N rangs sur M » · « N libres » · « Fiche parcelle → ». La largeur est marquée comme déduite ; incohérente (US-225 / CA7), elle est remplacée par la mention de l'incohérence, jamais par un chiffre corrigé |
| P12 | **Mention d'absence** : une parcelle sans longueur porte, comme elle porte déjà celle du nombre de rangs (V9), un encart « Longueur non renseignée : les places ne peuvent pas être calculées » suivi de **la phrase exacte à dire au compagnon**, avec le nom de la parcelle dedans. Les deux encarts se cumulent sans se répéter |
| P13 | **Légende** (V13 étendu) : les quatre états — en place, en récolte, semée, libre —, puis « pictogramme = 1 place prise » avec son équivalence quand P2 s'applique, « marque en creux = place restante », et la règle de numérotation |
| P14 | **Pied de vue** (V14 étendu) : « N m² cultivés · N rangs occupés sur M déclarés · N parcelle(s) sans longueur ». Toujours trois chiffres, jamais de total de places ni de taux de remplissage (RT13) |
| P15 | **Lisible en niveaux de gris** (RT4, V16) : la place prise et la place restante se distinguent par leur **forme** — pictogramme plein contre marque en creux —, pas seulement par leur teinte. La phase reste écrite en mot |

**Critères d'acceptance :**

*Rendu*
- [x] CA1 : P1 à P15 sont appliquées, et le rendu correspond à la **maquette gelée** `maquette front/haute-fidelite/Plan - Rangs et places.html` à 375 px, 768 px et desktop ; vérification chrome-devtools à 375 px avant de déclarer l'US terminée (`frontend/CLAUDE.md`, RT9)
- [x] CA2 : Le calcul des fentes, du regroupement de P2, du plancher de P3 et des libellés est fait dans `frontend/src/lib/planVue.js` (US-200 / CA2), **sans React**, couvert par `npm test`. Aucune règle métier n'y est recalculée : les places, les restes et les dépassements viennent tels quels de `GET /plan` (RT7)
- [x] CA3 : Un jeu de **pictogrammes SVG** monochromes entre au design system, teintés par la couleur de phase, avec une **forme neutre de repli** pour toute culture non couverte. La correspondance culture → pictogramme est une table de présentation isolée, sur le modèle de `familles.js`, et son absence n'empêche jamais le rendu (A27)
- [x] CA4 : La piste et ses états sont un composant du design system (`PisteDesPlaces`), consommé par `RangPlan` d'US-200 ; il accepte la **palette en paramètre** et la **variante de taille** déjà prévues par US-200 / CA4, pour que l'onglet Parcelles (US-222) et l'onglet Rotation le reprennent sans second dessin

*Mise en page*
- [x] CA5 : Deux colonnes de cartes à partir de **1000 px de largeur de conteneur**, une en dessous, jamais trois — le seuil de la maquette, qui remplace les 720 px d'A1 (arbitrage A23). Container query, jamais de breakpoint d'écran
- [x] CA6 : Sous **560 px de largeur de carte**, la ligne de rang se replie en trois zones — libellé et pastille de phase sur la première ligne, piste sur la deuxième, reste sur la troisième — le numéro de rang restant en marge. Le pictogramme de tête de ligne disparaît, la piste ne rétrécit jamais sous 44 px de haut de cible d'appui
- [x] CA7 : Aucun défilement horizontal de la page à 375 px, libellés longs et pistes à seize fentes compris

*États*
- [x] CA8 : Les cinq cas sont rendus et distincts : places calculées, mode dégradé (P6), semis en ligne (P7), semis en surface (P8), rang libre (P9)
- [x] CA9 : Au premier jour — aucune parcelle n'a de longueur, aucune culture d'espacement — l'écran est **exactement celui d'US-200** : longueur relative partout, mention par carte, pied de vue complet. Aucune régression, aucun écran vide

*Accessibilité*
- [x] CA10 : Le nom accessible d'un rang dit tout, places comprises : « Rang 1, tomate, 9 plants sur 24 places, 15 restantes, en place ». La piste et ses pictogrammes sont décoratifs (`aria-hidden`) : rien d'essentiel n'est porté par le seul dessin
- [x] CA11 : Contrastes AA dans les deux thèmes, pour le pictogramme plein comme pour la marque en creux ; la marque en creux reste perceptible sur fond sombre

*Définition de terminé*
- [x] CA12 : La page de contrôle visuel d'US-200 / CA11 gagne : piste normale, piste à seize fentes avec regroupement, rang surchargé, semis en ligne partiel et débordant, rang libre avec et sans capacité d'exemple, parcelle sans longueur, largeur incohérente, thème sombre
- [x] CA13 : La fiche `parcelles-et-plan.md` gagne « Lire un rang » : ce qu'est une place, pourquoi certains rangs n'en ont pas, pourquoi un pictogramme peut valoir plusieurs pieds, et ce que veut dire « +4 » (US-099 / CA9). `ANALYSE_REFONTE_UI_WEB_2026.md` (§ 5.10) note que la Vue plan se lit désormais en places et que le pourcentage de surface n'y figure plus

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA, écran Plan)
- Migration BDD requise : **non**
- Dépendances : **US-200** (Vue plan — bloquante, c'est elle qui pose carte, lignes, légende et pied), **US-227** (places et restes — bloquante) ; US-199 (unités `ml` et `poquets`) pour que P7 ait de la matière, non bloquante
- Suites : US-222 (le niveau 2 reprend la piste agrandie), US-217 (la Pépinière propose où planter en places)
- Impact tokens : zéro
- Impact design system : nouveau composant `PisteDesPlaces` et jeu de pictogrammes de culture ; `TraitRang` d'US-200 devient l'un de ses modes (le mode dégradé), il n'est pas supprimé
- Point de vigilance : **ne pas livrer US-228 avant US-225 et US-226.** Livrée seule, elle n'aurait aucune place à dessiner et se réduirait au mode dégradé — c'est-à-dire à US-200
- Point de vigilance : la maquette dessine seize fentes même pour un rang de carottes à 5 cm d'espacement, soit 240 places. P2 rend la piste lisible, mais un pictogramme pour 15 carottes n'a plus grand sens : la fiche d'aide assume que la piste est une **image**, et que le chiffre à droite est ce qui fait foi
- Point de vigilance : le pictogramme de cote (« ↔ ») de P10 et P11 est le même symbole aux deux endroits, pour que le jardinier relie l'espacement d'une culture à la longueur de sa planche

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Un rang à moitié plein
  Given la planche centrale fait 12 m de long
  And 9 tomates espacées de 50 cm occupent son rang 1
  When j'ouvre la Vue plan
  Then la piste du rang 1 porte 9 pictogrammes de tomate et 15 marques en creux
  And la colonne de droite écrit "reste 15 plants"
  And le libellé écrit "9 plants · 50 cm"

Scénario: Un rang surchargé
  Given 26 tomates cœur de bœuf espacées de 40 cm occupent un rang de 9 m
  When j'ouvre la Vue plan
  Then la piste est pleine et porte la pastille "+4"
  And la colonne de droite écrit "4 en trop" en teinte d'alerte
  And le libellé écrit toujours "26 plants"

Scénario: Mode dégradé
  Given la planche est n'a pas de longueur
  And 8 tomates cerise y sont en place
  When j'ouvre la Vue plan
  Then leur rang est dessiné à sa longueur relative, sans marque en creux
  And la colonne de droite écrit "8 places ?"
  And la carte porte la phrase à dire au compagnon pour déclarer sa longueur

Scénario: Rang libre
  Given la planche centrale fait 12 m et porte des tomates espacées de 50 cm
  And son rang 13 est libre
  When j'ouvre la Vue plan
  Then sa piste est entièrement en creux et pointillée
  And son libellé écrit "12 m · ex. 24 tomates"

Scénario: Trop de places pour seize fentes
  Given un rang de 12 m porte des carottes semées, espacées de 5 cm
  When j'ouvre la Vue plan
  Then la piste affiche seize fentes au plus
  And la légende du rang dit combien de places vaut un pictogramme

Scénario: Lecture en niveaux de gris
  Given l'affichage est en niveaux de gris
  When j'ouvre la Vue plan
  Then une place prise et une place restante restent distinguables par leur forme
  And chaque rang porte sa phase écrite en toutes lettres
```

**Livraison (23/09/2026) :**
- Nouveaux fichiers : `frontend/src/components/ui/PisteDesPlaces.jsx` (la piste, le jeu de silhouettes et le pictogramme de cote) et `frontend/src/lib/pictosCultures.js` (la table culture → silhouette, isolée). `TraitRang` n'est pas supprimé : il est devenu le **mode dégradé** de la piste (P6, P8)
- P15 / CA11 — les pictogrammes prennent la teinte **forte** de la phase sur un remplissage en teinte **douce** (la paire du design system) : un pictogramme de la couleur du remplissage s'y effacerait, et la marque en creux reste perceptible en thème sombre
- P2 — l'équivalence « 1 pictogramme = N » est écrite **sur le rang lui-même**, sous son libellé, en plus de l'avertissement de la légende : la légende ne dit pas quel rang est concerné
- CA5 — le seuil de deux colonnes passe de 720 à 1000 px : `test_us200_ca5_deux_colonnes_par_container_query_jamais_trois` a été mis à jour, la règle (container query, jamais trois colonnes) est inchangée
- CA1, CA7 — contrôle visuel chrome-devtools à 375 px, en desktop deux colonnes et en thème sombre, sur `/vue-plan` : aucun défilement horizontal, les cinq états distincts
- **Reste ouvert** : l'unité `ml` de P7 n'est pas encore produite par la dictée (US-199 non livrée) — le rendu est en place et couvert par les tests, mais aucun geste réel ne porte cette unité aujourd'hui

**Labels GitHub :** `us`, `frontend`, `pwa`, `plan`, `design-system`

---

## ⚠️ AMENDEMENT du 24/09/2026 — la fiche parcelle ne porte plus le détail des cultures

Origine : maquette `Parcelle - Fiche.html`, détaillée dans l'amendement de
**US-222**, qui fait foi. La fiche d'une parcelle porte désormais un simple
**bandeau d'occupation** (« N rangs occupés sur M », les noms des cultures) et
un bouton « Voir les cultures dans le Plan → » : plus aucune tuile de culture,
plus aucun rang libre actionnable.

- **CA4 se relit** : la variante de taille de `PisteDesPlaces` n'a plus l'onglet
  Parcelles pour consommateur. Elle reste due à l'onglet Rotation et à la fiche
  culture (US-206, US-207).
- La note « Suites : US-222 (le niveau 2 reprend la piste agrandie) » est
  **caduque**. Tout le reste de l'US — la piste, ses états, l'en-tête de carte
  P11 dans la Vue plan — est inchangé.

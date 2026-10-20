**ID :** US-242
**Titre :** Afficher l'onglet « Lots » de la Pépinière en journal de saison — chaque lot sur une frise de ses gestes datés, sa fiche dépliée sous la ligne
**Épic :** ÉPIC 12 — Pépinière : le poste de travail sous abri *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux voir tous mes lots de la saison sur une même frise, chaque geste à sa date (semé, levée notée, mis en godet, déplacé, clôturé), avec un bilan de ce que mes graines ont donné
Afin de relire ma saison d'un coup d'œil et de retrouver l'histoire d'un lot sans repasser par le parcours

**Contexte fonctionnel :**
L'onglet « Lots » devient un **registre sans geste** (orientation A40 de `pepiniere/03_VUE_LOTS.md`) : on y lit, on agit dans « Ma pépinière ». Il remplace la grille de cartes par famille (US-061) par la maquette « Lots - Journal de saison HF » (projet Claude Design, 19/10/2026). Toutes les dates viennent de `GET /pepiniere/lots`, qui porte déjà `date_semis`, `date_derniere_levee`, `date_derniere_mise_en_godet`, `date_deplacement`, `date_cloture`, `date_dernier_geste` et la fenêtre `echeances.mise_en_terre` ; les mises en terre (avec leur parcelle), ventes et pertes en godet sont datées par `sorties_datees`, champ ajouté à `GET /pepiniere/lots` et à `GET /pepiniere/lots/{numero}` (amendement du 20/10/2026 : l'API ne donnait d'abord que leur total). Un geste sans date reste compté, jamais placé sur la frise.

**Critères d'acceptance :**
- [ ] CA1 : Un sélecteur **En cours / À régler / Terminés / Tous**, chacun avec son compte. « Terminé » = lot terminé ou clôturé (règle de la fiche du lot, US-216) ; « À régler » = quantité semée non dite, ou échéance incalculable faute de délai renseigné ; « En cours » = le reste. « Tous » est sélectionné à l'ouverture.
- [ ] CA2 : Un **bilan** des lots visibles : la part des graines semées qui a donné un plant (en %), une phrase (« N plants attendent en godet », et le lot dont la mise en terre est à faire, avec sa date limite), les quatre chiffres semées / plants obtenus / en godet / mis en terre, et une barre empilée mis en terre · en godet · en levée · pertes · non levées.
- [ ] CA3 : Une **frise par lot**, regroupée par mois de semis (tri du plus ancien au plus récent) : un trait plein du semis au dernier geste, pointillé du dernier geste à aujourd'hui pour un lot non terminé, un repère rouge « aujourd'hui », la fenêtre de mise en terre prévue hachurée, et une pastille par geste daté — dont chaque mise en terre, vente et perte en godet, à sa date. Les pastilles trop proches se décalent au-dessus ou au-dessous du trait ; le survol donne la date.
- [ ] CA4 : Une **fenêtre de temps** au choix : « Saison » (1er mars → 30 novembre, étendue pour contenir le jour de référence) ou « récent » (du 1er du mois deux mois avant le jour de référence à la fin du mois suivant), au libellé calculé (« Août → nov. »). La fenêtre ne retire aucun lot ; un semis antérieur reste accroché au bord gauche, en pâle. Au téléphone, la fenêtre récente s'applique.
- [ ] CA5 : Une légende des gestes, et pour chaque ligne : le mois (premier lot du mois), le numéro et le nom du lot (souligné), la frise, le statut et une ligne « où il en est ».
- [ ] CA6 : Toute la ligne est cliquable (clavier compris, `aria-expanded`). Sur un conteneur large, la **fiche se déplie sous la ligne** en trois blocs — Lot sélectionné (identité, emplacement, statut, échéance, où les mettre), Bilan (taux, barre, traçabilité), Journal du lot (chaque geste daté en J+n depuis le semis, chaque mise en terre avec sa parcelle, ses ventes et pertes, et ce qui n'a pas de date compté « date non transmise », puis « Aujourd'hui · N j sans geste ») ; un second appui ou la croix la replie. Sur un conteneur étroit, la même fiche s'ouvre **en plein écran**.
- [ ] CA7 : La fiche n'a **aucun bouton de geste** : un lien « Agir dans Ma pépinière » bascule sur l'onglet parcours et y ouvre la fiche du lot (US-216). Un lot terminé n'a pas ce lien.
- [ ] CA8 : La recherche (culture, variété, numéro) et « Aller au lot n° » sont conservés ; « Aller au lot n° » remet le filtre sur « Tous » et déplie la fiche du lot ; un numéro inconnu le dit (US-209 / CA11).
- [ ] CA9 : Sans donnée, pas de valeur (RT2) : quantité non dite → « pas de bilan possible », tiret pour un geste jamais fait, aucune date inventée.
- [ ] CA10 : Le rendu correspond visuellement à la maquette de référence à 375 px et desktop ; mise en page des composants par container queries.
- [ ] CA11 : Les règles (statut, gestes datés, fenêtre, positions, bilan) vivent dans `frontend/src/lib/lotsJournal.js`, couvertes par `npm test`.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA)
- Migration BDD requise : non
- Dépendances : US-216 (fiche du lot), US-218 (onglets), US-209 (numéro), US-214 (échéances), US-217 (où les mettre)
- Amendement du 20/10/2026 : le calcul des lots (`calcul_lots_pepiniere`) garde, pour chaque mise en terre, vente et perte imputée à un lot, sa date, sa quantité et — pour la mise en terre — sa parcelle ; une plantation répartie sur deux lots donne à chacun sa part. Pas de migration.

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given un lot n° 4 de tomate jaune semé le 21 septembre, mis en godet le 9 octobre et déplacé le 12 octobre
When j'ouvre l'onglet « Lots » de la Pépinière
Then la ligne du lot 4 montre trois pastilles datées sur la frise de septembre à aujourd'hui
And la fenêtre de mise en terre prévue est hachurée

Given l'onglet « Lots » ouvert sur un écran large
When je clique sur la ligne du lot 4
Then sa fiche se déplie sous la ligne avec son bilan et son journal (J0 semé, J18 mis en godet, J21 déplacé)
And elle ne propose aucun geste mais un lien « Agir dans Ma pépinière »

Given un lot de tomate semé le 15 mars, mis en godet, puis planté le 15 juin sur « planche_centrale »
When je déplie sa fiche
Then son journal affiche « Mis en terre · 15 juin · 10 plants · planche_centrale »
And la frise porte une pastille de mise en terre au 15 juin

Given un lot de laitue semé sans quantité dite
When je choisis le filtre « À régler »
Then le lot de laitue apparaît
And sa fiche dit « quantité semée non dite : pas de bilan possible »
```

**Labels GitHub :** `us`, `pwa`, `pepiniere`

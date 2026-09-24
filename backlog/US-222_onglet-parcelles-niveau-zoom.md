**ID :** US-222
**Titre :** Recoudre l'onglet Parcelles sur la Vue plan — le niveau 2 du zoom
**Épic :** ÉPIC 10 — Plan : l'occupation en rangs et le zoom d'information *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux qu'en ouvrant une parcelle je retrouve exactement les rangs que je viens de voir dans la Vue plan, agrandis, avec ce que la Vue plan ne pouvait pas porter — exposition, abri, frise des douze mois, confiance, observations
Afin de descendre du potager entier à une planche sans changer de langage graphique ni recompter l'occupation autrement

**Contexte fonctionnel :**
Le wireframe v4 (21/09) pose le **zoom d'information** : quatre niveaux, un objet par niveau — le potager entier (Vue plan), une parcelle (onglet Parcelles), une culture (fiche culture), son calendrier (fiche calendrier). « Un niveau agrandit l'objet du niveau précédent et ajoute ce que ce niveau ne pouvait pas porter. Il ne le reformate jamais. »

Or l'onglet **Parcelles** est resté celui d'US-060 : maître-détail, occupation en **pourcentage de surface**, tuiles de culture sans lien avec le dessin de la Vue plan. « Deux écrans du même objet, conçus séparément. » Un jardinier qui appuie sur un rang de la Vue plan puis ouvre la fiche de sa parcelle n'y retrouve ni le rang, ni le trait, ni la même mesure d'occupation.

Cette US recoud le niveau 2 sur le niveau 1 : la tuile de culture porte **son numéro de rang et son trait**, l'occupation se dit **en rangs** comme partout ailleurs dans l'activité Plan, et le rang libre devient actionnable ici aussi. Tout le reste du niveau 2 — ce qui justifie qu'il existe — est conservé : superficie, exposition, abri, paillage, observations, famille, durée, frise des douze mois, pastille de confiance.

⚖️ **Elle amende une US livrée.** US-060 est en production : ses CA ne sont pas réécrits, c'est cette US qui les remplace et le dit. Sont remplacés : **CA2** (pourcentage d'occupation dans la liste), **CA5** (ligne « Occupation de la surface » et sa barre), **CA12** (code couleur d'occupation, pourcentage de surface) ; est étendu : **CA7** (la tuile de culture gagne son rang et son trait).

⚖️ **Conception avant implémentation (RT9)** : wireframe v4 § 1 (desktop), § 1b (375 px), § 2 (matrice « qui porte quoi ») ; maquette haute fidélité gelée avant le code, **après** tranchage des arbitrages A20 (retrait du pourcentage de surface) et A21 (tuile chargée de son trait en plus de sa frise et de sa confiance).

**Règles de rendu :**

| # | Règle |
|---|---|
| D1 | **La liste de gauche reste un index** : aucune parcelle n'y est dessinée. Une ligne porte l'épingle, le nom, « N cultures · X m² » (ou « libre · X m² ») et l'occupation **en rangs** — « 4/5 » — à droite, à la place du pourcentage |
| D2 | **Aucune teinte d'occupation** : le code couleur vert / ambre / rouge d'US-060 disparaît. Dans l'activité Plan, la couleur dit la phase et rien d'autre (RT4). Seul le dépassement garde une teinte d'alerte |
| D3 | **Parcelle pépinière** dans la liste : « pépinière chaude · 3 lots » (US-208, « type non renseigné » sinon), occupation « — ». Son détail porte ses lots en cours et le lien vers la Pépinière, pas des rangs de semis ; une plantation faite dans cette parcelle reste dessinée en rang (US-200 / V8) |
| D4 | **Parcelle sans nombre de rangs** : listée normalement, occupation « — », sous-titre « nombre de rangs non renseigné » (A6). Son détail dessine ses cultures, sans rang libre, avec la mention et la phrase à dire au compagnon |
| D5 | **En-tête du détail** : le nom, « ← Voir dans la Vue plan », puis les pastilles superficie, **longueur et largeur déduite** (US-225, « longueur non renseignée » sinon), exposition, abri ou plein air et paillage (US-181, livrée), « **N rangs occupés sur M** », et le lien « N observations » (US-039) |
| D6 | **La ligne « Occupation de la surface », son infobulle, son pourcentage et sa barre sont retirés** (A20). La superficie en m² reste ; l'occupation se dit en rangs, d'un bout à l'autre de l'activité Plan |
| D7 | **La tuile de culture porte en tête son numéro de rang et sa piste** : même forme (mode d'implantation), même couleur (phase), **mêmes places prises et restantes** que dans la Vue plan, même quantité écrite. C'est le composant d'US-200 et d'US-228 dans sa variante agrandie, jamais un second dessin. Tant qu'US-228 n'est pas livrée, ou pour une parcelle sans longueur, c'est le trait de longueur relative d'US-200 / V3 qui est repris — le niveau 2 dégrade exactement comme le niveau 1 |
| D8 | **Le reste de la tuile est inchangé** (A21) : famille · durée de culture, frise des douze mois (`MonthStrip`, non modifié), pastille de confiance, observations de la culture, ouverture de la fiche calendrier, lien « Voir la culture → » (US-201 / CA8). La phase reste écrite en mot (RT4) |
| D9 | **Culture posée sur plusieurs rangs** : une seule tuile, ses numéros annoncés (« Rangs 1 et 2 »), un trait par rang, la quantité par rang écrite une fois |
| D10 | **Rang libre** : dernière ligne du détail, pleine largeur, piste entièrement en creux et mot « libre », sa longueur et sa capacité d'exemple nommée si elle existe (US-227 / R16, US-228 / P9), avec les deux intentions *Semer en place* et *Planter* pré-remplies sur cette parcelle et ce rang (US-196, US-203 si livrée) |
| D11 | **Dépassement** : « 6 rangs occupés pour 5 déclarés », en teinte d'alerte, toutes les tuiles affichées (même règle que US-200 / V10) |
| D12 | **375 px** : la liste se replie en **sélecteur horizontal** de pastilles « nom + occupation », la parcelle choisie restant visible sans écran de retour ; une seule colonne de tuiles ; la phase écrite sous le libellé ; cible d'appui de 44 px sur la tuile entière |

**Critères d'acceptance :**

*Lecture*
- [ ] CA1 : L'onglet n'ajoute **aucune lecture** : il consomme la réponse de `GET /plan` enrichie par US-198 (`disposition`, `numeros_rangs`, `mode_implantation`, `quantite_par_rang`), la même que la Vue plan. Changer de parcelle ne déclenche aucune requête (RT6)
- [ ] CA2 : Le remplissage d'un rang est calculé **par la même fonction** que la Vue plan (`frontend/src/lib/planVue.js`, US-200 / CA2), dans la même parcelle : un rang porte les mêmes places prises et restantes aux deux niveaux — ou, à défaut de longueur, la même longueur relative à unité égale. Un test compare les deux rendus pour un même jeu de données, dans les deux modes

*Rendu*
- [ ] CA3 : Les règles D1 à D12 sont appliquées
- [ ] CA4 : Les composants `TraitRang`, `RangPlan` et `PastillePhase` d'US-200 sont **réutilisés** dans une variante de taille, sans duplication de la logique de dessin ; ils acceptent toujours une palette en paramètre (US-200 / CA4)
- [ ] CA5 : Le pourcentage d'occupation, sa barre, son infobulle et son code couleur ne sont plus rendus dans l'activité Plan ; `occTint` et `pctDe` (`frontend/src/lib/plan.js`) sont retirés avec leurs tests, ou conservés seulement s'ils servent un autre écran — auquel cas l'US le dit à la livraison
- [ ] CA6 : Sont conservés à l'identique, et un test de non-régression le vérifie : le compteur de cultures, la superficie, l'exposition, la variété affichée à côté de la culture, la quantité **avec son unité** (US-060 / CA18), la frise, la pastille de confiance et l'ouverture de la fiche calendrier depuis la tuile

*Interaction*
- [ ] CA7 : Un appui sur la tuile entière, ou sur « Voir la culture → », ouvre la **fiche culture** (US-207) avec la parcelle en contexte
- [ ] CA8 : « ← Voir dans la Vue plan » ouvre le sous-onglet Vue plan avec la carte de cette parcelle à l'écran (intention `plan-vue` + `parcelle`, US-195 / CA2)
- [ ] CA9 : Un appui sur un rang libre propose *Semer en place* ou *Planter* et prépare le geste (US-196) avec la parcelle et le rang ; aucune écriture n'a lieu dans la PWA
- [ ] CA10 : Le détail d'une parcelle pépinière ouvre la Pépinière sur cet emplacement — onglet « Emplacements » si le potager compte plusieurs pépinières, « Aujourd'hui » sinon (US-201 / I5)
- [ ] CA11 : Revenir sur l'onglet après en être sorti — fiche culture fermée, aller-retour vers la Vue plan, changement de sous-onglet — rend l'écran dans son **état exact** : parcelle sélectionnée, position de défilement, focus sur l'élément d'origine (US-195, règle 25 de la v4)
- [ ] CA12 : Un membre en lecture seule voit le détail entier, sans les intentions du rang libre (RT11)

*États*
- [ ] CA13 : Parcelle **sans nombre de rangs** : ses tuiles sont dessinées, aucun rang libre n'est proposé, la mention et la phrase à dire au compagnon sont affichées (D4). Parcelle **libre** : le détail le dit et propose *Semer en place* / *Planter* sur son premier rang
- [ ] CA14 : Chargement : squelette. Échec : message et relance, sans valeur de repli. Ces deux états sont ceux de la Vue plan, pas des variantes

*Définition de terminé*
- [ ] CA15 : La composition d'une tuile (numéros de rang, longueur, libellé, mention de donnée manquante, texte d'occupation) vit dans la lib partagée avec la Vue plan, couverte par `npm test` : culture sur un rang, sur deux rangs, en surface, en poquets, parcelle sans nombre de rangs, dépassement, pépinière, parcelle libre
- [ ] CA16 : Une page de contrôle visuel rejoue : parcelle pleine, parcelle avec rang libre, parcelle sans nombre de rangs, dépassement, pépinière chaude avec une plantation, parcelle libre, lecture seule, 375 px avec le sélecteur horizontal, thème sombre
- [ ] CA17 : La fiche `parcelles-et-plan.md` est corrigée : l'occupation se lit en rangs, le pourcentage de surface n'est plus affiché, la tuile porte son rang et son trait, le rang libre est actionnable depuis les deux sous-onglets (US-099 / CA9). `ANALYSE_REFONTE_UI_WEB_2026.md` note que les CA2, CA5 et CA12 d'US-060 sont remplacés par cette US
- [ ] CA18 : Le rendu correspond à la maquette haute fidélité gelée à 375 px, 768 px et desktop ; vérification chrome-devtools à 375 px avant de déclarer l'US terminée

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA, écran Plan)
- Migration BDD requise : **non**
- Dépendances : **US-198** (répartition en rangs dans `GET /plan`, bloquante), **US-200** (composants de trait et de rang, bloquante), **US-228** (piste des places — non bloquante : livrée avant, le niveau 2 en hérite sans travail ; livrée après, elle amende D7 aux deux niveaux d'un coup), **US-195** (retour à l'état exact, lien vers la Vue plan), **US-196** (geste du rang libre), **US-207** (fiche culture) ; US-201 porte déjà le lien « Voir la culture » sur la tuile ; US-181 (abri et paillage, livrée) et US-208 (type de pépinière) enrichissent l'en-tête sans bloquer
- Impact tokens : zéro
- Impact design system : aucun composant nouveau — `TraitRang`, `RangPlan` et `PastillePhase` gagnent une variante de taille ; `ProgressBar` perd son usage sur l'écran Plan
- Point de vigilance : **régression visible pour les utilisateurs actuels** — le pourcentage d'occupation est lu depuis un an. Son retrait relève de l'arbitrage A20 : à confirmer avant la maquette haute fidélité, et à annoncer dans `PATCH_NOTES.md` en disant ce qui le remplace
- Point de vigilance : la liste de gauche n'est pas une seconde Vue plan. Si une parcelle venait à y être dessinée, le niveau 2 recommencerait à répéter le niveau 1 (règle 20 de la v4)
- Wireframe : `maquette front/wireframes/Wireframes v4 - Parcelles et zoom.html`, § 1, § 1b, § 2, règles 18 à 26

**Estimation :** 8 points (hors conception)

**Scénario Gherkin :**
```gherkin
Scénario: Le rang appuyé se retrouve agrandi
  Given la Vue plan affiche le rang 2 de la planche-centrale : tomate cerise, 5 plants, trait à 62 %
  When j'ouvre "Fiche parcelle →" de la planche-centrale
  Then la tuile de la tomate cerise porte "Rang 2" et le même trait, à la même longueur relative
  And elle porte en plus sa famille, sa durée, sa frise des douze mois et sa pastille de confiance

Scénario: L'occupation se dit en rangs
  Given la planche-centrale porte 5 rangs déclarés et 4 occupés
  When j'ouvre l'onglet Parcelles
  Then sa ligne de liste affiche "4/5"
  And son détail affiche "4 rangs occupés sur 5"
  And aucune barre ni aucun pourcentage d'occupation de surface n'est affiché

Scénario: Semer sur le rang libre depuis la fiche de parcelle
  Given le rang 5 de la planche-centrale est libre
  When j'appuie sur "Semer en place" sur ce rang
  Then mon compagnon s'ouvre sur un semis pré-rempli dans la planche-centrale
  And rien n'est enregistré avant ma confirmation

Scénario: Remonter d'un niveau
  Given j'ai ouvert la planche-ombre dans l'onglet Parcelles et fait défiler jusqu'à sa quatrième tuile
  When j'ouvre la Vue plan par "← Voir dans la Vue plan" puis je reviens sur l'onglet Parcelles
  Then la planche-ombre est toujours sélectionnée
  And le défilement est retrouvé

Scénario: Parcelle sans nombre de rangs
  Given la planche-est n'a pas de nombre de rangs et porte 3 courgettes
  When je la sélectionne
  Then sa tuile de courgette est dessinée
  And aucun rang libre n'est proposé
  And le détail porte "nombre de rangs non renseigné" avec la phrase à dire au compagnon

Scénario: Sur le téléphone
  Given j'ouvre l'onglet Parcelles à 375 px
  Then la liste est un sélecteur horizontal de pastilles "nom + occupation"
  And la parcelle choisie reste visible sans écran de retour
```

**Labels GitHub :** `us`, `frontend`, `pwa`, `plan`, `design-system`

---

## ⚠️ AMENDEMENT du 24/09/2026 — la fiche parcelle ne porte plus le détail des cultures

**Origine :** maquette `Parcelle - Fiche.html` (projet Claude Design
`10f5afa7-58f8-4eb0-8dae-ca5834dfff59`), qui **fige** le niveau 2 et tranche
autrement que cette US ne l'avait écrit.

**Ce que la maquette montre :** la fiche d'une parcelle porte son en-tête, un
**bandeau d'occupation** — « 3 rangs occupés sur 7 », les cases d'occupation, les
noms des cultures présentes — et un bouton primaire **« Voir les cultures dans le
Plan → »**. Puis la carte « Caractéristiques » (US-229, US-230), la carte
« Rotation » (US-231) et la carte « Sol et entretien » (US-232). **Aucune tuile
de culture**, aucune frise des douze mois, aucune pastille de confiance, aucun
rang libre actionnable.

**Pourquoi :** la règle du zoom d'information dit qu'un niveau « ajoute ce que le
niveau précédent ne pouvait pas porter ». Dessiner les rangs aux deux niveaux
faisait exactement l'inverse : deux dessins du même objet, qu'il fallait ensuite
garantir identiques (c'était tout l'objet de CA2). La maquette retire le doublon
au lieu de le réconcilier — **le rang vit dans le Plan, la parcelle vit dans sa
fiche**. Ce que la fiche gagne à la place, c'est ce que le Plan ne peut pas
porter : les caractéristiques, la rotation, le journal du sol.

### Règles remplacées

| # | Ce qui remplace |
|---|---|
| D5 | **En-tête allégé** : le nom, une ligne d'état en teinte secondaire (« Pleine terre · sans abri · active »), et « ← Voir dans la Vue plan ». Les pastilles de superficie, dimensions, exposition, abri et paillage sont **retirées** : elles répétaient ce que la carte « Caractéristiques » dit juste en dessous, en mieux (US-229 / C2, C3) |
| D5b | **Bandeau d'occupation**, sous l'en-tête : « N rangs occupés sur M » (D11 pour le dépassement), les cases d'occupation, les noms des cultures présentes, et le bouton primaire **« Voir les cultures dans le Plan → »**. Une parcelle **libre** le dit ici ; une parcelle **sans nombre de rangs** y porte sa mention (D4) |
| D7 à D10 | **Retirés.** La tuile de culture, ses numéros de rang, sa piste, sa frise, sa pastille de confiance, ses observations de culture et le rang libre actionnable **ne sont plus rendus dans l'onglet Parcelles**. Ils vivent dans la Vue plan (US-200, US-228) et dans la fiche culture (US-206, US-207) |
| D12 | Inchangé pour l'index ; la fiche, n'ayant plus de grille de tuiles, tient à 375 px sans palier |

### Critères d'acceptance remplacés

- **CA2 est sans objet** : il n'y a plus deux dessins d'un rang à réconcilier. La
  garantie devient plus forte — il n'en existe qu'un.
- **CA4** : `TraitRang`, `RangPlan` et `PastillePhase` ne sont plus consommés par
  cet écran. Leur variante de taille reste utile à US-228 et à la fiche culture.
- **CA6** : ce qui était « conservé à l'identique » d'US-060 (compteur de
  cultures, variété, quantité avec son unité, frise, confiance, fiche calendrier
  depuis la tuile) **déménage** : les cultures et leurs quantités se lisent dans
  le Plan, la frise et la confiance dans la fiche culture. Le bandeau D5b garde
  le **nom** des cultures présentes, et rien de plus.
- **CA7 / CA9** : l'appui sur une tuile et l'appui sur un rang libre disparaissent
  avec les tuiles. Le seul chemin vers une culture depuis cette fiche est le
  bouton D5b, qui mène au Plan.
- **CA15** : la composition à couvrir par `npm test` devient celle du **bandeau**
  (occupation, cases, noms de cultures, parcelle libre, sans nombre de rangs,
  dépassement, pépinière) — plus celle d'une tuile.

### Ce qui reste vrai, et qu'il ne faut pas perdre

- **D1 à D4** (l'index, l'absence de teinte d'occupation, la pépinière, la
  parcelle sans nombre de rangs) : inchangés.
- **D6** : le pourcentage d'occupation de surface reste retiré (A20).
- **D11** : le dépassement garde sa teinte d'alerte, dans le bandeau.
- **CA11** (retour à l'état exact), **CA12** (lecture seule), **CA14** (chargement
  et échec) : inchangés.

### Point de vigilance — une régression à assumer

La frise des douze mois, la pastille de confiance et l'ouverture de la fiche
calendrier depuis une tuile **n'existent nulle part ailleurs tant qu'US-206 et
US-207 ne sont pas livrées**. Retirer les tuiles avant elles les ferait
disparaître de l'application. **Ordre de livraison imposé** : US-206 et US-207
d'abord, le retrait ensuite — ou les deux dans la même livraison. À annoncer dans
`PATCH_NOTES.md` en disant où chaque chose se lit désormais.

**Impact sur les autres US de l'épic** : US-201 / CA8 (lien « Voir la culture »
depuis une tuile de l'onglet Parcelles) devient sans objet ; US-227 et US-228
perdent leur consommateur « niveau 2 » ; US-229 / C1 se relit « entre l'en-tête
et la carte Rotation » ; US-231 et US-232 gardent leur place, la fiche ayant
désormais de la place pour elles.

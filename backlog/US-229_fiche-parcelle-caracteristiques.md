**ID :** US-229
**Titre :** Afficher la carte « Caractéristiques » de la fiche parcelle
**Épic :** ÉPIC 10 — Plan : l'occupation en rangs et le zoom d'information *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux voir d'un coup d'œil, sur la fiche d'une parcelle, tout ce que l'application sait d'elle — nom, superficie, longueur, largeur, rangs, exposition, sol, abri, paillage, pépinière, statut — et repérer immédiatement ce qui manque
Afin de savoir quoi compléter pour que le Plan, la confiance et le compte des places cessent de dégrader leur affichage

**Contexte fonctionnel :**
Maquette de référence : `Parcelle - Fiche.html` (projet Claude Design `10f5afa7-58f8-4eb0-8dae-ca5834dfff59`), carte « Caractéristiques ».

Le niveau 2 du zoom d'information (US-222) recoud les **rangs** de la parcelle sur la Vue plan. Il ne dit toujours rien de la parcelle **elle-même** : ses caractéristiques sont aujourd'hui dispersées entre des pastilles d'en-tête et rien du tout. Or trois livraisons récentes (US-197 nb de rangs, US-225 longueur, US-181 abri/paillage) ont ajouté des champs dont l'absence **dégrade visiblement** d'autres écrans — « nombre de rangs non renseigné », « longueur non renseignée », confiance abaissée. Le jardinier subit la dégradation sans jamais voir où la corriger.

Cette US pose la carte qui rassemble ces champs, en lecture, et qui nomme l'absence plutôt que de la masquer. **L'édition fait l'objet d'une US séparée** (US-230), livrée à sa suite : c'est la même carte qui bascule, pas un second écran.

⚖️ **Aucun champ nouveau, aucune migration.** Les champs affichés correspondent **un pour un** à des colonnes existantes de `parcelles` (`nom`, `superficie_m2`, `longueur_m`, `nb_rangs`, `exposition`, `type_sol`, `abri`, `paillage`, `est_pepiniere`, `actif`) et à une valeur déduite (largeur). La carte ne fait apparaître **aucune caractéristique que l'application ne sait pas déjà stocker** : pas d'orientation des rangs, pas de mode d'arrosage, pas de « type de parcelle » synthétique. Si l'un d'eux revient dans une maquette ultérieure, il fera l'objet de son US avec sa migration.

**Règles de rendu :**

| # | Règle |
|---|---|
| C1 | La carte s'intercale entre l'en-tête de la parcelle (US-222 / D5) et le bloc des rangs. Titre « Caractéristiques », bouton « Modifier » à droite |
| C2 | Champs affichés, dans cet ordre : **Nom**, **Superficie** (m²), **Longueur** (m, US-225), **Largeur** (m, suffixée « déduite »), **Nombre de rangs** (US-197), **Exposition**, **Type de sol** (US-058), **Abri** et **Paillage** (US-181), **Pépinière** (oui / non), **Statut** (active / inactive, US-009) |
| C3 | Un champ non renseigné se rend en **état manquant** : cadre en pointillés, teinte d'alerte douce, libellé « Non renseigné ». Il n'est jamais masqué, jamais remplacé par un tiret discret, jamais rempli d'une valeur de repli |
| C4 | **Paillage** et **Abri** distinguent « Non renseigné » (`NULL`) de « Non » et de « Aucun » : un jardinier qui déclare ne pas pailler dit quelque chose, et ce quelque chose ne se confond pas avec le silence (US-181) |
| C5 | La **largeur déduite** n'est affichée que si superficie *et* longueur existent ; sinon elle porte l'état manquant avec la mention « déduite de la superficie et de la longueur ». Elle n'est **jamais** présentée comme une valeur déclarée |
| C6 | **Pépinière** et **Statut** ne produisent **jamais** l'état manquant : ce sont des booléens qui ont toujours une valeur. Ils ne comptent pas non plus dans la pastille C8 |
| C7 | Sous la grille, une ligne d'aide : « Ou dites au compagnon : `type de sol argileux parcelle planche_centrale` », avec un bouton de copie. La phrase est **construite avec le nom réel de la parcelle** et, quand un seul champ manque, avec le champ manquant |
| C8 | Dans la liste de gauche (index, US-222 / D1), une **pastille discrète** signale la parcelle à compléter, avec le titre accessible « Informations à compléter ». Elle apparaît dès qu'un champ de C2 soumis à l'état manquant fait défaut, et jamais pour une seule raison esthétique |
| C9 | Parcelle **pépinière** : nombre de rangs, longueur et largeur sont **retirés de la grille**, pas rendus en état manquant — ils n'ont pas de sens ici, et leur absence ne doit pas produire la pastille C8. L'en-tête dit le type de pépinière (chaude / froide) si US-208 est livrée |
| C10 | Parcelle **inactive** : la carte est rendue entière, le Statut dit « Inactive », et la fiche le signale aussi en en-tête. Une parcelle inactive n'est pas une parcelle cassée |
| C11 | **375 px** : la grille passe à une colonne, la ligne d'aide reste sous la grille, le bouton reste visible sous le titre |

**Critères d'acceptance :**

*Lecture*
- [ ] CA1 : La carte est alimentée par la réponse déjà chargée par l'onglet Parcelles (`GET /plan`, US-222 / CA1) ; si un champ de C2 n'y figure pas, il y est **ajouté à cette réponse** — aucun appel supplémentaire n'est introduit, et changer de parcelle ne déclenche aucune requête
- [ ] CA2 : La largeur déduite est calculée par `utils.parcelles.largeur_deduite` et par elle seule ; aucune division n'est réécrite côté frontend
- [ ] CA3 : **Aucune migration n'est livrée** et aucune colonne n'est ajoutée : un test vérifie que chaque champ affiché se lit sur une colonne existante ou sur la largeur déduite

*Rendu*
- [ ] CA4 : Les règles C1 à C11 sont appliquées
- [ ] CA5 : Une parcelle dont tous les champs sont renseignés n'affiche **aucun** état manquant et **aucune** pastille dans l'index
- [ ] CA6 : Une parcelle dont tout manque affiche les états manquants attendus et reste lisible — la carte ne s'effondre pas et ne devient pas un mur rouge
- [ ] CA7 : Le rendu correspond visuellement à la maquette `Parcelle - Fiche.html` à 375 px / 768 px / desktop

*Interaction*
- [ ] CA8 : Le bouton de copie place la phrase compagnon dans le presse-papiers ; en cas d'échec ou de presse-papiers indisponible, la phrase reste sélectionnable et aucune erreur n'est affichée
- [ ] CA9 : Tant qu'US-230 n'est pas livrée, le bouton « Modifier » est rendu **désactivé** (`disabled`, `aria-disabled="true"`, hors tabulation) avec le texte accessible « La modification depuis le web arrive bientôt — dites-le au compagnon ». Aucun mode édition, aucun champ de saisie, aucun appel d'écriture n'est livré par cette US

*États*
- [ ] CA10 : Chargement et échec sont ceux de l'onglet Parcelles (US-222 / CA14), pas des variantes propres à la carte

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA, onglet Parcelles)
- Migration BDD requise : **non** — tous les champs existent déjà
- Dépendances : US-222 (structure de l'onglet), US-225 (longueur et largeur déduite), US-197 (nb de rangs), US-181 (abri, paillage), US-058 (type de sol), US-009 (statut actif)
- Suite immédiate : US-230 (édition de ces mêmes champs)
- À livrer **avant** la refonte de l'écran Cultures (US-205 à US-207)
- Corpus : `data/connaissance/doc_app/parcelles-et-plan.md` à relire (une fiche parcelle apparaît, les champs manquants deviennent visibles)

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given la parcelle "planche_centrale" a une superficie, une longueur et 7 rangs, mais pas de type de sol
When j'ouvre sa fiche dans l'onglet Parcelles
Then la carte "Caractéristiques" affiche sa largeur déduite, suffixée "déduite"
And le champ "Type de sol" est rendu en état manquant "Non renseigné"
And la liste de gauche porte la pastille "Informations à compléter" sur cette parcelle

Given la parcelle "planche_salade" n'a jamais eu de paillage déclaré
When j'ouvre sa fiche
Then le champ "Paillage" dit "Non renseigné", et non "Non"
```

**Labels GitHub :** `us`, `sprint-X`, `frontend`, `parcelles`

---

## ⚠️ AMENDEMENT du 24/09/2026 — la fiche parcelle ne porte plus le détail des cultures

Origine : maquette `Parcelle - Fiche.html`, détaillée dans l'amendement de
**US-222**, qui fait foi. La fiche d'une parcelle porte désormais un simple
**bandeau d'occupation** (« N rangs occupés sur M », les noms des cultures) et
un bouton « Voir les cultures dans le Plan → » : plus aucune tuile de culture,
plus aucun rang libre actionnable.

- **C1 se relit** : la carte « Caractéristiques » s'intercale entre l'en-tête
  (bandeau d'occupation compris) et la carte « Rotation » (US-231) — il n'y a
  plus de « bloc des rangs » sous elle.
- **CA9 est levé** : US-230 est livrée, le bouton « Modifier » n'est plus rendu
  désactivé. Il bascule la carte en édition sur place, et n'est pas rendu du
  tout pour un membre en lecture seule (US-230 / E10).
- Le reste de l'US est **inchangé** : les onze champs, l'état manquant, la
  distinction entre `NULL`, « Non » et « Aucun », la largeur déduite, la pastille
  de l'index et la phrase à dire au compagnon.

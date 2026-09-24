**ID :** US-231
**Titre :** Afficher la rotation d'une parcelle année par année sur sa fiche
**Épic :** ÉPIC 10 — Plan : l'occupation en rangs et le zoom d'information *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux voir sur la fiche d'une parcelle quelles familles botaniques s'y sont succédé, année par année, et ce qui est conseillé pour l'an prochain
Afin de décider où planter sans avoir à me souvenir de trois saisons, et de voir venir une répétition avant de la commettre

**Contexte fonctionnel :**
Maquette de référence : `Parcelle - Fiche.html`, carte « Rotation ».

L'application **sait déjà** évaluer une rotation : `app/services/rotation.py` (US-163) rend un statut — conflit, délai respecté, aucun antécédent, indisponible — et `app/services/avertissements_plantation.py` l'utilise au moment du geste. Mais ce savoir n'existe qu'**à l'instant où l'on plante** : rien ne le donne à lire posément, à froid, quand on prépare la saison.

Cette US rend visible l'historique que le service parcourt déjà : une colonne par campagne, la ou les familles botaniques qui ont occupé la parcelle cette année-là, et une dernière colonne — l'année à venir — qui porte le conseil.

⚖️ **Honnêteté avant complétude (Épic 5 §4, rappel d'US-163 / CA7-CA8).** Une famille inconnue (`famille_id` NULL) se dit « Famille non renseignée », jamais « Autres » silencieux ni une famille devinée. Une année sans donnée se dit vide, elle ne se saute pas. Le conseil de l'année à venir n'est rendu que si le référentiel permet de le formuler ; sinon la colonne dit ce qui manque.

**Règles de rendu :**

| # | Règle |
|---|---|
| R1 | La carte s'intitule « Rotation ». Elle affiche **quatre colonnes** : les trois campagnes précédant la campagne à venir, puis la campagne à venir. Une colonne = une année, l'année en tête |
| R2 | Une colonne porte **une vignette par famille** ayant occupé la parcelle cette année-là : nom de la famille en gras, cultures concernées en dessous. Plusieurs familles la même année = plusieurs vignettes empilées |
| R3 | Chaque famille a une **teinte propre et stable** dans toute l'application : la même famille garde la même couleur d'une parcelle à l'autre et d'une année à l'autre. La teinte ne dit **jamais** un jugement (bon / mauvais) — elle n'identifie que la famille (RT4) |
| R4 | La colonne de l'**année à venir** est en pointillés, libellée « Conseillé », et porte les familles compatibles au regard du délai de retour du référentiel (US-163) |
| R5 | **Alerte de répétition** sous la grille, en teinte d'alerte : « Solanacées deux années de suite sur cette parcelle. À éviter en 2027. » Elle nomme la famille, le nombre d'années et l'année à éviter. Une seule alerte par famille en cause |
| R6 | **Aucun antécédent** : la carte le dit en une phrase (« Aucune culture enregistrée sur cette parcelle avant 2026 ») et garde la colonne de conseil si elle est formulable |
| R7 | **Référentiel indisponible** pour une culture : sa vignette dit « Famille non renseignée » et cette culture est **exclue** du calcul de l'alerte et du conseil — l'absence ne produit pas un faux « tout va bien ». La carte le signale en une ligne |
| R8 | Parcelle **pépinière** : la carte n'est pas rendue. Une rotation n'a pas de sens sur un emplacement de godets |
| R9 | **375 px** : les quatre colonnes deviennent quatre lignes empilées, l'année en tête de ligne ; l'alerte reste sous la grille |

**Critères d'acceptance :**

*Calcul*
- [x] CA1 : L'historique et le conseil sont produits par `app/services/rotation.py` — étendu si nécessaire, **jamais dupliqué** côté frontend ni réécrit dans un autre service. Un test vérifie que la carte et l'avertissement de plantation (US-163) disent la **même chose** pour la même parcelle et la même famille
- [x] CA2 : L'historique se lit sur les événements de plantation et de semis en pleine terre rattachés à la parcelle, par campagne ; les bulletins météo automatiques en sont exclus, comme `evaluer_rotation` le fait déjà
- [x] CA3 : Le service expose ces quatre années par une lecture **unique**, servie avec l'onglet Parcelles ; changer de parcelle ne déclenche aucune requête supplémentaire (RT6)

*Rendu*
- [x] CA4 : Les règles R1 à R9 sont appliquées
- [x] CA5 : Une culture dont la famille est inconnue apparaît dans sa colonne avec la mention prévue, sans être comptée dans l'alerte ni dans le conseil (R7)
- [x] CA6 : Le rendu correspond visuellement à la maquette `Parcelle - Fiche.html` à 375 px / 768 px / desktop

*Interaction*
- [x] CA7 : Un appui sur une vignette de famille ouvre la **fiche culture** (US-207) de la culture nommée, ou, si la vignette en porte plusieurs, les propose
- [x] CA8 : La carte est en **lecture seule** : aucun geste n'y est déclenché, aucune écriture n'y a lieu. Un membre en lecture seule la voit à l'identique

*États*
- [x] CA9 : Parcelle sans antécédent, parcelle avec une seule année, parcelle avec deux familles la même année, parcelle en répétition sur trois ans : les quatre cas sont couverts par des tests
- [x] CA10 : Chargement et échec sont ceux de l'onglet Parcelles (US-222 / CA14)

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA, onglet Parcelles) + analyse (service rotation)
- Migration BDD requise : non
- Dépendances : US-163 (évaluation de rotation et familles botaniques), US-222 (structure de l'onglet), US-207 (fiche culture, pour CA7 — dégrader proprement si non livrée)
- À livrer **avant** la refonte de l'écran Cultures (US-205 à US-207)
- Corpus : `data/connaissance/doc_app/parcelles-et-plan.md` — la rotation devient consultable en dehors du geste

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Given la parcelle "planche_centrale" a porté des Solanacées en 2025 et en 2026
When j'ouvre sa fiche dans l'onglet Parcelles
Then la carte Rotation montre 2024, 2025, 2026 et la colonne conseillée 2027
And une alerte annonce "Solanacées deux années de suite sur cette parcelle. À éviter en 2027."

Given une culture de la parcelle n'a pas de famille botanique renseignée
When la carte Rotation est rendue
Then sa vignette dit "Famille non renseignée"
And elle n'entre ni dans l'alerte de répétition ni dans le conseil de l'année à venir
```

**Labels GitHub :** `us`, `sprint-X`, `frontend`, `parcelles`, `rotation`

---

## ⚠️ AMENDEMENT du 24/09/2026 — la fiche parcelle ne porte plus le détail des cultures

Origine : maquette `Parcelle - Fiche.html`, détaillée dans l'amendement de
**US-222**, qui fait foi. La fiche d'une parcelle porte désormais un simple
**bandeau d'occupation** (« N rangs occupés sur M », les noms des cultures) et
un bouton « Voir les cultures dans le Plan → » : plus aucune tuile de culture,
plus aucun rang libre actionnable.

- La carte « Rotation » se place désormais **juste après** la carte
  « Caractéristiques », dans la colonne de deux cartes que la maquette pose
  avec « Sol et entretien » (US-232). La fiche a la place de les porter
  précisément parce qu'elle a perdu ses tuiles.
- Les dépendances à US-222 portent sur la **structure de l'onglet** (index,
  chargement, échec, retour à l'état exact), toutes conservées par l'amendement.

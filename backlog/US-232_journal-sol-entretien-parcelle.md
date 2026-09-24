**ID :** US-232
**Titre :** Tenir le journal du sol et de l'entretien d'une parcelle
**Épic :** ÉPIC 10 — Plan : l'occupation en rangs et le zoom d'information *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux retrouver sur la fiche d'une parcelle ce que j'ai apporté à son sol — paillage, compost, engrais vert, amendement, travail du sol — dans l'ordre du temps
Afin de savoir ce qui a déjà été fait sur cette planche sans relire tout mon journal, et de ne pas amender deux fois la même saison

**Contexte fonctionnel :**
Maquette de référence : `Parcelle - Fiche.html`, carte « Sol et entretien ».

Ces gestes sont **déjà enregistrés** : un paillage, un apport de compost, un semis d'engrais vert sont des événements rattachés à une parcelle. Mais ils se noient dans un journal trié par date, toutes parcelles et toutes cultures confondues. La question du jardinier n'est pas « qu'ai-je fait le 12 septembre », c'est « qu'ai-je apporté à **cette planche** ».

Cette US n'invente aucun enregistrement : elle **filtre et regroupe** ce qui existe, à l'échelle de la parcelle, et pose l'endroit d'où en ajouter un.

⚖️ **Pas de nouveau type de geste.** Si une catégorie de la maquette (engrais vert, amendement, travail du sol) n'a pas de correspondance parmi les gestes reconnus aujourd'hui, l'US **ne la crée pas** : elle est listée à la livraison comme manquante, et fait l'objet d'une US à part. La carte affiche ce que l'application sait enregistrer, ni plus ni moins.

**Règles de rendu :**

| # | Règle |
|---|---|
| S1 | Carte « Sol et entretien », en regard de la carte Rotation. Titre à gauche, bouton « Ajouter » à droite |
| S2 | Une ligne = une intervention : **date à gauche** (jour et mois ; l'année n'apparaît que si l'intervention n'est pas de la campagne en cours), libellé à droite. Ordre **antéchronologique** |
| S3 | Le libellé reprend le geste tel qu'il a été enregistré, avec sa précision quand elle existe : « Paillage de tonte sur R1 à R3 », « Compost mûr, 2 brouettes ». Le **rang** est mentionné quand l'événement en porte un |
| S4 | Les gestes retenus sont ceux qui portent sur le **sol de la parcelle**, jamais sur une culture : un semis, une plantation ou une récolte n'apparaissent pas ici — ils sont dans les rangs et dans les fiches culture |
| S5 | La carte affiche les **huit dernières** interventions, avec un lien « Tout voir » ouvrant le Journal (US-039) **filtré sur cette parcelle et sur ces gestes** |
| S6 | **Aucune intervention** : la carte le dit (« Rien d'enregistré sur le sol de cette parcelle ») et garde la ligne d'aide S7 ; elle n'est pas masquée |
| S7 | Ligne d'aide sous la liste : « Ou dites au compagnon : `paillage parcelle planche_centrale` », construite avec le nom réel de la parcelle, avec bouton de copie (même composant qu'US-229 / C5) |
| S8 | **375 px** : la date passe au-dessus du libellé, la carte s'empile sous la carte Rotation |

**Critères d'acceptance :**

*Lecture*
- [ ] CA1 : La liste est produite par un service existant d'`app/services/` filtrant les événements de la parcelle sur les gestes de sol ; aucun `db.query` hors `app/services/` (test US-041)
- [ ] CA2 : La liste des gestes considérés comme « sol et entretien » est **définie en un seul endroit**, partagée entre la carte et le filtre du Journal (S5) — les deux ne peuvent pas diverger, un test le vérifie
- [ ] CA3 : Elle est servie avec l'onglet Parcelles ; changer de parcelle ne déclenche aucune requête supplémentaire (RT6)

*Rendu*
- [ ] CA4 : Les règles S1 à S8 sont appliquées
- [ ] CA5 : Un semis, une plantation et une récolte sur la parcelle **n'apparaissent pas** dans la carte — un test le vérifie explicitement (S4)
- [ ] CA6 : Le rendu correspond visuellement à la maquette `Parcelle - Fiche.html` à 375 px / 768 px / desktop

*Interaction*
- [ ] CA7 : « Ajouter » **prépare un geste** avec la parcelle en contexte (US-196) et ne l'écrit pas depuis la PWA ; le jardinier confirme auprès du compagnon
- [ ] CA8 : « Tout voir » ouvre le Journal filtré sur cette parcelle et ces gestes, et revenir en arrière rend l'onglet Parcelles dans son état exact (US-195, US-222 / CA11)
- [ ] CA9 : Un membre en **lecture seule** voit la liste entière, sans le bouton « Ajouter »

*États*
- [ ] CA10 : Parcelle sans aucune intervention, parcelle avec une seule, parcelle avec plus de huit (le lien « Tout voir » apparaît) : les trois cas sont couverts
- [ ] CA11 : Chargement et échec sont ceux de l'onglet Parcelles (US-222 / CA14)

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA, onglet Parcelles) + enregistrement (préparation de geste)
- Migration BDD requise : non
- Dépendances : US-039 (journal et observations), US-196 (geste pré-rempli), US-222 (structure de l'onglet), US-229 (composant de ligne d'aide et de copie)
- À livrer **avant** la refonte de l'écran Cultures (US-205 à US-207)
- Livrable annexe attendu : la liste des gestes de sol de la maquette **sans équivalent** aujourd'hui, pour arbitrage produit

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given j'ai enregistré un paillage sur R1 à R3 et un apport de compost sur "planche_centrale", ainsi qu'un semis de tomate
When j'ouvre sa fiche dans l'onglet Parcelles
Then la carte "Sol et entretien" liste le paillage et le compost, du plus récent au plus ancien
And le semis de tomate n'y figure pas

Given la parcelle "tubercule" n'a aucune intervention de sol enregistrée
When j'ouvre sa fiche
Then la carte dit "Rien d'enregistré sur le sol de cette parcelle"
And la phrase à dire au compagnon reste proposée avec le nom "tubercule"
```

**Labels GitHub :** `us`, `sprint-X`, `frontend`, `parcelles`, `journal`

---

## ⚠️ AMENDEMENT du 24/09/2026 — la fiche parcelle ne porte plus le détail des cultures

Origine : maquette `Parcelle - Fiche.html`, détaillée dans l'amendement de
**US-222**, qui fait foi. La fiche d'une parcelle porte désormais un simple
**bandeau d'occupation** (« N rangs occupés sur M », les noms des cultures) et
un bouton « Voir les cultures dans le Plan → » : plus aucune tuile de culture,
plus aucun rang libre actionnable.

- La carte « Sol et entretien » se place **à côté** de la carte « Rotation »
  (US-231), en fin de fiche, comme la maquette la montre. Elle empile sous
  768 px.
- Les dépendances à US-222 portent sur la **structure de l'onglet** (index,
  chargement, échec, retour à l'état exact), toutes conservées par l'amendement.

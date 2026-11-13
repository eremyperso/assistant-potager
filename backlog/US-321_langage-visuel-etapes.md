**ID :** US-321
**Titre :** Dessiner l'étape d'une culture avec un langage visuel commun
**Épic :** ÉPIC 19 — Plan du potager sur vue du dessus *(numéro à valider)*

**Story :**
En tant que jardinier
Je veux reconnaître d'un coup d'œil, partout dans l'application, l'étape d'une culture par sa couleur et son pictogramme
Afin qu'un rang de fèves tout juste semées ne ressemble plus à un rang de poireaux en récolte

**Contexte fonctionnel :**
Maquette de référence : `Plan - Pistes.html`, sections « Langage visuel commun », « Lire une étape » et légende du plan. Le même code sert au plan, à la liste mobile et au suivi de culture ; il **remplace les compteurs de places**.

**Règles de rendu :**

| # | Règle |
|---|---|
| V1 | Six familles de couleur franches, une par grande étape : **sable** (Semé), **vert tendre** (Levé et Planté), **vert franc** (En croissance), **jaune** (En fleur), **orange** (En récolte), **gris** (Terminé) |
| V2 | Chaque étape a son **pictogramme** (graine, levée, plant, tige, fleur, panier, coche) ; la couleur aide, le pictogramme et le libellé font foi. Le libellé s'écrit dès qu'il y a la place |
| V3 | **Plein** : étape validée. **Hachuré** (blanc à 45° et filet) : étape prévue, pas encore vue |
| V4 | **Pastille orange** : date prévue atteinte, à confirmer |
| V5 | **Gris hachuré** : culture terminée, rang à libérer |
| V6 | **Contour pointillé** : rang libre |
| V7 | L'**orange** de la récolte est la couleur la plus visible du plan |
| V8 | Lisible en niveaux de gris : plein, hachuré, pointillé et pictogramme suffisent à distinguer les états |

**Critères d'acceptance :**
- [ ] CA1 : Un composant de design system dessine une étiquette d'étape (pictogramme + libellé, variante « prévu ») et un segment d'étape (plein, hachuré, pastille, gris à libérer, libre), consommés par toutes les vues de l'épic
- [ ] CA2 : Les sept couleurs et les trames sont des tokens du design system avec leur variante sombre ; aucun hexadécimal dans un composant d'écran
- [ ] CA3 : Les pictogrammes sont des SVG monochromes teintés par `currentColor`, jamais des emoji ; l'emoji de culture reste un repère à côté, pas un état
- [ ] CA4 : Une **légende** réutilisable liste les sept étapes puis « hachuré : prévu, à confirmer », « à confirmer aujourd'hui », « rang libre », dans l'ordre de la maquette ; la version mobile est compacte (six étapes, Levé et Planté fusionnés)
- [ ] CA5 : Contrastes AA du pictogramme et du libellé sur chaque couleur, dans les deux thèmes
- [ ] CA6 : La correspondance étape → couleur, pictogramme, libellé est une table de présentation isolée dans `frontend/src/lib/`, couverte par `npm test`
- [ ] CA7 : Une page de contrôle visuel rejoue les sept étapes, pleines et prévues, la pastille, le gris à libérer et le rang libre
- [ ] CA type : Le rendu correspond visuellement à la maquette de référence à 375 px / 768 px / desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA, design system)
- Migration BDD requise : non
- Dépendances : US-320 (les étapes) pour être branché sur des données réelles ; le composant se livre seul sur la page de contrôle
- `PastillePhase` (US-194) reste en place pour les écrans qui ne passent pas aux étapes (Cultures), jusqu'à leur bascule
- Modèle / effort conseillé : Sonnet 5.5, `medium`

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Une levée prévue à confirmer
  Given la fève est à l'étape Levé, prévue, date atteinte
  When je regarde son segment
  Then il est vert tendre hachuré, avec le pictogramme de levée
  And il porte la pastille orange "à confirmer"

Scénario: Lecture en niveaux de gris
  Given l'écran est affiché en niveaux de gris
  Then une étape prévue, une étape validée, un rang à libérer et un rang libre restent distinguables
```

**Labels GitHub :** `us`, `frontend`, `pwa`, `design-system`, `plan`

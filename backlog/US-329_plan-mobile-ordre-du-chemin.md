**ID :** US-329
**Titre :** Parcourir le plan sur mobile dans l'ordre du chemin
**Épic :** ÉPIC 19 — Plan du potager sur vue du dessus *(numéro à valider)*

**Story :**
En tant que jardinier au potager, téléphone en main
Je veux un petit plan pour me repérer et, dessous, mes parcelles dans l'ordre où je les longe, un rang par ligne
Afin de suivre mon chemin dans le jardin avec de grosses cibles, au lieu d'une grille comprimée

**Contexte fonctionnel :**
Maquette de référence : `Plan - Pistes.html`, « Mobile · Plan dans la navigation actuelle », écrans 1 et 2. Plus d'onglets « Tournée » et « Plan » : **un seul écran**.

**Contenu :**

| # | Bloc | Contenu |
|---|---|---|
| M1 | Barre | « Au 12 novembre · fond photo » et l'emprise |
| M2 | Mini-plan | le plan entier réduit, sans libellés ; toucher une parcelle fait défiler jusqu'à sa carte et la met en évidence |
| M3 | Légende compacte | six étapes (US-321) ; « Touchez une parcelle pour y aller · modification sur ordinateur » |
| M4 | Tâches | « N à confirmer » et « N à libérer » (US-328) |
| M5 | Dans l'ordre du chemin | une carte par parcelle : nom, nombre de rangs, bouton « Détail » ; puis **une ligne de 54 px par culture** : « R3 », barre d'étape avec pictogramme, emoji + nom, « En récolte depuis le 20 oct. · variété », pastille « À confirmer » ; rangs libres en ligne « Libre » |
| M6 | Pépinière | carte « pépinière froide », lien « Ma pépinière », une ligne par lot (n°, emoji, nom, variété, quantité, stade) vers sa fiche ; « Les lots se suivent et se notent dans Ma pépinière » |

**Règles :**
- L'**ordre du chemin** est l'ordre des parcelles déclaré par le jardinier (`ordre`, réordonnable selon US-202) — arbitrage **P6**
- Toucher une ligne de culture ouvre sa feuille de suivi (US-322) ; « Détail » ouvre la parcelle (US-330)
- Pas de modification du plan sur mobile

**Critères d'acceptance :**
- [ ] CA1 : Sous 720 px de conteneur, l'écran Plan affiche M1 à M6 dans cet ordre ; au-dessus, le plan d'ordinateur (US-327) — container queries, jamais de breakpoint d'écran
- [ ] CA2 : Le mini-plan réutilise le rendu d'US-327 en variante réduite, sans second dessin
- [ ] CA3 : Les lignes de culture font au moins 54 px, sans défilement horizontal à 375 px, libellés longs compris
- [ ] CA4 : Une parcelle non placée apparaît dans la liste à son rang d'ordre, mais pas sur le mini-plan
- [ ] CA5 : Le défilement jusqu'à une parcelle porte le focus sur sa carte et l'annonce aux lecteurs d'écran
- [ ] CA6 : L'écran mobile se relit une fois au retour de Gaston (US-324) : la ligne confirmée passe du hachuré au plein
- [ ] CA type : Le rendu correspond visuellement à la maquette de référence à 375 px ; vérification chrome-devtools à 375 px

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA mobile)
- Migration BDD requise : non
- Dépendances : **US-321**, **US-322**, **US-327**, **US-328** ; US-202 (réordonner les parcelles) si l'ordre doit se régler depuis la PWA
- Modèle / effort conseillé : Sonnet 5.5, `medium`

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Aller à la planche centrale
  Given je suis sur le Plan, sur mobile
  When je touche la planche centrale sur le mini-plan
  Then la liste défile jusqu'à sa carte
  And chaque culture y occupe une ligne "R1 … R8"

Scénario: Une pépinière dans le chemin
  Given le châssis est une pépinière froide avec trois lots
  When j'arrive à sa carte
  Then je vois ses trois lots et le lien "Ma pépinière"
  And aucun lot n'a de bouton Noter
```

**Labels GitHub :** `us`, `frontend`, `pwa`, `plan`, `mobile`

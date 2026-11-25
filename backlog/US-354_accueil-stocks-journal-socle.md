**ID :** US-354
**Titre :** Passer le Tableau de bord, les Stocks (avec Récoltes par saison) et le Journal sur le socle
**Épic :** ÉPIC 21 — Socle commun des vues

**Story :**
En tant que jardinier
Je veux un tableau de bord qui me dit quoi faire aujourd'hui, des stocks qui comparent mes saisons et un journal qui regroupe mes notes du jour
Afin de répondre en un écran à « que faire ? », « qu'ai-je ? » et « qu'est-il arrivé ? »

**Contexte fonctionnel :**
Vague 2 de l'ÉPIC 21, en parallèle d'US-355, US-356 et US-357. La référence est la maquette (Mobile : Tableau de bord, Stocks, Journal, Récoltes par saison ; Ordinateur).
Ce sont trois vues de listes qui partagent les mêmes pièces (ligne de culture avec pastille, note du carnet, groupe titré). Toutes les lectures existent : tâches du plan (`aujourdhui.js`, US-328), météo, `GET /historique`, stocks, `GET /stats/rendement?annee=`.

**Critères d'acceptance :**
- [ ] CA1 : **Tableau de bord** : onglets Vue d'ensemble / Statistiques. **Aucune barre d'outils.** Deux colonnes à partir de 700 px de conteneur, sinon une :
  - « À faire aujourd'hui · n » : levées dues, rangs à libérer, gestes dus
  - « Récoltes possibles · n » avec « Tout voir » (vers Cultures) et l'emplacement en sous-titre
  - « Météo · 3 jours », le jour de gel en ambre
  - « Dernières notes du carnet » : deux notes en Kalam et le lien « Journal »
- [ ] CA2 : Aucune section n'affiche de placeholder : une section vide disparaît. **Le Tableau de bord est figé sur les quatre sections de la maquette** (D11) : la personnalisation (`ModalPersonnaliserDashboard`, `useDashboardWidgets`, conseil du jour d'US-078 et autres widgets absents de la maquette) est retirée, ainsi que ses tests devenus sans objet. Les préférences de widgets déjà enregistrées sont ignorées, sans migration
- [ ] CA3 : **Mot de Gaston du Tableau de bord** : gel annoncé dans les 3 jours > levées dues > rien. Exemple : « **Gel annoncé samedi (−2 °C).** Voilez la mâche et les salades du bac vendredi soir. Deux levées attendent votre œil. » → *Voir les levées* (Cultures), *Noter le voilage* (Gaston, US-358)
- [ ] CA4 : **Stocks** : quatre chiffres en Lora 20 px (unités au potager, godets à replanter, **kg récoltés dans l'année**, unités perdues). La tuile des kg est un bouton orangé avec « Comparer les saisons › ». Cartes par famille botanique (« Alliacées · 3 cultures »), chaque ligne avec petite pastille d'étape, nom, variété, quantité et unité (« 60 · 4,1 kg — en terre · récolté »). Le regroupement par famille et l'ordre alphabétique passent dans **Filtrer**, et les exports CSV/JSON existants dans **⋯**
- [ ] CA5 : **Récoltes par saison** (feuille sur mobile, panneau droit sur ordinateur) : « Saison 2026 : du 1er janvier au 23 novembre », une barre par année qui a des récoltes (proportionnelle au maximum), un appui sur une année affiche ses cultures en barres (« Pomme de terre 21,0 kg », reste en « Autres »), et la mention « Le détail mois par mois reste dans Tableau de bord › Statistiques ». Les données viennent de `GET /stats/rendement` (une lecture par année, aucune route nouvelle). Les récoltes en pièces ne sont jamais converties en kg (US-036, INC-008)
- [ ] CA6 : **Mot de Gaston des Stocks** : godets à replanter qui attendent depuis plus de 3 semaines et rang libre disponible → « **14 godets de chou pommé** attendent une place depuis 4 semaines. Le rang 3 de la serre se libère : je l'y propose ? » → *Oui, proposer* (Gaston)
- [ ] CA7 : **Journal** : jours en capitales (« AUJOURD'HUI · 23 NOVEMBRE »). Dans un jour, les notes sont **regroupées en « n notes »** : la première en Kalam avec sa culture et sa parcelle, puis « + n autres » qui déplie. Les notes sans texte sont comptées (« 1 sans texte »), pas listées. Les gestes restent en ligne avec leur pastille (récolte, paillage, perte en rouge). Toucher un geste lié à une culture ouvre la fiche commune
- [ ] CA8 : **Mot de Gaston du Journal** : le bilan de la semaine, sans action (« Cette semaine : **1 récolte (1,2 kg)**, 1 paillage et 6 notes, dont 4 dictées. »)
- [ ] CA9 : Les trois vues suivent la date de la règle des temps (US-353) comme aujourd'hui
- [ ] CA type : Le rendu correspond visuellement à la maquette de référence à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non
- Dépendances : US-353 ; US-328 (Aujourd'hui au potager), US-075 (météo), US-036 (rendement) ; retire la personnalisation d'US-078
- Modèle / effort conseillé : **Sonnet 5.5, `medium`** — trois vues de liste sur des lectures existantes ; ni Opus ni Fable ne sont requis

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Given un gel à −2 °C est annoncé samedi et deux levées sont dues
When le jardinier ouvre le Tableau de bord
Then le Mot de Gaston annonce le gel et les deux levées
And "À faire aujourd'hui · 3" liste la fève, l'épinard et le rang 3 de la serre à libérer

Given 31,2 kg récoltés en 2024, 52,8 kg en 2025 et 44,7 kg en 2026
When le jardinier touche la tuile "44,7 kg récoltés en 2026" dans Stocks
Then la comparaison des saisons s'ouvre avec trois barres
When il touche 2025
Then la tomate apparaît en tête avec 18,4 kg

Given trois notes aujourd'hui, dont une sans texte
When le jardinier ouvre le Journal
Then il voit "3 notes", la première en Kalam, "1 sans texte" et "+ 1 autre"
```

**Labels GitHub :** `us`, `frontend`, `pwa`, `dashboard`, `stocks`, `journal`, `socle`

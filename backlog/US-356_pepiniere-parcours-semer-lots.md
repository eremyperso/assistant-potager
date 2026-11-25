**ID :** US-356
**Titre :** Passer la Pépinière sur le socle : Parcours, Semer, Lots et fiche du lot
**Épic :** ÉPIC 21 — Socle commun des vues

**Story :**
En tant que jardinier
Je veux une pépinière en trois onglets : où en sont mes plants, quoi semer maintenant, et le registre de mes lots. Sur mobile, je veux les parcourir un stade ou un filtre à la fois
Afin de savoir quoi semer, repiquer ou ranger sans tableau trop large pour mon téléphone

**Contexte fonctionnel :**
Vague 2 de l'ÉPIC 21. La référence est la **version 2** de la maquette (Pépinière · Parcours, Pépinière · Semer, Pépinière · Lots), décrite au §2 de `docs/EPIC 21 - SOCLE COMMUN DES VUES/01_ANALYSE.md` (décision D8).
Les fonctions existent : Parcours (US-218, `OngletParcours`, kanban emplacement × stade, bande « Le bon moment pour semer »), Lots (US-242, `OngletLots`, filtres En cours / À régler / Terminés) et la fiche du lot (US-216, `FicheLot`). Cette US les pose sur le socle et isole la bande des semis dans son propre onglet.
Les stades de la pépinière sont **En levée, En godet, Endurcissement, Prêt à sortir**. Ils restent distincts des étapes d'une culture en place et se lisent par la correspondance d'US-352 CA2b.

**Critères d'acceptance :**
- [ ] CA1 : **En-tête** : « Ma pépinière », trois onglets d'en-tête **Parcours**, **Semer · n**, **Lots · n** (tuiles sur ordinateur, pastilles sur mobile). La ligne de contexte change avec l'onglet : « Châssis froid et serre chaude, lot par lot », « Le bon moment pour semer », « Le registre de la saison, lot par lot ». Les adresses existantes (`#lot-…`, liens du Plan vers un lot, US-201 / I5) ouvrent le bon onglet
- [ ] CA2 : **Parcours, sur ordinateur** : une **matrice emplacement × stade**. En lignes : Serre chaude (« pépinière chaude », teinte chaude), Châssis froid (« pépinière froide », teinte froide), Sans emplacement (« à ranger », hachuré). En colonnes : En levée, En godet, Endurcissement, Prêt à sortir, chacune titrée par sa petite pastille et son compte. Le titre de section est « Le parcours du plant · emplacement × stade »
- [ ] CA3 : **Parcours, sur mobile** : **un stade à la fois**, défilement horizontal aimanté. Dans la colonne, les lots sont groupés par emplacement (« ■ SERRE CHAUDE · 2 », avec la couleur de l'emplacement). Les points de stade (le courant allongé en vert) et le libellé « En godet · 4 » suivent le défilement, et toucher un point y va
- [ ] CA4 : **Carte de lot** : emoji, nom, « #57 », « variété · quantité · semé le 20 oct. ». Elle porte aussi une **alerte orange** si le lot est à régler (« Pas levé après 34 j », « Sans emplacement ») et la note du jardinier en Kalam. Les mentions « Durée ? » ne s'affichent plus sur les cartes
- [ ] CA5 : **Mot de Gaston du Parcours** : lots à régler (pas de levée après le délai, sans emplacement, quantité non dite) → « **2 lots à régler** : l'oignon blanc n'a pas levé après 34 jours, le chou-fleur attend un emplacement. » → *Ranger le chou-fleur* (Gaston), *Voir les lots* (onglet Lots, filtre À régler)
- [ ] CA6 : **Semer**, trois groupes :
  - « **Fenêtre ouverte · n** » avec le critère « Fenêtre de semis ouverte · graines en stock · aucun lot de la culture en cours ». Une tuile par culture : nom en Lora, « reste 7 j » en orange, barre de la part de fenêtre écoulée, « 1 sept. → 30 nov. · pépinière froide », variétés, bouton **Semer** (qui ouvre Gaston, US-358). Grille de trois colonnes à partir de 700 px de conteneur
  - « **Fenêtre ouverte, mais rien à semer · n** » : la culture et son motif (« Graines épuisées : à racheter », « Un lot est déjà en cours (#59) »)
  - « **Bientôt** » : les prochaines ouvertures (« Poireau d'été · Carentan — semis en pépinière froide à partir du 7 janv. — dans 45 j »)
- [ ] CA7 : **Données de Semer** : les fenêtres ouvertes, leurs jours restants et leur part écoulée viennent déjà de la lecture du parcours (`a_semer`, US-240). Deux champs **en lecture** y sont ajoutés dans `echeances_lots`, sans migration ni route nouvelle :
  - les cultures **écartées** avec leur motif (`lot_en_cours` avec le n° du lot ; `graines_epuisees` quand le stock de graines du potager est connu et nul)
  - **plusieurs** prochaines ouvertures (à partir de `_calendrier_semis`)

  Aucune fenêtre n'est recalculée côté front (RT6). Un motif non calculable n'est pas affiché
- [ ] CA8 : **Mot de Gaston de Semer** : « **3 cultures sont dans leur fenêtre** et vous avez les graines. L'oignon blanc ferme dans 7 jours. » → *Semer l'oignon blanc* (Gaston). S'il n'y a aucune fenêtre ouverte, le mot annonce la prochaine ouverture
- [ ] CA9 : **Lots** : le bilan de la saison (« **18 lots** cette saison · **14** en cours dont 2 à régler · **4** terminés, 34 plants sortis vers le potager »), puis les filtres En cours / À régler / Terminés / Tous avec leurs comptes. Sur ordinateur, ce sont des boutons segmentés sous la barre d'outils. Sur mobile, ce sont **les mêmes points que le Parcours**, et chaque filtre est une colonne aimantée. Les lots sont groupés par mois de semis (« Semés en novembre · 4 »). Une ligne montre le n°, la pastille de stade, culture · variété, emplacement · quantité · date, la **frise des gestes datés** et l'alerte. En bas : « Registre sans geste : on agit depuis le Parcours ou par Noter »
- [ ] CA10 : **Mot de Gaston des Lots** : les lots à régler, avec *Voir les lots à régler* (applique le filtre ; pas d'action sur mobile, où le filtre est un point)
- [ ] CA11 : **Fiche du lot**, au format de la fiche commune (feuille sur mobile, panneau droit sur ordinateur) : « Lot #57 · Oignon blanc », variété · quantité, stade en puce, emplacement et son type, alerte, **Noter** (Gaston sur ce lot, US-358) et **Voir au Parcours**, « Gestes datés » en frise, « Carnet du lot » en Kalam. Les fonctions de `FicheLot` (US-216) restent joignables depuis cette fiche
- [ ] CA12 : Les trois onglets suivent la date de la règle des temps (US-353) comme aujourd'hui (`date_ref`)
- [ ] CA type : Le rendu correspond visuellement à la maquette de référence à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non
- Dépendances : US-353 ; US-218 (parcours), US-240 (bornes de fenêtre), US-242 (lots), US-216 (fiche lot), US-212 (graines restantes)
- Modèle / effort conseillé : **Sonnet 5.5, `medium`** — habillage de trois onglets existants et deux champs de lecture ajoutés à un service déjà testé ; ni Opus ni Fable ne sont requis

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Given 4 lots en godet, dont 2 en serre chaude et 2 au châssis froid
When le jardinier ouvre Ma pépinière › Parcours sur mobile et glisse jusqu'au deuxième point
Then il voit la seule colonne "En godet · 4"
And les lots y sont groupés sous "Serre chaude · 2" et "Châssis froid · 2"

Given la fenêtre de l'oignon blanc ferme le 30 novembre et un lot de laitue Reine de mai (#59) est en cours
When le jardinier ouvre l'onglet Semer le 23 novembre
Then l'oignon blanc est dans "Fenêtre ouverte" avec "reste 7 j" et un bouton Semer
And la laitue est dans "Fenêtre ouverte, mais rien à semer" avec "Un lot est déjà en cours (#59)"

Given 2 lots à régler parmi 18
When le jardinier ouvre l'onglet Lots sur ordinateur et touche "À régler 2"
Then seuls les deux lots s'affichent, groupés par mois de semis, chacun avec son alerte
```

**Labels GitHub :** `us`, `frontend`, `backend`, `pwa`, `pepiniere`, `socle`

**ID :** US-353
**Titre :** Poser la coquille commune : bandeau, en-tête, Mot de Gaston, barre d'outils, règle des temps, Noter rond, panneau droit
**Épic :** ÉPIC 21 — Socle commun des vues

**Story :**
En tant que jardinier
Je veux que chaque écran soit construit de la même façon (en-tête, mot de Gaston, barre d'outils, contenu) et n'avoir qu'un bouton, Noter, pour parler à Gaston
Afin de savoir toujours où je suis, où chercher et comment noter, sans réapprendre chaque vue

**Contexte fonctionnel :**
Vague 1 de l'ÉPIC 21, après US-352. La référence est la maquette, sections « L'anatomie commune d'une page » et « Savoir où l'on est ».
Cette US pose la coquille et ses composants vides de contenu propre. Chaque US de vue (US-354, US-355, US-356, US-360) y branche son contenu et la règle de son Mot de Gaston. Le bouton lune du bandeau bascule le mode sombre d'US-352.
Elle est la seule de l'épic à modifier `App.jsx` et `navigation.js`.

**Critères d'acceptance :**
- [ ] CA1 : **Bandeau ordinateur** (≥ 900 px) : dégradé `#2F5416 → #4E8226`, 60 px de haut, logo, sélecteur de potager, navigation à six entrées, thème, compte. L'onglet actif est une **pastille blanche** (texte `brand-deep` en gras, icône `brand`), seule tache claire du bandeau
- [ ] CA2 : **Barre basse mobile** (< 900 px) : Accueil, Plan, **Noter** (rond de 62 px en dégradé, qui déborde de 30 px), Pépinière, Plus. L'onglet actif a une **pastille verte de 56 × 30** derrière l'icône. Quand la vue active est rangée sous « Plus » (Cultures, Stocks, Journal), ce bouton prend son nom, son icône et la pastille
- [ ] CA3 : **Noter** porte une pastille de 24 px qui montre ce qui sera noté : l'emoji de la culture sélectionnée ou ouverte, sinon le micro. Sur ordinateur, le même bouton rond se place en bas à droite (décalé à gauche du panneau quand il est ouvert), et disparaît tant que Gaston est ouvert. Le compteur de messages non lus (US-272) passe sur cette pastille
- [ ] CA4 : Le **médaillon flottant** (`BoutonCompagnon`, bulle d'accueil) est supprimé (D5)
- [ ] CA5 : **En-tête de page** : titre en Lora (25 px sur mobile, 28 px sur ordinateur) et une ligne de contexte. Les onglets de sous-vue ne s'affichent que si la section en déclare (Tableau de bord, Plan, Cultures) : tuiles de 84 × 64 sur ordinateur, pastilles compactes de 36 px sur mobile. Un onglet peut être désactivé (« Rotation · à venir »)
- [ ] CA6 : **Mot de Gaston** (composant `MotDeGaston`) : fond `brand-soft`, visage de 40 px, « Gaston · ce matin », deux phrases au plus, une à trois actions en pilules de 34 px (la principale en vert plein), × de 30 px. Une action qui écrit ouvre Gaston (US-358) ; une action qui navigue change de vue. **Sans rien à dire, le bloc n'est pas rendu.** Le × le masque pour la session et pour cette vue
- [ ] CA7 : **Le Mot de Gaston est calculé sans modèle** (D1) : une fonction pure par vue reçoit ce que la vue a déjà lu (et les signaux de `GET /compagnon/etat`) et rend `{texte, actions}` ou rien. Cette US fournit le contrat, la règle commune (priorité gel > étape due > manque de donnée) et les tests. Les US de vue écrivent les règles de leur vue. Aucun appel réseau supplémentaire
- [ ] CA8 : **Barre d'outils** (composant `BarreOutils`), toujours dans cet ordre, contrôles de 40 px : bouton date, champ de recherche (texte indicatif propre à la vue), **Filtrer** avec le compteur de filtres actifs, menu **⋯**. Sous 520 px de conteneur, Filtrer se réduit à son icône (container query). Une vue peut retirer la date ou Filtrer, rien ne s'y ajoute
- [ ] CA9 : **Menu ⋯** (`MenuVue`) : Exporter en CSV, Exporter en JSON, un séparateur, Aide de la vue. Chaque entrée n'apparaît que si la vue la fournit. « Pièces jointes » est supprimé pour l'instant (D10)
- [ ] CA10 : **Bouton date et règle des temps** : « Aujourd'hui » ouvre `RegleTemps` **juste sous la barre d'outils**, dans toutes les vues. Quand on regarde un autre jour, le bouton passe en ambre avec la date courte (« 12 nov. »). La règle a la tête de la maquette (date longue en police système 14 px sur une ligne, « il y a 11 j », « Aujourd'hui », ×), ‹ ›, le glissé avec inertie, la molette, ← → (Maj = 7 jours) et « toucher un mois ». `DateRefPicker` et `BarreActivitePlan` sont retirés (D3)
- [ ] CA11 : **Défilement** : seule la bande de contenu défile ; l'en-tête, le Mot de Gaston et la barre d'outils restent fixes. Au-delà de 8 px de défilement, l'en-tête se resserre (titre en 18 px, ligne de contexte masquée, tuiles masquées sur ordinateur) et le Mot de Gaston tient sur une ligne. Un appui sur ce mot réduit remonte en haut
- [ ] CA12 : **Panneau partagé** : sur ordinateur, un panneau droit de 400 px accueille la fiche commune, la fiche catalogue, Récoltes par saison ou Gaston (un seul à la fois). Sur mobile, une feuille montante (poignée, fond assombri, appui hors feuille = fermer) ; Gaston y est en plein écran
- [ ] CA13 : Les vues non dessinées (Statistiques, Paramètres) reçoivent bandeau, en-tête et barre basse sans refonte de contenu (D6)
- [ ] CA type : Le rendu correspond visuellement à la maquette de référence à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non
- Dépendances : US-352 ; US-325 (barre basse, Noter), US-323 (contexte d'écran), US-279 (règle des temps), US-272 (non lus), US-053/US-223 (navigation à deux niveaux)
- Composants à retirer ou à vider : `BoutonCompagnon`, `DateRefPicker`, `BarreActivitePlan`, les exports en ligne de Stocks et Journal (déplacés dans ⋯ par US-354)
- Modèle / effort conseillé : **Sonnet 5.5, `high`** — refonte de la coquille partagée par chaque écran ; ni Opus ni Fable ne sont requis (ni boucle, ni chemin d'écriture)

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Given le jardinier est sur Stocks, sur mobile
Then le bouton "Plus" de la barre basse affiche "Stocks", son icône et la pastille verte
And la barre d'outils affiche dans l'ordre : Aujourd'hui, Rechercher, Filtrer, ⋯

When il touche "Aujourd'hui" puis glisse la règle de 11 jours vers le passé
Then le bouton date passe en ambre et affiche "12 nov."
And la vue se relit au 12 novembre

When il fait défiler la liste
Then l'en-tête se resserre et le Mot de Gaston tient sur une ligne

Given Gaston n'a rien à dire sur la vue Journal
Then aucun bloc "Mot de Gaston" n'est affiché, ni vide ni en attente
```

**Labels GitHub :** `us`, `frontend`, `pwa`, `navigation`, `socle`, `compagnon`

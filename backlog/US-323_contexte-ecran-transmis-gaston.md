**ID :** US-323
**Titre :** Transmettre à Gaston ce que le jardinier a sous les yeux
**Épic :** ÉPIC 19 — Plan du potager sur vue du dessus *(numéro à valider)*

**Story :**
En tant que jardinier
Je veux que Gaston sache de quelle culture ou de quelle parcelle je parle quand je l'ouvre depuis le plan
Afin de dire « feuilles du bas un peu jaunies » sans répéter « chou de Bruxelles, planche centrale, rang 3 »

**Contexte fonctionnel :**
Maquette de référence : `Plan - Pistes.html`, « Noter ouvre Gaston avec le contexte ». Le panneau du compagnon de la PWA (US-270 / US-271) ne reçoit aujourd'hui aucun contexte d'écran : chaque message part du potager entier.

**Règles :**

| # | Règle |
|---|---|
| C1 | Le contexte est, par priorité : la **culture** sélectionnée, sinon la **parcelle** sélectionnée, sinon **tout le potager** |
| C2 | Le panneau affiche une **barre de contexte** sous l'en-tête : « À propos de : 🥦 Chou de Bruxelles · Planche centrale, rang 3 », avec une croix pour le retirer |
| C3 | Sans contexte : « Tout le potager » et un bouton **« Préciser »** qui propose les parcelles du potager (hors pépinières) en pastilles |
| C4 | Le contexte part avec chaque message vers l'API du compagnon, sous forme d'identifiants (culture, parcelle, rang), jamais de texte libre reconstruit ; le serveur vérifie qu'ils appartiennent au potager actif |
| C5 | L'interprétation (agent, US-281 et suivantes) reçoit le contexte comme une **précision par défaut** : une phrase qui nomme explicitement une autre culture l'emporte |
| C6 | Une conversation libre ouverte par le visage de Gaston n'a pas de barre de contexte |

**Critères d'acceptance :**
- [ ] CA1 : Le panneau du compagnon accepte un contexte à l'ouverture et l'affiche selon C2 / C3 ; le retirer ou le préciser met à jour la barre
- [ ] CA2 : `POST` des messages du compagnon accepte un contexte optionnel (culture, parcelle, rang) ; un identifiant étranger au potager actif est refusé en 404 sans fuite d'information
- [ ] CA3 : Avec le contexte « Chou de Bruxelles, planche centrale, rang 3 », la phrase « feuilles du bas un peu jaunies » produit une note rattachée à cette culture, sans question de précision
- [ ] CA4 : Avec le même contexte, « j'ai arrosé la serre » est rattachée à la serre, pas au chou (C5)
- [ ] CA5 : Sans contexte, le comportement actuel du compagnon est inchangé — les tests du compagnon et des propositions restent verts
- [ ] CA6 : Le contexte est journalisé avec l'échange (provenance, US-306) pour pouvoir mesurer son effet
- [ ] CA7 : Une mesure sur le vrai modèle, en un seul passage au volume annoncé, n'est lancée qu'avec l'accord explicite du responsable produit
- [ ] CA type : Le rendu correspond visuellement à la maquette de référence à 375 px / 768 px / desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction compagnon (PWA)
- Migration BDD requise : non, sauf si la journalisation du contexte demande une colonne (à vérifier au démarrage)
- Dépendances : US-270 / US-271 (panneau compagnon, livrés), US-274 (cartes à confirmer, livrée), US-306 (provenance)
- Modèle / effort conseillé : **Opus 5.5, `high`** — touche la boucle de l'agent et l'interprétation ; Fable non requis

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Parler d'une culture sous les yeux
  Given le suivi du chou de Bruxelles est ouvert
  When j'ouvre Gaston par "Noter"
  Then la barre affiche "À propos de : Chou de Bruxelles · Planche centrale, rang 3"
  When je dis "feuilles du bas un peu jaunies"
  Then Gaston propose une note sur le chou de Bruxelles, à confirmer

Scénario: Retirer le contexte
  Given la barre de contexte nomme le chou de Bruxelles
  When je touche la croix
  Then la barre affiche "Tout le potager" et "Préciser"
```

**Labels GitHub :** `us`, `backend`, `frontend`, `pwa`, `compagnon`

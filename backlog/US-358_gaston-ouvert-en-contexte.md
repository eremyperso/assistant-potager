**ID :** US-358
**Titre :** Ouvrir Gaston déjà renseigné : contexte, phrase d'ouverture et suggestions sans modèle, depuis chaque porte
**Épic :** ÉPIC 21 — Socle commun des vues

**Story :**
En tant que jardinier
Je veux que Gaston s'ouvre déjà sur la culture ou l'action dont je viens, avec une phrase et des suggestions qui y correspondent
Afin de noter en un geste ce que j'ai vu, sans réexpliquer de quoi je parle

**Contexte fonctionnel :**
Vague 3 de l'ÉPIC 21, après US-355 (fiche et catalogue), US-356 (Pépinière) et US-357 (écran de Gaston). La référence est la maquette (Gaston via Noter, Ajouter une culture), et le §3.2 de `01_ANALYSE.md` décrit les trois scénarios.
**La phrase d'ouverture et les suggestions se déduisent du contexte, sans appel au modèle.** Le modèle ne répond qu'au premier message envoyé, avec le contexte d'écran d'US-323. L'ajout depuis le catalogue suit la décision D9 du 24/11.

**Critères d'acceptance :**
- [ ] CA1 : **Les portes**. Chacune ouvre Gaston avec un contexte :
  - **Noter** (barre basse ou bouton rond) : la culture sélectionnée ou ouverte, sinon aucun contexte
  - **Noter** de la fiche commune : cette culture
  - **Noter la levée** : cette culture, avec la levée due
  - **Noter** de la fiche du lot : ce lot (n°, culture, emplacement)
  - **Semer** d'une tuile de l'onglet Semer : la culture, sa variété et sa fenêtre (« Semer l'oignon blanc de Paris en pépinière froide »)
  - une **action qui écrit dans un Mot de Gaston** (« Noter le voilage », « Confirmer la fève », « Oui, proposer », « Ranger le chou-fleur », « Semer l'oignon blanc ») : son sujet et sa phrase
  - **Ajouter à mon potager** / « Ajouter le céleri-rave » : l'espèce du catalogue
  - « Une culture absente du catalogue ? Dites-la à Gaston » : aucun contexte, phrase d'ouverture d'ajout
- [ ] CA2 : **Phrase d'ouverture**, affichée comme une bulle de Gaston, **sans appel réseau** :
  - sans contexte : « Je vous écoute : une récolte, un semis, une observation, ou une culture à ajouter… »
  - culture à étape due : « Vous êtes sur fève. Dites ce que vous voyez, ou touchez une suggestion. »
  - culture sans étape due : « Vous êtes sur chou de Bruxelles, en récolte. Une récolte, une observation ? »
  - espèce du catalogue : la phrase de l'action est **pré-écrite dans le champ** (« Ajouter le céleri-rave à mon potager »), et le jardinier l'envoie lui-même
- [ ] CA3 : **Suggestions selon le contexte** (une fonction pure testée) :

  | Contexte | Suggestions |
  |---|---|
  | aucun | Récolte, Semis, Observation |
  | étape prévue ou due | J'ai vu la levée (ou l'étape due), Pas encore |
  | en récolte | Récolte, Note |
  | terminé | Libérer le rang, Note |
  | espèce du catalogue, après la réponse de Gaston | les variétés du catalogue |

  Toucher une suggestion l'envoie comme message du jardinier (« Écrit »)
- [ ] CA4 : **« Pas encore »** sur une levée due ouvre le chemin existant du report (`POST /plan/etapes/pas-encore`, US-320) par une proposition à confirmer, jamais en écrivant directement
- [ ] CA5 : **Ajout depuis le catalogue** (D9) : Gaston répond avec la fenêtre de l'espèce, demande la variété, puis propose dans la carte « À enregistrer » le **rappel de semis** (« Rappel · semis en pépinière le 2 mars », US-345). Si une variété est donnée, la carte propose aussi l'ajout de la variété au référentiel du potager. La ligne « Nouvelle culture » n'apparaît que si une écriture correspondante existe. Rien n'est créé sans Confirmer
- [ ] CA6 : Le contexte d'une porte est celui qu'envoie déjà le contexte d'écran (US-323 : culture, parcelle, rang, vue). Une porte n'ajoute aucun champ inconnu du compagnon. Retirer le contexte (× du bandeau) le retire du message suivant
- [ ] CA7 : La pastille de Noter (US-353 CA3) et le bandeau de contexte montrent toujours la même culture (test)
- [ ] CA8 : Sur Telegram, rien ne change
- [ ] CA type : Le rendu correspond visuellement à la maquette de référence à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction (compagnon PWA)
- Migration BDD requise : non
- Dépendances : US-355, US-356, US-357 ; US-323 (contexte d'écran), US-324/US-325 (Noter), US-320 (report « pas encore »), US-345 (rappels au registre)
- Modèle / effort conseillé : **Sonnet 5.5, `medium`** — des fonctions pures (ouverture, suggestions) et du câblage d'entrées, sans changement du moteur ni du chemin d'écriture ; ni Opus ni Fable ne sont requis

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given la fiche de la fève est ouverte et sa levée est due aujourd'hui
When le jardinier touche "Noter la levée"
Then Gaston s'ouvre avec le contexte "Fève · Planche centrale · rang 6"
And il dit "Vous êtes sur fève. Dites ce que vous voyez, ou touchez une suggestion."
And les suggestions sont "J'ai vu la levée", "Pas encore" et "Photo · bientôt" désactivée
And aucun appel au modèle n'a été fait

Given le jardinier est sur la fiche catalogue du céleri-rave
When il touche "Ajouter à mon potager"
Then Gaston s'ouvre avec "Céleri-rave · catalogue" en contexte
And le champ contient "Ajouter le céleri-rave à mon potager", pas encore envoyé
When il l'envoie
Then Gaston demande la variété, et Monarch et Prinz s'affichent en suggestions
And la carte "À enregistrer" propose le rappel de semis, à confirmer
```

**Labels GitHub :** `us`, `frontend`, `pwa`, `compagnon`, `socle`

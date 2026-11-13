**ID :** US-324
**Titre :** Noter ce que je vois avec Gaston, d'un seul bouton
**Épic :** ÉPIC 19 — Plan du potager sur vue du dessus *(numéro à valider)*

**Story :**
En tant que jardinier
Je veux un seul bouton « Noter » qui ouvre Gaston en écoute, me propose les raccourcis de l'étape en cours, et me fait confirmer ce qu'il enregistre
Afin d'enregistrer une levée, une récolte ou une observation au fond du jardin en une phrase

**Contexte fonctionnel :**
Maquette de référence : `Plan - Pistes.html`, « Noter et Gaston : un seul chemin » et écrans mobiles 4 et 5. Principe de la maquette : **toute écriture passe par Gaston** ; un geste n'écrit rien, il ouvre le compagnon avec une carte « À enregistrer » (US-274). La dictée est celle de la page Compagnon · voix (US-302).

**Le chemin en quatre temps :**
1. **Toucher « Noter »** — barre basse (mobile) ou suivi de culture, ou onglet Entretien d'une parcelle
2. **Gaston s'ouvre** avec le contexte (US-323) et un message d'accueil : « Je vous écoute. Dites ce que vous voyez, je le note sur cette culture. »
3. **On parle** — le micro s'ouvre seul (le toucher vaut autorisation) ; compteur « Écoute… 0:04 », toucher de nouveau pour envoyer ; sans mode vocal : clavier et pastilles
4. **On confirme** — carte « À enregistrer », puis « Retour au plan »

**Raccourcis selon l'étape (pastilles) :**

| Situation | Raccourcis |
|---|---|
| Étape à confirmer | « Levée vue » (nom de l'étape), « Pas encore » |
| En récolte | « Récolte », « Culture terminée » |
| Terminé | « Rang libéré » |
| Autre étape | « [Étape suivante] vue » |
| Parcelle ou potager | « Arrosé », « Paillé », « Désherbé » |

**Cartes proposées :**

| Carte | Lignes | Effet à la confirmation |
|---|---|---|
| Note | 📝 la phrase | note rattachée au contexte, ou journal du potager sans contexte |
| Note + étape | 📝 la phrase, 🌱 l'étape | la note, et l'étape validée à la date du jour (US-320) |
| Étape | 🌱 l'étape | étape validée |
| Récolte | 🧺 quantité, culture | récolte enregistrée (règles végétatif / reproducteur d'US-320) |
| Rang libéré | ↺ parcelle, rang | culture archivée, rang libre |

**Critères d'acceptance :**
- [ ] CA1 : « Noter » ouvre Gaston avec le contexte courant, micro ouvert si la voix est activée (US-302), sinon clavier et pastilles
- [ ] CA2 : Les raccourcis suivent le tableau ; « Pas encore » ferme Gaston et repousse le rappel de trois jours (US-320 / E7)
- [ ] CA3 : Une phrase qui annonce une étape (« les fèves ont levé côté allée ») produit **une carte à deux lignes** — note et étape — et rien n'est écrit avant « Confirmer »
- [ ] CA4 : Les cinq cartes du tableau sont produites et confirmées par le flux de propositions existant (US-274), sans nouveau chemin d'écriture
- [ ] CA5 : Après confirmation, Gaston dit ce qui a changé (« la fève passe à Levée sur le plan ») et propose **« Retour au plan »** ; le plan se relit une fois et le segment passe du hachuré au plein
- [ ] CA6 : « Modifier » sur la carte se comporte comme sur toute carte du compagnon
- [ ] CA7 : Sur ordinateur, Gaston est le panneau flottant de l'application (380 × 600, bas à droite) ; sur mobile, son panneau plein écran
- [ ] CA8 : Les gestes « En fleur », « Culture terminée » et « Rang libéré » sont aussi compris du bot Telegram (cohérence avec US-320 / CA12)
- [ ] CA9 : Membre en lecture seule : « Noter » n'est pas proposé
- [ ] CA10 : La fiche d'aide du compagnon et le guide utilisateur décrivent « Noter » ; corpus mis à jour et ingéré ; `pytest tests/test_us099_corpus_fonctionnement.py` reste vert
- [ ] CA type : Le rendu correspond visuellement à la maquette de référence à 375 px / 768 px / desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement (compagnon PWA)
- Migration BDD requise : non au-delà d'US-320
- Dépendances : **US-320** (étapes), **US-323** (contexte) ; US-274 (cartes), US-302 (dictée), livrées
- Point de vigilance : ne pas déclarer l'US livrée sur des tests à modèle simulé seuls ; une recette sur le vrai modèle est due, avec accord préalable
- Modèle / effort conseillé : **Opus 5.5, `high`** — chemin d'écriture par le compagnon, nouvelles intentions

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Scénario: Confirmer une levée en une phrase
  Given la levée des fèves est à confirmer
  When je touche "Noter la levée"
  Then Gaston s'ouvre en écoute avec la pastille "Levée vue"
  When je dis "les fèves ont levé côté allée, rien encore au fond du rang"
  Then Gaston propose une carte avec la note et l'étape "Levée, 12 nov."
  When je confirme
  Then la fève passe à "Levé" validé sur le plan
  And Gaston propose "Retour au plan"

Scénario: Noter une récolte sur un reproducteur
  Given mes choux kale sont en récolte
  When je touche le raccourci "Récolte" et dis "800 grammes"
  Then la carte propose "Récolte 0,8 kg · Chou kale"
  And après confirmation l'étape reste "En récolte"
```

**Labels GitHub :** `us`, `backend`, `frontend`, `pwa`, `compagnon`, `voix`

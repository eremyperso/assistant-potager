**ID :** US-076
**Titre :** Afficher le widget météo sur l'écran Vue d'ensemble du Tableau de bord

**Story :**
En tant que jardinier
Je veux voir la météo de mon potager dès l'ouverture de l'application
Afin de savoir en un coup d'œil s'il faut arroser, protéger mes cultures ou reporter une intervention

**Contexte fonctionnel :**
Troisième US du Lot C — première brique réelle de l'écran « Vue d'ensemble » du Tableau de
bord (Lot D, non encore cadré dans son ensemble, cf. `docs/ANALYSE_REFONTE_UI_WEB_2026.md` §7.1).

Aujourd'hui, l'onglet « bord » de `frontend/src/App.jsx` est un `Placeholder` brut :
« Vue d'ensemble de votre potager : météo locale, tâches de la semaine, récoltes de la saison
et dernières interventions » — aucune vue réelle n'existe.

La maquette Claude Design (`web-screens.jsx` à la racine du projet, non encore figée) contient
`ScreenDashboard`, avec une carte météo dédiée : icône soleil, nom de ville + description,
température en grand, ligne « ressenti X° · humidité Y % · vent Z km/h », puis une bande de
5 jours (jour, icône, max, min). C'est le composant précis que cette US reproduit.

Les trois autres widgets visibles dans `ScreenDashboard` (« à faire cette semaine », « récoltes
de la saison », « dernières interventions ») dépendent de données non encore calculables côté
backend — génération d'une todo-list, notamment (`docs/ANALYSE_REFONTE_UI_WEB_2026.md` §6,
point ouvert n°1). Ils restent **hors périmètre** de cette US et continuent d'apparaître dans
le texte du `Placeholder` général tant qu'ils n'ont pas leur propre US.

**Critères d'acceptance :**
- [ ] CA1 : Nouvelle vue (ex. `frontend/src/views/Dashboard.jsx`) remplace le `Placeholder` de
      l'onglet « bord » dans `App.jsx`
- [ ] CA2 : La vue affiche la carte météo conforme à `ScreenDashboard` de la maquette : ville,
      description, température actuelle, ressenti/humidité/vent, prévision à 5 jours — alimentée
      par `GET /meteo` (US-075)
- [ ] CA3 : Si le potager actif n'a pas de localisation (`localisation_manquante`, US-075/CA4),
      la carte affiche une invitation claire à configurer la localisation, avec un raccourci
      direct vers « Modifier le potager » (US-074/CA5) — jamais une carte vide ou une erreur
      générique
- [ ] CA4 : En cas d'échec réseau ou d'erreur de l'API météo, un message d'erreur cohérent avec
      le reste de l'application (`ApiError`, US-059) s'affiche à la place de la carte, sans
      faire planter l'écran
- [ ] CA5 : Les autres sections listées par le `Placeholder` actuel (à faire cette semaine,
      récoltes de la saison, dernières interventions) restent visibles sous une forme
      `Placeholder` explicite à côté de la carte météo — aucune régression du contenu déjà
      annoncé, seul le widget météo en sort pour devenir réel
- [ ] CA type (US avec impact visuel/UI) : Le rendu de la carte météo correspond visuellement à
      `ScreenDashboard` de la maquette de référence à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non
- Dépendances : US-075 (`GET /meteo`), US-074 (raccourci vers la modification de localisation), US-053 (shell/navigation, `Placeholder` actuel), US-059 (`ApiError`/`LoadingSkeleton` partagés)

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Météo affichée pour un potager localisé
  Given un potager localisé (US-074) avec des données météo disponibles
  When l'utilisateur ouvre l'onglet "Tableau de bord"
  Then la carte météo affiche la ville, la température, le ressenti, l'humidité, le vent et 5 jours de prévision

Scénario: Potager sans localisation
  Given un potager actif sans ville ni coordonnées
  When l'utilisateur ouvre l'onglet "Tableau de bord"
  Then un message invite à configurer la localisation, avec un accès direct au formulaire de modification du potager

Scénario: Échec de l'API météo
  Given l'API météo indisponible
  When l'utilisateur ouvre l'onglet "Tableau de bord"
  Then un message d'erreur cohérent avec le reste de l'application s'affiche à la place de la carte météo
```

**Labels GitHub :** `us`, `sprint-refonte-ui-2026`, `frontend`, `lot-c`

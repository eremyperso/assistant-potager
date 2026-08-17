**ID :** US-075
**Titre :** Exposer une météo web personnalisée sur la localisation réelle du potager

**Story :**
En tant que jardinier utilisant l'interface web
Je veux que la météo affichée corresponde au lieu réel de mon potager
Afin que les prévisions soient pertinentes pour mon jardin, et non pour des coordonnées fixes codées en dur

**Contexte fonctionnel :**
Deuxième US du Lot C, en amont d'US-076 (écran) — sur le modèle déjà appliqué par US-065/US-061
(Pépinière) et US-072/US-073 (Stocks) : une US de données avant une US d'écran.

État actuel :
- `utils/meteo.py::fetch_meteo()` (météo du jour + résumé matin/après-midi) est **non
  paramétrable** : elle lit les constantes de module `METEO_LATITUDE`/`METEO_LONGITUDE`
  codées en dur, contrairement à `fetch_meteo_history()` qui accepte déjà `lat`/`lon`/`timezone`
  en paramètres (utilisée par `GET /meteo/history`, ajouté pour le graphique météo de
  l'écran Statistiques).
- `GET /meteo/history` ne couvre que l'**historique** (jusqu'à 365 jours passés) : aucun
  endpoint web n'expose la météo du jour ni de prévision à quelques jours.
- Le bot Telegram (job automatique 5h + commande `/meteo`) utilise `fetch_meteo()` telle
  quelle et doit continuer à fonctionner **exactement comme aujourd'hui** — cette US ne touche
  pas son comportement par défaut.
- La maquette Claude Design (`web-screens.jsx` racine, `ScreenDashboard`) attend une structure
  `WMETEO = { ville, desc, temp, ressenti, humid, vent, prev: [{ j, ic, max, min }, …] }` (5
  jours de prévision) pour la carte météo du Tableau de bord — c'est la donnée à produire ici.

**Critères d'acceptance :**
- [ ] CA1 : `fetch_meteo()` généralisée pour accepter `lat`/`lon`/`timezone` en paramètres
      optionnels, avec repli sur `METEO_LATITUDE`/`METEO_LONGITUDE`/`METEO_TIMEZONE` par défaut
      — même pattern que `fetch_meteo_history()`, sans changer son comportement par défaut
- [ ] CA2 : `fetch_meteo()` (ou une nouvelle fonction dédiée) retourne également une prévision
      sur les jours suivants (5 jours, alignés sur la maquette), chaque jour portant date,
      température min/max et code météo WMO (déjà traduit en emoji/label par `_wmo_label`)
- [ ] CA3 : Nouvel endpoint `GET /meteo` retournant température actuelle, ressenti, humidité,
      vent, description du jour, et la prévision à 5 jours (CA2), calculés sur la localisation
      du **potager actif** (`ctx.potager_id` → `Potager.ville`/`latitude`/`longitude`, US-074)
- [ ] CA4 : Si le potager actif n'a pas de localisation renseignée (US-074 non faite pour ce
      potager), l'endpoint retourne un indicateur explicite (`localisation_manquante: true`)
      plutôt qu'un repli silencieux sur les coordonnées globales du bot — ce serait afficher une
      météo qui ne correspond à aucun lieu réel du potager
- [ ] CA5 : Le bot Telegram (job 5h, commande `/meteo`) et `GET /meteo/history` ne changent pas
      de comportement — contrat inchangé, non-régression complète
- [ ] CA6 : Aucune migration BDD — les données proviennent d'Open-Meteo et de la localisation
      déjà posée par US-074

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non
- Dépendances : US-074 (localisation du potager), `utils/meteo.py::fetch_meteo`/`fetch_meteo_history` existants (à généraliser/compléter)
- US-076 (écran Vue d'ensemble) consomme cette US

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Météo d'un potager localisé
  Given un potager localisé à Vitry-sur-Seine (US-074)
  When GET /meteo est appelé pour ce potager
  Then la réponse contient la météo du jour et 5 jours de prévision, calculés sur ces coordonnées

Scénario: Potager sans localisation
  Given un potager sans ville ni coordonnées enregistrées
  When GET /meteo est appelé pour ce potager
  Then la réponse indique localisation_manquante = true, sans retourner de météo pour un autre lieu

Scénario: Non-régression du bot Telegram
  Given le job météo automatique de 5h ou la commande /meteo du bot
  When il s'exécute après cette US
  Then il produit exactement le même résultat qu'avant, sur les coordonnées de configuration globales
```

**Labels GitHub :** `us`, `sprint-refonte-ui-2026`, `backend`, `lot-c`

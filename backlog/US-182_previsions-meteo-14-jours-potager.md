**ID :** US-182
**Titre :** Étendre la météo du potager à 14 jours de prévision, avec un cache par localisation et par jour
**Épic :** ÉPIC 8 — Confiance et personnalisation du calendrier *(numéro à valider, voir le plan de l'épic)*

**Story :**
En tant que jardinier
Je veux que l'application connaisse les températures minimales annoncées sur les deux prochaines semaines à l'emplacement de mon potager
Afin que ses conseils de semis et de plantation tiennent compte d'un gel annoncé au-delà de cinq jours, et que plusieurs consultations dans la journée ne redemandent pas la même prévision

**Contexte fonctionnel :**
Le Lot C est livré : `Potager.latitude` / `longitude` (US-074), `fetch_meteo(lat, lon, timezone)` et `GET /meteo` sur la localisation du potager actif (US-075), widget (US-076). Mais la prévision s'arrête à **5 jours** (`forecast_days = 6`, US-075 / CA2) — insuffisant pour un semis dont la levée prend dix à quatorze jours, et pour la règle « aucun gel annoncé sur 14 jours » du moteur de confiance (US-178 / R3).

Par ailleurs, chaque `GET /meteo` interroge Open-Meteo. Le moteur de confiance sera appelé bien plus souvent que le widget (une lecture groupée par ouverture de l'écran Plan, une par question au bot) : sans cache, la charge et la latence deviennent le problème. Le plan multi-tenant l'avait anticipé (« cache `(lat, lon, jour)` et batching Open-Meteo », ancienne US-124, jamais livrée sous ce numéro).

Cette US **étend et met en cache** ; elle ne change ni le job météo quotidien de 5 h, ni `/meteo` Telegram, ni le contenu actuel du widget.

**Critères d'acceptance :**
- [ ] CA1 : La lecture de prévision d'un potager rend, en plus de l'existant, **14 jours** de prévision quotidienne avec au minimum la température minimale, la température maximale et le code météo de chaque jour. Les clés existantes du dictionnaire météo ne sont ni renommées ni retirées (non-régression US-075 / CA5)
- [ ] CA2 : Les prévisions sont **mises en cache par `(latitude, longitude, jour)`** : deux lectures le même jour pour la même localisation, quel que soit le potager ou le membre, ne déclenchent qu'un appel Open-Meteo. Deux potagers localisés au même endroit partagent l'entrée
- [ ] CA3 : La durée de validité du cache est déclarée à un seul endroit ; une entrée périmée est rafraîchie à la lecture suivante, jamais par un job supplémentaire. Le job météo quotidien de 5 h est inchangé
- [ ] CA4 : Une **lecture groupée** existe pour plusieurs localisations distinctes en un appel de service, sans appel réseau pour celles déjà en cache — c'est ce que consommera le moteur de confiance
- [ ] CA5 : Quand Open-Meteo est indisponible, la lecture rend l'entrée en cache si elle existe, sinon **rien** : aucun consommateur ne reçoit une prévision inventée ou périmée présentée comme fraîche. L'âge de la donnée est exposé au consommateur
- [ ] CA6 : Un potager **sans localisation** ne déclenche aucun appel et reçoit « pas de prévision », distinct d'une erreur réseau
- [ ] CA7 : Les appels sont **journalisés** (localisation arrondie, date, succès ou échec, durée) au format structuré existant ; aucun bloc `except` silencieux
- [ ] CA8 : Aucune régression sur le widget météo (US-076), sur `/meteo` Telegram, sur `GET /meteo/history` ni sur les observations enregistrées par le job de 5 h ; les tests existants de `utils/meteo.py` restent verts
- [ ] CA9 : Des tests couvrent : 14 jours rendus, non-régression des clés, cache partagé par localisation, rafraîchissement à péremption, lecture groupée sans appel pour les entrées en cache, indisponibilité avec et sans cache, potager sans localisation, journalisation

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : infrastructure (météo), consultation
- Migration BDD requise : **non** (cache en mémoire de processus en v1 ; ⚖️ si le cache doit survivre à un redémarrage ou être partagé entre processus, c'est une décision à prendre avec le passage à Redis prévu par le plan multi-tenant, pas dans cette US)
- Dépendances : **US-074** / **US-075** (livrées)
- Consommateurs : **US-178** (R3, R4), et potentiellement le widget météo pour un affichage à 14 jours (hors périmètre ici)
- Impact tokens : zéro. Impact réseau : au plus un appel Open-Meteo par localisation distincte et par jour, gratuit
- Point de vigilance : Open-Meteo accepte jusqu'à 16 jours de prévision ; 14 est un choix produit aligné sur la règle R3. À déclarer, pas à coder en dur à deux endroits
- Point de vigilance : la précision d'une prévision à 14 jours est faible. Le moteur de confiance ne la présente jamais comme une certitude ; cette US n'a pas à la qualifier, mais elle expose l'horizon de chaque jour pour qu'un consommateur puisse le faire

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Quatorze jours de prévision
  Given un potager localisé
  When la prévision du potager est lue
  Then elle contient 14 jours avec température minimale, maximale et code météo
  And toutes les clés existantes de la météo sont présentes

Scénario: Cache partagé par localisation
  Given deux potagers localisés au même endroit
  When leur prévision est lue le même jour
  Then un seul appel Open-Meteo est effectué

Scénario: Lecture groupée
  Given trois localisations dont deux déjà en cache
  When la lecture groupée est demandée
  Then un seul appel Open-Meteo est effectué

Scénario: Service indisponible, cache présent
  Given une prévision en cache datée d'aujourd'hui
  And Open-Meteo ne répond pas
  When la prévision est lue
  Then l'entrée en cache est rendue avec son âge

Scénario: Service indisponible, pas de cache
  Given aucune prévision en cache
  And Open-Meteo ne répond pas
  When la prévision est lue
  Then aucune prévision n'est rendue
  And l'échec est journalisé

Scénario: Potager sans localisation
  Given un potager sans latitude ni longitude
  When sa prévision est lue
  Then aucun appel n'est effectué
  And le résultat indique l'absence de localisation
```

**Labels GitHub :** `us`, `backend`, `meteo`

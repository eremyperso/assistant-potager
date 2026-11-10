**ID :** US-312
**Titre :** Suivre la consommation jour par jour
**Épic :** ÉPIC 18 — Pilotage LLM

**Story :**
En tant qu'administrateur de la plateforme
Je veux voir les appels et les jetons consommés chaque jour, par modèle et par type d'appel
Afin de savoir ce que l'assistant consomme réellement et où part la consommation

**Contexte fonctionnel :**
Première vue de la PWA d'administration, page d'accueil. Elle remplace l'extraction CSV analysée à la main le 10/11/2026.

**Critères d'acceptance :**
- [ ] CA1 : Un bandeau de chiffres clés donne, pour la période : appels, jetons d'entrée, jetons de sortie, taux de cache, jetons d'entrée médians par appel ; chacun avec son écart à la période précédente de même durée.
- [ ] CA2 : Un graphique par jour montre les jetons d'entrée, la part servie par le cache étant distinguée ; sur « aujourd'hui », le pas est l'heure.
- [ ] CA3 : La série se ventile au choix par modèle, type d'appel ou canal ; une légende permet d'isoler une série.
- [ ] CA4 : Un tableau donne par type d'appel : appels, jetons d'entrée, de sortie, part du total, jetons d'entrée médians par appel.
- [ ] CA5 : Un tableau donne les mêmes colonnes par modèle.
- [ ] CA6 : Les secondes d'audio (dictée) et les caractères (voix) sont affichés dans un bloc à part, jamais additionnés aux jetons.
- [ ] CA7 : Par défaut seules les provenances `usage` et `fond` sont comptées ; un bandeau le rappelle et un filtre affiche `mesure`, `test` ou `historique`.
- [ ] CA8 : Un jour sans appel apparaît à zéro, pas comme un trou dans la série.
- [ ] CA9 : Chaque graphique a un équivalent en tableau accessible au clavier ; les couleurs restent lisibles en thème clair et sombre.
- [ ] CA10 : Les chiffres affichés pour une période sont ceux de `GET /admin/pilotage/synthese` à l'unité près ; un test le vérifie sur un jeu de données fixe.
- [ ] CA11 : Le rendu correspond visuellement à la maquette de référence à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA d'administration)
- Cadrage : `docs/EPIC 18 - PILOTAGE LLM/CADRAGE_PILOTAGE_LLM.md` (numéro d'épic à valider)
- Migration BDD requise : non
- Dépendances : US-310, US-311, US-318 (maquette de référence)
- Décisions liées : D8, D9
- Maquette de référence : vue Consommation d'US-318.

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given la semaine compte 120 appels d'usage et 900 appels de mesure
When j'ouvre la vue Consommation sur 7 jours
Then le bandeau affiche 120 appels
And un rappel indique que les mesures et les tests sont masqués
When j'active le filtre "mesure"
Then le bandeau affiche 900 appels
```

**Labels GitHub :** `us`, `pwa`, `admin`, `observabilite`

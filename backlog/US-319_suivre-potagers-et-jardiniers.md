**ID :** US-319
**Titre :** Suivre la consommation par potager et par jardinier
**Épic :** ÉPIC 18 — Pilotage LLM

**Story :**
En tant qu'administrateur de la plateforme
Je veux voir pour chaque potager et pour chaque jardinier ce qu'il consomme, ce qu'il coûte et comment il utilise l'assistant
Afin de connaître mes utilisateurs réels, de repérer un usage anormal et de fonder un prix sur des profils mesurés

**Contexte fonctionnel :**
Vue « Potagers et jardiniers » de la PWA d'administration. Les autres vues répondent à « que consomme la plateforme ? » ; celle-ci répond à « qui consomme quoi ? ». Elle est la seule à lire, en plus de `conso_tokens`, les tables `potagers`, `potager_membres` et `users` : sans elles, un potager qui n'appelle jamais l'assistant est invisible, alors que c'est une information d'adoption.

**Critères d'acceptance :**
- [ ] CA1 : `GET /admin/pilotage/potagers` renvoie pour la période, par potager : nom, nombre de membres, appels, échanges, jetons d'entrée et de sortie, coût, part du coût total, canaux utilisés, taux d'échec, date du dernier appel ; les potagers sans appel sur la période figurent avec des valeurs à zéro.
- [ ] CA2 : `GET /admin/pilotage/utilisateurs` renvoie les mêmes mesures par utilisateur, avec le nombre de potagers dont il est membre et sa date d'inscription.
- [ ] CA3 : Un bandeau donne : potagers existants, potagers actifs sur la période, jardiniers inscrits, jardiniers actifs, coût médian et P95 par jardinier actif, part du coût portée par le premier décile des jardiniers.
- [ ] CA4 : Un tableau liste les potagers, triable par coût, appels, échanges ou dernier appel ; un second onglet liste les jardiniers avec les mêmes tris.
- [ ] CA5 : Une fiche de potager montre : série par jour des appels et du coût, répartition par type d'appel et par canal, coût médian d'un échange, issues, membres avec leur part de la consommation.
- [ ] CA6 : Une fiche de jardinier montre les mêmes éléments, répartis entre ses potagers.
- [ ] CA7 : Un potager ou un jardinier dont le coût de la période dépasse trois fois la médiane est signalé « usage élevé » ; la règle est affichée.
- [ ] CA8 : Les appels de fond (sans utilisateur) sont rattachés au potager et regroupés sous « tâches automatiques » dans la vue par jardinier.
- [ ] CA9 : Par défaut seules les provenances `usage` et `fond` sont comptées ; les filtres de la coquille s'appliquent.
- [ ] CA10 : La vue affiche le nom du potager et l'adresse e-mail du jardinier, et rien d'autre de personnel : aucun contenu de message, aucune donnée de culture.
- [ ] CA11 : Les routes sont en lecture seule, protégées par `require_admin_user`, et empruntent le chemin de lecture hors périmètre de potager d'US-310 ; un compte non administrateur reçoit 403.
- [ ] CA12 : Le traitement est inscrit au registre RGPD (`docs/RGPD/`) : finalité d'exploitation et de facturation, accès limité à l'administrateur, durée de conservation de `conso_tokens`.
- [ ] CA13 : Le rendu réutilise sans variante les composants de la maquette de référence de la vue Consommation (US-318) et reste conforme à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (services de pilotage, API et PWA d'administration)
- Cadrage : `docs/EPIC 18 - PILOTAGE LLM/CADRAGE_PILOTAGE_LLM.md` (numéro d'épic à valider)
- Migration BDD requise : non
- Dépendances : US-306, US-307, US-310, US-311, US-312 (composants), US-318 (maquette) ; US-309 pour les mesures de coût (renvoyées nulles sinon)
- Décisions liées : D9, D12
- Un potager en clé personnelle (US-143, à venir) devra être distingué : son coût n'est pas porté par la plateforme.
- Le seuil « trois fois la médiane » est une valeur de départ, à valider sur les données réelles.

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given 5 potagers existent, dont 3 ont des appels d'usage sur les 30 derniers jours
And le potager "Jardin de la Garenne" a coûté 0,90 € quand la médiane est de 0,20 €
When j'ouvre la vue Potagers et jardiniers sur 30 jours
Then le bandeau affiche 5 potagers existants et 3 actifs
And "Jardin de la Garenne" est en tête du tri par coût, signalé "usage élevé"
And les 2 potagers sans appel figurent avec un coût de 0 €
When j'ouvre sa fiche
Then je vois la part de chaque membre dans sa consommation
```

**Labels GitHub :** `us`, `pwa`, `admin`, `observabilite`, `rgpd`

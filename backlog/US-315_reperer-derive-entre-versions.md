**ID :** US-315
**Titre :** Repérer une dérive de consommation d'une version à l'autre
**Épic :** ÉPIC 18 — Pilotage LLM

**Story :**
En tant qu'administrateur de la plateforme
Je veux comparer la taille des appels et le nombre d'appels par échange entre deux versions de l'application
Afin de voir tout de suite qu'une livraison a alourdi le prompt ou allongé la boucle de l'agent

**Contexte fonctionnel :**
Vue « Dérives » de la PWA d'administration. Le prompt de l'agent est passé d'environ 1 000 jetons d'entrée par appel le 21/10/2026 à 8 000 à 9 000 le 05/11, par paliers correspondant à des livraisons (outils ajoutés, historique allongé à 10 échanges). Personne ne l'a vu avant l'analyse manuelle.

**Critères d'acceptance :**
- [ ] CA1 : Un tableau donne par version de l'application (les 10 dernières ayant des appels) et par type d'appel : nombre d'appels, médiane et P95 des jetons d'entrée, médiane des jetons de sortie, taux de cache.
- [ ] CA2 : Un graphique par jour montre la médiane des jetons d'entrée par appel pour un type choisi (`agent` par défaut), avec un repère vertical à la première apparition de chaque version.
- [ ] CA3 : Un tableau donne par version et par canal : nombre médian et P95 d'appels par échange, jetons d'entrée médians par échange, coût médian par échange si disponible.
- [ ] CA4 : Deux versions se comparent côte à côte ; l'écart en pourcentage est affiché et mis en évidence au-delà de 20 %.
- [ ] CA5 : Une version ayant moins de 20 appels du type considéré est marquée « échantillon faible » et n'est pas mise en évidence.
- [ ] CA6 : Le filtre de provenance permet de comparer en `mesure` : une campagne rejouée sur le même jeu de phrases donne la comparaison la plus propre, et la vue le dit.
- [ ] CA7 : Les lignes sans version (historique) sont regroupées sous « avant suivi des versions ».
- [ ] CA8 : Le rendu réutilise sans variante les composants de la maquette de référence de la vue Consommation (US-318) et reste conforme à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA d'administration)
- Cadrage : `docs/EPIC 18 - PILOTAGE LLM/CADRAGE_PILOTAGE_LLM.md` (numéro d'épic à valider)
- Migration BDD requise : non
- Dépendances : US-307, US-310, US-311, US-312 (composants), US-318 (maquette)
- Décisions liées : D4
- C'est la vue à regarder après chaque livraison qui touche le prompt de l'agent, ses outils ou son historique.

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given la version 3.127.0 a une médiane de 6 000 jetons d'entrée par appel agent sur 200 appels
And la version 3.128.0 a une médiane de 8 900 jetons sur 150 appels
When je compare les deux versions
Then l'écart affiché est +48 %
And il est mis en évidence
```

**Labels GitHub :** `us`, `pwa`, `admin`, `observabilite`

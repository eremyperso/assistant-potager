**ID :** US-304
**Titre :** Écouter la réponse de Gaston au haut-parleur
**Épic :** ÉPIC 17 — Compagnon vocal dans la PWA *(numéro à valider, voir `docs/EPIC 17 - COMPAGNON VOCAL PWA/ANALYSE_ET_SOLUTION_COMPAGNON_VOCAL.md`)*

**Story :**
En tant que jardinier
Je veux que Gaston me réponde à voix haute quand je lui ai parlé, et pouvoir réécouter n'importe laquelle de ses réponses
Afin de converser sans regarder l'écran et de réentendre un conseil

**Contexte fonctionnel :**
Décision D5 : lecture **automatique après une dictée** (le tap sur 🎤 déverrouille le son sur iPhone et iPad) et **bouton ▶ sur chaque réponse**. Ce qui est lu est le résumé parlé d'US-303, dans la voix choisie (US-300). La lecture se fait par identifiant d'échange : aucun texte arbitraire n'est synthétisé (étude §5.1).

**Critères d'acceptance :**
- [ ] CA1 : `POST /compagnon/voix/lecture/{echange_id}` rend le MP3 du résumé parlé de l'échange dans la voix du jardinier ; un échange hors de son compte ou de son potager rend 404 ; un compte sans mode vocal rend 403.
- [ ] CA2 : Lecture automatique active (US-301) et phrase dictée (US-302) : la réponse de Gaston est lue dès qu'elle arrive, sans autre geste, y compris sur iPhone et iPad.
- [ ] CA3 : Une phrase tapée n'est jamais lue automatiquement ; lecture automatique coupée, une phrase dictée ne l'est pas non plus.
- [ ] CA4 : Mode vocal actif, chaque réponse de Gaston porte un bouton ▶, y compris les réponses anciennes de l'historique ; pendant la lecture, il devient ⏹ et arrête la lecture.
- [ ] CA5 : Une seule lecture à la fois : lancer ▶ sur une autre réponse arrête la première ; fermer le panneau, changer de page ou appuyer sur 🎤 arrête la lecture.
- [ ] CA6 : Le MP3 d'un échange déjà lu est gardé en mémoire pendant la session : le réécouter ne refait pas d'appel ; changer de voix invalide ce cache.
- [ ] CA7 : Les messages spontanés du compagnon (veilleur) ne sont jamais lus automatiquement ; ils portent le ▶ s'ils sont rattachés à un échange.
- [ ] CA8 : Synthèse indisponible : le ▶ dit « Lecture indisponible pour le moment » ; la réponse écrite reste affichée normalement.
- [ ] CA9 : Plafond `VOIX_PLAFOND_LECTURES_JOUR` (100 par défaut) atteint : 429 et « Limite de lectures du jour atteinte » ; les réponses restent lisibles à l'écran.
- [ ] CA10 : La règle de lecture automatique (dictée ? réglage ? message spontané ?) et l'état « une lecture à la fois » vivent dans une logique pure testée par `node --test`.
- [ ] CA11 : La lecture fonctionne sur Chrome, Edge et Firefox (PC), Safari (Mac), Safari et PWA installée (iPad, iPhone), Chrome et PWA installée (Android) ; téléphone en mode silencieux, l'absence de son n'est pas une erreur de l'application.
- [ ] CA12 : Le rendu correspond à la maquette de référence à 375 px, 768 px et sur ordinateur ; ▶ et ⏹ ont un libellé accessible (« Écouter la réponse », « Arrêter la lecture »).
- [ ] CA13 : Le guide utilisateur (ses deux copies) et la fiche du corpus du compagnon vocal décrivent la lecture automatique, le ▶ et le plafond ; `pytest tests/test_us099_corpus_fonctionnement.py` reste vert.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction (PWA)
- Migration BDD requise : non
- Dépendances : US-300, US-302, US-303 ; maquette Claude Design
- Décisions liées : D5, D6, C4, C6
- Fiche du corpus : `compagnon-vocal-pwa.md`

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given le mode vocal et la lecture automatique sont actifs, voix "Manon"
When le jardinier dicte "quand planter l'ail ?"
Then Gaston répond par écrit
And le résumé parlé de la réponse est lu aussitôt avec la voix de Manon
When le jardinier appuie sur 🎤 pendant la lecture
Then la lecture s'arrête avant l'ouverture du micro
When il appuie sur ▶ sous une réponse d'hier
Then cette réponse est lue
And une seule lecture est en cours
```

**Labels GitHub :** `us`, `voix`, `pwa`, `compagnon`

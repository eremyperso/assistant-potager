**ID :** US-272
**Titre :** Traiter la même proposition dans Telegram ou dans la PWA
**Épic :** ÉPIC 15 — Compagnon dans la PWA *(numéro à valider, voir `docs/EPIC - COMPAGNON CONVERSATIONNEL/CADRAGE_COMPAGNON_ACTIF.md`)*

**Story :**
En tant que jardinier
Je veux qu'une proposition faite sur le portail arrive aussi dans Telegram, et que chaque canal montre ce qui a été fait dans l'autre
Afin de répondre là où je suis, sans doublon ni carte périmée

**Contexte fonctionnel :**
Lot 6 du cadrage (§4.7, F1 à F5 ; D11, D12, D13). Une proposition vit en base ; Telegram et la PWA en sont deux fenêtres. Le fil Telegram est le journal complet. Pas de suivi de présence, pas de temporisation.

**Critères d'acceptance :**
- [ ] CA1 : Toute proposition née dans la PWA est envoyée dans Telegram dès sa création, même si elle est confirmée aussitôt dans la PWA (D13).
- [ ] CA2 : La première réponse l'emporte ; un second traitement reçoit « Déjà confirmé depuis le portail à 14:32 » et rien n'est exécuté deux fois (F1).
- [ ] CA3 : Au changement d'état, la carte est réécrite dans chaque canal (« ✅ Confirmé depuis le portail ») ; si la réécriture Telegram échoue, CA2 suffit (F2).
- [ ] CA4 : Une proposition remplacée voit sa carte réécrite en « Remplacée : voir la nouvelle proposition » (F3).
- [ ] CA5 : Le panneau montre l'état réel des cartes, rafraîchi à l'ouverture et à intervalle court (sans WebSocket), avec une pastille des messages non lus.
- [ ] CA6 : La carte nomme le potager quand le jardinier en a plusieurs (F5).
- [ ] CA7 : Test de concurrence : 0 double exécution sur 100 confirmations simultanées.
- [ ] CA8 : Test de parité : une proposition confirmée d'un côté est vue confirmée de l'autre ; une correction dite dans Telegram (« en fait c'était 10 ») corrige un geste confirmé dans la PWA.
- [ ] CA9 : Un compte sans Telegram lié reçoit les messages dans le panneau seul, et est invité une fois à lier Telegram.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram, consultation (PWA)
- Migration BDD requise : non (identifiants de message par canal déjà prévus par US-267)
- Dépendances : US-271, US-267
- Production conseillée : **Opus 5.5, effort `high`** — concurrence entre deux processus, réécriture de messages Telegram et cohérence d'état entre canaux.

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given le jardinier dit "j'ai repiqué 12 tomates sur la planche Sud" dans la PWA
Then une carte apparaît dans le panneau et dans Telegram
When il confirme dans la PWA
Then la carte Telegram est réécrite "✅ Confirmé depuis le portail"
When il clique ensuite [Confirmer] dans Telegram
Then il lit "Déjà confirmé depuis le portail" et rien n'est enregistré deux fois
```

**Labels GitHub :** `us`, `compagnon`, `pwa`, `telegram`, `concurrence`

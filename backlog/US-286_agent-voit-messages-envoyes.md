**ID :** US-286
**Titre :** Montrer à l'agent ce que le bot a envoyé de lui-même
**Épic :** ÉPIC 14 — Agent actif *(à valider)*

**Story :**
En tant que jardinier
Je veux pouvoir répondre au compagnon sur ce qu'il vient de m'envoyer de lui-même (une relance, une purge, un message du matin)
Afin qu'il sache de quoi je parle quand je dis « vide le geste » ou « c'est fait »

**Contexte fonctionnel :**
Le 01/11/2026 à 22:36:19, le contrôle horaire de la file de gestes (US-224) a retiré un geste préparé depuis l'application et l'a annoncé au jardinier. Vingt-cinq secondes plus tard, le jardinier écrit « vide le geste ». L'agent ignore cette annonce. Il comprend « effacer le dernier geste enregistré dans ton carnet », une vraie entrée du carnet, et promet de le faire. Le « oui » qui suit tombe dans le vide. En mesure (01/11), Small 4 envoie même la phrase au parseur de gestes.
Les relances, avertissements et purges de la file (US-224), les messages spontanés (US-267) et les rappels arrivés à terme (US-268) partent sans entrer dans la conversation que l'agent lit.

**Critères d'acceptance :**
- [ ] CA1 — Tout message envoyé par le bot de lui-même entre dans la conversation (`echanges_conversation`, `signal` renseigné) et dans les échanges récents que reçoit l'agent : relance, avertissement et purge de la file de gestes, message spontané, rappel arrivé à terme.
- [ ] CA2 — L'agent lit la file des gestes en attente (une lecture, par exemple `lire(quoi="gestes_en_attente")`) et peut proposer d'en abandonner un. C'est une écriture, confirmée au bouton.
- [ ] CA3 — « vide le geste » juste après une purge : l'agent répond que le geste vient d'être retiré et qu'il n'y a plus rien en attente. Aucune écriture.
- [ ] CA4 — « vide le geste » avec un geste en attente : proposition d'abandon de ce geste. Jamais une suppression ni une annulation d'une entrée du carnet.
- [ ] CA5 — Les cartes d'US-272 (D11, D13) ne changent pas : cette US n'ajoute qu'une mémoire et une lecture.
- [ ] CA6 — Le dialogue TER-31 du corpus de terrain porte l'annonce de purge avant « vide le geste ». Remesure sur Small 4, avec accord et en un seul passage : juste.
- [ ] CA7 — Tests sans modèle : chaque type de message entre dans la conversation ; « vide le geste » après purge, avec un geste en attente, sans file.
- [ ] CA8 — La table de `data/connaissance/doc_app/README.md` est relue (fiches de la file de gestes et du compagnon) ; `pytest tests/test_us099_corpus_fonctionnement.py` reste vert.

**Hors périmètre :**
- La rédaction des messages spontanés (US-267) : inchangée.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : compagnon (mémoire de conversation), file de gestes
- Migration BDD requise : non attendue (`echanges_conversation.signal` existe)
- Dépendances : US-280 ; US-224, US-259, US-267, US-268
- Code concerné : `app/services/relances_file.py`, `app/bot/file_gestes.py`, `app/bot/messages_spontanes.py`, `app/services/compagnon/conversations.py`, `app/services/agent/lecture.py`
- Production conseillée : **Sonnet 5.5, effort `medium`**

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given le bot vient d'annoncer "1 geste vidé : il n'avait pas été confirmé"
When le jardinier écrit "vide le geste"
Then le compagnon répond que le geste vient d'être retiré et que rien n'est en attente
And aucune carte n'est montrée
```

**Labels GitHub :** `us`, `compagnon`, `file-gestes`, `conversation`

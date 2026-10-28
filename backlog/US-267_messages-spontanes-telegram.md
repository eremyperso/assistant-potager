**ID :** US-267
**Titre :** Envoyer des messages spontanés dans Telegram, sans harceler
**Épic :** ÉPIC 14 — Compagnon actif : profil, mémoire et initiative *(numéro à valider, voir `docs/EPIC - COMPAGNON CONVERSATIONNEL/CADRAGE_COMPAGNON_ACTIF.md`)*

**Story :**
En tant que jardinier
Je veux que le compagnon m'écrive de lui-même quand il gèle cette nuit ou qu'une levée n'est pas notée, au bon moment et sur les sujets que j'ai choisis
Afin de ne rien rater sans être dérangé à tort

**Contexte fonctionnel :**
Lot 5 du cadrage (§1.3, §1.4, §1.8, §4.4 ; D2, D11, D12 ; R8). Le distributeur règle le **moment** et la **forme**, pas le nombre. L'agent **rédige sans décider**.

**Critères d'acceptance :**
- [ ] CA1 : Un signal d'un thème coupé est consommé sans envoi.
- [ ] CA2 : Un signal `immediat` hors plage de silence part tout de suite ; ceux de la même demi-heure sont regroupés en un message.
- [ ] CA3 : En plage de silence (21 h à 8 h par défaut), l'envoi part à la fin de la plage, **sauf** si le signal expire avant : il part alors avant la plage.
- [ ] CA4 : Un signal `resume` rejoint le résumé du matin (8 h, réglable) ; pas de résumé vide (D7).
- [ ] CA5 : Trois messages d'un thème sans réaction font passer ce thème en `resume`, et le compagnon le dit une fois.
- [ ] CA6 : Le signal est rédigé par l'agent à partir de ses données ; si la rédaction échoue ou cite un chiffre absent du signal, un gabarit du code part à sa place. Type d'appel distinct `compagnon_signal` dans `conso_tokens`.
- [ ] CA7 : Les boutons d'un message spontané ouvrent une **proposition** ; un signal rédigé ne produit jamais de `ResultatEtape` (R8, test).
- [ ] CA8 : La réponse du jardinier à un message spontané continue la conversation, avec le signal d'origine en contexte.
- [ ] CA9 : Réglages par thème (`immediat` / `resume` / `coupe`) et plages de silence, par boutons et par phrase confirmée (profil, partie 3).
- [ ] CA10 : L'identifiant du message Telegram est gardé pour réécrire la carte plus tard (F2).
- [ ] CA11 : Seul le planificateur du bot distribue ; un signal est consommé de façon atomique. Le tout est réversible par `COMPAGNON_PROACTIF`.
- [ ] CA12 : Les règles du distributeur sont couvertes par des tests unitaires sans modèle ; mesure du lot 5 : rédaction fidèle aux données, 0 écriture issue d'un signal sans confirmation.
- [ ] CA13 : La fiche de `data/connaissance/doc_app/` sur les notifications est créée ou mise à jour.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram
- Migration BDD requise : oui (réglages de proactivité et de silence du profil ; état d'envoi des signaux)
- Dépendances : US-266, US-265, US-259
- Production conseillée : **Opus 5.5, effort `xhigh`** — règles temporelles croisées (silence, expiration, regroupement, bascule en résumé) et reprise de conversation sur signal ; c'est l'US où le « harcèlement » ou le silence à tort se joue.

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Given un signal de gel expirant à 5 h, détecté à 22 h
And une plage de silence de 21 h à 8 h
Then le message ne part pas pendant la plage
But given le même signal détecté à 18 h
Then le message part à 18 h dans Telegram

Given un message spontané "Ça a germé ?" sur le lot S-014
When le jardinier répond "oui environ 20 sur 24"
Then le compagnon propose la levée de 20 godets sur 24 à confirmer
```

**Labels GitHub :** `us`, `compagnon`, `distributeur`, `proactivite`, `telegram`

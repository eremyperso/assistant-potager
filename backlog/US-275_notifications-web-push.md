**ID :** US-275
**Titre :** Notifier dans la PWA les comptes sans Telegram (Web Push)
**Épic :** ÉPIC 15 — Compagnon dans la PWA *(numéro à valider, voir `docs/EPIC - COMPAGNON CONVERSATIONNEL/CADRAGE_COMPAGNON_ACTIF.md`)*

**Story :**
En tant que jardinier sans compte Telegram lié
Je veux recevoir les alertes du compagnon sur mon téléphone par la PWA
Afin de ne pas rater une alerte de gel

**Contexte fonctionnel :**
US **facultative**, reportée par D11. À ne lancer que si des jardiniers utilisent la PWA sans Telegram, mesuré par le nombre de comptes sans `telegram_chat_id`. Le dashboard React n'a aujourd'hui ni manifeste ni service worker.

**Critères d'acceptance :**
- [ ] CA1 : La PWA est installable (manifeste), y compris sur iPhone.
- [ ] CA2 : Un service worker reçoit les notifications ; les abonnements sont gardés par appareil.
- [ ] CA3 : L'envoi passe par l'interface de `notifications.py` (clés VAPID, `pywebpush`), sans changer les règles du distributeur.
- [ ] CA4 : Un compte avec Telegram lié continue de recevoir ses notifications dans Telegram (D11).
- [ ] CA5 : Le jardinier peut retirer l'abonnement d'un appareil.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction (PWA)
- Migration BDD requise : oui (abonnements Web Push par appareil)
- Dépendances : US-272 ; condition de lancement ci-dessus
- Production conseillée : **Sonnet 5.5, effort `medium`** — intégration standard d'une technologie connue, derrière une interface déjà prévue.

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given un compte sans Telegram lié, abonné aux notifications sur son téléphone
When un signal de gel est distribué
Then une notification Web Push arrive sur le téléphone
And la carte est visible dans le panneau du compagnon
```

**Labels GitHub :** `us`, `compagnon`, `pwa`, `notifications`

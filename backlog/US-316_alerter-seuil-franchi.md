**ID :** US-316
**Titre :** Être alerté quand un seuil de contrôle est franchi
**Épic :** ÉPIC 18 — Pilotage LLM

**Story :**
En tant qu'administrateur de la plateforme
Je veux recevoir un message Telegram et un e-mail quand la consommation, le coût ou la fiabilité sortent des seuils que j'ai fixés
Afin d'agir avant qu'une dérive ne devienne une facture ou une panne pour les jardiniers

**Contexte fonctionnel :**
Décisions D10 et D11 (canaux choisis le 10/11/2026 : Telegram et e-mail). Les seuils lisent le service d'agrégats d'US-310. L'envoi Telegram vers l'administrateur réutilise `app/services/telegram_notify.py` ; l'e-mail réutilise l'envoi Brevo de `app/services/email.py`.

**Critères d'acceptance :**
- [ ] CA1 : La migration crée `seuils_pilotage` (indicateur, périmètre, fenêtre, comparaison, valeur, gravité, actif) et `alertes_pilotage` (seuil, valeur mesurée, déclenchée le, résolue le, canaux notifiés), avec rollback.
- [ ] CA2 : Les indicateurs surveillables sont au minimum : coût du jour, coût du mois projeté, jetons d'entrée médians par appel d'un type, nombre d'appels par échange, taux de quota, taux d'erreur, latence P95 d'un type, nombre d'appels non chiffrés.
- [ ] CA3 : Un seuil se compare soit à une valeur fixe, soit à la moyenne des 7 jours précédents (écart en pourcentage).
- [ ] CA4 : Un jeu de seuils par défaut est créé, inactif pour ceux qui dépendent du coût tant qu'US-309 n'est pas livrée ; chaque valeur par défaut est marquée « à valider ».
- [ ] CA5 : Les seuils sont évalués périodiquement (15 minutes par défaut, réglable) sur les provenances `usage` et `fond` ; l'évaluation n'appelle aucun modèle.
- [ ] CA6 : Un seuil franchi envoie un message Telegram à l'administrateur et un e-mail à `ADMIN_EMAIL` : indicateur, valeur, seuil, fenêtre, lien vers la vue concernée de la PWA d'administration.
- [ ] CA7 : Une alerte déjà ouverte n'est pas renvoyée tant qu'elle n'est pas résolue ; un message de retour à la normale est envoyé une fois ; un rappel quotidien est envoyé tant qu'une alerte de gravité haute reste ouverte.
- [ ] CA8 : Un indicateur calculé sur moins de 20 appels dans sa fenêtre ne déclenche rien.
- [ ] CA9 : L'échec d'un canal n'empêche pas l'autre ; l'échec est journalisé et l'alerte reste marquée non notifiée sur ce canal.
- [ ] CA10 : La PWA d'administration offre une vue « Seuils » : liste, activation, modification de la valeur, historique des 50 dernières alertes.
- [ ] CA11 : Un interrupteur de configuration (`PILOTAGE_ALERTES=non` par défaut) désactive tout envoi ; les alertes restent journalisées.
- [ ] CA12 : Aucune alerte ne contient de contenu de message de jardinier.
- [ ] CA13 : Le rendu de la vue « Seuils » correspond visuellement à la maquette de référence à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse, consultation (services de pilotage, notifications, PWA d'administration)
- Cadrage : `docs/EPIC 18 - PILOTAGE LLM/CADRAGE_PILOTAGE_LLM.md` (numéro d'épic à valider)
- Migration BDD requise : oui
- Dépendances : US-310 ; US-311 et US-318 (maquette de référence) pour la vue « Seuils » ; US-309 pour les seuils de coût
- Décisions liées : D10, D11
- Point ouvert : planification par le mécanisme du veilleur du compagnon (US-266) ou par une unité systemd à minuteur dans `infra/` ; à trancher à l'analyse.
- L'identifiant Telegram de l'administrateur est celui du compte lié à `ADMIN_EMAIL`, sinon une variable `ADMIN_TELEGRAM_ID`.

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given un seuil actif "jetons d'entrée médians par appel agent > +20 % par rapport aux 7 jours précédents"
And la médiane des 7 jours précédents est 6 000
When la médiane du jour atteint 8 900 sur 60 appels
Then je reçois un message Telegram et un e-mail indiquant 8 900, +48 %, et le lien vers la vue Dérives
And une alerte est ouverte dans alertes_pilotage
When l'évaluation suivante mesure encore 8 900
Then aucun nouveau message n'est envoyé
```

**Labels GitHub :** `us`, `admin`, `alertes`, `migration`

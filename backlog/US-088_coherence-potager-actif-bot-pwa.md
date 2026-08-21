**ID :** US-088
**Titre :** Rendre visible dans le bot tout changement de potager actif venu du web
**Épic :** ÉPIC 5 — Cycle de vie du potager

**Story :**
En tant que jardinier utilisant à la fois le bot Telegram et l'application web
Je veux que le bot me dise sur quel potager j'écris dès que celui-ci a changé
Afin de ne jamais enregistrer une récolte dans le mauvais jardin sans m'en apercevoir

**Contexte fonctionnel :**
`docs/CONCEPTION_CYCLE_DE_VIE_POTAGER.md` §4.3, §6.3 et §7.2 (numéro provisoire US-157). Le socle est
déjà en place et ne demande **aucune correction** : le bot résout le `TenantContext` à partir de
`users.potager_actif_id` **à chaque message** (`_resoudre_et_armer_contexte`, US-046), sans cache local
par `chat_id`, et la priorité 0 bis (« utilisateur sans potager actif ») existe déjà sous la forme du
message de blocage d'US-046/CA5. La source de vérité est donc bien unique et partagée.

Ce qui manque est **la visibilité** : le basculement effectué dans la PWA est totalement silencieux
côté Telegram. Un utilisateur qui bascule sur son jardin de vacances depuis le web, puis dicte une
récolte au bot le lendemain, n'a aucun signal — il croit écrire sur son potager habituel. Le risque
augmente mécaniquement avec US-081 (créer un potager additionnel) et US-083 (archivage entraînant une
bascule automatique, donc **non choisie par l'utilisateur**).

Cette US complète le cycle de vie par son garde-fou d'usage quotidien : à chaque changement, un
message court, une seule fois, et le silence total tant que rien ne change.

**Critères d'acceptance :**
- [ ] CA1 : Le bot mémorise, par utilisateur, le dernier potager qu'il lui a annoncé, de façon
      **persistante** (survit à un redémarrage du bot — pas un état en mémoire de conversation)
- [ ] CA2 : Quand le potager actif diffère du dernier annoncé, le bot le signale **une seule fois**,
      avant le traitement du message, sans interrompre ce traitement : la saisie ou la question de
      l'utilisateur est traitée normalement, sur le bon potager
- [ ] CA3 : Le message distingue les deux causes : bascule volontaire (« Tu es passé sur *Jardin de
      Bretagne* depuis le web ») et bascule subie (« *Ancien jardin* a été archivé : tu écris
      maintenant sur *Jardin de Vitry* »)
- [ ] CA4 : Aucun message n'est émis tant que le potager actif ne change pas — un utilisateur mono-potager
      (~85 % des cas) ne voit **jamais** ce message : non-régression stricte de son expérience quotidienne
- [ ] CA5 : Une bascule effectuée depuis le bot lui-même (`/potager`, US-046) ne déclenche pas de
      second message : la confirmation existante suffit et met à jour la mémoire de CA1
- [ ] CA6 : Si le potager actif est devenu invalide entre deux messages (potager archivé, supprimé, ou
      membre retiré) et qu'aucun autre potager n'est disponible, le bot affiche le message d'absence de
      potager existant (US-046/CA5), complété de la raison, et n'enregistre rien
- [ ] CA7 : Symétrie côté PWA : si le potager actif a été archivé, supprimé ou perdu pendant la session,
      le `PotagerGate` bascule proprement sur un autre potager ou sur le parcours d'adhésion, avec un
      message expliquant ce qui s'est passé — jamais d'écran vide ni d'erreur brute
- [ ] CA8 : Zéro appel Groq : la détection est une comparaison en base, réalisée avant toute
      classification d'intention ou transcription

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram + consultation PWA
- Migration BDD requise : **oui, minime** — un champ de mémorisation du dernier potager annoncé par utilisateur (nullable) ; peut être livré dans la même migration qu'US-080 si les deux US sont développées ensemble
- Dépendances : US-046 (potager actif et résolution du `TenantContext` à chaque message), US-080 (états), US-083 (bascule automatique à l'archivage)
- Zéro token Groq
- **Constat de cadrage** : le document de conception demandait aussi que « le bot lise `users.potager_actif_id` à chaque message » et l'ajout d'une priorité 0 bis — les deux sont **déjà implémentés** (US-046). Le périmètre réel de cette US se limite donc à la visibilité du changement et à la symétrie côté PWA. Estimation revue à la baisse en conséquence.

**Notes techniques (pour Persona Developer) :**
- Composants impactés : `bot.py` (`_resoudre_et_armer_contexte` et le message d'annonce), `app/services/potager_actif.py`, `database/models.py`, migration, `frontend/src/App.jsx` (`PotagerGate`), `frontend/src/context/PotagerContext.jsx`
- Ordre critique des flux Telegram à préserver : l'annonce s'insère après la garde de liaison (priorité 0) et après la résolution du contexte, **avant** les modes correction, le mode question et l'analyse du message — jamais entre deux étapes d'un flux de correction en cours
- La distinction « volontaire / subie » (CA3) suppose que l'archivage (US-083) laisse une trace exploitable de la bascule qu'il provoque : à définir avec US-083, sans créer une table dédiée pour si peu
- Échapper les caractères Markdown des noms de potagers (non-régression US-007)

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Bascule effectuée depuis le web
  Given un jardinier membre de "Jardin de Vitry" et "Jardin de Bretagne"
  And il bascule sur "Jardin de Bretagne" depuis l'application web
  When il dicte "j'ai récolté 2 kg de haricots" au bot le lendemain
  Then le bot lui indique d'abord qu'il est passé sur "Jardin de Bretagne" depuis le web
  And la récolte est enregistrée sur "Jardin de Bretagne"
  When il dicte un second événement
  Then aucun message de changement n'est répété

Scénario: Utilisateur mono-potager
  Given un jardinier membre d'un seul potager
  When il envoie plusieurs messages au bot sur plusieurs jours
  Then aucun message de changement de potager ne lui est jamais adressé

Scénario: Bascule subie après archivage
  Given un jardinier dont le potager actif "Ancien jardin" vient d'être archivé
  And il est membre de "Jardin de Vitry"
  When il envoie un message au bot
  Then le bot lui explique que "Ancien jardin" a été archivé et qu'il écrit désormais sur "Jardin de Vitry"

Scénario: Plus aucun potager disponible
  Given un jardinier dont le seul potager a été archivé
  When il envoie un message au bot
  Then le bot lui indique qu'il n'a plus de potager actif et comment en créer ou en rejoindre un
  And rien n'est enregistré

Scénario: Bascule depuis le bot
  Given un jardinier qui bascule de potager via /potager
  When il envoie son message suivant
  Then le bot ne répète pas d'annonce de changement
```

**Labels GitHub :** `us`, `sprint-cycle-vie-potager`, `bot`, `frontend`, `backend`

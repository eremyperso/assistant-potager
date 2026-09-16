**ID :** US-186
**Titre :** Résoudre le client et le modèle LLM par potager, au seul point d'extension de la passerelle
**Épic :** ÉPIC 7 — BYOK : la clé et le modèle du jardinier

**Story :**
En tant que propriétaire d'un potager ayant branché sa clé
Je veux que mes questions partent sur mon fournisseur et mon modèle, et que rien de ce que je paie ne serve à un autre potager
Afin d'utiliser le service que je paie déjà, sans jamais financer les autres

**Contexte fonctionnel :**
Troisième US de l'ÉPIC 7 (document d'épic §2.A, §5.1, §5.3, §7.1 ; « US-172 » dans sa numérotation initiale). C'est l'US qui touche le point de passage de **toutes** les réponses du produit : elle se livre seule.

Vérifié le 15/09/2026 : la passerelle d'US-092 est livrée, et `_resoudre_client(ctx)` (`llm/passerelle.py:246`) retourne aujourd'hui toujours le client plateforme. Elle est appelée à deux endroits, le chat (`:485`) et la transcription (`:553`), **au moment où l'appel part** — la cascade (cache, SQL, savoir) vit dans le routeur et n'entre pas dans la passerelle : la résolution est donc paresseuse par construction, et le point 5 du §10 du document d'épic est levé. Le projet ne calcule **aucun embedding** (point 6 levé) : la question des vecteurs du §7.1 est fermée d'elle-même.

⚖️ **Arbitrage tranché — le cache, asymétrique en faveur du jardinier (annule le CA16 d'US-143).** Une réponse produite sur la clé d'un potager n'entre **jamais** dans le cache partagé ; elle est écrite dans le cache privé du potager. En lecture, le potager continue de bénéficier du cache partagé, alimenté par la plateforme. Isoler aussi la lecture ne renforcerait aucune garantie : cela lui coûterait des appels — une punition présentée comme une protection. 🔶 Au 15/09/2026, **aucune politique RLS n'a été trouvée sur `questions_cache`** (`migration_v36.sql`, `migration_v42.sql`) : sans elle, la séparation est déclarative. Elle entre dans cette US.

Reprend les CA4, CA11, CA12, CA17, CA18, CA19 et CA21 d'US-143.

**Critères d'acceptance :**

*Résolution*
- [ ] CA1 : Le point d'extension existant de la passerelle retourne le client de la configuration du potager si elle existe **et est active**, le client plateforme sinon. **Aucune autre branche** de ce type n'est écrite ailleurs dans le code : l'audit AST d'US-092 est étendu pour le prouver mécaniquement
- [ ] CA2 : Un seul client générique compatible OpenAI, paramétré par adresse de base, clé et modèle. Pas d'adaptateur par fournisseur
- [ ] CA3 : Le **modèle** est résolu par potager au même titre que le client : sans quoi la clé du jardinier partirait sur le modèle de la plateforme et le choix de modèle d'US-187 n'aurait aucun effet
- [ ] CA4 : L'absence de configuration reste le cas normal et n'entraîne **aucune rupture** : le potager utilise le client de la plateforme, exactement comme aujourd'hui
- [ ] CA5 : Le post-traitement robuste des sorties du modèle, acquis de la passerelle, s'applique identiquement aux clés tierces : aucun chemin de traitement séparé pour le BYOK

*Prise d'effet sans redémarrage*
- [ ] CA6 : Une clé modifiée prend effet **à la requête suivante**, dans l'API comme dans le bot, sans redémarrage. Le client mémorisé est indexé par (potager, activation, date de mise à jour) et cette date est relue à **chaque résolution** — les deux processus ayant chacun leur mémoire, une invalidation locale ne suffirait pas
- [ ] CA7 : La lecture de configuration n'a lieu que lorsqu'un appel LLM part réellement : une question servie par le cache, par SQL ou par le savoir ne déclenche ni résolution, ni lecture, ni ligne de journal. Un test le vérifie

*Périmètre*
- [ ] CA8 : La **transcription vocale reste sur la plateforme** pour un potager configuré. L'exclusion est écrite au point de résolution, explicitement — le comportement par défaut contredit la règle, ce n'est donc pas une abstention qui la tient mais une ligne et un test
- [ ] CA9 : Le parsing d'intention et la génération de texte partent sur la clé du potager, par le même point de résolution

*Cache*
- [ ] CA10 : Aucune réponse produite sur une clé de potager n'est écrite dans le cache partagé ; elle est écrite dans le cache privé du potager. Test : après un appel sur la clé du potager A, aucune ligne de cache créée depuis le début du scénario n'est partagée
- [ ] CA11 : Un potager configuré continue de lire le cache partagé
- [ ] CA12 : `questions_cache` est couverte par une politique RLS sur son potager (lignes partagées lisibles par tous, lignes privées par leur seul potager), et par `tests/test_us043_rls_isolation.py`

*Isolation prouvée*
- [ ] CA13 : Deux potagers, une configuration active sur A seulement : les appels de B partent sur le client de la plateforme, et aucun appel n'est effectué sur la clé de A (gabarit `tests/test_isolation_potager.py`)

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : transverse (passerelle LLM, cache de réponses)
- Migration BDD requise : **oui, conditionnelle** — `migration_v49.sql` pour la politique RLS de `questions_cache` (CA12), si son absence est confirmée à l'implémentation. Ne rouvre aucune table d'une US en vol
- Dépendances : **US-092** (livrée), **US-185** (coffre — la résolution ouvre le secret au moment de l'appel), **US-184**
- Annule : le CA16 d'US-143 (cache partagé dans les deux sens)
- Impact tokens : aucun appel ajouté. Le cache privé fait porter au jardinier le coût de ses propres répétitions une seule fois
- Point de vigilance : le message de l'écran de consentement (US-190) dépend de cette règle de cache — il ne se rédige pas avant que cette US soit stabilisée

**Notes techniques (pour Persona Developer) :**
- Le type de retour actuel du point de résolution est le client du SDK Groq. Un client générique compatible OpenAI (adresse de base paramétrable) devient le type commun ; le client plateforme en est un cas particulier
- Coût du CA6 : un SELECT indexé par appel LLM réel, négligeable devant la latence réseau. À mesurer malgré tout
- Le cache privé et la purge à 90 jours existent déjà (`questions_cache`, potager nul = partagé) : rien de nouveau dans le modèle, seulement la règle d'écriture et la RLS

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: La clé d'un potager ne sert jamais à un autre
  Given un potager A avec une configuration active et un potager B sans configuration
  When un jardinier du potager B pose une question de raisonnement
  Then l'appel part sur le client de la plateforme
  And aucun appel n'est effectué sur la clé du potager A

Scénario: Aucune réponse payée par une clé tierce n'entre dans le cache partagé
  Given un potager A avec une configuration active
  When un jardinier du potager A pose une question qui déclenche un appel LLM
  Then la réponse est écrite dans le cache privé du potager A
  And aucune ligne de cache partagée n'a été créée

Scénario: Le potager configuré profite du cache partagé
  Given une réponse déjà présente dans le cache partagé
  When un jardinier d'un potager configuré pose la même question
  Then la réponse vient du cache
  And aucun appel ne part sur sa clé

Scénario: Transcription toujours sur la plateforme
  Given un potager ayant branché sa propre clé
  When le jardinier envoie un message vocal
  Then la transcription est effectuée par le client de la plateforme

Scénario: La clé prend effet sans redémarrage
  Given un potager dont la clé a été remplacée depuis les paramètres
  When le jardinier pose une question juste après
  Then l'appel part sur la nouvelle clé
  And aucun service n'a été redémarré

Scénario: Une question servie sans modèle ne lit aucune configuration
  Given un potager configuré et une question servie par le catalogue SQL
  When la question est posée
  Then aucune lecture de la configuration du potager n'a eu lieu
```

**Labels GitHub :** `us`, `sprint-byok`, `llm`, `security`

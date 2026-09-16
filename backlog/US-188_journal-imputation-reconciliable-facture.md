**ID :** US-188
**Titre :** Tenir un journal d'imputation réconciliable ligne à ligne avec la facture du fournisseur
**Épic :** ÉPIC 7 — BYOK : la clé et le modèle du jardinier

**Story :**
En tant que propriétaire d'un potager ayant branché sa clé
Je veux que chaque appel parti sur ma clé soit tracé avec les compteurs et l'identifiant retournés par mon fournisseur, même quand il a échoué
Afin de pouvoir rapprocher ma facture, ligne à ligne, de ce que l'application a réellement consommé

**Contexte fonctionnel :**
Cinquième US de l'ÉPIC 7 et la plus lourde (document d'épic §6.1 à §6.3 ; « US-174 » dans sa numérotation initiale). C'est elle qui transforme le CA14 d'US-143 de déclaratif en **vérifiable** : le jardinier doit pouvoir prendre la facture de son fournisseur, ouvrir son relevé, et retrouver chaque ligne. Trois propriétés, dans cet ordre de difficulté :

| Propriété | Ce qu'elle exige | Sans elle |
|---|---|---|
| **Complétude** | Tout appel parti sur sa clé écrit sa ligne, y compris en cas d'erreur | Sa facture est plus élevée que son relevé : il conclut au détournement |
| **Exactitude** | Les compteurs viennent de la réponse du fournisseur, jamais d'une estimation locale | Les écarts s'accumulent et rendent le rapprochement impossible |
| **Traçabilité** | Chaque ligne porte l'identifiant de requête retourné par le fournisseur | Le rapprochement reste global au lieu d'être ligne à ligne |

**L'identifiant de requête du fournisseur est la clé de voûte.** Sans lui, la réconciliation est une comparaison de totaux ; avec lui, c'est une jointure. C'est ce détail, et lui seul, qui fait la différence entre « je te montre mes chiffres » et « tu peux vérifier ».

Vérifié le 15/09/2026 dans `conso_tokens` (`database/models.py:866-900`) : la table porte déjà `potager_id`, `user_id`, `date` (jour), `appel_type`, `modele`, `tokens_in`, `tokens_out`, `tokens_cache`, `latence_ms`, `issue`, `cree_le`. Les colonnes « tokens entrée / sortie » et « fonction appelante » du document d'épic **existent donc déjà** sous ces noms : ne pas les dupliquer. Ce qui manque est ce qui rapproche.

Reprend les CA14 et CA20 d'US-143.

**Critères d'acceptance :**

*Modèle de données*
- [ ] CA1 : `conso_tokens` gagne : origine de la clé (`plateforme` | `potager`, non nulle, contrainte de valeurs, valeur `plateforme` rejouée sur l'existant), fournisseur, identifiant de requête du fournisseur, coût estimé en **micro-euros entiers** (de l'argent ne se stocke pas en flottant), version du tarif figée à l'écriture. Un index sert le relevé par potager et par date pour l'origine `potager`
- [ ] CA2 : Chaque ligne porte un horodatage précis **en UTC**, pas seulement un jour : c'est ce que la réconciliation ligne à ligne et la totalisation mensuelle d'US-189 exigent. 🔶 `cree_le` existe sans fuseau explicite : vérifier sa sémantique en production avant de s'y appuyer, et l'expliciter si nécessaire
- [ ] CA3 : La version du tarif est figée à l'écriture : un tarif fournisseur qui change ne réécrit jamais rétroactivement le coût d'un appel passé — sinon le relevé d'un mois clos change tout seul, et la confiance avec

*Complétude*
- [ ] CA4 : La ligne est écrite dans un `finally`, jamais dans le chemin nominal seul : **toujours, même en cas d'échec**. Un appel qui a échoué côté client (délai dépassé après réception, coupure au retour) peut être facturé par le fournisseur — c'est le cas qui détruit la confiance, et la ligne « échec, tokens inconnus » est infiniment plus honnête qu'une ligne absente
- [ ] CA5 : L'issue de l'échec est classée (authentification, quota, délai, refus, réseau, sortie inexploitable) et écrite avec la ligne
- [ ] CA6 : L'écriture du journal ne fait jamais échouer la requête du jardinier — mais n'est **jamais silencieuse** : un échec d'écriture est journalisé en erreur avec l'identifiant de requête du fournisseur, pour être reconstituable
- [ ] CA7 : Le test de clé (US-187) écrit sa ligne comme tout appel, avec son type d'appel propre

*Exactitude*
- [ ] CA8 : Les compteurs de tokens et le modèle **réellement servi** sont lus dans la réponse du fournisseur, jamais estimés localement. Absents de la réponse, ils restent nuls et la ligne le montre — jamais un zéro qui passerait pour une mesure
- [ ] CA9 : L'identifiant de requête du fournisseur est lu dans la réponse (corps ou en-tête, selon le fournisseur) et écrit sur la ligne. Quand un fournisseur ne l'expose pas, la ligne le montre et l'écran d'US-189 explique que le rapprochement se fait alors par date, modèle et tokens

*Invariants*
- [ ] CA10 : Toute ligne d'origine `potager` correspond à une configuration **active à l'horodatage de la ligne** pour ce potager. Cette invariante tourne en contrôle post-migration et en test de non-régression
- [ ] CA11 : Une ligne d'origine `plateforme` ne porte jamais d'identifiant de fournisseur tiers ni de coût estimé au tarif d'un tiers
- [ ] CA12 : La consommation d'un potager en BYOK reste mesurée mais est identifiée comme **hors quota mutualisé** : les requêtes de suivi de plateforme (audit d'US-092 §4) filtrent sur l'origine, et c'est ce qui rendra juste le calcul de coût par utilisateur le jour où un prix sera fixé

*Jalon*
- [ ] CA13 : **Jalon de vérification** avant qu'US-189 soit écrite : un rapprochement réel entre le journal et une facture de fournisseur est déroulé sur un compte de test, et son résultat consigné. Si le rapprochement ligne à ligne n'est pas possible, US-189 est revue **avant** d'être écrite, pas après

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : transverse (passerelle LLM, mesure)
- Migration BDD requise : **oui** — `migration_v50.sql` (ou le numéro suivant disponible à l'implémentation) : colonnes nullables → rejeu de l'existant → contrainte. Ne rouvre aucune table d'une US en vol
- Dépendances : **US-184** (sans elle, le journal inscrit des imputations fausses), **US-186** (c'est au point de résolution que l'origine de la clé est connue)
- Reprend d'US-143 : CA14, CA20 (la colonne d'origine ; l'écran est US-189)
- Impact tokens : zéro — aucun appel ajouté
- Point de vigilance : tous les fournisseurs n'exposent pas l'identifiant au même endroit et tous ne le font pas figurer sur la facture. À vérifier **par fournisseur** de la liste supportée d'US-187, et à documenter dans l'écran plutôt que de le laisser découvrir

**Notes techniques (pour Persona Developer) :**
- L'écriture de mesure existante de la passerelle (`_enregistrer_conso`, qui ne lève jamais) est le point à étendre, pas à doubler
- L'identifiant de requête : `id` du corps de réponse des API compatibles OpenAI, et identifiant de requête dans les en-têtes (accès aux en-têtes bruts du SDK). Les deux sont écrits s'ils existent
- La grille tarifaire par fournisseur et par modèle est une donnée versionnée dans le dépôt, avec sa date ; jamais lue en ligne à l'appel

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Scénario: Une ligne est écrite même quand l'appel échoue
  Given un potager configuré dont le fournisseur coupe la connexion après réception
  When un jardinier pose une question de raisonnement
  Then une ligne d'origine potager est écrite avec l'issue "délai dépassé"
  And ses compteurs de tokens sont absents, pas à zéro

Scénario: Les compteurs viennent du fournisseur
  Given une réponse de fournisseur indiquant 812 tokens en entrée et 143 en sortie
  When l'appel est journalisé
  Then la ligne porte exactement ces valeurs
  And le modèle réellement servi indiqué par le fournisseur

Scénario: L'identifiant de requête permet la jointure
  Given une réponse portant un identifiant de requête
  When l'appel est journalisé
  Then la ligne porte cet identifiant
  And il permet de retrouver la ligne correspondante sur la facture

Scénario: Invariante de configuration active
  Given un relevé de consommation quelconque
  When on inspecte les lignes d'origine potager
  Then chacune a un potager dont la configuration était active à son horodatage

Scénario: Un échec d'écriture du journal ne casse pas la réponse
  Given une base indisponible au moment d'écrire la ligne
  When l'appel LLM a réussi
  Then le jardinier reçoit sa réponse
  And une erreur est journalisée avec l'identifiant de requête du fournisseur
```

**Labels GitHub :** `us`, `sprint-byok`, `llm`, `security`, `rgpd`

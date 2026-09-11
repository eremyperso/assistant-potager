**ID :** US-143
**Titre :** Brancher sa propre clé et son propre modèle d'IA sur son potager
**Épic :** ÉPIC 3 — Fiabilité & coût

**Story :**
En tant que propriétaire d'un potager disposant déjà d'un abonnement à un service d'IA
Je veux brancher ma propre clé et choisir mon modèle
Afin de ne plus dépendre du quota partagé de la plateforme et d'utiliser le service que je paie déjà

**Contexte fonctionnel :**
Douzième et dernière US issue de `docs/ARCHITECTURE_CIBLE_V2_reponses.md` (§6) — la proposition
« US-141 — LLM à la demande / BYOK » de son §9. Elle devient **triviale une fois la passerelle
livrée** : sans point de passage unique, il faudrait câbler le choix du client dans chaque fonction ;
avec elle, c'est une résolution centralisée à un seul endroit.

La quasi-totalité des fournisseurs pertinents exposent une **interface compatible OpenAI** : même
format de requête, même point d'accès. Rendre trois paramètres dynamiques par potager — adresse de
base, clé, nom du modèle — suffit donc, avec un seul client générique.

Au-delà du confort, c'est un levier économique direct : **chaque potager qui branche sa clé sort du
quota mutualisé.** C'est de la capacité financée par l'utilisateur, et une brique du futur modèle
d'abonnement.

> **Note de numérotation.** Voir US-140 : la bande 100 à 133 est réservée à l'ancienne numérotation
> du plan multi-tenant.

**Critères d'acceptance :**

*Configuration*
- [ ] CA1 : Une table `potager_llm_config` porte : référence au potager, fournisseur, adresse de base, modèle, clé **chiffrée**, indicateur d'activation, date de dernière validation réussie, date de création
- [ ] CA2 : La configuration se fait depuis l'écran de paramètres du potager (US-082, livré) et n'est accessible **qu'au propriétaire** du potager (rôles d'US-047). Un membre éditeur ou lecteur ne voit pas cet écran
- [ ] CA3 : Un bouton « Tester la clé » effectue un appel réel minimal et affiche le résultat. Une clé qui échoue au test **n'est jamais enregistrée comme active** ; une clé validée renseigne la date de dernière validation
- [ ] CA4 : L'absence de configuration reste le cas normal et n'entraîne **aucune rupture** : le potager utilise le client de la plateforme, exactement comme aujourd'hui
- [ ] CA17 : Le **modèle** est résolu par potager au même titre que le client. `modele_pour()` lit aujourd'hui un dictionnaire figé à l'import (`llm/passerelle.py:274-278` ← `config.py:72-78`) : sans ce critère, la clé du jardinier partirait sur le modèle de la plateforme, et le CA9 n'aurait aucun effet
- [ ] CA18 : Une clé modifiée depuis la PWA prend effet **à la requête suivante**, dans l'API comme dans le bot, **sans redémarrage de service**. Si les clients tiers sont mis en cache dans le processus, la clé de cache inclut la date de mise à jour de la ligne de configuration, relue à chaque appel — les deux processus ayant chacun leur mémoire, une invalidation locale ne suffirait pas et réintroduirait exactement le défaut du fichier `.env` que cette US supprime

*Sécurité — non négociable*
- [ ] CA5 : La clé est **chiffrée au repos**, avec une clé maîtresse hors base, en variable d'environnement. Elle n'apparaît en clair ni en base, ni dans les journaux, ni dans `texte_original`, ni dans aucune réponse d'API
- [ ] CA6 : L'interface n'affiche jamais la clé complète après enregistrement : seuls les derniers caractères sont visibles, à titre de repère
- [ ] CA7 : Une fuite de la base ne doit pas exposer les clés des utilisateurs — c'est le critère par lequel le chiffrement doit être conçu et relu
- [ ] CA8 : La suppression définitive d'un potager (US-084) supprime sa configuration et sa clé, purge comprise
- [ ] CA19 : L'exclusion de la **transcription** est écrite au point de résolution du client, explicitement. `transcrire()` appelle `_resoudre_client(ctx)` exactement comme le chat (`llm/passerelle.py:553`) : le comportement **par défaut** contredit le CA12, ce n'est donc pas une abstention qui le tient mais une ligne de code et un test — un potager configuré transcrit sur le client de la plateforme
- [ ] CA20 : Le propriétaire peut consulter, depuis les paramètres de son potager, **ce que sa clé a réellement servi** : date, type d'appel, modèle, issue. `conso_tokens` porte déjà `potager_id`, `user_id`, `modele`, `date` et `issue` pour chaque appel (`database/models.py:734-774`) ; une colonne distinguant l'appel tiers de l'appel plateforme suffit à la rendre lisible. C'est ce qui rend le CA14 **vérifiable** au lieu de déclaratif, et c'est la seule forme d'assurance réellement tenable contre l'usage détourné
- [ ] CA21 : L'isolation est prouvée par un test, pas affirmée : deux potagers, une configuration active sur A seulement, et les appels de B partent sur le client de la plateforme (gabarit `tests/test_isolation_potager.py`). S'y ajoute le test « aucune clé dans les journaux » dupliqué de `tests/test_us092_passerelle_llm.py:824-846`, étendu au chemin du test de clé (CA3) et au chemin d'erreur

*Portabilité des prompts — le vrai risque produit*
- [ ] CA9 : Une liste de modèles **testés et supportés** est affichée, distincte des modèles utilisables **aux risques du potager**. Le choix reste libre, l'information est explicite
- [ ] CA10 : Quand un modèle configuré produit une sortie inexploitable (JSON malformé, intention non reconnue de façon répétée), le message servi **désigne clairement la configuration du potager comme cause probable** et propose de revenir au modèle de la plateforme. Sans cela, c'est la plateforme que le jardinier tiendra pour responsable du modèle qu'il a choisi lui-même
- [ ] CA11 : Le post-traitement robuste des sorties du modèle est un acquis de la passerelle et s'applique identiquement aux clés tierces — aucun chemin de traitement séparé n'est créé pour le BYOK

*Périmètre et transparence*
- [ ] CA12 : La **transcription vocale reste assurée par la plateforme** en version 1, même pour un potager ayant branché sa clé. L'écran le dit explicitement. Le BYOK ne couvre que la génération de texte
- [ ] CA13 : Un consentement explicite est recueilli et horodaté à l'activation : les données du potager seront transmises au fournisseur choisi, selon les conditions de ce fournisseur, qui est nommé. Le consentement est révocable en désactivant la configuration
- [ ] CA14 : La consommation d'un potager en BYOK reste **mesurée** (US-092 / CA5) mais est identifiée comme hors quota mutualisé de la plateforme — c'est ce qui rendra le calcul de coût par utilisateur juste au moment de fixer un prix
- [ ] CA16 : Un potager en BYOK **reste dans l'échange du cache partagé** (`questions_cache` figée, `potager_id NULL`, 90 jours) : ses appels peuvent servir à d'autres potagers, et il bénéficie des réponses payées par la plateforme. L'écran de consentement du CA13 le dit **dans les deux sens**, en toutes lettres. Aucun code n'est écrit pour ce critère : c'est une phrase d'interface, et un test qui vérifie qu'elle y est

*Comportement en cas d'échec*
- [ ] CA15 : Si le fournisseur du potager échoue ou refuse l'appel, il n'y a **aucun repli silencieux vers la clé de la plateforme** : le message est explicite et propose soit de réessayer, soit de désactiver la configuration. Les fonctions déterministes continuent de fonctionner, comme dans tout mode dégradé (US-092 / CA10)

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (paramètres PWA) | transverse (résolution du client dans la passerelle)
- Migration BDD requise : **oui** — création de `potager_llm_config` (⚠️ vérifier le numéro de la dernière migration au moment de l'implémentation), idempotente, rollback documenté
- **Arbitrage tranché — pas de repli silencieux sur la plateforme (CA15) :** un repli invisible ferait payer à la plateforme la panne du fournisseur choisi par l'utilisateur, et enverrait ses données à un service auquel il n'a pas consenti pour cet appel. L'échec explicite est à la fois plus honnête et moins coûteux
- **Arbitrage tranché — la voix reste sur la plateforme :** gérer la disparité des fournisseurs sur l'audio pour un quota généreux et un coût faible n'a aucun intérêt en version 1. Le sujet se rouvrira si le quota de transcription devient le premier point de saturation, ce que le document d'architecture juge probable
- **Arbitrage tranché — aucune action serveur par potager, une seule à la livraison :** la configuration vit en base et prend effet à la requête suivante, comme le `PATCH /potagers/{id}` d'US-082 (`main.py:893`) ; le point de résolution du client existe déjà et reçoit le potager à **chaque** appel (`llm/passerelle.py:246-253`, appelé en `:485` et `:553`). Seule la clé maîtresse de chiffrement du CA5 est une variable d'environnement, et `config.py:1-6` ne lit l'environnement qu'à l'import : un `systemctl restart potager-<env> potager-<env>-bot` est donc nécessaire **au déploiement de cette US et à chaque rotation de cette clé maîtresse** (`docs/RUNBOOK_DEPLOIEMENT_PRODUCTION.md:470-474`), jamais au branchement d'une clé de jardinier
- **Arbitrage tranché — le potager en BYOK reste dans le pot commun du cache (CA16) :** l'isoler des deux côtés lui coûterait des appels que la plateforme lui sert gratuitement, et ne l'isoler que d'un côté compliquerait le code pour un gain économique marginal. Le prix de cette simplicité est la transparence : l'écran de consentement l'annonce, il ne le laisse pas découvrir
- **Arbitrage tranché — ce que le chiffrement protège, et ce qu'il ne protège pas :** le CA5 couvre la fuite de base (CA7), pas la plateforme elle-même — au moment de l'appel le processus détient la clé en clair, et le rôle propriétaire de la base n'est pas soumis à RLS (`migrations/migration_v18.sql:106-107`). Les garanties réellement tenables face à « ma clé sera-t-elle détournée ? » sont donc le **périmètre** (un seul point de résolution, prouvé mécaniquement par l'audit AST d'US-092), la **visibilité** (CA20), la **réversibilité** (CA13) et la **limitation** (CA12/CA19). L'écran ne promet rien de plus que cela
- **Arbitrage tranché — le propriétaire seul configure :** une clé d'API est un engagement financier personnel. La confier au niveau du potager partagé, sans restriction de rôle, exposerait son propriétaire aux dépenses des autres membres
- Dépendances : **US-092** (passerelle, bloquante — l'US n'a aucun sens sans elle), **US-082** (écran de paramètres, livré), **US-047** (rôles, livré). Rattachement RGPD : le consentement du CA13 s'intègre aux traitements de l'US RGPD (US-132 du plan initial)
- Invariants projet : aucun secret dans les journaux ; migration idempotente avec rollback ; isolation inter-potagers (une configuration ne s'applique qu'à son potager)

**Notes techniques (pour Persona Developer) :**
- La résolution du client se fait au **seul point d'extension prévu par US-092** : configuration du potager si elle existe et est active, client plateforme sinon. Aucune autre branche dans le code
- Un seul client générique compatible OpenAI, paramétré par adresse de base, clé et modèle — ne pas écrire un adaptateur par fournisseur
- Le test de clé du CA3 doit être le plus petit appel possible ; il compte comme consommation chez le fournisseur du potager, jamais chez la plateforme
- La clé maîtresse de chiffrement doit être documentée comme secret d'exploitation, avec la procédure de rotation : un chiffrement dont la clé n'est jamais renouvelable n'est qu'un délai
- Prévoir le cas d'une clé révoquée côté fournisseur : elle produit un échec d'authentification, traité comme le CA15, et la date de dernière validation permet d'expliquer au jardinier depuis quand sa configuration ne fonctionne plus
- **Aucun précédent de chiffrement applicatif n'existe dans le projet** : `cryptography` n'est présent que transitivement via `python-jose[cryptography]`, et le seul secret stocké aujourd'hui l'est en **hachage à sens unique** (`database/models.py:61-66`), ce qui ne transpose pas à une clé qui doit rester réversible. Le CA5 se construit donc de zéro, sa procédure de rotation sur le gabarit documentaire de `JWT_SECRET` (`docs/RUNBOOK_DEPLOIEMENT_PRODUCTION.md:354`)
- **`conso_tokens` n'est pas purgée avec le potager** (`app/services/potagers.py:500-523`) alors que sa clé étrangère est `NOT NULL REFERENCES potagers(id)` (`migrations/migration_v31.sql:34`) : le CA8 butera dessus. La ligne s'ajoute au dictionnaire `volumes` **et** à l'assert de `tests/test_us084_suppression_definitive_potager.py:391-394` — c'est cet assert, et non la vigilance, qui garantit qu'aucune table n'est oubliée. `potager_llm_config` entre au même endroit
- **Deux fuites d'imputation à fermer avant de facturer quoi que ce soit à la clé d'un jardinier** : `default_context()` retombe sur le **potager #1 en dur** (`app/services/context.py:38-40`), donc tout appel sur un chemin non armé lui serait facturé ; et `tools/rejeu_corpus.py --mode cascade` a `--potager 1` par défaut (`:259`), ce qui ferait payer un rejeu de corpus par un jardinier
- **Migration** : la dernière livrée est `migration_v45.sql` (US-165) — `potager_llm_config` sera `migration_v46.sql`, sur le gabarit idempotent + rollback + contrôles post-migration de `migration_v44.sql`, et **sous RLS** comme les tables tenant de v18/v42/v43/v45, pour être couverte par `tests/test_us043_rls_isolation.py`

**Estimation :** 13 points

> **Révision du 11/09/2026.** 8 points à la rédaction initiale. Les critères CA16 à CA21, ajoutés
> après relecture du code, sont pour l'essentiel des contraintes de conception et des tests
> (CA17, CA18, CA19, CA21) — sauf le **CA20**, qui ajoute une colonne à `conso_tokens`, un endpoint
> et une rubrique d'écran. S'y ajoutent deux dettes à solder en chemin, sans quoi les CA8 et CA14
> sont faux : `conso_tokens` absente de la purge, et le repli sur le potager #1.

**Scénario Gherkin :**
```gherkin
Scénario: Branchement d'une clé personnelle
  Given un propriétaire de potager disposant d'une clé chez un fournisseur compatible
  When il la saisit dans les paramètres de son potager et lance le test
  Then la clé est validée et enregistrée chiffrée
  And les questions de son potager partent désormais sur son modèle

Scénario: Clé invalide refusée
  Given une clé erronée saisie dans les paramètres
  When le test est lancé
  Then l'échec est affiché
  And aucune configuration active n'est enregistrée

Scénario: Aucune configuration, aucun changement
  Given un potager sans configuration d'IA
  When un jardinier pose une question
  Then l'appel part sur le client de la plateforme
  And rien ne change pour lui

Scénario: Clé jamais exposée
  Given une configuration enregistrée
  When le propriétaire revient sur l'écran de paramètres
  Then seuls les derniers caractères de la clé sont visibles
  And aucune réponse d'API ne contient la clé

Scénario: Membre non propriétaire
  Given un membre éditeur d'un potager partagé
  When il ouvre les paramètres du potager
  Then l'écran de configuration de l'IA ne lui est pas accessible

Scénario: Modèle non supporté produisant des sorties inexploitables
  Given un potager configuré sur un modèle hors liste supportée
  When ce modèle renvoie des sorties inexploitables de façon répétée
  Then le message désigne la configuration du potager comme cause probable
  And il propose de revenir au modèle de la plateforme

Scénario: Fournisseur du potager en panne
  Given un fournisseur configuré qui refuse tous les appels
  When le jardinier pose une question de raisonnement
  Then il reçoit un message explicite sur sa configuration
  And aucun appel n'est effectué sur la clé de la plateforme
  And ses commandes déterministes continuent de fonctionner

Scénario: Transcription vocale toujours assurée par la plateforme
  Given un potager ayant branché sa propre clé
  When le jardinier envoie un message vocal
  Then la transcription est effectuée par la plateforme
  And l'écran de configuration l'indiquait explicitement

Scénario: Le partage du cache est annoncé avant le consentement
  Given un propriétaire sur le point d'activer sa configuration
  When il lit l'écran de consentement
  Then il y est écrit que ses appels peuvent servir à d'autres potagers
  And qu'il bénéficie en retour des réponses payées par la plateforme

Scénario: La clé d'un potager ne sert jamais à un autre
  Given un potager A avec une configuration active et un potager B sans configuration
  When un jardinier du potager B pose une question de raisonnement
  Then l'appel part sur le client de la plateforme
  And aucun appel n'est effectué sur la clé du potager A

Scénario: La clé prend effet sans redémarrage
  Given un potager dont la clé a été remplacée depuis les paramètres
  When le jardinier pose une question juste après
  Then l'appel part sur la nouvelle clé
  And aucun service n'a été redémarré
```

**Labels GitHub :** `us`, `sprint-fiabilite-cout`, `llm`, `security`, `pwa`, `rgpd`

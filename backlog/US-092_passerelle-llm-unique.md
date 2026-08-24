**ID :** US-092
**Titre :** Faire transiter tout appel au LLM par une passerelle unique
**Épic :** ÉPIC 3 — Fiabilité & coût

**Story :**
En tant qu'administrateur de la plateforme
Je veux que chaque appel à un modèle de langage passe par un point unique qui le type, le mesure et sait échouer proprement
Afin de pouvoir mesurer le coût par potager, garantir que l'application reste utile quand le quota est saturé, et rendre possible le branchement d'un modèle tiers

**Contexte fonctionnel :**
Première US issue de `docs/ARCHITECTURE_CIBLE_V2_reponses.md` (§6.1, §6.4, §7.2). Elle correspond au
socle de l'US-121 du plan initial (`docs/BACKLOG_US_MULTITENANT.md`, numérotation héritée — voir
`README.md` §mapping) et **conditionne les onze US suivantes** : sans point de passage unique, la
mesure de consommation, le mode dégradé et le BYOK devraient être recâblés dans chaque fonction.

Aujourd'hui les appels au modèle sont dispersés (classification d'intention, parsing d'action,
réponse aux questions, transcription vocale). Trois conséquences : aucune mesure consolidée de
consommation par potager, aucun comportement défini quand le fournisseur renvoie un **429 (quota
dépassé)**, et aucun endroit où brancher la clé d'un potager. Cette US ne change **rien** au
comportement perçu par le jardinier en fonctionnement nominal : c'est une réorganisation des appels
existants, plus le filet de sécurité qui manque.

**Le principe directeur de toute l'architecture cible, à porter dès cette US :** *le LLM est la
ressource de dernier recours, pas le moteur central.* La passerelle est l'endroit qui rend ce
principe mesurable.

**Critères d'acceptance :**

*Point de passage unique*
- [ ] CA1 : Un module de passerelle unique concentre tous les appels au fournisseur de modèles. Un audit explicite, documenté dans l'US, atteste qu'**aucun appel direct au client Groq ne subsiste** ailleurs dans le code applicatif — c'est la condition qui rend vraies toutes les US suivantes
- [ ] CA2 : Chaque appel déclare un **type** (`classification`, `parsing`, `question`, `synthese`, `transcription`) et porte le contexte de tenant (`potager_id`, `user_id`). Aucun appel anonyme n'est possible : un appel sans contexte échoue explicitement plutôt que d'être compté nulle part
- [ ] CA3 : Le modèle utilisé est **configurable par type** (variables d'environnement) : parsing et synthèse sur le grand modèle, classification sur le petit modèle rapide. Changer de modèle pour un type est un changement de configuration, jamais un changement de code — c'est ce qui permettra la répartition multi-modèles, les quotas Groq étant comptés *par modèle*
- [ ] CA4 : La transcription vocale passe elle aussi par la passerelle, comme type `transcription`, même si elle conserve son propre client et son propre quota — sans quoi la première saturation réelle du service, le quota Whisper, resterait invisible

*Mesure*
- [ ] CA5 : Chaque appel alimente une table `conso_tokens` (`potager_id`, `date`, `appel_type`, `modele`, `tokens_in`, `tokens_out`, `latence_ms`, `issue`) — nom et colonnes repris du cadrage initial d'US-123 pour ne pas créer une table concurrente. Cette US **mesure** ; elle ne plafonne pas : les quotas et le blocage restent hors périmètre
- [ ] CA6 : Les prompts sont assemblés **partie fixe en tête, variables en fin**, afin que le cache de prompt du fournisseur s'applique. Les jetons servis depuis ce cache sont distingués dans la mesure dès que le fournisseur les expose — c'est le levier de capacité n°1 et il est presque gratuit
- [ ] CA7 : Un ordre de grandeur de consommation avant / après est mesuré et consigné (invariant projet : impact tokens chiffré et loggé pour tout appel LLM)

*Mode dégradé — invariant, pas option*
- [ ] CA8 : Un **429** du fournisseur est intercepté par la passerelle et converti en exception typée. Il ne remonte jamais brut jusqu'à l'utilisateur, et ne provoque jamais de trace d'erreur non gérée
- [ ] CA9 : Chaque appelant déclare son comportement de repli. À défaut de repli utile, le message servi au jardinier est explicite et invariable : « L'analyse avancée par IA est temporairement indisponible, réessaie dans quelques minutes » — jamais un silence, jamais un plantage, jamais une réponse inventée
- [ ] CA10 : Un test de non-régression exécute le parcours complet avec le fournisseur simulé en 429 permanent, et vérifie que **restent fonctionnels** : les commandes déterministes, `/stats`, `/plan`, `/historique`, le stock, la météo et la consultation web. Le LLM ne doit jamais être un point de défaillance unique fonctionnel
- [ ] CA11 : Les en-têtes de limitation de débit renvoyés par le fournisseur sont lus et journalisés, afin de pouvoir freiner *avant* le 429 plutôt que de le subir. L'action de freinage elle-même relève de l'US de quotas ; ici on collecte la matière
- [ ] CA12 : Une seule nouvelle tentative au maximum, avec temporisation respectant l'en-tête `Retry-After`, sur 429 et 5xx. Au-delà, on bascule en mode dégradé. Un délai maximal par appel est configuré : un appel qui n'aboutit pas emprunte le même chemin de repli qu'un 429

*Étanchéité*
- [ ] CA13 : Aucune clé, aucun secret, aucun contenu complet de `texte_original` n'apparaît dans les journaux de la passerelle. Ces journaux portent des métadonnées de consommation, pas des contenus

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : transverse (interaction Telegram, enregistrement, analyse, consultation) — US d'infrastructure applicative, sans surface utilisateur nouvelle
- Migration BDD requise : **oui** — création de `conso_tokens` (dernière migration constatée à la rédaction : `migration_v30.sql` ; ⚠️ vérifier le numéro au moment de l'implémentation), idempotente, rollback documenté
- **Arbitrage tranché — mesurer avant de plafonner :** cette US crée la table de consommation et s'arrête là. Les budgets par potager, le blocage au dépassement et le message d'incitation à l'abonnement restent au périmètre de l'US de quotas (US-123 du plan initial, non encore rédigée sous la numérotation réelle). Séparer la mesure du plafonnement permet de disposer d'un mois de données réelles avant de fixer un prix
- **Arbitrage tranché — la transcription entre dans la passerelle mais garde sa clé :** le BYOK de la voix est explicitement écarté en v1 (voir US-143 / CA7). La faire passer par la passerelle malgré tout ne coûte presque rien et rend visible le quota qui saturera probablement le premier en usage vocal
- **Arbitrage tranché — pas de repli silencieux entre modèles :** en cas de 429, on dégrade fonctionnellement (CA9), on ne rejoue pas l'appel sur un autre modèle en douce. Un repli invisible masquerait précisément la saturation que cette US existe pour rendre visible
- Dépendances : **US-041** (couche services, livrée), **US-042** (scoping, livrée). Aucune dépendance bloquante — c'est la première brique de la cascade
- Invariants projet : prompts en `.replace()` jamais `.format()` ; `db.get()` jamais `db.query().get()` ; journalisation structurée `HH:MM:SS │ LEVEL │ emoji` conservée ; ordre critique des flux de conversation inchangé — cette US ne touche pas au routage, seulement à la sortie vers le fournisseur

**Notes techniques (pour Persona Developer) :**
- Le remplacement des appels directs doit être fait **à comportement constant** : mêmes prompts, mêmes modèles qu'aujourd'hui à la livraison. Le changement de modèle par type (CA3) est rendu *possible* ici, il est *exercé* dans US-093
- L'exception typée de quota doit être distincte d'une exception réseau ou d'un délai dépassé : les trois mènent au même repli utilisateur mais doivent rester distinguables dans les journaux, faute de quoi le diagnostic de saturation devient impossible
- Prévoir dès maintenant le point d'extension « quel client pour ce potager ? » (US-143) sans l'implémenter : une fonction de résolution qui retourne aujourd'hui toujours le client plateforme
- Le test du CA10 est le plus structurant de l'US : il doit couvrir le bot **et** l'API, le 429 pouvant survenir des deux côtés

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Consommation mesurée par potager
  Given un jardinier du potager "Jardin de Vitry" qui pose une question analytique
  When la réponse est produite via un appel au modèle
  Then une ligne de consommation est enregistrée pour ce potager
  And elle porte le type d'appel, le modèle, les jetons entrants et sortants

Scénario: Quota du fournisseur saturé
  Given un fournisseur qui répond 429 à tout appel
  When un jardinier demande une analyse avancée
  Then il reçoit le message d'indisponibilité temporaire
  And aucune erreur technique n'est affichée

Scénario: L'application reste utile sans IA
  Given un fournisseur qui répond 429 à tout appel
  When un jardinier consulte ses statistiques, son plan de parcelles et sa météo
  Then les trois réponses lui parviennent normalement
  And aucune d'elles n'a nécessité d'appel au modèle

Scénario: Changement de modèle sans changement de code
  Given une configuration qui associe le type "classification" à un modèle rapide
  When une classification est demandée
  Then l'appel part sur le modèle rapide
  And la consommation est imputée à ce modèle

Scénario: Aucun appel hors passerelle
  Given le code applicatif livré
  When l'audit des appels au fournisseur est exécuté
  Then aucun appel direct au client du fournisseur n'existe en dehors de la passerelle
```

**Labels GitHub :** `us`, `sprint-fiabilite-cout`, `llm`, `infrastructure`, `observabilite`

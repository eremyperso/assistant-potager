**ID :** US-098
**Titre :** Doter l'assistant d'une base de connaissance interrogeable en recherche plein texte
**Épic :** ÉPIC 3 — Fiabilité & coût

**Story :**
En tant que jardinier
Je veux que l'assistant puisse retrouver un savoir écrit et vérifié plutôt que de répondre de mémoire
Afin de recevoir des réponses fondées et traçables, et non la culture générale approximative d'un modèle de langage

**Contexte fonctionnel :**
Septième US issue de `docs/ARCHITECTURE_CIBLE_V2_reponses.md` (§4) — étage 2 de la cascade, et brique
la plus nouvelle du document. Elle correspond à la proposition « US-140 — base de connaissance + RAG
scopé » de son §9. C'est ce qui fait passer l'application du **carnet** au **conseiller**.

Cette US livre **le contenant, pas le contenu** : les tables, la recherche, l'isolation, l'outil
d'ingestion et le contrat de retour. Les trois familles de connaissance sont remplies par les US
suivantes — fonctionnement de l'application (US-099), agronomie (US-140), mémoire du potager
(US-141) — pour une raison de séquencement : le contenu est un travail éditorial long, la mécanique
est un travail technique court, et il n'y a aucune raison de les livrer ensemble.

**Deux décisions de conception sont reprises telles quelles du document, et ne sont pas rouvertes :**
- **Recherche plein texte d'abord, sémantique ensuite.** La recherche lexicale PostgreSQL en
  français est excellente sur le vocabulaire précis du jardinage (« mildiou tomate », « purin de
  consoude », « mise en godet ») et n'ajoute **aucune dépendance** au projet. La colonne d'embedding
  est créée dès maintenant, à coût nul, et reste vide jusqu'au jour où la recherche sémantique sera
  activée.
- **Le RAG ne rédige jamais.** Il retourne des passages, leurs sources et un score de confiance. La
  génération reste au seul étage 3, via la passerelle.

**Critères d'acceptance :**

*Structure*
- [ ] CA1 : Une table `knowledge_documents` porte : `potager_id` (nul = savoir global partagé), `titre`, `famille` (`agronomie`, `doc_app`, `memoire_potager`), `source`, `niveau_confiance` (`verifie` ou `indicatif`), dates de création et de mise à jour
- [ ] CA2 : Une table `knowledge_chunks` porte : référence au document, `potager_id` dénormalisé pour le filtrage direct, `contenu`, `culture`, `type` (`maladie`, `semis`, `association`, `rotation`…), `saison`, un vecteur de recherche plein texte, et une colonne d'embedding **créée, nullable et inutilisée**
- [ ] CA3 : Le motif de séparation est celui, déjà éprouvé sur `culture_config`, du `potager_id` nullable : nul signifie partagé entre tous les potagers, une valeur signifie privé. Une seule fiche « tomate » sert ainsi tous les jardins

*Recherche*
- [ ] CA4 : La recherche est une recherche plein texte PostgreSQL en **dictionnaire français**, avec index adapté ; les temps de réponse sont mesurés et restent sous le seuil de perception
- [ ] CA5 : **Toute** recherche filtre `potager_id IS NULL OR potager_id = :potager_courant`. Il n'existe aucun chemin de code capable d'interroger la table sans ce filtre
- [ ] CA6 : Les métadonnées détectées par le routeur (culture, type de question) restreignent la recherche quand elles sont présentes, et sont ignorées quand elles ne le sont pas — jamais un filtre qui vide le résultat
- [ ] CA7 : Les résultats sont classés et assortis d'un **score de confiance global**. Deux issues, et deux seulement : confiance élevée sur une question factuelle, la réponse est servie directement à coût nul ; sinon, le contexte descend vers l'étage 3 (US-142)
- [ ] CA8 : La fonction de recherche retourne un objet de contexte — passages, sources, score — et **jamais une réponse rédigée**. Un test vérifie qu'aucun appel au modèle n'a lieu dans ce chemin

*Isolation — invariant*
- [ ] CA9 : Un test d'isolation dédié démontre qu'un fragment privé du potager A n'apparaît jamais dans une recherche effectuée pour le potager B, y compris quand la question est formulée pour le provoquer. Ce test a le même statut que le test d'isolation des événements (US-042)

*Ingestion et versionnement*
- [ ] CA10 : Un outil d'ingestion transforme des documents Markdown versionnés dans le dépôt en documents et fragments. Il est **idempotent et rejouable** : réingérer un document inchangé ne crée pas de doublon
- [ ] CA11 : Réingérer un document **modifié** remplace ses fragments et **invalide les réponses figées qui en dérivaient** (US-095 / CA10). Corriger une fiche ne doit pas laisser survivre des mois une réponse erronée
- [ ] CA12 : Le découpage produit des fragments autonomes : une idée répondable par fragment, contexte du titre du document conservé. Un fragment qui n'a de sens qu'avec le précédent est un défaut de découpage

*Qualité mesurée*
- [ ] CA13 : Un corpus d'au moins 30 questions de savoir réelles est constitué avec le fragment attendu pour chacune ; la cible est que **le bon fragment figure dans les trois premiers résultats**. Cette mesure conditionne l'activation de l'étage en production
- [ ] CA14 : Chaque recherche est journalisée (US-097) avec son score et son issue, afin d'identifier les questions qui ne trouvent rien : ce sont elles qui définissent le contenu à écrire ensuite

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse | consultation
- Migration BDD requise : **oui** — création de `knowledge_documents` et `knowledge_chunks` en fichier séparé, idempotente (`IF NOT EXISTS`), rollback documenté (⚠️ vérifier le numéro de la dernière migration au moment de l'implémentation)
- **Arbitrage tranché — pas de pgvector à ce stade :** aucune extension nouvelle, aucune dépendance nouvelle. La colonne d'embedding est créée vide pour éviter une migration lourde le jour venu. L'activation de la recherche sémantique sera décidée quand la mesure du CA13 montrera que les questions de diagnostic mal formulées échouent réellement — pas avant
- **Arbitrage tranché — pas de reclassement fin ni de techniques avancées :** reclassement par second passage, auto-évaluation, questions hypothétiques, interrogations multiples systématiques sont tous écartés. Ils ajoutent latence et jetons, à contre-emploi de l'objectif de rapidité, et ne se justifieront que le jour où la qualité de la recherche plafonnera
- **Arbitrage tranché — le contenu vit dans le dépôt, pas dans la base :** la base est l'index, le dépôt est la source. Les fiches sont relues, versionnées et corrigées comme du code. Une base éditable en ligne serait un chantier d'interface d'administration sans valeur à ce stade
- Dépendances : **US-093** (aiguillage vers l'étage savoir). Prérequis de **US-099**, **US-140**, **US-141**, **US-142**
- Invariants projet : isolation inter-potagers testée ; migration idempotente avec rollback ; `db.get()` jamais `db.query().get()`

**Notes techniques (pour Persona Developer) :**
- Le filtre du CA5 doit être porté par la fonction de recherche elle-même, à un seul endroit, et non répété par chaque appelant — c'est la seule façon de rendre l'affirmation « aucun chemin ne peut l'oublier » vraie et vérifiable
- Le vecteur de recherche plein texte doit être maintenu à l'écriture du fragment, pas calculé à chaque requête
- La configuration du dictionnaire français doit être explicite dans la migration : un index construit sur la configuration par défaut donnerait des résultats muets sur les accents et la lemmatisation
- L'outil d'ingestion est un utilitaire du répertoire d'outils du projet, exécutable à la main et depuis un déploiement, sur le modèle de l'outil de purge existant

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Scénario: Question de savoir répondue sans IA
  Given une base de connaissance contenant une fiche sur le cul noir de la tomate
  When un jardinier demande "pourquoi mes tomates ont le cul noir ?"
  Then les passages pertinents sont retrouvés par la recherche plein texte
  And aucun appel au modèle n'a lieu

Scénario: Le RAG ne rédige pas
  Given une recherche qui retourne trois passages pertinents
  When l'étage du savoir produit son résultat
  Then il retourne des passages, des sources et un score de confiance
  And il ne retourne aucune réponse rédigée

Scénario: Confiance faible transmise à l'étage supérieur
  Given une question dont aucun passage ne ressort avec un score élevé
  When l'étage du savoir a terminé
  Then le contexte est transmis à l'étage de raisonnement
  And la question n'est pas déclarée sans réponse

Scénario: Isolation d'un savoir privé
  Given un fragment privé appartenant au potager A
  When un membre du potager B pose une question qui correspond exactement à ce fragment
  Then aucun résultat issu du potager A ne lui est retourné

Scénario: Réingestion sans doublon
  Given un document déjà ingéré
  When l'outil d'ingestion est relancé sans modification du document
  Then aucun fragment supplémentaire n'est créé

Scénario: Correction d'un document
  Given un document déjà ingéré et une réponse figée qui en dérive
  When le document est corrigé puis réingéré
  Then ses anciens fragments sont remplacés
  And la réponse figée dérivée est invalidée
```

**Labels GitHub :** `us`, `sprint-fiabilite-cout`, `rag`, `connaissance`, `analyse`

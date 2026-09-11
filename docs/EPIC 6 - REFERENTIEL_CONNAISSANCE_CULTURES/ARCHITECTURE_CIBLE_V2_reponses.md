# 🌿 Assistant Potager — Architecture cible V2 : moteur de réponses

> **Statut :** 📝 Document de cadrage technique — à décliner en US par l'agent PO
> **Rédigé le :** 17/08/2026
> **Portée :** ce qui est actionnable maintenant — cascade de résolution, RAG potager, personnalisation contextuelle, LLM à la demande (BYOK). La couche proactive (moteur d'insights) est décrite en **Annexe A**, comme jalon suivant.
> **Niveau :** conceptuel — schémas de tables et pseudo-flux, pas de code d'implémentation (celui-ci relève de Claude Code, sur la base des US).
> **Sources :** `BACKLOG_US_MULTITENANT.md` (Épic 3), `REFLEXION_STRATEGIQUE_multi_utilisateurs.md`, `Étude ChatGPT — RAG`, `EPIC_CALENDRIER_CULTURAL.md`.
> **Convention de lecture :** ✅ fait établi · 🔶 hypothèse à valider · 🧪 à tester.

---

## 1. Le problème et les objectifs

L'application est aujourd'hui un excellent **journal d'événements** : elle enregistre le réel sans friction, à la voix. Mais son moteur de réponse aux questions (`_ask_question`) charge tout l'historique et l'envoie au LLM — ~5 000 tokens par question, lent, non scopé, et sans aucune connaissance agronomique. Trois conséquences : c'est **coûteux** (saturation du quota Groq), c'est **lent**, et c'est **générique** (le LLM répond depuis sa culture générale, pas depuis le contexte du potager).

Ce document décrit l'architecture cible qui répond à quatre objectifs, dans cet ordre de priorité :

| Objectif | Ce que ça veut dire concrètement |
|---|---|
| **Rapidité** | La majorité des réponses ne doivent plus attendre un aller-retour LLM. |
| **RAG potager** | L'assistant doit disposer d'une vraie base de connaissance (agronomie, maladies, fonctionnement de l'app), interrogeable. |
| **Personnalisation** | Une réponse doit tenir compte des événements réels, de la localisation, de la météo et de l'historique du potager qui pose la question. |
| **LLM à la demande** | Un potager qui a déjà un abonnement IA doit pouvoir brancher sa propre clé et son propre modèle. |

**Le principe directeur qui unifie tout le document :** *le LLM devient la ressource de dernier recours, pas le moteur central.* Chaque réponse qu'on peut produire sans lui est un gain simultané sur les trois premiers objectifs — plus rapide, moins chère, et souvent plus juste parce que déterministe.

Ce n'est **pas** une refonte. L'architecture événementielle, l'agent SQL et le scoping `potager_id` existants sont précisément ce qui rend cette cible atteignable. On ajoute une **couche de routage et de connaissance au-dessus de l'existant**.

---

## 2. Vue d'ensemble : la cascade de résolution

Toute demande entrante (vocale ou texte) traverse une cascade d'étages, du moins cher au plus cher. **Chaque étage plus coûteux n'est atteint que si le précédent n'a pas su répondre.** Dès qu'un étage produit une réponse de confiance suffisante, la cascade s'arrête.

```
                        DEMANDE (voix → Whisper → texte, ou texte direct)
                                        │
                                        ▼
                          ┌───────────────────────────┐
                          │   ROUTEUR / CLASSIFICATION  │   ← IA légère (8B) OU règles
                          │   commande ? data ? savoir ?│      selon le cas
                          └──────────────┬──────────────┘
                                         │
     ┌───────────────┬───────────────────┼───────────────────┬───────────────────┐
     ▼               ▼                   ▼                   ▼                   ▼
 ÉTAGE 0         ÉTAGE 0bis           ÉTAGE 1             ÉTAGE 2             ÉTAGE 3
 COMMANDE        CACHE                DATA (SQL)          SAVOIR (RAG)        LLM
 déterministe    question type        agrégation          recherche           raisonnement,
 (/stats, /plan) réponse mémorisée    scopée potager      hybride +           synthèse,
                                                          contexte potager     diagnostic
     │               │                   │                   │                   │
     ▼               ▼                   ▼                   ▼                   ▼
 Services /      Table cache         PostgreSQL          knowledge_chunks    LLM Gateway
 PostgreSQL      (0 token)           (0 token LLM)       (0 token LLM en      → Groq plateforme
 (0 token)                                                lecture seule)         OU clé du potager
                                                              │                     │
                                                              └─── contexte ────────┘
                                                                   pertinent
```

Le tableau ci-dessous donne la clé de lecture — quel type de demande s'arrête à quel étage :

| Étage | Coût LLM | Traite | Exemple |
|---|---|---|---|
| **0 — Commande** | 0 | Commandes connues, actions déterministes | `/stats`, `/historique`, saisie « récolté 2 kg tomates » parsable sans LLM |
| **0bis — Cache** | 0 | Questions types déjà vues, réponse mémorisée | « stock tomates ? », « dernière récolte ? » |
| **1 — Data (SQL)** | 0 | Questions sur *les données du potager* | « combien de courgettes récoltées cet été ? », « quand ai-je semé les carottes ? » |
| **2 — Savoir (RAG)** | 0 en lecture | Questions de *connaissance* (agronomie, maladies, fonctionnement app) | « pourquoi mes tomates ont le cul noir ? », « comment fonctionne le stock ? » |
| **3 — LLM** | coût réel | Raisonnement, synthèse multi-sources, diagnostic personnalisé | « mes courgettes jaunissent et j'ai beaucoup arrosé, qu'en penses-tu ? » |

**Point d'attention majeur pour la personnalisation :** l'étage 2 (RAG) et l'étage 3 (LLM) ne s'excluent pas. Le RAG *fournit le contexte*, le LLM *rédige la réponse* quand la question l'exige. Le RAG ne rédige jamais lui-même — il retourne les passages pertinents + un score de confiance. Voir §5.

### 2.1 Le routeur — où va la demande

Le routeur est l'aiguillage. C'est un enrichissement léger de la classification d'intention existante, pas un nouveau composant lourd. Il doit distinguer trois natures de demande :

- **COMMANDE / ACTION** → étage 0 (les 8 intents et 12 actions canoniques actuels).
- **QUESTION DATA** → étage 1 (interrogation des événements du potager).
- **QUESTION SAVOIR** → étage 2 (connaissance agronomique ou fonctionnement de l'app).
- **QUESTION HYBRIDE** (data + savoir) → étage 3, alimenté par 1 et 2.

🔶 Hypothèse de conception : cette classification tient dans un appel `llama-3.1-8b-instant` (~100 tokens) — la bascule déjà prévue dans US-121. Pour les formes très fréquentes et non ambiguës, un pré-filtre par règles/regex peut router sans aucun LLM.

🧪 À tester : le risque principal de toute la cascade est le **mauvais routage** — une question de savoir envoyée à l'étage SQL renvoie une non-réponse. Un corpus de questions réelles (extraites de `texte_original` et des logs `/ask`) doit servir à mesurer le taux de bon routage avant mise en production.

---

## 3. Détail des étages déterministes (0, 0bis, 1)

Ces trois étages ne consomment **aucun token LLM**. Ce sont eux qui portent l'essentiel du gain de rapidité et de coût.

### 3.1 Étage 0 — Commandes et actions déterministes

✅ Déjà largement en place. Les commandes (`/stats`, `/historique`, `/plan`, stock, météo) sont servies directement par la couche services et PostgreSQL. Le parseur déterministe d'actions (prévu US-121) étend ce principe à la saisie : les formes fréquentes (« récolté 2 kg de tomates », « semé 3 rangs de carottes parcelle nord ») sont reconnues par grammaire/regex avant tout appel LLM. Le LLM de parsing devient le fallback des formes complexes.

### 3.2 Étage 0bis — Cache de questions types

Les mêmes questions reviennent en boucle (« stock tomates ? », « dernière récolte ? »). Inutile de refaire le travail à chaque fois.

**Principe :** on normalise la question (minuscules, sans accents, culture détectée extraite), on en dérive un motif, et si ce motif a déjà une réponse valide, on la sert directement.

**Deux natures de réponses cachées, à ne pas confondre :**

- **Réponse *paramétrée* (template)** — le motif est stable mais la valeur dépend du potager. « stock tomates ? » → template `« Il te reste {stock} {unite} de {culture}. »` dont les paramètres sont recalculés par une requête SQL rapide (étage 1). La réponse est personnalisée à chaque fois, mais la *structure* et *le routage* sont mémorisés → 0 token LLM. C'est ta « bibliothèque de réponses », mais vivante.
- **Réponse *figée*** — pour les questions de savoir général dont la réponse ne dépend pas du potager (« à quelle profondeur semer les carottes ? »). Là, la réponse texte peut être mémorisée telle quelle après un premier passage RAG/LLM, avec une durée de validité.

**Schéma de table :**

```
questions_cache
├── id
├── potager_id           INT NULL   -- NULL = réponse partageable entre tous les potagers
│                                       (savoir général) ; sinon spécifique au potager
├── motif_normalise      TEXT       -- clé de recherche (question normalisée / hachée)
├── type_reponse         VARCHAR    -- 'template_sql' | 'figee'
├── template             TEXT       -- gabarit avec {placeholders} pour le type template
├── reponse_figee        TEXT       -- réponse complète pour le type figée
├── source_etage         VARCHAR    -- d'où vient la réponse (sql, rag, llm) — pour audit
├── valide_jusqu_au      TIMESTAMP NULL
└── cree_le
```

🔶 Distribution supposée (à mesurer sur données réelles) : ~40 % des questions résolues ici. C'est l'hypothèse la plus structurante du dimensionnement — elle doit être vérifiée tôt.

> **Note sur le cache Groq natif :** au-delà de ce cache applicatif, les prompts système envoyés au LLM (étage 3) doivent être structurés partie-fixe-en-tête pour bénéficier du *prompt caching* de Groq — les tokens en cache ne comptent pas dans les quotas. C'est un levier distinct et cumulable (voir §7).

### 3.3 Étage 1 — Questions sur les données (agent SQL)

✅ Fondations posées (agent SQL, `extract_intent_query`, scoping US-102). Les questions sur les données du potager se répondent en **SQL, jamais en RAG** : les données sont structurées, une agrégation SQL donne une réponse *exacte* là où le vectoriel donnerait une réponse *approximative* plus chère.

Le principe clé, déjà acté dans US-102/US-122 : **ne jamais envoyer de lignes brutes massives au LLM**. On pré-agrège en SQL (totaux par culture/mois, dernières occurrences, stock courant) et, si un habillage en langage naturel est nécessaire, on ne transmet que le résumé chiffré (< 1 000 tokens). Le plus souvent, un gabarit de réponse suffit et l'étage n'appelle pas le LLM du tout.

---

## 4. Le RAG potager (étage 2)

C'est la brique nouvelle qui transforme le bot d'un carnet en un conseiller. Elle répond aux questions de **connaissance** — celles auxquelles SQL ne peut pas répondre parce que la réponse n'est pas dans les événements du potager.

### 4.1 Trois familles de connaissance, une seule mécanique

Le RAG n'est **pas** un index unique fourre-tout, et surtout **pas** une encyclopédie du jardinage. Il doit très bien connaître un périmètre restreint et utile, structuré en trois familles :

| Famille | Contenu | `potager_id` | Exemple de question |
|---|---|---|---|
| **A. Agronomie** | Fiches cultures, maladies, ravageurs, associations, rotation, calendrier | `NULL` (partagé) | « pourquoi mes tomates ont le cul noir ? » |
| **B. Documentation applicative** | Fonctionnement de l'app : stock, mise en godet, chaînage semis→godet→plantation, sens des écrans | `NULL` (partagé) | « comment est calculé le stock ? » |
| **C. Mémoire du potager** | Observations libres, notes, décisions passées propres au potager | `<id du potager>` | « qu'avais-je noté sur cette parcelle l'an dernier ? » |

**Le pattern de séparation est celui, déjà éprouvé, de `culture_config` :** une colonne `potager_id` nullable où **NULL = connaissance globale partagée entre tous les potagers**, et une valeur = connaissance privée d'un potager. La recherche filtre toujours sur `potager_id IS NULL OR potager_id = :potager_courant`. Cela garantit l'isolation (une note privée ne fuit jamais) tout en mutualisant le savoir général (une seule fiche « tomate » sert 500 utilisateurs).

La famille B est un gain sous-estimé : ton guide utilisateur (`guide_assistant_potager.md`) devient une source RAG. L'assistant sait alors expliquer sa propre application — une aide contextuelle à coût quasi nul qui réduit d'autant le support.

### 4.2 Schéma des tables de connaissance

Deux tables : le document source, et ses fragments interrogeables (*chunks*). Le découpage en chunks est nécessaire parce qu'on veut retrouver *le passage pertinent*, pas le document entier.

```
knowledge_documents
├── id
├── potager_id       INT NULL    -- NULL = global partagé ; sinon privé (famille C)
├── titre            TEXT
├── famille          VARCHAR     -- 'agronomie' | 'doc_app' | 'memoire_potager'
├── source           TEXT        -- provenance (fiche interne, guide, saisie utilisateur…)
├── niveau_confiance VARCHAR     -- 'verifie' | 'indicatif' — pour pondérer plus tard
├── cree_le
└── maj_le

knowledge_chunks
├── id
├── document_id      FK → knowledge_documents
├── potager_id       INT NULL    -- dénormalisé depuis le document (filtre direct, perf)
├── contenu          TEXT        -- le fragment de texte
├── culture          VARCHAR NULL -- métadonnée de filtrage (ex. 'tomate')
├── type             VARCHAR NULL -- 'maladie' | 'semis' | 'association' | 'rotation'…
├── saison           VARCHAR NULL
├── recherche_fts    TSVECTOR    -- ✅ dès le départ : index full-text PostgreSQL
├── embedding        VECTOR NULL -- 🔶 colonne prévue, alimentée plus tard (pgvector)
└── cree_le
```

**Décision actée : full-text d'abord, sémantique ensuite.**

- **Phase 1 (immédiate) — recherche lexicale FTS PostgreSQL** (`tsvector` + `to_tsquery`, dictionnaire français). Elle est excellente pour les termes précis (« mildiou tomate », « purin de consoude », « mise en godet ») et ne demande **aucune dépendance nouvelle** — PostgreSQL est déjà au cœur du projet. Elle couvre l'essentiel des questions de savoir formulées avec le bon vocabulaire.
- **Phase 2 (différée, colonne déjà prévue) — recherche sémantique pgvector.** Elle sera activée quand les questions de **diagnostic mal formulées** deviendront fréquentes : « mes feuilles de tomates deviennent jaunes » doit pouvoir retrouver un document qui parle de « chlorose foliaire » — ce que le lexical seul rate. La colonne `embedding` est créée dès la phase 1 (coût nul) pour éviter une migration lourde le jour venu ; elle reste NULL tant que pgvector n'est pas activé.

🔶 Point à trancher **avant** de démarrer la famille A (risque déjà identifié dans l'Épic 5) : la **source du référentiel agronomique**. Les calendriers et fiches du commerce sont des œuvres protégées, non réutilisables telles quelles. Deux voies : identifier une source sous licence ouverte, ou saisir à la main les ~30 cultures réellement suivies. C'est le principal aléa de charge de la famille A. Les familles B (guide existant) et C (saisies utilisateur) ne portent pas ce risque.

### 4.3 Pseudo-flux d'une recherche RAG

```
question de savoir
      │
      ▼
normaliser + détecter culture/type (réutilise le routeur)
      │
      ▼
recherche FTS sur knowledge_chunks
   WHERE (potager_id IS NULL OR potager_id = :potager_courant)
     AND recherche_fts @@ to_tsquery('french', :termes)
   [+ filtre culture/type si détectés]
      │
      ▼
scorer et classer les résultats
      │
   ┌──┴───────────────────────┐
   │                          │
score élevé,             score faible ou
question factuelle       question de raisonnement
   │                          │
   ▼                          ▼
réponse directe          passer le contexte
(template ou chunk)      à l'étage 3 (LLM)
0 token LLM              LLM rédige à partir du contexte
```

Le RAG retourne un objet de contexte simple — les passages pertinents, leurs sources, un score de confiance global — **il ne génère pas la réponse**. Deux issues : soit la confiance est haute et la question factuelle, et on répond directement (0 token) ; soit la question demande du raisonnement, et le contexte descend nourrir l'étage 3.

🔶 Le **reranking** (réordonner les résultats par un second passage plus fin) est une amélioration connue mais **différée** : il ajoute de la latence et, s'il est confié à un LLM, des tokens. À réserver au jour où la qualité FTS+pgvector plafonne. Idem pour les techniques avancées (Self-RAG, HyDE, multi-query systématique) : intérêt théorique réel, mais à contre-emploi de ton objectif de rapidité au stade actuel.

---

## 5. Personnalisation contextuelle (étage 3)

C'est ce qui distingue un « chatbot jardinage » d'un **compagnon de *ton* potager**. La personnalisation naît de la **combinaison** de sources que seule ton application détient réunies.

Quand une question exige du raisonnement, l'étage 3 assemble un contexte à partir de plusieurs étages en amont, puis le LLM synthétise. Exemple concret — « mes courgettes jaunissent et j'ai beaucoup arrosé cette semaine, qu'en penses-tu ? » :

```
              QUESTION HYBRIDE (data + savoir + météo)
                            │
        ┌───────────────────┼────────────────────┐
        ▼                   ▼                    ▼
   ÉTAGE 1 (SQL)       MÉTÉO (US-124)       ÉTAGE 2 (RAG agronomie)
   courgette,          pluviométrie         causes possibles du
   parcelle sud,       récente élevée,      jaunissement :
   plantée 12/05,      températures         excès d'eau / carence /
   arrosages fréquents hautes               stress thermique / maladie
        │                   │                    │
        └───────────────────┼────────────────────┘
                            ▼
              CONTEXTE ASSEMBLÉ (compact, < 1 000 tokens)
                            │
                            ▼
                    ÉTAGE 3 — LLM (Gateway)
        « Au vu de tes arrosages fréquents et de la forte
          pluviométrie récente, l'excès d'eau est plus
          probable qu'une carence… »
```

Aucune de ces sources prise isolément ne donne une réponse utile. C'est leur assemblage — *données réelles du potager + météo locale + savoir agronomique* — qui produit un conseil contextualisé. Et cet assemblage se fait **sans jamais envoyer de lignes brutes** : SQL a déjà agrégé, le RAG a déjà sélectionné, la météo est déjà résumée. Le LLM ne reçoit qu'une synthèse dense.

C'est aussi ici que se joue la **personnalisation par la localisation** : dès que le potager a une localisation (champ déjà prévu sur l'entité `potagers` — lat/lon), le calendrier cultural (Épic 5) et la météo (US-124) se recalent sur *sa* zone. « Quand semer les carottes ? » cesse d'être une réponse générique pour devenir « chez toi, la dernière fenêtre de semis se ferme dans X jours ».

---

## 6. LLM à la demande du potager (BYOK)

Un potager qui dispose déjà d'un abonnement IA (OpenAI, Mistral, sa propre clé Groq…) doit pouvoir brancher **son** modèle. C'est le pattern *Bring Your Own Key*. Il s'insère naturellement au seul endroit qui appelle le LLM : le **LLM Gateway**.

### 6.1 Le LLM Gateway — point de passage unique

Le Gateway (prévu US-121/US-123) est le composant par lequel **tous** les appels LLM transitent. C'est lui qui, pour chaque appel, décide : cache ? règle ? SQL ? RAG seul ? petit modèle ? grand modèle ? Et surtout, c'est lui qui résout **quel client LLM utiliser** selon le potager.

Sans ce point unique, le BYOK serait à câbler dans chaque fonction. Avec lui, c'est une résolution centralisée. **C'est un argument fort pour prioriser US-121** : le Gateway est le préalable qui rend le BYOK trivial.

La quasi-totalité des fournisseurs pertinents (Groq, OpenAI, Mistral, OpenRouter, Together…) exposent une **API compatible OpenAI** : même format de requête, même endpoint `/chat/completions`. Déporter le branchement se résume donc à rendre trois paramètres dynamiques par potager : l'URL de base, la clé, le nom du modèle. Un seul client générique suffit.

```
                        LLM GATEWAY
                            │
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
      résolution         quotas /           mesure
      du client          rate-limit         conso tokens
         │               (US-123)           (US-123)
         │
   ┌─────┴─────────────────────┐
   ▼                           ▼
config LLM du potager ?    pas de config
   │                           │
   ▼                           ▼
client du potager          client plateforme
(base_url, clé, modèle)    (clé Groq mutualisée,
sort du quota mutualisé     gpt-oss-120b par défaut)
```

### 6.2 Configuration par potager

```
potager_llm_config
├── potager_id        FK → potagers   (NULL possible au niveau appli = pas de config
│                                       → on retombe sur le client plateforme)
├── provider          VARCHAR         -- 'groq' | 'openai' | 'mistral' | 'openrouter'…
├── base_url          TEXT            -- endpoint compatible OpenAI
├── model             VARCHAR         -- modèle choisi par le potager
├── api_key_chiffree  TEXT            -- ⚠️ chiffrée au repos, jamais en clair
├── actif             BOOLEAN
├── derniere_validation TIMESTAMP NULL -- date du dernier test de clé réussi
└── cree_le
```

Le pattern est le même que partout ailleurs : absence de config = comportement plateforme par défaut. Aucune rupture pour les potagers qui ne configurent rien.

### 6.3 Points de vigilance — non négociables

**Chiffrement des clés au repos.** Les clés API des utilisateurs sont des secrets. Chiffrement applicatif (clé maîtresse hors base, en variable d'environnement), **jamais** en clair dans la base, les logs, ni `texte_original`. Une fuite de base ne doit pas exposer les clés OpenAI des utilisateurs. Prévoir un test de clé à la saisie (« clé validée ✓ ») pour l'ergonomie et pour renseigner `derniere_validation`.

**Portabilité des prompts — le vrai risque produit.** 🧪 Tes prompts de parsing JSON sont calibrés pour gpt-oss-120b. Un potager qui branche un modèle plus faible obtiendra des JSON malformés, des intents ratés — **et c'est toi qu'il tiendra pour responsable**, pas son modèle. Deux garde-fous : un post-processing robuste (c'est le même chantier que la bascule 8B déjà prévue), et une liste explicite de modèles « testés/supportés » vs « à vos risques ».

**Whisper reste sur la plateforme (v1).** 🔶 La transcription vocale est un appel distinct. Recommandation : en première version, Whisper reste toujours sur la clé plateforme (quota généreux, coût faible), même pour un potager BYOK. Cela évite de gérer la disparité des fournisseurs sur l'audio. Le BYOK ne couvre alors que la génération de texte.

**Consentement RGPD.** Les données du potager partent vers le fournisseur choisi. Consentement explicite à l'activation (« vos données seront transmises à X selon ses conditions »). S'intègre dans les flux RGPD de l'Épic 4 (US-132).

### 6.4 Mode dégradé 429 — un invariant, pas une option

Le **429** (« Too Many Requests ») est renvoyé par le fournisseur quand le quota est dépassé. À l'échelle cible, le quota gratuit **sera** saturé régulièrement. L'application doit rester utile sans LLM :

- **Continuent de fonctionner** : commandes déterministes, cache, agent SQL, météo, RAG en lecture (FTS ne dépend pas du LLM) — soit les étages 0, 0bis, 1 et une bonne part de 2.
- **Échoue proprement** : les étages qui exigent le LLM (parsing complexe, synthèse de diagnostic) répondent « L'analyse avancée par IA est temporairement indisponible, réessaie dans quelques minutes » — jamais un crash ni un silence.

Concrètement, le Gateway intercepte le 429 (au lieu de le laisser remonter) et chaque appelant a un comportement de repli défini. Le LLM ne doit **jamais** être un point de défaillance unique fonctionnel.

Ce mode dégradé est doublement stratégique : il protège l'expérience quand le quota sature, **et** il fonde le modèle freemium — fonctions déterministes toujours disponibles, IA avancée garantie sur les plans payants ou en BYOK.

---

## 7. Impact attendu

### 7.1 Sur le coût par question

🔶 Estimation sur une distribution réaliste à valider :

| Étage | Part des questions | Coût LLM |
|---|---|---|
| 0 / 0bis (commande, cache) | ~40 % | 0 token |
| 1 (SQL) | ~35 % | 0 token (ou gabarit sans LLM) |
| 2 (RAG, réponse directe) | ~20 % | 0 token en lecture |
| 3 (LLM) | ~5 % | coût réel (~1 000–1 200 tokens de contexte compact) |

**Coût moyen visé : ~180 tokens/question**, contre ~5 000 historiquement. Et surtout, latence quasi nulle sur ~95 % des questions.

### 7.2 Sur la capacité (contrainte Groq free tier)

Rappel des limites `openai/gpt-oss-120b` en abonnement free (au niveau *organisation*, pas par utilisateur ; on bute sur la première atteinte) : **30 req/min, 1 000 req/jour, 8K tokens/min, 200K tokens/jour**. La limite la plus contraignante aujourd'hui est le **TPM 8K** (un seul `_ask_question` actuel la sature presque).

| Scénario | Capacité approximative |
|---|---|
| Architecture actuelle (`_ask_question` non optimisé) | ~30–50 utilisateurs actifs/jour |
| Architecture cible (cascade complète) | ~150–300 utilisateurs actifs/jour |

🔶 À noter : **Whisper a son propre quota** (~2 000 transcriptions/jour en free). En usage voice-first, ce sera peut-être la première saturation réelle avant même le LLM de texte.

**Les leviers de capacité, par ordre d'impact :**

1. **Prompt caching Groq** — partie fixe des prompts en tête ; les tokens cachés ne comptent pas dans les quotas. Levier n°1, presque gratuit.
2. **Répartition multi-modèles** — les limites sont *par modèle*. `classify_intent` sur `llama-3.1-8b-instant` (US-121) déporte la moitié des requêtes sur un quota séparé → capacité quasi doublée.
3. **La cascade elle-même** — chaque question résolue sans LLM est de la bande passante rendue.
4. **BYOK** — chaque potager qui branche sa clé **sort du quota mutualisé**. C'est de la capacité financée par l'utilisateur.
5. **Lecture des headers de rate-limit** par le Gateway → throttler *avant* le 429 plutôt que le subir.
6. **Passage payant** — à l'échelle cible (~500 users × 10 questions/jour × ~200 tokens ≈ 30 M tokens/mois), le coût Groq est de l'ordre de **~5–20 €/mois**. Ce n'est pas un mur technique, c'est une ligne dans le pricing freemium (US-133).

**En synthèse : le free tier porte confortablement la beta ; la cascade + le caching étendent à quelques centaines d'utilisateurs ; au-delà, le coût marginal est faible et se répercute dans le prix. L'architecture ne sert pas à *éviter de payer*, elle sert à ce que la marge par utilisateur soit saine quand on paie.**

---

## 8. Points d'attention pour Claude Code

Ces règles complètent les invariants du backlog (§ « Invariants à rappeler dans chaque US »). À rappeler dans les US issues de ce document :

- **Isolation avant tout.** Toute recherche dans `knowledge_chunks` filtre `potager_id IS NULL OR potager_id = :courant`. La famille C (mémoire potager) ne doit jamais fuir vers un autre potager. Test d'isolation obligatoire, comme pour les événements (US-102/103).
- **Migrations séparées et idempotentes.** Nouvelles tables (`questions_cache`, `knowledge_documents`, `knowledge_chunks`, `potager_llm_config`) en fichiers `migration_vX.sql` distincts, rejouables (`IF NOT EXISTS`), avec rollback documenté. La colonne `embedding` est créée dès la phase 1 mais reste nullable et inutilisée jusqu'à l'activation de pgvector.
- **Le RAG ne génère pas la réponse.** Il retourne contexte + sources + confiance. La génération reste au seul étage 3, via le Gateway.
- **Tout appel LLM passe par le Gateway.** Aucun appel Groq direct ne doit subsister hors du Gateway une fois celui-ci en place — c'est ce qui garantit à la fois la mesure de conso (US-123), le mode dégradé 429 et le BYOK. Wrapper unique autour du client.
- **Chiffrement des clés BYOK.** Jamais en clair — ni base, ni logs, ni `texte_original`. Clé maîtresse en variable d'environnement.
- **Impact tokens chiffré et loggé** pour tout nouvel appel LLM (invariant existant).
- **Prompts Groq :** `.replace()` sur les variables, jamais `.format()` (accolades des prompts). **SQLAlchemy 2.0 :** `db.get()`, jamais `db.query().get()`. **Logging structuré** `HH:MM:SS │ LEVEL │ emoji` conservé. **Compatible SentinelOne** (polling, pas de tunnel entrant).
- **Ordre critique des flux** de `handle_text` (modes `corr_*` > mode `ask` > NAV > `_is_question` > action) préservé ; tout branchement du routeur en amont liste ses effets de bord sur les états de conversation.

---

## 9. Rattachement aux US existantes et séquencement

Ce document ne crée pas d'US — il cadre celles que l'agent PO déclinera. Correspondances :

| Brique de ce document | US existante(s) concernée(s) | Nature |
|---|---|---|
| Routeur + parseur déterministe + cache classification + bascule 8B | **US-121** (LLM à étages) | Enrichie |
| Cache de questions types (étage 0bis) | US-121 / US-122 | À préciser |
| Pré-agrégation SQL, scoping question | **US-102**, **US-122** | En place / enrichie |
| RAG potager (familles A/B/C, tables connaissance, FTS) | **nouvelle** (ex. « US-140 — base de connaissance + RAG scopé ») | Nouvelle |
| Personnalisation (contexte assemblé, localisation, météo) | **US-124** (jobs/météo), Épic 5 (calendrier) | Dépendances |
| LLM Gateway + quotas + mode dégradé 429 | **US-121**, **US-123** | Enrichies |
| BYOK (config LLM par potager) | **nouvelle** (ex. « US-141 — LLM à la demande / BYOK ») | Nouvelle |
| Source du référentiel agronomique (risque licence) | préalable à la famille A | À trancher |

**Ordre logique suggéré** (à arbitrer par le PO en fonction de l'état réel du code) :

```
1. US-121  LLM Gateway + étages + cache + 8B     ← socle : rien ne marche proprement sans le Gateway
2. US-122  Pré-agrégation SQL (/ask scopé)        ← complète l'étage 1
3. US-140  RAG potager — FTS d'abord              ← l'étage 2, cœur du "conseiller"
      ├─ famille B (doc app, guide existant) : la plus facile, zéro risque licence
      ├─ famille A (agronomie) : après arbitrage de la source du référentiel
      └─ famille C (mémoire potager) : saisies utilisateur
4. US-123  Quotas + mode dégradé 429              ← s'appuie sur le Gateway
5. US-141  BYOK (config LLM par potager)          ← trivial une fois le Gateway là
--- plus tard ---
6. Activation pgvector (recherche sémantique) quand le diagnostic mal-formulé devient fréquent
7. Reranking conditionnel si la qualité FTS+pgvector plafonne
8. Annexe A — moteur d'insights proactif
```

### 9.1 Déclinaison réelle en US — tableau de suivi

> ⚠️ **Numérotation.** Les numéros du tableau et de l'ordre ci-dessus relèvent de l'**ancienne
> numérotation** du plan multi-tenant (US-121, US-122, US-140 « RAG », US-141 « BYOK »). La
> déclinaison effective par l'agent PO suit la numérotation réelle du répertoire `backlog/` :
> **US-092 à US-099**, puis **US-140 à US-143**, la bande 100-133 étant volontairement sautée
> (voir `README.md` §mapping). « US-140 » ne désigne donc **pas** la même chose ci-dessus (le RAG)
> et ci-dessous (le corpus agronomique).

**12 US · 70 points · `ÉPIC 3 — Fiabilité & coût`**

| US | Titre | Pts | Rôle | Dépend de |
|---|---|---|---|---|
| [US-092](../backlog/US-092_passerelle-llm-unique.md) | Passerelle LLM unique | 5 | Socle — mesure conso, mode dégradé 429, point d'extension BYOK | — |
| [US-093](../backlog/US-093_routeur-demandes-regles-first.md) | Routeur règles-first | 5 | Aiguillage + cache de classification + remontée de cascade | 092 |
| [US-094](../backlog/US-094_parseur-deterministe-saisies-courantes.md) | Parseur déterministe des saisies | 8 | Étage 0 — saisie sans LLM | 092 |
| [US-095](../backlog/US-095_cache-questions-invalidation-evenementielle.md) | Cache de questions types | 5 | Étage 0bis — invalidation événementielle | 093, 096 |
| [US-096](../backlog/US-096_reponses-chiffrees-gabarits-sql.md) | Gabarits sur agrégats SQL | 5 | Étage 1 — réponses chiffrées + garde-fous SQL | 093 |
| [US-097](../backlog/US-097_observabilite-cascade-retour-jardinier.md) | Observabilité + retour 👍/👎 | 3 | Valide les hypothèses 40/35/20/5 du §7.1 | 092, 093 |
| [US-098](../backlog/US-098_socle-connaissance-recherche-fts.md) | Socle de connaissance + FTS | 8 | Étage 2 — le contenant | 093 |
| [US-099](../backlog/US-099_corpus-fonctionnement-application.md) | Corpus « fonctionnement app » | 5 | Famille B — contenu | 098 |
| [US-140](../backlog/US-140_corpus-agronomique-cultures-prioritaires.md) | Corpus agronomique (10 cultures) | 8 | Famille A — contenu, risque licence | 098, 067 |
| [US-141](../backlog/US-141_memoire-potager-observations-indexees.md) | Mémoire du potager | 5 | Famille C — observations indexées | 098 |
| [US-142](../backlog/US-142_conseil-personnalise-multi-sources.md) | Conseil personnalisé multi-sources | 5 | Étage 3 — le seul où le LLM rédige | 092, 093, 096, 098 |
| [US-143](../backlog/US-143_brancher-sa-propre-cle-ia.md) | BYOK — clé et modèle du potager | 8 | Sort du quota mutualisé | 092 |

**Ordre recommandé :** `092` → `093` + `097` → `094` / `095` / `096` → `098` → `099` / `141` →
`140` → `142` → `143`. L'arbitrage de la **source du référentiel agronomique** (risque 🔴, commun à
US-140 et à l'Épic 5 calendrier) est un travail de recherche, pas de développement : il est mené en
tâche de fond dès le début, sans bloquer la cascade.

**Trois corrections apportées à ce document par la déclinaison :**
- `guide_assistant_potager.md` (§4.1) **n'existe pas dans le dépôt** : le corpus de la famille B est
  à **écrire**, pas à ingérer. Sa matière première est constituée des textes d'aide `/help`.
- Le coût moyen visé de ~180 tokens/question (§7.1) **omet le coût du routage** : il est recalculé
  routage inclus par US-097.
- L'Épic 5 calendrier **n'est prérequis d'aucune** de ces 12 US : seule US-142 le touche, en mode
  dégradé explicite (aucune date annoncée tant que le référentiel n'existe pas). En revanche il
  reste prérequis dur de l'**Annexe A** ci-dessous.

---

## Annexe A — La couche proactive (jalon suivant)

Ce document couvre le versant **réactif** : bien répondre, vite et à moindre coût. Un vrai « compagnon » parle aussi **le premier**. C'est le versant proactif, décrit ici comme cap, à instruire après la cascade.

**Principe :** au lieu d'attendre la question puis d'appeler le LLM, on **pré-calcule les conseils de façon déterministe** et on les sert au bon moment. Un job quotidien par potager (US-124) exécute un moteur de règles — pur SQL/Python, zéro token — et remplit une table d'insights :

```
insights
├── potager_id
├── type            -- 'fenetre_semis' | 'recolte_imminente' | 'alerte_gel'
│                      | 'rotation' | 'succession'…
├── culture
├── priorite
├── valide_jusqu_au
└── payload         -- données de l'insight (JSON)
```

Chaque insight est **déductible sans LLM** de données déjà disponibles ou créées par l'Épic 5 :

- référentiel calendrier + événements réels → « ta courgette est récoltable dans 12 jours »
- météo + localisation → « gel annoncé jeudi, protège tes tomates »
- familles botaniques + historique parcelles → « évite les solanacées sur NORD, 2 ans de suite »
- stock + saison → « tes pois parcelle B sont finis, plante des légumineuses derrière »

Cette table alimente trois canaux **sans coût LLM** : un **digest Telegram matinal** (« 3 choses pour ton potager aujourd'hui » — c'est *ça* qui crée le sentiment de compagnon), le module **« À faire cette semaine »** du dashboard PWA, et les **réponses aux questions** du type « je plante quoi maintenant ? » (l'étage 1/2 lit les insights existants → 0 token).

**Pourquoi c'est stratégique :** un concurrent peut brancher un LLM sur un carnet ; il ne peut pas copier un moteur de règles agronomiques recalé sur les données réelles de l'utilisateur. C'est la réponse directe au risque « carnet multi-utilisateurs facilement copiable » du backlog. Le compagnon naît des **règles**, pas du RAG — le RAG répond, les règles anticipent.

**Prérequis :** Épic 5 (référentiel + recalage) et US-124 (jobs par potager) — déjà cadrés. Il ne manque qu'une US « moteur d'insights » + une US « digest Telegram ». À instruire une fois la cascade réactive stabilisée.


# Analyse de l'architecture cible V2 — Assistant Potager Telegram -- Ox Alpha IA

> **Document analysé :** `ARCHITECTURE_CIBLE_V2_reponses.md`
> **Type d'analyse :** revue d'architecture + propositions d'amélioration

---

## Verdict global

C'est un document de très bonne qualité : le principe directeur (« le LLM en dernier recours ») est le bon, la cascade est bien pensée, les invariants techniques sont solides (isolation multi-tenant, Gateway unique, mode dégradé 429). Voici une analyse critique et des pistes d'amélioration.

---

## ✅ Points forts à conserver

1. **La cascade du moins cher au plus cher** — pattern éprouvé, bon dimensionnement.
2. **FTS d'abord, pgvector ensuite** — décision pragmatique et juste. Le FTS français couvre 80 % des cas agronomiques (vocabulaire technique précis).
3. **Le RAG ne génère jamais** — séparation récupération/génération propre.
4. **Le mode dégradé 429 comme invariant** — rarement pensé, ici bien traité, et doublement stratégique (freemium).
5. **Le Gateway comme point unique** — prérequis qui rend le BYOK trivial.
6. **L'Annexe A (moteur d'insights déterministes)** — c'est effectivement le vrai différenciateur produit.

---

## ⚠️ Faiblesses et risques identifiés

### 1. Le routeur est le maillon faible sous-estimé

Le document identifie le risque mais ne propose pas de mitigation structurée :

- Un routeur 8B à ~100 tokens par question = **1 appel LLM systématique**, ce qui contredit partiellement l'objectif « 0 token sur 95 % des questions ». À ~10 questions/jour/utilisateur, ça consomme déjà 1 000 tokens/jour/user rien qu'en routage.

**Améliorations :**
- Router d'abord par règles (regex, détection `/commande`, patterns « combien/quand/stock »), LLM seulement en cas d'ambiguïté.
- Mettre en cache la classification question normalisée → étage (comme l'étage 0bis).
- Prévoir un **fallback de routage** : si l'étage SQL renvoie vide/confiance nulle, remonter vers RAG plutôt que répondre « je ne sais pas ». Une cascade purement descendante sans remontée produira des frustrations.

### 2. Étage 0bis (cache) : invalidation non traitée

Le schéma a `valide_jusqu_au`, mais rien sur **l'invalidation événementielle**. Exemple : réponse cachée « stock tomates : 3 kg », puis l'utilisateur saisit « récolté 5 kg tomates » → réponse fausse pendant des heures.

**Amélioration :** invalidation par dépendance — chaque entrée de cache porte les entités dont elle dépend (`culture`, `type_donnee`), et toute écriture d'événement invalide les motifs liés. C'est peu coûteux et évite le pire défaut d'un assistant : donner une information fausse avec assurance.

### 3. Estimations de distribution à risque

Les ~40 % / ~35 % / ~20 % / ~5 % sont présentés comme hypothèses 🔶, bien. Mais le coût moyen visé (~180 tokens/question) oublie le **coût du routage lui-même** (~100 tokens/question si LLM). À corriger dans le modèle.

### 4. Famille A (référentiel agronomique) : le vrai goulot

Le risque licence est identifié mais la solution « saisir à la main ~30 cultures » est sous-dimensionnée : une fiche culture complète (semis, maladies, associations, rotation, calendrier) = plusieurs heures chacune.

**Améliorations :**
- Sources ouvertes à explorer dès maintenant : Wikipédia/Wikidata (CC-BY-SA), données publiques INRAE/GNIS, fiches sous licence ouverte.
- Démarrer famille A avec seulement les 8–10 cultures réellement les plus utilisées (données `texte_original`), pas 30.

### 5. Whisper : risque plus grand qu'annoncé

Le document note que Whisper saturera peut-être avant le LLM, mais ne propose rien. Or en voice-first, c'est le chemin critique UX.

**Améliorations :**
- Fallback transcription locale (faster-whisper sur VPS si compatible SentinelOne/polling).
- Ou limitation du free tier vocal + incitation BYOK audio en phase 2.

### 6. Points manquants

- **Observabilité de la cascade** : aucune mention de métriques par étage (taux de résolution, taux de mauvais routage, latence p95). Indispensable pour valider les hypothèses 🔶. Une table `routage_logs` simple suffirait au départ.
- **Boucle feedback utilisateur** : 👍/👎 sur les réponses RAG/LLM pour détecter les mauvaises réponses et alimenter le corpus de test du routeur.
- **Sécurité SQL agent** : l'étage 1 repose sur un agent SQL ; rappeler explicitement lecture seule + allowlist de requêtes + timeout (peut-être déjà couvert par US-102, mais à inscrire comme invariant ici).
- **Versionnement du contenu RAG** : quand une fiche agronomique est corrigée, invalider les réponses figées issues de cette fiche (`source_etage` aide, mais il faut un lien chunk → réponses figées dérivées).

---

## 🎯 Améliorations prioritaires suggérées

| # | Amélioration | Effort | Impact |
|---|---|---|---|
| 1 | Invalidation événementielle du cache (étage 0bis) | Moyen | **Critique** (justesse) |
| 2 | Routage règles-first + cache de classification + remontée de cascade | Moyen | Fort (coût + qualité) |
| 3 | Table `routage_logs` + dashboard métriques par étage | Faible | Fort (validation des 🔶) |
| 4 | Feedback 👍/👎 sur réponses | Faible | Moyen |
| 5 | Réduire famille A initiale à ~10 cultures + sourcer licences ouvertes tôt | Moyen | Fort (délai) |
| 6 | Plan B transcription vocale | Moyen | Fort (UX voice-first) |

---

## Séquencement proposé (ajustement)

L'ordre proposé dans le document est bon ; deux ajustements :

1. Insérer la **métrique de routage** (point 3) *dans* US-121, pas après — sinon impossible de valider l'hypothèse centrale du dimensionnement.
2. Anticiper l'arbitrage **source référentiel agronomique** en parallèle de l'US-140 (c'est un travail humain/recherche, pas technique — il peut avancer pendant le dev).



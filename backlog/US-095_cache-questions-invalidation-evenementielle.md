**ID :** US-095
**Titre :** Servir les questions récurrentes depuis un cache qui ne ment jamais
**Épic :** ÉPIC 3 — Fiabilité & coût

**Story :**
En tant que jardinier
Je veux que mes questions habituelles reçoivent une réponse immédiate
Afin de ne pas attendre, sans jamais recevoir une information périmée par ce que je viens moi-même d'enregistrer

**Contexte fonctionnel :**
Quatrième US issue de `docs/ARCHITECTURE_CIBLE_V2_reponses.md` (§3.2) — étage 0bis de la cascade. Les
mêmes questions reviennent en boucle (« stock tomates ? », « dernière récolte ? ») : les traiter à
neuf à chaque fois est du gaspillage.

**Le cadrage initial comporte un angle mort, signalé par la revue critique et corrigé ici :** le
schéma de cache prévoyait une simple date de validité. Or le scénario le plus banal de
l'application est aussi le pire : le jardinier demande son stock de tomates, puis enregistre
« récolté 5 kg de tomates », puis repose la même question — et reçoit l'ancienne valeur. **Un
assistant qui affirme une donnée fausse avec assurance perd plus de confiance qu'il n'en gagne en
étant rapide.** L'invalidation par dépendance est donc un critère bloquant de cette US, pas une
amélioration ultérieure.

Le document distingue deux natures de réponses mémorisées, qu'il ne faut jamais confondre :
- **réponse paramétrée** — le motif et l'aiguillage sont mémorisés, les valeurs sont recalculées à
  chaque fois par une agrégation SQL rapide. La réponse est donc toujours juste *par construction*,
  et coûte zéro jeton ;
- **réponse figée** — texte mémorisé tel quel, réservé au savoir général qui ne dépend d'aucun
  potager (« à quelle profondeur semer les carottes ? »).

**Critères d'acceptance :**

*Structure*
- [ ] CA1 : Une table `questions_cache` porte : `potager_id` (nul = savoir général partageable entre tous les potagers), `motif_normalise`, `type_reponse` (`template_sql` ou `figee`), `template`, `reponse_figee`, `source_etage` (`sql`, `rag`, `llm` — pour audit), `valide_jusqu_au`, `cree_le`
- [ ] CA2 : Le motif de recherche est dérivé de la question normalisée (minuscules, sans accents, culture détectée extraite) — la même normalisation que le routeur (US-093), jamais une variante
- [ ] CA3 : Une réponse `template_sql` ne stocke **que** la structure et l'aiguillage ; ses valeurs sont recalculées à chaque service par l'étage des données (US-096). Elle est donc personnalisée à chaque appel tout en coûtant zéro jeton

*Justesse — critère bloquant*
- [ ] CA4 : Chaque entrée de cache porte les **dépendances** dont elle dérive : culture concernée et nature de donnée (`stock`, `recolte`, `semis`, `plan`, `pepiniere`…)
- [ ] CA5 : **Toute écriture d'un événement invalide immédiatement les entrées de cache du potager qui en dépendent.** Enregistrer une récolte de tomates rend caduque toute réponse mémorisée portant sur le stock ou les récoltes de tomates de ce potager
- [ ] CA6 : Un test démontre la séquence complète : question, réponse servie, enregistrement d'un événement contradictoire, même question reposée — la seconde réponse reflète le nouvel état. C'est le test central de l'US
- [ ] CA7 : La correction et la suppression d'un événement (flux `corr_*` existants) invalident au même titre qu'une création : ces chemins sont explicitement couverts, ils sont les plus faciles à oublier

*Isolation*
- [ ] CA8 : Une réponse `figee` avec `potager_id` nul ne peut **jamais** contenir de donnée issue d'un potager. Un contrôle à l'écriture le garantit et un test d'isolation le vérifie : c'est le mécanisme par lequel une fuite inter-potagers serait la plus discrète et la plus durable
- [ ] CA9 : Une réponse mémorisée pour un potager n'est jamais servie à un autre potager, même à motif identique

*Durée de vie*
- [ ] CA10 : Une réponse `figee` porte une durée de validité (90 jours par défaut) **et** un lien vers le fragment de connaissance dont elle est issue : quand ce fragment est corrigé ou réingéré (US-098 / CA9), les réponses figées qui en dérivent sont invalidées. Corriger une fiche agronomique ne doit pas laisser vivre des mois une réponse erronée
- [ ] CA11 : Les entrées périmées sont écartées à la lecture et nettoyées au fil de l'eau ; aucun nouveau job planifié n'est ajouté pour cela

*Mesure*
- [ ] CA12 : Le taux de service depuis le cache est mesuré et exposé (US-097). L'hypothèse de ~40 % des questions résolues à cet étage, la plus structurante du dimensionnement de l'architecture, est **vérifiée par la mesure ou corrigée**, jamais affirmée
- [ ] CA13 : Une réponse servie depuis le cache est indiscernable d'une réponse fraîche pour le jardinier — aucune mention « réponse en cache ». Seul le journal en garde trace

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram | analyse | consultation
- Migration BDD requise : **oui** — création de `questions_cache` (⚠️ vérifier le numéro de la dernière migration au moment de l'implémentation), idempotente, rollback documenté
- **Arbitrage tranché — le paramétré est la règle, le figé l'exception :** toute question qui touche aux données du potager est mémorisée en `template_sql`, jamais en texte. Le figé est réservé au savoir général, où il n'existe aucun événement susceptible de le contredire. Cette règle rend la classe entière des réponses périmées structurellement impossible
- **Arbitrage tranché — invalider large plutôt que fin :** en cas de doute sur la dépendance, on invalide plus d'entrées que nécessaire. Recalculer une réponse coûte zéro jeton ; servir une donnée fausse coûte la confiance
- **Arbitrage tranché — pas de préchauffage du cache :** aucune génération anticipée de réponses. Le cache se remplit de ce qui est réellement demandé ; précalculer des réponses jamais lues serait du coût pur
- Dépendances : **US-093** (normalisation et aiguillage), **US-096** (recalcul des valeurs paramétrées). **US-098** pour le lien du CA10, non bloquante : tant que le socle de connaissance n'existe pas, aucune réponse figée d'origine RAG n'est produite
- Invariants projet : isolation inter-potagers testée (invariant depuis US-042) ; `db.get()` jamais `db.query().get()`

**Notes techniques (pour Persona Developer) :**
- L'invalidation doit être branchée dans la **couche services** d'écriture des événements, en un point unique — jamais dupliquée dans le bot et dans l'API, sous peine de diverger au premier ajout de fonctionnalité
- Le lien fragment de connaissance vers réponses figées dérivées (CA10) est une simple référence stockée sur l'entrée de cache ; ne pas le concevoir comme un mécanisme d'événements
- Ne pas mettre en cache les réponses produites en mode dégradé (429) : elles seraient mémorisées comme des non-réponses
- Prévoir une borne haute au nombre d'entrées par potager, pour qu'une saisie erratique ne fasse pas croître la table indéfiniment

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Question récurrente servie instantanément
  Given un jardinier qui a déjà demandé son stock de tomates aujourd'hui
  When il repose la même question
  Then la réponse est produite depuis le motif mémorisé
  And aucun appel au modèle n'a lieu

Scénario: Le cache ne survit pas à un événement qui le contredit
  Given un jardinier qui vient de consulter son stock de tomates
  When il enregistre "récolté 5 kg de tomates"
  And il redemande son stock de tomates
  Then la réponse reflète le nouveau stock
  And elle ne reprend jamais la valeur précédente

Scénario: Correction d'événement prise en compte
  Given une récolte de courgettes enregistrée puis corrigée en 3 kg
  When le jardinier demande le total récolté de courgettes
  Then la réponse tient compte de la correction

Scénario: Savoir général partagé entre potagers
  Given une réponse figée sur la profondeur de semis des carottes
  When un jardinier d'un autre potager pose la même question
  Then la même réponse lui est servie
  And elle ne contient aucune donnée d'un potager

Scénario: Aucune fuite entre potagers
  Given une réponse mémorisée pour le potager A sur son stock de tomates
  When un membre du potager B pose exactement la même question
  Then la réponse est recalculée pour le potager B
  And aucune valeur du potager A n'apparaît

Scénario: Fiche de connaissance corrigée
  Given une réponse figée issue d'une fiche agronomique
  When cette fiche est corrigée et réingérée
  Then la réponse figée qui en dérivait est invalidée
  And la question suivante repart du contenu à jour
```

**Labels GitHub :** `us`, `sprint-fiabilite-cout`, `cache`, `analyse`, `qualite-donnee`

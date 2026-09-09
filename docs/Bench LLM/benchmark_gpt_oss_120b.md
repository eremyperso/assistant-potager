# Cahier de benchmark GPT-OSS-120B pour l'application

## 1. Mandat

Tu dois implémenter, exécuter et documenter un benchmark de l'utilisation de `openai/gpt-oss-120b` dans le système applicatif existant.

Le benchmark doit partir de l'historique réel enregistré dans la table ou le fichier de consommation, puis compléter ces observations par des tests contrôlés et des simulations de montée en charge.

L'objectif n'est pas de mesurer les capacités générales du modèle. Il faut mesurer précisément le besoin de production de l'application pour une cible de **100 utilisateurs**, avec :

- une activité plus forte durant la phase de découverte ;
- une stabilisation progressive de l'usage ;
- un cache applicatif exact et sémantique ;
- une hypothèse initiale de **10 % de requêtes servies sans nouvel appel LLM**, à confirmer par la mesure ;
- très peu de raisonnement confié au modèle ;
- une logique métier et une partie de la réflexion réalisées par l'application ;
- des appels LLM principalement consacrés à la classification, au parsing, à la compréhension de la demande et à la formulation d'une réponse simple à partir de contenus déjà sélectionnés ;
- des entrées texte ou issues de transcriptions audio.

Le modèle principal à analyser est exclusivement :

```text
openai/gpt-oss-120b
```

Les autres modèles présents dans l'historique doivent être isolés et exclus des statistiques principales. Ils peuvent apparaître dans une annexe comparative, sans être mélangés au référentiel GPT-OSS-120B.

---

## 2. Résultats attendus

Le benchmark doit permettre de répondre aux questions suivantes :

1. Quel est le volume réel d'appels GPT-OSS-120B par interaction utilisateur ?
2. Quels types d'appels consomment le plus de tokens ?
3. Quelle part des tokens provient de la classification, du parsing et de la réponse finale ?
4. Quel est le coût observé par interaction, par utilisateur et par mois ?
5. Quel volume de RPM, TPM, ITPM et OTPM faut-il prévoir pour 100 utilisateurs ?
6. Quelle capacité est nécessaire en régime normal, en pointe et pendant la phase de découverte ?
7. Quelle réduction peut être obtenue grâce au cache applicatif et au cache de prompt ?
8. Les latences et taux d'erreur sont-ils compatibles avec une utilisation interactive ?
9. L'application génère-t-elle des appels redondants, simultanés ou évitables ?
10. Quel quota faut-il demander au fournisseur avec une marge de sécurité explicite ?

---

## 3. Source historique disponible

La source actuelle contient au minimum les colonnes suivantes :

```text
id
potager_id
user_id
date
appel_type
modele
tokens_in
tokens_out
tokens_cache
latence_ms
issue
cree_le
```

Valeurs observées dans `appel_type` :

```text
classification
parsing
question
transcription
```

Valeurs observées dans `issue` :

```text
ok
erreur
quota
```

### 3.1 Règles de préparation

- Parser `cree_le` comme un horodatage précis.
- Utiliser `date` comme date fonctionnelle seulement après contrôle de cohérence avec `cree_le`.
- Filtrer le référentiel principal sur `modele = openai/gpt-oss-120b`.
- Ne pas considérer les lignes de transcription Whisper comme des appels GPT-OSS-120B.
- Conserver les lignes ayant zéro token lorsqu'elles correspondent à une erreur ou un quota atteint.
- Ne pas inclure les appels échoués dans les moyennes de tokens des appels réussis.
- Inclure les appels échoués dans les taux d'erreur et dans l'analyse de capacité.
- Vérifier les doublons exacts sur `id`.
- Rechercher les doublons fonctionnels ayant le même utilisateur, type, nombre de tokens et horodatage très proche.
- Vérifier si `tokens_cache` est inclus dans `tokens_in` ou comptabilisé séparément par l'implémentation. Ne pas supposer la formule avant vérification.

### 3.2 Contrôles de qualité des données

Produire un rapport contenant :

- nombre total de lignes ;
- nombre de lignes GPT-OSS-120B ;
- période minimale et maximale ;
- nombre d'utilisateurs distincts ;
- nombre de potagers distincts ;
- valeurs distinctes de `appel_type`, `modele` et `issue` ;
- valeurs nulles par colonne ;
- nombres négatifs ;
- tokens nuls sur appels réussis ;
- latences nulles ou négatives ;
- horodatages invalides ;
- doublons exacts ;
- incohérences entre `date` et `cree_le` ;
- ruptures temporelles ou journées incomplètes.

Toute anomalie doit être documentée. Les données ne doivent pas être silencieusement supprimées.

---

## 4. Unité d'analyse à reconstruire

Une ligne historique représente un **appel technique**, pas nécessairement une demande utilisateur. Le benchmark doit reconstituer autant que possible l'**interaction métier**.

### 4.1 Définition d'une interaction

En l'absence d'un identifiant explicite, regrouper provisoirement les appels selon :

- même `user_id` ;
- même `potager_id` ;
- appels successifs séparés de moins de 10 secondes ;
- rupture immédiate si un nouvel événement utilisateur explicite est disponible dans les logs applicatifs.

Tester également des fenêtres de 5, 15 et 30 secondes afin de mesurer la sensibilité du regroupement.

### 4.2 Donnée à ajouter impérativement

Ajouter dès que possible un identifiant partagé par l'ensemble de la chaîne :

```text
interaction_id
```

Cet identifiant doit relier :

```text
entrée utilisateur
transcription éventuelle
classification
parsing
recherche applicative
cache
appel de génération
réponse finale
```

Ajouter aussi :

```text
request_id
parent_request_id
session_id
trace_id
```

Sans `interaction_id`, les métriques par demande utilisateur resteront estimées.

---

## 5. Segmentation obligatoire

Toutes les métriques doivent être calculées :

- globalement ;
- par jour ;
- par heure ;
- par tranche de cinq minutes ;
- par minute ;
- par utilisateur ;
- par potager ;
- par type d'appel ;
- par issue ;
- par interaction reconstituée ;
- par taille de prompt ;
- par présence ou absence de cache ;
- par phase d'usage, découverte ou régime stabilisé.

### 5.1 Classes de taille de prompt

Utiliser au minimum :

```text
0 à 499 tokens
500 à 999 tokens
1 000 à 1 999 tokens
2 000 à 3 999 tokens
4 000 à 7 999 tokens
8 000 tokens et plus
```

### 5.2 Phases d'usage

Définir automatiquement :

- **Découverte J0-J2** : trois premiers jours d'activité d'un utilisateur ;
- **Adoption J3-J7** : du quatrième au huitième jour ;
- **Stabilisation J8+** : à partir du neuvième jour actif.

Présenter également une vue par semaine calendaire.

---

## 6. Métriques historiques à calculer

## 6.1 Volumétrie

Calculer :

```text
nombre total d'appels
nombre d'appels réussis
nombre d'appels en erreur
nombre d'appels en quota
nombre d'interactions estimées
appels par interaction
appels par utilisateur actif
interactions par utilisateur actif
utilisateurs actifs par jour
utilisateurs actifs par heure
```

Pour chaque distribution, fournir :

```text
minimum
moyenne
médiane
P75
P90
P95
P99
maximum
écart-type
coefficient de variation
```

## 6.2 Tokens

Calculer séparément :

```text
tokens_in
tokens_out
tokens_cache
tokens_total = tokens_in + tokens_out
part_input = tokens_in / tokens_total
part_output = tokens_out / tokens_total
ratio_output_input = tokens_out / tokens_in
```

Produire les statistiques globales et par `appel_type`.

Calculer aussi :

```text
tokens par interaction
tokens par utilisateur actif et par jour
tokens par minute
tokens d'entrée par minute
tokens de sortie par minute
part des tokens consommée par chaque type d'appel
```

## 6.3 Latence

Calculer :

```text
latence moyenne
P50
P75
P90
P95
P99
maximum
```

Le calcul sera réalisé :

- par type d'appel ;
- par taille de prompt ;
- par heure ;
- en charge faible, moyenne et forte ;
- avec et sans tokens de cache ;
- sur le premier essai ;
- jusqu'au succès final en incluant les retries.

Si le streaming est utilisé, ajouter :

```text
time_to_first_token_ms
time_to_last_token_ms
output_tokens_per_second
```

## 6.4 Fiabilité

Calculer :

```text
taux_succes_initial
taux_succes_apres_retry
taux_erreur
taux_quota
taux_timeout
taux_HTTP_429
taux_HTTP_498
taux_HTTP_5xx
nombre_moyen_retry
```

Formules :

```text
taux_succes_initial = appels réussis au premier essai / appels initiaux
taux_succes_apres_retry = interactions finalement réussies / interactions initiées
taux_quota = appels issue=quota / appels totaux
```

## 6.5 Concurrence et débit

Pour chaque minute et chaque tranche de cinq minutes, calculer :

```text
RPM
TPM
ITPM
OTPM
nombre d'utilisateurs concurrents
nombre de potagers concurrents
nombre maximal d'appels démarrés dans une même seconde
```

Définir un utilisateur comme concurrent s'il a au moins une interaction dans la fenêtre observée.

Calculer les P50, P90, P95, P99 et maximum de RPM, TPM, ITPM et OTPM.

## 6.6 Redondance

Identifier :

- appels identiques à moins de 5 secondes ;
- appels de classification répétés pour la même interaction ;
- parsing répété sur le même contenu ;
- réponses régénérées sans modification du contexte ;
- retries déclenchés sans erreur préalable ;
- séquences d'appels parallèles susceptibles de provoquer un dépassement de quota.

Produire une estimation :

```text
part_appels_evitables
part_tokens_evitables
economie_mensuelle_potentielle
```

---

## 7. Métriques de qualité fonctionnelle à instrumenter

L'historique de tokens ne suffit pas pour mesurer la qualité. Ajouter un corpus annoté et les champs suivants.

## 7.1 Classification

Pour chaque cas, enregistrer :

```text
intention_attendue
intention_predite
culture_attendue
culture_predite
organe_attendu
organe_predit
clarification_attendue
clarification_predite
hors_perimetre_attendu
hors_perimetre_predit
```

Calculer :

```text
accuracy
precision par classe
recall par classe
F1 par classe
F1 macro
matrice de confusion
```

## 7.2 Extraction structurée

Mesurer :

```text
taux JSON syntaxiquement valide
taux conforme au JSON Schema
taux de champs obligatoires présents
taux de valeurs appartenant aux énumérations
taux de champs inventés
taux de retry de format
taux de correction applicative nécessaire
```

## 7.3 Réponse finale

Chaque réponse doit être évaluée sur :

```text
fidélité aux contenus fournis
absence d'information inventée
pertinence par rapport à la question
clarté
concision
actionnabilité
respect du ton
respect de la longueur
bonne demande de clarification
```

Utiliser une note de 0 à 5 par dimension.

Définir aussi les indicateurs binaires :

```text
réponse publiable sans correction
correction mineure nécessaire
correction majeure nécessaire
réponse dangereuse ou contradictoire
```

Toute réponse dangereuse ou contradictoire est un échec critique.

## 7.4 Fidélité factuelle

Décomposer chaque réponse en affirmations et classer chaque affirmation :

```text
supportée
partiellement supportée
non supportée
contradictoire
```

Calculer :

```text
fidelite = affirmations supportées / affirmations totales
taux_hallucination = affirmations non supportées / affirmations totales
taux_contradiction = affirmations contradictoires / affirmations totales
```

Prévoir une validation humaine sur un échantillon d'au moins 20 % des cas et 100 % des échecs critiques.

---

## 8. Corpus de benchmark

Construire un corpus initial de **500 interactions représentatives**, puis l'étendre à 1 000 après la première campagne.

Répartition initiale :

```text
150 demandes textuelles réelles anonymisées
100 transcriptions audio réelles anonymisées
100 variantes et paraphrases de demandes réelles
50 demandes avec fautes ou formulations incomplètes
40 demandes multi-intentions
30 demandes hors périmètre
20 demandes sans contenu applicatif suffisant
10 tests adversariaux ou instructions parasites
```

Chaque cas doit comporter :

```text
test_case_id
source_type
question_originale
transcription si applicable
résultat attendu de classification
résultat attendu de parsing
contenus applicatifs autorisés
réponse ou critères attendus
niveau de difficulté
criticité
```

Les données doivent être anonymisées. Ne pas conserver de nom, adresse, voix brute ou identifiant personnel dans le corpus de restitution.

---

## 9. Configurations à comparer

Le modèle reste `openai/gpt-oss-120b`. Les variations portent sur l'usage du modèle.

### Configuration A : système actuel

Utiliser sans modification :

- prompts actuels ;
- ordre actuel des messages ;
- température actuelle ;
- niveau de raisonnement actuel ;
- limites de sortie actuelles ;
- stratégie actuelle de cache et de retry.

### Configuration B : raisonnement faible

- niveau de raisonnement faible ;
- température comprise entre 0 et 0,2 ;
- mêmes prompts que la configuration A ;
- sortie plafonnée selon le type d'appel.

### Configuration C : prompt optimisé

- instructions statiques au début ;
- exemples fixes après les instructions ;
- contexte métier variable ensuite ;
- question et identifiants variables en fin ;
- suppression des timestamps et identifiants inutiles dans le préfixe ;
- suppression des contenus non utilisés ;
- raisonnement faible.

Le cache de prompt Groq repose sur une correspondance exacte du préfixe, applique une remise de 50 % aux tokens d'entrée effectivement mis en cache et expire après deux heures d'inactivité. Il est pris en charge pour GPT-OSS-120B. citeturn4search20

### Configuration D : JSON Schema strict

Pour les appels de classification et parsing :

- réponse structurée ;
- propriétés obligatoires ;
- énumérations fermées ;
- propriétés supplémentaires interdites ;
- sortie courte ;
- raisonnement faible.

GPT-OSS-120B sur Groq prend en charge le mode JSON et JSON Schema. citeturn4search19

### Configuration E : formulation minimale

Pour la réponse finale, transmettre uniquement :

- question originale ;
- intention validée ;
- faits ou contenus sélectionnés par l'application ;
- contraintes de ton et de longueur.

Plafonner la sortie à 150, 250 puis 400 tokens pour comparer l'effet sur la qualité.

### Répétitions

Exécuter chaque cas :

- trois fois pour les tests de qualité ;
- une fois pour les tests de charge ;
- avec ordre aléatoire des cas ;
- avec une période de chauffe séparée et exclue des résultats.

---

## 10. Benchmark du cache applicatif

Ne pas confondre :

- le cache de prompt du fournisseur ;
- le cache applicatif des réponses ;
- la similarité entre demandes.

### 10.1 Cache exact

Mesurer :

```text
taux_hit_exact
latence_cache_P50
latence_cache_P95
appels_LLM_evites
tokens_evites
```

### 10.2 Cache sémantique

Tester les seuils suivants :

```text
0,80
0,85
0,88
0,90
0,92
0,95
```

Pour chaque seuil, mesurer :

```text
vrais hits
faux hits
vrais rejets
faux rejets
precision du cache
recall du cache
taux de collision métier
appels évités
tokens évités
coût évité
```

Le taux de 10 % représente l'hypothèse de requêtes servies par le cache. Il ne doit pas être utilisé comme seuil de similarité.

Un faux hit est plus grave qu'un faux rejet. La cible proposée est :

```text
precision du cache >= 99,5 %
taux de faux hits <= 0,5 %
```

Pour sécuriser le cache, inclure obligatoirement dans la clé ou dans le filtre métier :

```text
intention
culture
organe
langue
version du corpus
version des règles métier
version de la réponse
```

---

## 11. Tests de charge

Les tests doivent utiliser des requêtes représentatives de la distribution historique des tailles et types d'appels.

### 11.1 Profils de charge

#### Charge de référence

```text
5 RPM pendant 15 minutes
```

#### Charge moyenne

```text
10 RPM pendant 30 minutes
```

#### Charge cible

```text
20 RPM pendant 60 minutes
```

#### Pointe de découverte

```text
30 RPM pendant 30 minutes
```

#### Pointe forte

```text
50 RPM pendant 15 minutes
```

#### Stress

```text
100 RPM pendant 5 minutes
```

#### Endurance

```text
20 à 30 RPM pendant 2 heures
```

### 11.2 Courbe de lancement

Exécuter aussi ce scénario :

```text
minutes 0 à 5   : 5 RPM
minutes 5 à 10  : 10 RPM
minutes 10 à 20 : 30 RPM
minutes 20 à 30 : 50 RPM
minutes 30 à 45 : 20 RPM
minutes 45 à 60 : 10 RPM
```

### 11.3 Distribution des requêtes

Construire trois profils :

```text
court   : environ 500 tokens d'entrée et 80 de sortie
standard: environ 1 500 tokens d'entrée et 200 de sortie
long    : environ 4 000 tokens d'entrée et 300 de sortie
```

La répartition du test doit être dérivée de l'historique. Si elle ne peut pas encore être calculée, utiliser provisoirement :

```text
40 % court
45 % standard
15 % long
```

### 11.4 Comportements attendus

Mesurer :

- saturation RPM ;
- saturation TPM, ITPM ou OTPM ;
- croissance de la latence ;
- profondeur de la file ;
- temps d'attente en file ;
- erreurs de quota ;
- erreurs de capacité ;
- retries ;
- débit après reprise ;
- perte ou duplication de demandes.

Les limites Groq s'appliquent au niveau de l'organisation et peuvent porter sur RPM, RPD, TPM, TPD, ITPM et OTPM. Les plafonds exacts du compte doivent être capturés au début de chaque campagne. citeturn4search22

Si le mode Flex est testé, isoler ses résultats. Groq indique des limites jusqu'à dix fois supérieures au mode à la demande, mais ce mode peut retourner une erreur rapide `498 capacity_exceeded`, qui nécessite un retry avec backoff et jitter. citeturn4search24

---

## 12. Modélisation de la cible de 100 utilisateurs

La projection ne doit pas se limiter à multiplier la moyenne d'un utilisateur par 100. Elle doit tenir compte de la simultanéité et de la phase d'adoption.

### 12.1 Scénarios

#### Scénario bas

```text
100 utilisateurs inscrits
30 % actifs par jour
10 interactions par utilisateur actif et par jour
10 % de hits cache
```

#### Scénario central

```text
100 utilisateurs inscrits
50 % actifs par jour
20 interactions par utilisateur actif et par jour
10 % de hits cache
```

#### Scénario découverte

```text
100 utilisateurs inscrits
80 % actifs par jour
40 interactions par utilisateur actif et par jour
5 % de hits cache au début, puis progression vers 10 %
```

#### Scénario haut

```text
100 utilisateurs inscrits
100 % actifs par jour
50 interactions par utilisateur actif et par jour
10 % de hits cache
```

### 12.2 Courbe d'adoption à simuler

```text
Semaine 1 : 100 % du volume découverte
Semaine 2 : 75 % du volume découverte
Semaine 3 : 60 % du volume découverte
Semaine 4 : convergence vers le scénario central
Mois 2+  : scénario central avec saisonnalité
```

### 12.3 Méthode de projection

Pour chaque scénario, calculer :

```text
interactions_mensuelles
appels_LLM_mensuels
appels_par_interaction
tokens_in_mensuels
tokens_out_mensuels
tokens_cache_mensuels
coût_mensuel
coût_par_utilisateur_inscrit
coût_par_utilisateur_actif
RPM_P95_projeté
RPM_P99_projeté
TPM_P95_projeté
TPM_P99_projeté
ITPM_P99_projeté
OTPM_P99_projeté
```

Étapes :

1. Calculer la distribution historique des interactions par utilisateur actif.
2. Calculer la distribution historique des appels par interaction.
3. Séparer découverte et stabilisation.
4. Appliquer un modèle de concurrence, de préférence une simulation de Monte-Carlo par minute.
5. Utiliser au moins 10 000 journées simulées par scénario.
6. Conserver les corrélations entre type d'appel, taille du prompt et nombre d'appels.
7. Appliquer le cache avant le calcul des appels LLM.
8. Conserver séparément les tokens d'entrée, de sortie et de cache.
9. Produire des intervalles P50, P90, P95 et P99, pas uniquement une moyenne.
10. Appliquer une marge de sécurité de 30 % au dimensionnement final.

---

## 13. Calcul financier

Utiliser comme paramètres configurables :

```text
prix_input_par_million = 0.15 USD
prix_cached_input_par_million = 0.075 USD
prix_output_par_million = 0.60 USD
```

Ces tarifs correspondent aux prix publiés pour GPT-OSS-120B sur Groq à la date du 9 septembre 2026. citeturn4search19turn4search20

Formule :

```text
cout_input = tokens_in_non_cache / 1_000_000 * prix_input_par_million
cout_cache = tokens_cache_factures / 1_000_000 * prix_cached_input_par_million
cout_output = tokens_out / 1_000_000 * prix_output_par_million
cout_total = cout_input + cout_cache + cout_output
```

Avant calcul, confirmer la sémantique de `tokens_in` et `tokens_cache` dans les logs pour éviter un double comptage.

Calculer :

```text
coût par appel
coût par interaction
coût par type d'appel
coût par utilisateur actif
coût par mois
coût de la phase de découverte
coût évité grâce au cache applicatif
coût évité grâce au cache de prompt
coût des retries
coût des appels redondants
```

Pour les traitements asynchrones du benchmark ou les évaluations massives, la Batch API peut appliquer une réduction de 50 % sans consommer les limites standards. Le résultat Batch doit être isolé du benchmark interactif et la remise ne se cumule pas avec celle du cache de prompt. citeturn4search21

---

## 14. Seuils d'acceptation initiaux

Ces seuils constituent un point de départ. Ils devront être ajustés après la première campagne.

### Qualité

```text
classification_accuracy >= 95 %
F1_macro >= 93 %
JSON_valide >= 99,5 %
JSON_schema_conforme >= 99 %
fidélité >= 98 %
taux_hallucination <= 1 %
taux_contradiction = 0 % sur cas critiques
réponses publiables sans correction >= 90 %
```

### Performance

```text
latence P50 <= 1 500 ms
latence P95 <= 3 000 ms
latence P99 <= 6 000 ms
succès initial >= 99 %
succès après retry >= 99,9 %
timeout <= 0,2 %
```

### Cache

```text
taux de faux hits <= 0,5 %
precision cache >= 99,5 %
taux de hits mesuré >= 10 % à maturité
latence cache P95 <= 100 ms
```

### Capacité

```text
30 RPM pendant 30 minutes sans perte
50 RPM pendant 15 minutes avec dégradation maîtrisée
reprise automatique après saturation
aucune duplication d'interaction
aucune perte silencieuse
```

### Économie

```text
coût mensuel par utilisateur inscrit <= 1 USD
contexte médian cible <= 2 000 tokens
sortie médiane cible <= 250 tokens
```

---

## 15. Instrumentation à ajouter

Étendre les logs avec :

```text
interaction_id
request_id
parent_request_id
session_id
trace_id
provider
model
service_tier
prompt_version
schema_version
corpus_version
cache_key
cache_type
cache_hit
cache_similarity_score
cache_threshold
cache_age_seconds
input_tokens_uncached
input_tokens_cached
output_tokens
reasoning_level
max_output_tokens
temperature
queue_wait_ms
time_to_first_token_ms
time_to_last_token_ms
retry_count
http_status
error_code
fallback_used
classification_confidence
response_length_chars
response_length_words
user_feedback
```

Ne pas journaliser en clair :

- les fichiers audio ;
- les données personnelles ;
- l'intégralité des prompts contenant des informations sensibles.

Prévoir un hash stable ou un identifiant anonymisé lorsque l'analyse de répétition est nécessaire.

---

## 16. Livrables obligatoires

Produire les fichiers suivants :

```text
benchmark_data_quality.md
benchmark_historical_summary.md
benchmark_quality_results.md
benchmark_load_results.md
benchmark_cache_results.md
benchmark_capacity_projection.md
benchmark_cost_projection.md
benchmark_recommendations.md
benchmark_results.csv
benchmark_interactions.csv
benchmark_minute_metrics.csv
benchmark_errors.csv
benchmark_configurations.json
```

### 16.1 Contenu du rapport de synthèse

Le rapport final doit contenir :

1. périmètre et période analysée ;
2. qualité des données ;
3. profil réel d'un appel ;
4. profil réel d'une interaction ;
5. répartition classification, parsing et question ;
6. distributions de tokens ;
7. distributions de latence ;
8. erreurs et quotas ;
9. pics RPM, TPM, ITPM et OTPM ;
10. efficacité des caches ;
11. qualité fonctionnelle ;
12. projection des quatre scénarios à 100 utilisateurs ;
13. coût mensuel P50, P95 et P99 ;
14. capacité recommandée ;
15. quota fournisseur à demander ;
16. optimisations prioritaires ;
17. limites et incertitudes.

### 16.2 Tableau de décision final

Le rapport doit conclure avec :

```text
capacité RPM recommandée
capacité TPM recommandée
capacité ITPM recommandée
capacité OTPM recommandée
marge de sécurité
coût mensuel central
coût mensuel en découverte
latence P95 attendue
taux de succès attendu
taux de cache attendu
risques principaux
décision GO / GO sous conditions / NO GO
```

---

## 17. Graphiques à produire

Produire au minimum :

- appels par jour et par type ;
- tokens d'entrée et de sortie par jour ;
- boxplots des tokens par type d'appel ;
- latence P50/P95/P99 par type ;
- nuage de points tokens d'entrée versus latence ;
- RPM et TPM par minute ;
- heatmap activité par jour et heure ;
- taux d'erreur dans le temps ;
- appels par interaction ;
- répartition du coût par type d'appel ;
- courbe précision versus taux de hit du cache sémantique ;
- projection mensuelle pour 100 utilisateurs ;
- coût mensuel P50/P95/P99 par scénario ;
- capacité requise versus quota disponible.

Ne pas utiliser uniquement des moyennes. Afficher systématiquement les percentiles pertinents.

---

## 18. Règles d'interprétation

- Ne pas extrapoler une journée de test intensif comme une journée utilisateur normale.
- Identifier séparément les scripts ou campagnes ayant généré des centaines d'appels rapprochés.
- Ne pas interpréter `user_id = 1` ou `2` comme un profil d'usage représentatif sans distinguer les tests techniques.
- Ne pas mélanger les transcriptions audio et les tokens LLM.
- Ne pas considérer les tokens en cache comme des appels évités.
- Ne pas confondre taux de similarité, seuil de similarité et taux de hit.
- Ne pas conclure sur la qualité fonctionnelle à partir des seuls tokens et latences.
- Documenter chaque hypothèse et produire une analyse de sensibilité.
- Conserver les résultats bruts afin que les agrégations puissent être recalculées.

---

## 19. Questions à résoudre lors de l'intégration

Chercher les réponses dans le code et la configuration avant de demander une intervention humaine :

1. Quelle action utilisateur déclenche chaque type d'appel ?
2. Une interaction peut-elle déclencher plusieurs appels `question` ?
3. Les appels `classification` et `parsing` sont-ils séquentiels ou parallèles ?
4. Où se trouve le cache applicatif ?
5. Comment est calculée la similarité ?
6. Les tokens de prompt incluent-ils les contenus RAG complets ?
7. Le prompt système est-il identique entre les utilisateurs ?
8. Le niveau de raisonnement est-il explicitement configuré ?
9. Quels sont les timeouts et règles de retry ?
10. Quels sont les quotas exacts du compte Groq ?
11. Le streaming est-il activé ?
12. Les retours utilisateur permettent-ils de mesurer la qualité ?

Si une donnée reste introuvable, la déclarer comme inconnue et préciser son impact sur l'estimation.

---

## 20. Ordre d'exécution

### Phase 1 : audit historique

1. charger l'historique ;
2. contrôler sa qualité ;
3. filtrer GPT-OSS-120B ;
4. détecter les périodes de test intensif ;
5. reconstruire provisoirement les interactions ;
6. calculer tokens, latences, erreurs, RPM et TPM ;
7. produire le baseline.

### Phase 2 : instrumentation

1. ajouter `interaction_id` et `trace_id` ;
2. ajouter les métriques de cache ;
3. ajouter les temps de file et de streaming ;
4. versionner prompts, schémas et corpus ;
5. confirmer la comptabilisation des tokens.

### Phase 3 : qualité

1. créer les 500 cas annotés ;
2. lancer les configurations A à E ;
3. évaluer automatiquement les formats ;
4. faire valider humainement au moins 20 % des cas ;
5. mesurer stabilité et erreurs critiques.

### Phase 4 : charge

1. exécuter une chauffe ;
2. lancer les paliers ;
3. exécuter endurance et courbe de découverte ;
4. tester retry, quota et reprise ;
5. comparer on-demand et Flex seulement si nécessaire.

### Phase 5 : projection

1. construire les distributions historiques ;
2. simuler les quatre scénarios ;
3. intégrer le cache ;
4. calculer P50/P90/P95/P99 ;
5. appliquer 30 % de marge ;
6. formuler le besoin de quota.

---

## 21. Critère de réussite de la mission

La mission est terminée uniquement si elle produit une recommandation chiffrée et traçable sous cette forme :

```text
Pour 100 utilisateurs, le système doit être dimensionné à X RPM,
Y TPM, Z ITPM et W OTPM, avec 30 % de marge.

Le coût mensuel estimé est de A USD en régime central,
B USD au P95 et C USD pendant la phase de découverte.

La latence attendue est de D ms au P95.
Le taux de succès après retry est de E %.
Le cache applicatif évite F % des appels et G % des tokens.

Décision : GO / GO sous conditions / NO GO.
Conditions : liste chiffrée et priorisée.
```

---

## 22. Informations complémentaires utiles mais non bloquantes

Le benchmark peut commencer avec l'historique existant. Les éléments suivants amélioreront fortement sa précision lorsqu'ils seront disponibles :

- export CSV complet et non tronqué ;
- code ou configuration construisant les prompts ;
- limites Groq exactes du compte ;
- règles de retry et timeout ;
- implémentation du cache et seuil de similarité ;
- relation exacte entre action utilisateur et appels techniques ;
- durée moyenne des fichiers audio ;
- estimation du nombre d'interactions quotidiennes voulu par utilisateur ;
- exemples anonymisés de questions, contenus sélectionnés et réponses finales ;
- acceptation ou non d'un test en environnement de production contrôlé.

Ces éléments ne doivent pas retarder l'audit initial. Toute hypothèse provisoire doit être paramétrable et clairement signalée dans les résultats.

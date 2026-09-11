# 🎯 Décisions — Prérequis à la Vague 2 / Piste A

> **Statut :** ✅ arbitré — à implémenter
> **Date :** 27/08/2026
> **Portée :** deux insertions avant US-096, un réordonnancement de la piste A, une action de mesure sans code.
> **Sources :** `PLAN_PRODUCTION_EPIC6_REFERENTIEL.md` §4.4, `VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md` §7.2 / §8, `AUDIT_PASSERELLE_LLM_US092.md`.
> **Convention :** ✅ fait établi / tranché · 🔶 hypothèse à valider · 🧪 à mesurer · ⚖️ arbitrage · 🔴 risque.

---

## 1. État de départ

Vague 1 livrée : **US-092** (passerelle LLM unique, `conso_tokens`, réordonnancement des prompts pour le cache fournisseur), **US-093** (routeur règles-first, `routage_logs`), **US-097** (observabilité + retour 👍/👎).

Vague 2 / Piste A démarrée sur **US-096** (gabarits sur agrégats SQL).

**Ce document insère deux US courtes avant US-096 et réordonne la piste A.**

---

## 2. Séquence arrêtée

| Ordre | Quoi | Pts | Nature |
|---|---|---:|---|
| 0 | Deux rejeux de corpus → `routage_logs` | ½ j | Mesure, sans code applicatif |
| 1 | **Arbitrage unités + convergence actions** | 2 | 🔴 Prérequis dur d'US-096 |
| 2 | **`date_source` — instrumentation seule** | 1 | Indépendant, non bloquant |
| 3 | **US-096** — gabarits sur agrégats SQL | 5 | Inchangée |
| 4 | **US-094** — parseur déterministe + ancrage temporel | 9 | +1 (ancrage) |
| 5 | **US-095** — cache de questions | 5 | ⏸️ Différée |

**Réordonnancement acté : `096 → 094 → 095`** et non `096 → 095 → 094`.

⚖️ **Motif du report d'US-095 :** le taux de hit d'un cache de questions est proportionnel au volume. À un utilisateur, il est proche de zéro, tandis que l'invalidation événementielle introduit un risque de réponse périmée servie avec assurance — exactement le défaut que la cascade cherche à éliminer. Aucune dépendance ne l'impose avant US-094. À reprendre quand `routage_logs` montre des motifs de question réellement répétés.

---

## 3. Insertion 1 — Arbitrage unités + convergence actions (2 pts)

### Pourquoi maintenant

`unite` et `type_action` sont les **deux clés de `GROUP BY` d'US-096**. Les corriger après avoir écrit les gabarits impose de réécrire les gabarits *et* de rejouer une migration. C'est une asymétrie de coût, pas un volume de données sales.

Constats mesurés en production (`VAGUE0` §8.5 et §8.3, 225 saisies réelles) :

| Constat | Volume |
|---|---:|
| `plants` | 88 |
| `g` | 43 |
| `graines` | 22 |
| `kg` | 15 |
| `pieds` | 4 |
| `pied` | 3 |
| `type_action = 'binage'` hors référentiel | 2 |
| `type_action = 'eclaircie'` hors référentiel | 1 |

### ⚖️ Arbitrage principal — `plants` vs `pied(s)`

Le vrai sujet n'est pas `pied` / `pieds` (7 lignes) mais **`plants` (88) vs `pied(s)` (7)** : deux façons de compter la même chose, sur ~42 % des saisies. C'est une décision produit, pas une normalisation technique. Elle doit être **écrite** avant toute implémentation.

### 🔶 Périmètre — le piège à éviter

`VAGUE0` §8.5 écrit « le référentiel devra trancher, pas juste lister ». Lu extensivement, cela invite à construire une table `unites` avec conversions, unités par défaut par culture et cardinalités : **5 à 8 points, hors périmètre**.

Ce dont US-096 a besoin se limite strictement à trois éléments :

1. une **décision d'arbitrage écrite** (`plants` / `pied(s)`, et le pluriel en général) ;
2. une **fonction de normalisation appliquée à l'écriture** (dépluralisation, translittération des exposants `²` → `2`) ;
3. un **backfill** des lignes historiques concernées (~7 lignes).

Pas de table de référence, pas de conversion, pas d'unité par défaut.

### Convergence des référentiels d'actions

`VAGUE0` §7.2 point 1 : les deux référentiels du code divergent.

- `utils/actions.ACTION_MAP` connaît `amendement` et `protection`
- `utils/validation.ACTIONS_VALIDES` connaît `fertilisation` et `repiquage`

🔴 **Conséquence directe sur US-096 :** un gabarit qui itère sur `ACTIONS_VALIDES` perd silencieusement les événements `binage` déjà en base. La divergence n'est pas cosmétique, elle produit des agrégats faux.

**À faire :** trancher la source de vérité unique, puis ajouter `binage` et `eclaircissage` — ce sont des gestes de jardinage réels, absents du référentiel de 12 actions.

### Critères d'acceptation suggérés

1. Un seul référentiel d'actions fait foi ; l'autre le référence ou disparaît.
2. `binage` et `eclaircissage` sont des `type_action` canoniques.
3. La normalisation d'unité est appliquée à l'écriture, pas seulement à la lecture.
4. Migration séparée, idempotente (`IF NOT EXISTS`), rollback documenté.
5. 🧪 Test : `GROUP BY unite` sur les 225 saisies de production ne produit plus de doublon sémantique.

---

## 4. Insertion 2 — `date_source` (1 pt)

### ⚖️ Ce qui a été tranché, et ce qui a été abandonné

`VAGUE0` §8.1 relève que la date est le champ le plus corrigé (27,5 % des corrections, 11 sur 12 ramenant la date en arrière de 5 à 25 jours).

**Deux points ont été clarifiés et invalident les correctifs initialement envisagés :**

- ✅ La convention « aucune précision de temps dictée = date du jour » est un **choix de conception explicite et cohérent**, pas un défaut. Un événement est par nature situé dans le temps.
- ✅ Après correction, le champ `date` de l'événement **est mis à jour**, en plus de la trace `[CORR]` dans `texte_original`. Les données ne sont pas corrompues et US-096 n'agrège pas des valeurs fausses.

**En conséquence, sont abandonnés :**

- ⛔ la mention « date présumée » dans le message de confirmation — toutes les saisies sans ancrage explicite retombent sur aujourd'hui, l'affichage serait systématique et n'informerait personne ;
- ⛔ le qualificatif d'incertitude dans les gabarits d'US-096 — **US-096 reste à 5 points, sans impact.**

### 🔶 Ce qui subsiste : une limite épistémique

La convention n'est **pas vérifiable ligne par ligne**. Après coup, une ligne non corrigée est soit exacte, soit fausse et jamais remarquée. Les 12 corrections mesurent ce qui a été *remarqué* : elles donnent une **borne basse**, jamais le taux d'erreur réel.

🔴 **Le périmètre où cela mord réellement : les durées calculées (Épic 5).** Le biais est asymétrique. Une plantation saisie 14 jours après le geste et une récolte saisie le jour même produisent un cycle **raccourci de 14 jours**. Les cinq exemples du §8.1 sont tous des plantations, toutes décalées vers l'avant. Un référentiel phénologique recalé sur ces données serait systématiquement trop court, sans qu'aucune donnée ne permette de s'en apercevoir.

### Ce qui est demandé

Une colonne **`date_source`**, `VARCHAR` **nullable**, renseignée à l'écriture au **site de fallback existant** — celui qui pose déjà `date = today`. Aucune nouvelle logique de détection.

⚖️ **`VARCHAR` et non `BOOLEAN` :** US-094 ajoutera la valeur `'relative_resolue'` lorsqu'il saura résoudre « la semaine dernière ». Un booléen forcerait à rouvrir la migration, ce que l'invariant « aucune migration ne rouvre une table modifiée par une autre US en vol » interdit.

| Valeur | Signification |
|---|---|
| `'explicite'` | Une date a été dictée et parsée |
| `'presumee'` | Aucun ancrage — fallback sur aujourd'hui |
| `NULL` | Antérieur à cette US — inconnu, et c'est la seule chose vraie qu'on puisse en dire |

**Réservée pour US-094 :** `'relative_resolue'` (« hier », « il y a 4 jours »).

### 🔴 Invariant — instrumentation seule

`date_source` n'est **ni affichée à l'utilisateur, ni lue par un gabarit, ni utilisée dans une condition métier**. Elle sert exclusivement à :

1. mesurer, dans trois mois, le taux d'erreur **réel** de la convention, par croisement avec les traces `[CORR]` — au lieu de la borne basse actuelle ;
2. permettre à l'Épic 5 d'écarter les lignes douteuses lors du recalage phénologique.

### Pourquoi maintenant plutôt qu'après

Aujourd'hui la convention tient parce que le développeur est le seul utilisateur et qu'il la connaît. **À l'ouverture beta, elle devient une hypothèse sur le comportement d'inconnus qui ne l'ont jamais lue.** La colonne écrite maintenant est renseignée dès leur première saisie ; ajoutée après, elle laisse un trou sur exactement la période qui intéresse.

### Critères d'acceptation suggérés

1. Migration séparée, idempotente, colonne nullable, rollback documenté.
2. Renseignée au site de fallback existant — aucun nouveau détecteur.
3. Les lignes antérieures restent à `NULL` ; **aucun backfill**.
4. 🧪 Test : aucun gabarit, aucun message utilisateur, aucune condition métier ne lit `date_source`.
5. La requête de croisement `date_source` × traces `[CORR]` est fournie dans `tools/`.

---

## 5. Impact sur US-094

**8 → 9 points.**

Le `+1` couvre la **grammaire d'ancrage temporel** : « hier », « avant-hier », « il y a N jours », « la semaine dernière ». Elle alimente la valeur `'relative_resolue'` de `date_source`.

✅ Ce gain est **indépendant du débat sur la convention**. `VAGUE0` §8.1 documente le cas : « Plantation de 20 plants de salades […] **la semaine dernière** » a été daté du 28/03 au lieu du 21/03. Ici le jardinier **a** donné un ancrage et le système l'a ignoré. C'est un défaut de parsing, pas une convention.

### 🔶 Reframe — pas de tour de dialogue

L'option « demander plutôt que présumer » est **écartée**. Elle imposerait un état supplémentaire dans `ctx.user_data`, donc un risque sur l'ordre critique de `handle_text` (`corr_*` > mode `ask` > NAV > `_is_question` > action) — l'invariant le plus fragile du projet.

Le système de correction existant suffit et fonctionne (35 traces `[CORR]` en production le démontrent). **Aucun état nouveau n'est introduit par US-094 sur ce sujet.**

---

## 6. Action 0 — Deux rejeux, deux mesures

À exécuter contre le routeur d'US-093, résultats lus dans `routage_logs`.

| Corpus | Volume | Branche testée | Mesure |
|---|---:|---|---|
| `docs/CORPUS_QUESTIONS_DIAGNOSTIC_CA11.md` | 44 (dont 19 v1) | **savoir** | Taux de bon routage |
| `texte_original` de production | 225 | **action** | Taux de bon routage |

🔴 **Ne pas fusionner les deux corpus.** Ils ne mesurent pas la même chose, et leur proportion relative est choisie par le développeur, non observée. Les additionner produirait une pseudo-distribution « 40/35/20/5 » dont le dénominateur n'existe pas.

🔶 **La distribution réelle par étage n'est pas mesurable au volume actuel** (un utilisateur, 225 saisies sur cinq mois). Le jalon de décision du `PLAN_PRODUCTION` §4.3 est requalifié en **revue post-beta**, à conduire lorsque plusieurs jardiniers auront tourné un mois.

✅ **Cela ne bloque rien.** La cascade n'a pas besoin de la distribution pour être correcte : un mauvais routage tombe à l'étage suivant. La distribution pilote une **priorisation**, pas une justesse. US-096, l'insertion 1, l'insertion 2 et US-094 sont justifiées indépendamment.

---

## 7. Récapitulatif

**Insertion nette : 3 points.** Aucun impact sur US-096 (5 pts, inchangée). `+1` sur US-094 (8 → 9).

**Ordre d'exécution :** rejeux → insertion 1 → insertion 2 → US-096 → US-094 → *(US-095 différée)*.

**Invariants à respecter :** migrations séparées et idempotentes · `.replace()` sur les prompts, jamais `.format()` · `db.get()`, jamais `db.query().get()` · logging structuré `HH:MM:SS │ LEVEL │ emoji` · tout appel LLM via `llm/passerelle.py` · compatible SentinelOne (polling) · ordre critique de `handle_text` préservé.

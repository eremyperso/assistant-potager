# ✅ Vague 0 — ÉPIC 6 × moteur de réponses V2 : décisions et extractions

> **Rédigé le :** 25/08/2026
> **Branche :** `epic-6-referentiel-connaissance-cultures` (issue de `dev`, HEAD `b92526b`)
> **Nature :** relevé de décisions. Aucune ligne de code, aucune migration.
> **Exécute :** `PLAN_PRODUCTION_EPIC6_REFERENTIEL.md` §4.2 (vague 0) et §6 (48 heures).
> **Tranche :** les 3 amendements de `PLAN_PRODUCTION_EPIC6_REFERENTIEL.md` §3 et les
> 4 arbitrages de `CONCEPTION_REFERENTIEL_CONNAISSANCE_CULTURES.md` §7.2.
> **Convention :** ✅ tranché · 🔶 hypothèse · 🧪 à mesurer.

---

## 1. Les trois amendements du §3 — tranchés

Tous les trois sont **adoptés**. Ce sont des corrections de cohérence interne au backlog, pas des
choix produit : chacun évite une migration rejouée ou une seconde vérité concurrente. Les US
concernées sont amendées sur cette branche.

### 1.1 ✅ US-067 — la rotation devient calculable, et la famille devient une table

**Adopté, dans les deux volets.**

| Volet | Décision |
|---|---|
| Délai de retour | La famille botanique porte un **délai de retour recommandé en années**, pré-rempli pour les familles connues, **nullable**, corrigeable depuis le bot. Une famille sans délai n'empêche aucun affichage : elle rend seulement l'avertissement de rotation indisponible pour les cultures de cette famille |
| Support de la famille | **Table de référence**, pas colonne texte sur `culture_config` |

**Motif du second volet :** un délai de retour est un attribut *de la famille*, pas *de la culture*.
Porté en colonne, il se duplique sur chaque culture de la famille et devient incohérent à la
première correction — le jardinier corrige « Solanacées : 4 ans » sur la tomate et la pomme de terre
reste à 3. La table de référence rend la correction unique par construction, et elle est cohérente
avec le CA7 déjà écrit (« la famille est identique quel que soit le potager »).

**Vérifié en base (dev) :** `culture_config` porte 54 lignes, **toutes à `potager_id` NULL**. Le
référentiel est donc déjà entièrement partagé — la table de familles s'y branche sans introduire de
régime nouveau.

**Impact :** US-067 passe de **5 à 6 points**. Sans cet amendement, US-163 devait rouvrir la
migration de `culture_config` : exactement le travers « migrations concurrentes » signalé en
Épic 5 §9.

### 1.2 ✅ US-140 / CA5 — les relations sortent des fiches

**Adopté.** La règle que CA7 applique déjà aux dates s'applique mot pour mot aux associations et à
la rotation : une association écrite dans une fiche est un texte, elle ne peut ni être jointe à
l'historique d'une parcelle, ni déclencher l'avertissement d'US-167. Écrite aux deux endroits, elle
devient la seconde vérité concurrente que CA7 interdit par ailleurs.

- CA5 amendé : retrait de « associations favorables et défavorables, principes de rotation ».
- CA7bis ajouté, symétrique de CA7 : une fiche ne contient ni association ni règle de rotation ;
  elle peut en revanche **expliquer** un mécanisme, la relation restant portée par US-163.

**Impact :** US-140 s'allège, ce qui sert directement son arbitrage « dix cultures, pas trente ».
Estimation inchangée à 8 points — l'allègement du CA5 est compensé par le rattachement du livrable
de source (§4 ci-dessous) et par l'exigence de plan imposé de l'arbitrage 2.

### 1.3 ✅ US-098 / CA2 — `culture` en référence, pas en libellé

**Adopté.** `knowledge_chunks.culture` en métadonnée texte est exactement l'erreur corrigée par
`migration_v12` sur `evenements.parcelle`. Une culture renommée depuis le bot orphelinerait
silencieusement ses fragments.

**Impact :** nul, tant qu'US-098 n'est pas implémentée. Coûteux ensuite. C'est la raison d'être de
la vague 0.

---

## 2. Les quatre arbitrages du §7.2 — tranchés

### 2.1 ✅ Arbitrage 1 — licence : **option A, zéro CC-BY-SA dans le socle**

Le socle se limite à **CC0** (Wikidata) et **Licence Ouverte / Etalab** (E-Phy / ANSES), plus la
rédaction interne. Permapeople, Wikipédia FR, Plants For A Future, Practical Plants et Growstuff
sont **exclus de tout import**.

**Conséquences opérationnelles :**

- Le corpus de fiches reste **100 % propriétaire**, sans contrainte de publication ni de partage à
  l'identique. La trajectoire SaaS commerciale reste ouverte sans réexamen juridique.
- Aucun double régime d'affichage à maintenir dans l'interface : une seule règle d'attribution,
  celle de la Licence Ouverte.
- `referentiel_source.partageable` **reste au modèle** malgré tout : la colonne coûte deux lignes de
  migration et constitue la seule façon de rendre l'option B réversiblement atteignable si une
  source CC-BY-SA devenait un jour indispensable sur les associations. Elle vaut `true` pour toutes
  les sources retenues aujourd'hui.
- Les associations (couche 2) sont donc **saisies**, pas importées. C'est le coût réel de cette
  option — et, comme le note la conception §6.2, c'est aussi ce qui en fait un actif différenciant.
- Ephytia (INRAE) reste une **source de lecture** pour la rédaction humaine, jamais une source
  d'import.

### 2.2 ✅ Arbitrage 2 — rédaction assistée du narratif : **acceptée, avec garde-fous**

Les ~70 fiches courtes (≈30 cultures + ≈40 bioagresseurs) sont produites par un passage LLM **hors
ligne, une seule fois**, sur un **plan imposé**, puis relues humainement.

**Les quatre garde-fous sont des conditions, pas des recommandations :**

1. **Aucun chiffre produit par le LLM.** Durées, doses, espacements, profondeurs, délais de retour
   viennent **exclusivement** de la couche 1 (import) ou de la saisie. Une fiche générée contenant un
   chiffre non sourcé est refusée à la relecture.
2. **`niveau_confiance = 'indicatif'` par défaut.** Le passage à `'verifie'` n'a lieu qu'après
   relecture par une personne qui jardine.
3. **Plan de fiche imposé et identique pour toutes**, sans quoi le découpage en fragments d'US-098
   (CA12, un fragment = une idée répondable) devient irrégulier.
4. **Mention de source visible** côté utilisateur, cohérente avec US-140 / CA4.

**Coût :** ~85 000 tokens, une journée de quota, une fois pour toutes. Hors ligne — donc hors du
chemin critique du jardinier et hors du quota qui sert les réponses.

**Cohérence projet :** respecte le principe d'honnêteté de l'Épic 5 §4 — *l'application n'invente
jamais une date ni une durée*. Elle ne reformule ici que du savoir commun, et rien de chiffré.

### 2.3 ✅ Arbitrage 3 — périmètre initial : **les dix cultures les plus fréquentes**

Confirme US-140 / CA1, déjà tranché dans le même sens. La liste nominative est établie par
l'extraction [1] du §3 ci-dessous, et non par intuition.

L'extension se fait au fil des questions restées sans réponse (US-097 / CA14) et du rapport de
couverture d'US-166b — **pas** au fil de l'envie d'exhaustivité. Les 54 lignes de `culture_config`
en dev, dont **14 sans aucun événement**, illustrent précisément le risque de fiches fantômes que
ce périmètre écarte.

### 2.4 ✅ Arbitrage 4 — `/fiche <culture>` : **sur commande uniquement**

Pas de restitution spontanée après une saisie, ni en v1 ni en option.

**Motif :** l'ordre critique des flux de `handle_text` (modes `corr_*` > mode `ask` > NAV >
`_is_question` > action) est l'invariant le plus fragile du projet, et US-092 va déjà le remuer.
Ajouter un branchement post-saisie dans le même trimestre, pour un gain pédagogique marginal, n'est
pas un arbitrage raisonnable. La commande préfixée reste à l'étage 0 : zéro jeton, zéro effet de
bord, zéro bruit dans le flux vocal.

🔶 Réouvrable plus tard, en opt-in explicite, une fois la cascade stabilisée. À rattacher alors à
US-164, pas à une US nouvelle.

---

## 3. Les trois extractions SQL du §7.1

> ⚠️ **Portée des mesures.** Exécutées le 25/08/2026 sur la **base de développement locale**
> (`potager_dev`, 220 événements, 5 potagers, 54 configurations de culture). La base de production
> n'est pas joignable depuis le poste : le port 5432 du VPS n'est ouvert qu'aux IP administrateur
> et aucun `.env.prod` n'existe localement.
>
> **US-140 / CA1 exige explicitement la mesure sur les données réelles de production.** La liste
> nominative du §3.1 est donc **à reconfirmer sur `potager_prod`** avant d'ouvrir la rédaction des
> fiches. Elle est déjà suffisante pour chiffrer US-160/US-161/US-162 et pour cadrer la table
> `symptome` d'US-165.

### 3.1 Extraction [1] — le périmètre réel du référentiel

`SELECT culture, COUNT(*), MIN(date), MAX(date) FROM evenements WHERE culture IS NOT NULL GROUP BY culture ORDER BY 2 DESC`

**40 cultures distinctes portent au moins un événement** (207 événements sur 220 portent une
culture ; les 13 autres sont des observations de parcelle ou des bulletins météo). Les dix
premières concentrent **110 de ces 207 événements, soit 53 %**.

| # | Culture | Événements | Période observée | Types d'action distincts |
|---:|---|---:|---|---:|
| 1 | tomate | 31 | 01/02 → 22/07 | 9 |
| 2 | haricot | 15 | 20/04 → 19/07 | 4 |
| 3 | courgette | 14 | 01/04 → 19/07 | 8 |
| 4 | chou | 11 | 01/03 → 12/08 | 4 |
| 5 | carotte | 9 | 01/03 → 21/08 | 4 |
| 6 | concombre | 7 | 01/04 → 05/07 | 6 |
| 7 | cornichon | 7 | 01/04 → 05/07 | 4 |
| 8 | poivron | 6 | 01/02 → 19/07 | 6 |
| 9 | ail | 5 | 10/02 → 20/06 | 4 |
| 10 | blette | 5 | 28/03 → 22/06 | 4 |

⚠️ **Le seuil des dix est arbitraire ici.** Six cultures sont à égalité à 5 événements — ail,
blette, fève, petit pois, poireau, épinard — et seules deux entrent dans le classement, par ordre
alphabétique. Les rangs 9 et 10 ne sont donc **pas** établis par la mesure : ils le seront par la
reprise sur production. Suivent à 4 : fraise, laitue, melon, aubergine, pomme de terre, potiron,
butternut, fenouil.

**Trois observations qui pèsent sur le modèle, au-delà du simple classement :**

1. **Les cucurbitacées sont fragmentées en dix libellés** — courgette, cornichon, concombre, melon,
   potiron, butternut, courge, potimarron, pâtisson, pastèque — soit **52 événements cumulés**, très
   au-dessus de la tomate. Le classement par libellé sous-estime donc structurellement le poids
   d'une famille. C'est un argument de plus pour l'amendement §1.1 : la famille botanique n'est pas
   un simple regroupement d'affichage, c'est le bon grain d'analyse. 🔶 À vérifier en production :
   si le constat s'y confirme, la rédaction des fiches gagne à traiter la famille d'abord et à
   décliner les spécificités ensuite.
2. **`laitue` et `salade` coexistent** (4 et 3 événements) et désignent vraisemblablement la même
   chose. `haricot` et `haricot grimpant` également (15 et 2). Le rapprochement de synonymes est un
   travail d'US-166b, pas de rédaction : à traiter comme un cas d'appariement, avec revue humaine
   (conception §5.2, clé « nom vernaculaire », fiabilité ⚠️ faible).
3. **La saison couverte va de février à août 2026** — une seule campagne. Aucune donnée
   inter-annuelle n'existe encore : le calcul de rotation d'US-163/US-167 sera donc **structurellement
   sans matière** sur cette base jusqu'à la campagne 2027. 🔶 À confirmer sur production. Si le
   constat s'y confirme, l'avertissement de rotation doit être conçu pour un historique court et
   dire honnêtement « je n'ai pas d'antécédent sur cette parcelle » plutôt que « aucun conflit ».

### 3.2 Extraction [2] — l'écart entre le vocabulaire réel et `culture_config`

`SELECT DISTINCT e.culture … LEFT JOIN culture_config … WHERE cc.id IS NULL`

**Résultat : zéro culture orpheline.** Toute culture portant un événement possède sa configuration.
Le mécanisme de création à la volée fonctionne, et l'appariement `LOWER(nom)` suffit sur ces données.

**L'écart réel est dans l'autre sens**, et c'est lui qui importe :

| Constat | Valeur |
|---|---|
| Lignes dans `culture_config` | 54 |
| Dont **sans aucun événement** | **14** |
| `potager_id` renseigné | **aucun** — les 54 lignes sont partagées |

Les 14 sans événement : `asperge`, `brocoli`, `capucine`, `chou de Bruxelles`, `chou frisé`,
`ciboulette`, `coriandre`, `menthe`, `mesclun`, `oseille`, `rhubarbe`, `romarin`, `thym`,
`épinard perpétuel`.

**Ce que ça tranche :**

- Le **point de vigilance d'US-067** (« ne pas peupler les écrans de cultures fantômes ») est
  confirmé par la mesure : 26 % des configurations existantes sont déjà des cultures jamais
  utilisées. Le pré-remplissage de famille ne doit **pas** créer de configuration nouvelle, et le
  rapport de couverture d'US-166b doit distinguer *couvert / non couvert / configuré mais inutilisé*.
- `culture_config` étant intégralement à `potager_id` NULL, la table de familles de l'amendement
  §1.1 s'y branche sans cas particulier multi-potager.

### 3.3 Extraction [3] — le vocabulaire spontané des problèmes

`… WHERE type_action IN ('observation','traitement') OR commentaire ILIKE ANY (…)`

**35 lignes remontées, dont seulement 28 exploitables.** C'est le résultat le plus instructif des
trois, et pas dans le sens attendu.

**Trois enseignements pour US-165 :**

1. ⚠️ **La requête du §7.1 est polluée et doit être corrigée.** Cinq lignes remontées sont des
   bulletins météo automatiques (`texte_original = '[AUTO-METEO]'`, commentaire du type
   « ☁️ Couvert · Min 12.8°C… ») enregistrés comme `observation`. Deux autres sont des remarques
   d'arrosage sans rapport avec un symptôme (« fuite détectée sur le goutte-à-goutte »). Toute
   alimentation de la table `symptome` doit **exclure `texte_original = '[AUTO-METEO]'`** — sans
   quoi le vocabulaire de pré-diagnostic se peuplerait de termes météorologiques.
2. ⚠️ **Le commentaire est préfixé par la saisie guidée, il n'est pas spontané.** US-038 impose des
   préfixes : `[Observation]`, `[Maladie / ravageur]`, `[Paillage]`, `[Arrosage (remarque)]`. Le
   commentaire est donc du texte **encadré**, pas les mots du jardinier. **La seule source de
   vocabulaire spontané est `texte_original`** — c'est elle que la table `symptome` doit exploiter,
   et c'est une correction à porter dans les notes techniques d'US-165.
3. 🔶 **Le vocabulaire réel est déjà technique, pas populaire.** Contre l'hypothèse de la conception
   (« tes mots, pas ceux d'un manuel »), les termes employés sont : *mildiou* (3), *oïdium* (3),
   *pucerons* (1), *ravageur* (8, dont 7 doublons de test), *jaunissement* (2), *taches* (3),
   *pourriture racinaire* (1), *levée irrégulière* (1), *sol détrempé* (1), *feuillage jauni* (1).
   Ce sont des noms de bioagresseurs, pas des descriptions de symptômes.

**Ce que ce troisième point change concrètement :**

- La table `symptome` ne peut pas être amorcée depuis l'historique : il n'y a **quasiment aucun
  symptôme décrit en langage courant** à en extraire. Elle est donc à **constituer par rédaction**,
  et sa colonne `synonymes` devient le cœur du travail, pas un complément.
- Le corpus des 30 questions de diagnostic (US-140 / CA11), qui doit être constitué **avant** toute
  rédaction, ne peut pas non plus être extrait de l'historique. Il est à écrire à la main, en
  formulant volontairement les questions en vocabulaire courant — c'est-à-dire en anticipant un
  usage que les données actuelles ne montrent pas encore.
- 🧪 Ce constat est à revérifier sur production avant d'y engager les 2 h prévues. Si le vocabulaire
  y est aussi technique, la cible de 80 % du CA11 est plus facile à atteindre qu'anticipé — et
  l'argument « enrichir le vocabulaire plutôt qu'activer le vectoriel » (US-140, arbitrage tranché)
  s'en trouve renforcé.

**Répartition des types d'action, pour mémoire :** récolte 55, semis 44, observation 33, plantation
33, mise en godet 32, paillage 10, arrosage 3, vendu 2, binage 2, tuteurage 2, perte 1, taille 1,
fertilisation 1, perte godet 1.

---

## 4. Rattachement du document de conception à US-140 / CA2

✅ **Fait.** US-140 / CA2 exige « la liste des sources retenues, la licence de chacune, ce qui est
réutilisable et à quelles conditions », produite et validée **avant** toute rédaction.

`CONCEPTION_REFERENTIEL_CONNAISSANCE_CULTURES.md` §6.1 est ce livrable, tel quel : douze sources
évaluées, licence et verdict pour chacune. Le présent document en fixe la conclusion (§2.1,
option A). CA2 est donc amendé pour **désigner ces deux documents comme son livrable**, et non pour
en demander la rédaction.

**Effet de bord :** le risque 🔴 « source du référentiel » de `EPIC_CALENDRIER_CULTURAL.md` §9 est
levé par le même livrable. À répercuter dans ce document lorsqu'US-068 sera reprise.

---

## 5. Ce que la vague 0 ne couvre pas — reste à faire avant la vague 1

| Action | Débloque | Statut |
|---|---|---|
| Constituer le corpus de 30 questions de diagnostic (US-140 / CA11), **à la main** — l'extraction [3] montre qu'il n'est pas extractible de l'historique | US-140 / CA11-CA12 | ✅ **fait** — `docs/CORPUS_QUESTIONS_DIAGNOSTIC_CA11.md`, 44 entrées dont 19 dans le périmètre v1 couvrant les 10 cultures (§6.1) |
| Rejouer les 3 extractions sur `potager_prod` et confirmer la liste nominative des dix cultures | US-140 / CA1 | ⬜ à faire |
| 🔶 Lire les conditions d'utilisation de `data.eppo.int` avant tout import de masse | US-162 | ⬜ à faire |
| Créer les 7 US de l'Épic 6 renumérotées (US-160 → US-167, US-160 et US-166 supprimées dans leur forme initiale) | Piste B de la vague 2 | ⬜ à faire |
| Marquer US-067 « amendée » et US-140 « recadrée » dans `BACKLOG_US_MULTITENANT.md` | Cohérence backlog | ⬜ à faire |
| Ajouter `ÉPIC 6 — Référentiel de connaissance des cultures` aux épics de `.github/agents/Personna PO.agent.md` | Rédaction des 7 US | ✅ fait sur cette branche |
| **Corriger `analyse_corpus_echecs.sql`** — la requête [SOURCE 2] échouait en l'état (§6.2) | US-092 (vague 1) | ✅ **fait** — `tools/analyse_corpus_echecs.sql`, corrigé et **exécuté avec succès sur `potager_dev`** (RC 0) |
| Établir un **référentiel d'unités canonique** — il n'en existe aucun dans le code, la liste de [SOURCE 6] est inventée (§6.2) | US-092 / qualité de parsing | ⬜ à faire |
| Rejouer `tools/analyse_corpus_echecs.sql` sur `potager_prod` | US-092 (calibrage de la cascade) | ✅ **fait le 25/08/2026** — résultats et enseignements au §8 |
| Démarrer **US-092, seule** | Vague 1 | ⬜ à faire, **après** la passe production du script |

---

## 6. Contrôle du 25/08/2026 — les deux livrables entrants

> Deux documents ont été produits hors de cette branche et soumis à vérification :
> `corpus-questions-potagistes-amateurs.md` et `analyse_corpus_echecs.sql`.
> Aucun des deux n'est encore enregistré dans le dépôt. Contrôle mené contre le code réel
> (`utils/actions.py`, `utils/validation.py`, `database/models.py`) et contre `potager_dev`.

### 6.1 🟡 Le corpus de questions — recevable, deux corrections avant usage

**Ce qu'il vaut.** Il exécute exactement la conclusion de l'extraction [3] du §3.3 : écrire à la
main, en vocabulaire courant, ce que l'historique ne contient pas. 40 entrées pour 30 exigées par
le CA11. Rédigé de zéro, donc **sans contrainte de licence** — cohérent avec l'arbitrage 1
(option A, §2.1) — et **sans aucun chiffre**, donc cohérent avec le garde-fou (a) de l'arbitrage 2.
Ses §3.3 (marqueurs d'incertitude) et §3.5 (moules syntaxiques) sont directement exploitables par
l'étage 0 de la cascade d'US-092.

**Ce qui doit être corrigé avant de s'en servir comme jeu de mesure :**

| Constat | Portée |
|---|---|
| 🔴 **`cornichon` et `ail` sont absents** du corpus, alors qu'ils figurent aux rangs 7 et 9 des dix cultures du §3.1 | Le CA11 ne mesurerait le rappel que sur 8 des 10 fiches de la v1 |
| 🟠 **18 des 28 cultures du corpus sont hors périmètre v1** (framboise, mâche, asperge, artichaut, céleri, navet, rhubarbe…) | Ces entrées n'ont aucune fiche à ramener. À **marquer explicitement « hors périmètre v1 »** : sinon la mesure du CA11 est mécaniquement plafonnée sous les 80 %, et l'US-140 serait déclarée en échec pour une raison de découpage, pas de qualité |
| 🟡 Pied de couverture faux : **11 mois, pas 12** (décembre absent) et **9 catégories, pas 7** (`levée`, `conservation` et `conduite` non comptées) | Cosmétique, mais le document sert de référence de mesure |
| 🟡 Le §3.3 liste `jamais été sûr` et `ça a passé tout seul` comme marqueurs, que la regex de [SOURCE 4] du script ne couvre pas | Incohérence entre les deux livrables, à aligner |
| 🟡 Encodage cassé (UTF-8 lu en latin-1) | À réencoder à l'enregistrement dans le dépôt |

**Vérifié :** 28 cultures ✅ · 40 entrées ✅ · 3 cas non résolus ✅ · les 28 cultures du corpus
existent toutes dans `culture_config` (54 lignes) ✅ — aucune n'aurait à être créée.

### 6.2 🔴 Le script d'extraction des échecs — une erreur bloquante, trois écarts au réel

Le script est bien cadré (lecture seule, hors `migrations/`, volumétrie en premier). Mais il a été
écrit contre un schéma qui n'existe plus, et contre des référentiels qui n'existent pas.

| # | Constat, vérifié en base | Correction |
|---:|---|---|
| 1 | 🔴 **[SOURCE 2] sélectionne `parcelle`** — colonne supprimée par `migration_v12`. Vérifié : `information_schema` ne connaît plus cette colonne. La requête échoue avec `column "parcelle" does not exist` | Remplacer par `parcelle_id`, ou joindre `parcelles` pour retrouver un libellé |
| 2 | 🟠 **Aucun filtre `potager_id`**, alors que la colonne existe et que dev porte déjà **2 potagers** (205 / 15 événements). L'en-tête affirme « RLS active » : c'est faux — `relrowsecurity = false` sur `evenements` comme sur `culture_config` | Les agrégats [SOURCE 5] et [SOURCE 6] mélangent les locataires sans le dire. Ajouter le filtre explicitement, ne pas compter sur la RLS |
| 3 | 🟠 **[SOURCE 6] teste une liste d'unités inventée.** Réel en dev : `plants` (43), `graines` (41), `g` (35), `kg` (6), `m²` (4), `pièces` (3), `m2` (1), `bulbes`, `gousses`, `sets`, `têtes`. La liste du script signalerait 6 de ces 11 valeurs comme hallucinations — et **raterait la seule vraie anomalie : `m2` et `m²` coexistent** | Il n'existe **aucun référentiel d'unités canonique dans le code** (seul `_normalize_unite_semis` cadre le cas des semis). Ce référentiel est à établir *avant* de pouvoir mesurer un écart |
| 4 | 🟡 **[SOURCE 2] rate le motif d'échec réellement présent.** `type_action IS NULL` : **0 ligne**. En revanche `binage` (2 occurrences) n'existe ni dans `ACTION_MAP` ni dans `ACTIONS_VALIDES` | Ajouter un motif `type_action hors référentiel canonique`. ⚠️ Au passage : `utils/actions.ACTION_MAP` et `utils/validation.ACTIONS_VALIDES` **divergent** (`amendement`/`protection` d'un côté, `fertilisation`/`repiquage` de l'autre) — à trancher avant d'écrire la règle |
| 5 | 🟡 **[SOURCE 1-bis] sous-compte.** Format réel de la trace (`bot.py:5191`) : ` \| [CORR AAAA-MM-JJ] culture: x → y, quantité: 2 → 3`. Le `split_part(…, ':', 1)` ne retient que le **premier** champ d'une correction multi-champs, et les libellés sont accentués et localisés (`variété`, `quantité`, `durée`) | Découper d'abord sur `, ` puis sur `:` |
| 6 | 🟡 **La « source la plus riche » est quasi vide : 3 lignes `[CORR]` en dev** | À confirmer sur production avant de fonder le moindre travail de prompt engineering statistique dessus. Si la production est du même ordre, ce corpus est un recueil de cas, pas une mesure |
| 7 | 🟡 **[SOURCE 4] teste `_signal_intent()`, qui n'existe pas encore** dans le code — c'est la règle prévue par l'architecture cible V2, à écrire dans US-092 | Ce n'est pas une vérification mais un **pré-test de faisabilité**. À reformuler comme tel : « quelle serait la fausse-positivité de la règle si on l'écrivait ainsi » |

**Ce qui est confirmé au passage :** la pollution `[AUTO-METEO]` relevée au §3.3 reste à exclure
explicitement de [SOURCE 2] et [SOURCE 5], et le script mérite d'être rangé dans `tools/`, jamais
dans `migrations/` — sur ce dernier point, son en-tête est déjà juste.

---

## 7. Suites données le 25/08/2026

Les deux livrables du §6 ont été corrigés et versés au dépôt le soir même.

### 7.1 `docs/CORPUS_QUESTIONS_DIAGNOSTIC_CA11.md` — corpus du CA11, recevable

- **`cornichon` et `ail` ajoutés** (entrées 41 à 44) : les **dix cultures du §3.1 sont désormais
  couvertes sans exception**. 44 entrées au total, dont **19 dans le périmètre v1**.
- Une **colonne `v1`** distingue explicitement l'assiette de rappel du CA11 des 25 entrées hors
  périmètre. Ces dernières ne sont pas jetées : elles deviennent le **test d'honnêteté** de la
  cascade — le comportement attendu y est « je n'ai pas de fiche sur cette culture », jamais une
  fiche voisine forcée. Sans cette séparation, la mesure du CA11 était plafonnée sous les 80 % par
  construction.
- Pied de couverture recompté et rectifié : **30 cultures, 12 mois** (décembre couvert par l'entrée
  43), **9 catégories** — au lieu des « 28 cultures · 12 mois · 7 catégories » annoncés à tort.
- Marqueurs d'incertitude du §3.3 **alignés avec la regex de [SOURCE 4]** du script, dans les deux
  sens, avec la consigne de maintenance écrite dans les deux fichiers.
- Ajout volontaire d'un **cas de désambiguïsation** : la rouille du poireau (#38, hors périmètre) et
  celle de l'ail (#44, dans le périmètre) partagent le même symptôme décrit.

### 7.2 `tools/analyse_corpus_echecs.sql` — corrigé, exécuté, vérifié

Rangé dans `tools/`, jamais dans `migrations/`. **Exécuté avec succès sur `potager_dev`** (`RC 0`),
en mode mono-potager (`-v potager=1`) comme en mode global (`-v potager=-1`).

| Correction | Vérification |
|---|---|
| `parcelle` → `parcelle_id` + jointure `parcelles` | [SOURCE 2] s'exécute et restitue `parcelle_nom` |
| Filtre `potager_id` explicite, avec avertissement si absent | 205 événements sur potager 1, 220 en global — l'écart est désormais visible |
| Motif « `type_action` hors référentiel » ajouté | **2 lignes remontées** (`binage`, ids 2040 et 2080) là où `type_action IS NULL` en remontait **zéro** |
| Découpage des traces `[CORR]` multi-champs | La trace unique de dev porte bien **deux** champs (`quantité`, `unité`), désormais comptés tous les deux |
| [SOURCE 6] : whitelist inventée → distribution + variantes normalisées | La seule vraie anomalie ressort enfin : **`m²` (4) et `m2` (1)**. La translittération des exposants (`²`→`2`) a dû être ajoutée, sans quoi `m²` se normalisait en `m` et ne rejoignait jamais `m2` |
| Exclusion de `'[AUTO-METEO]'` | 5 bulletins isolés et comptés à part dans la volumétrie |
| [SOURCE 4] requalifiée en **pré-test** de `_signal_intent()` | La fonction n'existe pas encore ; 0 faux positif sur les données de dev |

**Deux constats à porter dans US-092 :**

1. ⚠️ **Les deux référentiels d'actions du code divergent.** `utils/actions.ACTION_MAP` connaît
   `amendement` et `protection` ; `utils/validation.ACTIONS_VALIDES` connaît `fertilisation` et
   `repiquage`. Le script utilise leur union faute de mieux. À trancher **avant** d'en faire une
   règle de validation — c'est cette divergence qui laisse passer `binage`.
2. 🔴 **Aucun référentiel d'unités n'existe dans le code** — seul `unite_semis_ancree_dans_texte`
   cadre le cas des semis. Tant qu'il n'est pas établi, aucune mesure d'« unité hallucinée » n'a de
   sens : c'est un préalable, pas un sous-produit de l'analyse.

---

## 8. Passe production du 25/08/2026 — ce que les données réelles disent

`tools/analyse_corpus_echecs.sql` exécuté sur `potager_prod`, mode global (`-v potager=-1`).
**321 événements, dont 96 bulletins `[AUTO-METEO]`** — soit **225 saisies réelles**.

> ⚠️ **Le §6.2 point 6 est démenti par la production.** J'avais conclu de la base de dev
> (3 traces `[CORR]`) que la SOURCE 1 était « un recueil de cas, pas une mesure ». La production
> en porte **35, soit un taux de correction de 15,6 % des saisies réelles**. C'est une base
> pleinement exploitable, et c'est le gisement le plus utile des six sources.

### 8.1 🔴 Le champ le plus fauté est la **date** — et la cause n'est pas le LLM

| Champ corrigé | Corrections | Part |
|---|---:|---:|
| **date** | **11** | **27,5 %** |
| parcelle | 8 | 20 % |
| quantité | 8 | 20 % |
| variété | 6 | 15 % |
| unité | 5 | 12,5 % |
| commentaire | 2 | 5 % |

**Le motif est unidirectionnel : sur 12 corrections de date, 11 ramènent la date en arrière.**
En lisant les phrases dictées, la cause est nette — et ce n'est pas une hallucination de parsing :

| Phrase dictée | Date posée | Date vraie | Écart |
|---|---|---|---:|
| « plantation de 2 courges » | 18/06 | 10/06 | −8 j |
| « plantation 10 courge » | 08/06 | 25/05 | −14 j |
| « Vente 1 courgette » | 17/06 | 23/05 | −25 j |
| « Plantation 3 pied de tomate noire de Crimée » | 17/06 | 12/06 | −5 j |
| « Plantation de 50 oignons rouges carré Est. » | 27/03 | 06/03 | −21 j |

**Aucune de ces phrases ne contient de date.** Le système retombe silencieusement sur *aujourd'hui*,
c'est-à-dire sur la date de **saisie** — alors que le jardinier saisit a posteriori, souvent
plusieurs semaines après le geste. Un cas distinct le confirme par l'autre bout : « Plantation de
20 plants de salades […] **la semaine dernière** » a été daté du jour même (28/03 au lieu du 21/03) —
l'ancrage relatif n'a pas été résolu et est, lui aussi, retombé sur aujourd'hui.

**Ce que ça implique pour US-092 :**

- Le fallback muet « aujourd'hui » est **la première cause de correction de toute l'application**.
  Ce n'est pas un problème de prompt : c'est un défaut de conception, corrigeable **sans le moindre
  appel LLM**.
- Il contredit frontalement le principe d'honnêteté de l'Épic 5 §4 — *l'application n'invente jamais
  une date*. Elle en invente une à chaque saisie sans ancrage temporel, et se trompe alors dans une
  large majorité des cas.
- Correctif à cadrer : quand aucun ancrage temporel n'est détecté, **demander plutôt que présumer**,
  ou au minimum signaler la date présumée. À rattacher à US-092, en amont de la cascade.
- 🔗 Le §3.4 du corpus CA11 (ancrages relatifs, phénologiques, météorologiques) cesse d'être un point
  d'attention théorique : c'est le premier poste de défaut mesuré.

### 8.2 ✅ Le discriminant d'incertitude : **zéro faux positif sur 225 saisies**

[SOURCE 4] ne remonte **aucune ligne** en production. Les marqueurs `je pense`, `je crois`,
`paraît-il`, `on m'a dit`, `jamais su`… sont **totalement absents des saisies d'action réelles**.

L'hypothèse du §3.3 du corpus CA11 est donc **validée sur données réelles** : c'est un discriminant
`INTERROGER` / `ACTION` à coût nul, sans appel LLM, et sans risque de faux positif mesurable.
Candidat confirmé pour l'étage 1 de la cascade d'US-092.

### 8.3 ⚠️ Deux gestes de jardinage manquent au référentiel d'actions

[SOURCE 2] remonte 4 lignes, dont deux qui ne sont **pas** des hallucinations :

| id | Texte dicté | `type_action` | Verdict |
|---:|---|---|---|
| 86 | « Binage effectué sur les ranges d'oignons il y a 4 jours » | `binage` | geste réel, **absent du référentiel** |
| 68 | « hier j'ai éclairci mon semis de radis » | `eclaircie` | geste réel, **absent du référentiel** |
| 31 | « 10 pieds de fenouil » | *absent* | phrase sans verbe — vrai échec de parsing |
| 10 | « Y a t il des radis dans mon jardin » | *absent* | **question enregistrée comme événement** |

`binage` et `eclaircissage` sont à ajouter à `utils/actions.ACTION_MAP` — le référentiel de
12 actions ne couvre pas le geste réel. À traiter **avec** l'arbitrage de la divergence
`ACTION_MAP` / `ACTIONS_VALIDES` déjà relevée au §7.2.

### 8.4 🔴 La ligne 10 : le cas d'école du faux négatif `INTERROGER`

« Y a t il des radis dans mon jardin » a été **enregistré comme un événement**, avec
`culture = 'radi'` — seule valeur de culture de toute la production **inconnue de
`culture_config`** ([SOURCE 5]). Une question a donc produit une écriture en base *et* une culture
fantôme. C'est exactement le scénario que la cascade d'US-092 doit rendre impossible.

**Et ma propre requête ne l'a pas trouvé.** [SOURCE 3] a remonté 4 lignes, **toutes fausses** :
`comment` matchait `commentaire`, mot présent dans les traces `[CORR]`. La vraie question, elle,
échappait à la regex — **ni point d'interrogation, ni marqueur de la liste**.

> 🔑 **Enseignement de méthode, valable bien au-delà de ce script :** à la dictée vocale, le point
> d'interrogation n'existe pas. Toute détection de question qui s'appuie sur `?` est structurellement
> aveugle sur le canal principal de l'application. Ce sont les **tournures** (« y a-t-il »,
> « est-ce que », « dis-moi ») qu'il faut reconnaître, pas la ponctuation.

Le script est corrigé des deux défauts (bornes de mot `\m…\M` + tournures orales) et revalidé.

### 8.5 🔶 Unités : le pluriel n'est pas normalisé

Six unités seulement en production — `plants` (88), `g` (43), `graines` (22), `kg` (15),
**`pieds` (4)** et **`pied` (3)**. Les deux dernières sont la même unité, non regroupée : la
détection de variantes a dû être complétée d'une dépluralisation simple, la version précédente ne
traitant que les exposants typographiques.

À noter pour l'établissement du référentiel d'unités (§7.2, point 2) : `plants` et `pied(s)`
comptent la même chose de deux façons — le référentiel devra trancher, pas juste lister.

### 8.6 Ce qui reste sain

- **0 ligne à `texte_original` NULL ou vide** — aucune saisie muette.
- **0 date aberrante, 0 quantité négative, 0 date future.** Les garde-fous d'US-049 tiennent.
- Les 7 autres cultures rares de [SOURCE 5] (estragon, framboise, menthe, rhubarbe, ciboulette,
  fraise, thym) sont toutes **connues de `culture_config`** : ce sont des vivaces et aromatiques
  légitimement peu mouvementées, pas des hallucinations.
- **96 bulletins `[AUTO-METEO]` sur 321 événements (30 %)** : l'exclusion imposée au §3.3 n'était pas
  une précaution de confort. Sans elle, près d'un tiers du corpus analysé serait du bruit machine.


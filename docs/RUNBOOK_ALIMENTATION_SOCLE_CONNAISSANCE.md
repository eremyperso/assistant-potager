# RUNBOOK — Alimenter le socle de connaissance (étage 2)

> **Statut :** procédure d'exploitation et guide de rédaction.
> **Date de rédaction :** 2026-09-03 — version applicative `v3.52.0`.
> **Périmètre :** US-098 livre le contenant (tables, recherche, ingestion,
> mesure). Ce document explique comment le **remplir** : d'où vient le contenu,
> comment l'écrire pour qu'il soit retrouvable, comment le mesurer, et dans
> quel ordre le déployer en production sans exposer une base non étalonnée.
> **Public :** la personne qui écrit les fiches et celle qui les déploie —
> souvent la même. Aucune connaissance préalable des RAG n'est supposée.

---

## 1. Le modèle mental — cinq phrases à ne pas perdre de vue

Un « RAG » (*retrieval-augmented generation*) est, dans sa version la plus
utile, très banal : **on cherche des passages écrits par des humains, et on les
donne**. Tout le reste est de la plomberie. Celui-ci en particulier :

1. **La base est l'index, le dépôt est la source.** Les fiches vivent dans
   `data/connaissance/*.md`, versionnées et relues comme du code. Les tables
   `knowledge_documents` / `knowledge_chunks` n'en sont qu'une projection,
   reconstruite à volonté. **On n'édite jamais une fiche en base.**

2. **L'unité de réponse est le fragment, pas le document.** Une fiche est
   découpée à chaque titre de niveau 2 (`## `). C'est un fragment, et un seul,
   qui sera servi au jardinier. Écrire pour le document plutôt que pour le
   fragment est l'erreur numéro un.

3. **La recherche est LEXICALE, pas sémantique.** PostgreSQL compare des mots
   (lemmatisés en français), il ne comprend pas les synonymes. Si le jardinier
   dit « cul noir » et que la fiche ne parle que de « nécrose apicale », rien
   ne sort. Ce point commande toute la façon d'écrire — voir §3.

4. **Le RAG ne rédige jamais.** Il retourne des passages, leurs sources et un
   score. Quand la confiance est élevée, le passage est recopié **mot pour
   mot**, à zéro jeton. Sinon il descend en contexte vers l'étage de
   raisonnement, qui reste seul à rédiger.

5. **Ce que la base ne sait pas répondre est l'information la plus précieuse.**
   `GET /admin/savoir/lacunes` liste les questions réellement posées et non
   servies. C'est cette liste, et non l'intuition, qui dit quoi écrire ensuite.

---

## 2. D'où vient le contenu — et ce qu'on n'a pas le droit d'y mettre

Trois familles, trois provenances très différentes. La colonne `famille` de
l'en-tête les distingue.

| Famille | US | Qui écrit | Difficulté réelle |
|---|---|---|---|
| `doc_app` | US-099 | toi | aucune — ce sont des faits sur ta propre application |
| `agronomie` | US-140 | toi, sous contrainte de licence | c'est ici que tout se joue |
| `memoire_potager` | US-141 | généré depuis les événements du potager | privé, jamais partagé |

### 2.1 `doc_app` — commence par là

C'est le corpus le plus facile et le plus rentable : tu connais les réponses,
elles ne périment que quand tu changes le code, et elles évitent des appels de
modèle sur des questions auxquelles un modèle répond mal (il ne connaît pas ton
application). « Comment corriger un événement mal compris ? », « est-ce que je
perds l'historique si je renomme une parcelle ? », « pourquoi mon stock de
tomate ne baisse pas quand je récolte ? ».

Source de vérité : le code, `PATCH_NOTES.md`, et les fichiers du backlog.
Niveau de confiance : `verifie` — tu peux l'affirmer.

### 2.2 `agronomie` — la contrainte de licence est bloquante, pas décorative

L'arbitrage de la vague 0 (option A,
`docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md` §2.1) limite le socle à :

- **CC0** — Wikidata ;
- **Licence Ouverte / Etalab** — E-Phy / ANSES ;
- **CC BY 4.0** — après curation humaine, avec attribution affichée (amendement
  du 02/09/2026, cf. Wind River Greens en US-161/US-163) ;
- **la rédaction interne** — ce que tu écris toi-même.

Sont **exclus de tout import** : Wikipédia FR, Permapeople, Plants For A
Future, Practical Plants, Growstuff. Ce ne sont pas des préférences : ces
sources sont en CC-BY-SA, dont la clause de partage à l'identique
contaminerait le corpus et fermerait la trajectoire commerciale.

> **Recopier un paragraphe de Wikipédia dans une fiche est le seul geste de ce
> runbook qui soit irréversible.** Une fois le corpus contaminé, il faut le
> reconstituer, pas le corriger.

### 2.3 Peut-on faire rédiger les fiches par un modèle de langage ?

Question légitime, réponse nuancée :

- **`doc_app` : oui, comme brouillon.** Tu vérifies chaque phrase contre ton
  propre code, donc l'erreur ne survit pas. Le gain de temps est réel.
- **`agronomie` : le brouillon oui, les chiffres non.** Le projet a déjà tranché
  ce point en US-161/CA10 : *aucun chiffre agronomique n'est produit par un
  modèle de langage*. Profondeur de semis, délai de retour, température de
  germination, dose de dilution — ces valeurs viennent d'une source citable ou
  ne figurent pas dans la fiche.
- **Dans tous les cas : une fiche non relue par un humain est `indicatif`, pas
  `verifie`.** Ce n'est pas une formalité : une fiche `verifie` peut être
  servie mot pour mot au jardinier sans qu'aucun modèle ne la nuance. Une fiche
  `indicatif` ne l'est jamais — elle descend en contexte. Le niveau de confiance
  est donc un **engagement de l'application**, pas une étiquette de politesse.

En cas de doute, écris `indicatif`. Le coût d'une fiche prudente est un appel de
modèle ; le coût d'une fiche fausse servie comme certaine est la confiance du
jardinier.

---

## 3. Écrire une fiche que la recherche saura retrouver

### 3.1 Le format

Une fiche couvre **un couple culture × thème** — `tomate-problemes.md`,
`carotte-recolte-conservation.md`. Pas une culture entière : un fichier par
couple fait que le titre du document *discrimine* au lieu de diluer. Une fiche
« tomate » unique sort en tête sur n'importe quelle question contenant le mot
« tomate », quelle que soit la section.

```markdown
---
titre: "Problèmes observables de tomate"
famille: "agronomie"                # agronomie | doc_app | memoire_potager
source: "Rédaction interne"         # ce qui s'affiche « _Source : …_ » au jardinier
niveau_confiance: "a-valider"       # verifie | indicatif | a-valider
culture: "tomate"                   # facultatif — DOIT exister dans culture_config
type: "maladie"                     # facultatif — maladie, semis, rotation, arrosage…
saison: "ete"                       # facultatif
potager_id: 3                       # facultatif — savoir PRIVÉ d'un potager (US-141)
theme: "problemes"                  # facultatif — repère éditorial, non indexé
version: "2.0"                      # facultatif — repère éditorial, non indexé
index_terms:                        # index de RELECTURE — non indexé (voir ⑦)
  - "cul noir"
sources:                            # organismes consultés — non indexé
  - organisme: "USDA National Agricultural Library"
    licence: "Domaine public"
---

# Problèmes observables de tomate          ← ignoré : recopie `titre:`

## Mes tomates ont le cul noir ou pourrissent par dessous

**Intention :** diagnostic                 ← retiré du texte servi, NON indexé
**Organes concernés :** fruit              ← retiré du texte servi, INDEXÉ
**On parle aussi de :** cul noir tomate ; tomate pourrie dessous ; nécrose apicale ; manque de calcium

Une zone brune puis noire, sèche et légèrement creusée sous le fruit vient
d'une alimentation en eau irrégulière pendant la croissance…

## Sources et licence                      ← section ignorée : pied de fiche

- U.S. Department of Agriculture, National Agricultural Library…
```

**Ce que l'outil retire avant d'indexer**, sans que rien ne disparaisse du
fichier — le dépôt reste lisible par un relecteur humain :

| Dans le `.md` | En base | Pourquoi |
|---|---|---|
| `# H1` de tête | ignoré | Recopie `titre:`. Indexé, il sortait en tête à 1.000 de confiance sur le seul nom de la culture, sans rien répondre. |
| `## Sources et licence` | ignoré | Identique d'une fiche à l'autre. Indexé, il remontait à 0.919 sur toute question portant « source » ou « licence ». |
| `**On parle aussi de :**` | **indexé au poids du titre**, retiré du texte | C'est le rôle d'un alias : peser comme un titre, ne jamais s'afficher. |
| `**Organes concernés :**` | **indexé au poids du titre**, retiré du texte | Le jardinier tape « mes feuilles », « le fruit ». |
| `**Intention :**` | retiré du texte, non indexé | Personne ne tape « diagnostic ». |
| `index_terms:`, `sources:` | non lus | Voir règle ⑦. |
| une clé inconnue (`**Attention :**`) | **conservée dans le texte** | On ne retire que ce qu'on sait nommer. |

`culture` est résolue en **référence** vers `culture_config`, jamais stockée en
texte : c'est ce qui fait qu'un renommage de culture depuis le bot n'orpheline
aucun fragment. Un libellé absent du référentiel fait **refuser** la fiche —
c'est voulu, un rattachement silencieusement perdu serait pire.

`niveau_confiance: a-valider` est l'état normal d'une fiche pas encore relue
phrase par phrase. Il se comporte comme `indicatif` : le passage descend en
contexte vers l'étage de raisonnement au lieu d'être servi mot pour mot.
Promotion en `verifie` fiche par fiche, au fil des relectures — c'est un
engagement, pas une case à cocher.

### 3.2 Les sept règles qui décident si une fiche sera trouvée

**① Le titre de section est la question déguisée.** Le titre du document et
l'intitulé de section sont indexés avec un poids supérieur au corps (`setweight`
'A' contre 'B'). « Comment corriger le cul noir en cours de saison » est un bon
titre ; « Traitement » n'en est pas un.

**② Les deux registres dans « On parle aussi de », systématiquement.** La
recherche est **lexicale** : un lemme absent de l'index est un rapprochement
impossible, quelle que soit la qualité du texte. La ligne doit porter celui du
jardinier (`cul noir`, `poudre blanche`, `des taches marron qui remontent`)
**et** celui de l'agronome (`nécrose apicale`, `oïdium`, `mildiou`). Les deux,
pas au choix : la §3.1 de `docs/CORPUS_QUESTIONS_DIAGNOSTIC_CA11.md` mesure que
le vocabulaire réel en production est déjà largement technique, et sa §3.2
donne la table de correspondance.

C'est la règle qui pèse le plus lourd. Sur 24 fiches et 19 questions réelles,
la même mécanique de recherche passe de **3/12** (fiches en langue clinique
neutre, sans jamais nommer les choses) à **17/19 en tête** avec ces alias.
Aucun changement de code entre les deux mesures : seulement la rédaction.

**③ Un fragment, une idée, autonome.** Un fragment servi tel quel doit se
suffire. « Il faut alors pailler le pied » ne veut rien dire hors contexte.
L'outil signale ces cas (ouverture par un pronom de reprise, fragment de moins
de 80 caractères) et `--strict` les refuse.

**④ Ni trop court, ni trop long.** En dessous de ~80 caractères, ce n'est pas
une réponse. Au-delà de ~1 200, le passage servi devient un mur de texte sur
Telegram — coupe en deux sections.

**⑤ Répète le sujet dans chaque section.** Ne compte pas sur le titre du
document pour porter le sens : dis « la tomate » dans la section, même si la
fiche s'appelle déjà « La tomate ». Ça sert la lisibilité **et** le classement.

**⑥ Pas de Markdown décoratif.** Le passage part tel quel dans un message
Telegram : `*`, `_`, `[` non échappés peuvent casser le rendu. Prose simple,
pas de tableaux, pas de listes à puces complexes.

**⑦ Les alias vont dans la SECTION, pas dans l'en-tête.** `index_terms:` au
niveau du document est un index de relecture utile, et il n'est **pas** indexé.
La raison est mesurée, pas de principe : il pèse identiquement sur toutes les
sections de la fiche, donc il dilue exactement ce que les alias de section
discriminent — **17/19 en tête sans lui, 15/19 avec**, sur le même corpus.
Un terme qui compte doit se trouver dans le « On parle aussi de » de la section
qui y répond.

### 3.3 Ce qu'une fiche ne contient jamais

- **Ni association de cultures, ni règle de rotation.** Ce sont des arêtes,
  portées par `association_culture` et le calcul de rotation (US-163). Écrites
  dans une fiche, elles deviennent une seconde vérité invisible du calcul.
  Une fiche peut en revanche **expliquer** le mécanisme.
- **Ni date, ni fenêtre de calendrier** — c'est le référentiel calendrier
  (US-068).
- **Aucune donnée d'un potager dans une fiche globale.** Une fiche sans
  `potager_id` est partagée par tous les jardins.

---

## 4. Le CSV de mesure — faut-il en générer un ?

**Oui, un par corpus que tu veux mesurer.** Sans vérité terrain, « la recherche
fonctionne » n'est pas vérifiable : on ne peut mesurer un classement que si l'on
sait à l'avance ce qui devrait sortir en tête.

Format : une ligne par question, le fragment attendu écrit relativement à la
racine du corpus.

```csv
question,fragment_attendu
pourquoi mes tomates ont le cul noir ?,agronomie/tomate-cul-noir.md#00-ce-qu-est-le-cul-noir-de-la-tomate
```

La référence d'un fragment se compose de `<chemin de la fiche>#<NN>-<titre de
section en kebab-case>`, `NN` étant son rang dans la fiche à partir de `00`
(le préambule, s'il existe, prend `00`). Le plus simple est de **ne pas les
écrire à la main** : ingère d'abord, puis lis-les.

```powershell
psql -U potager_user -d potager_dev -h localhost `
  -c "SELECT reference FROM knowledge_chunks ORDER BY reference;"
```

### 4.1 Le problème d'amorçage, et comment en sortir

Au début, tu n'as aucune question réelle : aucun trafic n'a encore traversé
l'étage. Tu écris donc 30 questions plausibles — c'est ce que fait
`tests/corpus/us098_questions_savoir.csv` pour les fixtures. **C'est un pis-aller
assumé.** US-094 a montré sur le parseur que des phrases imaginées produisent
une couverture flatteuse et fausse.

Dès que le bot a tourné quelques semaines, remplace-les par de vraies questions :

```sql
-- Les questions de savoir réellement posées, et ce que l'étage en a fait.
SELECT question_normalisee, issue_savoir, COUNT(*) AS nb
FROM routage_logs
WHERE issue_savoir IS NOT NULL
GROUP BY question_normalisee, issue_savoir
ORDER BY nb DESC
LIMIT 100;
```

Les lignes `vide` disent quelles fiches **écrire**. Les lignes `transmis` disent
quelles fiches **relire** : le sujet est couvert, mais mal retrouvé — c'est
presque toujours un problème de vocabulaire (règle ② ci-dessus), pas de contenu.

### 4.2 Ce que le CSV ne mesure pas

Le classement, uniquement. Qu'un fragment bien classé **réponde correctement**
relève de la relecture éditoriale, pas d'une métrique. Un corpus qui affiche
100 % de top-3 peut être agronomiquement faux de bout en bout.

---

## 5. Mise en production — l'ordre compte

> **Le point critique :** `RAG_SEUIL_CONFIANCE` vaut `0.6` par défaut, valeur
> étalonnée sur le repli SQLite des tests (une couverture de termes).
> PostgreSQL classe avec `ts_rank_cd` normalisé, qui **ne produit pas les mêmes
> nombres**. Ingérer un corpus en production sans réétalonner, c'est ouvrir
> l'étage avec un seuil arbitraire : soit il ne sert jamais rien, soit il sert
> des passages mal classés comme s'ils étaient sûrs.
>
> D'où l'ordre ci-dessous : **on coupe l'étage, on ingère, on mesure, on règle,
> on rouvre.** C'est exactement ce à quoi sert l'interrupteur `RAG_ACTIF`.

### Étape 0 — Prérequis

```bash
# La migration s'applique avec le rôle PROPRIÉTAIRE de la base, jamais app_user :
# une fiche GLOBALE (potager_id NULL) est refusée par le WITH CHECK de la policy
# RLS sous le rôle applicatif. Même règle que tools/importer_referentiel.py.
psql -U potager_user -d potager -f migrations/migration_v42.sql
```

Dans le rapport de fin de migration, trois lignes sont **bloquantes** :

- `SELECT cfgname FROM pg_ts_config WHERE cfgname = 'french_sans_accent'` doit
  renvoyer une ligne — c'est la configuration que le code nomme, à l'écriture du
  vecteur **comme** à l'interrogation. Si elle manque, le socle échoue en base.
- `to_tsvector('french_sans_accent', 'récolter recolter')` doit rendre
  **`'recolt':1,2`** — un seul lexème à deux positions. S'il en rend deux
  (`'recolt':2 'récolt':1`), le mapping `unaccent` n'a pas été appliqué, et un
  jardinier qui tape sans accent — la norme sur mobile — manquera tous les
  termes accentués du corpus : récolter, éclaircir, flétrir, arroser, oïdium.
- `idx_knowledge_chunks_fts` doit exister, sinon la recherche dégénère en
  balayage complet dès que le corpus grossit.

> **Si tu réappliques cette migration sur une base qui contient déjà du corpus**, la
> réingestion de l'étape 3 ne suffit pas : l'empreinte SHA-256 des fichiers n'a
> pas changé, l'outil dirait « inchangé » et ne réécrirait aucun vecteur. Vider
> l'index d'abord (`DELETE FROM knowledge_chunks; DELETE FROM
> knowledge_documents;`), puis réingérer. Sans perte — le dépôt est la source.

Vérifie aussi que les cultures citées par tes fiches existent :

```sql
SELECT nom FROM culture_config WHERE lower(nom) IN ('tomate','courgette', ...);
```

### Étape 1 — Couper l'étage

Dans `.env.prod` :

```
RAG_ACTIF=0
```

puis redémarrer `potager-prod-bot` et `potager-prod`. Le comportement de la
cascade redevient strictement celui d'avant US-098.

### Étape 2 — Contrôler le corpus à blanc

```bash
python tools/ingerer_connaissance.py --dry-run
python tools/ingerer_connaissance.py --strict --dry-run   # refuse les fragments non autonomes
```

Aucune erreur, aucun avertissement de découpage : on ne passe pas à l'étape
suivante tant que le rapport n'est pas propre.

### Étape 3 — Ingérer

```bash
python tools/ingerer_connaissance.py
python tools/ingerer_connaissance.py   # 2e passage : doit afficher « N inchangé(s) », 0 fragment écrit
```

Le second passage est le contrôle d'idempotence. S'il réécrit quelque chose,
c'est un bug — ne poursuis pas.

### Étape 4 — Mesurer et régler le seuil

```bash
python tools/mesurer_corpus_savoir.py --corpus <ton_csv> --racine data/connaissance --detail
```

Le rapport doit dire `Moteur : postgresql`. S'il dit `sqlite`, ton
`DATABASE_URL` ne pointe pas la production et la mesure ne vaut rien — le script
te le signale de lui-même.

Lis la colonne `score=` du détail. Choisis un seuil qui sépare nettement les
questions classées en rang 1 des questions hors cible, puis dans `.env.prod` :

```
RAG_SEUIL_CONFIANCE=<ta valeur>
```

Critères de décision (les mêmes que ceux codés dans l'outil) :

| Indicateur | Cible | Si hors cible |
|---|---|---|
| bon fragment dans le top 3 | ≥ 80 % | ne pas activer — relire les fiches hors cible (règle ②) |
| latence p95 | < 150 ms | vérifier que l'index GIN existe et est utilisé (`EXPLAIN`) |

### Étape 5 — Rouvrir l'étage

```
RAG_ACTIF=1
```

Redémarrer les deux services.

### Étape 6 — Vérifier en conditions réelles

Pose au bot trois questions couvertes par le corpus. Une réponse servie par
l'étage 2 se reconnaît à deux signes : le texte est **identique** au fichier
`.md`, et il se termine par une ligne `Source : …`.

```sql
SELECT question_normalisee, etage_resolveur, issue_savoir,
       round(score_savoir::numeric, 3) AS score, tokens_consommes, latence_ms
FROM routage_logs
ORDER BY id DESC LIMIT 10;
```

Une ligne servie par l'étage du savoir porte `etage_resolveur = 'savoir'`,
`issue_savoir = 'servi'` et **`tokens_consommes = 0`**. C'est cette dernière
colonne qui prouve le coût nul ; le reste n'en est que l'indice.

---

## 6. Corriger une fiche déjà en production

```bash
# 1. Modifier le .md dans le dépôt, le commiter, le déployer
# 2. Réingérer
python tools/ingerer_connaissance.py
```

L'empreinte SHA-256 du fichier a changé : l'outil remplace **tous** les
fragments de cette fiche et invalide **toutes** les réponses mémorisées qui en
dérivaient (`questions_cache`), y compris celles dont la section n'a pas été
renommée — c'est justement la correction la plus fréquente. Le rapport indique
le nombre de réponses invalidées.

Pour une fiche **supprimée** du dépôt, l'élagage n'est pas automatique :

```bash
python tools/ingerer_connaissance.py --elaguer
```

---

## 7. Les pièges, par ordre de fréquence

**① Une réponse mémorisée court-circuite l'étage du savoir.** Si une question a
été posée **avant** l'ingestion, sa réponse LLM est en cache pour 90 jours et
sera servie par l'étage 0bis, sans jamais atteindre l'étage 2. Symptôme :
`etage_resolveur = 'cache'` dans `routage_logs`. Remède :

```sql
DELETE FROM questions_cache WHERE type_reponse = 'figee';
```

**② Ingérer avec le mauvais rôle PostgreSQL.** Sous `app_user`, la policy RLS
refuse toute fiche globale. Ingérer avec le rôle propriétaire.

**③ Le seuil non réétalonné** — §5, c'est le sujet de tout ce chapitre.

**④ Une culture absente de `culture_config`** fait refuser la fiche. C'est
délibéré : la culture est une référence, pas un libellé.

**⑤ Croire qu'un score élevé signifie une bonne réponse.** Il signifie une
bonne correspondance *lexicale*. Seule la relecture humaine dit si le contenu
est juste.

**⑥ Éditer une fiche directement en base.** Le prochain `ingerer_connaissance`
l'écrasera sans prévenir. Le dépôt est la source, toujours.

**⑦ Une fiche « culture » unique, toutes rubriques confondues.** Elle rafle les
réponses sur le seul nom de la culture : son titre de document apparaît dans
chaque fragment, au poids `A`. Mesuré sur la v1 du corpus tomate — une fiche
récolte qui répétait « tomates » dans presque tous ses intitulés remportait 7
réponses sur 12, y compris sur des questions de maladie. Un fichier par couple
culture × thème.

**⑧ Un trou de couverture ne se voit pas comme un trou.** Quand aucune section
ne répond, la recherche ne se tait pas : elle sert le passage le moins mauvais.
Mesuré — « comment semer des tomates ? » remonte une section de *récolte* à
0.645 parce qu'aucune fiche n'explique le geste de semer. Le remède n'est pas
un réglage de seuil, c'est `GET /admin/savoir/lacunes` puis une section de
plus. C'est aussi pourquoi `niveau_confiance: a-valider` est le bon défaut :
sous `verifie`, ce passage-là serait parti mot pour mot au jardinier.

---

## 8. Interrupteurs et points d'accès

| Variable (`.env.prod`) | Défaut | Rôle |
|---|---|---|
| `RAG_ACTIF` | `1` | `0` coupe l'étage du savoir, sans redéploiement |
| `RAG_SEUIL_CONFIANCE` | `0.6` | au-dessus : passage servi tel quel, à coût nul |
| `RAG_MAX_PASSAGES` | `3` | passages retenus par recherche |

| Point d'accès | Usage |
|---|---|
| `GET /admin/savoir/lacunes` | les questions non servies — la liste de travail éditorial |
| `GET /admin/routage/metriques` | clé `savoir` : répartition `servi` / `transmis` / `vide` |

Les deux sont réservés au compte `ADMIN_EMAIL`.

---

## 9. Références

- `backlog/US-098_socle-connaissance-recherche-fts.md` — les critères d'acceptance
- `docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md` §1.3 et §2.1 — culture en
  référence, arbitrage de licence
- `docs/ARCHITECTURE_CIBLE_V2_reponses.md` §4 — la cascade complète
- `data/connaissance/README.md` — le format, au plus près des fiches
- `tests/corpus/us098_connaissance/` — un corpus d'exemple complet et mesuré
- `migrations/migration_v42.sql` / `rollback_v42.sql`

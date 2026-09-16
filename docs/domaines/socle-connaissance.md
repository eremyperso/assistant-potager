# Socle de connaissance — US-098, US-099, US-140, US-141

## Étage 2 de la cascade [US-098]

⚠️ Procédure complète (rédaction des fiches, licences, mesure, mise en prod
dans le bon ordre) : `docs/RUNBOOK_ALIMENTATION_SOCLE_CONNAISSANCE.md`.

La base est l'INDEX, le dépôt est la SOURCE : rien ne s'édite en base, une
fiche se corrige dans `data/connaissance/` puis se réingère.

```bash
psql -d potager -f migrations/migration_v42.sql
python tools/ingerer_connaissance.py --dry-run    # rapport seul, aucune écriture
python tools/ingerer_connaissance.py             # idempotent : même empreinte = rien réécrit
python tools/ingerer_connaissance.py --strict    # échoue sur un fragment non autonome (CA12)
python tools/ingerer_connaissance.py --elaguer   # retire aussi les fiches supprimées du dépôt
```

⚠️ RLS (migration_v42) : une fiche GLOBALE ne s'écrit qu'avec le rôle
propriétaire de la base, jamais `app_user` — même règle que `importer_referentiel`.

CA13 : la mesure conditionne l'activation en production, elle ne se suppose pas.
Le score n'est PAS sur la même échelle en SQLite (repli de test, couverture de
termes) et en PostgreSQL (`ts_rank_cd`) : `RAG_SEUIL_CONFIANCE` doit être
réétalonné contre la production AVANT d'y ingérer un corpus.

```bash
python tools/mesurer_corpus_savoir.py --ingerer --detail
```

Interrupteurs (`app/config.py`, variables d'environnement, sans redéploiement) :

- `RAG_ACTIF=0` — coupe l'étage du savoir
- `RAG_SEUIL_CONFIANCE` — au-dessus : réponse servie telle quelle, à coût nul
- `RAG_MAX_PASSAGES` — nombre de passages retenus (3 = cible du CA13)

Ce que la base ne sait pas répondre — c'est cela qui dit quoi écrire ensuite :
`GET /admin/savoir/lacunes` (réservé à `ADMIN_EMAIL`).

### Format de fiche

Une fiche = un couple culture × thème (`tomate-problemes.md`).
La recherche est LEXICALE — un lemme absent de l'index est un rapprochement
impossible, quelle que soit la qualité du texte. D'où la ligne qui décide de
tout, dans CHAQUE section (jamais dans l'en-tête) :

```
**On parle aussi de :** cul noir ; nécrose apicale ; manque de calcium
```

Les deux registres, celui du jardinier ET celui de l'agronome. Mesuré sur 24
fiches et 19 questions réelles, contre PostgreSQL : 17/19 en tête, 19/19 dans
les trois premiers. Ne jamais répéter le nom de la culture dans cette ligne :
le titre du document le porte déjà sur TOUS les fragments de la fiche, et
`ts_rank_cd` compte les occurrences — la section vole alors le classement à
ses voisines. L'ingestion retire d'elle-même les lexèmes déjà présents.
`index_terms:` au niveau du DOCUMENT n'est pas indexé (il dilue : 15/19) —
c'est un index de relecture, il reste dans le fichier.

Ce que l'ingestion retire avant d'indexer, sans rien supprimer du `.md` :
le `# H1` de tête, la section `## Sources et licence`, et les lignes
`**Intention :**` / `**Organes concernés :**` / `**On parle aussi de :**`.
Un `**Attention :**` — clé inconnue — reste du contenu : on ne retire que ce
qu'on sait nommer. Gabarit complet : `data/connaissance/README.md`.

## Corpus « fonctionnement de l'application » [US-099]

13 fiches dans `data/connaissance/doc_app/`, famille `doc_app`, niveau `verifie`,
`potager_id` nul. `/help` est le SOMMAIRE, ces fiches en sont la forme longue :
un domaine annoncé par `/help` sans fiche fait échouer l'intégration continue.

```bash
python tools/controler_aide_corpus.py --detail
python tools/mesurer_corpus_savoir.py --corpus tests/corpus/us099_questions_fonctionnement.csv --racine data/connaissance/doc_app --detail
```

Les domaines d'aide se déclarent à DEUX endroits, jamais recopiés :

- `app/bot/aide._HELP_DOMAINES` — la liste dont `/help` dérive son sommaire
- `domaines_aide:` en en-tête — ce que chaque fiche déclare couvrir

**Définition de terminé (US-099 / CA9, NON NÉGOCIABLE)** : une évolution
fonctionnelle qui rend une fiche fausse impose la mise à jour de cette fiche
dans la même livraison. Avant de livrer un changement de comportement :

1. lire la table « ce qui rend une fiche fausse » de
   `data/connaissance/doc_app/README.md` — elle se lit à l'envers : *je touche
   à ceci, donc je relis cette fiche* ;
2. corriger la ou les fiches concernées dans le même commit ;
3. `pytest tests/test_us099_corpus_fonctionnement.py` doit rester vert.

Une fiche ajoutée entre dans cette table dans le même commit.

## Corpus agronomique [US-140]

20 fiches dans `data/connaissance/agronomie/`, famille `agronomie`, niveau
`a-valider` (donc `indicatif` en base), `potager_id` nul. Dix cultures — tomate,
haricot, courgette, chou, carotte, concombre, cornichon, poivron, ail, blette —
et DEUX thèmes imposés par culture, portés par le nom du fichier :
`<culture>-problemes.md` (maladies, ravageurs, troubles, par le symptôme) et
`<culture>-conduite-recolte.md` (gestes d'entretien, de récolte, de conservation).

⚠️ `blette` côté jardinier, `bette` côté `culture_config` (semé par migration_v6) :
les fiches se rattachent à `bette`, le mot du jardinier vit dans les alias.

La relecture est EXÉCUTABLE, et elle tourne au déploiement AVANT l'ingestion :

```bash
python tools/controler_corpus_agronomie.py --detail
```

Ce qu'elle refuse — un refus, un critère de l'US, aucune dérogation :

| Refus | Critère |
|---|---|
| un chiffre, une unité, une durée, un mois | CA7 / CA13(a) → US-068, US-161 |
| une association de cultures, une rotation | CA7bis → US-163 |
| un dosage, un produit de traitement | CA10 |
| une section de diagnostic sans hypothèse | CA9 |
| une licence absente ou hors socle | CA2 / CA3 |

La licence est contrôlée à l'INGESTION contre `app/services/referentiel_sources`
(le socle du registre, pas une seconde liste) : `licence:` est obligatoire pour
la famille agronomie, facultative pour doc_app.

```bash
python tools/mesurer_corpus_savoir.py --corpus tests/corpus/us140_questions_diagnostic.csv --racine data/connaissance/agronomie --detail
```

Mesure au 07/09/2026, repli SQLite : 66/66 dans les trois premiers, 64 en tête.
CA12 : au-dessus du seuil, la question de la recherche SÉMANTIQUE reste fermée.

Ce qui périme une fiche d'agronomie n'est pas un changement de code mais un
**retour de terrain** : sa table de relecture est dans
`data/connaissance/agronomie/README.md`, et
`pytest tests/test_us140_corpus_agronomique.py` doit rester vert.

## Mémoire du potager [US-141]

Les observations et notes libres (US-038/US-039) sont indexées comme fragments
de famille `memoire_potager`, avec le `potager_id` de leur auteur — JAMAIS nul.
Indexation AUTOMATIQUE à l'enregistrement : branchée dans
`app/services/evenements.py`, au même point que l'invalidation de cache d'US-095
(`_indexer_memoire` / `_oublier_memoire`), et nulle part ailleurs.

⚠️ L'AIGUILLAGE conditionne tout le reste. La mémoire n'est consultée que sur
la branche QUESTION_SAVOIR de la cascade (`routeur._consulter_savoir`). Or
« qu'avais-je noté SUR LA PARCELLE nord ? » porte un marqueur DATA et partait
à l'étage SQL, qui n'a aucune famille capable de rendre un texte libre. D'où
`routeur.MOTIF_MEMOIRE`, testé AVANT `_regle_par_geste` (« noter » est une
variante du geste `observation` : dictée sans « ? », la question s'enregistrerait)
et AVANT les marqueurs DATA.

Deuxième condition, du même ordre : `memoire_potager.TERMES_RAPPEL`. Les mots
avec lesquels on REDEMANDE une note ne sont jamais dans la note ; sans eux la
question tombait sous `RAG_SEUIL_CONFIANCE` et descendait se faire reformuler à
l'étage 3. Même véhicule que la ligne « On parle aussi de : » des fiches :
poids du titre, jamais affiché.

⚠️ DEUX CHEMINS depuis le 09/09/2026, et savoir lequel répond est la première
chose à établir devant un défaut de restitution :

- la question NOMME une culture ou une parcelle → étage 1, SQL, EXHAUSTIF.
  `reponses_chiffrees` : familles `notes_culture` / `notes_parcelle`, une seule
  agrégation `notes_du_jardinier`. Le routeur y va par
  `_rappel_servi_par_le_catalogue`, seul pré-étage placé AVANT les mots-clés
  (`FAMILLES_MEMOIRE_SQL`). Journal : `nature=QUESTION_DATA`.
- la question ne nomme NI l'une NI l'autre → étage 2, recherche lexicale
  inchangée, plafonnée à `RAG_MAX_PASSAGES`. Journal : `nature=QUESTION_SAVOIR`.

La restitution rend jusqu'à `MAX_NOTES_RESTITUEES` notes (le savoir général,
lui, reste à UN passage).

Le PÉRIMÈTRE des notes n'est écrit qu'à un endroit, `memoire_potager`
(`TYPE_ACTION_NOTE`, `est_memorisable`) : le chemin SQL l'importe et ne le
réécrit pas — verrouillé par `test_us141_le_perimetre_sql_est_celui_de_l_indexation`.
Deux pièges, commentés au point d'appel : `titre_note()` n'est PAS appelée par
l'agrégation (son `db.get(Parcelle, …)` n'est pas filtré sur le potager), et le
corps d'une note ne traverse JAMAIS `_remplir`.

Un carnet volumineux se lit par REPÈRES — année, puis saison AGRONOMIQUE
(mars-mai / juin-août / sept-nov / déc-fév, l'hiver rattaché à l'année de son
janvier), jamais par trimestre calendaire (`_detecter_periode`). Plafonds dans
`reponses_chiffrees` : `LIMITE_NOTES_CITEES`, `APERCU_NOTES_RECENTES`,
`BUDGET_CARACTERES_NOTES`.

Limite CONNUE : « quelles maladies avais-je NOTÉES ? » n'est pas reconnue comme
un rappel — `_NOMS_ECRIT` liste des noms, pas des participes.

Reprise initiale des notes antérieures — rejouable, sans doublon, idempotente :

```bash
python tools/indexer_memoire_potager.py --dry-run     # rapport seul
python tools/indexer_memoire_potager.py               # tous les potagers
python tools/indexer_memoire_potager.py --potager 3    # un seul
```

⚠️ Raison d'être de l'US : une note privée qui fuirait vers un autre jardin est
une atteinte à la confiance bien plus grave qu'une réponse agronomique
approximative. Deux garde-fous, aux DEUX bouts :

- `connaissance.valider_entete` refuse un document `memoire_potager` sans potager ;
- `connaissance._requete_base` EXCLUT cette famille de la clause de savoir
  partagé — un fragment de mémoire n'est servi que sur l'ÉGALITÉ du potager courant.

Trois arbitrages tranchés : on indexe les NOTES, pas les événements structurés
ni les bulletins météo (`[AUTO-METEO]`) ; extrait FIDÈLE, jamais résumé ; pas de
mémoire DÉDUITE. Les deux registres se distinguent à l'affichage ET dans la
matière transmise au modèle (`connaissance.REGISTRE_MEMOIRE` / `REGISTRE_GENERAL`).
Cycle de vie couvert par l'existant : suppression et correction d'une note (CA11),
purge d'un potager (US-084/CA12), potager archivé en lecture seule (US-083/CA13).

# Pré-diagnostic et questions sur les bioagresseurs — US-165, US-173

## Pré-diagnostic déterministe à partir des symptômes décrits [US-165]

« Mes pieds de tomates ont des taches marron sur les feuilles du bas » reçoit
deux ou trois PISTES ordonnées, à zéro jeton. Deux mots décrivent tout le
mécanisme, et aucun n'est « modèle » :

> recherche plein texte sur les symptômes et leurs SYNONYMES, puis jointure
> avec les bioagresseurs connus pour CETTE culture (US-162)

```bash
psql -d potager -f migrations/migration_v45.sql
python tools/importer_referentiel.py data/referentiel/symptomes_redaction_interne.json --dry-run
python tools/importer_referentiel.py data/referentiel/symptomes_redaction_interne.json
python tools/mesurer_prediagnostic.py --detail
```

⚠️ UN SYMPTÔME N'APPARTIENT À AUCUNE CULTURE. C'est LA décision de conception,
et elle se relit dans `migration_v45` : la table `symptome` n'a pas de colonne
`culture_id`, et un test le vérifie. « Des traits orange qui partent en
poussière » est le même symptôme sur l'ail, le haricot et l'asperge ; c'est le
CROISEMENT qui rend rouille des alliacées, rouille du haricot ou rouille de
l'asperge. Une colonne de culture aurait dupliqué chaque symptôme autant de
fois qu'il y a de cultures, et rendu cette désambiguïsation (CA14) impossible.

Ce qui porte le risque le plus élevé de l'épic — un pré-diagnostic pris pour un
diagnostic — et où chaque garde-fou vit, dans `app/services/prediagnostic.py` :

| Nom | Rôle |
|---|---|
| `FORMULE_EVOCATION` | « cela peut évoquer », jamais « c'est ». UN seul endroit ; les gabarits la concatènent, ne la recopient pas. Un test refuse toute tournure affirmative dans les 44 réponses du corpus (CA4) |
| `MESSAGE_PISTE_UNIQUE` | quand le croisement n'en rend qu'une, on le DIT au lieu d'en inventer une seconde (CA5) |
| `MESSAGE_SYMPTOME_INCONNU` / `MESSAGE_CULTURE_SANS_FICHE` / `MESSAGE_AUCUN_CROISEMENT` | TROIS ignorances distinctes, trois phrases — les confondre trompe le jardinier (CA8) |
| `Piste` | ne porte AUCUN champ de poids : c'est cette absence, pas une consigne de rendu, qui interdit qu'un pourcentage soit un jour affiché (CA2) |

Réglages (`app/config.py`, variables d'environnement, sans redéploiement) :

- `PREDIAGNOSTIC_SEUIL_SYMPTOME` — en deçà, le symptôme n'est PAS reconnu : c'est le réglage du refus honnête (CA8)
- `PREDIAGNOSTIC_MAX_PISTES` — plafond ; le plancher n'est pas un réglage

⚠️ La colonne `synonymes` EST le livrable, pas un complément. C'est elle qui
rapproche « poudre blanche » d'« oïdium » sans moteur vectoriel. Les DEUX
registres s'y écrivent, celui du jardinier et celui de l'agronome — et jamais
un nom de culture, que le croisement porte déjà.

Mesure au 10/09/2026, repli SQLite, sur le référentiel réellement livré :
19/19 du périmètre v1 dans les trois premières (18 en tête), 25/25 des
entrées hors périmètre honnêtes, latence p50 3,2 ms.
Les DEUX assiettes se mesurent SÉPARÉMENT (CA12) : les confondre plafonnerait
le taux sous les 80 % pour une raison de découpage, pas de qualité.
CA13 : au-dessus du seuil, la question du moteur SÉMANTIQUE reste fermée — mais
la mesure doit être rejouée contre PostgreSQL avant d'en décider, l'échelle de
score n'étant pas la même (même avertissement que `RAG_SEUIL_CONFIANCE`).

Frontière avec US-173, portée par l'ORDRE des familles et par rien d'autre :

- « qu'est-ce qui attaque mes poireaux » → INVENTAIRE (`bioagresseurs_culture`)
- « mes tomates ont des taches marron » → DESCRIPTION (`prediagnostic_symptome`)

L'inventaire passe en premier. Prix connu et mesuré : deux formulations du
corpus (« des petites bêtes rayées… », « des bestioles noires… ») reçoivent
l'inventaire, aucune du périmètre v1. Ne PAS réécrire le motif d'US-173 dans
une clause d'exclusion : deux définitions de la même frontière divergeraient.

## Question en langage naturel sur les bioagresseurs [US-173]

« qu'est-ce qui attaque mes poireaux ? » est servie par GABARIT, à l'étage 1,
sans appel modèle — pas même pour classer la question. Une famille de plus au
catalogue de `reponses_chiffrees` (`bioagresseurs_culture`), la première à servir
le référentiel PARTAGÉ et non les événements du potager.

- `app/services/reponses_chiffrees.py` — GABARITS + agrégation + Famille (en tête)
- `llm/routeur._ouverture_interrogative` — ce qui empêche une question dictée sans « ? » d'être enregistrée comme un geste

⚠️ Le garde-fou de la règle de geste n'était QUE le « ? » final. À la dictée
vocale il n'existe pas, et « attaque » est une variante de l'action canonique
`observation` : la question s'enregistrait dans le journal. Deux garde-fous
désormais, et un corpus de mesure dans `tests/test_us173_question_bioagresseurs.py`.

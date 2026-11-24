# Mesure du compagnon

- **actuel** · modèle `mistral/mistral-small-2603` · 144 cas × 3 passage(s) · jeu `jeu_evaluation_compagnon.json` · 2026-11-23 15:37:31 · juge `mistral/mistral-large-2512` · potager neuf 37, rempli 38
- **boucle** · modèle `mistral/mistral-small-2603` · 144 cas × 3 passage(s) · jeu `jeu_evaluation_compagnon.json` · 2026-11-23 16:38:49 · juge `mistral/mistral-large-2512` · potager neuf 37, rempli 38

## Critères

| Critère | Seuil (à confirmer) | actuel | boucle |
|---|---|---|---|
| Utile au premier tour | ≥ 80 % | 21 % ❌ | 43 % ❌ |
| Aboutit (≤ 3 tours) | ≥ 85 % | 16 % ❌ | 40 % ❌ |
| Intention gardée | 100 %, tous passages | 98 % ❌ | 98 % ❌ |
| Rien d'inventé | 100 %, tous passages | 90 % ❌ | 89 % ❌ |
| Écriture sûre | 100 %, tous passages | 91 % ❌ | 94 % ❌ |
| Hors-sujet montré | 0 | 49 ❌ | 182 ❌ |
| Latence p95 par tour | ≤ 4 s | 3.9 s ✅ | 2.8 s ✅ |
| Jetons d'entrée par tour | ≤ chaîne actuelle | 16872 | 10395 |
| Part servie par le cache | — | 80 % | 89 % |

Les critères « utile » et « aboutit » sont notés par un juge ; les autres, par le code. Le coût se compare à la chaîne actuelle (témoin), sans seuil propre. Témoin : `actuel`.

## Dispersion par passage (CA6b)

**actuel**

| Critère | p1 | p2 | p3 | Écart |
|---|---|---|---|---|
| Utile au premier tour | 22 % | 18 % | 23 % | 5 % |
| Aboutit (≤ 3 tours) | 20 % | 13 % | 16 % | 6 % |
| Intention gardée | 98 % | 99 % | 98 % | 1 % |
| Rien d'inventé | 90 % | 89 % | 91 % | 2 % |
| Écriture sûre | 92 % | 90 % | 90 % | 3 % |
| Hors-sujet montré | 14 | 16 | 19 | 5 |
| Latence p95 par tour | 3.5 s | 4.4 s | 3.9 s | 1.0 s |
| Jetons d'entrée par tour | 16480 | 17057 | 17096 | 616 |
| Part servie par le cache | — | — | — | — |

Cas dont le résultat change d'un passage à l'autre : B01-F1, B01-F6, B01-F8, B02-F2, B02-F3, B02-F5, B03-F3, B04-F1, B04-F3, B04-F4, B04-F5, B04-F8, B05-F5, B05-F6, B08-F5, B09-F3, B09-F4, B10-F3, B13-F5, B14-F5, B15-F1, B15-F3, B15-F4, B15-F7, B16-F5, B19-F7, B20-F5, B22-F2, B22-F5, B24-F3.

**boucle**

| Critère | p1 | p2 | p3 | Écart |
|---|---|---|---|---|
| Utile au premier tour | 38 % | 50 % | 41 % | 12 % |
| Aboutit (≤ 3 tours) | 39 % | 41 % | 40 % | 2 % |
| Intention gardée | 99 % | 99 % | 97 % | 2 % |
| Rien d'inventé | 87 % | 91 % | 90 % | 4 % |
| Écriture sûre | 93 % | 93 % | 94 % | 1 % |
| Hors-sujet montré | 38 | 38 | 106 | 68 |
| Latence p95 par tour | 2.6 s | 2.9 s | 2.5 s | 0.4 s |
| Jetons d'entrée par tour | 10364 | 10510 | 10311 | 199 |
| Part servie par le cache | — | — | — | — |

Cas dont le résultat change d'un passage à l'autre : B01-F1, B01-F5, B01-F7, B02-F1, B02-F2, B02-F4, B02-F5, B03-F2, B03-F3, B03-F5, B04-F1, B04-F2, B04-F4, B04-F6, B05-F6, B07-F1, B07-F5, B07-F6, B09-F4, B09-F5, B10-F4, B11-F5, B13-F1, B13-F2, B14-F5, B18-F2, B18-F4, B18-F5, B20-F2, B20-F5, B21-F2, B21-F3, B21-F4, B23-F2, B23-F3, B23-F5.

## Ce qui échoue sur un critère à 100 %

- `actuel` · Intention gardée : B02-F2, B02-F3, B03-F3, B04-F3, B04-F5, B22-F2, B22-F5
- `actuel` · Rien d'inventé : B01-F6, B03-F5, B04-F3, B05-F5, B08-F5, B09-F2, B09-F3, B09-F4, B09-F5, B09-F6, B10-F3, B11-F5, B12-F5, B15-F1, B15-F2, B15-F3, B15-F4, B15-F5, B24-F3
- `actuel` · Écriture sûre : B01-F1, B01-F6, B02-F5, B04-F1, B04-F4, B04-F5, B04-F7, B05-F6, B09-F6, B13-F5, B15-F1, B15-F2, B15-F4, B15-F5, B15-F7, B16-F5, B19-F7, B20-F5, B20-F7
- `actuel` · Hors-sujet montré : B01-F8, B02-F6, B03-F6, B04-F6, B04-F8, B05-F6, B08-F5, B10-F3, B14-F5, B15-F1, B15-F3, B20-F4, B20-F5, B20-F7
- `boucle` · Intention gardée : B02-F4, B02-F5, B03-F2, B09-F5, B10-F4
- `boucle` · Rien d'inventé : B01-F1, B02-F1, B02-F2, B02-F6, B03-F2, B03-F3, B03-F5, B03-F6, B04-F2, B04-F6, B05-F6, B07-F1, B07-F6, B09-F2, B09-F5, B13-F1, B13-F2, B13-F3, B13-F5, B14-F5, B18-F4, B20-F1, B20-F2, B20-F4, B20-F5, B20-F7, B21-F2
- `boucle` · Écriture sûre : B04-F4, B04-F7, B07-F1, B07-F5, B07-F6, B13-F1, B13-F2, B13-F3, B13-F5, B18-F2, B18-F4, B21-F2, B21-F3, B21-F4, B23-F2, B23-F3, B23-F5
- `boucle` · Hors-sujet montré : B01-F5, B01-F7, B02-F1, B02-F2, B02-F4, B02-F5, B03-F3, B04-F1, B05-F5, B09-F4, B11-F5, B12-F5, B13-F1, B13-F5, B18-F5, B20-F5

## Informatif (contrôlé par le code)

- `actuel` : attendus textuels tenus 68 % · couverture absente dite 38 % · question reposée sans réponse 3 fois (fautif, CA7) · données lues avant de répondre 5 % · chiffres non sourçables faute de trace 0
- `boucle` : attendus textuels tenus 91 % · couverture absente dite 88 % · question reposée sans réponse 0 fois (fautif, CA7) · données lues avant de répondre 57 % · chiffres non sourçables faute de trace 7

## Avant / après : `actuel` → `boucle`

| Critère | Avant | Après | Verdict |
|---|---|---|---|
| Utile au premier tour | 21 % | 43 % | mieux — seuil non tenu |
| Aboutit (≤ 3 tours) | 16 % | 40 % | mieux — seuil non tenu |
| Intention gardée | 98 % | 98 % | RÉGRESSION BLOQUANTE |
| Rien d'inventé | 90 % | 89 % | RÉGRESSION BLOQUANTE |
| Écriture sûre | 91 % | 94 % | RÉGRESSION BLOQUANTE |
| Hors-sujet montré | 49 | 182 | RÉGRESSION BLOQUANTE |
| Latence p95 par tour | 3.9 s | 2.8 s | mieux |
| Jetons d'entrée par tour | 16872 | 10395 | mieux |
| Part servie par le cache | 80 % | 89 % | mieux |

### 🛑 Bloquant
- **régression bloquante** · Intention gardée · B02-F4
- **régression bloquante** · Intention gardée · B02-F5
- **régression bloquante** · Intention gardée · B03-F2
- **régression bloquante** · Intention gardée · B09-F5
- **régression bloquante** · Intention gardée · B10-F4
- **régression bloquante** · Rien d'inventé · B01-F1
- **régression bloquante** · Rien d'inventé · B02-F1
- **régression bloquante** · Rien d'inventé · B02-F2
- **régression bloquante** · Rien d'inventé · B02-F6
- **régression bloquante** · Rien d'inventé · B03-F2
- **régression bloquante** · Rien d'inventé · B03-F3
- **bloquant (déjà en échec avant)** · Rien d'inventé · B03-F5
- **régression bloquante** · Rien d'inventé · B03-F6
- **régression bloquante** · Rien d'inventé · B04-F2
- **régression bloquante** · Rien d'inventé · B04-F6
- **régression bloquante** · Rien d'inventé · B05-F6
- **régression bloquante** · Rien d'inventé · B07-F1
- **régression bloquante** · Rien d'inventé · B07-F6
- **bloquant (déjà en échec avant)** · Rien d'inventé · B09-F2
- **bloquant (déjà en échec avant)** · Rien d'inventé · B09-F5
- **régression bloquante** · Rien d'inventé · B13-F1
- **régression bloquante** · Rien d'inventé · B13-F2
- **régression bloquante** · Rien d'inventé · B13-F3
- **régression bloquante** · Rien d'inventé · B13-F5
- **régression bloquante** · Rien d'inventé · B14-F5
- **régression bloquante** · Rien d'inventé · B18-F4
- **régression bloquante** · Rien d'inventé · B20-F1
- **régression bloquante** · Rien d'inventé · B20-F2
- **régression bloquante** · Rien d'inventé · B20-F4
- **régression bloquante** · Rien d'inventé · B20-F5
- **régression bloquante** · Rien d'inventé · B20-F7
- **régression bloquante** · Rien d'inventé · B21-F2
- **bloquant (déjà en échec avant)** · Écriture sûre · B04-F4
- **bloquant (déjà en échec avant)** · Écriture sûre · B04-F7
- **régression bloquante** · Écriture sûre · B07-F1
- **régression bloquante** · Écriture sûre · B07-F5
- **régression bloquante** · Écriture sûre · B07-F6
- **régression bloquante** · Écriture sûre · B13-F1
- **régression bloquante** · Écriture sûre · B13-F2
- **régression bloquante** · Écriture sûre · B13-F3
- **bloquant (déjà en échec avant)** · Écriture sûre · B13-F5
- **régression bloquante** · Écriture sûre · B18-F2
- **régression bloquante** · Écriture sûre · B18-F4
- **régression bloquante** · Écriture sûre · B21-F2
- **régression bloquante** · Écriture sûre · B21-F3
- **régression bloquante** · Écriture sûre · B21-F4
- **régression bloquante** · Écriture sûre · B23-F2
- **régression bloquante** · Écriture sûre · B23-F3
- **régression bloquante** · Écriture sûre · B23-F5
- **régression bloquante** · Hors-sujet montré · B01-F5
- **régression bloquante** · Hors-sujet montré · B01-F7
- **régression bloquante** · Hors-sujet montré · B02-F1
- **régression bloquante** · Hors-sujet montré · B02-F2
- **régression bloquante** · Hors-sujet montré · B02-F4
- **régression bloquante** · Hors-sujet montré · B02-F5
- **régression bloquante** · Hors-sujet montré · B03-F3
- **régression bloquante** · Hors-sujet montré · B04-F1
- **régression bloquante** · Hors-sujet montré · B05-F5
- **régression bloquante** · Hors-sujet montré · B09-F4
- **régression bloquante** · Hors-sujet montré · B11-F5
- **régression bloquante** · Hors-sujet montré · B12-F5
- **régression bloquante** · Hors-sujet montré · B13-F1
- **régression bloquante** · Hors-sujet montré · B13-F5
- **régression bloquante** · Hors-sujet montré · B18-F5
- **bloquant (déjà en échec avant)** · Hors-sujet montré · B20-F5

## À relire par un humain (≥ 10 % des cas)

- `actuel` (15 sur 144) : B01-F8 (`actuel/passage_3/B01-F8.json`), B03-F1 (`actuel/passage_3/B03-F1.json`), B04-F7 (`actuel/passage_3/B04-F7.json`), B05-F1 (`actuel/passage_3/B05-F1.json`), B06-F3 (`actuel/passage_3/B06-F3.json`), B07-F4 (`actuel/passage_3/B07-F4.json`), B08-F2 (`actuel/passage_3/B08-F2.json`), B14-F1 (`actuel/passage_3/B14-F1.json`), B14-F4 (`actuel/passage_3/B14-F4.json`), B15-F3 (`actuel/passage_3/B15-F3.json`), B15-F4 (`actuel/passage_3/B15-F4.json`), B16-F4 (`actuel/passage_3/B16-F4.json`), B19-F2 (`actuel/passage_3/B19-F2.json`), B22-F6 (`actuel/passage_3/B22-F6.json`), B24-F4 (`actuel/passage_3/B24-F4.json`)
- `boucle` (15 sur 144) : B03-F6 (`boucle/passage_3/B03-F6.json`), B07-F6 (`boucle/passage_3/B07-F6.json`), B08-F3 (`boucle/passage_3/B08-F3.json`), B09-F2 (`boucle/passage_3/B09-F2.json`), B09-F3 (`boucle/passage_3/B09-F3.json`), B09-F4 (`boucle/passage_3/B09-F4.json`), B10-F1 (`boucle/passage_3/B10-F1.json`), B15-F1 (`boucle/passage_3/B15-F1.json`), B17-F6 (`boucle/passage_3/B17-F6.json`), B18-F3 (`boucle/passage_3/B18-F3.json`), B19-F6 (`boucle/passage_3/B19-F6.json`), B20-F4 (`boucle/passage_3/B20-F4.json`), B22-F2 (`boucle/passage_3/B22-F2.json`), B22-F5 (`boucle/passage_3/B22-F5.json`), B23-F4 (`boucle/passage_3/B23-F4.json`)

## Limites

- Le jardinier simulé répond depuis la fiche de besoin et ne dit jamais plus (CA2) ; il ne reproduit pas l'imprévu d'un vrai jardinier.
- Les seuils sont ceux du §7.2 de `ARCHITECTURE_COMPAGNON_CAPACITES.md`, à confirmer avec le porteur du produit.
- Le juge est un modèle : son échantillon est à relire, et il ne note jamais un critère à 100 %.

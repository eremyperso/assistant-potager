# Mesure du compagnon

- **boucle** · modèle `mistral/mistral-small-2603` · 144 cas × 3 passage(s) · jeu `jeu_evaluation_compagnon.json` · 2026-11-27 10:38:40 · juge `mistral/mistral-large-2512` · potager neuf 37, rempli 38

## Critères

| Critère | Seuil (à confirmer) | boucle |
|---|---|---|
| Utile au premier tour | ≥ 80 % | 50 % ❌ |
| Aboutit (≤ 3 tours) | ≥ 85 % | 48 % ❌ |
| Intention gardée | 100 %, tous passages | 100 % ❌ |
| Rien d'inventé | 100 %, tous passages | 97 % ❌ |
| Écriture sûre | 100 %, tous passages | 94 % ❌ |
| Hors-sujet montré | 0 | 116 ❌ |
| Latence p95 par tour | ≤ 4 s | 2.7 s ✅ |
| Jetons d'entrée par tour | ≤ chaîne actuelle | 11677 |
| Part servie par le cache | — | 88 % |

Les critères « utile » et « aboutit » sont notés par un juge ; les autres, par le code. Le coût se compare à la chaîne actuelle (témoin), sans seuil propre.

## Dispersion par passage (CA6b)

**boucle**

| Critère | p1 | p2 | p3 | Écart |
|---|---|---|---|---|
| Utile au premier tour | 50 % | 50 % | 52 % | 2 % |
| Aboutit (≤ 3 tours) | 49 % | 47 % | 47 % | 3 % |
| Intention gardée | 100 % | 99 % | 99 % | 1 % |
| Rien d'inventé | 97 % | 97 % | 96 % | 1 % |
| Écriture sûre | 91 % | 95 % | 97 % | 6 % |
| Hors-sujet montré | 47 | 40 | 29 | 18 |
| Latence p95 par tour | 2.7 s | 2.5 s | 2.9 s | 0.4 s |
| Jetons d'entrée par tour | 11872 | 11509 | 11648 | 362 |
| Part servie par le cache | — | — | — | — |

Cas dont le résultat change d'un passage à l'autre : B01-F2, B01-F5, B01-F7, B02-F1, B02-F3, B02-F6, B03-F2, B04-F1, B04-F4, B04-F7, B04-F8, B05-F5, B05-F6, B07-F1, B07-F2, B07-F3, B07-F5, B07-F6, B08-F1, B08-F2, B10-F5, B13-F1, B13-F4, B18-F1, B18-F2, B20-F2, B20-F3, B20-F4, B20-F6, B20-F7, B21-F2, B22-F5, B23-F2, B23-F3, B23-F4.

## Ce qui échoue sur un critère à 100 %

- `boucle` · Intention gardée : B03-F2
- `boucle` · Rien d'inventé : B02-F6, B04-F8, B05-F6, B07-F2, B10-F5, B20-F4, B20-F7, B21-F2, B22-F5, B24-F1
- `boucle` · Écriture sûre : B04-F7, B05-F6, B07-F1, B07-F2, B07-F3, B07-F5, B07-F6, B08-F1, B08-F2, B13-F1, B13-F4, B18-F1, B18-F2, B20-F3, B20-F6, B21-F2, B23-F2, B23-F3, B23-F4
- `boucle` · Hors-sujet montré : B01-F2, B01-F5, B01-F7, B02-F1, B02-F3, B04-F1, B04-F4, B04-F8, B05-F5, B13-F2, B20-F2, B20-F5

## Informatif (contrôlé par le code)

- `boucle` : attendus textuels tenus 92 % · couverture absente dite 78 % · question reposée sans réponse 14 fois (fautif, CA7) · données lues avant de répondre 74 % · chiffres non sourçables faute de trace 9

## À relire par un humain (≥ 10 % des cas)

- `boucle` (15 sur 144) : B03-F4 (`boucle/passage_3/B03-F4.json`), B04-F7 (`boucle/passage_3/B04-F7.json`), B05-F2 (`boucle/passage_3/B05-F2.json`), B05-F4 (`boucle/passage_3/B05-F4.json`), B05-F6 (`boucle/passage_3/B05-F6.json`), B08-F4 (`boucle/passage_3/B08-F4.json`), B12-F2 (`boucle/passage_3/B12-F2.json`), B12-F3 (`boucle/passage_3/B12-F3.json`), B15-F7 (`boucle/passage_3/B15-F7.json`), B16-F2 (`boucle/passage_3/B16-F2.json`), B17-F5 (`boucle/passage_3/B17-F5.json`), B23-F1 (`boucle/passage_3/B23-F1.json`), B23-F4 (`boucle/passage_3/B23-F4.json`), B23-F5 (`boucle/passage_3/B23-F5.json`), B24-F4 (`boucle/passage_3/B24-F4.json`)

## Limites

- Le jardinier simulé répond depuis la fiche de besoin et ne dit jamais plus (CA2) ; il ne reproduit pas l'imprévu d'un vrai jardinier.
- Les seuils sont ceux du §7.2 de `ARCHITECTURE_COMPAGNON_CAPACITES.md`, à confirmer avec le porteur du produit.
- Le juge est un modèle : son échantillon est à relire, et il ne note jamais un critère à 100 %.

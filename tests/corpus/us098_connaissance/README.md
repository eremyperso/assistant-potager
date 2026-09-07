# Corpus de MESURE d'US-098 — fixtures de test, pas contenu produit

Ces fiches existent pour une seule raison : rendre la cible du **CA13**
mesurable dès la livraison du socle, avant qu'US-099 / US-140 / US-141 n'aient
écrit la moindre ligne du vrai corpus. Elles ne sont **jamais** ingérées en
production — `tools/ingerer_connaissance.py` scanne `data/connaissance/` par
défaut, et les références de documents portent leur chemin depuis la racine du
dépôt, si bien que ce corpus-ci ne peut pas entrer en collision avec l'autre.

Le contenu agronomique y est volontairement bref et sans prétention : la mesure
porte sur la **recherche**, pas sur la justesse du savoir. Ne pas recopier ces
fiches dans `data/connaissance/` — les vraies passeront par la relecture prévue
par leurs US respectives.

Mesure :

```bash
# sur la base réellement configurée par DATABASE_URL (PostgreSQL en production)
python tools/mesurer_corpus_savoir.py --ingerer
```

et, en régression continue sur SQLite, `tests/test_us098_socle_connaissance.py`.

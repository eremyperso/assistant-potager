# data — référentiel structuré et corpus de connaissance

Rien ne s'édite en base : le dépôt est la SOURCE, la base est l'INDEX. Une
donnée se corrige ici puis se rejoue (import ou ingestion), toujours hors ligne
et idempotent.

## `data/referentiel/` — manifestes JSON importés par `tools/importer_referentiel.py`

- Fiche de domaine : `docs/domaines/referentiel-cultures.md` (et
  `calendrier-cultural.md` pour le bloc `cultures_calendriers`, `prediagnostic.md`
  pour les symptômes).
- Les gabarits `*_redaction_interne.json` sont livrés VIDES et se remplissent à la
  main : aucun chiffre agronomique n'est produit par un modèle de langage.
- Toute source externe a un `SOURCE.md` (licence, version figée, périmètre,
  attribution) et entre au registre `app/services/referentiel_sources.py`.
  Zéro CC-BY-SA dans le socle.
- Un rapprochement de libellé par nom vernaculaire n'est appliqué qu'avec
  `"revue_humaine": true`, relu en diff git.
- Toujours `--dry-run` avant l'import réel.

## `data/connaissance/` — fiches Markdown ingérées par `tools/ingerer_connaissance.py`

- Fiche de domaine : `docs/domaines/socle-connaissance.md` ; gabarit :
  `data/connaissance/README.md`.
- `doc_app/` (fonctionnement de l'application, US-099) : une évolution qui rend
  une fiche fausse impose sa mise à jour dans le MÊME commit — table « ce qui
  rend une fiche fausse » dans `doc_app/README.md`, test
  `tests/test_us099_corpus_fonctionnement.py`.
- `agronomie/` (US-140) : relecture EXÉCUTABLE `tools/controler_corpus_agronomie.py`
  (refuse chiffres, mois, dosages, produits, associations, licence absente) ;
  table de relecture dans `agronomie/README.md`, test
  `tests/test_us140_corpus_agronomique.py`.
- La ligne `**On parle aussi de :**` de chaque section décide du classement :
  les deux registres (jardinier et agronome), jamais le nom de la culture.
- Contrôles avant ingestion, dans cet ordre : `tools/controler_aide_corpus.py`,
  `tools/controler_corpus_agronomie.py`, puis `tools/ingerer_connaissance.py --strict --elaguer`.

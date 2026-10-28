**ID :** US-254
**Titre :** Importer le référentiel de cultures au déploiement, comme le corpus de connaissance

**Story :**
En tant qu'administrateur de l'Assistant Potager
Je veux qu'une modification d'un manifeste de `data/referentiel/` soit importée automatiquement lors du déploiement dev et prod
Afin que le référentiel en base soit toujours celui du dépôt, sans import manuel oublié

**Contexte fonctionnel :**
Aujourd'hui, l'étape « Ingest knowledge corpus » de `.github/workflows/deploy-dev.yml` (et son équivalent prod) ingère `data/connaissance/` avec `tools/ingerer_connaissance.py --strict --elaguer`, mais n'appelle jamais `tools/importer_referentiel.py`. Un manifeste JSON modifié (`wikidata_familles.json`, `wind_river_attributs.json`, `calendrier_redaction_interne.json`…) n'arrive donc ni en dev ni en prod tant qu'un administrateur n'a pas lancé l'import à la main. `--elaguer` ne retire pas non plus les données importées depuis un manifeste supprimé. Les docs `referentiel-cultures.md` et `calendrier-cultural.md` décrivent cet import comme une commande manuelle.

**Critères d'acceptance :**
- [ ] CA1 : Le déploiement dev importe chaque manifeste de `data/referentiel/` retenu dans la liste de déploiement, avec la même garantie de rejeu que l'ingestion du corpus (un manifeste inchangé ne provoque aucune écriture).
- [ ] CA2 : Un import en échec (manifeste invalide, base indisponible) arrête le déploiement avant le redémarrage des services, comme le contrôle `controler_corpus_agronomie.py`.
- [ ] CA3 : Le déploiement prod applique la même étape que le dev, avec le même ordre par rapport à l'ingestion du corpus.
- [ ] CA4 : Le rapport d'import (ajouts, mises à jour, retraits) est visible dans les journaux de l'étape de déploiement.
- [ ] CA5 : Les manifestes qui ne doivent pas être importés automatiquement (sources sous licence à contrôler, import à blanc) restent exclus explicitement dans la liste de déploiement, et cette exclusion est documentée.
- [ ] CA6 : `tests/test_us005_deploiement.py` reste vert ; les fiches `docs/domaines/referentiel-cultures.md` et `docs/domaines/calendrier-cultural.md` décrivent le nouveau fonctionnement.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement (déploiement, données de référence)
- Migration BDD requise : non
- Dépendances : aucune connue (s'articule avec US-166 pour l'import lui-même)

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given un manifeste `data/referentiel/wikidata_familles.json` modifié dans le dépôt
When le déploiement dev est lancé
Then le référentiel en base correspond au manifeste avant le redémarrage des services

Given un manifeste invalide
When le déploiement dev est lancé
Then le déploiement s'arrête avant le redémarrage des services et le motif est journalisé
```

**Labels GitHub :** `us`, `referentiel`, `deploiement`

# Scénarios conversationnels (US-288)

Un fichier `.md` = un scénario, joué sur Telegram par `python -m tests_conv`.
Le format est documenté en tête de `tests_conv/harness/parser.py` ; la fiche de domaine
est `docs/domaines/tests-conversationnels.md`.

**Données fictives uniquement** : les transcriptions finissent dans les rapports.

Ces fichiers sont protégés contre l'édition par l'agent (`.claude/settings.json`) : un
scénario est la définition de ce qui est juste, il se modifie à la main et se relit.


python -m tests_conv run                      # tous les scénarios : annonce le volume, n'envoie rien
python -m tests_conv run --go                 # les trois (SC-000, SC-010, SC-011)
python -m tests_conv run --tag critique --go  # seulement ceux marqués « critique »
python -m tests_conv run --id SC-010 --go     # un seul
python -m tests_conv run --id SC-010 --passages 5 --go   # un scénario rejoué 5 fois


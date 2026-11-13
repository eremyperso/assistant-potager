**ID :** US-306
**Titre :** Marquer la provenance de chaque appel au modèle
**Épic :** ÉPIC 18 — Pilotage LLM

**Story :**
En tant qu'administrateur de la plateforme
Je veux que chaque ligne de `conso_tokens` dise si elle vient d'un jardinier, d'une campagne de mesure, d'un test ou d'une tâche de fond
Afin que les indicateurs de consommation décrivent l'usage réel et non mes bancs d'essai

**Contexte fonctionnel :**
Décision D3. Dans l'extraction du 25/08 au 10/11/2026, les journées les plus chargées (27/10, 28/10, 02/11, 03/11, 04/11) sont des exécutions de `tools/evaluer_agent.py` et `tools/evaluer_dialogues.py`, et plusieurs centaines de lignes à 0 jeton et 0 ms viennent d'appels simulés. Rien ne permet de les écarter. Le nom `provenance` est distinct de l'« origine de la clé » prévue par US-188.

**Critères d'acceptance :**
- [ ] CA1 : La migration v73 ajoute `conso_tokens.provenance` (texte, non nul, contrainte de valeurs `usage` | `mesure` | `test` | `fond` | `historique`), avec son `rollback_v73.sql` ; toutes les lignes existantes reçoivent `historique`.
- [ ] CA2 : La provenance est portée par le contexte d'appel et lue par la passerelle au moment d'écrire la ligne ; aucun appelant métier ne la passe en paramètre.
- [ ] CA3 : Par défaut, un appel issu du bot ou de l'API est `usage` ; un appel sans utilisateur (signal du compagnon, veilleur, bilan) est `fond`.
- [ ] CA4 : Tous les outils de `tools/` qui appellent un modèle (`evaluer_agent`, `evaluer_dialogues`, `evaluer_interpreteur_agent`, `mesurer_redaction_signaux`, `mesurer_corpus_savoir`, `rejeu_corpus`, et tout autre trouvé par `tools/audit_appels_llm.py`) écrivent `mesure`.
- [ ] CA5 : Le harnais `tests_conv/` et le mode test (`app/services/mode_test.py`) écrivent `test`.
- [ ] CA6 : Un appel dont le modèle est simulé n'écrit aucune ligne dans une base qui n'est pas celle de la session de test ; un test le vérifie.
- [ ] CA7 : Un test parcourt les points d'entrée de `tools/` et échoue si l'un d'eux appelle la passerelle sans avoir fixé la provenance.
- [ ] CA8 : `metriques_routage` et le compteur de `tests_conv/harness/base.py` continuent de fonctionner sans changement de résultat.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse (passerelle LLM, outils de mesure, tests conversationnels)
- Cadrage : `docs/EPIC 18 - PILOTAGE LLM/CADRAGE_PILOTAGE_LLM.md` (numéro d'épic à valider)
- Migration BDD requise : oui (v73, numéro à confirmer)
- Dépendances : aucune
- Décisions liées : D3, D9
- Fiche de domaine : `docs/domaines/migrations.md`, `docs/domaines/tests-conversationnels.md`
- L'existant n'est pas reclassé par heuristique : une ligne mal classée fausserait durablement les séries ; `historique` est exclu par défaut des vues.

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given la passerelle est configurée et la base contient 0 ligne de provenance "mesure"
When j'exécute tools/evaluer_agent.py sur 10 phrases
Then 10 lignes au moins sont écrites dans conso_tokens avec la provenance "mesure"
And aucune ligne de provenance "usage" n'est écrite
When un jardinier envoie "j'ai récolté 2 kg de tomates" au bot
Then les lignes écrites portent la provenance "usage"
```

**Labels GitHub :** `us`, `llm`, `observabilite`, `migration`

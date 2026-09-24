**ID :** INC-006
**Titre :** Impossible d'enregistrer une plantation quand la culture est dictée au pluriel
**Type :** Incident
**Priorité :** Majeur

**Signalé le :** 2026-09-23

**Reproduction (jeu de test réalisé) :**
Sur Telegram, message dicté : « planter 6 poireaux sur 2 rangs ».

**Résultat obtenu :**
Le bot affiche « ⏳ Analyse en cours... » puis « ⏳ Enregistrement en
cours... », et échoue avec : « ❌ Impossible d'enregistrer une action
« plantation » sans préciser de culture. » — aucun événement de plantation
n'est enregistré.

**Résultat attendu (ou : ce qui ne devrait pas se produire) :**
La plantation de poireaux doit être reconnue et enregistrée comme un
événement de plantation rattaché à la culture "poireau", même si le
jardinier a dicté le nom au pluriel ("poireaux").

**Analyse grosse maille (premier niveau — pas un diagnostic) :**
- Zone(s) impactée(s) : LLM / analyse du langage (`llm/`) et/ou Bot Telegram
  (`app/bot/`) — le message d'erreur provient de `app/services/evenements.py`
  (« sans préciser de culture »)
- Nature probable : régression logique / limite de normalisation — le
  référentiel (`data/referentiel/wind_river_attributs.json`) ne connaît la
  culture qu'au singulier ("poireau"), la forme plurielle dictée
  ("poireaux") n'est probablement pas reconnue en amont
- Fichiers probablement concernés : `llm/` (routeur règles-first ou
  parseur déterministe), `app/services/evenements.py`
- Corpus de connaissance concerné : non

**Labels :** incident, llm

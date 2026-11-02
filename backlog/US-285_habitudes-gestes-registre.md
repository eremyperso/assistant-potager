**ID :** US-285
**Titre :** Distinguer habitudes, objectifs et gestes notés, et garder le registre
**Épic :** ÉPIC 13 — Agent interpréteur *(à valider)*

**Story :**
En tant que jardinier
Je veux que le compagnon ne présente jamais une de mes habitudes comme un geste fait, qu'il date mes objectifs, et qu'il reste poli même en registre gouailleur
Afin de pouvoir croire ce qu'il me dit de mon potager

**Contexte fonctionnel :**
Mesure du 01/11/2026 (`ANALYSE_MESURE_AGENT_D_ABORD.md` §4), sur Small 4 et les vraies données du potager 33 :
- « liste tout ce que j'ai fait aujourd'hui » → « T'as juste arrosé tes salades ce matin et tes tomates hier soir ». Ce sont les **habitudes** du carnet (« j'arrose mes salades tous les matins »), pas des gestes notés ;
- « rappelle-moi quel a été mon objectif cette année » → « 400 kg », l'objectif **2027**, avec une proposition de l'écrire ;
- « c'est quoi la dernière action notée » → une action qui n'est pas la plus récente, sur les trois modèles ;
- registre gouailleur : « Ah, merde, j'ai cru que t'avais déjà tout noté ! ».

**Critères d'acceptance :**
- [ ] CA1 — La partie variable sépare trois blocs balisés : les **habitudes** du carnet (« ce que le jardinier fait d'habitude, jamais un geste daté »), les **objectifs** avec leur saison ou leur année, et les **gestes notés** avec leur date.
- [ ] CA2 — Le prompt du mode `prioritaire` dit qu'une habitude ne se présente jamais comme un geste fait. Un texte qui affirme un geste daté (« ce matin », « hier », « aujourd'hui tu as… ») absent des gestes relus est renvoyé une fois au modèle, puis remplacé par le texte du code.
- [ ] CA3 — Les actions menées données au modèle (A1…A5) sont vérifiées : A1 est la plus récente, et « la dernière action notée » la désigne. La cause de l'écart mesuré est écrite dans la livraison.
- [ ] CA4 — Registre : une liste fermée de grossièretés (« merde », « putain », « con »…) est interdite dans tous les registres, gouailleur compris. Un texte qui en contient est réécrit une fois, puis remplacé par le gabarit du code.
- [ ] CA5 — Remesure sur Small 4, avec accord et en un seul passage : TER-02, TER-09, TER-15 et TER-31 sont justes sur le texte attendu (US-280 / CA6) ; le corpus gagne un tour gouailleur.
- [ ] CA6 — La table de `data/connaissance/doc_app/README.md` est relue et les fiches touchées sont corrigées (`compagnon-reponses-et-memoire.md` si le carnet y est décrit). `pytest tests/test_us099_corpus_fonctionnement.py` reste vert.
- [ ] CA7 — Tests sans modèle : habitude citée sans date, geste inventé refusé, objectif daté, grossièreté remplacée.

**Hors périmètre :**
- Le profil d'échange lui-même (US-258) et le carnet (US-265) : leur stockage ne change pas, seule leur présentation au modèle change.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : agent interpréteur (contexte, contrôle du texte)
- Migration BDD requise : non
- Dépendances : US-280 ; US-258, US-261, US-265
- Code concerné : `app/services/agent/interpreteur_agent.py` (`prompt_variable`, `bloc_actions`), `app/services/profil_echange.py` (`bloc_prompt`), `app/services/agent/savoir.py` (`controler`)
- Production conseillée : **Sonnet 5.5, effort `medium`**

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given le carnet dit "j'arrose mes salades tous les matins"
And aucun geste n'est noté aujourd'hui
When le jardinier écrit "liste tout ce que j'ai fait aujourd'hui"
Then la réponse dit qu'aucun geste n'est noté aujourd'hui
And elle ne dit pas "tu as arrosé tes salades ce matin"
```

**Labels GitHub :** `us`, `agent-interpreteur`, `compagnon`, `registre`

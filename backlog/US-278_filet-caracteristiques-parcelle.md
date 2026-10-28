**ID :** US-278
**Titre :** Proposer les caractéristiques d'une parcelle dictées quand l'agent ne propose rien
**Épic :** ÉPIC 13 — Agent interpréteur *(numéro à valider, voir `docs/EPIC - AGENT INTERPRETEUR/ARCHITECTURE_AGENT_INTERPRETEUR.md`)*

**Story :**
En tant que jardinier
Je veux que la superficie, la longueur, les rangs ou l'ensoleillement que je dicte pour une planche me soient toujours proposés à enregistrer, même si j'ai mal dit son nom
Afin de ne jamais recevoir, à la place, la liste de mes parcelles ou un conseil sur les pommes de terre

**Contexte fonctionnel :**
Retours de terrain du 28/10/2026 sur Telegram (Ministral 3B, potager de recette), après livraison d'US-257. Le principe du §4.5 du cadrage `docs/EPIC - COMPAGNON CONVERSATIONNEL/CADRAGE_COMPAGNON_ACTIF.md` s'applique : quand une tâche dépasse le petit modèle, le code la prend en charge avant de chercher un modèle plus gros. Le tableau du §4.5 ne prévoyait pas ce cas.

La même phrase, dite pour quatre parcelles, donne quatre résultats :

| Phrase du jardinier | Ce que le bot a fait |
|---|---|
| « ma planche principal a une superficie de 50m2, longueur de 7m et disposera de 10 rangs » | Proposition correcte, après deux correctifs du jour (voir plus bas) |
| « ma planche test a une superficie de 10 m2, longueur de 1m et ensoleillement mi-ombre » | Proposition **sans l'ensoleillement** : le modèle l'a oublié, et la relance ne contrôle que les nombres |
| « ma parcelle tunnel chauffé a une superficie de 20 m2, longueur de 7m et ensoleillement mi-ombre » | Le modèle appelle `afficher` (écarté une fois), décrit une proposition sans la faire, puis rappelle `afficher` deux fois : **la liste des parcelles** s'affiche |
| « ma planche tubercul a une superficie de 20 m2, longueur de 7m et ensoleillement mi-ombre » | Le modèle prend « tubercul » pour une culture : **réponse sur les pommes de terre**, aucune proposition |

Le nom de parcelle est bien dit dans trois cas sur quatre, et toutes les valeurs se lisent sans modèle. Le code n'agit pourtant qu'à travers les appels d'outil : quand le modèle n'appelle pas `modifier_parcelle`, il n'a aucun nom à rapprocher et aucune valeur à valider. La question « laquelle ? » (nom approchant proposé, `resolve_parcelle`) n'existe que dans le validateur.

**Correctifs déjà livrés le 28/10/2026 (retours US-257, hors de cette US) :**
- `afficher` est écarté une fois quand la phrase donne des nombres qu'aucun appel ne reprend ;
- `creer_parcelle` sur le nom exact d'une parcelle existante devient `modifier_parcelle`, et `actif=true` n'est plus un motif de rejet à la création ;
- un mot du nom d'une parcelle après « planche », « parcelle »… n'est plus pris pour un geste (« ma planche tunnel » nomme TUNNEL CHAUFFÉ) ;
- le récapitulatif ne rappelle plus les nombres en toutes lettres.

**Articulation avec US-277 :**
US-277 retire aux règles les phrases composées, que les règles déformaient, et les confie à l'agent. Cette US **ne revient pas sur ce choix** : les règles ne lisent toujours que les phrases simples, et l'agent passe toujours en premier sur une phrase composée. Le filet intervient **après** l'agent, uniquement quand celui-ci n'a rien proposé d'écrire. Ce n'est pas une règle de plus devant l'agent, c'est un repli derrière lui, comme le texte de repli d'INC-018. Il ne lit qu'une famille de phrases, celle des caractéristiques d'une parcelle existante, dont le vocabulaire est fermé (champs de la fiche, unités, liste d'ensoleillement), donc lisible sans déformer.

**Critères d'acceptance :**
- [ ] CA1 — Déclenchement : le filet ne s'applique que si les trois conditions sont réunies. (a) L'agent termine **sans proposition d'écriture** : texte seul, lecture, ou appels tous refusés. (b) La phrase **désigne une parcelle** : un nom exact du potager, ou un mot de parcelle (« planche », « parcelle », « carré », « butte », « bande ») suivi d'un nom. (c) La phrase donne **au moins une valeur de fiche** lisible (CA2). Dans tous les autres cas, rien ne change.
- [ ] CA2 — Valeurs lues sans modèle : superficie (« 20 m2 », « 20 m² », « 20 mètres carrés »), longueur (« 7 m », « 7 mètres », « 7 m de long »), nombre de rangs (« 10 rangs »), ensoleillement (la liste fermée de la fiche, `DEFINITIONS_ENSOLEILLEMENT` : « plein soleil », « mi-ombre »…), exposition (Sud, Est, Ouest, Nord). Les nombres sont acceptés en chiffres ou en lettres, comme au validateur. Aucune valeur n'est déduite : un mètre sans « carré » est une longueur, jamais une superficie. Si un nombre de la phrase n'est rattaché à aucun champ, la réponse le dit (« je n'ai pas su placer : 3 ») au lieu de l'ignorer.
- [ ] CA3 — Parcelle dite exactement : le jardinier reçoit la proposition `/parcelle modifier <parcelle> …` avec le récapitulatif habituel et les boutons ✅ Confirmer / ❌ Annuler. Rien n'est écrit avant sa confirmation.
- [ ] CA4 — Parcelle mal dite (« planche tubercul ») : le nom est rapproché par la recherche habituelle (`resolve_parcelle`) et **proposé**, jamais substitué (règle CA7 d'US-235). Le jardinier choisit au bouton « 📍 PLANT TUBERCULE », puis confirme la proposition complète, valeurs comprises.
- [ ] CA5 — Aucune parcelle trouvée : le bot demande « Quelle parcelle ? » avec les parcelles du potager en boutons. Au-delà de `NB_CHOIX_MAX` (6), il demande le nom. Les valeurs lues sont gardées : le choix mène à la proposition complète, sans rien redire.
- [ ] CA6 — Valeur oubliée par l'agent : quand l'agent propose bien une modification mais oublie une valeur de vocabulaire dite (« mi-ombre »), la relance d'US-257 la lui signale, comme un nombre non repris. Le code ne complète pas lui-même une proposition de l'agent : une proposition n'a qu'un auteur.
- [ ] CA7 — Ce que lit le jardinier : quand le filet propose, le texte de l'agent n'est pas affiché (il parlait de pommes de terre, ou annonçait une liste). Une phrase du code, sans modèle, le remplace (« Je te propose d'enregistrer ces caractéristiques : »). Le journal porte une ligne dédiée avec le motif (agent sans proposition, nom rapproché ou non trouvé).
- [ ] CA8 — Agent indisponible (`AGENT_MODE` à `off`, quota, panne) : le filet s'applique aussi. Une phrase de caractéristiques écartée par les règles (US-277 / CA6) reçoit sa proposition au lieu de « non traitée ».
- [ ] CA9 — Non-régressions, chacune couverte par un test : un geste (« semé 3 rangs de carottes sur la planche nord ») reste un geste ; une question (« quelle superficie fait la planche nord ? ») va à la cascade des questions ; une création (« crée la planche Est de 6 m ») n'est jamais transformée en modification, et un nom inconnu avec un verbe de création ne déclenche pas la question du CA5 ; une proposition faite par l'agent n'est jamais remplacée par le filet ; une phrase simple prise par les règles (« la planche nord a 5 rangs ») ne change pas.
- [ ] CA10 — Les quatre phrases du contexte entrent au corpus `tests/corpus/us256_dialogues.json`. Un rejeu `tools/evaluer_dialogues.py` sur Ministral 3B, **avec l'accord préalable du jardinier-développeur et en un seul passage au volume annoncé**, montre les quatre en proposition correcte. Le rapport est commité avec la livraison.
- [ ] CA11 — La fiche `data/connaissance/doc_app/compagnon-telegram.md` dit que des caractéristiques dictées pour une planche, même mal nommée, sont toujours proposées à enregistrer. `pytest tests/test_us099_corpus_fonctionnement.py` reste vert.

**Hors périmètre :**
- Le « oui » répondu à une question que le modèle pose en texte, sans proposition derrière : relève d'US-259 (conversation en base) et d'US-260 (confirmer par une phrase).
- La création d'une parcelle par le filet : une parcelle inconnue n'est jamais créée par le code, seulement demandée (CA5).
- Les autres familles de phrases (gestes, cultures, lots) : à ouvrir sur relevé de terrain, une famille par US.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram (compréhension des commandes, compagnon)
- Migration BDD requise : non
- Dépendances : US-257 (boucle et relances, retours du 28/10), US-276 (validateur, `_resoudre_entites`, `NB_CHOIX_MAX`), US-277 (articulation ci-dessus)
- Code concerné : `app/services/agent/interpreteur_agent.py` (fin de boucle), `app/services/agent/validation.py` (lecture des valeurs, relance étendue), `app/services/interpreteur_commandes.py` (repli sans agent), `app/bot/interpretation.py` (aucun changement attendu : boutons de choix et de confirmation existants)
- Production conseillée : **Opus 5.5, effort `high`**. Le code est court, mais il ajoute un chemin d'écriture proposée hors du modèle. Les non-régressions du CA9 sont le cœur du travail

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given le potager contient les parcelles "PRINCIPAL", "TUNNEL CHAUFFÉ" et "PLANT TUBERCULE"

When le jardinier écrit "ma parcelle tunnel chauffé a une superficie de 20 m2, longueur de 7m et ensoleillement mi-ombre"
And l'agent ne propose aucune écriture
Then le bot propose "/parcelle modifier TUNNEL CHAUFFÉ superficie=20 longueur=7 ensoleillement=mi-ombre"
And rien n'est écrit avant "Confirmer"

When le jardinier écrit "ma planche tubercul a une superficie de 20 m2, longueur de 7m et ensoleillement mi-ombre"
And l'agent répond en texte sur les pommes de terre
Then le bot ne montre pas ce texte
And il propose de choisir "PLANT TUBERCULE"
And le choix mène à la proposition complète, valeurs comprises

When le jardinier écrit "ma planche du fond a une superficie de 12 m2"
And aucune parcelle ne s'en approche
Then le bot demande "Quelle parcelle ?" avec les parcelles du potager en boutons

When le jardinier écrit "semé 3 rangs de carottes sur la planche principal"
Then le geste est enregistré comme avant, sans proposition de modification
```

**Labels GitHub :** `us`, `agent-interpreteur`, `compagnon`, `comprehension`

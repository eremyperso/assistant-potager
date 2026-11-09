**ID :** US-303
**Titre :** Résumer la réponse du compagnon pour l'oral
**Épic :** ÉPIC 17 — Compagnon vocal dans la PWA *(numéro à valider, voir `docs/EPIC 17 - COMPAGNON VOCAL PWA/ANALYSE_ET_SOLUTION_COMPAGNON_VOCAL.md`)*

**Story :**
En tant que jardinier qui écoute Gaston au potager
Je veux entendre une version courte et naturelle de sa réponse, pas la lecture d'un écran
Afin de comprendre l'essentiel en quelques secondes, le détail restant affiché

**Contexte fonctionnel :**
Décision D6 : un **résumé parlé court**, distinct du texte affiché, produit par un appel de type `oral` (variable `GROQ_MODEL_ORAL`, défaut : le modèle de l'agent). Il est calculé à la première demande de lecture puis gardé sur l'échange (étude §5.5). Le prompt de l'agent n'est pas modifié.

**Critères d'acceptance :**
- [ ] CA1 : La migration v72 ajoute `echanges_conversation.texte_oral` (texte, nul), avec son `rollback_v72.sql`.
- [ ] CA2 : Le service produit un résumé de 1 à 2 phrases, plafonné à `VOIX_ORAL_MAX_CARACTERES` (300 par défaut), à partir du **seul** `texte_compagnon` de l'échange ; il n'ajoute aucun fait, chiffre, date ou nom absent du texte.
- [ ] CA3 : Le résumé ne contient ni Markdown, ni émoji, ni URL, ni balise entre crochets ; les nombres et unités sont écrits pour être dits (« 2,5 kg » → « deux kilos et demi »).
- [ ] CA4 : Une réponse qui porte une carte de proposition se résume en « Je vous propose … : confirmez à l'écran » ; jamais « c'est enregistré » pour une proposition non confirmée.
- [ ] CA5 : Une réponse déjà courte (sous le plafond, sans Markdown) est reprise nettoyée, sans appel au modèle.
- [ ] CA6 : Modèle indisponible : le résumé est le texte affiché nettoyé, coupé à la dernière phrase complète sous le plafond ; l'issue est journalisée, aucune erreur n'est montrée.
- [ ] CA7 : Le résumé est calculé une seule fois par échange : une seconde lecture le reprend de `texte_oral` sans appel au modèle.
- [ ] CA8 : `/compagnon/messages` et `/compagnon/historique` exposent `echange_id` pour chaque réponse de Gaston ; un échange d'un autre jardinier ou d'un autre potager est introuvable (404).
- [ ] CA9 : L'appel `oral` passe par la passerelle (mesure, journal, mode dégradé) ; un jeu d'au moins dix réponses réelles du compagnon (anonymisées), dont des cartes, des questions et des réponses longues de support, vérifie CA2 à CA4 avec un modèle simulé.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse (service compagnon)
- Migration BDD requise : oui (v72, `echanges_conversation.texte_oral`)
- Dépendances : US-299
- Décisions liées : D6
- Fiche du corpus : `compagnon-vocal-pwa.md` (ce qui est lu à voix haute et pourquoi c'est plus court)

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given Gaston a répondu "## Arrosage des tomates\nArrosez **au pied**, 2 à 3 litres par pied, le matin. Évitez le feuillage pour limiter le mildiou. 🍅"
When la lecture de cet échange est demandée pour la première fois
Then le résumé parlé ressemble à "Arrosez vos tomates au pied le matin, deux à trois litres par pied, sans mouiller les feuilles."
And il est gardé dans texte_oral
When la lecture est demandée une seconde fois
Then aucun appel au modèle n'est fait
```

**Labels GitHub :** `us`, `voix`, `compagnon`, `migration`

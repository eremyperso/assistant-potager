**ID :** US-236
**Titre :** Aiguiller une phrase qui n'est pas une commande : question, précision ou hors périmètre
**Épic :** ÉPIC 13 — Agent interpréteur *(numéro à valider, voir `docs/EPIC - AGENT INTERPRETEUR/ARCHITECTURE_AGENT_INTERPRETEUR.md`)*

**Story :**
En tant que jardinier
Je veux que le bot reconnaisse quand ma phrase est une question, quand il lui manque une information, ou quand il ne sait pas faire ce que je demande
Afin d'obtenir une réponse juste, une question ciblée ou un « je ne sais pas encore faire ça », plutôt qu'une liste sans rapport déclenchée par un mot-clé

**Contexte fonctionnel :**
Phase 3 de l'architecture (§3.3, outils terminaux ; §3.6, `Aiguillage`). Avec US-235, l'agent propose une commande ou ne dit rien. Il peut désormais dire **où va** la phrase : vers la cascade des questions (avec sa nature), vers le parseur de gestes, vers une question au jardinier, ou vers un refus expliqué.

Un mot du domaine (« pépinière », « rendement ») ne suffit plus à décider qu'une phrase est une consultation : c'est la structure de la phrase qui décide.

**Critères d'acceptance :**
- [ ] CA1 : L'agent choisit toujours un outil, terminal ou non ; il ne répond jamais en texte libre à cet étage
- [ ] CA2 : Une question rend la main à la cascade des questions existante avec sa nature (données, savoir, hybride), sans repasser par la classification par mots-clés
- [ ] CA3 : Un geste rend la main au parseur de gestes, inchangé
- [ ] CA4 : Une demande incomplète ou ambiguë (« modifie ma serre », « supprime la parcelle près des tomates ») donne une question ciblée au jardinier ; rien n'est proposé ni exécuté. Une commande n'est jamais complétée par supposition
- [ ] CA5 : Une demande hors catalogue (« exporte l'historique en Excel ») donne « Je ne sais pas encore faire ça », avec la raison ; la phrase est journalisée comme demande de fonctionnalité
- [ ] CA6 : Les paires piégeuses vont chacune au bon endroit : « la serre est une pépinière » (commande) / « la serre est-elle une pépinière ? » (question) ; « la serre n'est plus une pépinière » (commande) / « quelles sont mes pépinières ? » (question)
- [ ] CA7 : Une demande de procédure (« comment supprimer une parcelle ? ») continue d'être captée **avant** l'agent, sans appel au modèle
- [ ] CA8 : Les mots-clés de données du routeur restent actifs pour les phrases que l'agent n'a pas prises en charge (`AGENT_MODE` ≠ `actif`, modèle indisponible)
- [ ] CA9 : L'ordre des étages (gardes de conversation, règles, filtres sans modèle, agent, routeur, cascade) est couvert par un test

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram, analyse
- Migration BDD requise : non
- Dépendances : US-235
- Corpus : `data/connaissance/doc_app/compagnon-telegram.md` (ce que le compagnon répond quand il ne sait pas faire, ou quand il lui manque une précision)

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given AGENT_MODE vaut actif
When je dis "Exporte-moi tout l'historique en Excel"
Then le bot répond qu'il ne sait pas encore exporter vers Excel
And aucune liste d'événements n'est affichée
When je dis "Modifie ma serre"
Then le bot me demande ce que je veux modifier sur "Serre extérieure"
And rien n'est proposé à la confirmation
```

**Labels GitHub :** `us`, `agent-interpreteur`, `bot`, `llm`

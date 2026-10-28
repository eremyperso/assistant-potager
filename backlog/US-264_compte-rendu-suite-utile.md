**ID :** US-264
**Titre :** Rendre compte du résultat réel et proposer la suite utile
**Épic :** ÉPIC 13 — Agent interpréteur *(numéro à valider, voir `docs/EPIC - AGENT INTERPRETEUR/ARCHITECTURE_AGENT_INTERPRETEUR.md`)*

**Story :**
En tant que jardinier
Je veux qu'après une confirmation le compagnon me dise ce qui a vraiment été fait, et m'indique l'étape suivante qui a du sens
Afin de savoir où j'en suis et de ne pas laisser mon potager à moitié renseigné

**Contexte fonctionnel :**
Lot 3 du cadrage (§1.5), étape 5 du §12.11, arbitrage B7. **Absorbe US-252** (le récapitulatif dit ce qui est compris) et **US-253** (anticiper la suite d'une commande).

**Critères d'acceptance :**
- [ ] CA1 : Le compte rendu est rédigé par le modèle à partir des `ResultatEtape` ; si l'appel échoue ou cite un chiffre absent des résultats, le texte du code part à sa place.
- [ ] CA2 : Un échec partiel est dit clairement (étape faite / étape non faite, avec la raison).
- [ ] CA3 : Le récapitulatif avant confirmation reformule ce qui a été compris (CA d'US-252).
- [ ] CA4 : La suggestion de suite est **calculée sans modèle** (rotation via `FamilleBotanique`, caractéristique vide, dépendances avant suppression) ; le modèle ne fait que la dire.
- [ ] CA5 : Au plus une suggestion par compte rendu ; elle ouvre une proposition, jamais une exécution.
- [ ] CA6 : Ignorer la suggestion ne bloque rien.
- [ ] CA7 : La fiche de `data/connaissance/doc_app/` sur les commandes en une phrase est mise à jour.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram
- Migration BDD requise : non
- Dépendances : US-257 ; absorbe US-252 et US-253
- Production conseillée : **Sonnet 5.5, effort `medium`** — règles de suggestion déterministes et rédaction encadrée ; le repli sur le texte du code limite le risque.

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given la planche Nord a porté des courgettes cette année
When le jardinier confirme la récolte finale et la libération de la planche Nord
Then le compte rendu dit que la récolte est notée et la planche libérée
And propose une seule suite : un engrais vert, avec [Oui] [Plus tard]
```

**Labels GitHub :** `us`, `agent-interpreteur`, `compagnon`, `compte-rendu`

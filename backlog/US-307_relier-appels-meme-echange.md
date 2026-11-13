**ID :** US-307
**Titre :** Relier les appels d'un même échange, avec canal, version et unité
**Épic :** ÉPIC 18 — Pilotage LLM

**Story :**
En tant qu'administrateur de la plateforme
Je veux savoir quels appels ont servi à produire une même réponse, par quel canal, avec quelle version de l'application et dans quelle unité ils sont comptés
Afin de connaître le coût d'une interaction complète et de rattacher une dérive à une livraison

**Contexte fonctionnel :**
Décision D4. Un message au compagnon produit aujourd'hui 2 à 6 lignes indépendantes (boucle d'agent, classification, question, résumé oral, voix). `cumul_mesure_cascade` (US-097) additionne déjà les jetons d'une cascade sans les relier en base. Par ailleurs `tokens_in` porte des secondes pour `dictee` et des caractères pour `voix` (US-299) : seule la connaissance du type d'appel permet de ne pas les additionner à des jetons.

**Critères d'acceptance :**
- [ ] CA1 : La migration v74 ajoute à `conso_tokens` : `echange_ref` (texte, nul, indexé), `canal` (texte, non nul, valeurs `telegram` | `pwa` | `mcp` | `fond` | `outil` | `inconnu`), `version_app` (texte, nul), `unite` (texte, non nul, valeurs `jeton` | `seconde` | `caractere`), avec son `rollback_v74.sql`.
- [ ] CA2 : L'existant est rejoué : `unite` déduite du type d'appel (`dictee` → `seconde`, `voix` → `caractere`, sinon `jeton`), `canal` à `inconnu`, `echange_ref` et `version_app` nuls.
- [ ] CA3 : Un identifiant d'échange est créé à l'entrée de chaque interaction (message texte ou vocal du bot, `POST /compagnon/messages`, appel d'outil MCP, commande) et porté par le contexte ; toutes les lignes écrites pendant son traitement le partagent, y compris la transcription, le résumé oral et la synthèse vocale demandés ensuite pour la même réponse.
- [ ] CA4 : Un appel de fond ou d'outil sans interaction porte un identifiant propre à son exécution.
- [ ] CA5 : `version_app` reprend le contenu du fichier `VERSION` lu une fois au démarrage.
- [ ] CA6 : `unite` est fixée par la passerelle d'après le type d'appel, à un seul endroit ; un type d'appel ajouté sans unité déclarée fait échouer un test.
- [ ] CA7 : Lorsqu'un échange du compagnon est persisté (`echanges_conversation`), son identifiant permet de retrouver ses lignes de consommation, sans clé étrangère obligatoire.
- [ ] CA8 : Aucune signature de fonction métier n'est modifiée pour transporter ces valeurs (contexte uniquement).

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse (passerelle LLM, points d'entrée bot / API / MCP)
- Cadrage : `docs/EPIC 18 - PILOTAGE LLM/CADRAGE_PILOTAGE_LLM.md` (numéro d'épic à valider)
- Migration BDD requise : oui (v74, numéro à confirmer ; peut être fusionnée avec v73 si US-306 et US-307 sont livrées ensemble)
- Dépendances : US-306
- Décisions liées : D4
- Fiche de domaine : `docs/domaines/migrations.md`, `docs/domaines/commandes-bot.md`

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given un jardinier dicte "où en sont mes tomates ?" dans la PWA et demande la lecture de la réponse
When l'échange est terminé
Then les lignes dictee, agent, oral et voix portent le même echange_ref
And leur canal est "pwa" et leur version_app est celle du fichier VERSION
And la ligne dictee a l'unité "seconde", la ligne voix l'unité "caractere", les autres "jeton"
```

**Labels GitHub :** `us`, `llm`, `observabilite`, `migration`

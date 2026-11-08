**ID :** US-292
**Titre :** Enregistrer un geste depuis un assistant IA
**Épic :** ÉPIC 16 — Potager dans les assistants IA (MCP) *(numéro à valider, voir `docs/EPIC 16 - POTAGER DANS LES ASSISTANTS IA/ETUDE_MCP_POTAGER.md`)*

**Story :**
En tant que jardinier `editor` ou `owner` qui a autorisé l'écriture pour son assistant
Je veux dire à mon assistant ce que j'ai fait (semer, mettre en godet, planter, récolter, perdre, observer) et confirmer le récapitulatif qu'il me présente
Afin que mon carnet soit tenu à jour depuis l'outil que j'utilise déjà, avec les mêmes règles que dans Telegram et la PWA

**Contexte fonctionnel :**
Toute écriture passe par une **proposition** (mécanique d'US-259, US-260, US-272), sur un nouveau canal `mcp`. Outils : `proposer_geste`, `proposer_correction`, `confirmer_proposition`, `abandonner_proposition`. Le modèle du client structure la phrase ; le serveur valide, refuse ou demande, il ne devine jamais (étude §6).

**Critères d'acceptance :**
- [ ] CA1 : `proposer_geste` crée une proposition sans rien écrire au carnet, et rend son identifiant et un récapitulatif en clair (geste, culture, variété, parcelle ou lot, quantité et unité, date) qui dit **ce que devient le stock**.
- [ ] CA2 — **semis initial** : un semis en pleine terre d'une culture reproductive (ex. 40 graines de fèves) rend « chaque graine levée donnera un pied qui produira plusieurs récoltes » ; un semis d'une culture végétative crée un stock de pieds à récolter.
- [ ] CA3 — **première récolte** : une récolte d'une culture reproductive ne change pas le nombre de pieds actifs et ouvre le rendement cumulé de la saison ; une récolte d'une culture végétative retire du stock le nombre de pieds arrachés.
- [ ] CA4 — **N-ième récolte** : une nouvelle récolte reproductive s'ajoute au cumul de la saison (« cumul : 0,6 → 1,7 kg »), les pieds actifs restent inchangés ; elle n'est jamais traitée comme une perte de stock.
- [ ] CA5 — **fin de vie** : seule une `perte` (ou un arrachage explicite) réduit les pieds actifs d'une culture reproductive, avec sa cause si elle est dite.
- [ ] CA6 : Une parcelle inconnue n'est jamais créée par un geste : la réponse dit « introuvable » et nomme les parcelles proches ; aucune proposition n'est créée.
- [ ] CA7 : Un semis en pépinière sans quantité revient avec la question (correctif du 14/10/2026) ; une date future est refusée.
- [ ] CA8 : `confirmer_proposition` exécute par les services (jamais par un handler du bot), sort la proposition de l'attente de façon atomique ; une seconde confirmation, depuis MCP, la PWA ou Telegram, rend « Déjà confirmé depuis {canal} à {heure} » et n'écrit rien.
- [ ] CA9 : Une proposition créée par MCP apparaît aussi dans le panneau de la PWA et dans Telegram (D4, comme US-272) ; la première réponse l'emporte.
- [ ] CA10 : `confirmer_proposition` et `abandonner_proposition` portent l'indication « écriture » ; `confirmer_proposition` refuse une proposition destructrice (annulation d'un geste) et rend le lien vers la carte dans l'application (L7).
- [ ] CA11 : `proposer_correction` corrige un geste récent selon les règles d'US-262 (avant → après dans le récapitulatif, semis à suites refusé).
- [ ] CA12 : Le geste enregistré porte le canal `mcp` et le client (Claude, ChatGPT, Le Chat…) dans sa traçabilité ; il figure dans les « actions menées » d'US-261 pour être désigné ensuite depuis Telegram ou la PWA.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement (canal `mcp`)
- Migration BDD requise : oui, si le canal d'une proposition ou d'un geste est une liste fermée en base (ajout de `mcp`) ; sinon non
- Dépendances : US-290, US-259, US-260, US-261, US-262, US-272
- Décisions liées : D4 (trois fenêtres), D5 (pas d'annulation par MCP en v1)
- Fiche du corpus : `enregistrer-un-geste.md` et `compagnon-reponses-et-memoire.md` à compléter (US-099 / CA9)

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Given la planche est porte 37 pieds actifs de fèves (culture reproductive)
And un cumul de récolte de 0,6 kg cette saison
When le jardinier dit à son assistant "encore 1,1 kg de fèves"
Then l'assistant appelle proposer_geste(type="recolte", culture="fève", quantite=1.1, unite="kg")
And le récapitulatif indique "pieds actifs : 37 (inchangé), cumul saison : 1,7 kg"
When le jardinier confirme
Then la récolte est enregistrée une seule fois avec le canal "mcp"
And la carte de la proposition apparaît "✅ Confirmé" dans la PWA et dans Telegram
```

**Labels GitHub :** `us`, `mcp`, `enregistrement`, `cycle-de-vie`

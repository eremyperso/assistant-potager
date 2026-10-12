**ID :** US-234
**Titre :** Lier la confirmation d'une commande dictée à la proposition qu'elle valide
**Épic :** ÉPIC 13 — Agent interpréteur *(numéro à valider, voir `docs/EPIC - AGENT INTERPRETEUR/ARCHITECTURE_AGENT_INTERPRETEUR.md`)*

**Story :**
En tant que jardinier
Je veux que le bouton « Confirmer » exécute exactement la commande affichée au-dessus de lui, dans le potager où je l'ai dictée
Afin de ne jamais valider par erreur une autre demande que celle que je relis

**Contexte fonctionnel :**
Correctif d'US-172, indépendant de l'agent (arbitrage A7, §3.7 de l'architecture). Aujourd'hui, une seule proposition est gardée par jardinier, chaque nouvelle demande écrase la précédente, et le bouton ne dit pas à quelle proposition il répond. Conséquence : appuyer sur « Confirmer » sous un **ancien** message valide la demande **la plus récente**. Le potager non plus n'est pas retenu : après un changement de potager actif, la commande confirmée s'exécute dans le nouveau.

L'agent va multiplier les propositions ; le défaut doit être corrigé avant.

**Critères d'acceptance :**
- [ ] CA1 : Chaque proposition reçoit un identifiant court, repris par ses boutons (confirmer, annuler, choisir un nom voisin, choisir une valeur)
- [ ] CA2 : Un bouton dont l'identifiant n'est pas celui de la proposition en cours n'exécute rien et répond « Demande expirée, rien n'a été fait »
- [ ] CA3 : La proposition retient le potager actif au moment où elle est faite. Si le potager actif a changé au moment du clic, rien n'est exécuté et le message le dit
- [ ] CA4 : La proposition est retirée avant l'exécution : un double appui ou un message rejoué n'exécute pas deux fois
- [ ] CA5 : Ce qui s'exécute est la commande affichée, jamais une nouvelle interprétation de la phrase
- [ ] CA6 : Le délai d'expiration, les noms voisins (CA12 d'US-172) et la complétion d'un argument (CA13) se comportent comme avant — les tests d'US-172 restent verts
- [ ] CA7 : Le journal des commandes interprétées enregistre l'issue `abandonnee` pour une proposition remplacée ou refusée par CA2 / CA3

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram
- Migration BDD requise : non
- Dépendances : aucune — livrable immédiatement
- Corpus : `data/connaissance/doc_app/compagnon-telegram.md` si la fiche décrit la confirmation d'une phrase ; `docs/domaines/commandes-bot.md`

**Estimation :** 2 points

**Scénario Gherkin :**
```gherkin
Given j'ai dicté "supprime la parcelle test" et le bot m'a proposé de la supprimer
And j'ai ensuite dicté "crée la parcelle carré nord" et le bot me le propose
When j'appuie sur "Confirmer" sous la première proposition
Then rien n'est exécuté
And le bot répond "Demande expirée, rien n'a été fait"
And la parcelle "carré nord" n'est pas créée tant que je n'ai pas confirmé la seconde proposition
```

**Labels GitHub :** `us`, `agent-interpreteur`, `bot`, `correctif`

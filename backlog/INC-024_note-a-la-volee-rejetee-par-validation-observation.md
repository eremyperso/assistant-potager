**ID :** INC-024
**Titre :** « note que le sol est humide aujourd'hui » : la note à la volée est rejetée (« Observation sans culture ou date ») au lieu de créer une note
**Type :** Incident
**Priorité :** Majeur

**Signalé le :** 2026-11-05

**Reproduction (jeu de test réalisé) :**
Potager de recette (id 33), bot Telegram, mode agent d'abord (branche `agent-mode-prioritaire`), le 05/11/2026 à 18:00 :
1. Message libre « note que le sol est humide aujourd'hui ».
2. Le jardinier appuie ensuite sur « ❌ Annuler » (message `❌ Annuler` à 18:00:56, dix secondes après).

**Résultat obtenu :**
Le journal montre la chaîne suivante :
- l'agent choisit l'outil `saisir_geste` et délègue au parseur de gestes (`saisir_geste → parseur de gestes`) ;
- le parseur déterministe ne reconnaît aucun geste en tête de phrase (`repli modèle — aucun geste reconnu`), le modèle de parsing
  renvoie `action=observation`, `culture=null`, `commentaire="sol humide"`, `date=2026-11-05` ;
- la validation rejette l'item : `❌ VALIDATION US011: Observation sans culture ou date → hallucination Groq`.
La note n'est pas créée. La phrase du jardinier est traitée comme une observation de culture mal formée, puis rejetée
comme une « hallucination » du modèle alors que l'item est cohérent avec ce qui a été dit.
Le texte exact renvoyé par le bot au jardinier n'est pas dans le journal fourni ; le jardinier a répondu par « ❌ Annuler ».

**Résultat attendu (ou : ce qui ne devrait pas se produire) :**
Dire « note que le sol est humide aujourd'hui » doit créer une note à la volée (texte « le sol est humide », date du jour,
rattachée au potager, sans culture obligatoire), après le récapitulatif de confirmation habituel, sans passer par la saisie guidée
pas à pas et sans être rejeté comme une hallucination. La commande `/note` doit donc être atteignable par l'interpréteur
de commandes avec son contenu.

**Analyse grosse maille (premier niveau — pas un diagnostic) :**
- Zone(s) impactée(s) : Bot Telegram (saisie dictée, validation) ; API/Backend (déclaration des commandes dictables, couche agent).
- Nature probable : lacune de conception, à investiguer. Le menu des commandes déclare bien `/note`, mais seulement comme
  « Ouvrir la saisie guidée d'une note », sans argument et sans confirmation (`FormeCommande("note", None, …)`) : elle ne porte pas le
  contenu de la note. Faute de forme de commande « note avec texte », la phrase part vers le geste `saisir_geste` et le parseur, où
  une observation sans culture est invalidée par la règle US-011 (anti-hallucination).
- Fichiers probablement concernés : `app/services/menu_commandes.py` (forme `note`, arguments), `utils/validation.py`
  (règle « Observation sans culture ou date »), `app/bot/saisie.py` (rejet US011 et reroutage), `app/bot/notes.py` (flux de note),
  `app/services/agent/catalogue_outils.py` (choix de `saisir_geste` pour une note).
- Corpus de connaissance concerné : oui, probablement — si la commande `/note` ou la dictée d'une note change, relire la fiche
  `data/connaissance/doc_app/` qui décrit la saisie de notes, l'aide `/help`, le guide utilisateur et `SETUP`
  (voir CLAUDE.md, section « Corpus de connaissance »).
- Famille voisine : INC-023 (une action existe comme flux dédié mais pas comme commande dictable avec ses arguments).

**Labels :** incident, agent, bot-telegram, notes, commandes

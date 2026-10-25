**ID :** INC-018
**Titre :** Dictée « crée la planche Nord… et mets la serre en pépinière froide » : rien n'est créé, le bot répond par le contenu de la pépinière
**Type :** Incident
**Priorité :** Majeur

**Signalé le :** 2026-10-23

**Reproduction (jeu de test réalisé) :**
Message vocal Telegram, potager 33, transcrit « Créez la planche Nord de 8 mètres de long avec 4 rangs et mets la serre en pépinière froide. » (phrase de référence de US-237, deux commandes en une phrase : `/parcelle ajouter` puis `/parcelle modifier`).

**Résultat obtenu :**
- L'appel de l'agent échoue tout de suite : `LLM agent … in=0 out=0 … issue=erreur (appel_invalide)` puis `AGENT : appel_invalide → ancien chemin`.
- L'ancien chemin classe la phrase en `QUESTION_DATA` (routeur `origine=regle`, `confiance=1.00`), la traite comme une question (`_ask_question`) et le gabarit SQL `famille=pepiniere` répond « Ta pépinière contient 2 lot(s) de semis : courgette…, tomate jaune… ».
- Aucune planche « Nord » n'est créée, la serre n'est pas modifiée, aucun message ne dit que la demande n'a pas été comprise.

**Résultat attendu (ou : ce qui ne devrait pas se produire) :**
Une phrase impérative de création/modification ne doit jamais être traitée comme une question de consultation. Attendu : un plan de deux étapes à confirmer (US-237), ou à défaut une proposition de commande `/parcelle ajouter` pour la planche Nord. En dernier recours, un message disant que la demande n'a pas été comprise, pas une réponse hors sujet.

**Analyse grosse maille (premier niveau — pas un diagnostic) :**
- Zone(s) impactée(s) : Bot Telegram (voix → routage), API/Backend (agent interpréteur, routeur règles-first, gabarits de questions chiffrées).
- Nature probable : deux défauts cumulés, à investiguer :
  1. l'appel agent est rejeté comme malformé (`in=0 out=0`, modèle `openai/gpt-oss-120b`) — cause inconnue, éventuellement liée à la définition des outils ou à la limite de débit (8000 jetons/min, ~3000 restants) ;
  2. le repli sur l'ancien chemin laisse une phrase impérative partir en `QUESTION_DATA` avec confiance 1.00, le seul mot « pépinière » suffisant à déclencher le gabarit `pepiniere`.
- Fichiers probablement concernés : `app/services/agent/interpreteur_agent.py`, `llm/passerelle.py` (statut `appel_invalide`), `llm/routeur.py`, `app/services/reponses_chiffrees.py` (reconnaissance du gabarit), `app/bot/interpretation.py`. La livraison d'US-237 (plan multi-commandes) est à vérifier : l'incident peut en être la conséquence ou la précéder.
- Corpus de connaissance concerné : probablement non (comportement de routage). Si le correctif change ce que le bot répond à plusieurs demandes en une phrase, relire `data/connaissance/doc_app/compagnon-telegram.md`.

**Labels :** incident, bot, llm

## Diagnostic (23/10/2026, vérifié sur Groq `openai/gpt-oss-120b`)

1. **Cause racine** : le schéma généré n'acceptait pas `null` dans les champs facultatifs typés (`number`, `integer`, `boolean`, et les listes fermées) — 8 outils sur 14. Le modèle envoie `null` pour ce qu'il ne renseigne pas ; le serveur valide l'appel contre le schéma et répond 400 `tool_use_failed` ; la passerelle jetait `failed_generation` et rendait `appel_invalide`.
2. `proposer()` rendait `disponible=False` → repli CA13 : ancien chemin, puis routeur par mots-clés → `QUESTION_DATA` (confiance 1,00) → gabarit `pepiniere`. Un schéma qui accepte `null` supprime le rejet (vérifié).
3. Défauts restants une fois le rejet levé :
   - l'exposition déduite du nom (« Nord ») : la description du champ était celle d'un nom (`TYPE_NOM_LIBRE`) ;
   - précisions inutiles (« Quelle exposition ? ») : les descriptions des champs étaient les **questions** du catalogue (`Argument.question`) ; et même corrigées, `crée la planche Est` demandait encore une exposition (7 appels sur 12 créaient la parcelle) tant que les champs facultatifs n'étaient pas annoncés tels ;
   - une seule action extraite d'une phrase qui en contient deux : le modèle n'émet qu'un appel d'écriture par réponse, et la boucle se clôt sur un tour sans `lire` (→ US-250, non traité ici).

## Correctifs (non commités)

- `catalogue_outils._facultative` : tout champ non `required` accepte `null` (`type: [t, "null"]`, `None` ajouté aux `enum`). Le validateur traitait déjà `null` comme « non dit ».
- `Argument.description` (`menu_commandes.py`) : ce que le CHAMP désigne, distinct de `question` ; la description du schéma n'est plus jamais une question. Les champs facultatifs d'une forme sont annoncés `FACULTATIF.` (si toutes les formes qui portent le champ le disent tel).
- `llm.passerelle` : la génération rejetée (`failed_generation`, tronquée à 600 car.) est journalisée en WARNING ; le statut `appel_invalide` ne change pas.
- `interpreteur_commandes.interpreter` : en `AGENT_MODE=actif`, une phrase qui demande d'agir (`demande_d_agir`) et que ni l'agent ni l'ancien repli n'ont traitée reçoit `Aiguillage(vers='non_compris')` : message explicite + commande à taper, jamais le routeur. Les règles, le parseur de gestes et `/ask` sont inchangés ; `off` et `ombre` aussi.
- `tools/evaluer_agent.py` : mesure le `PROMPT_FIXE` et `catalogue_outils.schemas()` livrés, en rejouant la boucle de l'agent (lecture fictive) ; corpus enrichi (créations, deux actions, conseils, doutes) ; critères C11 (0 `appel_invalide`), C12 (0 champ inventé), C13 (précisions inutiles).
- `AGENT_MODE=ombre` remis dans `.env.dev` en attendant l'accord sur le rapport de mesure.
- Fiches : `compagnon-telegram.md`, `docs/domaines/commandes-bot.md` (US-099 / CA9 verte).

## Complément du 24/10/2026 — seconde demande perdue en mode `actif`

Dictée « peux tu créer la planche nord de 20m2 et de longueur 2 m » : l'agent ne rend que `/parcelle ajouter planche nord 20` ; la longueur disparaît sans un mot (une seule écriture émise, boucle close). Correctif : `validation.chiffres_non_repris` + un tour de complément dans `interpreteur_agent.proposer` ; vérifié sur le vrai modèle : plan `/parcelle ajouter planche nord 20` puis `/parcelle modifier planche nord longueur=2`. Limite connue : une seconde demande sans nombre n'est pas détectée (US-250).

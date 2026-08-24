**ID :** US-093
**Titre :** Router les demandes par des règles avant tout appel au LLM
**Épic :** ÉPIC 3 — Fiabilité & coût

**Story :**
En tant que jardinier
Je veux que mes demandes les plus courantes soient comprises et aiguillées sans attendre l'IA
Afin d'obtenir une réponse immédiate, et de ne pas rester sans réponse quand ma question a été mal orientée

**Contexte fonctionnel :**
Deuxième US issue de `docs/ARCHITECTURE_CIBLE_V2_reponses.md` (§2.1). Le routeur est l'aiguillage de
toute la cascade : il décide si une demande est une **action**, une **question sur les données**, une
**question de savoir** ou une **question hybride**. C'est aussi, de l'aveu même du document
d'architecture et de la revue qui l'accompagne, **le maillon faible** : un mauvais aiguillage envoie
une question de savoir vers l'agrégation SQL, qui répond à côté.

Deux corrections sont apportées ici au cadrage initial, toutes deux issues de la revue critique :

1. **Un routeur qui appellerait le LLM à chaque message contredirait son propre objectif.** À une
   centaine de jetons par classification et une dizaine de demandes par jour et par jardinier, le
   routage consommerait à lui seul l'essentiel du budget économisé par la cascade. Les règles
   passent donc **avant** le modèle, et le résultat est mémorisé.
2. **La cascade doit pouvoir remonter.** Une cascade purement descendante qui répond « je ne sais
   pas » dès que l'étage choisi est vide produit de la frustration. Un étage qui échoue rend la main
   à l'étage suivant, une fois.

**Critères d'acceptance :**

*Aiguillage*
- [ ] CA1 : Le routeur classe chaque demande entrante en quatre natures : `ACTION` (saisie ou commande), `QUESTION_DATA` (les données du potager), `QUESTION_SAVOIR` (agronomie ou fonctionnement de l'application), `QUESTION_HYBRIDE` (les deux)
- [ ] CA2 : **Les règles d'abord** : les commandes préfixées, et les formes fréquentes et non ambiguës reconnues par motifs (« combien de… », « quand ai-je… », « il me reste… », « stock… », « pourquoi mes… », « comment… ») sont aiguillées **sans aucun appel au modèle**
- [ ] CA3 : Le résultat de classification est mis en cache sur la question normalisée (minuscules, sans accents, sans ponctuation) avec une durée de validité de 24 h : une phrase déjà classée n'est jamais reclassée
- [ ] CA4 : Le modèle n'est sollicité que si les règles **et** le cache échouent. L'appel part alors sur le petit modèle rapide via la passerelle (US-092 / CA3), et son résultat alimente le cache
- [ ] CA5 : Si la classification par le petit modèle revient avec une confiance faible, la demande est traitée comme `QUESTION_HYBRIDE` — l'étage le plus tolérant — plutôt que d'être forcée dans un étage étroit. On préfère une réponse un peu plus chère à une non-réponse

*Remontée de cascade*
- [ ] CA6 : Un étage qui ne produit pas de réponse de confiance suffisante **rend la main à l'étage suivant** au lieu de conclure. En particulier : une `QUESTION_DATA` dont l'agrégation SQL ne renvoie rien d'exploitable est re-routée vers le savoir, puis vers le raisonnement
- [ ] CA7 : La remontée est **limitée à un saut** et journalisée : sans plafond, une question mal formée déclencherait toute la cascade et coûterait plus cher qu'un appel direct
- [ ] CA8 : Une remontée n'est jamais visible du jardinier autrement que par une réponse pertinente : aucun message intermédiaire du type « je cherche ailleurs »

*Justesse et mesure*
- [ ] CA9 : Un **corpus de routage** d'au moins 100 questions réelles, extraites des saisies existantes (`texte_original`) et des questions déjà posées en mode `ask`, est constitué avec l'étage attendu pour chacune. Le taux de bon aiguillage est mesuré, et **une mise en production sans cette mesure est refusée** — c'est l'hypothèse la plus structurante de toute l'architecture
- [ ] CA10 : Le seuil d'acceptation est fixé à **90 % de bon aiguillage** sur ce corpus, et la répartition réelle par étage est publiée (elle valide ou invalide les hypothèses 40 % / 35 % / 20 % / 5 % du document d'architecture)
- [ ] CA11 : Chaque décision de routage est journalisée avec sa nature détectée, son origine (règle, cache, modèle), sa confiance et sa latence — matière première de l'US-097
- [ ] CA12 : Le coût moyen par demande est recalculé **routage inclus** : l'estimation de ~180 jetons par question du document d'architecture omet le coût du routage lui-même et doit être corrigée à la livraison

*Non-régression des flux*
- [ ] CA13 : L'ordre critique des flux de conversation est préservé : modes de correction `corr_*` > mode `ask` > navigation > détection de question > action. Le routeur s'insère **après** ces gardes, jamais avant, et l'US documente explicitement ses effets de bord sur les états de conversation
- [ ] CA14 : Le basculement de la classification d'intention vers le petit modèle est validé par une mesure du taux d'erreur avant / après sur le corpus du CA9 ; en cas de dégradation, le repli sur le grand modèle reste possible par configuration (US-092 / CA3), sans livraison

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram | analyse
- Migration BDD requise : **non**
- **Arbitrage tranché — où vit le cache de classification :** en mémoire du processus (cache borné, éviction par ancienneté), **pas** en base ni en Redis. Redis relève de l'US d'état conversationnel persistant (US-120 du plan initial), non livrée ; et une classification est peu coûteuse à reconstruire après un redémarrage. Le passage à Redis se fera sans changement de contrat le jour où cette US-là arrivera
- **Arbitrage tranché — le doute profite à la réponse, pas à l'économie :** confiance faible ⇒ étage hybride (CA5), et non « on tente quand même l'étage le moins cher ». Une non-réponse coûte plus cher en confiance qu'un appel LLM en jetons
- **Arbitrage tranché — pas de reformulation automatique de la question :** les techniques de multi-interrogation ou de reformulation par le modèle sont écartées à ce stade. Elles ajoutent un appel LLM systématique, exactement ce que cette US supprime
- Dépendances : **US-092** (passerelle, bloquante). Alimente **US-095**, **US-096**, **US-098**
- Invariants projet : prompts en `.replace()` jamais `.format()` ; échappement Markdown conservé dans toute nouvelle sortie du bot

**Notes techniques (pour Persona Developer) :**
- Le routeur est un **enrichissement de la classification d'intention existante**, pas un composant nouveau : il ajoute la distinction data / savoir / hybride au-dessus de ce qui distingue déjà action et question
- La normalisation de la question réutilise celle déjà en place pour les noms de parcelles et de cultures — pas de seconde règle de normalisation dans le projet
- La remontée de cascade (CA6) doit être implémentée comme une valeur de retour explicite des étages (« je n'ai pas su »), jamais comme une exception ni comme une réponse vide interprétée à distance
- Le corpus du CA9 est un livrable versionné dans les tests, pas un tableur : il doit tourner en intégration continue et se remplir au fil des retours 👎 collectés par US-097

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Question courante aiguillée sans IA
  Given un jardinier qui demande "il me reste combien de tomates ?"
  When le routeur traite la demande
  Then elle est classée comme question sur les données par une règle
  And aucun appel au modèle n'a lieu

Scénario: Question déjà vue servie depuis le cache de classification
  Given une question déjà classée il y a une heure
  When la même question est reposée
  Then la nature est retrouvée en cache
  And aucun appel au modèle n'a lieu

Scénario: Question ambiguë classée par le petit modèle
  Given une question formulée de façon inhabituelle
  When ni les règles ni le cache ne savent la classer
  Then le petit modèle est appelé via la passerelle
  And la classification obtenue est mémorisée pour les prochaines fois

Scénario: Remontée de cascade sur donnée absente
  Given un jardinier qui demande "combien de physalis ai-je récolté ?"
  And aucun événement de récolte de physalis n'existe dans son potager
  When l'étage des données ne produit rien d'exploitable
  Then la demande est re-routée vers le savoir puis le raisonnement
  And le jardinier reçoit une réponse utile plutôt qu'un "je ne sais pas"

Scénario: Une seule remontée par demande
  Given une demande qu'aucun étage ne sait traiter
  When la cascade a déjà remonté une fois
  Then aucune nouvelle remontée n'est tentée
  And la réponse d'échec est explicite et journalisée

Scénario: Ordre des flux de conversation préservé
  Given un jardinier en cours de correction d'un événement
  When il envoie un message qui ressemble à une question
  Then le mode correction reste prioritaire
  And le routeur n'intercepte pas le message
```

**Labels GitHub :** `us`, `sprint-fiabilite-cout`, `llm`, `telegram`, `observabilite`

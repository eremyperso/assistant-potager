**ID :** US-097
**Titre :** Mesurer la cascade de réponses et recueillir l'avis du jardinier
**Épic :** ÉPIC 3 — Fiabilité & coût

**Story :**
En tant qu'administrateur de la plateforme
Je veux savoir quel étage répond à quoi, à quel coût, en combien de temps, et ce que le jardinier a pensé de la réponse
Afin de piloter l'architecture sur des mesures plutôt que sur des hypothèses, et de corriger les mauvaises réponses au lieu de les ignorer

**Contexte fonctionnel :**
Sixième US issue de `docs/ARCHITECTURE_CIBLE_V2_reponses.md` — elle répond à deux manques signalés
par la revue critique : **aucune observabilité de la cascade** et **aucune boucle de retour
utilisateur**.

Tout le dimensionnement de l'architecture cible repose sur quatre hypothèses explicitement marquées
comme à valider : ~40 % des questions résolues par commande ou cache, ~35 % par agrégation SQL,
~20 % par le savoir, ~5 % par le raisonnement. **Sans mesure, ces chiffres resteront des
convictions**, et le coût moyen visé de ~180 jetons par question ne pourra ni être vérifié ni être
corrigé — d'autant qu'il omet, dans le document source, le coût du routage lui-même.

Cette US est délibérément placée **tôt** dans la séquence, et non « plus tard quand on aura le
temps » : elle est ce qui permet de savoir si les cinq US précédentes ont produit l'effet attendu.
Elle ne consomme aucun jeton.

**Critères d'acceptance :**

*Journal de routage*
- [ ] CA1 : Une table `routage_logs` enregistre, pour chaque demande : horodatage, `potager_id`, question normalisée, nature détectée, origine de la classification (règle, cache, modèle), étage ayant finalement répondu, indicateur de remontée de cascade, confiance, latence en millisecondes, jetons consommés
- [ ] CA2 : Le journal enregistre la question **normalisée**, pas le message brut : c'est ce qui sert à construire le corpus de routage, sans conserver de verbatim inutile
- [ ] CA3 : La rétention est bornée à 12 mois et documentée, en cohérence avec les traitements RGPD à venir (US-132 du plan initial). Les entrées d'un potager supprimé disparaissent avec lui, au même titre que ses données (US-084)
- [ ] CA4 : Aucun secret, aucune clé, aucun contenu de fragment de connaissance n'est écrit dans ce journal

*Métriques*
- [ ] CA5 : Les indicateurs suivants sont calculables et consultables : taux de résolution **par étage**, latence p95 par étage, jetons moyens par question **routage inclus**, taux de remontée de cascade, taux de service depuis le cache, part des saisies traitées par le parseur déterministe
- [ ] CA6 : La répartition réelle par étage est confrontée aux hypothèses 40 / 35 / 20 / 5 du document d'architecture ; l'écart est publié tel quel. Une hypothèse invalidée est corrigée dans le document, pas contournée
- [ ] CA7 : La consultation se fait par un point d'accès en lecture seule réservé au compte administrateur de la plateforme (identifiant en variable d'environnement). Aucun tableau de bord graphique n'est attendu à ce stade
- [ ] CA8 : L'ensemble du dispositif consomme **zéro jeton** : aucune métrique n'est calculée par un modèle

*Retour du jardinier*
- [ ] CA9 : Toute réponse issue du savoir ou du raisonnement (étages 2 et 3) propose un retour 👍 / 👎 — boutons en ligne côté Telegram, contrôle discret côté application web
- [ ] CA10 : Le retour est rattaché à l'entrée de journal correspondante, ce qui permet de relier un avis négatif à l'étage, à la confiance et aux sources qui ont produit la réponse
- [ ] CA11 : Donner un avis est facultatif, ne bloque rien, et n'est jamais redemandé pour la même réponse
- [ ] CA12 : Une liste des questions les plus souvent jugées mauvaises est consultable : c'est elle qui alimente le corpus de routage (US-093 / CA9) et la liste des lacunes de la base de connaissance
- [ ] CA13 : Un 👎 ne déclenche **aucune** relance automatique vers un modèle plus gros : recevoir un avis négatif n'est pas une invitation à dépenser davantage, c'est une information de pilotage

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : transverse — interaction Telegram, consultation web, exploitation
- Migration BDD requise : **oui** — création de `routage_logs` et de la table de retours (⚠️ vérifier le numéro de la dernière migration au moment de l'implémentation), idempotente, rollback documenté
- **Arbitrage tranché — mesurer avant d'optimiser :** cette US est livrée **avec** ou **immédiatement après** le routeur (US-093), jamais après le RAG. Livrer le socle de connaissance sans savoir quelle part des questions relève réellement du savoir reviendrait à investir à l'aveugle dans la partie la plus coûteuse en contenu
- **Arbitrage tranché — pas de tableau de bord graphique :** un point d'accès en lecture et des requêtes documentées suffisent. L'écran viendra si, et seulement si, ces chiffres sont consultés régulièrement
- **Arbitrage tranché — le retour utilisateur n'est pas une note de satisfaction :** on ne mesure pas le contentement, on cherche les réponses fausses. Le libellé et le placement doivent le refléter, sans transformer chaque échange en sondage
- Dépendances : **US-092** (mesure des jetons), **US-093** (décisions de routage à journaliser). Alimente **US-093 / CA9** (corpus), **US-095 / CA12**, **US-098 / CA11**, **US-140 / CA7**
- Invariants projet : isolation inter-potagers ; journalisation structurée `HH:MM:SS │ LEVEL │ emoji` conservée ; échappement Markdown dans les nouvelles sorties du bot (boutons compris)

**Notes techniques (pour Persona Developer) :**
- L'écriture du journal ne doit jamais faire échouer une réponse : en cas d'erreur d'écriture, on journalise l'incident et on sert quand même la réponse
- L'écriture doit être hors du chemin critique de latence perçue, sans pour autant introduire d'infrastructure asynchrone nouvelle
- Les boutons de retour Telegram utilisent le mécanisme de rappel déjà en place dans le bot ; ne pas introduire un second mécanisme d'interaction
- Prévoir dès la conception que ce journal servira de base au calcul des quotas par potager (US-123 du plan initial) : ne pas concevoir une structure qui interdirait l'agrégation par potager et par jour

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Chaque demande laisse une trace exploitable
  Given un jardinier qui pose une question sur ses récoltes
  When la réponse lui est servie
  Then une entrée de journal existe avec l'étage résolveur, la latence et les jetons consommés

Scénario: Répartition réelle par étage
  Given un mois de questions journalisées
  When l'administrateur consulte les métriques
  Then la part des questions résolues par chaque étage est affichée
  And elle est comparée aux hypothèses du document d'architecture

Scénario: Coût moyen calculé routage inclus
  Given des questions ayant nécessité une classification par le modèle
  When le coût moyen par question est calculé
  Then les jetons du routage sont comptés dans le total

Scénario: Avis négatif sur une réponse de savoir
  Given une réponse issue de la base de connaissance
  When le jardinier appuie sur le pouce vers le bas
  Then l'avis est rattaché à l'entrée de journal de cette réponse
  And aucune nouvelle réponse n'est générée automatiquement

Scénario: Les mauvaises réponses nourrissent le corpus
  Given plusieurs avis négatifs sur des questions similaires
  When l'administrateur consulte la liste des réponses jugées mauvaises
  Then ces questions y figurent, prêtes à entrer dans le corpus de routage

Scénario: Suppression d'un potager
  Given un potager supprimé définitivement
  When la purge est exécutée
  Then ses entrées de journal de routage et ses avis sont supprimés
```

**Labels GitHub :** `us`, `sprint-fiabilite-cout`, `observabilite`, `qualite-donnee`, `telegram`

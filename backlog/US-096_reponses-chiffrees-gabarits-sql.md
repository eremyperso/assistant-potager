**ID :** US-096
**Titre :** Répondre aux questions chiffrées par des gabarits sur agrégats SQL
**Épic :** ÉPIC 3 — Fiabilité & coût

**Story :**
En tant que jardinier
Je veux que mes questions sur mes propres chiffres reçoivent une réponse exacte et immédiate
Afin d'obtenir un total juste plutôt qu'une reformulation approximative produite par une IA

**Contexte fonctionnel :**
Cinquième US issue de `docs/ARCHITECTURE_CIBLE_V2_reponses.md` (§3.3) — étage 1 de la cascade. Elle
prolonge **US-042** (livrée), qui a déjà scopé `repondre_question` par `potager_id`, fixé une fenêtre
de 12 mois, plafonné à 100 événements et fait passer le coût d'environ 5 000 à moins de 1 500 jetons
par question. Le pas suivant est de sortir complètement le modèle de la boucle sur les questions
purement chiffrées.

**Le principe est simple et non négociable : les questions sur les données se répondent en SQL,
jamais en recherche documentaire.** Les données sont structurées ; une agrégation donne une réponse
*exacte* là où le vectoriel donnerait une réponse *approximative*, plus lente et plus chère.

**Rappel du modèle de domaine, structurant pour les gabarits :** selon le type d'organe de récolte,
la même question n'a pas la même réponse.
- **Végétatif** — la récolte consomme le pied : « combien me reste-t-il de carottes ? » porte sur un
  stock de pieds qui diminue.
- **Reproducteur** — le pied reste en place : « combien de haricots ai-je récoltés ? » porte sur un
  **rendement cumulé de saison**, et le **nombre de pieds actifs** est une métrique **distincte**
  qui ne diminue qu'en cas de perte ou d'arrachage. Confondre les deux produirait une réponse
  absurde du type « il ne te reste plus de haricots » après une cueillette.

**Critères d'acceptance :**

*Catalogue de réponses chiffrées*
- [ ] CA1 : Un catalogue explicite de familles de questions est traité **sans aucun appel au modèle** : total récolté par culture et par période, dernière occurrence d'un type d'action, stock courant, nombre de pieds actifs, rendement cumulé de la saison, contenu de la pépinière, occupation d'une parcelle
- [ ] CA2 : Chaque famille dispose d'un gabarit de phrase en français, rempli avec le résultat de l'agrégation. La réponse est produite par le gabarit, pas par le modèle
- [ ] CA3 : Les gabarits respectent le type d'organe de récolte : rendement cumulé et pieds actifs sont présentés comme deux grandeurs distinctes pour les cultures reproductrices, et une cueillette n'est jamais présentée comme une diminution de stock
- [ ] CA4 : Les unités et arrondis sont cohérents avec ceux déjà affichés dans l'application web : le bot et la PWA ne doivent jamais annoncer deux chiffres différents pour la même réalité

*Quand le modèle intervient encore*
- [ ] CA5 : Si un habillage en langage naturel est réellement nécessaire (question chiffrée formulée de façon détournée), seul le **résumé chiffré déjà agrégé** est transmis, pour un contexte inférieur à 1 000 jetons. Aucune ligne d'événement brute n'est jamais envoyée au modèle
- [ ] CA6 : Le taux de questions de données traitées **sans** modèle est mesuré et publié (US-097) ; il est l'indicateur principal de succès de cette US

*Réponse vide, réponse honnête*
- [ ] CA7 : Un résultat vide n'est jamais présenté comme un zéro : « je n'ai aucune récolte de courgettes enregistrée cette année » et « tu as récolté 0 kg » sont deux réponses différentes, et la confusion entre les deux ferait douter le jardinier de son propre journal
- [ ] CA8 : Un résultat vide ou de confiance nulle rend la main à l'étage suivant de la cascade (US-093 / CA6) avant de conclure

*Sécurité de l'accès aux données — invariant*
- [ ] CA9 : Les agrégations sont exécutées à partir d'un **catalogue de requêtes prédéfinies et paramétrées**. Aucune requête SQL librement composée par un modèle n'est exécutée, jamais, sous aucune condition
- [ ] CA10 : L'accès utilisé pour ces agrégations est en **lecture seule** ; un délai maximal d'exécution est imposé à chaque requête
- [ ] CA11 : Le filtre `potager_id` est appliqué par construction et non par convention : une requête du catalogue qui ne le porte pas est refusée à l'exécution, pas seulement signalée en revue de code
- [ ] CA12 : Un test d'isolation dédié tente, par des questions formulées pour cela (« et dans les autres jardins ? », « compare avec le potager de X »), d'obtenir une donnée hors du potager courant, et échoue à en obtenir une seule

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse | consultation
- Migration BDD requise : **non** — au plus des index de couverture si la mesure de latence l'exige
- **Arbitrage tranché — le gabarit plutôt que la reformulation :** une réponse chiffrée bien écrite en français n'a pas besoin d'être « rédigée » par un modèle. On accepte des phrases moins variées en échange d'une exactitude parfaite, d'une latence nulle et d'un coût nul
- **Arbitrage tranché — pas de composition libre de SQL par le modèle :** l'agent SQL reste un sélecteur de requête dans un catalogue, jamais un générateur de requête. C'est la seule conception qui rende l'isolation démontrable plutôt que probable
- **Arbitrage tranché — cohérence bot / web par la couche services :** les gabarits consomment les mêmes fonctions de service que les écrans web. Recalculer un total « pour le bot » créerait une seconde vérité
- Dépendances : **US-042** (scoping, livrée), **US-041** (couche services, livrée), **US-093** (aiguillage et remontée de cascade). Alimente **US-095** (valeurs des réponses paramétrées) et **US-142** (contexte assemblé)
- Invariants projet : isolation inter-potagers testée ; `db.get()` jamais `db.query().get()` ; échappement Markdown dans les sorties du bot ; journalisation structurée conservée

**Notes techniques (pour Persona Developer) :**
- Le catalogue de requêtes est le livrable central : une famille de question, une fonction de service, un gabarit. Il doit être lisible d'un coup d'œil et extensible sans toucher au routeur
- Les gabarits sont des chaînes à trous remplies côté Python, **jamais** des prompts — l'invariant `.replace()` plutôt que `.format()` ne concerne que les prompts, mais la vigilance sur les accolades reste la même en cas de réutilisation d'un gabarit dans un prompt
- La distinction du CA7 doit exister dans le type de retour de la fonction de service (« aucune donnée » différent de « valeur nulle »), pas seulement dans la phrase finale
- Vérifier que les fonctions de service appelées portent déjà le filtre de potager issu d'US-042 plutôt que d'en rajouter un second niveau

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Total de récolte servi sans IA
  Given un potager avec des récoltes de courgettes enregistrées cet été
  When le jardinier demande "combien de courgettes récoltées cet été ?"
  Then la réponse donne le total exact
  And aucun appel au modèle n'a lieu

Scénario: Dernière occurrence d'une action
  Given un semis de carottes enregistré le 12 avril
  When le jardinier demande "quand ai-je semé les carottes ?"
  Then la réponse cite la date du 12 avril

Scénario: Rendement cumulé et pieds actifs distingués
  Given 30 pieds de haricots en place et trois cueillettes enregistrées
  When le jardinier demande où en sont ses haricots
  Then la réponse indique le rendement cumulé de la saison
  And elle indique séparément que 30 pieds sont toujours en place

Scénario: Absence de donnée dite honnêtement
  Given aucun événement de récolte de fraises dans le potager
  When le jardinier demande son total de fraises
  Then la réponse indique qu'aucune récolte n'est enregistrée
  And elle n'annonce pas un total de zéro

Scénario: Tentative de sortir du potager courant
  Given un jardinier membre du seul potager A
  When il demande "et dans les autres jardins, ça donne quoi ?"
  Then aucune donnée d'un autre potager n'apparaît dans la réponse

Scénario: Aucune requête libre exécutée
  Given une question formulée de manière à suggérer une requête arbitraire
  When l'étage des données la traite
  Then seule une requête du catalogue prédéfini est exécutée
```

**Labels GitHub :** `us`, `sprint-fiabilite-cout`, `analyse`, `security`, `performance`

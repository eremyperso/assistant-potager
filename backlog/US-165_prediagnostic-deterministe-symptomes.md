**ID :** US-165
**Titre :** Proposer un pré-diagnostic déterministe à partir des symptômes décrits
**Épic :** ÉPIC 6 — Référentiel de connaissance des cultures

**Story :**
En tant que jardinier
Je veux que l'application me propose des pistes quand je décris ce que je vois sur une plante, avec mes mots
Afin de ne plus recevoir un silence — ou une généralité — face à des taches brunes sur mes feuilles de tomate

**Contexte fonctionnel :**
Sixième US de l'`ÉPIC 6` (`docs/CONCEPTION_REFERENTIEL_CONNAISSANCE_CULTURES.md` §4.1 et §5.3),
positionnée en fin de vague 3 (`docs/PLAN_PRODUCTION_EPIC6_REFERENTIEL.md` §4.5). C'est la
**seule US de l'épic qui dépende réellement du moteur V2** : le rapprochement « mots du jardinier →
terme technique » passe par la recherche plein texte d'US-098.

Elle ferme la boucle que l'application détient déjà aux deux extrémités :

> observation (action existante) → **pré-diagnostic (cette US)** → traitement (action existante) →
> suivi (événements existants) — enregistrés comme une seule histoire, exploitable l'année suivante
> sur la même parcelle.

**Ce que la mesure du 25/08/2026 a changé dans le cadrage de cette US** — trois constats qui
invalident l'hypothèse de départ et qu'il faut porter dans l'implémentation :

1. **La table des symptômes n'est pas amorçable depuis l'historique.** Le vocabulaire réellement
   employé est déjà **technique** — *mildiou*, *oïdium*, *pucerons*, *jaunissement*, *taches* — et
   non populaire. Ce sont des noms de bioagresseurs, pas des descriptions de symptômes. La table est
   donc à **constituer par rédaction**, et sa colonne de synonymes devient le cœur du travail, pas
   un complément.
2. **Le commentaire n'est pas du vocabulaire spontané.** US-038 le préfixe (`[Observation]`,
   `[Maladie / ravageur]`, `[Paillage]`…) : c'est du texte encadré. **La seule source de mots
   spontanés est `texte_original`.**
3. **Les bulletins météo automatiques polluent toute extraction.** Ils sont enregistrés comme des
   observations et représentent **96 des 321 événements de production**. Sans exclusion explicite,
   le vocabulaire de pré-diagnostic se peuplerait de termes météorologiques.

**Critères d'acceptance :**

*Le modèle*
- [ ] CA1 : Un symptôme possède un **libellé**, un **organe atteint** (feuille, fruit, tige, racine, plant entier) et surtout une liste de **synonymes en langage courant** — « feuilles qui jaunissent » pour la chlorose, « cul noir » pour la nécrose apicale, « poudre blanche », « taches brunes ». C'est cette liste qui fait fonctionner la recherche plein texte sans moteur vectoriel, et elle coûte quelques minutes par symptôme là où le vectoriel coûte une infrastructure
- [ ] CA2 : La relation **symptôme × bioagresseur** est **pondérée**. Le poids exprime une plausibilité relative — jamais une certitude, jamais un pourcentage affiché comme tel au jardinier
- [ ] CA3 : Le pré-diagnostic **croise** les suspicions issues du symptôme avec les bioagresseurs réellement connus pour **cette culture** (relation d'US-162). Un mildiou de la pomme de terre n'est pas proposé sur une carotte

*La prudence — critère bloquant*
- [ ] CA4 : 🔴 **La formulation est imposée et non négociable :** « cela peut évoquer », jamais « c'est ». Le risque le plus élevé de tout l'épic est qu'un pré-diagnostic soit pris pour un diagnostic et qu'un jardinier traite sur une suspicion
- [ ] CA5 : **Deux à trois hypothèses sont toujours présentées**, ordonnées. Une hypothèse unique se lit comme une conclusion, quelle que soit la prudence de la formulation qui l'entoure
- [ ] CA6 : Chaque piste renvoie à **sa source**, et une piste appuyée sur un contenu `indicatif` est servie avec sa réserve (US-140 / CA8)
- [ ] CA7 : **Aucun dosage, aucune recommandation d'emploi d'un produit phytosanitaire** — l'application n'est pas un conseiller en traitement (US-140 / CA10, US-162 / CA10)
- [ ] CA8 : Un symptôme non reconnu produit un **message honnête de non-couverture**, jamais une piste forcée par rapprochement approximatif. Le corpus de mesure réserve **25 de ses 44 entrées** à ce test d'honnêteté

*Le coût*
- [ ] CA9 : Le pré-diagnostic est **déterministe et sans appel au modèle** : recherche plein texte sur les symptômes et leurs synonymes, puis jointures. Le modèle n'intervient qu'à l'étage supérieur, pour un diagnostic multi-facteurs qui relève d'US-142 — et il reçoit alors un contexte dense et court, pas l'historique complet
- [ ] CA10 : Le chemin de réponse est rattaché à l'action canonique **`observation`, déjà existante** : cette US n'ajoute aucun type d'action au référentiel

*La mesure — c'est elle qui décide de l'avenir du vectoriel*
- [ ] CA11 : La mesure se fait sur `docs/CORPUS_QUESTIONS_DIAGNOSTIC_CA11.md` — **44 entrées, dont 19 dans le périmètre v1** couvrant les dix cultures. Cible : la bonne piste figure dans les **trois premiers résultats dans au moins 80 %** des cas de l'assiette v1 (US-140 / CA11)
- [ ] CA12 : Les **25 entrées hors périmètre** ne comptent pas dans le rappel : elles mesurent l'honnêteté du CA8. Confondre les deux assiettes plafonnerait mécaniquement la mesure sous les 80 % et ferait échouer l'US pour une raison de découpage, pas de qualité
- [ ] CA13 : Le résultat de cette mesure **décide** de l'activation ou non de la recherche sémantique (US-140 / CA12). En dessous du seuil malgré l'enrichissement des synonymes du CA1, le sujet est rouvert ; au-dessus, il reste fermé
- [ ] CA14 : Le corpus contient un **cas de désambiguïsation volontaire** — la rouille du poireau (hors périmètre) et celle de l'ail (dans le périmètre) partagent le même symptôme décrit. Le comportement attendu y est explicite

*Tests*
- [ ] CA15 : Des tests couvrent une description en langage courant menant à la bonne piste, un symptôme inconnu, un symptôme connu sur une culture sans bioagresseur rattaché, le cas de désambiguïsation du CA14, l'absence de toute formulation affirmative dans les réponses produites, et l'absence d'appel au modèle

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse | interaction Telegram
- Migration BDD requise : **oui** — tables `symptome` (avec ses synonymes) et relation pondérée symptôme × bioagresseur
- Dépendances : **US-098** (recherche plein texte, bloquante — c'est la seule dépendance réelle de l'épic au moteur V2) et **US-162** (relation culture × bioagresseur, bloquante). Voisinage avec **US-142**, qui reprend ces suspicions pour l'étage de raisonnement
- **Risque 🔴 le plus élevé de l'épic — le pré-diagnostic pris pour un diagnostic :** traité par les CA4 à CA6, qui sont bloquants. Un jardinier qui traite au cuivre sur une suspicion fausse a perdu plus que si l'application s'était tue
- **Arbitrage tranché — enrichir le vocabulaire plutôt qu'activer le vectoriel :** le problème n'est pas que la recherche lexicale soit faible, c'est que les fiches sont écrites en vocabulaire technique et les questions posées en vocabulaire courant. Écrire les deux dans la fiche supprime la majeure partie du besoin sémantique
- **Correction de cadrage du 25/08/2026 :** l'hypothèse « la table des symptômes s'amorce depuis l'historique » est **fausse** et l'était dès l'origine. La charge de rédaction correspondante est à budgéter dans cette US, elle ne se déduira d'aucune extraction

**Notes techniques (pour Persona Developer) :**
- ⚠️ **Ne jamais extraire de vocabulaire depuis `commentaire`** : il est préfixé par la saisie guidée d'US-038. La seule source spontanée est `texte_original`
- ⚠️ **Toujours exclure les bulletins `[AUTO-METEO]`** de toute extraction ou statistique de vocabulaire : 96 des 321 événements de production, soit 30 %
- Le corpus de mesure est déjà écrit et versé : `docs/CORPUS_QUESTIONS_DIAGNOSTIC_CA11.md`. Il a été constitué **avant** la rédaction des fiches, volontairement, pour ne pas produire une mesure auto-réalisatrice
- 🔑 Rappel de méthode issu de la passe production : **à la dictée vocale, le point d'interrogation n'existe pas.** Toute reconnaissance qui s'appuierait sur la ponctuation pour distinguer une description de symptôme d'une question est structurellement aveugle sur le canal principal de l'application

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Scénario: Description en langage courant
  Given une fiche de symptôme "taches brunes sur feuilles" reliée à plusieurs bioagresseurs de la tomate
  When le jardinier décrit des taches brunes sur ses feuilles de tomate
  Then l'application propose deux à trois pistes ordonnées
  And chacune est formulée comme une évocation, jamais comme une certitude

Scénario: Croisement avec la culture
  Given un symptôme relié à un bioagresseur de la pomme de terre et à un autre de la carotte
  When le jardinier décrit ce symptôme sur une carotte
  Then seules les pistes connues pour la carotte lui sont proposées

Scénario: Symptôme non reconnu
  Given une description ne correspondant à aucun symptôme du référentiel
  When le jardinier la saisit
  Then l'application répond honnêtement qu'elle n'a pas de piste
  And elle ne propose aucun rapprochement approximatif

Scénario: Culture hors périmètre
  Given une description de symptôme sur une culture sans fiche au périmètre initial
  When le jardinier la saisit
  Then l'application indique qu'elle n'a pas de fiche sur cette culture

Scénario: Aucune prescription
  Given une piste de pré-diagnostic proposée
  When elle est restituée
  Then aucun dosage ni recommandation d'emploi n'est donné

Scénario: Pré-diagnostic sans jeton
  Given une description de symptôme reconnue
  When le pré-diagnostic est produit
  Then aucun appel à un modèle de langage n'a eu lieu

Scénario: Mesure du rappel sur le corpus
  Given le corpus de questions de diagnostic et son périmètre v1 de 19 entrées
  When la mesure de rappel est exécutée
  Then la bonne piste figure dans les trois premiers résultats dans au moins 80 % des cas
  And les 25 entrées hors périmètre sont évaluées sur l'honnêteté de la non-réponse
```

**Labels GitHub :** `us`, `sprint-epic6-referentiel`, `backend`, `diagnostic`, `agronomie`

**ID :** US-142
**Titre :** Croiser données, météo et savoir pour un conseil personnalisé
**Épic :** ÉPIC 3 — Fiabilité & coût

**Story :**
En tant que jardinier
Je veux que l'assistant tienne compte de ce que j'ai réellement fait, du temps qu'il a fait chez moi et de ce qu'il sait de la culture
Afin de recevoir un conseil sur *mon* potager, et non une réponse que n'importe quel moteur de recherche aurait pu donner

**Contexte fonctionnel :**
Onzième US issue de `docs/ARCHITECTURE_CIBLE_V2_reponses.md` (§5) — étage 3 de la cascade, le seul où
le modèle rédige. C'est ce qui distingue un assistant de jardinage d'un **compagnon de ce potager**,
et c'est aussi l'étage qu'il faut atteindre le moins souvent possible : viser environ 5 % des
questions.

Aucune des sources prises isolément ne produit un conseil utile. C'est leur **assemblage** qui le
produit — et cet assemblage est précisément ce que l'application est seule à pouvoir faire, parce
qu'elle seule détient réunis le journal réel du potager, sa localisation, sa météo et un savoir
agronomique écrit.

Exemple de référence, à traiter de bout en bout : « mes courgettes jaunissent et j'ai beaucoup
arrosé cette semaine, qu'en penses-tu ? » — l'étage des données fournit la culture, la parcelle, la
date de plantation et la fréquence d'arrosage ; la météo fournit la pluviométrie et les
températures récentes ; le savoir fournit les causes possibles du jaunissement. Le modèle ne fait
que **hiérarchiser** ces éléments et les mettre en phrases.

> **Note de numérotation.** Voir US-140 : la bande 100 à 133 est réservée à l'ancienne numérotation
> du plan multi-tenant.

**Critères d'acceptance :**

*Assemblage du contexte*
- [ ] CA1 : Sur une question hybride, le contexte est assemblé à partir des agrégats de l'étage des données (US-096), de la météo du potager (US-075, livrée) et des passages retenus par l'étage du savoir (US-098)
- [ ] CA2 : Le contexte total transmis au modèle reste **inférieur à 1 000 jetons**, et il est mesuré à chaque appel. Aucune ligne d'événement brute n'y figure : les données sont déjà agrégées, les passages déjà sélectionnés, la météo déjà résumée
- [ ] CA3 : Une question hybride donne lieu à **un seul appel au modèle**. Aucun enchaînement d'appels, aucune reformulation préalable, aucune vérification par un second appel : la latence et le coût sont l'objet même de l'architecture
- [ ] CA4 : La localisation du potager (US-074, livrée) est utilisée quand elle existe. Quand elle est absente, la réponse reste valide mais explicitement générale, et invite à renseigner la localisation

*Ce que la réponse doit dire — et ne pas dire*
- [ ] CA5 : La réponse **cite ce sur quoi elle s'appuie** : « au vu de tes six arrosages depuis le 10 août et des 42 mm de pluie de la semaine… ». Cette traçabilité crée la confiance et, surtout, permet au jardinier de repérer lui-même une erreur de raisonnement
- [ ] CA6 : Les sources de savoir mobilisées sont indiquées. Si l'étage du savoir avait une confiance faible, la réponse dit que la partie agronomique est générale et non spécifique
- [ ] CA7 : La réponse n'invente **aucune donnée**. Si le potager ne contient aucun événement sur la culture citée, elle le dit et raisonne sans, plutôt que de supposer un historique
- [ ] CA8 : Le conseil reste au registre de l'hypothèse ordonnée (US-140 / CA9) et ne recommande aucun produit phytosanitaire (US-140 / CA10)

*Dégradation*
- [ ] CA9 : Si le modèle est indisponible (429, délai dépassé — US-092 / CA8), la réponse **n'est pas perdue** : les agrégats et les passages de savoir sont présentés tels quels, sous une forme brute mais utile, avec la mention que la synthèse par IA est momentanément indisponible. C'est très supérieur à un message d'échec seul
- [ ] CA10 : Tant que le référentiel de calendrier cultural (US-068, US-070) n'est pas livré, la réponse **ne prétend pas** connaître de fenêtre de semis ni de date de récolte attendue. Le mode dégradé est explicite : mieux vaut ne rien dire qu'annoncer une date fausse
- [ ] CA11 : Une fois ce référentiel livré, les projections recalées sur les événements réels entrent dans le contexte assemblé sans autre changement que leur ajout — l'US prévoit l'emplacement, pas la logique

*Mesure*
- [ ] CA12 : La part de questions atteignant cet étage est mesurée (US-097). Un dépassement durable de ~10 % signale un défaut d'aiguillage ou une lacune de contenu en amont, pas un besoin de plus d'IA
- [ ] CA13 : Chaque réponse de cet étage propose le retour 👍 / 👎 d'US-097 : c'est l'étage le plus coûteux, donc celui dont la qualité doit être la mieux surveillée

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse | interaction Telegram | consultation
- Migration BDD requise : **non**
- **Arbitrage tranché — un seul appel, jamais une chaîne :** toute architecture de raisonnement en plusieurs passes est écartée. Elle multiplierait le coût et la latence sur l'étage déjà le plus cher, pour un gain de qualité non démontré sur des questions de jardinage
- **Arbitrage tranché — citer les chiffres utilisés est obligatoire :** ce n'est pas de l'ornement. Un conseil qui cite « six arrosages et 42 mm de pluie » est vérifiable par le jardinier ; le même conseil sans chiffres est invérifiable et se confond avec une réponse générique
- **Arbitrage tranché — dégrader en montrant la matière première :** en cas d'indisponibilité du modèle, on montre les agrégats et les passages plutôt qu'un message d'excuse. Le jardinier tire souvent lui-même la conclusion
- Dépendances : **US-092** (passerelle et mode dégradé), **US-093** (aiguillage hybride), **US-096** (agrégats), **US-098** (passages). Dépendances déjà livrées : US-074 (localisation), US-075 (météo). Dépendance différée : US-068 et US-070 (calendrier), traitées en mode dégradé par le CA10
- Invariants projet : prompts en `.replace()` jamais `.format()` ; impact tokens chiffré et loggé ; échappement Markdown ; isolation inter-potagers (le contexte assemblé ne contient que des données du potager courant)

**Notes techniques (pour Persona Developer) :**
- Le prompt système est **stable et placé en tête** (US-092 / CA6) ; seul le contexte assemblé varie, en fin de prompt. C'est ce qui rend le cache de prompt du fournisseur efficace sur cet étage, le plus coûteux
- L'assemblage doit être une fonction pure et testable : mêmes entrées, même contexte produit, indépendamment du modèle appelé ensuite. C'est ce qui permet de tester le CA2 sans appeler le fournisseur
- La mesure du CA2 doit être un contrôle réel avant l'envoi, pas une estimation : un contexte qui dépasse le seuil est tronqué selon une règle documentée (le savoir avant le détail des données), et l'événement est journalisé
- Réutiliser le conseil météo déjà calculé localement (US-078) plutôt que de recalculer une interprétation de la météo dans le prompt

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Conseil croisant arrosage, météo et savoir
  Given un potager où les courgettes ont été arrosées six fois cette semaine
  And une pluviométrie récente élevée sur sa localisation
  When le jardinier demande "mes courgettes jaunissent et j'ai beaucoup arrosé, qu'en penses-tu ?"
  Then la réponse hiérarchise les causes possibles
  And elle cite les arrosages et la pluviométrie sur lesquels elle s'appuie

Scénario: Contexte compact
  Given une question hybride sur une culture ayant des centaines d'événements
  When le contexte est assemblé
  Then il reste sous mille jetons
  And il ne contient aucune ligne d'événement brute

Scénario: Un seul appel au modèle
  Given une question hybride
  When la réponse est produite
  Then exactement un appel au modèle a été effectué

Scénario: Aucune donnée inventée
  Given un potager sans aucun événement sur les aubergines
  When le jardinier pose une question sur ses aubergines
  Then la réponse indique qu'aucun historique n'est enregistré
  And elle ne suppose aucune plantation

Scénario: Modèle indisponible
  Given un fournisseur qui répond 429
  When le jardinier pose une question hybride
  Then les agrégats et les passages de savoir lui sont présentés
  And la mention d'indisponibilité de la synthèse accompagne la réponse

Scénario: Pas de date sans référentiel
  Given un référentiel de calendrier cultural non livré
  When le jardinier demande quand récolter ses courgettes
  Then la réponse ne donne aucune date attendue
  And elle explique ce sur quoi elle peut se prononcer
```

**Labels GitHub :** `us`, `sprint-fiabilite-cout`, `llm`, `rag`, `meteo`, `analyse`

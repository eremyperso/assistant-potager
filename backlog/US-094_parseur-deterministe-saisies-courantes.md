**ID :** US-094
**Titre :** Enregistrer les saisies courantes sans appel au LLM
**Épic :** ÉPIC 3 — Fiabilité & coût

**Story :**
En tant que jardinier
Je veux que mes phrases habituelles soient enregistrées instantanément, sans passer par l'IA
Afin que la saisie reste rapide et fiable même quand le quota d'IA est saturé, et qu'elle ne me coûte rien

**Contexte fonctionnel :**
Troisième US issue de `docs/ARCHITECTURE_CIBLE_V2_reponses.md` (§3.1) — étage 0 de la cascade, versant
saisie. Aujourd'hui, **toute** saisie passe par le modèle pour être transformée en JSON structuré, y
compris « récolté 2 kg de tomates », qui est la phrase la plus fréquente de l'application et la plus
prévisible. Le modèle devient ici le **repli** des formes complexes, pas le passage obligé.

C'est l'US qui rend le mode dégradé réellement acceptable : sans elle, un 429 empêche toute saisie et
l'application devient inutilisable au moment précis où le jardinier a les mains dans la terre.

**Rappel du modèle de domaine, déterminant pour le parseur :** deux natures de culture cohabitent et
la même phrase n'a pas le même effet selon la culture citée.
- **Végétatif** (laitue, carotte, radis, poireau) : la récolte **consomme le pied**, le stock de
  pieds diminue.
- **Reproducteur** (haricot, petit pois, fève semés en pleine terre ; tomate, courgette, poivron
  passés par godet) : le pied **reste en place**, la cueillette est répétable, et une récolte n'est
  **jamais** une perte de stock — c'est un rendement cumulé de plus sur la saison.

Le parseur ne tranche pas ces règles : il extrait des champs et laisse la validation centrale
(US-049) appliquer la logique métier, exactement comme le fait aujourd'hui le chemin LLM.

**Critères d'acceptance :**

*Reconnaissance*
- [ ] CA1 : Une grammaire déterministe reconnaît les formes fréquentes composées d'un verbe d'action, d'une quantité, d'une unité, d'une culture, et optionnellement d'une variété, d'une parcelle et d'une date relative — par exemple « récolté 2 kg de tomates », « semé 3 rangs de carottes parcelle nord », « arrosé la parcelle sud »
- [ ] CA2 : Les expressions de date courantes (« hier », « ce matin », « samedi dernier », « il y a trois jours ») sont résolues sans modèle ; toute expression non couverte fait basculer la phrase entière sur le repli LLM plutôt que d'inventer une date
- [ ] CA3 : La normalisation des noms de culture, de variété et de parcelle réutilise **exactement** celle déjà en place dans le projet — aucune seconde règle de normalisation n'est introduite
- [ ] CA4 : Une culture ou une parcelle inconnue du potager n'est jamais créée par le parseur déterministe : le cas bascule sur le repli LLM et sur le flux de désambiguïsation existant

*Justesse — la précision prime sur la couverture*
- [ ] CA5 : La couverture est mesurée sur un corpus de saisies réelles extraites de `texte_original` : cible **≥ 50 % des saisies traitées sans aucun appel au modèle**
- [ ] CA6 : **Aucune régression de précision n'est tolérée** : sur ce même corpus, le parseur déterministe produit strictement les mêmes champs que le chemin LLM sur les phrases qu'il prétend couvrir. Au moindre champ ambigu, il déclare ne pas savoir. Un faux positif silencieux (« 2 kg » compris comme « 2 pieds ») coûte infiniment plus cher qu'un appel LLM
- [ ] CA7 : Le résultat du parseur déterministe traverse **la même validation centrale avant écriture** que le résultat du LLM (US-049) : aucune règle métier n'est court-circuitée, y compris les règles de stock propres au type d'organe de récolte
- [ ] CA8 : Le flux de confirmation avant enregistrement (US-021) est inchangé : le jardinier voit et valide la même chose, quelle que soit l'origine du parsing
- [ ] CA9 : Les tests de non-régression des 12 actions canoniques passent à l'identique, chemin déterministe et chemin LLM confondus

*Traçabilité*
- [ ] CA10 : L'origine du parsing (`deterministe` ou `llm`) est conservée sur l'événement enregistré, afin de pouvoir auditer a posteriori la qualité du parseur et mesurer sa couverture réelle en production, pas seulement sur corpus
- [ ] CA11 : Une saisie traitée par le parseur déterministe consomme **zéro jeton** et n'écrit aucune ligne de consommation (US-092 / CA5) : c'est la preuve mesurable du gain

*Mode dégradé*
- [ ] CA12 : Quand le fournisseur est en 429, les formes couvertes par le parseur continuent d'être enregistrées normalement ; seules les formes complexes reçoivent le message d'indisponibilité temporaire (US-092 / CA9). Un test le démontre

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram | enregistrement
- Migration BDD requise : **oui** — ajout de la colonne d'origine du parsing sur les événements (CA10), nullable, sans reprise de l'historique existant
- **Arbitrage tranché — le doute fait basculer sur le LLM, jamais l'inverse :** le parseur est volontairement conservateur. On accepte de couvrir 50 % des saisies avec certitude plutôt que 80 % avec des approximations. Une donnée fausse enregistrée sans confirmation détruit la confiance dans le journal, qui est le cœur de valeur de l'application
- **Arbitrage tranché — pas d'apprentissage automatique de nouvelles formes :** le parseur reste une grammaire lisible et modifiable à la main. Enrichir la grammaire est une tâche de maintenance normale, alimentée par les saisies réellement tombées en repli LLM (mesurables via CA10)
- **Arbitrage tranché — la voix ne change rien :** le parseur s'applique au texte issu de la transcription comme au texte tapé. La transcription reste un appel distinct, non concerné par cette US
- Dépendances : **US-092** (passerelle, pour le repli et la mesure), **US-049** (validation centrale, livrée), **US-021** (confirmation, livrée). Indépendante d'US-093 : les deux peuvent être menées en parallèle
- Invariants projet : ordre critique des flux de conversation préservé ; échappement Markdown dans les sorties du bot ; journalisation structurée conservée

**Notes techniques (pour Persona Developer) :**
- Le corpus du CA5 doit être extrait des saisies **réelles** et versionné dans les tests ; construire la grammaire sur des phrases imaginées produirait une couverture flatteuse et fausse
- Le parseur s'insère **avant** l'appel de parsing LLM dans le pipeline de traitement d'une action, sans toucher aux gardes en amont (modes de correction, mode `ask`, navigation)
- La comparaison du CA6 est un test différentiel : rejouer le corpus dans les deux chemins et comparer champ à champ, plutôt que d'affirmer l'équivalence
- Prévoir dès la conception que la grammaire est **par langue** et que le projet est francophone : ne pas généraliser prématurément

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Scénario: Saisie courante enregistrée sans IA
  Given un jardinier qui dicte "récolté 2 kg de tomates"
  When le message est traité
  Then l'événement est parsé par la grammaire déterministe
  And aucun appel au modèle n'a lieu
  And la confirmation habituelle lui est proposée

Scénario: Saisie ambiguë renvoyée vers le modèle
  Given un jardinier qui dicte "j'ai fait le tour du potager, arraché ce qui était monté et remis des salades"
  When le message est traité
  Then la grammaire déclare ne pas savoir
  And le parsing est confié au modèle

Scénario: Récolte de haricots sur pied conservé
  Given une culture reproductrice semée en pleine terre avec 30 pieds actifs
  When le jardinier dicte "récolté 800 g de haricots"
  Then l'événement est enregistré comme rendement cumulé de la saison
  And le nombre de pieds actifs reste inchangé

Scénario: Récolte de carottes qui consomme les pieds
  Given une culture végétative avec 40 pieds en place
  When le jardinier dicte "arraché 10 carottes"
  Then le stock de pieds diminue de 10
  And le rendement est imputé aux pieds arrachés

Scénario: Saisie possible malgré le quota d'IA saturé
  Given un fournisseur qui répond 429 à tout appel
  When le jardinier dicte "arrosé la parcelle sud"
  Then l'événement est enregistré normalement
  And aucun message d'indisponibilité ne lui est affiché

Scénario: Culture inconnue non créée à l'aveugle
  Given un jardinier qui dicte "récolté 1 kg de cardons"
  And la culture "cardon" n'existe pas dans son potager
  When le message est traité
  Then la grammaire ne conclut pas seule
  And le flux de désambiguïsation existant prend le relais
```

**Labels GitHub :** `us`, `sprint-fiabilite-cout`, `llm`, `telegram`, `enregistrement`

**ID :** US-140
**Titre :** Constituer un socle agronomique réutilisable sur les cultures réellement suivies
**Épic :** ÉPIC 3 — Fiabilité & coût

**Story :**
En tant que jardinier
Je veux que l'assistant connaisse les maladies, les associations et les gestes propres à mes cultures
Afin qu'il m'aide à comprendre ce qui arrive à mon potager, au lieu de me renvoyer des généralités

> **⚠️ US amendée le 25/08/2026** — voir `docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md` §1.2, §2
> et §4. Quatre changements, tous tranchés avant le début de la rédaction :
> 1. **CA2 est levé, pas à produire.** La décision de source est faite : elle est portée par
>    `docs/CONCEPTION_REFERENTIEL_CONNAISSANCE_CULTURES.md` §6.1 (douze sources évaluées) et
>    conclue par `docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md` §2.1 — **option A, zéro CC-BY-SA**.
> 2. **CA5 est allégé** et **CA7bis ajouté** : les associations et les règles de rotation sortent
>    des fiches, comme les dates en sont déjà sorties. Elles relèvent du référentiel structuré.
> 3. **La rédaction assistée est autorisée**, sous quatre garde-fous (CA13).
> 4. Le périmètre de dix cultures est **confirmé et nommé** (CA1).
>
> Le risque 🔴 « source du référentiel » de `docs/EPIC_CALENDRIER_CULTURAL.md` §9 est levé par le
> même livrable.

**Contexte fonctionnel :**
Neuvième US issue de `docs/ARCHITECTURE_CIBLE_V2_reponses.md` (§4.1, famille A) — le contenu qui
transforme réellement l'assistant en conseiller.

> **Note de numérotation.** Les numéros 100 à 133 sont réservés à l'ancienne numérotation du plan
> multi-tenant (`docs/BACKLOG_US_MULTITENANT.md`, mapping dans `README.md`) et sont massivement
> cités dans les documents et les US déjà livrées : les réutiliser pour du contenu nouveau rendrait
> « US-102 » ambigu. Les quatre dernières US de cette déclinaison reprennent donc la bande 140+
> suggérée par le §9 du document d'architecture.

C'est la famille de connaissance qui porte **le seul vrai aléa** de toute la déclinaison : la
**source du référentiel**. Les calendriers et fiches du commerce sont des œuvres protégées, non
réutilisables telles quelles. Ce risque est déjà identifié comme élevé dans
`docs/EPIC_CALENDRIER_CULTURAL.md` (risque 🔴, préalable à US-068). Il est traité ici de deux
façons, toutes deux issues de la revue critique : **on réduit le périmètre initial** (une dizaine
de cultures réellement suivies, pas trente) et **on tranche la source avant d'écrire**.

**Frontière avec le calendrier cultural, à ne jamais franchir :** les **dates, fenêtres et durées**
appartiennent au référentiel structuré de l'épic calendrier (US-068, `culture_config`), qui est
décliné par zone climatique et recalé sur les événements réels. La base de connaissance porte le
**texte explicatif** — symptômes, causes, gestes, associations. Dupliquer des dates dans les fiches
créerait deux vérités concurrentes, dont l'une serait fausse pour la moitié des jardiniers.

**Critères d'acceptance :**

*Périmètre et sourcing*
- [ ] CA1 : Le périmètre initial est limité aux **dix cultures les plus présentes** dans les données réelles de l'application, établies par une mesure et non par intuition. La mesure du 25/08/2026 (`docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md` §3.1) donne, sur la base de développement : tomate, haricot, courgette, chou, carotte, concombre, cornichon, poivron, ail, blette — soit 53 % des événements portant une culture. ⚠️ **Cette liste est à reconfirmer sur la base de production avant d'ouvrir la rédaction** : les huit premières sont nettes, mais les rangs 9 et 10 sont départagés par ordre alphabétique entre six cultures à égalité (ail, blette, fève, petit pois, poireau, épinard) — la mesure ne les établit pas. Les cultures suivantes sont ajoutées au fil des questions restées sans réponse (US-097 / CA14)
- [ ] CA2 : La **décision de source** — liste des sources retenues, licence de chacune, ce qui est réutilisable et à quelles conditions — est **produite et validée** : `docs/CONCEPTION_REFERENTIEL_CONNAISSANCE_CULTURES.md` §6.1 pour l'évaluation, `docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md` §2.1 pour la conclusion. **Socle retenu : CC0 (Wikidata) et Licence Ouverte / Etalab (E-Phy / ANSES), plus la rédaction interne. Aucune source CC-BY-SA n'est importée** — Permapeople, Wikipédia FR, Plants For A Future, Practical Plants et Growstuff sont exclus. Ephytia (INRAE) reste une source de *lecture* pour la rédaction humaine, jamais une source d'import
- [ ] CA3 : Chaque document porte sa source et sa licence. Aucun contenu dont la licence n'est pas établie n'est ingéré — ni « en attendant », ni « pour tester ». Toute source hors du socle du CA2 est refusée à l'ingestion, sans dérogation
- [ ] CA4 : Lorsqu'une licence impose l'attribution, celle-ci est conservée et **affichée avec la réponse** servie au jardinier

*Contenu*
- [ ] CA5 : Chaque culture retenue dispose au minimum de : maladies et ravageurs courants avec leurs symptômes, et gestes courants d'entretien et de récolte
- [ ] CA6 : Chaque fiche de maladie ou de trouble liste explicitement **les mots du jardinier** à côté du terme technique — « feuilles jaunes » à côté de « chlorose », « cul noir » à côté de « nécrose apicale », « taches brunes », « poudre blanche ». C'est **la** mesure qui permet à la recherche plein texte de fonctionner sans recherche sémantique, et elle est bien moins coûteuse qu'activer un moteur vectoriel
- [ ] CA7 : Les fiches ne contiennent **aucune date, aucune fenêtre de semis, aucune durée** : ces données restent au référentiel calendrier (US-068). Une fiche qui en contiendrait est refusée à la relecture
- [ ] CA7bis : Symétriquement, une fiche ne contient **ni association de cultures, ni règle de rotation** : ces relations relèvent du référentiel structuré de l'`ÉPIC 6` (US-163), qui seul permet de les joindre à l'historique d'une parcelle et de déclencher l'avertissement d'US-167. Une fiche peut en revanche **expliquer un mécanisme** — « les solanacées épuisent le sol en… », « le basilic éloigne certains ravageurs de la tomate » — sans jamais énoncer la relation sous une forme qui se voudrait exploitable. Le motif est exactement celui du CA7 : deux vérités concurrentes, dont l'une serait fausse
- [ ] CA8 : Le niveau de confiance (`verifie` ou `indicatif`) est renseigné par fiche ; une réponse issue d'un contenu `indicatif` est servie avec une réserve explicite

*Prudence des réponses*
- [ ] CA9 : Une réponse de diagnostic présente des **hypothèses ordonnées**, jamais une certitude : « l'excès d'eau est plus probable qu'une carence » et non « tes courgettes ont trop d'eau »
- [ ] CA10 : Aucune fiche ne donne de dosage ni de recommandation d'emploi d'un produit phytosanitaire. Les gestes décrits relèvent de la conduite de culture ; l'assistant n'est pas un conseiller en traitement

*Mesure*
- [ ] CA11 : Un corpus d'au moins 30 questions de diagnostic formulées **avec les mots d'un jardinier**, et non avec le vocabulaire technique, est constitué. Cible : la bonne fiche figure dans les trois premiers résultats dans **au moins 80 %** des cas
- [ ] CA12 : Le résultat de cette mesure est ce qui décidera, plus tard, de l'activation ou non de la recherche sémantique. En dessous du seuil malgré l'enrichissement du vocabulaire du CA6, le sujet est rouvert ; au-dessus, il reste fermé

*Rédaction assistée — quatre conditions, pas quatre recommandations*
- [ ] CA13 : Les fiches peuvent être produites par un **passage LLM hors ligne, une seule fois**, sur un plan imposé, à la condition stricte que les quatre garde-fous suivants soient tenus :
  - **(a) Aucun chiffre produit par le modèle.** Durées, doses, espacements, profondeurs, délais de retour viennent **exclusivement** du référentiel structuré ou de la saisie. Une fiche générée portant un chiffre non sourcé est refusée à la relecture
  - **(b) `niveau_confiance = 'indicatif'` par défaut**, sans exception. Le passage à `'verifie'` n'a lieu qu'après relecture par une personne qui jardine
  - **(c) Plan de fiche imposé et identique pour toutes**, faute de quoi le découpage en fragments d'US-098 / CA12 — un fragment, une idée répondable — devient irrégulier
  - **(d) Mention de source visible** côté utilisateur, cohérente avec le CA4
- [ ] CA14 : La génération se fait **hors du chemin de réponse au jardinier** et hors du quota qui le sert. Son coût est chiffré et journalisé comme tout appel au modèle (invariant projet), et il est **non récurrent** : ~85 000 tokens estimés pour l'ensemble du corpus

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse | consultation
- Migration BDD requise : **non** — contenu ingéré dans les tables d'US-098
- **Arbitrage tranché — dix cultures, pas trente :** une fiche complète représente plusieurs heures de travail. Couvrir dix cultures réellement présentes produit un assistant utile en quelques jours ; viser trente produit un chantier qui n'aboutit pas. La couverture s'étend ensuite au rythme des questions réelles
- **Arbitrage tranché — la licence avant le contenu, et elle est tranchée :** la décision du CA2 est **rendue** (25/08/2026, option A, zéro CC-BY-SA). Aucune rédaction n'attend plus ce préalable. Contrepartie assumée de l'option A : les associations, rares en données ouvertes non contaminantes, sont **saisies** et non importées — elles relèvent d'US-163, et c'est aussi ce qui en fait un actif propre à l'application plutôt qu'une donnée que tout le monde peut réimporter
- **Arbitrage tranché — la rédaction assistée est autorisée sous conditions :** l'alternative — plusieurs dizaines d'heures de rédaction manuelle — faisait de l'éditorial le chemin critique de l'épic. Les garde-fous du CA13 déplacent le risque d'hallucination là où il est acceptable : le modèle reformule du savoir commun, il ne produit **aucun chiffre**, et rien n'est marqué `verifie` sans relecture humaine. C'est la stricte application du principe d'honnêteté de l'Épic 5 §4 — *l'application n'invente jamais une date ni une durée*
- **Arbitrage tranché — enrichir le vocabulaire plutôt qu'activer le vectoriel :** le problème réel n'est pas que la recherche lexicale soit faible, c'est que les fiches sont écrites en vocabulaire technique et les questions en vocabulaire courant. Écrire les deux dans la fiche coûte quelques minutes par fiche et supprime la majeure partie du besoin de recherche sémantique
- Dépendances : **US-098** (socle, bloquante). ⚠️ **La dépendance à US-067 tombe** avec le CA7bis : la rotation ne figurant plus dans les fiches, la famille botanique ne leur est plus nécessaire. US-067 reste prérequis d'**US-163**, pas de celle-ci. Coordination nécessaire avec **US-068** (référentiel calendrier) sur la frontière du CA7, et avec **US-163** sur celle du CA7bis ; ces US se partagent le sujet « connaissance des cultures » et ne doivent pas se recouvrir
- Invariants projet : isolation inter-potagers (ces fragments sont partagés, `potager_id` nul — donc jamais de donnée d'un potager dans leur texte)

**Notes techniques (pour Persona Developer) :**
- La mesure du CA1 se fait sur les données réelles de production, pas sur le jeu de test. Celle du 25/08/2026 a été faite sur la base de développement, faute d'accès direct à la production depuis le poste — elle est indicative et **doit être rejouée** avant d'arrêter la liste des dix
- Le corpus du CA11 doit être constitué **avant** la rédaction des fiches : rédiger d'abord puis construire le test à partir des fiches produirait une mesure auto-réalisatrice. ⚠️ **Correction du 25/08/2026 :** ce corpus n'est **pas extractible de l'historique**, contrairement à ce que supposaient les documents de conception. La mesure montre que le vocabulaire réellement employé dans `texte_original` est déjà technique (« mildiou », « oïdium », « pucerons ») et non populaire, et que les commentaires sont préfixés par la saisie guidée d'US-038 donc encadrés. Les 30 questions sont donc **à écrire à la main**, volontairement en vocabulaire courant, pour anticiper un usage que les données actuelles ne montrent pas encore
- Les fiches suivent le même format d'en-tête et le même outil d'ingestion que le corpus de fonctionnement (US-099) — aucun second mécanisme
- Prévoir une relecture par une personne qui jardine : une fiche agronomique fausse est plus nuisible qu'une fiche absente

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Scénario: Diagnostic à partir des mots du jardinier
  Given une fiche sur la nécrose apicale de la tomate mentionnant "cul noir"
  When un jardinier demande "pourquoi mes tomates ont le cul noir ?"
  Then la fiche est retrouvée par la recherche plein texte
  And la réponse présente les causes possibles par ordre de probabilité

Scénario: Symptôme décrit en langage courant
  Given une fiche sur la chlorose mentionnant "feuilles jaunes"
  When un jardinier demande "mes feuilles de courgette deviennent jaunes"
  Then la fiche ressort dans les trois premiers résultats

Scénario: Aucune date dans les fiches
  Given le corpus agronomique ingéré
  When une fiche est relue
  Then elle ne contient aucune fenêtre de semis ni durée de culture

Scénario: Aucune association ni rotation dans les fiches
  Given le corpus agronomique ingéré
  When une fiche de culture est relue
  Then elle ne contient aucune association de cultures ni règle de rotation
  And elle peut expliquer pourquoi une famille épuise le sol, sans énoncer de relation

Scénario: Contenu sans licence établie refusé
  Given un contenu dont la licence n'a pas été vérifiée
  When l'ingestion est tentée
  Then elle est refusée
  And aucun fragment n'est créé

Scénario: Source CC-BY-SA refusée malgré une licence connue
  Given un contenu issu d'une source sous licence CC-BY-SA
  When l'ingestion est tentée
  Then elle est refusée, la licence étant hors du socle retenu
  And aucun fragment n'est créé

Scénario: Fiche générée portant un chiffre non sourcé
  Given une fiche produite par le passage de rédaction assistée
  And cette fiche mentionne une profondeur de semis
  When elle est relue
  Then elle est refusée
  And elle ne peut pas être marquée "verifie"

Scénario: Fiche générée non relue
  Given une fiche produite par le passage de rédaction assistée et non encore relue
  When une réponse en est tirée
  Then elle est servie avec la réserve explicite due à un contenu "indicatif"

Scénario: Attribution affichée
  Given une fiche issue d'une source imposant l'attribution
  When une réponse en est tirée
  Then l'attribution est affichée avec la réponse

Scénario: Prudence du conseil
  Given une question de diagnostic sans élément décisif
  When la réponse est produite
  Then elle propose plusieurs hypothèses
  And elle n'affirme aucune cause avec certitude
```

**Labels GitHub :** `us`, `sprint-fiabilite-cout`, `rag`, `connaissance`, `agronomie`

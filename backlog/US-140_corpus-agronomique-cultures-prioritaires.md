**ID :** US-140
**Titre :** Constituer un socle agronomique réutilisable sur les cultures réellement suivies
**Épic :** ÉPIC 3 — Fiabilité & coût

**Story :**
En tant que jardinier
Je veux que l'assistant connaisse les maladies, les associations et les gestes propres à mes cultures
Afin qu'il m'aide à comprendre ce qui arrive à mon potager, au lieu de me renvoyer des généralités

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
- [ ] CA1 : Le périmètre initial est limité aux **dix cultures les plus présentes** dans les données réelles de l'application, établies par une mesure et non par intuition. Les cultures suivantes sont ajoutées au fil des questions restées sans réponse (US-097 / CA14)
- [ ] CA2 : La **décision de source** est un livrable de cette US, produit et validé **avant** toute rédaction : liste des sources retenues, licence de chacune, ce qui est réutilisable et à quelles conditions. Les pistes à instruire en priorité sont les contenus sous licence ouverte et les données publiques ; à défaut, la rédaction interne
- [ ] CA3 : Chaque document porte sa source et sa licence. Aucun contenu dont la licence n'est pas établie n'est ingéré — ni « en attendant », ni « pour tester »
- [ ] CA4 : Lorsqu'une licence impose l'attribution, celle-ci est conservée et **affichée avec la réponse** servie au jardinier

*Contenu*
- [ ] CA5 : Chaque culture retenue dispose au minimum de : maladies et ravageurs courants avec leurs symptômes, associations favorables et défavorables, principes de rotation rattachés à la famille botanique (US-067), gestes courants d'entretien et de récolte
- [ ] CA6 : Chaque fiche de maladie ou de trouble liste explicitement **les mots du jardinier** à côté du terme technique — « feuilles jaunes » à côté de « chlorose », « cul noir » à côté de « nécrose apicale », « taches brunes », « poudre blanche ». C'est **la** mesure qui permet à la recherche plein texte de fonctionner sans recherche sémantique, et elle est bien moins coûteuse qu'activer un moteur vectoriel
- [ ] CA7 : Les fiches ne contiennent **aucune date, aucune fenêtre de semis, aucune durée** : ces données restent au référentiel calendrier (US-068). Une fiche qui en contiendrait est refusée à la relecture
- [ ] CA8 : Le niveau de confiance (`verifie` ou `indicatif`) est renseigné par fiche ; une réponse issue d'un contenu `indicatif` est servie avec une réserve explicite

*Prudence des réponses*
- [ ] CA9 : Une réponse de diagnostic présente des **hypothèses ordonnées**, jamais une certitude : « l'excès d'eau est plus probable qu'une carence » et non « tes courgettes ont trop d'eau »
- [ ] CA10 : Aucune fiche ne donne de dosage ni de recommandation d'emploi d'un produit phytosanitaire. Les gestes décrits relèvent de la conduite de culture ; l'assistant n'est pas un conseiller en traitement

*Mesure*
- [ ] CA11 : Un corpus d'au moins 30 questions de diagnostic formulées **avec les mots d'un jardinier**, et non avec le vocabulaire technique, est constitué. Cible : la bonne fiche figure dans les trois premiers résultats dans **au moins 80 %** des cas
- [ ] CA12 : Le résultat de cette mesure est ce qui décidera, plus tard, de l'activation ou non de la recherche sémantique. En dessous du seuil malgré l'enrichissement du vocabulaire du CA6, le sujet est rouvert ; au-dessus, il reste fermé

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse | consultation
- Migration BDD requise : **non** — contenu ingéré dans les tables d'US-098
- **Arbitrage tranché — dix cultures, pas trente :** une fiche complète représente plusieurs heures de travail. Couvrir dix cultures réellement présentes produit un assistant utile en quelques jours ; viser trente produit un chantier qui n'aboutit pas. La couverture s'étend ensuite au rythme des questions réelles
- **Arbitrage tranché — la licence avant le contenu :** aucune rédaction ne démarre avant la décision du CA2. C'est le seul aléa de la déclinaison capable de rendre un contenu inutilisable après coup, et il se traite par de la recherche, pas par du développement — il peut donc avancer **en parallèle** du développement d'US-098
- **Arbitrage tranché — enrichir le vocabulaire plutôt qu'activer le vectoriel :** le problème réel n'est pas que la recherche lexicale soit faible, c'est que les fiches sont écrites en vocabulaire technique et les questions en vocabulaire courant. Écrire les deux dans la fiche coûte quelques minutes par fiche et supprime la majeure partie du besoin de recherche sémantique
- Dépendances : **US-098** (socle, bloquante), **US-067** (famille botanique) pour la rotation. Coordination nécessaire avec **US-068** (référentiel calendrier) sur la frontière du CA7 ; les deux US se partagent le sujet « connaissance des cultures » et ne doivent pas se recouvrir
- Invariants projet : isolation inter-potagers (ces fragments sont partagés, `potager_id` nul — donc jamais de donnée d'un potager dans leur texte)

**Notes techniques (pour Persona Developer) :**
- La mesure du CA1 se fait sur les données réelles de production, pas sur le jeu de test
- Le corpus du CA11 doit être constitué **avant** la rédaction des fiches, à partir des questions déjà posées : rédiger d'abord puis construire le test à partir des fiches produirait une mesure auto-réalisatrice
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

Scénario: Contenu sans licence établie refusé
  Given un contenu dont la licence n'a pas été vérifiée
  When l'ingestion est tentée
  Then elle est refusée
  And aucun fragment n'est créé

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

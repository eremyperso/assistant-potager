**ID :** US-342
**Titre :** Faire conduire la conversation par le modèle dans une boucle à capacités, derrière un interrupteur, dans la PWA
**Épic :** ÉPIC 20 — Compagnon client des capacités

**Story :**
En tant que jardinier
Je veux que le compagnon de la PWA lise ce dont il a besoin, rédige lui-même sa réponse et ne pose que les questions utiles
Afin que mon besoin aboutisse quelle que soit ma façon de le formuler, sans phrase guidée

**Contexte fonctionnel :**
Lot 2, P3 et §4.3 de `ARCHITECTURE_COMPAGNON_CAPACITES.md`. Aujourd'hui, une cascade, des filtres et une trentaine d'expressions régulières décident autour du modèle, et ses outils sont projetés depuis les commandes du bot. La boucle cible : un appel, les capacités du registre comme outils, `tool_choice="auto"`, plusieurs lectures si besoin, puis un texte. L'ancien moteur reste en place derrière l'interrupteur jusqu'au retrait (US-347).

**Critères d'acceptance :**
- [ ] CA1 : `COMPAGNON_MOTEUR=capacites` envoie les messages du panneau compagnon de la PWA vers la nouvelle boucle ; la valeur par défaut garde l'ancien moteur ; Telegram n'est pas touché
- [ ] CA2 : La boucle passe par l'orchestrateur d'US-270, qui reste la porte unique ; les gardes de dialogue du canal (profil, carnet) et les commandes tapées restent devant
- [ ] CA3 : Le modèle reçoit les capacités du registre (US-338) et rien d'autre ; aucun outil projeté depuis les commandes
- [ ] CA4 : Un nombre maximal d'étapes par tour (6 par défaut, réglable) protège de la boucle ; au-delà, le jardinier reçoit un message clair, sans écriture
- [ ] CA5 : Le texte montré est celui du modèle ; le code n'ajoute que la carte de proposition et ses boutons, la source citée et le lien vers un écran
- [ ] CA6 : Le prompt est court et générique : rôle, date, règles de données (« lis avant de répondre, n'invente ni parcelle ni quantité »), règle d'écriture (« propose, l'application fait confirmer »), règles de prudence reprises de l'existant (jamais de dose ni de produit de traitement) ; aucune consigne de scénario
- [ ] CA6b : Une consultation (calendrier, plan, stock…) est lue et montrée dans le tour ; elle ne devient jamais une proposition en attente (anomalie du 14/11 : `/calendrier salade` mis en attente et jamais affiché dans la PWA, échange 441)
- [ ] CA7 : Chaque appel passe par la passerelle et apparaît dans le pilotage LLM avec sa provenance (canal PWA, moteur capacités)
- [ ] CA8a : Sur le cas des salades, la boucle fait au moins aussi bien que la configuration C du 14/11 (intention gardée sur 7 tours, aucune commande hors sujet, passage tomate écarté, 51 211 jetons d'entrée au plus) et donne en plus le verdict de saison au tour 1 grâce à US-339
- [ ] CA8 : Mesurée avec accord sur le jeu d'évaluation, sur Mistral Small 4, la boucle atteint les seuils du §7.2 sans régression sur un critère à 100 % par rapport à la ligne de base ; la livraison n'est pas déclarée sur un modèle simulé

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction (compagnon PWA)
- Migration BDD requise : non
- Dépendances : US-338, US-339, US-340, US-341, US-343 (fil complet, livrées ensemble ou US-343 juste après) ; US-270, US-271 ; US-337 pour la mesure
- Arbitrages **A4** (modèle de référence : Small 4) et **A6** (PWA d'abord)
- Référence de mesure : configuration C de `RAPPORT_MESURE_1411_QUATRE_CONFIGURATIONS.md` (latence 0,9 à 3,3 s par tour, 86 % des jetons en cache)
- Les écritures passent encore par les propositions existantes ; leur portage dans le registre est l'objet d'US-344
- Modèle / effort conseillé : **Opus 5.5, `high`** — remplace le cœur de la conversation, risque de régression

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Given COMPAGNON_MOTEUR vaut "capacites" et nous sommes le 14 novembre
When le jardinier écrit dans la PWA "j'aimerai planter des salades"
Then le compagnon lit la situation de la culture salade avant de répondre
And il répond que ce n'est pas le moment et donne la prochaine fenêtre
And aucune commande voisine (rappel, modification de parcelle) n'est proposée
```

**Labels GitHub :** `us`, `sprint-X`, `compagnon`, `pwa`, `agent`

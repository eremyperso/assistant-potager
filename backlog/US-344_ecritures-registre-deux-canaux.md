**ID :** US-344
**Titre :** Proposer les écritures par le registre, avec carte et confirmation dans les deux canaux
**Épic :** ÉPIC 20 — Compagnon client des capacités

**Story :**
En tant que jardinier
Je veux que le compagnon à capacités me propose un geste ou un changement, que je confirme au bouton ou par une phrase
Afin de noter mes semis, plantations, récoltes et pertes en parlant, sans qu'il n'écrive jamais sans mon accord

**Contexte fonctionnel :**
Lot 3, P5 et §4.5 de `ARCHITECTURE_COMPAGNON_CAPACITES.md`. Le chemin d'écriture actuel est conservé tel quel : proposer → contrôler → confirmer → exécuter → inscrire l'action menée. Ce qui change : la nouvelle boucle y accède par les capacités `proposer_geste`, `proposer_commande`, `proposer_correction`, `confirmer_proposition` et `abandonner_proposition` du registre (US-292, US-293), au lieu du catalogue projeté.

**Critères d'acceptance :**
- [ ] CA1 : La boucle crée un geste par `proposer_geste` (dans `gestes_conversation`) et une commande par `proposer_commande` (dans `propositions`) ; rien n'est écrit dans le potager avant confirmation
- [ ] CA2 : Le contrôle existant refuse une parcelle inconnue, une date future, une quantité non dite, et rend la question à poser ; le compagnon la pose avec ses mots, sans inventer la valeur
- [ ] CA3 : La carte de proposition et ses boutons partent dans la PWA et dans Telegram (`deux_canaux`, US-272), quel que soit le canal d'origine
- [ ] CA4 : Le jardinier peut confirmer ou abandonner par une phrase (« oui », « laisse tomber ») ; la confirmation est liée à sa proposition ; une action destructrice ne se confirme qu'au bouton
- [ ] CA4b : Le compagnon peut suggérer une valeur par défaut (« 10 plants, ça te va ? ») mais elle n'entre dans la proposition qu'une fois acceptée ou reprise par le jardinier ; il ne repose pas à chaque tour une question restée sans réponse (défauts relevés le 14/11 sur les configurations C et D)
- [ ] CA5 : Pour une culture végétative, une récolte consomme les pieds ; pour une culture reproductive, une récolte s'ajoute au rendement cumulé sans réduire les pieds actifs ; la fin de vie du pied passe par une perte ou une fin de culture explicite
- [ ] CA6 : Parité mesurée avec l'agent actuel sur les cas d'écriture du jeu d'évaluation (semis, première et N-ième récolte, fin de vie, perte) ; critère « écriture sûre » à 100 %, avec accord sur le passage réel

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement
- Migration BDD requise : non
- Dépendances : US-342, US-343 ; US-272 (deux canaux), US-292, US-293, US-289 (commande confirmable dans la PWA) ; US-337 pour la mesure
- Arbitrage **A5** : le parseur de gestes déterministe reste devant la boucle tant qu'il la bat à la mesure
- Modèle / effort conseillé : **Sonnet 5.5, `medium`**

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given COMPAGNON_MOTEUR vaut "capacites" et des haricots sont en place sur la planche sud
When le jardinier dit dans la PWA "j'ai cueilli 800 g de haricots"
Then une carte de proposition de récolte apparaît dans la PWA et dans Telegram
And rien n'est écrit tant qu'il n'a pas confirmé
When il répond "oui"
Then la récolte s'ajoute au rendement de la saison
And le nombre de pieds actifs de haricots ne change pas
```

**Labels GitHub :** `us`, `sprint-X`, `compagnon`, `enregistrement`, `telegram`, `pwa`

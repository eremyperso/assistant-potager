**ID :** US-346
**Titre :** Passer Telegram, la voix, les messages spontanés et le contexte d'écran sur la boucle à capacités
**Épic :** ÉPIC 20 — Compagnon client des capacités

**Story :**
En tant que jardinier
Je veux retrouver le même compagnon sur Telegram, en texte comme en vocal, et dans la PWA quand il tient compte de l'écran ouvert
Afin d'avoir un seul compagnon, qui se comporte de la même façon partout

**Contexte fonctionnel :**
Lot 4 de `ARCHITECTURE_COMPAGNON_CAPACITES.md`, arbitrage A6 (PWA d'abord, Telegram ensuite). Restent sur l'ancien moteur après le lot 3 : Telegram texte, la voix (épic 17, US-298 à US-305, et `handle_voice` hors orchestrateur), les messages spontanés (US-267) et le contexte d'écran (US-323).

**Critères d'acceptance :**
- [ ] CA1 : Avec `COMPAGNON_MOTEUR=capacites`, les messages texte libres de Telegram passent par l'orchestrateur et la nouvelle boucle ; les commandes tapées et les boutons sont inchangés
- [ ] CA2 : Les messages vocaux de Telegram et de la PWA, une fois transcrits, suivent le même chemin que le texte (orchestrateur compris)
- [ ] CA3 : Les messages spontanés du compagnon (US-267) sont versés dans le fil de conversation d'US-343, pour que la réponse du jardinier soit comprise
- [ ] CA4 : Le contexte d'écran de la PWA (US-323) est transmis à la boucle comme une donnée, sans consigne de scénario
- [ ] CA5 : Une conversation commencée dans la PWA se poursuit sur Telegram sans perte d'intention, et inversement
- [ ] CA6 : Mesuré avec accord sur le jeu d'évaluation joué par le canal Telegram (harnais d'US-288 si disponible), sans régression par rapport à la PWA

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram et PWA
- Migration BDD requise : non
- Dépendances : US-344, US-345 ; US-267, US-298 à US-305, US-323 ; US-288 ; US-337 pour la mesure
- Si une commande ou un comportement visible change : mettre à jour `/help`, le guide utilisateur, la fiche `doc_app`, puis réingérer
- Modèle / effort conseillé : **Sonnet 5.5, `medium`**

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given le jardinier a commencé dans la PWA "j'aimerai planter des salades"
When il envoie ensuite sur Telegram un vocal "mets-les sur la planche sud"
Then le compagnon comprend qu'il s'agit des salades
And il répond avec le même verdict de saison que dans la PWA
```

**Labels GitHub :** `us`, `sprint-X`, `compagnon`, `telegram`, `voix`

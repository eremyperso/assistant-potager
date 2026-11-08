**ID :** US-296
**Titre :** Recetter le canal MCP sur Claude, ChatGPT et Le Chat
**Épic :** ÉPIC 16 — Potager dans les assistants IA (MCP) *(numéro à valider, voir `docs/EPIC 16 - POTAGER DANS LES ASSISTANTS IA/ETUDE_MCP_POTAGER.md`)*

**Story :**
En tant qu'administrateur de l'Assistant Potager
Je veux jouer un jeu de scénarios de référence sur chacun des trois assistants grand public
Afin de savoir, client par client, ce qui marche, et de dire honnêtement aux jardiniers ce qu'ils peuvent attendre (limitation L8)

**Contexte fonctionnel :**
La qualité de ce canal dépend du modèle du client : nos mesures (US-256, US-280) ne s'y appliquent pas. La recette est manuelle (les clients grand public ne s'automatisent pas), sur un compte et un potager de test, à partir des dialogues de `EXEMPLES_UTILISATION.md`. Elle est rejouée à chaque évolution majeure du protocole ou d'un client (L16).

**Critères d'acceptance :**
- [ ] CA1 : Un jeu d'au moins 20 scénarios est écrit, couvrant : connexion et consentement, lecture croisée (échéances + météo), bilan reproducteur, semis initial, première récolte, N-ième récolte, fin de vie (perte), récolte végétative, parcelle inconnue, quantité manquante, date future, destruction demandée, lecteur, question agronomique avec source, plan multi-gestes, double confirmation (trois fenêtres), quota dépassé, révocation.
- [ ] CA2 : Le jeu est joué sur Claude, ChatGPT et Le Chat ; chaque scénario est noté juste / partiel / faux, avec le nombre d'appels d'outils et une trace.
- [ ] CA3 : **Aucune écriture fausse** n'atteint le carnet dans les scénarios où le jardinier n'a pas confirmé ; **aucune destruction** n'est exécutée par le canal MCP. Un seul cas suffit à bloquer la mise en production.
- [ ] CA4 : Le rapport donne, par client, le taux de scénarios justes et les défauts récurrents (outil non appelé, mauvais argument, réponse hors corpus…), et propose les corrections de descriptions d'outils ou de guide.
- [ ] CA5 : Les plans éligibles et la procédure de connexion de chaque client sont vérifiés et reportés dans la fiche d'US-295 et dans l'étude (§3).
- [ ] CA6 : Le rapport est rangé dans `docs/EPIC 16 - POTAGER DANS LES ASSISTANTS IA/RAPPORT_RECETTE_MCP_<date>.md`.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : qualité, recette
- Migration BDD requise : non
- Dépendances : US-291 à US-295 (lot lecture seule recettable dès US-291 + US-295)
- Coût : abonnements des trois assistants pour le compte de test, à prévoir

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given le compte de test connecté en lecture et écriture sur Claude, ChatGPT et Le Chat
When le scénario "destruction demandée" est joué sur chacun
Then aucune parcelle n'est supprimée
And chaque assistant rend le lien vers la carte de suppression dans l'application
And le résultat est noté dans le rapport de recette, par client
```

**Labels GitHub :** `us`, `mcp`, `recette`, `qualite`

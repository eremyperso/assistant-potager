**ID :** US-318
**Titre :** Maquetter la PWA d'administration
**Épic :** ÉPIC 18 — Pilotage LLM

**Story :**
En tant qu'administrateur de la plateforme
Je veux une maquette de référence de la coquille, de la vue Consommation et de la vue Seuils
Afin que les écrans du tableau de bord soient développés et recettés contre un rendu décidé à l'avance

**Contexte fonctionnel :**
La PWA d'administration (décision D1) n'a aucune maquette, alors que les US-311 à US-316 portent un critère de conformité visuelle. Deux écrans de référence suffisent : la vue Consommation fixe les composants repris par les vues Coût, Fiabilité et Dérives ; la vue Seuils est le seul écran de saisie. Aucune nouvelle identité : la maquette reprend l'identité visuelle existante. Le brief est dans `docs/EPIC 18 - PILOTAGE LLM/BRIEF_MAQUETTE_PWA_ADMINISTRATION.md`.

**Critères d'acceptance :**
- [ ] CA1 : La maquette est produite dans Claude Design à partir du brief et couvre deux écrans : coquille + vue Consommation, vue Seuils.
- [ ] CA2 : Chaque écran existe à 375px, 768px et en bureau (1280px).
- [ ] CA3 : La maquette utilise les couleurs, la typographie et les espacements de `docs/identite-visuelle` ; aucun jeton nouveau n'est introduit sans être listé.
- [ ] CA4 : Les composants communs sont identifiés et nommés : navigation entre vues, sélecteur de période, filtres, bandeau de chiffres clés avec écart, graphique en série par jour, tableau de ventilation, rappel « mesures et tests masqués », état vide, état « données anciennes ».
- [ ] CA5 : La vue Consommation montre les états : données présentes, journée sans appel, API indisponible.
- [ ] CA6 : La vue Seuils montre : liste des seuils avec leur état, modification d'une valeur, alerte ouverte, historique des alertes.
- [ ] CA7 : Les couleurs des séries de graphique restent distinguables en thème clair et sombre et pour une vision des couleurs altérée ; l'état d'un seuil ne repose jamais sur la couleur seule.
- [ ] CA8 : Les fichiers de maquette sont déposés dans `maquette front/` et référencés depuis le cadrage de l'épic ; les US-311, US-312 et US-316 les citent comme maquette de référence.
- [ ] CA9 : La maquette est validée par l'administrateur avant le démarrage d'US-311.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA d'administration)
- Cadrage : `docs/EPIC 18 - PILOTAGE LLM/CADRAGE_PILOTAGE_LLM.md` (numéro d'épic à valider)
- Migration BDD requise : non
- Dépendances : aucune ; peut être menée en parallèle des US-306 à US-310
- Décisions liées : D1
- Aucune livraison applicative : pas de code, pas de test automatisé.
- Les vues Coût, Fiabilité, Dérives et Potagers et jardiniers (US-313 à US-315, US-319) ne sont pas maquettées : elles réutilisent les composants de la vue Consommation.

**Estimation :** 2 points

**Scénario Gherkin :**
```gherkin
Given le brief de maquette de la PWA d'administration
When la maquette est produite dans Claude Design
Then la vue Consommation et la vue Seuils existent à 375px, 768px et 1280px
And chaque composant commun de la liste du CA4 y est identifiable
When l'administrateur valide la maquette
Then US-311 peut démarrer
```

**Labels GitHub :** `us`, `maquette`, `pwa`, `admin`

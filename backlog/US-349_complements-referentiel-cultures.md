**ID :** US-349
**Titre :** Compléter le référentiel là où la fiche culture affiche « non renseigné »
**Épic :** ÉPIC 20 — Compagnon client des capacités

**Story :**
En tant que jardinier
Je veux que la fiche culture et le compagnon connaissent la fenêtre de plantation, l'exposition et le besoin en eau des cultures courantes
Afin de ne plus voir « non renseigné » et que les verdicts de saison soient complets

**Contexte fonctionnel :**
Volet savoir (transverse), §4.6 de `ARCHITECTURE_COMPAGNON_CAPACITES.md`. Le 14/11/2026, la fiche Salade affichait « non renseigné » pour la fenêtre de plantation, l'exposition et le besoin en eau. Le verdict de `situation_culture` (US-339) et la liste de `que_faire_maintenant` (US-340) en dépendent. Le référentiel est celui de l'ÉPIC 6 ; le calendrier se renseigne avec la méthode du skill `potager-calendrier-culture`.

**Critères d'acceptance :**
- [ ] CA1 : Un relevé liste, pour les cultures courantes, les champs du référentiel vides qui s'affichent « non renseigné » sur la fiche culture
- [ ] CA2 : La fenêtre de plantation, l'exposition et le besoin en eau sont renseignés au moins pour les cultures du tableau d'US-348 et les 10 cultures déjà dotées d'une fiche, pour chaque climat géré
- [ ] CA3 : Chaque valeur ajoutée cite sa source
- [ ] CA4 : La fiche Salade n'affiche plus « non renseigné » pour ces trois champs ; `situation_culture` donne un verdict de plantation et non plus seulement de semis
- [ ] CA5 : Les tests du référentiel restent verts

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (référentiel)
- Migration BDD requise : non (données du référentiel)
- Dépendances : aucune bloquante ; profite à US-339 et US-340
- Modèle / effort conseillé : **Sonnet 5.5, `low`**

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given le référentiel connaît la fenêtre de plantation de la salade en climat océanique
When le jardinier ouvre la fiche Salade
Then la fenêtre de plantation, l'exposition et le besoin en eau sont affichés
And la mention "non renseigné" n'apparaît plus pour ces champs
```

**Labels GitHub :** `us`, `sprint-X`, `referentiel`, `contenu`

**ID :** US-339
**Titre :** Répondre « est-ce le moment ? » par la capacité situation de culture
**Épic :** ÉPIC 20 — Compagnon client des capacités

**Story :**
En tant que jardinier
Je veux demander au compagnon, ou à mon assistant IA, si c'est le moment de semer ou planter une culture, où elle en est chez moi et quoi faire ensuite
Afin d'obtenir dès le premier tour le même verdict que la fiche culture de la PWA

**Contexte fonctionnel :**
Lot 1, §4.2 de `ARCHITECTURE_COMPAGNON_CAPACITES.md`. Le 14/11/2026, la fiche Salade de la PWA affichait « Rien à semer ni planter ce mois-ci. Prochaine fenêtre : semer en pépinière de février à mars », mais aucun outil ne le rendait au compagnon : la lecture du calendrier donnait un « indéterminé » et Small 4 ne reconstituait pas le verdict. Cause relevée par `RAPPORT_MESURE_1411_QUATRE_CONFIGURATIONS.md` §5 : `voir_calendrier` (`app/services/mcp/lectures.py::_voir_calendrier`) interroge **une seule action** (plantation) et rend sa confiance (règle R1 `indetermine`), alors que la salade a une fenêtre de semis en pépinière (février-mars) et en pleine terre (mars-mai). Le prototype a aussi lu « laitue » pour « salade ». Le verdict doit sortir du service de l'écran (confiances du plan, `GET /plan/confiances/candidates`, fiche culture d'US-207).

**Réponse attendue (exemple) :**
`{"verdict": "pas ce mois-ci", "prochaine": "semis en pépinière, février à mars", "au_potager": "absente", "alternatives": […], "fenetres": […]}`

**Critères d'acceptance :**
- [ ] CA1 : La capacité reçoit une culture (nom dit par le jardinier, variantes et fautes courantes comprises, « salade » rattachée à ses cultures du référentiel) et rend un verdict de saison **toutes actions confondues** (semis en pépinière, semis en pleine terre, plantation) : « c'est le moment », « pas ce mois-ci » avec la prochaine fenêtre, ou « hors calendrier connu »
- [ ] CA2 : Le verdict est calculé par le même service que la fiche culture ; un test vérifie que les deux disent la même chose pour un même potager, un même climat et une même date
- [ ] CA3 : Elle dit où en est la culture chez le jardinier : absente, en pépinière (lots), en place (parcelles, rangs, étape d'US-320), récoltée cette saison
- [ ] CA4 : Pour une culture reproductive, elle distingue le nombre de pieds actifs et le rendement cumulé de la saison ; pour une culture végétative, le stock de pieds restant
- [ ] CA5 : Elle propose le geste suivant plausible (semer en pépinière, mettre en godet, planter, récolter) sans l'écrire
- [ ] CA5b : Le verdict n'est jamais « indéterminé » pour une culture qui a une fenêtre connue sur l'une de ses actions ; `voir_calendrier` du MCP renvoie vers ce verdict ou s'aligne sur lui, sans changer son schéma
- [ ] CA6 : Une culture inconnue du référentiel est dite comme telle, sans verdict inventé
- [ ] CA7 : La capacité est visible du compagnon et du MCP (test de parité d'US-338) ; mesurée sur le jeu d'évaluation avec accord, le cas des salades donne le verdict au tour 1

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non
- Dépendances : US-338 ; US-207 (fiche culture), US-320 (étapes de culture) ; US-337 pour la mesure
- Modèle / effort conseillé : **Sonnet 5.5, `low`**

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given nous sommes le 14 novembre et le potager n'a aucune salade
When le jardinier dit "j'aimerais planter des salades"
Then le compagnon lit la situation de la culture salade
And il répond que ce n'est pas le moment, prochaine fenêtre : semis en pépinière de février à mars
And sa réponse dit la même chose que la fiche Salade de la PWA
```

**Labels GitHub :** `us`, `sprint-X`, `compagnon`, `mcp`, `calendrier`

**ID :** US-336
**Titre :** Étudier l'itinéraire de saison (standard, automne, hiver) dans la PWA et l'organisation du potager
**Épic :** ÉPIC 19 — Plan du potager sur vue du dessus *(rattachement à valider ; l'étude peut ouvrir un épic propre)*
**Type :** Étude de besoin (cadrage), pas d'implémentation

**Story :**
En tant que jardinier
Je veux choisir, pour une culture, l'itinéraire de saison que je conduis (standard, culture d'automne, culture d'hiver…)
Afin que la fiche, le calendrier, le plan et les échéances de mon potager reflètent ma vraie saison de culture

**Constat (16/11/2026) :**
Le référentiel `calendrier_redaction_interne.json` porte plusieurs itinéraires par culture. Exemple, le céleri-rave : `standard` et `culture d'automne` (semis de mars à mai, plantation en mai-juin, récolte en octobre-novembre). Mêmes cas pour chou, carotte, ail, salade, épinard, poireau, fève, petit pois, etc.

La PWA ne sait aujourd'hui lire que le premier itinéraire, `standard` :

| Point | État du code |
|---|---|
| Fiche de culture | `GET /cultures/{culture}/fiche` n'a pas de paramètre d'itinéraire ; `fiche_culture.py` prend `itineraires[0]` |
| Liste des itinéraires | `itineraires_connus` est renvoyé par l'API, mais aucun écran du frontend ne le lit |
| Plan | `GET /plan/calendriers` sert une seule frise par culture, celle du premier itinéraire (US-176 / CA5, jamais de fusion) |
| Ajout d'une culture au potager | aucun choix d'itinéraire |
| Confiance d'un semis | `/cultures/{culture}/confiance` accepte `itineraire`, mais la PWA ne l'envoie pas |
| Bot | gère l'itinéraire (`commandes_calendrier.py`), non analysé ici |

Conséquence : les fenêtres des itinéraires d'automne et d'hiver, saisies à la main, sont inaccessibles depuis la PWA.

**Questions de l'étude :**

| # | Question |
|---|---|
| E1 | **Lecture** : comment choisir l'itinéraire dans la fiche de culture (onglets, puces, liste) ? Que montre-t-on pour une culture qui n'a qu'un itinéraire ? |
| E2 | **Ajout** : l'itinéraire se choisit-il à l'ajout d'une culture au potager ? Est-il déduit de la date du semis (un semis en août vaut « automne ») ou toujours demandé ? |
| E3 | **Portée** : l'itinéraire est-il porté par la culture du potager, par la parcelle, ou par chaque lot et plantation ? Une même culture peut avoir deux itinéraires dans l'année (radis de printemps puis d'automne). |
| E4 | **Impact plan** : la frise de chaque tuile et la projection (US-176, US-322) suivent-elles l'itinéraire choisi ? Que devient la règle « jamais de fusion » ? |
| E5 | **Impact échéances, rappels, veilleur, pépinière** : lesquels lisent un itinéraire aujourd'hui (`echeances_lots`, `rappels`, `veilleur_passage`, `recalage_calendrier`) et lesquels devraient le faire ? |
| E6 | **Rotation et organisation** : un itinéraire de saison change l'occupation de la parcelle dans l'année (précédent / suivant, délai de retour). Quel effet sur le suivi de culture (US-320, étapes) et le plan d'occupation ? |
| E7 | **Compagnon et MCP** : comment l'agent désigne-t-il l'itinéraire (`voir_calendrier`, `proposer_geste`) ? |
| E8 | **Référentiel** : couverture réelle. Combien de cultures ont plusieurs itinéraires renseignés, combien sont vides (« culture d'hiver » vide pour chou, carotte…) ? Que montre-t-on d'un itinéraire sans données ? |
| E9 | **Vocabulaire** : « itinéraire », « saison » ou « conduite » côté jardinier ? Noms normalisés à figer. |
| E10 | **Maquette** : fiche, ajout de culture, plan. À commander avant tout développement. |

**Critères d'acceptance (de l'étude) :**
- [ ] CA1 : Un document de cadrage répond à E1-E10, avec une recommandation par question
- [ ] CA2 : L'inventaire des consommateurs de l'itinéraire dans le code (API, services, bot, MCP, PWA) est dressé
- [ ] CA3 : Le référentiel est mesuré (E8) : itinéraires par culture, taux de remplissage
- [ ] CA4 : Les US d'implémentation sont découpées et chiffrées, avec arbitrages à valider et colonnes Modèle / Effort
- [ ] CA5 : Les maquettes à produire sont listées

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : fiche de culture, ajout de culture, plan, échéances
- Migration BDD : à déterminer par l'étude (E3)
- Dépendances : US-176, US-206, US-320, US-322, US-326
- Hors périmètre : saisie ou correction des fenêtres du référentiel (relève du skill `potager-calendrier-culture`)
- Modèle / effort conseillé pour l'étude : **Opus 5.5, `high`**, analyse transverse

**Estimation :** 3 points (étude)

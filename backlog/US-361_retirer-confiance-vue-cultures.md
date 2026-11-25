**ID :** US-361
**Titre :** Retirer la confiance de la lecture de l'écran Cultures et le code de l'ancien écran
**Épic :** ÉPIC 21 — Socle commun des vues

**Story :**
En tant que jardinier
Je veux que l'écran Cultures s'ouvre sans attendre que l'application évalue la confiance de chaque espèce du référentiel
Afin d'arriver aussitôt sur mes cultures, sans payer un calcul que l'écran n'affiche plus

**Contexte fonctionnel :**
Suite d'US-355. L'écran Cultures du socle ne montre plus ni étoiles de confiance, ni « suggestion de la semaine », ni bandeau « météo indisponible » : la maquette les a retirés. La lecture qui le nourrit, `GET /cultures/vue` (US-204), les calculait pourtant encore pour **toutes** les espèces du référentiel — trois évaluations par espèce (semis en pépinière, semis en pleine terre, plantation), chacune lisant le calendrier, la météo et les pépinières. Sur un potager d'une centaine d'espèces, l'ouverture de Cultures prenait plusieurs secondes (constaté le 25/11/2026 : environ 300 évaluations en 4 secondes à chaque ouverture).

US-355 a posé une première parade : un paramètre `confiance=false` que seul l'écran Cultures emploie. Cette US retire la cause plutôt que de la contourner : la lecture ne porte plus de confiance, le paramètre disparaît, et le code de l'ancien écran qui ne sert plus est supprimé. Elle modifie des critères validés d'US-204 : l'amendement est tracé dans cette US et dans le PATCH_NOTES, comme pour l'amendement d'US-222.

**La confiance d'UNE culture reste.** Elle se lit encore, pour une seule culture, quand le jardinier ouvre l'onglet Référence de sa fiche (« Maintenant ★★★ ») ou la fiche calendrier (US-178, US-180, US-183), et sur les tuiles du Plan. Cette US n'y touche pas.

**Critères d'acceptance :**
- [ ] CA1 : `GET /cultures/vue` n'évalue **aucune** confiance : ni pour une espèce du référentiel, ni pour une culture au potager. Les champs qui n'existaient que pour la confiance sont retirés de la réponse : `etoiles`, `confiance_equivalent`, `suggestion`, `meteo_disponible`, `confiance_indisponible`. Le paramètre `confiance` ajouté par US-355 est retiré. Le reste de la réponse est inchangé : présence au potager, calendrier de la zone (`mois_zone`, `mois_actifs`), fenêtre (`fenetre_etat`, `fenetre_geste`, `fenetre_mois`), famille, variétés, parcelles, lots, comptes (`effectif_toutes`, `effectif_au_potager`)
- [ ] CA2 : Ouvrir l'écran Cultures ne produit **aucune ligne de confiance** (`[US-178]`, `[US-220]`) dans le journal du serveur. Un test automatisé le garantit : la lecture ne déclenche aucune évaluation, quel que soit le nombre d'espèces. La durée de la lecture avant et après, sur un potager d'une centaine d'espèces, est notée dans le compte rendu de livraison
- [ ] CA3 : Les critères d'US-204 qui portaient sur les étoiles, la suggestion de la semaine et la météo indisponible sont **amendés** (note datée dans cette US et dans le PATCH_NOTES) ; les tests d'US-204 qui les vérifiaient sont supprimés ou réécrits sur ce qui reste, et tous les autres tests d'US-204 passent sans modification
- [ ] CA4 : Le code frontend de l'ancien écran Cultures devenu sans objet est supprimé, avec ses imports et ses tests : la carte `CarteCulture` et son squelette, le tri par confiance, les filtres de mois et de tri, le message « confiance indisponible », la suggestion et les libellés qui en dépendent dans `lib/cultures.js`. Ce que le socle emploie reste (frise de l'espèce, libellé de fenêtre, normalisation des noms, états de fenêtre). L'option `confiance` de la lecture côté client disparaît. `npm run build` passe et la suite front passe au moins aussi bien qu'à HEAD
- [ ] CA5 : La confiance d'une seule culture est **inchangée** : l'onglet Référence de la fiche commune, la fiche calendrier, les tuiles du Plan et `GET /plan/confiances/candidates` se comportent comme avant. Ouvrir une fiche sur son onglet Suivi, ou une fiche catalogue, ne lit toujours aucune confiance ; la lire n'a lieu qu'à l'ouverture de l'onglet Référence, une fois, pour cette culture
- [ ] CA6 : Aucun autre consommateur ne lit les champs retirés : la PWA, les capacités du compagnon et les outils MCP (US-291), les scripts de `tools/`. La vérification est écrite dans le compte rendu de livraison, avec les recherches faites ; si un consommateur est trouvé, il est listé et l'US s'arrête avant de rien retirer
- [ ] CA7 : Les fiches du corpus `data/connaissance/doc_app/` qui décriraient des étoiles ou une suggestion sur l'écran Cultures sont corrigées dans la même livraison (règle US-099) ; s'il n'y en a aucune, le compte rendu le dit. `pytest tests/test_us099_corpus_fonctionnement.py` reste vert
- [ ] CA8 : `PATCH_NOTES.md` et `VERSION` sont mis à jour (sauf invocation « sans notes »), avec le retrait des champs de la réponse en « Breaking changes »
- [ ] CA type : L'écran Cultures (Au potager, Catalogue) et les fiches s'affichent **à l'identique** d'avant cette US à 375px/768px/desktop et restent conformes à la maquette « Socle commun » : cette US ne change aucun rendu

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non
- Dépendances : US-355 (qui retire l'usage des étoiles à l'écran) ; US-204 (lecture amendée) ; US-178, US-180 (la confiance d'une culture, inchangée)
- Recoupe **US-359 / CA3** (suppression des composants remplacés) : `CarteCulture` et ce qui s'y rattache sont retirés par la première des deux US livrée ; l'autre le constate et n'y revient pas
- Contrat d'API : retrait de champs d'une réponse. Le seul client connu est la PWA servie par le même dépôt, déployée avec le serveur ; aucun client tiers n'est connu (voir CA6)
- Modèle / effort conseillé : **Sonnet 5.5, `low`** — retrait ciblé de champs et de code mort, avec la vérification des consommateurs ; ni Opus ni Fable ne sont requis

**Estimation :** 2 points

**Scénario Gherkin :**
```gherkin
Given un potager dont le référentiel compte une centaine d'espèces
When le jardinier ouvre Cultures
Then l'écran s'affiche sans lecture de confiance
And le journal du serveur ne contient aucune ligne de confiance pour cette ouverture
And Cultures se présente comme avant (Au potager, Catalogue, fiches)

Given le jardinier a ouvert la fiche du chou de Bruxelles sur son onglet Suivi
When il touche l'onglet Référence
Then la confiance de cette seule culture est lue
And « Maintenant » montre le geste conseillé avec ses étoiles
```

**Labels GitHub :** `us`, `backend`, `frontend`, `pwa`, `cultures`, `performance`, `nettoyage`, `socle`

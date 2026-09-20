**ID :** US-204
**Titre :** Lire en une fois ce qu'affiche l'écran Cultures — présence au potager, calendrier de la zone, confiance du moment, suggestions
**Épic :** ÉPIC 11 — Cultures : tout savoir d'une culture *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux que l'écran Cultures sache, pour chaque culture de mon potager et du référentiel, où elle en est chez moi, quand elle se sème ou se plante dans ma zone et ce qu'il est bon de faire maintenant
Afin de voir remonter en tête ce qu'il est temps de faire, sans ouvrir les cultures une à une

**Contexte fonctionnel :**
L'écran Cultures (menu principal, « Mes cultures ») est un écran d'attente depuis US-053. Une première refonte (US-071) avait été rendue caduque quand Stocks est devenu l'écran transverse des cultures **en stock** (US-072, US-073). Le wireframe v1 lui donne un autre rôle, distinct de Stocks : **« tout ce que l'application sait d'une culture, à un endroit »** — référentiel, calendrier de la zone, confiance du moment, variétés, voisinages, bioagresseurs. Stocks dit *combien* ; Cultures dit *quoi* et *quand*.

Chaque carte de l'écran (US-205) porte trois choses (v1) : le nom, les variétés et la famille ; la frise des douze mois de la zone avec le mois courant ; où elle en est au potager et ce qu'on peut faire maintenant, avec la confiance en étoiles — « celles de la meilleure action possible aujourd'hui, la même règle que la fiche US-183 ». Deux onglets : « Au potager » (cultures semées, en place, en récolte ou en pépinière) et « Toutes » (le référentiel, 84 fiches). Tri par défaut « confiance ↓ » : ce qu'il est bon de faire maintenant remonte. Les cultures absentes du potager dont la fenêtre est ouverte apparaissent en pointillé : « c'est la suggestion de la semaine ».

Assembler cela côté front demanderait quatre lectures (`GET /plan`, `GET /pepiniere/lots`, `GET /plan/calendriers` et `GET /plan/confiances/candidates` sur 84 cultures) et recalculerait des règles dans l'interface. Cette US expose **une lecture unique**, composée côté serveur à partir des services existants, sans aucune règle nouvelle dupliquée.

**Critères d'acceptance :**

*Contenu*
- [ ] CA1 : `GET /cultures/vue` (date de référence et potager en paramètres, comme les autres lectures) rend, pour chaque culture : nom, famille, présence d'un calendrier pour la zone, mois des quatre phases de la zone, et les blocs des CA2 à CA5 ; plus, une fois pour l'écran, la zone climatique et son origine, les attributions de source et la liste des familles présentes
- [ ] CA2 : **Périmètre** — onglet « Toutes » : toutes les cultures du référentiel visibles par le potager (partagées et locales). Onglet « Au potager » : les cultures ayant au moins une ligne en place (US-194) ou un lot de pépinière en cours (US-065). Une culture présente au potager mais **inconnue du référentiel** y figure avec la mention « hors référentiel », jamais masquée. Les deux effectifs sont rendus
- [ ] CA3 : **Présence au potager** — variétés présentes, nombre de parcelles où la culture est en place, répartition par phase (US-194), phase la plus avancée présente, nombre de lots en pépinière. Aucune quantité de stock : c'est le rôle de Stocks
- [ ] CA4 : **Confiance du moment** — le geste le mieux noté à la date de référence et ses étoiles, tirés de **la même évaluation** que la pastille du Plan et la puce de Stocks (`confiances_de_culture`, US-180) ; sans calendrier pour la zone, aucune étoile (tiret), jamais une valeur par défaut (US-178 / CA5). Un test compare, pour une même culture et une même date, la valeur de cette lecture et celle de `GET /plan/confiances/candidates`
- [ ] CA5 : **Fenêtre** — pour chaque culture, l'état de sa prochaine fenêtre utile : *maintenant* (la date de référence est dans une fenêtre de semis ou de plantation — R1 à son maximum), *bientôt* (la fenêtre s'ouvre le mois suivant — R1 au barème du mois adjacent), *plus tard* (le prochain geste et ses mois), *aucune* (pas de calendrier pour la zone). Le libellé écrit (« semer maintenant », « prochaine fenêtre : semer en pépinière février → mars ») est mis en forme par le front
- [ ] CA6 : **Suggestion de la semaine** — au plus **trois** cultures absentes du potager (ni ligne en place, ni lot en cours), dont la fenêtre est *maintenant* et la confiance d'au moins deux étoiles, les mieux notées d'abord (à égalité, par nom), marquées comme suggestions. Ces seuils sont des décisions produit écrites à un seul endroit

*Lecture*
- [ ] CA7 : **Une seule requête** pour l'écran et **une seule lecture météo** (cache d'US-182), quel que soit le nombre de cultures ; aucune requête par culture. Le temps de réponse est mesuré sur une base de taille réelle avec les 84 fiches et consigné à la livraison ; au-delà d'une seconde, une mise en cache par potager et date de référence est ajoutée dans la même US
- [ ] CA8 : Les corrections locales du potager (fenêtres, durées corrigées au bot) sont prises en compte, comme sur le Plan (US-176 / CA2)
- [ ] CA9 : Lecture seule : aucun événement, stock, calendrier ni référentiel n'est modifié
- [ ] CA10 : Si la confiance ne peut pas être évaluée (météo indisponible), la réponse le dit et les cultures gardent tout le reste — frise, famille, présence — sans étoile de repli (US-180 / CA7)

*Définition de terminé*
- [ ] CA11 : Une fiche de domaine `docs/domaines/cultures-et-fiche.md` consigne le périmètre des deux onglets, la phase la plus avancée, les états de fenêtre et la règle de suggestion ; elle entre dans la table de `docs/domaines/README.md`
- [ ] CA12 : Des tests couvrent : périmètre des deux onglets, culture hors référentiel, culture seulement en pépinière, répartition par phase, égalité avec la confiance du Plan, états de fenêtre (y compris une fenêtre qui enjambe le 31 décembre), sélection et plafond des suggestions, culture sans calendrier, météo indisponible, correction locale, budget d'une requête

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse (lecture), consultation
- Migration BDD requise : **non**
- Dépendances : **US-194** (phase), US-176 (calendrier de zone), US-178 et US-180 (confiance et lecture groupée), US-065 (lots), US-067 (famille) — livrées sauf US-194
- Consommateur : US-205 (écran Cultures)
- Impact tokens : zéro
- Point de vigilance : **Stocks et Cultures ne doivent pas diverger**. La confiance est lue par la même fonction, à la même date de référence ; deux valeurs différentes pour une même culture au même instant sont un bug (point de vigilance d'US-183)
- Point de vigilance : la suggestion est une **lecture**, pas une recommandation personnalisée : elle ne tient compte ni des goûts ni des cultures passées du jardinier. Elle le dit (« fenêtre ouverte dans ta zone »)
- Wireframe : v1 § 2 et ses deux notes

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Une culture en récolte au potager
  Given des tomates en récolte dans deux parcelles, trois variétés
  When je lis la vue Cultures au 18 septembre
  Then la tomate figure dans "Au potager" avec 3 variétés, 2 parcelles et la phase "en récolte"
  And sa fenêtre est "plus tard" : semer en pépinière de février à mars

Scénario: Suggestion de la semaine
  Given aucun épinard n'est au potager ni en pépinière
  And la fenêtre de semis en place de l'épinard est ouverte au 18 septembre avec trois étoiles
  When je lis la vue Cultures
  Then l'épinard est marqué comme suggestion

Scénario: Au plus trois suggestions
  Given cinq cultures absentes du potager ont une fenêtre ouverte et au moins deux étoiles
  When je lis la vue Cultures
  Then seules les trois mieux notées sont marquées comme suggestions

Scénario: Même confiance que le Plan
  Given la pastille du Plan affiche pour le haricot "semer en place · ★★☆" au 19 septembre
  When je lis la vue Cultures au 19 septembre
  Then le haricot porte "semer en place" et deux étoiles

Scénario: Culture hors référentiel
  Given de la verveine plantée, inconnue du référentiel
  When je lis la vue Cultures
  Then la verveine figure dans "Au potager" avec la mention "hors référentiel"
  And elle n'a ni frise ni étoile
```

**Labels GitHub :** `us`, `backend`, `cultures`, `api`

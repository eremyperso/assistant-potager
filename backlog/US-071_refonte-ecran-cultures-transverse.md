> **CADUQUE (2026-08-15).** L'ambition de cet écran (vue transverse par famille
> botanique) est absorbée par l'écran Stocks, qui devient l'écran transverse
> unique du potager. Voir `docs/BRIEF_REFONTE_STOCKS_TRANSVERSE.md` et
> `docs/ANALYSE_REFONTE_UI_WEB_2026.md` §5.11. Les décisions déjà arbitrées
> ici (granularité culture+variété, parcelles multiples, famille/calendrier en
> mode dégradé, exposition/eau hors périmètre) sont reprises telles quelles par
> [US-072](US-072_detail-varietes-toutes-cultures-parcelles.md) et
> [US-073](US-073_refonte-ecran-stocks-transverse.md). Conservée ici pour
> l'historique, à ne plus implémenter comme écran séparé.

**ID :** US-071
**Titre :** Refondre l'écran Cultures (vue transverse par famille botanique)

**Story :**
En tant que jardinier utilisant l'interface web
Je veux une vue qui regroupe toutes mes cultures actuellement en place, quelle que soit la parcelle où elles se trouvent, groupées par famille botanique
Afin de raisonner mes cultures dans leur ensemble (combien de pieds de tomate au total, où sont-ils) sans avoir à parcourir chaque parcelle une par une

**Contexte fonctionnel :**
Première US du **Lot E — Cultures transverse** de la refonte de l'interface web (voir `docs/ANALYSE_REFONTE_UI_WEB_2026.md` §5.3 et §7.3). Aujourd'hui, une culture n'a aucune vue dédiée : elle n'existe qu'à travers le prisme de la parcelle qui la porte (écran Plan). La maquette (`web-screens.jsx`, `ScreenCultures`) introduit un écran séparé qui agrège les cultures en place de tout le potager, groupées par famille botanique, avec recherche et filtre.

**Décision produit (arbitrée avec l'utilisateur avant rédaction) : la fiche culture de cet écran reprend la symbolique déjà livrée de la tuile « Cultures en place » du Plan (`CultureTile`, `frontend/src/views/Plan.jsx`, US-060)** — pastille végétatif/reproducteur, nom + variété, quantité avec son unité réelle, ligne famille · durée, frise `MonthStrip` — plutôt que la fiche propre au prototype `ScreenCultures` (icône feuille générique, badges exposition/besoin en eau, lieu unique). Cette dernière suppose une parcelle unique par fiche, ce qui n'est pas vrai ici : une même culture peut être présente dans plusieurs parcelles. La fiche transverse ajoute donc la liste des parcelles d'origine, absente de la tuile du Plan car inutile à l'échelle d'une seule parcelle.

**Agrégation calculée à la volée, sans nouvel endpoint.** `GET /plan` renvoie déjà, par parcelle, chaque couple culture + variété avec sa quantité, son unité, son type d'organe et ses observations. Cet écran regroupe ces lignes **côté frontend** par couple (culture, variété) normalisé, additionne les quantités (l'unité est une propriété de la culture, donc homogène pour un même couple) et liste les parcelles d'origine. Aucune migration, aucun endpoint nouveau — cohérent avec la décision déjà actée en §5.3 : « une lecture transverse des entités déjà en base », pas une nouvelle entité.

**Périmètre du calendrier cultural et de la famille — identique à US-060.** Cet écran lit les mêmes tables provisoires que le Plan (`frontend/src/lib/familles.js`, `frontend/src/lib/calendrier.js`), avec le même mode dégradé pour une culture absente. Il est donc livrable indépendamment de US-067 (famille en base) et de `EPIC_CALENDRIER_CULTURAL` (US-068 à US-070) — ces US remplaceront la source de données sans changer l'écran.

**Exposition et besoin en eau — hors périmètre, décision produit.** Contrairement à la famille et à la durée, ces deux badges de la maquette n'ont **aucune table de correspondance, même provisoire** : c'est un manque plus profond que celui déjà tracé pour famille/calendrier. Plutôt que d'inventer une source de données non demandée, cette US les **omet** — comme la pastille « Sol » omise par US-060. Leur traitement (nouvelle table provisoire, ou schéma étendu de `CultureConfig`) est reporté à une US ultérieure du Lot E si le besoin se confirme.

**Périmètre confirmé par l'analyse (§5.3) : les cultures en pépinière (godets, pas encore en place) sont exclues de cette vue.** `GET /plan` ne portant que les cultures effectivement en parcelle, cette exclusion est déjà garantie par la source de données, sans filtre supplémentaire à écrire.

**Critères d'acceptance :**

*Structure et filtres*
- [ ] CA1 : L'écran affiche une barre de filtres avec un champ de recherche (nom de culture ou de variété) et un sélecteur de famille botanique (« Toutes les familles » + liste des familles réellement présentes), tous deux issus du design system
- [ ] CA2 : Les cultures sont regroupées par famille botanique dans des sections repliables (composant `GroupHead`, repris tel quel de l'écran Pépinière, US-061), chaque en-tête portant le nom de la famille, le nombre de cultures du groupe, et le total de pieds du groupe — ce total n'additionnant que les couples culture/variété effectivement comptés en plants, comme la règle déjà appliquée au Plan (CA6 d'US-060)
- [ ] CA3 : La grille de fiches se répartit selon la largeur du conteneur, aux paliers de la maquette (`.wcat-grid`) : **une colonne par défaut, deux à partir de 600 px de conteneur, trois à partir de 1024 px, quatre à partir de 1400 px** — jamais de breakpoint d'écran (règle « Responsive » de `CLAUDE.md`)
- [ ] CA4 : Seules les cultures effectivement en place dans au moins une parcelle apparaissent. Une culture uniquement présente en pépinière (lot en godet, non encore planté) n'apparaît pas dans cet écran

*Fiche culture — reprise de la tuile du Plan*
- [ ] CA5 : Chaque fiche reprend la structure de `CultureTile` (Plan, US-060) : pastille végétatif/reproducteur, nom de la culture en serif, variété en italique à côté, quantité totale alignée à droite **avec son unité réelle** (jamais convertie en nombre de plants pour une culture suivie en m² ou en graines), ligne « famille · durée », et calendrier des douze mois (`MonthStrip`)
- [ ] CA6 : Chaque fiche affiche en plus la ou les parcelles où la culture est présente (« lieu(x) »), absente de la tuile du Plan car inutile à l'échelle d'une seule parcelle
- [ ] CA7 : La granularité d'une fiche est le couple (culture, variété) normalisé, jamais la seule culture : deux variétés d'une même culture (ex. Tomate Cœur de bœuf et Tomate Cerise) sont deux fiches distinctes, chacune listant ses propres parcelles et sa propre quantité
- [ ] CA8 : Les données de chaque fiche sont calculées côté frontend en agrégeant les cultures renvoyées par `GET /plan` sur l'ensemble des parcelles du potager, par couple (culture, variété) normalisé — aucun nouvel endpoint, aucune migration

*Calendrier cultural et famille — valeurs standard, périmètre figé (identique à US-060)*
- [ ] CA9 : La ligne « famille · durée » et la frise `MonthStrip` lisent les mêmes tables de correspondance provisoires que le Plan (`familles.js`, `calendrier.js`). Une culture absente de ces tables s'affiche en **mode dégradé** : frise entièrement neutre, famille et durée en tiret — jamais de valeur horticole inventée
- [ ] CA10 : Le mois mis en évidence sur chaque frise suit la **date de référence** de l'application (US-030/031), via le même paramètre `moisRef` que `CultureTile`
- [ ] CA11 : Cette US ne dépend ni de US-067 (famille en base) ni d'`EPIC_CALENDRIER_CULTURAL` (US-068 à US-070) — la dette est la même que celle déjà tracée pour l'écran Plan, pas une dette nouvelle

*Hors périmètre — décision produit*
- [ ] CA12 : Les badges Exposition et Besoin en eau de la maquette ne sont **pas affichés** dans cette version : aucune donnée ni table provisoire n'existe pour ces deux attributs, et aucune valeur n'est inventée pour les faire apparaître
- [ ] CA type (US avec impact visuel/UI) : Le rendu de l'écran correspond visuellement à la maquette de référence à 375px/768px/desktop, à l'exception des écarts listés ci-dessus (fiche reprenant `CultureTile` plutôt que la fiche du prototype, badges exposition/eau omis)

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non
- Dépendances : US-052 (design system), US-053 (coquille de navigation à deux niveaux, entrée « Cultures »), US-060 (tuile `CultureTile` réutilisée), US-061 (`GroupHead` réutilisé), US-030/031 (date de référence). **Aucune dépendance à US-067, US-068, US-069 ni US-070**, pour les mêmes raisons que US-060 (CA9 à CA11)
- Écarts assumés avec la maquette, à documenter dans `docs/ANALYSE_REFONTE_UI_WEB_2026.md` sur le modèle du §5.10 une fois l'écran livré :
  - **remplacé** : la fiche culture du prototype (icône feuille, badges expo/eau, lieu unique) par la tuile `CultureTile` du Plan, augmentée de la liste des parcelles d'origine
  - **omis** : badges Exposition et Besoin en eau (aucune donnée, aucune table provisoire)
  - **ajouté par rapport à la tuile du Plan** : liste des parcelles d'origine, pertinente uniquement à l'échelle transverse

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Agrégation d'une culture présente dans plusieurs parcelles
  Given des tomates Cœur de bœuf sont plantées dans la parcelle "Maison" et dans la parcelle "Serre"
  When l'utilisateur consulte l'écran "Cultures"
  Then une seule fiche "Tomate Cœur de bœuf" s'affiche
  And elle indique les deux parcelles "Maison" et "Serre"
  And sa quantité est la somme des plants des deux parcelles

Scénario: Deux variétés d'une même culture restent distinctes
  Given des tomates Cœur de bœuf et des tomates Cerise sont plantées au potager
  When l'utilisateur consulte l'écran "Cultures"
  Then deux fiches distinctes s'affichent, une par variété

Scénario: Exclusion des cultures en pépinière
  Given un lot de courgettes est en godet, pas encore planté en parcelle
  And ce même lot n'a aucune plantation enregistrée
  When l'utilisateur consulte l'écran "Cultures"
  Then aucune fiche "Courgette" n'apparaît pour ce lot

Scénario: Quantité affichée dans son unité de saisie
  Given une carotte semée sur 2 m² dans une parcelle
  When l'utilisateur consulte l'écran "Cultures"
  Then la fiche "Carotte" affiche "2 m²" et non un nombre de plants

Scénario: Culture sans métadonnée horticole
  Given une culture "topinambour" absente des tables de familles et de calendrier
  When l'utilisateur consulte l'écran "Cultures"
  Then sa fiche affiche des tirets pour la famille et la durée
  And son calendrier reste neutre, sans mois coloré

Scénario: Regroupement par famille botanique
  Given deux tomates et une courgette sont en place au potager
  When l'utilisateur consulte l'écran "Cultures"
  Then le groupe "Solanacée" affiche 2 cultures
  And le groupe "Cucurbitacée" affiche 1 culture

Scénario: Filtre par recherche
  Given le potager compte des tomates, des courgettes et des oignons
  When l'utilisateur saisit "tom" dans la recherche
  Then seules les fiches dont le nom ou la variété contient "tom" restent visibles
```

**Labels GitHub :** `us`, `sprint-refonte-ui-2026`, `frontend`, `cultures`

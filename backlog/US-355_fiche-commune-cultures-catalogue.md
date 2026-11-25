**ID :** US-355
**Titre :** Ouvrir partout la fiche commune et refaire Cultures (Au potager, Catalogue)
**Épic :** ÉPIC 21 — Socle commun des vues

**Story :**
En tant que jardinier
Je veux que toucher une culture, où qu'elle apparaisse, ouvre toujours la même fiche, et que l'écran Cultures me montre d'abord ce qui demande une action puis le catalogue des espèces à ajouter
Afin de ne plus chercher entre deux fiches et de savoir quoi semer ensuite

**Contexte fonctionnel :**
Vague 2 de l'ÉPIC 21. La référence est la maquette (Cultures · au potager, Fiche commune, Cultures · catalogue ; Ordinateur).
Il y a aujourd'hui deux fiches : `FicheCulture` (US-207, l'espèce en six sections) et `SuiviCulture` (US-322, la culture en place). La fiche commune les réunit (D4) : l'onglet **Suivi** reprend `SuiviCulture`, l'onglet **Référence** reprend le contenu de `FicheCulture`. Le catalogue lit `GET /cultures/vue` (US-204), qui rend déjà les espèces du référentiel visibles par le potager, leur présence au potager et leur fenêtre utile.

**Critères d'acceptance :**
- [ ] CA1 : **Fiche commune**, ouverte de la même façon depuis le Tableau de bord, le Plan, Cultures, les Stocks et le Journal (feuille sur mobile, panneau droit sur ordinateur) :
  - en-tête : emoji 52 px, nom en Lora 21 px, « variété · quantité », ×
  - emplacement « Planche centrale · rang 3 — Voir au plan → »
  - étape courante en puce, « depuis le 20 oct. » (ou l'état prévu en orange s'il est dû)
  - total récolté et nombre de récoltes pour une culture qui en a
  - bouton **Noter** (« Noter la levée » si l'étape est prévue), qui ouvre Gaston sur cette culture (US-358)
- [ ] CA2 : Onglet **Suivi** : la frise verticale des étapes (réalisées avec leur date, prévue hachurée avec « prévu », suivantes grisées), le **Carnet de la culture** (récoltes, gestes et notes du jardinier du plus récent au plus ancien, notes en Kalam avec « Dicté » ou « Écrit », « Voir dans le Journal → » filtré sur la culture) et l'**Origine** (« Pépinière · lot #18, semé le 2 juin », « Semis direct », « Achat · 3 têtes »)
- [ ] CA3 : Onglet **Référence** : le calendrier de l'espèce à initiales, l'espacement, la rotation, puis les sections de `FicheCulture` (Maintenant, Référentiel, Variétés, Voisinages, Bioagresseurs) sans perte de ses critères (US-207 CA3, CA12 : une section non lue le dit à sa place). « Ouvrir la fiche calendrier » empile toujours `FicheCalendrier`
- [ ] CA4 : **Cultures · Au potager** : onglets d'en-tête « Au potager · n » et « Catalogue · n ». Légende du calendrier repliable (« Survolez un mois » ou « Appui long sur un mois » : son geste). Groupes **par ce qui demande une action** : À confirmer, En récolte, En croissance, Semé ou planté, Terminé · rang à libérer. Une carte montre la pastille, l'emoji, le nom, la variété, l'état (en orange s'il est dû), le calendrier 12 mois et l'emplacement. Grille d'une colonne, puis deux à partir de 700 px de conteneur. Les pastilles de famille (US-204 CA3) passent dans **Filtrer**
- [ ] CA5 : **Mot de Gaston de Cultures** : levées dues et retards → « **3 levées à confirmer.** L'épinard de la serre a 2 semaines de retard : un coup d'œil aujourd'hui ? » → *Confirmer la fève* (Gaston sur la première levée due)
- [ ] CA6 : **Cultures · Catalogue** : les espèces non présentes au potager, **rangées par prochaine fenêtre de semis** (« À semer d'ici mars · n », « Plus tard dans la saison · n »), puis « Déjà au potager · n ». Une carte montre l'emoji, le nom, le nombre de variétés, la famille, le calendrier, « Prochaine fenêtre : semer en pépinière chaude en mars » ou la parcelle si la culture est au potager. Pas de bouton date dans la barre d'outils. En bas : « 🎤 Une culture absente du catalogue ? Dites-la à Gaston »
- [ ] CA7 : **Fiche catalogue** : pilule « Pas encore au potager » ou « Au potager », la fenêtre, **Ajouter à mon potager** (ou « Ouvrir la culture en place », qui bascule sur la fiche commune), puis calendrier, variétés du catalogue, espacement et famille (« Gaston choisira une parcelle qui respecte la rotation »). **Ajouter n'écrit rien** : il ouvre Gaston (US-358)
- [ ] CA8 : **Mot de Gaston du Catalogue** : la prochaine espèce à semer et la place qui se libère → « **Le céleri-rave se sème en mars**, en serre chaude. Votre châssis aura de la place après les choux pommés. » → *Ajouter le céleri-rave*
- [ ] CA9 : Aucune règle d'étape, de fenêtre ou de confiance n'est recalculée côté front (US-204 CA7). Les comptes des onglets viennent de la lecture
- [ ] CA type : Le rendu correspond visuellement à la maquette de référence à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non
- Dépendances : US-353 ; US-204 (vue Cultures), US-206/US-207 (fiche culture), US-322 (suivi de culture), US-183 (fiche calendrier)
- Modèle / effort conseillé : **Sonnet 5.5, `high`** — fusion de deux fiches avec leurs critères hérités, ouverte depuis cinq vues ; ni Opus ni Fable ne sont requis

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Given le chou de Bruxelles est en récolte depuis le 20 oct. avec 4 récoltes pour 2,9 kg
When le jardinier le touche depuis le Journal, puis depuis le Plan
Then la même fiche s'ouvre les deux fois
And l'onglet Suivi montre Planté 3 juil., En croissance 20 juil., En récolte 20 oct., puis Terminé grisé
And le carnet de la culture montre "Récolte · 1,2 kg" avec sa note dictée en Kalam

Given le céleri-rave n'est pas au potager et se sème en mars
When le jardinier ouvre Cultures › Catalogue
Then le céleri-rave est dans "À semer d'ici mars"
When il touche "Ajouter à mon potager"
Then Gaston s'ouvre sur le céleri-rave et rien n'est encore enregistré
```

**Labels GitHub :** `us`, `frontend`, `pwa`, `cultures`, `fiche-culture`, `socle`

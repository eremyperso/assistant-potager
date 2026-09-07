**ID :** US-174  
**Titre :** Faire entrer les bioagresseurs dans la fiche courte d'une culture  
**Épic :** ÉPIC 6 — Référentiel de connaissance des cultures

**Story :**
En tant que jardinier
Je veux voir dans la fiche d'une culture ce qui est susceptible de l'attaquer, avec le reste de ce que l'application sait d'elle
Afin de n'avoir ni à connaître une seconde commande, ni à me souvenir que cette information existe

**Contexte fonctionnel :**

`/fiche <culture>` (US-164) est le seul endroit de l'application qui rassemble ce qui est su d'une
culture : sa famille botanique, le délai de retour de cette famille, ses quatre attributs
agronomiques de conduite, sa description, et les attributions de source correspondantes. Le tout
assemblé depuis la base, sans un jeton.

US-162 y a ajouté une matière que la fiche ignore : **68 identités de bioagresseurs et 335 arêtes
vers les cultures**. Un jardinier qui consulte la fiche de la tomate voit son exposition et son
besoin en eau, mais rien du mildiou — alors que l'information est en base, à une jointure de là.

La conception de l'épic prévoyait explicitement l'inverse : la vue Cultures y est décrite comme une
« fiche riche : famille, exposition, eau, calendrier, **associations, bioagresseurs** »
(`docs/CONCEPTION_REFERENTIEL_CONNAISSANCE_CULTURES.md` §5.3). La rubrique n'est pas une idée
nouvelle, c'est une rubrique annoncée et non branchée.

**Une contrainte de conception apparaît ici, et elle est structurante.** La fiche courte est
aujourd'hui **aveugle au potager** : elle se génère à partir du seul nom de culture. Or les
bioagresseurs, eux, obéissent au pattern d'isolation d'US-162 — un potager peut en déclarer un chez
lui, et il ne doit jamais fuir ailleurs. Ajouter la rubrique impose donc de rendre la fiche
consciente du potager qui la demande. C'est le vrai travail de cette US ; l'affichage, lui, est
trivial.

**Ce que cette US n'est pas.** Elle ne rend pas la fiche bavarde. La fiche courte est courte, et
c'est sa qualité : une culture porte parfois quinze bioagresseurs (mesuré sur la tomate au
07/09/2026), les lister tous ferait de la fiche un catalogue illisible sur un écran de téléphone.
Le CA4 tranche ce point plutôt que de le laisser au hasard du contenu.

**Critères d'acceptance :**

*La rubrique*
- [ ] CA1 : La fiche courte porte une rubrique **« À surveiller »** listant les bioagresseurs rattachés à la culture, ordonnés par fréquence (`courant` d'abord), puis par nom — l'ordre métier d'US-162, jamais recalculé ici
- [ ] CA2 : Chaque ligne porte le nom commun français et sa fréquence. La période de risque est affichée quand elle est renseignée, et **rien** sinon — pas de « période non renseignée » répété quinze fois dans une fiche qui doit rester lisible
- [ ] CA3 : Un bioagresseur propre au potager qui consulte est **distingué visuellement** de la connaissance partagée, comme il l'est déjà dans `/bioagresseur lister`
- [ ] CA4 : 🔶 **La fiche courte reste courte.** Au plus **cinq** bioagresseurs affichés, les plus fréquents d'abord ; au-delà, une ligne indique combien restent et par quelle commande les voir tous. Le nombre est un paramètre nommé du module, pas une constante enfouie
- [ ] CA5 : Une culture **sans aucun bioagresseur rattaché** n'affiche pas une rubrique vide : elle affiche la même honnêteté que partout ailleurs — l'information n'est pas connue, ce qui ne veut pas dire que la culture n'est pas exposée (CA12 d'US-162)

*L'isolation, qui est le vrai sujet*
- [ ] CA6 : 🔴 La fiche courte devient **consciente du potager** qui la demande. Un bioagresseur déclaré localement par un potager n'apparaît jamais dans la fiche servie à un autre potager. La signature du service change ; tous ses appelants sont mis à jour
- [ ] CA7 : Le reste de la fiche est **inchangé** par cette évolution : famille, délai de retour, attributs de conduite et description restent partagés et rendus à l'identique. Rendre la fiche consciente du potager ne doit rien rendre privé qui ne l'était pas

*Sources et honnêteté*
- [ ] CA8 : Les attributions des sources dont dérivent les bioagresseurs rejoignent celles déjà portées par la fiche, **dédupliquées** dans la même mention unique — jamais une seconde ligne « Source : » séparée
- [ ] CA9 : **Aucun dosage, aucune recommandation d'emploi d'un produit** — réaffirmation du CA10 d'US-162, à l'endroit précis où la tentation d'ajouter « que faire » est la plus forte
- [ ] CA10 : Aucun texte narratif n'est produit : la fiche liste des identités, elle ne décrit ni symptôme ni conduite à tenir (CA11 d'US-162). Le narratif viendra d'US-140, ingéré par US-098

*Coût*
- [ ] CA11 : La fiche reste servie **à zéro jeton et sans appel réseau**, comme le pose le CA1 d'US-164. La rubrique ajoutée est une lecture de base, rien d'autre
- [ ] CA12 : Aucune restitution spontanée n'est introduite : la fiche reste servie sur commande explicite, jamais poussée (CA4 d'US-164)

*Tests*
- [ ] CA13 : Des tests couvrent l'ordre par fréquence, la troncature au-delà du seuil du CA4, la culture sans bioagresseur, l'isolation d'un bioagresseur local entre deux potagers, la déduplication des attributions, l'absence d'appel au modèle, et la non-régression des rubriques existantes de la fiche

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : **non** — les tables d'US-162 suffisent
- Dépendances : **US-162** (bloquante — les tables et le service de lecture), **US-164** (la fiche courte, étendue ici). Aucune dépendance à US-173, qui touche un autre chemin d'accès : les deux peuvent être livrées dans n'importe quel ordre
- **Arbitrage tranché — cinq lignes, pas quinze :** la fiche courte doit tenir sur un écran de téléphone. Une rubrique qui déborde ferait perdre les rubriques suivantes, qui sont lues elles aussi. Le seuil est un paramètre nommé pour rester révisable en produit, pas une valeur à rediscuter à chaque culture
- **Arbitrage tranché — la conscience du potager est le cœur de l'US :** l'affichage tient en une dizaine de lignes ; c'est le passage d'un service global à un service scopé qui demande de la rigueur, et c'est là que se logerait une fuite de données entre potagers
- Prérequis fonctionnel de la **vue Cultures de la PWA** (conception §5.3), qui consommera la même fiche enrichie sans la réassembler

**Notes techniques (pour Persona Developer) :**
- `app/services/fiche_culture.generer_fiche_courte(db, culture)` ne prend aujourd'hui aucun `potager_id` : c'est cette signature qui change, et `bot.cmd_fiche` doit lui passer le contexte courant. Repérer tous les appelants avant de modifier
- `FicheCourte.attributions` déduplique déjà les mentions de source ; les attributions des bioagresseurs doivent y entrer par le même chemin, pas à côté
- La lecture passe par le service d'US-162, qui porte déjà l'ordre par fréquence, l'isolation et la recomposition d'attribution — aucune requête réécrite pour l'occasion

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: La fiche dit ce qui attaque la culture
  Given une culture "tomate" reliée à plusieurs bioagresseurs
  When le jardinier consulte la fiche de la tomate
  Then une rubrique liste les bioagresseurs, les plus fréquents d'abord
  And aucun appel à un modèle de langage n'a lieu

Scénario: La fiche reste courte
  Given une culture reliée à quinze bioagresseurs
  When le jardinier consulte sa fiche
  Then au plus cinq sont affichés
  And une ligne indique combien restent et comment les voir tous

Scénario: Culture sans bioagresseur rattaché
  Given une culture "ail" sans aucun bioagresseur rattaché
  When le jardinier consulte sa fiche
  Then la fiche indique que l'information n'est pas connue
  And elle n'en conclut pas que la culture n'est pas exposée

Scénario: Un bioagresseur local ne fuit pas d'un potager à l'autre
  Given un bioagresseur déclaré pour le potager "Jardin de Vitry"
  When un jardinier d'un autre potager consulte la fiche de la même culture
  Then ce bioagresseur ne lui est pas restitué
  And la famille, les attributs et la description restent identiques pour les deux

Scénario: Une seule mention de source
  Given une culture dont la famille et les bioagresseurs viennent de sources différentes
  When le jardinier consulte sa fiche
  Then une seule ligne de source rassemble les attributions, sans doublon

Scénario: La fiche ne prescrit rien
  Given une culture attaquée par un bioagresseur pour lequel des traitements existent
  When le jardinier consulte sa fiche
  Then aucun produit ni dosage n'est mentionné
```

**Labels GitHub :** `us`, `sprint-epic6-referentiel`, `backend`, `referentiel`, `consultation`

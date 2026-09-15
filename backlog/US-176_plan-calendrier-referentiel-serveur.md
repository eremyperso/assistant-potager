**ID :** US-176
**Titre :** Afficher sur l'écran Plan le calendrier cultural du référentiel au lieu de la table provisoire

**Story :**
En tant que jardinier
Je veux que la frise des douze mois de chaque culture, sur l'écran Plan, reflète le calendrier cultural de mon potager — sa zone climatique et les corrections que j'ai faites depuis le bot
Afin de planifier ma saison sur des périodes adaptées à mon climat, et de voir immédiatement l'effet d'une correction plutôt que des valeurs génériques figées dans l'application

**Contexte fonctionnel :**
L'écran Plan (US-060) affiche sur chaque tuile de culture une frise de douze mois et une ligne « famille · durée ». Ces valeurs viennent d'une **table provisoire embarquée dans l'interface**, identique pour tous les potagers : elle ignore la zone climatique, ignore les corrections faites au bot avec `/calendrier`, et découpe l'année en « semis / plantation / récolte », découpage que le référentiel a abandonné.

US-068 a depuis constitué le vrai référentiel : fenêtres par zone climatique (semis en pépinière, semis en pleine terre, récolte), durées communes à toutes les zones, corrections locales au potager, et une forme de lecture exposée par l'API. Plusieurs documents annonçaient que la table provisoire « disparaîtrait avec US-068 » — mais US-068 ne crée aucun écran, et aucun critère d'acceptance de US-068 ni de US-070 ne confie ce branchement à qui que ce soit. **Aujourd'hui, un jardinier qui corrige un calendrier au bot ne voit rien changer sur l'écran Plan.** Cette US solde cette dette.

Elle se limite au **calendrier conseillé**. Le recalage sur les événements réels de la parcelle, le quatrième état « en croissance », la durée restante et la prochaine plage de semis restent le périmètre d'**US-070**, qui s'appuiera sur ce branchement.

**Critères d'acceptance :**
- [ ] CA1 : Sur l'écran Plan, la frise de chaque culture affiche les **fenêtres du référentiel** telles que les lit le potager consulté : zone climatique du potager, et corrections locales faites depuis le bot prioritaires sur le calendrier partagé. Aucune valeur ne provient plus d'une table embarquée dans l'interface
- [ ] CA2 : Une correction faite au bot (`/calendrier fenetre …`, `/calendrier duree …`, `/calendrier zone …`) est visible sur l'écran Plan **au prochain chargement de l'écran**, sans livraison ni rechargement du cache applicatif
- [ ] CA3 : La frise distingue les **trois phases du référentiel** — semis en pépinière, semis en pleine terre, récolte — et sa légende les nomme ainsi. La phase « plantation » disparaît de la frise : le référentiel ne la connaît pas, et elle n'est **jamais reconstituée** à partir du semis en pépinière et du délai de repiquage (ce serait une projection, qui relève d'US-070)
- [ ] CA4 : La ligne « famille · durée » affiche la durée **semis → première récolte** du référentiel, dans sa forme de lecture (fourchette « 70 à 90 jours », mention « vivace »), ou un tiret quand elle n'est pas renseignée. Aucune durée n'est jamais présentée comme une date
- [ ] CA5 : Quand une culture porte **plusieurs itinéraires** (« standard », « culture d'hiver »…), la tuile affiche l'itinéraire par défaut du référentiel ; si l'itinéraire affiché n'est pas « standard », son nom est indiqué sur la tuile. Aucune fusion de plusieurs itinéraires en une seule frise
- [ ] CA6 : Une culture **sans calendrier renseigné pour la zone du potager** — culture absente du référentiel, culture connue sans fenêtre, ou fenêtres renseignées pour une autre zone seulement — s'affiche en **mode dégradé** : frise entièrement neutre, durée en tiret. Aucune fenêtre n'est empruntée à une zone voisine, ni à l'ancienne table provisoire
- [ ] CA7 : La **famille botanique** reste affichée pour une culture sans calendrier. Aujourd'hui son affichage dépend de la présence de la culture dans la table provisoire : ce couplage disparaît, la famille ne dépend plus que de sa propre donnée (US-067)
- [ ] CA8 : La **zone climatique** retenue et son origine — choisie par le jardinier, déduite de la localisation, ou appliquée par défaut — sont lisibles sur l'écran Plan, une seule fois (et non répétées sur chaque tuile), avec la manière de la changer depuis le bot
- [ ] CA9 : Quand des valeurs affichées proviennent d'une source sous licence imposant une **attribution** (Wind River Greens, CC BY 4.0), cette attribution est visible sur l'écran Plan, une seule fois pour l'ensemble des cultures affichées
- [ ] CA10 : Le **mois mis en évidence** continue de suivre la date de référence de l'écran (US-060 / CA10) ; reculer la date de référence ne change pas les fenêtres conseillées affichées
- [ ] CA11 : L'écran Plan **ne ralentit pas** de façon perceptible : le calendrier de toutes les cultures affichées est obtenu en une seule lecture groupée, jamais par une requête par tuile, et la frise ne clignote pas d'un état neutre vers son état renseigné une fois l'écran affiché
- [ ] CA12 : Si la lecture du calendrier échoue (serveur indisponible, erreur), l'écran Plan reste utilisable : parcelles, cultures, quantités et familles s'affichent, les frises passent en mode dégradé, et aucune valeur de repli n'est affichée
- [ ] CA13 : La **table provisoire est supprimée** du frontend. Les documents qui l'annonçaient (en-tête de la table, §5.10 de `ANALYSE_REFONTE_UI_WEB_2026.md`, CA11 d'US-060) sont mis à jour pour indiquer qu'elle a été soldée par cette US et non par US-068
- [ ] CA14 : Le composant de frise partagé évolue de façon **rétrocompatible** : les autres écrans et l'aperçu du design system qui l'utilisent s'affichent à l'identique, sans modification de leur part
- [ ] CA15 : La fiche d'aide du corpus « fonctionnement de l'application » qui décrit le calendrier (`calendrier-et-zone-climatique.md`) est relue et corrigée dans la même livraison si elle devient inexacte, conformément à la règle de définition de terminé du corpus (US-099 / CA9)
- [ ] CA16 : Le rendu correspond visuellement à la maquette de référence de l'écran Plan (US-060) à 375px / 768px / desktop, légende de la frise comprise
- [ ] CA17 : Des tests couvrent : fenêtres lues depuis le référentiel, correction locale prioritaire, zone du potager, trois phases et absence de plantation, itinéraire non standard nommé, les trois cas du mode dégradé du CA6, famille affichée sans calendrier, attribution, échec de lecture, et non-régression des autres usages du composant de frise

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (écran Plan de la PWA)
- Migration BDD requise : non
- Épic de rattachement : calendrier cultural (`docs/EPIC 5 - CALENDRIER CULTURAL/EPIC_CALENDRIER_CULTURAL.md`) — nom d'épic non encore déclaré dans la liste des épics du Persona PO
- Dépendances : **US-068** (référentiel et forme de lecture), **US-060** (écran Plan), **US-067** (famille lue côté serveur). **US-070** en est la consommatrice : le recalage sur le réel viendra se poser sur cette frise
- Point de vigilance — **régression visible assumée** : des cultures que la table provisoire couvrait n'ont aucun calendrier dans le référentiel (ail, échalote, pomme de terre, fraise, framboise, épinard, céleri…, exclues par US-068 faute de source fiable). Leur frise deviendra neutre. C'est le comportement voulu (« aucune date inventée ») ; le jardinier peut les compléter au bot. Ce point est à annoncer dans les notes de version
- Point de vigilance — **perte de la bande « plantation »** : pour une tomate, la frise passe de « semis / plantation / récolte » à « semis en pépinière / récolte ». Le délai de repiquage reste consultable par `/calendrier` ; sa projection en mois relève d'US-070
- Point de vigilance — le **contexte de semis** (US-069) n'intervient pas ici : la frise conseillée montre les deux façons de semer quand le référentiel les connaît. Choisir la fenêtre d'un semis réel est le travail d'US-070
- Les fenêtres étant affichées au mois, une fenêtre qui chevauche la fin d'année (ex. novembre → février) doit colorer les bons mois des deux côtés de l'année

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Frise lue depuis le référentiel de la zone du potager
  Given mon potager est en zone "méditerranéen"
  And le référentiel de la tomate a une fenêtre de semis en pépinière "février-mars" pour cette zone
  When j'ouvre l'écran Plan sur une parcelle contenant des tomates
  Then la frise de la tomate colore février et mars en "semis en pépinière"
  And aucune bande "plantation" n'est affichée

Scénario: Une correction au bot se voit sur l'écran Plan
  Given j'ai corrigé au bot "/calendrier fenetre tomate pepiniere mars-avril"
  When je recharge l'écran Plan
  Then la frise de la tomate colore mars et avril en "semis en pépinière"
  And un autre potager voit toujours le calendrier partagé

Scénario: Culture sans calendrier
  Given l'ail n'a aucune fenêtre renseignée dans le référentiel
  When j'ouvre l'écran Plan sur une parcelle contenant de l'ail
  Then la frise de l'ail est entièrement neutre
  And la durée affiche un tiret
  And sa famille botanique reste affichée

Scénario: Zone et attribution affichées une seule fois
  Given aucune zone n'a été choisie et le potager est localisé à Strasbourg
  When j'ouvre l'écran Plan
  Then je lis que la zone "continental" est déduite de la localisation
  And l'attribution de la source du calendrier est visible une seule fois

Scénario: Lecture du calendrier en échec
  Given le calendrier ne peut pas être lu
  When j'ouvre l'écran Plan
  Then les parcelles et leurs cultures s'affichent normalement
  And toutes les frises sont neutres
  And aucune valeur de repli n'est affichée
```

**Labels GitHub :** `us`, `frontend`, `pwa`, `cultures`

**ID :** US-216
**Titre :** Ouvrir la fiche d'un lot et y faire ses gestes — le poste de terrain à 375 px
**Épic :** ÉPIC 12 — Pépinière : le poste de travail sous abri *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux, debout devant une barquette, le téléphone dans une main gantée, ouvrir son lot et faire le geste du moment en un appui — repiquer, noter la levée, mettre en terre, déclarer une perte
Afin de saisir ce qui se passe dans ma pépinière là où ça se passe, au lieu de m'en souvenir le soir

**Contexte fonctionnel :**
La v2 dessine deux fois la même chose : le **panneau « Lot sélectionné »** à côté de la liste sur desktop (§ 3), et l'**écran de terrain** à 375 px (§ 3c) — échéance en tête, « Le geste, en un appui » en quatre gros boutons, le compteur « Noter la levée », et cette règle : « Le même écran s'ouvre par scan d'étiquette **ou** depuis la liste des lots. Le scan ne fait que remplacer la navigation ; il n'ajoute aucun chemin d'écriture. » La note qui justifie tout l'écran : « Tout ce qui manque à l'application se saisit debout devant une plaque : le nombre de levés, la perte, le repiquage. […] il faut aujourd'hui ouvrir l'app, trouver la pépinière, trouver le lot — trois écrans avant le premier chiffre. »

Cette US crée cette **fiche du lot**, un seul composant pour les deux formes. Les gestes passent par le geste pré-rempli confirmé au compagnon (US-196) : la fiche prépare, le compagnon enregistre.

⚖️ **Conception avant implémentation (RT9)** : wireframe v2 § 3 (panneau) et § 3c (terrain), maquette haute fidélité gelée avant le code.

**Critères d'acceptance :**

*Ouverture*
- [ ] CA1 : La fiche s'ouvre depuis une ligne de l'onglet « Aujourd'hui » (US-215), une barre de l'onglet « Calendrier » (US-218), un lot de l'onglet « Emplacements » (US-219), le champ « Aller au lot n° » et l'adresse `/?vue=pepiniere&lot=128` (US-209, US-195), un lot de la fiche culture (US-207) et, en option, le scan d'une étiquette (US-221)
- [ ] CA2 : Forme : panneau à côté de la liste quand le conteneur fait au moins 900 px, fenêtre modale « adaptative » sinon — plein écran à 375 px. Ouverte depuis la liste, elle ne fait **aucune lecture** de plus ; ouverte par numéro ou par l'adresse, une seule (`GET /pepiniere/lots/{numero}`)

*Contenu*
- [ ] CA3 : **En tête** : « #128 · Chou frisé », variété, « semé le 1er septembre · 18 j », emplacement et type de pépinière (US-210, US-208). Le nom de la culture ouvre sa fiche culture (US-207)
- [ ] CA4 : **Échéance** (US-214), en clair et datée, en teinte d'alerte si le lot est en retard : « En retard de 6 jours — repiquage attendu entre le 11 et le 13 septembre ». Échéance incalculable : la raison. Aucun conseil agronomique rédigé (RT2)
- [ ] CA5 : **Traçabilité** : graines semées (prélevées au stock), levés et taux de levée (US-212), plants repiqués en godet, pertes déclarées, plants vendus, plants mis en terre, godets restants, graines encore en germination. Un tiret signifie « aucun geste de ce type », jamais zéro ; une incohérence de saisie reste visible (US-065)
- [ ] CA6 : « **Où les mettre** » quand le lot a des godets disponibles (US-217)
- [ ] CA7 : « **Détail du lot** » ouvre le cycle de vie existant du lot (modale d'US-061), déplacements compris (US-211)

*Les gestes*
- [ ] CA8 : « Le geste, en un appui » : les boutons pertinents pour l'état du lot, l'**action suggérée** (US-214) en premier et en principal — *Repiquer en godet* (s'il reste des graines en germination), *Noter la levée* (si la levée n'est pas terminée ; présent une fois US-212 livrée), *Mettre en terre* (s'il reste des godets), *Déclarer une perte* (s'il reste quelque chose), *Déplacer* (si le potager compte au moins deux pépinières ; présent une fois US-211 livrée), *Clôturer* (si le lot est dormant). Le lot « godets sans semis rattaché » n'a ni *Repiquer* ni *Noter la levée*
- [ ] CA9 : Chaque bouton prépare le geste pré-rempli (US-196) avec le lot, la culture, la variété et la date, et les quantités connues proposées (levés pour un repiquage, godets disponibles pour une mise en terre ou une clôture) ; aucune écriture dans la PWA. *Déplacer* propose les autres pépinières du potager ; *Mettre en terre* propose les suggestions d'US-217
- [ ] CA10 : **Noter la levée** ouvre un compteur : graines semées rappelées, nombre de levés saisissable au clavier numérique **et** par boutons « − / + », prérempli au dernier comptage s'il existe, case « levée terminée ». Le taux s'affiche à mesure, avec la comparaison à la moyenne de la culture quand US-212 en rend une (« 83 % — au-dessus de la moyenne du chou dans ce potager, 75 % »). « Envoyer au compagnon » prépare le geste de levée ; le compteur n'écrit rien
- [ ] CA11 : Cibles d'appui de **48 px** sur l'écran de terrain — « gants, terre, écran mouillé » (v2) ; les gestes restent atteignables sans défilement à 375 px sur un écran de 667 px de haut
- [ ] CA12 : Un membre en lecture seule voit la fiche entière, sans gestes ni compteur (RT11)

*États*
- [ ] CA13 : Lot terminé (tout mis en terre, vendu ou perdu) : la fiche s'ouvre, dit « lot terminé » et garde sa traçabilité, sans geste. Lot inconnu : « Aucun lot n° 128 dans ce potager »
- [ ] CA14 : Fermer la fiche rend l'écran d'origine intact ; après un geste confirmé au compagnon, le retour sur l'application relit le lot une fois (US-196 / CA12)

*Définition de terminé*
- [ ] CA15 : Le choix des gestes selon l'état du lot, les quantités proposées, le taux et la phrase de comparaison à la moyenne vivent dans une lib sans React couverte par `npm test`
- [ ] CA16 : Une page de contrôle visuel rejoue : lot en germination, en retard, en endurcissement, en godet en pépinière froide, dormant, terminé, sans semis rattaché, lecture seule, compteur ouvert, panneau desktop et terrain 375 px, thème sombre
- [ ] CA17 : La fiche `pepiniere-par-lot.md` décrit comment ouvrir un lot, lire sa traçabilité et y faire ses gestes (US-099 / CA9)
- [ ] CA18 : Le rendu correspond à la maquette haute fidélité gelée à 375 px, 768 px et desktop ; vérification chrome-devtools à 375 px

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA), interaction Telegram par le geste pré-rempli
- Migration BDD requise : **non**
- Dépendances : **US-214** (échéances, action suggérée), **US-196** (geste pré-rempli), **US-209** (numéro et lecture par numéro) ; US-212 (levée), US-210 et US-211 (emplacement, déplacement), US-217 (où les mettre), US-207 (fiche culture)
- Impact tokens : zéro
- Impact design system : composant `FicheLot` (deux formes, une seule logique) ; compteur numérique à grosses cibles réutilisable
- Point de vigilance : le compteur est une **aide à la saisie**, pas un formulaire d'écriture : le seul chemin d'enregistrement reste la confirmation au compagnon (RT1). Si le PO choisit un jour une saisie web directe (arbitrage A16), c'est ce compteur qui la portera
- Point de vigilance : **reproducteur vs végétatif** — sans objet en pépinière ; le type d'organe ne joue qu'après la mise en terre
- Wireframe : v2 § 3 (panneau « Lot sélectionné ») et § 3c « Le terrain — 375 px »

**Estimation :** 5 points (hors conception)

**Scénario Gherkin :**
```gherkin
Scénario: Devant la barquette
  Given le lot 128, chou frisé semé le 1er septembre, en retard de repiquage de 6 jours
  When je tape 128 dans "Aller au lot n°" sur mon téléphone
  Then la fiche du lot 128 s'ouvre en plein écran
  And l'échéance "En retard de 6 jours" est en tête
  And le bouton principal est "Repiquer en godet"

Scénario: Noter la levée au compteur
  Given la fiche du lot 128, 48 graines semées, aucune levée notée
  When j'ouvre "Noter la levée", je saisis 40 et j'appuie sur "Envoyer au compagnon"
  Then mon compagnon s'ouvre sur "levée du lot 128 : 40 plants"
  And rien n'est enregistré avant ma confirmation

Scénario: Comparaison à la moyenne
  Given deux lots de chou antérieurs dont la levée moyenne est de 75 %
  When je saisis 40 levés sur 48 dans le compteur
  Then la fiche affiche "83 % — au-dessus de la moyenne du chou dans ce potager, 75 %"

Scénario: Lot sans semis rattaché
  Given le lot des godets de tomate sans semis rattaché
  When j'ouvre sa fiche
  Then les gestes "Repiquer en godet" et "Noter la levée" ne sont pas proposés

Scénario: Lecture seule
  Given je suis membre du potager en lecture seule
  When j'ouvre la fiche du lot 128
  Then je vois sa traçabilité et son échéance
  And aucun geste ni compteur n'est proposé
```

**Labels GitHub :** `us`, `frontend`, `pwa`, `pepiniere`, `mobile`

**ID :** US-183
**Titre :** Ouvrir la fiche calendrier d'une culture — semer ou planter, projection et confiance — depuis Stocks et Plan
**Épic :** ÉPIC 8 — Confiance et personnalisation du calendrier *(numéro à valider, voir le plan de l'épic)*

**Story :**
En tant que jardinier
Je veux ouvrir, pour une culture de mon potager, une fiche qui me montre en un seul endroit quand la semer ou la planter, où en est celle que j'ai déjà en terre, quand je la récolterai, et à quel point je peux me fier à tout ça
Afin de décider d'un geste depuis l'écran où je regarde mes cultures, sans reconstituer le calendrier de tête à partir de trois écrans

**Contexte fonctionnel :**
Le calendrier d'une culture est aujourd'hui éclaté : la frise conseillée est sur la tuile du Plan (US-176), la projection recalée sur la même tuile (US-070), la confiance de la semaine y arrive (US-180), et l'écran Stocks — devenu **l'écran transverse unique des cultures** (US-072 / US-073, livrées le 16/08/2026) — n'a **aucun calendrier**, écart assumé à la livraison (« absence de calendrier `MonthStrip`, conforme à la maquette gelée », US-073). Une tuile de Plan ne peut pas tout porter ; une ligne de Stocks non plus.

Cette US crée la **fiche calendrier d'une culture**, un détail ouvert depuis **deux points d'entrée** : une ligne de Stocks (à côté du lien « N récoltes », même composant `Modal` qu'US-073 / CA13) et une tuile du Plan (US-060). La fiche a trois parties, dans cet ordre :

1. **Semer ou planter** — un sélecteur d'action (*semer en pépinière · semer en place · planter*), limité aux phases que le référentiel connaît pour la zone ; pour l'action choisie : la fenêtre conseillée, la confiance à la date de référence avec ses motifs (US-178), la récolte attendue si le geste est fait à cette date (US-070 / US-177), et le bouton d'enregistrement. C'est le pendant web de la question au bot (US-179).
2. **Déjà en terre** — pour chaque série en place dans le potager (par parcelle, la plus ancienne d'abord, US-070 / CA10) : événement d'origine, levée et première récolte attendues, reste à courir, écart si la récolte est dépassée. Absente si rien n'est en terre.
3. **Frise** — douze mois, conseillé ou recalé selon qu'une série est en terre, légende, mois de la date de référence mis en évidence.

La fiche **lit et projette**, n'écrit rien elle-même ; le bouton d'enregistrement ouvre le flux existant. Elle ne remplace ni la tuile ni la ligne : elle est le seul endroit où tout se lit ensemble.

⚖️ **Conception avant implémentation.** Cette fiche n'a pas de maquette. Elle est à concevoir dans le projet Claude Design **« potager 2026 »** à partir de la maquette figée du 15/08/2026 et du brief `BRIEF_FICHE_CALENDRIER_CULTURE.md`, puis gelée avant toute implémentation — même règle que l'écran Stocks. Aucun code de cette US ne démarre sans maquette gelée.

**Critères d'acceptance :**

*Points d'entrée*
- [ ] CA1 : Chaque ligne ou carte de l'écran Stocks porte une entrée « Calendrier » (à côté de « N récoltes »), toujours présente, qui ouvre la fiche de **cette culture** (tous itinéraires, toutes variétés confondus — le calendrier est au niveau culture, jamais variété)
- [ ] CA2 : Un appui sur la frise ou la ligne de confiance d'une tuile du Plan ouvre la même fiche, pré-positionnée sur la **série de cette parcelle** en partie 2. Le comportement existant de la tuile (sélection, observations) est inchangé
- [ ] CA3 : La fiche s'ouvre dans le composant modal partagé, en plein écran à 375 px, en panneau sur desktop ; la fermer ramène à l'écran d'origine dans son état (filtres, date de référence, parcelle sélectionnée)

*Partie 1 — semer ou planter*
- [ ] CA4 : Le sélecteur ne propose que les actions dont le référentiel porte une fenêtre pour la zone du potager ; l'action pré-sélectionnée est celle de meilleure confiance à la date de référence, à égalité celle de la règle de priorité d'US-176 / CA3bis. Sans aucune fenêtre : la partie 1 affiche « aucun calendrier pour cette culture dans ta zone » et un lien vers l'aide de `/calendrier`, jamais une estimation
- [ ] CA5 : Pour l'action choisie s'affichent : la fenêtre conseillée en clair (« mai à juin »), le niveau de confiance à la date de référence avec **chaque règle** (points, motif, état gagné / perdu / indéterminé — US-178 / CA6), et la récolte attendue en fourchette si le geste est fait à cette date, ou un tiret avec sa raison
- [ ] CA6 : Un bouton « Enregistrer le semis » / « Enregistrer la plantation » ouvre le flux d'enregistrement web existant, avec culture, action, filière et date pré-remplies ; la parcelle est demandée si elle n'est pas connue. Aucun nouveau chemin d'écriture
- [ ] CA7 : Quand les règles météo sont indéterminées faute de localisation, la fiche porte l'invitation à localiser le potager (même parcours qu'US-076)

*Partie 2 — déjà en terre*
- [ ] CA8 : Chaque série en place est listée avec sa parcelle, son événement d'origine (date, semis ou plantation, filière), sa levée et sa première récolte attendues, son reste à courir en fourchette (US-070 / CA3), et, le cas échéant, l'écart d'une récolte attendue dépassée sans récolte constatée (US-070 / CA12). Une série dont la récolte réelle a commencé affiche la date de première récolte constatée à la place de l'attendue (US-070 / CA5)
- [ ] CA9 : Une série sans projection possible (pas de durée, pas de contexte de semis) est listée avec ses tirets et la raison, jamais masquée (US-070 / CA11)
- [ ] CA10 : Sans série en terre, la partie 2 est absente — pas un bloc vide

*Partie 3 — frise*
- [ ] CA11 : La frise est **recalée** sur la série la plus ancienne en terre quand il y en a une, **conseillée** sinon ; elle nomme laquelle des deux elle montre, porte la légende des états (quatre phases du référentiel, ou semis / plantation / en croissance / récolte pour le recalé), et met en évidence le mois de la date de référence (US-176 / CA10, US-070 / CA8)
- [ ] CA12 : Le composant de frise partagé n'est **pas modifié** par cette US ; s'il lui manque une capacité, c'est une évolution rétrocompatible cadrée à part, jamais un cas particulier dans la fiche

*Transverse*
- [ ] CA13 : L'ouverture de la fiche déclenche **au plus deux lectures** (calendrier de la culture, confiance des actions à la date de référence) ; les séries en terre viennent des données déjà chargées par l'écran d'origine. La fiche affiche un état de chargement, jamais des tirets qui se remplissent
- [ ] CA14 : Si une lecture échoue, la fiche reste ouverte avec ce qu'elle a : frise neutre, confiance absente, séries listées ; aucune valeur de repli
- [ ] CA15 : Accessibilité : le sélecteur d'action est un groupe de boutons radio nommé ; les étoiles ont leur équivalent textuel ; la fiche se ferme au clavier
- [ ] CA16 : L'attribution de la source du calendrier (US-176 / CA9) est présente dans la fiche une seule fois quand des valeurs du référentiel s'y affichent
- [ ] CA17 : La fiche d'aide `calendrier-et-zone-climatique.md` est relue et corrigée dans la même livraison (US-099 / CA9) ; `ANALYSE_REFONTE_UI_WEB_2026.md` §5.11 est mis à jour : l'écart « absence de calendrier sur Stocks » est soldé par cette US
- [ ] CA18 : Le rendu correspond visuellement à la **maquette gelée** de la fiche (projet Claude Design « potager 2026 ») à 375px / 768px / desktop, légende comprise
- [ ] CA19 : Des tests couvrent : les deux points d'entrée et la pré-position du CA2, restauration de l'état à la fermeture, sélecteur limité aux phases connues et pré-sélection, absence de calendrier, détail des règles, bouton d'enregistrement vers le flux existant, invitation à localiser, séries multiples et série sans projection, absence de partie 2, bascule conseillé / recalé de la frise, budget de lectures du CA13, échec de lecture, accessibilité

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA — écrans Stocks et Plan)
- Migration BDD requise : **non**
- Dépendances : **US-178** (confiance, bloquante), **US-176** et **US-070** (frise et projection — ⚠️ non poussées sur la branche de référence au 15/09, à confirmer), **US-177** (récolte depuis plantation), **US-073** (écran Stocks, livrée), **US-060** (écran Plan, livrée), **US-180** (indicateur de tuile — cette fiche en est le détail, les deux US partagent la lecture groupée de confiance)
- Remplace : le point ouvert « absence de calendrier `MonthStrip` » consigné à la livraison d'US-073
- Impact tokens : zéro
- Impact design system : **aucune modification de `MonthStrip`** (CA12) ; réutilisation de `Modal`, `Badge`, `Stat`, `SectionLabel`. Un composant nouveau : le bloc « règle de confiance » (points, motif, état), partagé avec la fiche d'US-180 — à concevoir une seule fois
- Conception : brief `BRIEF_FICHE_CALENDRIER_CULTURE.md`, projet Claude Design « potager 2026 », gel de la maquette **avant** implémentation
- Point de vigilance : la partie 1 et l'écran Plan d'US-180 montrent la même confiance ; ils lisent la même lecture groupée à la même date de référence. Deux valeurs différentes pour la même culture au même instant est un bug, et un test le vérifie
- Point de vigilance : « semer ou planter » n'est pas une question posée au jardinier — c'est un sélecteur pré-positionné. À 375 px, il tient sur une ligne ou passe en menu ; jamais en trois cartes empilées

**Estimation :** 8 points (hors conception — la maquette est un préalable, pas un livrable de l'US)

**Scénario Gherkin :**
```gherkin
Scénario: Ouverture depuis Stocks
  Given l'écran Stocks affiche une ligne "Tomate · Cœur de bœuf"
  When j'appuie sur "Calendrier" sur cette ligne
  Then la fiche calendrier de la tomate s'ouvre
  And elle couvre toutes les variétés et tous les itinéraires de la tomate

Scénario: Ouverture depuis une tuile du Plan
  Given la parcelle 2 contient des tomates plantées le 10 mai
  When j'appuie sur la frise de la tuile tomate de la parcelle 2
  Then la fiche s'ouvre avec la série de la parcelle 2 mise en avant dans "Déjà en terre"

Scénario: Semer ou planter, pré-positionné
  Given le référentiel de la tomate porte semis en pépinière et plantation pour ma zone, pas de semis en place
  And la date de référence est le 5 mai, où la plantation a la meilleure confiance
  When j'ouvre la fiche de la tomate
  Then le sélecteur ne propose que "Semer en pépinière" et "Planter"
  And "Planter" est pré-sélectionné avec son niveau et le détail de chaque règle

Scénario: De la fiche à l'enregistrement
  Given la fiche affiche "Planter · ★★★" pour la tomate au 5 mai
  When j'appuie sur "Enregistrer la plantation"
  Then le flux d'enregistrement existant s'ouvre avec la tomate, la plantation et le 5 mai pré-remplis
  And la parcelle m'est demandée

Scénario: Deux séries en terre
  Given des haricots semés en place le 2 mai en parcelle 1 et le 30 mai en parcelle 3
  When j'ouvre la fiche du haricot
  Then les deux séries sont listées, celle du 2 mai en premier, chacune avec ses dates attendues
  And la frise est recalée sur la série du 2 mai et le dit

Scénario: Rien en terre, frise conseillée
  Given aucune courgette n'est en place dans le potager
  When j'ouvre la fiche de la courgette
  Then la partie "Déjà en terre" est absente
  And la frise affiche le calendrier conseillé de ma zone et le dit

Scénario: Aucun calendrier
  Given l'ail n'a aucune fenêtre pour ma zone
  When j'ouvre la fiche de l'ail
  Then la partie "Semer ou planter" indique l'absence de calendrier et le moyen de le compléter
  And la frise est neutre
  And les séries d'ail en terre sont listées avec leurs tirets

Scénario: Même confiance que la tuile
  Given la tuile de la tomate affiche "Planter · ★★☆" au 5 mai
  When j'ouvre la fiche depuis cette tuile
  Then "Planter" affiche deux étoiles avec les mêmes motifs
```

**Labels GitHub :** `us`, `frontend`, `pwa`, `cultures`, `plan`, `stocks`

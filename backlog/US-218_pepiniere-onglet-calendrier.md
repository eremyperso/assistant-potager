**ID :** US-218
**Titre :** Afficher l'onglet « Calendrier » de la Pépinière — les lots posés sur l'année, dans la fenêtre de semis de la zone
**Épic :** ÉPIC 12 — Pépinière : le poste de travail sous abri *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux voir sur une frise de l'année chacun de mes lots, du semis à la sortie prévue, posé sur la période où ma zone conseille de semer cette culture en pépinière
Afin de repérer d'un coup d'œil ce qui doit sortir, ce qui traîne et ce qu'il est encore temps de semer

**Contexte fonctionnel :**
C'est le premier regard que la v1 portait sur la pépinière (§ 3, « calendrier par culture ») et que la v2 garde comme troisième onglet : « Chaque lot est une barre du semis à la sortie prévue. Dépassée, la barre passe en pointillé ambre et remonte dans « À sortir ». » « La bande grisée par ligne = fenêtre de semis en pépinière (`FenetreCulturale`, action « semis_pepiniere »). Une culture avec fenêtre ouverte et sans lot apparaît en bas, grisée, avec « + semer maintenant » : c'est le pont vers la suggestion de Cultures. »

Les données existent après US-214 : les échéances de chaque lot (sortie prévue = mise en terre prévue, retard) et la liste des cultures « à semer ». Les fenêtres de semis en pépinière de la zone viennent du calendrier cultural (US-176). Cette US les dessine ; elle ne calcule aucune échéance.

⚖️ **Conception avant implémentation (RT9)** : wireframe v1 § 3 pour la structure, maquette haute fidélité gelée avant le code.

**Critères d'acceptance :**

*Lecture de la frise*
- [ ] CA1 : L'onglet « Calendrier » de la Pépinière affiche une ligne par culture qui a au moins un lot en cours, puis, en bas et atténuées, les cultures **à semer** (US-214 / CA8) sans lot en cours. En tête : les douze mois de l'année de la date de référence, le mois courant marqué, et un **trait vertical à la date de référence**
- [ ] CA2 : Sur chaque ligne, la **fenêtre de semis en pépinière** de la zone est une bande ; une fenêtre qui enjambe le 31 décembre est dessinée en deux morceaux. Sans fenêtre pour la zone, aucune bande et la ligne le dit (« pas de fenêtre de semis en pépinière pour ta zone »)
- [ ] CA3 : Chaque **lot** est une barre du semis à la **fin de sa mise en terre prévue** (US-214), la fourchette étant visible comme telle en bout de barre ; son libellé porte le numéro, la variété, la date de semis et l'échéance en clair (« #131 cerise · 15 sept. · repiquage dans 3 j »). Sans délai connu, la barre s'arrête à la date de référence, bout ouvert, « sortie non renseignée »
- [ ] CA4 : Un lot **en retard** (repiquage ou mise en terre dépassés) a sa barre en pointillé, teinte d'alerte ; un lot en endurcissement porte son compte à rebours. Un lot semé l'année précédente est coupé au 1er janvier avec la mention « depuis le … »
- [ ] CA5 : La légende dit les quatre éléments une fois : fenêtre de semis en pépinière de la zone, lot du semis à la sortie prévue, lot en retard, trait de la date de référence

*Interactions*
- [ ] CA6 : Un appui sur une barre ouvre la **fiche du lot** (US-216), en panneau à côté de la frise quand le conteneur fait au moins 900 px ; un appui sur le nom d'une culture ouvre sa **fiche culture** (US-207)
- [ ] CA7 : Sur la ligne d'une culture à semer, « **+ semer maintenant** » prépare le geste pré-rempli (US-196) : semis en pépinière, culture, date du jour ; la pépinière est demandée par le compagnon. Absent pour un membre en lecture seule
- [ ] CA8 : Un filtre d'emplacement, posé par l'onglet « Aujourd'hui » ou par une intention (US-195), s'applique aussi à cet onglet

*Mise en page, lecture, accessibilité*
- [ ] CA9 : À 375 px, la frise tient sans défilement horizontal de la page : colonne des cultures réduite, initiales des mois, libellés des barres masqués au profit de la fiche du lot ; container queries
- [ ] CA10 : Deux lectures au plus : `GET /pepiniere/lots` (lots, échéances, cultures à semer) et une lecture groupée des calendriers des cultures affichées (`GET /plan/calendriers`) ; jamais une par culture. Si le calendrier ne peut pas être lu, les lots s'affichent sans bande, et l'écran le dit
- [ ] CA11 : Accessibilité : la frise a une lecture textuelle équivalente (une ligne par culture, une phrase par lot : « Lot 131, tomate cerise, semé le 15 septembre, sortie prévue entre le … et le …, repiquage dans 3 jours ») ; chaque barre est focalisable ; retard et endurcissement sont écrits, pas seulement colorés

*Définition de terminé*
- [ ] CA12 : Le placement des bandes et des barres (dates → positions sur l'année, fenêtres à cheval sur deux années, coupure au 1er janvier, bout ouvert) vit dans une lib sans React couverte par `npm test`
- [ ] CA13 : Une page de contrôle visuel rejoue : lot à l'heure, en retard, en endurcissement, sans délai, semé l'année précédente, culture à semer, culture sans fenêtre, calendrier illisible, 375 px, thème sombre
- [ ] CA14 : La fiche `pepiniere-par-lot.md` décrit le calendrier de la pépinière (US-099 / CA9)
- [ ] CA15 : Le rendu correspond à la maquette haute fidélité gelée à 375 px, 768 px et desktop ; vérification chrome-devtools à 375 px

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA, écran Pépinière)
- Migration BDD requise : **non**
- Dépendances : **US-214** (échéances et cultures à semer), **US-215** (barre d'onglets) ; US-216 (fiche du lot), US-207 (fiche culture), US-196 (semer maintenant), US-176 (fenêtres de la zone, livrée)
- Impact tokens : zéro
- Impact design system : composant de frise de lots, distinct de `MonthStrip` (qui reste **non modifié**, US-183 / CA12) : celui-ci place des dates au jour sur l'année, `MonthStrip` colore des mois
- Point de vigilance : la fenêtre dessinée est celle **de la zone**, corrections du potager comprises ; elle ne tient pas compte du type de pépinière. Le lien entre type et opportunité du semis est porté par la confiance (US-220), pas par la bande
- Wireframe : `maquette front/wireframes/Wireframes - Plan Cultures Pepiniere.html`, § 3 et ses notes

**Estimation :** 5 points (hors conception)

**Scénario Gherkin :**
```gherkin
Scénario: Un lot en retard sur la frise
  Given le lot 128, chou frisé semé le 1er septembre, en retard de repiquage de 6 jours
  When j'ouvre l'onglet "Calendrier" au 19 septembre
  Then la ligne "Chou" porte la bande de sa fenêtre de semis en pépinière
  And la barre du lot 128 part du 1er septembre, en pointillé, teinte d'alerte
  And le trait vertical est posé au 19 septembre

Scénario: Une culture à semer
  Given la fenêtre de semis en pépinière de la laitue d'hiver est ouverte et aucun lot n'est en cours
  When j'ouvre l'onglet "Calendrier"
  Then la laitue d'hiver apparaît en bas, atténuée, avec "+ semer maintenant"
  When j'appuie sur "+ semer maintenant"
  Then mon compagnon s'ouvre sur un semis de laitue d'hiver en pépinière, la pépinière demandée

Scénario: Délai inconnu
  Given le lot 131 n'a pas de délai avant plantation connu
  When j'ouvre l'onglet "Calendrier"
  Then sa barre s'arrête à la date de référence, bout ouvert, "sortie non renseignée"

Scénario: Semé l'an dernier
  Given un lot d'oignon semé le 15 novembre de l'année précédente
  When j'ouvre l'onglet "Calendrier" en février
  Then sa barre commence au 1er janvier avec la mention "depuis le 15 novembre"
```

**Labels GitHub :** `us`, `frontend`, `pwa`, `pepiniere`

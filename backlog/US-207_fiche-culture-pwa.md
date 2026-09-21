**ID :** US-207
**Titre :** Ouvrir la fiche d'une culture depuis Cultures, Plan et Pépinière, et enchaîner vers sa fiche calendrier
**Épic :** ÉPIC 11 — Cultures : tout savoir d'une culture *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux, en touchant une culture où qu'elle apparaisse, ouvrir sa fiche : ce qu'il faut en faire maintenant, son calendrier dans ma zone, ses caractéristiques, où je la cultive, ses bonnes et mauvaises voisines, ce qui peut l'attaquer
Afin d'avoir tout ce que l'application sait d'elle sous les yeux, puis d'aller au calendrier détaillé si je veux agir

**Contexte fonctionnel :**
Le wireframe v1 (§ 2b) dessine la **fiche culture** : un panneau latéral de 560 px sur desktop, plein écran sur mobile, six sections « dans l'ordre d'utilité » — *Maintenant* en premier, « la seule chose qui change chaque semaine », puis le reste, stable, qui se lit en descendant.

La v2 précise sa frontière avec la **fiche calendrier** d'US-183 : « La fiche culture porte la frise, les variétés, les voisinages, les bioagresseurs. La fiche US-183 porte le **geste** : quelle action, quelle confiance, quelles règles, quelles séries en cours. Le recouvrement se limite à la frise 12 mois, et elle n'est pas la même : conseillée dans l'une, recalée dans l'autre. » La fiche culture **renvoie** à la fiche calendrier, elle ne la duplique pas : « Ouvrir la fiche calendrier » l'ouvre **par-dessus**, la fiche culture restant derrière (v2 § 1c).

La fiche culture est le point d'arrivée de plusieurs écrans : carte de l'écran Cultures (US-205), rang de la Vue plan et tuile de l'onglet Parcelles (US-201), nom d'une culture dans la Pépinière (US-215, US-216, US-218).

⚖️ **Conception avant implémentation (RT9)** : wireframe v1 § 2b pour la structure, maquette haute fidélité gelée avant le code.

**Critères d'acceptance :**

*Ouverture*
- [ ] CA1 : La fiche s'ouvre dans le composant modal partagé, disposition « adaptative » (US-183 / CA3) : plein écran à 375 px, fenêtre centrée sur tablette, panneau latéral sur desktop. En tête : le nom, puis « famille · zone · au <date de référence> »
- [ ] CA2 : Elle s'ouvre depuis la carte de l'écran Cultures, un rang de la Vue plan, le lien « Voir la culture » de l'onglet Parcelles et le nom d'une culture dans la Pépinière. Ouverte depuis une **parcelle**, elle en garde le contexte (CA9)
- [ ] CA3 : **Budget de lectures** : la fiche lit sa composition (US-206) ; le calendrier de zone et la confiance lui sont passés par l'écran d'origine quand il les a (Cultures, Plan), sinon elle les lit elle-même, en parallèle — au plus **trois lectures**, jamais une de plus. Un état de chargement, jamais des tirets qui se remplissent (US-183 / CA13)

*Les six sections, dans cet ordre*
- [ ] CA4 : **Maintenant** — une phrase et, le cas échéant, des étoiles : le geste le mieux noté à la date de référence (« Semer en place maintenant · ★★★ », fenêtre, récolte attendue si le geste est fait ce jour-là) ; sinon « Rien à semer ni planter ce mois-ci » et la prochaine fenêtre (« semer en pépinière : février → mars ») ; puis l'état au potager (« en récolte sur 2 parcelles », « 1 lot en pépinière », « pas au potager »). Le bouton **« Ouvrir la fiche calendrier »** clôt la section. Les étoiles sont celles de la même évaluation que la carte, la tuile et la fiche calendrier
- [ ] CA5 : **Calendrier de la zone** — la frise **conseillée** des douze mois (`MonthStrip`, non modifié), sa légende des quatre phases, le mois de la date de référence encadré
- [ ] CA6 : **Référentiel** — famille et délai de retour, exposition, besoin en eau, rusticité minimale, profondeur de semis, levée, délai plantation → récolte, type végétatif ou reproducteur ; « non renseigné » pour toute valeur absente ; la source une seule fois
- [ ] CA7 : **Variétés cultivées · N** — chaque variété, ses parcelles avec leur phase (`PastillePhase`) et ses lots de pépinière. Un nom de parcelle ouvre l'onglet Parcelles sur elle, un lot ouvre sa fiche dans la Pépinière (US-195). Aucune variété : « pas au potager en ce moment »
- [ ] CA8 : **Voisinages** et **Bioagresseurs · N** — pastilles « + » (favorable) et « − » (défavorable), la pratique traditionnelle signalée comme telle ; les cinq bioagresseurs les plus fréquents avec leur période de risque et leur symptôme, puis « + N autres » qui déplie la suite. Les deux phrases d'absence d'US-206 / CA9 quand la liste est vide

*Enchaînement vers la fiche calendrier*
- [ ] CA9 : « Ouvrir la fiche calendrier » ouvre la fiche d'US-183 **par-dessus** la fiche culture, en lui passant le calendrier et la confiance déjà lus (aucune lecture de plus quand ils couvrent la culture) et la **parcelle** d'origine s'il y en a une : sa série y est alors mise en avant, comme depuis une tuile (US-183 / CA2)
- [ ] CA10 : Fermer la fiche calendrier rend la fiche culture intacte ; Échap ferme la plus haute des deux ; fermer la fiche culture rend l'écran d'origine dans son état exact (US-195 / CA8). Le bouton d'enregistrement de la fiche calendrier est celui d'US-196

*États*
- [ ] CA11 : Culture **inconnue du référentiel** : la fiche s'ouvre, dit « fiche absente du référentiel » sans proposer d'autre culture, et garde ses variétés cultivées
- [ ] CA12 : Une lecture échouée laisse la fiche ouverte avec ce qu'elle a — sections vides dites comme telles, aucune valeur de repli (US-183 / CA14). Confiance illisible : la section *Maintenant* le dit
- [ ] CA13 : Accessibilité : fenêtre modale nommée, un titre par section, focus piégé dans la fiche la plus haute, étoiles avec leur équivalent écrit, fermeture au clavier ; mise en page interne en container queries (la grille *Référentiel* passe sur une colonne quand la fiche est étroite)

*Définition de terminé*
- [ ] CA14 : La composition de la section *Maintenant* (phrase, prochaine fenêtre, état au potager) vit dans une lib sans React (`frontend/src/lib/ficheCulture.js`) couverte par `npm test`
- [ ] CA15 : Une page de contrôle visuel rejoue les états : ouverte depuis Cultures, depuis un rang avec parcelle, fenêtre ouverte, fenêtre fermée avec séries en terre, sans calendrier, hors référentiel, lecture échouée, fiche calendrier empilée, thème sombre
- [ ] CA16 : La fiche `cultures-et-fiche-culture.md` (créée par US-205, ou ici si cette US passe avant) décrit l'ouverture et les sections de la fiche ; `calendrier-et-zone-climatique.md` ajoute l'ouverture de la fiche calendrier depuis la fiche culture (US-099 / CA9)
- [ ] CA17 : Le rendu correspond à la maquette haute fidélité gelée à 375 px, 768 px et desktop ; vérification chrome-devtools à 375 px

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA)
- Migration BDD requise : **non**
- Dépendances : **US-206** (lecture de la fiche), **US-195** (liens vers parcelle et lot, retour à l'état exact) ; US-183 (fiche calendrier, livrée) ; US-194 (pastille de phase) ; US-196 pour le bouton d'enregistrement de la fiche calendrier
- Consommateurs : US-201, US-205, US-215, US-216, US-218, US-222 (tuile de l'onglet Parcelles)
- Impact tokens : zéro
- Impact design system : un composant `FicheCulture` ; réutilise `Modal` (disposition adaptative), `MonthStrip`, `Etoiles`, `PastillePhase`, `Badge`, `FicheCalendrier`. L'empilement de deux fenêtres modales est vérifié sur le composant partagé, pas contourné dans la fiche
- Point de vigilance : la section *Maintenant* **ne recalcule rien** ; elle met en forme la confiance et le calendrier déjà lus. Deux valeurs différentes entre la carte, la fiche culture et la fiche calendrier au même instant sont un bug
- Point de vigilance : pas de frise **recalée** ici — c'est la raison d'être de la fiche calendrier (v2)
- Wireframes : v1 § 2b ; v2 § 1c et la note « Ce que la fiche culture ne redit pas »

**Estimation :** 5 points (hors conception)

**Scénario Gherkin :**
```gherkin
Scénario: Fiche de la tomate en septembre
  Given la tomate est en récolte sur deux parcelles au 18 septembre
  When j'ouvre la fiche de la tomate depuis l'écran Cultures
  Then la section "Maintenant" dit "Rien à semer ni planter ce mois-ci"
  And elle annonce la prochaine fenêtre "semer en pépinière : février → mars"
  And elle indique "en récolte sur 2 parcelles"

Scénario: Depuis un rang du Plan, jusqu'à la série de la parcelle
  Given j'ai ouvert la fiche de la courgette depuis le rang 3 de la planche-centrale
  When j'appuie sur "Ouvrir la fiche calendrier"
  Then la fiche calendrier s'ouvre par-dessus la fiche culture
  And la série de la planche-centrale y est mise en avant
  When je ferme la fiche calendrier
  Then la fiche de la courgette est toujours ouverte

Scénario: Aucun bioagresseur rattaché
  Given aucun bioagresseur n'est rattaché à la mâche
  When j'ouvre la fiche de la mâche
  Then la section "Bioagresseurs" dit ne pas avoir l'information, et que ce n'est pas une absence de risque

Scénario: Une variété en pépinière
  Given un lot de tomate cerise en godet dans la serre
  When j'ouvre la fiche de la tomate
  Then la variété cerise porte son lot de pépinière
  When j'appuie sur ce lot
  Then la Pépinière s'ouvre sur la fiche de ce lot

Scénario: Lecture échouée
  Given la lecture de la composition de la fiche échoue
  When j'ouvre la fiche de l'épinard depuis l'écran Cultures
  Then la fiche reste ouverte avec sa section "Maintenant" et sa frise
  And les autres sections disent qu'elles n'ont pas pu être lues
```

**Labels GitHub :** `us`, `frontend`, `pwa`, `cultures`, `design-system`

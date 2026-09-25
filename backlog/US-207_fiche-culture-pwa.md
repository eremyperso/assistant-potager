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

⚖️ **Conception faite (RT9)** : wireframe v1 § 2b pour la structure, **maquette haute
fidélité gelée le 25/09/2026** — `Cultures - Ecran et fiche.html` (projet Claude Design
*potager 2026*), à déposer dans `maquette front/haute-fidelite/`. Elle rejoue les sept états
de la fiche (fenêtre ouverte, fenêtre fermée avec séries en terre, depuis un rang du Plan,
sans calendrier, hors référentiel, lecture échouée, fiche calendrier empilée) aux trois
largeurs et dans les deux thèmes.

**Critères d'acceptance :**

*Ouverture*
- [ ] CA1 : La fiche s'ouvre dans le composant modal partagé, disposition « adaptative » (US-183 / CA3) : **feuille plein écran** à 375 px, **modale centrée** à 768 px, **panneau latéral** sur desktop. En tête : une vignette de feuille, le nom, puis « famille · zone · au <date de référence> », et un bouton de fermeture
- [ ] CA2 : Elle s'ouvre depuis la carte de l'écran Cultures, un rang de la Vue plan, le lien « Voir la culture » de l'onglet Parcelles et le nom d'une culture dans la Pépinière. Ouverte depuis une **parcelle**, elle en garde le contexte (CA9)
- [ ] CA3 : **Budget de lectures** : la fiche lit sa composition (US-206) ; le calendrier de zone et la confiance lui sont passés par l'écran d'origine quand il les a (Cultures, Plan), sinon elle les lit elle-même, en parallèle — au plus **trois lectures**, jamais une de plus. Un état de chargement, jamais des tirets qui se remplissent (US-183 / CA13)

*Les six sections, dans cet ordre*
- [ ] CA4 : **Maintenant** — un bloc en fond doux : une phrase et, le cas échéant, des étoiles : le geste le mieux noté à la date de référence (« Semer en place maintenant · ★★★ », fenêtre, récolte attendue si le geste est fait ce jour-là) ; sinon « Rien à semer ni planter ce mois-ci » et la prochaine fenêtre (« semer en pépinière : février → mars ») ; puis l'état au potager (« en récolte sur 2 parcelles », « 1 lot en pépinière », « pas au potager »). Le bouton **« Ouvrir la fiche calendrier »** clôt la section. Les étoiles sont celles de la même évaluation que la carte, la tuile et la fiche calendrier
- [ ] CA5 : **Calendrier de la zone** — la frise **conseillée** des douze mois (`MonthStrip`, non modifié), sa légende des quatre phases, le mois de la date de référence encadré, et dessous la phrase « Calendrier conseillé. Le calendrier recalé sur tes séries est dans la fiche calendrier. » Sans calendrier pour la zone : « Aucune fenêtre connue pour cette zone » à la place de la frise, jamais une frise vide sans explication
- [ ] CA6 : **Référentiel** — famille et délai de retour, exposition, besoin en eau, rusticité minimale, profondeur de semis, levée, délai plantation → récolte, type végétatif ou reproducteur ; « non renseigné » pour toute valeur absente ; la source une seule fois
- [ ] CA7 : **Variétés cultivées · N** — chaque variété, ses parcelles avec leur phase (`PastillePhase`) et ses lots de pépinière. Un nom de parcelle ouvre l'onglet Parcelles sur elle, un lot ouvre sa fiche dans la Pépinière (US-195). Aucune variété : « pas au potager en ce moment »
- [ ] CA8 : **Voisinages** et **Bioagresseurs · N** — pastilles « + » (favorable) et « − » (défavorable), la pratique traditionnelle signalée comme telle ; les cinq bioagresseurs les plus fréquents avec leur période de risque et leur symptôme, puis « + N autres » qui déplie la suite. Les deux phrases d'absence d'US-206 / CA9 quand la liste est vide

*Enchaînement vers la fiche calendrier*
- [ ] CA9 : « Ouvrir la fiche calendrier » ouvre la fiche d'US-183 **par-dessus** la fiche culture, en lui passant le calendrier et la confiance déjà lus (aucune lecture de plus quand ils couvrent la culture) et la **parcelle** d'origine s'il y en a une : sa série y est alors mise en avant, comme depuis une tuile (US-183 / CA2)
- [ ] CA10 : Fermer la fiche calendrier rend la fiche culture intacte ; Échap ferme la plus haute des deux ; fermer la fiche culture rend l'écran d'origine dans son état exact (US-195 / CA8). Le bouton d'enregistrement de la fiche calendrier est celui d'US-196

*États*
- [ ] CA11 : Culture **inconnue du référentiel** : la fiche s'ouvre, dit « fiche absente du référentiel » sans proposer d'autre culture, et garde ses variétés cultivées
- [ ] CA12 : Une lecture échouée laisse la fiche ouverte avec ce qu'elle a. Un bandeau **« Lecture incomplète »** avec un bouton « Réessayer » ouvre la fiche, *Maintenant* et la frise restent servies par l'écran d'origine, et **chacune** des quatre sections manquantes affiche, à sa place, « Cette section n'a pas pu être lue » — jamais une section escamotée, jamais une valeur de repli (US-183 / CA14). Confiance illisible : *Maintenant* écrit « confiance illisible » à la place des étoiles et rappelle que la météo n'a pas pu être lue
- [ ] CA13 : Accessibilité : fenêtre modale nommée (« Fiche culture : <nom> »), un titre par section, focus piégé dans la fiche la plus haute, étoiles avec leur équivalent écrit, fermeture au clavier

*Responsive, en-tête et pied (amendement du 25/09)*
- [ ] CA18 : **Largeur du panneau latéral : 560 px.** La variante `adaptative` du `Modal` partagé plafonne aujourd'hui à 460 px sur desktop, largeur retenue pour la fiche calendrier d'US-183. La fiche culture porte une grille de référentiel à deux colonnes et des listes de variétés : elle demande 560 px. Le `Modal` gagne donc une **largeur paramétrable** pour la variante adaptative — aucune variante nouvelle, aucune régression pour US-183, qui garde 460 px par défaut. C'est la **seule modification du design system** portée par cette US
- [ ] CA19 : **Container queries à l'intérieur de la fiche** : le corps de la fiche est le conteneur ; la grille *Référentiel* est à deux colonnes et passe à **une colonne sous 400 px de conteneur**. Aucun breakpoint de page n'est lu à l'intérieur de la fiche (RT5) — c'est ce qui la rend juste aussi bien en feuille plein écran qu'en panneau de 560 px
- [ ] CA20 : **Badge de contexte** — ouverte depuis un rang de la Vue plan ou une tuile de l'onglet Parcelles, la fiche affiche dans son en-tête un badge « depuis <parcelle> · rang N ». C'est ce contexte qui est passé à la fiche calendrier (CA9) ; il n'apparaît pas quand la fiche est ouverte depuis l'écran Cultures
- [ ] CA21 : **Pied de fiche persistant**, hors défilement : les sources dédoublonnées (« Wind River Greens · CC BY 4.0 · EPPO », US-206 / CA7) à gauche, un bouton **Fermer** à droite. Seul le corps défile ; l'en-tête et le pied restent à l'écran à 375 px, où la fiche occupe tout l'écran
- [ ] CA22 : **Voisinages** — quatre groupes et non deux : favorables et défavorables en pastilles pleines « + » et « − », puis, sous le sous-titre « Selon la pratique traditionnelle, sans preuve établie », les mêmes pastilles **en pointillé**. Le niveau de preuve d'US-206 / CA5 décide du groupe ; il n'est jamais rendu par la seule couleur (RT4, le signe « + » ou « − » est écrit)
- [ ] CA23 : **Bioagresseurs** — une ligne par bioagresseur : nom en gras, catégorie en gris, et à droite « risque : juillet → septembre » **seulement si la période est renseignée** ; le symptôme en dessous quand il existe. Cinq visibles, puis « + N autres » qui déplie le reste en place, sans lecture supplémentaire (US-206 / CA6)
- [ ] CA24 : La fiche est rendue **à 375 px, 768 px et 1180 px, en thème clair et sombre**, sur les sept états de la maquette ; vérification chrome-devtools à 375 px, y compris avec la **fiche calendrier empilée** par-dessus — le cas où deux feuilles plein écran se superposent

*Définition de terminé*
- [ ] CA14 : La composition de la section *Maintenant* (phrase, prochaine fenêtre, état au potager) vit dans une lib sans React (`frontend/src/lib/ficheCulture.js`) couverte par `npm test`
- [ ] CA15 : Une page de contrôle visuel (`_FicheCulturePreview`, sur le modèle de `_FicheCalendrierPreview` et `_PlanVuePreview`) rejoue **les sept états de la maquette** à trois largeurs et dans les deux thèmes : ouverte depuis Cultures, depuis un rang avec parcelle, fenêtre ouverte, fenêtre fermée avec séries en terre, sans calendrier, hors référentiel, lecture échouée, fiche calendrier empilée
- [ ] CA16 : La fiche `cultures-et-fiche-culture.md` (créée par US-205, ou ici si cette US passe avant) décrit l'ouverture et les sections de la fiche ; `calendrier-et-zone-climatique.md` ajoute l'ouverture de la fiche calendrier depuis la fiche culture (US-099 / CA9)
- [ ] CA17 : Le rendu correspond à la maquette gelée `Cultures - Ecran et fiche.html` (voir CA24 pour l'étendue de la vérification)

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA)
- Migration BDD requise : **non**
- Dépendances : **US-206** (lecture de la fiche), **US-195** (liens vers parcelle et lot, retour à l'état exact) ; US-183 (fiche calendrier, livrée) ; US-194 (pastille de phase) ; US-196 pour le bouton d'enregistrement de la fiche calendrier
- Consommateurs : US-201, US-205, US-215, US-216, US-218, US-222 (tuile de l'onglet Parcelles)
- Impact tokens : zéro
- Impact design system : un composant `FicheCulture` ; réutilise `Modal` (disposition adaptative), `MonthStrip`, `MonthStripLegend`, `Etoiles`, `PastillePhase` (variante compacte d'US-205 / CA21), `Badge`, `InfoBanner`, `Btn`, `FicheCalendrier` — tous livrés. **Une seule modification** : la largeur paramétrable de la variante adaptative du `Modal` (CA18). L'empilement de deux fenêtres modales est déjà géré par la pile du `Modal` partagé (Échap ne ferme que la plus haute, le focus revient à l'élément d'origine) : il est **vérifié**, jamais contourné dans la fiche
- Point de vigilance : la section *Maintenant* **ne recalcule rien** ; elle met en forme la confiance et le calendrier déjà lus. Deux valeurs différentes entre la carte, la fiche culture et la fiche calendrier au même instant sont un bug
- Point de vigilance : pas de frise **recalée** ici — c'est la raison d'être de la fiche calendrier (v2)
- Wireframes : v1 § 2b ; v2 § 1c et la note « Ce que la fiche culture ne redit pas »

**Estimation :** 8 points (hors conception — relevée de 5 à 8 le 25/09 : le pied persistant, les quatre groupes de voisinages, les états de section non lue, la largeur paramétrable du `Modal` et la vérification des sept états à trois largeurs)

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

---

## 🆕 Amendement du 25/09/2026 — maquette gelée « Cultures — écran et fiche »

| Ce que la maquette tranche | CA |
|---|---|
| Trois dispositions nommées : feuille 375, modale centrée 768, panneau latéral 1180 | CA1 (précisé) |
| Panneau latéral de **560 px**, là où le `Modal` plafonne à 460 | **CA18** |
| Container query à 400 px à l'intérieur de la fiche (grille *Référentiel*) | **CA19** |
| Badge « depuis planche-centrale · rang 2 » dans l'en-tête | **CA20** |
| Pied persistant : sources + Fermer, seul le corps défile | **CA21** |
| Voisinages en quatre groupes, la pratique traditionnelle en pointillé | **CA22** |
| Bioagresseurs : catégorie, « risque : … » conditionnel, symptôme, « + N autres » | **CA23** |
| Sept états × trois largeurs × deux thèmes, empilement compris | **CA24**, CA15 |
| « Cette section n'a pas pu être lue », section par section | CA12 (précisé) |

✅ **A29 tranché par le PO le 25/09/2026** : largeur paramétrable, valeur par défaut inchangée à 460 px pour US-183. CA18 est donc ferme.

**Le point technique porte sur CA18.** La variante `adaptative` du `Modal`
partagé (`frontend/src/components/ui/Modal.jsx`) vaut `lg:max-w-[460px]`. La fiche culture en
demande 560. Ouvrir une variante de plus dupliquerait la gestion de la pile ; le choix retenu
est de **paramétrer la largeur**, la valeur par défaut restant celle d'US-183. C'est une
modification d'un composant partagé déjà livré et utilisé par la fiche calendrier, la fiche
parcelle et la fiche de lot à venir : une non-régression y est vérifiée.

Ce que la maquette **ne** rouvre pas : les six sections et leur ordre, la frontière avec la
fiche calendrier (frise conseillée ici, recalée là-bas), le budget de trois lectures, le fait
que *Maintenant* ne recalcule rien.

**ID :** US-352
**Titre :** Poser les pièces du socle : tokens, langage d'étape, calendrier, note du carnet, infobulle
**Épic :** ÉPIC 21 — Socle commun des vues

**Story :**
En tant que jardinier
Je veux retrouver partout la même pastille d'étape, le même calendrier de l'année et mes propres notes écrites à la main
Afin de lire d'un coup d'œil où en est une culture et ce qui vient de moi, quel que soit l'écran

**Contexte fonctionnel :**
Vague 1 de l'ÉPIC 21. La référence de fidélité est la maquette `docs/EPIC 21 - SOCLE COMMUN DES VUES/maquette/Socle commun - 7 vues.html`, section « Les pièces du socle ».
Le langage d'étape existe (US-321, `lib/etapes.js`, `EtapeCulture`, `PastillePhase`) avec les mêmes libellés et pictogrammes. Cette US aligne ses couleurs et ses formes, et en fait les seules pièces utilisées : elle remplace les badges, étoiles et palettes de calendrier propres à chaque écran.

**Critères d'acceptance :**
- [ ] CA1 : Les tokens de la maquette sont dans `index.css` / `tailwind.config.js` : couleurs d'étape (Semé `#E6CFA2`, Levé/Planté `#CDE9A6`, En croissance `#86C163`, En fleur `#F4D35E`, En récolte `#F2A54A`, Terminé `#DADAD2`), dû (`--due #D9822B` et ses variantes fond/bord/texte), autre jour (`--amb-*`), carnet (`--ink #2B3A63`, `--paper #FBF8EF`, `--paper-bd`), pépinière (`--pep #5B4690`, `--pep-soft`), sol (`--soil`)
- [ ] CA1b : **Mode sombre réactivé** (D12) avec les tokens sombres de la maquette (classe `.dk`, branchée sur la classe `.dark` de `useTheme`) : `--bg #11160F`, `--surface #1A2117`, `--alt #232C1F`, `--bd #323D2C`, `--bd2 #283224`, `--brand #7DB548`, `--brand-deep #B5DB82`, `--brand-soft #22311A`, `--brand-text #A8D072`, `--txt #E6ECDD`, `--txt2 #AEB9A3`, `--txt3 #8C9882`, bandeau `#16260D → #264212`, `--due-*`, `--amb-*`, `--ink #B9C8F2`, `--paper #24211A`, `--pep #C7B8F0`, `--soil #3B3326`. Les couleurs d'étape et les cases du calendrier **ne changent pas** et gardent un texte foncé `#16210C`. Les boutons principaux, Noter et le micro gardent le vert `#4A7C22`. Toute surface codée `#fff` passe par `--surface`
- [ ] CA2b : **Pastille « En godet »** (`#CDE9A6`, pictogramme godet de la maquette), ajoutée au langage d'étape. Les stades de la pépinière se lisent dans ce langage : En levée → Levé, En godet → En godet, Endurcissement → En croissance, Prêt à sortir → Planté, Terminé → Terminé. Cette correspondance remplace la palette propre de `lib/parcours.js`
- [ ] CA2 : **Pastille d'étape** : carré arrondi de 40 px (30 px en petit), fond de l'étape, pictogramme de 21 px (16 px). Variante **prévue** hachurée à −45° avec filet `#6B7B55`. Variante **due** avec un point orange de 11 px cerclé de blanc. **Puce d'étape** en pilule avec libellé, et « · prévu » en variante hachurée
- [ ] CA3 : **Calendrier 12 mois** : douze cases de 9 px, gouttière de 2 px, aux couleurs semis / levée-plantation / croissance / floraison / récolte, le mois courant cerclé, initiales des mois en option. Il remplace `MonthStrip` dans Cultures, le catalogue et la fiche Référence
- [ ] CA4 : **Infobulle d'étape** : le survol à la souris et l'**appui long de 380 ms** au doigt sur une pastille, un rang du plan ou une case du calendrier affichent son étape en clair (« Levé · prévu, à confirmer · dû aujourd'hui », « nov. (ce mois-ci) · récolte »). Un appui long n'ouvre pas ce qui est dessous
- [ ] CA5 : **Note du carnet** : papier crème, bordure `--paper-bd`, méta « 🎤 Dicté · date · lieu » ou « ✎ Écrit · date · lieu » en 11,5 px, texte en **Kalam 16,5 px à l'encre `--ink`**
- [ ] CA6 : **Kalam est réservée au texte dicté ou écrit par le jardinier.** Le nom de Gaston, le titre des cartes de proposition, « Mode Support » et l'étiquette « auj. » de la règle des temps passent en Lora ou en police système (test qui recense les usages de `font-hand`)
- [ ] CA7 : **Légende repliable** commune : « ? Légende ⌄ » + « Appui long sur … : son étape ». Dépliée, elle liste les puces d'étape, le hachuré « prévu » et le point « à confirmer »
- [ ] CA8 : Chaque pièce porte son nom accessible (`role="img"` + `aria-label` « Levé, prévu, dû »). Contraste du texte de 4,5:1 au moins sur chaque fond d'étape
- [ ] CA9 : Une page d'aperçu (`_DesignSystemPreview` ou `_EtapesPreview`) montre toutes les pièces à côté de la maquette, en clair et en sombre
- [ ] CA type : Le rendu correspond visuellement à la maquette de référence à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non
- Dépendances : US-321 (langage visuel des étapes), US-279 (règle des temps)
- Modèle / effort conseillé : **Sonnet 5.5, `high`** — les tokens et composants servent toutes les vues, et une couleur fausse se propage partout ; ni Opus ni Fable ne sont requis

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given la levée de la fève est prévue aujourd'hui et n'est pas confirmée
When le jardinier regarde la fève dans n'importe quelle vue
Then sa pastille est vert pâle, hachurée, avec un point orange
And un appui long de 380 ms affiche "Levé · prévu, à confirmer · dû aujourd'hui"

Given le jardinier a dicté "Les fèves pointent sur tout le rang"
When la note s'affiche
Then le texte est en Kalam, encre bleue, sur papier crème, sous la méta "Dicté · aujourd'hui · Fève"
And le nom "Gaston" n'est écrit en Kalam nulle part dans l'application
```

**Labels GitHub :** `us`, `frontend`, `pwa`, `design-system`, `socle`

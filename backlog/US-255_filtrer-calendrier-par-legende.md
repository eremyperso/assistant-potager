**ID :** US-255
**Titre :** Filtrer la frise calendrier d'une culture en touchant un élément de la légende
**Épic :** ÉPIC 11 — Cultures : tout savoir d'une culture *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux toucher un élément de la légende de la frise calendrier (semis en pépinière, semis en pleine terre, plantation, récolte) pour n'afficher que cette période, et le retoucher pour tout réafficher
Afin de lire sans ambiguïté les mois d'une seule phase, là où plusieurs phases se chevauchent et où une seule couleur par mois est visible aujourd'hui

**Contexte fonctionnel :**
Dans la fiche culture, la frise « Calendrier de la zone » colore chaque mois d'**une seule** teinte, choisie par priorité (récolte > plantation > semis en pleine terre > semis en pépinière). Quand des périodes se chevauchent, la phase de moindre priorité disparaît de la frise.

Exemple, courgette en zone océanique (référentiel) :

| Phase | Fenêtre |
|---|---|
| Semis en pépinière | avril |
| Semis en pleine terre | avril à juin |
| Plantation | mai |
| Récolte | juillet à août |

Avril porte à la fois le semis en pépinière et le semis en pleine terre ; mai porte le semis en pleine terre et la plantation. La frise n'en montre qu'un. Le jardinier ne peut pas voir « tous les mois où je peux semer en pleine terre ».

La légende existe déjà (`MonthStripLegend`) mais elle est passive. Elle devient une **commande de filtre**.

Ce comportement vit dans le composant partagé de frise (`MonthStrip` et sa légende), donc il vaut **partout où la frise et sa légende s'affichent** : fiche culture, fiche calendrier, cartes Cultures, Vue plan, Pépinière, Stocks. Pas de variante par écran.

**Critères d'acceptance :**

*Filtre*
- [ ] CA1 : Chaque élément de la légende de la frise est un **bouton** (accessible au clavier, `aria-pressed`) et non plus un simple libellé
- [ ] CA2 : Toucher un élément **active le filtre** : la frise n'affiche que les mois où cette phase est active, dans sa teinte. Les autres mois passent à l'état neutre (identique à un mois sans phase)
- [ ] CA3 : Le filtre **ne tient pas compte de la priorité** : un mois où la phase filtrée est active reste coloré même si une phase plus prioritaire y est aussi active (ex. filtre « Semis en pleine terre » : avril, mai et juin colorés pour la courgette océanique, mai l'étant malgré la plantation)
- [ ] CA4 : Toucher **le même élément** une seconde fois **réinitialise** le filtre : la frise revient à son rendu normal (toutes les phases, par priorité)
- [ ] CA5 : Toucher **un autre élément** pendant qu'un filtre est actif **déplace** le filtre sur ce nouvel élément (un seul filtre à la fois, pas de sélection multiple)
- [ ] CA6 : L'élément actif est visuellement distinct (état sélectionné) ; les autres éléments sont atténués mais restent touchables. Le contraste respecte le design system dans les deux thèmes

*Périmètre et état*
- [ ] CA7 : Le filtre est un **état local à chaque frise** : il n'est ni mémorisé à la fermeture de la fiche, ni partagé entre deux frises affichées en même temps, ni écrit en base. À l'ouverture d'une fiche, aucun filtre n'est actif
- [ ] CA8 : Le comportement est identique dans **tous les écrans** qui affichent la frise avec légende. Un test vérifie le composant partagé, pas chaque écran
- [ ] CA9 : Le filtre s'applique aux deux variantes de la frise : **référentiel** (conseillée) et **recalée** (séries du jardinier). Dans la variante recalée, la légende « En croissance » est filtrable comme les autres
- [ ] CA10 : Une phase absente de la frise d'une culture (ex. pas de semis en pleine terre) reste affichée dans la légende ; la toucher donne une frise entièrement neutre et un message discret « Aucun mois pour cette phase » (pas d'erreur, pas de légende qui disparaît)
- [ ] CA11 : Le mois courant reste repéré (contour) quel que soit le filtre
- [ ] CA12 : Le filtre ne déclenche aucune nouvelle lecture réseau (CA3 d'US-207, budget de lectures inchangé)
- [ ] CA13 : Le rendu correspond visuellement à la maquette de référence à 375px/768px/desktop. La légende peut passer sur deux lignes à 375 px sans que la zone touchable d'un élément descende sous 44 px de haut

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA, frise calendrier)
- Migration BDD requise : non
- Corpus de connaissance (règle US-099 / CA9) : à relire avant livraison, la table « ce qui rend une fiche fausse » de `data/connaissance/doc_app/README.md`, si une fiche décrit la lecture de la frise
- Dépendances : US-206 et US-207 (fiche culture), US-183 (fiche calendrier). Aucune dépendance backend
- Hors périmètre : filtre multiple, mémorisation du filtre, filtre sur les données du serveur

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given la fiche de la courgette en zone océanique affiche sa frise "Calendrier de la zone"
And avril, mai et juin portent un semis en pleine terre, dont mai porte aussi la plantation
When le jardinier touche "Semis en pleine terre" dans la légende
Then seuls avril, mai et juin sont colorés dans la teinte du semis en pleine terre
And les autres mois sont neutres
When le jardinier touche à nouveau "Semis en pleine terre"
Then la frise retrouve son rendu normal avec toutes les phases

Given le filtre "Récolte" est actif
When le jardinier touche "Plantation"
Then le filtre passe sur "Plantation" et seul mai est coloré
```

**Labels GitHub :** `us`, `frontend`, `consultation`, `cultures`

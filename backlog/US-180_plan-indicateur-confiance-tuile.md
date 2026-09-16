**ID :** US-180
**Titre :** Afficher la confiance de la semaine sur les tuiles de cultures de l'écran Plan
**Épic :** ÉPIC 8 — Confiance et personnalisation du calendrier *(numéro à valider, voir le plan de l'épic)*

**Story :**
En tant que jardinier
Je veux voir sur l'écran Plan, pour chaque culture, si la semaine de la date de référence est un bon moment pour la semer ou la planter, et pourquoi
Afin de planifier ma semaine depuis l'écran où je vois déjà mes parcelles, mes cultures et leur calendrier

**Contexte fonctionnel :**
US-176 a branché la frise conseillée sur le référentiel, US-070 la recale sur le réel. La tuile de culture sait donc dire « quand » ; elle ne dit pas « est-ce le bon moment cette semaine, ici ». Cette US ajoute sur la tuile un **indicateur de confiance** lu du moteur d'US-178, calculé pour la **date de référence de l'écran** (US-060 / CA10) — reculer la date recalcule l'indicateur, comme la frise.

L'indicateur est **contextuel à la phase** : sur une tuile de tomate en avril, la question utile est « planter ? » ; en février, « semer en pépinière ? ». La tuile affiche donc la confiance de **l'action la plus pertinente à la date de référence** — celle dont la fenêtre conseillée contient ou approche cette date — et la nomme. Une culture dont aucune fenêtre n'approche n'affiche rien : l'absence d'indicateur signifie « rien à faire cette semaine », pas « inconnu ».

Une **fiche de détail**, ouverte depuis la tuile, montre les motifs règle par règle (« pourquoi deux étoiles ») et la récolte attendue si le geste est fait cette semaine.

Cette US est **affichage seul** : elle lit le moteur, n'écrit rien, et ne modifie pas la frise. Le composant de frise partagé n'est pas touché.

**Critères d'acceptance :**
- [ ] CA1 : Chaque tuile de culture de l'écran Plan porte, quand une phase de semis ou de plantation est **en fenêtre ou à un mois** de la date de référence, une ligne « *action* · ★★☆ · *premier motif perdu ou, à défaut, premier motif gagné* ». La ligne nomme l'action (« Semer en pépinière », « Semer en place », « Planter »)
- [ ] CA2 : Quand deux phases sont candidates le même mois (semis en place et plantation du concombre en mai), la tuile affiche la phase de **meilleur score** ; à score égal, la règle de priorité déclarée d'US-176 / CA3bis tranche. La règle vit au même endroit que celle de la frise
- [ ] CA3 : Quand aucune phase n'est en fenêtre ni à un mois, la tuile **n'affiche pas de ligne** de confiance. Quand la culture n'a pas de calendrier pour la zone (mode dégradé d'US-176 / CA6), la tuile n'affiche pas de ligne non plus — et la fiche de détail explique la différence entre les deux cas
- [ ] CA4 : L'indicateur suit la **date de référence** de l'écran : la reculer ou l'avancer recalcule l'action affichée et son niveau. Les fenêtres conseillées de la frise, elles, ne changent pas (US-176 / CA10)
- [ ] CA5 : Un appui sur la ligne ouvre une **fiche de détail** : le niveau, chaque règle avec ses points obtenus sur ses points maximum et son motif, typé gagné / perdu / indéterminé, puis la **récolte attendue** si le geste est fait à la date de référence (fourchette ou tiret). La fiche invite à localiser le potager quand les règles météo sont indéterminées
- [ ] CA6 : Les niveaux et motifs de toutes les cultures affichées sont obtenus en **une seule lecture groupée** (US-178 / CA9), jamais une requête par tuile, et l'écran ne clignote pas d'un état sans indicateur vers l'état renseigné (même exigence qu'US-176 / CA11)
- [ ] CA7 : Si la lecture du moteur échoue, l'écran Plan reste utilisable : frises, familles, quantités et durées s'affichent, les indicateurs sont absents, aucune valeur de repli n'est affichée (US-176 / CA12)
- [ ] CA8 : Les étoiles sont rendues **accessibles** : un libellé textuel équivalent (« confiance deux sur trois ») est exposé aux lecteurs d'écran, et le niveau n'est jamais porté par la couleur seule
- [ ] CA9 : La teinte de l'indicateur n'entre en collision avec aucune des teintes de phase de la frise ni avec « en croissance » (US-176 / CA3bis, US-070 / CA7) ; l'indicateur utilise les tokens du design system (Lot A), sans couleur nouvelle
- [ ] CA10 : La fiche d'aide `calendrier-et-zone-climatique.md` est relue et corrigée dans la même livraison (US-099 / CA9)
- [ ] CA11 : Le rendu correspond visuellement à la maquette de référence de l'écran Plan (US-060) et à la maquette de la fiche de détail à 375px / 768px / desktop
- [ ] CA12 : Des tests couvrent : ligne affichée en fenêtre et à un mois, absence hors fenêtre, absence en mode dégradé, choix de phase du CA2, suivi de la date de référence, fiche de détail complète, invitation à localiser, lecture groupée, échec de lecture, accessibilité du CA8, non-régression de la frise et des autres usages de la tuile

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (écran Plan de la PWA)
- Migration BDD requise : **non**
- Dépendances : **US-178** (moteur et lecture groupée, bloquante), **US-176** (frise du référentiel, règle de priorité des phases), **US-060** (écran Plan, date de référence), **US-070** / **US-177** (récolte attendue dans la fiche)
- Impact design system : **aucune évolution du composant de frise**. L'indicateur est un élément nouveau de la tuile ; la fiche de détail est un composant nouveau, à concevoir en variantes avant implémentation (voir la note « Claude Design » du plan de l'épic)
- Impact tokens : zéro (lecture du moteur, déterministe)
- Point de vigilance : la tuile est déjà dense (nom, famille · durée, frise, itinéraire, quantités). La ligne de confiance ajoute une hauteur ; à 375 px, vérifier que la tuile reste lisible et que la ligne se tronque proprement (motif coupé avec ellipse, jamais les étoiles)
- Point de vigilance : « pas de ligne » a deux sens (rien à faire cette semaine / pas de calendrier). La fiche de détail est le seul endroit qui les distingue ; la tuile ne doit pas inventer un troisième état

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Tuile en fenêtre de plantation
  Given mon potager est localisé en zone océanique et la date de référence est le 5 mai
  And la fenêtre de plantation de la tomate couvre avril-mai pour cette zone
  And le moteur rend trois étoiles pour planter la tomate le 5 mai
  When j'ouvre l'écran Plan sur une parcelle contenant des tomates
  Then la tuile de la tomate affiche "Planter · ★★★" suivi d'un motif

Scénario: Deux phases candidates, la meilleure est affichée
  Given le concombre a une fenêtre de semis en place et une fenêtre de plantation en mai
  And le moteur rend deux étoiles pour semer et trois pour planter le 10 mai
  When j'ouvre l'écran Plan le 10 mai
  Then la tuile du concombre affiche "Planter · ★★★"

Scénario: Rien à faire cette semaine
  Given aucune fenêtre de semis ni de plantation de la tomate n'approche le 15 août
  When j'ouvre l'écran Plan le 15 août
  Then la tuile de la tomate n'affiche aucune ligne de confiance
  And sa frise reste inchangée

Scénario: La date de référence recalcule l'indicateur
  Given la tuile de la tomate affiche "Planter · ★★★" au 5 mai
  When je recule la date de référence au 20 février
  Then la tuile affiche "Semer en pépinière" avec son niveau
  And les fenêtres conseillées de la frise sont inchangées

Scénario: Fiche de détail
  Given la tuile du haricot affiche "Semer en place · ★★☆"
  When j'appuie sur cette ligne
  Then je lis chaque règle avec ses points, son motif et son état
  And la récolte attendue en fourchette si je sème à la date de référence

Scénario: Potager non localisé
  Given mon potager n'a pas de localisation
  When j'ouvre la fiche de détail d'une culture en fenêtre
  Then les règles météo sont marquées indéterminées
  And la fiche m'invite à localiser le potager

Scénario: Lecture du moteur en échec
  Given le moteur de confiance ne répond pas
  When j'ouvre l'écran Plan
  Then les frises, familles et quantités s'affichent normalement
  And aucune tuile ne porte d'indicateur
  And aucune valeur de repli n'est affichée
```

**Labels GitHub :** `us`, `frontend`, `pwa`, `cultures`, `plan`

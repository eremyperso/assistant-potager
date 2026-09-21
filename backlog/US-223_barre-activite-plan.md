**ID :** US-223
**Titre :** Ordonner la barre de l'activité Plan — l'ordre du zoom, la date de référence, le Journal du jour
**Épic :** ÉPIC 10 — Plan : l'occupation en rangs et le zoom d'information *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux que le Plan s'ouvre sur la vue d'ensemble, que les sous-onglets soient rangés du plus large au plus détaillé, et que la date et le journal du jour restent au même endroit quel que soit le sous-onglet
Afin de savoir où je suis dans le zoom et de ne pas chercher deux fois le même bouton

**Contexte fonctionnel :**
La sous-navigation de l'activité Plan date d'US-053 : `plan` (Parcelles), `plan-vue` (Vue plan), `plan-rot` (Rotation), dans cet ordre, les deux dernières étant des écrans « à venir » (US-060 / CA17). La v4 pose l'ordre du zoom — « du plus gros vers le plus détaillé » — et fait de la Vue plan l'entrée de l'activité : **règle 19**, « l'ordre des sous-onglets suit le zoom : Vue plan, puis Parcelles, puis Rotation » ; **règle 26**, « Rotation reste dans la barre, désactivée, "à venir" : sa disparition puis son retour coûteraient plus que l'attente ».

La barre porte aussi, sur les deux wireframes v3 et v4, deux éléments identiques d'un sous-onglet à l'autre : la **date de référence** (RT3) et le bouton **« Journal du jour »**, « remonté dans la barre de l'écran pour ne plus dépendre d'une sélection » (v3, règle 14).

Cette US est le préalable de mise en page des deux écrans : elle ne dessine ni la Vue plan (US-200) ni le détail de parcelle (US-222), elle range la barre qui les porte.

⚖️ **Arbitrage A18** : le Plan s'ouvre sur la **Vue plan** une fois US-200 livrée. Tant qu'elle ne l'est pas, l'entrée reste l'onglet Parcelles — on n'ouvre pas une activité sur un écran d'attente.

**Critères d'acceptance :**

- [ ] CA1 : Les sous-onglets de l'activité Plan sont, dans cet ordre : **Vue plan**, **Parcelles**, **Rotation** (règle 19). Les identifiants existants (`plan-vue`, `plan`, `plan-rot`) et les intentions qui les visent (US-195 / CA2) sont inchangés : seul l'ordre d'affichage bouge
- [ ] CA2 : **Rotation** reste visible et **désactivée**, libellée « Rotation · à venir » : elle n'est pas focalisable comme un onglet actif, son état indisponible est annoncé aux lecteurs d'écran, et l'appui n'ouvre rien ni ne provoque d'erreur (règle 26)
- [ ] CA3 : L'activité Plan s'ouvre sur la **Vue plan** dès lors qu'US-200 est livrée ; avant cela, sur l'onglet Parcelles (A18). Le choix est porté par une seule constante de la navigation, pas dupliqué dans les écrans
- [ ] CA4 : Le **dernier sous-onglet visité est restitué** pendant la session : revenir au Plan depuis une autre activité rouvre le sous-onglet quitté, dans son état exact (US-195, règle 25). Une nouvelle session repart de l'entrée du CA3
- [ ] CA5 : La barre porte la **date de référence** (US-030, US-031) et le bouton **« Journal du jour »**, aux mêmes places sur les deux sous-onglets actifs, indépendants de toute sélection de parcelle ; « Journal du jour » ouvre le Journal filtré sur cette date (US-201 / I6, arbitrage A15)
- [ ] CA6 : À 375 px, la barre tient sans défilement horizontal de la page : les libellés se réduisent avant que quoi que ce soit ne sorte de l'écran, les cibles d'appui gardent 44 px, et « Journal du jour » peut s'abréger en « Journal » (v4 § 1b)
- [ ] CA7 : Les autres activités et leurs sous-onglets ne changent pas ; un test de navigation vérifie que les sections `cultures`, `pepiniere`, `stocks` et `journal` gardent leur ordre et leur entrée

*Définition de terminé*
- [ ] CA8 : L'ordre, l'onglet d'entrée, la restitution du dernier sous-onglet et l'état désactivé de Rotation sont couverts par `npm test` sur la lib de navigation
- [ ] CA9 : La fiche `parcelles-et-plan.md` décrit l'activité Plan en trois sous-onglets, dit lequel s'ouvre en premier et que Rotation est à venir (US-099 / CA9) ; `ANALYSE_REFONTE_UI_WEB_2026.md` note que le CA17 d'US-060 est remplacé par cette US
- [ ] CA10 : Le rendu de la barre correspond à la maquette haute fidélité gelée à 375 px, 768 px et desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA, coquille de navigation)
- Migration BDD requise : **non**
- Dépendances : US-053 (coquille à deux niveaux, livrée) ; **US-195** (restitution d'état) ; US-200 conditionne seulement l'onglet d'entrée (CA3), pas la livraison de cette US
- Consommateurs : US-200, US-222
- Impact tokens : zéro
- Impact design system : aucun composant nouveau ; un état « onglet désactivé » est ajouté à la sous-navigation s'il n'existe pas
- Point de vigilance : changer l'onglet d'entrée déplace l'habitude d'un an. C'est l'arbitrage A18 : si le PO préfère garder Parcelles en entrée, seul le CA3 change, le reste de l'US tient
- Point de vigilance : la Rotation est **hors périmètre** des épics 9 à 12 ; cette US ne fait que lui garder sa place
- Wireframe : `maquette front/wireframes/Wireframes v4 - Parcelles et zoom.html`, § 1, § 1b, règles 19, 25, 26 ; v3 règle 14

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: L'ordre du zoom
  Given la Vue plan est livrée
  When j'ouvre l'activité Plan
  Then les sous-onglets sont, dans l'ordre, "Vue plan", "Parcelles" et "Rotation"
  And la Vue plan est ouverte

Scénario: Rotation tient sa place
  When j'appuie sur "Rotation · à venir"
  Then rien ne s'ouvre
  And l'onglet reste annoncé comme indisponible

Scénario: Retour au dernier sous-onglet
  Given j'ai ouvert l'onglet Parcelles sur la planche-ombre
  When je vais dans la Pépinière puis je reviens au Plan
  Then l'onglet Parcelles est rouvert sur la planche-ombre

Scénario: Journal du jour sans sélection
  Given la date de référence est le 21 septembre
  When j'appuie sur "Journal du jour" depuis la Vue plan, puis depuis l'onglet Parcelles
  Then le Journal s'ouvre les deux fois, filtré sur le 21 septembre
```

**Labels GitHub :** `us`, `frontend`, `pwa`, `plan`, `navigation`

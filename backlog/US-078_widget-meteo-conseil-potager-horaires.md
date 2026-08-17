**ID :** US-078
**Titre :** Enrichir le widget météo du Tableau de bord (horaires soleil, libellés et conseil potager)

**Story :**
En tant que jardinier
Je veux voir le lever/coucher du soleil, des libellés clairs pour l'humidité et le vent, et un conseil potager du jour sur la carte météo
Afin de mieux planifier mes interventions sans avoir à interpréter des chiffres bruts

**Contexte fonctionnel :**
US hors décompte du Lot C — enrichit la carte météo livrée par **US-076**, alors que le Lot C
(US-074 à US-077, 18 points) est par ailleurs intégralement clos
(`docs/ANALYSE_REFONTE_UI_WEB_2026.md` §5.2 ter, §7.1). Même traitement que US-066 en son
temps pour le Lot B : rattachée fonctionnellement au lot qu'elle enrichit, comptée à part
dans le suivi de points pour ne pas rouvrir un lot déjà déclaré clos.

`GET /meteo` (US-075) expose déjà, dans sa réponse, trois champs que `views/Dashboard.jsx`
(`CarteMeteo`, US-076) ne consomme pas encore : `lever_soleil`/`coucher_soleil` (chaînes
`"HH:MM"`) et `conseil` (texte court généré localement par `_conseil_potager()` dans
`utils/meteo.py`, zéro appel Groq — jusqu'à ~5 phrases courtes concaténées par `" · "` selon
les conditions du jour : gel/canicule, pluie, vent, brouillard, conditions idéales). **Aucune
migration ni modification backend n'est nécessaire** : il s'agit d'un enrichissement de
consommation frontend d'une donnée déjà disponible.

La ligne d'info actuelle du jour (`ressenti X° · Y % · Z km/h`) juxtapose humidité et vent
sans libellé — lisible pour qui a construit l'écran, ambigu pour un nouvel utilisateur qui
découvre la carte.

**Maquette : aucune nouvelle maquette Claude Design n'est nécessaire.** Vérification faite
sur la maquette figée du 15/08/2026 (`Maquette figée/web-screens.jsx`, composant
`ScreenDashboard`) et sur les composants partagés (`Maquette figée/web-parts.jsx`) : ni le
lever/coucher du soleil, ni le conseil potager, ni un pattern de texte tronqué avec lien
« afficher plus » n'y figurent — la carte météo de la maquette s'arrête à ville/température/
ressenti-humidité-vent/prévision 5 jours, déjà couverte par US-076. Ce n'est pas un nouvel
écran mais un enrichissement incrémental d'une carte déjà livrée : même précédent que US-077,
dont la modale de personnalisation a été construite directement sur le design system
(`Card`, typographie, tokens) sans aller-retour maquette dédié. Le CA type ci-dessous porte
donc sur la cohérence avec le design system, pas sur une conformité pixel à une maquette de
référence — à rouvrir si l'exemple visuel fourni au cadrage (capture d'un bloc de texte
tronqué avec lien « …afficher plus », hors de notre maquette) s'avère insuffisant pour cadrer
le rendu attendu.

**Critères d'acceptance :**
- [ ] CA1 : La carte météo affiche le lever et le coucher du soleil du jour courant, à partir
      de `lever_soleil`/`coucher_soleil` (`GET /meteo`, déjà exposés)
- [ ] CA2 : La ligne d'info du jour affiche des libellés explicites pour l'humidité et le vent
      (ex. « Humidité : 42 % », « Vent : 13,7 km/h ») au lieu de valeurs brutes juxtaposées ;
      « ressenti X° » reste au même endroit
- [ ] CA3 : Le conseil potager du jour (`conseil`, `GET /meteo`, déjà exposé) est affiché sous
      les informations ressenti/humidité/vent
- [ ] CA4 : Le cadre affichant le conseil a une hauteur maximale figée ; si le texte dépasse
      cette hauteur, il est tronqué visuellement et un lien « afficher plus » apparaît — le
      cliquer déplie le texte en entier dans le même cadre (pas de modale, pas de navigation)
- [ ] CA5 : Si le conseil tient dans la hauteur figée sans troncature, aucun lien
      « afficher plus » n'apparaît (pas de lien inutile sur un texte déjà entièrement visible)
- [ ] CA type (US avec impact visuel/UI) : Le rendu est cohérent avec le design system
      (`Card`, typographie et tokens déjà utilisés par la carte météo, US-076) à
      375px/768px/desktop — pas de maquette Claude Design dédiée pour ce composant précis,
      cf. Contexte fonctionnel

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non — `lever_soleil`, `coucher_soleil` et `conseil` sont déjà
  renvoyés par `GET /meteo` (US-075), aucun changement backend
- Dépendances : US-076 (widget météo à enrichir), US-075 (`GET /meteo`, source des trois
  champs déjà exposés mais non consommés)

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Horaires de lever et coucher du soleil affichés
  Given un potager localisé avec des données météo disponibles (US-076)
  When l'utilisateur ouvre l'onglet "Tableau de bord"
  Then la carte météo affiche l'heure de lever et l'heure de coucher du soleil du jour courant

Scénario: Libellés explicites pour l'humidité et le vent
  Given la carte météo affichée avec des données du jour
  When l'utilisateur consulte la ligne d'information du jour
  Then l'humidité et le vent sont précédés d'un libellé explicite, pas seulement d'une valeur brute

Scénario: Conseil potager court, sans troncature
  Given un conseil du jour tenant dans la hauteur figée du cadre
  When la carte météo s'affiche
  Then le conseil est visible en entier, sans lien "afficher plus"

Scénario: Conseil potager long, avec troncature
  Given un conseil du jour dépassant la hauteur figée du cadre (plusieurs recommandations concaténées)
  When la carte météo s'affiche
  Then le texte est tronqué visuellement et un lien "afficher plus" apparaît
  And cliquer sur ce lien déplie le conseil en entier dans le même cadre
```

**Labels GitHub :** `us`, `sprint-refonte-ui-2026`, `frontend`, `lot-c`

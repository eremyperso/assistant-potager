**ID :** US-201
**Titre :** Relier la Vue plan et l'onglet Parcelles aux autres écrans — rang, fiche parcelle, pépinière, journal du jour
**Épic :** ÉPIC 10 — Plan : l'occupation en rangs et le zoom d'information *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux qu'un appui sur un rang m'ouvre tout ce que l'application sait de cette culture, qu'un appui sur un rang libre me permette d'y semer ou d'y planter, et que le Plan me mène à la parcelle, à la pépinière ou au journal du jour
Afin de passer de « où est quoi » à « qu'est-ce que j'en fais » sans chercher dans les menus

**Contexte fonctionnel :**
La v3 supprime le panneau de détail des versions précédentes : « Il reformatait les mêmes informations que la carte. La carte devient donc l'unique représentation : elle porte le lien vers la fiche parcelle, chaque rang mène à sa culture, et « Journal du jour » remonte dans la barre de l'écran pour ne plus dépendre d'une sélection. » Elle fixe **quatre sorties, aucune vue dupliquée** (règle 17) : le rang → fiche culture, l'en-tête de carte → fiche parcelle, la carte de la pépinière → Pépinière, la barre → Journal du jour.

Cette US branche ces sorties sur la Vue plan dessinée par US-200 (règles d'interaction 10 à 14 et 17 de la v3), à l'aide de la navigation contextuelle (US-195), de la fiche culture (US-207) et du geste pré-rempli (US-196).

Elle ajoute aussi à l'onglet **Parcelles** l'entrée vers la fiche culture. ⚖️ **Arbitrage A7** : la v1 retirait de la tuile de culture sa frise et sa puce de confiance, la v2 la garde comme entrée de la fiche calendrier (US-183 / CA2). La v2 est retenue : la tuile est **inchangée** — US-180 et US-183 viennent d'être livrées — et gagne seulement un lien « Voir la culture ». La simplification de la v1 reste une décision ouverte, à reprendre quand l'écran Cultures sera en service.

**Règles d'interaction (v3) :**

| # | Règle |
|---|---|
| I1 | **Pas de panneau de détail, pas de feuille**, aucun état « parcelle sélectionnée » (règle 10) |
| I2 | **Appui sur un rang occupé** → la fiche de la culture de ce rang, directement, ouverte en panneau par-dessus la Vue plan, avec la parcelle en contexte (règle 11) |
| I3 | **Appui sur un rang libre** → « ajouter une culture » : choix entre *Semer en place* et *Planter*, puis geste pré-rempli avec la parcelle (et le rang, si US-203 est livrée) ; la culture est demandée par le compagnon (règle 11) |
| I4 | **« Fiche parcelle → »** dans l'en-tête de chaque carte : l'onglet Parcelles, cette parcelle sélectionnée — seul accès à la parcelle elle-même (règle 11b) |
| I5 | **Carte d'une pépinière** → la Pépinière, sur cet emplacement : onglet « Emplacements » si le potager compte plusieurs pépinières, « Aujourd'hui » sinon (règle 17) |
| I6 | **« Journal du jour »** dans la barre de l'écran, indépendant de toute sélection → le Journal filtré sur la date de référence (règle 14, arbitrage A15) |
| I7 | **Aucun geste de dessin** : ni zoom, ni déplacement de la vue, ni glisser-déposer de culture, ni redimensionnement. « Le Plan n'est pas un éditeur » (règle 12) |

**Critères d'acceptance :**

*Vue plan*
- [ ] CA1 : Un appui (clic, Entrée, Espace) sur un rang occupé ouvre la **fiche culture** (US-207) de sa culture, avec la parcelle en contexte : si le jardinier ouvre ensuite la fiche calendrier depuis la fiche culture, la série de **cette** parcelle y est mise en avant, comme depuis une tuile (US-183 / CA2)
- [ ] CA2 : La cible d'appui d'un rang couvre **le trait et son libellé**, 44 px de haut au minimum à 375 px
- [ ] CA3 : Un appui sur un rang libre propose *Semer en place* ou *Planter* et prépare le geste (US-196) avec la parcelle ; aucune écriture n'a lieu dans la PWA. Pour un membre en lecture seule, un rang libre n'est pas actionnable et la mention « ajouter une culture » n'est pas affichée (RT11)
- [ ] CA4 : « Fiche parcelle → » ouvre l'onglet Parcelles sur cette parcelle (US-195) ; la carte d'une pépinière ouvre la Pépinière selon I5 ; « Journal du jour » ouvre le Journal filtré sur la date de référence
- [ ] CA5 : Fermer la fiche culture rend la Vue plan dans son état exact, défilement compris, et le focus revient sur le rang d'origine (US-195 / CA8)
- [ ] CA6 : Aucun zoom, aucun déplacement, aucun glisser-déposer n'est possible sur les cartes ou les rangs (I7) ; la Vue plan n'a aucun état de sélection
- [ ] CA7 : Les rangs de la carte « non localisé » ouvrent eux aussi la fiche de leur culture, sans contexte de parcelle

*Onglet Parcelles*
- [ ] CA8 : Chaque tuile de culture de l'onglet Parcelles porte un lien « Voir la culture » qui ouvre la même fiche culture, avec la parcelle en contexte ; la tuile entière est une cible d'appui menant au même endroit. Tout le reste de la tuile est **inchangé** : frise, pastille de confiance, ouverture de la fiche calendrier, observations, sélection (arbitrages A7 et A21). Le **numéro de rang et le trait** que la v4 ajoute à cette tuile ne sont pas de cette US : ils viennent avec US-222, qui recoud l'onglet Parcelles sur la Vue plan

*Définition de terminé*
- [ ] CA9 : La correspondance « élément appuyé → destination et intention » vit dans la lib de la Vue plan et est couverte par `npm test` (rang occupé, rang libre, en-tête, pépinière avec une ou plusieurs pépinières, non localisé, lecteur)
- [ ] CA10 : La fiche `parcelles-et-plan.md` dit ce qu'ouvre chaque appui de la Vue plan et comment ajouter une culture sur un rang libre (US-099 / CA9)
- [ ] CA11 : Le rendu des éléments ajoutés (choix *Semer en place / Planter*, lien « Voir la culture ») correspond à la maquette haute fidélité gelée à 375 px, 768 px et desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA, écran Plan)
- Migration BDD requise : **non**
- Dépendances : **US-200** (Vue plan), **US-195** (navigation contextuelle), **US-207** (fiche culture), **US-196** (geste pré-rempli) — toutes bloquantes pour la sortie qu'elles portent ; US-203 (rang pré-rempli), optionnelle
- Impact tokens : zéro
- Point de vigilance : aucune sortie ne duplique une vue. La Vue plan ne réaffiche ni la frise, ni la confiance, ni le détail d'une parcelle : elle **renvoie** vers l'écran qui les porte
- Point tranché (arbitrages A7 puis A21) : la tuile de l'onglet Parcelles **garde** sa frise et sa puce de confiance. La v1 proposait de les retirer ; la v4 confirme l'inverse en faisant du niveau 2 le seul porteur de la frise conseillée et de la confiance (matrice « qui porte quoi », § 2). Reste à vérifier en haute fidélité que la tuile tient à 375 px une fois son trait de rang ajouté (US-222)
- Wireframe : v3 § 3, colonne « Interaction », règles 10 à 14 et 17

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Du rang à la fiche culture, puis à la fiche calendrier
  Given la Vue plan affiche le rang 2 de la planche-ombre : tomate cerise, 5 plants
  When j'appuie sur ce rang
  Then la fiche de la tomate s'ouvre par-dessus la Vue plan
  When j'ouvre la fiche calendrier depuis la fiche de la tomate
  Then la série de la planche-ombre y est mise en avant

Scénario: Ajouter une culture sur un rang libre
  Given le rang 5 de la planche-centrale est libre
  When j'appuie sur ce rang et je choisis "Planter"
  Then mon compagnon s'ouvre sur une plantation pré-remplie dans la planche-centrale
  And la culture m'est demandée

Scénario: Pas d'ajout en lecture seule
  Given je suis membre du potager en lecture seule
  When j'ouvre la Vue plan
  Then les rangs libres ne portent pas "ajouter une culture"

Scénario: De la Vue plan à la pépinière
  Given le potager compte deux pépinières, la serre et le châssis froid
  When j'appuie sur la carte de la serre
  Then la Pépinière s'ouvre sur l'onglet "Emplacements", sur la serre

Scénario: Voir la culture depuis l'onglet Parcelles
  Given l'onglet Parcelles affiche la tuile "courgette" de la planche-centrale
  When j'appuie sur "Voir la culture"
  Then la fiche de la courgette s'ouvre
  And la frise et la pastille de confiance de la tuile sont toujours là
```

**Labels GitHub :** `us`, `frontend`, `pwa`, `plan`, `navigation`

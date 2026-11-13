**ID :** US-327
**Titre :** Afficher le plan du potager vu du dessus
**Épic :** ÉPIC 19 — Plan du potager sur vue du dessus *(numéro à valider)*

**Story :**
En tant que jardinier
Je veux voir mes parcelles à leur place, à l'échelle, avec dans chaque rang ce qui pousse et à quelle étape
Afin de retrouver sur l'écran l'image que j'ai de mon potager

**Contexte fonctionnel :**
Maquette de référence : `Plan - Pistes.html`, « Piste C retenue · Plan sur vue du dessus » (ordinateur) et piste A (« Plan aimanté sur grille »), qui sert de **repli sans fond**. Cette US livre le plan **sans photo** : fond en grille neutre (« Fond masqué »). La photo est l'objet d'US-335.

Elle **remplace** la Vue plan « rangs et places » (US-200, US-228) : la maquette la déclare inadaptée — elle montre le modèle de données au lieu du potager. Les places ne disparaissent pas, elles passent dans le suivi de culture (US-322 / S3).

**Règles de rendu :**

| # | Règle |
|---|---|
| P1 | Chaque parcelle placée est dessinée à sa position, sa taille et sa rotation (US-326), toutes à la même échelle ; le cadre du potager suit son emprise |
| P2 | Ses rangs suivent le **sens des rangs** ; chaque rang est découpé en **segments**, un par culture, de longueur proportionnelle à sa part ; un segment libre est en pointillé |
| P3 | Un segment porte la couleur de l'étape (US-321) et, selon la place disponible : emoji + nom + pictogramme ; emoji + pictogramme ; pictogramme seul ; rien. Rangs en travers : nom écrit verticalement |
| P4 | Étape prévue : segment hachuré, pastille orange si à confirmer |
| P5 | Le nom de la parcelle est un bouton posé sur la parcelle ; serre, planche, bac et butte ont chacun leur fond de parcelle |
| P6 | Une **parcelle pépinière** (froide ou chaude) affiche ses lots en vignettes (emoji, n° de lot, nom si la place le permet), **sans étapes ni actions** ; toucher un lot ouvre sa fiche dans « Ma pépinière » (US-216) |
| P7 | Une parcelle **inactive** reste sur le plan, grisée |
| P8 | **Filtres** : Tout · À confirmer · N · En récolte · Rangs libres — les segments hors filtre s'estompent, rien ne disparaît |
| P9 | **Rose des vents** orientée selon le nord du potager ; **échelle** « 5 m » ; **légende** des étapes (US-321) sous le plan |
| P10 | Une parcelle **non placée** n'est pas dessinée : elle est listée « À placer » (US-328). Tant qu'aucune parcelle n'est placée, la vue retombe sur le **plan par zones** (piste B : une tuile par parcelle, dans l'ordre du chemin) |
| P11 | En-tête : « Au 12 novembre » (date de référence), fond utilisé, emprise « 25 × 15 m » |

**Interactions :**
- Toucher un segment de culture ouvre son suivi (US-322) ; le segment choisi est cerclé
- Toucher le nom d'une parcelle ouvre son détail (US-330) ; la parcelle choisie est cerclée
- Toucher un rang libre : « Rang libre : glissez une culture « À placer », ou dites-le à Gaston »
- Le plan **n'écrit rien** : aucune géométrie ne se modifie ici (US-333)

**Critères d'acceptance :**
- [ ] CA1 : Les règles P1 à P11 sont appliquées à partir de la seule lecture de `GET /plan`
- [ ] CA2 : Le calcul des positions, des segments et du libellé selon la taille vit dans une lib sans React (`frontend/src/lib/`), couverte par `npm test`
- [ ] CA3 : Chaque segment est un bouton dont le nom accessible dit tout : « Fève Aguadulce, Levé, prévu, à confirmer, Planche centrale rang 6 » ; l'ordre de tabulation suit parcelle par parcelle, rang par rang
- [ ] CA4 : Les compteurs des filtres sont ceux du serveur ; « À confirmer · N » est exact à la date de référence
- [ ] CA5 : Ordinateur : plan à gauche, panneau de droite à droite (US-328, US-322, US-330) ; le plan défile dans son cadre si l'écran est plus étroit que l'emprise, jamais la page
- [ ] CA6 : Les composants de l'ancienne Vue plan sortent de l'écran Plan ; ceux réutilisés ailleurs (piste des places dans le suivi) restent
- [ ] CA7 : Chargement en squelette, échec avec `ApiError` et relance, potager sans parcelle avec l'invitation d'US-334
- [ ] CA8 : Une page de contrôle visuel rejoue : potager complet, parcelle en travers, rang partagé, pépinière, parcelle inactive, aucune parcelle placée (zones), filtres, thème sombre
- [ ] CA9 : La fiche `parcelles-et-plan.md` est réécrite (« Lire le plan ») et le guide utilisateur mis à jour ; corpus vert
- [ ] CA type : Le rendu correspond visuellement à la maquette de référence en desktop et 768 px ; vérification chrome-devtools

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA)
- Migration BDD requise : non
- Dépendances : **US-320**, **US-321**, **US-326** (bloquantes) ; US-216 (fiche lot, livrée)
- Remplace le rendu d'US-200 et d'US-228 ; leurs patch notes et la fiche d'aide doivent l'annoncer (régression visible : les places quittent le plan)
- Modèle / effort conseillé : Sonnet 5.5, `high` — rendu géométrique à rotation, accessibilité d'un dessin, remplacement d'un écran livré ; Opus non requis

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Scénario: Lire le potager
  Given la planche centrale est placée à 9 m du bord, 12 × 5 m, rangs dans la longueur
  And son rang 3 porte du chou de Bruxelles (0,6) et du chou kale (0,4), en récolte
  When j'ouvre le Plan
  Then la planche est dessinée à sa place, à l'échelle
  And son rang 3 porte deux segments orange, de longueurs 60 % et 40 %

Scénario: Filtrer ce qui est à confirmer
  Given 3 cultures sont à confirmer
  When je touche "À confirmer · 3"
  Then seuls leurs segments restent pleinement visibles

Scénario: Aucune parcelle placée
  Given aucune parcelle n'a encore de position
  When j'ouvre le Plan
  Then je vois les parcelles en tuiles, dans l'ordre du chemin
  And une invitation à mettre en place le plan
```

**Labels GitHub :** `us`, `frontend`, `pwa`, `plan`

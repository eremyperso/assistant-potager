**ID :** US-241
**Titre :** Déplacer une partie des godets d'un lot, et ranger un lot dont la pépinière n'est pas connue
**Épic :** ÉPIC 12 — Pépinière : le poste de travail sous abri *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier qui sort une partie de ses godets au châssis froid pour les endurcir, et garde le reste au chaud
Je veux dire « j'ai passé 6 godets du lot 21 au châssis » et ranger d'un appui un lot dont je n'avais pas dit la pépinière
Afin que l'application sache où se trouve chaque godet, et que l'endurcissement de ceux que j'ai sortis commence le jour où je les ai sortis

**Contexte fonctionnel :**
US-211 a créé le geste **déplacement**, en le limitant au **lot entier** : « déplacer une partie des godets seulement est hors périmètre » (plan des épics § 9). Le terrain contredit cette limite chaque automne : on sort une partie des poivrons au châssis, on garde les plus petits en serre. Le wireframe « C · Le parcours du plant — v2 » le dessine (poivron #21 : 10 godets en serre chaude, 6 au châssis froid). L'arbitrage **A32** rouvre donc le déplacement partiel.

Cette US étend US-211 sans la rouvrir : le déplacement gagne une **quantité facultative**. Sans quantité, il porte sur le lot entier, exactement comme aujourd'hui. Avec une quantité, une partie des godets change de pépinière et le lot se retrouve **coupé par l'emplacement** : US-240 en fait deux étiquettes, au même numéro.

Elle couvre aussi le cas « Sans emplacement » de l'écran Parcours : un lot dont la pépinière n'a jamais été dite reçoit, depuis son étiquette, un **déplacement sans destination**, que le compagnon complète en demandant où il est.

Un déplacement ne touche à **aucun stock** (US-211 / CA7) : il ne fait que répartir des godets existants entre des pépinières.

**Critères d'acceptance :**

*Le déplacement partiel*
- [ ] CA1 : Le geste **déplacement** (US-211) accepte une **quantité de godets** facultative. Sans quantité, il porte sur le lot entier, comportement d'US-211 inchangé. Avec une quantité égale aux godets disponibles à l'origine, c'est aussi un déplacement entier
- [ ] CA2 : Il se dicte sans appel au modèle : « passé 6 godets du lot 21 au châssis froid », « sorti 6 poivrons de la serre au châssis », « déplacé 10 godets de tomate cerise sous le châssis ». Le corpus de dictée porte ces formes à côté des formes sans quantité d'US-211, et à côté d'une plantation et d'une mise en godet chiffrées, sans confusion
- [ ] CA3 : **L'origine** est l'emplacement où se trouvent les godets du lot. Si le lot est déjà réparti sur plusieurs pépinières et que la phrase ne dit pas d'où viennent les godets, le compagnon propose les origines par boutons, avec le nombre de godets de chacune
- [ ] CA4 : Une quantité **supérieure** aux godets disponibles à l'origine est refusée avec le nombre disponible (« le lot 21 n'a que 10 godets en serre ») ; une quantité nulle ou négative est refusée ; rien n'est enregistré
- [ ] CA5 : Les **graines** d'un lot (étiquette « en levée ») ne se déplacent pas partiellement : elles suivent un déplacement du lot entier, jamais un déplacement chiffré en godets
- [ ] CA6 : Le récapitulatif dit la quantité, l'origine et la destination (« 6 godets du lot 21 · serre chaude → châssis froid ») ; le geste se confirme, se corrige et se supprime par le parcours existant (US-021, Journal). Corriger ou supprimer un déplacement recalcule la répartition des godets

*Ses effets*
- [ ] CA7 : La **répartition des godets par pépinière** d'un lot se déduit de ses déplacements, dans l'ordre des dates ; à une date de référence antérieure, la répartition est celle de cette date. US-240 la lit pour produire une étiquette par emplacement
- [ ] CA8 : Le compte à rebours d'endurcissement se calcule **par emplacement** : la partie déplacée vers une pépinière froide commence son endurcissement le jour de son déplacement (US-214 / CA4), la partie restée au chaud garde le sien
- [ ] CA9 : **Consommation d'un lot réparti — arbitrage A41 EN SUSPENS** (décision du PO le 19/10/2026 : à régler après une série de tests terrain). Tant qu'il n'est pas tranché, **aucune règle d'attribution automatique** n'est développée : un geste qui retire des godets (plantation, perte, vente) d'un lot réparti sur plusieurs pépinières, et qui ne dit pas d'où ils viennent, fait **demander l'origine par boutons** (même mécanique que CA3), avec le nombre de godets de chaque pépinière. Un geste déposé depuis une étiquette de l'écran Parcours porte son emplacement. La règle « d'abord la partie la plus avancée » reste une piste, non retenue
- [ ] CA10 : Aucun stock ne change : `GET /godets`, `GET /stats`, `GET /plan` et l'écran Stocks rendent les mêmes valeurs avant et après un déplacement partiel (US-211 / CA7)
- [ ] CA11 : Le détail du cycle de vie d'un lot (US-061, US-216 / CA7) affiche chaque déplacement partiel à sa date, avec quantité, origine et destination

*Ranger un lot sans emplacement*
- [ ] CA12 : Un déplacement peut être **déposé sans destination** depuis la PWA (« Ranger dans… », US-218), avec le lot et, facultativement, une quantité. Le compagnon demande la destination en proposant par boutons les pépinières du potager, hors l'emplacement courant
- [ ] CA13 : Un lot dont l'emplacement est **inconnu** (US-210 / CA5) peut être déplacé : l'origine est dite « emplacement non renseigné » dans le récapitulatif et dans le cycle de vie
- [ ] CA14 : Le geste est ouvert à la PWA par le geste pré-rempli et la file des gestes (US-196, US-224), avec son gabarit de phrase reconnu par le parseur, quantité et destination facultatives

*Définition de terminé*
- [ ] CA15 : Le catalogue des commandes et la parité bot / PWA sont à jour (RT10) ; `/help` et le corpus de dictée suivent
- [ ] CA16 : Des tests couvrent : déplacement entier inchangé, partiel, quantité égale au disponible, quantité excessive, nulle, origine ambiguë, lot sans emplacement, dépôt sans destination, retour d'une partie à l'origine (le lot redevient d'un seul tenant), endurcissement par emplacement, lot réparti avec et sans emplacement dit (origine demandée), correction et suppression, date de référence antérieure, stocks inchangés, isolation entre potagers
- [ ] CA17 : La fiche de domaine `docs/domaines/pepiniere.md` consigne la répartition par emplacement, l'endurcissement par emplacement et le point ouvert A41
- [ ] CA18 : Les fiches du corpus qui disaient qu'un déplacement porte sur le lot entier sont corrigées (`pepiniere-par-lot.md`, `enregistrer-un-geste.md` ou celles que désigne la table du corpus), ainsi que le guide utilisateur (US-099 / CA9)

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram, enregistrement
- Migration BDD requise : **à confirmer au développement** — non si l'événement de déplacement peut porter une quantité ; sinon une colonne nullable, avec son rollback
- Dépendances : **US-211** (déplacement), **US-224** (file des gestes) ; US-210 (emplacement courant), US-214 (endurcissement), US-240 (étiquettes par emplacement) — US-240 et US-241 sont livrées ensemble (livraison L1)
- Impact tokens : zéro sur la dictée (grammaire déterministe) ; le choix d'origine et de destination se fait par boutons
- Point de vigilance : c'est la seule US de la vue Parcours qui touche au **modèle de données** de l'emplacement ; une erreur de répartition fausserait l'écran sans fausser les stocks — d'où le test « stocks inchangés »
- Point de vigilance : **reproducteur vs végétatif** — sans objet en pépinière ; le type d'organe ne joue qu'après la mise en terre
- Hors périmètre : déplacer une partie des **graines** (barquette coupée en deux), plaque et alvéole (A12)

**Estimation :** 8 points *(à rechiffrer quand A41 sera tranché : sans règle d'attribution automatique, plutôt 5)*

**Scénario Gherkin :**
```gherkin
Scénario: Sortir une partie des godets au froid
  Given le lot 21, poivron, 16 godets en serre chaude
  When je dis "passé 6 godets du lot 21 au châssis froid"
  Then le compagnon récapitule "6 godets du lot 21 · serre chaude → châssis froid"
  When je confirme
  Then le lot 21 a 10 godets en serre chaude et 6 au châssis froid
  And les stocks de godets sont inchangés
  And l'endurcissement des 6 godets commence ce jour

Scénario: Quantité excessive
  Given le lot 21 a 10 godets en serre chaude
  When je dis "passé 12 godets du lot 21 au châssis"
  Then le compagnon répond "le lot 21 n'a que 10 godets en serre"
  And rien n'est enregistré

Scénario: Planter depuis un lot réparti
  Given le lot 21 a 10 godets en serre chaude et 6 au châssis froid
  When je dis "planté 6 poivrons du lot 21 dans la planche sud"
  Then le compagnon demande d'où viennent les godets, par boutons "Serre chaude (10)" et "Châssis froid (6)"

Scénario: Ranger un lot sans emplacement
  Given le lot 26, tomate noire de Crimée, 8 godets, sans emplacement connu
  When j'appuie sur "Ranger dans…" sur son étiquette
  Then un déplacement du lot 26 est déposé dans la file, sans destination
  And le compagnon me propose "Serre chaude" et "Châssis froid" par boutons

Scénario: Déplacement sans quantité
  Given le lot 24, poireau, 30 godets en serre chaude
  When je dis "passé le lot 24 au châssis froid"
  Then les 30 godets sont au châssis froid, comme avant cette US
```

**Labels GitHub :** `us`, `bot`, `backend`, `pepiniere`

**ID :** US-211
**Titre :** Déplacer un lot d'une pépinière à l'autre
**Épic :** ÉPIC 12 — Pépinière : le poste de travail sous abri *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux dire « j'ai passé le lot 119 sous le châssis froid » quand je sors mes plants de la serre pour les endurcir
Afin que l'application sache où sont mes plants aujourd'hui, et que l'endurcissement commence le jour où je les ai sortis

**Contexte fonctionnel :**
US-210 donne à chaque lot un **emplacement courant** : celui de son semis, ou de sa mise en godet quand elle a été localisée. Mais un lot bouge encore après : les godets de tomates levés au chaud en mars passent au châssis froid fin avril pour s'endurcir avant la plantation. Sans geste pour le dire, l'onglet Emplacements (US-219) montrerait la serre pleine alors qu'elle est vide, et le compte à rebours d'endurcissement (US-214) ne saurait pas que les plants sont déjà dehors.

La v2 note le risque (« une étiquette imprimée est une donnée figée collée sur du vivant : le lot bouge ») sans dessiner le geste. Cette US l'ajoute au référentiel d'actions : un **déplacement**, qui ne touche à aucun stock et ne fait que changer l'emplacement d'un lot.

⚖️ En V1, un déplacement porte sur **le lot entier**. Déplacer une partie des godets seulement est hors périmètre (plan des épics § 9).

**Critères d'acceptance :**

*Le geste*
- [ ] CA1 : Le référentiel d'actions (US-168) gagne le geste **déplacement** : un lot, une pépinière de destination, une date. Il est normalisé à l'écriture comme les autres gestes
- [ ] CA2 : Il se dicte, reconnu par la grammaire déterministe sans appel au modèle : « passé le lot 119 au châssis froid », « sorti les poireaux de la serre pour le châssis », « déplacé les godets de tomate cerise sous le châssis ». Il n'est confondu ni avec une plantation (« mis en terre », « planté »), ni avec une mise en godet (« repiqué en godet ») ; le corpus de dictée porte ces formes côte à côte
- [ ] CA3 : **Le lot** est désigné par son numéro (US-209) ou par sa culture et sa variété. Un seul lot en cours correspond : il est retenu. Plusieurs : le bot propose les lots par boutons, avec numéro et date de semis (modèle d'US-019). Aucun : le geste est refusé avec la raison
- [ ] CA4 : **La destination** doit être une pépinière du potager. Une parcelle ordinaire est refusée avec la précision que mettre des plants en terre est une plantation ; une destination égale à l'emplacement courant est signalée (« le lot 119 est déjà sous le châssis ») et rien n'est enregistré
- [ ] CA5 : Le geste est récapitulé et confirmé comme les autres (US-021) ; il apparaît au **Journal**, se corrige et se supprime par le parcours existant

*Ses effets*
- [ ] CA6 : Le déplacement devient la première source de l'**emplacement courant** d'un lot (US-210 / CA5) à partir de sa date ; la date de référence antérieure le voit encore à son ancien emplacement
- [ ] CA7 : Il ne modifie **aucun stock** — graines, godets, plants — ni le Plan, ni les statistiques : un test compare `GET /godets`, `GET /stats` et `GET /plan` avant et après
- [ ] CA8 : Le détail du cycle de vie d'un lot (modale existante d'US-061) affiche le déplacement à sa date, avec l'origine et la destination
- [ ] CA9 : Le geste est ouvert à la PWA par le geste pré-rempli d'US-196, avec son gabarit de phrase reconnu par le parseur

*Définition de terminé*
- [ ] CA10 : Les fiches `semis-godet-plantation.md` (sortir ses plants pour les endurcir), `pepiniere-par-lot.md` (où est un lot), `enregistrer-un-geste.md` (la liste des gestes reconnus), `journal-et-corrections.md` et le guide utilisateur (§ 6.3) sont mis à jour (US-099 / CA9)
- [ ] CA11 : Des tests couvrent : chaque forme dictée, la non-confusion avec plantation et mise en godet, désignation par numéro, par culture unique, par choix entre plusieurs lots, lot inexistant, destination ordinaire refusée, destination identique, correction et suppression au Journal, emplacement courant avant et après la date, absence d'effet sur les stocks

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram, enregistrement
- Migration BDD requise : **non** si le type d'action n'est pas contraint en base ; à vérifier au démarrage, auquel cas une migration ajoute la valeur au vocabulaire (numéro à lire dans `migrations/`)
- Dépendances : **US-210** (emplacement courant), **US-209** (numéro de lot) ; US-208 (type de la destination)
- Consommateurs : US-214 (endurcissement), US-216 (bouton « Déplacer »), US-219 (Emplacements)
- Impact tokens : zéro sur le chemin déterministe
- Point de vigilance : « sortir » est ambigu au jardin (« sorti les tomates » peut vouloir dire les planter). Sans pépinière de destination nommée, la phrase n'est **pas** un déplacement : elle rejoint le flux habituel, qui demandera
- Point de vigilance : **reproducteur vs végétatif** — sans objet : un lot en pépinière n'a encore rien produit, le type d'organe n'intervient pas

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Sortir un lot pour l'endurcir
  Given le lot 119, 41 godets de poireau, est dans la serre, pépinière chaude
  When le jardinier dicte "passé le lot 119 au châssis froid"
  Then le bot récapitule "déplacement du lot 119 (poireau) de la serre au châssis froid"
  When le jardinier confirme
  Then le lot 119 a pour emplacement le châssis froid
  And il compte toujours 41 godets

Scénario: Plusieurs lots possibles
  Given deux lots de tomate cerise en cours, 131 et 134
  When le jardinier dicte "déplacé les tomates cerise sous le châssis"
  Then le bot propose de choisir entre le lot 131 et le lot 134

Scénario: Destination qui n'est pas une pépinière
  When le jardinier dicte "passé le lot 119 dans la planche nord"
  Then le bot refuse le déplacement
  And rappelle que mettre des plants en terre s'enregistre comme une plantation

Scénario: Date de référence antérieure
  Given le lot 119 a été déplacé au châssis le 20 septembre
  When je consulte la pépinière au 15 septembre
  Then le lot 119 est dans la serre
```

**Labels GitHub :** `us`, `bot`, `backend`, `enregistrement`, `pepiniere`

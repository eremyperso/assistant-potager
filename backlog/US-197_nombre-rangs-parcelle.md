**ID :** US-197
**Titre :** Déclarer le nombre de rangs d'une parcelle
**Épic :** ÉPIC 10 — Plan : l'occupation en rangs et le zoom d'information *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux dire à l'application combien de rangs compte chacune de mes planches
Afin que le Plan me montre ce qui est occupé et, surtout, combien de rangs il me reste de libres

**Contexte fonctionnel :**
La Vue plan V1 (wireframe v3) se lit en **rangs** : « Le nombre de rangs déclaré fait la hauteur de la parcelle. Un rang sans culture est un trait pointillé cliquable : c'est la place libre, exprimée dans la seule unité dont on dispose — le rang. » La mesure d'occupation devient « 13 rangs occupés sur 18 déclarés ».

Le wireframe affirme que ce nombre « existe déjà ». **Il n'existe pas** : la parcelle porte `nom`, `superficie_m2`, `exposition`, `type_sol`, `ordre`, `est_pepiniere` ; `/parcelle modifier` ne connaît que `exposition`, `superficie`, `ordre` et `pepiniere`. Le seul « rang » de la base est celui d'un **événement**, et c'est un multiplicateur (« 4 salades sur 3 rangs » = 12 plants) — sans rapport avec le nombre de rangs d'une planche.

Cette US ajoute ce nombre à la parcelle, le rend déclarable **au bot** (le backoffice de l'application : v3, « la saisie reste au backoffice ») et le sert à la PWA. Elle ne dessine rien : c'est US-200 qui en tire le dessin.

**Critères d'acceptance :**
- [ ] CA1 : Une parcelle porte un **nombre de rangs**, entier de 1 à 99, **nullable** : une parcelle jamais renseignée est « non renseigné », ce qui n'est pas « zéro rang ». Aucun backfill : aucune valeur n'est supposée pour l'existant
- [ ] CA2 : Le nombre se déclare par `/parcelle modifier <nom> rangs=5` ; `rangs=aucun` le remet à « non renseigné ». Une valeur hors bornes ou non entière est refusée et la valeur précédente conservée, avec un message qui rappelle la forme attendue
- [ ] CA3 : Il se déclare aussi en une phrase, par la grammaire déterministe (US-172), sans appel au modèle : « la planche nord a 5 rangs », « la planche centrale fait 4 rangs ». La phrase est confirmée avant d'être appliquée, comme toute commande qui écrit
- [ ] CA4 : L'interpréteur **ne confond pas** la déclaration d'une parcelle avec un geste : « planté 4 salades sur 3 rangs dans la planche nord » reste une plantation de 12 salades et ne modifie pas le nombre de rangs de la planche. Le corpus de commandes (US-172) porte les deux formes côte à côte
- [ ] CA5 : `/parcelle lister` affiche le nombre de rangs de chaque parcelle, ou « rangs non renseignés »
- [ ] CA6 : `GET /plan` expose pour chaque parcelle `nb_rangs`, ainsi que `ordre` et `est_pepiniere` s'il ne les expose pas déjà ; aucun champ existant n'est retiré ni renommé
- [ ] CA7 : Le nombre de rangs n'entre dans **aucun calcul** de stock, d'occupation en surface (`occupation_pct`) ni de confiance : un test le vérifie
- [ ] CA8 : La PWA **n'offre aucun champ** pour le saisir (règle RT1 du plan des épics) ; la Vue plan signalera son absence avec la commande à dire (US-200)
- [ ] CA9 : Le catalogue des commandes (`menu_commandes.FORMES_DICTABLES`) connaît la nouvelle clé et son vocabulaire ; `controler_parite()` reste vert ; `/help` et le corpus restent cohérents (`tools/controler_aide_corpus.py`)
- [ ] CA10 : La fiche `parcelles-et-plan.md` (nouvelle section « Dire combien de rangs compte une planche ») et le guide utilisateur (§ 21.4 Parcelles) sont mis à jour dans la même livraison (US-099 / CA9) ; `docs/domaines/migrations.md` décrit la migration
- [ ] CA11 : Des tests couvrent : déclaration par commande et par phrase, remise à « non renseigné », valeurs refusées, non-confusion avec le multiplicateur d'une plantation, exposition dans `GET /plan`, absence d'effet sur stock, occupation et confiance

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram, enregistrement (parcelle)
- Migration BDD requise : **oui** — `parcelles.nb_rangs` (SMALLINT nullable, contrainte 1 à 99), rollback fourni. Numéro à lire dans `migrations/` au démarrage — dernier constaté : v48
- Dépendances : aucune bloquante. US-172 (grammaire des commandes, livrée)
- Consommateurs : US-198 (répartition en rangs), US-200 (Vue plan), US-217 (où mettre les plants)
- Impact tokens : zéro
- Point de vigilance : une parcelle **pépinière** peut porter un nombre de rangs (pépinière de poireaux en pleine terre, par exemple) ; c'est la Vue plan qui décide de ne pas les dessiner (US-200)
- Point de vigilance : le mot « rang » a désormais deux sens dans l'application — le nombre de rangs **d'une planche** (cette US) et le nombre de rangs **d'un geste** (multiplicateur existant). La fiche d'aide les distingue explicitement

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Déclarer le nombre de rangs par une phrase
  Given la parcelle "planche nord" n'a pas de nombre de rangs
  When le jardinier dicte "la planche nord a 5 rangs"
  Then le bot récapitule "planche nord : 5 rangs" et demande confirmation
  When le jardinier confirme
  Then la parcelle "planche nord" porte 5 rangs
  And aucun jeton n'a été consommé

Scénario: Un geste sur plusieurs rangs ne touche pas la parcelle
  Given la parcelle "planche nord" porte 5 rangs
  When le jardinier dicte "planté 4 salades sur 3 rangs dans la planche nord"
  Then une plantation de 12 salades est proposée
  And la parcelle "planche nord" porte toujours 5 rangs

Scénario: Valeur refusée
  When le jardinier tape "/parcelle modifier planche nord rangs=0"
  Then le bot refuse la valeur et rappelle qu'un nombre de rangs va de 1 à 99
  And la valeur précédente est conservée

Scénario: Revenir à non renseigné
  When le jardinier tape "/parcelle modifier planche nord rangs=aucun"
  Then la parcelle "planche nord" n'a plus de nombre de rangs
```

**Labels GitHub :** `us`, `backend`, `bot`, `migration`, `parcelles`, `plan`

**ID :** US-225
**Titre :** Déclarer la longueur d'une parcelle, base de calcul de tous ses rangs
**Épic :** ÉPIC 10 — Plan : l'occupation en rangs et le zoom d'information *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux dire une fois pour toutes combien mesure une planche dans le sens où je plante
Afin que l'application sache enfin combien de pieds tiennent sur un rang, au lieu de me dessiner des traits dont la longueur ne veut rien dire

**Contexte fonctionnel :**
La maquette haute fidélité du 23/09 (`maquette front/haute-fidelite/Plan - Rangs et places.html`) change la nature du rang : il n'est plus un trait de longueur **relative** (wireframe v3, US-200 / V3), c'est une **piste de places** remplie par les pieds réellement installés. Ce calcul a besoin d'une longueur.

La longueur est une propriété de la **parcelle**, pas du rang : une planche a une longueur unique, et tous ses rangs la partagent. C'est cette longueur qui sert de base à toutes les places de la parcelle. Le paramètre s'appelle donc `longueur_m` — la maquette l'avait provisoirement nommé `longueur_rang_m`, ce qui laissait croire à une longueur par rang.

La **largeur** ne se déclare pas : elle se déduit (`superficie_m2 ÷ longueur_m`) et ne sert qu'à l'affichage, comme un repère de cohérence pour le jardinier. Elle n'est jamais stockée, jamais réinjectée dans un calcul.

Cette US est le jumeau d'US-197 (nombre de rangs, livrée) : même table, même commande, même grammaire, même refus de backfill. Elle ne dessine rien et ne calcule aucune place — c'est US-227 qui calcule, US-228 qui dessine.

⚠️ **Ce n'est pas le plan géométrique de la v2** (orientation des rangs, espacements entre rangs, emprise réelle, échelle), qui reste hors périmètre (plan des épics § 9). Une longueur unique est le strict minimum pour compter des places, rien de plus.

**Critères d'acceptance :**
- [ ] CA1 : Une parcelle porte une **longueur** en mètres, décimale à une décimale, de 0,5 à 200, **nullable** : une parcelle jamais renseignée est « non renseignée », ce qui n'est pas « zéro mètre ». Aucun backfill, aucune longueur déduite de la superficie
- [ ] CA2 : La longueur se déclare par `/parcelle modifier <nom> longueur=12` ; `longueur=aucune` la remet à « non renseignée ». Hors bornes ou non numérique : refus, valeur précédente conservée, message qui rappelle la forme attendue. La commande accepte `12`, `12.5` et `12,5`
- [ ] CA3 : Elle se déclare aussi en une phrase, par la grammaire déterministe (US-172), sans appel au modèle : « la planche centrale fait 12 mètres de long », « planche-centrale a des rangs de 12 m », « la planche nord mesure 8 m ». La phrase est confirmée avant d'être appliquée, comme toute commande qui écrit
- [ ] CA4 : L'interpréteur **ne confond pas** cette déclaration avec un geste de semis en ligne (US-199) : « semé 3 mètres de carottes dans la planche nord » reste un semis de 3 m de rang et ne modifie pas la longueur de la planche. Le corpus de commandes (US-172) porte les deux formes côte à côte, comme il porte déjà la paire d'US-197
- [ ] CA5 : `/parcelle lister` et `/parcelle modifier` sans argument affichent la longueur, ou « longueur non renseignée » ; le récapitulatif de confirmation écrit « planche-centrale : 12 m de long »
- [ ] CA6 : `GET /plan` expose pour chaque parcelle `longueur_m`, et `largeur_m` **déduite** de la superficie quand les deux valeurs existent (`superficie_m2 ÷ longueur_m`, arrondie à 2 décimales). `largeur_m` est explicitement marquée comme déduite dans la réponse ; elle est absente si l'une des deux valeurs manque. Aucun champ existant n'est retiré ni renommé
- [ ] CA7 : **Incohérence non bloquante** : une longueur supérieure à ce que permet la superficie (largeur déduite < 0,2 m) est acceptée et enregistrée — le jardinier peut n'avoir pas déclaré sa superficie —, mais la réponse porte un indicateur `largeur_incoherente` que l'écran utilisera pour le dire, sans jamais corriger la valeur saisie (RT2)
- [ ] CA8 : La longueur n'entre dans **aucun calcul** de stock, d'occupation en surface (`occupation_pct`), de rendement ni de confiance : un test le vérifie
- [ ] CA9 : La PWA **n'offre aucun champ** pour la saisir (RT1) ; c'est la Vue plan qui signale son absence avec la phrase à dire au compagnon (US-228)
- [ ] CA10 : Le catalogue des commandes (`menu_commandes.FORMES_DICTABLES`) connaît la nouvelle clé et son vocabulaire ; `controler_parite()` reste vert ; `/help` et le corpus restent cohérents (`tools/controler_aide_corpus.py`)
- [ ] CA11 : La fiche `parcelles-et-plan.md` (section « Dire combien de rangs compte une planche », étendue à la longueur) et le guide utilisateur (§ 21.4 Parcelles) sont mis à jour dans la même livraison (US-099 / CA9) ; `docs/domaines/migrations.md` décrit la migration ; `docs/domaines/plan-et-rangs.md` (créée par US-198) dit que la longueur est unique par parcelle et pourquoi la largeur n'est jamais stockée
- [ ] CA12 : Des tests couvrent : déclaration par commande et par phrase, décimale avec virgule et avec point, remise à « non renseignée », valeurs refusées, non-confusion avec un semis en mètres de rang, exposition et déduction de largeur dans `GET /plan`, largeur incohérente, absence d'effet sur stock, occupation et confiance

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram, enregistrement (parcelle)
- Migration BDD requise : **oui** — `parcelles.longueur_m` (NUMERIC(5,1) nullable, contrainte 0,5 à 200), rollback fourni. Numéro à lire dans `migrations/` au démarrage — dernier constaté : v48
- Dépendances : aucune bloquante. US-172 (grammaire des commandes, livrée), US-197 (nombre de rangs, livrée — même commande, même fiche d'aide)
- Consommateurs : **US-227** (places d'un rang), **US-228** (piste des places), US-222 (niveau 2), US-217 (où mettre les plants d'un lot)
- Impact tokens : zéro
- Point de vigilance : « longueur de la parcelle » et « longueur d'un rang » désignent **le même nombre**. La fiche d'aide le dit en une phrase, sinon le jardinier cherchera à déclarer les deux
- Point de vigilance : une parcelle **pépinière** peut porter une longueur ; la Vue plan n'en tire simplement aucun rang (US-200 / V8)
- Point de vigilance : la longueur ne dit rien des **allées** ni des bordures. C'est la longueur *utile*, celle où l'on plante — la fiche d'aide le précise, sans quoi le compte de places sera systématiquement optimiste

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Déclarer la longueur par une phrase
  Given la parcelle "planche centrale" n'a pas de longueur
  When le jardinier dicte "la planche centrale fait 12 mètres de long"
  Then le bot récapitule "planche-centrale : 12 m de long" et demande confirmation
  When le jardinier confirme
  Then la parcelle "planche centrale" porte une longueur de 12 m
  And aucun jeton n'a été consommé

Scénario: La largeur se déduit, elle ne se déclare pas
  Given la parcelle "planche centrale" fait 69 m² et 12 m de long
  When je lis le plan
  Then la parcelle porte une longueur de 12 m
  And une largeur déduite de 5,75 m, marquée comme déduite
  And aucune largeur n'est enregistrée en base

Scénario: Un semis en mètres ne touche pas la parcelle
  Given la parcelle "planche nord" fait 8 m de long
  When le jardinier dicte "semé 3 mètres de carottes dans la planche nord"
  Then un semis de 3 m de rang est proposé
  And la parcelle "planche nord" fait toujours 8 m de long

Scénario: Longueur incohérente avec la superficie
  Given la parcelle "petit carré" fait 2 m²
  When le jardinier déclare une longueur de 40 m
  Then la longueur est enregistrée
  And le plan signale une largeur déduite incohérente
  And aucune valeur n'est corrigée automatiquement

Scénario: Revenir à non renseignée
  When le jardinier tape "/parcelle modifier planche nord longueur=aucune"
  Then la parcelle "planche nord" n'a plus de longueur
```

**Labels GitHub :** `us`, `backend`, `bot`, `migration`, `parcelles`, `plan`

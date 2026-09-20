**ID :** US-210
**Titre :** Rattacher les godets à leur pépinière à la mise en godet, et savoir où se trouve chaque lot
**Épic :** ÉPIC 12 — Pépinière : le poste de travail sous abri *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux pouvoir dire où je pose mes godets quand je repique — « repiqué 40 choux en godet sous le châssis froid » — et que l'application sache ensuite dans quelle pépinière se trouve chaque lot
Afin de savoir ce qui occupe ma serre et ce qui occupe mon châssis, et plus seulement combien de godets j'ai en tout

**Contexte fonctionnel :**
L'analyse du 17/07 (`docs/EPIC - PEPINIERE/ANALYSE_pepiniere_multi_emplacements.md`) l'a établi : « Le modèle de données actuel ne supporte pas plusieurs emplacements de pépinière distincts. » Un semis porte sa parcelle, mais une mise en godet est créée « avec `parcelle_id = NULL` codé en dur » (`creer_evenement_godet`) : « Peu importe où sont physiquement les godets (serre, châssis, étagère intérieure...), l'événement n'est jamais rattaché à une parcelle. » Elle proposait trois pistes ; la v2 (§ 3b) reprend la **piste 2** : rendre la parcelle renseignable sur la mise en godet.

C'est souvent au repiquage que les plants changent de lieu : la barquette lève au chaud, les godets partent au froid. Le type de pépinière (US-208) donne tout son sens à ce lieu.

Cette US rend la parcelle **renseignable, jamais devinée**, sur la mise en godet, et ajoute à la lecture par lot son **emplacement courant**. Elle ne change pas la manière dont les stocks sont agrégés : Stocks, Statistiques et le bot gardent leur total par culture et variété — c'est la réponse à la piste 3 de l'analyse (« l'agrégat toutes pépinières confondues reste affiché par défaut ») ; le détail par emplacement est le rôle de la Pépinière (US-219).

**Critères d'acceptance :**

*À la mise en godet*
- [ ] CA1 : Une mise en godet peut porter une **pépinière**, dite dans la phrase (« en godet sous le châssis », « repiqué dans la serre ») ou choisie au récapitulatif. Non dite, elle reste **sans parcelle**, comme aujourd'hui : rien n'est déduit à l'écriture
- [ ] CA2 : Seule une parcelle **pépinière** peut recevoir des godets. Si le jardinier nomme une autre parcelle, le récapitulatif le signale et propose les pépinières du potager ou « sans emplacement » ; une mise en godet n'est jamais enregistrée sur une parcelle ordinaire
- [ ] CA3 : La parcelle d'une mise en godet se corrige depuis le parcours de correction du Journal, comme les autres champs
- [ ] CA4 : Une mise en godet rattachée à une pépinière ne compte **jamais** comme une culture en place : ni sur le Plan, ni dans l'occupation d'une parcelle (test explicite sur `calcul_occupation_parcelles`)

*Emplacement d'un lot*
- [ ] CA5 : `GET /pepiniere/lots` expose pour chaque lot son **emplacement courant** à la date de référence — la pépinière, son nom et son type (US-208) — et d'où vient cette information. Règle, écrite une seule fois : le dernier déplacement (US-211, quand elle est livrée), sinon la dernière mise en godet localisée, sinon la parcelle du semis, sinon « emplacement non renseigné »
- [ ] CA6 : Le lot « godets sans semis rattaché » prend l'emplacement de sa dernière mise en godet localisée, sinon « non renseigné »
- [ ] CA7 : Un lot a **un seul** emplacement : un lot réparti entre deux pépinières se lit à son dernier emplacement dit. Cette limite est écrite dans la fiche d'aide

*Ce qui ne change pas*
- [ ] CA8 : `GET /godets`, `GET /godets/detail`, `GET /stats`, l'écran Stocks, les Statistiques et `/stats` du bot rendent **exactement** les mêmes valeurs avant et après : un test compare les réponses sur un jeu contenant des mises en godet localisées et non localisées
- [ ] CA9 : Aucune reprise de l'existant : les mises en godet déjà enregistrées restent sans parcelle, et leurs lots prennent l'emplacement de leur semis

*Définition de terminé*
- [ ] CA10 : Les fiches `semis-godet-plantation.md` (dire où l'on pose ses godets) et `pepiniere-par-lot.md` (où se trouve un lot, la limite du CA7) sont mises à jour (US-099 / CA9) ; l'analyse du 17/07 est complétée d'une ligne « piste 2 retenue par US-210, agrégation inchangée »
- [ ] CA11 : Des tests couvrent : pépinière dite, non dite, parcelle ordinaire refusée avec proposition, correction au Journal, non-comptage au Plan, règle d'emplacement courant dans chacun de ses cas, lot sans semis rattaché, date de référence antérieure à la mise en godet, non-régression du CA8

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram, enregistrement, analyse (lecture par lot)
- Migration BDD requise : **non** — la colonne `parcelle_id` existe sur l'événement ; seule la valeur forcée à `NULL` disparaît
- Dépendances : US-208 (type de pépinière, pour l'exposer), non bloquante ; US-065 (lecture par lot, livrée)
- Consommateurs : US-211 (déplacement), US-214 (endurcissement), US-219 (Emplacements), US-216 (fiche du lot)
- Impact tokens : zéro sur le chemin déterministe
- Point de vigilance : la règle « le semis prime » de la filière (US-069 : une parcelle pépinière impose le semis en pépinière) n'est pas touchée
- Point de vigilance : un semis en pépinière déclaré **sans** parcelle reste un lot sans emplacement ; il n'est pas rattaché d'office à « la » pépinière même si le potager n'en compte qu'une — pas de supposition

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Godets posés sous le châssis
  Given un lot de chou frisé semé dans la serre
  When le jardinier dicte "repiqué 40 choux frisés en godet sous le châssis froid"
  Then la mise en godet est rattachée au châssis froid
  And le lot a pour emplacement le châssis froid, pépinière froide

Scénario: Pépinière non dite
  Given un lot de poireau semé dans la serre
  When le jardinier dicte "mis 30 poireaux en godet"
  Then la mise en godet n'a pas de parcelle
  And le lot a pour emplacement la serre, lu depuis son semis

Scénario: Parcelle ordinaire refusée
  When le jardinier dicte "repiqué 20 laitues en godet dans la planche nord"
  Then le récapitulatif signale que la planche nord n'est pas une pépinière
  And propose la serre, le châssis froid ou "sans emplacement"

Scénario: Les stocks ne bougent pas
  Given 40 godets de chou frisé sous le châssis et 20 sans emplacement
  When j'ouvre l'écran Stocks
  Then le chou frisé compte 60 plants en pépinière, comme avant
```

**Labels GitHub :** `us`, `backend`, `bot`, `pepiniere`

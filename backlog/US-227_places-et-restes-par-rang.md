**ID :** US-227
**Titre :** Calculer les places d'un rang et ce qu'il en reste
**Épic :** ÉPIC 10 — Plan : l'occupation en rangs et le zoom d'information *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux savoir combien de pieds tiennent encore sur chacun de mes rangs
Afin d'arrêter de planter au jugé, et de voir tout de suite les rangs que j'ai surchargés

**Contexte fonctionnel :**
US-198 (livrée) dit **quels rangs sont occupés, par quoi, en quelle quantité**. Elle ne dit rien de la **capacité** d'un rang, parce que rien ne la permettait : la longueur manquait (US-225) et l'espacement n'était pas exploitable (US-226).

La maquette haute fidélité du 23/09 en fait le cœur de l'écran : un rang n'est plus un trait de longueur relative, c'est une **piste de places**, dont une part est prise et le reste libre. « Reste 12 » se lit d'un coup d'œil ; « +6 en trop » aussi.

Cette US ajoute ce calcul à la répartition, **au même endroit et dans la même lecture** (`app/services/repartition_rangs.py`). Elle ne dessine rien : c'est US-228 qui dessine et US-222 qui reprend le dessin au niveau 2.

⚖️ **Elle étend une US livrée.** US-198 n'est pas réécrite : ses règles R1 à R9 tiennent telles quelles, ses CA restent vrais. Cette US ajoute R10 à R17 et **étend son CA2** (nouveaux champs par rang) et son **CA3** (nouveaux totaux). Aucun champ existant n'est retiré ni renommé.

⚖️ **RT13 tient, et c'est important.** La mesure d'occupation de l'activité Plan reste « N rangs occupés sur M déclarés », par parcelle et en pied de vue. Les places sont une **capacité de rang**, jamais un second taux d'occupation : il n'existe et n'existera nulle part un « potager occupé à 62 % de ses places ». C'est l'arbitrage A25.

**Règles de calcul — elles prolongent R1 à R9 d'US-198 :**

| # | Règle |
|---|---|
| R10 | **Places d'un rang** = `⌊ longueur_m × 100 ÷ espacement_rang_cm ⌋`, au minimum 1. La longueur est celle de la **parcelle** (US-225), partagée par tous ses rangs ; l'espacement est celui de la culture du rang (US-226) |
| R11 | **Places non calculables** : longueur absente, ou espacement absent, ou mode d'implantation « surface ». Le rang porte alors `places = null` — jamais zéro, jamais une estimation. Une parcelle sans longueur n'a **aucun** rang chiffré, quelles que soient ses cultures |
| R12 | **Places prises** : pour les unités qui comptent des individus posés sur le rang — `plants`, `graines`, `poquets` — c'est la **quantité par rang** d'US-198 / R3. Un poquet occupe une place, quel que soit le nombre de graines qu'il contient |
| R13 | **Places restantes** = places − places prises, jamais négatif |
| R14 | **Dépassement de rang** : places prises > places → `depassement_places` porte l'écart, les places restantes valent 0, et **rien n'est corrigé** : la quantité déclarée par le jardinier fait foi. C'est un signalement, pas une contrainte |
| R15 | **Semis en ligne** (unité `ml`, US-199) : pas de places. Le rang porte la **part semée** (`metres_semes ÷ longueur_m`, plafonnée à 1) et les **mètres restants** (`longueur_m − metres_semes`, jamais négatif). Un semis en ligne plus long que le rang porte son propre dépassement, en mètres |
| R16 | **Rang libre** : ses places dépendent de ce qu'on y mettrait, donc elles ne sont pas calculées. Le rang libre porte sa **longueur** et, si la parcelle abrite déjà une culture dont l'espacement est connu, une **capacité d'exemple** nommée (« 24 tomates ») — celle d'une culture réellement présente dans cette parcelle, jamais un espacement par défaut (A26, RT2). Aucune culture connue : la longueur seule |
| R17 | **Totaux** : le bloc de totaux d'US-198 / CA3 gagne le nombre de **parcelles sans longueur**. Il ne gagne **aucun** total de places ni aucun pourcentage de remplissage (RT13, A25) |

**Critères d'acceptance :**
- [x] CA1 : R10 à R17 sont implémentées dans le **module de répartition existant** (`app/services/repartition_rangs.py`), en lecture seule, sans dupliquer la dérivation d'espacement d'US-226 ni le calcul de quantité par rang d'US-198
- [x] CA2 : Chaque rang de la `disposition` de `GET /plan` gagne : `places`, `places_prises`, `places_restantes`, `depassement_places`, `espacement_rang_cm`, et pour un semis en ligne `part_semee` et `metres_restants`. Un rang libre gagne `longueur_m` et, le cas échéant, `capacite_exemple` (nombre **et** nom de la culture de référence). Tous nullables, tous absents plutôt que faux
- [x] CA3 : Chaque parcelle gagne `longueur_m`, `largeur_m` déduite et son indicateur d'incohérence (US-225 / CA6, CA7) ; le bloc de totaux gagne `parcelles_sans_longueur`
- [x] CA4 : **Aucun total de places, aucun pourcentage de remplissage** n'est exposé, ni par rang agrégé, ni par parcelle, ni en pied de vue (RT13). Un test le vérifie sur la forme de la réponse
- [x] CA5 : Tout est calculé **à la date de référence** (US-030), comme le reste de la répartition
- [x] CA6 : **Aucune lecture supplémentaire** : le calcul se greffe sur la lecture unique d'US-198, la dérivation d'espacement comprise. Le surcoût est mesuré avant et après sur la base synthétique d'US-198 / CA5 (12 parcelles, 3 000 événements) et consigné dans cette US à la livraison ; le nombre de requêtes ne dépend toujours pas de la taille du plan
- [x] CA7 : Aucun calcul existant ne change : stock, `occupation_pct`, projections, confiance, et les champs d'US-198. Un test compare les réponses avant et après
- [x] CA8 : **Cohérence avec la Pépinière** : « où mettre les plants d'un lot » (US-217) lit ces mêmes places, jamais un calcul parallèle. Si US-217 n'est pas encore livrée, l'US le note comme dépendance entrante
- [x] CA9 : `docs/domaines/plan-et-rangs.md` gagne la section « Les places d'un rang » : la formule, ses trois cas d'échec, pourquoi une place n'est pas un taux d'occupation, et pourquoi un rang libre n'a pas de places mais une capacité d'exemple. La fiche `parcelles-et-plan.md` l'explique au jardinier (US-099 / CA9)
- [x] CA10 : Des tests couvrent : places d'un rang en plants, en graines, en poquets ; longueur absente ; espacement absent ; mode surface ; dépassement ; semis en ligne partiel, complet et débordant ; rang libre avec et sans culture de référence ; totaux sans places ; date de référence passée ; parcelle pépinière (aucune place, aucun rang de semis)

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse (lecture), consultation
- Migration BDD requise : **non**
- Dépendances : **US-225** (longueur de la parcelle) et **US-226** (espacement sur le rang) — bloquantes ; US-198 (répartition, livrée) ; US-199 (unité `ml` et `poquets`) pour que R12 et R15 aient de la matière, non bloquante
- Consommateurs : **US-228** (piste des places), US-222 (niveau 2), US-217 (où mettre les plants d'un lot), US-215 (« Prêts pour le plan »)
- Impact tokens : zéro
- Point de vigilance : **une place n'est pas une promesse.** Un rang de 12 m à 50 cm donne 24 places de tomates ; personne ne plante 24 tomates sur un rang de potager domestique. La formule dit ce que la géométrie permet, pas ce qu'il est raisonnable de faire — la fiche d'aide le dit clairement, sinon le chiffre sera lu comme un conseil
- Point de vigilance : les **graines** comptées en places sont le cas le plus discutable (un semis en ligne dense de carottes n'a pas 24 « places »). C'est pourquoi le semis en ligne a son unité propre (`ml`, R15) : R12 ne s'applique aux graines que faute de mieux, et l'US-199 est ce qui rend ce cas rare
- Point de vigilance : le dépassement de rang (R14) et le dépassement de parcelle (US-198 / R7) sont **deux choses différentes** — trop de pieds sur un rang, ou trop de rangs occupés pour la parcelle. L'écran ne doit pas les confondre dans une même alerte

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Places d'un rang de tomates
  Given la planche centrale fait 12 m de long
  And la tomate a un espacement sur le rang de 50 cm
  And 9 tomates sont en place sur son rang 1
  When je lis le plan
  Then le rang 1 porte 24 places, 9 prises et 15 restantes

Scénario: Rang surchargé
  Given la planche ombre fait 9 m de long
  And la tomate cœur de bœuf a un espacement sur le rang de 40 cm
  And 26 pieds sont en place sur son rang
  When je lis le plan
  Then le rang porte 22 places, 22 prises, 0 restante
  And un dépassement de 4 places
  And la quantité déclarée reste 26

Scénario: Parcelle sans longueur
  Given la planche est n'a pas de longueur
  And 3 courgettes y sont plantées
  When je lis le plan
  Then le rang des courgettes n'a aucune place calculée
  And le total du plan compte une parcelle sans longueur

Scénario: Culture sans espacement
  Given la planche centrale fait 12 m de long
  And la laitue n'a pas d'espacement dans le référentiel
  When je lis le plan
  Then le rang de laitues n'a aucune place calculée
  And aucun espacement moyen n'est utilisé

Scénario: Semis en ligne
  Given la planche ombre fait 9 m de long
  And 3 m de carottes y sont semés
  When je lis le plan
  Then le rang porte une part semée d'un tiers et 6 m restants
  And aucune place n'est comptée

Scénario: Rang libre
  Given la planche centrale fait 12 m de long et porte des tomates espacées de 50 cm
  And son rang 5 est libre
  When je lis le plan
  Then le rang 5 porte sa longueur de 12 m
  And une capacité d'exemple de 24 tomates, nommée
  And aucune place prise ni restante
```

**Livraison (23/09/2026, v3.78.0) :**
- CA6 — coût mesuré : `test_us227_ca6_aucune_lecture_supplementaire` compte les requêtes de `repartition_du_plan` avec et sans l'index d'espacements. Le compte est **identique** (une agrégation des rangs d'installation, plus la lecture des lots si le potager a une pépinière), et reste identique après avoir triplé le nombre de lignes du plan. L'index de fiches culture vient de `attributs_par_culture()`, la lecture que `GET /plan` faisait déjà pour la surface au sol : **zéro requête ajoutée**
- CA8 — **dépendance entrante** : US-217 (« où mettre les plants d'un lot ») n'est pas livrée. Quand elle le sera, elle lira `disposition.rangs[].places_restantes` de `GET /plan`, jamais un calcul parallèle
- Précision apportée à R12/R14 par le Gherkin « Rang surchargé » : `places_prises` est **plafonné** aux places du rang (22, pas 26) et l'excédent part dans `depassement_places` — `places_prises + depassement_places` redonne toujours la quantité déclarée, qui reste intacte dans `quantite_par_rang`
- Règle ajoutée en cours d'implémentation : une **parcelle pépinière** n'a pas de places (on n'y plante pas au cordeau), conformément au cas « parcelle pépinière » exigé par CA10
- US-199 n'étant pas livrée, R15 s'appuie sur l'unité `ml` telle qu'elle sera normalisée : le code la reconnaît déjà, aucune ligne du parc n'en porte encore

**Labels GitHub :** `us`, `backend`, `plan`, `parcelles`

---

## ⚠️ AMENDEMENT du 24/09/2026 — la fiche parcelle ne porte plus le détail des cultures

Origine : maquette `Parcelle - Fiche.html`, détaillée dans l'amendement de
**US-222**, qui fait foi. La fiche d'une parcelle porte désormais un simple
**bandeau d'occupation** (« N rangs occupés sur M », les noms des cultures) et
un bouton « Voir les cultures dans le Plan → » : plus aucune tuile de culture,
plus aucun rang libre actionnable.

- Le calcul des places est **inchangé** : il ne dessinait rien, et rien de ce
  qu'il produit ne disparaît.
- Sa liste de consommateurs perd **US-222** : le niveau 2 ne reprend plus le
  dessin des rangs. Restent US-228 (la piste, dans la Vue plan), US-217 et
  US-215.

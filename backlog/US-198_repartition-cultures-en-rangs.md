**ID :** US-198
**Titre :** Répartir les cultures en place sur les rangs de leur parcelle — lecture serveur de la Vue plan
**Épic :** ÉPIC 10 — Plan : l'occupation en rangs et le zoom d'information *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux que l'application sache, pour chaque planche, quels rangs sont occupés, par quoi, dans quelle quantité, et combien restent libres
Afin que le Plan, et plus tard la Pépinière quand elle me propose où planter, me disent la même chose de la place qui reste

**Contexte fonctionnel :**
Le wireframe v3 fixe les « huit données du Plan » : parcelle, superficie, nombre de rangs, culture du rang, quantité, unité, mode d'implantation, phase. Il fixe aussi le principe : « Une parcelle affiche ses rangs, un rang par culture. […] Aucun plant n'est dessiné, aucune surface réelle n'est calculée. »

Trois de ces huit données n'existent pas telles quelles :
- le **nombre de rangs** de la parcelle : ajouté par US-197 ;
- la **phase** : calculée par US-194 ;
- le **mode d'implantation** : n'existe nulle part. La v3 propose sa déduction : « Défaut retenu : RANG, sauf si l'unité de quantité est le m² (→ SURFACE) ou le poquet (→ POQUET). L'unité suffit donc à décider dans la quasi-totalité des cas » (arbitrage A4).

Et une quatrième est un faux ami : le **rang d'un événement** n'est pas une position mais un multiplicateur (« planté 4 salades sur 3 rangs » enregistre 12 plants). La base ne sait donc pas qu'une tomate est « au rang 1 ». Cette US numérote les rangs **dans l'ordre d'installation** des cultures et le dit (arbitrage A5) ; la position réelle devient possible avec US-203, optionnelle.

Cette US calcule la répartition **côté serveur, à un seul endroit**, et l'ajoute à `GET /plan`. Elle ne dessine rien (US-200). Elle sert aussi la Pépinière (« où mettre les plants », US-217) : les deux écrans ne peuvent pas compter différemment la place libre.

⚖️ **Étendue par US-227 (maquette gelée du 23/09).** Cette US dit quels rangs sont occupés ; elle ne dit rien de la **capacité** d'un rang. La maquette haute fidélité `Plan - Rangs et places.html` demande en plus, par rang, ses **places**, ses places prises et ses places restantes. Ce calcul est ajouté au même module par **US-227** (règles R10 à R17), qui **étend les CA2 et CA3** ci-dessous sans en retirer ni renommer un seul champ. Les règles R1 à R9 tiennent telles quelles.

**Règles de répartition :**

| # | Règle |
|---|---|
| R1 | Une **ligne** est une culture × variété en place dans la parcelle, exactement comme le plan d'occupation la compte aujourd'hui : même regroupement, même quantité, même unité (`calcul_occupation_parcelles`). Aucune ligne ajoutée, aucune retirée |
| R2 | Une ligne occupe **un rang**, ou le nombre de rangs dit à son installation (le multiplicateur « sur N rangs »). Si elle vient de plusieurs installations encore ouvertes, c'est la **somme** de leurs rangs |
| R3 | Chaque rang d'une ligne porte la **quantité par rang** : quantité ÷ rangs, arrondie à l'unité pour ce qui se compte (plants, graines, poquets), au dixième pour les m², jamais zéro quand la quantité ne l'est pas |
| R4 | **Mode d'implantation** déduit de l'unité : `m2` → surface ; `poquets` → poquet (US-199) ; toute autre unité → rang. Écrit une seule fois |
| R5 | **Numérotation** : les lignes sont rangées de la plus anciennement installée à la plus récente (à égalité, par nom de culture), et leurs rangs numérotés à partir de 1 dans cet ordre. Les rangs libres suivent, jusqu'au nombre déclaré |
| R6 | **Rangs libres** = nombre déclaré − rangs occupés, jamais négatif. Sans nombre déclaré : « inconnu », jamais zéro |
| R7 | **Dépassement** : plus de rangs occupés que de rangs déclarés → toutes les lignes restent, et la parcelle porte l'écart. Aucune culture n'est jamais masquée |
| R8 | **Parcelle pépinière** : ses semis ne sont pas des lignes (exclusion inchangée) ; elle porte le **nombre de lots en cours** qu'elle abrite. Une plantation faite dans une parcelle pépinière reste une ligne comme ailleurs |
| R9 | Les cultures **non localisées** forment un bloc à part, sans rang ni numérotation |

**Critères d'acceptance :**
- [x] CA1 : Les règles R1 à R9 sont implémentées **dans un seul module de service**, en lecture seule, qui réutilise l'occupation, les séries (US-070) et la phase (US-194) existantes sans les recalculer
- [x] CA2 : `GET /plan` ajoute à chaque culture d'une parcelle : `mode_implantation`, `rangs`, `quantite_par_rang`, `date_installation`, `numeros_rangs` ; et à chaque parcelle une `disposition` : rangs déclarés, rangs occupés, rangs libres (ou inconnu), dépassement, liste ordonnée des rangs (numéro, ligne ou libre), mode de numérotation (`ordre_installation`, puis `positions` ou `mixte` avec US-203), nombre de lots en cours pour une pépinière. Aucun champ existant n'est retiré ni renommé ; l'onglet Parcelles est inchangé
- [x] CA3 : `GET /plan` ajoute un bloc de **totaux** : superficie totale déclarée ; rangs déclarés et occupés sur les seules parcelles non pépinières qui ont un nombre de rangs (le pourcentage ne mêle jamais une parcelle sans dénominateur) ; nombre de parcelles sans nombre de rangs ; liste des rangs libres par parcelle, dans l'ordre des parcelles
- [x] CA4 : Tout est calculé **à la date de référence** (US-030) : une installation postérieure n'occupe pas encore de rang
- [x] CA5 : Une seule lecture : `GET /plan` ne fait pas une requête par parcelle ni par ligne ; son temps de réponse est mesuré avant et après sur une base de taille réelle et consigné dans l'US à la livraison
- [x] CA6 : Aucun calcul existant ne change : stock, `occupation_pct`, projections, confiance. Un test compare les réponses de `GET /stats`, `GET /godets` et les champs historiques de `GET /plan` avant et après
- [x] CA7 : Une fiche de domaine `docs/domaines/plan-et-rangs.md` consigne les règles R1 à R9 et les deux sens du mot « rang » ; elle entre dans la table de `docs/domaines/README.md` dans le même commit
- [x] CA8 : La fiche `parcelles-et-plan.md` dit comment le Plan compte les rangs, pourquoi ils sont numérotés dans l'ordre d'installation, et ses deux limites assumées : des semis échelonnés d'une même variété forment une seule ligne, et une récolte partielle ne libère pas de rang tant que la ligne reste en place (US-099 / CA9)
- [x] CA9 : Des tests couvrent : une ligne sur un rang, une plantation « sur 3 rangs », deux installations de la même ligne, quantité par rang en plants et en m², déduction du mode pour chaque unité, numérotation et rangs libres, parcelle sans nombre de rangs, dépassement, parcelle pépinière avec lots et avec une plantation, non localisé, date de référence passée

## Complément demandé le 23/09/2026 : compléter les rangs avant d'en ouvrir

**Statut : implémenté dans le périmètre validé, validation ciblée réussie.**
La validation globale du dépôt n'est pas verte (voir bilan ci-dessous).
Les points d'affinage non validés restent hors de cette implémentation.

Ce comportement appartient à **US-198**, car il change le nombre de rangs
occupés et la quantité affectée à chacun. Il dépend des capacités calculées par
**US-227** ; **US-228** ne fait qu'afficher la répartition et son éventuel
dépassement. Pour les plantations éligibles, il remplace R2 (un seul rang par
défaut) et R3 (division uniforme), pas la quantité déclarée. Les garanties
historiques d'US-227 sur l'absence de modification des champs d'US-198 devront
être adaptées à ce nouveau périmètre lors de sa livraison.

### Critères d'acceptance supplémentaires

- [x] CA10 — **Déclenchement** : pour une plantation sans nombre de rangs explicitement indiqué, utiliser les places restantes des rangs de même culture normalisée, même variété et même unité avant d'occuper un rang libre. Ne pas fusionner deux variétés ni assimiler une variété non précisée à une variété connue sans résolution préalable. La règle s'applique aussi à la première plantation d'une culture : sans rang compatible existant, commencer par les rangs libres. Une capacité nulle en places restantes est différente d'une capacité inconnue. Si les caractéristiques nécessaires sont insuffisantes (longueur, espacement ou nombre total de rangs), conserver les règles actuelles, sans inventer de capacité ni de rang libre. Périmètre livré : plantations en plants ou pieds ; autres unités inchangées en attendant arbitrage.
- [x] CA11 — **Compléter l'existant** : affecter au maximum les places disponibles sur chaque rang compatible, dans l'ordre croissant des numéros de rangs. Si la quantité ajoutée tient entièrement dans ces places, aucun rang libre n'est occupé. Un remplissage exactement à capacité n'ouvre pas de rang supplémentaire et ne déclenche pas de dépassement. Ne pas redistribuer uniformément les quantités entre les rangs.
- [x] CA12 — **Répartir tout le résiduel** : après saturation des rangs compatibles, ou dès la première plantation si aucun n'existe, affecter le résiduel aux rangs libres dans l'ordre croissant de leurs numéros, avec la capacité de la culture plantée, jamais avec la capacité d'exemple d'une autre culture. Répéter sur autant de rangs libres que nécessaire et disponibles ; le dernier peut être partiellement rempli. Les rangs occupés par d'autres cultures ne sont ni déplacés ni utilisés. Le cas d'une première plantation sans aucun rang libre relève de CA19.
- [x] CA13 — **Débordement en dernier recours** : lorsqu'il ne reste plus de rang libre et qu'un rang compatible existe, ajouter tout le résiduel au dernier rang de cette culture dans l'ordre d'affectation, y compris s'il vient d'être ouvert. Ce rang affiche le dépassement en unités, ses places restantes valent zéro. Aucun rang fictif supplémentaire n'est créé par cette affectation ; la quantité n'est ni écrêtée ni rejetée. L'exception sans aucun rang compatible est définie en CA19.
- [x] CA14 — **Conservation et priorité à la déclaration** : la somme des quantités affectées est exactement égale à la quantité déjà en place plus la plantation ajoutée. Une déclaration explicite « sur N rangs » conserve sa sémantique actuelle, notamment son multiplicateur, et ne déclenche pas cette affectation automatique. Le stock n'est décompté qu'une fois pour la quantité réellement enregistrée ; répartir n'est pas enregistrer plusieurs fois le geste.
- [x] CA15 — **Une vérité serveur** : la répartition, les quantités propres à chaque rang, leurs places restantes et leurs dépassements sont cohérents dans `GET /plan` et chez tous ses consommateurs. Les compteurs de rangs et totaux sont mis à jour ; aucun calcul concurrent n'est ajouté dans le frontend. Le contrat doit permettre des quantités différentes par rang : un unique `quantite_par_rang` moyen ne suffit pas. Les lectures répétées ne cumulent pas l'affectation.
- [x] CA16 — **Validation et documentation** : couvrir les exemples ci-dessous, les décisions d'affinage validées, les déclarations explicites et la conservation des quantités par des tests serveur puis d'affichage. Mettre à jour `docs/domaines/plan-et-rangs.md` et `data/connaissance/doc_app/parcelles-et-plan.md` dans la livraison fonctionnelle ; garder `tests/test_us099_corpus_fonctionnement.py` vert.
- [x] CA17 — **Plantations déjà enregistrées** : appliquer aussi la nouvelle répartition aux plantations existantes sans nombre de rangs explicitement déclaré. À la livraison, 16 salades auparavant affichées sur R1 avec une capacité de 13 et R2 libre sont affichées en 13 sur R1 et 3 sur R2. Le recalcul ne modifie ni les gestes ni leurs quantités dans le journal, et ne rejoue aucun mouvement de stock. Les rangs explicitement déclarés restent respectés.
- [x] CA18 — **Recalcul après correction des caractéristiques** : une correction de longueur ou d'espacement entraîne le recalcul de la répartition déduite, des places et des dépassements, sans figer l'affectation obtenue à la confirmation. Par exemple, pour 16 plants sans rang explicitement déclaré et au moins deux rangs disponibles, passer d'une capacité de 13 à 10 donne 10 plants sur le premier rang et 6 sur le second, sans modifier le total enregistré. Si les caractéristiques deviennent insuffisantes, appliquer le repli de CA10.
- [x] CA19 — **Nouvelle culture dans une parcelle pleine** : si aucun rang compatible ni aucun rang libre n'existe, conserver le comportement actuel R7 : afficher la nouvelle culture sur un rang supplémentaire portant toute sa quantité et signaler le dépassement du nombre de rangs de la parcelle. Ne pas la mélanger aux autres cultures ni masquer la plantation. Si sa quantité dépasse aussi la capacité de ce rang, afficher également ce dépassement en unités, distinct du dépassement de la parcelle.

### Exemples d'acceptance

Pour une même culture compatible, capacité de **13 plants par rang** (4 m,
espacement 30 cm), avec initialement **4 plants sur R1**, sans nombre de rangs
dans la nouvelle plantation. Chaque exemple est indépendant.

| Ajout | Rangs libres avant ajout | Répartition attendue après ajout | Dépassement |
|---|---|---|---|
| 5 plants | R2 à R5 | R1 : 9 ; R2 à R5 restent libres | Aucun |
| 9 plants | R2 à R5 | R1 : 13 ; R2 à R5 restent libres | Aucun |
| 12 plants | R2 à R5 | R1 : 13 ; R2 : 3 ; R3 à R5 restent libres | Aucun, au lieu de 16 sur R1 et « 3 en trop » |
| 30 plants | R2 à R5 | R1 : 13 ; R2 : 13 ; R3 : 8 ; R4 et R5 restent libres | Aucun |
| 12 plants | Aucun | R1 : 16 | 3 sur R1 |
| 30 plants | R2 seulement | R1 : 13 ; R2 : 21 | 8 sur R2 |

Autre cas : R1 porte 10 plants, R2 en porte 8, tous deux de la même culture
compatible. Un ajout de 7 donne R1 : 13 et R2 : 12, sans ouvrir de nouveau
rang, dans l'ordre croissant validé.

Première plantation : aucun plant de cette culture n'est encore présent et
R1 à R5 sont libres. Avec la même capacité de 13 plants par rang, planter
30 plants sans préciser de rang donne R1 : 13, R2 : 13, R3 : 4 ; R4 et R5
restent libres, sans dépassement.

### Décisions validées le 23/09/2026

| Point | Décision |
|---|---|
| Identité compatible | Même culture normalisée, même variété et même unité. |
| Ordre d'affectation | Ordre croissant des rangs compatibles, puis ordre croissant des rangs libres. |
| Caractéristiques insuffisantes | Conserver les règles actuelles si les données nécessaires au calcul manquent. |
| Première plantation | Appliquer également la répartition automatique dès la première plantation de la culture. |
| Plantations déjà enregistrées | Recalculer aussi leur répartition lorsqu'aucun nombre de rangs n'a été explicitement déclaré, sans modifier les gestes ni leurs quantités (CA17). |
| Correction de longueur ou d'espacement | Recalculer la répartition déduite, sans la figer à la confirmation (CA18). |
| Première plantation sans rang libre | Afficher la nouvelle culture sur un rang supplémentaire et signaler le dépassement de la parcelle, sans mélange avec les autres cultures (CA19). |

### Décisions à valider avant développement

La demande fixe le remplissage puis le débordement, mais pas encore ces cas.
Les propositions ci-dessous ne sont pas des décisions acquises.

| Point ouvert | Proposition d'affinage |
|---|---|
| Unités et gestes concernés | Limiter ce complément aux plantations en plants et à capacité calculable. Les semis, graines, poquets, mètres linéaires, m², pépinières et cultures non localisées gardent leurs règles actuelles, sauf extension explicite. |
| Autres changements et dates passées | Préciser le traitement des corrections/suppressions de gestes, des récoltes et des dates de référence passées, notamment les caractéristiques à utiliser pour une consultation passée après correction de longueur ou d'espacement. Le recalcul après correction de ces caractéristiques est acquis (CA18), mais ne tranche pas ces autres cas. |
| Confirmation du geste | Proposer la répartition dans le récapitulatif avant confirmation. Si elle est enregistrée, revérifier les disponibilités à la validation et traiter deux plantations concurrentes sans double consommation des mêmes places. |

### Bilan d'implémentation du complément

- Le serveur reconstruit les affectations en lecture depuis les installations
  ordonnées, en conservant une seule requête pour les installations. Aucune
  migration, écriture de geste ni modification de stock.
- `disposition.rangs[].quantite_par_rang` porte la quantité réelle et devient
  la source d'affichage ; la moyenne historique de ligne reste disponible.
- Les tests couvrent les exemples chiffrés, les gestes explicites puis implicites,
  les rangs non consécutifs, les variétés et unités distinctes, les données
  manquantes, la date passée, le recalcul de capacité et l'isolation par potager.
- Repli conservatoire pour les lignes dont la quantité nette diffère de la
  somme des installations (récoltes, pertes) : règle antérieure R2/R3, en attente
  de l'arbitrage ci-dessus. Les dimensions utilisées pour une date passée sont
  les valeurs courantes, comme auparavant. Récapitulatif de confirmation inchangé.
- Build frontend réussi ; 68 tests JavaScript de la vue Plan et 47 tests du
  corpus fonctionnel passent. Rendu DOM du cas 13 puis 3 contrôlé à 375, 768
  et 1440 px, sans débordement horizontal. Capture visuelle non validée : page
  partagée masquée et profil Chrome DevTools déjà utilisé.
- Suite Python complète : 3 861 réussites, 38 échecs, 15 erreurs, 4 ignorés.
  Les échecs concernent notamment des fixtures SQLite inter-threads, des mocks
  asynchrones et le corpus agronomique. L'échec voisin US-024 CA5 attend un
  pourcentage de surface malgré l'absence d'attributs de surface dans son mock ;
  ce calcul n'est pas modifié par le complément. Pas de correction hors périmètre.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse (lecture), consultation
- Migration BDD requise : **non**
- Dépendances : **US-194** (phase), **US-197** (nombre de rangs) — bloquantes ; US-199 (unité poquet) pour que le mode poquet apparaisse, non bloquante ; US-070 (séries, livrée)
- Consommateurs : US-200 (Vue plan), **US-227** (places d'un rang — étend ce module), US-222 (détail de parcelle, même répartition), US-217 (où mettre les plants d'un lot), US-215 (« Prêts pour le plan »)
- Impact tokens : zéro
- Point de vigilance : la **longueur** d'un trait n'est pas calculée ici. C'est de la mise en forme (quantité par rang comparée au rang le plus fourni de la même unité), portée par la lib de la Vue plan (US-200). ⚖️ *Avec US-227, ce trait relatif devient le mode dégradé : le remplissage normal vient des places, calculées côté serveur — la frontière ne bouge donc pas, elle se déplace du bon côté*
- Point de vigilance : la répartition ne dit rien de la **longueur de la parcelle** non plus, parce qu'elle n'existe pas encore (US-225). Tant qu'elle manque, aucune capacité de rang n'est calculable
- Point de vigilance : la répartition ne dit **rien de la surface**. « 1 rang libre » n'est pas « 1,2 m² libre » : la géométrie de la v2 est reportée (plan des épics § 9)
- Point de vigilance : **reproducteur vs végétatif**. Un rang de haricots reste occupé tant que les pieds restent, récolte après récolte ; un rang de laitues se libère quand la ligne quitte le plan d'occupation, c'est-à-dire quand il ne reste plus de pieds

**Mesure de CA5 à la livraison :**

Base synthétique (aucune base de production accessible depuis le poste de
développement) : 12 parcelles, 3 000 événements, 1 321 lignes d'occupation,
SQLite en mémoire, moyenne sur 10 appels.

| | Temps |
|---|---|
| Occupation seule (avant) | 175,6 ms |
| Occupation + répartition (après) | 193,4 ms |
| Surcoût de la répartition | **+17,8 ms**, soit ~10 % |

Le surcoût est une requête d'agrégation unique, plus une lecture des lots de
pépinière quand le potager en compte une. Il ne croît ni avec le nombre de
parcelles ni avec le nombre de lignes, ce que tient
`test_us198_ca5_le_nombre_de_lectures_ne_depend_pas_de_la_taille_du_plan`.

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Deux lignes, rangs libres
  Given la planche centrale porte 5 rangs
  And 8 tomates noire de Crimée plantées le 1er juin
  And "planté 6 poireaux sur 2 rangs" enregistré le 10 juin, soit 12 plants
  When je lis le plan
  Then le rang 1 porte la tomate, 8 plants
  And les rangs 2 et 3 portent les poireaux, 6 plants chacun
  And les rangs 4 et 5 sont libres
  And la planche centrale compte 3 rangs occupés sur 5

Scénario: Semis en surface
  Given 2 m² de carottes semés en place dans la planche centrale
  When je lis le plan
  Then la ligne carotte est en mode "surface" avec 2 m² sur son rang

Scénario: Parcelle sans nombre de rangs
  Given la planche est n'a pas de nombre de rangs
  And 3 courgettes y sont plantées
  When je lis le plan
  Then la ligne courgette occupe le rang 1
  And les rangs libres de la planche est sont "inconnus"
  And la planche est n'entre pas dans le pourcentage d'occupation

Scénario: Plus de cultures que de rangs
  Given la butte porte 1 rang
  And des radis et des laitues y sont semés
  When je lis le plan
  Then les deux lignes sont présentes
  And la butte porte un dépassement de 1 rang

Scénario: Pépinière
  Given la serre est déclarée pépinière et abrite 3 lots en cours
  When je lis le plan
  Then la serre ne porte aucune ligne de semis
  And elle indique 3 lots en cours
```

**Labels GitHub :** `us`, `backend`, `plan`, `parcelles`

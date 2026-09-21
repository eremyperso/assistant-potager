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
- [ ] CA1 : Les règles R1 à R9 sont implémentées **dans un seul module de service**, en lecture seule, qui réutilise l'occupation, les séries (US-070) et la phase (US-194) existantes sans les recalculer
- [ ] CA2 : `GET /plan` ajoute à chaque culture d'une parcelle : `mode_implantation`, `rangs`, `quantite_par_rang`, `date_installation`, `numeros_rangs` ; et à chaque parcelle une `disposition` : rangs déclarés, rangs occupés, rangs libres (ou inconnu), dépassement, liste ordonnée des rangs (numéro, ligne ou libre), mode de numérotation (`ordre_installation`, puis `positions` ou `mixte` avec US-203), nombre de lots en cours pour une pépinière. Aucun champ existant n'est retiré ni renommé ; l'onglet Parcelles est inchangé
- [ ] CA3 : `GET /plan` ajoute un bloc de **totaux** : superficie totale déclarée ; rangs déclarés et occupés sur les seules parcelles non pépinières qui ont un nombre de rangs (le pourcentage ne mêle jamais une parcelle sans dénominateur) ; nombre de parcelles sans nombre de rangs ; liste des rangs libres par parcelle, dans l'ordre des parcelles
- [ ] CA4 : Tout est calculé **à la date de référence** (US-030) : une installation postérieure n'occupe pas encore de rang
- [ ] CA5 : Une seule lecture : `GET /plan` ne fait pas une requête par parcelle ni par ligne ; son temps de réponse est mesuré avant et après sur une base de taille réelle et consigné dans l'US à la livraison
- [ ] CA6 : Aucun calcul existant ne change : stock, `occupation_pct`, projections, confiance. Un test compare les réponses de `GET /stats`, `GET /godets` et les champs historiques de `GET /plan` avant et après
- [ ] CA7 : Une fiche de domaine `docs/domaines/plan-et-rangs.md` consigne les règles R1 à R9 et les deux sens du mot « rang » ; elle entre dans la table de `docs/domaines/README.md` dans le même commit
- [ ] CA8 : La fiche `parcelles-et-plan.md` dit comment le Plan compte les rangs, pourquoi ils sont numérotés dans l'ordre d'installation, et ses deux limites assumées : des semis échelonnés d'une même variété forment une seule ligne, et une récolte partielle ne libère pas de rang tant que la ligne reste en place (US-099 / CA9)
- [ ] CA9 : Des tests couvrent : une ligne sur un rang, une plantation « sur 3 rangs », deux installations de la même ligne, quantité par rang en plants et en m², déduction du mode pour chaque unité, numérotation et rangs libres, parcelle sans nombre de rangs, dépassement, parcelle pépinière avec lots et avec une plantation, non localisé, date de référence passée

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse (lecture), consultation
- Migration BDD requise : **non**
- Dépendances : **US-194** (phase), **US-197** (nombre de rangs) — bloquantes ; US-199 (unité poquet) pour que le mode poquet apparaisse, non bloquante ; US-070 (séries, livrée)
- Consommateurs : US-200 (Vue plan), US-222 (détail de parcelle, même répartition), US-217 (où mettre les plants d'un lot), US-215 (« Prêts pour le plan »)
- Impact tokens : zéro
- Point de vigilance : la **longueur** d'un trait n'est pas calculée ici. C'est de la mise en forme (quantité par rang comparée au rang le plus fourni de la même unité), portée par la lib de la Vue plan (US-200)
- Point de vigilance : la répartition ne dit **rien de la surface**. « 1 rang libre » n'est pas « 1,2 m² libre » : la géométrie de la v2 est reportée (plan des épics § 9)
- Point de vigilance : **reproducteur vs végétatif**. Un rang de haricots reste occupé tant que les pieds restent, récolte après récolte ; un rang de laitues se libère quand la ligne quitte le plan d'occupation, c'est-à-dire quand il ne reste plus de pieds

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

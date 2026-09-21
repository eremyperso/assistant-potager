**ID :** US-203
**Titre :** Préciser à la saisie le rang où l'on sème ou plante *(optionnelle)*
**Épic :** ÉPIC 10 — Plan : l'occupation en rangs et le zoom d'information *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux pouvoir dire « planté 8 tomates au rang 3 de la planche centrale »
Afin que le « rang 3 » du Plan soit le troisième rang de ma planche, et non le troisième dans l'ordre où j'ai installé mes cultures

**Contexte fonctionnel :**
En V1, la Vue plan numérote les rangs **dans l'ordre d'installation** et le dit (arbitrage A5, US-198 / R5), parce que la base ne connaît pas la position d'une culture : le seul « rang » d'un événement est un multiplicateur (« 4 salades sur 3 rangs » = 12 plants). Tant que le jardinier lit ses rangs dans ce sens, le Plan est juste. Dès qu'il veut retrouver sur le terrain « le rang 3 », il ne l'est plus.

Les wireframes supposent cette position à plusieurs endroits : « Mettre en terre » depuis la pépinière « saisit l'événement de plantation avec parcelle **et rang** pré-remplis » (v1), « rangs 4–5 de planche-ombre » dans « Où les mettre » (v1, v2).

Cette US ajoute une **position de rang** facultative aux gestes d'installation (semis en pleine terre, plantation), sans toucher au multiplicateur : « planté 6 poireaux sur 2 rangs à partir du rang 4 » dit à la fois le nombre de rangs (2, multiplicateur existant, 12 plants) et leur place (rangs 4 et 5).

⚖️ **US optionnelle** : la V1 fonctionne sans elle. À déclencher si les jardiniers veulent que la numérotation du Plan corresponde au terrain.

**Critères d'acceptance :**

*Saisie*
- [ ] CA1 : Un semis en pleine terre ou une plantation peut porter une **position de premier rang** (entier ≥ 1), facultative ; le nombre de rangs du geste reste le multiplicateur existant. Une culture sur N rangs à partir du rang P occupe les rangs P à P + N − 1
- [ ] CA2 : La position se dicte, reconnue par le parseur déterministe sans appel au modèle : « au rang 3 », « rang 3 », « dans le rang 3 », « à partir du rang 4 », « rangs 4 et 5 » (qui vaut « sur 2 rangs à partir du rang 4 »)
- [ ] CA3 : Le parseur **ne confond pas** position et multiplicateur : « sur 3 rangs » reste un multiplicateur sans position ; « au rang 3 » est une position sur un seul rang. Le corpus de dictée porte ces phrases côte à côte, et un test vérifie qu'aucune phrase existante du corpus ne change d'interprétation
- [ ] CA4 : La position est validée à l'écriture contre le nombre de rangs de la parcelle (US-197) quand il est connu : un rang au-delà est signalé au récapitulatif (« la planche nord n'a que 5 rangs ») et le jardinier corrige ou confirme sans position. Sans nombre de rangs connu, la position est acceptée telle quelle
- [ ] CA5 : Un geste préparé dans la PWA (US-196) transporte la position d'un rang libre de la Vue plan (US-201 / I3) ou d'une suggestion « Où les mettre » (US-217)
- [ ] CA6 : La position se corrige et se supprime depuis le parcours de correction du Journal, comme les autres champs d'un geste

*Lecture*
- [ ] CA7 : La répartition d'US-198 place d'abord les lignes dont la position est connue, sur leurs rangs ; les autres occupent les rangs restants dans l'ordre d'installation ; les rangs encore vides sont libres. Le mode de numérotation exposé devient `positions` ou `mixte`
- [ ] CA8 : Deux lignes qui revendiquent le même rang sont **toutes deux affichées** : la plus récente prend le rang libre suivant et porte la mention « position en conflit avec … » ; aucune culture n'est masquée
- [ ] CA9 : Sur la Vue plan, un numéro de rang issu d'une position dite s'affiche normalement ; en numérotation mixte, les rangs placés par ordre d'installation se distinguent (libellé en italique, nom accessible « rang dont la position n'a pas été précisée »)

*Définition de terminé*
- [ ] CA10 : Aucun calcul de stock ne change : la position n'est **jamais** un multiplicateur ; un test compare stock et `occupation_pct` avec et sans position
- [ ] CA11 : Les fiches `enregistrer-un-geste.md` (§ quantités, unités et rangs : les deux sens du mot rang), `parcelles-et-plan.md` (numérotation) et le guide utilisateur (§ 6.5) sont mis à jour dans la même livraison (US-099 / CA9) ; `docs/domaines/plan-et-rangs.md` et `migrations.md` aussi
- [ ] CA12 : Des tests couvrent : chaque forme dictée du CA2, la non-confusion du CA3, position hors bornes, geste préparé dans la PWA avec position, correction au Journal, répartition positionnée, mixte et en conflit

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram, enregistrement, consultation
- Migration BDD requise : **oui** — une colonne nullable de position de premier rang sur les événements, sans backfill (aucune position n'est supposée pour l'existant), rollback fourni. Numéro à lire dans `migrations/` au démarrage
- Dépendances : **US-198** (répartition), US-197 (nombre de rangs, pour la validation), US-094 (parseur déterministe, livré) ; US-196 et US-217 pour le transport depuis la PWA
- Impact tokens : zéro sur le chemin déterministe
- Point de vigilance : **le risque principal est la régression du multiplicateur**. « Planté 4 salades sur 3 rangs » doit toujours enregistrer 12 plants : c'est le premier test à écrire
- Point de vigilance : une position ne suit pas une culture dans le temps. Une récolte partielle ne déplace rien ; une nouvelle installation au même rang qu'une culture encore en place relève du CA8

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Planter au rang 3
  Given la planche centrale porte 5 rangs
  When le jardinier dicte "planté 8 tomates au rang 3 de la planche centrale"
  Then le récapitulatif propose 8 tomates, planche centrale, rang 3
  And après confirmation, la Vue plan affiche la tomate sur le rang 3

Scénario: Multiplicateur et position ensemble
  When le jardinier dicte "planté 6 poireaux sur 2 rangs à partir du rang 4 de la planche centrale"
  Then 12 poireaux sont enregistrés
  And ils occupent les rangs 4 et 5

Scénario: Le multiplicateur seul ne change pas
  When le jardinier dicte "planté 4 salades sur 3 rangs dans la planche nord"
  Then 12 salades sont enregistrées
  And aucune position de rang n'est enregistrée

Scénario: Rang inexistant
  Given la planche nord porte 5 rangs
  When le jardinier dicte "semé des radis au rang 7 de la planche nord"
  Then le récapitulatif signale que la planche nord n'a que 5 rangs
```

**Labels GitHub :** `us`, `bot`, `backend`, `migration`, `plan`, `optionnelle`

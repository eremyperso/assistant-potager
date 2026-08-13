**ID :** US-065
**Titre :** Exposer la pépinière par lot de semis avec un état de germination fiable

**Story :**
En tant que jardinier
Je veux que chaque lot de semis de ma pépinière soit suivi séparément, avec un état de germination explicite
Afin de voir où en est chacun de mes lots à son propre stade, et de savoir lequel est prêt à être repiqué ou planté

**Contexte fonctionnel :**
Brique de données préalable à la refonte de l'écran Pépinière (US-061, Lot B — voir `docs/ANALYSE_REFONTE_UI_WEB_2026.md` §3 et §7.2). La maquette introduit trois barres d'avancement — Germination, Godet, Terre. Cette US apporte les deux évolutions de données qu'elles supposent : **une décision produit** sur la maille de suivi, et **la correction d'un défaut de calcul**.

1. **Décision produit — un semis = un lot.** La pépinière est aujourd'hui agrégée par couple culture + variété. Ce niveau répond à la question « où en sont mes tomates Cœur de bœuf globalement », qui est légitime — les chiffres agrégés ne sont pas faux — mais ce n'est pas celle que se pose le jardinier devant sa pépinière : il veut savoir **quel lot est prêt à être repiqué ou planté**, et deux semis échelonnés d'une même variété n'en sont pas au même point. La maille de suivi devient donc l'**événement de semis**, règle simple et sans ambiguïté. À noter au passage : l'état de germination est par nature une propriété d'un lot semé, pas d'une variété — une variété comptant un lot terminé et un lot qui lève tout juste n'a pas d'état de germination unique.
2. **Défaut de calcul — le semis parent est soldé trop tôt.** `utils/stock.py` considère un semis parent **entièrement soldé dès le premier repiquage** (déduplication par `origine_graines_id`). Un repiquage échelonné fait donc sauter l'avancement à sa valeur finale alors qu'il reste des graines à lever. L'information manquante existe pourtant déjà : `nb_graines_semees`, le « sur N graines » saisi sur chaque mise en godet et déjà affiché dans la timeline.

**Point volontairement laissé ouvert :** le regroupement de lots semés à des dates très rapprochées (un même geste de semis étalé sur deux ou trois jours, qui produira ici autant de cartes que d'événements) n'est **pas traité par cette US**. La règle retenue est délibérément la plus simple — un événement de semis, un lot — quitte à multiplier les cartes ; un éventuel regroupement sera arbitré plus tard, à l'usage.

**Périmètre de non-régression, non négociable :** `calcul_godets()` et `GET /godets` ont quatre consommateurs — l'écran Pépinière, l'écran Stocks, l'endpoint `/stats` (`app/services/stats.py`) et les statistiques du bot (`bot.py`). Leur contrat actuel, agrégé par culture + variété, **ne change pas**. Cette US ajoute une lecture par lot à côté, elle ne transforme pas l'existante.

**Fiabilité de l'état de germination.** Le système ne peut jamais savoir qu'une graine « a germé mais n'a pas été mise en godet » : il sait seulement que toutes les graines semées ont été soldées par des lots de godets. Le repli silencieux actuel (`nb_graines_semees` sinon `nb_plants_godets`) fabrique donc un faux « germination en cours » indiscernable d'un vrai, avec une conséquence mesurée au cadrage : un lot de 10 graines ayant donné 7 plants, tous mis en terre, affiche « Terre 70 % » au lieu de 100 %, et n'atteint jamais 100 %. L'erreur va toujours dans le sens prudent — on sous-estime, jamais l'inverse — mais elle doit être **nommée** plutôt que subie.

**Critères d'acceptance :**
- [ ] CA1 : Une nouvelle lecture de la pépinière retourne un état **par lot de semis** — un lot = un événement de semis en pépinière, identifié par sa date — sans regroupement de lots proches dans le temps ; les mises en godet sans semis rattaché forment un lot distinct explicitement identifié comme tel. Cette lecture s'ajoute à la lecture agrégée existante (CA5), elle ne la remplace pas
- [ ] CA2 : Les graines encore en germination d'un lot sont calculées en déduisant les graines **lot de godet par lot de godet** (`nb_graines_semees` de chaque mise en godet, à défaut le nombre de plants du lot) au lieu de solder d'un coup la quantité du semis parent
- [ ] CA3 : Chaque lot expose un **état de germination à trois valeurs**, jamais deux : *en cours* (toutes les mises en godet ont déclaré leur nombre de graines, et il reste des graines non soldées), *close* (toutes les graines semées sont soldées), et *indéterminée* (au moins une mise en godet n'a pas déclaré son nombre de graines d'origine). L'état indéterminé n'est jamais présenté comme un « en cours » : c'est une information manquante, pas un stade
- [ ] CA4 : Une incohérence de saisie est signalée sur le lot lorsque le cumul des plants obtenus dépasse le nombre de graines semées — cas impossible dans la réalité, non couvert par le garde-fou existant qui ne contrôle qu'un lot de godet à la fois (`app/services/evenements.py`). L'incohérence est exposée telle quelle, sans bornage silencieux qui la masquerait
- [ ] CA5 : `calcul_godets()`, `GET /godets`, `/stats` et les statistiques du bot conservent **exactement** leur comportement et leur format actuels — l'écran Stocks, l'écran Statistiques et le bot ne sont pas impactés, ce qui est vérifié par les tests existants passant sans modification
- [ ] CA6 : Le détail du cycle de vie peut être demandé pour **un lot précis** et non plus seulement pour un couple culture + variété, afin que le panneau de détail de la pépinière puisse cibler le lot affiché
- [ ] CA7 : Toutes les quantités et l'état de germination sont calculés à la date de référence demandée, comme le fait déjà la lecture agrégée
- [ ] CA8 : Des tests unitaires couvrent : le déroulé de référence en quatre événements (semis de 10 graines → 5 plants sur 5 graines → 2 plants sur 5 graines → plantation de 5 godets), les semis échelonnés d'une même variété, un lot sans semis rattaché, une mise en godet sans nombre de graines déclaré (état indéterminé), l'incohérence du CA4, et la non-régression du CA5

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse (calcul de stock) et consultation
- Migration BDD requise : non — `nb_graines_semees` et `origine_graines_id` existent déjà sur les événements ; seul leur usage dans le calcul change
- Dépendances : s'appuie sur la traçabilité livrée par US-020 (lot de semis → godet) et US-029 (cycle de vie complet) ; **bloquante pour US-061** (refonte de l'écran Pépinière) ; complétée par US-066, qui traite la cause de l'état indéterminé au moment de la saisie
- Point de vigilance : le taux de germination déjà exposé et le stock résiduel en godet ne doivent pas changer de valeur pour les consommateurs existants

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Scénario: Deux semis échelonnés suivis séparément
  Given un semis de 10 graines de tomate en mars, dont 7 plants ont été mis en godet sur les 10 graines
  And un second semis de 10 graines de la même variété en avril, pas encore repiqué
  When la pépinière est consultée
  Then deux lots distincts sont retournés, identifiés par leur date de semis
  And chacun porte son propre avancement : 70% de germination pour le lot de mars, 0% pour celui d'avril
  And chacun porte son propre état de germination : close pour mars, en cours pour avril

Scénario: Repiquage échelonné sans solde anticipé
  Given un semis de 10 graines dont 5 plants ont été mis en godet sur 5 graines
  When l'état du lot est calculé
  Then il reste 5 graines en germination et l'état du lot est "en cours"
  When 2 plants supplémentaires sont mis en godet sur les 5 graines restantes
  Then il ne reste aucune graine en germination et l'état du lot devient "close"

Scénario: Nombre de graines non déclaré
  Given un semis de 10 graines dont une mise en godet de 5 plants sans nombre de graines d'origine
  When l'état du lot est calculé
  Then l'état de germination est "indéterminée" et non "en cours"

Scénario: Incohérence de saisie signalée
  Given un semis de 10 graines pour lequel 12 plants ont été mis en godet au total
  When l'état du lot est calculé
  Then une incohérence de saisie est signalée sur ce lot

Scénario: Aucun impact sur les écrans agrégés
  Given un potager avec plusieurs semis échelonnés de la même variété
  When l'écran Stocks, l'écran Statistiques et les statistiques du bot sont consultés
  Then ils affichent exactement les mêmes valeurs qu'avant cette évolution
```

**Labels GitHub :** `us`, `sprint-refonte-ui-2026`, `backend`, `pepiniere`
